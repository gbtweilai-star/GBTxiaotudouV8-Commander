# -*- coding: utf-8 -*-
"""《免费样片》v2 补全：按 14s 剧本真产素材/配音/BGM → edit_core 渲染 → 许可登记。
中间件全部落 .scratch/（抽屉里只进成品）。"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import edit_core as EC  # noqa: E402
from gbt_allinone.tools import media_license as ML  # noqa: E402

WORK = "免费样片"
DAY = "20260926"
SCR = ROOT / ".scratch" / "_免费样片_v2"
SCR.mkdir(parents=True, exist_ok=True)
RAW = ROOT / "projects/short-video/03-raw"
CUT = ROOT / "projects/short-video/04-cut"
PUB = ROOT / "projects/short-video/05-publish"

# 剧本四镜（与 01-script.md 一致：3+3+4+4 = 14s）
SHOTS = [
    (3.0, 0x101820, "slateblue",  "深夜工作室 · 台灯亮起"),
    (3.0, 0x182030, "steelblue",  "字幕逐句点亮 · 剪辑自动推进"),
    (4.0, 0x20283a, "royalblue",  "渲染键按下 · 进度条走满"),
    (4.0, 0x2a3040, "lightblue",  "成片登场 · 收在暖光"),
]
SUBS = [
    (0.2, 2.6, "凌晨两点，只有机器还醒着"),
    (3.2, 2.6, "字幕自动点亮，节奏自己走"),
    (6.2, 3.6, "一键渲染，十四秒成片"),
    (10.2, 3.6, "这条片，从配音到成片没花一分钱"),
]
VOICE = "深夜两点，只有机器还醒着。字幕自动点亮，节奏自己走。一键渲染，十四秒成片。这条片，从配音到成片，没花一分钱。"


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, shell=(sys.platform == "win32" and False))
    return r.returncode, (r.stderr or "")[-400:]


def synth_clip(dst: Path, secs: float, c1: str, c2: str, label: str) -> bool:
    """lavfi 合成竖屏底片 + 渐变 + 中央字条（无 drawtext 依赖字体问题）。"""
    vf = (
        "gradients=s=1080x1920:c0=%s:c1=%s:speed=0.02:d=%s,"
        "drawbox=x=90:y=860:w=900:h=200:color=black@0.35:t=fill,"
        "noise=alls=8:allf=t" % (c1, c2, secs)
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", vf, "-frames:v", str(int(secs * 30)),
           "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst)]
    rc, err = sh(cmd)
    return rc == 0 and dst.is_file()


def synth_bgm(dst: Path, secs: float) -> bool:
    """两路正弦叠一层慢呼吸的低频鼓点，做成一条 14s 的极简 BGM。"""
    a = SCR / "_bgm_a.wav"
    b = SCR / "_bgm_b.wav"
    r1, _ = sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                "-i", "sine=frequency=220:duration=%s" % secs, str(a)])
    r2, _ = sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                "-i", "sine=frequency=330:duration=%s" % secs, str(b)])
    if r1 != 0 or r2 != 0:
        return False
    rc, err = sh(["ffmpeg", "-y", "-loglevel", "error",
                  "-i", str(a), "-i", str(b),
                  "-filter_complex",
                  "[0:a]volume=0.25[a];[1:a]volume=0.15,tremolo=f=2:d=0.6[b];"
                  "[a][b]amix=inputs=2:duration=first:normalize=0,afade=t=in:d=0.5,"
                  "afade=t=out:st=%s:d=1.2" % (secs - 1.2),
                  "-ar", "44100", "-ac", "2", str(dst)])
    return rc == 0 and dst.is_file()


def sapi_tts(dst: Path, text: str, voice: str) -> bool:
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          "$s.SelectVoice('%s');$s.Rate=0;"
          "$s.SetOutputToWaveFile($env:TTS_OUT);$s.Speak($env:TTS_TEXT);$s.Dispose();"
          "Write-Output TTS_OK" % voice)
    env = {"TTS_OUT": str(dst), "TTS_TEXT": text}
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180, env={**__import__('os').environ, **env})
    return "TTS_OK" in (r.stdout or "") and dst.is_file()


def register(file: Path, kind: str, step: str) -> dict:
    r = api_ready(file)
    src = "本仓 ffmpeg/SAPI 自产：《免费样片》v2 %s 步" % step
    lic = ML.run("register", file=str(file), source=src, license="自有（本机自产，CC0等效）",
                 note="%s | sha16=%s" % (kind, r))
    return lic


def api_ready(file: Path) -> str:
    import hashlib
    h = hashlib.sha256(file.read_bytes()).hexdigest()
    return h[:16]


def main() -> None:
    t0 = time.time()
    report = {"ok": True, "steps": []}

    # 1) 四镜素材（1080x1920, 30fps）
    clips = []
    for i, (secs, _bg, c2, _label) in enumerate(SHOTS, 1):
        dst = SCR / ("_shot%d.mp4" % i)
        c1 = ["#0b0f18", "#0e1524", "#131a2a", "#1a2030"][i - 1]
        ok = synth_clip(dst, secs, c1, c2, _label)
        report["steps"].append({"step": "clip%d" % i, "ok": ok, "secs": secs})
        if not ok:
            report["ok"] = False
            break
        clips.append(dst)

    # 2) SAPI 配音
    vo = SCR / "_voiceover.wav"
    ok = sapi_tts(vo, VOICE, "Microsoft Huihui Desktop")
    report["steps"].append({"step": "tts", "ok": ok, "out": vo.name})
    if not ok:
        report["ok"] = False

    # 3) BGM 14s
    bgm = SCR / "_bgm.wav"
    ok = synth_bgm(bgm, 14.0)
    report["steps"].append({"step": "bgm", "ok": ok})
    if not ok:
        report["ok"] = False

    # 4) 配音转 48k stereo wav 供时间线用
    vo48 = SCR / "_voiceover48.wav"
    if vo.is_file():
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vo),
            "-ar", "48000", "-ac", "2", str(vo48)])

    # 5) 时间线：4 视频段 + 2 音轨 + 4 字幕
    tl = {
        "version": 1, "unit": "second",
        "canvas": {"w": 1080, "h": 1920, "fps": 30, "bg": "black"},
        "tracks": {
            "video": [],
            "audio": [],
            "text": [],
        },
    }
    tcur = 0.0
    for i, (secs, *_rest) in enumerate(SHOTS):
        seg = {
            "src": str(clips[i]),
            "t0": round(tcur, 3),
            "dur": secs,
            "src_start": 0.0,
            "fit": "cover",
            "motion": {"kind": "kenburns", "zoom_from": 1.0, "zoom_to": 1.0 + 0.06 * (i + 1) / 4},
        }
        tl["tracks"]["video"].append(seg)
        tcur += secs

    if vo48.is_file():
        tl["tracks"]["audio"].append({"src": str(vo48), "t0": 0.0, "src_start": 0.0,
                                      "dur": 14.0, "gain_db": 0.0,
                                      "fade_in": 0.08, "fade_out": 0.2})
    if bgm.is_file():
        tl["tracks"]["audio"].append({"src": str(bgm), "t0": 0.0, "src_start": 0.0,
                                      "dur": 14.0, "gain_db": -12.0,
                                      "fade_in": 0.5, "fade_out": 1.2})
    for (st, dur, txt) in SUBS:
        tl["tracks"]["text"].append({"text": txt, "t0": st, "dur": dur, "y": 0.78})

    v = EC.validate(tl)
    report["validate"] = v
    if not v.get("ok"):
        report["ok"] = False
        out = ROOT / "projects/short-video/04-cut/_v2_validate_fail.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return

    # 6) 渲染 14s 成片（彩排件名，走 media_flow 合规命名）
    rel_out = "projects/short-video/04-cut/%s-%s-%s-rehearsal.mp4" % (DAY, "short-video", WORK)
    dst = ROOT / rel_out
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = EC.render(tl, str(dst), workdir=str(SCR / "_render_work"), mode="")
    report["render"] = {k: r.get(k) for k in ("ok", "mode", "out", "why", "notes")}
    if not r.get("ok"):
        report["ok"] = False
        errs = []
        for run in (r.get("runs") or []):
            if run.get("rc") != 0:
                errs.append({"cmd": (run.get("cmd") or "")[:300], "err": (run.get("err") or "")[-800:]})
        report["render_stage"] = r.get("stage")
        report["render_errs"] = errs or (r.get("runs") or [])[-1:]

    # 7) 导出 + 许可登记
    if r.get("ok"):
        pub = PUB / dst.name
        pub.write_bytes(dst.read_bytes())
        lic1 = register(dst, "short-video", "edit")
        lic2 = register(pub, "short-video", "export")
        for f, kind in ((clips[0], "素材"), (vo48, "配音"), (bgm, "BGM")):
            register(f, "short-video", kind)
        report["export"] = {"ok": pub.is_file(), "bytes": pub.stat().st_size if pub.is_file() else 0}

    report["secs"] = round(time.time() - t0, 1)
    (SCR / "_v2_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
