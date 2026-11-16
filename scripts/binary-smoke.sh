#!/usr/bin/env bash
# Smoke-test a packed briefing binary on a clean machine: no Perl from the build, no Python,
# an empty PATH. binary_smoke of the [@Author::GETTY] bundle (dist.ini): its dzil-binary
# workflow runs it from the unpacked dist on every platform (Linux in clean images, macOS and
# Windows on the runner), and dzil build's local check right after packing.
#   bash scripts/binary-smoke.sh <binary>       from the dist root
# Prints "smoke: all checks passed" and exits 0, or "FAIL: <reason>" on STDERR and exits 1.
#
# Checks, each on the binary only:
#   --version prints "briefing <version>"; --help starts with "Usage:"; an unknown command
#   exits 2; then, in an ASCII project and again in one whose directory and skill have
#   non-ASCII names (Windows: the umlaut and CJK paths the packaging probe failed on, see
#   docs/perl-direction.md point 1):
#     doctor --tsv     (from the directory, then with --cwd DIR) exits 0 and reports agent, skill, settings and hook as ok;
#     doctor           exits 0;
#     hook subagent-start   writes the briefing with the skill's marker text (a spawn is
#                      briefed), exit 0;
#     hook pre-tool-use     denies an agent that declares an unknown skill;
#     hook session-start    warns about that agent with a systemMessage;
#     hook with empty stdin exits 0 and writes nothing.
#
# BRIEFING_EXPECT_VERSION: the version --version must report (default: $VERSION of
# lib/App/Briefing.pm in the dist, which the build stamps with the dist version).
# BRIEFING_SMOKE_PATH: PATH visible to the binary (default: an empty directory, so the packed
# runtime provably calls neither a system Perl nor Python).
set -euo pipefail

[ -n "${1:-}" ] || { echo "usage: binary-smoke.sh <binary>" >&2; exit 1; }
[ -f lib/App/Briefing.pm ] || { echo "FAIL: run from the dist root of briefing" >&2; exit 1; }
[ -f "$1" ] || { echo "FAIL: no such binary: $1" >&2; exit 1; }
BIN=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")

want=${BRIEFING_EXPECT_VERSION:-$(sed -n "s/^our \$VERSION = '\([^']*\)';.*/\1/p" lib/App/Briefing.pm | head -n 1)}
[ -n "$want" ] || { echo "FAIL: cannot work out the expected version" >&2; exit 1; }

mkd=$(mktemp -d) || exit 1
work=$(cd "$mkd" && pwd -P) || exit 1
trap 'rm -rf "${work:?}"' EXIT
mkdir -p "$work/empty"
runtime_path=${BRIEFING_SMOKE_PATH:-$work/empty}
# The bundle mounts the binary read-only with its mode already set; an Actions artifact or an
# HTTP download carries none. Never chmod in place: copy to the work dir and run that.
if [ ! -x "$BIN" ]; then
  cp "$BIN" "$work/briefing-bin" && chmod +x "$work/briefing-bin" || fail_early=1
  [ -z "${fail_early:-}" ] || { echo "FAIL: cannot make a runnable copy of $BIN" >&2; exit 1; }
  BIN=$work/briefing-bin
fi
. "$(dirname "${BASH_SOURCE[0]}")/binary-lib.sh"

out=$(bin --version) || fail "--version failed"
[ "$out" = "briefing $want" ] || fail "--version prints '$out', want 'briefing $want'"
echo "smoke --version: OK ($out)"

rc=0
bin --help >"$work/help" 2>"$work/help.err" || rc=$?
[ "$rc" -eq 0 ] || fail "--help exits $rc: $(head -c 400 "$work/help.err")"
[ "$(head -n 1 "$work/help")" = "Usage:" ] || fail "--help starts with '$(head -n 1 "$work/help")'"
echo "smoke --help: OK"

rc=0
bin nope >/dev/null 2>"$work/nope.err" || rc=$?
[ "$rc" -eq 2 ] || fail "an unknown command exits $rc, want 2"
echo "smoke error path: OK (unknown command, exit 2)"

