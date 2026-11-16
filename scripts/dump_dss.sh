#!/system/bin/sh
# Dump the Samsung debug-snapshot memory right after a failed boot.
#
# Run this from a TWRP/recovery adb shell.  Do NOT power the device off
# first: the kernel log ring lives in DRAM and is lost on a cold boot.
# A warm reset (Vol-Down + Power) keeps DRAM contents.
#
#   adb shell sh /tmp/dump_dss.sh /tmp/dss
#   adb pull /tmp/dss
#
# The three regions are the defaults from
# include/dt-bindings/soc/samsung/debug-snapshot-def.h.  The header dump
# contains the bootloader-populated item table at offset 0x900, so the
# actual addresses/sizes can be checked with scripts/parse_dss.py.

set -u

OUT="${1:-/tmp/dss}"
MEM=/dev/mem

mkdir -p "$OUT" || exit 1

if [ ! -e "$MEM" ]; then
	echo "error: $MEM is not available in this recovery" >&2
	exit 1
fi

dump() {
	name="$1"
	addr="$2"
	size="$3"
	skip=$((addr / 4096))
	count=$(((size + 4095) / 4096))
	echo "== $name @ $addr ($size bytes)"
	dd if="$MEM" of="$OUT/$name.bin" bs=4096 skip="$skip" count="$count"
}

dump dss_header 0xFD900000 0x10000
dump log_kernel 0xFD910000 0x200000
dump log_pstore 0xeb308000 0x8000

if [ -d /sys/fs/pstore ]; then
	mkdir -p "$OUT/pstore"
	cp -a /sys/fs/pstore/. "$OUT/pstore/" 2>/dev/null
fi

sync
echo "done: $OUT"
ls -l "$OUT"
