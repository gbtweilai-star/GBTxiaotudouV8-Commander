# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 逐模块视觉就绪测试（Owner 2026-09-19：挨个测试，都得看得见）。

为什么单独做这一件：十二个模块里，**八个是"要看画面"的**（剧本/资产一致性/分镜/
图生视频/口型/审批门/虚拟摄影/合成审片），四个不看（编排、音乐三件）。
"看得见"必须是**跑出来的**，不是写在文档里的 —— 所以本工具对每个模块**各跑一次**，
用**真素材**（成片抽帧），逐条落读数。

纪律：
  · 模块没实现就如实写「未建」，**不许拿视觉能力通过冒充模块通过**；
  · 每个模块测的是"它将来要靠的那条视觉路径"，路径通不通与模块建没建**分开记**；
  · 输出逐条带 `读数` 字段（尺寸/主色/亮度/边缘密度/区域网格/差异），不写形容词。

用法：
    python -m gbt_allinone.tools.vision_probe            # 全跑
    python -m gbt_allinone.tools.vision_probe --json     # 纯 JSON
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

_FRAME_DIR = ROOT / ".scratch" / "vision_probe"
_SRC_VIDEO = ROOT / "outputs" / "drafts" / "GBT-potato-portrait-15s.mp4"


def _frames() -> dict:
    """从真成片里抽两帧（t=1s / t=8s）。抽不出来就如实返回空，不造假素材。"""
    _FRAME_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for tag, ts in (("a", "1"), ("b", "8")):
        dst = _FRAME_DIR / f"frame_{tag}.png"
        if dst.exists():
            out[tag] = dst
            continue
        if not _SRC_VIDEO.exists():
            continue
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", ts, "-i", str(_SRC_VIDEO),
                 "-frames:v", "1", str(dst)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=90, check=False)
        except Exception:  # noqa: BLE001
            continue
        if dst.exists():
            out[tag] = dst
    return out


def _analyze(path, grid=3):
    from gbt_allinone import vision_cap
    return vision_cap.run("analyze", image=str(path), grid=grid)


def _frame_diff(p1, p2):
    """两帧差异：复用她视觉总线自己的感知哈希（不自造第二套算法）。"""
    try:
        from gbt_allinone.tentacle import vision_bus as VB
        import base64
        b1 = base64.b64encode(Path(p1).read_bytes()).decode()
        b2 = base64.b64encode(Path(p2).read_bytes()).decode()
        h1, h2 = VB._ahash(b1), VB._ahash(b2)
        if isinstance(h1, str):
            d = sum(1 for x, y in zip(h1, h2) if x != y)
        else:
            d = bin(int(h1, 16) ^ int(h2, 16)).count("1")
        return {"ok": True, "hamming": d}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:120]}


# 十二个模块 × 它们各自要靠的视觉路径（模块存在与否单独记，不混判）
MODULES = [
    ("1 剧本理解引擎",        "读剧本/读分镜图",          "present", _analyze),
    ("2 资产一致性管理器",    "比对角色/场景是否同一",     "absent",  _frame_diff),
    ("3 分镜准备工作流",      "关键帧能否读出",           "absent",  _analyze),
    ("4 图生视频引擎",        "生成的帧是否可读",         "absent",  _analyze),
    ("5 配音与口型同步",      "看嘴部区域",              "absent",  _analyze),
    ("6 多Agent Pipeline编排", "不看画面（编排）",        "present", None),
    ("7 人工审批门禁",        "给主人看产出预览",         "partial", _analyze),
    ("8 虚拟摄影系统",        "看构图/九宫格",           "absent",  _analyze),
    ("9 音乐生成引擎",        "不看画面（音频）",         "absent",  None),
    ("10 音乐结构控制",       "不看画面（音频）",         "absent",  None),
    ("11 多任务类型引擎",     "不看画面（音频）",         "absent",  None),
    ("12 Remotion合成引擎",   "审片：抽帧看成品",         "partial", _analyze),
]


# 一致性红线（Owner 2026-09-19 提出 0.85）。口径必须先说死，否则就是假绿：
#   score = 1 - hamming/256，且**只对"同一主体跨镜"的成对素材计分**。
#   拿两个随手抽的帧算相似度**不是**一致性分数 —— 那是画面差异，不是同一个人/同一个景。
CONSISTENCY_THRESHOLD = 0.85
_PAIRWISE_BITS = 256.0


