"""Alloy Origins 65: byte layouts and command sequences, as NGENUITY Legacy sends them."""
import unittest
import unittest.mock

from hyperx_linux import effects as fx
from hyperx_linux.drivers import ngenuity_kb as O

ANSI = O.layouts("origins65")["ansi"]
from hyperx_linux.keymap import MacroEvent, parse_macro
from tests.fakes import FakeNode, Recorder

INFO = bytes.fromhex("0040000000300000" "00f0030000" "8f03000000" "0421" + "00" * 5 + "39").ljust(65, b"\0")
PROFILE = bytes(13) + b"\xff\x00\x00\xff\xff\xff\xff"  # report id + 64 bytes: brightness 255, no Fn lock


class FakeKeyboard(FakeNode):
    """Acknowledges commands ([1]=04) like the firmware: [2]=cmd [4]=01, then the data, if any."""

    def __init__(self):
        super().__init__()
        self.queue: list[bytes] = []
        self.feature_reply = self._reply

    def set_feature(self, report):
        super().set_feature(report)
        if report[1] == 0x04 and report[2] != O.CMD_DIRECT:
            ack = bytearray(65)
            ack[1:5] = bytes([0x04, report[2], 0, 1])
            self.queue = [bytes(ack)] + ({0x05: [INFO], 0x56: [PROFILE.ljust(65, b"\0")]}.get(report[2], []))

    def _reply(self, rid, n):
        return self.queue.pop(0) if self.queue else bytes(n)

    def commands(self):
        return [f[2] for f in self.features if f[1] == 0x04]


def keyboard():
    node = FakeKeyboard()
    drv = O.AlloyOrigins65(node, Recorder())
    drv.refresh()
    node.features.clear()
    return drv, node


class Encoding(unittest.TestCase):
    def test_key_matrix_codes(self):
        layout = ANSI
        m = O.encode_matrix({"capslock": "esc", "fn+q": "media:volume-up", "a": "mouse:right", "s": "disabled",
                             "d": "fn", "f": "ctrl+c", "g": "macro:x", "h": "super"}, layout, {"x": 0}, {"x": "hold"})
        slot = {k.id: k.slot for k in layout}
        self.assertEqual(len(m), 160 * 4)
        self.assertEqual(m[slot["capslock"] * 4:][:4], bytes([2, 0, 0x29, 0]))
        self.assertEqual(m[(slot["q"] + 78) * 4:][:4], bytes([3, 0xE9, 0, 0]))
        self.assertEqual(m[slot["a"] * 4:][:4], bytes([1, 1, 2, 0]))
        self.assertEqual(m[slot["s"] * 4:][:4], bytes([5, 0, 0, 0]))
        self.assertEqual(m[slot["d"] * 4:][:4], bytes([2, 0, 0xA4, 0]))
        self.assertEqual(m[slot["f"] * 4:][:4], bytes([2, 1, 6, 0]))
        self.assertEqual(m[slot["g"] * 4:][:4], bytes([6, 0, 3, 0]))
        self.assertEqual(m[slot["h"] * 4:][:4], bytes([2, 8, 0, 0]))  # lone modifier: mask only
        with self.assertRaises(ValueError):
            O.encode_matrix({"fn": "esc"}, layout, {}, {})  # Fn itself has no slot

    def test_macro_table(self):
        a = parse_macro("ctrl+c")
        b = [MacroEvent("button", 1, True, 300), MacroEvent("wheel", -1, True, 0)]
        t = O.encode_macros([a, b])
        self.assertEqual(int.from_bytes(t[0:4], "little"), 400)
        self.assertEqual(int.from_bytes(t[4:8], "little"), 400 + 8 + 4 * len(a))
        self.assertEqual(t[400:408], len(a).to_bytes(4, "little") + bytes(4))
        self.assertEqual(t[408:412], bytes([20, 0, 0xE0, 0xB0]))  # ctrl down, 20 ms
        self.assertEqual(t[412:416], bytes([20, 0, 0x06, 0xB0]))  # c down
        self.assertEqual(t[416:420], bytes([20, 0, 0x06, 0x30]))  # c up
        second = 400 + 8 + 4 * len(a) + 8
        self.assertEqual(t[second:second + 8], bytes([0x2C, 0x01, 1, 0x90, 0, 0, 0xFF, 0xA0]))


