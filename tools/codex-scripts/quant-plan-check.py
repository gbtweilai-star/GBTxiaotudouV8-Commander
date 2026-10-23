#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""压缩方案判据（quant-plan-check）—— 把“8GB 跑 27B”变成**能算能咬**的判据

主人令 2026-10-16：提炼**压缩体积**与**执行层**（蒸馏自 Bonsai 2 27B）。

判据（对 tools/train/recipe_v26.json）：
  C1 每个量化目标必须声明 bits_per_weight + container；
  C2 **算术自洽**：估算体积 = 参数 × b/w / 8 × 开销系数（默认 1.3，分组 scale/bias）；
     若估算 > 8.6 GB 却声称“8GB 可跑” ⇒ **红**；
  C3 验收里必须有**实测体积/显存**要求（不许只报字面）；
  C4 不许拿托管模型冲当我们的权重（c03 无限制通道铁律）。
负对照：把 b/w 改成 16（FP16）⇒ C2 必红；把实测要求删掉 ⇒ C3 必红。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

RECIPE = WS / "tools" / "train" / "recipe_v26.json"
PARAMS = 27e9               # Qwen3.8-27B 级
OVERHEAD = 1.3              # 分组 scale/bias 与容器头开销
FIT_GB = 8.6                # “能在 8GB 级设备上跑”的口径（含视觉塔 0.92GB）


def estimate(bits: float, params: float = PARAMS, overhead: float = OVERHEAD) -> float:
    return params * float(bits) / 8.0 / 1024.0 ** 3 * overhead


def audit(recipe: dict) -> dict:
    bad, rows = [], []
    q = recipe.get("quantize") or {}
    tg = q.get("targets") or []
    if not tg:
        bad.append({"c": "C1", "why": "没声明任何量化目标"})
    for t in tg:
        name = t.get("name")
        b = t.get("bits_per_weight")
        c = t.get("container")
        if not name or b in (None, "") or not c:
            bad.append({"c": "C1", "why": "%s 缺 name/bits_per_weight/container" % name})
            continue
        est = estimate(b)
        rows.append({"name": name, "bits": b, "container": c, "est_gb": round(est, 2)})
        if est > FIT_GB and "8GB" in str(t.get("role") or ""):
            bad.append({"c": "C2", "why": "%s 估算 %.2f GB > %.1f GB 却声称 8GB 可跑" % (name, est, FIT_GB)})
        if float(b) >= 16.0:
            bad.append({"c": "C2", "why": "%s 声称三值却给了 %.1f b/w（FP16）" % (name, b)})
    acc = json.dumps(q.get("acceptance") or {}, ensure_ascii=False)
    if "实测" not in acc:
        bad.append({"c": "C3", "why": "验收里没有“实测体积/显存”要求"})
    blob = json.dumps(recipe, ensure_ascii=False)
    for banned in ("Workers AI", "gpt-oss", "@cf/"):
        if banned in blob:
            bad.append({"c": "C4", "why": "出现托管模型字样：%s（不许冲当我们的权重）" % banned})
    # C5（2026-10-16 加，主人令「本地不要任何大模型」）：**模型只在云插件层**。
    #   咬的是"承载面"（backends / endpoint / url）里的本机字样；**不咬禁令文字本身**
    #   （所以先剥掉否定语境：不落本机 / 不许 / 不承载 / 127.0.0.1 的禁令说明只在注释里）。
    ex = recipe.get("execution_layer") or {}
    ngt = ("不落本机", "不许", "不承载", "不要任何大模型", "不跑模型")
    for b in (ex.get("backends") or []):
        s = str(b)
        if any(n in s for n in ngt):
            continue
        if any(k in s for k in ("127.0.0.1", "localhost", "本机", "llama.cpp")):
            bad.append({"c": "C5", "why": "承载面出现本机/回环：%s（模型只能部署在云插件层）" % s[:60]})
    return {"ok": not bad, "kind": "quant_plan", "recipe": str(RECIPE), "params": PARAMS,
            "overhead": OVERHEAD, "fit_gb": FIT_GB, "targets": rows, "violations": bad,
            "note": "只算不报字面；真体积/显存必须在机上实测"}


def selftest() -> dict:
    real = json.loads(RECIPE.read_text(encoding="utf-8")) if RECIPE.is_file() else {}
    outs = {"正例绿": audit(real)["ok"]}
    fp16 = json.loads(json.dumps(real))
    for t in (fp16.get("quantize", {}).get("targets") or []):
        t["bits_per_weight"] = 16.0
    outs["FP16被咬"] = not audit(fp16)["ok"]
    noacc = json.loads(json.dumps(real))
    noacc.setdefault("quantize", {})["acceptance"] = {"x": 1}
    outs["无实测要求被咬"] = not audit(noacc)["ok"]
    local = json.loads(json.dumps(real))
    local.setdefault("execution_layer", {})["backends"] = ["llama.cpp/GGUF（本机）"]
    outs["本机承载被咬"] = not audit(local)["ok"]
    return {"ok": all(outs.values()), "kind": "quant_plan_selftest", **outs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="压缩方案判据（recipe_v26）")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        r = selftest()
    else:
        if not RECIPE.is_file():
            print("✖ 读不到:", RECIPE)
            return 2
        r = audit(json.loads(RECIPE.read_text(encoding="utf-8")))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("压缩方案：%s" % ("PASS" if r["ok"] else "FAIL"))
        for t in (r.get("targets") or []):
            print("  %-14s %s b/w · %-6s ⇒ 估 %s GB" % (t["name"], t["bits"], t["container"], t["est_gb"]))
        for v in (r.get("violations") or []):
            print("  ✖ %s %s" % (v["c"], v["why"]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
