"""HP-era "Universal" protocol mice: Pulsefire Haste 2 family, Saga Pro, Saga.

Transport in universal.py. Multi-byte integers are little endian. Writes use slot 0 (RAM) only:
slot 1 is the onboard profile in flash. Full notes: docs/devices/mice.md
"""
from __future__ import annotations

from ..controls import Battery, Choice, Color, Group, Range
from .base import Kind, Support
from .universal import BATTERY, LINK, REPORT_EVENT, UniversalDevice

GET_INFO = (0x10, 0x01)
DPI_READ, DPI_WRITE = (0x32, 0x02), (0x32, 0x01)
SENSOR_READ, SENSOR_WRITE = (0x36, 0x02), (0x36, 0x01)
BRIGHT_READ, BRIGHT_WRITE = (0x40, 0x02), (0x40, 0x01)
LIVE_HEADER, LIVE_COLOR = (0x44, 0x01), (0x44, 0x02)
EV_DPI_STAGE, EV_LINK = 0x08, 0x0A

LIVE_COLOR_HOLD_S = 0.5  # the mouse falls back to its saved effect ~1.5-2 s after the last frame


def universal_controls(polling: tuple[int, ...], dpi_max: int, battery: bool, lift_off: bool):
    ctrls = []
    if battery:
        ctrls.append(Battery("battery", "Battery", Group.BATTERY))
    ctrls += [
        Range("dpi", "DPI", Group.PERFORMANCE, "Current DPI stage", min=200, max=dpi_max, step=50),
        Choice("dpi_stage", "DPI stage", Group.PERFORMANCE, options=tuple((i, str(i)) for i in range(1, 6))),
        Choice("polling", "Polling rate", Group.PERFORMANCE, options=tuple((hz, f"{hz} Hz") for hz in polling)),
    ]
    if lift_off:
        ctrls.append(Choice("lift_off", "Lift-off distance", Group.PERFORMANCE,
                            options=((1, "1 mm"), (2, "2 mm"))))
    ctrls += [
        Color("color", "Color", Group.LIGHTING, "Kept while the app runs", readable=False, persist=True),
        Range("brightness", "Brightness", Group.LIGHTING, min=0, max=100, step=1, unit="%"),
    ]
    return tuple(ctrls)


