---
name: briefing-core
description: Use when changing the briefing farewell plugin - its SessionStart hook, manifests, README or the hook test.
---

# briefing core

briefing is a farewell plugin. Claude Code preloads agent skills natively through a
top-level `skills:` list in an agent's frontmatter, so the plugin does one thing: at
SessionStart it shows a message that names the switch and the uninstall command.

## Contract

- `hooks/hooks.json` holds exactly one `SessionStart` command hook: `echo` of JSON with
  `systemMessage`. No Python, binary, download or `${CLAUDE_PLUGIN_ROOT}` file, so it runs
  in POSIX shells and Git Bash on Windows.
- No `SubagentStart` and no `PreToolUse` hook: the hook never blocks or rewrites anything.
- The message carries the URL
  `https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents`.
- `.claude-plugin/plugin.json` carries no `version`; the commit is the version.

## Check

`prove t` runs the hook command and checks the message and URL. For the live view, run
`claude -p "say ok" --plugin-dir <checkout> --setting-sources project --output-format stream-json --verbose`
in a scratch project and read the `SessionStart` `hook_response`.
