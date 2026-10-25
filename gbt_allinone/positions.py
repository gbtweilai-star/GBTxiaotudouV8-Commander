#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固定职位表 —— 亿万触手里的"编制"，唯一定义处。

Owner 2026-09-22：
  「你有亿万触手，职位必须是固定的。另外的你想怎么设都可以，
    唯独固定职位的必须固定。」

═══ 这条约束是什么意思（我的理解，可被纠正）═══
  · **亿万触手** = 可无限派生。它们**不在这张表里**，随任务起、随任务灭。
  · **固定职位** = 编制。**有名字、有职责、有归属、不许漂移。**
  · 分界：**表内的不许改；表外的随便建。**
    —— 没有这条分界，"亿万触手"会退化成"一堆没有身份的一次性进程"。

═══ 为什么职位要"固定"（不是形式主义）═══
  ① **可追责** —— 出了事要知道是哪个职位干的
  ② **可审计** —— 同一个职位昨天的活与今天的活能对比
  ③ **可长肌肉** —— 职位固定，能力才能在上面累积；职位老变，每次都从零开始
  ④ **可派单** —— 固定职位才能被"委派职责"，动态触手只能被"指派任务"

═══ 与既有模块的关系 ═══
  · `caps_registry` 管**能力**（147 项，能调什么）
  · **本表管职位**（谁负责哪一块，该块该有什么水平）
  · 一个职位**拥有若干能力**；一个能力**可被多个职位共用**
  · 本表**不复制** caps_registry —— 只引用能力名，真值仍在注册表

═══ 铁律 ═══
  · 表内的 `id` **一经登记不许改**（改名 = 断掉历史，等于新职位）
  · 表内职位**不许删**，只许标 `retired: True` 并写明原因
  · `required_caps` 里引用的能力**必须真在 caps_registry 里** —— 否则报红
  · 本模块**只读**：不写盘、不出网、不起进程
