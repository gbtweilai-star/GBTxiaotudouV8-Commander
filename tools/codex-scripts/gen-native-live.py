#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成开源仓里的两份「真跑读数」——**有生产者的账**（P9：手抄的账必烂）。

产出：
  1. outputs/open-source-release/data/gbt-tianzhen-live.json   ← GBT天真（comfy_native）live 读数
  2. outputs/open-source-release/data/five-dim-live.json       ← 五维合一（brain_unify）live 回执

口径（写死，不许改口径去凑绿）：
  · 一切调用走唯一门 `gbt_allinone.api.run_task`（= 万能插同一条门），不直调模块函数；
  · 写面（op=run / 需 filesystem_write）**不跑**，如实记 denied + missing_scopes；
  · 只读面（status/contract/nodes/validate）真跑；validate 正反例各一；
  · 五维合一按人话意图真路由，路由降级/被门挡住都原样入账，不挑好看的。

用法：py -3.12 tools/codex-scripts/gen-native-live.py     （3.12 有 Pillow，comfy_native 的图算子才活得起来）
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone.api import run_task                     # noqa: E402

OUT = ROOT / "outputs" / "open-source-release" / "data"


def unwrap(resp) -> dict:
    """门回执两层嵌套：gbt_result.result（取数按单层取会得到空 dict，这里显式展开）。"""
    if not isinstance(resp, dict):
        return {"ok": False, "why": "回执不是 dict"}
    body = resp.get("gbt_result", resp)
    inner = body.get("result") if isinstance(body, dict) else None
    return inner if isinstance(inner, dict) else {}


def call(kind: str, payload: dict) -> dict:
    t0 = time.time()
    resp = run_task(kind, payload)
    body = resp.get("gbt_result", resp) if isinstance(resp, dict) else {}
    return {
        "kind": kind,
        "payload": payload,
        "denied": bool((body or {}).get("denied") or (resp or {}).get("denied")),
        "envelope": (body or {}).get("status"),
        "missing_scopes": (body or {}).get("missing_scopes") or (resp or {}).get("missing_scopes"),
        "reason": (body or {}).get("reason") or (resp or {}).get("reason")
                  or (body or {}).get("error") or (resp or {}).get("error"),
        "result": unwrap(resp),
        "elapsed_s": round(time.time() - t0, 2),
    }


# ── 一、GBT天真（comfy_native）──────────────────────────────────────────────

# 正例按 **ComfyUI 的写法**给（节点名 + socket 名 + filename_prefix），不给我们自己的别名。
# 这张图能不能过，就是"契约保真"的判据：过不了 = 我们嘴上说同契约，实际只认自己的别名。
GOOD_WORKFLOW = {
    "nodes": [
        {"id": "n1", "node": "LoadImage",
         "inputs": {"image": "holo_pet/assets/digital-human/standard/reference-front.jpg"}},
        {"id": "n2", "node": "ImageScale",
         "inputs": {"width": 512, "height": 512, "upscale_method": "lanczos"}},
        {"id": "n3", "node": "SaveImage",
         "inputs": {"filename_prefix": "state/comfy_native_livecheck/out"}},
    ],
    "edges": [
        {"from": "n1", "to": "n2", "field": "image->image"},
        {"from": "n2", "to": "n3", "field": "image->image"},
    ],
}

BAD_WORKFLOW = {
    "nodes": [
        {"id": "n1", "node": "LoadImage", "inputs": {}},                      # 缺必填 image
        {"id": "n2", "node": "ImageFantasy", "inputs": {}},                   # 未知节点
        {"id": "n3", "node": "ImageScale", "inputs": {"width": 512}},         # 缺必填 height
    ],
    "edges": [
        {"from": "n1", "to": "n2", "field": "image->image"},
        {"from": "n2", "to": "n1", "field": "image->image"},                  # 成环
    ],
}

