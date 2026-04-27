# Changelog

## 0.1.0 — unreleased

Initial scaffold. Not yet published anywhere — install via
`/plugin marketplace add Getty/briefing` from the GitHub repo
directly.

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
