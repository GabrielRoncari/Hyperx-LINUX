"""Test doubles: a hidraw node that records writes and answers like a device would."""
from __future__ import annotations

import threading
from typing import Callable


class FakeNode:
    def __init__(self, responder: Callable[[bytes], bytes | None] = lambda pkt: None):
        self.responder = responder
        self.written: list[bytes] = []
        self.features: list[bytes] = []
        self.closed = False
        self.listeners = []
        self.lock = threading.Lock()
        self.feature_reply: Callable[[int, int], bytes] = lambda rid, n: bytes([rid]) + bytes(n - 1)

    def write(self, report: bytes) -> None:
        self.written.append(bytes(report))

    def send(self, report: bytes, gap: float = 0) -> None:
        self.write(report)

    def set_feature(self, report: bytes) -> None:
        self.features.append(bytes(report))

    def get_feature(self, report_id: int, length: int) -> bytes:
        return self.feature_reply(report_id, length)

    def get_input(self, report_id: int, length: int) -> bytes:
        return bytes([report_id]) + bytes(length - 1)

    def request(self, send, match, timeout=1.0, gap=0):
        before = len(self.written) + len(self.features)
        send()
        sent = (self.written + self.features)[before:]
        reply = self.responder(sent[-1]) if sent else None
        return reply if reply is not None and match(reply) else None


class Recorder:
    """Collects driver notifications."""

    def __init__(self):
        self.events: list[tuple[str, object]] = []

    def __call__(self, key, value):
        self.events.append((key, value))
