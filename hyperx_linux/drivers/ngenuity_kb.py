"""HyperX keyboards driven by NGENUITY Legacy's per-model modules: Alloy Origins 65, Origins 60,
Alloy Origins and Alloy Elite 2. Effects, saving lighting to the keyboard, game mode, remapping,
macros, Fn lock and factory reset, each the way that model's module does it.

The protocol comes from NGENUITY Legacy 2.38 (static analysis). The Origins 65 was checked command by
command on a real keyboard; on the other models direct-mode lighting is confirmed by OpenRGB and the
rest is marked experimental until someone confirms it. Every exchange is a 64-byte feature report
without report id on interface 0, the keyboard's boot interface: NGENUITY uses interface 3, which
Linux can't bind (it has no input endpoint), but the firmware answers on either. Offsets follow
NGENUITY's 65-byte buffers, whose byte 0 is the report id; see docs/devices/keyboards.md.

  command  [1]=04 [2]=cmd, parameters from [9]; a GET_FEATURE then returns [2]=cmd [4]=01
  data     64 bytes from [1]; the last packet of a block carries AA 55 at [63..64]
  commit   command 02
Slots 0-2 are the onboard profiles and 3 is the active one, which NGENUITY writes while it runs.
After storing each packet the keyboard sends 05 AC AC AC on interface 1 (vendor collection,
report 5); when that node can be opened we wait for it like NGENUITY, otherwise for a fixed time.
"""
from __future__ import annotations

import dataclasses
import threading
import time
from dataclasses import dataclass
from typing import ClassVar

from .. import controls as C
from .. import effects as fx
from ..hid import HidError, Node, enumerate_nodes
from ..keymap import KEYS, Action, MacroEvent, events_from_reports, format_macro, parse_action, parse_macro
from .base import Driver, Kind, Support
from .kb_layouts import LAYOUTS as LAYOUT_DATA


@dataclass(frozen=True)
class Key:
    id: str
    led: int
    slot: int | None
    x: int  # centre, in NGENUITY's drawing units
    y: int
    col: int
    row: int
    w: int = 40  # key cap size, same units
    h: int = 40


def layouts(model: str) -> dict[str, tuple[Key, ...]]:
    return {name: tuple(Key(*k) for k in keys) for name, keys in LAYOUT_DATA[model].items()}


ACTIVE_SLOT = 3

CMD_COMMIT = 0x02
CMD_INFO = 0x05
CMD_MACRO_BEGIN, CMD_MACRO_END = 0x18, 0x19
CMD_LIVE_PROFILE = 0x67  # apply the profile now, without storing it
CMD_KEEPALIVE = 0xE0  # Alloy Origins, while streaming and before writes
CMD_APPLY_SYNC = 0xF0  # Alloy Origins, sent after saving lighting; effect not known
CMD_RESET = 0xFD
CMD_DIRECT = 0xF2
ACK_NOTIFICATION = b"\x05\xac\xac\xac"


class NotAccepted(HidError, ValueError):
    """The keyboard didn't acknowledge a command (silent, busy or another program talking to it)."""


def cmd_key_matrix(slot): return 0x21 + 16 * slot
def cmd_lighting_config(slot): return 0x23 + 16 * slot
def cmd_macros(slot): return 0x25 + 16 * slot
def cmd_profile_get(slot): return 0x26 + 16 * slot
def cmd_profile_set(slot): return 0x27 + 16 * slot
def cmd_erase_sync(slot): return 0x29 + 16 * slot
def cmd_frames(slot): return 0x53 + 16 * slot
def cmd_fn_lock(slot): return 0x80 + 16 * slot


# ------------------------------------------------------- remaps and macros
MOUSE_CODES = {"left": (1, 1), "right": (1, 2), "middle": (1, 4), "back": (1, 8), "forward": (1, 16),
               "wheel-up": (3, 1), "wheel-down": (3, 0xFF), "double-click": (2, 1)}
MACRO_MODE_CODES = {"once": 0, "toggle": 2, "hold": 3}
FN_KEY_USAGE = 0xA4  # what NGENUITY writes to make a key act as Fn
MAX_MACROS = 100
MACRO_TABLE = 400  # 100 little-endian offsets precede the macros


def key_slot(name: str, layout: tuple[Key, ...], fn_layer: int | None) -> int:
    """'capslock' or 'fn+q' -> key-matrix slot."""
    fn = name.startswith("fn+")
    base = name[3:] if fn else name
    key = next((k for k in layout if k.id == base and k.slot is not None), None)
    if key is None:
        raise ValueError(f"no remappable key {base!r} on this keyboard")
    if fn and fn_layer is None:
        raise ValueError("this keyboard has no Fn layer to remap")
    return key.slot + (fn_layer if fn else 0)


