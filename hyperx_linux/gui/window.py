"""Main window: device sidebar + the selected device's page."""
from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from .. import controls as C  # noqa: E402
from ..catalog import DETECTION_ONLY  # noqa: E402
from ..drivers import display_name  # noqa: E402
from ..i18n import _  # noqa: E402
from .page import KIND_ICONS, DevicePage, battery_icon  # noqa: E402

if TYPE_CHECKING:
    from .app import App

APP_NAME = "HyperX Linux"


class Window(Adw.ApplicationWindow):
    def __init__(self, app: "App"):
        super().__init__(application=app, title=APP_NAME, default_width=860, default_height=820)
        self.app = app
        self.set_hide_on_close(True)
        self.set_size_request(360, 420)  # required by the breakpoint
        self.pages: dict[str, DevicePage] = {}
        self.rows: dict[str, Adw.ActionRow] = {}
        self._selected: str | None = None

        # sidebar
        self.listbox = Gtk.ListBox(css_classes=["navigation-sidebar"])
        self.listbox.connect("row-selected", self._on_row_selected)
        side_header = Adw.HeaderBar()
        menu = Gio.Menu()
        menu.append(_("Preferences"), "app.preferences")
        menu.append(_("About"), "app.about")
        menu.append(_("Quit"), "app.quit")
        side_header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        side = Adw.ToolbarView()
        side.add_top_bar(side_header)
        side.set_content(Gtk.ScrolledWindow(child=self.listbox, hscrollbar_policy=Gtk.PolicyType.NEVER))

        # content
        self.content_title = Adw.WindowTitle(title=APP_NAME)
        content_header = Adw.HeaderBar(title_widget=self.content_title)
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=_("Refresh"))
        refresh.connect("clicked", self._on_refresh)
        content_header.pack_start(refresh)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.empty = Adw.StatusPage(icon_name="audio-headset-symbolic", title=_("No HyperX device found"),
                                    description=_("Plug in a HyperX headset, receiver, mouse, keyboard or microphone."))
        self.stack.add_named(self.empty, "empty")
        self.toasts = Adw.ToastOverlay(child=self.stack)
        content = Adw.ToolbarView()
        content.add_top_bar(content_header)
        content.set_content(self.toasts)

        self.split = Adw.NavigationSplitView(
            sidebar=Adw.NavigationPage(child=side, title=_("Devices")),
            content=Adw.NavigationPage(child=content, title=APP_NAME),
        )
        self.set_content(self.split)
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 780sp"))  # sidebar + EQ need ~730
        bp.add_setter(self.split, "collapsed", True)
        self.add_breakpoint(bp)
        self.rebuild()

    # --------------------------------------------------------------- devices
    def rebuild(self) -> None:
        sessions = {s.key: s for s in self.app.manager.list()}
        for key in list(self.pages):
            if key not in sessions:
                self.stack.remove(self.pages.pop(key))
        while (row := self.listbox.get_row_at_index(0)) is not None:
            self.listbox.remove(row)
        self.rows.clear()

        entries: list[tuple[str, Adw.ActionRow]] = []
        for key, s in sessions.items():
            if key not in self.pages:
                page = DevicePage(s, self.app.set_control, lambda: self.app.manager.config["low_battery"],
                                  self.app.save_preset)
                self.pages[key] = page
                self.stack.add_named(page, key)
            row = Adw.ActionRow(title=s.name, activatable=True)
            row.add_prefix(Gtk.Image(icon_name=KIND_ICONS[s.driver.kind]))
            entries.append((key, row))
            self.rows[key] = row
            self.update_row(s)
        for info in self.app.manager.unsupported:
            if (info.vid, info.pid) in DETECTION_ONLY:
                continue  # e.g. a headset charging over USB-C: the receiver is the device to control
            key = f"unsupported:{info.usb_path or info.path}"
            row = Adw.ActionRow(title=display_name(info), subtitle=_(self._unsupported_label(info)),
                                activatable=True)
            row.add_prefix(Gtk.Image(icon_name="dialog-question-symbolic"))
            entries.append((key, row))
            if self.stack.get_child_by_name(key) is None:
                self.stack.add_named(self._unsupported_page(info), key)
        for key, err in self.app.manager.errors.items():
            row = Adw.ActionRow(title=_("No permission to access the device"), subtitle=err, activatable=True)
            row.add_prefix(Gtk.Image(icon_name="dialog-warning-symbolic"))
            entries.append((f"error:{key}", row))
            if self.stack.get_child_by_name(f"error:{key}") is None:
                self.stack.add_named(Adw.StatusPage(
                    icon_name="dialog-warning-symbolic", title=_("No permission to access the device"),
                    description=_("Install the udev rules: run install.sh or see the README.")), f"error:{key}")

        for key, row in entries:
            row.key = key
            self.listbox.append(row)
        keys = [k for k, _r in entries]
        target = self._selected if self._selected in keys else (keys[0] if keys else None)
        if target is None:
            self.stack.set_visible_child_name("empty")
            self.content_title.set_title(APP_NAME)
        else:
            self.listbox.select_row(next(r for k, r in entries if k == target))

    @staticmethod
    def _unsupported_label(info) -> str:
        from ..drivers import passive_note
        return passive_note(info) or "Not supported yet"

    def _unsupported_page(self, info) -> Gtk.Widget:
        from ..drivers import passive_note
        note = passive_note(info)
        if note:
            return Adw.StatusPage(icon_name="dialog-information-symbolic", title=display_name(info),
                                  description=_(note))
        return Adw.StatusPage(
            icon_name="dialog-question-symbolic", title=f"{display_name(info)} ({info.usb_id})",
            description=_("Not supported yet") + "\n\n" +
            _("Run “hyperx-linux diag” and open an issue with the output to help add it."))

    def update_row(self, session) -> None:
        row = self.rows.get(session.key)
        if row is None:
            return
        drv = session.driver
        b = drv.values.get("battery")
        if drv.online is False:
            row.set_subtitle(_("Device off or out of range"))
        elif isinstance(b, C.BatteryValue) and b.level is not None:
            text = _("Battery {level}%", level=b.level)
            if b.charging:
                text += f" · {_('charging')}"
            row.set_subtitle(text)
        else:
            row.set_subtitle(_("Connected") if drv.online else "")

    def _on_row_selected(self, _lb, row) -> None:
        if row is None:
            return
        self._selected = row.key
        self.stack.set_visible_child_name(row.key)
        self.content_title.set_title(row.get_title())
        self.split.set_show_content(True)

    def _on_refresh(self, *_a) -> None:
        page = self.pages.get(self._selected or "")
        if page:
            page.session.refresh()

    # ----------------------------------------------------------------- events
    def on_change(self, session, key, value) -> None:
        page = self.pages.get(session.key)
        if key == "error":
            if value:
                self.toasts.add_toast(Adw.Toast(title=str(value), timeout=4))
            return
        if page:
            page.apply(key, value)
        if key in ("battery", "online"):
            self.update_row(session)


__all__ = ["Window", "battery_icon"]
