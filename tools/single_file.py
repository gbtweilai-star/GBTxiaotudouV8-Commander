#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""single_file —— 把 deck.html 里引用的本地图片内联成 base64，产出单文件版。

为什么做：包里的 deck.html 依赖 media/ 目录。发微信/邮件时得打 zip，
对方还要解压。单文件版**一个 html 走天下**，双击就开，零依赖。
"""
from __future__ import annotations

import base64
import mimetypes
import os
import re
import sys


def inline(html_path: str, out_path: str) -> dict:
    with open(html_path, encoding="utf-8") as fh:
        html = fh.read()
    base = os.path.dirname(os.path.abspath(html_path))
    pat_attr = r'(?:src|href)="([^"#:]+?\.(?:png|jpg|jpeg|webp|gif))"'
    pat_css = r'url\(([^)"\']+?\.(?:png|jpg|jpeg|webp|gif))\)'
    refs = sorted(set(re.findall(pat_attr, html, re.I)) | set(re.findall(pat_css, html, re.I)))
    done, skipped = [], []
    for rel in refs:
        p = os.path.normpath(os.path.join(base, rel))
        if not os.path.exists(p):
            skipped.append(rel)
            continue
        mime = mimetypes.guess_type(p)[0] or "image/png"
        with open(p, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        uri = "data:%s;base64,%s" % (mime, data)
        # 两种写法都要换：属性值和 CSS url()
        html = html.replace('"%s"' % rel, '"%s"' % uri)
        html = html.replace("url(%s)" % rel, "url(%s)" % uri)
        done.append("%s (%.0f KB)" % (rel, os.path.getsize(p) / 1024))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return {"out": out_path, "bytes": os.path.getsize(out_path),
            "inlined": done, "missing": skipped,
            "left": len(re.findall(r'(?:src|href)="(?!data:)[^"#:]+\.(?:png|jpg|jpeg|webp)"', html, re.I))}


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: single_file.py <in.html> [out.html]")
        return 2
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + "-single.html"
    r = inline(src, dst)
    print("单文件 %s · %.1f MB" % (r["out"], r["bytes"] / 1048576))
    for x in r["inlined"]:
        print("  内联 %s" % x)
    for x in r["missing"]:
        print("  缺  %s（跳过）" % x)
    print("剩余外链图 %d 个" % r["left"])
    return 0 if r["left"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