def action_code(a: Action, macro_index: dict[str, int], macro_modes: dict[str, str],
                fn_key: bool = True, fn_lock: str | None = "list") -> bytes:
    """NGENUITY's GetKeyAssignment: the first 4 bytes of a key-matrix slot."""
    if a.kind == "default":
        return bytes(4)
    if a.kind == "disabled":
        return bytes([5, 0, 0, 0])
    if a.kind == "fn":
        if not fn_key:
            raise ValueError("this keyboard can't turn a key into Fn")
        return bytes([2, 0, FN_KEY_USAGE, 0])
    if a.kind == "fn-lock":
        if fn_lock == "matrix":  # Origins 60: the lock is the key's action, with its colour
            return bytes([7, *a.usage.to_bytes(3, "big")])
        if fn_lock == "list":  # Origins 65: the key keeps its action; the lock list goes separately (80)
            return bytes(4)
        raise ValueError("this keyboard has no Fn lock")
    if a.kind == "key":
        return bytes([2, a.modifiers, a.usage, 0])
    if a.kind == "media":
        return bytes([3, a.usage & 0xFF, a.usage >> 8, 0])
    if a.kind == "mouse":
        return bytes([1, *MOUSE_CODES[a.name], 0])
    if a.kind == "macro":
        if a.name not in macro_index:
            raise ValueError(f"no macro named {a.name!r}")
        return bytes([6, macro_index[a.name], MACRO_MODE_CODES[macro_modes[a.name]], 0])
    raise ValueError(a.kind)


def encode_matrix(remap: dict[str, str], layout, macro_index, macro_modes, slots: int = 160, entry: int = 4,
                  fn_layer: int | None = 78, fn_key: bool = True, fn_lock: str | None = "list") -> bytes:
    matrix = bytearray(slots * entry)
    for name, text in remap.items():
        slot = key_slot(name, layout, fn_layer)
        code = action_code(parse_action(text), macro_index, macro_modes, fn_key, fn_lock)
        matrix[slot * entry:slot * entry + 4] = code
    return bytes(matrix)


def macro_item(e: MacroEvent) -> bytes:
    """delay (LE16, pause after this event), code, flags; as NGENUITY's SetMacro builds them."""
    if e.kind == "key":
        code, flags = e.code, 0x30 | (0x80 if e.down else 0)
    elif e.kind == "button":
        code, flags = e.code, 0x10 | (0x80 if e.down else 0)
    else:  # wheel
        code, flags = (1 if e.code > 0 else 0xFF), 0xA0
    return bytes([e.delay_ms & 0xFF, e.delay_ms >> 8 & 0xFF, code, flags])


def encode_macros(macros: list[list[MacroEvent]]) -> bytes:
    header, body = bytearray(MACRO_TABLE), bytearray()
    for i, events in enumerate(macros[:MAX_MACROS]):
        header[i * 4:i * 4 + 4] = (MACRO_TABLE + len(body)).to_bytes(4, "little")
        body += len(events).to_bytes(4, "little") + bytes(4)
        body += b"".join(macro_item(e) for e in events)
    if MACRO_TABLE + len(body) >= 0x10000:
        raise ValueError("the macros are too long for the keyboard's memory")
    return bytes(header + body)


# ---------------------------------------------------------------- controls
EFFECT = C.Choice("effect", "Effect", C.Group.LIGHTING, readable=False, persist=True,
                  options=tuple((e.id, e.label) for e in fx.EFFECTS) + (("custom", "Custom (painted keys)"),
                                                                         ("onboard", "Saved on the keyboard")))
# "custom": the painted keys over the colour; every other effect runs on the whole keyboard
COLOR = C.Color("color", "Color", C.Group.LIGHTING, "Used by every effect that isn't rainbow-coloured",
                readable=False, persist=True)
COLOR2 = C.Color("color2", "Second color", C.Group.LIGHTING, "Alternating and swipe", readable=False, persist=True)
DIRECTION = C.Choice("direction", "Direction", C.Group.LIGHTING, "Wave, swipe and stacking", readable=False,
                     persist=True, options=fx.DIRECTIONS)
SPEED = C.Range("speed", "Speed", C.Group.LIGHTING, readable=False, persist=True, min=1, max=100, step=1, unit="%")
BRIGHTNESS = C.Range("brightness", "Brightness", C.Group.LIGHTING, min=0, max=100, step=1, unit="%")
SOFT_BRIGHTNESS = C.Range("brightness", "Brightness", C.Group.LIGHTING, readable=False, persist=True,
                          min=0, max=100, step=1, unit="%")
SAVE = C.Action("save_lighting", "Save lighting to the keyboard", C.Group.LIGHTING,
                "It keeps playing without the app, in the active onboard profile", button="Save")
GAME_MODE = C.Toggle("game_mode", "Game mode", C.Group.KEYS, "Turns the Windows/Super key off")
BLOCKS = (
    C.Toggle("block_alt_tab", "Block Alt+Tab", C.Group.KEYS, "While game mode is on"),
    C.Toggle("block_alt_f4", "Block Alt+F4", C.Group.KEYS, "While game mode is on"),
    C.Toggle("block_shift_tab", "Block Shift+Tab", C.Group.KEYS, "While game mode is on"),
    C.Toggle("block_ctrl_esc", "Block Ctrl+Esc", C.Group.KEYS, "While game mode is on"),
)
BLOCK_BITS = {"block_alt_tab": 1, "block_alt_f4": 2, "block_shift_tab": 4, "block_ctrl_esc": 8}
MACRO_RECORD = C.Recorder("macro_record", "Record a macro", C.Group.KEYS,
                          "Type it on this keyboard; the pauses between keys are kept")
MACROS = C.MacroList("macros", "Macros", C.Group.KEYS, "Assign one to a key below to play it")
MAX_RECORDED = 400  # reports; a macro this long is almost certainly a forgotten recording
RESET = C.Action("factory_reset", "Restore factory settings", C.Group.SYSTEM,
                 "Lighting, remaps, macros and game mode of every onboard profile", button="Restore",
                 confirm="This erases the lighting, remapped keys and macros stored on the keyboard.")
