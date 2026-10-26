#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_switch —— 把「本框要不要切到 A19」变成算出来的结论，不是拍脑袋。

判定依据（缺一个就不许切）：
  1) 容器活着（:1234 真探，且 /v1/models 200）
  2) 窗口预算够：会话估算 token ≤ 预算
     预算 = prefill 实测算出的「窗口内可吃 token」（/tmp/a19_ready.json），
     没有实测就退回保守值 ctx*0.6（4096*0.6≈2458）
  3) 切完有退路：能一条命令切回（打印出来）

用法：
    python3 tools/a19_switch.py                # 用当前会话估算
    python3 tools/a19_switch.py --tokens 5000  # 指定估算
    python3 tools/a19_switch.py --apply        # 判定通过就真的切（需你确认）
"""
import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
A19_ENTRY = "entry:4EFFE91A-06A9-445D-83B2-E398A556B2D4/gbt-v8-v82-q5_0"
BACK_ENTRY = "entry:8A656D95-CB0D-4927-9466-292C2C1C89BC/deepseek-flash"


def load(name):
    spec = importlib.util.spec_from_file_location("m_" + name, str(TOOLS / name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def session_tokens():
    """当前会话的粗估 token（可见消息；系统注入另计）。"""
    try:
        out = subprocess.run(["minis-sessions-cli", "list", "--limit", "1"],
                             capture_output=True, text=True, timeout=30).stdout
        sid = json.loads(out)["data"]["sessions"][0]["session_id"]
        out = subprocess.run(["minis-sessions-cli", "messages", "--id", sid],
                             capture_output=True, text=True, timeout=60).stdout
        msgs = json.loads(out).get("data", {}).get("messages") or []
        chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs)
        return chars // 2, sid, len(msgs)
    except Exception:                                             # noqa: BLE001
        return None, None, None


def budget():
    """窗口预算：优先用 prefill 实测。"""
    p = "/tmp/a19_ready.json"
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            b = ((d.get("prefill") or {}).get("window_prompt_budget_tokens"))
            if b:
                return int(b), "prefill 实测 /tmp/a19_ready.json"
            ctx = None
        except Exception:                                         # noqa: BLE001
            pass
    ctl = load("a19_ctl.py")
    st = ctl.status_dict()
    ctx = st.get("ctx") or 4096
    return int(ctx * 0.6), "保守值 ctx(%s)*0.6（还没跑 prefill 实测）" % ctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    ctl = load("a19_ctl.py")
    st = ctl.status_dict()
    tok, sid, nmsg = (a.tokens, None, None) if a.tokens else session_tokens()
    bud, why = budget()

    print("容器   %s · %s" % (st.get("container"), st.get("why") or "models=%s" % st.get("models")))
    print("预算   %d token（%s）" % (bud, why))
    print("会话   %s token%s" % (tok if tok is not None else "?",
                                "（%s 条消息）" % nmsg if nmsg else ""))

    ok = True
    if st.get("container") != "UP":
        ok = False
        print("判定   ✗ 容器不在 —— 切过去必断，不许切")
    elif tok is None:
        ok = False
        print("判定   ✗ 量不到会话规模，不许盲切")
    elif tok > bud:
        ok = False
        print("判定   ✗ 会话 %d > 预算 %d —— 切过去会被裁（丢记忆/丢工具/丢自我认知）" % (tok, bud))
    else:
        print("判定   ✓ 可以切（%d ≤ %d）" % (tok, bud))

    print("退路   minis-config set session.primaryModel '\"%s\"'" % BACK_ENTRY)
    if not ok:
        print("动作   不切。继续走旁路：a19_ctl ask \"问题\"（只送问题本身，4096 够）")
        return 1

    if a.apply:
        print("执行   切到 A19 …")
        r = subprocess.run(["minis-config", "set", "session.primaryModel",
                            '"%s"' % A19_ENTRY], capture_output=True, text=True)
        print(r.stdout[:300] or r.stderr[:300])
        return 0 if '"ok" : true' in r.stdout else 2
    print("动作   判定通过，但未下切（加 --apply 才动手）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
