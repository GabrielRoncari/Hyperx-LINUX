# HyperX Linux

Control panel for **HyperX headsets, mice, keyboards and microphones on Linux**: battery, microphone
mute and monitoring (sidetone), equalizer, auto power-off, DPI, polling rate, lighting and more. It
is an unofficial replacement for NGENUITY, which only exists for Windows.

[Português](README.pt-BR.md) · [Supported devices](SUPPORTED.md) · [Contributing](CONTRIBUTING.md)

> Not affiliated with HP or HyperX. "HyperX" and "NGENUITY" are trademarks of HP Inc., used here
> only to say which hardware this software works with.

## What you get

- A **GTK 4 / libadwaita app** laid out like NGENUITY 3: a sidebar with each device and its
  features, a live preview of the device (the keyboard shows the light it is showing), and a feature
  panel at the bottom (Lighting, Keys, Audio, Spatial audio, Buttons, Settings). Every page is built
  from the device's driver.
- A **tray icon** with battery level and a microphone mute toggle (any StatusNotifierItem tray:
  KDE, COSMIC, GNOME with the AppIndicator extension, waybar…).
- **Desktop notifications**: low battery, fully charged, microphone muted, device connected or
  disconnected.
- An **audio engine for headsets**, the Linux take on NGENUITY's: virtual 7.1 spatial audio, a
  software equalizer and voice processing for the microphone (noise and echo reduction, high-pass,
  NGENUITY's mic presets), made on the computer by PipeWire ([docs/audio.md](docs/audio.md)).
- **Other actions for headset buttons**: the multi-function button (1, 2 or 3 presses), volume and
  mute can run a shortcut, a media key, a macro, a command, or toggle the microphone, monitoring or
  spatial audio. NGENUITY only offers this on the Cloud Alpha 2; here it works on every headset whose
  buttons reach the computer as media keys.
- A **command line** for scripts and status bars.
- `hyperx-linux diag`, a read-only report to attach to an issue so new devices can be added.

Settings are applied directly to the device over `hidraw`, and the audio engine through PipeWire.
Nothing runs as root.

## Devices

**55 drivers** cover HyperX headsets (Cloud III S/III/II/Alpha/Flight/Stinger families), mice
(Pulsefire Haste 2 family, Saga Pro, Dart, Haste Wireless, Surge, Core, Raid…), keyboards (Alloy
Origins/Elite/Rise families, Origins 2 65, Eve 1800) and the QuadCast 2 / 2 S and Fury Ultra.
The full table with USB ids and features is in [SUPPORTED.md](SUPPORTED.md).

The **Alloy Origins 65** gets everything NGENUITY offers for it: its 14 lighting effects (static,
breathing, spectrum, wave, alternating, swipe, confetti, sun, twilight, stacking, hourglass and the
reactive fade, explosion, implosion and HyperX flame), saving the lighting to the keyboard so it plays
without the app, brightness, game mode with the Alt+Tab / Alt+F4 / Shift+Tab / Ctrl+Esc blocks, key
remapping (also on the Fn layer), Fn lock keys, and macros stored on the keyboard, which you can also
record by typing them. Like in NGENUITY, the page **draws the keyboard**: paint keys with their own
colours (say the whole keyboard red and WASD green, or a wave with WASD fixed), and click a key to
choose what it does. The **Alloy Origins 60**, **Alloy Origins** and **Alloy Elite 2** get the same
features, each with the protocol of its own NGENUITY module; their lighting is confirmed by other
projects, and what writes to the keyboard's memory stays experimental until someone confirms it.

Nobody owns all of this hardware, so every driver has a **support level**:

| Level | Meaning |
|---|---|
| **verified** | tested on the device by a maintainer |
| **community** | the protocol was confirmed on real hardware by another open project or user (linked in the driver) |
| **experimental** | derived from the vendor software or unconfirmed; it can read, but **changing settings is disabled** until you enable *Preferences → Allow experimental drivers* (or pass `--experimental` on the command line) |

If you own a device marked community or experimental, a report saying whether it works is the most
valuable contribution you can make: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Install

One line, on any distribution with GTK 4 (Ubuntu 22.04+, Debian 12+, Fedora, Arch, openSUSE,
Pop!_OS, Mint 21+, Void, Alpine…):

```sh
curl -fsSL https://raw.githubusercontent.com/GabrielRoncari/Hyperx-LINUX/main/install.sh | sh
```

That's all: it downloads the app, installs what it needs with your package manager (Python,
PyGObject, GTK 4, libadwaita), the udev rules, the `hyperx-linux` command, a menu entry and a login
entry that starts it in the tray. It asks for your password once (`sudo`, `doas` or `run0`). Run the
same line again to update, or end it with `| sh -s -- --uninstall` to remove everything.

From then on devices are plug and play. If one ever shows *No permission* (for example a device
that a newer version learned to support), click *Allow access* on its page: the app asks for your
password in the system's dialog and the device shows up a moment later.

