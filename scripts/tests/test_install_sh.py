"""install.sh, the one-command install, run against PATH shims.

Nothing here touches the host: every command install.sh may run is either a
fake in a private bin folder (sudo, apt, apt-get, docker, sg, git, curl, gh,
wget, hostname, uname, dpkg, id) or a plain text tool linked from the host
(ls, grep, sed, cat, mktemp, rm, tr, python3). Any other command is "not
found". /etc/os-release, /etc/rpi-issue and the device-tree model come from a
fake root folder, and the answers from a file instead of the terminal
(SPROUTWALL_INSTALL_TEST_ROOT and SPROUTWALL_INSTALL_TEST_TTY). The script is
fed to bash on stdin, as `curl ... | bash` does.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from sproutwall_lib import schema

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SCRIPTS)
INSTALL_SH = os.path.join(ROOT, "install.sh")
GUIDE = os.path.join(ROOT, "INSTALL-WITH-AI.md")
COMPOSE_TEMPLATE = os.path.join(ROOT, "docker-compose.preview.yml")
BASH = shutil.which("bash")

# Answers are followed by this line. A fictional PIN: if the script ever read
# one line more than it asked for, the flow tests would see it.
FAKE_PIN = "2468"
PROMPT_MARKERS = ("[y/N]", "[1-5, Enter = 1]", "(press Enter)")
# sed is not linked: the bin folder has a GNU-compatible sed (see SED_SHIM).
HOST_TOOLS = ("ls", "grep", "cat", "mktemp", "rm", "tr", "python3", "cmp", "diff", "mkdir", "cp", "tee")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def pinned_pair_in_script():
    text = read(INSTALL_SH)
    commit = re.search(r'^PINNED_SOURCE_COMMIT="([^"]*)"$', text, re.M).group(1)
    digest = re.search(r'^PINNED_IMAGE_DIGEST="([^"]*)"$', text, re.M).group(1)
    return commit, digest


def pinned_pair_in_guide():
    text = read(GUIDE)
    commit = re.search(r"^\| Source commit \| `([^`]*)` \|$", text, re.M).group(1)
    digest = re.search(r"^\| Image index digest \| `([^`]*)` \|$", text, re.M).group(1)
    return commit, digest


COMMIT, DIGEST = pinned_pair_in_script()


def host_free(err):
    """stderr without the one host-dependent line: Docker's own command reads
    /etc/os-release for the codename, and a test host (macOS) may have none."""
    return "\n".join(line for line in err.splitlines() if "/etc/os-release" not in line)


def doctor_json(phase, **overrides):
    """A real closed-schema doctor report: every check passes except overrides."""
    outcomes = {check_id: schema.PASS for check_id in schema.CHECK_IDS}
    outcomes.update(overrides)
    report = schema.build_report(phase, outcomes)
    return schema.serialize(report), schema.exit_code(report)


TRUSTED_LAN = {"app_bind": ("unknown", "confirm_trusted_lan")}

SHIMS = {
    "sudo": r"""#!/bin/bash
printf 'sudo %s\n' "$*" >>"$FAKE_LOG"
if [ "$1" = tee ]; then cat >/dev/null; fi
if [ -n "${FAKE_SUDO_FAIL:-}" ] && [ "$*" = "$FAKE_SUDO_FAIL" ]; then exit 100; fi
if [ -n "${FAKE_APT_LOCKED:-}" ] && [ "$*" = "$FAKE_APT_LOCKED" ]; then
  echo "E: Could not get lock /var/lib/dpkg/lock-frontend. It is held by process 812 (apt-get)" >&2
  echo "E: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), is another process using it?" >&2
  exit 100
fi
if [ "$1 $2" = "sshd -T" ]; then
  # The read-only look at the SSH settings (over SSH only).
  [ -z "${FAKE_SSHD_FAIL:-}" ] || exit 1
  printf '%b\n' "${FAKE_SSHD_T:-port 22\npermitrootlogin without-password\npasswordauthentication yes\npermitemptypasswords no}"
  exit 0
fi
if [ "$1" = cat ]; then
  # The read-only look at the SSH config files (over SSH only), under the test's fake root.
  shift
  exec cat "$@"
fi
if [ "$1" = sh ]; then
  # The read-only read of the whole SSH config as root (over SSH only), under the test's fake root.
  # FAKE_ROOT_BIN puts the test's own commands (a failing ls) first for root.
  [ -z "${FAKE_SUDO_SH_FAIL:-}" ] || exit 1
  shift
  [ -z "${FAKE_ROOT_BIN:-}" ] || PATH="$FAKE_ROOT_BIN:$PATH"
  exec /bin/sh "$@"
fi
if [ "$1" = ls ]; then
  # The read-only look into Docker's data folder; the path is under the test's fake root.
  shift
  exec ls "$@"
fi
if [ "$1" = docker ]; then
  # Root reaches the daemon (the read-only existing-hub check), unless the test says it does not answer.
  if [ -n "${FAKE_SUDO_DOCKER_FAIL:-}" ]; then echo "Cannot connect to the Docker daemon" >&2; exit 1; fi
  command -v docker >/dev/null || { echo "sudo: docker: command not found" >&2; exit 1; }
  shift
  FAKE_IN_SG=1 exec docker "$@"
fi
case "$*" in
  "apt install"* | "apt-get install"*)
    # apt with no -y stops at "Do you want to continue? [Y/n]" (opt-in, as seen in the VM run).
    if [ -n "${FAKE_APT_STRICT:-}" ] && [[ " $* " != *" -y "* ]]; then
      echo "Do you want to continue? [Y/n] Abort." >&2
      exit 1
    fi
    ;;
esac
case "$*" in
  "apt install"*docker-ce*)
    # A test can have the docker command appear only when the plan installs it.
    if [ -n "${FAKE_DOCKER_SHIM:-}" ]; then cp "$FAKE_DOCKER_SHIM" "$FAKE_BIN/docker"; fi
    ;;
esac
exit 0
""",
    "apt": "#!/bin/bash\nprintf 'apt %s\\n' \"$*\" >>\"$FAKE_LOG\"\nexit 0\n",
    "apt-get": "#!/bin/bash\nprintf 'apt-get %s\\n' \"$*\" >>\"$FAKE_LOG\"\nexit 0\n",
    "id": r"""#!/bin/bash
printf 'id %s\n' "$*" >>"$FAKE_LOG"
case "$1" in
  -u) echo "${FAKE_UID:-1000}" ;;
  -un) echo parent ;;
  *) echo "uid=1000(parent) gid=1000(parent)" ;;
esac
""",
    "uname": r"""#!/bin/bash
printf 'uname %s\n' "$*" >>"$FAKE_LOG"
case "$1" in
  -s) echo "${FAKE_KERNEL:-Linux}" ;;
  -m) echo "${FAKE_MACHINE:-aarch64}" ;;
  *) echo Linux ;;
esac
""",
    "dpkg": r"""#!/bin/bash
printf 'dpkg %s\n' "$*" >>"$FAKE_LOG"
[ "$1" = --print-architecture ] || exit 99
echo "${FAKE_ARCH:-arm64}"
""",
    "hostname": r"""#!/bin/bash
printf 'hostname %s\n' "$*" >>"$FAKE_LOG"
[ "$1" = -I ] || exit 99
count=$(( $(cat "$FAKE_STATE/hostname.count" 2>/dev/null || echo 0) + 1 ))
echo "$count" >"$FAKE_STATE/hostname.count"
if [ "$count" -ge "${FAKE_HOSTNAME_LATER_FROM:-2}" ] && [ -n "${FAKE_HOSTNAME_LATER:-}" ]; then
  echo "$FAKE_HOSTNAME_LATER"
else
  echo "${FAKE_HOSTNAME:-192.168.1.50 172.17.0.1 fd12:3456::50}"
fi
""",
    "ip": r"""#!/bin/bash
case "$*" in
  "-6 -o addr show scope global")
    # This device's global IPv6 addresses with prefix lengths.
    [ -z "${FAKE_IP6:-}" ] || printf '%b\n' "$FAKE_IP6"
    ;;
  "-o -6 addr show")
    # Every IPv6 address of this device, with its interface (over SSH, the
    # interface that holds the address the session connected to).
    printf '%b\n' "${FAKE_IP6_ALL-2: wlan0    inet6 fd12:3456::50/64 scope global dynamic mngtmpaddr \\       valid_lft 86000sec preferred_lft 14000sec\n2: wlan0    inet6 fe80::50/64 scope link \\       valid_lft forever preferred_lft forever}"
    ;;
  "-o -4 addr show" | "-o -4 addr show dev "*)
    # The IPv4 addresses of one interface, or of every interface.
    [ -z "${FAKE_IP4_FAIL:-}" ] || { echo "Device does not exist." >&2; exit 1; }
    want=${!#}
    listing="${FAKE_IP4-2: wlan0    inet 192.168.1.50/24 brd 192.168.1.255 scope global dynamic wlan0\\       valid_lft 86000sec preferred_lft 86000sec\n3: eth0    inet 192.168.1.51/24 brd 192.168.1.255 scope global eth0\\       valid_lft forever preferred_lft forever\n4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever}"
    printf '%b\n' "$listing" | while IFS= read -r line; do
      read -r _ dev _ <<<"$line"
      { [ "$want" = show ] || [ "$dev" = "$want" ]; } && printf '%s\n' "$line"
    done
    exit 0
    ;;
  "route get "*)
    # This device's route to the laptop's address: its interface.
    if [ -n "${FAKE_ROUTE_FAIL:-}" ]; then echo "RTNETLINK answers: Network is unreachable" >&2; exit 2; fi
    printf '%b\n' "${FAKE_ROUTE:-${!#} via 192.168.1.1 dev wlan0 src 192.168.1.50 uid 1000 \n    cache }"
    ;;
  *) exit 99 ;;
esac
""",
    "systemctl": r"""#!/bin/bash
# Only the unprivileged check that SSH is off after the last question (over SSH).
printf 'systemctl %s\n' "$*" >>"$FAKE_LOG"
[ "$*" = "is-active ssh.service ssh.socket" ] || exit 99
case "${FAKE_SSH_STATES:-off}" in
  off) printf 'inactive\ninactive\n'; exit 3 ;;
  socket-on) printf 'inactive\nactive\n'; exit 0 ;;
  *) echo "System has not been booted with systemd as init system (PID 1). Can't operate." >&2; exit 1 ;;
esac
""",
    "sg": r"""#!/bin/bash
printf 'sg %s\n' "$*" >>"$FAKE_LOG"
[ "$1" = docker ] && [ "$2" = -c ] && [ "$#" = 3 ] || exit 98
export FAKE_IN_SG=1
exec /bin/sh -c "$3"
""",
    "docker": r"""#!/bin/bash
printf 'docker %s\n' "$*" >>"$FAKE_LOG"
if [ -n "${FAKE_DOCKER_DENIED_OUTSIDE_SG:-}" ] && [ -z "${FAKE_IN_SG:-}" ]; then
  echo "permission denied while trying to connect to the Docker daemon socket" >&2
  exit 1
