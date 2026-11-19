# briefing

> **Programmatic briefing beats prompt stuffing.**

briefing is a plugin for **Claude Code** and **Codex**. A subagent declares
the skills it needs; when it is spawned, briefing puts the full text of those
skills into its context, so it starts its first turn already briefed. No
"MANDATORY: load skill X first" in the agent's prompt, and no silent skip: if a
declared skill cannot be found, Claude Code refuses the spawn and a Codex agent
is told to stop and report instead of working unbriefed.

## Why

Two harness decisions that are each correct leave a gap together.

**Subagents start fresh.** A subagent gets its own context window; that is the
point of it. Whatever the main agent had read, the subagent has not.

**Skills load lazily.** What sits in the context is a list: each skill's name,
description and location. The instructions themselves are read only once the
agent decides it needs them.

So an agent spawned *because* it needs particular expertise must still find
that expertise on its own, from a one-line description, in the middle of a
task. Sometimes it does. Sometimes it decides the description does not match
closely enough and does the work uninformed, and nothing in the result says so.

Codex sharpens this. Its own system prompt tells the main agent:

> *"Do not delegate reading, summarizing, or interpreting skill instructions to
> a subagent."*

So the subagent is not supposed to read the skill, and nothing hands it over
either.

The usual workaround is an order in the agent's prompt: *"You MUST invoke the
code-style skill before doing anything."* That is prompt stuffing. It competes
with everything else in the prompt, repeats what the skill already says, and
fails quietly. briefing replaces it with a mechanism: at spawn time a hook reads
the agent's declaration, resolves each skill and hands its text to the agent.

## Install

