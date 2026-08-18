# Changelog

## 0.3.0 — unreleased

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

## 0.2.0 — unreleased

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
