"""GBT小土豆V8 · 大脑执行层（brain_exec）——五维合一的统一调度头。

复活自 V7 execution_router（archived_logs/.../brain/execution_router.py），
V8 化：不再走子代理，全部落在万能插 + 触手 + 统一接口的纪律上。

五维合一（Owner 原设计）：
  route    意图 → 能力动态路由（语义匹配注册表 + 兜底建议）
  execute  并行执行（万能插 DAG——大脑的手）
  verify   触手肉眼验证（domain_* 五维穿透——用眼睛确认执行结果）
  health   执行层自检评分（五维各自健康度）
  unify    五维合一总入口：一次调用 = route → execute → verify → health 全链

操作五维（触手的 UIA 穿透，无视遮挡）：
  domain_index  索引（窗口/控件树）
  domain_read   读（窗口内容）
  domain_type   写（输入文本）
  domain_act    动作（点击等，含坐标兜底）
  + 视觉（vision_bus 全屏帧）——先看再动的"看"
"""
import contextlib
import functools
import json
import time

from .store import audit


# ═══════════════ 进出成对事件（span）· 2026-09-22 ═══════════════
# 为什么必须加：`audit.jsonl` 原来**每次调用只落一行结果**（ok/error/denied），
# **没有"进入"信号**。于是可视化里「**忙**」和「**卡**」两个状态**永远点不亮**
# —— 拿不到"开始"就无从判断"是不是还在跑"。这不是画得不好，是**数据里根本没有**。
#
# 现在每个维进出各一条事件：
#     进了没出        ⇒ 忙（真在跑）
#     进了超时还没出   ⇒ 卡（真卡住，不是猜）
#     出了            ⇒ 成 / 败（带真实耗时 ms）
#
# 用**装饰器**加而不是在每个函数体里塞 with：一行一个，不碰原函数缩进，
# 改动面最小、最不容易弄坏既有逻辑。嵌套调用（unify 调四维）会自然形成
# 真实的嵌套 span —— 跟专业 tracer 一样。
@contextlib.contextmanager
def span(dim: str, **meta):
    """进出成对。**异常也一定落 exit**（否则崩一次就永远"卡"着，成了假信号）。"""
    t0 = time.time()
    audit("brain_enter", {"dim": dim, **{k: str(v)[:60] for k, v in meta.items()}})
    try:
        yield
    except BaseException as e:                                      # noqa: BLE001
        audit("brain_exit", {"dim": dim, "ok": False,
                             "ms": int((time.time() - t0) * 1000),
                             "error": f"{type(e).__name__}: {str(e)[:80]}"})
        raise
    else:
        audit("brain_exit", {"dim": dim, "ok": True,
                             "ms": int((time.time() - t0) * 1000)})


# 每一维的**最小结果契约**（Owner 2026-09-22「乙」：让她执行时也自检）
# 为什么放在维里而不是要求调用方声明：**调用方会忘**。
# 放这里 ⇒ **五维链上每一维出厂就自带验收**，不依赖外部记得声明。
# 契约故意取得**很宽**（不是业务断言，是"这次到底出没出东西"）：
#   是 dict、非空、至少有一个结果指示字段。业务级断言仍由调用方用 `_verify` 声明。
_CONTRACT_HINTS = ("ok", "status", "result", "kind", "found", "caps", "dims", "reply")


def _contract(dim: str, r) -> list:
    """返回契约违反项（空列表 = 通过）。"""
    probs = []
    if not isinstance(r, dict):
        probs.append(f"返回不是 dict，而是 {type(r).__name__}")
        return probs
    if not r:
        probs.append("返回空 dict（等于什么都没说）")
    elif not any(k in r for k in _CONTRACT_HINTS):
        probs.append("没有任何结果指示字段（ok/status/result/kind/…）"
                     " —— 这种返回读的人没法判断成没成")
    return probs


def _spanned(fn):
    """给维函数套上进出事件 + **结果契约检查**。保留 __name__ / __doc__。"""
    @functools.wraps(fn)
    def _wrap(*a, **kw):
        with span(fn.__name__):
            r = fn(*a, **kw)
        probs = _contract(fn.__name__, r)
        if probs:
            # 不抛、不改返回值 —— 只**如实记账**。
            # 抛异常会把既有调用链弄断；改返回值会骗人。记账最诚实。
            audit("brain_contract_fail", {"dim": fn.__name__, "problems": probs[:3]})
        return r
    return _wrap


class BrainExecError(Exception):
    pass


# ── 维度一：route（意图 → 能力）──

