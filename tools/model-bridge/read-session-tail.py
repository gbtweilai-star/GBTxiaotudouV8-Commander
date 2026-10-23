#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""读会话账本的尾巴（只读）：把最后 N 条事件的关键字段打成一行行。

为什么要有它：页面卡住时，界面只给一个转圈，真因写在会话账本里
（provider 报错 / 流断了 / 工具回合超时）。判据必须来自账本，不来自印象。
"""
import argparse
import json
import os
import re
import sys

import zstandard as zstd


def find_session(pattern=None):
    root = os.path.join(os.path.expanduser("~"), ".dsh", "sessions")
    best = None
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f != "session.v3.jsonl.zstd":
                continue
            p = os.path.join(dp, f)
            if pattern and pattern not in p:
                continue
            mt = os.path.getmtime(p)
            if best is None or mt > best[0]:
                best = (mt, p)
    return best[1] if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default=None, help="路径片段（默认取最新）")
    ap.add_argument("--tail", type=int, default=25)
    ap.add_argument("--grep", default=None, help="只看含该词的事件")
    ap.add_argument("--full", action="store_true", help="整条打印")
    a = ap.parse_args()
    p = find_session(a.session)
    if not p:
        print("没找到会话账本")
        return 2
    print("session:", p, "size=%.1fMB" % (os.path.getsize(p) / 1e6))
    raw = open(p, "rb").read()
    try:
        blob = zstd.ZstdDecompressor().decompress(raw, max_output_size=1 << 30)
    except Exception:
        # 多帧：用流式读
        d = zstd.ZstdDecompressor()
        with open(p, "rb") as fh:
            blob = d.stream_reader(fh).read()
    lines = blob.splitlines()
    print("events:", len(lines))
    sel = []
    for ln in lines:
        try:
            j = json.loads(ln)
        except Exception:
            continue
        s = json.dumps(j, ensure_ascii=False)
        if a.grep and a.grep not in s:
            continue
        sel.append(j)
    for j in sel[-a.tail:]:
        if a.full:
            print(json.dumps(j, ensure_ascii=False)[:2000])
            continue
        t = j.get("type") or j.get("kind") or "?"
        bits = [str(t)]
        for k in ("role", "provider", "model", "status", "error", "reason", "ms", "durationMs", "stopReason", "finishReason"):
            if k in j and j[k] not in (None, "", []):
                v = j[k]
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)[:120]
                bits.append("%s=%s" % (k, str(v)[:140]))
        msg = j.get("message") or {}
        if isinstance(msg, dict) and msg.get("content"):
            c = msg["content"]
            c = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
            bits.append("content=" + re.sub(r"\s+", " ", c)[:160])
        print(" · ".join(bits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
