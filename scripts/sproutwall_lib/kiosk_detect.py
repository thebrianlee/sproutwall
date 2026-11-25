"""Read-only detection for `setup kiosk`: platform, desktop session, Chromium,
the connected output, the touch input, autologin and desktop blanking.

Everything here only reads (through the injected System). Nothing it reads
is printed: callers turn results into fixed text and closed enum values.

An error is never read as "missing" or "off". Only ENOENT (or a process
that has just exited) means absent; any other failure, and any input that
does not parse exactly, raises CannotTell, and the caller stops without
editing anything.

The one supported path is Raspberry Pi OS 64-bit Desktop -> Wayland/labwc ->
exactly one connected HDMI or DSI output -> one touch input -> Chromium.

Sources for the Raspberry Pi OS desktop facts used below:
- labwc is the default compositor on every model:
  raspberrypi/documentation@97485d97, documentation/asciidoc/computers/
  configuration/localisation.adoc line 292.
- The session file LXDE-pi-labwc.desktop runs /usr/bin/labwc-pi, which ends
  with `exec /usr/bin/labwc -m` (--merge-config: the user's files in
  ~/.config/labwc augment /etc/xdg/labwc instead of replacing them), and
  /etc/xdg/labwc/autostart starts `/usr/bin/kanshi &`:
  raspberrypi-ui/raspberrypi-ui-mods@667217eb, usr/bin/labwc-pi,
  usr/share/wayland-sessions/LXDE-pi-labwc.desktop, etc/xdg/labwc/autostart.
- Desktop screen blanking under labwc is a `swayidle` line in
  ~/.config/labwc/autostart (Control Centre and raspi-config create and remove
  it): raspberrypi/documentation@97485d97, documentation/asciidoc/computers/
  configuration/audio-display.adoc lines 200 and 243-250; RPi-Distro/
  raspi-config@22cea75e (trixie branch), get_blanking() and do_blanking().
- Autologin is lightdm's autologin-user, set by
  `raspi-config nonint do_boot_behaviour B4` (B3 turns it off): RPi-Distro/
  raspi-config@22cea75e, get_autologin() and do_boot_behaviour().
- The output and touch configuration files: see kiosk_files.py.
"""

import fnmatch
import os
import re
from dataclasses import dataclass, field


class CannotTell(Exception):
    """A source could not be read or did not parse exactly. The argument is a
    fixed key naming the source; host text never goes into it."""


def _re(pattern):
    return re.compile(pattern, re.ASCII)


# --- platform ----------------------------------------------------------------

RPI_ISSUE = "/etc/rpi-issue"  # written into every Raspberry Pi OS image by pi-gen
DT_MODEL = "/proc/device-tree/model"
DPKG_ARCH_RE = _re(r"([a-z0-9]+)\n?")


def platform_supported(system):
    """True only on 64-bit Raspberry Pi OS on a Raspberry Pi; False when it is
    clearly something else. Raises CannotTell. The model is never printed."""
    if system.sysname() != "Linux" or system.machine() != "aarch64":
        return False
    result = system.run(["dpkg", "--print-architecture"])
    if result.missing:
        return False  # not Debian-based, so not Raspberry Pi OS
    if result.rc != 0:
        raise CannotTell("dpkg")
    match = DPKG_ARCH_RE.fullmatch(result.out)
    if not match:
        raise CannotTell("dpkg")
    if match.group(1) != "arm64":
        return False
    state = system.probe(RPI_ISSUE)
    if state == "error":
        raise CannotTell("rpi-issue")
    if state != "file":
        return False
    try:
        model = system.read_bytes(DT_MODEL)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise CannotTell("model") from error
    return model.startswith(b"Raspberry Pi ")


# --- desktop session -----------------------------------------------------------

