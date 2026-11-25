"""`sproutwall setup kiosk`: one output, with touch mapped to it.

  setup kiosk [--orientation portrait|portrait-flipped|landscape|landscape-flipped]
  setup kiosk --check [--json]
  setup kiosk --off
  setup kiosk --undo

Runs as the desktop user, never as root, and never runs sudo. The one
privileged step, desktop autologin, is printed for the person to run
themselves (see docs/install-cli.md for why).

Output is fixed text keyed by enum values only. Paths, user names, the
touch device name and the connector name are written to config files but
never printed; the screen is named only by its kind (HDMI or DSI).

An error is never treated as "missing" or "off": a source that cannot be
read or does not parse exactly stops the run before any edit (exit 6), and
`--check` reports it as unknown.
"""

import json
import os
import signal

from . import kiosk, kiosk_detect as det, kiosk_files as kf

EXIT_OK = 0
EXIT_ATTENTION = 1
EXIT_USAGE = 2  # also an unexpected error, as everywhere in scripts/sproutwall
EXIT_UNSUPPORTED = 3
EXIT_NOT_READY = 4
EXIT_CHANGED = 5
EXIT_CANNOT_TELL = 6

MANUAL = "Set up the screen by hand instead: docs/raspberry-pi.md, section Kiosk."
UNCHANGED = "Nothing was changed."


def _lower_first(text):
    return text[0].lower() + text[1:]


REFUSALS = {
    # key: (exit code, fixed text)
    "root": (EXIT_UNSUPPORTED, "Refused: run this as the desktop user, without sudo."),
    "unsupported_os": (
        EXIT_UNSUPPORTED,
        "Refused: setup kiosk supports only Raspberry Pi OS (64-bit) with the desktop, on a Raspberry Pi. "
        "The hub itself runs on any 64-bit Linux; on other devices open the hub in a browser's kiosk mode "
        "(docs/raspberry-pi.md, Kiosk on other devices).",
    ),
    "no_desktop": (
        EXIT_UNSUPPORTED,
        "Refused: no Raspberry Pi OS desktop session (labwc) is running for this user. Log in to the desktop "
        "on the Pi's own screen, then run this again from its Terminal (or from an SSH login of the same user). "
        "An image without the desktop (Lite) is not supported. " + MANUAL,
    ),
    "other_desktop": (
        EXIT_UNSUPPORTED,
        "Refused: this desktop is not Raspberry Pi OS's Wayland/labwc session (for example X11 or Wayfire), "
        "and setup kiosk never configures those. Switch to labwc in sudo raspi-config (Advanced Options, "
        "Wayland), log in again and rerun, or " + _lower_first(MANUAL),
    ),
    "session": (
        EXIT_UNSUPPORTED,
        "Refused: this labwc session is not set up the way current Raspberry Pi OS sets it up (labwc with "
        "merged configuration, kanshi and its display socket). Update Raspberry Pi OS and log in again, or "
        + _lower_first(MANUAL),
    ),
    "no_chromium": (
        EXIT_UNSUPPORTED,
        "Refused: Chromium was not found (chromium or chromium-browser). Install it from Raspberry Pi OS's own "
        "packages, then run this again.",
    ),
    "no_wlr_randr": (EXIT_UNSUPPORTED, "Refused: the connected screens could not be listed (wlr-randr is missing). " + MANUAL),
    "outputs_none": (
        EXIT_NOT_READY,
        "Stopped: no switched-on HDMI or DSI screen was found. The kiosk needs exactly one. Reconnect or "
        "switch on the screen you want to use, unplug any other screen, wait ten seconds, then run this again.",
    ),
    "outputs_several": (
        EXIT_NOT_READY,
        "Stopped: more than one screen was found. The kiosk needs exactly one HDMI or DSI screen. Reconnect "
        "or switch on the screen you want to use, unplug any other screen, wait ten seconds, then run this again.",
    ),
    "unsupported_connector": (
        EXIT_UNSUPPORTED,
        "Refused: the connected screen is not on an HDMI or DSI connector (for example DPI, composite or a "
        "virtual screen). " + MANUAL,
    ),
    "touch_none": (
        EXIT_NOT_READY,
        "Stopped: no touch input was found. Connect the screen's touch connection (many HDMI screens need a "
        "separate USB cable for touch), wait ten seconds, then run this again. For a screen without touch, "
        + _lower_first(MANUAL),
    ),
    "touch_several": (
        EXIT_NOT_READY,
        "Stopped: more than one touch input was found, so the tool cannot tell which belongs to the screen. "
        "Unplug the other touch devices (a second touch screen, a drawing tablet), then run this again.",
    ),
    "system_blanking": (
        EXIT_UNSUPPORTED,
        "Refused: screen blanking is switched on for every user of this Pi (the system-wide labwc autostart), "
        "which this tool does not change. " + MANUAL,
    ),
    "manual_kiosk": (
        EXIT_NOT_READY,
        "Stopped: labwc autostart already starts Chromium (a kiosk line added by hand). Remove that line first "
        "(docs/raspberry-pi.md, Kiosk), then run this again, so the screen never opens two browsers.",
    ),
    "rc_xml": (
        EXIT_UNSUPPORTED,
        "Refused: your labwc rc.xml could not be merged safely (it is not well-formed XML or has an unexpected "
        "layout). Fix it, or map the touch input by hand (docs/raspberry-pi.md, Kiosk).",
    ),
    "link": (
        EXIT_UNSUPPORTED,
        "Refused: a file this tool would manage (labwc autostart or rc.xml, the kanshi config, the launcher or "
        "its state folder), or a folder on the way to it, is a link or not a regular file or folder. " + MANUAL,
    ),
    "changed": (
        EXIT_CHANGED,
        "Stopped: files this tool manages (labwc autostart, labwc rc.xml, the kanshi config or the launcher) were "
        "changed after setup, for example by Control Centre. They were left as they are. Put those changes "
        "back, or remove the kiosk by hand (docs/raspberry-pi.md, Kiosk), then run this again.",
    ),
    "state_damaged": (
        EXIT_CHANGED,
        "Stopped: the kiosk's saved snapshot is missing, damaged or not in the form this version writes, so it "
        "cannot be used safely. Remove the kiosk by hand (docs/raspberry-pi.md, Kiosk).",
    ),
    "config_path": (
        EXIT_UNSUPPORTED,
        "Refused: this desktop session reads its configuration from a non-standard place (a labwc or kanshi "
        "config option, another XDG_CONFIG_HOME or XDG_CONFIG_DIRS, or another home folder), so the files this "
        "tool writes would not be used. " + MANUAL,
    ),
    "state_orphan": (
        EXIT_CHANGED,
        "Stopped: the kiosk's state folder or launcher already exists (even empty, or holding only a lock "
        "file), but without the record this tool writes, so it is not safe to take it over or delete it. "
        "Check it and remove it by hand (the paths are in docs/install-cli.md, setup kiosk), then run this "
        "again.",
    ),
    "state_link": (
        EXIT_CHANGED,
        "Stopped: the kiosk's state folder, or something inside it, is a link or not the kind of file this "
        "tool made, so it is not safe to use or delete. Check it and remove it by hand (docs/install-cli.md, "
        "setup kiosk).",
    ),
    "busy": (
        EXIT_NOT_READY,
        "Stopped: another setup kiosk run is in progress. Wait for it to finish, then run this again.",
    ),
    "changed_during": (
        EXIT_CHANGED,
        "Stopped: a file this tool manages changed while it was being updated (for example Control Centre "
        "saved it). That file was left as it is, and nothing more was written. Put the change back, then run "
        "the same command again to finish, or --undo.",
    ),
    "kept_aside": (
        EXIT_CHANGED,
        "Stopped: a file this tool manages changed while it was being updated, and the tool could not prove "
        "which version was whose, so it deleted none of them: one was kept next to the file, under the "
        "file's name followed by .sproutwall-kept- and a number. Nothing more was written. Compare the "
        "versions by hand (docs/install-cli.md, setup kiosk), then run the same command again, or --undo.",
    ),
    "unsupported_metadata": (
        EXIT_CANNOT_TELL,
        "Stopped: a file this tool manages (or one it has just written) has extra hard links, another owner "
        "or group, or extended attributes (such as an access control list), or its folder would give new "
        "files an access control list or another group. This tool could not put such a file back exactly "
        "as it was, so it stops here. " + MANUAL,
    ),
    "rename_unsupported": (
        EXIT_CANNOT_TELL,
        "Refused: the file system holding your home folder does not support the atomic swap this tool needs "
        "(renameat2 with RENAME_EXCHANGE), so it cannot update files without risking a version saved at the "
        "same moment. " + MANUAL,
    ),
    "stop_failed": (
        EXIT_NOT_READY,
        "Stopped: the running kiosk launcher or its browser could not be stopped, or the tool could not "
        "confirm that it had stopped. Log out of the desktop (or restart the Pi), then run this again.",
    ),
    "cannot_tell": (
        EXIT_CANNOT_TELL,
        "Stopped: something this tool must read could not be read, or did not have the expected form, so it "
        "cannot tell whether changing the screen settings is safe. Wait a minute and run this again from the "
        "Pi's desktop Terminal. If it repeats, " + _lower_first(MANUAL),
    ),
}

