"""hidraw transport, stdlib only.

- enumerate(): every hidraw node with its USB identity and parsed report descriptor
- Node: open node with a reader thread, output/feature/input report helpers and
  a request() helper that writes a packet and waits for a matching input report
"""
from __future__ import annotations

import errno
import fcntl
import glob
import os
import select
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

HYPERX_VIDS = (0x0951, 0x03F0)  # Kingston (older devices), HP (newer devices)

# ioctl numbers from <linux/hidraw.h>: _IOC(_IOC_READ|_IOC_WRITE, 'H', nr, len)
_IOC_RW = 3


def _hidioc(nr: int, length: int) -> int:
    return (_IOC_RW << 30) | (length << 16) | (ord("H") << 8) | nr


HIDIOCSFEATURE, HIDIOCGFEATURE, HIDIOCGINPUT, HIDIOCSOUTPUT = 0x06, 0x07, 0x0A, 0x0B


class HidError(Exception):
    pass


# ---------------------------------------------------------------- descriptor
@dataclass
class Collection:
    usage_page: int
    usage: int
    report_ids: set[int] = field(default_factory=set)


@dataclass
class Descriptor:
    collections: list[Collection] = field(default_factory=list)
    # (kind, report_id) -> size in bytes, without the report id; kind: "in", "out", "feature"
    reports: dict[tuple[str, int], int] = field(default_factory=dict)

    def has_page(self, page: int, usage: int | None = None) -> bool:
        return any(c.usage_page == page and (usage is None or c.usage == usage) for c in self.collections)

    def report_size(self, kind: str, report_id: int) -> int | None:
        return self.reports.get((kind, report_id))


