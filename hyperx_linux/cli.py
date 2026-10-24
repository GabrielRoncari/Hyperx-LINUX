"""Command line: hyperx-linux <command>. Without a command the GUI opens."""
from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from . import controls as C
from .config import Config
from .drivers import DRIVERS, Driver, Support, display_name, find_driver, passive_note
from .hid import HidError, Node, NodeInfo, enumerate_nodes

COMMANDS = {"list", "status", "get", "set", "listen", "diag", "udev-rules", "devices"}


class Opened:
    def __init__(self, info: NodeInfo, driver_cls: type[Driver]):
        self.info = info
        self.node = Node(info)
        self.driver = driver_cls(self.node, lambda key, value: None)
        self.node.listeners.append(self.driver.handle_input)

    def close(self):
        self.node.close()


def discover() -> tuple[list[tuple[NodeInfo, type[Driver]]], list[NodeInfo]]:
    """Supported devices (one node each) and HyperX devices without a driver."""
    groups: dict[str, list[NodeInfo]] = {}
    for n in enumerate_nodes():
        groups.setdefault(n.usb_path or n.path, []).append(n)
    found, other = [], []
    for group in groups.values():
        match = next(((n, d) for n in group for d in [find_driver(n)] if d), None)
        (found.append(match) if match else other.append(group[0]))
    return found, other


def pick(selector: str | None) -> Opened:
    found, _other = discover()
    if not found:
        raise SystemExit("no supported HyperX device found (try: hyperx-linux list)")
    if selector is None:
        info, d = found[0]
    elif selector.isdigit() and 1 <= int(selector) <= len(found):
        info, d = found[int(selector) - 1]
    else:
        matches = [(i, d) for i, d in found if selector.lower() in d.name.lower()]
        if not matches:
            raise SystemExit(f"no device matching {selector!r}")
        info, d = matches[0]
    try:
        return Opened(info, d)
    except HidError as e:
        raise SystemExit(str(e))


# ------------------------------------------------------------------ formatting
def fmt(control: C.Control, value) -> str:
    if value is None:
        return "—"
    if isinstance(control, C.Battery):
        b: C.BatteryValue = value
        extra = " full" if b.full else (" charging" if b.charging else "")
        volts = f" ({b.voltage_mv / 1000:.2f} V)" if b.voltage_mv else ""
        return f"{b.level}%{extra}{volts}"
    if isinstance(control, C.Toggle):
        return "on" if value else "off"
    if isinstance(control, C.Choice):
        return control.label(value)
    if isinstance(control, C.Color):
        return "#%02x%02x%02x" % tuple(value)
    if isinstance(control, C.Equalizer):
        return " ".join(f"{g:+.1f}" for g in value)
    if isinstance(control, C.Range) and control.unit:
        return f"{value} {control.unit}"
    return str(value)


def parse(control: C.Control, args: list[str]):
    text = " ".join(args).strip()
    if isinstance(control, C.Toggle):
        if text.lower() in ("on", "1", "true", "yes"):
            return True
        if text.lower() in ("off", "0", "false", "no"):
            return False
        raise SystemExit("use on/off")
    if isinstance(control, C.Range):
        v = float(text)
        if not control.min <= v <= control.max:
            raise SystemExit(f"range is {control.min:g}..{control.max:g}")
        return int(v) if float(control.step).is_integer() else v
    if isinstance(control, C.Choice):
        for value, label in control.options:
            if text.lower() in (label.lower(), str(value).lower()):
                return value
        if control.unit == "s" and text.rstrip("m").isdigit():
            return int(text.rstrip("m")) * 60
        raise SystemExit("options: " + ", ".join(label for _v, label in control.options))
    if isinstance(control, C.Color):
        t = text.lstrip("#")
        if "," in t:
            return tuple(int(x) for x in t.split(","))
        return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))
    if isinstance(control, C.Equalizer):
        presets = {name.lower(): list(g) for name, g in control.presets}
        if text.lower() in presets:
            return presets[text.lower()]
        gains = [float(x) for x in args]
        if len(gains) != len(control.bands_hz):
            raise SystemExit(f"give {len(control.bands_hz)} gains in dB or a preset: "
                             + ", ".join(n for n, _g in control.presets))
        return [max(control.min_db, min(control.max_db, g)) for g in gains]
    raise SystemExit("this control is read-only")


