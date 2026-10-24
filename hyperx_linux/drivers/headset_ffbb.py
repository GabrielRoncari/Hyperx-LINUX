"""Headsets with the "06 FF BB" (HP) and "Kingston 62-byte" protocols.

HP family (Cloud II Wireless 0696/018B, Cloud Stinger 2 Wireless):
    request = output report 06 FF BB <cmd> <arg> (20 bytes); reply = input report 06 FF BB <cmd> ...
Kingston family (Cloud II Wireless 0951:1718, Cloud Flight S):
    GET_INPUT(0x06) before every write (without it Linux returns EPIPE), then output report
    06 00 02 00 9A 00 00 68 4A 8E 0A 00 00 00 BB <cmd> <arg> (62 bytes); reply = input report 0B 00 BB <cmd> ...

Command 01 (link status) is never sent: users report it resets state and unmutes the microphone.
Full notes: docs/devices/headsets.md
"""
from __future__ import annotations

from ..controls import Battery, BatteryValue, Choice, Group, Range, Toggle
from .base import Driver, Kind, Support

AUTO_OFF = ((0, "Never"), (10, "10 min"), (20, "20 min"), (30, "30 min"))


def s8(b: int) -> int:
    return b - 256 if b > 127 else b


class HPCloudII(Driver):
    """06 FF BB protocol."""

    kind = Kind.HEADSET
    wireless = True
    interfaces = (3,)
    mic_mute_writable = True
    sidetone_level_reapply = False  # Stinger 2: the level only takes effect when sidetone is switched on

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and (info.descriptor.report_size("out", 0x06) or 0) >= 19

    def _xfer(self, cmd: int, *args: int) -> bytes | None:
        pkt = bytes([0x06, 0xFF, 0xBB, cmd, *args]).ljust(20, b"\0")
        return self.node.request(lambda: self.node.write(pkt),
                                 lambda r: len(r) >= 5 and r[:4] == pkt[:4])

    def refresh(self) -> None:
        if not self._read_battery():
            return
        for cid, cmd in (("mic_mute", 0x05), ("sidetone", 0x06)):
            r = self._xfer(cmd)
            if r:
                self.set_value(cid, r[4] == 1)
        r = self._xfer(0x07)
        if r:
            self.set_value("auto_off", r[4])
        if self.has("sidetone_level"):
            r = self._xfer(0x0B)
            if r:
                self.set_value("sidetone_level", s8(r[4]))

    def poll(self) -> None:
        self._read_battery()

    def _read_battery(self) -> bool:
        r = self._xfer(0x02)
        if r is None:
            self.set_online(False)
            return False
        self.set_online(True)
        c = self._xfer(0x03)
        state = c[4] if c else 0
        mv = r[5] << 8 | r[6]
        self.set_value("battery", BatteryValue(level=r[7], charging=state == 1, full=state == 2,
                                               voltage_mv=mv or None))
        return True

    def apply(self, control_id, value):
        if control_id == "mic_mute" and self.mic_mute_writable:
            r = self._xfer(0x20, int(bool(value)))
            self.set_value("mic_mute", bool(r[4]) if r else bool(value))
        elif control_id == "sidetone":
            r = self._xfer(0x21, int(bool(value)))
            if r:
                self.set_value("sidetone", r[4] == 1)
        elif control_id == "auto_off":
            r = self._xfer(0x22, int(value) & 0xFF)
            if r:
                self.set_value("auto_off", r[4])
        elif control_id == "sidetone_level":
            level = max(-30, min(0, int(value)))  # dB; +32 dB was reported as deafening
            r = self._xfer(0x23, level & 0xFF)
            if r:
                self.set_value("sidetone_level", s8(r[4]))
            if self.sidetone_level_reapply and self.values.get("sidetone"):
                self._xfer(0x21, 0)
                self._xfer(0x21, 1)
        else:
            raise KeyError(control_id)

    def handle_input(self, report: bytes) -> None:
        if len(report) < 5 or report[:3] != b"\x06\xff\xbb":
            return
        cmd, v = report[3], report[4]
        if cmd == 0x20:
            self.set_value("mic_mute", v == 1)
        elif cmd == 0x01:  # power state broadcast by the dongle
            self.set_online(v in (1, 4))
        elif cmd == 0x21:
            self.set_value("sidetone", v == 1)


def hp_controls(mic_writable: bool, level: bool):
    ctrls = [
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, writable=mic_writable,
               subtitle="" if mic_writable else "Flip the microphone up to mute"),
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
    ]
    if level:
        ctrls.append(Range("sidetone_level", "Monitoring volume", Group.MICROPHONE, min=-30, max=0, step=1, unit="dB"))
    ctrls.append(Choice("auto_off", "Automatic power off", Group.POWER, "After this much inactivity", options=AUTO_OFF))
    return tuple(ctrls)


