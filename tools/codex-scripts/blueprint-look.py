# -*- coding: utf-8 -*-
"""blueprint-look.py —— 用**她自己的原生视觉**读网页/屏幕，并做**可校准**的点击。

## 为什么必须有这个工具（三条实测，不是理论）

projectaal 的 builder 是 **SPA**，而这台环境里能读它的路只剩一条：

| 路 | 实测结果 |
|---|---|
| `web_fetch` | 只拿到标题（SPA 空壳） |
| Playwriter 新标签页 | **导航后必被关**（对照 `example.com` 同样被关） |
| `read_text`（UIA） | 🔴 **读不到 Chrome 页面正文** —— 给的是桌面/任务栏的 UIA 树（坐标还是负的） |
| `hotkey ctrl+tab` + `focus_window` | 🔴 **切不动 Chrome 标签页**（标题 25 次没变） |
| ✅ `browser op=open` | **确实把标签页带到前台**，且**窗口标题是活的**（开 example.com 后标题真变成 "Example Domain"） |

⇒ **可靠组合 = `op=open` 把页带到前台 → 她的云端视觉读整屏原图。**

## 三个已校准的坑（写死在这里，别重踩）

1. **整屏原图 + 明确提问 = 可靠**；**裁图让她读小字 = 不可靠**
   （实测：把顶部横条读成「macOS 的 Dock」，而这是 Windows —— 纯幻觉）。
2. **她的纵坐标估计有系统性偏移**（实测 +120px：她说 Blueprint y≈495，
   点 495 实际命中 Code(375)）。⇒ **每一次点击都必须回读验证**，不许盲点第二下。
3. **她的读数里同一界面中英并列**（`Preview 预览`），提问时要说明"原文照抄"，别让她翻译。

## 隐私红线（本工具为什么要按区域取字）

`tentacle read_text` 是**整屏 UIA 扫描** —— 实测它把主人 **Telegram 的私信**一起读了进来。
⇒ 本工具**默认只截屏 + 只问她指定的问题**；`--text-region` 才走 UIA，
且**只回落在指定矩形内的块**，**绝不整屏倾倒**。

用法：
    python tools/codex-scripts/blueprint-look.py look                       # 看当前屏
    python tools/codex-scripts/blueprint-look.py look --ask "列出左侧导航每一项"
    python tools/codex-scripts/blueprint-look.py open                       # 把蓝图页带到前台
    python tools/codex-scripts/blueprint-look.py click 120 615 --expect "Blueprint"
    python tools/codex-scripts/blueprint-look.py text-region 0 55 300 1010   # 只取左栏文字
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BUILDER_URL = "https://projectaal.com/builder/1ce4852b-eb26-4a1d-940b-cc6fa0673d19"

# 读界面时的默认提问：逼她**照抄原文**，并点名要那四类东西
DEFAULT_ASK = (
    "这是电脑屏幕截图里的网页应用界面。照抄界面原文回答，不要翻译、不要概括："
    "①左侧导航栏逐项列出，并指出哪一项高亮选中；②主标题；"
    "③主区域从上到下逐条列出（区块名、字段名、按钮文字、表格列名、卡片数字）；"
    "④任何报错、警告、待填、灰色禁用、'未完成/敬请期待/即将上线'字样，原文照抄。"
    "不要描述操作系统任务栏、微信、Telegram 或其它窗口。用中文。"
)


def _rt(cap, payload):
    """走能力位（过门、落审计），拿本体结果。"""
    import gbt_allinone as gbt
    env = gbt.run_task(cap, payload or {})
    r = env
    for _ in range(3):
        if isinstance(r, dict) and isinstance(r.get("result"), dict):
            r = r["result"]
        else:
            break
    return r if isinstance(r, dict) else {}


def _screenshot() -> bytes:
    r = _rt("tentacle", {"action": "see_active_window"})
    b64 = r.get("image_base64") or ""
    if not b64:
        raise SystemExit("截屏失败：%s" % json.dumps(r, ensure_ascii=False)[:200])
    return base64.b64decode(b64)


def _wait_ready(min_bytes: int = 120000, tries: int = 10, gap: float = 2.0):
    """等画面**真的渲染出来**，再动手读/点。

    🔴 为什么必须有它（实测换来的）：`op=open` 会让 **SPA 重载**，
    重载后 9 秒截图**只有 43 KB**（还在白屏/加载），而渲染好的页是 **150–300 KB**。
    ⇒ 用**截图字节数**当"渲染好了没"的判据：便宜、有效、不依赖任何 CSS 选择器
      （这台环境读不到 Chrome 的 DOM，所以只能用像素侧判据）。
    判据 = ① 字节数够大 ② 与上一张相比**基本不再变**（同一量级波动 <2%）。
    """
    last = b""
    for i in range(tries):
        img = _screenshot()
        big = len(img) >= min_bytes
        stable = last and abs(len(img) - len(last)) < max(2000, len(img) // 50)
        if big and stable:
            return img, i + 1, "ready"
        last = img
        time.sleep(gap)
    return last, tries, "timeout(可能仍在加载，读数要打折看)"


def _ask_image(img_bytes: bytes, ask: str) -> dict:
    from gbt_allinone import vision_cap as V
    return V.cloud_recognize(img_bytes, prompt=ask)


def chrome_title() -> str:
    r = _rt("tentacle", {"action": "list_windows"})
    for w in (r.get("windows") or []):
        if "Chrome" in str(w.get("title", "")):
            return str(w["title"])
    return ""


def cmd_open(a):
    r = _rt("browser", {"op": "open", "url": a.url})
    time.sleep(a.wait)
    print(json.dumps({"ok": r.get("ok"), "backend": r.get("backend"),
                      "title": chrome_title()}, ensure_ascii=False))


def cmd_look(a):
    img = _screenshot()
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(img)
        print("证据图: %s (%d 字节)" % (p, len(img)), file=sys.stderr)
    if a.region:
        from PIL import Image
        x, y, w, h = a.region
        im = Image.open(io.BytesIO(img)).convert("RGB")
        im = im.crop((x, y, x + w, y + h))
        if a.zoom != 1:
            im = im.resize((im.width * a.zoom, im.height * a.zoom), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        img = buf.getvalue()
        print("送图尺寸: %s" % (im.size,), file=sys.stderr)
    d = _ask_image(img, a.ask or DEFAULT_ASK)
    print(json.dumps({"ok": d.get("ok"), "engine": d.get("model"),
                      "title": chrome_title(),
                      "description": d.get("description") or d.get("error")},
                     ensure_ascii=False, indent=1))


def cmd_peek(a):
    """**一个进程内** open → 等 → look。

    为什么必须合成一条（2026-09-25 实测踩到）：
      `open` 与 `look` 分成两次调用时，中间**主人会切回 DSH 面板标签页**
      ⇒ 第二次 `look` 截到的是面板，不是目标页（实测：裁图裁到面板、她读出的是 Python 代码）。
      ⇒ 想稳定读到目标页，**open 与 look 必须在同一进程里连着做**。
    """
    r = _rt("browser", {"op": "open", "url": a.url})
    time.sleep(a.wait)
 # 必须紧接着点（同进程内）：`op=open` 同一个 URL 会让 **SPA 重载**，
    #    面板状态被重置（实测：重开后高亮回到 Preview，Code/文件树全丢）
    #    ⇒ open → 点导航 → 读，三步必须在同一个进程里连着做。
    if getattr(a, "click", None):
        for cx, cy in a.click:
            _rt("tentacle", {"action": "click", "args": [cx, cy]})
            time.sleep(a.click_wait)
    title = chrome_title()
    img = _screenshot()
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(img)
        print("证据图: %s (%d 字节)" % (p, len(img)), file=sys.stderr)
    if a.region:
        from PIL import Image
        x, y, w, h = a.region
        im = Image.open(io.BytesIO(img)).convert("RGB")
        im = im.crop((x, y, x + w, y + h))
        if a.zoom != 1:
            im = im.resize((im.width * a.zoom, im.height * a.zoom), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        img = buf.getvalue()
        print("送图尺寸: %s" % (im.size,), file=sys.stderr)
    d = _ask_image(img, a.ask or DEFAULT_ASK)
    print(json.dumps({"ok": d.get("ok"), "opened": r.get("ok"), "engine": d.get("model"),
                      "title": title,
                      "description": d.get("description") or d.get("error")},
                     ensure_ascii=False, indent=1))


def cmd_click(a):
    """点一次 —— **必带验证**（因为她的坐标有系统性偏移）。"""
    before = chrome_title()
    r = _rt("tentacle", {"action": "click", "args": [a.x, a.y]})
    if not r.get("ok"):
        print(json.dumps({"ok": False, "error": r.get("error")}, ensure_ascii=False))
        return
    time.sleep(a.wait)
    img = _screenshot()
    d = _ask_image(img, "这是网页应用截图。只回答一句：左侧导航栏里**哪一项是高亮选中**？照抄它的文字。")
    got = str(d.get("description") or "").strip()
    print(json.dumps({"clicked": [a.x, a.y], "expect": a.expect,
                      "title_before": before, "title_after": chrome_title(),
                      "highlighted": got[:120],
                      "hit": (a.expect.lower() in got.lower()) if a.expect else None},
                     ensure_ascii=False, indent=1))


SWEEP_ASK = (
    "这是网页应用截图。**严格照抄界面原文**：不要翻译、不要概括、不要只挑重点，有就全列。"
    "【A】左侧导航栏里**哪一项是高亮选中**（照抄它的文字；若看不到左侧栏，就写「看不到左侧栏」）。"
    "【B】主区域从上到下**逐条**列出：区块名、字段名、按钮文字、输入框里的灰色提示文字、"
    "表格列名、卡片的数字与百分比。"
    "【C】把界面上**所有**报错、警告、红色/黄色/绿色提示条、灰色禁用项，以及"
    "「未完成 / 敬请期待 / 即将上线 / TODO / coming soon / 加载中 / 0 条 / 暂无数据」"
    "这类字样，**逐条原文照抄**；一条都没有就写「无」。"
    "【D】**疑是故障**：任何看起来不对的地方 —— 大片空白、错位、重叠、中英混杂、"
    "文字被截断、按钮像没响应、数字不合理、重复条目、占位符没替换、"
    "图标缺失、边框缺失 —— 逐条列出它在哪、长什么样。宁可多报，不许放过。"
    "不要描述操作系统任务栏、微信、Telegram 等其它窗口。用中文。"
)


def cmd_sweep(a):
    """**无死角扫描**：把一列 y 坐标逐个点过去，每一位读一次，**全部落账本**。

    为什么这样设计（对应主人的要求「全方位无死角、疑是故障也不能放过」）：
      · **不靠记忆**：每一位的读数当场写进 `--ledger`（jsonl，逐条追加，可复核）。
      · **不靠猜坐标**：每个位置点完都读一次「哪一项高亮」，所以映射是**跑出来的**。
      · **渲染判据**：每次点击/导航后先过 `_wait_ready()`，不拿加载中的白屏当读数。
    """
    out = Path(a.ledger)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = _rt("browser", {"op": "open", "url": a.url})
    img, tries, state = _wait_ready(tries=a.tries)
    print("open=%s · 渲染=%s（第 %d 次截图 · %d 字节）"
          % (r.get("ok"), state, tries, len(img)), file=sys.stderr)

    ys = ([int(v) for v in a.ys.split(",")] if a.ys
          else list(range(a.start, a.stop + 1, a.step)))
    n = 0
    for y in ys:
        _rt("tentacle", {"action": "click", "args": [a.x, y]})
        time.sleep(a.click_wait)
        img, tries, state = _wait_ready(tries=a.tries)
        if a.out:
            p = Path(a.out) / ("y%04d.png" % y)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(img)
        d = _ask_image(img, a.ask or SWEEP_ASK)
        desc = str(d.get("description") or d.get("error") or "")
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "x": a.x, "y": y,
               "shot_bytes": len(img), "render": state, "engine": d.get("model"),
               "title": chrome_title(), "reading": desc}
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        n += 1
        print("  y=%-5d %-14s %7dB  %s"
              % (y, state.split("(")[0], len(img), " ".join(desc.split())[:96]))
    print("\n账本: %s（本次追加 %d 条）" % (out, n))


def cmd_text_region(a):
    """**只取指定矩形内的 UIA 文字块** —— 绝不整屏倾倒（隐私红线）。"""
    r = _rt("tentacle", {"action": "read_text"})
    x0, y0, w, h = a.rect
    x1, y1 = x0 + w, y0 + h
    keep = []
    for b in (r.get("text_blocks") or []):
        bx, by = b.get("x", -99999), b.get("y", -99999)
        t = str(b.get("text", "")).strip()
        if t and x0 <= bx <= x1 and y0 <= by <= y1:
            keep.append({"x": bx, "y": by, "type": b.get("type"), "text": t})
    keep.sort(key=lambda z: (z["y"], z["x"]))
    print(json.dumps({"rect": a.rect, "count": len(keep), "blocks": keep},
                     ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description="用她的原生视觉读网页/屏幕 + 可校准点击")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("open", help="把页面带到前台（op=open 是免门的，且会聚焦）")
    p.add_argument("--url", default=BUILDER_URL)
    p.add_argument("--wait", type=float, default=9.0)
    p.set_defaults(fn=cmd_open)

    p = sub.add_parser("look", help="截当前屏并问她")
    p.add_argument("--ask", default=None)
    p.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    p.add_argument("--zoom", type=int, default=1)
    p.add_argument("--out", default=None, help="把截图存到这个路径（证据）")
    p.set_defaults(fn=cmd_look)

    p = sub.add_parser("peek", help="**一个进程内** open→(可选点击)→look（推荐）")
    p.add_argument("--url", default=BUILDER_URL)
    p.add_argument("--wait", type=float, default=9.0)
    p.add_argument("--click", type=int, nargs=2, action="append", metavar=("X", "Y"),
                   help="open 之后紧接着点一下；可重复给多次（按顺序点）")
    p.add_argument("--click-wait", type=float, default=4.0)
    p.add_argument("--ask", default=None)
    p.add_argument("--region", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    p.add_argument("--zoom", type=int, default=1)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_peek)

    p = sub.add_parser("click", help="校准点击（点完自动回读验证）")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--expect", default=None, help="期望命中的导航项文字")
    p.add_argument("--wait", type=float, default=4.0)
    p.set_defaults(fn=cmd_click)

    p = sub.add_parser("sweep", help="**无死角扫描**：逐个位置点过去，每位读一次，全落账本")
    p.add_argument("--url", default=BUILDER_URL)
    p.add_argument("--x", type=int, default=120, help="点击的 x（左侧栏用小 x）")
    p.add_argument("--ys", default=None, help="显式 y 列表，逗号分隔（优先于 start/stop/step）")
    p.add_argument("--start", type=int, default=300)
    p.add_argument("--stop", type=int, default=960)
    p.add_argument("--step", type=int, default=40)
    p.add_argument("--click-wait", type=float, default=3.0)
    p.add_argument("--tries", type=int, default=6, help="渲染判据最多重截几次")
    p.add_argument("--ask", default=None)
    p.add_argument("--out", default=None, help="每位再存一张截图到这个目录（证据）")
    p.add_argument("--ledger", default="output/blueprint-audit/sweep.jsonl")
    p.set_defaults(fn=cmd_sweep)

    p = sub.add_parser("text-region", help="只取指定矩形内的 UIA 文字（隐私安全）")
    p.add_argument("rect", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    p.set_defaults(fn=cmd_text_region)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    if os.name == "nt":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    main()
