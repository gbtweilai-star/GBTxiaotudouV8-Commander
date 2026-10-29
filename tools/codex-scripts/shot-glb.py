# -*- coding: utf-8 -*-
"""通用 GLB 截图工具：真浏览器渲染并截图，同时回报顶点/三角形/贴图/动作读数。

前置：先起本地服务（plugins/gbt-master/tools/serve-digital-human.mjs → 8788，它服务整个工作区）
用法：python tools/codex-scripts/shot-glb.py <工作区相对路径.glb> <输出名.png> [rot]
"""
import json
import pathlib
import sys
from playwright.sync_api import sync_playwright

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE = "http://127.0.0.1:8788"

glb = sys.argv[1] if len(sys.argv) > 1 else "/assets/treasure-chest.glb"
name = sys.argv[2] if len(sys.argv) > 2 else "glb-渲染.png"
rot = sys.argv[3] if len(sys.argv) > 3 else "0.6"
focus = sys.argv[4] if len(sys.argv) > 4 else ""
out = WS / "render" / name

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME, headless=True,
                           args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 780, "height": 780})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.on("response", lambda r: errs.append(f"{r.status} {r.url[-60:]}") if r.status >= 400 else None)
    extra = sys.argv[5] if len(sys.argv) > 5 else ""          # 追加查询串，如 clip=walk&strip=8&inplace=1
    url = f"{BASE}/tools/codex-scripts/view-glb.html?glb={glb}&rot={rot}&focus={focus}&{extra}"
    pg.goto(url, wait_until="load", timeout=40000)
    # 等"真的画出来了"（__painted 需要画面明暗差 > 12，能挡住 WebGL 掉上下文导致的空帧）
    painted = False
    for _ in range(20):
        try:
            pg.wait_for_function("() => window.__painted === true || window.__err", timeout=5000)
            painted = pg.evaluate("() => window.__painted === true")
            if painted or pg.evaluate("() => !!window.__err"):
                break
        except Exception:
            pass
    if not painted:
        errs.append("未能确认画面已绘制（可能 WebGL 掉上下文）；__spread=" + str(pg.evaluate("() => window.__spread")))
    pg.wait_for_timeout(400)
    m = pg.evaluate("""()=>({file:document.getElementById('f').textContent,
        v:document.getElementById('v').textContent, t:document.getElementById('t').textContent,
        tex:document.getElementById('tx').textContent, an:document.getElementById('an').textContent,
        err:window.__err||''})""")
    pg.screenshot(path=str(out))
    print(json.dumps(m, ensure_ascii=False))
    print("问题:", errs[:4] if errs else "无")
    print("saved:", out)
    b.close()
