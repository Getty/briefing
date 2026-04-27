# briefing

> **Programmatic briefing beats prompt stuffing.**

A Claude Code plugin that lets a subagent declare its required skills in
frontmatter — and guarantees they are loaded *before* the agent thinks
its first thought. No "MANDATORY: load X first" pleading in the body.
No silent skips. The skills are simply *there* when the agent wakes up.

## How it works

`briefing` ships a single `PreToolUse` hook bound to the `Agent` tool:

1. Subagent is about to spawn — Claude Code calls the hook with the
   `Agent` tool input (`subagent_type`, `prompt`, …).
2. Hook reads the target agent's markdown file and parses its YAML
   frontmatter for a `skills:` list.
3. Each skill name is resolved against the same locations Claude Code
   itself uses — project `.claude/skills/`, user `~/.claude/skills/`,
   and plugin caches — including the `plugin:skill` namespaced form.
4. Skill bodies are concatenated into a "pre-loaded skills" block and
   prepended to the agent's prompt. The block tells the agent the
   skills are already in context and it must NOT call the `Skill`
   tool for them.
5. If any declared skill cannot be resolved, the spawn is **denied**
   with a clear error — no silent drift.

## Agent frontmatter

```yaml
---
name: perl-backend-master-and-pipeline
description: ...
allowed-tools: Read, Edit, Write, Bash, Glob, Grep
skills:
  - perl-core
  - perl-moose
  - perl-ai-langertha
  - perl-io-async-future
  - perl-firecrawl
  - perl-localization-with-locale-simple
---
```

The `skills:` key is a custom extension — Claude Code's harness ignores
it; only `briefing` reads it.

## Install

Clone the repo into your plugin cache and enable it:

```sh
git clone https://github.com/Getty/briefing.git \
    ~/.claude/plugins/cache/briefing
```

Then enable it in your Claude Code `settings.json`:

```json
{
  "enabledPlugins": {
    "briefing": true
  }
}
```

## Try it

Drop the example agent + skill into any project:

```sh
cp examples/agents/briefing-demo.md       /your/project/.claude/agents/
cp -r examples/skills/briefing-demo-skill /your/project/.claude/skills/
```

Spawn the `briefing-demo` subagent — it will echo back a magic phrase
from `briefing-demo-skill/SKILL.md`, proving the skill body was already
in its context before its first turn.

## Develop

```sh
python3 -m py_compile hooks/briefing-preload
python3 -m unittest discover tests -v
```

Stdlib only. No dependencies. CI runs on Python 3.10 / 3.11 / 3.12.

## Status

v0.1.0 — working hook, hard-fail on missing skills. See `TODO.md`.
