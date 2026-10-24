"""Main window, laid out like NGENUITY 3.1: a frosted sidebar with the wordmark and a tree of devices
and their features, and the content on the right: the home cards or a device page."""
from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

from .. import controls as C  # noqa: E402
from ..catalog import DETECTION_ONLY  # noqa: E402
from ..drivers import display_name  # noqa: E402
from ..udev import GROUP, install_command, outdated, root_script, rules, uaccess_supported  # noqa: E402
from . import compat  # noqa: E402
from .autostart import IN_FLATPAK  # noqa: E402
from ..i18n import _  # noqa: E402
from .home import HomePage  # noqa: E402
from .page import FALLBACK_ICON, KIND_ICONS, DevicePage, battery_icon, features_of, themed  # noqa: E402

if TYPE_CHECKING:
    from .app import App

APP_NAME = "HyperX Linux"
SIDEBAR_WIDTH, SIDEBAR_COLLAPSED = 232, 56


class Sidebar(Gtk.Box):
    """The frosted left bar. `collapsed` shows icons only (narrow windows, or the user's choice)."""
    collapsed = GObject.Property(type=bool, default=False)

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, css_classes=["hx-sidebar"])
        self.set_size_request(SIDEBAR_WIDTH, -1)
        self.labels: list[Gtk.Widget] = []  # header and bottom: always there
        self.tree_labels: list[Gtk.Widget] = []  # the device tree: rebuilt often
        self.connect("notify::collapsed", lambda *_a: self.apply_collapsed())

    def track(self, widget: Gtk.Widget, tree: bool = False) -> Gtk.Widget:
        """Hidden while collapsed."""
        (self.tree_labels if tree else self.labels).append(widget)
        widget.set_visible(not self.collapsed)
        return widget

    def apply_collapsed(self) -> None:
        self.set_size_request(SIDEBAR_COLLAPSED if self.collapsed else SIDEBAR_WIDTH, -1)
        for w in self.labels + self.tree_labels:
            w.set_visible(not self.collapsed)
        self.queue_resize()


def _row(icon: str, label: str, sidebar: Sidebar, child: bool = False, suffix: Gtk.Widget | None = None,
         tree: bool = True):
    row = Gtk.ListBoxRow()
    box = Gtk.Box(spacing=8, css_classes=["hx-child"] if child else [])
    box.append(Gtk.Image(icon_name=icon, pixel_size=16 if child else 20))
    text = Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
    box.append(sidebar.track(text, tree))
    if suffix is not None:
        box.append(sidebar.track(suffix, tree))
    row.set_child(box)
    row.set_tooltip_text(label)
    return row


