"""Smaller headset families:

- Cloud III wired / Cloud Alpha Air: feature report 0x20 (62 bytes); only sidetone on/off is known
  (20 86 01 / 20 86 00), there is no read.
- Avnera chipsets (Cloud Stinger Core Wireless, Cloud Core Wireless): feature report 0xFF; the reply
  is fetched with GET_FEATURE(0xFF) and only battery voltage/charging state are known.
- Universal-protocol headsets (Cloud Alpha 2 Wireless, Cloud Flight 2): see universal.py.
Full notes: docs/devices/headsets.md
"""
from __future__ import annotations

import time

from ..controls import Battery, BatteryValue, Choice, Group, Range, Toggle
from .base import Driver, Kind, Support
from .universal import EV_LINK, REPORT_EVENT, UniversalDevice


# ------------------------------------------------------------------ Cloud III wired
class CloudIIIWired(Driver):
    name = "HyperX Cloud III"
    kind = Kind.HEADSET
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x089D, "USB adapter"), (0x03F0, 0x03CC, "USB-C adapter (2026)"))
    interfaces = (3,)
    controls = (
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)",
               readable=False, persist=True),
    )
    sources = ("https://github.com/Sapd/HeadsetControl/issues/346", "https://github.com/Sapd/HeadsetControl/pull/525")

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.has_page(0x01C0)

    def apply(self, control_id, value):
        if control_id != "sidetone":
            raise KeyError(control_id)
        self.node.set_feature(bytes([0x20, 0x86, int(bool(value))]).ljust(62, b"\0"))
        self.set_value("sidetone", bool(value))


class CloudIIIWiredOther(CloudIIIWired):
    name = "HyperX Cloud III"
    support = Support.EXPERIMENTAL
    ids = ((0x03F0, 0x0ACE, "USB adapter (second source)"),)
    sources = ("NGENUITY 3.1 hub: Cloud3 protocol",)


class CloudAlphaAir(CloudIIIWired):
    name = "HyperX Cloud Alpha Air"
    support = Support.EXPERIMENTAL
    ids = ((0x03F0, 0x07D0, ""),)
    interfaces = None
    sources = ("NGENUITY 3.1 hub: Cloud3 protocol",)


# ------------------------------------------------------------------------- Avnera
STINGER_CORE_DISCHARGING = (3517, 3651, 3700, 3738, 3763, 3785, 3838, 3905, 3954, 4042, 4121)
STINGER_CORE_CHARGING = (3400, 3831, 3871, 3916, 3930, 3946, 3967, 4000, 4050, 4090, 4130)
AVNERA_BATTERY = bytes.fromhex("FF 07 00 FD 04 0C F1 02 01 04 F0 0C")
AVNERA_LINK = bytes.fromhex("FF 07 00 FD 04 00 00 02 82 03 05 29 0F 00 00 03 68 10")


def curve_percent(mv: int, curve: tuple[int, ...]) -> int:
    """11-point curve (0, 10, ... 100 %) with linear interpolation."""
    if mv <= curve[0]:
        return 0
    for i in range(10):
        if mv <= curve[i + 1]:
            return round(10 * i + 10 * (mv - curve[i]) / (curve[i + 1] - curve[i]))
    return 100


class AvneraHeadset(Driver):
    kind = Kind.HEADSET
    wireless = True
    interfaces = (3,)
    percent_from_voltage = True

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.has_page(0xFF00)

    def _query(self, pkt: bytes) -> bytes | None:
        """SET_FEATURE, then poll GET_FEATURE(0xFF): the valid reply (FF 12 05 ...) is short-lived."""
        with self.node.lock:
            self.node.set_feature(pkt.ljust(64, b"\0"))
            for _ in range(10):
                time.sleep(0.02)
                r = self.node.get_feature(0xFF, 64)
                if r[:3] == b"\xff\x12\x05":
                    return r
        return None

    def refresh(self) -> None:
        if self.has_link:
            r = self._query(AVNERA_LINK)
            self.set_online(bool(r and r[11] == 1))
            if not self.online:
                return
        r = self._query(AVNERA_BATTERY)
        if r is None:  # the old voltage stays in the report after power-off: don't show it
            self.set_online(False)
            return
        self.set_online(True)
        state, mv = r[9], r[11] | r[12] << 8
        charging = state == 0x05
        level = None
        if self.percent_from_voltage:
            level = curve_percent(mv, STINGER_CORE_CHARGING if charging else STINGER_CORE_DISCHARGING)
        self.set_value("battery", BatteryValue(level=100 if state == 0x06 else level, charging=charging,
                                               full=state == 0x06, voltage_mv=mv))

    has_link = True


class CloudStingerCoreWireless(AvneraHeadset):
    name = "HyperX Cloud Stinger Core Wireless"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x0A93, "dongle (PlayStation)"),)
    controls = (Battery("battery", "Battery", Group.BATTERY, "Estimated from the battery voltage"),)
    sources = ("https://github.com/davidsantanaalves/HyperBatteryMonitor/pull/6",)


