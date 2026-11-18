#!/usr/bin/env python3
"""Native chain test: the packed asset behind the plugin's real entry point.

The binaries workflow job `chain` runs this once on every native runner, with the
platform's packed asset from the same workflow run:

    python3 tests/test_binary_chain.py <path-to-asset> -v      (Windows: python)

The asset name is briefing-<version>-<platform> (".exe" on Windows). The version is
`probe-<sha7>` in a probe run and the dist version in a release run; the platform must
be the host's.

Unlike scripts/binary-smoke.sh, which runs the asset alone, this runs the whole chain a
plugin user gets:

    POSIX    bin/briefing (sh starter) -> download, verify, cache -> cached PAR binary
    Windows  bin/briefing.exe (winlaunch copy) -> bin/briefing-bootstrap.exe -> cached PAR

in a plugin copy and a project at paths with umlaut and CJK characters, with a CLAUDE
config directory of that kind, and with a PATH that holds neither Perl nor Python.
The asset is served from a loopback HTTP server through the starter's and the bootstrap's
test gates (BRIEFING_STARTER_TESTING, BRIEFING_BOOTSTRAP_TESTING) and
BRIEFING_BINARY_BASE_URL; the pin manifest of the plugin copy carries the asset's real
SHA-256 for the host platform.

Without an asset argument (for example under `unittest discover`) every test is skipped.
Timings for k6 are printed as `chain_timing <platform> <series> <ms> ... median=<ms>`
lines; they are measurements, not assertions.

Standard library only, Python 3.8+.
"""

import functools
import hashlib
import http.server
import json
import os
import platform
import re
import shutil
import stat
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = os.name == "nt"
ASSET_PATH = None  # set from argv[1] by __main__

PLATFORMS = (
    "linux-x86_64",
    "linux-arm64",
    "macos-x86_64",
    "macos-arm64",
    "windows-x86_64",
)
ASSET_NAME = re.compile(
    r"^briefing-(?P<version>.+)-(?P<platform>%s)(?P<exe>\.exe)?$" % "|".join(PLATFORMS)
)
SKILL = "grüße-技能"
MARKER = "CHAIN-MARKER-" + SKILL
SKIP_REASON = (
    "needs a packed asset: run by the `chain` job of .github/workflows/binaries.yml as "
    "`python3 tests/test_binary_chain.py <asset> -v`"
)
WARNING = r"^briefing: no binary \(.+\) and no fallback \(.+\)\.$"

# k8: on Windows argv reaches Perl in the ANSI code page, so a non-ANSI --cwd cannot work yet.
expected_failure_on_windows = unittest.expectedFailure if IS_WINDOWS else (lambda test: test)


