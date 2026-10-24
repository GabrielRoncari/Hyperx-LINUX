"""The home page: a card per device, like NGENUITY's (battery, the device, its name, shortcuts to
its features)."""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk  # noqa: E402

from .. import controls as C  # noqa: E402
from ..drivers import Support  # noqa: E402
from ..i18n import _  # noqa: E402
from . import art  # noqa: E402
from .keyboard import KeyboardCanvas  # noqa: E402
from .page import FALLBACK_ICON, KIND_ICONS, features_of, themed  # noqa: E402

KIND_NAMES = {"headset": "Headset", "mouse": "Mouse", "keyboard": "Keyboard", "microphone": "Microphone",
              "other": "HyperX device"}
CHARS = 22  # wrapped text measures by its unwrapped length: keep cards card-sized
SUPPORT = {Support.VERIFIED: "Tested on real hardware", Support.COMMUNITY: "Community",
           Support.EXPERIMENTAL: "Experimental"}


class HomePage(Gtk.ScrolledWindow):
    def __init__(self, open_device: Callable[[str, str | None], None]):
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.open_device = open_device
        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=16, row_spacing=16,
                                homogeneous=True, max_children_per_line=4, min_children_per_line=1,
                                halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=48, margin_bottom=48)
        self.set_child(self.flow)
        self.batteries: dict[str, Callable] = {}

    def rebuild(self, sessions, extra_cards) -> None:
        """extra_cards: (key, title, subtitle, icon) for devices without a page of their own."""
        while (child := self.flow.get_first_child()) is not None:
            self.flow.remove(child)
        self.batteries.clear()
        for s in sessions:
            self.flow.append(self._card(s))
        for key, title, subtitle, icon in extra_cards:
            self.flow.append(self._plain_card(key, title, subtitle, icon))
        if not sessions and not extra_cards:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["hx-card"],
                          width_request=420)
            box.append(Gtk.Label(label=_("No HyperX device found"), css_classes=["hx-card-name"], wrap=True))
            box.append(Gtk.Label(label=_("Plug in a HyperX headset, receiver, mouse, keyboard or microphone."),
                                 css_classes=["hx-card-sub"], wrap=True, justify=Gtk.Justification.CENTER))
            self.flow.append(box)

    def _card(self, s) -> Gtk.Widget:
        drv = s.driver
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["hx-card"],
                       width_request=260, height_request=296)
        top = Gtk.Box(spacing=6)
        battery = Gtk.Label(label="", xalign=0, css_classes=["hx-chip"], visible=False)
        top.append(battery)
        card.append(top)
        colors = next((c for c in s.controls if isinstance(c, (C.KeyColors, C.KeyRemap)) and c.layouts), None)
        if colors is not None:  # the keyboard itself, with its live light
            canvas = KeyboardCanvas(natural_width=228)
            canvas.set_keys(colors.layouts[0][1])
            canvas.set_live(lambda d=drv: getattr(d, "preview", None))
            canvas.set_vexpand(True)
            canvas.set_valign(Gtk.Align.CENTER)
            card.append(canvas)
        else:
            card.append(art.widget(drv.kind.value, themed(KIND_ICONS[drv.kind], FALLBACK_ICON), 180, 150,
                                   vexpand=True))
        card.append(Gtk.Label(label=drv.name.replace("HyperX ", "").upper(), css_classes=["hx-card-name"],
                              wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=CHARS))
        card.append(Gtk.Label(label=f"{_(KIND_NAMES.get(drv.kind.value, 'HyperX device'))} · "
                                    f"{_(SUPPORT[drv.support])}", css_classes=["hx-card-sub"], wrap=True,
                              justify=Gtk.Justification.CENTER, max_width_chars=CHARS))
        shortcuts = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
        for fid, title, icon, _groups in features_of(s.controls):
            b = Gtk.Button(child=Gtk.Image(icon_name=themed(icon, FALLBACK_ICON), pixel_size=18),
                           tooltip_text=_(title), css_classes=["flat", "hx-feature-tab"])
            b.connect("clicked", lambda _b, f=fid, k=s.key: self.open_device(k, f))
            shortcuts.append(b)
        card.append(shortcuts)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_a, k=s.key: self.open_device(k, None))
        card.add_controller(click)

        def show_battery(b):
            if isinstance(b, C.BatteryValue) and b.level is not None:
                battery.set_label(f"{b.level}%" + (" ⚡" if b.charging else ""))
                battery.set_visible(True)
        self.batteries[s.key] = show_battery
        show_battery(drv.values.get("battery"))
        return card

    def _plain_card(self, key, title, subtitle, icon) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["hx-card"],
                       width_request=260, height_request=296)
        card.append(Gtk.Image(icon_name=icon, pixel_size=64, vexpand=True))
        card.append(Gtk.Label(label=title.upper(), css_classes=["hx-card-name"], wrap=True,
                              justify=Gtk.Justification.CENTER, max_width_chars=CHARS))
        card.append(Gtk.Label(label=subtitle, css_classes=["hx-card-sub"], wrap=True, justify=Gtk.Justification.CENTER,
                              max_width_chars=CHARS))
        click = Gtk.GestureClick()
        click.connect("released", lambda *_a: self.open_device(key, None))
        card.add_controller(click)
        return card

    def update_battery(self, key: str, value) -> None:
        if key in self.batteries:
            self.batteries[key](value)
