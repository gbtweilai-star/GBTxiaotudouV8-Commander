# -*- coding: utf-8 -*-
"""页面文本卫生（唯一实现）—— 重建版（2026-11-01 补齐）。

## 为什么有这个文件
本仓 `tools/codex-scripts/` 里 8 个脚本 `from _page_text import clean/scrub/esc`，
但**该文件从未随仓库发布**（全仓 0 文件，上游 `gbtweilai-star/GBTxiaotudouV8-Commander@main`
逐路径实测 404；`tools/codex-scripts/README` 也没记）。2026-11-01 按**调用方契约 + 仓内注释**
把它补回来，行为以下面这些仓内已写明的判据为准：

  · `capability-audit.py:1027-1031`：台账里的 **markdown 记号**要剥掉 ——
    `**回环**` 不能印成两个星号、`` `py -3.14 …` `` 不能印成反引号；
    但 `state/**/*.json` 这种 glob 里的 `**` 是**内容**，只剥**成对形态**。
  · `health-ledger.py:141-143`：同上，另加长度上限（`_c(读数, 120)`）。
  · `ai-board.py:209-211`：`esc(x, dflt)` = 转义 + `None` 显示成 `dflt`；
    台账里计数缺键是 `None`，直接插值会在界面印出字面 `None`。
  · `ai-board.py:162`：`scrub({...})` 对**整块外来数据**递归洗（dict/list 里的字符串）。

本文件是**重建件**，不是原作者原文；实现只覆盖上述契约，不猜多余行为。
"""
from __future__ import annotations

import html
import re

__all__ = ["EMOJI", "clean", "scrub", "esc"]

# 仓内统一 emoji 面：与 quick_scan.py:196 / capability-audit 旧 `_EMOJI` 同口径
EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF"      # 各类 emoji 块
    "\U00002600-\U000027BF"       # 杂项符号 / Dingbats
    "\U00002B00-\U00002BFF"       # 箭头 / 星
    "\U0000FE0E\U0000FE0F"        # 变体选择符
    "\U0000200D"                  # ZWJ
    "\U000020E3]"                 # 组合键帽
)

# 只剥**成对**形态：`**粗体**` / `` `行内代码` ``。
# 单星号、单个反引号、以及 `state/**/*.json` 这种没闭合的 `**` 一律不动。
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
_CODE = re.compile(r"(?<!`)`(?=\S)([^`\n]+?)(?<=\S)`(?!`)")

_WS_LEAD = re.compile(r"^\s+")
_WS_TAIL = re.compile(r"\s+$")


def _strip_markup(s: str) -> str:
    """剥 emoji + 成对 markdown 记号；最多 3 轮（嵌套/相邻成对）。"""
    s = EMOJI.sub("", s)
    for _ in range(3):
        nxt = _BOLD.sub(r"\1", s)
        nxt = _CODE.sub(r"\1", nxt)
        if nxt == s:
            break
        s = nxt
    return s.replace("\u200b", "").replace("\ufeff", "")


def clean(x, limit=None, strip=True) -> str:
    """外来文本 → 可印文本。

    · `None` / 非字符串：`None` 回空串，其余 `str()` 后处理；
    · 去 emoji、只剥成对 markdown 记号（判据见模块头）；
    · `limit`：给定时按**字符数**截断并以 `…` 收尾（`health-ledger` 的 `_c(读数, 120)`）；
    · `strip=False`：保留首尾空白（`_page_emit` 洗 HTML 文本节点时用，避免把
      `hello <b>world</b>` 中间的空白吃掉）。
    """
    if x is None:
        return ""
    s = x if isinstance(x, str) else str(x)
    if not s:
        return ""
    lead = _WS_LEAD.match(s)
    tail = _WS_TAIL.search(s)
    core = _strip_markup(s)
    if strip:
        core = core.strip()
        out = core
    else:
        out = (lead.group(0) if lead else "") + core.strip() + (tail.group(0) if tail else "")
    if limit is not None and limit > 0 and len(out) > limit:
        out = out[: max(1, limit - 1)] + "…"
    return out


def scrub(obj):
    """递归清洗：dict / list / tuple / set 里的字符串走 `clean()`，其余原样。"""
    if isinstance(obj, str):
        return clean(obj)
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(scrub(v) for v in obj)
    if isinstance(obj, set):
        return {scrub(v) for v in obj}
    return obj


def esc(x, dflt="—") -> str:
    """进 HTML 前的唯一出口：清洗 → HTML 转义；空/None 显示成 `dflt`。"""
    if x is None:
        return dflt
    s = clean(x)
    return html.escape(s, quote=True) if s else dflt