LAYOUT = C.Info("layout", "Layout", C.Group.INFO)


# keys whose cap covers several LEDs: the 60 and 65 light their space bar in three zones
ZONES = {"space": ("led-space-left", "led-space-right")}


def drawn_keys(keys: tuple[Key, ...]) -> tuple[tuple[str, int, int, int, int], ...]:
    """(id, x, y, w, h) of each key cap as drawn: LED zones under a key become part of it."""
    ids = {k.id for k in keys}
    members = {m for key, ms in ZONES.items() if key in ids for m in ms}
    out = []
    for k in keys:
        if k.id in members:
            continue
        parts = [k] + [m for m in keys if m.id in ZONES.get(k.id, ())]
        left, right = min(p.x - p.w / 2 for p in parts), max(p.x + p.w / 2 for p in parts)
        top, bottom = min(p.y - p.h / 2 for p in parts), max(p.y + p.h / 2 for p in parts)
        out.append((k.id, round((left + right) / 2), round((top + bottom) / 2), round(right - left), round(bottom - top)))
    return tuple(out)


def geometry(layout_set: dict[str, tuple[Key, ...]], names: dict[str, str]) -> C.KeyGeometry:
    """Every key cap of each layout, keyed by what the Layout row shows."""
    return tuple((names[name], drawn_keys(keys)) for name, keys in layout_set.items())


def key_colors_control(layout_set, names) -> C.KeyColors:
    return C.KeyColors("key_colors", "Per-key colors", C.Group.LIGHTING,
                       "Click keys, or drag over several, and paint them; the others follow the effect",
                       layouts=geometry(layout_set, names))


def parse_hex(text: str) -> tuple[int, int, int]:
    t = str(text).lstrip("#")
    if len(t) != 6:
        raise ValueError(f"not a colour: {text!r} (use #rrggbb)")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)
FN_LOCK = C.Info("fn_lock", "Fn lock", C.Group.KEYS, "Set a key to “Fn lock” below to use it")


def remap_control(layout_set: dict[str, tuple[Key, ...]], fn_layer: int | None, names: dict[str, str]) -> C.KeyRemap:
    ids: list[str] = []
    for layout in layout_set.values():
        ids += [k.id for k in layout if k.slot is not None and k.id not in ids]
    keys = tuple((i, i) for i in ids) + (tuple((f"fn+{i}", f"fn+{i}") for i in ids) if fn_layer is not None else ())
    return C.KeyRemap("remap", "Remapped keys", C.Group.KEYS, "Stored on the keyboard, also works without the app",
                      keys=keys, layouts=geometry(layout_set, names))


def model_controls(layout_set, names, fn_layer, fn_lock, reset: bool, verified: bool) -> tuple[C.Control, ...]:
    """The Origins 65 has everything confirmed; on the others what writes to the keyboard's memory is
    experimental and brightness scales the streamed colours, which direct mode is confirmed for."""
    def x(c):
        return c if verified else dataclasses.replace(c, experimental=True)
    lighting = (EFFECT, COLOR, COLOR2, SPEED, DIRECTION, BRIGHTNESS if verified else SOFT_BRIGHTNESS,
                key_colors_control(layout_set, names), x(SAVE))
    keys = (x(GAME_MODE), *(x(b) for b in BLOCKS), MACRO_RECORD, x(MACROS),
            x(remap_control(layout_set, fn_layer, names)))
    return (lighting + keys + ((FN_LOCK,) if fn_lock else ()) + ((x(RESET),) if reset else ()) + (LAYOUT,))


FRAME_SECONDS = 0.05  # NGENUITY streams these keyboards at 20 fps
CMD_WAIT, DATA_WAIT, ACK_TIMEOUT = 0.011, 0.025, 0.5
# Commands 25 (macros) and 53 (lighting frames) first erase their memory area (~0.45 s measured on the
# Origins 65) and drop whatever arrives meanwhile; NGENUITY gets past it by waiting for the ack.


