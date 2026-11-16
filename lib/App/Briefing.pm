package App::Briefing;
# ABSTRACT: Preload declared skills for fresh subagents

use Moo;
use App::Briefing::Filesystem;
use B qw( SVf_POK SVp_POK svref_2object );
use Carp qw( croak );
use Encode qw( encode_utf8 );
use JSON::MaybeXS ();
use TOML::Tiny::Parser;
use namespace::clean;

our $VERSION = '0.001';

use constant BUDGET_BYTES => 64 * 1024;

has filesystem => ( is => 'lazy' );

=attr filesystem

Filesystem adapter. Defaults to a new L<App::Briefing::Filesystem> object.

=cut

has cwd => ( is => 'lazy' );

=attr cwd

Project context used for agent and skill lookup. Defaults to the process current
directory without changing it.

=cut

has home => ( is => 'lazy' );

=attr home

Harness user home. Defaults to C<HOME>, then the platform user home.

=cut

has codex_home => ( is => 'lazy' );

=attr codex_home

Codex configuration root. Defaults to C<CODEX_HOME> or F<.codex> below C<home>.

=cut

has _json => ( is => 'lazy', init_arg => undef );

sub filesystem_class { 'App::Briefing::Filesystem' }
sub toml_parser_class { 'TOML::Tiny::Parser' }

sub _build_filesystem {
  my ( $self ) = @_;
  return $self->filesystem_class->new;
}

sub _environment_path {
  my ( $self, $value ) = @_;
  return $self->filesystem->decode_path($value);
}

sub _build_cwd {
  my ( $self ) = @_;
  return $self->_environment_path( $ENV{PWD} )
    if defined $ENV{PWD} && length $ENV{PWD};
  return $self->filesystem->current_dir;
}

sub _build_home {
  my ( $self ) = @_;
  return $self->_environment_path( $ENV{HOME} )
    if defined $ENV{HOME} && length $ENV{HOME};

  if ($self->filesystem->is_windows) {
    return $self->_environment_path( $ENV{USERPROFILE} )
      if defined $ENV{USERPROFILE} && length $ENV{USERPROFILE};
    return $self->_environment_path( $ENV{HOMEDRIVE}.$ENV{HOMEPATH} )
      if defined $ENV{HOMEDRIVE}
      && length $ENV{HOMEDRIVE}
      && defined $ENV{HOMEPATH}
      && length $ENV{HOMEPATH};
  }

  my $home = (getpwuid $<)[7];
  return $self->_environment_path($home) if defined $home && length $home;
  return $self->filesystem->current_dir;
}

sub _build_codex_home {
  my ( $self ) = @_;
  return $self->_environment_path( $ENV{CODEX_HOME} )
    if defined $ENV{CODEX_HOME} && length $ENV{CODEX_HOME};
  return $self->filesystem->join_path( $self->home, '.codex' );
}

sub _build__json {
  my ( $self ) = @_;
  return JSON::MaybeXS->new(
    allow_nonref    => 0,
    canonical       => 1,
    convert_blessed => 1,
    utf8            => 0,
  );
}

sub _is_string {
  my ( $self, $value ) = @_;
  return 0 unless defined $value && !ref $value;
  my $flags = svref_2object( \$value )->FLAGS;
  return $flags & ( SVf_POK | SVp_POK ) ? 1 : 0;
}

sub _nonempty_string {
  my ( $self, $value ) = @_;
  return $self->_is_string($value) && length $value ? 1 : 0;
}

sub _trim {
  my ( $self, $value ) = @_;
  $value = '' unless defined $value;
  $value =~ s/\A\s+//;
  $value =~ s/\s+\z//;
  return $value;
}

sub _split_frontmatter {
  my ( $self, $text ) = @_;
  $text = '' unless defined $text;
  return ( $1, $2 )
    if $text =~ /\A---\r?\n(.*?)\r?\n---\r?\n(.*)\z/s;
  return ( '', $text );
}

sub _dedent {
  my ( $self, $block ) = @_;
  my @lines = split /\r?\n/, $block, -1;
  my @indents = map {
    my ( $indent ) = /\A([ \t]*)/;
    length $indent;
  } grep { /\S/ } @lines;
  return $block unless @indents;

  my $common = $indents[0];
  for my $indent (@indents) {
    $common = $indent if $indent < $common;
  }
  return join( "\n", map { length($_) >= $common ? substr( $_, $common ) : $_ } @lines );
}

