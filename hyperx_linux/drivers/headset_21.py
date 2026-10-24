"""Cloud Alpha Wireless ("21 BB" protocol) and Cloud Flight Wireless ("21 FF 05").

Alpha Wireless: request = output report 21 BB <cmd> <value>; reply = 21 BB <cmd> <value>...
SETs echo 21 BB <cmd> <value> 01. Events 21 BB <22 sidetone|23 mute|24 link|25 battery|26 charging>.
The sidetone level command is left out: its scale is unknown.

Cloud Flight: only battery voltage (21 FF 05 -> 21 FF 05 <mV hi> <mV lo>); power and mute arrive as
2-byte events (64 01 on, 64 03 off, 65 04 muted). Full notes: docs/devices/headsets.md
"""
from __future__ import annotations

from ..controls import Battery, BatteryValue, Choice, Group, Info, Toggle
from .base import Driver, Kind, Support

AUTO_OFF = ((0, "Never"), (10, "10 min"), (20, "20 min"), (30, "30 min"))
COLORS = {0: "Black", 1: "White", 2: "Black/Red"}
ALPHA = {  # control id: (GET, SET)
    "sidetone": (0x05, 0x10),
    "voice_prompts": (0x09, 0x13),
    "mic_mute": (0x0A, 0x15),
}


class CloudAlphaWireless(Driver):
    name = "HyperX Cloud Alpha Wireless"
    kind = Kind.HEADSET
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x03F0, 0x098D, "dongle"), (0x0951, 0x1743, "dongle"), (0x0951, 0x1765, "dongle"),
           (0x03F0, 0x1743, "dongle"), (0x03F0, 0x1765, "dongle"))
    interfaces = (3,)
    controls = (
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, "Same as the button on the headset"),
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
        Choice("auto_off", "Automatic power off", Group.POWER, "After this much inactivity", options=AUTO_OFF),
        Toggle("voice_prompts", "Voice prompts", Group.SYSTEM, "Headset voice on power on, mute, low battery"),
        Info("color", "Color", Group.INFO),
    )
    sources = ("https://github.com/LennardKittner/HyperHeadset/issues/26", "https://github.com/Sapd/HeadsetControl")

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0x21) is not None

    def _xfer(self, cmd: int, *args: int) -> bytes | None:
        pkt = bytes([0x21, 0xBB, cmd, *args]).ljust(31, b"\0")
        return self.node.request(lambda: self.node.write(pkt),
                                 lambda r: len(r) >= 4 and r[:3] == pkt[:3], timeout=1.5)

    def refresh(self) -> None:
        r = self._xfer(0x03)
        self.set_online(bool(r and r[3] == 0x02))
        if not self.online:
            return
        self._read_battery()
        for cid, (get, _set) in ALPHA.items():
            r = self._xfer(get)
            if r:
                self.set_value(cid, r[3] == 1)
        r = self._xfer(0x07)
        if r:
            self.set_value("auto_off", r[3])
        r = self._xfer(0x0E)
        if r:
            self.set_value("color", COLORS.get(r[3], f"#{r[3]}"))

    def poll(self) -> None:
        r = self._xfer(0x03)
        self.set_online(bool(r and r[3] == 0x02))
        if self.online:
            self._read_battery()

    def _read_battery(self) -> None:
        r = self._xfer(0x0B)
        c = self._xfer(0x0C)
        if r:
            mv = r[4] << 8 | r[5]
            self.set_value("battery", BatteryValue(level=r[3], charging=bool(c and c[3] == 1),
                                                   voltage_mv=mv if 2500 < mv < 5000 else None))

    def apply(self, control_id, value):
        if control_id in ALPHA:
            get, set_ = ALPHA[control_id]
            self._xfer(set_, int(bool(value)))
            r = self._xfer(get)
            self.set_value(control_id, (r[3] == 1) if r else bool(value))
        elif control_id == "auto_off":
            self._xfer(0x12, int(value) & 0xFF)
            r = self._xfer(0x07)
            self.set_value("auto_off", r[3] if r else int(value))
        else:
            raise KeyError(control_id)

    def handle_input(self, report: bytes) -> None:
        if len(report) < 4 or report[:2] != b"\x21\xbb":
            return
        ev, v = report[2], report[3]
        if ev == 0x22:
            self.set_value("sidetone", v == 1)
        elif ev == 0x23:
            self.set_value("mic_mute", v == 1)
        elif ev == 0x24:
            self.set_online(v == 0x02)
        elif ev in (0x25, 0x26):
            old = self.values.get("battery")
            if isinstance(old, BatteryValue):
                if ev == 0x25:
                    self.set_value("battery", BatteryValue(v, old.charging, old.full, old.voltage_mv))
                else:
                    self.set_value("battery", BatteryValue(old.level, v == 1, old.full, old.voltage_mv))


# Voltage -> percent while discharging (HyperHeadset's 20-step table, linearised between points).
FLIGHT_CURVE = ((3328, 0), (3500, 15), (3650, 35), (3750, 55), (3850, 75), (3970, 100))
FLIGHT_CHARGING_MV = 0x1014  # >= while on the cable; sources disagree on the exact threshold


def flight_percent(mv: int) -> int:
    if mv <= FLIGHT_CURVE[0][0]:
        return 0
    for (v0, p0), (v1, p1) in zip(FLIGHT_CURVE, FLIGHT_CURVE[1:]):
        if mv <= v1:
            return round(p0 + (p1 - p0) * (mv - v0) / (v1 - v0))
    return 100


class CloudFlight(Driver):
    name = "HyperX Cloud Flight Wireless"
    kind = Kind.HEADSET
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x0951, 0x16C4, "dongle"), (0x0951, 0x1723, "dongle, rev. 2"), (0x0951, 0x1749, "dongle (PS)"),
           (0x03F0, 0x0E90, "dongle"))
    interfaces = (3,)
    controls = (
        Battery("battery", "Battery", Group.BATTERY, "Estimated from the battery voltage"),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, "Use the button on the headset", writable=False),
    )
    sources = ("https://github.com/kondinskis/hyperx-cloud-flight", "https://github.com/alex-bakaldin/hyperx-cloud-flight-wireless")

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and (info.descriptor.report_size("out", 0x21) or 0) >= 19

    def refresh(self) -> None:
        pkt = bytes([0x21, 0xFF, 0x05]).ljust(20, b"\0")
        r = self.node.request(lambda: self.node.write(pkt),
                              lambda r: len(r) >= 5 and r[:3] == pkt[:3], timeout=1.5)
        if r is None:
            return
        mv = r[3] << 8 | r[4]
        charging = mv >= FLIGHT_CHARGING_MV
        self.set_online(True)
        self.set_value("battery", BatteryValue(level=None if charging else flight_percent(mv),
                                               charging=charging, voltage_mv=mv))

    def handle_input(self, report: bytes) -> None:
        if len(report) == 2:
            if report[0] == 0x64:
                self.set_online(report[1] == 0x01)  # the manager re-reads the battery when it comes back
            elif report[0] == 0x65:
                self.set_value("mic_mute", report[1] == 0x04)


MODELS = (CloudAlphaWireless, CloudFlight)
