# gbt-capability: vision_print
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""视觉打印 —— 看到的东西 → 打成代码（自包含 HTML）→ 真渲染 → 与所见帧比。

## 为什么有这一位（主人令 2026-10-13）

主人问：「她视觉打印能力有没有丢 —— 就是看到的东西都可以原样以代码打印并渲染成看到的样子」。
本轮现读的结论是：**这条链从未在册**，不是丢了：

| 面 | 现读 | 缺什么 |
|---|---|---|
| 她的「看」 | tentacle 视觉 12 法（see/screenshot/vision_diff…）+ `vision` / `vlx_flow` / `vision_grounding` | 只出**读数与指纹**，不吐代码 |
| 她的「渲」 | `ui_render`（8 组件白名单 · 零脚本零外链） | 是**报告页**渲染器，按设计不能还原任意界面 |
| 框架自述 | `zimage_rewash` desc：「**无图像理解能力位**：vision 是屏幕视觉、云链 ask() 是纯文本」 | 「看图→出码」这格是空的 |
| 反向那一半 | `render_page.py`（真 Chromium 渲成 PNG 给自己看） | 那是「码→像」，不是「像→码」 |

本件把缺的那条**正向链**补齐，并把「原样」从感觉变成**可复核的数字**。

## 五段链（每段都要真读数；缺哪段就点哪段，不假装）

   ① see     取帧：原生眼（`tentacle/omni_core._screen_capture` = dxcam→mss→pyautogui），或直接喂图
   ② print   代码落地：**码由调用方给**（她是文本模型，代码由她写）；
             要模型看图回码走 `op=ask_model`（缺依赖如实报 needs_dependency，绝不编一段假码）
   ③ render  真渲染：真 Chromium/Edge 载入这份 HTML → PNG。纪律**同**
             `tools/codex-scripts/render_page.py`：只放行 file:/data:/blob:，其余**逐条记拦获**；
             pageerror / console(error|warning) / requestfailed 三条都记
   ④ diff    与所见帧比：**五个现算数** —— aHash 汉明距离 · 逐块变化率（网格哈希）· 平均亮度差
             · **变化像素占比** · **最大块平均差**（后两个是局部敏感项，专抓小面积真变：
             首版只有前三个时，改一处文字颜色被判成「同款」，那是尺子瞎不是"像"）
             （指纹尺子**只许一把**：复用 `tentacle/vision_bus`，不另写第二份指纹算法）
   ⑤ judge   判据成**档位**（同款 / 接近 / 不像 / **无法判定**），每条带出处；判定只用非 LLM 数字

## 🔴 四条硬规矩

1. **不编码**：`print` 只接受**真代码**（判据：能载入 + 产出 PNG 非空）；`ask_model` 抽不出代码块
   就如实报 `code_looks_like_code=false`，**不许把散文当代码去渲**。
2. **不假相似度**：三个数全部现算；`vision_bus` 不在 ⇒ 报 `needs_dependency`（fail-closed）。
3. **结果落文件 + 双账**：每跑一次落 `store/vision_print/ledger.jsonl`（只追加）+ 框架审计一条；
   产物落 `outputs/vision-print/`。
4. 🔴 **假绿闸（fail-closed）**：四种情形一律把结论降成 **`无法判定`**，**不许报「同款」**——
   ① 所见帧**近空白**（灰度标准差 < 2：纯色画面拿什么码去比都容易"像"，那是没内容）
   ② 所见帧与渲回来的图**逐字节同一张**（自己跟自己比 ⇒ 必然"同款"，与还原无关）
   ③ **渲得不可信**（页面自报错 / 请求失败）
   ④ **渲时有出网请求被拦**（本件禁网兜底 ⇒ 这张图不是真实浏览器会显示的样子）。
   另外 `see` 会如实标 **`frame_from`**（`screen` / `file`）：用文件当"所见帧"时，这条链只证明
   「码→图」与「图→图」两条腿，**不证明她真看过屏幕** —— 这条边界写进返回值，不靠人记。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "outputs" / "vision-print"
_GRID = 4

# 判据档位（**人定、写死在这里、可复核可改**）。
# 字段序：(名字, aHash 距离上限, 块变化率上限, 变化像素占比上限, 最大块平均差上限)
#
# 🔴 为什么要这四个数、而不是只用一个总 aHash（2026-10-13 本件自测抓到的假绿）：
#   首版只用「整图 aHash 64 位距离 + 4×4 块变化率 + 平均亮度差」，实测**只改一处文字颜色**
#   （`#00E5FF`→`#FF6B6B`）时，aHash 距离 = **0**、块变化率 = **0**、平均亮度差 = **0.0**
#   ⇒ 判成「同款」。那不是"像"，那是**尺子看不见**：整图缩到 16×16 后，一行字的颜色
#   在均值里被抹平了；平均值又被整页面积摊薄。
#   ⇒ 补两个**局部敏感**的现算数：`变化像素占比`（逐像素容差 tol 之外的比例）与
#     `最大块平均差`（4×4 里最差那一块的平均像素差）。前者抓"小面积真变"，后者抓"局部塌陷"。
_PIXEL_TOL = 8
_BANDS = (
    ("同款", 4, 0.125, 0.002, 6.0),
    ("接近", 10, 0.375, 0.02, 20.0),
)

# 第四档：**无法判定**（fail-closed）。不是"没算出来"，是"算出来了但**不许**当结论"。
# 触发它的三种情形（每一条都是当场抓到的假绿通道，见 vaults/vision_print/记忆.md）：
#   ① 所见帧近空白（灰度标准差 < _BLANK_STD）：纯色画面拿什么码去比都容易"像"，那是**没内容**；
#   ② 所见帧与渲回来的图**逐字节同一张**：自己跟自己比 ⇒ 必然"同款"，与"还原"无关；
#   ③ 渲得不可信（页面自报错 / 请求失败）：图本身就不可信，拿它下结论就是假绿。
#   ④ 渲的时候**有出网请求被拦**：那张图不是真实浏览器的样子（本件禁网兜底），拿它下结论同样是假绿。
_VERDICT_UNKNOWN = "无法判定"
_BLANK_STD = 2.0

_MODEL_PROMPT = (
    "看这张图，把它**原样**还原成一份**自包含**的单文件 HTML（内联 CSS，零脚本、零外链、零图片外链）。"
    "只回一个 ```html 代码块，不要解释。尺寸按图的宽高比。"
)

