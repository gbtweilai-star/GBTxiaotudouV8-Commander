#!/usr/bin/env python3
"""持续监听 —— 麦克风 → 文本 → （可选）脑 → 嘴

主人令：打开麦克风实时监听，用语音跟她对话测试联通。

设计要点：
  · **轮转采**：每轮采 N 秒 → 立刻识别 → 记一行 → 马上接着采
    （不用一个长录音：识别服务对长音频更易超时，短段成功率高）
  · **静音不记**：识别出 0 字就什么都不写，不制造噪声
  · **有字就往下走**：识别到内容 → 问脑 → 用台湾腔说出来
  · 脑不通时**只记"听到了什么"**，这一步本身就有价值（证明耳通了）
  · 全程落 logs/ear_listen.jsonl，可回溯

用法：
  python3 tools/ear_listen.py --seconds 6 --rounds 20
  python3 tools/ear_listen.py --seconds 6 --until 180     # 监听 180 秒
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

LEDGER = ROOT / "logs" / "ear_listen.jsonl"
SPEECH = "apple-speech"


def log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def listen_once(seconds: int, lang: str) -> dict:
    """采一轮并识别。返回 {ok, text, ms, err}"""
    t0 = time.perf_counter()
    try:
        r = subprocess.run([SPEECH, "transcribe", "--source", "mic",
                            "--duration", str(int(seconds)), "--language", lang],
                           capture_output=True, text=True, timeout=seconds + 60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "text": "", "err": "识别超时",
                "ms": round((time.perf_counter() - t0) * 1000)}
    out = (r.stdout or "").strip()
    try:
        d = json.loads(out[out.index("{"):])
    except Exception:                                         # noqa: BLE001
        return {"ok": False, "text": "", "err": (out or r.stderr or "")[:100],
                "ms": round((time.perf_counter() - t0) * 1000)}
    if not d.get("ok"):
        return {"ok": False, "text": "",
                "err": str((d.get("error") or {}).get("message") or "")[:100],
                "ms": round((time.perf_counter() - t0) * 1000)}
    data = d.get("data") or {}
    return {"ok": True, "text": (data.get("text") or "").strip(),
            "segments": len(data.get("segments") or []),
            "ms": round((time.perf_counter() - t0) * 1000)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--rounds", type=int, default=0)
    ap.add_argument("--until", type=int, default=0, help="监听多少秒后停")
    ap.add_argument("--lang", default="zh-CN")
    ap.add_argument("--no-brain", action="store_true")
    a = ap.parse_args()

    print("  🎤 麦克风已开 · 每轮 %d 秒 · 你直接说话" % a.seconds, flush=True)
    print("  识别到内容就记一行；识别不到就跳过（不写噪声）\n", flush=True)

    t_start = time.time()
    round_no = 0
    heard = 0
    while True:
        round_no += 1
        if a.rounds and round_no > a.rounds:
            break
        if a.until and time.time() - t_start > a.until:
            break
        print("  [%02d] 采 %ds…" % (round_no, a.seconds), end=" ", flush=True)
        r = listen_once(a.seconds, a.lang)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "round": round_no,
               "seconds": a.seconds, **r}
        if not r["ok"]:
            print("🔴 %s" % (r.get("err") or "")[:60], flush=True)
            log(rec)
            time.sleep(1)
            continue
        if not r["text"]:
            print("（静音）", flush=True)
            log(rec)
            continue
        heard += 1
        print("✅ 听到：「%s」" % r["text"][:60], flush=True)
        rec["heard"] = True
        log(rec)

        if a.no_brain:
            continue
        # 有字 → 问脑 → 嘴
        try:
            import voice_loop as VL
            br = VL.brain_ask(r["text"])
            rec["brain"] = {"via": br.get("via"), "ok": br.get("ok"),
                            "answer": (br.get("answer") or "")[:200],
                            "tried": br.get("tried")}
            if br.get("ok"):
                print("     脑(%s)：%s" % (br.get("via"),
                                          (br.get("answer") or "")[:60]), flush=True)
                import tentacle_bus as BUS
                m = BUS.call("mouth", (br.get("answer") or "")[:300])
                rec["mouth"] = {"via": m.get("via"), "ok": m.get("ok"),
                                "played": m.get("played")}
                print("     嘴(%s)：%s" % (m.get("via"),
                                          "已出声" if m.get("played") else m.get("detail", "")[:40]),
                      flush=True)
            else:
                print("     脑不通（%s）—— 只记下听到了什么"
                      % ", ".join("%s" % (t.get("via")) for t in (br.get("tried") or [])),
                      flush=True)
        except Exception as exc:                              # noqa: BLE001
            rec["brain_err"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
            print("     下游失败：%s" % str(exc)[:60], flush=True)
        log(rec)

    print("\n  监听结束：%d 轮 · 听到 %d 次" % (round_no - 1, heard), flush=True)
    print("  账本: logs/ear_listen.jsonl", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
