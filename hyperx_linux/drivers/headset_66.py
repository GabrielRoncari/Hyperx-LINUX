"""Headsets with the "0x66" protocol: Cloud III Wireless, Cloud II Core Wireless.

Request = output report 66 <cmd> <arg> (62 bytes); GETs have bit 7 set (0x8x), SETs don't.
Reply = input report 66 <cmd> <data>. Events = 66 <id> <value> (0A mute, 0B link, 0C charging,
0D battery). 66 1E resets the pairing key (SIRK) and is never sent. Full notes: docs/devices/headsets.md
"""
from __future__ import annotations

from ..controls import Battery, BatteryValue, Choice, Group, Info, Range, Toggle
from .base import Driver, Kind, Support

AUTO_OFF = ((0, "Never"), (10, "10 min"), (20, "20 min"), (30, "30 min"))
COLORS = {0: "Black", 1: "White", 2: "Black/Red"}
TOGGLES = {  # control id: (GET, SET)
    "sidetone": (0x84, 0x01),
    "mic_mute": (0x86, 0x03),
    "playback_mute": (0x87, 0x04),
    "noise_gate": (0x8D, 0x0F),
}
EV_SIDETONE, EV_MUTE, EV_LINK, EV_CHARGING, EV_BATTERY = 0x09, 0x0A, 0x0B, 0x0C, 0x0D


def s8(b: int) -> int:
    return b - 256 if b > 127 else b


class Headset66(Driver):
    kind = Kind.HEADSET
    wireless = True
    interfaces = (3,)

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0x66) is not None

    def _xfer(self, cmd: int, *args: int) -> bytes | None:
        pkt = bytes([0x66, cmd, *args]).ljust(62, b"\0")
        return self.node.request(lambda: self.node.write(pkt), lambda r: len(r) >= 3 and r[0] == 0x66 and r[1] == cmd)

    def _read_link(self) -> bool:
        r = self._xfer(0x82)
        self.set_online(bool(r and r[2] == 1))
        return bool(self.online)

    def _read_battery(self) -> None:
        r = self._xfer(0x89)
        if r is None or (r[2] == 0 and r[3] == 0):
            return
        c = self._xfer(0x8A)
        state = c[2] if c else 0
        self.set_value("battery", BatteryValue(level=r[4], charging=state == 1, full=state == 2,
                                               voltage_mv=r[2] << 8 | r[3]))

    def refresh(self) -> None:
        if not self._read_link():
            return
        self._read_battery()
        for cid, (get, _set) in TOGGLES.items():
            if self.has(cid):
                r = self._xfer(get)
                if r:
                    self.set_value(cid, r[2] == 1)
        r = self._xfer(0x85)
        if r:
            self.set_value("auto_off", r[2])
        if self.has("sidetone_level"):
            r = self._xfer(0x88)
            if r:
                self.set_value("sidetone_level", s8(r[2]))
        if self.has("color"):
            r = self._xfer(0x8F)
            if r:
                self.set_value("color", COLORS.get(r[2], f"#{r[2]}"))

    def poll(self) -> None:
        if self._read_link():
            self._read_battery()

    def apply(self, control_id, value):
        if control_id in TOGGLES:
            get, set_ = TOGGLES[control_id]
            self._xfer(set_, int(bool(value)))
            r = self._xfer(get)
            self.set_value(control_id, (r[2] == 1) if r else bool(value))
        elif control_id == "auto_off":
            self._xfer(0x02, int(value) & 0xFF)
            r = self._xfer(0x85)
            self.set_value("auto_off", r[2] if r else int(value))
        elif control_id == "sidetone_level":
            self._xfer(0x05, max(-5, min(5, int(value))) & 0xFF)
            r = self._xfer(0x88)
            if r:
                self.set_value("sidetone_level", s8(r[2]))
        else:
            raise KeyError(control_id)

    def handle_input(self, report: bytes) -> None:
        if len(report) < 3 or report[0] != 0x66:
            return
        ev, v = report[1], report[2]
        if ev == EV_MUTE:
            self.set_value("mic_mute", v == 1)
        elif ev == EV_SIDETONE:
            self.set_value("sidetone", v == 1)
        elif ev == EV_LINK:
            self.set_online(v == 1)
        elif ev == EV_CHARGING:
            old = self.values.get("battery")
            if isinstance(old, BatteryValue):
                self.set_value("battery", BatteryValue(old.level, v == 1, v == 2, old.voltage_mv))
        elif ev == EV_BATTERY and len(report) >= 5 and (report[2] or report[3]):
            old = self.values.get("battery")
            charging = old.charging if isinstance(old, BatteryValue) else None
            self.set_value("battery", BatteryValue(report[4], charging, False, report[2] << 8 | report[3]))


BASE = (
    Battery("battery", "Battery", Group.BATTERY),
    Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, "Same as the button on the headset"),
    Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
)


class CloudIIIWireless(Headset66):
    name = "HyperX Cloud III Wireless"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x05B7, "dongle"), (0x03F0, 0x0C9D, "dongle"), (0x03F0, 0x0FCC, "dongle, rev. 2"))
    controls = BASE + (
        Toggle("playback_mute", "Mute audio", Group.AUDIO, "Silences the headset speakers"),
        Choice("auto_off", "Automatic power off", Group.POWER, "After this much silence", options=AUTO_OFF),
        Info("color", "Color", Group.INFO),
    )
    sources = ("https://github.com/LennardKittner/HyperHeadset", "https://github.com/HeyOkay/HaloBattery")


class CloudIICoreWireless(Headset66):
    name = "HyperX Cloud II Core Wireless"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x0995, "dongle"), (0x03F0, 0x069F, "dongle"), (0x03F0, 0x0795, "dongle, second mode"))
    controls = BASE + (
        Range("sidetone_level", "Monitoring volume", Group.MICROPHONE, min=-5, max=5, step=1),
        Toggle("noise_gate", "Noise gate", Group.MICROPHONE, "Cuts background noise when you are not talking"),
        Toggle("playback_mute", "Mute audio", Group.AUDIO, "Silences the headset speakers"),
        Choice("auto_off", "Automatic power off", Group.POWER, "After this much silence", options=AUTO_OFF),
    )
    sources = ("https://github.com/LennardKittner/HyperHeadset/issues/27", "https://github.com/HeyOkay/HaloBattery")


MODELS = (CloudIIIWireless, CloudIICoreWireless)
