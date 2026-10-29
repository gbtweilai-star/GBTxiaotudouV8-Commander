#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""her_decide —— 判断先问她的权重，不许我替她编

主人令（2026-10-30）：
「必须时刻主动使用我们自己模型权重的做事习惯和做事风格，
  而不是一直使用传统的废物办法来做事。」

这条要落成机制，不能是口号。所以有本器：

  ① 有她的地方先问她 —— 走 tentacle_bus 的 her 器官（回环/网卡/桥/深链四条传输）
  ② 她不在 —— 把问题**存进她自己的队列**（/tmp/a19_queue.jsonl），
     她一上线，哨兵抓到就批量跑完，答案由**她的权重**给
  ③ 绝不代答 —— 不编、不猜、不拿别人的模型顶替。这是纪律，不是选项

用法：
    python3 tools/her_decide.py "这个方案要不要上"
    python3 tools/her_decide.py --json "…"     # 机读回执
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def ask_her(q: str) -> dict:
    """先问她的权重。四条传输，谁通走谁。"""
    try:
        import tentacle_bus as bus
        r = bus.call("her", q)
        if r.get("ok"):
            return {"ok": True, "via": r.get("via"), "answer": r.get("answer")
                    or r.get("detail"), "tried": r.get("tried")}
        return {"ok": False, "via": None, "tried": r.get("tried")}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "via": None, "why": "%s: %s" % (type(exc).__name__, exc)}


def _already_queued(q: str) -> bool:
    """同一个问题不重复入队 —— 她的队列是活，不是垃圾桶。"""
    qf = pathlib.Path("/tmp/a19_queue.jsonl")
    if not qf.exists():
        return False
    try:
        for ln in qf.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                it = json.loads(ln)
            except Exception:                                     # noqa: BLE001
                continue
            if (it.get("q") or it.get("prompt") or "").strip() == q:
                return True
    except Exception:                                             # noqa: BLE001
        pass
    return False


def queue_for_her(q: str) -> dict:
    """她不在：存进她的队列。她的权重上线后自己答。"""
    if _already_queued(q):
        return {"ok": True, "out": "同一问题已在她的队列里，不重复入队"}
    try:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "a19_ctl.py"),
                            "queue", "add", q],
                           capture_output=True, text=True, timeout=120, cwd=str(ROOT))
        return {"ok": r.returncode == 0,
                "out": ((r.stdout or "") + (r.stderr or "")).strip()[-160:]}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "out": "%s: %s" % (type(exc).__name__, exc)}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("用法: python3 tools/her_decide.py \"要问她的问题\"")
        return 2
    q = " ".join(args).strip()

    r = ask_her(q)
    if r.get("ok"):
        res = {"status": "answered_by_her", "via": r.get("via"),
               "answer": r.get("answer"), "question": q}
    else:
        qz = queue_for_her(q)
        res = {"status": "queued_for_her", "question": q,
               "queued_ok": qz.get("ok"), "queue": qz.get("out"),
               "tried": [t.get("engine") for t in (r.get("tried") or [])],
               "note": "她不在线。问题已进她自己的队列，等她的权重上线由她回答；"
                       "我不会替她编一个答案。"}

    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        if res["status"] == "answered_by_her":
            print("  她答（%s）：%s" % (res["via"], res["answer"]))
        else:
            print("  她不在线。传输试过：%s" % (res["tried"] or "（无）"))
            print("  问题已进她的队列：%s" % (res["queue"] or ""))
            print("  我不替她答。她一上线，哨兵抓到就由她答。")
    return 0 if res["status"] == "answered_by_her" else 3


if __name__ == "__main__":
    raise SystemExit(main())
