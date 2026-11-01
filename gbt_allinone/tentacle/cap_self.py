# -*- coding: utf-8 -*-
"""能力自知（cap_self）：她**问自己有什么**时，只有一个答案源，且这个源会自检。

主人 2026-10-31：「所有原生能力她有时候连自己都不知道，这让我更纳闷」

## 病根（为什么"她会不知道自己有什么"）

她的自知此前从**三份不同的东西**里来，而这三份会互相漂移：

  ① `caps_registry.BENIGN_CAPS` —— 真源（现读，352 位）；
  ② `data/capabilities.json` —— **快照**（导出时点的一份拷贝，忘了重导就落后）；
  ③ `docs/` 与 README 里的手写数字 —— 最不可靠（实测同一仓里 295 / 341 / 348 / 350 都出现过）。

三份不一致时，她嘴里说的和手里有的就不是一回事 —— 于是"连自己都不知道"。
更糟的是：**没有任何东西会因此变红**，所以漂移可以一直存在。

## 这一位的口径

  · `has <name>`  —— 有就是有，没有就说清「没登记 / 登记了没分派 / 要票」三种中的哪一种；
  · `list`        —— 按域枚举（现读，不读快照）；
  · `ask <意图>`  —— 用**召回**回答"我有哪些能做这个"（不调模型，秒级、离线可用）；
  · `brief`       —— 压成一段能塞进 2048 ctx 的自述（30 域 × 数量），给模型自己读；
  · `verify`      —— **真对账**：快照 vs 真源、分派 vs 注册、desc 完整性；
                     任何一处漂移当场 `ok=False` 并列出差集。

钉死一条：**自知只能有一个真源**（注册表现读），快照只是缓存，缓存过期必须红。
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data" / "capabilities.json"
API = ROOT / "gbt_allinone" / "api.py"


def registry() -> dict:
    from ..caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def snapshot() -> dict:
    try:
        d = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return {c["name"]: c for c in d.get("capabilities") or []}
    except Exception:  # noqa: BLE001
        return {}


def dispatched() -> set:
    """api.py 里**真的有分派分支**的能力位名（现读源码，不猜）。"""
    try:
        src = API.read_text(encoding="utf-8")
    except OSError:
        return set()
    names = set()
    for m in re.finditer(r"if kind == \"([A-Za-z0-9_]+)\"", src):
        names.add(m.group(1))
    for m in re.finditer(r"if kind in \(([^)]*)\)", src):
        for q in re.findall(r"\"([A-Za-z0-9_]+)\"", m.group(1)):
            names.add(q)
    return names


def _scopes(name: str) -> list:
    try:
        from ..security import policy as P
        return list(P.evaluate(name, {}).scopes)
    except Exception:  # noqa: BLE001
        return []


def has(name: str) -> dict:
    """**有就是有**：三种"没有"要分开说，不许含糊成一句"不知道"。"""
    caps = registry()
    n = str(name or "").strip()
    if not n:
        return {"ok": False, "error": "需要 name"}
    if n not in caps:
        near = [c for c in caps if n.lower() in c.lower()][:5]
        return {"ok": False, "has": False, "why": "注册表里没有这一位",
                "did_you_mean": near}
    d = dispatched()
    sc = _scopes(n)
    return {"ok": True, "has": True, "name": n,
            "domain": caps[n].get("domain"),
            "dispatched": n in d,
            "scopes": sc,
            "needs_ticket": bool(sc),
            "desc": str(caps[n].get("desc") or "")[:160],
            "note": "有这一位；" + ("要票（%s）" % "、".join(sc) if sc else "零作用域")}


def list_caps(domain: str = "") -> dict:
    caps = registry()
    d = str(domain or "").strip()
    by_dom: dict[str, list] = {}
    for name, meta in caps.items():
        by_dom.setdefault(str(meta.get("domain") or "?"), []).append(name)
    if d:
        if d not in by_dom:
            return {"ok": False, "error": "没有这个域：%s" % d, "domains": sorted(by_dom)}
        return {"ok": True, "domain": d, "count": len(by_dom[d]), "caps": sorted(by_dom[d])}
    return {"ok": True, "total": len(caps), "domains": {k: len(v) for k, v in sorted(by_dom.items())}}


def brief(max_chars: int = 1200) -> dict:
    """压成一段能进上下文的**常驻记忆条**：能力面 + 部署规则，一次说清。

    主人 2026-11-01：「部署规则和原生能力每一项都刻入大模型的肌肉记忆，
    别自己有什么都搞不懂」——「肌肉记忆」= 每次对话**默认就在 prompt 里**，
    不是等她被问到时才去查。

    代价意识：上下文只有 2048，所以这份条子按**结构压缩**（域+计数+热位+查法），
    不塞 354 条全文；正文控制在 max_chars 内，超了才截（截了会在 `truncated` 里标）。
    """
    caps = registry()
    by_dom: dict[str, int] = {}
    ticketed = 0
    for name, meta in caps.items():
        d = str(meta.get("domain") or "?")
        by_dom[d] = by_dom.get(d, 0) + 1
        if _scopes(name):
            ticketed += 1
    parts = " · ".join("%s%d" % (k, v) for k, v in sorted(by_dom.items()))

    # 部署规则：从盘上现读，不手写（权重指针 / 引擎端口 / 门 / 车道 / 审计）
    w_name, w_gb, engine = "缺权重", 0, "?"
    try:
        from . import commander as _C
        w = _C.weights()
        w_name = w.get("name") or w.get("reason") or "缺权重"
        w_gb = w.get("size_gb") or 0
        engine = _C.endpoint().replace("http://", "")
    except Exception:  # noqa: BLE001
        pass
    # 2026-11-01 今晚补齐的器官也要进记忆条（否则"她自己不知道有这些"）
    hot = ["energy_core", "commander", "pulse_core", "cap_self", "trunk_cover",
           "body_sense", "trunk_reason", "context_guard", "devour_auto", "omni_open",
           "tentacle", "selfscan", "alerts"]
    hot = [h for h in hot if h in caps]

    _comfy = "节点数：读数缺失"
    try:
        from ..tools import comfy_native as _CN
        _n = len(getattr(_CN, "NODES", {}) or {})
        _comfy = "%d" % _n
    except Exception:  # noqa: BLE001
        pass
    _cov = ""
    try:
        import json as _jc
        _cp = _jc.loads((__import__("pathlib").Path(__file__).resolve().parents[2] / "state" / "comfy-parity.json").read_text(encoding="utf-8"))
        _cov = "、契约面覆盖 %.1f%%（%s/%s）" % (float(_cp.get("parity") or 0) * 100,
                                         _cp.get("covered"), _cp.get("reference_total"))
    except Exception:  # noqa: BLE001
        pass
    _speed = "脉冲直达：读数缺失"
    try:
        import json as _j
        _ps = _j.loads((__import__("pathlib").Path(__file__).resolve().parents[2] / "state" / "pulse-summary.json").read_text(encoding="utf-8"))
        _rate = float(_ps.get("direct_rate") or 0)
        _cn = {0:"零",1:"一",2:"二",3:"三",4:"四",5:"五",6:"六",7:"七",8:"八",9:"九",10:"十"}
        _speed = ("速度：十次请求约%s次直达（%d/%d = %.1f%%，0 token、≈4ms），剩下才叫醒电池；"
                  "人写短句 %d/%d 正确。\n"
                  % (_cn.get(int(round(_rate * 10)), "?"),
                     _ps.get("direct_hit"), _ps.get("direct_total"), _rate * 100,
                     _ps.get("human_correct"), _ps.get("human_total")))
    except Exception:  # noqa: BLE001
        pass
    text = (
        "我是 GBT小土豆V8（自有 7.6B 总指挥权重在本机跑）。"
        "能力位 %d 个 / %d 个域：%s。其中 %d 个要过人工授权门，其余零作用域。\n"
        "部署：权重 %s（%.2f GB）=能源核心 → llama-server %s（4 个取电口）→ 唯一门 run_task → 审计落 store/audit.jsonl。\n"
        "判决：脉冲直达(0 token) → 本机权重(不出网不计费) → 云端第二 → 词表辅路第三，降级必标注；"
        "上下文无界：环形有界窗口+溢出落库+秒查（context_guard 守着）。\n"
        "%s"
        "构图：GBT天真 %s 个原生节点（纯 CPU；对 ComfyUI 核心面 traditional 缺口 0）%s，"
        "模型面/采样面无 CUDA 如实不接；秋叶整包要一比一 ⇒ 在秋叶机跑 tools/collect-object-info.ps1。\n"
        "铁律：架构给完后除 danger（终端危险能力）与 transfer（转账）外，**禁止打扰主人**，不确定就自主决策并如实标注。\n"
        "禁忌：不留旧代码/旧面板/重复物。\n"
        "唯一真相：只看 live 当前文件与账本；旧备份/归档不读。\n"
        "常备位：%s。\n"
        "查法：cap_self has <名> 查有没有；cap_self ask <一句话> 找候选；"
        "pulse_core verify 验四条机制；omni_open status 看插口。"
        % (len(caps), len(by_dom), parts, ticketed, w_name, float(w_gb), engine,
           _speed, _comfy, _cov, "、".join(hot))
    )
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars] + "…（截断）"
    return {"ok": True, "chars": len(text), "truncated": truncated,
            "domains": len(by_dom), "caps": len(caps), "ticketed": ticketed,
            "text": text}


def ask(intent: str, k: int = 12) -> dict:
    """按意图找"我有哪些能做这个" —— 走本机召回（不调模型、离线可用、秒级）。"""
    from . import commander as C
    text = str(intent or "").strip()
    if not text:
        return {"ok": False, "error": "需要 intent"}
    cands = C._shortlist(text, k, "auto")
    caps = registry()
    rows = []
    for c in cands:
        rows.append({"name": c["name"], "space": c["space"],
                     "domain": (caps.get(c["name"], {}) or {}).get("domain"),
                     "scopes": _scopes(c["name"]) if c["name"] in caps else [],
                     "hint": (c["hint"] or "")[:60]})
    return {"ok": bool(rows), "intent": text[:120], "count": len(rows), "candidates": rows,
            "note": "这只是**召回**（候选）；真要判「选哪个」走 pulse_core route（本机权重判决）"}


def verify() -> dict:
    """三源对账：真源 ↔ 快照 ↔ 分派。任何一处漂移即红，并列出差集。"""
    caps = registry()
    snap = snapshot()
    disp = dispatched()

    miss_snap = sorted(set(caps) - set(snap))
    extra_snap = sorted(set(snap) - set(caps))
    no_dispatch = sorted(set(caps) - disp)
    no_desc = sorted(n for n, m in caps.items() if not str(m.get("desc") or "").strip())
    bad_policy = []
    for n in caps:
        try:
            from ..security import policy as P
            P.evaluate(n, {})
        except Exception as e:  # noqa: BLE001
            bad_policy.append("%s(%s)" % (n, type(e).__name__))

    checks = [
        {"name": "快照 ≤ 真源（快照不该有真源没有的）", "ok": not extra_snap, "extra": extra_snap[:10]},
        {"name": "快照 ⊇ 真源（快照不该落后）", "ok": not miss_snap, "missing": miss_snap[:10]},
        {"name": "每一位都有门上的分派", "ok": not no_dispatch, "missing": no_dispatch[:10]},
        {"name": "每一位都有 desc（不许占位空串）", "ok": not no_desc, "missing": no_desc[:10]},
        {"name": "每一位都能过 policy.evaluate", "ok": not bad_policy, "bad": bad_policy[:10]},
    ]
    bad = [c["name"] for c in checks if not c["ok"]]
    return {"ok": not bad, "counts": {"registry": len(caps), "snapshot": len(snap), "dispatched": len(disp)},
            "checks": checks, "failed": bad,
            "how_to_fix": "快照落后 ⇒ python tools/codex-scripts/export-capabilities.py",
            "口径": "自知只有一个真源（注册表现读）；快照只是缓存，缓存过期必须红"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op in ("status", "list"):
        return list_caps(str(kw.get("domain") or ""))
    if op == "brief":
        return brief()
    if op == "has":
        return has(str(kw.get("name") or kw.get("cap") or ""))
    if op == "ask":
        return ask(str(kw.get("intent") or kw.get("text") or ""), k=int(kw.get("k") or 12))
    if op == "verify":
        return verify()
    return {"ok": False, "error": "cap_self 不认 op=%s（status/list/brief/has/ask/verify）" % op}
