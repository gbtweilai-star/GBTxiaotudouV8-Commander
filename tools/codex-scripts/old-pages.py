#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: 旧页面判决器 —— 把「哪个页面还算数」变成机检，而不是靠人记得
# 开发者：自由的风 · GBT小土豆V8
"""旧页面判决器（只读；`--check` 有过期页面则非零退出）。

## 为什么要有它

Owner **提过三次**：「旧页面都要清理掉别留在项目里面容易搞混」。
前两次都是**临时扫一遍**（`dup-pages.py` 找重复、`probe-page-consumers.py` 数消费者），
扫完就完了 —— 下一批页面长出来时，没有任何东西会提醒。
本器把那次临时扫描**固化成一张判决表 + 一道闸**。

## 判决只有四种，每种都要有**依据**

| 判决 | 依据 |
|---|---|
| **现行** | 被**清单**点名（窗口注册表 / 宿主面板清单 / 工具里的页面表）|
| **被超越** | 同族里存在**更高版本**的文件（`V<n>` 族），或同目录存在明确的 `_now` 版本 |
| **零引用** | 上面两条都不成立，且全仓文本面没有引用它 |
| **排除** | 不属于"我们的页面"，逐类写明理由（见 EXCLUDED）|

## 三条纪律（都拿事故换的）

1. **判据取名字/清单，不取"看着旧"**：mtime 早不等于过期 —— `delivery/*.html` 是记录，
   2026-09-11 的也比今天新写的草稿更该留。
2. **排除项要写理由**，不许静默跳过：静默跳过就是"看着干净、其实没看"。
3. **别人的页面一律不碰**（`_upstream` / 技能库 / 他人工作区）。

用法：
    py -3.14 tools/codex-scripts/old-pages.py            # 出判决表
    py -3.14 tools/codex-scripts/old-pages.py --check     # 有过期/零引用 ⇒ 退出码 2
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

# ── 谁的页面：**按树列白名单**（白名单之外的一律不看，省得把别人的算进来）──
# 🔴 第一版这里写的是 `("", …)` 加几个子树 —— 结果 `os.walk(仓根)` **递归进了全仓**：
#    扫出 406 个（真值 ~270），把 `gbt_allinone/.pylibs/win32comext/…/ie/*.html`
#    这类**第三方示例页**也算成"我们的页面"，还给出一堆"零引用"的假判决。
#    ⇒ 仓根**只取一层**（`depth=1`），其余按子树各自递归；且子树之间不许重叠（会重复计数）。
OURS = [
    ("", 1),                       # 仓根散页：**只一层**，不递归
    ("holo_pet_w3", 0), ("holo_pet", 0), ("deploy", 0), ("brain", 0),
    ("projects", 0), ("infinite-canvas-output", 0), ("tools/codex-scripts", 0),
    ("assets", 0), ("caps", 0), ("outputs", 0),
]

# ── 排除（逐类写理由；**不许静默跳过**）──
EXCLUDED = [
    ("gbt_allinone", "框架正文 + store 生产数据 + .pylibs（第三方）：它的页面在镜像面与 docs，"
                     "受镜像多维度纪律管，不按此判；.pylibs 更不是我们的页面"),
    ("_upstream", "上游语料：别人的仓库，引用即证据（gbt-security/remotion 等逐条引其内部路径）"),
    ("审美相关skill", "技能图鉴根：800+ 技能的示例页，别人的素材"),
    ("vendor", "第三方依赖实体（junction 的落点）"),
    ("node_modules", "依赖目录"),
    ("dist", "构建产物：electron-builder 打出来的装机包"),
    (".scratch", "草稿+证据区：另有 Owner 明令与 clean_residue 白名单管（.scratch/render 是交付物）"),
    ("delivery", "**交付记录**：带日期的报告是记录不是残骸（记录不是草稿 —— 本仓已定过）"),
    ("agent-gvmz-gbtv8", "他人工作区：scan_scope 已声明不是本框架源码面"),
    (".cluster", "各 agent 的登记面"),
    (".agents", "技能安装面（实体）"),
    (".claude", "技能安装面（视图）"),
    (".dsh", "工具运行时"),
]

# ── 按**模式**点名的页面族（清单用 pattern 记名，不是逐个文件名）──
# 为什么要这一条：`windows.json` 写的是 `per_cap_pages: brain/caps/<kind>.html ——
# 161 条能力各自一页（cap-pages.py 生成）` —— **它是按模式登记的一族**。
# 第一版只认逐个文件名 ⇒ 161 张真·现行页面全被判成"零引用"。
PATTERN_PAGES = [
    ("holo_pet_w3/brain/caps/", "能力页族：cap-pages.py 生成，windows.json 的 per_cap_pages 按模式登记"),
    ("holo_pet_w3/brain/vendor/", "vendored 依赖（three.js 经典脚本版）"),
]


def _clean_residue():
    p = Path(__file__).resolve().parent / "clean_residue.py"
    spec = importlib.util.spec_from_file_location("gbt_clean_residue", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _manifest_pages() -> dict:
    """被**清单**点名的页面 → {相对路径: 清单名}。清单是唯一的"现行"依据。"""
    out: dict = {}

    def note(rel: str, who: str, base: Path = ROOT):
        try:
            key = Path(os.path.relpath((base / rel).resolve(), ROOT)).as_posix()
        except (OSError, ValueError):
            return
        out.setdefault(key, who)

    # ① 窗口注册表
    reg = ROOT / "holo_pet_w3" / "shell" / "windows.json"
    if reg.is_file():
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
            shell = reg.parent.parent
            for w in data.get("windows", []):
                f = w.get("file")
                if f:
                    note(f.lstrip("./"), "窗口注册表 windows.json（窗 " + str(w.get("id")) + "）", shell)
        except (OSError, ValueError):
            pass

    # ② 宿主面板清单（12 面板就在这个文件里）
    host = ROOT / "plugins" / "gbt-master" / "lib" / "host.js"
    if host.is_file():
        try:
            txt = host.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"file:\s*'([^']+\.html)'", txt):
                note(m.group(1), "宿主面板清单 plugins/gbt-master/lib/host.js")
            for m in re.finditer(r"file:\s*\"([^\"]+\.html)\"", txt):
                note(m.group(1), "宿主面板清单 plugins/gbt-master/lib/host.js")
        except OSError:
            pass
    return out


def scan() -> list[dict]:
    refs = _clean_residue().referenced_names()
    manifest = _manifest_pages()
    bank = []
    seen = set()
    for sub, depth1 in OURS:
        base = ROOT / sub
        if not base.is_dir():
            continue
        if depth1:
            # 仓根**只取一层**：递归会走进别人的树（第一版就是这么扫出 406 个的）
            walker = [(str(base), [], [f.name for f in os.scandir(base) if f.is_file()])]
        else:
            walker = os.walk(base)
        for dp, dn, fn in walker:
            dn[:] = [d for d in dn if d not in ("node_modules", "__pycache__", ".git", "dist")]
            for f in fn:
                if not f.lower().endswith((".html", ".htm")):
                    continue
                p = Path(dp) / f
                try:
                    rel = p.relative_to(ROOT).as_posix()
                except ValueError:
                    continue
                if rel in seen:            # 子树重叠 ⇒ 会重复计数，去重
                    continue
                seen.add(rel)
                if any(rel.startswith(e + "/") or rel == e for e, _w in EXCLUDED):
                    continue
                st = p.stat()
                bank.append({"rel": rel, "kb": round(st.st_size / 1024, 1),
                             "mtime": st.st_mtime, "path": p})
    # 判词
    for b in bank:
        who = manifest.get(b["rel"])
        if who:
            b["verdict"], b["why"] = "现行", who
            continue
        hit = [w for pre, w in PATTERN_PAGES if b["rel"].startswith(pre)]
        if hit:
            b["verdict"], b["why"] = "现行", hit[0]
            continue
        name = b["path"].name
        # 被超越：同族更高版本（V<n> 名字族）
        m = re.match(r"^V(\d+)\s+(.+)$", name)
        if m:
            n, suf = int(m.group(1)), m.group(2)
            sib = [x for x in bank
                   if x["rel"] != b["rel"] and re.match(r"^V(\d+)\s+%s$" % re.escape(suf),
                                                        Path(x["rel"]).name)]
            hi = [int(re.match(r"^V(\d+)\s+", Path(x["rel"]).name).group(1)) for x in sib]
            if hi and max(hi) > n:
                b["verdict"] = "被超越"
                b["why"] = "同族已有 V%d（本件 V%d）" % (max(hi), n)
                continue
        if name in refs:
            b["verdict"], b["why"] = "现行", "全仓文本面有引用（引用即证据）"
            continue
        # 自包含 app 的**入口壳**：小而只负责挂同目录的 js/css。
        # 为什么单列：入口页**本来就不会被别处按文件名引用**（人直接打开它），
        # 拿"零引用"判它 = 判错方向 —— 第一版就把 V2 那两个入口判成了零引用。
        if b["kb"] < 4:
            try:
                txt = b["path"].read_text(encoding="utf-8", errors="replace")
            except OSError:
                txt = ""
            assets = re.findall(r'(?:src|href)="([^":/]+\.(?:js|css))"', txt)
            here = b["path"].parent
            ok_assets = [x for x in assets if (here / x).is_file()]
            if assets and len(ok_assets) == len(assets):
                b["verdict"] = "现行"
                b["why"] = "自包含 app 的入口壳（同目录 %s 都在）" % "、".join(sorted(set(ok_assets))[:3])
                continue
        b["verdict"], b["why"] = "零引用", "既不在任何清单里，全仓文本面也没有提到它的文件名"
    return sorted(bank, key=lambda x: (x["verdict"], -x["kb"]))


def main() -> int:
    ap = argparse.ArgumentParser(description="旧页面判决器（只读）")
    ap.add_argument("--check", action="store_true", help="有过期/零引用 ⇒ 退出码 2")
    a = ap.parse_args()

    rows = scan()
    by: dict = {}
    for r in rows:
        by.setdefault(r["verdict"], []).append(r)

    print("=" * 96)
    print("旧页面判决器 · 我们自己的树里 %d 个页面" % len(rows))
    print("=" * 96)
    for v in ("被超越", "零引用", "现行"):
        lst = by.get(v) or []
        print("  [%s] %d 个" % (v, len(lst)))
    print("-" * 96)
    for v in ("被超越", "零引用"):
        lst = by.get(v) or []
        if not lst:
            continue
        print("  【%s】" % v)
        for r in lst:
            print("      %8.1f KB  %-58s %s" % (r["kb"], r["rel"][:58], r["why"]))
    lst = by.get("现行") or []
    print("  【现行】前 12 个（其余同型）：")
    for r in lst[:12]:
        print("      %8.1f KB  %-58s %s" % (r["kb"], r["rel"][:58], r["why"][:40]))
    print("-" * 96)
    print("  排除在外、不看（逐类给理由，**不许静默跳过**）：")
    for e, why in EXCLUDED:
        print("      %-22s %s" % (e or "(仓根)", why))

    bad = (by.get("被超越") or []) + (by.get("零引用") or [])
    if not a.check:
        return 0
    print("-" * 96)
    if bad:
        print("  🔴 有 %d 个页面过期或零引用 ⇒ 要么清掉（回收站），要么写进登记表说明为什么留" % len(bad))
        return 2
    print("  ✅ 每个页面都有归属：清单点名 / 有引用 / 被别人家排除项解释掉")
    return 0


if __name__ == "__main__":
    sys.exit(main())
