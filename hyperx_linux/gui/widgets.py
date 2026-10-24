"""One builder per control type: returns (row widget, update(value) function)."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import controls as C  # noqa: E402
from .. import keymap  # noqa: E402
from ..i18n import _  # noqa: E402
from . import compat  # noqa: E402

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
        scrolled = ctl.get_widget().get_ancestor(Gtk.ScrolledWindow) or self.scrolled
        if scrolled is None:
            return True  # nothing to scroll, but the wheel still never moves the slider
        adj = scrolled.get_vadjustment()
        if compat.wheel_units(ctl):
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
    row, switch = compat.switch_row(_(c.title), _(c.subtitle))
    switch.connect("notify::active", lambda w, _p: guard.active or set_(c.id, w.get_active(), False))

    def update(v):
        if v is not None:
            switch.set_active(bool(v))
    return row, update


def range_(c: C.Range, guard: Guard, set_: Setter, sp: ScrollPassthrough):
    unit = f" {c.unit}" if c.unit else ""
    if (c.max - c.min) / c.step > 120:  # big ranges (DPI): spin button
        row, spin = compat.spin_row(_(c.title), _(c.subtitle), c.min, c.max, c.step)
        sp.attach(row)
        send = debounce(lambda v: set_(c.id, v, False), 400)
        spin.connect("notify::value", lambda w, _p: guard.active or send(type(c.step)(w.get_value())))

        def update(v):
            if v is not None:
                spin.set_value(v)
        return row, update

    # NGENUITY's slider: the title with the value on the right, the slider full width below
    row = Gtk.ListBoxRow(activatable=False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=8, margin_bottom=6,
                  margin_start=12, margin_end=12)
    head = Gtk.Box(spacing=8)
    head.append(Gtk.Label(label=_(c.title), xalign=0, hexpand=True, wrap=True))
    value = Gtk.Label(xalign=1, css_classes=["dim-label", "numeric"])
    head.append(value)
    box.append(head)
    if c.subtitle:
        box.append(Gtk.Label(label=_(c.subtitle), xalign=0, wrap=True, css_classes=["dim-label", "caption"]))
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, c.min, c.max, c.step)
    scale.set_hexpand(True)
    scale.set_draw_value(False)
    scale.set_digits(0 if float(c.step).is_integer() else 1)
    if c.min < 0 < c.max:
        scale.add_mark(0, Gtk.PositionType.BOTTOM, None)
    sp.attach(scale)
    box.append(scale)
    row.set_child(box)
    send = debounce(lambda v: set_(c.id, v, False))

    def changed(s):
        value.set_label(f"{s.get_value():g}{unit}")
        if not guard.active:
            send(int(round(s.get_value())) if float(c.step).is_integer() else s.get_value())
    scale.connect("value-changed", changed)

    def update(v):
        if v is not None:
            scale.set_value(v)
            value.set_label(f"{float(v):g}{unit}")
    return row, update


def choice(c: C.Choice, guard: Guard, set_: Setter, _sp):
    """NGENUITY's dropdown: the title above, the list full width below (it fits narrow sections)."""
    values = [v for v, _l in c.options]
    model = Gtk.StringList.new([_(lbl) for _v, lbl in c.options])
    row = Gtk.ListBoxRow(activatable=False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin_top=8, margin_bottom=8,
                  margin_start=12, margin_end=12)
    box.append(Gtk.Label(label=_(c.title), xalign=0, wrap=True))
    if c.subtitle:
        box.append(Gtk.Label(label=_(c.subtitle), xalign=0, wrap=True, css_classes=["dim-label", "caption"]))
    dropdown = Gtk.DropDown(model=model, hexpand=True)
    box.append(dropdown)
    row.set_child(box)

    def changed(d, _p):
        i = d.get_selected()
        if not guard.active and 0 <= i < len(values):
            set_(c.id, values[i], False)
    dropdown.connect("notify::selected", changed)

    def update(v):
        if v is None:
            return
        if v not in values:  # value set outside the app: show it instead of lying
            values.append(v)
            model.append(_(c.label(v)))
        dropdown.set_selected(values.index(v))
    return row, update


def color(c: C.Color, guard: Guard, set_: Setter, _sp):
    row = Adw.ActionRow(title=_(c.title), subtitle=_(c.subtitle))
    button = compat.color_button()
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
    row = compat.property_row(_(c.title), "—")

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


