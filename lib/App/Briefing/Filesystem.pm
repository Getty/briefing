package App::Briefing::Filesystem;
# ABSTRACT: Unicode-safe filesystem access for App::Briefing

use Moo;
use Encode qw( FB_CROAK decode encode );
use Path::Tiny qw( path );
use utf8 ();
use if $^O eq 'MSWin32', 'Win32::LongPath';
use namespace::clean;

our $VERSION = '0.001';

sub is_windows { $^O eq 'MSWin32' }

sub decode_path {
  my ( $self, $value ) = @_;
  return $value unless defined $value;
  return $value if utf8::is_utf8($value);

  my $decoded = eval { decode( 'UTF-8', $value, FB_CROAK ) };
  return $@ ? $value : $decoded;
}

sub _native_path {
  my ( $self, $value ) = @_;
  return $value
    if $self->is_windows || !defined $value || !utf8::is_utf8($value);

  my $encoded = eval { encode( 'UTF-8', $value, FB_CROAK ) };
  return $@ ? $value : $encoded;
}

sub join_path {
  my ( $self, @parts ) = @_;
  return '' unless @parts;

  my $joined = shift @parts;
  for my $part (@parts) {
    next unless defined $part && length $part;
    $joined = path($part)->is_absolute
      ? $part
      : path( $joined, $part )->stringify;
  }
  return path($joined)->stringify;
}

sub parent {
  my ( $self, $file ) = @_;
  return path($file)->parent->stringify;
}

sub basename {
  my ( $self, $file ) = @_;
  return path($file)->basename;
}

sub is_absolute {
  my ( $self, $file ) = @_;
  return path($file)->is_absolute ? 1 : 0;
}

sub current_dir {
  my ( $self ) = @_;
  my $directory = $self->is_windows
    ? Win32::LongPath::getcwdL()
    : path('.')->absolute->stringify;
  return $self->decode_path($directory);
}

sub absolute {
  my ( $self, $file ) = @_;
  my $absolute = $self->is_windows
    ? Win32::LongPath::abspathL($file)
    : $self->normalize( path($file)->absolute->stringify );
  return $self->decode_path($absolute);
}

sub exists {
  my ( $self, $file ) = @_;
  return Win32::LongPath::testL( 'e', $file ) ? 1 : 0
    if $self->is_windows;
  return path($file)->exists ? 1 : 0;
}

sub is_file {
  my ( $self, $file ) = @_;
  return Win32::LongPath::testL( 'f', $file ) ? 1 : 0
    if $self->is_windows;
  return path($file)->is_file ? 1 : 0;
}

sub is_dir {
  my ( $self, $file ) = @_;
  return Win32::LongPath::testL( 'd', $file ) ? 1 : 0
    if $self->is_windows;
  return path($file)->is_dir ? 1 : 0;
}

sub is_readable_file {
  my ( $self, $file ) = @_;
  return 0 unless $self->is_file($file);

  my $fh;
  my $opened = $self->is_windows
    ? Win32::LongPath::openL( \$fh, '<:encoding(UTF-8)', $file )
    : eval { $fh = path($file)->openr_utf8; 1 };
  return 0 unless $opened && $fh;
  close $fh;
  return 1;
}

sub _universal_newlines {
  my ( $self, $text ) = @_;
  $text = '' unless defined $text;
  $text =~ s/\r\n?/\n/g;
  return $text;
}

sub slurp_utf8 {
  my ( $self, $file ) = @_;
  return '' unless $self->is_file($file);

  if ($self->is_windows) {
    my $fh;
    return '' unless Win32::LongPath::openL(
      \$fh,
      '<:encoding(UTF-8)',
      $file,
    );
    local $/;
    my $text = <$fh>;
    close $fh;
    return $self->_universal_newlines($text);
  }

  my $text = eval { path($file)->slurp_utf8 };
  return $self->_universal_newlines($text);
}

sub spew_utf8 {
  my ( $self, $file, $text ) = @_;

  if ($self->is_windows) {
    my $fh;
    return 0 unless Win32::LongPath::openL(
      \$fh,
      '>:encoding(UTF-8)',
      $file,
    );
    my $ok = print {$fh} $text;
    $ok = close($fh) && $ok;
    return $ok ? 1 : 0;
  }

  return eval { path($file)->spew_utf8($text); 1 } ? 1 : 0;
}

