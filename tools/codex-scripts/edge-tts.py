# gbt-capability: drama_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""edge-tts.py — 台湾腔女声（zh-TW-HsiaoChenNeural）合成；需联网。

为什么不用 SAPI：本机音色随系统语言包漂移，不能拿来当既定音色。
（2026-11-04 复测：本机已装 Microsoft Hanhan Desktop / zh-TW / Female，同时也装着 zh-CN Huihui；
 旧注释「本机 SAPI 只有 zh-CN Huihui、没有 zh-TW 女声」已过时 —— 以 GetInstalledVoices 现读为准，
 不要在注释里断言某台机器的音色清单。）
Edge TTS 的 zh-TW-HsiaoChenNeural 是台湾腔女声；edge-tts 依赖装在 vendor/pylibs（不进源码）。
用法：py tools/codex-scripts/edge-tts.py --text-file in.txt --out out.mp3 [--voice zh-TW-HsiaoChenNeural]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _base in (ROOT, ROOT.parent):
    _libs = _base / "vendor" / "pylibs"
    if _libs.is_dir():
        sys.path.insert(0, str(_libs))
        break


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="zh-TW-HsiaoChenNeural")
    ap.add_argument("--rate", default="")
    ap.add_argument("--pitch", default="")
    args = ap.parse_args()
    text = args.text or (Path(args.text_file).read_text(encoding="utf-8-sig", errors="replace") if args.text_file else "")
    text = " ".join(text.split())
    if not text:
        print(json.dumps({"ok": False, "error": "text 为空"}, ensure_ascii=False))
        return 2
    try:
        import edge_tts
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": "edge_tts 未安装/不可导入：%s" % type(e).__name__,
                          "how": "已装 vendor/pylibs；检查 PYTHONPATH"}, ensure_ascii=False))
        return 3
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kw = {}
    if args.rate:
        kw["rate"] = args.rate
    if args.pitch:
        kw["pitch"] = args.pitch
    try:
        c = edge_tts.Communicate(text, args.voice, **kw)
        asyncio.run(c.save(str(out)))
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:180]), "voice": args.voice},
                         ensure_ascii=False))
        return 4
    print(json.dumps({"ok": out.is_file() and out.stat().st_size > 1000, "out": str(out),
                      "voice": args.voice, "bytes": out.stat().st_size if out.is_file() else 0},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
