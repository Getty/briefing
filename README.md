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
| Agent definition | `.claude/agents/*.md`, by `name` | `.codex/agents/*.toml`, by `name` |
| Declaration | `briefing.skills` in frontmatter | `# briefing: skills = [...]` comment |
| Injection | rewrites the agent's prompt | `additionalContext` |
| Missing skill | spawn is **denied** | agent starts, told to abort |

The last row is not a choice. A `SubagentStart` hook cannot stop a spawn — Codex
parses `continue: false` for compatibility but ignores it. So under Codex the
nearest honest equivalent is an agent that starts and refuses: instead of skills
it receives an instruction not to attempt the task and to report the failure.

Each skill arrives wrapped in its own element, so the agent can tell where one
ends and the next begins:

```
<skill name="getty-perl-core">
…the SKILL.md body, frontmatter stripped…
</skill>
```

Every successful briefing leaves one line for you, not for the model:
`briefing: my-agent ← getty-perl-core, superpowers:brainstorming (14 kB)`. Above
64 kB of skill text a second line says so — the spawn still goes ahead.

## Checking before anything spawns

A broken declaration should not cost a spawn to discover. At session start the
hook checks every briefing-aware agent of the harness you are in and, if any
would fail, tells you which and why. A healthy project hears nothing.

For the full picture, run the doctor:

```sh
briefing-doctor                 # this project, both harnesses
briefing-doctor --cwd ~/dev/x --harness codex
```

```
briefing doctor — /home/me/dev/x

Claude Code
  ok    reviewer  (.claude/agents/reviewer.md)
        getty-perl-core, kanban-issues-karr-cli  (13 kB)
  FAIL  backend  (.claude/agents/backend.md)
        getty-perl-core, kubernetes-rest  (18 kB)
        → unknown skill(s): kubernetes-rest
```

It exits 1 if any spawn would fail — an unknown skill, or a Codex agent still
carrying a `[briefing]` table — so it works in CI. Claude Code puts
`briefing-doctor` on `PATH` for the agent; Codex plugins cannot, so there run
`python3 <plugin root>/hooks/briefing-preload doctor`.

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

**Codex** — as a `# briefing:` comment line in the agent's TOML:

```toml
name = "my_agent"
description = "..."
# briefing: skills = ["getty-perl-core", "getty-perl-moose", "superpowers:brainstorming"]
developer_instructions = """
You are my_agent. Do the thing.
"""
```

It is a comment because it has to be. Codex reads agent files strictly and
drops the whole agent over any key it does not know — a `[briefing]` table, the
form used up to 0.3.0, makes Codex 0.153 ignore the agent with ``unknown field
`briefing` ``. A comment is invisible to Codex and every other TOML parser. Keep
the declaration on one line, outside any multi-line string; a matching line
inside `developer_instructions` is prose and is not read. The hook still reads
an old `[briefing]` table where Codex lets the agent spawn at all, and tells you
to migrate it.

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
looks: `.claude/skills/` for Claude Code; `.codex/skills/` and `.agents/skills/`
up to the repo root, then `$CODEX_HOME/skills/` and `~/.agents/skills/` for
Codex. Codex agents are found the way Codex finds them — by their `name` field,
in any `*.toml` under `agents/`, or through `[agents.<name>] config_file`.

A briefing above 64 kB of skill text still goes through, but the hook says so in
a `systemMessage`: that much context is rarely what anyone meant.

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
`briefing` skills answered from skill content it was never told to read, while
the identical agent without the declaration did not. See `CHANGELOG.md` and
`TODO.md`.

## License

Copyright (c) 2026 Torsten Raudssus.

This is free software; you can redistribute it and/or modify it under the
terms of the [Artistic License 2.0](LICENSE).
