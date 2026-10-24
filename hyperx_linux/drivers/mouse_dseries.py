"""NGENUITY 2 "D-series" mice: Pulsefire Dart, Pulsefire Haste Wireless, Pulsefire FPS Pro (rev. CD).

64-byte output reports without a report id ([0] = opcode). Accepted commands come back as an echo
of the request with the read fields filled in; errors as <first 3 bytes> 02 EC <code>
(code 5 through the receiver = mouse asleep or out of range). Writes D0-DF only change RAM;
DE (save to EEPROM) is never sent. Full notes: docs/devices/mice.md
"""
from __future__ import annotations

from ..controls import Battery, BatteryValue, Choice, Color, Group, Range
from .base import Driver, Kind, Support

POLLING = {0: 125, 1: 250, 2: 500, 3: 1000}
ERR_LINK_DOWN = 0x05
EVENT = 0xFF


class DSeriesMouse(Driver):
    kind = Kind.MOUSE
    poll_seconds = 30.0
    dpi_unit = 50  # DPI per step in D3 02 / 53
    polling_offset = 52  # polling code inside the 50 03 config dump
    live_color_reverts = False  # True: the mouse falls back to its saved effect after ~2 s
    has_lift_off = False

    @classmethod
    def match_interface(cls, info):
        # vendor collection with 64-byte input/output reports and no report id
        return super().match_interface(info) and info.descriptor.report_size("out", 0) == 64

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._color: tuple[int, int, int] | None = None
        self._brightness = 100
        self._mask = 0x1F
        self._active = 0

    @property
    def keepalive_seconds(self):
        return 0.5 if self.live_color_reverts else None

    # ------------------------------------------------------------- transport
    def _cmd(self, *data: int) -> bytes | None:
        """Send one command and return its echo; None on error frames or timeout."""
        pkt = bytes(data) + bytes(64 - len(data))
        reply = self.node.request(lambda: self.node.write(b"\x00" + pkt),
                                  lambda r: len(r) >= 6 and r[:3] == pkt[:3], timeout=1.0)
        if reply is None:
            return None
        if reply[3] == 0x02 and reply[4] == 0xEC:
            if reply[5] == ERR_LINK_DOWN and self.wireless:
                self.set_online(False)
            return None
        return reply

    # ----------------------------------------------------------------- reads
    def refresh(self) -> None:
        if self.wireless:
            link = self._cmd(0x46)
            self.set_online(bool(link and link[3] == 0x01 and link[4] == 0x01))
            if not self.online:
                return
        self._read_battery()
        self._read_dpi()
        cfg = self._cmd(0x50, 0x03)
        if cfg and cfg[self.polling_offset] in POLLING:
            self.set_value("polling", POLLING[cfg[self.polling_offset]])
        led = self._cmd(0x52, 0x00, 0x00)
        if led:
            self._brightness = min(100, led[7])
            self.set_value("brightness", self._brightness)
            if led[4] >> 4 == 0:  # static effect: the colour is meaningful
                self._color = (led[8], led[9], led[10])
                self.set_value("color", self._color)

    def poll(self) -> None:
        if self.wireless:
            link = self._cmd(0x46)
            self.set_online(bool(link and link[3] == 0x01 and link[4] == 0x01))
            if not self.online:
                return
        self._read_battery()

    def _read_battery(self) -> None:
        r = self._cmd(0x51, 0x00, 0x00)
        if r is None or r[4] == 0xFF:
            return
        self._battery_from(r[4], r[5], r)

    battery_mv = False  # Dart reports millivolts in [7..8]
    charging_codes = (1,)  # power state byte of 51 / FF 03
    full_codes = (2,)

    def _battery_from(self, level: int, power: int, r: bytes | None = None) -> None:
        old = self.values.get("battery")
        mv = (r[7] | r[8] << 8) if r is not None and self.battery_mv else 0
        voltage = mv if 2500 < mv < 5000 else (old.voltage_mv if isinstance(old, BatteryValue) else None)
        self.set_value("battery", BatteryValue(level=level, charging=power in self.charging_codes,
                                               full=power in self.full_codes, voltage_mv=voltage))

    def _read_dpi(self) -> None:
        r = self._cmd(0x53, 0x00, 0x00)
        if not r:
            return
        self._active, self._mask = r[4], r[5]
        code = r[12 + 2 * self._active] | r[13 + 2 * self._active] << 8
        self.set_value("dpi_stage", self._active + 1)
        self.set_value("dpi", code * self.dpi_unit)
        if self.has_lift_off and r[37] in (1, 2):
            self.set_value("lift_off", r[37])

    # ---------------------------------------------------------------- writes
    def apply(self, control_id: str, value) -> None:
        if control_id == "polling":
            code = next(c for c, hz in POLLING.items() if hz == int(value))
            if self._cmd(0xD0, 0x00, 0x00, 0x01, code):
                self.set_value("polling", int(value))
        elif control_id == "dpi_stage":
            stage = int(value) - 1
            if not self._mask >> stage & 1:
                raise ValueError(f"DPI stage {value} is disabled on the mouse")
            self._cmd(0xD3, 0x00, 0x00, 0x01, stage)
            self._read_dpi()
        elif control_id == "dpi":
            steps = max(200, min(16000, int(value))) // self.dpi_unit
            self._cmd(0xD3, 0x02, self._active, 0x02, steps & 0xFF, steps >> 8)
            self._read_dpi()
        elif control_id == "lift_off" and self.has_lift_off:
            v = 2 if int(value) == 2 else 1
            self._cmd(0xD3, 0x05, 0x00, 0x01, v, v)
            self._read_dpi()
        elif control_id == "color":
            self._color = tuple(int(c) for c in value)
            self._send_led()
            self.set_value("color", self._color)
        elif control_id == "brightness":
            self._brightness = max(0, min(100, int(value)))
            self._send_led()
            self.set_value("brightness", self._brightness)
        else:
            raise KeyError(control_id)

    led_zone = 0x20  # 00 logo, 10 scroll wheel, 20 both

    def _send_led(self) -> None:
        if self._color is None or self.online is False:
            return
        r, g, b = self._color
        self._cmd(0xD2, self.led_zone, 0x00, 0x08, r, g, b, r, g, b, self._brightness, 0x00)

    def keepalive(self) -> None:
        if self.live_color_reverts:
            self._send_led()

    # ---------------------------------------------------------------- events
    def handle_input(self, report: bytes) -> None:
        if len(report) >= 5 and report[0] == EVENT and report[1] == 0x03:
            if self.wireless:
                self.set_online(report[4] != 0)
            if report[4]:
                self.set_value("dpi_stage", report[2] + 1)
                old = self.values.get("battery")
                if isinstance(old, BatteryValue):
                    self._battery_from(old.level, report[3])


