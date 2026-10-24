"""HyperX Cloud III S Wireless (2.4 GHz dongle).

Request  = output report 0x0C (64 bytes): 0C 02 03 <rw> 00 <op> <args...>, rw 01 = GET, 00 = SET
Reply    = input report 0x0C, same header, value from byte 6 (GET only; SETs are not acked)
Event    = input report 0x0D: 0D 02 03 00 <type> <value>
Full notes and hardware validation: docs/devices/cloud3s.md
"""
from __future__ import annotations

from ..controls import Battery, BatteryValue, Choice, Equalizer, Group, Info, Range, Toggle
from .base import Driver, Kind, Support

REPORT_CMD, REPORT_EVENT = 0x0C, 0x0D
GET, SET = 0x01, 0x00
NO_VALUE = 0xFF  # headset off / out of range

OP_SET_MIC_MUTE, OP_GET_LINK, OP_GET_MIC_MUTE, OP_GET_BATTERY = 0x01, 0x02, 0x04, 0x06
OP_SET_VOICE_PROMPTS, OP_SET_SIDETONE, OP_GET_VOICE_PROMPTS, OP_GET_SIDETONE = 0x0B, 0x0D, 0x14, 0x16
OP_SET_SIDETONE_LEVEL, OP_GET_SIDETONE_LEVEL = 0x44, 0x45
OP_SET_PLAYBACK_MUTE, OP_GET_PLAYBACK_MUTE, OP_GET_CHARGING = 0x46, 0x47, 0x48
OP_SET_AUTO_OFF, OP_GET_AUTO_OFF, OP_GET_COLOR, OP_SET_EQ_BAND = 0x4A, 0x4B, 0x4D, 0x5F

EV_BATTERY, EV_MIC_MUTE, EV_SIDETONE, EV_CHARGING, EV_LINK = 1, 3, 5, 10, 12

COLORS = {
    0: "Black", 1: "White", 2: "Black/Red", 3: "Black/Blue", 4: "Black/Green", 5: "White/Pink",
    6: "White/Blue", 7: "White/Green", 8: "Gray/Green", 9: "Black/White", 10: "Silver/Black",
    11: "Blue/Black", 12: "White/Purple", 13: "White/Black", 14: "Black/Purple", 15: "Gray/Red",
    16: "Purple", 22: "White/Silver",
}

EQ_PRESETS = (
    ("Flat", (0,) * 10),
    ("Bass", (6, 5, 4, 2, 0, 0, 0, 0, 0, 0)),
    ("Treble", (0, 0, 0, 0, 0, 0, 2, 4, 5, 6)),
    ("V-shape", (5, 4, 2, 0, -2, -2, 0, 2, 4, 5)),
    ("Voice", (-3, -2, -1, 0, 2, 3, 3, 2, 0, -1)),
    ("FPS", (-4, -4, -3, -1, 0, 2, 4, 5, 3, 1)),
)


def s8(b: int) -> int:
    return b - 256 if b > 127 else b


