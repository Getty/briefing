"""End-to-end tests for hooks/briefing-preload.

The hook is invoked as a subprocess with a controlled HOME and cwd so
that nothing on the developer's machine leaks into the test sandbox.
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


class BriefingHookTests(unittest.TestCase):
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
        ti = {"subagent_type": "demo", "prompt": "ORIGINAL"}
        ti.update(overrides.pop("tool_input", {}))
        return {
            "tool_name": "Agent",
            "cwd": str(self.cwd),
            "tool_input": ti,
            **overrides,
        }

    # --- passthrough cases ----------------------------------------------

    def test_non_agent_tool_is_noop(self):
        proc = run_hook(
            {"tool_name": "Bash", "tool_input": {"command": "ls"}},
            fake_home=self.home,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_agent_without_frontmatter_is_noop(self):
        write(self.cwd / ".claude/agents/demo.md", "Just a body, no frontmatter.\n")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_agent_without_briefing_block_is_noop(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            name: demo
            description: x
            ---
            body
        """)
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_bare_top_level_skills_key_is_ignored(self):
        # `skills:` at the top level belongs to Claude Code itself; the
        # briefing hook MUST NOT read it. Only `briefing.skills` counts.
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            name: demo
            skills:
              - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "FOO")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_unknown_agent_is_noop(self):
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_garbage_stdin_is_noop(self):
        proc = subprocess.run(
            ["python3", str(HOOK)],
            input="this is not json",
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(self.home)},
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    # --- frontmatter parsing -------------------------------------------

    def test_block_list_parses(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
                - "bar"
                - 'baz'
            ---
            body
        """)
        for s in ("foo", "bar", "baz"):
            write(self.cwd / f".claude/skills/{s}/SKILL.md", f"# {s}\n")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn('<skill name="foo">', prompt)
        self.assertIn('<skill name="bar">', prompt)
        self.assertIn('<skill name="baz">', prompt)
        self.assertTrue(prompt.endswith("ORIGINAL"))

    def test_flow_list_parses(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills: [foo, "bar", 'baz']
            ---
            body
        """)
        for s in ("foo", "bar", "baz"):
            write(self.cwd / f".claude/skills/{s}/SKILL.md", f"# {s}\n")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn('<skill name="foo">', prompt)
        self.assertIn('<skill name="bar">', prompt)
        self.assertIn('<skill name="baz">', prompt)

    def test_briefing_block_coexists_with_other_frontmatter(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            name: demo
            description: a demo
            allowed-tools: Read, Bash
            briefing:
              skills:
                - foo
            model: sonnet
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "FOO BODY")
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("FOO BODY", prompt)

    # --- resolution order ----------------------------------------------

    def test_project_beats_user(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "PROJECT FOO")
        write(self.home / ".claude/skills/foo/SKILL.md", "USER FOO")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("PROJECT FOO", prompt)
        self.assertNotIn("USER FOO", prompt)

    def test_user_beats_plugin(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.home / ".claude/skills/foo/SKILL.md", "USER FOO")
        write(
            self.home / ".claude/plugins/cache/somepl/skills/foo/SKILL.md",
            "PLUGIN FOO",
        )
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("USER FOO", prompt)
        self.assertNotIn("PLUGIN FOO", prompt)

    def test_plugin_cache_resolves(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(
            self.home / ".claude/plugins/cache/somepl/skills/foo/SKILL.md",
            "PLUGIN FOO",
        )
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("PLUGIN FOO", prompt)

    # --- namespaced form -----------------------------------------------

    def test_namespaced_skill(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - superpowers:brainstorming
            ---
            body
        """)
        write(
            self.home
            / ".claude/plugins/cache/superpowers/skills/brainstorming/SKILL.md",
            "BRAIN BODY",
        )
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn('<skill name="superpowers:brainstorming">', prompt)
        self.assertIn("BRAIN BODY", prompt)

    def test_namespaced_skill_nested_owner(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - superpowers:brainstorming
            ---
            body
        """)
        write(
            self.home
            / ".claude/plugins/cache/owner/superpowers/skills/brainstorming/SKILL.md",
            "NESTED BRAIN",
        )
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("NESTED BRAIN", prompt)

    # --- hard-fail -----------------------------------------------------

    def test_missing_skill_denies(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
                - missing-one
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "FOO")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("missing-one", hso["permissionDecisionReason"])
        self.assertNotIn("updatedInput", hso)

    # --- frontmatter is stripped from injected body -------------------

    def test_skill_frontmatter_is_stripped(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", """
            ---
            name: foo
            description: secret-metadata
            ---
            VISIBLE BODY
        """)
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertIn("VISIBLE BODY", prompt)
        self.assertNotIn("secret-metadata", prompt)

    # --- limits ----------------------------------------------------------

    def test_large_briefing_still_spawns_but_warns(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - big
            ---
            body
        """)
        write(self.cwd / ".claude/skills/big/SKILL.md", "x" * (70 * 1024))
        proc = run_hook(self._payload(), fake_home=self.home)
        out = json.loads(proc.stdout)
        self.assertIn("updatedInput", out["hookSpecificOutput"])
        self.assertIn("over 64 kB", out["systemMessage"])
        self.assertIn("over 64 kB", proc.stderr)

    def test_small_briefing_has_no_size_warning(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "FOO")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        self.assertNotIn("over 64 kB", out["systemMessage"])

    def test_skills_are_leaves_not_expanded_recursively(self):
        # A skill that itself declares briefing.skills is injected as it is;
        # its own list is not followed, so there is nothing to cycle on.
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - outer
            ---
            body
        """)
        write(self.cwd / ".claude/skills/outer/SKILL.md", """
            ---
            name: outer
            briefing:
              skills:
                - outer
                - inner
            ---
            OUTER BODY
        """)
        write(self.cwd / ".claude/skills/inner/SKILL.md", "INNER BODY")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertEqual(prompt.count("OUTER BODY"), 1)
        self.assertNotIn("INNER BODY", prompt)

    # --- what the human and the agent see ------------------------------

    def test_successful_briefing_is_audited_in_one_line(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
                - bar
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "FOO")
        write(self.cwd / ".claude/skills/bar/SKILL.md", "BAR")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        msg = out["systemMessage"]
        self.assertEqual(len(msg.splitlines()), 1)
        self.assertIn("demo", msg)
        self.assertIn("foo, bar", msg)
        self.assertIn("kB", msg)

    def test_each_skill_is_wrapped_in_a_skill_element(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "---\nname: foo\n---\nFOO BODY\n")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        self.assertRegex(prompt, r'<skill name="foo">\s*FOO BODY\s*</skill>')
        self.assertNotIn("## Skill:", prompt)
        self.assertTrue(prompt.rstrip().endswith("ORIGINAL"))

    # --- finding the agent the way Claude Code does ----------------------

    def test_agent_found_by_frontmatter_name_not_file_name(self):
        write(self.cwd / ".claude/agents/some-file.md", """
            ---
            name: demo
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "BY NAME")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        self.assertIn("BY NAME", out["hookSpecificOutput"]["updatedInput"]["prompt"])

    def test_agent_found_in_subdirectory(self):
        write(self.cwd / ".claude/agents/team/demo.md", """
            ---
            name: demo
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "NESTED")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        self.assertIn("NESTED", out["hookSpecificOutput"]["updatedInput"]["prompt"])

    def test_file_named_after_agent_but_named_otherwise_is_not_it(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            name: someone-else
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "WRONG")
        proc = run_hook(self._payload(), fake_home=self.home)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
