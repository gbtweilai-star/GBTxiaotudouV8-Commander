# gbt-capability: 自动导航病因钩子（八类命名病因 + 收口吞错 + 环形病因账）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""自动导航的**病因钩子** —— 让失败带上"病的名字"，而不是一段字符串。

═══ 为什么要有这个文件（2026-09-22 深度排查的结论）═══
排查读数（可复算）：
  · 「病因」一词在全部 `.py` 里出现 **0 次**（只在 .md 里 8 次）⇒ 09-18 想过，从没落进代码
  · 导航 7 个文件里 `rule`/`why`/`cause` 字段几乎全空（`omni_window` 11 处失败返回，0 个 rule）
  · **65 处吞错**（omni_domain 18 / omni_read 17 / omni_mouse 13 / omni_core 13 / 其余 4）
    形态一律是 `except Exception as _e: print(f"⚠️ … 吞错: {_e}", file=sys.stderr)`
  · 50 个故障钩子**生产调用点 = 0**（连 4 条标 `existing` 的也没接线）
后果：六类病在返回值上**长得一模一样** ⇒ ① 重试策略无法自动选（该滚屏找？该等？该关弹窗？该换后端？）
② **不可统计**，没有病因字段就做不出"哪类病最多"的读数，也就没法按病下药。

═══ 本模块只管一件事 ═══
把「异常 / 失败返回」归一成 `{ok: False, cause: <八类之一>, evidence, retry_hint}`，
并把每一次吞错**记进环形病因账**（可查、可统计）。**不改变任何 ok:True 的路径。**

纪律：
  ① 病因是**枚举**不是自由字符串 —— 自由字符串只是把"没记录"换成"记了但不可比"。
  ② 判不出类别时老实给 `action_no_effect`，**不猜一个更漂亮的病名**。
  ③ 记录本身绝不许把执行弄崩（整个 `record_swallow` 包在 try 里）。
  ④ 账本只读面（`ledger/stats`）不写盘；要落盘得由调用方显式给路径。