class NgenuityKeyboard(Driver):
    kind = Kind.KEYBOARD
    interfaces = (0,)
    extra_interfaces = (1,)  # acknowledgements and notifications; optional
    keepalive_seconds = FRAME_SECONDS
    poll_seconds = 10.0
    # model description, overridden per keyboard
    model: ClassVar[str]
    layout_names: ClassVar[dict[str, str]]  # layout key -> what the Layout row shows
    leds: ClassVar[int] = 80
    max_frames: ClassVar[int] = 120
    matrix_slots: ClassVar[int] = 160
    matrix_entry: ClassVar[int] = 4
    fn_layer: ClassVar[int | None] = 78
    fn_key: ClassVar[bool] = True  # a key can be turned into Fn
    fn_lock: ClassVar[str | None] = "list"  # "list" (command 80), "matrix" (action 07), None
    ap_profile_id: ClassVar[int] = 0  # byte 0 of the live ("AP") profile
    profile_fixed: ClassVar[dict[int, int]] = {}  # profile bytes NGENUITY always writes
    hardware_brightness: ClassVar[bool] = True
    frame_erase_wait: ClassVar[float] = 0.8
    macro_erase_wait: ClassVar[float] = 0.8
    matrix_commit_verified: ClassVar[bool] = True

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self.layout_set = layouts(self.model)
        self.layout = next(iter(self.layout_set.values()))
        self.fx = fx.Renderer(self.layout, self.leds)
        self.effect, self.color = "static", None  # nothing is streamed until the user picks something
        self.brightness = 100  # software brightness (models without the hardware one)
        self.remap: dict[str, str] = {}
        self.key_colors: dict[str, tuple[int, int, int]] = {}  # painted keys: shown by the "custom" effect
        self.preview: dict[str, tuple[int, int, int]] | None = None  # colours last sent, for the app to draw
        self.macros: dict[str, dict] = {}
        self.profile = bytearray(64)  # last profile read from the active slot
        self._usage_led = {}
        self._ack = threading.Event()
        self._acks: Node | None = None
        self._restoring = False
        self._held: set[int] = set()
        self._recording: list[tuple[float, bytes]] | None = None
        self._open_notifications()

    def layout_for(self, country: int) -> str:
        raise NotImplementedError

    # ------------------------------------------------------------ transport
    def _open_notifications(self) -> None:
        info = getattr(self.node, "info", None)
        if info is None or not info.usb_path:
            return
        sibling = next((n for n in enumerate_nodes() if n.usb_path == info.usb_path and n.interface == 1
                        and n.descriptor.has_page(0xFFFF)), None)
        if sibling is None:
            return
        try:
            self._acks = Node(sibling)
        except HidError:
            return  # no permission for interface 1 yet: fixed waits instead
        self._acks.listeners.append(self._on_notification)

    def close(self) -> None:
        if self._acks:
            self._acks.close()

    def _on_notification(self, r: bytes) -> None:
        if r[:4] == ACK_NOTIFICATION:
            self._ack.set()
        elif r[:2] == b"\x05\x07" and len(r) > 3:
            self.set_value("game_mode", r[3] == 1)
        elif r[:2] == b"\x05\x08" and len(r) > 2:
            self.set_value("brightness", round(r[2] * 100 / 255))
        elif r[:2] == b"\x05\x09" and len(r) > 2:
            self.set_value("fn_lock", "on" if r[2] == 1 else "off")

    def _send(self, buf: bytes, wait: float) -> None:
        self._ack.clear()
        self.node.set_feature(bytes(buf))
        if self._acks is None or not self._ack.wait(ACK_TIMEOUT):
            time.sleep(wait)

    def _command(self, cmd: int, params: dict[int, int] | None = None, erase: float = 0.0,
                 verify: bool = True) -> bytes | None:
        """Send a command and check the keyboard took it; `erase`: time it needs before data."""
        buf = bytearray(65)
        buf[1], buf[2] = 0x04, cmd
        for offset, value in (params or {}).items():
            buf[offset] = value
        self._send(buf, CMD_WAIT)
        if not verify:  # NGENUITY reads a reply here but doesn't look at it
            self.node.get_feature(0, 65)
            return None
        for _ in range(5):
            reply = self.node.get_feature(0, 65)
            if reply[2] == cmd and reply[4] == 1:
                time.sleep(erase)
                return reply
            time.sleep(0.01)
        raise NotAccepted(f"the keyboard did not accept command {cmd:02x}")

    def _data(self, payload: bytes = b"", tail: bool = False) -> None:
        buf = bytearray(65)
        buf[1:1 + len(payload)] = payload
        if tail:
            buf[63], buf[64] = 0xAA, 0x55
        self._send(buf, DATA_WAIT)

    def _commit(self, tail: bool = False, verify: bool = True) -> None:
        self._command(CMD_COMMIT, {63: 0xAA, 64: 0x55} if tail else None, verify=verify)

    def _before_write(self) -> None:
        """Hook: the Alloy Origins wants a keep-alive before key-matrix, macro and live-profile writes."""

    # ----------------------------------------------------------------- reads
    def refresh(self) -> None:
        try:
            self._command(CMD_INFO, {9: 1})
        except NotAccepted:
            return  # nothing to show yet; the next poll tries again
        info = self.node.get_feature(0, 65)  # the data follows the acknowledgement
        name = self.layout_for(info[25])
        self.layout = self.layout_set[name]
        self.fx = fx.Renderer(self.layout, self.leds)
        self._configure_fx()
        self._usage_led = {KEYS[k.id]: k for k in self.layout if k.id in KEYS}
        self.set_value("layout", self.layout_names[name])
        if not self.hardware_brightness:
            self.set_value("brightness", self.brightness)
        self.poll()

    def poll(self) -> None:
        try:
            self._command(cmd_profile_get(ACTIVE_SLOT), {9: 1})
        except NotAccepted:
            return
        self.profile = bytearray(self.node.get_feature(0, 65)[1:65])
        self.set_value("game_mode", self.profile[4] == 1)
        for cid, bit in BLOCK_BITS.items():
            self.set_value(cid, bool(self.profile[8] & bit))
        if self.hardware_brightness:
            self.set_value("brightness", round(self.profile[12] * 100 / 255))

    # ---------------------------------------------------------------- writes
    def apply(self, control_id, value):
        if control_id == "effect":
            self.effect = str(value)
            self._configure_fx()
        elif control_id == "color":
            self.color = tuple(int(c) for c in value)
            self._configure_fx()
        elif control_id in ("color2", "speed", "direction"):
            self.fx.configure(**{control_id: tuple(value) if control_id == "color2" else value})
        elif control_id == "key_colors":
            self.key_colors = {k: parse_hex(v) for k, v in dict(value or {}).items()}
            value = {k: "#%02x%02x%02x" % rgb for k, rgb in self.key_colors.items()}
        elif control_id == "brightness" and not self.hardware_brightness:
            self.brightness = max(0, min(100, int(value)))
            self.set_value("brightness", self.brightness)
        elif control_id in ("game_mode", "brightness", *BLOCK_BITS):
            self._write_profile(control_id, value)
        elif control_id == "macros":
            self.macros = {n: dict(m) for n, m in dict(value or {}).items()}
            self._check_macros()
            if not self._restoring and any(a.startswith("macro:") for a in self.remap.values()):
                self.write_keymap(ACTIVE_SLOT)
        elif control_id == "remap":
            self.remap = {k: v for k, v in dict(value or {}).items() if parse_action(v).kind != "default"}
            if not self._restoring:
                self.write_keymap(ACTIVE_SLOT)
        elif control_id == "macro_record":
            self._record(bool(value))
            return
        elif control_id == "save_lighting":
            self.save_lighting()
            return
        elif control_id == "factory_reset":
            self.factory_reset()
            return
        else:
            raise KeyError(control_id)
        self.set_value(control_id, value)

    def load_state(self, saved: dict) -> None:
        """Take the settings the app keeps (effect, remaps, macros) without talking to the keyboard."""
        self.effect = saved.get("effect", self.effect)
        self.color = tuple(saved["color"]) if saved.get("color") else self.color
        self.fx.configure(color2=saved.get("color2"), speed=saved.get("speed"), direction=saved.get("direction"))
        self._configure_fx()
        self.macros = {n: dict(m) for n, m in (saved.get("macros") or {}).items()}
        self.remap = dict(saved.get("remap") or {})
        self.key_colors = {k: parse_hex(v) for k, v in (saved.get("key_colors") or {}).items()}
        if not self.hardware_brightness and saved.get("brightness") is not None:
            self.brightness = int(saved["brightness"])
            self.set_value("brightness", self.brightness)

    def restore(self, saved: dict) -> None:
        """On connect: one keymap write for remaps and macros together, like NGENUITY's setup."""
        self._restoring = True
        try:
            for cid in ("effect", "color", "color2", "speed", "direction", "key_colors", "macros", "remap",
                        *(() if self.hardware_brightness else ("brightness",))):
                if saved.get(cid) is not None:
                    self.apply(cid, saved[cid])
        finally:
            self._restoring = False
        if self.remap:
            self.write_keymap(ACTIVE_SLOT)

    def _write_profile(self, control_id, value) -> None:
        p = bytearray(self.profile)
        if control_id == "game_mode":
            p[4] = 1 if value else 0
        elif control_id == "brightness":
            p[12] = round(max(0, min(100, int(value))) * 255 / 100)
        else:
            bit = BLOCK_BITS[control_id]
            p[8] = (p[8] | bit) if value else (p[8] & ~bit)
        self._store_profile(cmd_profile_set(ACTIVE_SLOT), p)
        self._store_live(p)
        self.profile = p

    def _store_live(self, profile: bytes) -> None:
        """Apply now (NGENUITY's "AP mode"); the profile id there depends on the model."""
        live = bytearray(profile)
        live[0] = self.ap_profile_id
        self._before_write()
        self._store_profile(CMD_LIVE_PROFILE, live)

    def _store_profile(self, cmd: int, profile: bytes) -> None:
        """NGENUITY's SetProfile: command, the 64-byte profile ending in AA 55, commit."""
        self._command(cmd, {9: 1})
        data = bytearray(profile)
        for offset, value in self.profile_fixed.items():
            data[offset] = value
        data[62:64] = b"\xaa\x55"
        self._data(bytes(data))
        self._commit()

    def _check_macros(self) -> None:
        for name, m in self.macros.items():
            parse_macro(m.get("steps", ""))  # raises on bad text
            if m.setdefault("mode", "once") not in MACRO_MODE_CODES:
                raise ValueError(f"macro {name!r}: mode must be one of {', '.join(MACRO_MODE_CODES)}")

    def write_keymap(self, slot: int) -> None:
        """Macros used by the remaps, then the 160-slot key matrix, then an empty Fn-lock list."""
        used = []
        for text in self.remap.values():
            a = parse_action(text)
            if a.kind == "macro" and a.name not in used:
                if a.name not in self.macros:
                    raise ValueError(f"no macro named {a.name!r}")
                used.append(a.name)
        index = {name: i for i, name in enumerate(used)}
        modes = {name: self.macros[name].get("mode", "once") for name in used}
        matrix = encode_matrix(self.remap, self.layout, index, modes, self.matrix_slots, self.matrix_entry,
                               self.fn_layer, self.fn_key, self.fn_lock)
        if used:
            self._write_macros(slot, [parse_macro(self.macros[n]["steps"]) for n in used])
        self._write_matrix(slot, matrix)
        if self.fn_lock == "list":
            self._write_fn_locks(slot)

    def _write_matrix(self, slot: int, matrix: bytes) -> None:
        """Command with the packet count (+1 for the AA 55 packet), the packets, AA 55, commit."""
        packets = [matrix[i:i + 64] for i in range(0, len(matrix), 64)]
        self._before_write()
        self._command(cmd_key_matrix(slot), {9: len(packets) + 1})
        for packet in packets:
            self._data(packet)
        self._data(tail=True)
        self._commit(verify=self.matrix_commit_verified)

    def _write_fn_locks(self, slot: int) -> None:
        """NGENUITY's SetFnLockSettings: the keys that lock the Fn layer, one packet each (at least one)."""
        locks = [(key_slot(k, self.layout, self.fn_layer), parse_action(v).usage) for k, v in self.remap.items()
                 if parse_action(v).kind == "fn-lock"]
        self._command(cmd_fn_lock(slot), {9: len(locks)})
        for i in range(max(len(locks), 1)):
            packet = bytearray(64)
            packet[13], packet[14] = len(locks), i
            if locks:
                packet[15] = locks[i][0]
                packet[16:19] = locks[i][1].to_bytes(3, "big")
            self._data(bytes(packet), tail=True)
        self._commit()

    def _write_macros(self, slot: int, macros: list[list[MacroEvent]]) -> None:
        """Origins 65: 18; 25 with chunks+1 (erases); chunks; AA 55 packet; 19; 02 with AA 55."""
        table = encode_macros(macros)
        chunks = [table[i:i + 64] for i in range(0, len(table), 64)]
        self._command(CMD_MACRO_BEGIN)
        self._command(cmd_macros(slot), {9: len(chunks) + 1}, erase=self.macro_erase_wait)
        for chunk in chunks:
            self._data(chunk)
        self._data(tail=True)
        self._command(CMD_MACRO_END)
        self._commit(tail=True)

    # -------------------------------------------------------------- lighting
    def _configure_fx(self) -> None:
        self.fx.configure(effect="static" if self.effect in ("onboard", "custom") else self.effect,
                          color=self.color or (255, 255, 255))

    @property
    def streaming(self) -> bool:
        """False: the keyboard shows what it has stored (nothing picked yet, or "Saved on the keyboard")."""
        return self.effect != "onboard" and (self.effect not in ("static", "custom") or self.color is not None
                                             or (self.effect == "custom" and bool(self.key_colors)))

    def _paint(self, frame) -> list:
        """In the custom effect the painted keys over the colour; then the software brightness."""
        frame = list(frame)
        zone_of = {m: key for key, ms in ZONES.items() for m in ms}
        for k in self.layout if self.effect == "custom" else ():
            painted = self.key_colors.get(k.id) or self.key_colors.get(zone_of.get(k.id, ""))
            if painted:
                frame[k.led] = painted
        if not self.hardware_brightness and self.brightness < 100:
            frame = [fx.dim(rgb, self.brightness / 100) for rgb in frame]
        return frame

    def keepalive(self) -> None:
        if not self.streaming:
            self.preview = None
            return
        frame = self._paint(self.fx.frame(time.monotonic()))
        self._show(frame)
        level = self.values.get("brightness", 100) / 100 if self.hardware_brightness else 1.0
        self.preview = {k.id: fx.dim(frame[k.led], level) if level < 1 else frame[k.led] for k in self.layout}

    def _show(self, frame) -> None:
        packets = self.leds // 16
        init = bytearray(65)
        init[1], init[2], init[9] = 0x04, CMD_DIRECT, packets
        self.node.set_feature(bytes(init))
        for p in range(packets):
            buf = bytearray(65)
            for j in range(16):
                buf[1 + 4 * j] = 0x81
                buf[2 + 4 * j:5 + 4 * j] = bytes(frame[p * 16 + j])
            self.node.set_feature(bytes(buf))

    def _record(self, start: bool) -> None:
        if start:
            self._recording = []
            self.set_value("macro_record", "")
            return
        reports, self._recording = self._recording or [], None
        events = events_from_reports(reports)
        self.set_value("macro_record", format_macro(events) if events else None)

    def handle_input(self, report: bytes) -> None:
        if self._recording is not None and len(report) == 8 and len(self._recording) < MAX_RECORDED:
            self._recording.append((time.monotonic(), bytes(report)))
        if len(report) != 8 or not (self.fx.effect.reactive and self.effect != "onboard"):
            return  # keystrokes are only looked at for reactive lighting and while recording
        now = time.monotonic()
        pressed = {k for k in report[2:8] if k > 3} | {0xE0 + b for b in range(8) if report[0] >> b & 1}
        for usage in pressed - self._held:
            key = self._usage_led.get(usage)
            if key:
                self.fx.press(key, now)
        self._held = pressed

    def save_lighting(self) -> None:
        """Origins 65 / 60 (NGENUITY's Sync): frames and timing, then the profile of the onboard slot,
        the active profile, the slot's keymap and the live profile."""
        slot = min(self.profile[0], 2)
        self._write_frames(slot, *self._render_saved())
        time.sleep(1.0)
        profile = bytearray(self.profile)
        profile[0] = slot
        self._store_profile(cmd_profile_set(slot), profile)
        self._store_profile(cmd_profile_set(ACTIVE_SLOT), profile)
        self.write_keymap(slot)
        self._store_live(self.profile)
        self.set_value("save_lighting", None)

    def _render_saved(self):
        """Frames of one loop of the effect, or a dark frame plus a reactive effect the keyboard runs."""
        if self.effect == "onboard":
            raise ValueError("pick an effect first: this one is what the keyboard already has stored")
        trigger = fx.ONBOARD_TRIGGERS.get(self.fx.effect.id)
        if self.fx.effect.reactive and trigger is None:
            raise ValueError(f"{self.fx.effect.label} only runs while the app is open; the keyboard can "
                             "store fade, explosion and HyperX flame")
        loop = fx.Renderer(self.layout, self.leds, seed=0)  # a copy, so the live effect keeps running
        loop.configure(**vars(self.fx.settings))
        frames, frame_ms = loop.render_loop(max_frames=self.max_frames)
        frames = [self._paint(f) for f in frames]
        interval = max(0, min(255, round(frame_ms) - 16))  # longer loops play faster on the keyboard
        return frames, interval, trigger

    def _write_frames(self, slot: int, frames, interval: int, trigger: int | None, final_commit: bool = True,
                      pause: float = 0.0) -> None:
        """Frame packets (80 R G B), commit, then the timing and reactive-effect packets, commit."""
        packets = self.leds // 16
        self.set_value("save_lighting", 0)
        count = len(frames) * packets
        self._command(cmd_frames(slot), {9: count & 0xFF, 10: count >> 8}, erase=self.frame_erase_wait)
        for n, frame in enumerate(frames):
            for p in range(packets):
                packet = bytearray(64)
                for j in range(16):
                    packet[4 * j] = 0x80
                    packet[4 * j + 1:4 * j + 4] = bytes(frame[p * 16 + j])
                self._data(bytes(packet))
            self.set_value("save_lighting", round(100 * (n + 1) / len(frames)))
        self._commit()
        time.sleep(pause)
        self._command(cmd_lighting_config(slot), {9: 2})
        timing = bytearray(64)
        timing[0], timing[59], timing[61] = 8, interval, len(frames)
        self._data(bytes(timing), tail=True)
        react = bytearray(64)
        if trigger:
            color = bytes(self.color or (255, 255, 255))
            react[0], react[1:4], react[5:8] = trigger, color, color
            react[59] = round((100 - self.fx.settings.speed) * 255 / 99)
        self._data(bytes(react), tail=True)
        self._commit(verify=final_commit)

    def factory_reset(self) -> None:
        """NGENUITY's ResetToDefault: forget the synced presets of slots 0-2, then command FD."""
        for slot in range(3):
            self._command(cmd_erase_sync(slot), {9: 2})
            self._data()
            self._data(tail=True)
            self._commit()
        self._send(bytearray([0, 0x04, CMD_RESET] + [0] * 62), 0)
        time.sleep(1.0)  # NGENUITY waits for the acknowledgement and then one more second
        reply = self.node.get_feature(0, 65)
        if reply[2] == CMD_RESET and reply[4] == 1:
            self._commit()
        self.remap, self.macros = {}, {}
        self.set_value("remap", {})
        self.set_value("macros", {})
        self.poll()



