# -*- coding: utf-8 -*-
# ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""book_skill —— **书→技能**（主人令 2026-10-16：把 book-to-skill 变成我们的原生能力）

蒸自 **virgiliojr94/book-to-skill**（MIT）的思想：**把任何技术书/文档集变成结构化技能，按需加载**。
四件要点：① 提取器与生成器分开 ② **按需加载** ③ **提结构不提摘要**（每条指回章节）④ 可更新折叠合并。
我们刻意不同的三处：只落**我们自己的托管目录** · 每条**指回出处** · **回读验证**才报成功。
op：plan / contract / extract / pack / budget / check / route（**全只读·零作用域·不出网**）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "Book-to-Skill-书变技能-蒸馏.md"
OUR_SKILLS = "~/.openclaw-autoclaw/skills/<name>/"
READ_OPS = ("plan", "contract", "extract", "pack", "budget", "check", "route")


def plan(source: str = "") -> dict:
    s = (source or "").strip()
    if not s:
        return {"ok": False, "reason": "need_source", "how": "给一个书/文件夹/glob，例：./my-book.pdf"}
    return {"ok": True, "op": "plan", "kind": "book_skill", "source": s,
            "steps": [{"n": 1, "what": "指定", "judge": "文件在且可读"},
                      {"n": 2, "what": "提取（确定性）", "judge": "得到干净文本+元数据含章节边界"},
                      {"n": 3, "what": "生成（spec 驱动）", "judge": "五件产物齐"},
                      {"n": 4, "what": "验收", "judge": "每条指回章节 + 回读一致"}],
            "source_doc": str(DOC)}


def contract() -> dict:
    return {"ok": True, "op": "contract", "kind": "book_skill",
            "artifacts": ["SKILL.md（心智模型+章节索引 ~4000 tokens）",
                          "chapters/ch01-*.md（每章一件、按需加载 ~1000）",
                          "glossary.md（术语+章节引用 ~1500）",
                          "patterns.md（技巧/算法/模式 ~2000）",
                          "cheatsheet.md（决策表 ~1000）"],
            "landing": OUR_SKILLS,
            "forbidden": "不装进 ~/.agents/skills/（与其他工具共用）"}


def extract() -> dict:
    return {"ok": True, "op": "extract", "kind": "book_skill",
            "take": ["框架（心智模型）", "决策规则", "反模式（坑与禁区）", "章节边界"],
            "skip": ["逐字摘要", "无出处的大道理"],
            "judge": "每条结论能指回 章节:行；指不回的不收"}


def pack() -> dict:
    return {"ok": True, "op": "pack", "kind": "book_skill",
            "steps": ["先出章节索引（主件只带索引）", "再写各章文件",
                      "术语表与模式表各自成件", "最后出决策表"],
            "note": "主件小、章节按需加载 = 省 token 的机制"}


def budget() -> dict:
    return {"ok": True, "op": "budget", "kind": "book_skill",
            "core": "把整本书丢进上下文比结构化技能**多花 24×–51× token**",
            "judge": "读一份资料前先问：这一次值不值得拉全文？不值就按需加载章节",
            "note": "对方读数来自其 README 与 docs/performance（我们未复现）"}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "book_skill",
            "rules": ["每条结论能指回章节:行",
                      "提结构不提摘要",
                      "主件只带索引、章节按需加载",
                      "只落我们自己的托管目录",
                      "新增即清旧（折叠合并后旧章节回收）"],
            "doc": str(DOC)}


def route(source: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "book_skill", "source": (source or "").strip(),
            "path": ["意图", "cap book_skill", "提取器（确定性转文本）", "生成器（spec 出五件）", OUR_SKILLS],
            "direct": True}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "plan":
        return plan(kw.get("source") or "")
    if o == "contract":
        return contract()
    if o == "extract":
        return extract()
    if o == "pack":
        return pack()
    if o == "budget":
        return budget()
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("source") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(READ_OPS)}
