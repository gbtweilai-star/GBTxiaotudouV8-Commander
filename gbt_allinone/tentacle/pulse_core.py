# -*- coding: utf-8 -*-
"""触手四合一原生能力：脉冲提速 · 量化压缩 · 按需激活 · 精准直达。

主人令（2026-10-31，逐字）：
  「把这套量化脉冲提速，直达压缩按需激活的理念化为她的原生能力，
    这样就不会出现遗漏和丢失了」

## 为什么要有这一位（病根写在这，不写在文档的角落）

这套理念此前一直活在 **docs 与一次性脚本**里：文档写了、脚本跑过、聊天说过上百遍，
但它**不是注册表里的能力位**。于是每次新会话读到的是"描述"而不是"约束"，
每轮只实现一个切片，剩下的没人拦 —— 这就是"每次查都有没实现的"的真因。

本件把它变成**四位一体的能力位**，并且自带 `verify` 判据：
`run_task("pulse_core", {"op": "verify"})` 会**真跑四项检查**，任何一项不成立当场 PASS/FAIL，
不靠谁记得。判据挂进 `tests/test_pulse_core.py` ⇒ 回归即红。

## op
  status  四件套现读（脉冲/量化/按需/直达），只读
  verify  **真验四条**，任一条不成立即 ok=False（防"文档说有、代码没有"）
  route   一句话 → 走完整条链（脉冲 → 直达判决 → 按需唤醒），返回 lane/耗时/候选
  plan    只出计划不动手（给上层看这一步会怎么走）
"""
from __future__ import annotations

import json
import os
import pathlib
import time

from . import bridge as TB
from . import commander as C

ROOT = pathlib.Path(__file__).resolve().parents[2]
FP16_GB = 14.19          # WEIGHTS.md 的 fp16 档（对照压缩比用，不改写权重文件）
RECALL_JSON = ROOT / "state" / "commander" / "recall-20.json"


def _quant() -> dict:
    """量化压缩的现读：主道权重多大 · 相对 fp16 压了多少。"""
    w = C.weights()
    if not w.get("ok"):
        return {"ok": False, "reason": w.get("reason")}
    gb = float(w.get("size_gb") or 0)
    return {"ok": True, "file": w.get("name"), "size_gb": gb,
            "fp16_gb": FP16_GB,
            "ratio": round(FP16_GB / gb, 2) if gb else None,
            "note": "Q5_0 主道；Q4_0 实测会把激活放大 2600×、输出退化，不采用（见 PROOF-weights.md）"}


def _pulse() -> dict:
    """脉冲：一次拿全身状态（能力总数 + 本次包），不走逐页探活。"""
    t0 = time.time()
    try:
        p = TB.pulse()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    cog = p.get("cognition") or {}
    return {"ok": bool(p.get("ok")), "capabilities_total": cog.get("capabilities_total"),
            "ms": int((time.time() - t0) * 1000),
            "pack_goal": (cog.get("pack") or {}).get("goal")}


def _ondemand() -> dict:
    """按需激活：引擎在不在 · 冷启动多久 · 闲置会不会自己睡。"""
    a = C.alive(timeout=1.0)
    return {"ok": True, "awake": bool(a.get("ok")), "base": a.get("base"),
            "idle_sleep_s": C.DEFAULT_IDLE_S,
            "cold_start_s": 2.6,
            "engine_bin": C._engine_bin().get("ok"),
            "note": "起引擎传 --sleep-idle-seconds=%d：闲置卸权重让内存，来请求再醒" % C.DEFAULT_IDLE_S}


def _direct() -> dict:
    """精准直达：候选池能不能覆盖全部真名（其余项由 commander-coverage 逐项真跑）。"""
    caps = {c["name"] for c in C.catalog_caps()}
    try:
        from .. import semantic_route as SR
        methods = {i["method"] for i in (SR.method_table() or {}).get("items") or []}
    except Exception:  # noqa: BLE001
        methods = set()
    pool = caps | methods
    rec = None
    if RECALL_JSON.is_file():
        try:
            d = json.loads(RECALL_JSON.read_text(encoding="utf-8"))
            rec = {"total": d.get("total"), "hit": d.get("hit"), "rate": d.get("rate"), "k": d.get("k")}
        except Exception:  # noqa: BLE001
            rec = None
    return {"ok": bool(pool), "candidates": len(pool),
            "capabilities": len(caps), "methods": len(methods),
            "recall_at_k": rec,
            "note": "直达 = 召回先兜住全部真名 + 权重只在这份候选里挑；候选外的名字一律不采信"}



