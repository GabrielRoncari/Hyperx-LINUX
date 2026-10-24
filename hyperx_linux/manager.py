"""Finds HyperX devices, opens a session per device and runs all device I/O off the UI thread.

Callbacks fire from worker threads; GUI code must hop to its main loop.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable

from .config import Config
from .controls import Control
from .drivers import Driver, Support, find_driver
from .hid import HidError, Node, NodeInfo, enumerate_nodes

SCAN_SECONDS = 2.0


class Session:
    """One connected device: its driver, its node and a worker thread."""

    def __init__(self, manager: "Manager", info: NodeInfo, driver_cls: type[Driver]):
        self.manager = manager
        self.info = info
        self.key = info.usb_path or info.path
        self.error: str | None = None
        self.node = Node(info)
        self.driver = driver_cls(self.node, self._on_driver_change)
        self.node.listeners.append(self.driver.handle_input)
        self.node.on_close = self._on_close
        self._jobs: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"session-{info.path}", daemon=True)
        self._online_seen = self.driver.online

    # --------------------------------------------------------------- helpers
    @property
    def name(self) -> str:
        return self.driver.name

    @property
    def driver_id(self) -> str:
        return self.driver.driver_id()

    @property
    def writable(self) -> bool:
        return self.driver.support != Support.EXPERIMENTAL or bool(self.manager.config["allow_experimental"])

    @property
    def closed(self) -> bool:
        return self.node.closed

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._jobs.put(None)
        self.node.close()

    def submit(self, fn: Callable[[], None]) -> None:
        self._jobs.put(fn)

    # ----------------------------------------------------------------- worker
    def _run(self) -> None:
        self._safe(self._connect)
        next_poll = time.monotonic() + self.driver.poll_seconds
        ka = self.driver.keepalive_seconds
        next_ka = time.monotonic() + ka if ka else None
        tick = min(0.25, ka / 2) if ka else 0.25
        while not self._stop.is_set() and not self.node.closed:
            now = time.monotonic()
            if now >= next_poll:
                self._safe(self.driver.poll)
                next_poll = now + self.driver.poll_seconds
            if next_ka and now >= next_ka:
                if not self.manager.paused:
                    self._safe(self.driver.keepalive)
                next_ka = now + ka
            try:
                job = self._jobs.get(timeout=tick)
            except queue.Empty:
                continue
            if job is None:
                break
            self._safe(job)

    def _safe(self, fn: Callable[[], None]) -> None:
        try:
            fn()
            if self.error:
                self.error = None
                self.manager._emit(self, "error", None)
        except (HidError, OSError, ValueError, KeyError, IndexError) as e:
            self.error = str(e)
            self.manager._emit(self, "error", self.error)

    def _connect(self) -> None:
        self.driver.refresh()
        if self.driver.online:
            self._reapply()

    def _reapply(self) -> None:
        """Controls the device can't report (e.g. EQ) are restored from the config."""
        if not self.writable:
            return
        saved = self.manager.config.device(self.driver_id)
        for c in self.driver.controls:
            if c.persist and c.id in saved and saved[c.id] is not None:
                self.driver.apply(c.id, saved[c.id])

    def _on_driver_change(self, key: str, value: object) -> None:
        if key == "online":
            if value and self._online_seen is False:
                self.submit(self._connect)  # headset came back: re-read and restore
            self._online_seen = value
        self.manager._emit(self, key, value)

    def _on_close(self) -> None:
        self.manager._remove(self)

    # ------------------------------------------------------------------ API
    def control(self, control_id: str) -> Control:
        return self.driver.control(control_id)

    def set(self, control_id: str, value: object, live: bool = False) -> None:
        """Write a control. live=True: intermediate value while dragging (EQ)."""
        if not self.writable:
            self.manager._emit(self, "error", "experimental driver: enable experimental drivers to change settings")
            return
        c = self.control(control_id)
        if not c.writable:
            return
        if c.persist:
            self.manager.config.set_device_value(self.driver_id, control_id, value)
        live_fn = getattr(self.driver, "write_eq_live", None) if live else None
        self.submit(lambda: live_fn(value) if live_fn else self.driver.apply(control_id, value))

    def refresh(self) -> None:
        self.submit(self.driver.refresh)


class Manager:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.sessions: dict[str, Session] = {}
        self.unsupported: list[NodeInfo] = []  # HyperX devices without a driver
        self.errors: dict[str, str] = {}  # usb path -> open error (e.g. permissions)
        self.paused = False  # stop lighting keep-alives (system going to sleep)
        self.on_change: Callable[[Session | None, str, object], None] = lambda s, k, v: None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._scan_loop, name="hyperx-scan", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            sessions = list(self.sessions.values())
        for s in sessions:
            s.stop()

    def scan_once(self) -> None:
        nodes = enumerate_nodes()
        groups: dict[str, list[NodeInfo]] = {}
        for n in nodes:
            groups.setdefault(n.usb_path or n.path, []).append(n)
        changed = False
        unsupported = []
        for key, group in groups.items():
            with self._lock:
                if key in self.sessions:
                    continue
            match = next(((n, d) for n in group for d in [find_driver(n)] if d), None)
            if match is None:
                unsupported.append(group[0])
                continue
            info, driver_cls = match
            try:
                session = Session(self, info, driver_cls)
            except HidError as e:
                if self.errors.get(key) != str(e):
                    self.errors[key] = str(e)
                    changed = True
                continue
            self.errors.pop(key, None)
            with self._lock:
                self.sessions[key] = session
            session.start()
            changed = True
        gone = [k for k in self.errors if k not in groups]
        for k in gone:
            del self.errors[k]
            changed = True
        if [n.usb_id for n in unsupported] != [n.usb_id for n in self.unsupported]:
            self.unsupported = unsupported
            changed = True
        if changed:
            self.on_change(None, "devices", None)

    def _scan_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception as e:  # never let discovery die
                self.errors["scan"] = str(e)
            self._stop.wait(SCAN_SECONDS)

    def _remove(self, session: Session) -> None:
        with self._lock:
            if self.sessions.get(session.key) is session:
                del self.sessions[session.key]
        self.on_change(None, "devices", None)

    def _emit(self, session: Session, key: str, value: object) -> None:
        self.on_change(session, key, value)

    def list(self) -> list[Session]:
        with self._lock:
            return sorted(self.sessions.values(), key=lambda s: (s.driver.kind.value, s.name))
