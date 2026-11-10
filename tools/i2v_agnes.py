#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i2v_agnes —— Agnes 图生视频接线（官方 OpenAI Videos 兼容口径）

主人令 2026-11-07：「图生视频也使用这个（Agnes）」

## 官方口径（2026-11-07 取自 agnes-ai.cn/zh-Hans/docs/agnes-video-25-flash，实测校准）
```
POST {base}/videos
  { "model": "agnes-video-2.5-flash", "prompt": "...", "mode": "text|keyframe|reference",
    "seconds": "5"（字符串 4–12）, "size": "720P"（Flash 只认这个值）,
    "aspect_ratio": "16:9|9:16|1:1|4:3|3:4|21:9" }
  mode=keyframe  → first_frame / last_frame（至少给一个）
  mode=reference → images[]（≤5）/ audios[]（≤3）；Flash 不接受 videos
GET  {host}/agnesapi?video_id=<id>&model_name=agnes-video-2.5-flash   ← 轮询用这个
      completed 后从顶层 `url` 取视频地址
```
⚠️ 官方写明：媒体 URL 必须**可被 Agnes 服务公网访问**。本机图片是本地文件，
所以默认会先试 `data:` URI（有些实现放行）；若上游拒绝，**如实报 needs_public_url**，
把图上传到公网（图床 / 对象存储）后再用 `--image-url` 传入 —— 绝不假装出了片。

## 钥匙（与生图共用，只报来源名）
① env `AGNES_API_KEY` / `GBT_AGNES_KEY` / `GBT_I2V_KEY`
② 仓内 `store/secrets/agnes.key`
③ `~/.dsh/.credentials.yaml` 的 `refs.GBT_API_KEY`（本机现用，实测 200）

## 判据（产物是"真 mp4"才算过）
① 文件 ≥ 100KB  ② ffprobe 能读出时长 > 0（硬判据）  ③ 落盘 .mp4 可读

用法：
    python tools/i2v_agnes.py status
    python tools/i2v_agnes.py text   --prompt "..." [--seconds 5]
    python tools/i2v_agnes.py submit --image x.png --prompt "..." [--mode keyframe]
    python tools/i2v_agnes.py poll   --video-id <id>
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import sys