NOT_INSTALLED = "The kiosk is not set up by this tool. " + UNCHANGED
AUTOLOGIN_ON_CMD = " ".join(det.AUTOLOGIN_ON)
AUTOLOGIN_OFF_CMD = " ".join(det.AUTOLOGIN_OFF)
KIND_TEXT = {"hdmi": "HDMI", "dsi": "DSI"}

# Also hard-coded in scripts/sproutwall, which must work without this package
# (a unit test compares them).
FAILED = (
    "sproutwall: setup kiosk stopped by an unexpected error. "
    "Run ./scripts/sproutwall setup kiosk --check to see what is in place."
)
CRASH_DURING = (
    "sproutwall: setup kiosk stopped by an unexpected error after it had started writing. "
    "Run ./scripts/sproutwall setup kiosk --check, then --undo to restore the snapshot."
)


class Refused(Exception):
    def __init__(self, key):
        super().__init__(key)
        self.key = key


class Progress:
    """Whether any file has been written yet, for the crash message."""

    def __init__(self):
        self.writing = False


STARTED_WRITING = (
    "It had already started writing. Run ./scripts/sproutwall setup kiosk --check, then the same command "
    "again to finish, or --undo."
)

# Errors from kiosk_files that have their own fixed text.
ERROR_REFUSALS = (
    (kf.StateLink, "state_link"),
    (kf.KeptAside, "kept_aside"),
    (kf.ChangedMeanwhile, "changed_during"),
    (kf.Busy, "busy"),
    (kf.RenameUnsupported, "rename_unsupported"),
    (kf.UnsupportedMetadata, "unsupported_metadata"),
    (kf.StateDamaged, "state_damaged"),
    (kf.ManagedFileError, "link"),
)


def refusal_lines(key, writing=False):
    code, text = REFUSALS[key]
    if key in ("changed", "changed_during", "kept_aside"):
        return code, [text]  # the text says what was and was not changed
    return code, [text, STARTED_WRITING if writing else UNCHANGED]


# --- shared steps --------------------------------------------------------------------

SESSION_REFUSAL = {
    "root": "root",
    "no_desktop": "no_desktop",
    "other_desktop": "other_desktop",
    "no_merge": "session",
    "no_kanshi": "session",
    "no_socket": "session",
    "config_path": "config_path",
}


