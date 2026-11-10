# -*- coding: utf-8 -*-
"""对话「每一步可见」判据（2026-11-07 主人令）。

主人原话：「我要的是跟 Codex 一样的显示，而不是直接显示出来……她开始执行任务每一步都要
能看到她在干嘛执行到哪里每一个步骤都要精细显示出来」。

这里锁四件事，全部跑真的：
  ① 服务端 `_chat` 每跨一个阶段就回调一条**实测**步骤（seq 递增、ms 来自 perf_counter）；
  ② POST /api/chat 带 stream=true 时回 `text/event-stream`，一条一条推，最后再给 final；
  ③ 不带 stream 时仍是原来的单个 JSON（旧调用方与测试不受影响）；
  ④ 前端按到达顺序追加步骤（turn.step），不整段闪现。

跑法：python tests/test_chat_live_steps.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))
    if not cond:
        FAILED.append(name)


def load_server():
    spec = importlib.util.spec_from_file_location("console_server_live_steps", ROOT / "tools" / "console-server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    os.environ["GBT_ENGINE_AUTOSTART"] = "0"
    js = (ROOT / "holo_pet_w3" / "console" / "app.js").read_text(encoding="utf-8")
    srv_src = (ROOT / "tools" / "console-server.py").read_text(encoding="utf-8")

    print("[1] 前端：步骤是追加出来的，不是整段替换")
    check("turn.step 存在", "step: function (rec)" in js)
    check("读 SSE 流", "_readChatStream" in js and "text/event-stream" in js)
    check("请求带 stream:true", "stream: true" in js)
    check("当前步骤自动展开", 'wrap.querySelectorAll(".step-body")' in js)
    check("最终回执优先用实测步骤", "Array.isArray(j.steps)" in js)

    print("[2] 服务端：逐步回调 + SSE 通道")
    check("_ChatSteps 存在", "class _ChatSteps:" in srv_src)
    check("_chat 接 on_step", "on_step=None" in srv_src)
    check("SSE 路由", 'body.get("stream") is True' in srv_src and "_chat_stream" in srv_src)
    check("流式响应头", "text/event-stream; charset=utf-8" in srv_src)

    mod = load_server()

    print("[3] 真跑 _chat：每一步有序、耗时是实测")
    import gbt_allinone.energy_core as E
    import gbt_allinone.omni_plug as OP
    old_think, old_plug, old_settings = E.think, OP.plug_and_run, mod._settings_load
    E.think = lambda *a, **k: {"ok": True, "text": "你好", "ms": 7,
                               "usage": {"completion_tokens": 3}, "context": {"mode": "stub"}}
    OP.plug_and_run = lambda *a, **k: {"ok": False, "error": "stub: no engine"}
    mod._settings_load = lambda: {}
    seen = []
    try:
        res = mod._chat("你好，介绍一下你自己", on_step=seen.append)
    finally:
        E.think, OP.plug_and_run, mod._settings_load = old_think, old_plug, old_settings
    check("_chat 仍有原回执", res.get("ok") is True and res.get("via"), res.get("via"))
    check("至少 5 步", len(seen) >= 5, len(seen))
    check("seq 从 1 连续递增", [x["seq"] for x in seen] == list(range(1, len(seen) + 1)),
          [x["seq"] for x in seen])
    check("有实测 ms（>0）", any(isinstance(x.get("ms"), (int, float)) and x["ms"] > 0 for x in seen),
          [(x["title"], x.get("ms")) for x in seen])
    check("有开始/收尾", any("接收指令" in x["title"] for x in seen)
          and any("交付回执" in x["title"] for x in seen), [x["title"] for x in seen])
    check("保留最终答案", "你好" in str(res.get("text") or ""))

    print("[3.5] 指挥官派发：命中安全命令时真执行，而不是交模型")
    from gbt_allinone import operator_index as OI
    from gbt_allinone.tools import commander_dispatch as CD
    old_gate, old_log = OI.gate, OI.log_gate
    old_run = CD.api.run_task
    fake_body = {"ok": True, "op": "scan", "页数": 20, "绑好": 20, "未绑好": 0,
                 "唯一能力位": 410, "实探能力位": 410,
                 "绿": 380, "黄": 28, "红": 2,
                 "红名单": [{"cap": "x", "why": "boom"}],
                 "黄名单": [], "结论": "有红/有缺口 ⇒ 见名单", "用时秒": 1.2}
    fake_env = {"ok": True, "status": "ok", "kind": "page_scan",
                "result": {"status": "ok", "kind": "page_scan", "result": fake_body}}
    OI.gate = lambda text, topk=5: {
        "hit": True, "why": "测试命中", "margin": 0.5,
        "top": [{"cap": "page_scan", "score": 1.0, "source": "curation"}],
    }
    OI.log_gate = lambda *a, **k: None
    CD.api.run_task = lambda cap, payload, safe=True: fake_env
    seen_cd = []
    try:
        res_cd = mod._chat("那你自己全量扫描一遍看看还有那些没有接好",
                           on_step=seen_cd.append)
    finally:
        OI.gate, OI.log_gate = old_gate, old_log
        CD.api.run_task = old_run
    check("派发即真执行", res_cd.get("via") == "commander-dispatch:page_scan",
          res_cd.get("via"))
    check("回执带真实红名单", "红名单" in str(res_cd.get("text") or ""),
          res_cd.get("text"))
    check("步骤里有派发与执行",
          any("指挥官派发" in x["title"] for x in seen_cd)
          and any("执行能力位" in x["title"] for x in seen_cd),
          [x["title"] for x in seen_cd])

    print("[4] 真跑 SSE：一条一条到，最后才 final")
    def fake_chat(**kw):
        cb = kw.get("on_step")
        for i in range(1, 4):
            if cb:
                cb({"seq": i, "title": "步骤%d" % i, "rows": [["k", "v"]],
                    "ms": 5.0 * i, "state": "running" if i == 3 else "done",
                    "at_ms": 5 * i})
        return {"ok": True, "text": "done", "via": "test-lane"}

    real_chat = mod._chat
    mod._chat = fake_chat
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    try:
        body = json.dumps({"text": "hi", "stream": True}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:%d/api/chat" % port, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            ctype = r.headers.get("Content-Type") or ""
            raw = r.read().decode("utf-8")
        events = [json.loads(x[5:].strip()) for x in raw.splitlines()
                  if x.startswith("data:")]
        steps = [e for e in events if e.get("type") == "step"]
        finals = [e for e in events if e.get("type") == "final"]
        check("响应是 SSE", "text/event-stream" in ctype, ctype)
        check("收到 3 条 step", len(steps) == 3, len(steps))
        check("step 顺序正确", [s["seq"] for s in steps] == [1, 2, 3],
              [s.get("seq") for s in steps])
        check("只有 1 条 final 且在最后", len(finals) == 1 and events[-1].get("type") == "final",
              [e.get("type") for e in events])
        check("final 带回实测步骤", len((finals[0].get("result") or {}).get("steps") or []) == 3,
              finals[0].get("result") if finals else None)

        body2 = json.dumps({"text": "hi"}).encode("utf-8")
        req2 = urllib.request.Request("http://127.0.0.1:%d/api/chat" % port, data=body2,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req2, timeout=15) as r2:
            j = json.loads(r2.read().decode("utf-8"))
        check("非流式仍是单个 JSON", j.get("ok") is True and j.get("via") == "test-lane", j)
    finally:
        mod._chat = real_chat
        httpd.shutdown()
        httpd.server_close()

    print()
    if FAILED:
        print("FAILED: %d" % len(FAILED))
        for x in FAILED:
            print("  - " + x)
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
