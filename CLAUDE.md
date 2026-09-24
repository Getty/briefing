# briefing — CLAUDE.md

This is the **briefing** plugin, for Claude Code *and* Codex. Motto:

> Programmatic briefing beats prompt stuffing.

Product documentation lives in [README.md](README.md); this file is guidance for
working on the plugin itself.

## What this plugin does

A subagent declares the skills it needs; a hook puts their full text into the
agent's context at spawn time. The agent therefore wakes up with the content
already there — no round-trip to load each skill, no chance of the model
"forgetting".

Both harnesses have the same gap (subagents start fresh, skills load lazily) and
the same fix, but they expose different spawn events, agent formats, and
injection channels. One script serves both.

## Two harnesses, one hook script

`hooks/briefing-preload` branches on `hook_event_name` in the stdin payload:
`SubagentStart` is Codex, `SessionStart` is the pre-flight check for either,
anything else falls through to the Claude Code path keyed on
`tool_name == "Agent"`. Called as `briefing-doctor` (the symlink in `bin/`) or
with `doctor` as its first argument it is a CLI instead. Everything between
reading the declaration and emitting the result is shared: the `Briefing` class
resolves a declaration once, and the spawn paths, the pre-flight and the doctor
all read their verdict from it.

| | Claude Code | Codex |
|---|---|---|
| Event | `PreToolUse`, matcher `Agent` | `SubagentStart` |
| Agent file | `<cwd>/.claude/agents/<subagent_type>.md` | any `*.toml` under a layer's `agents/` whose `name` matches, or `[agents.<name>] config_file` |
| Declaration | `briefing.skills` in YAML frontmatter | `# briefing: skills = [...]` TOML comment |
| Output | `updatedInput` with a rewritten `prompt` | `additionalContext` |
| Missing skill | `permissionDecision: deny` | abort instruction + `systemMessage` |

**Codex cannot deny a spawn.** `continue: false` is parsed for compatibility and
then ignored, so the hard-fail policy degrades to the nearest honest thing: the
agent starts, and instead of skills it gets an instruction not to attempt the
task and to report the failure. Do not "improve" this into a partial briefing —
a half-briefed agent producing plausible output is exactly the failure mode this
plugin exists to prevent.

## Four traps specific to the Codex side

**The declaration must be a comment.** Codex deserializes agent files with
`deny_unknown_fields` (`RawAgentRoleFileToml`, which flattens `ConfigToml`) and
drops the *whole* agent over a key it does not know — warning ``Ignoring
malformed agent role definition … unknown field `briefing` ``. The `[briefing]`
table of 0.3.0 hits exactly that on Codex 0.153. `ConfigToml` has no free-form
namespace to hide in, and a sidecar `.toml` under `.codex/agents/` would itself
be loaded as an agent (discovery takes every `*.toml`, recursively). Hence
`# briefing: skills = [...]`, found by `parse_skills_comment`, which skips lines
inside multi-line strings. The legacy table is still read — with a
`systemMessage` telling the owner to migrate — because older Codex spawns it.

**`additionalContextLimit` must be `0`.** The default threshold is about 2500
tokens; above it Codex writes the hook's output to disk and sends the model a
*preview* instead. Skill bodies are routinely larger than that, so at the
default the plugin looks installed, reports no error, and briefs nobody. The
`0` in `hooks/hooks.json` is load-bearing.

**Hooks only run once the user trusts them.** Codex gates plugin hooks behind a
trust prompt. Until it is granted, hooks are skipped silently — no error, no
output. Non-interactive runs (`codex exec`) cannot grant it at all, which makes
`codex exec` useless for verifying hook behavior unless
`--dangerously-bypass-hook-trust` is passed. Debugging a "briefing does nothing"
report starts here, not in the code.

**`tomllib` is Python 3.11+.** CI still runs 3.10, so `parse_skills_toml` (the
legacy table) tries `tomllib` and falls back to a regex that understands exactly
one table and one key. The comment form needs neither. The import is *inside*
the function, so the Claude Code path never pays for it and still runs on 3.8. `tests/test_briefing_codex.py` forces the fallback by
putting a `tomllib.py` that raises `ImportError` on `PYTHONPATH` — without that
shim the fallback would never be exercised on a modern interpreter.

