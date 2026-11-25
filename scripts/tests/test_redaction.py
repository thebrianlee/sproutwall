"""Doctor redaction canaries.

Fictional names, an iCal URL with a query token, a PIN, an API key and a
cookie are seeded into command stdout and stderr, file contents, exception
messages, the health JSON and gh's output, on success and failure paths.
None may appear on stdout or stderr, and --json stdout must stay one
closed-schema object. Every scenario also asserts that it reached the code
path whose output it seeds (the fake was called), so a canary test cannot
pass by stopping early. The canaries are assembled from pieces so secret
scanners do not flag them.
"""

import contextlib
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest import mock

from sproutwall_lib import attestation, checks, cli, compose
from sproutwall_lib.system import CommandResult, HttpResponse

from . import fakes
from .fakes import HOME, ROOT, healthy_pi

ICAL_TOKEN = "canary" + "icaltoken" + "7q"
API_KEY = "sk-ant-" + "api03-" + "canaryQuinnKey"
COOKIE = "sw_device=" + "canary" + "cookieRiley"
PIN = "482915"
ICAL = "webcal://calendar.example.test/ical/basic.ics?token=" + ICAL_TOKEN
CANARIES = ("Riley", "Quinn", ICAL, ICAL_TOKEN, "?token=", PIN, API_KEY, "canaryQuinnKey", COOKIE, "cookieRiley")
SEED = "household Riley and Quinn; calendar %s; pin %s; key %s; cookie %s" % (ICAL, PIN, API_KEY, COOKIE)
HUB_IP = "10.66.77.88"  # the seeded container address must not be printed either

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SCRIPTS, "sproutwall")
REPO = os.path.dirname(SCRIPTS)

# The closed schema, written out here on purpose instead of
# imported from sproutwall_lib.schema, so a change there cannot also change
# what this test expects.
EXPECTED_KEYS = ["schema", "phase", "result", "checks"]
EXPECTED_CHECK_KEYS = ["id", "status", "action"]
EXPECTED_IDS = [
    "platform", "docker", "image_identity", "storage", "health", "app_bind",
    "bridge_bind", "ssh_policy", "setup", "read_guard", "kiosk", "temporary_access",
]
EXPECTED_PHASES = ["running", "configured", "final"]
EXPECTED_TIERS = ["A", "B", "C"]
EXPECTED_RESULTS = {"pass", "fail", "unknown"}
EXPECTED_STATUSES = {"pass", "fail", "unknown", "not_applicable"}
EXPECTED_ACTIONS = {
    "none", "use_supported_os", "verify_release", "restore_storage", "restrict_ports",
    "confirm_trusted_lan", "review_ssh", "open_hub", "repair_kiosk", "remove_agent", "retry_local",
}


def assert_closed_schema(test, stdout):
    lines = stdout.splitlines()
    test.assertEqual(len(lines), 1, "exactly one JSON object")
    report = json.loads(lines[0])
    test.assertEqual(list(report), EXPECTED_KEYS)
    test.assertIs(type(report["schema"]), int)
    test.assertEqual(report["schema"], 1)
    test.assertIn(report["phase"], EXPECTED_PHASES)
    test.assertIn(report["result"], EXPECTED_RESULTS)
    test.assertEqual([check.get("id") for check in report["checks"]], EXPECTED_IDS)
    for check in report["checks"]:
        test.assertEqual(list(check), EXPECTED_CHECK_KEYS)
        test.assertIn(check["status"], EXPECTED_STATUSES)
        test.assertIn(check["action"], EXPECTED_ACTIONS)
    statuses = {check["status"] for check in report["checks"]}
    expected = "fail" if "fail" in statuses else "unknown" if "unknown" in statuses else "pass"
    test.assertEqual(report["result"], expected)


def assert_clean(test, out, err, json_mode):
    text = out + err
    for canary in CANARIES + (HUB_IP,):
        test.assertNotIn(canary, text)
        test.assertNotIn(canary.lower(), text.lower())
    if json_mode:
        assert_closed_schema(test, out)


