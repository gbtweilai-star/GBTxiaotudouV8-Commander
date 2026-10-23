# -*- coding: utf-8 -*-
"""按**内容**识别图片格式并规范化输出（Tripo 的产物常把 JPEG 写成 .png，读取前先规范化）。
用法: python tools/codex-scripts/normalize-image.py <输入> [输出.png]"""
import pathlib
import sys
from PIL import Image

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".norm.png")
im = Image.open(src)                      # PIL 按内容识别
print(f"{src.name}: 真实格式 {im.format} · {im.size[0]}×{im.size[1]} · 模式 {im.mode}")
im.convert("RGB").save(dst)
print(f"规范化输出 → {dst} （{dst.stat().st_size/1024:.0f} KB）")
