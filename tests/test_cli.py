import pathlib
import unittest

from hyperx_linux import controls as C
from hyperx_linux.cli import fmt, parse
from hyperx_linux.drivers.cloud3s import Cloud3SWireless
from hyperx_linux.udev import rules


def control(cid):
    return next(c for c in Cloud3SWireless.controls if c.id == cid)


class Values(unittest.TestCase):
    def test_toggle(self):
        self.assertIs(parse(control("sidetone"), ["on"]), True)
        self.assertEqual(fmt(control("sidetone"), False), "off")

    def test_choice_by_label_or_minutes(self):
        self.assertEqual(parse(control("auto_off"), ["never"]), 0)
        self.assertEqual(parse(control("auto_off"), ["45m"]), 2700)
        self.assertEqual(fmt(control("auto_off"), 2700), "45 min")

    def test_range_bounds(self):
        self.assertEqual(parse(control("sidetone_level"), ["-3"]), -3)
        with self.assertRaises(SystemExit):
            parse(control("sidetone_level"), ["9"])

    def test_eq_preset_and_gains(self):
        self.assertEqual(parse(control("eq"), ["bass"])[:3], [6, 5, 4])
        self.assertEqual(parse(control("eq"), [str(x) for x in range(10)])[-1], 8.0)  # clamped to +8 dB

    def test_color(self):
        c = C.Color("color", "Color", C.Group.LIGHTING)
        self.assertEqual(parse(c, ["#ff8000"]), (255, 128, 0))
        self.assertEqual(fmt(c, (255, 128, 0)), "#ff8000")


class Generated(unittest.TestCase):
    def test_supported_md_is_current(self):
        from hyperx_linux.udev import supported_table
        text = (pathlib.Path(__file__).parent.parent / "SUPPORTED.md").read_text()
        self.assertTrue(text.endswith(supported_table(markdown=True)),
                        "regenerate SUPPORTED.md (see its header)")


class Udev(unittest.TestCase):
    def test_committed_rules_are_current(self):
        path = pathlib.Path(__file__).parent.parent / "udev" / "70-hyperx-linux.rules"
        self.assertEqual(path.read_text(), rules(), "run: python3 -m tools.gen_docs")

    def test_rules_cover_every_id(self):
        text = rules()
        for vid, pid, _v in Cloud3SWireless.ids:
            self.assertIn(f'ATTRS{{idProduct}}=="{pid:04x}"', text)
        self.assertIn('TAG+="uaccess"', text)

    def test_group_rules_for_systems_without_logind(self):
        lines = [line for line in rules(group="hyperx").splitlines() if 'ATTRS{idVendor}' in line]
        self.assertTrue(lines)
        for line in lines:
            self.assertTrue(line.endswith('TAG+="uaccess", GROUP="hyperx", MODE="0660"'), line)
        self.assertNotIn("GROUP=", rules())

    def test_one_parent_device_per_rule(self):
        # udev matches all ATTRS of a rule on the same parent: the interface number (USB interface)
        # and the ids (USB device) can never match together, so the interface goes through ENV
        lines = [line for line in rules().splitlines() if line and not line.startswith("#")]
        for line in lines:
            if "ATTRS{idVendor}" in line:
                self.assertNotIn("ATTRS{bInterfaceNumber}", line)
            self.assertNotIn("#", line, "udev rejects comments after the keys")
        self.assertIn('ENV{HYPERX_LINUX_IF}=="03", ATTRS{idVendor}=="03f0", ATTRS{idProduct}=="02cc"', rules())

    def test_udevadm_verify(self):
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("udevadm"):
            self.skipTest("no udevadm")
        with tempfile.NamedTemporaryFile("w", suffix=".rules") as f:
            f.write(rules())
            f.flush()
            r = subprocess.run(["udevadm", "verify", "--no-style", f.name], capture_output=True, text=True)
        if "verify" in r.stderr and "nknown" in r.stderr:
            self.skipTest("udevadm without verify (systemd < 254)")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_install_command(self):
        from hyperx_linux import APP_ID
        from hyperx_linux.udev import RULES_PATH, install_command
        self.assertTrue(install_command(False).startswith("hyperx-linux udev-rules | sudo tee " + RULES_PATH))
        self.assertTrue(install_command(True).startswith(f"flatpak run {APP_ID} udev-rules"))


if __name__ == "__main__":
    unittest.main()
