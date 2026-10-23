# -*- coding: utf-8 -*-
"""逐页摘要：给「把关键词弱绑定改成真申报」提供**页面自己的证据**。

每页只摘 6 样（都来自页面正文/引用，不是我猜的）：
  title · 前 3 个 h2 · 内联 data-kind · 引用的数据件(script src) · 页面里出现的 gbt 能力位名 · 大小

用法： py -3.14 -X utf8 tools/codex-scripts/page-evidence.py [--json]
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
OUT = ROOT / "state" / "page-evidence.json"


def pages() -> list:
    txt = PANEL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const PAGES = \[(.*?)\n\];", txt, re.S)
    rows = []
    if not m:
        return rows
    for mm in re.finditer(r'id:\s*"([^"]+)"[^}]*?name:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', m.group(1)):
        rows.append({"id": mm.group(1), "name": mm.group(2), "rel": mm.group(3)})
    return rows


def caps() -> dict:
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except Exception:                                                 # noqa: BLE001
        return {}


def main() -> int:
    allcaps = caps()
    out = []
    for p in pages():
        f = (PANEL.parent / p["rel"]).resolve()
        row = {"页": p["id"], "名": p["name"], "落点": p["rel"], "在盘": f.is_file()}
        if not f.is_file():
            out.append(row)
            continue
        h = f.read_text(encoding="utf-8", errors="replace")
        row["字节"] = f.stat().st_size
        t = re.search(r"<title>(.*?)</title>", h, re.S)
        row["title"] = (t.group(1).strip() if t else "")[:80]
        row["h2"] = [re.sub(r"<[^>]+>", "", x).strip()[:46]
                     for x in re.findall(r"<h2[^>]*>(.*?)</h2>", h, re.S)][:3]
        row["data_kind"] = sorted(set(re.findall(r'data-kind="([^"]+)"', h)))[:6]
        row["data_files"] = sorted(set(re.findall(r'src="\./([A-Za-z0-9_.\-]+\.js)"', h)))[:4]
        # 页面正文里出现的能力位名（只算注册表里真有的）
        names = [k for k in allcaps if len(k) >= 4 and re.search(r"\b" + re.escape(k) + r"\b", h)]
        row["cap_names_in_page"] = sorted(names)[:8]
        row["关键词命中"] = [k for k in allcaps
                        if any(t2.lower() in (k + " " + str((allcaps.get(k) or {}).get("desc", ""))).lower()
                               for t2 in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", p["id"] + " " + p["name"])
                               if len(t2) >= 2)][:8]
        out.append(row)

    res = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "页数": len(out), "逐页": out}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已落盘 %s（%d 页）" % (OUT.relative_to(ROOT), len(out)))
    for r in out:
        if not r.get("在盘"):
            print("  %-18s 落点不在盘" % r["页"])
            continue
        print("  %-18s %s" % (r["页"], r.get("title", "")[:56]))
        print("       h2=%s" % (r.get("h2") or []))
        print("       kinds=%s data=%s capsInPage=%s"
              % (r.get("data_kind"), r.get("data_files"), r.get("cap_names_in_page")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
