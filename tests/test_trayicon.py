import unittest

from hyperx_linux.gui import trayicon


class IconNames(unittest.TestCase):
    STANDARD = ({f"battery-level-{n}-symbolic" for n in range(0, 101, 10)}
                | {f"battery-level-{n}-charging-symbolic" for n in range(0, 91, 10)}
                | {"battery-level-100-charged-symbolic", "battery-missing-symbolic"})

    def test_every_state_has_a_standard_name(self):
        for level in range(101):
            for charging in (False, True, None):
                for full in (False, True):
                    name = trayicon.battery_icon_name(level, charging, full, True)
                    self.assertIn(name, self.STANDARD, (level, charging, full))
        self.assertEqual(trayicon.battery_icon_name(97, True, False, True), "battery-level-90-charging-symbolic")
        self.assertEqual(trayicon.battery_icon_name(None, True, False, True), "battery-missing-symbolic")
        self.assertEqual(trayicon.battery_icon_name(50, False, False, False), "battery-missing-symbolic")


@unittest.skipIf(trayicon.cairo is None, "pycairo not installed")
class TrayIcon(unittest.TestCase):
    def test_pixmaps_are_straight_argb_in_network_order(self):
        pixmaps = trayicon.battery_pixmaps(50, charging=False, low=False, dark=True)
        self.assertEqual([(w, h) for w, h, _b in pixmaps], [(n, n) for n in trayicon.SIZES])
        for w, h, data in pixmaps:
            self.assertEqual(len(data), w * h * 4)
        w, h, data = pixmaps[-1]
        corner = data[0:4]  # transparent background
        self.assertEqual(corner[0], 0)
        alphas = data[0::4]
        self.assertTrue(any(a == 255 for a in alphas))

    def test_low_battery_is_red(self):
        w, h, data = trayicon.battery_pixmaps(10, charging=False, low=True, dark=True)[-1]
        pixels = [tuple(data[i:i + 4]) for i in range(0, len(data), 4)]
        self.assertTrue(any(a == 255 and r > 200 and g < 80 for a, r, g, _b in pixels))


if __name__ == "__main__":
    unittest.main()
