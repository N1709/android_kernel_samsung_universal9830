#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
#
# Repack an Android boot image (v2) with a new arm64 Image and a
# Samsung-wrapped Exynos DTB.  The template supplies the ramdisk, load
# addresses, cmdline and padding; only the kernel and DTB are replaced.
#
# The Samsung bootloader expects the DTB after the page-aligned ramdisk and
# uses the dtb_size/dtb_addr fields in the v2 header.  A plain FDT will be
# rejected with FDT_EAR_BADMAGIC; use scripts/wrap_samsung_dtb.py first.
#
# Usage:
#   scripts/repack_bootimg.py \
#       --template boot-working.img \
#       --kernel  out/arch/arm64/boot/Image \
#       --dtb     out/arch/arm64/boot/dts/exynos/exynos9830.dtb \
#       --output  boot-v420.img

import argparse
import os
import struct
import sys

ANDROID_MAGIC = b"ANDROID!"
SAMSUNG_MAGIC = b"\xd7\xb7\xab\x1e"
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
ARM64_MAGIC = b"ARM\x64"
PAGE_SIZE = 2048
MAX_BOOT_SIZE = 64 * 1024 * 1024


def fail(message):
    print("error: " + message, file=sys.stderr)
    sys.exit(1)


def read_file(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        fail("cannot read %s: %s" % (path, exc))


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def get_u32(buffer, offset):
    return struct.unpack_from("<I", buffer, offset)[0]


def set_u32(buffer, offset, value):
    struct.pack_into("<I", buffer, offset, value)


def get_u64(buffer, offset):
    return struct.unpack_from("<Q", buffer, offset)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True,
                        help="working boot image with the same ROM ramdisk")
    parser.add_argument("--kernel", required=True,
                        help="uncompressed arm64 Image")
    parser.add_argument("--dtb", required=True,
                        help="Samsung-wrapped DTB (d7b7ab1e header)")
    parser.add_argument("--output", required=True,
                        help="output boot image")
    args = parser.parse_args()

    template = bytearray(read_file(args.template))
    kernel = read_file(args.kernel)
    dtb = read_file(args.dtb)

    if len(template) < PAGE_SIZE or template[:8] != ANDROID_MAGIC:
        fail("%s is not an Android boot image" % args.template)
    if kernel[0x38:0x3c] != ARM64_MAGIC:
        fail("%s is not an uncompressed arm64 Image (use Image, not Image.gz)"
             % args.kernel)
    if dtb[:4] != SAMSUNG_MAGIC:
        fail("%s has no Samsung DTB header; run scripts/wrap_samsung_dtb.py first"
             % args.dtb)
    if dtb[64:68] != FDT_MAGIC:
        fail("%s has no FDT at offset 64" % args.dtb)

    page_size = get_u32(template, 36)
    header_version = get_u32(template, 40)
    kernel_size = get_u32(template, 8)
    ramdisk_size = get_u32(template, 16)
    second_size = get_u32(template, 24)
    recovery_dtbo_size = get_u32(template, 1632)
    header_size = get_u32(template, 1644)
    header_dtb_size = get_u32(template, 1648)
    dtb_addr = get_u64(template, 1652)

    if page_size != PAGE_SIZE:
        fail("unsupported boot image page size %d (expected %d)" %
             (page_size, PAGE_SIZE))
    if header_version != 2:
        fail("unsupported boot header version %d (expected 2)" % header_version)
    if header_size < 1660 or header_size > page_size:
        fail("invalid boot header size %d" % header_size)
    if second_size != 0:
        fail("template has a second stage (%d bytes); not supported" % second_size)
    if recovery_dtbo_size != 0:
        fail("template has a recovery dtbo (%d bytes); not supported" %
             recovery_dtbo_size)
    if header_dtb_size and header_dtb_size != len(dtb):
        print("note: template dtb_size=%d, new dtb_size=%d" %
              (header_dtb_size, len(dtb)), file=sys.stderr)

    kernel_offset = page_size
    ramdisk_offset = align(kernel_offset + len(kernel), page_size)
    dtb_offset = align(ramdisk_offset + ramdisk_size, page_size)
    image_end = dtb_offset + len(dtb)
    output_size = max(len(template), image_end)
    if output_size > MAX_BOOT_SIZE:
        fail("new image is %d bytes, larger than the %d-byte boot limit" %
             (output_size, MAX_BOOT_SIZE))
    output_size = align(output_size, 1024 * 1024)

    # Copy the template ramdisk.  It starts after the template kernel.
    template_ramdisk_offset = align(page_size + kernel_size, page_size)
    if template_ramdisk_offset + ramdisk_size > len(template):
        fail("template ramdisk is outside the file")
    ramdisk = template[template_ramdisk_offset:
                       template_ramdisk_offset + ramdisk_size]
    if len(ramdisk) != ramdisk_size:
        fail("short template ramdisk")

    header = bytearray(template[:page_size])
    set_u32(header, 8, len(kernel))
    set_u32(header, 16, len(ramdisk))
    set_u32(header, 24, 0)
    set_u32(header, 1648, len(dtb))
    struct.pack_into("<Q", header, 1652, dtb_addr)

    image = bytearray(header)
    image += kernel
    image += b"\0" * (ramdisk_offset - len(image))
    image += ramdisk
    image += b"\0" * (dtb_offset - len(image))
    image += dtb
    image += b"\0" * (output_size - len(image))

    # Keep the original Samsung header field in sync: total size = FDT + 64.
    # The Samsung and FDT size fields are both big-endian.
    fdt_size = struct.unpack_from(">I", dtb, 68)[0]
    if (struct.unpack_from(">I", dtb, 4)[0] != fdt_size + 64 or
            struct.unpack_from(">I", dtb, 32)[0] != fdt_size):
        fail("%s has inconsistent Samsung header sizes" % args.dtb)

    try:
        with open(args.output, "wb") as handle:
            handle.write(image)
    except OSError as exc:
        fail("cannot write %s: %s" % (args.output, exc))

    print("template : %s (%d bytes)" % (args.template, len(template)))
    print("kernel   : %s (%d bytes)" % (args.kernel, len(kernel)))
    print("ramdisk  : %d bytes @ %#x" % (len(ramdisk), ramdisk_offset))
    print("dtb      : %d bytes @ %#x (load %#x)" %
          (len(dtb), dtb_offset, dtb_addr))
    print("output   : %s (%d bytes)" % (args.output, len(image)))
    if len(image) != len(template):
        print("note: output size differs from the template; verify the "
              "boot partition is large enough", file=sys.stderr)


if __name__ == "__main__":
    main()