fi
case "$*" in
  "ps -a --format {{.Names}}") printf '%s' "${FAKE_CONTAINERS:-}"; [ -z "${FAKE_CONTAINERS_FILE:-}" ] || cat "$FAKE_CONTAINERS_FILE" ;;
  "volume ls -q") printf '%s' "${FAKE_VOLUMES:-}"; [ -z "${FAKE_VOLUMES_FILE:-}" ] || cat "$FAKE_VOLUMES_FILE" ;;
  "volume ls -q --filter name=familyhub-data") printf '%s' "${FAKE_VOLUMES:-}" | grep familyhub-data || true ;;
  "compose version") echo "Docker Compose version v2.39.1" ;;
  "info") echo "Server Version: 29.0.0" ;;
  "compose -f docker-compose.preview.yml up -d --wait") exit "${FAKE_UP_EXIT:-0}" ;;
  "compose -f docker-compose.preview.yml ps")
    echo "NAME                      IMAGE      SERVICE      STATUS"
    echo "sproutwall-family-hub-1   ghcr.io    family-hub   Up 12 seconds (${FAKE_PS_HEALTH:-healthy})"
    [ -z "${FAKE_PS_EXTRA_FILE:-}" ] || cat "$FAKE_PS_EXTRA_FILE"
    ;;
  *) echo "fake docker: unexpected call" >&2; exit 99 ;;
esac
""",
    "gh": r"""#!/bin/bash
printf 'gh %s\n' "$*" >>"$FAKE_LOG"
case "$*" in
  --version) echo "gh version ${FAKE_GH_VERSION:-2.105.0} (2026-01-01)"; echo "https://github.com/cli/cli/releases/tag/v2.105.0" ;;
  "attestation verify --help") exit 0 ;;
  *) exit 99 ;;
esac
""",
    "wget": r"""#!/bin/bash
printf 'wget %s\n' "$*" >>"$FAKE_LOG"
for arg in "$@"; do
  case "$arg" in -O*) echo "fake keyring" >"${arg#-O}" ;; esac
done
""",
    "curl": r"""#!/bin/bash
printf 'curl %s\n' "$*" >>"$FAKE_LOG"
case "$*" in
  "-fsS --max-time 3 http://127.0.0.1:3847/api/health")
    case "${FAKE_HEALTH:-ok}" in
      ok) echo '{"ok":true,"version":"0.1.0-preview.0","schema":12,"setup":false}' ;;
      503) echo "curl: (22) The requested URL returned error: 503" >&2; exit 22 ;;
      *) echo "curl: (7) Failed to connect" >&2; exit 7 ;;
    esac
    ;;
  *) exit 99 ;;
esac
""",
    "git": r"""#!/bin/bash
printf 'git %s\n' "$*" >>"$FAKE_LOG"
case "$1" in
  clone)
    [ "$#" = 3 ] && [ "$2" = "https://github.com/thebrianlee/sproutwall.git" ] || exit 99
    mkdir "$3" || exit 128
    mkdir -p "$3/.git" "$3/scripts"
    cp "$FAKE_COMPOSE_TEMPLATE" "$3/docker-compose.preview.yml"
    cp "$FAKE_COMPOSE_TEMPLATE" "$3/.git/original-compose"
    cp "$FAKE_SPROUTWALL" "$3/scripts/sproutwall"
    echo "$2" >"$3/.git/origin"
    echo 0000000000000000000000000000000000000000 >"$3/.git/head"
    ;;
  checkout) [ "$2" = --detach ] && echo "${FAKE_CHECKOUT_HEAD:-$3}" >.git/head ;;
  remote) [ "$2 $3" = "get-url origin" ] && cat .git/origin ;;
  rev-parse) [ "$2" = HEAD ] && cat .git/head ;;
  status)
    [ "$2" = --short ] || exit 99
    cmp -s .git/original-compose docker-compose.preview.yml || echo " M docker-compose.preview.yml"
    ;;
  diff)
    [ "$2" = --numstat ] || exit 99
    if ! cmp -s .git/original-compose docker-compose.preview.yml; then
      removed=$(diff .git/original-compose docker-compose.preview.yml | grep -c '^<')
      added=$(diff .git/original-compose docker-compose.preview.yml | grep -c '^>')
      printf '%s\t%s\tdocker-compose.preview.yml\n' "$added" "$removed"
    fi
    ;;
  *) exit 99 ;;
esac
""",
}

# GNU-compatible sed for the tests. install.sh runs GNU `sed -i EXPR FILE`,
# exactly as the guide writes it (the installer targets Debian-family
# systems). On a host whose sed is BSD (macOS), `-i` needs a suffix argument,
# so this wrapper passes `-i ""` there. FAKE_HOST_SED is the host's sed.
SED_SHIM = r"""#!/bin/bash
real="$FAKE_HOST_SED"
if "$real" --version >/dev/null 2>&1; then exec "$real" "$@"; fi
args=()
for arg in "$@"; do
  if [ "$arg" = -i ]; then args+=(-i ""); else args+=("$arg"); fi
done
exec "$real" "${args[@]}"
"""

# A small stand-in for BSD sed (macOS), enough for install.sh's one call: like
# BSD sed, -i always takes the next word as the backup suffix, and --version
# is an illegal option. It lets Linux CI prove the wrapper above works there.
BSD_SED = r"""import re, sys
args = sys.argv[1:]
if args[:1] == ["--version"]:
    sys.stderr.write("sed: illegal option -- -\n")
    sys.exit(1)
suffix, i = None, 0
while i < len(args) and args[i].startswith("-"):
    if args[i] == "-i":
        suffix, i = args[i + 1], i + 2
    elif args[i].startswith("-i"):
        suffix, i = args[i][2:], i + 1
    else:
        sys.exit(1)
script, files = args[i], args[i + 1:]
match = re.fullmatch(r"s(.)(.*?)\1(.*?)\1", script, re.S)
if not match:
    sys.stderr.write('sed: 1: "%s": invalid command code %s\n' % (script, script[:1]))
    sys.exit(1)
