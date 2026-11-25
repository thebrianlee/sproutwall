"""Each doctor check's pass, fail and unknown branches, from fake host output."""

import os
import unittest

from sproutwall_lib import checks, compose
from sproutwall_lib.checks import Context
from sproutwall_lib.system import CommandResult, HttpResponse

from . import fakes
from .fakes import COMPOSE, HOME, ROOT, exec_key, healthy_pi, ok, proc_table, ssh_on

PASS = ("pass", "none")


def run(check, system, phase="running", tier="A", kiosk="on", outcomes=None):
    ctx = Context(system, ROOT, phase, tier, kiosk)
    ctx.outcomes.update(outcomes or {})
    return getattr(checks, "check_" + check)(ctx)


class PlatformTests(unittest.TestCase):
    def test_pass_on_arm64_pi(self):
        self.assertEqual(run("platform", healthy_pi()), PASS)

    def test_pass_on_arm64_board_that_is_not_a_pi(self):
        s = healthy_pi()
        del s.files["/proc/device-tree/model"]
        self.assertEqual(run("platform", s), PASS)

    def test_pass_on_amd64(self):
        s = healthy_pi()
        s.arch = "x86_64"
        s.set(["dpkg", "--print-architecture"], ok("amd64\n"))
        self.assertEqual(run("platform", s), PASS)

    def test_pass_on_64_bit_linux_without_dpkg(self):
        s = healthy_pi()
        s.set(["dpkg", "--print-architecture"], CommandResult(None, missing=True))
        self.assertEqual(run("platform", s), PASS)

    def test_fail_on_32_bit_cpu_or_kernel(self):
        for machine in ("armv7l", "armv6l", "i686"):
            s = healthy_pi()
            s.arch = machine
            self.assertEqual(run("platform", s), ("fail", "use_supported_os"), machine)

    def test_fail_on_64_bit_kernel_with_32_bit_userland(self):
        s = healthy_pi()
        s.set(["dpkg", "--print-architecture"], ok("armhf\n"))
        self.assertEqual(run("platform", s), ("fail", "use_supported_os"))
        s = healthy_pi()
        s.arch = "x86_64"
        s.set(["dpkg", "--print-architecture"], ok("i386\n"))
        self.assertEqual(run("platform", s), ("fail", "use_supported_os"))
        s = healthy_pi()
        s.set(["dpkg", "--print-architecture"], CommandResult(None, missing=True))
        s.bits = "32bit"
        self.assertEqual(run("platform", s), ("fail", "use_supported_os"))

    def test_fail_when_not_linux(self):
        s = healthy_pi()
        s.os_name = "Darwin"
        s.arch = "arm64"
        self.assertEqual(run("platform", s), ("fail", "use_supported_os"))

    def test_unknown_when_architecture_unreadable(self):
        s = healthy_pi()
        s.arch = ""
        self.assertEqual(run("platform", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["dpkg", "--print-architecture"], ok(rc=2))
        self.assertEqual(run("platform", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["dpkg", "--print-architecture"], CommandResult(None, timed_out=True))
        self.assertEqual(run("platform", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["dpkg", "--print-architecture"], CommandResult(None, missing=True))
        s.bits = ""
        self.assertEqual(run("platform", s), ("unknown", "retry_local"))


class DockerTests(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(run("docker", healthy_pi()), PASS)

    def test_fail_without_docker_or_compose(self):
        s = healthy_pi()
        s.set(["docker", "compose", "version", "--short"], CommandResult(None, missing=True))
        self.assertEqual(run("docker", s), ("fail", "use_supported_os"))
        s = healthy_pi()
        s.set(["docker", "compose", "version", "--short"], ok("", "not a docker command", rc=1))
        self.assertEqual(run("docker", s), ("fail", "use_supported_os"))

    def test_unknown_when_daemon_unreachable(self):
        s = healthy_pi()
        s.set(["docker", "version", "--format", "{{.Server.Version}}"], ok("", "permission denied", rc=1))
        self.assertEqual(run("docker", s), ("unknown", "retry_local"))


class ImageIdentityTests(unittest.TestCase):
    def test_pass_by_repo_digest(self):
        self.assertEqual(run("image_identity", healthy_pi()), PASS)

    def test_pass_with_containerd_store_image_id(self):
        s = healthy_pi()
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(image=fakes.DIGEST)))
        s.set(["docker", "image", "inspect"], ok(fakes.image_json(id=fakes.DIGEST, repo_digests=[])))
        self.assertEqual(run("image_identity", s), PASS)

    def test_fail_on_placeholder_tag_or_other_repo(self):
        for reference in (
            '"ghcr.io/thebrianlee/sproutwall:preview@sha256:<published-index-digest-hex>"',
            "ghcr.io/thebrianlee/sproutwall:preview",
            "ghcr.io/someone/sproutwall@" + fakes.DIGEST,
        ):
            s = healthy_pi()
            s.files[COMPOSE] = fakes.compose_text(reference)
            self.assertEqual(run("image_identity", s), ("fail", "verify_release"), reference)

    def test_effective_compose_must_be_the_pinned_single_service(self):
        for config in (
            fakes.compose_config_json(extra_services={"sidecar": {"image": "busybox"}}),
            fakes.compose_config_json(build={"context": "."}),
            fakes.compose_config_json(image="ghcr.io/thebrianlee/sproutwall@sha256:" + "f" * 64),
            fakes.compose_config_json(image="ghcr.io/thebrianlee/sproutwall:preview"),
        ):
            s = healthy_pi()
            s.set(compose.config_argv(COMPOSE), ok(config))
            self.assertEqual(run("image_identity", s), ("fail", "verify_release"), config)

    def test_fail_on_interpolated_image_line(self):
        s = healthy_pi()
        s.files[COMPOSE] = fakes.compose_text('"${SPROUTWALL_IMAGE:-ghcr.io/thebrianlee/sproutwall@' + fakes.DIGEST + '}"')
        self.assertEqual(run("image_identity", s), ("fail", "verify_release"))

    def test_unknown_when_compose_config_is_unavailable(self):
        s = healthy_pi()
        s.set(compose.config_argv(COMPOSE), CommandResult(None, missing=True))
        self.assertEqual(run("image_identity", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(compose.config_argv(COMPOSE), ok("", "error", rc=1))
        self.assertEqual(run("image_identity", s), ("unknown", "retry_local"))

    def test_fail_when_running_image_is_not_the_pinned_index(self):
        s = healthy_pi()
        s.set(["docker", "image", "inspect"], ok(fakes.image_json(repo_digests=["sproutwall-family-hub@sha256:" + "c" * 64])))
        self.assertEqual(run("image_identity", s), ("fail", "verify_release"))

    def test_fail_on_wrong_platform_manifest(self):
        s = healthy_pi()
        s.set(["docker", "image", "inspect"], ok(fakes.image_json(arch="amd64")))
        self.assertEqual(run("image_identity", s), ("fail", "verify_release"))

    def test_fail_without_a_container(self):
        s = healthy_pi()
        s.set(["docker", "compose", "-f", COMPOSE, "ps", "--all", "--quiet"], ok(""))
        self.assertEqual(run("image_identity", s), ("fail", "verify_release"))

    def test_unknown_when_docker_or_files_cannot_be_read(self):
        s = healthy_pi()
        s.set(["docker", "compose", "-f", COMPOSE, "ps", "--all", "--quiet"], ok("", "denied", rc=1))
        self.assertEqual(run("image_identity", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.files[COMPOSE] = PermissionError(13, "denied")
        self.assertEqual(run("image_identity", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["docker", "image", "inspect"], ok("", "boom", rc=1))
        self.assertEqual(run("image_identity", s), ("unknown", "retry_local"))


class StorageTests(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(run("storage", healthy_pi()), PASS)

    def test_pass_with_pre_rename_database(self):
        s = healthy_pi()
        s.set(exec_key("test", "-f", "/data/sproutwall.db"), ok(rc=1))
        s.set(exec_key("test", "-f", "/data/family-hub.db"), ok())
        s.set(exec_key("test", "-w", "/data/family-hub.db"), ok())
        self.assertEqual(run("storage", s), PASS)

    def test_fail_on_unexpected_mounts(self):
        anonymous = [{"Type": "volume", "Name": "f" * 64, "Destination": "/data", "RW": True},
                     {"Type": "bind", "Destination": "/photos", "RW": True}]
        no_photos = [{"Type": "volume", "Name": "sproutwall_familyhub-data", "Destination": "/data", "RW": True}]
        for mounts in (anonymous, no_photos, []):
            s = healthy_pi()
            s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(mounts=mounts)))
            self.assertEqual(run("storage", s), ("fail", "restore_storage"))

    def test_fail_when_not_writable_or_no_database(self):
        s = healthy_pi()
        s.set(exec_key("test", "-w", "/data"), ok(rc=1))
        self.assertEqual(run("storage", s), ("fail", "restore_storage"))
        s = healthy_pi()
        s.set(exec_key("test", "-f", "/data/sproutwall.db"), ok(rc=1))
        self.assertEqual(run("storage", s), ("fail", "restore_storage"))
        s = healthy_pi()
        s.set(exec_key("test", "-w", "/data/sproutwall.db"), ok(rc=1))
        self.assertEqual(run("storage", s), ("fail", "restore_storage"))

    def test_unknown_when_exec_or_container_unavailable(self):
        s = healthy_pi()
        s.set(exec_key("true"), ok("", "container is not running", rc=1))
        self.assertEqual(run("storage", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(running=False)))
        self.assertEqual(run("storage", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(exec_key("test", "-w", "/data"), ok(rc=126))
        self.assertEqual(run("storage", s), ("unknown", "retry_local"))


class HealthTests(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(run("health", healthy_pi()), PASS)

    def test_fail_on_blocked_database(self):
        s = healthy_pi()
        s.http_map[("GET", "/api/health")] = HttpResponse(503, b'{"ok":false,"code":"db_newer"}')
        self.assertEqual(run("health", s), ("fail", "restore_storage"))

    def test_fail_on_generic_or_wrong_answers(self):
        for status, body in ((503, b'{"ok":false}'), (200, b'{"ok":"true"}'), (200, b"ok"), (302, b""), (401, b"{}")):
            s = healthy_pi()
            s.http_map[("GET", "/api/health")] = HttpResponse(status, body)
            self.assertEqual(run("health", s), ("fail", "retry_local"), (status, body))

    def test_unknown_when_the_container_address_does_not_answer(self):
        for error in ("refused", "timeout", "error"):
            s = healthy_pi()
            s.http_map[("GET", "/api/health")] = HttpResponse(None, error=error)
            self.assertEqual(run("health", s), ("unknown", "retry_local"), error)
            self.assertEqual(len(s.http_calls), 1, "no second try anywhere else")

    def test_unknown_on_timeout(self):
        s = healthy_pi()
        s.http_map[("GET", "/api/health")] = HttpResponse(None, error="timeout")
        self.assertEqual(run("health", s), ("unknown", "retry_local"))


class AppBindTests(unittest.TestCase):
    def test_lan_publication_is_unknown_confirm_trusted_lan(self):
        self.assertEqual(run("app_bind", healthy_pi()), ("unknown", "confirm_trusted_lan"))

    def test_pass_when_loopback_only(self):
        s = healthy_pi()
        loop = {"3847/tcp": [{"HostIp": "127.0.0.1", "HostPort": "3847"}]}
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(ports=loop, port_bindings=loop)))
        s.files["/proc/net/tcp"] = proc_table([("127.0.0.1", 3847, "0A")])
        s.files["/proc/net/tcp6"] = proc_table([], v6=True)
        self.assertEqual(run("app_bind", s), PASS)

    DUAL_STACK = {"lo": ["127.0.0.1", "::1"], "wlan0": ["192.168.1.50", "2001:db8::50", "fe80::1"]}

    def test_dual_stack_host_with_ipv4_only_publication_is_confirm_trusted_lan(self):
        # The preview compose publishes 0.0.0.0:3847 only, so a global IPv6
        # address on the Pi does not expose the hub.
        s = healthy_pi()
        s.set(["ip", "-j", "addr", "show"], ok(fakes.ip_addr_json(self.DUAL_STACK)))
        self.assertEqual(run("app_bind", s), ("unknown", "confirm_trusted_lan"))

    def test_fail_on_ipv6_wildcard_across_global_ipv6(self):
        # docker-compose.yml's plain "3847:3847" also publishes on [::].
        s = healthy_pi()
        both = {"3847/tcp": [{"HostIp": "0.0.0.0", "HostPort": "3847"}, {"HostIp": "::", "HostPort": "3847"}]}
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(ports=both, port_bindings={"3847/tcp": [{"HostIp": "", "HostPort": "3847"}]})))
        s.files["/proc/net/tcp6"] = proc_table([("::", 3847, "0A")], v6=True)
        s.set(["ip", "-j", "addr", "show"], ok(fakes.ip_addr_json(self.DUAL_STACK)))
        self.assertEqual(run("app_bind", s), ("fail", "restrict_ports"))

    def test_fail_on_wildcard_across_public_ipv4(self):
        s = healthy_pi()
        s.set(["ip", "-j", "addr", "show"], ok(fakes.ip_addr_json({"eth0": ["203.0.113.7"]})))
        self.assertEqual(run("app_bind", s), ("fail", "restrict_ports"))

    def test_fail_on_public_bind_even_if_inspection_incomplete(self):
        s = healthy_pi()
        s.set(["docker", "compose", "-f", COMPOSE, "ps", "--all", "--quiet"], ok(rc=1))
        s.files["/proc/net/tcp"] = proc_table([("198.51.100.9", 3847, "0A")])
        self.assertEqual(run("app_bind", s), ("fail", "restrict_ports"))

    def test_public_listener_is_kept_when_a_later_read_fails(self):
        s = healthy_pi()
        s.files["/proc/net/tcp"] = proc_table([("198.51.100.9", 3847, "0A")])
        s.files["/proc/net/tcp6"] = PermissionError(13, "denied")
        s.set(["ip", "-j", "addr", "show"], ok(rc=1))
        self.assertEqual(run("app_bind", s), ("fail", "restrict_ports"))

    def test_malformed_later_line_never_hides_a_public_listener(self):
        s = healthy_pi()
        s.files["/proc/net/tcp"] = proc_table([("198.51.100.9", 3847, "0A")]) + "  7: garbage\n"
        self.assertEqual(run("app_bind", s), ("fail", "restrict_ports"))
        s = healthy_pi()
        s.files["/proc/net/tcp"] = proc_table([("0.0.0.0", 3847, "0A")]) + "  7: garbage\n"
        self.assertEqual(run("app_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp"), ok(proc_table([("0.0.0.0", 8787, "0A")]) + "  7: garbage\n"))
        self.assertEqual(run("bridge_bind", s), ("fail", "restrict_ports"))

    def test_lan_address_bind_is_still_not_verified_safe(self):
        s = healthy_pi()
        lan = {"3847/tcp": [{"HostIp": "192.168.1.50", "HostPort": "3847"}]}
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(ports=lan, port_bindings=lan)))
        s.files["/proc/net/tcp"] = proc_table([("192.168.1.50", 3847, "0A")])
        s.files["/proc/net/tcp6"] = proc_table([], v6=True)
        self.assertEqual(run("app_bind", s), ("unknown", "confirm_trusted_lan"))

    def test_incomplete_inspection_is_retry_local(self):
        s = healthy_pi()
        s.set(["ip", "-j", "addr", "show"], CommandResult(None, missing=True))
        self.assertEqual(run("app_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.files["/proc/net/tcp6"] = PermissionError(13, "denied")
        self.assertEqual(run("app_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["docker", "compose", "-f", COMPOSE, "ps", "--all", "--quiet"], ok(rc=1))
        self.assertEqual(run("app_bind", s), ("unknown", "retry_local"))


class BridgeBindTests(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(run("bridge_bind", healthy_pi()), PASS)

    def test_fail_when_8787_is_published(self):
        s = healthy_pi()
        ports = {"3847/tcp": [{"HostIp": "0.0.0.0", "HostPort": "3847"}], "8787/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8787"}]}
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(ports=ports)))
        self.assertEqual(run("bridge_bind", s), ("fail", "restrict_ports"))

    def test_fail_when_bridge_listens_beyond_loopback(self):
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp"), ok(proc_table([("0.0.0.0", 8787, "0A")])))
        self.assertEqual(run("bridge_bind", s), ("fail", "restrict_ports"))
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp6"), ok(proc_table([("::", 8787, "0A")], v6=True)))
        self.assertEqual(run("bridge_bind", s), ("fail", "restrict_ports"))

    def test_pass_when_ipv6_is_off_in_the_container(self):
        s = healthy_pi()
        s.set(exec_key("test", "-e", "/proc/net/tcp6"), ok(rc=1))
        self.assertEqual(run("bridge_bind", s), PASS)

    def test_unknown_when_either_family_is_unreadable(self):
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp6"), ok("", "Permission denied", rc=1))
        self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp"), ok("", "Permission denied", rc=1))
        self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(exec_key("test", "-e", "/proc/net/tcp6"), ok(rc=126))
        self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp6"), ok("garbage"))
        self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"))

    def test_fail_with_host_networking_and_open_bridge(self):
        s = healthy_pi()
        s.set(["docker", "inspect", "--type", "container"], ok(fakes.container_json(network_mode="host", ports={}, port_bindings={})))
        s.files["/proc/net/tcp6"] = proc_table([("::", 8787, "0A")], v6=True)
        self.assertEqual(run("bridge_bind", s), ("fail", "restrict_ports"))

    def test_unknown_when_container_cannot_be_inspected(self):
        s = healthy_pi()
        s.set(exec_key("cat", "/proc/net/tcp"), ok("", "OCI runtime exec failed", rc=126))
        self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"))
        s = healthy_pi()
        s.set(["docker", "compose", "-f", COMPOSE, "ps", "--all", "--quiet"], ok(rc=1))
        self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"))


class SshPolicyTests(unittest.TestCase):
    def test_pass_when_off_for_a_and_c(self):
        for tier in ("A", "C"):
            self.assertEqual(run("ssh_policy", healthy_pi(), tier=tier), PASS)

    def test_fail_when_on_for_a_or_c(self):
        s = healthy_pi()
        ssh_on(s)
        self.assertEqual(run("ssh_policy", s, tier="C"), ("fail", "review_ssh"))
        s = healthy_pi()
        s.files["/proc/net/tcp"] = proc_table([("0.0.0.0", 22, "0A")])  # sshd started by hand
        self.assertEqual(run("ssh_policy", s, tier="A"), ("fail", "review_ssh"))

    def test_b_temporary_key_only_on_lan_passes_until_final(self):
        s = healthy_pi()
        ssh_on(s)
        self.assertEqual(run("ssh_policy", s, tier="B", phase="running"), PASS)
        self.assertEqual(run("ssh_policy", s, tier="B", phase="final"), ("fail", "review_ssh"))

    def test_b_allows_passwords_until_final(self):
        # HJ, 2026-11-20: an install over SSH from a laptop may use a password; no SSH key needed.
        s = healthy_pi()
        ssh_on(s, password=True)
        self.assertEqual(run("ssh_policy", s, tier="B", phase="running"), PASS)
        self.assertEqual(run("ssh_policy", s, tier="B", phase="final"), ("fail", "review_ssh"))
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config"] = fakes.SSHD_CONFIG + "Match Address 192.168.1.0/24\n  PasswordAuthentication yes\n"
        self.assertEqual(run("ssh_policy", s, tier="B"), PASS)
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config"] = "Include /etc/ssh/sshd_config.d/*.conf\n"  # keyboard-interactive default yes
        self.assertEqual(run("ssh_policy", s, tier="B"), PASS)
        for tier in ("A", "C"):
            s = healthy_pi()
            ssh_on(s, password=True)
            self.assertEqual(run("ssh_policy", s, tier=tier), ("fail", "review_ssh"), tier)

    def test_b_fails_on_root_login_or_empty_passwords(self):
        for extra in (
            "PermitRootLogin yes\n",
            "PermitEmptyPasswords yes\n",
            "Match User guest\n  PermitEmptyPasswords yes\n",
            'PermitRootLogin "yes"\n',
            "PermitRootLogin 'YES'\n",
            'PermitRootLogin="yes"\n',
            'PermitEmptyPasswords "yes"\n',
        ):
            s = healthy_pi()
            ssh_on(s)
            s.files["/etc/ssh/sshd_config"] = extra + fakes.SSHD_CONFIG
            self.assertEqual(run("ssh_policy", s, tier="B"), ("fail", "review_ssh"), extra)

    def test_b_fails_on_public_listener(self):
        s = healthy_pi()
        ssh_on(s)
        s.set(["ip", "-j", "addr", "show"], ok(fakes.ip_addr_json({"wlan0": ["192.168.1.50", "2001:db8::50"]})))
        s.files["/proc/net/tcp6"] = proc_table([("::", 22, "0A")], v6=True)
        self.assertEqual(run("ssh_policy", s, tier="B"), ("fail", "review_ssh"))

    def test_unknown_when_state_or_config_unreadable(self):
        s = healthy_pi()
        s.set(["systemctl", "is-enabled", "ssh.service"], CommandResult(None, missing=True))
        self.assertEqual(run("ssh_policy", s), ("unknown", "review_ssh"))
        s = healthy_pi()
        s.set(["systemctl", "is-active", "ssh.socket"], ok("", "Failed to connect to bus", rc=1))
        s.files["/lib/systemd/system/ssh.socket"] = "[Socket]\n"
        self.assertEqual(run("ssh_policy", s), ("unknown", "review_ssh"))
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config.d/50-temp.conf"] = PermissionError(13, "denied")
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))
        s = healthy_pi()
        ssh_on(s)
        s.set(["ip", "-j", "addr", "show"], ok("not json"))
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "retry_local"))

    def test_sshd_units_and_custom_ports_count(self):
        s = healthy_pi()
        s.set(["systemctl", "is-active", "sshd.socket"], ok("active\n"))
        self.assertEqual(run("ssh_policy", s), ("fail", "review_ssh"))
        s = healthy_pi()
        s.files["/etc/ssh/sshd_config.d/10-port.conf"] = "Port 2222\n"
        s.files["/proc/net/tcp"] = proc_table([("0.0.0.0", 2222, "0A")])
        self.assertEqual(run("ssh_policy", s), ("fail", "review_ssh"))

    def test_any_password_yes_is_still_not_key_only(self):
        from sproutwall_lib import sshd

        for extra in (
            "Match User guest\n  PasswordAuthentication yes\n",
            "Match Address 10.0.0.0/8\n  KbdInteractiveAuthentication yes\n",
            "PasswordAuthentication yes\n",  # after an earlier "no": sshd ignores it, doctor does not
        ):
            s = healthy_pi()
            ssh_on(s)
            s.files["/etc/ssh/sshd_config"] = fakes.SSHD_CONFIG + extra
            self.assertTrue(sshd.allows_password(sshd.read_directives(s)), extra)
            self.assertEqual(run("ssh_policy", s, tier="B"), PASS, extra)  # tier B allows passwords

    def test_unreadable_config_is_unknown_while_ssh_is_on(self):
        # SSH that is off passes even when the config cannot be read
        # (Raspberry Pi Imager can leave a root-only file in sshd_config.d).
        # While SSH is on, an unreadable config is never ignored.
        setups = (
            lambda s: s.unlistable.add("/etc/ssh/sshd_config.d"),
            lambda s: s.files.__setitem__("/etc/ssh/sshd_config.d/20-x.conf", PermissionError(13, "denied")),
            lambda s: s.files.__setitem__("/etc/ssh/sshd_config", PermissionError(13, "denied")),
        )
        for number, setup in enumerate(setups):
            for tier in ("A", "C"):
                for phase in ("running", "final"):
                    s = healthy_pi()
                    setup(s)
                    self.assertEqual(run("ssh_policy", s, tier=tier, phase=phase), PASS, (number, tier, phase))
            s = healthy_pi()
            setup(s)
            ssh_on(s)
            self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"), number)
            self.assertEqual(run("ssh_policy", s, tier="B", phase="final"), ("fail", "review_ssh"), number)
            self.assertEqual(run("ssh_policy", s, tier="C"), ("fail", "review_ssh"), number)

    def test_ssh_off_passes_with_a_root_only_imager_file(self):
        # The final check after the person turned SSH off over SSH and restarted.
        s = healthy_pi()
        s.files["/etc/ssh/sshd_config.d/50-cloud-init.conf"] = PermissionError(13, "denied")
        self.assertEqual(run("ssh_policy", s, tier="C", phase="final"), PASS)
        # Still on: a listener on port 22 (sshd started by hand) is never hidden by it.
        s.files["/proc/net/tcp"] = proc_table([("0.0.0.0", 22, "0A")])
        self.assertEqual(run("ssh_policy", s, tier="C", phase="final"), ("fail", "review_ssh"))
        # Still on: a unit that is active.
        s = healthy_pi()
        s.files["/etc/ssh/sshd_config.d/50-cloud-init.conf"] = PermissionError(13, "denied")
        s.set(["systemctl", "is-active", "ssh.socket"], ok("active\n"))
        self.assertEqual(run("ssh_policy", s, tier="C", phase="final"), ("fail", "review_ssh"))
        # Unknown state stays unknown.
        s = healthy_pi()
        s.files["/etc/ssh/sshd_config.d/50-cloud-init.conf"] = PermissionError(13, "denied")
        s.set(["systemctl", "is-enabled", "ssh.service"], CommandResult(None, missing=True))
        self.assertEqual(run("ssh_policy", s, tier="C", phase="final"), ("unknown", "review_ssh"))

    def test_quoted_and_listen_address_ports_are_read(self):
        from sproutwall_lib import sshd

        cases = {
            'Port "2222"\n': ([22, 2222], True),
            "Port '2222'\n": ([22, 2222], True),
            "Port=2222\n": ([22, 2222], True),
            "Port 2222 # custom\n": ([22, 2222], True),
            "ListenAddress 0.0.0.0:2200\n": ([22, 2200], True),
            'ListenAddress "[::]:2201"\n': ([22, 2201], True),
            "ListenAddress 192.168.1.50:2202 rdomain 1\n": ([22, 2202], True),
            "ListenAddress 192.168.1.50\n": ([22], True),
            "ListenAddress ::\n": ([22], True),
            "ListenAddress [::1]\n": ([22], True),
            "Port ssh\n": ([22], False),
            "Port 70000\n": ([22], False),
            'Port "22x"\n': ([22], False),
            "Port\n": ([22], False),
            "ListenAddress 0.0.0.0:http\n": ([22], False),
            "ListenAddress [::1:2203\n": ([22], False),
            "ListenAddress [::1]x2203\n": ([22], False),
        }
        for text, expected in cases.items():
            s = healthy_pi()
            s.files["/etc/ssh/sshd_config.d/10-port.conf"] = text
            self.assertEqual(sshd.port_list(sshd.read_directives(s)), expected, text)

    def test_quoted_custom_port_listener_counts(self):
        for text in ('Port "2222"\n', "ListenAddress 0.0.0.0:2222\n"):
            s = healthy_pi()
            s.files["/etc/ssh/sshd_config.d/10-port.conf"] = text
            s.files["/proc/net/tcp"] = proc_table([("0.0.0.0", 2222, "0A")])
            self.assertEqual(run("ssh_policy", s, tier="A"), ("fail", "review_ssh"), text)
            self.assertEqual(run("ssh_policy", s, tier="C", phase="final"), ("fail", "review_ssh"), text)

    def test_unparseable_port_is_unknown_not_ignored(self):
        for text in ("Port ssh\n", 'Port "22x"\n', "ListenAddress 0.0.0.0:http\n"):
            for on in (False, True):
                s = healthy_pi()
                s.files["/etc/ssh/sshd_config.d/10-port.conf"] = text
                if on:
                    ssh_on(s)
                    self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"), text)
                else:
                    self.assertEqual(run("ssh_policy", s, tier="A"), ("unknown", "review_ssh"), text)
                    self.assertEqual(run("ssh_policy", s, tier="C", phase="final"), ("unknown", "review_ssh"), text)

    def test_quoted_include_paths_are_read(self):
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config"] = 'Include "/etc/ssh/my conf.d/*.conf"\n' + fakes.SSHD_CONFIG
        s.files["/etc/ssh/my conf.d/90-pw.conf"] = "PermitRootLogin yes\n"
        self.assertEqual(run("ssh_policy", s, tier="B"), ("fail", "review_ssh"))
        s.files["/etc/ssh/sshd_config"] = 'Include "/etc/ssh/unbalanced\n' + fakes.SSHD_CONFIG
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))

    def test_wildcard_folders_must_be_listable(self):
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config"] = "Include /etc/ssh/*.d/*.conf\n" + fakes.SSHD_CONFIG
        s.files["/etc/ssh/extra.d/90-pw.conf"] = "PermitRootLogin yes\n"
        self.assertEqual(run("ssh_policy", s, tier="B"), ("fail", "review_ssh"))
        s.unlistable.add("/etc/ssh/extra.d")
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))
        s = healthy_pi()
        s.files["/etc/ssh/sshd_config"] = "Include /etc/ssh/*.d/*.conf\n" + fakes.SSHD_CONFIG
        s.unlistable.add("/etc/ssh")
        self.assertEqual(run("ssh_policy", s, tier="A"), PASS)  # SSH is off
        ssh_on(s)
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))

    def test_missing_literal_include_is_skipped(self):
        s = healthy_pi()
        s.files["/etc/ssh/sshd_config"] = (
            "Include /etc/ssh/not-there.conf\nInclude /etc/ssh/no-folder/x.conf\n" + fakes.SSHD_CONFIG
        )
        self.assertEqual(run("ssh_policy", s, tier="A"), PASS)
        ssh_on(s)
        self.assertEqual(run("ssh_policy", s, tier="B"), PASS)

    def test_inaccessible_literal_include_is_unknown_not_missing(self):
        cases = {
            "file mode 000": lambda s: s.files.__setitem__("/etc/ssh/locked.conf", PermissionError(13, "denied")),
            "folder mode 000": lambda s: s.blocked.add("/etc/ssh/locked.d"),
            "part is a file": lambda s: s.files.__setitem__("/etc/ssh/locked.d", "not a folder\n"),
            "include is a folder": lambda s: s.dirs.add("/etc/ssh/locked.conf"),
        }
        includes = {
            "file mode 000": "/etc/ssh/locked.conf",
            "folder mode 000": "/etc/ssh/locked.d/x.conf",
            "part is a file": "/etc/ssh/locked.d/x.conf",
            "include is a folder": "/etc/ssh/locked.conf",
        }
        for label, setup in cases.items():
            for tier in ("A", "B"):
                s = healthy_pi()
                if tier == "B":
                    ssh_on(s)
                s.files["/etc/ssh/sshd_config"] = "Include %s\n" % includes[label] + fakes.SSHD_CONFIG
                setup(s)
                # SSH off (tier A here) passes even when the config cannot be read.
                expected = ("unknown", "review_ssh") if tier == "B" else PASS
                self.assertEqual(run("ssh_policy", s, tier=tier), expected, (label, tier))

    def test_wildcard_matches_follow_the_same_rule(self):
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config.d/50-locked.conf"] = PermissionError(13, "denied")
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))
        s = healthy_pi()
        ssh_on(s)
        s.dirs.add("/etc/ssh/sshd_config.d/sub.conf")  # a folder matched by *.conf
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))

    def test_listing_errors_are_never_no_matches(self):
        import errno

        for tier in ("A", "B"):
            s = healthy_pi()
            if tier == "B":
                ssh_on(s)
            s.list_errors["/etc/ssh/sshd_config.d"] = OSError(errno.EIO, "Input/output error")
            # SSH off (tier A here) passes even when the config cannot be read.
            expected = ("unknown", "review_ssh") if tier == "B" else PASS
            self.assertEqual(run("ssh_policy", s, tier=tier), expected, tier)

    def test_wildcards_skip_dotfiles_like_glob3(self):
        s = healthy_pi()
        ssh_on(s)
        s.files["/etc/ssh/sshd_config.d/.90-hidden.conf"] = "PermitRootLogin yes\n"
        self.assertEqual(run("ssh_policy", s, tier="B"), PASS)
        s.files["/etc/ssh/sshd_config"] = "Include /etc/ssh/sshd_config.d/.*.conf\n" + fakes.SSHD_CONFIG
        self.assertEqual(run("ssh_policy", s, tier="B"), ("fail", "review_ssh"))

    def test_wildcard_results_are_sorted(self):
        from sproutwall_lib import sshd

        s = healthy_pi()
        for name in ("50-b.conf", "10-a.conf", "90-c.conf", "notes.txt", ".hidden.conf"):
            s.files["/etc/ssh/sshd_config.d/" + name] = "\n"
        self.assertEqual(s.listdir("/etc/ssh/sshd_config.d")[0], "notes.txt")  # the fake lists out of order
        expected = ["/etc/ssh/sshd_config.d/" + n for n in ("10-a.conf", "50-b.conf", "90-c.conf")]
        self.assertEqual(sshd.include_files(s, "/etc/ssh/sshd_config.d/*.conf"), expected)
        self.assertEqual(sshd.wildcard_matches(s, "/etc/ssh/sshd_config.d", "*.conf"), expected)
        # First match wins in sshd, so the order decides: 10-a says no, 90-c says yes.
        s.files["/etc/ssh/sshd_config.d/10-a.conf"] = "Port 2200\n"
        s.files["/etc/ssh/sshd_config.d/90-c.conf"] = "Port 2299\n"
        self.assertEqual(sshd.ports(sshd.read_directives(s)), [22, 2200, 2299])

    def test_unit_file_lookup_error_is_unknown(self):
        s = healthy_pi()
        s.set(["systemctl", "is-active", "ssh.socket"], ok("", "Failed to connect to bus", rc=1))
        s.probe_errors.add("/lib/systemd/system/ssh.socket")
        self.assertEqual(run("ssh_policy", s), ("unknown", "review_ssh"))
        s.probe_errors.clear()
        self.assertEqual(run("ssh_policy", s), PASS)  # every unit folder says ENOENT: not installed

    def test_missing_main_config(self):
        s = healthy_pi()
        del s.files["/etc/ssh/sshd_config"]
        self.assertEqual(run("ssh_policy", s, tier="A"), PASS)
        ssh_on(s)
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))
        s = healthy_pi()
        s.blocked.add("/etc/ssh")
        self.assertEqual(run("ssh_policy", s, tier="A"), PASS)  # SSH is off
        ssh_on(s)
        self.assertEqual(run("ssh_policy", s, tier="B"), ("unknown", "review_ssh"))

    def test_real_probe_reports_why(self):
        import tempfile

        from sproutwall_lib.system import System

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.conf")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("Port 22\n")
            probe = System().probe
            self.assertEqual(probe(path), "file")
            self.assertEqual(probe(tmp), "dir")
            self.assertEqual(probe(os.path.join(tmp, "none.conf")), "missing")
            self.assertEqual(probe(os.path.join(tmp, "no-folder", "x.conf")), "missing")
            self.assertEqual(probe(os.path.join(path, "child.conf")), "error")  # ENOTDIR
            self.assertEqual(probe("bad\x00path"), "error")

    def test_listener_seen_before_a_failed_read_still_counts(self):
        s = healthy_pi()
        s.files["/proc/net/tcp"] = proc_table([("0.0.0.0", 22, "0A")])
        s.files["/proc/net/tcp6"] = PermissionError(13, "denied")
        self.assertEqual(run("ssh_policy", s), ("fail", "review_ssh"))
        s = healthy_pi()
        s.files["/proc/net/tcp6"] = PermissionError(13, "denied")
        self.assertEqual(run("ssh_policy", s), ("unknown", "review_ssh"))

    def test_off_when_openssh_is_not_installed(self):
        s = healthy_pi()
        for unit in ("ssh.service", "sshd.service", "ssh.socket", "sshd.socket"):
            s.set(["systemctl", "is-enabled", unit], ok("not-found\n", rc=4))
            s.set(["systemctl", "is-active", unit], ok("", "Failed to connect to bus", rc=1))
        del s.files["/etc/ssh/sshd_config"]
        self.assertEqual(run("ssh_policy", s), PASS)


class SetupAndReadGuardTests(unittest.TestCase):
    def test_setup_pass_fail_unknown(self):
        self.assertEqual(run("setup", healthy_pi(), phase="configured"), PASS)
        self.assertEqual(run("setup", healthy_pi(phase_ready=False), phase="configured"), ("fail", "open_hub"))
        for response in (
            HttpResponse(200, b'{"ok":true,"version":"0.1.0","schema":3}'),  # image from before the field
            fakes.health_response(setup="yes"),
            HttpResponse(503, b'{"ok":false,"code":"db_newer_than_app"}'),
            HttpResponse(None, error="refused"),
            HttpResponse(None, error="timeout"),
        ):
            s = healthy_pi()
            s.http_map[("GET", "/api/health")] = response
            self.assertEqual(run("setup", s, phase="configured"), ("unknown", "retry_local"), response)

    def test_doctor_only_reads_from_the_hub(self):
        from sproutwall_lib.doctor import run_doctor

        for phase in ("running", "configured", "final"):
            s = healthy_pi()
            run_doctor(s, ROOT, phase)
            self.assertTrue(s.http_calls)
            self.assertEqual({method for method, _, body, _ in s.http_calls}, {"GET"})
            self.assertTrue(all(body is None for _, _, body, _ in s.http_calls))
            paths = [path for _, path, _, _ in s.http_calls]
            self.assertEqual(paths.count("/api/health"), 1, "health is asked once and shared with setup")
            self.assertNotIn("/api/setup", paths)

    def test_no_http_request_unless_docker_reports_healthy(self):
        from sproutwall_lib.doctor import run_doctor

        not_ready = [
            ok(fakes.hub_state("starting")),
            ok(fakes.hub_state("unhealthy")),
            ok(fakes.hub_state("healthy", "restarting")),
            ok(fakes.hub_state(None)),  # no healthcheck at all
            ok("", "Error: No such container", rc=1),
            CommandResult(None, missing=True),
        ]
        for state in not_ready:
            s = healthy_pi()
            s.set(["docker", "inspect", "--type", "container", "--format", checks.HUB_FORMAT], state)
            self.assert_no_requests(run_doctor(s, ROOT, "final"), s, state)
        for broken in (ok(rc=1), ok(fakes.CID + "\n" + "d" * 64 + "\n"), CommandResult(None, missing=True)):
            s = healthy_pi()
            s.set(["docker", "compose", "-f", COMPOSE, "ps", "--all", "--quiet"], broken)
            run_doctor(s, ROOT, "final")
            self.assertEqual(s.http_calls, [], broken)

    def assert_no_requests(self, report, system, label):
        self.assertEqual(system.http_calls, [], label)
        by_id = {c["id"]: (c["status"], c["action"]) for c in report["checks"]}
        for check_id in ("health", "setup", "read_guard"):
            self.assertEqual(by_id[check_id], ("unknown", "retry_local"), (label, check_id))

    def test_requests_go_to_the_inspected_container_address(self):
        import ipaddress

        from sproutwall_lib.doctor import run_doctor

        s = healthy_pi()
        run_doctor(s, ROOT, "final")
        self.assertEqual([path for _, path, _, _ in s.http_calls], ["/api/health", "/api/modules"])
        self.assertEqual(s.http_targets, [ipaddress.ip_address(fakes.HUB_IP)] * 2)
        hub_reads = [argv for argv, _ in s.calls if len(argv) > 5 and argv[5] == checks.HUB_FORMAT]
        self.assertEqual(hub_reads, [("docker", "inspect", "--type", "container", "--format", checks.HUB_FORMAT, fakes.CID)])
        s = healthy_pi()
        s.set(["docker", "inspect", "--type", "container", "--format", checks.HUB_FORMAT], ok(fakes.hub_state(addresses=("", "fd12:3456::7"))))
        run_doctor(s, ROOT, "final")
        self.assertEqual(s.http_targets, [ipaddress.ip_address("fd12:3456::7")] * 2)

    def test_zero_requests_without_exactly_one_private_container_address(self):
        from sproutwall_lib.doctor import run_doctor

        cases = {
            "no address": fakes.hub_state(addresses=("", "")),
            "no networks": fakes.hub_state(addresses=()),
            "two addresses": fakes.hub_state(addresses=(fakes.HUB_IP, "fd12:3456::7")),
            "two networks": fakes.hub_state(addresses=(fakes.HUB_IP, "", "10.9.0.4", "")),
            "host network": fakes.hub_state(network_mode="host", addresses=("", "")),
            "host network with address": fakes.hub_state(network_mode="host"),
            "public": fakes.hub_state(addresses=("203.0.113.5", "")),
            "global v6": fakes.hub_state(addresses=("", "2001:db8::5")),
            "loopback": fakes.hub_state(addresses=("127.0.0.1", "")),
            "link-local": fakes.hub_state(addresses=("169.254.0.9", "")),
            "zone": fakes.hub_state(addresses=("", "fd12::7%eth0")),
            "garbage": fakes.hub_state(addresses=("hub.local", "")),
            "other container": fakes.hub_state(cid="d" * 64),
            "short id": fakes.hub_state(cid=fakes.CID[:12]),
        }
        for label, state in cases.items():
            s = healthy_pi()
            s.set(["docker", "inspect", "--type", "container", "--format", checks.HUB_FORMAT], ok(state))
            self.assert_no_requests(run_doctor(s, ROOT, "final"), s, label)

    def test_no_loopback_fallback_even_in_the_real_client(self):
        from sproutwall_lib.system import System

        for target in ("127.0.0.1", "localhost", None, b"127.0.0.1"):
            self.assertIsNone(System().http(target, "GET", "/api/health").status)

    def test_container_address_never_appears_in_output(self):
        import io

        from sproutwall_lib import cli

        address = "10.77.66.55"
        for argv in (["doctor", "--json", "--phase", "final"], ["doctor", "--phase", "final"]):
            for response in (fakes.health_response(), HttpResponse(None, error="refused"), HttpResponse(503, b'{"ok":false,"code":"x"}')):
                s = healthy_pi()
                s.set(["docker", "inspect", "--type", "container", "--format", checks.HUB_FORMAT], ok(fakes.hub_state(addresses=(address, ""))))
                s.http_map[("GET", "/api/health")] = response
                out, err = io.StringIO(), io.StringIO()
                cli.main(argv, system=s, root=ROOT, out=out, err=err)
                self.assertTrue(s.http_calls)
                self.assertNotIn(address, out.getvalue() + err.getvalue())

    def test_hub_format_requests_only_id_health_network_mode_and_addresses(self):
        self.assertIn(".State.Health.Status", checks.HUB_FORMAT)
        self.assertIn(".NetworkSettings.Networks", checks.HUB_FORMAT)
        for field in (".Config", "Env", "Log", "MacAddress", "Aliases", "Mounts", ".Name"):
            self.assertNotIn(field, checks.HUB_FORMAT)

    def test_read_guard_pass_fail_unknown(self):
        self.assertEqual(run("read_guard", healthy_pi(), phase="configured"), PASS)
        s = healthy_pi()
        s.http_map[("GET", "/api/modules")] = HttpResponse(200, b'{"rev":1}')
        self.assertEqual(run("read_guard", s, phase="configured", outcomes={"setup": PASS}), ("fail", "verify_release"))
        self.assertEqual(run("read_guard", s, phase="configured", outcomes={"setup": ("fail", "open_hub")}), ("fail", "open_hub"))
        s = healthy_pi()
        s.http_map[("GET", "/api/modules")] = HttpResponse(503, b"{}")
        self.assertEqual(run("read_guard", s, phase="configured"), ("unknown", "retry_local"))
        self.assertEqual(s.http_calls[-1][3], {"Accept": "application/json"})  # no cookie


class KioskTests(unittest.TestCase):
    AUTOSTART = HOME + "/.config/labwc/autostart"
    LINE = '"$HOME/.local/share/sproutwall/kiosk-launch" & # sproutwall:kiosk-launcher\n'

    def test_on(self):
        self.assertEqual(run("kiosk", healthy_pi(), phase="final"), PASS)
        s = healthy_pi()
        del s.files[self.AUTOSTART]
        self.assertEqual(run("kiosk", s, phase="final"), ("fail", "repair_kiosk"))
        s = healthy_pi()
        s.files[self.AUTOSTART] = self.LINE * 2
        self.assertEqual(run("kiosk", s, phase="final"), ("fail", "repair_kiosk"))
        s = healthy_pi()
        s.files[self.AUTOSTART] = "# " + self.LINE
        self.assertEqual(run("kiosk", s, phase="final"), ("fail", "repair_kiosk"))

    def test_off(self):
        s = healthy_pi()
        self.assertEqual(run("kiosk", s, phase="final", kiosk="off"), ("fail", "repair_kiosk"))
        s.files[self.AUTOSTART] = "# " + self.LINE
        self.assertEqual(run("kiosk", s, phase="final", kiosk="off"), PASS)
        del s.files[self.AUTOSTART]
        self.assertEqual(run("kiosk", s, phase="final", kiosk="off"), PASS)

    def test_unknown_when_unreadable(self):
        s = healthy_pi()
        s.files[self.AUTOSTART] = PermissionError(13, "denied")
        self.assertEqual(run("kiosk", s, phase="final"), ("unknown", "retry_local"))


class TemporaryAccessTests(unittest.TestCase):
    def test_pass(self):
        for tier in ("A", "B", "C"):
            self.assertEqual(run("temporary_access", healthy_pi(), phase="final", tier=tier), PASS)

    def test_fail_when_an_agent_remains(self):
        s = healthy_pi()
        s.which_map["claude"] = HOME + "/.local/bin/claude"
        self.assertEqual(run("temporary_access", s, phase="final"), ("fail", "remove_agent"))
        s = healthy_pi()
        s.dirs.add(HOME + "/.codex")
        self.assertEqual(run("temporary_access", s, phase="final", tier="C"), ("fail", "remove_agent"))
        s = healthy_pi()
        s.files[HOME + "/.config/autostart/helper.desktop"] = "[Desktop Entry]\nExec=/usr/local/bin/gemini --resume\n"
        self.assertEqual(run("temporary_access", s, phase="final"), ("fail", "remove_agent"))

    def test_listing_and_lookup_errors_are_unknown_but_findings_still_fail(self):
        import errno

        s = healthy_pi()
        s.list_errors[HOME + "/.config/autostart"] = OSError(errno.EIO, "Input/output error")
        self.assertEqual(run("temporary_access", s, phase="final"), ("unknown", "retry_local"))
        s = healthy_pi()
        s.probe_errors.add(HOME + "/.codex")
        self.assertEqual(run("temporary_access", s, phase="final"), ("unknown", "retry_local"))
        s.files[HOME + "/.config/systemd/user/helper.service"] = "[Service]\nExecStart=/usr/bin/env codex serve\n"
        self.assertEqual(run("temporary_access", s, phase="final"), ("fail", "remove_agent"))

    def test_fail_when_an_ssh_session_is_open(self):
        s = healthy_pi()
        s.files["/proc/net/tcp"] = proc_table([("192.168.1.50", 22, "01")])
        self.assertEqual(run("temporary_access", s, phase="final", tier="B"), ("fail", "remove_agent"))

    def test_unknown_when_unreadable(self):
        s = healthy_pi()
        s.files["/proc/net/tcp"] = PermissionError(13, "denied")
        self.assertEqual(run("temporary_access", s, phase="final"), ("unknown", "retry_local"))
        s = healthy_pi()
        s.files[HOME + "/.config/autostart/x.desktop"] = PermissionError(13, "denied")
        self.assertEqual(run("temporary_access", s, phase="final"), ("unknown", "retry_local"))

    def test_root_only_imager_file_with_ssh_off_passes(self):
        # the final check after the person turned SSH off and
        # restarted, with Raspberry Pi Imager's root-only file in sshd_config.d.
        unreadable = (
            lambda s: s.files.__setitem__("/etc/ssh/sshd_config.d/50-cloud-init.conf", PermissionError(13, "denied")),
            lambda s: s.unlistable.add("/etc/ssh/sshd_config.d"),
        )
        for number, setup in enumerate(unreadable):
            for tier in ("A", "B", "C"):
                s = healthy_pi()
                setup(s)
                self.assertEqual(run("temporary_access", s, phase="final", tier=tier), PASS, (number, tier))
                self.assertEqual(run("ssh_policy", s, phase="final", tier=tier), PASS, (number, tier))
            # SSH still on: the unreadable config stays unknown.
            s = healthy_pi()
            setup(s)
            ssh_on(s)
            self.assertEqual(run("temporary_access", s, phase="final"), ("unknown", "retry_local"), number)
            # SSH state unknown: still unknown.
            s = healthy_pi()
            setup(s)
            s.set(["systemctl", "is-enabled", "ssh.service"], CommandResult(None, missing=True))
            self.assertEqual(run("temporary_access", s, phase="final"), ("unknown", "retry_local"), number)
            # An open session on port 22 still fails, SSH off or not.
            s = healthy_pi()
            setup(s)
            s.files["/proc/net/tcp"] = proc_table([("192.168.1.50", 22, "01")])
            self.assertEqual(run("temporary_access", s, phase="final"), ("fail", "remove_agent"), number)


class ParserTests(unittest.TestCase):
    def test_proc_net_tcp_round_trip(self):
        from sproutwall_lib import net

        sockets, complete = net.parse_proc_net_tcp(proc_table([("127.0.0.1", 8787, "0A")]), 4)
        self.assertEqual(([(str(a), p, st) for a, p, st in sockets], complete), ([("127.0.0.1", 8787, "0A")], True))
        sockets, complete = net.parse_proc_net_tcp(proc_table([("::1", 3847, "0A")], v6=True), 6)
        self.assertEqual(([(str(a), p, st) for a, p, st in sockets], complete), ([("::1", 3847, "0A")], True))
        self.assertEqual(net.parse_proc_net_tcp("garbage", 4), ([], False))
        self.assertEqual(net.parse_proc_net_tcp(proc_table([]) + proc_table([]), 4), ([], False))  # two headers
        self.assertEqual(sorted(net.TCP_STATES), ["%02X" % n for n in range(1, 12)])

    def test_a_malformed_line_keeps_the_lines_already_read(self):
        from sproutwall_lib import net

        text = proc_table([("198.51.100.9", 3847, "0A")]) + "  9: ZZZZ:XYZ 00000000:0000 0A\n  10:\n"
        sockets, complete = net.parse_proc_net_tcp(text, 4)
        self.assertFalse(complete)
        self.assertEqual([(str(a), p) for a, p, _ in sockets], [("198.51.100.9", 3847)])

    # Each bad row: (table version, the row). Fields: sl local remote st.
    BAD_ROWS = {
        "state 0C": (4, "  5: 00000000:0F07 00000000:0000 0C 0 0 0"),
        "state ZZ": (4, "  5: 00000000:0F07 00000000:0000 ZZ 0 0 0"),
        "port 10000 hex": (4, "  5: 00000000:10000 00000000:0000 0A 0 0 0"),
        "short port": (4, "  5: 00000000:F07 00000000:0000 0A 0 0 0"),
        "v6 address in tcp": (4, "  5: " + "0" * 32 + ":0F07 00000000:0000 0A 0 0 0"),
        "v4 address in tcp6": (6, "  5: 00000000:0F07 " + "0" * 32 + ":0000 0A 0 0 0"),
        "short remote": (4, "  5: 00000000:0F07 0000:0000 0A 0 0 0"),
        "lowercase hex": (4, "  5: 0000000a:0f07 00000000:0000 0A 0 0 0"),
    }

    def test_each_invalid_row_makes_the_table_incomplete(self):
        from sproutwall_lib import net

        for label, (version, row) in self.BAD_ROWS.items():
            sockets, complete = net.parse_proc_net_tcp(proc_table([], v6=version == 6) + row + "\n", version)
            self.assertEqual((sockets, complete), ([], False), label)

    def test_invalid_rows_alone_are_unknown_and_never_hide_a_public_listener(self):
        for label, (version, row) in self.BAD_ROWS.items():
            table = "/proc/net/tcp6" if version == 6 else "/proc/net/tcp"
            s = healthy_pi()
            s.files[table] = proc_table([], v6=version == 6) + row + "\n"
            self.assertEqual(run("app_bind", s), ("unknown", "retry_local"), label)
            s = healthy_pi()
            public = [("2001:db8::9", 3847, "0A")] if version == 6 else [("198.51.100.9", 3847, "0A")]
            s.files[table] = proc_table(public, v6=version == 6) + row + "\n"
            self.assertEqual(run("app_bind", s), ("fail", "restrict_ports"), label)

    def test_container_tables_follow_the_same_rule(self):
        for label, (version, row) in self.BAD_ROWS.items():
            table = "/proc/net/tcp6" if version == 6 else "/proc/net/tcp"
            s = healthy_pi()
            s.set(exec_key("cat", table), ok(proc_table([], v6=version == 6) + row + "\n"))
            self.assertEqual(run("bridge_bind", s), ("unknown", "retry_local"), label)
            s = healthy_pi()
            open_bridge = [("::", 8787, "0A")] if version == 6 else [("0.0.0.0", 8787, "0A")]
            s.set(exec_key("cat", table), ok(proc_table(open_bridge, v6=version == 6) + row + "\n"))
            self.assertEqual(run("bridge_bind", s), ("fail", "restrict_ports"), label)

    def test_classify(self):
        import ipaddress

        from sproutwall_lib import net

        cases = {
            "127.0.0.1": "loopback", "::1": "loopback", "192.168.1.50": "lan", "10.1.2.3": "lan",
            "172.20.0.1": "lan", "fe80::1": "lan", "fd00::1": "lan", "::ffff:192.168.1.5": "lan",
            "2001:db8::1": "public", "203.0.113.7": "public", "100.64.0.1": "public",
        }
        for address, expected in cases.items():
            self.assertEqual(net.classify(ipaddress.ip_address(address)), expected, address)

    def test_container_format_requests_no_environment(self):
        self.assertNotIn("Env", checks.CONTAINER_FORMAT)
        self.assertNotIn(".Config", checks.CONTAINER_FORMAT)


if __name__ == "__main__":
    unittest.main()