# Compositors and X servers that mean "a desktop, but not the supported one".
OTHER_DESKTOPS = ("wayfire", "Xorg", "X", "sway", "weston", "gnome-shell", "kwin_wayland", "kwin_x11", "openbox", "mutter")
WAYLAND_SOCKET_RE = _re(r"wayland-[0-9]{1,3}")
RUNTIME_DIR_RE = _re(r"/[A-Za-z0-9._/-]{1,200}")
PID_TEXT_RE = _re(r"[1-9][0-9]{0,9}")


@dataclass
class Session:
    """The kiosk user's labwc session, or why there is none.

    reason: "ok", "root", "no_desktop" (nothing graphical for this user, e.g. a
    Lite image or nobody logged in), "other_desktop" (X11, Wayfire, ...),
    "no_merge" (labwc without --merge-config: our files would replace the
    system defaults), "no_kanshi" (no output configuration daemon in this
    session) or "no_socket" (the session's Wayland socket is not there).
    """

    reason: str  # also "config_path": a config folder or file option, or XDG_CONFIG_HOME, moves the config away from ~/.config
    labwc_pid: int = 0
    kanshi_pids: list = field(default_factory=list)
    env: dict = field(default_factory=dict)  # WAYLAND_DISPLAY and XDG_RUNTIME_DIR only

    @property
    def ok(self):
        return self.reason == "ok"


def own_processes(system):
    try:
        processes = system.processes()
    except OSError as error:
        raise CannotTell("processes") from error
    uid = system.uid()
    return [p for p in processes if p[1] == uid]


# Options that make labwc or kanshi read another configuration than
# ~/.config/labwc and ~/.config/kanshi/config (labwc(1): -c/--config,
# -C/--config-dir; kanshi(1): -c/--config).
LABWC_CONFIG_OPTIONS = ("-c", "-C", "--config", "--config-dir")
KANSHI_CONFIG_OPTIONS = ("-c", "--config")


def _overrides_config(argv, options):
    """True if argv (after the program) has one of options, as a separate
    word, as --option=value, or inside a cluster of short options (-mC)."""
    short = [o[1] for o in options if len(o) == 2]
    for arg in argv[1:]:
        if arg in options or any(arg.startswith(o + "=") for o in options if o.startswith("--")):
            return True
        if arg.startswith("-") and not arg.startswith("--") and any(c in arg[1:] for c in short):
            return True
    return False


DEFAULT_CONFIG_DIRS = "/etc/xdg"


def _config_env_ok(env, home):
    """The session environment uses this home folder and the default config
    places: XDG_CONFIG_HOME unset or exactly ~/.config, and XDG_CONFIG_DIRS
    unset, empty (the XDG default) or exactly /etc/xdg, where this tool
    reads the system labwc files."""
    session_home = env.get("HOME")
    if not isinstance(session_home, str) or os.path.normpath(session_home) != os.path.normpath(home):
        return False
    config = env.get("XDG_CONFIG_HOME")
    if config is not None and os.path.normpath(config) != os.path.join(os.path.normpath(home), ".config"):
        return False
    dirs = env.get("XDG_CONFIG_DIRS")
    return dirs is None or dirs == "" or (":" not in dirs and os.path.normpath(dirs) == DEFAULT_CONFIG_DIRS)


