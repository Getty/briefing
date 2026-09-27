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


def install_plugin(home, name, *, version="1.0.0", marketplace="mp",
                   skills=(), manifest=None, scope="user", project=None):
    """Lay a plugin out the way Claude Code installs it: a versioned cache
    directory, registered in installed_plugins.json. `skills` maps a path
    below the plugin root to a SKILL.md body."""
    root = home / ".claude/plugins/cache" / marketplace / name / version
    for rel, body in dict(skills).items():
        write(root / rel / "SKILL.md", body)
    if manifest is not None:
        write(root / ".claude-plugin/plugin.json", json.dumps(manifest))
    index = home / ".claude/plugins/installed_plugins.json"
    data = (json.loads(index.read_text()) if index.exists()
            else {"version": 2, "plugins": {}})
    entry = {"scope": scope, "installPath": str(root), "version": version}
    if project is not None:
        entry["projectPath"] = str(project)
    data["plugins"].setdefault(f"{name}@{marketplace}", []).append(entry)
    write(index, json.dumps(data))
    return root


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

    def _declare(self, *skills):
        items = "".join(f"\n    - {s}" for s in skills)
        write(self.cwd / ".claude/agents/demo.md",
              f"---\nbriefing:\n  skills:{items}\n---\nbody\n")

    def _briefed(self):
        """The rewritten prompt, or None if the spawn was not briefed."""
        proc = run_hook(self._payload(), fake_home=self.home)
        hso = json.loads(proc.stdout)["hookSpecificOutput"]
        return hso.get("updatedInput", {}).get("prompt")

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
        self.assertIn('<skill name="foo"', prompt)
        self.assertIn('<skill name="bar"', prompt)
        self.assertIn('<skill name="baz"', prompt)
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
        self.assertIn('<skill name="foo"', prompt)
        self.assertIn('<skill name="bar"', prompt)
        self.assertIn('<skill name="baz"', prompt)

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
        self._declare("foo")
        write(self.home / ".claude/skills/foo/SKILL.md", "USER FOO")
        install_plugin(self.home, "somepl", skills={"skills/foo": "PLUGIN FOO"})
        prompt = self._briefed()
        self.assertIn("USER FOO", prompt)
        self.assertNotIn("PLUGIN FOO", prompt)

    def test_plugin_cache_resolves(self):
        self._declare("foo")
        install_plugin(self.home, "somepl", skills={"skills/foo": "PLUGIN FOO"})
        self.assertIn("PLUGIN FOO", self._briefed())

    # --- namespaced form -----------------------------------------------

    def test_namespaced_skill(self):
        self._declare("superpowers:brainstorming")
        install_plugin(self.home, "superpowers", version="6.4.1",
                       skills={"skills/brainstorming": "BRAIN BODY"})
        prompt = self._briefed()
        self.assertIn('<skill name="superpowers:brainstorming"', prompt)
        self.assertIn("BRAIN BODY", prompt)

    def test_namespaced_skill_comes_from_the_installed_version(self):
        # The cache keeps versions that are no longer installed, and some
        # versions are commit hashes, so neither "highest" nor "newest" is
        # a safe guess. installed_plugins.json says which one is live.
        self._declare("superpowers:brainstorming")
        install_plugin(self.home, "superpowers", version="6.3.0",
                       skills={"skills/brainstorming": "INSTALLED"})
        write(self.home / ".claude/plugins/cache/mp/superpowers/6.4.1"
              "/skills/brainstorming/SKILL.md", "NOT INSTALLED")
        prompt = self._briefed()
        self.assertIn("INSTALLED", prompt)
        self.assertNotIn("NOT INSTALLED", prompt)

    def test_namespaced_skill_the_manifest_places_in_a_category(self):
        self._declare("mattpocock-skills:domain-modeling")
        install_plugin(
            self.home, "mattpocock-skills", version="1.2.3",
            skills={"skills/engineering/domain-modeling": "DOMAIN BODY"},
            manifest={"name": "mattpocock-skills",
                      "skills": ["./skills/engineering/domain-modeling"]},
        )
        prompt = self._briefed()
        self.assertIn("DOMAIN BODY", prompt)
        skill_dir = os.path.abspath(
            self.home / ".claude/plugins/cache/mp/mattpocock-skills/1.2.3"
            "/skills/engineering/domain-modeling")
        self.assertIn('dir="%s"' % skill_dir, prompt)

    def test_manifest_skills_path_may_hold_several_skills(self):
        self._declare("somepl:tool")
        install_plugin(self.home, "somepl",
                       skills={"extra-skills/tool": "EXTRA TOOL"},
                       manifest={"name": "somepl", "skills": "./extra-skills/"})
        self.assertIn("EXTRA TOOL", self._briefed())

    def test_manifest_skills_add_to_the_default_scan(self):
        self._declare("somepl:plain", "somepl:extra")
        install_plugin(self.home, "somepl",
                       skills={"skills/plain": "PLAIN", "more/extra": "EXTRA"},
                       manifest={"name": "somepl", "skills": ["./more/extra"]})
        prompt = self._briefed()
        self.assertIn("PLAIN", prompt)
        self.assertIn("EXTRA", prompt)

    def test_nested_skill_the_manifest_does_not_declare_is_unknown(self):
        # Claude Code scans skills/<name>/ and the manifest's paths, nothing
        # deeper, so neither does briefing.
        self._declare("somepl:draft")
        install_plugin(self.home, "somepl",
                       skills={"skills/in-progress/draft": "DRAFT"},
                       manifest={"name": "somepl"})
        self.assertIsNone(self._briefed())

    def test_plugin_namespace_is_the_manifest_name(self):
        self._declare("real-name:tool")
        install_plugin(self.home, "entry-name",
                       skills={"skills/tool": "BY MANIFEST NAME"},
                       manifest={"name": "real-name"})
        self.assertIn("BY MANIFEST NAME", self._briefed())

    def test_project_scoped_plugin_serves_only_its_project(self):
        self._declare("somepl:tool")
        install_plugin(self.home, "somepl", skills={"skills/tool": "TOOL"},
                       scope="project", project=self.root / "elsewhere")
        self.assertIsNone(self._briefed())

        install_plugin(self.home, "somepl", version="2.0.0",
                       skills={"skills/tool": "HERE"},
                       scope="project", project=self.cwd)
        self.assertIn("HERE", self._briefed())

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
        self.assertRegex(prompt, r'<skill name="foo"[^>]*>\s*FOO BODY\s*</skill>')
        self.assertNotIn("## Skill:", prompt)
        self.assertTrue(prompt.rstrip().endswith("ORIGINAL"))

    def test_skill_element_carries_its_directory_for_references(self):
        write(self.cwd / ".claude/agents/demo.md", """
            ---
            briefing:
              skills:
                - foo
            ---
            body
        """)
        write(self.cwd / ".claude/skills/foo/SKILL.md", "See references/api.md.\n")
        write(self.cwd / ".claude/skills/foo/references/api.md", "API\n")
        out = json.loads(run_hook(self._payload(), fake_home=self.home).stdout)
        prompt = out["hookSpecificOutput"]["updatedInput"]["prompt"]
        skill_dir = os.path.abspath(self.cwd / ".claude/skills/foo")
        self.assertIn('<skill name="foo" dir="%s">' % skill_dir, prompt)
        self.assertIn("relative to", prompt)
        self.assertNotIn("\nAPI\n", prompt)

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