def _heuristic_caps(intent: str) -> list:
    """辅路：**本体能力空间**的词级 + 字符 2-gram 打分（只在主路不可用时启用）。

    2026-09-19（Owner：路由不许三处真相）：打分算法统一走 `semantic_route.grams`，
    本文件不再自带 `_grams` 副本；本函数只负责"能力空间"这一张表。
    """
    from .caps_registry import BENIGN_CAPS
    from .semantic_route import grams
    words = set(str(intent).lower().split()) | grams(intent)
    scored = []
    for name, info in BENIGN_CAPS.items():
        desc = str(info.get("desc", "")) + " " + name + " " + str(info.get("domain", ""))
        dw = set(desc.lower().split()) | grams(name) | grams(str(info.get("desc", ""))[:60])
        hit = len(words & dw)
        if hit:
            scored.append((hit, name, info.get("domain", "?"), info.get("desc", "")[:50]))
    scored.sort(key=lambda row: (-row[0], row[1]))   # 平手按名字定序，结果可复现
    return scored


@_spanned
def route(intent: str) -> dict:
    """意图动态路由 —— 主路 `semantic_route`，辅路本体能力启发式（降级必须自曝）。

    2026-09-19（Owner 拍 A 案）：此前本函数自带一套字符 2-gram，**没接**已建好的主路，
    于是"选哪个能力"在盘上出现了三处口径（本函数 / `tentacle.bridge.route_method` /
    `semantic_route`）。现在改成：

      ① **主路**：`semantic_route.route(intent)`（统一大模型在真实方法表里选，
         带幻觉防护）——它自己会在不可用时降级并把降级原因带回来；
      ② 主路给出的方法若**本身是本体能力** ⇒ 直接用；若是**触手方法** ⇒
         落 `tentacle` 能力并把方法名带在 `best.method`（调用方照此派单，不丢参数）；
      ③ 主路没给出可用方法（未授权 / 断网 / 模型判"清单里没有" / 输出不合法）⇒
         **降级**到本体能力启发式，并在返回值里写明 `path=heuristic`、
         `degraded=True`、`degraded_reason=...` —— **绝不把降级结果冒充主路结果**。

    返回值恒定包含：`ok / intent / best / alternatives / candidates / path / degraded`。
    """
    from .caps_registry import BENIGN_CAPS
    from . import semantic_route as SR
    if not intent:
        raise BrainExecError("需要 intent：任务意图描述")
    t0 = time.time()

    scored = _heuristic_caps(intent)
    top = scored[:5]
    alt = [{"kind": s[1], "domain": s[2]} for s in top[1:]]

    # ── ① 主路：语义路由（不可用时它自己如实降级并带原因回来）──
    main, main_err = None, ""
    try:
        main = SR.route(intent, mode="auto")
    except Exception as exc:  # noqa: BLE001
        main_err = f"{type(exc).__name__}: {exc}"[:160]

    out = {"ok": True, "intent": str(intent)[:120],
           "best": None, "alternatives": alt, "candidates": len(scored),
           "path": "heuristic", "degraded": True,
           "heuristic_best": ({"kind": top[0][1], "domain": top[0][2],
                               "desc": top[0][3]} if top else None),
           "elapsed_ms": 0.0}

    if isinstance(main, dict) and main.get("path") == "semantic" and main.get("ok"):
        method = main.get("method")
        out.update({"path": "semantic", "degraded": False,
                    "semantic": {"method": method, "confidence": main.get("confidence"),
                                 "reason": main.get("reason"),
                                 "provider": main.get("provider"),
                                 "second_opinion": main.get("heuristic_second_opinion")}})
        if method and str(method) in BENIGN_CAPS:
            info = BENIGN_CAPS[str(method)]
            out["best"] = {"kind": str(method), "domain": info.get("domain", "?"),
                           "desc": str(info.get("desc", ""))[:50], "via": "semantic"}
        elif method:
            # 主路选中的是触手方法 —— 仍落在本体能力命名空间（tentacle），方法名带在 method
            out["best"] = {"kind": "tentacle", "method": str(method),
                           "domain": "tentacle",
                           "desc": f"触手方法 {method}", "via": "semantic"}
        else:
            # 主路跑通但判"清单里没有合适的"—— 如实降级到能力启发式
            out.update({"degraded": True, "degraded_reason":
                        "主路判定方法清单里没有合适项（method=null）"})
            out["best"] = out["heuristic_best"]
    else:
        if main is None:
            out["degraded_reason"] = f"主路不可用: {main_err or '未返回结果'}"
        else:
            out["degraded_reason"] = (
                main.get("degraded_reason")
                or main.get("error")
                or ("主路未配置" if main.get("degraded") is None else "主路降级"))
        out["best"] = out["heuristic_best"]

    # ── ③ 降级路上，也要问一次「触手方法」这条本地路由 ──
    # R-H295 · 修根因：降级时只问 `_heuristic_caps`（**能力空间**），而它根本不认识
    # 万能插那 66 个方法。实测后果：`intent="看看现在有哪些窗口"` 被路由到 `cloud_pc`
    # （只因为它的描述里含"独立窗口"二字），备选是 `feishu_embed`（"镶嵌窗口"），
    # 候选一共 2 个 —— 而**真有 `list_windows` 的 `tentacle` 连候选都没进**。
    # 桥里本来就有 `tentacle.bridge.route_method(intent)`：纯本地、零依赖、不需要大模型，
    # 而且它认识的正是方法表。降级时问它一次；它命中就落 `tentacle` + `best.method`，
    # 与主路命中触手方法时的落法**完全一致**（同一命名空间，不新增第二套口径）。
    # 找不到也不硬凑：仍回落能力启发式，并如实写明两条路都没命中。
    if out.get("degraded"):
        try:
            from .tentacle import bridge as _TB
            _tm = _TB.route_method(intent)
            # 形状实测（不要猜）：route_method 返回的键是
            #   ok / best / alternatives / candidates / confident / direction /
            #   direction_why / intent / margin / tie_by_name
            # 方法名在 **best** 里，且 best 本身是个 dict（含 method 与各项打分）——
            # 没有顶层 `method` 键。（我第一版就写成了 `_tm["method"]`，于是条件恒假、
            # 整段静默不生效而没有任何报错。读数先看清形状，别照名字猜。）
            _best = _tm.get("best") if isinstance(_tm, dict) else None
            _hit = _best.get("method") if isinstance(_best, dict) else _best
            if _tm.get("ok") and _hit:
                # ⚠️ **只加字段，不动 `best`** —— `best` 在降级路下的契约是
                # 「本体能力启发式的命中」（`test_brain_route_cn` /
                # `test_brain_route_semantic_null_degrades_loudly` 就是守这一条的）。
                # 我第一版把 `best` 覆盖成触手方法，等于**悄悄改了降级路的契约**，
                # 当场打红两个用例。触手方法的优选交给**触手自己的派单口**
                # （`tentacle.bridge.invoke` 的 auto 分支）去消费这个字段 ——
                # 谁的方法表谁最清楚，分工才对。
                out["tentacle_route"] = {
                    "method": str(_hit), "via": "route_method（本地）",
                    "confident": _tm.get("confident"), "margin": _tm.get("margin"),
                    "direction": _tm.get("direction"),
                    "alternatives": _tm.get("alternatives"),
                    "note": "降级路下顺带问到的触手方法（不覆盖 best，由触手侧决定用不用）",
                }
            else:
                # 没命中就**如实说没命中**，不留一个"看起来跑过"的空档
                out["tentacle_route"] = {"method": None,
                                         "why": "本地方法路由没给出可用方法（不硬凑）",
                                         "candidates": _tm.get("candidates") if isinstance(_tm, dict) else None}
        except Exception as exc:  # noqa: BLE001
            out["tentacle_route_error"] = "%s: %s" % (type(exc).__name__, str(exc)[:100])

    out["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
    return out


# ── 维度二：execute（并行执行——万能插）──

@_spanned
def execute(kind: str = "", payload: dict = None, parallel: list = None,
            intent: str = "") -> dict:
    """执行：单能力直调，或多能力并行（parallel=[{kind,payload},...]——万能插线程池）。

    2026-09-19（Owner：大脑执行层必须协作触手执行任务 / 原生能力默认使用）：
    只给 `intent` 不给 `kind` 时，先过 `route()` 命中最佳能力再执行 ——
    执行层不必先"想我该调哪个"，那是外挂；这里把它变成默认路径。
    派出去的执行仍走 `api.run_task`，触手/本体同一道门，权限与审计照旧。
    """
    from .api import run_task
    t0 = time.time()
    routed = None
    payload = dict(payload or {})
    if not kind and str(intent or "").strip() and not parallel:
        routed = route(intent)
        _best = routed.get("best") or {}
        kind = _best.get("kind") or ""
        if not kind:
            return {"ok": False, "intent": str(intent)[:120], "route": routed,
                    "error": "没有能力命中这条意图（如实报，不猜一个）"}
        # 主路选中触手方法时：方法名随 payload 一起派下去，不丢参数
        if kind == "tentacle" and _best.get("method"):
            payload.setdefault("method", _best["method"])
    if parallel:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(parallel))) as pool:
            futs = {i: pool.submit(run_task, item.get("kind", ""), item.get("payload") or {})
                    for i, item in enumerate(parallel)}
        results = {}
        for i, f in futs.items():
            try:
                results[str(parallel[i].get("kind", i))] = f.result()
            except Exception as e:  # noqa: BLE001
                results[str(parallel[i].get("kind", i))] = {"status": "error", "message": str(e)[:100]}
        return {"ok": all(isinstance(r, dict) and r.get("gbt_result", r).get("status") == "ok"
                          for r in results.values()),
                "parallel": len(parallel), "results": results,
                "elapsed_ms": round((time.time() - t0) * 1000, 1)}
    if not kind:
        raise BrainExecError("需要 kind（或 parallel 列表）")
    r = run_task(kind, payload)
    body = r.get("gbt_result", r) if isinstance(r, dict) else {}
    inner = body.get("result") if isinstance(body.get("result"), dict) else {}
    out = {"ok": body.get("status") == "ok", "kind": kind,
           "status": body.get("status"),
           "result": body.get("result"),
           "elapsed_ms": round((time.time() - t0) * 1000, 1)}
    # 2026-10-21 修（P19 拒绝路径读数最容易被自己省掉）：原来这里只留一个 status=denied，
    # 缺的作用域与上游原话**全丢** ⇒ 调用方（含五维合一的 chain）只能看到"被拒"，
    # 不知道为什么拒、要请人发哪张票。现在把两层（信封 / 本体）的字段都透传上来。
    _miss = (body.get("missing_scopes") or body.get("missing")
             or inner.get("missing_scopes") or inner.get("missing"))
    _why = (body.get("reason") or body.get("error")
            or inner.get("reason") or inner.get("error"))
    if _miss:
        out["missing_scopes"] = _miss
    if _why:
        out["reason"] = str(_why)[:300]
    if routed is not None:
        out["intent"] = str(intent)[:120]
        out["routed_by"] = "brain_exec.route"
        out["route_candidates"] = routed.get("candidates")
        out["route_path"] = routed.get("path")
        out["route_degraded"] = bool(routed.get("degraded"))
    return out


