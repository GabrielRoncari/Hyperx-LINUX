"""The feature panel at the bottom of a device page, shaped like NGENUITY's: a rounded panel whose top
edge is 40 px down, with a raised trapezoid tab in the middle holding one icon per feature."""
from __future__ import annotations

import math
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..i18n import _  # noqa: E402
from . import compat  # noqa: E402

TAB_TOP = 40  # where the panel body starts
ICON, GAP = 24, 32
HEIGHT = 360
PANEL_RGBA = (30 / 255, 30 / 255, 31 / 255, 0.85)


def tab_width(n: int) -> float:
    """NGENUITY's formula for the top of the tab: 28 + 24n + 32(n − 1)."""
    return 28 + ICON * n + GAP * max(0, n - 1)


def outline(cr, width: float, height: float, n: int, inset: float = 0.0) -> None:
    """Panel + tab path; the tab's sides slope out 28 px, corners round by 6 (8 on the panel)."""
    w = tab_width(n)
    i = inset
    cx = width / 2
    top_l, top_r = cx - w / 2 + i, cx + w / 2 - i
    base_l, base_r = cx - w / 2 - 28 + i, cx + w / 2 + 28 - i
    y0, y1 = i, TAB_TOP + i
    r, rt = 8 - i, 6
    cr.new_path()
    cr.move_to(i, y1 + r)
    cr.arc(i + r, y1 + r, r, math.pi, 1.5 * math.pi)
    cr.line_to(base_l - rt, y1)
    cr.curve_to(base_l, y1, base_l, y1, base_l + rt * 0.6, y1 - rt * 0.8)  # foot of the left slope
    cr.line_to(top_l - rt * 0.6, y0 + rt * 0.8)
    cr.curve_to(top_l, y0, top_l, y0, top_l + rt, y0)  # top-left corner of the tab
    cr.line_to(top_r - rt, y0)
    cr.curve_to(top_r, y0, top_r, y0, top_r + rt * 0.6, y0 + rt * 0.8)
    cr.line_to(base_r - rt * 0.6, y1 - rt * 0.8)
    cr.curve_to(base_r, y1, base_r, y1, base_r + rt, y1)
    cr.line_to(width - i - r, y1)
    cr.arc(width - i - r, y1 + r, r, 1.5 * math.pi, 2 * math.pi)
    cr.line_to(width - i, height - i - r)
    cr.arc(width - i - r, height - i - r, r, 0, 0.5 * math.pi)
    cr.line_to(i + r, height - i)
    cr.arc(i + r, height - i - r, r, 0.5 * math.pi, math.pi)
    cr.close_path()


class FeaturePanel(Gtk.Overlay):
    """add_feature() each feature, then select(id). open_editor() lays a full editor over the panel
    (NGENUITY opens editors like the equalizer this way); on_select listeners get the feature id."""

    def __init__(self):
        super().__init__(height_request=HEIGHT, vexpand=False, hexpand=True)
        self.features: list[str] = []
        self.on_select: list[Callable[[str], None]] = []
        self.current: str | None = None
        self._editor: Gtk.Widget | None = None
        self.tabs = Gtk.Box(spacing=GAP - 8, halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=8)
        if compat.CAIRO:
            self.shape = Gtk.DrawingArea(hexpand=True, vexpand=True)
            self.shape.set_draw_func(self._draw)
        else:  # no cairo for Python: a plain panel with the tabs on a rounded strip
            self.shape = Gtk.Box(hexpand=True, vexpand=True, margin_top=TAB_TOP, css_classes=["hx-panel-plain"])
            self.tabs.add_css_class("hx-tabs-plain")
        self.set_child(self.shape)

        self.add_overlay(self.tabs)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=TAB_TOP + 10,
                       margin_bottom=12, margin_start=14, margin_end=14)
        self.title = Gtk.Label(xalign=0, css_classes=["hx-panel-title"])
        self.title_row = Gtk.Box(spacing=8)
        self.title_row.append(self.title)
        self.extra = Gtk.Box(spacing=8, hexpand=True, halign=Gtk.Align.END)  # e.g. an on/off switch
        self.title_row.append(self.extra)
        body.append(self.title_row)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True,
                               hhomogeneous=False)  # the widest feature mustn't widen the others
        body.append(self.stack)
        self.add_overlay(body)
        self._buttons: dict[str, Gtk.ToggleButton] = {}
        self._titles: dict[str, str] = {}
        self._extras: dict[str, Gtk.Widget] = {}

    def _draw(self, _area, cr, width, height):
        n = max(1, len(self.features))
        outline(cr, width, height, n)
        cr.set_source_rgba(*PANEL_RGBA)
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.8)  # BrushGenericBorder
        cr.set_line_width(1)
        cr.stroke()
        outline(cr, width, height, n, inset=1.5)
        cr.set_source_rgba(1, 1, 1, 0.2)  # BrushGenericInnerBorder
        cr.stroke()

    def add_feature(self, fid: str, title: str, icon: str, child: Gtk.Widget, extra: Gtk.Widget | None = None):
        button = Gtk.ToggleButton(child=Gtk.Image(icon_name=icon, pixel_size=ICON), tooltip_text=title,
                                  css_classes=["flat", "hx-feature-tab"])
        if self._buttons:
            button.set_group(next(iter(self._buttons.values())))
        button.connect("toggled", lambda b, f=fid: b.get_active() and self.select(f))
        self.tabs.append(button)
        self._buttons[fid] = button
        self._titles[fid] = title
        if extra is not None:
            self._extras[fid] = extra
        self.features.append(fid)
        # on a narrow window the sections scroll sideways instead of spilling out of the panel
        self.stack.add_named(Gtk.ScrolledWindow(child=child, vscrollbar_policy=Gtk.PolicyType.NEVER,
                                                hscrollbar_policy=Gtk.PolicyType.AUTOMATIC), fid)
        self.shape.queue_draw()

    def select(self, fid: str) -> None:
        if fid not in self._buttons:
            return
        self.close_editor()
        if not self._buttons[fid].get_active():
            self._buttons[fid].set_active(True)
            return  # the toggled handler comes back here
        if self.current == fid:
            return
        self.current = fid
        self.stack.set_visible_child_name(fid)
        self.title.set_label(self._titles[fid])
        while (child := self.extra.get_first_child()) is not None:
            self.extra.remove(child)
        if fid in self._extras:
            self.extra.append(self._extras[fid])
        for fn in self.on_select:
            fn(fid)

    # ----------------------------------------------------------- editors
    def open_editor(self, title: str, child: Gtk.Widget) -> None:
        """A full-size editor over the panel, with its title and a close button."""
        self.close_editor()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["hx-overlay"])
        head = Gtk.Box(spacing=8, margin_top=10, margin_start=14, margin_end=8)
        head.append(Gtk.Label(label=title, xalign=0, hexpand=True, css_classes=["hx-panel-title"]))
        close = Gtk.Button(icon_name="window-close-symbolic", tooltip_text=_("Close"), css_classes=["flat"])
        close.connect("clicked", lambda _b: self.close_editor())
        head.append(close)
        box.append(head)
        holder = Gtk.Box(margin_start=14, margin_end=14, margin_bottom=12, vexpand=True)
        if child.get_parent() is not None:
            child.unparent()
        holder.append(child)
        box.append(holder)
        self._editor = box
        self.add_overlay(box)

    def close_editor(self) -> None:
        if self._editor is not None:
            holder = self._editor.get_last_child()
            child = holder.get_first_child()
            if child is not None:
                holder.remove(child)  # editors are kept by their owner and reopened later
            self.remove_overlay(self._editor)
            self._editor = None
