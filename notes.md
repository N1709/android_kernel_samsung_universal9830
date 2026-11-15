# Notes: Exynos 990 (universal9830) kernel upgrade 4.19.325 → v5.0

Working document. Updated as the merge progresses.

## Status terkini (15 Nov 2026)

| Tahap | Status |
|---|---|
| Merge v4.20 | ✅ selesai — `3027a77146cf`, 1239 konflik resolved |
| Build-fix v4.20 | ✅ commit `962ddc46b`, sudah di-push ke `origin/lineage-24.0` |
| Build v4.20 | ⏸️ **dilakukan di laptop**, bukan di HP (HP thermal throttling / app force close) |
| Boot test v4.20 | ⏸️ menunggu hasil build laptop |
| Merge v5.0 | ⏸️ **ditunda** sampai v4.20 lolos build + boot test |

Catatan penting: clone di HP ini **shallow** (hanya 1 commit, `.git/shallow`
ada) dan **tidak punya tag** `v4.19.325`/`v4.20`/`v5.0`. Fetch
`--filter=blob:none` untuk tag upstream pernah dijalankan tetapi dibatalkan.
Sebelum merge v5.0, jalankan lagi:

```bash
git fetch --unshallow --filter=blob:none origin
git fetch --filter=blob:none stable tag v4.19.325 tag v4.20 tag v5.0
git merge-base HEAD v4.19.325     # harus a67e7cdde7cc...
```

## Goal

- Move the Samsung Exynos 990 kernel (S20 Ultra; x1s/y2s/z3s) from 4.19.325 to
  upstream v5.0 via an **in-place merge** (no rebase, no restart from a clean
  upstream tree).
- End target: **boot test on v5.0** only (not a production kernel).
- The user runs the boot test manually; the agent stops after the v5.0 merge
  builds.

## Environment

| Item | Value |
|---|---|
| Working dir (HP) | `/home/n1709/android_kernel_samsung_universal9830` |
| Working dir (lama) | `/home/n1709/app/experimental/upstream-4.19-5.4` (sudah tidak dipakai) |
| Base | fork N1709/android_kernel_samsung_universal9830, branch `lineage-24.0` |
| Makefile sekarang | `4.20.0` |
| Remote `origin` | `https://github.com/N1709/android_kernel_samsung_universal9830.git` |
| Remote `stable` | `https://github.com/gregkh/linux.git` (tags `v4.19.325`, `v4.20`, `v5.0`) |
| Clone | **shallow** (1 commit) + fetch tag upstream belum lengkap → jangan pakai `--depth`, jangan hapus remote |
| Arch | arm64, out-of-tree build into `out/` |
| Work branch | `lineage-24.0` @ `962ddc46b` (tanpa branch baru) |

## Required steps (checklist)

- [x] 1. `git merge-base HEAD v4.19.325` → `a67e7cdde7cc7984ae24c3c81a70dc1aa34424b1` (non-empty → continue)
- [x] 2. `git config rerere.enabled true`
- [x] 3. `git checkout -b upgrade-5.0`
- [x] 4. `git merge v4.20` → resolve → commit
  - [x] merge + resolve + commit (`3027a77146cf`)
  - [x] build-fix akhir (`962ddc46b`) + push ke `lineage-24.0`
  - [ ] **build passes — di laptop**
  - [ ] **boot test — user**
- [ ] 5. `git merge v5.0` → resolve → commit → build passes (**ditunda**)
- [ ] 6. STOP (user runs the boot test)

## Initial state of the v4.20 merge

`git merge --no-commit --no-ff v4.20` → **1239 conflicted files**.

Automatic classification (stage-1/base vs stage-2/ours):

| Category | Count | Action |
|---|---|---|
| Local identical to base (untouched) | 5 | take upstream |
| Added on both sides (AA) | 29 | take upstream (psi included) |
| Deleted on our side (DU) | 37 | keep deleted (`git rm`) |
| Deleted upstream (UD) | 10 | accept deletion (`git rm`) |
| Locally modified | 1158 | see rules below |

Important: only 5 files are byte-identical to the base, because the Lineage
branch carries ~9552 commits (many `UPSTREAM:`/`BACKPORT:` plus CAF merges), so
almost every generic file is technically "touched". Therefore "never touched by
Samsung/Lineage" is interpreted as **generic files whose local changes are only
upstream backports** → take upstream.

### Key finding: Samsung core directories have zero conflicts

No conflicts at all under:

```
drivers/gpu/arm            drivers/soc/samsung
drivers/clk/samsung        drivers/pinctrl/samsung
drivers/gpu/drm/samsung    drivers/misc/samsung
security/defex             drivers/media/platform/exynos
arch/arm64/boot/dts/exynos
```

So Samsung core code needs no manual merge for v4.20; upstream did not touch it.

Manual conflicts remain in only 74 files:

```
arch/arm64/**            (42 files)
kernel/sched/**          (8 files, EMS)
fs/f2fs/**               (22 files, Samsung f2fs fork)
drivers/tty/serial/samsung.c
```

## Resolution rules in use

1. Generic files (not on the Samsung list) → `git checkout --theirs` + `git add`.
   This bulk step is deliberate; Samsung-listed paths are never bulk-resolved.
2. Samsung-listed paths (`drivers/gpu/arm`, `drivers/soc/samsung`,
   `drivers/clk/samsung`, `drivers/pinctrl/samsung`, `drivers/gpu/drm/samsung`,
   `kernel/sched` (EMS), `sec_*`, defex, `arch/arm64`,
   `arch/arm64/boot/dts/exynos`) → resolve manually, file by file and hunk by
   hunk.
3. `kernel/sched/psi.c`, `include/linux/psi.h`, `include/linux/psi_types.h` →
   take upstream (the 4.19 PSI backport is replaced by the v5.0 version).
4. Do not drop Samsung features just to make the build pass. If unavoidable,
   record it under "Deviations" below and report it to the user.
5. Never use `--allow-unrelated-histories`, `--depth`, or remove remotes.

### Important caveat: "ours" is often NEWER than v4.20

The Lineage branch already backported many 5.x/6.x patches into its 4.19 tree
(e.g. `ARM64_ERRATUM_3194386`, Cortex-X925 / Neoverse-V3 MIDRs, spectre-BHB
mitigation, newer `aes-modes.S`). Because v4.20 is *older* than some of those
backports, blindly taking "theirs" in `arch/arm64` is a **regression**.

Tie-breaker used for `arch/arm64`: since the final target is v5.0, compare each
hunk with the v5.0 file. If a hunk's content is what v5.0 has, pick that side;
if neither side matches v5.0, resolve manually.

`/tmp/opencode/tiebreak.py FILE [REF]` prints, per hunk, whether the ours/theirs
block also exists in `REF` (default `v5.0`).

### Helper tool

`/tmp/opencode/resolve.py FILE CHOICES [--dry]`

Resolves conflicts hunk by hunk. `CHOICES` is a comma-separated list in file
order: `o` = ours (HEAD/Lineage), `t` = theirs (upstream), `b` = both, `n` =
drop. Example: `python3 /tmp/opencode/resolve.py kernel/sched/fair.c o,t,o`.

## v4.20 resolution progress

### Done

- **Bulk upstream**: 1165 generic files → `--theirs` (list in
  `/tmp/opencode/bulk_theirs.txt`, failures in `/tmp/opencode/theirs_missing.txt`).
- **kernel/sched/core.c** — 2 hunks, **ours** (Samsung features):
  - `frt_update_available_cpus()` in `scheduler_tick()`
  - `init_ems()` in `sched_init_smp()`
- **kernel/sched/Makefile** — 1 hunk, **ours**:
  `obj-$(CONFIG_SCHED_EMS) += ems/`

### Per-subsystem decisions

- **kernel/sched (EMS)**: small conflicts (fair.c 12 hunks, sched.h 4,
  topology.c 4, pelt.c 2, core.c 2, Makefile 1). Strategy: keep the
  Lineage-side API/semantics (4.19 + EMS); do not mix v5.0 APIs inside the same
  file unless other call sites require it.
  - `pelt.c`: the merged `___update_load_sum()` definition still uses the old
    signature (no `cpu` argument) and all other call sites are old too →
    **ours** for both hunks (taking theirs breaks the build).
  - `sched.h` `sd_asym*` hunk: v4.20 has only `sd_asym`; v5.0 has
    `sd_asym_packing` + `sd_asym_cpucapacity`, matching ours → **ours**.
- **fs/f2fs**: Samsung fork (581 commits, +11811/-2747). Plan: keep **ours**
  for all of `fs/f2fs/**` so the fork stays consistent, then fix build errors
  against v5.0 APIs. (Not executed yet.)
