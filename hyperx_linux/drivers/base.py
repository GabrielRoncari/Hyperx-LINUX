"""Driver contract. One subclass per device family; see docs/CONTRIBUTING.md."""
from __future__ import annotations

from enum import Enum
from typing import Callable, ClassVar

from ..controls import Control
from ..hid import Node, NodeInfo


class Kind(str, Enum):
    HEADSET = "headset"
    MOUSE = "mouse"
    KEYBOARD = "keyboard"
    MICROPHONE = "microphone"
    OTHER = "other"


class Support(str, Enum):
    VERIFIED = "verified"  # tested on real hardware by a maintainer
    COMMUNITY = "community"  # protocol confirmed on hardware by another project/user
    EXPERIMENTAL = "experimental"  # derived from vendor software or unconfirmed; writes need opt-in


class Driver:
    name: ClassVar[str]
    kind: ClassVar[Kind]
    support: ClassVar[Support]
    ids: ClassVar[tuple[tuple[int, int, str], ...]]  # (vid, pid, variant)
    interfaces: ClassVar[tuple[int, ...] | None] = None  # USB interfaces to open; None = any (udev too)
    controls: ClassVar[tuple[Control, ...]] = ()
    sources: ClassVar[tuple[str, ...]] = ()  # where the protocol comes from
    poll_seconds: ClassVar[float] = 60.0  # light refresh (battery) when nothing else happens
    wireless: ClassVar[bool] = False  # has a separate "device online" state (dongle without headset)

    def __init__(self, node: Node, notify: Callable[[str, object], None]):
        self.node = node
        self._notify = notify
        self.values: dict[str, object] = {}
        self.online: bool | None = None if self.wireless else True

    # -------------------------------------------------------------- matching
    @classmethod
    def driver_id(cls) -> str:
        return cls.__name__

    @classmethod
    def match_ids(cls, info: NodeInfo) -> bool:
        return any(info.vid == vid and info.pid == pid for vid, pid, _ in cls.ids)

    @classmethod
    def match(cls, info: NodeInfo) -> bool:
        """Right device and right interface. Override match_interface for the latter."""
        return cls.match_ids(info) and cls.match_interface(info)

    @classmethod
    def match_interface(cls, info: NodeInfo) -> bool:
        return cls.interfaces is None or info.interface in cls.interfaces

    @classmethod
    def variant(cls, info: NodeInfo) -> str:
        return next((v for vid, pid, v in cls.ids if (vid, pid) == (info.vid, info.pid)), "")

    def control(self, control_id: str) -> Control:
        return next(c for c in self.controls if c.id == control_id)

    # ------------------------------------------------------------ lifecycle
    def set_value(self, control_id: str, value: object) -> None:
        """Record a value and tell the app (from any thread)."""
        if self.values.get(control_id, object()) != value:
            self.values[control_id] = value
            self._notify(control_id, value)

    def set_online(self, online: bool) -> None:
        if self.online != online:
            self.online = online
            self._notify("online", online)

    def refresh(self) -> None:
        """Read every readable control. Called on connect and when asked."""

    def poll(self) -> None:
        """Cheap periodic refresh; default: full refresh."""
        self.refresh()

    def apply(self, control_id: str, value: object) -> None:
        """Write one control to the device."""
        raise NotImplementedError(control_id)

    def has(self, control_id: str) -> bool:
        return any(c.id == control_id for c in self.controls)

    def handle_input(self, report: bytes) -> None:
        """Unsolicited input reports (events, buttons)."""

    def keepalive(self) -> None:
        """Called every keepalive_seconds when set (devices that forget state)."""

    keepalive_seconds: ClassVar[float | None] = None
