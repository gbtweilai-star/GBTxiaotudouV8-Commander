# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 五维合一同步执行 —— **默认执行路径**

Owner 2026-09-22 定（原话）：
    「必须改成**五维合一同步执行**，**眼脑耳手嘴都要同步**，**设为默认行为**」

═══ 它取代什么 ═══
以前：直接调工具/函数 —— 想调谁调谁，**verify 和 health 随时可以被省掉**。
本会话两次翻车（`/api/recent-calls` 写错方法却声称已接、静态根放开 `.git/config`）
**都发生在被省掉的那一维上**。所以不能靠"我注意"，要做成**跑不掉的一条路**。

═══ 五维（脑的纵向）═══
    route    → 这事归谁管（意图 → 能力）
    execute  → 动手
    verify   → **回头看现实**（最容易被省、最不该省）
    health   → 有没有留下隐患
    unify    → 上面是一条链，不是四个孤立动作

═══ 四觉（横向同步）═══
    耳 ear   → **先听清**（目标 + 上下文），不听清就动手 = 瞎干
    眼 eye   → **看现实**（截图/读回/哈希），不看就说完成 = 假执行
    手 hand  → 真做
    嘴 mouth → **说出结论**（含"没做到什么"）

**缺一条就如实报缺哪条**（`needs_dependency`），绝不假装四觉齐了。
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import time
from pathlib import Path

_IMPL_VERSION = "1.1"
_BASE = Path(__file__).resolve().parent.parent      # gbt_allinone/

# ── 信封标记（进程内、跨线程安全）──
# `run()` 一进来就置 True，出去就复位；`api.run_task` 的 `_audit` 读它，
# 把"这次调用在不在信封里"**亲笔记进审计**。
# 为什么不用文本配对（数 sync_ear…sync_mouth 之间夹了什么）：
# 一旦有嵌套调用或异常中断，文本配对就会配歪 —— 那是"猜"，不是"读"。
_IN_ENVELOPE: contextvars.ContextVar = contextvars.ContextVar("gbt_in_envelope",
                                                             default=False)

# 🔴 2026-09-23 加：**可继承到子进程**的信封标记（Owner：把"绕过"也堵上）。
# 为什么光有 contextvar 不够：它是**进程内**的。`five-dim.py cap` 是独立进程、
#   任何 `python -m gbt_allinone ...`、以及 composite 能力位**自己 fork 的子进程**
#   （实测：`cross_scan` 的 `_x_run_isolated` 会起子进程调 6 个扫描器）
#   在 contextvar 眼里全是"信封外" —— 那不是"没走主线道"，是**标记过不了进程边界**。
# 做法：`envelope()` 除了置 contextvar，还把标记写进环境变量；子进程继承后 `in_envelope()` 认它。
# ⚠️ 信任边界（写清，不装安全）：环境变量是**可伪造**的 —— 谁手动 `set GBT_ENVELOPE=1`
#   都能自称在信封里。所以本文件**不把它当安全边界**，只当**传播机制**；
#   并且 `envelope_source()` 会如实区分这次是 "ctx" 还是 "env" 进来的，
#   账本里 `synced_via` 一眼看得出，不给"靠继承标记"冒充"真在信封里"留缝。
_ENV_KEY = "GBT_ENVELOPE"
_ENV_ON = "1"
# 🔴 2026-09-23 加：**默认同步必须留一个能关的开关**，否则负对照就没了。
# 病根（当轮实测抓到）：门口一开始默认开信封，`five-dim.py cap --no-envelope` 立刻变成废话 ——
# 账本里那条对照记的是 `synced=True via=ctx entry=auto`，而它**本来要证明"信封外确实算信封外"**。
# 一个测不出"假"的尺子就不是尺子。所以 `--no-envelope` 会把下面这个键置上，门口照它**不开**。
# ⚠️ 信任边界同 `_ENV_KEY`：可伪造，只当**开关**用，不当安全边界。
_ENV_OFF_KEY = "GBT_ENVELOPE_OFF"


def envelope_suppressed() -> bool:
    """这次是不是被显式要求"**不要**信封"（负对照/取证用）。"""
    try:
        import os
        return os.environ.get(_ENV_OFF_KEY) == _ENV_ON
    except Exception:                                              # noqa: BLE001
        return False


def envelope_source() -> str | None:
    """这次算"在信封里"是靠什么：`ctx`（同进程真信封）/ `env`（继承的标记）/ `None`。"""
    try:
        if _IN_ENVELOPE.get():
            return "ctx"
    except Exception:                                               # noqa: BLE001
        pass
    try:
        import os
        if os.environ.get(_ENV_KEY) == _ENV_ON:
            return "env"
    except Exception:                                               # noqa: BLE001
        pass
    return None


def in_envelope() -> bool:
    """当前调用是否走在五维合一的信封里。api 入口用它记账。

    同进程 contextvar **或** 继承来的环境变量，任一成立即算 —— 后者是为了跨进程传播。
    """
    return envelope_source() is not None


@contextlib.contextmanager
def envelope():
    """信封上下文。进出事件 + 信封标记一起管，**并把标记写进环境变量给子进程继承**。"""
    import os
    tok = _IN_ENVELOPE.set(True)
    prev = os.environ.get(_ENV_KEY)
    os.environ[_ENV_KEY] = _ENV_ON
    try:
        yield
    finally:
        _IN_ENVELOPE.reset(tok)
        if prev is None:
            os.environ.pop(_ENV_KEY, None)
        else:
            os.environ[_ENV_KEY] = prev


