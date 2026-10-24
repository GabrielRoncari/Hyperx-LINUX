# HyperX Pulsefire mice: HID protocols

Drivers: `hyperx_linux/drivers/mouse_universal.py` (+ transport in `universal.py`),
`mouse_dseries.py`, `mouse_feature7.py` · support level: **community** (a few models **experimental**)

Nothing on this page was measured on hardware by this project. It is a synthesis of public reverse
engineering (captures, firmware analysis, NGENUITY decompilation). Only facts are recorded: bytes,
offsets, semantics. No source code was copied. Where the drivers do something different from the
research notes, **the driver's behaviour wins** and the difference is called out.

Confidence labels used below:

- **Hardware**: someone owning the device sent the command and published the result.
- **Official**: taken from NGENUITY captures or decompilation, not independently re-tested.
- **Unconfirmed**: analogy or hypothesis.

Multi-byte integers are little endian unless stated otherwise.

## Which family is my mouse?

| Family | Mice | Control node | Packet |
|---|---|---|---|
| **Universal** (HP era) | Haste 2 family, Saga Pro, Saga | vendor collection, usually USB interface 2 | 64-byte output report, **report ID = command** |
| **D-series** (NGENUITY 2) | Dart, Haste Wireless, FPS Pro rev. CD | vendor collection, interface 1 or 2 | 64-byte output report, **no report ID**, `[0]` = opcode |
| **Feature 0x07** (Kingston gen.) | Surge, Core, FPS Pro (original), Raid | interface 1, collection `0xFF01:0x0001` | 264-byte **feature report** ID `07` |

Choose by VID:PID, then confirm from the report descriptor of the hidraw node (do not trust
interface numbers alone: they differ between cable and dongle, and usage pages differ between modes).
Never open the nodes whose PID is listed as firmware/DFU.

Linux hidraw reminders:

- Numbered report: the `write()` buffer starts with the report ID (Universal).
- No report ID: the `write()` buffer starts with `00`, which the kernel strips, then 64 bytes (D-series).
- `read()` includes the report ID only for numbered reports.
- Feature reports: `HIDIOCSFEATURE`/`HIDIOCGFEATURE` with `buf[0]` = report ID.

### About "firmware/DFU" PIDs

NGENUITY 3.1 (Rust hub, `get_product_definition`) tags some endpoints with the `DFU` purpose flag;
NGENUITY Legacy 2.38 names them `*_DFU`. Those are bootloader/update identities. **They are never
opened for commands.** NGENUITY 3.1 marks `03F0:0E97` (Haste 2 Wireless) and `03F0:05BF`/`03F0:07BF`
(Saga Pro) as DFU, although some community notes list them as normal-operation IDs. This project
follows NGENUITY. The Haste 3 entries combine the DFU flag with Reassign+Sensor on the same endpoint,
so their role is ambiguous (see the last section).

---

## 1. Universal family

### Models and USB IDs

VID is always `03F0`. "Driver" = the PID is claimed by the driver. Interface numbers are from the
NGENUITY Legacy 2.38 HID path table (`MI_xx`), not from the v3 table (which has none).

| Model | Receiver (2.4 GHz) | Cable | Firmware/DFU (never open) | Interface | Confidence | Driver |
|---|---|---|---|---|---|---|
| Pulsefire Haste 2 Wireless | `0F98` (rev. 2: `0299`) | `0D97` (rev. 2: `0F97`) | `0E97`, `0199`, `0198`, `0399` | 2 | Hardware | all four normal PIDs |
| Pulsefire Haste 2 (wired) | n/a | `0B97` (bcdDevice 0x1111) | `0C97` | 2 | Hardware | yes |
| Haste 2 Core Wireless | `0AB5` | PID unknown | `0BB5` | 2 | Hardware (partial) | dongle only |
| Haste 2 Core (wired, separate model) | n/a | `04B5` | `05B5` | 2 | none | **no** (no public protocol data) |
| Haste 2 Pro (4K) | `0CBD` | `0ABD` | `0BBD`, `0DBD` | dongle 3, cable 2 | IDs: hardware; protocol: official | experimental |
| Haste 2 Mini Wireless | `0DA0` | `0BA0` | `0CA0`, `0EA0` | 2 | IDs only | experimental |
| Haste 2 S Wireless | `0BB8` | `0AB8` | `0DB8`, `0CB8` | 2 | Official | experimental |
| Pulsefire Saga Pro | `06BF` | `04BF` | `05BF`, `07BF` | dongle 3, cable 2 | Hardware | yes |
| Pulsefire Saga (wired, 8 kHz) | n/a | `0EBE` | `0FBE` | 2 (inferred) | IDs only | experimental |

Notes:

- The Saga Pro and Haste 2 Pro also appear in NGENUITY as 3-in-one "Instant Pair" children (child PID
  `04BF` and `0ABD`). The dongle PID for that variant is not published; not handled.
- The Haste 2 Wireless dongle exposes a third interface: an HID **LampArray** (usage page `0x59`,
  Windows Dynamic Lighting). Nothing uses it on Linux; on the Saga Pro dongle it does not answer `50 02`.
- Usage page of the control collection: `0xFF00` on dongles and on the Haste 2 / Haste 2 Wireless
  cable; **`0xFF13`** on the Saga Pro cable and the Haste 2 Pro cable. NGENUITY 3.1 lists some of these
  endpoints as `FF90/FF00`; the driver does not match on usage page. It requires the descriptor to
  declare an **output report 0x32** (the DPI command) on the chosen interface.
- The wired Haste 2 descriptor is 598 bytes long and starts with `06 00 FF`.
- Bluetooth (Saga Pro, Fuse) is not covered by any public source.

### Packet format

```
request: [cmd][sub][payload ...]            64 bytes, zero padded, [0] is the report ID
reply:   [cmd+1][sub][payload ...]          input report, 64 bytes (read commands only)
ack:     FF 01 <12-byte device id> <cmd> <sub> <status> 00 ...    [14]=cmd [15]=sub [16]=status (00 = ok)
```