_TOOLS_DIR = str(pathlib.Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from agnes_keys import build_ring

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = os.environ.get("GBT_AGNES_VIDEO_MODEL") or "agnes-video-2.5-flash"
BASES = {
    "apihub": "https://apihub.agnes-ai.com/v1",
    "cn": "https://api.agnes-ai.cn/v1",
}
DEFAULT_BASE = (os.environ.get("GBT_I2V_BASE")
                or os.environ.get("GBT_AGNES_BASE")
                or BASES["apihub"]).rstrip("/")
KEY_ENVS = ("AGNES_API_KEY", "GBT_AGNES_KEY", "GBT_I2V_KEY")
OUT_DIR = ROOT / "outputs" / "i2v"
MODES = ("text", "keyframe", "reference")
ASPECTS = ("16:9", "9:16", "1:1", "4:3", "3:4", "21:9")


def _host() -> str:
    """轮询端点 /agnesapi 挂在域名根上，不在 /v1 下面。"""
    b = DEFAULT_BASE
    return b[:-3].rstrip("/") if b.endswith("/v1") else b


def _dsh_credential() -> str:
    p = pathlib.Path.home() / ".dsh" / ".credentials.yaml"
    if not p.is_file():
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        return ""
    m = re.search(r"^\s*GBT_API_KEY:\s*(\S+)\s*$", text, re.M)
    return m.group(1).strip() if m else ""


def _key(explicit: str = "") -> tuple:
    if explicit:
        return explicit, "参数传入"
    for name in KEY_ENVS:
        v = os.environ.get(name)
        if v:
            return v, "env:%s" % name
    f = ROOT / "store" / "secrets" / "agnes.key"
    if f.is_file():
        v = f.read_text(encoding="utf-8", errors="replace").strip()
        if v:
            return v, "file:store/secrets/agnes.key"
    v = _dsh_credential()
    if v:
        return v, "file:~/.dsh/.credentials.yaml#refs.GBT_API_KEY"
    # 最后兜底：桌面密钥库（与 create 的钥匙环同源）——否则只配了 txt 时
    # status/poll 会谎报「缺钥」，而 create 明明能跑。
    try:
        from agnes_keys import load_keys
        ks = load_keys()
        if ks:
            return ks[0], "file:桌面图片生成视频生成密钥库.txt"
    except Exception:                                        # noqa: BLE001
        pass
    return "", ""


def status() -> dict:
    k, src = _key()
    return {"ok": True, "op": "status", "model": MODEL, "base": DEFAULT_BASE,
            "create_endpoint": DEFAULT_BASE + "/videos",
            "poll_endpoint": _host() + "/agnesapi",
            "modes": list(MODES), "aspects": list(ASPECTS),
            "size": "720P", "seconds_range": ["4", "12"],
            "key_present": bool(k), "key_source": src or None,
            "key_env_names": list(KEY_ENVS),
            "ffprobe": bool(shutil.which("ffprobe")),
            "missing": [] if k else ["AGNES_API_KEY（agnes-video-2.5-flash 的钥）"],
            "how_to_fix": None if k else
            "设 AGNES_API_KEY，或写 store/secrets/agnes.key，"
            "或用 ~/.dsh/.credentials.yaml 的 refs.GBT_API_KEY（本机现用，实测 200）",
            "media_rule": "官方要求 first_frame/images 是**公网可访问 URL**；本机文件先试 data: URI，"
                          "被拒则如报 needs_public_url（不伪造产物）"}


def _img_ref(image: str) -> tuple:
    """把本地图变成能发给上游的引用：http(s) URL 原样；本地文件转 data: URI。"""
    s = (image or "").strip()
    if not s:
        return "", ""
    if s.startswith(("http://", "https://")):
        return s, ""
    p = pathlib.Path(s)
    if not p.is_file():
        return "", "图不存在：%s" % s
    raw = p.read_bytes()
    if len(raw) < 64:
        return "", "图太小（%d 字节），不像真图" % len(raw)
    ext = p.suffix.lower().lstrip(".") or "png"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        return "", "不支持的图格式：%s" % ext
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return "data:image/%s;base64,%s" % (mime, base64.b64encode(raw).decode()), ""


def build_request(prompt: str, mode: str = "text", image: str = "",
                  seconds: str = "5", aspect: str = "16:9",
                  last_frame: str = "") -> dict:
    mode = (mode or "text").lower()
    if mode not in MODES:
        raise ValueError("mode 只能是 %s" % "/".join(MODES))
    if not (prompt or "").strip():
        raise ValueError("prompt 不能为空（视频要有画面与运动描述）")
    try:
        sec = str(int(str(seconds)))
    except Exception:                                        # noqa: BLE001
        sec = "5"
    if not 4 <= int(sec) <= 12:
        raise ValueError('seconds 只支持 "4"–"12"')
    body = {"model": MODEL, "prompt": prompt.strip(), "mode": mode,
            "seconds": sec, "size": "720P", "n": 1,
            "aspect_ratio": aspect if aspect in ASPECTS else "16:9"}
    if mode in ("keyframe", "reference"):
        ref, err = _img_ref(image) if image else ("", "该模式需要图片：给 --image")
        if err:
            raise ValueError(err)
        if mode == "keyframe":
            body["first_frame"] = ref
            if last_frame:
                lf, lerr = _img_ref(last_frame)
                if lerr:
                    raise ValueError(lerr)
                body["last_frame"] = lf
            if "last_frame" not in body and not ref.startswith("data:"):
                pass
        else:
            body["images"] = [ref]
    return body


def _post(url: str, k: str, body: dict, timeout: float = 120.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + k,
                                          "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return {"ok": True, "http": r.status,
                    "elapsed_s": round(time.time() - t0, 1), "body": raw}
    except urllib.error.HTTPError as e:
        return {"ok": False, "http": e.code,
                "error": e.read().decode("utf-8", "replace")[:500],
                "elapsed_s": round(time.time() - t0, 1)}
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "elapsed_s": round(time.time() - t0, 1)}


