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
   frontmatter for a `briefing.skills` list.
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
briefing:
  skills:
    - perl-core
    - perl-moose
    - perl-ai-langertha
    - perl-io-async-future
    - perl-firecrawl
    - perl-localization-with-locale-simple
---
```

Everything plugin-specific lives under a single `briefing:` block, so
we never collide with Claude Code's own frontmatter keys (e.g. a
hypothetical future top-level `skills:`). The plain top-level
`skills:` key is intentionally ignored — it's reserved for the
harness.

A flow-style list works too:

```yaml
briefing:
  skills: [perl-core, perl-moose]
```

## Install

From inside Claude Code, via the shared marketplace that carries every
Getty plugin:

```
/plugin marketplace add Getty/claude-code
/plugin install briefing@getty
```

The first command registers the marketplace; the second installs the
`briefing` plugin from it. The hook is active immediately on the next
`Agent` spawn — no restart needed.

This repo is *also* a one-plugin marketplace, and stays one:

```
/plugin marketplace add Getty/briefing
/plugin install briefing@briefing
```

Both paths install the same plugin from the same repo and both keep
receiving updates. The shared marketplace just saves you from
registering a new one per plugin. If you installed the old way, a
`SessionStart` hook mentions this once and then never again.

## Authoring briefing-aware agents

The plugin ships with a `briefing` skill that documents how to write
agents that use it correctly — including the anti-pattern of
restating skills in the agent body when they're already injected,
and a recipe for migrating prompt-stuffed agents to declarative
`briefing.skills`. Once installed, invoke it as `/briefing` (or have
Claude pick it up automatically when working on agent files).

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

[v0.1.0](https://github.com/Getty/briefing/releases/tag/v0.1.0) —
working hook with namespaced `briefing.skills` frontmatter, hard-fail
on missing skills. Not submitted to Anthropic's official directory
yet; install directly from this repo. See `TODO.md` and
`CHANGELOG.md`.
