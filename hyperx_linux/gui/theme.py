"""NGENUITY 3.1's look: dark, frosted panels (ColorPanelDark with a black outer and a 20% white inner
border), grey section titles, 32 px controls, the system accent colour for whatever is on or
selected, and HyperX red only for the brand and recording. The values come from NGENUITY's compiled
XAML; the typeface for titles is Exo 2 (SIL OFL, bundled), the closest open match to NGENUITY's
commercial RBNo3.1."""
from __future__ import annotations

import ctypes
import ctypes.util
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from . import compat  # noqa: E402

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fonts")
FONT = "Exo 2"

RED = "#d02239"  # ColorBrandHyperX
SWATCHES = (  # ColorRGB*: the swatches of NGENUITY's colour picker
    ("Ruby", "#ff0000"), ("Amber", "#ff6600"), ("Citrine", "#f7b500"), ("Emerald", "#6dd400"),
    ("Amazonite", "#44d7b6"), ("Apatite", "#32c5ff"), ("Sapphire", "#0091ff"), ("Iolite", "#6236ff"),
    ("Amethyst", "#b620e0"), ("White", "#ffffff"),
)

NAMED = {  # libadwaita's colours, set to NGENUITY's dark theme. The accent is left to the system,
    # like NGENUITY, whose toggles, sliders and selections follow the Windows accent colour.
    "window_bg_color": "#0b0b0c",
    "window_fg_color": "#f9f9f8",
    "view_bg_color": "#141415",
    "view_fg_color": "#f9f9f8",
    "headerbar_bg_color": "transparent",
    "headerbar_fg_color": "#f9f9f8",
    "headerbar_backdrop_color": "transparent",
    "headerbar_shade_color": "transparent",
    "sidebar_bg_color": "transparent",
    "card_bg_color": "rgba(255, 255, 255, 0.02)",  # ColorShadesWhite02, NGENUITY's Section
    "card_fg_color": "#f9f9f8",
    "card_shade_color": "transparent",
    "popover_bg_color": "#1e1e1f",
    "popover_fg_color": "#f9f9f8",
    "dialog_bg_color": "#1e1e1f",
    "dialog_fg_color": "#f9f9f8",
    "destructive_bg_color": RED,
}