def _json(out: dict) -> dict:
    try:
        return json.loads(out.get("body") or "{}")
    except Exception:                                        # noqa: BLE001
        return {}


def create(body: dict, key: str = "") -> dict:
    """用钥匙环轮转提交视频任务。429 时自动冷却并切下一把；全部耗尽才返回失败。"""
    try:
        body_validated = body
    except ValueError as exc:
        return {"ok": False, "op": "create", "fail_closed": True, "error": str(exc)}

    ring = build_ring()
    if not ring.keys:
        return {"ok": False, "op": "create", "fail_closed": True,
                "error": "缺钥：桌面 图片生成视频生成密钥库.txt 未提取到任何 sk- 钥匙",
                "missing": ["AGNES_API_KEY / 密钥库"],
                "how_to_fix": "在桌面 图片生成视频生成密钥库.txt 里保留 sk-... 密钥，每行或空格分隔均可"}

    last_error = None
    last_http = None
    tries = []
    tried_idx = set()
    for _ in range(len(ring.keys)):
        k, idx = ring.next_key()
        if k is None or idx in tried_idx:
            break
        tried_idx.add(idx)
        tries.append(idx)
        r = _post(DEFAULT_BASE + "/videos", k, body_validated)
        http = r.get("http")
        if r.get("ok"):
            ring.mark_success(idx)
            d = _json(r)
            vid = d.get("video_id") or d.get("id") or d.get("task_id")
            return {"ok": bool(vid), "op": "create", "via": "%d" % idx,
                    "via_tail": ring.keys[idx][-6:], "http": r.get("http"),
                    "video_id": vid, "task_id": d.get("id") or d.get("task_id"),
                    "status": d.get("status"), "raw_keys": sorted(d)[:20],
                    "elapsed_s": r.get("elapsed_s"),
                    "ring": {"tried": tries, "active": ring.active_count(),
                             "total": len(ring.keys)}}
        last_error = str(r.get("error") or "")
        last_http = http
        if http == 429:
            retry_after = None
            try:
                retry_after = float(r.get("retry_after")) if r.get("retry_after") else None
            except Exception:  # noqa: BLE001
                pass
            ring.mark_rate_limited(idx, retry_after)
            hint = None
            if "data:image" in str(body_validated.get("first_frame", "")) + \
                    str(body_validated.get("images", "")):
                hint = ("上游拒绝内联 data: URI 图片：官方要求媒体是公网 URL。"
                        "把图传到图床/对象存储后用 --image-url 重试")
            continue
        # 非 429 的硬错误（401/400 等）不再切换，直接返回
        hint = None
        if "data:image" in str(body_validated.get("first_frame", "")) + \
                str(body_validated.get("images", "")) and http in (400, 422):
            hint = ("上游拒绝内联 data: URI 图片：官方要求媒体是公网 URL。"
                    "把图传到图床/对象存储后用 --image-url 重试")
        return {"ok": False, "op": "create", "via": "%d" % idx,
                "via_tail": ring.keys[idx][-6:], "model": MODEL,
                "http": http, "error": last_error[:400],
                "needs_public_url": hint,
                "elapsed_s": r.get("elapsed_s"),
                "ring": {"tried": tries, "active": ring.active_count(),
                         "total": len(ring.keys)}}

    # 全部钥匙都冷却或失败
    return {"ok": False, "op": "create", "fail_closed": True,
            "error": last_error or "全部钥匙均受限或失败",
            "http": last_http, "model": MODEL,
            "ring": {"tried": tries, "active": ring.active_count(),
                     "total": len(ring.keys)},
            "how_to_fix": "等待冷却后重试，或把密钥库里新的 sk- 追加进去"}


