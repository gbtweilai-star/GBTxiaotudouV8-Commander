# -*- coding: utf-8 -*-
"""paper_loop -- 双账本公开纪事环（保密版）。"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PUB = ROOT / "memory" / "papers_public"
PRIV = ROOT / "gbt_allinone" / "store" / "papers_private.jsonl"
SIG = "—— 小土豆 V8 今日手记"
sys.path.insert(0, str(ROOT / "tools" / "codex-scripts"))
from paper_guard import is_public_safe  # noqa: E402

TPL = """# 今日手记 · {date}

今天主人让我做一件 {what} 的事。

**卡在哪了？**
{stuck}

**怎么想到的？**
{idea}

**怎么解决的？**
{fix}

**今天学到什么？**
{learn}

**离人类近了哪？**
{human}

{sig}
"""


def main():
    ap = argparse.ArgumentParser(description="双账本公开纪事环（保密版）")
    ap.add_argument("cmd", choices=("write", "list", "check", "guard"))
    ap.add_argument("--date", default="")
    ap.add_argument("--draft", default="")
    ap.add_argument("--file", default="")
    a = ap.parse_args()
    d = a.date or time.strftime("%Y-%m-%d")
    if a.cmd == "guard":
        txt = Path(a.file).read_text(encoding="utf-8") if a.file else a.draft
        safe, tripped, hits, emo = is_public_safe(txt)
        print("safe=%s 触发=%d 白名单=%d 情绪=%d %s" % (safe, len(tripped), len(hits), len(emo), [x[1] for x in emo][:4]))
        for t in tripped[:6]:
            print("   拦截: " + t)
        return 0 if safe else 1
    if a.cmd == "check":
        bad = 0
        for f in sorted(PUB.glob("*.md")):
            safe, tripped, _, _emo = is_public_safe(f.read_text(encoding="utf-8"))
            if not safe:
                bad += 1
                print("   泄露: " + f.name + " 触发 " + str(len(tripped)) + " 条 " + str(tripped[:2]))
        print("公账扫描: 文件 %d · 违规 %d" % (len(list(PUB.glob("*.md"))), bad))
        return 0 if bad == 0 else 1
    if a.cmd == "list":
        for f in sorted(PUB.glob("*.md")):
            print("  " + f.name + "  " + str(f.stat().st_size) + "B")
        return 0
    # write：先过滤器，再写公账；私账全量留痕
    draft = Path(a.file).read_text(encoding="utf-8") if a.file else a.draft
    safe, tripped, hits, emo = is_public_safe(draft)
    PRIV.parent.mkdir(parents=True, exist_ok=True)
    with PRIV.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "date": d, "safe": safe,
                             "tripped": tripped, "allowed_hits": len(hits), "draft": draft}, ensure_ascii=False) + chr(10))
    if not safe:
        print("打回重写：触发 " + str(len(tripped)) + " 条 · 白名单命中 " + str(len(hits)) + "/4")
        for t in tripped[:6]:
            print("   拦截: " + t)
        return 1
    PUB.mkdir(parents=True, exist_ok=True)
    doc = draft if draft.strip().startswith("#") else (
        "# 今日手记 · " + d + chr(10) + chr(10) + draft.strip() + chr(10) + chr(10) + SIG + chr(10))
    (PUB / (d + ".md")).write_text(doc, encoding="utf-8")
    print("公账已落：" + str((PUB / (d + ".md")).relative_to(ROOT)) + " · 白名单命中 " + str(len(hits)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
