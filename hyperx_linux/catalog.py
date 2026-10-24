"""HyperX product catalog: names and kinds of known USB ids, and ids that must never be opened.

Generated from NGENUITY 3.1.0 (hub product table) and NGENUITY Legacy 2.38 (HID path table);
see docs/ngenuity-catalog.md. Only facts (ids, names) are kept.
"""
from __future__ import annotations

# (vid, pid): (name, kind)
PRODUCTS: dict[tuple[int, int], tuple[str, str]] = {
    (0x03F0, 0x018B): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x018C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x018D): ("HyperX CloudX Stinger Core Wireless", "headset"),
    (0x03F0, 0x018E): ("HyperX Pulsefire Mat RGB", "other"),
    (0x03F0, 0x0190): ("HyperX Pulsefire Haste", "mouse"),
    (0x03F0, 0x0191): ("HyperX Cloud Flight", "headset"),
    (0x03F0, 0x0192): ("HyperX Cloud Buds", "headset"),
    (0x03F0, 0x0194): ("HyperX CloudX Flight", "headset"),
    (0x03F0, 0x0198): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x0199): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x01A1): ("HyperX Alloy Rise", "keyboard"),
    (0x03F0, 0x01AF): ("HyperX Alloy Origins 265", "keyboard"),
    (0x03F0, 0x01B5): ("HyperX QuadCast 2 S", "microphone"),
    (0x03F0, 0x01B9): ("HyperX Alloy Rise 75 Wireless", "keyboard"),
    (0x03F0, 0x01BE): ("HyperX Pulsefire Fuse", "mouse"),
    (0x03F0, 0x01BF): ("HyperX Instant Pair", "other"),
    (0x03F0, 0x01C0): ("HyperX SoloCast 2", "microphone"),
    (0x03F0, 0x01C5): ("HyperX Instant Pair", "other"),
    (0x03F0, 0x01C6): ("HyperX Cloud Stinger 3 Wireless", "headset"),
    (0x03F0, 0x01C8): ("HyperX SoloCast 2 Pro", "microphone"),
    (0x03F0, 0x01CC): ("HyperX Cloud III S Wireless", "headset"),
    (0x03F0, 0x028B): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x028C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x028D): ("HyperX CloudX Stinger Core Wireless", "headset"),
    (0x03F0, 0x028E): ("HyperX Pulsefire Haste Wireless", "mouse"),
    (0x03F0, 0x0290): ("HyperX Pulsefire Raid", "mouse"),
    (0x03F0, 0x0291): ("HyperX Cloud Flight", "headset"),
    (0x03F0, 0x0292): ("HyperX Cloud Buds", "headset"),
    (0x03F0, 0x0293): ("HyperX Alloy Origins", "keyboard"),
    (0x03F0, 0x0294): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x0298): ("HyperX Pulsefire Surge", "mouse"),
    (0x03F0, 0x0299): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x02A1): ("HyperX Alloy Rise 75", "keyboard"),
    (0x03F0, 0x02AF): ("HyperX Alloy Origins 265", "keyboard"),
    (0x03F0, 0x02B5): ("HyperX QuadCast 2 S", "microphone"),
    (0x03F0, 0x02B9): ("HyperX Alloy Rise 75 Wireless", "keyboard"),
    (0x03F0, 0x02C6): ("HyperX Cloud Stinger 3 Wireless", "headset"),
    (0x03F0, 0x02C8): ("HyperX SoloCast 2 Pro", "microphone"),
    (0x03F0, 0x02CC): ("HyperX Cloud III S Wireless", "headset"),
    (0x03F0, 0x02CD): ("HyperX Pulsefire Haste 3 Pro", "mouse"),
    (0x03F0, 0x02CE): ("HyperX Pulsefire Haste 3 Wireless", "mouse"),
    (0x03F0, 0x038B): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x038C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x038D): ("HyperX Clutch", "other"),
    (0x03F0, 0x038E): ("HyperX Pulsefire Haste Wireless", "mouse"),
    (0x03F0, 0x038F): ("HyperX Alloy Origins 65", "keyboard"),
    (0x03F0, 0x0390): ("HyperX Pulsefire Raid", "mouse"),
    (0x03F0, 0x0391): ("HyperX Alloy Core RGB", "keyboard"),
    (0x03F0, 0x0392): ("HyperX Cloud MIX", "headset"),
    (0x03F0, 0x0393): ("HyperX Alloy Origins", "keyboard"),
    (0x03F0, 0x0394): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x0398): ("HyperX Pulsefire Surge", "mouse"),
    (0x03F0, 0x0399): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x039E): ("HyperX Cloud MIX Buds 2", "headset"),
    (0x03F0, 0x03A1): ("HyperX Alloy Rise 75", "keyboard"),
    (0x03F0, 0x03AF): ("HyperX Alloy Origins 2 Core", "keyboard"),
    (0x03F0, 0x03B5): ("HyperX QuadCast 2 S", "microphone"),
    (0x03F0, 0x03C6): ("HyperX Cloud Stinger 3 Wireless", "headset"),
    (0x03F0, 0x03CC): ("HyperX Cloud III", "headset"),
    (0x03F0, 0x048B): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x048C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x048D): ("HyperX Clutch", "other"),
    (0x03F0, 0x048E): ("HyperX Pulsefire Haste Wireless", "mouse"),
    (0x03F0, 0x048F): ("HyperX Alloy Origins 65", "keyboard"),
    (0x03F0, 0x0490): ("HyperX Pulsefire Surge", "mouse"),
    (0x03F0, 0x0491): ("HyperX QuadCast", "microphone"),
    (0x03F0, 0x0492): ("HyperX Cloud MIX", "headset"),
    (0x03F0, 0x0493): ("HyperX FURY Ultra", "other"),
    (0x03F0, 0x0494): ("HyperX Pulsefire Haste", "mouse"),
    (0x03F0, 0x0495): ("HyperX Clutch Gladiate", "other"),
    (0x03F0, 0x0498): ("HyperX Pulsefire Core", "mouse"),
    (0x03F0, 0x049E): ("HyperX Cloud MIX Buds 2", "headset"),
    (0x03F0, 0x04A1): ("HyperX Alloy Core 2 RGB", "keyboard"),
    (0x03F0, 0x04AF): ("HyperX Alloy Origins 2 Core", "keyboard"),
    (0x03F0, 0x04B5): ("HyperX Pulsefire Haste 2 Core", "mouse"),
    (0x03F0, 0x04BF): ("HyperX Pulsefire Saga Pro", "mouse"),
    (0x03F0, 0x04C5): ("HyperX Clutch Talon", "other"),
    (0x03F0, 0x04CD): ("HyperX Pulsefire Haste 3 Pro", "mouse"),
    (0x03F0, 0x058B): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x058C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x058D): ("HyperX Clutch", "other"),
    (0x03F0, 0x058E): ("HyperX Pulsefire Haste Wireless", "mouse"),
    (0x03F0, 0x058F): ("HyperX Alloy Elite 2", "keyboard"),
    (0x03F0, 0x0591): ("HyperX Alloy Origins", "keyboard"),
    (0x03F0, 0x0592): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0593): ("HyperX FURY Ultra", "other"),
    (0x03F0, 0x0594): ("HyperX Pulsefire Haste", "mouse"),
    (0x03F0, 0x0595): ("HyperX Clutch Gladiate", "other"),
    (0x03F0, 0x0598): ("HyperX Pulsefire Core", "mouse"),
    (0x03F0, 0x059E): ("HyperX Vision S", "other"),
    (0x03F0, 0x05A1): ("HyperX Alloy Core 2 RGB", "keyboard"),
    (0x03F0, 0x05AF): ("HyperX Alloy Origins 2", "keyboard"),
    (0x03F0, 0x05B5): ("HyperX Pulsefire Haste 2 Core", "mouse"),
    (0x03F0, 0x05B7): ("HyperX Cloud III Wireless", "headset"),
    (0x03F0, 0x05BE): ("HyperX Cloud III S Wireless", "headset"),
    (0x03F0, 0x05BF): ("HyperX Pulsefire Saga Pro", "mouse"),
    (0x03F0, 0x05C0): ("HyperX Clutch Talon", "other"),
    (0x03F0, 0x05CE): ("HyperX Pulsefire Haste 3", "mouse"),
    (0x03F0, 0x068B): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x068C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x068D): ("HyperX Cloud Core Wireless", "headset"),
    (0x03F0, 0x068E): ("HyperX Pulsefire Dart", "mouse"),
    (0x03F0, 0x068F): ("HyperX Alloy Elite 2", "keyboard"),
    (0x03F0, 0x0691): ("HyperX Alloy Origins", "keyboard"),
    (0x03F0, 0x0692): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0693): ("HyperX Pulsefire FPS Pro", "mouse"),
    (0x03F0, 0x0694): ("HyperX Pulsefire Haste", "mouse"),
    (0x03F0, 0x0695): ("HyperX Clutch Gladiate", "other"),
    (0x03F0, 0x0696): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x0699): ("HyperX Pulsefire Warp", "mouse"),
    (0x03F0, 0x069F): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x06AF): ("HyperX Alloy Origins 2", "keyboard"),
    (0x03F0, 0x06B7): ("HyperX Cloud 3 Wireless Atlas Headset", "headset"),
    (0x03F0, 0x06BE): ("HyperX Cloud III S Wireless", "headset"),
    (0x03F0, 0x06BF): ("HyperX Pulsefire Saga Pro", "mouse"),
    (0x03F0, 0x06C1): ("HyperX CloudX Flight 2", "headset"),
    (0x03F0, 0x078A): ("HyperX Cloud MIX Buds", "headset"),
    (0x03F0, 0x078B): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x078C): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x078D): ("HyperX Cloud Core Wireless", "headset"),
    (0x03F0, 0x078E): ("HyperX Pulsefire Dart", "mouse"),
    (0x03F0, 0x0791): ("HyperX Cloud Orbit S", "microphone"),
    (0x03F0, 0x0792): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0793): ("HyperX Pulsefire FPS Pro", "mouse"),
    (0x03F0, 0x0794): ("HyperX Pulsefire Haste", "mouse"),
    (0x03F0, 0x0795): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0799): ("HyperX Pulsefire Warp", "mouse"),
    (0x03F0, 0x079F): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x07A0): ("HyperX Clutch Gladiate RGB", "other"),
    (0x03F0, 0x07AF): ("HyperX QuadCast 2", "microphone"),
    (0x03F0, 0x07B4): ("HyperX QuadCast 2", "microphone"),
    (0x03F0, 0x07BF): ("HyperX Pulsefire Saga Pro", "mouse"),
    (0x03F0, 0x07C2): ("HyperX Eve 1800", "keyboard"),
    (0x03F0, 0x07C5): ("HyperX Origins 2 Pro 65", "keyboard"),
    (0x03F0, 0x07D0): ("HyperX Cloud Alpha Air", "headset"),
    (0x03F0, 0x088A): ("HyperX Cloud MIX Buds", "headset"),
    (0x03F0, 0x088B): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x088C): ("HyperX DuoCast", "microphone"),
    (0x03F0, 0x088D): ("HyperX Cloud Core Wireless", "headset"),
    (0x03F0, 0x088E): ("HyperX Pulsefire Dart", "mouse"),
    (0x03F0, 0x0891): ("HyperX Cloud Orbit S", "microphone"),
    (0x03F0, 0x0892): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0893): ("HyperX Cloud Stinger Core Wireless 7.1", "headset"),
    (0x03F0, 0x0895): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0896): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0899): ("HyperX Pulsefire Warp", "mouse"),
    (0x03F0, 0x089D): ("HyperX Cloud III", "headset"),
    (0x03F0, 0x089F): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x08A0): ("HyperX Clutch Gladiate RGB", "other"),
    (0x03F0, 0x08AF): ("HyperX QuadCast 2", "microphone"),
    (0x03F0, 0x08B4): ("HyperX QuadCast 2", "microphone"),
    (0x03F0, 0x08B7): ("HyperX Ralphie Ull Atlas", "headset"),
    (0x03F0, 0x08BE): ("HyperX Cloud Alpha 2 Wireless", "headset"),
    (0x03F0, 0x08C2): ("HyperX Eve 1800", "keyboard"),
    (0x03F0, 0x08C5): ("HyperX Origins 2 Pro 65", "keyboard"),
    (0x03F0, 0x098A): ("HyperX Cloud MIX Buds", "headset"),
    (0x03F0, 0x098B): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x098C): ("HyperX DuoCast", "microphone"),
    (0x03F0, 0x098D): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x03F0, 0x098E): ("HyperX Pulsefire Dart", "mouse"),
    (0x03F0, 0x098F): ("HyperX Alloy Origins Core", "keyboard"),
    (0x03F0, 0x0991): ("HyperX Cloud Orbit S", "microphone"),
    (0x03F0, 0x0992): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0993): ("HyperX Cloud Stinger Core Wireless 7.1", "headset"),
    (0x03F0, 0x0995): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0996): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0999): ("HyperX Pulsefire Warp", "mouse"),
    (0x03F0, 0x099C): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x099D): ("HyperX Cloud III", "headset"),
    (0x03F0, 0x099F): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x09A0): ("HyperX Clutch Gladiate RGB", "other"),
    (0x03F0, 0x09AF): ("HyperX QuadCast 2", "microphone"),
    (0x03F0, 0x09B4): ("HyperX Clutch Tanto", "other"),
    (0x03F0, 0x09C0): ("HyperX FlipCast", "microphone"),
    (0x03F0, 0x09C2): ("HyperX Origins 2 1800", "keyboard"),
    (0x03F0, 0x0A8B): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0A8C): ("HyperX DuoCast", "microphone"),
    (0x03F0, 0x0A8D): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x03F0, 0x0A8E): ("HyperX Cloud Stinger Core Wireless", "headset"),
    (0x03F0, 0x0A8F): ("HyperX Alloy Origins Core", "keyboard"),
    (0x03F0, 0x0A90): ("HyperX CloudX Flight", "headset"),
    (0x03F0, 0x0A91): ("HyperX Cloud Flight For PS", "headset"),
    (0x03F0, 0x0A92): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0A93): ("HyperX Cloud Stinger Core Wireless (PS4/PS5)", "headset"),
    (0x03F0, 0x0A95): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0A9B): ("HyperX Audio Mixer", "other"),
    (0x03F0, 0x0A9C): ("HyperX Vision", "other"),
    (0x03F0, 0x0A9D): ("HyperX Cirro Buds", "headset"),
    (0x03F0, 0x0A9F): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0AA0): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0AAF): ("HyperX QuadCast 2", "microphone"),
    (0x03F0, 0x0AB4): ("HyperX Clutch Tanto", "other"),
    (0x03F0, 0x0AB5): ("HyperX Pulsefire Haste 2 Core Wireless", "mouse"),
    (0x03F0, 0x0AB8): ("HyperX Pulsefire Haste 2 S", "mouse"),
    (0x03F0, 0x0ABD): ("HyperX Pulsefire Haste 2 Pro", "mouse"),
    (0x03F0, 0x0AC0): ("HyperX FlipCast", "microphone"),
    (0x03F0, 0x0AC1): ("HyperX Cloud Flight 2", "headset"),
    (0x03F0, 0x0AC2): ("HyperX Origins 2 1800", "keyboard"),
    (0x03F0, 0x0ACE): ("HyperX Cloud III", "headset"),
    (0x03F0, 0x0B8B): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0B8C): ("HyperX DuoCast", "microphone"),
    (0x03F0, 0x0B8D): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x03F0, 0x0B8E): ("HyperX Cloud Stinger Core Wireless", "headset"),
    (0x03F0, 0x0B8F): ("HyperX Alloy MKW 100", "keyboard"),
    (0x03F0, 0x0B90): ("HyperX CloudX Flight", "headset"),
    (0x03F0, 0x0B91): ("HyperX Cloud Flight For PS", "headset"),
    (0x03F0, 0x0B92): ("HyperX Cloud II", "headset"),
    (0x03F0, 0x0B93): ("HyperX Cloud Stinger Core Wireless (PS4/PS5)", "headset"),
    (0x03F0, 0x0B97): ("HyperX Pulsefire Haste 2", "mouse"),
    (0x03F0, 0x0B9B): ("HyperX Audio Mixer", "other"),
    (0x03F0, 0x0B9D): ("HyperX Cirro Buds", "headset"),
    (0x03F0, 0x0B9F): ("HyperX Cloud II Core Wireless", "headset"),
    (0x03F0, 0x0BA0): ("HyperX Pulsefire Haste 2 Mini", "mouse"),
    (0x03F0, 0x0BB4): ("HyperX Clutch Tanto", "other"),
    (0x03F0, 0x0BB5): ("HyperX Pulsefire Haste 2 Core Wireless", "mouse"),
    (0x03F0, 0x0BB8): ("HyperX Pulsefire Haste 2 S", "mouse"),
    (0x03F0, 0x0BBD): ("HyperX Pulsefire Haste 2 Pro", "mouse"),
    (0x03F0, 0x0BBE): ("HyperX Cloud Alpha 2 Wireless", "headset"),
    (0x03F0, 0x0BC0): ("HyperX FlipCast", "microphone"),
    (0x03F0, 0x0BC1): ("HyperX Cloud Flight 2", "headset"),
    (0x03F0, 0x0BC2): ("HyperX Origins 2 65", "keyboard"),
    (0x03F0, 0x0C8A): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x0C8B): ("HyperX SoloCast", "microphone"),
    (0x03F0, 0x0C8C): ("HyperX Cloud Flight For PS", "headset"),
    (0x03F0, 0x0C8D): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x03F0, 0x0C8E): ("HyperX Alloy Origins 60", "keyboard"),
    (0x03F0, 0x0C8F): ("HyperX Alloy MKW 100", "keyboard"),
    (0x03F0, 0x0C90): ("HyperX CloudX Flight", "headset"),
    (0x03F0, 0x0C91): ("HyperX Cloud Alpha S", "headset"),
    (0x03F0, 0x0C92): ("HyperX Cloud II", "headset"),
    (0x03F0, 0x0C97): ("HyperX Pulsefire Haste 2", "mouse"),
    (0x03F0, 0x0C9B): ("HyperX Audio Mixer", "other"),
    (0x03F0, 0x0C9D): ("HyperX Cloud 3 Wireless", "headset"),
    (0x03F0, 0x0CA0): ("HyperX Pulsefire Haste 2 Mini", "mouse"),
    (0x03F0, 0x0CB4): ("HyperX Clutch Tanto", "other"),
    (0x03F0, 0x0CB8): ("HyperX Pulsefire Haste 2 S", "mouse"),
    (0x03F0, 0x0CBD): ("HyperX Pulsefire Haste 2 Pro", "mouse"),
    (0x03F0, 0x0CC0): ("HyperX FlipCast", "microphone"),
    (0x03F0, 0x0CC1): ("HyperX CloudX Flight 2", "headset"),
    (0x03F0, 0x0CC2): ("HyperX Origins 2 65", "keyboard"),
    (0x03F0, 0x0CC5): ("HyperX CloudX Stinger 3 WL", "headset"),
    (0x03F0, 0x0D84): ("HyperX QuadCast 2 S", "microphone"),
    (0x03F0, 0x0D8A): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x0D8B): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x0D8C): ("HyperX Cloud Flight For PS", "headset"),
    (0x03F0, 0x0D8D): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x03F0, 0x0D8E): ("HyperX Alloy Origins 60", "keyboard"),
    (0x03F0, 0x0D8F): ("HyperX Pulsefire Core", "mouse"),
    (0x03F0, 0x0D90): ("HyperX CloudX Flight", "headset"),
    (0x03F0, 0x0D91): ("HyperX Cloud Alpha S", "headset"),
    (0x03F0, 0x0D92): ("HyperX Cloud MIX Buds", "headset"),
    (0x03F0, 0x0D93): ("HyperX Cloud Stinger 2 Wireless", "headset"),
    (0x03F0, 0x0D97): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x0D9B): ("HyperX Audio Mixer", "other"),
    (0x03F0, 0x0DA0): ("HyperX Pulsefire Haste 2 Mini", "mouse"),
    (0x03F0, 0x0DB8): ("HyperX Pulsefire Haste 2 S", "mouse"),
    (0x03F0, 0x0DBD): ("HyperX Pulsefire Haste 2 Pro", "mouse"),
    (0x03F0, 0x0DC5): ("HyperX CloudX Stinger 3 WL", "headset"),
    (0x03F0, 0x0E8A): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x0E8B): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x0E8C): ("HyperX Cloud Flight For PS", "headset"),
    (0x03F0, 0x0E8D): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x03F0, 0x0E8F): ("HyperX Pulsefire FPS Pro", "mouse"),
    (0x03F0, 0x0E90): ("HyperX Cloud Flight", "headset"),
    (0x03F0, 0x0E91): ("HyperX Cloud Revolver S", "headset"),
    (0x03F0, 0x0E92): ("HyperX Cloud Stinger S", "headset"),
    (0x03F0, 0x0E93): ("HyperX Cloud Stinger 2 Wireless", "headset"),
    (0x03F0, 0x0E97): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x0E9D): ("HyperX Cloud 3 Wireless Headset", "headset"),
    (0x03F0, 0x0EA0): ("HyperX Pulsefire Haste 2 Mini", "mouse"),
    (0x03F0, 0x0EAE): ("HyperX Cloud MIX 2", "headset"),
    (0x03F0, 0x0EB4): ("HyperX QuadCast 2 S", "microphone"),
    (0x03F0, 0x0EB8): ("HyperX Alloy Rise 75 Wireless", "keyboard"),
    (0x03F0, 0x0EBC): ("HyperX Ralphie Ull 2", "headset"),
    (0x03F0, 0x0EBE): ("HyperX Pulsefire Saga", "mouse"),
    (0x03F0, 0x0F8A): ("HyperX Cloud II Wireless", "headset"),
    (0x03F0, 0x0F8B): ("HyperX QuadCast S", "microphone"),
    (0x03F0, 0x0F8C): ("HyperX Cloud Flight For PS", "headset"),
    (0x03F0, 0x0F8D): ("HyperX Pulsefire Mat RGB", "other"),
    (0x03F0, 0x0F8F): ("HyperX Pulsefire Haste", "mouse"),
    (0x03F0, 0x0F90): ("HyperX Cloud Flight", "headset"),
    (0x03F0, 0x0F91): ("HyperX Cloud Revolver S", "headset"),
    (0x03F0, 0x0F92): ("HyperX Cloud Stinger S", "headset"),
    (0x03F0, 0x0F93): ("HyperX CloudX Flight", "headset"),
    (0x03F0, 0x0F97): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x0F98): ("HyperX Pulsefire Haste 2 Wireless", "mouse"),
    (0x03F0, 0x0FA0): ("HyperX Alloy Rise", "keyboard"),
    (0x03F0, 0x0FAE): ("HyperX Cloud MIX 2", "headset"),
    (0x03F0, 0x0FB4): ("HyperX QuadCast 2 S", "microphone"),
    (0x03F0, 0x0FB8): ("HyperX Alloy Rise 75 Wireless Keyboard", "keyboard"),
    (0x03F0, 0x0FBD): ("HyperX Pulsefire Fuse Wireless", "mouse"),
    (0x03F0, 0x0FBE): ("HyperX Pulsefire Saga", "mouse"),
    (0x03F0, 0x0FBF): ("HyperX SoloCast 2", "microphone"),
    (0x03F0, 0x0FC0): ("HyperX Pulsefire Haste 3 Wireless", "mouse"),
    (0x03F0, 0x0FC5): ("HyperX Cloud Stinger 3 Wireless", "headset"),
    (0x03F0, 0x0FCC): ("HyperX Cloud III Wireless", "headset"),
    (0x0951, 0x16BE): ("HyperX Alloy Elite", "keyboard"),
    (0x0951, 0x16C4): ("HyperX Cloud Flight Wireless", "headset"),
    (0x0951, 0x16D3): ("HyperX Pulsefire Surge", "mouse"),
    (0x0951, 0x16D7): ("HyperX Pulsefire FPS Pro", "mouse"),
    (0x0951, 0x16DC): ("HyperX Alloy FPS", "keyboard"),
    (0x0951, 0x16DE): ("HyperX Pulsefire Core", "mouse"),
    (0x0951, 0x16E1): ("HyperX Pulsefire Dart", "mouse"),
    (0x0951, 0x16E2): ("HyperX Pulsefire Dart", "mouse"),
    (0x0951, 0x16E4): ("HyperX Pulsefire Raid", "mouse"),
    (0x0951, 0x16E5): ("HyperX Alloy Origins", "keyboard"),
    (0x0951, 0x16E6): ("HyperX Alloy Origins Core", "keyboard"),
    (0x0951, 0x16EA): ("HyperX Cloud Flight S", "headset"),
    (0x0951, 0x16ED): ("HyperX Cloud Alpha S", "headset"),
    (0x0951, 0x16F5): ("HyperX Alloy Origins", "keyboard"),
    (0x0951, 0x16F6): ("HyperX Alloy Origins Core", "keyboard"),
    (0x0951, 0x16F7): ("HyperX Pulsefire Dart Dfu2", "mouse"),
    (0x0951, 0x16F8): ("HyperX Pulsefire Dart", "mouse"),
    (0x0951, 0x16F9): ("HyperX Pulsefire Raid", "mouse"),
    (0x0951, 0x1705): ("HyperX Fury Ultra", "other"),
    (0x0951, 0x1706): ("HyperX Fury Ultra", "other"),
    (0x0951, 0x1709): ("HyperX Stinger Core Wired", "headset"),
    (0x0951, 0x170B): ("HyperX Stinger Core Wireless", "headset"),
    (0x0951, 0x170F): ("HyperX SoloCast Black", "microphone"),
    (0x0951, 0x1711): ("HyperX Alloy Elite II", "keyboard"),
    (0x0951, 0x1712): ("HyperX Alloy Elite II", "keyboard"),
    (0x0951, 0x1715): ("HyperX Stinger S", "headset"),
    (0x0951, 0x1718): ("HyperX Cloud II Wireless", "headset"),
    (0x0951, 0x1719): ("HyperX Cloud II Wireless", "headset"),
    (0x0951, 0x171F): ("HyperX QuadCast S", "microphone"),
    (0x0951, 0x1720): ("HyperX QuadCast S", "microphone"),
    (0x0951, 0x1723): ("HyperX Cloud Flight Wireless", "headset"),
    (0x0951, 0x1727): ("HyperX Pulsefire Haste", "mouse"),
    (0x0951, 0x1728): ("HyperX Pulsefire Haste", "mouse"),
    (0x0951, 0x1729): ("HyperX Pulsefire FPS Pro", "mouse"),
    (0x0951, 0x172A): ("HyperX Pulsefire FPS Pro", "mouse"),
    (0x0951, 0x1734): ("HyperX Alloy Origins 60", "keyboard"),
    (0x0951, 0x1735): ("HyperX Alloy Origins 60", "keyboard"),
    (0x0951, 0x1741): ("HyperX Pulsefire Mat RGB", "other"),
    (0x0951, 0x1742): ("HyperX Pulsefire Mat RGB Dfu1", "other"),
    (0x0951, 0x1743): ("HyperX Cloud Alpha Wireless", "headset"),
    (0x0951, 0x1756): ("HyperX Alloy Mkw100", "keyboard"),
    (0x0951, 0x175F): ("HyperX DuoCast Controller", "microphone"),
    (0x0951, 0x1765): ("HyperX Cloud Alpha Wireless Dongle2", "headset"),
    (0x0951, 0x1774): ("HyperX QuadCast S 2s Wb", "microphone"),
}