class Window(Adw.ApplicationWindow):
    def __init__(self, app: "App"):
        super().__init__(application=app, title=APP_NAME, default_width=1280, default_height=860)
        self.app = app
        self.add_css_class("hx-window")
        self.set_hide_on_close(True)
        self.set_size_request(720, 560)
        self.pages: dict[str, DevicePage] = {}
        self._selected: str = "home"
        self._feature: dict[str, str] = {}
        self._expanded: set[str] = set()
        self._battery_labels: dict[str, Gtk.Label] = {}
        self._rebuilding = False

        # sidebar: wordmark, devices, home / settings / about
        self.sidebar = Sidebar()
        head = Gtk.Box(spacing=6, height_request=60, margin_start=16, margin_end=8)
        brand = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER, hexpand=True)
        brand.append(Gtk.Label(label="HYPERX", css_classes=["hx-brand"]))
        brand.append(Gtk.Label(label="LINUX", css_classes=["hx-brand", "hx-brand-accent"]))
        head.append(self.sidebar.track(brand))
        fold = Gtk.Button(icon_name="sidebar-show-symbolic", css_classes=["flat"], valign=Gtk.Align.CENTER,
                          tooltip_text=_("Collapse"))
        fold.connect("clicked", lambda _b: self.sidebar.set_property("collapsed", not self.sidebar.collapsed))
        head.append(fold)
        self.sidebar.append(Gtk.WindowHandle(child=head))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_start=8, margin_end=8)
        body.append(self.sidebar.track(Gtk.Label(label=_("Devices"), xalign=0, css_classes=["hx-sidebar-header"])))
        self.tree = Gtk.ListBox(css_classes=["hx-tree"], selection_mode=Gtk.SelectionMode.SINGLE)
        self.tree.connect("row-activated", self._on_activated)
        body.append(self.tree)
        self.sidebar.append(Gtk.ScrolledWindow(child=body, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.bottom = Gtk.ListBox(css_classes=["hx-tree"], selection_mode=Gtk.SelectionMode.SINGLE,
                                  margin_start=8, margin_end=8, margin_bottom=8)
        for key, icon, label in (("home", "go-home-symbolic", _("Home")),
                                 ("preferences", "emblem-system-symbolic", _("Settings")),
                                 ("about", "help-about-symbolic", _("About"))):
            r = _row(themed(icon, FALLBACK_ICON), label, self.sidebar, tree=False)
            r.key = key
            self.bottom.append(r)
        self.bottom.connect("row-activated", self._on_bottom)
        self.sidebar.append(self.bottom)

        # content: header with the window buttons, the rules banner, the pages
        header = Adw.HeaderBar(show_start_title_buttons=False, css_classes=["flat"])
        header.set_title_widget(Gtk.Label(label=""))
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=_("Refresh"))
        refresh.connect("clicked", self._on_refresh)
        header.pack_end(refresh)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True,
                               vhomogeneous=False, hhomogeneous=False)  # only the page on show counts
        self.home = HomePage(self.open)
        self.stack.add_named(self.home, "home")
        self.toasts = Adw.ToastOverlay(child=self.stack, vexpand=True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        content.append(header)
        group = None if uaccess_supported() else GROUP
        if not IN_FLATPAK and shutil.which("pkexec") and outdated(group):  # rules from an older version
            self.rules_banner = compat.banner(_("This version needs updated permissions (headset buttons, "
                                                "new devices)"), _("Update"), self._update_rules)
            content.append(self.rules_banner)
        content.append(self.toasts)
        root = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
        root.append(self.sidebar)
        root.append(content)
        self.set_content(root)
        if compat.adw(4):  # narrow windows: icons only, like NGENUITY below 1096 px
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 1000px"))
            bp.add_setter(self.sidebar, "collapsed", True)
            self.add_breakpoint(bp)
        self.rebuild()

    # --------------------------------------------------------------- devices
    def rebuild(self) -> None:
        sessions = {s.key: s for s in self.app.manager.list()}
        for key in list(self.pages):
            if key not in sessions:
                self.stack.remove(self.pages.pop(key))
        for key, s in sessions.items():
            if key not in self.pages:
                page = DevicePage(s, self.app.set_control, lambda: self.app.manager.config["low_battery"],
                                  self.app.save_preset)
                page.panel.on_select.append(lambda fid, k=key: self._on_feature(k, fid))
                self.pages[key] = page
                self.stack.add_named(page, key)
        extra = []
        for info in self.app.manager.unsupported:
            if (info.vid, info.pid) in DETECTION_ONLY:
                continue  # e.g. a headset charging over USB-C: the receiver is the device to control
            key = f"unsupported:{info.usb_path or info.path}"
            if self.stack.get_child_by_name(key) is None:
                self.stack.add_named(self._unsupported_page(info), key)
            extra.append((key, display_name(info), _(self._unsupported_label(info)), "dialog-question-symbolic"))
        for key, err in self.app.manager.errors.items():
            info = self.app.manager.failed.get(key)
            if self.stack.get_child_by_name(f"error:{key}") is None:
                self.stack.add_named(self._permission_page(), f"error:{key}")
            extra.append((f"error:{key}", display_name(info) if info else _("No permission to access the device"),
                          _("No permission to access the device") if info else err, "dialog-warning-symbolic"))
        self.home.rebuild(list(sessions.values()), extra)
        self._extra = extra
        if self._selected not in sessions and self._selected not in {k for k, *_r in extra}:
            self._selected = "home"
        self._fill_tree()
        self.stack.set_visible_child_name(self._selected)

    def _fill_tree(self) -> None:
        self._rebuilding = True
        while (row := self.tree.get_row_at_index(0)) is not None:
            self.tree.remove(row)
        self.sidebar.tree_labels.clear()
        self._battery_labels.clear()
        target = None
        for key, page in self.pages.items():
            s = page.session
            battery = Gtk.Label(css_classes=["hx-dim", "caption"])
            self._battery_labels[key] = battery
            r = _row(themed(KIND_ICONS[s.driver.kind], FALLBACK_ICON), s.name, self.sidebar, suffix=battery)
            r.key = ("device", key)
            self.tree.append(r)
            if key == self._selected and key not in self._expanded:
                target = r
            if key in self._expanded:
                for fid, title, icon, _g in features_of(s.controls):
                    fr = _row(themed(icon, FALLBACK_ICON), _(title), self.sidebar, child=True)
                    fr.key = ("feature", key, fid)
                    self.tree.append(fr)
                    if key == self._selected and self._feature.get(key) == fid:
                        target = fr
            self.update_row(s)
        for key, title, _subtitle, icon in self._extra:
            r = _row(icon, title, self.sidebar)
            r.key = ("other", key)
            self.tree.append(r)
            if key == self._selected:
                target = r
        self.tree.select_row(target)
        if self._selected == "home":
            self.bottom.select_row(self.bottom.get_row_at_index(0))
        else:
            self.bottom.unselect_all()
        self._rebuilding = False

    def open(self, key: str, feature: str | None = None) -> None:
        """Show a device (and one of its features), or another page by its key."""
        self._selected = key
        page = self.pages.get(key)
        if page is not None:
            self._expanded = {key}  # one device open at a time
            if feature:
                page.panel.select(feature)
            self._feature[key] = page.panel.current
        self.stack.set_visible_child_name(key)
        self._fill_tree()

    def _on_feature(self, key: str, fid: str) -> None:
        self._feature[key] = fid
        if not self._rebuilding and self._selected == key:
            self._fill_tree()

    def _on_activated(self, _lb, row) -> None:
        kind, key = row.key[0], row.key[1]
        if kind == "device" and key == self._selected and key in self._expanded:
            self._expanded.discard(key)
            self._fill_tree()
        elif kind == "feature":
            self.open(key, row.key[2])
        else:
            self.open(key)

    def _on_bottom(self, _lb, row) -> None:
        if row.key == "home":
            self.open("home")
        else:
            self.app.activate_action(row.key, None)
            self._fill_tree()  # the highlight goes back to the page that is showing

    def _permission_page(self) -> Gtk.Widget:
        page = Adw.StatusPage(icon_name="dialog-warning-symbolic", title=_("No permission to access the device"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        command = Gtk.Label(label=install_command(IN_FLATPAK), selectable=True, wrap=True,
                            css_classes=["monospace", "card"], margin_start=12, margin_end=12)
        command.set_wrap_mode(Pango.WrapMode.CHAR)
        if IN_FLATPAK or not shutil.which("pkexec"):  # the sandbox can't ask for admin rights
            page.set_description(_("Run this once in a terminal; after that, supported devices work "
                                   "as soon as they are plugged in:"))
            box.append(command)
        else:
            page.set_description(_("Allow it once and every supported HyperX device will work "
                                   "as soon as it is plugged in."))
            button = Gtk.Button(label=_("Allow access"), halign=Gtk.Align.CENTER,
                                css_classes=["suggested-action", "pill"])
            status = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, css_classes=["dim-label"])
            button.connect("clicked", lambda b: self._grant_access(b, status))
            box.append(button)
            box.append(status)
            box.append(Gtk.Expander(label=_("Or use a terminal"), child=command, halign=Gtk.Align.CENTER))
        page.set_child(Adw.Clamp(maximum_size=640, child=box))
        return page

    @staticmethod
    def _install_rules(done) -> bool:
        """Install the udev rules as root through polkit; done(ok, cancelled, error text) when finished.
        The manager picks the devices up on its next scan."""
        group = None if uaccess_supported() else GROUP
        try:
            proc = Gio.Subprocess.new(["pkexec", "/bin/sh", "-c", root_script(), "sh", GLib.get_user_name()],
                                      Gio.SubprocessFlags.STDIN_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            done(False, False, e.message)
            return False

        def finished(p: Gio.Subprocess, result: Gio.AsyncResult) -> None:
            try:
                err = p.communicate_utf8_finish(result)[2] or ""
            except GLib.Error as e:
                err = e.message
            # pkexec: 126 = authentication dialog dismissed, 127 = not authorized
            done(p.get_successful(), p.get_exit_status() in (126, 127), err.strip())

        proc.communicate_utf8_async(rules(group), None, finished)
        return True

    def _grant_access(self, button: Gtk.Button, status: Gtk.Label) -> None:
        group = None if uaccess_supported() else GROUP

        def done(ok, cancelled, err):
            if ok:
                status.set_label(_("Done: the device will show up in a moment.") if group is None else
                                 _("Done: log out and back in so your user joins the \"{}\" group.").format(group))
                return
            button.set_sensitive(True)
            status.set_label(_("Cancelled.") if cancelled else
                             (err or _("It didn't work; use the terminal command below.")))

        if self._install_rules(done):
            button.set_sensitive(False)
            status.set_label(_("Waiting for the password…"))

    def _update_rules(self) -> None:
        def done(ok, cancelled, err):
            if ok:
                self.rules_banner.set_visible(False)
                self.toasts.add_toast(Adw.Toast(title=_("Permissions updated")))
            elif not cancelled:
                self.toasts.add_toast(Adw.Toast(title=err or install_command(False), timeout=10))
        self._install_rules(done)

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
        label = self._battery_labels.get(session.key)
        if label is None:
            return
        drv = session.driver
        b = drv.values.get("battery")
        if drv.online is False:
            label.set_label("—")
        elif isinstance(b, C.BatteryValue) and b.level is not None:
            label.set_label(f"{b.level}%" + (" ⚡" if b.charging else ""))
        else:
            label.set_label("")

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
            self.home.update_battery(session.key, session.driver.values.get("battery"))


__all__ = ["Window", "battery_icon"]
