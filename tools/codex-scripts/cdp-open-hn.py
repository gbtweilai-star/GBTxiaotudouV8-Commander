# -*- coding: utf-8 -*-
"""把一个**已在 9222 上开着 CDP** 的 Chrome 导航到 HN 投稿页，并截图确认（只读观察）。

为什么需要它：Chrome 136+ 出于安全默认**禁止**对默认 profile 开 `--remote-debugging-port`，
所以驱动用的 Chrome 必须带独立的 `--user-data-dir`（`outputs/cdp-profile`）。
那个 profile 是空的 ⇒ **HN 登录态不在里面**，需要主人在这个窗口里登录一次。

用法：
  py -3.12 -X utf8 tools/codex-scripts/cdp-open-hn.py              # 打开投稿页 + 截图
  py -3.12 -X utf8 tools/codex-scripts/cdp-open-hn.py --shot out.png
"""
from __future__ import annotations

import argparse
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_SHOT = ROOT / "outputs" / "launch" / "hn-page.png"
HN_SUBMIT = "https://news.ycombinator.com/submit"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", default=str(DEFAULT_SHOT))
    ap.add_argument("--url", default=HN_SUBMIT)
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(a.url, wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        title = page.title()
        url = page.url
        # 只读观察：页面上有没有登录表单 / 有没有提交表单
        has_login = page.locator("input[name='acct']").count() > 0
        has_submit_form = page.locator("input[name='title']").count() > 0
        text = ""
        try:
            text = page.inner_text("body")[:600].replace("\n", " ")
        except Exception:                                     # noqa: BLE001
            pass
        out = pathlib.Path(a.shot)
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out), full_page=False)
        print("标题：%s" % title)
        print("URL ：%s" % url)
        print("登录表单：%s · 投稿表单：%s" % (has_login, has_submit_form))
        print("页面首段：%s" % text[:200])
        print("截图 → %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
