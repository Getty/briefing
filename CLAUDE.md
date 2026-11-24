# briefing

> Superseded: Claude Code preloads agent skills natively.

The last version of the plugin. Its only job is a SessionStart message that tells
users to move to a top-level `skills:` list in the agent's frontmatter and to run
`/plugin uninstall briefing`. Usage: [README.md](README.md).

## Repository language

Write repository content in **English**.

## Before working

- **Hook, manifests, test:** read [briefing-core](.claude/skills/briefing-core/SKILL.md).
- **Ownership and verification:** [.claude/rules/briefing-rules.md](.claude/rules/briefing-rules.md).

## The agent team

- `briefing-scout`: reads and reports; changes nothing.
- `briefing-worker`: maintains the hook, manifests and skill; never commits.
- `briefing-test-writer`: writes the test; leaves implementation to the worker.
- `briefing-reviewer`: reviews changes and runs tests; changes no files.
- `briefing-release-manager`: owns authorized commits, `Changes` and release checks.

Work belongs on the existing karr board (`karr list --compact`). Newly created agents
may require a fresh Claude Code session.

## Shared rules and skills

`.claude/skilletor.json` declares sources and the `getty-cpan-dist` bundle.
`skilletor sync --scope project` installs shared files; edit managed copies at their
source. Project agents, `briefing-core`, settings and skilletor configuration are
tracked; installed rules/skills, the lock and local settings are not.
