# mindset.md

Working handbook for any AI agent that continues this kernel upgrade.
Read it fully before touching the tree. It explains how to think, how to
scan, and which mistakes have already been made so they are not repeated.

This file is methodology. `notes.md` is status and history. If they
conflict, `notes.md` reflects reality, this file reflects intent.

---

## 1. The job

Upgrade the Samsung Exynos 990 (universal9830) kernel from 4.19.325 to
upstream 5.0, by merging one stable release at a time inside the existing
repository (never a fresh clone, never `--allow-unrelated-histories`,
never `--depth`).

**Target ROM: Android 17 / LineageOS 24.0 for the whole Exynos 990
family, not one device.** This tree builds every supported universal9830
variant (`x1s`, `y2s`, `z3s`, the `lte` variants, and the other device
fragments under `arch/arm64/configs/`). A change that only works for
`z3s` is not finished: it must keep the common Samsung platform code and
the per-device DTBs building together.

The kernel is not a standalone upstream test: it must keep the Android
userspace contract working. That contract is why some subsystems stay on
the Lineage 4.19 side even while the rest of the tree is normalised to
v4.20:

| Area | Why it stays Lineage |
|---|---|
| `fs/f2fs/**` | Samsung f2fs fork (compression, HPB, SEC fsck extras) used by the ROM |
| `fs/crypto/**`, `fs/verity/**`, `include/linux/fscrypt.h`, `include/linux/fsverity.h` | FBE v2 / fs-verity API expected by Android 17 |
| `security/selinux/**`, `security/defex/**` | Android SELinux policy ABI and Samsung defex |
| `drivers/android/**` | binder features used by Android 17 |
| `arch/arm64/**` | board support, errata, SMC, DTBs |
| `kernel/sched/**` (EMS) | Samsung scheduler |
| `hybridswap` (once ported) | Samsung zram + swapfile policy expected by the ROM; not present in this tree yet |
| Samsung drivers under `drivers/{gpu/arm,soc,clk,pinctrl,drm,media}/...`, `sec_*` | board support |

Everything else that exists in upstream v4.20 is expected to be
byte-for-byte v4.20. "Normalise to 4.20" never overrides the table above.

Current checkpoint: the v4.20 merge is committed. The vendor 5.9 BPF
backport has been reverted to v4.20 because it required 5.x core APIs and
produced about 550 of the 553 build errors. The tree must compile and
boot with v4.20 before any v5.0 work starts. The build is not green yet;
the next full build decides the remaining seam errors.

Branch: `K4.20`. Do not create new branches. Do not rewrite published
history except the documented `--amend` case in `notes.md`.

---

## 2. The one mental model that matters

After a merge like this the tree is not "4.20". It is a **mixture of two
API generations**, and every failure lives on a seam between them.

There are three provenances for any file:

| Provenance | Meaning | Typical behaviour |
|---|---|---|
| `^1` (4.19 side) | Lineage/Samsung 4.19 **with 5.x backports** | often *newer* than v4.20 |
| `^2` (4.20 side) | clean upstream v4.20 | often *older* for APIs Lineage backported |
| post-merge | changed by our own fix commits | deliberate, must be preserved |

The merge base commit for the v4.20 merge is `3027a7714`.
`3027a7714^1` is the 4.19 side, `3027a7714^2` is the v4.20 side.

**Rule: never fix a symbol before you know which generation each side is.**
A "missing declaration" is usually not missing. It was moved, renamed, or
intentionally dropped because the *other* side is newer. Ask:

1. Which side introduced this symbol?
2. Which side consumes it right now?
3. Which generation do the consumers belong to?

Answer those three and the fix is usually a one-line include or a restore
of one file, not a new declaration.

---

## 3. Ground truth hierarchy

Trust, in this order:

1. **The compiler.** A targeted compile of the affected translation unit
   is the only proof that a fix is correct.
2. **Git provenance.** `git diff` against `^1` and `^2` tells you what the
   merge actually did, which no amount of reading can replace.
3. **Static scans** (sections 5 and 6). They predict failures and find
   whole classes of bugs at once.
4. **Your own reasoning about the code.** Slowest to validate, most
   likely to be wrong.

Never reason for twenty minutes about what a header contains. Run one
`git show` or `grep` and know.

---

