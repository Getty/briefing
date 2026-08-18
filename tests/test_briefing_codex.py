"""End-to-end tests for the Codex side of hooks/briefing-preload.

Codex spawns subagents through a `SubagentStart` hook event rather than a
`PreToolUse` on an Agent tool, declares agents as TOML, and takes injected
context via `additionalContext` instead of a rewritten prompt. Same hook
script, different world — these tests drive it the way Codex would.

The hook runs as a subprocess with a controlled HOME and cwd so nothing on
the developer's machine leaks in.
"""

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "hooks" / "briefing-preload"


def run_hook(payload, *, fake_home):
    env = {**os.environ, "HOME": str(fake_home)}
    proc = subprocess.run(
        ["python3", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return proc


def write(path: Path, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")


class CodexHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cwd = self.root / "project"
        self.home = self.root / "home"
        self.cwd.mkdir()
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _payload(self, **overrides):
        payload = {
            "hook_event_name": "SubagentStart",
            "agent_type": "demo",
            "agent_id": "agent_123",
            "turn_id": "turn_123",
            "cwd": str(self.cwd),
        }
        payload.update(overrides)
        return payload

    def _agent(self, body):
        write(self.cwd / ".codex/agents/demo.toml", body)

    def _skill(self, name, body="Skill body here.\n", root=None):
        base = root if root is not None else self.cwd / ".agents/skills"
        write(
            base / name / "SKILL.md",
            "---\nname: %s\ndescription: d\n---\n\n%s" % (name, body),
        )

    def _out(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout, "hook produced no stdout")
        return json.loads(proc.stdout)

    # --- the core path ---------------------------------------------------

    def test_declared_skill_is_injected_as_additional_context(self):
        self._agent("""
            name = "demo"
            description = "x"
            developer_instructions = "do things"

            [briefing]
            skills = ["demo-skill"]
        """)
        self._skill("demo-skill", "The body of the demo skill.\n")

        out = self._out(run_hook(self._payload(), fake_home=self.home))

        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "SubagentStart")
        self.assertIn("The body of the demo skill.", hso["additionalContext"])

    # --- resolution -------------------------------------------------------

    def test_skill_resolves_from_user_agents_root(self):
        self._agent("""
            name = "demo"

            [briefing]
            skills = ["user-skill"]
        """)
        self._skill("user-skill", "From the user root.\n", root=self.home / ".agents/skills")

        out = self._out(run_hook(self._payload(), fake_home=self.home))

        self.assertIn("From the user root.", out["hookSpecificOutput"]["additionalContext"])

    def test_project_root_wins_over_user_root(self):
        self._agent("""
            name = "demo"

            [briefing]
            skills = ["dup"]
        """)
        self._skill("dup", "PROJECT COPY\n")
        self._skill("dup", "USER COPY\n", root=self.home / ".agents/skills")

        ctx = self._out(run_hook(self._payload(), fake_home=self.home))["hookSpecificOutput"]["additionalContext"]

        self.assertIn("PROJECT COPY", ctx)
        self.assertNotIn("USER COPY", ctx)

    def test_plugin_namespaced_skill_resolves_from_plugin_cache(self):
        # Codex addresses plugin skills as `plugin:skill`, same syntax as
        # Claude Code, and installs them under a versioned cache path.
        self._agent("""
            name = "demo"

            [briefing]
            skills = ["someplugin:tool"]
        """)
        write(
            self.home / ".codex/plugins/cache/mp/someplugin/1.2.3/skills/tool/SKILL.md",
            "---\nname: tool\ndescription: d\n---\n\nPlugin skill body.\n",
        )

        out = self._out(run_hook(self._payload(), fake_home=self.home))

        self.assertIn("Plugin skill body.", out["hookSpecificOutput"]["additionalContext"])

    # --- the failure path -------------------------------------------------

    def test_missing_skill_yields_abort_instruction_not_content(self):
        # Codex cannot deny a spawn, so the nearest thing to Claude Code's
        # hard fail is an agent that starts and refuses to work.
        self._agent("""
            name = "demo"

            [briefing]
            skills = ["gone"]
        """)

        out = self._out(run_hook(self._payload(), fake_home=self.home))
        ctx = out["hookSpecificOutput"]["additionalContext"]

        self.assertIn("gone", ctx)
        self.assertIn("NOT", ctx)
        self.assertIn("briefing", out["systemMessage"])
        self.assertIn("gone", out["systemMessage"])

    def test_one_missing_skill_aborts_even_when_others_resolve(self):
        self._agent("""
            name = "demo"

            [briefing]
            skills = ["present", "absent"]
        """)
        self._skill("present", "SHOULD NOT BE USED AS A BRIEFING\n")

        ctx = self._out(run_hook(self._payload(), fake_home=self.home))["hookSpecificOutput"]["additionalContext"]

        self.assertIn("absent", ctx)
        self.assertNotIn("SHOULD NOT BE USED AS A BRIEFING", ctx)

    # --- no-op cases ------------------------------------------------------

    def test_other_hook_event_is_noop(self):
        proc = run_hook(
            {"hook_event_name": "SubagentStop", "agent_type": "demo", "cwd": str(self.cwd)},
            fake_home=self.home,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_unknown_agent_is_noop(self):
        proc = run_hook(self._payload(agent_type="nosuch"), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_agent_without_briefing_table_is_noop(self):
        self._agent("""
            name = "demo"
            description = "x"
            developer_instructions = "do things"
        """)
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_codex_own_skills_config_is_not_read_as_a_briefing(self):
        # `[[skills.config]]` is Codex's own enable/disable mechanism. It
        # means "visible to the agent", not "preloaded", and briefing must
        # not quietly reinterpret it.
        self._agent("""
            name = "demo"

            [[skills.config]]
            path = "/somewhere/tool/SKILL.md"
            enabled = true
        """)
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    # --- the tomllib-less interpreter (CI still runs Python 3.10) ---------

    def test_declaration_is_parsed_without_tomllib(self):
        shim = self.root / "notoml"
        write(shim / "tomllib.py", "raise ImportError('blocked for test')\n")
        self._agent("""
            name = "demo"

            [briefing]
            skills = [
              "multi-line",
              'single-quoted',
            ]

            [other]
            skills = ["must-not-be-read"]
        """)
        self._skill("multi-line", "MULTI OK\n")
        self._skill("single-quoted", "SINGLE OK\n")

        env = {**os.environ, "HOME": str(self.home), "PYTHONPATH": str(shim)}
        proc = subprocess.run(
            ["python3", str(HOOK)],
            input=json.dumps(self._payload()),
            capture_output=True, text=True, env=env, timeout=10,
        )

        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("MULTI OK", ctx)
        self.assertIn("SINGLE OK", ctx)
        self.assertNotIn("must-not-be-read", ctx)
