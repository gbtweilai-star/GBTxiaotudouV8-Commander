# -*- coding: utf-8 -*-
"""agnes_image —— Agnes 生图接线（agnes-image-2.5-flash，文本 → PNG，带产物判据）

主人令（2026-11-07）：「参考 Agnes 文档，帮我接入生图，地址用 https://api.agnes-ai.cn/v1，
模型 agnes-image-2.5-flash，Key 在 xx 文件里。接好后生成一只坐在窗台上的橘猫」，
「图生视频也使用这个」。

## 实测口径（2026-11-07，别照抄别的文档）
```
GET  https://apihub.agnes-ai.com/v1/models        → 200，9 个模型，含
                                                    agnes-image-2.5-flash / agnes-video-2.5-flash /
                                                    agnes-image-2.1-flash / agnes-image-2.0-flash
GET  https://api.agnes-ai.cn/v1/models            → **401 无效的令牌**
POST .../v1/images/generations {response_format:url}      → 200，回 data[0].url + task_id（约 10s）
POST .../v1/images/generations {response_format:b64_json} → 200，回 data[0].b64_json（约 12s）
```
⇒ **同一把钥匙在 .cn 域名上是 401、在 apihub 域名上 200**。所以默认 base 用实测可用的
`apihub.agnes-ai.com`；`.cn` 只作为 `GBT_AGNES_BASE` 可选项保留（拿到 .cn 专用钥再切）。
不猜、不静默换域：`status` 会把两个域名都探一遍，把各自的真实回执写出来。

## 钥匙从哪来（按顺序，只报来源名，绝不回显明文）
1. 环境变量 `AGNES_API_KEY` / `GBT_AGNES_KEY`
2. 仓内 `store/secrets/agnes.key`（一行，纯文本，不写进代码）
3. `~/.dsh/.credentials.yaml` 的 `refs.GBT_API_KEY`（本机现用的那把，实测 200）

## 判据（产物是"真图"才算过）
① 文件扩充名 .png/.jpg 且 ≥ 8KB  ② 魔数对（PNG \\x89PNG / JPEG FFD8）  ③ PIL 能开且宽高 > 0

用法：
    python tools/agnes_image.py status
    python tools/agnes_image.py dryrun --prompt "..."
    python tools/agnes_image.py submit --prompt "..." [--size 1024x1024] [--out x.png]
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

_TOOLS_DIR = str(pathlib.Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
from agnes_keys import build_ring

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = os.environ.get("GBT_AGNES_IMAGE_MODEL") or "agnes-image-2.5-flash"
BASES = {
    "apihub": "https://apihub.agnes-ai.com/v1",
    "cn": "https://api.agnes-ai.cn/v1",
}
DEFAULT_BASE_KEY = (os.environ.get("GBT_AGNES_BASE_DOMAIN") or "apihub").strip().lower()
OUT_DIR = ROOT / "outputs" / "images"
KEY_ENVS = ("AGNES_API_KEY", "GBT_AGNES_KEY")


def base_url() -> str:
    """显式 GBT_AGNES_BASE 优先（可给完整 /v1 地址）；否则按域名别名取。"""
    explicit = (os.environ.get("GBT_AGNES_BASE") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    return BASES.get(DEFAULT_BASE_KEY, BASES["apihub"])


def _dsh_credential() -> str:
    """从 ~/.dsh/.credentials.yaml 的 refs.GBT_API_KEY 取（正则解析，不引 yaml 依赖）。"""
    p = pathlib.Path.home() / ".dsh" / ".credentials.yaml"
    if not p.is_file():
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:                                     # noqa: BLE001
        return ""
    m = re.search(r"^\s*GBT_API_KEY:\s*(\S+)\s*$", text, re.M)
    return m.group(1).strip() if m else ""


def key() -> tuple:
    """返回 (key, 来源名)。来源只报名字，不打印值。"""
    for name in KEY_ENVS:
        v = (os.environ.get(name) or "").strip()
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
    # 最后兜底：桌面密钥库（与 submit 的钥匙环同源）——否则只配了 txt 时
    # status/dryrun 会谎报「缺钥」，而 submit 明明能跑。
    try:
        from agnes_keys import load_keys
        ks = load_keys()
        if ks:
            return ks[0], "file:桌面图片生成视频生成密钥库.txt"
    except Exception:                                      # noqa: BLE001
        pass
    return "", ""


def _probe_models(base: str, k: str) -> dict:
    req = urllib.request.Request(base + "/models",
                                 headers={"Authorization": "Bearer " + k})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
            ids = [m.get("id") for m in (d.get("data") or [])]
            return {"http": r.status, "models": ids,
                    "has_image_model": MODEL in ids}
    except urllib.error.HTTPError as e:
        return {"http": e.code,
                "error": e.read().decode("utf-8", "replace")[:200]}
    except Exception as exc:                              # noqa: BLE001
        return {"error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}


def status(probe: bool = True) -> dict:
    k, src = key()
    out = {"ok": True, "op": "status", "model": MODEL,
           "base": base_url(), "base_domain": DEFAULT_BASE_KEY,
           "base_options": BASES,
           "key_present": bool(k), "key_source": src or None,
           "key_env_names": list(KEY_ENVS),
           "endpoint": base_url() + "/images/generations",
           "note": "2026-11-07 实测：.cn 域名对现用钥匙回 401；apihub 域名 200 且模型清单含 image/video"}
    if not k:
        out.update({"missing": ["AGNES_API_KEY / store/secrets/agnes.key / ~/.dsh refs.GBT_API_KEY"],
                    "how_to_fix": "写入 store/secrets/agnes.key（一行纯文本）或设 AGNES_API_KEY"})
        return out
    if probe:
        out["domains"] = {name: _probe_models(url, k) for name, url in BASES.items()}
    return out


def build_request(prompt: str, size: str = "1024x1024",
                  response_format: str = "b64_json") -> dict:
    if not (prompt or "").strip():
        raise ValueError("prompt 不能为空（生图要有画面描述）")
    return {"model": MODEL, "prompt": prompt.strip(), "size": size,
            "response_format": response_format, "n": 1}


def dryrun(prompt: str, size: str = "1024x1024") -> dict:
    try:
        body = build_request(prompt, size)
    except ValueError as exc:
        return {"ok": False, "op": "dryrun", "fail_closed": True, "error": str(exc)}
    k, src = key()
    return {"ok": True, "op": "dryrun",
            "endpoint": base_url() + "/images/generations",
            "headers": {"Authorization": "Bearer " + ("<有钥 %s>" % src if k else "<缺钥>"),
                        "Content-Type": "application/json"},
            "body_preview": body, "key_present": bool(k), "key_source": src or None,
            "judge": ["① 文件 ≥ 8KB", "② 魔数 PNG/JPEG", "③ PIL 能开且宽高 > 0"],
            "note": "dryrun 不联网：只证明请求能拼对、判据能落地。"}


def _post(url: str, k: str, body: dict, timeout: float = 240.0,
          retries: int = 2) -> dict:
    data = json.dumps(body).encode("utf-8")
    waited = 0.0
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data,
                                     headers={"Authorization": "Bearer " + k,
                                              "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                return {"ok": True, "http": r.status,
                        "elapsed_s": round(time.time() - t0, 1), "body": raw}
        except urllib.error.HTTPError as e:
            code = e.code
            text = e.read().decode("utf-8", "replace")
            if code == 429 and attempt < retries:
                back = 20.0 * (2 ** attempt)
                waited += back
                time.sleep(back)
                continue
            return {"ok": False, "http": code, "error": text[:400],
                    "elapsed_s": round(time.time() - t0, 1)}
        except Exception as exc:                          # noqa: BLE001
            return {"ok": False,
                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                    "elapsed_s": round(time.time() - t0, 1)}
    return {"ok": False, "error": "重试耗尽", "wait_s": round(waited, 1)}


def _decode(out: dict) -> tuple:
    """从回执里取出 (bytes, url)；b64/url 两种都认。"""
    raw = out.get("body") or ""
    try:
        d = json.loads(raw)
    except Exception:                                     # noqa: BLE001
        return b"", "", "回执不是 JSON"
    items = d.get("data") or []
    if not items:
        return b"", "", "回执无 data（%s）" % raw[:160]
    first = items[0] or {}
    url = str(first.get("url") or "")
    b64 = str(first.get("b64_json") or "")
    if b64:
        try:
            return base64.b64decode(b64), url, ""
        except Exception as exc:                          # noqa: BLE001
            return b"", url, "b64 解码失败：%s" % exc
    if url:
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read(), url, ""
        except Exception as exc:                          # noqa: BLE001
            return b"", url, "下载 url 失败：%s" % exc
    return b"", url, "既无 b64_json 也无 url"


def verify_product(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        return {"ok": False, "error": "产物不存在：%s" % path}
    raw = p.read_bytes()
    size = len(raw)
    magic = ("png" if raw[:8] == b"\x89PNG\r\n\x1a\n"
             else "jpeg" if raw[:2] == b"\xff\xd8" else "unknown")
    dims = None
    try:
        from PIL import Image
        with Image.open(p) as im:
            dims = list(im.size)
    except Exception:                                     # noqa: BLE001
        dims = None
    judge = {"size>=8KB": size >= 8 * 1024, "magic": magic in ("png", "jpeg"),
             "pil_opens": bool(dims)}
    return {"ok": all(judge.values()), "file": str(p), "bytes": size,
            "magic": magic, "size_px": dims, "judge": judge}


def submit(prompt: str, size: str = "1024x1024", out: str = "",
           response_format: str = "b64_json") -> dict:
    """用钥匙环轮转提交。429 时自动冷却并切下一把；全部耗尽才返回失败。"""
    try:
        body = build_request(prompt, size, response_format)
    except ValueError as exc:
        return {"ok": False, "op": "submit", "fail_closed": True, "error": str(exc)}

    ring = build_ring()
    if not ring.keys:
        return {"ok": False, "op": "submit", "fail_closed": True,
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
        # 环内换钥：不让 _post 自己睡 20/40 秒（那会把 17 把钥匙的轮转拖成十几分钟），
        # 429 立刻回给环，由环冷却并切下一把。
        r = _post(base_url() + "/images/generations", k, body, retries=0)
        http = r.get("http")
        if r.get("ok"):
            ring.mark_success(idx)
            raw, url, err = _decode(r)
            if err:
                return {"ok": False, "op": "submit", "via": "%d" % idx,
                        "via_tail": ring.keys[idx][-6:], "model": MODEL,
                        "error": err, "elapsed_s": r.get("elapsed_s")}
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            name = pathlib.Path(out).name if out else \
                "agnes-%s.png" % time.strftime("%Y%m%d_%H%M%S")
            path = OUT_DIR / name
            tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
            with open(tmp, "wb") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            v = verify_product(str(path))
            return {"ok": bool(v.get("ok")), "op": "submit", "via": "%d" % idx,
                    "via_tail": ring.keys[idx][-6:], "model": MODEL,
                    "endpoint": base_url() + "/images/generations",
                    "elapsed_s": r.get("elapsed_s"), "file": str(path),
                    "bytes": len(raw), "remote_url": url or None,
                    "verify": v, "prompt": prompt,
                    "ring": {"tried": tries, "active": ring.active_count(),
                             "total": len(ring.keys)}}
        last_error = r.get("error")
        last_http = http
        if http == 429:
            retry_after = None
            try:
                retry_after = float(r.get("retry_after")) if r.get("retry_after") else None
            except Exception:  # noqa: BLE001
                pass
            ring.mark_rate_limited(idx, retry_after)
            continue
        # 非 429 的硬错误（401/400 等）不再切换，直接返回
        return {"ok": False, "op": "submit", "via": "%d" % idx,
                "via_tail": ring.keys[idx][-6:], "model": MODEL,
                "http": http, "error": last_error,
                "elapsed_s": r.get("elapsed_s"),
                "ring": {"tried": tries, "active": ring.active_count(),
                         "total": len(ring.keys)}}

    # 全部钥匙都冷却或失败
    return {"ok": False, "op": "submit", "fail_closed": True,
            "error": last_error or "全部钥匙均受限或失败",
            "http": last_http, "model": MODEL,
            "ring": {"tried": tries, "active": ring.active_count(),
                     "total": len(ring.keys)},
            "how_to_fix": "等待冷却后重试，或把密钥库里新的 sk- 追加进去"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "dryrun":
        return dryrun(str(kw.get("prompt") or ""), str(kw.get("size") or "1024x1024"))
    if op == "submit":
        return submit(str(kw.get("prompt") or ""), str(kw.get("size") or "1024x1024"),
                      str(kw.get("out") or ""),
                      str(kw.get("response_format") or "b64_json"))
    if op == "verify":
        return verify_product(str(kw.get("file") or ""))
    if op == "keys":
        ring = build_ring()
        return {"ok": True, "op": "keys", "total": len(ring.keys),
                "ring": ring.summary()}
    return status(bool(kw.get("probe", True)))


def main(argv: list) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                      # noqa: BLE001
        pass
    def opt(k, d=""):
        return argv[argv.index(k) + 1] if k in argv else d
    op = argv[1] if len(argv) > 1 else "status"
    if op == "keys":
        r = run("keys")
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    if op == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=1)); return 0
    if op == "dryrun":
        r = dryrun(opt("--prompt"), opt("--size", "1024x1024"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    if op == "submit":
        r = submit(opt("--prompt"), opt("--size", "1024x1024"), opt("--out"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    if op == "verify":
        r = verify_product(opt("--file"))
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r.get("ok") else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