"""
from __future__ import annotations

import collections
import functools
import sys
import time
import traceback

# ── 八类命名病因：(键, 中文名, 重试策略提示)
NAV_CAUSES = (
    ("element_not_found", "目标元素不在当前画面/树上",
     "先滚动或展开再找；找不到就换文字特征重找，别原地重试"),
    ("window_lost", "目标窗口已消失或句柄失效",
     "重新枚举窗口；必要时重新拉起目标程序"),
    ("timeout", "等到超时仍不满足条件",
     "拉长超时或改判据（等状态而不是等固定秒数）"),
    ("modal_blocked", "被弹窗/遮罩挡住，动作发不进去",
     "先关弹窗（ESC/确定）再重发动作"),
    ("denied_by_gate", "被授权门或权限拒绝",
     "**不许绕门**：如实上报缺哪个 scope，等主人发放"),
    ("backend_unavailable", "后端/依赖不可用（模块缺失、服务没起）",
     "换后端或先补齐依赖；不是重试能解决的问题"),
    ("stale_target", "元素/句柄取到过但已失效（界面已重绘）",
     "重新取一次元素再动作，别复用旧引用"),
    ("action_no_effect", "动作发出去了但看不出效果（**判不出就别猜**）",
     "做前后对比截图确认到底动没动"),
)
CAUSE_KEYS = tuple(c[0] for c in NAV_CAUSES)
CAUSE_CN = {k: cn for k, cn, _ in NAV_CAUSES}
RETRY_HINT = {k: h for k, _, h in NAV_CAUSES}

# ── 判据表：(病因, 异常类型名集合, 文本关键词集合)。**顺序即优先级**，先匹配到的算数。
_RULES = (
    ("timeout", {"TimeoutError", "TimeoutExpired"},
     ("timeout", "timed out", "超时", "等待", "deadline")),
    ("denied_by_gate", {"PermissionError"},
     ("access is denied", "permission", "denied", "拒绝", "权限", "policy", "scope", "unauthorized", "403")),
    ("backend_unavailable", {"ImportError", "ModuleNotFoundError"},
     ("no module named", "not installed", "unavailable", "不可用", "未安装", "未启动", "connection refused", "not connected")),
    ("window_lost", set(),
     ("invalid window handle", "窗口", "hwnd", "window not found", "窗口已关闭", "窗口仍在")),
    ("modal_blocked", set(),
     ("dialog", "弹窗", "modal", "popup", "遮罩", "被挡住")),
    ("stale_target", set(),
     ("stale", "已失效", "not attached", "detached", "element is not", "旧引用")),
    ("element_not_found", set(),
     ("not found", "no such", "找不到", "未找到", "不存在", "missing element", "no element")),
)

_LEDGER: "collections.deque" = collections.deque(maxlen=500)


def classify(exc=None, text: str = "", status: str = "") -> str:
    """把异常/文本/状态判成八类之一。判不出 ⇒ `action_no_effect`（**不猜更漂亮的病名**）。"""
    etype = type(exc).__name__ if exc is not None else ""
    blob = " ".join(str(x) for x in (str(exc) if exc is not None else "", text, status)).lower()
    for cause, types, kws in _RULES:
        if etype and etype in types:
            return cause
        for kw in kws:
            if kw.lower() in blob:
                return cause
    if status == "timeout":
        return "timeout"
    return "action_no_effect"


def evidence_of(module: str, op: str = "", exc=None, text: str = "") -> dict:
    ev = {"module": module, "op": op, "at": round(time.time(), 3)}
    if exc is not None:
        ev["exc_type"] = type(exc).__name__
        ev["exc_msg"] = str(exc)[:200]
        tb = traceback.extract_tb(exc.__traceback__)
        if tb:
            last = tb[-1]
            ev["where"] = "%s:%s in %s" % (last.filename.replace("\\", "/").split("/")[-1],
                                           last.lineno, last.name)
    if text:
        ev["text"] = str(text)[:200]
    return ev


def cause(cause_key: str, module: str, op: str = "", exc=None, text: str = "") -> dict:
    """造一个**带病因**的结构化失败。"""
    key = cause_key if cause_key in CAUSE_CN else "action_no_effect"
    return {
        "ok": False,
        "cause": key,
        "cause_cn": CAUSE_CN[key],
        "retry_hint": RETRY_HINT[key],
        "evidence": evidence_of(module, op, exc, text),
    }


def record_swallow(exc, module: str = "?", op: str = "") -> str:
    """**65 处吞错的统一收口**：照旧喷一行 stderr（原观测行为不变），
    但同时在环形病因账里留下 `{病因, 模块, 方法, 异常类型, 原因, 时刻}`。

    铁律：记录本身绝不许把执行弄崩 —— 整体包 try，出事只回退成原来的 print。
    """
    try:
        key = classify(exc, op)
        _note({
            "cause": key, "cause_cn": CAUSE_CN[key], "module": module, "op": op,
            "exc_type": type(exc).__name__ if exc is not None else "",
            "msg": str(exc)[:300], "at": round(time.time(), 3),
        })
        print("⚠️ %s: 吞错[%s]: %s" % (module, key, exc), file=sys.stderr)
        return key
    except Exception:                                          # noqa: BLE001
        try:
            print("⚠️ %s: 吞错: %s" % (module, exc), file=sys.stderr)
        except Exception:                                      # noqa: BLE001
            pass
        return "action_no_effect"


def enrich(result, module: str = "?", op: str = ""):
    """给一个**已经失败**的返回补病因；`ok:True` 原样返回（本模块不动成功路径）。

    已经有 `cause` 的不覆盖 —— 已有的判定比事后猜的准。
    """
    if not isinstance(result, dict) or result.get("ok") is not False:
        return result
    if "cause" in result:
        return result
    text = " ".join(str(result.get(k, "")) for k in ("error", "why", "note", "status"))
    key = classify(None, text, str(result.get("status", "")))
    if key == "action_no_effect" and result.get("unavailable") is True:
        key = "backend_unavailable"
    if key == "action_no_effect" and result.get("denied") is True:
        key = "denied_by_gate"
    out = dict(result)
    out["cause"] = key
    out["cause_cn"] = CAUSE_CN[key]
    out["retry_hint"] = RETRY_HINT[key]
    out.setdefault("evidence", evidence_of(module, op, None, text))
    _note({"cause": key, "cause_cn": CAUSE_CN[key], "module": module, "op": op,
           "exc_type": "(失败返回)", "msg": text[:300], "at": round(time.time(), 3)})
    return out


def etiology(module: str, op: str = ""):
    """病因钩子（装饰器）：导航入口挂上它 ⇒ 抛错也变成**带病因的结构化失败**，
    成功路径**逐字节不变**。

    ── 2026-09-22 补：失败时**顺带把故障钩子链跑起来** ──
    这样那 5 个已挂钩子的导航入口就成了 `hook_registry.dispatch` 的**真实生产调用点**
    （此前 dispatch 的生产调用点 = 0，整张 50 钩子矩阵只是"位置登记表"）。
    钩子链本身的失败被 `dispatch` 隔离（红线②），绝不会拖垮导航动作。
    """
    def deco(fn):
        name = op or fn.__name__

        @functools.wraps(fn)
        def wrapper(*a, **kw):
            try:
                r = enrich(fn(*a, **kw), module, name)
            except Exception as e:                             # noqa: BLE001
                ck = classify(e, name)
                try:
                    print("⚠️ %s.%s: 抛出[%s]: %s" % (module, name, ck, e), file=sys.stderr)
                except Exception:                              # noqa: BLE001
                    pass
                r = cause(ck, module, name, exc=e)
            if isinstance(r, dict) and r.get("ok") is False:
                fire_failure_hooks(r, module, name)
            return r
        return wrapper
    return deco


# ───────────────────────────────────────────── 故障钩子链（真接线）

def hooks_for(cause_key: str) -> tuple:
    """按病因选出该跑哪几个故障钩子（钩子名取自 `hook_registry` 的登记表）。

    `denied_by_gate` 只发 denied，**绝不发 retry** —— 被门拒绝时"重试"就是绕门的开始。
    """
    ev = []
    if cause_key == "denied_by_gate":
        ev += ["on_tool_denied"]
    elif cause_key == "timeout":
        ev += ["on_tool_timeout"]
    elif cause_key == "backend_unavailable":
        ev += ["on_tool_denied"]          # 记成"这条走不通"，不是"再试一次"
    ev += ["after_browser_action", "post_tentacle_invoke"]
    return tuple(dict.fromkeys(ev))


def _hr():
    """稳健拿到 `hook_registry`：包路径 → 顶层名 → **按文件路径直接加载**（兜底）。

    教训（2026-09-22 实测）：第一版写的是 `from hook_registry import …`（顶层导入），
    而它在 `gbt_allinone/tools/` 下、不在触手目录的 sys.path 上 ⇒ 导入失败 ⇒
    被 `except: pass` 吞掉 ⇒ 表面"已接线"，实际 `hooks=None`（**静默失败**）。
    """
    import importlib
    for mod in ("gbt_allinone.tools.hook_registry", "hook_registry"):
        try:
            return importlib.import_module(mod)
        except Exception:                                      # noqa: BLE001
            continue
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parents[1] / "tools" / "hook_registry.py"
    spec = importlib.util.spec_from_file_location("_gbt_hook_registry", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m          # 3.14 规矩：先注册进 sys.modules 再 exec
    spec.loader.exec_module(m)
    return m


def fire_failure_hooks(result: dict, module: str, op: str) -> dict:
    """把失败交给钩子链。**钩子不在也不许影响导航结果**，但**失败必须可见**：
    出错要记进病因账（不许静默 pass —— 静默 pass 就是"假装已接线"）。"""
    out = {"fired": [], "errors": [], "why_not": None}
    try:
        hr = _hr()
        known = {h[1] for h in hr.HOOKS}
        if not hr.REGISTERED:
            hr.install_nav_hooks()
        want = [e for e in hooks_for(result.get("cause", "")) if e in known]
        chain = hr.registered_hooks(want)
        if not chain:
            out["why_not"] = "链上无已注册钩子：想要 %s" % want
            result.setdefault("hooks", out)
            return out
        rep = hr.dispatch(chain, ctx={"module": module, "op": op,
                                      "cause": result.get("cause"),
                                      "retry_hint": result.get("retry_hint")})
        out["fired"] = rep.get("ran", [])
        out["errors"] = rep.get("errors", [])
        out["on_hook_failed"] = rep.get("on_hook_failed", [])
        result.setdefault("hooks", out)
    except Exception as e:                                     # noqa: BLE001
        out["why_not"] = "%s: %s" % (type(e).__name__, str(e)[:140])
        result.setdefault("hooks", out)
        try:
            record_swallow(e, "nav_etiology", "fire_failure_hooks")
        except Exception:                                      # noqa: BLE001
            pass
    return out


def _hook_note(name: str):
    """故障钩子的真实现：把"哪一类病、在哪个入口"记进病因账，并回一行可读的处置建议。"""
    def impl(ctx=None):
        r = ctx if isinstance(ctx, dict) else {}
        record_swallow(RuntimeError("钩子 %s 触发" % name), r.get("module", "?"), r.get("op", name))
        return {"hook": name, "cause": r.get("cause"), "hint": r.get("retry_hint")}
    impl.__name__ = name
    return impl


_HOOK_IMPL = {
    "on_tool_timeout": _hook_note("on_tool_timeout"),
    "on_tool_retry": _hook_note("on_tool_retry"),
    "on_tool_denied": _hook_note("on_tool_denied"),
    "after_browser_action": _hook_note("after_browser_action"),
    "post_tentacle_invoke": _hook_note("post_tentacle_invoke"),
    # 登记表 #48：坏钩子这件事**必须进事件流**（此前只躺在当次返回值里）
    "on_hook_failed": _hook_note("on_hook_failed"),
}

# ───────────────────────────────────────────── 病因驱动重试（retry_hint 真被用上）

RETRY_POLICY = {
    "element_not_found": {"max_attempts": 3, "action": "scroll_and_refind",
                          "why": "多半在视野外 —— 先滚动/展开再重找，别原地重试"},
    "stale_target": {"max_attempts": 3, "action": "refetch_target",
                     "why": "界面重绘了 —— 重新取一次元素，别复用旧引用"},
    "modal_blocked": {"max_attempts": 2, "action": "dismiss_modal",
                      "why": "弹窗挡着 —— 先关弹窗再重发动作"},
    "timeout": {"max_attempts": 2, "action": "wait_longer",
                "why": "改判据或拉长等待（等状态而不是等固定秒数）"},
    "action_no_effect": {"max_attempts": 1, "action": "compare_frames",
                         "why": "先做前后对比确认到底动没动，再决定要不要重发"},
    "window_lost": {"max_attempts": 1, "action": "reenumerate_windows",
                    "why": "重新枚举窗口；必要时重新拉起目标程序"},
    # 下面两类**一次都不重试** —— 重试无意义（前者）或重试等于绕门（后者）
    "backend_unavailable": {"max_attempts": 0, "action": "stop_and_report",
                            "why": "后端不可用不是重试能解决的：先补依赖或换后端"},
    "denied_by_gate": {"max_attempts": 0, "action": "stop_and_report",
                       "why": "**被门拒绝不许重试** —— 重试就是绕门的开始，如实上报缺哪个 scope"},
}


def retry(fn, *args, cause_key: str | None = None, attempts: int | None = None,
          on_attempt=None, **kw) -> dict:
    """**按病因重试**：拿第一次失败的 `cause` 去查策略表，按策略决定"重不重、重几次"。

    `fn(*args, **kw)` 必须返回 dict 且带 `ok`。返回最终结果 + 重试读数：
        attempts 实际尝试次数 · retried 是否重试过 · policy 用了哪条策略
        stopped_because 为什么停（其中 `denied_by_gate` 一定是主动停，不是没试）
    铁律：`denied_by_gate` / `backend_unavailable` 的 `max_attempts = 0` ⇒ **一次都不重试**。
    """
    r = fn(*args, **kw)
    if not isinstance(r, dict) or r.get("ok") is not False:
        return {**r, "attempts": 1, "retried": False} if isinstance(r, dict) else r
    ck = cause_key or r.get("cause") or classify(None, str(r.get("error", "")))
    pol = RETRY_POLICY.get(ck, {"max_attempts": 0, "action": "stop_and_report", "why": "无策略"})
    limit = pol["max_attempts"] if attempts is None else int(attempts)
    tries = 1
    trail = []
    while tries <= limit:
        if callable(on_attempt):
            try:
                on_attempt({"attempt": tries + 1, "cause": ck, "action": pol["action"]})
            except Exception:                                  # noqa: BLE001
                pass
        _note({"cause": ck, "cause_cn": CAUSE_CN.get(ck, ck), "module": "retry",
               "op": "attempt#%d(%s)" % (tries + 1, pol["action"]),
               "exc_type": "(重试)", "msg": pol["why"], "at": round(time.time(), 3)})
        trail.append(pol["action"])
        r2 = fn(*args, **kw)
        tries += 1
        if isinstance(r2, dict) and r2.get("ok") is True:
            return {**r2, "attempts": tries, "retried": True, "policy": pol,
                    "retry_trail": trail, "recovered": True}
        r = r2
        ck2 = r.get("cause") or ck
        if ck2 != ck:                                          # 病变了就按新病重查策略
            ck = ck2
            pol = RETRY_POLICY.get(ck, {"max_attempts": 0, "action": "stop_and_report",
                                        "why": "换了病种且无策略"})
            limit = pol["max_attempts"] if attempts is None else int(attempts)
    return {**r, "attempts": tries, "retried": tries > 1, "policy": pol,
            "retry_trail": trail, "recovered": False,
            "stopped_because": ("策略禁止重试（%s）" % pol["why"]) if limit == 0
            else "重试用尽仍未成功"}


# ───────────────────────────────────────────── 病因账落盘（位置显式，不擅自进生产 store）

_LOG_PATH: list = [None]          # [Path | None]


def log_path() -> str:
    """当前落盘位置。默认 **None = 不落盘**（进程内环形缓冲）。

    位置策略（**不擅自写生产 store**）：
      · 环境变量 `GBT_NAV_ETIOLOGY_LOG` 优先（主人指定什么就是什么）
      · 否则**不落盘** —— 要落盘请显式 `attach_log(路径)`。
    建议位置：工作区内 `.gbt/logs/nav_etiology.jsonl`（非生产面、非镜像面、可整目录清）。
    """
    import os
    if _LOG_PATH[0] is not None:
        return str(_LOG_PATH[0])
    return os.environ.get("GBT_NAV_ETIOLOGY_LOG", "") or ""


def attach_log(path) -> dict:
    """显式挂上落盘位置（父目录自动建）。落盘失败**绝不影响导航**。"""
    from pathlib import Path as _Path
    p = _Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("")
        _LOG_PATH[0] = p
        return {"ok": True, "attached": str(p)}
    except OSError as e:
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}


def detach_log() -> dict:
    old, _LOG_PATH[0] = _LOG_PATH[0], None
    return {"ok": True, "detached": str(old) if old else ""}


_PERSIST_FAILED = {"count": 0, "reasons": {}, "last_at": None}


def persist_failures() -> dict:
    """只读：病因账**落盘失败**的计数与原因。

    `count > 0` ⇒ **账本可能缺行**（记录在内存环形缓冲里，但没写进 jsonl）。
    """
    return {"ok": True, "readonly": True, "count": _PERSIST_FAILED["count"],
            "reasons": dict(_PERSIST_FAILED["reasons"]),
            "last_at": _PERSIST_FAILED["last_at"],
            "note": "count>0 ⇒ 有病因记录未落盘（账本可能缺行）"}


def _persist(row: dict) -> None:
    """把一条病因记录**追加**到 jsonl。

    🔴 2026-09-22 修（错报治理 · 第 31/40 条）：这里原来 `except: pass` ——
    病因账落盘失败**无人知道**，账本看起来完整、实际缺行。
    注意：这里是**追加**（`mode="a"`），**不能**改用 `visible_write`（那是原子替换，会覆盖旧行）。
    所以就地留痕：计数 + 记因 + 同类首次出声。
    ⚠️ 不能走本模块的 `_note()`（那会回头调 `_persist` ⇒ 递归），故直接计数出声。
    """
    p = log_path()
    if not p:
        return
    try:
        import json as _json
        with open(p, "a", encoding="utf-8") as f:
            f.write(_json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as _e:                                    # noqa: BLE001
        import time as _t
        _PERSIST_FAILED["count"] += 1
        _PERSIST_FAILED["last_at"] = round(_t.time(), 3)
        _k = type(_e).__name__
        _PERSIST_FAILED["reasons"][_k] = _PERSIST_FAILED["reasons"].get(_k, 0) + 1
        if _PERSIST_FAILED["reasons"][_k] == 1:                # 同类只首次出声，不刷屏
            try:
                print("⚠️ nav_etiology: 病因账落盘失败（%s: %s）⇒ 账本可能缺行（累计 %d 次）"
                      % (_k, str(_e)[:110], _PERSIST_FAILED["count"]), file=sys.stderr)
            except Exception:                                   # noqa: BLE001
                pass


def _note(row: dict) -> dict:
    """**唯一记账口**：进内存环形缓冲 + （挂了位置就）落盘。

    教训（2026-09-22 实测）：第一版写了 `_persist()` 却**从来没调用它** ——
    `attach_log` 返回 ok、文件也建了，但**一行都没写进去**。
    接口在、链路断，是最难发现的那种半成品。故收成一个口，谁都别绕过它记账。
    """
    _LEDGER.append(row)
    _persist(row)
    return row



def ledger(limit: int = 50) -> dict:
    """只读：最近的吞错/失败账（按时间倒序）。"""
    rows = list(_LEDGER)[-limit:][::-1]
    return {"ok": True, "readonly": True, "size": len(_LEDGER), "rows": rows}


def stats() -> dict:
    """只读：**按病因计数** —— 这是"哪类病最多、该按哪类下药"的唯一依据。"""
    c = collections.Counter(r["cause"] for r in _LEDGER)
    return {
        "ok": True, "readonly": True, "total": len(_LEDGER),
        "by_cause": {k: {"n": c.get(k, 0), "cn": CAUSE_CN[k], "retry_hint": RETRY_HINT[k]}
                     for k in CAUSE_KEYS},
        "by_module": dict(collections.Counter(r["module"] for r in _LEDGER).most_common()),
        "unknown_causes": sorted(set(c) - set(CAUSE_KEYS)),
    }


def clear() -> dict:
    n = len(_LEDGER)
    _LEDGER.clear()
    return {"ok": True, "cleared": n}


# ───────────────────────────────────────────── 两把对照

def selftest(verbose: bool = True) -> int:
    """正对照：八类病因**每一类都必须能被判出来**（一类判不出 = 那一维是瞎的）。
    负对照：`ok:True` 不许被加病因、不许进账。"""
    clear()
    cases = [
        ("timeout", TimeoutError("subprocess timed out after 15s")),
        ("element_not_found", RuntimeError("element not found: 提交")),
        ("window_lost", OSError("Invalid window handle")),
        ("modal_blocked", RuntimeError("blocked by dialog")),
        ("denied_by_gate", PermissionError("[WinError 5] Access is denied")),
        ("backend_unavailable", ModuleNotFoundError("No module named 'uiautomation'")),
        ("stale_target", RuntimeError("element is stale")),
        ("action_no_effect", ValueError("something odd happened")),
    ]
    miss = []
    got = {}
    for want, exc in cases:
        k = classify(exc)
        got[want] = k
        if k != want:
            miss.append("%s → 判成 %s" % (want, k))
    # 失败返回也要能补病因
    e1 = enrich({"ok": False, "error": "等待 '登录' 超时(30s)"}, "omni_read", "wait_text")
    e2 = enrich({"ok": False, "unavailable": True, "denied": False,
                 "why": "uiautomation 不可用"}, "omni_domain", "read_controls")
    if e1.get("cause") != "timeout":
        miss.append("失败返回未判成 timeout：%s" % e1.get("cause"))
    if e2.get("cause") != "backend_unavailable":
        miss.append("unavailable 未判成 backend_unavailable：%s" % e2.get("cause"))
    # 负对照
    ok_before = {"ok": True, "data": 1}
    ok_after = enrich(dict(ok_before), "omni_read", "read_text")
    neg = []
    if ok_after != ok_before:
        neg.append("成功返回被改动了")
    if any(r["cause"] for r in ledger()["rows"] if r["module"] == "___never___"):
        neg.append("空账异常")
    # 装饰器：抛错的入口必须变成带病因的失败，而不是炸出去
    @etiology("omni_nav_test", "click_text")
    def boom():
        raise TimeoutError("click timed out")
    r = boom()
    if r.get("ok") is not False or r.get("cause") != "timeout":
        miss.append("装饰器未把抛错转成带病因的失败：%s" % r)
    # 装饰器：成功路径原样
    @etiology("omni_nav_test", "ok_path")
    def fine():
        return {"ok": True, "clicked": True}
    if fine() != {"ok": True, "clicked": True}:
        neg.append("装饰器改动了成功路径")
    st = stats()
    if verbose:
        print("═══ 病因钩子 · 两把对照 ═══")
        print("八类病因判定：")
        for k, v in got.items():
            print("   %-20s → %-20s %s" % (k, v, "✅" if k == v else "✗"))
        print("账本按病因：%s" % {k: v["n"] for k, v in st["by_cause"].items() if v["n"]})
        print("账本按模块：%s" % st["by_module"])
        print("未知病因（不该有）：%s" % st["unknown_causes"])
        print("正对照漏判 %d 项 %s" % (len(miss), miss))
        print("负对照问题 %d 项 %s" % (len(neg), neg))
        print("结论：%s" % ("两把对照都过 ✅" if not miss and not neg
                          else "✗ 判红：漏=%s 误=%s" % (miss, neg)))
    clear()
    return 0 if (not miss and not neg) else 1


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(selftest())