## File layout

```
.claude-plugin/plugin.json   Claude Code manifest
.codex-plugin/plugin.json    Codex manifest — same skills/ and hooks/, nothing copied
hooks/hooks.json             one file, both worlds; Claude Code ignores SubagentStart
hooks/briefing-preload       the hook (Python 3, stdlib only, executable)
hooks/briefing-marketplace-notice   SessionStart notice about the shared marketplace
bin/briefing-doctor          symlink to the hook; Claude Code puts bin/ on PATH
skills/briefing/SKILL.md     ships with the plugin — how to author briefing-aware agents
examples/                    example agent + minimal skill
tests/test_briefing.py       Claude Code path
tests/test_briefing_codex.py Codex path
tests/test_briefing_doctor.py  doctor CLI and SessionStart pre-flight
```

**One `hooks.json` serves both**, verified rather than assumed: Claude Code reads
the file with a `SubagentStart` block without complaint (a control test with
deliberately broken JSON shows it *does* report `Failed to load hooks` when
something is genuinely wrong). Codex resolves `${CLAUDE_PLUGIN_ROOT}` too, for
compatibility. Splitting the file would mean two places to keep in sync for no
gain.

## Hook contract

**Claude Code — stdin:**

```json
{
  "cwd": "/abs/path", "tool_name": "Agent",
  "tool_input": { "subagent_type": "...", "prompt": "...", "model": "sonnet" }
}
```

stdout: `hookSpecificOutput.updatedInput` with the rewritten prompt, or
`permissionDecision: "deny"` with a reason, or nothing at all.

**Codex — stdin:**

```json
{
  "hook_event_name": "SubagentStart", "cwd": "/abs/path",
  "agent_type": "my_agent", "agent_id": "...", "turn_id": "..."
}
```

stdout: `hookSpecificOutput.additionalContext`, optionally alongside a top-level
`systemMessage` for the human. No-op is exit 0 with empty stdout, same as always.

Both spawn paths put a one-line audit into `systemMessage` on success
(`briefing: agent ← a, b (N kB)`), plus any warnings on further lines. Skills
are injected as `<skill name="...">` elements, frontmatter stripped.

**SessionStart — stdin (both harnesses):**

```json
{
  "hook_event_name": "SessionStart", "cwd": "/abs/path", "session_id": "...",
  "source": "startup", "transcript_path": "/home/u/.codex/sessions/..."
}
```

stdout: a top-level `systemMessage` listing declarations that would fail, or
nothing. Never `hookSpecificOutput` — on SessionStart that would become model
context. The harness is told apart by `transcript_path` (`/.codex/` or
`$CODEX_HOME` vs `/.claude/`); when that is inconclusive, both are checked.
Runs on `startup` and `resume` only, so compaction does not repeat it.

The hook **must** be idempotent and side-effect-free. It only reads files.

## Skill resolution

Each side searches exactly where its own harness looks — that is the whole rule,
and it is why bare names stay portable.

**Claude Code**: `<cwd>/.claude/skills` → `~/.claude/skills` →
`~/.claude/plugins/cache/*/skills` → `~/.claude/plugins/cache/*/*/skills`.

