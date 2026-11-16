#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
#
# Wrap an FDT in the 64-byte Samsung DTB header used by the Exynos
# bootloader.  The bootloader rejects a plain FDT (d00dfeed) with
# FDT_EAR_BADMAGIC, and the dtbo overlay needs the __symbols__ node, so the
# input FDT must be built with dtc -@.
#
# Usage:
#   scripts/wrap_samsung_dtb.py \
#       --template arch/arm64/boot/dts/exynos/exynos9830.dtb \
#       --input  out/arch/arm64/boot/dts/exynos/exynos9830.dtb \
#       --output out/arch/arm64/boot/dts/exynos/exynos9830.dtb
#
# The template only supplies the 64-byte header.  The header size fields are
# updated for the new FDT.  The output is padded to the 2048-byte boot page.

import argparse
import struct
import sys

SAMSUNG_MAGIC = b"\xd7\xb7\xab\x1e"
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
HEADER_SIZE = 64
PAGE_SIZE = 2048


def fail(message):
    print("error: " + message, file=sys.stderr)
    sys.exit(1)


def read_file(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        fail("cannot read %s: %s" % (path, exc))


def read_word_le(buffer, offset):
    return struct.unpack_from("<I", buffer, offset)[0]


def read_word_be(buffer, offset):
    return struct.unpack_from(">I", buffer, offset)[0]


def extract_fdt(payload, path):
    if payload[:4] == FDT_MAGIC:
        return payload

    if payload[:4] == SAMSUNG_MAGIC:
        if len(payload) < HEADER_SIZE + 8:
            fail("%s is shorter than the Samsung header" % path)
        if payload[HEADER_SIZE:HEADER_SIZE + 4] != FDT_MAGIC:
            fail("%s has the Samsung magic but no FDT at offset %d" %
                 (path, HEADER_SIZE))
        return payload[HEADER_SIZE:]

    fail("%s is neither a plain FDT nor a Samsung-wrapped DTB" % path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True,
                        help="existing Samsung DTB that supplies the 64-byte header")
    parser.add_argument("--input", required=True,
                        help="plain FDT or Samsung-wrapped DTB to wrap")
    parser.add_argument("--output", required=True,
                        help="output path (may be the same as --input)")
    parser.add_argument("--allow-missing-symbols", action="store_true",
                        help="do not fail when the FDT lacks __symbols__")
    args = parser.parse_args()

    template = read_file(args.template)
    payload = read_file(args.input)

    if template[:4] != SAMSUNG_MAGIC:
        fail("%s does not start with the Samsung DTB magic" % args.template)
    if len(template) < HEADER_SIZE + 8:
        fail("%s is too short to contain a Samsung header" % args.template)
    if template[HEADER_SIZE:HEADER_SIZE + 4] != FDT_MAGIC:
        fail("%s has no FDT at offset %d" % (args.template, HEADER_SIZE))

    fdt = extract_fdt(payload, args.input)
    fdt_size = read_word_be(fdt, 4)
    if fdt_size < 8 or fdt_size > len(fdt):
        fail("invalid FDT totalsize %#x in %s" % (fdt_size, args.input))
    fdt = fdt[:fdt_size]

    if b"__symbols__" not in fdt and not args.allow_missing_symbols:
        fail("the FDT has no __symbols__ node; build it with dtc -@ "
             "(see DTC_FLAGS in arch/arm64/boot/dts/exynos/Makefile)")

    header = bytearray(template[:HEADER_SIZE])
    # The Samsung header stores its size fields in big-endian order, like the
    # FDT header.  Word 1 is the total image size and word 8 is the FDT size.
    struct.pack_into(">I", header, 4, fdt_size + HEADER_SIZE)
    struct.pack_into(">I", header, 32, fdt_size)

    output = bytes(header) + fdt
    output += b"\0" * ((-len(output)) % PAGE_SIZE)

    try:
        with open(args.output, "wb") as handle:
            handle.write(output)
    except OSError as exc:
        fail("cannot write %s: %s" % (args.output, exc))

    print("wrapped %s: fdt=%d image=%d (total %#x, fdt %#x)" %
          (args.output, fdt_size, len(output),
           read_word_be(header, 4), read_word_be(header, 32)))


if __name__ == "__main__":
    main()
