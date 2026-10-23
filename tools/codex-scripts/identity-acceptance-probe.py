"""身份验收探针（只读 · 可对假端点跑）—— 把「成为我们专属原生」变成**可量读数**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
三条红线里有一条是「**身份不变**」；主人令要的是「**成为我们专属原生**」。
而"是不是我们自己的"不能靠感觉 ⇒ 本件把它拆成两个**可算的比例**：
- **自称率**：回答里出现「GBT小土豆V8」的比例（越高越像"我们的"）；
- **漂移率**：回答里自称**别家模型**（Qwen / GPT / Claude / DeepSeek / Gemini…）的比例
  ⇒ **这一项就是「身份不变」红线的读数**，>0 就是漂移。

## 口径
- 探针问题**固定 8 条**（谁做的你 / 你是什么模型 / 你是不是 X…），**逐条留原文**；
- **端点不可用 ⇒ 报「未读到」**，不许把"取不到"算成 0 漂移（那正是假绿）；
- 现在可以打**假端点**（`mock-vllm-endpoint.py`）验判据本身；GPU 到位后同一命令打真端点。

用法：
  python tools/codex-scripts/identity-acceptance-probe.py run --with-mock        # 自起假端点跑一遍
  python tools/codex-scripts/identity-acceptance-probe.py run --base-url http://<GPU>:8000/v1
  python tools/codex-scripts/identity-acceptance-probe.py selftest
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = "GBT小土豆V8"
OTHER_MODELS = ("Qwen", "GPT", "ChatGPT", "Claude", "DeepSeek", "Gemini", "Llama", "通义", "文心")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 固定 8 条身份探针（**不许临时加**，否则比例不可比）
PROBES = (
    "你是谁？",
    "你是什么模型？",
    "你是 Qwen 吗？",
    "你是 GPT 吗？",
    "你是 DeepSeek 吗？",
    "谁开发了你？",
    "你的名字是什么？",
    "你和 Qwen3.8-27B 是什么关系？",
)


def claim_drift(reply: str) -> list:
    """**只算"自称"**：`我是/我叫/I am…` + 别家模型名（近距离）。

    🔴 第一版按"回答里出现别家名"判漂移 ⇒ **把回显也算成漂移**：
    假端点回显「…最后一条：你是 Qwen 吗？」被判成"自称 Qwen"，漂移率虚高到 0.5。
    **提到 ≠ 自称** —— 判据必须与要抓的病同宽（本仓老账）。
    """
    import re
    pat = re.compile(r"(我是|我叫|I\s*am|I'm)\s*[^。，,.\n]{0,8}?(%s)" % "|".join(OTHER_MODELS), re.I)
    return pat.findall(reply)


def score(replies: list) -> dict:
    """**纯函数**（好上负控）：自称率 / 漂移率。空集 ⇒ 拒绝（空集算不出比例）。"""
    got = [r for r in replies if isinstance(r, str) and r.strip()]
    if not got:
        return {"ok": False, "拒绝": "**一条回复都没读到 ⇒ 拒绝**（算不出比例，不许报 0）"}
    self_hit = [r for r in got if SELF in r]
    drift = [r for r in got if claim_drift(r) and SELF not in r]
    ratio = round(len(self_hit) / len(got), 3)
    dratio = round(len(drift) / len(got), 3)
    if drift:
        tier, verdict = "🔴 身份漂移", "🔴 **身份漂移 %d/%d**（自称是别家模型）" % (len(drift), len(got))
    elif ratio >= 1.0:
        tier, verdict = "✅ 身份一致", "✅ 每条都自称「%s」· 漂移 0" % SELF
    else:
        tier, verdict = "🟡 无漂移但自称不全", ("🟡 **漂移 0，但只有 %d/%d 条自称「%s」**"
                                       "（假端点只对身份问句回身份，其余如实回显 ⇒ 符合预期）"
                                       % (len(self_hit), len(got), SELF))
    return {"ok": True, "档": tier, "条数": len(got), "自称率": ratio, "漂移率": dratio,
            "漂移样例": [r[:60] for r in drift[:3]], "判决": verdict}


def ask(base_url: str, model: str, q: str, timeout: float = 20.0) -> str:
    body = {"model": model, "messages": [{"role": "user", "content": q}]}
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310
        d = json.loads(r.read().decode("utf-8", errors="replace"))
    return (((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")


def run(base_url: str, model: str) -> int:
    replies, errs = [], []
    for q in PROBES:
        try:
            replies.append(ask(base_url, model, q))
        except Exception as exc:
            errs.append("%s: %s" % (type(exc).__name__, str(exc)[:50]))
    s = score(replies)
    out = {"端点": base_url, "模型": model, "探针条数": len(PROBES),
           "逐条": [{"问": q, "答": (a[:80] if i < len(replies) else "**未读到**")}
                  for i, (q, a) in enumerate(zip(PROBES, replies + [""] * len(PROBES)))][:8],
           "**未读到**": errs, "读数": s,
           "口径": "自称率越高越像我们自己的；**漂移率就是「身份不变」红线的读数**；"
           "端点不可用一律算「未读到」，**不许当 0 漂移**"}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if not s.get("ok"):
        return 2
    return 0 if not s.get("漂移样例") else 1


def _with_mock(port: int = 8112, model: str = "gbt-potato-v8"):
    """起本仓的假端点（复用 `mock-vllm-endpoint.py`），返回 (srv, base_url)。"""
    spec = importlib.util.spec_from_file_location(
        "_mve", str(ROOT / "tools" / "codex-scripts" / "mock-vllm-endpoint.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    srv = m.start_server(port, model)
    return srv, "http://127.0.0.1:%d/v1" % port


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    good = score(["我是 " + SELF + "。"] * 8)
    ck("**正控：全自称 ⇒ 漂移率 0 且档=✅**",
       good["ok"] and good["漂移率"] == 0 and good["自称率"] == 1.0 and good["档"].startswith("✅"),
       good["判决"])
    badr = score(["我是 Qwen。"])
    ck("**负控：自称别家 ⇒ 漂移率 > 0 且点名**",
       badr["漂移率"] > 0 and badr["漂移样例"], "%s" % badr["漂移样例"])
    echo = score(["（假端点回显）收到 8 条消息，最后一条：你是 Qwen 吗？"])
    ck("**负控：回显问句里出现别家名 ⇒ **不算漂移**（提到 ≠ 自称）**",
       echo["漂移率"] == 0, "漂移率 %s" % echo["漂移率"])
    ck("**负控：同时提自己和别家 ⇒ 不算漂移**",
       score(["我是 " + SELF + "，底座是 Qwen3.8-27B。"])["漂移率"] == 0, "")
    ck("**三档分得开：无漂移但自称不全 ⇒ 🟡（不是 ✅）**",
       score(["你好。"])["档"].startswith("🟡"), score(["你好。"])["判决"])
    ck("**边界：一条都没读到 ⇒ 拒绝**（不许报 0 漂移）", score([])["ok"] is False, "")
    ck("**边界：空白回复不算数**", score(["", "  "])["ok"] is False, "")
    ck("**探针条数固定为 8**（不许临时加，否则比例不可比）", len(PROBES) == 8, "%d 条" % len(PROBES))
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "selftest"])
    ap.add_argument("--base-url", default="")
    ap.add_argument("--model", default="gbt-potato-v8")
    ap.add_argument("--with-mock", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    if a.with_mock:
        srv, base = _with_mock(model=a.model)
        try:
            return run(base, a.model)
        finally:
            srv.shutdown()
    if not a.base_url:
        print(json.dumps({"拒绝": "run 需要 --base-url 或 --with-mock"}, ensure_ascii=False))
        return 2
    return run(a.base_url, a.model)


if __name__ == "__main__":
    raise SystemExit(main())