# ── 维度三：verify（触手肉眼验证——先看再动）──

@_spanned
def verify(expectation: str = "", window: str = None) -> dict:
    """用触手的眼睛验证现实：抓全屏帧 + 感知指纹 + （可选）目标窗口内容读回。

    expectation 只是记录预期（供人对照），验证证据是视觉/读回的原始数据。
    """
    from .tentacle import bridge as TB
    from .tentacle import vision_bus as VB
    t0 = time.time()
    checks = {}
    # 1) 视觉证据（全屏帧 + 指纹）
    try:
        eye = TB.get_eye()
        snap = VB.snapshot(eye, ttl=30)
        checks["vision"] = {"ok": bool(snap.get("ok")),
                             "fingerprint": snap.get("fingerprint"),
                             "size": snap.get("size")}
    except Exception as e:  # noqa: BLE001
        checks["vision"] = {"ok": False, "error": str(e)[:80]}
    # 2) 目标窗口读回（domain_read——UIA 穿透）
    if window:
        try:
            r = TB.invoke("domain_read", window)
            checks["window_read"] = {"ok": bool(r.get("ok")),
                                      "sample": str(r)[:200]}
        except Exception as e:  # noqa: BLE001
            checks["window_read"] = {"ok": False, "error": str(e)[:80]}
    ok = all(c.get("ok") for c in checks.values()) if checks else False
    audit("brain_verify", {"ok": ok, "expectation": expectation[:60]})
    return {"ok": ok, "expectation": expectation[:200], "checks": checks,
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}


