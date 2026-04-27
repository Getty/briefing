# briefing — TODO

Live worklist. Tick as we go.

## v0.1 — MVP (this scaffold)

- [x] Plugin manifest `.claude-plugin/plugin.json`
- [x] Hook registration `hooks/hooks.json` (PreToolUse → Agent)
- [x] Hook script `hooks/briefing-preload` (Python 3, stdlib-only)
- [x] Frontmatter parser — block list and flow list forms of `skills:`
- [x] Skill resolution — project / user / plugin caches, bare + namespaced
- [x] Hard-fail on missing skill (`permissionDecision: deny`)
- [x] README.md + CLAUDE.md
- [x] Smoke test: feed the hook a fake `Agent` tool input on stdin
      (covered by `tests/test_briefing.py`).

## v0.2 — Robustness

- [x] Tests in `tests/` driven by `python3 -m unittest discover tests`
      — 14 cases covering passthrough, block/flow frontmatter,
      project/user/plugin precedence, `plugin:skill` form, and
      hard-fail. Runs against the hook as a subprocess with a
      sandboxed `HOME` and `cwd`.
- [x] Example agent in `examples/agents/briefing-demo.md` + matching
      skill in `examples/skills/briefing-demo-skill/` for end-to-end
      verification in any project.
- [ ] Token-budget guard: if injected size exceeds N kB, log a
      warning to stderr (still spawn). Decide N — start at 64 kB.
- [ ] Cycle detection: if a skill's body itself contains a frontmatter
      `skills:` list, **do not** recursively expand. Document it.

## v0.3 — Distribution

- [ ] Marketplace entry — `marketplace.json` style or whichever
      format Claude Code currently accepts (verify via claude-code-guide).
- [x] `CHANGELOG.md` — keep the changelog honest.
- [x] LICENSE file (Artistic-2.0).
- [x] CI: GitHub Actions workflow running `python3 -m unittest
      discover tests` on Python 3.10 + 3.11 + 3.12.

## v0.4 — Nice-to-have

- [ ] Optional `briefing-strip-frontmatter: false` per-skill flag —
      some skills' frontmatter is genuinely useful context.
- [ ] Optional `briefing-format: <fenced|raw>` — wrap each skill in
      a `<skill name="...">` XML-ish block so the agent can identify
      boundaries unambiguously.
- [ ] Source `skills:` from `description` text as a fallback (parse
      the existing prose like `"Loads backend Perl skills (perl-core,
      perl-moose, ...)"`) — would let existing Goldmine agents work
      without a frontmatter rewrite. Decide later: probably reject as
      too magical.
- [ ] `briefing doctor` CLI: validate every agent file in a project,
      report any unresolvable skills before they bite at spawn time.

## Open design questions

- [ ] Should we strip the skill's frontmatter (`name:`, `description:`,
      …) from the injected body? Currently yes. Some skills carry
      important metadata in description we're throwing away.
- [ ] Should `additionalContext` be used instead of mutating `prompt`?
      Pro: preserves the user's prompt verbatim in transcripts.
      Con: less control over ordering, behavior less documented.
- [ ] How do we want to surface "skill X was pre-loaded" in the
      transcript / UI so the user can audit? Probably a stderr line
      that the harness prints.

## Test cases for the next session

When you re-enter this repo fresh:

1. `python3 -m py_compile hooks/briefing-preload` — must compile clean.
2. Pipe a hand-crafted JSON into the hook and inspect stdout:
   ```
   echo '{"tool_name":"Agent","cwd":"'"$PWD"'","tool_input":{"subagent_type":"demo","prompt":"go"}}' \
     | hooks/briefing-preload | jq .
   ```
   Requires `examples/demo.md` agent + `examples/skills/foo/SKILL.md`
   plus a temp project layout.
3. Once tests exist: `python3 -m unittest discover tests`.
