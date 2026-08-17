"""Tests for hooks/briefing-marketplace-notice.

The hook runs as a subprocess with a controlled HOME and CLAUDE_PLUGIN_ROOT so
nothing on the developer's machine leaks into the sandbox.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "briefing-marketplace-notice"


def run_hook(*, fake_home, plugin_root):
    env = {**os.environ, "HOME": str(fake_home)}
    if plugin_root is None:
        env.pop("CLAUDE_PLUGIN_ROOT", None)
    else:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    return subprocess.run(
        ["python3", str(HOOK)],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


class MarketplaceNoticeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def cache_root(self, marketplace):
        return self.home / ".claude/plugins/cache" / marketplace / "briefing/0.1.0"

    def test_notice_shown_for_the_old_marketplace(self):
        proc = run_hook(fake_home=self.home, plugin_root=self.cache_root("briefing"))
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertIn("Getty/claude-code", payload["systemMessage"])
        self.assertIn("briefing@getty", payload["systemMessage"])

    def test_notice_says_the_old_path_keeps_working(self):
        proc = run_hook(fake_home=self.home, plugin_root=self.cache_root("briefing"))
        message = json.loads(proc.stdout)["systemMessage"]
        self.assertIn("keeps working", message)

    def test_silent_on_the_shared_marketplace(self):
        proc = run_hook(fake_home=self.home, plugin_root=self.cache_root("getty"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_silent_without_a_plugin_root(self):
        # --plugin-dir and local checkouts have no marketplace to move away from.
        proc = run_hook(fake_home=self.home, plugin_root=None)
        self.assertEqual(proc.stdout.strip(), "")

    def test_silent_outside_the_plugin_cache(self):
        proc = run_hook(fake_home=self.home, plugin_root=REPO_ROOT)
        self.assertEqual(proc.stdout.strip(), "")

    def test_shown_only_once(self):
        first = run_hook(fake_home=self.home, plugin_root=self.cache_root("briefing"))
        self.assertNotEqual(first.stdout.strip(), "")
        second = run_hook(fake_home=self.home, plugin_root=self.cache_root("briefing"))
        self.assertEqual(second.stdout.strip(), "")

    def test_unwritable_state_still_notifies(self):
        # Saying it every session beats never saying it.
        state_dir = self.home / ".claude"
        state_dir.mkdir(parents=True)
        state_dir.chmod(0o500)
        try:
            proc = run_hook(fake_home=self.home, plugin_root=self.cache_root("briefing"))
            self.assertEqual(proc.returncode, 0)
            self.assertIn("Getty/claude-code", json.loads(proc.stdout)["systemMessage"])
        finally:
            state_dir.chmod(0o700)

    def test_never_writes_to_stderr(self):
        proc = run_hook(fake_home=self.home, plugin_root=self.cache_root("briefing"))
        self.assertEqual(proc.stderr, "")


if __name__ == "__main__":
    unittest.main()
