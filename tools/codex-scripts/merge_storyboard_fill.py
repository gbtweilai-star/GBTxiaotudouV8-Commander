# -*- coding: utf-8 -*-
"""把填写页导出的 JSON 合并成**正式分镜件**（HITL#1 的落地端）。

闭环：填写页导出 → 落 `projects/_inbox/` → 本脚本校验并写成正式件。

纪律：
 · **校验不全就拒绝写**。缺项逐条列出，不许"部分合并"糊过去 ——
   半份分镜比没有更坏：它看起来像填完了。
 · **不覆盖既有产物**。同日同名按 README 加 `-vN`，旧件归档进同目录 `_old/`。
 · 署名与来源逐件带上，注明"由 HITL#1 填写页产出、非作者代填"。

用法：
  py -3.14 tools/codex-scripts/merge_storyboard_fill.py            # 预演（默认）
  py -3.14 tools/codex-scripts/merge_storyboard_fill.py --apply
  py -3.14 tools/codex-scripts/merge_storyboard_fill.py --in <别的json> --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gbt_allinone import run_task  # noqa: E402

TODAY = "20260921"
SIGN = "> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"

REQUIRED_FIELDS = ("render", "eyeline", "depth", "reason")

# 方向 -> (目标件路径, 工序标记, 是否要求 share, 是否有分镜稿)
# 音乐没有分镜件：它的 HITL 项（三项证明 + §3 生成前闸）**追加**到歌词件末尾，
# 按 README 的 `[-vN]` 规矩升版，原正文一字不动 —— 既不覆盖，也不破坏既有产物。
TARGETS = {
    "short-video": (f"projects/short-video/02-storyboard/{TODAY}-AI搬砖人/"
                    f"{TODAY}-short-video-AI搬砖人-02storyboard.md", "short-video", True, True),
    "film": (f"projects/film/02-storyboard/{TODAY}-老屋/"
             f"{TODAY}-film-老屋-02storyboard.md", "film", False, True),
    "music": (f"projects/music/01-lyrics/{TODAY}-夜航/"
              f"{TODAY}-music-夜航-01lyrics.md", "music", False, False),
}

# 音乐必填（契约 §3 四项 + 三项证明）。**看契约要什么，不看作者爱填什么。**
MUSIC_REQUIRED = {
    "att_copyright": "版权已核（素材授权可追溯）",
    "att_safety": "安全已审",
    "att_owner": "主人已批（HITL#1 签署）",
    "gate_source": "来源已核验（§3-1）",
    "gate_flag": "显式标志位已设（§3-2）",
    "gate_style_prompt": "风格提示词完整（§3-3）",
    "gate_artist_clear": "艺人名已清（§3-4）",
}

TIMED_RE = re.compile(r"## 一、分镜稿输入.*?```\n(.*?)```", re.S)


def parse_timed_strokes(board_text: str) -> dict:
    m = TIMED_RE.search(board_text)
    if not m:
        return {}
    r = run_task("drama", {"op": "parse_timed", "text": m.group(1).strip()})
    res = r.get("result", r) if isinstance(r, dict) else {}
    if isinstance(res, dict) and isinstance(res.get("result"), dict):
        res = res["result"]
    return res if isinstance(res, dict) else {}


def validate(direction: str, work: dict, need_share: bool) -> tuple[list[str], dict]:
    """逐格校验。返回 (缺项清单, 期望镜号集合)。

    无分镜件的方向（音乐）走另一套判据：核**契约 §3 的必填项**，不核镜头格。
    """
    missing: list[str] = []
    board_rel, _tag, _share, has_board = TARGETS[direction]

    if not has_board:
        g = work.get("globals") or {}
        for key, label in MUSIC_REQUIRED.items():
            if not str(g.get(key, "")).strip():
                missing.append(f"必填 · {label}")
        return missing, set()

    board = (ROOT / board_rel)
    if not board.is_file():
        return [f"分镜件不存在：{board_rel}"], {}
    pr = parse_timed_strokes(board.read_text(encoding="utf-8"))
    expected = {str(s.get("idx")) for s in (pr.get("shots") or [])}
    if not expected:
        return [f"分镜件里切不出镜头：{board_rel}"], {}

    g = work.get("globals") or {}
    if not str(g.get("style", "")).strip():
        missing.append("全局 · 全片预设风格（契约 §1：没有风格的分镜板一律打回）")
    if need_share:
        if not str(g.get("share_shot", "")).strip():
            missing.append("全局 · 收尾镜 shot.share 挂到第几镜（契约 §5：缺了分镜板打回）")
        elif str(g["share_shot"]).strip() not in expected:
            missing.append(f"全局 · shot.share 挂的镜号 {g['share_shot']} 不在本件镜号内 {sorted(expected, key=int)}")

    shots = work.get("shots") or {}
    for idx in sorted(expected, key=int):
        s = shots.get(idx)
        if not s:
            missing.append(f"第 {idx} 镜：整镜四项全空")
            continue
        for f in REQUIRED_FIELDS:
            if not str(s.get(f, "")).strip():
                missing.append(f"第 {idx} 镜：{f} 未填")
    # 理由不许复制：把重复的理由点出来（契约 §2.2「复制别人的理由 = 失败」）
    reasons: dict[str, list[str]] = {}
    for idx, s in shots.items():
        r = str(s.get("reason", "")).strip()
        if r:
            reasons.setdefault(r, []).append(idx)
    for r, idxs in reasons.items():
        if len(idxs) > 1:
            missing.append(f"理由被复制（契约 §2.2 明写复制=失败）：镜 {'/'.join(sorted(idxs, key=int))} 用了同一句")
    return missing, expected


def render_appended(src: Path, work: dict) -> str:
    """无分镜件的方向（音乐）：**在原件末尾追加** HITL#1 段，原正文一字不动。

    为什么用追加而不是重写：本脚本不持有歌词正文，重写就等于用一份残缺内容
    覆盖原稿 —— 那是毁产物。追加是唯一既落盘又不破坏的写法。
    """
    base_text = src.read_text(encoding="utf-8").rstrip() + "\n"
    g = work.get("globals") or {}
    rows = "\n".join(f"| {label} | {g.get(key, '')} |" for key, label in MUSIC_REQUIRED.items())
    extra = [(k, v) for k, v in g.items() if k not in MUSIC_REQUIRED and str(v).strip()]
    extra_md = ""
    if extra:
        extra_md = ("\n其余填写项（契约未强制，一并留档）：\n\n| 键 | 取值 |\n|---|---|\n"
                    + "\n".join(f"| {k} | {v} |" for k, v in extra) + "\n")

    section = f"""