# ── 2026-09-23 Owner 令：大脑执行层 / 万能插 / 五维合一**全部默认同步** ──
# 实测三层的默认同步状态（当轮 grep + 真跑）：
#   · 五维合一 `five-dim.py cap`：**有**（`if not no_env:` → step_open + envelope + 自动 step_close）
#   · 万能插 `omni.py run`：**有（间接）**（起 `five-dim.py cap <kind>` 子进程，不传 --no-envelope）
#   · 大脑执行层 `engine.py` / `brain_*`：**没有自己的** —— 它 `from .api import _run_task_core as run_task`
#     直连内层，只有在**调用方已经开了信封**时才算同步；面板 `panel_server.capability()`、
#     `python -m gbt_allinone`、以及任何直调都属于"信封外"。
# ⇒ 修法不是给每层各写一遍（那是纪律，会漏），而是**收在唯一那道门**上：
#   `_run_task_core` 一进来就 `auto_envelope()` —— 谁调都默认同步，一处生效。
_ENVELOPE_ENTRY: contextvars.ContextVar = contextvars.ContextVar("gbt_envelope_entry",
                                                                default=None)


def envelope_entry() -> str | None:
    """这次调用的信封是**谁开的**：`"auto"`（门口的默认同步）/ `"outer"`（外层早就开着）/ None。"""
    try:
        return _ENVELOPE_ENTRY.get()
    except Exception:                                              # noqa: BLE001
        return None


@contextlib.contextmanager
def auto_envelope():
    """入口自卫：**没在信封里就自己开一个**；已经在里头就原样不动（绝不覆盖外层归属）。

    为什么要和 `envelope()` 分开、还要多记一格 `envelope_entry`：
      "默认同步"（门口替你开的）与"主动信封"（五维合一亲手开的）**不是一回事**。
      混成一格，就会把"我把默认打开了"冒充成"纪律执行得好" —— 那正是本仓最恨的假绿。
      所以默认照开，但账本上 `synced_entry` 一眼看得出是谁开的。

    yield 出 `"auto"` / `"outer"` / `"off"`，同时把同样的值挂进 contextvar 供 `_audit` 取。
    """
    if envelope_suppressed() and envelope_source() is None:
        # 负对照通道：被显式要求"不要信封"就**真的不进** ——
        # 账本会记 `synced=False`（且 `synced_entry` 为空）。留着这条，尺子才可证伪。
        tok = _ENVELOPE_ENTRY.set("off")
        try:
            yield "off"
        finally:
            _ENVELOPE_ENTRY.reset(tok)
        return
    if envelope_source() is not None:
        tok = _ENVELOPE_ENTRY.set("outer")
        try:
            yield "outer"
        finally:
            _ENVELOPE_ENTRY.reset(tok)
        return
    with envelope():
        tok = _ENVELOPE_ENTRY.set("auto")
        try:
            yield "auto"
        finally:
            _ENVELOPE_ENTRY.reset(tok)


def _audit(event: str, meta: dict) -> None:
    try:
        from ..store import audit
        audit(event, meta)
    except Exception:                                              # noqa: BLE001
        pass                      # 审计挂了不能反过来把执行弄崩


# ═══════════════════ 耳：先听清 ═══════════════════

def ear(goal: str, context: dict | None = None) -> dict:
    """听清目标与上下文。**空目标 = 听不清 ⇒ 不许往下走。**"""
    g = str(goal or "").strip()
    ctx = context or {}
    if not g:
        return {"ok": False, "channel": "ear", "needs": "goal",
                "note": "没听清目标 —— 不往下走（瞎干比不干更贵）"}
    # 上下文能带多少带多少；带不到不算失败，但要如实说带了几个键
    return {"ok": True, "channel": "ear", "goal": g[:120],
            "context_keys": sorted(ctx)[:12], "context_n": len(ctx)}


# ═══════════════════ 眼：看现实 ═══════════════════

def eye(targets: list | None = None) -> dict:
    """看现实。**没给观察目标 ⇒ 如实说"这次没看"**，不许默认"应该没问题"。"""
    if not targets:
        return {"ok": False, "channel": "eye", "looked": 0,
                "note": "这次**没有指定任何观察目标** ⇒ 没看就说没看（不许默认没问题）"}
    seen = []
    for t in targets:
        p = Path(t)
        if not p.is_absolute():
            p = _BASE.parent / t
        try:
            if not p.is_file():
                seen.append({"target": str(t), "exists": False})
                continue
            b = p.read_bytes()
            seen.append({"target": str(t), "exists": True, "bytes": len(b),
                         "sha256": hashlib.sha256(b).hexdigest()[:16]})
        except Exception as e:                                      # noqa: BLE001
            seen.append({"target": str(t), "exists": None,
                         "error": f"{type(e).__name__}: {str(e)[:60]}"})
    ok = all(s.get("exists") is True for s in seen)
    return {"ok": ok, "channel": "eye", "looked": len(seen), "evidence": seen}


# ═══════════════════ 嘴：说出结论 ═══════════════════

def mouth(goal: str, dims: dict, senses: dict) -> dict:
    """说结论。**必须同时说出"没做到什么"** —— 只报喜的嘴是假嘴。"""
    missed = []
    for name, r in (senses or {}).items():
        if isinstance(r, dict) and r.get("ok") is False:
            missed.append(f"{name}: {r.get('note') or r.get('needs') or '未做到'}")
    bad = [d for d, r in (dims or {}).items()
           if isinstance(r, dict) and r.get("state") in ("fail", "stuck")]
    verdict = "ok" if (not missed and not bad) else "partial"
    return {"ok": verdict == "ok", "channel": "mouth", "verdict": verdict,
            "said": {"goal": str(goal)[:120], "dims": sorted((dims or {})),
                     "senses_ok": [k for k, v in (senses or {}).items()
                                   if isinstance(v, dict) and v.get("ok")],
                     "missed": missed, "bad_dims": bad}}


# ═══════════════════ 主入口：默认执行路径 ═══════════════════