- **arch/arm64**: 42 files. Sub-classify:
  - `boot/dts/{allwinner,altera,amlogic,renesas,rockchip,...}` → upstream.
  - `configs/defconfig` → upstream (the Exynos build uses its own defconfig).
  - `crypto/*`, `lib/*`, `net/bpf_jit_comp.c` → upstream (backports).
  - `kernel/*`, `mm/*`, `include/asm/*`, `Kconfig*`, `Makefile` → manual,
    because they carry Exynos platform hooks (errata, SMC, dma-mapping, etc.).
- **drivers/tty/serial/samsung.c** → manual (Samsung driver).

## v4.20 merge result

Merge commit: `3027a77146cf` — "Merge v4.20 into upgrade-5.0".
All 1239 conflicts resolved; `Makefile` is now `4.20.0`.

Resolution details worth remembering:

| Area | Decision |
|---|---|
| Generic files | upstream v4.20 (`--theirs`) |
| Locally deleted files (staging/erofs, i40evf, mt7621-mmc, ...) | keep deleted |
| Files removed upstream (iavf, mt76 tx, docg4, ...) | accept deletion |
| `fs/f2fs/**` | whole directory taken from HEAD (Samsung fork stays consistent) |
| `kernel/sched/psi.c`, `psi.h`, `psi_types.h` | upstream |
| `kernel/sched/{fair,sched.h,topology,pelt,core,Makefile}` | HEAD (EMS + schedtune SPC) |
| `arch/arm64/**` | per-hunk, v5.0 as tie-breaker |
| `arch/arm64/mm/dma-mapping.c` | upstream v4.20 + re-ported Samsung PCIe S2MPU / PL330 mcode ops on `dma_direct_*` |
| `drivers/tty/serial/samsung.c` | Samsung clock helpers kept, upstream resume reset taken |

