# -*- coding: utf-8 -*-
"""页面落盘的唯一出口 —— 重建版（2026-11-01 补齐）。

## 为什么有这个文件
`capability-audit` / `capability-bindings` / `cloud-plugins` / `cloud-status` /
`health-ledger` / `ai-board` / `blueprint-feed` / `welcome-page` 这 8 个生成器
都 `from _page_emit import clean_html`，但**该文件从未随仓库发布**（全仓 0 文件，
上游 main 逐路径实测 404）。2026-11-01 按调用方契约补回：

  · `PAGE.write_text(clean_html(render_page(model)))` —— 出口洗一遍再落盘；
  · 只洗**文本节点**：emoji / 成对 markdown 记号（走 `_page_text.clean`）；
  · **绝不改标签与属性**，也**不碰** `<script>` / `<style>` / `<pre>` / `<code>` /
    `<textarea>` 的内容 —— JS 的 `**` 是幂运算、CSS/代码块里的记号是内容
    （判据同 `capability-audit.py:1027-1031`：glob `**` 不许动）；
  · 文本节点首尾空白保留（否则 `hello <b>world</b>` 会粘成 `helloworld`）。

本文件是**重建件**，不是原作者原文。
"""
from __future__ import annotations

from html.parser import HTMLParser

from _page_text import clean as _clean

__all__ = ["clean_html"]

# 内容按原样保留的标签（写成集合，含大小写两种调用面）
_RAW = {"script", "style", "pre", "code", "textarea", "xmp", "plaintext"}


class _Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.raw_depth = 0

    # ── 标签原样回写（用源文本，不改大小写/属性引号）──────────────
    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag in _RAW:
            self.raw_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in _RAW and self.raw_depth > 0:
            self.raw_depth -= 1
        self.out.append("</%s>" % tag)

    # ── 文本：只有非 raw 上下文才洗 ────────────────────────────────
    def handle_data(self, data):
        if not data:
            return
        self.out.append(data if self.raw_depth else _clean(data, strip=False))

    # ── 实体 / 注释 / 声明原样保留（convert_charrefs=False 保证不走丢）──
    def handle_entityref(self, name):
        self.out.append("&%s;" % name)

    def handle_charref(self, name):
        self.out.append("&#%s;" % name)

    def handle_comment(self, data):
        self.out.append("<!--%s-->" % data)

    def handle_decl(self, decl):
        self.out.append("<!%s>" % decl)

    def handle_pi(self, data):
        self.out.append("<?" + (data if data.endswith(">") else data + ">"))

    def handle_unknown_decl(self, data):
        self.out.append("<![%s]>" % data)


def clean_html(html_text) -> str:
    """把页面 HTML 的文本节点洗一遍（emoji / 成对 markdown），标签与脚本原样。"""
    if html_text is None:
        return ""
    if not isinstance(html_text, str):
        html_text = str(html_text)
    p = _Cleaner()
    p.feed(html_text)
    p.close()
    return "".join(p.out)