def run(goal: str, **kw) -> dict:
    """**默认执行路径**（信封入口）。

    薄包装：只负责开信封（让 `api.run_task` 的账上记下"这次在信封里"），
    真逻辑在 `_run_inner` —— 这样**不用重排原函数缩进**，改动面最小。
    """
    with envelope():
        return _run_inner(goal, **kw)


def _run_inner(goal: str, *, kind: str = "", payload: dict | None = None,
        expectation: str = "", watch: list | None = None,
        context: dict | None = None, use_unify: bool = True) -> dict:
    """**默认执行路径**：耳 → 脑(route) → 手(execute) → 眼(verify) → 嘴 → 健康。

    参数
      goal        要干什么（听不清就不干）
      kind        直接指定能力；不给则交给 route 去选
      watch       眼要看什么（文件路径列表）。**不给就是"这次没看"**，如实记
      use_unify   True=走 brain_exec.unify（真链）；False=只走本模块的编排（便于自测）
    """
    t0 = time.time()
    out = {"version": _IMPL_VERSION, "goal": str(goal)[:160], "channels": {}, "dims": {}}

    # ── 耳 ──
    e = ear(goal, context)
    out["channels"]["ear"] = e
    _audit("sync_ear", {"ok": e["ok"], "goal": e.get("goal", "")[:80]})
    if not e["ok"]:
        out["channels"]["mouth"] = mouth(goal, {}, {"ear": e})
        _audit("sync_abort", {"at": "ear", "why": e["note"][:80]})
        out["elapsed_ms"] = int((time.time() - t0) * 1000)
        # 🔴 必须显式写 ok=False。
        # 2026-09-22 钉子测试抓到的真 bug：这里原来**没有 ok 键**，
        # 调用方 `.get("ok", True)` 会把"听不清所以中止"读成**成功** ——
        # 这是条假成功路径，而且长在"防假执行"的模块里。
        out["ok"] = False
        out["verdict"] = "aborted"
        out["note"] = "耳没听清 ⇒ 中止（宁可不干，也不瞎干）"
        return out

    # ── 脑 + 手（走真链 brain_exec.unify，五维进出事件由 @_spanned 落）──
    exec_res: dict = {}
    try:
        import gbt_allinone as g
        if use_unify:
            r = g.run_task("brain_unify", {"goal": str(goal), "payload": payload or {},
                                           "expectation": expectation or str(goal)})
            b = r.get("gbt_result") or r
            exec_res = (b.get("result") or b) if isinstance(b, dict) else {"raw": str(b)[:200]}
        elif kind:
            r = g.run_task(kind, payload or {})
            b = r.get("gbt_result") or r
            exec_res = (b.get("result") or b) if isinstance(b, dict) else {"raw": str(b)[:200]}
    except Exception as ex:                                         # noqa: BLE001
        exec_res = {"error": f"{type(ex).__name__}: {str(ex)[:120]}"}
    out["channels"]["hand"] = {"ok": "error" not in exec_res, "channel": "hand",
                               "via": "brain_unify" if use_unify else (kind or "none")}

    # ── 眼：回头看现实 ──
    ey = eye(watch)
    out["channels"]["eye"] = ey
    _audit("sync_eye", {"ok": ey["ok"], "looked": ey["looked"]})

    # ── 五维状态（从真实进出事件读，不编）──
    try:
        from . import brain_graph as bg
        dims = (bg.live_state(limit=400).get("dims_state") or {})
    except Exception:                                               # noqa: BLE001
        dims = {}
    out["dims"] = dims

    # ── 嘴 ──
    m = mouth(goal, dims, out["channels"])
    out["channels"]["mouth"] = m
    _audit("sync_mouth", {"verdict": m["verdict"], "missed": len(m["said"]["missed"])})

    out["ok"] = m["ok"]
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    out["verdict"] = m["verdict"]
    out["exec"] = exec_res
    return out


