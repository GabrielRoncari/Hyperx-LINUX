"""Microphones and mouse pads with HID-controllable lighting.

Only live ("direct") lighting is implemented; saving a colour to the device writes flash and is
left out. Gain, monitoring and polar pattern are USB Audio Class controls (use the sound settings),
not HID. QuadCast S and DuoCast have no hidraw node for their LEDs on Linux (interface without an
IN endpoint) and would need usbfs, which is not implemented yet. Full notes: docs/devices/other.md
"""
from __future__ import annotations

import time

from ..controls import Group, Range
from .base import Driver, Kind, Support
from .keyboards import COLOR, HW_BRIGHTNESS, SOFT_BRIGHTNESS, scale
from .universal import UniversalDevice


class QuadCast2S(UniversalDevice):
    """Controller 03F0:02B5, interface 1. 108 LEDs in 6 blocks of 20."""

    name = "HyperX QuadCast 2 S"
    kind = Kind.MICROPHONE
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x02B5, "LED controller"),)
    interfaces = (1,)
    keepalive_seconds = 0.2  # falls back to the stored frame/rainbow when frames stop
    controls = (COLOR, HW_BRIGHTNESS)
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/5113", "https://github.com/MuffinMario/quadcast2Srgb",
               "https://github.com/terracatta/omarchy-limelight")

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0x44) is not None

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._color = None

    def refresh(self):
        r = self._read((0x40, 0x02))
        if r:
            self.set_value("brightness", round(r[2] * 100 / 255))

    def apply(self, control_id, value):
        if control_id == "color":
            self._color = tuple(int(c) for c in value)
            self.set_value("color", self._color)
            self.keepalive()
        elif control_id == "brightness":
            level = max(0, min(100, int(value)))
            self._write((0x40, 0x01), 0, 0, level * 255 // 100)  # profile 0 = live
            self.set_value("brightness", level)
        else:
            raise KeyError(control_id)

    def keepalive(self):
        if self._color is None:
            return
        self.node.send(self._packet((0x44, 0x01), 6, 0), gap=0.002)
        for i in range(6):
            self.node.send(self._packet((0x44, 0x02), i, 0, *(self._color * 20)), gap=0.002)


class QuadCast2(Driver):
    """Red LED of the QuadCast 2 (controller 03F0:09AF, interface 0): brightness only."""

    name = "HyperX QuadCast 2"
    kind = Kind.MICROPHONE
    support = Support.EXPERIMENTAL  # bytes confirmed with libusb/Windows; the hidraw path is untested
    ids = ((0x03F0, 0x09AF, "LED controller"),)
    interfaces = (0,)
    keepalive_seconds = 0.5  # back to 100 % about 1 s after the host stops
    controls = (Range("brightness", "LED brightness", Group.LIGHTING, readable=False, persist=True,
                      min=0, max=100, step=1, unit="%"),)
    sources = ("https://github.com/colaquecez/quadcast-control", "https://github.com/Ors1mer/QuadcastRGB/issues/21")

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._level: int | None = None

    def apply(self, control_id, value):
        if control_id != "brightness":
            raise KeyError(control_id)
        self._level = max(0, min(100, int(value))) * 0xF2 // 100  # 0xF2 = NGENUITY's maximum
        self.set_value("brightness", int(value))
        self.keepalive()

    def keepalive(self):
        if self._level is None:
            return
        x = self._level
        self.node.set_feature(bytes([0x00, 0x81, x, 0, 0, 0x81, x, 0, 0]).ljust(65, b"\0"))
        time.sleep(0.02)
        self.node.set_feature(bytes([0x00, 0x04, x, 0, 0, 0, 0, 0, 0, 0x01]).ljust(65, b"\0"))  # heartbeat


class FuryUltra(Driver):
    """Fury Ultra mouse pad (0951:1705, interface 0): 20 LEDs, legacy 04 F2 / 81 RGB frames."""

    name = "HyperX Fury Ultra"
    kind = Kind.OTHER
    support = Support.COMMUNITY
    ids = ((0x0951, 0x1705, ""), (0x03F0, 0x0493, ""))
    interfaces = (0,)
    keepalive_seconds = 0.2
    controls = (COLOR, SOFT_BRIGHTNESS)
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB",)

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._color = None
        self._brightness = 100

    def apply(self, control_id, value):
        if control_id == "color":
            self._color = tuple(int(c) for c in value)
        elif control_id == "brightness":
            self._brightness = max(0, min(100, int(value)))
        else:
            raise KeyError(control_id)
        self.set_value(control_id, value)
        self.keepalive()

    def keepalive(self):
        if self._color is None:
            return
        rgb = scale(self._color, self._brightness)
        self.node.set_feature(bytes([0x00, 0x04, 0xF2, 0, 0, 0, 0, 0, 0, 0x02]).ljust(65, b"\0"))
        for packet in range(2):
            p = bytearray(65)
            for i in range(16):
                p[1 + 4 * i] = 0x81
                if packet * 16 + i < 20:
                    p[2 + 4 * i:5 + 4 * i] = bytes(rgb)
            self.node.set_feature(bytes(p))


MODELS = (QuadCast2S, QuadCast2, FuryUltra)
