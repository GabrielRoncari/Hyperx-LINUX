# HyperX Linux

Control panel for **HyperX headsets, mice, keyboards and microphones on Linux**: battery, microphone
mute and monitoring (sidetone), equalizer, auto power-off, DPI, polling rate, lighting and more. It
is an unofficial replacement for NGENUITY, which only exists for Windows.

[Português](README.pt-BR.md) · [Supported devices](SUPPORTED.md) · [Contributing](CONTRIBUTING.md)

> Not affiliated with HP or HyperX. "HyperX" and "NGENUITY" are trademarks of HP Inc., used here
> only to say which hardware this software works with.

## What you get

- A **GTK 4 / libadwaita app** that lists every HyperX device plugged in and builds a settings page
  for each one from its driver.
- A **tray icon** with battery level and a microphone mute toggle (any StatusNotifierItem tray:
  KDE, COSMIC, GNOME with the AppIndicator extension, waybar…).
- **Desktop notifications**: low battery, fully charged, microphone muted, device connected or
  disconnected.
- A **command line** for scripts and status bars.
- `hyperx-linux diag`, a read-only report to attach to an issue so new devices can be added.

Settings are applied directly to the device over `hidraw`. Nothing runs as root.

## Devices

**55 drivers** cover HyperX headsets (Cloud III S/III/II/Alpha/Flight/Stinger families), mice
(Pulsefire Haste 2 family, Saga Pro, Dart, Haste Wireless, Surge, Core, Raid…), keyboards (Alloy
Origins/Elite/Rise families, Origins 2 65, Eve 1800) and the QuadCast 2 / 2 S and Fury Ultra.
The full table with USB ids and features is in [SUPPORTED.md](SUPPORTED.md).

Nobody owns all of this hardware, so every driver has a **support level**:

| Level | Meaning |
|---|---|
| **verified** | tested on the device by a maintainer |
| **community** | the protocol was confirmed on real hardware by another open project or user (linked in the driver) |
| **experimental** | derived from the vendor software or unconfirmed; it can read, but **changing settings is disabled** until you enable *Preferences → Allow experimental drivers* (or pass `--experimental` on the command line) |

If you own a device marked community or experimental, a report saying whether it works is the most
valuable contribution you can make: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Install

Requirements: Python 3.10+, and for the window GTK 4.12+ with libadwaita 1.5+ (Ubuntu 24.04,
Fedora 39, Debian 13, Arch or newer):

```sh
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1        # Debian, Ubuntu, Pop!_OS
sudo dnf install python3-gobject gtk4 libadwaita                # Fedora
sudo pacman -S python-gobject gtk4 libadwaita                   # Arch
```

Then:

```sh
git clone https://github.com/GabrielRoncari/Hyperx-LINUX.git
cd Hyperx-LINUX
./install.sh                 # or: ./install.sh --no-autostart
```

`install.sh` installs udev rules (it asks for sudo once) so your user can talk to supported devices
without root. It also creates the `hyperx-linux` command, a menu entry, and a login entry that starts
the app in the tray. Remove everything with `./install.sh --uninstall`.

## Use

```sh
hyperx-linux                          # open the window
hyperx-linux --background             # tray only
hyperx-linux list                     # what is plugged in
hyperx-linux status                   # every setting of the first device
hyperx-linux -h                       # all commands
hyperx-linux set sidetone on
hyperx-linux set eq bass              # preset, or 10 gains in dB
hyperx-linux set dpi 1600 -d haste    # pick a device by name or number
hyperx-linux listen                   # events as they happen
hyperx-linux diag                     # report for an issue
```

Settings are stored in `~/.config/hyperx-linux/config.json`.

## Safety

The drivers deliberately **never** send:

- firmware updates, bootloader/DFU commands or factory resets;
- writes to onboard flash or EEPROM. Mice use the RAM slot only, and keyboard and microphone lighting
  uses the volatile "direct" mode. Some commands write flash on every call (Sonix keyboards, the
  QuadCast 2 persistent brightness); those devices or features are left out;
- commands known to misbehave, such as the Cloud II status query that unmutes the microphone, the
  Pulsefire Raid section selector that froze a mouse, or loud positive sidetone gains.

Bootloader ids from NGENUITY's own device table are never opened and never granted in the udev rules.

**Security note for some keyboards.** On Linux, the Alloy Origins, Alloy Elite 2 and Alloy Origins
60/65 accept lighting commands only through the hidraw node of their **keyboard interface**. Granting
access to it (the udev rules do) also lets programs running as your user read raw key presses from
that keyboard. OpenRGB has the same trade-off. If you don't want it, delete those lines from
`/etc/udev/rules.d/70-hyperx-linux.rules`.

## What it can't do

- **Active noise cancellation** on headsets that don't have it. Cancelling ambient noise needs a
  microphone-to-speaker path of well under 1 ms; going through the PC takes tens of ms. For the
  Cloud III S, a firmware analysis confirmed that its chip has no ANC module
  ([docs/devices/cloud3s-firmware.md](docs/devices/cloud3s-firmware.md)).
- **DTS, spatial audio and NGENUITY's "Audio Engine"** run on Windows, not on the device.
- **Microphone gain and polar pattern.** Gain is a regular USB audio control: use your sound
  settings. Polar pattern is a physical switch or knob.
- **Lighting keeps running only while the app runs**, for devices whose static colour only exists in
  volatile direct mode.

## How it was made

The protocols come from reverse engineering. Some was done for this project: a static analysis of
NGENUITY 3.1 and Legacy 2.38 for the device catalog, and USB/firmware work on the Cloud III S. Most
comes from the published work of other projects, credited in each driver's `sources` and in
[docs/devices](docs/devices). Thanks in particular to
[HeadsetControl](https://github.com/Sapd/HeadsetControl),
[OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB),
[HyperHeadset](https://github.com/LennardKittner/HyperHeadset),
[cloud3s-web-control](https://github.com/Tomlacko/cloud3s-web-control),
[ngenuity-linux-cli](https://github.com/PMarinov1994/ngenuity-linux-cli),
[pulsedart](https://github.com/Kota0674/pulsedart),
[santeri3700's Dart notes](https://github.com/santeri3700/hyperx_pulsefire_dart_reverse_engineering),
[HyperBatteryMonitor](https://github.com/davidsantanaalves/HyperBatteryMonitor),
[HaloBattery](https://github.com/HeyOkay/HaloBattery) and everyone who posted USB captures in their
issue trackers. Only facts (ids, byte layouts) were taken; no vendor code or firmware is included.

## License

[GPL-3.0-or-later](LICENSE).
