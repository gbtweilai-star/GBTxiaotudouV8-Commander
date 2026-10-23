# -*- coding: utf-8 -*-
"""GBT小土豆V8 × VoiceStudio · 本地语音工作台接道（主人令 2026-10-04「下一步」）。

真身：`debpalash/VoiceStudio`（开放源码 · AGPL-3.0）——开源、**完全本地**的 ElevenLabs 替代：
克隆 / 设计 / 配音 / 听写 / 转写 / 有声书，**646 种语言**。
已取至 `_upstream/VoiceStudio`（uv 管环境 · 本机 CPU torch 档 · .venv 约 4.4G）。

## 形态（为什么这样接）
上游是「桌面应用 + 无头语音服务」双形态：桌面壳（Electron/Tauri）我们**不装**，
只跑它的 headless 后端（FastAPI/uvicorn，**127.0.0.1:3900**），MCP 挂在 `/mcp/`。
本件是**我们这边的唯一操作口**，全部直连它后端的普通 HTTP 路由（就是 MCP 底下那层，不绕 JSON-RPC）：

  speak      → POST /generate        （文本 → WAV；可带 profile_id / language / instruct / speed）
  clone      → POST /profiles        （参考音 → 新声线 profile_id；之后 speak --profile 用）
  voices     → GET  /profiles        （已存声线清点）
  transcribe → POST /transcribe      （音频 → 文本）
  models     → GET  /models          （38 个模型的可装/已装；--install <repo_id> 拉模型）
  status     → GET  /health          （up/down + device + version）
  up / down  → 起停后端（.venv 直启，不借 uv 包装；日志落 state/voicestudio/server.log）

## 红线（与框架同口径）
  · 出站**只许回环 http**（`_checked_url`：协议/主机/重定向三重校验；目标由本件写死，无用户 URL）
  · 进程**硬关遥测**（OMNIVOICE_ANALYTICS_DISABLED=1，随 spawn 环境下发）
  · MCP 输出走 **files 模式 + BASE_PATH=state/voicestudio/out**（音频落盘，不灌上下文）
  · 失败必带原因（ok=false + reason）；子进程 shell=False + 不弹黑窗（CREATE_NO_WINDOW）

用法：
    py -3.14 tools/codex-scripts/voicestudio.py status
    py -3.14 tools/codex-scripts/voicestudio.py up | down
    py -3.14 tools/codex-scripts/voicestudio.py speak --text "你好" [--profile <id>] [--language zh] [--play]
    py -3.14 tools/codex-scripts/voicestudio.py clone --name 主人 --ref C:\\refs\\me.wav [--ref-text "…"]
    py -3.14 tools/codex-scripts/voicestudio.py voices
    py -3.14 tools/codex-scripts/voicestudio.py transcribe --audio C:\\x.wav
    py -3.14 tools/codex-scripts/voicestudio.py models [--install k2-fsa/OmniVoice]

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[2]
VS_DIR = ROOT / "_upstream" / "VoiceStudio"
STATE = ROOT / "state" / "voicestudio"
OUT = STATE / "out"
PIDFILE = STATE / "backend.pid"
LOG = STATE / "server.log"

HOST = "127.0.0.1"          # 字面回环：本件唯一的出站目标（无第二目标、无用户 URL）
DEFAULT_PORT = 3900
_CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def _port() -> int:
    raw = os.environ.get("OMNIVOICE_PORT", str(DEFAULT_PORT)).strip()
    try:
        p = int(raw)
    except ValueError:
        raise SystemExit("OMNIVOICE_PORT 不是整数：%r" % raw[:20])
    if not (1 <= p <= 65535):
        raise SystemExit("OMNIVOICE_PORT 越界：%d" % p)
    return p


PORT = _port()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """拒绝重定向：本地服务不该把我们导去别处（防被引导型 SSRF）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _checked_url(path: str) -> str:
    """唯一出站点：只许**回环 http**（协议/主机/重定向三重校验）。"""
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("路径必须以单个 / 开头：%r" % path[:40])
    url = "http://%s:%d%s" % (HOST, PORT, path)
    parts = urllib.parse.urlsplit(url)
    # 防未来误改常量：协议必须 http、主机必须**字面** 127.0.0.1（隐式放行 localhost/::1 也不许）
    if parts.scheme != "http" or parts.hostname != HOST:
        raise ValueError("出站目标必须字面回环 http：%r" % url)
    return url


