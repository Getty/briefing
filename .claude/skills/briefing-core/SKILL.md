---
name: briefing-core
description: Use when working in briefing — changing or reviewing its Perl library/CLI, distribution, hooks, skill resolution, Doctor, SessionStart, tests, or Windows launcher.
---

# Developing briefing

`briefing` fully preloads declared skills when a subagent starts.
Product skill: `skills/briefing/SKILL.md`; this skill covers development,
not use of the plugin. Product overview: `README.md` in the repository root.

## Mandatory boundaries

- The retained Python plugin starters and reference hooks remain Python 3.8+
  standard-library-only. Version-dependent imports stay function-local; the hook
  runs on every spawn. This constraint does not apply to the Perl library and CLI.
- `App::Briefing` and `bin/briefing` are the implemented source core and CLI; they
  never invoke Python. Plugin manifests still start the Python compatibility path
  until a separately verified binary cutover.
- `hooks/briefing-preload` remains read-only, idempotent, and free of side effects.
  Invalid input exits cleanly with exit 0; only a genuinely missing, explicitly
  declared skill may deny a Claude Code spawn. Doctor is a CLI: failed checks exit 1.
- `Briefing` resolves a declaration once; spawn, pre-flight, and Doctor use the
  same result, never separate resolvers.
- Both harnesses inject through `additionalContext` at `SubagentStart`.
  Claude Code's `PreToolUse` is a guard only: `deny` or empty, never `updatedInput`
  or prompt rewriting; otherwise auto mode can deny the modified call.
- Missing skills never produce a partial briefing. Neither harness can stop the
  spawn at `SubagentStart`: provide only an abort instruction, even if a skill
  disappears after the Claude Code guard.
- Only `SKILL.md` is injected, with frontmatter removed. The absolute `dir` on
  the `<skill>` element makes `references/` and `scripts/` discoverable; do not preload them.
- One `hooks/hooks.json` serves both harnesses. Codex requires
  `additionalContextLimit: 0`, otherwise long context becomes a preview rather than full text.
- Resolution follows the respective harness. Claude Code plugin caches are not
  installation indexes; disabled plugins provide no skills.
- Main sessions, arbitrary tool prompts, and later skill invocations remain
  outside this plugin. The project decides which skills an agent declares.

## Read selectively before changes

| Change | Reference |
|---|---|
| Events, JSON output, error policy, pre-flight | [Hook contract](references/hook-contract.md) |
| Find agents, parse declarations, resolve skills or plugins | [Resolution](references/resolution.md) |
| Prove harness integration or investigate “briefing does nothing” | [Live verification](references/live-verification.md) |

Check the effective contract against `hooks/hooks.json` and `hooks/briefing-preload` in
the version that is actually loaded: checkout, installed cache copy, and harness
version can differ. Legacy-harness caveat: [Hook contract](references/hook-contract.md).

## Perl source distribution

The root `App-Briefing` distribution provides the reusable library and the thin
`briefing` CLI. Read the POD in `lib/App/Briefing.pm` and
`lib/App/Briefing/CLI.pm`, the source-CLI section of `README.md`, and
`docs/perl-direction.md` instead of duplicating their public interfaces here.
Only `bin/briefing` is installed by the distribution; the old plugin doctor
launchers stay in the checkout for the transitional Python route.

## Checks

From the repository root:

```sh
export PERL5LIB="$PWD/.build-deps/lib/perl5${PERL5LIB:+:$PERL5LIB}"
prove -lr t
python3 -m py_compile hooks/briefing-preload hooks/briefing-marketplace-notice
sh -n bin/briefing-doctor
python3 -m unittest discover tests -v
BRIEFING_TEST_CLI='["/absolute/path/to/perl","-I/absolute/path/to/briefing/lib","/absolute/path/to/briefing/bin/briefing"]' \
  python3 -m unittest discover tests -v
python3 hooks/briefing-preload doctor --cwd . --harness both
dzil build
dzil test
```

The first unittest run checks the retained Python reference hooks. The second
uses Python only as the contract-test driver and targets the Perl CLI through a
JSON argv array; every entry must be an absolute path. The new CLI itself does
not run Python. Dist::Zilla gathers tracked or staged files, so a new source file
must be visible to Git before `dzil build` can package it.

The unittest suite starts hooks as subprocesses with isolated `HOME` and `cwd`.
`tests/test_briefing_codex.py` forces the Python 3.10 fallback through a
`tomllib.py` that fails at import: a run only with real `tomllib` does not prove
that path. CI matrix: `.github/workflows/test.yml`.

The local Doctor checks the checkout, while `briefing-doctor` on the plugin PATH
checks the installed version; they can differ. Doctor and simulated hook payloads
prove resolution, not actual integration by the harness.

## Windows

The Perl source library routes Windows filesystem access through
`App::Briefing::Filesystem`, but that path still requires native Windows
verification. Do not infer Windows or macOS support from Linux source or package
tests, and do not describe the source distribution as standalone binary delivery.

`bin/briefing-doctor` is a shell wrapper, not a symlink: POSIX starts Python
through it; Windows uses the `# winlaunch:` directive through the adjacent `.exe`.
The `.exe` files under `hooks/` and `bin/` are launchers and still require Python;
they are not standalone packages with an embedded interpreter.
For launcher or hook invocation changes, read `winlaunch/README.md`, the header of
`winlaunch/winlaunch.c`, and `.cicd/python+3.12+test.winlaunch.sh`.
The shared launcher source is in the windows-developer hub according to the README.
Linux unittest and a reproducible build do not replace a native Windows run.
Every report names the platforms actually checked and the tests omitted.