class UniversalMouse(UniversalDevice):
    kind = Kind.MOUSE
    keepalive_seconds = LIVE_COLOR_HOLD_S
    poll_seconds = 30.0
    leds = 1

    @classmethod
    def match_interface(cls, info):
        # the vendor collection declares the DPI command as an output report (usage page varies by mode)
        return super().match_interface(info) and info.descriptor.report_size("out", 0x32) is not None

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._dpi_raw: bytes | None = None  # bytes [2..61] of the last 33 02 reply, for read-modify-write
        self._sensor_raw: bytes | None = None
        self._live_color: tuple[int, int, int] | None = None

    # ----------------------------------------------------------------- reads
    def refresh(self) -> None:
        if self.wireless:
            link = self._read(LINK)
            self.set_online(bool(link and link[2] == 1))
            if not self.online:
                return
        if any(c.id == "battery" for c in self.controls):
            self._read_battery()
        self._read_dpi()
        if any(c.id == "lift_off" for c in self.controls):
            r = self._read(SENSOR_READ, 0)
            if r:
                self._sensor_raw = bytes(r[2:7])
                self.set_value("lift_off", 2 if r[5] == 0x02 else 1)
        r = self._read(BRIGHT_READ, 0)
        if r:
            self.set_value("brightness", round(r[2] * 100 / 255))

    def poll(self) -> None:
        if self.wireless:
            link = self._read(LINK)
            self.set_online(bool(link and link[2] == 1))
        if self.online and any(c.id == "battery" for c in self.controls):
            self._read_battery()

    def _read_dpi(self) -> None:
        r = self._read(DPI_READ, 0)
        if not r:
            return
        self._dpi_raw = bytes(r[2:62])
        polling_code, mask, active = r[2], r[3], r[4]
        if polling_code:
            self.set_value("polling", 8000 // polling_code)
        self._mask = mask
        code = r[5 + 5 * active] | (r[6 + 5 * active] << 8)
        self.set_value("dpi_stage", active + 1)
        self.set_value("dpi", (code + 1) * 50)

    # ---------------------------------------------------------------- writes
    def apply(self, control_id: str, value) -> None:
        if control_id in ("dpi", "dpi_stage", "polling"):
            self._write_dpi(control_id, value)
        elif control_id == "lift_off":
            if self._sensor_raw is None:
                raise ValueError("lift-off not read yet")
            raw = bytearray(self._sensor_raw)
            raw[3] = 0x02 if int(value) == 2 else 0x00
            self._write(SENSOR_WRITE, 0, 0, *raw)
            r = self._read(SENSOR_READ, 0)
            if r:
                self._sensor_raw = bytes(r[2:7])
                self.set_value("lift_off", 2 if r[5] == 0x02 else 1)
        elif control_id == "brightness":
            level = max(0, min(100, int(value)))
            self._write(BRIGHT_WRITE, 0, 0, level * 255 // 100)
            r = self._read(BRIGHT_READ, 0)
            self.set_value("brightness", round(r[2] * 100 / 255) if r else level)
        elif control_id == "color":
            self._live_color = tuple(int(c) for c in value)
            self._send_live_color()
            self.set_value("color", self._live_color)
        else:
            raise KeyError(control_id)

    def _write_dpi(self, control_id: str, value) -> None:
        if self._dpi_raw is None:
            self._read_dpi()
        if self._dpi_raw is None:
            raise ValueError("DPI settings not read yet")
        raw = bytearray(self._dpi_raw)  # [0] polling code, [1] stage mask, [2] active stage, stages from [3]
        if control_id == "polling":
            raw[0] = 8000 // int(value)
        elif control_id == "dpi_stage":
            stage = int(value) - 1
            if not raw[1] >> stage & 1:
                raise ValueError(f"DPI stage {value} is disabled on the mouse")
            raw[2] = stage
        else:
            code = max(200, min(self.dpi_max, int(value))) // 50 - 1
            off = 3 + 5 * raw[2]
            raw[off], raw[off + 1] = code & 0xFF, code >> 8
        self._write(DPI_WRITE, 0, 0, *raw[:58])
        self._read_dpi()  # confirm

    def _send_live_color(self) -> None:
        if self._live_color is None or self.online is False:
            return
        self._write(LIVE_HEADER, 1, 0)
        self._write(LIVE_COLOR, 0, 0, *(self._live_color * self.leds))

    def keepalive(self) -> None:
        self._send_live_color()

    # ---------------------------------------------------------------- events
    def handle_input(self, report: bytes) -> None:
        if len(report) < 3:
            return
        if report[0] == REPORT_EVENT and report[1] == EV_LINK and self.wireless:
            self.set_online(report[2] == 1)
        elif report[0] == REPORT_EVENT and report[1] == EV_DPI_STAGE and len(report) >= 5:
            self.set_value("dpi_stage", report[2] + 1)
            self.set_value("dpi", ((report[3] | report[4] << 8) + 1) * 50)
        elif report[0] == BATTERY[0] + 1 and report[1] == BATTERY[1] and len(report) >= 8:
            self._parse_battery(report)  # sent by the mouse on its own when it wakes up


# --------------------------------------------------------------------- models
# Interfaces come from NGENUITY Legacy's HID path table (MI_xx); firmware-update ids are excluded.
HASTE2_SOURCES = ("https://github.com/PMarinov1994/ngenuity-linux-cli", "https://github.com/rahmidaniel/Lumen",
                  "https://github.com/czQery/waybar-hyperx-haste2")


class Haste2Wireless(UniversalMouse):
    name = "HyperX Pulsefire Haste 2 Wireless"
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x03F0, 0x0F98, "2.4 GHz dongle"), (0x03F0, 0x0299, "2.4 GHz dongle, rev. 2"))
    interfaces = (2,)
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000), 26000, battery=True, lift_off=True)
    sources = HASTE2_SOURCES


class Haste2WirelessCable(Haste2Wireless):
    name = "HyperX Pulsefire Haste 2 Wireless (USB cable)"
    wireless = False
    ids = ((0x03F0, 0x0D97, "USB-C cable"), (0x03F0, 0x0F97, "USB-C cable, rev. 2"))


