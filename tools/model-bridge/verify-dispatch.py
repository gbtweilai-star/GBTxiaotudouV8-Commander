# -*- coding: utf-8 -*-
"""真跑验收 ②：APP 面板里的「派活 ⚡」必须真的把话变成一次能力位调用，并贴真回执。

判据（先写死，别改口径）：
  1. 点「派活」后必须出现 ① 路由块，且里面写明落到了 expected 那位能力位（名字来自目录，不是编的）；
  2. 必须出现 ② 派活块，三种结局只认两种：
       · 「派活成功」  → 里面要带真回执（非空 JSON），且不是占位符；
       · 「门拒绝了」  → 必须明写缺哪个作用域 + 怎么发（缺票不是坏，但**不许**说成成功）；
     第三种（「跑了但没成功」/「连不上桥」）一律判红，并原样贴出来。
  3. 失败也截图 —— 不许把"没通"说成"通了"。

用法：py -3.14 -X utf8 tools/model-bridge/verify-dispatch.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "holo_pet_w3" / "model-chat" / "index.html"
OUT = ROOT / "outputs" / "model-bridge"

CASES = [
    # (人话, 期望落到的能力位, 截图名)
    ("扫一下镜像有没有脏东西", "mirror_scan", "dispatch-ok.png"),
    ("把这次发布推到生产", "one_key_deploy", "dispatch-denied.png"),
]


def run_case(page, question: str, expected: str, shot: pathlib.Path) -> tuple[bool, str]:
    page.fill("#input", question)
    page.click("#dispatch")

    route_txt, act_txt, meta_txt = "", "", ""
    for _ in range(120):                                       # 最多等 120 秒（无服务器会冷启动）
        page.wait_for_timeout(1000)
        nodes = page.locator(".msg.ai").all()
        # 面板开屏那条说明也是 .msg.ai ⇒ 至少要有 3 条（说明 + ① + ②）才可能已经跑完
        if len(nodes) < 3:
            continue
        route_txt = nodes[-2].inner_text().strip()
        act_txt = nodes[-1].inner_text().strip()
        meta = nodes[-1].locator(".meta")
        meta_txt = meta.inner_text().strip() if meta.count() else ""
        if ("派活中" in act_txt) or ("① 问我们自己的模型" in act_txt):
            continue
        break

    page.screenshot(path=str(shot))
    ok_route = expected in route_txt
    ok_act = ("派活成功" in act_txt) or ("门拒绝了" in act_txt)
    if "门拒绝了" in act_txt:
        ok_act = ok_act and ("缺作用域" in act_txt)
    if "派活成功" in act_txt:
        ok_act = ok_act and ("回执" in act_txt) and ("{}" != act_txt.split("回执", 1)[-1].strip())

    print("─" * 72)
    print("问：%s（期望 → %s）" % (question, expected))
    print("① 路由块：\n    %s" % route_txt.replace("\n", "\n    "))
    print("② 派活块：\n    %s" % act_txt.replace("\n", "\n    "))
    print("③ 元信息：%s" % (meta_txt or "（无）"))
    print("截图 →", shot)
    return (ok_route and ok_act), ("①落点对" if ok_route else "①落点不对") + " · " + \
        ("②真回执" if ok_act else "②没拿到可判回执")


def main() -> int:
    from playwright.sync_api import sync_playwright

    if not PANEL.is_file():
        print("面板不存在：", PANEL)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, bool, str]] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for question, expected, name in CASES:
            page = b.new_page(viewport={"width": 1180, "height": 900})
            page.goto(PANEL.as_uri())
            page.wait_for_timeout(1500)
            print("桥徽标：%s" % page.inner_text("#bridge"))
            try:
                ok, why = run_case(page, question, expected, OUT / name)
            except Exception as exc:                           # noqa: BLE001
                ok, why = False, "抛异常：%s: %s" % (type(exc).__name__, exc)
                print("异常：", why)
            results.append((question, ok, why))
            page.close()
        b.close()

    print("═" * 72)
    passed = sum(1 for _q, ok, _w in results if ok)
    for question, ok, why in results:
        print("%s %s → %s" % ("✅" if ok else "❌", question, why))
    print("验收：%d/%d %s" % (passed, len(results), "全绿" if passed == len(results) else "有红（见上图与截图）"))
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