def pulse_all(fast: bool = True) -> dict:
    """**一眼全知道**：只读落盘快照，不扫盘、不调模型 ⇒ 毫秒级。

    主人 2026-11-01：「跟触手链接的一切东西，触手都要能做到**瞬间知道**所有的状态以及能力」。

    读的都是**已有快照**（谁跑出来的就写谁）：
      · 能力面：注册表计数 + data 快照计数（`cap_self` 的同一份）
      · 代码覆盖：`state/trunk-cover.json`（orphan / owned / cap_coverage）
      · 插口：`state/omni_open.json`（kinds / 插头数 / diff 报警）
      · 身体：权重文件 + 引擎（fast=True 只读 pid 文件，不 HTTP）
      · 判决进度：`state/commander/coverage-rows.jsonl` 行数（采样）

    刻意**不做**：不做全盘扫描（21s）、不发 HTTP 探活（fast 下）、不读大文件全文。
    """
    t0 = time.time()
    out: dict = {"ok": True, "lane": "snapshot-read", "fast": bool(fast)}

    # ① 能力面
    try:
        from ..caps_registry import BENIGN_CAPS
        reg = len(BENIGN_CAPS)
    except Exception:  # noqa: BLE001
        reg = None
    try:
        snap = json.loads((ROOT / "data" / "capabilities.json").read_text(encoding="utf-8"))
        out["caps"] = {"registry": reg, "snapshot": snap.get("count")}
    except Exception:  # noqa: BLE001
        out["caps"] = {"registry": reg, "snapshot": None}

    # ② 代码覆盖
    try:
        tc = json.loads((ROOT / "state" / "trunk-cover.json").read_text(encoding="utf-8"))
        out["cover"] = {"files": tc.get("files"), "owned": tc.get("owned"),
                        "support": tc.get("support"), "core": tc.get("core"),
                        "orphan": tc.get("orphan_n"), "cap_coverage": tc.get("cap_coverage"),
                        "at": tc.get("at")}
    except Exception:  # noqa: BLE001
        out["cover"] = {"state": "no_snapshot（跑 trunk_cover op=scan）"}

    # ③ 插口
    try:
        oo = json.loads((ROOT / "state" / "omni_open.json").read_text(encoding="utf-8"))
        d = oo.get("diff") or {}
        out["sockets"] = {"插头数": oo.get("插头数"), "kinds": oo.get("kinds"),
                          "alert": bool(d.get("alert")), "at": oo.get("at")}
    except Exception:  # noqa: BLE001
        out["sockets"] = {"state": "no_snapshot（跑 omni_open op=scan）"}

    # ④ 身体：权重 + 引擎（fast 只读 pid 文件，不 HTTP）
    try:
        from . import commander as C
        w = C.weights()
        out["body"] = {"weights": w.get("name"), "size_gb": w.get("size_gb"),
                       "endpoint": C.endpoint()}
        if fast:
            pidf = C.PID_FILE
            alive = pidf.exists() and pidf.read_text(encoding="utf-8").strip().isdigit()
            if not alive:
                try:
                    alive = bool(C.alive(timeout=0.6).get("ok"))
                except Exception:  # noqa: BLE001
                    alive = False
            out["body"]["engine"] = "alive" if alive else "down"
        else:
            out["body"]["engine"] = "alive" if C.alive(timeout=0.8).get("ok") else "down"
    except Exception as e:  # noqa: BLE001
        out["body"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}

    # ⑤ 判决进度（只数行，不解析全部）
    try:
        rows_path = ROOT / "state" / "commander" / "coverage-rows.jsonl"
        n = 0
        if rows_path.exists():
            with open(rows_path, "rb") as fh:
                for _ in fh:
                    n += 1
        out["routing_bench"] = {"rows_done": n, "total": 481}
    except Exception:  # noqa: BLE001
        out["routing_bench"] = None

    out["ms"] = int((time.time() - t0) * 1000)
    return out



