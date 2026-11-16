#!/usr/bin/env bash
# The extra pp arguments of the briefing binary, one per line on STDOUT: binary_pp_args of
# the [@Author::GETTY] bundle (dist.ini). Run from the dist root with the perl that packs;
# problems go to STDERR and end the run with exit 1, which fails the build.
#   scripts/binary-pp-args.sh
#
# The bundle runs pp itself (locally after `dzil build`, per platform in its dzil-binary
# workflow) as  PAR_VERBATIM=1 pp -o OUT -I lib <these lines> script/briefing. This adds what
# pp's static scan cannot see: the module set computed by scripts/loaded-modules.pl.
# briefing never talks to a network, so no TLS module is packed; binary-verify.sh rejects one.
#
# pp exits 0 on a binary that only dies at run time; scripts/binary-verify.sh and
# scripts/binary-smoke.sh are what prove a build.
set -euo pipefail

[ -f script/briefing ] && [ -f lib/App/Briefing.pm ] || { echo "ERROR: run from the dist root" >&2; exit 1; }
perl -Ilib -MMoo -MPath::Tiny -MJSON::MaybeXS -MTOML::Tiny::Parser -Mnamespace::clean -e1 \
  || { echo "ERROR: runtime dependencies missing (cpanm --installdeps .)" >&2; exit 1; }

loaded=$(perl -Ilib scripts/loaded-modules.pl | tr -d '\r') \
  || { echo "ERROR: scripts/loaded-modules.pl failed" >&2; exit 1; }
n=$(printf '%s\n' "$loaded" | wc -l | tr -d ' ')
[ "$n" -gt 30 ] || { echo "ERROR: loaded set suspiciously small ($n modules)" >&2; exit 1; }
for m in App::Briefing App::Briefing::CLI App::Briefing::Team Moo Path::Tiny TOML::Tiny::Parser; do
  printf '%s\n' "$loaded" | grep -qx "$m" || { echo "ERROR: the module list lacks $m" >&2; exit 1; }
done
# Diagnosis only, never fatal, nothing on STDOUT: on Windows (or with DIAG=1) report which module
# makes Module::ScanDeps (what pp uses) pull in Net::SSLeay / IO::Socket::SSL, as a chain
# down to one of our own modules or script/briefing. Output: STDERR lines starting "DIAG-SSL".
case "$(perl -e 'print $^O')" in MSWin32|msys|cygwin) diag=1 ;; *) diag=${DIAG:-} ;; esac
if [ -n "$diag" ]; then
  LOADED="$loaded" perl -Ilib -e '
    use strict; use warnings;
    my $ok = eval { require Module::ScanDeps; 1 };
    unless ($ok) { print STDERR "DIAG-SSL: Module::ScanDeps unavailable\n"; exit 0 }
    my @mods = grep { length } map { s/\r//gr } split /\n/, $ENV{LOADED};
    my %root = ("script/briefing" => 1);
    my @files = ("script/briefing");
    for my $m (@mods) {
      (my $rel = "$m.pm") =~ s{::}{/}g;
      my ($f) = grep { -f } map { "$_/$rel" } @INC;
      next unless $f;
      $root{$rel} = 1; push @files, $f;
    }
    my $map = Module::ScanDeps::scan_deps(files => \@files, recurse => 1);
    my $found = 0;
    for my $t ("Net/SSLeay.pm", "IO/Socket/SSL.pm") {
      my $e = $map->{$t} or next;
      $found = 1;
      my %seen = ($t => 1); my @q = ([$t]);
      my @out;
      while (my $path = shift @q) {
        my $cur = $path->[-1];
        my $by = $map->{$cur} ? $map->{$cur}{used_by} : [];
        if ($root{$cur} || !($by && @$by)) { push @out, join " <- ", @$path; next }
        for my $u (@$by) { next if $seen{$u}++; push @q, [@$path, $u] }
      }
      print STDERR "DIAG-SSL: $t used_by: ", join(", ", @{ $e->{used_by} || [] }), "\n";
      print STDERR "DIAG-SSL: chain: $_\n" for @out;
    }
    print STDERR "DIAG-SSL: Net::SSLeay/IO::Socket::SSL not reached by ScanDeps\n" unless $found;
  ' 1>&2 || echo "DIAG-SSL: diagnosis failed (ignored)" >&2
fi
# One argument per line, never word-split (the bundle's rule for binary_pp_args).
printf '%s\n' "$loaded" | while IFS= read -r m; do printf -- '-M\n%s\n' "$m"; done
