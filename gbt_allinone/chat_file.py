# -*- coding: utf-8 -*-
# gbt-capability: none  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""对话附件（chat_file）—— 聊天里「发送文件」入口的本地解析。

定位：和 `chat_image` 同一层（只读、零出网、零写盘）：
  · 文本/代码类文件（txt/md/json/csv/log/py/js/…）→ 解码出前 N 字 + 行数/字节/sha256；
  · 图片文件（走文件入口发来的）→ 转交 `chat_image` 出视觉读数；
  · 二进制（zip/pdf/…）→ 只报元数据（名字/大小/类型/sha256），**不假装解析内容**；
  · 单文件 ≤ 20MB；读不出如实报错。
"""
from __future__ import annotations

import base64
import hashlib
import re

MAX_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 4000
TEXT_EXTS = (".txt", ".md", ".markdown", ".json", ".jsonl", ".csv", ".tsv", ".log",
             ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".htm",
             ".css", ".scss", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".xml",
             ".sql", ".sh", ".ps1", ".bat", ".cmd", ".java", ".go", ".rs", ".c",
             ".h", ".cpp", ".hpp", ".rb", ".php", ".vue", ".svelte", ".diff", ".patch")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".ico")
FILE_ASK_RX = re.compile(
    r"(文件|附件|看看|看下|读一下|读读|内容|是什么|总结|分析|里面.*什么|附件.*什么)", re.I)


def _parse_data(data):
    """data URL / base64 / bytes → (bytes, mime)。"""
    if isinstance(data, (bytes, bytearray)):
        return bytes(data), ""
    s = str(data or "")
    if not s:
        return b"", ""
    if s.startswith("data:"):
        try:
            head, b64 = s.split(",", 1)
            mime = head.split(";", 1)[0][5:]
            return base64.b64decode(b64), mime
        except Exception:                                        # noqa: BLE001
            return b"", ""
    try:
        return base64.b64decode(s, validate=False), ""
    except Exception:                                            # noqa: BLE001
        return b"", ""


def _ext(name: str) -> str:
    n = str(name or "").strip().lower()
    i = n.rfind(".")
    return n[i:] if i >= 0 else ""


def _size_str(n: int) -> str:
    n = int(n or 0)
    if n < 1024:
        return "%dB" % n
    if n < 1024 * 1024:
        return "%.1fKB" % (n / 1024.0)
    return "%.1fMB" % (n / 1048576.0)


def looks_file_question(text: str) -> bool:
    return bool(FILE_ASK_RX.search(str(text or "")))


def analyze(name: str, data, file_type: str = "") -> dict:
    """附件 → 本地可读摘要（{ok, kind, brief, text?/analysis?, bytes, sha256}）。"""
    raw, mime = _parse_data(data)
    if not raw:
        return {"ok": False, "error": "user_error: 附件解码失败（不是合法 data URL/base64）",
                "missing": ["file"]}
    if len(raw) > MAX_BYTES:
        return {"ok": False, "error": "user_error: 文件太大（> 20MB）", "bytes": len(raw),
                "missing": ["file_size"]}
    fname = str(name or "附件").strip()[:200]
    ext = _ext(fname) or _ext(str(file_type or ""))
    mime = str(file_type or mime or "")
    sha = hashlib.sha256(raw).hexdigest()
    base = {"name": fname, "bytes": len(raw), "sha256": sha,
            "mime": mime or ("application/octet-stream"), "ext": ext}
    if ext in IMAGE_EXTS or mime.startswith("image/"):
        try:
            from . import chat_image as _CI
            r = _CI.analyze(data)
            if r.get("ok"):
                return {"ok": True, "kind": "image",
                        "brief": "图片附件：%s · %s" % (fname, r.get("brief")),
                        "analysis": r.get("analysis"), **base}
            return {"ok": False, "kind": "image", "error": r.get("error"),
                    "missing": r.get("missing") or ["image"], **base}
        except Exception as exc:                                 # noqa: BLE001
            return {"ok": False, "kind": "image",
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:160]), **base}
    is_text = (ext in TEXT_EXTS or mime.startswith("text/")
               or mime in ("application/json", "application/xml",
                           "application/javascript", "application/x-yaml"))
    if not is_text:
        # 末路：前 4KB 不含 NUL 且 UTF-8 可解 ⇒ 按文本处理（常见无扩展名脚本）
        head = raw[:4096]
        try:
            if b"\x00" not in head:
                head.decode("utf-8")
                is_text = True
        except Exception:                                        # noqa: BLE001
            is_text = False
    if is_text:
        text = raw.decode("utf-8", errors="replace")
        lines = text.count("\n") + (1 if text else 0)
        preview = text[:MAX_TEXT_CHARS]
        brief = ("文本附件：%s · %s · %d 行 · sha256 %s… · 前 %d 字：%s"
                 % (fname, _size_str(len(raw)), lines, sha[:12], min(len(preview), 600),
                    preview[:600].replace("\n", " ⏎ ")))
        return {"ok": True, "kind": "text", "brief": brief,
                "lines": lines, "preview": preview, "truncated": len(text) > MAX_TEXT_CHARS,
                **base}
    return {"ok": True, "kind": "binary",
            "brief": "二进制附件：%s · %s · %s · sha256 %s…（不解析内容，不假装读过）"
                     % (fname, _size_str(len(raw)), base["mime"], sha[:12]), **base}
