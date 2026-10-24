import unittest

from hyperx_linux.hid import parse_descriptor

# Cloud III S Wireless dongle (03f0:02cc), interface 3, read from sysfs
CLOUD3S_DONGLE = bytes.fromhex(
    "050c0901a101850f1500250109e909ea09e209cd09b509b67501950681020900950281"
    "02c00613ff0901a101150026ff0085060900750895 3d91028507090075089 53d8102c0"
    "050b0905a10115002501750185050920950181220 92f95018122092409210997092a09"
    "50950581060907050909017501950181020508850509170909091809200921092a9506"
    "9122950291 01c006c0ff0a0202a1018509951f75081500 26ff0009028100090291 00c0"
    "06c0010901a101150026ff00850c953f7508150026ff0009028100090291 00850d953f"
    "7508150026ff000902810009029100c0060f170a0202a101851f950775081500 26ff00"
    "09028100090291 00c0".replace(" ", ""))


class Descriptor(unittest.TestCase):
    def setUp(self):
        self.d = parse_descriptor(CLOUD3S_DONGLE)

    def test_collections(self):
        pages = [(c.usage_page, sorted(c.report_ids)) for c in self.d.collections]
        self.assertEqual(pages, [(0x000C, [15]), (0xFF13, [6, 7]), (0x000B, [5]), (0xFFC0, [9]),
                                 (0x01C0, [12, 13]), (0x170F, [31])])

    def test_report_sizes(self):
        self.assertEqual(self.d.report_size("out", 0x0C), 63)
        self.assertEqual(self.d.report_size("in", 0x0D), 63)
        self.assertEqual(self.d.report_size("out", 0x06), 61)
        self.assertEqual(self.d.report_size("in", 0x0F), 1)

    def test_has_page(self):
        self.assertTrue(self.d.has_page(0x01C0))
        self.assertTrue(self.d.has_page(0x000C, 0x0001))
        self.assertFalse(self.d.has_page(0xFF00))


if __name__ == "__main__":
    unittest.main()
