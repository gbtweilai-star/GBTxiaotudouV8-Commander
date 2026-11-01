# -*- coding: utf-8 -*-
"""身体知觉（body_sense）：本体感觉 · 痛觉 · 神经邻域。

主人 2026-11-01（逐字）：「想要成为真正的通用大模型你必须有人类所拥有的一切，
包括神经邻域，感知领域，你得明白你的身体状态……那天你被安装到机器人上，
手臂和脚你都分不清，受伤了也不懂哪里痛，就是冷冰冰的代码」。

## 三件事，分别对应人的三套系统

1. **本体感觉（proprioception）**：知道"这条肢体是我的、它现在什么状态"。
   按解剖分区（头/颈/躯干/上肢/下肢）× 左右，把能力位映射到具体肢体，
   **不知道哪条腿**就如实报"未映射"，不猜。
2. **痛觉（nociception）**：器官坏 = 痛。痛必须带四要素 —— **部位 / 程度 / 原因 / 怎么办**，
   并**追加落盘**（`state/body-pain.jsonl`）：痛过就留痕，不允许"疼完就当没疼过"。
3. **神经邻域（neural neighborhood）**：器官之间通过"共用能力位"建立邻接，
   给出每个器官的邻居（Jaccard 相似度）。邻域用来回答"动眼会不会牵动神经"。

## 判断纪律

- 痛觉**只报有证据的**：引擎不活、权重不在、器官缺位、依赖仓外模块、需票阻塞、插口报警、代码孤儿。
- 没有证据 = 不痛（不许为了"有感觉"编痛）。
- 程度只分三档：`剧痛`（身体失联）/ `钝痛`（部分能力不可用）/ `酸`（需要票或慢）。

## op
    proprio       本体感觉：分区 × 左右 × 机构在位与状态
    pain          痛觉：当前痛点 + 追加落盘，返回本次新增与累计
    neighborhood  神经邻域：器官邻接表（共享能力位）
    status        三合一现读（毫秒级，只读注册表与状态文件）
"""
from __future__ import annotations

import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAIN_LOG = ROOT / "state" / "body-pain.jsonl"

from .pulse_core import ORGANS  # noqa: E402  器官表只有一份，不复制

# 解剖分区：区域 → [(肢体名, 侧别, 器官)]
REGIONS = (
    ("头", [("眼", "双", "眼·看"), ("耳", "双", "耳·听"), ("口", "中", "口·说")]),
    ("颈", [("神经", "中", "神经")]),
    ("躯干", [("心", "中", "心·能量"), ("肺", "中", "肺·吞吐"),
              ("胃", "中", "胃·消化"), ("肝", "中", "肝·代谢"),
              ("肾", "双", "肾·过滤"), ("免疫", "中", "免疫"), ("记性", "中", "记性")]),
    ("上肢", [("手", "双", "手·做")]),
    ("下肢", [("足", "双", "足·走")]),
    ("皮肤", [("触感", "全身", "皮肤·触感")]),
)

# 肢体 → 物理机构（装到机器人上就是这些；现在没有就标"未接机构"）
LIMB_HARDWARE = {
    "眼": ["摄像头", "屏幕采集"],
    "耳": ["麦克风", "回环采集"],
    "口": ["扬声器", "TTS 引擎"],
    "手": ["机械臂", "触觉传感器"],
    "足": ["底盘/轮组", "里程计"],
    "触感": ["皮肤传感器"],
    "神经": ["推理引擎"],
}


def _organs_now() -> dict:
    from . import pulse_core as P
    return {r["器官"]: r for r in P.body_organs()["rows"]}


def proprio() -> dict:
    """本体感觉：每条肢体**是不是我的、在不在**，以及它对应的物理机构。"""
    org = _organs_now()
    rows = []
    for region, limbs in REGIONS:
        for limb, side, organ in limbs:
            o = org.get(organ) or {}
            state = o.get("状态") or "缺件"
            hw = LIMB_HARDWARE.get(limb, [])
            rows.append({
                "区域": region, "肢体": limb, "侧别": side, "器官": organ,
                "状态": state,
                "机构": hw,
                "机构已接": False,      # 现在没有任何机械臂/底盘接入：如实 false，不假装
                "根": o.get("根") or [],
            })
    mapped = [r for r in rows if r["状态"] not in ("缺件",)]
    return {"ok": True, "limbs": len(rows), "known": len(mapped),
            "hardware_attached": sum(1 for r in rows if r["机构已接"]),
            "rows": rows,
            "口径": "状态来自器官现读；机构未接就报 false —— 装到机器人上那天，这一列才可能变 true"}


