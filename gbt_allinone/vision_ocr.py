# -*- coding: utf-8 -*-
"""vision_ocr -- 把屏幕/图片上的 **字** 读成纯文本（零安装优先 · 离线 · 不回图）。

车道① windows-media-ocr   Windows.Media.Ocr 经 PowerShell 桥（系统内置 · 零 pip · 离线）← 默认
车道② winrt                装了 winrt-* 才走（原生 python WinRT，同一引擎的另一条腿）
车道③ pytesseract          装了 tesseract.exe + pytesseract 才走（chi_sim+eng，缺中文包退 eng）

── 设计铁律（2026-11-04 主人令「看图片用原生视觉，别走附件系统」）──────────────
1. **只吃本地路径**，绝不吃 URL。远程图必须先落本地再读（`fetch_to_temp()` 代劳）。
2. **只回文本**。图片本身永不进上下文 ⇒ 不产生远程 URL ⇒ 不会 HTTP 471 ⇒ 不吃图片 token。
3. **读不到就如实报**「没读到字」，绝不编字。

对外只有一个门：`ocr(image=..., lang=...)`
返回：{"ok": true, "backend": ..., "lang": ..., "lines": n, "chars": n, "text": "...", "truncated": bool}
      {"ok": false, "reason": ..., "lanes": {...}}
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_BRIDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "win_ocr.ps1")
MAX_CHARS = 12000


# ────────────────────────── 工具 ──────────────────────────
def _is_url(value) -> bool:
    return str(value or "").strip().lower().startswith(("http://", "https://", "file://"))


def fetch_to_temp(url: str) -> str:
    """把远程图落成本地临时 png，返回路径。失败抛异常。

    存在的意义：调度侧偶尔会递来一个 URL。就地落盘 = 图片永远不进上下文。
    """
    import urllib.request

    suffix = ".png"
    low = url.lower().split("?")[0]
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        if low.endswith(ext):
            suffix = ext
            break
    fd, path = tempfile.mkstemp(prefix="gbt-ocr-fetch-", suffix=suffix)
    os.close(fd)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (GBT vision_ocr)"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(path, "wb") as fh:
        fh.write(resp.read())
    return path


def _clip(text: str):
    """超长截断，返回 (text, truncated)。"""
    text = (text or "").strip()
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + "\n…（已截断，原长 %d 字）" % len(text), True
    return text, False


# ────────────────────── 车道① 系统内置 OCR ──────────────────────
def _lane_windows_media_ocr(path, lang=None):
    if os.name != "nt":
        raise OSError("windows-media-ocr 只在 Windows 上可用")
    if not os.path.exists(_BRIDGE):
        raise FileNotFoundError("缺桥文件: %s" % _BRIDGE)
    out = os.path.join(tempfile.gettempdir(), "gbt-ocr-%d.json" % os.getpid())
    try:
        if os.path.exists(out):
            os.remove(out)
    except OSError:
        pass
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", _BRIDGE, "-Path", path, "-Out", out]
    if lang:
        cmd += ["-Lang", str(lang)]
    subprocess.run(cmd, capture_output=True, timeout=90,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not os.path.exists(out):
        raise RuntimeError("桥没产出结果文件（powershell 启动失败？）")
    with open(out, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    try:
        os.remove(out)
    except OSError:
        pass
    if not data.get("ok"):
        raise RuntimeError(data.get("reason") or "windows-media-ocr 未读到字")
    return {"text": data.get("text") or "", "lines": data.get("lines"),
            "boxes": data.get("boxes") or [],
            "lang": data.get("lang"), "backend": data.get("backend", "windows-media-ocr")}


# ────────────────────── 车道② python winrt ──────────────────────
def _lane_winrt(path, lang=None):
    import asyncio
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage import StorageFile, FileAccessMode

    async def _run():
        f = await StorageFile.get_file_from_path_async(os.path.abspath(path))
        st = await f.open_async(FileAccessMode.READ)
        dec = await BitmapDecoder.create_async(st)
        bmp = await dec.get_software_bitmap_async()
        eng = None
        for tag in ([lang] if lang else []) + ["zh-Hans-CN", "zh-CN"]:
            try:
                eng = OcrEngine.try_create_from_language(Language(tag))
            except Exception:
                eng = None
            if eng is not None:
                break
        if eng is None:
            eng = OcrEngine.try_create_from_user_profile_languages()
        if eng is None:
            raise RuntimeError("没有可用的 OCR 引擎")
        res = await eng.recognize_async(bmp)
        lines = [ln.text for ln in res.lines]
        text = "\n".join(lines).replace(" ", "") if _has_cjk("\n".join(lines)) else "\n".join(lines)
        return {"text": text, "lines": len(lines), "lang": str(eng.recognizer_language.language_tag),
                "backend": "winrt"}

    return asyncio.run(_run())


def _has_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s or "")


# ────────────────────── 车道③ pytesseract ──────────────────────
def _lane_tess(path, lang=None):
    import pytesseract
    from PIL import Image

    if os.path.exists(TESSERACT_EXE):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    img = Image.open(path)
    order = [lang] if lang else []
    order += ["chi_sim+eng", "eng"]
    last = None
    for lg in order:
        try:
            txt = pytesseract.image_to_string(img, lang=lg)
            return {"text": (txt or "").strip(), "lines": len((txt or "").strip().splitlines()),
                    "lang": lg, "backend": "pytesseract"}
        except Exception as exc:  # 缺中文包 → 退 eng
            last = exc
    raise RuntimeError("pytesseract 全语种失败: %s" % last)


# ────────────────────────── 主门 ──────────────────────────
LANES = (
    ("windows-media-ocr", _lane_windows_media_ocr),
    ("winrt", _lane_winrt),
    ("pytesseract", _lane_tess),
)


def ocr(image=None, lang=None, **kw):
    """看图读字。image = 本地路径（也接受 URL，会先落本地）。"""
    if not image:
        return {"ok": False, "reason": "没给 image（要本地图片路径）"}

    target = str(image).strip().strip('"').strip("'")
    temp = None
    if _is_url(target):
        try:
            temp = fetch_to_temp(target)
            target = temp
        except Exception as exc:
            return {"ok": False, "reason": "远程图落本地失败: %s: %s" % (type(exc).__name__, str(exc)[:120])}

    try:
        if not os.path.exists(target):
            return {"ok": False, "reason": "本地图片不存在: %s" % target}

        errors = {}
        for name, fn in LANES:
            try:
                out = fn(target, lang)
            except Exception as exc:
                errors[name] = "%s: %s" % (type(exc).__name__, str(exc)[:140])
                continue
            text, truncated = _clip(out.get("text"))
            if not text:
                errors[name] = "读到了帧但没读到字（可能是纯图形界面）"
                continue
            return {"ok": True, "backend": name, "lang": out.get("lang"),
                    "lines": out.get("lines"), "chars": len(text),
                    "truncated": truncated, "text": text}

        return {"ok": False, "reason": "三条车道都没读到字", "lanes": errors}
    finally:
        if temp:
            try:
                os.remove(temp)
            except OSError:
                pass


def ocr_boxes(image=None, lang=None, **kw):
    """只走系统 OCR，把**每行文字连同包围盒**一起拿回来（给界面解析 vision_ui 用）。

    普通 ocr() 只回文本、丢掉位置；这里保留 (x,y,w,h)，才能把文字和界面区块对上。
    """
    if not image:
        return {"ok": False, "reason": "没给 image（要本地图片路径）"}
    target = str(image).strip().strip('"').strip("'")
    temp = None
    if _is_url(target):
        try:
            temp = fetch_to_temp(target)
            target = temp
        except Exception as exc:
            return {"ok": False, "reason": "远程图落本地失败: %s: %s"
                                          % (type(exc).__name__, str(exc)[:120])}
    try:
        if not os.path.exists(target):
            return {"ok": False, "reason": "本地图片不存在: %s" % target}
        out = _lane_windows_media_ocr(target, lang)
        boxes = out.get("boxes") or []
        return {"ok": True, "backend": out.get("backend"), "lang": out.get("lang"),
                "count": len(boxes), "boxes": boxes}
    except Exception as exc:
        return {"ok": False, "reason": "%s: %s" % (type(exc).__name__, str(exc)[:140])}
    finally:
        if temp:
            try:
                os.remove(temp)
            except OSError:
                pass


def run(op="read", **params):
    """统一入口，方便 api.run_task 风格调用。"""
    if op in ("read", "ocr", "text"):
        return ocr(params.get("image") or params.get("path"), params.get("lang"))
    if op in ("boxes", "lines", "layout"):
        return ocr_boxes(params.get("image") or params.get("path"), params.get("lang"))
    if op == "lanes":
        return {"ok": True, "lanes": [n for n, _ in LANES],
                "bridge": _BRIDGE, "bridge_exists": os.path.exists(_BRIDGE)}
    return {"ok": False, "reason": "未知 op: %s（支持 read/boxes/lanes）" % op}
