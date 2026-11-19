"""TEMPORARY k14 diagnostic: remove before the branch is finished.

An instrument, not a regression test. On native Windows it runs one Perl probe
and one Python control child with a non-ANSI HOME and a non-ANSI variable name,
prints what each of them sees between "K14-DIAG BEGIN" and "K14-DIAG END" on
stderr, and then fails on purpose so the report also lands in the FAIL section
of the CI log. It separates three hypotheses for card k14:
H1 the process's wide environment no longer holds the value when Perl code
runs, H2 the wide read is right and the failure is downstream (join_path,
is_dir/is_file), H3 the U+FFFF-prefixed ExpandEnvironmentStrings round trip
behaves differently than assumed.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROBE = r'''
use strict;
use warnings;
use JSON::PP;

my %out;
my @order;

sub desc {
  my ($v, $raw) = @_;
  return { defined => JSON::PP::false } unless defined $v;
  if (ref $v) {
    return { defined => JSON::PP::true, ref => ref($v),
             value => eval { JSON::PP->new->canonical->allow_nonref->allow_blessed->convert_blessed->decode(
               JSON::PP->new->canonical->allow_blessed->convert_blessed->ascii->encode($v)) } };
  }
  my $d = {
    defined => JSON::PP::true,
    utf8    => (utf8::is_utf8($v) ? JSON::PP::true : JSON::PP::false),
    cps     => join(' ', map { sprintf 'U+%04X', ord } split //, $v),
  };
  if ($raw) { $d->{bytes_hex} = do { use bytes; unpack 'H*', $v }; }
  return $d;
}

sub step {
  my ($name, $code) = @_;
  push @order, $name;
  my $r = eval { $code->() };
  $out{$name} = $@ ? { error => "$@" } : $r;
}

step(win32_load => sub { require Win32; 1 });
my $win32 = !(ref $out{win32_load} eq 'HASH');
$out{win32_loaded} = $win32 ? JSON::PP::true : JSON::PP::false;
push @order, 'win32_loaded';

step(os => sub { $^O });
step(perl => sub { "$]" });
step(win32_version => sub { $Win32::VERSION });
step(acp => sub { Win32::GetACP() });
step(oemcp => sub { Win32::GetOEMCP() });

step(env_home => sub { desc($ENV{HOME}, 1) });
step(env_probe => sub { desc($ENV{K14_PROBE}, 1) });
step(env_names_k14 => sub { [ map { desc($_, 1) } sort grep { /^K14_/ } keys %ENV ] });

my $expand = sub { my $s = shift; sub { desc(Win32::ExpandEnvironmentStrings($s), 1) } };
step(expand_home            => $expand->('%HOME%'));
step(expand_ffff_home       => $expand->("\x{FFFF}%HOME%"));
step(expand_literal         => $expand->("\x{6280}"));
step(expand_probe           => $expand->('%K14_PROBE%'));
step(expand_name_wide       => $expand->("%K14_\x{6280}%"));
step(expand_name_ansi       => $expand->('%K14_?%'));

my ($fs, $briefing, $home);
step(load_app_briefing => sub {
  require App::Briefing;
  require App::Briefing::Filesystem;
  require App::Briefing::CLI;
  $fs = App::Briefing::Filesystem->new;
  1;
});
step(environment_value_home => sub { desc($fs->environment_value('HOME'), 0) });
step(briefing_home => sub { $briefing = App::Briefing->new; $home = $briefing->home; desc($home, 0) });
step(briefing_home_is_dir => sub { $fs->is_dir($home) ? 1 : 0 });
my $skill;
step(skill_path => sub { $skill = $fs->join_path($home, '.claude', 'skills', 'user-skill', 'SKILL.md'); desc($skill, 0) });
step(skill_path_is_file => sub { $fs->is_file($skill) ? 1 : 0 });
step(skill_path_is_readable => sub { $fs->is_readable_file($skill) ? 1 : 0 });
step(resolve_user_skill => sub { desc(scalar $briefing->_resolve_skill_claude('user-skill'), 0) });
step(expand_ffff_home_after_load => $expand->("\x{FFFF}%HOME%"));

$out{order} = \@order;
print JSON::PP->new->canonical->ascii->encode(\%out), "\n";
'''

CONTROL = r'''
import os
print(ascii(os.environ["HOME"]))
print(ascii(os.environ["K14_PROBE"]))
print("K14_技" in os.environ)
'''

# ignore_cleanup_errors exists from Python 3.10.
TMP_OPTIONS = {"ignore_cleanup_errors": True} if sys.version_info >= (3, 10) else {}


def perl_executable():
    raw = os.environ.get("BRIEFING_TEST_CLI")
    if raw is not None:
        argv = json.loads(raw)
        if isinstance(argv, list) and argv and isinstance(argv[0], str) and argv[0]:
            return argv[0]
    return shutil.which("perl")


@unittest.skipUnless(os.name == "nt", "TEMPORARY k14 diagnostic: native Windows only")
class K14Diagnostic(unittest.TestCase):
    def test_k14_report(self):
        perl = perl_executable()
        if not perl:
            self.skipTest("no perl: BRIEFING_TEST_CLI unset and none on PATH")

        with tempfile.TemporaryDirectory(**TMP_OPTIONS) as tmp:
            root = Path(tmp)
            home = root / "home-ä-技能"
            skill_dir = home / ".claude" / "skills" / "user-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: user-skill\ndescription: k14 probe\n---\nbody\n",
                encoding="utf-8")
            probe = root / "k14_probe.pl"
            probe.write_text(PROBE, encoding="ascii")

            env = dict(os.environ)
            env["HOME"] = str(home)
            env["K14_PROBE"] = "probe-ä-技能"
            env["K14_技"] = "name-probe"

            done = subprocess.run([perl, str(probe)], env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out = done.stdout.decode("ascii", errors="replace")
            err = done.stderr.decode("utf-8", errors="replace")
            try:
                data = json.loads(out)
                probe_text = json.dumps(data, indent=2, sort_keys=True)
            except ValueError:
                data = None
                probe_text = "UNPARSEABLE STDOUT: " + out

            control = subprocess.run([sys.executable, "-I", "-c", CONTROL], env=env,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
            control_text = control.stdout.decode("utf-8", errors="replace")

            report = "\n".join([
                "perl: %s" % perl,
                "probe exit code: %s" % done.returncode,
                "probe json:", probe_text,
                "probe stderr:", err,
                "python control exit code: %s" % control.returncode,
                "python control (ascii HOME, ascii K14_PROBE, name present):", control_text,
            ])
            if data is not None and data.get("win32_loaded") is False:
                self.skipTest("Win32 cannot be loaded by the probe: %s"
                              % json.dumps(data.get("win32_load")))

            sys.stderr.write("K14-DIAG BEGIN\n%s\nK14-DIAG END\n" % report)
            sys.stderr.flush()
            self.fail("K14-DIAG (temporary, deliberate): " + report)


if __name__ == "__main__":
    unittest.main()