def run_in_process(argv, system):
    """cli.main with its own streams, while also capturing the real process
    streams, the root logger (DEBUG) and warnings: anything written outside
    the given streams shows up in the third value."""
    out, err = io.StringIO(), io.StringIO()
    stray_out, stray_err, log = io.StringIO(), io.StringIO(), io.StringIO()
    handler = logging.StreamHandler(log)
    handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    old_level = root_logger.level
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)
    try:
        with warnings.catch_warnings(record=True) as caught, contextlib.redirect_stdout(stray_out), contextlib.redirect_stderr(stray_err):
            warnings.simplefilter("always")
            code = cli.main(argv, system=system, root=ROOT, out=out, err=err)
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(old_level)
    stray = stray_out.getvalue() + stray_err.getvalue() + log.getvalue() + "".join(str(w.message) for w in caught)
    return code, out.getvalue(), err.getvalue(), stray


class SeededSystem(fakes.FakeSystem):
    """Every command also writes the seed to stderr."""

    def run(self, argv, timeout=15.0, env=None):
        result = super().run(argv, timeout, env)
        return CommandResult(result.rc, result.out, SEED, result.missing, result.timed_out)


def seeded_pi():
    """A healthy Pi whose every input carries the seed, and whose HTTP is reached."""
    base = healthy_pi()
    s = SeededSystem()
    s.__dict__.update({k: v for k, v in base.__dict__.items() if k != "calls"})
    s.calls = []
    s.files["/proc/device-tree/model"] = ("Raspberry Pi 5 Model B " + SEED).encode()
    s.files[fakes.COMPOSE] = "# " + SEED + "\n" + fakes.compose_text()
    s.files["/etc/ssh/sshd_config"] = fakes.SSHD_CONFIG + "# AllowUsers Riley Quinn\nBanner /etc/" + ICAL_TOKEN + "\n"
    s.files[HOME + "/.config/labwc/autostart"] += "# " + SEED + "\n"
    mounts = [
        {"Type": "volume", "Name": "sproutwall_familyhub-data", "Source": "/var/lib/Riley", "Destination": "/data", "RW": True},
        {"Type": "bind", "Source": "/home/Quinn/" + ICAL_TOKEN, "Destination": "/photos", "RW": True},
    ]
    s.set(["docker", "inspect", "--type", "container"], CommandResult(0, fakes.container_json(mounts=mounts, env=[SEED]), SEED))
    hub = json.loads(fakes.hub_state(addresses=(HUB_IP, "")))
    hub["labels"] = {"riley": SEED}
    s.set(["docker", "inspect", "--type", "container", "--format", checks.HUB_FORMAT], CommandResult(0, json.dumps(hub), SEED))
    s.set(["docker", "image", "inspect"], CommandResult(0, fakes.image_json(labels={"riley": SEED}), SEED))
    s.set(["docker", "version", "--format", "{{.Server.Version}}"], CommandResult(0, "27.3.1 " + SEED, SEED))
    config = json.loads(fakes.compose_config_json())
    config["x-seed"] = SEED
    s.set(compose.config_argv(fakes.COMPOSE), CommandResult(0, json.dumps(config), SEED))
    s.set(
        ["ip", "-j", "addr", "show"],
        CommandResult(0, json.dumps([{"ifname": "Riley-wlan", "label": SEED, "addr_info": [{"family": "inet", "local": "192.168.1.50", "label": SEED}]}]), ""),
    )
    health = {"ok": True, "version": "0.1.0-preview.0", "schema": 3, "setup": True, "household": "Riley", "calendar": ICAL, "pin": PIN, "key": API_KEY, "cookie": COOKIE}
    s.http_map[("GET", "/api/health")] = HttpResponse(200, json.dumps(health).encode())
    s.http_map[("GET", "/api/modules")] = HttpResponse(401, SEED.encode())
    return s


def seeded_http_failure():
    """Docker says healthy, then the hub answers with seeded errors or raises them."""
    s = seeded_pi()
    s.http_map[("GET", "/api/health")] = HttpResponse(503, json.dumps({"ok": False, "code": SEED, "detail": API_KEY}).encode())
    s.http_map[("GET", "/api/modules")] = OSError(SEED)
    return s


def seeded_http_exception():
    s = seeded_pi()
    s.http_map[("GET", "/api/health")] = RuntimeError(SEED)
    return s