_FENCE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n(.*?)```", re.S)


# ── 落点 / 双账 ────────────────────────────────────────────────────────────
def _safe(name) -> str:
    s = "".join(ch for ch in str(name or "") if ch.isalnum() or ch in "-_")
    return s[:40] or "vp"


def _store_dir() -> Path:
    d = os.environ.get("GBT_STORE_DIR")
    return Path(d) if d else (_ROOT / "gbt_allinone" / "store")


def _out_dir() -> Path:
    """产物目录。默认 `outputs/vision-print/`；`GBT_VISION_PRINT_OUT` 可指到隔离目录
    （判据件要用隔离目录跑，别把产物区当试验田 —— 与仓里"测试走隔离 store"同一条纪律）。"""
    d = os.environ.get("GBT_VISION_PRINT_OUT")
    p = Path(d) if d else _OUT
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ledger_path() -> Path:
    p = _store_dir() / "vision_print"
    p.mkdir(parents=True, exist_ok=True)
    return p / "ledger.jsonl"


def _record(row: dict) -> str:
    f = _ledger_path()
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(f)


def _audit(event: str, meta: dict) -> None:
    import importlib
    for mp in ("gbt_allinone.store", "store"):
        try:
            importlib.import_module(mp).audit(event, meta)
            return
        except Exception:                                     # noqa: BLE001
            continue


def _rel(p) -> str:
    try:
        return str(Path(p).relative_to(_ROOT))
    except Exception:                                        # noqa: BLE001
        return str(p)


# ── 依赖注入（api 分派分支把「眼」与「尺子」真接进来；直跑时按模块名兜底）────
def _bus(bus=None):
    if bus is not None:
        return bus
    import importlib
    for mp in ("gbt_allinone.tentacle.vision_bus", "vision_bus"):
        try:
            return importlib.import_module(mp)
        except Exception:                                    # noqa: BLE001
            continue
    return None


def _cap_mod(cap=None):
    if cap is not None:
        return cap
    import importlib
    for mp in ("gbt_allinone.vision_cap", "vision_cap"):
        try:
            return importlib.import_module(mp)
        except Exception:                                    # noqa: BLE001
            continue
    return None


def _eye():
    from ..tentacle import omni_core as _oc
    return _oc


# ── 图的小工具 ────────────────────────────────────────────────────────────
def _as_b64(value) -> str:
    """路径 / base64 / data URL / bytes → base64 串（读不出就回原样，让下游如实报错）。"""
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode()
    s = str(value or "").strip()
    if not s:
        return ""
    if s.startswith("data:"):
        return s.split(",", 1)[-1]
    try:
        p = Path(s)
        if p.is_file():
            return base64.b64encode(p.read_bytes()).decode()
    except Exception:                                        # noqa: BLE001
        pass
    return s


def _open(b64: str):
    import io as _io
    from PIL import Image
    return Image.open(_io.BytesIO(base64.b64decode(b64)))


def _fingerprint(b64: str):
    m = _bus(None)
    if m is None or not hasattr(m, "_ahash"):
        return None
    try:
        return m._ahash(b64)[:16]
    except Exception:                                        # noqa: BLE001
        return None


def _sha16(data) -> str:
    """逐字节指纹（用来抓「自己跟自己比」）。"""
    if isinstance(data, str):
        data = base64.b64decode(data)
    return hashlib.sha256(bytes(data)).hexdigest()[:16]


def _frame_info(b64: str) -> dict:
    """帧的**信息量**读数：灰度标准差。纯色/近空白 ⇒ std≈0 ⇒ 这张帧不该拿去判「像不像」。"""
    import numpy as np
    g = _open(b64).convert("L")
    a = np.asarray(g, dtype=np.float32)
    return {"size": list(g.size), "std_l": round(float(a.std()), 2),
            "mean_l": round(float(a.mean()), 2)}


def _crop_b64(b64: str, region: dict) -> tuple:
    """自己把 region **真裁**出来（回 (新 b64, [w,h])）。越界/字段非法 ⇒ 抛，由调用方 fail-closed。

    🔴 为什么必须自己裁（2026-10-13 实测）：`tentacle/omni_core._screen_capture` 的 **dxcam 分支
    完全无视 `region`** —— 我要 320×200，它回 **1920×1080 整屏，而且不报错**。
    静默偏差是假绿的亲戚：调用方以为拿到"那一块"，其实拿到的是整屏，后面所有判断都建在错的输入上。
    """
    import io as _io
    img = _open(b64)
    try:
        x, y = int(region.get("x", 0)), int(region.get("y", 0))
        w, h = int(region.get("w", 0)), int(region.get("h", 0))
    except Exception as e:                                   # noqa: BLE001
        raise ValueError("region 的 x/y/w/h 要是整数：%s" % str(e)[:80])
    if w <= 0 or h <= 0:
        raise ValueError("region 的 w/h 必须 > 0（收到 w=%s h=%s）" % (w, h))
    W, H = img.size
    if x < 0 or y < 0 or x + w > W or y + h > H:
        raise ValueError("region 越界：要 (%d,%d,%d,%d)，帧只有 %dx%d" % (x, y, w, h, W, H))
    crop = img.crop((x, y, x + w, y + h)).convert("RGB")
    buf = _io.BytesIO()
    crop.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode(), [crop.size[0], crop.size[1]]


def _mean_abs_l(a_b64: str, b_b64: str) -> float:
    from PIL import Image
    import numpy as np
    a = _open(a_b64).convert("L")
    b = _open(b_b64).convert("L").resize(a.size, Image.LANCZOS)
    x = np.asarray(a, dtype=np.int16)
    y = np.asarray(b, dtype=np.int16)
    return round(float(np.abs(x - y).mean()), 2)


def _pixel_stats(a_b64: str, b_b64: str, grid: int = _GRID, tol: int = _PIXEL_TOL):
    """两个**局部敏感**的现算数：(变化像素占比, 最大块平均差)。

    · 变化像素占比 = 逐像素 RGB 最大通道差 > tol 的像素比例（小面积真变也抓得到）；
    · 最大块平均差 = grid×grid 块里最差那一块的平均像素差（局部塌陷看得到）。
    """
    from PIL import Image
    import numpy as np
    a = _open(a_b64).convert("RGB")
    b = _open(b_b64).convert("RGB").resize(a.size, Image.LANCZOS)
    d = np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).max(axis=2)
    changed = float((d > int(tol)).mean())
    h, w = d.shape
    worst = 0.0
    for r in range(int(grid)):
        for c in range(int(grid)):
            blk = d[r * h // grid:(r + 1) * h // grid, c * w // grid:(c + 1) * w // grid]
            if blk.size:
                worst = max(worst, float(blk.mean()))
    return round(changed, 5), round(worst, 2)


def _extract_code(txt: str):
    """从模型回复里抽代码：抽得出回 (code, True)，抽不出回 ("", False)。"""
    t = str(txt or "")
    blocks = [b.strip() for b in _FENCE.findall(t) if b.strip()]
    for b in blocks:
        low = b.lower()
        if low.startswith("<!doctype") or low.startswith("<html") or "<body" in low or "<div" in low:
            return b, True
    if blocks:
        return blocks[0], True
    s = t.strip()
    low = s.lower()
    if low.startswith("<!doctype") or low.startswith("<html"):
        return s, True
    return "", False


def _quality(path, ref_w: int | None = None) -> dict:
    """成品读数（**调优前后各算一遍**，用来证明"真的更清楚了"）：
    锐度 = 边缘图方差 · 对比 = 灰度标准差 · 亮度 = 灰度均值 · 尺寸。

    🔴 **必须在同一像素网格上比**：放大一定会让"原始锐度读数"变大（尺寸变了），
    拿不同尺寸的两个数直接比 = 尺子坏掉（本仓"某个数看着不可能就是查错信号"那条）。
    所以 `ref_w` 给定后先把图缩到同一基准宽再算 —— 比的是**同尺寸下的清晰度**。
    """
    from PIL import Image, ImageFilter
    import numpy as np
    im = Image.open(path)
    size = list(im.size)
    g = im.convert("L")
    if ref_w and int(ref_w) > 0 and size[0] != int(ref_w):
        h = max(1, round(int(ref_w) * size[1] / max(size[0], 1)))
        g = g.resize((int(ref_w), h), Image.LANCZOS)
    a = np.asarray(g, dtype=np.float32)
    edge = np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    return {"size": size, "sharp": round(float(edge.var()), 3),
            "contrast": round(float(a.std()), 3), "brightness": round(float(a.mean()), 3),
            "ref_w": int(ref_w) if ref_w else size[0]}


def _call_cap(kind: str, payload: dict) -> dict:
    """调**既有能力位** —— 一律走**唯一门** `run_task`（不直连别人的模块函数、不绕门）。"""
    import sys as _sys
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    import gbt_allinone as _g
    r = _g.run_task(kind, payload)
    res = None
    if isinstance(r.get("gbt_result"), dict):
        res = (r["gbt_result"] or {}).get("result")
    if res is None and isinstance(r.get("result"), dict):
        res = r.get("result")
    return {"status": r.get("status"), "denied": bool(r.get("denied")),
            "missing_scopes": r.get("missing_scopes"), "result": res or {}}


# ── ① 取帧 ────────────────────────────────────────────────────────────────
def see(image=None, region=None, name="shot", **_kw) -> dict:
    """取一帧（原生眼）→ 落 PNG + 感知指纹。返回里的 `frame` 就是「所见帧」。"""
    nm = _safe(name)
    out_dir = _out_dir()
    engine, size, frame_from = "file", None, "file"
    if image:
        b64 = _as_b64(image)
        if not b64:
            return {"ok": False, "op": "see", "fail_closed": True,
                    "error": "给了 image 但读不出（路径与 base64 都不行）"}
        try:
            size = list(_open(b64).size)
        except Exception as e:                               # noqa: BLE001
            return {"ok": False, "op": "see", "fail_closed": True,
                    "error": "给的图解不开：%s: %s" % (type(e).__name__, str(e)[:120])}
    else:
        frame_from = "screen"
        try:
            cap = _eye()._screen_capture(region=region, fmt="png", incremental=False)
        except Exception as e:                               # noqa: BLE001（CaptureUnavailable 同族）
            return {"ok": False, "op": "see", "unavailable": True,
                    "rule": "vision_print_cannot_capture", "missing": ["display", "frame_source"],
                    "why": "%s: %s" % (type(e).__name__, str(e)[:180]),
                    "note": "取帧是**眼**的事；这里如实报做不了，不拿空白帧冒充"}
        b64 = str((cap or {}).get("image_base64") or "")
        if not b64:
            return {"ok": False, "op": "see", "unavailable": True,
                    "error": "取帧返回里没有 image_base64（形状异常）"}
        engine = cap.get("engine")
        size = cap.get("size")
    # 🔴 region 必须**真裁**（见 `_crop_b64` 的实测教训）；裁不了就 fail-closed，不许静默给整屏。
    region_applied = False
    if region:
        try:
            b64, size = _crop_b64(b64, region)
            region_applied = True
        except Exception as e:                               # noqa: BLE001
            return {"ok": False, "op": "see", "fail_closed": True,
                    "error": "region 用不了（越界/字段非法）：%s" % str(e)[:160],
                    "_口径": "region 裁不了宁可拒，也不许把整屏当成「那一块」交出去"}
    frame = out_dir / (nm + ".src.png")
    frame.write_bytes(base64.b64decode(b64))
    fp = _fingerprint(b64)
    info = _frame_info(b64)
    out = {"ok": True, "op": "see", "frame": _rel(frame), "size": size or info["size"],
           "engine": engine, "frame_from": frame_from, "bytes": frame.stat().st_size,
           "fingerprint": fp, "sha16": _sha16(b64),
           "std_l": info["std_l"], "mean_l": info["mean_l"], "blank": info["std_l"] < _BLANK_STD,
           "region": region, "region_applied": region_applied,
           "_口径": "这是「所见帧」—— 后面 diff 的基准"}
    warns = []
    if fp is None:
        warns.append("vision_bus 不在 ⇒ 指纹缺席（diff 会 fail-closed，不编一个）")
    if out["blank"]:
        out["frame_suspect"] = True
        warns.append("所见帧**近空白**（灰度标准差 %.2f < %.1f）⇒ 这张帧没有信息量，"
                     "后面**不许**拿它判「同款」（会得到假绿）" % (info["std_l"], _BLANK_STD))
    if frame_from == "file":
        warns.append("所见帧来自**文件**（不是原生眼取屏）⇒ 这条链只证明「码→图」与「图→图」两条腿，"
                     "**不证明她真看过屏幕**")
    if warns:
        out["warnings"] = warns
    return out


# ── ③ 真渲染 ──────────────────────────────────────────────────────────────
def _render(page: Path, out_png: Path, w: int = 1280, h: int = 900, wait: float = 0.7) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "status": "needs_dependency", "missing": ["playwright"],
                "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    last = ""
    for channel in ("msedge", "chrome", None):
        blocked: list = []
        errors: list = []
        console: list = []
        failed: list = []
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch(**({"channel": channel} if channel else {}))
                ctx = b.new_context(viewport={"width": int(w), "height": int(h)},
                                    device_scale_factor=1)
                pg = ctx.new_page()

                def _route(route):
                    u = route.request.url
                    if u.startswith(("file:", "data:", "blob:")):
                        route.continue_()
                    else:
                        blocked.append(u[:120])
                        route.abort()

                pg.route("**/*", _route)
                pg.on("pageerror", lambda e: errors.append((getattr(e, "stack", None) or str(e))[:300]))
                pg.on("console", lambda m: console.append("%s: %s" % (m.type, m.text[:160]))
                      if m.type in ("error", "warning") else None)
                pg.on("requestfailed", lambda r: failed.append(
                    "%s :: %s" % (r.url[:100], (r.failure or "")[:50])))
                pg.goto(page.as_uri(), wait_until="load")
                pg.wait_for_timeout(int(float(wait) * 1000))
                pg.screenshot(path=str(out_png))
                b.close()
            if not out_png.is_file() or out_png.stat().st_size == 0:
                return {"ok": False, "status": "render_failed", "error": "截图产物为空"}
            return {"ok": True, "engine": channel or "bundled-chromium", "blocked": blocked,
                    "errors": errors, "console": console, "failed": failed,
                    "zero_outbound": not blocked, "png_bytes": out_png.stat().st_size}
        except Exception as e:                               # noqa: BLE001
            last = "%s: %s: %s" % (channel or "bundled", type(e).__name__, str(e)[:150])
    return {"ok": False, "status": "render_failed", "error": last,
            "hint": "本机要有 Edge 或 Chrome（口径同 render_page.py：**不下载浏览器**）"}


# ── ② 代码落地 + 渲 ───────────────────────────────────────────────────────
def print_code(code=None, src=None, name="print", width=1280, height=900, wait=0.7, **_kw) -> dict:
    """把**真代码**落成自包含页 → 真渲染成 PNG。没有码就如实拒（fail-closed）。"""
    text = code if isinstance(code, str) and code.strip() else ""
    if not text and src:
        try:
            text = Path(str(src)).read_text(encoding="utf-8")
        except Exception as e:                               # noqa: BLE001
            return {"ok": False, "op": "print", "fail_closed": True,
                    "error": "src 读不到：%s: %s" % (type(e).__name__, str(e)[:120])}
    if not text.strip():
        return {"ok": False, "op": "print", "fail_closed": True, "status": "needs_params",
                "error": "要给我**要打印的代码**（code=自包含 HTML，或 src=代码文件路径）",
                "_口径": "码由她/调用方给；要模型看图回码走 op=ask_model。本件不替她编码"}
    nm = _safe(name)
    out_dir = _out_dir()
    page = out_dir / (nm + ".html")
    page.write_text(text, encoding="utf-8")
    png = out_dir / (nm + ".png")
    meta = _render(page, png, width, height, wait)
    if not meta.get("ok"):
        return {"ok": False, "op": "print", "status": meta.get("status") or "render_failed",
                "page": _rel(page), "code_bytes": page.stat().st_size, "render": meta}
    return {"ok": True, "op": "print", "page": _rel(page), "png": _rel(png),
            "code_bytes": page.stat().st_size, "png_bytes": meta.get("png_bytes"),
            "png_sha16": _sha16(png.read_bytes()),
            "render": meta,
            "_口径": "先载入再截图；「零出网」是**实测拦获**（不是 grep 推断）"}


# ── ④ 比 ──────────────────────────────────────────────────────────────────
def diff(a=None, b=None, grid: int = _GRID, bus=None, **_kw) -> dict:
    """所见帧(a) × 渲回来的图(b) → 三个现算数 + 档位判定。"""
    ab, bb = _as_b64(a), _as_b64(b)
    if not (ab and bb):
        return {"ok": False, "op": "diff", "fail_closed": True,
                "error": "要两张图：a=所见帧 / b=渲回来的图（路径或 base64）"}
    m = _bus(bus)
    if m is None or not hasattr(m, "_ahash") or not hasattr(m, "diff_regions"):
        return {"ok": False, "op": "diff", "status": "needs_dependency",
                "missing": ["tentacle.vision_bus"],
                "note": "相似度的尺子**只许有一把**（vision_bus）；不在就如实报缺，不另写第二份指纹算法"}
    try:
        ha, hb = m._ahash(ab), m._ahash(bb)
        reg = m.diff_regions(bb, ab, int(grid))
        dl = _mean_abs_l(ab, bb)
        px, worst = _pixel_stats(ab, bb, int(grid))
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "op": "diff", "error": "%s: %s" % (type(e).__name__, str(e)[:150])}
    if not ha or len(ha) != len(hb):
        return {"ok": False, "op": "diff", "error": "指纹长度异常（两图解不开？）len(a)=%d len(b)=%d"
                                                    % (len(ha), len(hb))}
    ham = sum(1 for x, y in zip(ha, hb) if x != y)
    ratio = reg.get("changed_ratio")
    # 🔴 两把尺子**各报各的档**，结论取严（2026-10-13 真眼腔实测教训）：
    #    整屏 aHash 只差 1 位（≈0.4%）而一块区域真变了 ⇒ 只报一个「不像」会把信息压没，
    #    事后复盘会得出"这么像怎么判不像"的错误结论。分开报 = 既保 fail-closed（取严），
    #    又让人看得见"整屏像、局部变了"这件事本身。
    tiers = ("同款", "接近", "不像")
    g_tier = 0 if ham <= _BANDS[0][1] else (1 if ham <= _BANDS[1][1] else 2)
    l_tier = 2
    for i, (_nm, _d, rmax, pmax, wmax) in enumerate(_BANDS):
        if ratio is not None and ratio <= rmax and px <= pmax and worst <= wmax:
            l_tier = i
            break
    lvl = max(g_tier, l_tier)                     # 取严：两把尺子谁更差听谁的
    verdict = tiers[lvl]
    return {"ok": True, "op": "diff", "verdict": verdict, "相似度": round(1 - ham / len(ha), 4),
            "aHash距离": ham, "指纹位数": len(ha),
            "块变化率": ratio, "变化块": reg.get("changed_blocks"), "网格": int(grid),
            "平均亮度差": dl, "变化像素占比": px, "最大块平均差": worst, "像素容差": _PIXEL_TOL,
            "全局档": tiers[g_tier], "局部档": tiers[l_tier], "尺度一致": g_tier == l_tier,
            "档位表": [list(x) for x in _BANDS],
            "_口径": "五个数全部现算（aHash 距离 / 块变化率 / 平均亮度差 / 变化像素占比 / 最大块平均差）；"
                     "档位写死在本件 _BANDS（可复核可改）。判定只用非 LLM 数字，不许拿形容词当判据。"
                     "⚠️ 只保底：整图 aHash 与平均值**看不见小面积改动**（本件自测实测：改一处文字颜色时"
                     "aHash 距离=0），所以**全局档**只看 aHash、**局部档**只看块变化率+变化像素占比+最大块平均差，"
                     "最终 verdict 取两者**更严**的那个；两档不一致时 `尺度一致=false`，"
                     "**表示「整屏像、局部变了」——不许把这种情形念成「还原成功」**"}


# ── ⑥ 调优：把图**配**成成品（清晰度走天真 · 补光/味道走外观库）─────────────
_KNOBS_DECLARED = ("size", "scale", "sharpen", "resample", "usm_radius", "usm_threshold",
                   "look", "look_intent", "grain", "grade_fmt", "expect", "node_inputs",
                   "say", "adjust")

# 人话 → 旋钮 的对照表（**一处定义 · 可机检**）。
# 铁律：**只查表、不猜** —— 表里没有的说法一律 `recognized=False` 并把认识的词列出来，
# 绝不"看着差不多就给个默认值"（那就是瞎猜）。判据件逐条查：命中的旋钮必须在可调清单里。
_SAY_TABLE = (
    (("更清晰", "清晰点", "清晰一点", "锐一点", "更锐", "好糊", "糊了", "模糊", "不清楚"),
     "清晰度", {"sharpen": 0.9, "scale": 2.0}),
    (("放大", "大一点", "分辨率", "4k", "高清", "高清点"),
     "清晰度", {"size": 3840}),
    (("太暗", "暗了", "提亮", "补光", "亮点", "亮一点", "发黑"),
     "补光", {"brightness": 0.06}),
    (("太亮", "过曝", "刺眼", "压暗", "暗一点"),
     "补光", {"brightness": -0.06}),
    (("发灰", "发闷", "闷得", "通透", "拉对比", "对比不够"),
     "补光", {"contrast": 1.08}),
    (("太冲", "对比太", "硬了", "对比过头"),
     "补光", {"contrast": 0.94}),
    (("淡一点", "太淡", "掉色", "褪色点"),
     "补光", {"saturation": 0.9}),
    (("艳一点", "更艳", "鲜艳", "浓一点"),
     "补光", {"saturation": 1.12}),
)


def _parse_say(say: str) -> dict:
    """人话 → 旋钮（**只查表，不猜**）。多族可同时命中；同一个旋钮被给了两个不同值 ⇒ 记「冲突」。"""
    s = str(say or "")
    low = s.lower()
    hits, knobs, conflicts = [], {}, []
    for words, fam, delta in _SAY_TABLE:
        hit = [w for w in words if w.lower() in low]
        if not hit:
            continue
        hits.append({"族": fam, "命中词": hit, "旋钮": dict(delta)})
        for k, v in delta.items():
            if k in knobs and knobs[k] != v:
                conflicts.append({"旋钮": k, "两个值": [knobs[k], v]})
            else:
                knobs[k] = v
    return {"say": s, "recognized": bool(knobs), "命中": hits, "旋钮": knobs, "冲突": conflicts,
            "认识的说法": sorted({w for words, _f, _d in _SAY_TABLE for w in words})}


def _declared_node_inputs(node: str) -> list:
    """**现读天真**：该节点声明了哪些入参（**不抄一份** —— 抄一份就会和它漂移）。"""
    try:
        from . import comfy_native as _cn
        spec = (_cn.NODES or {}).get(str(node)) or {}
        return [str(x).rstrip("?") for x in (spec.get("in") or [])]
    except Exception:                                        # noqa: BLE001
        return []


def polish(image=None, out=None, name="polish",
           size=0, scale=0, sharpen=None, resample=None,
           usm_radius=None, usm_threshold=None,
           look=None, look_intent=None, grain=None, grade_fmt=None,
           expect=None, node_inputs=None, say=None, adjust=None, **_kw) -> dict:
    """把「视觉打印的产物」调成成品 —— **旋钮全在参数上（触手可调）**：

    | 旋钮 | 走谁 | 参数 |
    |---|---|---|
    | **清晰度** | 天真 `comfy_native` · 节点 `upscale_4k` | `size`（目标宽）· `sharpen`（USM 强度）· `resample` |
    | **补光 / 味道** | 外观库 `look_grade` · `op=preview` | `look`（味道名）或 `look_intent`（人话，如「潮湿阴冷」「热血一点」） |

    🔴 **调完必须用读数验收**：调优前后在同一像素网格上算 `锐度/对比/亮度`；
    **提升不了就如实报没提升**（不许"看着更清楚了"）—— 这是本件一路的规矩在同一件事上的延续。
    两条腿都**走唯一门**（`run_task`）调既有位，不直连别人的模块函数、不绕门。
    """
    if not image:
        return {"ok": False, "op": "polish", "fail_closed": True, "status": "needs_params",
                "error": "要给 image（要调优的那张图）",
                "旋钮": {"清晰度": "size / sharpen / resample", "补光与味道": "look 或 look_intent"}}
    src = Path(str(image))
    if not src.is_file():
        return {"ok": False, "op": "polish", "status": "not_found", "error": "图不在盘：%s" % src}
    # 🔴 `sharpen` 默认必须是 **None（未给）**，不许给个 0.8 —— 否则"一个旋钮都不给"也会
    #    偷偷去放大 2×（本判据件实测抓到：`polish(image=…)` 光给图就自己放大到 1024 宽）。
    #    「无参即有后果」是本仓明令要避免的那类惊喜。
    extra = dict(node_inputs or {})
    # ① 人话：**只查表、不猜**；认不出就把认识的词摆出来让人换说法（绝不硬给默认值）
    parsed = _parse_say(say) if say else {"recognized": None, "命中": [], "旋钮": {}, "冲突": []}
    if say and not parsed["recognized"]:
        return {"ok": False, "op": "polish", "fail_closed": True, "status": "say_not_recognized",
                "error": "这句话表里没有（**不猜**）：%s" % say,
                "认识的说法": parsed["认识的说法"],
                "味道类说法": "请走 look_intent（外观库的 8 种味道，支持人话取味）"}
    if parsed.get("冲突"):
        return {"ok": False, "op": "polish", "fail_closed": True, "status": "say_conflict",
                "error": "这句话里有两个互相打架的说法，同一个旋钮被给了两个值 ⇒ 请说清要哪个",
                "冲突": parsed["冲突"], "命中": parsed["命中"]}
    adj_in = dict(adjust or {})
    if adj_in:
        bad_adj = sorted(k for k in adj_in if k not in ("brightness", "contrast", "saturation", "gamma"))
        if bad_adj:
            return {"ok": False, "op": "polish", "fail_closed": True, "status": "bad_adjust",
                    "error": "adjust 里不认这些旋钮：%s" % bad_adj,
                    "只认": ["brightness", "contrast", "saturation", "gamma"]}
    node_in = _declared_node_inputs("upscale_4k")
    if node_in:
        unknown = sorted(k for k in extra if str(k) not in node_in)
        if unknown:
            return {"ok": False, "op": "polish", "fail_closed": True,
                    "error": "node_inputs 里有该节点**没声明**的键：%s" % unknown,
                    "node": "upscale_4k", "declared": node_in,
                    "_口径": "不许把没声明的键静默丢掉（那就是「参数写了其实没生效」）"}
    knobs = {"size": int(size or 0), "scale": float(scale or 0),
             "sharpen": (float(sharpen) if sharpen is not None else None),
             "resample": (str(resample) if resample else None),
             "usm_radius": (int(usm_radius) if usm_radius is not None else None),
             "usm_threshold": (int(usm_threshold) if usm_threshold is not None else None),
             "look": str(look or ""), "look_intent": str(look_intent or ""),
             "grain": (int(grain) if grain is not None else None),
             "grade_fmt": (str(grade_fmt) if grade_fmt else None),
             "expect": dict(expect or {}), "node_inputs": extra,
             "say": (str(say) if say else ""), "adjust": {}}
    # ② 人话解析结果并入（**显式参数优先**），来源逐项标明 —— 免得"以为动了、其实没动"
    from_say = {}
    for k, v in (parsed.get("旋钮") or {}).items():
        if k in ("brightness", "contrast", "saturation", "gamma"):
            if k not in adj_in:
                knobs["adjust"][k] = v
                from_say["adjust." + k] = "say"
            continue
        if k in ("size", "scale"):
            if not (knobs["size"] > 0 or knobs["scale"] > 0):
                knobs[k] = int(v) if k == "size" else float(v)
                from_say[k] = "say"
            continue
        if k in ("sharpen", "usm_radius", "usm_threshold") and knobs[k] is None:
            knobs[k] = v
            from_say[k] = "say"
    knobs["adjust"].update(adj_in)                 # 显式 adjust 优先
    for k in adj_in:
        from_say["adjust." + k] = "显式"
    do_up = bool(knobs["size"] > 0 or knobs["scale"] > 0 or extra
                 or knobs["sharpen"] is not None or knobs["usm_radius"] is not None
                 or knobs["usm_threshold"] is not None)
    do_look = bool(knobs["look"] or knobs["look_intent"] or knobs["adjust"])
    if not (do_up or do_look):
        return {"ok": False, "op": "polish", "fail_closed": True, "status": "needs_params",
                "error": "一个旋钮都没给：清晰度给 size/sharpen，补光给 look/look_intent"}
    nm = _safe(name)
    od = _out_dir()
    pre = _quality(src)
    pre_w = int(pre["size"][0])
    final_path = Path(str(out)) if out else None
    steps, cur = [], src

    # ① 清晰度 —— 天真 upscale_4k（真渲 · 产物过闸才认账）
    if do_up:
        up = final_path if (final_path and not do_look) else (od / (nm + "-up.png"))
        # 目标宽：`size`（绝对）> `scale`（倍数）> 默认（2× 且 ≥1024）。
        # 🔴 默认也必须**回显**出来（`size_from`）—— 藏起来的默认＝看不见的常数。
        if knobs["size"] > 0:
            target, size_from = int(knobs["size"]), "size"
        elif knobs["scale"] > 0:
            target, size_from = max(1, int(round(pre_w * knobs["scale"]))), "scale"
        else:
            target, size_from = max(pre_w * 2, 1024), "default=2x(且>=1024)"
        ninputs = {"image": str(cur), "out": str(up), "size": int(target)}
        for k in ("resample", "sharpen", "usm_radius", "usm_threshold"):
            if knobs[k] is not None:
                ninputs[k] = knobs[k]
        ninputs.update(extra)                    # 直通（已在上面校验过键名）
        wf = {"name": "vp-polish-%s" % nm,
              "nodes": [{"id": "u1", "node": "upscale_4k", "inputs": ninputs}], "edges": []}
        r = _call_cap("comfy_native", {"op": "run", "workflow": wf, "expect": knobs["expect"]})
        res = r["result"] or {}
        tr = (res.get("trace") or [{}])[0]
        gate_ok = bool((tr.get("gate") or {}).get("pass"))
        step = {"step": "upscale_4k", "via": "comfy_native", "gate": r["status"],
                "ok": bool(res.get("ok")) and gate_ok, "engine": (tr.get("out") or {}).get("engine"),
                "out": str(up), "product_gate_pass": gate_ok, "fmt": up.suffix.lower(),
                "target_from": size_from,
                "knobs_used": (tr.get("out") or {}).get("knobs"), "expect": knobs["expect"]}
        steps.append(step)
        if not step["ok"] or not up.is_file():
            return {"ok": False, "op": "polish", "stage": "upscale", "steps": steps,
                    "error": res.get("error") or "upcale 那一步没成（产物不在盘或没过闸）",
                    "missing_scopes": r.get("missing_scopes")}
        step["quality_after"] = _quality(up, ref_w=pre_w)        # 这一步之后的同尺寸读数
        cur = up

    # ② 补光 / 味道 —— 外观库 look_grade（单帧出样 · 先看再定）
    if do_look:
        gf = knobs["grade_fmt"] or ".jpg"
        if not gf.startswith("."):
            gf = "." + gf
        dst = final_path or (od / (nm + "-grade" + gf))
        r = _call_cap("look_grade", {"op": "preview", "src": str(cur),
                                     "look": (knobs["look"] or knobs["look_intent"]
                                              or ("原样" if knobs["adjust"] else "filmic")),
                                     "out": str(dst), "grain": knobs["grain"],
                                     "adjust": dict(knobs["adjust"])})
        res = r["result"] or {}
        step = {"step": "preview(味道)", "via": "look_grade", "gate": r["status"],
                "ok": bool(res.get("ok")) and Path(str(dst)).is_file(),
                "look": res.get("look"), "label": res.get("label"), "out": str(dst),
                "grain": res.get("grain"), "how": res.get("how"),
                "adjust": res.get("adjust"),
                "fmt": Path(str(dst)).suffix.lower()}
        steps.append(step)
        if not step["ok"]:
            return {"ok": False, "op": "polish", "stage": "look", "steps": steps,
                    "error": res.get("error") or "味道那一步没成（产物不在盘）",
                    "missing_scopes": r.get("missing_scopes")}
        step["quality_after"] = _quality(Path(str(dst)), ref_w=pre_w)
        cur = Path(str(dst))

    if final_path and cur != final_path:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(cur.read_bytes())
        cur = final_path

    # 🔴 **每步各判各的**（2026-10-13 实测教训）：把"放大"和"上味道"混成一个端到端差值，
    #    会把两件事糊成一件事 —— 味道那一步改的是亮度/对比（链里就有 eq=brightness），
    #    拿它去算"清晰度差"，读出来的数根本不是清晰度。⇒ 清晰度只看**放大那一步**；
    #    补光/味道单列（亮度/对比差）。
    up_step = next((s for s in steps if s["step"] == "upscale_4k"), None)
    look_step = next((s for s in steps if s["step"] == "preview(味道)"), None)
    pct = None
    verdict = "未做清晰度那一步"
    fmt_warn = ""
    if up_step:
        q = up_step.get("quality_after") or {}
        pct = round((q.get("sharp", 0) / pre["sharp"] - 1) * 100, 2) if pre["sharp"] else None
        if pct is None:
            verdict = "无法判定"
        elif pct >= 2:
            verdict = "清晰度提升"
        elif pct <= -2:
            verdict = "清晰度下降"
        else:
            verdict = "基本持平"
        if src.suffix.lower() != up_step.get("fmt"):
            fmt_warn = ("⚠️ 比的两种格式不同（%s × %s）—— 读数里含**格式差**，不是纯清晰度差"
                        % (src.suffix.lower() or "无后缀", up_step.get("fmt")))
    post = _quality(cur, ref_w=pre_w)                   # 成品的最终读数（同一像素网格）
    look_delta = None
    if look_step:
        q = look_step.get("quality_after") or {}
        look_delta = {"亮度差": round(q.get("brightness", 0) - pre["brightness"], 3),
                      "对比差": round(q.get("contrast", 0) - pre["contrast"], 3)}
        if src.suffix.lower() != look_step.get("fmt"):
            fmt_warn = (fmt_warn + " ｜ " if fmt_warn else "") + (
                "⚠️ 味道那一步产物是 %s（有损格式会压掉高频）—— 亮度/对比差里含**格式差**"
                % look_step.get("fmt"))
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": "polish", "src": str(src),
           "out": str(cur), "knobs": knobs, "steps": steps, "verdict": verdict,
           "sharp_pct": pct, "pre": pre, "post": post, "look_delta": look_delta,
           "fmt_warn": fmt_warn,
           "contrast_delta": round(post["contrast"] - pre["contrast"], 3),
           "brightness_delta": round(post["brightness"] - pre["brightness"], 3)}
    led = _record(row)
    _audit("vision_print_polish", row)
    return {"ok": True, "op": "polish", "verdict": verdict, "清晰度变化_pct": pct,
            "旋钮_可调": list(_KNOBS_DECLARED), "旋钮_本次实际用了": knobs,
            "人话解析": parsed if say else None, "来源": from_say,
            "锐度_同尺寸": {"调前": pre["sharp"],
                           "放大后": (up_step or {}).get("quality_after", {}).get("sharp"),
                           "成品": post["sharp"]},
            "对比": {"调前": pre["contrast"], "调后": post["contrast"],
                     "差": row["contrast_delta"]},
            "亮度": {"调前": pre["brightness"], "调后": post["brightness"],
                     "差": row["brightness_delta"]},
            "补光与味道": look_delta, "尺子警告": fmt_warn or None,
            "尺寸": {"调前": pre["size"], "调后": post["size"]}, "steps": steps,
            "out": str(cur), "ledger": led,
            "_口径": "旋钮从参数传入（触手可调）；两条腿都走唯一门调既有位；"
                     "读数在同一像素网格上比（放大本身会抬读数，直接比尺寸不同的两个数＝尺子坏）；"
                     "**清晰度只看放大那一步、补光单列** —— 混成一个端到端差值会把两件事糊成一件事"}


# ── 看图回码（可选腿：缺依赖就如实报缺）─────────────────────────────────
def ask_model(image=None, prompt=None, cap=None, **_kw) -> dict:
    """让外部视觉模型看图 → 自包含 HTML。缺依赖 ⇒ needs_dependency；**绝不编假码**。"""
    b64 = _as_b64(image)
    if not b64:
        return {"ok": False, "op": "ask_model", "fail_closed": True,
                "error": "要给它看的那张图（image=路径/base64）"}
    m = _cap_mod(cap)
    if m is None or not hasattr(m, "cloud_recognize"):
        return {"ok": False, "op": "ask_model", "status": "needs_dependency",
                "missing": ["gbt_allinone.vision_cap"]}
    r = m.cloud_recognize(image=b64, prompt=prompt or _MODEL_PROMPT)
    if not r.get("ok"):
        return {"ok": False, "op": "ask_model", "status": str(r.get("status") or "needs_dependency"),
                "missing": ["视觉模型（GBT_VISION_BASE_URL / 保险箱密钥 / GBT_VISION_MODEL）"],
                "upstream": r,
                "_口径": "「看图」靠外部视觉模型（她的底座 Qwen2 **没有视觉塔**）；"
                         "缺就如实报缺，绝不编一段假码"}
    txt = str(r.get("description") or "")
    code, looks = _extract_code(txt)
    out = {"ok": bool(code), "op": "ask_model", "model": r.get("model"), "key_id": r.get("key_id"),
           "code_looks_like_code": looks, "code": code, "code_chars": len(code)}
    if not code:
        out["status"] = "no_code"
        out["error"] = "模型回复里**没有代码块** —— 如实报，不拿散文去渲"
        out["raw_head"] = txt[:400]
    return out


# ── ⑤ 一条链 ──────────────────────────────────────────────────────────────
def loop(code=None, src=None, image=None, region=None, name="loop", use_model: bool = False, prompt=None,
         width: int = 1280, height: int = 900, wait: float = 0.7, grid: int = _GRID,
         bus=None, cap=None, **_kw) -> dict:
    """see → print → render → diff → judge，一次给全景读数（缺哪段点哪段）。"""
    t0 = time.time()
    nm = _safe(name)
    s = see(image=image, region=region, name=nm)
    if not s.get("ok"):
        return {"ok": False, "op": "loop", "stage": "see", "see": s}
    src_code = code
    if not (isinstance(src_code, str) and src_code.strip()) and src:
        try:
            src_code = Path(str(src)).read_text(encoding="utf-8")
        except Exception as e:                               # noqa: BLE001
            return {"ok": False, "op": "loop", "stage": "print", "fail_closed": True, "see": s,
                    "error": "src 读不到：%s: %s" % (type(e).__name__, str(e)[:120])}
    model_face = None
    if use_model:
        model_face = ask_model(image=s["frame"], prompt=prompt, cap=cap)
        if not model_face.get("ok"):
            return {"ok": False, "op": "loop", "stage": "ask_model", "see": s, "ask_model": model_face}
        src_code = model_face.get("code")
    if not src_code:
        return {"ok": False, "op": "loop", "stage": "print", "fail_closed": True, "see": s,
                "status": "needs_params",
                "error": "要给 code（她的码）或 use_model=true（看图回码）"}
    p = print_code(code=src_code, name=nm, width=width, height=height, wait=wait)
    if not p.get("ok"):
        return {"ok": False, "op": "loop", "stage": "render", "see": s, "print": p}
    d = diff(a=s["frame"], b=p.get("png"), grid=grid, bus=bus)
    if not d.get("ok"):
        return {"ok": False, "op": "loop", "stage": "diff", "see": s, "print": p, "diff": d}
    render = p.get("render") or {}
    # ── 假绿闸（fail-closed）：四种情形一律把结论降成「无法判定」，**不许**报「同款」 ──
    # 它们不是"算错"，是"算得出来但不许当结论"。
    voids = []
    if s.get("frame_suspect"):
        voids.append("所见帧近空白（灰度标准差 %s，没有信息量）" % s.get("std_l"))
    if p.get("png_sha16") and s.get("sha16") and p["png_sha16"] == s["sha16"]:
        voids.append("所见帧与渲回来的图**逐字节同一张**（sha16 %s）⇒ 自己跟自己比，与「还原」无关"
                     % s["sha16"])
    if render.get("errors") or render.get("failed"):
        voids.append("渲得不可信：页面自报错 %d 条 · 请求失败 %d 条"
                     % (len(render.get("errors") or []), len(render.get("failed") or [])))
    if render.get("blocked"):
        voids.append("渲得不可信：有 %d 条**出网请求被拦**（本件禁网兜底）"
                     "⇒ 这张图不是真实浏览器会显示的样子，拿它下结论就是假绿"
                     % len(render.get("blocked") or []))
    verdict = _VERDICT_UNKNOWN if voids else d.get("verdict")
    d_out = dict(d)
    if voids:
        d_out["原始档位"] = d.get("verdict")
        d_out["verdict"] = _VERDICT_UNKNOWN
        d_out["无法判定理由"] = voids
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": "loop", "name": nm,
           "frame": s.get("frame"), "frame_from": s.get("frame_from"),
           "frame_sha16": s.get("sha16"), "frame_std_l": s.get("std_l"),
           "frame_fingerprint": s.get("fingerprint"),
           "page": p.get("page"), "png": p.get("png"), "render_engine": render.get("engine"),
           "blocked": len(render.get("blocked") or []), "render_errors": len(render.get("errors") or []),
           "verdict": verdict, "可信": not voids, "无法判定理由": voids,
           "similarity": d.get("相似度"),
           "ahash_dist": d.get("aHash距离"), "changed_ratio": d.get("块变化率"),
           "mean_delta_l": d.get("平均亮度差"),
           # 🔴 判档实际咬的是这两个**局部敏感**数 —— 账里必须有它们，
           #    否则事后只看 ahash_dist 会得出"这么像怎么判不像"的错误复盘（真眼腔实测：aHash 差 1 位仍判不像）
           "changed_px": d.get("变化像素占比"), "worst_block": d.get("最大块平均差"),
           "pixel_tol": d.get("像素容差"),
           "global_tier": d.get("全局档"), "local_tier": d.get("局部档"),
           "scales_agree": d.get("尺度一致"),
           "code_from": "model" if use_model else "caller",
           "ms": int((time.time() - t0) * 1000)}
    led = _record(row)
    _audit("vision_print", row)
    return {"ok": True, "op": "loop", "verdict": verdict, "可信": not voids,
            "无法判定理由": voids, "相似度": d.get("相似度"),
            "frame": s.get("frame"), "page": p.get("page"), "png": p.get("png"),
            "diff": d_out, "render": render, "ask_model": model_face, "ledger": led,
            "_口径": "ok=**五段链真跑通**（不是「还原成功」）；像不像看 verdict 与五个数；"
                     "verdict=「无法判定」表示**算得出来但不许当结论**（近空白帧/自比/渲得不可信）"}


# ── 契约面 ────────────────────────────────────────────────────────────────
def status(**_kw) -> dict:
    m = _bus(None)
    c = _cap_mod(None)
    via = None
    if c is not None and hasattr(c, "resolve_vision_backend"):
        try:
            via = c.resolve_vision_backend().get("via")
        except Exception:                                    # noqa: BLE001
            via = None
    return {"ok": True, "op": "status", "kind": "vision_print",
            "stages": ["see", "print", "render", "diff", "judge"],
            "eye": "tentacle.omni_core._screen_capture（dxcam→mss→pyautogui）",
            "ruler_present": bool(m), "ruler": "tentacle.vision_bus" if m else None,
            "eye_cap_present": bool(c), "cloud_vision_via": via,
            "out": _rel(_out_dir()), "ledger": _rel(_ledger_path()),
            "bands": [list(x) for x in _BANDS],
            "polish_legs": {"清晰度": "天真 comfy_native · 节点 upscale_4k（lanczos+USM · 旋钮 size/sharpen/resample）",
                            "补光与味道": "外观库 look_grade · op=preview（8 味道 · 链里含 eq=brightness 等）"},
            "guards": {"空白帧阈值_std_l": _BLANK_STD,
                       "第四档": _VERDICT_UNKNOWN,
                       "触发": ["所见帧近空白", "所见帧与渲回图逐字节同一张（自比）",
                                "渲得不可信（页面报错/请求失败）",
                                "渲时有出网请求被拦（那张图不是真实浏览器的样子）"]}}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "vision_print",
            "entry": "run_task('vision_print', {...})",
            "ops": ["see", "print", "diff", "loop", "polish", "ask_model", "status", "where"],
            "chain": ["see 取帧（原生眼）", "print 真码落地", "render 真 Chromium 渲",
                      "diff 与所见帧比（vision_bus）", "judge 三数成档",
                      "polish 调成成品（清晰度走天真 · 补光/味道走外观库）"],
            "not_copied": "不引任何截图转代码的上游实现；本件只做**编排**与**判据**，"
                          "眼睛用本仓原生的（omni_core / vision_bus），尺子只许一把",
            "hard_rules": ["码由调用方/她给，本件不编码（抽不出代码块就如实报 no_code）",
                           "零出网是实测拦获（逐条记），不是 grep 推断",
                           "相似度**五数**现算（含两个局部敏感项）· vision_bus 不在 ⇒ fail-closed",
                           "假绿闸：近空白帧 / 自比（逐字节同一张）/ 渲得不可信 ⇒ 结论降成「无法判定」，"
                           "不许报「同款」",
                           "`frame_from` 如实标 screen/file：文件当帧时不许念成「她真看过屏幕」",
                           "每次跑落 store/vision_print/ledger.jsonl + 框架审计一条"],
            "files": {"产物": _rel(_out_dir()), "账": _rel(_ledger_path())},
            "contract": [
                {"op": "see", "params": "image?/region?/name?", "returns": "所见帧 PNG + 指纹"},
                {"op": "print", "params": "code 或 src + name?", "returns": "自包含页 + 渲回的 PNG"},
                {"op": "diff", "params": "a=所见帧 b=渲回图 grid?", "returns": "三数 + 档位"},
                {"op": "loop", "params": "code 或 use_model + name?", "returns": "五段链全景 + 落账"},
                {"op": "ask_model", "params": "image + prompt?", "returns": "模型回的自包含 HTML（缺依赖如实报）"},
            ]}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("see", see), ("print", print_code), ("diff", diff), ("loop", loop),
                   ("polish", polish), ("ask_model", ask_model), ("status", status), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": "未知 op:%s（see/print/diff/loop/polish/ask_model/status/where）" % op}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="视觉打印：看到的东西 → 打成代码 → 真渲染 → 与所见帧比")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}", help='入参 JSON，如 {"name":"t1"}')
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
