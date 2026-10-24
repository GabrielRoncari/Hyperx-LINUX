# HyperX keyboards — HID protocol

Driver: `hyperx_linux/drivers/keyboards.py` (family D transport: `hyperx_linux/drivers/universal.py`)
· support level: **community** for every model except the Alloy Rise (**experimental**)

Compiled on 2026-10-24 from public reverse engineering only: OpenRGB drivers and wiki, SignalRGB
plugins, several small open-source projects, and passive analysis of USB captures that users attached to
public OpenRGB issues (NGENUITY running on real hardware). **No keyboard was opened while writing this
document or the driver.** Nothing here has been re-validated on hardware by this project.

## What the driver does

- One static colour for the whole keyboard, plus brightness. Nothing else.
- Every keyboard falls back to its onboard profile when the host stops sending frames, so the driver
  re-sends the last frame every 0.2 s (`keepalive_seconds`) while the app runs, and only after the user
  picked a colour.
- Brightness is a hardware command on families C and D. On families A and B no brightness command is
  known, so the driver scales the RGB values (software brightness).
- **Nothing is written to the onboard profiles.** Profile/effect/keymap/macro commands, factory resets
  and firmware commands are never sent (see each "Avoid" list). Family E is not implemented because every
  change writes flash.
- Not available for any keyboard: **game mode** (Windows-key lock), **polling rate** and **battery**.
  No source documents a host command for them. Game mode is a physical key handled by firmware (the
  Elite RGB stores what it blocks inside the profile); the Mars "gaming mode" is a Windows keyboard hook
  in the vendor software. Polling-rate and battery commands exist only for the mouse families.

Conventions: `buf[n]` is the byte index in the buffer handed to hidraw (`buf[0]` is the report ID, `00`
when the descriptor declares none). Feature report = `HIDIOCSFEATURE`, output report = `write()`.
`rep[n]` is the index in a report read from hidraw.

## Families at a glance

| Family | Models | Transport | Colour layout |
|---|---|---|---|
| A | Alloy Elite RGB, Alloy FPS RGB | feature report `07`, 264 B, interface 2 (UP `FF01`) | planar, one packet per channel |
| B | Alloy Origins, Alloy Elite 2, Alloy Origins 60, Alloy Origins 65 | feature report, no ID, 65 B, **interface 0 on Linux** | `04 F2` init + packets of 16 x `81 R G B` |
| C | Alloy Origins Core | output report, no ID, 64 B, interface 2 (UP `FF13`) | planar GRB, 380 B in 7 `A2` chunks |
| D | Alloy Rise, Alloy Rise 75, Origins 2 65, Eve 1800 | output report, ID = command, 64 B | `44 01` header + `44 02` blocks of 20 x RGB |
| E | Alloy MKW100, "Mars Gaming Keyboard" | feature report, no ID, 64 B, interface 0 | whole lighting block written to flash — **not implemented** |

No public protocol exists for the Alloy Core RGB (`0951:16DD`), Alloy FPS Pro (`0951:16D2`), Alloy
Elite without RGB (`0951:16BF`; its usage pages differ from the Elite RGB, so do not reuse family A) and
the Alloy Rise 75 Wireless (`03F0:01B9`, `03F0:0EB8`; the hypothesis that it speaks family D is
unconfirmed). These are not supported and must not be probed.

## Bootloader / DFU PIDs — never open

Taken from the NGENUITY 2.38 device catalogue (lowerx project). The driver and the udev rules ignore
them; do not add them anywhere.

| Model | DFU PIDs |
|---|---|
| Alloy Elite 2 | `0951:1712`, `03F0:068F` |
| Alloy Origins | `0951:16F5`, `03F0:0691` |
| Alloy Origins 60 | `0951:1735`, `03F0:0D8E` |
| Alloy Origins 65 | `03F0:048F` |
| Alloy Origins Core | `0951:16F6`, `03F0:0A8F` |
| Alloy Rise | `03F0:01A1` |
| Alloy Rise 75 | `03F0:03A1` |
| Alloy Rise 75 Wireless | `03F0:02B9`, `03F0:0FB8` |