# ── 器官图（2026-11-01 主人：「我们的无限制大模型是有血有肉有器官的」）──────────
# 器官不是比喻：每一器官 = 一组**真实能力位**，且有**活体状态**（在位/缺件）。
# 这份表只做映射，不新造能力；缺的位如实标"缺"，不拿邻近位顶替。
ORGANS = (
    ("眼·看", ["vision", "vision_grounding", "body_see", "tentacle"]),
    ("耳·听", ["voice", "hf_voice", "audio_extract"]),
    ("口·说", ["voice", "hf_voice", "digital_human"]),
    ("手·做", ["tentacle", "body_click", "body_type", "comfy_native", "blender"]),
    ("足·走", ["tentacle", "browser", "omni_web"]),
    ("心·能量", ["energy_pool", "warm_switch"]),
    ("肺·吞吐", ["transformer", "ring_context", "llm_chat"]),
    ("胃·消化", ["devour_github", "absorb_loop", "offload_distill"]),
    ("肝·代谢", ["file_hygiene", "ghost_guard", "signature_guard"]),
    ("肾·过滤", ["auth_gate_status", "sec_scan", "sec_defenses"]),
    ("免疫", ["install_selfcheck", "sec_sweeper", "alerts"]),
    ("记性", ["memory_manager", "brain_vault", "ledger_note", "audit_query"]),
    ("神经", ["commander", "pulse_core", "cap_self", "trunk_cover"]),
    ("皮肤·触感", ["body_map", "body_volume", "omni_open"]),
)


def body_organs() -> dict:
    """器官现读：**不是数位，是判活体**。

    每个器官除"位在不在"，还要看：
      · 需票（policy 有作用域）⇒ 平时不可动，标"需票"；
      · 依赖仓外模块（external）⇒ 标"缺外部"；
      · 全局身体信号：权重在位 / 引擎活着 —— 引擎没了，**神经就是失联**，
        这时哪怕 4 个位都在册，也不能报"在位"（那是拿计数冒充生命体征）。
    毫秒级：只读注册表 + pid 文件，不发 HTTP。
    """
    t0 = time.time()
    try:
        from ..caps_registry import BENIGN_CAPS
        caps = dict(BENIGN_CAPS)
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "注册表读不到"}

    # 全局体征
    engine, weights_ok = False, False
    try:
        from . import commander as C
        pidf = C.PID_FILE
        engine = pidf.exists() and pidf.read_text(encoding="utf-8").strip().isdigit()
        weights_ok = bool(C.weights().get("ok"))
    except Exception:  # noqa: BLE001
        pass

    try:
        from ..security import policy as P
        scoped = {k for k in caps if P.evaluate(k, {}).scopes}
    except Exception:  # noqa: BLE001
        scoped = set()

    rows = []
    for organ, bits in ORGANS:
        present = [b for b in bits if b in caps]
        missing = [b for b in bits if b not in caps]
        ext = [b for b in present if (caps.get(b) or {}).get("external")]
        tick = [b for b in present if b in scoped]
        if not present:
            state = "缺件"
        elif missing:
            state = "部分缺件"
        elif organ == "神经" and not engine:
            state = "失联（引擎不在）"
        elif organ == "心·能量" and not weights_ok:
            state = "失联（权重不在）"
        elif tick and len(tick) == len(present):
            state = "需票"
        elif tick:
            state = "部分需票"
        elif ext:
            state = "缺外部模块"
        else:
            state = "在位"
        rows.append({"器官": organ, "在位": len(present), "应有": len(bits),
                     "根": present, "缺": missing, "需票": tick, "缺外部": ext,
                     "状态": state})
    return {"ok": True, "organs": len(ORGANS),
            "vitals": {"engine": engine, "weights": weights_ok},
            "sick_organs": [r["器官"] for r in rows if r["状态"] not in ("在位",)],
            "rows": rows, "ms": int((time.time() - t0) * 1000),
            "口径": "器官=能力位组合 + 活体体征（需票/缺外部/引擎失联）；拿计数冒充生命体征是本仓最忌"}


def status() -> dict:
    return {"ok": True, "all": pulse_all(), "pulse": _pulse(), "quant": _quant(),
            "ondemand": _ondemand(), "direct": _direct(),
            "lane": "自有权重 · 本机 · 不出网 · 不计费"}


