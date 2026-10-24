"""What a device exposes, declared as data so the GUI and the CLI can be generated.

A driver lists its controls; values travel as plain Python objects:
    Toggle -> bool, Range -> int/float, Choice -> option value, Color -> (r, g, b),
    Equalizer -> list[float] (dB per band), Battery -> BatteryValue, Info -> str
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Group(str, Enum):
    BATTERY = "battery"
    MICROPHONE = "microphone"
    AUDIO = "audio"
    LIGHTING = "lighting"
    PERFORMANCE = "performance"
    POWER = "power"
    SYSTEM = "system"
    INFO = "info"


@dataclass(frozen=True)
class Control:
    id: str
    title: str
    group: Group
    subtitle: str = ""
    readable: bool = True  # False: the device can't report it, the app shows the last value it set
    writable: bool = True  # False: shown but not changeable (e.g. a mechanical mute switch)
    persist: bool = False  # re-apply the saved value whenever the device (re)connects
    cli: str = ""  # CLI name; defaults to id with "-" instead of "_"

    @property
    def cli_name(self) -> str:
        return self.cli or self.id.replace("_", "-")


@dataclass(frozen=True)
class Toggle(Control):
    pass


@dataclass(frozen=True)
class Range(Control):
    min: float = 0
    max: float = 100
    step: float = 1
    unit: str = ""


@dataclass(frozen=True)
class Choice(Control):
    options: tuple[tuple[object, str], ...] = ()  # (value, label)
    unit: str = ""  # "s": values are seconds, shown as minutes when not in options

    def label(self, value) -> str:
        known = next((lbl for v, lbl in self.options if v == value), None)
        if known is not None:
            return known
        if self.unit == "s" and isinstance(value, int):
            return f"{value // 60} min" if value % 60 == 0 else f"{value} s"
        return str(value)


@dataclass(frozen=True)
class Color(Control):
    pass


@dataclass(frozen=True)
class Equalizer(Control):
    bands_hz: tuple[int, ...] = ()
    min_db: float = -12.0
    max_db: float = 12.0
    step_db: float = 0.5
    presets: tuple[tuple[str, tuple[float, ...]], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Battery(Control):
    pass


@dataclass(frozen=True)
class Info(Control):
    pass


@dataclass
class BatteryValue:
    level: int | None  # percent
    charging: bool | None = None
    full: bool = False
    voltage_mv: int | None = None