# Bootloader / firmware-update ids: never opened, never granted in the udev rules.
FIRMWARE_MODE: frozenset[tuple[int, int]] = frozenset({
    (0x03F0, 0x018C),  # QuadCast S
    (0x03F0, 0x018E),  # Pulsefire Mat RGB
    (0x03F0, 0x0190),  # Pulsefire Haste
    (0x03F0, 0x0194),  # CloudX Flight
    (0x03F0, 0x0198),  # Pulsefire Haste 2 Wireless
    (0x03F0, 0x0199),  # Pulsefire Haste 2 Wireless
    (0x03F0, 0x01A1),  # Alloy Rise
    (0x03F0, 0x01B5),  # QuadCast 2 S
    (0x03F0, 0x01BE),  # Pulsefire Fuse
    (0x03F0, 0x01C0),  # SoloCast 2
    (0x03F0, 0x028B),  # Cloud II Wireless
    (0x03F0, 0x028D),  # CloudX Stinger Core Wireless
    (0x03F0, 0x0291),  # Cloud Flight
    (0x03F0, 0x0292),  # Cloud Buds
    (0x03F0, 0x02AF),  # Alloy Origins 265
    (0x03F0, 0x02B9),  # Alloy Rise 75 Wireless
    (0x03F0, 0x038C),  # QuadCast S
    (0x03F0, 0x038E),  # Pulsefire Haste Wireless
    (0x03F0, 0x0390),  # Pulsefire Raid
    (0x03F0, 0x0393),  # Alloy Origins
    (0x03F0, 0x0394),  # QuadCast S
    (0x03F0, 0x0398),  # Pulsefire Surge
    (0x03F0, 0x0399),  # Pulsefire Haste 2 Wireless
    (0x03F0, 0x03A1),  # Alloy Rise 75
    (0x03F0, 0x03B5),  # QuadCast 2 S
    (0x03F0, 0x048B),  # Cloud II Wireless
    (0x03F0, 0x048F),  # Alloy Origins 65
    (0x03F0, 0x0492),  # Cloud MIX
    (0x03F0, 0x04AF),  # Alloy Origins 2 Core
    (0x03F0, 0x058C),  # QuadCast S
    (0x03F0, 0x058D),  # Clutch
    (0x03F0, 0x058E),  # Pulsefire Haste Wireless
    (0x03F0, 0x0593),  # FURY Ultra
    (0x03F0, 0x0594),  # Pulsefire Haste
    (0x03F0, 0x0595),  # Clutch Gladiate
    (0x03F0, 0x0598),  # Pulsefire Core
    (0x03F0, 0x05A1),  # Alloy Core 2 RGB
    (0x03F0, 0x05B5),  # Pulsefire Haste 2 Core
    (0x03F0, 0x05BF),  # Pulsefire Saga Pro
    (0x03F0, 0x068B),  # Cloud II Wireless
    (0x03F0, 0x068F),  # Alloy Elite 2
    (0x03F0, 0x0691),  # Alloy Origins
    (0x03F0, 0x0692),  # SoloCast
    (0x03F0, 0x06AF),  # Alloy Origins 2
    (0x03F0, 0x078C),  # QuadCast S
    (0x03F0, 0x078D),  # Cloud Core Wireless
    (0x03F0, 0x078E),  # Pulsefire Dart
    (0x03F0, 0x0793),  # Pulsefire FPS Pro
    (0x03F0, 0x0794),  # Pulsefire Haste
    (0x03F0, 0x0799),  # Pulsefire Warp
    (0x03F0, 0x079F),  # Cloud II Core Wireless
    (0x03F0, 0x07BF),  # Pulsefire Saga Pro
    (0x03F0, 0x07C2),  # Eve 1800
    (0x03F0, 0x07C5),  # Origins 2 Pro 65
    (0x03F0, 0x088A),  # Cloud MIX Buds
    (0x03F0, 0x088B),  # SoloCast
    (0x03F0, 0x088D),  # Cloud Core Wireless
    (0x03F0, 0x0892),  # SoloCast
    (0x03F0, 0x0895),  # Cloud II Core Wireless
    (0x03F0, 0x08A0),  # Clutch Gladiate RGB
    (0x03F0, 0x08AF),  # QuadCast 2
    (0x03F0, 0x08B4),  # QuadCast 2
    (0x03F0, 0x098A),  # Cloud MIX Buds
    (0x03F0, 0x098E),  # Pulsefire Dart
    (0x03F0, 0x0996),  # Cloud II Core Wireless
    (0x03F0, 0x0999),  # Pulsefire Warp
    (0x03F0, 0x099D),  # Cloud III
    (0x03F0, 0x099F),  # Cloud II Core Wireless
    (0x03F0, 0x09C2),  # Origins 2 1800
    (0x03F0, 0x0A8B),  # SoloCast
    (0x03F0, 0x0A8D),  # Cloud Alpha Wireless
    (0x03F0, 0x0A8F),  # Alloy Origins Core
    (0x03F0, 0x0A92),  # SoloCast
    (0x03F0, 0x0A95),  # Cloud II Core Wireless
    (0x03F0, 0x0AAF),  # QuadCast 2
    (0x03F0, 0x0AB4),  # Clutch Tanto
    (0x03F0, 0x0AC0),  # FlipCast
    (0x03F0, 0x0B8C),  # DuoCast
    (0x03F0, 0x0B8E),  # Cloud Stinger Core Wireless
    (0x03F0, 0x0B90),  # CloudX Flight
    (0x03F0, 0x0B91),  # Cloud Flight For PS
    (0x03F0, 0x0B9B),  # Audio Mixer
    (0x03F0, 0x0B9D),  # Cirro Buds
    (0x03F0, 0x0B9F),  # Cloud II Core Wireless
    (0x03F0, 0x0BB5),  # Pulsefire Haste 2 Core Wireless
    (0x03F0, 0x0BBD),  # Pulsefire Haste 2 Pro
    (0x03F0, 0x0BC2),  # Origins 2 65
    (0x03F0, 0x0C8B),  # SoloCast
    (0x03F0, 0x0C8D),  # Cloud Alpha Wireless
    (0x03F0, 0x0C8F),  # Alloy MKW 100
    (0x03F0, 0x0C92),  # Cloud II
    (0x03F0, 0x0C97),  # Pulsefire Haste 2
    (0x03F0, 0x0CA0),  # Pulsefire Haste 2 Mini
    (0x03F0, 0x0CB8),  # Pulsefire Haste 2 S
    (0x03F0, 0x0CC0),  # FlipCast
    (0x03F0, 0x0D8C),  # Cloud Flight For PS
    (0x03F0, 0x0D8E),  # Alloy Origins 60
    (0x03F0, 0x0D90),  # CloudX Flight
    (0x03F0, 0x0D91),  # Cloud Alpha S
    (0x03F0, 0x0D9B),  # Audio Mixer
    (0x03F0, 0x0DB8),  # Pulsefire Haste 2 S
    (0x03F0, 0x0DBD),  # Pulsefire Haste 2 Pro
    (0x03F0, 0x0E8B),  # QuadCast S
    (0x03F0, 0x0E8D),  # Cloud Alpha Wireless
    (0x03F0, 0x0E93),  # Cloud Stinger 2 Wireless
    (0x03F0, 0x0E97),  # Pulsefire Haste 2 Wireless
    (0x03F0, 0x0EA0),  # Pulsefire Haste 2 Mini
    (0x03F0, 0x0EB4),  # QuadCast 2 S
    (0x03F0, 0x0F8C),  # Cloud Flight For PS
    (0x03F0, 0x0F90),  # Cloud Flight
    (0x03F0, 0x0F91),  # Cloud Revolver S
    (0x03F0, 0x0F92),  # Cloud Stinger S
    (0x03F0, 0x0FB8),  # Alloy Rise 75 Wireless Keyboard
    (0x03F0, 0x0FBE),  # Pulsefire Saga
    (0x0951, 0x16F5),  # Alloy Origins
    (0x0951, 0x16F6),  # Alloy Origins Core
    (0x0951, 0x16F8),  # Pulsefire Dart
    (0x0951, 0x16F9),  # Pulsefire Raid
    (0x0951, 0x1706),  # Fury Ultra
    (0x0951, 0x1712),  # Alloy Elite II
    (0x0951, 0x1720),  # QuadCast S
    (0x0951, 0x1728),  # Pulsefire Haste
    (0x0951, 0x172A),  # Pulsefire FPS Pro
    (0x0951, 0x1735),  # Alloy Origins 60
    (0x0951, 0x175F),  # DuoCast Controller
    (0x0951, 0x1774),  # QuadCast S 2s Wb
})

# Interfaces the vendor software only uses to detect the device or update its firmware.
DETECTION_ONLY: frozenset[tuple[int, int]] = frozenset({
    (0x03F0, 0x01CC),  # Cloud III S Wireless
    (0x03F0, 0x02C6),  # Cloud Stinger 3 Wireless
    (0x03F0, 0x05BE),  # Cloud III S Wireless
    (0x03F0, 0x06C1),  # CloudX Flight 2
    (0x03F0, 0x0BBE),  # Cloud Alpha 2 Wireless
    (0x03F0, 0x0BC1),  # Cloud Flight 2
    (0x03F0, 0x0CC5),  # CloudX Stinger 3 WL
    (0x03F0, 0x0FC5),  # Cloud Stinger 3 Wireless
})


def product(vid: int, pid: int) -> tuple[str, str] | None:
    return PRODUCTS.get((vid, pid))


def is_firmware_mode(vid: int, pid: int) -> bool:
    return (vid, pid) in FIRMWARE_MODE