def poll(video_id: str, key: str = "", timeout_s: float = 900.0,
         interval_s: float = 2.0) -> dict:
    k, src = _key(key)
    if not k:
        return {"ok": False, "op": "poll", "fail_closed": True,
                "error": "缺钥", "missing": ["AGNES_API_KEY"]}
    if not video_id:
        return {"ok": False, "op": "poll", "error": "缺 video_id"}
    qs = urllib.parse.urlencode({"video_id": video_id, "model_name": MODEL})
    url = _host() + "/agnesapi?" + qs
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout_s:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + k})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                last = json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            return {"ok": False, "op": "poll", "http": e.code,
                    "error": e.read().decode("utf-8", "replace")[:300],
                    "waited_s": round(time.time() - t0, 1)}
        except Exception as exc:                             # noqa: BLE001
            return {"ok": False, "op": "poll",
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
        st = str(last.get("status") or "")
        if st in ("completed", "succeeded"):
            return {"ok": bool(last.get("url")), "op": "poll", "status": st,
                    "url": last.get("url"), "seconds": last.get("seconds"),
                    "size": last.get("size"), "waited_s": round(time.time() - t0, 1),
                    "video_id": video_id}
        if st in ("failed", "error", "cancelled"):
            return {"ok": False, "op": "poll", "status": st,
                    "error": str(last.get("error"))[:400],
                    "waited_s": round(time.time() - t0, 1)}
        time.sleep(interval_s)
    return {"ok": False, "op": "poll", "status": last.get("status"),
            "error": "轮询超时（%.0fs）" % timeout_s,
            "progress": last.get("progress"), "waited_s": round(time.time() - t0, 1)}


def download(url: str, out: str = "") -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = pathlib.Path(out).name if out else "i2v-%s.mp4" % time.strftime("%Y%m%d_%H%M%S")
    p = OUT_DIR / name
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
            raw = r.read()
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "op": "download", "error": str(exc)[:200]}
    tmp = p.with_name("%s.tmp-%d" % (p.name, os.getpid()))
    with open(tmp, "wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
    v = verify_product(str(p))
    return {"ok": bool(v.get("ok")), "op": "download", "file": str(p),
            "bytes": len(raw), "verify": v}


def _ffprobe(path: pathlib.Path) -> dict:
    if not shutil.which("ffprobe"):
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
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, exc)}


