"""Run on older GTK 4 / libadwaita too (oldest target: GTK 4.6 + libadwaita 1.1, Ubuntu 22.04).

Each helper uses the modern widget when the running library has it and an equivalent built from
older widgets otherwise, so the rest of the GUI doesn't care which versions are installed.
"""
from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

def _cairo_ok() -> bool:
    """PyGObject can hand cairo contexts to Python (python3-gi-cairo on Debian/Ubuntu); without it,
    every cairo draw function raises "Couldn't find foreign struct converter for 'cairo.Context'"."""
    try:
        gi.require_foreign("cairo")
        return True
    except ImportError:
        return False


CAIRO = _cairo_ok()
ADW = (Adw.get_major_version(), Adw.get_minor_version())
GTK = (Gtk.get_major_version(), Gtk.get_minor_version())
CENTER = Gtk.Align.CENTER


def adw(minor: int) -> bool:
    return ADW >= (1, minor)


def gtk(minor: int) -> bool:
    return GTK >= (4, minor)


def load_css(provider: Gtk.CssProvider, css: str) -> None:
    if hasattr(provider, "load_from_string"):  # GTK 4.12
        provider.load_from_string(css)
        return
    try:
        provider.load_from_data(css, -1)
    except TypeError:  # older PyGObject maps the argument to bytes
        provider.load_from_data(css.encode())


def switch_row(title: str, subtitle: str = "", active: bool = False):
    """(row, switch); use notify::active and get/set_active on `switch`."""
    if adw(4):
        row = Adw.SwitchRow(title=title, subtitle=subtitle, active=active)
        return row, row
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    switch = Gtk.Switch(active=active, valign=CENTER)
    row.add_suffix(switch)
    row.set_activatable_widget(switch)
    return row, switch


def spin_row(title: str, subtitle: str, lo: float, hi: float, step: float):
    """(row, spin); use notify::value and get/set_value on `spin`."""
    if adw(4):
        row = Adw.SpinRow.new_with_range(lo, hi, step)
        row.set_title(title)
        row.set_subtitle(subtitle)
        return row, row
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    spin = Gtk.SpinButton.new_with_range(lo, hi, step)
    spin.set_valign(CENTER)
    row.add_suffix(spin)
    return row, spin


def property_row(title: str, subtitle: str = "") -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    if adw(3):
        row.set_subtitle_selectable(True)
    row.add_css_class("property")
    return row


def color_button() -> Gtk.Widget:
    """A colour picker button with get_rgba/set_rgba and notify::rgba."""
    if gtk(10):
        return Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), valign=CENTER)
    button = Gtk.ColorButton(valign=CENTER)
    button.set_use_alpha(False)
    return button


def wheel_units(ctl: Gtk.EventControllerScroll) -> bool:
    """True when scroll deltas are wheel clicks (always true before GTK 4.8)."""
    return not hasattr(ctl, "get_unit") or ctl.get_unit() == Gdk.ScrollUnit.WHEEL


def banner(title: str, button_label: str, on_click: Callable[[], None]) -> Gtk.Widget:
    if adw(3):
        b = Adw.Banner(title=title, revealed=True, button_label=button_label)
        b.connect("button-clicked", lambda *_a: on_click())
        return b
    box = Gtk.Box(spacing=12, css_classes=["compat-banner"])
    box.append(Gtk.Label(label=title, wrap=True, xalign=0, hexpand=True))
    button = Gtk.Button(label=button_label, valign=CENTER)
    button.connect("clicked", lambda *_a: on_click())
    box.append(button)
    return box


def toolbar_view(header: Gtk.Widget, content: Gtk.Widget) -> Gtk.Widget:
    if adw(4):
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(content)
        return view
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    content.set_vexpand(True)
    box.append(header)
    box.append(content)
    return box


class SplitView:
    """Sidebar + content: adaptive NavigationSplitView (libadwaita 1.4+), a fixed Gtk.Paned before."""

    def __init__(self, window: Adw.ApplicationWindow, sidebar: Gtk.Widget, sidebar_title: str,
                 content: Gtk.Widget, content_title: str, collapse_below_sp: int):
        self._split = None
        if adw(4):
            self._split = Adw.NavigationSplitView(
                sidebar=Adw.NavigationPage(child=sidebar, title=sidebar_title),
                content=Adw.NavigationPage(child=content, title=content_title),
            )
            window.set_content(self._split)
            # sp follows the font DPI; sessions without xsettings or the settings portal (sway, i3…)
            # report none (-1), which libadwaita 1.4 turns into a ~0 px sidebar and a dead breakpoint
            unit = "sp" if Gtk.Settings.get_default().props.gtk_xft_dpi > 0 else "px"
            if unit == "px":
                self._split.set_sidebar_width_unit(Adw.LengthUnit.PX)
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(f"max-width: {collapse_below_sp}{unit}"))
            bp.add_setter(self._split, "collapsed", True)
            window.add_breakpoint(bp)
        else:
            paned = Gtk.Paned(start_child=sidebar, end_child=content, position=270,
                              resize_start_child=False, shrink_start_child=False, shrink_end_child=False)
            window.set_content(paned)

    def show_content(self) -> None:
        if self._split is not None:
            self._split.set_show_content(True)

    @property
    def collapsed(self) -> bool:
        return self._split is not None and self._split.get_collapsed()


def present_about(parent: Gtk.Window | None, name: str, icon: str, version: str, website: str,
                  comments: str) -> None:
    common = dict(version=version, website=website, license_type=Gtk.License.GPL_3_0, comments=comments)
    if adw(5):
        Adw.AboutDialog(application_name=name, application_icon=icon, **common).present(parent)
    elif adw(2):
        Adw.AboutWindow(transient_for=parent, application_name=name, application_icon=icon, **common).present()
    else:
        Gtk.AboutDialog(transient_for=parent, program_name=name, logo_icon_name=icon, **common).present()


def present_preferences(parent: Gtk.Window | None, page: Adw.PreferencesPage) -> None:
    if adw(5):
        dialog = Adw.PreferencesDialog()
        dialog.add(page)
        dialog.present(parent)
    else:
        window = Adw.PreferencesWindow(transient_for=parent)
        window.add(page)
        window.present()


def confirm(parent: Gtk.Widget, heading: str, body: str, accept: str, cancel: str,
            on_accept: Callable[[], None]) -> None:
    """Ask before something destructive; on_accept runs only on the destructive button."""
    window = parent.get_root() if parent is not None else None
    if adw(5):
        d = Adw.AlertDialog(heading=heading, body=body)
    elif adw(2):
        d = Adw.MessageDialog(transient_for=window, heading=heading, body=body, modal=True)
    else:
        d = Gtk.MessageDialog(transient_for=window, modal=True, buttons=Gtk.ButtonsType.NONE,
                              text=heading, secondary_text=body)
        d.add_button(cancel, Gtk.ResponseType.CANCEL)
        d.add_button(accept, Gtk.ResponseType.ACCEPT).add_css_class("destructive-action")
        d.connect("response", lambda dlg, r: (dlg.destroy(), r == Gtk.ResponseType.ACCEPT and on_accept()))
        d.present()
        return
    d.add_response("cancel", cancel)
    d.add_response("accept", accept)
    d.set_response_appearance("accept", Adw.ResponseAppearance.DESTRUCTIVE)
    d.connect("response", lambda _d, r: r == "accept" and on_accept())
    if adw(5):
        d.present(window)
    else:
        d.present()
