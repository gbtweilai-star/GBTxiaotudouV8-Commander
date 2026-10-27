#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deck_check —— 演示台的成品验收：每次生成都过一遍，不靠肉眼。

六项（都能量，不靠感觉）：
  ① deck.html 存在且页数 ≥3
  ② 每页都有标题
  ③ 配图命中率（有图页 / 总页）
  ④ deck.mp4 分辨率 = 1920×1080
  ⑤ 音轨存在（要求旁白时）
  ⑥ 硬字幕已烧进 HTML（body.subs + 每页 .sub）

用法： python3 tools/deck_check.py <deck目录> [--expect-audio] [--expect-subs]
"""
import argparse, json, os, subprocess, sys


def probe(mp4):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height:format=duration",
                        "-of", "json", mp4], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except Exception:                                             # noqa: BLE001
        return {}
    st = d.get("streams") or []
    v = next((s for s in st if s.get("codec_type") == "video"), {})
    return {"has_audio": any(s.get("codec_type") == "audio" for s in st),
            "w": v.get("width"), "h": v.get("height"),
            "dur": round(float(d.get("format", {}).get("duration") or 0), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--expect-audio", action="store_true")
    ap.add_argument("--expect-subs", action="store_true")
    a = ap.parse_args()

    html = os.path.join(a.deck, "deck.html")
    mp4 = os.path.join(a.deck, "deck.mp4")
    rows, ok_all = [], True

    def add(name, ok, detail):
        nonlocal ok_all
        ok_all = ok_all and ok
        rows.append((name, ok, detail))

    html_txt = open(html, encoding="utf-8").read() if os.path.exists(html) else ""
    pages = html_txt.count('class="slide"')
    imgs = html_txt.count('class="fig"')
    subs = html_txt.count('class="sub"')
    titles = html_txt.count("<h1>") + html_txt.count("<h2>")

    add("① deck.html", bool(html_txt) and pages >= 3, "%d 页" % pages)
    add("② 每页有标题", pages > 0 and titles >= pages, "%d 标题 / %d 页" % (titles, pages))
    rate = (imgs / pages) if pages else 0
    add("③ 配图命中率", rate >= 0.4, "%d/%d = %.0f%%" % (imgs, pages, rate * 100))
    if a.expect_subs:
        has_subs = 'class="subs"' in html_txt and subs >= pages
        add("⑥ 硬字幕", has_subs, "body.subs=%s · .sub %d/%d"
            % ('class="subs"' in html_txt, subs, pages))

    if os.path.exists(mp4):
        p = probe(mp4)
        add("④ 分辨率", p.get("w") == 1920 and p.get("h") == 1080,
            "%sx%s" % (p.get("w"), p.get("h")))
        add("时长", p.get("dur", 0) >= 10, "%ss" % p.get("dur"))
        if a.expect_audio:
            add("⑤ 音轨", bool(p.get("has_audio")), "有" if p.get("has_audio") else "无")
        add("体积", os.path.getsize(mp4) > 500 * 1024,
            "%.1f MB" % (os.path.getsize(mp4) / 1024 / 1024))
    else:
        add("④ deck.mp4", False, "没有成片（只生成了 HTML？）")

    print("%-14s %-5s %s" % ("项", "结果", "读数"))
    print("-" * 60)
    for n, ok, d in rows:
        print("%-14s %-5s %s" % (n, "OK" if ok else "FAIL", d))
    print("-" * 60)
    print("判定 %s（%d 项，过 %d）" % ("PASS" if ok_all else "FAIL",
                                     len(rows), sum(1 for r in rows if r[1])))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
