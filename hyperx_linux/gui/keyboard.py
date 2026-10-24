"""The keyboard as NGENUITY shows it: a live drawing of the keys with the light the keyboard is
showing, painted by clicking or dragging over it (Lighting), or clicked to pick a key and give it an
action from a page of keycaps (Keys). The geometry comes from the controls (C.KeyGeometry)."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Graphene, Gsk, Gtk, Pango  # noqa: E402

from .. import controls as C  # noqa: E402
from .. import effects as fx  # noqa: E402
from .. import keymap  # noqa: E402
from ..i18n import _  # noqa: E402
from . import compat  # noqa: E402
from . import theme  # noqa: E402

SHORT = {
    "esc": "Esc", "backspace": "⌫", "tab": "Tab", "capslock": "Caps", "enter": "Enter", "lshift": "Shift",
    "rshift": "Shift", "lctrl": "Ctrl", "rctrl": "Ctrl", "lalt": "Alt", "ralt": "Alt Gr", "lsuper": "Super",
    "rsuper": "Super", "menu": "Menu", "space": "", "fn": "Fn", "delete": "Del", "insert": "Ins", "home": "Home",
    "end": "End", "pageup": "PgUp", "pagedown": "PgDn", "printscreen": "PrtSc", "scrolllock": "ScrLk",
    "pause": "Pause", "numlock": "Num", "up": "↑", "down": "↓", "left": "←", "right": "→", "nonus-hash": "#",
    "nonus-backslash": "\\", "kp-enter": "Enter", "kp-slash": "/", "kp-asterisk": "*", "kp-minus": "−",
    "kp-plus": "+", "kp-period": ".", "media-play-pause": "Play", "media-next": "Next", "media-previous": "Prev",
    "media-mute": "Mute", "media-volume-up": "Vol+", "media-volume-down": "Vol−", "game-mode": "Game",
    "brightness-up": "☀+", "brightness-down": "☀−", "intl-yen": "¥", "intl-ro": "ろ", "intl-muhenkan": "無変換",
    "intl-henkan": "変換", "intl-kana": "かな",
}
QUICK = (  # NGENUITY's QuickSelect groups
    ("WASD", ("w", "a", "s", "d")),
    ("QWER", ("q", "w", "e", "r")),
    ("Numbers", tuple("1234567890")),
    ("Arrows", ("up", "down", "left", "right")),
    ("Functions", tuple(f"f{i}" for i in range(1, 13))),
)
ACCENT = (0.816, 0.133, 0.224)  # NGENUITY's ColorBrandHyperX, #d02239
FONT = "Exo 2"


def short_label(key_id: str) -> str:
    if key_id.startswith(("led-", "lightbar-")):
        return ""
    if key_id in SHORT:
        return SHORT[key_id]
    if key_id.startswith("kp-"):
        return key_id[3:]
    label = keymap.key_label(key_id)
    return label if len(label) <= 6 else label[:5] + "…"


def _rgb(hex_text: str) -> tuple[float, float, float]:
    t = hex_text.lstrip("#")
    return int(t[0:2], 16) / 255, int(t[2:4], 16) / 255, int(t[4:6], 16) / 255


def _rgba(hex_text: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()  # older PyGObject has no keyword constructor for it
    rgba.parse(hex_text)
    return rgba


def _hex(rgba: Gdk.RGBA) -> str:
    return "#%02x%02x%02x" % (round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))


class KeyboardCanvas(Gtk.Widget):
    """Keys as rounded keycaps lit with their colour. Modes: "view" (no input), "select" (a click picks
    one key; on_select gets {id}), "paint" (a click or a drag marquee hands the keys to on_paint)."""

    def __init__(self, mode: str = "view", natural_width: int = 560):
        super().__init__(hexpand=True, focusable=False)
        self.mode = mode
        self.natural_width = natural_width
        self.on_paint: list[Callable[[set[str]], None]] = []
        self.keys: list[tuple[str, float, float, float, float]] = []  # id, left, top, w, h
        self.colors: dict[str, tuple[float, float, float]] = {}
        self.marks: set[str] = set()  # small dot: e.g. remapped
        self.enabled: set[str] | None = None  # None: every key can be picked
        self.selected: set[str] = set()
        self.on_select: list[Callable[[set[str]], None]] = []
        self._band: tuple[float, float, float, float] | None = None
        self.live: Callable[[], dict | None] | None = None
        self._tick = None
        self._last_tick = 0
        self._box = (0.0, 0.0, 1.0, 1.0)
        self.set_cursor_from_name("crosshair") if mode == "paint" else None
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", self._drag_end)
        self.add_controller(drag)
        self._start = (0.0, 0.0)
        self._inside = False

    # ------------------------------------------------------------- content
    def set_keys(self, keys) -> None:
        """keys: ((id, centre x, centre y, w, h), …) in any unit."""
        self.keys = [(k, x - w / 2, y - h / 2, w, h) for k, x, y, w, h in keys]
        if self.keys:
            self._box = (min(k[1] for k in self.keys), min(k[2] for k in self.keys),
                         max(k[1] + k[3] for k in self.keys), max(k[2] + k[4] for k in self.keys))
        ids = {k[0] for k in self.keys}
        self.selected &= ids
        self.queue_resize()
        self.queue_draw()

    @property
    def aspect(self) -> float:
        x0, y0, x1, y1 = self._box
        return (x1 - x0) / max(1.0, y1 - y0)

    def select(self, ids, notify: bool = True) -> None:
        allowed = {k[0] for k in self.keys if self.enabled is None or k[0] in self.enabled}
        self.selected = set(ids) & allowed
        self.queue_draw()
        if notify:
            for fn in self.on_select:
                fn(set(self.selected))

    # ----------------------------------------------------------- geometry
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        """As wide as the page allows, as tall as the keyboard's proportions ask."""
        if orientation == Gtk.Orientation.HORIZONTAL:
            return min(240, self.natural_width), self.natural_width, -1, -1
        height = round((for_size if for_size > 0 else self.natural_width) / self.aspect)
        return min(height, 90), height, -1, -1  # may get shorter: it draws to fit, keeping proportions

    def _transform(self, width: int, height: int):
        x0, y0, x1, y1 = self._box
        pad = 4
        scale = min((width - 2 * pad) / max(1.0, x1 - x0), (height - 2 * pad) / max(1.0, y1 - y0))
        ox = (width - (x1 - x0) * scale) / 2 - x0 * scale
        oy = (height - (y1 - y0) * scale) / 2 - y0 * scale
        return scale, ox, oy

    def _rect(self, key, scale, ox, oy):
        _k, x, y, w, h = key
        gap = max(1.5, 2.5 * scale)
        return x * scale + ox + gap / 2, y * scale + oy + gap / 2, w * scale - gap, h * scale - gap

    def _key_at(self, px: float, py: float) -> str | None:
        scale, ox, oy = self._transform(self.get_width(), self.get_height())
        for key in self.keys:
            x, y, w, h = self._rect(key, scale, ox, oy)
            if x <= px <= x + w and y <= py <= y + h:
                return key[0]
        return None

    def _keys_in(self, ax, ay, bx, by) -> set[str]:
        scale, ox, oy = self._transform(self.get_width(), self.get_height())
        lx, rx, ty, by_ = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
        out = set()
        for key in self.keys:
            x, y, w, h = self._rect(key, scale, ox, oy)
            if x < rx and x + w > lx and y < by_ and y + h > ty:
                out.add(key[0])
        return out

    # -------------------------------------------------------------- input
    def _drag_begin(self, gesture, x, y):
        self._start = (x, y)
        self._band = None
        self._inside = 0 <= x <= self.get_width() and 0 <= y <= self.get_height()
        # claim our presses, deny the others: GTK 4.6 otherwise keeps sending the next press here
        gesture.set_state(Gtk.EventSequenceState.CLAIMED if self._inside and self.mode != "view"
                          else Gtk.EventSequenceState.DENIED)

    def _drag_update(self, _g, dx, dy):
        if self._inside and self.mode == "paint" and abs(dx) + abs(dy) > 6:
            sx, sy = self._start
            self._band = (sx, sy, sx + dx, sy + dy)
            self.queue_draw()

    def _drag_end(self, _g, dx, dy):
        if not self._inside:
            return
        sx, sy = self._start
        if self.mode == "paint":
            keys = self._keys_in(sx, sy, sx + dx, sy + dy) if self._band else {self._key_at(sx, sy)} - {None}
            self._band = None
            self.queue_draw()
            if keys:
                for fn in self.on_paint:
                    fn(keys)
            return
        if self.mode != "select":
            return
        key = self._key_at(sx, sy)
        if key is None:
            self.select(set())  # clicking outside the keys lets the key go, as in NGENUITY
        elif self.enabled is None or key in self.enabled:
            self.select({key})

    # ------------------------------------------------------------ drawing
    def set_live(self, source: Callable[[], dict | None] | None) -> None:
        """source() -> {key id: (r, g, b)} as the keyboard shows it now, or None when unknown. While
        the drawing is on screen it is redrawn 15 times a second, like NGENUITY's live preview."""
        self.live = source
        if source is not None and self._tick is None:
            self._tick = self.add_tick_callback(self._on_tick)

    def _on_tick(self, _widget, clock) -> bool:
        now = clock.get_frame_time()
        if now - self._last_tick >= 66_000:  # µs
            self._last_tick = now
            self.queue_draw()
        return True

    def do_snapshot(self, snapshot) -> None:
        """Drawn with GTK's own scene graph: no cairo needed in Python, and the GPU does the work."""
        if not self.keys:
            return
        width, height = self.get_width(), self.get_height()
        live = self.live() if self.live else None
        scale, ox, oy = self._transform(width, height)
        font = Pango.FontDescription.from_string(f"{FONT} Semi-Bold")
        cap, white = _rgba_f(0.105, 0.105, 0.11), _rgba_f(1, 1, 1)
        for key in self.keys:
            kid = key[0]
            x, y, w, h = self._rect(key, scale, ox, oy)
            disabled = self.enabled is not None and kid not in self.enabled
            rgb = live.get(kid) if live else None
            color = tuple(c / 255 for c in rgb) if rgb else self.colors.get(kid)
            lit = color is not None and max(color) > 0.04
            r = min(6.0, w / 4, h / 4)
            _fill(snapshot, x, y, w, h, r, cap)  # keycap
            _stroke(snapshot, x, y, w, h, r, 1, _rgba_f(1, 1, 1, 0.05 if disabled else 0.10))
            if lit:  # its light
                inset = max(1.5, min(w, h) * 0.08)
                _fill(snapshot, x + inset, y + inset, w - 2 * inset, h - 2 * inset, max(1.0, r - inset / 2),
                      _rgba_f(*color, 0.35 if disabled else 0.92))
            if kid in self.selected:
                _stroke(snapshot, x - 2, y - 2, w + 4, h + 4, r + 2, 2.2, white)
            label = short_label(kid)
            if label and h > 10:
                layout = self.create_pango_layout(label)
                size = min(h * 0.34, 14)
                font.set_absolute_size(size * Pango.SCALE)
                layout.set_font_description(font)
                tw, th = layout.get_pixel_size()
                if tw > w - 6 and tw > 0:  # "Home", "PgUp"… on narrow keys
                    font.set_absolute_size(max(6.0, size * (w - 6) / tw) * Pango.SCALE)
                    layout.set_font_description(font)
                    tw, th = layout.get_pixel_size()
                if lit:
                    lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                    ink = _rgba_f(*((0.05, 0.05, 0.05) if lum > 0.5 else (1, 1, 1)), 0.5 if disabled else 0.95)
                else:
                    ink = _rgba_f(1, 1, 1, 0.30 if disabled else 0.80)
                snapshot.save()
                snapshot.translate(_point(x + (w - tw) / 2, y + (h - th) / 2))
                snapshot.append_layout(layout, ink)
                snapshot.restore()
            if kid in self.marks and self.mode == "select":  # remapped
                _fill(snapshot, x + w - 9, y + 2.5, 6, 6, 3, _rgba_f(*ACCENT))
        if self._band:
            ax, ay, bx, by = self._band
            bx0, by0, bw, bh = min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay)
            _fill(snapshot, bx0, by0, bw, bh, 1, _rgba_f(1, 1, 1, 0.10))
            _stroke(snapshot, bx0, by0, bw, bh, 1, 1, _rgba_f(1, 1, 1, 0.7))