def verify_product(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        return {"ok": False, "error": "产物不存在：%s" % path}
    n = p.stat().st_size
    pr = _ffprobe(p)
    return {"ok": n >= 100 * 1024 and pr.get("ok") is True, "file": str(p),
            "bytes": n, "ffprobe": pr,
            "judge": {"size>=100KB": n >= 100 * 1024, "ffprobe时长>0": pr.get("ok")}}


def dryrun(body: dict) -> dict:
    shown = dict(body)
    for f in ("first_frame", "last_frame"):
        if isinstance(shown.get(f), str) and shown[f].startswith("data:"):
            shown[f] = "<data-uri %d 字节>" % len(shown[f])
    if isinstance(shown.get("images"), list):
        shown["images"] = ["<data-uri %d 字节>" % len(x) if isinstance(x, str)
                           and x.startswith("data:") else x for x in shown["images"]]
    k, src = _key()
    return {"ok": True, "op": "dryrun", "endpoint": DEFAULT_BASE + "/videos",
            "poll": _host() + "/agnesapi?video_id=<id>&model_name=" + MODEL,
            "body_preview": shown, "key_present": bool(k), "key_source": src or None,
            "note": "dryrun 不联网：只证明请求体按官方口径拼对了。"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "create":
        try:
            body = build_request(str(kw.get("prompt") or ""), str(kw.get("mode") or "text"),
                                 str(kw.get("image") or kw.get("image_url") or ""),
                                 str(kw.get("seconds") or "5"),
                                 str(kw.get("aspect_ratio") or "16:9"),
                                 str(kw.get("last_frame") or ""))
        except ValueError as exc:
            return {"ok": False, "op": "create", "fail_closed": True, "error": str(exc)}
        return create(body, str(kw.get("key") or ""))
    if op == "dryrun":
        try:
            body = build_request(str(kw.get("prompt") or "一只猫抬头看镜头"),
                                 str(kw.get("mode") or "text"),
                                 str(kw.get("image") or kw.get("image_url") or ""),
                                 str(kw.get("seconds") or "5"),
                                 str(kw.get("aspect_ratio") or "16:9"))
        except ValueError as exc:
            return {"ok": False, "op": "dryrun", "fail_closed": True, "error": str(exc)}
        return dryrun(body)
    if op == "poll":
        return poll(str(kw.get("video_id") or ""), str(kw.get("key") or ""),
                    float(kw.get("timeout_s") or 900))
    if op == "download":
        return download(str(kw.get("url") or ""), str(kw.get("out") or ""))
    if op == "run":
        try:
            body = build_request(str(kw.get("prompt") or ""), str(kw.get("mode") or "text"),
                                 str(kw.get("image") or kw.get("image_url") or ""),
                                 str(kw.get("seconds") or "5"),
                                 str(kw.get("aspect_ratio") or "16:9"))
        except ValueError as exc:
            return {"ok": False, "op": "run", "fail_closed": True, "error": str(exc)}
        c = create(body, str(kw.get("key") or ""))
        if not c.get("ok"):
            return c
        # poll 必须用「创建时那把钥匙」：环换过钥后，poll 若拿默认单钥会缺钥/串钥。
        poll_key = str(kw.get("key") or "")
        if not poll_key:
            try:
                via = c.get("via")
                ring = build_ring()
                if ring.keys and via is not None:
                    poll_key = ring.keys[int(via)]
            except Exception:                                # noqa: BLE001
                poll_key = ""
        p = poll(str(c.get("video_id") or ""), poll_key)
        if not p.get("ok") or not p.get("url"):
            return {"ok": False, "op": "run", "create": c, "poll": p}
        d = download(str(p["url"]), str(kw.get("out") or ""))
        return {"ok": bool(d.get("ok")), "op": "run", "create": c, "poll": p,
                "download": d}
    if op == "verify":
        return verify_product(str(kw.get("file") or ""))
    if op == "keys":
        ring = build_ring()
        return {"ok": True, "op": "keys", "total": len(ring.keys),
                "ring": ring.summary()}
    return status()


def main(argv: list) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                        # noqa: BLE001
        pass
    def opt(k, d=""):
        return argv[argv.index(k) + 1] if k in argv else d
    op = argv[1] if len(argv) > 1 else "status"
    payloads = {
        "keys": {"op": "keys"},
        "status": {},
        "text": {"op": "run", "mode": "text", "prompt": opt("--prompt", "一只橘猫抬头看镜头"),
                 "seconds": opt("--seconds", "5"), "aspect_ratio": opt("--aspect", "16:9")},
        "submit": {"op": "run", "mode": opt("--mode", "keyframe"),
                   "image": opt("--image-url", "") or opt("--image", ""),
                   "prompt": opt("--prompt"), "seconds": opt("--seconds", "5")},
        "create": {"op": "create", "mode": opt("--mode", "text"), "prompt": opt("--prompt"),
                   "image": opt("--image-url", "") or opt("--image", ""),
                   "seconds": opt("--seconds", "5")},
        "dryrun": {"op": "dryrun", "mode": opt("--mode", "text"),
                   "prompt": opt("--prompt"), "image": opt("--image", "")},
        "poll": {"op": "poll", "video_id": opt("--video-id")},
        "verify": {"op": "verify", "file": opt("--file")},
    }
    if op not in payloads:
        print(__doc__)
        return 2
    r = run(payloads[op].pop("op", "status"), **payloads[op])
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
