#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Figma REST 客户端（只读为主）—— 让本机**真的能碰 Figma**

## 为什么走 REST 而不是那 7 条 figma-* 技能
`gbt-figma` 规程的硬结论（本次逐条复验仍成立）：本机**没有** Figma 桌面版、
**没有** figma CLI/MCP、**没有** `FIGMA_*` 凭据、上游未 vendored
⇒ 那 7 条（Plugin API / MCP / Code Connect 那一套）**现在跑不动**。
而 **REST API 只要一个 Personal Access Token** 就能真跑，且**只读为主**、风险最小。
⇒ 本件是「**先跑通一条真路**」，不是把 7 条 stub 当成能用。

## 权威形状（不是印象，来自官方 OpenAPI 规格，已下到 `.scratch/figma/openapi.yaml`）
- 鉴权头：**`X-Figma-Token`**（另有 OAuth2 authorizationCode 一路）
- `GET /v1/me` → `{id, email, handle, img_url}`
- `GET /v1/files/{key}` → `{name, role, lastModified, editorType, thumbnailUrl, version, document, …}`
- `GET /v1/files/{key}/nodes?ids=1:2,1:3` → `{nodes: {"1:2": {document: …}}, err}`
- `GET /v1/images/{key}?ids=…&format=png&scale=2` → `{err, images: {"1:2": "<临时 URL>"}}`
- 节点字段：`id / name / type / absoluteBoundingBox / children / characters …`

## 三条纪律（写死在代码里）
1. **只从环境变量取凭据**，变量名由 `--token-env` 指定（默认 `FIGMA_TOKEN`）。
   🔴 **绝不去翻** `~/.figma`、MCP/CLI 的 config、token 缓存 —— 那是规程明令禁止的。
   只报「已配 / 未配」或前 4 位掩码，**绝不打印值**。
2. **缺凭据就如实报缺并停下**（`status:"no_credential"`，退出码 3）。
   🔴 **绝不用别的手段"绕"出一张稿子**：不读缓存、不拿截图当稿子、不凭印象编 frame 名。
3. **期望形状没对上时不崩、也不编**：把**真键名**原样报出来（`found_keys`），
   让下一次调用能照着改 —— 这比"猜对了"更重要。

## 用法
  python tools/codex-scripts/figma-fetch.py me
  python tools/codex-scripts/figma-fetch.py file  <file_key> [--json out.json]
  python tools/codex-scripts/figma-fetch.py nodes <file_key> --ids 1:2,1:3
  python tools/codex-scripts/figma-fetch.py export <file_key> --ids 1:2 --scale 2 --out render/figma
  python tools/codex-scripts/figma-fetch.py vars  <file_key>              # 设计令牌（Variables）
  # 🔵 离线：拿本地夹具跑同一套"摘要"逻辑（没凭据也能验解析）
  python tools/codex-scripts/figma-fetch.py file --from-json fixture.json
退出码：0 成功 · 2 参数/用法错 · 3 **缺凭据** · 4 HTTP 错 · 5 响应形状不认识
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
API = "https://api.figma.com"

# 帧/组件这类"有外接框"的节点；其余（DOCUMENT/CANVAS）当容器
BOX_TYPES = {"FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE", "GROUP", "RECTANGLE",
             "ELLIPSE", "VECTOR", "TEXT", "BOOLEAN_OPERATION", "LINE", "STAR", "POLYGON"}


def tok(env_name):
    """只从环境变量取；只报已配/未配；绝不打印值。"""
    v = os.environ.get(env_name)
    if not v:
        return None
    return v


def mask(env_name):
    v = os.environ.get(env_name)
    if not v:
        return "未配"
    return v[:4] + "****（长度 %d）" % len(v)