def action(c: C.Action, _guard: Guard, set_: Setter, _sp):
    row = Adw.ActionRow(title=_(c.title), subtitle=_(c.subtitle))
    button = Gtk.Button(label=_(c.button), valign=Gtk.Align.CENTER)
    if c.confirm:
        button.add_css_class("destructive-action")
    row.add_suffix(button)

    def clicked(_b):
        if c.confirm:
            compat.confirm(row, _(c.title), _(c.confirm), _(c.button), _("Cancel"), lambda: set_(c.id, None, False))
        else:
            set_(c.id, None, False)
    button.connect("clicked", clicked)

    def update(v):  # progress while it runs, None when done
        busy = isinstance(v, int)
        button.set_sensitive(not busy)
        row.set_subtitle(_("Working… {}%").format(v) if busy else _(c.subtitle))
    return row, update


def _searchable(dropdown: Gtk.DropDown) -> Gtk.DropDown:
    try:
        dropdown.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        dropdown.set_enable_search(True)
    except TypeError:
        pass  # PyGObject < 3.44 can't build GtkExpressions: the list still works, without search
    return dropdown


def action_label(text: str) -> str:
    """Remap action text -> what the user reads ('media:mute' -> 'Media: Mute')."""
    a = keymap.parse_action(text)
    if a.kind == "disabled":
        return _("Disabled")
    if a.kind == "fn":
        return "Fn"
    if a.kind == "fn-lock":
        return _("Fn lock") + ("" if a.usage == 0xFFFFFF else f" (#{a.usage:06x})")
    if a.kind == "media":
        return _("Media: {}").format(_(keymap.MEDIA_LABELS[text.split(":", 1)[1].strip().lower()]))
    if a.kind == "mouse":
        return _("Mouse: {}").format(_(keymap.MOUSE_LABELS[a.name]))
    if a.kind == "macro":
        return _("Macro: {}").format(a.name)
    return " + ".join(_(keymap.key_label(k)) for k in keymap.format_action(a).split("+"))


def _action_choices(macros: list[str]) -> list[tuple[str, str]]:
    return ([("disabled", _("Disabled")), ("fn", "Fn"), ("fn-lock", _("Fn lock"))]
            + [(f"macro:{m}", _("Macro: {}").format(m)) for m in macros]
            + [(f"media:{k}", _("Media: {}").format(_(lbl))) for k, lbl in keymap.MEDIA_LABELS.items()]
            + [(f"mouse:{k}", _("Mouse: {}").format(_(lbl))) for k, lbl in keymap.MOUSE_LABELS.items()]
            + [(k, _(keymap.key_label(k))) for k in keymap.KEYS])


def key_remap(c: C.KeyRemap, _guard: Guard, set_: Setter, _sp):
    """Expander with one row per remapped key and a key -> action picker at the end; with a drawing
    of the keyboard when the driver gives one."""
    current: dict[str, str] = {}
    keys = [k for k, _label in c.keys]
    choices = _action_choices([])
    row = Adw.ExpanderRow(title=_(c.title), subtitle=_(c.subtitle))
    key_dd = _searchable(Gtk.DropDown.new_from_strings([_(keymap.key_label(k)) for k in keys]))
    action_model = Gtk.StringList.new([label for _v, label in choices])
    action_dd = _searchable(Gtk.DropDown(model=action_model))
    add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Add"), valign=Gtk.Align.CENTER)
    box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
    for w in (key_dd, Gtk.Label(label="→"), action_dd, add):
        box.append(w)
    adder = Adw.ActionRow(title=_("Remap a key"))
    adder.add_suffix(box)
    shown: list[Gtk.Widget] = []

    def on_add(_b):
        k, a = key_dd.get_selected(), action_dd.get_selected()
        if 0 <= k < len(keys) and 0 <= a < len(choices):
            set_(c.id, {**current, keys[k]: choices[a][0]}, False)
    add.connect("clicked", on_add)

    def rebuild():
        for w in shown + [adder]:
            if w.get_parent() is not None:
                row.remove(w)
        shown.clear()
        for k in sorted(current, key=lambda k: (k.startswith("fn+"), keys.index(k) if k in keys else 999)):
            r = Adw.ActionRow(title=_(keymap.key_label(k)), subtitle="→ " + action_label(current[k]))
            remove = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_("Remove"),
                                valign=Gtk.Align.CENTER, css_classes=["flat"])
            remove.connect("clicked", lambda _b, k=k: set_(c.id, {kk: v for kk, v in current.items() if kk != k}, False))
            r.add_suffix(remove)
            row.add_row(r)
            shown.append(r)
        row.add_row(adder)
        n = len(current)
        row.set_subtitle(_(c.subtitle) if not n else _("{} remapped").format(n))

    def set_macros(names: list[str]):
        nonlocal choices
        choices = _action_choices(names)
        action_model.splice(0, action_model.get_n_items(), [label for _v, label in choices])

    def update(v):
        current.clear()
        current.update(v or {})
        rebuild()
    row.set_macros = set_macros
    rebuild()
    return row, update


