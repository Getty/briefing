# Changelog

## 0.5.0 — 2026-09-24

- Each `<skill>` element carries the skill's absolute directory:
  `<skill name="foo" dir="/abs/path/skills/foo">`. Only `SKILL.md` is inlined,
  so a relative `references/api.md` had nothing to resolve against — under
  Claude Code a briefed agent searched the whole filesystem for it. The header
  now tells the agent to read references from `dir` when it needs them; they
  are still not inlined. Codex already lists every skill's path, so there it
  matters only for skills hidden from that agent.


## 0.4.1 — 2026-09-24

- The `SessionStart` pre-flight reports only what would fail at spawn time.
  0.4.0 also listed oversized briefings under "declared skills that will not
  work" — they do work, so every session start in such a project carried a
  false alarm. Size stays a `WARN` in `briefing-doctor` and a line in the
  spawn's own audit message.


## 0.4.0 — 2026-09-24

Broken declarations surface before anything spawns, and every briefing
leaves a trace.

- `briefing-doctor` checks every briefing-aware agent of a project, in both
  harnesses: which skills it declares, how large the briefing is, and what
  would fail — an unknown skill, or a Codex agent still carrying a
  `[briefing]` table. Exits 1 on a failure, so it can guard CI. It is a
  symlink to the hook in `bin/`, which Claude Code puts on `PATH`; under Codex
  run `hooks/briefing-preload doctor`.
- `SessionStart` pre-flight: the same checks run when a session starts or
  resumes, for the harness that started it, and a `systemMessage` names every
  declaration that would fail. Healthy projects hear nothing.
- Every successful briefing reports itself in one `systemMessage` line —
  `briefing: agent ← a, b (N kB)` — so you can see what an agent was given.
- Skills are injected as `<skill name="...">…</skill>` elements instead of
  `## Skill:` headings, so their boundaries are unambiguous.
- Claude Code agents are found by their frontmatter `name`, including in
  subdirectories of `.claude/agents/` — the same fix 0.3.1 made for Codex. A
  file named after the agent that declares a different `name` is not it.
- 20 new unit tests. Verified live in both harnesses — Codex 0.153.4 and
  Claude Code: briefed agents answered from skill content inside `<skill>`
  elements, controls did not, and the audit line and the pre-flight warning
  reached the harness as system messages. (`codex exec` does not print those;
  the Codex TUI does.)


## 0.3.1 — 2026-09-23

Codex agents declare their skills in a comment now, because Codex 0.153 no
longer tolerates the table.

- Codex deserializes agent files strictly and drops the **whole agent** over a
  key it does not know: ``Ignoring malformed agent role definition … unknown
  field `briefing` ``. The `[briefing]` table introduced in 0.3.0 did exactly
  that on Codex 0.153.4 — the agent silently vanished, and with it the briefing.
- The declaration is now a comment line, invisible to Codex and every other
  TOML parser:

  ```toml
  # briefing: skills = ["getty-perl-core", "superpowers:brainstorming"]
  ```

  A matching line inside a multi-line string such as `developer_instructions`
  is prose and is not read.
- A leftover `[briefing]` table is still honoured where an older Codex spawns
  the agent at all, and the hook adds a `systemMessage` asking for the move to
  the comment form. If both are present, the comment wins.
- Codex agents are found the way Codex finds them. The role name is the
  `name` field, not the file name; every `*.toml` below `agents/` counts,
  recursively; each directory from the project root down to cwd is a layer,
  nearest first; roles declared as `[agents.<name>] config_file` in a layer's
  `config.toml` win within that layer. Previously only
  `<cwd>/.codex/agents/<name>.toml` and `~/.codex/agents/<name>.toml` were
  tried, and anything else went unbriefed without a word.
- `CODEX_HOME` is honoured for agents, skills and the plugin cache.
- Codex skill roots now match Codex: `.codex/skills` and `.agents/skills` in
  every directory up to the project root, `$CODEX_HOME/skills`,
  `~/.agents/skills`, the bundled `$CODEX_HOME/skills/.system`, and
  `/etc/codex/skills`. The unconditional `<cwd>/../.agents/skills` is gone —
  Codex stops at the project root.
- A briefing over 64 kB of skill text still spawns, in both harnesses, but
  carries a `systemMessage` saying how large it is.
