"""Application: manager lifecycle, tray icon, notifications and preferences."""
from __future__ import annotations

import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import APP_ID, REPO_URL, __version__  # noqa: E402
from .. import controls as C  # noqa: E402
from ..i18n import _  # noqa: E402
from ..manager import Manager, Session  # noqa: E402
from .page import battery_icon  # noqa: E402
from . import autostart, compat, theme  # noqa: E402
from .tray import MenuItem, Notifier, Tray  # noqa: E402
from .trayicon import battery_pixmaps  # noqa: E402
from .window import APP_NAME, Window  # noqa: E402

USER_ECHO_S = 2.0  # changes made from the UI don't raise notifications

class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.manager = Manager()
        self.manager.on_change = lambda s, k, v: GLib.idle_add(self._on_change, s, k, v)
        self.window: Window | None = None
        self.tray: Tray | None = None
        self.notifier = Notifier(APP_NAME)
        self._user_set: dict[tuple[str, str], float] = {}
        self._low_warned: set[str] = set()
        self._seen: dict[tuple[str, str], object] = {}  # last value per (device, key) for notifications
        self._last_menu = None
        self.add_main_option("background", ord("b"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _("Show in tray only"), None)

    # -------------------------------------------------------------- lifecycle
    def do_startup(self):
        Adw.Application.do_startup(self)
        self.hold()  # keep running in the tray with the window closed
        theme.apply()
        for name, cb in (("about", self._about), ("quit", lambda *_a: self._quit()),
                         ("show", lambda *_a: self.show_window()), ("preferences", self._preferences)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", cb)
            self.add_action(act)
        self.set_accels_for_action("app.quit", ["<Ctrl>q"])
        try:
            self.tray = Tray(app_id="hyperx-linux", title=APP_NAME, on_activate=self.show_window)
        except GLib.Error as e:
            print(f"tray unavailable: {e.message}", file=sys.stderr)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_a: self._update_tray(force=True))
        self._update_tray()
        self._watch_sleep()
        self.manager.start()

    def _watch_sleep(self):
        """Pause lighting streams before suspend: some keyboards stop waking the PC otherwise."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
        except GLib.Error:
            return

        def on_signal(_conn, _sender, _path, _iface, _signal, params):
            self.manager.paused = bool(params.unpack()[0])
        bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
                             "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, on_signal)

    def do_command_line(self, cmdline):
        opts = cmdline.get_options_dict().end().unpack()
        if not opts.get("background") or self.window is not None:
            self.show_window()
        return 0

    def show_window(self):
        if self.window is None:
            self.window = Window(self)
        self.window.present()
        return False

    def _quit(self):
        self.manager.stop()
        self.quit()

    # ---------------------------------------------------------------- actions
    def set_control(self, session: Session, control_id: str, value, live: bool) -> None:
        self._user_set[(session.key, control_id)] = time.monotonic()
        session.set(control_id, value, live)

    def save_preset(self, session: Session, name: str | None) -> None:
        self.manager.config.set_device_value(session.driver_id, "eq_preset", name)

    def _about(self, *_a):
        compat.present_about(self.window, APP_NAME, app_icon(), __version__, REPO_URL,
                             _("Linux control panel for HyperX peripherals (unofficial)."))

    def _preferences(self, *_a):
        cfg = self.manager.config
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title=_("Preferences"))
        rows = []
        for key, title, subtitle in (
            ("notifications", "Desktop notifications", ""),
            ("notify_mic", "Notify when the microphone is muted", ""),
            ("allow_experimental", "Allow experimental drivers",
             "Lets drivers that nobody has tested on real hardware change settings"),
        ):
            row, switch = compat.switch_row(_(title), _(subtitle), bool(cfg[key]))
            switch.connect("notify::active", lambda w, _p, k=key: self._set_pref(k, w.get_active()))
            rows.append(row)
        start = autostart.is_enabled(APP_ID) or bool(cfg.data.get("autostart"))
        row, switch = compat.switch_row(_("Start in the tray at login"), "", start)
        switch.connect("notify::active", lambda w, _p: self._set_autostart(w.get_active()))
        rows.append(row)
        low, spin = compat.spin_row(_("Low battery warning (%)"), "", 5, 50, 5)
        spin.set_value(cfg["low_battery"])
        spin.connect("notify::value", lambda w, _p: self._set_pref("low_battery", int(w.get_value())))
        for row in (*rows, low):
            group.add(row)
        page.add(group)
        compat.present_preferences(self.window, page)

    def _set_autostart(self, enabled: bool) -> None:
        autostart.set_enabled(APP_ID, enabled)
        self.manager.config["autostart"] = enabled

    def _set_pref(self, key, value):
        self.manager.config[key] = value
        if key == "allow_experimental" and self.window:
            for page in list(self.window.pages):  # rebuild pages so rows pick up the new permission
                self.window.stack.remove(self.window.pages.pop(page))
            self.window.rebuild()

    # ----------------------------------------------------------------- events
    def _on_change(self, session: Session | None, key: str, value):
        if session is None:  # device list changed
            if self.window:
                self.window.rebuild()
        else:
            if self.window:
                self.window.on_change(session, key, value)
            self._maybe_notify(session, key, value)
        self._update_tray()
        return False

    def _notify(self, key, summary, body="", icon=None, urgency=1):
        if self.manager.config["notifications"]:
            self.notifier.notify(key, summary, body, icon, urgency)

    def _maybe_notify(self, s: Session, key: str, value) -> None:
        recent = time.monotonic() - self._user_set.get((s.key, key), 0) < USER_ECHO_S
        if key == "battery" and isinstance(value, C.BatteryValue) and value.level is not None:
            low = self.manager.config["low_battery"]
            if value.level <= low and not value.charging and s.key not in self._low_warned:
                self._low_warned.add(s.key)
                self._notify(f"battery:{s.key}", _("Low battery: {level}%", level=value.level),
                             f"{s.name} · {_('Charge it soon.')}", "battery-level-10-symbolic", urgency=2)
            elif value.level > low:
                self._low_warned.discard(s.key)
            if value.full and self._seen.get((s.key, "full")) is False:
                self._notify(f"battery:{s.key}", _("Fully charged"), s.name, "battery-level-100-charged-symbolic")
            self._seen[(s.key, "full")] = value.full
        elif key == "mic_mute" and self.manager.config["notify_mic"] and not recent:
            if (s.key, "mic_mute") in self._seen:
                if value:
                    self._notify(f"mic:{s.key}", _("Microphone muted"), s.name, "microphone-sensitivity-muted-symbolic")
                else:
                    self._notify(f"mic:{s.key}", _("Microphone on"), s.name, "audio-input-microphone-symbolic")
            self._seen[(s.key, "mic_mute")] = value
        elif key == "online" and value is not None:
            prev = self._seen.get((s.key, "online"))
            if prev is not None and prev != value:
                text = _("{name} connected", name=s.name) if value else _("{name} disconnected", name=s.name)
                self._notify(f"link:{s.key}", text, "", None if value else "battery-missing-symbolic")
            self._seen[(s.key, "online")] = value

    # ------------------------------------------------------------------- tray
    def _update_tray(self, force: bool = False):
        if not self.tray:
            return
        sessions = self.manager.list()
        lines, items = [], []
        main_battery = None
        for s in sessions:
            drv = s.driver
            b = drv.values.get("battery")
            if drv.online is False:
                text = _("Device off or out of range")
            elif isinstance(b, C.BatteryValue) and b.level is not None:
                text = _("Battery {level}%", level=b.level) + (f" ({_('charging')})" if b.charging else "")
                if main_battery is None:
                    main_battery = (b, drv.online)
            else:
                text = _("Connected")
            if drv.values.get("mic_mute"):
                text += f" · {_('mic muted')}"
            lines.append(f"{s.name}: {text}")
            items.append(MenuItem(label=f"{s.name}: {text}", enabled=False))
            if any(c.id == "mic_mute" for c in drv.controls) and drv.online and s.writable:
                items.append(MenuItem(label=_("Mute microphone"), checked=bool(drv.values.get("mic_mute")),
                                      action=lambda s=s: self.set_control(s, "mic_mute",
                                                                         not s.driver.values.get("mic_mute"), False)))
        icon = battery_icon(*main_battery) if main_battery else "audio-headset-symbolic"
        pixmaps = None
        if main_battery:
            b, online = main_battery
            dark = Adw.StyleManager.get_default().get_dark()
            low = b.level is not None and b.level <= self.manager.config["low_battery"]
            pixmaps = battery_pixmaps(b.level if online else None, bool(b.charging), low, dark)
        tooltip = "\n".join(lines) or _("No HyperX device found")
        if force:
            self.tray.pixmaps = None  # make update() emit NewIcon
        self.tray.update(icon=icon, tooltip=tooltip, pixmaps=pixmaps)
        menu = items + [MenuItem(separator=True), MenuItem(label=_("Open"), action=self.show_window),
                        MenuItem(label=_("Quit"), action=self._quit)]
        key = tuple((m.label, m.enabled, m.checked, m.separator) for m in menu)
        if key != self._last_menu:
            self._last_menu = key
            self.tray.set_menu(menu)


def app_icon() -> str:
    icons = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    return APP_ID if icons.has_icon(APP_ID) else "audio-headset"


def main(argv=None) -> int:
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        print(_("No graphical session found. The command line works anywhere: hyperx-linux -h"), file=sys.stderr)
        return 1
    # running from a checkout: the app icon isn't installed in an icon theme yet
    icons = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "icons")
    if os.path.isdir(icons):
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(icons)
    Gtk.Window.set_default_icon_name(APP_ID)
    return App().run(argv if argv is not None else sys.argv)
