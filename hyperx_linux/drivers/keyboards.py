"""Keyboard lighting: one static colour for the whole keyboard (+ brightness).

Every family keeps a "direct" frame only while the host keeps sending it, so the colour is
re-sent while the app runs (and only once the user picked one). Nothing here touches the
onboard profiles: profile writes, keymaps, macros and the Sonix family (MKW100), which writes
flash on every change, are left out. Full notes: docs/devices/keyboards.md

Families:
  A  Alloy Elite RGB, Alloy FPS RGB: feature report 07, 264 bytes, one packet per channel.
  B  Alloy Origins, Elite 2, Origins 60/65: feature report without id (65 bytes) on interface 0
     (the vendor interface 3 gets no driver on Linux): 04 F2 init + N packets of 16 x "81 R G B".
     Note: this needs hidraw access to the keyboard's boot interface.
  C  Alloy Origins Core: 64-byte output report without id: A2 <chunk> 00 <len> + planar GRB buffer.
  D  Alloy Rise, Rise 75, Origins 2 65, Eve 1800: Universal protocol, 44 01 / 44 02 frames.
"""
from __future__ import annotations

import time

from ..controls import Color, Group, Range
from .base import Driver, Kind, Support
from .universal import UniversalDevice


def scale(rgb, brightness: int) -> tuple[int, int, int]:
    return tuple(c * brightness // 100 for c in rgb)


COLOR = Color("color", "Color", Group.LIGHTING, "Kept while the app runs", readable=False, persist=True)
SOFT_BRIGHTNESS = Range("brightness", "Brightness", Group.LIGHTING, readable=False, persist=True,
                        min=0, max=100, step=1, unit="%")
HW_BRIGHTNESS = Range("brightness", "Brightness", Group.LIGHTING, min=0, max=100, step=1, unit="%")


class KeyboardLighting(Driver):
    kind = Kind.KEYBOARD
    keepalive_seconds = 0.2
    hardware_brightness = False
    controls = (COLOR, SOFT_BRIGHTNESS)

    def __init__(self, node, notify):
        super().__init__(node, notify)
        self._color: tuple[int, int, int] | None = None
        self._brightness = 100

    def apply(self, control_id, value):
        if control_id == "color":
            self._color = tuple(int(c) for c in value)
            self.set_value("color", self._color)
            self.keepalive()
        elif control_id == "brightness":
            self._brightness = max(0, min(100, int(value)))
            if self.hardware_brightness:
                self.write_brightness(self._brightness)
            else:
                self.keepalive()
            self.set_value("brightness", self._brightness)
        else:
            raise KeyError(control_id)

    def keepalive(self):
        if self._color is not None:
            rgb = self._color if self.hardware_brightness else scale(self._color, self._brightness)
            self.send_frame(rgb)

    def send_frame(self, rgb) -> None:
        raise NotImplementedError

    def write_brightness(self, percent: int) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------- family A
ELITE_KEY_OFFSETS = (
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x20, 0x21, 0x22, 0x23, 0x24, 0x26, 0x27, 0x28, 0x29,
    0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x37, 0x38, 0x39, 0x3A, 0x3B,
    0x3C, 0x3E, 0x3F, 0x41, 0x44, 0x45, 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0x51, 0x54,
    0x55, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5E, 0x5F, 0x61, 0x64, 0x65, 0x68, 0x69, 0x6A, 0x6B, 0x6C,
    0x6E, 0x6F, 0x74, 0x75, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x81, 0x84, 0x85, 0x88,
    0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F, 0x91, 0x94, 0x95,
)
# channel 04 (light bar + media keys): (R, G, B) offsets per LED
ELITE_EXTENDED = (
    (0x08, 0x29, 0x39), (0x48, 0x28, 0x38), (0x88, 0x78, 0x68), (0x09, 0x19, 0x3A), (0x89, 0x79, 0x69),
    (0x0A, 0x1A, 0x2A), (0x8A, 0x7A, 0x6A), (0x0B, 0x1B, 0x2B), (0x8B, 0x7B, 0x6B), (0x0C, 0x1C, 0x2C),
    (0x8C, 0x7C, 0x6C), (0x0D, 0x1D, 0x2D), (0x8D, 0x7D, 0x6D), (0x0E, 0x1E, 0x2E), (0x8F, 0x6E, 0x5E),
    (0x8E, 0x7E, 0x5D), (0x0F, 0x1F, 0x2F), (0x4F, 0x6F, 0x5F), (0x92, 0x82, 0x72), (0x13, 0x23, 0x33),
    (0x93, 0x83, 0x73), (0x12, 0x22, 0x32),
)


class AlloyEliteRGB(KeyboardLighting):
    name = "HyperX Alloy Elite RGB"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16BE, ""),)
    interfaces = (2,)
    keepalive_seconds = 0.05  # falls back to the profile quickly; OpenRGB re-sends after 50 ms
    extended_channel = True
    packet_gap = 0.005
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB", "https://gitlab.com/OpenRGBDevelopers/OpenRGB-Wiki")

    @classmethod
    def match_interface(cls, info):
        return (super().match_interface(info) and info.descriptor.has_page(0xFF01)
                and info.descriptor.report_size("feature", 0x07) == 263)

    def send_frame(self, rgb):
        for channel, value in zip((1, 2, 3), rgb):
            p = bytearray(264)
            p[0:4] = bytes([0x07, 0x16, channel, 0xA0])
            for off in ELITE_KEY_OFFSETS:
                p[off] = value
            self.node.set_feature(bytes(p))
            time.sleep(self.packet_gap)
        if self.extended_channel:
            p = bytearray(264)
            p[0:4] = bytes([0x07, 0x16, 0x04, 0xA0])
            for offsets in ELITE_EXTENDED:
                for off, value in zip(offsets, rgb):
                    p[off] = value
            self.node.set_feature(bytes(p))


