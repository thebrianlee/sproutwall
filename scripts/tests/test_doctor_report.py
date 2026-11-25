"""The closed schema, the result/exit rules and the exit-2 continue rule."""

import io
import json
import unittest
from unittest import mock

from sproutwall_lib import checks, cli, doctor, schema
from sproutwall_lib.system import HttpResponse

from . import fakes
from .fakes import HOME, ROOT, healthy_pi, ok, proc_table


def main(argv, system):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, system=system, root=ROOT, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def all_pass_pi():
    """healthy_pi with the hub bound to loopback, so every check can pass."""
    s = healthy_pi()
    loop = {"3847/tcp": [{"HostIp": "127.0.0.1", "HostPort": "3847"}]}
    s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(ports=loop, port_bindings=loop)))
    s.files["/proc/net/tcp"] = proc_table([("127.0.0.1", 3847, "0A")])
    s.files["/proc/net/tcp6"] = proc_table([], v6=True)
    return s


class ClosedSchemaTests(unittest.TestCase):
    def assert_closed(self, stdout, phase):
        lines = stdout.splitlines()
        self.assertEqual(len(lines), 1, "exactly one JSON object on one line")
        report = json.loads(lines[0])
        self.assertEqual(list(report), ["schema", "phase", "result", "checks"])
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["phase"], phase)
        self.assertIn(report["result"], schema.RESULTS)
        self.assertEqual([c["id"] for c in report["checks"]], list(schema.CHECK_IDS))
        for check in report["checks"]:
            self.assertEqual(list(check), ["id", "status", "action"])
            self.assertIn(check["status"], schema.STATUSES)
            self.assertIn(check["action"], schema.ACTIONS)
        schema.validate(report)
        return report

    def test_every_phase_emits_the_closed_schema(self):
        for phase in schema.PHASES:
            code, out, err = main(["doctor", "--json", "--phase", phase], healthy_pi())
            report = self.assert_closed(out, phase)
            self.assertEqual(err, "")
            self.assertEqual(code, schema.exit_code(report))

    def test_phase_omissions_are_not_applicable(self):
        report = doctor.run_doctor(healthy_pi(), ROOT, "running")
        statuses = {c["id"]: c["status"] for c in report["checks"]}
        for check_id in ("setup", "read_guard", "kiosk", "temporary_access"):
            self.assertEqual(statuses[check_id], "not_applicable")
        report = doctor.run_doctor(healthy_pi(), ROOT, "configured")
        statuses = {c["id"]: c["status"] for c in report["checks"]}
        self.assertEqual((statuses["setup"], statuses["read_guard"]), ("pass", "pass"))
        self.assertEqual((statuses["kiosk"], statuses["temporary_access"]), ("not_applicable", "not_applicable"))
        report = doctor.run_doctor(healthy_pi(), ROOT, "final")
        self.assertNotIn("not_applicable", [c["status"] for c in report["checks"]])

    def test_validate_rejects_anything_outside_the_schema(self):
        good = doctor.run_doctor(healthy_pi(), ROOT, "final")
        bad_reports = []
        extra = json.loads(json.dumps(good))
        extra["host"] = "hub"
        bad_reports.append(extra)
        extra_check_key = json.loads(json.dumps(good))
        extra_check_key["checks"][0]["detail"] = "x"
        bad_reports.append(extra_check_key)
        missing = json.loads(json.dumps(good))
        missing["checks"].pop()
        bad_reports.append(missing)
        swapped = json.loads(json.dumps(good))
        swapped["checks"][0], swapped["checks"][1] = swapped["checks"][1], swapped["checks"][0]
        bad_reports.append(swapped)
        duplicate = json.loads(json.dumps(good))
        duplicate["checks"][1] = dict(duplicate["checks"][0])
        bad_reports.append(duplicate)
        bad_value = json.loads(json.dumps(good))
        bad_value["checks"][0]["action"] = "see logs"
        bad_reports.append(bad_value)
        wrong_result = json.loads(json.dumps(good))
        wrong_result["result"] = "pass"
        bad_reports.append(wrong_result)
        for report in bad_reports:
            with self.assertRaises(ValueError):
                schema.serialize(report)

    def test_build_report_only_admits_allowlisted_values(self):
        report = schema.build_report(
            "running",
            {
                "platform": ("pass", "retry_local"),  # pass always carries action none
                "docker": ("fail", "a message with a path /home/pi"),
                "image_identity": ("ok", "none"),
                "storage": "pass",
                "health": ("not_applicable", "none"),  # not a documented omission
                "setup": ("fail", "open_hub"),  # not required in running
            },
        )
        by_id = {c["id"]: (c["status"], c["action"]) for c in report["checks"]}
        self.assertEqual(by_id["platform"], ("pass", "none"))
        for check_id in ("docker", "image_identity", "storage", "health", "app_bind"):
            self.assertEqual(by_id[check_id], ("unknown", "retry_local"), check_id)
        self.assertEqual(by_id["setup"], ("not_applicable", "none"))

    def test_a_crashing_check_is_unknown_retry_local(self):
        def boom(ctx):
            raise RuntimeError("Riley's calendar at /home/pi failed")

        with mock.patch.dict(checks.CHECKS, {"storage": boom}):
            report = doctor.run_doctor(healthy_pi(), ROOT, "running")
        self.assertEqual(report["checks"][3], {"id": "storage", "status": "unknown", "action": "retry_local"})


