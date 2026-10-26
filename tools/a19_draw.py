#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a19_draw —— 用 **A19 的算力**出图：让她写 SVG，本地渲染成图片。

为什么不是"直接文生图"：A19 跑的是 gbt-v8-v82-q5_0（纯文本模型），**没有图像解码器**，
结构上不可能吐像素。她能做的是写**代码/矢量**——那就让她写 SVG，由浏览器渲染成 PNG。
这条路用的是她真正的算力（她的词表、她的构图判断），不借任何第三方。

用法：
    python3 a19_draw.py "齐天大圣 力劈华山"
    python3 a19_draw.py "…" --render        # 直接渲染成 PNG（需浏览器 tab）
    python3 a19_draw.py --check             # 只检查容器在不在

约定：她必须只吐 <svg>…</svg>，尺寸 768x1024，三色以内，禁用渐变/滤镜/位图。
"""
import argparse
import importlib.util
import json
import os
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
SVG_OUT = "/var/minis/attachments/a19_draw.svg"
PNG_OUT = "/var/minis/attachments/a19_draw.png"

SYSTEM = """你是 GBT小土豆V8，现在只做一件事：把一句话画成 SVG。
硬规则：
1. 只输出一个 <svg>…</svg>，前后不许有任何文字、解释、markdown 代码块。
2. svg 必须带 viewBox="0 0 768 1024"，width="768" height="1024"。
3. 只准用 path / rect / circle / ellipse / polygon / polyline / line / text。
4. 颜色最多三个：一个底、一个墨、一个强调。不许渐变、不许 filter、不许 <image>。
5. 构图要求：一个焦点、主体占画面三分之一以上、留白成块不成碎屑。
6. 中文有就用 text 写，写不出就不写，别用占位符。"""


def ctl():
    spec = importlib.util.spec_from_file_location("a19ctl", str(TOOLS / "a19_ctl.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def extract_svg(text):
    m = re.search(r"<svg[\s\S]*?</svg>", text or "", re.I)
    if not m:
        return None
    s = m.group(0)
    if "viewBox" not in s:
        s = s.replace("<svg", '<svg viewBox="0 0 768 1024"', 1)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--tokens", type=int, default=1400)
    ap.add_argument("--temp", type=float, default=0.6)
    a = ap.parse_args()

    c = ctl()
    st = c.status_dict()
    if a.check or not a.prompt:
        print("容器 %s · %s" % (st.get("container"), st.get("why") or "models=%s" % st.get("models")))
        return 0 if st.get("container") == "UP" else 2

    if st.get("container") != "UP":
        print("容器不在 —— A19 没有算力可用（:1234 无监听），不借用任何外部模型顶替。")
        return 2

    q = " ".join(a.prompt)
    r = c.chat_dict([{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "画：" + q}], a.tokens, a.temp)
    if not r.get("ok"):
        print("A19 出错：%s" % r.get("why"))
        return 3

    svg = extract_svg(r.get("answer") or "")
    if not svg:
        print("她这次没吐出合法 SVG（原文前 300 字）：\n%s" % (r.get("answer") or "")[:300])
        return 4

    pathlib.Path(SVG_OUT).write_text(svg, encoding="utf-8")
    print("[A19] %s · %ss · %s tok/s · SVG %d 字节 → %s"
          % (r.get("model"), r.get("elapsed_s"), r.get("tok_s"), len(svg), SVG_OUT))
    print("渲染：minis-browser-use navigate --url minis://attachments/a19_draw.svg 然后截图")
    return 0


if __name__ == "__main__":
    sys.exit(main())