def supported_session(system):
    """The labwc session, or raise Refused / det.CannotTell. Checks root,
    platform, session and Chromium, in that order."""
    if system.euid() == 0:
        raise Refused("root")
    if not det.platform_supported(system):
        raise Refused("unsupported_os")
    session = det.find_session(system)
    if not session.ok:
        raise Refused(SESSION_REFUSAL[session.reason])
    if det.find_chromium(system) is None:
        raise Refused("no_chromium")
    return session


def the_output(system, session):
    try:
        outputs = det.read_outputs(system, session)
    except det.OutputsUnreadable as error:
        raise Refused("no_wlr_randr") from error
    kind, output = det.classify_outputs(outputs)
    if kind != "one":
        raise Refused({"none": "outputs_none", "several": "outputs_several"}.get(kind, kind))
    return output


def the_touch(system):
    kind, name = det.find_touch(system)
    if kind != "one":
        raise Refused("touch_" + kind)
    return name


def classify(state):
    """"absent", "manifest" or "foreign" (see State.classify)."""
    try:
        return state.classify()
    except kf.StateLink as error:
        raise Refused("state_link") from error
    except kf.ManagedFileError as error:
        raise Refused("link") from error
    except OSError as error:
        raise det.CannotTell("state") from error


def _foreign_refusal(state):
    """A state folder without a record: "busy" if a run holds its lock (a
    first setup between making the folder and writing its record), else
    "state_orphan". Only reads; nothing is made."""
    try:
        fd = kf.open_dir(state.home, kiosk.KIOSK_STATE_DIR)
    except (OSError, kf.ManagedFileError):
        return "state_orphan"
    try:
        lock = kf.lock_fd(fd, shared=True)
    except kf.Busy:
        return "busy"
    except (OSError, kf.StateLink):
        return "state_orphan"
    else:
        os.close(lock)
        return "state_orphan"
    finally:
        os.close(fd)


def _state_or_refuse(state):
    kind = classify(state)
    if kind == "foreign":
        raise Refused(_foreign_refusal(state))
    return kind


def _state_errors(fn):
    """Run fn, turning state-folder problems into refusals."""
    try:
        return fn()
    except kf.StateLink as error:
        raise Refused("state_link") from error
    except kf.StateDamaged as error:
        raise Refused("state_damaged") from error
    except kf.Busy as error:
        raise Refused("busy") from error
    except kf.ManagedFileError as error:
        raise Refused("state_link") from error
    except OSError as error:
        raise det.CannotTell("state") from error


def open_and_lock(state):
    """Open an existing state folder and take the exclusive run lock (so no
    other run, and no new launcher, starts meanwhile). Nothing is created:
    a record without its setup.lock (removed by hand) is a damaged state,
    refused before any check could report that nothing was changed while
    something was. Returns the lock fd."""

    def go():
        state.open()
        try:
            return kf.lock_fd(state.fd)
        except FileNotFoundError as error:
            raise kf.StateDamaged("setup.lock missing") from error

    return _state_errors(go)


def load_manifest(state):
    return _state_errors(state.load)


def check_no_links(state):
    """Refuse before writing if any managed path, or a folder on the way, is a link."""
    try:
        kf.assert_no_links(state.home, list(kf.MANAGED.values()))
    except kf.ManagedFileError as error:
        raise Refused("link") from error
    except OSError as error:
        raise det.CannotTell("home-files") from error


def observe_all(state):
    """{key: Seen} for the managed files: bytes, metadata, identity."""
    try:
        return {key: kf.observe(state.home, kf.MANAGED[key]) for key in kf.MANAGED}
    except kf.ManagedFileError as error:
        raise Refused("link") from error
    except OSError as error:
        raise det.CannotTell("home-files") from error


def check_metadata(seen):
    """Refuse files this tool could not put back exactly (hard links,
    another owner or group, extended attributes such as ACLs)."""
    try:
        for key in kf.MANAGED:
            kf.check_supported(seen[key])
    except kf.UnsupportedMetadata as error:
        raise Refused("unsupported_metadata") from error


def originals(state, manifest, seen):
    """{key: pre-install bytes or None}."""
    return _state_errors(lambda: {key: state.original_bytes(manifest, key, seen[key]) for key in kf.MANAGED})


def copies_to_save(state, manifest, seen):
    """Keys whose saved original copy is missing but can be taken from the
    file itself (it is still exactly the original). A copy that is there
    but not the original, or missing when the file has changed, is a
    damaged snapshot."""
    needed = []
    for key in kf.MANAGED:
        original = manifest["files"][key]["original"]
        if not original["exists"]:
            continue
        copy = _state_errors(lambda: state.observe_created(os.path.join(kf.ORIGINALS, key)))
        if copy.exists and copy.sha256 == original["sha256"]:
            continue
        if not copy.exists and kf.matches(seen[key], original):
            needed.append(key)
        else:
            raise Refused("state_damaged")
    return needed


def check_state_dirs(state):
    """Before any write: the state folder's subfolders are real folders."""
    _state_errors(state.check_dirs)


def check_created(state, manifest, changed_ok=False):
    """Before any write: no link in the state folder (state_link), and
    every file setup made there is still what it recorded, or missing and
    made again (else state_damaged). With changed_ok (--undo) a changed
    file is allowed: undo keeps it and says so."""
    check_state_dirs(state)
    for rel in manifest["created_files"]:
        if _state_errors(lambda: state.created_matches(manifest, rel)) is False and not changed_ok:
            raise Refused("state_damaged")


def verify_accepted(manifest, seen):
    if kf.changed_since_setup(manifest, seen):
        raise Refused("changed")


def recheck(state, seen):
    """Observe again right before writing: anything that changed since the
    check stops the run before it writes anything."""
    now = observe_all(state)
    if any(not now[key].same_file(seen[key]) for key in kf.MANAGED):
        raise Refused("changed")


