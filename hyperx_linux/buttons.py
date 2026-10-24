"""Other actions for a headset's buttons: the multi-function button (play/pause, next and previous,
by number of presses), volume and mute. NGENUITY only offers this for the Cloud Alpha 2's DAC keys,
and there too it happens on the PC (macros, text, launching programs); the headsets just send media
keys. Here the app takes the headset's media-key input device exclusively (EVIOCGRAB) while a button
is remapped: a remapped button runs its action, the others are passed on through a virtual device
(uinput), so volume keeps working. Nothing is written to the headset.

The input device is found through sysfs, which anyone can read; reading its events needs the udev
rule from `hyperx-linux udev-rules`.
"""
from __future__ import annotations

import fcntl
import glob
import os
import queue
import select
import subprocess
import threading
from typing import Callable

from . import controls as C
from . import keymap, uinput

EVIOCGRAB = 0x40044590
EV_KEY = 0x01
# Linux key code -> (button id, label); the codes hid-input.c gives the consumer usages headsets send
BUTTONS = {
    164: ("play_pause", "Multi-function button: play/pause"),
    163: ("next", "Multi-function button: next track"),
    165: ("previous", "Multi-function button: previous track"),
    115: ("volume_up", "Volume up"),
    114: ("volume_down", "Volume down"),
    113: ("mute", "Mute"),
}
DEVICE_ACTIONS = (("mic-mute", "Mute or unmute the microphone"), ("sidetone", "Microphone monitoring on/off"),
                  ("spatial", "Spatial audio on/off"))


def media_keys(capabilities: str) -> set[int]:
    """The BUTTONS among the keys of a sysfs capabilities/key bitmap (hex words, most significant first)."""
    bits = 0
    for word in capabilities.split():
        bits = bits << 64 | int(word, 16)
    return {code for code in BUTTONS if bits >> code & 1}


def find_input(hidraw_path: str) -> tuple[str | None, set[int]]:
    """The event node of the same USB device with the most media keys, and those keys."""
    try:
        hid = os.path.realpath(f"/sys/class/hidraw/{os.path.basename(hidraw_path)}/device")
    except OSError:
        return None, set()
    parts = hid.split("/")
    usb = next(("/".join(parts[:i]) for i in range(len(parts) - 1, 0, -1) if ":" in parts[i]
                and "." in parts[i].split(":")[-1] and "-" in parts[i]), None)  # 1-3:1.3 -> its parent 1-3
    if usb is None:
        return None, set()
    best, best_keys = None, set()
    for event in sorted(glob.glob("/sys/class/input/event*")):
        device = os.path.realpath(f"{event}/device")
        if not device.startswith(usb + "/"):
            continue
        try:
            with open(f"{device}/capabilities/key") as f:
                keys = media_keys(f.read())
        except (OSError, ValueError):
            continue
        if len(keys) > len(best_keys):
            best, best_keys = f"/dev/input/{os.path.basename(event)}", keys
    return best, best_keys


def button_control(keys: set[int], device_actions) -> C.ButtonMap:
    return C.ButtonMap("buttons", "Headset buttons", C.Group.BUTTONS,
                       "Done by the app while it runs; “Original” keeps what the button does",
                       buttons=tuple(BUTTONS[k] for k in sorted(keys, key=list(BUTTONS).index)),
                       device_actions=device_actions)


MACROS = C.MacroList("button_macros", "Macros for the buttons", C.Group.BUTTONS,
                     "Give one to a button above to play it")
LAST = C.Info("last_button", "Last button pressed", C.Group.BUTTONS,
              "Press the multi-function button once, twice and three times to see what each sends")


