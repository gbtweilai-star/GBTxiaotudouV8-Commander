# -*- coding: utf-8 -*-
"""逐页量「触手互通 / 秒级感知」到底连没连（这是回答"每一页都互通了吗"的唯一依据）。

口径（每条都从页面代码里读，不是我说的）：
  · 桥在不在：页面有没有用 `window.gbtW3`（壳的 preload 暴露，**不受 CSP 管**）
  · 订阅没订阅：有没有 `onEvent(` / `onStreamState(` / `onIntercom(` —— 有订阅才叫"秒级感知"
  · 静态快照：有没有同源数据件（.js 里内联快照）—— 有但没订阅 = **只到"几秒到几分钟级"，不是秒级**
  · CSP：connect-src 是什么（'none' ⇒ 页面不能 fetch，只能走桥或同源脚本）
用法：
  py -3.14 -X utf8 tools/codex-scripts/page-live-wiring.py            # 报读数（有页未订阅 exit 1）
  py -3.14 -X utf8 tools/codex-scripts/page-live-wiring.py --json
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "holo_pet_w3" / "panel" / "index.html"
OUT = ROOT / "state" / "page-live-wiring.json"

SUBS = ("onEvent(", "onStreamState(", "onIntercom(", "onPanelGoto(")


def pages() -> list:
    txt = PANEL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const PAGES = \[(.*?)\n\];", txt, re.S)
    rows = []
    if not m:
        return rows
    for mm in re.finditer(r'id:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', m.group(1)):
        rows.append({"id": mm.group(1), "rel": mm.group(2)})
    return rows


def analyse(f: pathlib.Path) -> dict:
    h = f.read_text(encoding="utf-8", errors="replace")
    csp = ""
    mc = re.search(r'content="([^"]*Content-Security-Policy[^"]*)"', h, re.I) or \
        re.search(r'Content-Security-Policy"\s*\n?\s*content="([^"]*)"', h, re.I)
    if mc:
        csp = mc.group(1)
    conn = ""
    cm = re.search(r"connect-src\s+([^;\"]+)", csp, re.I)
    if cm:
        conn = cm.group(1).strip()
    bridge = "window.gbtW3" in h or "gbtW3." in h
    subs = [s for s in SUBS if s in h]
    live_badge = "live-badge.js" in h
    snap = sorted(set(re.findall(r'src="\./?\.?/?([A-Za-z0-9_.\-]+-data\.js)"', h)))
    fetchy = bool(re.search(r"\bfetch\(", h))
    if subs or live_badge:
        cls = "LIVE"          # 订阅了状态事件 ⇒ 秒级
    elif bridge:
        cls = "BRIDGE"        # 桥在，但没订阅
    elif conn.lower() == "'none'" or "none" == conn.lower():
        cls = "OFFLINE"       # 既不能 fetch 也没订阅
    elif fetchy:
        cls = "PULL"          # 自己拉数据（不是推送，延迟看轮询）
    else:
        cls = "STATIC"        # 纯静态快照
    return {"桥": bridge, "订阅": subs, "live-badge": live_badge, "快照件": snap,
            "CSP-connect-src": conn, "fetch": fetchy, "类别": cls}


def build() -> dict:
    rows = []
    for p in pages():
        f = (PANEL.parent / p["rel"]).resolve()
        rec = {"页": p["id"], "落点": p["rel"], "在盘": f.is_file()}
        rec.update(analyse(f) if f.is_file() else {"类别": "缺件"})
        rows.append(rec)
    cnt = {}
    for r in rows:
        cnt[r["类别"]] = cnt.get(r["类别"], 0) + 1
    res = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "页数": len(rows),
           "分类计数": cnt, "逐页": rows,
           "口径": "LIVE=订阅了状态事件（秒级）· BRIDGE=有桥没订阅 · PULL=自己 fetch（看轮询）· "
                   "STATIC=纯静态快照 · OFFLINE=CSP 禁网且无订阅"}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> int:
    r = build()
    print("触手互通/秒级感知：%d 页 · %s" % (r["页数"], r["分类计数"]))
    bad = [x for x in r["逐页"] if x["类别"] != "LIVE"]
    for x in bad:
        print("  %-16s %-8s 桥=%-5s 订阅=%-12s CSP=%-6s 快照=%s"
              % (x["页"], x["类别"], x.get("桥"), ",".join(x.get("订阅") or []) or "—",
                 (x.get("CSP-connect-src") or "—")[:8], ",".join(x.get("快照件") or []) or "—"))
    print("\n判据：%s（LIVE=%d/%d）" % ("PASS" if not bad else "FAIL", r["分类计数"].get("LIVE", 0), r["页数"]))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