- Skills stay leaves: a skill's own `briefing.skills` is never followed, now
  pinned by a test.
- 24 new unit tests; suite green on Python 3.8, 3.10 and 3.13. Verified end to
  end against Codex 0.153.4: the declaring agent answered with a passphrase that
  existed only in the skill body, without a single tool call; the identical
  agent without the comment answered `UNKNOWN`; a marker in the installed hook
  recorded `SubagentStart` for both. The new agent lookup passed the same test
  live: a renamed file in `agents/team/`, a spawn from a repo subdirectory, and
  a `config_file` role were all briefed.

## 0.3.0 — 2026-08-18

Codex support, from the same set of files.

- `SubagentStart` hook for Codex, inside the same `hooks/briefing-preload`
  script: it branches on `hook_event_name`, so the Claude Code path is
  untouched.
- Codex agents declare skills in a `[briefing]` table in
  `.codex/agents/<name>.toml`. Codex's own `[[skills.config]]` is deliberately
  *not* read — it means "visible to the agent", not "preloaded".
- Skills resolve against the roots Codex itself searches (`.agents/skills` in
  project, parent and repo root, then `~/.agents/skills`, `~/.codex/skills`,
  `/etc/codex/skills`). `plugin:skill` works there too — Codex uses the same
  syntax, undocumented but observable.
- Injection goes through `additionalContext`, with `additionalContextLimit: 0`
  in `hooks.json`. At the default threshold Codex replaces large skill bodies
  with a preview and briefs nobody, silently.
- A `SubagentStart` hook cannot deny a spawn, so a missing skill yields an abort
  instruction to the agent plus a `systemMessage` to the user — and none of the
  skills that *did* resolve. No partial briefings.
- `.codex-plugin/plugin.json` points at the same `skills/` and `hooks/`
  directories. Nothing is duplicated; one `hooks.json` serves both harnesses,
  verified against Claude Code rather than assumed.
- TOML parsing uses `tomllib` where available and a regex fallback on Python
  3.10, which CI still covers. A test forces the fallback path explicitly.
- 11 new unit tests for the Codex path, plus end-to-end verification against
  Codex 0.147.0: a declaring agent answered from injected skill content, the
  identical non-declaring agent did not, and a marker confirmed `SubagentStart`
  reached the hook in both runs.

## 0.2.0 — never tagged, shipped as part of 0.3.0

- `SessionStart` hook pointing at
  [`Getty/marketplace`](https://github.com/Getty/marketplace), the shared
  marketplace that now carries every Getty plugin. It reads the marketplace
  name out of `CLAUDE_PLUGIN_ROOT`, so it stays silent for anyone already
  installed from there, for `--plugin-dir`, and for local checkouts — and
  shows at most once, recorded in `~/.claude/.briefing-marketplace-notice`.
- This repo's own marketplace stays in place and stays maintained. Both
  install paths lead to the same plugin; nobody has to migrate.
- 8 unit tests for the notice hook, covering the silent cases, the
  once-only behaviour, and an unwritable state directory.

## 0.1.0 — 2026-04-27

Initial release. Tagged as
[`v0.1.0`](https://github.com/Getty/briefing/releases/tag/v0.1.0).
Install via `/plugin marketplace add Getty/briefing` and
`/plugin install briefing@briefing`.

- `PreToolUse` hook on the `Agent` tool, written in Python 3 (stdlib
  only).
- Reads target subagent's frontmatter, parses a nested
  `briefing.skills` list (block + flow forms). Everything
  plugin-specific lives under a single `briefing:` block, so we
  never collide with Claude Code's own frontmatter keys (the bare
  top-level `skills:` is intentionally ignored — reserved for the
  harness).
- Resolves bare and `plugin:skill` namespaced names against project
  / user / plugin-cache locations.
- Inlines each `SKILL.md` body into the agent's prompt before the
  agent's first turn — no `Skill` tool round-trip required.
- Hard-fails (`permissionDecision: deny`) if any declared skill
  cannot be resolved.
- 16 unit tests covering passthrough, frontmatter parsing,
  resolution precedence, namespaced lookup, and hard-fail behavior.
- GitHub Actions CI on Python 3.10 / 3.11 / 3.12.
- One-repo marketplace via `.claude-plugin/marketplace.json`.