class AlloyFPSRGB(AlloyEliteRGB):
    name = "HyperX Alloy FPS RGB"
    ids = ((0x0951, 0x16DC, ""),)
    extended_channel = False
    packet_gap = 0.01
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB", "https://github.com/Grabulosaure/hyperx_alloy_fps_rgb")


# ---------------------------------------------------------------------- family B
class F2Keyboard(KeyboardLighting):
    interfaces = (0,)  # see the module docstring
    keepalive_seconds = 0.1  # one source says the Origins forgets the frame in under a second
    packets = 9
    empty_slots: frozenset[int] = frozenset()

    def send_frame(self, rgb):
        init = bytearray(65)
        init[1:3] = b"\x04\xF2"
        init[9] = self.packets
        self.node.set_feature(bytes(init))
        for k in range(self.packets):
            p = bytearray(65)
            for i in range(16):
                slot = k * 16 + i
                p[1 + 4 * i] = 0x81
                if slot not in self.empty_slots:
                    p[2 + 4 * i:5 + 4 * i] = bytes(rgb)
            self.node.set_feature(bytes(p))


class AlloyOrigins(F2Keyboard):
    name = "HyperX Alloy Origins"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16E5, ""), (0x03F0, 0x0591, ""))
    empty_slots = frozenset({23, 29, 41, 47, 59, 70, 71, 87, 88, 93, 99, 100, 102, 108, 113, 114, 120, 123, 124}
                            | set(range(126, 144)))
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB", "https://github.com/Shehtman/hyperx-studio")


class AlloyElite2(F2Keyboard):
    name = "HyperX Alloy Elite 2"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x1711, ""), (0x03F0, 0x058F, ""))
    empty_slots = frozenset({23, 29, 41, 47, 70, 71, 76, 77, 87, 88, 93, 99, 100, 102, 108, 113})
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/427",)


class AlloyOrigins60(F2Keyboard):
    name = "HyperX Alloy Origins 60"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x1734, ""), (0x03F0, 0x0C8E, ""))
    packets = 5
    empty_slots = frozenset({0, 14, 42, 45, 56, 67, 68, 69} | set(range(71, 80)))
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/1617", "https://github.com/EriksRemess/hyperrust")


class AlloyOrigins65(F2Keyboard):
    name = "HyperX Alloy Origins 65"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x038F, ""),)
    packets = 5
    empty_slots = frozenset({0, 14, 42, 45, 56, 65, 66, 67} | set(range(77, 80)))
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/1739",)


