#!/usr/bin/env python3
"""Static analysis of the Cloud III S CM4 firmware (ARM Thumb).

    python -m tools.cloud3s.fwscan re/cm4.bin     # disassembly needs `pip install capstone`

1. strings mentioning ANC / pass-through / ambient mode;
2. RACE command ids as Thumb immediates (movw/cmp) and as raw u16 values, to see which
   command ranges the dispatcher handles.
"""
import re
import struct
import sys

BASE = 0x0818C000  # partition address in memory-mapped flash (XIP)

KEYWORDS = re.compile(rb"anc|ANC|Anc|hybrid|passthr|PassThr|PASSTHR|ambient|Ambient|AMBIENT|"
                      rb"hear.?through|feedforward|feedback|_ff_|_fb_|leak|howl|psap|PSAP", re.I)


def strings(data, n=5):
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % n, data):
        yield m.start(), m.group().decode()


def main(path):
    data = open(path, "rb").read()
    print(f"{path}: {len(data)} bytes")

    print("\n## relevant strings")
    hits = [(o, s) for o, s in strings(data) if KEYWORDS.search(s.encode())]
    for o, s in hits[:200]:
        print(f"  0x{BASE + o:08X}  {s[:120]}")
    print(f"  ({len(hits)} total)")

    print("\n## RACE ids 0x0E0x as raw u16 (tables)")
    for cid in (0x0E00, 0x0E01, 0x0E02, 0x0E03, 0x0E04, 0x0E05, 0x0E06, 0x0E07, 0x0E08, 0x0E10):
        pat = struct.pack("<H", cid)
        n = sum(1 for _ in re.finditer(re.escape(pat), data))
        print(f"  0x{cid:04X}: {n} raw hits")

    try:
        import capstone
    except ImportError:
        print("\n(capstone missing: pip install capstone)")
        return
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.skipdata = True
    print("\n## Thumb immediates equal to RACE ids of interest")
    want = {0x0E06: "ANC (0x0E06)", 0x0E00: "DSP realtime base", 0x0A00: "NVKEY read", 0x1C00: "FOTA",
            0x0403: "storage read", 0x0301: "SDK ver", 0x0F92: "log"}
    found = {k: [] for k in want}
    for ins in md.disasm(data, BASE):
        if ins.mnemonic in ("movw", "mov", "cmp", "movs", "cmp.w", "mov.w", "sub.w", "subw", "addw") and "#" in ins.op_str:
            try:
                imm = int(ins.op_str.split("#")[-1], 0)
            except ValueError:
                continue
            if imm in found:
                found[imm].append(ins.address)
    for k, addrs in found.items():
        print(f"  {want[k]:20} 0x{k:04X}: {len(addrs)} uses  {' '.join(hex(a) for a in addrs[:12])}")


if __name__ == "__main__":
    main(sys.argv[1])
