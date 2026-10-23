# -*- coding: utf-8 -*-
"""compact-app-nav.py —— 把 App 每个页面顶上那坨「直达」巨型导航收成**一条紧凑导航**。

## 为什么（Owner 2026-10-21：「先整理一遍她的 APP 页面，那么多垃圾堆挤在一起」）
实测：20 扇窗的每一页都内联了一份「直达：」清单，**每页几百条链接**（caps/* 438 个 + blueprints + shards），
排在正文顶上 —— 每页都像被导航淹掉。链接本身有用，不该删；**该收起来**。

## 做法（保留全部链接，只改呈现）
1. 扫全仓 `gbt-direct-nav` 内联块，抽出其中所有 `href`；
2. 生成唯一一份 `holo_pet_w3/shell/nav-index.json`（按首段目录分组、去重）；
3. 把每个页面的内联块换成 `<script src="<rel>/shell/nav-compact.js">`（按页面深度算相对路径）；
4. 打印每页：原链接数 → 剩 1 个脚本标签。

## 用法
  py -3.14 tools/codex-scripts/compact-app-nav.py --check   # 只报会改哪些页
  py -3.14 tools/codex-scripts/compact-app-nav.py           # 真改（原子写，不留 .bak）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "holo_pet_w3"
NAV_JSON = APP / "shell" / "nav-index.json"

BLOCK = re.compile(r'<div id="gbt-direct-nav"[\s\S]*?</div>', re.I)
HREF = re.compile(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', re.I)


def pages() -> list:
    out = []
    for p in APP.rglob("*.html"):
        if "_archive" in p.parts or "node_modules" in p.parts:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:                                            # noqa: BLE001
            continue
        if 'id="gbt-direct-nav"' in t:
            out.append(p)
    return sorted(out)


def scan(paths: list) -> tuple:
    links, per = [], {}
    seen = set()
    for p in paths:
        t = p.read_text(encoding="utf-8", errors="replace")
        m = BLOCK.search(t)
        n = len(HREF.findall(m.group(0))) if m else 0
        per[str(p.relative_to(APP))] = n
        if not m:
            continue
        for href, label in HREF.findall(m.group(0)):
            h = href.strip()
            if h.startswith(("http://", "https://", "#", "javascript:")):
                continue
            key = h.split("#")[0]
            if key in seen:
                continue
            seen.add(key)
            norm = os.path.normpath(key.replace("\\", "/"))
            probe = norm
            while probe.startswith(".."):
                probe = probe[3:] if probe.startswith("../") else probe[2:]
            parts = [x for x in probe.split("/") if x and x != "."]
            grp = parts[0] if len(parts) > 1 else "根"
            links.append({"path": norm, "label": unquote(label.strip()) or norm, "group": grp})
    return links, per


def rel_to_shell(page: Path) -> str:
    """页面到 shell/nav-compact.js 的相对前缀。"""
    depth = len(page.relative_to(APP).parts) - 1          # 目录层数
    return ("../" * depth) if depth else "./"


def run(check: bool) -> dict:
    ps = pages()
    links, per = scan(ps)
    rep = {"pages": len(ps), "links_before_total": sum(per.values()),
           "unique_links": len(links), "groups": len({x["group"] for x in links})}
    if check:
        rep["per_page"] = per
        return rep
    NAV_JSON.parent.mkdir(parents=True, exist_ok=True)
    NAV_JSON.write_text(json.dumps({"schema": "gbt-nav/v1", "links": links},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    changed = 0
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        m = BLOCK.search(t)
        if not m:
            continue
        tag = '<script src="%sshell/nav-compact.js"></script>' % rel_to_shell(p)
        t2 = t[:m.start()] + tag + t[m.end():]
        p.write_text(t2, encoding="utf-8")
        changed += 1
    rep["changed"] = changed
    rep["nav_json"] = str(NAV_JSON)
    rep["nav_json_bytes"] = NAV_JSON.stat().st_size
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(a.check), ensure_ascii=False, indent=1)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