# ---------------------------------------------------------------------- family C
class AlloyOriginsCore(KeyboardLighting):
    name = "HyperX Alloy Origins Core"
    support = Support.COMMUNITY
    ids = ((0x0951, 0x16E6, ""), (0x03F0, 0x098F, ""))
    interfaces = (2,)
    keepalive_seconds = 0.1
    hardware_brightness = True
    controls = (COLOR, HW_BRIGHTNESS)
    sources = ("https://github.com/identityapproved/hyperx-origins-core-tkl-rgb", "https://gitlab.com/CalcProgrammer1/OpenRGB")

    @classmethod
    def match_interface(cls, info):
        return (super().match_interface(info) and info.descriptor.has_page(0xFF13)
                and info.descriptor.report_size("out", 0) == 64)

    def _cmd(self, *data: int, reply: bool = False) -> bytes | None:
        pkt = b"\x00" + bytes(data).ljust(64, b"\0")
        if not reply:
            self.node.send(pkt, gap=0.002)
            return None
        return self.node.request(lambda: self.node.write(pkt), lambda r: len(r) > 4 and r[0] == data[0])

    def refresh(self):
        r = self._cmd(0x27, reply=True)
        if r:
            self._brightness = round(r[4] * 100 / 255)
            self.set_value("brightness", self._brightness)

    def write_brightness(self, percent):
        self._cmd(0xA7, 0x00, 0x00, 0x01, percent * 255 // 100)

    def send_frame(self, rgb):
        r, g, b = rgb
        buf = bytearray(380)
        for idx in range(94):  # planar GRB, two halves of the matrix
            pos = (idx // 12) * 48 + ((idx // 6) & 1) * 8 + idx % 6
            buf[pos], buf[pos + 16], buf[pos + 32] = g, r, b
        for chunk in range(7):
            data = buf[chunk * 60:(chunk + 1) * 60]
            self._cmd(0xA2, chunk, 0x00, len(data), *data)


# ---------------------------------------------------------------------- family D
class UniversalKeyboard(UniversalDevice, KeyboardLighting):
    hardware_brightness = True
    controls = (COLOR, HW_BRIGHTNESS)
    blocks = 6
    header_blocks: int | None = None  # what goes in 44 01 (Eve 1800 sends 4 with a single block)
    leds_per_block = 20

    @classmethod
    def match_interface(cls, info):
        return super().match_interface(info) and info.descriptor.report_size("out", 0x44) is not None

    def refresh(self):
        r = self._read((0x40, 0x02))
        if r:
            self._brightness = round(r[2] * 100 / 255)
            self.set_value("brightness", self._brightness)

    def write_brightness(self, percent):
        # not every model acknowledges it (Eve 1800), so don't wait for the ACK
        self.node.send(self._packet((0x40, 0x01), 0, 0, percent * 255 // 100))

    def send_frame(self, rgb):
        header = self.header_blocks if self.header_blocks is not None else self.blocks
        self.node.send(self._packet((0x44, 0x01), header, 0), gap=0.002)
        for i in range(self.blocks):
            self.node.send(self._packet((0x44, 0x02), i, 0, *(tuple(rgb) * self.leds_per_block)), gap=0.002)


class AlloyRise75(UniversalKeyboard):
    name = "HyperX Alloy Rise 75"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x02A1, ""),)
    interfaces = (2,)
    blocks = 6
    sources = ("https://github.com/abhinavpathak9873/hyperx_open_lighting",)


class AlloyRise(UniversalKeyboard):
    name = "HyperX Alloy Rise"
    support = Support.EXPERIMENTAL  # only NGENUITY captures; same frames as the Rise 75
    ids = ((0x03F0, 0x0FA0, ""),)
    interfaces = (2,)
    blocks = 7
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/4480",)


class Origins2_65(UniversalKeyboard):
    name = "HyperX Origins 2 65"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x0CC2, ""),)
    interfaces = (3,)
    blocks = 4
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/3239",
               "https://github.com/ScottStaschke/PlasmaNGenuity-HyperX")


class Eve1800(UniversalKeyboard):
    name = "HyperX Eve 1800"
    support = Support.COMMUNITY
    ids = ((0x03F0, 0x08C2, ""),)
    interfaces = (2,)
    blocks = 1
    header_blocks = 4
    leds_per_block = 10
    sources = ("https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/3321",)


MODELS = (AlloyEliteRGB, AlloyFPSRGB, AlloyOrigins, AlloyElite2, AlloyOrigins60, AlloyOrigins65,
          AlloyOriginsCore, AlloyRise75, AlloyRise, Origins2_65, Eve1800)
