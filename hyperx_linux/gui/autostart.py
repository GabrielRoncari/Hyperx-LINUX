"""Start in the tray at login: an XDG autostart entry, or the Background portal inside Flatpak."""
from __future__ import annotations

import os
import shlex
import shutil
import sys

from gi.repository import Gio, GLib

IN_FLATPAK = os.path.exists("/.flatpak-info")
AUTOSTART_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "autostart")


def _entry_path(app_id: str) -> str:
    return os.path.join(AUTOSTART_DIR, f"{app_id}.desktop")


def is_enabled(app_id: str) -> bool:
    if IN_FLATPAK:
        return False  # the portal can't be queried; the preference is remembered in the config
    return os.path.exists(_entry_path(app_id))


def _command() -> str:
    launcher = shutil.which("hyperx-linux")
    if launcher:
        return f"{shlex.quote(launcher)} --background"
    # running from a checkout: same interpreter and package path as now
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return f"env PYTHONPATH={shlex.quote(root)} {shlex.quote(sys.executable)} -m hyperx_linux --background"


def set_enabled(app_id: str, enabled: bool) -> None:
    if IN_FLATPAK:
        _request_background(enabled)
        return
    path = _entry_path(app_id)
    if not enabled:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    with open(path, "w") as f:
        f.write(f"[Desktop Entry]\nType=Application\nName=HyperX Linux\nIcon={app_id}\n"
                f"Exec={_command()}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n")


def _request_background(enabled: bool) -> None:
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    except GLib.Error:
        return
    options = {
        "reason": GLib.Variant("s", "Show battery and microphone status in the tray"),
        "autostart": GLib.Variant("b", enabled),
        "commandline": GLib.Variant("as", ["hyperx-linux", "--background"]),
    }
    bus.call("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
             "org.freedesktop.portal.Background", "RequestBackground",
             GLib.Variant("(sa{sv})", ("", options)), None, Gio.DBusCallFlags.NONE, -1, None, None)
