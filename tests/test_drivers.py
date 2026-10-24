"""Driver tests with replies taken from published captures (see docs/devices/*.md)."""
import unittest

from hyperx_linux import controls as C
from hyperx_linux.controls import BatteryValue
from hyperx_linux.drivers import DRIVERS
from hyperx_linux.drivers.headset_66 import CloudIIIWireless
from hyperx_linux.drivers.headset_ffbb import CloudStinger2Wireless
from hyperx_linux.drivers.headset_misc import CloudAlpha2Wireless, CloudIIIWired
from hyperx_linux.drivers.keyboards import AlloyEliteRGB, AlloyOriginsCore, AlloyRise75
from hyperx_linux.drivers.ngenuity_kb import AlloyElite2, AlloyOrigins, AlloyOrigins60
from hyperx_linux.drivers.mouse_dseries import Dart
from hyperx_linux.drivers.mouse_universal import Haste2Wireless
from tests.fakes import FakeNode, Recorder

SAMPLE = {
    C.Toggle: True, C.Range: None, C.Choice: None, C.Color: (255, 128, 0), C.Equalizer: None,
}


def sample_value(c):
    if isinstance(c, C.Range):
        return c.min
    if isinstance(c, C.Choice):
        return c.options[0][0]
    if isinstance(c, C.Equalizer):
        return [0.0] * len(c.bands_hz)
    return SAMPLE.get(type(c))


def frame(*data, size=64):
    return bytes(data).ljust(size, b"\0")


class Smoke(unittest.TestCase):
    def test_every_driver_survives_a_silent_device(self):
        for d in DRIVERS:
            with self.subTest(driver=d.__name__):
                drv = d(FakeNode(lambda pkt: None), Recorder())
                drv.refresh()
                drv.poll()
                for c in d.controls:
                    if not c.writable or isinstance(c, (C.Battery, C.Info)):
                        continue
                    try:
                        drv.apply(c.id, sample_value(c))
                    except ValueError:
                        pass  # "not read yet" is a valid answer from a silent device
                drv.keepalive()

    def test_controls_are_unique_and_declared(self):
        for d in DRIVERS:
            with self.subTest(driver=d.__name__):
                ids = [c.id for c in d.controls]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(d.ids and d.name and d.sources)


def universal(replies):
    """Universal protocol responder: replies[(cmd, sub)] for reads, ACK for everything else."""
    def respond(pkt):
        if (pkt[0], pkt[1]) in replies:
            return frame(pkt[0] + 1, pkt[1], *replies[(pkt[0], pkt[1])])
        ack = bytearray(64)
        ack[0:2] = b"\xff\x01"
        ack[14], ack[15], ack[16] = pkt[0], pkt[1], 0
        return bytes(ack)
    return respond