- Report IDs declared as both Output and Feature (63 data bytes): `10 12 14 20 22 30 32 36 40 42 44 50 52
  60 62 F0 FA FC`. Every tool uses **output reports** on the interrupt OUT endpoint (`0x04`); nobody
  uses the feature variant. The driver sends exactly 64 bytes with the report ID in `[0]` (some
  community code sends 65 bytes; Windows reportedly rejects that framing).
- Replies arrive on interrupt IN `0x83`. Every request is acknowledged. Writes get **only** the ack.
- **Through the dongle two acks arrive**: one from the dongle (local, status always 00), one from the
  mouse (same device id as in `11 01`). With the mouse asleep only the dongle ack returns, except for
  `10 01`, which the dongle answers from a cache. A request issued while the mouse sleeps may be queued
  by the dongle and delivered on wake-up.
- High bits in `[1]` (`0x40|sub`, "target" bits) make the mouse reject the command: use the plain sub.
- **Slots** (`[2..3]` u16 in write commands, a single byte `[2]` in reads): `0` = live (RAM, lost at
  power-off), `1` = onboard profile in flash (what NGENUITY's "Save" writes; reloaded into slot 0 at
  power-on).
- **Pacing**: at least 10 ms between packets (NGENUITY). Through the dongle send **one request at a
  time** and wait for the cmd+1 reply, otherwise packets are lost on the RF link.
- **Validation**: match the reply on byte 0 and 1 (`51 02` at `[0..1]`). Do not search the buffer for
  `51 02` anywhere: acks carry the same two bytes at `[14..15]`, which produces a false "0 %, charging".

### Commands

| Feature | Request | Reply | Notes | Confidence |
|---|---|---|---|---|
| Device info | `10 01` | `11 01`: `[2..13]` device id, `[31]` category (02 = mouse), `[35..36]` VID, `[37..46]` five u16 (PIDs/version), `[41..42]` mouse PID, `[43..44]` firmware, `[45..46]` dongle PID, `[52]` layout, `[54]` LED count | Category is **not** 02 on the Haste 2 Core Wireless dongle (seen as headset): identify by PID. Not sent by the driver. | Hardware (Haste 2 Wireless) |
| Link state | `52 01` | `53 01 <s>`: `[2]` 1 = mouse connected to dongle, 0 = asleep/off | Dongle models only. NGENUITY polls every ~5 s. | Hardware (Haste 2 Wireless); untested on Saga Pro |
| Battery | `50 02` | `51 02`: `[2]` percent, `[3]` state (00 discharging, 01 charging, 02 full, 03 charger error, FF unknown), `[4..5]` temperature in C (i16), `[6..7]` millivolts (u16), `[8]` gauge type, `[9]` charger type, `[10]` low-battery threshold (read as 0 on the Haste 2, `0A` on the Saga Pro; meaning unverified) | Real sample: `51 02 36 00 1a 00 00 0f 01 00` = 54 %, 26 C, 3840 mV. Also sent by the mouse unprompted on wake. Works on the cable. | Hardware (Haste 2 Wireless, Saga Pro) |
| Low-battery alert | `50 01 <pct> <save>` | ack only | pct 5-25 (default 10); `save`=1 writes flash. **Not sent.** | Hardware |
| Read DPI + polling | `32 02 <slot>` | `33 02 RR MM AA <stage records>`: `[2]` polling code, `[3]` enabled-stage mask, `[4]` active stage (0-based), stage *i* at `[5+5i .. 9+5i]` = u16 DPI code, R, G, B (indicator colour); up to 11 records | DPI = (code + 1) * 50. Sample: `33 02 08 0f 01 07 00 ff 00 00 0f 00 00 00 ff 1f 00 ff ff 00 3f ...` = 1000 Hz, 400/800/1600/3200, second stage active. | Hardware |
| Write DPI + polling | `32 01 <slot u16> RR MM AA <stage records>`: `[4]` polling, `[5]` mask, `[6]` active, stage *i* at `[7+5i..11+5i]` | ack only | Read-modify-write: copy the reply, change the field, write it back, re-read to confirm. DPI code = DPI/50 - 1. Official range 200-26000 in steps of 50 (Haste 2 Core Wireless: 50-12000). | Hardware |
| Polling codes | (inside `32 01`) | n/a | `40`=125, `20`=250, `10`=500, `08`=1000, `04`=2000, `02`=4000, `01`=8000 Hz (Hz = 8000/code). Wireless models: 125-1000 official; 4000 Hz captured on the Saga Pro dongle only. | Hardware / official |
| Read sensor | `36 02 <slot>` | `37 02`: `[2]` angle snap, `[3]` angle tune, `[4]` angle tune on, `[5]` lift-off (00 = 1 mm, 02 = 2 mm), `[6]` motion sync | Only lift-off was seen to change. | Hardware (Haste 2 Wireless) |
| Write sensor | `36 01 <slot u16> <snap> <tune> <tune_on> <lift> <msync>` | ack only | Lift-off lands in `[7]`. Read-modify-write; do not send fixed bytes (they overwrite angle snap and motion sync). | Hardware (Haste 2 Wireless) |
| Brightness | `40 01 <slot u16> <b>`; read `40 02 <slot>` | `41 02 <b>` | 0-255; NGENUITY sends floor(percent * 255 / 100). Applies to live colour too. | Hardware |
| Live colour | `44 01 <pages> 00` then `44 02 <page u16> R G B ...` | ack, sometimes `45 02` | RAM only; each frame holds ~1.5-2 s and then the mouse returns to its saved effect, so resend at <= 0.5 s (NGENUITY ~15/s). RGB per LED from `[4]`. The `44 01` header is optional on the Wireless; sending both is safe. | Hardware |
| Firmware effect | `42 02 <slot u16> <mode> <duration u16> <dir> <color type> <R G B x3>` | ack + `43 02`; read `42 03 <slot>` -> `43 03` | Working modes: 00 off, 01 solid, 02 breathing, 04 colour cycle (03/05/09 become 04). Duration uses only the low byte. Mode 06 = FrameLight. | Hardware (Haste 2 Wireless) |
| FrameLight (persistent static colour) | `44 03 <frames> <packets u16> <slot u16> 00`, `44 04 <index u16> R G B`, `42 02 <slot u16> 06 32 00` | `45 04 <index>` per frame, `43 02` at the end | With slot 1 the colour survives power-off. **Not sent.** | Hardware (Saga Pro, Haste 2 Wireless) |
| Button remap | `20 05` (reset), `20 01`, `20 02`, `22 07`; read `20 03`/`20 04` | `21 xx` | 4-byte entries `[type][button][a][b]`. **Not sent.** | Hardware (Haste 2 Wireless) |

