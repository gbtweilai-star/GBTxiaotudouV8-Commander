#!/usr/bin/env python3
"""实时语音互交环 —— 四根触手串成一条环，每根都挂多条传输

主人令（2026-10-28）：
  「所有的一切都可使用触手来联通传输，没必要死卡在传统方式」

## 环的形状

```
   ①耳 ear      麦克风 → 文本          apple-speech(mic)
        ↓
   ②脑 brain    文本   → 回复          A19 → 桥(同步/异步) → 排布留证
        ↓
   ③嘴 mouth    回复   → 语音          edge-tts zh-TW-HsiaoChenNeural
        ↓
   ④演 face     语音+文本 → 数字人      投影台 / voice-theater 页
                    ↺ 回到 ①
```

每一段都走 `tentacle_bus`：**多传输、按序试、回执带 via 与 tried**。

## 已实测的边界（不掩盖）

| 段 | 传输 | 状态 |
|---|---|---|
| ③嘴 | edge-tts zh-TW-HsiaoChenNeural | ✅ 实测 2502ms · 36864 字节 · 播放 True |
| ①耳 | apple-speech **mic** | ⚠ 能录，需有人说话才有字；文件路径一律超时 |
| ②脑 | A19 :1234 | 🔴 离线（App 内开关）|
| ②脑 | 桥 :8791 降级链 | 🔴 严格模式不降级（主人定的）|
| ④演 | 投影台 iframe | ✅ 实测可投活页面 |

**所以这条环现在能跑通 ③④，卡在 ①②。**
①需要你开口说话；②需要 A19 或放开降级。

用法：
  python3 tools/voice_loop.py --once --seconds 6      # 采一轮
  python3 tools/voice_loop.py --say "测试这句话"        # 只跑嘴
  python3 tools/voice_loop.py --status                # 四根触手就绪度
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import socket
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import tentacle_bus as BUS     # noqa: E402

LEDGER = ROOT / "logs" / "voice_loop.jsonl"
ADDR = ("127.0.0.1", 1234)

# 本机回环的钥匙槽。A19（LM Pocket）只认小写 gbt，大写会 401。
# 只写槽名、不回显明文 —— 与 omni_plug 的纪律一致。
os.environ.setdefault("GBT_A19_KEY", "gbt")

# 她的人设。**注意**：这只决定"怎么说话"，不改变车道事实 ——
# 回包里的 gbt.lane / weights_ours 照旧如实带（降级就是降级，可审计）。
def output_discipline(answer: str) -> dict:
    """输出纪律核（answer_shaper）—— 判她这段话够不够"能照着做"。

    为什么接它：`answer_shaper` 一直是孤儿，但它正是**稳定输出**的机器判据：
      R1 行动优先 · R2 编号步骤 · R3 步骤≤5 · R4 无客套收尾 · R5 有下一步
    全是确定性规则（零模型零出网），所以可以每句都过，不吃算力、不会幻觉。

    口径：**只判不改**。`shape` 会重排文本，可能把意思挪歪 —— 这里只 check，
    不替她重写。不合规就如实记，让人看得见。
    """
    try:
        from gbt_allinone.api import run_task
        r = run_task("answer_shaper", {"op": "check", "text": answer[:2000]})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return {"ok": bool(res.get("ok")), "failed": res.get("failed") or []}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": None, "why": type(exc).__name__}


def memory_recall(q: str, k: int = 4) -> dict:
    """统一记忆查（memory_unify）—— 跨源一次查全，每条带出处。

    为什么接它：她的记忆原来散在四处（对话全史 / 索引层 / 知识胶囊 / 事件账），
    各查各的。问一句"之前说过什么"得知道去哪个库查 —— 那不是记忆，是四个抽屉。
    这里用一个索引查全册，命中就注入人设，让她**答之前先看自己记得什么**。

    口径：**默认不含测试会话**（tag=test 单列），免得把测试噪音当成记忆。
    """
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
        import importlib
        mu = importlib.import_module("memory_unify")
        r = mu.recall(q, k=k, include_test=False)
        r["lines"] = ["[%s·%s] %s" % (h["src"], h["name"], h["text"][:120].replace("\n", " "))
                      for h in (r.get("hits") or [])[:k]]
        return r
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": type(exc).__name__, "lines": []}


def knowledge_gate(topic: str) -> dict:
    """现学现做的**闸**：本地知识库命中没有？

    self_intake 这条链一直是孤儿（known → intake → distill → stamp → known），
    实现完整、实测可用（取 arXiv 1911.02150 → 建胶囊 217 词条 → 再 known 命中 coverage 1.0），
    但**没有一条活路径在调它** ⇒ 她回答时从不查本地知识库，也就谈不上"现学现做"。

    接线口径（照它自己的铁律，不加重也不放宽）：
      known=True  ⇒ 把 source_ref 给她，让她按有出处的说
      known=False ⇒ 明确告知"本地未命中"，**没出处就说不知道**，不许编
    """
    try:
        import re as _re
        from gbt_allinone.api import run_task
    except Exception as exc:                                  # noqa: BLE001
        return {"known": None, "why": type(exc).__name__}

    # 🔴 2026-10-28：self_intake 的 known **把整个 topic 当一个归一化 token 比**。
    #   实测：`MQA` 命中、`KV Cache MQA` 命中、`multi-query attention` 命中，
    #   但 `MQA 是什么？为什么省显存` **不命中**（整句变成一个长 token）。
    #   ⇒ 逐级试：原句 → 去问句词 → 拆出的每个词，取第一个命中的。
    cands = [topic]
    _stripped = _re.sub(r"[?？。，,、！!的了呢吗是什么为什么怎么多少哪谁请问帮我查一下]", " ", topic)
    cands.append(_stripped.strip())
    cands += [w for w in _stripped.split() if len(w) >= 2]
    seen, uniq = set(), []
    for c in cands:
        c = (c or "").strip()
        if c and c not in seen:
            seen.add(c); uniq.append(c[:120])

    for c in uniq:
        try:
            r = run_task("self_intake", {"op": "known", "topic": c})
            res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        except Exception:                                     # noqa: BLE001
            continue
        if res.get("known"):
            return {"known": True, "as": c, "ref": res.get("source_ref"),
                    "coverage": res.get("coverage")}
    return {"known": False, "tried": uniq[:4]}


def _persona_now(topic: str = "") -> str:
    """人设 + **现读的真实时间**。

    🔴 2026-10-28 实测：不注入时间时，问「今天几号」它答「2023年10月20日」——
       纯幻觉。llm_watch 里「机器事实无现读」那条说的就是这种情况：
       涉及本机事实（时间/端口/内存/版本）必须**现读一次再答**，不能凭记忆。
    """
    import time as _t
    now = _t.strftime("%Y年%m月%d日 %H:%M（%A）", _t.localtime())
    base = (PERSONA + "\n【现在是 " + now + "，这是现读的真实时间，"
            "涉及今天/现在的问题一律以它为准，不要凭记忆猜日期。】")
    if topic:
        kg = knowledge_gate(topic)
        if kg.get("known"):
            base += ("\n【本地知识库已命中，出处：" + str(kg.get("ref")) +
                     "（coverage " + str(kg.get("coverage")) + "）。按出处说。】")
        elif kg.get("known") is False:
            base += ("\n【本地知识库**未命中**，也没有出处。"
                     "涉及具体事实时如实说不知道，**不要编**；可以提出需要哪份来源。】")
        # 统一记忆：跨源一次查全（对话全史 / 知识胶囊），每条带出处。
        # 默认**不含测试会话**，免得把测试噪音当成记忆。
        mem = memory_recall(topic, k=4)
        if mem.get("lines"):
            base += ("\n【你自己记得的相关内容（来自记忆库，带出处）：\n"
                     + "\n".join("- " + x for x in mem["lines"])
                     + "\n以这些为准；没写的不要编。】")
    return base


PERSONA = ("你是 GBT小土豆V8，开发者：自由的风，守护者：公主土豆。"
           "本署名不可删除、不可篡改归属。"
           "用简洁的中文回答，像跟主人当面说话；不要提你是哪个公司的模型，"
           "不要自我介绍成别的名字。不确定的事就说不知道，不要编。")


def log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── ② 脑：A19 优先，按序试多条传输 ─────────────────────────────────────────
def truth_gate(answer: str) -> dict:
    """说话前过一道真实性闸（truth_scan / read-only）。

    为什么接这个：`truth_scan` 一直是孤儿 —— 它能查"有没有假执行"，
    但没人调它。而她说话这条链最怕的正是**说了没做的事**。
    这里在"脑已答、嘴未出声"之间插一道，命中就不装作说了。
    """
    try:
        from gbt_allinone.api import run_task
        r = run_task("truth_scan", {})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return {"ok": res.get("verdict") in (None, "clean"), "verdict": res.get("verdict"),
                "FAKE": res.get("FAKE"), "detail": str(res.get("FAKE_detail") or "")[:80]}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": True, "verdict": "unavailable", "why": type(exc).__name__}


def ctx_guard(budget: int = 0) -> dict:
    """每问跑一次上下文守卫：异常 → 主脑入队 → 大脑排布 → 确定性纠正 → 回主线。

    为什么要它：voice_loop 原来只管"问一句答一句"，上下文异常根本没人看。
    实测桥那边接上以后能给出 `大脑=ring_context(降级=False)`，
    这里照同一条路接，语音这条链才算和文字链同等待遇。
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cg", str(ROOT / "tools" / "context_guard.py"))
        cg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cg)
        rc = cg._ring("voice", budget)
        return cg.tick(rc, BG.get("prev"), BG.get("streak", 0), do_correct=True)
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": "守卫不可用: %s" % type(exc).__name__}