def parse_descriptor(data: bytes) -> Descriptor:
    """Small HID report descriptor parser: top-level collections and report sizes."""
    desc = Descriptor()
    page = rsize = rcount = rid = 0
    stack: list[tuple[int, int, int, int]] = []
    usages: list[int] = []
    depth = 0
    bits: dict[tuple[str, int], int] = {}
    top: Collection | None = None
    i = 0
    while i < len(data):
        prefix = data[i]
        if prefix == 0xFE:  # long item
            i += 3 + (data[i + 1] if i + 1 < len(data) else 0)
            continue
        size = (0, 1, 2, 4)[prefix & 3]
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        raw = data[i + 1:i + 1 + size]
        value = int.from_bytes(raw, "little") if raw else 0
        i += 1 + size
        if kind == 1:  # global
            if tag == 0x0:
                page = value
            elif tag == 0x7:
                rsize = value
            elif tag == 0x8:
                rid = value
                if top is not None:
                    top.report_ids.add(rid)
            elif tag == 0x9:
                rcount = value
            elif tag == 0xA:
                stack.append((page, rsize, rcount, rid))
            elif tag == 0xB and stack:
                page, rsize, rcount, rid = stack.pop()
        elif kind == 2:  # local
            if tag == 0x0:
                usages.append(value if size == 4 else (page << 16) | value)
        elif kind == 0:  # main
            if tag == 0xA:  # collection
                if depth == 0:
                    u = usages[0] if usages else 0
                    top = Collection(usage_page=(u >> 16) or page, usage=u & 0xFFFF)
                    desc.collections.append(top)
                depth += 1
            elif tag == 0xC:  # end collection
                depth = max(0, depth - 1)
                if depth == 0:
                    top = None
            elif tag in (0x8, 0x9, 0xB):
                name = {0x8: "in", 0x9: "out", 0xB: "feature"}[tag]
                bits[(name, rid)] = bits.get((name, rid), 0) + rsize * rcount
                if top is not None and rid:
                    top.report_ids.add(rid)
            usages = []
    desc.reports = {k: (v + 7) // 8 for k, v in bits.items()}
    return desc


# ----------------------------------------------------------------- enumerate
@dataclass
class NodeInfo:
    path: str  # /dev/hidrawN
    vid: int
    pid: int
    bus: int  # 3 = USB, 5 = Bluetooth
    name: str
    interface: int | None  # USB interface number
    usb_path: str | None  # sysfs path of the USB device (groups the interfaces of one device)
    bcd_device: int | None
    descriptor: Descriptor
    raw_descriptor: bytes

    @property
    def usb_id(self) -> str:
        return f"{self.vid:04x}:{self.pid:04x}"


def _read(path: str, binary: bool = False):
    try:
        with open(path, "rb" if binary else "r") as f:
            return f.read() if binary else f.read().strip()
    except OSError:
        return None


def enumerate_nodes(vids: tuple[int, ...] = HYPERX_VIDS) -> list[NodeInfo]:
    nodes = []
    for sysnode in sorted(glob.glob("/sys/class/hidraw/hidraw*"), key=lambda p: int(p.rsplit("hidraw", 1)[1])):
        uevent = _read(f"{sysnode}/device/uevent") or ""
        props = dict(line.split("=", 1) for line in uevent.splitlines() if "=" in line)
        try:
            bus, vid, pid = (int(x, 16) for x in props.get("HID_ID", "").split(":"))
        except ValueError:
            continue
        if vid not in vids:
            continue
        raw = _read(f"{sysnode}/device/report_descriptor", binary=True) or b""
        interface = usb_path = bcd = None
        if bus == 3:
            # .../usb1/1-3/1-3:1.3/0003:03F0:02CC.0007 -> interface dir 1-3:1.3, device dir 1-3
            hid_dir = os.path.realpath(f"{sysnode}/device")
            iface_dir = os.path.dirname(hid_dir)
            try:
                interface = int(os.path.basename(iface_dir).rsplit(".", 1)[1])
            except (IndexError, ValueError):
                interface = None
            usb_path = os.path.dirname(iface_dir)
            bcd_s = _read(f"{usb_path}/bcdDevice")
            bcd = int(bcd_s, 16) if bcd_s else None
        nodes.append(NodeInfo(
            path=f"/dev/{os.path.basename(sysnode)}", vid=vid, pid=pid, bus=bus,
            name=props.get("HID_NAME", ""), interface=interface, usb_path=usb_path,
            bcd_device=bcd, descriptor=parse_descriptor(raw), raw_descriptor=raw,
        ))
    return nodes


# ---------------------------------------------------------------------- node
class Node:
    """An open hidraw node. A reader thread hands every input report to the listeners."""

    def __init__(self, info: NodeInfo):
        self.info = info
        try:
            self.fd = os.open(info.path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as e:
            raise HidError(f"no permission on {info.path}: install the udev rules") from e
        except OSError as e:
            raise HidError(f"cannot open {info.path}: {e}") from e
        self.listeners: list[Callable[[bytes], None]] = []
        self.on_close: Callable[[], None] | None = None
        self.lock = threading.Lock()  # serialises request/response exchanges
        self._cv = threading.Condition()
        self._inbox: list[bytes] = []
        self._watching = 0
        self._closed = False
        self._thread = threading.Thread(target=self._reader, name=f"hid-{info.path}", daemon=True)
        self._thread.start()

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            try:
                os.close(self.fd)
            except OSError:
                pass

    def _reader(self) -> None:
        while not self._closed:
            try:
                ready, _, _ = select.select([self.fd], [], [], 0.5)
                if not ready:
                    continue
                data = os.read(self.fd, 4096)
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    continue
                break  # ENODEV: unplugged
            except (ValueError, TypeError):
                break  # fd closed under us
            if not data:
                continue
            with self._cv:
                if self._watching:
                    self._inbox.append(data)
                    self._cv.notify_all()
            for cb in list(self.listeners):
                try:
                    cb(data)
                except Exception:  # a buggy listener must not kill the reader
                    pass
        was_open = not self._closed
        self.close()
        if was_open and self.on_close:
            self.on_close()

    # -------------------------------------------------------------- writes
    def write(self, report: bytes) -> None:
        """Output report; first byte is the report id (0 if the device has none)."""
        if self._closed:
            raise HidError("device closed")
        try:
            os.write(self.fd, report)
        except OSError as e:
            raise HidError(f"write failed: {e}") from e

    def set_feature(self, report: bytes) -> None:
        buf = bytearray(report)
        try:
            fcntl.ioctl(self.fd, _hidioc(HIDIOCSFEATURE, len(buf)), buf)
        except OSError as e:
            raise HidError(f"set_feature failed: {e}") from e

    def get_feature(self, report_id: int, length: int) -> bytes:
        """length includes the report id byte."""
        buf = bytearray(length)
        buf[0] = report_id
        try:
            n = fcntl.ioctl(self.fd, _hidioc(HIDIOCGFEATURE, length), buf)
        except OSError as e:
            raise HidError(f"get_feature failed: {e}") from e
        return bytes(buf[:n] if isinstance(n, int) and n > 0 else buf)

    def get_input(self, report_id: int, length: int) -> bytes:
        buf = bytearray(length)
        buf[0] = report_id
        try:
            n = fcntl.ioctl(self.fd, _hidioc(HIDIOCGINPUT, length), buf)
        except OSError as e:
            raise HidError(f"get_input failed: {e}") from e
        return bytes(buf[:n] if isinstance(n, int) and n > 0 else buf)

    # ------------------------------------------------------------ exchange
    def request(self, send: Callable[[], None], match: Callable[[bytes], bool],
                timeout: float = 1.0, gap: float = 0.01) -> bytes | None:
        """Run send() and wait for the first input report accepted by match()."""
        with self.lock:
            with self._cv:
                self._inbox.clear()
                self._watching += 1
            try:
                send()
                deadline = time.monotonic() + timeout
                with self._cv:
                    while True:
                        for r in self._inbox:
                            if match(r):
                                return r
                        self._inbox.clear()
                        left = deadline - time.monotonic()
                        if left <= 0 or self._closed:
                            return None
                        self._cv.wait(left)
            finally:
                with self._cv:
                    self._watching -= 1
                time.sleep(gap)

    def send(self, report: bytes, gap: float = 0.01) -> None:
        """Fire-and-forget output report, serialised with request()."""
        with self.lock:
            self.write(report)
            time.sleep(gap)
