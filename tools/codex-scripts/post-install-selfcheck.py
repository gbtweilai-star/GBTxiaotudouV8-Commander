# -*- coding: utf-8 -*-
"""post-install-selfcheck -- **装完就跑一遍**的装机自检（主人 2026-10-17 令）。

主人原话：「安装上我们的大模型就自动自检一遍排除病毒木马等」。

做什么（全部走唯一门；只读，不杀不删）：
  ① `install_selfcheck op=scan`：扫安装目录/模型目录/手机包 —— 危险命令行特征、双扩展名、
     脚本型可执行、隐藏可执行；
  ② `install_selfcheck op=persistence`：自启键/计划任务/监听端口（Win）或自启目录（POSIX）；
  ③ 出报告 `state/defense/install-selfcheck.json`（含 verdict、证据、时间、平台），
     并在 stdout 摘要；`--fail-on-high` 时有高危可疑项退出码 1（给安装器用）。

用法：
  py -3.14 tools/codex-scripts/post-install-selfcheck.py                       # 默认扫仓内关键目录
  py -3.14 tools/codex-scripts/post-install-selfcheck.py --paths state/mobile-pack state/weights
  py -3.14 tools/codex-scripts/post-install-selfcheck.py --fail-on-high
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
OUT = ROOT / "state" / "defense"
DEFAULT_PATHS = ["gbt_allinone", "tools", "state/mobile-pack", "state/weights", "holo_pet_w3"]


def cap(payload: dict, timeout: int = 600) -> dict:
    p = subprocess.run([sys.executable, "-X", "utf8", str(GATE), "cap", "install_selfcheck",
                        json.dumps(payload, ensure_ascii=False), "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, cwd=str(ROOT))
    t = (p.stdout or "") + (p.stderr or "")
    i = t.find("{")
    try:
        return json.loads(t[i:])
    except Exception:                                            # noqa: BLE001
        return {"status": "error", "raw": t[:300]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="装机自检：查病毒木马/后门（只读，走唯一门）")
    ap.add_argument("--paths", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=3000)
    ap.add_argument("--fail-on-high", action="store_true")
    a = ap.parse_args(argv)
    paths = a.paths or DEFAULT_PATHS
    t0 = time.time()
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "paths": paths, "steps": {}}
    sc = cap({"op": "scan", "paths": paths, "limit": a.limit})
    sr = sc.get("result") or {}
    out["steps"]["scan"] = {k: sr.get(k) for k in
                            ("ok", "platform", "scanned_files", "high", "total", "truncated", "verdict")}
    out["steps"]["scan"]["findings_top"] = (sr.get("findings") or [])[:25]
    ps = cap({"op": "persistence"}, timeout=300)
    pr = ps.get("result") or {}
    out["steps"]["persistence"] = {k: pr.get(k) for k in
                                   ("ok", "platform", "listening_count", "items")}
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    out["verdict"] = ("发现高危可疑项，需人工复核" if (sr.get("high") or 0) > 0 else "未发现高危特征")
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "install-selfcheck.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("== 装机自检 ==")
    print(" 平台:", out["steps"]["scan"].get("platform") or out["steps"]["persistence"].get("platform"))
    print(" 扫描:", out["steps"]["scan"].get("scanned_files"), "文件 · 高危", out["steps"]["scan"].get("high"),
          "· 可疑总数", out["steps"]["scan"].get("total"), "·", out["verdict"])
    if out["steps"]["scan"].get("findings_top"):
        for f in out["steps"]["scan"]["findings_top"][:8]:
            print("  - [%s] %s :: %s" % (f.get("severity"), f.get("kind"), f.get("path")))
    print(" 持久化/端口:", out["steps"]["persistence"].get("platform"),
          "· 监听", out["steps"]["persistence"].get("listening_count"))
    print(" 报告:", p.relative_to(ROOT), "· 耗时", out["elapsed_ms"], "ms")
    print(" 说明：只读扫描；命中≠定罪，处置请人工确认（不擅自杀/删）")
    if a.fail_on_high and (sr.get("high") or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