class ButtonMapper:
    def __init__(self, event_path: str, keys: set[int], notify: Callable[[str, object], None],
                 device_action: Callable[[str], None], device_actions=DEVICE_ACTIONS, run_command=None):
        self.event_path = event_path
        self.keys = keys
        self._notify = notify
        self._device_action = device_action
        self._run_command = run_command or (lambda cmd: subprocess.Popen(
            ["sh", "-c", cmd], stdin=subprocess.DEVNULL, start_new_session=True))
        self.controls = (button_control(keys, device_actions), MACROS, LAST)
        self.values: dict[str, object] = {}
        self.remap: dict[str, str] = {}
        self.macros: dict[str, dict] = {}
        self._fd: int | None = None
        self._grabbed = False
        self._virtual: uinput.VirtualInput | None = None
        self._stop_r, self._stop_w = os.pipe()
        self._thread: threading.Thread | None = None
        self._jobs: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._run_jobs, name="button-actions", daemon=True)
        self._worker.start()

    @classmethod
    def for_node(cls, hidraw_path: str, notify, device_action, device_actions=DEVICE_ACTIONS):
        path, keys = find_input(hidraw_path)
        return cls(path, keys, notify, device_action, device_actions) if path else None

    def handles(self, control_id: str) -> bool:
        return control_id in ("buttons", "button_macros", "last_button")

    def _set_value(self, control_id, value) -> None:
        if self.values.get(control_id, object()) != value:
            self.values[control_id] = value
            self._notify(control_id, value)

    # ------------------------------------------------------------- settings
    def load_state(self, saved: dict) -> None:
        self.remap = {k: v for k, v in dict(saved.get("buttons") or {}).items() if v not in ("", "default")}
        self.macros = {n: dict(m) for n, m in dict(saved.get("button_macros") or {}).items()}
        self._set_value("buttons", dict(self.remap))
        self._set_value("button_macros", {n: dict(m) for n, m in self.macros.items()})

    def restore(self, saved: dict) -> None:
        self.load_state(saved)
        self._update()

    def apply(self, control_id: str, value, live: bool = False) -> None:
        if control_id == "buttons":
            remap = {k: v for k, v in dict(value or {}).items() if v not in ("", "default")}
            for action in remap.values():
                self.check(action)
            self.remap = remap
            self._set_value("buttons", dict(remap))
        elif control_id == "button_macros":
            self.macros = {n: dict(m) for n, m in dict(value or {}).items()}
            for m in self.macros.values():
                keymap.parse_macro(m["steps"])
            self._set_value("button_macros", {n: dict(m) for n, m in self.macros.items()})
        else:
            raise KeyError(control_id)
        self._update()

    @staticmethod
    def check(action: str) -> None:
        """Raise ValueError for an action text that can't be performed."""
        if action.startswith("run:"):
            if not action[4:].strip():
                raise ValueError("give the command to run")
            return
        if action in dict(DEVICE_ACTIONS):
            return
        a = keymap.parse_action(action)
        if a.kind in ("fn", "fn-lock"):
            raise ValueError("Fn only exists on keyboards")

    # -------------------------------------------------------------- reading
    def _update(self) -> None:
        """Hold the input device while a button is remapped; let it go otherwise."""
        want = bool(self.remap)
        if want and self._fd is None:
            self._open()
        elif not want and self._fd is not None:
            self.stop()

    def _open(self) -> None:
        try:
            self._fd = os.open(self.event_path, os.O_RDONLY | os.O_NONBLOCK)
        except PermissionError:
            raise ValueError("no permission to read the headset's buttons: update the permissions "
                             "(banner at the top of the window, or run ./install.sh again)") from None
        if uinput.available():  # without a way to pass the other buttons on, don't take them away
            try:
                self._virtual = uinput.VirtualInput()
                fcntl.ioctl(self._fd, EVIOCGRAB, 1)
                self._grabbed = True
            except OSError:
                self._grabbed = False
        if not self._grabbed:
            self._notify("error", "the buttons' own function still happens too: /dev/uinput isn't available "
                                  "(update the permissions)")
        self._thread = threading.Thread(target=self._read, name="headset-buttons", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._fd is None:
            return
        os.write(self._stop_w, b"x")
        if self._thread:
            self._thread.join(timeout=2)
        os.read(self._stop_r, 64)
        if self._grabbed:
            try:
                fcntl.ioctl(self._fd, EVIOCGRAB, 0)
            except OSError:
                pass
        os.close(self._fd)
        self._fd, self._grabbed, self._thread = None, False, None
        if self._virtual:
            self._virtual.close()
            self._virtual = None

    def _read(self) -> None:
        size = uinput.EVENT.size
        while True:
            ready, _w, _x = select.select([self._fd, self._stop_r], [], [])
            if self._stop_r in ready:
                return
            try:
                data = os.read(self._fd, size * 64)
            except BlockingIOError:
                continue
            except OSError:
                return  # unplugged
            if not data:
                return
            for i in range(0, len(data) - size + 1, size):
                _s, _us, type_, code, value = uinput.EVENT.unpack_from(data, i)
                if type_ == EV_KEY:
                    self.on_key(code, value)

    def on_key(self, code: int, value: int) -> None:
        """value 1 press, 0 release, 2 repeat."""
        button = BUTTONS.get(code, (None, ""))[0]
        action = self.remap.get(button) if button else None
        if value == 1 and button:
            self._set_value("last_button", BUTTONS[code][1])
        if action is None:
            if self._grabbed and self._virtual:  # not remapped: pass it on unchanged
                self._virtual.key(code, value != 0)
            return
        if value == 1 and action != "disabled":
            self._jobs.put(action)

    # -------------------------------------------------------------- actions
    def _run_jobs(self) -> None:
        while True:
            action = self._jobs.get()
            try:
                self.perform(action)
            except (OSError, ValueError, KeyError) as e:
                self._notify("error", f"{action}: {e}")

    def perform(self, action: str) -> None:
        if action.startswith("run:"):
            self._run_command(action[4:].strip())
        elif action in dict(DEVICE_ACTIONS):
            self._device_action(action)
        else:
            a = keymap.parse_action(action)
            virtual = self._virtual or uinput.VirtualInput()
            try:
                if a.kind == "macro":
                    macro = self.macros.get(a.name)
                    if macro is None:
                        raise ValueError(f"no macro called {a.name!r}")
                    virtual.play(keymap.parse_macro(macro["steps"]))
                else:
                    virtual.action(a)
            finally:
                if virtual is not self._virtual:
                    virtual.close()
