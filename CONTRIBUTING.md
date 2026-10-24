# Contributing

The most useful contribution is **a report from real hardware**. Nobody on the project owns every
HyperX device, so most drivers start as *community* or *experimental* and only become *verified*
when someone confirms them.

## Reporting a device

1. Run `hyperx-linux diag` (it only reads; no serial numbers in the output).
2. Open an issue with the "Device report" template and paste the output.
3. If a driver exists, say which settings worked and which didn't.

For experimental drivers, `hyperx-linux diag --probe` also runs the driver's read commands.
Writes stay off until you opt in: `hyperx-linux set --experimental …` or *Preferences → Allow
experimental drivers*.

## Support levels

| Level | Meaning | Writes |
|---|---|---|
| `verified` | a maintainer tested it on the device | yes |
| `community` | the protocol was confirmed on hardware by another project or user (link in `sources`) | yes, with a notice in the app |
| `experimental` | derived from vendor software or unconfirmed | only after opt-in |

A driver moves up a level when someone reports it working on real hardware.

## Safety rules (non-negotiable)

- **No firmware updates, DFU/bootloader commands or factory modes.** A bad packet there can brick
  a device.
- **No writes to onboard flash** unless the vendor software does the same thing on every change
  (and then document it). Prefer runtime commands.
- Every command in a driver must come from a source you can link: another open project, a USB
  capture, or the vendor software. Put the links in `sources` and in `docs/devices/<device>.md`.
- `refresh()` must only send read commands.

## Writing a driver

A driver is one class in `hyperx_linux/drivers/`. It declares *what* the device has as data
(`controls`); the GUI, CLI and tray are generated from it.

```python
from ..controls import Battery, BatteryValue, Group, Toggle
from .base import Driver, Kind, Support


class CloudExample(Driver):
    name = "HyperX Cloud Example"
    kind = Kind.HEADSET
    support = Support.EXPERIMENTAL
    wireless = True                       # has a "device online" state separate from the receiver
    ids = ((0x03F0, 0x1234, "2.4 GHz dongle"),)
    interfaces = (3,)                     # USB interfaces to open (also used for the udev rules)
    sources = ("https://github.com/…/issues/…",)
    controls = (
        Battery("battery", "Battery", Group.BATTERY),
        Toggle("mic_mute", "Mute microphone", Group.MICROPHONE),
    )

    def refresh(self):                    # reads only
        reply = self.node.request(lambda: self.node.write(bytes([0x06, 0xFF, 0xBB, 0x02]) + bytes(48)),
                                  lambda r: r[:4] == bytes([0x06, 0xFF, 0xBB, 0x02]))
        if reply:
            self.set_online(True)
            self.set_value("battery", BatteryValue(level=reply[7]))

    def apply(self, control_id, value):   # writes
        ...

    def handle_input(self, report):       # unsolicited events from the device
        ...
```

Then:

1. add the class to `DRIVERS` in `hyperx_linux/drivers/__init__.py`;
2. regenerate the derived files (udev rules, SUPPORTED.md): `python3 -m tools.gen_docs`;
3. add tests with `tests/fakes.FakeNode`, which records what the driver writes and answers like the
   device would (see `tests/test_cloud3s.py`);
4. document the protocol in `docs/devices/<device>.md`;
5. run `python3 -m unittest`.

### Transport helpers (`hyperx_linux/hid.py`)

| Method | What it does |
|---|---|
| `node.write(report)` | output report (first byte = report id) |
| `node.send(report)` | output report, serialised with other exchanges, with a short gap |
| `node.set_feature(report)` / `node.get_feature(id, length)` | feature reports |
| `node.get_input(id, length)` | `GET_REPORT(Input)` |
| `node.request(send, match, timeout)` | run `send()` and wait for the first input report `match()` accepts |

`info.descriptor` has the parsed report descriptor (`has_page()`, `report_size()`), useful in
`match_interface()` when a device has several HID interfaces.

### Control types (`hyperx_linux/controls.py`)

`Toggle` (bool), `Range` (number; big ranges become spin buttons), `Choice` (list of options),
`Color` (RGB tuple), `Equalizer` (dB per band + presets), `Battery` (`BatteryValue`), `Info`
(read-only text). `readable=False` means the device can't report the value; `persist=True`
re-applies the saved value whenever the device reconnects (e.g. an EQ without a read command).

## Translations

Strings are English in the code and translated in `hyperx_linux/i18n.py`. Add a dict for your
language and its prefix to `LANGS`.

## Code style

Standard library only for the core (`hid`, `drivers`, `manager`, `cli`); PyGObject for the GUI.
Run `python3 -m unittest` before sending a pull request.
