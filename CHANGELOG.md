# Changelog

## 0.2.0 — 2026-04-27

**Breaking:** the agent frontmatter key moved from a top-level
`skills:` list to a nested `briefing.skills` list. The bare
`skills:` key is now intentionally ignored — it's reserved for
Claude Code's own future use, and we don't want a semantic
collision if the harness ever adopts it. Everything plugin-specific
now lives under a single `briefing:` block, leaving room for future
options (`briefing.format`, `briefing.max_size`, …) without
sprinkling `briefing-foo:` keys across the frontmatter.

Migration: replace

```yaml
skills:
  - foo
```

with

```yaml
briefing:
  skills:
    - foo
```

## 0.1.0 — 2026-04-27

Initial release.

- `PreToolUse` hook on the `Agent` tool, written in Python 3 (stdlib
  only).
- Reads target subagent's frontmatter, parses `skills:` (block + flow
  forms), resolves bare and `plugin:skill` namespaced names against
  project / user / plugin-cache locations.
- Inlines each `SKILL.md` body into the agent's prompt before the
  agent's first turn — no `Skill` tool round-trip required.
- Hard-fails (`permissionDecision: deny`) if any declared skill cannot
  be resolved.
- 14 unit tests covering passthrough, frontmatter parsing, resolution
  precedence, namespaced lookup, and hard-fail behavior.
- GitHub Actions CI on Python 3.10 / 3.11 / 3.12.
