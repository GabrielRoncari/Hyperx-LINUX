# Cloud III S Wireless firmware (Airoha AB157x) — reverse engineering notes

Done on 2026-10-24 to find out whether active noise cancellation could be added. Everything
here is **read-only**; nothing was written to the headset. Tools: `tools/cloud3s/`.

## Access

- The **dongle** (`03f0:02cc`) also exposes Airoha's RACE channel (usage page `0xFF13`,
  reports `0x06`/`0x07`) but does not answer any command in normal use.
- The **headset over USB-C** (`03f0:01cc`, bcdDevice 31.22) exposes HID only (no audio):
  page `0xFF13` = RACE (reports `0x06` out / `0x07` in, 61 bytes), page `0x01C1` = the HyperX
  protocol (`0x0C`/`0x0D`), plus telephony (report `0x05`).
- HID framing: `06 <len u16 LE> <RACE packet>`; replies arrive as `07 <len> <≤59 bytes>` forming
  a **byte stream** that must be reassembled (`tools/cloud3s/race.py`).
- RACE packet: `05 <type> <len u16 LE = 2 + payload> <id u16 LE> <payload>`; type `5A` request,
  `5B` response, `5D` indication.
- The channel also streams the **firmware debug log** (indication `0x5D`, id `0x0F92`, plain text:
  "LE connected, handle 0x0002", "Sink Status: STREAMING.").

## Identification (RACE `0x0301` / `0x1E08`)

```
SDK   IoT_SDK_for_BT_Audio_V5.0.0.AB157x_c120sp_6
board ab157x_evk
build 2025/12/19 16:18:16 GMT +08:00
relay (0x0D00): no destinations
```

## Flash layout (RACE `0x0403` storage page read, table at `0x08000000`)

| Address | Size | Type | Contents |
|---|---|---|---|
| `0x08003000` | 64 KiB | 3 | bootloader (ARM Thumb) |
| `0x08015000` | 1500 KiB | 6 | DSP firmware (Xtensa) |
| `0x0818C000` | 2296 KiB | 4 | main CM4 firmware (ARM Thumb, XIP) |
| `0x083CA000` | 128 KiB | 9 | NVDM (configuration NVKEYs) |
| `0x083EA000` | 800 KiB | 10 | ROFS (voice prompt .mp3 files) |
| `0x084B2000` | 3320 KiB | 7 | FOTA area (empty) |
| `0x087F0000` | 64 KiB | 15 | spare NVDM (empty) |

Dumps are not part of the repository (vendor firmware). To make your own:
`RACE_DEV=/dev/hidrawN python3 -m tools.cloud3s.race dump ADDR SIZE FILE`.

## NVDM

Item: `status pnum type ff offset(u16) group_len name_len size(u16) index(u16) seq(u32) hash(u32)`
+ `group\0` + `name\0` + value + checksum(u16). About 350 NVKEYs in group `AB15`, named after
their hex id (`tools/cloud3s/nvdm.py`).

Filter banks `E1C0`–`E1DB` (copy in `E8F4`–`E8F9`) come in L/R pairs: 3 blocks × (8-byte header +
9 biquads `b0 b1/2 b2 a1/2 a2` in Q31), Q15 gain in the header. `E1C2`/`E1C4` hold a block with
+28.9 dB of gain; at ~384 kHz that is a +22 to +28 dB band-pass between 100 and 500 Hz. That
shape fits an ANC or pass-through filter, but nothing uses it (see below).

## RACE "DSP realtime" dispatcher (CM4 `0x081D8A6C`): no ANC

The function reads the id at `[pkt+4]` and jumps through two tables (`0x0E01`–`0x0E12` at
`0x081D8AAC`, `0x0E20`–`0x0E30` at `0x081D8B08`). Supported ids tail-call their own handler; the
others fall into `0x081D8A94` (`return 0`, no response):

```
handled:     0E01 0E02 0E03 0E05 0E0B 0E0C 0E0D 0E10 0E12 0E20 0E21 0E27 0E29 0E2A 0E30
not handled: 0E04 0E06 0E07 0E08 0E09 0E0A 0E0E 0E0F 0E11 0E22–0E26 0E28 0E2B–0E2F
```

`0x0E06` is the Airoha SDK ANC command (on with `00 0A <filter>`, off with `00 0B`; confirmed on
another Airoha product, the JBL Tune 770NC). Here it **has no handler**. A full scan of the CM4
image (`tools/cloud3s/fwscan.py`) finds no instruction using `0x0E06`, no other dispatcher for
the `0x0E00` range, and no string about ANC, pass-through or ambient mode. The DSP links no ANC
library either: its algorithm table lists AAC, SBC/mSBC, LC3plus, PEQ, compander, ECNR (echo and
noise reduction **for the microphone**), wind detection, PLC and skew control.

**Conclusion:** the ANC control path was compiled out of this firmware. Adding it would mean
writing the AB157x ANC engine driver without the SDK and reflashing a signed image, with a real
risk of bricking, and the headset would still lack ANC-placed microphones and acoustic calibration.
