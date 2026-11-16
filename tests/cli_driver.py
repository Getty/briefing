"""Select the reference Python entrypoint or an external briefing CLI.

BRIEFING_TEST_CLI is a JSON array, for example
["/usr/bin/perl", "-I/absolute/path/to/lib", "/absolute/path/to/bin/briefing"].
The configured command is executed as an argv list and receives one of the
public subcommands (hook, doctor, or notice) plus the caller's arguments; it
is never passed to a shell.
"""

import json
import os


def command_for(subcommand, default_argv, *arguments):
    """Return the configured CLI plus forwarded argv, or the unchanged fallback."""
    raw = os.environ.get("BRIEFING_TEST_CLI")
    if raw is None:
        return [*default_argv, *arguments]

    try:
        argv = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("BRIEFING_TEST_CLI must be a JSON argv array") from exc

    if not isinstance(argv, list) or not argv or not all(
        isinstance(item, str) and item for item in argv
    ):
        raise RuntimeError("BRIEFING_TEST_CLI must be a non-empty JSON argv array")

    return [*argv, subcommand, *arguments]
