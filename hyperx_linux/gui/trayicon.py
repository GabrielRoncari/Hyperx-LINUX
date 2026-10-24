"""Tray battery icon drawn by the app (StatusNotifierItem IconPixmap).

Icon themes disagree on battery icons (vertical, coloured, missing levels) and panels rescale
them, so the tray draws its own glyph. Returns None when pycairo is missing; the caller then
falls back to a themed icon name.
"""
from __future__ import annotations

try:
    import cairo
except ImportError:  # optional dependency
    cairo = None

SIZES = (24, 32, 48, 64)


def battery_icon_name(level: int | None, charging: bool | None, full: bool, online: bool | None) -> str:
    """Freedesktop battery icon name. Themes ship battery-level-{0..100}-symbolic,
    battery-level-{0..90}-charging-symbolic and battery-level-100-charged-symbolic: there is no
    "100-charging", so a charging battery is capped at 90."""
    if not online or level is None:
        return "battery-missing-symbolic"
    if full:
        return "battery-level-100-charged-symbolic"
    step = min(100, max(0, round(level / 10) * 10))
    if charging:
        return f"battery-level-{min(step, 90)}-charging-symbolic"
    return f"battery-level-{step}-symbolic"
GREEN, RED = (0.30, 0.69, 0.31), (0.90, 0.22, 0.21)


def _rounded_rect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -1.5708, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, 1.5708)
    ctx.arc(x + r, y + h - r, r, 1.5708, 3.1416)
    ctx.arc(x + r, y + r, r, 3.1416, 4.7124)
    ctx.close_path()


def _draw(size: int, level: int | None, charging: bool, low: bool, dark: bool):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(s)
    ctx.scale(size / 32, size / 32)  # draw on a 32x32 grid
    fg = (0.94, 0.94, 0.94) if dark else (0.19, 0.19, 0.19)
    # body (horizontal battery) and terminal
    _rounded_rect(ctx, 1.5, 7.5, 26.5, 17, 3.5)
    ctx.set_source_rgb(*fg)
    ctx.set_line_width(2.4)
    ctx.stroke()
    ctx.rectangle(28.5, 12.5, 2.5, 7)
    ctx.fill()
    if level is None:  # unknown / off: question mark
        ctx.set_font_size(13)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ext = ctx.text_extents("?")
        ctx.move_to(14.5 - ext.width / 2 - ext.x_bearing, 16 - ext.height / 2 - ext.y_bearing)
        ctx.show_text("?")
    else:
        width = max(1.5, 20.5 * max(0, min(100, level)) / 100)
        _rounded_rect(ctx, 4.5, 10.5, width, 11, 1.5)
        ctx.set_source_rgb(*(RED if low and not charging else GREEN if charging else fg))
        ctx.fill()
    if charging:  # lightning bolt with an outline in the background colour
        ctx.move_to(17, 5)
        ctx.line_to(10.5, 17.5)
        ctx.line_to(15, 17.5)
        ctx.line_to(13.5, 27)
        ctx.line_to(20.5, 14)
        ctx.line_to(16, 14)
        ctx.close_path()
        ctx.set_source_rgb(*((0.12, 0.12, 0.12) if dark else (1, 1, 1)))
        ctx.set_line_width(2.5)
        ctx.stroke_preserve()
        ctx.set_source_rgb(*fg)
        ctx.fill()
    s.flush()
    return s


def _argb_bytes(surface) -> bytes:
    """cairo ARGB32 is native-endian and premultiplied; SNI wants straight ARGB in network order."""
    data = bytes(surface.get_data())
    out = bytearray(len(data))
    for i in range(0, len(data), 4):
        b, g, r, a = data[i], data[i + 1], data[i + 2], data[i + 3]  # little-endian memory order
        if a:
            r, g, b = min(255, r * 255 // a), min(255, g * 255 // a), min(255, b * 255 // a)
        out[i:i + 4] = bytes((a, r, g, b))
    return bytes(out)


def battery_pixmaps(level: int | None, charging: bool, low: bool, dark: bool):
    """[(width, height, ARGB bytes)] for the tray, or None without pycairo."""
    if cairo is None:
        return None
    return [(n, n, _argb_bytes(_draw(n, level, charging, low, dark))) for n in SIZES]


def preview_png(path: str, level: int | None, charging: bool, low: bool, dark: bool, size: int = 64) -> None:
    if cairo is not None:
        _draw(size, level, charging, low, dark).write_to_png(path)