Notable per-file choices in `arch/arm64`:
- kept ours (newer backports): `cpucaps.h`, `cputype.h`, `cpu_errata.c`,
  `sysreg.h` (SB barrier, RAS), `hwcap.h` (`HWCAP_SB`), `ptrace.h`,
  `Kconfig.platforms`, `Makefile` (dtbo + vdso32 rules), `crypto/Makefile`
  (crc32-ce, poly1305-neon), `net/bpf_jit_comp.c`, `vmlinux.lds.S` (both
  page-table blocks), `lib/crc32.S` (ours' faster crc32 path).
- took theirs (v5.0-consistent): `stage2_pgtable.h`, `pgtable.h`,
  `processor.h`, `traps.c`, `sys_compat.c`, `kvm/hyp/hyp-entry.S`,
  `mm/{init,mmu}.c`, `cpufeature.c` (most hunks), `mm/fault.c` (new
  `arm64_notify_die`/`is_el1_permission_fault` signatures).
- `mm/fault.c`: Samsung debug hooks (`safe_fault_in_progress`,
  `CONFIG_SEC_DEBUG_EXTRA_INFO`, `CONFIG_SEC_DEBUG_FAULT_MSG_ADV`) were
  re-inserted by hand after taking the new API.
- `cpufeature.c`: dropped the upstream `ARM64_HAS_CRC32` capability entry
  because `cpucaps.h` stays on the Lineage numbering (no `ARM64_HAS_CRC32`);
  4.19's `crc32-ce-glue.c` uses `cpu_have_crc32()` instead.

## Build

Build script in the tree (`build_kernel.sh`) references
`exynos9830-x1slte_defconfig`, which does not exist in `arch/arm64/configs/`.
The available configs are `exynos9830_defconfig` plus per-device fragments
(`x1s.config`, `y2s.config`, `z3s.config`, ...).

Toolchain: the defconfig was generated with Android clang 14.0.6 + LLD.
The host only has clang 23.1.5 / LLD 23.1.5, which is much newer than what
4.19/v4.20 Kbuild expects.

Kconfig note: the first `make ... defconfig` failed with a bogus
`init/Kconfig:17: syntax error` plus `scripts/gcc-version.sh: -p: command not
found`. Root cause was the stale 4.19 `scripts/gcc-version.sh` (see below),
not the compiler selection.

### Build fixes needed after the merge

1. `scripts/gcc-version.sh` was still the old 4.19 script (no `-p` support)
   while `init/Kconfig` was already v4.20. Restored v4.20's version.
2. `scripts/gcc-plugins/Kconfig` and `security/Kconfig.hardening` both defined
   `GCC_PLUGIN_STRUCTLEAK*`. `security/Kconfig.hardening` (Lineage backport,
   not present in v4.20) owns the definitions inside the
   "Initialize kernel stack variables" choice, so the duplicate block was
   removed from `scripts/gcc-plugins/Kconfig`.
3. The defconfig was generated with clang originally; make sure the config is
   regenerated with the clang toolchain so `CONFIG_CC_IS_CLANG` matches the
   compiler actually used.
4. `scripts/dtc/` was a mix of v4.20 `dtc.h` and an older `livetree.c`
   (`build_property`/`build_node` signatures did not match). Restored the
   whole directory from v4.20 (`git checkout v4.20 -- scripts/dtc/`); the
   file list is identical, including `yamltree.c`.
5. `include/linux/pgtable.h` is a Lineage backport of the old
   `asm-generic/pgtable.h` (guard is still `_ASM_GENERIC_PGTABLE_H`), but
   v4.20's `arch/arm64/include/asm/pgtable.h` ends with
   `#include <asm-generic/pgtable.h>`, which no longer exists here. Added
   `#include <linux/pgtable.h>` at the end of `asm/pgtable.h` and
   `#include <asm/pgtable.h>` at the top of `linux/pgtable.h`, so the header
   is self-contained no matter which one is included first (e.g.
   `linux/memremap.h` pulls in `linux/pgtable.h` before `asm/pgtable.h`).
6. `scripts/dtc/dtc-lexer.l`: v4.20 defines `YYLTYPE yylloc;` in the lexer,
   which clashes with the definition from the generated parser when the host
   compiler defaults to `-fno-common`. Dropped the definition (HEAD already
   did this); the parser's `extern` declaration is enough.
6. `include/linux/cpumask.h` used `bitmap_size()` (a much newer helper that
   does not exist in 4.19/4.20/5.0). Replaced with the equivalent
   `BITS_TO_LONGS(nr_cpumask_bits) * sizeof(long)`.
7. `include/linux/debug-snapshot.h` defined both a
   `dbg_snapshot_get_hardlockup()` macro and a `static inline` function of the
   same name in the `!CONFIG_DEBUG_SNAPSHOT` stub block. Removed the macro.

Note: `CONFIG_DEBUG_SNAPSHOT` has no `config` entry anywhere in the tree
(neither in HEAD nor after the merge), so the Samsung debug-snapshot code is
already compiled out in this branch. This is pre-existing, not caused by the
merge.

### Pre-existing version skew in HEAD

The starting tree was already a mix of 4.19, 5.x backports and partial
Android/Lineage patches, and several of those combinations did not compile:

- `include/linux/sched/task.h` used `refcount_inc(&t->usage)` while
  `struct task_struct.usage` is still `atomic_t`.
- `include/linux/mm_types.h` and `include/linux/mm.h` both defined
  `compound_mapcount_ptr()`.
- `include/linux/page-flags.h` (5.x backport) used
  `compound_mapcount_ptr()` from `mm_types.h`.
- `include/linux/kernfs.h` was the 5.5+ version (`kn->id` is `u64`) while
  `include/linux/cgroup.h` still used `union kernfs_node_id`.
- `include/linux/cgroup-defs.h` was the 5.x version (no `int id` in
  `struct cgroup`, has freezer state) while `kernel/cgroup/cgroup.c` still
  dereferenced `cgrp->id`.
- `arch/arm64/include/asm/memory.h` used `page_kasan_tag()` but nothing
  defined it.

Fixes chosen (generic subsystems are aligned to v4.20, Samsung/Android
features are kept):

| File(s) | Action |
|---|---|
| `include/linux/sched/task.h` | v4.20 (matches `atomic_t usage` and `kernel/fork.c`) |
| `include/linux/page-flags.h` | v4.20 (the 5.x `PageTransCompoundMap` backport needed the duplicate helper) |
| `include/linux/mm_types.h` | kept HEAD (SPECULATIVE_PAGE_FAULT, ANDROID_KABI, anon_name); removed the duplicate `compound_mapcount_ptr()` |
| `include/linux/mm.h` | added the v5.0 `page_kasan_tag*()` helpers and `KASAN_TAG_PGSHIFT` |
| `include/linux/mmzone.h` | re-added the Samsung `ZERO_PAGE_ALLOC_*` node stats for `CONFIG_KZEROD` |
| `include/linux/kernfs.h`, `fs/kernfs/`, `fs/sysfs/`, `include/linux/cgroup-defs.h`, `kernel/cgroup/` | v4.20 as one consistent cluster |
| `kernel/cgroup/legacy_freezer.c` | removed (v4.20 has no legacy freezer) |
| `include/linux/cgroup-defs.h` | re-added `CGRP_ROOT_MEMORY_LOCAL_EVENTS` and `CGRP_ROOT_MEMORY_RECURSIVE_PROT` (used by the kept `mm/memcontrol.c`) |
| `scripts/extract-cert.c` | guard the ENGINE/PKCS#11 code with `OPENSSL_NO_ENGINE` (host OpenSSL 4 has no ENGINE API) |
| `include/vdso/datapage.h` | dropped `#include <linux/compat_time.h>`; that header never existed upstream and the file does not use any of its types |
| `arch/arm64/mm/fault.c` | v4.20 API: `__do_page_fault(struct mm_struct *, ...)` + `find_vma()` di dalam; `do_debug_exception()` param `addr`, cek watchpoint pakai `instruction_pointer(regs)` |
| `include/linux/cryptohash.h` | tambah `SHA_MESSAGE_BYTES` (dibutuhkan v4.20 `include/linux/filter.h`) |
| `include/linux/memblock.h` | deklarasikan `enum memsize_kernel_type` + `set_memsize_*`/`record_memsize_*`/`free_memsize_reserved()` (dipakai `mm/memblock.c` dan `arch/arm64/mm/init.c`) |
| `include/linux/random.h`, `mm/util.c` | hapus duplikat `randomize_page()`; di v4.20 pemiliknya `drivers/char/random.c` |

Side effect to remember: because `kernel/cgroup/` is v4.20, the cgroup core
never sets `CGRP_ROOT_MEMORY_RECURSIVE_PROT`, so the memory cgroup recursive
protection knob from the Lineage backport is inactive. It compiles and does
not affect boot.

## Build di laptop (x86_64)

Jangan build di HP: Exynos 990 throttle dan aplikasi pernah force close.

```bash
# 1. clone branch hasil merge
git clone -b lineage-24.0 \
  https://github.com/N1709/android_kernel_samsung_universal9830.git kernel-5.0
cd kernel-5.0
git log --oneline -2        # harus ada 962ddc46b

# 2. dependency (Ubuntu/Debian)
sudo apt install -y clang lld llvm gcc-aarch64-linux-gnu \
  binutils-aarch64-linux-gnu libssl-dev bc bison flex libelf-dev \
  libncurses-dev kmod cpio rsync zstd python3 make

# 3. WAJIB export CC (Kconfig membaca CC dari environment, bukan dari argumen make)
export CC=clang LD=ld.lld AR=llvm-ar NM=llvm-nm \
       OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip \
       CROSS_COMPILE=aarch64-linux-gnu-

# 4. config: base + fragment S20 Ultra (z3s)
make O=out ARCH=arm64 exynos9830_defconfig
make O=out ARCH=arm64 z3s.config

# 5. build
make O=out ARCH=arm64 -j$(nproc)
```

Hasil:

```
out/arch/arm64/boot/Image
out/arch/arm64/boot/Image.gz
out/arch/arm64/boot/dts/exynos/*.dtb
```

Catatan:
- Jangan pakai `build_kernel.sh` — script itu menunjuk
  `exynos9830-x1slte_defconfig` yang tidak ada di tree ini.
- Defconfig aslinya dibuat dengan Android clang 14.0.6 + LLD. Kalau clang
  host (18/19+) memunculkan error aneh, pakai prebuilt AOSP clang 14
  (`clang-r450784d`) dan arahkan `CC`/`LD` ke situ.
- `z3s.config` hanya fragment (`CONFIG_MODEL_Z3S`, kamera, dsb). Kalau target
  boot test cukup memakai `exynos9830_defconfig` saja, fragmen ini opsional.

## Log

- Merge-base OK (`a67e7cdd`), branch `upgrade-5.0` dibuat, rerere enabled.
- `git merge --no-commit --no-ff v4.20` → 1239 conflicts.
- Bulk `--theirs` atas 1165 file generik.
- Merge v4.20 selesai + commit `3027a77`, push ke `lineage-24.0`.
- Build-fix checkpoint `d25ce9a` (push).
- Fix terakhir yang sempat hilang (clone baru) diterapkan ulang + commit
  `962ddc46b`:
  `mm/util.c`, `include/linux/random.h`, `include/linux/memblock.h`,
  `arch/arm64/mm/fault.c`, `include/linux/cryptohash.h`.
- Push `d25ce9a98..962ddc46b` ke `origin/lineage-24.0`.
- Build penuh **dipindah ke laptop**; HP hanya untuk merge/commit/push.
- Merge v5.0 belum dimulai (menunggu v4.20 lolos build + boot).
- Blocker untuk v5.0: clone HP masih shallow & tag upstream belum ada —
  fetch ulang seperti di bagian "Status terkini".
