#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「需参数」的能力位**真带参数跑一遍**（不再记成"没跑"）。

口径（写死）：
  · 一切走唯一门 `gbt_allinone.api.run_task`；
  · **隔离 store**：本脚本自己把 GBT_STORE_DIR 指到临时目录 ⇒ 写盘/建工作流/建调度都落在临时账上，
    不碰生产账本与产物（跑完目录留在 %TEMP%，不删是为了让读的人能自己去看）；
  · 参数是**人写的样本**（不自动猜）——猜出来的参数跑绿了也不算证明；
  · 结果如实分五类：ok / needs_ticket / needs_dependency / needs_input / failed。
  · 只跑**只读或落在临时 store 里**的动作；不部署、不推远端、不发消息（要票的会当场 denied，正好当证据）。

产出：outputs/open-source-release/data/params-probe.json
用法：py -3.12 tools/codex-scripts/probe-caps-params.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
# 必须先设 store，再 import 框架（_paths 在 import 时就定死了落点）
_STORE = pathlib.Path(tempfile.mkdtemp(prefix="gbt_params_store_"))
os.environ["GBT_STORE_DIR"] = str(_STORE)
os.environ.pop("GBT_OWNER_SESSION", None)          # 按非主人跑：要票的就该被拒，这是结构证明
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, str(ROOT))

from gbt_allinone.api import run_task                 # noqa: E402

OUT = ROOT / "outputs" / "open-source-release" / "data" / "params-probe.json"

# 顺序有意义：wf_define 必须在 wf_run 之前（同一个临时 store 里才认得出来）
CASES: list[tuple[str, dict, str]] = [
    ("brain_route", {"intent": "统计一下这段话有多少个词"}, "语义路由：给意图，回最佳落点"),
    ("brain_execute", {"kind": "echo"}, "指定能力直跑"),
    ("brain_unify", {"goal": "统计一下这段话有多少个词"}, "五维合一全链"),
    ("tentacle", {"action": "available_actions"}, "触手：列出可用动作（只读）"),
    ("persona_kernel", {"op": "constitution"}, "人格内核：读宪章（只读）"),
    ("pipeline_versions", {"name": "gbt-potato-v8"}, "流水线版本列表（只读）"),
    ("impact_check", {"symbol": "run_task"}, "影响面检查（只读）"),
    ("deploy_queue", {"op": "list"}, "部署队列列表（只读）"),
    ("git_write", {"op": "status"}, "版本库写面入口：先看 status（不改盘）"),
    ("code_patch", {"path": "gbt_allinone/api.py"}, "改代码：默认 dry_run（不落盘）"),
    ("record_grid", {"text": "width: 10\nheight: 20", "op": "parse"}, "行式记录解析"),
    ("wf_define", {"name": "probe_wf",
                   "nodes": [{"id": "a", "kind": "echo", "payload": {"text": "hello"}}]},
     "定义工作流（落临时 store）"),
    ("wf_run", {"name": "probe_wf"}, "跑刚定义的工作流（真跑）"),
    ("wf_resume", {"run_id": "probe-none"}, "续跑一个不存在的 run（应如实报找不到）"),
    ("sched_define", {"name": "probe_sched", "workflow": "probe_wf", "every_seconds": 3600},
     "建一条调度（落临时 store）"),
    ("lr_submit", {"description": "探针：证明长程任务能提交", "kind": "echo", "max_attempts": 1},
     "提交长程任务（落临时 store）"),
    ("osint_scan", {"target": "8.8.8.8"}, "公网目标（不该被内网护栏挡）"),
    ("omni_web", {"url": "https://example.com"}, "读一个公网页面"),
    ("browser", {"url": "https://example.com"}, "开浏览器（要 browser_control 票）"),
    ("codex_chat", {"message": "只回一个字：好"}, "跟 Codex 说一句（要起进程）"),
    ("codex_turn_send", {"thread_id": "probe-none", "text": "回一个字：好"}, "Codex 写操作"),
    ("codex_interrupt", {"thread_id": "probe-none"}, "打断一个不存在的线程"),
    ("sec_llm", {"prompt": "回一个字：好", "max_tokens": 64}, "黑客大脑（要 external_llm 票）"),
    ("autopilot", {"goal": "列一条当前告警"}, "自主环"),
    ("think_loop", {"goal": "给一句今日提醒"}, "思考环"),
    ("topic_watch", {"need": "帮我盯着 AI 行业动态", "op": "route"}, "题材盯梢（只读路由）"),
    ("devour_github", {"repo": "https://github.com/octocat/Hello-World"}, "吞一个公开仓库"),
    ("one_key_deploy", {"target": "probe-none"}, "一键部署（要 deploy_publish 票）"),
    ("pipeline_rollback", {"name": "probe-none"}, "回滚（要 deploy_publish 票）"),
]


def unwrap(resp) -> tuple[dict, dict]:
    body = resp.get("gbt_result", resp) if isinstance(resp, dict) else {}
    inner = body.get("result") if isinstance(body, dict) else None
    return (body if isinstance(body, dict) else {}), (inner if isinstance(inner, dict) else {})


def classify(body: dict, inner: dict) -> tuple[str, str]:
    st = str(body.get("status") or "")
    if body.get("denied") or inner.get("denied"):
        miss = body.get("missing") or inner.get("missing") or body.get("missing_scopes") or []
        return "needs_ticket", "缺票：%s" % ",".join(miss) if miss else "缺票（门拒）"
    msg = str(body.get("error") or body.get("message") or inner.get("error") or inner.get("reason") or "")
    if st == "ok" and inner.get("ok") is not False:
        return "ok", "真跑通过"
    if "needs_dependency" in msg or "needs_dependency" in st:
        return "needs_dependency", msg[:160]
    if any(k in msg for k in ("需要", "缺少", "必填", "要 image/out", "user_error")):
        return "needs_input", msg[:160]
    return "failed", (msg or st)[:160]


def main() -> int:
    rows = []
    for name, payload, why in CASES:
        t0 = time.time()
        try:
            resp = run_task(name, payload)
            body, inner = unwrap(resp)
            verdict, note = classify(body, inner)
            status = body.get("status")
        except Exception as e:                                  # noqa: BLE001
            body, inner, status = {}, {}, "exception"
            verdict, note = "failed", "%s: %s" % (type(e).__name__, str(e)[:160])
        rows.append({"cap": name, "why": why, "payload": payload, "status": status,
                     "verdict": verdict, "note": note,
                     "elapsed_s": round(time.time() - t0, 2)})
        print("%-18s %-16s %-7s %s" % (name, verdict, status, note[:70]))

    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    doc = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "store": str(_STORE),
        "session": "非主人会话（GBT_OWNER_SESSION 已移除）",
        "total": len(rows),
        "counts": cnt,
        "口径": "人写样本参数（不自动猜）；要票的当场 denied 并记缺哪张票；写盘/建工作流落临时 store；"
                "不部署、不推远端、不发消息",
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n合计 %d 位：%s" % (len(rows), cnt))
    print("落账 →", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
