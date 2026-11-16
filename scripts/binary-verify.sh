#!/usr/bin/env bash
# Verify a packed briefing against `perl -Ilib script/briefing` from this dist.
#   bash scripts/binary-verify.sh <binary>
# binary_verify of the [@Author::GETTY] bundle (dist.ini): run from the dist root right after
# packing, by dzil build's local check and by each platform leg of the bundle's dzil-binary
# workflow. Prints "verify: OK" and exits 0, or "FAIL: <reason>" on STDERR and exits 1.
# Run it where the binary was built (the perl that packed it, with the dist's dependencies):
# the bundle names where they are in DZIL_BINARY_PERL5LIB (unset or empty: this shell's
# environment as it is). scripts/binary-smoke.sh is the other half: the binary on a machine
# without Perl, in non-ASCII paths.
#
# Compared with the reference, in an ASCII project, STDOUT and exit code: --version, --help,
# doctor --tsv, hook subagent-start, hook pre-tool-use (an unknown skill), hook session-start.
# Also: no TLS module is inside the archive (briefing has no network access).
set -euo pipefail

[ -n "${1:-}" ] || { echo "usage: binary-verify.sh <binary>" >&2; exit 1; }
[ -f script/briefing ] && [ -f lib/App/Briefing.pm ] || { echo "FAIL: run from the dist root of briefing" >&2; exit 1; }
BIN=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
[ -f "$BIN" ] || { echo "FAIL: no such binary: $BIN" >&2; exit 1; }
root=$(pwd)

mkd=$(mktemp -d) || exit 1
work=$(cd "$mkd" && pwd -P) || exit 1
trap 'rm -rf "${work:?}"' EXIT
mkdir -p "$work/empty"
runtime_path=$work/empty
# The binary may sit on a read-only mount with its mode set: never chmod in place.
if [ ! -x "$BIN" ]; then
  cp "$BIN" "$work/briefing-bin" && chmod +x "$work/briefing-bin" || { echo "FAIL: cannot make a runnable copy of $BIN" >&2; exit 1; }
  BIN=$work/briefing-bin
fi
. "$(dirname "${BASH_SOURCE[0]}")/binary-lib.sh"

# same_as_perl CASE STDIN ARGS...: STDOUT and exit code of the binary match the reference's.
# The reference must have printed something (empty on both sides proves nothing).
same_as_perl() {
  local name=$1 input=$2 rc_want=0 rc_got=0
  shift 2
  (cd "$work/ascii" && env -i "${envs[@]/#PATH=*/PATH=$PATH}" ${DZIL_BINARY_PERL5LIB:+PERL5LIB="$DZIL_BINARY_PERL5LIB"} \
    perl -I"$(native "$root")/lib" "$(native "$root")/script/briefing" "$@" <"$input" >"$work/want" 2>"$work/want.err") || rc_want=$?
  (cd "$work/ascii" && env -i "${envs[@]}" "$BIN" "$@" <"$input" >"$work/got" 2>"$work/got.err") || rc_got=$?
  [ "$rc_want" = "$rc_got" ] || fail "$name: exit code differs (binary $rc_got, perl $rc_want): $(head -n 3 "$work/got.err")"
  [ -s "$work/want" ] || fail "$name: the perl reference printed nothing, the case proves nothing: $(head -c 300 "$work/want.err")"
  cmp -s "$work/want" "$work/got" || {
    diff "$work/want" "$work/got" | head -n 10 >&2 || true
    fail "$name: STDOUT differs between the binary and perl -Ilib script/briefing"
  }
  echo "verify $name: same as perl (exit $rc_got)"
}

fixture ascii demo-skill
dir=$work/ascii
ndir=$(native "$dir")
transcript=$(native "$home")/.claude/projects/p/s.jsonl
: >"$work/empty-in"
printf '{"hook_event_name":"SubagentStart","agent_type":"demo","agent_id":"a","cwd":"%s","transcript_path":"%s"}' \
  "$ndir" "$transcript" >"$work/in-start"
printf '{"hook_event_name":"PreToolUse","tool_name":"Agent","cwd":"%s","tool_input":{"subagent_type":"broken"}}' \
  "$ndir" >"$work/in-pre"
printf '{"hook_event_name":"SessionStart","cwd":"%s","source":"startup","transcript_path":"%s"}' \
  "$ndir" "$transcript" >"$work/in-session"

same_as_perl version "$work/empty-in" --version
same_as_perl help "$work/empty-in" --help
same_as_perl doctor-tsv "$work/empty-in" doctor --tsv --cwd "$ndir"
broken_agent ascii # from here on the project also has an agent with an unknown skill
same_as_perl subagent-start "$work/in-start" hook subagent-start
same_as_perl pre-tool-use "$work/in-pre" hook pre-tool-use
same_as_perl session-start "$work/in-session" hook session-start

# The zip central directory of a PAR executable names every packed file in clear.
if grep -aq -e 'Net/SSLeay' -e 'IO/Socket/SSL' "$BIN"; then
  # Name what matched (byte offset: matched text), so the log shows the cause. Diagnostic only.
  echo "TLS gate: first matches (offset:text, 20 of $(grep -a -o -e 'Net/SSLeay' -e 'IO/Socket/SSL' "$BIN" | wc -l | tr -d ' ')):" >&2
  { grep -a -o -b -e '[A-Za-z0-9_./-]*Net/SSLeay[A-Za-z0-9_./-]*' -e '[A-Za-z0-9_./-]*IO/Socket/SSL[A-Za-z0-9_./-]*' "$BIN" | head -n 20 >&2; } || true
  fail "the archive holds a TLS module; briefing has no network access and must not pack one"
fi
echo "verify: OK"
