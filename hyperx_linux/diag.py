"""`hyperx-linux diag`: a Markdown report to paste into a GitHub issue.

Descriptors come from sysfs (no device access needed). Reads only run for drivers that
are verified or community-confirmed, unless --probe is given. Serial numbers are not included.
"""
from __future__ import annotations

import os
import platform
from collections import defaultdict

from . import __version__
from .drivers import Support, find_driver, passive_note
from .hid import HidError, Node, enumerate_nodes


def _hexdump(data: bytes) -> str:
    return "\n".join(data[i:i + 16].hex(" ") for i in range(0, len(data), 16))


def report(probe: bool = False) -> str:
    out = [f"## hyperx-linux diag\n\n- version: {__version__}\n- kernel: {platform.release()}\n{_environment()}"]
    groups = defaultdict(list)
    for n in enumerate_nodes():
        groups[n.usb_path or n.path].append(n)
    if not groups:
        out.append("No HyperX HID device found (vendor 0951 or 03f0).\n")
    for nodes in groups.values():
        first = nodes[0]
        bcd = f"{first.bcd_device:04x}" if first.bcd_device is not None else "?"
        out.append(f"### {first.name or 'unknown'} — `{first.usb_id}` (bcdDevice {bcd}, bus {first.bus})\n")
        note = passive_note(first)
        if note:
            out.append(f"Note: {note}\n")
        for n in nodes:
            d = find_driver(n)
            out.append(f"#### {n.path} — interface {n.interface}\n")
            out.append(f"- driver: {d.name + ' [' + d.support.value + ']' if d else 'none'}")
            for c in n.descriptor.collections:
                ids = ", ".join(f"0x{r:02X}" for r in sorted(c.report_ids)) or "none"
                out.append(f"- collection: usage page 0x{c.usage_page:04X}, usage 0x{c.usage:04X}, report ids {ids}")
            sizes = ", ".join(f"{k}:0x{rid:02X}={size}B" for (k, rid), size in sorted(n.descriptor.reports.items()))
            out.append(f"- reports: {sizes or 'none'}")
            out.append(f"\n<details><summary>report descriptor ({len(n.raw_descriptor)} bytes)</summary>\n\n```\n"
                       f"{_hexdump(n.raw_descriptor)}\n```\n</details>\n")
            if d and (d.support != Support.EXPERIMENTAL or probe):
                out.append(_read_values(n, d))
    return "\n".join(out)


def _read_values(info, driver_cls) -> str:
    try:
        node = Node(info)
    except HidError as e:
        return f"- read: skipped ({e})\n"
    try:
        drv = driver_cls(node, lambda k, v: None)
        drv.refresh()
        lines = [f"- online: {drv.online}"]
        lines += [f"- {k}: {v}" for k, v in drv.values.items()]
        return "\n".join(lines) + "\n"
    except Exception as e:  # a report must never crash
        return f"- read failed: {type(e).__name__}: {e}\n"
    finally:
        node.close()


def _environment() -> str:
    """Distribution and library versions, for compatibility reports."""
    lines = [f"- python: {platform.python_version()}"]
    try:  # inside Flatpak, /etc/os-release describes the runtime; the host's is in /run/host
        with open("/run/host/os-release" if os.path.exists("/run/host/os-release") else "/etc/os-release") as f:
            fields = dict(line.rstrip().split("=", 1) for line in f if "=" in line)
        lines.append(f"- distro: {fields.get('PRETTY_NAME', '?').strip(chr(34))}")
    except OSError:
        pass
    if os.path.exists("/.flatpak-info"):
        lines.append("- packaging: flatpak")
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk
        lines.append(f"- gtk: {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}")
        lines.append(f"- libadwaita: {Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}")
        lines.append(f"- pygobject: {'.'.join(map(str, gi.version_info))}")
    except (ImportError, ValueError) as e:
        lines.append(f"- gui: unavailable ({e})")
    return "\n".join(lines) + "\n"
