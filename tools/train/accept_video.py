# -*- coding: utf-8 -*-
"""accept_video -- 看视频理解验收（判据按题型分派）"""
from __future__ import annotations
import argparse, json
from pathlib import Path
CASES = {
    "怎么知道本机能不能看视频": [("probe",), ("未读到", "missing")],
    "看视频要出什么结构": [("类型化", "shots"), ("未读到",)],
    "镜头是怎么切出来": [("ffmpeg", "scene"), ("\u65f6\u957f", "\u5e27\u7387", "len", "0.05")],
    "语义层": [("未读到",), ("视觉位", "云车道")],
    "喂给谁": [("shot_director",), ("输入", "命令")],
    "命令怎么写": [("video_intel",), ("cap", "five-dim")],
}


def main():
    ap = argparse.ArgumentParser(description="看视频理解验收")
    ap.add_argument("--answers", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = 0
    for i, r in enumerate(rows, 1):
        q = r.get("q") or ""
        ans = r.get("a") or ""
        rule = None
        for key, rr in CASES.items():
            if key in q:
                rule = rr
                break
        if rule is None:
            print("  %-3d RED  无对应判据（题=%s）" % (i, q[:20]))
            continue
        miss = []
        for grp in rule:
            if not any(w.lower() in ans.lower() for w in grp):
                miss.append(list(grp))
        good = not miss
        print("  %-3d %s 缺 %s" % (i, "OK " if good else "RED", miss or "-"))
        ok += 1 if good else 0
    print("== 看视频理解：%d/%d ==" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

