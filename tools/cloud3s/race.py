#!/usr/bin/env python3
"""Airoha RACE client over the HID interface of the headset on USB-C, with stream reassembly.

Reports 0x07 carry a byte stream (07 <len u16 LE> <up to 59 bytes>); RACE packets span
reports. The headset also streams its firmware debug log as indication 0x5D id 0x0F92 (text).

    RACE_DEV=/dev/hidrawN python3 -m tools.cloud3s.race log 20          # 20 s of log
    RACE_DEV=/dev/hidrawN python3 -m tools.cloud3s.race cmd 0301 [payload-hex]
    RACE_DEV=/dev/hidrawN python3 -m tools.cloud3s.race dump 0818C000 23E000 re/cm4.bin

`cmd` only accepts ids from the READ_ONLY list; `dump` only uses the read command 0x0403.
"""
from __future__ import annotations

import fcntl
import os
import select
import struct
import sys
import time

LOG_ID = 0x0F92
READ_ONLY = {
    0x0301: "SDK version",
    0x1E08: "build version",
    0x0D00: "relay: destinos",
    0x1C00: "FOTA partition info",
    0x0CD5: "BD address",
}


def hidiocginput(length: int) -> int:
    return (3 << 30) | (length << 16) | (ord("H") << 8) | 0x0A


def race(cmd_id: int, payload: bytes = b"", kind: int = 0x5A) -> bytes:
    return struct.pack("<BBHH", 0x05, kind, 2 + len(payload), cmd_id) + payload


class Race:
    def __init__(self, path: str):
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self.buf = bytearray()

    def close(self):
        os.close(self.fd)

    def send(self, pkt: bytes):
        os.write(self.fd, (bytes([0x06]) + struct.pack("<H", len(pkt)) + pkt).ljust(62, b"\0"))

    def _chunk(self, data: bytes):
        if data and data[0] == 0x07:
            ln = struct.unpack_from("<H", data, 1)[0]
            self.buf += data[3:3 + ln]

    def pump(self) -> bool:
        """Drain what is available (interrupt + GET_REPORT). True if anything arrived."""
        got = False
        while True:
            r, _, _ = select.select([self.fd], [], [], 0)
            if not r:
                break
            self._chunk(os.read(self.fd, 64))
            got = True
        for _ in range(64):
            b = bytearray(62)
            b[0] = 0x07
            fcntl.ioctl(self.fd, hidiocginput(62), b)
            if not struct.unpack_from("<H", b, 1)[0]:
                break
            self._chunk(bytes(b))
            got = True
        return got

    def frames(self):
        """Pull complete packets out of the stream: (type, id, payload)."""
        out = []
        while True:
            i = self.buf.find(0x05)
            if i < 0:
                self.buf.clear()
                break
            del self.buf[:i]
            if len(self.buf) < 6:
                break
            kind, ln, cid = struct.unpack_from("<BHH", self.buf, 1)
            if kind not in (0x5A, 0x5B, 0x5C, 0x5D) or ln < 2 or ln > 4096:
                del self.buf[:1]  # not the start of a packet
                continue
            if len(self.buf) < 4 + ln:
                break
            out.append((kind, cid, bytes(self.buf[6:4 + ln])))
            del self.buf[:4 + ln]
        return out

    def request(self, cid: int, payload: bytes = b"", timeout: float = 2.0) -> bytes | None:
        """Send a 0x5A request and wait for the 0x5B response with the same id (ignores the log)."""
        self.send(race(cid, payload))
        found: list[bytes] = []

        def match(kind, cid_, pl):
            if kind == 0x5B and cid_ == cid:
                found.append(pl)
                return True
            return False
        self.run(timeout, match)
        return found[0] if found else None

    def read_flash(self, addr: int) -> bytes | None:
        """RACE_STORAGE_PAGE_READ (0x0403): 256 bytes of flash, read only."""
        pl = self.request(0x0403, bytes([0, 1]) + struct.pack("<I", addr))
        if not pl or len(pl) < 8 or pl[0] != 0:
            return None
        if struct.unpack_from("<I", pl, 4)[0] != addr:
            return None
        return pl[8:8 + 256]

    def run(self, seconds: float, on_frame):
        end = time.time() + seconds
        while time.time() < end:
            if not self.pump():
                time.sleep(0.02)
            for f in self.frames():
                if on_frame(*f):
                    return True
        return False


def text(payload: bytes) -> str:
    return payload.decode("latin-1").rstrip("\r\n")


def main(argv):
    rc = Race(os.environ.get("RACE_DEV", "/dev/hidraw8"))
    try:
        if argv[0] == "log":
            secs = float(argv[1]) if len(argv) > 1 else 15

            def show(kind, cid, pl):
                if cid == LOG_ID:
                    print(f"{time.strftime('%H:%M:%S')} {text(pl)}", flush=True)
                else:
                    print(f"{time.strftime('%H:%M:%S')} [0x{kind:02X} 0x{cid:04X}] {pl.hex(' ')}", flush=True)
            rc.run(secs, show)
        elif argv[0] == "dump":  # dump ADDR SIZE ARQUIVO (hex)
            rc.run(0.3, lambda *f: None)
            dump(rc, int(argv[1], 16), int(argv[2], 16), argv[3])
        elif argv[0] == "cmd":
            cid = int(argv[1], 16)
            if cid not in READ_ONLY:
                sys.exit(f"0x{cid:04X} is not in the read-only list")
            payload = bytes.fromhex(" ".join(argv[2:]))
            rc.run(0.5, lambda *f: None)  # drop whatever was queued
            rc.send(race(cid, payload))

            def match(kind, cid_, pl):
                if cid_ == LOG_ID:
                    return False
                asc = bytes(c if 32 <= c < 127 else 46 for c in pl).decode()
                print(f"[0x{kind:02X} 0x{cid_:04X}] {pl.hex(' ')}\n    ascii: {asc}")
                return cid_ == cid and kind == 0x5B
            if not rc.run(3, match):
                print("no 0x5B response")
    finally:
        rc.close()



def dump(rc: Race, addr: int, size: int, out: str) -> None:
    """Read [addr, addr+size) page by page into `out`, 3 attempts per page."""
    t0 = time.time()
    with open(out, "wb") as f:
        for a in range(addr, addr + size, 0x100):
            for _ in range(3):
                page = rc.read_flash(a)
                if page is not None:
                    break
            else:
                raise SystemExit(f"failed reading 0x{a:08X}")
            f.write(page)
            done = a + 0x100 - addr
            if done % 0x10000 == 0:
                print(f"{out}: {done // 1024}/{size // 1024} KiB ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["log"])