# -------------------------------------------------------------------- commands
def cmd_list(_a) -> int:
    found, other = discover()
    for i, (info, d) in enumerate(found, 1):
        print(f"{i}. {d.name} [{d.support.value}]  {info.usb_id}  {info.path}")
    for info in other:
        note = passive_note(info)
        print(f"-  {display_name(info)}  {info.usb_id}  {note or 'not supported yet (run: hyperx-linux diag)'}")
    if not found and not other:
        print("no HyperX device found")
    return 0


def cmd_status(a) -> int:
    dev = pick(a.device)
    try:
        dev.driver.refresh()
        d = dev.driver
        print(f"{d.name} [{d.support.value}]  {dev.info.usb_id}  {dev.info.path}")
        if d.online is False:
            print("device off or out of range")
            return 1
        saved = Config().device(d.driver_id())
        for c in d.controls:
            value = d.values.get(c.id, saved.get(c.id) if c.persist else None)
            print(f"  {c.cli_name:16} {fmt(c, value)}")
        return 0
    finally:
        dev.close()


def find_control(d: Driver, name: str) -> C.Control:
    for c in d.controls:
        if name in (c.cli_name, c.id):
            return c
    raise SystemExit(f"unknown control {name!r}; controls: " + ", ".join(c.cli_name for c in d.controls))


def cmd_get(a) -> int:
    dev = pick(a.device)
    try:
        dev.driver.refresh()
        c = find_control(dev.driver, a.control)
        print(fmt(c, dev.driver.values.get(c.id)))
        return 0
    finally:
        dev.close()


def cmd_set(a) -> int:
    dev = pick(a.device)
    try:
        d = dev.driver
        cfg = Config()
        if d.support == Support.EXPERIMENTAL and not (a.experimental or cfg["allow_experimental"]):
            raise SystemExit("experimental driver: pass --experimental to change settings "
                             "(nobody has confirmed this protocol on real hardware yet)")
        c = find_control(d, a.control)
        if not c.writable:
            raise SystemExit(f"{c.cli_name} is read-only on this device")
        value = parse(c, a.value)
        d.apply(c.id, value)
        if c.persist:
            cfg.set_device_value(d.driver_id(), c.id, value)
        print(f"{c.cli_name}: {fmt(c, d.values.get(c.id, value))}")
        return 0
    finally:
        dev.close()


def cmd_listen(a) -> int:
    dev = pick(a.device)
    d = dev.driver
    controls = {c.id: c for c in d.controls}

    def show(key, value):
        text = fmt(controls[key], value) if key in controls else str(value)
        print(f"{time.strftime('%H:%M:%S')} {key}: {text}", flush=True)
    d._notify = show
    print(f"listening to {d.name} (Ctrl+C to stop)…")
    try:
        while not dev.node.closed:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()
    return 0


def cmd_diag(a) -> int:
    from .diag import report
    print(report(probe=a.probe))
    return 0


def cmd_udev(_a) -> int:
    from .udev import rules
    print(rules(), end="")
    return 0


def cmd_devices(a) -> int:
    from .udev import supported_table
    print(supported_table(markdown=a.markdown), end="")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="hyperx-linux", description="Control HyperX peripherals on Linux.")
    ap.add_argument("--version", action="version", version=f"hyperx-linux {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="devices that are plugged in").set_defaults(fn=cmd_list)
    p = sub.add_parser("status", help="read every setting")
    p.add_argument("-d", "--device", help="number from 'list' or part of the name")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("get", help="read one setting")
    p.add_argument("control")
    p.add_argument("-d", "--device")
    p.set_defaults(fn=cmd_get)
    p = sub.add_parser("set", help="change one setting, e.g. 'set sidetone on', 'set eq bass'")
    p.add_argument("control")
    p.add_argument("value", nargs="+")
    p.add_argument("-d", "--device")
    p.add_argument("--experimental", action="store_true", help="allow writes with an experimental driver")
    p.set_defaults(fn=cmd_set)
    p = sub.add_parser("listen", help="print events (buttons, battery, mute) as they happen")
    p.add_argument("-d", "--device")
    p.set_defaults(fn=cmd_listen)
    p = sub.add_parser("diag", help="report to attach to a GitHub issue")
    p.add_argument("--probe", action="store_true",
                   help="also run the read commands of experimental drivers")
    p.set_defaults(fn=cmd_diag)
    sub.add_parser("udev-rules", help="print udev rules for every supported device").set_defaults(fn=cmd_udev)
    p = sub.add_parser("devices", help="table of supported models")
    p.add_argument("--markdown", action="store_true")
    p.set_defaults(fn=cmd_devices)
    a = ap.parse_args(argv)
    return a.fn(a)


__all__ = ["COMMANDS", "DRIVERS", "main"]
