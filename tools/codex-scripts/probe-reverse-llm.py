# -*- coding: utf-8 -*-
"""反向调用大模型：走唯一门 run_task → omni_plug op=ai_control → 任意 OpenAI 兼容端点。

用途：产出**可贴进文档的脱敏 log**（text / tool_calls / usage），证明"万能插不只是被插，
它还能反插别人的大模型"。

纪律（照 _ai_call 自己的钉）：
  · 钥匙只回**槽名**，永不回显明文；本脚本额外做一遍兜底脱敏（把任何 sk-… 打成 sk-***）；
  · 端点只认 https；拒重定向（由 _ai_call 内部保证）；
  · 缺钥匙 / 端点上不去 ⇒ 如实报，不伪造 text/usage。

用法：
  py -3.14 -X utf8 tools/codex-scripts/probe-reverse-llm.py            # 跑 deepseek + openai
  py -3.14 -X utf8 tools/codex-scripts/probe-reverse-llm.py --only deepseek
产物：
  outputs/reverse-call/<provider>-raw.json          （门原样回执，已脱敏）
  outputs/open-source-release/data/reverse-call-live.json（汇总，给文档引用）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs" / "reverse-call"
DATA = ROOT / "outputs" / "open-source-release" / "data"

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_capability",
        "description": "按名字取一位能力位的说明",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string"}},
                       "required": ["name"]},
    },
}]

PROMPT = "路由一下：把一份 Markdown 转成 PPT 该用哪个能力位？只回一句理由，并调用工具把位名取出来。"

PROVIDERS = {
    "deepseek": {"target": "https://api.deepseek.com/v1", "key_env": "deepseek",
                 "model": "deepseek-chat"},
    "openai": {"target": "https://api.openai.com/v1", "key_env": "openai",
               "model": "gpt-4o-mini"},
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"hf_[A-Za-z0-9]{10,}"),
]


def scrub(obj):
    """递归脱敏：任何像 key 的字符串都打成 sk-***（只保留"有多少位"这种无信息量的事实）。"""
    if isinstance(obj, str):
        out = obj
        for pat in SECRET_PATTERNS:
            out = pat.sub(lambda m: (m.group(0)[:3] + "***"), out)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    return obj


def dig(env):
    """信封是多层的：往里挖到"带 ok 且带 key_slot/text/usage"的那一层（不许只读第一层）。"""
    cur, hops = env, 0
    while isinstance(cur, dict) and hops < 5:
        if "key_slot" in cur or ("text" in cur and "http" in cur) or cur.get("reason") == "没有可用钥匙":
            return cur
        nxt = cur.get("result") if isinstance(cur.get("result"), dict) else None
        if nxt is None:
            break
        cur, hops = nxt, hops + 1
    return cur if isinstance(cur, dict) else {}


def call(provider: str, mode: str = "tool") -> dict:
    """mode=tool 强制调工具（拿 tool_calls）；mode=text 不给工具（拿 text）。"""
    from gbt_allinone import run_task
    cfg = PROVIDERS[provider]
 # 契约要点（2026-10-21 现场抓到的）：`op=ai_control` 读的是**顶层字段**（kw），不是 args 包里。
    #    第一版照 `op=run` 的习惯塞进 args ⇒ key_env/messages 全变 None ⇒ 门回"没有可用钥匙"。
    #    只有 `op=run` 才用 args。
    payload = {"op": "ai_control", "target": cfg["target"],
               "key_env": cfg["key_env"], "model": cfg["model"],
               "max_tokens": 200,
               "messages": [{"role": "user", "content": PROMPT}]}
    if mode == "tool":
        payload["tools"] = TOOLS
        payload["tool_choice"] = {"type": "function", "function": {"name": "get_capability"}}
    t0 = time.perf_counter()
    try:
        env = run_task("omni_plug", payload) or {}
    except Exception as exc:                                   # noqa: BLE001
        env = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
    dt = round(time.perf_counter() - t0, 2)
    inner = dig(env)
    rec = {
        "provider": provider,
        "mode": mode,
        "target": cfg["target"],
        "model": cfg["model"],
        "elapsed_s": dt,
        "gate_envelope_keys": sorted(env.keys()) if isinstance(env, dict) else str(type(env)),
        "ok": bool(inner.get("ok")),
        "http": inner.get("http"),
        "key_slot": inner.get("key_slot") or ("vault:" + cfg["key_env"] if inner.get("ok") else None),
        "model_returned": inner.get("model"),
        "text": inner.get("text"),
        "tool_calls": inner.get("tool_calls") or [],
        "usage": inner.get("usage") or {},
        # 拒绝路径必须带上游原话（P19）：401/429 这类要能看到上游说了什么
        "upstream": (inner.get("raw") or inner.get("未读到") or inner.get("error")
                     or inner.get("reason") or inner.get("why")),
        "reason": inner.get("reason") or inner.get("why") or inner.get("error"),
        "missing_scopes": env.get("missing_scopes") if isinstance(env, dict) else None,
        "how_to_grant": env.get("how_to_grant") if isinstance(env, dict) else None,
    }
    return scrub(rec)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", choices=["", "deepseek", "openai"])
    ap.add_argument("--mode", default="tool", choices=["tool", "text"])
    a = ap.parse_args()
    order = [a.only] if a.only else ["deepseek", "openai"]
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    rows = []
    for provider in order:
        rec = call(provider, a.mode)
        rows.append(rec)
        p = OUT / ("%s-%s-raw.json" % (provider, a.mode))
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        flag = "OK " if rec["ok"] else "MISS"
        print("%s %-9s http=%s · %ss · slot=%s · usage=%s · tool_calls=%d"
              % (flag, provider, rec["http"], rec["elapsed_s"], rec["key_slot"],
                 rec["usage"] or {}, len(rec["tool_calls"])))
        if not rec["ok"]:
            print("      原因：%s" % (rec["reason"] or "（门未放行）"))
            if rec["missing_scopes"]:
                print("      缺票：%s" % rec["missing_scopes"])
        else:
            print("      text=%r" % ((rec["text"] or "")[:120]))
            for tc in rec["tool_calls"][:2]:
                fn = (tc.get("function") or {})
                print("      tool_call: %s(%s)" % (fn.get("name"), str(fn.get("arguments"))[:80]))

    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "schema": "reverse-call-live-v1",
           "note": "走唯一门 run_task → omni_plug op=ai_control；钥匙只回槽名，已二次脱敏",
           "rows": rows}
    (DATA / "reverse-call-live.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n落账 →", DATA / "reverse-call-live.json")
    print("逐条 →", OUT)
    return 0 if any(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
