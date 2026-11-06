# -*- coding: utf-8 -*-
"""薄壳：真实现是 ``gbt_allinone/tools/film_gate.py``（零外部依赖）。

    python tools/film-gate.py probe 片.mp4
    python tools/film-gate.py subtitles 字幕.ass
    python tools/film-gate.py storyboard 分镜.json --segment E01-01
    python tools/film-gate.py verify 片.mp4 --storyboard 分镜.json --segment E01-01 --subs 字幕.ass

为什么要有壳：验收器要能被**终端 / process_execute / 触手**用同一条命令调到，
而 pyembed 是 embeddable 包（``-m`` 不生效），所以脚本自己把仓根塞进 sys.path。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone.tools import film_gate as FG  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="成片验收（零外部依赖，不调 ffprobe）")
    ap.add_argument("op", nargs="?", default="schema",
                    choices=["schema", "probe", "subtitles", "storyboard", "verify"])
    ap.add_argument("path", nargs="?", default="")
    ap.add_argument("--storyboard", default="")
    ap.add_argument("--segment", default="")
    ap.add_argument("--subs", default="")
    ap.add_argument("--audio", default="")
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--fps", type=float, default=0.0)
    a = ap.parse_args()

    spec = {}
    if a.width:
        spec["width"] = a.width
    if a.height:
        spec["height"] = a.height
    if a.fps:
        spec["fps"] = a.fps
    out = FG.run(a.op, film=a.path, path=a.path, storyboard=a.storyboard or None,
                 segment=a.segment, subs=a.subs or None,
                 audio=a.audio or None, spec=spec or None)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