# 写面真跑用的小图（512×512，落 .scratch，不进交付树）
WRITE_CHECK_WORKFLOW = {
    "nodes": [
        {"id": "n1", "node": "LoadImage",
         "inputs": {"image": "holo_pet/assets/digital-human/standard/reference-front.jpg"}},
        {"id": "n2", "node": "ImageScale",
         "inputs": {"width": 256, "height": 256, "upscale_method": "lanczos"}},
        {"id": "n3", "node": "SaveImage",
         "inputs": {"filename_prefix": ".scratch/comfy-live-check/out"}},
    ],
    "edges": [
        {"from": "n1", "to": "n2", "field": "image->image"},
        {"from": "n2", "to": "n3", "field": "image->image"},
    ],
}


def tianzhen() -> dict:
    st = call("comfy_native", {"op": "status"})
    con = call("comfy_native", {"op": "contract"})
    nodes = call("comfy_native", {"op": "nodes"})
    val_ok = call("comfy_native", {"op": "validate", "workflow": GOOD_WORKFLOW})
    val_bad = call("comfy_native", {"op": "validate", "workflow": BAD_WORKFLOW})
    # 写面真跑一次（落点在被 git 忽略的 .scratch，不进交付树）；再拿坏图跑一次证明 fail-closed。
    run_ok = call("comfy_native", {"op": "run", "workflow": WRITE_CHECK_WORKFLOW})
    run_bad = call("comfy_native", {"op": "run", "workflow": BAD_WORKFLOW})

    # op=nodes 的 nodes 是 **dict**：{节点名: {in/out/writes/desc}}（不是 list of dict —— 我第一版按
    # list 解析，读出来 27 个算子被算成 0，好在打印行当场显形，没被当成"没有算子"写进账）。
    nodes_raw = (nodes.get("result") or {}).get("nodes") or {}
    node_list = []
    if isinstance(nodes_raw, dict):
        for nm, spec in nodes_raw.items():
            spec = spec if isinstance(spec, dict) else {}
            node_list.append({"node": nm, "in": spec.get("in"), "out": spec.get("out"),
                              "writes": spec.get("writes"), "desc": spec.get("desc")})
    node_list.sort(key=lambda r: str(r["node"]))
    c = con.get("result") or {}

    runs_file = ROOT / "gbt_allinone" / "store" / "comfy_native" / "runs.jsonl"
    runs = []
    if runs_file.is_file():
        for line in runs_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except Exception:                              # noqa: BLE001
                continue
    real_runs = [{
        "at": r.get("at"), "nodes": r.get("nodes"), "seconds": r.get("seconds"),
        "products": r.get("products"),
        "trace": [{"node": t.get("node"), "ok": t.get("ok"), "ms": t.get("ms"),
                   "gate_pass": (t.get("gate") or {}).get("pass"),
                   "sha16": ((t.get("gate") or {}).get("info") or {}).get("sha256")}
                  for t in (r.get("trace") or [])],
    } for r in runs[-3:]]

    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "名称": "GBT天真（主人命名 2026-10-11「触手的 ComfyUI 我们取名叫 GBT天真」）",
        "能力位": "comfy_native",
        "域": "creation",
        "status": st,
        "contract": c,
        "nodes_count": len(node_list),
        "nodes": node_list,
        "validate_ok": {"workflow": GOOD_WORKFLOW, **val_ok},
        "validate_bad": {"workflow": BAD_WORKFLOW, **val_bad},
        "run_ok": {"workflow": WRITE_CHECK_WORKFLOW, **run_ok},
        "run_bad": {"workflow": BAD_WORKFLOW, **run_bad},
        "写面门规约": "op=run 走同一道 run_task 门；按主人 2026-10-19 令，filesystem_write 已不再要票"
                     "（auth_gate.ENFORCED_SCOPES 只留浏览器/桌面/设备/内网/隐私/进程/远端/发声/"
                     "数据外发/外部大模型/生产发布/强制放行）⇒ 写面会真写盘，落点由 out/filename_prefix 决定，"
                     "缺省落 store/comfy_native，并落审计与 runs.jsonl",
        "runs_total": len(runs),
        "runs_last": real_runs,
        "口径": "只读面真跑；写面（op=run）真跑一次小图并把产物 sha256 记账；坏图跑一次证明 fail-closed；"
                "runs_last 是盘上既有生产流水（含 4K 放大）",
    }