def probe(state):
    """Before any write: atomic exchange must work where the managed files live."""
    try:
        kf.probe_rename_support(state.home, list(kf.MANAGED.values()) + [kf.state_rel(kf.MANIFEST)])
    except kf.RenameUnsupported as error:
        raise Refused("rename_unsupported") from error
    except kf.UnsupportedMetadata as error:
        raise Refused("unsupported_metadata") from error
    except kf.ManagedFileError as error:
        raise Refused("link") from error
    except OSError as error:
        raise det.CannotTell("probe") from error


def target_modes(original_states):
    """The mode each managed file is written with: its original mode if it
    existed, else the default (the launcher is always 0755)."""
    modes = {}
    for key in kf.MANAGED:
        original = original_states[key]
        modes[key] = original["mode"] if original["exists"] and key != "launcher" else kf.DEFAULT_MODES[key]
    return modes


def build_targets(base, original_states, meta):
    """{key: (bytes, mode)} for the configuration in meta, from the originals."""
    try:
        data = {
            "launcher": kf.launcher_bytes(),
            "kanshi": kf.kanshi_text(base["kanshi"], meta["connector"], meta["transform"]),
            "rc_xml": kf.rc_xml_text(base["rc_xml"], meta["touch_device"], meta["connector"]),
            "autostart": kf.autostart_text(base["autostart"], meta["enabled"]),
        }
    except kf.RcXmlError as error:
        raise Refused("rc_xml") from error
    modes = target_modes(original_states)
    return {key: (data[key], modes[key]) for key in kf.MANAGED}


def _add(items, extra):
    for item in extra:
        if item not in items:
            items.append(item)


def create_fresh_state(state, seen, autologin, meta, progress):
    """A first setup: make the state folder with mkdir (it must not exist),
    take the run lock, and write the record (phase "init") right away. If
    anything fails before the record is written, what this run made is
    removed again (the lock file only while it is still the one this run
    holds); once the record is there, the folder and its lock stay for the
    next run to finish. Returns (lock fd, manifest)."""
    created = []
    try:
        state.create(created)
    except kf.StateExists as error:
        kf.remove_created_dirs(state.home, created)
        raise Refused(_foreign_refusal(state)) from error  # made a moment ago
    except kf.ManagedFileError as error:
        kf.remove_created_dirs(state.home, created)
        raise Refused("state_link") from error
    progress.writing = True
    lock = None
    try:
        lock = kf.lock_fd(state.fd, create=True)
        files = {key: {"original": seen[key].state(), "installed": None, "previous": None, "target": None} for key in kf.MANAGED}
        manifest = {
            "schema": kf.STATE_SCHEMA,
            "phase": "init",
            "operation": "setup",
            "autologin_before": autologin,
            "created_dirs": list(created),
            "created_files": {kf.state_rel(kf.SETUP_LOCK): state.record(kf.SETUP_LOCK)},
            "files": files,
        }
        manifest.update(meta)
        state.save(manifest)
    except BaseException:
        try:
            recorded = state.observe_created(kf.MANIFEST).exists
        except BaseException:  # noqa: BLE001 - cannot tell: keep everything
            recorded = True
        if lock is not None:
            if not recorded:  # with a record, the lock stays with it: the next run finishes
                kf.unlink_if_same_inode(state.fd, kf.SETUP_LOCK, lock)
            os.close(lock)
        state.close()
        if not recorded:
            kf.remove_created_dirs(state.home, created)
        raise
    return lock, manifest


def transact(state, manifest, seen, targets, meta, operation, progress, save_copies=()):
    """One write-ahead transaction over the managed files.

    1. Everything this run will create (folders, the original copies, the
       launcher's run files) is recorded, and the record is saved with phase
       "writing" and, per file, "previous" (what it holds now) and "target".
    2. The folders and state files are made; each managed file is written,
       or removed, only if it is not already at its target, each with the
       verified exchange of kf.write_atomic / kf.remove_file.
    3. The record is saved with phase "done" and "installed" = target.
    If the run stops in step 2, every file is at its previous state, its
    original or its target, all accepted while the phase is "writing", so
    the same command (or --undo) can be run again to finish."""
    home = state.home
    managed_dirs, state_dirs, new_files = [], [], {}
    if operation != "undo":
        for key in kf.WRITE_ORDER:
            if targets[key][0] is not None:
                managed_dirs.append(os.path.dirname(kf.MANAGED[key]))
        state_dirs = list(kf.STATE_SUBDIRS)
        for key in save_copies:
            new_files[kf.state_rel(kf.ORIGINALS, key)] = (seen[key].data, 0o600)
        new_files[kf.state_rel(kf.RUN_DIR, kf.LAUNCHER_LOCK)] = (b"", 0o600)
        new_files[kf.state_rel(kf.RUN_DIR, kf.WAIT_PAGE)] = (kf.wait_page_bytes(), 0o600)
    try:
        planned = []
        for rel in managed_dirs:
            _add(planned, kf.missing_dirs(home, rel))
        for name in state_dirs:
            if not _exists_dir(state, name):
                _add(planned, [kf.state_rel(name)])
    except kf.ManagedFileError as error:
        raise Refused("link") from error
    except kf.StateLink as error:
        raise Refused("state_link") from error
    except OSError as error:
        raise det.CannotTell("home-files") from error
    _add(manifest["created_dirs"], planned)
    making = {}
    for rel, (data, mode) in new_files.items():
        known = rel in manifest["created_files"]
        if not known or state.created_matches(manifest, rel) is None:
            making[rel] = (data, mode)
            manifest["created_files"][rel] = {"sha256": kf.sha256(data), "mode": mode, "dev": None, "ino": None}
        elif manifest["created_files"][rel]["ino"] is None:
            # Made by a run that stopped before recording its identity.
            manifest["created_files"][rel] = state.record(os.path.relpath(rel, kiosk.KIOSK_STATE_DIR))
    manifest.update(meta)
    manifest["phase"] = "writing"
    manifest["operation"] = operation
    for key in kf.MANAGED:
        manifest["files"][key].update({"installed": None, "previous": seen[key].state(), "target": kf.file_state(*targets[key])})

    progress.writing = True
    state.save(manifest)
    for name in state_dirs:
        os.close(state.subdir(name, create=True))
    for rel in managed_dirs:
        kf.make_dirs(home, rel, 0o755, [])
    for rel, (data, mode) in making.items():
        manifest["created_files"][rel] = state.write_created(os.path.relpath(rel, kiosk.KIOSK_STATE_DIR), data, mode)
    order = reversed(kf.WRITE_ORDER) if operation == "undo" else kf.WRITE_ORDER
    try:
        for key in order:
            data, mode = targets[key]
            if kf.matches(seen[key], kf.file_state(data, mode)):
                continue
            if data is None:
                kf.remove_file(home, kf.MANAGED[key], seen[key])
            else:
                kf.write_atomic(home, kf.MANAGED[key], data, mode, seen[key])
    except kf.ChangedMeanwhile as error:
        raise Refused("changed_during") from error
    except kf.KeptAside as error:
        raise Refused("kept_aside") from error
    except kf.UnsupportedMetadata as error:
        raise Refused("unsupported_metadata") from error  # a generated file was rolled back
    for key in kf.MANAGED:
        entry = manifest["files"][key]
        entry.update({"installed": entry["target"], "previous": None, "target": None})
    manifest["phase"] = "done"
    state.save(manifest)
    return manifest


