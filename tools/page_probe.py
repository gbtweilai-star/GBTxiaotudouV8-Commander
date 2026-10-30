#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page_probe —— 页面自报读数的读取端（2026-10-30）

问题：页面好不好，以前只能"打开看一眼"。这在手机上既慢又不可复核。

做法：页面带 `?_probe=1` 打开时，自己把关键读数 POST 到桥的 `/_probe`，
      桥追加 `state/page_probes.jsonl`。本器读那个账，按页聚合出：
        · 最后一次自报是什么时候（新鲜度）
        · ok / 否
        · 关键读数（tok/s、三角形、像素亮度…）

用法：
    python3 tools/page_probe.py status          # 人读
    python3 tools/page_probe.py status --json   # 机读
    python3 tools/page_probe.py status --max-age 3600   # 只认 1 小时内的
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "page_probes.jsonl"


def load() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                                        # noqa: BLE001
            pass
    return out


# ── 判决规则（2026-10-30）─────────────────────────────────────────────
# 为什么要有：账上只有数字时，人还得自己判断"这个数算好还是坏"。
# 每条规则都必须能指回一个具体读数，不猜。
TPS_MIN = {"gpu": 30.0, "js": 8.0}


def judge(readings: dict, ok_flag: bool) -> tuple:
    """→ (verdict, reason)。verdict ∈ ok / red / warn"""
    rd = readings or {}
    if not ok_flag:
        return "red", "页面自己报了 ok=false"
    # ① 3D 页：看三角形与帧
    if "tris" in rd:
        tris = rd.get("tris") or 0
        frames = rd.get("frames") or 0
        if tris <= 100:
            return "red", "模型没进画面（tris=%s ≤ 100）" % tris
        if frames == 0:
            return "red", "帧驱动没启动（frames=0，tris=%s 说明几何在提交）" % tris
        if frames < 10:
            return "warn", "帧数偏低（frames=%s）—— 疑似后台标签节流" % frames
        return "ok", "tris=%s · frames=%s · 非黑 %s%%" % (tris, frames, rd.get("nonblack"))
    # ②b 穿透证据：页面必须真的能调能力位（gbtW3.cap → /_cap → run_task）
    if "cap_ok" in rd:
        if not rd.get("cap_ok"):
            return "red", "页面调不到能力位（cap_ok=false %s）" % (rd.get("cap_err") or "")
        return "ok", "穿透 ok · %sms · python %s · %s tok/s · top-1 %r" % (
            rd.get("cap_ms"), rd.get("cap_python"), rd.get("tps"), rd.get("top1"))

    # ② 推理页：看 top-1 与速度
    if "top1" in rd or "tps" in rd:
        top1 = str(rd.get("top1") or "")
        backend = str(rd.get("backend") or "")
        tps = float(rd.get("tps") or 0)
        if "endoftext" in top1 or "<|" in top1:
            return "red", "top-1 是特殊 token（%r）—— 分布崩了" % top1
        if (rd.get("rows_bad") or 0) > 0:
            return "red", "自检有 %s 项红" % rd.get("rows_bad")
        floor = TPS_MIN.get(backend)
        if floor and tps < floor:
            return "red", "速度 %s < %s（%s 后端门槛）" % (tps, floor, backend)
        return "ok", "%s · %s tok/s · top-1 %r" % (backend, tps, top1)
    # ③ 其它页：只认 ok
    return "ok", "ok"


def aggregate(max_age: float | None = None) -> dict:
    rows = load()
    now = time.time()
    per = {}
    for r in rows:
        page = r.get("page") or "?"
        try:
            t = time.mktime(time.strptime(r.get("at", ""), "%Y-%m-%dT%H:%M:%S"))
        except Exception:                                        # noqa: BLE001
            continue
        if max_age is not None and now - t > max_age:
            continue
        cur = per.get(page)
        if cur is None or t > cur["_ts"]:
            per[page] = {"page": page, "at": r.get("at"), "ok": bool(r.get("ok")),
                         "readings": r.get("readings") or {}, "_ts": t,
                         "age_s": int(now - t)}
    items = sorted(per.values(), key=lambda x: x["_ts"], reverse=True)
    for it in items:
        it.pop("_ts", None)
        v, why = judge(it.get("readings"), it.get("ok"))
        it["verdict"], it["why"] = v, why
    ok_n = sum(1 for x in items if x["verdict"] == "ok")
    warn_n = sum(1 for x in items if x["verdict"] == "warn")
    red_n = sum(1 for x in items if x["verdict"] == "red")
    return {"pages": items, "total": len(items), "ok": ok_n, "warn": warn_n,
            "fail": red_n, "ledger": str(LEDGER)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("op", nargs="?", default="status", choices=["status", "selftest"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-age", type=float, default=None,
                    help="只认这么多秒内的自报（默认不限）")
    a = ap.parse_args(argv)

    if a.op == "selftest":
        # 铁证：证明判决规则真的会亮红灯（不是只会在绿的时候显示绿）
        cases = [
            ("3D 缺人物", {"tris": 12, "frames": 5}, True, "red"),
            ("3D 帧没起", {"tris": 20545, "frames": 0}, True, "red"),
            ("3D 节流",   {"tris": 20545, "frames": 2}, True, "warn"),
            ("3D 正常",   {"tris": 20545, "frames": 40, "nonblack": 13}, True, "ok"),
            ("推理崩",    {"backend": "gpu", "tps": 40, "top1": "<|endoftext|>"}, True, "red"),
            ("推理慢",    {"backend": "gpu", "tps": 10, "top1": " Paris"}, True, "red"),
            ("推理正常",  {"backend": "gpu", "tps": 38, "top1": " Paris"}, True, "ok"),
            ("页面自报失败", {"tris": 20545, "frames": 40}, False, "red"),
            ("穿透成功",   {"cap_ok": True, "cap_ms": 27, "cap_python": "3.12.14", "tps": 37, "top1": " Paris"}, True, "ok"),
            ("穿透失败",   {"cap_ok": False, "cap_err": "TypeError"}, True, "red"),
        ]
        bad = 0
        for name, rd, okf, want in cases:
            v, why = judge(rd, okf)
            good = (v == want)
            if not good:
                bad += 1
            print("   %s %-14s → %-5s（期望 %-5s）· %s"
                  % ("✅" if good else "🔴", name, v, want, why))
        print("  自测 %d/%d 通过" % (len(cases) - bad, len(cases)))
        if a.json:
            print(json.dumps({"ok": bad == 0, "cases": len(cases), "bad": bad}))
        return 0 if bad == 0 else 1

    res = aggregate(a.max_age)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["total"] else 2

    print("  页面自报账 · %d 页（ok %d / 警告 %d / 红 %d）"
          % (res["total"], res["ok"], res["warn"], res["fail"]))
    if not res["pages"]:
        print("  还没有任何页面自报过。让页面带 ?_probe=1 打开一次。")
        return 2
    for it in res["pages"]:
        mark = {"ok": "✅", "warn": "⚠️", "red": "🔴"}[it["verdict"]]
        print("   %s %-30s %5ds 前 · %s" % (mark, it["page"][-30:], it["age_s"], it["why"]))
    return 0 if res["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