# run_case LABEL DIRNAME SKILL
run_case() {
  local label=$1 name=$2 skill=$3 dir ndir transcript rc out
  dir=$work/$name
  fixture "$name" "$skill"
  ndir=$(native "$dir")
  transcript=$(native "$home")/.claude/projects/p/s.jsonl

  rc=0
  printf '{"hook_event_name":"SubagentStart","agent_type":"demo","agent_id":"a","cwd":"%s","transcript_path":"%s"}' \
    "$ndir" "$transcript" >"$work/in"
  (cd "$dir" && env -i "${envs[@]}" "$BIN" hook subagent-start <"$work/in" >"$work/out" 2>"$work/err") || rc=$?
  [ "$rc" -eq 0 ] || fail "$label: hook subagent-start exits $rc: $(head -c 400 "$work/err")"
  grep -qF '"hookEventName":"SubagentStart"' "$work/out" || fail "$label: no SubagentStart output: $(head -c 400 "$work/out")"
  grep -qF "SMOKE-MARKER-$skill" "$work/out" || fail "$label: the briefing lacks the skill text (a spawn would run unbriefed): $(head -c 400 "$work/out")"
  echo "smoke $label hook subagent-start: OK (the skill text arrives)"

  broken_agent "$name"
  rc=0
  printf '{"hook_event_name":"PreToolUse","tool_name":"Agent","cwd":"%s","tool_input":{"subagent_type":"broken"}}' \
    "$ndir" >"$work/in"
  (cd "$dir" && env -i "${envs[@]}" "$BIN" hook pre-tool-use <"$work/in" >"$work/out" 2>"$work/err") || rc=$?
  [ "$rc" -eq 0 ] || fail "$label: hook pre-tool-use exits $rc"
  grep -qF '"permissionDecision":"deny"' "$work/out" || fail "$label: an unknown skill is not denied: $(head -c 400 "$work/out")"
  echo "smoke $label hook pre-tool-use: OK (unknown skill denied)"

  rc=0
  printf '{"hook_event_name":"SessionStart","cwd":"%s","source":"startup","transcript_path":"%s"}' \
    "$ndir" "$transcript" >"$work/in"
  (cd "$dir" && env -i "${envs[@]}" "$BIN" hook session-start <"$work/in" >"$work/out" 2>"$work/err") || rc=$?
  [ "$rc" -eq 0 ] || fail "$label: hook session-start exits $rc"
  grep -qF '"systemMessage"' "$work/out" || fail "$label: session-start does not warn: $(head -c 400 "$work/out")"
  echo "smoke $label hook session-start: OK"
  rm -f "$dir/.claude/agents/broken.md"

  # doctor without --cwd reads the directory from the process (a wide API on Windows).
  rc=0
  out=$(cd "$dir" && bin doctor --tsv 2>"$work/err") || rc=$?
  [ "$rc" -eq 0 ] || fail "$label: doctor --tsv (cwd) exits $rc: $out $(head -c 400 "$work/err")"
  for what in agent skill settings hook; do
    printf '%s\n' "$out" | grep -q "^$what	ok	" || fail "$label: doctor --tsv (cwd) has no ok $what line: $out"
  done
  printf '%s\n' "$out" | grep -qF "$skill" || fail "$label: doctor --tsv (cwd) does not name the skill $skill"
  echo "smoke $label doctor --tsv (cwd): OK"

  # doctor --cwd DIR takes the path from argv. Windows hands Perl an ANSI command line, so
  # characters outside the code page arrive as '?': a known limit of argv, not of the hooks
  # (their paths come as UTF-8 JSON on stdin, checked above).
  rc=0
  out=$(cd "$dir" && bin doctor --tsv --cwd "$ndir" 2>"$work/err") || rc=$?
  [ "$rc" -eq 0 ] || fail "$label: doctor --tsv --cwd (argv) exits $rc: $out $(head -c 400 "$work/err")"
  for what in agent skill settings hook; do
    printf '%s\n' "$out" | grep -q "^$what	ok	" || fail "$label: doctor --tsv has no ok $what line: $out"
  done
  printf '%s\n' "$out" | grep -qF "$skill" || fail "$label: doctor --tsv does not name the skill $skill"
  echo "smoke $label doctor --tsv --cwd (argv): OK"

  rc=0
  (cd "$dir" && bin doctor --cwd "$ndir" --harness claude >"$work/out" 2>"$work/err") || rc=$?
  [ "$rc" -eq 0 ] || fail "$label: doctor exits $rc: $(head -c 400 "$work/err")"
  echo "smoke $label doctor: OK"
}

run_case ascii project demo-skill
# The non-ASCII case: umlaut and CJK in the project directory and in the skill name.
run_case unicode "Pfad ä 技能/projekt" "grüße-技能"

rc=0
(cd "$work" && env -i "${envs[@]}" "$BIN" hook subagent-start </dev/null >"$work/out" 2>"$work/err") || rc=$?
[ "$rc" -eq 0 ] || fail "a hook with empty stdin exits $rc"
[ ! -s "$work/out" ] || fail "a hook with empty stdin writes '$(head -c 200 "$work/out")'"
echo "smoke hook empty stdin: OK"
echo "smoke: all checks passed"