# ── 维度四：health（执行层自检评分）──

@_spanned
def health() -> dict:
    """五维各自健康度 + 总分（大脑执行层的体检）。"""
    from .api import run_task
    t0 = time.time()
    dims = {}
    # 1) 路由维：注册/路由一致性
    sc = run_task("selfscan", {})
    sc_b = sc.get("gbt_result", {}).get("result", {}) if isinstance(sc, dict) else {}
    # 路由维健康标准：selfscan 能跑通且能力全路由（verdict 是数据态：隔离环境 P0/P1 合理，不算断连）
    _routing_ok = True
    _sec = sc_b.get("sections", {}).get("routing", {})
    if _sec and not _sec.get("ok"):
        _routing_ok = False
    dims["route"] = {"ok": _routing_ok and bool(sc_b.get("capabilities_total")),
                     "detail": f"selfscan={sc_b.get('verdict')}, 路由 {_sec.get('registered', '?')}/{_sec.get('routed', '?')}, 能力 {sc_b.get('capabilities_total')}"}
    # 2) 执行维：万能插健康（引擎可用性）
    try:
        wf = run_task("wf_status", {"limit": 1})
        wf_b = wf.get("gbt_result", {}) if isinstance(wf, dict) else {}
        dims["execute"] = {"ok": wf_b.get("status") == "ok",
                            "detail": f"wf_status ok, 引擎可用"}
    except Exception as e:  # noqa: BLE001
        dims["execute"] = {"ok": False, "detail": str(e)[:60]}
    # 3) 触手维（五维穿透的操作通道）
    try:
        ts = run_task("tentacle_status", {})
        ts_b = ts.get("gbt_result", {}).get("result", {}) if isinstance(ts, dict) else {}
        diag = ts_b.get("diagnose", {})
        dims["tentacle"] = {"ok": bool(diag.get("ok")),
                             "detail": f"eye_error={diag.get('eye_error')}"}
    except Exception as e:  # noqa: BLE001
        dims["tentacle"] = {"ok": False, "detail": str(e)[:60]}
    # 4) 视觉维
    try:
        from .tentacle import bridge as TB
        dims["vision"] = {"ok": TB.eye_ready(), "detail": "eye_ready" if TB.eye_ready() else str(TB.eye_error())[:60]}
    except Exception as e:  # noqa: BLE001
        dims["vision"] = {"ok": False, "detail": str(e)[:60]}
    # 5) 审计维
    try:
        from .store import log_count
        dims["audit"] = {"ok": log_count() >= 0, "detail": f"审计 {log_count()} 条"}
    except Exception as e:  # noqa: BLE001
        dims["audit"] = {"ok": False, "detail": str(e)[:60]}

    ok_count = sum(1 for d in dims.values() if d.get("ok"))
    score = round(ok_count / len(dims) * 100, 1) if dims else 0
    return {"ok": ok_count == len(dims), "score": score,
            "healthy_dims": ok_count, "total_dims": len(dims),
            "dims": dims,
            "elapsed_ms": round((time.time() - t0) * 1000, 1)}


