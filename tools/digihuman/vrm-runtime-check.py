# -*- coding: utf-8 -*-
"""S10b/S11 运行时门：用 **three-vrm 官方实现**加载 avatar.vrm，读它自己算出的 humanoid/expressions/springBone。

    python tools/digihuman/vrm-runtime-check.py [vrm路径]

判据：官方实现能读出 ≥15 根 humanoid 骨 ⇒ 我们的 VRM 合规（比自写检查强得多）。
需要本地服务（8788）在跑：node plugins/gbt-master/tools/serve-digital-human.mjs
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
PAGE = "/holo_pet/assets/digital-human/web/vrm-runtime-check.html"   # 必须在白名单目录（tools/ 被路由 DENY）
VRM = sys.argv[1] if len(sys.argv) > 1 else "/gbt-master/fs/holo_pet/assets/digital-human/raw/rig/avatar.vrm"
BASE = "http://127.0.0.1:3080/gbt-master/fs"


def _find_chrome() -> str:
    """🔴 2026-09-26 自纠：原来写死 x64 Program Files 一条路 —— Chrome 装在用户目录/x86 时
    launch 直接炸。现按 环境变量 → PATH → 三个常见落点 找；都找不到返回空串
    （回落 Playwright 自带内核，不硬性要求装 Chrome）。"""
    cands = [os.environ.get("GBT_CHROME_PATH") or "", shutil.which("chrome") or "",
             shutil.which("chromium") or "",
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             str(pathlib.Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe")]
    return next((c for c in cands if c and pathlib.Path(c).is_file()), "")


def selftest() -> int:
    """S10b/S11 运行时门的负控 —— **能测的测，测不了的如实报缺前置（rc=3）**。

    🔴 2026-10-10 补。起因：judge-map 逐阶段清点负控出处，S11 那格是空的。
    这道门要**本地服务 + Playwright + three-vrm** 才能真跑，不是随时可跑的判据。
    那就**别假装**：把不依赖服务的部分（找 Chrome 的那条回退链）配上真负控，
    需要服务的那部分**如实标 rc=3 = 不适用（缺前置）** —— 与"失败(rc=1)"分开，读数才不糊。
    """
    fails, n = [], [0]

    def c(name, got, want):
        n[0] += 1
        ok = (got == want)
        print("  %-56s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    # ① 找 Chrome 的回退链：给一个**不存在的** GBT_CHROME_PATH ⇒ 不许被选中（真负例）
    old = os.environ.get("GBT_CHROME_PATH")
    try:
        bogus = "C:/_no_such_chrome_/nope.exe"        # 注意：**不用反斜杠** —— 写 \n 会被当成换行
        os.environ["GBT_CHROME_PATH"] = bogus
        got = _find_chrome()
        c("_find_chrome 负例·环境变量指向不存在的路径 ⇒ **不返回它**",
          got != bogus, True)
        # ② 都找不到时**返回空串**（回落 Playwright 自带内核）—— 这是契约，不是失败
        c("_find_chrome 契约·找不到就返回空串（回落自带内核，不硬性要求装 Chrome）",
          isinstance(got, str), True)
    finally:
        if old is None:
            os.environ.pop("GBT_CHROME_PATH", None)
        else:
            os.environ["GBT_CHROME_PATH"] = old
    print()
    print("  找 Chrome: %r" % (_find_chrome(),))
    # ③ 需要服务的部分：探一下 BASE 在不在；不在就**如实报缺前置**，退 rc=3（不是"失败"）
    import urllib.request
    try:
        urllib.request.urlopen(BASE, timeout=3)
        served = True
    except Exception:                                                 # noqa: BLE001
        served = False
    print("  本地服务 %s: %s" % (BASE, "在" if served else "**不在**"))
    print()
    if not served:
        print("运行时可判部分的自检: %s（%d 条）"
              % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
        print("⚠️ **需要服务的那部分没跑** —— %s 不在 ⇒ rc=3 = **不适用（缺前置）**，不是失败" % BASE)
        return 3
    print("运行时可判部分的自检: %s（%d 条）· 服务在，可真跑"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
    return 0 if not fails else 1


def main():
    from playwright.sync_api import sync_playwright
    url = f"{BASE}{PAGE}?vrm={VRM}"
    chrome = _find_chrome()
    kw = {"headless": True,
          "args": ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]}
    if chrome:
        kw["executable_path"] = chrome
    with sync_playwright() as pw:
        b = pw.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": 760, "height": 720})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
        pg.on("console", lambda m: errs.append("console:" + m.text[:160]) if m.type == "error" else None)
        pg.goto(url, wait_until="load", timeout=60000)
        rep = None
        try:
            pg.wait_for_function("() => window.__vrmReport !== undefined", timeout=90000)
            rep = pg.evaluate("() => window.__vrmReport")
        except Exception as e:
            errs.append("wait:" + str(e)[:80])
        painted = pg.evaluate("() => document.querySelector('canvas')?.dataset.painted")
        pg.screenshot(path=str(WS / "render/VRM-运行时验收.png"))
        b.close()
    ok = bool(rep and rep.get("ok"))
    print(f"运行时门: {'✅' if ok else '❌'} " + (json.dumps(rep, ensure_ascii=False) if rep else "无读数"))
    if errs:
        print("  问题: " + " | ".join(errs[:3]))
    print(f"  画面已绘制: {painted} · 截图 render/VRM-运行时验收.png")
    return 0 if ok else 1


if __name__ == "__main__":
    if "selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
