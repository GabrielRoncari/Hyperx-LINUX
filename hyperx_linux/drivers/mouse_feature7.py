"""Kingston-era wired mice with a 264-byte feature report 0x07: Pulsefire Surge, Core, FPS Pro, Raid.

Only direct colour is documented. It is volatile: the mouse returns to its onboard effect when the
host stops sending, so the colour is re-sent while the app runs. Profile commands (07 01, 07 03,
07 07) write onboard memory and one of them froze a Raid until replugged: never sent.
Full notes: docs/devices/mice.md
"""
from __future__ import annotations

from ..controls import Color, Group, Range
from .base import Driver, Kind, Support

REPORT = 0x07
SIZE = 264  # including the report id


def scale(rgb, brightness: int) -> tuple[int, int, int]:
    return tuple(c * brightness // 100 for c in rgb)


class Feature7Mouse(Driver):
    kind = Kind.MOUSE
    interfaces = (1,)
    keepalive_seconds = 0.25
    controls = (
        Color("color", "Color", Group.LIGHTING, "Kept while the app runs", readable=False, persist=True),
        Range("brightness", "Brightness", Group.LIGHTING, readable=False, persist=True,
              min=0, max=100, step=1, unit="%"),
    )

    @classmethod
    def match_interface(cls, info):
        return (super().match_interface(info) and info.descriptor.has_page(0xFF01)
                and info.descriptor.report_size("feature", REPORT) == SIZE - 1)

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._color: tuple[int, int, int] | None = None
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
        if self._color is not None:
            self.node.set_feature(self.frame(scale(self._color, self._brightness)))

    def frame(self, rgb) -> bytes:
        """Single-LED models (Core, FPS Pro): 07 0A R G B 00 00 00 A0."""
        p = bytearray(SIZE)
        p[0], p[1] = REPORT, 0x0A
        p[2:5] = bytes(rgb)
        p[8] = 0xA0
        return bytes(p)


class PulsefireCore(Feature7Mouse):
    name = "HyperX Pulsefire Core"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16DE, ""), (0x03F0, 0x0D8F, ""))
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/2369",)


class PulsefireFPSPro(Feature7Mouse):
    name = "HyperX Pulsefire FPS Pro"
    support = Support.EXPERIMENTAL
    ids = ((0x0951, 0x16D7, ""), (0x03F0, 0x0E8F, ""))
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB",)


class PulsefireRaid(Feature7Mouse):
    name = "HyperX Pulsefire Raid"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16E4, ""), (0x03F0, 0x0290, ""))
    keepalive_seconds = 0.5
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/1233", "https://github.com/kbpk/OpenHyperX")

    def frame(self, rgb):
        """07 0A <wheel RGB> <logo RGB> A0."""
        p = bytearray(SIZE)
        p[0], p[1] = REPORT, 0x0A
        p[2:5] = bytes(rgb)
        p[5:8] = bytes(rgb)
        p[8] = 0xA0
        return bytes(p)


class PulsefireSurge(Feature7Mouse):
    name = "HyperX Pulsefire Surge"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16D3, ""), (0x03F0, 0x0490, ""))
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB",)

    def frame(self, rgb):
        """07 14 00 A0, then planar R[32] G[32] B[32] for the ring, logo RGB at 0x6C."""
        p = bytearray(SIZE)
        p[0], p[1], p[3] = REPORT, 0x14, 0xA0
        r, g, b = rgb
        p[0x08:0x28] = bytes([r]) * 32
        p[0x28:0x48] = bytes([g]) * 32
        p[0x48:0x68] = bytes([b]) * 32
        p[0x6C:0x6F] = bytes(rgb)
        return bytes(p)


MODELS = (PulsefireCore, PulsefireFPSPro, PulsefireRaid, PulsefireSurge)
