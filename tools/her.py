#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""her.py —— 「她的嘴」：把一句话交给 A19 原生权重，原话带回，并且**落盘**。

这是主人口径「这个框使用我们的原生权重」的执行件：
    python3 her.py "你的问题"        # 走容器，原话输出（--raw 只输出正文）
    python3 her.py --status          # 只看容器在不在（<1s）
    python3 her.py --tail 6          # 读回最近 6 条（页面和本框共用一份记录）
    python3 her.py --mode on|off|show

与页面的关系：两边写同一份 state/her_transcript.jsonl，
用 source 字段区分 page / minis —— 不会再出现「页面记得、这边不知道」。

纪律（主人令）：A19 优先 · 不许静默降级云端 · 不许编造她没说过的话 ·
              容器不在就如实说不在（0.9 秒内），且**不落盘**（没发生的对话不记）。
"""
import argparse
import importlib.util
import json
import os
import pathlib
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
MODE_FILE = TOOLS.parent / "state" / "a19_mode.json"
TRANSCRIPT = TOOLS.parent / "state" / "her_transcript.jsonl"
MAXLEN = 8000


def ctl():
    spec = importlib.util.spec_from_file_location("a19ctl", str(TOOLS / "a19_ctl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def log(role, text, upstream=None, model=None, source="minis"):
    """落一行到共用账本。失败不影响回答 —— 但会如实说一声。"""
    try:
        TRANSCRIPT.parent.mkdir(parents=True, exist_ok=True)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "role": role,
               "text": str(text or "")[:MAXLEN], "upstream": upstream,
               "model": model, "source": source}
        with open(TRANSCRIPT, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception as exc:                                      # noqa: BLE001
        sys.stderr.write("[her] 落盘失败 %s: %s\n" % (type(exc).__name__, exc))
        return False


PERSONA_LITE = TOOLS.parent / "state" / "her_persona_lite.txt"   # 407 字，默认
PERSONA_FULL = TOOLS.parent / "state" / "her_persona.txt"        # 1182 字，--persona-full


def persona(full=False):
    """默认精简版：7.6B/4096 的窗口里，全量人格占 18%，会把对话挤没。"""
    for p in ((PERSONA_FULL, PERSONA_LITE) if full else (PERSONA_LITE, PERSONA_FULL)):
        try:
            return p.read_text(encoding="utf-8")
        except Exception:                                         # noqa: BLE001
            continue
    return ""


def tail(n=6):
    if not TRANSCRIPT.exists():
        return []
    rows = []
    for line in TRANSCRIPT.read_text(encoding="utf-8").splitlines()[-n:]:
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:                                     # noqa: BLE001
                pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="*")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("--tail", type=int, default=0)
    ap.add_argument("--taste", action="store_true",
                    help="输出「品味内核」（吞噬 taste-skill 后蒸馏，1.2k token）")
    ap.add_argument("--persona-full", action="store_true", help="用 1182 字全量人格（默认 407 字精简）")
    ap.add_argument("--sensor", type=int, default=0,
                    help="读最近 N 条传感器记录（页面在容器活着/断了时记下的读数）")
    ap.add_argument("--tokens", type=int, default=512)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--mode", choices=["on", "off", "show"])
    a = ap.parse_args()

    if a.mode:
        MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if a.mode == "show":
            print(MODE_FILE.read_text(encoding="utf-8")
                  if MODE_FILE.exists() else '{"mode":"off"}')
            return 0
        MODE_FILE.write_text(json.dumps({"mode": a.mode,
                                         "at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                        ensure_ascii=False), encoding="utf-8")
        print("mode=%s" % a.mode)
        return 0

    if a.taste:
        kp = TOOLS.parent / "state" / "taste_kernel.txt"
        if not kp.exists():
            print("内核不在：%s" % kp)
            return 2
        text = kp.read_text(encoding="utf-8")
        print("# 品味内核 · %d 字 · %s" % (len(text), kp))
        print(text)
        return 0

    if a.sensor:
        rows = [r for r in tail(200) if r.get("role") == "sensor"][-a.sensor:]
        if not rows:
            print("（还没有传感器记录 —— 页面要在容器活着/断了的时候打开过才会记）")
            return 0
        for r in rows:
            try:
                d = json.loads(r.get("text") or "{}")
            except Exception:                                     # noqa: BLE001
                d = {"raw": r.get("text")}
            bits = " ".join("%s=%s" % (k, v) for k, v in d.items())
            print("[%s] %s" % (r.get("at", "")[11:19], bits))
        return 0

    if a.tail:
        rows = tail(a.tail)
        if not rows:
            print("（还是空的）")
            return 0
        for r in rows:
            # 默认只显示对话行；传感器/读数请用 --sensor
            if r.get("role") not in ("user", "assistant"):
                continue
            src = r.get("source") or "?"
            print("[%s] %-9s %s" % (r.get("at", "")[11:19], r.get("role", "?") + "/" + src,
                                    (r.get("text") or "").replace("\n", " ")[:90]))
        return 0

    c = ctl()
    st = c.status_dict()
    if a.status or not a.prompt:
        print("%s · %s" % (st.get("container"),
                           st.get("why") or "models=%s ctx=%s" % (st.get("models"), st.get("ctx"))))
        return 0 if st.get("container") == "UP" else 2

    text = " ".join(a.prompt)
    if st.get("container") != "UP":
        # 没发生的对话不落盘：账本里只留真说过的话
        print("容器不在 —— 她这会儿没有嘴（:1234 无监听）。")
        print("动作：LM Pocket 前台点 Load & Start Server；或 a19_ctl queue add 先存着。")
        return 2

    r = c.ask_dict(text, a.tokens, a.temp, system=persona(a.persona_full))
    if not r.get("ok"):
        print("容器出错：%s" % r.get("why"))
        return 3

    answer = r.get("answer") or ""
    log("user", text, r.get("model"), r.get("model"), "minis")
    log("assistant", answer, "selfhost", r.get("model"), "minis")

    if a.raw:
        print(answer)
    else:
        print("[A19 · %s · %ss · %s tok/s]"
              % (r.get("model"), r.get("elapsed_s"), r.get("tok_s")))
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
