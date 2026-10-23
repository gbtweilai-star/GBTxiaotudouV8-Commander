# -*- coding: utf-8 -*-
"""飞书云空间 · 递归盘点（只读）。

按 lark-drive workflow `knowledge_organize` 的 INVENTORY 规则：
  · Drive 树：max_depth=3 · max_items=500 · 每目录最多 10 页 · page_size=200
  · 只递归 type=folder
  · 结果规范成 ResourceItem（字段照 workflow 的模型）
  · **不执行任何写操作**

结果落 .scratch/_lark_inventory.json，控制台只打摘要。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / ".scratch" / "_lark_inventory.json"

MAX_DEPTH = 3
# 条目上限是**分批检查点**，不是覆盖上限（工作流原文）。
# 第一次跑 500 就撞顶了 → 提到 3000 继续，不许拿半份清单去出方案。
MAX_ITEMS = 3000
MAX_PAGES_PER_DIR = 10
PAGE_SIZE = 200


def cli(params: dict) -> dict:
    """调 lark-cli drive files list，返回 JSON。失败返回 {"ok": False, ...}。"""
    p = json.dumps(params, ensure_ascii=False)
    try:
        r = subprocess.run(
            ["lark-cli", "drive", "files", "list", "--as", "user",
             "--params", p, "--format", "json"],
            capture_output=True, text=True, encoding="utf-8", timeout=90,
            cwd=str(ROOT), shell=True)
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": {"message": f"{type(exc).__name__}: {exc}"}}
    s = (r.stdout or "").strip()
    if not s:
        return {"ok": False, "error": {"message": f"空输出 rc={r.returncode} err={(r.stderr or '')[:200]}"}}
    try:
        return json.loads(s)
    except ValueError:
        return {"ok": False, "error": {"message": f"非 JSON: {s[:200]}"}}


def item(f, path, depth, parent):
    t = f.get("type") or f.get("obj_type") or "?"
    tok = f.get("token") or ""
    return {
        "source": "drive", "title": f.get("name") or "",
        "type": t, "path": f"{path}/{f.get('name') or ''}", "depth": depth,
        "url": f.get("url") or "", "token": tok,
        "node_token": "", "obj_token": tok, "node_type": "",
        "origin_node_token": "", "space_id": "", "parent_token": parent,
        "has_child": t == "folder",
        "dedupe_key": f"drive:{t}:{tok}",
        "created_at": "", "updated_at": "", "needs_review": False, "needs_review_reason": "",
    }


def main() -> int:
    t0 = time.time()
    items: list[dict] = []
    queue = [{"folder_token": "", "path": "", "depth": 0}]
    seen_folders: set[str] = set()
    scanned = 0
    pages_total = 0
    blockers: list[str] = []
    truncated = False

    print("=" * 78)
    print("飞书云空间 · 递归盘点（只读 · 不执行移动或创建）")
    print("=" * 78)
    print(f"  范围：我的空间（Drive 根）· 深度≤{MAX_DEPTH} · 上限 {MAX_ITEMS} 项")
    print("  开始盘点…")

    while queue:
        node = queue.pop(0)
        ft, path, depth = node["folder_token"], node["path"], node["depth"]
        if ft and ft in seen_folders:
            continue
        if ft:
            seen_folders.add(ft)
        if depth > MAX_DEPTH:
            blockers.append(f"深度上限：{path or '根'} 之下的子目录未继续")
            truncated = True
            continue

        page_token, pages = "", 0
        while True:
            params = {"folder_token": ft, "page_size": PAGE_SIZE}
            if page_token:
                params["page_token"] = page_token
            j = cli(params)
            pages += 1
            pages_total += 1
            if j.get("ok") is False:
                msg = (j.get("error") or {}).get("message", "未知")
                blockers.append(f"{path or '根'}：{msg[:110]}")
                break
            data = j.get("data") or {}
            files = data.get("files") or []
            for f in files:
                it = item(f, path, depth, ft)
                items.append(it)
                if it["type"] == "folder" and it["token"]:
                    queue.append({"folder_token": it["token"],
                                  "path": it["path"], "depth": depth + 1})
            scanned += 1
            if len(items) >= MAX_ITEMS:
                truncated = True
                blockers.append(f"条目上限 {MAX_ITEMS} 已到，剩余目录未继续")
                break
            if not data.get("has_more"):
                break
            page_token = data.get("next_page_token") or ""
            if not page_token:
                blockers.append(f"{path or '根'}：has_more 但无 next_page_token")
                break
            if pages >= MAX_PAGES_PER_DIR:
                blockers.append(f"{path or '根'}：单目录页数上限 {MAX_PAGES_PER_DIR}")
                truncated = True
                break
        if truncated and len(items) >= MAX_ITEMS:
            break

    # 统计
    from collections import Counter
    types = Counter(i["type"] for i in items)
    folders = [i for i in items if i["type"] == "folder"]
    lvl1 = [i for i in folders if i["depth"] == 0]
    root_docs = [i for i in items if i["depth"] == 0 and i["type"] != "folder"]

    result = {
        "scope": "drive_root", "identity": "user", "max_depth": MAX_DEPTH,
        "partial": bool(blockers), "blockers": blockers,
        "elapsed_s": round(time.time() - t0, 1),
        "counts": {"total": len(items), "folders": len(folders),
                   "level1_folders": len(lvl1), "root_docs": len(root_docs),
                   "scanned_dirs": len(seen_folders), "pages": pages_total},
        "by_type": dict(types), "items": items,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n  用时 {result['elapsed_s']}s · 扫了 {len(seen_folders)} 个目录 · {pages_total} 页")
    print(f"  资源总数 {len(items)} · 文件夹 {len(folders)} · 一级目录 {len(lvl1)} · 根目录直放文档 {len(root_docs)}")
    print(f"  类型分布：{dict(types)}")
    if blockers:
        print(f"  ⚠ 未完全覆盖（{len(blockers)} 处），逐条：")
        for b in blockers[:8]:
            print(f"     · {b}")
    else:
        print("  ✓ 确认范围内已穷尽")
    print(f"\n  明细 -> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size:,} B)")

    print("\n  一级目录：")
    for i in lvl1:
        n = sum(1 for x in items if x["path"].startswith(i["path"] + "/"))
        print(f"    {i['title']:34} 内含 {n:>4} 项")
    print("\n  根目录直放资源：")
    for i in root_docs:
        print(f"    [{i['type']:9}] {i['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
