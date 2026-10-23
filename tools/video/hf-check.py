# -*- coding: utf-8 -*-
r"""S3 前置门 · 跑**声明后端自己的**六域门（hyperframes check）并绑工程哈希落盘。

主人令目标（2026-10-10 目标轮）：「① 走本仓自己的编排器 · 不手搓平行实现」
—— 视频流水线里 S3「动效」的**声明后端是 hyperframes**。
我先前在 S3 上挂的是**我自己写的** gate_video + gate_motion（能解码 + 真有画面变化）。
那两条不算错，但**它们只覆盖我看得见的两个维度**；而后端自己有一道**六域门**：
    Lint · Runtime · Layout（含接缝处瞬时重叠）· Motion · Contrast（WCAG AA）· Snapshots

⇒ 本件把那道门接进 S3：**用它的判据，不是用我的**。

## 为什么落盘 + 绑哈希（不每次现跑）
`npx hyperframes check` 要起 headless Chrome 跑一遍，约 30~60 秒 —— 塞进每次 status 会拖死。
⇒ **落盘缓存**：跑一次存判决 + **工程内容哈希**；门读缓存。
   **工程一改（index.html / scenes/*.html 变了）⇒ 哈希不符 ⇒ 缓存作废、必须重跑。**
   这与 S2（复核绑图哈希）、S12（渲染绑预设哈希）是**同一套反静默手法**。

用法：
  py -3.14 -X utf8 tools/video/hf-check.py run      # 真跑并把判决落盘
  py -3.14 -X utf8 tools/video/hf-check.py status    # 只读判决（含新鲜度）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PROJ = ROOT / "video-src" / "motion"
OUT = ROOT / "state" / "hf-check.json"
GLOBS = ("index.html", "scenes/*.html")


def project_hash() -> str:
    """工程内容哈希：把根件 + 所有子合成**按路径排序**逐个喂进 sha256。

    🔴 任一文件改名/增删都会改变哈希 —— 不留"改了子件但缓存还算新鲜"的口子。
    """
    h = hashlib.sha256()
    files = []
    for g in GLOBS:
        files.extend(sorted(PROJ.glob(g)))
    seen = set()
    for f in sorted(files):
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        h.update(str(f.relative_to(PROJ)).encode("utf-8"))
        h.update(b"\x00")
        h.update(f.read_bytes())
        h.update(b"\x00")
    return h.hexdigest(), len(seen)


def run() -> dict:
    if not PROJ.is_dir():
        return {"ok": False, "why": "没有工程目录 %s" % PROJ}
    h, n = project_hash()
    t0 = time.time()
    # --at-transitions：**在每条补间的起止边界也采样**（它自己的说法：catch transient overlaps
    #   at transition seams）。我先前那个重叠就发生在接缝处，而它默认关着 —— 这道门必须开。
    cp = subprocess.run(["npx.cmd", "--yes", "hyperframes@latest", "check", "--at-transitions"],
                        capture_output=True, cwd=str(PROJ), shell=True, timeout=900)
    out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace")
    secs = round(time.time() - t0, 1)
    # 逐域读它的判决（**读它的域，不是读它的总结**）
    doms = {}
    for d in ("Lint", "Runtime", "Layout", "Motion", "Contrast", "Snapshots"):
        m = re.search(r"^\s*%s\s*$\s*\n\s*(.+)$" % d, out, re.M)
        doms[d] = (m.group(1).strip() if m else "(没读到)").replace("◇", "").strip()
    ok = ("Check passed" in out) and all(
        ("0 error" in v or "pass" in v or "issues across" in v or "disabled" in v)
        for v in doms.values())
    rec = {"ok": bool(ok), "工程哈希": h, "文件数": n, "耗时s": secs,
           "逐域": doms, "rc": cp.returncode, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "口径": "**六域门是声明后端自己的**（hyperframes check）；本件只负责跑它、录它、绑哈希"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def status() -> dict:
    """只读判决 + **新鲜度**（工程哈希对不对得上）。"""
    if not OUT.is_file():
        return {"ok": False, "why": "没跑过（先 run）", "新鲜": False}
    rec = json.loads(OUT.read_text(encoding="utf-8"))
    now, n = project_hash() if PROJ.is_dir() else ("", 0)
    fresh = bool(rec.get("工程哈希")) and rec["工程哈希"] == now
    return {"ok": bool(rec.get("ok")) and fresh, "新鲜": fresh,
            "记录哈希": (rec.get("工程哈希") or "")[:12],
            "现在哈希": (now or "")[:12],
            "为什么": "" if fresh else "**工程改过了 ⇒ 这份判决作废，必须重跑**",
            "逐域": rec.get("逐域"), "耗时s": rec.get("耗时s"), "at": rec.get("at")}


def main() -> int:
    ap = argparse.ArgumentParser(description="S3 前置门（声明后端自己的六域门）")
    ap.add_argument("mode", nargs="?", default="status", choices=["run", "status"])
    a = ap.parse_args()
    r = run() if a.mode == "run" else status()
    print(json.dumps(r, ensure_ascii=False, indent=1)[:1800])
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