class ResultRuleTests(unittest.TestCase):
    def test_all_pass_is_pass_exit_0(self):
        for phase in schema.PHASES:
            report = doctor.run_doctor(all_pass_pi(), ROOT, phase)
            self.assertEqual((report["result"], schema.exit_code(report)), ("pass", 0), report)

    def test_any_fail_is_fail_exit_1_even_with_unknowns(self):
        s = healthy_pi()  # app_bind unknown
        s.http_map[("GET", "/api/health")] = HttpResponse(503, b'{"ok":false,"code":"db_newer"}')
        report = doctor.run_doctor(s, ROOT, "running")
        self.assertEqual((report["result"], schema.exit_code(report)), ("fail", 1))
        code, out, _ = main(["doctor", "--json", "--phase", "running"], s)
        self.assertEqual((code, json.loads(out)["result"]), (1, "fail"))

    def test_required_unknown_is_unknown_exit_2(self):
        report = doctor.run_doctor(healthy_pi(), ROOT, "running")
        self.assertEqual((report["result"], schema.exit_code(report)), ("unknown", 2))

    def test_not_applicable_does_not_count(self):
        s = all_pass_pi()
        s.http_map[("GET", "/api/health")] = fakes.health_response(setup=False)  # would fail from configured
        report = doctor.run_doctor(s, ROOT, "running")
        self.assertEqual(report["result"], "pass")
        self.assertEqual(doctor.run_doctor(s, ROOT, "configured")["result"], "fail")

    def test_result_of(self):
        mk = lambda *statuses: [{"id": "x", "status": st, "action": "none"} for st in statuses]  # noqa: E731
        self.assertEqual(schema.result_of(mk("pass", "unknown", "fail")), "fail")
        self.assertEqual(schema.result_of(mk("pass", "unknown", "not_applicable")), "unknown")
        self.assertEqual(schema.result_of(mk("pass", "not_applicable")), "pass")


