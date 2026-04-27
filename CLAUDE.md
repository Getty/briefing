# briefing — CLAUDE.md

This is the **briefing** Claude Code plugin. Motto:

> Programmatic briefing beats prompt stuffing.

## What this plugin does

Ships a single `PreToolUse` hook on the `Agent` tool. When a subagent
is about to spawn, the hook:

1. Reads the target agent's markdown file (project then user level).
2. Parses YAML frontmatter for a custom `briefing.skills` list (the
   `briefing:` block reserves all of our keys under one namespace).
3. Resolves each skill name against project / user / plugin-cache
   skill locations.
4. Inlines each `SKILL.md` body into a "pre-loaded skills" block and
   prepends it to the agent's `prompt`.
5. **Hard-fails** the spawn if any skill cannot be resolved.

The agent therefore wakes up with the skill content already in its
context window — no LLM round-trip to invoke `Skill` per skill, no
chance of the model "forgetting" to load them.

## File layout

```
.claude-plugin/plugin.json   plugin manifest (name, version, description)
hooks/hooks.json             hook registration (PreToolUse → Agent)
hooks/briefing-preload       the hook itself (Python 3, executable)
skills/briefing/SKILL.md     ships with the plugin — teaches Claude
                             how to author and migrate briefing-aware
                             agents (anti-patterns, migration recipe,
                             debugging)
examples/                    example agent + minimal skill for testing
tests/                       pytest-style tests (python3 -m unittest)
README.md                    user-facing intro
TODO.md                      live worklist
```

## Hook contract — what the hook reads and writes

**stdin** — Claude Code passes a JSON object:

```json
{
  "session_id": "...",
  "transcript_path": "...",
  "cwd": "/abs/path/to/project",
  "tool_name": "Agent",
  "tool_input": {
    "subagent_type": "perl-backend-master-and-pipeline",
    "description": "...",
    "prompt": "...",
    "model": "sonnet"
  }
}
```

**stdout** — JSON with `hookSpecificOutput`:

- Success: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {<modified tool_input>}}}`
- Missing skill: `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}`
- No-op (not Agent / no frontmatter / no skills): exit 0 with empty stdout.

The hook **must** be idempotent and side-effect-free. It only reads
files; it never writes.

## Skill resolution order

Bare name (`perl-core`):

1. `<cwd>/.claude/skills/<name>/SKILL.md`
2. `~/.claude/skills/<name>/SKILL.md`
3. `~/.claude/plugins/cache/*/skills/<name>/SKILL.md`
4. `~/.claude/plugins/cache/*/*/skills/<name>/SKILL.md`

Namespaced (`superpowers:brainstorming`):

1. `~/.claude/plugins/cache/superpowers/skills/brainstorming/SKILL.md`
2. `~/.claude/plugins/cache/*/superpowers/skills/brainstorming/SKILL.md`

First match wins.

## Style rules for working in this repo

- Python 3.8+ assumed for the hook. Standard library only — no pip
  deps. `json`, `re`, `glob`, `os`, `sys` are all stdlib.
- The hook is performance-critical: it runs on every `Agent` spawn.
  Keep it under ~50ms cold. No heavy imports.
- All code paths must exit 0 cleanly even on bad input. **Never
  block a spawn unless a declared skill is genuinely missing.** A
  parse error in someone else's agent file is not our bug.
- Tests live under `tests/` and run with `python3 -m unittest
  discover tests`. Stdlib only.
- Commit style: `git-commit-style` — compact conventional commits.

## What this plugin is NOT

- Not a skill loader for the *main* session — only for `Agent` spawns.
- Not a prompt rewriter for arbitrary tools — only `Agent`.
- Not a replacement for the `Skill` tool. Skills the agent discovers
  *during* its run still go through `Skill` normally.
- Not opinionated about which skills an agent should declare. That's
  the agent author's job.
