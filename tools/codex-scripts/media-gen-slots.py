# -*- coding: utf-8 -*-
"""三套链的**生成步插座位**（第 46 轮）—— **规格件，不是接线件**

════════════════════════════════════════════════════════════════════════
它是什么 / 不是什么（先写死，免得后人把它当"已经接上了"）
════════════════════════════════════════════════════════════════════════
是什么：把三个**生成式步**的**步定义 + 判据 + 进门条件**写成可机检的规格，
        并**对照 `policy.py` 现读**核出它们各自真正要的作用域。
不是什么：**它们还没有插进 `media_run.CHAINS`**（本件里 `WIRED = False` 明写）。
        三件都要主人点头 —— `audio_output` / 外部密钥+花钱 / `privacy_read`；
        **AI 无权自己给自己发授权**（本仓红线），所以这里只做插座、不通电。

为什么要先做插座：主人问过"要不要配音/出图/视觉复核"。无论答不答应，
**步的接口与判据都该先定清楚** —— 定了才知道"通电"时到底要改哪几行；
也才知道缺的是**授权**、是**密钥**、还是**代码**。

缺口口径（第 45 轮校正过的准确版）：
  · 链里**有**实现器步，且真跑（实测 film `ran 4`：shots/sound/edit/export）——
    但它们是**确定性合成步**（ffmpeg/audio_mix 那一类）：**装配**内容，不**创作**内容。
  · 缺的是 ① **生成式步**（大模型编剧 / TTS 配音 / 出图分镜）② **视觉复核步**
    （现有判据都判**输入口**，没有判**产物画面**的）。

用法：`py -3.14 tools/codex-scripts/media-gen-slots.py`（0 = 规格自洽且与 policy 一致）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 🔴 本仓老坑（这次又踩）：GBK 控制台下 `⚠️` 这类字符会直接 UnicodeEncodeError 把脚本弄崩，
#   而"崩了"看起来像"这个工具坏了"。出口一律 utf-8 + errors=replace。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "gbt_allinone" / "security" / "policy.py"
REGISTRY = ROOT / "gbt_allinone" / "caps_registry.py"

# 🔴 **本件只到规格为止**：这三个步没有进 CHAINS。改了这里不等于链子多了三步。
WIRED = False

SLOTS = [
    {
        "step": "narration",              # 拟插位置：film / short_video 的 script 之后
        "into": ("film", "short_video"),
        "after": "script",
        "cap": "voice",
        "op": "tts",                      # 本步实际会用哪个 op —— **判据要按 op 说话**
        "kind": "生成式步（配音）",
        "produces": "旁白音轨（wav）",
        "judge": "产物非空 + 时长 ≥ 旁白字数下限 + 采样率/声道可读（ffprobe 现读）",
        # policy 的 voice 分支：`if p.get("out"): add("filesystem_write")`
        #                     `if (op or "tts") in ("tts","speak",None): add("audio_output")`
        # ⇒ 本步用 tts 且不要求 out ⇒ 一定会加 audio_output；filesystem_write **只在 out 时**加。
        "expect_scopes": ("audio_output",),
        "expect_note": "用 tts ⇒ audio_output 必加；filesystem_write 仅在 payload 带 out 时加（本步不带）",
        "gate_extra": "无（本机 SAPI，不出网、不花钱）",
    },
    {
        "step": "frames",                 # 拟插位置：storyboard 之后、shots 之前
        "into": ("film", "short_video"),
        "after": "storyboard",
        "cap": "a1art_skill",
        "op": "GENERATE",
        "kind": "生成式步（出图分镜）",
        "produces": "逐镜画面（png/jpg）",
        "judge": "张数 == 分镜镜数 + 每张可解码 + **与分镜一致性**（由视觉复核那一步判）",
        "expect_scopes": None,            # policy 里**没有这个 kind** ⇒ 闸不在作用域
        "expect_note": "policy.py 里**零命中**：闸在**密钥与预算**（DPAPI/密钥池 + 计费确认），不在作用域",
        "gate_extra": "外部密钥 + 花钱；结果必须落盘",
    },
    {
        "step": "visual_check",           # 拟插位置：edit 之后（判**产物**，不判输入）
        "into": ("film", "short_video"),
        "after": "edit",
        "cap": "vision",
        "op": "analyze_file",             # ← 关键：读**产物文件**，不是读屏/摄像头
        "kind": "视觉复核步（判**产物**）",
        "produces": "逐镜判定（对/不对 + 理由）",
        "judge": "把**已有判据**的用法反过来：判据判输入口，这一步判**产物画面**",
        # policy 的 vision 分支：`if op not in ("status","analyze_file"): add("privacy_read")`
        # ⇒ 用 analyze_file **免卡** —— 这条真身纠正了我第 45 轮的声明（当时写 privacy_read）。
        "expect_scopes": (),
        "expect_note": "用 analyze_file ⇒ **免卡**（privacy_read 只在读屏/摄像头时加）—— 第 47 轮读真身后纠正",
        "gate_extra": "本步只读产物文件；不读屏、不开摄像头",
    },
]


# 分支体：从 `kind == "X":` 起，到**下一个 `(el)if kind ==`** 处刹住（前瞻不带 `\n`，见下）。
_BRANCH_NOTE = True
_BRANCH = (r'kind\s*==\s*["\']%s["\']\s*:\n'
           r'((?:(?![ \t]*(?:el)?if\s+kind\s*==)[ \t]+.*\n)+)')
# 🔴 前瞻里**不能带 `\n`**（第 49 轮踩的）：循环每轮已经把行尾的 `\n` 吃掉了，
#    下一轮尝试的起点在**行首**，此时再去找 `\n[ \t]*elif` 永远找不到 ⇒ 从不刹住，
#    于是 `voice` 的并集把后面 `audit_query`/`notion`/`codex_chat` 的 add() 全吸了进来。
#    并集一宽，判据就退化成"什么都能过"。正确写法：前瞻只看**当前位置**（行首）起的内容。


def policy_scopes(kind: str) -> tuple[str, ...] | None:
    """从 `policy.py` 现读某个 kind 会加哪些作用域（**不靠记忆**）。

    🔴 第 47 轮读真身后的关键认识：`policy.py` 里作用域是**在分支体里按 op 条件 add() 的**，
    不是一张静态表。所以"这个能力位要什么作用域"这个问法本身就不准确 ——
    准确问法是「**这个 kind 的这个 op** 要什么作用域」。证据（原码）：
        elif kind == "vision":
            if op not in ("status", "analyze_file"): add("privacy_read")
        elif kind == "voice":
            if p.get("out"): add("filesystem_write")
            if (op or "tts") in ("tts","speak",None): add("audio_output")

    ⇒ 本函数返回：该分支**可能**加的全部作用域（并集，已在下一个分支头处截断），
      另由 `policy_branch_text()` 把分支原文带出去，让读的人自己看条件。
    """
    if not POLICY.is_file():
        return None
    src = POLICY.read_text(encoding="utf-8", errors="replace")
    m = re.search(_BRANCH % re.escape(kind), src)
    if not m:
        return None
    body = m.group(1)
    # 🔴 2026-09-25 修 FR-6（`false_report_audit --scope workspace` 机检命中）：
    #    原字符类是 `[a-z_]+` —— **不吃数字与大写** ⇒ 将来一旦有人加了带数字/驼峰的作用域
    #    （比如 `tts_v2` / `osintPrivate`），这里会**静默漏掉它**，读出来是"这个分支没挂作用域"
    #    ⇒ 正是本仓最忌的**假缺失**（查不到 ≠ 不存在）。今天 15 个作用域恰好全是小写+下划线，
    #    所以**现在没出错，但坑已经埋好**。改成完整的标识符字符类。
    return tuple(sorted(set(re.findall(r'add\(\s*["\']([A-Za-z0-9_]+)["\']', body))))


def policy_branch_text(kind: str) -> str:
    if not POLICY.is_file():
        return ""
    src = POLICY.read_text(encoding="utf-8", errors="replace")
    m = re.search(_BRANCH % re.escape(kind), src)
    if not m:
        return ""
    return " / ".join(x.strip() for x in m.group(1).splitlines() if x.strip())[:180]


def in_registry(kind: str) -> bool | None:
    if not REGISTRY.is_file():
        return None
    return ('"%s"' % kind) in REGISTRY.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    print("=" * 84)
    print("三套链 · 生成步**插座位**（规格件）· WIRED = %s" % WIRED)
    print("=" * 84)
    if WIRED:
        print("🔴 与本件自述矛盾：规格件声明自己不该被当成接线件，但它写着 WIRED=True —— 停下来核。")
        return 1
    print("  ⚠️ 这三个步**还没有**进 `media_run.CHAINS`。本件只定接口与判据，不通电。\n")
    ok = True
    verified = 0
    for s in SLOTS:
        branch = policy_scopes(s["cap"])          # policy 分支里可能加的全部作用域（并集）
        btext = policy_branch_text(s["cap"])
        reg = in_registry(s["cap"])
        expect = s["expect_scopes"]
        # ── 判据：**按 op 说话**，且只用"不矛盾"这种能被真身支持的结论 ──
        if branch is None:
            # policy 里没有这个 kind ⇒ 闸不在作用域（本件必须也这么声明，才算自洽）
            verdict = ("✅ 自洽：policy 无此 kind，本件也声明「闸不在作用域」"
                       if expect is None else
                       "🔴 矛盾：policy 里查不到这个 kind，而本件仍声明要作用域 %s" % list(expect))
            good = expect is None
            verified += 1 if good else 0
        else:
            if expect is None:
                verdict = "🔴 矛盾：policy 有该 kind 的分支，而本件声明「没有作用域闸」"
                good = False
            else:
                extra = tuple(x for x in branch if x not in expect)
                good = set(expect) <= set(branch)
                verdict = ("✅ 不矛盾：本步用的作用域 %s 都在 policy 该分支可能加的 %s 里%s"
                           % (list(expect) or "（空）", list(branch) or "（空）",
                              ("；条件性作用域 %s（本步 op=%s 不一定加）" % (list(extra), s["op"]))
                              if extra else ""))
                verified += 1 if good else 0
        print("  %-14s %-13s op=%-13s → %s" % (s["step"], s["cap"], s["op"], s["kind"]))
        print("      插到：%s 的 %s 之后 ｜ 产出：%s" % ("/".join(s["into"]), s["after"], s["produces"]))
        print("      判据：%s" % s["judge"])
        print("      policy 分支原文：%s" % (btext or "（policy 里查不到这个 kind）"))
        print("      本件声明：%s ｜ %s" % (list(expect) if expect is not None else "None（闸不在作用域）",
                                      s["expect_note"]))
        print("      在注册表：%s ｜ %s" % ("是" if reg else ("否" if reg is False else "取不到"), verdict))
        print("      另需：%s" % s["gate_extra"])
        if not good:
            ok = False
        print()
    print("判读：%s" % ("✅ %d/%d 格**与 policy 真身不矛盾**（按 op 说话）—— 插座已做好，等主人点头通电"
                     % (verified, len(SLOTS)) if ok else
                     "🔴 未通过：自洽 %d/%d 格。**没核上的按「未验」算，不许读成「没问题」**。" % (verified, len(SLOTS))))
    print("⚠️ 本件**不构成授权**：narration 需 audio_output；frames 需密钥与预算；visual_check（analyze_file）免卡。")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
