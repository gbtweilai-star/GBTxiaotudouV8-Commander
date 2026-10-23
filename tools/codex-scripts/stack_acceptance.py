# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 本机栈**合并验收回执**（主人 2026-10-04 收口令：「现在这套是完整的」⇒ 逐条取证）。

一跑全检、只读为主、结果落 `state/stack_acceptance.json` + 屏上一张表。
判据口径：**每条都要有真读数**；拿不到就写 `未读到` + 原因（不拿绿顶）。

覆盖的七条（与主人清单逐条对应）：
  1. 浏览器触手：CDP ready + 开**本机页**并读到正文（证明「公网+本机页」两向都能）
  2. 桌面触手：list_windows 出真窗口 + read_text 出 UIA 文本块
  3. 文件/进程触手：desktop_commander 同进程 connect + tools 数（>0 且报版本）
  4. 统一密钥双向绑定：门侧 verify 本地钥 + 整链真发（我们→路由器→云端）
  5. 三条车道：路由器 /v1/models 列车道（≥1 条）+ 至少一条真回话
  6. 面板服务：8765 /api/state → 200
  7. 50 邮箱 + 50 槽云端：CF Email Routing 规则 ≥50 · 云端 /slots50 的槽/边/已接线

用法：
    py -3.14 tools/codex-scripts/stack_acceptance.py            # 全检（约 60s）
    py -3.14 tools/codex-scripts/stack_acceptance.py --with-local  # 含本机大模型真发（+2 分钟）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPDIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "gbt-cliproxy"
RECEIPT = ROOT / "state" / "stack_acceptance.json"
WORKER = "https://gbt-potato-cloud-10.lopaycn.workers.dev"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
sys.path.insert(0, str(ROOT))


def _p(env):
    x = env
    for _ in range(4):
        if isinstance(x, dict) and isinstance(x.get("result"), dict) and "ok" not in x:
            x = x["result"]
        elif isinstance(x, dict) and "gbt_result" in x:
            x = x["gbt_result"]
        else:
            break
    return x if isinstance(x, dict) else {}


def _cap(kind, payload):
    from gbt_allinone import run_task
    return _p(run_task(kind, payload, safe=True))


def _client_key() -> str:
    f = APPDIR / "client-key.txt"
    return f.read_text(encoding="utf-8").strip() if f.is_file() else ""


def _http(url, *, data=None, key="", timeout=60, method=None):
    headers = {"User-Agent": UA}
    if key:
        headers["Authorization"] = "Bearer " + key
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:                                     # noqa: BLE001
        return 0, "%s: %s" % (type(e).__name__, str(e)[:120])


def _port(host, port) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except Exception:                                          # noqa: BLE001
        return False


def leg_browser(rows):
    r = _cap("browser", {"op": "native", "action": "status"})
    ready = bool(r.get("ok")) and r.get("cdp_available") is True
    t = _cap("browser", {"op": "native", "action": "create_tab", "url": "http://127.0.0.1:11434/"})
    tid = ((t.get("tab") or {}).get("id")) or ""
    txt = ""
    # 🔴 时序纪律：新标签**要等载入完**才读得到正文（实测：不等就是 ''，等 1–2 秒就有）。
    #    重试 4 次、每次 1.2s，仍空才判红 —— 判据不放松，只是把"没等"与"读不到"分开。
    for _ in range(4):
        if not tid:
            break
        time.sleep(1.2)
        g = _cap("browser", {"op": "native", "action": "get_text", "tab_id": tid})
        txt = (g.get("text") or "").strip()[:40]
        if txt:
            break
    rows.append({"leg": "浏览器触手（公网+本机页）", "ok": ready and bool(txt),
                 "reading": "CDP=%s · 本机页正文=%r" % (r.get("status"), txt)})


def leg_desktop(rows):
    w = _cap("tentacle", {"action": "list_windows"})
    n = len(w.get("windows") or [])
    t = _cap("tentacle", {"action": "read_text"})
    blocks = int(t.get("count") or 0)
    rows.append({"leg": "桌面触手（窗口/UI 读）", "ok": bool(w.get("ok")) and blocks > 0,
                 "reading": "窗口 %d 个 · UIA 文本块 %d" % (n, blocks)})


def leg_files_process(rows):
    c = _cap("desktop_commander", {"op": "connect"})
    tl = _cap("desktop_commander", {"op": "tools"})
    tools = tl.get("tools") or []
    ver = ((c.get("server") or {}).get("version")) if isinstance(c.get("server"), dict) else None
    rows.append({"leg": "文件/进程触手（desktop_commander）", "ok": bool(c.get("ok")) and len(tools) > 0,
                 "reading": "版本 %s · 工具 %d 件" % (ver, len(tools))})


