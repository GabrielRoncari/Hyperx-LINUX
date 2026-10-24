# HyperX Cloud III S Wireless — HID protocol

Driver: `hyperx_linux/drivers/cloud3s.py` · support level: **verified**

Based on the community reverse engineering of NGENUITY
([cloud3s-web-control/docs/PROTOCOL.md](https://github.com/Tomlacko/cloud3s-web-control/blob/main/docs/PROTOCOL.md):
NGENUITY Legacy 2.35 decompiled with ILSpy, NGENUITY 3.1's Rust hub disassembled) and
**re-validated on hardware** on 2026-10-24 (dongle `03f0:02cc`, bcdDevice 41.22, kernel 7.2, Pop!_OS 24.04).

## Transport

- USB interface 3 (HID), interrupt IN endpoint `0x84` only; output reports go out as `SET_REPORT`
  (hidraw does that).
- Control collection: usage page `0x01C0` (`06 C0 01` in the descriptor), reports `0x0C`/`0x0D`.
- hidraw delivers every report of the interface on one node. The enumeration problem reported by
  HyperHeadset (needing `usbcore.quirks=…:r`) did **not** happen here.

## Packets

```
request: 0C 02 03 <rw> 00 <op> <args…>     64 bytes, rw 01 = GET, 00 = SET
reply:   0C 02 03 01 00 <op> <value…>      GET only
event:   0D 02 03 00 <type> <value>
buttons: 0F <bitmask>                       01 vol+, 02 vol−, 08 play/pause
```

**SETs are not acknowledged.** None of the SETs returns a `0x0C` report. Read the matching GET
afterwards to confirm a write (the driver does that).

## Opcodes (validated)

| Op | Kind | What | On hardware |
|---|---|---|---|
| `02` | GET | headset ↔ dongle link | `02` = connected ✔ |
| `01`/`04` | SET/GET | microphone mute | ✔, also raises event 3 |
| `06` | GET | battery | byte 6 = %, **bytes 7–8 = millivolts, big endian** (`0F 51` = 3.921 V at 74%) ✔ *new* |
| `48` | GET | charging | 0 discharging, 1 charging, 2 full ✔ |
| `0B`/`14` | SET/GET | voice prompts | ✔ |
| `0D`/`16` | SET/GET | sidetone on/off | ✔, also raises event 5 |
| `44`/`45` | SET/GET | sidetone level | **int8 from −6 to +6**; the firmware clamps anything outside (tested −20…127) ✔ *new* |
| `46`/`47` | SET/GET | playback mute | ✔ |
| `4A`/`4B` | SET/GET | auto power-off in seconds, u16 BE | ✔; **accepts values other than 10/20/30 min** (45 min stuck and read back) *new* |
| `4D` | GET | color | 0 = black ✔ |
| `5F` | SET | EQ band: `band, gain_hi, gain_lo, depop` (hundredths of dB, int16 BE) | no GET; checked by ear |
| `49` | GET | information | `00 01 0C 0C 00 03 0F 00 "HP, Inc" 03 01 02 02`; format unknown |
| `43` | GET | microphone boom | `00` with the boom attached; meaning unconfirmed |
| `0F`/`1C` | SET/GET | onboard EQ slot | **does nothing on this firmware**: SET doesn't change the GET; after SET 6 the GET returns `FF` |

EQ bands: 32, 64, 125, 250, 500, 1k, 2k, 4k, 8k, 16k Hz; NGENUITY 3 offers ±8 dB. The `depop`
flag goes only on the last band packet when switching presets, not while dragging a slider.

## Events (report 0x0D)

| Type | What | Seen |
|---|---|---|
| 1 | battery (%) | — |
| 3 | microphone mute | ✔ `0D 02 03 00 03 01` |
| 5 | sidetone | ✔ `0D 02 03 00 05 01` |
| 10 | charging | — |
| 12 | headset link | — |

## Not possible

- **Active noise cancellation.** The headset firmware has no ANC module (see
  [cloud3s-firmware.md](cloud3s-firmware.md)), and doing it on the PC is impossible: the
  mic → 2.4 GHz → USB → PC → back path takes tens of ms, while ANC needs well under 1 ms.
- **DTS, "Audio Engine" noise suppression** are Windows-side audio processing, not headset settings.
- **Firmware update** is deliberately not implemented (Airoha FOTA can brick the headset).
