# HyperX headsets — HID protocols (all models except Cloud III S Wireless)

Drivers: `hyperx_linux/drivers/headset_ffbb.py`, `headset_66.py`, `headset_21.py`, `headset_misc.py`,
and the Stinger 3 / MIX 2 classes at the end of `cloud3s.py` · support level: **community** or
**experimental** (see each section). The Cloud III S Wireless has its own page: [cloud3s.md](cloud3s.md).

Everything here comes from **reading the code and notes of other people's reverse engineering projects**
(research of 2026-10-24). No device was opened and no code from those projects was run or copied.
Only the Cloud III S Wireless was re-validated on hardware by this project. For every other model the
"confidence" lines say who confirmed what, and where.

Where this document and a driver differ, **the driver's behaviour wins** (clamped ranges, commands
deliberately not sent). Each section says so explicitly.

## Conventions

- Offsets start at 0 and **include the report-ID byte**, i.e. the buffer as hidraw `read()` returns it
  and as `write()` takes it. Bytes are hex.
- *Output* = `write()` on the hidraw node. *Feature* = `HIDIOCSFEATURE` / `HIDIOCGFEATURE`.
  *GET_INPUT* = `HIDIOCGINPUT`.
- "Collection X:Y" = usage page X, usage Y of the top-level collection. In a descriptor the page shows as
  `06 <lo> <hi>` (0xFF90 = `06 90 FF`, 0xFF13 = `06 13 FF`, 0xFF00 = `06 00 FF`, 0x01C0 = `06 C0 01`).
  Drivers pick the node by usage page and report ID, never by position.
- "Windows MI_03&Col0N" is the Windows HID path (interface 3, N-th collection); it is only a hint.
- Replies arrive as input reports on the interrupt endpoint and go to **every** open handle. With NGENUITY
  or another tool running, you will see their replies and they yours; match on the opcode and drop the rest.
- Several families answer **out of order**; match on the command, never on position.
- Pace requests (the drivers serialise them; community tools wait 50–120 ms, NGENUITY 3 at least 10 ms
  between Universal packets). Write bursts have destabilised dongles.
- With the headset off the dongle answers "not connected" or stays silent. Only the dongle knows the link.
- Do not trust `old_cloud_2_doc/Headset_protocol.md` in HyperHeadset (AI-generated from decompiled
  NGENUITY): its Cloud II Kingston part was validated, but its **Cloud Alpha Wireless and Cloud III
  Wireless tables are wrong**.

## Families at a glance

| Family | Request | Reply | Models |
|---|---|---|---|
| A. `06 FF BB` (HP) | out `06 FF BB <cmd> <arg>` | in `06 FF BB <cmd> …` | Cloud II Wireless (HP), Stinger 2 Wireless |
| B. Kingston 62-byte | out `06 00 02 00 9A 00 00 68 4A 8E 0A 00 00 00 BB <cmd> <arg>` | in `0B 00 BB <cmd> …` | Cloud II Wireless (Kingston), Cloud Flight S |
| C. `0x66` | out `66 <cmd> <arg>` | in `66 <cmd/event> …` | Cloud III Wireless, Cloud II Core Wireless |
| D. `21 BB` | out `21 BB <cmd> <arg>` | in `21 BB <cmd/event> <value>` | Cloud Alpha Wireless |
| E. `21 FF 05` | out `21 FF 05` | in, 20 bytes; events of 2 and 5 bytes | Cloud Flight Wireless |
| F. `0C 02 03` | out `0C 02 03 <rw> 00 <op> <args>` | in `0C 02 03 …`; event `0D 02 03 00 <type> <v>` | Cloud III S (own page), Stinger 3, MIX 2 |
| G. Universal | 64 bytes `<cmd> <sub> …` | in report `cmd+1`; ACK `FF 01`; notify `FB` | Cloud Alpha 2 Wireless, Cloud Flight 2, TIO receiver |
| H. Avnera | feature `FF 07 00 FD …` | GET_FEATURE `FF` | Stinger Core Wireless, Cloud Core Wireless |
| I. feature `0x20` | feature `20 <op> <v>` | none known | Cloud III (wired) |

What one model teaches about its family does not carry over byte for byte: opcodes and meanings differ
between models.

---

## 1. `06 FF BB` (HP) — Cloud II Wireless, Cloud Stinger 2 Wireless

Driver: `headset_ffbb.py` (`HPCloudII`) · **community**

| Model | USB IDs |
|---|---|
| Cloud II Wireless (HP) | `03F0:0696`, `03F0:018B` (rev. 2). `038B`/`058B` appear only in the NGENUITY 2.38 catalog, never reported by a user: not matched |
| Cloud Stinger 2 Wireless | `03F0:0D93` |

- HyperHeadset also lists `1718` with VID 03F0 in this family; that is the Kingston PID (family B) and is
  almost certainly a typo. Not matched.
- **Interface:** 3 (inferred from the Stinger 2 platform, `MI_03&Col03`), vendor collection **0xFF90:0x0303**,
  report ID `0x06`. The driver requires an output report 0x06 of at least 19 bytes (plus ID).
- **Packet:** output report of 20 bytes `06 FF BB <cmd> <arg>` zero-padded (other tools write 52 bytes; both
  work). No GET_INPUT needed. Reply: input report 0x06, 20 bytes, `06 FF BB <cmd> …`, ~50–100 ms later.
  SET replies echo the value in `[4]` and put `01` (success) in `[5]`.