class CloudStingerCoreWirelessKingston(CloudStingerCoreWireless):
    support = Support.EXPERIMENTAL
    ids = ((0x0951, 0x170B, "dongle"),)


class CloudCoreWireless(AvneraHeadset):
    name = "HyperX Cloud Core Wireless"
    support = Support.EXPERIMENTAL  # voltage confirmed, but no calibrated percentage
    ids = ((0x0951, 0x173F, "dongle"),)
    has_link = False
    percent_from_voltage = False
    controls = (Battery("battery", "Battery", Group.BATTERY, "Only the voltage is known for this model"),)
    sources = ("https://github.com/LennardKittner/HyperHeadset/issues/59",)


# ---------------------------------------------------------------- Universal headsets
AUDIO_READ, AUDIO_WRITE = (0x60, 0x02), (0x60, 0x01)
# offsets inside the 12-byte audio block (block = reply bytes [4..15], write payload [2..13])
BLK_SIDETONE, BLK_SIDETONE_LEVEL, BLK_CHAT_MIX, BLK_EQ = 4, 5, 8, 11
CHAT_MIX_CENTER = 0x80  # 0x7B all game ... 0x85 all chat


class CloudAlpha2Wireless(UniversalDevice):
    name = "HyperX Cloud Alpha 2 Wireless"
    kind = Kind.HEADSET
    support = Support.COMMUNITY  # confirmed on Windows; same HID bytes on Linux
    wireless = True
    ids = ((0x03F0, 0x08BE, "base station"),)
    interfaces = (2,)
    controls = (
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
        Range("sidetone_level", "Monitoring volume", Group.MICROPHONE, min=0, max=20, step=1),
        Range("chat_mix", "Game / chat balance", Group.AUDIO, "−5 all game, +5 all chat", min=-5, max=5, step=1),
        Choice("eq_preset", "Equalizer preset", Group.AUDIO, options=((1, "Preset 1"), (2, "Preset 2"), (3, "Preset 3"))),
    )
    sources = ("https://github.com/Sapd/HeadsetControl/pull/590", "https://github.com/Dasio/HeadsetAutoSwitch")

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0x60) is not None

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._block: bytes | None = None

    def refresh(self) -> None:
        if not self._read_link():
            return
        self._read_battery()
        self._read_audio()

    def poll(self) -> None:
        if self._read_link():
            self._read_battery()

    def _read_audio(self) -> None:
        r = self._read(AUDIO_READ)
        if not r:
            return
        self._block = bytes(r[4:16])
        b = self._block
        self.set_value("sidetone", b[BLK_SIDETONE] == 1)
        self.set_value("sidetone_level", b[BLK_SIDETONE_LEVEL])
        self.set_value("chat_mix", b[BLK_CHAT_MIX] - CHAT_MIX_CENTER)
        if b[BLK_EQ] in (1, 2, 3):
            self.set_value("eq_preset", b[BLK_EQ])

    def apply(self, control_id, value):
        self._read_audio()  # the base only accepts the whole block: read, change one byte, write back
        if self._block is None:
            raise ValueError("audio settings not read yet")
        block = bytearray(self._block)
        if control_id == "sidetone":
            block[BLK_SIDETONE] = int(bool(value))
        elif control_id == "sidetone_level":
            block[BLK_SIDETONE_LEVEL] = max(0, min(20, int(value)))
        elif control_id == "chat_mix":
            block[BLK_CHAT_MIX] = CHAT_MIX_CENTER + max(-5, min(5, int(value)))
        elif control_id == "eq_preset":
            block[BLK_EQ] = max(1, min(3, int(value)))
        else:
            raise KeyError(control_id)
        self._write(AUDIO_WRITE, *block)
        self._read_audio()

    def handle_input(self, report: bytes) -> None:
        if len(report) >= 3 and report[0] == REPORT_EVENT:
            if report[1] == EV_LINK:
                self.set_online(report[2] == 1)
            elif report[1] == 0x13 and len(report) >= 4:
                old = self.values.get("battery")
                charging = old.charging if isinstance(old, BatteryValue) else None
                self.set_value("battery", BatteryValue(report[3], charging))


class CloudFlight2(UniversalDevice):
    name = "HyperX Cloud Flight 2"
    kind = Kind.HEADSET
    support = Support.EXPERIMENTAL
    wireless = True
    ids = ((0x03F0, 0x0AC1, "dongle"), (0x03F0, 0x0CC1, "dongle (Xbox)"))
    interfaces = (3,)
    controls = (Battery("battery", "Battery", Group.BATTERY),)
    sources = ("https://github.com/davidsantanaalves/HyperBatteryMonitor",)

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0x50) is not None

    def refresh(self) -> None:
        if self._read_link():
            self._read_battery()

    def handle_input(self, report: bytes) -> None:
        if len(report) >= 3 and report[0] == REPORT_EVENT and report[1] == EV_LINK:
            self.set_online(report[2] == 1)


MODELS = (CloudIIIWired, CloudIIIWiredOther, CloudAlphaAir, CloudStingerCoreWireless,
          CloudStingerCoreWirelessKingston, CloudCoreWireless, CloudAlpha2Wireless, CloudFlight2)
