"""Keyboard lighting effects, following NGENUITY's own (Legacy 2.38 NGenuity2.Effects.Keyboard and the
3.x light engine): same behaviour, timing ranges and key grid, our own code.

A renderer works on a layout of keys, each with an LED index, its column/row in NGENUITY's key grid
(what the effects move across) and a physical centre (used by the rainbow wave). `frame(t)` returns
one RGB per LED; reactive effects also need `press(key, t)` for every key that goes down.
Effects that NGENUITY lists but never implemented (rain, snow, heatmap, snake…) aren't here.
"""
from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass, field
from typing import Protocol

RGB = tuple


class Key(Protocol):
    led: int
    col: int
    row: int
    x: int
    y: int


@dataclass(frozen=True)
class Effect:
    id: str
    label: str
    min_ms: int  # NGENUITY's interval range for the effect: speed 100 -> min, speed 1 -> max
    max_ms: int
    colors: int = 1  # how many user colours it uses
    reactive: bool = False  # runs per key press
    directional: bool = False


EFFECTS = (
    Effect("static", "Static", 100, 100),
    Effect("breathing", "Breathing", 500, 4000),
    Effect("spectrum", "Spectrum cycle", 500, 4000, colors=0),
    Effect("wave", "Rainbow wave", 1000, 9000, colors=0, directional=True),
    Effect("alternating", "Alternating", 1200, 4800, colors=2),
    Effect("swipe", "Swipe", 500, 3000, colors=2, directional=True),
    Effect("confetti", "Confetti", 500, 3000, colors=0),
    Effect("sun", "Sun", 500, 1375, colors=0),
    Effect("twilight", "Twilight", 300, 1000),
    Effect("stacking", "Stacking", 1000, 2500, colors=0, directional=True),
    Effect("hourglass", "Hourglass", 100, 2000),
    Effect("reactive-fade", "Reactive: fade", 1000, 5000, reactive=True),
    Effect("reactive-explosion", "Reactive: explosion", 600, 10000, reactive=True),
    Effect("reactive-implosion", "Reactive: implosion", 250, 2500, reactive=True),
    Effect("reactive-flame", "Reactive: HyperX flame", 1000, 12000, reactive=True),
)
BY_ID = {e.id: e for e in EFFECTS}
DIRECTIONS = (("right", "Left to right"), ("left", "Right to left"))

# Sun: each key gets one of three warm palettes and loops through it (NGENUITY's theme colours)
SUN_THEMES = (
    ((0.0, (255, 178, 0)), (0.5, (255, 97, 0))),
    ((0.0, (255, 178, 0)), (0.25, (255, 97, 0)), (0.5, (255, 20, 0)), (0.75, (255, 183, 0))),
    ((0.0, (255, 130, 0)), (0.2, (255, 153, 0)), (0.4, (255, 161, 0)), (0.6, (255, 168, 0)), (0.8, (255, 97, 0))),
)
STACKING_COLORS = ((255, 0, 0), (255, 0, 255), (0, 255, 0), (255, 255, 0), (0, 0, 255))
# HyperX flame: cells lit at each stage, relative to the pressed key (column, row)
FLAME_STAGES = (
    ((-1, -1), (-2, -2)),
    ((0, -1), (1, -1), (1, -2), (2, -3)),
    ((0, -2), (1, -3), (1, -4)),
    ((0, -3), (-1, -3), (-2, -4)),
    ((0, -4),),
    ((-1, -5),),
    ((-1, -6),),
)
EXPLOSION_RING = 10.0  # grid units behind the front that stay lit
LOOP_ROUNDS = {"swipe": 2, "confetti": 4, "twilight": 8, "stacking": 10}  # NGENUITY's CycleCount
ONBOARD_TRIGGERS = {"reactive-fade": 4, "reactive-explosion": 5, "reactive-flame": 6}  # run by the keyboard


def interval_ms(effect: Effect, speed: int) -> float:
    """Speed 1..100 -> the effect's interval, NGENUITY's slowest .. fastest."""
    speed = max(1, min(100, int(speed)))
    return effect.max_ms - (speed - 1) / 99 * (effect.max_ms - effect.min_ms)


