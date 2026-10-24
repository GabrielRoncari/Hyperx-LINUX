#!/usr/bin/env python3
"""Regenerate the files derived from the driver registry: udev rules and SUPPORTED.md.

    python3 -m tools.gen_docs
"""
from collections import Counter
from pathlib import Path

from hyperx_linux.drivers import DRIVERS
from hyperx_linux.udev import rules, supported_table

ROOT = Path(__file__).resolve().parent.parent


def supported_md() -> str:
    n = Counter(d.support.value for d in DRIVERS)
    return f"""# Supported devices

Generated from the drivers by `python3 -m tools.gen_docs`; do not edit by hand.

**{len(DRIVERS)} drivers**: {n['verified']} verified, {n['community']} community, {n['experimental']} experimental
(see [support levels](CONTRIBUTING.md#support-levels)). Protocol notes per family are in
[docs/devices](docs/devices). Bootloader / firmware-update ids are never opened.

Every headset also gets the [audio engine](docs/audio.md) (spatial audio, software equalizer when it has
none of its own, voice processing), made by PipeWire on the computer: spatial, spatial-width,
spatial-experience, software-eq, mic-noise, mic-highpass, mic-preset. Headsets whose buttons reach the
computer as media keys can give them other actions (buttons, button-macros), done by the app.

""" + supported_table(markdown=True)


def main():
    (ROOT / "udev" / "70-hyperx-linux.rules").write_text(rules())
    (ROOT / "SUPPORTED.md").write_text(supported_md())
    print("udev/70-hyperx-linux.rules and SUPPORTED.md regenerated")


if __name__ == "__main__":
    main()