def _request(method: str, path: str, data: bytes | None = None,
             ctype: str | None = None, timeout: float = 30.0):
    """→ (status|None, headers, body bytes)。status=None ⇒ 连不上（reason 在 body）。"""
    url = _checked_url(path)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "gbt-voicestudio-driver/1")
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()
    except Exception as e:  # noqa: BLE001 —— 连不上/超时都属于"读不到"，如实回 reason
        return None, {}, ("%s: %s" % (type(e).__name__, e)).encode("utf-8")


def _multipart(fields: dict, files: dict | None = None):
    """(body, content_type)。files: {name: (filename, bytes)}。"""
    boundary = "----gbtVS" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for k, v in fields.items():
        chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                       % (boundary, k, v)).encode("utf-8"))
    for k, (fname, raw) in (files or {}).items():
        chunks.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                       "Content-Type: application/octet-stream\r\n\r\n"
                       % (boundary, k, fname)).encode("utf-8"))
        chunks.append(bytes(raw))
        chunks.append(b"\r\n")
    chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(chunks), "multipart/form-data; boundary=%s" % boundary


def _sniff_ext(raw: bytes) -> str:
    if raw.startswith(b"fLaC"):
        return ".flac"
    if raw.startswith(b"ID3") or raw[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    if raw.startswith(b"OggS"):
        return ".ogg"
    return ".wav"


def _health(timeout: float = 3.0) -> tuple[bool, dict]:
    st, _h, body = _request("GET", "/health", timeout=timeout)
    if st == 200:
        try:
            return True, json.loads(body.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            return True, {}
    reason = body.decode("utf-8", "replace")[:200] if body else "无响应"
    return False, {"reason": reason, "status": st}


def _venv_python() -> Path:
    win = VS_DIR / ".venv" / "Scripts" / "python.exe"
    nix = VS_DIR / ".venv" / "bin" / "python"
    return win if win.exists() else nix


def cmd_status(_a) -> dict:
    up, info = _health()
    if up:
        return {"ok": True, "up": True, "port": PORT, "base": "http://%s:%d" % (HOST, PORT),
                "version": info.get("version"), "device": info.get("device")}
    return {"ok": True, "up": False, "port": PORT,
            "reason": info.get("reason"), "hint": "起：py -3.14 tools/codex-scripts/voicestudio.py up"}


def cmd_up(a) -> dict:
    up, info = _health()
    if up:
        return {"ok": True, "already_up": True, "version": info.get("version"), "device": info.get("device")}
    pyexe = _venv_python()
    if not pyexe.exists():
        return {"ok": False, "reason": "未找到上游 venv：%s（先跑 node scripts/setup-api.mjs）" % pyexe,
                "missing": ["_upstream/VoiceStudio/.venv"]}
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "OMNIVOICE_ANALYTICS_DISABLED": "1",       # 硬关遥测（随进程下发，不看它的默认）
        "OMNIVOICE_MCP_OUTPUT_MODE": "files",       # 音频走文件，不进上下文
        "OMNIVOICE_MCP_BASE_PATH": str(OUT),        # MCP 文件输入/输出的唯一边界
        "OMNIVOICE_PORT": str(PORT),
    })
    log = open(LOG, "ab", buffering=0)
    flags = _CREATE_NO_WINDOW | _CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        [str(pyexe), "-m", "uvicorn", "main:app", "--app-dir", "backend",
         "--host", HOST, "--port", str(PORT)],
        cwd=str(VS_DIR), env=env, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
    )
    PIDFILE.write_text(str(proc.pid), encoding="ascii")
    deadline = time.time() + max(30, int(a.wait))
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = ""
            try:
                tail = LOG.read_text(encoding="utf-8", errors="replace")[-600:]
            except Exception:  # noqa: BLE001
                pass
            return {"ok": False, "reason": "后端进程已退出（code=%s）" % proc.returncode, "log_tail": tail}
        up, info = _health()
        if up:
            return {"ok": True, "started": True, "pid": proc.pid, "version": info.get("version"),
                    "device": info.get("device"), "log": str(LOG)}
        time.sleep(2)
    step = {}
    st, _h, body = _request("GET", "/startup/progress", timeout=3)
    if st == 200:
        try:
            step = json.loads(body.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            pass
    return {"ok": False, "reason": "等待就绪超时（%ss）" % int(a.wait), "pid": proc.pid,
            "startup": {"status": step.get("status"), "step": step.get("step"), "label": step.get("label")}}


def cmd_down(_a) -> dict:
    pid = None
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text(encoding="ascii").strip())
        except Exception:  # noqa: BLE001
            pid = None
    if pid is None:  # 兜底：按监听端口找 PID（GBK 解码见仓内血账）
        try:
            r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, timeout=15)
            text = r.stdout.decode("gbk", "replace")
            for line in text.splitlines():
                if (":%d " % PORT) in line and "LISTENING" in line.upper():
                    pid = int(line.split()[-1])
                    break
        except Exception:  # noqa: BLE001
            pid = None
    if pid is None:
        up, info = _health(2)
        return {"ok": not up, "stopped": False, "reason": None if not up else info.get("reason"),
                "note": "没找到 PID 且服务在跑" if up else "服务本来就没跑"}
    r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=20)
    ok = r.returncode == 0
    for _ in range(15):
        up, _info = _health(1.5)
        if not up:
            break
        time.sleep(1)
    up, _info = _health(1.5)
    try:
        PIDFILE.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": (not up) if ok else False, "stopped": not up, "pid": pid,
            "taskkill_rc": r.returncode,
            "reason": None if not up else "进程杀了但端口仍在响应"}