class Cloud3SWireless(Driver):
    name = "HyperX Cloud III S Wireless"
    kind = Kind.HEADSET
    support = Support.VERIFIED
    wireless = True
    ids = (
        (0x03F0, 0x06BE, "2.4 GHz dongle, rev. 1"),
        (0x03F0, 0x02CC, "2.4 GHz dongle, rev. 2"),
    )
    sources = (
        "https://github.com/Tomlacko/cloud3s-web-control/blob/main/docs/PROTOCOL.md",
        "https://github.com/Sapd/HeadsetControl/issues/486",
    )
    controls = (
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, "Same as the button on the headset"),
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
        Range("sidetone_level", "Monitoring volume", Group.MICROPHONE, min=-6, max=6, step=1),
        Toggle("playback_mute", "Mute audio", Group.AUDIO, "Silences the headset speakers"),
        Equalizer("eq", "Equalizer", Group.AUDIO, readable=False, persist=True,
                  bands_hz=(32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000),
                  min_db=-8.0, max_db=8.0, presets=EQ_PRESETS),
        Choice("auto_off", "Automatic power off", Group.POWER, "After this much silence",
               options=((0, "Never"), (600, "10 min"), (1200, "20 min"), (1800, "30 min")), unit="s"),
        Toggle("voice_prompts", "Voice prompts", Group.SYSTEM, "Headset voice on power on, mute, low battery"),
        Info("color", "Color", Group.INFO),
    )

    interfaces = (3,)

    @classmethod
    def match_interface(cls, info):
        # interface 3 and the control collection (reports 0x0C/0x0D)
        return super().match_interface(info) and info.descriptor.has_page(0x01C0)

    # ------------------------------------------------------------- transport
    def _packet(self, rw: int, op: int, *args: int) -> bytes:
        p = bytearray(64)
        p[0:6] = bytes([REPORT_CMD, 0x02, 0x03, rw, 0x00, op])
        p[6:6 + len(args)] = bytes(a & 0xFF for a in args)
        return bytes(p)

    def _get(self, op: int) -> bytes | None:
        pkt = self._packet(GET, op)
        return self.node.request(
            lambda: self.node.write(pkt),
            lambda r: len(r) > 7 and r[0] == REPORT_CMD and r[1:4] == b"\x02\x03\x01" and r[5] == op,
        )

    def _set(self, op: int, *args: int) -> None:
        self.node.send(self._packet(SET, op, *args))  # no ack: confirm with the matching GET

    # ----------------------------------------------------------------- reads
    def _read(self, op: int) -> int | None:
        r = self._get(op)
        if r is None or r[6] == NO_VALUE:
            return None
        return r[6]

    def _read_battery(self) -> None:
        r = self._get(OP_GET_BATTERY)
        charging = self._read(OP_GET_CHARGING)
        if r is None or r[6] == NO_VALUE:
            return
        mv = (r[7] << 8) | r[8]
        self.set_value("battery", BatteryValue(level=r[6], charging=charging == 1, full=charging == 2,
                                               voltage_mv=mv or None))

    def _read_link(self) -> bool:
        link = self._read(OP_GET_LINK)
        self.set_online(link == 0x02)
        return bool(self.online)

    def refresh(self) -> None:
        if not self._read_link():
            return
        self._read_battery()
        for cid, op in (("mic_mute", OP_GET_MIC_MUTE), ("playback_mute", OP_GET_PLAYBACK_MUTE),
                        ("sidetone", OP_GET_SIDETONE), ("voice_prompts", OP_GET_VOICE_PROMPTS)):
            v = self._read(op)
            if v is not None:
                self.set_value(cid, v == 1)
        r = self._get(OP_GET_SIDETONE_LEVEL)
        if r is not None and r[6] != NO_VALUE:
            self.set_value("sidetone_level", s8(r[6]))
        r = self._get(OP_GET_AUTO_OFF)
        if r is not None and (r[6], r[7]) != (0xFF, 0xFF):
            self.set_value("auto_off", (r[6] << 8) | r[7])
        color = self._read(OP_GET_COLOR)
        if color is not None:
            self.set_value("color", COLORS.get(color, f"#{color}"))

    def poll(self) -> None:
        if self._read_link():
            self._read_battery()

    # ---------------------------------------------------------------- writes
    def apply(self, control_id: str, value) -> None:
        if control_id == "mic_mute":
            self._set(OP_SET_MIC_MUTE, int(bool(value)))
            v = self._read(OP_GET_MIC_MUTE)
        elif control_id == "playback_mute":
            self._set(OP_SET_PLAYBACK_MUTE, int(bool(value)))
            v = self._read(OP_GET_PLAYBACK_MUTE)
        elif control_id == "sidetone":
            self._set(OP_SET_SIDETONE, int(bool(value)))
            v = self._read(OP_GET_SIDETONE)
        elif control_id == "voice_prompts":
            self._set(OP_SET_VOICE_PROMPTS, int(bool(value)))
            v = self._read(OP_GET_VOICE_PROMPTS)
        elif control_id == "sidetone_level":
            self._set(OP_SET_SIDETONE_LEVEL, max(-6, min(6, int(value))) & 0xFF)
            r = self._get(OP_GET_SIDETONE_LEVEL)
            if r is not None and r[6] != NO_VALUE:
                self.set_value(control_id, s8(r[6]))
            return
        elif control_id == "auto_off":
            seconds = max(0, min(0xFFFF, int(value)))
            self._set(OP_SET_AUTO_OFF, seconds >> 8, seconds & 0xFF)
            r = self._get(OP_GET_AUTO_OFF)
            if r is not None:
                self.set_value(control_id, (r[6] << 8) | r[7])
            return
        elif control_id == "eq":
            self._write_eq(list(value), depop=True)
            self.set_value(control_id, list(value))
            return
        else:
            raise KeyError(control_id)
        if v is not None:
            self.set_value(control_id, v == 1)

    def write_eq_live(self, gains: list[float]) -> None:
        """While dragging a slider: no depop flag (NGENUITY does the same)."""
        self._write_eq(gains, depop=False)
        self.set_value("eq", list(gains))

    def _write_eq(self, gains: list[float], depop: bool) -> None:
        last = len(gains) - 1
        for band, gain in enumerate(gains):
            centi = max(-800, min(800, round(float(gain) * 100))) & 0xFFFF  # hundredths of dB, int16 BE
            self._set(OP_SET_EQ_BAND, band, centi >> 8, centi & 0xFF, 1 if depop and band == last else 0)

    # ---------------------------------------------------------------- events
    def handle_input(self, report: bytes) -> None:
        if len(report) < 6 or report[0] != REPORT_EVENT:
            return
        kind, v = report[4], report[5]
        if kind == EV_LINK:
            self.set_online(v == 1)  # the manager re-reads everything on False -> True
        elif kind == EV_MIC_MUTE:
            self.set_value("mic_mute", v == 1)
        elif kind == EV_SIDETONE:
            self.set_value("sidetone", v == 1)
        elif kind == EV_BATTERY:
            old = self.values.get("battery") or BatteryValue(level=None)
            self.set_value("battery", BatteryValue(v, old.charging, old.full, old.voltage_mv))
        elif kind == EV_CHARGING:
            old = self.values.get("battery") or BatteryValue(level=None)
            self.set_value("battery", BatteryValue(old.level, v == 1, v == 2, old.voltage_mv))


