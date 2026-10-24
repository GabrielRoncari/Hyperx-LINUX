"""Transport of the HP-era "Universal" protocol (NGENUITY 3), shared by mice, headsets and keyboards.

Request = 64-byte output report whose report id is the command: [0]=cmd [1]=sub [2..]=payload.
Read reply = input report cmd+1 with the same sub. Every request is also acknowledged with
FF 01 <12-byte device id> <cmd> <sub> <status>; writes only get the ack.
Never sent: 10 02 / 12 01 (factory reset), report ids 30/F0/FA/FC (firmware), slot 1 writes in
loops (onboard flash), 70 04 / 70 07 (pairing). See docs/devices/universal.md
"""
from __future__ import annotations

from ..controls import BatteryValue
from .base import Driver

BATTERY = (0x50, 0x02)
LINK = (0x52, 0x01)
REPORT_ACK, REPORT_EVENT = 0xFF, 0xFB
EV_LINK = 0x0A


class UniversalDevice(Driver):
    @staticmethod
    def _packet(cmd_sub: tuple[int, int], *payload: int) -> bytes:
        p = bytearray(64)
        p[0], p[1] = cmd_sub
        p[2:2 + len(payload)] = bytes(b & 0xFF for b in payload)
        return bytes(p)

    def _read(self, cmd_sub, *payload) -> bytes | None:
        pkt = self._packet(cmd_sub, *payload)
        cmd, sub = cmd_sub
        return self.node.request(lambda: self.node.write(pkt),
                                 lambda r: len(r) >= 16 and r[0] == cmd + 1 and r[1] == sub)

    def _write(self, cmd_sub, *payload) -> bool:
        """Send and wait for the ack; True when the device accepted it."""
        pkt = self._packet(cmd_sub, *payload)
        cmd, sub = cmd_sub
        ack = self.node.request(lambda: self.node.write(pkt),
                                lambda r: len(r) >= 17 and r[0] == REPORT_ACK and r[1] in (0x01, 0x02)
                                and r[14] == cmd and r[15] == sub)
        return ack is not None and ack[1] == 0x01 and ack[16] == 0  # FF 02 = NACK

    def _read_link(self) -> bool:
        link = self._read(LINK)
        self.set_online(bool(link and link[2] == 1))
        return bool(self.online)

    def _read_battery(self) -> None:
        r = self._read(BATTERY)
        if r:
            self._parse_battery(r)

    def _parse_battery(self, r: bytes) -> None:
        """51 02 <%> <state 0 bat/1 charging/2 full> <temp i16> <mV u16 LE> ..."""
        state = r[3]  # 0 battery, 1 charging, 2 full, 3 charger error, FF unknown
        mv = r[6] | (r[7] << 8)
        self.set_value("battery", BatteryValue(level=r[2], charging=state == 1 if state <= 2 else None,
                                               full=state == 2,
                                               voltage_mv=mv if 2500 < mv < 5000 else None))
