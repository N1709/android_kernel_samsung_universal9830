#!/usr/bin/env bash
#
# build.sh - build the Exynos 990 (universal9830) kernel, v4.20 line.
#
# Default device: z3s (Galaxy S20 Ultra).
#
# Usage:
#   ./build.sh                  # exynos9830_defconfig + z3s fragment, -j$(nproc)
#   ./build.sh -d x1s           # Galaxy S20
#   ./build.sh -d y2s           # Galaxy S20+
#   ./build.sh -j 6             # limit parallelism
#   ./build.sh -c               # remove out/ first (clean build)
#   ./build.sh -n               # skip dtbs (kernel image only)
#
# Arch Linux dependencies:
#   sudo pacman -S --needed clang lld llvm bc bison flex openssl libelf \
#     ncurses kmod cpio rsync zstd python make git
#
# Cross binutils are required: clang runs with -no-integrated-as, so it
# needs aarch64-linux-gnu-as/objcopy/ld next to it (AUR):
#   yay -S --needed aarch64-linux-gnu-gcc
#
set -euo pipefail

DEVICE="z3s"
JOBS="$(nproc)"
CLEAN=0
DO_DTBS=1
KEEP=0

usage() {
	cat <<'EOF'
Usage: ./build.sh [-d DEVICE] [-j JOBS] [-c] [-n] [-k]

  -d DEVICE   device fragment in arch/arm64/configs (default: z3s)
              known: z3s, x1s, y2s, x1slte, y2slte, c1s, c2s, r8s
  -j JOBS     parallel jobs (default: nproc)
  -c          remove out/ before building
  -n          do not build dtbs (kernel image only)
  -k          keep going after errors (make -k), collects every error
EOF
}

while getopts 'd:j:cnkh' opt; do
	case "$opt" in
		d) DEVICE="$OPTARG" ;;
		j) JOBS="$OPTARG" ;;
		c) CLEAN=1 ;;
		n) DO_DTBS=0 ;;
		k) KEEP=1 ;;
		h) usage; exit 0 ;;
		*) usage; exit 1 ;;
	esac
done

cd "$(dirname "$0")"

FRAG="arch/arm64/configs/${DEVICE}.config"
if [ ! -f "$FRAG" ]; then
	echo "error: unknown device '${DEVICE}' (missing ${FRAG})" >&2
	usage
	exit 1
fi

need() { command -v "$1" >/dev/null 2>&1; }

missing=()
for t in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-strip \
	 make bc bison flex; do
	need "$t" || missing+=("$t")
done
if [ "${#missing[@]}" -ne 0 ]; then
	echo "error: missing tools: ${missing[*]}" >&2
	echo "Arch Linux:" >&2
	echo "  sudo pacman -S --needed clang lld llvm bc bison flex openssl libelf \\" >&2
	echo "    ncurses kmod cpio rsync zstd python make git" >&2
	exit 1
fi

if ! need "${CROSS_COMPILE:-aarch64-linux-gnu-}as"; then
	echo "error: ${CROSS_COMPILE:-aarch64-linux-gnu-}as not found" >&2
	echo "clang runs with -no-integrated-as, so cross binutils are required." >&2
	echo "Arch Linux (AUR):" >&2
	echo "  yay -S --needed aarch64-linux-gnu-gcc" >&2
	exit 1
fi

export ARCH=arm64
export CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}"

# The kernel Makefile assigns CC/LD/... with plain '=', which wins over the
# environment, so these must be passed on the make command line.
TCVARS=(
	CC=clang
	LD=ld.lld
	AR=llvm-ar
	NM=llvm-nm
	OBJCOPY=llvm-objcopy
	OBJDUMP=llvm-objdump
	STRIP=llvm-strip
)

if [ "$CLEAN" -eq 1 ]; then
	echo "==> clean: removing out/"
	rm -rf out
fi

mkdir -p out
LOG="out/build.log"

echo "==> defconfig: exynos9830_defconfig"
make O=out ARCH=arm64 "${TCVARS[@]}" exynos9830_defconfig

echo "==> fragment: ${DEVICE}.config"
make O=out ARCH=arm64 "${TCVARS[@]}" "${DEVICE}.config"

targets=(Image.gz)
[ "$DO_DTBS" -eq 1 ] && targets+=(dtbs)

echo "==> build: ${targets[*]} with -j${JOBS} (log: ${LOG})"
make_args=(-j"${JOBS}")
[ "$KEEP" -eq 1 ] && make_args+=(-k)
if ! make O=out ARCH=arm64 "${TCVARS[@]}" "${make_args[@]}" "${targets[@]}" 2>&1 | tee "$LOG"; then
	echo
	echo "build failed; first errors:" >&2
	grep -E 'error:|fatal error' "$LOG" | sort -u | head -60 >&2 || true
	exit 1
fi

echo
echo "==> artifacts"
ls -lh out/arch/arm64/boot/Image.gz 2>/dev/null || true
if [ "$DO_DTBS" -eq 1 ]; then
	find out/arch/arm64/boot/dts -type f \( -name '*.dtb' -o -name '*.dtbo' \) \
		| sort | head -25
fi
if need sha256sum && [ -f out/arch/arm64/boot/Image.gz ]; then
	sha256sum out/arch/arm64/boot/Image.gz
fi
