"""Command line: hyperx-linux <command>. Without a command the GUI opens."""
from __future__ import annotations

import argparse
import time

from . import __version__, audio
from . import controls as C
from . import keymap
from .config import Config
from .drivers import DRIVERS, Driver, Kind, Support, display_name, find_driver, passive_note
from .buttons import DEVICE_ACTIONS, ButtonMapper, button_control, find_input
from .drivers.ngenuity_kb import parse_hex
from .buttons import MACROS as BUTTON_MACROS
from .hid import HidError, Node, NodeInfo, enumerate_nodes

COMMANDS = {"list", "status", "get", "set", "listen", "diag", "udev-rules", "devices"}


class Opened:
    def __init__(self, info: NodeInfo, driver_cls: type[Driver]):
        self.info = info
        self.node = Node(info)
        self.driver = driver_cls(self.node, lambda key, value: None)
        self.node.listeners.append(self.driver.handle_input)
        self.audio = None  # the audio engine runs on its own; settings made here keep running after we exit
        self.buttons = None  # done by the app; here only shown and saved
        if self.driver.kind == Kind.HEADSET:
            path, keys = find_input(info.path)
            if path:
                self.buttons = (button_control(keys, DEVICE_ACTIONS), BUTTON_MACROS)
        if self.driver.kind == Kind.HEADSET and audio.available():
            hardware_eq = any(isinstance(c, C.Equalizer) for c in self.driver.controls)
            self.audio = audio.AudioEngine(info.vid, info.pid, self.driver.name, lambda key, value: None,
                                           hardware_eq)

    @property
    def controls(self) -> tuple[C.Control, ...]:
        return self.driver.controls + (self.audio.controls if self.audio else ()) + (self.buttons or ())

    def value(self, c: C.Control, saved: dict):
        if self.audio and self.audio.handles(c.id):
            return self.audio.values.get(c.id)
        if c.id in ("buttons", "button_macros"):
            return saved.get(c.id) or {}
        return self.driver.values.get(c.id, saved.get(c.id) if c.persist else None)

    def close(self):
        self.node.close()
        self.driver.close()


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
    if isinstance(control, (C.KeyRemap, C.ButtonMap)):
        return ", ".join(f"{k}={v}" for k, v in value.items()) or "none"
    if isinstance(control, C.KeyColors):
        return ", ".join(f"{k}={v}" for k, v in value.items()) or "none"
    if isinstance(control, C.MacroList):
        return "; ".join(f"{n}:{m.get('mode', 'once')}={m['steps']}" for n, m in value.items()) or "none"
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
    if isinstance(control, C.Action):
        return None
    if isinstance(control, C.Recorder):
        return float(text or 5)  # seconds to record
    if isinstance(control, C.KeyRemap):
        # caps=esc fn+q=media:volume-up …; "key=default" removes one, "clear" removes all
        if text.lower() == "clear":
            return {}
        delta = {}
        for item in args:
            key, sep, action = item.partition("=")
            if not sep:
                raise SystemExit("use KEY=ACTION, e.g. capslock=esc or fn+q=media:volume-up")
            fn = key.lower().startswith("fn+")
            keymap.parse_action(action)
            delta[("fn+" if fn else "") + keymap.canonical_key(key[3:] if fn else key)] = action
        return delta
    if isinstance(control, C.ButtonMap):
        # play_pause=media:next volume_up="run:playerctl next" …; "button=default" removes one, "clear" all
        if text.lower() == "clear":
            return {}
        buttons = {b for b, _l in control.buttons}
        delta = {}
        for item in args:
            button, sep, action = item.partition("=")
            button = button.strip().replace("-", "_")
            if not sep or button not in buttons:
                raise SystemExit("use BUTTON=ACTION; buttons: " + ", ".join(sorted(buttons)))
            ButtonMapper.check(action)
            delta[button] = action
        return delta
    if isinstance(control, C.KeyColors):
        # w=#00ff00 a=#00ff00 …, all=#ff0000 for every key; "key=default" removes one, "clear" all
        if text.lower() == "clear":
            return {}
        keys = {k for _layout, ks in control.layouts for k, *_g in ks}
        delta = {}
        for item in args:
            key, sep, color = item.partition("=")
            if not sep:
                raise SystemExit("use KEY=#rrggbb, e.g. w=#00ff00, or all=#ff0000")
            if color.strip().lower() != "default":
                parse_hex(color)
            targets = keys if key.lower() == "all" else {keymap.canonical_key(key)}
            delta.update({k: color.strip() for k in targets})
        return delta
    if isinstance(control, C.MacroList):
        # NAME[:once|toggle|hold]=STEPS; "NAME=" removes it, "clear" removes all
        if text.lower() == "clear":
            return {}
        head, sep, steps = text.partition("=")
        name, _, mode = head.strip().partition(":")
        if not sep or not name:
            raise SystemExit('use NAME=STEPS, e.g. copy-paste="ctrl+c, 50ms, ctrl+v" (optional NAME:hold=…)')
        if not steps.strip():
            return {name: None}
        keymap.parse_macro(steps)
        return {name: {"steps": steps.strip(), "mode": mode or "once"}}
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
        if dev.audio:
            dev.audio.load_state(saved)
        width = max(len(c.cli_name) for c in dev.controls)
        for c in dev.controls:
            if isinstance(c, C.Action):
                continue  # buttons: "hyperx-linux set <name>" runs them
            print(f"  {c.cli_name:{width}} {fmt(c, dev.value(c, saved))}")
        return 0
    finally:
        dev.close()


