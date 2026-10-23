#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**语音链路就绪清单** —— 回答一个问题：数字人现在的语音，还差哪几块才真的能说能听？

开发者：自由的风 · 本署名不可删除、不可篡改归属

## 为什么要有它
2026-10-17 重做了语音交互（A·全屏对话剧场）。设计稿能看，但「真能说话」要三样东西：
  ① 票：说话=audio_output · 听话=privacy_read（**只有主人能在终端发**，AI 无权自授）
  ② 引擎：本机 TTS / 离线识别器 / 录音端点（现读，不猜）
  ③ 接缝：页面要能接住真跑出来的语音产物（`?audio=<wav>`）
任何一项没到位，页面都只能演样本。**这一页就是把这三项摊开**，免得每次都要重新推。

## 它读什么（全部只读）
  · `py -3.14 -m gbt_allinone auth status`      → 每个作用域还剩几张票
  · `five-dim.py cap voice {"op":"status"}`     → 本机 TTS/ASR/识别器/录音端点
  · 页面与素材：有没有 `?audio=` 接缝、样本 wav / 立绘在不在

## 它不做什么
  · **不发任何写动作**、不开麦克风、不出声（那是要票的事，且在别的命令里）。
  · 拿不到读数就写「未读到」，**不写「没有」**（本仓纪律：取不到 ≠ 不存在）。
  · `不适用 ≠ 通过`：票没发的时候结论就是「未就绪」，不是「差不多好了」。

## 用法
  py -3.14 tools/codex-scripts/voice-link-readiness.py
  py -3.14 tools/codex-scripts/voice-link-readiness.py --json
退出码：0 全部就绪 · 1 有未就绪项（含"等你发票"）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "holo_pet_w3/voice-theater/index.html"
WAV = ROOT / "holo_pet_w3/digital-human/welcome-gbt-v8-zh.wav"
PORTRAIT = ROOT / "holo_pet_w3/digital-human/digital-human-hero-3q.jpg"

PY = sys.executable or "py"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _run_json(cmd: list[str], timeout: int = 90) -> tuple[object | None, str]:
    """跑一条只读命令并解析 JSON。**输出走真文件**（本沙箱挡管道），失败带原文。"""
    with tempfile.TemporaryDirectory(prefix="voice-ready-") as td:
        out = Path(td) / "out.json"
        err = Path(td) / "err.txt"
        with out.open("wb") as fo, err.open("wb") as fe:
            try:
                proc = subprocess.run(cmd, stdout=fo, stderr=fe, timeout=timeout, cwd=str(ROOT))
            except subprocess.TimeoutExpired:
                return None, f"超时 {timeout}s"
        text = out.read_text("utf-8", "replace")
        if not text.strip():
            tail = err.read_text("utf-8", "replace")[-300:]
            return None, f"没有输出（rc={proc.returncode}）{tail}"
        try:
            return json.loads(text), ""
        except Exception as e:  # noqa: BLE001
            return None, f"不是 JSON：{e} · 首 200 字：{text[:200]}"


def grants() -> dict:
    # 🔴 用 sys.executable（**已经是 3.14 解释器**）⇒ 不能再传 `-3.14`：
    #    那是 `py` 启动器的写法，传给 python.exe 会报 `Unknown option: -3`（本器第一版就这么栽的）。
    data, why = _run_json([PY, "-m", "gbt_allinone", "auth", "status"])
    if not isinstance(data, dict):
        return {"ok": False, "why": why or "读不到"}
    sc = data.get("scopes") or {}
    want = {}
    for key in ("audio_output", "privacy_read"):
        item = sc.get(key) or {}
        want[key] = {
            "grants": int(item.get("grants_available") or 0),
            "desc": item.get("desc", ""),
            "mode": item.get("mode", ""),
        }
    return {"ok": True, "scopes": want}


def voice_status() -> dict:
    data, why = _run_json([PY, str(ROOT / "tools/codex-scripts/five-dim.py"),
                           "cap", "voice", '{"op":"status"}'])
    if not isinstance(data, dict):
        return {"ok": False, "why": why or "读不到"}
    res = data.get("result")
    if not isinstance(res, dict) or not res.get("ok"):
        return {"ok": False, "why": "status 返回不含 ok", "raw_keys": list(data)[:6]}
    keep = ("tts", "asr", "listen", "listen_recognizer", "wavein_devices", "listen_note", "voicestudio")
    return {"ok": True, **{k: res.get(k) for k in keep if k in res}}


