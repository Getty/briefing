"""Contract of the sh starter bin/briefing.

The starter runs a cached release binary (verified against the checksum pinned in
bin/briefing-binaries.sha256), downloads it only for `hook session-start`, and otherwise
falls back to the Python hook, so a spawn is never unbriefed. Every test runs a copy of the
plugin with an isolated HOME, CLAUDE_CONFIG_DIR and cwd, a fake binary and a file:// download.

Skipped on Windows (the starter is POSIX sh; Windows starts bin/briefing.exe) and wherever sh,
a checksum tool or a pinned platform is missing; download tests also need curl.
"""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.2.3"
MARKER = "STARTER-MARKER-X"
NOW = "1700000000"

SKIP_REASON = None
OS_NAME = ARCH = None
if sys.platform.startswith("win"):
    SKIP_REASON = "skipped on Windows: bin/briefing is a POSIX sh starter"
else:
    OS_NAME = {"Linux": "linux", "Darwin": "macos"}.get(platform.system())
    ARCH = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine().lower())
    if shutil.which("sh") is None:
        SKIP_REASON = "skipped: no sh on PATH"
    elif OS_NAME is None or ARCH is None:
        SKIP_REASON = "skipped: no binary is pinned for %s %s" % (platform.system(), platform.machine())
    elif shutil.which("sha256sum") is None and shutil.which("shasum") is None:
        SKIP_REASON = "skipped: neither sha256sum nor shasum is available"
    elif shutil.which("python3") is None:
        SKIP_REASON = "skipped: no python3 on PATH for the fallback hook"

