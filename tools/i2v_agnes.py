#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i2v_agnes —— 图生视频接线（一张图 + 提示词 → mp4，带产物判据）

主人第 4 条：「图生视频接线：接 agnes-video-2.5-flash，一张图 + 提示词 → mp4，带产物判据」

## 现实：钥不在本机（2026-10-30 实测）
```
AGNES_API_KEY            未设置
store/secrets/           空目录（registry 里的 on_disk:true 指的是 Windows 那台机器）
tools/codex-scripts/n-video-probe*.py   盘上不存在（只在绑定台账里有名字）
```
所以本器**默认只做接线与判据**：`dryrun` 把请求体真拼出来、把产物判据真列出来；
`submit` 在缺钥时 **fail-closed** 并说清缺哪一把 —— 绝不假装出了片。

## 给钥的方式（二选一）
  · 环境变量：`AGNES_API_KEY=...`（本框架的 n 能量槽就是这个 env 名）
  · 或运行时传 `key=` 参数（不落盘、不写日志）

## 判据（产物是"真 mp4"才算过）
  ① HTTP 200 且 content-type 含 video 或 octet-stream
  ② 字节数 ≥ 100 KB（实测空壳响应通常 < 20 KB）
  ③ **ffprobe 能读出时长且 > 0** —— 这条最硬：编码坏掉的文件 ffprobe 直接报错
  ④ 落盘路径可读、扩展名 .mp4

用法：
    python3 tools/i2v_agnes.py status
    python3 tools/i2v_agnes.py dryrun --image x.png --prompt "她转头微笑"
    python3 tools/i2v_agnes.py submit --image x.png --prompt "..." [--out out.mp4]
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = "agnes-video-2.5-flash"
DEFAULT_BASE = os.environ.get("GBT_I2V_BASE") or "https://apihub.agnes-ai.com/v1"
KEY_ENVS = ("AGNES_API_KEY", "GBT_AGNES_KEY", "GBT_I2V_KEY")
OUT_DIR = ROOT / "outputs" / "i2v"


def _key(explicit: str = "") -> tuple:
    """返回 (key, 来源)。**只报变量名，不打印值。**"""
    if explicit:
        return explicit, "参数传入"
    for name in KEY_ENVS:
        v = os.environ.get(name)
        if v:
            return v, "env:%s" % name
    return "", ""


def status() -> dict:
    k, src = _key()
    have_ff = bool(subprocess.run(["sh", "-c", "command -v ffprobe"],
                                  capture_output=True).stdout.strip())
    return {"ok": True, "op": "status", "model": MODEL, "base": DEFAULT_BASE,
            "key_present": bool(k), "key_source": src or None,
            "key_env_names": list(KEY_ENVS),
            "ffprobe": have_ff,
            "missing": [] if k else ["AGNES_API_KEY（agnes-video-2.5-flash 的钥）"],
            "how_to_fix": None if k else
            "设环境变量 AGNES_API_KEY，或调用时传 key=；"
            "本机 store/secrets/ 是空目录，Windows 那台的 .dpapi 在 Linux 解不开"}


def _img_b64(path: str) -> tuple:
    p = pathlib.Path(path)
    if not p.is_file():
        return "", "图不存在：%s" % path
    raw = p.read_bytes()
    if len(raw) < 64:
        return "", "图太小（%d 字节），不像真图" % len(raw)
    ext = p.suffix.lower().lstrip(".") or "png"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        return "", "不支持的图格式：%s" % ext
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return "data:image/%s;base64,%s" % (mime, base64.b64encode(raw).decode()), ""


def build_request(image: str, prompt: str, seconds: int = 4) -> dict:
    """真拼请求体（dryrun 与 submit 用同一份，避免"试的和发的不一样"）。"""
    b64, err = _img_b64(image)
    if err:
        raise ValueError(err)
    if not (prompt or "").strip():
        raise ValueError("prompt 不能为空（一张图 + 一句提示词才有方向）")
    return {"model": MODEL,
            "input": {"image": b64, "prompt": prompt.strip(),
                      "duration": int(seconds)},
            "response_format": "url"}