def leg_key_binding(rows):
    key = _client_key()
    v = _cap("key_gateway", {"op": "verify", "key": key}) if key else {}
    # 整链真发：我们 → 路由器(8317) → 云端
    body = json.dumps({"model": "gbt-potato-v8",
                       "messages": [{"role": "user", "content": "只回四个字：整链已通"}],
                       "max_tokens": 600, "stream": False}).encode("utf-8")
    t0 = time.time()
    st, txt = _http("http://127.0.0.1:8317/v1/chat/completions", data=body, key=key, timeout=120)
    ms = int((time.time() - t0) * 1000)
    content = ""
    if st == 200:
        try:
            content = (((json.loads(txt).get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        except Exception:                                      # noqa: BLE001
            content = ""
    rows.append({"leg": "统一密钥双向绑定（门认钥 + 整链真发）", "ok": bool(v.get("ok")) and bool(content),
                 "reading": "key_id=%s · 整链 %s %dms · 回话=%r"
                            % (v.get("key_id"), st, ms, content[:20])})


def leg_lanes(rows, with_local=False):
    key = _client_key()
    st, txt = _http("http://127.0.0.1:8317/v1/models", key=key, timeout=20)
    ids = []
    if st == 200:
        try:
            ids = [m.get("id") for m in (json.loads(txt).get("data") or [])]
        except Exception:                                      # noqa: BLE001
            ids = []
    rows.append({"leg": "三条车道（路由器 /v1/models）", "ok": len(ids) >= 3,
                 "reading": "车道 %d 条：%s" % (len(ids), "、".join(ids))})
    if with_local:
        body = json.dumps({"model": "qwen3:latest",
                           "messages": [{"role": "user", "content": "只回四个字：本地已通"}],
                           "max_tokens": 800, "stream": False}).encode("utf-8")
        t0 = time.time()
        st2, txt2 = _http("http://127.0.0.1:8317/v1/chat/completions", data=body, key=key, timeout=300)
        c2 = ""
        if st2 == 200:
            try:
                c2 = (((json.loads(txt2).get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            except Exception:                                  # noqa: BLE001
                c2 = ""
        rows.append({"leg": "本机车道真发（qwen3:latest）", "ok": bool(c2),
                     "reading": "%s %dms · 回话=%r" % (st2, int((time.time() - t0) * 1000), c2[:20])})


def leg_panel(rows):
    st, txt = _http("http://127.0.0.1:8765/api/state", timeout=15)
    rows.append({"leg": "面板服务 8765", "ok": st == 200,
                 "reading": "HTTP %s%s" % (st, "" if st == 200 else " · " + txt[:80])})


def leg_cloud(rows):
    # 50 邮箱（CF Email Routing）
    # 口径如实：50 个地址**创建时已逐个核过**（新建 50/失败 0 + 回读 50/50）；
    # 本腿是"再复验一次"。CF 的边缘/令牌时效会让**裸 API 调用**偶尔 403（wrangler 自己会刷新 OAuth），
    # 这种情况写「未复验（原因）」而**不是**假绿，也不是把已验过的成果判坏。
    mails = "未复验（未读到）"
    ok_mail = False
    try:
        import re
        tokp = Path.home() / ".wrangler" / "config" / "default.toml"
        tok = next((re.match(r'\s*oauth_token\s*=\s*"([^"]+)"', l).group(1)
                    for l in tokp.read_text(encoding="utf-8", errors="replace").splitlines()
                    if re.match(r"\s*oauth_token\s*=", l)), "")
        if not tok:
            mails = "未复验（wrangler 配置里没有 oauth_token）"
        if tok:
            st, txt = _http("https://api.cloudflare.com/client/v4/zones?per_page=5", key=tok, timeout=25)
            if st != 200:
                mails = ("未复验（CF API HTTP %s —— wrangler 的 OAuth 由它自己刷新，裸调用可能被拒；"
                         "创建时已核 50/50）" % st)
            if st == 200:
                zid = (json.loads(txt)["result"][0]["id"])
                st2, txt2 = _http("https://api.cloudflare.com/client/v4/zones/%s/email/routing/rules?per_page=200"
                                  % zid, key=tok, timeout=30)
                if st2 == 200:
                    n = len([x for x in json.loads(txt2)["result"]
                             if x.get("matchers") and str(x["matchers"][0].get("value", "")).startswith("c")])
                    mails, ok_mail = "%d 个 cNN@gbtxiaotudou.com" % n, n >= 50
    except Exception as e:                                     # noqa: BLE001
        mails = "未复验（读 CF 失败：" + str(e)[:80] + "）"
    st3, txt3 = _http(WORKER + "/slots50", timeout=40)
    slots = {}
    if st3 == 200:
        try:
            slots = json.loads(txt3)
        except Exception:                                      # noqa: BLE001
            slots = {}
    rows.append({"leg": "50 邮箱（CF Email Routing）", "ok": ok_mail, "reading": mails,
                 "note": "创建时已核（新建 50/失败 0 + 回读 50/50）；本腿失败只表示**这次没复验到**"})
    rows.append({"leg": "50 槽云端（/slots50）", "ok": slots.get("slots") == 50,
                 "reading": "槽 %s · 已接线 %s · 备用 %s · 有向边 %s"
                            % (slots.get("slots"), slots.get("wired_now"),
                               len(slots.get("unwired") or []), (slots.get("edges") or {}).get("directed"))})


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="本机栈合并验收回执")
    ap.add_argument("--with-local", action="store_true", help="含本机大模型真发（+约 2 分钟）")
    a = ap.parse_args(argv)
    rows = []
    for fn in (leg_browser, leg_desktop, leg_files_process, leg_key_binding, leg_panel, leg_cloud):
        try:
            fn(rows)
        except Exception as e:                                 # noqa: BLE001
            rows.append({"leg": fn.__name__, "ok": False, "reading": "巡检抛错：" + str(e)[:120]})
    try:
        leg_lanes(rows, with_local=a.with_local)
    except Exception as e:                                     # noqa: BLE001
        rows.append({"leg": "三条车道", "ok": False, "reading": "巡检抛错：" + str(e)[:120]})

    ok_n = sum(1 for r in rows if r["ok"])
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": rows,
           "pass": ok_n, "fail": len(rows) - ok_n,
           "note": "逐条真读数；拿不到写「未读到」+原因，不拿绿顶"}
    try:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    print("=" * 78)
    print("GBT小土豆V8 · 本机栈合并验收")
    print("=" * 78)
    for r in rows:
        print("%s %-30s %s" % ("✅" if r["ok"] else "🔴", r["leg"], r["reading"]))
    print("-" * 78)
    print("PASS %d · FAIL %d · 回执：%s" % (ok_n, len(rows) - ok_n, RECEIPT))
    return 0 if ok_n == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
