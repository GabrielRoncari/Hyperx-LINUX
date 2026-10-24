"""The audio engine: virtual 7.1 spatial audio, a software equalizer and voice processing for the
microphone, made by PipeWire on this computer. It is the Linux counterpart of NGENUITY's Audio
Engine, which on Windows is HEAR360 SONAMI running on the PC (nothing spatial runs on the headset);
DTS Headphone:X is licensed per product and can't be reproduced. See docs/audio.md.

Each part is a filter graph run by its own `pipewire -c <file>` process, detached so a crash of the
app doesn't take the sound with it; a pid file next to the config tells us which process is ours.
Both attach to one headset by its USB ids and become the default output/microphone while on. In the
Flatpak these processes run on the host (flatpak-spawn): the runtime has no filter-chain module.

Spatial audio: a 7.1 virtual sink; each channel goes through the MIT KEMAR head-related impulse
responses of its virtual speaker (left and right ear), the ears are mixed, then optionally a room
ambience (our own synthetic one) and the equalizer. Speaker angles follow NGENUITY's drawing: front
at ±(15+60·width)°, rear at ±(165−60·width)°, sides at ±90°.
"""
from __future__ import annotations

import glob
import json
import math
import os
import random
import shutil
import signal
import subprocess
import time
import wave
from dataclasses import dataclass, field
from typing import Callable

from . import controls as C
from .drivers.cloud3s import EQ_PRESETS
from .i18n import _

FLATPAK_ID = os.environ.get("FLATPAK_ID") if os.path.exists("/.flatpak-info") else None
PACKAGED_HRIRS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "hrtf-mit-kemar")
_RUN = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/hyperx-linux-{os.getuid()}"
# both visible to the host under the same path, also from the Flatpak
RUNTIME_DIR = os.path.join(_RUN, "app", FLATPAK_ID, "hyperx-linux") if FLATPAK_ID else os.path.join(_RUN, "hyperx-linux")
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "hyperx-linux")
HRIR_DIR = os.path.join(CACHE_DIR, "hrtf-mit-kemar") if FLATPAK_ID else PACKAGED_HRIRS  # /app isn't on the host

CHANNELS = ("FL", "FR", "FC", "LFE", "RL", "RR", "SL", "SR")
CHANNEL_GAIN = 0.5  # 8 virtual speakers into two ears; one front speaker comes out at unity (−0.5 dB measured)
# NGENUITY's output equalizer: low shelf, peaking bands, high shelf, ±8 dB (same bands as the Cloud III S)
EQ_BANDS = ((32, "bq_lowshelf"), (64, "bq_peaking"), (125, "bq_peaking"), (250, "bq_peaking"),
            (500, "bq_peaking"), (1000, "bq_peaking"), (2000, "bq_peaking"), (4000, "bq_peaking"),
            (8000, "bq_peaking"), (16000, "bq_highshelf"))
EQ_LIMIT_DB = 8.0
EXPERIENCES = (("performance", "Performance"), ("balanced", "Balanced"), ("immersion", "Immersion"))
ROOMS = {"balanced": (0.35, 0.18), "immersion": (0.8, 0.3)}  # (decay to −60 dB in s, wet level)

# NGENUITY's microphone presets (HXN AudioEngineInputFeatureController): (biquad, Hz, Q, dB)
MIC_PRESETS = {
    "high": (("bq_lowshelf", 300, 0.5, 5.0), ("bq_highshelf", 1500, 0.5, 5.0)),
    "mid": (("bq_peaking", 140, 0.5, 4.0), ("bq_peaking", 500, 0.5, 4.0), ("bq_peaking", 1800, 0.5, 4.0)),
    "low": (("bq_lowshelf", 300, 0.5, 5.0), ("bq_highshelf", 1500, 0.5, -5.0)),
}
HIGHPASS_HZ = 80.0
NODE_WAIT = 5.0  # seconds for a new node (ours, or the headset's after plugging) to show up


