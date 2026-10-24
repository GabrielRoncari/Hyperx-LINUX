"""A virtual keyboard and mouse (uinput) that performs the actions given to device buttons: keys,
media keys, macros, and the buttons it passes through while it holds a device grabbed.

uinput is the kernel's way for a program to type; /dev/uinput needs the udev rule from
`hyperx-linux udev-rules` (the same one Steam ships) or root.
"""
from __future__ import annotations

import fcntl
import os
import struct
import time

from . import keymap

# HID keyboard usage -> Linux key code: the kernel's hid_keyboard[] (drivers/hid/hid-input.c), 0 = none
HID_TO_KEY = (
      0,   0,   0,   0,  30,  48,  46,  32,  18,  33,  34,  35,  23,  36,  37,  38,
     50,  49,  24,  25,  16,  19,  31,  20,  22,  47,  17,  45,  21,  44,   2,   3,
      4,   5,   6,   7,   8,   9,  10,  11,  28,   1,  14,  15,  57,  12,  13,  26,
     27,  43,  43,  39,  40,  41,  51,  52,  53,  58,  59,  60,  61,  62,  63,  64,
     65,  66,  67,  68,  87,  88,  99,  70, 119, 110, 102, 104, 111, 107, 109, 106,
    105, 108, 103,  69,  98,  55,  74,  78,  96,  79,  80,  81,  75,  76,  77,  71,
     72,  73,  82,  83,  86, 127, 116, 117, 183, 184, 185, 186, 187, 188, 189, 190,
    191, 192, 193, 194, 134, 138, 130, 132, 128, 129, 131, 137, 133, 135, 136, 113,
    115, 114,   0,   0,   0, 121,   0,  89,  93, 124,  92,  94,  95,   0,   0,   0,
    122, 123,  90,  91,  85,   0,   0,   0,   0,   0,   0,   0, 111,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 179, 180,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0, 111,   0,   0,   0,   0,   0,   0,   0,
     29,  42,  56, 125,  97,  54, 100, 126, 164, 166, 165, 163, 161, 115, 114, 113,
    150, 158, 159, 128, 136, 177, 178, 176, 142, 152, 173, 140,   0,   0,   0,   0,
)
# consumer usages the app offers (keymap.MEDIA) -> Linux key code, as hid-input.c maps them
CONSUMER_TO_KEY = {
    0x0B5: 163, 0x0B6: 165, 0x0B7: 166, 0x0CD: 164, 0x0E2: 113, 0x0E9: 115, 0x0EA: 114, 0x18A: 155,
    0x192: 140, 0x194: 144, 0x196: 150, 0x221: 217, 0x223: 172, 0x224: 158, 0x225: 159, 0x22A: 156,
}
BUTTON_TO_KEY = {1: 0x110, 2: 0x111, 4: 0x112, 8: 0x113, 16: 0x114}  # keymap.MOUSE_BUTTONS bits -> BTN_*
KEY_MICMUTE = 248

EV_SYN, EV_KEY, EV_REL = 0x00, 0x01, 0x02
REL_X, REL_Y, REL_WHEEL = 0x00, 0x01, 0x08
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_SETUP, UI_DEV_CREATE, UI_DEV_DESTROY = 0x405C5503, 0x5501, 0x5502
BUS_VIRTUAL = 0x06
EVENT = struct.Struct("llHHi")  # struct input_event: timeval, type, code, value
PATHS = ("/dev/uinput", "/dev/input/uinput")


def available() -> bool:
    return any(os.access(p, os.W_OK) for p in PATHS)


class VirtualInput:
    """One virtual device with every key, the five mouse buttons and the wheel."""

    def __init__(self, name: str = "HyperX Linux virtual input"):
        path = next((p for p in PATHS if os.path.exists(p)), PATHS[0])
        self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        try:
            for ev in (EV_SYN, EV_KEY, EV_REL):
                fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
            for code in sorted({*range(1, 249), *BUTTON_TO_KEY.values()}):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            for rel in (REL_X, REL_Y, REL_WHEEL):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, rel)
            setup = struct.pack("HHHH80sI", BUS_VIRTUAL, 0x03F0, 0x0001, 1, name.encode()[:79], 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise
        time.sleep(0.2)  # let the compositor pick the new device up before the first event

    def close(self) -> None:
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)

    # ------------------------------------------------------------- events
    def emit(self, type_: int, code: int, value: int) -> None:
        os.write(self.fd, EVENT.pack(0, 0, type_, code, value))

    def key(self, code: int, down: bool) -> None:
        self.emit(EV_KEY, code, 1 if down else 0)
        self.emit(EV_SYN, 0, 0)

    def tap(self, codes: list[int]) -> None:
        """Press the keys in order and release them in reverse (a shortcut)."""
        for code in codes:
            self.key(code, True)
            time.sleep(0.01)
        for code in reversed(codes):
            self.key(code, False)
            time.sleep(0.01)

    def wheel(self, steps: int) -> None:
        self.emit(EV_REL, REL_WHEEL, steps)
        self.emit(EV_SYN, 0, 0)

    def action(self, a: keymap.Action) -> None:
        """A key, shortcut, media key or mouse button from keymap.parse_action."""
        if a.kind == "key":
            mods = [HID_TO_KEY[0xE0 + bit] for bit in range(8) if a.modifiers >> bit & 1]
            self.tap(mods + ([HID_TO_KEY[a.usage]] if a.usage and HID_TO_KEY[a.usage] else []))
        elif a.kind == "media" and a.usage in CONSUMER_TO_KEY:
            self.tap([CONSUMER_TO_KEY[a.usage]])
        elif a.kind == "mouse" and a.name.startswith("wheel-"):
            self.wheel(1 if a.name == "wheel-up" else -1)
        elif a.kind == "mouse":
            self.play(keymap.parse_macro("click:" + a.name) if a.name != "double-click"
                      else keymap.parse_macro("click:left, 30ms, click:left"))
        else:
            raise ValueError(f"can't perform {a.kind!r} on this computer")

    def play(self, events: list[keymap.MacroEvent]) -> None:
        for e in events:
            if e.kind == "key" and HID_TO_KEY[e.code]:
                self.key(HID_TO_KEY[e.code], e.down)
            elif e.kind == "button" and e.code in BUTTON_TO_KEY:
                self.key(BUTTON_TO_KEY[e.code], e.down)
            elif e.kind == "wheel" and e.down:
                self.wheel(e.code)
            time.sleep(e.delay_ms / 1000)
