# Notes: Exynos 990 (universal9830) kernel upgrade 4.19.325 → v5.0

Working document. Updated as the merge progresses.

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
| Working dir | `/home/n1709/app/experimental/upstream-4.19-5.4` |
| Base | fork N1709/android_kernel_samsung_universal9830, branch `lineage-24.0` |
| Base Makefile | `4.19.325` |
| Remote `origin` | `git@github.com:N1709/android_kernel_samsung_universal9830.git` |
| Remote `stable` | `https://github.com/gregkh/linux.git` (tags `v4.19.325`, `v4.20`, `v5.0`) |
| Clone | partial (`--filter=blob:none`) → do **not** use `--depth`, do not remove remotes |
| Arch | arm64, out-of-tree build into `out/` |
| Work branch | `upgrade-5.0` (from `lineage-24.0` @ `97369af7bbd6`) |

## Required steps (checklist)

- [x] 1. `git merge-base HEAD v4.19.325` → `a67e7cdde7cc7984ae24c3c81a70dc1aa34424b1` (non-empty → continue)
- [x] 2. `git config rerere.enabled true`
- [x] 3. `git checkout -b upgrade-5.0`
- [ ] 4. `git merge v4.20` → resolve → commit → build passes
- [ ] 5. `git merge v5.0` → resolve → commit → build passes
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

## Deviations / features dropped

(none yet; fill in if something has to be dropped)

## Build

```bash
cd /home/n1709/app/experimental/upstream-4.19-5.4
ls arch/arm64/configs/ | grep -i -E 'exynos|universal|lineage'   # find the defconfig
make O=out ARCH=arm64 <defconfig>
make O=out ARCH=arm64 -j$(nproc)
```

## Log

- Merge-base OK (`a67e7cdd`), branch `upgrade-5.0` created, rerere enabled.
- `git merge --no-commit --no-ff v4.20` → 1239 conflicts.
- Bulk `--theirs` over 1165 generic files started.
- `kernel/sched/core.c`, `kernel/sched/Makefile` done.
- Next: `kernel/sched/{pelt.c,sched.h,fair.c,topology.c}`, `psi.c`,
  `arch/arm64`, `fs/f2fs`, `drivers/tty/serial/samsung.c`, then `git commit`.