# ── 维度五：unify（五维合一总入口）──

@_spanned
def unify(goal: str, payload: dict = None, expectation: str = "") -> dict:
    """五维合一：route → execute → verify → health 一次跑完（大脑执行层全链）。

    goal 用于路由（自动找能力）；也可直接传 kind（payload 里）跳过路由。
    """
    if not goal and not (payload or {}).get("kind"):
        raise BrainExecError("需要 goal（意图）或 payload.kind（指定能力）")
    t0 = time.time()
    chain = {}

    # 1) 路由
    rt = route(goal)
    chain["route"] = {"best": rt.get("best"), "candidates": rt.get("candidates"),
                      "path": rt.get("path"), "degraded": bool(rt.get("degraded")),
                      "degraded_reason": rt.get("degraded_reason")}

    # 2) 执行（goal 路由出的最佳能力，或显式 kind）
    p = payload or {}
    _best = rt.get("best") or {}
    kind = p.get("kind") or _best.get("kind")
    if not kind:
        return {"ok": False, "error": "路由无候选且未指定 kind", "chain": chain}
    _pl = {k: v for k, v in p.items() if k != "kind"}
    if kind == "tentacle" and _best.get("method"):
        _pl.setdefault("method", _best["method"])
    ex = execute(kind, _pl)
    chain["execute"] = {"kind": kind, "ok": ex.get("ok"), "status": ex.get("status"),
                        "missing_scopes": ex.get("missing_scopes"),
                        "reason": ex.get("reason")}

    # 3) 验证（触手肉眼）
    vf = verify(expectation or f"执行 {kind} 后的现实状态")
    chain["verify"] = {"ok": vf.get("ok"),
                        "checks": {k: v.get("ok") for k, v in vf.get("checks", {}).items()}}

    # 4) 健康
    hl = health()
    chain["health"] = {"score": hl.get("score"), "healthy": f"{hl.get('healthy_dims')}/{hl.get('total_dims')}"}

    ok = ex.get("ok")
    audit("brain_unify", {"goal": goal[:80], "kind": kind, "execute_ok": ok,
                           "health": hl.get("score")})
    return {"ok": ok, "goal": goal[:200], "kind": kind, "chain": chain,
            "elapsed_s": round(time.time() - t0, 1),
            "note": "五维合一：route→execute→verify→health 全链留痕"}


# ═══════════════ 第六维：heartbeat（12 根分类心跳触手的接收口）· 2026-10-30 ═══════════════
# 主人令：「每一个分类部署一根心跳触手…状态返回给大脑执行层分析，再返回执行指令」。
# 分工写死在注释里，免得以后有人把分析塞回触手：
#   触手只管**自检和报状态**（heartbeat_tentacle），不许自己下结论；
#   分析、定级、出指令**只在本文件**（大脑执行层），触手不越界。


