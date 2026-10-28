#!/usr/bin/env python3
"""唤醒词「小土豆」—— 喊一声她就应

主人令（2026-10-28）：「随时可用，我每次喊小土豆她要能回应我才行」。

## 它做什么

```
采一段（60 秒，一次开关） → 识别 → 文本里有没有唤醒词？
   有 → 立刻回应（台湾腔）→ 记录这一声
   没有 → 丢弃，接着下一段
```

## 三条纪律（都是拿血换的）

1. **一次开 60 秒**，不是 6 秒 —— 反复开关会把 iOS 的音频会话卡死
   （实测：103 次快速开关后被限流，连文件源都失败）
2. **出错指数退避** 10→20→40→60，连败 3 次停
3. **判据可测**：`--test "小土豆"` 不需要麦克风就能验判定逻辑

## 诚实的边界

iOS 不允许命令行常驻监听：`apple-speech` 是**一次一录**（上限 60 秒），
没有常驻模式；iSH 也没有音频设备节点。
⇒ **"随时可用"在这台机上 = 有一个 60 秒的窗口在听。**
窗口开着的时候你喊就有反应；窗口关着的间隙会漏。

用法：
  python3 tools/wake_word.py --test "小土豆 在吗"     # 只验判定（不用麦克风）
  python3 tools/wake_word.py --once                    # 采一段判断
  python3 tools/wake_word.py --loop --until 600        # 连续听 10 分钟
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

LEDGER = ROOT / "logs" / "wake_word.jsonl"
QUOTA_FILE = ROOT / "state" / "speech_quota.json"

# 🔴 2026-10-28 实测出来的配额规律（不是猜的）：
#   成功 3 次（间隔 15s）后开始被拒；间隔 5s/10s 也拒；冷却 200 秒仍拒；
#   从被拒到恢复，实测隔了约 29 分钟。
#   ⇒ iOS 对 SpeechRecognition 有**次数配额 + 长冷却**。
#   所以：
#     · **不要循环监听**，一次一枪（--once）
#     · 冷却期内直接拒绝，不浪费尝试（每次尝试都可能在续期封锁）
#     · 把最近一次成功/被拒的时间记下来，下次先看表
COOLDOWN_S = 1800          # 被拒后至少等 30 分钟再试


def _quota() -> dict:
    try:
        return json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
    except Exception:                                         # noqa: BLE001
        return {}


def _save_quota(d: dict) -> None:
    QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def quota_state() -> dict:
    """现在能不能安全地试一次？"""
    q = _quota()
    last_ok = q.get("last_ok") or 0
    last_deny = q.get("last_deny") or 0
    now = time.time()
    if last_deny and now - last_deny < COOLDOWN_S:
        return {"ok": False, "why": "被拒后冷却中",
                "wait_s": int(COOLDOWN_S - (now - last_deny)),
                "last_deny": time.strftime("%H:%M:%S", time.localtime(last_deny))}
    return {"ok": True, "last_ok": (time.strftime("%H:%M:%S", time.localtime(last_ok))
                                    if last_ok else "从未"),
            "ok_count": q.get("ok_count", 0), "deny_count": q.get("deny_count", 0)}

# 唤醒词（含常见误识别写法）
WAKES = ["小土豆", "小土豆v8", "小土豆 v8", "土豆", "xiaotudou", "小土斗", "小士豆"]

# 喊她之后她怎么应
REPLY = "我在。"


def log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def detect(text: str) -> dict:
    """判定这段文本里有没有在喊她。

    返回 {woke, word, rest}：
      woke  是否被喊
      word  命中的那个词
      rest  喊完之后跟的那句话（"小土豆，今天几号" → "今天几号"）
    """
    t = str(text or "").strip()
    if not t:
        return {"woke": False, "word": None, "rest": ""}
    low = t.lower().replace(" ", "")
    # 🔴 2026-10-28：光判"含不含"会误唤醒 —— 实测「土豆丝怎么炒」被判成喊她。
    #   「土豆」是常用食材名，所以裸「土豆」后面跟着这些字时**不算喊她**：
    #   丝/片/泥/块/条/粉/烧/炖/炒/的做法/的价格…
    FOOD = r"丝|片|泥|块|条|粉|烧|炖|炒|焖|沙拉|的做法|怎么|多少钱|价格|的营养"
    for w in sorted(WAKES, key=len, reverse=True):
        k = w.lower().replace(" ", "")
        if not k:
            continue
        if w in ("土豆", "xiaotudou") and re.search(re.escape(w) + "(?:" + FOOD + ")", t):
            continue          # 食材/菜名，不是喊她
        if k and k in low:
            # 取第一次出现位置之后的内容当指令
            i = low.find(k)
            # 原串里对应位置（去空格会错位，退化为按词切）
            parts = re.split(re.escape(w), t, maxsplit=1, flags=re.IGNORECASE)
            rest = parts[1].strip(" ，,。.!！?？、~～") if len(parts) > 1 else ""
            return {"woke": True, "word": w, "rest": rest}
    return {"woke": False, "word": None, "rest": ""}


def capture(seconds: int, lang: str = "zh-CN") -> dict:
    t0 = time.perf_counter()
    try:
        r = subprocess.run(["apple-speech", "transcribe", "--source", "mic",
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
        msg = str((d.get("error") or {}).get("message") or "")[:100]
        q = _quota(); q["last_deny"] = time.time()
        q["deny_count"] = q.get("deny_count", 0) + 1
        _save_quota(q)
        return {"ok": False, "text": "", "err": msg,
                "ms": round((time.perf_counter() - t0) * 1000)}
    q = _quota(); q["last_ok"] = time.time()
    q["ok_count"] = q.get("ok_count", 0) + 1
    q["last_deny"] = 0          # 成功即清掉冷却标记
    _save_quota(q)
    return {"ok": True, "text": ((d.get("data") or {}).get("text") or "").strip(),
            "ms": round((time.perf_counter() - t0) * 1000)}


def answer(rest: str) -> dict:
    """被喊之后：有指令就问脑，没指令就应一声。"""
    import tentacle_bus as BUS
    if not rest:
        return BUS.call("mouth", REPLY)
    try:
        import voice_loop as VL
        br = VL.brain_ask(rest)
        if br.get("ok"):
            return BUS.call("mouth", (br.get("answer") or "")[:300])
        # 脑不通：至少应一声，并说明"脑子没接上"
        return BUS.call("mouth", "我在，但我现在脑子没接上。")
    except Exception:                                         # noqa: BLE001
        return BUS.call("mouth", REPLY)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="", help="只用文本验判定，不开麦克风")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--until", type=int, default=0)
    ap.add_argument("--lang", default="zh-CN")
    ap.add_argument("--no-answer", action="store_true")
    a = ap.parse_args()

    if a.test != "":
        d = detect(a.test)
        print(json.dumps({"input": a.test, **d}, ensure_ascii=False, indent=1))
        return 0 if d["woke"] else 1

    if not (a.once or a.loop):
        ap.print_help()
        return 2

    qs = quota_state()
    if not qs.get("ok"):
        print("  ⛔ 现在不该试：%s（还要等 %d 分 %d 秒）"
              % (qs.get("why"), qs["wait_s"] // 60, qs["wait_s"] % 60), flush=True)
        print("     上次被拒 %s。每次尝试都可能在续期封锁，所以直接等。"
              % qs.get("last_deny"), flush=True)
        return 1
    print("  🎤 唤醒词监听：喊「%s」她就应" % WAKES[0], flush=True)
    print("  每段 %d 秒（一次开关）· 退避 10/20/40 · 连败 3 次停\n" % a.seconds, flush=True)

    t_start = time.time()
    fails = 0
    round_no = 0
    woke_n = 0
    while True:
        round_no += 1
        if a.once and round_no > 1:
            break
        if a.until and time.time() - t_start > a.until:
            break
        print("  [%02d] 听 %ds…" % (round_no, a.seconds), end=" ", flush=True)
        c = capture(a.seconds, a.lang)
        if not c["ok"]:
            fails += 1
            wait = min(60, 10 * (2 ** (fails - 1)))
            print("🔴 %s · 退避 %ds" % ((c.get("err") or "")[:40], wait), flush=True)
            log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "round": round_no, **c})
            if fails >= 3:
                print("  ⛔ 连败 3 次，停（识别服务需恢复或重启 App）", flush=True)
                break
            time.sleep(wait)
            continue
        fails = 0
        d = detect(c["text"])
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "round": round_no,
               "text": c["text"], **d}
        if not c["text"]:
            print("（静音）", flush=True)
            log(rec)
            continue
        print("听到「%s」" % c["text"][:50], flush=True)
        if not d["woke"]:
            print("     （没喊她，忽略）", flush=True)
            log(rec)
            continue
        woke_n += 1
        print("     ✅ 喊了「%s」%s" % (d["word"],
              "· 指令：%s" % d["rest"] if d["rest"] else "（只喊名）"), flush=True)
        if not a.no_answer:
            m = answer(d["rest"])
            rec["answer"] = {"via": m.get("via"), "ok": m.get("ok"),
                             "played": m.get("played")}
            print("     → 应她（%s）%s" % (m.get("via"),
                  "已出声" if m.get("played") else (m.get("detail") or "")[:40]),
                  flush=True)
        log(rec)

    print("\n  结束：%d 段 · 被喊 %d 次" % (round_no - (1 if a.once else 0), woke_n), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停")
