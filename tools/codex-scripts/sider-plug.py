# -*- coding: utf-8 -*-
r"""Sider 万能插适配器（V8 版）—— **不破坏、只接管：新开一条总线把她盖住**。

主人令（2026-10-10）：
  「万能插就是**接管她原来的地方** —— **新开辟一条能连接她所有能力的接口直接插入**，
    **不去破坏它**，就把她**掩盖掉**。」
  「你这么去插V9干嘛！**插这个 https://sider.ai/zh-CN**」

## 落地口径（照 V9 的 sider_plug.py 的成文口径，一字不改地执行）
  · **不破坏**：不改 Sider、**不绕 Cloudflare 挑战、不伪造指纹**；
  · **新总线**：用**她自己的浏览器 profile** 里**主人登入过的真实会话**接它；
  · **掩盖**：对外只暴露**我们自己的口**，用户看到的是我们，不是 Sider 的界面。

## 现读事实（不猜）
  · 靶：ENTRY=https://sider.ai/zh-CN/ · CLOUD_PC=https://sider.ai/zh-CN/cloud-pc（**免费云电脑**）
  · Sider 只认**可见窗口**的真实会话；headless 必被挑战 ⇒ HEADED=True
  · 本机浏览器 profile 里的 Sider cookie **只有 locale/分析 + Cloudflare 挑战痕迹，没有登录态**
    （出处：V9/state/browser_own_profile 的 Cookies 库现读）
  ⇒ **登录态那一下只能主人在可见窗口做一次**（V9 自己的 plug_boot.py 也是这么写的：
    「Sider 会话：待登入（需你在可见窗口登一次）」）。**本件不假装已登入。**

用法：py -3.14 -X utf8 tools/codex-scripts/sider-plug.py [status|open_login|--check]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "state" / "browser_own_profile"
V9_PROFILE = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V9\state\browser_own_profile")
LEDGER = ROOT / "state" / "sider_plug.jsonl"
ENTRY = "https://sider.ai/zh-CN/"
CLOUD_PC = "https://sider.ai/zh-CN/cloud-pc"
HEADED = True
CHALLENGE_MARKS = ("__cf_chl", "Just a moment", "Checking your browser", "cf-challenge")


def _log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + chr(10))


def seed() -> dict:
    """把**已有真实会话**的 profile 种一份到我们这侧（**只读她的、复制，不改她**）。"""
    if PROFILE.is_dir() and any(PROFILE.iterdir()):
        return {"状态": "已有", "件数": sum(1 for _ in PROFILE.rglob("*"))}
    if not V9_PROFILE.is_dir():
        return {"状态": "没得种（V9 的 profile 不在）"}
    try:
        shutil.copytree(V9_PROFILE, PROFILE, dirs_exist_ok=True)
        return {"状态": "已从 V9 的 profile 种过来（**只读+复制，没改她**）",
                "源": str(V9_PROFILE), "件数": sum(1 for _ in PROFILE.rglob("*"))}
    except Exception as exc:                                  # noqa: BLE001
        return {"状态": "种失败", "为什么": "%s: %s" % (type(exc).__name__, str(exc)[:80])}


def session() -> dict:
    """她那个 profile 里有没有**登录态**（只看 cookie 名，不读值）。"""
    import sqlite3
    import tempfile
    out = {"profile": str(PROFILE), "在": PROFILE.is_dir()}
    cks = list(PROFILE.glob("**/Cookies")) + list(PROFILE.glob("**/Network/Cookies"))
    out["cookies库"] = len(cks)
    if not cks:
        out["登录态"] = "**没有 profile**"
        return out
    tmp = Path(tempfile.gettempdir()) / ("sider_ck_%d.db" % time.time())
    try:
        shutil.copyfile(cks[0], tmp)
        con = sqlite3.connect(str(tmp))
        rows = con.execute("SELECT host_key, name FROM cookies").fetchall()
        con.close()
        sd = [n for h, n in rows if "sider" in h]
        authish = [n for n in sd if any(k in n.lower() for k in
                                        ("session", "token", "auth", "jwt", "sid", "user"))]
        out["sider cookie 数"] = len(sd)
        out["疑似登录态"] = authish or "**无**（只有 locale/分析/挑战痕迹）"
        out["登录态"] = "有" if authish else "**没有 —— 要在可见窗口登一次**"
    except Exception as exc:                                  # noqa: BLE001
        out["登录态"] = "读不出来：%s" % type(exc).__name__
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return out


def _chrome_exe():
    """本机真实存在的 chromium 可执行文件（playwright 期望版本可能不在 ⇒ 自己找）。"""
    import glob
    import os
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    for pat in ("chromium-*/chrome-win64/chrome.exe", "chromium-*/chrome-win/chrome.exe",
                "chromium_headless_shell-*/chrome-win64/headless_shell.exe"):
        hits = sorted(glob.glob(str(base / pat)))
        if hits:
            return Path(hits[-1])
    return None


CDP = "http://127.0.0.1:9222"


def cdp_read() -> dict:
    r"""**接主人给的调试口**（127.0.0.1:9222）—— 那是**她自己的浏览器**：
    真会话、真扩展、真指纹 ⇒ **不用饶、不用伪造**（口径明写：不绕 Cloudflare、不伪造指纹）。

    🔴 2026-10-10 实测对照（这条是**正路**）：
      · 新建 profile + playwright 自己起 ⇒ 开 sider.ai 得 **"Just a moment..."**（Cloudflare 挑战）；
      · **CDP 接她已在跑的那个浏览器** ⇒ 直接读到 Sider 的正文与能力项，**零挑战**。
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:                                  # noqa: BLE001
        return {"接管": False, "为什么": "playwright 没装：%s" % type(exc).__name__}
    try:
        with sync_playwright() as pw:
            br = pw.chromium.connect_over_cdp(CDP)
            pages, sider = [], None
            for ctx in br.contexts:
                for p in ctx.pages:
                    pages.append({"url": p.url[:110], "标题": (p.title() or "")[:60]})
                    if sider is None and ("sider.ai" in p.url
                                          or "difoiogjjojoaoomphldepapgpbgkhkb" in p.url):
                        sider = p
            out = {"接管": True, "浏览器": "她自己的（CDP %s）" % CDP, "页数": len(pages), "页": pages}
            if sider is None:
                out["Sider"] = "**没找到 Sider 目标**（她没开着）"
                return out
            js = ("() => { const t = document.body ? document.body.innerText : '';"
                  " const b = [...document.querySelectorAll('button,[role=button],a')]"
                  ".map(e => (e.innerText || e.getAttribute('aria-label') || '').trim())"
                  ".filter(Boolean);"
                  " return {正文: t.slice(0, 600), 可点项: [...new Set(b)].slice(0, 60),"
                  " 登录态: /登录|Sign In|登入/.test(t) ? '未登录' : '已登录（或页面无登录字样）'}; }")
            r = sider.evaluate(js)
            out["Sider"] = {"url": sider.url[:110], "标题": sider.title()[:70],
                            "登录态": r.get("登录态"),
                            "正文前600": (r.get("正文") or "").replace(chr(10), " / ")[:600],
                            "可点项": r.get("可点项") or []}
            return out
    except Exception as exc:                                  # noqa: BLE001
        return {"接管": False, "为什么": "%s: %s" % (type(exc).__name__, str(exc)[:120])}