"""
from __future__ import annotations

import sys
from pathlib import Path

# ═══ 固定职位表 ═══════════════════════════════════════════════════
# 字段口径：
#   id           唯一标识，**登记后不许改**
#   cn           中文名（可读，可改）
#   duty         这个职位负责什么（一句话，判断"该不该派给它"用这句）
#   domain       归属域（对齐 caps_registry 的 domain）
#   required_caps 该职位**必须**能调的能力（校验它们真在册）
#   min_level    **应该有**的水平：full=能执行 / read=只读判 / gate=闸门
#   current_level **现在有**的水平；缺省 = min_level
#                ★ 这两栏一起才是 Owner「顶级实力不是壳子」那条的落点：
#                  **不许把"应该有"写成"现在有"。** 差多少，gap 栏如实记。
#   gap          现在缺什么（一句话）。**有 gap 不算错，瞒着才算。**
#   fixed        恒为 True —— 本表内一律固定；动态触手不登记在此
#   retired      退役标记；退役必须写 note
POSITIONS = [
    # ── 感知与在场 ──────────────────────────────────────────────
    {"id": "eye", "cn": "眼睛", "domain": "tentacle", "min_level": "full",
     "duty": "看屏幕、看窗口、看现场 —— 一切「现在是什么样」的读数来源",
     "required_caps": ["tentacle", "vision"]},
    {"id": "hand", "cn": "双手", "domain": "tentacle", "min_level": "full",
     "duty": "点击、输入、拖动、按键 —— 一切「让它变成什么样」的动作执行",
     "required_caps": ["tentacle", "desktop_commander"]},
    {"id": "sense_host", "cn": "本体感知", "domain": "device", "min_level": "full",
     "duty": "报本体（这台电脑）的 CPU/内存/磁盘/进程/网络 —— 身体舒服不舒服",
     "required_caps": ["health", "selfscan"]},

    # ── 认知与纪律 ──────────────────────────────────────────────
    {"id": "cognition", "cn": "认知包", "domain": "system", "min_level": "gate",
     "duty": "每次触手调用前注入任务上下文/角色边界/自检三问/五条红线",
     "required_caps": ["tentacle_cognition"]},
    {"id": "meta", "cn": "元认知", "domain": "mind", "min_level": "read",
     "duty": "自省→查内部→查外部→问主人→沉淀；不许自省变自责，不许硬猜",
     "required_caps": ["meta_cognition"]},
    {"id": "observer", "cn": "观察者", "domain": "mind", "min_level": "read",
     "duty": "审计别人 —— 且自己也被审计（同一方不许既扫又报）",
     "required_caps": ["observer_anchor"]},

    # ── 记忆与情报 ──────────────────────────────────────────────
    {"id": "memory", "cn": "记忆", "domain": "data", "min_level": "full",
     "duty": "记住发生过什么、能被检索回来 —— 不是「存了就算」",
     "required_caps": ["brain_vault", "life"]},
    {"id": "intel_short", "cn": "短视频情报", "domain": "recon", "min_level": "read",
     "duty": "盯短视频方向的行业动向；**禁区清单优先于流量趋势**",
     "required_caps": ["video_intel"]},
    {"id": "intel_music", "cn": "音乐情报", "domain": "recon", "min_level": "read",
     "duty": "盯音乐方向的合规红线/过审/流量/画像/竞品",
     "required_caps": ["music_intel"]},
    {"id": "intel_film", "cn": "影视情报", "domain": "recon", "min_level": "read",
     "duty": "盯影视方向的六维覆盖；情报是输入不是指令",
     "required_caps": ["film_intel"]},

    # ── 创作三方向 ──────────────────────────────────────────────
    {"id": "make_short", "cn": "短视频创作", "domain": "creation", "min_level": "full",
     "duty": "短视频从剧本到成片的产出链",
     # 闸查出 libtv_workflow 自标「只读骨架」⇒ 现在最多 read。
     # **不改成 read 糊过去**（那等于承认短视频做不了），也不留 full 假装。
     # 如实记 gap：应该有 full，现在只有 read。
     "gap": "libtv_workflow 仍是只读骨架，生成端未接；分镜/剧本段已可跑",
     "required_caps": ["media_pipeline", "libtv_workflow"]},
    {"id": "make_music", "cn": "音乐创作", "domain": "creation", "min_level": "full",
     "duty": "音乐从词曲到成品的产出链",
     "required_caps": ["media_pipeline", "voice"]},
    {"id": "make_film", "cn": "电影创作", "domain": "creation", "min_level": "full",
     "duty": "电影从剧本到成片的产出链",
     "required_caps": ["media_pipeline"]},
    {"id": "design", "cn": "设计", "domain": "creation", "min_level": "read",
     # 2026-09-22 由 full 降为 read：闸查出 code_art / scene_anchor 自标「只读骨架」，
     # 而 full 意味着"能执行"。**不许把壳子标成满配** —— 要么长肌肉，要么如实降级。
     "duty": "视觉/界面/物料的设计方案与审美把关（**出方案不出结论**，好看只能人判）",
     "required_caps": ["code_art", "scene_anchor"]},
    {"id": "emotion", "cn": "情感投射", "domain": "creation", "min_level": "read",
     "duty": "叙事四问 → 投射细节 → 四项校验；『身临其境』只有人能判",
     "required_caps": ["emotion_projection"]},

    # ── 工程与治理 ──────────────────────────────────────────────
    {"id": "code", "cn": "编程", "domain": "llm", "min_level": "full",
     "duty": "写代码、改代码、修 bug —— 按顶级工程师那十条做",
     "required_caps": ["codex_chat", "codex_turn_send"]},
    {"id": "audit_caps", "cn": "覆盖审计", "domain": "system", "min_level": "read",
     "duty": "八短板↔八触手组 + 覆盖率读数 + 死角登记 + 五条红线",
     "required_caps": ["coverage_auditor"]},
    {"id": "gate_vis", "cn": "门可见性", "domain": "framework", "min_level": "read",
     "duty": "回答「门看得见什么、看不见什么」—— 三态：已纳入/显式不纳入/未决定",
     "required_caps": ["gate_visibility"]},
    {"id": "scan_code", "cn": "逐行穷尽扫描", "domain": "system", "min_level": "full",
     "duty": "走遍每一个候选文件、每一行；覆盖率必须闭合（扫过+失败==候选）",
     "required_caps": ["cross_scan", "inventory"]},
    {"id": "scan_host", "cn": "主机安全", "domain": "security", "min_level": "full",
     "duty": "反病毒在位/持久化入口/进程签名/网络连接/可疑位置/关联 —— 六层只读",
     "required_caps": ["selfscan"]},
    {"id": "reclaim", "cn": "回收", "domain": "system", "min_level": "full",
     "duty": "找垃圾、量盲区、搬进垃圾桶（**只搬不删**，清不清由主人定）",
     "required_caps": ["file_hygiene"]},
    {"id": "trace", "cn": "留痕", "domain": "system", "min_level": "full",
     "duty": "每一步逐字记：命令/退出码/输出头尾/sha256 —— 让人能复算",
     "required_caps": ["audit_query"]},

    # ── 长程与调度 ──────────────────────────────────────────────
    {"id": "longrun", "cn": "长程调度", "domain": "longrun", "min_level": "full",
     "duty": "把长活拆成步、按节拍推进、卡住就上报 —— 不许无限重试",
     "required_caps": ["long_run_supervisor"]},
    {"id": "orchestrate", "cn": "编排", "domain": "engine", "min_level": "full",
     "duty": "按 DAG 派单；**只自动跑只读能力**，写动作一律回 run_task 过门",
     "required_caps": ["orchestration_kernel"]},
    {"id": "evolve", "cn": "进化", "domain": "devour", "min_level": "full",
     "duty": "吞噬→反思→消化→重组→创新；产物必须是真能力，不是恒返回桩",
     "required_caps": ["devour_pulse"]},
]

DYNAMIC_NOTE = (
    "**本表只管固定职位。** 亿万触手是动态的 —— 随任务起、随任务灭、随便设，"
    "**不登记在此**，也不受本表的改名/退役约束。"
    "分界：**表内的不许改；表外的随便建。**"
)


def audit() -> dict:
    """校验表内每一条：能力真在册吗？标 full 的职位，其能力是真实现还是只读骨架？"""
    import importlib
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    CR = importlib.import_module("gbt_allinone.caps_registry")
    B = getattr(CR, "BENIGN_CAPS", {}) or {}
    import re
    STUB = re.compile(r"骨架|not_implemented|未实现|占位")

    issues, rows, gaps = [], [], []
    for p in POSITIONS:
        missing = [c for c in p["required_caps"] if c not in B]
        stubs = [c for c in p["required_caps"]
                 if c in B and STUB.search(str((B[c] or {}).get("desc") or ""))]
        want = p.get("min_level")
        have = p.get("current_level", want)
        # 实测水平：依赖里有骨架 ⇒ 现在最多是 read
        actual = "read" if stubs else have
        level_gap = (want == "full" and actual != "full")
        rows.append({"id": p["id"], "cn": p["cn"], "missing_caps": missing,
                     "stub_caps": stubs, "min_level": want, "actual_level": actual,
                     "gap": p.get("gap", ""), "level_gap": bool(level_gap)})
        if missing:
            issues.append(f"[{p['id']}] 引用了不在册的能力: {missing}")
        if level_gap:
            # **缺口不是错** —— 如实记，不阻断。瞒着才是错。
            gaps.append(f"[{p['id']}] {p['cn']}：应该有 {want}，现在只有 {actual}"
                        f"（依赖 {stubs} 是骨架）"
                        + (f" —— {p['gap']}" if p.get("gap") else ""))
    ids = [p["id"] for p in POSITIONS]
    dup = [i for i in set(ids) if ids.count(i) > 1]
    if dup:
        issues.append(f"职位 id 重复: {dup}")
    return {"positions": len(POSITIONS), "rows": rows, "issues": issues,
            "gaps": gaps, "ok": not issues, "dynamic_note": DYNAMIC_NOTE}


def main() -> int:
    r = audit()
    print("=" * 78)
    print(f"固定职位表 · {r['positions']} 个编制")
    print("=" * 78)
    for p in POSITIONS:
        print(f"  {p['id']:14} {p['cn']:8} {p['min_level']:5} {p['duty'][:52]}")
    a = r
    print()
    print("─" * 78)
    print(f"  校验: {'✔ 全过' if a['ok'] else '✘ ' + str(len(a['issues'])) + ' 处问题'}")
    for i in a["issues"]:
        print(f"     {i}")
    if a.get("gaps"):
        print(f"  ── 能力缺口 {len(a['gaps'])} 处（**不是错，是还没长出来**）:")
        for g in a["gaps"]:
            print(f"     {g}")
    print("─" * 78)
    print("  " + r["dynamic_note"])
    return 0 if a["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
