"""The page of one device, laid out like NGENUITY 3.1's: the device preview fills the page, status chips
sit at the top, and a feature panel at the bottom has one tab per feature (Lighting, Keys, Audio…),
each made of sections. Everything is generated from the driver's controls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from .. import ISSUES_URL  # noqa: E402
from .. import controls as C  # noqa: E402
from ..drivers import Kind, Support  # noqa: E402
from ..i18n import _, number  # noqa: E402
from ..manager import Session  # noqa: E402
from . import art, compat, keyboard  # noqa: E402
from . import widgets as W  # noqa: E402
from .panel import FeaturePanel  # noqa: E402
from .trayicon import battery_icon_name  # noqa: E402

# NGENUITY's features and the control groups that make each one
FEATURES = (
    ("lights", "Lighting", "display-brightness-symbolic", (C.Group.LIGHTING,)),
    ("keys", "Keys", "input-keyboard-symbolic", (C.Group.KEYS,)),
    ("sensor", "Sensor", "input-mouse-symbolic", (C.Group.PERFORMANCE,)),
    ("audio", "Audio", "audio-volume-high-symbolic", (C.Group.AUDIO, C.Group.MICROPHONE, C.Group.VOICE)),
    ("spatial", "Spatial audio", "audio-speakers-symbolic", (C.Group.ENGINE,)),
    ("buttons", "Buttons", "input-gaming-symbolic", (C.Group.BUTTONS,)),
    ("settings", "Settings", "emblem-system-symbolic", (C.Group.POWER, C.Group.SYSTEM, C.Group.INFO)),
)
GROUP_TITLES = {
    C.Group.MICROPHONE: "Microphone", C.Group.AUDIO: "Audio", C.Group.ENGINE: "Audio engine",
    C.Group.VOICE: "Voice processing", C.Group.BUTTONS: "Buttons", C.Group.LIGHTING: "Lighting",
    C.Group.KEYS: "Keys", C.Group.PERFORMANCE: "Performance", C.Group.POWER: "Power",
    C.Group.SYSTEM: "System", C.Group.INFO: "Device",
}
KIND_ICONS = {
    Kind.HEADSET: "audio-headset-symbolic",
    Kind.MOUSE: "input-mouse-symbolic",
    Kind.KEYBOARD: "input-keyboard-symbolic",
    Kind.MICROPHONE: "audio-input-microphone-symbolic",
    Kind.OTHER: "applications-system-symbolic",
}
FALLBACK_ICON = "emblem-system-symbolic"


def battery_icon(b: C.BatteryValue | None, online: bool | None) -> str:
    if b is None:
        return "battery-missing-symbolic"
    return battery_icon_name(b.level, b.charging, b.full, online)


def themed(name: str, fallback: str = "battery-symbolic") -> str:
    """The name if the current icon theme has it, a generic icon otherwise (never "image-missing")."""
    display = Gdk.Display.get_default()
    if display is not None and not Gtk.IconTheme.get_for_display(display).has_icon(name):
        return fallback
    return name


def battery_text(b: C.BatteryValue | None) -> str:
    if b is None:
        return ""
    parts = []
    if b.full:
        parts.append(_("Fully charged"))
    elif b.charging is not None:
        parts.append(_("Charging") if b.charging else _("Discharging"))
    if b.voltage_mv:
        parts.append(f"{number(b.voltage_mv / 1000)} V")
    return " · ".join(parts)


def features_of(controls) -> list[tuple[str, str, str, tuple]]:
    groups = {c.group for c in controls if not isinstance(c, C.Battery)}
    return [f for f in FEATURES if groups & set(f[3])]


@dataclass
class Ctx:
    """What feature builders need from the page."""
    session: Session
    guard: W.Guard
    sp: W.ScrollPassthrough
    set: Callable[[str, object, bool], None]
    register: Callable[[str, Callable], None]
    panel: FeaturePanel
    on_preset: Callable[[str | None], None]

    def can_write(self, c: C.Control) -> bool:
        return self.session.can_write(c)

    def build(self, c: C.Control) -> Gtk.Widget:
        """A row for one control, wired to the page, greyed out when it can't be changed."""
        row, update = W.BUILDERS[type(c)](c, self.guard, self.set, self.sp)
        self.register(c.id, update)
        if not isinstance(c, C.Info) and not self.can_write(c):
            row.set_sensitive(False)
            if c.experimental and self.session.writable:
                row.set_tooltip_text(_("Not confirmed on this model yet: enable experimental "
                                       "drivers in Preferences to use it"))
        return row


