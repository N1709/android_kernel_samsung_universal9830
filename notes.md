# Notes: Exynos 990 (universal9830) kernel upgrade 4.19.325 → v5.0

Working document. Updated as the merge progresses.

## Current status (15 Nov 2026)

| Stage | Status |
|---|---|
| v4.20 merge | done — `3027a77146cf`, 1239 conflicts resolved |
| v4.20 normalization | `a838f89fb` covered 9838 files; `466c12f3e` added the 307 missed generic files |
| v4.20 Kconfig/header seams | `efd91f859` |
| v4.20 vDSO config | `a448d5c26` — `source "lib/vdso/Kconfig"` in `lib/Kconfig` |
| Android-critical headers | `e450173fb` — Lineage fscrypt/f2fs headers kept |
| FBE v2 filesystem stack | in progress — Lineage `fs/crypto`, `fs/verity`, `fs/ext4`, `fs/f2fs`; 4.19 compat shims added for the core APIs 4.20 removed |
| Target ROM | Android 17 / LineageOS 24.0, all Exynos 990 (universal9830) devices |
| Hybridswap | not present in this tree; required by the ROM, source pending |
| arch/arm64 | generic code forced to v4.20 (`b9b373430`); `boot/dts/**` and `configs/**` stay vendor (v4.20 has no Exynos 990 files at all) |
| dropped v4.20 files | `lib/chacha20.c`, `mm/kasan/kasan.c`, `mm/kasan/kasan_init.c`, `crypto/memneq.c` restored in `1b6e32131` |
| arch/arm64 cluster | rc=0, zero errors (kernel, mm, lib, crypto) |
| vendor build wiring | restored after the v4.20 normalization silently dropped it; see "Vendor build wiring" below |
| v4.20 build | first full `-j2 -k` run stopped after 62 errors; arch/arm64 was a v4.20/vendor mix, now resynced to v4.20 |
| v4.20 boot test | pending build |
| v5.0 merge | on hold until v4.20 builds and boots |
| Branch | `K4.20` (GitHub default); `lineage-24.0` removed |

The local clone is shallow (`git rev-parse --is-shallow-repository` says
true) and partial (`blob:none`). Tags `v4.20` and `v5.0` are present;
`v4.19.325` is not. Before merging v5.0, re-run:

```bash
git fetch --unshallow --filter=blob:none origin
git fetch --filter=blob:none stable tag v4.19.325 tag v4.20 tag v5.0
git merge-base HEAD v4.19.325     # harus a67e7cdde7cc...
```

## Goal

- Move the Samsung Exynos 990 (universal9830) kernel for **all supported
  devices** — S20 series (`x1s`/`y2s`/`z3s`), Note 20 series, S20 FE and the
  other device fragments — from 4.19.325 to upstream v5.0 via an **in-place
  merge** (no rebase, no restart from a clean upstream tree).
- Target ROM: **Android 17 / LineageOS 24.0**, all universal9830 variants.
  Android-critical paths (f2fs, fscrypt/fs-verity, SELinux/defex, binder,
  Samsung platform code) keep the Lineage 4.19 APIs.
- Hybridswap is part of that contract. It is not in this tree yet; port it
  once a reference source is available, and keep its files out of the
  v4.20 normalization.
- End target: **boot test on v5.0** only (not a production kernel).
- The user runs the boot test manually; the agent stops after the v5.0 merge
  builds.

## Environment

| Item | Value |
|---|---|
| Working dir | `/home/n1709/android_kernel_samsung_universal9830` |
| Working dir (legacy) | `/home/n1709/app/experimental/upstream-4.19-5.4` (no longer used) |
| Base | fork N1709/android_kernel_samsung_universal9830, branch `K4.20` |
| Current Makefile | `4.20.0` |
| Remote `origin` | `https://github.com/N1709/android_kernel_samsung_universal9830.git` |
| Remote `stable` | `https://github.com/gregkh/linux.git` (tags `v4.19.325`, `v4.20`, `v5.0`) |
| Clone | partial (`blob:none`), shallow, tags `v4.20` and `v5.0` present, no `v4.19.325` |
| Arch | arm64, out-of-tree build into `out/` |
| Work branch | `K4.20` @ `a448d5c26` (no extra branch) |

