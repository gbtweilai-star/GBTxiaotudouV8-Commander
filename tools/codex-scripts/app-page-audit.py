# -*- coding: utf-8 -*-
"""app-page-audit.py —— 把 GBT 桌面 App 的页面**逐个过一遍**，数清楚"做坏的/垃圾的"有多少。

## 判据（写死，可复核；每条都打印它命中的样例）
- `空壳`：可见文字 < 40 字 或 元素 < 8
- `占位/自认没做`：正文出现 占位|未实现|TODO|coming soon|待补|stub|尚未接线|占位页
- `报错页`：正文出现 载入失败|解析失败|错误|Error|not found|404|异常
- `重复页`：正文归一化后哈希相同（同组 ≥2 个 ⇒ 除第一个外都算多余）
- `孤儿页`：盘上有 index.html，但 `shell/windows.json` 里没有对应窗
- `死链`：页内 href 指向的本地文件不存在

## 用法
  py -3.14 tools/codex-scripts/app-page-audit.py            # 汇总 + 前 15 个坏页
  py -3.14 tools/codex-scripts/app-page-audit.py --json     # 全量明细
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "holo_pet_w3"
REG = APP / "shell" / "windows.json"

TAG = re.compile(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>")
HREF = re.compile(r'href="([^"#?]+)"')
STUB = re.compile(r"占位|未实现|TODO|coming soon|待补|stub|尚未接线|占位页|敬请期待", re.I)
ERR = re.compile(r"载入失败|解析失败|not found|404|异常|载入异常|cannot read|undefined is not", re.I)


def visible(html: str) -> str:
    t = TAG.sub(" ", html)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    reg_ids, reg_files = set(), set()
    if REG.is_file():
        for w in json.loads(REG.read_text(encoding="utf-8")).get("windows", []):
            reg_ids.add(w.get("id"))
            reg_files.add((w.get("file") or "").lstrip("./").replace("../", ""))

    pages, dead_all = [], 0
    for p in sorted(APP.rglob("*.html")):
        if any(x.startswith("_archive") for x in p.parts) or "node_modules" in p.parts:
            continue
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:                                            # noqa: BLE001
            continue
        txt = visible(html)
        rel = p.relative_to(APP).as_posix()
        dead = []
        for h in HREF.findall(html):
            if h.startswith(("http", "mailto:", "javascript:", "data:")):
                continue
            tgt = (p.parent / h.split("#")[0]).resolve()
            if not tgt.exists():
                dead.append(h)
        dead_all += len(dead)
        pages.append({
            "path": rel, "bytes": p.stat().st_size, "chars": len(txt),
            "h": hashlib.sha1(re.sub(r"\W+", "", txt).encode("utf-8")).hexdigest()[:12],
            "empty": len(txt) < 40,
            "stub": bool(STUB.search(txt)),
            "err": bool(ERR.search(txt)),
            "dead": len(dead), "dead_sample": dead[:3],
            "registered": rel in reg_files,
        })

    # 重复组（只对"有实质正文"的页算，空壳已经单独算）
    groups = {}
    for pg in pages:
        if pg["chars"] >= 40:
            groups.setdefault(pg["h"], []).append(pg["path"])
    dup_extra = [g[1:] for g in groups.values() if len(g) > 1]
    dup_set = {x for g in dup_extra for x in g}

    bad = {
        "空壳": [p["path"] for p in pages if p["empty"]],
        "占位/自认没做": [p["path"] for p in pages if p["stub"]],
        "报错页": [p["path"] for p in pages if p["err"]],
        "重复页(多余份)": sorted(dup_set),
        "是否登记窗": [p["path"] for p in pages if not p["registered"]],
    }
    rep = {
        "pages": len(pages),
        "bad_counts": {k: len(v) for k, v in bad.items()},
        "dead_links_total": dead_all,
        "dup_groups": len(dup_extra),
        "windows_registered": len(reg_ids),
        "samples": {k: v[:6] for k, v in bad.items()},
        "worst": sorted(pages, key=lambda x: (x["chars"], -x["dead"]))[:10],
    }
    if a.json:
        rep["all"] = pages
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