def _exists_dir(state, name):
    try:
        os.close(state.subdir(name))
        return True
    except FileNotFoundError:
        return False


def remove_state(state, manifest, lock):
    """After an undo: empty browser/, delete each file setup created only if
    it is still exactly what was recorded (checked again after moving it
    aside), then the record, then the lock, then each folder setup created
    if it is empty. Never a whole folder. True if everything went; False if
    something was kept (a changed file, or files setup did not make)."""
    complete = True
    state.empty_profile()
    lock_rel = kf.state_rel(kf.SETUP_LOCK)
    for rel in manifest["created_files"]:
        if rel != lock_rel and not state.remove_created(manifest, rel):
            complete = False
    if not state.remove_manifest():
        complete = False
    if lock_rel in manifest["created_files"] and not state.remove_created(manifest, lock_rel):
        complete = False
    os.close(lock)
    state.close()
    return kf.remove_created_dirs(state.home, manifest["created_dirs"]) and complete


def launcher_processes(system, state):
    """pids of this user's launcher and kiosk browser main processes. Raises det.CannotTell."""
    launcher = state.path("launcher")
    profile_flag = "--user-data-dir=" + state.profile_dir()
    pids = []
    for pid, _owner, _comm, argv in det.own_processes(system):
        if launcher in argv[:3]:
            pids.append(pid)
        elif profile_flag in argv and not any(arg.startswith("--type=") for arg in argv):
            pids.append(pid)
    return pids


def _still_running(system, state, pids):
    try:
        return [pid for pid in launcher_processes(system, state) if pid in pids]
    except det.CannotTell as error:
        raise Refused("stop_failed") from error


def stop_running(system, state):
    """SIGTERM the launcher (it closes its browser) and any kiosk browser;
    SIGKILL whatever is left after ten seconds; then confirm they are gone.
    A signal that cannot be sent, or a process still there (or a process
    table that cannot be read to confirm it), stops the run (stop_failed).
    True if anything ran."""
    pids = launcher_processes(system, state)
    for pid in pids:
        if system.kill(pid, signal.SIGTERM) == "denied":
            raise Refused("stop_failed")
    left = list(pids)
    for _ in range(20):
        if not left:
            break
        system.sleep(0.5)
        left = _still_running(system, state, pids)
    for pid in left:
        if system.kill(pid, signal.SIGKILL) == "denied":
            raise Refused("stop_failed")
    for _ in range(6):
        if not left:
            break
        system.sleep(0.5)
        left = _still_running(system, state, pids)
    if left:
        raise Refused("stop_failed")
    return bool(pids)


def reload_session(system, session):
    """kanshi re-reads its config on SIGHUP (kanshi(1)); labwc re-reads rc.xml
    and remaps touch inputs on SIGHUP, which is what `labwc --reconfigure`
    sends (labwc-config(5); labwc src/seat.c seat_reconfigure). True only if
    every signal was delivered."""
    results = [system.kill(pid, signal.SIGHUP) for pid in session.kanshi_pids]
    results.append(system.kill(session.labwc_pid, signal.SIGHUP))
    return all(result == "sent" for result in results)


RELOAD_FAILED = (
    "labwc or kanshi could not be told to reload, so the new settings are not in effect yet. They apply "
    "at the next login (sudo reboot)."
)


def rotation_applied(system, session, connector, transform, attempts=6):
    """Read the transform back; False (not confirmed) if it never matches or cannot be read."""
    for attempt in range(attempts):
        try:
            outputs = det.read_outputs(system, session)
        except (det.CannotTell, det.OutputsUnreadable):
            outputs = []
        if any(o.name == connector and o.transform == transform for o in outputs):
            return True
        if attempt + 1 < attempts:
            system.sleep(0.5)
    return False


def autologin_lines(state_now):
    if state_now == "on":
        return ["Autologin: already on for this user."]
    head = {
        "other_user": "Autologin: set for a different user, so the kiosk would not start after a power cut.",
        "off": "Autologin: off.",
    }.get(state_now, "Autologin: could not be read.")
    return [
        head + " This step needs administrator rights, so this tool does not do it. Run it yourself in the "
        "Pi's terminal; sudo asks for your password:",
        "  " + AUTOLOGIN_ON_CMD,
    ]


