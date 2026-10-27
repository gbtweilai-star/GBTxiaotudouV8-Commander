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


def log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── ② 脑：A19 优先，按序试多条传输 ─────────────────────────────────────────
def brain_ask(text: str, timeout: float = 120) -> dict:
    tried = []
    # 传输①：A19 直连
    try:
        s = socket.socket(); s.settimeout(timeout)
        s.connect(ADDR)
        body = json.dumps({"messages": [{"role": "user", "content": text}],
                           "max_tokens": 300}).encode()
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
            data=json.dumps({"messages": [{"role": "user", "content": text}],
                             "max_tokens": 300}).encode(),
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