class Haste2(unittest.TestCase):
    # 33 02 from ngenuity-linux-cli: 1000 Hz, stages 0-3, active stage 1 (800 DPI)
    DPI = bytes.fromhex("080f0107 00ff0000 0f000000 ff1f00ff ff003f00 00ff00".replace(" ", ""))
    BATTERY = bytes.fromhex("36001a00000f0100")  # 54 %, 26 C, 3840 mV

    def setUp(self):
        self.node = FakeNode(universal({(0x52, 0x01): b"\x01", (0x32, 0x02): self.DPI,
                                        (0x50, 0x02): self.BATTERY, (0x40, 0x02): b"\x82",
                                        (0x36, 0x02): b"\x00\x00\x00\x00\x00"}))
        self.d = Haste2Wireless(self.node, Recorder())
        self.d.refresh()

    def test_reads(self):
        v = self.d.values
        self.assertEqual(v["polling"], 1000)
        self.assertEqual(v["dpi_stage"], 2)
        self.assertEqual(v["dpi"], 800)
        self.assertEqual(v["battery"], BatteryValue(54, False, False, 3840))
        self.assertEqual(v["brightness"], 51)
        self.assertEqual(v["lift_off"], 1)

    def test_dpi_is_read_modify_write_in_slot_0(self):
        self.d.apply("dpi", 1600)
        w = [p for p in self.node.written if p[:2] == b"\x32\x01"][-1]
        self.assertEqual(w[2:4], b"\x00\x00")  # slot 0 = RAM
        self.assertEqual(w[4:7], b"\x08\x0f\x01")  # polling, mask and active stage preserved
        self.assertEqual(w[7 + 5 * 1], 1600 // 50 - 1)
        self.assertEqual(w[7:12], bytes.fromhex("0700ff0000"))  # stage 0 untouched

    def test_polling(self):
        self.d.apply("polling", 500)
        w = [p for p in self.node.written if p[:2] == b"\x32\x01"][-1]
        self.assertEqual(w[4], 0x10)

    def test_never_writes_flash_slot(self):
        for cid, value in (("dpi", 400), ("polling", 250), ("brightness", 10), ("lift_off", 2), ("color", (1, 2, 3))):
            self.d.apply(cid, value)
        for p in self.node.written:
            if p[0] in (0x32, 0x36, 0x40) and p[1] == 0x01:
                self.assertEqual(p[2:4], b"\x00\x00", p[:8].hex())
            self.assertNotIn(p[0], (0x10 if p[1] == 0x02 else -1, 0x12, 0x30, 0xF0, 0xFA, 0xFC))


class DartMouse(unittest.TestCase):
    def setUp(self):
        def respond(pkt):
            if pkt[0] == 0x00:
                pkt = pkt[1:]
            if pkt[0] == 0x46:
                return frame(0x46, 0, 0, 0x01, 0x01)
            if pkt[0] == 0x51:  # 60 %, charging, 3983 mV (santeri3700 capture)
                return frame(0x51, 0, 0, 0x03, 0x3C, 0x01, 0x0F, 0x8F, 0x0F)
            if pkt[0] == 0x53:
                r = bytearray(frame(0x53, 0, 0, 0x21, 0x01, 0x1F))
                for i, steps in enumerate((16, 20, 30, 60, 320)):
                    r[12 + 2 * i], r[13 + 2 * i] = steps & 0xFF, steps >> 8
                return bytes(r)
            return frame(*pkt[:12])  # echo
        self.node = FakeNode(respond)
        self.d = Dart(self.node, Recorder())
        self.d.refresh()

    def test_reads(self):
        self.assertEqual(self.d.values["battery"], BatteryValue(60, True, False, 3983))
        self.assertEqual(self.d.values["dpi"], 1000)  # stage 1 = 20 steps of 50

    def test_writes_without_report_id_and_unit_50(self):
        self.d.apply("dpi", 3200)
        w = [p for p in self.node.written if p[1] == 0xD3 and p[2] == 0x02][-1]
        self.assertEqual(w[0], 0x00)  # no report id
        self.assertEqual(w[1:7], bytes([0xD3, 0x02, 0x01, 0x02, 64, 0]))
        self.assertFalse(any(p[1] == 0xDE for p in self.node.written))  # never saves to EEPROM


class Stinger2(unittest.TestCase):
    def setUp(self):
        def respond(pkt):
            cmd = pkt[3]
            if cmd == 0x02:
                return frame(0x06, 0xFF, 0xBB, 0x02, 0x00, 0x0E, 0x98, 0x1F, size=20)
            if cmd in (0x21, 0x23):
                return frame(0x06, 0xFF, 0xBB, cmd, pkt[4], 0x01, size=20)
            return frame(0x06, 0xFF, 0xBB, cmd, 0x01, size=20)
        self.node = FakeNode(respond)
        self.d = CloudStinger2Wireless(self.node, Recorder())
        self.d.refresh()

    def test_battery_voltage_big_endian(self):
        self.assertEqual(self.d.values["battery"], BatteryValue(31, True, False, 3736))

    def test_sidetone_level_is_capped_at_0_db_and_reapplied(self):
        self.d.apply("sidetone_level", 32)
        sent = [p[3:5] for p in self.node.written if p[3] in (0x21, 0x23)]
        self.assertEqual(sent, [b"\x23\x00", b"\x21\x00", b"\x21\x01"])

    def test_never_sends_status_01(self):
        self.d.refresh()
        self.assertFalse(any(p[3] == 0x01 for p in self.node.written))


class CloudIII(unittest.TestCase):
    def test_battery_66(self):
        def respond(pkt):
            if pkt[1] == 0x82:
                return frame(0x66, 0x82, 0x01, size=62)
            if pkt[1] == 0x89:
                return frame(0x66, 0x89, 0x0F, 0x75, 0x4F, size=62)
            return frame(0x66, pkt[1], 0x00, size=62)
        d = CloudIIIWireless(FakeNode(respond), Recorder())
        d.refresh()
        self.assertEqual(d.values["battery"], BatteryValue(79, False, False, 3957))

    def test_wired_sidetone_feature_report(self):
        node = FakeNode()
        CloudIIIWired(node, Recorder()).apply("sidetone", True)
        self.assertEqual(node.features[0][:3], b"\x20\x86\x01")
        self.assertEqual(len(node.features[0]), 62)


class Alpha2(unittest.TestCase):
    def test_audio_block_read_modify_write(self):
        block = bytes.fromhex("5a 00 01 14 00 00 01 0a 00 00 81 01 0d 01".replace(" ", ""))
        node = FakeNode(universal({(0x52, 0x01): b"\x01", (0x60, 0x02): block,
                                   (0x50, 0x02): bytes.fromhex("5d0019006110")}))
        d = CloudAlpha2Wireless(node, Recorder())
        d.refresh()
        self.assertEqual((d.values["sidetone"], d.values["sidetone_level"], d.values["chat_mix"], d.values["eq_preset"]),
                         (True, 10, 1, 1))
        d.apply("chat_mix", -5)
        w = [p for p in node.written if p[:2] == b"\x60\x01"][-1]
        self.assertEqual(w[2:14], bytes.fromhex("011400000 10a00007b010d01".replace(" ", "")))


class Keyboards(unittest.TestCase):
    def test_origins_core_planar_grb(self):
        node = FakeNode()
        d = AlloyOriginsCore(node, Recorder())
        d.apply("color", (10, 20, 30))
        frames = [p for p in node.written if p[1] == 0xA2]
        self.assertEqual(len(frames), 7)
        self.assertEqual([p[4] for p in frames], [60] * 6 + [20])
        self.assertEqual(frames[0][5:8], bytes([20, 20, 20]))  # green plane first
        self.assertEqual(frames[0][5 + 16], 10)

    def test_f2_family_init_and_packets(self):
        node = FakeNode()
        d = AlloyOrigins60(node, Recorder())
        d.apply("color", (1, 2, 3))
        d.keepalive()  # the session streams the frame
        self.assertEqual(node.features[0][1:3], b"\x04\xf2")
        self.assertEqual(node.features[0][9], 5)
        self.assertEqual(len(node.features), 6)
        self.assertEqual(node.features[1][5:9], b"\x81\x01\x02\x03")  # LED 1 = ESC; LED 0 has no key
        self.assertEqual(node.features[1][1:5], b"\x81\x00\x00\x00")

    def test_full_size_frames_and_keepalive(self):
        for cls, keepalive in ((AlloyOrigins, True), (AlloyElite2, False)):
            node = FakeNode()
            d = cls(node, Recorder())
            d.apply("color", (1, 2, 3))
            d.keepalive()
            sent = [f[2] for f in node.features]
            self.assertEqual(sent.count(0xE0), 1 if keepalive else 0, cls.__name__)
            frames = [f for f in node.features if f[2] != 0xE0]
            self.assertEqual((frames[0][2], frames[0][9], len(frames)), (0xF2, 9, 10))

    def test_elite_channels(self):
        node = FakeNode()
        AlloyEliteRGB(node, Recorder()).apply("color", (9, 8, 7))
        self.assertEqual([p[:4] for p in node.features],
                         [bytes([7, 0x16, ch, 0xA0]) for ch in (1, 2, 3, 4)])
        self.assertEqual(node.features[0][0x08], 9)
        self.assertTrue(all(len(p) == 264 for p in node.features))

    def test_rise75_frames(self):
        node = FakeNode(universal({}))
        AlloyRise75(node, Recorder()).apply("color", (5, 6, 7))
        self.assertEqual(node.written[0][:4], bytes([0x44, 0x01, 0x06, 0x00]))
        self.assertEqual(len([p for p in node.written if p[:2] == b"\x44\x02"]), 6)



class Translations(unittest.TestCase):
    def test_every_driver_string_is_translated(self):
        from hyperx_linux.i18n import PT_BR
        units = (" Hz", " mm", " min")
        for d in DRIVERS:
            for c in d.controls:
                texts = [c.title, c.subtitle]
                if isinstance(c, C.Choice):
                    texts += [label for _v, label in c.options]
                for t in texts:
                    if t and not t.endswith(units) and not t.isdigit():
                        self.assertIn(t, PT_BR, f"{d.__name__}: add a pt-BR translation in i18n.py")


if __name__ == "__main__":
    unittest.main()
