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
    BUTTONS = "buttons"  # actions the app performs for the device's buttons
    ENGINE = "engine"  # audio processed on the computer (PipeWire)
    VOICE = "voice"  # microphone processed on the computer
    LIGHTING = "lighting"
    KEYS = "keys"
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
    experimental: bool = False  # not confirmed on this model: writes need "allow experimental drivers"

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


@dataclass(frozen=True)
class Action(Control):
    """A button: apply(id, None) runs it. `confirm` asks first (destructive actions). While it runs
    the driver may report progress as the control's value (0-100), and None when done."""
    button: str = "Run"
    confirm: str = ""
    readable: bool = False


# What a keyboard looks like, per layout: ((value of the "layout" control, ((key id, x, y, w, h), …)), …),
# x/y the centre of the key cap in any unit. Keys drawn but not listed in a control are shown greyed out.
KeyGeometry = tuple[tuple[str, tuple[tuple[str, int, int, int, int], ...]], ...]


@dataclass(frozen=True)
class KeyRemap(Control):
    """Value: {key id: action text} (keymap.parse_action); keys are (id, label) pairs. With `layouts`
    the app draws the keyboard and keys are picked on it."""
    keys: tuple[tuple[str, str], ...] = ()
    layouts: KeyGeometry = ()
    readable: bool = False
    persist: bool = True


@dataclass(frozen=True)
class ButtonMap(Control):
    """What the app does when a button of the device is pressed. Value: {button id: action}, where an
    action is keymap.parse_action text, "macro:NAME", "run:COMMAND", one of `device_actions`, or
    "disabled"; buttons left out keep their own function. `buttons`: (id, label) pairs."""
    buttons: tuple[tuple[str, str], ...] = ()
    device_actions: tuple[tuple[str, str], ...] = ()
    readable: bool = False
    persist: bool = True


@dataclass(frozen=True)
class KeyColors(Control):
    """Per-key colours on top of the lighting effect. Value: {key id: "#rrggbb"}; keys without one
    follow the effect. `layouts` as for KeyRemap; every key drawn can be painted."""
    layouts: KeyGeometry = ()
    readable: bool = False
    persist: bool = True


@dataclass(frozen=True)
class MacroList(Control):
    """Value: {name: {"steps": keymap macro text, "mode": one of MACRO_MODES}}."""
    readable: bool = False
    persist: bool = True


@dataclass(frozen=True)
class Recorder(Control):
    """Records from the device: apply(id, True) starts, apply(id, False) stops. The value is "" while
    recording and the result (macro text, keymap syntax) once stopped."""
    readable: bool = False


MACRO_MODES = (("once", "Once"), ("toggle", "Repeat until pressed again"), ("hold", "Repeat while held"))


@dataclass
class BatteryValue:
    level: int | None  # percent
    charging: bool | None = None
    full: bool = False
    voltage_mv: int | None = None