# ------------------------------------------------------------------ models
ANSI_ISO = {"ansi": "ANSI", "iso": "ISO"}
FULL_SIZE = {"104": "104 keys", "105": "105 keys", "106": "106 keys", "108": "108 keys"}

class AlloyOrigins65(NgenuityKeyboard):
    name = "HyperX Alloy Origins 65"
    support = Support.VERIFIED
    ids = ((0x03F0, 0x038F, ""),)
    model = "origins65"
    layout_names = ANSI_ISO
    controls = model_controls(layouts("origins65"), ANSI_ISO, 78, "list", reset=True, verified=True)
    sources = ("NGENUITY Legacy 2.38, NGenuity2.Devices.Keyboard.Origins65 (static analysis)",
               "https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/1739")
    ISO = frozenset({59, 60, 61, 62, 63, 67, 68, 73, 74, 75})  # anything else: ANSI, as in NGENUITY

    def layout_for(self, country: int) -> str:
        return "iso" if country in self.ISO else "ansi"


class AlloyOrigins60(NgenuityKeyboard):
    """Like the 65, but an 8-byte key matrix of 144 slots, the Fn layer at +72, Fn lock as a key
    action, macros without the 18/19 framing, and profile byte [16] always 1."""
    name = "HyperX Alloy Origins 60"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x1734, ""), (0x03F0, 0x0C8E, ""))
    model = "origins60"
    layout_names = ANSI_ISO
    matrix_slots, matrix_entry = 144, 8
    fn_layer, fn_lock = 72, "matrix"
    ap_profile_id = 3
    profile_fixed = {15: 1}  # NGENUITY's ProfileAlloyOrigins60.ToBytes writes [16] = 1 (65-byte offset)
    hardware_brightness = False
    matrix_commit_verified = False
    controls = model_controls(layouts("origins60"), ANSI_ISO, 72, "matrix", reset=True, verified=False)
    sources = ("NGENUITY Legacy 2.38, NGenuity2.Devices.Keyboard.Origins60 (static analysis)",
               "https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/1617", "https://github.com/EriksRemess/hyperrust")
    ISO = frozenset({40, 41, 42, 43, 44, 48, 49, 54, 55, 56})

    def layout_for(self, country: int) -> str:
        return "iso" if country in self.ISO else "ansi"

    def _write_macros(self, slot: int, macros: list[list[MacroEvent]]) -> None:
        """Origins 60: 25 with the chunk count (erases), the chunks, 02 with AA 55."""
        table = encode_macros(macros)
        chunks = [table[i:i + 64] for i in range(0, len(table), 64)]
        self._command(cmd_macros(slot), {9: len(chunks)}, erase=self.macro_erase_wait)
        for chunk in chunks:
            self._data(chunk)
        self._commit(tail=True)


