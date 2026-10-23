# -*- coding: utf-8 -*-
"""把三件作品接进框架的 `media_pipeline` 编排层（**只调纯函数**）。

安全边界（读源码后确认）：
 · plan / knowledge / collaborate / review = 纯函数（review 只写审计台账）→ 本脚本只用这四个
 · compose / launch_cycle 会写盘（room_space.create / long_run_supervisor.create）→ **不调**
 · publish 即使传 authorization 也拒绝（"模块不接受自带令牌绕门"）→ **不调**

喂进去的是**真 sha256**（现算盘上文件），不是编的哈希。
产物：.scratch/_media_pipeline_receipt.json（供审批屏渲染）
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gbt_allinone import run_task  # noqa: E402

TODAY = "20260921"
OUT = ROOT / ".scratch" / "_media_pipeline_receipt.json"

# 作品 → 框架 kind / 标题 / 简述 / 已有产物按【框架工序名】挂载
# 工序名对照见 projects/README.md 的实测表（本地抽屉更细，框架更粗）
WORKS = [
    {
        "kind": "short_video", "title": "AI搬砖人", "label": "短视频",
        "brief": "把『加班到凌晨』从『我不够努力』重新解释成『我把力气用错了地方』；"
                 "46 秒，单一口播视角，收尾一句可转发物。",
        "assets": {  # 框架工序名 -> 盘上真文件
            "script": f"projects/short-video/01-script/{TODAY}-AI搬砖人/{TODAY}-short-video-AI搬砖人-01script.md",
            "storyboard": f"projects/short-video/02-storyboard/{TODAY}-AI搬砖人/{TODAY}-short-video-AI搬砖人-02storyboard.md",
        },
    },
    {
        "kind": "film", "title": "老屋", "label": "电影",
        "brief": "全片一个场、一个人、一句台词：保洁员林秀兰回老屋擦相框，"
                 "不往里走，擦完就走，门没关。",
        "assets": {
            "script": f"projects/film/01-screenplay/{TODAY}-老屋/{TODAY}-film-老屋-01screenplay.md",
            "shots": f"projects/film/02-storyboard/{TODAY}-老屋/{TODAY}-film-老屋-02storyboard.md",
        },
    },
    {
        "kind": "music", "title": "夜航", "label": "音乐",
        "brief": "一个人夜里开车，不为了到哪儿，只为了有一段没人找他的时间；"
                 "全篇第一人称不漂移。",
        "assets": {
            "lyrics": f"projects/music/01-lyrics/{TODAY}-夜航/{TODAY}-music-夜航-01lyrics.md",
        },
    },
]


def sha_file(rel: str) -> str:
    f = ROOT / rel
    if not f.is_file():
        return ""
    return hashlib.sha256(f.read_bytes()).hexdigest()


def call(op: str, **params) -> dict:
    r = run_task("media_pipeline", {"op": op, **params})
    res = r.get("result", r) if isinstance(r, dict) else {}
    if isinstance(res, dict) and isinstance(res.get("result"), dict):
        res = res["result"]
    return res if isinstance(res, dict) else {}


def main() -> int:
    print("=" * 78)
    print("接进 media_pipeline 编排层（只调纯函数 · 真 sha256）")
    print("=" * 78)

    status = call("status")
    print(f"  status: {status}")

    receipt: dict = {"generated_at": TODAY, "status": status, "works": []}

    for w in WORKS:
        print(f"\n── {w['label']}《{w['title']}》 ({w['kind']}) ──")

        plan = call("plan", kind=w["kind"], title=w["title"], brief=w["brief"])
        print(f"  plan   : ok={plan.get('ok')} stages={plan.get('stages')}")
        print(f"           publish_policy={plan.get('publish_policy')}")

        collab = call("collaborate", kind=w["kind"], objective=w["brief"][:40],
                      cycle_id=f"{TODAY}-{w['title']}")
        packets = collab.get("packets") or []
        print(f"  collab : ok={collab.get('ok')} 角色包 {len(packets)} 个")
        for p in packets:
            print(f"           {p['step_id']:42} {p['role']}")

        # 真 sha256：只挂**盘上真有**的工序，缺的如实不挂
        assets, missing = {}, []
        for stage, rel in w["assets"].items():
            h = sha_file(rel)
            if h:
                assets[stage] = {"ref": rel, "sha256": h, "bytes": (ROOT / rel).stat().st_size}
            else:
                missing.append(stage)
        expected = plan.get("stages") or []
        absent = [s for s in expected if s not in assets]
        print(f"  产物   : 已挂 {sorted(assets)}")
        print(f"           缺工序 {absent}")

        manifest = {
            "schema": "gbt-media-pipeline/v1", "kind": w["kind"],
            "label": w["label"], "title": w["title"], "brief": w["brief"],
            "assets": assets,
            # 三项证明一律 False —— 版权没核、安全没审、主人没批，就是 False，不代填
            "copyright_attested": False, "safety_reviewed": False, "owner_reviewed": False,
        }
        review = call("review", manifest=manifest, room_id=f"media-{TODAY}-{w['kind']}-dryrun")
        print(f"  review : {review.get('passed')}/{review.get('total')} 通过")
        print(f"           未过项: {review.get('blocked_reasons')}")
        print(f"           publish: {review.get('publish')}")

        receipt["works"].append({
            "kind": w["kind"], "label": w["label"], "title": w["title"],
            "plan": plan, "packets": packets, "review": review,
            "assets": {k: {"ref": v["ref"], "sha256": v["sha256"], "bytes": v["bytes"]}
                       for k, v in assets.items()},
            "stages_expected": expected, "stages_absent": absent,
        })

    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n回执 -> {OUT.relative_to(ROOT)}  ({OUT.stat().st_size} B)")

    # 交叉核对：回执里的 sha256 必须与盘上当前文件一致（防"存了个旧哈希"）
    print("\n=== 交叉核对：回执里的 sha256 与盘上现算是否一致 ===")
    bad = 0
    for w in receipt["works"]:
        for stage, meta in w["assets"].items():
            now = sha_file(meta["ref"])
            same = now == meta["sha256"]
            bad += (not same)
            print(f"  {'✔' if same else 'x'} {w['title']}/{stage}  {meta['sha256'][:16]}…")
    print(f"\n{'='*78}\n哈希核对 {'全部一致' if bad == 0 else f'{bad} 处不一致'}\n{'='*78}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
