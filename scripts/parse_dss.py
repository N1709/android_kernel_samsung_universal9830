#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
#
# Parse a dump produced by scripts/dump_dss.sh.
#
# The Samsung bootloader and every Samsung-based kernel keep a small
# control block at 0xFD900000 and a 2 MiB printk ring at 0xFD910000.
# The control block survives a warm reset, and the ring is not cleared by
# the next kernel when the saved write pointer (offset 0x200) is valid.
# That makes the ring the only usable boot log on a device without UART.
#
# Usage:
#   scripts/parse_dss.py /tmp/dss

import argparse
import re
import struct
import sys
from pathlib import Path

ITEM_INFO_OFFSET = 0x900
ITEM_NAME_LEN = 16
ITEM_STRUCT_SIZE = ITEM_NAME_LEN + 4 + 4 + 4
KERNEL_ITEM_NAME = b"log_kernel"
PRINTABLE = re.compile(rb"[\x20-\x7e]{6,}")


def u32(buf, off):
    if off + 4 > len(buf):
        return None
    return struct.unpack_from("<I", buf, off)[0]


def parse_header(path):
    data = path.read_bytes()
    print("== control block %s (%d bytes)" % (path, len(data)))
    print("   last_kernel_logbuf : %#x" % (u32(data, 0x200) or 0))
    print("   last_platform_logbuf: %#x" % (u32(data, 0x280) or 0))
    print("   bl boot count       : magic=%#x count=%d" %
          (u32(data, 0x250) or 0, u32(data, 0x254) or 0))
    print("   kernel boot count   : magic=%#x count=%d" %
          (u32(data, 0x260) or 0, u32(data, 0x264) or 0))
    print("   panic stat          : %#x" % (u32(data, 0x500) or 0))

    magic1 = u32(data, ITEM_INFO_OFFSET)
    magic2 = u32(data, ITEM_INFO_OFFSET + 4)
    count = u32(data, ITEM_INFO_OFFSET + 8)
    if magic1 != 0x01234567 or magic2 != 0x89ABCDEF or not count:
        print("   item table: not present (kernel did not reach debug-snapshot init)")
        return data, None

    print("   item table (%d entries):" % count)
    kernel_paddr = None
    kernel_size = None
    for index in range(min(count, 16)):
        off = ITEM_INFO_OFFSET + 12 + index * ITEM_STRUCT_SIZE
        name = data[off:off + ITEM_NAME_LEN].split(b"\0", 1)[0]
        paddr = u32(data, off + ITEM_NAME_LEN)
        size = u32(data, off + ITEM_NAME_LEN + 4)
        enabled = u32(data, off + ITEM_NAME_LEN + 8)
        print("     %-16s paddr=%#010x size=%#09x enabled=%d" %
              (name.decode("ascii", "replace"), paddr, size, enabled))
        if name == KERNEL_ITEM_NAME:
            kernel_paddr = paddr
            kernel_size = size
    return data, (kernel_paddr, kernel_size)


def extract_strings(blob, base=0):
    out = []
    for match in PRINTABLE.finditer(blob):
        out.append((base + match.start(), match.group().decode("ascii", "replace")))
    return out


def parse_ring(path, paddr, size, last_buf):
    data = path.read_bytes()
    print("== kernel ring %s (%d bytes)" % (path, len(data)))
    if not data.strip(b"\0"):
        print("   ring is empty (kernel never logged to debug-snapshot)")
        return
    offset = 0
    if paddr and last_buf and paddr <= last_buf <= paddr + size:
        offset = last_buf - paddr
        print("   write pointer offset: %#x (last boot ended here)" % offset)
    ordered = data[offset:] + data[:offset]
    lines = extract_strings(ordered, offset - len(data))
    if not lines:
        print("   no printable text found")
        return
    print("   %d strings, oldest first:" % len(lines))
    for _, line in lines:
        print("   | " + line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dumpdir", help="directory written by dump_dss.sh")
    parser.add_argument("--max-strings", type=int, default=0,
                        help="only print the last N ring strings")
    args = parser.parse_args()

    dumpdir = Path(args.dumpdir)
    header_path = dumpdir / "dss_header.bin"
    if not header_path.exists():
        print("error: %s not found" % header_path, file=sys.stderr)
        sys.exit(1)

    header, item = parse_header(header_path)
    last_buf = u32(header, 0x200) or 0

    ring_path = dumpdir / "log_kernel.bin"
    if ring_path.exists() and ring_path.stat().st_size:
        if item:
            paddr, size = item
        else:
            paddr, size = 0xFD910000, 0x200000
        if args.max_strings:
            # Reuse parse_ring, but trim its output afterwards would be
            # awkward; print the tail by scanning the ordered buffer here.
            data = ring_path.read_bytes()
            offset = 0
            if paddr and last_buf and paddr <= last_buf <= paddr + size:
                offset = last_buf - paddr
            ordered = data[offset:] + data[:offset]
            lines = extract_strings(ordered)
            for _, line in lines[-args.max_strings:]:
                print("| " + line)
        else:
            parse_ring(ring_path, paddr, size, last_buf)

    pstore = dumpdir / "log_pstore.bin"
    if pstore.exists() and pstore.stat().st_size:
        print("== pstore %s (%d bytes)" % (pstore, pstore.stat().st_size))
        for _, line in extract_strings(pstore.read_bytes()):
            print("   | " + line)

    pstore_dir = dumpdir / "pstore"
    if pstore_dir.is_dir():
        print("== /sys/fs/pstore files")
        for entry in sorted(pstore_dir.iterdir()):
            print("   %s (%d bytes)" % (entry.name, entry.stat().st_size))


if __name__ == "__main__":
    main()
