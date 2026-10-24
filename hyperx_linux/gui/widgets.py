"""One builder per control type: returns (row widget, update(value) function)."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import controls as C  # noqa: E402
from ..i18n import _  # noqa: E402

DEBOUNCE_MS = 250


class Guard:
    """Set while the UI is being updated from the device, so handlers don't echo writes back."""

    def __init__(self):
        self.active = False

    def __enter__(self):
        self.active = True

    def __exit__(self, *exc):
        self.active = False


class ScrollPassthrough:
    """Mouse wheel over sliders/spin buttons scrolls the page instead of changing the value."""

    def __init__(self):
        self.scrolled: Gtk.ScrolledWindow | None = None

    def attach(self, widget: Gtk.Widget) -> None:
        ctl = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
        ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)  # before the widget's own handler
        ctl.connect("scroll", self._on_scroll)
        widget.add_controller(ctl)

    def _on_scroll(self, ctl, _dx, dy):
        if self.scrolled is None:
            return False
        adj = self.scrolled.get_vadjustment()
        if ctl.get_unit() == Gdk.ScrollUnit.WHEEL:
            dy *= adj.get_page_size() ** (2 / 3)  # same step as GtkScrolledWindow
        adj.set_value(adj.get_value() + dy)
        return True


def debounce(fn: Callable, ms: int = DEBOUNCE_MS) -> Callable:
    timer = 0

    def call(*args):
        nonlocal timer
        if timer:
            GLib.source_remove(timer)

        def fire():
            nonlocal timer
            timer = 0
            fn(*args)
            return False
        timer = GLib.timeout_add(ms, fire)
    return call


Setter = Callable[[str, object, bool], None]  # (control id, value, live)


def toggle(c: C.Toggle, guard: Guard, set_: Setter, _sp):
    row = Adw.SwitchRow(title=_(c.title), subtitle=_(c.subtitle))
    row.connect("notify::active", lambda r, _p: guard.active or set_(c.id, r.get_active(), False))

    def update(v):
        if v is not None:
            row.set_active(bool(v))
    return row, update


def range_(c: C.Range, guard: Guard, set_: Setter, sp: ScrollPassthrough):
    unit = f" {c.unit}" if c.unit else ""
    if (c.max - c.min) / c.step > 120:  # big ranges (DPI): spin button
        row = Adw.SpinRow.new_with_range(c.min, c.max, c.step)
        row.set_title(_(c.title))
        row.set_subtitle(_(c.subtitle))
        sp.attach(row)
        send = debounce(lambda v: set_(c.id, v, False), 400)
        row.connect("notify::value", lambda r, _p: guard.active or send(type(c.step)(r.get_value())))

        def update(v):
            if v is not None:
                row.set_value(v)
        return row, update

    row = Adw.ActionRow(title=_(c.title), subtitle=_(c.subtitle))
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, c.min, c.max, c.step)
    scale.set_size_request(200, -1)
    scale.set_valign(Gtk.Align.CENTER)
    scale.set_draw_value(True)
    scale.set_digits(0 if float(c.step).is_integer() else 1)
    scale.set_format_value_func(lambda s, v: f"{v:g}{unit}")
    if c.min < 0 < c.max:
        scale.add_mark(0, Gtk.PositionType.BOTTOM, None)
    sp.attach(scale)
    send = debounce(lambda v: set_(c.id, v, False))
    scale.connect("value-changed", lambda s: guard.active or send(
        int(round(s.get_value())) if float(c.step).is_integer() else s.get_value()))
    row.add_suffix(scale)

    def update(v):
        if v is not None:
            scale.set_value(v)
    return row, update


def choice(c: C.Choice, guard: Guard, set_: Setter, _sp):
    values = [v for v, _l in c.options]
    model = Gtk.StringList.new([_(lbl) for _v, lbl in c.options])
    row = Adw.ComboRow(title=_(c.title), subtitle=_(c.subtitle), model=model)

    def changed(r, _p):
        i = r.get_selected()
        if not guard.active and 0 <= i < len(values):
            set_(c.id, values[i], False)
    row.connect("notify::selected", changed)

    def update(v):
        if v is None:
            return
        if v not in values:  # value set outside the app: show it instead of lying
            values.append(v)
            model.append(_(c.label(v)))
        row.set_selected(values.index(v))
    return row, update