class _FullSize(NgenuityKeyboard):
    """Alloy Origins and Elite 2: 144 LEDs in 9 packets, a 144-slot key matrix without Fn layer, Fn
    key or Fn lock, at most 110 saved frames. NGENUITY allows the frame erase 3 s on these."""
    leds = 144
    max_frames = 110
    matrix_slots = 144
    fn_layer, fn_key, fn_lock = None, False, None
    hardware_brightness = False
    matrix_commit_verified = False
    frame_erase_wait, macro_erase_wait = 3.0, 1.0
    layout_names = FULL_SIZE

    def layout_for(self, country: int) -> str:
        if country < 2 or country in (18, 24, 26, 27, 28):
            return "104"
        if 2 <= country <= 6 or country in (19, 20, 29, 30, 31):
            return "105"
        return {7: "106", 8: "108"}.get(country, "104")  # NGENUITY has no layout for other codes


class AlloyOrigins(_FullSize):
    """Wants a keep-alive (E0) every half second while streaming and before key-matrix, macro and
    live-profile writes; saves lighting with a 2 s pause and a closing F0."""
    name = "HyperX Alloy Origins"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16E5, ""), (0x03F0, 0x0591, ""))
    model = "origins"
    controls = model_controls(layouts("origins"), FULL_SIZE, None, None, reset=False, verified=False)
    sources = ("NGENUITY Legacy 2.38, KeyboardAlloyOrigins / CMDKBAlloyOrigins* (static analysis)",
               "https://gitlab.com/CalcProgrammer1/OpenRGB", "https://github.com/Shehtman/hyperx-studio")
    _last_keepalive = 0.0

    def _before_write(self) -> None:
        self._command(CMD_KEEPALIVE)

    def keepalive(self) -> None:
        now = time.monotonic()
        if self.streaming and now - self._last_keepalive >= 0.5:
            buf = bytearray(65)
            buf[1], buf[2] = 0x04, CMD_KEEPALIVE
            self.node.set_feature(bytes(buf))
            self._last_keepalive = now
        super().keepalive()

    def _write_macros(self, slot: int, macros: list[list[MacroEvent]]) -> None:
        """Alloy Origins: 18; keep-alive; 25 with the chunk count (erases); chunks; 02 with AA 55; 19."""
        table = encode_macros(macros)
        chunks = [table[i:i + 64] for i in range(0, len(table), 64)]
        self._command(CMD_MACRO_BEGIN, verify=False)
        self._before_write()
        self._command(cmd_macros(slot), {9: len(chunks)}, erase=self.macro_erase_wait)
        for chunk in chunks:
            self._data(chunk)
        self._commit(tail=True)
        self._command(CMD_MACRO_END, verify=False)

    def save_lighting(self) -> None:
        """Alloy Origins: the slot's keymap first, frames (2 s pause), F0, then 57, 27+16s and 67."""
        slot = min(self.profile[0], 2)
        frames, interval, trigger = self._render_saved()
        self.write_keymap(slot)
        self._write_frames(slot, frames, interval, trigger, final_commit=False, pause=2.0)
        time.sleep(0.02)
        self._command(CMD_APPLY_SYNC, verify=False)
        time.sleep(1.0)
        profile = bytearray(self.profile)
        profile[0] = slot
        self._store_profile(cmd_profile_set(ACTIVE_SLOT), profile)
        self._store_profile(cmd_profile_set(slot), profile)
        self._store_live(self.profile)
        self.set_value("save_lighting", None)