def find_session(system):
    """The labwc session of the user running this, found from the process table.

    Works from the desktop's own terminal and from an SSH login of the same
    user: the Wayland socket is taken from the environment of the kanshi that
    labwc started (it carries LABWC_PID and WAYLAND_DISPLAY), not from the
    caller's environment. labwc and kanshi must use the default config
    places (~/.config, no config options, no other XDG_CONFIG_HOME) and this
    home folder, or the files this tool writes would not be read: that is
    "config_path". Raises CannotTell, also when an environment cannot be read.
    """
    if system.euid() == 0:
        return Session("root")
    own = own_processes(system)
    labwc = [p for p in own if p[2] == "labwc"]
    if not labwc:
        if any(p[2] in OTHER_DESKTOPS for p in own):
            return Session("other_desktop")
        return Session("no_desktop")
    if len(labwc) != 1:
        return Session("other_desktop")  # nested or several labwc: not the plain desktop
    labwc_pid, _, _, labwc_argv = labwc[0]
    if _overrides_config(labwc_argv, LABWC_CONFIG_OPTIONS):
        return Session("config_path")
    if not _overrides_config(labwc_argv, ("-m", "--merge-config")):  # -m, also inside -dm
        return Session("no_merge")
    home = system.home()
    try:
        labwc_env = system.process_environ(labwc_pid)
    except OSError as error:  # gone or unreadable: either way it cannot be told
        raise CannotTell("labwc-environment") from error
    if not _config_env_ok(labwc_env, home):
        return Session("config_path")
    kanshi = [(p[0], p[3]) for p in own if p[2] == "kanshi"]
    session_kanshi = []
    env = None
    for pid, argv in kanshi:
        try:
            penv = system.process_environ(pid)
        except ProcessLookupError:
            continue  # exited meanwhile
        except OSError as error:
            raise CannotTell("kanshi-environment") from error
        if penv.get("LABWC_PID") != str(labwc_pid):
            continue
        if _overrides_config(argv, KANSHI_CONFIG_OPTIONS) or not _config_env_ok(penv, home):
            return Session("config_path")
        session_kanshi.append(pid)
        env = env or penv
    if not session_kanshi:
        return Session("no_kanshi")
    display = env.get("WAYLAND_DISPLAY")
    runtime = env.get("XDG_RUNTIME_DIR")
    if not isinstance(display, str) or not WAYLAND_SOCKET_RE.fullmatch(display):
        raise CannotTell("wayland-display")
    if not isinstance(runtime, str) or not RUNTIME_DIR_RE.fullmatch(runtime) or os.path.normpath(runtime) != runtime:
        raise CannotTell("runtime-dir")
    state = system.probe(os.path.join(runtime, display))
    if state == "error":
        raise CannotTell("wayland-socket")
    if state != "file":
        return Session("no_socket")
    return Session(
        "ok",
        labwc_pid=labwc_pid,
        kanshi_pids=session_kanshi,
        env={"WAYLAND_DISPLAY": display, "XDG_RUNTIME_DIR": runtime},
    )


# --- Chromium ------------------------------------------------------------------

# Current Raspberry Pi OS calls it chromium; older Bookworm images
# chromium-browser. kiosk_launcher.py searches the same list.
CHROMIUM_CANDIDATES = ("/usr/bin/chromium", "/usr/bin/chromium-browser")


def find_chromium(system):
    """The first installed candidate, or None. Raises CannotTell."""
    for path in CHROMIUM_CANDIDATES:
        state = system.probe(path)
        if state == "error":
            raise CannotTell("chromium")
        if state == "file" and system.is_executable(path):
            return path
    return None


# --- outputs (wlr-randr) ------------------------------------------------------------

# The connectors this tool configures: HDMI (HDMI-A-1, HDMI-A-2) and DSI
# (DSI-1, DSI-2), as named by the kernel and wlroots
# (raspberrypi/documentation@97485d97, computers/configuration/
# audio-display.adoc, "Your display port can be any of the following").
CONNECTOR_RE = _re(r"(?:HDMI-A|DSI)-[1-9]")
OUTPUT_NAME_RE = _re(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}")
TRANSFORMS = ("normal", "90", "180", "270", "flipped", "flipped-90", "flipped-180", "flipped-270")


def connector_kind(name):
    """"hdmi" or "dsi" (an enum, printable) for a supported connector name."""
    if not CONNECTOR_RE.fullmatch(name):
        raise ValueError("connector")
    return "hdmi" if name.startswith("HDMI-") else "dsi"


@dataclass
class Mode:
    width: int
    height: int
    preferred: bool = False
    current: bool = False


@dataclass
class Output:
    name: str
    enabled: bool
    modes: list = field(default_factory=list)
    transform: object = None  # one of TRANSFORMS, or None for a switched-off output

    def native_mode(self):
        """The panel's own mode: the one preferred mode, else the one current
        mode. Raises CannotTell when neither is known for certain (no
        guessing a landscape panel)."""
        for flag in ("preferred", "current"):
            found = [m for m in self.modes if getattr(m, flag)]
            if len(found) == 1:
                return found[0]
            if len(found) > 1:
                raise CannotTell("modes")
        raise CannotTell("modes")


