# -*- coding: utf-8 -*-
"""把「上帝视角」窗口**带真实数据**渲染出来。

为什么以前渲染不出来：holo_pet_w3/index.html 的 CSP 是 connect-src 'none'，
全部数据走 `window.gbtW3`（preload 注入的 IPC 桥）。在普通浏览器里没有这座桥，
window.js 就走 noBridge() 兜底 —— 六个标签页全是"没有接上宿主进程"。

本脚本：
  ① 用 .scratch/god_view_call.cjs 真调出来的 15 条通道原始载荷当数据源
  ② 在页面脚本执行前注入 window.gbtW3（与 preload 暴露的同形）
  ③ 按设计尺寸 1080×680 逐个标签页截图

只读：不改 holo_pet_w3 任何文件；截图落 render/godview/。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = ROOT / "holo_pet_w3" / "index.html"
FULL = ROOT / ".scratch" / "_god_view_full.json"
OUT = ROOT / "render" / "godview"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

W, H = 1080, 680
TABS = [
    ("quad", "四视图"),
    ("tree", "工作树"),
    ("matrix", "故障矩阵"),
    ("cockpit", "驾驶舱"),
    ("tools", "工具"),
    ("pets", "数字人"),
]

full = json.loads(FULL.read_text(encoding="utf-8"))
chan = full["channels"]


def payload(name: str):
    """取某通道的完整返回值（原样，含 ok/error 与 data）。"""
    v = (chan.get(name) or {}).get("value")
    if v is None:
        return {"ok": False, "error": "probe 未取到该通道"}
    return v


# 注入 script：形状与 holo_pet_w3/shell/preload.cjs 暴露的 gbtW3 一致
BRIDGE_JS = """
(() => {
  const P = %s;
  const call = (name) => Promise.resolve(P[name] !== undefined ? P[name]
                        : { ok: false, error: "本渲染器未取该通道: " + name });
  window.gbtW3 = {
    readonly: true,
    non_readonly_capability: "summon（只起一个本机窗口：不写文件、不发网络、不 kill 进程）",
    config: () => call("w3:config"),
    state: () => call("w3:state"),
    tasks: () => call("w3:tasks"),
    env: () => call("w3:env"),
    ledger: () => call("w3:ledger"),
    health: () => call("w3:health"),
    matrix: () => call("w3:matrix"),
    mindmap: () => call("w3:mindmap"),
    selfcheck: () => call("w3:selfcheck"),
    introspect: () => call("w3:introspect"),
    tools: () => call("w3:tools"),
    h1: () => call("w3:h1"),
    pets: () => call("w3:pets"),
    summon: () => call("w3:summon"),
    eigenflux: () => call("w3:eigenflux"),
    coverage: () => call("w3:coverage"),
    orphans: () => call("w3:orphans"),
    gene: () => call("w3:gene"),
    onEvent: () => {},
    onStreamState: () => {},
  };
})();
""" % json.dumps({k: payload(k) for k, _ in
                  [("w3:config", 0), ("w3:state", 0), ("w3:tasks", 0), ("w3:env", 0),
                   ("w3:ledger", 0), ("w3:health", 0), ("w3:matrix", 0), ("w3:mindmap", 0),
                   ("w3:selfcheck", 0), ("w3:introspect", 0), ("w3:tools", 0), ("w3:h1", 0),
                   ("w3:pets", 0), ("w3:summon", 0), ("w3:eigenflux", 0),
                   ("w3:coverage", 0), ("w3:orphans", 0), ("w3:gene", 0)]},
                 ensure_ascii=False)

OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
    pg.add_init_script(BRIDGE_JS)
    pg.goto(PAGE.as_uri(), wait_until="load")
    pg.wait_for_timeout(1800)

    # 桥到底接上没有？页面自己有兜底文案"没有接上宿主进程"，这里如实检测
    bridged = pg.evaluate("() => !!(window.gbtW3 && window.gbtW3.readonly)")
    print("gbtW3 桥注入:", "OK" if bridged else "失败")

    for key, label in TABS:
        pg.click(f'.gbt-tab[data-view="{key}"]')
        pg.wait_for_timeout(900)
        # 有的页签要再点一次"刷新"才取数（设计如此：不做后台轮询）。
        # 用 JS 触发而不是鼠标点击：驾驶舱页卡片较高，按钮可能被相邻卡片盖住，
        # 鼠标点击会撞上命中测试（这是渲染探针的取数手段，不是产品路径）。
        for bid in ("btn-tools-refresh", "btn-pets-refresh",
                    "btn-coverage", "btn-orphans", "btn-gene"):
            el = pg.query_selector(f"#{bid}")
            if el and el.is_visible():
                el.evaluate("e => e.click()")
                pg.wait_for_timeout(900)
        f = OUT / f"{key}_{label}.png"
        pg.screenshot(path=str(f))
        # 该页签的可读文本量 —— 用来判"渲染出来是真有内容还是空壳"
        txt = pg.inner_text(f"#view-{key}") if pg.query_selector(f"#view-{key}") else ""
        print("  %-10s %-8s 文本 %5d 字  -> %s" % (key, label, len(txt.strip()), f.name))

    pg.screenshot(path=str(OUT / "全窗口_四视图.png"))
    b.close()

print("\n落盘目录:", OUT.relative_to(ROOT))