class CloudStinger3Wireless(Cloud3SWireless):
    """Same 0x0C protocol, smaller command set (NGENUITY 3.1 hub): no mic-mute SET, EQ, playback
    mute or prompts, no charging GET, and different event types (mic polarity is inverted)."""

    name = "HyperX Cloud Stinger 3 Wireless"
    support = Support.EXPERIMENTAL
    ids = (
        (0x03F0, 0x01C6, "dongle (PC)"),
        (0x03F0, 0x03C6, "dongle (PlayStation)"),
        (0x03F0, 0x0DC5, "dongle (Xbox)"),
    )
    interfaces = None  # not published; matched by the 0x01C0 control collection
    controls = (
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE, "Use the button on the headset", writable=False),
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
        Range("sidetone_level", "Monitoring volume", Group.MICROPHONE, min=-6, max=6, step=1),
        Choice("auto_off", "Automatic power off", Group.POWER, "After this much silence",
               options=((0, "Never"), (600, "10 min"), (1200, "20 min"), (1800, "30 min")), unit="s"),
        Info("color", "Color", Group.INFO),
    )
    sources = ("https://github.com/davidsantanaalves/HyperBatteryMonitor",
               "NGENUITY 3.1 hub, Stinger3WirelessProtocol: GET 02/04/06/16/45/4B/4D, SET 0D/44/4A")

    def _read_battery(self) -> None:
        level = self._read(OP_GET_BATTERY)
        if level is not None:
            old = self.values.get("battery")
            charging = old.charging if isinstance(old, BatteryValue) else None
            self.set_value("battery", BatteryValue(level=level, charging=charging))

    def refresh(self) -> None:
        if not self._read_link():
            return
        self._read_battery()
        for cid, op in (("mic_mute", OP_GET_MIC_MUTE), ("sidetone", OP_GET_SIDETONE)):
            v = self._read(op)
            if v is not None:
                self.set_value(cid, v == 1)
        r = self._get(OP_GET_SIDETONE_LEVEL)
        if r is not None and r[6] != NO_VALUE:
            self.set_value("sidetone_level", s8(r[6]))
        r = self._get(OP_GET_AUTO_OFF)
        if r is not None and (r[6], r[7]) != (0xFF, 0xFF):
            self.set_value("auto_off", (r[6] << 8) | r[7])
        color = self._read(OP_GET_COLOR)
        if color is not None:
            self.set_value("color", COLORS.get(color, f"#{color}"))

    def apply(self, control_id, value):
        if control_id in ("mic_mute", "playback_mute", "voice_prompts", "eq"):
            raise KeyError(control_id)
        super().apply(control_id, value)

    def handle_input(self, report: bytes) -> None:
        if len(report) < 6 or report[0] != REPORT_EVENT:
            return
        kind, v = report[4], report[5]
        old = self.values.get("battery")
        if kind == 0x0C:
            self.set_online(v == 1)
        elif kind == 0x03:
            self.set_value("mic_mute", v == 0)  # inverted compared with the GET
        elif kind == 0x0B and isinstance(old, BatteryValue):
            self.set_value("battery", BatteryValue(v, old.charging, old.full, old.voltage_mv))
        elif kind == 0x0A:
            level = old.level if isinstance(old, BatteryValue) else None
            self.set_value("battery", BatteryValue(level, v == 1))


