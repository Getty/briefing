<!-- ack: shape=project manager=none board=karr committer=release-manager outside_input=on headless=off -->
# briefing: project rules

## Lanes

| Work | Agent |
|---|---|
| Read code and history, explain relationships | `briefing-scout` |
| `hooks/`, `.claude-plugin/`, distribution configuration | `briefing-worker` |
| `t/` | `briefing-test-writer` |
| Review completed work and run checks independently | `briefing-reviewer` |
| Authorized commits, `Changes`, release checks | `briefing-release-manager` |

Hook configuration and plugin manifests are behavior-relevant: changes belong to the
worker, even when they are JSON. The main session owns coordination, plain prose
documentation and team configuration.

## Checks and commits

`prove t` checks the hook. The release manager alone makes authorized commits and
closes their cards; leave other sessions' working-tree changes untouched.

## Board

The existing board lives in `refs/karr/*`; `karr list --compact` shows open work.
Karr mutations synchronize with `origin`: obtain authorization for that exchange
before the first write.

## With superpowers

Work in the existing checkout; use isolation only when explicitly chosen.
Code tasks go to the worker/test-writer, then the reviewer checks the uncommitted
diff; the release manager makes an authorized commit afterwards.

## Hazards

- The hook command stays dependency-free: `echo` with embedded JSON, valid in POSIX
  shells and Git Bash.
- `Changes` is the single changelog; release conventions belong only to the release manager.