class OutputsUnreadable(Exception):
    """wlr-randr is not installed (key "missing")."""


def _size(value):
    if type(value) is not int or not 0 < value < 100000:
        raise ValueError("size")
    return value


def _flag(item, key):
    value = item.get(key)  # required: a missing flag is not "False"
    if type(value) is not bool:
        raise ValueError("flag")
    return value


def parse_wlr_randr_json(text):
    """`wlr-randr --json` (wlr-randr 0.4+): a list of output objects.

    Reads name, enabled, modes[width, height, preferred, current] and
    transform, all required; anything that is not exactly that shape raises
    ValueError.
    The field names follow wlr-randr 0.4's JSON output. A ValueError here
    makes the caller use the plain-text output instead.
    """
    from .kiosk import loads_strict

    data = loads_strict(text)  # duplicate keys or NaN: AmbiguousJSON (a ValueError)
    if not isinstance(data, list):
        raise ValueError("not a list")
    outputs = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("output")
        name = item.get("name")
        if not isinstance(name, str) or not OUTPUT_NAME_RE.fullmatch(name):
            raise ValueError("name")
        enabled = item.get("enabled")
        if type(enabled) is not bool:
            raise ValueError("enabled")
        modes_data = item.get("modes")  # required: missing is not "no modes"
        if not isinstance(modes_data, list):
            raise ValueError("modes")
        modes = []
        for mode in modes_data:
            if not isinstance(mode, dict):
                raise ValueError("mode")
            modes.append(Mode(_size(mode.get("width")), _size(mode.get("height")), _flag(mode, "preferred"), _flag(mode, "current")))
        transform = None
        if enabled:
            transform = item.get("transform")
            if transform not in TRANSFORMS:
                raise ValueError("transform")
        outputs.append(Output(name=name, enabled=enabled, modes=modes, transform=transform))
    return outputs


HEADER_RE = _re(r'([A-Za-z0-9][A-Za-z0-9_.-]{0,31}) "[^\n]*"')
PROPERTY_RE = _re(r"  ([A-Z][A-Za-z ]{0,30}):(?: ([^\n]*))?")
MODE_LINE_RE = _re(r"    ([1-9][0-9]{0,4})x([1-9][0-9]{0,4}) px(?:, [0-9]{1,4}\.[0-9]{1,6} Hz)?(?: \((preferred|current|preferred, current)\))?")


def parse_wlr_randr_text(text):
    """Plain `wlr-randr`: an unindented `NAME "description"` line per output,
    two-space property lines (Enabled, Transform, ...) and four-space mode
    lines `WxH px, R Hz (preferred, current)` (wlr-randr main.c print_state).
    Every line must have one of these shapes; anything else raises ValueError."""
    outputs = []
    current = None
    in_modes = False
    seen = set()
    complete = []
    for line in text.split("\n"):
        if line == "":
            continue
        header = HEADER_RE.fullmatch(line)
        if header:
            if current is not None:
                complete.append("Enabled" in seen)
            current = Output(name=header.group(1), enabled=False)
            outputs.append(current)
            in_modes = False
            seen = set()
            continue
        if current is None:
            raise ValueError("line before output")
        mode = MODE_LINE_RE.fullmatch(line)
        if mode:
            if not in_modes:
                raise ValueError("mode outside Modes")
            flags = mode.group(3) or ""
            current.modes.append(Mode(int(mode.group(1)), int(mode.group(2)), "preferred" in flags, "current" in flags))
            continue
        prop = PROPERTY_RE.fullmatch(line)
        if not prop:
            raise ValueError("line shape")
        key, value = prop.group(1), prop.group(2)
        if key in seen:
            raise ValueError("repeated property")
        seen.add(key)
        in_modes = key == "Modes"
        if key == "Enabled":
            if value not in ("yes", "no"):
                raise ValueError("enabled")
            current.enabled = value == "yes"
        elif key == "Transform":
            if value not in TRANSFORMS:
                raise ValueError("transform")
            current.transform = value
        elif key == "Modes" and value not in (None, ""):
            raise ValueError("modes")
    if current is not None:
        complete.append("Enabled" in seen)
    for output, has_enabled in zip(outputs, complete):
        if not has_enabled or (output.enabled and output.transform is None):
            raise ValueError("incomplete output")
        if not output.enabled:
            output.transform = None
    return outputs


