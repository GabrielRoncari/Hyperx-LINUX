"""Tray icon via StatusNotifierItem + com.canonical.dbusmenu (plain Gio).

Works with any StatusNotifierWatcher: KDE, COSMIC, GNOME with the AppIndicator extension, waybar...
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from gi.repository import Gio, GLib

SNI_XML = """
<node>
 <interface name="org.kde.StatusNotifierItem">
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="WindowId" type="i" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="IconThemePath" type="s" access="read"/>
  <property name="OverlayIconName" type="s" access="read"/>
  <property name="AttentionIconName" type="s" access="read"/>
  <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <method name="ContextMenu"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="Activate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/></method>
  <method name="Scroll"><arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/></method>
  <signal name="NewTitle"/>
  <signal name="NewIcon"/>
  <signal name="NewToolTip"/>
  <signal name="NewStatus"><arg name="status" type="s"/></signal>
 </interface>
</node>
"""

MENU_XML = """
<node>
 <interface name="com.canonical.dbusmenu">
  <property name="Version" type="u" access="read"/>
  <property name="TextDirection" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="IconThemePath" type="as" access="read"/>
  <method name="GetLayout">
   <arg type="i" name="parentId" direction="in"/>
   <arg type="i" name="recursionDepth" direction="in"/>
   <arg type="as" name="propertyNames" direction="in"/>
   <arg type="u" name="revision" direction="out"/>
   <arg type="(ia{sv}av)" name="layout" direction="out"/>
  </method>
  <method name="GetGroupProperties">
   <arg type="ai" name="ids" direction="in"/>
   <arg type="as" name="propertyNames" direction="in"/>
   <arg type="a(ia{sv})" name="properties" direction="out"/>
  </method>
  <method name="GetProperty">
   <arg type="i" name="id" direction="in"/>
   <arg type="s" name="name" direction="in"/>
   <arg type="v" name="value" direction="out"/>
  </method>
  <method name="Event">
   <arg type="i" name="id" direction="in"/>
   <arg type="s" name="eventId" direction="in"/>
   <arg type="v" name="data" direction="in"/>
   <arg type="u" name="timestamp" direction="in"/>
  </method>
  <method name="EventGroup">
   <arg type="a(isvu)" name="events" direction="in"/>
   <arg type="ai" name="idErrors" direction="out"/>
  </method>
  <method name="AboutToShow">
   <arg type="i" name="id" direction="in"/>
   <arg type="b" name="needUpdate" direction="out"/>
  </method>
  <method name="AboutToShowGroup">
   <arg type="ai" name="ids" direction="in"/>
   <arg type="ai" name="updatesNeeded" direction="out"/>
   <arg type="ai" name="idErrors" direction="out"/>
  </method>
  <signal name="ItemsPropertiesUpdated">
   <arg type="a(ia{sv})" name="updatedProps"/>
   <arg type="a(ias)" name="removedProps"/>
  </signal>
  <signal name="LayoutUpdated">
   <arg type="u" name="revision"/>
   <arg type="i" name="parent"/>
  </signal>
 </interface>
