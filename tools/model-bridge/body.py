# -*- coding: utf-8 -*-
"""身体：把「装在哪台设备上」变成「她有什么身体」。

一块能力位叫「腿/眼/耳/口/手」，都不该写死在某台机器 —— 装到哪台，
就把那台的设备现读成身体，缺的如实报缺，不许假装有。

对外两件事：
  body()            -> dict   这台设备的身体清单（感官 + 动作 + 每项的实读证据）
  act(limb, args)   -> dict   真的动一下（截屏 / 发声 / 点按 / 调音量 / 看摄像头）

命令行：
  python body.py --json        打印身体清单
  python body.py --act see     {"path":"x.png"} 之类
"""
from __future__ import annotations
import json, os, platform, subprocess, sys, time

def _try(fn, default=None):
    try:
        return fn()
    except Exception as exc:                                     # noqa: BLE001
        return {"_err": "%s: %s" % (type(exc).__name__, str(exc)[:120])}

# ── 感官 ────────────────────────────────────────────────────
def sense_screen():
    import mss
    with mss.mss() as s:
        mons = s.monitors[1:]
        return {"ok": True, "monitors": len(mons),
                "size": [m["width"] for m in mons], "height": [m["height"] for m in mons]}

def sense_camera():
    import cv2
    found = []
    for i in range(3):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            found.append({"index": i, "w": w, "h": h})
        cap.release()
    return {"ok": bool(found), "cameras": found}

def sense_mic():
    import sounddevice as sd
    ins = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
    return {"ok": bool(ins), "count": len(ins),
            "names": [d["name"] for d in ins][:4]}

def sense_speaker():
    import sounddevice as sd
    outs = [d for d in sd.query_devices() if d.get("max_output_channels", 0) > 0]
    return {"ok": bool(outs), "count": len(outs), "names": [d["name"] for d in outs][:4]}

def sense_power():
    import psutil
    b = psutil.sensors_battery()
    return {"ok": True, "percent": None if b is None else round(b.percent),
            "plugged": None if b is None else b.power_plugged,
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "mem_used_mb": round(psutil.virtual_memory().used / 1048576)}

def sense_net():
    import psutil
    out = []
    for name, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family.name == "AF_INET" and not a.address.startswith("127."):
                out.append({"if": name, "ip": a.address})
    return {"ok": bool(out), "lan": out[:4],
            "hostname": platform.node(), "os": platform.platform()}

def sense_bluetooth():
    r = subprocess.run(["powershell", "-NoProfile", "-c",
        "(Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'OK' } | Measure-Object).Count"],
        capture_output=True, text=True)
    n = int((r.stdout or "0").strip() or 0)
    return {"ok": n > 0, "adapters": n}

SENSES = {
    "see_screen": ("屏幕/多显示器", sense_screen),
    "see_camera": ("摄像头", sense_camera),
    "hear_mic": ("麦克风", sense_mic),
    "speak_out": ("扬声器", sense_speaker),
    "feel_power": ("电量/CPU/内存", sense_power),
    "net_reach": ("网络与身份", sense_net),
    "bt_nearby": ("蓝牙适配器", sense_bluetooth),
}

# ── 动作 ────────────────────────────────────────────────────
def act_see(args):
    import mss
    from PIL import Image
    path = args.get("path") or os.path.join(os.environ.get("TEMP", "."), "body-see-%d.png" % int(time.time()))
    with mss.mss() as s:
        raw = s.grab(s.monitors[int(args.get("monitor", 1))])
        Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX").save(path)
    return {"ok": True, "path": path, "bytes": os.path.getsize(path)}

def act_say(args):
    text = str(args.get("text") or "")[:300]
    if not text:
        return {"ok": False, "error": "缺 text"}
    ps = ("Add-Type -AssemblyName System.Speech; "
          "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.Rate = %d; $s.Speak([Console]::In.ReadToEnd())" % int(args.get("rate", 0)))
    # 🔴 2026-10-28：原来只会 powershell（Windows 专用）。本机是 iSH/iOS，
    #   实测 FileNotFoundError: 'powershell' ⇒ 授权放开了门，门后没实现。
    #   现在按平台依次降级，**每一档都如实报用了谁**：
    #     ① Windows  → powershell System.Speech
    #     ② iOS/iSH  → apple-speak（iOS AVSpeechSynthesizer 原生 TTS）
    #     ③ 都不行   → 如实报平台没有出声能力，不假装说过话
    import shutil as _sh
    if _sh.which("powershell"):
        r = subprocess.run(["powershell", "-NoProfile", "-c", ps], input=text,
                           capture_output=True, text=True, timeout=90)
        return {"ok": r.returncode == 0, "chars": len(text), "engine": "powershell",
                "err": (r.stderr or "")[:120]}
    if _sh.which("apple-speak"):
        # 正确形态是 `speak --text <串>`（不是 `speak <串>`）；
        # 中文要用 zh-CN 嗓子，否则英文嗓子念中文会跳过。
        r = subprocess.run(["apple-speak", "speak", "--text", text,
                            "--voice", str(args.get("voice") or "zh-CN")],
                           capture_output=True, text=True, timeout=90)
        return {"ok": r.returncode == 0, "chars": len(text), "engine": "apple-speak",
                "err": (r.stderr or "")[:120]}
    return {"ok": False, "chars": len(text), "engine": "none",
            "error": "这台机没有出声实现（无 powershell / 无 apple-speak）"}