def read_outputs(system, session):
    """Every output the compositor reports, from `wlr-randr --json`, else the
    plain output of `wlr-randr`. Raises OutputsUnreadable("missing") when
    wlr-randr is not installed and CannotTell when it fails or its answer
    does not parse."""
    from .kiosk import AmbiguousJSON
    from .system import command_env

    env = command_env()
    env.update(session.env)
    result = system.run(["wlr-randr", "--json"], timeout=10.0, env=env)
    if result.missing:
        raise OutputsUnreadable("missing")
    if result.rc == 0:
        try:
            return parse_wlr_randr_json(result.out)
        except AmbiguousJSON as error:
            raise CannotTell("wlr-randr") from error  # a duplicate key: never guessed
        except (ValueError, TypeError):
            pass  # an older wlr-randr without --json, or an unexpected shape
    result = system.run(["wlr-randr"], timeout=10.0, env=env)
    if result.rc != 0:
        raise CannotTell("wlr-randr")
    try:
        return parse_wlr_randr_text(result.out)
    except (ValueError, TypeError) as error:
        raise CannotTell("wlr-randr") from error


def classify_outputs(outputs):
    """("one", output) | ("none", None) | ("several", None) | ("unsupported_connector", None).

    Every reported output counts, including virtual ones (NOOP-1 for a
    headless VNC desktop): kanshi applies a profile only when the set of
    connected outputs matches it exactly, so a second output of any kind
    would keep the kiosk profile from applying.
    """
    if not outputs:
        return "none", None
    if len(outputs) > 1:
        return "several", None
    output = outputs[0]
    if not CONNECTOR_RE.fullmatch(output.name):
        return "unsupported_connector", None
    if not output.enabled:
        return "none", None  # connected but switched off: "enable the panel"
    return "one", output


# Orientation -> wlroots output transform. The spec's mapping (portrait = 90,
# its opposite 270) assumes a panel whose own mode is landscape. A panel
# whose own mode is portrait (taller than wide) is already portrait at
# "normal", so its table is turned by 90 degrees.
ORIENTATIONS = ("portrait", "portrait-flipped", "landscape", "landscape-flipped")
DEFAULT_ORIENTATION = "portrait"
KIOSK_TRANSFORMS = ("normal", "90", "180", "270")
TRANSFORM_LANDSCAPE_PANEL = {"portrait": "90", "portrait-flipped": "270", "landscape": "normal", "landscape-flipped": "180"}
TRANSFORM_PORTRAIT_PANEL = {"portrait": "normal", "portrait-flipped": "180", "landscape": "90", "landscape-flipped": "270"}


def transform_for(orientation, output):
    """Raises CannotTell when the panel's own mode is not known for certain."""
    mode = output.native_mode()
    table = TRANSFORM_PORTRAIT_PANEL if mode.height > mode.width else TRANSFORM_LANDSCAPE_PANEL
    return table[orientation]


# --- touch input (/proc/bus/input/devices) --------------------------------------------

INPUT_DEVICES = "/proc/bus/input/devices"
BITS_PER_LONG = 64  # the kernel prints unsigned long words; only aarch64 is supported

EV_KEY, EV_ABS, EV_REL = 0x01, 0x03, 0x02
ABS_X, ABS_Y, ABS_Z = 0x00, 0x01, 0x02
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 0x2F, 0x35, 0x36
BTN_MOUSE, BTN_JOYSTICK = 0x110, 0x120
BTN_TOOL_PEN, BTN_TOOL_FINGER, BTN_TOUCH, BTN_STYLUS = 0x140, 0x145, 0x14A, 0x14B
INPUT_PROP_DIRECT, INPUT_PROP_POINTING_STICK, INPUT_PROP_ACCELEROMETER = 0x01, 0x05, 0x06