| Feature | Request | Reply | Notes |
|---|---|---|---|
| link / power | `06 FF BB 01` | `[4]`: 1 or 4 on, 3 off | **never sent** (see Avoid) |
| battery | `06 FF BB 02` | `[7]` = %, `[5..6]` = mV u16 BE | e.g. `… 02 00 0E 98 1F` = 3736 mV, 31% |
| charging | `06 FF BB 03` | `[4]`: 0 no, 1 charging, 2 full, 3 error | |
| mic mute (read) | `06 FF BB 05` | `[4]` = 1 muted | Stinger 2: mechanical (boom up), no SET |
| sidetone on/off (read) | `06 FF BB 06` | `[4]` = 1 on | |
| auto-off (read) | `06 FF BB 07` | `[4]` = minutes, 0 = never | |
| mic attached | `06 FF BB 08` | `[4]` = 1 | HyperHeadset only |
| pairing info | `06 FF BB 09` | `[4]` opaque | meaning unknown |
| sidetone level (read) | `06 FF BB 0B` | `[4]` = int8 **dB** | |
| noise gate (read) | `06 FF BB 0D` | `[4]` (0 = on, per hsctl) | Stinger 2 only, hypothesis |
| mic mute (write) | `06 FF BB 20 <0/1>` | echo `06 FF BB 20 <v>` | Cloud II only |
| sidetone on/off | `06 FF BB 21 <0/1>` | echo, `[5]` = 1 | |
| auto-off | `06 FF BB 22 <min>` | echo, `[5]` = 1 | NGENUITY offers 0/10/20/30; HeadsetControl accepts 0–255 |
| sidetone level | `06 FF BB 23 <dB>` | echo `[4]` = level, `[5]` = 1 | int8 dB. **Stinger 2: factory −25 dB (`E7`); −12 dB (`F4`) tested; takes effect only when sidetone is switched on** |

**Events** (same layout as replies): `06 FF BB 20 <v>` mic moved or button pressed (1 = muted); echoes of
`21`/`22`/`23` reach every program when any of them writes; `06 FF BB 01 <s>` headset power.