**Codex**: for each directory from `<cwd>` up to the project root (nearest
`.git`, Codex's default `project_root_markers`), nearest first: `.codex/skills`
→ `.agents/skills`; then `$CODEX_HOME/skills` → `~/.agents/skills` →
`$CODEX_HOME/skills/.system` → `/etc/codex/skills`. `CODEX_HOME` defaults to
`~/.codex` and also locates the plugin cache.

## Agent lookup on Codex

Codex does not find agents by file name. Each config layer — every `.codex/`
from the project root down to `<cwd>`, then `$CODEX_HOME`, then `/etc/codex` —
contributes roles declared in its `config.toml` (`[agents.<name>] config_file`,
relative to that file) and every `*.toml` below its `agents/`, recursively,
named by their `name` field. `find_codex_agent` walks the same layers, nearest
first, and within a layer prefers the declared role, as Codex does.
`<name>.toml` is only a fast path, and is skipped if its `name` says otherwise.
Sources: `codex-rs/agent-roles/src/{loader,discovery}.rs`.

`plugin:skill` works in both. Codex uses the same syntax — observed as
`briefing:briefing` in `codex debug prompt-input`, though its documentation does
not mention namespacing — and installs plugins under
`$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/`.

**Codex's `[[skills.config]]` is not ours.** It means "visible to this agent",
not "preloaded". Reading it as a briefing declaration would remove the user's
ability to express one without the other, and would silently inject context for
anyone who only wanted a skill enabled. `tests/test_briefing_codex.py` pins this.

## Style rules

- Python 3.8+ for the shared and Claude Code paths, stdlib only, no pip deps.
- The hook runs on every spawn. Keep it fast, keep imports light, and keep
  version-specific imports function-local.
- Every code path exits 0 cleanly on bad input. **Never block a spawn unless a
  declared skill is genuinely missing.** Someone else's malformed agent file is
  not our bug.
- Tests run with `python3 -m unittest discover tests`, stdlib only, driving the
  hook as a subprocess with a sandboxed `HOME` and `cwd`.
- Conventional commits, `--signoff`.

## Verifying against a real Codex

Unit tests cover "given this payload, emit that context". They cannot show that
Codex actually calls the hook and uses its output. That takes a live run, and the
test must be built so it cannot pass for the wrong reason:

- **The secret must exist only inside the skill body.** Asking an agent "is
  string X in your context?" puts X in the question — the model can answer yes
  without any hook running. Ask it to *produce* something it could only know from
  the skill.
- **Run the control.** The same agent without the `[briefing]` block must fail to
  produce it. Skills are listed to every agent by name and description, so a
  tempting description invites the agent to just go read the file itself — which
  looks exactly like success.
- **Make sure Codex loaded the project at all.** Project `.codex/` layers —
  agents included — load only for trusted projects, and trust on an ancestor
  such as `$HOME` does not cover a separate git repo below it. Without it Codex
  offers no roles and spawns `default`, which looks exactly like a broken
  briefing. `--dangerously-bypass-hook-trust` does not help here. Grant it per
  run with `-c 'projects={"<abs path>"={trust_level="trusted"}}'`; the dotted
  form `projects."<path>".trust_level=...` is silently ignored. The marker's
  `agent_type` tells the two apart.
- **Never copy `auth.json` into a second `CODEX_HOME`.** Use the real one and
  pass everything else via `-c`. Two homes sharing one refresh token can end
  the login.
- **`codex exec` does not print hook messages.** Codex turns a hook's
  `systemMessage` into a `Warning` output entry, which the TUI shows and
  `exec` (with or without `--json`) drops. To see what a hook returned, wrap
  the installed copy in a script that logs stdin and stdout.
- **Instrument the installed copy, not the repo.** Appending a marker that logs
  `hook_event_name` to the cached plugin under `~/.codex/plugins/cache/` proves
  which events actually arrive.

The agent lookup was verified the same way on Codex 0.153.4 — a role whose file
name differs from its `name` inside `agents/team/`, the same role spawned from a
subdirectory of the repo, and a role declared via `config_file` all answered
with the phrase; the control answered `UNKNOWN`.

0.4.0 was verified in both harnesses: under Codex the declaring agent answered
with the phrase and named the `<skill>` element it arrived in, and the logged
`SessionStart` exchange showed the pre-flight warning for a broken agent; under
Claude Code (`claude -p --plugin-dir` with the installed copy disabled via
`--settings '{"enabledPlugins":{"briefing@getty":false}}'`) an agent found by
`name` in a subdirectory answered with the phrase without a tool call, the
control answered `UNKNOWN`, and both the audit line and the pre-flight warning
arrived as system messages.

The original implementation was verified like this: the declaring agent answered
with the phrase, the identical non-declaring agent answered "unknown", and the
marker recorded `SubagentStart` in both runs.

## What this plugin is NOT

- Not a skill loader for the main session — only for subagent spawns.
- Not a prompt rewriter for arbitrary tools.
- Not a replacement for skill invocation during a run.
- Not opinionated about which skills an agent should declare.