def cmd_speak(a) -> dict:
    if not (a.text or "").strip():
        return {"ok": False, "reason": "缺少 --text"}
    fields = {"text": a.text, "speed": str(a.speed), "num_step": str(a.steps)}
    if a.language:
        fields["language"] = a.language
    if a.profile:
        fields["profile_id"] = a.profile
    if a.instruct:
        fields["instruct"] = a.instruct
    if a.engine:
        fields["engine"] = a.engine
    body, ctype = _multipart(fields)
    t0 = time.time()
    st, headers, resp = _request("POST", "/generate", data=body, ctype=ctype, timeout=a.timeout)
    ms = int((time.time() - t0) * 1000)
    if st != 200:
        return {"ok": False, "reason": resp.decode("utf-8", "replace")[:400], "status": st, "ms": ms}
    audio_id = (headers.get("X-Audio-Id") or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{8}", audio_id or ""):
        audio_id = "t%d" % int(time.time())
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("vs-%s.wav" % audio_id)
    path.write_bytes(resp)
    out = {"ok": True, "audio_id": audio_id, "ms": ms, "bytes": len(resp), "file": str(path),
           "gen_time_s": headers.get("X-Gen-Time"), "audio_duration_s": headers.get("X-Audio-Duration"),
           "profile_id": a.profile or None, "language": a.language or None}
    if a.play:
        os.startfile(str(path))  # noqa: S606 —— 不经 shell，路径由本件拼定
        out["played"] = True
    return out


def cmd_voices(_a) -> dict:
    st, _h, body = _request("GET", "/profiles", timeout=15)
    if st != 200:
        return {"ok": False, "status": st, "reason": body.decode("utf-8", "replace")[:300]}
    try:
        rows = json.loads(body.decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "返回不是 JSON：%s" % e}
    slim = [{"id": r.get("id"), "name": r.get("name"), "kind": r.get("kind"),
             "language": r.get("language")}
            for r in rows if isinstance(r, dict)]
    return {"ok": True, "count": len(slim), "voices": slim}


def cmd_clone(a) -> dict:
    ref = Path(a.ref)
    if not ref.exists():
        return {"ok": False, "reason": "参考音不存在：%s" % ref}
    raw = ref.read_bytes()
    if len(raw) > 200 * 1024 * 1024:
        return {"ok": False, "reason": "参考音超过 200MB 上限"}
    fields = {"name": a.name, "kind": "clone", "ref_text": a.ref_text or "",
              "instruct": a.instruct or "", "language": a.language or "Auto"}
    body, ctype = _multipart(fields, files={"ref_audio": ("ref" + _sniff_ext(raw), raw)})
    st, _h, resp = _request("POST", "/profiles", data=body, ctype=ctype, timeout=a.timeout)
    if st != 200:
        return {"ok": False, "status": st, "reason": resp.decode("utf-8", "replace")[:400]}
    try:
        p = json.loads(resp.decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "返回不是 JSON：%s" % e}
    return {"ok": True, "profile_id": p.get("id"), "name": p.get("name"), "kind": p.get("kind"),
            "ref_bytes": len(raw), "note": "之后用 speak --profile %s 说话" % (p.get("id"),)}


def cmd_transcribe(a) -> dict:
    audio = Path(a.audio)
    if not audio.exists():
        return {"ok": False, "reason": "音频不存在：%s" % audio}
    raw = audio.read_bytes()
    fields = {}
    if a.language:
        fields["language"] = a.language
    body, ctype = _multipart(fields, files={"audio": ("audio" + _sniff_ext(raw), raw)})
    st, _h, resp = _request("POST", "/transcribe", data=body, ctype=ctype, timeout=a.timeout)
    if st != 200:
        return {"ok": False, "status": st, "reason": resp.decode("utf-8", "replace")[:400]}
    try:
        return {"ok": True, **json.loads(resp.decode("utf-8", "replace"))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "返回不是 JSON：%s" % e}


def cmd_models(a) -> dict:
    if a.install:
        st, _h, body = _request("POST", "/models/install",
                                data=json.dumps({"repo_id": a.install, "target": "local"}).encode(),
                                ctype="application/json", timeout=60)
        if st != 200:
            return {"ok": False, "status": st, "reason": body.decode("utf-8", "replace")[:400]}
        started = json.loads(body.decode("utf-8", "replace"))
        deadline = time.time() + max(60, int(a.wait))
        last = {}
        while time.time() < deadline:
            st2, _h2, b2 = _request("GET", "/models/install/status?repo_id=" +
                                    urllib.parse.quote(a.install), timeout=15)
            if st2 == 200:
                try:
                    jobs = json.loads(b2.decode("utf-8", "replace")).get("jobs", [])
                    last = jobs[0] if jobs else {}
                except Exception:  # noqa: BLE001
                    last = {}
            state = (last or {}).get("state")
            if state in ("done", "complete", "installed", "error", "failed", "cancelled"):
                break
            time.sleep(5)
        ok = (last or {}).get("state") in ("done", "complete", "installed")
        return {"ok": ok, "started": started, "final": last,
                "reason": None if ok else "未在等待窗内完成（state=%s），可稍后用 models 复查"
                                          % (last or {}).get("state")}
    st, _h, body = _request("GET", "/models", timeout=15)
    if st != 200:
        return {"ok": False, "status": st, "reason": body.decode("utf-8", "replace")[:300]}
    d = json.loads(body.decode("utf-8", "replace"))
    rows = [{"repo_id": m.get("repo_id"), "size_gb": m.get("size_gb"), "required": m.get("required"),
             "installed": m.get("installed"), "incomplete": m.get("incomplete"),
             "on_disk_gb": round((m.get("size_on_disk_bytes") or 0) / 1e9, 2)}
            for m in d.get("models", [])]
    return {"ok": True, "total_models": len(rows),
            "installed_count": sum(1 for r in rows if r["installed"]),
            "disk_free_gb": d.get("disk_free_gb"), "hf_cache_dir": d.get("hf_cache_dir"),
            "installed": [r for r in rows if r["installed"]],
            "not_installed_required": [r for r in rows if r["required"] and not r["installed"]]}


def main() -> int:
    ap = argparse.ArgumentParser(description="VoiceStudio 本地语音工作台接道")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    p_up = sub.add_parser("up")
    p_up.add_argument("--wait", type=int, default=300)
    sub.add_parser("down")

    p_sp = sub.add_parser("speak")
    p_sp.add_argument("--text", required=True)
    p_sp.add_argument("--profile", default=None)
    p_sp.add_argument("--language", default=None)
    p_sp.add_argument("--instruct", default=None)
    p_sp.add_argument("--engine", default=None)
    p_sp.add_argument("--speed", type=float, default=1.0)
    p_sp.add_argument("--steps", type=int, default=16)
    p_sp.add_argument("--timeout", type=float, default=900.0)
    p_sp.add_argument("--play", action="store_true")

    sub.add_parser("voices")

    p_cl = sub.add_parser("clone")
    p_cl.add_argument("--name", required=True)
    p_cl.add_argument("--ref", required=True)
    p_cl.add_argument("--ref-text", dest="ref_text", default=None)
    p_cl.add_argument("--instruct", default=None)
    p_cl.add_argument("--language", default="Auto")
    p_cl.add_argument("--timeout", type=float, default=900.0)

    p_tr = sub.add_parser("transcribe")
    p_tr.add_argument("--audio", required=True)
    p_tr.add_argument("--language", default=None)
    p_tr.add_argument("--timeout", type=float, default=600.0)

    p_md = sub.add_parser("models")
    p_md.add_argument("--install", default=None)
    p_md.add_argument("--wait", type=int, default=2400)

    a = ap.parse_args()
    fn = {"status": cmd_status, "up": cmd_up, "down": cmd_down, "speak": cmd_speak,
          "voices": cmd_voices, "clone": cmd_clone, "transcribe": cmd_transcribe,
          "models": cmd_models}[a.cmd]
    try:
        out = fn(a)
    except Exception as e:  # noqa: BLE001 —— 顶层兜底也要带原因，不裸崩
        out = {"ok": False, "reason": "%s: %s" % (type(e).__name__, e)}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
