#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""taste_lint —— 把 taste-skill 的「家规」变成能在这里跑的判据（不需要 Node/Chrome）。

它原本的检查器是 Puppeteer/CDP 驱动的 Node 脚本，我们的 A19 跑不动、iSH 也没有 Chrome。
所以改法：**用现有 WebView 去量，用 Python 判**。

    tools/taste_collect.js   在真页面里取读数（字号/字体/渐变/阴影/发丝线/圆角/眉标/索引号/emoji/强调色）
    tools/taste_lint.py      按家规逐条判红，每条都带原文规则 id

用法：
    python3 tools/taste_lint.py --url minis://shared/gbtv8/holo_pet_w3/model-chat/index.html
    python3 tools/taste_lint.py --json /tmp/metrics.json     # 用已采集的读数重跑判定
    python3 tools/taste_lint.py --url … --app               # 按 app 界面判（默认开）

退出码：0 无 FAIL · 1 有 FAIL · 2 采集失败
"""
import argparse
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
COLLECT = os.path.join(TOOLS, "taste_collect.js")
OUT = "/tmp/taste_report.json"

# 规则出处：taste-skill/SKILL.md「House rules」与 references/{type,colour,copy}.md
RULES = {
    "heading-lines": ("FAIL", "标题最多两行（任何宽度）", "SKILL.md §House rules 第 1 条"),
    "first-title": ("FAIL", "首屏要有清楚的标题（页面唯一 h1）", "House rules 第 2 条"),
    "eyebrow": ("FAIL", "不许眉标/小标签贴在标题上方", "House rules 第 6 条"),
    "index-numbering": ("FAIL", "不许 01/02/Step N 索引编号", "House rules 第 8 条"),
    "mono": ("FAIL", "非代码处不许等宽字体", "House rules 第 7 条"),
    "hairline": ("FAIL", "不许发丝线（1px 框/分隔线）", "House rules 第 9 条"),
    "gradient": ("FAIL", "不许渐变", "House rules 第 10 条"),
    "shadow-rest": ("WARN", "静止物体不许阴影/发光（浮层除外）", "House rules 第 11 条"),
    "upper-tracked": ("FAIL", "不许全大写＋大字距小标签", "House rules 第 13 条"),
    "emoji": ("FAIL", "不许 emoji", "House rules 第 15 条"),
    "glass": ("FAIL", "不许玻璃拟态/毛玻璃", "House rules 第 15 条"),
    "typefaces": ("FAIL", "字体最多两款（通常一款）", "House rules 第 17 条"),
    "type-sizes": ("WARN", "一页最多 5 个字号", "Laws · Type"),
    "soft-radius": ("WARN", "9–16px「软圆角」是弱站默认；直角或全圆，一次定死", "Laws · Components"),
    "accent": ("WARN", "一底一墨一强调；强调色只落在动作上", "Laws · Colour"),
    "section-gap": ("WARN", "节间距要明显大于节内间距", "Laws · Space"),
}


def collect(url):
    script = open(COLLECT, encoding="utf-8").read()
    r = subprocess.run(["minis-browser-use", "navigate", "--url", url],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        return None, "navigate 失败: %s" % (r.stdout or r.stderr)[:200]
    r = subprocess.run(["minis-browser-use", "execute_js", "--script", script],
                       capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        return None, "execute_js 失败: %s" % (r.stdout or r.stderr)[:300]
    try:
        env = json.loads(r.stdout)
    except Exception:                                             # noqa: BLE001
        return None, "回包不是 JSON: %s" % r.stdout[:200]
    # minis-browser-use 把 execute_js 的返回值放在 data.text（不是 data.result）
    _d = env.get("data", {})
    res = _d.get("result") if "result" in _d else _d.get("text", env.get("result"))
    if isinstance(res, str):
        # CLI 会在返回值后面追加 "  tab_id: N"，必须切掉再解析
        res = res.split("\n  tab_id:")[0].strip()
        try:
            res = json.loads(res)
        except Exception:                                         # noqa: BLE001
            return None, "result 不是 JSON: %s" % str(res)[:200]
    if not isinstance(res, dict):
        return None, "拿不到读数: %s" % str(env)[:200]
    return res, None


def broken_links(full_html):
    """页面引用的本地 css/js 是不是真的存在。缺失的样式层会让每页各写各的 —— 
    全站扫描里那三件套（emoji/hairline/typefaces）每页重复出错，根因常在这里。"""
    import re as _re
    try:
        html = open(full_html, encoding="utf-8", errors="replace").read()
    except Exception:                                             # noqa: BLE001
        return []
    base = os.path.dirname(os.path.abspath(full_html))
    bad = []
    for m in _re.finditer(r'<(?:link|script)[^>]+(?:href|src)="([^"]+)"', html, _re.I):
        u = m.group(1)
        if u.startswith(("http://", "https://", "//", "data:", "minis://", "#")):
            continue
        pth = os.path.normpath(os.path.join(base, u.split("?")[0].split("#")[0]))
        if not os.path.exists(pth):
            bad.append(u)
    return sorted(set(bad))


def html_urls(root, limit=8, skip=("_archive", "vendor", "node_modules", ".git", ".bak")):
    """把一个目录下的 html 找出来，转成 minis:// 资源地址（页面能被 WebView 打开）。"""
    root = os.path.abspath(root)
    out = []
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames if not any(k in d for k in skip)]
        for f in sorted(files):
            if not f.endswith(".html") or any(k in f for k in skip):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, "/var/minis")
            out.append((full, "minis://" + rel.replace(os.sep, "/")))
    out.sort()
    return out[:limit] if limit else out