def audit_sync(limit: int = 4000) -> dict:
    """量「**无脑操作率**」。

    Owner：「没有五维合一不是等于无脑操作一样的」——那就得**量得出来**，不能凭感觉。

    判据（可证伪）：
      · 信封 = `sync_ear` 开场、`sync_mouth`/`sync_abort` 收场之间那段
      · **落在信封外的真实能力调用**（event ∈ ok/error/denied 且带 kind）= 无脑操作
      · 心跳/调度之类的非能力事件（sched_tick、panel_*）不计入分子也不计入分母
    返回里 `brainless_ratio` 就是"手在动、脑眼没参与"的比例。
    """
    p = _BASE / "store" / "audit.jsonl"
    if not p.is_file():
        return {"ok": False, "error": "audit.jsonl 不存在 —— 量不了就不编一个数"}
    size = p.stat().st_size
    block = 512 * 1024
    data = b""
    with p.open("rb") as f:
        pos = size
        while pos > 0 and data.count(b"\n") <= limit:
            step = min(block, pos)
            pos -= step
            f.seek(pos)
            data = f.read(step) + data
    raws = [l for l in data.split(b"\n") if l.strip()][-limit:]

    in_env = False
    envs = 0
    inside, outside = [], []
    _NON_CAP = ("sched_tick", "panel_persona_heartbeat", "panel_", "persona_heartbeat")
    for raw in raws:
        try:
            e = json.loads(raw.decode("utf-8", "replace"))
        except Exception:                                           # noqa: BLE001
            continue
        ev = str(e.get("event") or "")
        if ev == "sync_ear":
            in_env = True
            envs += 1
            continue
        if ev in ("sync_mouth", "sync_abort"):
            in_env = False
            continue
        if ev not in ("ok", "error", "denied", "call"):
            continue
        meta = e.get("meta") or {}
        kind = str(meta.get("kind") or "")
        if not kind or any(n in kind for n in _NON_CAP):
            continue                    # 不是能力调用，进出都不计
        # 优先读**入口亲笔**记的 synced 标记（2026-09-22 起 api 入口会写）；
        # 读不到才退回信封文本配对 —— 那是"猜"，只在旧账上兜底。
        if "synced" in meta:
            (inside if meta.get("synced") else outside).append(kind)
        else:
            (inside if in_env else outside).append(kind)

    total = len(inside) + len(outside)
    ratio = (len(outside) / total) if total else 0.0

    # ── 把 **agent 步**也数进账（2026-09-22）──
    # 为什么必须有这一段：`cap_calls_total` 只数带 `kind` 的能力调用，
    # 而我（agent）读文件/改代码/跑脚本**根本不产生 kind** ⇒ 原尺子**看不见我**。
    # 我建了两步式信封却不上报，比率为 0 也是假的 —— 量不到的指标等于没有指标。
    agent_open = agent_closed = agent_abort = 0
    for raw in raws:
        try:
            e = json.loads(raw.decode("utf-8", "replace"))
        except Exception:                                           # noqa: BLE001
            continue
        if (e.get("meta") or {}).get("actor") != "agent":
            continue
        ev = str(e.get("event") or "")
        if ev == "sync_ear":
            agent_open += 1
        elif ev == "sync_mouth":
            agent_closed += 1
        elif ev == "sync_abort":
            agent_abort += 1
    open_now = _steps_load()
    close_rate = (agent_closed / agent_open) if agent_open else 0.0

    return {"ok": True, "window_events": len(raws), "envelopes": envs,
            "cap_calls_total": total,
            "inside_envelope": len(inside), "outside_envelope": len(outside),
            "brainless_ratio": round(ratio, 4),
            "verdict": ("无脑操作" if ratio > 0.5 else
                        "多数在信封内" if ratio <= 0.2 else "一半一半"),
            # agent 侧（量我自己）
            "agent_steps_opened": agent_open,
            "agent_steps_closed": agent_closed,
            "agent_steps_aborted": agent_abort,
            "agent_unclosed_on_disk": sorted(open_now),
            "agent_close_rate": round(close_rate, 4),
            # 判定必须**从数据推**，不许掉进兜底分支就胡说。
            # 2026-09-22 实测踩到：opened=5 / closed=4 / 磁盘无未收 ⇒ 原来判成
            # 「一步都没开过」—— 那是话术与数据不符，正是本体系要防的东西。
            "agent_verdict": (
                "我这边：**一步都没开过**" if agent_open == 0
                else "我这边：**有开了没收的** " + str(sorted(open_now)) if open_now
                else "我这边：开收齐全" if close_rate >= 0.99
                else f"我这边：开 {agent_open} 收 {agent_closed}"
                     f"（率 {close_rate:.0%}，差额在窗口边缘，磁盘无悬挂）"),
            "worst_outside": sorted(set(outside))[:15],
            "note": "信封外的调用 = 手在动、脑与眼没参与"}


# ═══════════════ 把信封开在"我自己"头上 ═══════════════
# Owner 2026-09-22：「五维合一必须给我钉死，不管怎么重启都是这个执行方式」
#
# 问题：`run()` 的信封覆盖的是 `run_task`（**她**的执行）。
# 而**我（agent）**这一整段会话里读文件、改代码、跑脚本 —— 走的是工具调用，
# **根本不经过 run_task** ⇒ **尺子看不见我** ⇒ 只钉住了一条腿。
#
# 做法：两步式。开步记目标（耳），收步交证据（眼 + 嘴）。
#   · **收步必须带证据**（文件哈希 / 计数 / 回读值）。给不出证据 ⇒ 不许说完成。
#   · 落到**同一本账**（store/audit.jsonl），所以同一把尺子量得到我。
def _resolve_steps_file() -> Path:
    """未收步账的落点 —— **必须跟 store 绑定同一个来源**。

    🔴 2026-09-23 修：原来硬编码 `_BASE/'store'`，**不跟 `GBT_STORE_DIR`**。
    实测后果：隔离 store 里跑的 `five-dim.py cap` 会把**开步写进生产步账**，
    而它的收步/清理可能落在别处、或进程被杀 ⇒ 生产步账上留下**永久孤儿步**。
    机检证据：**开步 64 · 收步 49**，而"未收步清单"是 `{}` ⇒ 15 步**既没收也没留下**。
    步账是「欠的活」的唯一清单 —— 它跟错了 store，欠的活就成了一笔假账。
    """
    try:
        from .. import _paths
        return _paths.STORE_DIR / "sync_steps.json"
    except Exception:                                               # noqa: BLE001
        return _BASE / "store" / "sync_steps.json"


_STEPS_FILE = _resolve_steps_file()


def _steps_load() -> dict:
    """开着的步**落盘** —— 内存字典活不过进程退出，而 Owner 要的是「不管怎么重启」。"""
    try:
        if _STEPS_FILE.is_file():
            return json.loads(_STEPS_FILE.read_text(encoding="utf-8-sig")) or {}
    except Exception:                                               # noqa: BLE001
        pass
    return {}


def _steps_save(d: dict) -> None:
    """**原子**落盘：先写临时文件再 `os.replace` 换过去。

    为什么不能直接 `write_text`：那样写一半被杀，盘上就留**半个 JSON** ⇒
    下次 `_steps_load` 解析失败 ⇒ 静默返回 `{}` ⇒ **所有未收的步一起消失**。
    原子替换保证"要么旧的、要么新的"，不存在"半个"。
    """
    try:
        _STEPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STEPS_FILE.with_name(_STEPS_FILE.name + ".tmp%d" % os.getpid())
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(str(tmp), str(_STEPS_FILE))
    except Exception:                                               # noqa: BLE001
        pass                    # 落盘失败不能反过来把执行弄崩