# --- setup ---------------------------------------------------------------------------------


def _release(state, lock):
    if lock is not None:
        try:
            os.close(lock)
        except OSError:
            pass
    state.close()


def run_setup(system, orientation, progress):
    home = system.home()
    session = supported_session(system)
    state = kf.State(home)
    check_no_links(state)
    kind = _state_or_refuse(state)
    lock = None
    try:
        manifest = None
        if kind == "manifest":
            lock = open_and_lock(state)
            manifest = load_manifest(state)
        seen = observe_all(state)
        check_metadata(seen)
        if manifest is not None:
            verify_accepted(manifest, seen)
            check_created(state, manifest)
            save_copies = copies_to_save(state, manifest, seen)
            base = originals(state, manifest, seen)
            original_states = {key: manifest["files"][key]["original"] for key in kf.MANAGED}
        else:
            if seen["launcher"].exists:
                raise Refused("state_orphan")
            save_copies = [key for key in kf.MANAGED if seen[key].exists]
            base = {key: seen[key].data for key in kf.MANAGED}
            original_states = {key: seen[key].state() for key in kf.MANAGED}
        if det.system_blanking(system):
            raise Refused("system_blanking")
        output = the_output(system, session)
        touch = the_touch(system)
        if orientation is None:
            orientation = manifest["orientation"] if manifest is not None else det.DEFAULT_ORIENTATION
        transform = det.transform_for(orientation, output)
        if any(det.launches_chromium(line) for line in kf.decode_text(base["autostart"]).splitlines()):
            raise Refused("manual_kiosk")
        meta = {"enabled": True, "orientation": orientation, "connector": output.name, "transform": transform, "touch_device": touch}
        targets = build_targets(base, original_states, meta)
        autologin = det.autologin_state(system)
        probe(state)
        recheck(state, seen)
        if manifest is None:
            lock, manifest = create_fresh_state(state, seen, autologin, meta, progress)
        transact(state, manifest, seen, targets, meta, "setup", progress, save_copies)
    finally:
        _release(state, lock)

    reloaded = reload_session(system, session)
    applied = reloaded and rotation_applied(system, session, output.name, transform)
    kind_text = KIND_TEXT[det.connector_kind(output.name)]
    lines = [
        "Kiosk set up on the %s screen: %s (output transform %s)." % (kind_text, orientation, transform),
        "  Rotation: saved in the kanshi config; "
        + ("applied now." if applied else "not confirmed yet, it applies at the next login."),
        "  Touch: the one touch input is mapped to this screen in labwc rc.xml"
        + ("; labwc reloaded." if reloaded else "."),
        "  Screen blanking: off from the next login. The hub's own screensaver is not affected.",
        "  Launcher: one line in labwc autostart. It opens the hub once /api/health answers ok.",
        "  Snapshot: saved. ./scripts/sproutwall setup kiosk --undo restores the previous settings.",
        "",
        "Now tap the four corners and the centre of the screen. Each tap must land under your finger;",
        "a rotated picture alone does not prove the touch mapping. If taps land elsewhere, run",
        "./scripts/sproutwall setup kiosk --undo and report it.",
        "",
    ]
    lines += autologin_lines(autologin)
    lines += ["", "Then restart to start the kiosk: sudo reboot"]
    if not reloaded:
        lines += ["", RELOAD_FAILED]
        return EXIT_ATTENTION, lines
    return EXIT_OK, lines


# --- off -------------------------------------------------------------------------------------


def run_off(system, progress):
    if system.euid() == 0:
        raise Refused("root")
    state = kf.State(system.home())
    check_no_links(state)
    if _state_or_refuse(state) != "manifest":
        return EXIT_OK, [NOT_INSTALLED]
    lock = None
    try:
        lock = open_and_lock(state)
        manifest = load_manifest(state)
        seen = observe_all(state)
        check_metadata(seen)
        stopped = stop_running(system, state)
        stop_line = "Stopped the running kiosk browser." if stopped else "No kiosk browser was running."
        if kf.changed_since_setup(manifest, seen):
            code, text = REFUSALS["changed"]
            return code, [stop_line, text, "If the launcher line is still active, it starts again at the next login."]
        check_created(state, manifest)
        save_copies = copies_to_save(state, manifest, seen)
        base = originals(state, manifest, seen)
        meta = {key: manifest[key] for key in ("orientation", "connector", "transform", "touch_device")}
        meta["enabled"] = False
        original_states = {key: manifest["files"][key]["original"] for key in kf.MANAGED}
        targets = build_targets(base, original_states, meta)
        probe(state)
        recheck(state, seen)  # after waiting for the browser to stop
        transact(state, manifest, seen, targets, meta, "off", progress, save_copies)
    finally:
        _release(state, lock)
    return EXIT_OK, [
        stop_line,
        "Kiosk launch is off: the launcher line stays in labwc autostart as a comment. Rotation, touch and "
        "blanking settings are kept.",
        "The hub keeps running; phones on the home network still reach it.",
        "Turn the kiosk back on with ./scripts/sproutwall setup kiosk (it starts at the next login).",
    ]


# --- undo --------------------------------------------------------------------------------------


