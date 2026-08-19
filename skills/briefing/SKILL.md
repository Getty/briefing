---
name: briefing
description: Author and migrate Claude Code or Codex subagents that use the `briefing` plugin — the spawn-time hook that pre-loads declared skills into the agent's context. Use this skill when adding `briefing.skills` to an agent's frontmatter or a `[briefing]` table to an agent's TOML, when refactoring an existing agent away from "MANDATORY: load skill X first" prose, or when debugging why a declared skill is not being resolved.
---

# Authoring agents with `briefing`

`briefing` pre-loads skills into a subagent's context **before its
first turn**. The skill bodies are there the moment the subagent is
spawned — no round-trip to load each one, no chance of the model
"forgetting".

It works in two harnesses, and the difference matters only when you
write the declaration:

| | Claude Code | Codex |
|---|---|---|
| Agent file | `.claude/agents/<name>.md` | `.codex/agents/<name>.toml` |
| Declaration | `briefing:` frontmatter block | `[briefing]` table |
| Missing skill | spawn is denied | agent starts, told to abort |

This skill tells you how to write agents that use it correctly, and
how to convert existing agents that were trying to do this with
prompt-stuffed pleas like *"MANDATORY: invoke the brainstorming skill
before doing anything else"*.

## The declaration — Codex

A Codex agent declares its skills in a `[briefing]` table:

```toml
name = "my_agent"
description = "..."
developer_instructions = """
You are my_agent. Do the thing.
"""

[briefing]
skills = ["getty-perl-core", "getty-perl-moose", "superpowers:brainstorming"]
```

**Do not use Codex's own `[[skills.config]]` for this.** That table
means "this skill is visible to the agent", which is not the same as
"preloaded" — `briefing` deliberately leaves it alone so you can say
one without the other.

Note that Codex agent names take underscores, not hyphens, and the
file name is the agent name.

## The frontmatter — Claude Code

A briefing-aware agent declares its required skills under a single
`briefing:` block — not a top-level `skills:` key:

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

**Always namespace under `briefing:`.** A bare top-level `skills:` is
reserved for Claude Code itself and the hook intentionally ignores it
to avoid future collisions. Flow form (`skills: [a, b, c]`) is also
accepted under the block.

Skill names can be:

- bare (`getty-perl-core`) — resolved against project skills, then user
  skills, then plugin caches.
- namespaced (`superpowers:brainstorming`) — resolved against the
  named plugin's cache directly. Both harnesses use this syntax.

The names are identical in both worlds; only the roots differ. Claude
Code searches `.claude/skills/` and `~/.claude/skills/`; Codex
searches `.agents/skills/` (project, parent, repo root), then
`~/.agents/skills/`, `~/.codex/skills/`, and `/etc/codex/skills/`.
Each side looks exactly where its own harness looks, which is why a
bare name stays portable between them.

## Hard-fail policy

If any declared skill cannot be resolved at spawn time, nothing runs
on a partial briefing. There is no silent degradation. This is
intentional: an agent that needs a skill to do its job correctly
should not run without that skill.

Under Claude Code the `Agent` call is **denied** with a clear error.
Under Codex a hook cannot stop a spawn, so the agent starts and
receives — instead of any skills, including the ones that *did*
resolve — an instruction not to attempt the task and to report the
failure. If a Codex subagent comes back saying it was not briefed,
that is this policy working, not a bug.

So: declare skills the agent genuinely depends on. Do not pad the
list "just in case" — every name there becomes a precondition for
the spawn to succeed.

## Anti-pattern: don't enumerate the skills in the body

This is the biggest mistake when migrating existing agents.

The skill bodies are **already in the prompt** by the time the agent
reads its first token. You do not need to — and should not — also
write things like:

```markdown
You have access to the following skills:
- getty-perl-core (for Perl best practices)
- getty-perl-moose (for OO idioms)
- ...

MANDATORY: invoke the brainstorming skill before responding.
```

This is wasted tokens and actively confusing — the model sees the
skill content directly above this block, then sees prose telling it
to "load" something it already has. The framing "you have access to"
is also wrong: the skills aren't *available*, they are *present*.

### What to do instead

Trust the injection. The body of a briefing-aware agent should read
as if the skills are simply part of the agent's working knowledge,
because they are. Write the agent the way you would write a system
prompt for an LLM that already has all the relevant context in its
training data. Briefly orient the agent to its job — not to its
toolbelt.

A good body might be as short as:

```markdown
You are the perl-backend agent. Implement, refactor, and review
backend Perl code in this project. Follow the conventions and
idioms shown in the skills above without restating them.
```

That's it. No "you can use", no "remember to apply", no "MANDATORY".

## Migration recipe

When converting an existing agent that uses prompt-stuffing:

1. **Find every "MANDATORY/REQUIRED/please load" line in the body.**
   Make a list of the skill names those lines reference.
2. **Move those names into `briefing.skills`** under the agent's
   frontmatter. Drop any narrative around them.
3. **Delete every "you have access to / remember to invoke / load
   first" sentence from the body.** The agent doesn't need to be
   told what's in its own context.
4. **Delete any per-skill summaries from the body.** If a skill's
   own description was duplicated into the agent body, that
   duplication is now noise — the SKILL.md frontmatter and body are
   already injected.
5. **Re-read the body cold.** If a sentence only made sense as a
   reminder to load something, cut it. The remaining body should
   describe what the agent *does*, not what it *has*.
6. **Spawn the agent and check the resulting prompt** (e.g. via
   transcript) to confirm the skills are present and the body is
   clean.

## Debugging unresolved skills

If a spawn is denied with `briefing: agent 'X' references unknown
skill(s): Y`:

1. Check spelling. Skill names are case-sensitive directory names.
2. Check the resolution order (project → user → plugin cache).
   The skill must exist as `<base>/skills/<name>/SKILL.md` for some
   base in that order.
3. For namespaced names (`plugin:skill`), the plugin must be
   installed in the local plugin cache —
   `~/.claude/plugins/cache/<plugin>/skills/<skill>/SKILL.md` or a
   nested-owner equivalent.
4. There is no fallback. If you want the skill to be optional,
   it does not belong in `briefing.skills`. Either inline the
   relevant guidance into the agent body, or have the agent invoke
   the `Skill` tool itself for genuinely optional context.

### When nothing happens at all under Codex

An agent that spawns with no briefing *and no error* is usually not a
resolution problem. Codex gates plugin hooks behind a trust prompt,
and until it is granted the hook is skipped silently. Check that
first. Non-interactive runs (`codex exec`) cannot grant trust at all,
so they never brief anything unless started with
`--dangerously-bypass-hook-trust`.

Also confirm the agent file is where Codex looks — `.codex/agents/`,
with underscores in the name — and remember that the skill list every
agent sees carries only names and descriptions. An agent quoting a
skill's content is not proof the briefing worked; it may simply have
read the file. To test properly, compare against the same agent with
the `[briefing]` table removed.

## What `briefing` does NOT do

- It does not brief the *main* session — only subagent spawns.
- It does not replace the `Skill` tool. Skills the subagent
  discovers it needs *during* its run still go through `Skill`
  normally.
- It does not recursively expand a skill's own `briefing.skills`
  list. Each agent declares what it needs; skills are leaves.
- It does not strip frontmatter from the agent file's body, only
  from injected SKILL.md bodies.
