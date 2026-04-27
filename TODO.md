# briefing — TODO

Live worklist. Tick as we go.

## v0.1 — MVP (this scaffold)

- [x] Plugin manifest `.claude-plugin/plugin.json`
- [x] Hook registration `hooks/hooks.json` (PreToolUse → Agent)
- [x] Hook script `hooks/briefing-preload` (Perl, core-only)
- [x] Frontmatter parser — block list and flow list forms of `skills:`
- [x] Skill resolution — project / user / plugin caches, bare + namespaced
- [x] Hard-fail on missing skill (`permissionDecision: deny`)
- [x] README.md + CLAUDE.md
- [ ] Smoke test: feed the hook a fake `Agent` tool input on stdin and
      diff the resulting prompt against a golden file.

## v0.2 — Robustness

- [ ] Tests in `t/` driven by `prove -l t/`:
  - [ ] `t/01-frontmatter.t` — block / flow / quoted / missing
  - [ ] `t/02-resolve.t` — project beats user beats plugin
  - [ ] `t/03-namespaced.t` — `plugin:skill` form
  - [ ] `t/04-hard-fail.t` — missing skill returns deny JSON
  - [ ] `t/05-passthrough.t` — non-Agent tool, no frontmatter,
        empty `skills:` all exit 0 with empty stdout
- [ ] Example agent in `examples/` + tiny example skill, so anyone
      can try the plugin against this repo as both project and
      plugin source.
- [ ] Token-budget guard: if injected size exceeds N kB, log a
      warning to stderr (still spawn). Decide N — start at 64 kB.
- [ ] Cycle detection: if a skill's body itself contains a frontmatter
      `skills:` list, **do not** recursively expand. Document it.

## v0.3 — Distribution

- [ ] Marketplace entry — `marketplace.json` style or whichever
      format Claude Code currently accepts (verify via claude-code-guide).
- [ ] `Changes` file in dzil style (even though this is not a CPAN
      dist — keeps the changelog honest).
- [ ] LICENSE file (Artistic-2.0 to match Perl community default).
- [ ] CI: GitHub Actions workflow running `prove -l t/` on
      perl 5.36 + 5.38 + 5.40.

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

1. `perl -c hooks/briefing-preload` — must compile clean.
2. Pipe a hand-crafted JSON into the hook and inspect stdout:
   ```
   echo '{"tool_name":"Agent","cwd":"'"$PWD"'","tool_input":{"subagent_type":"demo","prompt":"go"}}' \
     | hooks/briefing-preload | jq .
   ```
   Requires `examples/demo.md` agent + `examples/skills/foo/SKILL.md`
   plus a temp project layout.
3. Once tests exist: `prove -lv t/`.
