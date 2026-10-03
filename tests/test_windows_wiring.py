"""How the hooks reach Windows.

Claude Code on Windows cannot start a script without extension, and has no
switch to run a hook on some platforms only. An exec-form entry (one with
`args`) whose command has no extension is started as `<command>.exe` there:
winlaunch, which runs what the `# winlaunch: run` line of the script next to
it names. Linux and macOS start the script itself. Codex ignores `args` and
runs the command text through its shell, as before.
"""

import json
import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFIX = "${CLAUDE_PLUGIN_ROOT}/"


def entries():
    with open(REPO_ROOT / "hooks" / "hooks.json", encoding="utf-8") as f:
        doc = json.load(f)
    for event, groups in doc["hooks"].items():
        for group in groups:
            for hook in group["hooks"]:
                yield event, hook


class WindowsWiring(unittest.TestCase):
    def test_every_entry_is_exec_form(self):
        for event, hook in entries():
            with self.subTest(event=event, command=hook["command"]):
                self.assertIn("args", hook)
                self.assertTrue(hook["command"].startswith(PREFIX))

    def test_every_command_has_a_winlaunch_exe_that_runs_it(self):
        commands = {hook["command"][len(PREFIX):] for _, hook in entries()}
        commands.add("bin/briefing-doctor")
        for rel in sorted(commands):
            with self.subTest(command=rel):
                self.assertTrue((REPO_ROOT / (rel + ".exe")).is_file())
                text = (REPO_ROOT / rel).read_text(encoding="utf-8")
                head = text.splitlines()[:64]
                self.assertTrue(any(l.startswith("# winlaunch: run python ") for l in head))

    def test_doctor_is_a_script_not_a_symlink(self):
        # A symlink becomes a text file holding its target in a Windows
        # checkout without developer mode.
        self.assertFalse(os.path.islink(REPO_ROOT / "bin" / "briefing-doctor"))


if __name__ == "__main__":
    unittest.main()
