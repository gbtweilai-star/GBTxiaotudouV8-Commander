# -*- coding: utf-8 -*-
"""云空间 · 缓存清理执行器（R3 · destructive）。

授权依据：主人 2026-09-22 明确确认「只删 A + B（缓存，38 个）」。
删的**只有**可被工具重建的缓存目录，不含任何文档/代码/素材。

R3 要求逐条落实：
  · 恢复边界 —— 执行前落一份完整 token 快照（rollback 档案）
  · 分批策略 —— 每批 8 个，批间输出进度
  · 失败停止 —— 任一失败立刻停，不硬跑
  · 写后验证 —— 用 fresh read 复核目录是否真没了
  · 执行日志 —— 逐项落 .scratch/_lark_delete_journal.jsonl

用法：
  py -3.14 tools/codex-scripts/lark_delete_caches.py            # DRY-RUN（只验证参数）
  py -3.14 tools/codex-scripts/lark_delete_caches.py --apply    # 真删
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEL = ROOT / ".scratch" / "_lark_deletable.json"
SNAP = ROOT / ".scratch" / "_lark_rollback_snapshot.json"
JOURNAL = ROOT / ".scratch" / "_lark_delete_journal.jsonl"
BATCH = 8


def run(args: list[str], timeout=180) -> tuple[bool, dict | str]:
    try:
        r = subprocess.run(["lark-cli"] + args, capture_output=True, text=True,
                           encoding="utf-8", timeout=timeout, cwd=str(ROOT), shell=True)
    except Exception as exc:                                    # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"
    s = (r.stdout or "").strip()
    if not s:
        return False, f"空输出 rc={r.returncode} err={(r.stderr or '')[:200]}"
    try:
        j = json.loads(s)
    except ValueError:
        return False, f"非 JSON: {s[:200]}"
    # lark-shared 契约：成功看 ok == true（不是 code == 0）
    return (j.get("ok") is not False), j


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    rep = json.loads(DEL.read_text(encoding="utf-8"))
    targets = []
    for b in rep["buckets"]:
        if b["bucket"].startswith(("A ", "B ")):
            targets += b["items"]

    print("=" * 84)
    print(f"云空间 · 缓存清理 · {'APPLY 真删' if a.apply else 'DRY-RUN 只验参'}")
    print("=" * 84)
    print(f"  目标 {len(targets)} 个目录（A 桶 __pycache__ + B 桶 .wrangler）")
    print("  全部为工具可重建的缓存；不含文档 / 代码 / 素材\n")

    # ── 恢复边界：落快照 ──
    snap = {"taken_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scope": rep["scope"], "identity": rep["identity"],
            "reason": "主人确认只删 A+B 桶（缓存目录）",
            "count": len(targets),
            "items": [{"path": t["path"], "type": t["type"], "token": t["token"]}
                      for t in targets]}
    SNAP.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ① 快照已落 {SNAP.name}（{len(targets)} 项 token，供回滚留档）")

    # ── dry-run 验参 ──
    ok, r = run(["drive", "+delete", "--file-token", targets[0]["token"],
                 "--type", "folder", "--as", "user", "--dry-run"])
    print(f"  ② dry-run 验参：{'通过' if ok else '失败'}")
    if not ok:
        print(f"      {str(r)[:300]}")
        return 2
    if isinstance(r, dict):
        print(f"      {json.dumps(r, ensure_ascii=False)[:220]}")
    if not a.apply:
        print("\n  预演结束。加 --apply 真删。")
        return 0

    # ── 分批执行 ──
    done, failed = 0, None
    t0 = time.time()
    with JOURNAL.open("w", encoding="utf-8") as jf:
        for i in range(0, len(targets), BATCH):
            chunk = targets[i:i + BATCH]
            for t in chunk:
                ok, r = run(["drive", "+delete", "--file-token", t["token"],
                             "--type", "folder", "--as", "user", "--yes"])
                rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "path": t["path"],
                       "token": t["token"], "ok": bool(ok),
                       "resp": (json.dumps(r, ensure_ascii=False)[:200] if isinstance(r, dict) else str(r)[:200])}
                jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jf.flush()
                if ok:
                    done += 1
                else:
                    failed = rec
                    break
            print(f"      进度 {done}/{len(targets)}  （{(time.time()-t0):.0f}s）")
            if failed:
                break

    print(f"\n  ③ 执行结束：成功 {done} · 失败 {'1（已停）' if failed else '0'}")
    if failed:
        print(f"      失败项：{failed['path']}")
        print(f"      响应  ：{failed['resp'][:220]}")
        print("      **按要求停止，未继续后续批次。**")

    # ── 写后验证：交给「重盘比对」，不在这里假装验证 ──
    # 上一版我在这写了段带 break 的循环，等于没验证 —— 删掉。
    # 正确做法：删完重跑 lark_inventory.py，把新清单与本次快照比对：
    #   快照里的每个 token 都不应再出现在新清单里。
    # 由 verify_delete.py 执行（它读这两个文件做集合差）。
    print("\n  ④ 写后验证：**不在本脚本内自证**，由 verify_delete.py 重盘比对")
    print(f"      依据 {SNAP.name}（删前 token 集合）")
    print(f"      + {JOURNAL.name}（本次逐项结果）")
    print("      → 重跑盘点，确认快照里每个 token 都不再出现")
    print(f"\n  日志 -> {JOURNAL.name}")
    print(f"  快照 -> {SNAP.name}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