## 4. Provenance probe: run this constantly

For a single file:

```bash
cd ~/android_kernel_samsung_universal9830
f=include/net/sock.h
git diff --quiet 3027a7714^1 HEAD -- "$f" && echo "== 4.19 side" || echo "differs from 4.19"
git diff --quiet 3027a7714^2 HEAD -- "$f" && echo "== 4.20 side" || echo "differs from 4.20"
```

For a whole subsystem (this is the map that decides strategy):

```bash
python3 - <<'EOF'
import subprocess
def names(a, b, path):
    return set(subprocess.run(["git","diff","--name-only",a,b,"--",path],
                              capture_output=True,text=True).stdout.split())
for d in ["net/","fs/","kernel/","drivers/net/","include/net/",
          "include/linux/","include/uapi/","mm/","arch/arm64/"]:
    d19 = names("3027a7714^1","HEAD",d)
    d20 = names("3027a7714^2","HEAD",d)
    total = len(subprocess.run(["git","ls-files",d],
                               capture_output=True,text=True).stdout.split())
    print(f"{d:16} total={total:5} ==4.19:{total-len(d19):5} "
          f"==4.20:{total-len(d20):5} modified-after-merge:{len(d19 & d20):4}")
EOF
```

Interpretation:

- mostly `==4.19` → the subsystem kept the Lineage backports; its
  consumers expect 5.x APIs. Do not "upgrade" its headers to v4.20.
- mostly `==4.20` → clean upstream; consumers expect v4.20 APIs.
- a directory with a large `modified-after-merge` count is the risk zone:
  those are the files where someone already made judgement calls.

### Downgrade detection

When the merge replaced a file with the v4.20 side, check whether v4.20
was actually *older*:

```bash
git diff --numstat 3027a7714^1 3027a7714 -- include/uapi
```

A large removal count with a small addition count means the merge
downgraded a Lineage backport. Real examples already fixed this way:

| File | 4.19 -> 4.20 diff | Consequence |
|---|---|---|
| `include/uapi/linux/bpf.h` | 320 added / 2420 removed | lost `BPF_CGROUP_INET4/6_GETPEERNAME`, `GETSOCKNAME`, `SOCK_RELEASE` |
| `include/uapi/linux/fs.h` | 49 added / 5 removed | re-introduced legacy `struct fscrypt_key`, dropped `FS_VERITY_FL`, `FS_CASEFOLD_FL` |
| `include/net/addrconf.h` | +46 / -13 | duplicate `ipv6_stub`, lost `__ipv6_sock_ac_close()`, `in6_ifa_hold_safe()` |

Fix for a downgrade is `git checkout 3027a7714^1 -- <file>`, not a hand
patch, unless the file is on the Samsung core list (section 8).

---

## 5. Scan every header before every long build

Two scans catch most "one error per forty minutes" pain.

### 5.1 Duplicate definitions

Two headers that define the same `static inline` function, struct tag, or
enum tag break whichever translation unit includes both. Scan:

```bash
python3 - <<'EOF'
import os, re, subprocess
from collections import defaultdict
os.chdir(os.path.expanduser("~/android_kernel_samsung_universal9830"))
M = "3027a7714"
files = [f for f in subprocess.run(["git","ls-files","*.h"],
         capture_output=True,text=True).stdout.split()
         if f.startswith(("include/","arch/arm64/include/"))]
changed = set(subprocess.run(["git","diff","--name-only",f"{M}^1",M],
              capture_output=True,text=True).stdout.split())
func = re.compile(r"\bstatic\b[^;{}()]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{", re.S)
tag  = re.compile(r"^\s*(?:struct|enum|union)\s+([A-Za-z_]\w*)\s*\{", re.M)
inc  = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
defs, tags, includes = defaultdict(set), defaultdict(set), {}
for p in files:
    t = open(p, encoding="utf-8", errors="ignore").read()
    includes[p] = set(inc.findall(t))
    for m in func.finditer(t): defs[m.group(1)].add(p)
    for m in tag.finditer(t):  tags[m.group(1)].add(p)
def related(a, b):
    return (os.path.basename(b) in includes.get(a, ()) or
            os.path.basename(a) in includes.get(b, ()))
def report(title, table):
    print(f"== {title} ==")
    for sym, paths in sorted(table.items()):
        pl = sorted(paths)
        if len(pl) < 2 or not any(p in changed for p in pl): continue
        pairs = [(a, b) for i, a in enumerate(pl) for b in pl[i+1:] if not related(a, b)]
        if pairs:
            print(sym)
            for a, b in pairs: print(f"  {a}  <->  {b}")
report("duplicate static definitions", defs)
report("duplicate tags", tags)
EOF
```

