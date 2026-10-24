#!/usr/bin/env python3
"""RE helper for the Cloud III S: send every known GET and print the raw reply.

GETs only; nothing is changed on the headset.
    python3 -m tools.cloud3s.probe
"""
from hyperx_linux.drivers import cloud3s as P
from hyperx_linux.hid import Node, enumerate_nodes

GETS = {name: op for name, op in vars(P).items() if name.startswith("OP_GET_")}


def main():
    info = next(n for n in enumerate_nodes() if P.Cloud3SWireless.match(n))
    node = Node(info)
    drv = P.Cloud3SWireless(node, lambda k, v: None)
    try:
        for name, op in sorted(GETS.items(), key=lambda kv: kv[1]):
            r = drv._get(op)
            raw = r[:16].hex(" ") if r else "(no reply)"
            print(f"{name:24} 0x{op:02X}  {raw}")
    finally:
        node.close()


if __name__ == "__main__":
    main()