# ── 二、五维合一（brain_unify）─────────────────────────────────────────────

INTENTS = [
    {"label": "只读·数据域", "goal": "统计一下这段话有多少个词"},
    {"label": "只读·系统域", "goal": "看一下本机能力位总共有多少位、分哪些域"},
    {"label": "只读·系统健康", "goal": "查一下本机系统健康信息（平台、Python 版本、时间）"},
    # 这一条是为了拿到**拒绝路径的完整回执**（缺哪张票）：屏/窗/输入属隐私与桌面控制，必被门挡。
    {"label": "会被门挡住", "goal": "看看当前屏幕上有哪些窗口"},
    {"label": "指定能力直跑", "goal": "指定能力直跑：echo", "kind": "echo"},
]


def five_dim() -> dict:
    rows = []
    for it in INTENTS:
        payload = {"goal": it["goal"]}
        if it.get("kind"):
            payload["kind"] = it["kind"]
        c = call("brain_unify", payload)
        res = c.get("result") or {}
        chain = res.get("chain") or {}
        rows.append({
            "label": it["label"],
            "goal": it["goal"],
            "指定 kind": it.get("kind"),
            "envelope": c.get("envelope"),
            "denied": c.get("denied"),
            "missing_scopes": c.get("missing_scopes"),
            "elapsed_s": res.get("elapsed_s") or c.get("elapsed_s"),
            "kind": res.get("kind"),
            "chain": {
                "route": chain.get("route"),
                "execute": chain.get("execute"),
                "verify": chain.get("verify"),
                "health": chain.get("health"),
            },
            "error": c.get("reason"),
        })
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "入口": "run_task('brain_unify', {goal}) —— 与万能插 five-dim.py cap 同一条门",
        "维度": {
            "route": "语义路由：统一大模型在真方法表里选（不可用时降级并自曝 degraded_reason）",
            "execute": "万能插执行：单能力直调或 parallel 线程池，全部走 run_task 同一道门",
            "verify": "触手肉眼验证：抓全屏帧 + 感知指纹（先看再动）",
            "health": "五维自检评分：route/execute/tentacle/vision/audit 各一维",
            "unify": "本入口：route→execute→verify→health 顺序串链，route 的 best 喂给 execute",
        },
        "intents": rows,
        "extract_note": "门回执双层嵌套：gbt_result.result.chain（按单层取会取到空 dict）",
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    t = tianzhen()
    (OUT / "gbt-tianzhen-live.json").write_text(
        json.dumps(t, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[GBT天真] 算子 %d · 契约面 %s · 同名 %s · validate 正例=%s · 反例抓到 %d 条错 · 写面真跑=%s（产物 %d）· 坏图=%s"
          % (t["nodes_count"], t["contract"].get("contract_nodes"),
             len(t["contract"].get("native_also_in_contract") or []),
             (t["validate_ok"].get("result") or {}).get("ok"),
             len(((t["validate_bad"].get("result") or {}).get("errors") or [])),
             (t["run_ok"].get("result") or {}).get("ok"),
             len((t["run_ok"].get("result") or {}).get("products") or []),
             (t["run_bad"].get("result") or {}).get("ok")))
    f = five_dim()
    (OUT / "five-dim-live.json").write_text(
        json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in f["intents"]:
        print("[五维] %-12s %-16s path=%-9s degraded=%-5s execute=%-7s health=%s  %ss"
              % (r["label"], r["kind"], (r["chain"]["route"] or {}).get("path"),
                 (r["chain"]["route"] or {}).get("degraded"),
                 (r["chain"]["execute"] or {}).get("status"),
                 (r["chain"]["health"] or {}).get("healthy"), r["elapsed_s"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