Not every hit is real. Dismiss with evidence, not hope:

- mutually exclusive config branches (`srcutree.h` / `srcutiny.h`,
  `rwsem.h` / `rwsem-spinlock.h`)
- `#ifndef __KERNEL__` in a uapi header (`struct sigaction`)
- arch override vs `asm-generic` fallback (`virt_to_phys`, `switch_mm`)
- headers that include each other (the script already filters these)

### 5.2 Symbols the merge deleted but code still uses

```bash
python3 - <<'EOF'
import os, re, subprocess
from collections import defaultdict
os.chdir(os.path.expanduser("~/android_kernel_samsung_universal9830"))
M = "3027a7714"
git = lambda *a: subprocess.run(["git",*a],capture_output=True,text=True).stdout
headers = [h for h in git("diff","--name-only",f"{M}^1",M,"--","*.h").split()
           if not h.startswith(("tools/","Documentation/"))]
fn   = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
tag  = re.compile(r"\b(?:struct|union|enum)\s+([A-Za-z_]\w*)\s*\{")
removed = defaultdict(set)
for h in headers:
    for line in git("diff","-U0",f"{M}^1",M,"--",h).splitlines():
        if not line.startswith("-") or line.startswith("---"): continue
        body = line[1:].strip()
        if not body or body.startswith(("/*","*","//")): continue
        m = re.match(r"^\s*#\s*define\s+([A-Za-z_]\w*)", body) or tag.search(body)
        if m: removed[m.group(1)].add(h); continue
        if not body.endswith(";"):
            m = fn.search(body)
            if m: removed[m.group(1)].add(h)
open("/tmp/names.txt","w").write("\n".join(sorted(n for n in removed if len(n) >= 4)) + "\n")
raw = git("grep","-nIwF","-f","/tmp/names.txt","--","*.c","*.S")
word = re.compile(r"[A-Za-z_]\w*")
hits = defaultdict(set)
for line in raw.splitlines():
    path, _, rest = line.partition(":")
    if path.startswith("out/"): continue
    for w in set(word.findall(rest)):
        if w in removed: hits[w].add(path)
for name in sorted(hits, key=lambda n: -len(hits[n])):
    print(f"{name}  [{', '.join(sorted(removed[name]))}]")
    print(f"    {', '.join(sorted(hits[name])[:8])}")
EOF
```

Use it as a to-do list, then verify each entry by hand: a removed
declaration is only a problem when a *built* file still calls it.

### 5.3 Always

```bash
git grep -n -E '^(<<<<<<<|>>>>>>>) ' -- ':!Documentation' ':!out' | head
```

Zero conflicts markers, always. A leftover marker is not a merge style
question, it is a syntax error waiting for the least convenient moment.

---

## 6. The fast loop: targeted translation units

A full clean build costs hours. A single object costs seconds.

```bash
make O=out ARCH=arm64 \
  CC=clang LD=ld.lld AR=llvm-ar NM=llvm-nm \
  OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip \
  CROSS_COMPILE=aarch64-linux-gnu- -j2 \
  net/ipv6/ip6_output.o net/core/filter.o fs/fuse/dev.o
```

Rules:

- **Check `out/.config` first.** `make path/to/file.o` builds the file
  even when its `CONFIG_` is disabled, so you can "find" errors in code
  that is never compiled. `CONFIG_IP_SCTP` is unset here; SCTP errors are
  noise. `CONFIG_BPF_SYSCALL=y`, `CONFIG_FUSE_FS=y`,
  `CONFIG_ANDROID_BINDER_IPC=y` are real.
- Compile a *cluster* of related objects, not one at a time. Errors in one
  subsystem usually share a cause.
- Run one `make` at a time. Two concurrent kbuild invocations in the same
  `out/` corrupt each other's generated headers.
