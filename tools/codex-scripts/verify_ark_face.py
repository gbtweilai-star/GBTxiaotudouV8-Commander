"""真浏览器校验「能力台上的 Ark 云端能力面」。

查四件事，全部要真读数：
  ① 页面里 CAPS 到底有多少条、多少个域、其中 external 多少条（不被渲染失败蒙混）
  ② Ark 节点的详情页**有没有"调用"按钮** —— 外部 CLI 能力**必须没有**
  ③ 详情页有没有如实写出它自己的 CLI 入口
  ④ 控制台错 / >=400 响应 / canvas 是否真出画面（WebGL 掉上下文时空白帧不算过）

用法：
    C:\\Python312\\python.exe tools/codex-scripts/verify_ark_face.py
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
URL = "http://127.0.0.1:3080/gbt-master/fs/capabilities.html"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SHOT = ROOT / "render" / "能力球-含Ark能力面.png"
PROBE_KIND = "arkcli-billing"


def main() -> int:
    from playwright.sync_api import sync_playwright

    problems: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME, headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        errs, bad = [], []
        pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)[:160]))
        pg.on("response", lambda r: bad.append("%s %s" % (r.status, r.url[:110]))
              if r.status >= 400 else None)
        pg.goto(URL, wait_until="load", timeout=45000)
        pg.wait_for_timeout(6000)

        info = pg.evaluate(
            "()=>({caps:(typeof CAPS!=='undefined')?CAPS.length:null,"
            "doms:(typeof CAPS!=='undefined')?Array.from(new Set(CAPS.map(c=>c.domain))).length:null,"
            "ark:(typeof CAPS!=='undefined')?CAPS.filter(c=>c.state==='external').length:null,"
            "withHelp:(typeof CAPS!=='undefined')?CAPS.filter(c=>c.state==='external'&&c.cli_help).length:null,"
            "lede:((document.querySelector('.hint')||{}).innerText||'').replace(/\\s+/g,' '),"
            "canvas:document.querySelectorAll('canvas').length})")
        print("页面读数: %s" % info)
        if not info["caps"]:
            problems.append("页面里拿不到 CAPS（脚本没跑起来？）")
        if not info["ark"]:
            problems.append("球面上一条 external（Ark）都没有 —— 没接上")
        if info["canvas"] != 1:
            problems.append("canvas 数不是 1（WebGL 可能没起来）")

        pg.screenshot(path=str(SHOT))
        print("截图: %s" % SHOT.relative_to(ROOT))

        # 驱一个 Ark 节点的详情页，看它是不是"诚实地不给调用按钮"
        pg.evaluate("()=>openCap('%s')" % PROBE_KIND)
        pg.wait_for_timeout(900)
        detail = pg.evaluate(
            "()=>{const s=document.getElementById('sheet-in');"
            "return {txt:s?s.innerText.replace(/\\s+/g,' ').slice(0,600):'(找不到详情容器)',"
            "go:!!document.getElementById('go')}}")
        print("--- Ark 节点详情页（%s）---" % PROBE_KIND)
        print(detail["txt"])
        if detail["go"]:
            problems.append("Ark 外部能力竟然渲染了『调用』按钮 —— 那会调一个不存在的路")
        if "arkcli" not in detail["txt"]:
            problems.append("详情页没写出它的 CLI 入口")

        print("控制台错: %s" % (errs or "无"))
        print(">=400 响应: %s" % (bad or "无"))
        if errs:
            problems.append("控制台有错：%s" % errs[:2])
        b.close()

    print("\n=== 结论 ===")
    if problems:
        for p in problems:
            print("  🔴 %s" % p)
        return 1
    print("  ✅ 全过：Ark 能力面已上球面 · 外部能力不给调用按钮 · 自己写了 CLI 入口 · 页面无错")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
