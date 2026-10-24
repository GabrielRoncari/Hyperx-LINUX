"""Device illustrations drawn with cairo, for the device preview (NGENUITY shows product photos; these
are our own drawings). Each function draws into a w x h box with the device centred."""
from __future__ import annotations

import math

ACCENT = (0.816, 0.133, 0.224)  # #d02239


def _round_rect(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _body(cr, x0, y0, x1, y1, light=0.20, dark=0.07):
    """Fill the current path with a soft top-to-bottom shade, then outline it faintly."""
    import cairo
    g = cairo.LinearGradient(x0, y0, x1, y1)
    g.add_color_stop_rgb(0, light, light, light + 0.01)
    g.add_color_stop_rgb(1, dark, dark, dark + 0.01)
    cr.set_source(g)
    cr.fill_preserve()
    cr.set_source_rgba(1, 1, 1, 0.10)
    cr.set_line_width(1.2)
    cr.stroke()


def _glow(cr, cx, cy, radius, color, alpha=0.35):
    import cairo
    g = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
    g.add_color_stop_rgba(0, *color, alpha)
    g.add_color_stop_rgba(1, *color, 0)
    cr.set_source(g)
    cr.arc(cx, cy, radius, 0, 2 * math.pi)
    cr.fill()


def headset(cr, w, h, accent=ACCENT):
    s = min(w / 300, h / 300)
    cr.save()
    cr.translate(w / 2 - 150 * s, h / 2 - 150 * s)
    cr.scale(s, s)
    _glow(cr, 150, 175, 150, accent, 0.18)
    # headband
    cr.set_line_width(18)
    cr.set_source_rgb(0.13, 0.13, 0.14)
    cr.arc(150, 150, 105, math.pi * 1.05, math.pi * 1.95)
    cr.stroke()
    cr.set_line_width(4)
    cr.set_source_rgba(*accent, 0.9)
    cr.arc(150, 150, 96, math.pi * 1.12, math.pi * 1.88)
    cr.stroke()
    for side in (-1, 1):
        cx = 150 + side * 100
        # fork
        cr.set_line_width(6)
        cr.set_source_rgb(0.30, 0.30, 0.32)
        cr.move_to(cx - 18 * side, 120)
        cr.line_to(cx - 18 * side, 150)
        cr.stroke()
        # ear cup
        cr.save()
        cr.translate(cx, 195)
        cr.scale(0.72, 1)
        cr.arc(0, 0, 62, 0, 2 * math.pi)
        cr.restore()
        _body(cr, cx, 135, cx, 255)
        cr.save()
        cr.translate(cx, 195)
        cr.scale(0.72, 1)
        cr.arc(0, 0, 40, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgba(*accent, 0.85)
        cr.set_line_width(3)
        cr.stroke()
    # microphone boom on the left cup
    cr.set_line_width(5)
    cr.set_source_rgb(0.22, 0.22, 0.24)
    cr.move_to(70, 230)
    cr.curve_to(70, 275, 110, 285, 140, 280)
    cr.stroke()
    cr.arc(144, 279, 7, 0, 2 * math.pi)
    cr.set_source_rgb(0.12, 0.12, 0.13)
    cr.fill()
    cr.restore()


def mouse(cr, w, h, accent=ACCENT):
    s = min(w / 300, h / 300)
    cr.save()
    cr.translate(w / 2 - 150 * s, h / 2 - 150 * s)
    cr.scale(s, s)
    _glow(cr, 150, 170, 140, accent, 0.18)
    cr.move_to(150, 40)
    cr.curve_to(215, 40, 228, 110, 226, 170)
    cr.curve_to(224, 235, 195, 270, 150, 270)
    cr.curve_to(105, 270, 76, 235, 74, 170)
    cr.curve_to(72, 110, 85, 40, 150, 40)
    cr.close_path()
    _body(cr, 150, 40, 150, 270)
    cr.set_source_rgba(1, 1, 1, 0.12)
    cr.set_line_width(2)
    cr.move_to(150, 42)
    cr.line_to(150, 130)
    cr.stroke()
    _round_rect(cr, 143, 70, 14, 34, 7)  # wheel
    cr.set_source_rgb(0.08, 0.08, 0.09)
    cr.fill_preserve()
    cr.set_source_rgba(*accent, 0.9)
    cr.set_line_width(2)
    cr.stroke()
    cr.move_to(118, 245)  # logo light
    cr.line_to(182, 245)
    cr.set_source_rgba(*accent, 0.9)
    cr.set_line_width(4)
    cr.stroke()
    cr.restore()


def microphone(cr, w, h, accent=ACCENT):
    s = min(w / 300, h / 300)
    cr.save()
    cr.translate(w / 2 - 150 * s, h / 2 - 150 * s)
    cr.scale(s, s)
    _glow(cr, 150, 120, 120, accent, 0.30)
    _round_rect(cr, 105, 30, 90, 170, 40)  # capsule
    _body(cr, 150, 30, 150, 200, 0.22, 0.09)
    cr.set_source_rgba(1, 1, 1, 0.07)
    cr.set_line_width(1)
    for y in range(48, 190, 9):  # grille
        cr.move_to(112, y)
        cr.line_to(188, y)
    cr.stroke()
    cr.set_source_rgba(*accent, 0.85)
    _round_rect(cr, 108, 33, 84, 164, 38)
    cr.set_line_width(3)
    cr.stroke()
    cr.set_line_width(10)  # stand
    cr.set_source_rgb(0.16, 0.16, 0.17)
    cr.move_to(150, 200)
    cr.line_to(150, 250)
    cr.stroke()
    _round_rect(cr, 85, 248, 130, 18, 9)
    _body(cr, 150, 248, 150, 266)
    cr.restore()


def generic(cr, w, h, accent=ACCENT):
    s = min(w / 300, h / 300)
    cr.save()
    cr.translate(w / 2 - 150 * s, h / 2 - 150 * s)
    cr.scale(s, s)
    _glow(cr, 150, 150, 130, accent, 0.18)
    _round_rect(cr, 70, 90, 160, 120, 18)
    _body(cr, 150, 90, 150, 210)
    cr.restore()


BY_KIND = {"headset": headset, "mouse": mouse, "microphone": microphone}


def draw(kind: str, cr, w: int, h: int, accent=ACCENT) -> None:
    BY_KIND.get(kind, generic)(cr, w, h, accent)


def widget(kind: str, icon: str, width: int, height: int, **props):
    """The drawing as a widget; the device's icon when PyGObject has no cairo support."""
    from gi.repository import Gtk
    from . import compat
    if not compat.CAIRO:
        return Gtk.Image(icon_name=icon, pixel_size=min(width, height), css_classes=["hx-dim"], **props)
    area = Gtk.DrawingArea(content_width=width, content_height=height, **props)
    area.set_draw_func(lambda _a, cr, w, h: draw(kind, cr, w, h))
    return area
