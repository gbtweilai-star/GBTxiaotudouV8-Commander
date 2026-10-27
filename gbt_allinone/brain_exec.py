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

    # ── ⓪ 词表路：确定性领域映射（排在语义路之前）──────────────────────────
    # 🔴 2026-10-28：主路要统一大模型；A19 不在时降级到字符 2-gram，
    #   实测把「上下文异常纠正」路由成了 libtv_workflow（视频工作流）——完全不相干。
    #   词表是**人工钉死的领域→能力位映射**，命中即确定，不是降级。
    #   没命中就照原路走，不影响其它意图。
    # ── ⓪-1 自称谓优先（比词表更具体）─────────────────────────────────
    # 实测驱动：能力位名是**英文**（brain_health / model_key_pool），描述全是中文，
    # 位名 token 在描述里一个都不出现 ⇒ "按位名自识别"对这类位完全失效。
    # 但描述里有**中文自称谓**（"大脑执行层·健康维：" 里的"健康维"），
    # 那才是它在文本里的真实身份。实测 4 个错位位 4/4 命中且都对。
    try:
        from .llm import route_lexicon as _LX0
        nh = _LX0.name_hint(intent)
    except Exception:                                         # noqa: BLE001
        nh = {"ok": False}
    if nh.get("ok"):
        b = nh["best"]
        return {"ok": True, "intent": str(intent)[:120],
                "best": {"kind": b["cap"], "domain": b.get("domain") or "self",
                         "desc": "自称谓命中：%s" % b["label"], "via": "self_label"},
                "alternatives": [], "candidates": 1,
                "path": "self_label", "degraded": False,
                "self_label": {"label": b["label"], "weight": b["weight"],
                               "ambiguous": bool(b.get("ambiguous")),
                               "tied": b.get("tied") or []},
                "semantic_skipped": True,
                "heuristic_best": ({"kind": top[0][1], "domain": top[0][2],
                                    "desc": top[0][3]} if top else None),
                "elapsed_ms": round((time.time() - t0) * 1000, 1)}

    try:
        from .llm import route_lexicon as _LX
        lx = _LX.match(intent)
    except Exception:                                         # noqa: BLE001
        lx = {"ok": False, "why": "词表不可用"}
    if lx.get("ok"):
        e = lx["entry"]
        return {"ok": True, "intent": str(intent)[:120],
                "best": {"kind": (e["kinds"] or [""])[0],
                         "domain": "lexicon", "desc": e["reason"][:80],
                         "via": "lexicon"},
                "alternatives": [{"kind": k, "domain": "lexicon"}
                                 for k in e["kinds"][1:]],
                "candidates": len(e["kinds"]), "path": "lexicon",
                "degraded": False,                 # 确定性命中不是降级
                "lexicon": {"id": e["id"], "score": e["score"],
                            "hits": e["hits"], "kinds": e["kinds"],
                            "tools": e.get("tools") or [],
                            "reason": e["reason"]},
                "semantic_skipped": True,
                "heuristic_best": ({"kind": top[0][1], "domain": top[0][2],
                                    "desc": top[0][3]} if top else None),
                "elapsed_ms": round((time.time() - t0) * 1000, 1)}

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
def _probe_reality(expectation: str) -> dict:
    """**非视觉**的现实验证面 —— 给没有交互桌面的机器用。

    2026-10-28 实测驱动：本机是 iSH/Alpine，GDI/DXGI 拿不到屏，
    `verify` 的 vision 检查恒 false ⇒ 整条链的"验证"那一环是空的。
    但"验证现实"不等于"必须看屏幕"：端口通不通、文件在不在、哈希对不对，
    同样是现实，同样可复算。

    只认得出来的面；认不出就如实说"无可验证面"，**绝不假装验过**。
    """
    import hashlib
    import pathlib as _pl
    import re as _re
    import socket
    text = str(expectation or "")
    faces, results = [], {}

    # ① 端口 / URL
    # 允许裸 ":8765"（实测：写"面板后端 :8765 应该在线"时旧正则要求主机前缀，漏掉了）
    for m in _re.finditer(r"(?<![\d:])(?:(?:127\.0\.0\.1|localhost))?:(\d{2,5})\b", text):
        port = int(m.group(1))
        faces.append("port:%d" % port)
        ok = False
        s = socket.socket()
        s.settimeout(2.0)
        try:
            s.connect(("127.0.0.1", port))
            ok = True
        except OSError:
            ok = False
        finally:
            s.close()
        results["port:%d" % port] = {"ok": ok, "kind": "tcp"}

    # ② 文件路径（相对仓库根）
    root = _pl.Path(__file__).resolve().parents[1]
    for m in _re.finditer(r"([\w./-]+\.(?:py|json|html|md|js|txt))", text):
        rel = m.group(1)
        fp = (root / rel)
        if not fp.exists():
            fp2 = _pl.Path(rel)
            fp = fp2 if fp2.exists() else fp
        faces.append("file:" + rel)
        if fp.is_file():
            h = hashlib.sha256(fp.read_bytes()).hexdigest()[:12]
            results["file:" + rel] = {"ok": True, "kind": "file",
                                      "bytes": fp.stat().st_size, "sha12": h}
        else:
            results["file:" + rel] = {"ok": False, "kind": "file",
                                      "why": "不存在"}

    if not faces:
        return {"ok": False, "reason": "无可验证面（expectation 里没有端口/文件）",
                "faces": [], "results": {}}
    ok = all(v["ok"] for v in results.values())
    return {"ok": ok, "faces": faces, "results": results,
            "reason": "" if ok else "有面没过"}


