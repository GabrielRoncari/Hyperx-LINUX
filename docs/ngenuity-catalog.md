# How the device catalog was obtained

`hyperx_linux/catalog.py` is generated from the vendor's own software, analysed statically. It gives the app
names and kinds for **340 USB ids**, a list of **126 bootloader-only ids** that are never opened, and a short
list of **detection-only** interfaces. Only facts were kept: ids, names, usage pages and byte layouts. No
vendor code, firmware image or library is distributed, and nothing from the vendor was executed.

## What was analysed

| Item | Value |
|---|---|
| NGENUITY 3.1.0 installer | `https://files.hyperx.com/software-installers/ngenuity/stable/3.1.0/HyperX_NGENUITY_Installer.exe` (link from the official `hyperx.com/pages/ngenuity` page), 502,755,064 bytes, SHA-256 `ac10d8cd6126af4e5b003256b557f26afd407757ae30e42c32e0d4252311a139` |
| NGENUITY Legacy 2.38.0.0 installer | `https://files.hyperx.com/software-installers/Ngenuity_Installer/HyperX_NGENUITY_Installer_2.38.0.0.exe`, SHA-256 `19d5744a6781130f9354cf455c16959eef8756ff683ff56cbd48ce9e50cff804` |
| Hub, Windows (`hxn-srv-communication-hub.exe`, Rust, no symbols) | `ab808dacf2f379603c2f3ca14e5f88228f4fae50e59c4c682cb37a45a7c6aac7` |
| Hub, Mach-O arm64 (debug build with a full symbol table) | `a9258ffd8810997e16f55f728b8a93874dff6e0b004effe4878bf274d65872d1` |
| `NGENUITY.dll` (Avalonia UI) | `03515f57445c3c1ebb20c793c3a69fad72e455a54fff842356fede5e49e4a4d9` |
| `NGENUITY.Common.dll` (FlatBuffers enums) | `dee3f2af5281c2b6a5813dd18c29d5984a170bec9f8503487486b6721a3217d0` |
| Legacy `NGenuity2Helper.exe` | `2d6bc3c58a37afc0b0fb537dd3b8eb9cd7d493b5c850de36b56bd580fad711b8` |

The 3.1.0 path was republished by the vendor (Last-Modified 2026-10-06), so hashes can change; compare
before assuming a different file means a different version. The download server sends an incomplete TLS chain;
the missing DigiCert intermediate was fetched from the certificate's AIA URL and verified against the system
roots. Certificate verification was never disabled.

## Method

Static analysis only. No installer, DLL or hub was run (not even under Wine), and no HID device was opened.

1. The installer is a Velopack `Setup.exe`. The `.nupkg` (a zip) sits in the overlay of the PE file, so a
   standard zip reader extracts it directly. It is a .NET `net10.0` Avalonia application plus the Rust
   hub as a service.
2. The .NET parts (`NGENUITY.dll`, `NGENUITY.Common.dll`, `NGenuity2Helper.exe`) were decompiled with
   ILSpy (`ilspycmd` 9.1). They provide the `Products` and `ProductCategory` enums, the `SupportFeatures*`
   bit flags, the display names, and which products the 3.1 UI supports.
3. The hub is Rust. The Windows build has no symbols, but the package accidentally ships a **Mach-O arm64
   debug build that kept its symbol table** (Rust v0 mangling). That made it possible to read it function by
   function. Product definitions and packet builders were disassembled with capstone, and a small partial
   evaluator interpreted the already-decoded arm64 instructions of tiny, side-effect-free functions
   to recover constant bytes. The binary itself never ran.
4. The Mach-O is a slightly older build than the Windows `.exe` (which has more updaters). To check the
   table, each 8-byte endpoint record from the Mach-O was searched literally in the `.exe`: **290 of 293
   match**. The three that differ belong to the Pulsefire Haste 3 family (purpose bits `0x06`/`0x16` on
   Windows, `0x07`/`0x17` with the DFU bit on the Mac); the Mac values are used and the difference noted.
5. The Legacy 2.38 installer is a .NET installer whose `Setup` resource is an `.msixbundle`; inside it the
   x64 `.msix` contains `Assets/Native/NGenuity2Helper.exe`, which holds a table of 198 HID path
   constants (VID, PID, `MI_xx` interface, `Col0x` collection). It also lists the 58 Kingston (`0951`) ids of
   pre-HP products that version 3 dropped.

## What the product table contains

The hub function `get_product_definition(Products)` returns, for each of the 103 `Products` enum values, a
list of endpoints, a product code and a category. An endpoint is 8 bytes: `{pid u16, usage page u16,
usage u16, purpose u16}`. The VID is always `0x03F0`. The hub matches a device by PID plus usage page/usage
as reported by hidapi, so **the v3 table has no interface number**; the Legacy table (`MI_xx`) or the HID
report descriptor on Linux supply it.

