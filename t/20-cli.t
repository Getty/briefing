#!/usr/bin/env perl

use strict;
use warnings;

use FindBin;
use Test::More;

use lib $FindBin::Bin.'/../lib';
use lib $FindBin::Bin.'/lib';

use App::Briefing;
use App::Briefing::CLI;
use BriefingTest qw(
  claude_agent
  claude_skill
  decode_json_output
  hook_payload
  repo_root
  run_cli
  sandbox
);
use JSON::MaybeXS qw( encode_json );
use Path::Tiny qw( path );

sub briefing_argv {
  return (
    $^X,
    '-I'.path(repo_root(), 'lib')->stringify,
    path(repo_root(), 'script', 'briefing')->stringify,
    @_,
  );
}

can_ok('App::Briefing::CLI', 'run');
ok(
  path(repo_root(), 't', '00-load.t')->is_file,
  'repo_root resolves the distribution root',
);

my $version_box = sandbox();
my $version = run_cli(
  sandbox => $version_box,
  argv    => [briefing_argv('--version')],
);
is($version->{exit_code}, 0, 'briefing --version exits zero');
is($version->{stderr}, '', 'briefing --version is quiet on stderr');
like(
  $version->{stdout},
  qr/\Q$App::Briefing::VERSION\E/,
  'briefing --version reports the loaded package version',
);

my $hook_box = sandbox();
claude_agent($hook_box, 'demo', 'cli-skill');
claude_skill($hook_box, 'cli-skill', "CLI SKILL BODY\n");
my $hook = run_cli(
  sandbox => $hook_box,
  argv    => [briefing_argv('hook')],
  input   => encode_json(hook_payload($hook_box)),
);
is($hook->{exit_code}, 0, 'briefing hook exits zero for a valid hook payload');
is($hook->{stderr}, '', 'briefing hook does not warn for a small complete briefing');
like(
  decode_json_output($hook->{stdout})->{hookSpecificOutput}{additionalContext},
  qr/CLI SKILL BODY/,
  'briefing hook emits the public hook JSON contract',
);

my $doctor_box = sandbox();
claude_agent($doctor_box, 'reviewer', 'missing-skill');
my $doctor = run_cli(
  sandbox => $doctor_box,
  argv    => [briefing_argv('doctor', '--cwd', $doctor_box->{cwd})],
);
is($doctor->{exit_code}, 1, 'briefing doctor exits one for a missing skill');
like($doctor->{stdout}, qr/reviewer/, 'briefing doctor identifies the broken agent');
like($doctor->{stdout}, qr/missing-skill/, 'briefing doctor identifies the missing skill');

my $notice_box = sandbox();
my $old_plugin_root = path(
  $notice_box->{home}, '.claude', 'plugins', 'cache', 'briefing', 'briefing', '0.1.0',
)->stringify;
my $notice = run_cli(
  sandbox => $notice_box,
  argv    => [briefing_argv('notice')],
  env     => { CLAUDE_PLUGIN_ROOT => $old_plugin_root },
);
is($notice->{exit_code}, 0, 'briefing notice exits zero');
like(
  decode_json_output($notice->{stdout})->{systemMessage},
  qr/Getty\/marketplace/,
  'briefing notice retains the marketplace notice contract',
);
my $notice_again = run_cli(
  sandbox => $notice_box,
  argv    => [briefing_argv('notice')],
  env     => { CLAUDE_PLUGIN_ROOT => $old_plugin_root },
);
is($notice_again->{stdout}, '', 'briefing notice records that it has already been shown');

done_testing;