def run_undo(system, progress):
    if system.euid() == 0:
        raise Refused("root")
    home = system.home()
    state = kf.State(home)
    check_no_links(state)
    if _state_or_refuse(state) != "manifest":
        return EXIT_OK, [NOT_INSTALLED]
    lock = None
    try:
        lock = open_and_lock(state)
        manifest = load_manifest(state)
        seen = observe_all(state)
        check_metadata(seen)
        verify_accepted(manifest, seen)
        check_created(state, manifest, changed_ok=True)
        before = originals(state, manifest, seen)
        stop_running(system, state)
        probe(state)
        recheck(state, seen)  # after waiting for the browser to stop
        targets = {key: (before[key], manifest["files"][key]["original"]["mode"]) for key in kf.MANAGED}
        meta = {key: manifest[key] for key in ("enabled", "orientation", "connector", "transform", "touch_device")}
        autologin_before = manifest["autologin_before"]
        manifest = transact(state, manifest, seen, targets, meta, "undo", progress)
        complete = remove_state(state, manifest, lock)
        lock = None
    finally:
        _release(state, lock)
    try:
        session = det.find_session(system) if det.platform_supported(system) else None
    except det.CannotTell:
        session = None
    reloaded = session is not None and session.ok and reload_session(system, session)
    lines = [
        "Kiosk removed. labwc autostart, labwc rc.xml and the kanshi config are back as they were before setup "
        "(files that did not exist then were removed). The launcher, its browser profile and the snapshot "
        "were deleted.",
        "Rotation and touch mapping were reloaded." if reloaded else "Rotation and touch mapping return at the next login.",
        "Screen blanking is back as it was from the next login. The hub and its data were not touched.",
    ]
    if not complete:
        lines.append(
            "The kiosk's state folder was kept, because it holds files that setup did not make or that "
            "changed after setup made them. Check them and remove the folder by hand (docs/install-cli.md, "
            "setup kiosk)."
        )
    if autologin_before in ("off", "other_user") and det.autologin_state(system) == "on":
        lines += [
            "Autologin was not on for this user before setup and is on now. To turn it off, run this yourself "
            "in the Pi's terminal:",
            "  " + AUTOLOGIN_OFF_CMD,
        ]
    if session is not None and session.ok and not reloaded:
        lines += [RELOAD_FAILED]
        return EXIT_ATTENTION, lines
    return EXIT_OK, lines


# --- check ---------------------------------------------------------------------------------------

CHECK_SCHEMA = 1
CHECK_FIELDS = (
    ("result", ("ok", "attention", "not_installed", "unsupported", "unknown")),
    ("reason", ("none", "root", "unsupported_os", "no_desktop", "other_desktop", "session", "config_path", "no_chromium", "cannot_tell", "unknown")),
    ("installed", ("yes", "no", "damaged", "unknown")),
    ("launch", ("on", "off", "duplicate", "none", "unknown")),
    ("files", ("as_set_up", "partial", "changed", "none", "unknown")),
    ("running", ("yes", "no", "unknown")),
    ("output", ("one", "none", "several", "unsupported_connector", "unknown")),
    ("orientation", det.ORIENTATIONS + ("none", "unknown")),
    ("rotation", ("applied", "not_applied", "none", "unknown")),
    ("touch", ("mapped", "not_mapped", "none", "unknown")),
    ("blanking", ("off", "on", "system", "unknown")),
    ("autologin", ("on", "off", "other_user", "unknown")),
)
CHECK_TITLES = {
    "installed": "Set up by this tool",
    "launch": "Launcher line in labwc autostart",
    "files": "Managed files against the setup hashes",
    "running": "Launcher running now",
    "output": "Connected screens",
    "orientation": "Chosen orientation",
    "rotation": "Rotation in effect",
    "touch": "Touch mapped to the screen",
    "blanking": "Desktop screen blanking",
    "autologin": "Desktop autologin for this user",
}
CHECK_EXIT = {"ok": EXIT_OK, "attention": EXIT_ATTENTION, "not_installed": EXIT_ATTENTION, "unknown": EXIT_CANNOT_TELL}


def unknown_report(result="unknown", reason="unknown"):
    report = {key: "unknown" for key, _ in CHECK_FIELDS}
    report.update({"result": result, "reason": reason})
    return report


def serialize_check(report):
    """One line of JSON, closed: schema, then fixed keys in order, allowlisted values only."""
    if set(report) != {key for key, _ in CHECK_FIELDS}:
        raise ValueError("check keys")
    out = {"schema": CHECK_SCHEMA}
    for key, allowed in CHECK_FIELDS:
        canonical = next((item for item in allowed if item == report[key]), None)
        if canonical is None:
            raise ValueError("check value")
        out[key] = canonical
    return json.dumps(out, separators=(",", ":"), ensure_ascii=True)


def fallback_json():
    """The --check --json answer for a run that could not look at anything."""
    return serialize_check(unknown_report())


# Everything a detection step raises when it cannot read or cannot parse a
# source, or a tool it runs is missing: --check reports that item as unknown.
UNREADABLE = (
    det.CannotTell,
    det.OutputsUnreadable,
    Refused,
    kf.RcXmlError,
    kf.StateDamaged,
    kf.ManagedFileError,
    kf.StateLink,
    OSError,
)


def _try(fn, default="unknown"):
    try:
        return fn()
    except UNREADABLE:
        return default


