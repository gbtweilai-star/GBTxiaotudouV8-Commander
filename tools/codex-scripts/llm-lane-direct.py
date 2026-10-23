# -*- coding: utf-8 -*-
"""GBT小土豆V8 · LLM 车道「双向绑定 + 直通启动」（主人令 2026-10-14）。

## 为什么有这一件（真读数，不是设计稿）
主人令：**「把所有连接慢的使用触手加一条双向绑定，实现直通启动」**。
实测到的慢在哪（本机现读）：
  · 自家车道 `gbt-potato-v8`（RunPod Serverless `gbt-v8-live`，workersMin=0）**冷启动 92s~300s**；
    热机时同一发只要 **0.8s~2.2s** ⇒ 慢的不是模型，是「没人在的时候 worker 睡了」。
  · 代理 `CLIProxyAPI`（127.0.0.1:8317）此前**只能手工 up**；重启/登录后没人拉 ⇒ 第一条必然慢或直接不通。
  · 4446 老中继已死、31415 免费池没跑 —— 本件**不替它们续命**，只按车道表如实标注。

## 双向绑定（与仓里 `触手双向绑定架构` 同口径）
  · **A 向（框架/触手 → 车道）**：一条 base-url `http://127.0.0.1:8317/v1` 直达全部车道；
    进不去就**当场拉起**代理（自愈），再对冷启动车道打一发**保温请求**（keepalive）。
  · **B 向（车道 → 框架）**：把车道读数**回写**成框架读得到的一份状态
    `state/llm-lane-binding.json`（车道表 / 上游 worker 就绪数 / 上次保温延迟 / 是否冷启动 / 绑定时间）。
    ⇒ 路由与面板不必再猜「这条车道现在通不通」。

## 「直通启动」怎么落地
  `install` 往**当前用户 Startup 目录**放一个 VBS（与既有 `agnes-proxy.vbs` 同法，**不需要提权**）：
  登录即静默跑 `loop`，默认**自适应保温**（近 `--idle-window` 内有会话活动才保，没人用就让它睡，不烧 GPU）。

用法：
    py -3.14 tools/codex-scripts/llm-lane-direct.py up        # 一次直通：拉起代理 + 保温 + 写绑定读数
    py -3.14 tools/codex-scripts/llm-lane-direct.py loop      # 常驻保温（默认自适应）
    py -3.14 tools/codex-scripts/llm-lane-direct.py status    # 只读：车道 + 上游 + 上次保温
    py -3.14 tools/codex-scripts/llm-lane-direct.py install   # 注册登录直通（Startup，免提权）
    py -3.14 tools/codex-scripts/llm-lane-direct.py uninstall # 撤销

红线：
  · **只回环**：代理请求一律 `127.0.0.1:8317`，非回环目标拒发；
  · **密钥只读不回显**（只报前 4 位 + 长度）；不在任何日志/状态文件里写明文；
  · **不替死件续命**：车道表里没出现的车道不编、不猜、不假装活着。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
PORT = int(os.environ.get("GBT_CLIPROXY_PORT", "8317"))
BASE = "http://%s:%d/v1" % (HOST, PORT)
APPDIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "gbt-cliproxy"
KEYFILE = APPDIR / "client-key.txt"
STATE = ROOT / "state" / "llm-lane-binding.json"
STARTUP = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
VBS_NAME = "GBT-LLM车道直通.vbs"
ALLOWED_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_WARM = [m.strip() for m in (os.environ.get("GBT_LANE_WARM_MODELS") or "gbt-potato-v8").split(",") if m.strip()]
ENDPOINT_ID = os.environ.get("GBT_POTATO_ENDPOINT_ID", "qnnqf9w8xcefj8")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _fp(key: str) -> str:
    return (key[:4] + "****(" + str(len(key)) + ")") if key else "（无）"


def _user_env(name: str) -> str:
    """环境变量缺失时回注册表读（用户级）。实测坑：老进程/老终端的环境块可能是旧的，
    `os.environ` 里没有 GBT_* 而 `HKCU\\Environment` 里有 —— 直通件不能因此判"缺钥"。"""
    v = (os.environ.get(name) or "").strip()
    if v or os.name != "nt":
        return v
    try:
        import winreg                                          # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return (winreg.QueryValueEx(k, name)[0] or "").strip()
    except Exception:                                          # noqa: BLE001
        return ""


def _client_key() -> str:
    env = _user_env("GBT_CLIPROXY_KEY")
    if env:
        return env
    try:
        return KEYFILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _url(path: str) -> str:
    if not path.startswith("/"):
        raise ValueError("路径必须以 / 开头")
    url = "http://%s:%d%s" % (HOST, PORT, path)
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in ALLOWED_LOOPBACK:
        raise ValueError("非回环目标被拒：%s" % url[:80])
    return url


def _req(method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> tuple:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(_url(path), data=data, method=method,
                                 headers={"Authorization": "Bearer " + _client_key(),
                                          "Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:400]
    except Exception as exc:                                     # noqa: BLE001
        return 0, "连不上：%s" % str(exc)[:160]


def lanes() -> list:
    st, body = _req("GET", "/v1/models", timeout=5.0)
    if st != 200:
        return []
    try:
        return [m.get("id") for m in (json.loads(body).get("data") or []) if m.get("id")]
    except Exception:                                            # noqa: BLE001
        return []


def _child_env() -> dict:
    """给子进程（cliproxy.py up）**补齐钥匙**。

    🔴 2026-10-14 血读（我自己踩的）：自愈里直接 `subprocess.run(..., env 继承)`，
    而老进程/老终端的环境块里**没有** GBT_* ⇒ `cliproxy.py up` 用"统一钥"当上游钥重写配置
    ⇒ 上游 RunPod 回 `401 invalid api key`，deepseek 车道因缺钥被整条丢掉（3 条 → 1 条）。
    修法：**进程环境优先，缺的从用户注册表补**（仍属"环境变量"，只是持久化那份）。
    """
    env = dict(os.environ)
    for name in ("GBT_CLIPROXY_KEY", "GBT_POTATO_BASE_URL", "GBT_POTATO_API_KEY",
                 "GBT_POTATO_LANE_KEY", "GBT_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY",
                 "FREELLMAPI_API_KEY", "GBT_FREE_POOL_KEY"):
        v = _user_env(name)
        if v:
            env.setdefault(name, v)
    if env.get("GBT_POTATO_API_KEY"):
        env.setdefault("GBT_POTATO_LANE_KEY", env["GBT_POTATO_API_KEY"])
    return env


def _run_up() -> None:
    """走仓里自己的 up（不绕门）：它负责写配置 + 重启 + 探活。**必须带补齐的 env**。"""
    script = ROOT / "tools" / "codex-scripts" / "cliproxy.py"
    subprocess.run([sys.executable, str(script), "up"], cwd=str(ROOT), timeout=180,
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=_child_env())


def ensure_proxy(expected: list | None = None) -> dict:
    """A 向前提：8317 得活着，**而且车道得在列**。

    两级自愈（都实测过）：
      ① 代理没在跑 ⇒ 拉起；
      ② 代理在跑、**但某条车道没在列** ⇒ 重启代理。
         实测坑（2026-10-14）：CLIProxyAPI 对**连续失败的上游**会把整条车道**下架**
         （`/v1/models` 里直接消失），不重启就一直是"少一条腿"的状态 —— 上游明明已经活了。
    """
    want = list(expected or DEFAULT_WARM)
    st, _ = _req("GET", "/v1/models", timeout=4.0)
    if st == 200:
        have = lanes()
        missing = [m for m in want if m not in have]
        if not missing:
            return {"was_running": True, "action": "none", "lanes": have}
        try:
            _run_up()
        except Exception as exc:                                 # noqa: BLE001
            return {"was_running": True, "action": "restart_failed", "error": str(exc)[:160], "lanes": have}
        for _ in range(20):
            time.sleep(1.0)
            have = lanes()
            if all(m in have for m in want):
                return {"was_running": True, "action": "restarted_cleared_cooldown",
                        "missing": missing, "lanes": have}
        return {"was_running": True, "action": "restart_did_not_restore", "missing": missing, "lanes": lanes()}
    try:
        _run_up()
    except Exception as exc:                                     # noqa: BLE001
        return {"was_running": False, "action": "up_failed", "error": str(exc)[:160]}
    for _ in range(20):
        time.sleep(1.0)
        st, _ = _req("GET", "/v1/models", timeout=4.0)
        if st == 200:
            return {"was_running": False, "action": "started", "lanes": lanes()}
    return {"was_running": False, "action": "started_but_unhealthy"}


def _shot(model: str, timeout: float) -> dict:
    t0 = time.perf_counter()
    st, body = _req("POST", "/v1/chat/completions",
                    {"model": model, "messages": [{"role": "user", "content": "ping"}],
                     "max_tokens": 1, "stream": False}, timeout=timeout)
    ms = int((time.perf_counter() - t0) * 1000)
    return {"model": model, "status": st, "ms": ms, "cold": ms > 10000,
            "err": "" if st == 200 else body[:200]}


def warm_one(model: str, timeout: float = 300.0) -> dict:
    """保温一发。冷启动会慢（实测 92s~300s），热机 0.8~2.2s。

    🔴 2026-10-14 加**冷却自愈**（主人截图里那条 `503 auth_unavailable: no auth available` 就是它）：
      CLIProxyAPI 对**连败的上游**会把该 provider 的凭据整条**冷却**，此后所有请求回
      503 auth_unavailable / 401 invalid token（不是我们钥匙错，是它在罚站）。
      命中这个签名就**重启代理清冷却**，再打一发 —— 冷/热/冷却这套状态在连接层吸收掉，
      不该透到调用方（Codex 那边只会看到 503）。
    """
    r = _shot(model, timeout)
    if r["status"] in (401, 403, 503):
        try:
            _run_up()
        except Exception as exc:                                 # noqa: BLE001
            r["heal"] = "restart_failed: %s" % str(exc)[:80]
            return r
        time.sleep(2.0)
        r2 = _shot(model, timeout)
        r2["healed"] = "restarted_cleared_cooldown"
        r2["first_attempt"] = {"status": r["status"], "err": r["err"][:120]}
        return r2
    return r


def upstream_workers() -> dict:
    """B 向读数之一：上游 worker 就绪数（RunPod 只读 health）。没钥就如实缺。"""
    key = _user_env("GBT_POTATO_API_KEY")
    if not key:
        return {"ok": False, "reason": "缺 GBT_POTATO_API_KEY（进程环境与用户注册表都没有）"}
    req = urllib.request.Request("https://api.runpod.ai/v2/%s/health" % ENDPOINT_ID,
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:        # noqa: S310
            return {"ok": True, "endpoint": ENDPOINT_ID, "health": json.loads(r.read().decode("utf-8", "replace"))}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "reason": str(exc)[:120]}


def session_active(idle_window: int) -> dict:
    """最近 idle_window 秒内有没有人在用（Codex / DSH 会话文件 mtime 现读）。"""
    roots = [Path.home() / ".codex" / "sessions", Path.home() / ".dsh" / "sessions"]
    newest, where = 0.0, ""
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if p.is_file():
                m = p.stat().st_mtime
                if m > newest:
                    newest, where = m, str(p)
    age = (time.time() - newest) if newest else None
    return {"active": bool(age is not None and age <= idle_window), "idle_seconds": int(age) if age else None,
            "watch": where}


def write_state(direction_a: dict, direction_b: dict, keepalive: dict) -> str:
    doc = {"generated_at": _now(), "binding": "llm-lane-direct/双向绑定",
           "direction_a": direction_a, "direction_b": direction_b, "keepalive": keepalive,
           "note": "A 向=框架→车道（一条 base-url 直达）· B 向=车道→框架（读数回写）"}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE)
    return str(STATE)


def cmd_up(a) -> int:
    want = a.warm_model or DEFAULT_WARM
    print("① 代理：", ensure_proxy(want))
    ids = lanes()
    print("② 车道（%d 条）：%s" % (len(ids), "、".join(ids) or "（空）"))
    # 「冷热无非就是读一遍全部资料」⇒ --preload 时把**车道表上每条腿**都叫醒一遍（启动即全部就位）
    want = list(ids) if getattr(a, "preload", False) else (a.warm_model or DEFAULT_WARM)
    hot = [m for m in want if m in ids]
    results = [warm_one(m, a.timeout) for m in hot]
    for r in results:
        flag = "冷启动" if r["cold"] else "热机"
        print("③ 保温 %-16s → HTTP %s  %6dms  [%s]%s" % (r["model"], r["status"], r["ms"], flag,
                                                        ("  " + r["err"]) if r["err"] else ""))
    up = upstream_workers()
    if up.get("ok"):
        w = (up["health"] or {}).get("workers", {})
        print("④ 上游 worker：ready=%s idle=%s running=%s throttled=%s" %
              (w.get("ready"), w.get("idle"), w.get("running"), w.get("throttled")))
    else:
        print("④ 上游 worker：未读到（%s）—— 如实缺，不编" % up.get("reason"))
    ka = {"mode": "once", "interval": None, "idle_window": None}
    path = write_state({"base_url": BASE, "lanes": ids, "client_key": _fp(_client_key()),
                        "warm_models": hot, "ensure_proxy": ensure_proxy()},
                       {"last_warm": results, "upstream": up}, ka)
    print("⑤ 双向绑定读数已写：%s" % path)
    return 0 if all(r["status"] == 200 for r in results) else 1


def cmd_loop(a) -> int:
    print("直通保温常驻：interval=%ss idle_window=%ss always=%s" % (a.interval, a.idle_window, a.always))
    while True:
        try:
            info = ensure_proxy(a.warm_model or DEFAULT_WARM)
            ids = lanes()
            hot = [m for m in (a.warm_model or DEFAULT_WARM) if m in ids]
            act = session_active(a.idle_window) if not a.always else {"active": True, "idle_seconds": 0, "watch": "always"}
            up = upstream_workers()
            w = (up.get("health") or {}).get("workers", {}) if up.get("ok") else {}
            already = bool(w.get("ready") or w.get("idle"))
            if not act["active"]:
                print("[%s] 无人使用（%ss）⇒ 让它睡，不烧 GPU" % (_now(), act["idle_seconds"]))
                results = []
            elif already and not a.force:
                print("[%s] worker 已就绪（ready=%s）⇒ 无需保温" % (_now(), w.get("ready")))
                results = []
            else:
                results = [warm_one(m, a.timeout) for m in hot]
                for r in results:
                    print("[%s] 保温 %s → HTTP %s %dms%s" % (_now(), r["model"], r["status"], r["ms"],
                                                            "  [冷启动]" if r["cold"] else ""))
            write_state({"base_url": BASE, "lanes": ids, "client_key": _fp(_client_key()),
                         "warm_models": hot, "ensure_proxy": info},
                        {"last_warm": results, "upstream": up, "session": act},
                        {"mode": "loop", "interval": a.interval, "idle_window": a.idle_window, "always": a.always})
            time.sleep(a.interval)
        except KeyboardInterrupt:
            print("收到中断，停。")
            return 0
        except Exception as exc:                                 # noqa: BLE001
            print("[%s] 循环异常：%s" % (_now(), str(exc)[:200]))
            time.sleep(a.interval)


def cmd_status(_a) -> int:
    ids = lanes()
    print("代理：%s" % BASE)
    print("车道 %d 条：%s" % (len(ids), "、".join(ids) or "（空）"))
    if STATE.is_file():
        doc = json.loads(STATE.read_text(encoding="utf-8"))
        print("上次绑定：%s（%s）" % (doc.get("generated_at"), doc.get("binding")))
        for r in (doc.get("direction_b") or {}).get("last_warm") or []:
            print("   保温 %s → HTTP %s %dms%s" % (r.get("model"), r.get("status"), r.get("ms", 0),
                                                  "  [冷启动]" if r.get("cold") else ""))
    else:
        print("尚无绑定读数（先跑一次 up）")
    up = upstream_workers()
    print("上游 worker：%s" % (json.dumps((up.get("health") or {}).get("workers", {}), ensure_ascii=False)
                              if up.get("ok") else "未读到 · " + str(up.get("reason"))))
    print("登录自启：%s" % ("已装 " + str(STARTUP / VBS_NAME) if (STARTUP / VBS_NAME).is_file() else "未装"))
    return 0


def cmd_install(_a) -> int:
    script = Path(__file__).resolve()
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.is_file() else Path(sys.executable)
    vbs = STARTUP / VBS_NAME
    body = ('Set s = CreateObject("WScript.Shell")\r\n'
            's.CurrentDirectory = "%s"\r\n'
            's.Run "\"%s\" \"%s\" loop --interval 240 --idle-window 900", 0, False\r\n'
            % (ROOT, exe, script))
    STARTUP.mkdir(parents=True, exist_ok=True)
    vbs.write_text(body, encoding="mbcs")
    print("已装登录直通：%s" % vbs)
    print("（免提权 · 撤销用 uninstall；自适应保温：近 15 分钟有人用才保）")
    return 0


def cmd_uninstall(_a) -> int:
    vbs = STARTUP / VBS_NAME
    if vbs.is_file():
        os.replace(vbs, str(vbs) + ".removed-" + time.strftime("%Y%m%d-%H%M%S"))
        print("已撤销（改名留存，没删）：%s" % vbs)
    else:
        print("本来就没装。")
    return 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="LLM 车道双向绑定 + 直通启动（回环）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("up", cmd_up), ("loop", cmd_loop), ("status", cmd_status),
                     ("install", cmd_install), ("uninstall", cmd_uninstall)):
        p = sub.add_parser(name, help=fn.__doc__ or "")
        p.add_argument("--warm-model", action="append", default=[], help="要保温的车道模型（可重复）")
        p.add_argument("--timeout", type=float, default=300.0, help="单发保温超时秒")
        if name == "up":
            p.add_argument("--preload", action="store_true", help="把车道表上每条腿都叫醒一遍（启动即全部就位）")
        if name == "loop":
            p.add_argument("--interval", type=int, default=240, help="巡检间隔秒（默认 240 < 上游 idleTimeout 300）")
            p.add_argument("--idle-window", type=int, default=900, help="近 N 秒有会话活动才保温")
            p.add_argument("--always", action="store_true", help="无条件常驻保温（会持续烧 GPU，慎用）")
            p.add_argument("--force", action="store_true", help="worker 已就绪也再打一发")
        p.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
