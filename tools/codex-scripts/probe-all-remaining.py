#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把最后剩下的位**全部真跑一遍**（主人令：「全部都要给我跑通」）。

票额现读：process_execute 2 · deploy_publish 4 · privacy_read 2 · data_export 4（window 类可多次，one_shot 用一张少一张）。
所以顺序按票种排，先跑 window 类，再跑 one_shot，避免"跑到一半没票了"。

安全边界（写死）：
  · 隔离 store（写盘/镜像/排练都落临时目录）+ 只读复制真授权账本；
  · `mirror_*` 在**隔离 store** 上跑 ⇒ 它动的是临时镜像空间，不是真交付区；
  · 没有任何一位会碰 `delivery/`、`gbt_allinone/store` 真库、远端仓库。

产出：outputs/open-source-release/data/remaining-probe.json
用法：py -3.12 tools/codex-scripts/probe-all-remaining.py
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
_STORE = pathlib.Path(tempfile.mkdtemp(prefix="gbt_remaining_store_"))
os.environ["GBT_STORE_DIR"] = str(_STORE)
sys.path.insert(0, str(ROOT))

_grants = ROOT / "gbt_allinone" / "store" / "auth_grants.jsonl"
if _grants.is_file():
    (_STORE).mkdir(parents=True, exist_ok=True)
    shutil.copy2(_grants, _STORE / "auth_grants.jsonl")
    print("[票] 真授权账本已复制进隔离 store（%d 行）"
          % len((_STORE / "auth_grants.jsonl").read_text(encoding="utf-8").strip().splitlines()))

from gbt_allinone.api import run_task      # noqa: E402

OUT = ROOT / "outputs" / "open-source-release" / "data" / "remaining-probe.json"
TIMEOUT = 60

CASES = [
    # ── 隐私载体类（privacy_read，window；票额 2 → 先跑两位最典型的）──────────
    ("keylogger", {"op": "status"}),
    ("screen_sniff", {"op": "status"}),
    # ── 起进程类（process_execute，window）────────────────────────────────
    ("mirror_rehearse", {"name": "probe"}),
    ("omarchy_bridge", {"op": "status"}),
    ("remote_confinement", {"op": "status"}),
    ("comfy_cloud", {"op": "status"}),
    ("cli_chat", {"agent": "codebuddy", "message": "只回一个字：好"}),
    ("remote_domain", {"op": "list"}),
    # ── 生产写入类（deploy_publish，one_shot；票额 4）──────────────────────
    ("mirror_ascend", {"name": "probe"}),
    ("mirror_release", {"name": "probe"}),
    ("mirror_rewind", {"name": "probe"}),
    ("pipeline_submit", {"name": "probe", "content": "x"}),
    # ── 出网类（data_export，one_shot；票额 4）────────────────────────────
    ("omni_web", {"url": "https://example.com"}),
    # ── 无需票（缺依赖/缺输入，但必须真调一次拿回执）────────────────────────
    ("code_patch", {"path": "gbt_allinone/api.py", "find": "_run_task_base = run_task",
                    "replace": "_run_task_base = run_task  # probe", "apply": False}),
    ("git_write", {"op": "stage", "paths": ["AGENTS.md"]}),
    ("blender", {"op": "status"}),
    ("tripo", {"op": "status"}),
    ("ul_tars_desktop", {"op": "status"}),
]


def unwrap(resp):
    b = resp.get("gbt_result", resp) if isinstance(resp, dict) else {}
    inner = b.get("result") if isinstance(b, dict) else None
    return (b if isinstance(b, dict) else {}), (inner if isinstance(inner, dict) else {})


def classify(b, i):
    if b.get("denied") or i.get("denied"):
        miss = b.get("missing") or i.get("missing") or []
        return "needs_ticket", "缺票：" + ",".join(miss)
    st = str(b.get("status") or "")
    msg = str(b.get("error") or b.get("message") or i.get("error") or i.get("reason") or "")
    low = msg.lower()
    if "needs_dependency" in low or "未安装" in msg or "not found" in low or "不存在" in msg:
        return "needs_dependency", msg[:150]
    if st == "ok" and i.get("ok") is not False:
        return "ok", "真跑通过（隔离 store）"
    if any(k in msg for k in ("缺少", "需要", "不能为空", "要 ", "未声明", "无此", "user_error")):
        return "needs_input", msg[:150]
    return "failed", (msg or st)[:150]


def one(cap, payload):
    t0 = time.time()
    try:
        with cf.ThreadPoolExecutor(max_workers=1) as ex:
            resp = ex.submit(run_task, cap, payload).result(timeout=TIMEOUT)
        b, i = unwrap(resp)
        v, note = classify(b, i)
        return {"cap": cap, "payload": payload, "status": b.get("status"),
                "verdict": v, "note": note, "elapsed_s": round(time.time() - t0, 2)}
    except cf.TimeoutError:
        return {"cap": cap, "payload": payload, "status": "timeout", "verdict": "failed",
                "note": "> %ds（票可能已消耗）" % TIMEOUT, "elapsed_s": round(time.time() - t0, 2)}
    except Exception as e:                                   # noqa: BLE001
        return {"cap": cap, "payload": payload, "status": "exception", "verdict": "failed",
                "note": "%s: %s" % (type(e).__name__, str(e)[:140]),
                "elapsed_s": round(time.time() - t0, 2)}


def main() -> int:
    rows = []
    for cap, payload in CASES:
        r = one(cap, payload)
        rows.append(r)
        print("%-20s %-16s %-9s %s" % (r["cap"], r["verdict"], r["status"], r["note"][:70]))

    # git_write：真跑了就立刻 reset 复原（只 stage，不 commit）
    try:
        subprocess.run(["git", "-C", str(ROOT), "reset", "-q", "--", "AGENTS.md"],
                       capture_output=True, text=True, timeout=60)
        print("[复原] AGENTS.md 已从索引撤下（未 commit）")
    except Exception as e:                                    # noqa: BLE001
        print("[复原失败]", type(e).__name__, str(e)[:80])

    cnt: dict[str, int] = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": len(rows), "counts": cnt,
           "store": str(_STORE),
           "口径": "隔离 store + 真授权账本副本；mirror_* 跑在临时镜像空间；git_write 只 stage 并立刻 reset；"
                   "隐私类只跑 op=status（不真读屏幕/键盘内容）",
           "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n计数：", cnt, "→", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