@_spanned
def heartbeat(mode: str = "light", persist: bool = True) -> dict:
    """收 12 根分类心跳触手的定点自检状态（大脑执行层的"体检台"）。

    mode:
      light（默认）只跑快探针，全套 12 根实测约 0.3 秒 —— 这是心跳该有的节奏；
      full 加上 `body_map` 全身扫描（七感官六动作逐根回读，约 6.5 秒）。
    返回里**不含**每根触手的 349 条成员清单（那会淹掉读数），成员数单独给。
    """
    from . import heartbeat_tentacle as HB

    rep = HB.scan_all(mode=mode, persist=persist)
    brief = {}
    for code, s in (rep.get("statuses") or {}).items():
        brief[code] = {
            "tentacle": s.get("tentacle"),
            "title": s.get("title"),
            "ok": s.get("ok"),
            "score": s.get("score"),
            "members": s.get("members_total"),
            "beat": s.get("beat"),
            "at": s.get("at"),
            "ms": s.get("ms"),
            "checks": {k: (v or {}).get("ok") for k, v in (s.get("checks") or {}).items()},
            "probe_detail": ((s.get("checks") or {}).get("probe") or {}).get("detail"),
            "hygiene_detail": ((s.get("checks") or {}).get("hygiene") or {}).get("detail"),
            "signals": s.get("signals"),
        }
    return {
        "ok": rep.get("tentacles_red", 1) == 0,
        "at": rep.get("at"),
        "mode": rep.get("mode"),
        "score": rep.get("score"),
        "tentacles_total": rep.get("tentacles_total"),
        "tentacles_ok": rep.get("tentacles_ok"),
        "tentacles_red": rep.get("tentacles_red"),
        "taxonomy": rep.get("taxonomy"),
        "signals_by_level": rep.get("signals_by_level"),
        "tentacles": brief,
        "elapsed_ms": rep.get("ms"),
        "note": "触手只报状态；定级与指令在 advise()",
    }


# 信号码 → 执行指令模板（只在这里定义一次，避免两处口径）
_ADVICE_RULES: dict = {
    "tentacle_crash": ("P0", "这根触手自身崩了，先修它自己 —— 它崩着就等于这个分类没人看"),
    "registry_gap": ("P0", "分类表与真源对不上，先对齐分类表（caps_registry 为唯一真源）"),
    "dispatch_gap": ("P0", "有能力的 handler 不在分派表内 —— 登记了却调不到，等于假绿"),
    "dispatch_unreadable": ("P0", "分派表解析失败 —— 心跳的判据本身失明，先修解析"),
    "policy_break": ("P0", "策略门对某些能力位抛异常 —— 门坏了，任何放行结论都不可信"),
    "probe_dead": ("P1", "该分类的器官探针报红 —— 这个器官当下不能用，改走邻类路径"),
    "members_removed": ("P1", "成员消失 —— 不是正常下线就是被误删，必须逐个核对"),
    "state_flip": ("P1", "状态翻转 —— 上一跳与这一跳结论相反，先确认哪一次是对的"),
    # ── 卫生层（主人令 2026-10-30 追加：触手自检要会清垃圾、整理自身、防混入）──
    "foreign_intrusion": ("P1", "抽屉里有不是我们产的件 —— 只报不删（别人的东西不由触手处置），要么人认领要么人清走"),
    "misplaced_state": ("P1", "状态文件被写脏（category 与文件名不符）—— 说明有别的进程在写我们的格，先查谁写的"),
    "garbage_found": ("P2", "抽屉里有垃圾/超额扫描件 —— 跑 `scan --clean` 就清（默认 dry-run 不删，删除属写面）"),
    "garbage_cleaned": ("P2", "垃圾已清（信息态）"),
    # 落盘失败是 P0：状态没写进去，后面所有读数（含 act 的重定级）都在读旧账。
    "persist_failed": ("P0", "心跳写不进盘 —— 状态没落盘，读数与重定级全部基于旧数据，先修写权限/磁盘"),
    "hygiene_error": ("P1", "卫生层清理时出错 —— 该删没删或该留没留，逐条看 errors"),
}

# 根因是**全局**的信号码：它们的病根不在某个分类，而在共享的那一层。
# 12 根会各报一次同一条，必须合成一条并列出受影响分类 —— 否则一个磁盘写不进
# 就被念成 12 个问题，真正的病灶反而被淹掉。
_SYSTEMIC_CODES: frozenset = frozenset({
    "persist_failed", "dispatch_unreadable", "taxonomy_broken",
})