def gather_check(system):
    """(report dict, refusal key or None, names of fields not as setup left them)."""
    if system.euid() == 0:
        return unknown_report("unsupported", "root"), "root", []
    state = kf.State(system.home())
    manifest = None
    try:
        kind = state.classify()
        installed = {"absent": "no", "foreign": "damaged", "manifest": "yes"}[kind]
        if installed == "yes":
            state.open()
            try:
                manifest = state.load()
            finally:
                state.close()
    except (kf.StateDamaged, kf.ManagedFileError, kf.StateLink):
        installed = "damaged"
    except OSError:
        installed = "unknown"
    session, reason = None, "none"
    try:
        session = supported_session(system)
    except Refused as refusal:
        reason = refusal.key
    except det.CannotTell:
        reason = "cannot_tell"
    if installed in ("no", "unknown") and session is None:
        return unknown_report("unsupported" if reason != "cannot_tell" else "unknown", reason), reason, []

    report = unknown_report("unknown", reason)
    report["installed"] = installed
    seen = _try(lambda: observe_all(state), None)
    current = {key: seen[key].data for key in kf.MANAGED} if seen is not None else None
    if current is not None:
        text = kf.decode_text(current["autostart"])
        active, inactive = kiosk.active_marker_lines(text), kiosk.inactive_marker_lines(text)
        report["launch"] = "duplicate" if active > 1 else "on" if active == 1 else "off" if inactive else "none"
        report["blanking"] = "on" if det.has_blanking(text) else "off"
    system_wide = _try(lambda: det.system_blanking(system), None)
    if system_wide is None:
        report["blanking"] = "unknown"
    elif system_wide:
        report["blanking"] = "system"
    report["autologin"] = _try(lambda: det.autologin_state(system))
    report["running"] = _try(lambda: "yes" if launcher_processes(system, state) else "no")
    if installed == "no":
        report["files"] = report["orientation"] = report["rotation"] = report["touch"] = "none"
    if manifest is not None:
        report["orientation"] = manifest["orientation"]
        if seen is not None:
            if kf.changed_since_setup(manifest, seen):
                report["files"] = "changed"  # bytes, mode or existence (a chmod counts)
            else:
                report["files"] = "as_set_up" if manifest["phase"] == "done" else "partial"
        if current is not None:
            report["touch"] = _try(
                lambda: "mapped"
                if kf.effective_touch_output([det.system_rc_xml(system), current["rc_xml"]], manifest["touch_device"])
                == manifest["connector"]
                else "not_mapped"
            )
    if session is not None:
        outputs = _try(lambda: det.read_outputs(system, session), None)
        if outputs is not None:
            report["output"] = det.classify_outputs(outputs)[0]
            if manifest is not None:
                live = [o for o in outputs if o.name == manifest["connector"]]
                report["rotation"] = "applied" if live and live[0].transform == manifest["transform"] else "not_applied"

    problems = []
    if installed == "yes":
        wanted = {
            "files": "as_set_up",
            "launch": "on" if manifest["enabled"] else "off",
            "output": "one",
            "rotation": "applied",
            "touch": "mapped",
            "blanking": "off",
            "autologin": "on",
        }
        problems = [key for key, value in wanted.items() if report[key] not in (value, "unknown")]
        report["result"] = "attention" if problems else "ok"
    elif installed == "no":
        report["result"] = "not_installed"
    elif installed == "damaged":
        report["result"] = "attention"
        problems = ["installed"]
    # Any field that could not be read makes the whole result unknown: "ok"
    # (or "not_installed") is never claimed for something not looked at.
    if any(report[key] == "unknown" for key, _ in CHECK_FIELDS[2:]):
        report["result"] = "unknown"
    return report, None, problems


def check_lines(report, problems):
    lines = ["Sproutwall kiosk check"]
    for key, _ in CHECK_FIELDS[2:]:
        lines.append("  %-12s %-22s %s" % (key, report[key], CHECK_TITLES[key]))
    code = CHECK_EXIT[report["result"]]
    lines.append("Result: %s (exit %d)" % (report["result"], code))
    fixable = [p for p in problems if p != "autologin"]
    if fixable:
        lines.append(
            "Not everything is as setup left it (%s). Run ./scripts/sproutwall setup kiosk again, or --undo."
            % ", ".join(fixable)
        )
    if "autologin" in problems:
        lines.append("Autologin is not on for this user. Run this yourself in the Pi's terminal: " + AUTOLOGIN_ON_CMD)
    if report["result"] == "unknown":
        lines.append("Some items could not be read. Run this again from the Pi's desktop Terminal after a minute.")
    if report["result"] == "not_installed":
        lines.append("The kiosk is not set up by this tool yet: ./scripts/sproutwall setup kiosk")
    return code, lines


# --- entry -----------------------------------------------------------------------------------------


def run(system, action, orientation=None, json_mode=False, out=None, err=None):
    """Run one action ("setup", "check", "off", "undo"); write fixed text; return the exit code."""
    progress = Progress()
    try:
        if action == "check":
            report, refusal, problems = gather_check(system)
            if refusal is not None:
                code, lines = refusal_lines(refusal if refusal in REFUSALS else "cannot_tell")
                if json_mode:
                    out.write(serialize_check(report) + "\n")
                else:
                    err.write("\n".join(lines) + "\n")
                return code
            code, lines = check_lines(report, problems)
            out.write((serialize_check(report) if json_mode else "\n".join(lines)) + "\n")
            return code
        handlers = {"setup": lambda: run_setup(system, orientation, progress), "off": lambda: run_off(system, progress), "undo": lambda: run_undo(system, progress)}
        code, lines = handlers[action]()
        (out if code == EXIT_OK else err).write("\n".join(lines) + "\n")
        return code
    except Refused as refusal:
        code, lines = refusal_lines(refusal.key, progress.writing)
        err.write("\n".join(lines) + "\n")
        return code
    except tuple(kind for kind, _ in ERROR_REFUSALS) as error:
        key = next(key for kind, key in ERROR_REFUSALS if isinstance(error, kind))
        if json_mode:
            out.write(fallback_json() + "\n")
            return EXIT_CANNOT_TELL
        code, lines = refusal_lines(key, progress.writing)
        err.write("\n".join(lines) + "\n")
        return code
    except (det.CannotTell, OSError):
        if progress.writing:
            err.write(CRASH_DURING + "\n")
            return EXIT_USAGE
        if json_mode:
            out.write(fallback_json() + "\n")
            return EXIT_CANNOT_TELL
        code, lines = refusal_lines("cannot_tell")
        err.write("\n".join(lines) + "\n")
        return code
    except (Exception, KeyboardInterrupt):  # noqa: BLE001 - fixed text only, never the error
        if json_mode:
            out.write(fallback_json() + "\n")
        else:
            err.write((CRASH_DURING if progress.writing else FAILED) + "\n")
        return EXIT_USAGE