## Required steps (checklist)

- [x] 1. `git merge-base HEAD v4.19.325` → `a67e7cdde7cc7984ae24c3c81a70dc1aa34424b1` (non-empty → continue)
- [x] 2. `git config rerere.enabled true`
- [x] 3. `git checkout -b upgrade-5.0`
- [x] 4. `git merge v4.20` → resolve → commit
  - [x] merge + resolve + commit (`3027a77146cf`)
  - [x] final build fixes (`962ddc46b`) + push to `lineage-24.0`
  - [ ] **build passes**
  - [ ] **boot test — user**
- [ ] 5. `git merge v5.0` → resolve → commit → build passes (**on hold**)
- [ ] 6. STOP (user runs the boot test)

## FBE v2 seam (Android 17)

Android 17 needs fscrypt v2 (keyring, HKDF, v2 policies, casefold) and
fs-verity.  Upstream v4.20 only has fscrypt v1, so the whole consumer
stack stays on the Lineage side:

```
fs/crypto/**            fs/verity/**            fs/ext4/**
fs/f2fs/**              include/linux/fscrypt.h include/linux/fsverity.h
include/uapi/linux/fscrypt.h
```

v4.20 `fs/ext4` cannot be reused: it still calls the v1 page encryption
API, while the Lineage fscrypt exports the v2 API.  Keeping the Lineage
ext4 therefore needs a few small 4.20 compatibility shims for core APIs
that v4.20 removed:

| Shim | File |
|---|---|
| `jbd2_journal_inode_ranged_write/wait` | `include/linux/jbd2.h`, `fs/jbd2/transaction.c` |
| `sb_breadahead_unmovable()` | `include/linux/buffer_head.h` |
| 4.19 mb_cache API | `fs/mbcache.c`, `include/linux/mbcache.h` (only ext4 uses it; ext2 is off) |
| `DCACHE_ENCRYPTED_NAME` | `include/linux/dcache.h` (same bit as the unused `DCACHE_ENCRYPTED_WITH_KEY`) |
| `generic_set_encrypted_ci_d_ops()` | `fs/libfs.c` |
| `vfs_ioc_setflags_prepare()`, `vfs_ioc_fssetxattr_check()` | `fs/inode.c` |
| `simple_fill_fsxattr()` | `include/linux/fs.h` |
| `s_master_keys` in `struct super_block` | `include/linux/fs.h` |
| `REQ_OP_ZONE_REPORT` (trace string only) | `include/linux/blk_types.h` |
| `lookup_user_key()` declaration | `include/linux/key.h` |
| `strscpy_pad()` | `lib/string.c`, `include/linux/string.h` |
| `__vmalloc()` 2-argument call sites | `fs/ext4/super.c` |
| `FS_VERITY_FL`, `FS_CASEFOLD_FL`, `STATX_ATTR_VERITY` | `include/uapi/linux/fs.h`, `include/uapi/linux/stat.h` |
| f2fs/ext4 trace events | `include/trace/events/f2fs.h`, `include/trace/events/ext4.h` |

`CONFIG_FS_VERITY` and `CONFIG_EXT4_FS_VERITY` are unset in the current
config, so `fs/verity` and `fs/ext4/verity.c` are not built.  The
`S_VERITY`/`IS_VERITY` definitions stay in `fs.h` because f2fs headers
still reference them.

## Stability plan

Priority order: green build, then boot, then stability, then features.

1. Build `Image.gz` + `dtbs` with zero errors on the Android 17 config.
2. Boot test on universal9830; capture last_kmsg/pstore if it fails.
3. Keep vendor drivers and board files untouched until boot is green.
4. arch/arm64 generic code is v4.20 per the user's decision.  If early
   boot fails on Exynos-specific errata, cpuidle or suspend, restore
   only the affected vendor file instead of the whole directory.
5. No MGLRU, BORE, Simple LMK, WALT or Adreno boosts before boot and
   basic stability are confirmed; they are separate, reversible commits.

## Vendor build wiring (must stay vendor)

The v4.20 normalization also replaced `drivers/Kconfig`, `drivers/Makefile`
and thousands of other Kconfig/Makefile files with their upstream versions.
That silently disabled the whole Samsung driver set:

