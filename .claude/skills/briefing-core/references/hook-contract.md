# Hook contract for this checkout

Applies to `hooks/briefing-preload`, not unchecked to installed plugin versions.
`main()` routes `SubagentStart` to the shared briefing, `SessionStart` to
pre-flight, and otherwise only `tool_name == "Agent"` to the Claude Code guard.
When invoked as `briefing-doctor` or with `doctor` as its first argument, the same
resolution runs as a CLI. `bin/briefing-doctor` is its executable wrapper.

## Claude Code: PreToolUse guard

```json
{
  "hook_event_name": "PreToolUse", "cwd": "/abs/path", "tool_name": "Agent",
  "permission_mode": "auto",
  "tool_input": { "subagent_type": "my-agent", "prompt": "...", "model": "sonnet" }
}
```

Missing declared skill: `hookSpecificOutput` with
`hookEventName: "PreToolUse"`, `permissionDecision: "deny"`, and
`permissionDecisionReason`. Otherwise exit 0 with empty stdout — even on success.
The guard never changes the call and never emits `updatedInput`.
Auto mode reviews the call before hooks and can deny subsequent changes:
`a hook changed this call's input after auto mode reviewed it`.
Therefore, do not reintroduce the prompt rewrite used through briefing 0.5.x.

## SubagentStart: both harnesses

Claude Code, observed payload in 2.1.318 (without `permission_mode`):

```json
{
  "hook_event_name": "SubagentStart", "cwd": "/abs/path",
  "session_id": "...", "transcript_path": "/home/u/.claude/projects/.../x.jsonl",
  "prompt_id": "...", "agent_id": "...", "agent_type": "my-agent"
}
```

Codex:

```json
{
  "hook_event_name": "SubagentStart", "cwd": "/abs/path",
  "agent_type": "my_agent", "agent_id": "...", "turn_id": "..."
}
```

`spawn_harness` first distinguishes through `transcript_path` (`/.claude/` versus
`/.codex/` or `$CODEX_HOME`), then through Codex's `turn_id`. With no unambiguous
signal, a found Claude Code agent wins; otherwise Codex is used. `agent_type` is
the declared agent name, not necessarily the file name. No matching agent or no
declaration means exit 0 and empty stdout; built-ins without an agent file are
also no-ops.

Success: `hookSpecificOutput.hookEventName: "SubagentStart"` and
`additionalContext` with the complete briefing.
Missing skill: instead, an instruction not to perform the task and to return to
the requester with the error; additionally, `systemMessage`.
Even skills that were already resolvable remain out when an error occurs. This
also applies if, under Claude Code, a skill disappears between the guard and
`SubagentStart`.

Neither harness can stop the spawn at `SubagentStart`. Codex ignores
`continue: false` despite its compatibility parser; a partial briefing is not a
substitute. `additionalContextLimit: 0` in `hooks/hooks.json` prevents Codex
from writing long output to disk and providing only a preview to the model
context (the default is about 2500 tokens).

**Legacy-harness caveat:** Claude Code must support context from `SubagentStart`;
2.1.318 was tested, not the earliest possible version. Older versions without
this support start the agent silently unbriefed: a successful guard injects
nothing and is not a fallback.

## Shared output

On success, `SubagentStart` writes an audit line for the human to `systemMessage`:
`briefing: my-agent ← skill-a, skill-b (N kB)`; warnings follow on further lines.
More than 64 KiB of skill text warns but does not deny.
Each skill is embedded without frontmatter as follows:

```xml
<skill name="skill-a" dir="/abs/path/to/skill-a">
…SKILL.md content…
</skill>
```

`dir` is absolute; only the main text is preloaded. Further files remain
progressively accessible. A skill does not recursively load further
`briefing.skills`.

## SessionStart: both harnesses

```json
{
  "hook_event_name": "SessionStart", "cwd": "/abs/path", "session_id": "...",
  "source": "startup", "transcript_path": "/home/u/.codex/sessions/..."
}
```

Only a top-level `systemMessage` for declarations that do not work, otherwise no
output. Never `hookSpecificOutput`, which would create model context here.
`transcript_path` distinguishes `/.codex/` or `$CODEX_HOME` from `/.claude/`;
without an unambiguous signal, both are checked.
`startup`, `resume`, and a missing `source` are checked; other sources such as
compaction remain silent. Overlong but working briefings are not reported again
here. Doctor, by contrast, shows errors and budget warnings.

## Shared hook file

`hooks/hooks.json` remains shared: `SubagentStart` serves both harnesses,
`PreToolUse` only the Claude Code guard. Codex also resolves `${CLAUDE_PLUGIN_ROOT}`.
Windows invocation is exec form (`command` with `args: []`); the `.exe` launcher
runs there instead of the extensionless script. Background and native tests:
`winlaunch/README.md`.

`hooks/briefing-marketplace-notice` is a separate SessionStart notice with its
own state storage; the read-only and side-effect-free guarantee of the preload
hook is not a claim about this notice hook.