pattern, replacement = re.compile(match.group(2)), match.group(3)
for name in files:
    with open(name, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    out = "\n".join(pattern.sub(lambda _m: replacement, line, count=1) for line in lines)
    if suffix is None:
        sys.stdout.write(out)
    else:
        if suffix:
            with open(name + suffix, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
        with open(name, "w", encoding="utf-8") as handle:
            handle.write(out)
"""

# The fake scripts/sproutwall that the fake clone puts in the checkout.
FAKE_SPROUTWALL = r"""#!/bin/bash
printf 'sproutwall %s\n' "$*" >>"$FAKE_LOG"
if [ "$1" = verify-image ]; then
  digest=$5
  grep -q "@${digest}\"" docker-compose.preview.yml || exit 2
  exit "${FAKE_VERIFY_EXIT:-0}"
fi
if [ "$1" = doctor ] && [ "$2" = --json ]; then
  phase=$4
  count=$(( $(cat "$FAKE_STATE/doctor-$phase.count" 2>/dev/null || echo 0) + 1 ))
  echo "$count" >"$FAKE_STATE/doctor-$phase.count"
  base="$FAKE_STATE/doctor-$phase"
  [ -e "$base-$count.json" ] && base="$base-$count"
  cat "$base.json"
  exit "$(cat "$base.exit")"
fi
if [ "$1" = doctor ]; then
  echo "Result: unknown (exit 2)"
  exit 2
fi
if [ "$1 $2" = "setup kiosk" ] && [ "${3:-}" = --check ]; then
  if [ -n "${FAKE_KIOSK_CHECK_EXIT:-}" ] && [ "$FAKE_KIOSK_CHECK_EXIT" != 0 ]; then
    echo "Result: attention (exit $FAKE_KIOSK_CHECK_EXIT)"
    exit "$FAKE_KIOSK_CHECK_EXIT"
  fi
  echo "Result: ok (exit 0)"
  exit 0
fi
if [ "$1 $2" = "setup kiosk" ]; then
  count=$(( $(cat "$FAKE_STATE/kiosk.count" 2>/dev/null || echo 0) + 1 ))
  echo "$count" >"$FAKE_STATE/kiosk.count"
  if [ -n "${FAKE_KIOSK_EXIT:-}" ] && [ "$FAKE_KIOSK_EXIT" != 0 ]; then
    echo "Stopped: no connected screen was found." >&2
    exit "$FAKE_KIOSK_EXIT"
  fi
  echo "Kiosk set up on the HDMI screen: portrait (output transform 90)."
  echo "Autologin: off. This step needs administrator rights, so this tool does not do it. Run it yourself in the Pi's terminal; sudo asks for your password:"
  echo "  sudo raspi-config nonint do_boot_behaviour B4"
  echo ""
  echo "Then restart to start the kiosk: sudo reboot"
  exit 0
fi
exit 99
"""


class Run:
    def __init__(self, code, out, err, log, home, prompts):
        self.code = code
        self.out = out
        self.err = err
        self.log = log
        self.home = home
        self.prompts = prompts

    def commands(self):
        return {line.split(" ", 1)[0] for line in self.log}

    def index(self, line):
        return self.log.index(line)


class InstallShTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="install-sh-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        self.state = os.path.join(self.tmp, "state")
        self.sysroot = os.path.join(self.tmp, "root")
        bin_dir = os.path.join(self.tmp, "bin")
        host_dir = os.path.join(self.tmp, "hostbin")
        for path in (self.home, self.state, bin_dir, host_dir, os.path.join(self.tmp, "tmp")):
            os.makedirs(path)
        for name, body in SHIMS.items():
            self.write(os.path.join(bin_dir, name), body, 0o755)
        self.write(os.path.join(bin_dir, "sed"), SED_SHIM, 0o755)
        self.bin_dir = bin_dir
        for name in HOST_TOOLS:
            found = shutil.which(name)
            self.assertIsNotNone(found, name)
            os.symlink(found, os.path.join(host_dir, name))
        self.fake_sproutwall = self.write(os.path.join(self.state, "fake-sproutwall"), FAKE_SPROUTWALL, 0o755)
        self.log_path = os.path.join(self.state, "log")
        self.tty = os.path.join(self.tmp, "tty")
        self.env = {
            "PATH": bin_dir + ":" + host_dir,
            "HOME": self.home,
            "USER": "parent",
            "LANG": "C.UTF-8",
            "TMPDIR": os.path.join(self.tmp, "tmp"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "FAKE_LOG": self.log_path,
            "FAKE_STATE": self.state,
            "FAKE_COMPOSE_TEMPLATE": COMPOSE_TEMPLATE,
            "FAKE_SPROUTWALL": self.fake_sproutwall,
            "FAKE_HOST_SED": shutil.which("sed"),
            "SPROUTWALL_INSTALL_TEST_ROOT": self.sysroot,
            "SPROUTWALL_INSTALL_TEST_TTY": self.tty,
        }
        self.raspberry_pi_os()
        self.doctor("running", **TRUSTED_LAN)
        self.doctor("configured", **TRUSTED_LAN)

    def write(self, path, text, mode=0o644):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(path, mode)
        return path

    def raspberry_pi_os(self, model="Raspberry Pi 5 Model B Rev 1.0"):
        self.write(
            os.path.join(self.sysroot, "etc/os-release"),
            'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nID=debian\nVERSION_CODENAME=trixie\n',
        )
        self.write(os.path.join(self.sysroot, "etc/rpi-issue"), "Raspberry Pi reference 2026-10-01\n")
        self.write(os.path.join(self.sysroot, "proc/device-tree/model"), model + "\0")

    def docker_installed_by_the_plan(self):
        """No docker command at first; the plan's `apt install ... docker-ce` brings it."""
        shim = os.path.join(self.state, "docker-shim")
        os.rename(os.path.join(self.bin_dir, "docker"), shim)
        self.env.update(FAKE_DOCKER_SHIM=shim, FAKE_BIN=self.bin_dir)

    def ubuntu_pc(self):
        shutil.rmtree(self.sysroot)
        self.write(
            os.path.join(self.sysroot, "etc/os-release"),
            'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_CODENAME=noble\nUBUNTU_CODENAME=noble\n',
        )
        self.env.update(FAKE_ARCH="amd64", FAKE_MACHINE="x86_64")

    def doctor(self, phase, number=None, **overrides):
        text, code = doctor_json(phase, **overrides)
        base = os.path.join(self.state, "doctor-%s%s" % (phase, "" if number is None else "-%d" % number))
        self.write(base + ".json", text + "\n")
        self.write(base + ".exit", "%d\n" % code)

    def run_install(self, answers, **env):
        self.write(self.tty, "".join(line + "\n" for line in answers) + FAKE_PIN + "\n")
        full_env = dict(self.env)
        full_env.update(env)
        proc = subprocess.run(
            [BASH],
            input=read(INSTALL_SH).encode(),
            env=full_env,
            cwd=self.tmp,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
        log = read(self.log_path).splitlines() if os.path.exists(self.log_path) else []
        out, err = proc.stdout.decode(), proc.stderr.decode()
        prompts = sum(out.count(marker) for marker in PROMPT_MARKERS)
        for text in (out, err, "\n".join(log)):
            self.assertNotIn(FAKE_PIN, text)
        return Run(proc.returncode, out, err, log, self.home, prompts)

    def assert_stopped_before_changes(self, run):
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1, run.err)
        self.assertLessEqual(run.commands(), {"id", "uname", "dpkg", "docker", "hostname"}, run.log)
        self.assertEqual(run.prompts, 0, run.out)
        self.assertFalse(os.path.exists(os.path.join(run.home, "sproutwall")))

    def assert_never_destructive(self, run):
        joined = "\n".join(run.log)
        for pattern in (r"\bdown\b", r"volume rm", r"\bprune\b", r"gh auth", r"\bpull\b", r"(?m)^(sudo )?rm\b", r":preview"):
            self.assertNotRegex(joined, pattern)


HAPPY_ANSWERS = ["", "y", "y", "", "", "y"]  # portrait, plan, home network, setup done, taps, autologin


class PinnedPairTests(unittest.TestCase):
    def test_pinned_pair_equals_the_guides_table(self):
        self.assertEqual(pinned_pair_in_script(), pinned_pair_in_guide())

    def test_pinned_pair_is_well_formed(self):
        commit, digest = pinned_pair_in_script()
        self.assertRegex(commit, r"^[0-9a-f]{40}$")
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")

    def test_guide_uses_the_same_pair_in_steps_3_and_4(self):
        commit, digest = pinned_pair_in_guide()
        guide = read(GUIDE)
        self.assertEqual(set(re.findall(r"checkout --detach (\S+)", guide)), {commit})
        self.assertEqual(set(re.findall(r"--source-sha ([0-9a-f]{40})", guide)), {commit})
        self.assertEqual(set(re.findall(r"@sha256:([0-9a-f]{64})", guide)), {digest[len("sha256:"):]})


class MirrorsTheGuideTests(unittest.TestCase):
    def guide_block_after(self, marker):
        guide = read(GUIDE)
        start = guide.index("```bash", guide.index(marker)) + len("```bash")
        return [line.strip() for line in guide[start : guide.index("```", start)].strip().splitlines()]

    def test_github_cli_block_is_the_guides_block(self):
        script = [line.strip() for line in read(INSTALL_SH).splitlines()]
        block = self.guide_block_after("**GitHub CLI (`gh`).**")
        self.assertGreater(len(block), 5)
        for line in block:
            # Once where it runs (install_gh) and once in the printed plan.
            self.assertGreaterEqual(script.count(line), 2, line)

    def test_step_3_and_4_commands_are_the_guides(self):
        script = read(INSTALL_SH)
        for line in self.guide_block_after("### Install the tools"):
            self.assertIn(line, script)
        self.assertIn("sudo usermod -aG docker", script)
        self.assertIn("""sed -i 's|@sha256:<published-index-digest-hex>"|@sha256:'"$hex"'"|'""", script)
        self.assertIn('test "$(git remote get-url origin)" = "https://github.com/thebrianlee/sproutwall.git"', script)
        self.assertIn('docker compose -f "$PREVIEW" up -d --wait', script)
        self.assertIn("curl -fsS --max-time 3", script)

    def test_links_point_to_existing_sections(self):
        def anchors(path):
            found = set()
            for heading in re.findall(r"(?m)^#+ (.+)$", read(path)):
                slug = re.sub(r"[^a-z0-9 -]", "", heading.replace("`", "").lower()).replace(" ", "-")
                found.add(slug)
            return found

        script = read(INSTALL_SH)
        targets = {
            "INSTALL-WITH-AI.md": (GUIDE, re.findall(r"\$GUIDE#([a-z0-9-]+)", script)),
            "docs/raspberry-pi.md": (os.path.join(ROOT, "docs", "raspberry-pi.md"), re.findall(r"\$PI_GUIDE#([a-z0-9-]+)", script)),
        }
        for name, (path, links) in targets.items():
            self.assertTrue(links, name)
            for link in links:
                self.assertIn(link, anchors(path), name)
        self.assertIn("with-one-command", anchors(os.path.join(ROOT, "README.md")))

    def test_no_destructive_or_unsafe_command(self):
        script = read(INSTALL_SH)
        for word in ("prune", "sudoers", "REQUIRE_AUTH_FOR_READS", "8787", "GH_TOKEN", "GITHUB_TOKEN"):
            self.assertNotIn(word, script)
        # "down -v" and "volume rm" appear only in the advice never to run them.
        for word in ("down -v", "volume rm"):
            lines = [line.strip() for line in script.splitlines() if word in line]
            self.assertEqual(lines, ['say "  The household lives in its Docker volume. Never run docker compose down -v or docker volume rm."'])
        removals = re.findall(r"\brm -rf? [^\n]*", script)
        self.assertEqual(removals, ['rm -rf "$WORK_DIR"'])
        self.assertNotRegex(script, r"(?m)^\s*(sudo )?gh auth")
        self.assertNotRegex(script, r"(?m)^\s*docker[^\n]*:preview")


class PreflightTests(InstallShTestCase):
    def test_existing_sproutwall_folder_stops_in_preflight(self):
        os.mkdir(os.path.join(self.home, "sproutwall"))
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 1)
        self.assertIn("#existing-install--update", run.err)
        self.assertLessEqual(run.commands(), {"id", "uname", "dpkg"}, run.log)
        self.assertEqual(run.prompts, 0)

    def test_existing_family_hub_folder_stops(self):
        os.mkdir(os.path.join(self.home, "family-hub"))
        run = self.run_install(HAPPY_ANSWERS)
        self.assertIn("#existing-install--update", run.err)
        self.assertLessEqual(run.commands(), {"id", "uname", "dpkg"}, run.log)

    def test_existing_docker_volume_stops(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_VOLUMES="family-hub_familyhub-data\n")
        self.assert_stopped_before_changes(run)
        self.assertIn("#existing-install--update", run.err)
        self.assertIn("docker volume ls -q", run.log)

    def test_existing_container_stops(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_CONTAINERS="sproutwall-family-hub-1\n")
        self.assert_stopped_before_changes(run)
        self.assertIn("#existing-install--update", run.err)

    def test_root_stops(self):
        for env in ({"FAKE_UID": "0"}, {"SUDO_USER": "parent"}):
            with self.subTest(env=env):
                run = self.run_install(HAPPY_ANSWERS, **env)
                self.assert_stopped_before_changes(run)
                self.assertIn("not as root", run.err)
                self.assertEqual(run.commands(), {"id"})

    def test_unsupported_systems_stop(self):
        cases = {
            "fedora": ("etc/os-release", "ID=fedora\nVERSION_ID=43\n"),
            "32-bit Raspberry Pi OS": ("etc/os-release", "ID=raspbian\nVERSION_CODENAME=trixie\n"),
            "Raspberry Pi 3": ("proc/device-tree/model", "Raspberry Pi 3 Model B Plus Rev 1.3\0"),
        }
        for name, (path, text) in cases.items():
            with self.subTest(name):
                self.raspberry_pi_os()
                self.write(os.path.join(self.sysroot, path), text)
                run = self.run_install(HAPPY_ANSWERS)
                self.assert_stopped_before_changes(run)
                self.assertIn("#supported-devices", run.err)
        with self.subTest("32-bit userland"):
            self.raspberry_pi_os()
            run = self.run_install(HAPPY_ANSWERS, FAKE_ARCH="armhf")
            self.assert_stopped_before_changes(run)
            self.assertIn("64-bit", run.err)
        with self.subTest("not Linux"):
            run = self.run_install(HAPPY_ANSWERS, FAKE_KERNEL="Darwin")
            self.assert_stopped_before_changes(run)

    def test_no_terminal_prints_the_manual_guide(self):
        self.env["SPROUTWALL_INSTALL_TEST_TTY"] = os.path.join(self.tmp, "no-such-tty")
        run = self.run_install([])
        self.assert_stopped_before_changes(run)
        self.assertIn("INSTALL-WITH-AI.md#without-ai", run.err)

    def test_public_address_stops_before_any_change(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_HOSTNAME="203.0.113.7 192.168.1.50")
        self.assert_stopped_before_changes(run)
        self.assertIn("hostname -I", run.log)
        self.assertIn("home network", run.err)


class ConsentTests(InstallShTestCase):
    def test_no_at_the_plan_prompt_changes_nothing(self):
        for answer in ("n", "", "maybe", "no"):
            with self.subTest(answer=answer):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(["", answer])
                self.assertEqual(run.code, 0, run.err)
                self.assertIn("THE INSTALL PLAN", run.out)
                self.assertIn("nothing was changed", run.out)
                self.assertNotIn("sudo", run.commands())
                self.assertEqual(run.prompts, 2)

    def test_no_at_the_home_network_rule_changes_nothing(self):
        run = self.run_install(["", "y", "n"])
        self.assertEqual(run.code, 0, run.err)
        self.assertIn("trusted home network", run.out)
        self.assertNotIn("sudo", run.commands())

    def test_no_answer_at_all_changes_nothing(self):
        self.write(self.tty, "")
        full_env = dict(self.env)
        proc = subprocess.run(
            [BASH], input=read(INSTALL_SH).encode(), env=full_env, cwd=self.tmp, capture_output=True, timeout=60
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("sudo ", read(self.log_path))


class FailureTests(InstallShTestCase):
    def test_verify_image_failure_stops_before_compose_up(self):
        for code, words in ((1, "not verified"), (4, "internet connection"), (5, "sproutwall-verify-")):
            with self.subTest(code=code):
                shutil.rmtree(self.home)
                os.mkdir(self.home)
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(HAPPY_ANSWERS, FAKE_VERIFY_EXIT=str(code))
                self.assertEqual(run.code, 1, run.out + run.err)
                self.assertIn(words, run.err)
                self.assertIn("sproutwall verify-image --source-sha %s --digest %s" % (COMMIT, DIGEST), run.log)
                self.assertFalse([line for line in run.log if " up " in line or line.startswith("curl")], run.log)
                self.assert_never_destructive(run)

    def test_public_address_at_start_stops_before_compose_up(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_HOSTNAME_LATER="192.168.1.50 198.51.100.20")
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("home-network ranges", run.err)
        verify = run.index("sproutwall verify-image --source-sha %s --digest %s" % (COMMIT, DIGEST))
        self.assertEqual(run.log[verify + 1 :], ["hostname -I"])

    def test_health_503_stops_with_the_guides_message(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_HEALTH="503")
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("the database is blocked", run.err)
        self.assertIn("Don't start over with a new volume", run.err)
        self.assertIn("docker compose -f docker-compose.preview.yml logs", run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)
        self.assertNotIn("sproutwall doctor --json --phase running --tier C", run.log)
        self.assert_never_destructive(run)

    def test_compose_up_failure_with_503_stops_with_the_guides_message(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_UP_EXIT="1", FAKE_HEALTH="503")
        self.assertEqual(run.code, 1)
        self.assertIn("the database is blocked", run.err)
        self.assert_never_destructive(run)

    def test_unhealthy_hub_stops(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_PS_HEALTH="health: starting")
        self.assertEqual(run.code, 1)
        self.assertIn("not reported healthy", run.err)
        self.assert_never_destructive(run)

    def test_doctor_unknown_other_than_trusted_lan_stops(self):
        self.doctor("running", ssh_policy=("unknown", "review_ssh"), **TRUSTED_LAN)
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("#if-something-goes-wrong", run.err)
        self.assertIn("sproutwall doctor --phase running --tier C", run.log)
        self.assertNotIn("sproutwall setup kiosk", run.log)
        self.assertEqual(run.prompts, 3)

    def test_doctor_fail_stops(self):
        self.doctor("running", app_bind=("fail", "restrict_ports"))
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 1)
        self.assertNotIn("sproutwall setup kiosk", run.log)

    def test_failed_system_update_stops_before_the_code(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_SUDO_FAIL="apt full-upgrade -y")
        self.assertEqual(run.code, 1)
        self.assertIn("safe to run this script again", run.err)
        self.assertNotIn("git", run.commands())
        self.assertEqual(run.log.count("sudo apt install -y git"), 0)

    def test_old_gh_stops_before_the_code(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_GH_VERSION="2.46.0")
        self.assertEqual(run.code, 1)
        self.assertIn("gh 2.68.0 or newer", run.err)
        self.assertNotIn("git", run.commands())


class HappyPathTests(InstallShTestCase):
    def test_calls_happen_in_the_documented_order(self):
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(host_free(run.err), "")
        # Every answer was asked for, and nothing more was read: the line
        # after the answers (a PIN) was never consumed.
        self.assertEqual(run.prompts, len(HAPPY_ANSWERS))
        expected = [
            "sudo apt update",
            "sudo apt full-upgrade -y",
            "sudo apt install -y git",
            "sudo apt install -y ca-certificates curl",
            "sudo install -m 0755 -d /etc/apt/keyrings",
            "sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc",
            "sudo chmod a+r /etc/apt/keyrings/docker.asc",
            "sudo tee /etc/apt/sources.list.d/docker.sources",
            "sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
            "sudo usermod -aG docker parent",
            "sudo mkdir -p -m 755 /etc/apt/keyrings",
            "sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg",
            "sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg",
            "sudo tee /etc/apt/sources.list.d/github-cli.list",
            "sudo apt install gh -y",
            "docker compose version",
            "docker info",
            "gh --version",
            "gh attestation verify --help",
            "docker volume ls -q",
            "docker ps -a --format {{.Names}}",
            "git clone https://github.com/thebrianlee/sproutwall.git sproutwall",
            "git checkout --detach " + COMMIT,
            "git remote get-url origin",
            "git rev-parse HEAD",
            "git status --short",
            "git diff --numstat",
            "sproutwall verify-image --source-sha %s --digest %s" % (COMMIT, DIGEST),
            "hostname -I",
            "docker compose -f docker-compose.preview.yml up -d --wait",
            "curl -fsS --max-time 3 http://127.0.0.1:3847/api/health",
            "docker compose -f docker-compose.preview.yml ps",
            "sproutwall doctor --json --phase running --tier C",
            "sproutwall doctor --json --phase configured --tier C",
            "sproutwall setup kiosk",
            "sudo raspi-config nonint do_boot_behaviour B4",
            "sproutwall setup kiosk --check",
        ]
        position = 0
        for line in expected:
            self.assertIn(line, run.log[position:], "%r missing or out of order" % line)
            position = run.log.index(line, position) + 1

        # Docker, verify-image and doctor run with the docker group (sg), no re-login.
        for index, line in enumerate(run.log):
            if line.startswith(("docker compose", "sproutwall verify-image", "sproutwall doctor")):
                self.assertTrue(run.log[index - 1].startswith("sg docker -c "), line)
        # After the hub starts, the only sudo is the approved autologin line.
        up = run.index("docker compose -f docker-compose.preview.yml up -d --wait")
        self.assertEqual(
            [line for line in run.log[up:] if line.startswith("sudo")],
            ["sudo raspi-config nonint do_boot_behaviour B4"],
        )
        # Every sudo command that ran was shown in the plan before the first sudo.
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        for line in run.log:
            if line.startswith("sudo"):
                self.assertIn(line, plan)
        self.assertNotIn("apt", run.commands())
        self.assertNotIn("apt-get", run.commands())
        self.assert_never_destructive(run)

        compose = read(os.path.join(self.home, "sproutwall", "docker-compose.preview.yml"))
        self.assertEqual(compose.count('@%s"' % DIGEST), 1)
        self.assertNotIn('@sha256:<published-index-digest-hex>"', compose)
        self.assertIn("Source OK", run.out)
        self.assertIn("app_bind / confirm_trusted_lan", run.out)
        self.assertIn("http://localhost:3847", run.out)
        self.assertIn("http://192.168.1.50:3847", run.out)
        self.assertIn("sudo reboot", run.out)
        self.assertIn("doctor --phase final --tier C --kiosk on", run.out)
        self.assertIn("never asks for it", run.out)

    def test_a_second_run_hits_the_existing_install_stop(self):
        first = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(first.code, 0, first.err)
        os.remove(self.log_path)
        second = self.run_install(HAPPY_ANSWERS, FAKE_VOLUMES="sproutwall_familyhub-data\n")
        self.assertEqual(second.code, 1)
        self.assertIn("#existing-install--update", second.err)
        self.assertNotIn("sudo", second.commands())

    def test_landscape_and_no_kiosk(self):
        run = self.run_install(["3", "y", "y", "", "", "y"])
        self.assertEqual(run.code, 0, run.err)
        self.assertIn("sproutwall setup kiosk --orientation landscape", run.log)
        os.remove(self.log_path)
        shutil.rmtree(self.home)
        os.mkdir(self.home)
        for name in os.listdir(self.state):
            if name.endswith(".count"):
                os.remove(os.path.join(self.state, name))
        run = self.run_install(["5", "y", "y", ""])
        self.assertEqual(run.code, 0, run.err)
        self.assertEqual(run.prompts, 4)
        self.assertFalse([line for line in run.log if "setup kiosk" in line or "raspi-config" in line])
        self.assertNotIn("do_boot_behaviour", run.out[: run.out.index("Do you approve this plan?")])
        self.assertIn("--kiosk off", run.out)

    def test_ubuntu_pc_uses_dockers_ubuntu_commands_and_no_kiosk(self):
        self.ubuntu_pc()
        run = self.run_install(["y", "y", ""])
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(run.prompts, 3)
        self.assertIn(
            "sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc", run.log
        )
        self.assertFalse([line for line in run.log if "setup kiosk" in line])
        self.assertIn("kiosk-on-other-devices", run.out)
        self.assertIn("--kiosk off", run.out)

    def test_waits_until_household_setup_is_finished(self):
        self.doctor("configured", 1, setup=("fail", "open_hub"), read_guard=("fail", "open_hub"), **TRUSTED_LAN)
        run = self.run_install(["", "y", "y", "", "", "", "y"])
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(run.prompts, 7)
        self.assertIn("Setup is not finished yet", run.out)
        self.assertEqual(run.log.count("sproutwall doctor --json --phase configured --tier C"), 2)

    def test_kiosk_screen_not_found_can_be_skipped(self):
        run = self.run_install(["", "y", "y", "", "n"], FAKE_KIOSK_EXIT="4")
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(run.prompts, 5)
        self.assertIn("reconnect the one screen", run.out)
        self.assertNotIn("sudo raspi-config nonint do_boot_behaviour B4", run.log)
        self.assertIn("--kiosk off", run.out)

    def test_kiosk_check_on_the_device_has_no_ssh_hint(self):
        run = self.run_install(["", "y", "y", "", "", "y"], FAKE_KIOSK_CHECK_EXIT="1")
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("The screen check needs attention", run.out)
        self.assertNotIn("With no keyboard and SSH off", run.out)

    def test_declined_autologin_is_not_run(self):
        run = self.run_install(["", "y", "y", "", "", "n"])
        self.assertEqual(run.code, 0, run.err)
        self.assertNotIn("sudo raspi-config nonint do_boot_behaviour B4", run.log)
        self.assertIn("sproutwall setup kiosk --check", run.log)


DOCKER_PAGE_LINES = {
    # Docker's "Install using the apt repository", steps 1 and 2, with -y added
    # to the two apt installs (the person approved them in the plan).
    "debian": [
        "sudo apt update",
        "sudo apt install -y ca-certificates curl",
        "sudo install -m 0755 -d /etc/apt/keyrings",
        "sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc",
        "sudo chmod a+r /etc/apt/keyrings/docker.asc",
        "sudo tee /etc/apt/sources.list.d/docker.sources <<EOF",
        "URIs: https://download.docker.com/linux/debian",
        'Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")',
        "Architectures: $(dpkg --print-architecture)",
        "Signed-By: /etc/apt/keyrings/docker.asc",
        "sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
    ],
    "ubuntu": [
        "sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc",
        "URIs: https://download.docker.com/linux/ubuntu",
        'Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")',
    ],
}


class AptNeverWaitsTests(InstallShTestCase):
    """Point 6: apt stopped at [Y/n] in the VM; every approved install has -y."""

    def test_every_apt_install_has_y(self):
        installs = [
            line.strip()
            for line in read(INSTALL_SH).splitlines()
            if re.search(r"\bapt(-get)? install\b", line)
        ]
        self.assertGreaterEqual(len(installs), 8)
        for line in installs:
            self.assertRegex(line, r"apt(-get)? install( \S+)* -y\b|apt(-get)? install -y\b", line)

    def test_docker_lines_are_dockers_with_y_in_plan_and_run(self):
        script = [line.strip().removesuffix(" || return 1") for line in read(INSTALL_SH).splitlines()]
        for variant, lines in DOCKER_PAGE_LINES.items():
            for line in lines:
                # Once in the printed plan and once where it runs, per variant.
                self.assertGreaterEqual(script.count(line), 2, (variant, line))

    def test_docker_apt_installs_never_wait_for_a_yes(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_APT_STRICT="1")
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn(
            "sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
            run.log,
        )
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        self.assertIn("with -y added to its two apt installs because you approve them here", plan)


class ExistingHubBeforeChangesTests(InstallShTestCase):
    """Point 1: Docker installed but out of reach: a read-only sudo check right
    after approval, before the first change. Point 2: one matcher everywhere."""

    READ_ONLY = ["sudo docker ps -a --format {{.Names}}", "sudo docker volume ls -q"]

    def test_unreachable_docker_with_a_hub_stops_before_any_change(self):
        for hub in ({"FAKE_VOLUMES": "sproutwall_familyhub-data\n"}, {"FAKE_CONTAINERS": "family-hub-family-hub-1\n"}):
            with self.subTest(hub=hub):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(["", "y", "y"], FAKE_DOCKER_DENIED_OUTSIDE_SG="1", **hub)
                self.assertEqual(run.code, 1, run.out + run.err)
                self.assertIn("#existing-install--update", run.err)
                self.assertEqual([line for line in run.log if line.startswith("sudo")], self.READ_ONLY)
                self.assertEqual(run.prompts, 2)
                self.assertNotIn("git", run.commands())
                self.assertIn("sudo docker ps -a --format '{{.Names}}'", run.out)

    def test_docker_that_does_not_answer_even_with_sudo_stops_with_nothing_changed(self):
        run = self.run_install(["", "y", "y"], FAKE_DOCKER_DENIED_OUTSIDE_SG="1", FAKE_SUDO_DOCKER_FAIL="1")
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("cannot tell whether a hub is already on this device. Nothing was changed.", run.err)
        self.assertEqual([line for line in run.log if line.startswith("sudo")], self.READ_ONLY[:1])

    def test_unreachable_docker_without_a_hub_checks_first_then_installs(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_DOCKER_DENIED_OUTSIDE_SG="1")
        self.assertEqual(run.code, 0, run.out + run.err)
        sudo = [line for line in run.log if line.startswith("sudo")]
        self.assertEqual(sudo[:3], self.READ_ONLY + ["sudo apt update"])
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        for line in sudo:
            self.assertIn(line, plan.replace("'", ""))
        self.assertIn("Read-only, right after you approve and before anything changes", plan)

    def test_no_docker_command_needs_no_check(self):
        self.docker_installed_by_the_plan()
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertFalse([line for line in run.log if line.startswith("sudo docker")])
        self.assertNotIn("Read-only, right after you approve", run.out)

    def test_second_check_matches_every_hub_name(self):
        # Docker's data can outlive an uninstalled docker command: the first
        # check sees no docker; the check after the install must catch any name.
        for hub in (
            {"FAKE_VOLUMES": "family-hub_photos\n"},
            {"FAKE_VOLUMES": "sproutwall_data\n"},
            {"FAKE_VOLUMES": "old_familyhub-data\n"},
            {"FAKE_CONTAINERS": "sproutwall-family-hub-1\n"},
        ):
            with self.subTest(hub=hub):
                self.setUp()
                self.docker_installed_by_the_plan()
                run = self.run_install(HAPPY_ANSWERS, **hub)
                self.assertEqual(run.code, 1, run.out + run.err)
                self.assertIn("#existing-install--update", run.err)
                self.assertIn("sudo usermod -aG docker parent", run.log)
                self.assertNotIn("git", run.commands())

    def test_one_matcher_for_every_check(self):
        script = read(INSTALL_SH)
        self.assertEqual(script.count("*sproutwall* | *family-hub* | *familyhub-data*"), 1)
        self.assertEqual(script.count('names_include_a_hub "$'), 4)
        self.assertNotRegex(script, r"(?<!\|)\|\s*names_include_a_hub")  # a pipe, not ||
        code = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
        self.assertFalse([line for line in code if "--filter" in line])


class TruncatedDownloadTests(InstallShTestCase):
    """Point 3: a download cut off anywhere in the last line never runs main."""

    def run_text(self, text):
        proc = subprocess.run(
            [BASH], input=text.encode(), env=self.env, cwd=self.tmp, capture_output=True, timeout=30, check=False
        )
        return proc.stdout.decode() + proc.stderr.decode()

    def test_main_never_runs_from_a_cut_off_last_line(self):
        script = read(INSTALL_SH)
        self.assertTrue(script.endswith("\n"))
        # main is replaced by a marker that only prints and exits.
        self.assertEqual(script.count("\nmain() {\n"), 1)
        faked = script.replace("\nmain() {\n", "\nmain() {\n  echo MAIN_RAN\n  exit 0\n")
        last_line = faked[:-1].rsplit("\n", 1)[1]
        start = len(faked) - 1 - len(last_line)
        self.assertIn("main", last_line)
        self.assertIn("MAIN_RAN", self.run_text(faked))
        self.assertIn("MAIN_RAN", self.run_text(faked[:-1]))
        for cut in range(start, start + len(last_line)):
            with self.subTest(prefix=faked[start:cut]):
                self.assertNotIn("MAIN_RAN", self.run_text(faked[:cut]))
        self.assertFalse(os.path.exists(self.log_path))


class PortableSedTests(InstallShTestCase):
    """Point 4: the flow tests run where the host sed is BSD (macOS)."""

    def bsd_sed(self):
        import sys

        return self.write(os.path.join(self.state, "bsd-sed"), "#!%s\n%s" % (sys.executable, BSD_SED), 0o755)

    def test_bsd_sed_stand_in_rejects_the_gnu_call(self):
        target = self.write(os.path.join(self.tmp, "f.yml"), 'image: "x@sha256:<published-index-digest-hex>"\n')
        expr = 's|@sha256:<published-index-digest-hex>"|@sha256:abc"|'
        direct = subprocess.run([self.bsd_sed(), "-i", expr, target], capture_output=True, check=False)
        self.assertNotEqual(direct.returncode, 0)
        self.assertIn("invalid command code", direct.stderr.decode())
        env = dict(self.env, FAKE_HOST_SED=self.bsd_sed())
        wrapped = subprocess.run([os.path.join(self.bin_dir, "sed"), "-i", expr, target], env=env, check=False)
        self.assertEqual(wrapped.returncode, 0)
        self.assertEqual(read(target), 'image: "x@sha256:abc"\n')

    def test_happy_path_with_a_bsd_sed(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_HOST_SED=self.bsd_sed())
        self.assertEqual(run.code, 0, run.out + run.err)
        compose = read(os.path.join(self.home, "sproutwall", "docker-compose.preview.yml"))
        self.assertEqual(compose.count('@%s"' % DIGEST), 1)


class FinishTextTests(InstallShTestCase):
    """Point 5: the no-kiosk finish gives the guide's exact checks; the README
    says which answers the script accepts."""

    def test_no_kiosk_finish_has_the_guides_exact_checks(self):
        guide = read(GUIDE)
        section = guide[guide.index("- **Without the kiosk**") :]
        block = section[section.index("```bash") + len("```bash") : section.index("```", section.index("```bash") + 7)]
        lines = [line.strip() for line in block.strip().splitlines()]
        self.assertIn("curl -fsS --max-time 3 http://127.0.0.1:3847/api/health", lines)
        run = self.run_install(["5", "y", "y", ""])
        self.assertEqual(run.code, 0, run.out + run.err)
        finish = run.out[run.out.index("Now restart the device") :]
        for line in lines:
            self.assertIn("  " + line + "\n", finish)
        self.assertIn('must print "ok":true', finish)

    def test_readme_names_exactly_the_answers_the_script_accepts(self):
        accepted = re.search(r"(?m)^\s*(y \|[^)]*)\) return 0 ;;$", read(INSTALL_SH)).group(1)
        words = [word.strip() for word in accepted.split("|")]
        self.assertEqual(words, ["y", "Y", "yes", "Yes", "YES"])
        readme = read(os.path.join(ROOT, "README.md"))
        line = next(line for line in readme.splitlines() if "approve that plan" in line)
        sentence = line[line.index("Only ") :]
        self.assertEqual(sorted(set(re.findall(r"`([A-Za-z]+)`", sentence))), sorted(words))


def long_listing(path, first, lines=10000):
    """A matching name first, then thousands of others: far more than a pipe
    holds, so a reader that stops early would leave the writer failing."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(first + "\n")
        for number in range(lines):
            # Letters only, so no filler line can contain the fictional PIN.
            tag = "".join(chr(ord("a") + int(digit)) for digit in "%05d" % number)
            handle.write("unrelated-volume-%s-abcdefabcdef\n" % tag)
    return path


class PipeTimingTests(InstallShTestCase):
    """Round 2, point 1: a hub named first in a long listing is still found by
    every existing-hub check (under pipefail, grep -q on a pipe could flip it)."""

    def test_long_listing_first_check_stops(self):
        listing = long_listing(os.path.join(self.state, "volumes"), "sproutwall_familyhub-data")
        run = self.run_install(HAPPY_ANSWERS, FAKE_VOLUMES_FILE=listing)
        self.assert_stopped_before_changes(run)
        self.assertIn("#existing-install--update", run.err)

    def test_long_listing_sudo_step_0_check_stops(self):
        listing = long_listing(os.path.join(self.state, "volumes"), "family-hub_familyhub-data")
        run = self.run_install(["", "y", "y"], FAKE_DOCKER_DENIED_OUTSIDE_SG="1", FAKE_VOLUMES_FILE=listing)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("#existing-install--update", run.err)
        self.assertNotIn("No existing hub found", run.out)
        self.assertEqual(
            [line for line in run.log if line.startswith("sudo")],
            ExistingHubBeforeChangesTests.READ_ONLY,
        )

    def test_long_listing_post_tools_check_stops(self):
        self.docker_installed_by_the_plan()
        listing = long_listing(os.path.join(self.state, "containers"), "sproutwall-family-hub-1")
        run = self.run_install(HAPPY_ANSWERS, FAKE_CONTAINERS_FILE=listing)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("#existing-install--update", run.err)
        self.assertNotIn("git", run.commands())

    def test_long_ps_output_still_reads_healthy(self):
        extra = long_listing(os.path.join(self.state, "ps-extra"), "   (more status lines)")
        run = self.run_install(HAPPY_ANSWERS, FAKE_PS_EXTRA_FILE=extra)
        self.assertEqual(run.code, 0, run.err[-500:])

    def test_no_grep_reads_from_a_pipe(self):
        code = [line for line in read(INSTALL_SH).splitlines() if not line.lstrip().startswith("#")]
        self.assertFalse([line for line in code if re.search(r"(?<!\|)\|\s*grep\b", line)])


class DockerDataFolderTests(InstallShTestCase):
    """Round 2, point 2: no docker command, but Docker's data folder is left from
    an earlier install: a read-only `sudo ls` in step 0, before any change."""

    def docker_data(self, volumes):
        root = os.path.join(self.sysroot, "var", "lib", "docker")
        os.makedirs(root)
        if volumes is not None:
            for name in volumes:
                os.makedirs(os.path.join(root, "volumes", name))
        self.docker_installed_by_the_plan()
        return "sudo ls -1 %s/var/lib/docker/volumes" % self.sysroot

    def test_data_folder_with_a_hub_volume_stops_before_any_change(self):
        read_only = self.docker_data(["sproutwall_familyhub-data", "4f2a9c"])
        run = self.run_install(["", "y", "y"], FAKE_VOLUMES="sproutwall_familyhub-data\n")
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("changes nothing", run.err)
        self.assertIn("#existing-install--update", run.err)
        self.assertEqual([line for line in run.log if line.startswith("sudo")], [read_only])
        self.assertEqual(run.prompts, 2)
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        self.assertIn("sudo ls -1 /var/lib/docker/volumes", plan)

    def test_data_folder_without_a_hub_continues(self):
        read_only = self.docker_data(["4f2a9c", "backingFsBlockDev"])
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        sudo = [line for line in run.log if line.startswith("sudo")]
        self.assertEqual(sudo[:2], [read_only, "sudo apt update"])
        self.assertIn("No existing hub found.", run.out)

    def test_unreadable_volume_list_stops_with_nothing_changed(self):
        read_only = self.docker_data(None)
        run = self.run_install(["", "y", "y"])
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("could not be read", run.err)
        self.assertIn("Nothing was changed.", run.err)
        self.assertIn("#first-is-sproutwall-already-on-this-device", run.err)
        self.assertEqual([line for line in run.log if line.startswith("sudo")], [read_only])

    def test_no_data_folder_needs_no_check(self):
        self.docker_installed_by_the_plan()
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertFalse([line for line in run.log if line.startswith("sudo ls")])
        self.assertNotIn("Read-only, right after you approve", run.out)

    def test_hub_found_after_the_tools_does_not_claim_nothing_changed(self):
        self.docker_installed_by_the_plan()
        run = self.run_install(HAPPY_ANSWERS, FAKE_VOLUMES="sproutwall_familyhub-data\n")
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("The tools in the plan were installed", run.err)
        self.assertNotIn("changes nothing", run.err)
        self.assertNotIn("Nothing was changed", run.err)


class FirstStartTests(InstallShTestCase):
    """Round 2, point 3: wait for cloud-init's first-start setup before apt, and
    tell an apt lock apart, worded for what was really changed."""

    def cloud_init(self):
        self.write(
            os.path.join(self.bin_dir, "cloud-init"),
            "#!/bin/bash\nprintf 'cloud-init %s\\n' \"$*\" >>\"$FAKE_LOG\"\n"
            "[ \"$*\" = \"status --wait\" ] || exit 99\n"
            "if [ -n \"${FAKE_CLOUD_INIT_EXIT:-}\" ]; then echo 'status: error'; exit \"$FAKE_CLOUD_INIT_EXIT\"; fi\n"
            "echo 'status: done'\n",
            0o755,
        )

    def timeout_shim(self):
        """coreutils timeout: logs, then runs the command (or reports 124 itself)."""
        self.write(
            os.path.join(self.bin_dir, "timeout"),
            "#!/bin/bash\nprintf 'timeout %s\\n' \"$*\" >>\"$FAKE_LOG\"\n"
            "if [ -n \"${FAKE_TIMEOUT_EXPIRES:-}\" ]; then exit 124; fi\n"
            "shift\nexec \"$@\"\n",
            0o755,
        )

    def test_timeout_present_limits_the_wait_to_600_seconds(self):
        self.cloud_init()
        self.timeout_shim()
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        wait = run.index("timeout 600 cloud-init status --wait")
        self.assertEqual(run.log[wait + 1], "cloud-init status --wait")
        self.assertLess(wait, run.index("sudo apt update"))
        self.assertNotIn("continuing anyway", run.out)

    def test_timeout_absent_waits_plainly(self):
        self.cloud_init()
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertNotIn("timeout", run.commands())
        self.assertLess(run.index("cloud-init status --wait"), run.index("sudo apt update"))

    def test_wait_that_times_out_notes_it_and_apt_still_runs(self):
        self.cloud_init()
        self.timeout_shim()
        run = self.run_install(HAPPY_ANSWERS, FAKE_TIMEOUT_EXPIRES="1")
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("The Pi's first-start setup is still running after 10 minutes; continuing anyway.", run.out)
        self.assertLess(run.index("timeout 600 cloud-init status --wait"), run.index("sudo apt update"))

    def test_cloud_init_error_notes_it_and_apt_still_runs(self):
        for with_timeout in (True, False):
            with self.subTest(with_timeout=with_timeout):
                self.setUp()
                self.cloud_init()
                if with_timeout:
                    self.timeout_shim()
                run = self.run_install(HAPPY_ANSWERS, FAKE_CLOUD_INIT_EXIT="1")
                self.assertEqual(run.code, 0, run.out + run.err)
                self.assertIn("The Pi's first-start setup reported a problem of its own; continuing anyway.", run.out)
                self.assertLess(run.index("cloud-init status --wait"), run.index("sudo apt update"))

    def test_cloud_init_present_waits_before_apt(self):
        self.cloud_init()
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("Waiting for the Pi's first-start setup to finish", run.out)
        self.assertLess(run.index("cloud-init status --wait"), run.index("sudo apt update"))
        self.assertNotIn("sudo cloud-init status --wait", run.log)

    def test_cloud_init_absent_no_wait(self):
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertNotIn("cloud-init", run.commands())
        self.assertNotIn("first-start setup", run.out)

    def test_apt_lock_at_the_system_update_stops_plainly(self):
        run = self.run_install(HAPPY_ANSWERS, FAKE_APT_LOCKED="apt update")
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn(
            "Stopped: Another update is running. Wait a few minutes and run the same command again. "
            "Nothing that matters was changed.",
            run.err,
        )
        self.assertIn("Could not get lock", run.err)
        self.assertEqual([line for line in run.log if line.startswith("sudo")], ["sudo apt update"])

    def test_apt_lock_later_is_worded_for_what_already_ran(self):
        run = self.run_install(
            HAPPY_ANSWERS,
            FAKE_APT_LOCKED="apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
        )
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("Another update is running.", run.err)
        self.assertIn("The system update already ran", run.err)
        self.assertNotIn("Nothing that matters was changed", run.err)
        self.assertNotIn("git", run.commands())


if __name__ == "__main__":
    unittest.main()


SSH_ENV = {"SSH_CONNECTION": "192.168.1.20 52344 192.168.1.50 22"}
# portrait, plan, home network, SSH risk, setup done, taps, autologin, SSH off
SSH_ANSWERS = ["", "y", "y", "y", "", "", "y", "y"]


STOCK_SSHD_CONFIG = (
    "Include /etc/ssh/sshd_config.d/*.conf\n"
    "KbdInteractiveAuthentication no\n"
    "UsePAM yes\n"
    "#Match User anoncvs\n"
    "#\tX11Forwarding no\n"
)


class OverSshTests(InstallShTestCase):
    """The one command run from a laptop over SSH (HJ, 2026-11-20): tier B
    checks, a responsibility notice before any change, and SSH off at the end."""

    def setUp(self):
        super().setUp()
        self.ssh_config()

    def ssh_config(self, main=STOCK_SSHD_CONFIG, dropins=None):
        self.write(os.path.join(self.sysroot, "etc/ssh/sshd_config"), main)
        for name, text in (dropins if dropins is not None else {"50-cloud-init.conf": "PasswordAuthentication yes\n"}).items():
            self.write(os.path.join(self.sysroot, "etc/ssh/sshd_config.d", name), text)

    def sudo_lines(self, run):
        return [line for line in run.log if line.startswith("sudo")]

    def test_over_ssh_checks_as_tier_b_and_turns_ssh_off(self):
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(run.prompts, len(SSH_ANSWERS))
        self.assertIn("sproutwall doctor --json --phase running --tier B", run.log)
        self.assertIn("sproutwall doctor --json --phase configured --tier B", run.log)
        self.assertNotIn("sproutwall doctor --json --phase running --tier C", run.log)
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        self.assertIn("7. sudo raspi-config nonint do_ssh 1", plan)
        self.assertIn("Undo: sudo raspi-config nonint do_ssh 0", plan)
        # Every sudo command that ran was in the plan; turning SSH off is the very last one.
        unquoted = plan.replace("'", "")
        for line in run.log:
            if line.startswith("sudo"):
                self.assertIn(line, unquoted)
        self.assertEqual([line for line in run.log if line.startswith("sudo")][-1], "sudo raspi-config nonint do_ssh 1")
        self.assertIn("http://192.168.1.50:3847", run.out[run.out.index("Set up your household now") :])
        self.assertIn("this computer", run.out)
        self.assertIn("never in this Terminal", run.out)
        self.assertIn("On the device's own screen, tap the four corners", run.out)
        self.assertIn("SSH is off: systemctl is-active ssh.service ssh.socket prints inactive for both.", run.out)
        self.assertIn("doctor --phase final --tier B", run.out)
        self.assert_never_destructive(run)

    def test_questions_come_in_the_documented_order(self):
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        order = [
            "How does the screen hang?",
            "Do you approve this plan?",
            "Is all of this true for the network this device is on?",
            "Do you understand and accept this?",
            "Checking the SSH settings",
            "Set up your household now",
            "On the device's own screen, tap the four corners",
            "Run it now? sudo asks for your password.",
            "== Sproutwall is installed ==",
            "Turn SSH off now?",
        ]
        positions = [run.out.index(text) for text in order]
        self.assertEqual(positions, sorted(positions))
        # The responsibility notice comes before the first change.
        notice = run.out.index("SSH: YOUR RESPONSIBILITY")
        self.assertIn("is your responsibility", run.out[notice : notice + 600])
        self.assertLess(notice, run.out.index("== Installing the tools"))

    def test_declining_the_ssh_risk_changes_nothing(self):
        for answer in ("n", "", "ok", "sure"):
            with self.subTest(answer=answer):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(["", "y", "y", answer], **SSH_ENV)
                self.assertEqual(run.code, 0, run.out + run.err)
                self.assertNotIn("Stopped:", run.err)
                self.assertIn("nothing was changed", run.out)
                self.assertFalse([line for line in run.log if line.startswith("sudo")])
                self.assertFalse(os.path.exists(os.path.join(run.home, "sproutwall")))

    def test_declining_ssh_off_keeps_it_on_and_says_whose_responsibility(self):
        run = self.run_install(SSH_ANSWERS[:-1] + ["n"], **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertNotIn("sudo raspi-config nonint do_ssh 1", run.log)
        tail = run.out[run.out.index("Turn SSH off now?") :]
        self.assertIn("SSH stays on.", tail)
        self.assertIn("Keeping SSH on is your own responsibility", tail)
        self.assertIn("sudo raspi-config nonint do_ssh 1", tail)

    def test_ssh_off_is_confirmed_with_systemctl(self):
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        off = run.index("sudo raspi-config nonint do_ssh 1")
        self.assertEqual(run.log[off + 1 :], ["systemctl is-active ssh.service ssh.socket"])
        self.assertIn("SSH is off: systemctl is-active ssh.service ssh.socket prints inactive for both.", run.out)
        for states in ("socket-on", "no-systemd"):
            with self.subTest(states=states):
                os.remove(self.log_path)
                shutil.rmtree(self.home)
                os.mkdir(self.home)
                for name in os.listdir(self.state):
                    if name.endswith(".count"):
                        os.remove(os.path.join(self.state, name))
                run = self.run_install(SSH_ANSWERS, FAKE_SSH_STATES=states, **SSH_ENV)
                self.assertEqual(run.code, 0, run.out + run.err)
                tail = run.out[run.out.index("Turn SSH off now?") :]
                self.assertNotIn("SSH is off", tail)
                self.assertIn("SSH is not confirmed off", tail)
                self.assertIn("treat SSH as still on", tail)
                self.assertIn("Try again:  sudo raspi-config nonint do_ssh 1", tail)
                self.assertIn("Until it does, SSH is on", tail)
                self.assertNotIn("expected for that choice", tail)

    def test_finish_names_the_one_acceptable_ssh_unknown(self):
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        finish = run.out[run.out.index("== Sproutwall is installed ==") : run.out.index("== SSH (last question) ==")]
        self.assertIn("ssh_policy unknown (review_ssh)", finish)
        self.assertIn("only root can", finish)
        self.assertIn("inactive for both:  systemctl is-active ssh.service ssh.socket", finish)
        self.assertIn("Any other unknown, and any other fail, is still a stop.", finish)

    def test_ssh_off_that_fails_says_ssh_is_still_on(self):
        run = self.run_install(SSH_ANSWERS, FAKE_SUDO_FAIL="raspi-config nonint do_ssh 1", **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("Turning SSH off did not work, so SSH is still on.", run.out)
        self.assertIn("Try again:  sudo raspi-config nonint do_ssh 1", run.out)
        self.assertNotIn("Keeping SSH on is your own responsibility", run.out)

    def test_unreadable_ssh_settings_are_accepted_over_ssh_only(self):
        unknown_ssh = {"ssh_policy": ("unknown", "review_ssh")}
        self.doctor("running", **unknown_ssh, **TRUSTED_LAN)
        self.doctor("configured", **unknown_ssh, **TRUSTED_LAN)
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("This script checked it itself", run.out)
        self.assertNotIn("doctor: pass.", run.out)
        os.remove(self.log_path)
        shutil.rmtree(self.home)
        os.mkdir(self.home)
        for name in os.listdir(self.state):
            if name.endswith(".count"):
                os.remove(os.path.join(self.state, name))
        run = self.run_install(HAPPY_ANSWERS)  # not over SSH: the same unknown stops
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)
        self.assertIn("doctor found something that is not a clean result", run.err)

    def test_old_doctor_ssh_fail_is_accepted_after_the_sshd_check(self):
        # The pinned checkout's doctor predates password SSH for tier B and reports it as a fail.
        self.doctor("running", ssh_policy=("fail", "review_ssh"), **TRUSTED_LAN)
        self.doctor("configured", ssh_policy=("fail", "review_ssh"), **TRUSTED_LAN)
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("This script checked it itself", run.out)
        first_check = next(i for i, line in enumerate(run.log) if line.startswith("sudo sshd -T -C user=root,"))
        self.assertLess(first_check, run.index("sudo apt update"))
        self.assertIn("sudo sshd -T -C user=parent,host=192.168.1.20,addr=192.168.1.20,laddr=192.168.1.50,lport=22", run.log)

    def test_root_login_or_empty_passwords_stop_before_any_change(self):
        for settings in ("permitrootlogin yes\npasswordauthentication yes", "permitemptypasswords yes"):
            with self.subTest(settings=settings):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(SSH_ANSWERS, FAKE_SSHD_T=settings, **SSH_ENV)
                self.assertEqual(run.code, 1, run.out + run.err)
                self.assertEqual(run.err.count("Stopped:"), 1)
                self.assertIn("Nothing was changed", run.err)
                self.assertEqual(
                    self.sudo_lines(run),
                    ["sudo sshd -T -C user=root,host=192.168.1.20,addr=192.168.1.20,laddr=192.168.1.50,lport=22"],
                )

    def test_unreadable_sshd_settings_stop_before_any_change(self):
        run = self.run_install(SSH_ANSWERS, FAKE_SSHD_FAIL="1", **SSH_ENV)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("could not be read (sudo sshd -T -C)", run.err)
        self.assertEqual(len(self.sudo_lines(run)), 1)

    def test_match_rule_or_foreign_include_stops_before_any_change(self):
        cases = {
            "match in main": (STOCK_SSHD_CONFIG + "Match Address 10.0.0.0/8\n  PermitRootLogin yes\n", None),
            "match in drop-in": (STOCK_SSHD_CONFIG, {"60-x.conf": "  match user guest\n PermitEmptyPasswords yes\n"}),
            "match=value": (STOCK_SSHD_CONFIG, {"60-x.conf": "Match=User guest\n PermitEmptyPasswords yes\n"}),
            "match = value": (STOCK_SSHD_CONFIG + "\tMATCH = Address 10.0.0.0/8\n PermitRootLogin yes\n", None),
            "other include": ("Include /etc/ssh/extra/*.conf\n" + STOCK_SSHD_CONFIG, None),
            "include=value": ("Include=/etc/ssh/extra/*.conf\n" + STOCK_SSHD_CONFIG, None),
        }
        for label, (main, dropins) in cases.items():
            with self.subTest(label=label):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                shutil.rmtree(os.path.join(self.sysroot, "etc/ssh"), ignore_errors=True)
                self.ssh_config(main, dropins)
                run = self.run_install(SSH_ANSWERS, **SSH_ENV)
                self.assertEqual(run.code, 1, run.out + run.err)
                self.assertEqual(run.err.count("Stopped:"), 1)
                self.assertIn("Nothing was changed", run.err)
                self.assertFalse([line for line in self.sudo_lines(run) if "apt" in line])
                self.assertTrue(self.sudo_lines(run)[-1].startswith("sudo sh -c "))

    def test_commented_match_in_the_stock_config_is_fine(self):
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("no Match rules. OK.", run.out)

    def test_stock_include_written_with_equals_or_quotes_is_fine(self):
        for line in ('Include="/etc/ssh/sshd_config.d/*.conf"\n', "include = /etc/ssh/sshd_config.d/*.conf\n"):
            with self.subTest(line=line):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                shutil.rmtree(self.home)
                os.mkdir(self.home)
                for name in os.listdir(self.state):
                    if name.endswith(".count"):
                        os.remove(os.path.join(self.state, name))
                shutil.rmtree(os.path.join(self.sysroot, "etc/ssh"), ignore_errors=True)
                self.ssh_config(line + "UsePAM yes\n")
                run = self.run_install(SSH_ANSWERS, **SSH_ENV)
                self.assertEqual(run.code, 0, run.out + run.err)
                self.assertIn("no Match rules. OK.", run.out)

    def test_a_file_without_a_last_line_break_never_hides_the_next_files_match(self):
        # GATE-sw73: each file is read as its own lines.
        cases = {
            "drop-in ends in a comment": (
                STOCK_SSHD_CONFIG,
                {"10-a.conf": "PasswordAuthentication yes\n# no line break here", "20-b.conf": "Match User guest\n  PermitEmptyPasswords yes\n"},
            ),
            "main config ends in a comment": (
                STOCK_SSHD_CONFIG + "# no line break here",
                {"20-b.conf": "Match User guest\n  PermitEmptyPasswords yes\n"},
            ),
        }
        for label, (main, dropins) in cases.items():
            with self.subTest(label=label):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                shutil.rmtree(os.path.join(self.sysroot, "etc/ssh"), ignore_errors=True)
                self.ssh_config(main, dropins)
                run = self.run_install(SSH_ANSWERS, **SSH_ENV)
                self.assertEqual(run.code, 1, run.out + run.err)
                self.assertEqual(run.err.count("Stopped:"), 1)
                self.assertIn("have a Match rule", run.err)
                self.assertFalse([line for line in self.sudo_lines(run) if "apt" in line])

    def test_a_failed_drop_in_listing_is_never_an_empty_folder(self):
        # GATE-sw73: ls reports an I/O error for sshd_config.d; the read fails closed.
        root_bin = os.path.join(self.tmp, "rootbin")
        self.write(
            os.path.join(root_bin, "ls"),
            "#!/bin/sh\nfor last; do :; done\n"
            'case "$last" in */sshd_config.d) echo "ls: reading directory \'$last\': Input/output error" >&2; exit 2 ;; esac\n'
            'exec "%s" "$@"\n' % shutil.which("ls"),
            0o755,
        )
        run = self.run_install(SSH_ANSWERS, FAKE_ROOT_BIN=root_bin, **SSH_ENV)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)
        self.assertIn("The SSH settings files could not be read", run.err)
        self.assertFalse([line for line in self.sudo_lines(run) if "apt" in line])

    def test_drop_in_folder_that_is_not_a_folder_fails_closed(self):
        shutil.rmtree(os.path.join(self.sysroot, "etc/ssh"), ignore_errors=True)
        self.ssh_config(STOCK_SSHD_CONFIG, {})  # no drop-in folder
        self.write(os.path.join(self.sysroot, "etc/ssh/sshd_config.d"), "Match User guest\n")
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertIn("The SSH settings files could not be read", run.err)

    def test_drop_in_names_follow_sshds_glob(self):
        # No sshd_config.d at all is fine; dotfiles and other names are not read, as sshd's
        # *.conf glob skips them; a name ls has to escape stops the read.
        shutil.rmtree(os.path.join(self.sysroot, "etc/ssh"), ignore_errors=True)
        self.write(os.path.join(self.sysroot, "etc/ssh/sshd_config"), STOCK_SSHD_CONFIG)
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("no Match rules. OK.", run.out)
        for name, code in ((".90-hidden.conf", 0), ("notes.txt", 0), ("a b.conf", 1)):
            with self.subTest(name=name):
                os.remove(self.log_path)
                shutil.rmtree(self.home)
                os.mkdir(self.home)
                for state in os.listdir(self.state):
                    if state.endswith(".count"):
                        os.remove(os.path.join(self.state, state))
                shutil.rmtree(os.path.join(self.sysroot, "etc/ssh"), ignore_errors=True)
                self.ssh_config(STOCK_SSHD_CONFIG, {"10-ok.conf": "PasswordAuthentication yes\n", name: "Match User guest\n"})
                run = self.run_install(SSH_ANSWERS, **SSH_ENV)
                self.assertEqual(run.code, code, run.out + run.err)
                if code:
                    self.assertIn("The SSH settings files could not be read", run.err)

    def test_config_read_as_root_fails_closed(self):
        run = self.run_install(SSH_ANSWERS, FAKE_SUDO_SH_FAIL="1", **SSH_ENV)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)
        self.assertIn("could not be read", run.err)
        self.assertIn("Nothing was changed", run.err)
        self.assertFalse([line for line in self.sudo_lines(run) if "apt" in line])
        self.assertTrue(self.sudo_lines(run)[-1].startswith("sudo sh -c "))

    def test_docker_checks_over_ssh_wait_for_the_ssh_notice(self):
        root = os.path.join(self.sysroot, "var", "lib", "docker")
        os.makedirs(os.path.join(root, "volumes", "4f2a9c"))
        self.docker_installed_by_the_plan()
        run = self.run_install(["", "y", "y", "n"], **SSH_ENV)  # decline the SSH notice
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("nothing was changed", run.out)
        self.assertFalse(self.sudo_lines(run))
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        self.assertIn("0. Read-only, after the SSH question below", plan)
        os.remove(self.log_path)
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        sudo = self.sudo_lines(run)
        self.assertEqual(sudo[0], "sudo ls -1 %s/var/lib/docker/volumes" % self.sysroot)
        self.assertLess(run.out.index("Do you understand and accept this?"), run.out.index("Looking for an existing hub"))

    def test_old_doctor_ssh_fail_still_stops_without_ssh(self):
        self.doctor("running", ssh_policy=("fail", "review_ssh"), **TRUSTED_LAN)
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertNotIn("sshd -T", "\n".join(run.log))

    def test_another_fail_next_to_the_expected_ssh_result_does_not_blame_ssh(self):
        # Password SSH gives the expected ssh_policy fail; a separate check fails too.
        self.doctor("running", ssh_policy=("fail", "review_ssh"), bridge_bind=("fail", "restrict_ports"), **TRUSTED_LAN)
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)
        self.assertIn("not what stopped it", run.err)
        self.assertNotIn("leave SSH as it is", run.err)
        self.assertNotIn("public address, or it allows root login", run.err)

    def test_internet_ipv6_is_always_in_the_notice_the_person_accepts(self):
        # Always stated, so the consent covers an internet IPv6 address that appears only later.
        for hostnames in ("192.168.1.50 2001:db8::50 fe90::50", "192.168.1.50 fd12:3456::50 fe90::50"):
            with self.subTest(hostnames=hostnames):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(["", "y", "y", "n"], FAKE_HOSTNAME=hostnames, **SSH_ENV)
                notice = run.out[run.out.index("SSH: YOUR RESPONSIBILITY") : run.out.index("Do you understand and accept this?")]
                self.assertIn("internet (IPv6) address", notice)
                self.assertIn("SSH could be reachable from the internet", notice)

    def test_ipv4_address_rechecked_before_the_doctor_ssh_result_is_accepted(self):
        self.doctor("running", ssh_policy=("fail", "review_ssh"), **TRUSTED_LAN)
        # A public IPv4 address appears after the first preflight check.
        run = self.run_install(SSH_ANSWERS, FAKE_HOSTNAME_LATER="203.0.113.50 192.168.1.50", **SSH_ENV)
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)

    def test_public_address_at_the_doctor_check_does_not_say_to_run_the_command_again(self):
        # A public IPv4 address appears after the hub started (third hostname -I call).
        self.doctor("running", ssh_policy=("fail", "review_ssh"), **TRUSTED_LAN)
        run = self.run_install(
            SSH_ANSWERS, FAKE_HOSTNAME_LATER="203.0.113.50 192.168.1.50", FAKE_HOSTNAME_LATER_FROM="3", **SSH_ENV
        )
        self.assertEqual(run.code, 1, run.out + run.err)
        self.assertEqual(run.err.count("Stopped:"), 1)
        self.assertIn("doctor found SSH in a state this install can't accept", run.err)
        self.assertIn("don't run the one command again", run.err)
        self.assertNotIn("run the command in the device's own Terminal", run.err)

    def test_kiosk_check_over_ssh_names_the_no_keyboard_stand_in(self):
        run = self.run_install(SSH_ANSWERS, FAKE_KIOSK_CHECK_EXIT="1", **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertIn("The screen check needs attention", run.out)
        self.assertIn("With no keyboard and SSH off you can't run that check", run.out)
        self.assertIn("With no keyboard and SSH off, the screen check after the restart stands in for it.", run.out)

    def test_ipv6_only_lan_stops_in_preflight_over_ssh(self):
        # The session came over IPv6 and its interface has no IPv4 address.
        run = self.run_install(
            SSH_ANSWERS, FAKE_HOSTNAME="fd12:3456::50", FAKE_IP4="",
            SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22",
        )
        self.assert_stopped_before_changes(run)
        self.assertIn("no IPv4 home-network address", run.err)
        self.assertNotIn("<lan-ip>", run.out + run.err)

    def test_laptop_url_never_uses_a_docker_address_listed_first(self):
        # GATE-sw73: hostname -I can list docker0 (172.17.0.1) first; the laptop cannot reach it.
        cases = (
            ("over IPv4", {"SSH_CONNECTION": "192.168.1.20 52344 192.168.1.50 22"}),
            ("over IPv6", {"SSH_CONNECTION": "fd12:3456::7 52344 fd12:3456::50 22"}),
            ("SSH_CLIENT only", {"SSH_CLIENT": "192.168.1.20 52344 22"}),
        )
        for label, env in cases:
            with self.subTest(label=label):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                shutil.rmtree(self.home)
                os.mkdir(self.home)
                for name in os.listdir(self.state):
                    if name.endswith(".count"):
                        os.remove(os.path.join(self.state, name))
                run = self.run_install(SSH_ANSWERS, FAKE_HOSTNAME="172.17.0.1 192.168.1.50 fd12:3456::50", **env)
                self.assertEqual(run.code, 0, run.out + run.err)
                self.assertNotIn("172.17.0.1", run.out)
                household = run.out[run.out.index("Set up your household now") : run.out.index("You see")]
                self.assertIn("http://192.168.1.50:3847", household)
                finish = run.out[run.out.index("== Sproutwall is installed ==") :]
                self.assertIn("open http://192.168.1.50:3847", finish)

    def test_laptop_url_is_the_address_the_session_reached(self):
        run = self.run_install(
            SSH_ANSWERS, FAKE_HOSTNAME="172.17.0.1 10.0.0.9 192.168.1.50",
            SSH_CONNECTION="10.0.0.7 52344 10.0.0.9 22",
        )
        self.assertEqual(run.code, 0, run.out + run.err)
        household = run.out[run.out.index("Set up your household now") : run.out.index("You see")]
        self.assertIn("http://10.0.0.9:3847", household)

    def test_no_reachable_ipv4_stops_in_preflight(self):
        cases = {
            "session on docker0": dict(
                SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22",
                FAKE_IP6_ALL="4: docker0    inet6 fd12:3456::50/64 scope global \\       valid_lft forever preferred_lft forever",
            ),
            "session on a bridge": dict(SSH_CONNECTION="fe80::1c2b%br-3f2a 52344 fe80::50%br-3f2a 22"),
            "session interface with only a public IPv4": dict(
                SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22",
                FAKE_IP6_ALL="3: eth0    inet6 fd12:3456::50/64 scope global \\       valid_lft forever preferred_lft forever",
                FAKE_IP4="3: eth0    inet 203.0.113.50/24 brd 203.0.113.255 scope global eth0",
            ),
            "no IPv4 on the session's interface": dict(SSH_CONNECTION="fd12:3456::7 52344 fd12:3456::50 22", FAKE_IP4=""),
            "session to this device itself": dict(SSH_CONNECTION="127.0.0.1 52344 127.0.0.1 22"),
        }
        for label, env in cases.items():
            with self.subTest(label=label):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(SSH_ANSWERS, **env)
                self.assert_stopped_before_changes(run)
                self.assertIn("no IPv4 home-network address that your laptop reaches", run.err)

    def test_household_url_is_the_ipv4_address_only(self):
        run = self.run_install(SSH_ANSWERS, **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        household = run.out[run.out.index("Set up your household now") : run.out.index("You see")]
        self.assertIn("http://192.168.1.50:3847", household)
        self.assertNotIn(".local:3847", household)

    def test_session_from_outside_the_home_network_stops_in_preflight(self):
        for address in ("203.0.113.9", "100.101.102.103", "2001:db8::9", "fe9::1", "fec0::1"):
            with self.subTest(address=address):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(SSH_ANSWERS, SSH_CONNECTION="%s 52344 192.168.1.50 22" % address)
                self.assert_stopped_before_changes(run)
                self.assertIn("does not come from your home network", run.err)

    def test_global_ipv6_client_in_this_devices_prefix_is_accepted(self):
        ip6 = "2: wlan0    inet6 2001:db8:1:2::50/64 scope global dynamic mngtmpaddr \\       valid_lft 86000sec preferred_lft 14000sec"
        run = self.run_install(["", "n"], SSH_CONNECTION="2001:db8:1:2:aa::7 52344 2001:db8:1:2::50 22", FAKE_IP6=ip6)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertNotIn("does not come from your home network", run.err)
        self.assertIn("You did not approve the plan", run.out)
        for address in ("2001:db8:9::7", "2001:db8:1:3::7"):
            with self.subTest(address=address):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(["", "n"], SSH_CONNECTION="%s 52344 2001:db8:1:2::50 22" % address, FAKE_IP6=ip6)
                self.assert_stopped_before_changes(run)
                self.assertIn("does not come from your home network", run.err)

    def test_home_network_session_addresses_are_accepted(self):
        for env in (
            {"SSH_CLIENT": "10.0.0.7 52344 22"},
            {"SSH_CONNECTION": "172.20.1.4 52344 192.168.1.50 22"},
            {"SSH_CONNECTION": "fe80::1c2b%wlan0 52344 fe80::50%wlan0 22"},
            {"SSH_CONNECTION": "fd12:3456::7 52344 fd12:3456::50 22"},
            {"SSH_CONNECTION": "169.254.1.2 52344 169.254.1.50 22"},
            {"SSH_CONNECTION": "fe90::2 52344 fe90::50 22"},
            {"SSH_CONNECTION": "febf::2%eth0 52344 febf::50%eth0 22"},
        ):
            with self.subTest(env=env):
                if os.path.exists(self.log_path):
                    os.remove(self.log_path)
                run = self.run_install(["", "n"], **env)  # stop at the plan: nothing changes
                self.assertEqual(run.code, 0, run.out + run.err)
                self.assertNotIn("does not come from your home network", run.err)
                self.assertIn("You did not approve the plan", run.out)

    def test_ubuntu_over_ssh_uses_systemctl(self):
        self.ubuntu_pc()
        self.ssh_config()
        run = self.run_install(["y", "y", "y", "", "y"], **SSH_ENV)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(run.prompts, 5)
        plan = run.out[run.out.index("THE INSTALL PLAN") : run.out.index("Do you approve this plan?")]
        self.assertIn("6. sudo systemctl disable --now ssh.socket ssh.service", plan)
        self.assertEqual(
            [line for line in run.log if line.startswith("sudo")][-1], "sudo systemctl disable --now ssh.socket ssh.service"
        )

    def test_no_terminal_over_ssh_says_how_to_log_in(self):
        env = dict(self.env)
        env.update(SSH_ENV, SPROUTWALL_INSTALL_TEST_TTY=os.path.join(self.tmp, "no-such-tty"))
        proc = subprocess.run([BASH], input=read(INSTALL_SH).encode(), env=env, cwd=self.tmp,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("this SSH session has no terminal", proc.stderr.decode())


class NotOverSshTests(InstallShTestCase):
    def test_without_ssh_nothing_about_ssh_is_asked_or_run(self):
        run = self.run_install(HAPPY_ANSWERS)
        self.assertEqual(run.code, 0, run.out + run.err)
        self.assertEqual(run.prompts, len(HAPPY_ANSWERS))
        self.assertNotIn("SSH: YOUR RESPONSIBILITY", run.out)
        self.assertNotIn("Turn SSH off now?", run.out)
        self.assertFalse([line for line in run.log if "do_ssh" in line or "systemctl" in line])
        self.assertFalse([line for line in run.log if "--tier B" in line])
        self.assertIn("http://localhost:3847", run.out)
        self.assertIn("If a check finds a problem (for example SSH turned on)", run.out)