### Events (report `FB`, unprompted)

| Event | Meaning | Confidence |
|---|---|---|
| `FB 0A <0\|1>` | mouse link lost (0) or restored (1), sleep/wake | Hardware |
| `FB 08 <stage> <code u16>` | DPI stage changed by the button; DPI = (code + 1) * 50 (example `FB 08 03 3F 00` = stage 3, 3200 DPI) | Hardware |
| `FB 01 <button> 00 <0\|1>` | button released/pressed (`0x20` = DPI button) | Hardware |
| `FB 07`, `45 xx` | notifications of unknown meaning; ignored | |
| `51 02 ...` | battery report sent by the mouse on wake | Hardware |

### Sequences worth knowing

- On every link restore NGENUITY re-applies state: `10 01`, `52 01`, `50 02`, `40 01`, `36 01`, `32 01`,
  `20 05`, `22 07`.
- Static colour without streaming (3 packets, tested): `44 03` (1 frame) -> `44 04` (colour) -> `42 02`
  mode 06. Only valid for slot 0 as a volatile effect; with slot 1 it is the flash "Save".

### What the driver implements

- Controls: battery (models with a battery), DPI (200 to the model maximum, step 50), DPI stage 1-5,
  polling rate, lift-off (models that have it), colour and brightness.
- **Slot 0 only.** Every write goes to RAM. Slot 1, the Saga Pro "save RGB to mouse" flow and
  FrameLight are not sent: they write flash and reset button maps/macros.
- Reads `32 02`/`36 02`/`40 02` with a single slot byte `0`. DPI writes are read-modify-write: the driver
  keeps the reply bytes `[2..61]`, edits polling, active stage or the active stage's DPI code, and
  writes `32 01 00 00` + the first 58 of those bytes (reply `[2..59]`, i.e. all 11 possible stage
  records), then re-reads. Only the active stage's DPI can be changed.
- Lift-off: read-modify-write of `[2..6]` of `37 02`, only the lift byte changes.
- Colour has **no read-back** (`readable=False`). The live colour is sent (`44 01 01 00` then
  `44 02 00 00 R G B`, repeated per LED; 5 identical triplets on the Saga) **only after the user picks a
  colour**, and then re-sent every 0.5 s as a keep-alive for as long as the app runs. Nothing is sent
  at start-up, so the mouse keeps its own effect until the user chooses.
- Wireless models: link check with `52 01` before any read; commands are not sent while offline;
  battery polled every 30 s; `FB 0A`, `FB 08` and unprompted `51 02` are handled.
- Polling options offered: 125-1000 Hz for wireless models; Haste 2 (wired) and Saga 125-8000;
  Haste 2 Pro 125-4000 (also on its cable); the Saga Pro cable entry offers 125-1000 only, which is
  stricter than needed (2000/4000 Hz are advertised for 2.4 GHz only).
- Left out: slot 1 and flash, effects, FrameLight, button remapping, macros, low-battery threshold,
  `10 01` identification, sensor calibration, firmware.
- Experimental models (Haste 2 Pro, Haste 2 S, Haste 2 Mini, Saga) reuse the Haste 2 Wireless layout
  without any capture of their own.

### Avoid

- `10 02` (factory reset per NGENUITY) and `12 01` (named "factory reset" in one community note; not in
  the NGENUITY command table). Treat both as destructive.
- Report IDs `30`, `F0`, `FA`, `FC` (presumed firmware) and every DFU PID.
- `70 04` / `70 07` (enter pairing / clear pairing info on 3-in-one dongles).
- Repeated slot 1 writes (`32 01 01..`, `40 01 01..`, `44 03 .. 01`, `42 02 01..`, `50 01 .. 01`): flash wear.
  Only on an explicit user "save", never in a loop.
- `20 05 01 00 01` and `22 07 01 00 01`: they reset the onboard button maps and macros.
- `14 01` (profile setup/reset) and `36 03` (lift calibration) without understanding them.
- Replaying NGENUITY's start-up packets blindly (`40 01 00 00 82`, `32 01 00 00 08 01 01 1f 00 ff ff`...).
- Searching replies by pattern anywhere in the buffer (see Validation above).

### Confidence and sources

Haste 2 Wireless: **Hardware** (ngenuity-linux-cli with captures, Lumen, several battery tools).
Haste 2 wired: Hardware (haste2ctl). Haste 2 Core Wireless: Hardware for DPI read/write, brightness, live
colour (hyperx_open_lighting, open-ngenuity); polling and battery not verified. Saga Pro: Hardware
(hyperx-saga-control: battery, DPI, polling, live and saved colour); `32 02`/`36 02`/`40 02`/`42 03`
reads are unconfirmed on this exact model. Haste 2 Pro, Mini, S, Saga: Official/unconfirmed.

Links: see the Sources table at the end.

---

## 2. D-series ("NGENUITY 2")

### Models and USB IDs

| Model | Receiver | Cable | Firmware/DFU (never open) | Interface (receiver / cable) | Confidence | Driver |
|---|---|---|---|---|---|---|
| Pulsefire Dart | `0951:16E1`, `03F0:068E` | `0951:16E2`, `03F0:088E` | `0951:16F7`, `0951:16F8`, `03F0:078E`, `03F0:098E` | 2 (`0xFF00`) / 1 (`0xFF13`) | Hardware | yes |
| Pulsefire Haste Wireless | `03F0:028E` | `03F0:048E` | `03F0:038E`, `03F0:058E` | 2 / 2 (`0xFF00`) | Hardware (requests), medium for replies | yes |
| Pulsefire FPS Pro rev. CD | n/a | `0951:1729`, `03F0:0693` | `0951:172A`, `03F0:0793` | 2 (`0xFF00`) | Official (captures) | experimental |