# The kernel's input_devices_seq_show() lines (drivers/input/input.c).
DEVICE_LINE_RES = {
    "I": _re(r"I: Bus=[0-9a-f]{4} Vendor=[0-9a-f]{4} Product=[0-9a-f]{4} Version=[0-9a-f]{4}"),
    "N": _re(r'N: Name="([^\x00-\x1f\x7f]*)"'),
    "P": _re(r"P: Phys=[^\x00-\x1f\x7f]*"),
    "S": _re(r"S: Sysfs=[^\x00-\x1f\x7f]*"),
    "U": _re(r"U: Uniq=[^\x00-\x1f\x7f]*"),
    "H": _re(r"H: Handlers=((?:[A-Za-z0-9_-]+ ?)*)"),
    "B": _re(r"B: (PROP|EV|KEY|REL|ABS|MSC|LED|SND|FF|SW)=([0-9a-f]{1,16}(?: [0-9a-f]{1,16})*)"),
}
DEVICE_NAME_RE = _re(r"[^\x00-\x1f\x7f]{1,128}")
EVENT_HANDLER_RE = _re(r"event[0-9]{1,4}")


def parse_bitmap(text):
    """A /proc/bus/input/devices bitmap ("400 0 0 0 0 0") as one integer."""
    value = 0
    for word in text.split(" "):
        value = (value << BITS_PER_LONG) | int(word, 16)
    return value


def _bit(bitmap, number):
    return bool((bitmap >> number) & 1)


# Which event-type bit makes the kernel print which bitmap line
# (input_devices_seq_show(): KEY only with EV_KEY, ABS only with EV_ABS, ...).
BITMAP_EV_BITS = {"KEY": 0x01, "REL": 0x02, "ABS": 0x03, "MSC": 0x04, "SW": 0x05, "LED": 0x11, "SND": 0x12, "FF": 0x15}


def _check_record(block):
    """Every line the kernel always prints (I, N, P, S, U, H, PROP, EV), and
    each type bitmap exactly when its EV bit is set. Else ValueError."""
    for key in ("I", "N", "P", "S", "U", "H", "PROP", "EV"):
        if key not in block:
            raise ValueError("incomplete record")
    for key, bit in BITMAP_EV_BITS.items():
        if (key in block) != _bit(block["EV"], bit):
            raise ValueError("bitmap does not match EV")


def parse_input_devices(text):
    """[{name, handlers, PROP, EV, KEY, ABS, ...}] from /proc/bus/input/devices.

    Every line must have one of the kernel's shapes, no line may repeat in a
    record, and every record must be complete (_check_record); anything else
    raises ValueError: an incomplete record is never read as "no
    capabilities"."""
    devices = []
    block = {}
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line in lines + [""]:
        if line == "":
            if block:
                _check_record(block)
                devices.append(block)
            block = {}
            continue
        regex = DEVICE_LINE_RES.get(line[:1])
        match = regex.fullmatch(line) if regex is not None else None
        if not match:
            raise ValueError("line shape")
        kind = line[:1]
        key = match.group(1) if kind == "B" else kind
        if key in block:
            raise ValueError("repeated line")
        if kind == "N":
            block["name"] = match.group(1)
        elif kind == "H":
            block["handlers"] = match.group(1).split()
        elif kind == "B":
            block[key] = parse_bitmap(match.group(2))
        block[key] = block.get(key, True)
    return devices