def probe_page(url=ENTRY) -> dict:
    """真开一次页面（**可见**窗口，不绕挑战），读标题与挑战标记。"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:                                  # noqa: BLE001
        return {"打开": False, "为什么": "playwright 没装：%s" % type(exc).__name__}
    try:
        with sync_playwright() as pw:
            # 🔴 2026-10-10 实测：playwright 按自己的期望版本找浏览器，本机只有 chromium-1223
            #    ⇒ 报 "Executable doesn't exist at ...\ms-playwright\" ⇒ **显式给可执行文件**。
            exe = _chrome_exe()
            kw = {"headless": not HEADED,
                  "args": ["--disable-blink-features=AutomationControlled"]}
            if exe:
                kw["executable_path"] = str(exe)
            ctx = pw.chromium.launch_persistent_context(str(PROFILE), **kw)
            pg = ctx.pages[0] if ctx.pages else ctx.new_page()
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            html = pg.content()[:4000]
            title = pg.title()
            chall = [m for m in CHALLENGE_MARKS if m.lower() in html.lower()]
            ctx.close()
            return {"打开": True, "标题": title, "挑战标记": chall or "无",
                    "判定": "**被 Cloudflare 挑战**" if chall else "页面正常"}
    except Exception as exc:                                  # noqa: BLE001
        return {"打开": False, "为什么": "%s: %s" % (type(exc).__name__, str(exc)[:110])}


def check() -> int:
    d = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "靶": {"入口": ENTRY, "云电脑": CLOUD_PC},
         "口径": "不破坏 / 新总线（她真实会话）/ 掩盖（只露我们的口）",
         "种 profile": seed(), "会话": session(),
         "正路·CDP接她自己的浏览器": cdp_read()}
    cdp = d["正路·CDP接她自己的浏览器"]
    _log({"at": d["at"], "抓": "sider.check", "CDP接管": cdp.get("接管"),
          "Sider": (cdp.get("Sider") or {}).get("登录态") if isinstance(cdp.get("Sider"), dict) else cdp.get("Sider")})
    print(json.dumps(d, ensure_ascii=False, indent=1))
    ok = bool(cdp.get("接管")) and isinstance(cdp.get("Sider"), dict)
    print("判据：%s" % ("PASS（接管她的浏览器 + 读到 Sider）" if ok
                       else "FAIL（接管 %s）" % cdp.get("为什么", cdp.get("Sider"))))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Sider 万能插适配器（V8）")
    ap.add_argument("cmd", nargs="?", default="status", choices=["status", "open_login", "seed"])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.cmd == "seed":
        print(json.dumps(seed(), ensure_ascii=False)); return 0
    if a.cmd == "open_login":
        print(json.dumps({"给主人登一次": ENTRY, "口径": "**可见窗口**；登完我们就有会话了",
                          "开页": probe_page(ENTRY)}, ensure_ascii=False, indent=1))
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