def host_platform():
    system = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system())
    machine = platform.machine().lower()
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    if system is None or arch is None:
        raise AssertionError("unsupported host: %s %s" % (platform.system(), platform.machine()))
    return "%s-%s" % (system, arch)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def remove_tree(path):
    def writable(function, name, _error):
        os.chmod(name, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        function(name)

    shutil.rmtree(str(path), onerror=writable)


class ReleaseServer:
    """Loopback HTTP server for <root>/<version>/<asset>; records the requested paths."""

    def __init__(self, root):
        self.paths = []
        paths = self.paths

        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(handler):
                paths.append(handler.path)
                http.server.SimpleHTTPRequestHandler.do_GET(handler)

            def log_message(handler, format_, *args):
                pass

        handler = functools.partial(Handler, directory=str(root))
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def base_url(self, version):
        return "http://127.0.0.1:%d/%s" % (self.server.server_port, version)

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


def report_timing(series, values):
    sys.stdout.write(
        "chain_timing %s %s %s median=%.1f\n"
        % (
            ChainTests.platform,
            series,
            " ".join("%.1f" % value for value in values),
            statistics.median(values),
        )
    )
    sys.stdout.flush()


class ChainTests(unittest.TestCase):
    platform = None

    @classmethod
    def setUpClass(cls):
        if ASSET_PATH is None:
            raise unittest.SkipTest(SKIP_REASON)
        if not ASSET_PATH.is_file():
            raise AssertionError("the asset does not exist: %s" % ASSET_PATH)
        match = ASSET_NAME.match(ASSET_PATH.name)
        if match is None:
            raise AssertionError(
                "the asset name is not briefing-<version>-<platform>[.exe]: %s" % ASSET_PATH.name
            )
        cls.version = match.group("version")
        cls.platform = match.group("platform")
        host = host_platform()
        if cls.platform != host:
            raise AssertionError("asset platform %s does not match the host %s" % (cls.platform, host))
        if bool(match.group("exe")) != IS_WINDOWS:
            raise AssertionError("an .exe suffix is required exactly on Windows: %s" % ASSET_PATH.name)
        cls.asset_name = ASSET_PATH.name
        cls.asset_sha = sha256_of(ASSET_PATH)

        cls.temporary = tempfile.mkdtemp(prefix="briefing-chain-Ärger-世界-")
        cls.addClassCleanup(remove_tree, cls.temporary)
        cls.root = Path(cls.temporary).resolve()

        # The plugin copy: bin/ and hooks/ as shipped, plus the pin manifest of this asset.
        cls.plugin = cls.root / "Plugin-ä-世界"
        for name in ("bin", "hooks"):
            shutil.copytree(str(REPO_ROOT / name), str(cls.plugin / name))
        lines = []
        for name in PLATFORMS:
            asset = "briefing-%s-%s%s" % (cls.version, name, ".exe" if name.startswith("windows") else "")
            digest = cls.asset_sha if name == cls.platform else hashlib.sha256(asset.encode()).hexdigest()
            lines.append("%s  %s\n" % (digest, asset))
        # Bytes, not text: the bootstrap rejects a CRLF manifest and Windows text mode would write one.
        (cls.plugin / "bin" / "briefing-binaries.sha256").write_bytes("".join(lines).encode("ascii"))
        entry = "briefing.exe" if IS_WINDOWS else "briefing"
        cls.entry = cls.plugin / "bin" / entry

        # The release location: <root>/<version>/<asset>, and an empty one.
        cls.release = cls.root / "Veröffentlichung-ö-世界"
        (cls.release / cls.version).mkdir(parents=True)
        shutil.copyfile(str(ASSET_PATH), str(cls.release / cls.version / cls.asset_name))
        cls.empty_release = cls.root / "Leer-ü-世界"
        cls.empty_release.mkdir()
        cls.server = ReleaseServer(cls.release)
        cls.addClassCleanup(cls.server.stop)
        cls.empty_server = ReleaseServer(cls.empty_release)
        cls.addClassCleanup(cls.empty_server.stop)

        # The user's home and a project with an agent that declares a skill, plus its skill.
        cls.home = cls.root / "Heim-ä-世界"
        (cls.home / ".claude").mkdir(parents=True)
        (cls.home / ".codex").mkdir()
        cls.tmpdir = cls.root / "tmp"
        cls.tmpdir.mkdir()
        cls.project = cls.root / "Projekt-ö-技能"
        (cls.project / ".claude" / "agents").mkdir(parents=True)
        skill_dir = cls.project / ".claude" / "skills" / SKILL
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_bytes((MARKER + "\n").encode("utf-8"))
        (cls.project / ".claude" / "agents" / "demo.md").write_bytes(
            (
                "---\nname: demo\ndescription: d\nbriefing:\n  skills:\n    - %s\n---\nbody\n" % SKILL
            ).encode("utf-8")
        )
        (cls.project / ".claude" / "settings.json").write_bytes(
            (
                '{"enabledPlugins":{"briefing@getty":true},"extraKnownMarketplaces":{"getty":'
                '{"source":{"source":"github","repo":"Getty/marketplace"}}}}\n'
            ).encode("utf-8")
        )
        cls.path_value = cls.build_path()
        cls.assert_no_runtimes_on(cls.path_value)

    @classmethod
    def build_path(cls):
        """A PATH that provably holds neither Perl nor Python."""
        if IS_WINDOWS:
            # An empty directory only. Nothing in the chain needs PATH (the bootstrap and the
            # PAR binary find their DLLs in the system directory), and %SystemRoot% may hold
            # py.exe, which the bootstrap's fallback would pick (tests 7 and 8).
            empty = cls.root / "empty-path"
            empty.mkdir()
            return str(empty)
        farm = cls.root / "path-farm"
        farm.mkdir()
        refused = re.compile(r"^(perl|python|cpan|pip)")
        for directory in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                target = os.path.join(directory, name)
                link = farm / name
                if (
                    refused.match(name)
                    or link.exists()
                    or link.is_symlink()
                    or not os.path.isfile(target)
                    or not os.access(target, os.X_OK)
                ):
                    continue
                os.symlink(target, str(link))
        for name in os.listdir(str(farm)):
            if refused.match(name):
                raise AssertionError("the PATH farm contains %s" % name)
        return str(farm)

    @staticmethod
    def assert_no_runtimes_on(path_value):
        """Premise: no Perl and no Python (or py launcher) is reachable through PATH."""
        runtime = re.compile(r"^(perl|python|py$|py\.exe$)", re.IGNORECASE)
        for directory in path_value.split(os.pathsep):
            if not directory or not os.path.isdir(directory):
                continue
            found = [name for name in os.listdir(directory) if runtime.match(name)]
            if found:
                raise AssertionError("PATH entry %s holds a runtime: %r" % (directory, found))

    # -- helpers

    def new_config(self):
        config = self.root / ("Konfiguration-ä-世界-" + self._testMethodName)
        if config.exists():
            remove_tree(config)
        config.mkdir()
        return config

    def environment(self, config, server=None):
        env = {
            "PATH": self.path_value,
            "HOME": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"),
            "TMPDIR": str(self.tmpdir),
            "TMP": str(self.tmpdir),
            "TEMP": str(self.tmpdir),
            "CLAUDE_CONFIG_DIR": str(config),
            "BRIEFING_STARTER_TESTING": "1",
            "BRIEFING_BOOTSTRAP_TESTING": "1",
            "BRIEFING_BINARY_BASE_URL": (server or self.server).base_url(self.version),
        }
        if IS_WINDOWS:
            env["SystemRoot"] = os.environ.get("SystemRoot", r"C:\Windows")
            env["WINDIR"] = env["SystemRoot"]
            env["USERPROFILE"] = str(self.home)
        else:
            env["LC_ALL"] = "C"
        return env

    def run_entry(self, args, config, payload=None, cwd=None, server=None, timeout=180):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return subprocess.run(
            [str(self.entry)] + list(args),
            input=payload if payload is not None else b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd or self.project),
            env=self.environment(config, server=server),
            timeout=timeout,
        )

    def payload(self, event, **extra):
        data = {"hook_event_name": event, "cwd": str(self.project)}
        data.update(extra)
        return json.dumps(data, ensure_ascii=False)

    def subagent_payload(self):
        return self.payload("SubagentStart", agent_type="demo", agent_id="a1")

    def cache_dir(self, config):
        return config / "briefing" / "bin" / self.version

    def cached_binary(self, config):
        return self.cache_dir(config) / ("%s-%s" % (self.asset_name, self.asset_sha))

    def listing(self, config):
        base = self.cache_dir(config)
        return sorted(p.name for p in base.iterdir()) if base.exists() else []

    def provision(self, config):
        result = self.run_entry(
            ("hook", "session-start"), config, self.payload("SessionStart", source="startup")
        )
        detail = "session-start exit=%r\nstdout:\n%s\nstderr:\n%s" % (
            result.returncode,
            result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"),
        )
        self.assertEqual(result.returncode, 0, detail)
        self.assertTrue(
            self.cached_binary(config).is_file(),
            "no verified binary in %s: %r\n%s"
            % (self.cache_dir(config), self.listing(config), detail),
        )
        return result

    def assert_safe_warning(self, result):
        """The documented no-binary, no-fallback contract: one systemMessage line, exit 0."""
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stderr, b"")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        output = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(set(output), {"systemMessage"})
        self.assertRegex(output["systemMessage"], WARNING)

    def add_broken_agent(self):
        path = self.project / ".claude" / "agents" / "broken.md"
        path.write_bytes(
            "---\nname: broken\ndescription: d\nbriefing:\n  skills:\n    - no-such-skill\n---\nbody\n".encode(
                "utf-8"
            )
        )
        self.addCleanup(lambda: path.unlink() if path.exists() else None)

    def tsv_rows(self, result):
        text = result.stdout.decode("utf-8")
        return [line.split("\t") for line in text.splitlines() if line]

    def assert_doctor_ok(self, result):
        detail = result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
        self.assertEqual(result.returncode, 0, detail)
        rows = self.tsv_rows(result)
        for kind in ("agent", "skill", "settings", "hook"):
            self.assertTrue(
                any(len(row) > 1 and row[0] == kind and row[1] == "ok" for row in rows),
                "no ok %s row: %r" % (kind, rows),
            )
        self.assertIn(SKILL, result.stdout.decode("utf-8"))

    # -- cases

    def run_direct(self, label, copy, par_temp):
        """Run the asset copy directly (no bootstrap, no starter) with --version.

        Returns (ok, report); the report carries the variant's paths, exit code and output.
        """
        env = self.environment(self.new_config())
        env["PAR_GLOBAL_TEMP"] = str(par_temp)
        try:
            result = subprocess.run(
                [str(copy), "--version"],
                input=b"",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(Path(str(copy)).parent),
                env=env,
                timeout=120,
            )
            code, out, err = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as expired:
            code, out, err = "timeout", expired.stdout or b"", expired.stderr or b""
        text = out.decode("utf-8", "replace")
        ok = code == 0 and re.match(r"^briefing \S+\r?\n$", text) is not None
        return ok, (
            "%s (%s; PAR_GLOBAL_TEMP=%s): exit=%r\nstdout:\n%s\nstderr:\n%s"
            % (label, copy, par_temp, code, text, err.decode("utf-8", "replace"))
        )

    def direct_copy(self, base, temp_name):
        directory = base / "bin"
        par_temp = base / temp_name
        directory.mkdir(parents=True)
        par_temp.mkdir(parents=True)
        copy = directory / self.asset_name
        shutil.copyfile(str(ASSET_PATH), str(copy))
        copy.chmod(0o755)
        return copy, par_temp

    def test_0_asset_runs_directly_from_an_ascii_directory(self):
        """Diagnostic control: PAR itself, with ASCII paths only (every platform)."""
        ascii_root = Path(tempfile.mkdtemp(prefix="briefing-chain-ascii-")).resolve()
        self.addCleanup(remove_tree, ascii_root)
        copy, par_temp = self.direct_copy(ascii_root, "par-temp")
        ok, report = self.run_direct("ascii", copy, par_temp)
        self.assertTrue(ok, "the asset failed when run directly from ASCII paths:\n" + report)

    def _unicode_direct(self):
        copy, par_temp = self.direct_copy(self.root / "Direkt-ä-世界", "par-temp-ö")
        return self.run_direct("unicode", copy, par_temp)

    def test_0_asset_runs_directly_from_a_non_ansi_directory(self):
        """PAR's loader is ANSI-only, so on Windows a direct run from a non-ANSI long path
        with a non-ANSI PAR_GLOBAL_TEMP cannot pass on a non-UTF-8 code page. The spec's
        Unicode requirement covers the bootstrap chain (which hands PAR the 8.3 alias),
        not a direct PAR run. POSIX has no such limit and must pass.
        """
        ok, report = self._unicode_direct()
        self.assertTrue(ok, "the asset failed when run directly from non-ANSI paths:\n" + report)

    if IS_WINDOWS:
        test_0_asset_runs_directly_from_a_non_ansi_directory = unittest.expectedFailure(
            test_0_asset_runs_directly_from_a_non_ansi_directory
        )
        test_0_asset_runs_directly_from_a_non_ansi_directory.__doc__ = (
            "Known failure on Windows: PAR::Packer's loader is ANSI-only; the bootstrap hands "
            "it the 8.3 alias."
        )

    @unittest.skipUnless(IS_WINDOWS, "8.3 aliases exist only on Windows")
    def test_0_asset_runs_directly_through_the_8_3_alias_of_non_ansi_paths(self):
        """The same non-ANSI copy, reached through the 8.3 alias of its directory and of
        a non-ANSI PAR_GLOBAL_TEMP, must run. A volume without 8.3 aliases fails loudly
        here (the alias equals the long path, or the call fails): that is the evidence
        whether the runner can provide the alias the bootstrap relies on.
        """
        import ctypes

        copy, par_temp = self.direct_copy(self.root / "Alias-ä-世界", "par-temp-ö")

        def short(path):
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, 32768)
            self.assertTrue(
                0 < length < 32768,
                "GetShortPathNameW failed for %s (error %d): no 8.3 alias"
                % (path, ctypes.GetLastError()),
            )
            return buffer.value

        short_directory = short(copy.parent)
        short_temp = short(par_temp)
        self.assertNotEqual(
            os.path.normcase(short_directory), os.path.normcase(str(copy.parent)),
            "the volume has no 8.3 alias for %s (the call returned the long path)" % copy.parent,
        )
        self.assertNotEqual(
            os.path.normcase(short_temp), os.path.normcase(str(par_temp)),
            "the volume has no 8.3 alias for %s (the call returned the long path)" % par_temp,
        )
        ok, report = self.run_direct(
            "unicode via 8.3 alias", os.path.join(short_directory, self.asset_name), short_temp
        )
        self.assertTrue(ok, "the asset failed through the 8.3 aliases:\n" + report)

    def test_1_cold_provision_downloads_verifies_and_caches(self):
        durations = []
        for attempt in range(3):
            config = self.new_config()
            started = time.perf_counter()
            self.provision(config)
            durations.append((time.perf_counter() - started) * 1000)
            self.assertEqual(
                sha256_of(self.cached_binary(config)), self.asset_sha,
                "the cached bytes are not the pinned asset",
            )
            if not IS_WINDOWS:
                par = Path(str(self.cached_binary(config)) + ".par")
                for path in (config / "briefing", config / "briefing" / "bin", self.cache_dir(config), par):
                    self.assertTrue(path.is_dir(), path)
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700, str(path))
                self.assertEqual(stat.S_IMODE(self.cached_binary(config).stat().st_mode), 0o700)
        # The loopback fixture, not the network.
        report_timing("cold_provision_file_fixture", durations)

    def test_2_warm_subagent_start_briefs_with_the_skill_text(self):
        config = self.new_config()
        self.provision(config)
        requests = len(self.server.paths)
        result = self.run_entry(("hook", "subagent-start"), config, self.subagent_payload())
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        specific = json.loads(result.stdout.decode("utf-8"))["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "SubagentStart")
        self.assertIn(MARKER, specific["additionalContext"])
        self.assertEqual(len(self.server.paths), requests, "a warm hook downloaded again")

    def test_3_pre_tool_use_denies_an_unknown_skill(self):
        config = self.new_config()
        self.provision(config)
        self.add_broken_agent()
        result = self.run_entry(
            ("hook", "pre-tool-use"),
            config,
            self.payload("PreToolUse", tool_name="Agent", tool_input={"subagent_type": "broken"}),
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        output = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_4_doctor_tsv_in_the_project_directory(self):
        config = self.new_config()
        self.provision(config)
        self.assert_doctor_ok(self.run_entry(("doctor", "--tsv"), config, cwd=self.project))

    @expected_failure_on_windows
    def test_5_doctor_tsv_with_cwd_through_argv(self):
        # k8: on Windows argv reaches Perl in the ANSI code page. An unexpected success there
        # shows up, so this marker is removed when k8 is done.
        config = self.new_config()
        self.provision(config)
        result = self.run_entry(("doctor", "--tsv", "--cwd", str(self.project)), config, cwd=self.root)
        self.assert_doctor_ok(result)

    def test_6_version_and_exit_status_pass_through(self):
        config = self.new_config()
        self.provision(config)
        version = self.run_entry(("--version",), config)
        self.assertEqual(version.returncode, 0, version.stderr.decode("utf-8", "replace"))
        self.assertRegex(version.stdout.decode("utf-8"), r"^briefing \S+\r?\n$")
        unknown = self.run_entry(("nope",), config)
        self.assertEqual(unknown.returncode, 2, unknown.stderr.decode("utf-8", "replace"))
        self.assertEqual(unknown.stdout, b"")
        self.assertNotEqual(unknown.stderr.strip(), b"", "the error text did not reach stderr")

    def test_7_tampered_binary_is_never_run(self):
        config = self.new_config()
        self.provision(config)
        cached = self.cached_binary(config)
        data = bytearray(cached.read_bytes())
        data[len(data) // 2] ^= 0xFF
        cached.write_bytes(bytes(data))
        result = self.run_entry(("hook", "subagent-start"), config, self.subagent_payload())
        # No Python or Perl on PATH: not the binary's briefing, only the single warning.
        self.assert_safe_warning(result)
        self.assertNotIn(MARKER, result.stdout.decode("utf-8"))

    def test_8_failed_download_leaves_no_executable_cache_entry(self):
        config = self.new_config()
        result = self.run_entry(
            ("hook", "session-start"),
            config,
            self.payload("SessionStart", source="startup"),
            server=self.empty_server,
        )
        self.assert_safe_warning(result)
        self.assertGreater(len(self.empty_server.paths), 0, "the empty location was never asked")
        binary_root = config / "briefing" / "bin"
        leftovers = (
            [p for p in binary_root.rglob("*") if p.is_file() and not p.name.endswith(".failed-at")]
            if binary_root.exists()
            else []
        )
        self.assertEqual(leftovers, [])
        self.assertFalse(self.cached_binary(config).exists())

    def test_9_timings_for_k6(self):
        config = self.new_config()
        self.provision(config)
        payload = self.subagent_payload()
        series = {
            "warm_hook_subagent_start": [],
            "cold_par_hook_subagent_start": [],
            "python_hook_subagent_start": [],
        }

        for _ in range(10):
            started = time.perf_counter()
            result = self.run_entry(("hook", "subagent-start"), config, payload)
            series["warm_hook_subagent_start"].append((time.perf_counter() - started) * 1000)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertIn(MARKER, result.stdout.decode("utf-8"))

        par = Path(str(self.cached_binary(config)) + ".par")
        for _ in range(3):
            if par.exists():
                remove_tree(par)
            started = time.perf_counter()
            result = self.run_entry(("hook", "subagent-start"), config, payload)
            series["cold_par_hook_subagent_start"].append((time.perf_counter() - started) * 1000)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
            self.assertIn(MARKER, result.stdout.decode("utf-8"))

        # For comparison: the Python reference hook with the full PATH.
        python_env = dict(os.environ)
        python_env.update(
            HOME=str(self.home), CLAUDE_CONFIG_DIR=str(config), PYTHONUTF8="1", PYTHONIOENCODING="utf-8"
        )
        for _ in range(10):
            started = time.perf_counter()
            result = subprocess.run(
                [sys.executable, str(self.plugin / "hooks" / "briefing-preload")],
                input=payload.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.project),
                env=python_env,
                timeout=120,
            )
            series["python_hook_subagent_start"].append((time.perf_counter() - started) * 1000)
            self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))

        for name, values in series.items():
            report_timing(name, values)


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        ASSET_PATH = Path(sys.argv.pop(1)).resolve()
    unittest.main()
