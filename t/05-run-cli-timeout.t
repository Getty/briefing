#!/usr/bin/env perl

use strict;
use warnings;

use FindBin;
use Test::More;

use lib $FindBin::Bin.'/lib';

use BriefingTest qw( run_cli sandbox );

my $box = sandbox();

my $echo = run_cli(
  sandbox => $box,
  argv    => [$^X, '-e', 'local $/; print scalar <STDIN>; print STDERR "e"; exit 3'],
  input   => "hello\n",
);
is_deeply(
  $echo,
  { stdout => "hello\n", stderr => 'e', exit_code => 3 },
  'run_cli feeds stdin from a file and captures both streams and the exit code',
);

my $started = time;
my $ok = eval {
  run_cli(
    sandbox => $box,
    argv    => [$^X, '-e', 'sleep 300'],
    timeout => 2,
  );
  1;
};
my $elapsed = time - $started;
ok(!$ok, 'run_cli dies when the child outlives its timeout');
like($@, qr/timed out after 2s/, 'the failure names the timeout');
cmp_ok($elapsed, '<', 30, 'the sleeping child was killed, not waited for');

done_testing;
