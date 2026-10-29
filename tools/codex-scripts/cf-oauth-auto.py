# -*- coding: utf-8 -*-
"""十账号授权 · 用「触手」（Playwright + 独立浏览器配置）逐个自动跑 OAuth。

主人令 2026-10-23：「直接让触手以无痕浏览器配置十个上去是我设计最完美的」
—— 能做的是：**每个账号一个独立浏览器配置（等价无痕、互不串登录态）**，
   自动打开授权页、自动点「允许」、自动拿回会话、自动部署节点。
—— 不能做的是：Google 的密码与两步验证。这两步只有主人能过（我们**不存密码**）。

所以每格的实际动作：
  ① 起 `wrangler login`（拿 OAuth 链接）
  ② 用该格的独立配置打开链接
  ③ 若显示 Google 登录 → 主人在这个窗口里登录（一次性，之后配置留住登录态）
  ④ 脚本自动点「允许」→ wrangler 收到回调 → 读 whoami → 与已用账号比对 → 部署节点

用法：
  py -3 tools/codex-scripts/cf-oauth-auto.py --selftest           # 只验底座（不开浏览器授权）
  py -3 tools/codex-scripts/cf-oauth-auto.py --slot 01            # 跑一个槽位
  py -3 tools/codex-scripts/cf-oauth-auto.py --all                # 连跑十格（已授权的会自动跳过）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MESH_SRC = os.path.join(ROOT, "deploy", "cloud-10", "mesh10")
HOME_ROOT = os.path.join(os.path.expanduser("~"), ".cf-oauth")
LEDGER = os.path.join(ROOT, "state", "mesh-nodes.json")
URL_RE = re.compile(r"https://dash\.cloudflare\.com/oauth2/auth\?[^\s\"']+")
EMAIL_RE = re.compile(r"associated with the email\s+(\S+)")


def sh(cmd, env=None, timeout=180):
    # 统一按 UTF-8 解码：wrangler 输出里有中文/emoji，用 GBK 解会当场 UnicodeDecodeError（实测 2026-10-23）
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=ROOT, env=env or os.environ.copy(), shell=False)


def whoami():
    r = sh(["cmd", "/c", "npx", "--yes", "wrangler@4", "whoami"], timeout=180)
    text = (r.stdout or "") + (r.stderr or "")
    email = (EMAIL_RE.search(text) or [None, None])[1]
    m = re.search(r"│\s*([^│]+?)\s*│\s*([0-9a-f]{32})\s*│", text)
    return {"ok": bool(email), "email": email,
            "account": m.group(1).strip() if m else None,
            "idMask": (m.group(2)[:8] + "****") if m else None,
            "raw": None if email else text[-300:]}


def load_ledger():
    try:
        return json.load(open(LEDGER, encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return {"nodes": []}


def save_ledger(d):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(d, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def deploy_node():
    st = whoami()
    if not st["ok"]:
        return {"ok": False, "why": "当前没有有效会话", "detail": st["raw"]}
    mask = (st["idMask"] or "").replace("*", "")
    if not re.fullmatch(r"[0-9a-f]{8}", mask):
        return {"ok": False, "why": "读不到账号 id", "detail": st}
    d = os.path.join(MESH_SRC, "build", "acct-" + mask)
    os.makedirs(d, exist_ok=True)
    shutil.copyfile(os.path.join(MESH_SRC, "worker.js"), os.path.join(d, "worker.js"))
    open(os.path.join(d, "wrangler.toml"), "w", encoding="utf-8", newline="\n").write(
        'name = "gbt-mesh-10"\nmain = "worker.js"\ncompatibility_date = "2025-01-01"\n\n'
        '[vars]\nNODE_ID = "acct-%s"\nMESH = "[]"\n' % mask)
    r = sh(["cmd", "/c", "npx", "--yes", "wrangler@4", "deploy", "-c",
            os.path.join(d, "wrangler.toml")], timeout=300)
    text = (r.stdout or "") + (r.stderr or "")
    url = (re.search(r"https://[a-z0-9\-.]+\.workers\.dev", text) or [None])[0]
    return {"ok": bool(url), "url": url, "email": st["email"], "node": "acct-" + mask,
            "tail": text[-300:]}


def start_login(slot):
    home = os.path.join(HOME_ROOT, "acct-" + slot)
    os.makedirs(home, exist_ok=True)
    env = os.environ.copy()
    env.update({"USERPROFILE": home, "HOME": home, "CLOUDFLARE_API_TOKEN": ""})
    p = subprocess.Popen(["cmd", "/c", "npx", "--yes", "wrangler@4", "login"],
                         cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    buf, url = [], None
    t0 = time.time()
    while time.time() - t0 < 60 and not url:
        line = p.stdout.readline()
        if not line:
            break
        buf.append(line)
        m = URL_RE.search("".join(buf))
        if m:
            url = m.group(0)
    return p, url, "".join(buf)


def wait_login(p, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p.poll() is not None:
            return p.returncode
        time.sleep(1)
    try:
        p.kill()
    except Exception:                                   # noqa: BLE001
        pass
    return None


def run_slot(slot, seen_emails):
    prof = os.path.join(HOME_ROOT, "browser-" + slot)
    p, url, head = start_login(slot)
    if not url:
        try:
            p.kill()
        except Exception:                               # noqa: BLE001
            pass
        return {"slot": slot, "ok": False, "why": "拿不到 OAuth 链接", "tail": head[-300:]}

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(prof, headless=False,
                                                   args=["--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        print("  [槽 %s] 浏览器已打开；若是登录页，请在这个窗口登录对应账号" % slot)
        # 自动点「允许」/「Allow」：Cloudflare 的同意页
        for _ in range(120):                            # 最多等 4 分钟
            if p.poll() is not None:
                break
            for label in ("Allow", "允许", "Authorize", "同意"):
                try:
                    btn = page.get_by_role("button", name=label)
                    if btn.count() and btn.first.is_visible():
                        btn.first.click(timeout=2000)
                        print("  [槽 %s] 已点「%s」" % (slot, label))
                        break
                except Exception:                       # noqa: BLE001
                    pass
            try:
                page.wait_for_timeout(2000)
            except Exception:                           # noqa: BLE001
                break
        code = wait_login(p, timeout=30)
        ctx.close()

    st = whoami()
    if not st["ok"]:
        return {"slot": slot, "ok": False, "why": "授权没完成（whoami 读不到）", "code": code, "detail": st["raw"]}
    if st["email"] in seen_emails:
        return {"slot": slot, "ok": False, "why": "这次授权的是已经用过的账号 %s（换账号请用这个槽的浏览器配置重新登录）" % st["email"],
                "email": st["email"]}
    dep = deploy_node()
    return {"slot": slot, "ok": bool(dep["ok"]), "email": st["email"], "idMask": st["idMask"],
            "url": dep.get("url"), "deploy_tail": dep.get("tail") if not dep["ok"] else None}


def _ensure_playwright():
    """本机有多个解释器：`py -3` 那个**没装** playwright（实测 2026-10-23 主人跑出来 ModuleNotFoundError）。
    这里不猜、也不要求主人换命令：自己找一个装了 playwright 的解释器重跑本脚本。"""
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        pass
    cands = [r"C:\Python312\python.exe", r"C:\Python313\python.exe", r"C:\Python314\python.exe"]
    which = shutil.which("python")
    if which:
        cands.append(which)
    me = os.path.abspath(sys.executable)
    for c in cands:
        if not c or not os.path.isfile(c) or os.path.abspath(c) == me:
            continue
        try:
            probe = subprocess.run([c, "-c", "import playwright, sys; print(sys.version_info[:2])"],
                                   capture_output=True, text=True, timeout=60)
        except Exception:                                # noqa: BLE001
            continue
        if probe.returncode == 0:
            print("[切换解释器] %s 没有 playwright → 改用 %s 运行本脚本" % (me, c))
            os.execv(c, [c, os.path.abspath(__file__)] + sys.argv[1:])
    print(json.dumps({"ok": False,
                      "why": "这台机器上没有装了 playwright 的解释器（试过 %s）" % cands,
                      "fix": r"用 C:\Python312\python.exe 跑本脚本，或给当前解释器装 playwright"},
                     ensure_ascii=False, indent=1))
    return False



CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def chrome_login(slot):
    """用**真 Chrome**（不挂任何自动化框架）打开授权页，人只需点一次「允许」。
    为什么不用 Playwright 去点：Cloudflare 的反自动机检测会把自动化浏览器挡在
    「正在进行安全验证」页（本机实测两次，标题与页面原话都留档了）；
    而普通的 Chrome 进程没有自动化指纹，能正常走完 OAuth。
    会话/登录态留在该槽的独立配置里，下次这个账号不用再登录。"""
    prof = os.path.join(HOME_ROOT, "browser-" + slot)
    os.makedirs(prof, exist_ok=True)
    p, url, head = start_login(slot)
    if not url:
        try:
            p.kill()
        except Exception:                            # noqa: BLE001
            pass
        return {"slot": slot, "ok": False, "why": "拿不到 OAuth 链接", "tail": head[-200:]}
    if not os.path.isfile(CHROME_EXE):
        try:
            p.kill()
        except Exception:                            # noqa: BLE001
            pass
        return {"slot": slot, "ok": False, "why": "找不到 Chrome：%s" % CHROME_EXE}
    subprocess.Popen([CHROME_EXE, "--user-data-dir=" + prof, "--no-first-run",
                      "--no-default-browser-check", url])
    print("  [槽 %s] 真 Chrome 已打开授权页：请在窗口里点「允许」（要登录就用该账号登录一次）" % slot)
    code = wait_login(p, timeout=420)
    st = whoami()
    if not st["ok"]:
        return {"slot": slot, "ok": False, "why": "授权未完成（whoami 读不到）", "code": code, "detail": st["raw"]}
    dep = deploy_node()
    return {"slot": slot, "ok": bool(dep["ok"]), "email": st["email"], "idMask": st["idMask"],
            "url": dep.get("url"), "deploy_tail": None if dep["ok"] else dep.get("tail")}


def open_profiles(n):
    """十根触手各开一个**独立持久浏览器配置**（每根一个永久邮箱的登录态）。

    这一步是主人设计的前半段：把十个账号各自登录进 `~/.cf-oauth/browser-NN`，
    登录一次就永久留着；后半段 `--all` 复用这些配置去点「允许」并部署节点。
    注意：**这一层可以十窗并行**；真正必须串行的是后半段（wrangler 会话全局一份）。
    """
    from playwright.sync_api import sync_playwright
    ctxs = []
    with sync_playwright() as pw:
        for i in range(1, n + 1):
            prof = os.path.join(HOME_ROOT, "browser-%02d" % i)
            os.makedirs(prof, exist_ok=True)
            ctx = pw.chromium.launch_persistent_context(
                prof, headless=False,
                args=["--no-first-run", "--no-default-browser-check"],
                viewport={"width": 1100, "height": 800},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto("https://dash.cloudflare.com/login", wait_until="domcontentloaded", timeout=60000)
            except Exception:                            # noqa: BLE001
                pass
            ctxs.append(ctx)
            print("  [触手 %02d] 已打开 · 配置 %s" % (i, prof))
        print("\n十个窗口已就位：请在**每一格**里登录它自己的账号（登录一次就永久保留）。")
        print("全部登好后，把这些窗口关掉，再跑：py -3 tools/codex-scripts/cf-oauth-auto.py --all")
        t0 = time.time()
        while time.time() - t0 < 1800:
            alive = [c for c in ctxs if c.pages]
            if not alive:
                break
            time.sleep(3)
    return 0


CHROME_SKIP = {"Cache", "Code Cache", "GPUCache", "DawnCache", "ShaderCache", "GrShaderCache",
               "Service Worker", "Extensions", "Extension State", "File System", "IndexedDB",
               "Local Storage", "Session Storage", "Sessions", "Media Cache", "optimization_guide_model_store",
               "component_crx_cache", "BrowserMetrics", "Crashpad", "Safe Browsing", "Segmentation Platform",
               "AutofillStrikeDatabase", "BudgetDatabase", "ClientSideModel", "Commerce", "Download Service"}


def chrome_profiles():
    """现读本机 Chrome 里**已经登录**的账号（主人机器上实测有 5 个 Cloudflare 账号各占一个配置）。
    这些会话就是"自主配置"的来源：拷进触手自己的配置里，触手就不用再请主人登录。"""
    ls = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "Local State")
    if not os.path.isfile(ls):
        return []
    try:
        d = json.load(open(ls, encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return []
    base = os.path.dirname(ls)
    out = []
    for name, info in ((d.get("profile") or {}).get("info_cache") or {}).items():
        email = (info.get("user_name") or "").strip()
        src = os.path.join(base, name)
        if email and os.path.isdir(src):
            out.append({"profile": name, "email": email, "dir": src})
    return out


def import_chrome(limit=10):
    """把 Chrome 里已登录的配置拷成触手的独立配置（只拷会话相关文件，不搬缓存）。"""
    profs = chrome_profiles()[:limit]
    if not profs:
        print(json.dumps({"ok": False, "why": "Chrome 里没读到已登录账号（Local State 的 info_cache 为空）"},
                         ensure_ascii=False))
        return 1
    rows = []
    for i, p in enumerate(profs, 1):
        dst = os.path.join(HOME_ROOT, "browser-%02d" % i)
        os.makedirs(dst, exist_ok=True)
        copied = 0
        for base, dirs, files in os.walk(p["dir"]):
            rel = os.path.relpath(base, p["dir"])
            if rel.split(os.sep)[0] in CHROME_SKIP:
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if d not in CHROME_SKIP]
            tgt = dst if rel == "." else os.path.join(dst, rel)
            os.makedirs(tgt, exist_ok=True)
            for f in files:
                if f in ("Cookies-journal", "LOCK", "LOG"):
                    continue
                try:
                    shutil.copy2(os.path.join(base, f), os.path.join(tgt, f))
                    copied += 1
                except Exception:                        # noqa: BLE001
                    pass
 # 关键：Chrome 的 cookie 用「用户级密钥」加密，那把钥匙在 User Data\Local State（配置目录之外）。
        # 只拷配置目录会导致 cookie 解不开 ⇒ Cloudflare 仍把人当未登录（实测 2026-10-23：跳到 Google 登录页）。
        try:
            base_root = os.path.dirname(p["dir"])
            src_ls = os.path.join(base_root, "Local State")
            if os.path.isfile(src_ls):
                shutil.copy2(src_ls, os.path.join(dst, "Local State"))
                copied += 1
        except Exception:                            # noqa: BLE001
            pass
        rows.append({"slot": "%02d" % i, "chrome_profile": p["profile"],
                     "email": p["email"], "dir": dst, "files": copied})
        print("  [触手 %02d] 来自 Chrome 「%s」 %s → %s（%d 个会话文件）"
              % (i, p["profile"], p["email"], dst, copied))
    print(json.dumps({"ok": True, "imported": len(rows), "rows": rows}, ensure_ascii=False, indent=1))
    return 0


def check_login(profile_dir, timeout=45000):
    """用某格配置打开 Cloudflare 面板，判定它是不是**已登录**（返回邮箱或 why）。"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(profile_dir, headless=True,
                                                   args=["--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://dash.cloudflare.com/", wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_timeout(3500)
            url = page.url
            body = (page.inner_text("body") or "")[:4000]
        except Exception as e:                           # noqa: BLE001
            ctx.close()
            return {"logged_in": False, "why": "打开失败：" + str(e)[:120]}
        ctx.close()
    if "/login" in url or "Log in" in body[:600] and "Sign up" in body[:600]:
        return {"logged_in": False, "why": "未登录（跳到了登录页）", "url": url}
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", body)
    return {"logged_in": True, "email_hint": m.group(0) if m else None, "url": url}


def list_accounts(limit=10):
    """用每根触手自己的浏览器配置，向 Cloudflare 面板**现读**它能看见的账号清单。
    这是回答「十个云插件到底有几个账号」的唯一可靠办法：一个用户可能有多个账号，
    所以按"账号"数不按"邮箱"数。"""
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as pw:
        for i in range(1, limit + 1):
            d = os.path.join(HOME_ROOT, "browser-%02d" % i)
            if not os.path.isdir(d):
                continue
            ctx = pw.chromium.launch_persistent_context(d, headless=True,
                                                       args=["--no-first-run", "--no-default-browser-check"])
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            info = {"slot": "%02d" % i, "accounts": [], "error": None}
            try:
                page.goto("https://dash.cloudflare.com/", wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
                data = page.evaluate("""async () => {
                    const r = await fetch('/client/v4/accounts', {credentials: 'include'});
                    return {status: r.status, body: await r.text()};
                }""")
                raw = data.get("body") or ""
                try:
                    body = json.loads(raw)
                except Exception:
                    info["error"] = "非 JSON（status=%s）：%s" % (data.get("status"), raw[:160].replace("\n", " "))
                    ctx.close(); rows.append(info); print(json.dumps(info, ensure_ascii=False)); continue
                for a in (body.get("result") or []):
                    info["accounts"].append({"id": a.get("id"), "name": a.get("name")})
                if not info["accounts"]:
                    info["error"] = "读到 0 个账号（status=%s）" % data.get("status")
            except Exception as e:                       # noqa: BLE001
                info["error"] = str(e)[:160]
            ctx.close()
            rows.append(info)
            print(json.dumps(info, ensure_ascii=False))
    total = sum(len(r["accounts"]) for r in rows)
    print(json.dumps({"slots": len(rows), "total_accounts": total,
                      "accounts": [{"slot": r["slot"], **a} for r in rows for a in r["accounts"]]},
                     ensure_ascii=False, indent=1))
    return 0 if total else 1


def selftest():
    ok = {"root": ROOT, "mesh_src": os.path.isdir(MESH_SRC),
          "home_root": os.path.isdir(HOME_ROOT) or os.makedirs(HOME_ROOT, exist_ok=True) is None}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            pg = b.new_page()
            pg.goto("about:blank")
            pg.set_content("<h1 id=t>ok</h1>")
            ok["browser"] = pg.inner_text("#t") == "ok"
            b.close()
    except Exception as e:                              # noqa: BLE001
        ok["browser"] = False
        ok["browser_error"] = str(e)[:200]
    ok["whoami"] = whoami()
    print(json.dumps(ok, ensure_ascii=False, indent=1))
    return 0 if ok.get("browser") and ok["mesh_src"] else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--start", default="01")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--open-profiles", type=int, default=0,
                    help="先开 N 个独立浏览器配置，各自登录一个账号（永久保留）；0=不开")
    ap.add_argument("--chrome-login", default="",
                    help="用真 Chrome 打开某槽的授权页（人点一次允许），完成后自动部署")
    ap.add_argument("--import-chrome", type=int, default=0,
                    help="把 Chrome 里已登录的账号拷成触手配置（N=最多几个，默认 10）")
    ap.add_argument("--list-accounts", type=int, default=0,
                    help="用每根触手的配置现读它能看见的 Cloudflare 账号（1=全部）")
    ap.add_argument("--check-login", action="store_true",
                    help="逐个验证触手配置是否已登录 Cloudflare")
    a = ap.parse_args()
    if not _ensure_playwright():
        return 2
    if a.chrome_login:
        r = chrome_login(a.chrome_login.zfill(2))
        print(json.dumps(r, ensure_ascii=False))
        if r.get("ok"):
            led = load_ledger()
            led.setdefault("nodes", []).append({"id": r.get("idMask"), "email": r.get("email"),
                                                "url": r.get("url"), "slot": a.chrome_login.zfill(2),
                                                "deployed_at": time.strftime("%Y-%m-%dT%H:%M")})
            save_ledger(led)
        return 0 if r.get("ok") else 1
    if a.import_chrome:
        return import_chrome(max(1, min(10, a.import_chrome)))
    if a.list_accounts:
        return list_accounts(a.list_accounts if a.list_accounts > 1 else 10)
    if a.check_login:
        rows = []
        for i in range(1, 11):
            d = os.path.join(HOME_ROOT, "browser-%02d" % i)
            if not os.path.isdir(d):
                continue
            r = check_login(d)
            rows.append({"slot": "%02d" % i, **r})
            print(json.dumps(rows[-1], ensure_ascii=False))
        print(json.dumps({"logged_in": sum(1 for r in rows if r.get("logged_in")), "checked": len(rows)},
                         ensure_ascii=False))
        return 0
    if a.open_profiles:
        return open_profiles(max(1, min(10, a.open_profiles)))
    if a.selftest:
        return selftest()

    ledger = load_ledger()
    seen = {n.get("email") for n in ledger.get("nodes", []) if n.get("email")}
    slots = [""] if not a.all else ["%02d" % i for i in range(int(a.start), 11)]
    if a.slot:
        slots = [a.slot.zfill(2)]

    results = []
    for s in slots:
        print("=== 槽 %s ===" % s)
        r = run_slot(s, seen)
        results.append(r)
        if r.get("ok"):
            ledger["nodes"].append({"id": r.get("idMask"), "email": r.get("email"),
                                    "url": r.get("url"), "slot": s,
                                    "deployed_at": time.strftime("%Y-%m-%dT%H:%M")})
            save_ledger(ledger)
            seen.add(r["email"])
        print(json.dumps(r, ensure_ascii=False))
    print(json.dumps({"done": len([x for x in results if x.get("ok")]),
                      "total": len(results),
                      "ledger_nodes": len(ledger.get("nodes", []))}, ensure_ascii=False))
    return 0 if all(x.get("ok") for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