@_spanned
def advise(report: dict = None, mode: str = "light") -> dict:
    """大脑执行层：把触手状态**分析**成**执行指令**（带优先级、依据、证据）。

    这是主人令里「返回执行指令」那一步。判据不新造，全部落在 `_ADVICE_RULES`
    与分类自校验上 —— 新加一类问题就要先在规则表里加一行，不许临场发挥。

    规格：
      · P0 = 现在就不许用（假绿 / 门坏 / 触手崩 / 状态写不进盘）→ 必须先修，修完再谈别的
      · P1 = 这个分类当下降级（器官失灵 / 成员消失 / 状态翻转）→ 改道或复检
      · P2 = 可做可不做的整理（清垃圾）→ 在 instructions 里，因为它是**动作**
      · INFO = 纯信息（探针被档位跳过等）→ 进 `notes`，**不进 instructions**
        （2026-10-30 打磨：原来 INFO 也塞成 P2 指令，每跳稳定多一条无依据的噪音）
      · 全绿 ⇒ instructions 为空，verdict=green
    """
    from . import heartbeat_tentacle as HB

    rep = report or HB.scan_all(mode=mode, persist=True)
    tax = rep.get("taxonomy") or {}
    instructions = []

    # ⓪ 分类自校验不通过 ⇒ 一切读数都不作数，这是最上游的 P0
    if not tax.get("ok", True):
        instructions.append({
            "priority": "P0", "id": "taxonomy_broken",
            "action": "先修分类表：有未归类/重复归类/孤儿 domain/未映射动作域",
            "why": "分类一旦不严格，12 根触手看的就不是全集 —— 后面的绿都是假绿",
            "evidence": {k: tax.get(k) for k in
                         ("unclassified", "duplicated", "orphan_domains",
                          "unmapped_action_domains", "source_total", "classified_total")},
        })

    # ① 逐条信号 → 指令
    # 🔴 2026-10-30 打磨：INFO 原来被塞成一条 P2 指令（"无需动作（信息态）"），
    #    而且连 signal_code 都没带 ⇒ 每跳都稳定多一条既无依据又不可追溯的噪音，
    #    真问题就被淹在里面。现在 INFO 走独立的 notes，不进 instructions。
    seen = set()
    notes = []
    for s in rep.get("signals") or []:
        code = s.get("code")
        level = s.get("level")
        if level == "INFO":
            notes.append({"code": code, "category": s.get("category"),
                          "msg": s.get("msg")})
            continue
        rule = _ADVICE_RULES.get(code)
        prio = rule[0] if rule else ("P0" if level == "P0" else "P1")
        hint = rule[1] if rule else "未登记的信号码 —— 先补 _ADVICE_RULES 再谈处置"
        # 全局根因：按 code 去重并把受影响分类汇总，不按分类各开一张单
        systemic = code in _SYSTEMIC_CODES
        key = (prio, code) if systemic else (prio, code, s.get("category"))
        if key in seen:
            # 已有一张单：把这条分类补进 affected，而不是再开一张
            if systemic:
                for x in instructions:
                    if x.get("evidence", {}).get("signal_code") == code:
                        aff = x.setdefault("affected", [])
                        _c = s.get("category")
                        if _c not in aff:      # 汇总层用值日根名义也会报一次，别重复计
                            aff.append(_c)
                        break
            continue
        seen.add(key)
        ins = {
            "priority": prio,
            "id": code if systemic else f"{s.get('category')}:{code}",
            "category": s.get("category"),
            "tentacle": s.get("tentacle"),
            "action": hint,
            "why": s.get("msg"),
            "evidence": {"signal_code": code, "level": level},
        }
        if systemic:
            ins["affected"] = [s.get("category")]
            ins["root_cause_scope"] = "全局（不是某个分类的问题，别按类各修一遍）"
        instructions.append(ins)

    # ② 按优先级排序：P0 先，P1 次，P2 后；同级别按分类顺序（稳定可复现）
    order = {"P0": 0, "P1": 1, "P2": 2}
    instructions.sort(key=lambda x: (order.get(x["priority"], 9), str(x.get("id"))))

    p0 = [x for x in instructions if x["priority"] == "P0"]
    p1 = [x for x in instructions if x["priority"] == "P1"]

    if p0:
        verdict, headline = "red", f"先修 {len(p0)} 条 P0：现在有假绿，任何「能跑」的结论都不作数"
    elif p1:
        verdict, headline = "yellow", f"{len(p1)} 条 P1：系统整体在，但有分类降级，改道或复检"
    elif not tax.get("ok", True):
        verdict, headline = "red", "分类表不严格，读数不可信"
    else:
        verdict, headline = "green", "12 根全绿，分类严格自校验通过 —— 维持，按需执行"

    audit("brain_advise", {"verdict": verdict, "p0": len(p0), "p1": len(p1),
                           "score": rep.get("score")})

    return {
        "ok": verdict == "green",
        "verdict": verdict,
        "headline": headline,
        "score": rep.get("score"),
        "tentacles_ok": rep.get("tentacles_ok"),
        "tentacles_total": rep.get("tentacles_total"),
        "taxonomy_ok": tax.get("ok"),
        "instructions": instructions,
        "notes": notes,
        "counts": {"P0": len(p0), "P1": len(p1),
                   "P2": len([x for x in instructions if x["priority"] == "P2"])},
        "mode": rep.get("mode"),
        "at": rep.get("at"),
        "note": "指令由 brain_exec 出；触手只报状态，不越界下结论",
    }


