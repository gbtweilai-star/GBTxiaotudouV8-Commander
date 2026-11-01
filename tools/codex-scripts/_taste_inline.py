# -*- coding: utf-8 -*-
"""内联站点审美令牌（唯一实现）—— 重建版（2026-11-01 补齐）。

## 为什么有这个文件
`capability-audit` / `capability-bindings` / `cloud-plugins` / `cloud-status` /
`health-ledger` / `blueprint-feed` 这 6 个生成器都 `from _taste_inline import site_root_block`，
但**该文件从未随仓库发布**（全仓 0 文件，上游 main 逐路径实测 404）。2026-11-01 按
**仓内已生成页面里的内联块**反推补回：

  · 单一源（原注释写的）：`state/taste/*.json` → `holo_pet_w3/theme/taste-tokens.css`；
    但这两处在盘上都不存在（`state/` 只有运行数据，`theme/` 目录没有文件）。
  · 本件先用**冻结快照**：逐字节取自 2026-10-27 之后生成的页面
    `holo_pet_w3/capabilities/index.html`（`site_root_block()` 的内联产物），
    这样新生成页与现存页的令牌**完全一致**，不会出现两套色板。
  · 若哪天 `holo_pet_w3/theme/taste-tokens.css` 回来了，优先读它（现读优先，快照兜底，
    与仓内"单一源、别抄第二份"的纪律一致）。

返回值契约（按调用方用法反推，已核对生成页）：
    `:root{\n --taste-…}` —— **不含 `<style>` 标签、不带尾随换行**。
    调用方自己拼 `"<style>\n" + site_root_block() + "/* … */"`。

本文件是**重建件**，不是原作者原文；色值来自仓内已生成页，未自造新色。
"""
from __future__ import annotations

import re
from pathlib import Path

__all__ = ["site_root_block", "TASTE_KEYS", "FROZEN"]

_ROOT = Path(__file__).resolve().parents[2]
_THEME = _ROOT / "holo_pet_w3" / "theme" / "taste-tokens.css"
_ROOT_BLOCK = re.compile(r":root\s*\{[^}]*\}")

# 冻结快照：与 holo_pet_w3/capabilities/index.html 内联块逐字相同（2026-10-27 版）
FROZEN = (
    ":root{\n"
    " --taste-ground:#0B1120;--taste-surface:#111827;--taste-raised:#1A2535;"
    "--taste-border:#1E3A5F;--taste-rule:#162035;--taste-control:#1E3A5F;"
    "--taste-text:#E8ECF8;--taste-muted:#9AA4C4;--taste-faint:#6B7280;"
    "--taste-accent:#F5B041;--taste-positive:#00E5FF;--taste-negative:#EF4444;"
    "--taste-warning:#F5B041;--taste-unknown:#7C4DFF;"
    "--taste-radius:10px;--taste-font:Segoe UI, system-ui, sans-serif;"
    "--taste-fs-title:22px;--taste-fs-section:16px;--taste-fs-kpi:22px;"
    "--taste-fs-body:13px;--taste-fs-small:11.5px}"
)

TASTE_KEYS = (
    "--taste-ground", "--taste-surface", "--taste-raised", "--taste-border",
    "--taste-rule", "--taste-control", "--taste-text", "--taste-muted",
    "--taste-faint", "--taste-accent", "--taste-positive", "--taste-negative",
    "--taste-warning", "--taste-unknown", "--taste-radius", "--taste-font",
    "--taste-fs-title", "--taste-fs-section", "--taste-fs-kpi", "--taste-fs-body",
    "--taste-fs-small",
)


def site_root_block() -> str:
    """返回可内联进 `<style>` 的 `:root{…}` 令牌块。

    现读优先：`holo_pet_w3/theme/taste-tokens.css` 存在时抽它的第一个 `:root{…}`；
    否则回冻结快照（来源见模块头）。读不到/解析不出也回快照 —— 令牌层永远有值。
    """
    try:
        text = _THEME.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FROZEN
    m = _ROOT_BLOCK.search(text)
    if not m:
        return FROZEN
    return m.group(0)