def key_colors(c: C.KeyColors, _guard: Guard, set_: Setter, _sp):
    """Without the keyboard drawing (the device page shows one): how many keys are painted, and clear."""
    row = Adw.ActionRow(title=_(c.title), subtitle=_(c.subtitle))
    clear = Gtk.Button(label=_("Clear all"), valign=Gtk.Align.CENTER)
    clear.connect("clicked", lambda _b: set_(c.id, {}, False))
    row.add_suffix(clear)

    def update(v):
        row.set_subtitle(_("{} keys painted").format(len(v)) if v else _(c.subtitle))
    return row, update


def button_map(c: C.ButtonMap, guard: Guard, set_: Setter, _sp):
    """One row per button with what it should do; "Run a command…" opens a field for the command."""
    current: dict[str, str] = {}
    row = Adw.ExpanderRow(title=_(c.title), subtitle=_(c.subtitle), expanded=True)
    RUN = "run:"

    def make_choices(macros):
        rest = [x for x in _action_choices(macros) if x[0] not in ("disabled", "fn", "fn-lock")]
        return ([("default", _("Original function")), ("disabled", _("Disabled"))]
                + [(v, _(label)) for v, label in c.device_actions] + [(RUN, _("Run a command…"))] + rest)
    choices = make_choices([])
    entries: dict[str, tuple[Gtk.DropDown, Gtk.StringList, Adw.ActionRow, Gtk.Entry]] = {}

    def send(button, action):
        new = {k: v for k, v in current.items() if k != button}
        if action != "default":
            new[button] = action
        set_(c.id, new, False)

    for button, label in c.buttons:
        model = Gtk.StringList.new([lbl for _v, lbl in choices])
        dd = _searchable(Gtk.DropDown(model=model, valign=Gtk.Align.CENTER))
        r = Adw.ActionRow(title=_(label))
        r.add_suffix(dd)
        row.add_row(r)
        cmd_row = Adw.ActionRow(title=_("Command"), visible=False)
        cmd = Gtk.Entry(placeholder_text="playerctl next", hexpand=True, valign=Gtk.Align.CENTER)
        save = Gtk.Button(label=_("Save"), valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
        save.connect("clicked", lambda _b, b=button, e=cmd: e.get_text().strip() and send(b, RUN + e.get_text().strip()))
        cmd.connect("activate", lambda e, b=button: e.get_text().strip() and send(b, RUN + e.get_text().strip()))
        cmd_row.add_suffix(cmd)
        cmd_row.add_suffix(save)
        row.add_row(cmd_row)
        entries[button] = (dd, model, cmd_row, cmd)

        def on_pick(d, _p, b=button):
            if guard.active:
                return
            i = d.get_selected()
            if not 0 <= i < len(choices):
                return
            value = choices[i][0]
            entries[b][2].set_visible(value == RUN)
            if value == RUN:
                entries[b][3].grab_focus()
            else:
                send(b, value)
        dd.connect("notify::selected", on_pick)

    def show():
        values = [v for v, _l in choices]
        with guard:
            for button, (dd, _m, cmd_row, cmd) in entries.items():
                action = current.get(button, "default")
                is_run = action.startswith(RUN)
                key = RUN if is_run else action
                dd.set_selected(values.index(key) if key in values else 0)  # 0: e.g. a macro that was deleted
                cmd_row.set_visible(is_run)
                if is_run:
                    cmd.set_text(action[len(RUN):])
        n = len(current)
        row.set_subtitle(_(c.subtitle) if not n else _("{} remapped").format(n))

    def set_macros(names):
        nonlocal choices
        choices = make_choices(names)
        with guard:
            for dd, model, _r, _e in entries.values():
                model.splice(0, model.get_n_items(), [label for _v, label in choices])
        show()

    def update(v):
        current.clear()
        current.update(v or {})
        show()
    row.set_macros = set_macros
    show()
    return row, update


def recorder(c: C.Recorder, guard: Guard, set_: Setter, _sp):
    """Record/Stop toggle. The button never takes keyboard focus: the keys typed while recording
    would otherwise press it."""
    row = Adw.ActionRow(title=_(c.title), subtitle=_(c.subtitle))
    button = Gtk.ToggleButton(label=_("Record"), valign=Gtk.Align.CENTER, focusable=False, focus_on_click=False)
    row.add_suffix(button)
    on_result: list = []

    def toggled(b):
        if guard.active:
            return
        if b.get_active() and b.get_root() is not None:
            b.get_root().set_focus(None)  # don't type into an entry while recording
        set_(c.id, b.get_active(), False)
    button.connect("toggled", toggled)

    def update(v):
        recording = v == ""
        with guard:
            button.set_active(recording)
        button.set_label(_("Stop") if recording else _("Record"))
        if recording:
            row.set_subtitle(_("Recording… type on the keyboard"))
        elif v:
            row.set_subtitle(_("Recorded: {}").format(v if len(v) < 60 else v[:57] + "…"))
            for fn in on_result:
                fn(v)
        else:
            row.set_subtitle(_(c.subtitle))
    row.on_result = on_result
    return row, update


def macro_list(c: C.MacroList, _guard: Guard, set_: Setter, _sp):
    """Expander with the macros and an editor: name, steps, play mode. Clicking a macro edits it."""
    current: dict[str, dict] = {}
    modes = [v for v, _label in C.MACRO_MODES]
    row = Adw.ExpanderRow(title=_(c.title), subtitle=_(c.subtitle))
    name = Gtk.Entry(placeholder_text=_("Name"), width_chars=12)
    mode = Gtk.DropDown.new_from_strings([_(label) for _v, label in C.MACRO_MODES])
    save = Gtk.Button(label=_("Save"), valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
    steps = Gtk.Entry(placeholder_text='ctrl+c, 50ms, ctrl+v', hexpand=True)
    hint = Gtk.Label(label=_('Steps: ctrl+c · 50ms · "text" · down:shift / up:shift · click:left · wheel:down'),
                     xalign=0, wrap=True, css_classes=["dim-label", "caption"])
    top = Gtk.Box(spacing=6)
    for w in (name, mode, save):
        top.append(w)
    editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=10, margin_bottom=10,
                     margin_start=12, margin_end=12)
    for w in (top, steps, hint):
        editor.append(w)
    adder = Adw.PreferencesRow(activatable=False)
    adder.set_child(editor)
    shown: list[Gtk.Widget] = []
    on_change: list = []

    def problem(widget: Gtk.Entry, message: str | None):
        (widget.add_css_class if message else widget.remove_css_class)("error")
        widget.set_tooltip_text(message)

    def on_save(_b):
        title, text = name.get_text().strip(), steps.get_text().strip()
        problem(name, None if title else _("Give the macro a name"))
        try:
            keymap.parse_macro(text)
            problem(steps, None)
        except ValueError as e:
            problem(steps, str(e))
            return
        if title:
            set_(c.id, {**current, title: {"steps": text, "mode": modes[mode.get_selected()]}}, False)
            name.set_text("")
            steps.set_text("")
    save.connect("clicked", on_save)

    def edit(title: str):
        name.set_text(title)
        steps.set_text(current[title]["steps"])
        mode.set_selected(modes.index(current[title].get("mode", "once")))

    def set_steps(text: str):  # a recording arrived: open the editor with it, ready to be named
        steps.set_text(text)
        row.set_expanded(True)
        name.grab_focus()

    def rebuild():
        for w in shown + [adder]:
            if w.get_parent() is not None:
                row.remove(w)
        shown.clear()
        for title, m in current.items():
            label = dict(C.MACRO_MODES)[m.get("mode", "once")]
            r = Adw.ActionRow(title=title, subtitle=f"{m['steps']}  ·  {_(label)}", activatable=True)
            r.connect("activated", lambda _r, t=title: edit(t))
            remove = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_("Remove"),
                                valign=Gtk.Align.CENTER, css_classes=["flat"])
            remove.connect("clicked", lambda _b, t=title: set_(c.id, {k: v for k, v in current.items() if k != t}, False))
            r.add_suffix(remove)
            row.add_row(r)
            shown.append(r)
        row.add_row(adder)
        row.set_subtitle(_(c.subtitle) if not current else _("{} macros").format(len(current)))

    def update(v):
        current.clear()
        current.update(v or {})
        rebuild()
        for fn in on_change:
            fn(list(current))
    row.on_change = on_change
    row.set_steps = set_steps
    rebuild()
    return row, update


BUILDERS = {
    C.Toggle: toggle,
    C.Range: range_,
    C.Choice: choice,
    C.Color: color,
    C.Info: info,
    C.Action: action,
    C.KeyRemap: key_remap,
    C.KeyColors: key_colors,
    C.ButtonMap: button_map,
    C.MacroList: macro_list,
    C.Recorder: recorder,
}
