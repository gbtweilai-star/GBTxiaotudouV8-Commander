# -*- coding: utf-8 -*-
"""vision_ocr -- 把屏幕/图片上的**字**读出来（零密钥优先，离线）。
车道① Windows.Media.Ocr（python winrt，系统 zh-CN）
车道② pytesseract + 本机 tesseract.exe（chi_sim+eng，缺中文包退 eng）
取不到就如实写未读到，绝不编字。
"""
from __future__ import annotations

EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _lane_winrt(path):
    import asyncio
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage import StorageFile, FileAccessMode

    async def _r():
        f = await StorageFile.get_file_from_path_async(path)
        st = await f.open_async(FileAccessMode.READ)
        dec = await BitmapDecoder.create_async(st)
        bmp = await dec.get_software_bitmap_async()
        eng = None
        try:
            eng = OcrEngine.try_create_from_language(Language("zh-CN"))
        except Exception:
            eng = None
        if eng is None:
            eng = OcrEngine.try_create_from_user_profile_languages()
        if eng is None:
            return None
        res = await eng.recognize_async(bmp)
        lines = [ln.text for ln in res.lines]
        return {"text": chr(10).join(lines), "lines": len(lines)}

    return asyncio.run(_r())


def _lane_tess(path):
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = EXE
    img = Image.open(path)
    try:
        txt = pytesseract.image_to_string(img, lang="chi_sim+eng")
        lang = "chi_sim+eng"
    except Exception:
        txt = pytesseract.image_to_string(img, lang="eng")
        lang = "eng"
    txt = (txt or "").strip()
    return {"text": txt[:6000], "chars": len(txt), "lang": lang}


def ocr(image=None, **kw):
    if not image:
        return {"ok": False, "reason": "没给 image"}
    path = str(image)
    errs = {}
    for name, fn in (("winrt-windows-media-ocr", _lane_winrt), ("pytesseract", _lane_tess)):
        try:
            out = fn(path)
            if out and out.get("text"):
                return {"ok": True, "backend": name, **out}
            errs[name] = "读到了帧但没读到字（可能是纯图形界面）"
        except Exception as e:
            errs[name] = "%s: %s" % (type(e).__name__, str(e)[:100])
    return {"ok": False, "reason": "两条车道都没读到字", "lanes": errs}