def is_touchscreen(device):
    """udev's input_id rule for ID_INPUT_TOUCHSCREEN, which is what libinput
    (and so labwc) treats as a touch device: absolute X/Y (or multitouch)
    axes, BTN_TOUCH or INPUT_PROP_DIRECT, and not a pen tablet, a touchpad,
    an absolute mouse or an accelerometer (systemd udev-builtin-input_id.c,
    test_pointers)."""
    if not any(EVENT_HANDLER_RE.fullmatch(h) for h in device.get("handlers", [])):
        return False
    ev, key, abs_, props = device.get("EV", 0), device.get("KEY", 0), device.get("ABS", 0), device.get("PROP", 0)
    if not _bit(ev, EV_ABS):
        return False
    has_keys = _bit(ev, EV_KEY)
    has_abs = _bit(abs_, ABS_X) and _bit(abs_, ABS_Y)
    if _bit(props, INPUT_PROP_ACCELEROMETER) or (not has_keys and has_abs and _bit(abs_, ABS_Z)):
        return False
    if _bit(props, INPUT_PROP_POINTING_STICK):
        return False
    has_mt = _bit(abs_, ABS_MT_POSITION_X) and _bit(abs_, ABS_MT_POSITION_Y)
    if has_mt and _bit(abs_, ABS_MT_SLOT) and _bit(abs_, ABS_MT_SLOT - 1):
        has_mt = False  # the device claims every axis: not real multitouch
    pen = _bit(key, BTN_STYLUS) or _bit(key, BTN_TOOL_PEN)
    finger_no_pen = _bit(key, BTN_TOOL_FINGER) and not _bit(key, BTN_TOOL_PEN)
    direct = _bit(props, INPUT_PROP_DIRECT)
    touch = _bit(key, BTN_TOUCH)
    mouse_button = any(_bit(key, b) for b in range(BTN_MOUSE, BTN_JOYSTICK))
    if has_abs:
        if pen or (finger_no_pen and not direct) or mouse_button:
            return False
        if touch or direct:
            return True
    if has_mt and not pen and not (finger_no_pen and not direct) and (touch or direct):
        return True
    return False