def edge_reachable() -> dict:
    """edge-tts **真能不能用**：装没装 ≠ 通不通（2026-10-18 实栽）。

    实测那天：`voice op=tts` 报 `wss speech.platform.bing.com 403`，
    而本器当时只查「引擎已装 edge-tts」就报 ✅ —— **假绿**。
    现口径：真去 HTTPS 取一次 voices 列表（只读、不出声、不写盘）；
    取不到就写未读到，不许因为"装了"就当成"能用"。
    """
    import urllib.error
    import urllib.request

    url = ("https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list"
           "?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (gbt-readiness)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read(4096)
            return {"ok": resp.status == 200 and len(body) > 2,
                    "detail": "HTTPS %s · %dB（voices 列表）" % (resp.status, len(body))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "detail": "HTTPS %s" % e.code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": "连不上：%s" % type(e).__name__}


def sapi_voices() -> dict:
    """本机 SAPI 发音人（离线出声的唯一兜底）。只读，走一次 PowerShell。"""
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture }; "
          "$s.Dispose()")
    with tempfile.TemporaryDirectory(prefix="voice-sapi-") as td:
        out = Path(td) / "v.txt"
        with out.open("wb") as fo:
            try:
                subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                               stdout=fo, stderr=subprocess.DEVNULL, timeout=90)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "voices": [], "tw": [], "detail": "读取失败：%s" % e}
        text = out.read_text("utf-8", "replace")
    rows = [ln.strip() for ln in text.splitlines() if "|" in ln]
    tw = [r for r in rows if ("TW" in r.split("|")[-1] or "台灣" in r or "台湾" in r or "繁體" in r)]
    return {"ok": bool(rows), "voices": rows, "tw": tw,
            "detail": "%d 个发音人 · zh-TW %d 个" % (len(rows), len(tw))}


def ks_endpoints() -> dict:
    """WDM-KS 能看见几个采集引脚（**看见 ≠ 有数据**）。

    2026-10-18 实测：MME/DirectSound/WASAPI 的 default_input 全是 -1，
    但 WDM-KS 列出 4 个输入引脚（Realtek 麦克风 / 立体声混音 / 蓝牙免提 / Input()）；
    逐个试录，**两个采集引脚都开得起来却 0 帧** ⇒ 引脚没被 Windows 路由。
    本器只报这个事实，不改任何系统设置。
    """
    script = ROOT / "tools/codex-scripts/wasapi-record.py"
    if not script.is_file():
        return {"ok": False, "detail": "wasapi-record.py 不在盘上"}
    with tempfile.TemporaryDirectory(prefix="voice-ks-") as td:
        out = Path(td) / "list.txt"
        with out.open("wb") as fo:
            try:
                subprocess.run([PY, str(script), "--list"], stdout=fo,
                               stderr=subprocess.DEVNULL, timeout=90)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "detail": "读取失败：%s" % type(e).__name__}
        text = out.read_text("utf-8", "replace")
    pins = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("#")]
    if not pins:
        return {"ok": False, "detail": "WDM-KS 也没列出采集引脚（真没有录音硬件）"}
    return {"ok": True,
            "detail": "WDM-KS 列出 %d 个采集引脚：%s" % (len(pins), " · ".join(p.split("  ")[-1][:24] for p in pins[:4]))}