@dataclass
class OutputSettings:
    spatial: bool = False
    width: float = 0.5  # 0..1, NGENUITY's speaker width (front and rear together)
    experience: str = "balanced"
    eq: tuple = field(default_factory=lambda: (0.0,) * len(EQ_BANDS))  # dB per band

    @property
    def needed(self) -> bool:
        return self.spatial or any(abs(g) > 0.05 for g in self.eq)


@dataclass
class MicSettings:
    noise: str = "off"  # "off", "rnnoise" or "webrtc"
    highpass: bool = False
    preset: str = "off"  # "off" or a MIC_PRESETS key

    @property
    def needed(self) -> bool:
        return self.noise != "off" or self.highpass or self.preset in MIC_PRESETS


# ---------------------------------------------------------- the host system
def host(argv: list[str]) -> list[str]:
    """A command line that runs on the host, also from the Flatpak."""
    return ["flatpak-spawn", "--host", *argv] if FLATPAK_ID else argv


def _run(argv: list[str], timeout: float = 10) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(host(argv), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def _first_existing(patterns: list[str]) -> str | None:
    """The first path matching one of the shell patterns, on the host."""
    if not FLATPAK_ID:
        return next((p for pattern in patterns for p in sorted(glob.glob(pattern))), None)
    script = 'for p in "$@"; do for f in $p; do [ -e "$f" ] && { echo "$f"; exit 0; }; done; done; exit 1'
    r = _run(["sh", "-c", script, "sh", *patterns])
    return (r.stdout.strip() or None) if r and r.returncode == 0 else None


def _lib_patterns(name: str, file: str) -> list[str]:
    prefixes = ("/usr/lib", "/usr/lib64", "/usr/local/lib", "/usr/local/lib64", "/run/current-system/sw/lib")
    return [f"{p}{sub}/{name}/{file}" for p in prefixes for sub in ("", "/*")] + [f"{os.path.expanduser('~')}/.{name}/{file}"]


def find_rnnoise() -> str | None:
    """The RNNoise LADSPA plugin (github.com/werman/noise-suppression-for-voice), when installed."""
    extra = [f"{d}/librnnoise_ladspa.so" for d in os.environ.get("LADSPA_PATH", "").split(":") if d]
    return _first_existing(extra + _lib_patterns("ladspa", "librnnoise_ladspa.so"))


def noise_options() -> tuple[tuple[str, str], ...]:
    options = [("off", "Off")]
    if find_rnnoise():
        options.append(("rnnoise", "AI (RNNoise)"))
    if _first_existing(_lib_patterns("spa-0.2", "aec/libspa-aec-webrtc.so")):
        options.append(("webrtc", "WebRTC: noise and echo"))
    # no "noisegate": PipeWire 1.6 clamps its Level control from NaN ("measure") to 0, so it never opens
    return tuple(options)


def available() -> bool:
    tools = ("pipewire", "pw-dump", "pw-cli", "pw-metadata")
    if not FLATPAK_ID:
        return all(shutil.which(tool) for tool in tools)
    r = _run(["sh", "-c", " && ".join(f"command -v {t} >/dev/null" for t in tools)])
    return bool(r and r.returncode == 0)


def _hrirs_ready() -> None:
    """In the Flatpak, copy the impulse responses where the host's PipeWire can read them."""
    if HRIR_DIR != PACKAGED_HRIRS and not os.path.isdir(HRIR_DIR):
        tmp = HRIR_DIR + ".tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(PACKAGED_HRIRS, tmp)
        os.replace(tmp, HRIR_DIR)


# ----------------------------------------------------------------- geometry
def speaker_directions(width: float) -> dict[str, tuple[int, int]]:
    """Channel -> (elevation, azimuth) in degrees; azimuth 0 = front, 90 = left."""
    w = max(0.0, min(1.0, width))
    front, rear = 15 + 60 * w, 165 - 60 * w
    return {"FL": (0, front), "FR": (0, 360 - front), "FC": (0, 0), "LFE": (-40, 0),
            "RL": (0, rear), "RR": (0, 360 - rear), "SL": (0, 90), "SR": (0, 270)}


def hrir_file(elevation: int, azimuth: float) -> str:
    step = 5 if elevation == 0 else 30
    az = int(round(azimuth / step) * step) % 360
    return os.path.join(HRIR_DIR, f"e{elevation:+03d}_a{az:03d}.wav")


# --------------------------------------------------------------------- room
def room_ir(experience: str, rate: int = 48000) -> str | None:
    """A stereo, decorrelated, exponentially decaying noise tail (our own, not SONAMI's rooms)."""
    if experience not in ROOMS:
        return None
    decay, _wet = ROOMS[experience]
    path = os.path.join(CACHE_DIR, f"room-{experience}-v2.wav")
    if os.path.exists(path):
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    rng = random.Random(experience)
    n, predelay = int(decay * rate), int(0.012 * rate)
    tails = ([0.0] * (n + predelay), [0.0] * (n + predelay))
    lp = [0.0, 0.0]
    for i in range(predelay, n + predelay):
        env = math.exp(-6.9 * (i - predelay) / n)  # −60 dB at the end
        damp = 0.25 + 0.6 * (i / (n + predelay))  # darker as it decays, like air and walls do
        for ch in (0, 1):
            lp[ch] += (rng.uniform(-1, 1) - lp[ch]) * (1 - damp)
            tails[ch][i] = lp[ch] * env
    # unit energy per ear, so the wet level is the ambience's share of the sound
    scale = [1 / math.sqrt(sum(v * v for v in t)) for t in tails]
    frames = bytearray()
    for i in range(n + predelay):
        for ch in (0, 1):
            v = int(round(max(-1.0, min(1.0, tails[ch][i] * scale[ch])) * (2 ** 23 - 1)))
            frames += v.to_bytes(4, "little", signed=True)[:3]
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(rate)
        w.writeframes(bytes(frames))
    os.replace(tmp, path)
    return path


# ------------------------------------------------------------ PipeWire config
def _key(key: str) -> str:
    return key if all(c.isalnum() or c in "._-*:" for c in key) else json.dumps(key)


def _spa(value) -> str:
    """Python value -> SPA JSON."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(round(value, 6)) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        return "{ " + " ".join(f"{_key(k)} = {_spa(v)}" for k, v in value.items()) + " }"
    return "[ " + " ".join(_spa(v) for v in value) + " ]"


def _config(*modules: dict) -> str:
    base = [
        {"name": "libpipewire-module-rt", "args": {}, "flags": ["ifexists", "nofail"]},
        {"name": "libpipewire-module-protocol-native"},
        {"name": "libpipewire-module-client-node"},
        {"name": "libpipewire-module-adapter"},
    ]
    return "\n".join([
        "context.properties = " + _spa({"log.level": 0}),
        "context.spa-libs = " + _spa({"audio.convert.*": "audioconvert/libspa-audioconvert",
                                      "support.*": "support/libspa-support"}),
        "context.modules = " + _spa(base + list(modules)),
    ]) + "\n"


def eq_params(eq) -> dict[str, float]:
    """Control values of the equalizer nodes, for a live update."""
    gains = [max(-EQ_LIMIT_DB, min(EQ_LIMIT_DB, float(g))) for g in eq]
    return {f"eq{ear}{b}:Gain": g for ear in "LR" for b, g in enumerate(gains)}


def output_graph(s: OutputSettings) -> tuple[dict, list[str]]:
    """Filter graph (nodes, links, inputs, outputs) and the input channel positions."""
    nodes, links = [], []
    ears: dict[str, list[str]] = {"L": [], "R": []}  # what each ear's mixer receives
    if s.spatial:
        inputs = []
        for ch, (el, az) in speaker_directions(s.width).items():
            nodes.append({"type": "builtin", "label": "copy", "name": f"in{ch}"})
            inputs.append(f"in{ch}:In")
            for ear, idx in (("L", 0), ("R", 1)):
                name = f"hrir{ch}{ear}"
                nodes.append({"type": "builtin", "label": "convolver", "name": name,
                              "config": {"filename": hrir_file(el, az), "channel": idx, "gain": CHANNEL_GAIN}})
                links.append({"output": f"in{ch}:Out", "input": f"{name}:In"})
                ears[ear].append(f"{name}:Out")
        positions = list(CHANNELS)
    else:
        inputs = ["inL:In", "inR:In"]
        for ear in "LR":
            nodes.append({"type": "builtin", "label": "copy", "name": f"in{ear}"})
            ears[ear].append(f"in{ear}:Out")
        positions = ["FL", "FR"]
    room = room_ir(s.experience) if s.spatial else None
    if room:
        # ambience from the mono sum of both ears, two decorrelated tails, mixed back in
        wet = ROOMS[s.experience][1]
        nodes.append({"type": "builtin", "label": "mixer", "name": "roomSend",
                      "control": {"Gain 1": 0.5, "Gain 2": 0.5}})
        for ear, idx in (("L", 0), ("R", 1)):
            nodes.append({"type": "builtin", "label": "convolver", "name": f"room{ear}",
                          "config": {"filename": room, "channel": idx, "gain": wet}})
            links.append({"output": "roomSend:Out", "input": f"room{ear}:In"})
    gains = eq_params(s.eq)
    outputs = []
    for n, ear in enumerate("LR", 1):
        last = ears[ear][0]
        if len(ears[ear]) > 1:
            nodes.append({"type": "builtin", "label": "mixer", "name": f"mix{ear}",
                          "control": {f"Gain {i}": 1.0 for i in range(1, len(ears[ear]) + 1)}})
            for i, port in enumerate(ears[ear], 1):
                links.append({"output": port, "input": f"mix{ear}:In {i}"})
            last = f"mix{ear}:Out"
        if room:
            nodes.append({"type": "builtin", "label": "mixer", "name": f"dry{ear}"})
            links.append({"output": last, "input": f"dry{ear}:In 1"})
            links.append({"output": last, "input": f"roomSend:In {n}"})
            links.append({"output": f"room{ear}:Out", "input": f"dry{ear}:In 2"})
            last = f"dry{ear}:Out"
        for b, (freq, kind) in enumerate(EQ_BANDS):  # always there, so the gains can change live
            name = f"eq{ear}{b}"
            nodes.append({"type": "builtin", "label": kind, "name": name,
                          "control": {"Freq": float(freq), "Q": 1.0, "Gain": gains[f"{name}:Gain"]}})
            links.append({"output": last, "input": f"{name}:In"})
            last = f"{name}:Out"
        outputs.append(last)
    return {"nodes": nodes, "links": links, "inputs": inputs, "outputs": outputs}, positions


def output_config(s: OutputSettings, target: str, name: str, label: str) -> str:
    graph, positions = output_graph(s)
    description = f"{label} ({_('Spatial 7.1') if s.spatial else _('Equalizer')})"
    return _config({"name": "libpipewire-module-filter-chain", "args": {
        "node.description": description,
        "media.name": description,
        "filter.graph": graph,
        "capture.props": {"node.name": name, "media.class": "Audio/Sink",
                          "audio.channels": len(positions), "audio.position": positions},
        "playback.props": {"node.name": f"{name}.headset", "node.passive": True, "audio.channels": 2,
                           "audio.position": ["FL", "FR"], "target.object": target, "stream.dont-remix": True},
    }})


def mic_graph(m: MicSettings, rnnoise: str | None = None) -> dict | None:
    """The microphone's filter chain, or None when there's nothing to filter (WebRTC alone)."""
    nodes = []  # (node, input port, output port)
    if m.noise == "rnnoise":
        nodes.append(({"type": "ladspa", "name": "rnnoise", "plugin": rnnoise or "librnnoise_ladspa",
                       "label": "noise_suppressor_mono", "control": {"VAD Threshold (%)": 50.0}}, "Input", "Output"))
    if m.highpass:
        nodes.append(({"type": "builtin", "label": "bq_highpass", "name": "highpass",
                       "control": {"Freq": HIGHPASS_HZ, "Q": 0.707}}, "In", "Out"))
    for i, (kind, hz, q, db) in enumerate(MIC_PRESETS.get(m.preset, ())):
        nodes.append(({"type": "builtin", "label": kind, "name": f"voice{i}",
                       "control": {"Freq": float(hz), "Q": q, "Gain": db}}, "In", "Out"))
    if not nodes:
        return None
    links = [{"output": f"{a['name']}:{a_out}", "input": f"{b['name']}:{b_in}"}
             for (a, _ai, a_out), (b, b_in, _bo) in zip(nodes, nodes[1:])]
    first, last = nodes[0], nodes[-1]
    return {"nodes": [n for n, _i, _o in nodes], "links": links,
            "inputs": [f"{first[0]['name']}:{first[1]}"], "outputs": [f"{last[0]['name']}:{last[2]}"]}


def voice_name(label: str) -> str:
    """What the processed microphone is called in the sound settings and in other apps."""
    return f"{label} ({_('voice processing')})"


def mic_config(m: MicSettings, source: str, sink: str | None, name: str, label: str,
               rnnoise: str | None = None) -> str:
    """WebRTC (noise suppression and echo cancellation against what the headset plays) and/or a
    filter chain; the last stage is the new microphone, `name`."""
    description = voice_name(label)
    graph = mic_graph(m, rnnoise)
    modules = []
    target = source
    if m.noise == "webrtc":
        stage = f"{name}.webrtc" if graph else name
        modules.append({"name": "libpipewire-module-echo-cancel", "args": {
            "library.name": "aec/libspa-aec-webrtc",
            "monitor.mode": True,  # the reference is what the headset plays, no extra sink
            "audio.channels": 1, "audio.position": ["MONO"],
            "aec.args": {"webrtc.noise_suppression": True, "webrtc.high_pass_filter": True,
                         "webrtc.gain_control": False, "webrtc.extended_filter": False},
            "capture.props": {"node.name": f"{stage}.capture", "target.object": source, "node.passive": True,
                              "node.dont-reconnect": True},
            "source.props": {"node.name": stage, "node.description": description if not graph
                             else f"{description} 1/2"},
            "sink.props": {"node.name": f"{stage}.reference", "node.passive": True,
                           **({"target.object": sink} if sink else {})},
        }})
        target = stage
    if graph:
        modules.append({"name": "libpipewire-module-filter-chain", "args": {
            "node.description": description,
            "media.name": description,
            "audio.channels": 1, "audio.position": ["MONO"],
            **({"audio.rate": 48000} if m.noise == "rnnoise" else {}),  # RNNoise works at 48 kHz only
            "filter.graph": graph,
            "capture.props": {"node.name": f"{name}.capture", "target.object": target, "node.passive": True,
                              "node.dont-reconnect": True},
            "playback.props": {"node.name": name, "media.class": "Audio/Source"},
        }})
    return _config(*modules)


# ------------------------------------------------------------ PipeWire state
def pw_objects() -> list[dict]:
    r = _run(["pw-dump"])
    try:
        return json.loads(r.stdout or "[]") if r else []
    except ValueError:
        return []


def _props(o: dict) -> dict:
    return (o.get("info") or {}).get("props") or {}


def find_nodes(vid: int, pid: int, objects: list[dict]) -> dict[str, str]:
    """{'sink': node.name, 'source': node.name} of the audio device with these USB ids."""
    devices = {o["id"]: _props(o) for o in objects if o.get("type") == "PipeWire:Interface:Device"}
    found: dict[str, str] = {}
    for o in objects:
        props = _props(o) if o.get("type") == "PipeWire:Interface:Node" else {}
        dev = devices.get(props.get("device.id"), {})
        try:
            ids = (int(str(dev.get("device.vendor.id", "0")), 16), int(str(dev.get("device.product.id", "0")), 16))
        except ValueError:
            continue
        kind = {"Audio/Sink": "sink", "Audio/Source": "source"}.get(props.get("media.class"))
        if ids == (vid, pid) and kind and kind not in found:
            found[kind] = props["node.name"]
    return found


def node_id(name: str, objects: list[dict]) -> int | None:
    return next((o["id"] for o in objects if o.get("type") == "PipeWire:Interface:Node"
                 and _props(o).get("node.name") == name), None)


def default_node(kind: str, objects: list[dict]) -> str | None:
    """The configured default sink/source, else the current one."""
    found = {}
    for o in objects:
        if o.get("type") == "PipeWire:Interface:Metadata" and o.get("props", {}).get("metadata.name") == "default":
            for item in o.get("metadata") or []:
                value = item.get("value")
                if isinstance(value, dict):
                    found[item.get("key")] = value.get("name")
    return found.get(f"default.configured.audio.{kind}") or found.get(f"default.audio.{kind}")


def set_default_node(kind: str, name: str) -> None:
    _run(["pw-metadata", "-n", "default", "0", f"default.configured.audio.{kind}", json.dumps({"name": name}),
          "Spa:String:JSON"])


def set_params(node: int, params: dict[str, float]) -> None:
    flat = " ".join(f"{json.dumps(k)} {v:.3f}" for k, v in params.items())
    _run(["pw-cli", "set-param", str(node), "Props", f"{{ params = [ {flat} ] }}"])


# ---------------------------------------------------------------- processes
class Engine:
    """A detached `pipewire -c` process running one config. The pid file holds the pid on the host,
    written by the shell that becomes PipeWire."""

    def __init__(self, name: str, runtime_dir: str = RUNTIME_DIR):
        self.name = name
        self.conf = os.path.join(runtime_dir, f"{name}.conf")
        self.pidfile = os.path.join(runtime_dir, f"{name}.pid")
        self.log = os.path.join(runtime_dir, f"{name}.log")

    def pid(self) -> int | None:
        try:
            with open(self.pidfile) as f:
                pid = int(f.read())
        except (OSError, ValueError):
            return None
        if FLATPAK_ID:
            r = _run(["cat", f"/proc/{pid}/cmdline"])
            cmdline = r.stdout if r else ""
        else:
            try:
                with open(f"/proc/{pid}/cmdline") as f:
                    cmdline = f.read()
            except OSError:
                cmdline = ""
        return pid if self.conf in cmdline else None

    @property
    def running(self) -> bool:
        return self.pid() is not None

    def start(self, config: str) -> None:
        self.stop()
        os.makedirs(os.path.dirname(self.conf), exist_ok=True)
        with open(self.conf, "w") as f:
            f.write(config)
        script = 'echo $$ > "$1" && exec pipewire -c "$2"'
        with open(self.log, "w") as log:
            proc = subprocess.Popen(host(["sh", "-c", script, "sh", self.pidfile, self.conf]),
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        time.sleep(0.3)
        if proc.poll() is not None:
            raise ValueError(f"PipeWire refused the {self.name} graph: {self.last_error()}")

    def stop(self) -> None:
        pid = self.pid()
        if pid is not None:
            if FLATPAK_ID:
                _run(["kill", str(pid)])
            else:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            for _ in range(20):  # the old nodes must be gone before new ones take their names
                if self.pid() is None:
                    break
                time.sleep(0.05)
        try:
            os.remove(self.pidfile)
        except OSError:
            pass

    def last_error(self) -> str:
        try:
            with open(self.log) as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            return lines[-1] if lines else "no output"
        except OSError:
            return "no log"


# ------------------------------------------------------------------ controls
SPATIAL = C.Toggle("spatial", "Spatial audio", C.Group.ENGINE, "Virtual 7.1 surround for headphones",
                   readable=False, persist=True)
WIDTH = C.Range("spatial_width", "Speaker width", C.Group.ENGINE, "How far apart the virtual speakers are",
                readable=False, persist=True, min=0, max=100, step=10, unit="%")
EXPERIENCE = C.Choice("spatial_experience", "Experience", C.Group.ENGINE,
                      "Performance is dry; Balanced and Immersion add a room around you", readable=False,
                      persist=True, options=EXPERIENCES)
SOFTWARE_EQ = C.Equalizer("software_eq", "Equalizer", C.Group.ENGINE, readable=False, persist=True,
                          bands_hz=tuple(hz for hz, _k in EQ_BANDS), min_db=-EQ_LIMIT_DB, max_db=EQ_LIMIT_DB,
                          presets=EQ_PRESETS)
MIC_PRESET = C.Choice("mic_preset", "Voice preset", C.Group.VOICE, "NGENUITY's microphone equalizer presets",
                      readable=False, persist=True,
                      options=(("off", "Off"), ("high", "High boost"), ("mid", "Mid boost"), ("low", "Low boost")))
HIGHPASS = C.Toggle("mic_highpass", "Cut low rumble", C.Group.VOICE, "High-pass filter at 80 Hz",
                    readable=False, persist=True)
VOICE_DEVICE = C.Info("voice_device", "Processed microphone", C.Group.VOICE)


def noise_control(options) -> C.Choice:
    return C.Choice("mic_noise", "Noise reduction", C.Group.VOICE,
                    "Creates a separate microphone with the processing; it becomes the default if the "
                    "headset's was", readable=False, persist=True, options=options)


class AudioEngine:
    """Spatial audio, software equalizer and voice processing for one headset."""

    def __init__(self, vid: int, pid: int, label: str, notify: Callable[[str, object], None],
                 hardware_eq: bool = False, runtime_dir: str = RUNTIME_DIR):
        self.vid, self.pid, self.label = vid, pid, label
        tag = f"{vid:04x}_{pid:04x}"
        self.output_name, self.mic_name = f"hyperx_linux_output.{tag}", f"hyperx_linux_mic.{tag}"
        self.output = Engine(f"output-{tag}", runtime_dir)
        self.mic = Engine(f"mic-{tag}", runtime_dir)
        self.out_settings, self.mic_settings = OutputSettings(), MicSettings()
        self.values: dict[str, object] = {}
        self._notify = notify
        self.controls: tuple[C.Control, ...] = (
            SPATIAL, WIDTH, EXPERIENCE, *(() if hardware_eq else (SOFTWARE_EQ,)),
            noise_control(noise_options()), HIGHPASS, MIC_PRESET, VOICE_DEVICE)

    def handles(self, control_id: str) -> bool:
        return any(c.id == control_id for c in self.controls)

    def _set_value(self, control_id: str, value: object) -> None:
        if self.values.get(control_id, object()) != value:
            self.values[control_id] = value
            self._notify(control_id, value)

    # -------------------------------------------------------------- settings
    def load_state(self, saved: dict) -> None:
        o, m = self.out_settings, self.mic_settings
        o.spatial = bool(saved.get("spatial", o.spatial))
        o.width = float(saved.get("spatial_width", o.width * 100)) / 100
        o.experience = str(saved.get("spatial_experience", o.experience))
        if self.handles("software_eq") and saved.get("software_eq") is not None:
            o.eq = tuple(float(g) for g in saved["software_eq"])
        m.noise = str(saved.get("mic_noise", m.noise))
        m.highpass = bool(saved.get("mic_highpass", m.highpass))
        m.preset = str(saved.get("mic_preset", m.preset))
        values = {"spatial": o.spatial, "spatial_width": round(o.width * 100), "spatial_experience": o.experience,
                  "mic_noise": m.noise, "mic_highpass": m.highpass, "mic_preset": m.preset}
        if self.handles("software_eq"):
            values["software_eq"] = list(o.eq)
        values["voice_device"] = voice_name(self.label) if self.mic.running else _("Off")
        for cid, value in values.items():
            self._set_value(cid, value)

    def restore(self, saved: dict) -> None:
        """Bring back what was on: called when the headset connects."""
        self.load_state(saved)
        self._update_output(wait=True)
        self._update_mic(wait=True)

    def apply(self, control_id: str, value: object, live: bool = False) -> None:
        o, m = self.out_settings, self.mic_settings
        if control_id == "software_eq":
            o.eq = tuple(float(g) for g in value)
            self._set_value(control_id, list(o.eq))
            node = node_id(self.output_name, pw_objects()) if self.output.running else None
            if node is not None and o.needed:
                set_params(node, eq_params(o.eq))  # no restart, no gap in the sound
            else:
                self._update_output()
            return
        if live:
            return
        if control_id == "spatial":
            o.spatial = bool(value)
        elif control_id == "spatial_width":
            o.width = float(value) / 100
        elif control_id == "spatial_experience":
            o.experience = str(value)
        elif control_id == "mic_noise":
            m.noise = str(value)
        elif control_id == "mic_highpass":
            m.highpass = bool(value)
        elif control_id == "mic_preset":
            m.preset = str(value)
        else:
            raise KeyError(control_id)
        self._set_value(control_id, value)
        if control_id.startswith("mic_"):
            self._update_mic()
        else:
            self._update_output()

    def stop(self) -> None:
        """Hand the defaults back to the headset and end both graphs."""
        objects = pw_objects() if (self.output.running or self.mic.running) else []
        nodes = find_nodes(self.vid, self.pid, objects)
        for kind, ours, engine in (("sink", self.output_name, self.output), ("source", self.mic_name, self.mic)):
            if engine.running:
                if default_node(kind, objects) == ours and nodes.get(kind):
                    set_default_node(kind, nodes[kind])
                engine.stop()

    # -------------------------------------------------------------- graphs
    def _headset(self, kind: str, wait: bool) -> tuple[str, dict]:
        deadline = time.monotonic() + (NODE_WAIT if wait else 0)
        while True:
            objects = pw_objects()
            nodes = find_nodes(self.vid, self.pid, objects)
            if kind in nodes or time.monotonic() >= deadline:
                break
            time.sleep(0.5)
        if kind not in nodes:
            what = "output" if kind == "sink" else "microphone"
            raise ValueError(f"PipeWire doesn't show this headset's {what}; is it plugged in and turned on?")
        return nodes[kind], nodes

    def _switch(self, kind: str, headset: str, ours: str, engine: Engine, config: str | None) -> None:
        """Start (config) or stop (None) a graph, moving the default device along when it was the headset."""
        objects = pw_objects()
        current = default_node(kind, objects)
        if config is None:
            if engine.running:
                if current == ours:
                    set_default_node(kind, headset)
                engine.stop()
            return
        engine.start(config)
        deadline = time.monotonic() + NODE_WAIT
        while node_id(ours, pw_objects()) is None:
            if time.monotonic() >= deadline:
                raise ValueError(f"PipeWire didn't create the {engine.name} node: {engine.last_error()}")
            time.sleep(0.1)
        if current in (None, headset, ours):
            set_default_node(kind, ours)

    def _update_output(self, wait: bool = False) -> None:
        if not self.out_settings.needed and not self.output.running:
            return
        sink, _nodes = self._headset("sink", wait)
        if self.out_settings.spatial:
            _hrirs_ready()
        config = output_config(self.out_settings, sink, self.output_name, self.label) \
            if self.out_settings.needed else None
        self._switch("sink", sink, self.output_name, self.output, config)

    def _update_mic(self, wait: bool = False) -> None:
        m = self.mic_settings
        if not m.needed and not self.mic.running:
            self._set_value("voice_device", _("Off"))
            return
        source, nodes = self._headset("source", wait)
        rnnoise = find_rnnoise()
        if m.noise == "rnnoise" and rnnoise is None:
            raise ValueError("the RNNoise plugin isn't installed (noise-suppression-for-voice)")
        config = mic_config(m, source, nodes.get("sink"), self.mic_name, self.label, rnnoise) if m.needed else None
        self._switch("source", source, self.mic_name, self.mic, config)
        self._set_value("voice_device", voice_name(self.label) if m.needed else _("Off"))
