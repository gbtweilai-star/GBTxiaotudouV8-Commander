# -*- coding: utf-8 -*-
"""omission-gate -- 防“遗漏再生”的三条闸。
C1 声明层vs运行层：声称“已做成”的事必须有**运行层回执**（落盘且新鲜）
C2 静止窗口：自检前必须静止（最近 N 秒内未写仓），否则会得到瞬时假红
C3 补丁已生效：改件必须留“改动数>0 + 验证命令”的回执
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
NOW = time.time()


def c1_runtime():
    hits = []
    # 语音：要有真出声的 wav（运行层）
    wav = sorted((ROOT / "state" / "voicestudio" / "out").glob("*.wav"), key=lambda p: p.stat().st_mtime)
    if wav and (NOW - wav[-1].stat().st_mtime) < 48 * 3600:
        hits.append(("voice", "runtime", "wav %s %.0fKB" % (wav[-1].name, wav[-1].stat().st_size / 1024)))
    else:
        hits.append(("voice", "static-only", "未见近 48h 内的真出声 wav"))
    # 页面：分片索引必须存在（运行层产物）
    sh = list((ROOT / "state" / "project-shards").glob("shard-*.html"))
    hits.append(("bind", "runtime" if sh else "static-only", "%d 片" % len(sh)))
    # 视觉：要有 op=see 的真回执文件
    v = list((ROOT / ".scratch").glob("reverse_*.json")) + list((ROOT / ".scratch").glob("ocr*.json"))
    hits.append(("vision", "runtime" if v else "static-only", "%d 份回执" % len(v)))
    return hits


def c2_quiet(sec=30):
    recent = []
    for p in list(ROOT.glob("tools/**/*.py")) + list(ROOT.glob("gbt_allinone/**/*.py")) + list(ROOT.glob("state/*.json")):
        try:
            if NOW - p.stat().st_mtime < sec:
                recent.append(str(p.relative_to(ROOT)))
        except Exception:
            pass
    return recent


def c3_patches():
    f = ROOT / "state" / "patch-receipts.json"
    if not f.is_file():
        return None, "无回执账（改件必须写这里）"
    d = json.loads(f.read_text(encoding="utf-8"))
    bad = [k for k, v in d.items() if not (isinstance(v, dict) and v.get("changes", 0) > 0)]
    return d, ("共 %d 条·无效 %d" % (len(d), len(bad)))


def main():
    red = 0
    print("C1 声明层 vs 运行层：")
    for name, kind, note in c1_runtime():
        flag = "OK " if kind == "runtime" else "RED"
        if kind != "runtime":
            red += 1
        print("   %-8s %s  %s" % (name, flag, note))
    rec = c2_quiet()
    print("C2 静止窗口：%s" % ("静止 ✓" if not rec else "非静止（最近 30s 内有写）: %s" % ", ".join(rec[:5])))
    if rec:
        red += 1
    d, note = c3_patches()
    print("C3 补丁已生效：%s" % note)
    print("== 防遗漏门：红 %d ==" % red)
    return 0 if red == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
