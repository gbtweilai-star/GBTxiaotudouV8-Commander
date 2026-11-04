# -*- coding: utf-8 -*-
"""local_llm —— 本机算力（llama.cpp @ 127.0.0.1:8111）的**严格限定**入口

主人令（2026-11-04）：「她这个速度不能使用我们的触手双向绑定每一页，
覆盖每一个代码每一页可以和所有页面互通，实现精准直达脉冲提速」。

—— 这一条实测证实了，而且比预想更糟：

| 用法                  | 实测结果                        | 判定 |
|---------------------|-----------------------------|----|
| 带 4020 tokens 系统提示 | 8~13 秒/次                    | 不可用 |
| 零系统提示 · 短问答        | 1.10 / 1.42 / 2.44 秒       | 勉强 |
| 意图分类（直接选能力名）      | 1/3 命中（「读图里的字」→ detect）  | **不可用** |
| 大类判定（读字/看界面/找物体…） | **3/7 命中**（「照片里有几只猫」→ 读字） | **不可用** |
| 并发 8 路算术            | 8/8 全对，零串台                 | 可用 |
| JSON 结构化抽取          | 指令跟随正常                     | 可用 |

**所以本模块不提供 classify / route。** 不是懒得做，是做了会害人：
一个 43% 准确率的分类器接在路由前面，比没有更糟 —— 它会把「看按钮」
稳定地送去读字。路由靠**索引直达**（router.py 的 L1 规则，0 ms 且准），
这个模型只做**确定性任务**：算术、格式转换、JSON 抽取。

—— 三条硬边界 ——
1. **不做逐页绑定**：1.4s/页 × 上千页 = 几十分钟，物理上就不成立。
   页面互通靠 `codepage.py` 的索引直达（毫秒级），不靠模型一页页读。
2. **不做语义判定**：它分不清「读字」和「找猫」，交给规则和云端。
3. **慢就放弃**：所有调用有超时；超时/不可用一律 `ok=False` + `fallback` 提示，
   绝不假装算完 —— 调用方据此回落云端，而不是拿一个空结果当真。

本机实况（2026-11-04）：i5-1340P / 15.7GB RAM / Iris Xe 2GB；
模型 gbt-v8-v82-q5_0.gguf（4.88GB，Qwen2 架构 28 层 / 32K ctx / Q5_0）；
llama-server build 12032；生成 3.22 tok/s，prefill ~32 tok/s ⇒ **短任务才有意义**。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8111"
ENV_BASE = "GBT_LOCAL_LLM_BASE"
TIMEOUT = 90.0          # 单次总超时（秒）：超了就是超了，不给它拖死调用方的机会
MAX_TOKENS = 256        # 短任务上限；要长输出请用云端


def _base() -> str:
    import os
    return (os.environ.get(ENV_BASE) or BASE).rstrip("/")


def _post(path: str, body: dict, timeout: float = TIMEOUT) -> tuple:
    req = urllib.request.Request(_base() + path,
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    return (time.time() - t0), raw


def health() -> dict:
    """探活。**不缓存**：服务随时可能被主人停掉，缓存会骗人。"""
    try:
        t0 = time.time()
        with urllib.request.urlopen(_base() + "/health", timeout=3) as r:
            body = r.read().decode("utf-8", "replace")
        return {"ok": True, "up": True, "ms": int((time.time() - t0) * 1000),
                "base": _base(), "body": body[:120]}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "up": False, "base": _base(),
                "reason": "本地 LLM 未运行：%s: %s" % (type(exc).__name__, str(exc)[:120]),
                "start": r"payload\tools\start_local_llm.ps1"}


def _chat(messages, max_tokens: int = MAX_TOKENS, temperature: float = 0.0,
          timeout: float = TIMEOUT) -> dict:
    body = {"model": "local", "messages": messages,
            "max_tokens": int(max_tokens), "temperature": float(temperature),
            "stream": False}
    try:
        dt, raw = _post("/v1/chat/completions", body, timeout)
        d = json.loads(raw)
        msg = (d.get("choices") or [{}])[0].get("message") or {}
        usage = d.get("usage") or {}
        return {"ok": True, "reply": (msg.get("content") or "").strip(),
                "elapsed_ms": int(dt * 1000),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "tok_per_s": round((usage.get("completion_tokens") or 0) / max(dt, 1e-6), 2)}
    except urllib.error.URLError as exc:
        return {"ok": False, "reason": "连不上本地 LLM：%s" % str(exc)[:160],
                "fallback": "改用云端，或先跑 tools\\start_local_llm.ps1"}
    except TimeoutError:
        return {"ok": False, "reason": "本地 LLM 超时（%.0fs）—— 慢就是不能用" % timeout,
                "fallback": "改走云端"}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "%s: %s" % (type(exc).__name__, str(exc)[:160])}


def ask(prompt: str, max_tokens: int = MAX_TOKENS, temperature: float = 0.0) -> dict:
    """短问答。**无系统提示** —— 带上系统提示就退化成 8~13 秒（实测）。"""
    if not prompt:
        return {"ok": False, "reason": "需要 prompt"}
    return _chat([{"role": "user", "content": str(prompt)}], max_tokens, temperature)


def calc(expr: str) -> dict:
    """算术（唯一实测稳的用法：并发 8/8、串行 8/8 全对）。

    让模型只回数字 —— 它算得对，但一让它解释就会绕。
    """
    if not expr:
        return {"ok": False, "reason": "需要 expr：要算的式子"}
    r = _chat([{"role": "user", "content":
                "只回数字，不要过程不要单位。\n算：%s\n=" % expr}], max_tokens=24)
    if not r.get("ok"):
        return r
    r["expr"] = expr
    r["answer"] = (r.get("reply") or "").strip()
    return r


def extract(text: str, fields) -> dict:
    """结构化抽取：给文本 + 要的字段，回 JSON。实测指令跟随正常。"""
    if not text:
        return {"ok": False, "reason": "需要 text：要抽取的原文"}
    if not fields:
        return {"ok": False, "reason": "需要 fields：要抽的字段名列表"}
    if isinstance(fields, str):
        fields = [f.strip() for f in fields.replace("，", ",").split(",") if f.strip()]
    r = _chat([{"role": "user", "content":
                "从文本里抽取字段，只回 JSON 对象，不要解释。\n字段：%s\n文本：%s"
                % (", ".join(fields), str(text)[:2000])}], max_tokens=400)
    if not r.get("ok"):
        return r
    raw = (r.get("reply") or "").strip()
    # 模型偶尔裹 ```json ```，剥掉再解
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        r["data"] = json.loads(raw.strip())
    except Exception:                                              # noqa: BLE001
        r["data"] = None
        r["note"] = "模型没给出可解析 JSON，原文见 reply"
    return r


def status() -> dict:
    """现况 + **诚实的用途边界**（写进返回值，省得下次又被当成万能大脑）。"""
    h = health()
    out = {"ok": h.get("ok"), "health": h,
           "supported": ["ask", "calc", "extract", "status", "bench"],
           "refused": {
               "classify": "实测 1/3 命中 —— 43%% 的分类器接在路由前比没有更糟",
               "route": "同上；路由靠 router.py 的 L1 规则（0 ms）",
               "page_bind": "1.4s/页 × 上千页不成立；页面互通靠 codepage.py 索引",
           },
           "limits": {"timeout_s": TIMEOUT, "max_tokens": MAX_TOKENS,
                      "no_system_prompt": "带系统提示会退化到 8~13s/次"}}
    if h.get("ok"):
        out["note"] = "只做确定性短任务（算术/抽取/格式）；语义判定与分类一律不要交给它"
    return out


def bench() -> dict:
    """现场复测速度 —— 数字自己跑，不引旧账。"""
    if not health().get("ok"):
        return {"ok": False, "reason": "服务没起，先 start_local_llm.ps1"}
    cases = [("2+3", "5"), ("17*23", "391"), ("100-58", "42")]
    rows = []
    for expr, want in cases:
        r = calc(expr)
        rows.append({"expr": expr, "want": want, "got": r.get("answer"),
                     "ok": str(r.get("answer") or "").replace(",", "") == want,
                     "ms": r.get("elapsed_ms"), "tok_per_s": r.get("tok_per_s")})
    hit = sum(1 for x in rows if x["ok"])
    ms = [x["ms"] for x in rows if x.get("ms")]
    return {"ok": True, "rows": rows, "hit": "%d/%d" % (hit, len(rows)),
            "avg_ms": int(sum(ms) / len(ms)) if ms else None}


def run(op: str = "status", **kw) -> dict:
    o = str(op or "status").strip()
    if o in ("status", "health"):
        return status()
    if o in ("bench", "speed"):
        return bench()
    if o in ("ask", "chat", "q"):
        return ask(kw.get("prompt") or kw.get("q") or kw.get("text") or "",
                   int(kw.get("max_tokens") or MAX_TOKENS),
                   float(kw.get("temperature") or 0.0))
    if o in ("calc", "math"):
        return calc(kw.get("expr") or kw.get("prompt") or "")
    if o in ("extract", "json"):
        return extract(kw.get("text") or "", kw.get("fields") or [])
    if o in ("classify", "route", "page_bind"):
        # 不让它做 —— 但要说清楚为什么，且给出该走的路
        return {"ok": False,
                "refused": o,
                "reason": "本机模型不适合做%s：实测意图分类 1/3、大类判定 3/7 命中，"
                          "且 1.4s/次 —— 慢且不准的分类器接在路由前比没有更糟" % o,
                "use_instead": {"classify": "router.py L1 规则（0 ms）",
                                "route": "router.py / api.run_task",
                                "page_bind": "codepage.py 索引直达"}.get(o, "云端模型")}
    return {"ok": False, "reason": "未知 op: %s" % o,
            "supported": ["status", "bench", "ask", "calc", "extract"]}