- Treat warnings from clang as future errors: this tree uses
  `-Werror=implicit-function-declaration`, `-Wincompatible-pointer-types`,
  `-Werror=designated-init`, and friends.

Full build, when the cluster is clean:

```bash
./build.sh -j2 -c        # clean
./build.sh -j2 -k        # keep going, prints every unique error
```

`-j2` is not timidity. The phone has ~4 GB available RAM; higher
parallelism gets the shell killed by Android's low-memory killer, not by
the OOM killer in the kernel under test.

---

## 7. Classify the error before fixing it

| Symptom | Real cause | Correct fix |
|---|---|---|
| `implicit declaration of X` | header moved the declaration, or v4.20 dropped it | find the owning header with `git grep -n 'X' include/`; include it, or restore the declaration from `^1` if the definition still exists |
| `redefinition of X` | both generations define it | delete the stale copy, keep the one whose consumers exist, or make one header include the other |
| `no member named Y in struct Z` | struct taken from one generation, code from the other | restore the struct from the generation its consumers expect |
| `incompatible function pointer types` | signature changed between generations | pick a generation, then update the smaller side (count call sites first) |
| `too few/many arguments` | same as above | same as above |
| `undeclared identifier ENUM_VALUE` | uapi header downgraded by merge | `git checkout 3027a7714^1 -- <uapi header>` |
| missing file for `obj-y` | v4.20 renamed/split a source file | restore the file from `^1` or port the Makefile entry |
| orphan `.c` never compiled | v4.20 renamed the file, old one stayed | delete only after proving nothing references it |

Before choosing a side, count the call sites:

```bash
grep -rn 'ip6_dst_lookup_flow(' --include='*.c' --include='*.h' . | grep -v '^./out/'
```

In that real case 13 callers used the 4-argument form and 3 used the
3-argument form, so the 4-argument form won and only 4 edits were needed.

---

## 8. Non-negotiable rules

- Branch stays `K4.20`.
- Never `--allow-unrelated-histories`, never `--depth`, never drop a remote.
- Never bulk `--theirs` / `--ours` on: `drivers/gpu/arm`,
  `drivers/soc/samsung`, `drivers/clk/samsung`, `drivers/pinctrl/samsung`,
  `drivers/gpu/drm/samsung`, `kernel/sched` (EMS), `sec_*`, defex,
  `arch/arm64`, `arch/arm64/boot/dts/exynos`, `include/linux/mfd/samsung`.
  Resolve those per hunk, by hand.
- Never normalise these Android 17 paths to v4.20: `fs/f2fs/**`,
  `fs/crypto/**`, `fs/verity/**`, `include/linux/fscrypt.h`,
  `include/linux/fsverity.h`, `include/linux/f2fs_fs.h`,
  `include/uapi/linux/fscrypt.h`, `security/selinux/**`,
  `drivers/android/**`. They are newer than v4.20 on purpose; reverting
  them breaks FBE, f2fs, SELinux policy or binder.
- `include/linux/fs.h` is v4.20, but must keep the Lineage `S_CASEFOLD`,
  `S_VERITY`, `IS_CASEFOLDED()` and `IS_VERITY()` definitions that
  `fs/crypto`, `fs/verity` and `fs/f2fs` consume.
- Hybridswap is a required ROM feature but is not in this tree yet. When
  it is ported, never normalise its files (`mm/hybridswap*`,
  `include/linux/hybridswap.h`, zram/swap hooks, `CONFIG_HYBRIDSWAP`) to
  upstream v4.20; keep the Samsung implementation and its Kconfig.
- Do not silently revert a post-merge fix commit. Check
  `git log --oneline -8` and `git diff 3027a7714 HEAD -- <file>` before
  `git checkout`.
- Do not delete a file because it "looks old". Prove it is unbuilt and
  unreferenced first.
- `out/` is untracked and ignored. Never commit it again.
- Do not build with `export CC=clang`. `Makefile` assigns
  `CC = $(CROSS_COMPILE)gcc` with plain `=`, which beats the environment.
  The toolchain must be passed on the `make` command line, as `build.sh`
  does. A log containing `cc1: some warnings being treated as errors` is a
  gcc log; clang logs say `N errors generated`.
- Do not touch `arch/arm64/Makefile`'s duplicate `dtbs` recipe while a
  build is running; it is cosmetic and can wait.

