# The HP-era "Universal" protocol

Driver (transport only): `hyperx_linux/drivers/universal.py` · used by the Haste 2 / Saga Pro mouse
drivers, the Alloy Rise keyboards, the QuadCast 2 S and the Cloud Alpha 2 Wireless

"Universal" is the name of the protocol module in the NGENUITY 3.1 communication hub (`UniversalProtocol`).
Nearly every HP-era HyperX device that is not a Cloud III / Stinger 3 headset speaks it: mice, keyboards,
several headsets, microphones, the Instant Pair dongle and the Clutch Talon. The best public specification is
`docs/protocol/universal.md` of [ngenuity-linux-cli](https://github.com/PMarinov1994/ngenuity-linux-cli)
(MIT), confirmed on hardware for the Haste 2 Wireless; the NGENUITY analysis is in
[ngenuity-catalog.md](../ngenuity-catalog.md). Per-device pages describe the commands each device accepts.

## Dangerous commands: never send

These are implemented by the vendor software, but they erase user data, reset the device or touch
firmware. The shared transport never sends them and no driver should.

| Bytes | What it does |
|---|---|
| `10 02` | `DeviceFactoryReset` (hub name) |
| `12 01` | factory reset, as seen in community specifications and device tables |
| report ids `F0`, `FA`, `FC` (`F1`, `FD` are the matching input ids; the driver also refuses `30`, which is declared but absent from the hub tables) | probable firmware update channel; `FB` is **not** part of it, it carries events |
| `20 05` | reset general key assignments |
| `22 07` | reset macro assignments |
| `24 06 00 00 00 02` | reset key press and release settings |
| `26 05` | reset SOCD |
| `70 04` | put the 3-in-1 dongle in pairing mode |
| `70 07` | **clear the pairing information** of the 3-in-1 dongle |
| `36 03` | mouse sensor lift-off calibration |
| `08 AE 5E` | Emblems "enable mouse", part of that dongle's firmware update flow |
| `44 06 01` | flash read in a firmware region (read only, still avoid) |

Also avoid, because they write flash: slot 1 writes in a loop (see slots), `42 02 02 00 06` (commit of
button colours on the Alpha 2), and anything on a bootloader/DFU endpoint (the catalog never opens those).
The bit `InitiateReprogrammer` in the device information announces a reprogramming mode; no dedicated
command was found in the hub.

Some product-specific protocols (Cloud III S, Stinger 3, Cloud III Wireless, Cloud III, Realtek) treat
"factory reset" as a no-op; only Universal devices actually implement it.

## Framing

Every request is a 64-byte output report. The **report id is the command** (the "class"); `[1]` is the
sub-command; the payload starts at `[2]`, padded with zeros. Multi-byte integers are little-endian. On Linux
hidraw the buffer passed to `write()` is exactly these 64 bytes; `read()` returns 64 bytes that start with the
report id. The control interface is normally USB interface 2, vendor collection `0xFF00` (the descriptor
starts with `06 00 FF`). Exceptions: `0xFF13` on the Haste 2 Pro and Saga Pro cable, `0xFF90/0xFF00` on
many keyboards and newer mice, interface 3 on the Saga Pro dongle. Find the node from the descriptor, not
from a fixed interface number. The hub's product table does not store interface numbers.

| Item | Layout |
|---|---|
| Request | `[0]` cmd, `[1]` sub, `[2..]` payload |
| Read reply | input report `cmd+1`, same sub in `[1]` |
| ACK | report `FF`: `FF 01 <12-byte device id> <cmd> <sub> <status>`; device id at `[2..13]`, cmd at `[14]`, sub at `[15]`, status at `[16]` (0 = accepted, 1 = rejected) |
| Event | report `FB`: `FB <type> ...` |
| NACK | the HeadsetControl project treats `FF 02 ...` as a NACK; the transport here only recognises `FF 01` |

- **Every** request gets an ACK, reads and writes alike. Writes get nothing else. Through a dongle two ACKs
  can arrive, one from the dongle and one from the device. On the QuadCast 2 S the device id is all zeros.
- **Match replies by `[0]` (and `[1]`), never by searching the buffer.** ACKs carry the command in
  `[14..15]`, so a search for `51 02` finds an ACK for a battery request and reads a bogus "0 %, charging".
- The driver's read helper accepts a reply whose `[0]` is `cmd+1` and `[1]` equals the sub; the write
  helper waits for `FF 01` with `[14]`=cmd, `[15]`=sub and succeeds only when `[16]` is 0.
- Declared report ids (output and feature): `10 12 14 20 22 30 32 36 40 42 44 50 52 60 62 F0 FA FC`; input
  ids `11 13 15 21 23 31 33 37 41 43 45 51 53 61 F1 FB FD FF`. Tools use output reports only; nobody has used
  the feature variants.
- While NGENUITY runs it polls the same interface (~75 times a second on the Alpha 2). Discard anything
  that is not yours.

### Events (`FB`)

| Packet | Meaning |
|---|---|
| `FB 0A <0/1>` | link to the device lost (0) or restored (1); the driver watches type `0x0A` |
| `FB 08 <stage> <DPI code u16>` | DPI stage changed by the button |
| `FB 01 <button> 00 <0/1>` | button released or pressed (`0x20` = DPI button) |
| `FB 13 00 <%>` | battery level changed (one headset source) |
| `45 xx` | notifications; ignore |

## Slots

For write commands the profile slot is a u16 at `[2..3]`. Read commands take a single slot byte at `[2]`.

- **Slot 0 is RAM**: live, lost at power-off. Use it for everything the app applies.
- **Slot 1 is the onboard profile in flash**: NGENUITY's "Save", loaded into slot 0 at power-up. Flash has a
  finite write life; never write slot 1 in a loop or on every slider move.

## Command classes

Initial bytes come from static analysis of the hub (`generate_command` of each message). The sub is
`01` for set/configure and `02` for get/information unless noted. Argument layouts are only known for the
commands used by the drivers; the rest were not extracted.

| Class | Commands |
|---|---|
| `10` device | `10 01` DeviceInformation; `10 02` factory reset (dangerous) |
| `14` profile | `14 01` select current profile; `14 02` read it |
| `20` key assignment | `20 01` key definition; `20 03` total data pages; `20 04` settings info; `20 05` reset (dangerous) |
| `22` macros | `22 01` setup; `22 02` group configuration; `22 03` action data; `22 04` total groups; `22 05` group info; `22 06` action data info; `22 07` reset (dangerous) |
| `24` key press/release | `24 0x` setup; `24 06` reset (dangerous) |
| `26` SOCD | `26 0x` setup; `26 03` data pages; `26 04` info; `26 05` reset (dangerous) |
| `32` DPI | `32 01` set; `32 02` read |
| `36` sensor | `36 01` / `36 02` additional customisation; `36 03` lift calibration (dangerous); `36 04` calibration status |
| `40` LED brightness | `40 01` set (`[2..3]` profile, `[4]` 0-255); `40 02` read, reply `41 02 <level>` |
| `42` preset lighting | `42 02` set (`[4]` mode: 0 off, 1 solid, 2 breathing, 6 frame light; `[5..6]` duration ms); `42 03` read |
| `44` direct/frame lighting | `44 01` frame header (`[2]` = number of data packets); `44 02` frame data (`[2]` index, RGB triplets from `[4]`); `44 03`-`44 06` stored frames (flash) |
| `46` ambient/misc light | `46 03` ambient config; `46 04` status; `46 05` enable set; `46 06` enable read |
| `50` battery | `50 01` configuration; `50 02` read, reply `51 02` |
| `52` link | `52 01` read, reply `53 01 <1 = linked>` |
| `54` sleep time | `54 01` set; `54 02` read |
| `60` generic audio | `60 01` set; `60 02` read, reply `61 02 ...` |
| `62` prompt sound | `62 01` / `62 02` |
| `66` onboard EQ | `66 01` set; `66 02` read |
| `70` 3-in-1 dongle | `70 02` mode status; `70 04` and `70 07` are dangerous |
| `80`-`86` gamepad | `80 01` info; `82 0x` trigger dead zone; `84 0x` thumbsticks; `86 0x` vibration; `80 FF` input notifications |

In Universal devices the audio commands of the hub's generic trait (input level, polar pattern, monitoring)
are **not** implemented; audio goes through `60`, `62` and `66`. The QuadCast 2 S audio side uses a
separate Realtek protocol on report `77`.

### Battery reply

`51 02 <%> <state> <temperature i16> <millivolts u16> <gauge chip> <charger chip>`: state 0 on battery, 1
charging, 2 full; the notes also list 3 = error and `FF` = unknown, which the driver does not decode (any
other value is shown as neither charging nor full). Example: `51 02 5D 00 19 00 61 10` is 93 %, 25 C,
4193 mV. The driver reads the voltage only when it is between 2.5 and 5 V. One headset tool derives
"charging" from bit 7 of byte 6, which is the low byte of the voltage; use the state byte.

## Device information (`10 01`)

The feature set of a Universal device is **reported by the device**, not hard-coded. The hub reads the raw
64-byte reply of `10 01`: byte `0x38` = SupportFeaturesA, `0x39` = B, `0x3A` = C. Other bytes (`0x31`,
`0x35`, `0x3B`, `0x3D`, pairs at `0x1F..0x30`, probably versions) are read without a known meaning. The
byte positions are given as the hub reads them; whether they count the report id has not been confirmed on
hardware.

| Byte | Bits |
|---|---|
| A | 0x01 general key assignment, 0x02 macros, 0x04 game mode, 0x08 DPI, 0x10 function lock, 0x20 LED brightness, 0x40 preset lighting, 0x80 direct lighting |
| B | 0x01 LED sleep, 0x02 sensor extras, **0x04 initiate reprogrammer**, 0x08 notification commands, 0x10 wireless RF, 0x20 general audio, 0x40 advanced audio, 0x80 ambient light |
| C | 0x01 AAA battery, 0x02 rapid trigger, 0x04 3-in-1 dongle commands, 0x08 SOCD, 0x10 vibration level, 0x20 dead zone, 0x40 audio feature, 0x80 multi-PID |
| audio L (reply to `60 02`) | 0x01 microphone, 0x02 polar pattern, 0x04 global filters, 0x08 sidetone, 0x10 balance, 0x20 chat mix, 0x40 playback, 0x80 onboard mic EQ |
| audio H | 0x01 onboard playback EQ, 0x02 reverse mute/unmute lighting |
| gamepad A | 0x01 thumbstick mode, 0x02 dead zone, 0x04 output curve, 0x08 trigger lock, 0x10 trigger dead zone, 0x20 vibration, 0x40 remapping |

The hub also applies per-product overrides (audio, light, non-light, Clutch Talon, SoloCast 2) whose
content was not extracted.

## Pacing

- The vendor software waits at least 10 ms between packets.
- **Through a receiver or dongle, send one request at a time and wait for the device's reply (`cmd+1`)
  before the next.** Otherwise packets are lost over RF. A command sent while the device sleeps is queued by
  the dongle and delivered when it wakes.
- Live lighting (`44 01` / `44 02`) is not persistent: repeat the frame, about every 45 ms while animating,
  keepalive at 200 ms or less while static. When frames stop, the device falls back to its stored state.
- A device that stops being read can stop accepting writes on some platforms; keep draining the input side.

## Drivers and the protocol

The transport class `UniversalDevice` builds the 64-byte packets, issues reads and writes through the HID node's
`request()` (one in flight at a time) and decodes the link (`52 01`, byte `[2]` = 1) and the battery
(`50 02`). Its module docstring lists the commands it never sends (`10 02`, `12 01`, `30`, `F0`, `FA`, `FC`,
slot 1 loops, `70 04`, `70 07`).

## Sources

| Source | License |
|---|---|
| [PMarinov1994/ngenuity-linux-cli](https://github.com/PMarinov1994/ngenuity-linux-cli) `docs/protocol/universal.md` | MIT |
| NGENUITY 3.1 hub, static analysis (see [ngenuity-catalog.md](../ngenuity-catalog.md)) | facts only |
| [HeadsetControl](https://github.com/Sapd/HeadsetControl) PR 590 (Cloud Alpha 2 Wireless) | GPL-3.0 |
| [peroxy/hyperx-cloud-alpha2-lightsout](https://github.com/peroxy/hyperx-cloud-alpha2-lightsout) | MIT |
| Lumen, hyperx-saga-control, hyperx_open_lighting (Haste 2, Saga Pro, Alloy Rise 75) | see each device page |