def _rgba_f(r, g, b, a=1.0) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.red, c.green, c.blue, c.alpha = r, g, b, a
    return c


def _point(x, y) -> Graphene.Point:
    return Graphene.Point().init(x, y)


def _rounded(x, y, w, h, r) -> Gsk.RoundedRect:
    rr = Gsk.RoundedRect()
    rr.init_from_rect(Graphene.Rect().init(x, y, max(0.0, w), max(0.0, h)), max(0.0, r))
    return rr


def _fill(snapshot, x, y, w, h, r, color: Gdk.RGBA) -> None:
    snapshot.push_rounded_clip(_rounded(x, y, w, h, r))
    snapshot.append_color(color, Graphene.Rect().init(x, y, max(0.0, w), max(0.0, h)))
    snapshot.pop()


def _stroke(snapshot, x, y, w, h, r, width, color: Gdk.RGBA) -> None:
    snapshot.append_border(_rounded(x, y, w, h, r), [width] * 4, [color] * 4)


class SwatchPicker(Gtk.Box):
    """NGENUITY's colour picker: its swatches plus any colour from a dialog; get_hex() / set_hex()."""

    def __init__(self, swatches):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=4, row_spacing=4,
                                max_children_per_line=12, min_children_per_line=6, homogeneous=True)
        self.append(self.flow)
        self.on_change: list[Callable[[str], None]] = []
        self._hex = swatches[0][1]
        self._buttons: dict[str, Gtk.ToggleButton] = {}
        group = None
        for name, hex_ in swatches:
            dot = Gtk.Box(css_classes=["hx-sw", f"hx-sw-{hex_.lstrip('#').lower()}"], halign=Gtk.Align.CENTER,
                          valign=Gtk.Align.CENTER)
            b = Gtk.ToggleButton(child=dot, css_classes=["hx-swatch", "flat"], tooltip_text=_(name))
            if group is None:
                group = b
            else:
                b.set_group(group)
            b.connect("toggled", lambda btn, hx=hex_: btn.get_active() and self._pick(hx))
            self._buttons[hex_] = b
            self.flow.append(b)
        row = Gtk.Box(spacing=8)
        self.custom = compat.color_button()
        self.custom.set_tooltip_text(_("Other color"))
        self.custom.connect("notify::rgba", lambda w, _p: self._pick(_hex(w.get_rgba()), from_custom=True))
        row.append(self.custom)
        self.label = Gtk.Label(css_classes=["hx-dim", "caption", "monospace"], xalign=0)
        row.append(self.label)
        self.append(row)
        self.set_hex(self._hex)

    def _pick(self, hex_: str, from_custom: bool = False) -> None:
        self._hex = hex_.lower()
        self.label.set_label(self._hex.upper())
        if from_custom:
            for b in self._buttons.values():
                b.set_active(False) if b.get_active() and self._buttons.get(self._hex) is not b else None
        for fn in self.on_change:
            fn(self._hex)

    def get_hex(self) -> str:
        return self._hex

    def set_hex(self, hex_: str) -> None:
        hex_ = hex_.lower()
        if hex_ in self._buttons:
            self._buttons[hex_].set_active(True)
        self._hex = hex_
        self.label.set_label(hex_.upper())