def color(c: C.Color, guard: Guard, set_: Setter, _sp):
    row = Adw.ActionRow(title=_(c.title), subtitle=_(c.subtitle))
    button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), valign=Gtk.Align.CENTER)
    row.add_suffix(button)
    send = debounce(lambda rgb: set_(c.id, rgb, False))

    def changed(b, _p):
        if guard.active:
            return
        rgba = b.get_rgba()
        send((round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255)))
    button.connect("notify::rgba", changed)

    def update(v):
        if v is not None:
            rgba = Gdk.RGBA()
            rgba.red, rgba.green, rgba.blue, rgba.alpha = v[0] / 255, v[1] / 255, v[2] / 255, 1.0
            button.set_rgba(rgba)
    return row, update


def info(c: C.Info, _guard, _set, _sp):
    row = Adw.ActionRow(title=_(c.title), subtitle="—", subtitle_selectable=True)
    row.add_css_class("property")

    def update(v):
        if v is not None:
            row.set_subtitle(_(str(v)))
    return row, update


def equalizer(c: C.Equalizer, guard: Guard, set_: Setter, sp: ScrollPassthrough, saved_preset=None,
              on_preset=None):
    """Preset row + a card of vertical sliders. Returns (box, update)."""
    custom = _("Custom")
    names = [n for n, _g in c.presets] + [custom]
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    group = Adw.PreferencesGroup()
    preset = Adw.ComboRow(title=_(c.title), model=Gtk.StringList.new([_(n) for n in names]))
    group.add(preset)
    box.append(group)

    card = Gtk.Box(spacing=2, homogeneous=True, css_classes=["card"])
    scales: list[Gtk.Scale] = []
    for i, hz in enumerate(c.bands_hz):
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["eq-band"],
                      margin_top=12, margin_bottom=10)
        if i == 0:
            col.set_margin_start(6)
        elif i == len(c.bands_hz) - 1:
            col.set_margin_end(10)
        s = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, c.min_db, c.max_db, c.step_db)
        s.set_inverted(True)
        s.set_has_origin(False)
        s.set_size_request(-1, 170)
        s.set_draw_value(True)
        s.set_value_pos(Gtk.PositionType.TOP)
        s.set_digits(1)
        s.set_value(0)
        s.add_mark(0, Gtk.PositionType.RIGHT, None)
        sp.attach(s)
        col.append(s)
        col.append(Gtk.Label(label=f"{hz // 1000}k" if hz >= 1000 else str(hz), css_classes=["dim-label"]))
        card.append(col)
        scales.append(s)
    box.append(card)

    def gains():
        return [s.get_value() for s in scales]

    def set_scales(values):
        with guard:
            for s, g in zip(scales, values):
                s.set_value(g)

    def mark(name, changed_by_user):
        with guard:
            preset.set_selected(names.index(name if name in names else custom))
        preset.set_subtitle(_("Re-applied on reconnect") if changed_by_user else _("Factory (not changed yet)"))

    current = {"preset": saved_preset}
    send_live = debounce(lambda: set_(c.id, gains(), True))

    def on_slider(_s):
        if guard.active:
            return
        current["preset"] = None
        mark(custom, True)
        if on_preset:
            on_preset(None)
        send_live()

    for s in scales:
        s.connect("value-changed", on_slider)

    def on_preset_selected(r, _p):
        if guard.active:
            return
        name = names[r.get_selected()]
        if name == custom:
            return
        values = list(dict(c.presets)[name])
        current["preset"] = name
        set_scales(values)
        mark(name, True)
        if on_preset:
            on_preset(name)
        set_(c.id, values, False)
    preset.connect("notify::selected", on_preset_selected)

    mark(saved_preset or custom, False)

    def update(v):
        if v is None:
            return
        set_scales(v)
        mark(current["preset"] or custom, True)
    return box, update


BUILDERS = {
    C.Toggle: toggle,
    C.Range: range_,
    C.Choice: choice,
    C.Color: color,
    C.Info: info,
}