- `drivers/samsung/` was never entered from `drivers/Makefile`, so
  `CONFIG_SEC_*` never appeared in `.config`;
- 145 Exynos/Samsung symbols requested by the defconfig were dropped,
  including `SOC_EXYNOS9830`, `MODEL_Z3S`, `EXYNOS_DPU30`,
  `BATTERY_SAMSUNG`, `SEC_PM` and `EXYNOS_BTS`;
- `arch/arm64/Kconfig.platforms` was v4.20, so the Exynos platform and
  model selection menus did not exist at all.

A build without those drivers cannot boot Android, even if `Image.gz`
links.  The whole Kconfig/Makefile set under `drivers/`, `sound/`,
`security/`, `fs/`, `net/`, `block/`, `mm/`, `kernel/`, `lib/`, `ipc/`,
`firmware/` and `init/`, plus `arch/arm64/Kconfig.platforms`, is
therefore restored from the vendor tree (`3027a7714^1`).  The v4.20
top-level `Makefile`, `scripts/`, and the already-synced 4.20 code stay
as they are.

Two 4.19 symbols that the vendor Kconfig files still test were removed
in 4.20: `HAVE_MEMBLOCK` and `NO_BOOTMEM`.  Both are selected again
from `arch/arm64/Kconfig`; without them `CONFIG_ION` and
`CONFIG_PSTORE_RAM` stay disabled and the CMA select from `HPA` warns.
Memory hotplug is not restored: v4.20 arm64 has no `arch_add_memory()`,
so `CONFIG_MEMORY_HOTPLUG`, `CONFIG_MEMORY_HOTREMOVE` and
`CONFIG_EXYNOS_PASR` stay off until the arch code is reconciled.

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
| `arch/arm64/mm/fault.c` | v4.20 API: `__do_page_fault(struct mm_struct *, ...)` + `find_vma()` inside; `do_debug_exception()` takes `addr`, watchpoint check uses `instruction_pointer(regs)` |
| `include/linux/cryptohash.h` | added `SHA_MESSAGE_BYTES` (needed by v4.20 `include/linux/filter.h`) |
| `include/linux/memblock.h` | declare `enum memsize_kernel_type` + `set_memsize_*`/`record_memsize_*`/`free_memsize_reserved()` (used by `mm/memblock.c` and `arch/arm64/mm/init.c`) |
| `include/linux/random.h`, `mm/util.c` | drop the duplicate `randomize_page()`; in v4.20 it is owned by `drivers/char/random.c` |

Side effect to remember: because `kernel/cgroup/` is v4.20, the cgroup core
never sets `CGRP_ROOT_MEMORY_RECURSIVE_PROT`, so the memory cgroup recursive
protection knob from the Lineage backport is inactive. It compiles and does
not affect boot.

## Build

```bash
# 1. clone the merged branch
git clone -b K4.20 \
  https://github.com/N1709/android_kernel_samsung_universal9830.git kernel-5.0
cd kernel-5.0

# 2. dependencies (Ubuntu/Debian)
sudo apt install -y clang lld llvm gcc-aarch64-linux-gnu \
  binutils-aarch64-linux-gnu libssl-dev bc bison flex libelf-dev \
  libncurses-dev kmod cpio rsync zstd python3 make

# 3. build (config + Image.gz + dtbs, logs to out/build.log)
./build.sh              # add -j N to limit parallelism, -c for a clean build
```

`arch/arm64/configs/*.config` fragments are merged by `build.sh`; use `-d x1s`
(or `y2s`, `x1slte`, ...) for other models, `-n` to skip the device trees.

Do not export the toolchain instead of passing it: the kernel `Makefile` uses
plain assignments (`CC = $(CROSS_COMPILE)gcc`, `LD = ...`), and those always win
over the environment. The toolchain has to be on the `make` command line:

```bash
export ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
make O=out ARCH=arm64 \
  CC=clang LD=ld.lld AR=llvm-ar NM=llvm-nm \
  OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip \
  exynos9830_defconfig
make O=out ARCH=arm64 CC=clang LD=ld.lld ... z3s.config
make O=out ARCH=arm64 CC=clang LD=ld.lld ... -j$(nproc)
```