Notes:

- The research notes called `16F7`/`16F8`/`078E`/`098E` (Dart) and `172A`/`0793` (FPS Pro CD) "unknown
  function". NGENUITY marks all of them as DFU (v3 table `DFU` flag; Legacy `*_DFU` names), as it does
  `038E`/`058E` for the Haste Wireless, which the notes guessed were internal mouse IDs (they appear in the
  `50 00 00` reply because they are PIDs the firmware refers to). They are excluded.
- Dart receiver descriptor: input 64 B, output 64 B, feature 64 B, no report ID; other nodes: mouse (if0),
  keyboard (if1), consumer. Dart cable descriptor: input 64 B and output 64 B (EP `0x03` OUT, `0x82` IN),
  no feature, no report ID; mouse is if0, keyboard if2, consumer if3.
- Haste Wireless cable: the interface-2 descriptor is 25 bytes, like the Dart cable's `0xFF13`, so check the
  usage page in the descriptor. Receiver EP `0x04` OUT / `0x83` IN, cable `0x02` OUT / `0x82` IN.
- FPS Pro CD: IF0 boot mouse, IF1 keyboard + consumer, IF2 vendor `0xFF00:0x0001` with 64-byte input,
  output and feature, no report IDs (EP `0x83` IN, `0x04` OUT). **There is no `0xFF01` collection**, so
  this is *not* a feature-0x07 mouse (an OpenRGB issue claiming it works with `07 0A` conflicts with the
  captured descriptors; the captures are trusted).
- With cable and receiver connected at once, **only commands over the cable take effect** (Dart).

### Packet format

```
request:  [opcode][b1][b2][b3][data ...]      64 bytes, no report ID; hidraw write() = 00 + these 64 bytes
reply:    echo of the request with the read fields filled in (compare [0..2] with the request)
error:    <first 3 request bytes> 02 EC <code>    0 unsupported, 1 sub/range, 2 index, 3 count, 4 value out of range, 5 link down
event:    FF 03 ...                                unprompted
```

- Read opcodes `50`-`57`; write opcodes `D0`-`DF` (`D0` polling, `D2` LED, `D3` DPI, `D4` buttons, `D5`/`D6`
  macros, `DE` **save to EEPROM**). Write format: `<op> <sub> <index> <length> <data...>`; `[3]` is the data
  length and the Dart firmware ignores it.
- `D0`-`DF` change **RAM only** and never revert by themselves. Persistence needs `DE`.
- Unused reply bytes repeat the request, so send zeros.
- Through a receiver, error code 5 (`.. .. .. 02 EC 05`) = mouse asleep or out of range: show "offline", not 0 %.
- Timeout used by the other implementations: 1 s; 2 ms between writes in OpenRGB (sending colours too fast
  caused trouble).
- The FPS Pro CD is an exception: no echo was captured, only an unprompted `FF 07 00 00 00 00 00 00 64 FF`
  after connection and after `D3 01`/`D3 00` (not decoded).

### Commands: Pulsefire Dart (reference), Haste Wireless differences marked