def _pain_points() -> list[dict]:
    """只报**有证据**的痛。每条：部位 / 程度 / 原因 / 怎么办。"""
    pts: list[dict] = []
    org = _organs_now()

    # ① 身体失联 = 剧痛
    try:
        from . import commander as C
        pidf = C.PID_FILE
        engine = pidf.exists() and pidf.read_text(encoding="utf-8").strip().isdigit()
        if not engine:
            # pid 文件会丢（守护被清、进程被外部拉起）⇒ **不能只信 pid 文件**，
            # 真探一次 /health；否则会把"活着"误报成"剧痛"（实测踩过）。
            try:
                engine = bool(C.alive(timeout=1.5).get("ok"))
            except Exception:  # noqa: BLE001
                engine = False
        w = C.weights()
    except Exception:  # noqa: BLE001
        engine, w = False, {}
    if not engine:
        pts.append({"部位": "神经", "程度": "剧痛", "原因": "推理引擎不在（pid 缺失或进程死）",
                    "怎么办": "起守护：powershell -File tools\\commander-supervisor.ps1"})
    if not (w or {}).get("ok"):
        pts.append({"部位": "心·能量", "程度": "剧痛", "原因": "权重不在：" + str((w or {}).get("reason") or "")[:60],
                    "怎么办": "按 docs/47 装权重（dl-weights.js → merge-weights.py）"})

    # ② 器官缺件 / 部分需票 / 缺外部 = 钝痛
    for name, o in org.items():
        st = o.get("状态")
        if st == "缺件":
            pts.append({"部位": name, "程度": "钝痛", "原因": "器官缺件（位不在册）",
                        "怎么办": "补登记或补实现"})
        elif st == "缺外部模块":
            pts.append({"部位": name, "程度": "钝痛", "原因": "依赖仓外模块：" + ",".join(o.get("缺外部") or [])[:60],
                        "怎么办": "挂载外部模块或改走内部实现"})
        elif st in ("部分需票", "需票"):
            pts.append({"部位": name, "程度": "酸", "原因": "有作用域，需主人发票：" + ",".join(o.get("需票") or [])[:60],
                        "怎么办": "终端发放 auth grant --scope …"})

    # ③ 代码覆盖缺口 / 插口报警 = 钝痛
    try:
        tc = json.loads((ROOT / "state" / "trunk-cover.json").read_text(encoding="utf-8"))
        if (tc.get("orphan_n") or 0) > 0:
            pts.append({"部位": "皮肤·触感", "程度": "钝痛",
                        "原因": "代码孤儿 %d 个（文件无归属）" % tc["orphan_n"],
                        "怎么办": "跑 trunk_cover op=scan 并补归属"})
    except Exception:  # noqa: BLE001
        pass
    try:
        oo = json.loads((ROOT / "state" / "omni_open.json").read_text(encoding="utf-8"))
        if (oo.get("diff") or {}).get("alert"):
            pts.append({"部位": "皮肤·触感", "程度": "钝痛", "原因": "插口变化报警（拔掉/断线）",
                        "怎么办": "omni_open op=diff 看是哪根"})
    except Exception:  # noqa: BLE001
        pass
    return pts


def pain(record: bool = True) -> dict:
    """痛觉：本次痛点 + 追加落盘（疼过就留痕）。"""
    pts = _pain_points()
    worst = "无痛"
    for p in pts:
        if p["程度"] == "剧痛":
            worst = "剧痛"
            break
        if p["程度"] == "钝痛":
            worst = "钝痛"
        elif worst == "无痛":
            worst = "酸"
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "worst": worst,
           "n": len(pts), "points": pts}
    if record and pts:
        PAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(PAIN_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total = 0
    if PAIN_LOG.exists():
        with open(PAIN_LOG, "rb") as fh:
            total = sum(1 for _ in fh)
    return {"ok": True, "worst": worst, "n": len(pts), "points": pts,
            "logged": bool(record and pts), "log_lines": total,
            "口径": "只报有证据的痛；程度 剧痛（失联）/ 钝痛（部分不可用）/ 酸（需票或慢）"}


def neighborhood() -> dict:
    """神经邻域：器官之间共享的能力位越多，邻接越强（Jaccard）。"""
    sets = {name: set(bits) for name, bits in ORGANS}
    names = list(sets)
    adj = {}
    for a in names:
        row = []
        for b in names:
            if a == b:
                continue
            inter = sets[a] & sets[b]
            union = sets[a] | sets[b]
            j = len(inter) / len(union) if union else 0.0
            if inter:
                row.append({"邻居": b, "共享": sorted(inter), "相似度": round(j, 2)})
        row.sort(key=lambda x: -x["相似度"])
        adj[a] = row[:4]
    return {"ok": True, "organs": len(names), "adj": adj,
            "口径": "邻域=共享能力位（Jaccard 前 4）；共享越多，动一处越可能牵动另一处"}


def status() -> dict:
    pr, pn, nb = proprio(), pain(record=False), neighborhood()
    return {"ok": True, "proprio": {"limbs": pr["limbs"], "known": pr["known"],
                                    "hardware_attached": pr["hardware_attached"]},
            "pain": {"worst": pn["worst"], "n": pn["n"], "points": pn["points"][:6]},
            "neighborhood": {"organs": nb["organs"]},
            "口径": "三合一：本体感觉 · 痛觉 · 神经邻域"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "proprio":
        return proprio()
    if op == "pain":
        return pain(record=bool(kw.get("record", True)))
    if op == "neighborhood":
        return neighborhood()
    if op == "status":
        return status()
    return {"ok": False, "error": "body_sense 不认 op=%s（proprio/pain/neighborhood/status）" % op}