sub _parse_skills_list {
  my ( $self, $frontmatter ) = @_;
  return [] unless defined $frontmatter && length $frontmatter;
  return [] unless $frontmatter =~ /^briefing:[ \t]*\r?\n((?:[ \t]+[^\r\n]*(?:\r?\n|$))+)/m;

  my $block = $self->_dedent($1);
  if ($block =~ /^skills:[ \t]*\r?\n((?:[ \t]*-[ \t]*[^\r\n]+\r?\n?)+)/m) {
    my $items = $1;
    my @skills;
    while ($items =~ /^[ \t]*-[ \t]*(["']?)([^"'\r\n]+)\1[ \t]*$/mg) {
      my $skill = $self->_trim($2);
      push @skills, $skill if length $skill;
    }
    return \@skills;
  }

  if ($block =~ /^skills:[ \t]*\[([^\]\r\n]+)\]/m) {
    my @skills;
    for my $item (split /,/, $1) {
      $item = $self->_trim($item);
      $item =~ s/\A["']//;
      $item =~ s/["']\z//;
      push @skills, $item if length $item;
    }
    return \@skills;
  }
  return [];
}

sub _parse_frontmatter_name {
  my ( $self, $frontmatter ) = @_;
  return unless defined $frontmatter;
  return $self->_trim($2)
    if $frontmatter =~ /^name:[ \t]*(["']?)([^"'\r\n]+?)\1[ \t]*$/m;
  return;
}

sub _find_first_readable {
  my ( $self, @files ) = @_;
  for my $file (@files) {
    next unless defined $file && length $file;
    return $file if $self->filesystem->is_readable_file($file);
  }
  return;
}

sub _claude_agent_roots {
  my ( $self ) = @_;
  return (
    $self->filesystem->join_path( $self->cwd,  '.claude', 'agents' ),
    $self->filesystem->join_path( $self->home, '.claude', 'agents' ),
  );
}

sub _claude_agent_name {
  my ( $self, $file ) = @_;
  my ( $frontmatter ) = $self->_split_frontmatter(
    $self->filesystem->slurp_utf8($file),
  );
  my $name = $self->_parse_frontmatter_name($frontmatter);
  return $name if defined $name;
  my $basename = $self->filesystem->basename($file);
  $basename =~ s/\.md\z//;
  return $basename;
}

sub _find_claude_agent {
  my ( $self, $agent ) = @_;
  for my $root ($self->_claude_agent_roots) {
    next unless $self->filesystem->is_dir($root);
    my $direct = $self->filesystem->join_path( $root, $agent.'.md' );
    if (
      $self->_find_first_readable($direct)
      && $self->_claude_agent_name($direct) eq $agent
    ) {
      return $direct;
    }
    for my $file (@{ $self->filesystem->walk_files( $root, '.md' ) }) {
      next if $file eq $direct;
      return $file if $self->_claude_agent_name($file) eq $agent;
    }
  }
  return;
}

sub _list_claude_agents {
  my ( $self ) = @_;
  my %agents;
  for my $root ($self->_claude_agent_roots) {
    next unless $self->filesystem->is_dir($root);
    for my $file (@{ $self->filesystem->walk_files( $root, '.md' ) }) {
      my $name = $self->_claude_agent_name($file);
      $agents{$name} = $file unless exists $agents{$name};
    }
  }
  return \%agents;
}

sub _load_json {
  my ( $self, $file ) = @_;
  my $text = $self->filesystem->slurp_utf8($file);
  my $data = eval { $self->_json->decode( length($text) ? $text : '{}' ) };
  return ref $data eq 'HASH' ? $data : {};
}

sub _enabled_plugins {
  my ( $self ) = @_;
  my %enabled;
  for my $file (
    $self->filesystem->join_path( $self->home, '.claude', 'settings.json' ),
    $self->filesystem->join_path( $self->cwd, '.claude', 'settings.json' ),
    $self->filesystem->join_path( $self->cwd, '.claude', 'settings.local.json' ),
  ) {
    my $values = $self->_load_json($file)->{enabledPlugins};
    next unless ref $values eq 'HASH';
    for my $key (keys %{$values}) {
      next unless JSON::MaybeXS::is_bool( $values->{$key} );
      $enabled{$key} = $values->{$key} ? 1 : 0;
    }
  }
  return \%enabled;
}

sub _claude_plugins {
  my ( $self ) = @_;
  my $registry = $self->_load_json(
    $self->filesystem->join_path(
      $self->home,
      '.claude',
      'plugins',
      'installed_plugins.json',
    ),
  )->{plugins};
  return [] unless ref $registry eq 'HASH';

  my $enabled = $self->_enabled_plugins;
  my @found;
  for my $key (keys %{$registry}) {
    next unless $enabled->{$key};
    my $entries = $registry->{$key};
    next unless ref $entries eq 'ARRAY';
    for my $entry (@{$entries}) {
      next unless ref $entry eq 'HASH';
      my $root = $entry->{installPath};
      next unless $self->_nonempty_string($root);
      my $project = $entry->{projectPath};
      if ($self->_nonempty_string($project)) {
        next unless $self->filesystem->within( $self->cwd, $project );
        push @found, [ -length($project), $key, $root ];
      }
      else {
        push @found, [ 0, $key, $root ];
      }
    }
  }

  my @plugins;
  for my $item (sort {
    $a->[0] <=> $b->[0]
      || $a->[1] cmp $b->[1]
      || $a->[2] cmp $b->[2]
  } @found) {
    my ( undef, $key, $root ) = @{$item};
    my $manifest = $self->_load_json(
      $self->filesystem->join_path(
        $root,
        '.claude-plugin',
        'plugin.json',
      ),
    );
    my $name = $self->_nonempty_string( $manifest->{name} )
      ? $manifest->{name}
      : (split /\@/, $key, 2)[0];
    push @plugins, [ $name, $root, $manifest ];
  }
  return \@plugins;
}

sub _plugin_skill_dirs {
  my ( $self, $root, $manifest ) = @_;
  my $extra = $manifest->{skills};
  my @extra = $self->_is_string($extra)
    ? ($extra)
    : ref $extra eq 'ARRAY'
      ? grep { $self->_is_string($_) } @{$extra}
      : ();
  my @bases = (
    $self->filesystem->join_path( $root, 'skills' ),
    map { $self->filesystem->join_path( $root, $_ ) } @extra,
  );

  my @directories;
  for my $base (@bases) {
    next unless $self->filesystem->within( $base, $root );
    if ($self->filesystem->is_file(
      $self->filesystem->join_path( $base, 'SKILL.md' ),
    )) {
      push @directories, $base;
      next;
    }
    next unless $self->filesystem->is_dir($base);
    for my $directory (@{ $self->filesystem->child_directories($base) }) {
      push @directories, $directory
        if $self->filesystem->is_file(
          $self->filesystem->join_path( $directory, 'SKILL.md' ),
        );
    }
  }
  return \@directories;
}

sub _resolve_plugin_skill {
  my ( $self, $skill, $wanted_plugin ) = @_;
  for my $plugin (@{ $self->_claude_plugins }) {
    my ( $name, $root, $manifest ) = @{$plugin};
    next if defined $wanted_plugin && $name ne $wanted_plugin;
    for my $directory (@{ $self->_plugin_skill_dirs( $root, $manifest ) }) {
      next unless $self->filesystem->basename($directory) eq $skill;
      my $file = $self->filesystem->join_path( $directory, 'SKILL.md' );
      return $file if $self->filesystem->is_readable_file($file);
    }
  }
  return;
}

sub _resolve_skill_claude {
  my ( $self, $name ) = @_;
  if ($name =~ /:/ && $name !~ /\A:/) {
    my ( $plugin, $skill ) = split /:/, $name, 2;
    return $self->_resolve_plugin_skill( $skill, $plugin )
      if length($plugin) && length($skill) && $plugin !~ / /;
  }

  for my $base (
    $self->filesystem->join_path( $self->cwd,  '.claude', 'skills' ),
    $self->filesystem->join_path( $self->home, '.claude', 'skills' ),
  ) {
    my $file = $self->filesystem->join_path( $base, $name, 'SKILL.md' );
    return $file if $self->filesystem->is_readable_file($file);
  }
  return $self->_resolve_plugin_skill($name);
}

sub _toml_string_state {
  my ( $self, $line, $state ) = @_;
  my $index = 0;
  my $length = length $line;
  while ($index < $length) {
    if (!defined $state) {
      my $character = substr( $line, $index, 1 );
      last if $character eq '#';
      my $triple = substr( $line, $index, 3 );
      if ($triple eq q{"""} || $triple eq q{'''}) {
        $state = $triple;
        $index += 3;
        next;
      }
      if ($character eq q{"} || $character eq q{'}) {
        $index++;
        while ($index < $length && substr( $line, $index, 1 ) ne $character) {
          $index += $character eq q{"}
            && substr( $line, $index, 1 ) eq '\\'
            ? 2
            : 1;
        }
      }
      $index++;
      next;
    }

    if ($state eq q{"""} && substr( $line, $index, 1 ) eq '\\') {
      $index += 2;
      next;
    }
    if (substr( $line, $index, 3 ) eq $state) {
      $state = undef;
      $index += 3;
      next;
    }
    $index++;
  }
  return $state;
}

sub _parse_skills_comment {
  my ( $self, $text ) = @_;
  my $state;
  for my $line (split /\r?\n/, defined $text ? $text : '') {
    if (!defined $state && $line =~ /\A[ \t]*#[ \t]*briefing:[ \t]*skills[ \t]*=[ \t]*\[([^\]\r\n]*)\]/) {
      my $items = $1;
      my @skills;
      while ($items =~ /["']([^"']+)["']/g) {
        my $skill = $self->_trim($1);
        push @skills, $skill if length $skill;
      }
      return \@skills;
    }
    $state = $self->_toml_string_state( $line, $state );
  }
  return [];
}

sub _parse_toml {
  my ( $self, $text ) = @_;
  return {} unless defined $text && length $text;
  my $parser_class = $self->toml_parser_class;
  my $document = eval {
    $parser_class->new(
      strict           => 1,
      inflate_boolean  => sub { return [ boolean => $_[0] ] },
      inflate_datetime => sub { return [ datetime => $_[0] ] },
      inflate_float    => sub { return [ float => $_[0] ] },
      inflate_integer  => sub { return [ integer => $_[0] ] },
    )->parse( encode_utf8($text) );
  };
  return ref $document eq 'HASH' ? $document : {};
}

sub _parse_skills_toml {
  my ( $self, $text ) = @_;
  my $document = $self->_parse_toml($text);
  my $briefing = $document->{briefing};
  return [] unless ref $briefing eq 'HASH';
  my $skills = $briefing->{skills};
  return [] unless ref $skills eq 'ARRAY';
  return [
    map { $self->_trim($_) }
    grep { $self->_is_string($_) && length $self->_trim($_) }
    @{$skills}
  ];
}

sub _parse_toml_name {
  my ( $self, $text ) = @_;
  my $state;
  for my $line (split /\r?\n/, defined $text ? $text : '') {
    if (!defined $state) {
      return if $line =~ /\A[ \t]*\[/;
      if ($line =~ /\A[ \t]*name[ \t]*=[ \t]*(?:"([^"\\]*)"|'([^']*)')/) {
        return defined $1 ? $1 : $2;
      }
    }
    $state = $self->_toml_string_state( $line, $state );
  }
  return;
}

sub _project_dirs {
  my ( $self ) = @_;
  my $cwd = $self->filesystem->absolute( $self->cwd );
  my @directories;
  my $directory = $cwd;
  while (1) {
    push @directories, $directory;
    return \@directories
      if $self->filesystem->exists(
        $self->filesystem->join_path( $directory, '.git' ),
      );
    my $parent = $self->filesystem->parent($directory);
    return [$cwd] if $parent eq $directory;
    $directory = $parent;
  }
}

sub _codex_layers {
  my ( $self ) = @_;
  return [
    (map { $self->filesystem->join_path( $_, '.codex' ) }
      @{ $self->_project_dirs }),
    $self->codex_home,
    $self->filesystem->join_path( '/', 'etc', 'codex' ),
  ];
}

sub _expand_home {
  my ( $self, $file ) = @_;
  return $self->home if $file eq '~';
  return $self->filesystem->join_path( $self->home, substr( $file, 2 ) )
    if $file =~ /\A~[\\\/]/;
  return $file;
}

sub _declared_roles {
  my ( $self, $layer ) = @_;
  my $document = $self->_parse_toml(
    $self->filesystem->slurp_utf8(
      $self->filesystem->join_path( $layer, 'config.toml' ),
    ),
  );
  my $agents = $document->{agents};
  return {} unless ref $agents eq 'HASH';

  my %roles;
  for my $name (keys %{$agents}) {
    my $role = $agents->{$name};
    next unless ref $role eq 'HASH';
    my $file = $role->{config_file};
    next unless $self->_nonempty_string($file);
    $file = $self->_expand_home($file);
    $roles{$name} = $self->filesystem->is_absolute($file)
      ? $file
      : $self->filesystem->join_path( $layer, $file );
  }
  return \%roles;
}

sub _find_codex_agent {
  my ( $self, $agent ) = @_;
  for my $layer (@{ $self->_codex_layers }) {
    my $declared = $self->_declared_roles($layer)->{$agent};
    if ($declared && $self->_find_first_readable($declared)) {
      return ( $declared, $self->filesystem->slurp_utf8($declared) );
    }

    my $root = $self->filesystem->join_path( $layer, 'agents' );
    next unless $self->filesystem->is_dir($root);
    my $direct = $self->filesystem->join_path( $root, $agent.'.toml' );
    if ($self->_find_first_readable($direct)) {
      my $text = $self->filesystem->slurp_utf8($direct);
      my $name = $self->_parse_toml_name($text);
      return ( $direct, $text ) if !defined $name || $name eq $agent;
    }
    for my $file (@{ $self->filesystem->walk_files( $root, '.toml' ) }) {
      next if $file eq $direct;
      my $text = $self->filesystem->slurp_utf8($file);
      my $name = $self->_parse_toml_name($text);
      return ( $file, $text ) if defined $name && $name eq $agent;
    }
  }
  return;
}

sub _list_codex_agents {
  my ( $self ) = @_;
  my %agents;
  for my $layer (@{ $self->_codex_layers }) {
    my %layer_agents;
    my $declared = $self->_declared_roles($layer);
    for my $name (keys %{$declared}) {
      $layer_agents{$name} = $declared->{$name}
        if $self->_find_first_readable( $declared->{$name} );
    }

    my $root = $self->filesystem->join_path( $layer, 'agents' );
    if ($self->filesystem->is_dir($root)) {
      for my $file (@{ $self->filesystem->walk_files( $root, '.toml' ) }) {
        my $name = $self->_parse_toml_name(
          $self->filesystem->slurp_utf8($file),
        );
        $layer_agents{$name} = $file
          if defined $name && !exists $layer_agents{$name};
      }
    }

    for my $name (keys %layer_agents) {
      $agents{$name} = $layer_agents{$name} unless exists $agents{$name};
    }
  }
  return \%agents;
}

sub _resolve_codex_plugin_skill {
  my ( $self, $plugin, $skill ) = @_;
  my $cache = $self->filesystem->join_path(
    $self->codex_home,
    'plugins',
    'cache',
  );

  for my $marketplace (@{ $self->filesystem->child_directories($cache) }) {
    my $plugin_root = $self->filesystem->join_path( $marketplace, $plugin );
    for my $version (@{ $self->filesystem->child_directories($plugin_root) }) {
      my $file = $self->filesystem->join_path(
        $version,
        'skills',
        $skill,
        'SKILL.md',
      );
      return $file if $self->filesystem->is_readable_file($file);
    }
  }

  my $direct_root = $self->filesystem->join_path( $cache, $plugin );
  for my $version (@{ $self->filesystem->child_directories($direct_root) }) {
    my $file = $self->filesystem->join_path(
      $version,
      'skills',
      $skill,
      'SKILL.md',
    );
    return $file if $self->filesystem->is_readable_file($file);
  }

  for my $marketplace (@{ $self->filesystem->child_directories($cache) }) {
    my $file = $self->filesystem->join_path(
      $marketplace,
      $plugin,
      'skills',
      $skill,
      'SKILL.md',
    );
    return $file if $self->filesystem->is_readable_file($file);
  }
  return;
}

sub _resolve_skill_codex {
  my ( $self, $name ) = @_;
  if ($name =~ /:/ && $name !~ /\A:/) {
    my ( $plugin, $skill ) = split /:/, $name, 2;
    return $self->_resolve_codex_plugin_skill( $plugin, $skill )
      if length($plugin) && length($skill) && $plugin !~ / /;
  }

  my @bases;
  for my $directory (@{ $self->_project_dirs }) {
    push @bases,
      $self->filesystem->join_path( $directory, '.codex',  'skills' ),
      $self->filesystem->join_path( $directory, '.agents', 'skills' );
  }
  push @bases,
    $self->filesystem->join_path( $self->codex_home, 'skills' ),
    $self->filesystem->join_path( $self->home, '.agents', 'skills' ),
    $self->filesystem->join_path( $self->codex_home, 'skills', '.system' ),
    $self->filesystem->join_path( '/', 'etc', 'codex', 'skills' );

  for my $base (@bases) {
    my $file = $self->filesystem->join_path( $base, $name, 'SKILL.md' );
    return $file if $self->filesystem->is_readable_file($file);
  }
  return;
}

sub _claude_declaration {
  my ( $self, $file ) = @_;
  my ( $frontmatter ) = $self->_split_frontmatter(
    $self->filesystem->slurp_utf8($file),
  );
  return ( $self->_parse_skills_list($frontmatter), 0 );
}

sub _codex_declaration {
  my ( $self, $text ) = @_;
  my $legacy = $self->_parse_skills_toml($text);
  my $comment = $self->_parse_skills_comment($text);
  return ( @{$comment} ? $comment : $legacy, @{$legacy} ? 1 : 0 );
}

sub _briefing_result {
  my ( $self, $agent, $path, $skills, $harness, $legacy ) = @_;
  my @missing;
  my @blocks;
  for my $name (@{$skills}) {
    my $skill_file = $harness eq 'claude'
      ? $self->_resolve_skill_claude($name)
      : $self->_resolve_skill_codex($name);
    if (!$skill_file) {
      push @missing, $name;
      next;
    }
    my ( undef, $body ) = $self->_split_frontmatter(
      $self->filesystem->slurp_utf8($skill_file),
    );
    my $directory = $self->filesystem->absolute(
      $self->filesystem->parent($skill_file),
    );
    push @blocks,
      '<skill name="'.$name.'" dir="'.$directory.'">'."\n"
      .$self->_trim($body)."\n</skill>";
  }

  my $resolved_text = join "\n\n", @blocks;
  return {
    agent   => $agent,
    path    => $path,
    harness => $harness,
    skills  => [ @{$skills} ],
    missing => \@missing,
    text    => @missing ? '' : $resolved_text,
    size    => length encode_utf8($resolved_text),
    legacy  => $legacy ? 1 : 0,
  };
}

sub _brief_agent_claude {
  my ( $self, $agent ) = @_;
  my $file = $self->_find_claude_agent($agent);
  return unless $file;
  my ( $skills, $legacy ) = $self->_claude_declaration($file);
  return unless @{$skills};
  return $self->_briefing_result(
    $agent,
    $file,
    $skills,
    'claude',
    $legacy,
  );
}

sub _brief_agent_codex {
  my ( $self, $agent ) = @_;
  my ( $file, $text ) = $self->_find_codex_agent($agent);
  return unless $file;
  my ( $skills, $legacy ) = $self->_codex_declaration($text);
  return unless @{$skills};
  return $self->_briefing_result(
    $agent,
    $file,
    $skills,
    'codex',
    $legacy,
  );
}

sub brief_agent {
  my ( $self, $agent, %options ) = @_;
  my $harness = $options{harness};
  croak __PACKAGE__.'->brief_agent requires harness claude or codex'
    unless defined $harness && ($harness eq 'claude' || $harness eq 'codex');
  return $harness eq 'claude'
    ? $self->_brief_agent_claude($agent)
    : $self->_brief_agent_codex($agent);
}

=method brief_agent

    my $result = $briefing->brief_agent('reviewer', harness => 'claude');

Resolves one agent declaration. Returns C<undef> when the harness has no
briefing-aware agent by that name. A result records the declaration, missing
skills, UTF-8 byte size and injected text. If any skill is missing, C<text> is
empty rather than a partial briefing.

=cut

sub check_agents {
  my ( $self, %options ) = @_;
  my $harness = defined $options{harness} ? $options{harness} : 'both';
  croak __PACKAGE__.'->check_agents requires harness claude, codex, or both'
    unless $harness eq 'claude' || $harness eq 'codex' || $harness eq 'both';

  my @results;
  if ($harness eq 'claude' || $harness eq 'both') {
    my $agents = $self->_list_claude_agents;
    for my $name (sort keys %{$agents}) {
      my $result = $self->_brief_agent_claude($name);
      push @results, $result if $result;
    }
  }
  if ($harness eq 'codex' || $harness eq 'both') {
    my $agents = $self->_list_codex_agents;
    for my $name (sort keys %{$agents}) {
      my $result = $self->_brief_agent_codex($name);
      push @results, $result if $result;
    }
  }
  return \@results;
}

=method check_agents

    my $results = $briefing->check_agents(harness => 'both');

Returns every briefing-aware agent in harness resolution order. It performs the
same resolution used at spawn time and has no output side effects.

=cut

sub _for_payload {
  my ( $self, $payload ) = @_;
  my $cwd = $payload->{cwd};
  return $self unless $self->_nonempty_string($cwd) && $cwd ne $self->cwd;
  return $self->new(
    cwd        => $cwd,
    home       => $self->home,
    codex_home => $self->codex_home,
    filesystem => $self->filesystem,
  );
}

sub _harnesses_for_payload {
  my ( $self, $payload ) = @_;
  my $transcript = $payload->{transcript_path};
  $transcript = '' unless $self->_is_string($transcript);
  $transcript =~ tr{\\}{/};
  my $codex_home = $self->codex_home;
  $codex_home =~ tr{\\}{/};
  return ['codex']
    if index( $transcript, '/.codex/' ) >= 0
    || (length($codex_home) && index( $transcript, $codex_home.'/' ) == 0);
  return ['claude'] if index( $transcript, '/.claude/' ) >= 0;
  return [qw( claude codex )];
}

sub _spawn_harness {
  my ( $self, $payload, $agent ) = @_;
  my $harnesses = $self->_harnesses_for_payload($payload);
  return $harnesses->[0] if @{$harnesses} == 1;
  return 'codex' if exists $payload->{turn_id};
  return $self->_find_claude_agent($agent) ? 'claude' : 'codex';
}

sub _legacy_note {
  my ( $self, $result ) = @_;
  return 'briefing: '.$result->{path}
    .' declares skills in a [briefing] table. Codex 0.153+ rejects that as an '
    .'unknown field and ignores the whole agent. Replace the table with a '
    .'comment line: # briefing: skills = [...]';
}

sub _missing_note {
  my ( $self, $result ) = @_;
  return "briefing: agent '".$result->{agent}."' references unknown skill(s): "
    .join( ', ', @{ $result->{missing} } );
}

sub _size_note {
  my ( $self, $result ) = @_;
  return "briefing: agent '".$result->{agent}."' is briefed with "
    .int( $result->{size} / 1024 ).' kB of skill text (over '
    .int( BUDGET_BYTES / 1024 ).' kB) '."\x{2014}".' consider declaring fewer or smaller skills.';
}

sub _audit_line {
  my ( $self, $result ) = @_;
  my $kilobytes = 0;
  if ($result->{size}) {
    my $whole = int( $result->{size} / 1024 );
    my $remainder = $result->{size} % 1024;
    $kilobytes = $whole
      + ($remainder > 512 || ($remainder == 512 && $whole % 2) ? 1 : 0);
    $kilobytes = 1 if $kilobytes < 1;
  }
  return 'briefing: '.$result->{agent}.' '."\x{2190}".' '
    .join( ', ', @{ $result->{skills} } ).' ('.$kilobytes.' kB)';
}

sub _problems {
  my ( $self, $result ) = @_;
  my ( @failures, @warnings );
  push @failures, 'unknown skill(s): '.join( ', ', @{ $result->{missing} } )
    if @{ $result->{missing} };
  push @failures,
    '[briefing] table '."\x{2014}".' Codex 0.153+ ignores this whole agent; use # briefing: skills = [...]'
    if $result->{legacy};
  push @warnings,
    int( $result->{size} / 1024 ).' kB of skill text, over '
      .int( BUDGET_BYTES / 1024 ).' kB'
    if $result->{size} > BUDGET_BYTES;
  return ( \@failures, \@warnings );
}

sub _spawn_header {
  my ( $self, $harness ) = @_;
  my $dont = $harness eq 'claude'
    ? 'do NOT call the Skill tool for any of these names'
    : 'do NOT go looking for their SKILL.md files';
  return '# Briefing '."\x{2014}".' pre-loaded skills'."\n\n"
    .'The skills below have been injected directly into your context by the'."\n"
    .'briefing plugin, one <skill> element each. Treat them as already loaded '."\x{2014}\n"
    .$dont.'; their content is already here. Only the SKILL.md body is'."\n"
    .'included: paths a skill mentions (references/, scripts/, '."\x{2026}"
    .') are relative to'."\n"
    .'its element\'s dir, so read them from there when you need them.'."\n\n";
}

sub _abort_context {
  my ( $self, $result ) = @_;
  return '# Briefing '."\x{2014}".' FAILED'."\n\n"
    .'The skills this agent declares could not be loaded: '
    .join( ', ', @{ $result->{missing} } ).'.'."\n\n"
    .'You are NOT briefed for this task. Do NOT attempt it and do NOT'."\n"
    .'improvise a substitute. Report this exact failure to whoever'."\n"
    .'delegated to you, and stop.'."\n";
}

sub _process_subagent_start {
  my ( $self, $payload ) = @_;
  my $agent = $payload->{agent_type};
  return ( undef, '' ) unless $self->_nonempty_string($agent);

  my $harness = $self->_spawn_harness( $payload, $agent );
  my $result = $self->brief_agent( $agent, harness => $harness );
  return ( undef, '' ) unless $result;

  my @notes = $result->{legacy} ? ($self->_legacy_note($result)) : ();
  if (@{ $result->{missing} }) {
    my $message = $self->_missing_note($result);
    return (
      {
        systemMessage      => join( "\n", $message, @notes ),
        hookSpecificOutput => {
          hookEventName     => 'SubagentStart',
          additionalContext => $self->_abort_context($result),
        },
      },
      $message."\n",
    );
  }

  push @notes, $self->_size_note($result)
    if $result->{size} > BUDGET_BYTES;
  my $stderr = @notes ? join( "\n", @notes )."\n" : '';
  return (
    {
      systemMessage      => join( "\n", $self->_audit_line($result), @notes ),
      hookSpecificOutput => {
        hookEventName     => 'SubagentStart',
        additionalContext => $self->_spawn_header($harness).$result->{text},
      },
    },
    $stderr,
  );
}

sub _process_guard {
  my ( $self, $payload ) = @_;
  my $tool_input = $payload->{tool_input};
  return ( undef, '' ) unless ref $tool_input eq 'HASH';
  my $agent = $tool_input->{subagent_type};
  return ( undef, '' ) unless $self->_nonempty_string($agent);

  my $result = $self->brief_agent( $agent, harness => 'claude' );
  return ( undef, '' ) unless $result && @{ $result->{missing} };
  my $message = $self->_missing_note($result);
  return (
    {
      hookSpecificOutput => {
        hookEventName            => 'PreToolUse',
        permissionDecision       => 'deny',
        permissionDecisionReason => $message,
      },
    },
    $message."\n",
  );
}

sub _harness_label {
  my ( $self, $harness ) = @_;
  return $harness eq 'claude' ? 'Claude Code' : 'Codex';
}

sub _process_session_start {
  my ( $self, $payload ) = @_;
  my $source = $payload->{source};
  return ( undef, '' )
    if defined $source && ($source ne 'startup' && $source ne 'resume');

  my @lines;
  for my $harness (@{ $self->_harnesses_for_payload($payload) }) {
    for my $result (@{ $self->check_agents( harness => $harness ) }) {
      my ( $failures ) = $self->_problems($result);
      push @lines, map {
        '  '.$self->_harness_label($harness)." agent '"
          .$result->{agent}."': ".$_
      } @{$failures};
    }
  }
  return ( undef, '' ) unless @lines;

  my @shown = @lines > 8 ? @lines[0 .. 7] : @lines;
  push @shown, '  '."\x{2026}".' and '.(@lines - @shown).' more'
    if @lines > @shown;
  return (
    {
      systemMessage => 'briefing: declared skills that will not work '."\x{2014}"
        .' run briefing-doctor for details'."\n".join( "\n", @shown ),
    },
    '',
  );
}

sub process_hook {
  my ( $self, $payload ) = @_;
  my $empty = { output => undef, stderr => '', exit_code => 0 };
  return $empty unless ref $payload eq 'HASH';

  my $context = $self->_for_payload($payload);
  my ( $output, $stderr );
  my $event = $payload->{hook_event_name};
  if ($context->_is_string($event) && $event eq 'SubagentStart') {
    ( $output, $stderr ) = $context->_process_subagent_start($payload);
  }
  elsif ($context->_is_string($event) && $event eq 'SessionStart') {
    ( $output, $stderr ) = $context->_process_session_start($payload);
  }
  elsif (
    $context->_is_string( $payload->{tool_name} )
    && $payload->{tool_name} eq 'Agent'
  ) {
    ( $output, $stderr ) = $context->_process_guard($payload);
  }
  else {
    return $empty;
  }

  return {
    output    => $output,
    stderr    => defined $stderr ? $stderr : '',
    exit_code => 0,
  };
}

=method process_hook

    my $operation = $briefing->process_hook($decoded_payload);

Evaluates one hook payload and returns C<output>, C<stderr> and C<exit_code>
without printing or changing files. A payload C<cwd> is used only for that call.

=cut

sub _installed_marketplace {
  my ( $self ) = @_;
  my $root = $ENV{CLAUDE_PLUGIN_ROOT};
  return unless defined $root && length $root;
  $root = $self->_environment_path($root);
  $root =~ tr{\\}{/};
  my @parts = split m{/+}, $root;
  for my $index (0 .. $#parts) {
    return $parts[$index + 1]
      if $parts[$index] eq 'cache' && $index < $#parts;
  }
  return;
}

sub process_notice {
  my ( $self, $payload ) = @_;
  my $result = { output => undef, stderr => '', exit_code => 0 };
  my $marketplace = $self->_installed_marketplace;
  return $result unless defined $marketplace && $marketplace ne 'getty';

  my $state = $self->filesystem->join_path(
    $self->home,
    '.claude',
    '.briefing-marketplace-notice',
  );
  return $result if $self->filesystem->exists($state);

  my $parent = $self->filesystem->parent($state);
  $self->filesystem->make_path($parent);
  $self->filesystem->spew_utf8( $state, $marketplace."\n" );

  $result->{output} = {
    systemMessage => 'briefing is now also in the shared Getty marketplace, '
      .'alongside the other plugins: /plugin marketplace add Getty/marketplace '
      ."\x{2014}".' then /plugin install briefing@getty. Your install from Getty/briefing '
      .'keeps working and stays maintained, so there is nothing you have to do.',
  };
  return $result;
}

=method process_notice

    my $operation = $briefing->process_notice({});

Evaluates the one-time marketplace notice. Unlike C<process_hook>, this method
may create the notice state file. It still performs no terminal output itself.

=cut

=synopsis

    use App::Briefing;

    my $briefing = App::Briefing->new(
      cwd        => '/work/project',
      home       => '/home/user',
      codex_home => '/home/user/.codex',
    );

    my $agent = $briefing->brief_agent('reviewer', harness => 'claude');
    my $all = $briefing->check_agents(harness => 'both');

=description

C<App::Briefing> is the reusable implementation behind the C<briefing> source
CLI. It discovers Claude Code and Codex agents, parses their briefing
declarations, resolves skills with each harness's precedence and constructs the
hook result. Missing skills never expose partial briefing text.

The object carries an explicit filesystem context. Supplying C<cwd>, C<home>
and C<codex_home> makes library use and tests independent of process-global
working-directory changes.

=cut

1;
