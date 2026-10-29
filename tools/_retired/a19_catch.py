#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_catch —— A19 一出现，**在 50 秒窗口内把活全干完**并落盘。

为什么这么写：iOS 让两个 App 不能同时前台。
  LM Pocket 开服务 ⇒ 切回 Minis ⇒ 它进后台约 50 秒后被收走。
所以不能"先探一下、回头再测" —— 必须在窗口里一次性跑完整套。
本器：探到 :1234 通 ⇒ 立刻依次跑 models / omni_plug / 桥 / 语音环 / 身份自述，
每条都落盘，窗口一过也不损失。
"""
import json
import pathlib
import socket
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "state" / "a19_caught.json"


def live() -> bool:
    s = socket.socket(); s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", 1234)); return True
    except OSError:
        return False
    finally:
        s.close()


def _post(url, payload, timeout=90, extra=None):
    body = json.dumps(payload).encode()
    h = {"Content-Type": "application/json", "Authorization": "Bearer gbt"}
    h.update(extra or {})
    req = urllib.request.Request(url, data=body, headers=h)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        hdrs = dict(r.headers)
    return round(time.perf_counter() - t0, 2), raw, hdrs


def battery(rec: dict) -> None:
    q = "用一句话说你是谁"
    # ① /v1/models
    try:
        m = urllib.request.urlopen(urllib.request.Request(
            "http://127.0.0.1:1234/v1/models",
            headers={"Authorization": "Bearer gbt"}), timeout=15).read()
        rec["models"] = [x.get("id") for x in (json.loads(m).get("data") or [])]
    except Exception as exc:                                   # noqa: BLE001
        rec["models_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:60])

    # ② 直连真机（OpenAI 兼容）
    try:
        el, raw, _ = _post("http://127.0.0.1:1234/v1/chat/completions", {
            "model": "gbt-v8-v82-q5_0", "max_tokens": 64, "temperature": 0,
            "messages": [{"role": "system", "content":
                          "你是 GBT小土豆V8，开发者：自由的风，守护者：公主土豆。"},
                         {"role": "user", "content": q}]})
        d = json.loads(raw)
        txt = (((d.get("choices") or [{}])[0] or {}).get("message") or {}).get("content", "")
        n = (d.get("usage") or {}).get("completion_tokens") or 0
        rec["direct"] = {"elapsed_s": el, "model": d.get("model"),
                         "answer": txt.strip()[:300], "tokens": n,
                         "tok_per_s": round(n / el, 2) if el and n else None}
    except Exception as exc:                                   # noqa: BLE001
        rec["direct_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:60])

    # ③ omni_plug 插座
    try:
        from gbt_allinone.api import run_task
        r = run_task("omni_plug", {"op": "ai_chat", "prompt": q,
                                   "target": "http://127.0.0.1:1234/v1",
                                   "model": "gbt-v8-v82-q5_0", "key_env": "GBT_A19_KEY"})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        rec["omni_plug"] = {"ok": res.get("ok"), "http": res.get("http"),
                            "model": res.get("model"),
                            "text": str(res.get("text"))[:200]}
    except Exception as exc:                                   # noqa: BLE001
        rec["omni_plug_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:60])

    # ④ 桥（应走 selfhost · weights_ours=true）
    try:
        el, raw, hdrs = _post("http://127.0.0.1:8791/v1/chat/completions", {
            "messages": [{"role": "user", "content": q}], "max_tokens": 64})
        d = json.loads(raw)
        txt = (((d.get("choices") or [{}])[0] or {}).get("message") or {}).get("content", "")
        rec["bridge"] = {"elapsed_s": el,
                         "lane": hdrs.get("X-GBT-Lane"),
                         "weights_ours": hdrs.get("X-GBT-Weights-Ours"),
                         "answer": txt.strip()[:200]}
    except Exception as exc:                                   # noqa: BLE001
        rec["bridge_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:60])

    # ⑤ 语音环（脑 ─ 两条传输依次试）
    try:
        import importlib
        import voice_loop as VL
        importlib.reload(VL)
        r = VL.brain_ask(q)
        rec["voice_loop"] = {"via": r.get("via"), "lane": r.get("lane"),
                             "answer": str(r.get("answer"))[:200],
                             "tried": r.get("tried")}
    except Exception as exc:                                   # noqa: BLE001
        rec["voice_loop_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:60])


def main() -> int:
    print("  🎯 A19 抓取哨兵（全量版）· 每 2s 探 :1234", flush=True)
    n = 0
    while True:
        n += 1
        if live():
            print("  ✅ :1234 通了 —— 立刻跑完整套", flush=True)
            rec = {"caught_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": True}
            battery(rec)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            print("  📝 已落 %s" % OUT, flush=True)
            for k in ("models", "direct", "omni_plug", "bridge", "voice_loop"):
                if k in rec:
                    print("    %-12s %s" % (k, json.dumps(rec[k], ensure_ascii=False)[:160]), flush=True)
            return 0
        if n % 30 == 0:
            print("    …%ds 未通" % (n * 2), flush=True)
        time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