def find_touch(system):
    """("one", name) | ("none", None) | ("several", None). Raises CannotTell.

    Every touch device counts, even two with the same name: labwc maps by
    name, so two same-named devices could be two panels, and that is
    ambiguous. A missing file (ENOENT: no input devices at all) is "none";
    any other failure, a file that does not parse, or a touch name that
    cannot be written safely is CannotTell.
    """
    try:
        raw = system.read_bytes(INPUT_DEVICES)
    except FileNotFoundError:
        return "none", None
    except OSError as error:
        raise CannotTell("input-devices") from error
    try:
        devices = parse_input_devices(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise CannotTell("input-devices") from error
    names = [device["name"] for device in devices if is_touchscreen(device)]
    if not names:
        return "none", None
    if len(names) > 1:
        return "several", None
    if not DEVICE_NAME_RE.fullmatch(names[0]):
        raise CannotTell("touch-name")
    return "one", names[0]


# --- autologin (lightdm) -------------------------------------------------------------

LIGHTDM_CONF = "/etc/lightdm/lightdm.conf"
LIGHTDM_CONF_D = "/etc/lightdm/lightdm.conf.d"
# lightdm's load order (later files override earlier ones): the packaged
# configuration folders, then /etc/lightdm/lightdm.conf.d, then
# /etc/lightdm/lightdm.conf (lightdm src/lightdm.c, config_load_from_standard_locations).
LIGHTDM_CONF_DIRS = (
    "/usr/share/lightdm/lightdm.conf.d",
    "/usr/local/share/lightdm/lightdm.conf.d",
    "/etc/xdg/lightdm/lightdm.conf.d",
    LIGHTDM_CONF_D,
)
AUTOLOGIN_ON = ["sudo", "raspi-config", "nonint", "do_boot_behaviour", "B4"]
AUTOLOGIN_OFF = ["sudo", "raspi-config", "nonint", "do_boot_behaviour", "B3"]
CONF_NAME_RE = _re(r"[A-Za-z0-9_.-]{1,64}\.conf")
INI_SECTION_RE = _re(r"\[([^\[\]\x00-\x1f]{1,64})\]")
INI_KEY_RE = _re(r"[A-Za-z0-9_.-]{1,64}")
# The sections whose autologin-user applies to the Pi's seat, as lightdm
# reads them (canonical/lightdm@bcd0e902: common/configuration.c moves keys
# of the old [SeatDefaults] into [Seat:*]; src/lightdm.c get_config_sections
# takes [Seat:*] first, then every [Seat:<pattern>] matching the seat name).
SEAT_NAME = "seat0"


def parse_lightdm_ini(text):
    """{section: {key: value}} for one lightdm (GKeyFile-style) file.
    Raises ValueError on any line that is not blank, a comment, a [section]
    header or key=value inside a section."""
    sections = {}
    current = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        header = INI_SECTION_RE.fullmatch(stripped)
        if header:
            current = sections.setdefault(header.group(1), {})
            continue
        key, sep, value = stripped.partition("=")
        if not sep or current is None or not INI_KEY_RE.fullmatch(key.strip()):
            raise ValueError("malformed line")
        current[key.strip()] = value.strip()
    return sections


def autologin_state(system):
    """"on" (this user), "other_user", "off" or "unknown". The name is never printed.

    Informational only: the tool never edits lightdm. "unknown" when a file
    or a folder cannot be read, decoded or parsed (never "off")."""
    files = []
    for folder in LIGHTDM_CONF_DIRS:
        try:
            names = system.listdir(folder)
        except FileNotFoundError:
            continue
        except OSError:
            return "unknown"
        files += [os.path.join(folder, n) for n in sorted(names) if CONF_NAME_RE.fullmatch(n)]
    files.append(LIGHTDM_CONF)
    merged = {}  # section -> {key: value}, in the order sections first appear
    readable = False
    for path in files:
        try:
            sections = parse_lightdm_ini(system.read_bytes(path).decode("utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, UnicodeDecodeError, ValueError):
            return "unknown"
        readable = True
        for name, keys in sections.items():
            merged.setdefault("Seat:*" if name == "SeatDefaults" else name, {}).update(keys)
    if not readable:
        return "unknown"
    value = merged.get("Seat:*", {}).get("autologin-user")
    for name, keys in merged.items():
        if name.startswith("Seat:") and name != "Seat:*" and fnmatch.fnmatchcase(SEAT_NAME, name[len("Seat:") :]):
            value = keys.get("autologin-user", value)
    if not value:
        return "off"
    try:
        return "on" if value == system.username() else "other_user"
    except (KeyError, OSError):
        return "unknown"


# --- desktop blanking (swayidle in labwc autostart) ----------------------------------------

SYSTEM_AUTOSTART = "/etc/xdg/labwc/autostart"
SYSTEM_RC_XML = "/etc/xdg/labwc/rc.xml"
SWAYIDLE_RE = _re(r"(?:^|[\s/;&|])swayidle(?:\s|$)")


def is_blanking_line(line):
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#") and bool(SWAYIDLE_RE.search(stripped))


def has_blanking(text):
    return any(is_blanking_line(line) for line in text.splitlines())


def system_blanking(system):
    """True/False: a swayidle line in the system-wide labwc autostart, which
    this tool cannot change. ENOENT is False; any other failure CannotTell."""
    try:
        text = system.read_bytes(SYSTEM_AUTOSTART).decode("utf-8")
    except FileNotFoundError:
        return False
    except (OSError, UnicodeDecodeError) as error:
        raise CannotTell("system-autostart") from error
    return has_blanking(text)


def system_rc_xml(system):
    """The system rc.xml bytes, or None when absent. Raises CannotTell."""
    try:
        return system.read_bytes(SYSTEM_RC_XML)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise CannotTell("system-rc-xml") from error


# --- manual kiosk lines (docs/raspberry-pi.md before this tool) ------------------------------

CHROMIUM_NAMES = ("chromium", "chromium-browser")


def launches_chromium(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    for token in re.split(r"[\s;&|]+", stripped):
        if os.path.basename(token.strip("\"'")) in CHROMIUM_NAMES:
            return True
    return False
