import unittest

from hyperx_linux.controls import BatteryValue
from hyperx_linux.drivers.cloud3s import Cloud3SWireless
from tests.fakes import FakeNode, Recorder

# GET replies captured from a real headset (03f0:02cc, fw 41.22)
REPLIES = {
    0x02: "02", 0x04: "00", 0x06: "4a0f51", 0x14: "01", 0x16: "00", 0x45: "00",
    0x47: "00", 0x48: "00", 0x4b: "04b0", 0x4d: "00",
}


def headset(link="02"):
    def respond(pkt):
        if pkt[3] != 0x01:  # SETs are not acknowledged
            return None
        value = link if pkt[5] == 0x02 else REPLIES.get(pkt[5])
        if value is None:
            return None
        r = bytearray(64)
        r[0:6] = bytes([0x0C, 0x02, 0x03, 0x01, 0x00, pkt[5]])
        v = bytes.fromhex(value)
        r[6:6 + len(v)] = v
        return bytes(r)
    return respond


class Packets(unittest.TestCase):
    def setUp(self):
        self.node = FakeNode(headset())
        self.events = Recorder()
        self.d = Cloud3SWireless(self.node, self.events)

    def test_get_header(self):
        self.d.refresh()
        self.assertEqual(self.node.written[0][:7], bytes.fromhex("0c020301000200"))
        self.assertEqual(len(self.node.written[0]), 64)

    def test_refresh_values(self):
        self.d.refresh()
        self.assertTrue(self.d.online)
        self.assertEqual(self.d.values["battery"], BatteryValue(74, False, False, 3921))
        self.assertEqual(self.d.values["auto_off"], 1200)
        self.assertEqual(self.d.values["color"], "Black")
        self.assertIs(self.d.values["voice_prompts"], True)

    def test_offline_headset(self):
        d = Cloud3SWireless(FakeNode(headset(link="00")), Recorder())
        d.refresh()
        self.assertIs(d.online, False)
        self.assertNotIn("battery", d.values)

    def test_set_sidetone(self):
        self.d.apply("sidetone", True)
        self.assertEqual(self.node.written[0][:7], bytes.fromhex("0c020300000d01"))

    def test_sidetone_level_clamped_signed(self):
        self.d.apply("sidetone_level", -20)
        self.assertEqual(self.node.written[0][5:7], bytes([0x44, 0xFA]))

    def test_auto_off_big_endian(self):
        self.d.apply("auto_off", 1800)
        self.assertEqual(self.node.written[0][5:8], bytes([0x4A, 0x07, 0x08]))

    def test_eq_centi_db_and_depop(self):
        self.d.apply("eq", [6.0] + [0.0] * 8 + [-2.5])
        pkts = [p for p in self.node.written if p[5] == 0x5F]
        self.assertEqual(pkts[0][6:10], bytes([0, 0x02, 0x58, 0]))
        self.assertEqual(pkts[9][6:10], bytes([9, 0xFF, 0x06, 1]))
        self.assertEqual([p[9] for p in pkts], [0] * 9 + [1])

    def test_eq_live_has_no_depop(self):
        self.d.write_eq_live([1.0] * 10)
        self.assertEqual([p[9] for p in self.node.written if p[5] == 0x5F], [0] * 10)

    def test_events(self):
        self.d.handle_input(bytes.fromhex("0d0203000301"))
        self.assertIs(self.d.values["mic_mute"], True)
        self.d.handle_input(bytes.fromhex("0d0203000c00"))
        self.assertIs(self.d.online, False)
        self.d.handle_input(bytes.fromhex("0d020300012a"))
        self.assertEqual(self.d.values["battery"].level, 42)


if __name__ == "__main__":
    unittest.main()