---

## 9. Case law already established

Fix these the same way again, do not re-litigate them.

| Problem | Decision |
|---|---|
| `printk_safe_init()` undeclared | v4.20 `include/linux/printk.h` declares it and provides a `!CONFIG_PRINTK` stub; restore both |
| `__iter_div_u64_rem` defined twice | v4.20 `include/linux/math64.h` includes `<vdso/math64.h>`; the function has exactly one owner, the vdso header |
| `CLANG_PREFIX` pointed at `/usr/bin/` | must be `--prefix=$(dir $(which $(CROSS_COMPILE)as))$(CROSS_COMPILE)` |
| `struct fscrypt_key` twice | Lineage moved it to `uapi/linux/fscrypt.h`; `uapi/linux/fs.h` must be the Lineage version |
| `ipv6_stub` twice | `net/ipv6_stubs.h` owns it; `addrconf.h` includes that header |
| `ip6_dst_lookup_flow` arity | 4 arguments `(net, sk, fl6, final_dst)`; the stub member has the same shape |
| `inet6_bind` flags | `u32 flags` with `BIND_WITH_LOCK` / `BIND_FORCE_ADDRESS_NO_PORT`, not booleans |
| `neigh_output()` | three arguments, third is `skip_cache` |
| `mmap_lock`, `make_task_dead`, `struct sched_param`, `probe_kernel_read` | v4.20 callers expect the 5.x-ish helpers; declarations restored in `mm.h`, `sched/task.h`, `sched/types.h`, `uaccess.h` |
| `prog->call_get_stack` | field does not exist in this tree's `struct bpf_prog`; the check was removed from `kernel/events/core.c` |
| `VM_FAULT_*_HINDEX` | owned by `mm_types.h`; duplicates removed from `mm.h` |
| vendor 5.9 BPF backport | do not restore it. v4.20 lacks the required core (BTF, trampoline, local storage, iterators); the backport alone produced about 550 errors. `kernel/bpf/**`, BPF/BTF/filter/skmsg headers, `net/core/filter.c` and the BPF UAPI stay v4.20 |
| vendor pseudo-fs / `init_fs_context` | do not mix with the v4.20 VFS. `struct file_system_type` in this tree has no `init_fs_context`; use v4.20 `fs/libfs.c` and `mount_pseudo()`/`mount_pseudo_xattr()`, and leave `fs/fs_context.c` and `fs/fs_parser.c` uncompiled |
| `dma_common_mmap` / `dma_common_get_sgtable` / `dma_common_free_remap` | use the v4.20 signatures (`attrs` argument on the first two, no `nowarn` on the last) and update vendor callers such as `drivers/iommu/dma-mapping-fast.c` |
| `arch_dma_mmap_pgprot` | the arch header defines it as an object-like macro; `arch/arm64/mm/dma-mapping.c` must `#undef` it before defining the function |
| `sched_idle_set_state` | v4.20 takes one argument. The vendor `index` parameter belongs to a newer scheduler; do not change the v4.20 header to match it |
| `kernfs_xattr_get/set` | v4.20 kernfs keeps xattrs private; the public wrappers are a deliberate Samsung/SELinux seam, not a general v4.20 API |
| memory hotplug / PASR | do not enable until `arch_add_memory()` and `ARCH_ENABLE_MEMORY_HOTPLUG/HOTREMOVE` are ported to arm64. Leaving the Kconfig symbols on without the arch code only hides the gap |

---

## 10. Evidence discipline

Every fix batch answers three questions in the commit message:

1. What failed (the exact compiler message).
2. Why it failed (the provenance: which side moved what).
3. Why the chosen side is the right one (call-site count, upstream
   owner, config).

Commit style used in this branch:

```
<subsystem>: <short summary>

- <file>: <what and why>
- <file>: <what and why>
```

For code that comes from outside this tree, mark where it came from with
one of the five provenance prefixes (Android Common Kernel convention),
then the subsystem:

- `UPSTREAM:` mainline patch applied as-is (add the
  `(cherry picked from commit <hash>)` line when the hash is known).
- `BACKPORT:` mainline patch that had to be adapted to this older tree.
- `FROMGIT:` taken from a maintainer tree, not in mainline yet.
- `FROMLIST:` taken from a mailing list, not accepted yet.
- `ANDROID:` Android-only change with no mainline counterpart.