| Feature | Request | Reply | Notes | Confidence |
|---|---|---|---|---|
| Battery | `51 00 00` | `[3]`=len; `[4]` percent (`FF` = no gauge); `[5]` power state (0 battery, 1 external charging, 2 external via another path, 3 external with charge pin inactive = done); `[6]` low-battery threshold (default 15); `[7..8]` millivolts (u16, `FFFF` = none); `[9]` gauge status; `[10..13]` counter | Gauge updates about every 5 s. Sample: 60 % = `8F 0F` = 3983 mV. **Haste Wireless**: `[4]` percent, `[5]` 0 on battery / 1 charging on cable / 2 charged on cable, `[6..12]` unknown (a voltage may sit at `[9..10]`; unverified). | Hardware (Dart), medium (Haste Wireless) |
| Link (receiver only) | `46` | `46 00 00 01 xx`: xx 01 connected, 00 asleep | On a cable the mouse answers with the error frame `46 00 00 02 EC 00`. | Hardware |
| Hardware info | `50 00 00` | `[4..5]` PID, `[6..7]` VID, `[8..11]` firmware, `[12..]` ASCII name | Haste Wireless: `[12..15]` carry the DFU-side PID/VID. Not sent. | Hardware |
| Config dump | `50 03` | Dart: `[4]`/`[5]` LED effect of zone 0/1, `[6]` enabled stages, `[7..8]` sniper DPI, `[9..18]` 5 DPIs, `[19..33]` 5 stage colours, `[34..51]` 6 buttons, **`[52]` polling code**. Haste Wireless: DPIs from `[10..19]` (x100), colours `[20..34]`, buttons `[35..52]`, **`[53]` polling code** | Polling code 0..3 = 125/250/500/1000 Hz. | Hardware |
| Read DPI | `53 00 00` | `[4]` active stage, `[5]` stage mask, `[6..7]` min, `[8..9]` max, `[10..11]` sniper, `[12..21]` 5 stage DPIs (u16), `[22..36]` 5 colours; Haste Wireless adds **`[37]` lift-off (1 = 1 mm, 2 = 2 mm)** | **Dart: DPI = value * 50** (max `0x140` = 16000). **Haste Wireless: DPI = value * 100** (max `A0` = 160). The Dart-style offsets are the correct ones; one community driver reads them shifted. | Hardware |
| Read LED | `52 00 00` | `[4]` effect (high nibble) / sub-mode, `[5]` sub-mode, `[6]` speed, `[7]` brightness, `[8..10]` colour 1, `[11..13]` colour 2, zone 1 from `[14]` | Reflects the RAM block that `D2` modifies. | Hardware |
| Polling | `D0 00 00 01 p` | echo | p: 0 = 125, 1 = 250, 2 = 500, 3 = 1000 Hz; p >= 4 is error 4. Persist with `DE 00`. | Hardware |
| Low-battery threshold | `D1 00 00 01 v` | echo | v 5-25. Persist with `DE 01`. **Not sent.** | Hardware (Dart) |
| LED | `D2 zz ee 08 R1 G1 B1 R2 G2 B2 BR SP` | echo | `zz`: 00 logo, 10 scroll wheel, 20 both (Dart); Haste Wireless has one zone, `zz` = 00. `ee`: high nibble effect (0 static, 1 spectrum, 2 breathing, 3 reactive), low nibble sub-mode. `BR` 0..`0x64`. `SP` 0..255, 0 fastest. Static colour: `ee`=00, `SP`=00. **Haste Wireless: the mouse returns to its saved config about 2 s later**, so the colour must be streamed. | Hardware |
| Select DPI stage | `D3 00 00 01 s` | echo | s 0-4, must be enabled in the mask (else error 4). Applies immediately. | Hardware |
| Enabled stages | `D3 01 00 01 m` | echo | Bit n = stage n (`1F` all). Send before per-stage commands. | Hardware |
| Stage DPI | `D3 02 s 02 lo hi` | echo | u16 in units of 50 (Dart) or 100 (Haste Wireless, `D3 02 s 02 v 00`). Stage must be enabled (else error 2). Applies to the sensor if it is the active stage. | Hardware |
| Stage colour | `D3 03 s 03 R G B` | echo | Flash colour shown on stage change. | Hardware |
| Sniper DPI | `D3 04 00 02 lo hi` | echo | Out-of-range values are silently ignored. | Hardware (Dart) |
| Lift-off | Haste Wireless: `D3 05 00 01 v v` | echo | v 1 = 1 mm, 2 = 2 mm (repeated in `[5]`). The Dart has **no** lift-off (`D3 05` -> error 1). | Hardware (Haste Wireless) |
| Buttons | `D4 b t 02 c x` | echo | Dart `b`: 0 left, 1 right, 2 middle, 3 forward, 4 back, 5 DPI; Haste Wireless: 3 back, 4 forward (reversed). `t`: 0 off, 1 mouse (c 1-5), 2 keyboard, 3 media (0-6), 4 macro, 7 special (c 8 = DPI cycle). **Not sent.** | Hardware |
| Save | `DE k` | delayed echo | `FF` all, 0 config/polling, 1 battery, 2 LED, 3 DPI, 4 buttons, 5 macros. Writes EEPROM and briefly stalls the mouse. **Not sent.** | Hardware |
| Debounce (hidden) | `D0 54 78 00 p r` | echo | RAM only, unchecked. **Not sent.** | Unconfirmed |

### Commands: FPS Pro rev. CD (captured from NGENUITY, no echo)

| Feature | Request | Notes | Confidence |
|---|---|---|---|
| Direct LED | `D8 00 00 06 R1 G1 B1 R2 G2 B2 64` | zone 1 = wheel, zone 2 = logo (per SignalRGB). Brightness is done by scaling RGB; `[10]` stays `64`. Breathing/cycle are rendered on the host at ~12-16 Hz; no onboard effect seen. | Official |
| Polling | `D0 00 00 01 p` | Captured `p=03` only; the 125/250/500 codes come from the Dart firmware. | Official / unconfirmed codes |
| Stage DPI | `D3 02 s 02 lo hi` | Units of 50; captured 700/1600/3200. | Official |
| Stage colour | `D3 03 s 03 R G B` | | Official |
| Enabled stages / current | `D3 01 00 01 mask`, `D3 00 00 01 s` | both trigger the unprompted `FF 07` report | Official |
| Buttons | `D4 b t 02 c aux` | as the Dart | Official |
| Unknown | `D0 04 00 01 00` | sent by NGENUITY on connect; not decoded | Unconfirmed |

### Events (`FF 03`, unprompted)

Dart: `FF 03 s p a sn f btn` where `[2]` DPI stage, `[3]` power state (as in `51`), `[4]` awake (0 = asleep;
the receiver emits `FF 03 00 00 00` when the link drops), `[5]` sniper held, `[6]` factory reset just
happened, `[7]` physical buttons (bit 0 left, 1 right, 2 middle, 3 forward, 4 back, 5 DPI). Haste Wireless:
`[2]` stage, `[3]` charge (0/1/2), `[4]` 0 going to sleep / 1 awake (wireless only), `[7]` buttons (01 left,
02 right, 04 middle, 08 back, 10 forward, 20 DPI), `[8]` shortcut function running. Sent on power change, on
every button edge and on wake; there is no periodic heartbeat.

### What the driver implements

- **Dart / Dart cable / Haste Wireless / Haste Wireless cable** (`DSeriesMouse`): battery, DPI (200-16000),
  DPI stage 1-5, polling, colour, brightness; lift-off on the Haste Wireless. Not implemented: sniper DPI,
  per-stage colours, enabling stages, button remapping, macros, LED effects, the low-battery threshold,
  hardware info, hidden debounce.
- Reads: `46` (link, receiver models), `51 00 00`, `53 00 00`, `50 03` (polling only), `52 00 00`
  (brightness `[7]`, colour `[8..10]` when the effect nibble is 0). Battery polled every 30 s; the `FF 03`
  event updates stage, power state and link.
- DPI write changes **only the active stage** (`D3 02 <active> 02 ...`); the clamp is 200-16000 for both
  Dart (50 DPI step) and Haste Wireless (100 DPI step). The driver parses the Dart voltage from `[7..8]`
  (accepted only if 2500-5000 mV). Power states 1 and 2 count as charging and 3 as full on the Dart; on the
  Haste Wireless 1 is charging and 2 is full.