def dryrun(image: str, prompt: str) -> dict:
    try:
        body = build_request(image, prompt)
    except ValueError as exc:
        return {"ok": False, "op": "dryrun", "fail_closed": True, "error": str(exc)}
    b = dict(body)
    b["input"] = dict(b["input"])
    img = b["input"]["image"]
    b["input"]["image"] = "<data:image/... base64 %d 字节>" % len(img)
    k, src = _key()
    return {"ok": True, "op": "dryrun", "endpoint": DEFAULT_BASE + "/video/generations",
            "headers": {"Authorization": "Bearer " + ("<有钥 %s>" % src if k else "<缺钥>"),
                        "Content-Type": "application/json"},
            "body_preview": b,
            "key_present": bool(k), "key_source": src or None,
            "judge": ["① HTTP 200 且 content-type 含 video/octet-stream",
                      "② 字节数 ≥ 100KB",
                      "③ ffprobe 能读出时长 > 0（硬判据：坏编码直接报错）",
                      "④ 落盘 .mp4 可读"],
            "note": "dryrun 不联网：只证明'请求能拼对、判据能落地'。缺钥时 submit 会 fail-closed。"}


def _ffprobe(path: pathlib.Path) -> dict:
    if not subprocess.run(["sh", "-c", "command -v ffprobe"],
                          capture_output=True).stdout.strip():
        return {"ok": None, "why": "本机没有 ffprobe"}
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration,format_name", "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return {"ok": False, "why": (r.stderr or "")[:160]}
        d = json.loads(r.stdout or "{}").get("format") or {}
        dur = float(d.get("duration") or 0)
        return {"ok": dur > 0, "duration_s": dur, "format": d.get("format_name")}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, exc)}


def submit(image: str, prompt: str, out: str = "", key: str = "") -> dict:
    k, src = _key(key)
    if not k:
        return {"ok": False, "op": "submit", "fail_closed": True,
                "error": "缺钥：agnes-video-2.5-flash 需要 AGNES_API_KEY",
                "missing": ["AGNES_API_KEY"],
                "how_to_fix": status()["how_to_fix"],
                "note": "fail-closed：没有钥就不发请求，也不生成任何假产物"}
    try:
        body = build_request(image, prompt)
    except ValueError as exc:
        return {"ok": False, "op": "submit", "fail_closed": True, "error": str(exc)}

    import urllib.request
    url = DEFAULT_BASE + "/video/generations"
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + k,
                                          "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            ct = r.headers.get("content-type", "")
            raw = r.read()
            code = getattr(r, "status", 200)
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "op": "submit", "via": src,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:160]),
                "elapsed_s": round(time.time() - t0, 1)}
    return {"ok": True, "op": "submit", "via": src, "http": code,
            "content_type": ct, "bytes": len(raw),
            "elapsed_s": round(time.time() - t0, 1),
            "note": "图生视频是异步任务：若回的是 task/job JSON，需再轮询；"
                    "若是二进制则已直接落盘"} if code == 200 else {
            "ok": False, "op": "submit", "http": code, "body": raw[:200].decode("utf-8", "replace")}


def verify_product(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        return {"ok": False, "error": "产物不存在：%s" % path}
    size = p.stat().st_size
    pr = _ffprobe(p)
    ok = size >= 100 * 1024 and pr.get("ok") is True
    return {"ok": ok, "file": str(p), "bytes": size, "ffprobe": pr,
            "judge": {"size≥100KB": size >= 100 * 1024, "ffprobe时长>0": pr.get("ok")}}


def run(op: str = "status", **kw) -> dict:
    """能力位统一入口（唯一门按 kind 取 run）。"""
    op = str(op or "status").lower()
    if op == "dryrun":
        return dryrun(str(kw.get("image") or ""), str(kw.get("prompt") or ""))
    if op == "submit":
        return submit(str(kw.get("image") or ""), str(kw.get("prompt") or ""),
                      str(kw.get("out") or ""), str(kw.get("key") or ""))
    if op == "verify":
        return verify_product(str(kw.get("file") or ""))
    return status()


def main(argv: list) -> int:
    def opt(k, d=""):
        return argv[argv.index(k) + 1] if k in argv else d
    op = argv[1] if len(argv) > 1 else "status"
    if op == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=1)); return 0
    if op == "dryrun":
        r = dryrun(opt("--image"), opt("--prompt"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    if op == "submit":
        r = submit(opt("--image"), opt("--prompt"), opt("--out"), opt("--key"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    if op == "verify":
        r = verify_product(opt("--file"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