class Sequences(unittest.TestCase):
    def test_refresh_reads_firmware_layout_and_profile(self):
        node = FakeKeyboard()
        rec = Recorder()
        drv = O.AlloyOrigins65(node, rec)
        drv.refresh()
        events = dict(rec.events)
        self.assertEqual((events["layout"], events["brightness"]), ("ANSI", 100))
        self.assertEqual(node.commands(), [0x05, 0x56])

    def test_game_mode_is_stored_then_applied(self):
        drv, node = keyboard()
        drv.apply("game_mode", True)
        f = node.features
        self.assertEqual(node.commands(), [0x57, 0x02, 0x67, 0x02])
        stored, live = f[1], f[4]
        self.assertEqual((stored[5], stored[63], stored[64]), (1, 0xAA, 0x55))
        self.assertEqual((live[1], live[5], live[13]), (0, 1, 0xFF))  # live keeps id 0 and the brightness

    def test_keymap_with_a_macro(self):
        drv, node = keyboard()
        drv.apply("macros", {"cp": {"steps": "ctrl+c, 50ms, ctrl+v", "mode": "once"}})
        self.assertEqual(node.features, [])  # nothing uses it yet
        drv.apply("remap", {"capslock": "macro:cp", "delete": "default"})
        cmds = node.commands()
        table = O.encode_macros([parse_macro("ctrl+c, 50ms, ctrl+v")])
        chunks = -(-len(table) // 64)
        self.assertEqual(cmds, [0x18, 0x55, 0x19, 0x02, 0x51, 0x02, 0xB0, 0x02])
        self.assertEqual(node.features[1][9], chunks + 1)
        matrix_cmd = [f for f in node.features if f[1:3] == b"\x04\x51"][0]
        self.assertEqual(matrix_cmd[9], 11)
        self.assertEqual(len(node.features), 2 + chunks + 1 + 2 + 1 + 10 + 1 + 1 + 1 + 1 + 1)

    def test_fn_lock_list(self):
        drv, node = keyboard()
        drv.apply("remap", {"fn+backspace": "fn-lock:#ff8000", "capslock": "esc"})
        lock_cmd = next(i for i, f in enumerate(node.features) if f[1:3] == b"\x04\xb0")  # 80 + 16*3
        self.assertEqual(node.features[lock_cmd][9], 1)
        entry = node.features[lock_cmd + 1]
        slot = next(k.slot for k in drv.layout if k.id == "backspace") + 78
        self.assertEqual((entry[14], entry[15], entry[16], entry[17:20], entry[63:65]),
                         (1, 0, slot, b"\xff\x80\x00", b"\xaa\x55"))
        matrix = b"".join(f[1:65] for f in node.features[2:12])  # the lock leaves the key's action alone
        self.assertEqual(matrix[slot * 4:slot * 4 + 4], bytes(4))

    def test_save_static_lighting_writes_one_frame(self):
        drv, node = keyboard()
        drv.apply("color", (10, 20, 30))
        drv.save_lighting()
        cmds = node.commands()
        self.assertEqual(cmds[:3], [0x53, 0x02, 0x23])
        frames = node.features[1:6]
        esc = ANSI[0]
        self.assertEqual(frames[esc.led // 16][1 + 4 * (esc.led % 16):][:4], bytes([0x80, 10, 20, 30]))
        timing = node.features[8]  # after the command, 5 frame packets, commit and command 23
        self.assertEqual((timing[1], timing[60], timing[62], timing[63], timing[64]), (8, 34, 1, 0xAA, 0x55))
        self.assertIn(0x27, cmds)  # profile of slot 0
        self.assertEqual(cmds[-2:], [0x67, 0x02])


class Lighting(unittest.TestCase):
    def test_effects_fill_the_keys(self):
        r = fx.Renderer(ANSI, seed=1)
        for e in fx.EFFECTS:
            r.configure(effect=e.id, color=(255, 0, 0))
            self.assertEqual(len(r.frame(1.0)), 80)
            frames, ms = r.render_loop()
            self.assertTrue(1 <= len(frames) <= 120 and ms > 0)
        r.configure(effect="wave")
        wave = r.frame(0.3)
        esc, h = (next(k for k in ANSI if k.id == i) for i in ("esc", "h"))
        self.assertNotEqual(wave[esc.led], wave[h.led])

    def test_reactive_lights_the_pressed_key_only_when_asked(self):
        drv, _node = keyboard()
        a = next(k for k in drv.layout if k.id == "a")
        drv.handle_input(bytes([0, 0, 0x04, 0, 0, 0, 0, 0]))
        self.assertEqual(drv.fx.presses, [])  # static effect: keystrokes are ignored
        drv.apply("effect", "reactive-fade")
        drv.apply("color", (0, 255, 0))
        drv.handle_input(bytes([0, 0, 0x04, 0, 0, 0, 0, 0]))
        press = drv.fx.presses[0]
        period = fx.interval_ms(drv.fx.effect, drv.fx.settings.speed) / 1000
        self.assertEqual(drv.fx.frame(press.t0 + period / 2)[a.led], (0, 255, 0))

    def test_painted_keys_are_the_custom_effect(self):
        drv, node = keyboard()
        self.assertFalse(drv.streaming)  # nothing picked yet: the keyboard shows its own lighting
        drv.apply("effect", "custom")
        drv.apply("key_colors", {**{k.id: "#ff0000" for k in drv.layout}, "w": "#00FF00"})
        self.assertTrue(drv.streaming)
        drv.keepalive()
        w, h = (next(k for k in drv.layout if k.id == i) for i in ("w", "h"))
        packet = lambda led: node.features[1 + led // 16][1 + 4 * (led % 16):5 + 4 * (led % 16)]
        self.assertEqual((packet(w.led), packet(h.led)), (bytes([0x81, 0, 255, 0]), bytes([0x81, 255, 0, 0])))
        self.assertEqual(drv.values["key_colors"]["w"], "#00ff00")

    def test_other_effects_run_on_the_whole_keyboard(self):
        """Painted keys don't block an effect: they are kept, and come back with "custom"."""
        drv, _node = keyboard()
        drv.apply("effect", "custom")
        drv.apply("key_colors", {"w": "#00ff00"})
        drv.apply("effect", "static")
        drv.apply("color", (200, 0, 0))
        w = next(k for k in drv.layout if k.id == "w")
        self.assertEqual(drv._paint(drv.fx.frame(1.0))[w.led], (200, 0, 0))
        drv.apply("effect", "custom")
        self.assertEqual(drv._paint(drv.fx.frame(1.0))[w.led], (0, 255, 0))
        with self.assertRaises(ValueError):
            drv.apply("key_colors", {"w": "green"})

    def test_preview_is_what_was_sent(self):
        drv, _node = keyboard()
        drv.keepalive()
        self.assertIsNone(drv.preview)  # nothing streamed: the keyboard shows its own lighting
        drv.apply("effect", "custom")
        drv.apply("color", (200, 0, 0))
        drv.apply("key_colors", {"w": "#00ff00"})
        drv.keepalive()
        self.assertEqual((drv.preview["w"], drv.preview["q"]), ((0, 255, 0), (200, 0, 0)))

    def test_space_bar_is_one_key_with_three_leds(self):
        drv, node = keyboard()
        keys = dict(next(c for c in drv.controls if c.id == "key_colors").layouts)["ANSI"]
        ids = [k[0] for k in keys]
        self.assertIn("space", ids)
        self.assertFalse(any(i.startswith("led-space") for i in ids))
        self.assertEqual(next(k for k in keys if k[0] == "space")[3], 268)  # spans the three zones
        drv.apply("effect", "custom")
        drv.apply("key_colors", {"space": "#0000ff"})
        frame = drv._paint([(0, 0, 0)] * 80)
        leds = [k.led for k in drv.layout if k.id in ("space", "led-space-left", "led-space-right")]
        self.assertEqual([frame[i] for i in leds], [(0, 0, 255)] * 3)

    def test_saved_lighting_has_the_painted_keys(self):
        drv, node = keyboard()
        drv.apply("effect", "custom")
        drv.apply("color", (10, 20, 30))
        drv.apply("key_colors", {"esc": "#ff8000"})
        drv.save_lighting()
        esc = next(k for k in drv.layout if k.id == "esc")
        frame = node.features[1 + esc.led // 16]
        self.assertEqual(frame[1 + 4 * (esc.led % 16):5 + 4 * (esc.led % 16)], bytes([0x80, 255, 128, 0]))

    def test_macro_recording_keeps_the_pauses(self):
        drv, _node = keyboard()
        clock = iter([10.0, 10.25, 10.30])
        drv.handle_input(bytes([0, 0, 0x04, 0, 0, 0, 0, 0]))  # not recording: ignored
        with unittest.mock.patch.object(O.time, "monotonic", lambda: next(clock)):
            drv.apply("macro_record", True)
            drv.handle_input(bytes([0x02, 0, 0, 0, 0, 0, 0, 0]))  # shift
            drv.handle_input(bytes([0x02, 0, 0x04, 0, 0, 0, 0, 0]))  # shift+a
            drv.handle_input(bytes(8))
            drv.apply("macro_record", False)
        text = drv.values["macro_record"]
        self.assertEqual(text, "down:lshift, 250ms, down:a, 50ms, up:a, up:lshift")
        self.assertEqual(parse_macro(text)[0].delay_ms, 250)


class OtherModels(unittest.TestCase):
    """What NGENUITY does differently on the Origins 60, Alloy Origins and Elite 2."""

    def make(self, cls):
        node = FakeKeyboard()
        drv = cls(node, Recorder())
        drv.refresh()
        node.features.clear()
        return drv, node

    def test_origins60_matrix_macros_and_fn_lock(self):
        drv, node = self.make(O.AlloyOrigins60)
        drv.apply("macros", {"m": {"steps": "a", "mode": "once"}})
        drv.apply("remap", {"fn+backspace": "fn-lock:#00ff00", "capslock": "macro:m"})
        self.assertEqual(node.commands(), [0x55, 0x02, 0x51, 0x02])  # no 18/19, no Fn-lock list
        header = next(f for f in node.features if f[1:3] == b"\x04\x51")
        self.assertEqual(header[9], 19)  # 18 packets of 8 x 8-byte slots, plus the AA 55 one
        start = node.features.index(header) + 1
        matrix = b"".join(f[1:65] for f in node.features[start:start + 18])
        bs = next(k.slot for k in drv.layout if k.id == "backspace") + 72
        caps = next(k.slot for k in drv.layout if k.id == "capslock")
        self.assertEqual(matrix[bs * 8:bs * 8 + 8], bytes([7, 0, 255, 0, 0, 0, 0, 0]))
        self.assertEqual(matrix[caps * 8:caps * 8 + 4], bytes([6, 0, 0, 0]))
        drv.apply("game_mode", True)
        live = next(f for f in node.features if f[1:3] == b"\x04\x67")
        data = node.features[node.features.index(live) + 1]
        self.assertEqual((data[1], data[5], data[16]), (3, 1, 1))  # id 3, game mode, the fixed [16]

    def test_alloy_origins_keepalive_before_writes(self):
        drv, node = self.make(O.AlloyOrigins)
        drv.apply("remap", {"capslock": "esc"})
        self.assertEqual(node.commands(), [0xE0, 0x51, 0x02])
        header = next(f for f in node.features if f[1:3] == b"\x04\x51")
        self.assertEqual(header[9], 10)  # 9 packets of 16 x 4-byte slots, plus AA 55
        node.features.clear()
        drv.apply("game_mode", True)
        self.assertEqual(node.commands(), [0x57, 0x02, 0xE0, 0x67, 0x02])
        with self.assertRaises(ValueError):
            drv.apply("remap", {"fn+q": "esc"})  # no Fn layer on this model

    def test_elite2_matrix_between_19_and_18(self):
        drv, node = self.make(O.AlloyElite2)
        drv.apply("remap", {"capslock": "esc"})
        self.assertEqual(node.commands(), [0x19, 0x51, 0x02, 0x18])
        node.features.clear()
        drv.apply("game_mode", True)
        live = next(f for f in node.features if f[1:3] == b"\x04\x67")
        self.assertEqual(node.features[node.features.index(live) + 1][1], 3)

    def test_software_brightness_dims_the_stream(self):
        drv, node = self.make(O.AlloyElite2)
        self.assertEqual(drv.values["brightness"], 100)
        drv.apply("color", (200, 100, 50))
        drv.apply("brightness", 50)
        drv.keepalive()
        esc = next(k for k in drv.layout if k.id == "esc").led
        packet = node.features[1 + esc // 16]
        self.assertEqual(packet[1 + 4 * (esc % 16):5 + 4 * (esc % 16)], bytes([0x81, 100, 50, 25]))
        self.assertEqual(drv.values["brightness"], 50)

    def test_unconfirmed_models_mark_memory_writes_experimental(self):
        for cls in (O.AlloyOrigins60, O.AlloyOrigins, O.AlloyElite2):
            flags = {c.id: c.experimental for c in cls.controls}
            self.assertTrue(flags["remap"] and flags["macros"] and flags["save_lighting"] and flags["game_mode"])
            self.assertFalse(flags["effect"] or flags["color"] or flags["brightness"], cls.__name__)
        self.assertFalse(any(c.experimental for c in O.AlloyOrigins65.controls))


if __name__ == "__main__":
    unittest.main()