def scan(root, limit=8, app=True):
    rows = []
    for i, (full, url) in enumerate(html_urls(root, limit), 1):
        m, err = collect(url)
        if err:
            miss = broken_links(full)
            rows.append({"page": full, "url": url, "error": err,
                         "fails": (["broken-css"] if miss else []), "warns": [],
                         "missing": miss})
            print("  [%d] %-46s 采集失败: %s" % (i, os.path.basename(full), err[:40]))
            continue
        judged = judge(m, app=app)
        fails = [r["id"] for r in judged if r["level"] == "FAIL"]
        miss = broken_links(full)
        if miss:
            fails = ["broken-css"] + fails
        warns = [r["id"] for r in judged if r["level"] == "WARN"]
        rows.append({"page": full, "url": url, "fails": fails, "warns": warns,
                     "metrics": {k: m.get(k) for k in ("w", "h", "counts", "fontSizes",
                                                       "fontFamilies")}})
        print("  [%d] %-46s FAIL %d%s" % (i, os.path.relpath(full, os.path.abspath(root))[:46], len(fails),
                                          (" · " + ",".join(fails)) if fails else ""))
    return rows


def judge(m, app=True):
    out = []

    def add(rid, ok, detail):
        lvl, title, src = RULES[rid]
        out.append({"id": rid, "ok": bool(ok),
                    "level": "OK" if ok else lvl,
                    "rule": title, "src": src, "detail": str(detail)[:160]})

    heads = m.get("headings") or []
    over = [h for h in heads if h.get("lines", 1) > 2]
    add("heading-lines", not over,
        "超两行 %d 处: %s" % (len(over), "; ".join('%s「%s」%d行' % (h["tag"], h["text"][:14], h["lines"])
                                                  for h in over[:3])) if over else "%d 个标题都在两行内" % len(heads))

    h1 = [h for h in heads if h.get("tag") == "h1"]
    add("first-title", bool(h1), "h1: %s" % (h1[0]["text"][:30] if h1 else "没有 h1"))

    c = m.get("copy") or {}
    d = m.get("decor") or {}
    add("eyebrow", c.get("eyebrows", 0) == 0, "眉标候选 %s 处" % c.get("eyebrows"))
    add("index-numbering", c.get("indexNumbering", 0) == 0, "索引编号 %s 处" % c.get("indexNumbering"))
    add("emoji", c.get("emoji", 0) == 0, "emoji %s 个" % c.get("emoji"))
    add("mono", d.get("mono", 0) == 0, "代码外等宽 %s 处" % d.get("mono"))
    add("hairline", d.get("hairlines", 0) == 0, "发丝线 %s 处" % d.get("hairlines"))
    add("gradient", d.get("gradients", 0) == 0, "渐变 %s 处" % d.get("gradients"))
    add("shadow-rest", d.get("shadows", 0) == 0, "静止阴影 %s 处" % d.get("shadows"))
    add("upper-tracked", d.get("upperTracked", 0) == 0, "全大写大字距 %s 处" % d.get("upperTracked"))
    add("glass", d.get("glass", 0) == 0, "玻璃 %s 处" % d.get("glass"))

    fams = m.get("fontFamilies") or []
    sizes = m.get("fontSizes") or []
    add("typefaces", len(fams) <= 2, "%d 款: %s" % (len(fams), ", ".join(fams[:4])))
    add("type-sizes", len(sizes) <= 5, "%d 个字号: %s" % (len(sizes), sizes[:8]))
    add("soft-radius", d.get("softRadius", 0) == 0, "9–16px 软圆角 %s 处" % d.get("softRadius"))

    ac = (m.get("color") or {}).get("actionColors") or []
    add("accent", len(ac) <= 2, "%d 种动作色: %s" % (len(ac), ac[:3]))

    gaps = m.get("gaps") or []
    if app or len(gaps) < 2:
        out.append({"id": "section-gap", "ok": True, "level": "N/A",
                    "rule": RULES["section-gap"][1], "src": RULES["section-gap"][2],
                    "detail": "app 界面不按落地页节律判（%d 段间距）" % len(gaps)})
    else:
        ok = max(gaps) >= 2 * max(1, min(gaps))
        add("section-gap", ok, "间距样本 %s" % gaps[:6])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--json")
    ap.add_argument("--scan", help="扫一个目录下所有 html（全站闸）")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--app", action="store_true", default=True)
    ap.add_argument("--landing", action="store_true", help="按落地页判（不跳过节律/图）")
    a = ap.parse_args()

    if a.scan:
        print("全站扫描 %s（最多 %d 页）" % (a.scan, a.limit))
        t0 = __import__("time").time()
        rows = scan(a.scan, a.limit, app=not a.landing)
        bad = [r for r in rows if r.get("fails")]
        print("-" * 78)
        for r in rows:
            if r.get("error"):
                print("%-46s 采集失败" % os.path.basename(r["page"]))
            else:
                _rel = os.path.relpath(r["page"], os.path.abspath(a.scan))
                print("%-46s FAIL %-2d WARN %-2d %s" % (
                    _rel[:46], len(r["fails"]), len(r["warns"]),
                    ",".join(r["fails"][:4])))
        print("-" * 78)
        print("扫了 %d 页 · 有红 %d 页 · 用时 %.1fs" % (len(rows), len(bad),
                                                   __import__("time").time() - t0))
        json.dump(rows, open("/tmp/taste_scan.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("落盘 /tmp/taste_scan.json")
        return 1 if bad else 0

    if a.json:
        m = json.load(open(a.json, encoding="utf-8"))
        err = None
    elif a.url:
        m, err = collect(a.url)
    else:
        print("用法: taste_lint.py --url <minis://|http://> | --json <file>")
        return 2

    if err:
        print("采集失败：%s" % err)
        return 2

    rows = judge(m, app=not a.landing)
    fails = [r for r in rows if r["level"] == "FAIL"]
    warns = [r for r in rows if r["level"] == "WARN"]

    print("被试 %s · %sx%s · 元素 %d · 图 %d" % (
        m.get("url", "?")[-60:], m.get("w", "?"), m.get("h", "?"),
        (m.get("counts") or {}).get("elements", 0), (m.get("counts") or {}).get("images", 0)))
    print("%-16s %-5s %-44s %s" % ("规则", "结果", "读数", "出处"))
    print("-" * 104)
    for r in rows:
        print("%-16s %-5s %-44s %s" % (r["id"], r["level"], r["detail"][:44], r["src"]))
    print("-" * 104)
    print("FAIL %d · WARN %d · 通过 %d" % (len(fails), len(warns),
                                          sum(1 for r in rows if r["level"] == "OK")))
    json.dump({"metrics": m, "rows": rows}, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("落盘 %s" % OUT)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