def find_control(dev: Opened, name: str) -> C.Control:
    for c in dev.controls:
        if name in (c.cli_name, c.id):
            return c
    raise SystemExit(f"unknown control {name!r}; controls: " + ", ".join(c.cli_name for c in dev.controls))


def cmd_get(a) -> int:
    dev = pick(a.device)
    try:
        dev.driver.refresh()
        c = find_control(dev, a.control)
        saved = Config().device(dev.driver.driver_id())
        if dev.audio:
            dev.audio.load_state(saved)
        print(fmt(c, dev.value(c, saved)))
        return 0
    finally:
        dev.close()


def cmd_set(a) -> int:
    dev = pick(a.device)
    try:
        d = dev.driver
        cfg = Config()
        c = find_control(dev, a.control)
        if c.id in ("buttons", "button_macros"):  # performed by the app while it runs: just saved
            saved = cfg.device(d.driver_id())
            value = parse(c, a.value)
            if value:
                value = {k: v for k, v in {**(saved.get(c.id) or {}), **value}.items()
                         if v is not None and v != "default"}
            cfg.set_device_value(d.driver_id(), c.id, value)
            print(f"{c.cli_name}: {fmt(c, value)}  (the app does it while it runs; restart it to apply)")
            return 0
        if dev.audio and dev.audio.handles(c.id):  # made on this computer: no device I/O
            dev.audio.load_state(cfg.device(d.driver_id()))
            value = parse(c, a.value)
            dev.audio.apply(c.id, value)
            cfg.set_device_value(d.driver_id(), c.id, value)
            print(f"{c.cli_name}: {fmt(c, dev.audio.values.get(c.id, value))}")
            return 0
        if d.support == Support.EXPERIMENTAL and not (a.experimental or cfg["allow_experimental"]):
            raise SystemExit("experimental driver: pass --experimental to change settings "
                             "(nobody has confirmed this protocol on real hardware yet)")
        if not c.writable:
            raise SystemExit(f"{c.cli_name} is read-only on this device")
        if c.experimental and not (a.experimental or cfg["allow_experimental"]):
            raise SystemExit(f"{c.cli_name} isn't confirmed on this model yet: pass --experimental to use it")
        saved = cfg.device(d.driver_id())
        d.load_state(saved)
        value = parse(c, a.value)
        if isinstance(c, C.Recorder):
            print(f"recording for {value:g} s: type on the keyboard…", flush=True)
            d.apply(c.id, True)
            time.sleep(value)
            d.apply(c.id, False)
            print(d.values.get(c.id) or "nothing was typed")
            return 0
        if isinstance(c, (C.KeyRemap, C.MacroList, C.KeyColors)) and value:  # change entries, keep the others
            value = {k: v for k, v in {**(saved.get(c.id) or {}), **value}.items()
                     if v is not None and v != "default"}
        d.apply(c.id, value)
        if c.persist:
            cfg.set_device_value(d.driver_id(), c.id, value)
        if isinstance(c, C.KeyColors) and value and d.has("effect"):  # painted keys show in the custom effect
            d.apply("effect", "custom")
            cfg.set_device_value(d.driver_id(), "effect", "custom")
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


def cmd_udev(a) -> int:
    from .udev import rules
    print(rules(group=a.group), end="")
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
    p.add_argument("value", nargs="*")
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
    p = sub.add_parser("udev-rules", help="print udev rules for every supported device")
    p.add_argument("--group", help="also grant access to this group (systems without systemd-logind)")
    p.set_defaults(fn=cmd_udev)
    p = sub.add_parser("devices", help="table of supported models")
    p.add_argument("--markdown", action="store_true")
    p.set_defaults(fn=cmd_devices)
    a = ap.parse_args(argv)
    return a.fn(a)


__all__ = ["COMMANDS", "DRIVERS", "main"]