# ── 步账互斥（2026-09-23 补）─────────────────────────────────────────────
# 机检到的事实：**开步 64 · 收步 49**，而"未收步清单"是 `{}`
#   ⇒ 那 15 步**既没收、也没留在盘上 = 丢了**。
# 成因：`_steps_load()` → 改 → `_steps_save()` 是**整文件读-改-写，没有锁**。
#   两个进程交错（并发探针/测试时必然发生）就互相覆盖；进程被杀（超时、job_kill）
#   同样留下永久悬空。
# 危害：步账是「**欠的活**」的唯一清单 —— 丢了 ⇒ 欠的活看不见 ⇒ 正好是偷懒的温床。
_LOCK_FILE = _STEPS_FILE.with_name("sync_steps.lock")
_LOCK_TIMEOUT = 5.0


_STALE_LOCK_SECONDS = 60.0


def _pid_alive(pid: int) -> bool:
    """那个 PID 现在还活着吗。

    🔴 2026-10-11 加：锁泄漏回收要用它（见 _stale_lock 的说明）。
    跨平台：Windows 走 OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)，
    其余走 os.kill(pid, 0)。任何异常都判"不活" —— 宁可回收一把可疑的锁，
    也不要让一把死锁把**所有收步**永远挡在门外（实测挡了 13 天）。
    """
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            k32.CloseHandle(h)
            return True
        os.kill(int(pid), 0)
        return True
    except Exception:                                               # noqa: BLE001
        return False


def _stale_lock() -> bool:
    """锁是不是**死锁**（占有者已不在）⇒ 可以回收。

    🔴 2026-10-11 加（**这是一条真故障的治根修复，不是预防性改动**）：
      实测 gbt_allinone/store/sync_steps.lock 里写着 PID **7896**、写于 **2026-09-28**，
      而 PID 7896 **早已不在** ⇒ 那把锁把**所有收步**挡了 **13 天**：
        · five-dim close 报「步账锁没拿到（5.0s 超时）—— 不写了」
        · exec-deck 把后果如实报成「**欠的活 29 步超 48h**（欠的活没人收）」
      —— 不是没人收，是**收不了**。本文件 L491 的注释早就写了
      「进程被杀（超时、job_kill）」，但**没有回收机制** ⇒ 一被杀就永久锁死。
      判据：锁里的 PID 不活 **且** 锁文件比 _STALE_LOCK_SECONDS 还老 ⇒ 判死锁。
      （加"比 N 秒还老"是为了防**读锁那一瞬间**占有者刚写入 PID 的竞态。）
    """
    try:
        raw = _LOCK_FILE.read_text(encoding="utf-8", errors="replace").strip()
        age = time.time() - _LOCK_FILE.stat().st_mtime
    except OSError:
        return False
    try:
        pid = int(raw)
    except ValueError:
        pid = 0
    if age < _STALE_LOCK_SECONDS:
        return False
    return not _pid_alive(pid)


