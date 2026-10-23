# -*- coding: utf-8 -*-
"""真跑验收：模型桥 + APP 内“模型对话”面板，必须看到**真回执**才算通。

判据（先写死，别改）：
  1. 面板能打开（file://）+ 桥 health 徽标变「在线」；
  2. 输入一句话点发送，**必须**出现非空回答，且带 `usage` 元信息（证明是上游真回的，不是本地拼的）；
  3. 失败也要截图为证（红色错误块），不许把"没通"说成"通了"。

用法：py -3.12 -X utf8 tools/model-bridge/verify-in-app.py
"""
from __future__ import annotations

import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "holo_pet_w3" / "model-chat" / "index.html"
SHOT = ROOT / "outputs" / "model-bridge" / "in-app-chat.png"
QUESTION = "一句话说明：单门执行是什么。"


def main() -> int:
    from playwright.sync_api import sync_playwright

    if not PANEL.is_file():
        print("面板不存在：", PANEL)
        return 1
    SHOT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1180, "height": 760})
        page.goto(PANEL.as_uri())
        page.wait_for_timeout(1500)
        badge = page.inner_text("#bridge")
        print("桥徽标：%s" % badge)
        page.fill("#input", QUESTION)
        page.click("#send")
        reply, meta = "", ""
        for _ in range(90):                                    # 最多等 90 秒
            page.wait_for_timeout(1000)
            nodes = page.locator(".msg.ai").all()
            if not nodes:
                continue
            last = nodes[-1]
            body = last.inner_text()
            if "…" == body.strip():
                continue
            reply = body.strip()
            m = last.locator(".meta")
            meta = m.inner_text() if m.count() else ""
            if reply and reply != "…":
                break
        page.screenshot(path=str(SHOT), full_page=False)
        ok = bool(reply) and reply != "…" and "usage" in meta.lower()
        print("回答前 120 字：%s" % reply.replace("\n", " ")[:120])
        print("元信息：%s" % (meta or "（无）"))
        print("截图 →", SHOT)
        b.close()
    print("验收：%s" % ("✅ 通（面板里拿到真回执）" if ok else "❌ 未通（见截图与上面的原话）"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