## Family A — Alloy Elite RGB / Alloy FPS RGB

| Model | USB ID |
|---|---|
| HyperX Alloy Elite RGB (ANSI and ISO share the PID) | `0951:16BE` |
| HyperX Alloy FPS RGB | `0951:16DC` |

- Interface 2, usage page `0xFF01`, usage 1. Feature report ID `07`, 264 bytes including the ID. The
  driver matches the interface by the `FF01` page and a feature size of 263 bytes in the descriptor
  (descriptor sizes exclude the ID).
- Works on Linux through the normal hidraw node of interface 2. No response is used by any source.
  (The FPS RGB answers on interrupt IN `0x83`; format unconfirmed.)

Command table (`buf[0]` = `07`):

| Command | Bytes | Effect |
|---|---|---|
| Direct colour, volatile | `07 16 CC A0`, intensity at each key's offset, rest `00` | `CC` = `01` R, `02` G, `03` B, `04` extended (light bar + media keys, Elite RGB only) |
| Profile colour | `07 06 PP CC` + same offsets | **writes the profile** |
| Hardware effect | `07 02 PP …` (wave/static/breathing, speed, colour mode) | **writes the profile**; users report brightness dropping to 0 afterwards |
| Select profile | `07 81 PP` | `PP` 1-3 profiles, 4 internal, **5 = factory reset (FPS RGB)** |
| Profile + brightness | `07 01 PP 00 00 00 BB 01` | `BB` 0-3 per the OpenRGB wiki (the FPS RGB capture uses 4); unknown whether it stores |

Static colour for the whole keyboard (what the driver sends): packets for channels 1, 2, 3 (R, G, B) with
5 ms between them, then channel 4 on the Elite RGB. Every buffer is zeroed first, so bytes without an LED
stay `00` (OpenRGB leaves stale memory in channel 4). The driver repeats this every 0.2 s.

