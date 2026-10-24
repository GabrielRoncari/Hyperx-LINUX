"""Driver registry. Add new driver modules to the import list below."""
from __future__ import annotations

from ..catalog import DETECTION_ONLY, is_firmware_mode, product
from ..hid import NodeInfo
from . import (cloud3s, headset_21, headset_66, headset_ffbb, headset_misc, keyboards, lighting, mouse_dseries,
               mouse_feature7, mouse_universal)
from .base import Driver, Kind, Support

DRIVERS: tuple[type[Driver], ...] = (
    *cloud3s.MODELS, *headset_ffbb.MODELS, *headset_66.MODELS, *headset_21.MODELS, *headset_misc.MODELS,
    *mouse_universal.MODELS, *mouse_dseries.MODELS, *mouse_feature7.MODELS,
    *keyboards.MODELS, *lighting.MODELS,
)

DETECTION_NOTE = "Charging/firmware interface: use the receiver"
FIRMWARE_NOTE = "Firmware update mode: not opened"


def passive_note(info: NodeInfo) -> str | None:
    """Why a HyperX interface is listed without controls, if it is a known non-control interface."""
    if is_firmware_mode(info.vid, info.pid):
        return FIRMWARE_NOTE
    if (info.vid, info.pid) in DETECTION_ONLY:
        return DETECTION_NOTE
    return None


def display_name(info: NodeInfo) -> str:
    known = product(info.vid, info.pid)
    if known:
        suffix = " (USB-C)" if (info.vid, info.pid) in DETECTION_ONLY else ""
        return known[0] + suffix
    name = info.name.removeprefix("HP, Inc ").removeprefix("Kingston ").strip()
    return name or f"HyperX device {info.usb_id}"


def find_driver(info: NodeInfo) -> type[Driver] | None:
    if is_firmware_mode(info.vid, info.pid):
        return None  # bootloader / DFU: never opened
    return next((d for d in DRIVERS if d.match(info)), None)


def known_ids() -> list[tuple[int, int, str, type[Driver]]]:
    return [(vid, pid, variant, d) for d in DRIVERS for vid, pid, variant in d.ids]


__all__ = ["DRIVERS", "Driver", "Kind", "Support", "display_name", "find_driver", "known_ids", "passive_note"]