def consistency_gate(pair_score=None):
    """一致性门：算得出来才算分，算不出来就如实判**未测**，不按绿算（《反假绿律》）。

    现在算不出来，原因两条（读数）：①「资产一致性管理器」模块未建，没有主体标注；
    ② 手上只有一条成片的两个任意帧，**不是同一主体跨镜**的成对素材。
    ⇒ 状态 UNK（未测，0 分），不假装能击杀。
    """
    if pair_score is None:
        return {"threshold": CONSISTENCY_THRESHOLD, "status": "UNK",
                "why": "模块未挂载 + 无同主体跨镜成对素材 ⇒ 算不出分数",
                "would_kill_when": "score < %.2f 触发击杀重做" % CONSISTENCY_THRESHOLD,
                "redo_wired": False,
                "note": "击杀判定已定义，但『重做派单』尚未接线 —— 如实报，不假装能自动重做。"}
    kill = pair_score < CONSISTENCY_THRESHOLD
    return {"threshold": CONSISTENCY_THRESHOLD, "status": "kill" if kill else "pass",
            "score": round(pair_score, 4), "redo_wired": False}


def _dom_hex(top_colors):
    """把她的 `top_colors[0]` 转成 hex，只为**好读**——不新增颜色算法、不建第二份真相。

    2026-09-19 自纠：我先前说「dominant_color 是 None ⇒ 她视觉缺主色」是**错的**。
    真相是她的 `vision_cap.analyze()` 一直返回 `top_colors`（前 5 主色 + 占比，量化步长 32），
    是**我的探针读了一个不存在的键名**。缺的是我的读数，不是她的眼睛。
    """
    try:
        rgb = (top_colors or [{}])[0].get("rgb") or []
        if len(rgb) != 3:
            return None
        return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:  # noqa: BLE001
        return None


def probe():
    fr = _frames()
    have = sorted(fr)
    rows = []
    for name, need, impl, fn in MODULES:
        row = {"module": name, "vision_need": need, "module_impl": impl,
               "vision_path": "无视觉需求" if fn is None else fn.__name__}
        if fn is None:
            row["status"] = "n/a"
            row["读数"] = "该模块不看画面"
            rows.append(row)
            continue
        if not have:
            row["status"] = "素材缺失"
            row["读数"] = "抽帧失败：无真素材可测（不造假素材）"
            rows.append(row)
            continue
        try:
            if fn is _frame_diff:
                if len(have) < 2:
                    row["status"] = "素材不足"
                    row["读数"] = f"只抽到 {len(have)} 帧"
                else:
                    r = _frame_diff(fr[have[0]], fr[have[1]])
                    row["status"] = "ok" if r.get("ok") else "fail"
                    row["读数"] = r
            else:
                r = _analyze(fr[have[0]])
                ok = bool(r.get("ok"))
                row["status"] = "ok" if ok else "fail"
                # 读她**真实存在**的键：top_colors（前 5 主色 + 占比）。
                out = {k: r.get(k) for k in
                       ("ok", "size", "brightness", "contrast", "edge_density", "grid")}
                out["top_colors"] = r.get("top_colors")
                out["dominant_hex"] = _dom_hex(r.get("top_colors"))
                row["读数"] = out if ok else r
        except Exception as exc:  # noqa: BLE001
            row["status"] = "fail"
            row["读数"] = f"{type(exc).__name__}: {exc}"[:160]
        rows.append(row)

    ok = sum(1 for r in rows if r["status"] == "ok")
    na = sum(1 for r in rows if r["status"] == "n/a")
    return {"frames": [str(p) for p in fr.values()],
            "source_video": str(_SRC_VIDEO), "source_exists": _SRC_VIDEO.exists(),
            "modules": rows, "vision_ok": ok, "no_vision_needed": na,
            "total": len(rows),
            # 两帧相隔 7 秒，汉明距只能说明"画面变了"，**不能**当一致性分数用。
            "pairwise_hamming_note": "仅作『画面有无变化』读数；一致性分数需同主体跨镜素材",
            "consistency_gate": consistency_gate(),
            "note": ("模块未建 ≠ 视觉路径不通：本表把『看得见的路径』与『模块建没建』分开记，"
                     "不许互相冒充。")}


def main(argv=None):
    r = probe()
    if "--json" in (argv or sys.argv):
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print("素材：%s（存在=%s）" % (r["source_video"], r["source_exists"]))
    print("抽帧：%s" % (r["frames"] or "无"))
    print("-" * 78)
    for m in r["modules"]:
        print("%-22s %-8s %-14s %s" % (m["module"], m["module_impl"],
                                       m["status"], str(m["读数"])[:150]))
    print("-" * 78)
    print("看得见 %d 条 · 无视觉需求 %d 条 · 共 %d 条" % (r["vision_ok"], r["no_vision_needed"], r["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
