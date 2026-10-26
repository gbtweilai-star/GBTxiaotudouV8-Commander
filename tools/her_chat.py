#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""her_chat —— 让「这个框」真正用她的原生权重：**自带预算的多轮**。

难点从来不是"调不通 1234"，是 **4096 装不下**：
Minis 每轮往模型里塞上万 token 的注入，A19 直接爆窗。所以这里自己管上下文：

    system（可选：品味内核/身份）
    + 最近若干轮问答，按预算从旧到新裁
    + 本轮问题
    ≤ 预算   （预算 = 容器 ctx − 输出预留）

用法：
    python3 her_chat.py --ask "你是谁"        # 一轮（自动带最近历史）
    python3 her_chat.py --ask "继续" --kernel # 把品味内核作为 system 一起送
    python3 her_chat.py --show                # 看当前历史与预算占用
    python3 her_chat.py --reset               # 清空历史（不动账本）

历史落 state/her_chat.json；对话同时写进共用账本（source=minis）。
"""
import argparse
import importlib.util
import json
import pathlib
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
STATE = TOOLS.parent / "state"
HIST = STATE / "her_chat.json"
KERNEL = STATE / "taste_kernel.txt"
CTX = 4096            # 容器 ctx（宿主内设定，改不了；见 docs/17）
RESERVE = 640         # 给回答留的 token
MAX_TURNS = 8


def ctl():
    spec = importlib.util.spec_from_file_location("a19ctl", str(TOOLS / "a19_ctl.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def est(text):
    """粗估 token：中文按 1.6 字/token，英文按 4 字符/token，取折中 1.8。"""
    t = str(text or "")
    return max(1, int(len(t) / 1.8))


def load_hist():
    if HIST.exists():
        try:
            return json.loads(HIST.read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            return []
    return []


def save_hist(h):
    STATE.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(h[-MAX_TURNS * 2:], ensure_ascii=False, indent=1),
                    encoding="utf-8")


def build(system, hist, question, budget):
    """从新到旧装历史，装不下就停 —— 保证最终 prompt ≤ budget。"""
    msgs = []
    q_cost = est(question)
    left = budget - q_cost
    if system:
        s_cost = est(system)
        if s_cost + q_cost > budget:      # system 都装不下 ⇒ 只保问题
            system, s_cost = "", 0
        else:
            msgs.append({"role": "system", "content": system})
            left -= s_cost
    picked = []
    for turn in reversed(hist):
        c = est(turn.get("content")) + 4
        if c > left:
            break
        picked.append(turn)
        left -= c
    msgs.extend(reversed(picked))
    msgs.append({"role": "user", "content": question})
    return msgs, budget - left


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask")
    ap.add_argument("--kernel", action="store_true", help="把品味内核当 system 一起送")
    ap.add_argument("--system", default="")
    ap.add_argument("--tokens", type=int, default=512)
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()

    if a.reset:
        save_hist([])
        print("历史已清空（账本不动）")
        return 0

    hist = load_hist()

    if a.show:
        budget = CTX - min(RESERVE, max(200, a.tokens))
        print("预算 ctx=%d − 输出预留=%d ⇒ prompt 预算 %d token" % (CTX, min(RESERVE, a.tokens), budget))
        used = sum(est(t.get("content")) for t in hist)
        print("历史 %d 条 · 约占 %d token（%.0f%%）" % (len(hist), used, used * 100.0 / budget))
        for t in hist[-6:]:
            print("  %-9s %s" % (t.get("role"), (t.get("content") or "")[:60].replace("\n", " ")))
        return 0

    if not a.ask:
        print("用法: her_chat.py --ask \"问题\" [--kernel] | --show | --reset")
        return 1

    system = a.system
    if a.kernel and KERNEL.exists():
        system = KERNEL.read_text(encoding="utf-8")

    budget = CTX - min(RESERVE, max(200, a.tokens))
    msgs, used = build(system, hist, a.ask, budget)

    c = ctl()
    st = c.status_dict()
    if st.get("container") != "UP":
        print("容器不在 —— 她这会儿没有嘴（:1234 无监听）。历史未改动。")
        return 2

    r = c.chat_dict(msgs, a.tokens, a.temp)
    if not r.get("ok"):
        print("容器出错：%s" % r.get("why"))
        return 3

    hist += [{"role": "user", "content": a.ask},
             {"role": "assistant", "content": r.get("answer") or ""}]
    save_hist(hist)

    print("[A19 · %s · %ss · %s tok/s · prompt≈%d/%d]"
          % (r.get("model"), r.get("elapsed_s"), r.get("tok_s"), used, budget))
    print(r.get("answer") or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
