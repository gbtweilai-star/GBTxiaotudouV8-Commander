# gbt-capability: answer_shaper
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""行动优先输出核：**ADHD 友好输出的可机检版**（蒸馏自 i-have-adhd 的纪律面）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜截图 `ayghri/i-have-adhd`——截图只露了**仓库名**。
  从名字与仓里已有技能 `gbt-adhd-mode` 同族判断，是"ADHD 友好输出"的纪律技能。
  🔴 **未联网核验、未读它一个字** ⇒ 本件**不引用该仓任何代码/文本/规则原文**；
  下面每条纪律规则都取自**本仓自己的规矩**（AGENTS.md 沟通纪律：先给下一步行动、
  编号多步任务、无铺垫无收尾客套），不是抄来的。
· **时间**：2026-09-28。
· **口径**：ADHD 友好输出的纪律面已有技能（`gbt-adhd-mode`，提示词侧）；本件补的是
  **运行时可机检的核**——给一段文字打分（行动优先吗？编号了吗？超 5 步吗？有客套铺垫吗？），
  并做**纯机械**的重排（剥铺垫、抽步骤、截到 5 步）；判不了的部分**如实标"未判定"**，不编造。

## 硬规矩
1. **确定性**：check/shape 全是规则运算，不调大模型 ⇒ 可单测、零出网、零幻觉。
2. **不编造**：shape 只会**挪动/剥离**原文里已有的句子；抽不出步骤的部分
   原样放进 `未判定` 区并标"需人看"——绝不替作者补写内容。
3. **分数可见**：check 的每条规则带命中细节，哪条红哪条过，看得见。
"""
from __future__ import annotations

import re

_PREAMBLE = ("好的", "当然", "没问题", "以下是", "首先让我", "让我来", "我来说明",
             "接下来我", "明白了", "收到")
_CLOSERS = ("祝", "希望对你有帮助", "希望有帮助", "如果还有", "随时问我", "欢迎追问",
            "谢谢阅读", "有问题再")
_ACTION_HINT = ("先", "然后", "接着", "运行", "打开", "创建", "检查", "发送", "跑",
                "写", "改", "看", "读", "装", "配", "点", "按", "执行", "开始", "停")
_NUM = re.compile(r"^\s*(\d+)[.、)）]\s*")


def _lines(text: str) -> list:
    return [ln.rstrip() for ln in str(text or "").splitlines()]


def check(text: str = "", **_kw) -> dict:
    """给一段文字打分：行动优先 / 编号 / 步数 / 客套 / 下一步。**纯规则，零模型**。"""
    lines = [ln for ln in _lines(text) if ln.strip()]
    if not lines:
        return {"ok": False, "fail_closed": True, "error": "text 要给（非空）"}
    first = lines[0].strip()
    steps = [ln for ln in lines if _NUM.match(ln)]
    rules = [
        {"id": "R1_行动优先", "ok": not first.startswith(_PREAMBLE),
         "detail": "首行=%s…" % first[:20] if not first.startswith(_PREAMBLE)
                   else "首行是铺垫（%s…）" % first[:16]},
        {"id": "R2_编号步骤", "ok": bool(steps),
         "detail": "编号行 %d 条" % len(steps) if steps else "全文没有编号步骤"},
        {"id": "R3_步骤≤5", "ok": (len(steps) <= 5) if steps else True,
         "detail": "编号行 %d 条" % len(steps)},
        {"id": "R4_无客套收尾", "ok": not any(c in text for c in _CLOSERS),
         "detail": "含客套词" if any(c in text for c in _CLOSERS) else "干净"},
        {"id": "R5_有下一步", "ok": any(h in first for h in _ACTION_HINT) or bool(steps),
         "detail": "首行含动作意图" if any(h in first for h in _ACTION_HINT)
                   else ("有编号步骤" if steps else "首行无动作意图且无步骤")},
    ]
    bad = [r["id"] for r in rules if not r["ok"]]
    return {"ok": not bad, "op": "check", "rules": rules, "failed": bad,
            "_口径": "确定性规则（零模型零出网）；规则源=本仓沟通纪律，非该仓原文"}


def shape(text: str = "", max_steps: int = 5, **_kw) -> dict:
    """纯机械重排：剥铺垫 → 抽编号步骤（截到 max_steps）→ 首行=第一步。
    抽不出的原文**原样**进 `未判定` 区并标"需人看"——**不替作者补写**。"""
    if not str(text or "").strip():
        return {"ok": False, "fail_closed": True, "error": "text 要给（非空）"}
    lines = [ln for ln in _lines(text) if ln.strip()]
    pre, steps, rest = [], [], []
    for ln in lines:
        if _NUM.match(ln):
            steps.append(ln.strip())
        elif ln.startswith(_PREAMBLE) and not steps:
            pre.append(ln)                              # 只剥"步骤开始前"的铺垫
        else:
            rest.append(ln)
    kept, dropped = steps[:max(1, int(max_steps))], steps[max(1, int(max_steps)):]
    lead = kept[0] if kept else (rest[0] if rest else "")
    out = {
        "lead": lead,
        "steps": kept,
        "steps_dropped": len(dropped),
        "stripped_preamble": pre,
        "未判定": {"rows": [ln for ln in rest if ln != lead],
                   "why": "这些行不是编号步骤，机器判不了它该不该留 ⇒ 原样保留，需人看（不编造）"},
    }
    c = check("\n".join([out["lead"]] + out["steps"]))
    out["check_after"] = {"ok": c.get("ok"), "failed": c.get("failed")}
    out["_口径"] = "纯机械挪动/剥离，不补写一字；判不了的如实标未判定"
    return {"ok": True, "op": "shape", **out}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "answer_shaper", "tentacle": "answer_shaper",
            "entry": "run_task('answer_shaper', {...})",
            "ops": ["check", "shape", "where"],
            "distilled_from": "2026-09-28 主人给的周榜截图 ayghri/i-have-adhd——截图只给仓库名；"
                              "蒸馏的是『ADHD 友好输出』的纪律面，**未引用该仓任何代码/文本**",
            "not_copied": "规则取自本仓自己的沟通纪律（AGENTS.md：先给下一步行动、编号多步、少铺垫）"
                          "与已有技能 gbt-adhd-mode（提示词侧）；本件补的是**运行时可机检的核**",
            "hard_rules": ["确定性：check/shape 全是规则运算（零模型零出网零幻觉）",
                           "不编造：shape 只挪动/剥离原文，判不了的标未判定需人看",
                           "分数可见：每条规则带命中细节"],
            "files": {},
            "contract": [
                {"op": "check", "params": "text", "returns": "五条规则逐条判定（R1..R5）"},
                {"op": "shape", "params": "text [max_steps]", "returns": "重排稿 + 未判定区 + 复检"},
            ]}


def run_op(op: str = "check", **params) -> dict:
    op = (op or "check").lower()
    for name, fn in (("check", check), ("shape", shape), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（check/shape/where）"}


if __name__ == "__main__":                                    # 主人的终端入口
    import argparse
    import json
    ap = argparse.ArgumentParser(description="行动优先输出核（可机检 · 零模型）")
    ap.add_argument("cmd", nargs="?", default="check")
    ap.add_argument("--text", default="")
    ap.add_argument("--max-steps", type=int, default=5)
    a = ap.parse_args()
    if a.cmd == "shape":
        print(json.dumps(run_op("shape", text=a.text, max_steps=a.max_steps),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_op("check", text=a.text), ensure_ascii=False, indent=1))