- LED: `D2 <zone> 00 08 R G B R G B BR 00`, zone `20` (both) on the Dart, `00` on the Haste Wireless.
  Colour is sent only after the user picks one. The **Dart is not re-sent** (RAM value stays); the **Haste
  Wireless is re-sent every 0.5 s** because it reverts after ~2 s.
- **No `DE`.** Nothing is ever saved to the EEPROM, so a power cycle or a new NGENUITY session restores the
  mouse's stored settings. Matching a reply uses `[0..2]`; error frames are treated as failures, and
  error 5 marks a receiver model offline.
- **FPS Pro CD** (`FPSProCD`): colour (`D8`, both zones the same, streamed at 4 Hz) and polling (`D0`).
  Nothing is read back (`readable=False`), so the values shown are only what the app last sent; polling
  is applied optimistically. No DPI, buttons or the `D0 04` packet are sent.

### Avoid

- `DE k` outside an explicit "save" (30 ms of I2C per block, stalls the mouse; `DE 00` has a page-wrap bug
  with custom LED arrays). `DF AA k` (loads RAM defaults, wipes current settings).
- `D1 01` (writes EEPROM and **resets** the MCU), `D1 02`, `D1 94 78 ...`.
- `D0 AA 55 D0 AA 55` (test mode: disables sleep, writes a sensor register), `D0 54 ...` (unchecked).
- `D0 01` / `D0 02` (custom LED arrays: buffer overflow in stock firmware), `D6` with a wrong count.
- Receiver-only `50 00 D2`, `57 ...`, `A4 ...` (pairing), `A0 EA 5A A5` (bootloader unlock), `A1 ...`
  (**enters DFU**), `A2 ...`.
- `53 94 87 ...` (reads **and writes** a sensor register), `51 01 ...` (fuel-gauge control).
- Unknown opcodes on the FPS Pro CD; assume it shares the Dart's dangerous set.
- Sending to the DFU PIDs listed above.
- The DPI step: do not apply the Dart's 50 to the Haste Wireless (the same `D3 02` uses 100 there).

### Confidence and sources

Dart: **Hardware**, high (USB captures of NGENUITY on the mouse, OpenRGB driver tested wired and wireless,
byte-level static analysis of the dumped 1.1.0.8 firmware). The millivolt field and power states 2/3 come
from firmware code only; the voltage matches a capture. Haste Wireless: requests confirmed in hardware by
captures; replies were documented from the author's mouse but have no capture in the repo (medium-high).
FPS Pro CD: **Official**, captures attached to an OpenRGB issue; the Dart's firmware knowledge is used only
for the polling code table.

---

## 3. Feature 0x07 / 264 bytes (Kingston generation)

### Models and USB IDs

| Model | Normal IDs | Firmware/DFU (never open) | Interface | Zones | Confidence | Driver |
|---|---|---|---|---|---|---|
| Pulsefire Surge | `0951:16D3`, `03F0:0490` (also `03F0:0298` in NGENUITY 3.1, unseen elsewhere) | `03F0:0398` | 1 (`0xFF01:0x0001`) | 32-LED strip + logo | Hardware (LED) | community |
| Pulsefire Core | `0951:16DE`, `03F0:0D8F` (also `03F0:0498`) | `03F0:0598` | 1 | logo | Hardware (LED) | community |
| Pulsefire FPS Pro (original) | `0951:16D7`, `03F0:0E8F` | `03F0:0793` is the CD revision's; the original has none listed | 1 | logo | not explicitly confirmed | experimental |
| Pulsefire Raid | `0951:16E4` (bcdDevice 0x1124), `03F0:0290` | `0951:16F9`, `03F0:0390` | 1 (config/RGB), 2 (8-byte ACK) | wheel + logo | Hardware (LED, DPI) | community |

Notes:

- NGENUITY Legacy locates these on interface 1 collection 5 (`Col05`). Interface 1 also holds keyboard,
  system control, consumer and a `0xFF00:0x0001` vendor collection (Core: report ID 6, 3-byte input,
  meaning unknown); on Linux they share one hidraw node.
- Report descriptor of the control collection (Raid): `06 01 FF 09 01 A1 01 85 07 09 20 15 00 26 FF 00 75
  08 96 07 01 B1 02 C0` = **feature report ID 7 with 263 data bytes (264 with the ID)**, no input/output.
- Interface 2 (`0xFF00:0xFF00`, 8-byte input/output, EP `0x83` IN only) exists on the Raid and the Core.
  On the Raid it carries the ACKs described below; its role on the Core is presumed the same.
- The Raid PID in one OpenRGB issue (`16BE`) is a typo.

### Packet format

Feature report ID `07`, 264 bytes including the ID, set with `SET_REPORT` (wValue `0x0307`, wIndex 1) and read
with `GET_REPORT`. No source reads a reply to the colour packet; there is no write confirmation.

### Commands

