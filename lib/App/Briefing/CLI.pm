package App::Briefing::CLI;
# ABSTRACT: Command-line interface for App::Briefing

use Moo;
use App::Briefing;
use Encode qw( encode_utf8 );
use JSON::MaybeXS ();
use namespace::clean;

our $VERSION = '0.001';

has _json => ( is => 'lazy', init_arg => undef );

sub app_class { 'App::Briefing' }

sub _build__json {
  my ( $self ) = @_;
  return JSON::MaybeXS->new(
    allow_nonref    => 0,
    canonical       => 1,
    convert_blessed => 1,
    utf8            => 1,
  );
}

sub _usage {
  my ( $self ) = @_;
  return <<'USAGE';
Usage:
  briefing hook
  briefing doctor [--cwd DIR] [--harness claude|codex|both]
  briefing notice
  briefing --help
  briefing --version
USAGE
}

sub _write_stdout {
  my ( $self, $text ) = @_;
  print STDOUT encode_utf8($text);
  return;
}

sub _write_stderr {
  my ( $self, $text ) = @_;
  print STDERR encode_utf8($text);
  return;
}

sub _write_json {
  my ( $self, $output, $newline ) = @_;
  print STDOUT $self->_json->encode($output);
  print STDOUT "\n" if $newline;
  return;
}

sub _application {
  my ( $self, %attributes ) = @_;
  my $class = $self->app_class;
  return $class->new(%attributes);
}

sub _run_hook {
  my ( $self ) = @_;
  local $/;
  my $raw = <STDIN>;
  return 0 unless defined $raw && length $raw;
  my $payload = eval { $self->_json->decode($raw) };
  return 0 unless ref $payload eq 'HASH';

  my $result = $self->_application->process_hook($payload);
  $self->_write_stderr( $result->{stderr} ) if length $result->{stderr};
  $self->_write_json( $result->{output}, 0 ) if defined $result->{output};
  return $result->{exit_code};
}

sub _doctor_options {
  my ( $self, $arguments ) = @_;
  my %options = ( cwd => '.', harness => 'both' );
  while (@{$arguments}) {
    my $argument = shift @{$arguments};
    if ($argument eq '--help') {
      return ( \%options, undef, 1 );
    }
    if ($argument eq '--cwd' || $argument eq '--harness') {
      return ( undef, $argument.' requires a value', 0 ) unless @{$arguments};
      my $key = substr( $argument, 2 );
      $options{$key} = shift @{$arguments};
      next;
    }
    if ($argument =~ /\A--(cwd|harness)=(.*)\z/s) {
      $options{$1} = $2;
      next;
    }
    return ( undef, 'unknown doctor option: '.$argument, 0 );
  }

  return ( undef, '--cwd requires a non-empty value', 0 )
    unless defined $options{cwd} && length $options{cwd};
  return ( undef, '--harness must be claude, codex, or both', 0 )
    unless $options{harness} eq 'claude'
      || $options{harness} eq 'codex'
      || $options{harness} eq 'both';
  return ( \%options, undef, 0 );
}

sub _doctor_problems {
  my ( $self, $result ) = @_;
  my ( @failures, @warnings );
  push @failures, 'unknown skill(s): '.join( ', ', @{ $result->{missing} } )
    if @{ $result->{missing} };
  push @failures,
    '[briefing] table '."\x{2014}".' Codex 0.153+ ignores this whole agent; use # briefing: skills = [...]'
    if $result->{legacy};
  push @warnings,
    int( $result->{size} / 1024 ).' kB of skill text, over 64 kB'
    if $result->{size} > 64 * 1024;
  return ( \@failures, \@warnings );
}

sub _harness_label {
  my ( $self, $harness ) = @_;
  return $harness eq 'claude' ? 'Claude Code' : 'Codex';
}

sub _run_doctor {
  my ( $self, $arguments ) = @_;
  my ( $options, $error, $help ) = $self->_doctor_options($arguments);
  if ($help) {
    $self->_write_stdout($self->_usage);
    return 0;
  }
  if (defined $error) {
    $self->_write_stderr('briefing doctor: '.$error."\n".$self->_usage);
    return 2;
  }

  my $base = $self->_application;
  my $cwd = $base->filesystem->absolute( $options->{cwd} );
  my $app = $self->_application(
    cwd        => $cwd,
    home       => $base->home,
    codex_home => $base->codex_home,
    filesystem => $base->filesystem,
  );
  my $results = $app->check_agents( harness => $options->{harness} );
  my $text = 'briefing doctor '."\x{2014}".' '.$cwd."\n";
  if (!@{$results}) {
    $self->_write_stdout( $text.'  no agents declare skills'."\n" );
    return 0;
  }

  my @harnesses = $options->{harness} eq 'both'
    ? qw( claude codex )
    : ($options->{harness});
  my $failed = 0;
  for my $harness (@harnesses) {
    my @entries = grep { $_->{harness} eq $harness } @{$results};
    next unless @entries;
    $text .= "\n".$self->_harness_label($harness)."\n";
    for my $result (@entries) {
      my ( $failures, $warnings ) = $self->_doctor_problems($result);
      my $where = $app->filesystem->within( $result->{path}, $cwd )
        ? $app->filesystem->relative( $result->{path}, $cwd )
        : $result->{path};
      my $status = @{$failures} ? 'FAIL' : @{$warnings} ? 'WARN' : 'ok';
      $failed = 1 if @{$failures};
      $text .= sprintf "  %-4s  %s  (%s)\n",
        $status,
        $result->{agent},
        $where;
      $text .= '        '.join( ', ', @{ $result->{skills} } ).'  ('
        .int( $result->{size} / 1024 ).' kB)'."\n";
      $text .= '        '."\x{2192}".' '.$_."\n"
        for ( @{$failures}, @{$warnings} );
    }
  }
  $self->_write_stdout($text);
  return $failed ? 1 : 0;
}

sub _run_notice {
  my ( $self ) = @_;
  my $result = $self->_application->process_notice({});
  $self->_write_stderr( $result->{stderr} ) if length $result->{stderr};
  $self->_write_json( $result->{output}, 1 ) if defined $result->{output};
  return $result->{exit_code};
}

sub run {
  my ( $invocant, $arguments ) = @_;
  my $self = ref $invocant ? $invocant : $invocant->new;
  $arguments = [] unless ref $arguments eq 'ARRAY';
  my @arguments = @{$arguments};

  binmode STDIN,  ':raw';
  binmode STDOUT, ':raw';
  binmode STDERR, ':raw';

  my $command = @arguments ? shift @arguments : '--help';
  if ($command eq '--help' || $command eq 'help') {
    $self->_write_stdout($self->_usage);
    return 0;
  }
  if ($command eq '--version') {
    $self->_write_stdout('briefing '.$App::Briefing::VERSION."\n");
    return 0;
  }
  if ($command eq 'hook') {
    return $self->_run_hook if !@arguments;
  }
  elsif ($command eq 'doctor') {
    return $self->_run_doctor(\@arguments);
  }
  elsif ($command eq 'notice') {
    return $self->_run_notice if !@arguments;
  }

  $self->_write_stderr('briefing: unknown command or arguments'."\n".$self->_usage);
  return 2;
}

=method run

    exit App::Briefing::CLI->run(\@ARGV);

Runs one C<hook>, C<doctor> or C<notice> command and returns its process exit
code. C<--help> and C<--version> are handled without constructing a briefing
context.

=cut

=description

This is the terminal adapter for L<App::Briefing>. Hook processing, notice
state and agent resolution remain library operations; this class owns argument
parsing and standard-stream I/O.

=cut

1;