def dseries_controls(lift_off: bool, battery: bool):
    ctrls = [Battery("battery", "Battery", Group.BATTERY)] if battery else []
    ctrls += [
        Range("dpi", "DPI", Group.PERFORMANCE, "Current DPI stage", min=200, max=16000, step=50),
        Choice("dpi_stage", "DPI stage", Group.PERFORMANCE, options=tuple((i, str(i)) for i in range(1, 6))),
        Choice("polling", "Polling rate", Group.PERFORMANCE, options=tuple((hz, f"{hz} Hz") for hz in POLLING.values())),
    ]
    if lift_off:
        ctrls.append(Choice("lift_off", "Lift-off distance", Group.PERFORMANCE, options=((1, "1 mm"), (2, "2 mm"))))
    ctrls += [
        Color("color", "Color", Group.LIGHTING, persist=True),
        Range("brightness", "Brightness", Group.LIGHTING, min=0, max=100, step=1, unit="%"),
    ]
    return tuple(ctrls)


DART_SOURCES = ("https://github.com/santeri3700/hyperx_pulsefire_dart_reverse_engineering",
                "https://github.com/Kota0674/pulsedart")


class Dart(DSeriesMouse):
    name = "HyperX Pulsefire Dart"
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x0951, 0x16E1, "2.4 GHz dongle"), (0x03F0, 0x068E, "2.4 GHz dongle"))
    interfaces = (2,)
    battery_mv = True
    charging_codes = (1, 2)  # 2: powered through another path (ChargePlay/Qi)
    full_codes = (3,)
    controls = dseries_controls(lift_off=False, battery=True)
    sources = DART_SOURCES


class DartCable(Dart):
    name = "HyperX Pulsefire Dart (USB cable)"
    wireless = False
    ids = ((0x0951, 0x16E2, "USB cable"), (0x03F0, 0x088E, "USB cable"))
    interfaces = (1,)


class HasteWireless(DSeriesMouse):
    name = "HyperX Pulsefire Haste Wireless"
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x03F0, 0x028E, "2.4 GHz dongle"),)
    interfaces = (2,)
    dpi_unit = 100
    polling_offset = 53
    live_color_reverts = True
    has_lift_off = True
    led_zone = 0x00
    controls = dseries_controls(lift_off=True, battery=True)
    sources = ("https://github.com/evan-razzaque/open-pulsefire-haste",)


class HasteWirelessCable(HasteWireless):
    name = "HyperX Pulsefire Haste Wireless (USB cable)"
    wireless = False
    ids = ((0x03F0, 0x048E, "USB cable"),)


class FPSProCD(Driver):
    """FPS Pro revision 'CD': D-series opcodes, but the mouse sends no echo, so nothing is readable."""

    name = "HyperX Pulsefire FPS Pro"
    kind = Kind.MOUSE
    support = Support.EXPERIMENTAL
    ids = ((0x0951, 0x1729, "rev. CD"), (0x03F0, 0x0693, "rev. CD"))
    interfaces = (2,)
    keepalive_seconds = 0.25  # NGENUITY streams the colour at 12-16 Hz
    controls = (
        Choice("polling", "Polling rate", Group.PERFORMANCE, readable=False, persist=True,
               options=tuple((hz, f"{hz} Hz") for hz in POLLING.values())),
        Color("color", "Color", Group.LIGHTING, readable=False, persist=True),
    )
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/4250",)

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0) == 64

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._color = None

    def _send(self, *data: int) -> None:
        self.node.send(b"\x00" + bytes(data) + bytes(64 - len(data)))

    def apply(self, control_id, value):
        if control_id == "polling":
            code = next(c for c, hz in POLLING.items() if hz == int(value))
            self._send(0xD0, 0x00, 0x00, 0x01, code)
            self.set_value("polling", int(value))
        elif control_id == "color":
            self._color = tuple(int(c) for c in value)
            self.keepalive()
            self.set_value("color", self._color)
        else:
            raise KeyError(control_id)

    def keepalive(self):
        if self._color:
            r, g, b = self._color
            self._send(0xD8, 0x00, 0x00, 0x06, r, g, b, r, g, b, 0x64)  # wheel + logo


MODELS = (Dart, DartCable, HasteWireless, HasteWirelessCable, FPSProCD)