class CloudIIWireless(HPCloudII):
    name = "HyperX Cloud II Wireless"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x0696, "dongle"), (0x03F0, 0x018B, "dongle, rev. 2"))
    controls = hp_controls(mic_writable=True, level=False)  # level semantics only measured on the Stinger 2
    sources = ("https://github.com/Sapd/HeadsetControl", "https://github.com/LennardKittner/HyperHeadset")


class CloudStinger2Wireless(HPCloudII):
    name = "HyperX Cloud Stinger 2 Wireless"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x0D93, "dongle"),)
    mic_mute_writable = False
    sidetone_level_reapply = True
    controls = hp_controls(mic_writable=False, level=True)
    sources = ("https://github.com/lbkeppler/lowerx", "https://github.com/oauthul/hsctl")


# --------------------------------------------------------------- Kingston family


class KingstonCloud(Driver):
    """62-byte protocol of the Kingston-era wireless headsets."""

    kind = Kind.HEADSET
    wireless = True
    header = bytes.fromhex("06 00 02 00 9A 00 00 68 4A 8E 0A 00 00 00 BB")

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.has_page(0xFF13)

    def _xfer(self, cmd: int, *args: int, wait: bool = True) -> bytes | None:
        pkt = (self.header + bytes([cmd, *args])).ljust(62, b"\0")

        def send():
            try:
                self.node.get_input(0x06, 64)  # required before writing, see module docstring
            except Exception:
                pass  # the Flight S rejects it but works anyway
            self.node.write(pkt)
        if not wait:
            with self.node.lock:
                send()
            return None
        return self.node.request(send, lambda r: len(r) >= 5 and r[0] == 0x0B and r[2] == 0xBB and r[3] == cmd)

    def refresh(self) -> None:
        if not self._read_battery():
            return
        r = self._xfer(0x1A)
        if r:
            self.set_value("auto_off", r[4])

    def poll(self) -> None:
        self._read_battery()

    def _read_battery(self) -> bool:
        r = self._xfer(0x02)
        if r is None or (r[5] == 0 and r[6] == 0):  # no reply, or an empty reading: headset off
            self.set_online(False)
            return False
        self.set_online(True)
        c = self._xfer(0x03)
        state = c[4] if c else 0
        self.set_value("battery", BatteryValue(level=r[7], charging=state == 1, full=state == 2))
        return True

    def apply(self, control_id, value):
        if control_id == "sidetone":
            self._xfer(0x19, int(bool(value)), wait=False)
            self.set_value("sidetone", bool(value))
        elif control_id == "auto_off":
            self._xfer(0x18, int(value) & 0xFF, wait=False)
            r = self._xfer(0x1A)
            self.set_value("auto_off", r[4] if r else int(value))
        else:
            raise KeyError(control_id)

    def handle_input(self, report: bytes) -> None:
        if len(report) >= 5 and report[0] == 0x0B and report[2] == 0xBB:
            cmd, v = report[3], report[4]
            if cmd == 0x08:
                self.set_value("mic_mute", v == 1)
            elif cmd == 0x01:
                self.set_online(v in (1, 4))
        elif len(report) >= 5 and report[0] == 0x0A and report[3] == 0x03:
            bits = report[4]  # Flight S audio state: 0x02 mic muted, 0x10 sidetone on
            self.set_value("mic_mute", bool(bits & 0x02))
            self.set_value("sidetone", bool(bits & 0x10))


KINGSTON_CONTROLS = (
    Battery("battery", "Battery", Group.BATTERY),
    Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, "Use the button on the headset", writable=False),
    Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)", readable=False),
    Choice("auto_off", "Automatic power off", Group.POWER, "After this much inactivity", options=AUTO_OFF),
)


class CloudIIWirelessKingston(KingstonCloud):
    name = "HyperX Cloud II Wireless"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x1718, "dongle (Kingston)"),)
    interfaces = (3,)
    controls = KINGSTON_CONTROLS
    sources = ("https://github.com/LennardKittner/HyperHeadset", "https://github.com/Sapd/HeadsetControl")


class CloudFlightS(KingstonCloud):
    name = "HyperX Cloud Flight S"
    support = Support.EXPERIMENTAL  # reads confirmed on hardware; sidetone/auto-off writes are not
    ids = ((0x0951, 0x16EA, "dongle"), (0x0951, 0x16EB, "dongle, rev. 2"))
    controls = KINGSTON_CONTROLS
    sources = ("https://github.com/hahuk/gohyper", "https://github.com/SimyriK/HyperHeadset")


MODELS = (CloudIIWireless, CloudStinger2Wireless, CloudIIWirelessKingston, CloudFlightS)
