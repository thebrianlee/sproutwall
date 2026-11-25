"""The closed `doctor --json` schema (spec section 4.3) and its result rules.

Everything doctor prints with --json is built here, from the constants below.
No other module writes to stdout in --json mode.
"""

import json

SCHEMA_VERSION = 1

PHASES = ("running", "configured", "final")
TIERS = ("A", "B", "C")
KIOSK_STATES = ("on", "off")

# Each id occurs once, in this order.
CHECK_IDS = (
    "platform",
    "docker",
    "image_identity",
    "storage",
    "health",
    "app_bind",
    "bridge_bind",
    "ssh_policy",
    "setup",
    "read_guard",
    "kiosk",
    "temporary_access",
)

STATUSES = ("pass", "fail", "unknown", "not_applicable")
ACTIONS = (
    "none",
    "use_supported_os",
    "verify_release",
    "restore_storage",
    "restrict_ports",
    "confirm_trusted_lan",
    "review_ssh",
    "open_hub",
    "repair_kiosk",
    "remove_agent",
    "retry_local",
)
RESULTS = ("pass", "fail", "unknown")

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_UNKNOWN = 2

# Checks that only apply from a later phase. Every other check applies in
# every phase. These are the only documented omissions (not_applicable).
FIRST_PHASE = {
    "setup": "configured",
    "read_guard": "configured",
    "kiosk": "final",
    "temporary_access": "final",
}

PASS = ("pass", "none")
NOT_APPLICABLE = ("not_applicable", "none")


def fail(action):
    return ("fail", action)


def unknown(action):
    return ("unknown", action)


# What a check reports when it could not finish (an exception, a bad value).
INCOMPLETE = ("unknown", "retry_local")


def is_required(check_id, phase):
    first = FIRST_PHASE.get(check_id)
    if first is None:
        return True
    return PHASES.index(phase) >= PHASES.index(first)


def _canonical(value, allowed):
    """The allowlisted constant equal to value, or None. Never returns value itself."""
    if type(value) is not str:
        return None
    for item in allowed:
        if value == item:
            return item
    return None


def _canonical_outcome(outcome):
    if not isinstance(outcome, tuple) or len(outcome) != 2:
        return None
    status = _canonical(outcome[0], STATUSES)
    action = _canonical(outcome[1], ACTIONS)
    if status is None or action is None:
        return None
    if status in ("pass", "not_applicable"):
        action = "none"
    return (status, action)


def build_report(phase, outcomes):
    """The report dict for phase from {check id: (status, action)}.

    Every value in the result is one of the constants above. A missing or
    malformed outcome becomes unknown/retry_local; a check that does not apply
    to the phase is always not_applicable.
    """
    phase = _canonical(phase, PHASES)
    if phase is None:
        raise ValueError("unknown phase")
    checks = []
    for check_id in CHECK_IDS:
        if not is_required(check_id, phase):
            status, action = NOT_APPLICABLE
        else:
            status, action = _canonical_outcome(outcomes.get(check_id)) or INCOMPLETE
            if status == "not_applicable":
                status, action = INCOMPLETE
        checks.append({"id": check_id, "status": status, "action": action})
    return {"schema": SCHEMA_VERSION, "phase": phase, "result": result_of(checks), "checks": checks}


def result_of(checks):
    """Any fail -> fail; otherwise any required unknown -> unknown; otherwise pass."""
    statuses = [check["status"] for check in checks]
    if "fail" in statuses:
        return "fail"
    if "unknown" in statuses:
        return "unknown"
    return "pass"


def exit_code(report):
    return {"pass": EXIT_PASS, "fail": EXIT_FAIL, "unknown": EXIT_UNKNOWN}[report["result"]]


def fallback_report(phase):
    """The report for a run that inspected nothing (help or usage error with
    --json, crash): every check unknown/retry_local, result unknown (exit 2).
    scripts/sproutwall prints the same object when even the import fails."""
    phase = _canonical(phase, PHASES) or PHASES[0]
    checks = [{"id": check_id, "status": "unknown", "action": "retry_local"} for check_id in CHECK_IDS]
    return {"schema": SCHEMA_VERSION, "phase": phase, "result": "unknown", "checks": checks}


def validate(report):
    """Raise ValueError unless report matches the closed schema exactly."""
    if not isinstance(report, dict) or list(report) != ["schema", "phase", "result", "checks"]:
        raise ValueError("top-level keys")
    if report["schema"] != SCHEMA_VERSION or type(report["schema"]) is not int:
        raise ValueError("schema")
    if _canonical(report["phase"], PHASES) is None or _canonical(report["result"], RESULTS) is None:
        raise ValueError("phase or result")
    checks = report["checks"]
    if not isinstance(checks, list) or [c.get("id") for c in checks if isinstance(c, dict)] != list(CHECK_IDS):
        raise ValueError("check ids")
    for check in checks:
        if list(check) != ["id", "status", "action"]:
            raise ValueError("check keys")
        if _canonical(check["status"], STATUSES) is None or _canonical(check["action"], ACTIONS) is None:
            raise ValueError("check values")
        omitted = not is_required(check["id"], report["phase"])
        if omitted and check["status"] != "not_applicable" and (check["status"], check["action"]) != INCOMPLETE:
            raise ValueError("phase omission")
        if not omitted and check["status"] == "not_applicable":
            raise ValueError("not_applicable is only for phase omissions")
    if report["result"] != result_of(checks):
        raise ValueError("result")


def serialize(report):
    """One line of JSON. Re-validated here so nothing else can reach stdout."""
    validate(report)
    return json.dumps(report, separators=(",", ":"), ensure_ascii=True)


def residual_is_trusted_lan_only(report):
    """True when exit 2 comes only from app_bind/confirm_trusted_lan.

    That action means local inspection completed (listeners, published ports
    and interfaces, IPv4 and IPv6) without finding public exposure.
    unknown/retry_local (incomplete inspection) never qualifies.
    """
    if report.get("result") != "unknown":
        return False
    open_checks = [c for c in report["checks"] if c["status"] in ("fail", "unknown")]
    return len(open_checks) == 1 and open_checks[0] == {
        "id": "app_bind",
        "status": "unknown",
        "action": "confirm_trusted_lan",
    }


def t1t2_may_continue(report, network_prerequisite_affirmed):
    """Continue on exit 2 only when all of these hold:

    - the sole unknown is app_bind/confirm_trusted_lan;
    - local inspection completed without finding public exposure;
    - the operator affirmed the trusted-network prerequisite under decision 3.

    The residual unknown is still recorded; it is not a clean pass. Any other
    unknown or any failure stops.
    """
    return network_prerequisite_affirmed is True and residual_is_trusted_lan_only(report)