Local seam fixes use a plain subsystem prefix (`kbuild:`, `kconfig:`,
`arm64:`, `docs:`). Above all, the subject must say what changed and
why it matters, e.g. `BACKPORT: mmc: restore the Exynos tuning API`,
so the intent is obvious when reading `git log` months later.

Leave `notes.md` in English, no emoji, no commentary about where the
build was run. Update it when a milestone changes, not for every commit.

When a rewrite or amend is unavoidable, say so explicitly, note it in
`notes.md`, and tell the human that other clones need
`git fetch && git reset --hard origin/K4.20`.

---

## 11. Escalate instead of thrashing

Stop and ask the human when:

- a fix would require choosing a generation for a whole subsystem and the
  two choices are both defensible (for example: normalise all of `net/` to
  v4.20, versus restore the Lineage 4.19 network stack and its backports);
- the same header has produced three separate conflicts;
- a targeted compile passes but the same symbol keeps failing in another
  unit, which usually means the header choice itself is wrong;
- a change would touch a Samsung core path listed in section 8.

Present the fork with counts and a recommendation. "I fixed the error" is
not an answer when the error is a symptom of a wrong seam.

---

## 12. Where the work stands

Target userspace: **Android 17 / LineageOS 24.0**, for every supported
universal9830 device (not `z3s` only). Build compatibility is necessary
but not sufficient; the Android-critical paths in section 1 must keep
their Lineage APIs.

Measured provenance map (`3027a7714^1` = 4.19, `3027a7714^2` = 4.20):

```
net/             total= 1772  ==4.19: 1374  ==4.20:  973  modified: 197
fs/              total= 1973  ==4.19: 1643  ==4.20: 1174  modified: 167
kernel/          total=  476  ==4.19:  348  ==4.20:  198  modified:  48
drivers/net/     total= 8175  ==4.19: 7178  ==4.20: 3036  modified: 353
include/net/     total=  320  ==4.19:  269  ==4.20:  194  modified:  24
include/linux/   total= 2526  ==4.19: 2198  ==4.20: 1815  modified: 108
include/uapi/    total=  894  ==4.19:  835  ==4.20:  731  modified:  21
mm/              total=  130  ==4.19:   73  ==4.20:   49  modified:  27
block/           total=  111  ==4.19:   81  ==4.20:   61  modified:  18
```

Read this carefully: no subsystem is uniformly one generation. `net/` is
roughly 55% 4.19 and 40% 4.20, which is exactly why it produces a stream
of signature and struct mismatches. Expect the same in `fs/` and
`drivers/net/`.

Progress estimate after the latest checkpoint:

| Area | Estimate |
|---|---:|
| v4.20 merge and generic normalization | 100% |
| Build-clean | ~80-85% |
| Boot and stability | 0% |
| Overall | ~80% |

The estimate is based on the last full build (553 errors, about 550 in the
vendor 5.9 BPF backport). The BPF backport is now reverted and the related
seam fixes are in the working tree, but the checkpoint has not been rebuilt.
Do not treat 80-85% as a green build; only a full `-j4 -k` run with `dtbs`
can confirm it.

- v4.20 merge committed as `3027a7714`.
- Build fixes: `962ddc46b`, `634c8c9cb`, `4c371f972`, `358220981`,
  `1a1232fb6`.
- Already unified: `math64` ownership, `printk_safe_init`, clang
  toolchain plumbing, `bpf.h` restored, `fs.h` restored, `ipv6_stub`
  ownership, `ip6_dst_lookup_flow` arity, `inet6_bind` flags.
- Deliberately reverted or deferred: vendor 5.9 BPF backport; FUSE
  passthrough/virtiofs; the vendor `fs_context` pseudo-fs; memory-hotplug
  and PASR; printk process-name extension; warn-limit policy; memory-boost
  sysfs/reclaim policy. See `notes.md` for the full table.
- Next work is measured, not guessed: rebuild the current checkpoint,
  classify the remaining seam errors, fix them, then run the final build
  with `dtbs`. Only after that can the human boot-test v4.20.
- `arch/arm64/Makefile` still has the duplicate `dtbs` / `dtbs_install`
  recipes inherited from 4.19. Cosmetic, fix after the build is green.
