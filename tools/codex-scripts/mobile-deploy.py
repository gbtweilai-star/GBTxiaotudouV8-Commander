# -*- coding: utf-8 -*-
"""mobile-deploy -- 手机部署：打包 + 局域网地址 + 校验。"""
from __future__ import annotations
import argparse, json, shutil, socket, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "state" / "mobile-pack"
PROF = ROOT / "state" / "deploy-profiles.json"
# 2026-10-17 修（**手机版丢页** · 留痕 · 原口径 / 为什么翻 / 现口径）：
#   原口径：`["holo_pet_w3", "state/blueprints"]` ⇒ 手机包只有 **367 页**。
#   为什么翻（实测）：同一时刻电脑版/直达闸/设备注入用的是
#     `["holo_pet_w3", "state", "state/blueprints", "docs"]` ⇒ **757 页**；
#     差额 **390 页正是 `state/*.html`**（生成的面板/看板）——「手机电脑版本都要在，别丢了」
#     ⇒ 手机包漏掉这 390 页 = 手机上打不开它们。
#   现口径：**与 page-reach / device-deploy 同一份页目录清单**（单一真相），
#     并在 `pack()` 里按**去重后的解析路径**计数（`state` 已含 `state/blueprints`，
#     重复列举不会再重复拷）。
PAGE_DIRS = ["holo_pet_w3", "state", "state/blueprints", "docs"]
# 2026-10-17 事故剪枝（与 page-reach/device-deploy 同源 · 自反爆炸）：
#   手机包输出就在 `state/mobile-pack`，而 `state` 是页目录 ⇒ 打包会把**包自己**再拷进去。
#   实测失控到 **24,150 文件 / 54.7GB / 4,768 层**。⇒ 打包必须跳过产物目录，并加页数上限。
SKIP_PARTS = {".git", "node_modules", ".pylibs", "vendor", "_upstream", ".scratch",
              "mobile-pack", ".mimosa", "__pycache__", ".wrangler"}
MAX_PAGES = 3000


def _skip(p):
    return any(part in SKIP_PARTS for part in p.parts)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def pack(profile):
    prof = json.loads(PROF.read_text(encoding="utf-8"))
    p = prof["profiles"].get(profile) or prof["profiles"][prof["default"]]
    if PACK.is_dir() and not (PACK / profile).is_dir():
        pass
 # 2026-10-17 修（**苹果安卓都要 · 两包并存** · 留痕 · 原口径 / 为什么翻 / 现口径）：
    #   原口径：两档共用 `state/mobile-pack`，每次 `shutil.rmtree(PACK)` ⇒ 打安卓会**删掉苹果包**。
    #   为什么翻：主人令「手机是苹果安卓都有的哈」⇒ 必须**两档同时存在**，不能互相覆盖。
    #   现口径：每档一个子目录 `state/mobile-pack/<profile>/`，只清自己的子目录。
    out = PACK / profile
    if out.is_dir():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    seen = set()
    for d in PAGE_DIRS:
        b = ROOT / d
        if not b.is_dir():
            continue
        for f in b.rglob("*.html"):
            if _skip(f):                                # 产物目录（含 mobile-pack 自己）一律不拷
                continue
            key = str(f.resolve()).lower()          # 去重：state 已含 state/blueprints
            if key in seen:
                continue
            seen.add(key)
            if n >= MAX_PAGES:                          # fail-closed：失控就停
                raise SystemExit("手机包页数 > 上限 %d ⇒ 疑似产物自反，拒绝打包" % MAX_PAGES)
            tgt = out / d / f.relative_to(b)
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, tgt)
            n += 1
 # 2026-10-17 修（**数据页上手机变成瞎页** · 留痕 · 原口径 / 为什么翻 / 现口径）：
            #   原口径：只打 *.html ⇒ db-fleet / tentacles 这类数据页的伴生
            #     *-data.js 不在包里，手机打开只剩"读不到 xxx-data.js"兜底句；
            #     连首页壳的 window.js / ef_render.js 也没打（壳功能全瘫）。
            #   现口径：每个 html 把它**同目录**的 *.js 伴生文件一起打
            #     （数据 js + 壳脚本都因此齐活；不递归、不碰 node_modules）。
            for js in f.parent.glob("*.js"):
                if _skip(js):
                    continue
                jtgt = tgt.parent / js.name
                if not jtgt.exists():
                    shutil.copy2(js, jtgt)
    for extra in (ROOT / "holo_pet_w3" / "manifest.webmanifest", ROOT / "state" / "direct-index.json"):
        if extra.is_file():
            shutil.copy2(extra, out / extra.name)
    entry = out / "index.html"
    links = sorted(str(x.relative_to(out)).replace("\\", "/") for x in out.rglob("*.html") if x != entry)
    entry.write_text("<!doctype html><meta charset=\"utf-8\">" +
                     '<meta name="viewport" content="' + prof["profiles"][profile]["viewport"] + '">' +
                     '<meta name="apple-mobile-web-app-capable" content="yes">' +
                     '<meta name="theme-color" content="' + prof["profiles"][profile]["pwa"]["theme_color"] + '">' +
                     "<title>手机入口 · 小土豆V8</title>" +
                     "<body style=\"background:#0b0d10;color:#e8ecf1;font:16px/1.8 system-ui;padding:18px\">" +
                     "<h1>手机入口（" + profile + "）</h1><p>点任一页进入；每页顶部有直达条，任意页可一跳到任意页。</p><ul>" +
                     "".join('<li><a style="color:#8ab4ff" href="%s">%s</a></li>' % (x, x) for x in links[:400]) +
                     "</ul><p style=\"color:#7d8794;font-size:13px\">开发者：自由的风 · 守护者：公主土豆</p></body>",
                     encoding="utf-8")
    ip = lan_ip()
    print("手机包已出：" + str(out.relative_to(ROOT)) + " · 档 " + profile + " · 页 %d 张 · 入口 index.html" % n)
    print("手机打开方式：① 把 " + str(out.relative_to(ROOT)) + " 整个目录拷到手机，点 index.html；")
    print("              ② 或在本机起静态服务器，手机浏览器输：http://" + ip + ":8080/" + profile + "/index.html")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", action="store_true")
    ap.add_argument("--profile", default="apple-iphone17")
    a = ap.parse_args()
    if a.pack:
        return pack(a.profile)
    print("参数：--pack [--profile apple-iphone17|android-mobile]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