`purpose` is a bitflags value: General 0, **DFU 0x1**, Reassignments 0x2, Sensor 0x4, Lighting 0x8, Wireless
0x10, Audio 0x20, Calibration 0x40, Notifications 0x80, **DetectionOnly 0x100**, ThreeInOne 0x200, Gamepad
0x400, Misc 0x800.

`category`: 1 keyboard, 2 mouse, 3 headset, 4 microphone, 5 mouse pad, 6 gamepad, 7 streaming deck,
8 webcam, 9 monitor, 10 DAC, 11 mixer, 12 3-in-1 dongle, 255 unknown.

The hub also picks the protocol from the product (`create_communication_hub`), and the UI assembly
shows which products have a configuration panel in 3.1. The Universal command table, the dangerous-command
list and the feature bit flags that come from the same analysis are in
[devices/universal.md](devices/universal.md). The full 103-row table is not reproduced here; use
`catalog.py` for ids and names.

## How `catalog.py` uses it

- `PRODUCTS`: `(vid, pid) -> (name, kind)` for 340 ids (296 with VID `03F0`, 44 Kingston `0951` from the
  Legacy table). Kinds are `headset` 121, `mouse` 82, `microphone` 57, `keyboard` 50 and `other` 30
  (mouse pads, gamepads, mixers, webcams, dongles). Drivers use it for display names when an id has no
  dedicated driver.
- `FIRMWARE_MODE`: 126 ids that every table marks as DFU/bootloader only. An id that one table calls DFU and
  the other calls a normal endpoint (the DuoCast's `098C`/`088C`) is left out of the list
  (the Legacy `_DFU` constants and the DFU-flagged endpoints of v3). The app **never opens them** and the
  generated udev rules **never grant access** to them (`udev.py` filters with `is_firmware_mode`), so
  a device in update mode cannot be written to by accident.
- `DETECTION_ONLY`: 8 interfaces that the vendor software only uses to detect presence or run the Airoha
  firmware updater: Cloud III S `01CC`/`05BE`, Stinger 3 `02C6`/`0CC5`/`0FC5`, Flight 2 `0BC1`/`06C1` and
  Alpha 2 Wireless `0BBE`. They are listed in the device list (marked as USB-C) but no command is ever sent.
- Firmware update flows (Airoha FOTA, Sonix, Realtek, Primax, dfu1620) were located only to know what
  to stay away from; their opcodes live in third-party DLLs and were deliberately not extracted.

## Protocol by product

| Family | Products | Protocol in the hub | Transport |
|---|---|---|---|
| Cloud III S Wireless, Stinger 3 Wireless | dongles `02CC`/`06BE`, `01C6`/`03C6`/`0DC5` | `Cloud3sWireless` / `Stinger3Wireless` (Stinger is a subset) | output report `0x0C`, usage page `0x01C0` |
| Cloud III Wireless | `0FCC`, `05B7` | `Cloud3Wireless` | output report `0x66` |
| Cloud III (wired), Alpha Air | `03CC`, `089D`, `0ACE`, `07D0` | `Cloud3` | feature report `0x20` |
| QuadCast 2 S audio side | audio endpoints | `RealtekV7` | output report `0x77` |
| Mice, keyboards, other headsets, microphones, pads, gamepads, mixer, Instant Pair dongle | everything else | `Universal` | report id = command, see [universal.md](devices/universal.md) |

Within the Universal group the repository's drivers split by generation: the Haste 2 / Saga Pro mice and the
Alloy Rise keyboards use it directly, while the Kingston-era mice (Surge, Core, Raid, FPS Pro `16D7`) and the
NGENUITY 2 "D series" (Dart, Haste Wireless) use older formats documented in their own pages, and the
QuadCast S, DuoCast, QuadCast 2, Fury Ultra and Pulsefire Mat use the legacy `04/81` family described in
[devices/other.md](devices/other.md). The hub lists those older products under `Universal` only as a
default; the real packet formats there come from the community captures.

## Limits

- Interface numbers are not in the v3 table; match by usage page from the HID descriptor.
- Full reply layouts of `10 01` beyond the three feature bytes, the arguments of most Universal SETs, the
  notification parsers and the per-product `workaround_*` overrides were not extracted.
- Some PIDs appear in two products (for example `03F0:0F8D` is listed under both the Pulsefire Fuse and
  the Pulsefire Mat). When the v3 table is ambiguous, the catalog takes the Legacy table's name (here
  Pulsefire Mat RGB; the Fuse is `03F0:0FBD` there). A name from the catalog is a hint, not proof.
- The legal stance is one line: only facts (ids, names, byte layouts) were kept; no vendor code or firmware
  is distributed, and the analysis was done on files downloaded from the vendor's official site.
