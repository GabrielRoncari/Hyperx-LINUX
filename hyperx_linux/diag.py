"""`hyperx-linux diag`: a Markdown report to paste into a GitHub issue.

Descriptors come from sysfs (no device access needed). Reads only run for drivers that
are verified or community-confirmed, unless --probe is given. Serial numbers are not included.
"""
from __future__ import annotations

import platform
from collections import defaultdict

from . import __version__
from .drivers import Support, find_driver, passive_note
from .hid import HidError, Node, enumerate_nodes


def _hexdump(data: bytes) -> str:
    return "\n".join(data[i:i + 16].hex(" ") for i in range(0, len(data), 16))


def report(probe: bool = False) -> str:
    out = [f"## hyperx-linux diag\n\n- version: {__version__}\n- kernel: {platform.release()}\n"]
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