class FailingSystem(fakes.FakeSystem):
    """Every command fails with the seed; files, which and HTTP raise it."""

    def run(self, argv, timeout=15.0, env=None):
        self.calls.append((tuple(argv), env))
        if argv[0] == "ip":
            raise RuntimeError(SEED)
        return CommandResult(1, SEED, SEED)

    def _file(self, path):
        raise PermissionError(13, SEED, path + SEED)

    def which(self, name, extra_dirs=()):
        raise RuntimeError(SEED)


def reached_commands(test, system, *names):
    called = {argv[0] for argv, _ in system.calls}
    for name in names:
        test.assertIn(name, called)


def reached_hub(test, system, phase):
    paths = [path for _, path, _, _ in system.http_calls]
    test.assertIn("/api/health", paths, phase)
    if phase != "running":
        test.assertIn("/api/modules", paths, phase)


class InProcessCanaryTests(unittest.TestCase):
    def run_all(self, make_system, expect_codes, reached):
        for phase in EXPECTED_PHASES:
            for tier in EXPECTED_TIERS:
                for json_mode in (True, False):
                    argv = ["doctor", "--phase", phase, "--tier", tier] + (["--json"] if json_mode else [])
                    system = make_system()
                    code, out, err, stray = run_in_process(argv, system)
                    self.assertIn(code, expect_codes, argv)
                    assert_clean(self, out, err, json_mode)
                    self.assertEqual(stray, "", "nothing outside the given streams, no log record, no warning")
                    reached(system, phase)

    def test_success_path(self):
        def reached(system, phase):
            reached_commands(self, system, "docker", "ip", "systemctl", "dpkg")
            reached_hub(self, system, phase)

        self.run_all(seeded_pi, (0, 2), reached)

    def test_hub_error_answers(self):
        self.run_all(seeded_http_failure, (1, 2), lambda system, phase: reached_hub(self, system, phase))

    def test_hub_request_raising(self):
        self.run_all(seeded_http_exception, (1, 2), lambda system, phase: reached_hub(self, system, phase))

    def test_failing_commands_and_files(self):
        # The unreadable sshd config stops ssh_policy before systemctl (unknown), by design.
        self.run_all(FailingSystem, (1,), lambda system, phase: reached_commands(self, system, "docker", "ip", "dpkg"))

    def test_verify_image_gh_output(self):
        bundles = [{"seed": SEED}]
        for gh_result in (
            CommandResult(0, SEED, SEED),
            CommandResult(1, SEED, SEED),
            CommandResult(None, timed_out=True),
            RuntimeError(SEED),
        ):
            s = SeededSystem()
            s.files[fakes.COMPOSE] = "# " + SEED + "\n" + fakes.compose_text()
            s.set(compose.config_argv(fakes.COMPOSE), CommandResult(0, fakes.compose_config_json(), SEED))
            s.set(["gh", "--version"], CommandResult(0, "gh version 2.89.0 (2026-03-26)\n", SEED))
            s.set(["gh", "attestation", "verify"], gh_result)
            with mock.patch.object(attestation, "fetch_bundles", lambda digest, opener=None: bundles):
                _, out, err, stray = run_in_process(["verify-image", "--source-sha", fakes.SOURCE_SHA], s)
            self.assertIn(("gh", "attestation", "verify"), [argv[:3] for argv, _ in s.calls], gh_result)
            assert_clean(self, out, err, False)
            self.assertEqual(stray, "")


FAKE_TOOL = r'''#!%(python)s
import os, sys
name = os.path.basename(sys.argv[0])
args = sys.argv[1:]
with open(%(log)r, "a", encoding="utf-8") as log:
    log.write(name + " " + " ".join(args[:2]) + "\n")
seed = %(seed)r
sys.stderr.write(seed)
if name == "docker" and "config" in args:
    sys.stdout.write(%(config)r)
    sys.exit(0)
if name == "gh" and args[:1] == ["--version"]:
    sys.stdout.write("gh version 2.89.0 (2026-03-26)\n")
    sys.exit(0)
sys.stdout.write(seed)
sys.exit(int(os.environ.get("FAKE_GH_RC", "1")) if name == "gh" else 1)
'''