class T1T2RuleTests(unittest.TestCase):
    def test_sole_trusted_lan_unknown_may_continue_only_when_affirmed(self):
        report = doctor.run_doctor(healthy_pi(), ROOT, "final")
        self.assertEqual(schema.exit_code(report), 2)
        self.assertTrue(schema.residual_is_trusted_lan_only(report))
        self.assertTrue(schema.t1t2_may_continue(report, True))
        self.assertFalse(schema.t1t2_may_continue(report, False))
        self.assertFalse(schema.t1t2_may_continue(report, "yes"))

    def test_incomplete_interface_inspection_stops(self):
        s = healthy_pi()
        s.set(["ip", "-j", "addr", "show"], ok(rc=1))
        report = doctor.run_doctor(s, ROOT, "final")
        self.assertEqual(report["checks"][5], {"id": "app_bind", "status": "unknown", "action": "retry_local"})
        self.assertEqual(schema.exit_code(report), 2)
        self.assertFalse(schema.t1t2_may_continue(report, True))

    def test_any_other_unknown_stops(self):
        s = healthy_pi()
        s.http_map[("GET", "/api/health")] = HttpResponse(None, error="timeout")
        report = doctor.run_doctor(s, ROOT, "final")
        self.assertEqual(schema.exit_code(report), 2)
        self.assertFalse(schema.t1t2_may_continue(report, True))

    def test_any_failure_stops(self):
        s = healthy_pi()
        s.files[HOME + "/.config/labwc/autostart"] = ""
        report = doctor.run_doctor(s, ROOT, "final")
        self.assertEqual(schema.exit_code(report), 1)
        self.assertFalse(schema.t1t2_may_continue(report, True))

    def test_a_clean_pass_is_not_the_exception(self):
        report = doctor.run_doctor(all_pass_pi(), ROOT, "final")
        self.assertFalse(schema.residual_is_trusted_lan_only(report))

    def test_human_output_names_the_residual(self):
        code, out, err = main(["doctor", "--phase", "running"], healthy_pi())
        self.assertEqual(code, 2)
        self.assertIn("app_bind / confirm_trusted_lan", out)
        self.assertIn("not a clean pass", out)


class CliTests(unittest.TestCase):
    def test_usage_errors_still_emit_one_json_object_and_echo_nothing(self):
        for argv in (
            ["doctor", "--json"],
            ["doctor", "--json", "--phase", "Riley"],
            ["doctor", "--json", "--phase", "final", "--tier", "Quinn"],
            ["doctor", "--json", "--phase", "final", "--kiosk"],
            ["doctor", "--json", "--phase", "final", "--token=sk-canary"],
        ):
            code, out, err = main(argv, healthy_pi())
            self.assertEqual(code, 2, argv)
            report = json.loads(out)
            schema.validate(report)
            self.assertEqual(report["result"], "unknown")
            for value in ("Riley", "Quinn", "sk-canary", "token"):
                self.assertNotIn(value, out + err)

    def test_json_help_and_usage_print_the_fixed_object(self):
        for argv in (
            ["doctor", "--json", "--help"],
            ["doctor", "-h", "--json", "--phase", "final"],
            ["--json"],
            ["--help", "--json"],
            ["verify-image", "--json", "--source-sha", "0" * 40],
            ["unknown-command", "--json"],
        ):
            code, out, err = main(argv, healthy_pi())
            self.assertEqual(code, 2, argv)
            self.assertEqual(err, "", argv)
            report = json.loads(out)
            self.assertEqual(report, schema.fallback_report(report["phase"]), argv)
            self.assertEqual({(c["status"], c["action"]) for c in report["checks"]}, {("unknown", "retry_local")})
        self.assertEqual(json.loads(main(["doctor", "--json", "--help", "--phase", "final"], healthy_pi())[1])["phase"], "final")

    def test_fallback_is_valid_closed_schema(self):
        for phase in schema.PHASES + ("bogus",):
            report = schema.fallback_report(phase)
            schema.validate(report)
            self.assertEqual(schema.exit_code(report), 2)

    def test_fallback_keeps_a_valid_requested_phase(self):
        code, out, _ = main(["doctor", "--json", "--phase", "final", "--tier", "D"], healthy_pi())
        self.assertEqual(json.loads(out)["phase"], "final")

    def test_tier_is_not_printed(self):
        _, out, _ = main(["doctor", "--json", "--phase", "running", "--tier", "B"], healthy_pi())
        self.assertNotIn('"B"', out)
        self.assertNotIn("tier", out)

    def test_unexpected_crash_still_emits_json(self):
        with mock.patch.object(cli, "run_doctor", side_effect=RuntimeError("Quinn at /home/pi")):
            code, out, err = main(["doctor", "--json", "--phase", "configured"], healthy_pi())
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)["phase"], "configured")
        self.assertNotIn("Quinn", out + err)

    def test_help_and_unknown_commands(self):
        code, out, _ = main(["--help"], healthy_pi())
        self.assertEqual(code, 0)
        self.assertIn("doctor", out)
        code, out, err = main(["install-riley"], healthy_pi())
        self.assertEqual(code, 2)
        self.assertNotIn("riley", (out + err).lower())


if __name__ == "__main__":
    unittest.main()