briefing runs its hooks with Python 3 today; see
[What it needs to run](#what-it-needs-to-run) before you install.

### Claude Code

From the shared marketplace that carries every Getty plugin:

```
/plugin marketplace add Getty/marketplace
/plugin install briefing@getty
```

This repository is also a one-plugin marketplace of its own. It serves the
installs from before the shared marketplace existed and stays maintained, so
there is nothing to migrate:

```
/plugin marketplace add Getty/briefing
/plugin install briefing@briefing
```

Both install the same plugin from this repository, and both keep receiving
updates. The plugin's version is the commit, so every change on `main` reaches
installs that update from their marketplace. An install from `Getty/briefing`
hears about the shared marketplace once, at a session start, and never again.

### Codex

The shared marketplace is the only route for Codex:

```
codex plugin marketplace add Getty/marketplace
codex plugin add briefing@getty
```

Codex then needs two trust decisions:

- **Hook trust.** Codex runs a plugin's hooks only after you trust them. Until
  then briefing is installed but silent: no error, no briefing, agents simply
  start unbriefed. If skills are not arriving, look for the trust prompt first.
  Non-interactive runs (`codex exec`) cannot grant this trust; grant it once
  in an interactive session. A release that changes the hooks asks again; this
  one does, because Codex now reads its own hook file.
- **Project trust.** Codex loads a project's own agents only in a trusted
  project. In an untrusted one it spawns its `default` agent instead, and that
  agent declares nothing.

To update, run `codex plugin add briefing@getty` again.
`codex plugin marketplace upgrade getty` refreshes only the catalog, and the
catalog points at this repository's `main` without a version, so it does not
change when briefing does.

### Your first briefed agent

The repository ships a demo agent and a demo skill whose body holds a phrase
that is not in the agent's prompt. From a clone
(`git clone https://github.com/Getty/briefing`), copy both into a project:

```sh
mkdir -p /your/project/.claude/agents /your/project/.claude/skills
cp examples/agents/briefing-demo.md       /your/project/.claude/agents/
cp -r examples/skills/briefing-demo-skill /your/project/.claude/skills/
```

Claude Code reads new agent files only when a session starts, so start a new
one in that project and ask it to spawn the `briefing-demo` agent. Its prompt
only asks it to say which skills it can already see, and tells it not to call
the Skill tool; the phrase **PROGRAMMATIC BRIEFING BEATS PROMPT STUFFING**, and
the request to echo it, are in the skill, not in the prompt. A briefed agent names the skill
and echoes the phrase without reading anything first. The demo agent may use
Read and Bash, so an answer that came after reading the skill's file proves
nothing.

For Codex, put the skill where Codex looks and declare it in a TOML agent:

```sh
mkdir -p /your/project/.agents/skills /your/project/.codex/agents
cp -r examples/skills/briefing-demo-skill /your/project/.agents/skills/
cat > /your/project/.codex/agents/briefing-demo.toml <<'EOF'
name = "briefing_demo"
description = "Demo agent: proves that briefing pre-loads its declared skills."
# briefing: skills = ["briefing-demo-skill"]
developer_instructions = """
Say which skills you can already see in your context, then stop.
"""
EOF
```

Then ask Codex, in a trusted project, to spawn `briefing_demo`.

## Everyday use

### Declaring skills

**Claude Code:** under `briefing:` in the agent's frontmatter, as a block list
or on one line (`skills: [code-style, review-checklist]`):

```yaml
---
name: reviewer
description: Reviews a change and runs the tests
briefing:
  skills:
    - code-style
    - review-checklist
    - superpowers:brainstorming
---

You are the reviewer. Review the change you are given.
```

**Codex:** as a `# briefing:` comment line in the agent's TOML file:

```toml
name = "reviewer"
description = "Reviews a change and runs the tests"
# briefing: skills = ["code-style", "review-checklist", "superpowers:brainstorming"]
developer_instructions = """
You are the reviewer. Review the change you are given.
"""
```

It is a comment because it has to be. Codex reads agent files strictly and
drops the whole agent over a key it does not know: a `[briefing]` table, the
form used up to briefing 0.3.0, makes Codex 0.153 ignore the agent with
``unknown field `briefing` ``. A comment is invisible to Codex and to every
other TOML parser. Keep the declaration on one line, outside any multi-line
string; a matching line inside `developer_instructions` is prose and is not
read. briefing still reads an old `[briefing]` table where Codex lets the
agent spawn at all, and tells you to replace it.

Everything sits under a `briefing` name so nothing collides with keys the
harness owns. Two look similar and are left alone on purpose: a top-level
`skills:` in Claude Code frontmatter, and Codex's `[[skills.config]]`. The
latter means *"this skill is visible to the agent"*, which is not the same as
*"preloaded"*.

### How names resolve

Each harness is searched where the harness itself looks, nearest first.

**Claude Code**

- A bare name (`code-style`): the project's `.claude/skills/code-style/SKILL.md`,
  then `~/.claude/skills/code-style/SKILL.md`, then the skills of installed
  plugins.
- A namespaced name (`superpowers:brainstorming`): only that plugin's skills.
- A plugin counts only when it is installed and switched on in
  `enabledPlugins`, as for Claude Code itself; its skills are `skills/<name>/`
  plus whatever its `plugin.json` lists under `skills`.
- Agents are the `.md` files under the project's `.claude/agents/`, then
  `~/.claude/agents/`, subdirectories included, matched by their `name`.

**Codex**

- A bare name: `.codex/skills/` and `.agents/skills/` in the working directory
  and in each parent up to the repository root (the nearest `.git`), then
  `$CODEX_HOME/skills/`, `~/.agents/skills/`, `$CODEX_HOME/skills/.system/` and
  `/etc/codex/skills/`. `CODEX_HOME` defaults to `~/.codex`. A bare name does
  not reach into plugins.
- A namespaced name: that plugin in Codex's plugin cache,
  `$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/skills/`.
- Agents: in the `.codex/` of the working directory and each parent up to the
  repository root, then `$CODEX_HOME`, then `/etc/codex`. Within one of them
  `[agents.<name>] config_file` wins; otherwise any `*.toml` under `agents/`
  whose `name` matches.

### What the agent receives

| | Claude Code | Codex |
|---|---|---|
| Hook | `SubagentStart`, plus `PreToolUse` on `Agent` as a guard | `SubagentStart` |
| Agent definition | `.claude/agents/*.md`, by `name` | `.codex/agents/*.toml`, by `name` |
| Declaration | `briefing.skills` in the frontmatter | `# briefing: skills = [...]` comment |
| Delivery | `additionalContext` | `additionalContext` |
| A skill is missing | the spawn is **denied** | the agent starts and is told to abort |

The last row is not a choice. A `SubagentStart` hook cannot stop a spawn;
Codex parses `continue: false` for compatibility and ignores it. So under Codex
the nearest honest equivalent is an agent that starts and refuses. It gets no
skill text at all, not even for the skills that did resolve, but this:

```
# Briefing — FAILED

The skills this agent declares could not be loaded: kubernetes-rest.

You are NOT briefed for this task. Do NOT attempt it and do NOT
improvise a substitute. Report this exact failure to whoever
delegated to you, and stop.
```

Claude Code has a chance before the spawn: the `PreToolUse` hook on the
`Agent` tool checks the declaration and denies the call if a skill is missing,
with the reason
`briefing: agent 'backend' references unknown skill(s): kubernetes-rest`.
If a skill disappears between that check and the spawn, the agent gets the
abort instruction above, as under Codex.

The guard never changes the call; the skills arrive at `SubagentStart`. That
is what lets briefing work under `--permission-mode auto`: auto mode reviews a
tool call before hooks run and refuses one whose input a hook changed
afterwards (*"a hook changed this call's input after auto mode reviewed it"*).
Up to 0.5.x briefing rewrote the agent's prompt in `PreToolUse`, so in auto
mode a briefed spawn could be refused. This needs a Claude Code whose
`SubagentStart` hooks can add context; 2.1.318 does. Older versions start the
agent unbriefed, without an error.

A briefing opens with a short header that tells the agent the skills are
already loaded (under Claude Code not to call the Skill tool for them, under
Codex not to go looking for their `SKILL.md` files), then holds each skill in
its own element, so the agent can tell where one ends and the next begins:

```
<skill name="code-style" dir="/home/you/dev/shop/.claude/skills/code-style">
…the SKILL.md body, frontmatter stripped…
</skill>
```

Only `SKILL.md` is included. A skill's `references/` and `scripts/` stay on
disk and load on demand, as they do natively; `dir` tells the agent where they
are. A briefed skill does not pull in further skills.

### The audit line

Every successful briefing leaves one line for you, not for the model:

```
briefing: reviewer ← code-style, review-checklist (13 kB)
```

Above 64 kB of skill text a second line says so, and the spawn still goes
ahead, because that much context is rarely what anyone meant:

```
briefing: agent 'wide' is briefed with 69 kB of skill text (over 64 kB) — consider declaring fewer or smaller skills.
```

Codex shows these lines in its TUI; `codex exec` drops them. Claude Code
2.1.318 shows no `SubagentStart` message in `claude -p` output.

### Checking before anything spawns

A broken declaration should not cost a spawn to discover. When a session
starts or resumes, briefing checks every briefing-aware agent of the harness
you are in and names the ones that would fail; a healthy project hears nothing:

```
briefing: declared skills that will not work — run briefing-doctor for details
  Claude Code agent 'backend': unknown skill(s): kubernetes-rest
```

For the full picture, run the doctor. Claude Code puts the plugin's `bin/` on
the `PATH` of its Bash tool, so Claude can run it for you:

```sh
briefing-doctor                                # this project, both harnesses
briefing-doctor --cwd ~/dev/shop --harness codex
```

```
briefing doctor — /home/you/dev/shop

Claude Code
  FAIL  backend  (.claude/agents/backend.md)
        code-style, kubernetes-rest  (9 kB)
        → unknown skill(s): kubernetes-rest
  ok    reviewer  (.claude/agents/reviewer.md)
        code-style, review-checklist  (13 kB)

Codex
  ok    reviewer  (.codex/agents/reviewer.toml)
        code-style, review-checklist  (13 kB)
```

It exits 1 if any spawn would fail (an unknown skill, or a Codex agent still
carrying a `[briefing]` table), so it can guard CI. Above 64 kB an agent shows
as `WARN`, which does not fail. `briefing doctor` takes the same options and
prints the same report. On Windows, `bin/briefing-doctor.exe` starts the same
doctor, so `briefing-doctor` also works from PowerShell and cmd.

Codex cannot put a plugin's programs on `PATH`, so there run the plugin's own
launcher from Codex's plugin cache (under `$CODEX_HOME` if you set it):

```sh
~/.codex/plugins/cache/getty/briefing/<version>/bin/briefing doctor
```

On Windows the launcher is `bin\briefing.exe`; in cmd:

```bat
%USERPROFILE%\.codex\plugins\cache\getty\briefing\<version>\bin\briefing.exe doctor
```

`ls ~/.codex/plugins/cache/getty/briefing/` (on Windows
`dir %USERPROFILE%\.codex\plugins\cache\getty\briefing`) shows the installed
version.

For tools there is `briefing doctor --tsv`: one tab-separated line per finding
about the project's Claude Code team (what, `ok`, `missing` or `warn`, name,
text), exit 1 when any line is `missing`. Besides the declared skills it checks
the agents' frontmatter, what the hooks answer for them, and the plugin
settings in `.claude/settings.json`. Today this form needs Perl; see
[What it needs to run](#what-it-needs-to-run).

### Writing agents with the briefing skill

The plugin ships a skill on writing agents for briefing: both declaration
formats, why an agent's prompt should not restate skills that are already
injected, and a recipe for migrating prompt-stuffed agents. Claude Code lists
it as `briefing:briefing`; type `/briefing:briefing`, or let the agent pick it
up when it works on agent files.

## Status

### What ships

The plugin for Claude Code and Codex: the spawn-time briefing, the Claude Code
guard, the session-start check, the doctor, the authoring skill and the
one-time note for installs from the legacy marketplace. Its hooks run through
the plugin's launcher, `bin/briefing` (on Windows `bin/briefing.exe`, which
starts the plugin's own `bin/briefing-bootstrap.exe`), and with this version
the launcher runs the Python hook.

### The standalone binary is off in this version

The launcher can also run briefing as a self-contained binary that needs
neither Python nor Perl. That path switches on only in a plugin version that
carries `bin/briefing-binaries.sha256`, the SHA-256 checksums of one release's
binaries. This version does not carry it, so nothing is downloaded and
everything runs as described under [What it needs to run](#what-it-needs-to-run).
Once a version pins binaries:

- **Platforms:** Linux x86_64 and arm64, macOS x86_64 and arm64, Windows
  x86_64. Every other platform keeps running as today. Each release is built
  and smoke-tested on GitHub's hosted runners of the day and records which
  ones; that recorded set is what is supported. Older operating-system
  versions may work but are not promised.
- **Download:** once per version, and only by the `SessionStart` hook, which
  may then take up to 90 seconds. It comes from this repository's GitHub
  release over HTTPS, at most 256 MiB. Agent spawns and `briefing doctor`
  never download. After a failed attempt Linux and macOS wait 15 minutes
  before trying again; Windows tries again at the next session start. After
  the first download the binary works offline.
- **Trust:** a binary runs only if its SHA-256 matches the checksum in the
  installed plugin, checked after the download and again before every start.
  The release's own `SHA256SUMS` is never trusted at run time. Repository and
  release permissions are the trust root; there are no signatures or
  attestations.
- **Cache:** `<config>/briefing/bin/<version>/<first 16 hex digits of the
  checksum>/briefing` (`briefing.exe` on Windows), with the binary's unpacked
  runtime in `par/` beside it. `<config>` is `CLAUDE_CONFIG_DIR` when it is
  set and not empty, else `~/.claude` (Windows: `%USERPROFILE%\.claude`). A
  `CLAUDE_CONFIG_DIR` that is not an absolute path does not fall back to
  `~/.claude`: it keeps the binary from being used, and the plugin runs as in
  the first table under [What it needs to run](#what-it-needs-to-run). The
  cache is private to the user; old versions are not removed.

### What it needs to run

With this version, on every platform:

| Part | Linux and macOS | Windows |
|---|---|---|
| Hooks: the guard, the briefing, the session-start check | Python 3 on `PATH`: `python3`, else `python` | Python 3 on `PATH`: `python3.exe`, else `python.exe`, else `py.exe -3`, run in UTF-8 mode; the Microsoft Store stubs under `WindowsApps` do not count |
| The one-time marketplace note | the same Python, else no note | the same |
| `briefing-doctor` | `python3` | the same Python as the hooks |
| `briefing doctor` | the same Python as the hooks, else Perl as below | the same |
| `briefing doctor --tsv`, `--version`, `--help`, `notice` | a `perl` on `PATH` that has the modules in `cpanfile`: Moo, namespace::clean, Path::Tiny, JSON::MaybeXS, TOML::Tiny | `perl.exe` on `PATH`, likewise, plus Win32 and Win32::LongPath |
| The launcher itself | `sh` | nothing; no Git Bash |

**Without Python, briefing does not brief.** The guard, the briefing and the
session-start check each print one warning,
`briefing: no binary (…) and no fallback (…).`, and exit 0, so the spawn goes
ahead without its skills and the Claude Code guard denies nothing. The
marketplace note stays silent. A `briefing` command that finds nothing the
table names for it prints the same message on standard error and exits 1.

Once a version pins binaries, on the five platforms above:

| Part | Linux and macOS | Windows |
|---|---|---|
| Every start of the cached binary: hooks, the marketplace note, every `briefing` command | `sh`, and `sha256sum` (Linux) or `openssl` (macOS; not `shasum`, which needs Perl): the launcher checks the binary against its checksum before each start | nothing beyond the plugin's own files: `bin/briefing.exe` starts `bin/briefing-bootstrap.exe`, which uses only Windows' own libraries and checks the binary with BCrypt before each start; no PowerShell, Python or Perl |
| The first download, at a session start | the same, plus `curl` or `wget` | the same; the bootstrap downloads with WinHTTP |
| `briefing-doctor` | still `python3` | still Python |

On Linux and macOS, without its checking tool the launcher refuses the cached
binary, at every start. Then, and until a verified binary is in the cache,
everything runs as in the first table.

### What has been shown

- **Claude Code 2.1.318, live (`claude -p` in auto mode), through the Python
  hook:** an agent that declared a skill answered with a phrase found only in
  that skill, without loading anything; the same agent without the
  declaration could not; an agent declaring an unknown skill was denied; the
  `Agent` prompt arrived unchanged.
- **Claude Code on Linux x86_64, live, through a test build of the binary**
  (not a release), pinned and served locally: the spawn hooks ran through the
  binary, and the skill arrived.
- **Codex 0.153.4, live, before this version moved Codex to its own hook
  file:** the declaring agent produced the phrase, the control did not; also
  with the agent file under a different name in a subdirectory, from a
  repository subdirectory, and through `config_file`.
- **Automated tests:** the hook contracts pass against the Python hook and
  against the Perl command on Linux. In CI the Perl distribution installs,
  passes its own tests and then the same contracts as an installed command on
  Linux (Perl 5.20 and 5.40) and macOS (Intel, Perl 5.40). On Windows
  (Strawberry Perl 5.40) its own tests pass except two, both for the
  marketplace note; because those fail, the distribution is not installed
  there and the contracts do not run. Before this version's change to the
  marketplace note, all of it passed on Windows as well.
- **Binaries, from test builds:** all five build and pass a smoke test
  without Perl or Python on GitHub-hosted runners (Linux x86_64 and arm64,
  macOS Intel and Apple silicon, Windows). The full path from the launcher to
  the binary passes on both Linux and both macOS targets, and on Windows from
  `bin/briefing.exe` through the bootstrap to the binary, apart from the
  marketplace note (below).
- **The Windows bootstrap, in CI:** the committed `bin/briefing-bootstrap.exe`
  equals a fresh build byte for byte and passes its native test suite on
  Windows, apart from its marketplace-note tests.

Not yet shown:

- the marketplace note on Windows, from the Perl command as well as through
  the bootstrap and the binary: its tests fail there today;
- a live session on macOS or Windows, and Codex on Windows at all;
- Codex live with this version's hook file;
- the first download from a real release over the network (the tests serve
  local files);
- whether Claude Code's interactive TUI shows the audit line.

### Known limits

- Claude Code versions whose `SubagentStart` hooks cannot add context start
  the agent unbriefed, without an error; 2.1.318 is the version tested, not
  the oldest that works.
- On Windows, pass a directory whose path has characters outside the ANSI code
  page by changing into it, not through `--cwd`: the Perl command and the
  binary receive command-line arguments in the ANSI code page. Today this
  affects the doctor only where it runs on Perl (`--tsv`, or no Python); once
  a version pins binaries, every `briefing doctor`. Hook payloads arrive as
  UTF-8 and are not affected.
- Once binaries are pinned: a configuration directory (`~/.claude` or
  `CLAUDE_CONFIG_DIR`) that is, or lies below, a symbolic link (on Windows, a
  reparse point) keeps the binary from being used, and the plugin runs as
  today.

## Develop

briefing has one core: **App::Briefing**, a Perl library, and its command
**briefing** (`script/briefing`), released together as the CPAN distribution
App-Briefing. It is not on CPAN yet. The standalone binaries are that same
command, packed. The Python hook `hooks/briefing-preload` is the reference
implementation and, wherever no verified binary is cached, the fallback; both
are held to the same contract tests. Background:
[the App::Briefing direction](docs/perl-direction.md).

The library needs Perl 5.20 or newer and the modules in `cpanfile`; on Windows
it uses `Win32::LongPath` for Unicode and long paths. From a checkout:

```sh
cpanm --installdeps .                                   # the modules in cpanfile
perl -Ilib script/briefing doctor --cwd . --harness both
```

To keep the modules inside the checkout, install them with
`cpanm -L .build-deps --installdeps .` and
`export PERL5LIB="$PWD/.build-deps/lib/perl5${PERL5LIB:+:$PERL5LIB}"`.

Tests:

```sh
prove -lr t                             # the Perl library and command
python3 -m unittest discover tests -v   # the hook contracts, against the Python hook
```

To hold the Perl command to the same contracts, set `BRIEFING_TEST_CLI` to a
JSON array with the absolute Perl path, `-I<checkout>/lib` and
`<checkout>/script/briefing`:

```sh
BRIEFING_TEST_CLI='["/usr/bin/perl","-I/absolute/checkout/lib","/absolute/checkout/script/briefing"]' \
  python3 -m unittest discover tests -v
```

The Windows bootstrap and launcher have native tests that Linux cannot stand
in for: [briefing-bootstrap/README.md](briefing-bootstrap/README.md) and
[winlaunch/README.md](winlaunch/README.md).

Build: `dzil build` makes the CPAN distribution, which installs only the
`briefing` command, none of the plugin's `bin/` files. The binaries are built
from a release by the `binaries` workflow (`.github/workflows/binaries.yml`),
which smoke-tests each one on its own platform; `scripts/import-binary-sums.py`
turns the release's checksums into `bin/briefing-binaries.sha256`, and the
plugin version that commits that file is the one that switches the binary on.
The changelog for the plugin and the distribution is [Changes](Changes).

## License

Copyright (c) 2026 Torsten Raudssus.

This is free software; you can redistribute it and/or modify it under the
terms of the [Artistic License 2.0](LICENSE).