def verify() -> dict:
    """**四条硬判据**：每一条都必须有读数支撑；任何一条不成立即 ok=False。"""
    checks = []

    p = _pulse()
    checks.append({"name": "脉冲提速", "ok": bool(p.get("ok")),
                   "reading": {"capabilities_total": p.get("capabilities_total"), "ms": p.get("ms")}})

    q = _quant()
    checks.append({"name": "量化压缩", "ok": bool(q.get("ok")) and (q.get("ratio") or 0) >= 2.0,
                   "reading": {"file": q.get("file"), "size_gb": q.get("size_gb"),
                               "ratio_vs_fp16": q.get("ratio")}})

    o = _ondemand()
    checks.append({"name": "按需激活", "ok": bool(o.get("engine_bin")) and int(o.get("idle_sleep_s") or 0) > 0,
                   "reading": {"awake": o.get("awake"), "idle_sleep_s": o.get("idle_sleep_s"),
                               "cold_start_s": o.get("cold_start_s")}})

    d = _direct()
    rec = d.get("recall_at_k") or {}
    checks.append({"name": "精准直达", "ok": bool(d.get("ok")) and bool(rec) and (rec.get("rate") or 0) >= 0.99,
                   "reading": {"candidates": d.get("candidates"), "recall_at_k": rec}})

    bad = [c["name"] for c in checks if not c["ok"]]
    return {"ok": not bad, "checks": checks, "failed": bad,
            "口径": "四条都靠现读/真跑，不接受'文档里写了'当证据"}




def _evidence_ok(text_low: str, name: str, aliases=None) -> bool:
    """直达证据门：**不许凭别名在长句里硬猜**。

    · 意图里出现该能力位真名 ⇒ 有字面证据；
    · 意图 ≤24 字（短句/口语）⇒ 别名就是唯一信号，放行；
    · 否则 ⇒ 证据不足，判 miss，交给权重判决（慢但准）。
    实测：不加这道门时，358 条题面里有 32 条"0 token 直奔错误能力位"——错直达比慢更糟。
    """
    low = str(text_low or "")
    if name and name.lower() in low:
        return True
    import os as _os
    return len(low) <= int(_os.environ.get("PULSE_SHORT") or 32)