| Your system | How |
|---|---|
| Ubuntu 22.04+, Debian 12+, Fedora, Arch/Manjaro, openSUSE Tumbleweed, Pop!_OS, Mint 21+, Void, Alpine, Solus… | the line above, or [install.sh from a clone](#from-a-clone) |
| Gentoo | install the packages below yourself, then install.sh |
| Debian 11, Ubuntu 20.04 and others without GTK 4 | [Flatpak](#with-flatpak) for the window (install.sh still gives you the command line) |
| Fedora Silverblue/Kinoite, Bazzite, SteamOS and other immutable systems | [Flatpak](#with-flatpak) |
| NixOS | install.sh prints the line to add to `configuration.nix` |

### From a clone

```sh
git clone https://github.com/GabrielRoncari/Hyperx-LINUX.git
cd Hyperx-LINUX
./install.sh                 # options: --no-autostart, --no-deps, --uninstall
```

`install.sh` is plain POSIX `sh` (bash, dash, BusyBox). With `--no-deps` it doesn't touch your
packages; these are what it would install (the command line alone needs only Python 3.8+):

```sh
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1     # Debian, Ubuntu, Pop!_OS, Mint
sudo dnf install python3-gobject python3-cairo gobject-introspection gtk4 libadwaita   # Fedora
sudo pacman -S python-gobject python-cairo gtk4 libadwaita                   # Arch, Manjaro, EndeavourOS
sudo zypper install python313-gobject python313-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1   # openSUSE (python3XX = your Python)
sudo xbps-install python3-gobject python3-cairo gtk4 libadwaita              # Void
doas apk add py3-gobject3 py3-cairo gtk4.0 libadwaita                        # Alpine
emerge dev-python/pygobject dev-python/pycairo gui-libs/gtk gui-libs/libadwaita  # Gentoo
```

For a virtualenv, [requirements.txt](requirements.txt) lists the Python packages (GTK 4 and
libadwaita still come from the distribution; the file explains the details).

**Without systemd** (Void, Artix, Devuan, Gentoo with OpenRC, Alpine…) the usual `uaccess` tag does
nothing, so install.sh creates a `hyperx` group, adds you to it and writes rules for that group.
Log out and back in afterwards.

### With Flatpak

Download `hyperx-linux.flatpak` from the [Releases](https://github.com/GabrielRoncari/Hyperx-LINUX/releases)
page and install it (the GNOME runtime comes from Flathub):

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user hyperx-linux.flatpak
```

A Flatpak can't install udev rules by itself, so run this once (the app also shows it when it has no
permission):

```sh
flatpak run io.github.gabrielroncari.HyperXLinux udev-rules | sudo tee /etc/udev/rules.d/70-hyperx-linux.rules
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw --action=change
```

Without systemd, use `udev-rules --group hyperx` instead and add yourself to that group
(`sudo groupadd -r hyperx && sudo usermod -aG hyperx $USER`). To build the Flatpak yourself:
`flatpak-builder --user --install --force-clean build-dir packaging/flatpak/io.github.gabrielroncari.HyperXLinux.yml`.

### Tested with

| | Versions |
|---|---|
| Python | 3.8 to 3.14 |
| GTK / libadwaita | 4.6 / 1.1 (Ubuntu 22.04), 4.8 / 1.2 (Debian 12), 4.12 / 1.4 (openSUSE Leap 15.6, RHEL 9), 4.22 / 1.9 (current releases) |
| Installer | real installs, dependencies included, on Debian 12, Ubuntu 22.04, Fedora, openSUSE Tumbleweed, Arch, Void and Alpine 3.20 (each then read a real headset); bash, dash and BusyBox; the eudev (group) path in a dry run |
| Real hardware | Cloud III S Wireless on Pop!_OS 24.04 (COSMIC), installed and as a Flatpak |

Older libraries get simpler widgets with the same features (a fixed sidebar instead of the adaptive
one, the classic About and Preferences windows).

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

- firmware updates or bootloader/DFU commands;
- writes to onboard memory you didn't ask for. Mice use the RAM slot only, and lighting uses the
  volatile "direct" mode. Some commands write flash on every call (Sonix keyboards, the QuadCast 2
  persistent brightness); those devices or features are left out. The one exception is the **Alloy
  Origins** family: when you save lighting, remap keys, add macros or change game mode, the keyboard
  stores them in its onboard profiles with exactly the commands NGENUITY uses (checked on an Origins
  65; experimental on the Origins 60, Origins and Elite 2), and the 60 and 65 have a *Restore factory
  settings* button;
- commands known to misbehave, such as the Cloud II status query that unmutes the microphone, the
  Pulsefire Raid section selector that froze a mouse, or loud positive sidetone gains.

Bootloader ids from NGENUITY's own device table are never opened and never granted in the udev rules.

**Headset buttons.** To give a headset button another action, the app reads that headset's own
input device (only its media keys) and takes it while a button is remapped, and it uses `uinput` to
pass the other buttons on and type the chosen keys. The udev rules grant both; `uinput` lets programs
of the logged-in user create virtual keyboards, the same rule Steam installs. Delete the
`uinput` line from `/etc/udev/rules.d/70-hyperx-linux.rules` if you don't want it (button actions
that type keys and the pass-through of volume stop working; commands and toggles keep working).

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
- **DTS Headphone:X and HEAR360 SONAMI**, the engines behind NGENUITY's spatial audio, are licensed
  per product. The audio engine here does the same job with open measurements of a dummy head (MIT
  KEMAR), so it sounds different ([docs/audio.md](docs/audio.md)).
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
Spatial audio uses the MIT KEMAR measurements by Bill Gardner and Keith Martin (1995). The interface
follows NGENUITY 3.1's layout and palette (read from its compiled XAML; no HP artwork is included) and
uses the [Exo 2](https://github.com/googlefonts/Exo-2.0) typeface (SIL Open Font License).

## License

[GPL-3.0-or-later](LICENSE).
