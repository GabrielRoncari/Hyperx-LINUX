# Audio engine: spatial audio, equalizer and voice processing

NGENUITY's spatial audio and microphone effects never run on the headset. On Windows they run on the
PC, so on Linux the same work is done by PipeWire. This page explains what NGENUITY does, how
HyperX Linux reproduces it and what it can't reproduce.

## What NGENUITY does (static analysis)

- **NGENUITY Legacy 2.38** licensed **DTS Headphone:X v2** per headset model and installed it as a
  Windows audio effect (APO). The DTS code and the licence belong to DTS/Xperi, so this part can't be
  reproduced.
- **NGENUITY 3.1** has an *Audio Engine* built on **HEAR360 SONAMI** (`SONAMIGaming_x64.dll`), driven
  by a Rust service (`hxn-srv-audio-engine`). It creates HP-branded virtual audio devices: an 8 or 12
  channel spatial endpoint, chat, mic mix and stream mix. Settings: spatial on/off, speaker width,
  an "experience" preset, a 10-band equalizer (32 Hz low shelf, peaking bands, high shelf, ±8 dB), and
  for the microphone AI noise reduction, a high-pass filter, an equalizer with three presets, a
  compressor, presence, a de-esser and a limiter
  (`HXN.FeatureControllers.AudioEngineInputFeatureController`).

## What HyperX Linux does

Every headset page has two extra groups, *Audio engine* and *Voice processing*. They work the same on
every HyperX headset, because nothing is sent to the device.

| NGENUITY | HyperX Linux |
|---|---|
| Spatial 7.1 endpoint (SONAMI / DTS) | a 7.1 virtual sink: each channel is convolved with the **MIT KEMAR** head-related impulse responses (left and right ear) of its virtual speaker |
| Speaker width | front speakers at ±(15 + 60·w)°, rear at ±(165 − 60·w)°, sides at ±90°, as NGENUITY draws them |
| Experience | *Performance* is dry; *Balanced* and *Immersion* add our own synthetic room (decorrelated noise tails, 0.35 s and 0.8 s, at 18% and 30%) |
| 10-band equalizer | the same bands as PipeWire biquads. Only headsets **without** an equalizer of their own get it (the Cloud III S uses its hardware EQ). Dragging a slider changes the gains live, without restarting anything |
| AI noise reduction | **RNNoise** when its LADSPA plugin ([noise-suppression-for-voice](https://github.com/werman/noise-suppression-for-voice)) is installed, or **WebRTC** noise suppression, which also cancels the headset's own sound leaking into the microphone |
| High-pass filter | 80 Hz, 2nd order |
| Mic presets | NGENUITY's own values, below |

NGENUITY's microphone presets, copied as they are (Q 0.5):

| Preset | Bands |
|---|---|
| High boost | low shelf 300 Hz +5 dB, high shelf 1500 Hz +5 dB |
| Mid boost | peaking 140 Hz, 500 Hz and 1800 Hz, +4 dB each |
| Low boost | low shelf 300 Hz +5 dB, high shelf 1500 Hz −5 dB |

### Measured

Measured through PipeWire with noise bursts on each channel, recorded from a silent null sink:

- Ear difference: front ±10.6 dB, side ±11.8 dB, rear ±9.9 dB, centre 0.0 dB (with *Immersion*'s room:
  ±9.0, ±10.4, ±8.6, 0.1 dB). One front speaker comes out at −0.5 dB, so the volume matches stereo.
- Equalizer: +8 dB at 1 kHz measures +8.0 dB at 1 kHz and +0.1 dB at 100 Hz and 8 kHz.
- Microphone, with background noise at −55 dBFS and tones at −20 dBFS: the high-pass filter brings
  40 Hz down to −32 dBFS and leaves voice frequencies alone. WebRTC brings the noise down to −66…−72
  dBFS and leaves the voice at −20 dBFS.

## How it runs

- Each part (output, microphone) is a filter graph run by its own `pipewire -c <file>` process,
  **detached** from the app: if the app crashes, the sound keeps working. The files are in
  `$XDG_RUNTIME_DIR/hyperx-linux/` (`output-<vid>_<pid>.conf/.log/.pid`, the same for `mic-…`).
- The graphs attach to the headset by its **USB ids**, never by "whatever is the default".
- When it turns on, the virtual device becomes the **default** output or microphone if the headset
  was the default. When it turns off, or the headset disconnects, the default goes back to the
  headset. The processed microphone is a separate device called
  "*<headset> (voice processing)*", so you can also pick it in a single app (Discord, OBS…).
- Settings are saved like the others and restored when the headset connects.
- Stereo sources are spread to the virtual speakers by PipeWire's own upmixing (`channelmix.upmix`,
  on by default).
- **Flatpak**: the GNOME runtime has neither the `pipewire` daemon nor the filter-chain and
  echo-cancel modules, so the graphs run on the host through `flatpak-spawn --host` (hence the
  `org.freedesktop.Flatpak` permission). The impulse responses are copied to the app's cache folder,
  where the host can read them.

From the command line:

```sh
hyperx-linux set spatial on
hyperx-linux set spatial-width 70
hyperx-linux set spatial-experience immersion
hyperx-linux set software-eq bass          # headsets without their own equalizer
hyperx-linux set mic-noise webrtc
hyperx-linux set mic-preset "mid boost"
```

## What it doesn't do

- **DTS Headphone:X** and **SONAMI**: proprietary, licensed per product. Spatial audio here comes
  from open measurements of a dummy head, so it sounds different, and it isn't personalised.
- **Noise gate**: PipeWire 1.6's `noisegate` filter clamps its `Level` control from NaN ("measure
  the input") to 0 before the first sample, so the gate never opens (filter-graph.c,
  `port_set_control_value`). It comes back once that is fixed upstream.
- **Compressor, presence, de-esser, limiter** for the microphone: PipeWire has no built-in ones;
  they would need LV2 plugins (LSP, x42, Calf), which most systems don't have installed.
- **Chat / game mix and stream mix** endpoints: a separate chat device can be made with PipeWire's
  own [virtual devices](https://docs.pipewire.org/page_module_loopback.html).

## Data and credits

- Impulse responses: MIT KEMAR, "normal pinna" (Gardner and Martin, 1995), SOFA conversion by the
  Acoustics Research Institute ([sofacoustics.org](https://sofacoustics.org/data/database/mit/)),
  "provided without any usage restrictions". 85 directions are extracted into
  `hyperx_linux/data/hrtf-mit-kemar` by [`tools/hrir_extract.py`](../tools/hrir_extract.py).
- The room tails are generated by the app (`audio.room_ir`); no recordings are used.
