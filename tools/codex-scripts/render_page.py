# -*- coding: utf-8 -*-
"""页面渲染取证器（2026-09-23 起）—— 把本地 HTML 真渲染成 PNG，**给模型自己看**。

## 为什么要这一件

「3D 立体视觉感」「视觉冲击」这类要求，**文字描述证明不了**。本仓过去吃过这个亏：
反复"我觉得好看"、反复返工，因为没有一次是把**眼睛**放上去的。

⇒ 这一件把"好看不好看"变成一条能重复的取证链：
   `本地 HTML → 真浏览器渲染 → PNG → 看图`。
   改一次 CSS，渲一张，看一次 —— 一轮几秒，不再靠猜。

## 两条硬纪律

1. **禁网**：所有非 `file:` 请求**一律拦掉**，并**逐条记下来**（`blocked`）。
   ⇒ "这页不依赖外网"从此是**实测读数**，不是 grep `http://` 的推断。
   谁的页面偷引了 CDN 字体/图标，这里当场现形。
2. **可复现**：CSS 动画默认不定帧，截图落在哪一帧看运气。
   `--freeze <秒>` 把动画**定在同一帧**（用负 `animation-delay` + `paused`），
   于是"上一张和这一张"能逐像素比。

## 用法

    py -3.14 tools/codex-scripts/render_page.py holo_pet_w3/code-deck/index.html
    py -3.14 tools/codex-scripts/render_page.py <页> --out "%TEMP%\\x.png" --w 1200 --h 860
    py -3.14 tools/codex-scripts/render_page.py <页> --freeze 4 --no-js

用现成的 Edge/Chrome（`channel=msedge`/`chrome`）—— **不下载任何浏览器**（装包属闸二）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
OUTDIR = Path(__import__("os").environ.get("TEMP", "/tmp")) / "gbt-render"


def main() -> int:
    ap = argparse.ArgumentParser(description="把本地页面渲染成 PNG（禁网 + 可定帧）")
    ap.add_argument("page", help="本地 HTML 路径")
    ap.add_argument("--out", default="", help="PNG 输出路径（默认 %%TEMP%%\\gbt-render\\<名>.png）")
    ap.add_argument("--w", type=int, default=1280)
    ap.add_argument("--h", type=int, default=900)
    ap.add_argument("--freeze", type=float, default=None,
                    help="把 CSS 动画定在第 N 秒那一帧（同一 N ⇒ 同一张图）")
    ap.add_argument("--wait", type=float, default=0.7, help="加载后再等几秒（默认 0.7）")
    ap.add_argument("--no-js", action="store_true", help="禁用脚本（快照页本就该无脚本）")
    ap.add_argument("--channel", default="msedge", help="msedge / chrome（不下载浏览器）")
    ap.add_argument("--full", action="store_true", help="整页截图（默认只截视口）")
    ap.add_argument("--webgl", action="store_true",
                    help="开软件 WebGL（three.js 那类页面必须开，否则画布是空的）")
    a = ap.parse_args()

    page_path = Path(a.page)
    if not page_path.is_absolute():
        page_path = (ROOT / a.page).resolve()
    if not page_path.is_file():
        print("🔴 页面不存在：%s" % page_path)
        return 2

    out = Path(a.out) if a.out else (OUTDIR / (page_path.parent.name + "-" + page_path.stem + ".png"))
    out.parent.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright
    blocked = []
    # 软件 WebGL：headless 里默认没有 GPU，three.js 那类页面会**静默画成空白**
    # （"空白帧 ≠ 没问题" —— 正是本仓反复强调的那条）。这两个开关是 Chromium 现在的正解。
    args = ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"] if a.webgl else []
    with sync_playwright() as p:
        b = p.chromium.launch(channel=a.channel, args=args)
        ctx = b.new_context(viewport={"width": a.w, "height": a.h},
                            device_scale_factor=2, java_script_enabled=not a.no_js)
        page = ctx.new_page()
        # ── 禁网：只放行 file:，其余一律拦掉并记名 ──

        def _route(route):
            u = route.request.url
            if u.startswith("file:") or u.startswith("data:") or u.startswith("blob:"):
                route.continue_()
            else:
                blocked.append(u[:120])
                route.abort()
        page.route("**/*", _route)
        errors = []
        page.on("pageerror", lambda e: errors.append(
            (getattr(e, "stack", None) or str(e))[:400]))
        # 🔴 控制台与**失败请求**都要记：模块脚本被 CORS 挡掉时**不报 pageerror**，
        #    只在 console 里留一行；不记它就会得到"零错误 + 空白画布"这种**假绿**。
        console = []
        page.on("console", lambda m: console.append("%s: %s" % (m.type, m.text[:200]))
                if m.type in ("error", "warning") else None)
        failed = []
        page.on("requestfailed",
                lambda r: failed.append("%s :: %s" % (r.url[:110], (r.failure or "")[:60])))
        page.goto(page_path.as_uri(), wait_until="load")
        frozen, freeze_why = False, ""
        if a.freeze is not None:
            try:
                page.add_style_tag(content=(
                    "*{animation-delay:-%ss !important;animation-play-state:paused !important;"
                    "transition:none !important}" % a.freeze))
                frozen = True
            except Exception as e:                                  # noqa: BLE001
                # 🔴 页面自己的 CSP 把内联样式挡了（`style-src 'self'`）—— 这是**page 做对了**，
                # 不是渲染器坏了。如实报"没定成帧"，不许假装定了（不定帧 ⇒ 每张图落哪帧看运气）。
                freeze_why = ("被页面 CSP 挡掉（`style-src 'self'` 不许内联样式）"
                              if "Content Security Policy" in str(e) else str(e)[:90])
        page.wait_for_timeout(int(a.wait * 1000))
        page.screenshot(path=str(out), full_page=a.full)
        b.close()

    print("=" * 74)
    print("页面渲染取证")
    print("=" * 74)
    print("  页面 %s" % page_path)
    print("  视口 %dx%d @2x ｜ 脚本 %s ｜ 定帧 %s"
          % (a.w, a.h, "关" if a.no_js else "开",
             ("第 %ss 帧" % a.freeze) if frozen else
             ("**没定成**：%s ⇒ 落哪帧看运气" % freeze_why) if a.freeze is not None
             else "不定帧（落哪帧看运气）"))
    print("  PNG  %s（%.1f KB）" % (out, out.stat().st_size / 1024.0))
    if blocked:
        print("  🔴 **有 %d 条出网请求被拦掉**（这页不是自包含的）：" % len(blocked))
        for u in blocked[:8]:
            print("      · %s" % u)
    else:
        print("  ✅ 零出网请求（实测拦获 0 条）—— 断网照常渲染")
    if errors:
        print("  ⚠️ 页面脚本报了 %d 条错：" % len(errors))
        for e in errors[:5]:
            print("      · %s" % e)
    if console:
        print("  ⚠️ 控制台 %d 条（**模块被 CORS 挡掉只在这里现形**）：" % len(console))
        for c in console[:6]:
            print("      · %s" % c)
    if failed:
        print("  🔴 **%d 个请求失败**（页面拿不到它要的东西）：" % len(failed))
        for f in failed[:6]:
            print("      · %s" % f)
    return 1 if (blocked or errors or failed or console) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