def http(path, token, timeout=60):
    """一次 GET。**HTTP 错原样带出**（Figma 的 err 文本是有用的）。"""
    req = urllib.request.Request(API + path, headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(body)
        except Exception:                                                  # noqa: BLE001
            j = {"raw": body[:400]}
        return e.code, j
    except Exception as e:                                                 # noqa: BLE001
        return 0, {"transport_error": "%s: %s" % (type(e).__name__, str(e)[:200])}


def digest_document(doc):
    """把 `document` 树摘成**可读清单**（id/type/name/尺寸/文本），不搬全量。"""
    pages, frames, texts = [], [], []
    counts = {}

    def walk(n, depth=0):
        if not isinstance(n, dict):
            return
        t = n.get("type") or "?"
        counts[t] = counts.get(t, 0) + 1
        bb = n.get("absoluteBoundingBox") or {}
        size = None
        if bb:
            size = [round(bb.get("width", 0), 1), round(bb.get("height", 0), 1)]
        if t == "CANVAS":
            pages.append({"id": n.get("id"), "name": n.get("name")})
        elif t in ("FRAME", "COMPONENT", "COMPONENT_SET") and depth <= 3:
            frames.append({"id": n.get("id"), "type": t, "name": n.get("name"), "size": size,
                           "kids": len(n.get("children") or [])})
        if t == "TEXT" and n.get("characters"):
            texts.append({"id": n.get("id"), "text": str(n["characters"])[:60]})
        for c in (n.get("children") or []):
            walk(c, depth + 1)

    walk(doc)
    return {"pages": pages, "frames": frames[:60], "texts": texts[:40],
            "type_counts": counts,
            "totals": {"pages": len(pages), "frames": len(frames), "texts": len(texts),
                       "nodes": sum(counts.values())}}


def shape_probe(j, wanted, label):
    """期望的键不在时**不崩**：把真键名报出来。"""
    if isinstance(j, dict) and wanted in j:
        return None
    keys = sorted(j.keys()) if isinstance(j, dict) else "（不是对象：%s）" % type(j).__name__
    return {"ok": False, "status": "shape_unexpected", "where": label,
            "wanted": wanted, "found_keys": keys,
            "_口径": "期望的键没出现 ⇒ 把**真键名**原样报出来，照着改；不猜、不编"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Figma REST 客户端（只读为主）")
    ap.add_argument("op", choices=["me", "file", "nodes", "export", "vars", "cred"])
    ap.add_argument("key", nargs="?", default="", help="file key（URL 里 /design/<key>/ 那一段）")
    ap.add_argument("--ids", default="", help="节点 id，逗号分隔（如 1:2,1:3）")
    ap.add_argument("--token-env", default="FIGMA_TOKEN")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--format", default="png", choices=["png", "jpg", "svg", "pdf"])
    ap.add_argument("--out", default="render/figma")
    ap.add_argument("--from-json", default="", help="离线：从本地夹具跑同一套摘要（不需要凭据）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    # ── 离线腿：夹具 → 摘要（**没凭据也能验解析**）────────────────────────────
    if a.from_json:
        try:
            j = json.loads(Path(a.from_json).read_text(encoding="utf-8", errors="replace"))
        except Exception as e:                                             # noqa: BLE001
            print(json.dumps({"ok": False, "status": "bad_fixture", "error": str(e)[:160]},
                             ensure_ascii=False))
            return 2
        doc = j.get("document") or (j.get("nodes", {}).get(a.ids.split(",")[0], {}) or {}).get("document")
        if not doc:
            print(json.dumps(shape_probe(j, "document", "fixture"), ensure_ascii=False, indent=1))
            return 5
        d = digest_document(doc)
        d.update({"ok": True, "status": "digested_from_fixture", "file_name": j.get("name"),
                  "_口径": "**离线腿**：只证明解析逻辑，不证明连上了 Figma"})
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0

    # ── 凭据闸（**只报已配/未配，绝不打印值，绝不去翻凭据**）──────────────────
    token = tok(a.token_env)
    cred = {"env": a.token_env, "状态": mask(a.token_env)}
    if a.op == "cred" or not token:
        print(json.dumps({
            "ok": False, "status": "no_credential", "cred": cred,
            "how": ("Figma 网页版 → 右上头像 → Settings → Security → Personal access tokens → "
                    "Generate new token（只勾 File content 的只读即可）；"
                    "然后在本机设 `setx %s <token>` 并**重开终端**" % a.token_env),
            "_口径": ("缺凭据就**如实报缺并停下**：不读缓存、不拿截图当稿子、不编 frame 名。"
                    "本件只从环境变量取，且只报已配/未配")
        }, ensure_ascii=False, indent=1))
        return 3

    # ── 在线腿 ───────────────────────────────────────────────────────────────
    if a.op == "me":
        st, j = http("/v1/me", token)
        if st != 200:
            print(json.dumps({"ok": False, "status": "http_error", "http": st, "body": j,
                              "cred": cred}, ensure_ascii=False, indent=1))
            return 4
        j["ok"] = True
        j["_口径"] = "身份只读；token 值绝不打印（只报前 4 位掩码）"
        print(json.dumps(j, ensure_ascii=False, indent=1))
        return 0

    if not a.key:
        print(json.dumps({"ok": False, "status": "usage", "need": "file key",
                          "hint": "URL 形如 https://www.figma.com/design/<file_key>/<name> 中间那段"},
                         ensure_ascii=False))
        return 2

    if a.op in ("file", "vars"):
        path = "/v1/files/%s" % urllib.parse.quote(a.key) if a.op == "file" \
            else "/v1/files/%s/variables/local" % urllib.parse.quote(a.key)
        st, j = http(path, token)
        if st != 200:
            print(json.dumps({"ok": False, "status": "http_error", "http": st, "body": j,
                              "cred": cred}, ensure_ascii=False, indent=1))
            return 4
        if a.op == "vars":
            # Variables 的响应形状本机**没验过**（Beta）：不猜键名，原样报结构
            j["ok"] = True
            j["_口径"] = "Variables(Beta)：响应形状本机**未验**，故原样报出顶层键与计数，不猜"
            if isinstance(j.get("meta"), dict):
                j["_meta_keys"] = sorted(j["meta"].keys())
            print(json.dumps(j, ensure_ascii=False, indent=1)[:4000])
            return 0
        bad = shape_probe(j, "document", "/v1/files/{key}")
        if bad:
            print(json.dumps(bad, ensure_ascii=False, indent=1))
            return 5
        d = digest_document(j["document"])
        d.update({"ok": True, "status": "file_read", "file_name": j.get("name"),
                  "role": j.get("role"), "lastModified": j.get("lastModified"),
                  "editorType": j.get("editorType"), "version": j.get("version"),
                  "thumbnailUrl": j.get("thumbnailUrl")})
        if a.json:
            Path(a.out).mkdir(parents=True, exist_ok=True)
            (Path(a.out) / ("file-%s.json" % a.key[:12])).write_text(
                json.dumps(j, ensure_ascii=False), encoding="utf-8")
            d["全量落盘"] = str(Path(a.out) / ("file-%s.json" % a.key[:12]))
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0

    if a.op == "nodes":
        if not a.ids:
            print(json.dumps({"ok": False, "status": "usage", "need": "--ids 1:2,1:3"},
                             ensure_ascii=False))
            return 2
        st, j = http("/v1/files/%s/nodes?ids=%s" % (urllib.parse.quote(a.key),
                                                    urllib.parse.quote(a.ids)), token)
        if st != 200:
            print(json.dumps({"ok": False, "status": "http_error", "http": st, "body": j},
                             ensure_ascii=False, indent=1))
            return 4
        bad = shape_probe(j, "nodes", "/v1/files/{key}/nodes")
        if bad:
            print(json.dumps(bad, ensure_ascii=False, indent=1))
            return 5
        out = {"ok": True, "status": "nodes_read", "err": j.get("err"), "nodes": {}}
        for nid, wrap in (j.get("nodes") or {}).items():
            doc = (wrap or {}).get("document")
            out["nodes"][nid] = digest_document(doc) if doc else {"_缺": "document"}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    if a.op == "export":
        if not a.ids:
            print(json.dumps({"ok": False, "status": "usage", "need": "--ids 1:2,1:3"},
                             ensure_ascii=False))
            return 2
        q = urllib.parse.urlencode({"ids": a.ids, "format": a.format, "scale": a.scale})
        st, j = http("/v1/images/%s?%s" % (urllib.parse.quote(a.key), q), token)
        if st != 200:
            print(json.dumps({"ok": False, "status": "http_error", "http": st, "body": j},
                             ensure_ascii=False, indent=1))
            return 4
        bad = shape_probe(j, "images", "/v1/images/{key}")
        if bad:
            print(json.dumps(bad, ensure_ascii=False, indent=1))
            return 5
        outdir = Path(a.out)
        outdir.mkdir(parents=True, exist_ok=True)
        saved, failed = [], []
        for nid, url in (j.get("images") or {}).items():
            if not url:
                failed.append({"id": nid, "why": "Figma 返回 null（该节点可能渲染不出）"})
                continue
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    blob = r.read()
                dst = outdir / ("%s-%s.%s" % (int(time.time()), nid.replace(":", "_"), a.format))
                dst.write_bytes(blob)                      # **逐字节**落盘
                saved.append({"id": nid, "file": str(dst), "bytes": len(blob),
                              "sha256_head": hashlib.sha256(blob).hexdigest()[:16]})
            except Exception as e:                                         # noqa: BLE001
                failed.append({"id": nid, "why": "%s: %s" % (type(e).__name__, str(e)[:120])})
        print(json.dumps({"ok": bool(saved), "status": "exported" if saved else "export_failed",
                          "figma_err": j.get("err"), "scale": a.scale, "format": a.format,
                          "saved": saved, "failed": failed,
                          "_口径": ("导出 URL 是**临时**的；图**逐字节**落盘。"
                                  "`ok` 只说明拿到了字节，**不说明好看** —— 审美走 gbt-aesthetic")},
                         ensure_ascii=False, indent=1))
        return 0 if saved else 5

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
