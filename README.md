# briefing

> **Programmatic briefing beats prompt stuffing.**

A subagent declares the skills it needs. `briefing` guarantees those skills are
in its context *before it thinks its first thought* — no "MANDATORY: load X
first" pleading in the body, no silent skips.

Works in **Claude Code** and **Codex**, from one set of files.

## The problem this solves

Every agent harness that has both subagents and skills has the same gap, and it
follows from two design decisions that are individually correct:

**Subagents start fresh.** A subagent gets its own context window — that is the
point of it. Whatever the main agent had read, the subagent has not.

**Skills load lazily.** Skills use progressive disclosure: what sits in the
context window is a *list* — each skill's name, description, and where to find
it. The instructions themselves are only read once the agent decides it needs
them. That keeps the context small, and it works well for an agent browsing a
menu.

Put the two together and you get an agent that was spawned *because* it needs
particular expertise, and that must nonetheless discover that expertise on its
own, from a one-line description, in the middle of a task. Sometimes it does.
Sometimes it decides the description does not match closely enough and does the
work uninformed — and nothing in the output says so.

The usual workaround is to write the instruction into the agent's body: *"You
MUST invoke the getty-perl-core skill before doing anything."* That is prompt
stuffing. It competes for attention with everything else in the prompt, it
duplicates content that already exists in a skill, and it degrades quietly.

Codex sharpens the problem. Its own system prompt tells the main agent:

> *"Do not delegate reading, summarizing, or interpreting skill instructions to
> a subagent."*

So the subagent is not supposed to read the skill — and nothing hands it over
either.

`briefing` closes the gap mechanically: at spawn time, a hook reads the agent's
declaration, resolves each skill, and puts the full text into the agent's
context. The agent wakes up already briefed. If a declared skill cannot be
found, nothing proceeds on a partial briefing.

## How it works

| | Claude Code | Codex |
|---|---|---|
| Hook event | `PreToolUse` on the `Agent` tool | `SubagentStart` |
| Agent definition | `.claude/agents/<name>.md` | `.codex/agents/<name>.toml` |
| Declaration | `briefing.skills` in frontmatter | `[briefing] skills` table |
| Injection | rewrites the agent's prompt | `additionalContext` |
| Missing skill | spawn is **denied** | agent starts, told to abort |

The last row is not a choice. A `SubagentStart` hook cannot stop a spawn — Codex
parses `continue: false` for compatibility but ignores it. So under Codex the
nearest honest equivalent is an agent that starts and refuses: instead of skills
it receives an instruction not to attempt the task and to report the failure.

## Declaring skills

**Claude Code** — under a `briefing:` block in the agent's frontmatter:

```yaml
---
name: my-agent
description: ...
allowed-tools: Read, Edit, Bash
briefing:
  skills:
    - getty-perl-core
    - getty-perl-moose
    - superpowers:brainstorming
---

You are my-agent. Do the thing.
```

**Codex** — as a `[briefing]` table in the agent's TOML:

```toml
name = "my_agent"
description = "..."
developer_instructions = """
You are my_agent. Do the thing.
"""

[briefing]
skills = ["getty-perl-core", "getty-perl-moose", "superpowers:brainstorming"]
```

Same names, same resolution rules, same namespacing — only the file format
differs, because the two harnesses define agents differently.

Everything lives under a `briefing` namespace so nothing collides with keys the
harness owns. Two are left alone on purpose: a bare top-level `skills:` in
Claude Code frontmatter, and Codex's own `[[skills.config]]`. The latter means
*"this skill is visible to the agent"*, which is not the same as *"preloaded"* —
reinterpreting it would take away your ability to say one without the other.

Skill names resolve the same way in both worlds:

- **bare** (`getty-perl-core`) — project skills, then user skills, then plugin caches.
- **namespaced** (`superpowers:brainstorming`) — straight to that plugin's skills.

Only the roots differ, and each side searches exactly where its own harness
looks: `.claude/skills/` for Claude Code, `.agents/skills/` for Codex.

## Install

**Claude Code**, via the shared marketplace that carries every Getty plugin:

```
/plugin marketplace add Getty/marketplace
/plugin install briefing@getty
```

This repo is *also* a one-plugin marketplace for Claude Code. That one is legacy —
it serves the people who installed briefing before the shared catalog existed, and it
stays maintained so nobody has to migrate:

```
/plugin marketplace add Getty/briefing
/plugin install briefing@briefing
```

Both paths install the same plugin from the same repo and both keep receiving
updates. If you installed the old way, a `SessionStart` hook mentions the shared
marketplace once and then never again.

**Codex**, from the shared marketplace — the only route there:

```
codex plugin marketplace add Getty/marketplace
codex plugin add briefing@getty
```

Codex asks you to trust a plugin's hooks before it runs them. Until you do,
`briefing` is installed but silent — no error, no injected context, agents simply
spawn unbriefed. If skills are not arriving, check the hook trust prompt first.
Non-interactive runs (`codex exec`) cannot grant that trust at all.

## Authoring briefing-aware agents

The plugin ships a `briefing` skill documenting how to write agents that use it
correctly — both declaration formats, the anti-pattern of restating skills in the
agent body when they are already injected, and a recipe for migrating
prompt-stuffed agents. Invoke it as `/briefing`, or let the agent pick it up when
it works on agent files.

## Try it

```sh
cp examples/agents/briefing-demo.md       /your/project/.claude/agents/
cp -r examples/skills/briefing-demo-skill /your/project/.claude/skills/
```

Spawn the `briefing-demo` subagent — it echoes a magic phrase from the skill,
proving the body was in its context before its first turn.

## Develop

```sh
python3 -m py_compile hooks/briefing-preload
python3 -m unittest discover tests -v
```

Stdlib only, no dependencies. CI runs Python 3.10 / 3.11 / 3.12 — the Codex
branch parses TOML with `tomllib` where it exists and falls back to a small regex
parser on 3.10, so both paths are exercised across the matrix.

## Status

Working in both harnesses, verified end to end: a Codex subagent declaring
`[briefing] skills` answered from skill content it was never told to read, while
the identical agent without the declaration did not. See `CHANGELOG.md` and
`TODO.md`.