sub make_path {
  my ( $self, $directory ) = @_;
  return 1 if $self->is_dir($directory);

  if ($self->is_windows) {
    my $parent = $self->parent($directory);
    return 0
      if $parent ne $directory
      && !$self->is_dir($parent)
      && !$self->make_path($parent);
    return 1 if Win32::LongPath::mkdirL($directory);
    return $self->is_dir($directory);
  }

  return eval { path($directory)->mkpath; 1 } ? 1 : 0;
}

sub children {
  my ( $self, $directory ) = @_;
  return [] unless $self->is_dir($directory);

  if ($self->is_windows) {
    my $dir = Win32::LongPath->new;
    return [] unless $dir->opendirL($directory);
    my @entries = $dir->readdirL;
    $dir->closedirL;
    return [
      sort
      map { $self->decode_path($_) }
      grep { $_ ne '.' && $_ ne '..' }
      @entries
    ];
  }

  my $native_directory = $self->_native_path($directory);
  my @children = eval { path($native_directory)->children };
  return [] if $@;
  return [ sort map { $self->decode_path( $_->basename ) } @children ];
}

sub child_directories {
  my ( $self, $directory ) = @_;
  return [
    grep { $self->is_dir($_) }
    map { $self->join_path( $directory, $_ ) }
    @{ $self->children($directory) }
  ];
}

sub walk_files {
  my ( $self, $root, $suffix ) = @_;
  return [] unless $self->is_dir($root);

  my @files;
  $self->_walk_files_into( \@files, $root, $suffix );
  return \@files;
}

sub _walk_files_into {
  my ( $self, $files, $directory, $suffix ) = @_;
  my @directories;
  for my $name (@{ $self->children($directory) }) {
    my $entry = $self->join_path( $directory, $name );
    if ($self->is_dir($entry)) {
      push @directories, $entry;
    }
    elsif ($self->is_file($entry) && $name =~ /\Q$suffix\E\z/) {
      push @{$files}, $entry;
    }
  }
  $self->_walk_files_into( $files, $_, $suffix ) for @directories;
  return;
}

sub normalize {
  my ( $self, $file ) = @_;
  my $value = defined $file ? $file : '';

  my $prefix = '';
  if ($self->is_windows) {
    $value =~ tr{\\}{/};
    if ($value =~ s{\A([A-Za-z]:)(?:/+)?}{}) {
      $prefix = $1.'/';
    }
    elsif ($value =~ s{\A/+}{}) {
      $prefix = '/';
    }
  }
  elsif ($value =~ s{\A/+}{}) {
    $prefix = '/';
  }

  my @parts;
  for my $part (split m{/+}, $value) {
    next if $part eq '' || $part eq '.';
    if ($part eq '..') {
      if (@parts && $parts[-1] ne '..') {
        pop @parts;
        next;
      }
      push @parts, $part unless $prefix;
      next;
    }
    push @parts, $part;
  }

  my $normalized = $prefix.join '/', @parts;
  $normalized = '/' if $normalized eq '' && $prefix eq '/';
  $normalized = lc $normalized if $self->is_windows;
  return $normalized;
}

sub within {
  my ( $self, $file, $root ) = @_;
  my $normalized_file = $self->normalize($file);
  my $normalized_root = $self->normalize($root);
  return 1 if $normalized_file eq $normalized_root;
  my $prefix = $normalized_root eq '/' ? '/' : $normalized_root.'/';
  return index( $normalized_file, $prefix ) == 0 ? 1 : 0;
}

sub relative {
  my ( $self, $file, $root ) = @_;
  return path($file)->relative($root)->stringify;
}

=description

This adapter keeps all filesystem access used by App::Briefing in one place.
POSIX systems use L<Path::Tiny>. Windows uses explicit L<Win32::LongPath>
operations so Unicode and long paths are not routed through Perl's ordinary
file tests or C<open>. It does not install global filesystem overrides.

=cut

1;