def verify(expectation: str = "", window: str = None) -> dict:
    """验证现实。视觉优先，**没有桌面就走非视觉面**。

    🔴 2026-10-28 改：原来只有 vision 一条检查，而本机（iSH/Alpine）
       GDI/DXGI 拿不到屏 ⇒ checks 里只有一个 False ⇒ ok 恒 false，
       整条链的"验证"永远是空的。
       现在两条面并存：
         vision  —— 有桌面才算数；拿不到就标 available=false 且 counted=false
         reality —— 端口/文件，无桌面也能算
       只要 reality 有面且全过 ⇒ verdict=verified；
       一条面都没有 ⇒ verdict=unverified_no_surface（**不假装验过**）。
    """
    from .tentacle import bridge as TB
    from .tentacle import vision_bus as VB
    t0 = time.time()
    checks = {}

    # 1) 视觉证据（拿不到屏要如实标，且**不计入判定**）
    try:
        eye = TB.get_eye()
        snap = VB.snapshot(eye, ttl=30)
        ok_v = bool(snap.get("ok"))
        checks["vision"] = {"ok": ok_v, "counted": ok_v,
                            "available": True,
                            "fingerprint": snap.get("fingerprint"),
                            "size": snap.get("size")}
    except Exception as e:                                    # noqa: BLE001
        checks["vision"] = {"ok": False, "counted": False, "available": False,
                            "error": str(e)[:80],
                            "note": "无交互桌面（拿不到屏）—— 本机正常状态，不计入判定"}

    # 2) 目标窗口读回（UIA 穿透，Windows）
    if window:
        try:
            r = TB.invoke("domain_read", window)
            checks["window_read"] = {"ok": bool(r.get("ok")),
                                     "counted": bool(r.get("ok")),
                                     "sample": str(r)[:200]}
        except Exception as e:                                # noqa: BLE001
            checks["window_read"] = {"ok": False, "counted": False,
                                     "available": False, "error": str(e)[:80]}

    # 3) 非视觉现实面（端口 / 文件）—— 本机的主力
    rl = _probe_reality(expectation)
    checks["reality"] = {**rl, "counted": bool(rl.get("faces"))}

    counted = [c for c in checks.values() if c.get("counted")]
    if not counted:
        verdict, ok = "unverified_no_surface", False
    else:
        ok = all(c.get("ok") for c in counted)
        verdict = "verified" if ok else "failed"

    audit("brain_verify", {"ok": ok, "verdict": verdict,
                           "expectation": expectation[:60]})
    return {"ok": ok, "verdict": verdict,
            "expectation": expectation[:200], "checks": checks,
            "counted_faces": [k for k, v in checks.items() if v.get("counted")],
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
    # 🔴 2026-10-28：原来只透传 ok 与"每条检查的 ok"，把 verdict / 计入的面
    #   全丢了 ⇒ 上层只看到 vision:False，分不清"验失败"还是"根本没面可验"。
    chain["verify"] = {"ok": vf.get("ok"),
                        "verdict": vf.get("verdict"),
                        "counted_faces": vf.get("counted_faces") or [],
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