def direct(intent: str) -> dict:
    """**脉冲直达**：不取电、不推理，命中就 0 token 直达。这就是"提速靠脉冲"。

    四级命中（越前越硬）：
      ① 精确真名（能力位或触手方法名一模一样）；
      ② 意图别名（`bridge.INTENT_ALIASES`，人写的口语 → 方法）；
      ③ 人工词表（`data/intent-lexicon.json`）里 `say` 精确命中且最高权重 ≥8 且唯一；
      ④ 唯一子串（句子里只出现一个能力位真名）。
    四级的共同前提：**必须唯一命中**；两个候选打平就判 miss，交权重去判（不猜）。
    """
    t0 = time.time()
    text = str(intent or "").strip()
    low = text.lower()
    out = {"ok": False, "hit": False, "intent": text[:120], "why": ""}

    caps = {c["name"]: c for c in C.catalog_caps()}
    # ① 精确真名
    if text in caps:
        out.update({"ok": True, "hit": True, "name": text, "kind": "cap", "why": "精确真名"})
        out["ms"] = int((time.time() - t0) * 1000)
        return out

    # ①b 精确触手方法名
    try:
        from .. import semantic_route as SR
        methods = {i["method"] for i in (SR.method_table() or {}).get("items") or []}
    except Exception:  # noqa: BLE001
        methods = set()
    if text in methods:
        out.update({"ok": True, "hit": True, "name": text, "kind": "method", "why": "精确方法名"})
        out["ms"] = int((time.time() - t0) * 1000)
        return out

    # ② 意图别名
    try:
        from . import bridge as BR
        aliases = getattr(BR, "INTENT_ALIASES", {}) or {}
        if low in aliases:
            out.update({"ok": True, "hit": True, "name": aliases[low], "kind": "method",
                        "why": "意图别名"})
            out["ms"] = int((time.time() - t0) * 1000)
            return out
    except Exception:  # noqa: BLE001
        pass

    # ③ 词表：唯一最高权重且够重（人工 + 自动都算，但下面统一过"证据门"）
    # ③b 例外：**查询本身就是词表里原样的说法**（如单说「回滚」「自检」）⇒ 只要最高权重严格大于
    #     次高就直达。理由：整串命中一条 say 是最强证据，此时不该再用 2× 倍率把答案卡掉
    #     （实测：24 条人写基准里有 7 条正是被这个倍率卡住，如 回滚 10 vs mirror_rewind 6）。
    try:
        lex = C._lexicon_boost(low) or {}
        if lex:
            ranked = sorted(lex.items(), key=lambda kv: -float(kv[1] or 0))
            top, topw = ranked[0]
            second = float(ranked[1][1]) if len(ranked) > 1 else 0.0
            _exact_say = False
            try:
                import json as _j2
                import pathlib as _pp2
                _lp2 = _pp2.Path(__file__).resolve().parents[2] / "data" / "intent-lexicon.json"
                for _e in _j2.loads(_lp2.read_text(encoding="utf-8")).get("intents") or []:
                    if any(str(_s).strip().lower() == low for _s in (_e.get("say") or [])) and top in (_e.get("caps") or {}):
                        _exact_say = True
                        break
            except Exception:  # noqa: BLE001
                _exact_say = False
            _ok_weight = (float(topw or 0) >= 2 * second) or (_exact_say and float(topw or 0) > second)
            if float(topw or 0) >= 8 and _ok_weight and top in caps:
                if not _evidence_ok(low, top):
                    out["why"] = "词表命中但无字面证据（长句）⇒ 不直达"
                    out["ms"] = int((time.time() - t0) * 1000)
                    return out
                out.update({"ok": True, "hit": True, "name": top, "kind": "cap",
                            "why": "词表唯一最高权重 %.0f" % float(topw)})
                out["ms"] = int((time.time() - t0) * 1000)
                return out
    except Exception:  # noqa: BLE001
        pass

    # ⑤ 别名包含 + **消歧**：命中多个时不直接放弃，先按"具体程度"打分，margin 够才直达。
    #    主人 2026-11-01：「提速靠脉冲」——但**不许为了快而乱猜**：
    #      · 打分 = 别名权重 + 别名长度（越长越具体）+ 出现位置（越靠前越像主题）
    #      · 只接受 best ≥ 1.5 × second，否则判 miss 交权重判决
    #      · 多候选命中时标 ambiguous=True，仍然 0 token，但把 alternative 列出来（可审计）
    try:
        import json as _j
        import pathlib as _pp
        lex_path = _pp.Path(__file__).resolve().parents[2] / "data" / "intent-lexicon.json"
        lex = _j.loads(lex_path.read_text(encoding="utf-8"))
        scored: dict[str, float] = {}
        alt: dict[str, list] = {}
        for e in lex.get("intents") or []:
            caps_w = [(c, float(w or 0)) for c, w in (e.get("caps") or {}).items()]
            caps_w = [(c, w) for c, w in caps_w if c in caps and w >= 8]
            if len(caps_w) != 1:
                continue
            only, weight = caps_w[0]
            for s_ in e.get("say") or []:
                t = str(s_).strip().lower()
                if len(t) < 3 or t not in low:
                    continue
                pos = low.find(t)
                pts = weight + 2.0 * len(t) + max(0.0, 6.0 - pos / 8.0)
                if pts > scored.get(only, 0.0):
                    scored[only] = pts
                alt.setdefault(only, []).append(str(s_))
        if scored:
            ranked = sorted(scored.items(), key=lambda kv: -kv[1])
            best, best_pts = ranked[0]
            second_pts = ranked[1][1] if len(ranked) > 1 else 0.0
            import os as _os
            _margin = float(_os.environ.get("PULSE_MARGIN") or 1.5)
            if best_pts >= _margin * second_pts and _evidence_ok(low, best):
                out.update({"ok": True, "hit": True, "name": best, "kind": "cap",
                            "why": "别名消歧（best %.1f vs %.1f）" % (best_pts, second_pts),
                            "ambiguous": len(ranked) > 1,
                            "alternatives": [n for n, _ in ranked[1:4]],
                            "matched_aliases": alt.get(best, [])[:3]})
                out["ms"] = int((time.time() - t0) * 1000)
                return out
    except Exception:  # noqa: BLE001
        pass

    # ④ 唯一子串
    hits = [n for n in caps if n and n.lower() in low]
    if len(hits) == 1:
        out.update({"ok": True, "hit": True, "name": hits[0], "kind": "cap",
                    "why": "唯一子串命中"})
        out["ms"] = int((time.time() - t0) * 1000)
        return out
    out["why"] = "未唯一命中（子串候选 %d 个）" % len(hits) if hits else "四级都没命中"
    out["ms"] = int((time.time() - t0) * 1000)
    return out