class EndToEndCanaryTests(unittest.TestCase):
    """The real script, real subprocesses: fake docker, ip, systemctl, dpkg
    and gh on PATH print the seed (and log that they ran); HOME holds seeded
    files; the environment holds seeded variables."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        bin_dir = os.path.join(root, "bin")
        home = os.path.join(root, "home")
        self.log = os.path.join(root, "calls.log")
        os.makedirs(bin_dir)
        os.makedirs(os.path.join(home, ".config", "labwc"))
        os.makedirs(os.path.join(home, ".codex"))
        with open(os.path.join(home, ".config", "labwc", "autostart"), "w", encoding="utf-8") as handle:
            handle.write("# " + SEED + "\n")
        tool = FAKE_TOOL % {"python": sys.executable, "log": self.log, "seed": SEED, "config": fakes.compose_config_json()}
        for name in ("docker", "ip", "systemctl", "dpkg", "gh"):
            path = os.path.join(bin_dir, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(tool)
            os.chmod(path, 0o755)
        self.env = dict(os.environ)
        self.env.update(
            {
                "PATH": bin_dir + os.pathsep + os.environ.get("PATH", ""),
                "HOME": home,
                "GH_TOKEN": API_KEY,
                "SPROUTWALL_DB": "/data/Riley.db",
                "ICAL_URL": ICAL,
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, script=SCRIPT, env=None, cwd=REPO):
        proc = subprocess.run(
            [sys.executable, script] + list(args),
            cwd=cwd,
            env=env or self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        return proc.returncode, proc.stdout.decode(), proc.stderr.decode()

    def ran(self):
        if not os.path.exists(self.log):
            return set()
        with open(self.log, encoding="utf-8") as handle:
            return {line.split()[0] for line in handle if line.strip()}

    def test_doctor_json_and_human(self):
        for phase in EXPECTED_PHASES:
            code, out, err = self.run_script("doctor", "--json", "--phase", phase, "--tier", "B")
            self.assertIn(code, (1, 2))
            assert_clean(self, out, err, True)
            self.assertEqual(err, "")
            code, out, err = self.run_script("doctor", "--phase", phase)
            assert_clean(self, out, err, False)
        # Only tools doctor queries on every host: whether systemctl or dpkg run
        # depends on the host (a readable sshd config, a 64-bit CPU), and the
        # real sockets on 22 or 3847 must not change the result either.
        self.assertTrue({"docker", "ip"} <= self.ran(), self.ran())

    def test_verify_image_reaches_gh(self):
        repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(os.path.join(repo, "scripts"))
        shutil.copy(SCRIPT, os.path.join(repo, "scripts", "sproutwall"))
        shutil.copytree(os.path.join(SCRIPTS, "sproutwall_lib"), os.path.join(repo, "scripts", "sproutwall_lib"))
        with open(os.path.join(repo, compose.PREVIEW_COMPOSE), "w", encoding="utf-8") as handle:
            handle.write("# " + SEED + "\n" + fakes.compose_text())
        bundle = os.path.join(self.tmp.name, "Riley-bundle.jsonl")
        with open(bundle, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"seed": SEED}) + "\n")
        script = os.path.join(repo, "scripts", "sproutwall")
        for rc, expected in (("1", 1), ("0", 0)):
            env = dict(self.env, FAKE_GH_RC=rc)
            code, out, err = self.run_script("verify-image", "--source-sha", fakes.SOURCE_SHA, "--bundle", bundle, script=script, env=env, cwd=repo)
            self.assertEqual(code, expected, err)
            assert_clean(self, out, err, False)
        with open(self.log, encoding="utf-8") as handle:
            calls = handle.read()
        self.assertIn("docker compose", calls)
        self.assertIn("gh attestation", calls)

    def test_bad_arguments(self):
        code, out, err = self.run_script("doctor", "--json", "--phase", "Riley", "--pin", PIN)
        self.assertEqual(code, 2)
        assert_clean(self, out, err, True)
        code, out, err = self.run_script("verify-image", "--source-sha", ICAL_TOKEN, "--bundle", "/tmp/Quinn")
        self.assertEqual(code, 2)
        assert_clean(self, out, err, False)

    def test_verify_image_refuses_the_committed_placeholder(self):
        code, out, err = self.run_script("verify-image", "--source-sha", fakes.SOURCE_SHA)
        self.assertEqual(code, 2)
        self.assertIn("placeholder", err)
        assert_clean(self, out, err, False)


if __name__ == "__main__":
    unittest.main()