| Feature | Request (offsets with report ID at `[0]`) | Reply | Notes | Confidence |
|---|---|---|---|---|
| Direct colour: Core, FPS Pro `16D7` | `07 0A R G B 00 00 00 A0`, zero to 264 | none | One LED (logo). `[8]` is `A0` in OpenRGB and `FF` in a SignalRGB plugin; unknown meaning (brightness or constant). | Hardware (Core) |
| Direct colour: Raid | `07 0A Rw Gw Bw Rl Gl Bl A0`, zero to 264 | none | `[2..4]` wheel, `[5..7]` logo. Volatile: resend within 1 s (OpenRGB 1 s, NGENUITY Legacy ~62 ms). No brightness field. Does not use the section selector, so it is the safe path. | Hardware |
| Direct colour: Surge | `07 14 00 A0 00 00 00 00`, then `[0x08..0x27]` = R of LEDs 0-31, `[0x28..0x47]` = G, `[0x48..0x67]` = B (planar), `[0x68..0x6B]` = 0, `[0x6C..0x6E]` = R,G,B of the logo, zero to 264 | none | `[3]` is `A0` in OpenRGB and in the NGENUITY capture (a SignalRGB plugin uses `0A`). Continuous stream, >=20 Hz; if it stops the mouse returns to the onboard effect. | Hardware (+ partial NGENUITY capture) |
| Raid: session start | `07 07 00`, wait ~110 ms, `07 07 01` | ACK `00 00 07 07 00 00 00 00` for the second | Enables ACKs on interface 2. **Not sent.** | Hardware (OpenHyperX) |
| Raid: select section | `07 03 04 64` (runtime) / `07 03 01 64` (onboard) | ACK `00 00 07 03 00 ...` | **Dangerous**, see below. **Not sent.** | Hardware (incident) |
| Raid: request image | `07 81`, wait ~110 ms, `GET_FEATURE 07` | `07 81 <section> ...` with a 256-byte profile image from `[8]`, ACK `00 00 07 81 FF 00 00 00` | **Not sent.** | Hardware (OpenHyperX) |
| Raid: write image | `07 01 <section>` + the image just read | ACK `00 00 07 01 00 ...` | Flash when section 1. **Not sent.** | Hardware (OpenHyperX) |
| Raid image fields | polling at `0x18` (ms: 01 = 1000, 02 = 500, 04 = 250, 08 = 125 Hz); DPI stages 1-5 X as **big-endian** u16 at `0x19/1B/1D/1F/21` (value = DPI/50), Y at `0x25..0x2D`, active stage `0x31`, enabled `0x32..0x36`, stage colours `0x69..0x77` | n/a | Range 200-16000 in steps of 50. Other field names (LED intensity `0x16`, sniper DPI, LED modes `0x37/0x38`, angle snapping `0x3A`, 13 four-byte button registers `0x7C..0xAF`) have no validated codec. | Hardware (OpenHyperX) |
| Surge/FPS Pro `16D7`/Core profile commands | `07 01 ...`, `07 03 <profile> 01 01 01 <brightness>`, `07 07 <profile>` | n/a | Defined in OpenRGB but never called; layouts unknown. Sibling analogy with the Raid is unverified and the image offsets do **not** transfer. | Unconfirmed |
| DPI / polling / lift-off on Surge, Core, FPS Pro `16D7` | none | | No public source. A SignalRGB plugin sends a `D3` (D-series) packet to these mice, which lack the matching interface: likely non-functional. | none |

### What the driver implements

- **Direct colour only**, one `Color` control and one `Brightness` control (no read-back). Brightness
  scales the RGB values in software, because no brightness field is known.
- Nothing is sent until the user picks a colour. After that the frame is re-sent as a keep-alive for as
  long as the app runs: every 0.25 s (Surge, Core, FPS Pro) and every 0.5 s (Raid). The Raid frame
  writes the same colour into both wheel and logo; the Surge frame fills all 32 strip LEDs and the logo
  with one colour. The Raid rate sits inside the observed 750 ms tolerance.
- Matching: interface 1, a collection on usage page `0xFF01`, and a feature report 7 of 263 data bytes.
- **Left out on purpose:** `07 01`, `07 03`, `07 07`, `07 81`, the Raid session start and every onboard
  save. They address the profile memory (flash) and one of them locked a mouse.
- **The Raid `07 03` freeze.** On 2026-09-27 the OpenHyperX author sent `07 03 04 64` alone to a cold Raid
  whose runtime image was empty (the GET returned `07 81 04` and zeros). The mouse lost cursor, clicks
  and light until it was replugged, and that project suspended all runtime reads and writes. The cause
  is presumed to be activating an empty runtime image. This is why the whole section selector, and read
  or write of images, stays out of the driver, even though DPI and polling through the image were
  confirmed to work on other days.
- Nothing is read, so there are no events and no battery.

### Avoid

- `07 03 04 64` (and `07 81` + GET) when the state is unknown; never write an image built from scratch or
  from an empty GET.
- Any use of `07 01`, `07 03`, `07 07` on the Surge, Core and FPS Pro `16D7` (unknown layouts).
- The Raid's repeated onboard save (`07 03 01 64` ... `07 01 01`): flash.
- Writing blindly to interface 2 (Core/Raid ACK node).
- `D3`-style DPI packets from SignalRGB plugins for these mice.
- The DFU PIDs `16F9`, `0390`, `0398`, `0598`.
- Sending the Surge frame faster than needed (~20 Hz suffices).

### Confidence and sources