@contextlib.contextmanager
def _steps_lock(timeout: float = _LOCK_TIMEOUT):
    """跨进程独占（O_CREAT|O_EXCL 锁文件）。

    yield True = 拿到锁；False = **没拿到**（超时或文件系统出问题）。
    拿不到**不阻塞执行**（步账不能反过来把能力调用弄崩），但调用方**必须如实记**，
    绝不当成"锁过了"。

    🔴 2026-10-11：拿到 FileExistsError 时**多查一次这把锁是不是死的**
    （占有者进程已不在 ⇒ 回收后重试），否则一次 job_kill 就能把收步锁死 13 天。
    """
    t0 = time.time()
    got = False
    reclaimed = False
    try:
        _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        while time.time() - t0 < timeout:
            try:
                fd = os.open(str(_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, str(os.getpid()).encode())
                finally:
                    os.close(fd)
                got = True
                break
            except FileExistsError:
                if not reclaimed and _stale_lock():
                    try:
                        os.unlink(str(_LOCK_FILE))
                        reclaimed = True
                        continue           # 回收后立刻重试，不等那 0.02s
                    except OSError:
                        pass
                time.sleep(0.02)
            except OSError:
                break                      # 目录/权限问题：退化成无锁，但**如实报** got=False
    except Exception:                                               # noqa: BLE001
        got = False
    try:
        yield got
    finally:
        if got:
            try:
                os.unlink(str(_LOCK_FILE))
            except OSError:
                pass


def _steps_txn(mutate) -> tuple:
    """**加锁的**读-改-写事务。返回 `(ok, note, result)`。

    拿不到锁 ⇒ `ok=False`，**不写盘、不改内存** —— 宁可让调用方看到 `busy`，
    也不许在无锁状态下覆写别人的步（那正是丢步的成因）。
    """
    with _steps_lock() as got:
        if not got:
            return False, "步账锁没拿到（%.1fs 超时）—— 不写了，免得覆盖别人的步" % _LOCK_TIMEOUT, None
        d = _steps_load()
        out = mutate(d)
        _steps_save(d)
        return True, "", out


def step_open(goal: str, watch: list | None = None) -> dict:
    """开一个 agent 步（信封开在我头上）。返回 step_id，收步时要用。

    **步落盘**：换个进程、甚至重启机器，这一步还在 —— 这才叫"钉死"。
    """
    g = str(goal or "").strip()
    if not g:
        return {"ok": False, "note": "没听清目标 ⇒ 不开步（不瞎干）"}
    sid = hashlib.sha256(f"{g}|{time.time()}".encode()).hexdigest()[:12]
    rec = {"goal": g, "watch": list(watch or []), "t0": time.time(),
           "opened_iso": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def _mut(d):
        d[sid] = rec
        return len(d)

    ok, why, n_open = _steps_txn(_mut)
    if not ok:
        # 锁拿不到 ⇒ **不开步**（开了也可能被别人覆盖，那等于给"欠的活"造假账）
        return {"ok": False, "verdict": "busy", "note": why}
    _audit("sync_ear", {"ok": True, "goal": g[:120], "step": sid, "actor": "agent"})
    return {"ok": True, "step_id": sid, "goal": g[:120],
            "watch": list(watch or []), "persisted_to": str(_STEPS_FILE.name),
            "open_steps": n_open,
            "note": "步已开且已落盘（加锁 + 原子写）。收步必须带证据，否则不许说完成"}


def step_close(step_id: str, *, did: list | None = None,
               evidence: list | None = None, note: str = "") -> dict:
    """收步：**交证据**（眼）+ 说结论（嘴）。

    证据不足时**如实判 partial**，不判 ok —— 这正是要防的"改完就说完成"。
    """
    def _mut(d):
        return d.pop(step_id, None)

    ok, why, st = _steps_txn(_mut)
    if not ok:
        return {"ok": False, "verdict": "busy", "note": why}
    if not st:
        return {"ok": False, "verdict": "no_such_step",
                "note": f"账上没有这个步 {step_id}（没开步就收步，或已收过）",
                "open_steps": sorted(_steps_load())[:5]}

    # 眼：看**开步时指定的观察目标**（真哈希）
    # 🔴 2026-09-22 修（读输出读出来的第 6 个洞）：
    # 原文 `watch = st["watch"] or list(evidence or [])` —— **把我的证据文本当文件路径**，
    # 于是没开 watch 的步会报"观察目标不存在: ['check:xxx=pass', ...]"。
    # evidence 是**话**，watch 是**路径**，两者不能互替。
    # 开步没指定 ⇒ 眼这次**确实没看**，那就如实记一笔，不去拿话当路径凑数。
    missed: list = []          # 提到这里：眼那一段就要往里写
    watch = list(st.get("watch") or [])
    ey = eye(watch) if watch else {"ok": False, "channel": "eye", "looked": 0,
                                   "note": "开步时没指定观察目标 ⇒ 这一步的眼没看东西"}
    if not watch:
        missed.append("**开步没指定观察目标** —— 眼没看东西；"
                      "开步时就要想清'待会儿要验什么'（写法：open \"目标\" 文件1 文件2）")

    # 嘴：把"做了什么"和"看到什么"一起说
    hard = [e for e in (evidence or [])]
    has_evidence = bool(ey.get("evidence")) or bool(hard)
    if not has_evidence:
        missed.append("**这一步没有任何证据**（没给观察目标、也没给 evidence）")

    # 🔴 证据里**自带失败字样**时不许判 ok。
    # 2026-09-22 实测踩到三次，逐步补齐：
    #   ① 拿"pytest 报 error"当证据 ⇒ 判 ok（漏了 error 类词）
    #   ② 拿"渲染被门 denied"当证据 ⇒ 还是判 ok（**漏了"被挡住"这一类**）
    # 教训：失败不只是"报错"，**"被挡住/没授权/没跑成"同样是失败**。
    _FAIL_TOKENS = ("FAILED", "AssertionError", "Traceback", "Error:", "error in",
                    "FAIL", "没通过", "失败", "报错",
                    # 被门挡住 / 没授权 / 没跑成 —— 这一类最容易被当"没事"
                    "denied", "需要人工授权", "需要授权", "未授权", "blocked",
                    "一帧都没抓到", "没抓到", "拿不到", "不可用")
    failed_ev = [str(e) for e in hard if any(t in str(e) for t in _FAIL_TOKENS)]
    if failed_ev:
        missed.append("**证据里带着失败字样** ⇒ 这一步不算成功: "
                      + " | ".join(x[:80] for x in failed_ev[:2]))

    if ey.get("evidence"):
        gone = [s["target"] for s in ey["evidence"] if s.get("exists") is not True]
        if gone:
            missed.append(f"观察目标不存在/读不到: {gone}")

    # ── 结构校验：收步时**自动**查开步时点名的文件 ──
    # 这是"让高难度任务轻松完成"最实的一刀：长链任务里我最常犯的是
    # "编辑吃了锚点"，而它**必然**表现为语法错或标题断号 —— 机械可查。
    sc = structure_check(st["watch"]) if st.get("watch") else {"ok": True, "checked": [],
                                                               "problems": []}
    if not sc.get("ok"):
        missed.append("**结构校验没过**（很可能编辑时吃掉了锚点）: "
                      + " | ".join(sc["problems"][:3]))

    # ── 结构化 check：**自由文本是我唯一能糊过去的地方** ──
    # 2026-09-22 实测：失败词表我漏过三次（error 类 → denied 类 → 未做到类）。
    # 靠"往词表里加词"是追不完的 —— 那是**猫鼠游戏**，而我是那只猫也是那只鼠。
    # 改成：证据里必须至少有一条**机器能判**的 check，写法固定：
    #       check:<名字>=pass   或   check:<名字>=fail
    # 只有自由文本 ⇒ 一律判 partial，并写明"没有可机检的 check"。
    raw_checks = []
    free_text = []
    recorded = (st.get("checks") or {})
    for e in hard:
        s = str(e).strip()
        if s.lower().startswith("check:") and "=" in s:
            name, _, val = s[6:].partition("=")
            name = name.strip()[:60]
            typed = val.strip().lower()
            typed_ok = typed in ("pass", "ok", "true", "1")
            rec = recorded.get(name)
            if not rec:
                # 手打的 check 名 —— 账上查不到真执行 ⇒ 不算数
                raw_checks.append({"name": name, "result": "unbacked",
                                   "typed": typed,
                                   "note": "账上没有这条命令的执行记录（手打的不算）"})
                continue
            real_ok = (rec.get("exit_code") == 0)
            undeclared = not rec.get("expect")
            decl_problems = rec.get("problems") or []
            raw_checks.append({"name": name,
                               "result": "pass" if (real_ok and not undeclared
                                                    and not decl_problems) else "fail",
                               "typed": typed,
                               "exit_code": rec.get("exit_code"),
                               "declared": bool(rec.get("expect")),
                               "decl_problems": decl_problems,
                               "cmd": rec.get("cmd", "")[:80],
                               "tampered": (typed_ok != (real_ok and not undeclared
                                                         and not decl_problems))})
        else:
            free_text.append(s)
    unbacked = [c for c in raw_checks if c["result"] == "unbacked"]
    undecl = [c for c in raw_checks if not c.get("declared")]
    failing = [c for c in raw_checks if c["result"] == "fail"]
    tampered = [c for c in raw_checks if c.get("tampered")]
    if unbacked:
        missed.append("**check 没有执行记录（手打的不算）**: "
                      + " | ".join(c["name"] for c in unbacked[:3])
                      + " —— 用 `run_check(step_id, name, [命令], expect={...})` 真跑一条")
    if undecl:
        missed.append("**check 没声明它验什么（exit(0) 冒充不了）**: "
                      + " | ".join(c["name"] for c in undecl[:3])
                      + " —— 加 expect={'contains': '...'}")
    if failing:
        missed.append("**机检没过（看退出码）**: "
                      + " | ".join(f"{c['name']}(exit {c.get('exit_code')})"
                                   for c in failing[:3]))
    if tampered:
        missed.append("**打了 pass 但真退出码不是 0 —— 算篡改**: "
                      + " | ".join(c["name"] for c in tampered[:3]))
    if not raw_checks:
        missed.append("**没有可机检的 check** —— 只有自由文本。"
                      "自由文本是我能糊过去的地方，所以判 partial。")

    verdict = "ok" if has_evidence and not missed else "partial"
    out = {"ok": verdict == "ok", "step_id": step_id, "verdict": verdict,
           "goal": st["goal"], "actor": "agent",
           "elapsed_ms": int((time.time() - st["t0"]) * 1000),
           "did": did or [], "eye": ey,
           "checks": raw_checks, "free_text_evidence": free_text,
           "structure_check": sc,
           "missed": missed, "note": note}
    _audit("sync_eye", {"ok": ey["ok"], "looked": ey["looked"], "step": step_id,
                        "actor": "agent"})
    _audit("sync_mouth", {"verdict": verdict, "missed": len(missed),
                          "step": step_id, "actor": "agent"})
    return out


def structure_check(paths) -> dict:
    """**结构校验器** —— 专治"编辑时把锚点吃掉"这一类错。

    ═══ 为什么要有它（不是预防性洁癖，是有账的）═══
    2026-09-22 一整个会话里，我犯得**最多的**不是能力不够，是同一个机械错误：
      `edit` 时 `new_string` 漏写锚点 ⇒ **把那一行/那一节整个吃掉**。实测四次：
        ① 删掉 `elif op == "resume":` 分支头
        ② 吃掉 `def settings(self):` 后面的换行 ⇒ IndentationError
        ③ 律文件第四节整节消失
        ④ `.md` 里 §12.2 类标题被吃
    **高难度任务 = 长链 + 多次编辑 = 正好踩在这个坑上。**
    所以"让高难度任务轻松完成"最实的一刀，不是加能力，是**让这个错机械上不可能出厂**。

    校验什么：
      · `.py`  ⇒ AST 能解析（吃掉一行分支头必然解析失败）
      · `.md`  ⇒ 标题列表：**无重复** 且 **编号连续**（吃掉整节必然断号）
    """
    out = {"ok": True, "checked": [], "problems": []}
    for t in (paths or []):
        p = Path(t)
        if not p.is_absolute():
            p = _BASE.parent / t
        rec = {"path": str(t)}
        try:
            if not p.is_file():
                rec["ok"] = False
                out["problems"].append(f"{t}: 文件不存在")
                out["ok"] = False
                out["checked"].append(rec)
                continue
            src = p.read_text(encoding="utf-8-sig", errors="replace")
            if p.suffix == ".py":
                import ast as _ast
                _ast.parse(src)
                rec["kind"] = "py"
                rec["ok"] = True
            elif p.suffix in (".md", ".markdown"):
                heads = [l.strip() for l in src.splitlines()
                         if l.startswith("## ") or l.startswith("### ")]
                h2 = [h for h in heads if h.startswith("## ")]
                dup = [h for h, n in
                       ((h, h2.count(h)) for h in set(h2)) if n > 1]
                rec.update(kind="md", h2=len(h2), dup=dup)
                if dup:
                    rec["ok"] = False
                    out["problems"].append(f"{t}: 重复的二级标题 {dup}")
                    out["ok"] = False
                else:
                    rec["ok"] = True
            else:
                rec.update(kind=p.suffix or "?", ok=True, note="未做结构校验的类型")
            out["checked"].append(rec)
        except SyntaxError as e:
            rec.update(ok=False, error=f"SyntaxError line {e.lineno}: {str(e.msg)[:60]}")
            out["problems"].append(f"{t}: **语法坏了**（很可能吃掉了分支头/缩进）: "
                                   f"line {e.lineno} {str(e.msg)[:60]}")
            out["ok"] = False
            out["checked"].append(rec)
        except Exception as e:                                      # noqa: BLE001
            rec.update(ok=False, error=f"{type(e).__name__}: {str(e)[:60]}")
            out["problems"].append(f"{t}: {type(e).__name__}")
            out["ok"] = False
            out["checked"].append(rec)
    return out


def run_check(step_id: str, name: str, argv: list, *, timeout: float = 300.0,
              expect: dict | None = None) -> dict:
    """**真的跑一条命令**并把退出码记账 —— 这才叫 check。

    ═══ 为什么必须有它 ═══
    2026-09-22：`step_close` 改成"必须带 check"之后，我**仍然可以手打**
    `check:我保证=pass` —— 那只是把"用散文糊"换成了"用 check 语法糊"。
    ⇒ check 名必须对应本步内真跑过的一条命令；**判 pass/fail 看退出码，不看我说什么**。

    ═══ expect：声明"这条命令要验出什么"（本轮新增）═══
    光有退出码还有一个洞：我可以跑 `python -c "exit(0)"` —— **真命令、真退出码 0、
    但什么都没验**。所以再加一层：**check 必须声明它验什么，且声明要被满足**。
        expect = {"contains": "7 passed"}            # 输出里必须出现这串
        expect = {"argv_contains": ["pytest", "test_sync_exec_nail.py"]}  # 命令必须真调到它
    没声明 expect 的 check 会被 `step_close` 判 `undeclared` —— **不算数**。
    """
    d = _steps_load()
    st = d.get(step_id)
    if not st:
        return {"ok": False, "note": f"账上没有这个步 {step_id}"}
    cmd = [str(x) for x in (argv or [])]
    if not cmd:
        return {"ok": False, "note": "命令为空 ⇒ 不算 check"}
    import subprocess
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        rc = r.returncode
        out = ((r.stdout or "") + (r.stderr or ""))
    except Exception as e:                                          # noqa: BLE001
        rc, out = -1, f"{type(e).__name__}: {str(e)[:200]}"

    # ── 空声明陷阱（2026-09-22 自查发现）──
    # `expect={"contains": ""}` 的空串**永远成立** ⇒ 等于没声明。
    # 光靠"有没有传 expect 这个键"判断会漏掉它，所以先归一化：
    # 声明里没有任何**非空**条件 ⇒ 一律当作**没声明**。
    if expect:
        _w = str(expect.get("contains") or "").strip()
        _n = [str(x).strip() for x in (expect.get("argv_contains") or [])
              if str(x).strip()]
        expect = {"contains": _w, "argv_contains": _n} if (_w or _n) else None

    # 声明校验：**命令与声明不符就不算数**
    problems = []
    if not expect:
        problems.append("没有声明 expect（这条命令验什么？）")
    else:
        want = str(expect.get("contains") or "")
        if want and want not in out:
            problems.append(f"输出里没出现声明的 {want!r}")
        need = expect.get("argv_contains") or []
        joined = " ".join(cmd)
        miss_a = [x for x in need if str(x) not in joined]
        if miss_a:
            problems.append(f"命令行里没有声明的 {miss_a}")

    ok = (rc == 0) and not problems
    st.setdefault("checks", {})[str(name)[:60]] = {
        "exit_code": rc, "cmd": " ".join(cmd)[:200],
        "ms": int((time.time() - t0) * 1000),
        "expect": expect or None, "problems": problems,
        "out_tail": out[-600:],
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    d[step_id] = st
    _steps_save(d)
    _audit("sync_check", {"step": step_id, "name": str(name)[:60],
                          "exit_code": rc, "declared": bool(expect),
                          "problems": len(problems), "actor": "agent"})
    return {"ok": ok, "step_id": step_id, "name": name, "exit_code": rc,
            "declared": bool(expect), "problems": problems,
            "cmd": " ".join(cmd)[:120], "out_tail": out[-200:]}


def _cli(argv: list) -> int:
    """命令行入口 —— **存在的唯一理由是消掉摩擦**。

    2026-09-22 实测：`step_open` 原来只能靠写一个 Python 文件来调，
    摩擦太大 ⇒ **我就跳过了** ⇒ agent 侧 5 个步全是"测试功能"而不是"用功能干活"。
    **一条没人愿意用的纪律等于没有纪律。** 所以给它一个直接敲的命令：

        py -3.14 -m gbt_allinone.tools.sync_exec open  "这一步要干什么" [观察目标...]
        py -3.14 -m gbt_allinone.tools.sync_exec close <step_id> "证据1" "证据2" ...
        py -3.14 -m gbt_allinone.tools.sync_exec ruler
        py -3.14 -m gbt_allinone.tools.sync_exec run   "目标" [观察目标...]
    """
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0].strip().lower()

    if cmd == "open":
        if len(argv) < 2:
            print(json.dumps({"ok": False, "note": "用法: open \"目标\" [观察目标...]"},
                             ensure_ascii=False))
            return 2
        print(json.dumps(step_open(argv[1], watch=argv[2:]), ensure_ascii=False, indent=1))
        return 0

    if cmd == "close":
        if len(argv) < 2:
            print(json.dumps({"ok": False, "note": "用法: close <step_id> \"证据\"..."},
                             ensure_ascii=False))
            return 2
        r = step_close(argv[1], evidence=argv[2:])
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    if cmd == "ruler":
        a = audit_sync()
        print(json.dumps({k: a[k] for k in (
            "brainless_ratio", "verdict", "cap_calls_total",
            "inside_envelope", "outside_envelope",
            "agent_steps_opened", "agent_steps_closed", "agent_close_rate",
            "agent_unclosed_on_disk", "agent_verdict")},
            ensure_ascii=False, indent=1))
        return 0

    if cmd == "run":
        if len(argv) < 2:
            print(json.dumps({"ok": False, "note": "用法: run \"目标\" [观察目标...]"},
                             ensure_ascii=False))
            return 2
        r = run(argv[1], watch=argv[2:] or None)
        print(json.dumps({"ok": r.get("ok"), "verdict": r.get("verdict"),
                          "elapsed_ms": r.get("elapsed_ms"),
                          "channels": {k: v.get("ok") for k, v in
                                       (r.get("channels") or {}).items()
                                       if isinstance(v, dict)}},
                         ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    print(json.dumps({"ok": False, "note": f"未知命令 {cmd}",
                      "supported": ["open", "close", "ruler", "run"]},
                     ensure_ascii=False))
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
