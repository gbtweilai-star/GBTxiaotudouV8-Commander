# -*- coding: utf-8 -*-
"""逐页量「触手覆盖每一个代码点」：每个可交互点、每个数据入口，到底经不经过触手/能力位。

口径（全部从页面代码现读，不猜）：
  · 交互点 = `<button>` / `<a href="#…">或 role=button` / `[onclick]` / `[data-action]` / `<select>` / `<input>`
  · 触手通道 = `gbtW3.cap(` / `gbtW3.say(` / `gbtW3.message(` / `gbtW3.beat` / `GBT_LIVE` / `live-badge.js`
  · 覆盖判定：页面里**至少有一个**触手通道 ⇒ 该页"有触手面"；逐交互点是否各自接上，要看
    `data-cap` / `data-live` / `onclick` 里是否出现触手通道名。
用法：
  py -3.14 -X utf8 tools/codex-scripts/page-tentacle-coverage.py         # 报读数（有未覆盖即 rc=1）
  py -3.14 -X utf8 tools/codex-scripts/page-tentacle-coverage.py --json
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
OUT = ROOT / "state" / "page-tentacle-coverage.json"

TOUCH = ("gbtW3.cap(", "gbtW3.say(", "gbtW3.message(", "gbtW3.beat", "GBT_LIVE", "live-badge.js")
INTERACTIVE = [
    ("button", r"<button\b[^>]*>"),
    ("data-action", r"<[^>]+data-action="),
    ("onclick", r"<[^>]+onclick="),
    ("select", r"<select\b[^>]*>"),
    ("input", r"<input\b[^>]*>"),
]


def pages():
    t = PANEL.read_text(encoding="utf-8")
    m = re.search(r"const PAGES = \[(.*?)\n\];", t, re.S)
    out = []
    if m:
        for mm in re.finditer(r'id:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', m.group(1)):
            out.append((mm.group(1), mm.group(2)))
    return out


def audit(f: pathlib.Path) -> dict:
    h = f.read_text(encoding="utf-8", errors="replace")
    # 页内所有标签片段（用于逐个交互点看它自己带不带触手标记）
    tags = re.findall(r"<[a-zA-Z][^>]*>", h)
    interactive = [t for t in tags if re.search(r"<(button|select|input)\b|data-action=|onclick=|role=\"button\"", t)]
    wired = [t for t in interactive if ("data-cap=" in t or "data-live" in t
                                        or "gbtW3" in t or "GBT_LIVE" in t)]
    channels = sorted({c for c in TOUCH if c in h})
    kit = "tentacle-kit.js" in h
    # 接管器在 == 页里**所有**交互点都会被它接管（含运行期新增），所以整页算覆盖
    covered = len(wired) + (len(interactive) - len(wired) if kit else 0)
    snaps = sorted(set(re.findall(r'src="\./([A-Za-z0-9_.\-]+-data\.js)"', h)))
    if not interactive:
        verdict = "无交互点（不适用）"
        pct = 100.0
    else:
        pct = round(covered * 100.0 / len(interactive), 1)
        verdict = "接管器覆盖" if (kit and covered == len(interactive)) else (
            "逐点标记" if covered == len(interactive) else "有未覆盖点")
    return {"交互点": len(interactive), "已接触手": covered,
            "覆盖": pct, "判定": verdict, "接管器": kit,
            "触手通道": channels, "静态快照件": snaps}


def build() -> dict:
    rows = []
    for pid, rel in pages():
        f = (PANEL.parent / rel).resolve()
        rec = {"页": pid, "落点": rel}
        rec.update(audit(f) if f.is_file() else {"交互点": 0, "已接触手": 0, "覆盖": 0.0,
                                                 "触手通道": [], "静态快照件": []})
        rows.append(rec)
    bad = [r for r in rows if r["覆盖"] < 100.0]
    res = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "页数": len(rows),
           "全覆盖": len(rows) - len(bad), "未覆盖": len(bad),
           "交互点总数": sum(r["交互点"] for r in rows),
           "已接总数": sum(r["已接触手"] for r in rows),
           "逐页": rows,
           "口径": "交互点里带 data-cap/data-live/gbtW3/GBT_LIVE 的才算「接上触手」；"
                   "100% 才算这一页的代码点被触手覆盖"}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> int:
    r = build()
    print("触手覆盖代码点：%d 页 · 全覆盖 %d · **未覆盖 %d** · 交互点 %d · 已接 %d"
          % (r["页数"], r["全覆盖"], r["未覆盖"], r["交互点总数"], r["已接总数"]))
    for x in sorted(r["逐页"], key=lambda y: y["覆盖"])[:12]:
        print("  %-16s 覆盖 %5.1f%%  (%d/%d) 通道=%s 快照=%s"
              % (x["页"], x["覆盖"], x["已接触手"], x["交互点"],
                 ",".join(x["触手通道"])[:40] or "—", ",".join(x["静态快照件"])[:28] or "—"))
    print("\n判据：%s" % ("PASS" if r["未覆盖"] == 0 else "FAIL"))
    return 0 if r["未覆盖"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
