# HyperX microphones and mouse pads — HID protocol

Driver: `hyperx_linux/drivers/lighting.py` · support level: **community** (QuadCast 2 S, Fury Ultra),
**experimental** (QuadCast 2)

Nothing here was tested by the project on hardware. The protocol facts come from public reverse
engineering (OpenRGB, QuadcastRGB and others, see [Sources](#sources)) plus offline decoding of the
public NGENUITY USB captures. Only **live** lighting is implemented: storing a colour on the device
writes flash and is left out on purpose. Where the research notes and the implemented driver differ,
the driver wins and the difference is called out.

Offsets are 0-based and refer to the 64 bytes on the wire (the report payload). OpenRGB and SignalRGB use
65-byte buffers with a report id at `[0]`; subtract one from their offsets.

## Things that are not HID

Input gain, headphone monitoring, volume and the polar pattern are **not** HID on any of these devices.

- Gain, capture mute and headphone volume are USB Audio Class controls (ALSA mixer, PipeWire or Pulse).
- The polar pattern is a physical switch or knob. On the QuadCast 2 S, holding the knob for 2 s and
  turning it changes the pattern and nothing appears on USB.
- NGENUITY 3's EQ, noise reduction and compressor are DSP in the Windows audio driver. The one
  exception is the SoloCast 2, which has filters and a presence boost in the microphone itself (below).
- None of these devices has a battery.

## Two USB devices per microphone

Each microphone enumerates as two USB devices behind an internal hub: the **audio** device (UAC plus an HID
for buttons and events) and the **controller** (LEDs). RGB always goes to the controller. No source
documents a PID change after power-up. What causes confusion is the pair of simultaneous PIDs, the
different PIDs per hardware revision (Kingston `0951`, HP `03F0`) and OpenRGB registering two *audio* PIDs
of the QuadCast S (`03F0:0294`, `03F0:0D8B`) as controllers; those never match, because interface 0 there
is AudioControl.

There are two protocol families:

- **Legacy "04/81"**: QuadCast S, DuoCast, QuadCast 2, Fury Ultra, Pulsefire Mat. Feature report without
  id, 64 bytes. A header `04 F2 ...` announces the colour packets, which are 4-byte entries `81 R G B`.
- **Universal** (NGENUITY 3): QuadCast 2 S and SoloCast 2. See [universal.md](universal.md).

## HyperX QuadCast 2 S

Class `QuadCast2S` · controller `03F0:02B5` (bcdDevice 61.12 or 61.13) · audio device `03F0:0D84`
· support **community** · universal family

- **Interface**: the LED controller has three HID interfaces. Interface 1 is the one that matters:
  interrupt IN `0x85` and OUT `0x06`, 64 bytes, numbered reports where the report id is the command
  (declared ids include `01 07 10/11 14/15 40/41 42/43 44/45 62-65 DB F0 F1 FA-FD FF`). The driver picks the
  node whose descriptor declares an output report `0x44`. GET_FEATURE stalls on all of them.
- **Transport**: plain `write()` of 64 bytes including the report id at `[0]`. Replies arrive as input
  reports. An unknown command is dropped silently. On macOS the firmware stops accepting OUTs when replies
  are not read; on Linux hidraw keeps draining the IN endpoint, but replies should still be read to pair them.

| Request | Meaning | Reply |
|---|---|---|
| `10 01` | device information (contains 0x6C = 108 LEDs); used by some tools as handshake | `11 01 ...` |
| `44 01 06 00` | live frame header; `[2]` = number of data packets (6) | ACK `FF 01`, `[14]`=44 `[15]`=01 |
| `44 02 <i> 00` + 20 x `R G B` | live frame data, i = 0..5, 120 positions of which 108 are LEDs (packet 5 uses 8) | ACK `[14]`=44 `[15]`=02 (fw 61.13) or `45 02 <i>` (fw 61.12) |
| `40 01 00 00 <0-255>` | hardware brightness; `[2..3]` = profile u16, 0 = live | ACK |
| `40 02` | read brightness | `41 02 <level>` |

- **LED map**: 12 columns x 9 rows wired as a serpentine; strip `s = floor(index / 9)`; even strips run
  bottom to top, odd strips top to bottom. The packets are in RGB order. QuadcastRGB's "upper/lower" halves
  (LEDs 0-53 / 54-107) are really front/back.
- **Live colour does not persist.** Frames must be repeated; when they stop the microphone returns to the
  stored frame or the factory rainbow. NGENUITY sends a frame every ~45 ms with ~2 ms between packets;
  keepalives of 150-250 ms are used by other tools.
- **Driver**: sends the header and six data packets with a single colour replicated 20 times, 2 ms apart,
  repeated every 200 ms (`keepalive_seconds`). Brightness is a 0-100 slider mapped to 0-255 and written to
  profile 0 (live); it is read back with `40 02`.
- **Differences from the research notes**: the notes say to wait for the reply to each data packet; the
  driver sends the seven packets fire-and-forget. The notes also say it is unknown whether `40 01`
  writes flash (OpenRGB uses `40 01 00 00 FF` as the last packet of a saved effect); the driver only ever
  uses profile 0.
- **Confidence**: live frame confirmed on hardware by several independent testers; `40`, `42`, `44 03-06`
  confirmed by a single source on firmware 61.13; mute event (`77 06 00/01` on the audio device) not verified.
- **Avoid**: `F0 F1 FA-FD` (firmware), `12 01` (factory reset), `44 03` / `44 04` / `42 02` / `40 01` with a
  non-zero profile (flash), the declared-but-unexplored ids `01 07 14 62-65 DB`, and any write to reports
  `0x77` or `0x08` of the audio device.

## HyperX QuadCast 2 (red LED)

Class `QuadCast2` · controller `03F0:09AF` · audio device `03F0:07B4` · support **experimental**

The LED is red and only brightness is controllable. The NGENUITY hub lists `07AF` as an audio endpoint, so
the `07AF` mentioned in an OpenRGB issue is not a controller.

- **Interface 0** of the controller is HID with an interrupt IN endpoint, so Linux creates a hidraw node.
  The bytes below are confirmed with libusb and on Windows; **nobody has tested the hidraw path**, hence
  the experimental level. It relies on `HIDIOCSFEATURE` producing the same SET_REPORT control transfer
  (`wIndex 0`, 64 bytes) that other tools send.
- **Packets** (feature report, no reply): brightness `81 XX 00 00 81 XX 00 00`, with `XX` from `00` to `F2`
  (`F2` is NGENUITY's maximum); heartbeat `04 XX 00 00 00 00 00 00 01`, where `XX` must equal the brightness
  or the LED flickers.
- **Behaviour**: send brightness, wait about 20 ms, send the heartbeat, repeat every ~500 ms. About 1 s after
  the host stops, the LED returns to 100 %. There is no persistence on the live path.
- **Driver**: maps 0-100 % to 0-`F2`, sends both packets every 500 ms, brightness is write-only. The notes
  recommend ~20 ms between the two packets; the driver sends them back to back.
- **Mute** is an input report `77 06 00/01` on the audio device (the mainline kernel `hid-hyperx` driver
  already turns it into `KEY_MICMUTE`). Not used by this driver.
- **Avoid**: `04 FD` and the 64-byte packet with `[12]` = brightness (persistent brightness, writes flash,
  single source); any output on the audio device's report `0x77`.

## HyperX Fury Ultra (mouse pad)

Class `FuryUltra` · `0951:1705` and `03F0:0493` · support **community**

- **Interface 0**, feature report without id, 64 bytes, legacy family, 20 LEDs (OpenRGB: 0-14 underglow,
  15-19 LED strip). The NGENUITY hub reports `03F0:0493` as the lighting endpoint of the HP revision and
  `03F0:0593` as its bootloader; `0493` was added to the driver from that table and has no hardware report.
- **Frame**: header `04 F2 00 00 00 00 00 00 02` (`[8]` = number of colour packets), then two packets of
  16 entries `81 R G B`, of which 20 positions are used. No reply. Brightness is baked into the RGB values
  (the driver scales the colour in software). Resent every 200 ms.
- **Differences**: SignalRGB frames it differently (`04 F2 00 01`, eight packets). The driver follows
  OpenRGB, which is the more consistent with the family.
- **Hidraw**: OpenRGB opens this interface through hidapi-libusb on Linux, which hints (unconfirmed) that
  there may be no hidraw node for it. If there is none, the pad is not controllable until usbfs is added.
- **Avoid**: unknown `04 xx` registers; the flash-write sequence `04 53 ...` is untested on this device.

## Not implemented

### QuadCast S and DuoCast

Controllers: QuadCast S `0951:171F`, `03F0:0F8B`, `03F0:028C`, `03F0:048C`, `03F0:068C`; DuoCast `03F0:098C`
(audio `03F0:0A8C`). NGENUITY 3.1 marks `098C` as DFU and `088C` as the lighting endpoint, while the
Legacy table and the hardware reports say the opposite; the catalog therefore blocks neither (see
[ngenuity-catalog.md](../ngenuity-catalog.md)). Confirm which id is the controller before adding a driver.

**Why not**: the LED interface (interface 0) is HID with a single interrupt **OUT** endpoint. `usbhid`
refuses interfaces without an input interrupt endpoint, so **no `/dev/hidrawN` exists for it** on Linux.
The commands are SET_REPORT/GET_REPORT control transfers on endpoint 0 with `wIndex 0`, which means usbfs
(`/dev/bus/usb/...`, libusb or pyusb). No kernel driver binds interface 0, so no detach is needed.
Interface 1 (events, interrupt IN `0x82`) is the one that gets a hidraw node, and sending through it would
use `wIndex 1`, which is wrong.

Protocol, for a contributor:

- Transfer: `bmRequestType 0x21, bRequest 0x09, wValue 0x0300, wIndex 0, wLength 64` (SET_REPORT feature,
  id 0); replies with `0xA1, 0x01, 0x0300, 0, 64`.
- Live: header `04 F2 00 00 00 00 00 00 01` then a colour packet `81 Rt Gt Bt 81 Rb Gb Bb` (two zones, RGB,
  brightness inside the RGB, no brightness command). The DuoCast fills 14 entries, only the first two
  coloured. Repeat a pair every 40-50 ms with >= 10 ms between the two; when the host stops, the
  microphone returns to its stored effect. No replies.
- Stored effect (flash, avoid unless you know why): `04 53 [8]=N` (N = data packets), N packets of 8 frames
  each, `04 02` (reply carries a checksum u32 LE at `[4..7]`: sum of all bytes sent since the last
  `04 53`/`04 02`), `04 23 [8]=01`, an end packet `08` with `[59]=28`, frame count u16 LE at `[60..61]`,
  `[62]=AA`, `[63]=55`, then `04 02` again. OpenRGB, castglow and linde12 put the parameters at `[7]`
  and the frame count in one byte; the NGENUITY captures say `[8]` and u16, and the captures win.
- Also seen: `04 58` (information, sent by NGENUITY on open), `04 56`/`04 57` (look like raw flash access:
  never send).
- Mute on the QuadCast S is unconfirmed (a single source reports `05 10 <state>` on interface 1); on the
  DuoCast it is on the audio device, vendor page `0xFFC1`/`0xFFC0` usage `0xF0`, probably the same
  `77 06 00/01` report as the QuadCast 2.

### Pulsefire Mat RGB

`03F0:0F8D` and `0951:1741`. Legacy family, feature report, `04 F2 ... 02` header plus colour packets. Not
implemented because the facts disagree:

- **LED count**: OpenRGB assumes 20 LEDs for `0F8D` (copied from the Fury Ultra) and 32 positions for
  `1741`; SignalRGB plugins and retailers say 2 zones, sent as one packet `81 R0 G0 B0 81 R1 G1 B1`.
- **Interface**: `FF90/FF00` on interface 1 on Windows, but OpenRGB matches interface 0 with usage
  `0x000C/0x0001` on Linux, and a user controlled the mat through hidraw on interface 0. Read each
  descriptor and look for `06 90 FF` before choosing.
- NGENUITY 3.1 lists `03F0:0F8D` under both the Pulsefire Fuse and the Mat (lighting endpoint, usage
  `FFFF/0001`); the Legacy table gives it to the Mat and the Fuse is `03F0:0FBD`. Another reason to wait for
  hardware captures.

### SoloCast and SoloCast 2

- **SoloCast** (`0951:170F`, `03F0:078B`): gain and mute are UAC Feature Unit controls (ALSA `Mic Capture
  Volume/Switch`). The touch mute changes the same firmware register with **no HID event and no mixer
  notification**, so the ALSA cache goes stale; read the real state with a direct UAC `GET_CUR` or detect
  digital silence. The HID collection (`0xFFC0`) exists but its packets were never published.
- **SoloCast 2** (`03F0:0FBF`): HID filters and a presence boost on a vendor interface (the NGENUITY hub
  says usage page `FF90`, usage `FF00`; the community tool guessed `FFC0`). The commands are
  `60 02` / `61 02` (bit0 high-pass, bit1 low-pass in `[7]`), `60 01 00 00 00 <bits>`, `66 02` / `67 02`
  (EQ) and `66 01 01 ...` (presence boost, +/-6 dB, `[2]=01` = saved profile, probably flash). **A single
  source** wrote and tested these on one unit, so the driver does not exist yet. Gain and mute remain UAC.
- **Avoid**: NGENUITY 3's firmware update for the SoloCast 2 (`03F00FBF.rfw`) can render a SoloCast 1
  unusable; `F0`/`FA`/`FC` and `12 01`.

### ProCast, ChargePlay, Clutch, others

- **ProCast** is an XLR microphone with no USB, so nothing to control.
- **ChargePlay** (Base, Duo, Quad, Clutch) are chargers powered over USB with no data function and no
  NGENUITY configuration.
- **Clutch** controllers: the Talon seems to use the Universal protocol according to the hub analysis
  (untested); the Tachi uses Xbox GIP; Gladiate and Tanto are standard gamepads. Avoid `12 01` and `F0/FA/FC`.
- **FlipCast, SoloCast 2 Pro** (`03F0:02C8` audio, `03F0:01C8` light): probably Universal, no public
  reverse engineering. The Vision S webcam is UVC, out of scope.

## Sources

| Source | Used for | License |
|---|---|---|
| [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB) (HyperXMicrophone, V2, Mousemat controllers; issues #1298, #3579, #5113, #5149, #2272) | QuadCast S, DuoCast, QC2S, Fury Ultra, Mat | GPL-2.0-or-later |
| [QuadcastRGB](https://github.com/Ors1mer/QuadcastRGB) (issues #4-#35) | live frames, hardware reports | GPL-2.0-only |
| [NGENUITY and QuadcastRGB captures](https://ors1mer.xyz/downloads/quadcastrgb_and_ngenuity_captures.tgz) | stored effect, checksums | none declared |
| [ikarthikng/micdeck](https://github.com/ikarthikng/micdeck) | DuoCast | GPL-3.0-only |
| [MuffinMario/quadcast2Srgb](https://github.com/MuffinMario/quadcast2Srgb) | QC2S | MIT |
| [terracatta/omarchy-limelight](https://github.com/terracatta/omarchy-limelight) | QC2S commands | MIT |
| [PMarinov1994/ngenuity-linux-cli](https://github.com/PMarinov1994/ngenuity-linux-cli) | Universal specification | MIT |
| [SunstriderEx/QuadCast2-brightness](https://github.com/SunstriderEx/QuadCast2-brightness) | QuadCast 2 brightness | MIT |
| [colaquecez/quadcast-control](https://github.com/colaquecez/quadcast-control) | QuadCast 2 | none declared |
| [Linux `hid-hyperx.c`](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-hyperx.c) | QuadCast 2 mute report | GPL-2.0-or-later |
| [Raffaelbdl/solocast2-linux](https://github.com/Raffaelbdl/solocast2-linux) | SoloCast 2 | MIT |
| [mateusands/hyperx-solocast-boot-mute](https://github.com/mateusands/hyperx-solocast-boot-mute), [vnptb/tapline](https://github.com/vnptb/tapline) | SoloCast UAC | MIT |
| [poenus/ngenuity-solocast-restore](https://github.com/poenus/ngenuity-solocast-restore) | SoloCast firmware warning | MIT |
| SignalRGB plugins (`gitlab.com/signalrgb/signal-plugins`) | Fury Ultra / Mat framing | none declared (facts only) |
| [chattydogmagazine/castglow](https://github.com/chattydogmagazine/castglow) | QuadCast S cross-check | PolyForm Noncommercial 1.0.0 (facts only) |

Projects with no declared license were used only as a reference for facts; no code was copied from any source.
