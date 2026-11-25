# briefing

> **Superseded.** Claude Code now preloads an agent's skills natively.

briefing used to put the full text of an agent's declared skills into a subagent's
context at spawn time. Claude Code does that itself now: a top-level `skills:` list in
the agent's frontmatter loads each skill in full when the subagent starts, including
`plugin:skill` names. This last version of the plugin only prints one message at session
start and does nothing else. It is for everyone who still has briefing installed.

## What to do

Before (briefing format):

```yaml
---
name: my-agent
briefing:
  skills:
    - perl-core
    - superpowers:test-driven-development
---
```

After (native):

```yaml
---
name: my-agent
skills:
  - perl-core
  - superpowers:test-driven-development
---
```

Then remove the plugin:

```
/plugin uninstall briefing
```

Documentation: https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents

## License

Artistic License 2.0, see [LICENSE](LICENSE).
