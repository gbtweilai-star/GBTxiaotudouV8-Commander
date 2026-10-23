# -*- coding: utf-8 -*-
"""影子仓库 —— 把"我们的文件"复制成一个干净分块。

Owner 2026-09-22：「按照最稳定的方式，不会影响你运行的来设计」→「可以」

═══ 为什么是影子仓，而不是在当前仓里 git rm ═══
  当前仓此刻**有一个 git add -A 循环在反复跑**（agent-host-git-diff）。
  在它跑的时候动 .git/index ⇒ 抢锁 ⇒ 索引可能损坏。
  ⇒ 影子仓**全程不写当前仓的索引**：那个循环察觉不到我，我也不跟它抢锁。
     万一失败，原仓一个字没变。

═══ 六步 ═══
  1 拿权威清单（只读）—— **git ls-files --cached --others --exclude-standard**
  2 过滤：摘出临时区；剔除 gitignore 挡住的（node_modules 等，不入任何仓）
  3 按清单**逐个复制**到 .shadow-repo/
  4 在影子目录 git init + add + commit（全新空仓，与当前仓无关）
  5 验收：用**闭合恒等式**核，而不是拿两个不相干的数硬比
  6 推送 —— **推哪儿由主人定，本脚本不推**

═══ 为什么权威清单不能只用 git ls-files（第 2 个坑）═══
  2026-09-22 第二跑：闭合式验收全绿（余项 0），但一查产物就发现
  **V22 两个交付件、capabilities.html、index.html、archive/、projects/ 全不在分块里**。
  真因：本仓 .git/index 被一个 09-21 16:24 的**陈旧 index.lock 冻住了**
  （index 最后写入 09-21 15:16:58），此后新建/改动的文件一次都没入册 ⇒
  `git ls-files` 只认索引 ⇒ 我拿一份**冻结的旧账**当权威。
  实测：cached 38,494 · untracked-but-not-ignored 131 · 并集 38,625。
  那 131 个恰恰是本轮最重要的东西（V22 交付、能力球、工作区入口、projects/、
  plugins/、deploy/、memory/2026-09-22-*）。
  ⇒ 权威 = `--cached --others --exclude-standard`（= git 真正会管的全部），
     而不是"索引里碰巧有的"。**验收全绿 ≠ 东西齐** —— 尺子对了才谈得上对。

═══ 为什么第 5 步不能拿 copied == ls-files 硬比（第 1 个坑）═══
  2026-09-22 首跑就是栽在这：报告 2,778 vs 2,214「差 564，不许推送」。
  真因不是仓坏了，是**验收式写错了** —— 被 .gitignore 挡住的文件在盘上、
  但永远不入册，两个数本来就不该相等。差的那 564 个全是
  holo_pet/node_modules/**（electron 二进制）。仓是好的，尺子是坏的。
  ⇒ 现在用闭合恒等式，并强制**余项为 0**才放行：

      清单 keep = 在盘 present + 不在盘 absent
      在盘 present = 入册 tracked + 被忽略 ignored
      在册不在盘 must == 0        ← 最强的"没丢东西"证据
      tracked == present - ignored

  任何一项不闭合 ⇒ 余项非 0 ⇒ 打印余项明细 ⇒ exit 1，绝不静默放行。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(".").resolve()
SHADOW = ROOT / ".shadow-repo"
SCRATCH = ROOT / ".scratch"
LISTF = SCRATCH / "_shadow_filelist.json"
MANIFEST = SCRATCH / "_shadow_manifest.json"

# 摘出规则：前缀目录 + 精确文件名（这些是临时区/调试残留，不属于成品分块）
DROP_PREFIX = (".scratch/", ".trash/", ".backups/", ".playwright-cli/")
DROP_EXACT = {"test.txt"}

# 强制纳入：本仓 .gitignore 挡了、但**工作区自己的规则书要求必须留**的路径。
#   archive/ ← .gitignore L47 排除它，可是 OUTPUT_RULES.md 写着：
#     L115「archive/ 下的文件严禁修改，保持历史快照」
#     L334「历史版本可回退 | archive/ 含 V1...V{N-1} 全部历史版本」← 这是验收项
#     L67/L91-92 每次升版前必须先归档 ⇒ archive/ 是**规则强制产物**，不是垃圾
#   42 个文件 / 9.38 MB，装的是 V1→V21 全部历史版本。丢了就没有回退。
#   ⇒ 不擅自改原仓 .gitignore（那是全仓策略），只在本分块里显式纳入。
INCLUDE_OVERRIDE = ("archive/",)


def sh(args, cwd=None, timeout=1800, data=None):
    """跑命令，**统一走 bytes** —— 中文路径不被 codepage 吃掉。"""
    r = subprocess.run(args, capture_output=True, timeout=timeout,
                       cwd=str(cwd or ROOT), input=data)
    dec = lambda b: (b or b"").decode("utf-8", "replace")   # noqa: E731
    return r.returncode, dec(r.stdout), dec(r.stderr)


def git_paths(args, cwd=None):
    """返回 git 的**原始未转义**路径集（-z + quotepath=false）。"""
    rc, out, err = sh(["git", "-c", "core.quotepath=false"] + args, cwd=cwd)
    if rc != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {err[:200]}")
    return set(p for p in out.split("\0") if p), out


def force_rmtree(p: Path) -> None:
    """删目录树，**先摘 Windows 只读位**。

    为什么不能用 shutil.rmtree(ignore_errors=True)：
      本仓 tools/codex-scripts/*.frozen.out 五个文件是只读的（IsReadOnly=True，
      2026-09-16 冻结的探针输出）。Windows 上只读文件 rmtree 删不掉，
      ignore_errors=True 又把失败**吞掉** ⇒ 上一轮的只读残留静默留到这一轮，
      这一轮复制时撞上只读目标 ⇒ PermissionError。
      2026-09-22 实跑就是先报 0 失败、再报 5 失败，真因是"清理没清干净还被静默"。
    ⇒ 明着删、明着摘只读位，删不掉就报出来，不吞。
    """
    if not p.exists():
        return
    for dp, dn, fn in os.walk(p, topdown=False):
        for f in fn:
            fp = Path(dp, f)
            try:
                os.chmod(fp, stat.S_IWRITE)
                fp.unlink()
            except OSError:
                pass
        for d in dn:
            try:
                os.chmod(Path(dp, d), stat.S_IWRITE)
                Path(dp, d).rmdir()
            except OSError:
                pass
    try:
        os.chmod(p, stat.S_IWRITE)
        p.rmdir()
    except OSError:
        pass
    if p.exists():
        raise RuntimeError(f"清不掉影子目录（有文件被占用？）: {p}")


def check_ignored(paths, cwd=None):
    """哪些路径会被 .gitignore 挡住。一次性喂 stdin，避免 N 次进程开销。

    **必须带 --no-index**：默认模式会跳过"已被索引登记"的路径 ——
    而 holo_pet/node_modules 恰恰就是被登记过的（564 个第三方文件漏进了索引）。
    2026-09-22 实测：默认查同一路径返回空，--no-index 才如实报 ignored。
    """
    if not paths:
        return set()
    payload = "\0".join(paths).encode("utf-8")
    rc, out, err = sh(["git", "check-ignore", "--no-index", "--stdin", "-z"],
                      cwd=cwd, data=payload)
    if rc not in (0, 1):                      # 1 = 一个都没被忽略，属正常
        raise RuntimeError(f"git check-ignore 失败 rc={rc}: {err[:200]}")
    return set(p for p in out.split("\0") if p)


def recoverability(paths):
    """不在盘的文件：内容还能不能捞回来。HEAD → 索引 → 都没有。"""
    in_head, in_index, gone = [], [], []
    for p in paths:
        if sh(["git", "cat-file", "-e", "HEAD:" + p])[0] == 0:
            in_head.append(p)
        elif sh(["git", "cat-file", "-e", ":" + p])[0] == 0:
            in_index.append(p)                # 暂存过没提交，blob 还在
        else:
            gone.append(p)
    return in_head, in_index, gone


def main() -> int:
    t0 = time.time()
    print("=" * 76)
    print("影子仓库 · 建干净分块")
    print("=" * 76)

    # ── 步骤 1+2：拿清单并过滤（**只读**）──
    # 权威 = git 真正会管的全部 = 已入册 + 未入册但未被忽略。
    # 只认 --cached 会把"索引冻结后新建的东西"整个漏掉（V22 交付就是这么差点没了）。
    allf, _ = git_paths(["ls-files", "--cached", "--others",
                         "--exclude-standard", "-z"])
    cached, _ = git_paths(["ls-files", "--cached", "-z"])
    keep, drop = [], []
    for f in sorted(allf):
        s = f.replace("\\", "/")
        (drop if (s.startswith(DROP_PREFIX) or s in DROP_EXACT) else keep).append(f)
    fresh = len(allf) - len(cached)               # 索引冻结后新出现的，最容易被漏掉

    ignored = check_ignored(keep)             # node_modules 等：永不入仓
    keep = [f for f in keep if f not in ignored]

    # 强制纳入：.gitignore 挡了、但规则书要求留的（见 INCLUDE_OVERRIDE 注释）。
    # allf 来自 --exclude-standard，本就不含这些 ⇒ 必须回盘上单独捞。
    forced = []
    for pre in INCLUDE_OVERRIDE:
        base = ROOT / pre.rstrip("/")
        if base.is_dir():
            for dp, _dn, fn in os.walk(base):
                for f in fn:
                    rel = Path(dp, f).relative_to(ROOT).as_posix()
                    if not rel.startswith(DROP_PREFIX):
                        forced.append(rel)
    forced = sorted(set(forced) - set(keep))
    keep = sorted(set(keep) | set(forced))
    ignored -= set(forced)

    SCRATCH.mkdir(parents=True, exist_ok=True)
    LISTF.write_text(json.dumps(
        {"keep": keep, "drop": drop, "ignored": sorted(ignored),
         "forced": forced},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  步骤 1+2  已入册 {len(cached):,} + 未入册 {fresh:,} = 受控 {len(allf):,}"
          f" · 摘出临时区 {len(drop):,} · 剔除 gitignore {len(ignored):,}"
          f" · 强制纳入 {len(forced):,} · **保留 {len(keep):,}**")
    if forced:
        f_mb = sum((ROOT / f).stat().st_size for f in forced
                   if (ROOT / f).is_file()) / 1024 / 1024
        tops = Counter(f.split("/")[0] for f in forced)
        print("           强制纳入明细（.gitignore 挡了、规则书要求留）: "
              + " · ".join(f"{k} {v}" for k, v in tops.most_common(5))
              + f" · {f_mb:,.1f} MB —— 依据 OUTPUT_RULES.md L115/L334")
    if ignored:
        ig_mb = sum((ROOT / f).stat().st_size for f in ignored
                    if (ROOT / f).is_file()) / 1024 / 1024
        tops = Counter(f.replace("\\", "/").split("/")[0] for f in ignored)
        print("           剔除明细（被 .gitignore 挡住、却曾漏进索引的）: "
              + " · ".join(f"{k} {v}" for k, v in tops.most_common(5))
              + f" · 共 {ig_mb:,.1f} MB（可再生，不入任何仓）")
    print(f"           清单 -> {LISTF.relative_to(ROOT)}")

    # ── 步骤 3：按清单复制（只复制清单里的，不全盘拷）──
    if SHADOW.exists():
        print(f"  步骤 3  影子目录已存在，先清掉重来: {SHADOW.name}")
        force_rmtree(SHADOW)
    SHADOW.mkdir(parents=True, exist_ok=True)
    copied, absent, failed = 0, [], []
    for f in keep:
        src, dst = ROOT / f, SHADOW / f
        try:
            if not src.is_file():
                absent.append(f)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        except Exception as e:                                    # noqa: BLE001
            failed.append({"f": f, "why": f"{type(e).__name__}: {str(e)[:60]}"})
    tot_mb = sum((SHADOW / f).stat().st_size for f in keep
                 if (SHADOW / f).is_file()) / 1024 / 1024
    print(f"  步骤 3  已复制 **{copied:,}** 个 · 不在盘 {len(absent)} · 失败 {len(failed)} "
          f"· 共 {tot_mb:,.1f} MB")

    # ── 步骤 4：影子仓 git init + add + commit（在另一个目录，与当前仓无关）──
    msg = (f"干净分块：受控 {len(allf):,}（已入册 {len(cached):,} + 未入册 {fresh:,}）"
           f"中摘出临时区 {len(drop):,}、剔除 gitignore {len(ignored):,}，"
           f"保留 {copied:,} 个真实文件")
    for cmd in (["git", "init", "-q"],
                ["git", "add", "-A"],
                ["git", "-c", "user.name=GBT小土豆V8", "-c", "user.email=gbt@local",
                 "commit", "-q", "-m", msg]):
        rc, o, e = sh(cmd, cwd=SHADOW)
        if rc != 0 and "nothing to commit" not in (e or ""):
            print(f"  步骤 4  ✘ {' '.join(cmd[:2])} 失败: {e[:300]}")
            return 1

    # 影子仓继承了同一份 .gitignore ⇒ add -A 同样会跳过 archive/。
    # 所以强制纳入的那批必须显式 add -f，否则"清单里有、仓里没有"。
    if forced:
        rc, o, e = sh(["git", "add", "-f", "--pathspec-from-file=-",
                       "--pathspec-file-nul"],
                      cwd=SHADOW, data="\0".join(forced).encode("utf-8"))
        if rc != 0:
            print(f"  步骤 4  ✘ 强制 add 失败: {e[:300]}")
            return 1
        rc, o, e = sh(["git", "-c", "user.name=GBT小土豆V8", "-c", "user.email=gbt@local",
                       "commit", "-q", "-m",
                       f"按 OUTPUT_RULES.md L115/L334 强制纳入 {len(forced)} 个历史快照"
                       f"（archive/ V1→V21，历史版本可回退）"], cwd=SHADOW)
        if rc != 0 and "nothing to commit" not in (e or ""):
            print(f"  步骤 4  ✘ 强制纳入提交失败: {e[:300]}")
            return 1
        print(f"  步骤 4  强制纳入已入库 {len(forced):,} 个")

    # ── 步骤 5：闭合式验收 ──
    tracked, raw = git_paths(["ls-files", "-z"], cwd=SHADOW)
    disk = set()
    for dp, _dn, fn in os.walk(SHADOW):
        if ".git" in Path(dp).parts:
            continue
        for f in fn:
            disk.add(Path(dp, f).relative_to(SHADOW).as_posix())
    only_disk = disk - tracked
    only_git = tracked - disk
    ignored_in_shadow = check_ignored(sorted(only_disk), cwd=SHADOW) if only_disk else set()
    unexplained = only_disk - ignored_in_shadow

    prime = len(keep)
    lhs_ok = (prime == copied + len(absent))                  # 清单 = 在盘 + 不在盘
    mid_ok = (copied == len(tracked) + len(ignored_in_shadow))  # 在盘 = 入册 + 被忽略
    git_ok = (len(only_git) == 0)                             # 在册不在盘 == 0
    clean_ok = (len(unexplained) == 0)                        # 无说不清的余项
    ok = lhs_ok and mid_ok and git_ok and clean_ok

    print()
    print("─" * 76)
    print("  步骤 5  闭合式验收（余项必须为 0）")
    print(f"          ① 清单 {prime:,} = 在盘 {copied:,} + 不在盘 {len(absent):,}"
          f"   余项 {prime - copied - len(absent):+d}  {'✔' if lhs_ok else '✘'}")
    print(f"          ② 在盘 {copied:,} = 入册 {len(tracked):,} + 被忽略 {len(ignored_in_shadow):,}"
          f"   余项 {copied - len(tracked) - len(ignored_in_shadow):+d}  {'✔' if mid_ok else '✘'}")
    print(f"          ③ 在册不在盘 {len(only_git):,}        "
          f"{'✔ 没丢东西' if git_ok else '✘ 有入册文件不在盘'}")
    print(f"          ④ 说不清的余项 {len(unexplained):,}      "
          f"{'✔' if clean_ok else '✘'}")
    print(f"          ⇒  {'✔ 闭合 —— 可以推送' if ok else '✘ 不闭合 —— 不许推送'}")

    # ── 步骤 5b：不在盘的那批，内容还捞不捞得回来（不许把"没丢"当口号）──
    if absent:
        in_head, in_index, gone = recoverability(absent)
        print(f"          ⑤ 不在盘 {len(absent):,} 的可恢复性："
              f"HEAD {len(in_head):,} · 暂存blob {len(in_index):,} · 两无 {len(gone):,}")
        for p in gone:
            print(f"             ⚠ 两无: {p}")

    # ── 步骤 5c：入册文件逐个 sha256，落成可复核清单 ──
    rows, t = [], time.time()
    for f in sorted(tracked):
        p = SHADOW / f
        if p.is_file():
            h = hashlib.sha256()
            with p.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            rows.append({"path": f, "size": p.stat().st_size, "sha256": h.hexdigest()})
    MANIFEST.write_text(json.dumps(
        {"count": len(rows), "total_bytes": sum(r["size"] for r in rows), "files": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"          ⑥ sha256 清单 {len(rows):,} 条 · "
          f"{sum(r['size'] for r in rows)/1048576:,.1f} MB · {round(time.time()-t, 1)}s"
          f" -> {MANIFEST.relative_to(ROOT)}")

    # ── 步骤 5d：**产物在场断言** ──
    # 第 2 个坑的教训：闭合式验收四项全绿，产物照样是缺的。
    # "账平了" 和 "东西齐了" 是两件事 —— 必须分开各证一次。
    present = {r["path"] for r in rows}
    CRITICAL_FILES = [
        "AGENTS.md", "SOUL.md", "USER.md",
        "gbt_allinone/security/policy.py",          # 唯一的授权门，绝不能缺
        "V22 GBT小土豆V8-可交互原型.html",
        "V22 GBT小土豆V8-无限画布.html",
        "capabilities.html", "index.html", ".gitignore",
        "holo_pet/package.json", "projects/README.md",
        "archive/V21 GBT小土豆V8-可交互原型.html",
        "archive/V21 GBT小土豆V8-无限画布.html",
    ]
    CRITICAL_DIRS = ["assets/brand", "memory", "projects", "gbt_allinone",
                     "tools", "delivery", "holo_pet", "render", "archive"]
    miss_f = [p for p in CRITICAL_FILES if p not in present]
    miss_d = [d for d in CRITICAL_DIRS
              if not any(x.startswith(d + "/") for x in present)]
    for p in CRITICAL_FILES:
        print(f"             {'✔' if p in present else '✘ 缺'} {p}")
    for d in CRITICAL_DIRS:
        n = sum(1 for x in present if x.startswith(d + "/"))
        print(f"             {'✔' if n else '✘ 缺'} {d}/  ({n} 个文件)")
    presence_ok = not miss_f and not miss_d
    print(f"          ⑦ 产物在场: {'✔ 齐' if presence_ok else '✘ 有缺 —— 不许推送'}"
          + (f"  缺: {miss_f + miss_d}" if not presence_ok else ""))
    ok = ok and presence_ok
    print("─" * 76)
    print("  步骤 6  推送: **本脚本不推** —— 推哪儿由你定（我建议新分支 clean-block）")
    print()
    print(f"  影子仓位置: {SHADOW.relative_to(ROOT)}")
    print(f"  耗时 {round(time.time()-t0, 1)}s")
    print("  **当前仓一个字没动** —— 索引、锁、那个 add -A 循环，全没碰")
    if failed:
        print(f"  ⚠ 复制失败 {len(failed)}: {failed[:3]}")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
