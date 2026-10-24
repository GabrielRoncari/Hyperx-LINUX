"""The audio engine's PipeWire graphs, built without running PipeWire."""
import os
import tempfile
import unittest
import wave
from unittest import mock

from hyperx_linux import audio as A


def node_names(graph):
    return {n["name"] for n in graph["nodes"]}


def ports_exist(test, graph):
    names = node_names(graph)
    for link in graph["links"]:
        for end in (link["output"], link["input"]):
            test.assertIn(end.split(":")[0], names, end)
    for end in graph["inputs"] + graph["outputs"]:
        test.assertIn(end.split(":")[0], names, end)


class Spatial(unittest.TestCase):
    def test_speaker_angles_follow_width(self):
        narrow, wide = A.speaker_directions(0), A.speaker_directions(1)
        self.assertEqual((narrow["FL"], narrow["FR"], narrow["RL"]), ((0, 15), (0, 345), (0, 165)))
        self.assertEqual((wide["FL"], wide["RR"]), ((0, 75), (0, 255)))
        self.assertEqual((narrow["FC"], narrow["SL"], narrow["SR"]), ((0, 0), (0, 90), (0, 270)))

    def test_every_direction_has_an_impulse_response(self):
        for width in (0, 0.25, 0.5, 0.75, 1):
            for el, az in A.speaker_directions(width).values():
                path = A.hrir_file(el, az)
                self.assertTrue(os.path.exists(path), path)
        with wave.open(A.hrir_file(0, 90)) as w:
            self.assertEqual((w.getnchannels(), w.getframerate()), (2, 44100))

    def test_spatial_graph(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(A, "CACHE_DIR", tmp):
            graph, positions = A.output_graph(A.OutputSettings(spatial=True, experience="immersion"))
        self.assertEqual(positions, list(A.CHANNELS))
        self.assertEqual(len(graph["inputs"]), 8)
        self.assertEqual(len(graph["outputs"]), 2)
        convolvers = [n for n in graph["nodes"] if n["label"] == "convolver"]
        self.assertEqual(len(convolvers), 16 + 2)  # two ears per speaker, plus the room
        mixers = {n["name"]: n for n in graph["nodes"] if n["label"] == "mixer"}
        self.assertEqual(len(mixers["mixL"]["control"]), 8)  # a mixer has 8 inputs at most
        self.assertEqual(sum(n["label"].startswith("bq_") for n in graph["nodes"]), 20)
        ports_exist(self, graph)

    def test_equalizer_only_graph_is_stereo(self):
        graph, positions = A.output_graph(A.OutputSettings(eq=(3,) + (0,) * 9))
        self.assertEqual((positions, len(graph["inputs"])), (["FL", "FR"], 2))
        self.assertFalse(any(n["label"] == "convolver" for n in graph["nodes"]))
        first = next(n for n in graph["nodes"] if n["name"] == "eqL0")
        self.assertEqual(first["control"]["Gain"], 3.0)
        ports_exist(self, graph)

    def test_eq_params_clamp(self):
        params = A.eq_params((20, -20) + (0,) * 8)
        self.assertEqual((params["eqL0:Gain"], params["eqR1:Gain"]), (8.0, -8.0))

    def test_room_tail_has_unit_energy(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(A, "CACHE_DIR", tmp):
            path = A.room_ir("balanced")
            with wave.open(path) as w:
                raw = w.readframes(w.getnframes())
        samples = [int.from_bytes(raw[i:i + 3], "little", signed=True) / (2 ** 23 - 1) for i in range(0, len(raw), 3)]
        for ear in (0, 1):
            self.assertAlmostEqual(sum(v * v for v in samples[ear::2]), 1.0, places=2)
        self.assertIsNone(A.room_ir("performance"))


class Microphone(unittest.TestCase):
    def test_nothing_to_filter(self):
        self.assertIsNone(A.mic_graph(A.MicSettings()))
        self.assertIsNone(A.mic_graph(A.MicSettings(noise="webrtc")))
        self.assertFalse(A.MicSettings().needed)

    def test_chain_order_and_ports(self):
        graph = A.mic_graph(A.MicSettings(noise="rnnoise", highpass=True, preset="low"), "/x/librnnoise_ladspa.so")
        self.assertEqual([n["name"] for n in graph["nodes"]], ["rnnoise", "highpass", "voice0", "voice1"])
        self.assertEqual(graph["links"][0], {"output": "rnnoise:Output", "input": "highpass:In"})
        self.assertEqual((graph["inputs"], graph["outputs"]), (["rnnoise:Input"], ["voice1:Out"]))
        self.assertEqual(graph["nodes"][0]["plugin"], "/x/librnnoise_ladspa.so")
        self.assertEqual(graph["nodes"][3]["control"], {"Freq": 1500.0, "Q": 0.5, "Gain": -5.0})  # NGENUITY's low boost

    def test_webrtc_alone_is_the_new_microphone(self):
        conf = A.mic_config(A.MicSettings(noise="webrtc"), "src", "snk", "hyperx_linux_mic.t", "Headset")
        self.assertIn("libpipewire-module-echo-cancel", conf)
        self.assertNotIn("libpipewire-module-filter-chain", conf)
        self.assertIn('source.props = { node.name = "hyperx_linux_mic.t"', conf)
        self.assertIn('target.object = "snk"', conf)  # echo reference: what the headset plays

    def test_webrtc_then_filters(self):
        conf = A.mic_config(A.MicSettings(noise="webrtc", preset="mid"), "src", None, "hyperx_linux_mic.t", "H")
        self.assertIn('node.name = "hyperx_linux_mic.t.webrtc"', conf)
        self.assertIn('target.object = "hyperx_linux_mic.t.webrtc"', conf)  # the filter chain listens to it
        self.assertIn('playback.props = { node.name = "hyperx_linux_mic.t" media.class = "Audio/Source" }', conf)


class Config(unittest.TestCase):
    def test_spa_quotes_keys_with_spaces(self):
        self.assertEqual(A._spa({"Gain 1": 0.5, "node.name": "x", "flags": [True]}),
                         '{ "Gain 1" = 0.5 node.name = "x" flags = [ true ] }')

    def test_output_config_targets_the_headset(self):
        conf = A.output_config(A.OutputSettings(spatial=True), "alsa_output.usb-x", "hyperx_linux_output.t", "H")
        self.assertIn('target.object = "alsa_output.usb-x"', conf)
        self.assertIn('audio.position = [ "FL" "FR" "FC" "LFE" "RL" "RR" "SL" "SR" ]', conf)
        self.assertIn(f'node.description = "H ({A._("Spatial 7.1")})"', conf)


class PipeWireState(unittest.TestCase):
    DUMP = [
        {"id": 50, "type": "PipeWire:Interface:Device",
         "info": {"props": {"device.vendor.id": "0x03f0", "device.product.id": "0x02cc"}}},
        {"id": 51, "type": "PipeWire:Interface:Node",
         "info": {"props": {"device.id": 50, "media.class": "Audio/Sink", "node.name": "alsa_output.hx"}}},
        {"id": 52, "type": "PipeWire:Interface:Node",
         "info": {"props": {"device.id": 50, "media.class": "Audio/Source", "node.name": "alsa_input.hx"}}},
        {"id": 53, "type": "PipeWire:Interface:Node",
         "info": {"props": {"media.class": "Audio/Sink", "node.name": "hyperx_linux_output.03f0_02cc"}}},
        {"id": 60, "type": "PipeWire:Interface:Metadata", "props": {"metadata.name": "default"},
         "metadata": [{"subject": 0, "key": "default.audio.sink", "value": {"name": "alsa_output.hx"}},
                      {"subject": 0, "key": "default.configured.audio.sink",
                       "value": {"name": "hyperx_linux_output.03f0_02cc"}}]},
    ]

    def test_find_headset_nodes(self):
        self.assertEqual(A.find_nodes(0x03F0, 0x02CC, self.DUMP), {"sink": "alsa_output.hx", "source": "alsa_input.hx"})
        self.assertEqual(A.find_nodes(0x03F0, 0x0001, self.DUMP), {})

    def test_default_prefers_the_configured_one(self):
        self.assertEqual(A.default_node("sink", self.DUMP), "hyperx_linux_output.03f0_02cc")
        self.assertIsNone(A.default_node("source", self.DUMP))
        self.assertEqual(A.node_id("hyperx_linux_output.03f0_02cc", self.DUMP), 53)

    def test_controls(self):
        with mock.patch.object(A, "noise_options", lambda: (("off", "Off"), ("webrtc", "WebRTC"))):
            plain = A.AudioEngine(1, 2, "H", lambda k, v: None)
            with_hw_eq = A.AudioEngine(1, 2, "H", lambda k, v: None, hardware_eq=True)
        self.assertTrue(plain.handles("software_eq"))
        self.assertFalse(with_hw_eq.handles("software_eq"))  # the headset's own EQ is used instead
        self.assertEqual(plain.output_name, "hyperx_linux_output.0001_0002")


if __name__ == "__main__":
    unittest.main()