# ── 指令 → 执行（把闭环合上：只有清单没有动作，链条就断在最后一米）──
# 哪些能自动干，写死在表里；**表外的一律不自动**。
# 判据只有一条：这个动作**出错时只伤自己的抽屉**，才配自动。
#   · 清垃圾 —— 只删 state/heartbeat/ 里自己的 tmp/pyc/超额扫描 ⇒ 可自动
#   · 复检   —— 只是重打一跳读一次 ⇒ 可自动
#   · 登记缺/分派缺/策略抛/成员消失 —— 要改代码或改分类表 ⇒ **必须人来做**
_AUTO_ACTIONS: dict = {
    "garbage_found": {"op": "heartbeat_clean",
                      "why": "只在心跳自己的抽屉里清垃圾与超额扫描，不碰任何用户内容"},
    "state_flip": {"op": "heartbeat_recheck",
                   "why": "重打一跳确认哪次读数对（只读，无副作用）"},
}


@_spanned
def act(report: dict = None, mode: str = "light", dry_run: bool = False) -> dict:
    """把 advise() 里**可自动**的指令真的执行掉，然后重新定级 —— 闭环的最后一米。

    为什么不全部自动：P0 那几条（登记缺/分派缺/策略抛/成员消失）都要改代码或改分类表，
    自动改等于让系统自己给自己签字。**能自动的只有"出错只伤自己抽屉"的动作**（见
    `_AUTO_ACTIONS`），表外一律跳过并写明为什么跳过。

    返回 before/after 两次定级，让"执行完到底有没有变好"是可对照的，不是感觉。
    """
    from . import heartbeat_tentacle as HB

    adv = advise(report, mode=mode)
    executed, skipped = [], []

    for ins in adv.get("instructions") or []:
        code = (ins.get("evidence") or {}).get("signal_code")
        auto = _AUTO_ACTIONS.get(code)
        if not auto:
            skipped.append({"id": ins.get("id"), "priority": ins.get("priority"),
                            "why": "不在 _AUTO_ACTIONS 表内 —— 要改代码或改分类表，留给人",
                            "action": ins.get("action")})
            continue
        if dry_run:
            skipped.append({"id": ins.get("id"), "priority": ins.get("priority"),
                            "why": "dry_run=True，只演练不执行", "would": auto["op"]})
            continue
        try:
            if auto["op"] == "heartbeat_clean":
                HB.scan_all(mode=mode, persist=True, clean=True)
            elif auto["op"] == "heartbeat_recheck":
                HB.scan_all(mode=mode, persist=True)
            executed.append({"id": ins.get("id"), "op": auto["op"], "ok": True,
                             "note": auto["why"]})
        except Exception as e:  # noqa: BLE001
            executed.append({"id": ins.get("id"), "op": auto["op"], "ok": False,
                             "error": f"{type(e).__name__}: {str(e)[:140]}"})

    # 执行完重新定级（对着刚落的盘读，不是拿旧报告糊弄）
    after = advise(HB.latest(), mode=mode) if executed else {
        "verdict": adv.get("verdict"), "counts": adv.get("counts"),
        "headline": adv.get("headline")}

    audit("brain_act", {"before": adv.get("verdict"), "after": after.get("verdict"),
                        "executed": len(executed), "skipped": len(skipped),
                        "dry_run": bool(dry_run)})

    return {
        "ok": all(x.get("ok") for x in executed) if executed else True,
        "dry_run": bool(dry_run),
        "before": {"verdict": adv.get("verdict"), "counts": adv.get("counts"),
                   "headline": adv.get("headline")},
        "after": {"verdict": after.get("verdict"), "counts": after.get("counts"),
                  "headline": after.get("headline")},
        "improved": (adv.get("verdict") != "green" and after.get("verdict") == "green"),
        "executed": executed,
        "skipped": skipped,
        "note": "只执行 _AUTO_ACTIONS 表内的动作；表外一律留给人",
    }