- Hybridswap: required for the Android 17 ROM, but there is no
  `hybridswap` source, Kconfig symbol or header in this tree. Documentation
  reserves the path; implementation needs a reference patch/repo.
- v5.0 work is blocked until v4.20 builds and the human boot-tests it.
  Before that: `git fetch --unshallow --filter=blob:none origin` and fetch
  tags `v4.19.325`, `v4.20`, `v5.0`; verify
  `git merge-base HEAD v4.19.325` = `a67e7cdde7cc7984ae24c3c81a70dc1aa34424b1`.

---

## 13. Boot test logging readiness (v4.20 checkpoint)

A silent bootloop or stall at the Samsung splash screen is useless without
captured logs. Before asking the user to flash or test an image, verify the
entire post-mortem logging pipeline:

### 13.1 Pstore and Ramoops configuration

The kernel configuration must have the following symbols enabled:
- `CONFIG_PSTORE=y`
- `CONFIG_PSTORE_RAM=y`
- `CONFIG_PSTORE_CONSOLE=y`
- Optional but recommended: `CONFIG_PSTORE_PMSG=y`, `CONFIG_PSTORE_FTRACE=y`

### 13.2 Memory reservation for Ramoops

In this tree, the Exynos 990 ramoops memory reservation is wired through
Samsung's debug-snapshot framework:
- Device tree node: `log_pstore` under `reserved-memory` in
  `arch/arm64/boot/dts/exynos/exynos9830-rmem.dtsi` at `reg = <0 DSS_LOG_PSTORE_ADDR DSS_LOG_PSTORE_SIZE>`
  (`DSS_LOG_PSTORE_ADDR = 0xeb308000`, `DSS_LOG_PSTORE_SIZE = SZ_32K`).
- Dynamic platform device: `lib/debug-snapshot-pstore.c` dynamically registers
  `dss_ramoops` using `dbg_snapshot_get_item_paddr("log_pstore")`.
- **Caveat**: Never invent or guess RAM addresses in device tree files. Any
  manual ramoops node must be backed by an unmapped/free region confirmed from
  the stock Samsung bootloader DTB. If a dedicated standalone ramoops node is
  proposed, report the physical base and size and obtain user confirmation first.
- Note on console logs: `dss_ramoops_data` requires `.console_size` to be
  non-zero (e.g. 8K or 16K) to emit `console-ramoops-0`.

### 13.3 Samsung debug logging (sec_debug)

Samsung platform crash logging is driven by `CONFIG_SEC_DEBUG=y` and its
family:
- `CONFIG_SEC_DEBUG_LAST_KMSG=y` (provides `/proc/last_kmsg` across warm reboot)
- `CONFIG_SEC_DEBUG_AUTO_COMMENT=y`, `CONFIG_SEC_DEBUG_EXTRA_INFO=y`
- `CONFIG_DEBUG_SNAPSHOT=y`
- **Rule**: Never drop or disable `sec_debug` features just to appease a build
  error or ramoops conflict. If an unavoidable change is required, document it
  in `notes.md` under Deviations.

### 13.4 Kernel command line

- `ignore_loglevel` ensures all `pr_debug` / `pr_info` output reaches the
  console buffers before any hang.
- `earlycon` can be wired via `CONFIG_CMDLINE_EXTEND` or `boot.img` cmdline if
  UART is accessible.

### 13.5 Retrieval checklist (executed by the user)

```bash
mount -t pstore pstore /sys/fs/pstore
ls -la /sys/fs/pstore/
cat /sys/fs/pstore/console-ramoops-0
cat /proc/last_kmsg
```

Remember: Samsung bootloaders may clear parts of DRAM on reboot depending on
reset reason. Pstore / ramoops must be treated as unproven until verified on
hardware once.

### 13.6 Pre-flash user checklist

1. Tag the release: `git tag boot-4.20-try1`
2. Stock firmware ready in Odin; known working 4.19 `boot.img` backed up.
3. Keep `boot.img` header format, dtb/dtbo, and cmdline identical to the working ROM.
4. Verify `PSTORE_CONSOLE` and ramoops / `last_kmsg` status before flashing.
5. Do not proceed to v5.0 until v4.20 produces readable logs or boots.

