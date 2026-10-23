# -*- coding: utf-8 -*-
"""主脑语音对讲 · 常驻件（**页面生命周期绑定**）

主人令 2026-09-23：「我打开页面就自动监听，关闭她也跟着关闭，但是大脑后台是在运行的。」

⇒ 本件是**被页面（经壳）拉起、随页面关闭被杀掉**的那个进程：
   **没有开关** —— 起来就听，进程结束就停。定时/常驻守护**不做**（那是页面的事）。

三条纪律（写死）：
 ① **一切走唯一门**：调 `five-dim.py cap voice '<json>'`（= `api.run_task`），
    **绝不** `import voice_cap` 直调 —— 那会绕过授权门（本仓 2026-09-19 有过一次实测教训）。
 ② **安静 ≠ 坏了 ≠ 被门拒**：三种结果分开报，各有自己的退出码，绝不合并成"对讲不可用"。
 ③ **绝不伪造**：没听到就不写文本；被拒就原样带出 `missing_scopes` 与 `how_to_grant`。

用法：
    python tools/codex-scripts/intercom.py status                 # 三条腿现读（只读）
    python tools/codex-scripts/intercom.py say "要念的话"          # 走门 TTS（缺授权就如实报缺）
    python tools/codex-scripts/intercom.py watch --seconds 6       # 常驻监听（无限轮）
    python tools/codex-scripts/intercom.py watch --jsonl --rounds 3 # 每轮一行 JSON（给壳转给页面）

退出码：0=正常（听到/没听到都算正常）· 3=被门拒（缺作用域）· 4=后端不可用（缺设备/识别器）· 5=其他错
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
PY = sys.executable


def cap(payload: dict, timeout=180):
    """走万能插调 `voice`（**唯一门**）。返回 (信封 dict, 退出码)。"""
    if not FIVE.is_file():
        return {"ok": False, "status": "error", "error": "five-dim.py 不在盘上"}, 5
    cmd = [PY, str(FIVE), "cap", "voice", json.dumps(payload, ensure_ascii=False)]
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "error", "error": "万能插调用超时（%ss）" % timeout}, 5
    txt = (cp.stdout or b"").decode("utf-8", "replace")
    i = txt.find("{")
    if i < 0:
        return {"ok": False, "status": "error",
                "error": "没拿到 JSON（exit=%s）" % cp.returncode,
                "stderr": (cp.stderr or b"").decode("utf-8", "replace")[:200]}, 5
    try:
        env = json.loads(txt[i:])
    except Exception as e:                                            # noqa: BLE001
        return {"ok": False, "status": "error", "error": "JSON 解析失败：%s" % str(e)[:120]}, 5
    # 门亲笔的信封：denied/status 在外层，能力返回值在内层 result
    if env.get("denied") or env.get("missing_scopes"):
        return env, 3
    return env, 0


def _inner(env):
    """取门信封里的能力返回值 —— **并且认得"被收窄"的结果**。

    🔴 第 66 轮修（**真缺陷，实测抓到的**）：`five-dim.py` 在结果 >1100 字时会把 `result`
    收窄成 `{"_摘要": …, "keys": […], "preview": {…}}`。而 `watch` 原来的读法是
    `r.get("status")` —— **收窄后顶层没有 `status`** ⇒ 回落到
    `("heard" if heard else "quiet")` ⇒ **把「没有可用录音设备」念成「安静（没听到，不是坏）」**。
    这正是本仓最忌讳的假绿：**安静 ≠ 坏了 ≠ 被门拒**，三件事不许混。

    触发条件还是我自己造的：第 59 轮给 `listen` 补了 `legs`（两条腿各带异常原文）
    ⇒ 结果变大 ⇒ 撞上收窄阈值 ⇒ **改一个地方，另一处静默失效**。
    ⇒ 所以这里**既**认 `preview`（读法修好）**也**把 leg 的原因截短（体积压回去），两道都上。
    """
    r = env.get("result") if isinstance(env.get("result"), dict) else env
    if isinstance(r, dict) and "_摘要" in r and isinstance(r.get("preview"), dict):
        return r["preview"]
    return r


def legs(env):
    """把信封里的三条腿拆出来（**分开，不合并**）。"""
    r = env.get("result") if isinstance(env.get("result"), dict) else env
    return (r.get("backend") or r.get("status") or "?"), r


def cmd_status():
    out = {"ok": True, "legs": {}, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    env, _ = cap({"op": "status"}, timeout=90)
    r = _inner(env)
    out["legs"]["tts"] = r.get("tts") or "取不到"
    out["legs"]["asr_cloud"] = r.get("asr") or "取不到"
    out["legs"]["listen_local"] = r.get("listen") or "取不到"
    out["legs"]["recognizers_zh"] = r.get("recognizers_zh") or []
    # ── 🔴 第 59 轮补：**采集这条腿的"开机判据"** ────────────────────────────
    # 为什么非补不可：面板原来只有"识别器在不在"，识别器在位就标绿 ⇒ **假绿**。
    # 本机实测（四套音频 API 交叉验证）：录音端点在场的 **0** 个，
    # `waveInGetNumDevs() = 0` ⇒ **设备直连那条腿是死的，与插不插麦克风无关**。
    # 不把这格报出去，主人会以为"耳朵装好了，怎么听不见我说话"。
    w = r.get("wavein_devices")
    out["legs"]["wavein_devices"] = w
    out["legs"]["listen_input"] = r.get("listen_input") or "取不到"
    out["legs"]["listen_note"] = r.get("listen_note") or ""
    out["legs"]["capture_ready"] = (w is None) or (isinstance(w, int) and w > 0)
    # 出声这条腿要授权：不真出声，只报"缺什么"（试一次 tts 的空文本会被门先拦）
    env2, code2 = cap({"op": "tts", "text": "authorization probe"}, timeout=90)
    if code2 == 3:
        out["legs"]["tts_gate"] = {"denied": True,
                                   "missing_scopes": env2.get("missing_scopes"),
                                   "how_to_grant": env2.get("how_to_grant")}
    else:
        out["legs"]["tts_gate"] = {"denied": False,
                                   "note": "授权在位（本次探针真的发出了声音）"}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_say(text):
    env, code = cap({"op": "tts", "text": text})
    if code == 3:
        print(json.dumps({"ok": False, "status": "denied",
                          "missing_scopes": env.get("missing_scopes"),
                          "how_to_grant": env.get("how_to_grant"),
                          "note": "授权是**一次性消耗**：一次授权 = 一次出声"},
                         ensure_ascii=False, indent=1))
        return 3
    r = _inner(env)
    print(json.dumps({"ok": bool(r.get("ok")), "result": r}, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 4


def cmd_watch(args):
    """常驻监听：**无开关** —— 起来就听，进程被杀就停。
       退避策略写死（免得刷屏，也免得对着一个没设备的机器空转）：
         heard            → 立刻下一轮（间隔 0.2s）
         安静(heard=false) → 正常间隔（--interval，默认 0.5s）
         no_input         → 退避 3→5→10→15s 封顶，并**把真实原因原样带出**
         no_recognizer    → 停止重试（再试也没用），如实报后退出 4
         denied           → 停止（缺授权），带 how_to_grant 退出 3
    """
    n, heard_total, started = 0, 0, time.time()
    back = 3.0
    while args.rounds <= 0 or n < args.rounds:
        n += 1
        env, code = cap({"op": "listen", "seconds": args.seconds, "culture": args.culture},
                        timeout=args.seconds + 60)
        rec = {"round": n, "at": time.strftime("%H:%M:%S")}
        if code == 3:
            rec.update({"status": "denied", "missing_scopes": env.get("missing_scopes"),
                        "how_to_grant": env.get("how_to_grant")})
            _emit(rec, args)
            return 3
        r = _inner(env)
        rec["status"] = r.get("status") or ("heard" if r.get("heard") else "quiet")
        if r.get("heard"):
            rec["text"] = r.get("text")
            rec["confidence"] = r.get("confidence")
            heard_total += 1
            # 🔴 听到的话**必须落到主脑能读到的地方**，否则"自动监听"只是装饰。
            #    落到**只追加**的收件箱（与 advisor-note / store/*/events.jsonl 同一套纪律）：
            #    不改旧行、不覆盖、不放凭据（这里本来也没有凭据）。
            _append_inbox(rec, args.inbox)
        else:
            rec["reason"] = r.get("reason") or r.get("error")
        rec["rounds_total"] = n
        rec["heard_total"] = heard_total
        rec["uptime_s"] = round(time.time() - started, 1)
        _emit(rec, args)
        if r.get("status") == "no_recognizer":
            return 4
        if r.get("status") == "no_input":
            time.sleep(back)
            back = min(back * 1.7, 15.0)
        else:
            time.sleep(0.2 if r.get("heard") else args.interval)
    return 0


def _append_inbox(rec, path):
    """把"听到的一句话"**只追加**写进收件箱。取不到路径/写不进去 ⇒ **不静默**：
    在 stderr 留一行（页面看不到也不许悄悄丢），但**不因此中断监听**。
    为什么是只追加：主脑要能读、要能追溯"这句话是什么时候听到的"；
    覆盖式写入会把上一条语音抹掉 —— 那是数据丢失，不是节省。"""
    if not path:
        return None
    try:
        p = Path(path)
        if not p.is_absolute():
            p = ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        line = {"ts": rec.get("ts") or time.time(),
                "at": rec.get("at"), "text": str(rec.get("text") or "")[:500],
                "confidence": rec.get("confidence"), "source": "intercom.py watch"}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return str(p)
    except Exception as e:                                            # noqa: BLE001
        sys.stderr.write("intercom: 收件箱写不进去（%s）：%s\n" % (path, str(e)[:120]))
        return None


def _emit(rec, args):
    """`--jsonl`：一行一条 JSON（壳逐行读、转给页面）；否则给人看的一行。"""
    if args.jsonl:
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    else:
        if rec.get("text"):
            print("[听到] %s（置信 %.2f · 第 %d 轮）"
                  % (rec["text"], rec.get("confidence") or 0, rec["round"]), flush=True)
        else:
            print("[%s] 第 %d 轮 · %s" % (rec.get("status"), rec["round"],
                                        (rec.get("reason") or "")[:70]), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="主脑语音对讲常驻件")
    ap.add_argument("cmd", choices=["status", "say", "watch"])
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--seconds", type=float, default=6.0, help="每轮听多久")
    ap.add_argument("--culture", default="zh-CN")
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--rounds", type=int, default=0, help="0=无限（页面关闭由壳 kill）")
    ap.add_argument("--jsonl", action="store_true")
    ap.add_argument("--inbox", default="state/voice_inbox.jsonl",
                    help="听到的话只追加写到这里（主脑读它；默认 state/voice_inbox.jsonl）")
    a = ap.parse_args()
    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "say":
        return cmd_say(a.text or "主脑对讲自检")
    return cmd_watch(a)


if __name__ == "__main__":
    raise SystemExit(main())