---

## 附 · HITL#1 必填（由填写页定，非作者代填）

> 本节由 `merge_storyboard_fill.py` **追加**，**原歌词正文未改动**。
> 填写页：`projects/_shared/templates/{TODAY}-三方向-HITL1-分镜契约填写页.html`

契约 §3 生成前闸四项 + 三项证明：

| 项 | 取值 |
|---|---|
{rows}
{extra_md}
- 本件**尚未经过 HITL#1 签署**，仅为填写结果的落盘。
- 音频 QC（契约 §4 七项）仍为**未判** —— 需要真音频才能机器判，无音频不写预估值。

{SIGN}
"""
    return base_text + section


def render_filled(direction: str, work: dict, expected: set[str], pr: dict) -> str:
    g = work.get("globals") or {}
    shots = work.get("shots") or {}
    label = "短视频" if direction == "short-video" else "电影"
    name = work.get("name") or ("AI搬砖人" if direction == "short-video" else "老屋")
    shot_meta = {str(s.get("idx")): s for s in (pr.get("shots") or [])}

    rows = []
    for idx in sorted(expected, key=int):
        s = shots.get(idx, {})
        m = shot_meta.get(idx, {})
        rows.append(
            f"| {idx} | {m.get('t0')}–{m.get('t1')}s ({m.get('dur')}s) | {m.get('title', '')} | "
            f"{s.get('render', '')} | {s.get('eyeline', '')} | {s.get('depth', '')} | {s.get('reason', '')} |")

    share = ""
    if str(g.get("share_shot", "")).strip():
        text = str(g.get("share_text", "")).strip() or "（沿用源稿可转发物原文）"
        share = (f"\n## 五、可转发物落点（契约 §5）\n\n"
                 f"- `shot.share` 挂在第 **{g['share_shot']}** 镜\n"
                 f"- 文本：{text}\n")

    # 其余必填（三项证明 + 方向专属）**必须一并落盘**。
    # 上一版只写 style / share，于是填写页里填的三项证明与 §3 生成前闸
    # 在合并时被静默丢弃 —— 填了却不见了，比没填更坏。
    OTHER_LABEL = {
        "att_copyright": "版权已核（素材授权可追溯）",
        "att_safety": "安全已审",
        "att_owner": "主人已批（HITL#1 分镜审批签署）",
        "gate_source": "来源已核验（§3-1）",
        "gate_flag": "显式标志位已设（§3-2）",
        "gate_style_prompt": "风格提示词完整（§3-3）",
        "gate_artist_clear": "艺人名已清（§3-4）",
        "line_shot": "唯一台词「妈回来了」挂到第几镜",
        "line_to": "这句是对谁说的",
        "alt_scene": "备选场「院子空镜 6s」是否采纳",
        "hook_video": "开场是否用付费视频镜（hook_video）",
    }
    skip = {"style", "share_shot", "share_text"}
    other = [(OTHER_LABEL.get(k, k), v) for k, v in g.items() if k not in skip and str(v).strip()]
    other_md = ""
    if other:
        other_md = ("\n## 六、HITL#1 其余必填（由填写页定，非作者代填）\n\n"
                    "| 项 | 取值 |\n|---|---|\n"
                    + "\n".join(f"| {k} | {v} |" for k, v in other) + "\n")

    return f"""# {label} · 《{name}》· 02 分镜（契约已填 · HITL#1 产物）

