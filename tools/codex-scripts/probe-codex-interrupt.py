# -*- coding: utf-8 -*-
"""codex 打断链真跑探针：**同一进程内**连做三步（thread_new → turn_send → interrupt）。

## 为什么必须同进程（2026-10-21 量出来的三层）

`codex_interrupt` 长期记 `needs_input`，回执只有一句 `no active turn to interrupt`。实测三层：

  ① **跨进程必然丢线程**：`get_shared_server()` 的缓存是**进程级**的，而每条
     `five-dim.py cap` 都是一次新 python 进程、app-server 也跟着新建 ⇒
     进程 A 开的线程，进程 B 拿不到（实测回执 `thread not found`）。
  ② **`start_turn` 不是阻塞的**：实测 **0.28s** 就返回，且回执里直接带 `turn.id`
     ⇒ 拿到 turnId 那一刻回合**还活着**，可以真打断。
     （上一版推断「它要等回合跑完才返回」是错的 —— 真正晚的是跨进程那一步。）
  ③ **通知是稀疏的**：0.28s 内只见到 `mcpServer/startupStatus/updated` 一条
     ⇒ 不能靠订阅 `turn/*` 抓 turnId，必须用 `start_turn` 的返回值。

## 口径

  · 三步各自走 `api.run_task` **唯一门**（授权/审计/钢印都在门上），不直调模块函数；
  · 需要作用域：`process_execute` + `external_llm`（主人在终端发的时段票）；
  · 产物：`data/codex-interrupt-live.json`（消费者：`gen-capability-proof.py` ①g 段）；
  · 失败也落账：错误原话照抄，不许把「没跑成」写成「没这个功能」。

用法：
    py -3.14 -X utf8 tools/codex-scripts/probe-codex-interrupt.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import api                      # noqa: E402

DATA = ROOT / "outputs" / "open-source-release" / "data"


def _call(kind: str, payload: dict) -> dict:
    try:
        env = api.run_task(kind, payload)
    except Exception as exc:                       # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)[:300]}
    result = env.get("result") if isinstance(env.get("result"), dict) else {}
    # run_task 的信封是**两段**：外层 {ok,kind,result,...}，内层 {status,kind,result,authorization}
    # 只读一层会拿到空表 ⇒ 会把「开线程成功」误判成「没成」（2026-10-21 实测踩过）。
    if isinstance(result.get("result"), dict) and "kind" in result:
        result = result["result"]
    return {
        "ok": bool(env.get("ok")) and bool(result),
        "denied": env.get("denied"),
        "missing_scopes": env.get("missing_scopes") or result.get("missing_scopes"),
        "result": result,
        "status": env.get("status"),
        "error": env.get("error") or (result or {}).get("message"),
    }


def main() -> int:
    steps: dict = {}
    t0 = time.time()

    new = _call("codex_thread_new", {})
    thread_id = str(((new.get("result") or {}).get("thread") or {}).get("id") or "")
    steps["thread_new"] = {"ok": bool(thread_id), "thread_id": thread_id,
                           "error": new.get("error"), "denied": new.get("denied"),
                           "missing_scopes": new.get("missing_scopes")}
    if not thread_id:
        steps["thread_new"]["why"] = "开线程就没成，后面的步骤无从谈起（原话见 error）"
        return _dump(steps, t0)

    # 足够长的任务：让回合有东西可干（但它返回得很快，不靠它拖时间）
    text = ("请把这份仓库里 341 个能力位逐条列出来，每个位写清用途、参数、是否需要授权；"
            "按 30 个域分组，务必写满、不要省略任何一位、不要提前收尾。")
    t_send = time.time()
    send = _call("codex_turn_send", {"thread_id": thread_id, "text": text})
    send_s = round(time.time() - t_send, 2)
    turn_id = str(((send.get("result") or {}).get("turn") or {}).get("id") or "")
    steps["turn_send"] = {
        "ok": bool(turn_id),
        "turn_id": turn_id,
        "seconds": send_s,
        "note": "start_turn 回执里直接带 turn.id（实测约 0.3s）⇒ 此刻回合还在跑，可以真打断",
        "error": send.get("error"),
        "denied": send.get("denied"),
        "missing_scopes": send.get("missing_scopes"),
    }
    if not turn_id:
        return _dump(steps, t0)

    intr = _call("codex_interrupt", {"thread_id": thread_id, "turn_id": turn_id})
    steps["interrupt"] = {
        "ok": bool(intr.get("ok")),
        "error": intr.get("error"),
        "denied": intr.get("denied"),
        "missing_scopes": intr.get("missing_scopes"),
        "result": {k: v for k, v in (intr.get("result") or {}).items()
                   if k in ("turn", "status", "id", "message")},
    }
    return _dump(steps, t0)


def _dump(steps: dict, t0: float) -> int:
    ok = all((steps.get(k) or {}).get("ok") for k in ("thread_new", "turn_send", "interrupt"))
    doc = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema": "codex-interrupt-live-v1",
        "ok": ok,
        "elapsed_s": round(time.time() - t0, 2),
        "steps": steps,
        "law": ("三步必须在**同一进程**里连做（shared app-server 是进程级缓存，跨 cap 调用会 "
                "thread not found）；turnId 取 start_turn 的返回值（它 ~0.3s 就回，回合还活着）；"
                "三跳各自都过 run_task 唯一门。"),
    }
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "codex-interrupt-live.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    print("落账 →", out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