Cross binutils are mandatory: clang is used with `-no-integrated-as`, so
`aarch64-linux-gnu-as` must be installed. On Arch Linux the AUR package
`aarch64-linux-gnu-gcc` provides them.

Output:

```
out/arch/arm64/boot/Image
out/arch/arm64/boot/Image.gz
out/arch/arm64/boot/dts/samsung/exynos990-z3s*.dtb
```

Notes:
- Do not use `build_kernel.sh` — it refers to `exynos9830-x1slte_defconfig`,
  which does not exist in this tree.
- Early builds on both the laptop and the phone silently used `gcc`: `CC` was
  exported, but `Makefile:379` assigns `CC = $(CROSS_COMPILE)gcc`, so gcc was
  used while the log looked normal. Fixed by passing the toolchain on the make
  command line (`4c371f972`). If a log shows `cc1: some warnings being treated
  as errors`, gcc is still in use.
- `Makefile` also had a broken clang prefix: `--prefix=$(dir $(which $(LD)))`
  resolves to `/usr/bin/`, so clang assembled with the host `as`. It now uses
  `--prefix=$(dir $(which $(CROSS_COMPILE)as))$(CROSS_COMPILE)`.
- The defconfig was originally generated with Android clang 14.0.6 + LLD. If
  the host clang (18/19+) produces odd errors, switch to the AOSP clang 14
  prebuilt (`clang-r450784d`) and point `CC`/`LD` at it.
- `z3s.config` is only a fragment (`CONFIG_MODEL_Z3S`, camera, ...). For a pure
  boot test, `exynos9830_defconfig` alone is enough.

## Log

- Merge-base OK (`a67e7cdd`), branch `upgrade-5.0` created, rerere enabled.
- `git merge --no-commit --no-ff v4.20` → 1239 conflicts.
- Bulk `--theirs` over 1165 generic files.
- v4.20 merge completed and committed as `3027a77`, pushed to `lineage-24.0`.
- Build-fix checkpoint `d25ce9a` pushed.
- Last fixes that were lost when the tree was re-cloned re-applied and
  committed as `962ddc46b`:
  `mm/util.c`, `include/linux/random.h`, `include/linux/memblock.h`,
  `arch/arm64/mm/fault.c`, `include/linux/cryptohash.h`.
- Pushed `d25ce9a98..962ddc46b` to `origin/lineage-24.0`.
- Laptop build errors fixed in `32e549c22` (mmap_lock include, `make_task_dead`,
  `struct sched_param`, `probe_kernel_read/write`, vdso `math64.h`, perf-BPF
  `call_get_stack`, duplicate `VM_FAULT_*_HINDEX`).
- That commit accidentally included the build directory; `out/` is now
  untracked and ignored. The commit was amended to `634c8c9cb` and
  force-pushed, so existing clones must `git fetch && git reset --hard
  origin/lineage-24.0`.
- `4c371f972` makes the clang toolchain effective (`printk_safe_init`,
  `CLANG_PREFIX`, `build.sh` command-line variables).
- v5.0 merge not started yet (waiting for the v4.20 build and boot test).
- v5.0 blocker: the local clone is still shallow and has no upstream tags —
  re-run the fetch from "Current status" first.
- Branch renamed `lineage-24.0` → `K4.20` and set as the GitHub default;
  `lineage-24.0` removed locally and remotely. Commit subjects no longer use
  the `UPSTREAM:` prefix.
- `a838f89fb`: 9838 non-vendor files normalized byte-for-byte to v4.20; only
  `Makefile` and `.gitignore` differ on purpose.
- `efd91f859`: Kconfig/header seams — 4.19 kconfig parser, `as-instr` helper,
  4.19 gcc-plugins Kconfig, dtc lexer, removed `include/linux/limits.h`,
  `page_kasan_tag()`, `CAP_CHECKPOINT_RESTORE`, `classmap.h` host guard.
- `a448d5c26`: restored `source "lib/vdso/Kconfig"` in `lib/Kconfig`, which
  enables `CONFIG_GENERIC_GETTIMEOFDAY` and fixes the arm64 vDSO build.
- Cluster build (`/tmp/opencode/cluster1.sh`, 12 seam targets incl. vDSO):
  rc=0, all targets clean. Full `-j2` build started after that.