# ------------------------------------------------------------------ preview
class KeyboardPreview(Gtk.Box):
    """The keyboard on the page: a slot on top for the active feature's tools, then the drawing."""

    def __init__(self, layouts: C.KeyGeometry, live: Callable[[], dict | None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER)
        self.layouts = {name: keys for name, keys in layouts}
        self.top = Gtk.Box(halign=Gtk.Align.CENTER, height_request=34)
        self.append(self.top)
        self.canvas = KeyboardCanvas()
        self.canvas.set_live(live)
        self.append(Adw.Clamp(maximum_size=1040, child=self.canvas, margin_start=12, margin_end=12))
        self.tools: dict[str, Gtk.Widget] = {}
        self.modes: dict[str, str] = {}
        self.enabled: dict[str, set[str] | None] = {}
        self.layout_listeners: list[Callable[[set[str]], None]] = []
        self.set_layout(None)

    def set_layout(self, name) -> None:
        keys = self.layouts.get(name) or next(iter(self.layouts.values()), ())
        self.canvas.set_keys(keys)
        present = {k[0] for k in keys}
        for fn in self.layout_listeners:
            fn(present)

    def add_feature(self, fid: str, mode: str, tools: Gtk.Widget | None, enabled: set[str] | None = None) -> None:
        self.modes[fid] = mode
        self.enabled[fid] = enabled
        if tools is not None:
            self.tools[fid] = tools

    def set_feature(self, fid: str) -> None:
        mode = self.modes.get(fid, "view")
        self.canvas.mode = mode
        self.canvas.enabled = self.enabled.get(fid)
        self.canvas.set_cursor_from_name("crosshair" if mode == "paint" else None)
        if mode != "select":
            self.canvas.select(set(), notify=False)
            self.canvas.marks = set()
        while (child := self.top.get_first_child()) is not None:
            self.top.remove(child)
        if fid in self.tools:
            self.top.append(self.tools[fid])
        self.canvas.queue_draw()


def _pill(items) -> Gtk.Box:
    """NGENUITY's QuickSelect pill: labels separated by thin dividers."""
    pill = Gtk.Box(css_classes=["hx-pill"], valign=Gtk.Align.CENTER)
    for i, (label, fn) in enumerate(items):
        b = Gtk.Button(label=label, css_classes=["flat"])
        if i:
            sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
            b.bind_property("visible", sep, "visible", 2)  # SYNC_CREATE: the divider goes with its item
            pill.append(sep)
        b.connect("clicked", lambda _b, f=fn: f())
        pill.append(b)
    return pill


def _segmented(options, on_change) -> tuple[Gtk.Box, dict[str, Gtk.ToggleButton]]:
    box = Gtk.Box(css_classes=["hx-segmented"], valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
    buttons: dict[str, Gtk.ToggleButton] = {}
    for value, label in options:
        b = Gtk.ToggleButton(label=label)
        if buttons:
            b.set_group(next(iter(buttons.values())))
        b.connect("toggled", lambda btn, v=value: btn.get_active() and on_change(v))
        buttons[value] = b
        box.append(b)
    next(iter(buttons.values())).set_active(True)
    return box, buttons


def _brightness(ctx, c: C.Range) -> Gtk.Widget:
    """NGENUITY's brightness column: value on top, a vertical slider between the max and min icons."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["hx-section"], width_request=64)
    value = Gtk.Label(label="—", css_classes=["hx-section-title"])
    box.append(value)
    box.append(Gtk.Image(icon_name="display-brightness-symbolic", pixel_size=16))
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, c.min, c.max, c.step)
    scale.set_inverted(True)
    scale.set_vexpand(True)
    scale.set_draw_value(False)
    scale.set_halign(Gtk.Align.CENTER)
    ctx.sp.attach(scale)
    box.append(scale)
    box.append(Gtk.Image(icon_name="weather-clear-night-symbolic", pixel_size=14, css_classes=["hx-dim"]))
    from .widgets import debounce
    send = debounce(lambda v: ctx.set(c.id, v, False))

    def changed(s):
        value.set_label(f"{round(s.get_value())}%")
        if not ctx.guard.active:
            send(int(round(s.get_value())))
    scale.connect("value-changed", changed)

    def update(v):
        if v is not None:
            scale.set_value(v)
            value.set_label(f"{round(v)}%")
    ctx.register(c.id, update)
    if not ctx.can_write(c):
        box.set_sensitive(False)
    return box


def lights_panel(ctx, ctrls: list[C.Control], preview: KeyboardPreview) -> tuple[Gtk.Widget, Gtk.Widget | None]:
    """Brightness column | the effect and its settings | painting keys; quick groups over the drawing."""
    by_id = {c.id: c for c in ctrls}
    row = Gtk.Box(spacing=8)
    if "brightness" in by_id:
        row.append(_brightness(ctx, by_id["brightness"]))

    # the effect, showing only the settings it uses
    effect_rows: dict[str, Gtk.Widget] = {}
    for cid in ("effect", "color", "color2", "speed", "direction"):
        if cid in by_id:
            effect_rows[cid] = ctx.build(by_id[cid])
    from .page import rows_list, section  # noqa: PLC0415 (page imports this module)

    current_effect = {"id": "static"}

    def show_for(effect_id):
        current_effect["id"] = effect_id
        e = next((e for e in fx.EFFECTS if e.id == effect_id), None)
        if "color" in effect_rows:  # in "custom" it colours the keys that aren't painted
            effect_rows["color"].set_visible(effect_id == "custom" or (e is not None and e.id != "spectrum"))
        if "color2" in effect_rows:
            effect_rows["color2"].set_visible(e is not None and e.colors >= 2)
        if "speed" in effect_rows:
            effect_rows["speed"].set_visible(e is not None and e.id != "static")
        if "direction" in effect_rows:
            effect_rows["direction"].set_visible(e is not None and e.directional)
    ctx.register("effect", show_for)
    show_for("static")
    effect_box = [rows_list(list(effect_rows.values()))]
    if "save_lighting" in by_id:
        effect_box.append(rows_list([ctx.build(by_id["save_lighting"])]))
    row.append(section(_("Light effects"), *effect_box))

    extra = None
    colors = by_id.get("key_colors")
    if colors is not None:
        painted: dict[str, str] = {}
        tool = {"mode": "paint"}
        picker = SwatchPicker(theme.SWATCHES)

        def commit(new):
            painted.clear()
            painted.update(new)
            preview.canvas.colors = {k: _rgb(v) for k, v in painted.items()}
            preview.canvas.queue_draw()
            ctx.set(colors.id, dict(painted), False)

        def paint(keys):
            if current_effect["id"] != "custom":  # painted keys are their own effect, like NGENUITY's
                ctx.set("effect", "custom", False)
            if tool["mode"] == "erase":
                commit({k: v for k, v in painted.items() if k not in keys})
            else:
                commit({**painted, **{k: picker.get_hex() for k in keys}})
        preview.canvas.on_paint.append(paint)

        modes, _buttons = _segmented((("paint", _("Paint")), ("erase", _("Erase"))),
                                    lambda m: tool.__setitem__("mode", m))
        everything = Gtk.Button(label=_("Paint all"), css_classes=["hx-secondary"])
        everything.connect("clicked", lambda _b: paint({k[0] for k in preview.canvas.keys}))
        clear = Gtk.Button(label=_("Clear all"), css_classes=["hx-secondary"])
        clear.connect("clicked", lambda _b: commit({}))
        actions = Gtk.Box(spacing=6)
        actions.append(everything)
        actions.append(clear)
        hint = Gtk.Label(label=_("Click keys on the drawing, or drag over several. Painting switches to the "
                                 "Custom effect; pick another effect to see it on the whole keyboard."),
                         xalign=0, wrap=True, css_classes=["hx-dim", "caption"])
        paint_section = section(_("Paint keys"), modes, picker, hint, actions, scroll=False)
        paint_section.set_hexpand(False)
        paint_section.set_size_request(340, -1)
        row.append(paint_section)
        if not ctx.can_write(colors):
            paint_section.set_sensitive(False)

        quick_items = [(_("All"), lambda: paint({k[0] for k in preview.canvas.keys}))]
        for label, ids in QUICK:
            quick_items.append((_(label), lambda ids=ids: paint({k for k in ids if k in {x[0] for x in preview.canvas.keys}})))
        pill = _pill(quick_items)
        quick_buttons = [w for w in _children(pill) if isinstance(w, Gtk.Button)]

        def hide_missing(present):
            for button, (label, ids) in zip(quick_buttons[1:], QUICK):
                button.set_visible(set(ids) <= present)
        preview.layout_listeners.append(hide_missing)
        hide_missing({k[0] for k in preview.canvas.keys})
        preview.add_feature("lights", "paint", pill)

        def update(v):
            painted.clear()
            painted.update(v or {})
            preview.canvas.colors = {k: _rgb(val) for k, val in painted.items()}
            preview.canvas.queue_draw()
        ctx.register(colors.id, update)
    else:
        preview.add_feature("lights", "view", None)
    return row, extra


def _children(w: Gtk.Widget):
    c = w.get_first_child()
    while c is not None:
        yield c
        c = c.get_next_sibling()


def _keycap(label: str, tooltip: str, on_click, wide: bool = False) -> Gtk.Button:
    b = Gtk.Button(label=label, tooltip_text=tooltip, css_classes=["hx-keycap"], halign=Gtk.Align.START)
    if wide:
        b.set_size_request(104, 46)
    b.connect("clicked", lambda _b: on_click())
    return b


def keys_panel(ctx, ctrls: list[C.Control], preview: KeyboardPreview) -> Gtk.Widget:
    """Assignments: categories on the left, keycaps of the chosen category on the right; the key is
    picked on the drawing (and the layer above it), like NGENUITY's Keys tab."""
    from .page import rows_list, section  # noqa: PLC0415
    from .widgets import action_label  # noqa: PLC0415
    by_id = {c.id: c for c in ctrls}
    remap = next(c for c in ctrls if isinstance(c, C.KeyRemap))
    remappable = {k for k, _l in remap.keys}
    has_fn = any(k.startswith("fn+") for k in remappable)
    current: dict[str, str] = {}
    state = {"layer": "base"}
    canvas = preview.canvas

    def selected() -> str | None:
        if not canvas.selected:
            return None
        base = next(iter(canvas.selected))
        return f"fn+{base}" if state["layer"] == "fn" else base

    def assign(action: str):
        kid = selected()
        if kid is None:
            return
        new = {k: v for k, v in current.items() if k != kid}
        if action != "default":
            new[kid] = action
        ctx.set(remap.id, new, False)

    # header: what's selected and what it does now
    title = Gtk.Label(label=_("Click a key on the drawing"), xalign=0, css_classes=["hx-section-title"])
    now = Gtk.Label(xalign=0, css_classes=["hx-dim", "caption"])

    def show_selected(_sel=None):
        kid = selected()
        pages.set_sensitive(kid is not None and ctx.can_write(remap))
        if kid is None:
            title.set_label(_("Click a key on the drawing"))
            now.set_label("")
            return
        title.set_label(_(keymap.key_label(kid)))
        now.set_label(_("Now: {}").format(action_label(current[kid]) if kid in current else _("Original function")))
    canvas.on_select.append(show_selected)

    def marks():
        fn = state["layer"] == "fn"
        canvas.marks = {k[3:] if fn else k for k in current if k.startswith("fn+") == fn}
        canvas.queue_draw()

    # pages of keycaps
    pages = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True)
    flows: list[Gtk.FlowBox] = []

    def grid(items, wide=False) -> Gtk.Widget:
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=8, row_spacing=8,
                           min_children_per_line=4 if wide else 8, max_children_per_line=40, homogeneous=False,
                           valign=Gtk.Align.START, halign=Gtk.Align.START)  # GTK 4.6 needs the minimum
        for value, label, tip in items:
            flow.append(_keycap(label, tip, lambda v=value: assign(v), wide))
        flows.append(flow)
        return Gtk.ScrolledWindow(child=flow, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)

    search = Gtk.SearchEntry(placeholder_text=_("Search keys"), hexpand=False, width_request=260)
    key_items = [(k, short_label(k) or k, _(keymap.key_label(k))) for k in keymap.KEYS]
    key_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    key_page.append(search)
    key_grid = grid(key_items)
    key_page.append(key_grid)
    key_flow = flows[-1]

    def filter_keys(_e):
        text = search.get_text().strip().lower()
        for child, (k, label, tip) in zip(_children(key_flow), key_items):
            child.set_visible(not text or text in k or text in label.lower() or text in tip.lower())
    search.connect("search-changed", filter_keys)
    pages.add_named(key_page, "keys")
    pages.add_named(grid([(f"media:{k}", _(lbl), _(lbl)) for k, lbl in keymap.MEDIA_LABELS.items()], wide=True),
                    "media")
    pages.add_named(grid([(f"mouse:{k}", _(lbl), _(lbl)) for k, lbl in keymap.MOUSE_LABELS.items()], wide=True),
                    "mouse")
    special = [("default", _("Original"), _("Original function")), ("disabled", _("Disabled"), _("Disabled"))]
    if has_fn:  # models with an Fn layer also let a key be Fn or lock it
        special += [("fn", "Fn", "Fn"), ("fn-lock", _("Fn lock"), _("Fn lock"))]
    special_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    special_page.append(grid(special, wide=True))
    if "fn_lock" in by_id:
        special_page.append(rows_list([ctx.build(by_id["fn_lock"])]))
    pages.add_named(special_page, "special")

    # macros: assign one, edit them, record one
    macro_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    macro_flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=8, row_spacing=8,
                             max_children_per_line=12, valign=Gtk.Align.START)
    macro_page.append(macro_flow)
    macro_rows = []
    for cid in ("macro_record", "macros"):
        if cid in by_id:
            macro_rows.append(ctx.build(by_id[cid]))
    macro_page.append(rows_list(macro_rows))
    macros_row = macro_rows[-1] if "macros" in by_id else None
    recorder_row = macro_rows[0] if "macro_record" in by_id else None
    if macros_row is not None and recorder_row is not None:
        recorder_row.on_result.append(macros_row.set_steps)

    def set_macros(names):
        while (child := macro_flow.get_first_child()) is not None:
            macro_flow.remove(child)
        for n in names:
            macro_flow.append(_keycap(n, _("Macro: {}").format(n), lambda n=n: assign(f"macro:{n}"), wide=True))
    if macros_row is not None:
        macros_row.on_change.append(set_macros)
    pages.add_named(Gtk.ScrolledWindow(child=macro_page, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER),
                    "macro")

    game = [ctx.build(by_id[cid]) for cid in ("game_mode", "block_alt_tab", "block_alt_f4", "block_shift_tab",
                                              "block_ctrl_esc") if cid in by_id]
    categories = [("keys", _("Keys & buttons"), "input-keyboard-symbolic"),
                  ("media", _("Media"), "audio-x-generic-symbolic"),
                  ("mouse", _("Mouse"), "input-mouse-symbolic"),
                  ("macro", _("Macro"), "media-record-symbolic"),
                  ("special", _("Special"), "starred-symbolic")]
    if game:
        categories.append(("game", _("Game mode"), "applications-games-symbolic"))

    # left: the categories, and resetting the layer
    cat_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["hx-tree"])
    for cid, label, icon in categories:
        r = Gtk.ListBoxRow()
        b = Gtk.Box(spacing=8)
        b.append(Gtk.Image(icon_name=icon, pixel_size=16))
        b.append(Gtk.Label(label=label, xalign=0))
        r.set_child(b)
        r.cid = cid
        cat_list.append(r)
    reset = Gtk.Button(label=_("Reset layer"), css_classes=["hx-secondary"], valign=Gtk.Align.END, vexpand=True)

    def reset_layer(_b):
        fn = state["layer"] == "fn"
        ctx.set(remap.id, {k: v for k, v in current.items() if k.startswith("fn+") != fn}, False)
    reset.connect("clicked", reset_layer)
    left = section(_("Assignments"), cat_list, reset, scroll=False)
    left.set_hexpand(False)
    left.set_size_request(200, -1)

    # right: the selected key and the keycaps of the category (or the game-mode switches)
    right_stack = Gtk.Stack(vexpand=True)
    picker = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    head.append(title)
    head.append(now)
    picker.append(head)
    picker.append(pages)
    right_stack.add_named(picker, "assign")
    if game:
        right_stack.add_named(rows_list(game), "game")
    right = section("", right_stack, scroll=False)

    def on_category(_lb, r):
        if r is None:
            return
        if r.cid == "game":
            right_stack.set_visible_child_name("game")
        else:
            right_stack.set_visible_child_name("assign")
            pages.set_visible_child_name(r.cid)
    cat_list.connect("row-selected", on_category)
    cat_list.select_row(cat_list.get_row_at_index(0))

    # the layer switch over the drawing
    tools = None
    if has_fn:
        def on_layer(v):
            state["layer"] = v
            marks()
            show_selected()
        tools, _b = _segmented((("base", _("Base layer")), ("fn", _("Fn layer"))), on_layer)
    preview.add_feature("keys", "select", tools, {k for k in remappable if not k.startswith("fn+")})

    def update(v):
        current.clear()
        current.update(v or {})
        marks()
        show_selected()
    ctx.register(remap.id, update)
    show_selected()
    if not ctx.can_write(remap):
        tip = _("Not confirmed on this model yet: enable experimental drivers in Preferences to use it")
        right.set_tooltip_text(tip)
        left.set_tooltip_text(tip)
        reset.set_sensitive(False)

    row = Gtk.Box(spacing=8)
    row.append(left)
    row.append(right)
    return row
