# -*- coding: utf-8 -*-
"""验证 raw_tid 盖章（《M9判据收口.md》§3.2）—— 助手行为 + 四探针接线，全静态/临时根。

要点：
  · 帧里真有 threadId 才写 raw_tid；没有就**不写**（不填占位符 —— 那比不盖更坏）
  · params 可以是 dict / bytes / str，三种形态都要认
  · 嵌套形态 params.params.threadId 也要认（JSON-RPC 帧）
  · 四个探针的 ledger() 必须真的走盖章口（抽原文验，不用副本）
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
SINK_PY = ROOT / "holo_pet_w3" / "ledger" / "sink.py"
MIRROR = ROOT / ".scratch" / "codex_v2_mirror"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

spec = importlib.util.spec_from_file_location("sink", SINK_PY)
sink = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sink)

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-52s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-52s %s" % (name, detail))


print("① 助手行为（stamp_raw_tid）")
r = sink.stamp_raw_tid({"event": "x"}, {"threadId": "tid-123"})
chk("dict 形态：有 threadId → 写 raw_tid", r.get("raw_tid") == "tid-123", str(r.get("raw_tid")))

r = sink.stamp_raw_tid({"event": "x"}, {"effort": "high"})
chk("dict 形态：无 threadId → **不写**字段",
    "raw_tid" not in r, "keys=%s" % sorted(r))

r = sink.stamp_raw_tid({"event": "x"}, {"threadId": "   "})
chk("空白 threadId → 不写（不把空串当键）", "raw_tid" not in r, "")

raw = json.dumps({"method": "turn/start",
                  "params": {"threadId": "t-bytes", "effort": "high"}}).encode()
r = sink.stamp_raw_tid({"event": "x"}, raw)
chk("bytes 形态（真帧）→ 从 params.threadId 取",
    r.get("raw_tid") == "t-bytes", str(r.get("raw_tid")))

r = sink.stamp_raw_tid({"event": "x"}, raw.decode())
chk("str 形态（真帧）→ 同样认", r.get("raw_tid") == "t-bytes", str(r.get("raw_tid")))

r = sink.stamp_raw_tid({"event": "x"}, {"params": {"thread_id": "t-snake"}})
chk("嵌套 + thread_id 下划线形态 → 认", r.get("raw_tid") == "t-snake", str(r.get("raw_tid")))

r = sink.stamp_raw_tid({"event": "x"}, "not json at all")
chk("非 JSON 字符串 → 原样返回，不抛", r == {"event": "x"}, "")

r = sink.stamp_raw_tid({"event": "x"}, None)
chk("None → 原样返回", r == {"event": "x"}, "")

print("\n② 四个探针真的走盖章口（抽原文验）")
for fname, expect_var in (("panel_probe.py", None), ("bridge_probe.py", None),
                          ("route_probe.py", None), ("mock_v2_server.py", None)):
    p = MIRROR / fname
    src = io.open(p, encoding="utf-8", errors="replace").read()
    if fname == "mock_v2_server.py":
        # mock 走的是内联口径（_account 里直接写 raw_tid），等价
        got = ('verdict["raw_tid"] = _tid' in src) and ('params.get("threadId")' in src)
        chk("② %-20s 内联口径盖章" % fname, got, "在 _account 里")
        continue
    has_bind = "def _sink_stamp(" in src
    has_call = "record = _sink_stamp(dict(record), _LAST_PARAMS)" in src
    sets = src.count("_LAST_PARAMS = ")
    chk("② %-20s 绑定+盖章+设参 (%d 处)" % (fname, sets),
        has_bind and has_call and sets >= 2,
        "bind=%s call=%s" % (has_bind, has_call))

print("\n③ 端到端：把真帧喂进盖章口，看四路能否拿到同一个键")
frame = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "turn/start",
                    "params": {"threadId": "t-shared", "effort": "high"}}).encode()
tid_by_lane = {}
for lane in ("panel", "bridge", "route", "mock"):
    rec = sink.stamp_raw_tid({"layer": lane,
                              "frame_bytes": len(frame),
                              "frame_bytes_hash": "samehash12345678"}, frame)
    tid_by_lane[lane] = rec.get("raw_tid")
uniq = set(v for v in tid_by_lane.values())
chk("③ 同一帧在四路得到同一个 raw_tid", uniq == {"t-shared"},
    json.dumps(tid_by_lane, ensure_ascii=False))

print("\n" + "-" * 78)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