def act_type(args):
    import pyautogui
    t = str(args.get("text") or "")
    if not t:
        return {"ok": False, "error": "缺 text"}
    pyautogui.typewrite(t, interval=float(args.get("interval", 0.01)))
    return {"ok": True, "chars": len(t)}

def act_click(args):
    import pyautogui
    x, y = int(args.get("x", 0)), int(args.get("y", 0))
    pyautogui.click(x=x, y=y, clicks=int(args.get("clicks", 1)))
    return {"ok": True, "at": [x, y]}

def act_volume(args):
    # 🔴 2026-10-28：pycaw 是 Windows 专用。本机 iSH/iOS 实测
    #   ModuleNotFoundError: 'pycaw' ⇒ 授权放开了门、门后没实现。
    #   改：先认平台，Windows 走 pycaw，iOS 走 apple-media volume，都没有就如实报。
    import shutil as _sh
    if not _sh.which("powershell") and _sh.which("apple-media"):
        import subprocess as _sp
        lv = args.get("level")
        if lv is None:
            r = _sp.run(["apple-media", "volume"], capture_output=True,
                        text=True, timeout=30)
            try:
                import json as _j
                d = _j.loads((r.stdout or "").strip() or "{}")
                cur = (d.get("data") or d).get("volume")
                return {"ok": r.returncode == 0, "level": cur, "engine": "apple-media"}
            except Exception:                                 # noqa: BLE001
                return {"ok": False, "engine": "apple-media",
                        "err": (r.stdout or r.stderr or "")[:150]}
        r = _sp.run(["apple-media", "volume", "--level", str(float(lv))],
                    capture_output=True, text=True, timeout=30)
        return {"ok": r.returncode == 0, "level": float(lv), "engine": "apple-media",
                "err": (r.stderr or "")[:120]}
    from pycaw.pycaw import AudioUtilities
    dev = AudioUtilities.GetSpeakers()
    # pycaw 新版：AudioDevice 直接带 EndpointVolume；旧版要自己 Activate
    vol = getattr(dev, "EndpointVolume", None)
    if vol is None:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume
        iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
    level = args.get("level")
    if level is None:
        return {"ok": True, "level": round(vol.GetMasterVolumeLevelScalar(), 3)}
    vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, float(level))), None)
    return {"ok": True, "level": round(vol.GetMasterVolumeLevelScalar(), 3)}

def act_open(args):
    target = str(args.get("target") or "")
    if not target:
        return {"ok": False, "error": "缺 target"}
    # 🔴 2026-10-28：os.startfile 是 **Windows 专用**，本机（iSH/iOS）没有。
    #   按平台依次降级，每档标明用了谁：
    #     ① Windows → os.startfile
    #     ② iOS/iSH → apple-open（系统 URL handler）
    #     ③ 都没有  → 如实报
    import shutil as _sh
    if hasattr(os, "startfile"):
        os.startfile(target)                                      # noqa: S606
        return {"ok": True, "opened": target[:120], "engine": "os.startfile"}
    if _sh.which("apple-open"):
        r = subprocess.run(["apple-open", target], capture_output=True,
                           text=True, timeout=60)
        ok = r.returncode == 0
        return {"ok": ok, "opened": target[:120], "engine": "apple-open",
                "err": (r.stderr or "")[:120] if not ok else ""}
    return {"ok": False, "error": "这台机没有打开手段（无 os.startfile / 无 apple-open）",
            "engine": "none"}

ACTUATORS = {
    "see": ("截屏", act_see),
    "say": ("发声(TTS)", act_say),
    "type": ("键入", act_type),
    "click": ("点按", act_click),
    "volume": ("音量", act_volume),
    "open": ("打开", act_open),
}


def body() -> dict:
    senses = []
    for name, (label, fn) in SENSES.items():
        r = _try(fn)
        ok = bool(isinstance(r, dict) and r.get("ok"))
        senses.append({"limb": name, "label": label,
                       "state": "ok" if ok else "missing",
                       "detail": r})
    acts = [{"limb": k, "label": v[0]} for k, v in ACTUATORS.items()]
    healthy = sum(1 for s in senses if s["state"] == "ok")
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "device": {"host": platform.node(), "os": platform.platform(),
                       "cpu": os.cpu_count(), "py": platform.python_version()},
            "senses": senses, "actuators": acts,
            "score": {"senses_ok": healthy, "senses_total": len(senses),
                      "actuators": len(acts)}}


def act(limb: str, args: dict) -> dict:
    if limb not in ACTUATORS:
        return {"ok": False, "error": "不认识的肢体：%s（可选 %s）"
                                      % (limb, ",".join(ACTUATORS))}
    return _try(lambda: ACTUATORS[limb][1](args or {}))


if __name__ == "__main__":
    if "--act" in sys.argv:
        i = sys.argv.index("--act")
        limb = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        payload = json.loads(sys.argv[i + 2]) if len(sys.argv) > i + 2 else {}
        print(json.dumps(act(limb, payload), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(body(), ensure_ascii=False, indent=1))