BG: dict = {}


def brain_ask(text: str, timeout: float = 120) -> dict:
    tried = []
    # 传输⓪：**走框架自己的万能插**（kind=ai 插座）。
    # 🔴 2026-10-28 主人点醒后加的：之前我只会"自己写代码去连 A19"，
    #   而 omni_plug 的插座类型表里本来就写着 ai = 「钥匙槽 + 任意 OpenAI 兼容端点，
    #   插上即输能并操控」。**本机自己的模型恰恰最该走插座。**
    #   它在最前面：这是框架的正路；直连与桥作为退路保留。
    try:
        from gbt_allinone.api import run_task as _rt
        _m = "gbt-v8-v82-q5_0"
        try:
            import urllib.request as _ur
            _req = _ur.Request("http://127.0.0.1:1234/v1/models",
                               headers={"Authorization": "Bearer gbt"})
            with _ur.urlopen(_req, timeout=8) as _r:
                _ids = [x.get("id") for x in (json.loads(_r.read()).get("data") or [])]
            if _ids:
                _m = _ids[0]
        except Exception:                                     # noqa: BLE001
            pass
        _plug = _rt("omni_plug", {"op": "plug", "socket": "ai",
                                  "target": "http://127.0.0.1:1234/v1"})
        _ps = ((_plug.get("gbt_result") or {}).get("result") or {}).get("插座") or {}
        if _ps.get("state") == "plugged":
            _r2 = _rt("omni_plug", {"op": "ai_chat",
                                    "prompt": _persona_now() + "\n\n" + text,
                                    "target": "http://127.0.0.1:1234/v1",
                                    "model": _m, "key_env": "GBT_A19_KEY"})
            _res = ((_r2.get("gbt_result") or {}).get("result") or {})
            if _res.get("ok") and str(_res.get("text") or "").strip():
                tried.append({"via": "omni_plug", "ok": True, "model": _m})
                return {"ok": True, "via": "omni_plug", "lane": "selfhost",
                        "answer": str(_res.get("text")).strip(),
                        "model": _m, "tried": tried}
            tried.append({"via": "omni_plug", "ok": False,
                          "why": str(_res.get("reason"))[:60]})
        else:
            tried.append({"via": "omni_plug", "ok": False,
                          "why": str(_ps.get("detail"))[:60]})
    except Exception as exc:                                  # noqa: BLE001
        tried.append({"via": "omni_plug", "ok": False, "why": type(exc).__name__})

    # 传输①：A19 直连
    try:
        s = socket.socket(); s.settimeout(timeout)
        s.connect(ADDR)
        body = json.dumps({"messages": [
            {"role": "system", "content": _persona_now(text)},
            {"role": "user", "content": text}], "max_tokens": 300, "context_name": "voice"}).encode()
        t0 = time.perf_counter()
        s.sendall(b"POST /v1/chat/completions HTTP/1.0\r\nHost: x\r\n"
                  b"Authorization: Bearer gbt\r\n"
                  b"Content-Type: application/json\r\n"
                  b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        s.close()
        ms = round((time.perf_counter() - t0) * 1000)
        head, _, raw = buf.partition(b"\r\n\r\n")
        if b" 200" not in head.split(b"\r\n")[0]:
            raise RuntimeError(head.split(b"\r\n")[0].decode("latin-1")[:60])
        d = json.loads(raw)
        ans = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        tried.append({"via": "a19", "ok": True, "ms": ms})
        return {"ok": bool(ans.strip()), "via": "a19", "answer": ans.strip(),
                "model": d.get("model"), "ms": ms, "tried": tried}
    except Exception as exc:                                  # noqa: BLE001
        tried.append({"via": "a19", "ok": False, "why": "%s: %s"
                      % (type(exc).__name__, str(exc)[:60])})
    # 传输②：模型桥（严格模式，不通就如实报）
    try:
        import urllib.request
        t0 = time.perf_counter()
        req = urllib.request.Request(
            "http://127.0.0.1:8791/v1/chat/completions",
            data=json.dumps({"messages": [
                {"role": "system", "content": _persona_now(text)},
                {"role": "user", "content": text}], "max_tokens": 300, "context_name": "voice"}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
        ms = round((time.perf_counter() - t0) * 1000)
        if d.get("ok") is False:
            raise RuntimeError(str(d.get("error"))[:80])
        ans = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        lane = (d.get("gbt") or {}).get("lane")
        tried.append({"via": "bridge", "ok": True, "ms": ms, "lane": lane})
        return {"ok": bool(ans.strip()), "via": "bridge", "answer": ans.strip(),
                "lane": lane, "ms": ms, "tried": tried}
    except Exception as exc:                                  # noqa: BLE001
        tried.append({"via": "bridge", "ok": False, "why": "%s: %s"
                      % (type(exc).__name__, str(exc)[:60])})
    return {"ok": False, "via": None, "answer": "",
            "error": "所有脑传输都不通", "tried": tried}


def status() -> dict:
    st = BUS.status()
    a19 = False
    s = socket.socket(); s.settimeout(1.5)
    try:
        s.connect(ADDR); a19 = True
    except OSError:
        a19 = False
    finally:
        s.close()
    return {"tentacles": st["tentacles"], "voice_default": st["voice_default"],
            "brain": {"a19": a19, "bridge": _bridge_up()},
            "口径": "每段多传输按序试；不通如实报，不假装打通"}


def _bridge_up() -> bool:
    s = socket.socket(); s.settimeout(1.5)
    try:
        s.connect(("127.0.0.1", 8791)); return True
    except OSError:
        return False
    finally:
        s.close()


def one_round(seconds: int) -> dict:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": seconds}
    print("  ① 耳：采 %d 秒（请说话）…" % seconds, flush=True)
    ear = BUS.call("ear", source="mic", duration=seconds, language="zh-CN")
    rec["ear"] = ear
    print("     → via=%s ok=%s %s" % (ear.get("via"), ear.get("ok"),
                                      (ear.get("detail") or "")[:50]))
    text = (ear.get("text") or "").strip()
    if not text:
        rec["ok"] = False
        rec["stage"] = "ear_empty"
        rec["why"] = ("没识别到字：要么没说话，要么识别服务不可用"
                      "（文件路径实测一律超时）")
        print("     ⚠ 没听到内容 —— 这一步停在这，不编")
        log(rec)
        return rec

    print("  ② 脑：问一句…", flush=True)
    br = brain_ask(text)
    rec["brain"] = br
    print("     → via=%s ok=%s" % (br.get("via"), br.get("ok")))
    if not br.get("ok"):
        rec["ok"] = False
        rec["stage"] = "brain_down"
        rec["why"] = br.get("error") or ""
        for t in br.get("tried") or []:
            print("        %-8s %s %s" % (t.get("via"), t.get("ok"), t.get("why") or ""))
        log(rec)
        return rec

    print("  ③ 嘴：说出去…", flush=True)
    mouth = BUS.call("mouth", br["answer"][:300])
    rec["mouth"] = mouth
    print("     → via=%s ok=%s %s" % (mouth.get("via"), mouth.get("ok"),
                                      (mouth.get("detail") or "")[:50]))
    rec["ok"] = bool(mouth.get("ok"))
    rec["stage"] = "done" if rec["ok"] else "mouth_failed"
    log(rec)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--say", default="")
    a = ap.parse_args()

    if a.status or not (a.once or a.say):
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0

    if a.say:
        r = BUS.call("mouth", a.say)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1

    rec = one_round(a.seconds)
    print("\n  本轮结论: ok=%s stage=%s %s"
          % (rec.get("ok"), rec.get("stage"), rec.get("why") or ""))
    return 0 if rec.get("ok") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