class Haste2(UniversalMouse):
    name = "HyperX Pulsefire Haste 2"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x0B97, "wired"),)
    interfaces = (2,)
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000, 2000, 4000, 8000), 26000, battery=False, lift_off=False)
    sources = ("https://github.com/fspy/haste2ctl", "https://github.com/devfreitas/omarchy-haste2")


class Haste2CoreWireless(UniversalMouse):
    name = "HyperX Pulsefire Haste 2 Core Wireless"
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x03F0, 0x0AB5, "2.4 GHz dongle"),)
    interfaces = (2,)
    dpi_max = 12000
    controls = universal_controls((125, 250, 500, 1000), 12000, battery=True, lift_off=False)
    sources = ("https://github.com/abhinavpathak9873/hyperx_open_lighting", "https://github.com/zee-w/open-ngenuity")


class SagaPro(UniversalMouse):
    name = "HyperX Pulsefire Saga Pro"
    support = Support.COMMUNITY
    wireless = True
    ids = ((0x03F0, 0x06BF, "2.4 GHz dongle"),)
    interfaces = (3,)
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000), 26000, battery=True, lift_off=True)
    sources = ("https://github.com/notwaterbtl/hyperx-saga-control",
               "https://github.com/ScottStaschke/PlasmaNGenuity-HyperX")


class SagaProCable(SagaPro):
    name = "HyperX Pulsefire Saga Pro (USB cable)"
    wireless = False
    ids = ((0x03F0, 0x04BF, "USB cable"),)
    interfaces = (2,)


class Haste2Pro(UniversalMouse):
    name = "HyperX Pulsefire Haste 2 Pro"
    support = Support.EXPERIMENTAL
    wireless = True
    ids = ((0x03F0, 0x0CBD, "2.4 GHz dongle"),)
    interfaces = (3,)
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000, 2000, 4000), 26000, battery=True, lift_off=True)
    sources = ("https://github.com/PMarinov1994/ngenuity-linux-cli",)


class Haste2ProCable(Haste2Pro):
    name = "HyperX Pulsefire Haste 2 Pro (USB cable)"
    wireless = False
    ids = ((0x03F0, 0x0ABD, "USB cable"),)
    interfaces = (2,)
    # 2000/4000 Hz are advertised for 2.4 GHz only
    controls = universal_controls((125, 250, 500, 1000), 26000, battery=True, lift_off=True)


class Haste2S(UniversalMouse):
    name = "HyperX Pulsefire Haste 2 S Wireless"
    support = Support.EXPERIMENTAL
    wireless = True
    ids = ((0x03F0, 0x0BB8, "2.4 GHz dongle"),)
    interfaces = (2,)
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000), 26000, battery=True, lift_off=True)
    sources = ("https://github.com/PMarinov1994/ngenuity-linux-cli",)


class Haste2SCable(Haste2S):
    name = "HyperX Pulsefire Haste 2 S Wireless (USB cable)"
    wireless = False
    ids = ((0x03F0, 0x0AB8, "USB cable"),)


class Haste2Mini(UniversalMouse):
    name = "HyperX Pulsefire Haste 2 Mini Wireless"
    support = Support.EXPERIMENTAL
    wireless = True
    ids = ((0x03F0, 0x0DA0, "2.4 GHz dongle"),)
    interfaces = (2,)
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000), 26000, battery=True, lift_off=False)
    sources = ("https://github.com/lbkeppler/lowerx",)


class Haste2MiniCable(Haste2Mini):
    name = "HyperX Pulsefire Haste 2 Mini Wireless (USB cable)"
    wireless = False
    ids = ((0x03F0, 0x0BA0, "USB cable"),)


class Saga(UniversalMouse):
    name = "HyperX Pulsefire Saga"
    support = Support.EXPERIMENTAL
    ids = ((0x03F0, 0x0EBE, "wired"),)
    interfaces = (2,)
    leds = 5
    dpi_max = 26000
    controls = universal_controls((125, 250, 500, 1000, 2000, 4000, 8000), 26000, battery=False, lift_off=True)
    sources = ("https://github.com/PMarinov1994/ngenuity-linux-cli",)


MODELS = (Haste2Wireless, Haste2WirelessCable, Haste2, Haste2CoreWireless, SagaPro, SagaProCable,
          Haste2Pro, Haste2ProCable, Haste2S, Haste2SCable, Haste2Mini, Haste2MiniCable, Saga)