- **Key offsets** (identical in channels 1-3; 106 keys; ANSI and ISO positions both present). The driver
  writes the same value at all of them, so only the set matters:
  `08-0E 0F-17` (consecutive `08`...`17`), `18-1E`, `20-24`, `26-2F`, `30-34`, `37-3C`, `3E 3F`, `41`,
  `44 45`, `48-4F`, `51`, `54 55`, `58-5C`, `5E 5F`, `61`, `64 65`, `68-6C`, `6E 6F`, `74 75`, `78-7F`,
  `81`, `84 85`, `88-8F`, `91`, `94 95`.
  Examples: Esc `08`, `` ` `` `09`, Tab `0A`, Space `4D`, ANSI Enter `26`, ISO Enter `16`, KP Enter `94`.
  The per-key table (OpenRGB) lists the exact key at each offset; it is not repeated here.
- **Channel 4** (Elite RGB only, 22 LEDs: 18 light-bar LEDs + 4 media keys), one `R/G/B` offset triple
  per LED:

  | LED | R/G/B | LED | R/G/B | LED | R/G/B |
  |---|---|---|---|---|---|
  | bar 1 | `08/29/39` | bar 9 | `8B/7B/6B` | bar 17 | `0F/1F/2F` |
  | bar 2 | `48/28/38` | bar 10 | `0C/1C/2C` | bar 18 | `4F/6F/5F` |
  | bar 3 | `88/78/68` | bar 11 | `8C/7C/6C` | media previous | `92/82/72` |
  | bar 4 | `09/19/3A` | bar 12 | `0D/1D/2D` | media play | `13/23/33` |
  | bar 5 | `89/79/69` | bar 13 | `8D/7D/6D` | media next | `93/83/73` |
  | bar 6 | `0A/1A/2A` | bar 14 | `0E/1E/2E` | media mute | `12/22/32` |
  | bar 7 | `8A/7A/6A` | bar 15 | `8F/6E/5E` | | |
  | bar 8 | `0B/1B/2B` | bar 16 | `8E/7E/5D` | | |

  Total 106 + 18 + 4 = 128 LEDs on the Elite RGB; the FPS RGB has the 106 keys only and no channel 4.
- Channel-4 byte 3: OpenRGB sends `A0`, SignalRGB sends `0A`; both are reported to work. The driver sends
  `A0`.
- Keep-alive: the research says to resend at least every 50 ms; the driver resends every 0.2 s (see
  "Inconsistencies").

Confidence: **high** for direct colour (OpenRGB since 2020, SignalRGB plugin, Linux users in OpenRGB
#2058; Grabulosaure reproduced an NGENUITY capture on the FPS RGB with libusb). Effects and brightness:
partial, derived from NGENUITY captures.

Avoid: `07 02` and `07 06` (write the profile), `07 81 05` (factory reset), `07 03` (per-layer keymap),
`07 17 01` / `07 17 00` (open/close NGENUITY's save session).

## Family B — Alloy Origins / Elite 2 / Origins 60 / Origins 65

| Model | USB ID | Packets | Slots |
|---|---|---|---|
| HyperX Alloy Origins (ANSI, ISO, ABNT2 share the PID) | `0951:16E5`, `03F0:0591` | 9 | 144 (126 used, 107 lit) |
| HyperX Alloy Elite 2 | `0951:1711`, `03F0:058F` | 9 | 144 (128 lit) |
| HyperX Alloy Origins 60 | `0951:1734`, `03F0:0C8E` | 5 | 80 (63 lit) |
| HyperX Alloy Origins 65 | `03F0:038F` | 5 | 80 (69 lit) |

`03F0:0591` is the HP-era PID (also appears after a factory reset, OpenRGB #2771). Treat both Origins
PIDs alike.

> **Security note — interface 0 is the keyboard's boot interface.** The vendor interface (interface 3,
> usage page `0xFF90`, 64-byte reports) is where these commands live on Windows, but on Linux it gets no
> driver and therefore no hidraw node. The only node that accepts the feature report is the hidraw node of
> **interface 0**, the standard boot keyboard. Granting the user access to it (a udev `uaccess` rule, as
> the shipped rules do) also lets any process of that user **read raw key presses from that keyboard**
> through the same node. Interfaces 1 and 2 reject the report (`EPIPE`). OpenRGB makes the same trade-off
> on Linux. Install the rule only if you accept that.

- Transport: `HIDIOCSFEATURE(65)` with `buf[0] = 00`. No response is readable through interface 0.
- Command table:

| Command | Bytes |
|---|---|
| Direct-mode init | `buf[1..2] = 04 F2`, `buf[9] = N` (colour packets that follow), rest `00` |
| Colour packet | for slot `i` = 0..15: `buf[1+4i]=81`, `buf[2+4i]=R`, `buf[3+4i]=G`, `buf[4+4i]=B` |

  `N` varies between sources (`09` Origins, `05` Origins 60/65, `00` OpenRGB Elite 2, absent in some
  SignalRGB/kacper variants); the keyboards accept all of them. The driver sends `N` = packet count
  (9 or 5). OpenRGB's wiki and the kacper project document `04 02` plus marker `08`; working code,
  including kacper's own, uses `04 F2` and `81`.
- Sequence: init, then `packets` colour packets, repeated for every frame. Send the init **before each
  frame** (a report says that with init only at start-up the keyboard reverts). Slots listed below are
  sent as `00 00 00` (`81` marker kept).
- Empty slots (no LED; the driver leaves them black), as implemented:
  - Origins: `23 29 41 47 59 70 71 87 88 93 99 100 102 108 113 114 120 123 124` plus `126-143`
    (the ninth packet carries no LEDs; OpenRGB sends a single black slot there, the driver 16).
  - Elite 2: `23 29 41 47 70 71 76 77 87 88 93 99 100 102 108 113`. Slots `126-143` are the 18 light-bar
    LEDs and `114 120 123 124` are the media keys, all lit.
  - Origins 60: `0 14 42 45 56 67 68 69` and `71-79`; slot `70` is Fn.
  - Origins 65: `0 14 42 45 56 65 66 67` and `77-79`; slot `68` is Fn.
- Slot order is column-major from Esc: first column Esc/`` ` ``/Tab/Caps/LShift/LCtrl/ISO `\`, then
  1/Q/A/Z/LWin... The Origins ABNT2 extra key sits at slot `76` (lit), Menu at `77`; on the Elite 2 slots
  `76-77` are empty. Per-key names are in the OpenRGB sources and are not needed for a uniform colour.
- Keep-alive: sources disagree. alloy-ripple (`0951:16E5`, macOS) says the keyboard forgets in under 1 s
  and sends every 25 ms; hyperx-studio (`03F0:0591`, Linux) says the last frame persists until reboot.
  OpenRGB resends every 50 ms (Elite 2: 1 s). The driver resends every 0.2 s.
- Suspend: hyperx-studio observed that an Origins left in direct mode without frames stops signalling
  remote wakeup (the PC no longer wakes from that keyboard or a mouse on the same controller). Stop
  streaming and release the device before suspend.
- Brightness: **no confirmed command.** kacper's PoC defines `04 57` / `04 02` packets but never calls
  them; `04 02` is a commit in the Sonix family and may write flash. The driver uses software brightness.

Confidence: **high** for Origins (OpenRGB, hyperx-studio on Linux, alloy-ripple, kacper), Elite 2 (OpenRGB
MR!417/!427, SignalRGB) and Origins 60 (OpenRGB, hyperrust); **medium-high** for Origins 65 (OpenRGB
MR!1739, keyboard-visualizer on Linux).

Avoid: sweeping bytes 0/1 or any other `04 xx` (the space includes the bootloader; hyperx-studio found a
`FWUpdater.dll` and firmware images in the NGENUITY package), `04 57` and `04 02`, opening any DFU PID,
and factory-resetting as a "repair".

## Family C — Alloy Origins Core

| Model | USB ID |
|---|---|
| HyperX Alloy Origins Core (ANSI `09`, ABNT2 `10` layout byte) | `0951:16E6`, `03F0:098F` |

- Interface 2, usage page `0xFF13`, 64-byte reports **without** report ID. The driver matches the `FF13`
  page and a 64-byte output report. hidraw works on Linux.
- Output reports are written as `00` + 64 bytes: `buf[1]` command, `buf[2]` chunk/index, `buf[3]` `00`,
  `buf[4]` payload length, `buf[5..]` payload. Replies arrive as input reports without an ID byte:
  `rep[0]` echoes the opcode, `rep[3]` length, `rep[4..]` payload. Status payload `EC AC` = OK, `EC 00`
  = unsupported, `EC 01` = bad parameter. `A4` and `A6` never answer. Unsolicited notifications `70`
  (profile key), `71`, `73` (Fn layer usage press/release) must be filtered by opcode.

| Opcode | Meaning | Used |
|---|---|---|
| `10` | info: firmware at `rep[4..5]` (21.08 seen), ASCII name, layout at `rep[56]` | no |
| `27` | read brightness, `rep[4]` = 0-255 | yes (at refresh) |
| `A7` | set brightness: `buf[4]=01`, `buf[5]=BB` (0-255) | yes |
| `A2` | live colour chunk, volatile | yes |
| `15` / `95` | read / set active profile (1-3) | no |

- Colour stream: a 380-byte buffer sent as 7 `A2` chunks (chunks 0-5 carry 60 bytes, chunk 6 carries 20,
  length byte `3C` / `14`). Layout is **planar GRB**: for LED index `idx` (0-93),
  `pos = (idx / 12) * 48 + ((idx / 6) mod 2) * 8 + idx mod 6` (integer division), green at `pos`, red at
  `pos + 16`, blue at `pos + 32`. The matrix is scanned left half first (0-47), then right (48-93).
  The driver fills all 94 indices with the same colour, including the ones that are dead on ANSI
  (`34 44 46 47 77 83 93`), which is harmless. SignalRGB sends 384 bytes (24 in the last chunk); no effect.
- Keep-alive: the keyboard returns to its profile "a few seconds" after the last frame (hxoctkl: 10 ms is
  comfortable); the driver resends every 0.2 s, with 2 ms between chunks.
- Brightness: 0-255 per hxoctkl and OpenRGB; hyperx-macos limits it to 0-100. The driver maps 0-100 % to
  0-255. Whether `A7` persists across power cycles is not confirmed.

Confidence: **high** (hxoctkl on Linux with fw 21.08, OpenRGB incl. ABNT2, hyperx-macos).

Avoid: `A3` (commits the live buffer to a profile in flash), `A4` / `A5` (animation upload), `A0`, `B0`
(780-byte store; the SignalRGB plugin's initialiser sends it 13 times, do not copy), `93` / `94`, `30`
without parameters (crashes the firmware and re-enumerates the USB device), and opcode sweeps.

## Family D — Alloy Rise / Rise 75 / Origins 2 65 / Eve 1800

| Model | USB ID | Interface | Blocks | LEDs |
|---|---|---|---|---|
| HyperX Alloy Rise (**experimental**) | `03F0:0FA0` | 2 | 7 | 130 |
| HyperX Alloy Rise 75 | `03F0:02A1` | 2 | 6 | 103 |
| HyperX Origins 2 65 | `03F0:0CC2` | 3 | 4 | 80 slots (65 lit on the ANSI capture) |
| HyperX Eve 1800 | `03F0:08C2` | 2 | 1 (header says 4) | 10 zones |

This is the HP-era "Universal" protocol shared with the mice and headsets; the transport (64-byte output
report whose report ID is the command, acknowledgement `FF 01 <12-byte device id> <cmd> <sub> <status>`,
reads answered by report `cmd+1`) is implemented in `universal.py`. Interface 2 (UP `0xFF90`, EP `0x83`
IN / `0x04` OUT, 64 B) on the Rise and Rise 75; interface 3 on the Origins 2 65 (hidraw exists on
Linux). Spontaneous `FB …` reports are key presses: discard them and never log them.

| Command | Bytes | Notes |
|---|---|---|
| Info | `10 01` -> `11 01`: VID `[35..36]`, DFU PID `[37..38]`, PID `[41..42]`, firmware `[43..44]`, layout `[52]`, LED count `[54]` (`0x82`=130 Rise, 103 Rise 75) | not sent by the driver |
| Brightness, volatile | `40 01 00 00 BB`, `BB` 0-255 | ACK. `buf[2..3]` is a profile mask, always `00` |
| Read brightness | `40 02` -> `41 02 BB` | confirmed on the Rise 75 |
| Frame header | `44 01 NN 00` | `NN` = number of blocks |
| Colour block | `44 02 CC 00` + 20 x `R G B` (60 B) | `CC` 0..NN-1; answered by ACK and `45 02 CC` |

- Static colour: header, then every block filled with the same RGB, 2 ms between packets, repeated every
  0.2 s (NGENUITY streams about 20 frames/s). Gaps over about 5 s make the Rise 75 alternate with its
  onboard lighting; continuous streaming fixed it (700 frames in 35 s, longest gap 51.9 ms).
- Block counts: Rise 7 (130 LEDs), Rise 75 6 (103 LEDs), Origins 2 65 4 (80 slots). Slots beyond the LED
  count are sent with the same colour; no side effect is known.
- Eve 1800: one block of 10 zones (`44 02 00 00` + 10 x RGB); OpenRGB's header says `04` blocks although
  only one follows. The driver reproduces that (header 4, 1 block) because it is what works in hardware;
  the research suggests trying `44 01 01 00`, which is untested.
- Origins 2 65: OpenRGB sends the header before the blocks; the NGENUITY capture (PlasmaNGenuity) sends
  it after. Indistinguishable in a continuous stream; the driver sends it first.
- Write size: OpenRGB writes 65 bytes (one extra zero), NGENUITY and the other projects write 64. The
  driver writes 64.
- Rise 75 slot map (for a future per-key mode; not needed for one colour): Esc `0`, F1-F12 `1-12`, `` ` ``
  `14`, ... Space `80`, light bar interleaved in `79 81 89-102`. Unlit slots: `27 57 61 72 78 82 83`.
  Rise gaps: `32 54 91 101 105 106`, side bars `116-129` (+ `102 104`).