def hue(h: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 1.0, 1.0)
    return round(r * 255), round(g * 255), round(b * 255)


def dim(rgb, k: float) -> RGB:
    k = max(0.0, min(1.0, k))
    return tuple(round(c * k) for c in rgb)


def mix(a, b, f: float) -> RGB:
    f = max(0.0, min(1.0, f))
    return tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def random_color(rng: random.Random) -> RGB:
    return hue(rng.random())


def stops_color(stops, p: float) -> RGB:
    """Gradient through (position, colour) stops that wraps back to the first at 1."""
    for i, (pos, color) in enumerate(stops):
        end, after = (stops[i + 1] if i + 1 < len(stops) else (1.0, stops[0][1]))
        if pos <= p <= end:
            return mix(color, after, (p - pos) / (end - pos) if end > pos else 0)
    return stops[0][1]


@dataclass
class Settings:
    effect: str = "static"
    color: RGB = (255, 255, 255)
    color2: RGB = (0, 0, 255)
    speed: int = 50
    direction: str = "right"


@dataclass
class _Press:
    t0: float
    key: object
    lit: dict = field(default_factory=dict)  # flame: led -> time it lit up
    stage: int = 0


class Renderer:
    def __init__(self, keys, leds: int = 80, seed: int | None = None):
        self.keys = [k for k in keys if k.led < leds]
        self.leds = leds
        self.rng = random.Random(seed)
        self.settings = Settings()
        self.presses: list[_Press] = []
        self._grid: dict[tuple[int, int], list] = {}
        for k in self.keys:
            self._grid.setdefault((k.col, k.row), []).append(k)
        self.max_col = max((k.col for k in self.keys), default=0)
        self.max_row = max((k.row for k in self.keys), default=0)
        xs = [k.x for k in self.keys] or [0]
        self.x0, self.width = min(xs), (max(xs) - min(xs)) or 1
        self._state: dict = {}
        self._started: float | None = None
        self._loop: float | None = None  # set while rendering a loop for the keyboard

    # ------------------------------------------------------------ settings
    def configure(self, **changes) -> None:
        old = self.settings.effect
        for name, value in changes.items():
            if value is not None:
                setattr(self.settings, name, tuple(value) if name in ("color", "color2") else value)
        if self.settings.effect != old:
            self.reset()

    def reset(self) -> None:
        self._state, self.presses, self._started = {}, [], None

    @property
    def effect(self) -> Effect:
        return BY_ID.get(self.settings.effect, BY_ID["static"])

    def press(self, key, t: float) -> None:
        if self.effect.reactive:
            self.presses.append(_Press(t, key))
            del self.presses[:-64]

    # ------------------------------------------------------------- frames
    def frame(self, t: float) -> list[RGB]:
        if self._started is None:
            self._started = t
        out: list[RGB] = [(0, 0, 0)] * self.leds
        e, s = self.effect, self.settings
        period = interval_ms(e, s.speed) / 1000
        render = getattr(self, "_" + e.id.replace("-", "_"))
        render(out, t, t - self._started, period)
        return out

    def _set(self, out, key, rgb) -> None:
        out[key.led] = rgb

    def _static(self, out, t, age, period):
        for k in self.keys:
            out[k.led] = self.settings.color

    def _breathing(self, out, t, age, period):
        p = (age / period) % 1.0
        rgb = dim(self.settings.color, math.sin(min(p, 1 - p) * math.pi))
        for k in self.keys:
            out[k.led] = rgb

    def _spectrum(self, out, t, age, period):
        rgb = hue(age / period)
        for k in self.keys:
            out[k.led] = rgb

    def _wave(self, out, t, age, period):
        sign = 1 if self.settings.direction == "right" else -1
        for k in self.keys:
            out[k.led] = hue((k.x - self.x0) / self.width - sign * age / period)

    def _alternating(self, out, t, age, period):
        p = (age / period) % 1.0
        rgb = mix(self.settings.color, self.settings.color2, 1 - abs(1 - 2 * p))
        for k in self.keys:
            out[k.led] = rgb

    def _swipe(self, out, t, age, period):
        rounds, p = divmod(age / period, 1.0)
        a, b = self.settings.color, self.settings.color2
        if int(rounds) % 2:
            a, b = b, a
        width = self.max_col + 1
        front = int(p * width)
        for k in self.keys:
            col = k.col if self.settings.direction == "right" else self.max_col - k.col
            out[k.led] = b if col < front else a

    def _confetti(self, out, t, age, period):
        st = self._state
        rounds, p = divmod(age / period, 1.0)
        if st.get("round") != rounds:
            prev = st.get("to", {})
            st["from"] = prev or {k.led: random_color(self.rng) for k in self.keys}
            st.setdefault("first", st["from"])
            last_round = self._loop is not None and rounds >= round(self._loop / period) - 1
            st["to"] = st["first"] if last_round else {k.led: random_color(self.rng) for k in self.keys}
            st["round"] = rounds
        for k in self.keys:
            out[k.led] = mix(st["from"][k.led], st["to"][k.led], p)

    def _sun(self, out, t, age, period):
        themes = self._state.setdefault("themes", {k.led: self.rng.randrange(3) for k in self.keys})
        p = (age / period) % 1.0
        for k in self.keys:
            out[k.led] = stops_color(SUN_THEMES[themes[k.led]], p)

    def _twilight(self, out, t, age, period):
        """Stars: every round 1-3 keys fade in, stay two rounds, fade out."""
        st = self._state
        rounds, p = divmod(age / period, 1.0)
        stars = st.setdefault("stars", {})
        if st.get("round") != rounds:
            st["round"] = rounds
            if self._loop is not None and rounds >= round(self._loop / period) - 4:
                free = []  # let the last stars fade out so the loop ends where it started: dark
            else:
                free = [k for k in self.keys if k.led not in stars]
            for k in self.rng.sample(free, min(len(free), self.rng.randint(1, 3))):
                stars[k.led] = rounds
        for led, born in list(stars.items()):
            step = rounds - born
            level = p if step == 0 else (1 - p if step == 3 else (1.0 if step < 3 else 0.0))
            if step >= 4:
                del stars[led]
                continue
            out[led] = dim(self.settings.color, level)

    def _stacking(self, out, t, age, period):
        """Five column blocks slide in from one edge and pile up at the other, one per interval;
        then they leave in reverse order and the colours rotate."""
        sections = 5
        width = max(1, self.max_col // sections)
        move, p = divmod(age / period, 1.0)
        cycle, step = divmod(int(move), 2 * sections)
        placing = step < sections
        moving = step if placing else 2 * sections - 1 - step  # placement order: 0 rests farthest

        def rest_start(i):  # first column of block i once settled, counted from the entry edge
            return (sections - 1 - i) * width

        def block_width(i):
            return width if i else self.max_col + 1 - rest_start(0)
        travel = (rest_start(moving) + block_width(moving)) * (p if placing else 1 - p)
        for k in self.keys:
            col = k.col if self.settings.direction == "right" else self.max_col - k.col
            i = sections - 1 - min(col // width, sections - 1)  # block resting on this column
            if i < moving:
                out[k.led] = STACKING_COLORS[(i + cycle) % sections]
            elif rest_start(moving) - block_width(moving) + travel <= col < travel:
                out[k.led] = STACKING_COLORS[(moving + cycle) % sections]

    def _hourglass(self, out, t, age, period):
        """Grains fall from the top centre and pile up inside an hourglass outline, then it empties."""
        order = self._hourglass_order()
        if not order:
            return
        steps = int(age / period)
        filled = steps % (len(order) + 4)  # a short pause when full, then start again
        for k in order[:filled]:
            out[k.led] = self.settings.color
        if filled < len(order):  # the grain on its way down the centre column
            target = order[filled]
            frac = (age / period) % 1.0
            falling_row = int(frac * (target.row + 1))
            centre = round(self.max_col / 2)
            for k in self._grid.get((centre, falling_row), []):
                out[k.led] = self.settings.color

    def _hourglass_order(self) -> list:
        """Cells the sand fills, bottom row first and from the centre out, inside the outline."""
        if "order" not in self._state:
            centre, depth = self.max_col / 2, max(1, self.max_row)
            cells = sorted(self.keys, key=lambda k: (-k.row, abs(k.col - centre), k.col))
            self._state["order"] = [k for k in cells if abs(k.col - centre) <= 1 + centre * k.row / depth]
        return self._state["order"]

    # --------------------------------------------------- onboard playback
    def loop_seconds(self) -> float:
        e = self.effect
        period = interval_ms(e, self.settings.speed) / 1000
        if e.id == "static" or e.reactive:
            return 0.0
        if e.id == "hourglass":
            return (len(self._hourglass_order()) + 4) * period
        return LOOP_ROUNDS.get(e.id, 1) * period

    def render_loop(self, max_frames: int = 120, fps: int = 20) -> tuple[list[list[RGB]], float]:
        """One seamless loop for the keyboard's own player: the frames and the time per frame (ms).
        Reactive effects give a single dark frame (the keyboard runs the reaction itself)."""
        length = self.loop_seconds()
        self.reset()
        if not length:
            frame = [(0, 0, 0)] * self.leds if self.effect.reactive else self.frame(0.0)
            return [frame], 1000 / fps
        count = max(2, min(max_frames, round(length * fps)))
        self._loop = length
        try:
            frames = [self.frame(i * length / count) for i in range(count)]
        finally:
            self._loop = None
            self.reset()
        return frames, length * 1000 / count

    # ----------------------------------------------------------- reactive
    def _reactive(self, out, t, period, shade):
        alive = []
        for press in self.presses:
            if t - press.t0 <= period:
                alive.append(press)
                shade(out, press, (t - press.t0) / period)
        self.presses = alive

    def _reactive_fade(self, out, t, age, period):
        def shade(out, press, p):
            out[press.key.led] = dim(self.settings.color, (p if p <= 0.5 else 1 - p) / 0.5)
        self._reactive(out, t, period, shade)

    def _reactive_explosion(self, out, t, age, period):
        reach = math.hypot(self.max_col, self.max_row) + 11

        def shade(out, press, p):
            radius = p * reach
            for k in self.keys:
                behind = radius - math.hypot(k.col - press.key.col, k.row - press.key.row)
                if 0 <= behind <= EXPLOSION_RING:
                    level = (EXPLOSION_RING - behind) / EXPLOSION_RING
                    out[k.led] = max(out[k.led], dim(self.settings.color, level))
        self._reactive(out, t, period, shade)

    def _reactive_implosion(self, out, t, age, period):
        """A ring starts at the far edge and closes in on the key, one column every tenth of the
        interval; each key it passes then fades out over the interval."""
        step = period / 10
        alive = []
        for press in self.presses:
            r0 = max(press.key.col, self.max_col - press.key.col)
            a = t - press.t0
            if a > r0 * step + period:
                continue
            alive.append(press)
            for k in self.keys:
                d = math.hypot(k.col - press.key.col, k.row - press.key.row)
                if d > r0 + 0.5:
                    continue  # the ring starts at r0: keys beyond it are never reached
                hit = (r0 - d) * step
                if 0 <= a - max(hit, 0):
                    level = 1 - (a - max(hit, 0)) / period
                    if level > 0:
                        out[k.led] = max(out[k.led], dim(self.settings.color, level))
        self.presses = alive

    def _reactive_flame(self, out, t, age, period):
        """NGENUITY's Blaze: a flame climbs the rows above the key, every lit cell fades in half a cycle."""
        stage_time, fade = period / 50, period / 2

        def shade(out, press, p):
            elapsed = (p * period)
            if not press.lit:
                press.lit[press.key.led] = 0.0
            stages_due = int(elapsed / stage_time)
            height = press.key.row + 2  # lower keys give taller flames
            while press.stage < min(stages_due, len(FLAME_STAGES), height + 1):
                for dc, dr in FLAME_STAGES[press.stage]:
                    for k in self._grid.get((press.key.col + dc, press.key.row + dr), []):
                        press.lit.setdefault(k.led, press.stage * stage_time)
                press.stage += 1
            for led, lit_at in press.lit.items():
                level = 1 - (elapsed - lit_at) / fade
                if level > 0:
                    out[led] = max(out[led], dim(self.settings.color, level))
        self._reactive(out, t, period, shade)