class CloudMix2(Cloud3SWireless):
    """0x0C protocol with its own opcodes (HyperHeadset's cloud_mix_2 branch); includes hybrid ANC."""

    name = "HyperX Cloud MIX 2"
    support = Support.EXPERIMENTAL
    ids = ((0x03F0, 0x0FAE, "dongle"),)
    interfaces = None
    controls = (
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE),
        Toggle("sidetone", "Microphone monitoring", Group.MICROPHONE, "Hear your own voice (sidetone)"),
        Choice("anc", "Noise cancelling", Group.AUDIO, options=((0, "Off"), (1, "On"), (2, "Transparency"))),
    )
    sources = ("https://github.com/LennardKittner/HyperHeadset/tree/cloud_mix_2",)

    def _read_link(self) -> bool:
        self.set_online(self._read(OP_GET_LINK) == 0x01)
        return bool(self.online)

    def refresh(self) -> None:
        if not self._read_link():
            return
        level = self._read(OP_GET_BATTERY)
        if level is not None:
            self.set_value("battery", BatteryValue(level=level))
        for cid, op in (("mic_mute", OP_GET_MIC_MUTE), ("sidetone", OP_GET_SIDETONE)):
            v = self._read(op)
            if v is not None:
                self.set_value(cid, v == 1)
        anc = self._read(0x0E)
        if anc is not None:
            self.set_value("anc", anc)

    def poll(self) -> None:
        if self._read_link():
            level = self._read(OP_GET_BATTERY)
            if level is not None:
                self.set_value("battery", BatteryValue(level=level))

    def apply(self, control_id, value):
        if control_id == "anc":
            self._set(0x07, max(0, min(2, int(value))))
            v = self._read(0x0E)
            self.set_value("anc", v if v is not None else int(value))
        elif control_id in ("mic_mute", "sidetone"):
            super().apply(control_id, value)
        else:
            raise KeyError(control_id)

    def handle_input(self, report: bytes) -> None:
        if len(report) < 6 or report[0] != REPORT_EVENT:
            return
        kind, v = report[4], report[5]
        if kind == 0x01:
            self.set_value("battery", BatteryValue(level=v))
        elif kind == 0x03:
            self.set_value("mic_mute", v == 1)
        elif kind == 0x04:
            self.set_online(v == 1)
        elif kind == 0x06:
            self.set_value("anc", v)


MODELS = (Cloud3SWireless, CloudStinger3Wireless, CloudMix2)