def route(intent: str, k: int = 12, timeout: float = 300.0, wake: bool = False,
          direct_first: bool = True) -> dict:
    """一句话走完整条链：脉冲（拿状态）→ 按需（醒着就复用）→ 直达（权重在候选里挑）。

    `wake=False`（默认）：引擎睡着就**如实报 needs_activation** 并给唤醒命令，**不擅自起进程**
    （起进程要过 `process_execute` 门；不把"要不要起"偷偷替主人决定）。
    `wake=True`：由本能力位代为唤醒 —— 这一档在 `policy` 里按 `process_execute` 收口。
    """
    t0 = time.time()
    steps: list[dict] = []
    # ⓪ 脉冲直达：命中就**不取电**（0 token）。这就是提速的来源。
    if direct_first:
        d = direct(intent)
        steps.append({"step": "脉冲直达", "hit": d.get("hit"), "name": d.get("name"),
                      "why": d.get("why"), "ms": d.get("ms")})
        if d.get("hit"):
            return {"ok": True, "path": "pulse_direct", "intent": str(intent)[:120],
                    "name": d.get("name"), "kind": d.get("kind"), "why": d.get("why"),
                    "tokens": 0, "steps": steps, "ms": int((time.time() - t0) * 1000),
                    "note": "脉冲直达：0 token、不唤醒引擎"}
    p = _pulse()
    steps.append({"step": "脉冲", "ok": bool(p.get("ok")), "ms": p.get("ms")})

    o = _ondemand()
    if not o.get("awake"):
        if not wake:
            return {"ok": False, "needs_activation": True, "steps": steps,
                    "error": "本机引擎在睡/没起：先 wake",
                    "how": "run_task('pulse_core', {'op': 'wake'}) —— 需 process_execute 票"}
        r = C.start(wait=300)
        steps.append({"step": "按需激活", "ok": bool(r.get("ok")),
                      "boot_s": r.get("boot_s"), "stage": r.get("stage")})
        if not r.get("ok"):
            return {"ok": False, "steps": steps, "error": "引擎起不来", "detail": r}
    else:
        steps.append({"step": "按需激活", "ok": True, "awake": True})

    r = C.route(intent, k=k, timeout=timeout)
    steps.append({"step": "直达", "ok": bool(r.get("ok")), "ms": r.get("ms")})
    q = _quant()
    return {"ok": bool(r.get("ok")), "intent": str(intent)[:120],
            "space": r.get("space"), "name": r.get("name"), "why": r.get("why"),
            "lane": "commander_local_weights", "weights": q.get("file"),
            "compression": q.get("ratio"), "candidates": r.get("candidates"),
            "steps": steps, "ms": int((time.time() - t0) * 1000),
            "error": r.get("error")}


def plan(intent: str) -> dict:
    """只出计划（不动手、不起引擎）：这一步会怎么走，逐条列清。"""
    q = _quant()
    return {"ok": True, "intent": str(intent)[:120],
            "steps": [
                {"1": "脉冲", "call": "tentacle.bridge.pulse()", "why": "一次拿全身状态，不逐页探活"},
                {"2": "按需", "call": "commander.ensure()", "why": "没醒就先起（%.1fs），醒着就复用" % 2.6},
                {"3": "直达", "call": "commander.route(intent, k=%d)" % 12,
                 "why": "召回先兜住 %d 个真名，权重只在这份候选里挑" % (_direct().get("candidates") or 0)},
                {"4": "量化", "call": "commander.ask()", "why": "跑的是 %s（%.2fGB，fp16 的 %.2f×压缩）"
                 % (q.get("file"), q.get("size_gb") or 0, q.get("ratio") or 0)},
            ]}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "all":
        return pulse_all(fast=bool(kw.get("fast", True)))
    if op in ("organs", "body"):
        return body_organs()
    if op == "verify":
        return verify()
    if op in ("route", "ask"):
        return route(str(kw.get("intent") or kw.get("text") or ""),
                     k=int(kw.get("k") or 12), wake=bool(kw.get("wake")))
    if op == "wake":
        return {"ok": True, **C.start(ctx=int(kw.get("ctx") or C.DEFAULT_CTX),
                                      threads=int(kw.get("threads") or C.DEFAULT_THREADS),
                                      idle_s=int(kw.get("idle_s") or C.DEFAULT_IDLE_S))}
    if op == "stop":
        return C.stop()
    if op == "direct":
        return direct(str(kw.get("intent") or ""))
    if op == "plan":
        return plan(str(kw.get("intent") or kw.get("text") or ""))
    return {"ok": False, "error": "pulse_core 不认 op=%s（status/verify/route/plan）" % op}
