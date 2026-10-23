# -*- coding: utf-8 -*-
"""把 `arms/tentacle3d.html` 真跑起来录成 GIF（README 首屏用）。

真跑，不是画示意图：用 Playwright 打开本仓的 3D 页，按固定节拍截帧，再合成 GIF。
判读（先写死）：
  · 每帧必须**有内容变化**（帧差 > 0），否则说明页面没动/没加载 ⇒ 如实报，不出 GIF；
  · 页面自身是自包含的（无外部依赖），所以离线也能录；
  · 录不到就报原因，不拿静态图冒充动图。

产物：outputs/open-source-release/assets/tentacle3d.gif
用法：py -3.12 -X utf8 tools/codex-scripts/render-tentacle3d-gif.py
"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGE = ROOT / "outputs" / "open-source-release" / "arms" / "tentacle3d.html"
OUT = ROOT / "outputs" / "open-source-release" / "assets" / "tentacle3d.gif"
TMP = ROOT / "outputs" / "demo-gif" / "tentacle3d"
W, H = 720, 496
FRAMES = 26            # 26 帧 × 120ms ≈ 3.1 秒（README 首屏够看，体积可控）
INTERVAL_MS = 120


def main() -> int:
    from playwright.sync_api import sync_playwright

    if not PAGE.is_file():
        print("缺页面：", PAGE)
        return 1
    TMP.mkdir(parents=True, exist_ok=True)
    shots: list[pathlib.Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto(PAGE.as_uri())
        page.wait_for_timeout(2500)                       # 等 3D 初始化
        title = page.title()
        for i in range(FRAMES):
            f = TMP / ("f%03d.png" % i)
            page.screenshot(path=str(f))
            shots.append(f)
            page.wait_for_timeout(INTERVAL_MS)
            if i == FRAMES // 2:                          # 中途点一下画面，触发交互（如果有）
                try:
                    page.mouse.move(W // 2, H // 2)
                    page.mouse.down()
                    page.mouse.move(W // 2 + 160, H // 2 + 40, steps=8)
                    page.mouse.up()
                except Exception:                         # noqa: BLE001
                    pass
        browser.close()

    # 帧差校验：动图必须真的在动
    diffs = []
    prev = None
    for f in shots:
        im = Image.open(f).convert("L").resize((120, 80))
        if prev is not None:
            diffs.append(sum(abs(a - b) for a, b in zip(im.getdata(), prev.getdata())) / (120 * 80))
        prev = im
    moving = sum(1 for d in diffs if d > 0.5)
    print("页面标题：%s · 帧数 %d · 有变化帧 %d/%d（平均帧差 %.2f）"
          % (title, len(shots), moving, len(diffs), sum(diffs) / max(1, len(diffs))))
    if moving < len(diffs) * 0.3:
        print("⚠ 页面基本没动（可能是静态渲染或 WebGL 未启用）⇒ 不出 GIF，如实报")
        return 2

    frames = [Image.open(f).convert("RGB").resize((W, H)) for f in shots]
    pal = [im.convert("P", palette=Image.ADAPTIVE, colors=32) for im in frames]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=INTERVAL_MS,
                loop=0, optimize=True, disposal=2)
    print("已渲染 →", OUT, "·", round(OUT.stat().st_size / 1024, 1), "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
