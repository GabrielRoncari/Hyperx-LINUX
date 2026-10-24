#!/usr/bin/env python3
"""List the NVKEYs of an Airoha NVDM partition dump (read only).

Format (worked out from the Cloud III S dump, 4 KiB blocks):
    block: "NVDM" + 8 bytes
    item : status(1) pnum(1) type(1) ff(1) offset(u16) group_len(1) name_len(1)
           size(u16) index(u16) seq(u32) hash(u32)
           group\\0 name\\0 value[size] checksum(u16)
    status 0xFC = valid; the copy with the highest seq wins.

    python3 -m tools.cloud3s.nvdm re/nvdm.bin      # all
    python3 -m tools.cloud3s.nvdm re/nvdm.bin E    # ids starting with E (DSP)
"""
import struct
import sys

BLOCK = 0x1000
HDR = struct.Struct("<BBBBHBBHHII")


def items(data: bytes):
    best = {}
    for base in range(0, len(data), BLOCK):
        if data[base:base + 4] != b"NVDM":
            continue
        off = base + 12
        while off + HDR.size < base + BLOCK:
            status, _pnum, _vtype, _r, _o, glen, nlen, size, _idx, seq, _hash = HDR.unpack_from(data, off)
            if status == 0xFF or glen == 0 or glen > 32 or nlen == 0 or nlen > 64:
                break
            p = off + HDR.size
            group = data[p:p + glen].rstrip(b"\0").decode("latin-1")
            name = data[p + glen:p + glen + nlen].rstrip(b"\0").decode("latin-1")
            value = data[p + glen + nlen:p + glen + nlen + size]
            if status == 0xFC and (name not in best or seq > best[name][0]):
                best[name] = (seq, group, value)
            off = p + glen + nlen + size + 2
    return {k: (g, v) for k, (_s, g, v) in best.items()}


def main(path, prefix=""):
    found = items(open(path, "rb").read())
    for name in sorted(found):
        if not name.upper().startswith(prefix.upper()):
            continue
        group, value = found[name]
        asc = bytes(c if 32 <= c < 127 else 46 for c in value[:40]).decode()
        print(f"{group}/{name:5} {len(value):5} B  {value[:20].hex(' '):60} |{asc}|")
    print(f"{len(found)} NVKEYs", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:])
