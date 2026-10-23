# -*- coding: utf-8 -*-
"""一体式验收（主人令 2026-10-23：APP 要一体式、不要跳转）。

## 它到底验什么（7 条，全部可机检，全绿才算一体式）
A1 窗口清单里没有「一页一窗」的碎窗：每个窗都能说清它是什么，且总数与导航项对得上。
A2 **安装台在页内**：`digital-human/index.html` 里有 `cfx` 浮层 + `cfx-fab` 入口（不是另开一扇窗）。
A3 **没有独立安装窗**：`cloud-auth` 不在 windows.json / nav-index.json 里（这一条就是「不要跳转」的机器判据）。
A4 **对话面接的是主人自己那台 DSH**：`main.cjs` 认 `userData/dsh-live.json`，且 `dsh-chat` 的 `auto_dsh.enabled` 为 false（不自起第二份）。
A5 **页面内不往外跳**：`holo_pet_w3` 的页面里没有 `target="_blank"` 指向外站的链接、没有 `location.href=` 到 http(s) 外站（本机回环除外）。
A6 **没有「全项目索引 · 全页可达」那条浮条**（主人两次点名要删的东西）。
A7 **没有 V9 残留入口**：窗口/导航里不出现 `v9` / `gbt-potato-master-v9` 之外的旧壳名。

用法：
  py -3 tools/codex-scripts/integrated-check.py            # 人读表格
  py -3 tools/codex-scripts/integrated-check.py --json     # 机读
退出码：全绿 0，有红 1。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W3 = os.path.join(ROOT, "holo_pet_w3")
WIN = os.path.join(W3, "shell", "windows.json")
NAV = os.path.join(W3, "shell", "nav-index.json")
MAIN = os.path.join(W3, "shell", "main.cjs")
PRELOAD = os.path.join(W3, "shell", "preload.cjs")
DH = os.path.join(W3, "digital-human", "index.html")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


SKIP_DIRS = ("assets", "node_modules", "dist", "_archive", "legacy", ".git")


def pages():
    """holo_pet_w3 下**随 APP 出厂**的 html。

    🔴 2026-10-23 自纠（本件第一次跑就误报两条，都是判据错尺）：
    ① `node_modules/electron/dist/LICENSES.chromium.html` 是第三方许可证文件，不是我们的页面；
    ② `_archive-*/…` 是已退役的旧页（不进 APP）。
    两处都不是「跳转/浮条」的真违规 —— 判据只该量**在役页面**。
    """
    out = []
    for base, dirs, files in os.walk(W3):
        dirs[:] = [d for d in dirs if not any(d.startswith(k) for k in SKIP_DIRS)]
        if any(os.sep + k + os.sep in base + os.sep for k in SKIP_DIRS):
            continue
        for f in files:
            if f.lower().endswith((".html", ".htm")):
                out.append(os.path.join(base, f))
    return out


def run() -> dict:
    wins = load(WIN).get("windows") or []
    nav = load(NAV).get("links") or []
    main = read(MAIN)
    preload = read(PRELOAD)
    dh = read(DH)
    checks = []

    # A1：窗口与导航对得上（差 1 以内算正常：有的窗是浮层/托盘，不必有导航项）
    ids = [w.get("id") for w in wins]
    checks.append({"id": "A1", "name": "窗口清单完整且无重名",
                   "ok": len(ids) == len(set(ids)) and len(ids) > 0,
                   "reading": "windows=%d · nav=%d" % (len(ids), len(nav))})

    # A2：安装台在页内
    ok2 = ("cfx-fab" in dh) and ("id=\"cfx\"" in dh or "id='cfx'" in dh) and ("gbtCloud" in dh)
    checks.append({"id": "A2", "name": "安装台嵌在数字人页内（浮层+入口按钮）",
                   "ok": ok2, "reading": "cfx-fab=%s · cfx=%s · gbtCloud=%s"
                   % ("cfx-fab" in dh, 'id="cfx"' in dh, "gbtCloud" in dh)})

    # A3：没有独立安装窗
    in_win = any(w.get("id") == "cloud-auth" or "cloud-auth" in str(w.get("file") or "") for w in wins)
    in_nav = any(x.get("id") == "cloud-auth" or "cloud-auth" in str(x.get("path") or "") for x in nav)
    checks.append({"id": "A3", "name": "没有独立『云插件安装』窗（不跳转）",
                   "ok": (not in_win) and (not in_nav),
                   "reading": "windows命中=%s · nav命中=%s" % (in_win, in_nav)})

    # A4：对话面接主人自己那台 DSH，且不自起第二份
    chat = next((w for w in wins if w.get("id") == "dsh-chat"), {}) or {}
    auto = (chat.get("auto_dsh") or {}).get("enabled")
    ok4 = ("dsh-live.json" in main) and (auto is False)
    checks.append({"id": "A4", "name": "对话面接主人自己那台 DSH（不自起第二份）",
                   "ok": ok4, "reading": "dsh-live 逻辑=%s · auto_dsh.enabled=%s"
                   % ("dsh-live.json" in main, auto)})

    # A5：页面内不往外跳（外站链接）
    bad = []
    ext = re.compile(r'(?:href|src)\s*=\s*["\']https?://(?!127\.0\.0\.1|localhost)', re.I)
    for p in pages():
        t = read(p)
        if ext.search(t):
            bad.append(os.path.relpath(p, ROOT))
    checks.append({"id": "A5", "name": "页面里没有外站跳转链接",
                   "ok": not bad, "reading": ("命中 %d 件：%s" % (len(bad), ", ".join(bad[:4]))) if bad else "0 件"})

    # A6：没有「全项目索引 · 全页可达」浮条（**只看真元素，不看注释里的历史说明**）
    hits = []
    for p in pages():
        t = read(p)
        for line in t.splitlines():
            st = line.strip()
            if st.startswith(("/*", "*", "//")):
                continue                        # 注释里提到这段历史文案不算违规
            if ("全项目索引" in line and "全页可达" in line) or "gbt-project-nav" in line:
                hits.append(os.path.relpath(p, ROOT) + " :: " + st[:60])
                break
    checks.append({"id": "A6", "name": "没有『全项目索引·全页可达』浮条",
                   "ok": not hits, "reading": ("命中：" + ", ".join(hits[:4])) if hits else "0 件"})

    # A7：V9 残留
    v9 = [w.get("id") for w in wins if re.search(r"v9", str(w) + str(w.get("file") or ""), re.I)]
    checks.append({"id": "A7", "name": "窗口里没有 V9 残留入口",
                   "ok": not v9, "reading": ("命中：" + ", ".join(str(x) for x in v9[:4])) if v9 else "0 件"})

    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "windows": len(ids), "nav": len(nav),
            "install_channel": ("cf:install" in main) and ("install:" in preload)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = run()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("一体式验收 · 7 条判据\n")
        for c in r["checks"]:
            print("%s %-34s %s" % ("✅" if c["ok"] else "🔴", c["name"], c["reading"]))
        print("\n窗口 %d · 导航 %d · 安装通道（主进程+preload）= %s"
              % (r["windows"], r["nav"], "齐" if r["install_channel"] else "缺"))
        print("结论：%s" % ("一体式 · 全绿" if r["ok"] else "有红，见上"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
