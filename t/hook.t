use strict;
use warnings;
use Test::More;
use JSON::PP ();
use File::Spec;
use FindBin;

my $file = File::Spec->catfile($FindBin::Bin, '..', 'hooks', 'hooks.json');
open my $fh, '<:raw', $file or die "$file: $!";
my $config = JSON::PP->new->decode(do { local $/; <$fh> });

is_deeply([sort keys %{$config->{hooks}}], ['SessionStart'], 'only a SessionStart hook');
my @hooks = map { @{$_->{hooks}} } @{$config->{hooks}{SessionStart}};
is(scalar @hooks, 1, 'exactly one command');
is($hooks[0]{type}, 'command', 'a command hook');
unlike($hooks[0]{command}, qr/CLAUDE_PLUGIN_ROOT|python|curl/, 'no plugin files or external tools');

my $out = `$hooks[0]{command}`;
is($? >> 8, 0, 'hook exits 0');
my $json = eval { JSON::PP->new->decode($out) };
ok($json, 'hook prints JSON') or diag $out;
is_deeply([sort keys %$json], ['systemMessage'], 'only systemMessage');
my $m = $json->{systemMessage};
like($m, qr/^briefing is obsolete: Claude Code now preloads agent skills natively\./, 'message start');
like($m, qr/top-level `skills:` list/, 'names the replacement');
like($m, qr{/plugin uninstall briefing}, 'names the uninstall');
like($m, qr{https://code\.claude\.com/docs/en/sub-agents#preload-skills-into-subagents}, 'carries the URL');

done_testing;
