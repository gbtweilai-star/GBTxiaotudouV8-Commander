#!/usr/bin/env python3
"""触手总线 —— 把"传输"抽象成可插拔的触手，不卡死在一种接口上

主人令（2026-10-28 原话）：
  「所有的一切都可使用触手来联通传输，没必要死卡在传统方式，
    我们这是和市面上的大模型完全相反的两条线路」

## 为什么要有它

这一路我们已经撞过三次同一堵墙：

```
body_say     → powershell           （Windows 专用）
body_volume  → pycaw                （Windows 专用）
摄像头        → getUserMedia        （WebView 挂起）
STT          → apple-speech         （必须走苹果服务器，超时）
```

每一次都不是"功能不存在"，而是**绑定死了唯一一种传输方式**。

## 它做什么

把每个"器官"抽象成一根触手，每根触手挂**多条传输实现**，按顺序试：

```
tentacle_bus.call('mouth', text='…')
  ① edge-tts zh-TW-HsiaoChenNeural   ← 首选（她的原声）
  ② apple-speak zh-TW（美嘉）         ← 兜底
  ③ powershell System.Speech          ← Windows
  ④ 如实报"这台机没有这条传输"
```

**返回里必须带 `via`（走的哪条）和 `tried`（试过哪些、为什么没过）** ——
不许让人猜"到底是哪条干的活"。

## 与仓库既有触手的关系

`gbt_allinone/tentacle/` 那套（omni_audio / omni_core / omni_mouse…）
是**能力实现**，本器是**传输调度**：它把 apple-* CLI、edge-tts、HTTP、文件、
MCP 都当成同等地位的传输，谁通走谁。

**不替换、不覆盖**：`tentacle_bind` 仍然照旧绑定资产↔触手，本器只是多给一条路。

用法：
  python3 tools/tentacle_bus.py --status
  python3 tools/tentacle_bus.py --call mouth "说一句话"
  python3 tools/tentacle_bus.py --call ear --file x.mp3
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VOICE_TW = "zh-TW-HsiaoChenNeural"          # 曉臻 · 台湾腔女声（仓库真源）
LEDGER = ROOT / "logs" / "tentacle_bus.jsonl"


def log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── 传输实现：每条返回 (ok, detail, extra) ─────────────────────────────────

def t_edge_tts(text: str, **kw):
    """① 她的原声：edge-tts 台湾腔（晓臻）"""
    try:
        import asyncio
        import edge_tts
    except Exception as exc:                                  # noqa: BLE001
        return False, "edge_tts 不可用: %s" % exc, {}
    f = pathlib.Path("/var/minis/attachments") / ("her_%d.mp3" % int(time.time() * 1000))
    voice = kw.get("voice") or VOICE_TW
    try:
        asyncio.run(edge_tts.Communicate(text, voice).save(str(f)))
    except Exception as exc:                                  # noqa: BLE001
        return False, "合成失败: %s" % str(exc)[:80], {}
    played, player = False, "未播"
    if shutil.which("apple-player"):
        r = subprocess.run(["apple-player", "play", str(f)], capture_output=True,
                           text=True, timeout=120)
        played = r.returncode == 0
        player = "apple-player"
    return True, "合成 %d 字节" % f.stat().st_size, {
        "voice": voice, "file": str(f), "played": played, "player": player}


def t_apple_speak(text: str, **kw):
    """② 兜底：Apple 系统嗓音（zh-TW 美嘉）"""
    if not shutil.which("apple-speak"):
        return False, "无 apple-speak", {}
    r = subprocess.run(["apple-speak", "speak", "--text", text,
                        "--voice", kw.get("voice") or "zh-TW"],
                       capture_output=True, text=True, timeout=90)
    return r.returncode == 0, (r.stderr or "ok")[:120], {"engine": "apple-speak"}


def t_powershell(text: str, **kw):
    if not shutil.which("powershell"):
        return False, "无 powershell", {}
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object "
          "System.Speech.Synthesis.SpeechSynthesizer; $s.Speak([Console]::In.ReadToEnd())")
    r = subprocess.run(["powershell", "-NoProfile", "-c", ps], input=text,
                       capture_output=True, text=True, timeout=90)
    return r.returncode == 0, (r.stderr or "ok")[:120], {}


def t_apple_speech(text: str = "", **kw):
    """耳：Apple 语音识别（走苹果服务器；本机实测会超时）"""
    if not shutil.which("apple-speech"):
        return False, "无 apple-speech", {}
    src = kw.get("source") or "mic"
    dur = str(int(kw.get("duration") or 6))
    cmd = ["apple-speech", "transcribe", "--source", src,
           "--language", kw.get("language") or "zh-CN"]
    if src == "mic":
        cmd += ["--duration", dur]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False, "识别超时（>90s）", {}
    out = (r.stdout or "").strip()
    try:
        d = json.loads(out[out.index("{"):])
    except Exception:                                         # noqa: BLE001
        return False, out[:120] or "无输出", {}
    if not d.get("ok"):
        return False, str((d.get("error") or {}).get("message") or "")[:100], {}
    return True, "识别到 %d 字" % len((d.get("data") or {}).get("text") or ""), {
        "text": (d.get("data") or {}).get("text") or ""}


def t_apple_player(text: str = "", **kw):
    """播：把已有音频文件播出去"""
    f = kw.get("file")
    if not f or not shutil.which("apple-player"):
        return False, "缺 file 或无 apple-player", {}
    r = subprocess.run(["apple-player", "play", f], capture_output=True,
                       text=True, timeout=120)
    return r.returncode == 0, (r.stderr or "ok")[:120], {}


# ── her 器官：让她（A19 自有权重）能被联通 ────────────────────────────────
# 立命规矩（主人 2026-10-28）：「所有的一切都可使用触手来联通传输，没必要死卡在
# 传统方式」。所以这里**不是断言"只能 1234"**，而是把能想到的每条传输都真打一遍，
# 由 tried 如实记下哪条没过、为什么没过 —— 不许让人猜。
def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:                                             # noqa: BLE001
        return ""


def _a19_probe(host: str, port: int = 1234, timeout: float = 4.0):
    """真发一次 /v1/models —— TCP 通不算活，拿到 JSON 才算。"""
    import json as _j
    import urllib.request as _u
    h = "[%s]" % host if ":" in host else host
    req = _u.Request("http://%s:%d/v1/models" % (h, port),
                     headers={"Authorization": "Bearer gbt"})
    body = _u.urlopen(req, timeout=timeout).read(4000).decode("utf-8", "replace")
    d = _j.loads(body)
    items = d.get("data") or d.get("models") or []
    name = ""
    if items:
        first = items[0]
        name = first.get("id") if isinstance(first, dict) else str(first)
    return name, body[:200]


def t_a19_loopback(text: str = "", **kw):
    try:
        name, sample = _a19_probe("127.0.0.1")
        return True, "回环 :1234 应答 model=%s" % (name or "?"), {"model": name}
    except Exception as exc:                                      # noqa: BLE001
        return False, "回环 :1234 %s" % type(exc).__name__, {}


def t_a19_lan(text: str = "", **kw):
    ip = _lan_ip()
    if not ip:
        return False, "取不到网卡地址", {}
    try:
        name, sample = _a19_probe(ip)
        return True, "网卡 %s:1234 应答 model=%s" % (ip, name or "?"), {"model": name}
    except Exception as exc:                                      # noqa: BLE001
        return False, "网卡 %s:1234 %s" % (ip, type(exc).__name__), {}


def t_a19_bridge(text: str = "", **kw):
    """经我们自己的桥（:8791 selfhost 车道）—— 桥在不在、通不通，它自己会说。"""
    import json as _j
    import urllib.request as _u
    try:
        req = _u.Request("http://127.0.0.1:8791/v1/chat/completions",
                         data=_j.dumps({"model": "", "upstream": "selfhost",
                                        "max_tokens": 8,
                                        "messages": [{"role": "user",
                                                      "content": text or "在吗"}]}).encode(),
                         headers={"Content-Type": "application/json",
                                  "Authorization": "Bearer gbt"})
        d = _j.loads(_u.urlopen(req, timeout=40).read())
        if d.get("ok"):
            return True, "桥 selfhost 应答", {"answer": str(d)[:200]}
        return False, "桥如实报：%s" % (d.get("error", {}).get("message", "")[:80]), {}
    except Exception as exc:                                      # noqa: BLE001
        return False, "桥不通 %s" % type(exc).__name__, {}


def t_a19_deeplink(text: str = "", **kw):
    """把 App 拉到前台（这是唯一能碰它的动作）—— 打开后立刻探，看服务跟不跟着起。"""
    if not shutil.which("apple-open"):
        return False, "本机无 apple-open", {}
    r = subprocess.run(["apple-open", kw.get("url") or "lmpocket://"],
                       capture_output=True, text=True, timeout=30)
    opened = "false"
    try:
        opened = str(json.loads(r.stdout or "{}").get("data", {}).get("opened")).lower()
    except Exception:                                             # noqa: BLE001
        pass
    time.sleep(kw.get("wait", 20))
    try:
        name, _ = _a19_probe("127.0.0.1")
        return True, "拉起后 :1234 应答 model=%s" % (name or "?"), {"model": name}
    except Exception as exc:                                      # noqa: BLE001
        return False, "拉起 opened=%s，但 :1234 仍 %s" % (opened, type(exc).__name__), {}


def t_local_worker(text: str = "", **kw):
    """传输：本机权重 · 页面工人（2026-10-30）。

    为什么要有这条：A19（LM Pocket 的 :1234）要在 App 私有界面里点一下才起，
    那不归我们控制。但我们自己的权重还有第二条路 —— 页面里用整机 GPU 跑 GGUF。
    于是把**插座做成她需要的形状**：框架往桥的 /_local 派活，页面领活算完交回。
    页面侧见 holo_pet_w3/wgpu/local-llm.html?_worker=1。
    """
    import json as _j
    import urllib.request as _u
    BR = kw.get("bridge") or "http://127.0.0.1:8791"
    # 2026-10-30：**不阻塞**。页面工人在后台标签会被 WebView 节流（实测一轮 30–90s），
    # 死等只会把整根触手拖死。改成：入队 → 短等（默认 12s）→ 没到就如实报"已入队"。
    wait_s = float(kw.get("wait") or 12)
    body = _j.dumps({"text": text, "max_tokens": int(kw.get("max_tokens") or 48)}).encode()
    try:
        rq = _u.Request(BR + "/_local/enqueue", data=body,
                        headers={"Content-Type": "application/json"})
        jid = _j.loads(_u.urlopen(rq, timeout=10).read()).get("id")
        if not jid:
            return False, "入队失败", {}
        t0 = time.time()
        while time.time() - t0 < wait_s:
            time.sleep(1.0)
            try:
                rows = pathlib.Path("/var/minis/shared/gbtv8/state/local_results.jsonl")
                if not rows.is_file():
                    continue
                for ln in rows.read_text(encoding="utf-8").splitlines():
                    try:
                        d = _j.loads(ln)
                    except Exception:                             # noqa: BLE001
                        continue
                    if d.get("id") == jid:
                        txt = (d.get("text") or "").strip()
                        if not txt:
                            return False, "工人交了空回包", {"id": jid}
                        return True, txt, {"id": jid, "backend": d.get("backend"),
                                           "tok_s": d.get("tokPerSec")}
            except Exception:                                     # noqa: BLE001
                continue
        return False, "已入队 %s（工人算完会交回 state/local_results.jsonl；后台标签被节流时较慢）" % jid, {
            "id": jid, "queued": True}
    except Exception as exc:                                      # noqa: BLE001
        return False, "%s: %s" % (type(exc).__name__, str(exc)[:80]), {}


# ── 触手表：每根挂多条传输，按序试 ─────────────────────────────────────────
TENTACLES: dict[str, list[tuple[str, callable]]] = {
    "mouth": [("edge-tts-zhTW", t_edge_tts),
              ("apple-speak-zhTW", t_apple_speak),
              ("powershell", t_powershell)],
    "ear":   [("apple-speech", t_apple_speech)],
    "play":  [("apple-player", t_apple_player)],
    # 她：四条传输，谁通走谁；全不通就如实报哪条为什么没过
    "her":   [("http-loopback", t_a19_loopback),
              ("http-lan", t_a19_lan),
              ("bridge-selfhost", t_a19_bridge),
              # 2026-10-30：她需要什么接口，就把插座做成什么接口 ——
              # 页面工人用整机 GPU 跑我们的权重，框架经桥派活，不依赖 LM Pocket 的 :1234
              ("local-worker", t_local_worker),
              ("deeplink+lazy-probe", t_a19_deeplink)],
}


def call(name: str, text: str = "", **kw) -> dict:
    exps = TENTACLES.get(name)
    if not exps:
        return {"ok": False, "error": "没有这根触手：%s（可选 %s）"
                % (name, ",".join(TENTACLES))}
    tried = []
    for engine, fn in exps:
        t0 = time.perf_counter()
        try:
            ok, detail, extra = fn(text, **kw)
        except Exception as exc:                              # noqa: BLE001
            ok, detail, extra = False, "%s: %s" % (type(exc).__name__,
                                                   str(exc)[:80]), {}
        ms = round((time.perf_counter() - t0) * 1000)
        tried.append({"engine": engine, "ok": ok, "ms": ms, "detail": detail})
        if ok:
            rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tentacle": name,
                   "via": engine, "ms": ms, **extra}
            log(rec)
            return {"ok": True, "tentacle": name, "via": engine, "detail": detail,
                    "ms": ms, "tried": tried, **extra}
    log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tentacle": name,
         "via": None, "tried": tried})
    return {"ok": False, "tentacle": name, "via": None,
            "error": "所有传输都不通", "tried": tried}


def status() -> dict:
    out = {}
    for name, exps in TENTACLES.items():
        avail = []
        for engine, _ in exps:
            need = {"edge-tts-zhTW": "edge_tts", "apple-speak-zhTW": "apple-speak",
                    "powershell": "powershell", "apple-speech": "apple-speech",
                    "apple-player": "apple-player"}[engine]
            if need == "edge_tts":
                try:
                    import edge_tts  # noqa: F401
                    avail.append({"engine": engine, "ready": True})
                except Exception:                             # noqa: BLE001
                    avail.append({"engine": engine, "ready": False, "why": "模块缺失"})
            else:
                ok = bool(shutil.which(need))
                avail.append({"engine": engine, "ready": ok,
                              "why": "" if ok else "命令不在"})
        out[name] = avail
    return {"ok": True, "tentacles": out, "voice_default": VOICE_TW,
            "口径": "每根触手按序试多条传输；回执必带 via 与 tried，不让人猜"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--call", nargs="+", metavar="TENTACLE [TEXT]")
    ap.add_argument("--file", default="")
    a = ap.parse_args()

    if a.status or not a.call:
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return 0

    name = a.call[0]
    text = " ".join(a.call[1:]) if len(a.call) > 1 else ""
    kw = {"file": a.file} if a.file else {}
    r = call(name, text, **kw)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
