# -*- coding: utf-8 -*-
"""文档能力位计数守卫（doc_counts）：**一个真源，所有"现读数"必须跟它一致**。

主人 2026-11-01 发火：「怎么能力位你是搞不清还是什么？341 的 348 的 375 的我也是醉了」
根因（如实）：能力位一直在加（341 → 348 → … → 385），但 README/docs 里的数字是**手写快照**，
没有"改代码就改文档"的硬约束 ⇒ 同一仓里同时躺着好几个"当前数"。

本模块只做一件事：**把"当前数"的写法同步成注册表现读**。
  · 真源：`caps_registry.BENIGN_CAPS`；
  · 历史口径不动（含 快照 / 当时 / 评估基准 / 2026-10-21 / 第 N 位 的行跳过）；
  · 子集数（只读位 / 写口位 / 改状态出网）按 `safe` 字段**重新算**，不是套总数；
  · `docs/03` 的逐域表格（位数 / 只读 / 需授权）也按现注册表重算。
"""
from __future__ import annotations

import collections
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]

TARGETS = [
    "README.md",
    "docs/01-model-card.md",
    "docs/02-architecture.md",
    "docs/03-capabilities.md",
    "docs/11-five-dim.md",
    "docs/13-omni-plug.md",
    "docs/15-tentacle-counter.md",
    "docs/90-what-she-can-do.md",
]

HISTORY_MARKERS = ("快照", "当时", "旧", "历史", "评估", "基准", "2026-10-21", "第 3", "第 4",
                   "已过时", "曾", "原口径", "老口径", "权重发布")

# 通用"当前总数"写法（数字统一命名组 n）
TOTAL_PATTERNS = [
    re.compile(r"Capabilities-(?P<n>\d{2,4})-"),                    # shields 徽章
    re.compile(r"\*\*(?P<n>\d{2,4}) 个能力位"),                      # **385 个能力位
    re.compile(r"(?<![*\d])(?P<n>\d{2,4}) 个能力位"),               # 385 个能力位
    re.compile(r"(?P<n>\d{2,4}) 位能力"),                           # 385 位能力
    re.compile(r"# (?P<n>\d{2,4})\s*$"),                            # print(...)  # 385
    re.compile(r"\| 能力位 \| \*\*(?P<n>\d{2,4})\*\* \|"),           # 实测读数表
    re.compile(r"（(?P<n>\d{2,4}) 位）"),                            # （385 位）
    re.compile(r"30 域 · (?P<n>\d{2,4}) 位"),                       # 30 域 · 385 位
    re.compile(r"能力位 caps_registry\.py（(?P<n>\d{2,4}) 个"),      # 架构图注释
    re.compile(r"共 (?P<n>\d{2,4}) 位 / 30 个域"),                  # docs/03 标题
]

# 子集写法：只读 / 写口 / 改状态出网（按 safe 字段重算）
SUBSET_PATTERNS = [
    (re.compile(r"只读 (?P<n>\d{2,4}) 位"), "safe"),
    (re.compile(r"只读位（(?P<n>\d{2,4}) 位）"), "safe"),
    (re.compile(r"`safe=true`（(?P<n>\d{2,4}) 位）"), "safe"),
    (re.compile(r"`safe=false`（(?P<n>\d{2,4}) 位）"), "unsafe"),
    (re.compile(r"改状态/出网 (?P<n>\d{2,4}) 位"), "unsafe"),
    (re.compile(r"写口位（(?P<n>\d{2,4}) 位）"), "unsafe"),
]

# docs/03 逐域表格行
ROW_RE = re.compile(r"^\| `(?P<dom>[a-z_]+)` \| (?P<cn>[^|]+) \| (?P<total>\d+) \| (?P<safe>\d+) \| (?P<unsafe>\d+) \|")


def _caps() -> dict:
    from ..caps_registry import BENIGN_CAPS
    return BENIGN_CAPS


def current_count() -> int:
    return len(_caps())


def split_counts() -> tuple:
    caps = _caps()
    safe = sum(1 for v in caps.values() if v.get("safe", True))
    return safe, len(caps) - safe


def _is_history(line: str) -> bool:
    return any(m in line for m in HISTORY_MARKERS)


def _sub_n(line: str, pat, want: int, changed: list) -> str:
    def _f(m):
        old = int(m.group("n"))
        if old == want or 1900 <= old <= 2100:
            return m.group(0)
        changed.append(old)
        whole = m.group(0)
        a, b = m.span("n")
        a -= m.start(0)
        b -= m.start(0)
        return whole[:a] + str(want) + whole[b:]
    return pat.sub(_f, line)


def _sync_doc03_table(lines: list) -> tuple:
    """docs/03 逐域表格按现注册表重算（返回新行、改动行数）。"""
    caps = _caps()
    by_dom = collections.defaultdict(lambda: [0, 0, 0])
    for v in caps.values():
        d = v.get("domain") or "?"
        by_dom[d][0] += 1
        if v.get("safe", True):
            by_dom[d][1] += 1
        else:
            by_dom[d][2] += 1
    changed = 0
    out = []
    for line in lines:
        m = ROW_RE.match(line)
        if not m:
            out.append(line)
            continue
        d = m.group("dom")
        if d not in by_dom:
            out.append(line)
            continue
        want = [str(x) for x in by_dom[d]]
        cur = [m.group("total"), m.group("safe"), m.group("unsafe")]
        if cur == want:
            out.append(line)
            continue
        changed += 1
        new = line
        for w, c in zip(want, cur):
            if w != c:
                new = new.replace("| %s |" % c, "| %s |" % w, 1)
        out.append(new)
    return out, changed


def check(apply: bool = False) -> dict:
    total = current_count()
    safe, unsafe = split_counts()
    stale, fixed_files = [], []

    for rel in TARGETS:
        p = ROOT / rel
        if not p.is_file():
            continue
        lines = p.read_text(encoding="utf-8").split("\n")
        out, changed = [], 0
        for i, line in enumerate(lines):
            if _is_history(line):
                out.append(line)
                continue
            olds = []
            new = line
            subset_hit = False
            for pat, kind in SUBSET_PATTERNS:
                want = safe if kind == "safe" else unsafe
                m = pat.search(new)
                if m:
                    subset_hit = True          # 只要这一行是子集写法，就不让"总数"再改写它
                    if int(m.group("n")) != want:
                        olds.append(int(m.group("n")))
                new = _sub_n(new, pat, want, [])
            if not subset_hit:          # 子集行不再被"总数"二次改写
                for pat in TOTAL_PATTERNS:
                    new = _sub_n(new, pat, total, olds)
            if olds:
                stale.append({"file": rel, "line": i + 1, "old": sorted(set(olds)),
                              "text": line.strip()[:90]})
                changed += 1
            out.append(new)
        if rel == "docs/03-capabilities.md":
            out, tch = _sync_doc03_table(out)
            if tch:
                stale.append({"file": rel, "line": 0, "old": ["逐域表格"],
                              "text": "docs/03 逐域表 %d 行位数/只读/需授权重算" % tch})
                changed += 1
        if changed:
            fixed_files.append(rel)
            if apply:
                p.write_text("\n".join(out), encoding="utf-8")

    return {"ok": True, "current": total, "safe": safe, "unsafe": unsafe,
            "stale": stale, "count": len(stale),
            "files": sorted({s["file"] for s in stale}),
            "applied": bool(apply), "changed_files": fixed_files if apply else [],
            "verdict": "clean" if not stale else "stale",
            "how_to_fix": "python tools/sync-cap-counts.py --apply"}
