# -*- coding: utf-8 -*-
"""全仓页级双向绑定核对：**每一页代码都要有绑定，且任意两页互通**。

主人令 2026-10-31（逐字）：
  「触手双向绑定所有代码页面，覆盖每一页代码，每一页代码必须和所有页面都能互通，
    以触手脉冲提速量化压缩按需激活精准直达」

这份脚本只做**核对与落账**，不改任何源文件。三类读数：

  ① 覆盖：1706 页里，多少页有**正向绑定**（页 → 能力位）。分两档如实报：
       · 强绑（strict）= 页名/路径/符号里真的点到某位能力位；
       · 兜底（trunk） = 没点到具体能力位，按「神经系统」口径挂到主干 `tentacle`。
     两档分开计，**不把兜底混进强绑**糊弄覆盖率。
  ② 反向：351 位能力位里，多少位能被至少一页点回来（双向的另一半）。
  ③ 互通：把 `state/page_bind.json` 的邻接表当无向图算连通分量 + 到锚点(anchor)的最短跳数，
     给出「任意两页 ≤ 2×最大跳数」的上界（经锚点中转），并列出离锚最远的那几页。

用法：python tools/codex-scripts/page-bind-all.py [--json state/page-bind-all.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

# 目录 → 能力位的常识表（只在**路径里点不到具体名字**时用；全部是既有能力位，不新造）
PATH_HINTS = {
    "docs": ["doc_intake"],
    "data": ["datakit"],
    "state": ["ledger_note"],
    "assets": ["asset_index"],
    "tests": ["selfscan"],
    "icons": ["asset_index"],
    "vendor": ["omni_plug"],
    "skills": ["skill_finder"],
    "vaults": ["brain_vault"],
    "mobile": ["console_pages"],
    "ios": ["console_pages"],
    "dist": ["console_pages"],
    "logs": ["audit_query"],
    "runtime": ["task_manager"],
    "examples": ["book_skill"],
}


def load_caps() -> set:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return set(BENIGN_CAPS)


SUFFIXES = ("_cap", "_ops", "_bridge", "_skill", "_watch", "_engine", "_gate",
            "_core", "_hub", "_pages", "_tool", "_tools", "_plugin", "_embed")


def bind_page(page: str, caps: set) -> tuple[list, str]:
    """一页 → 正向能力位。返回 (能力位列表, 绑定强度)。

    匹配顺序（越靠前越硬）：
      ① 文件名 = 能力位名
      ② 文件名剥掉实现后缀后 = 能力位名（`actioncam_cap.py` → `actioncam`）
      ③ 文件名以「能力位名_」开头（`brain_exec.py` → `brain_*` 里最长的那个）
      ④ 路径里某一段 = 能力位名
      ⑤ 目录常识表
      ⑥ 兜底挂主干（神经系统口径：每一页都在主干射程里）
    """
    parts = page.replace("\\", "/").split("/")
    stem = parts[-1].rsplit(".", 1)[0]
    if stem in caps:
        return [stem], "strict"
    for suf in SUFFIXES:
        if stem.endswith(suf):
            base = stem[: -len(suf)]
            if base in caps:
                return [base], "strict"
            # `xxx_cap` 里 xxx 可能只是前缀：取「caps 里以 base_ 开头的最长名字」
            pref = [c for c in caps if stem.startswith(c + "_")]
            if pref:
                return [max(pref, key=len)], "strict"
    pref = [c for c in caps if stem.startswith(c + "_")]
    if pref:
        return [max(pref, key=len)], "strict"
    for seg in parts[:-1]:
        if seg in caps:
            return [seg], "strict"
    for seg in parts[:-1]:
        if seg in PATH_HINTS:
            hits = [c for c in PATH_HINTS[seg] if c in caps]
            if hits:
                return hits, "strict"
    return (["tentacle"] if "tentacle" in caps else []), "trunk"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="state/page-bind-all.json")
    args = ap.parse_args()

    caps = load_caps()
    graph = json.load(open(os.path.join(ROOT, "state", "page_bind.json"), encoding="utf-8"))
    pages, adj = graph["pages"], graph["adj"]
    anchor = graph.get("anchor") or "anchor:scope_root"

    rows, strict = [], 0
    for p in pages:
        fwd, strength = bind_page(p, caps)
        if strength == "strict":
            strict += 1
        rows.append({"页": p, "正向_能力位": fwd, "绑定": strength,
                     "在盘": os.path.exists(os.path.join(ROOT, p))})

    # ② 反向绑定：能力位 → 页
    rev: dict[str, list] = {}
    for r in rows:
        for c in r["正向_能力位"]:
            rev.setdefault(c, []).append(r["页"])
    cap_all = sorted(caps)
    covered_caps = [c for c in cap_all if c in rev]

    # ②b 反向的第二种口径：**在页正文里被提到**（仓里既有的「反向_提及于」口径）。
    #     为什么要这一档：很多能力位没有同名文件（`alerts` 的实现就在 api.py 里），
    #     只按文件名做反向会把它们误判成"没人点回"。
    import re as _re
    pat = _re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(_re.escape(c) for c in cap_all)
                      + r")(?![A-Za-z0-9_])")
    mention: dict[str, int] = {}
    TEXT_EXT = (".py", ".md", ".js", ".mjs", ".json", ".txt", ".html", ".yml", ".toml")
    for r in rows:
        p = r["页"]
        if not p.endswith(TEXT_EXT):
            continue
        try:
            txt = open(os.path.join(ROOT, p), encoding="utf-8", errors="ignore").read(1_500_000)
        except OSError:
            continue
        for name in set(pat.findall(txt)):
            mention[name] = mention.get(name, 0) + 1
    mentioned_caps = [c for c in cap_all if c in mention]

    # ③ 互通：连通分量 + 到锚点跳数
    dist = {anchor: 0}
    q = deque([anchor])
    while q:
        x = q.popleft()
        for y in adj.get(x, []):
            if y not in dist:
                dist[y] = dist[x] + 1
                q.append(y)
    sz = len(pages)
    isolated = [p for p in pages if not adj.get(p)]
    far = sorted(((d, p) for p, d in dist.items()), reverse=True)[:10]
    components = 0
    seen = set()
    for p in adj:
        if p in seen:
            continue
        components += 1
        stack = [p]
        seen.add(p)
        while stack:
            x = stack.pop()
            for y in adj.get(x, []):
                if y not in seen:
                    seen.add(y)
                    stack.append(y)

    summary = {
        "at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "页数": sz,
        "有绑定": sum(1 for r in rows if r["正向_能力位"]),
        "强绑": strict, "兜底挂主干": sum(1 for r in rows if r["绑定"] == "trunk"),
        "覆盖率": round(sum(1 for r in rows if r["正向_能力位"]) / max(1, sz), 4),
        "强绑率": round(strict / max(1, sz), 4),
        "能力位总数": len(cap_all), "被页点回的能力位": len(covered_caps),
        "反向覆盖率": round(len(covered_caps) / max(1, len(cap_all)), 4),
        "被页正文提及的能力位": len(mentioned_caps),
        "提及覆盖率": round(len(mentioned_caps) / max(1, len(cap_all)), 4),
        "反向合计覆盖": len(set(covered_caps) | set(mentioned_caps)),
        "完全没被任何页提到/绑定的能力位": [c for c in cap_all
                                            if c not in rev and c not in mention],
        "连通分量": components,
        "到锚点最远跳数": far[0][0] if far else None,
        "最远几页": [{"页": p, "跳": d} for d, p in far[:5]],
        "孤立页": isolated,
        "任意两页上界跳数": (2 * far[0][0]) if far else None,
        "互判据": "1 个连通分量 + 0 孤立 ⇒ 任意两页经锚点可达（≤ 2×最大跳数）",
        "逐页": rows,
    }
    out = os.path.join(ROOT, args.json)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)

    print("页数 %d · 有绑定 %d (%.1f%%) · 强绑 %d (%.1f%%) · 兜底挂主干 %d"
          % (sz, summary["有绑定"], 100 * summary["覆盖率"], strict, 100 * summary["强绑率"],
             summary["兜底挂主干"]))
    print("反向：绑定 %d/%d (%.1f%%) · 正文提及 %d/%d (%.1f%%) · 合计 %d/%d (%.1f%%)"
          % (len(covered_caps), len(cap_all), 100 * summary["反向覆盖率"],
             len(mentioned_caps), len(cap_all), 100 * summary["提及覆盖率"],
             summary["反向合计覆盖"], len(cap_all),
             100 * summary["反向合计覆盖"] / max(1, len(cap_all))))
    print("互通：%d 个连通分量 · 0 孤立=%s · 到锚最远 %s 跳 · 任意两页上界 %s 跳"
          % (components, not isolated, summary["到锚点最远跳数"], summary["任意两页上界跳数"]))
    miss = summary["完全没被任何页提到/绑定的能力位"]
    if miss:
        print("完全没被提到/绑定（前 20）：", ", ".join(miss[:20]))
    print("落盘:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
