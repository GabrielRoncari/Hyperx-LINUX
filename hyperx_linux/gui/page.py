"""The page of one device, generated from its driver's controls."""
from __future__ import annotations

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
from . import widgets as W  # noqa: E402
from .trayicon import battery_icon_name  # noqa: E402

GROUP_ORDER = (C.Group.MICROPHONE, C.Group.AUDIO, C.Group.PERFORMANCE, C.Group.LIGHTING,
               C.Group.POWER, C.Group.SYSTEM, C.Group.INFO)
GROUP_TITLES = {
    C.Group.MICROPHONE: "Microphone", C.Group.AUDIO: "Audio", C.Group.LIGHTING: "Lighting",
    C.Group.PERFORMANCE: "Performance", C.Group.POWER: "Power", C.Group.SYSTEM: "System",
    C.Group.INFO: "Device",
}
KIND_ICONS = {
    Kind.HEADSET: "audio-headset-symbolic",
    Kind.MOUSE: "input-mouse-symbolic",
    Kind.KEYBOARD: "input-keyboard-symbolic",
    Kind.MICROPHONE: "audio-input-microphone-symbolic",
    Kind.OTHER: "applications-system-symbolic",
}


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


class DevicePage(Gtk.Box):
    def __init__(self, session: Session, set_: Callable[[Session, str, object, bool], None],
                 low_battery: Callable[[], int], on_preset: Callable[[Session, str | None], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.session = session
        self.low_battery = low_battery
        self.guard = W.Guard()
        self.sp = W.ScrollPassthrough()
        self.updaters: dict[str, Callable[[object], None]] = {}
        drv = session.driver

        banner = self._support_banner()
        if banner:
            self.append(banner)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True)
        self.stack.add_named(Adw.StatusPage(
            icon_name=KIND_ICONS[drv.kind], title=_("Device off or out of range"),
            description=_("The receiver is connected. Turn the device on or bring it closer.")), "offline")
        self.stack.add_named(Adw.StatusPage(icon_name=KIND_ICONS[drv.kind], title=_("Reading…")), "loading")

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                       margin_top=18, margin_bottom=24, margin_start=16, margin_end=16)
        body.append(self._hero())

        def setter(cid, value, live):
            set_(session, cid, value, live)

        for group in GROUP_ORDER:
            ctrls = [c for c in drv.controls if c.group == group]
            if group == C.Group.INFO:
                body.append(self._info_group(ctrls, setter))
                continue
            if not ctrls:
                continue
            pg = Adw.PreferencesGroup(title=_(GROUP_TITLES[group]))
            body.append(pg)
            for c in ctrls:
                if isinstance(c, C.Equalizer):
                    saved = session.manager.config.device(session.driver_id).get("eq_preset")
                    box, update = W.equalizer(c, self.guard, setter, self.sp, saved,
                                              lambda name: on_preset(session, name))
                    box.set_sensitive(session.writable)
                    body.append(box)  # outside the group: it carries its own card
                    pg = Adw.PreferencesGroup()  # following rows go after the EQ
                    body.append(pg)
                else:
                    row, update = W.BUILDERS[type(c)](c, self.guard, setter, self.sp)
                    pg.add(row)
                    if not isinstance(c, C.Info) and not (session.writable and c.writable):
                        row.set_sensitive(False)
                self.updaters[c.id] = update

        scrolled = Gtk.ScrolledWindow(child=Adw.Clamp(maximum_size=600, child=body),
                                      hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.sp.scrolled = scrolled
        self.stack.add_named(scrolled, "main")
        self.append(self.stack)

        for cid, value in list(drv.values.items()):
            self.apply(cid, value)
        self.apply("online", drv.online)

    # ----------------------------------------------------------------- parts
    def _support_banner(self) -> Adw.Banner | None:
        support = self.session.driver.support
        if support == Support.VERIFIED:
            return None
        if support == Support.COMMUNITY:
            title = _("Confirmed by the community, not tested by the maintainers")
        elif self.session.writable:
            title = _("Experimental: not confirmed on real hardware")
        else:
            title = _("Experimental: not confirmed on real hardware, changes are disabled")
        banner = Adw.Banner(title=title, revealed=True, button_label=_("Report results"))
        banner.connect("button-clicked", lambda *_a: Gio.AppInfo.launch_default_for_uri(ISSUES_URL, None))
        return banner

    def _hero(self) -> Gtk.Widget:
        drv = self.session.driver
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["card", "hero"])
        top = Gtk.Box(spacing=12)
        has_battery = any(isinstance(c, C.Battery) for c in drv.controls)
        self.hero_icon = Gtk.Image(icon_name=KIND_ICONS[drv.kind], pixel_size=40)
        top.append(self.hero_icon)
        self.hero_label = Gtk.Label(label="—" if has_battery else drv.name, xalign=0,
                                    css_classes=["battery-big" if has_battery else "title-2"])
        top.append(self.hero_label)
        self.hero_detail = Gtk.Label(xalign=0, css_classes=["dim-label"], hexpand=True, valign=Gtk.Align.CENTER)
        top.append(self.hero_detail)
        hero.append(top)
        self.hero_bar = None
        if has_battery:
            self.hero_bar = Gtk.LevelBar(min_value=0, max_value=100, css_classes=["battery"])
            for name in ("low", "high", "full"):
                self.hero_bar.remove_offset_value(name)
            hero.append(self.hero_bar)
            self.updaters["battery"] = self._update_battery
        else:
            self.hero_detail.set_label(self.session.driver.variant(self.session.info))
        return hero

    def _update_battery(self, b: C.BatteryValue | None) -> None:
        if b is None:
            return
        self.hero_label.set_label(f"{b.level}%" if b.level is not None else "—")
        self.hero_icon.set_from_icon_name(themed(battery_icon(b, self.session.driver.online)))
        self.hero_detail.set_label(battery_text(b))
        if self.hero_bar:
            self.hero_bar.set_value(b.level or 0)
            low = b.level is not None and b.level <= self.low_battery()
            (self.hero_bar.add_css_class if low else self.hero_bar.remove_css_class)("low")

    def _info_group(self, ctrls, setter) -> Gtk.Widget:
        s, drv = self.session, self.session.driver
        pg = Adw.PreferencesGroup(title=_("Device"))
        for c in ctrls:
            row, update = W.BUILDERS[type(c)](c, self.guard, setter, self.sp)
            pg.add(row)
            self.updaters[c.id] = update
        support = {Support.VERIFIED: _("Tested on real hardware"),
                   Support.COMMUNITY: _("Confirmed by the community, not tested by the maintainers"),
                   Support.EXPERIMENTAL: _("Experimental: not confirmed on real hardware")}[drv.support]
        rows = [
            ("Model", f"{drv.name}" + (f" · {drv.variant(s.info)}" if drv.variant(s.info) else "")),
            ("USB", f"{s.info.usb_id} · {s.info.path}" + (f" · if {s.info.interface}" if s.info.interface is not None else "")),
            ("Firmware", f"{s.info.bcd_device >> 8:x}.{s.info.bcd_device & 0xFF:02x}" if s.info.bcd_device else "—"),
            ("Driver", support),
        ]
        for title, value in rows:
            row = Adw.ActionRow(title=_(title), subtitle=value, subtitle_selectable=True)
            row.add_css_class("property")
            pg.add(row)
        return pg

    # ---------------------------------------------------------------- update
    def apply(self, key: str, value: object) -> None:
        if key == "online":
            self.stack.set_visible_child_name(
                "main" if value else ("offline" if value is False else "loading"))
            if value is not None:
                self._update_battery(self.session.driver.values.get("battery"))
            return
        update = self.updaters.get(key)
        if update:
            with self.guard:
                update(value)
