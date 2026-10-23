# -*- coding: utf-8 -*-
"""三方向生产链 · 总检查（只读）。

一条命令看全：**产物 → 框架编排自审 → 独立审计 → HITL#1 填写 → 合并 → 阻塞**。

设计纪律：
 · 只读盘上与回执，**没有的就写「未做」**，绝不把"没查/没做"折算成"通过"。
 · 路径单一来源：合并目标直接 import `merge_storyboard_fill.TARGETS`，
   免得同一件事在两个脚本里各写一份路径、各漂移一次。
 · 不猜数字：填写进度只在**真有导出件**时才算，没导出就说"未导出"。

用法：py -3.14 tools/codex-scripts/pipeline_status.py
      py -3.14 tools/codex-scripts/pipeline_status.py --json
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS = ROOT / "tools" / "codex-scripts"


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MRG = _load("mrg_status", "merge_storyboard_fill.py")

DIRECTIONS = [
    ("short-video", "短视频", "AI搬砖人"),
    ("music", "音乐", "夜航"),
    ("film", "电影", "老屋"),
]

STAGE_LABEL = {
    "01-script": "选题口播", "02-storyboard": "分镜", "03-raw": "原始素材",
    "04-cut": "剪辑", "05-publish": "发布版", "06-cover": "封面",
    "01-lyrics": "歌词", "02-compose": "旋律", "03-arrange": "编曲",
    "04-mix": "混音", "05-master": "母带", "06-release": "发行",
    "01-screenplay": "剧本", "02-storyboard-film": "分镜", "03-shoot": "拍摄",
    "04-assets": "素材", "05-edit": "剪辑", "06-final": "终版",
}

RECEIPTS = {
    "编排层": ROOT / ".scratch" / "_media_pipeline_receipt.json",
    "独立审计": ROOT / ".scratch" / "_independent_review_receipt.json",
}
FILL_EXPORT = ROOT / "projects" / "_inbox" / "hitl1-storyboard-fill.json"


def read_json(p: Path):
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def stage_files(direction: str) -> list[dict]:
    """列出该方向各工序抽屉里**真正有内容**的文件（跳过 .gitkeep 与彩排件单列）。"""
    base = ROOT / "projects" / direction
    out = []
    if not base.is_dir():
        return out
    for stage in sorted(base.iterdir()):
        if not stage.is_dir() or not re.match(r"^\d\d-", stage.name):
            continue
        for f in sorted(stage.rglob("*")):
            if not f.is_file() or f.name == ".gitkeep":
                continue
            out.append({
                "stage": stage.name,
                "label": STAGE_LABEL.get(stage.name, stage.name),
                "file": str(f.relative_to(ROOT)).replace("\\", "/"),
                "name": f.name, "bytes": f.stat().st_size,
                "rehearsal": "彩排样板" in f.parts,
                "versioned": bool(re.search(r"-v\d+\.md$", f.name)),
            })
    return out


def merge_target(direction: str) -> dict:
    t = MRG.TARGETS.get(direction)
    if not t:
        return {"exists": False}
    rel, tag, need_share, has_board = t
    p = ROOT / rel
    return {"rel": rel, "exists": p.is_file(), "has_board": has_board,
            "need_share": need_share, "bytes": p.stat().st_size if p.is_file() else 0}


def merged_versions(direction: str) -> list[str]:
    t = MRG.TARGETS.get(direction)
    if not t:
        return []
    base = (ROOT / t[0]).with_suffix("")
    found = []
    for p in base.parent.glob(f"{base.name}-v*.md"):
        if re.search(r"-v\d+\.md$", p.name):
            found.append(p.name)
    return sorted(found)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    mp = read_json(RECEIPTS["编排层"]) or {}
    ir = read_json(RECEIPTS["独立审计"]) or {}
    fill = read_json(FILL_EXPORT)

    mp_by = {w.get("kind"): w for w in (mp.get("works") or [])}
    ir_by = {w.get("kind"): w for w in (ir.get("works") or [])}
    KIND = {"short-video": "short_video", "music": "music", "film": "film"}

    # 填写进度：只在真有导出件时才算。没导出就如实说未导出。
    fill_state: dict = {"exported": bool(fill)}
    if fill:
        for d, _l, _n in DIRECTIONS:
            w = (fill.get("works") or {}).get(d) or {}
            shots = w.get("shots") or {}
            g = w.get("globals") or {}
            fill_state[d] = {"shots_filled": len(shots),
                             "shots_cells": len(shots) * 4,
                             "globals_filled": len(g)}

    report = {"works": []}
    rc = 0
    print("=" * 96)
    print("三方向生产链 · 总检查（只读 · 没有的数据一律写「未做」）")
    print("=" * 96)

    for d, label, name in DIRECTIONS:
        print(f"\n{'─' * 96}")
        print(f"  {label} · 《{name}》   ({d})")
        print(f"{'─' * 96}")
        entry = {"direction": d, "label": label, "name": name}

        # ① 产物
        fs = stage_files(d)
        real = [f for f in fs if not f["rehearsal"]]
        reh = [f for f in fs if f["rehearsal"]]
        print(f"  ① 产物     : {len(real)} 件正式 · {len(reh)} 件彩排 · "
              f"{len(merged_versions(d))} 件合并版")
        for f in real:
            v = " [合并版]" if f["versioned"] else ""
            print(f"       {f['label']:<6} {f['name']}  ({f['bytes']} B){v}")
        if not real:
            print("       （无正式产物）")
        entry["artifacts"] = real
        entry["merged_versions"] = merged_versions(d)

        # ② 框架编排自审
        w = mp_by.get(KIND[d])
        if w:
            rv = w.get("review") or {}
            print(f"  ② 编排自审 : {rv.get('passed')}/{rv.get('total')} 项通过 · "
                  f"缺工序 {w.get('stages_absent') or '无'}")
            print(f"       发布口径 {rv.get('publish')} · 未过项 {rv.get('blocked_reasons')}")
            entry["review"] = {"passed": rv.get("passed"), "total": rv.get("total"),
                               "blocked": rv.get("blocked_reasons")}
        else:
            print("  ② 编排自审 : 未做（无回执）")
            entry["review"] = None

        # ③ 独立审计
        i = ir_by.get(KIND[d])
        if i:
            c = i.get("counts") or {}
            print(f"  ③ 独立审计 : {i.get('decision')} → 退回 {i.get('stage_to_return')} "
                  f"（阻断 {c.get('blocker', 0)} / 重要 {c.get('major', 0)} / 次要 {c.get('minor', 0)}）")
            entry["review_decision"] = i.get("decision")
            if i.get("decision") != "pass":
                rc = max(rc, 0)   # 退回不是脚本错误，只是状态
        else:
            print("  ③ 独立审计 : 未做（无回执）")
            entry["review_decision"] = None

        # ④ HITL#1 填写
        fst = fill_state.get(d)
        if fst:
            print(f"  ④ HITL#1填 : 已导出 · 逐镜 {fst['shots_filled']} 镜 / "
                  f"{fst['shots_cells']} 格 · 全局 {fst['globals_filled']} 项")
        else:
            print("  ④ HITL#1填 : **未导出**（填写页还没产出导出件）")
        entry["fill"] = fst

        # ⑤ 合并
        mv = merged_versions(d)
        if mv:
            print(f"  ⑤ 合并     : 已落 {mv}")
        else:
            print("  ⑤ 合并     : 未落（无 -vN 件）")
        entry["merged"] = mv

        # ⑥ 下一步该干什么（按链上第一个缺口说，不跳步）
        nxt = []
        if not w:
            nxt.append("跑 wire_media_pipeline.py 取编排自审")
        if not i:
            nxt.append("跑独立审计")
        if not fill:
            nxt.append("打开填写页填 HITL#1 并导出到 projects/_inbox/")
        elif not mv:
            nxt.append("跑 merge_storyboard_fill.py --apply 落合并件")
        if mv:
            nxt.append("合并件送独立审计复核")
        print(f"  ⑥ 下一步   : {' → '.join(nxt) if nxt else '（链上无明显缺口）'}")
        entry["next"] = nxt
        report["works"].append(entry)

    # 全局阻塞
    print(f"\n{'=' * 96}")
    print("全局阻塞（钥匙没到，②③④ 推不动）")
    print(f"{'=' * 96}")
    grants = ROOT / "store" / "auth_grants.jsonl"
    print(f"  授权台账 auth_grants.jsonl : {'存在 ' + str(grants.stat().st_size) + ' B' if grants.is_file() else '不存在'}")
    import os
    keys = [k for k in ("DEEPSEEK_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY",
                        "ANTHROPIC_API_KEY", "GEMINI_API_KEY") if os.environ.get(k)]
    print(f"  LLM 密钥                   : {keys or '一个都没设'}")
    print(f"  Lark 凭据                  : "
          f"{'存在' if (Path.home() / '.lark-cli' / 'config.json').is_file() else '无'}")
    report["blockers"] = {"grants": grants.is_file(), "llm_keys": keys,
                          "fill_exported": bool(fill)}

    if a.json:
        print("\n" + json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\n{'=' * 96}")
    print("说明：本工具只读。任何「未做」都不等于「通过」—— 缺什么就写缺什么。")
    print(f"{'=' * 96}")
    _LAST_REPORT.clear()
    _LAST_REPORT.update(report)
    return rc


# 供其他消费者（审批屏等）直接取数据，不必去解析 stdout（那是脆的，格式一改就断）。
_LAST_REPORT: dict = {}


def collect() -> dict:
    """跑一次采集并回传结构化结果。

    实现上**复用 main() 这一条路径**，只是把它的打印临时接管掉。
    为什么不另写一份采集：同一件事写两份，迟早各漂移一次
    —— 填写页那个「填一镜串八镜」的 bug 就是这么来的。
    接管 stdout 有点糙，但它是**一处真相**，而且这里明说了。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main([])
    return dict(_LAST_REPORT)


if __name__ == "__main__":
    raise SystemExit(main())