</node>
"""

SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
WATCHER = "org.kde.StatusNotifierWatcher"


@dataclass
class MenuItem:
    label: str = ""
    action: Callable[[], None] | None = None
    enabled: bool = True
    separator: bool = False
    checked: bool | None = None  # None: no checkbox

    def props(self) -> dict:
        if self.separator:
            return {"type": GLib.Variant("s", "separator")}
        p = {
            "label": GLib.Variant("s", self.label),
            "enabled": GLib.Variant("b", self.enabled),
            "visible": GLib.Variant("b", True),
        }
        if self.checked is not None:
            p["toggle-type"] = GLib.Variant("s", "checkmark")
            p["toggle-state"] = GLib.Variant("i", 1 if self.checked else 0)
        return p


@dataclass
class Tray:
    app_id: str
    title: str
    on_activate: Callable[[], None]
    icon: str = "audio-headset-symbolic"
    tooltip: str = ""
    items: list[MenuItem] = field(default_factory=list)
    pixmaps: list[tuple[int, int, bytes]] | None = None  # drawn icon; takes precedence over `icon`

    def __post_init__(self):
        self._revision = 1
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        # Inside Flatpak the app may not own arbitrary bus names, so it registers its unique
        # connection name instead (allowed by the spec; KDE, COSMIC and AppIndicator accept it).
        self._in_flatpak = os.path.exists("/.flatpak-info")
        self._name = self._bus.get_unique_name() if self._in_flatpak else f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        sni = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self._regs = [
            self._bus.register_object(SNI_PATH, sni, self._sni_call, self._sni_prop, None),
            self._bus.register_object(MENU_PATH, menu, self._menu_call, self._menu_prop, None),
        ]
        if not self._in_flatpak:
            Gio.bus_own_name_on_connection(self._bus, self._name, Gio.BusNameOwnerFlags.NONE, None, None)
        # Register now, and again whenever the panel (watcher) restarts.
        Gio.bus_watch_name_on_connection(
            self._bus, WATCHER, Gio.BusNameWatcherFlags.NONE, lambda *a: self._register(), None
        )

    def _register(self) -> None:
        self._bus.call(
            WATCHER, "/StatusNotifierWatcher", WATCHER, "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self._name,)), None, Gio.DBusCallFlags.NONE, -1, None, None,
        )

    def _emit(self, path: str, iface: str, signal: str, params: GLib.Variant | None = None) -> None:
        self._bus.emit_signal(None, path, iface, signal, params)

    # ------------------------------------------------------------- API
    def update(self, icon: str | None = None, tooltip: str | None = None,
               pixmaps: list[tuple[int, int, bytes]] | None = None) -> None:
        if (icon is not None and icon != self.icon) or pixmaps != self.pixmaps:
            self.icon = icon if icon is not None else self.icon
            self.pixmaps = pixmaps
            self._emit(SNI_PATH, "org.kde.StatusNotifierItem", "NewIcon")
        if tooltip is not None and tooltip != self.tooltip:
            self.tooltip = tooltip
            self._emit(SNI_PATH, "org.kde.StatusNotifierItem", "NewToolTip")
            self._emit(SNI_PATH, "org.kde.StatusNotifierItem", "NewTitle")

    def set_menu(self, items: list[MenuItem]) -> None:
        self.items = items
        self._revision += 1
        self._emit(MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated", GLib.Variant("(ui)", (self._revision, 0)))

    # ------------------------------------------------------------- SNI
    def _sni_prop(self, conn, sender, path, iface, name):
        values = {
            "Category": GLib.Variant("s", "Hardware"),
            "Id": GLib.Variant("s", self.app_id),
            "Title": GLib.Variant("s", self.tooltip or self.title),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            # an empty name makes hosts use the pixmap (KDE, COSMIC); themed name otherwise
            "IconName": GLib.Variant("s", "" if self.pixmaps else self.icon),
            "IconPixmap": GLib.Variant("a(iiay)", self.pixmaps or []),
            "IconThemePath": GLib.Variant("s", ""),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", (self.icon, [], self.title, self.tooltip)),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
        }
        return values.get(name)

    def _sni_call(self, conn, sender, path, iface, method, params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self.on_activate)
        invocation.return_value(None)

    # ------------------------------------------------------------ menu
    def _item_variant(self, idx: int) -> GLib.Variant:
        return GLib.Variant("(ia{sv}av)", (idx + 1, self.items[idx].props(), []))

    def _layout(self) -> GLib.Variant:
        root = {"children-display": GLib.Variant("s", "submenu")}
        children = [self._item_variant(i) for i in range(len(self.items))]
        return GLib.Variant("(u(ia{sv}av))", (self._revision, (0, root, children)))

    def _props_of(self, item_id: int) -> dict:
        if item_id == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        if 1 <= item_id <= len(self.items):
            return self.items[item_id - 1].props()
        return {}

    def _menu_prop(self, conn, sender, path, iface, name):
        return {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }.get(name)

    def _fire(self, item_id: int, event: str) -> None:
        if event == "clicked" and 1 <= item_id <= len(self.items):
            action = self.items[item_id - 1].action
            if action:
                GLib.idle_add(action)

    def _menu_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "GetLayout":
            invocation.return_value(self._layout())
        elif method == "GetGroupProperties":
            ids = params.unpack()[0]
            ids = ids or list(range(len(self.items) + 1))
            out = [(i, self._props_of(i)) for i in ids]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (out,)))
        elif method == "GetProperty":
            item_id, name = params.unpack()
            value = self._props_of(item_id).get(name, GLib.Variant("s", ""))
            invocation.return_value(GLib.Variant("(v)", (value,)))
        elif method == "Event":
            item_id, event, _data, _ts = params.unpack()
            self._fire(item_id, event)
            invocation.return_value(None)
        elif method == "EventGroup":
            for item_id, event, _data, _ts in params.unpack()[0]:
                self._fire(item_id, event)
            invocation.return_value(GLib.Variant("(ai)", ([],)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            invocation.return_value(None)


class Notifier:
    """org.freedesktop.Notifications directly, so a notification can replace the previous one by key."""

    def __init__(self, app_name: str, icon: str = "audio-headset-symbolic"):
        self.app_name = app_name
        self.icon = icon
        self._ids: dict[str, int] = {}
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        except GLib.Error:
            self._bus = None

    def notify(self, key: str, summary: str, body: str = "", icon: str | None = None,
               urgency: int = 1, timeout_ms: int = 4000) -> None:
        if self._bus is None:
            return
        hints = {"urgency": GLib.Variant("y", urgency), "transient": GLib.Variant("b", urgency < 2)}
        params = GLib.Variant(
            "(susssasa{sv}i)",
            (self.app_name, self._ids.get(key, 0), icon or self.icon, summary, body, [], hints, timeout_ms),
        )

        def done(bus, res):
            try:
                self._ids[key] = bus.call_finish(res).unpack()[0]
            except GLib.Error:
                pass

        self._bus.call(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications", "Notify", params, GLib.VariantType("(u)"),
            Gio.DBusCallFlags.NONE, -1, None, done,
        )