HAVE_CURL = shutil.which("curl") is not None
FAKE_BINARY = b'#!/bin/sh\necho "FAKE $PAR_GLOBAL_TEMP|$*"\n'
EVIL_BINARY = b"#!/bin/sh\necho EVIL-RAN\n"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@unittest.skipIf(SKIP_REASON is not None, SKIP_REASON or "")
class StarterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="briefing-starter-"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.plugin = self.tmp / "plugin"
        self.plugin.mkdir()
        for name in ("bin", "hooks", "lib", "script"):
            shutil.copytree(str(ROOT / name), str(self.plugin / name))
        try:  # start from the "nothing pinned" state, whatever the checkout holds
            (self.plugin / "bin" / "briefing-binaries.sha256").unlink()
        except OSError:
            pass
        self.starter = self.plugin / "bin" / "briefing"
        self.home = self.tmp / "home"
        self.config = self.tmp / "cfg"
        self.proj = self.home / "proj"
        (self.home / ".claude" / "skills" / "s").mkdir(parents=True)
        (self.home / ".claude" / "skills" / "s" / "SKILL.md").write_text(MARKER + "\n")
        (self.proj / ".claude" / "agents").mkdir(parents=True)
        (self.proj / ".claude" / "agents" / "demo.md").write_text(
            "---\nname: demo\nbriefing:\n  skills:\n    - s\n---\nbody\n")
        self.payload = json.dumps({
            "hook_event_name": "SubagentStart",
            "agent_type": "demo",
            "agent_id": "a1",
            "cwd": str(self.proj),
            "transcript_path": str(self.home / ".claude" / "projects" / "p" / "s.jsonl"),
        })
        self.asset = "briefing-%s-%s-%s" % (VERSION, OS_NAME, ARCH)
        self.cache_dir = self.config / "briefing" / "bin" / VERSION
        self.serve(FAKE_BINARY)

    def serve(self, data, name="srv"):
        """Serve `data` as the release asset at file://<tmp>/<name>/<VERSION>; return the URL."""
        directory = self.tmp / name / VERSION
        directory.mkdir(parents=True, exist_ok=True)
        (directory / self.asset).write_bytes(data)
        return "file://%s" % directory

    def pin(self, data=FAKE_BINARY):
        (self.plugin / "bin" / "briefing-binaries.sha256").write_text(
            "%s  %s\n" % (sha256(data), self.asset))
        return sha256(data)

    def run_starter(self, *args, url=None, now=None, stdin=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("BRIEFING_")}
        env.update(HOME=str(self.home), CLAUDE_CONFIG_DIR=str(self.config))
        env.pop("PAR_GLOBAL_TEMP", None)
        if url is not None:
            env["BRIEFING_BINARY_BASE_URL"] = url
        if now is not None:
            env["BRIEFING_STARTER_NOW"] = now
        return subprocess.run(
            ["sh", str(self.starter)] + list(args),
            input=self.payload if stdin is None else stdin,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
            cwd=str(self.proj), env=env, timeout=60)

    def files_left(self):
        if not self.config.exists():
            return []
        return sorted(str(p.relative_to(self.config)) for p in self.config.rglob("*") if p.is_file())

    def assert_python_briefed(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SubagentStart")
        self.assertIn(MARKER, context)

    # --- fallback

    def test_no_pin_falls_back_to_python_hook_which_briefs(self):
        result = self.run_starter("hook", "subagent-start")
        self.assert_python_briefed(result)

    def test_empty_pin_downloads_nothing_and_still_briefs(self):
        (self.plugin / "bin" / "briefing-binaries.sha256").write_text("")
        result = self.run_starter("hook", "session-start", url=self.serve(FAKE_BINARY))
        self.assertFalse((self.config / "briefing").exists(), self.files_left())
        self.assertNotIn("FAKE", result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pin_for_another_platform_downloads_nothing(self):
        other = "briefing-%s-freebsd-riscv" % VERSION
        (self.plugin / "bin" / "briefing-binaries.sha256").write_text(
            "%s  %s\n" % (sha256(FAKE_BINARY), other))
        self.run_starter("hook", "session-start", url=self.serve(FAKE_BINARY))
        self.assertFalse((self.config / "briefing").exists(), self.files_left())
        self.assert_python_briefed(self.run_starter("hook", "subagent-start"))

    # --- spawn hooks never download

    def test_spawn_hooks_never_download_and_still_brief(self):
        self.pin()
        url = self.serve(FAKE_BINARY)
        for event in ("subagent-start", "pre-tool-use"):
            with self.subTest(event=event):
                result = self.run_starter("hook", event, url=url)
                self.assertFalse((self.config / "briefing").exists(), self.files_left())
                self.assertNotIn("FAKE", result.stdout)
                self.assertEqual(result.returncode, 0, result.stderr)
                if event == "subagent-start":
                    self.assert_python_briefed(result)

    # --- session-start provisions

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_session_start_downloads_verifies_caches_and_runs_binary(self):
        digest = self.pin()
        result = self.run_starter("hook", "session-start", url=self.serve(FAKE_BINARY), now=NOW)
        cached = self.cache_dir / ("%s-%s" % (self.asset, digest))
        self.assertTrue(cached.is_file(), self.files_left())
        self.assertTrue(os.access(str(cached), os.X_OK))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"^FAKE .*%s\.par\|hook session-start" % cached.name)
        self.assertEqual(self.files_left(), [str(cached.relative_to(self.config))])

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_cache_hit_starts_binary_without_network(self):
        self.pin()
        self.run_starter("hook", "session-start", url=self.serve(FAKE_BINARY), now=NOW)
        result = self.run_starter("hook", "subagent-start", url="file:///nonexistent")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("|hook subagent-start", result.stdout)
        self.assertNotIn(MARKER, result.stdout)

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_tampered_cache_is_not_run_and_spawn_still_briefed(self):
        digest = self.pin()
        self.run_starter("hook", "session-start", url=self.serve(FAKE_BINARY), now=NOW)
        cached = self.cache_dir / ("%s-%s" % (self.asset, digest))
        with open(str(cached), "ab") as handle:
            handle.write(b"echo TAMPERED\n")
        result = self.run_starter("hook", "subagent-start", url="file:///nonexistent")
        self.assertNotIn("FAKE", result.stdout)
        self.assertNotIn("TAMPERED", result.stdout)
        self.assert_python_briefed(result)

    # --- wrong checksum

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_wrong_checksum_is_neither_used_nor_executed_nor_kept(self):
        self.pin()  # pins FAKE_BINARY; the server delivers something else
        url = self.serve(EVIL_BINARY, name="bad")
        result = self.run_starter("hook", "session-start", url=url, now=NOW)
        self.assertNotIn("EVIL-RAN", result.stdout + result.stderr)
        self.assertNotIn("FAKE", result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        # Only the backoff marker may remain: no binary, no temp download, no unpacked dir.
        leftovers = [f for f in self.files_left() if not f.endswith(".failed-at")]
        self.assertEqual(leftovers, [])
        # And the Python hook still briefs on the next spawn.
        self.assert_python_briefed(self.run_starter("hook", "subagent-start", url=url))

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_failed_session_start_backs_off_for_fifteen_minutes(self):
        self.pin()
        bad = self.serve(EVIL_BINARY, name="bad")
        good = self.serve(FAKE_BINARY)
        self.run_starter("hook", "session-start", url=bad, now=NOW)
        marker = self.cache_dir / ("." + self.asset + ".failed-at")
        self.assertTrue(marker.is_file(), self.files_left())
        self.assertEqual(marker.read_text().strip(), NOW)
        soon = self.run_starter("hook", "session-start", url=good, now=str(int(NOW) + 899))
        self.assertNotIn("FAKE", soon.stdout, "retried inside the backoff window")
        later = self.run_starter("hook", "session-start", url=good, now=str(int(NOW) + 900))
        self.assertIn("|hook session-start", later.stdout)
        self.assertFalse(marker.exists(), "a successful provision clears the backoff marker")

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_unreachable_download_leaves_no_binary_and_still_briefs(self):
        self.pin()
        result = self.run_starter("hook", "session-start", url="file:///nonexistent", now=NOW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([f for f in self.files_left() if not f.endswith(".failed-at")], [])
        self.assert_python_briefed(self.run_starter("hook", "subagent-start"))


    # --- explicit non-provisioning commands

    def _fake_source(self):
        """Fake `curl`/`wget` on PATH that record any call: nothing may read the source."""
        bindir = self.tmp / "fakebin"
        bindir.mkdir(exist_ok=True)
        log = self.tmp / "fetch.log"
        for tool in ("curl", "wget"):
            script = bindir / tool
            script.write_text('#!/bin/sh\necho "$0 $*" >>"%s"\nexit 1\n' % log)
            script.chmod(0o755)
        return bindir, log

    def test_version_and_doctor_never_download(self):
        self.pin()
        url = self.serve(FAKE_BINARY)
        bindir, log = self._fake_source()
        old_path = os.environ["PATH"]
        os.environ["PATH"] = "%s%s%s" % (bindir, os.pathsep, old_path)
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        for args in (("--version",), ("doctor",), ("doctor", "--tsv")):
            with self.subTest(args=args):
                result = self.run_starter(*args, url=url, now=NOW,
                                          stdin="")
                self.assertNotIn("FAKE", result.stdout)
                self.assertFalse((self.config / "briefing").exists(), self.files_left())
                self.assertFalse(log.exists(), "a downloader was started: " + (
                    log.read_text() if log.exists() else ""))

    @unittest.skipUnless(HAVE_CURL, "skipped: curl is not available for the file:// download")
    def test_download_url_has_no_v_before_the_version(self):
        self.pin()
        # Serve under <base>/<version>/<asset> only: a "v<version>" tag finds nothing.
        base = "file://%s/" % (self.tmp / "tags")
        directory = self.tmp / "tags" / VERSION
        directory.mkdir(parents=True)
        (directory / self.asset).write_bytes(FAKE_BINARY)
        text = self.starter.read_text()
        self.assertIn("release_tag_prefix=\n", text)
        # Rewrite only the prefix so the starter composes the URL itself.
        patched = text.replace("release_url_prefix=https://github.com/Getty/briefing/releases/download/",
                               "release_url_prefix=" + base)
        self.starter.write_text(patched)
        # The CLI command that provisions: a SessionStart hook, using the default URL.
        result = self.run_starter("hook", "session-start", now=NOW)
        cached = self.cache_dir / ("%s-%s" % (self.asset, sha256(FAKE_BINARY)))
        self.assertTrue(cached.is_file(), "URL did not resolve to <base>/<version>/<asset>: "
                        + repr(self.files_left()))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