Surge/Core/Raid colour: Hardware (OpenRGB drivers, user confirmations, Core descriptor captured in
OpenRGB issue #1552, Raid also by OpenHyperX on 2026-09-17). FPS Pro `16D7`: unconfirmed (same packet as the Core).
Raid DPI/polling/save: Hardware by OpenHyperX but with the open freeze incident above.

---

## 4. Mice without a public protocol

None of these has a driver.

- **Pulsefire Haste (1st gen, wired)** `0951:1727`, `03F0:0F8F` (also `03F0:0494`, `03F0:0694` in NGENUITY 3.1;
  DFU `0951:1728`, `03F0:0190`, `03F0:0594`, `03F0:0794`). Only direct colour is known: a 65-byte
  feature report (report ID 0 + 64) `04 F2 00 00 00 00 00 02` ("direct mode") then `81 R G B 00 00 00 02`,
  repeated (OpenRGB resends after >50 ms of silence); the `02` sits at `[7]` in OpenRGB but at `[8]` in a
  SignalRGB plugin. Windows uses interface 3, usage page `0xFF90`; the Linux paths in OpenRGB (interface 0,
  usage page 1) contradict that and no descriptor is published. DPI, polling and lift-off have no source,
  and with OpenRGB controlling this mouse several users reported the DPI dropping to an unusable value
  (cause unknown, possibly `04 F2`). Needs a capture of NGENUITY before anything beyond colour.
- **Pulsefire Fuse / Fuse Wireless**: `03F0:0FBD` (Legacy 2.38, interface 2; DFU path on interface 1
  collection 2) and `03F0:0F8D` (NGENUITY 3.1 table, the same PID as the Mat RGB); DFU `03F0:01BE`. No
  protocol data. The `Universal*` prefix in NGENUITY Legacy suggests the Universal family but this is a
  guess. Single AAA battery, 2.4 GHz and Bluetooth.
- **Pulsefire Haste 3 / Haste 3 Pro / Haste 3 Wireless**: the research notes say the IDs are unknown, but
  the NGENUITY 3.1 table lists them: Haste 3 Pro `03F0:02CD` (cable) and `03F0:04CD` (wireless), Haste 3
  Wireless `03F0:0FC0` and `03F0:02CE`, Haste 3 `03F0:05CE`, all `FF90/FF00` with the DFU flag set together
  with Reassign+Sensor (firmware images for `dfu1620-hid.dll`). Which of these is the normal-operation
  endpoint is therefore unclear. Capabilities from the NGENUITY 3.1 config: Haste 3 100-16000 DPI in steps
  of 100, up to 1000 Hz; Haste 3 Pro and Wireless 50-42000 in steps of 50, up to 8000 Hz; no RGB. Protocol
  presumed Universal, unconfirmed. Do not probe.
- **Pulsefire Haste 2 Core (wired)** `03F0:04B5` (DFU `05B5`): in NGENUITY as a separate model from the
  Haste 2 Core Wireless; no source discusses it.
- Other NGENUITY mice with no data: Pulsefire Warp (`0699`, `0899`; DFU `0799`, `0999`).

---

## Sources

| Source | What it gave | License |
|---|---|---|
| [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB) (`Controllers/HyperXMouseController/*`, issues #812 #999 #1063 #1552 #1659 #1745 #2097 #2271 #2283 #2592 #3233 #4250 #4283 #4288 #4560, MRs !275 !673 !1233 !1673 !1814 !1908 !2336 !2369 !3736) | Surge/Core/FPS Pro/Raid colour, Dart, Haste, Haste 2 Wireless keep-alive, descriptors | GPL-2.0-or-later (issue text: no licence of its own) |
| [kbpk/OpenHyperX](https://github.com/kbpk/OpenHyperX) | Raid image layout, session start, freeze incident | MIT |
| [PMarinov1994/ngenuity-linux-cli](https://github.com/PMarinov1994/ngenuity-linux-cli) | Universal protocol spec, Haste 2 family, Saga/Haste 3 config | MIT |
| [rahmidaniel/Lumen](https://github.com/rahmidaniel/Lumen) | Universal ack/reply matching, battery fields | MIT |
| [notwaterbtl/hyperx-saga-control](https://github.com/notwaterbtl/hyperx-saga-control) | Saga Pro hardware validation | MIT |
| [ScottStaschke/PlasmaNGenuity-HyperX](https://github.com/ScottStaschke/PlasmaNGenuity-HyperX) and [radoslavchobanov/PlasmaNGenuity](https://github.com/radoslavchobanov/PlasmaNGenuity) | Saga Pro and Dart packets (several offsets differ from the firmware; only used as cross-check) | MIT |
| [abhinavpathak9873/hyperx_open_lighting](https://github.com/abhinavpathak9873/hyperx_open_lighting) | Haste 2 Core Wireless | MIT |
| [zee-w/open-ngenuity](https://github.com/zee-w/open-ngenuity) | Haste 2 Core Wireless, Bluetooth note | MIT |
| [czQery/waybar-hyperx-haste2](https://github.com/czQery/waybar-hyperx-haste2), [n1rocket/hyperx-haste2-battery](https://github.com/n1rocket/hyperx-haste2-battery), [devfreitas/omarchy-haste2](https://github.com/devfreitas/omarchy-haste2), [PMarinov1994/hyperx-pulsefire-haste2-kde-widget](https://github.com/PMarinov1994/hyperx-pulsefire-haste2-kde-widget) | Haste 2 battery, wired colour, Haste 2 Pro IDs | MIT |
| [Emanuel4100/omarchy-hyperx-battery](https://github.com/Emanuel4100/omarchy-hyperx-battery) | battery cross-check | GPL-2.0 |
| [Tammo0987/hyperx-battery](https://github.com/Tammo0987/hyperx-battery), [Briaoeuidhtns/hyperx_battery](https://github.com/Briaoeuidhtns/hyperx_battery), [fspy/haste2ctl](https://github.com/fspy/haste2ctl) | battery cross-check, wired Haste 2 IDs and captures | no licence file |
| [santeri3700/hyperx_pulsefire_dart_reverse_engineering](https://github.com/santeri3700/hyperx_pulsefire_dart_reverse_engineering) | Dart descriptors, captures, button codes | CC0-1.0 |
| [Kota0674/pulsedart](https://github.com/Kota0674/pulsedart) | Dart firmware analysis (reference where sources disagree) | MIT |
| [evan-razzaque/open-pulsefire-haste](https://github.com/evan-razzaque/open-pulsefire-haste) | Haste Wireless protocol and captures | GPL-3.0 |
| [Perchanxe/HyperX-PulsefireHaste-Range-Fix](https://github.com/Perchanxe/HyperX-PulsefireHaste-Range-Fix) | Haste Wireless IDs and firmware versions | MIT |
| [lbkeppler/lowerx](https://github.com/lbkeppler/lowerx) (`DeviceCatalog.swift`, from NGENUITY 2.38) | PID catalogue | no licence for code |
| [signalrgb/signal-plugins](https://gitlab.com/signalrgb/signal-plugins) | cross-checks only | no licence file (facts only) |
| [Barashkov-GO/mouse_driver](https://github.com/Barashkov-GO/mouse_driver) | Surge captured setup packet | no licence |
| NGENUITY 3.1 (Rust hub) and NGENUITY Legacy 2.38 (`NGenuity2Helper.exe`) static analysis | authoritative DFU flags, interface numbers (Legacy), Universal command names | proprietary; only facts recorded |
| [linux-hardware.org](https://linux-hardware.org/?id=usb:03f0-0fbd) | Fuse PID | public database |

Not used: `chiritsuya/HyperX-Pulsefire-Surge` (executable download, no code), `niqore/Pulsefire-FPS-Pro-SDK`
and `Atesh19/pulsefire-core-macos` (empty).
