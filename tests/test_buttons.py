"""Headset buttons given other actions (buttons.py), without real input devices."""
import os
import tempfile
import threading
import unittest
from unittest import mock

from hyperx_linux import buttons as B
from hyperx_linux import keymap, uinput


class FakeVirtual:
    def __init__(self, *_a):
        self.keys, self.actions, self.played = [], [], []

    def key(self, code, down):
        self.keys.append((code, down))

    def action(self, a):
        self.actions.append(a)

    def play(self, events):
        self.played.append(events)

    def close(self):
        pass


def mapper(**kw):
    done = threading.Event()
    calls = []

    def device_action(name):
        calls.append(("device", name))
        done.set()

    def run(cmd):
        calls.append(("run", cmd))
        done.set()
    m = B.ButtonMapper("/nonexistent", {163, 164, 165, 113, 114, 115}, lambda k, v: None, device_action,
                       run_command=run, **kw)
    return m, calls, done


class Buttons(unittest.TestCase):
    def test_capability_bitmap(self):
        # the Cloud III S's consumer control: mute, volume, next, play/pause, previous
        self.assertEqual(B.media_keys("3800000000 e000000000000 0"), {113, 114, 115, 163, 164, 165})
        self.assertEqual(B.media_keys("0"), set())

    def test_controls_list_the_buttons_it_has(self):
        m, _c, _d = mapper()
        ids = [b for b, _l in m.controls[0].buttons]
        self.assertEqual(ids, ["play_pause", "next", "previous", "volume_up", "volume_down", "mute"])

    def test_checks(self):
        for bad in ("fn", "fn-lock", "run:  "):
            with self.assertRaises(ValueError):
                B.ButtonMapper.check(bad)
        for good in ("media:next", "ctrl+shift+m", "macro:x", "run:playerctl next", "mic-mute", "disabled"):
            B.ButtonMapper.check(good)

    def test_remapped_runs_the_action_others_pass_through(self):
        m, calls, done = mapper()
        virtual = FakeVirtual()
        m._virtual, m._grabbed = virtual, True
        m.remap = {"play_pause": "mic-mute", "next": "run:playerctl next", "mute": "disabled"}
        m.on_key(115, 1)  # volume up: not remapped, passed on
        m.on_key(115, 0)
        self.assertEqual(virtual.keys, [(115, True), (115, False)])
        m.on_key(164, 1)
        self.assertTrue(done.wait(2))
        m.on_key(164, 0)  # the release does nothing
        done.clear()
        m.on_key(163, 1)
        self.assertTrue(done.wait(2))
        m.on_key(113, 1)  # disabled: swallowed
        self.assertEqual(calls, [("device", "mic-mute"), ("run", "playerctl next")])
        self.assertEqual(virtual.keys, [(115, True), (115, False)])
        self.assertEqual(m.values["last_button"], "Mute")

    def test_keys_and_macros_go_through_the_virtual_device(self):
        m, _c, _d = mapper()
        virtual = FakeVirtual()
        m._virtual = virtual
        m.macros = {"hi": {"steps": '"hi"', "mode": "once"}}
        m.perform("ctrl+shift+m")
        m.perform("macro:hi")
        self.assertEqual(virtual.actions, [keymap.parse_action("ctrl+shift+m")])
        self.assertEqual(virtual.played, [keymap.parse_macro('"hi"')])
        with self.assertRaises(ValueError):
            m.perform("macro:nope")

    def test_holds_the_device_only_while_something_is_remapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            fifo = os.path.join(tmp, "event")
            os.mkfifo(fifo)
            m, calls, done = mapper()
            m.event_path = fifo
            with mock.patch.object(uinput, "available", lambda: False):
                m.apply("buttons", {"previous": "sidetone"})
                self.assertIsNotNone(m._fd)
                writer = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
                os.write(writer, uinput.EVENT.pack(0, 0, B.EV_KEY, 165, 1) + uinput.EVENT.pack(0, 0, 0, 0, 0))
                self.assertTrue(done.wait(2))
                self.assertEqual(calls, [("device", "sidetone")])
                m.apply("buttons", {})
                self.assertIsNone(m._fd)
                os.close(writer)


if __name__ == "__main__":
    unittest.main()