{SIGN}

> **本件的 `render` / `eyeline` / `depth` / 理由由 HITL#1 填写页产出，非作者代填。**
> 契约 §1 规定这些值必须「先读旁白，再决定」且「复制别人的理由 = 失败」——
> 作者不代填正是为了守这两条。填写页：`projects/_shared/templates/{TODAY}-三方向-HITL1-分镜契约填写页.html`

## 一、全片预设风格（契约 §1：没有风格的分镜板一律打回）

> {g.get('style', '')}

## 二、镜头三契约（逐镜 · 已填）

| 镜 | 时长 | 画面 | `render` | `eyeline` | `depth` | 为什么这么选 |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}
{share}{other_md}
## 七、来源

- 镜头切分：`drama.parse_timed`（离线 · 规则式）
- 取值来源：HITL#1 填写页导出件
- 本件**尚未经过 HITL#1 签署**，仅为填写结果的落盘
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", default=str(ROOT / "projects" / "_inbox" / "hitl1-storyboard-fill.json"))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    src = Path(a.src)
    print("=" * 78)
    print(f"HITL#1 填写结果合并 · {'APPLY' if a.apply else 'DRY-RUN'}")
    print("=" * 78)
    if not src.is_file():
        print(f"  找不到填写结果：{src}")
        print("  （先在填写页填完并点「导出填好的分镜」，把 JSON 落进 projects/_inbox/）")
        return 2
    data = json.loads(src.read_text(encoding="utf-8"))
    if data.get("schema") != "gbt-hitl1-storyboard-fill/v1":
        print(f"  schema 不认：{data.get('schema')!r}")
        return 2

    total_missing = 0
    plan = []
    no_target = []
    for direction, work in (data.get("works") or {}).items():
        if direction not in TARGETS:
            no_target.append((direction, work.get("name"), len(work.get("globals") or {})))
            continue
        rel, tag, need_share, has_board = TARGETS[direction]
        missing, expected = validate(direction, work, need_share)
        filled = len((work.get("shots") or {}))
        done = f"{filled}/{len(expected)} 镜" if has_board else f"{len(work.get('globals') or {})} 项全局"
        print(f"\n── {work.get('name')} ({direction}) —— 填了 {done}")
        if missing:
            total_missing += len(missing)
            print(f"   拒绝写入：{len(missing)} 项缺")
            for x in missing[:12]:
                print(f"     · {x}")
            if len(missing) > 12:
                print(f"     … 另 {len(missing)-12} 项")
            continue
        board = ROOT / rel
        if has_board:
            pr = parse_timed_strokes(board.read_text(encoding="utf-8"))
            text = render_filled(direction, work, expected, pr)
        else:
            text = render_appended(board, work)
        # 版本：同日同名加 -vN，不覆盖
        base = board.with_suffix("")
        n = 2
        while (base.parent / f"{base.name}-v{n}.md").exists():
            n += 1
        dest = base.parent / f"{base.name}-v{n}.md"
        print(f"   校验通过 → 将写 {dest.relative_to(ROOT)}（旧件保留，不覆盖）")
        plan.append((board, dest, text))
        if a.apply:
            dest.write_text(text, encoding="utf-8")
            back = dest.read_text(encoding="utf-8")
            print(f"   ✔ 回读 {len(back)} 字 · 署名{'在' if '本署名不可删除' in back else '缺!'}")

    print(f"\n{'='*78}")
    for d, n, k in no_target:
        print(f"  注意：{n} ({d}) 填了 {k} 项，但**本脚本还没有它的合并目标** ——")
        print("        音乐不走分镜件，它的 §3 生成前闸要落到哪一件，尚未定夺。")
        print("        这不是「已处理」，是「没处理」，填的内容目前只在导出件里。")
    if total_missing:
        print(f"有 {total_missing} 项缺，拒绝部分合并 —— 半份分镜比没有更坏：它看起来像填完了。")
        return 1
    if not plan:
        print("没有可写入的目标。")
        return 1
    print(f"{'已写' if a.apply else '将写'} {len(plan)} 件。" + ("" if a.apply else " 加 --apply 落盘。"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
