#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三条车道实测：Worker（云上拼接网）· 直连 vLLM · 本地兜底代理。

量的是页面真正要的东西：首字节时间（TTFB）与整轮耗时，分三档载荷：
  small   36 tokens 左右（闲聊天）
  big     ~20k tokens（长会话，模拟页面 28.9k 会话被裁后）
  tools   带 3 个工具声明（Agent 回合）
读完把读数打成人话表；每条都带上游原话（失败时不许只说"失败"）。

用法：py -3.14 tools/model-bridge/probe-page-lane.py [--lanes worker,direct,proxy] [--big-tokens 20000]
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

GW = os.environ.get("GBT_GATEWAY_TOKEN") or "gbt-gw-20260926"
RUNPOD_KEY = os.environ.get("GBT_POTATO_API_KEY") or os.environ.get("GBT_POTATO_LANE_KEY") or ""

LANES = {
    "worker": {
        "label": "Worker 云上拼接网（身份注入）",
        "url": "https://gbt-potato-cloud-10.paysssk.workers.dev/v1/chat/completions",
        "key": GW,
        "model": "gbt-potato-v8",
    },
    "direct": {
        "label": "直连我们自己的 vLLM",
        "url": "https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1/chat/completions",
        "key": RUNPOD_KEY,
        "model": "/runpod-volume/gbt-v8-v83",
    },
    "proxy": {
        "label": "本地兜底代理 8792",
        "url": "http://127.0.0.1:8792/v1/chat/completions",
        "key": RUNPOD_KEY,
        "model": "/runpod-volume/gbt-v8-v83",
    },
}

FILLER = ("这是第{n}段上下文，用来把提示词撑到长会话规模。内容只是占位，不需要回答，"
          "只用来测量首字节与总耗时。")

TOOLS = [
    {"type": "function", "function": {"name": "read", "description": "读文件",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                                                     "required": ["path"]}}},
    {"type": "function", "function": {"name": "grep", "description": "搜内容",
                                      "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}},
                                                     "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "pwsh", "description": "跑命令",
                                      "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                                                     "required": ["command"]}}},
]


def gw_from_credentials():
    """GW_AUTH 的真源是 DSH 凭据 refs（环境变量 GBT_GATEWAY_TOKEN 那把是旧的，实测 401）。"""
    import re
    p = os.path.join(os.path.expanduser("~"), ".dsh", ".credentials.yaml")
    try:
        t = open(p, encoding="utf-8").read()
    except OSError:
        return ""
    m = re.search(r"(?m)^\s*GW_AUTH:\s*(\S+)\s*$", t)
    return m.group(1).strip().strip("\"'") if m else ""


def load_key():
    global RUNPOD_KEY
    cred = gw_from_credentials()
    if cred:
        LANES["worker"]["key"] = cred
        globals()["GW"] = cred
    if RUNPOD_KEY:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        for name in ("GBT_POTATO_API_KEY", "GBT_POTATO_LANE_KEY"):
            try:
                v = winreg.QueryValueEx(k, name)[0]
            except OSError:
                continue
            RUNPOD_KEY = v
            for lane in LANES.values():
                if "runpod" in lane["url"] or "127.0.0.1" in lane["url"]:
                    lane["key"] = v


def build_prompt(target_tokens):
    # 中文 1 token ≈ 1.5 字，粗略够用
    n = max(1, int(target_tokens / 45))
    body = []
    for i in range(n):
        body.append(FILLER.format(n=i))
    return "以下是长会话历史（只作背景，不必复述）：\n\n" + "\n".join(body) + "\n\n只回答两个字：收到"


def stream_call(lane, messages, tools=None, max_tokens=64, timeout=300):
    body = {"model": lane["model"], "messages": messages, "max_tokens": max_tokens,
            "stream": True, "temperature": 0.3}
    if tools:
        body["tools"] = tools
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(lane["url"], data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + (lane["key"] or ""))
    req.add_header("Accept", "text/event-stream")
    req.add_header("User-Agent", "GBTxiaotudouV8-probe/1.0")
    t0 = time.time()
    out = {"lane": lane["label"], "ttfb_ms": None, "total_ms": None, "chars": 0,
           "chunks": 0, "text": "", "error": None, "status": None, "model": None,
           "identity": None}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out["status"] = resp.status
            buf = b""
            while True:
                chunk = resp.read(1)
                if not chunk:
                    break
                if out["ttfb_ms"] is None:
                    out["ttfb_ms"] = int((time.time() - t0) * 1000)
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    line = line.strip()
                    if not line.startswith(b"data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == b"[DONE]":
                        continue
                    try:
                        j = json.loads(payload)
                    except Exception:
                        continue
                    out["chunks"] += 1
                    if j.get("model"):
                        out["model"] = j.get("model")
                    gbt = j.get("gbt") or (j.get("choices") or [{}])[0].get("gbt")
                    if gbt:
                        out["identity"] = gbt
                    for ch in j.get("choices") or []:
                        piece = (ch.get("delta") or {}).get("content")
                        if piece:
                            out["text"] += piece
    except urllib.error.HTTPError as e:
        out["error"] = "HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:400])
    except Exception as e:  # noqa: BLE001
        out["error"] = "%s: %s" % (type(e).__name__, e)
    out["total_ms"] = int((time.time() - t0) * 1000)
    out["chars"] = len(out["text"])
    out["text"] = out["text"][:80]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", default="worker,direct,proxy")
    ap.add_argument("--big-tokens", type=int, default=20000)
    ap.add_argument("--cases", default="small,big,tools")
    a = ap.parse_args()
    load_key()
    cases = [c.strip() for c in a.cases.split(",") if c.strip()]
    rows = []
    for name in [x.strip() for x in a.lanes.split(",") if x.strip()]:
        lane = dict(LANES[name])
        if lane["url"].startswith("https://api.runpod") or "127.0.0.1" in lane["url"]:
            lane["key"] = RUNPOD_KEY
        else:
            lane["key"] = GW
        for case in cases:
            if case == "small":
                msgs = [{"role": "user", "content": "用一句话介绍你自己。"}]
                r = stream_call(lane, msgs, max_tokens=48)
            elif case == "big":
                msgs = [{"role": "user", "content": build_prompt(a.big_tokens)}]
                r = stream_call(lane, msgs, max_tokens=48)
            else:
                msgs = [{"role": "user", "content": "现在几点？可以用工具查一下。"}]
                r = stream_call(lane, msgs, tools=TOOLS, max_tokens=128)
            r["case"] = case
            r["lane_name"] = name
            rows.append(r)
            print(json.dumps({k: v for k, v in r.items() if k != "identity"},
                             ensure_ascii=False), flush=True)
    print("\n=== 人话表 ===")
    print("%-8s %-6s %8s %10s %8s %7s  %s" % ("lane", "case", "TTFB", "total", "chars", "status", "备注"))
    for r in rows:
        note = r.get("error") or ""
        if not note and r.get("identity"):
            g = r["identity"]
            note = "身份注入 ✓ weights_ours=%s via=%s" % (g.get("weights_ours"), g.get("via"))
        print("%-8s %-6s %8s %10s %8d %7s  %s" % (
            r["lane_name"], r["case"],
            ("%dms" % r["ttfb_ms"]) if r["ttfb_ms"] is not None else "—",
            "%dms" % r["total_ms"], r["chars"], r["status"], note[:90]))
    ok = [r for r in rows if not r["error"] and r["chars"] > 0]
    print("\n可答 %d/%d" % (len(ok), len(rows)))
    return 0 if len(ok) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