def page_hooks() -> dict:
    if not PAGE.is_file():
        return {"ok": False, "why": "页面不在"}
    html = PAGE.read_text("utf-8", "replace")
    return {
        "ok": True,
        "audio_param": "?audio=" in html and "AUDIO_SRC" in html,
        "state_machine": "function setState(" in html,
        "real_analyser": "createAnalyser" in html and "getByteFrequencyData" in html,
        "sample_wav": WAV.is_file() and WAV.stat().st_size > 100_000,
        "portrait": PORTRAIT.is_file(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="语音链路就绪清单（只读）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    g = grants()
    v = voice_status()
    p = page_hooks()

    items = []

    def add(name: str, ready: bool, detail: str, todo: str = "") -> None:
        items.append({"item": name, "ready": ready, "detail": detail, "todo": todo})

    # ① 票
    if g.get("ok"):
        ao = g["scopes"]["audio_output"]
        pr = g["scopes"]["privacy_read"]
        add("票 · 出声(audio_output)", ao["grants"] > 0,
            f"剩余 {ao['grants']} 张 · {ao['mode']} · {ao['desc']}",
            "python -m gbt_allinone auth grant --scope audio_output --ttl 600")
        add("票 · 听话(privacy_read)", pr["grants"] > 0,
            f"剩余 {pr['grants']} 张 · {pr['mode']} · {pr['desc']}",
            "python -m gbt_allinone auth grant --scope privacy_read --ttl 600")
    else:
        add("票面", False, f"读不到 auth status：{g.get('why')}", "先跑 python -m gbt_allinone auth status 看原文")

    # ② 引擎（**装没装 ≠ 通不通**：这一栏是本器 2026-10-18 假绿过的同一个坑）
    if v.get("ok"):
        add("引擎 · TTS 已装", bool(v.get("tts")), "现读：%s" % v.get("tts"))
    else:
        add("引擎 · TTS 已装", False, "读不到 voice status：%s" % v.get("why"))

    er = edge_reachable()
    add("引擎 · edge-tts 可达", bool(er.get("ok")), er.get("detail", ""),
        "wss 合成要能通（实测 2026-10-18：wss 403 · 而 HTTPS voices 列表 200）")

    sv = sapi_voices()
    add("引擎 · zh-TW 发音人", bool(sv.get("tw")), sv.get("detail", ""),
        "设置 → 时间和语言 → 语言和区域 → 添加「中文(繁體，台灣)」并勾选「语音」；"
        "装好后本机 SAPI 就有 zh-TW，不依赖外网")

    if v.get("ok"):
        add("引擎 · 离线识别器", bool(v.get("listen_recognizer")),
            "现读：%s（listen=%s）" % (v.get("listen_recognizer"), v.get("listen")))
        wd = v.get("wavein_devices")
        ks = ks_endpoints()
        add("硬件 · 默认录音设备", (wd or 0) > 0,
            "wavein_devices=%s ⇒ 系统没有『默认录音设备』（MME/DirectSound/WASAPI 的 default_input 全是 -1）" % wd,
            "设置 → 系统 → 声音 → 管理声音设备 → 启用『麦克风』或『立体声混音』")
        add("硬件 · KS 引脚可见", False,
            (ks.get("detail", "") + " —— ⚠️ 可见 ≠ 可用（本器只读，不替你录）")
            if ks.get("ok") else ks.get("detail", ""),
            "真要判「能不能采到」，必须真录一次："
            "py -3.14 tools/codex-scripts/wasapi-record.py --device <索引> --seconds 3 --out .scratch/t.wav --json"
            "（2026-10-18 实测：麦克风 #9 与立体声混音 #10 都是『流开得起来但 0 帧』⇒ 引脚未路由；"
            "先在 设置→系统→声音→管理声音设备 里启用采集设备，或插 USB 麦）")
    else:
        add("引擎", False, "读不到 voice status：%s" % v.get("why"))

    # ③ 接缝
    if p.get("ok"):
        add("接缝 · 页面能接真产物", bool(p.get("audio_param")),
            "页面支持 ?audio=<wav> 播放真 TTS 产物（给了就用它，不给就用样本）")
        add("接缝 · 真音频驱动", bool(p.get("real_analyser")), "AnalyserNode 实时包络（不是随机动画）")
        add("接缝 · 状态机", bool(p.get("state_machine")), "待机/在听/在想/在说，唯一改口 setState()")
        add("素材 · 样本与立绘", bool(p.get("sample_wav") and p.get("portrait")),
            "欢迎语音 wav + 数字人立绘都在盘上")
    else:
        add("接缝", False, p.get("why", "读不到"))

    red = [i for i in items if not i["ready"]]
    ok_all = not red

    if a.json:
        print(json.dumps({"ok": ok_all, "items": items}, ensure_ascii=False, indent=2))
    else:
        print("═" * 78)
        print("  数字人语音链路 · 就绪清单（只读）")
        print("═" * 78)
        for i in items:
            print(f"  {'✅' if i['ready'] else '🔴'} {i['item']:<24} {i['detail']}")
        print("-" * 78)
        todo = [i for i in red if i["todo"]]
        if todo:
            print("  还差（照抄这些命令）：")
            for i in todo:
                print(f"    · {i['item']} → {i['todo']}")
        print(f"结论：{'全就绪' if ok_all else '未就绪 %d 项' % len(red)}"
              "（未就绪 ≠ 坏了：多半只是票没发 / 硬件没有录音端点）")
        print("边界：本器只读；它不开麦、不出声，也不替你发票。")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
