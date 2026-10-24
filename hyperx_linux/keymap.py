"""Key names, HID usages and the text syntax for key remaps and macros (device independent).

A remap action is one of:
    default            the key does what it says on the cap
    disabled           nothing
    fn                 acts as the Fn key
    fn-lock[:#rrggbb]  locks the Fn layer and lights the key (Origins 65/60; white by default)
    a / esc / f5 …     another key, optionally with modifiers: ctrl+c, ctrl+shift+esc, super
    media:volume-up    a media key (see MEDIA)
    mouse:left         a mouse button or wheel (see MOUSE)
    macro:NAME         plays a macro

A macro is a comma-separated list of steps:
    ctrl+c             press and release, modifiers held around the key
    down:shift / up:shift
    "some text"        typed with the US layout
    click:left         mouse button (see MOUSE_BUTTONS); wheel:up / wheel:down
    50ms               pause before the next step
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# HID keyboard page (0x07)
KEYS: dict[str, int] = {
    **{chr(ord("a") + i): 0x04 + i for i in range(26)},
    **{str(d): 0x1D + d for d in range(1, 10)}, "0": 0x27,
    "enter": 0x28, "esc": 0x29, "backspace": 0x2A, "tab": 0x2B, "space": 0x2C, "minus": 0x2D,
    "equal": 0x2E, "lbracket": 0x2F, "rbracket": 0x30, "backslash": 0x31, "nonus-hash": 0x32,
    "semicolon": 0x33, "quote": 0x34, "grave": 0x35, "comma": 0x36, "period": 0x37, "slash": 0x38,
    "capslock": 0x39, **{f"f{n}": 0x3A + n - 1 for n in range(1, 13)},
    "printscreen": 0x46, "scrolllock": 0x47, "pause": 0x48, "insert": 0x49, "home": 0x4A,
    "pageup": 0x4B, "delete": 0x4C, "end": 0x4D, "pagedown": 0x4E, "right": 0x4F, "left": 0x50,
    "down": 0x51, "up": 0x52, "numlock": 0x53, "kp-slash": 0x54, "kp-asterisk": 0x55,
    "kp-minus": 0x56, "kp-plus": 0x57, "kp-enter": 0x58,
    **{f"kp-{d}": 0x59 + (d - 1) for d in range(1, 10)}, "kp-0": 0x62, "kp-period": 0x63,
    "nonus-backslash": 0x64, "menu": 0x65, **{f"f{n}": 0x68 + n - 13 for n in range(13, 25)},
    "lctrl": 0xE0, "lshift": 0xE1, "lalt": 0xE2, "lsuper": 0xE3,
    "rctrl": 0xE4, "rshift": 0xE5, "ralt": 0xE6, "rsuper": 0xE7,
}
ALIASES = {
    "escape": "esc", "return": "enter", "del": "delete", "ins": "insert", "pgup": "pageup",
    "pgdn": "pagedown", "caps": "capslock", "prtsc": "printscreen", "win": "lsuper", "super": "lsuper",
    "meta": "lsuper", "ctrl": "lctrl", "shift": "lshift", "alt": "lalt", "altgr": "ralt", "app": "menu",
    "-": "minus", "=": "equal", "[": "lbracket", "]": "rbracket", "\\": "backslash", ";": "semicolon",
    "'": "quote", "`": "grave", ",": "comma", ".": "period", "/": "slash",
}
MODIFIER_BITS = {"lctrl": 0x01, "lshift": 0x02, "lalt": 0x04, "lsuper": 0x08,
                 "rctrl": 0x10, "rshift": 0x20, "ralt": 0x40, "rsuper": 0x80}

# consumer page (0x0C) usages
MEDIA: dict[str, int] = {
    "volume-up": 0xE9, "volume-down": 0xEA, "mute": 0xE2, "play-pause": 0xCD, "next": 0xB5,
    "previous": 0xB6, "stop": 0xB7, "mail": 0x18A, "calculator": 0x192, "computer": 0x194,
    "browser": 0x223, "search": 0x221, "back": 0x224, "forward": 0x225, "favorites": 0x22A,
}
MOUSE = ("left", "right", "middle", "back", "forward", "wheel-up", "wheel-down", "double-click")
MOUSE_BUTTONS = {"left": 0x01, "right": 0x02, "middle": 0x04, "back": 0x08, "forward": 0x10}

# US layout: character -> (key, shifted)
_SHIFTED = dict(zip('!@#$%^&*()_+{}|:"~<>?', "1234567890-=[]\\;'`,./"))


def key_usage(name: str) -> int:
    name = ALIASES.get(name.strip().lower(), name.strip().lower())
    if name not in KEYS:
        raise ValueError(f"unknown key: {name!r}")
    return KEYS[name]


def canonical_key(name: str) -> str:
    name = ALIASES.get(name.strip().lower(), name.strip().lower())
    if name not in KEYS:
        raise ValueError(f"unknown key: {name!r}")
    return name


@dataclass(frozen=True)
class Action:
    kind: str  # default, disabled, fn, fn-lock, key, media, mouse, macro
    usage: int = 0  # key: HID usage (0 for a lone modifier); media: consumer usage; fn-lock: 0xRRGGBB
    modifiers: int = 0  # key: MODIFIER_BITS mask
    name: str = ""  # mouse: MOUSE entry; macro: macro name


def parse_action(text: str) -> Action:
    original = text.strip()
    text = original.lower()
    if text in ("", "default", "none"):
        return Action("default")
    if text in ("disabled", "off"):
        return Action("disabled")
    if text == "fn":
        return Action("fn")
    if text == "fn-lock" or text.startswith("fn-lock:"):
        rgb = text.partition(":")[2].lstrip("#") or "ffffff"
        if len(rgb) != 6 or any(c not in "0123456789abcdef" for c in rgb):
            raise ValueError(f"fn-lock colour must be #rrggbb, not {rgb!r}")
        return Action("fn-lock", usage=int(rgb, 16))
    kind, _, arg = text.partition(":")
    if arg:
        if kind == "media":
            if arg not in MEDIA:
                raise ValueError(f"unknown media key: {arg!r} (one of {', '.join(MEDIA)})")
            return Action("media", usage=MEDIA[arg])
        if kind == "mouse":
            if arg not in MOUSE:
                raise ValueError(f"unknown mouse action: {arg!r} (one of {', '.join(MOUSE)})")
            return Action("mouse", name=arg)
        if kind == "macro":
            return Action("macro", name=original.split(":", 1)[1].strip())
        raise ValueError(f"unknown action: {text!r}")
    mods, usage = parse_combo(text)
    return Action("key", usage=usage, modifiers=mods)


def parse_combo(text: str) -> tuple[int, int]:
    """'ctrl+shift+esc' -> (modifier mask, key usage); a lone modifier gives (its bit, 0)."""
    if any(not p.strip() for p in text.split("+")):
        raise ValueError(f"incomplete key combination: {text!r}")
    parts = [canonical_key(p) for p in text.split("+")]
    mods = 0
    for p in parts[:-1]:
        if p not in MODIFIER_BITS:
            raise ValueError(f"{p!r} is not a modifier (in {text!r})")
        mods |= MODIFIER_BITS[p]
    last = parts[-1]
    if last in MODIFIER_BITS:
        return mods | MODIFIER_BITS[last], 0
    return mods, KEYS[last]


def format_action(a: Action) -> str:
    if a.kind in ("default", "disabled", "fn"):
        return a.kind
    if a.kind == "fn-lock":
        return "fn-lock" if a.usage == 0xFFFFFF else f"fn-lock:#{a.usage:06x}"
    if a.kind == "media":
        return "media:" + next(k for k, v in MEDIA.items() if v == a.usage)
    if a.kind in ("mouse", "macro"):
        return f"{a.kind}:{a.name}"
    names = [k for k, bit in MODIFIER_BITS.items() if a.modifiers & bit]
    if a.usage:
        names.append(next(k for k, v in KEYS.items() if v == a.usage))
    return "+".join(names)


# ------------------------------------------------------------------ macros
@dataclass(frozen=True)
class MacroEvent:
    kind: str  # key, button, wheel
    code: int  # key: HID usage; button: MOUSE_BUTTONS bit; wheel: +1 up / -1 down
    down: bool
    delay_ms: int = 0  # pause after this event


DEFAULT_GAP_MS = 20  # between the events of one step, so applications see separate presses
MAX_DELAY_MS = 0xFFFF


def parse_macro(text: str) -> list[MacroEvent]:
    events: list[MacroEvent] = []
    explicit = False  # the last event's pause came from the text, so further pauses add up

    def add(kind, code, down):
        nonlocal explicit
        events.append(MacroEvent(kind, code, down, DEFAULT_GAP_MS))
        explicit = False

    def tap(mods: list[int], usage: int):
        for m in mods:
            add("key", m, True)
        add("key", usage, True)
        add("key", usage, False)
        for m in reversed(mods):
            add("key", m, False)

    for step in _split_steps(text):
        low = step.lower()
        if m := re.fullmatch(r"(\d+)\s*ms", low):
            if not events:
                continue  # a pause before the first event means nothing to the keyboard
            last = events[-1]
            delay = (last.delay_ms if explicit else 0) + int(m[1])
            events[-1] = MacroEvent(last.kind, last.code, last.down, min(MAX_DELAY_MS, delay))
            explicit = True
        elif step.startswith('"') and step.endswith('"') and len(step) >= 2:
            for ch in step[1:-1]:
                usage, shifted = _char_key(ch)
                tap([KEYS["lshift"]] if shifted else [], usage)
        elif low.startswith(("down:", "up:")):
            which, _, key = low.partition(":")
            if key.startswith("mouse-") and key[6:] in MOUSE_BUTTONS:
                add("button", MOUSE_BUTTONS[key[6:]], which == "down")
            else:
                add("key", key_usage(key), which == "down")
        elif low.startswith("click:"):
            button = low.split(":", 1)[1]
            if button not in MOUSE_BUTTONS:
                raise ValueError(f"unknown mouse button: {button!r}")
            add("button", MOUSE_BUTTONS[button], True)
            add("button", MOUSE_BUTTONS[button], False)
        elif low in ("wheel:up", "wheel:down"):
            add("wheel", 1 if low.endswith("up") else -1, True)
        else:
            parts = [canonical_key(p) for p in low.split("+")]
            *mods, key = parts
            tap([KEYS[m] for m in mods], KEYS[key])
    if events:  # nothing to wait for after the last event
        last = events[-1]
        events[-1] = MacroEvent(last.kind, last.code, last.down, 0)
    if not events:
        raise ValueError("the macro is empty")
    return events


def _split_steps(text: str) -> list[str]:
    steps, buf, quoted = [], "", False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            steps.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if quoted:
        raise ValueError("unclosed quote in macro")
    steps.append(buf.strip())
    return [s for s in steps if s]


def _char_key(ch: str) -> tuple[int, bool]:
    if ch.isalpha() and ch.isascii():
        return KEYS[ch.lower()], ch.isupper()
    if ch.isdigit():
        return KEYS[ch], False
    if ch == " ":
        return KEYS["space"], False
    if ch == "\n":
        return KEYS["enter"], False
    if ch in _SHIFTED:
        return KEYS[canonical_key(_SHIFTED[ch])], True
    if ch in ALIASES:
        return KEYS[ALIASES[ch]], False
    raise ValueError(f"can't type {ch!r} (only ASCII with the US layout)")


def events_from_reports(reports: list[tuple[float, bytes]]) -> list[MacroEvent]:
    """Turn boot-keyboard input reports (time, 8 bytes) into key events with real pauses."""
    events: list[tuple[float, int, bool]] = []
    held: set[int] = set()
    for t, r in reports:
        if len(r) < 8:
            continue
        now = {0xE0 + bit for bit in range(8) if r[0] >> bit & 1} | {k for k in r[2:8] if k > 3}
        events += [(t, k, False) for k in sorted(held - now)] + [(t, k, True) for k in sorted(now - held)]
        held = now
    out = []
    for i, (t, k, down) in enumerate(events):
        gap = round((events[i + 1][0] - t) * 1000) if i + 1 < len(events) else 0
        out.append(MacroEvent("key", k, down, max(0, min(MAX_DELAY_MS, gap))))
    return out


def format_macro(events: list[MacroEvent]) -> str:
    """Readable text for recorded events (explicit down/up steps)."""
    names = {v: k for k, v in KEYS.items()}
    steps = []
    for e in events:
        if e.kind == "key":
            steps.append(f"{'down' if e.down else 'up'}:{names.get(e.code, hex(e.code))}")
        elif e.kind == "button":
            name = next(k for k, v in MOUSE_BUTTONS.items() if v == e.code)
            steps.append(f"{'down' if e.down else 'up'}:mouse-{name}")
        else:
            steps.append("wheel:up" if e.code > 0 else "wheel:down")
        if e.delay_ms and e is not events[-1]:
            steps.append(f"{e.delay_ms}ms")
    return ", ".join(steps)


# ------------------------------------------------------------------ labels
_LABELS = {
    "esc": "Esc", "enter": "Enter", "backspace": "Backspace", "tab": "Tab", "space": "Space", "minus": "-",
    "equal": "=", "lbracket": "[", "rbracket": "]", "backslash": "\\", "nonus-hash": "# (ISO)",
    "semicolon": ";", "quote": "'", "grave": "`", "comma": ",", "period": ".", "slash": "/",
    "capslock": "Caps Lock", "printscreen": "Print Screen", "scrolllock": "Scroll Lock", "pause": "Pause",
    "insert": "Insert", "home": "Home", "pageup": "Page Up", "delete": "Delete", "end": "End",
    "pagedown": "Page Down", "right": "→", "left": "←", "down": "↓", "up": "↑", "numlock": "Num Lock",
    "nonus-backslash": "\\ (ISO)", "menu": "Menu", "lctrl": "Left Ctrl", "lshift": "Left Shift",
    "lalt": "Left Alt", "lsuper": "Super", "rctrl": "Right Ctrl", "rshift": "Right Shift", "ralt": "Right Alt",
    "rsuper": "Right Super",
}
MEDIA_LABELS = {
    "volume-up": "Volume up", "volume-down": "Volume down", "mute": "Mute", "play-pause": "Play/pause",
    "next": "Next track", "previous": "Previous track", "stop": "Stop", "mail": "Mail", "calculator": "Calculator",
    "computer": "Files", "browser": "Web browser", "search": "Search", "back": "Back", "forward": "Forward",
    "favorites": "Favorites",
}
MOUSE_LABELS = {
    "left": "Left click", "right": "Right click", "middle": "Middle click", "back": "Back button",
    "forward": "Forward button", "wheel-up": "Scroll up", "wheel-down": "Scroll down", "double-click": "Double click",
}


def key_label(name: str) -> str:
    """'capslock' -> 'Caps Lock', 'fn+q' -> 'Fn + Q', 'kp-1' -> 'Keypad 1'."""
    if name.startswith("fn+"):
        return "Fn + " + key_label(name[3:])
    if name in _LABELS:
        return _LABELS[name]
    if name.startswith("kp-"):
        return "Keypad " + {"slash": "/", "asterisk": "*", "minus": "-", "plus": "+", "enter": "Enter",
                            "period": "."}.get(name[3:], name[3:])
    return name.upper() if len(name) == 1 or (name[0] == "f" and name[1:].isdigit()) else name