Confidence: Rise 75 **high** (hyperx_open_lighting, firmware 21.10, Linux; packet layout from static
analysis of NGENUITY 2.38). Origins 2 65 **medium-high** (OpenRGB MR!3239; PlasmaNGenuity bytes checked
against an NGENUITY 2.1.3 capture). Eve 1800 **medium** (one author, OpenRGB MR!3321). Rise **medium-low**
(NGENUITY captures only, OpenRGB #4480; same frames as the Rise 75). Brightness is confirmed on the Rise
and Rise 75 only; on the Origins 2 65 it is inferred from the family and on the Eve 1800 OpenRGB sends it
without reading an answer.

Avoid (all write flash or break state): any command with a **profile mask other than `00`**, in
particular the NGENUITY save sequence `30 01`, `40 01 MM MM`, `44 03` / `44 04` (stored frame),
`42 02`, `20 05 MM MM`, `22 07 MM MM`; `20 05` / `22 07` even with mask `00` clear the active remaps and
macros; `20 xx` key remaps and `22 xx` macros are volatile but are not touched by this driver; report IDs
`F0` / `FA` / `FC` (firmware), `10 02` / `12 01` (factory reset), `70 04` / `70 07` (pairing); never open
the DFU PIDs. Unstable Ctrl/Shift after setup was reported once and cleared on replug; do not "fix" it
with a reset or flash.

## Family E — Sonix MKW100 / "Mars Gaming Keyboard" (not implemented)

| Model | USB ID |
|---|---|
| HyperX Alloy MKW100 | `03F0:0B8F`, `03F0:0C8F`, `0951:1756` |
| HyperX "Mars Gaming Keyboard" (Sonix, fw 1.00) | `0951:16C6` |

- Interface 0 (boot keyboard) carries a 64-byte feature report without ID; sent with `SET_REPORT` then
  `GET_REPORT`; `rep[3] = 01` means accepted. The same protocol as the Mars, confirmed byte for byte on
  the MKW100 capture (OpenRGB #2759). The same security consideration as family B applies to interface 0.
- Commands: `04 E0` ready check; `04 0A 00 00 00 00 00 00 0F 00` followed by 15 packets of 64 B writes a
  960-byte lighting block **to flash**; `04 02` returns a 32-bit LE sum at `[4..7]` for verification.
- The block holds five 64-byte effect slots (`01` breathing, `03` spectrum, `04` static, `05` wave, `08`
  stack), 144 x `80 R G B` per-key entries and a tail (active mode, custom brightness 0-5, `AA 55`).
  Changing even a static colour means rewriting the whole block.
- Why it is left out: there is no volatile/direct mode; every change erases and rewrites flash. A tool
  that applies a colour on each slider move would wear it. Avoid `04 0A`, `04 08` (keymap), `04 0C`
  (macros) and `04 AB` / `04 11` / `04 12` / `04 13` (firmware updater).
- Confidence: high on the Mars (KeyGlow), medium on the MKW100 (captures only). No open implementation
  exists for the MKW100.

## Inconsistencies between the research notes and the driver

The driver wins in every case below.

- **Keep-alive period.** Family A re-sends every 50 ms (as OpenRGB does), families B and C every 100 ms
  (one source has an Origins forgetting the frame in under 1 s), family D every 200 ms. Untested on
  hardware; if a model flickers, shorten its `keepalive_seconds`.
- **Family A packet spacing.** 5 ms between channel packets on the Elite RGB, 10 ms on the FPS RGB (as in
  the FPS RGB capture).
- **Origins Core packet field order.** The notes' transport sentence puts the index at `buf[2]` and the
  chunk at `buf[3]`; the command table and the driver put the chunk at `buf[2]`, `00` at `buf[3]`. This
  document follows the driver.
- **Origins Core brightness.** The notes list the 0-255 versus 0-100 conflict; the driver uses 0-255.
- **Origins packet count.** The notes show 8 data packets plus one black slot (OpenRGB) or 8 packets
  (hyperx-studio); the driver always sends 9 full packets with `buf[9] = 9` and blacks slots 126-143.
- **Elite 2 `buf[9]`.** OpenRGB uses `00`; the driver sends `09` (SignalRGB's value), like the Origins.
- **Dead LEDs on the Origins Core.** The notes list indices dead on ANSI; the driver lights all 94.
- **Eve 1800 and Origins 2 65 brightness.** Every family D class sends brightness as `40 01` without waiting
  for an ACK, because only the Rise and Rise 75 were observed answering (the Eve 1800 source reads nothing).
- **Checked and consistent:** the 106 key offsets of family A match the notes exactly; the 22 channel-4
  offset triples match (18 bar + 4 media, no duplicate offsets); the family B empty-slot lists match the
  notes (Origins also blacks 126-143, see above); slot counts (107, 128, 63, 69 lit) are consistent.
- **Shared transport doc:** [universal.md](universal.md).

## Sources

| Source | Used for | Licence |
|---|---|---|
| OpenRGB, `Controllers/HyperXKeyboardController/*` and related controllers (https://gitlab.com/CalcProgrammer1/OpenRGB), merge requests !417, !427, !1465, !1617, !1739, !3239, !3321, issues #1899, #2058, #2186, #2746, #2759, #2771, #3074, #4480 | families A-D, slot maps | GPL-2.0-or-later (issue attachments: none declared) |
| OpenRGB Wiki, `Device-Documentation/HyperX-Alloy-Elite.md`, `HyperX-Alloy-Origins.md` | Elite effects, Origins notes | none declared |
| SignalRGB plugins, `Plugins/HyperX/*` (https://gitlab.com/signalrgb/signal-plugins) | cross-checks | none declared |
| Shehtman/hyperx-studio (https://github.com/Shehtman/hyperx-studio) | Origins on Linux, interface 0, suspend | MIT |
| aaliboyev/alloy-ripple (https://github.com/aaliboyev/alloy-ripple) | Origins keep-alive | MIT |
| kacper-serewis/hyperx-keyboard-rgb (https://github.com/kacper-serewis/hyperx-keyboard-rgb) | Origins brightness PoC | MIT |
| EriksRemess/hyperrust (https://github.com/EriksRemess/hyperrust) | Origins 60 | MIT |
| Atshemyan/keyboard-visualizer | Origins 65 on Linux | none declared |
| Grabulosaure/hyperx_alloy_fps_rgb (https://github.com/Grabulosaure/hyperx_alloy_fps_rgb) | FPS RGB captures | none declared |
| SimpleLed/Driver.HyperXAlloy.RGB | Elite RGB cross-check | none declared |
| identityapproved/hyperx-origins-core-tkl-rgb (`hxoctkl`, https://github.com/identityapproved/hyperx-origins-core-tkl-rgb) | Origins Core | GPL-2.0 (or later) |
| fsd-niraj/hyperx-macos (https://github.com/fsd-niraj/hyperx-macos) | Origins Core on macOS | ISC |
| ScottStaschke/PlasmaNGenuity-HyperX (https://github.com/ScottStaschke/PlasmaNGenuity-HyperX) | Origins 2 65, Universal protocol | MIT |
| abhinavpathak9873/hyperx_open_lighting (https://github.com/abhinavpathak9873/hyperx_open_lighting) | Rise 75 | MIT |
| kach4n/keyglow (https://github.com/kach4n/keyglow) | Mars / MKW100 (family E) | MIT |
| lbkeppler/lowerx, `DeviceCatalog.swift` (https://github.com/lbkeppler/lowerx) | DFU PID catalogue | none declared |
| linux-usb.org `usb.ids` | Alloy FPS Pro ID | GPL-2.0-or-later / BSD-3-Clause |

Licences marked "none declared" were used for facts only (offsets, byte values); no code was copied.