**Confidence.** Cloud II (018B): LennardKittner ([HyperHeadset #13](https://github.com/LennardKittner/HyperHeadset/issues/13)),
wallasace (HeadsetControl [#574](https://github.com/Sapd/HeadsetControl/pull/574): battery, charging, voltage,
auto-off). 0696: Joaaoc (HeadsetControl #424/#436/#442/#448). Stinger 2: lbkeppler
([LowerX](https://github.com/lbkeppler/lowerx), macOS, "verified on the real device") and oauthul
([hsctl](https://github.com/oauthul/hsctl), Linux). The dB meaning of the level was measured **only on the
Stinger 2**.

**Driver.**
- Implements: battery (02 + 03), mic mute read (05, event 20; write 20 on the Cloud II only), sidetone
  on/off (06 / 21), auto-off (07 / 22, choice 0/10/20/30), sidetone level (0B / 23) **on the Stinger 2 only**.
- **Level is clamped to −30…0 dB** (the notes only say "never positive"; the lower bound is the driver's
  choice). On the Stinger 2, after writing a level while sidetone is on, the driver sends `21 00` then
  `21 01` so the level is applied.
- Leaves out: `01` (side effect), `08`, `09`, `0D`, level on the Cloud II (semantics not measured there),
  everything DTS.

**Avoid.**
- `06 FF BB 01`: works, but resets state (unmutes the mic). HyperHeadset disabled it. Use events and the
  battery reply for the link.
- Positive sidetone levels: +32 dB (`0x20`) was reported as deafening on the Stinger 2.
- Looking for 7.1/EQ opcodes: that is DTS processing on the PC.
- `21 BB 0E` (colour): reported not to work on this device.

## 2. Kingston 62-byte — Cloud II Wireless (Kingston), Cloud Flight S

Driver: `headset_ffbb.py` (`KingstonCloud`) · Cloud II Wireless (Kingston) **community**; Cloud Flight S
**experimental** (reads confirmed on hardware, the sidetone and auto-off writes are not)

| Model | USB IDs |
|---|---|
| Cloud II Wireless (Kingston, pre-HP) | `0951:1718`. `03F0:0C8A` (catalog only) and `0951:0B92` (unsourced) not matched |
| Cloud Flight S | `0951:16EA`, `0951:16EB` (seen in lsusb, not in the catalog) |

- **Interface:** Cloud II: interface 3 with two consumer (0x000C) collections and the vendor collection
  **0xFF13:0x0001**. Flight S: same vendor collection, Windows `MI_05&Col03` (interface 5), so the driver
  does not pin an interface for it; both match on usage page 0xFF13.
- **Report IDs:** out `0x06`; in `0x0B` (replies) and `0x0A` (audio/DSP state); Flight S also `0x02`.
- **Packet:** output report of 62 bytes, `[0..14]` fixed header ending in `BB`, `[15]` = cmd, `[16]` = arg.
  **Before every write do GET_INPUT(0x06)** and ignore the data; without it Linux returns `EPIPE`
  and one user got constant "strange sound" until re-plugging the dongle. On the Flight S the GET_INPUT
  fails but writing works anyway. Feature reports do **not** work (broken pipe). Replies are 64-byte
  `0B 00 BB <cmd> <data>`.

| Feature | Request (`…BB` = header) | Reply | Notes |
|---|---|---|---|
| link | `…BB 01` | `[4]`: 1 or 4 connected, 2 pairing (Flight S: 0/1) | **never sent** |
| battery | `…BB 02` | `[7]` = %; valid only if `[5]`,`[6]` are not both 0 | `[5..6]` probably mV, undocumented |
| charging | `…BB 03` | `[4]`: 0 no, 1 charging, 2 full, 3 error | |
| firmware | `…BB 11` | `[4..7]` = a.b.c.d | Cloud II only |
| auto-off (write) | `…BB 18 <min>` | none awaited | 0 = never; HeadsetControl caps at 30. The reply opcode is disputed (`18` vs `1A`) |
| sidetone on/off | `…BB 19 <0/1>` | `0B 00 BB 19 <state> 01` | no read command exists |
| auto-off (read) | `…BB 1A` | `[4]` = minutes | |
| init | `…BB 09`, `…BB 1D` | — | sent by NGENUITY on connect, purpose unknown |
| 7.1 / DSP state | `06 00 00 00 FF 00 00 68 4A 8E 00 …` (no `BB`) | input `0A 00 <dsp> 03 …`; `<dsp>` bit 0x02 = 7.1 on | read only (APO DTS on Windows) |

**Events.**
- `0B 00 BB 08 <0/1>`: mic mute by button (Cloud II). `0B 00 BB 04 …`: sporadic, ignored by NGENUITY.
- Flight S: `0B 00 BB 01 <0/1>` power (on: ask for the battery); `0B 00 BB 02/03 …` battery/charging.
- `0A 00 <surround> 03 <bits> 00 <game lvl> <game on> 00 00 <chat lvl> <chat on>`: `<surround>` 00/02,
  `<bits>` 0x02 = mic muted, 0x10 = sidetone on. `02 <v>`: volume buttons (01 up, 02 down, 00 release).

**Confidence.** Cloud II: fsvm88 ([HyperHeadset PR #14](https://github.com/LennardKittner/HyperHeadset/pull/14):
battery, charging, sidetone, auto-off, 7.1, firmware), MiniBossDK and Epzillon (issue #10), Phelete
(HeadsetControl [#519](https://github.com/Sapd/HeadsetControl/pull/519)). Flight S: kit93u and SimyriK
([HyperHeadset #18](https://github.com/LennardKittner/HyperHeadset/issues/18), reads: battery, mic, sidetone),
rum0r (16EB, #24), hahuk (gohyper, from USB captures), CubE135 (battery). **Writes on the Flight S
(sidetone, auto-off) were not explicitly reported working**; gohyper uses feature reports there, HyperHeadset
output reports, both reported OK for reads.

**Driver.**
- Implements: battery (02 + 03; both-zero `[5..6]` = headset off), auto-off read (1A) and write (18, then
  re-read), sidetone write (19, no wait, **no read-back**), mic mute from event `08` and from the Flight S
  `0A` bits (read-only), link from event `01`.
- The same four controls are offered on the Flight S as on the Cloud II, although Flight S writes are
  unconfirmed (see above).
- Leaves out: link `01`, firmware `11`, the `0A` 7.1 query, init `09`/`1D`, anything via feature reports.

**Avoid.** Writing without the preceding GET_INPUT; `01` (suspected to unmute the mic, issue #10); trying
to SET mute or 7.1 (no such command).

## 3. `0x66` — Cloud III Wireless, Cloud II Core Wireless

Driver: `headset_66.py` · **community**

| Model | USB IDs |
|---|---|
| Cloud III Wireless | `03F0:05B7`, `03F0:0C9D`, `03F0:0FCC` (alternative receiver). `06B7`/`0E9D` catalog only: not matched |
| Cloud II Core Wireless | `03F0:0995`, `03F0:069F`, `03F0:0795` ("second mode", same answers while charging) |

- `03F0:0AA0`/`099C` "HyperX Wireless Audio" (HP OMEN built-in receiver) does **not** answer this protocol.
- **Interface:** 3, vendor collection **0xFF13:0x0001** (confirmed for the III; probable for the II Core).
  Report ID `0x66`. The driver requires an output report 0x66 in the descriptor.
- **Packet:** output report `66 <cmd> <arg>` zero-padded to 62 bytes (NGENUITY capture; 64 also works).
  GETs have bit 7 set (`0x8x`), SETs are `0x0x`. Reply: input `66 <cmd> <data>`. On **Windows** some
  dongles accept only feature reports; on Linux `write()` works.

| Feature | GET / SET | Reply | Notes |
|---|---|---|---|
| device info | `66 81` | `66 81 9F 08 F0 03 02 31 00 "HP, Inc" "HyperX Cloud II Core Wireless"` | II Core; unknown |
| link | `66 82` | `[2]` = 1 connected | |
| SIRK | `66 83` | `[2..17]` = key | read only; all zero = needs reset |
| sidetone on/off | `66 84` / `66 01 <0/1>` | `[2]` | |
| auto-off | `66 85` / `66 02 <min>` | `[2]` = minutes (`14` = 20) | |
| mic mute | `66 86` / `66 03 <0/1>` | `[2]` = 1 muted | II Core: first needed false then true |
| playback mute | `66 87` / `66 04 <0/1>` | `[2]` | |
| sidetone level | `66 88` / `66 05 <int8>` | `[2]` signed | III: range undocumented (20 "worked"); II Core: −5…+5 |
| battery | `66 89` | `[4]` = %; valid only if `[2]` or `[3]` ≠ 0; `[2..3]` ≈ mV BE | `10 1A` = 4122 mV at 100% (III); `0F 75` = 3957 mV at 79% (II Core, inferred) |
| charging | `66 8A` | `[2]`: 0 no, 1 charging, 2 full | |
| mic attached | `66 8C` | `[2]` = 1 | II Core |
| noise gate | `66 8D` / `66 0F <0/1>` | `[2]` = 1 on | II Core |
| colour | `66 8F` | `[2]`: 0 black, 1 white, 2 black/red | III |

**Events** `66 <id> <value>`: `07` mic attached, `09` sidetone, `0A` mute, `0B` link, `0C` charging,
`0D <s1> <s2> <%>` battery (`[2..3]` mV, `[4]` %). `66 03 <x>` shows up unprompted on open, meaning unknown.
The II Core also emits events when the cable is plugged and when the battery drops.

**Confidence.** III: GhostTheDreamWalker ([HyperHeadset #13](https://github.com/LennardKittner/HyperHeadset/issues/13):
battery, charging, mute, auto-off, sidetone, level, playback mute, colour), MGehrmann (0C9D), the
HyperBatteryMonitor maintainer. II Core: lava114514
([HyperHeadset #27](https://github.com/LennardKittner/HyperHeadset/issues/27): all reads; writes of auto-off,
sidetone, level, playback mute, noise gate, mute), penalte (0995, #29), dantifrice (NGENUITY capture,
HaloBattery #155). There is **no voice-prompt command** (LennardKittner looked in NGENUITY, #31).

**Driver.**
- Implements: link (82), battery (89 + 8A), mic mute, sidetone, playback mute (III and II Core), noise
  gate (II Core only), auto-off (choice 0/10/20/30 min, minutes), colour (III), events 09/0A/0B/0C/0D.
  Each SET is followed by the matching GET.
- **Sidetone level only on the II Core, clamped to −5…+5** (the HyperHeadset range). Not offered on the
  III because its range is unknown.
- Leaves out: `81`, `83`, `8C`, event `07` (parsed in a constant but unused), the "false then true" mute
  workaround, the Windows feature-report path.

**Avoid.** **`66 1E` = reset of the SIRK** (pairing identity key): never sent. Do not probe other opcodes.
`66 83` is read-only.

## 4. `21 BB` — Cloud Alpha Wireless

Driver: `headset_21.py` (`CloudAlphaWireless`) · **community**

- **IDs:** `03F0:098D` (bcdDevice 41.08). `0951:1743` and `0951:1765` are in the NGENUITY 2.38 catalog with
  VID 0951, while HyperHeadset registers them with VID 03F0; the driver matches **both** VIDs.
- **Interface:** 3 (0–2 are audio). Usage page not published. Report ID `0x21`; the driver requires an
  output report 0x21.
- **Packet:** output `21 BB <cmd> <value>` zero-padded (driver: 31 bytes; others use 64). Reply: input
  `21 BB <cmd> <value> …`; SETs reply `21 BB <cmd> <value> 01`. Replies can lag one request behind.

| Feature | GET / SET | Reply | Notes |
|---|---|---|---|
| link | `21 BB 03` | `[3]`: 2 connected, 1 not | |
| pairing info | `21 BB 04` | `[3..8]` 6 bytes | address-like |
| sidetone on/off | `21 BB 05` / `21 BB 10 <0/1>` | `[3]` = 1 on | SET captured from NGENUITY |
| sidetone level | `21 BB 06` / `21 BB 11 <v>` | `[3]` 0xFF when sidetone is off; 2-byte values seen | **semantics unknown** |
| auto-off | `21 BB 07` / `21 BB 12 <min>` | `[3]` = minutes | 0–255 accepted; echo `… 12 <min> 01` |
| mic attached | `21 BB 08` | `[3]` = 1 | |
| voice prompts | `21 BB 09` / `21 BB 13 <0/1>` | `[3]` = 1 on | |
| mic mute | `21 BB 0A` / `21 BB 15 <0/1>` | `[3]` = 1 muted | mic LED follows |
| battery | `21 BB 0B` | `[3]` = %; `[4..5]` ≈ mV BE | `0F FE` = 4094 mV at 85% |
| charging | `21 BB 0C` | `[3]` = 1 charging | |
| device id | `21 BB 0D` | `[3..8]` 6 bytes | hxebolax only |
| colour | `21 BB 0E` | `[3]`: 0 black, 1 white, 2 black/red | |

**Events** `21 BB <id> <value>`: `22` sidetone, `23` mute, `24` link (2 = connected), `25` battery %,
`26` charging.

**Confidence.** oSourceSE ([HyperHeadset #26](https://github.com/LennardKittner/HyperHeadset/issues/26):
everything except the sidetone level), acidiclight (sidetone SET captured from NGENUITY), InfiniteLoopGameDev
(HeadsetControl PR #284); hxebolax marks its commands "verified". imjustafox/HyerpxAlpha-Linux labels `05`
and `0A` differently (microphone state / mic monitor); hardware reports contradict it. One user saw erratic
power saving after ~1 min (#26), apparently firmware.

**Driver.**
- Implements: link, battery (0B + 0C; mV kept only if 2500–5000), mic mute, sidetone, voice prompts,
  auto-off (choice 0/10/20/30), colour, events 22–26.
- **Leaves out the sidetone level (`06`/`11`)**: the scale is unknown (HeadsetControl/hxebolax send 0–128,
  only 100 and 255 "took" in HyperHeadset). Also leaves out `04`, `08`, `0D`.

**Avoid.** Writing a sidetone level until its semantics are known (do it slowly and by hand if
researching). Do not use the `old_cloud_2_doc` Alpha table (wrong).

## 5. `21 FF 05` — Cloud Flight Wireless

Driver: `headset_21.py` (`CloudFlight`) · **community**

- **IDs:** `0951:16C4` (old), `0951:1723` (new), `0951:1749` ("Cloud Flight for PS"), `03F0:0E90` (HP).
- **Interface:** 3 (Windows `MI_03&Col03`); GearPower prefers the 0xFF90 collection. All vendor traffic
  leaves through interrupt IN `0x83`. The driver requires an output report 0x21 of at least 19 bytes.
- **Packet:** output report of 20 bytes `21 FF 05 00 …`. The answer is **asynchronous**, a 20-byte input
  report `21 FF 05 <hi> <lo> …`. **The event type is decided by the read length: 2, 5 or 20 bytes.**

| Feature | Request | Reply | Notes |
|---|---|---|---|
| battery voltage | `21 FF 05` | mV = `[3]<<8 \| [4]` BE | `[3]` 0x0E/0x0F discharging, 0x10/0x11 on the cable |

No command is known for sidetone, auto-off or mute; mute and power arrive only as events.

**Events.** 2 bytes: `64 01` powered on (ask for the battery), `64 03` off, `65 04` muted, `65 <other>`
unmuted. 5 bytes: `01 01 00 00 00` vol+, `01 02 …` vol−, `01 00 …` release. Real volume is USB Audio Class
(SET_CUR on Feature Unit 2, −3…−64 dB), not HID, and `snd-usb-audio` owns that interface on Linux.

**Percent and charging are inferred from voltage, and sources disagree.** Charging threshold: HeadsetControl
> 4107 mV (0x100B); kondinskis/HyperHeadset/HyperBatteryMonitor ≥ 4116 mV (0x1014), below that with
`[3]` = 0x10 meaning "full, 100%"; GearPower the opposite. The percent curve is a table (kondinskis), a
20-step table (HyperHeadset, 3328 … 3970 mV = 100%) or a polynomial (HeadsetControl).

**Confidence.** kondinskis, alex-bakaldin (USBPcap of the Windows app, 70–100% range), c0d3h4x0r, angelleon,
thewaleedtariq ([HyperHeadset #30](https://github.com/LennardKittner/HyperHeadset/issues/30)), Marcoherna
(1723, #64), hede5562 (HeadsetControl PR #211). The charging and low-battery branches were tested least.

**Driver.**
- Implements: voltage → battery; **charging = mV ≥ 4116** (then percent is unknown and shown as none);
  otherwise percent from a 6-point piecewise-linear curve (3328 mV = 0% … 3970 mV = 100%), a
  simplification of the 20-step table. Power (`64 xx`; online only when `xx` = 01) and mute (`65 04`) events.
- Leaves out: volume events, UAC volume, any sidetone/auto-off (none known).

**Avoid.** Nothing known.

## 6. `0C` family variants — Cloud Stinger 3 Wireless, Cloud MIX 2

Driver: end of `cloud3s.py` (`CloudStinger3Wireless`, `CloudMix2`, subclasses of the Cloud III S driver) ·
**experimental**. Framing, report IDs (`0x0C` / `0x0D`), 64-byte packets and "SETs are not acknowledged"
are identical to [cloud3s.md](cloud3s.md). **Opcodes and event types are not.**

### Cloud Stinger 3 Wireless

- **IDs:** `03F0:01C6` (PC), `03F0:03C6` (PlayStation), `03F0:0DC5` (Xbox, `MI_03&Col05`). Absent from the
  legacy NGENUITY catalog; supported by NGENUITY 3 (`stinger_3_wireless` hub module).
- **Interface:** collection **0x01C0:0x0001**; interface number unknown, so the driver matches on the usage
  page only.

| Feature | Request | Reply | Notes |
|---|---|---|---|
| link | `0C 02 03 01 00 02` | `[6]` = 2 connected | |
| mic mute | `0C 02 03 01 00 04` | `[6]` = 1 muted | |
| battery | `0C 02 03 01 00 06` | `[6]` = % (≤ 100) | |
| charging | none | notification only | |

**Events** `0D 02 03 00 <type> <v>`: `0B` battery, `0A` charging (1 = yes), `03` mic with **inverted
polarity relative to the GET** (0 = muted), `0C` link (≠ 1 = disconnected).

**Confidence.** Partial. The Xbox interface was confirmed by a HyperBatteryMonitor tester; the rest is
derived from NGENUITY 3.1 analysis. No voice prompts (HyperHeadset #65).

**Driver.** Implements link, mic mute (read only), battery, charging/mic/link/battery events.
**It also offers sidetone on/off (`0D`/`16`), sidetone level (`44`/`45`, −6…+6), auto-off (`4A`/`4B`, seconds,
0/10/20/30 min) and colour (`4D`), none of which the research notes list for this headset**; they are
inherited from the Cloud III S opcodes and are unconfirmed here. Mic-mute SET, playback mute, voice prompts
and EQ are blocked in `apply`. Treat the extra controls as experimental.

**Avoid.** EQ and slot opcodes (`0F`/`1C`/`5F`) until confirmed; on the III S a slot SET left the GET at `FF`.

### Cloud MIX 2

- **ID:** `03F0:0FAE` (catalog `Headset_CloudMix2`). Windows `MI_03&Col06`. Usage page not published
  (probably 0x01C0; the driver matches 0x01C0 and would not bind otherwise).
- **Packet:** GET `0C 02 03 01 00 <op>`, SET `0C 02 03 00 00 <op> <value>`, reply `0C 02 03 01 00 <op> <value>`
  (value in `[6]`).

| Feature | GET / SET | Reply | Notes |
|---|---|---|---|
| mic mute | `04` / `01 <0/1>` | `[6]` = 1 muted | |
| link | `02` | `[6]` = **1** connected | differs from III S / Stinger 3 (2) |
| battery | `06` | `[6]` = % | no charging state |
| colour | `08` | `[6]` | |
| ANC mode | `0E` / `07 <v>` | 0 off, 1 on, 2 transparency | |
| ANC level | `10` / `09 <0–2>` | | |
| sidetone on/off | `16` / `0D <0/1>` | | |
| EQ preset | `1C` / `0F <0–4>` | index | |

**Events** `0D 02 03 00 <type> <v>`: `01` battery, `03` mic, `04` link (≠ 1 = off), `06` ANC mode.

**Confidence.** None on hardware. WIP branch `cloud_mix_2` of HyperHeadset (no feedback, #35); the
HyperBatteryMonitor does not claim validation.

**Driver.** Implements link, battery, mic mute (read and write), sidetone, ANC mode (0–2) and the four events.
Leaves out ANC level, colour and EQ preset. **Mic-mute write is offered even though nobody has tested it.**

**Avoid.** Values outside the ranges above.

## 7. Feature `0x20` — Cloud III (wired)

Driver: `headset_misc.py` (`CloudIIIWired`) · **community**; `CloudIIIWiredOther` and `CloudAlphaAir` are
**experimental**.

- **IDs:** `03F0:089D` ("HyperX Cloud III"), `03F0:03CC` (2026 revision via the bundled USB-C → 3.5 mm
  adapter, HeadsetControl PR #525). The driver also lists `03F0:0ACE` (Cloud III, "second source") and
  `03F0:07D0` (Cloud Alpha Air) from an NGENUITY 3.1 hub analysis; **neither is in the research notes** and
  neither has hardware confirmation. The NGENUITY catalog also names 089F/08B7/099C/0A9F/0AA0/0EBC "Cloud III"
  but with model `Headset_Ralphie` (OMEN receiver, see the last section): not matched.
- **Interface:** 3, four collections all with usage 0x0001: 0x000C, **0x01C0**, 0x170F, 0xFFC0. The driver
  binds when the 0x01C0 page exists (Alpha Air: no interface pinned).
- **Packet:** SET_REPORT **Feature**, ID `0x20`, 62 bytes (setup `21 09 20 03 03 00 3E 00`), i.e.
  `HIDIOCSFEATURE` with a 62-byte buffer starting at `20`. No reply is known.

| Feature | Request | Reply | Notes |
|---|---|---|---|
| sidetone on | `20 86 01` + zeros | none | tested |
| sidetone off | `20 86 00` | none | tested |
| unknown | `20 05 00 …` | none | NGENUITY sends it before `20 86 01`; not needed |
| level, colour, read-back, "save sidetone to device" | ? | ? | exist in legacy NGENUITY (HyperHeadset [#71](https://github.com/LennardKittner/HyperHeadset/issues/71)); bytes unpublished |

**Events.** None documented. The 0x01C0 page is the same one the Cloud III S uses, but nobody has tested
the `0C 02 03` protocol on this headset.

**Confidence.** AdamGardelov (HeadsetControl [#346](https://github.com/Sapd/HeadsetControl/issues/346),
"works perfect"), MattGalan (03CC, PR #525; found the sidetone very low).

**Driver.** Sidetone on/off only, write-only (no read-back, so the choice is persisted and re-sent). Leaves
out everything unknown.

**Avoid.** "Save to device" (writes persistent memory, bytes unknown); scanning `20 xx` opcodes.

## 8. Avnera feature `0xFF` — Cloud Stinger Core Wireless, Cloud Core Wireless

Driver: `headset_misc.py` (`AvneraHeadset`) · Stinger Core `0A93` **community**; `170B` and Core Wireless
**experimental**.

| Model | USB IDs |
|---|---|
| Cloud Stinger Core Wireless (+7.1) | `03F0:0A93` (PlayStation dongle), `0951:170B` (original dongle). `03F0:0A8E` ("DTS", three HID collections) failed with "Broken pipe" in HyperHeadset #57: not matched |
| Cloud Core Wireless | `0951:173F` (dongle). `0951:1740` (headset on USB-C) not matched; not supported by NGENUITY |

- **Interface:** 3. Stinger Core: vendor collection **0xFF00:0x0001** (`MI_03&Col03`). Core Wireless: 0x000C,
  0xFFC0 and **0xFF00**, all usage 1. The driver binds on page 0xFF00.
- **Transport:** **feature report 0xFF**, 64 bytes. SET_FEATURE the request, wait ~20 ms, GET_FEATURE(0xFF).
  The valid reply starts `FF 12 05`; idle is `FF 01 00 …` (the PlayStation receiver may return a stale
  `FF 01 00` first, so repeat up to 10 times). On the Core Wireless the reply is **ephemeral** (valid
  26–33 ms after the request), and after the headset turns off the header returns to `FF 01 00` while the
  old voltage stays in the bytes. On Windows a plain write fails (`WriteFile 0x57`).

| Feature | Request (64 bytes, zero-padded) | Reply | Notes |
|---|---|---|---|
| link | `FF 07 00 FD 04 00 00 02 82 03 05 29 0F 00 00 03 68 10` | `[11]` = 1 connected | Stinger Core only |
| battery | `FF 07 00 FD 04 0C F1 02 01 04 F0 0C` | `[9]`: 03 not charging, 05 on cable, 06 full; `[11..12]` = mV u16 **LE** | `[10]` is **not** a percentage |

Example Core Wireless reply: `FF 12 05 FE 0C 04 1F 0B 01 03 05 71 0D 00 00 03 68 10` = 3441 mV; on the cable
4152–4187 mV.

**Percent from voltage (Stinger Core only)**, 11 points at 0, 10, … 100%, linear between, same table in
HyperHeadset and HyperBatteryMonitor (both say it comes from NGENUITY):
- discharging: 3517, 3651, 3700, 3738, 3763, 3785, 3838, 3905, 3954, 4042, 4121 mV
- charging: 3400, 3831, 3871, 3916, 3930, 3946, 3967, 4000, 4050, 4090, 4130 mV

The Core Wireless has **no calibrated percentage** (measurements were taken with a faulty battery; the
HyperHeadset branch uses provisional 3380–3610 mV limits with a 20-sample average).

**Events.** None; mute is not monitored.

**Confidence.** `0A93`: pvpiv (HyperBatteryMonitor [PR #6](https://github.com/davidsantanaalves/HyperBatteryMonitor/pull/6),
52 queries). `170B`: supported by HyperBatteryMonitor without explicit validation. Core Wireless: sanjiamca
([HyperHeadset #59](https://github.com/LennardKittner/HyperHeadset/issues/59): request, LE voltage, charge state).

**Driver.** Implements the two requests, polling GET_FEATURE up to 10 × 20 ms for `FF 12 05`; battery as
voltage plus charging (`05`) and full (`06` = 100%); percent from the curve only on the Stinger Core, none
on the Core Wireless (voltage only). The charging state is applied immediately (HyperBatteryMonitor
requires 3 identical readings). If the Core Wireless gives no valid reply, the driver returns without
marking the device offline.

**Avoid.** Any other `FF 07 00 FD …` packet: the format looks like register or memory access on the Avnera
chip. No fuzzing.

## 9. Universal protocol headsets — Cloud Alpha 2 Wireless, Cloud Flight 2

Drivers: `headset_misc.py` (`CloudAlpha2Wireless`, `CloudFlight2`) on top of `universal.py` ·
Alpha 2 **community**, Flight 2 **experimental**. The shared transport (also used by HP mice and keyboards)
is documented in [universal.md](universal.md).

**Transport (family G).** 64-byte reports: `[0]` = report ID = command, `[1]` = subcommand, payload from
`[2]`. A read answers with report ID **command + 1** and the same subcommand. Every request also gets an
ACK `FF 01 …` with `[14]` = cmd, `[15]` = sub, `[16]` = status (0 = ok; the Flight 2 notes say 1 = failure;
HeadsetControl treats `FF 02 …` as NACK). Notifications are `FB <type> …`. With NGENUITY running it polls
~75×/s on the same interface; thousands of `FF 01` and `44`/`45` reports arrive, discard what is not yours.

### Cloud Alpha 2 Wireless

- **IDs:** `03F0:08BE` (base-station control MCU, "Alpha 2 Wireless Controller"): **this is the one that
  talks**. `03F0:0ABE` is the audio function; nothing to read there.
- **Interface:** **2**, collection **0xFF13:0xFF00**. The driver requires an output report 0x60.

| Feature | Request | Reply | Notes |
|---|---|---|---|
| link | `52 01` | `53 01 <c>` | 1 = linked |
| battery | `50 02` | `51 02 <%> <state> <temp °C i16 LE> <mV u16 LE> <gauge chip> <charger chip>` | state 0 no, 1 charging, 2 full, 3 error, FF unknown. `51 02 5D 00 19 00 61 10` = 93%, 25 °C, 4193 mV |
| read audio block | `60 02` | `61 02 <2 bytes> <12-byte block from [4]>` | block offsets: `+4` sidetone on/off, `+5` sidetone level 0–20, `+8` chat-mix, `+11` EQ preset 1–3; preserve the rest. Capture: `61 02 5A 00 01 14 00 00 <on> <lvl> 00 00 81 01 0D 01 …` |
| write audio block | `60 01 <12-byte block from [2]>` | ACK `FF 01` | **whole block only**: read, change your bytes, write back |
| LED brightness | `40 01 00 00 <0–255>` | none | persistent in firmware (peroxy) |
| LED colours (stream) | `44 01 02 00` opens, then `44 02 00 00 <RGB×20>` | none | only while streaming; `000000` = off |

Chat-mix byte: `7B` all game … `80` balanced … `85` all chat.

**Events** `FB 0A 01/00` headset linked/unlinked; `FB 13 00 <%>` battery changed (Dasio). `FB 09 <state>` and
`FB 0D <mute>` come from the HyperBatteryMonitor Universal parser and are **unconfirmed** on the Alpha 2.
A mic-mute read via `61 02` byte `[4]` also comes from that parser; on Alpha 2 captures `[4]` is the first
block byte, so it is **not** confirmed.

**Confidence.** Dasio ([HeadsetControl PR #590](https://github.com/Sapd/HeadsetControl/pull/590), **Windows**:
battery on battery / charging / off, sidetone, chat-mix, EQ preset), azizen12 (HaloBattery #26, battery),
peroxy (LEDs). **Not tested on Linux** (the PR marks the driver Windows-only). HaloBattery infers charging
from bit 7 of byte 6 (the low voltage byte); byte 3 is right.

**Driver.**
- Implements: link, battery (state from byte 3; mV kept if 2500–5000), audio block read, and writes of
  sidetone on/off, sidetone level (clamped 0–20), chat-mix (clamped −5…+5 around `0x80`) and EQ preset
  (clamped 1–3). Every write re-reads the block first and re-reads after writing. Events `FB 0A`, `FB 13`.
- Leaves out: LEDs, per-band custom EQ (unverified), mic mute, `FB 09`/`FB 0D`, NACK handling (a refused
  write simply times out).
- The support level is *community* although the Linux path is untested; the HID bytes are the same as on Windows.

**Avoid.**
- `42 02 02 00 06`: commit of the button colours, **writes to flash** (reversible with a backup, per peroxy).
- `12 01` (**factory reset**), `F0`/`FA`/`FC` (probably firmware), `44 06 01` (flash read; read-only but firmware
  region). `universal.py` also lists `10 02` and report ID `30` as never sent; the research notes do not
  mention those two.
- Writing the audio block without reading first; NGENUITY rewrites the whole block from its own cache when
  you touch its UI.

### Cloud Flight 2

- **IDs:** `03F0:0AC1` (dedicated dongle), `03F0:0CC1` (Xbox receiver); also reachable through the TIO receiver
  `03F0:01BF`. `03F0:03C0` is assigned to the Flight 2 in HyperHeadset #72 but is also the "Cloud Jet Dual
  Wireless" (#28): **not matched**.
- **Interface:** `MI_03&Col04` on Windows (0AC1); Xbox receiver: collection 0xFF90:0xFF00. The driver pins
  interface 3 and requires an output report 0x50.
- Same transport and ACK as the Alpha 2.

| Feature | Request | Reply | Notes |
|---|---|---|---|
| link | `52 01` | `53 01 <c>` | **polarity disputed** (below) |
| battery | `50 02` | `51 02 <%> <state> …` | same layout as Alpha 2 |
| mic mute | `60 02` | `61 02 … [4]` = 1 muted | not implemented |

**Events** `FB 09 <state>` (1 charging), `FB 0A <link>`, `FB 0D <mute>`.

**Link polarity.** HyperBatteryMonitor's dedicated Flight 2 driver treats `53 01 00` as connected, while its
own Universal parser, ngenuity-linux-cli and the hardware-confirmed Alpha 2 use 1 = connected. The shared
`UniversalDevice._read_link` uses **1 = connected**, so if the dedicated-driver reading is right, the Flight 2
would be reported offline while on.

**Confidence.** None on hardware: HyperBatteryMonitor derived it from NGENUITY 3.1 with no physical
validation noted.

**Driver.** Link and battery only; link from event `FB 0A`. **Avoid:** the Alpha 2 list.

---

## Headsets with no public protocol

Contributors with hardware can help most here. "Known" means what is published.

| Headset | USB IDs | What is known | What is missing / lead |
|---|---|---|---|
| Cloud Alpha S | `0951:16ED`, `03F0:0C91` | Catalog `Headset_CloudAlphaS`; control box has volume, mic, mute, 7.1 and game/chat balance in hardware | Interface, transport, opcodes. NGENUITY legacy supports it: look in `NGenuity2Helper.exe`, `NGenuity2.Devices.Headset` |
| Cloud Stinger Core (wired, 7.1) | `0951:1709` | Catalog `Headset_StingerCoreWired`; USB sound card | Everything |
| Cloud Stinger S | `0951:1715` | Catalog `Headset_StingerS`; USB sound card | Everything |
| Cloud MIX Buds / Buds 2 | `03F0:078A` / `03F0:039E` | 2.4 GHz USB-C adapters; also Bluetooth | Everything (family F or G is speculation) |
| Cloud Orbit / Orbit S | none found | Own software (Audeze + Waves Nx, head tracking on the S) | Everything; no RE of the Orbit or the Audeze Mobius |
| Cloud Revolver S | none found | "Plug and play" USB dongle, Dolby 7.1 by button, no software | Probably UAC audio plus consumer buttons; no vendor control known |
| Cloud Jet (Dual) Wireless | `03F0:03C0` | Possibly battery via **USB Mass Storage BOT** (CBW CDB `06 F0 09 00 00 00`, 16-byte reply with battery guessed at `[3]`); HID attempt failed on Windows | Unconfirmed; do not send arbitrary SCSI CDBs to the device |
| HyperX Three-In-One (TIO) receiver | `03F0:01BF` (parent), `03F0:01C5` (alt.) | Universal protocol; children addressed by rewriting byte 1 as `(slot << 6) \| (sub & 0x3F)`, slots 1–3; `70 02` returns 3 records of 8 bytes from `[3]`: `+1` state, `+2..3` VID LE, `+4..5` PID LE; `FB 14` = mode changed, `FB 0A` = child link | Unconfirmed (HyperBatteryMonitor, from NGENUITY 3.1). Avoid `70 04` (enter pairing) and `70 07` (**erase pairing**). Not implemented |
| HP OMEN built-in "HyperX Wireless Audio" receiver | `03F0:0AA0`, `03F0:099C` (+ `089F`, `08B7`, `0A9F`, `0EBC`, catalog `Headset_Ralphie`) | Four HID entries that ignore the `0x66` protocol; audio only on Linux. NGENUITY may reach it through an HP driver or WMI (user hypothesis) | Use the headset's own USB dongle (`069F`/`0995`) instead |
| Cloud Mix (original), Earbuds, analog Cloud II / Alpha / Stinger | `0951:16A4` (Cloud II wired "7.1 Audio" card) | Nothing to control over HID beyond consumer buttons | Nothing to implement |

## Not possible over HID

- 7.1 surround, EQ and spatial audio on the Cloud II family and Stinger 2 are DTS processing on the PC.
- Real headset volume on the Cloud Flight is USB Audio Class, not HID.
- Bluetooth: HyperHeadset reads battery, voice prompts and auto-off of the Cloud III S over Airoha RACE on
  BLE GATT (read only, writes go to volatile RAM). Not HID and not tested on other models.

## Sources

Code and notes were read only. Issue and PR text is user content (GitHub terms, no explicit licence); only
facts were taken from it.

| Source | Link | Licence |
|---|---|---|
| HeadsetControl (commit 2c6790b; PR #590 via `pull/590/head`) | https://github.com/Sapd/HeadsetControl | GPL-3.0 |
| HyperHeadset (commit 71c3067; branches `cloud-core`, `cloud-stinger-core-wireless`, `cloud_mix_2`, `CloudJet`) | https://github.com/LennardKittner/HyperHeadset | MIT |
| SimyriK/HyperHeadset (fork, Flight S) | https://github.com/SimyriK/HyperHeadset | MIT |
| HaloBattery | https://github.com/HeyOkay/HaloBattery | MIT |
| HyperBatteryMonitor (v2.4.0, db200fe) | https://github.com/davidsantanaalves/HyperBatteryMonitor | MIT |
| LowerX (catalog from NGENUITY 2.38, `StingerProtocol.swift`) | https://github.com/lbkeppler/lowerx | none declared |
| hsctl | https://github.com/oauthul/hsctl | MIT |
| auto94 HyperX-Cloud-2-Battery-Monitor | https://github.com/auto94/HyperX-Cloud-2-Battery-Monitor | MIT |
| ngenuity-linux-cli (`docs/protocol/universal.md`) | https://github.com/PMarinov1994/ngenuity-linux-cli | MIT |
| peroxy/hyperx-cloud-alpha2-lightsout | https://github.com/peroxy/hyperx-cloud-alpha2-lightsout | MIT |
| Dasio/HeadsetAutoSwitch | https://github.com/Dasio/HeadsetAutoSwitch | MIT |
| kondinskis/hyperx-cloud-flight | https://github.com/kondinskis/hyperx-cloud-flight | MIT |
| alex-bakaldin/hyperx-cloud-flight-wireless | https://github.com/alex-bakaldin/hyperx-cloud-flight-wireless | MIT |
| XAVIER0229/GearPower | https://github.com/XAVIER0229/GearPower | MIT |
| hahuk/gohyper | https://github.com/hahuk/gohyper | MIT |
| CubE135/hyperx-cloud-flight-s-battery-monitor | https://github.com/CubE135/hyperx-cloud-flight-s-battery-monitor | MIT |
| TheRealRazbi/hyperx-cloud-flight-s-battery-icon | https://github.com/TheRealRazbi/hyperx-cloud-flight-s-battery-icon | MPL-2.0 |
| hxebolax/HyperXAlphaAccesible | https://github.com/hxebolax/HyperXAlphaAccesible | none declared |
| acidiclight/hypermicmonitor | https://github.com/acidiclight/hypermicmonitor | MIT |
| imjustafox/HyerpxAlpha-Linux | https://github.com/imjustafox/HyerpxAlpha-Linux | MIT |
| csmith/alphabat | https://github.com/csmith/alphabat | MIT |
| Agustin-Jerusalinsky/hyperx-cloud-II-battery | https://github.com/Agustin-Jerusalinsky/hyperx-cloud-II-battery | none declared |
| KurtCheng/bluetooth-partner, GameoCoder/omen-hyperx-kde-tray, qu1ncky/BatteryTray, risenxxx/DeskVolt | derivatives; only confirm bytes listed above | MIT |
| HeadsetControl issues/PRs #284, #303, #345, #346, #381, #519, #525, #565, #574, #590; HyperHeadset issues #10, #11, #13, #18, #24, #26–#31, #35, #54, #57, #59, #64–#66, #71, #72 | linked inline | user content, facts only |
| usb.ids (2026.06.26) | http://www.linux-usb.org/usb.ids | BSD-3 / GPL-2 (dual) |
