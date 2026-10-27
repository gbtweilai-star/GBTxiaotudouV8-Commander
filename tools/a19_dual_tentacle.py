#!/usr/bin/env python3
"""A19 双触手 —— 以大脑执行层为核心，一根喂推理、一根把输出交回排布

主人令（2026-10-28 原话）：
  「以大脑执行层为核心生出两根触手对已经量化触手双向绑定的A19进行连接，
    一根喂推理一根返回输出大脑执行层进行排布」

结构：
                    ┌──────────────┐
                    │  大脑执行层   │  brain_route / brain_execute
                    └──┬────────┬──┘
              ①喂推理  │        │  ②返回输出
                 ┌─────▼──┐  ┌──▼──────┐
                 │a19_feed│  │a19_return│   两根触手，各自双向绑定
                 └─────┬──┘  └──▲──────┘
                       │        │
                    ┌──▼────────┴──┐
                    │  A19（量化）  │  127.0.0.1:1234 · key=gbt
                    └──────────────┘

两根触手的职责**严格分开**：
  a19_feed   —— 只负责"喂"：把大脑给的意图 + 环形窗口上下文推进模型
  a19_return —— 只负责"回"：把模型输出**交回大脑执行层**，由大脑排布下一步

为什么不合成一根：喂和回的错误面不同 ——
  喂错了（上下文没进去 / 超窗）要在喂这侧报；
  回错了（输出跑偏 / 幻觉）要在回这侧报。
  合成一根就只能报"整体失败"，分不清哪一头坏。

口径：
  · 上下文走 ring_context（有界窗口 + 溢出落库 + 秒查）——不自己攒字符串
  · 排布走 brain_route（自称谓 → 词表 → 语义），不自己拍脑袋
  · 两根触手都经 tentacle_bind 双向绑定到 A19 端点资产
  · 失败分类记账：feed_failed / model_down / empty_out / return_failed

用法：
  python3 tools/a19_dual_tentacle.py --once "介绍一下你自己"
  python3 tools/a19_dual_tentacle.py --loop 3
  python3 tools/a19_dual_tentacle.py --selftest      # 起桩容器自测，不依赖 A19 真开
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HOST, PORT, KEY = "127.0.0.1", 1234, "gbt"
FEED = "a19_feed"            # 触手一：喂推理
RET = "a19_return"           # 触手二：返回输出
LEDGER = ROOT / "state" / "a19_dual.jsonl"
RING = "a19_dual"


def log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def bind_tentacles() -> dict:
    """两根触手各绑一次 A19 端点资产（双向绑定）。"""
    out = {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tb", str(ROOT / "tools" / "tentacle_bind.py"))
        tb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tb)                          # type: ignore
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": "tentacle_bind 不可用: %s" % exc}
    asset = str(ROOT / "runtime" / "a19_endpoint.json")
    pathlib.Path(asset).parent.mkdir(parents=True, exist_ok=True)
    if not pathlib.Path(asset).exists():
        pathlib.Path(asset).write_text(json.dumps(
            {"host": HOST, "port": PORT, "key": KEY,
             "note": "A19 LM Pocket 端点（量化权重 gbt-v8-v82-q5_0）"},
            ensure_ascii=False, indent=1), encoding="utf-8")
    for t in (FEED, RET):
        try:
            tb.bind(asset, t, note="A19 双触手·%s" % t, quiet=True)
            out[t] = True
        except Exception as exc:                              # noqa: BLE001
            out[t] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    return {"ok": all(v is True for v in out.values()), "asset": asset, "bind": out}


def ring():
    from gbt_allinone.llm.ring_context import RingContext
    return RingContext(name=RING, window_chars=6000)


def model_up(t=1.5) -> bool:
    s = socket.socket(); s.settimeout(t)
    try:
        s.connect((HOST, PORT)); return True
    except OSError:
        return False
    finally:
        s.close()


def a19_chat(messages: list[dict], max_tokens: int = 200, timeout: float = 180):
    body = json.dumps({"messages": messages, "max_tokens": max_tokens,
                       "temperature": 0}, ensure_ascii=False).encode()
    s = socket.socket(); s.settimeout(timeout)
    try:
        s.connect((HOST, PORT))
        s.sendall(b"POST /v1/chat/completions HTTP/1.0\r\nHost: x\r\n"
                  b"Authorization: Bearer " + KEY.encode() + b"\r\n"
                  b"Content-Type: application/json\r\n"
                  b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        buf = b""
        t0 = time.perf_counter()
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        dt = time.perf_counter() - t0
        head, _, raw = buf.partition(b"\r\n\r\n")
        first = head.split(b"\r\n")[0].decode("latin-1") if head else ""
        if " 200" not in first:
            return {"ok": False, "why": first or "无响应"}
        d = json.loads(raw)
        txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        u = d.get("usage") or {}
        return {"ok": True, "text": txt.strip(), "s": round(dt, 2),
                "model": d.get("model"),
                "ctok": u.get("completion_tokens") or 0,
                "tps": round((u.get("completion_tokens") or 0) / dt, 2) if dt else None}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, str(exc)[:100])}
    finally:
        s.close()


def feed(rc, intent: str) -> dict:
    """触手一：喂推理。把意图推进环，再把环的有界窗口整个喂给模型。"""
    rc.push("user", intent)
    msgs = rc.window()
    t0 = time.perf_counter()
    payload_chars = sum(len(m.get("content") or "") for m in msgs)
    r = a19_chat(msgs, max_tokens=200)
    if not r["ok"]:
        return {"tentacle": FEED, "ok": False, "stage": "feed_failed",
                "why": r["why"], "window_msgs": len(msgs),
                "window_chars": payload_chars}
    if not r.get("text"):
        return {"tentacle": FEED, "ok": False, "stage": "empty_out",
                "window_msgs": len(msgs), "window_chars": payload_chars}
    return {"tentacle": FEED, "ok": True, "model": r.get("model"),
            "window_msgs": len(msgs), "window_chars": payload_chars,
            "s": r["s"], "tps": r.get("tps"), "text": r["text"],
            "ms": round((time.perf_counter() - t0) * 1000)}


def give_back(rc, out_text: str) -> dict:
    """触手二：把输出交回大脑执行层。

    🔴 2026-10-28 改：原来直接拿她的输出当 intent 去 `brain_route`
       —— 那是在问"这段话像哪个能力位"，问错了问题。
       实测她的自述「我是 GBT小土豆V8。开发者：自由的风…」被路由成
       `command_chain`，跟内容毫无关系。

       正确做法是用**大脑执行层本来就有的「守望」位** `llm_watch`：
       它的职责逐字就是「每次 LLM 输出过后**当场过机器判据**
       —— 无证据的「已完成」声明 / 越权声明 / 机器事实无现读 /
       自相矛盾 / claims 无 evidence / 数字对不上；命中就进主脑注意力队列」。

       而且它自己写明「只认可机检的错，语义幻觉判不了就如实写判不了」——
       这正是我们要的口径：**不冒充判过**。

    返回两件事：
      ① 守望判据：命中几条、是否进队
      ② 下一步落位：仍然问 brain_route，但只当参考（它降级就标出来）
    """
    rc.push("assistant", out_text)
    out = {"tentacle": RET, "ok": True, "returned_chars": len(out_text)}

    # ① 守望判据（主）
    try:
        from gbt_allinone.api import run_task
        r = run_task("llm_watch", {"op": "review", "answer": out_text,
                                   "claims": [], "evidence": []})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        hits = res.get("hits") or []
        out["watch"] = {
            "ok": bool(res.get("ok")),
            "hits": len(hits),
            # 命中项的字段是 code（不是 kind/rule），并带 severity 与 fix
            "codes": [h.get("code") for h in hits][:5],
            "severity": [h.get("severity") for h in hits][:5],
            "fixes": [h.get("fix") for h in hits][:2],
            "queued": res.get("queued") or 0,
            "note": res.get("note") or res.get("why") or "",
        }
    except Exception as exc:                                  # noqa: BLE001
        out["watch"] = {"ok": False, "why": "%s: %s"
                        % (type(exc).__name__, str(exc)[:100])}

    # ② 下一步落位（参考，不执行）
    try:
        from gbt_allinone.api import run_task
        r = run_task("brain_route", {"intent": out_text[:200]})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        best = res.get("best") or {}
        out["route"] = {"path": res.get("path"),
                        "degraded": bool(res.get("degraded")),
                        "next": best.get("kind"),
                        "note": "仅作参考；输出是自然语言时它多半不相关"}
    except Exception as exc:                                  # noqa: BLE001
        out["route"] = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:80])}

    out["ok"] = bool((out.get("watch") or {}).get("ok"))
    return out


def one_turn(rc, intent: str) -> dict:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "intent": intent[:120]}
    f = feed(rc, intent)
    rec["feed"] = f
    if not f["ok"]:
        rec["ok"] = False
        rec["stage"] = f["stage"]
        log(rec)
        return rec
    g = give_back(rc, f["text"])
    rec["return"] = g
    rec["ok"] = bool(g["ok"])
    rec["stage"] = "done" if g["ok"] else g.get("stage")
    log(rec)
    return rec


def show(rec: dict) -> None:
    f = rec.get("feed") or {}
    g = rec.get("return") or {}
    print("  ── %s" % rec["intent"][:60])
    if not f.get("ok"):
        print("     ①喂 %-14s %s" % (f.get("stage"), f.get("why") or ""))
        return
    print("     ①喂  %-22s %d条/%d字 · %.2fs · %s tok/s" %
          (f.get("model"), f.get("window_msgs"), f.get("window_chars"),
           f.get("s") or 0, f.get("tps")))
    print("        输出: %s" % (f.get("text") or "")[:70].replace("\n", " "))
    w = g.get("watch") or {}
    rt = g.get("route") or {}
    if w.get("ok"):
        print("     ②回  守望判据 → 命中 %s 条%s%s" %
              (w.get("hits"),
               ("（入队 %s）" % w.get("queued")) if w.get("queued") else "",
               (" · " + "、".join(str(k) for k in (w.get("codes") or []))) if w.get("codes") else ""))
        for f in (w.get("fixes") or []):
            print("         怎么改：%s" % str(f)[:70])
    else:
        print("     ②回  守望 判不了：%s" % (w.get("why") or w.get("note") or "未命中"))
    if rt.get("next"):
        print("         下一步参考 → %-16s path=%s%s" %
              (rt.get("next"), rt.get("path"),
               "（降级，可能不相关）" if rt.get("degraded") else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", default="")
    ap.add_argument("--loop", type=int, default=0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    b = bind_tentacles()
    print("  双向绑定: %s" % ("✅ %s + %s → A19 端点" % (FEED, RET) if b.get("ok")
                              else "🔴 %s" % b.get("bind")))
    rc = ring()

    if a.selftest:
        import subprocess
        print("  （起桩容器自测 —— 证明结构通，不证明 A19 真开）")
        p = subprocess.Popen([sys.executable, "-u", str(ROOT / "tools" / "a19_stub.py"),
                              "--port", str(PORT), "--seconds", "60"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        t0 = time.time()
        while time.time() - t0 < 20 and not model_up():
            time.sleep(1)
        if not model_up():
            print("  🔴 桩没起来"); p.kill(); return 1
        print("  桩已就绪，跑一轮\n")
        show(one_turn(rc, "用一句话说明这台机器是谁的"))
        p.kill()
        return 0

    if a.loop:
        print("  双触手跑 %d 轮\n" % a.loop)
        seeds = ["先说明你是谁", "把刚才那句落到一个能力位上", "现在上下文还剩多少"]
        bad = 0
        for i in range(a.loop):
            rec = one_turn(rc, seeds[i % len(seeds)])
            show(rec)
            bad += 0 if rec["ok"] else 1
            print()
        print("  %d 轮完成 · 失败 %d" % (a.loop, bad))
        return 0 if bad == 0 else 1

    if a.once:
        if not model_up():
            print("  🔴 :1234 不在 —— A19 没开，不编输出")
            print("     要验结构通不通，用 --selftest（起桩）")
            return 1
        show(one_turn(rc, a.once))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