def section(title: str, *children: Gtk.Widget, scroll: bool = True) -> Gtk.Box:
    """NGENUITY's Section: a faint card with a title; its content scrolls inside the panel."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["hx-section"], hexpand=True)
    if title:
        box.append(Gtk.Label(label=title, xalign=0, css_classes=["hx-section-title"]))
    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    for child in children:
        inner.append(child)
    if scroll:
        box.append(Gtk.ScrolledWindow(child=inner, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      propagate_natural_height=False))
    else:
        box.append(inner)
    return box


def rows_list(rows: list[Gtk.Widget]) -> Gtk.ListBox:
    lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    for r in rows:
        lb.append(r)
    return lb


class DevicePage(Gtk.Box):
    def __init__(self, session: Session, set_: Callable[[Session, str, object, bool], None],
                 low_battery: Callable[[], int], on_preset: Callable[[Session, str | None], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.session = session
        self.low_battery = low_battery
        self.guard = W.Guard()
        self.sp = W.ScrollPassthrough()
        self.updaters: dict[str, Callable[[object], None]] = {}
        drv = session.driver
        controls = session.controls
        self.rows: dict[str, Gtk.Widget] = {}

        # chips at the top: battery, support level
        top = Gtk.Box(spacing=6)
        self.battery_chip = Gtk.Box(spacing=6, css_classes=["hx-chip"], visible=False)
        self.battery_icon = Gtk.Image(icon_name="battery-missing-symbolic")
        self.battery_label = Gtk.Label(label="—")
        self.battery_chip.append(self.battery_icon)
        self.battery_chip.append(self.battery_label)
        top.append(self.battery_chip)
        chip = self._support_chip()
        if chip:
            top.append(chip)
        top.append(Gtk.Label(label=drv.name, css_classes=["hx-device-name"], hexpand=True, xalign=0.5,
                             ellipsize=3))
        self.append(top)

        # the preview: the keyboard itself, or a drawing of the device with its battery
        self.preview_stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                                       vhomogeneous=False)
        self.keyboard: keyboard.KeyboardPreview | None = None
        colors = next((c for c in controls if isinstance(c, C.KeyColors)), None)
        remap = next((c for c in controls if isinstance(c, C.KeyRemap) and c.layouts), None)
        if colors or remap:
            self.keyboard = keyboard.KeyboardPreview((colors or remap).layouts, lambda: getattr(drv, "preview", None))
            self.preview_stack.add_named(self.keyboard, "main")
        else:
            self.preview_stack.add_named(self._art_preview(), "main")
        self.preview_stack.add_named(self._state_page(_("Device off or out of range"),
                                                      _("The receiver is connected. Turn the device on or bring it closer.")),
                                     "offline")
        self.preview_stack.add_named(self._state_page(_("Reading…"), ""), "loading")
        self.append(self.preview_stack)

        # the feature panel
        self.panel = FeaturePanel()
        ctx = Ctx(session, self.guard, self.sp, lambda cid, v, live: set_(session, cid, v, live),
                  self._register, self.panel, lambda name: on_preset(session, name))
        self.ctx = ctx
        for fid, title, icon, groups in features_of(controls):
            ctrls = [c for c in controls if c.group in groups and not isinstance(c, C.Battery)]
            extra = None
            if fid == "lights" and colors and self.keyboard:
                content, extra = keyboard.lights_panel(ctx, ctrls, self.keyboard)
            elif fid == "keys" and remap and self.keyboard:
                content = keyboard.keys_panel(ctx, ctrls, self.keyboard)
            else:
                content = self._generic(groups, ctrls)
            self.panel.add_feature(fid, _(title), themed(icon, FALLBACK_ICON), content, extra)
        if self.keyboard:
            self.panel.on_select.append(self.keyboard.set_feature)
        clamp = Adw.Clamp(maximum_size=936, tightening_threshold=840, child=self.panel)
        # the device takes the height it needs at the top; the settings get the rest
        self.preview_stack.set_vexpand(False)
        self.preview_stack.set_valign(Gtk.Align.START)
        if self.keyboard:
            self.keyboard.set_valign(Gtk.Align.START)
        clamp.set_vexpand(True)
        self.panel.set_vexpand(True)
        self.append(clamp)
        if self.panel.features:
            self.panel.select(self.panel.features[0])
        self._wire()

        if any(isinstance(c, C.Battery) for c in drv.controls):
            self.updaters["battery"] = self._update_battery
        for cid, value in list(session.values.items()):
            self.apply(cid, value)
        self.apply("online", drv.online)

    # ----------------------------------------------------------- building
    def _register(self, cid: str, update: Callable) -> None:
        old = self.updaters.get(cid)
        self.updaters[cid] = update if old is None else (lambda v, a=old, b=update: (a(v), b(v)))

    def _generic(self, groups, ctrls) -> Gtk.Widget:
        """One section per control group, side by side."""
        row = Gtk.Box(spacing=8, homogeneous=True)
        for g in groups:
            items = [c for c in ctrls if c.group == g]
            if g == C.Group.INFO:
                row.append(section(_(GROUP_TITLES[g]), rows_list(self._info_rows(items))))
                continue
            if not items:
                continue
            widgets = []
            for c in items:
                if isinstance(c, C.Equalizer):
                    widgets.append(self._equalizer_row(c))
                    continue
                w = self.ctx.build(c)
                self.rows[c.id] = w
                widgets.append(w)
            row.append(section(_(GROUP_TITLES[g]), rows_list(widgets)))
        return row

    def _equalizer_row(self, c: C.Equalizer) -> Gtk.Widget:
        """The equalizer opens over the panel, like NGENUITY's EQ editor."""
        saved = self.session.manager.config.device(self.session.driver_id).get("eq_preset")
        box, update = W.equalizer(c, self.guard, self.ctx.set, self.sp, saved, self.ctx.on_preset)
        if not self.ctx.can_write(c):
            box.set_sensitive(False)
        self._register(c.id, update)
        row = Adw.ActionRow(title=_(c.title), subtitle=_(saved) if saved else _("Custom"))
        edit = Gtk.Button(label=_("Edit"), valign=Gtk.Align.CENTER, css_classes=["hx-secondary"])
        edit.connect("clicked", lambda _b: self.panel.open_editor(_(c.title), box))
        row.add_suffix(edit)
        row.set_activatable_widget(edit)
        self._register(c.id, lambda _v: row.set_subtitle(
            _(self.session.manager.config.device(self.session.driver_id).get("eq_preset") or "Custom")))
        return row

    def _info_rows(self, ctrls) -> list[Gtk.Widget]:
        s, drv = self.session, self.session.driver
        rows = [self.ctx.build(c) for c in ctrls]
        support = {Support.VERIFIED: _("Tested on real hardware"),
                   Support.COMMUNITY: _("Confirmed by the community, not tested by the maintainers"),
                   Support.EXPERIMENTAL: _("Experimental: not confirmed on real hardware")}[drv.support]
        for title, value in (
            ("Model", f"{drv.name}" + (f" · {drv.variant(s.info)}" if drv.variant(s.info) else "")),
            ("USB", f"{s.info.usb_id} · {s.info.path}" + (f" · if {s.info.interface}" if s.info.interface is not None else "")),
            ("Firmware", f"{s.info.bcd_device >> 8:x}.{s.info.bcd_device & 0xFF:02x}" if s.info.bcd_device else "—"),
            ("Driver", support),
        ):
            rows.append(compat.property_row(_(title), value))
        return rows

    def _wire(self) -> None:
        """Macros can be given to keys and buttons; drawings follow the layout the keyboard reports."""
        macro_rows = [self.rows[c.id] for c in self.session.controls if isinstance(c, C.MacroList) and c.id in self.rows]
        for target in (r for r in self.rows.values() if hasattr(r, "set_macros")):
            for m in macro_rows:
                m.on_change.append(target.set_macros)
        if self.keyboard:
            self._register("layout", self.keyboard.set_layout)

    def _art_preview(self) -> Gtk.Widget:
        drv = self.session.driver
        box = Gtk.Box(spacing=40, halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=4)
        box.append(art.widget(drv.kind.value, themed(KIND_ICONS[drv.kind], FALLBACK_ICON), 230, 200))
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        self.big = Gtk.Label(label="", xalign=0, css_classes=["hx-big"])
        self.big_detail = Gtk.Label(label="", xalign=0, css_classes=["hx-dim"])
        self.big_bar = Gtk.LevelBar(min_value=0, max_value=100, css_classes=["battery"], width_request=200,
                                    visible=False)
        for name in ("low", "high", "full"):
            self.big_bar.remove_offset_value(name)
        for w in (self.big, self.big_detail, self.big_bar):
            info.append(w)
        if not any(isinstance(c, C.Battery) for c in drv.controls):
            self.big.set_label("")
            self.big_detail.set_label(drv.variant(self.session.info))
        box.append(info)
        return box

    @staticmethod
    def _state_page(title: str, text: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER,
                      valign=Gtk.Align.CENTER)
        box.append(Gtk.Label(label=title, css_classes=["hx-section-title"]))
        if text:
            box.append(Gtk.Label(label=text, css_classes=["hx-dim"], wrap=True, justify=Gtk.Justification.CENTER))
        return box

    def _support_chip(self) -> Gtk.Widget | None:
        support = self.session.driver.support
        if support == Support.VERIFIED:
            return None
        if support == Support.COMMUNITY:
            text, tip = _("Community"), _("Confirmed by the community, not tested by the maintainers")
        else:
            text = _("Experimental")
            tip = (_("Experimental: not confirmed on real hardware") if self.session.writable else
                   _("Experimental: not confirmed on real hardware, changes are disabled"))
        button = Gtk.Button(css_classes=["hx-chip", "flat"], tooltip_text=tip + " — " + _("Report results"))
        inner = Gtk.Box(spacing=6)
        inner.append(Gtk.Image(icon_name="dialog-information-symbolic"))
        inner.append(Gtk.Label(label=text))
        button.set_child(inner)
        button.connect("clicked", lambda _b: Gio.AppInfo.launch_default_for_uri(ISSUES_URL, None))
        return button

    # ------------------------------------------------------------- update
    def _update_battery(self, b: C.BatteryValue | None) -> None:
        if b is None:
            return
        online = self.session.driver.online
        text = f"{b.level}%" if b.level is not None else "—"
        self.battery_chip.set_visible(True)
        self.battery_label.set_label(text)
        self.battery_icon.set_from_icon_name(themed(battery_icon(b, online)))
        if hasattr(self, "big"):
            self.big.set_label(text)
            self.big_detail.set_label(battery_text(b))
            self.big_bar.set_visible(b.level is not None)
            self.big_bar.set_value(b.level or 0)
            low = b.level is not None and b.level <= self.low_battery()
            (self.big_bar.add_css_class if low else self.big_bar.remove_css_class)("low")

    def apply(self, key: str, value: object) -> None:
        if key == "online":
            self.preview_stack.set_visible_child_name("main" if value else ("offline" if value is False else "loading"))
            self.panel.set_sensitive(bool(value))
            if value is not None:
                self._update_battery(self.session.driver.values.get("battery"))
            return
        update = self.updaters.get(key)
        if update:
            with self.guard:
                update(value)