PANEL = "rgba(30, 30, 31, 0.85)"  # ColorPanelDark
CSS = f"""
/* type: NGENUITY's titles are RBNo3.1 Book (here Exo 2), body text is the system font */
.hx-title, .hx-brand, .hx-section-title, .hx-panel-title, .hx-sidebar-header, .hx-card-name,
.hx-device-name, .hx-keycap, .hx-chip, .hx-big {{ font-family: "{FONT}", sans-serif; }}

window.hx-window {{
  background-color: #0b0b0c;
  background-image: radial-gradient(ellipse at 70% 0%, rgba(120, 120, 130, 0.16), transparent 60%),
                    radial-gradient(ellipse at 0% 100%, alpha({RED}, 0.10), transparent 55%);
}}

/* frosted panels: ColorPanelDark, black outer border, 20% white inner border */
.hx-sidebar, .hx-card, .hx-pill, .hx-chip, .hx-overlay {{
  background-color: {PANEL};
  border: 1px solid rgba(0, 0, 0, 0.40);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.20), 0 3px 24px -3px rgba(0, 0, 0, 0.35);
}}
.hx-sidebar {{ border-radius: 8px; }}
.hx-overlay {{ border-radius: 8px; }}
.hx-brand {{ font-weight: 800; font-size: 17px; letter-spacing: 3px; color: #f9f9f8; }}
.hx-brand-accent {{ color: {RED}; }}
.hx-sidebar-header {{ font-size: 12px; letter-spacing: 0.4px; color: #999999; margin: 16px 12px 6px 12px; }}
.hx-tree, .hx-tree > row {{ background: transparent; }}
.hx-tree > row {{
  min-height: 32px; border-radius: 4px; margin: 1px 0; padding: 0 6px; color: rgba(255, 255, 255, 0.8);
}}
.hx-tree > row:hover {{ background-color: rgba(255, 255, 255, 0.05); }}
.hx-tree > row:selected {{ background-color: rgba(255, 255, 255, 0.10); color: #ffffff; }}
.hx-tree .hx-child {{ border-left: 1px solid rgba(255, 255, 255, 0.15); margin-left: 16px; padding-left: 10px; }}
.hx-tree image {{ color: #efefef; }}

/* status chips over the page, like NGENUITY's battery / DPI chips */
.hx-chip {{ border-radius: 16px; min-height: 30px; padding: 0 14px; font-size: 13px; }}
.hx-pill {{ border-radius: 16px; min-height: 32px; padding: 0 10px; }}
.hx-pill button {{ min-height: 30px; padding: 0 12px; font-weight: 600; color: rgba(255, 255, 255, 0.6);
                  background: transparent; }}
.hx-pill button:hover, .hx-pill button:checked {{ color: #ffffff; }}
.hx-pill separator {{ min-height: 16px; margin: 8px 2px; background: rgba(255, 255, 255, 0.15); }}

/* segmented control: pill on black 40%, selected segment = accent at 20% */
.hx-segmented {{ background: rgba(0, 0, 0, 0.40); border: 1px solid rgba(255, 255, 255, 0.20);
                border-radius: 16px; padding: 1px; }}
.hx-segmented button {{ border-radius: 14px; min-height: 28px; padding: 0 16px; background: transparent;
                       color: #c0c0c0; font-weight: 600; }}
.hx-segmented button:checked {{ background: alpha(@accent_bg_color, 0.20); color: #f9f9f8; }}

/* the device page */
.hx-device-name {{ font-weight: 600; font-size: 15px; letter-spacing: 2px; color: rgba(255, 255, 255, 0.85); }}
.hx-big {{ font-size: 56px; font-weight: 700; font-feature-settings: "tnum"; }}
.hx-dim {{ color: #999999; }}
.hx-panel-title {{ font-size: 16px; letter-spacing: 0.4px; color: #999999; }}
.hx-section {{
  background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 4px; padding: 10px 16px;
}}
.hx-section-title {{ font-size: 14px; letter-spacing: 0.4px; color: #f9f9f8; margin-bottom: 4px; }}
.hx-section list, .hx-section list > row {{ background: transparent; border: none; box-shadow: none; }}
.hx-section list > row {{ border-radius: 4px; padding: 0; }}
.hx-section list > row:hover {{ background-color: rgba(255, 255, 255, 0.05); }}
.hx-section list > row:not(:last-child) {{ border-bottom: 1px solid rgba(255, 255, 255, 0.06); }}
.hx-feature-tab {{ color: #999999; background: transparent; padding: 4px; min-width: 0; min-height: 0; }}
.hx-feature-tab:hover {{ color: #efefef; background: transparent; }}
.hx-feature-tab:checked {{ color: #f9f9f8; background: transparent; }}

/* buttons: 32 tall, radius 4; secondary = 10% white with a light inner border */
button.hx-secondary {{ background-color: rgba(255, 255, 255, 0.10); border-radius: 4px; min-height: 32px;
                      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.20); }}
button.suggested-action, button.hx-primary {{ border-radius: 4px; min-height: 32px; font-weight: 600;
  box-shadow: 0 0 8px alpha(@accent_bg_color, 0.6); }}
button.hx-round {{ border-radius: 16px; min-width: 32px; min-height: 32px; padding: 0; }}

/* keycaps of the key-assignment page: 46x46, radius 6, #353535 */
button.hx-keycap {{ min-width: 46px; min-height: 46px; padding: 0 6px; border-radius: 6px; background: #353535;
                   border: 1px solid rgba(255, 255, 255, 0.40); font-size: 12px; color: #f9f9f8; }}
button.hx-keycap:hover {{ background: #4c4c4c; }}
button.hx-keycap.hx-current {{ border-color: @accent_bg_color; box-shadow: 0 0 0 1px @accent_bg_color; }}

/* home: device cards */
.hx-card {{ border-radius: 8px; background-color: rgba(0, 0, 0, 0.20); border-color: rgba(255, 255, 255, 0.20);
           box-shadow: none; padding: 16px; }}
.hx-card:hover {{ background-color: rgba(0, 0, 0, 0.40); border-color: rgba(255, 255, 255, 0.60);
                 box-shadow: 0 0 12px rgba(255, 255, 255, 0.20); }}
.hx-card-name {{ font-weight: 700; font-size: 18px; letter-spacing: 1px; }}
.hx-card-sub {{ color: #c0c0c0; font-size: 13px; font-weight: 600; }}
.hx-recording {{ border-color: {RED}; box-shadow: 0 0 8px alpha({RED}, 0.3); background: alpha({RED}, 0.2); }}

.hx-sw {{ min-width: 20px; min-height: 20px; border-radius: 10px; }}
.hx-panel-plain {{ background-color: {PANEL}; border: 1px solid rgba(0, 0, 0, 0.8); border-radius: 8px;
                  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2); }}
.hx-tabs-plain {{ background-color: {PANEL}; border-radius: 8px 8px 0 0; padding: 0 16px;
                 box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2); }}
.hx-swatch {{ min-width: 24px; min-height: 24px; padding: 0; border-radius: 12px;
             border: 2px solid transparent; background: transparent; }}
.hx-swatch:checked {{ border-color: #ffffff; }}
.eq-band label {{ font-size: 11px; font-feature-settings: "tnum"; }}
levelbar.battery trough {{ min-height: 6px; }}
levelbar.battery.low block.filled {{ background-color: @error_bg_color; }}
.compat-banner {{ background-color: alpha({RED}, 0.25); padding: 6px 12px; }}
"""


SWATCH_CSS = "".join(f".hx-sw-{hx.lstrip('#')} {{ background-color: {hx}; }}\n" for _n, hx in SWATCHES)


def register_fonts() -> None:
    """Make the bundled typeface available to this process only (fontconfig application fonts)."""
    path = ctypes.util.find_library("fontconfig")
    if not path or not os.path.isdir(FONT_DIR):
        return
    try:
        fc = ctypes.CDLL(path)
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        for name in sorted(os.listdir(FONT_DIR)):
            if name.endswith((".ttf", ".otf")):
                fc.FcConfigAppFontAddFile(None, os.path.join(FONT_DIR, name).encode())
    except OSError:
        pass  # no fontconfig: the system font is used


def apply() -> None:
    """Call once, before any window is created."""
    register_fonts()
    Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
    css = "".join(f"@define-color {k} {v};\n" for k, v in NAMED.items())
    if compat.gtk(16):  # libadwaita 1.6+ reads CSS variables
        css += ":root {" + "".join(f" --{k.replace('_', '-')}: {v};" for k, v in NAMED.items()) + " }\n"
    provider = Gtk.CssProvider()
    compat.load_css(provider, css + CSS + SWATCH_CSS)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