class AlloyElite2(_FullSize):
    """Wraps the key-matrix write in 19 … 18, keeps 3 in the live profile's id byte and doesn't
    store the active profile (57) when saving lighting. LEDs 126-143 are the light bar."""
    name = "HyperX Alloy Elite 2"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x1711, ""), (0x03F0, 0x058F, ""))
    model = "elite2"
    ap_profile_id = 3
    controls = model_controls(layouts("elite2"), FULL_SIZE, None, None, reset=False, verified=False)
    sources = ("NGENUITY Legacy 2.38, KeyboardAlloyEliteII / CMDKBAlloyEliteII* (static analysis)",
               "https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/427")

    def _write_matrix(self, slot: int, matrix: bytes) -> None:
        self._command(CMD_MACRO_END, verify=False)  # NGENUITY does 19 … 18 here; what for is unknown
        super()._write_matrix(slot, matrix)
        self._command(CMD_MACRO_BEGIN, verify=False)

    def _write_macros(self, slot: int, macros: list[list[MacroEvent]]) -> None:
        """Elite 2: 18; 25 with the chunk count (erases); chunks; 02 with AA 55; 19."""
        table = encode_macros(macros)
        chunks = [table[i:i + 64] for i in range(0, len(table), 64)]
        self._command(CMD_MACRO_BEGIN, verify=False)
        self._command(cmd_macros(slot), {9: len(chunks)}, erase=self.macro_erase_wait)
        for chunk in chunks:
            self._data(chunk)
        self._commit(tail=True)
        self._command(CMD_MACRO_END, verify=False)

    def save_lighting(self) -> None:
        """Elite 2: frames, the slot's profile, the slot's keymap, the live profile."""
        slot = min(self.profile[0], 2)
        self._write_frames(slot, *self._render_saved())
        time.sleep(1.0)
        profile = bytearray(self.profile)
        profile[0] = slot
        self._store_profile(cmd_profile_set(slot), profile)
        self.write_keymap(slot)
        self._store_live(self.profile)
        self.set_value("save_lighting", None)


MODELS = (AlloyOrigins65, AlloyOrigins60, AlloyOrigins, AlloyElite2)
