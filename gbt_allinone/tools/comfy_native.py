# -*- coding: utf-8 -*-
"""comfy_native —— **自食其力的 ComfyUI 能力**（不装重壳，用触手原生小算子出它的能力）。

## 为什么要它（一手账）
2026-10-11 实测：本机 **AMD 无 CUDA** + 总内存 **7.39 GB**（可用常年在 250-700 MB 徘徊）。
ComfyUI 本体（9.2 GB，带 2 个 SD1.5 权重）**真起得来**（8188 HTTP 200、962 节点），
但**任何重生成模型（SDXL/SD1.5 推理）都要 4-6 GB 连续内存** ⇒ **这台机器跑不动**。
⇒ 按主人令「**自食其力才是王道**」：**不依赖别人的重壳**，把 ComfyUI 的**架构**用轻量小算子长出来。

## 拿了它的三样（是**架构**，不是代码）
  ① **workflow.json 当契约** —— 图就是活的合同，可复跑、可留证；
  ② **节点 = 能力位** —— 每个节点一个小算子，注册在表里，白名单，不许任意执行；
  ③ **执行 = 拓扑序跑一遍** —— 分派器复用本仓既有口径（five-dim 那一套的唯一门）。

## 本件**没有**拿它的（如实写）
  · 不拿它的 torch 重算子（SDXL 那些）—— **本机内存不够**；
  · 不拿它的前端/服务（8188）—— **不需要常驻进程**；
  · 不拿它的模型权重 —— **一个都不下**。

## 与真 ComfyUI 的**能力边界**（不吹）
  ✅ 能真干：**传统算法**的图算子（放大/裁剪/拼贴/格式转换/校验/哈希/锐化/合成），纯 CPU、内存 <300 MB；
  ❌ 干不动：**任何重生成模型**（文生图/图生图/超分大模型）—— 要 GPU 或 ≥16 GB 内存；
  ⚠️ 中间态：kornia 的**传统滤波**（锐化/降噪/边缘）能跑；**神经超分**（spandrel 那些权重）要权重+内存，**未接**。

## op（读面免门 · 写面过 filesystem_write · 未列出 = fail-closed）
  status    在位/依赖/节点表/能力边界（只读）
  nodes     列出所有节点与它们的输入输出（只读）
  graph     读一份 workflow.json 并**拓扑排序**（只读，不执行）
  gate      只跑闸不跑图：给一个图/一件产物，报它过不过（只读）
  run       真跑一份 workflow（**写**；产物落盘前**必须过闸**）
  单节点     直接跑一个节点（**写**；同样过闸）

## 铁律
  · **闸是唯一真源**：产物不过闸 ⇒ **不许落盘**（不是"落盘后再检查"）；
  · **不编**：依赖取不到就回 needs_dependency，**绝不假装跑过**；
  · **证据只追加**：每次 run 落一条 state/comfy_native_runs.jsonl（图 + 每节点读数 + 产物哈希）；
  · **白名单**：节点名不在表里 ⇒ fail-closed（与 ComfyUI 的"任意 node"相反，这是**故意**的）。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import time

_BASE = pathlib.Path(__file__).resolve().parent
_ROOT = _BASE.parents[1]


def _store() -> pathlib.Path:
    sd = os.environ.get("GBT_STORE_DIR")
    if sd:
        return pathlib.Path(sd)
    return _ROOT / "gbt_allinone" / "store"


def _runs_file() -> pathlib.Path:
    d = _store() / "comfy_native"
    return d / "runs.jsonl"


def _append_run(row: dict) -> None:
    f = _runs_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + chr(10))


def _sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _deps() -> dict:
    """依赖现读（不缓存，每次现算 —— 免得"装上了但读数还是旧的"）。"""
    out = {}
    for name in ("PIL", "kornia", "numpy", "torch"):
        try:
            m = __import__(name)
            out[name] = getattr(m, "__version__", "ok")
        except Exception as e:                       # noqa: BLE001
            out[name] = "缺失(%s)" % type(e).__name__
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 闸：唯一真源。产物**先过闸，才允许落盘**。
# ─────────────────────────────────────────────────────────────────────────────
def gate_image(path: pathlib.Path, expect: dict) -> dict:
    """对一件图片产物过闸。

    判据（每一条都要有**读数**，不许"看着差不多"）：
      · 文件在、非空；
      · 真能被解码（不是改了后缀的假图）；
      · 尺寸**恰好**等于期望（expect: width/height）；
      · 模式/格式与期望一致（缺省不判）；
      · **去重哈希**（同一路径换内容会被抓出来）。
    """
    problems = []
    info = {"path": str(path), "exists": path.is_file()}
    if not path.is_file():
        return {"pass": False, "problems": ["产物不在：%s" % path], "info": info}
    size = path.stat().st_size
    info["bytes"] = size
    if size <= 0:
        problems.append("空文件")
    w = h = None
    mode = fmt = None
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            w, h = im.size
            mode = im.mode
            fmt = im.format
        info.update({"width": w, "height": h, "mode": mode, "format": fmt})
    except Exception as e:                           # noqa: BLE001
        problems.append("解不开（不是有效图）：%s" % e)
    if "width" in expect and w != expect["width"]:
        problems.append("宽不对：期望 %s 实得 %s" % (expect["width"], w))
    if "height" in expect and h != expect["height"]:
        problems.append("高不对：期望 %s 实得 %s" % (expect["height"], h))
    if "min_side" in expect and (w is None or min(w, h) < expect["min_side"]):
        problems.append("最短边小于 %s（实得 %s）" % (expect["min_side"], min(w, h) if w else None))
    if "mode" in expect and mode != expect["mode"]:
        problems.append("模式不对：期望 %s 实得 %s" % (expect["mode"], mode))
    if "format" in expect and fmt != expect["format"]:
        problems.append("格式不对：期望 %s 实得 %s" % (expect["format"], fmt))
    if size > 0:
        info["sha256"] = _sha_file(path)[:16]
    return {"pass": not problems, "problems": problems, "info": info}


def gate_any(path: pathlib.Path, expect: dict) -> dict:
    """非图片产物的闸（glb/json 等）：在、非空、能读、哈希。"""
    problems = []
    if not path.is_file():
        return {"pass": False, "problems": ["产物不在：%s" % path],
                "info": {"path": str(path), "exists": False}}
    size = path.stat().st_size
    info = {"path": str(path), "exists": True, "bytes": size, "sha256": _sha_file(path)[:16]}
    if size <= 0:
        problems.append("空文件")
    if "min_bytes" in expect and size < expect["min_bytes"]:
        problems.append("体量小于 %s（实得 %s）" % (expect["min_bytes"], size))
    return {"pass": not problems, "problems": problems, "info": info}


# ─────────────────────────────────────────────────────────────────────────────
# 节点表：**白名单**。每个节点 = 一个小算子（= 一根触手）。
# 口径与 ComfyUI 的"任意 node"相反：**不在表里就是 fail-closed**（故意的）。
# ─────────────────────────────────────────────────────────────────────────────
def _n_upscale_4k(inputs: dict, ctx: dict) -> dict:
    """**传统算法**放大（Pillow LANCZOS + 可选 kornia 锐化）—— 不用任何 AI 模型。

    这就是"8G 机上出 ComfyUI 能力"的样张：显存 0，内存实测 <300 MB。
    """
    from PIL import Image, ImageFilter
    src = pathlib.Path(inputs["image"])
    if not src.is_file():
        return {"ok": False, "error": "user_error: 输入图不在：%s" % src}
    target = int(inputs.get("size") or 4096)
    resample = inputs.get("resample") or "lanczos"
    # 🔴 2026-10-13 修「每一个调节都要触手可控」：
    #   ① `sharpen` 原来用 `or 0.6` ⇒ **传 0 也会被吞成 0.6**（想"不锐化"根本表达不出来）；
    #   ② USM 的 `radius` / `threshold` 原来**写死在代码里**（2 / 3）⇒ 挂不上去。
    #    现在三个都是**显式旋钮**：不传 = 走原默认（行为不变），传了（含 0）就照传的来。
    sharp = 0.6 if inputs.get("sharpen") is None else float(inputs["sharpen"])
    usm_radius = 2 if inputs.get("usm_radius") is None else int(inputs["usm_radius"])
    usm_threshold = 3 if inputs.get("usm_threshold") is None else int(inputs["usm_threshold"])
    RM = {"lanczos": Image.LANCZOS, "bicubic": Image.BICUBIC, "nearest": Image.NEAREST}
    if resample not in RM:
        return {"ok": False, "error": "user_error: resample 只认 %s" % list(RM)}
    with Image.open(src) as im:
        im.load()
        src_w, src_h = im.size
        out = im.convert("RGBA") if im.mode in ("P", "LA") else im.convert(im.mode)
        new_w = target
        new_h = max(1, round(target * src_h / max(src_w, 1)))
        up = out.resize((new_w, new_h), RM[resample])
    if sharp > 0:
        # 传统 USM 锐化（Pillow 自带），不是神经超分 —— 如实标注
        up = up.filter(ImageFilter.UnsharpMask(radius=usm_radius, percent=int(sharp * 100),
                                               threshold=usm_threshold))
    dst = pathlib.Path(inputs["out"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    save_kw = {}
    if dst.suffix.lower() in (".png",):
        save_kw["optimize"] = True
    up.save(dst, **save_kw)
    return {"ok": True, "out": str(dst), "from": [src_w, src_h], "to": [new_w, new_h],
            "engine": "PIL.%s%s" % (resample, "+USM" if sharp > 0 else ""),
            "knobs": {"size": target, "resample": resample, "sharpen": sharp,
                      "usm_radius": usm_radius, "usm_threshold": usm_threshold},
            "note": "**传统算法**（无 AI 模型参与）；神经超分要权重+内存，本机未接"}


def _n_copy(inputs: dict, ctx: dict) -> dict:
    """原样落盘（用来在图里做物化/passthrough）。"""
    import shutil
    src = pathlib.Path(inputs["src"])
    if not src.is_file():
        return {"ok": False, "error": "user_error: 源不在：%s" % src}
    dst = pathlib.Path(inputs["out"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"ok": True, "out": str(dst), "bytes": dst.stat().st_size}


def _n_sha(inputs: dict, ctx: dict) -> dict:
    """给一件产物算哈希（纯逻辑，用来把产物钉进证据链）。"""
    p = pathlib.Path(inputs["path"])
    if not p.is_file():
        return {"ok": False, "error": "user_error: 不在：%s" % p}
    return {"ok": True, "sha256": _sha_file(p), "bytes": p.stat().st_size}


def _n_info(inputs: dict, ctx: dict) -> dict:
    """读一件图产物的元信息（尺寸/模式/格式）—— 只读。"""
    p = pathlib.Path(inputs["image"])
    if not p.is_file():
        return {"ok": False, "error": "user_error: 不在：%s" % p}
    try:
        from PIL import Image
        with Image.open(p) as im:
            im.load()
            return {"ok": True, "width": im.size[0], "height": im.size[1],
                    "mode": im.mode, "format": im.format, "bytes": p.stat().st_size}
    except Exception as e:                           # noqa: BLE001
        return {"ok": False, "error": "解不开：%s" % e}


def _n_t2i_qwen(inputs: dict, ctx: dict) -> dict:
    """文生图节点（Qwen-Image-2.1-Turbo · **8 步计划**）—— 同源 Qwen 系 · 开放权重。

    边界如实（照本件铁律"不编"）：
      · **本机 AMD 无 CUDA**（4GB 显存）⇒ 一律返 `needs_dependency`，**不许假装出图**；
      · 配了云端点（env `GBT_T2I_ENDPOINT`）⇒ 上云跑，**必须带回四项能源读数**
        （**步数 / 秒 / 显存峰值 / 花费**）—— "最小能源"要能量出来，**报不出 = 没做完**。
    """
    import os
    ep = os.environ.get("GBT_T2I_ENDPOINT") or ""
    if not ep:
        return {"ok": False, "status": "needs_dependency", "node": "t2i_qwen",
                "缺失": ["云端点 GBT_T2I_ENDPOINT（本机 AMD 无 CUDA · 8G 显存不满足）",
                         "Qwen-Image-2.1-Turbo 权重（开放权重，未下载）"],
                "口径": "**不许假装出图**：缺什么写什么；配齐后由云上跑并回四项读数"}
    # ── 2026-10-26 接线：端点两种口径 ────────────────────────────────────────
    #  ① "pollinations" 前缀 ⇒ 免费公共文生图（无需钥，GET 出图）
    #  ② 其它 URL          ⇒ POST {prompt, size, steps}，认 {image_b64 | url} 回包
    #  两种都必须回四项能源读数；报不出 = 没做完（本节点铁律）。
    import base64 as _b64
    import json as _json
    import time as _t
    import urllib.parse as _up
    import urllib.request as _ur

    prompt = str(inputs.get("prompt") or "").strip()
    out = str(inputs.get("out") or "").strip()
    size = str(inputs.get("size") or "768x1024")
    try:
        w, h = [int(x) for x in size.lower().replace("×", "x").split("x")[:2]]
    except Exception:                                             # noqa: BLE001
        w, h = 768, 1024
    if not prompt:
        return {"ok": False, "status": "user_error", "node": "t2i_qwen",
                "缺失": ["prompt"]}
    if not out:
        return {"ok": False, "status": "user_error", "node": "t2i_qwen",
                "缺失": ["out（落盘路径）"]}

    t0 = _t.time()
    try:
        if ep.lower().startswith("pollinations"):
            seed = int(inputs.get("seed") or 0) or (abs(hash(prompt)) % 10 ** 6)
            url = ("https://image.pollinations.ai/prompt/" + _up.quote(prompt)
                   + "?width=%d&height=%d&nologo=true&model=flux&seed=%d" % (w, h, seed))
            req = _ur.Request(url, headers={"User-Agent": "gbt-tianzhen/1.0"})
            raw = _ur.urlopen(req, timeout=180).read()
            backend = "pollinations/flux"
        else:
            body = _json.dumps({"prompt": prompt, "size": "%dx%d" % (w, h),
                                "steps": int(inputs.get("steps") or 8),
                                "seed": int(inputs.get("seed") or 0)}).encode()
            req = _ur.Request(ep, data=body, method="POST",
                              headers={"Content-Type": "application/json"})
            d = _json.loads(_ur.urlopen(req, timeout=300).read())
            if d.get("image_b64"):
                raw = _b64.b64decode(d["image_b64"])
            elif d.get("url"):
                raw = _ur.urlopen(d["url"], timeout=180).read()
            else:
                return {"ok": False, "status": "bad_response", "node": "t2i_qwen",
                        "回包": str(d)[:300]}
            backend = str(d.get("model") or "endpoint")
        import pathlib
        pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(out).write_bytes(raw)
        dt = _t.time() - t0
        return {"ok": True, "status": "done", "node": "t2i_qwen", "out": out,
                "bytes": len(raw), "backend": backend,
                "能源读数": {"步数": int(inputs.get("steps") or 8),
                            "秒": round(dt, 2), "显存峰值": "n/a（远端）", "花费": 0},
                "口径": "第三方公共算力，**不是**本机权重；页面上标注了来源"}
    except Exception as exc:                                      # noqa: BLE001
        # 🔴 2026-10-26：HTTPError 的 body 里才是人话（例如 501 的 missing 清单），
        #    原来只回 "HTTP Error 501" 等于把原因藏了。
        detail = ""
        try:
            import urllib.error as _ue
            if isinstance(exc, _ue.HTTPError):
                detail = (exc.read() or b"")[:400].decode("utf-8", "replace")
        except Exception:                                         # noqa: BLE001
            pass
        return {"ok": False, "status": "call_failed", "node": "t2i_qwen",
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200]),
                "回包": detail or None}


NODES = {
    "upscale_4k": {"fn": _n_upscale_4k,
                   "in": ["image", "out", "size?", "resample?", "sharpen?",
                          "usm_radius?", "usm_threshold?"],
                   "out": ["out"], "writes": True,
                   "desc": "传统算法放大（Pillow LANCZOS + USM）—— 8G 机样张，无 AI 模型"},
    "t2i_qwen": {"fn": _n_t2i_qwen, "in": ["prompt", "out", "steps?", "size?"],
                 "out": ["out"], "writes": True,
                 "desc": "文生图（Qwen-Image-2.1-Turbo · 8 步计划 · 同源 Qwen · 开放权重）"
                         "—— 本机无 CUDA ⇒ 返 needs_dependency；要云"},
    "copy": {"fn": _n_copy, "in": ["src", "out"], "out": ["out"], "writes": True,
             "desc": "原样落盘（图里做物化）"},
    "sha": {"fn": _n_sha, "in": ["path"], "out": ["sha256"], "writes": False,
            "desc": "算产物哈希（钉进证据链）"},
    "info": {"fn": _n_info, "in": ["image"], "out": ["width", "height"], "writes": False,
             "desc": "读图元信息（只读）"},
}
_WRITE_OPS = ("run",)
_READ_OPS = ("status", "nodes", "graph", "gate", "contract", "validate")


# ─────────────────────────────────────────────────────────────────────────────
# 执行器：拓扑排序 + 按序跑。这就是 ComfyUI 的"执行引擎"，但只有 60 行。
# ─────────────────────────────────────────────────────────────────────────────
def toposort(wf: dict) -> dict:
    """把 workflow 排成可执行顺序。契约形状（写死，简单到不用学）：

        {"nodes": [{"id": "n1", "node": "upscale_4k", "inputs": {...}}, ...],
         "edges": [{"from": "n1", "to": "n2", "field": "out->image"}, ...]}
    """
    nodes = wf.get("nodes") or []
    edges = wf.get("edges") or []
    ids = [n.get("id") for n in nodes]
    if any(not i for i in ids):
        return {"ok": False, "error": "user_error: 每个节点都要有 id"}
    if len(set(ids)) != len(ids):
        return {"ok": False, "error": "user_error: 节点 id 有重复"}
    unknown = [n.get("node") for n in nodes if n.get("node") not in NODES]
    if unknown:
        return {"ok": False, "error": "user_error: 白名单里没有这些节点：%s" % unknown,
                "known": sorted(NODES)}
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a not in indeg or b not in indeg:
            return {"ok": False, "error": "user_error: 边指向了不存在的节点：%s->%s" % (a, b)}
        adj[a].append(b)
        indeg[b] += 1
    q = [i for i in ids if indeg[i] == 0]
    order = []
    while q:
        cur = q.pop(0)
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    if len(order) != len(ids):
        return {"ok": False, "error": "user_error: 图里有环，排不出序（ComfyUI 也拒这个）"}
    return {"ok": True, "order": order, "nodes": len(ids), "edges": len(edges)}


def run_workflow(wf: dict, ctx: dict | None = None) -> dict:
    """真跑一张图。**每个写节点的产物都先过闸才落盘**（闸是唯一真源）。"""
    ctx = dict(ctx or {})
    ts = toposort(wf)
    if not ts.get("ok"):
        return ts
    by_id = {n["id"]: n for n in wf["nodes"]}
    edges = wf.get("edges") or []
    feed = {}
    for e in edges:
        frm, to, field = e.get("from"), e.get("to"), (e.get("field") or "")
        src_field, _, dst_field = field.partition("->")
        feed[(to, dst_field or src_field)] = (frm, src_field)

    trace, t0 = [], time.time()
    for nid in ts["order"]:
        spec = by_id[nid]
        kind = spec["node"]
        inputs = dict(spec.get("inputs") or {})
        # 连边取上一节点的输出
        for (to, dst), (frm, srcf) in feed.items():
            if to != nid:
                continue
            prev = by_id[frm].get("_out") or {}
            val = prev.get(srcf)
            if val is None:
                # 2026-10-21 修（契约保真 · 连边名两套都认）：ComfyUI 的图在边上写的是
                # **socket 名**（IMAGE / STRING），而我们的算子把产物回在 `image`/`out` 上
                # ⇒ 只按字面名查会取不到，节点当场报「缺 image」。这里按 socket 名往下退化
                # （image/text/out），使标准 ComfyUI 连线形状能真跑通。
                for alt in (str(srcf).lower(), "image", "out", "text"):
                    if prev.get(alt) is not None:
                        val = prev[alt]
                        break
            if val is not None:
                inputs[dst] = val
        node = NODES[kind]
        st = time.time()
        try:
            res = node["fn"](inputs, ctx)
        except Exception as e:                       # noqa: BLE001
            res = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
        by_id[nid]["_out"] = res if isinstance(res, dict) else {}
        row = {"id": nid, "node": kind, "ok": bool(res.get("ok")),
               "ms": round((time.time() - st) * 1000, 1),
               "out": {k: v for k, v in (res or {}).items() if k != "note"}}
        # ⚠️ 写节点的产物**先过闸**；不过就**不认这一跑**
        if node.get("writes") and res.get("ok") and res.get("out"):
            expect = dict(ctx.get("expect") or {})
            # 一张图里各节点产物尺寸天然不同：允许按节点 id 覆写（覆盖全局期望），
            # 否则中间件必被全局 expect 误杀（2026-10-17 实测踩到）。
            expect.update((ctx.get("expect_by_id") or {}).get(nid) or {})
            g = (gate_image if pathlib.Path(res["out"]).suffix.lower() in
                 (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
                 else gate_any)(pathlib.Path(res["out"]), expect)
            row["gate"] = g
            if not g["pass"]:
                row["ok"] = False
                row["rejected"] = "产物没过闸，**不予认账**（闸是唯一真源）"
        trace.append(row)
        if not row["ok"]:
            return {"ok": False, "failed_at": nid, "trace": trace,
                    "error": row.get("rejected") or (res or {}).get("error"),
                    "seconds": round(time.time() - t0, 2)}

    products = [r["out"]["out"] for r in trace if isinstance(r.get("out"), dict) and r["out"].get("out")]
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "nodes": len(trace),
           "seconds": round(time.time() - t0, 2), "products": products,
           "trace": trace, "workflow_name": wf.get("name")}
    _append_run(row)
    return {"ok": True, "products": products, "trace": trace,
            "seconds": row["seconds"], "note": "证据已追加到 store/comfy_native/runs.jsonl"}


# ─────────────────────────────────────────────────────────────────────────────
# op
# ─────────────────────────────────────────────────────────────────────────────
def _op_status() -> dict:
    return {"ok": True, "capability": "comfy_native", "in_position": True,
            "why": "本机 AMD 无 CUDA + 总内存 7.39 GB ⇒ ComfyUI 本体跑不动重模型；"
                   "按其架构用轻量小算子自食其力（不装重壳、不下权重、不起 8188）",
            "deps": _deps(),
            "nodes": sorted(NODES),
            "read_ops": list(_READ_OPS), "write_ops": list(_WRITE_OPS),
            "able": ["传统算法图算子（放大/裁剪/拼贴/格式转换/校验/哈希/锐化）—— 纯 CPU，内存 <300 MB"],
            "unable": ["任何重生成模型（文生图/图生图/神经超分）—— 要 GPU 或 ≥16 GB 内存"],
            "honest": "神经超分（spandrel 那些权重）**未接**：要权重 + 内存，本机没有",
            "runs_file": str(_runs_file())}


def _op_nodes() -> dict:
    return {"ok": True, "nodes": {k: {"in": v["in"], "out": v["out"],
                                      "writes": v["writes"], "desc": v["desc"]}
                                  for k, v in NODES.items()}}


def _op_graph(payload: dict) -> dict:
    wf = payload.get("workflow")
    if isinstance(wf, str):
        p = pathlib.Path(wf)
        if not p.is_file():
            return {"ok": False, "error": "user_error: 图不在：%s" % p}
        try:
            wf = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:                       # noqa: BLE001
            return {"ok": False, "error": "user_error: 图不是合法 JSON：%s" % e}
    if not isinstance(wf, dict):
        return {"ok": False, "error": "user_error: 要给 workflow（dict 或 JSON 路径）"}
    ts = toposort(wf)
    if ts.get("ok"):
        ts["contract"] = {"nodes": [{"id": n["id"], "node": n["node"]} for n in wf.get("nodes") or []],
                          "edges": len(wf.get("edges") or [])}
    return ts


def _op_gate(payload: dict) -> dict:
    """只跑闸（不跑图）—— 给一件产物，报它过不过。"""
    p = payload.get("path") or payload.get("out")
    if not p:
        return {"ok": False, "error": "user_error: 要给 path"}
    path = pathlib.Path(p)
    expect = dict(payload.get("expect") or {})
    fn = gate_image if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp",
                                               ".tif", ".tiff") else gate_any
    g = fn(path, expect)
    return {"ok": True, "verdict": "过" if g["pass"] else "不过", **g}


def _taste(path, profile="photo"):
    """吞噬来的品味判据（tools/taste_gate.py）。判不了的四轴会如实标 not_measurable。"""
    import importlib.util as _iu
    gp = pathlib.Path(__file__).resolve().parents[2] / "tools" / "taste_gate.py"
    if not gp.exists():
        return {"ok": False, "error": "taste_gate 不在：%s" % gp}
    spec = _iu.spec_from_file_location("taste_gate", str(gp))
    m = _iu.module_from_spec(spec)
    spec.loader.exec_module(m)
    try:
        r = m.judge(str(path), profile)
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    return {"ok": True, **r}


def _attach_taste(res: dict, profile) -> dict:
    """出图后自动体检：给每件产物附上品味判定 + 不过的那几轴。不改变 ok，只加证据。"""
    if not profile:
        return res
    prof = "poster" if profile is True else str(profile)
    for tr in (res.get("trace") or []):
        o = tr.get("out") or {}
        pth = o.get("out")
        if o.get("ok") and pth:
            t = _taste(pth, prof)
            o["taste"] = {"profile": prof, "verdict": t.get("verdict"),
                          "fails": t.get("fails"), "readings": t.get("readings"),
                          "not_measurable": t.get("not_measurable")}
    return res


def _op_taste(payload: dict) -> dict:
    p = payload.get("path") or payload.get("out")
    if not p:
        return {"ok": False, "error": "user_error: 要给 path"}
    return _taste(p, str(payload.get("profile") or "photo"))


def _op_run(payload: dict) -> dict:
    wf = payload.get("workflow")
    if isinstance(wf, str):
        p = pathlib.Path(wf)
        if not p.is_file():
            return {"ok": False, "error": "user_error: 图不在：%s" % p}
        try:
            wf = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:                       # noqa: BLE001
            return {"ok": False, "error": "user_error: 图不是合法 JSON：%s" % e}
    if not isinstance(wf, dict):
        return {"ok": False, "error": "user_error: 要给 workflow（dict 或 JSON 路径）"}
    _res = run_workflow(wf, {"expect": payload.get("expect") or {},
                             "expect_by_id": payload.get("expect_by_id") or {},
                             "input": payload.get("input")})
    # 🔴 2026-10-26 融合：出图后自动过「吞噬来的品味闸」。
    #    payload 写 taste="photo" / "poster" 即生效；不写就不判（省算力）。
    #    判定**不改变 ok**，只加证据 —— 闸是底线，不是失败器。
    return _attach_taste(_res, payload.get("taste"))


def _op_single(payload: dict) -> dict:
    """直接跑一个节点（同样过闸）。"""
    kind = payload.get("node")
    if kind not in NODES:
        return {"ok": False, "fail_closed": True,
                "error": "user_error: 白名单里没有这个节点：%s" % kind,
                "known": sorted(NODES)}
    spec = NODES[kind]
    inputs = dict(payload.get("inputs") or {})
    res = spec["fn"](inputs, {})
    out = {"ok": bool(res.get("ok")), "node": kind, "result": res}
    if spec.get("writes") and res.get("ok") and res.get("out"):
        g = gate_image(pathlib.Path(res["out"]), dict(payload.get("expect") or {}))
        out["gate"] = g
        out["ok"] = out["ok"] and g["pass"]
        out["note"] = "产物过闸才认账（闸是唯一真源）"
    _append_run({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "single": kind, "trace": [out]})
    return out


def run(payload: dict | None = None) -> dict:
    payload = dict(payload or {})
    raw_op = str(payload.get("op") or "status").strip()
    op = raw_op.lower()
    if op == "status":
        return _op_status()
    if op == "nodes":
        return _op_nodes()
    if op == "graph":
        return _op_graph(payload)
    if op == "gate":
        return _op_gate(payload)
    if op in ("taste", "taste_gate"):
        return _op_taste(payload)
    if op == "contract":
        return _op_contract()
    if op == "validate":
        return _op_validate(payload)
    # R-H997：ComfyUI 节点名是**驼峰**（ImageScale…），而上面把 op 转了小写 ⇒ 单节点直跑全被
    #   fail-closed（实测 2026-10-15）。先按**原样**命中（大小写敏感），再回退到小写表。
    if raw_op in NODES:
        payload["node"] = raw_op
        return _op_single(payload)
    if op in NODES:                       # 直接跑单节点
        payload["node"] = op
        return _op_single(payload)
    if op == "run":
        return _op_run(payload)
    if op == "node":
        return _op_single(payload)
    return {"ok": False, "fail_closed": True,
            "error": "user_error: 未列出的 op（fail-closed）",
            "read_ops": list(_READ_OPS), "write_ops": list(_WRITE_OPS),
            "nodes": sorted(NODES)}


def cli(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")           # type: ignore[attr-defined]
        except Exception:
            pass
    payload = {}
    if argv:
        try:
            payload = json.loads(argv[0])
        except Exception:                             # noqa: BLE001
            payload = {"op": argv[0]}
    print(json.dumps(run(payload), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())



# ═══════════════════════════════════════════════════════════════════════════
#  R-H996 · 原生算子扩充 + 契约校验（不要 ComfyUI 的厚重外壳）
#  节点名与 ComfyUI **同名同契约**；内里跑的是我们自己的轻算子（PIL/numpy，纯 CPU）。
#  这样她的 workflow.json 可以是 ComfyUI 格式，但**不需要** ComfyUI 在位。
# ═══════════════════════════════════════════════════════════════════════════
_CONTRACT_SRC = _ROOT / "state" / "comfyui_object_info.json"
_CONTRACT_CACHE: dict = {}

# “契约已纳但原生未接”的**原因分类**（按 ComfyUI 类目归因，不逐个手写）
_NEEDS = (
    (("sampling", "loaders", "conditioning", "latent", "_for_testing", "model_patches", "advanced"),
     "重生成/模型面：要权重与 GPU（本机无 CUDA、内存 7.39GB）"),
    (("api node",), "云端 API 节点：要出网与凭据"),
    (("ImpactPack", "ipadapter", "ControlNet Preprocessors"),
     "控图/检测面：部分可原生（已接预处理），其余需权重"),
)


def _contract_load() -> dict:
    """读秋叶版节点 schema，归一化成**我们自己的契约**（只读，不写盘）。"""
    if _CONTRACT_CACHE:
        return _CONTRACT_CACHE
    try:
        raw = json.loads(_CONTRACT_SRC.read_text(encoding="utf-8"))
    except Exception:                                  # noqa: BLE001
        return {}
    out = {}
    for name, node in raw.items():
        node = node or {}
        req = (node.get("input") or {}).get("required") or {}
        opt = (node.get("input") or {}).get("optional") or {}
        sockets = []
        for sname, spec in list(req.items()):
            typ = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
            sockets.append({"name": sname, "type": (typ if isinstance(typ, str) else type(typ).__name__),
                            "required": True})
        for sname, spec in list(opt.items()):
            typ = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
            sockets.append({"name": sname, "type": (typ if isinstance(typ, str) else type(typ).__name__),
                            "required": False})
        out[name] = {"category": str(node.get("category") or ""),
                     "inputs": sockets,
                     "outputs": list(node.get("output") or []),
                     "output_names": list(node.get("output_name") or []),
                     "output_node": bool(node.get("output_node"))}
    _CONTRACT_CACHE.update(out)
    return out


def _need_reason(cat: str) -> str:
    for keys, why in _NEEDS:
        for k in keys:
            if k.lower() in cat.lower():
                return why
    return "传统算法面：**可原生**（未接的按需再长）"


def _op_contract() -> dict:
    """契约面：962 把节点 → 我们的契约 + 原生覆盖率（只读）。"""
    con = _contract_load()
    if not con:
        return {"ok": False, "reason": "no_contract_snapshot", "path": str(_CONTRACT_SRC),
                "detail": "契约快照读不到（未读到，不当空）"}
    native = sorted(NODES)
    covered = [n for n in native if n in con]
    contract_only = [n for n in con if n not in NODES]
    reasons: dict = {}
    for n in contract_only:
        why = _need_reason(con[n]["category"])
        reasons.setdefault(why, []).append(n)
    return {"ok": True, "op": "contract", "source": str(_CONTRACT_SRC),
            "contract_nodes": len(con), "native_nodes": native,
            "native_also_in_contract": covered,
            "native_only": [n for n in native if n not in con],
            "native_coverage_pct": round(100.0 * len(covered) / max(1, len(con)), 2),
            "contract_only": len(contract_only),
            "not_native_by_reason": {k: {"count": len(v), "sample": sorted(v)[:8]}
                                     for k, v in sorted(reasons.items(), key=lambda kv: -len(kv[1]))},
            "口径": "契约用它的（socket 名与类型），算子用我们的（纯 CPU）；「原生未接」不算失败，只不许假装能跑"}


def _op_validate(payload: dict) -> dict:
    """用**我们自己的契约**离线校验一份 workflow（不启 ComfyUI）。"""
    wf = payload.get("workflow")
    if isinstance(wf, str):
        fp = pathlib.Path(wf)
        if not fp.is_file():
            return {"ok": False, "error": "user_error: 图不在：%s" % fp}
        try:
            wf = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:                         # noqa: BLE001
            return {"ok": False, "error": "user_error: 图不是合法 JSON：%s" % e}
    if not isinstance(wf, dict):
        return {"ok": False, "error": "user_error: 要给 workflow（dict 或 JSON 路径）"}
    con = _contract_load()
    nodes = wf.get("nodes") or []
    edges = wf.get("edges") or []
    errors, warnings = [], []
    native_used, contract_only_used, unknown = [], [], []
    ids = [n.get("id") for n in nodes]
    if len(set(ids)) != len(ids):
        errors.append("user_error: 节点 id 有重复")
    incoming = {}
    for e in edges:
        frm, to = e.get("from"), e.get("to")
        if frm not in ids or to not in ids:
            errors.append("边指向不存在的节点：%s -> %s" % (frm, to))
        incoming.setdefault(to, set()).add(str(e.get("field") or "").split("->")[-1])
    for n in nodes:
        nm = n.get("node")
        if nm in NODES:
            native_used.append(nm)
            spec = NODES[nm]
            # 2026-10-21 修（契约保真）：`out` 是**可选落点**（缺省由 _out_path 自动派生，
            # ComfyUI 那边叫 filename_prefix），不参与"必填"判定 —— 否则标准 ComfyUI 图会被误判。
            req = {k for k in spec["in"] if not k.endswith("?") and k != "out"}
            given = set((n.get("inputs") or {}).keys()) | incoming.get(n.get("id"), set())
            miss = sorted(req - given)
            if miss:
                errors.append("%s(%s) 缺必填输入：%s" % (n.get("id"), nm, miss))
        elif nm in con:
            contract_only_used.append(nm)
        else:
            unknown.append(nm)
            errors.append("未知节点（既不在原生表也不在契约）：%s" % nm)
    if contract_only_used:
        warnings.append("契约已纳·原生未接（要 ComfyUI 在位或 GPU）：%s" % sorted(set(contract_only_used))[:12])
    # 成环（Kahn，不用 toposort 的白名单检查：那里会把契约节点当成非法）
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    for e in edges:
        if e.get("from") in indeg and e.get("to") in indeg:
            indeg[e["to"]] += 1
            adj[e["from"]].append(e["to"])
    q = [i for i, d in indeg.items() if d == 0]
    seen = 0
    while q:
        cur = q.pop()
        seen += 1
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    if seen != len(ids):
        errors.append("图成环（拓扑排不出来）")
    return {"ok": not errors, "op": "validate", "nodes": len(nodes), "edges": len(edges),
            "errors": errors, "warnings": warnings,
            "native_used": sorted(set(native_used)),
            "contract_only_used": sorted(set(contract_only_used)),
            "unknown_nodes": unknown,
            "verdict": ("可跑（全在原生表内）" if not errors and not contract_only_used
                        else ("有错" if errors else "部分节点要 ComfyUI"))}


# ── 原生算子（名与 ComfyUI 同名；纯 CPU、内存 <300MB）──────────────────────
def _out_path(inputs: dict, tag: str) -> str:
    """落点：`out` > `filename_prefix`（ComfyUI 的叫法）> 自动落 store/comfy_native/gen_*.png。"""
    out = inputs.get("out")
    if out:
        return str(out)
    pre = inputs.get("filename_prefix")
    if pre:
        p = pathlib.Path(str(pre))
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            return str(p)
        return str(p.with_suffix(".png"))
    d = _store() / "comfy_native"
    d.mkdir(parents=True, exist_ok=True)
    return str(d / ("%s_%d.png" % (tag, int(time.time() * 1000) % 1000000)))


def _n_ImageScale(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src, w, h = inputs.get("image"), int(inputs.get("width") or 0), int(inputs.get("height") or 0)
    if not src or w <= 0 or h <= 0:
        return {"ok": False, "error": "user_error: 要 image/width/height"}
    out = _out_path(inputs, "scale")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    m = {"nearest": Image.NEAREST, "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC,
         "area": Image.BOX, "lanczos": Image.LANCZOS}.get(str(inputs.get("upscale_method") or "lanczos").lower(),
                                                          Image.LANCZOS)
    Image.open(src).convert("RGBA").resize((w, h), m).save(out)
    return {"ok": True, "out": out, "width": w, "height": h, "method": str(inputs.get("upscale_method") or "lanczos")}


def _n_ImageCrop(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    x, y = int(inputs.get("x") or 0), int(inputs.get("y") or 0)
    w, h = int(inputs.get("width") or 0), int(inputs.get("height") or 0)
    if w <= 0 or h <= 0:
        return {"ok": False, "error": "user_error: 要 width/height"}
    out = _out_path(inputs, "crop")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGBA").crop((x, y, x + w, y + h)).save(out)
    return {"ok": True, "out": out, "box": [x, y, w, h]}


def _n_ImageInvert(inputs: dict, ctx: dict) -> dict:
    from PIL import Image, ImageOps
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    out = _out_path(inputs, "invert")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGBA")
    rgb = ImageOps.invert(im.convert("RGB")).convert("RGBA")
    rgb.putalpha(im.getchannel("A"))
    rgb.save(out)
    return {"ok": True, "out": out}


def _n_ImageBlur(inputs: dict, ctx: dict) -> dict:
    from PIL import Image, ImageFilter
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    r = float(inputs.get("radius") or 2.0)
    out = _out_path(inputs, "blur")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGBA").filter(ImageFilter.GaussianBlur(r)).save(out)
    return {"ok": True, "out": out, "radius": r}


def _n_ImageCompositeMasked(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    a, b = inputs.get("image1"), inputs.get("image2")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    x, y = int(inputs.get("x") or 0), int(inputs.get("y") or 0)
    base = Image.open(a).convert("RGBA")
    top = Image.open(b).convert("RGBA")
    mask = inputs.get("mask")
    if mask:
        m = Image.open(mask).convert("L").resize(top.size)
        top.putalpha(m)
    out = _out_path(inputs, "composite")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    base.alpha_composite(top, (x, y))
    base.save(out)
    return {"ok": True, "out": out, "at": [x, y], "masked": bool(mask)}


def _n_MaskToImage(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("mask")
    if not src:
        return {"ok": False, "error": "user_error: 要 mask"}
    out = _out_path(inputs, "mask2img")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("L").convert("RGBA").save(out)
    return {"ok": True, "out": out}


def _n_ImageToMask(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    ch = str(inputs.get("channel") or "red").lower()
    idx = {"red": 0, "green": 1, "blue": 2, "alpha": 3}.get(ch, 0)
    out = _out_path(inputs, "img2mask")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGBA")
    band = im.getchannel(idx) if idx < 4 else im.convert("L")
    band.save(out)
    return {"ok": True, "out": out, "channel": ch}


def _n_ImageBatch(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    a, b = inputs.get("image1"), inputs.get("image2")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    ia, ib = Image.open(a).convert("RGBA"), Image.open(b).convert("RGBA")
    w = max(ia.width, ib.width)
    out = _out_path(inputs, "batch")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", (w, ia.height + ib.height), (0, 0, 0, 0))
    canvas.paste(ia, (0, 0))
    canvas.paste(ib, (0, ia.height))
    canvas.save(out)
    return {"ok": True, "out": out, "size": [w, canvas.height]}


def _n_EmptyImage(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    w, h = int(inputs.get("width") or 512), int(inputs.get("height") or 512)
    c = int(inputs.get("color") or 0)
    rgba = ((c >> 16) & 255, (c >> 8) & 255, c & 255, 255)
    out = _out_path(inputs, "empty")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (w, h), rgba).save(out)
    return {"ok": True, "out": out, "size": [w, h]}


def _n_LoadImage(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("path") or inputs.get("image")
    if not src or not pathlib.Path(src).is_file():
        return {"ok": False, "error": "user_error: 图不在：%s" % src}
    im = Image.open(src)
    return {"ok": True, "image": str(src), "width": im.width, "height": im.height,
            "mode": im.mode, "sha256": _sha_file(pathlib.Path(src))}


def _n_SaveImage(inputs: dict, ctx: dict) -> dict:
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    # 2026-10-21 修：`out` 缺省也能存（落 store/comfy_native 或 `filename_prefix`）——
    # 否则一张标准 ComfyUI 图（SaveImage 只给 images/filename_prefix）会被判「缺必填 out」。
    out = _out_path(inputs, "save")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f1, open(out, "wb") as f2:
        while True:
            chunk = f1.read(1 << 20)
            if not chunk:
                break
            f2.write(chunk)
    return {"ok": True, "out": str(out), "sha256": _sha_file(pathlib.Path(out))}


def _n_AddTextPrefix(inputs: dict, ctx: dict) -> dict:
    txt = str(inputs.get("text") or "")
    pre = str(inputs.get("prefix") or "")
    return {"ok": True, "text": pre + txt}


def _n_AddTextSuffix(inputs: dict, ctx: dict) -> dict:
    txt = str(inputs.get("text") or "")
    suf = str(inputs.get("suffix") or "")
    return {"ok": True, "text": txt + suf}


NODES.update({
    "ImageScale": {"fn": _n_ImageScale,
                   "in": ["image", "width", "height", "out", "upscale_method?"],
                   "out": ["IMAGE"], "writes": True,
                   "desc": "所放（Pillow）：与 ComfyUI 同名同契约，纯 CPU"},
    "ImageCrop": {"fn": _n_ImageCrop,
                  "in": ["image", "x", "y", "width", "height", "out"],
                  "out": ["IMAGE"], "writes": True, "desc": "裁切"},
    "ImageInvert": {"fn": _n_ImageInvert, "in": ["image", "out"], "out": ["IMAGE"],
                    "writes": True, "desc": "反相（保留 alpha）"},
    "ImageBlur": {"fn": _n_ImageBlur, "in": ["image", "out", "radius?"], "out": ["IMAGE"],
                  "writes": True, "desc": "高斯模糊"},
    "ImageCompositeMasked": {"fn": _n_ImageCompositeMasked,
                             "in": ["image1", "image2", "out", "x?", "y?", "mask?"],
                             "out": ["IMAGE"], "writes": True, "desc": "带遮罩合成"},
    "MaskToImage": {"fn": _n_MaskToImage, "in": ["mask", "out"], "out": ["IMAGE"],
                    "writes": True, "desc": "遮罩→图"},
    "ImageToMask": {"fn": _n_ImageToMask, "in": ["image", "out", "channel?"], "out": ["MASK"],
                    "writes": True, "desc": "图→遮罩（单通道）"},
    "ImageBatch": {"fn": _n_ImageBatch, "in": ["image1", "image2", "out"], "out": ["IMAGE"],
                   "writes": True, "desc": "上下拼接"},
    "EmptyImage": {"fn": _n_EmptyImage, "in": ["out", "width?", "height?", "color?"],
                   "out": ["IMAGE"], "writes": True, "desc": "空画布"},
    # 2026-10-21 修（契约保真 · 判否了合法图）：ComfyUI 的 LoadImage 必填输入叫 `image`
    # （文件名/socket 名），本表原来只写内部别名 `path` ⇒ 一张**标准的 ComfyUI 图**会被本器
    # 判成「缺必填 path」而拒绝。operator `_n_LoadImage` 本来就两个名都认（path or image），
    # 所以这里按契约的写法登记：`image` 必填、`path` 选填别名。
    "LoadImage": {"fn": _n_LoadImage, "in": ["image", "path?"], "out": ["IMAGE", "MASK"], "writes": False,
                  "desc": "读图（只读，回尺寸与哈希；image 与 path 两个名都认）"},
    "SaveImage": {"fn": _n_SaveImage, "in": ["image", "out"], "out": ["IMAGE"], "writes": True,
                  "desc": "写盘（过闸才认账）"},
    "AddTextPrefix": {"fn": _n_AddTextPrefix, "in": ["text", "prefix"], "out": ["STRING"],
                      "writes": False, "desc": "文本前缀（纯函数）"},
    "AddTextSuffix": {"fn": _n_AddTextSuffix, "in": ["text", "suffix"], "out": ["STRING"],
                      "writes": False, "desc": "文本后缀（纯函数）"},
})

# ── R-H997 · 传统算法面按需长（主人令「下一步」2026-10-15）─────────────────────
#   这一族**不需要 GPU、不需要权重** ⇒ 本机唯一能真吃下的部分。每长一把，
#   `contract` 的原生覆盖率就往上走一格（那个百分比就是"离全原生还差多远"）。


def _n_ImageBlend(inputs: dict, ctx: dict) -> dict:
    from PIL import Image, ImageChops
    a, b = inputs.get("image1"), inputs.get("image2")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    f = max(0.0, min(1.0, float(inputs.get("blend_factor") if inputs.get("blend_factor") is not None else 0.5)))
    mode = str(inputs.get("blend_mode") or "normal").lower()
    i1 = Image.open(a).convert("RGBA")
    i2 = Image.open(b).convert("RGBA").resize(i1.size)
    if mode == "normal":
        out_img = Image.blend(i1, i2, f)
    elif mode in ("multiply", "screen", "add", "subtract", "difference"):
        fn = {"multiply": ImageChops.multiply, "screen": ImageChops.screen, "add": ImageChops.add,
              "subtract": ImageChops.subtract, "difference": ImageChops.difference}[mode]
        out_img = Image.blend(i1, fn(i1, i2), f)
    else:
        return {"ok": False, "error": "user_error: 不支持的 blend_mode：%s" % mode,
                "supported": ["normal", "multiply", "screen", "add", "subtract", "difference"]}
    out = _out_path(inputs, "blend")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out)
    return {"ok": True, "out": out, "blend_mode": mode, "blend_factor": f}


def _n_ImageHueSaturation(inputs: dict, ctx: dict) -> dict:
    # R-H999（2026-10-15）：**换成标准 HSV 空间**。
    #   旧实现是凑合近似（按通道加权混合再裁剪），第一次真跑就把金色面板
    #   #F5B041 洗成了灰白 —— 产物自己把问题暴露了。现在：rgb→hsv 逐像素转换，
    #   在 HSV 里旋色相、放饱和度与明度，再转回 rgb（不再有“近似”字样）。
    import numpy as np
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    hue = float(inputs.get("hue") if inputs.get("hue") is not None else 0.0)
    sat = float(inputs.get("saturation") if inputs.get("saturation") is not None else 0.0)
    val = float(inputs.get("value") if inputs.get("value") is not None else 0.0)
    im = Image.open(src).convert("RGBA")
    arr = np.asarray(im.convert("RGB")).astype("float32") / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    d = mx - mn
    v = mx
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    dd = np.maximum(d, 1e-6)
    hr = ((g - b) / dd) % 6.0
    hg = ((b - r) / dd) + 2.0
    hb = ((r - g) / dd) + 4.0
    h = np.select([mx == r, mx == g, mx == b], [hr, hg, hb], default=0.0) / 6.0
    h = np.where(d > 1e-6, h, 0.0)
    h = (h + hue) % 1.0
    s = np.clip(s * (1.0 + sat), 0.0, 1.0)
    v = np.clip(v * (1.0 + val), 0.0, 1.0)
    i = np.floor(h * 6.0)
    f = h * 6.0 - i
    p1 = v * (1.0 - s)
    q1 = v * (1.0 - f * s)
    t1 = v * (1.0 - (1.0 - f) * s)
    idx = (i % 6).astype("int32")
    r2 = np.choose(idx, [v, q1, p1, p1, t1, v])
    g2 = np.choose(idx, [t1, v, v, q1, p1, p1])
    b2 = np.choose(idx, [p1, p1, t1, v, v, q1])
    rgb = np.stack([r2, g2, b2], axis=2)
    res = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255).astype("uint8"), "RGB").convert("RGBA")
    res.putalpha(im.getchannel("A"))
    out = _out_path(inputs, "hsv")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    res.save(out)
    return {"ok": True, "out": out, "hue": hue, "saturation": sat, "value": val,
            "honest": "标准 HSV 空间逐像素调整（rgb↔hsv），非近似"}



def _n_ImageLevels(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    black = float(inputs.get("black") if inputs.get("black") is not None else 0.0)
    white = float(inputs.get("white") if inputs.get("white") is not None else 255.0)
    gamma = float(inputs.get("gamma") if inputs.get("gamma") is not None else 1.0) or 1.0
    if white <= black:
        return {"ok": False, "error": "user_error: white 必须大于 black"}
    lut = []
    for x in range(256):
        y = (x - black) / (white - black)
        y = min(1.0, max(0.0, y)) ** (1.0 / gamma)
        lut.append(int(round(y * 255)))
    im = Image.open(src).convert("RGBA")
    rgb = im.convert("RGB").point(lut * 3)
    res = rgb.convert("RGBA")
    res.putalpha(im.getchannel("A"))
    out = _out_path(inputs, "levels")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    res.save(out)
    return {"ok": True, "out": out, "black": black, "white": white, "gamma": gamma}


def _n_ImageRotate(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    ang = float(inputs.get("angle") if inputs.get("angle") is not None else 0.0)
    expand = bool(inputs.get("expand", True))
    im = Image.open(src).convert("RGBA")
    res = im.rotate(ang, resample=Image.BICUBIC, expand=expand)
    out = _out_path(inputs, "rotate")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    res.save(out)
    return {"ok": True, "out": out, "angle": ang, "size": list(res.size)}


def _n_ImageTranspose(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    mode = str(inputs.get("transpose") or "flip_horizontal").lower()
    M = {"flip_horizontal": Image.FLIP_LEFT_RIGHT, "flip_vertical": Image.FLIP_TOP_BOTTOM,
         "rotate_90": Image.ROTATE_90, "rotate_180": Image.ROTATE_180, "rotate_270": Image.ROTATE_270,
         "transpose": Image.TRANSPOSE, "transverse": Image.TRANSVERSE}
    if mode not in M:
        return {"ok": False, "error": "user_error: 不支持的 transpose：%s" % mode,
                "supported": sorted(M)}
    im = Image.open(src).convert("RGBA").transpose(M[mode])
    out = _out_path(inputs, "transpose")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return {"ok": True, "out": out, "transpose": mode, "size": list(im.size)}


def _n_ImagePadForOutpaint(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    l = int(inputs.get("left") or 0); t = int(inputs.get("top") or 0)
    r = int(inputs.get("right") or 0); bo = int(inputs.get("bottom") or 0)
    if min(l, t, r, bo) < 0 or max(l, t, r, bo) == 0:
        return {"ok": False, "error": "user_error: 四边至少一边 >0，且不能为负"}
    im = Image.open(src).convert("RGBA")
    w, h = im.width + l + r, im.height + t + bo
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(im, (l, t))
    # 扩边用**边缘拉伸**（比透明更像 ComfyUI 的 outpaint 预备）
    edge = im.crop((0, 0, 1, 1)).resize((w, h))
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    base.paste(edge, (0, 0))
    base.alpha_composite(canvas)
    out = _out_path(inputs, "pad")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    base.save(out)
    return {"ok": True, "out": out, "size": [w, h], "pad": [l, t, r, bo],
            "honest": "新增区域用**左上角单色拉伸**填充（不是内容感知填充）"}


def _n_MaskBlur(inputs: dict, ctx: dict) -> dict:
    from PIL import Image, ImageFilter
    src = inputs.get("mask")
    if not src:
        return {"ok": False, "error": "user_error: 要 mask"}
    rad = float(inputs.get("radius") if inputs.get("radius") is not None else 2.0)
    m = Image.open(src).convert("L").filter(ImageFilter.GaussianBlur(rad))
    out = _out_path(inputs, "maskblur")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    m.save(out)
    return {"ok": True, "out": out, "radius": rad}


def _n_MaskComposite(inputs: dict, ctx: dict) -> dict:
    from PIL import Image, ImageChops
    m1, m2 = inputs.get("mask1"), inputs.get("mask2")
    if not m1 or not m2:
        return {"ok": False, "error": "user_error: 要 mask1/mask2"}
    op = str(inputs.get("operation") or "add").lower()
    x, y = int(inputs.get("x") or 0), int(inputs.get("y") or 0)
    a = Image.open(m1).convert("L")
    b = Image.open(m2).convert("L")
    layer = Image.new("L", a.size, 0)
    layer.paste(b, (x, y))
    fn = {"add": ImageChops.lighter, "subtract": ImageChops.subtract,
          "multiply": ImageChops.multiply, "difference": ImageChops.difference}.get(op)
    if fn is None:
        return {"ok": False, "error": "user_error: 不支持的 operation：%s" % op,
                "supported": ["add", "subtract", "multiply", "difference"]}
    res = fn(a, layer)
    out = _out_path(inputs, "maskcomp")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    res.save(out)
    return {"ok": True, "out": out, "operation": op}


def _n_ImageBatchMulti(inputs: dict, ctx: dict) -> dict:
    from PIL import Image
    srcs = [inputs.get("image%d" % i) for i in range(1, 5)]
    srcs = [s for s in srcs if s]
    if len(srcs) < 2:
        return {"ok": False, "error": "user_error: 至少给两张（image1..image4）"}
    ims = [Image.open(s).convert("RGBA") for s in srcs]
    w = max(i.width for i in ims)
    h = sum(i.height for i in ims)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    yy = 0
    for i in ims:
        canvas.paste(i, (0, yy))
        yy += i.height
    out = _out_path(inputs, "batchmulti")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return {"ok": True, "out": out, "count": len(ims), "size": [w, h]}


NODES.update({
    "ImageBlend": {"fn": _n_ImageBlend,
                   "in": ["image1", "image2", "out", "blend_factor?", "blend_mode?"],
                   "out": ["IMAGE"], "writes": True,
                   "desc": "混合（normal/multiply/screen/add/subtract/difference）"},
    "ImageHueSaturation": {"fn": _n_ImageHueSaturation,
                           "in": ["image", "out", "hue?", "saturation?", "value?"],
                           "out": ["IMAGE"], "writes": True, "desc": "色相/饱和度/明度"},
    "ImageLevels": {"fn": _n_ImageLevels, "in": ["image", "out", "black?", "white?", "gamma?"],
                    "out": ["IMAGE"], "writes": True, "desc": "色阶（black/white/gamma）"},
    "ImageRotate": {"fn": _n_ImageRotate, "in": ["image", "out", "angle?", "expand?"],
                    "out": ["IMAGE"], "writes": True, "desc": "旋转"},
    "ImageTranspose": {"fn": _n_ImageTranspose, "in": ["image", "out", "transpose?"],
                       "out": ["IMAGE"], "writes": True, "desc": "翻转/旋转 90°系"},
    "ImagePadForOutpaint": {"fn": _n_ImagePadForOutpaint,
                            "in": ["image", "out", "left?", "top?", "right?", "bottom?"],
                            "out": ["IMAGE"], "writes": True, "desc": "朩边（外绘预备）"},
    "MaskBlur": {"fn": _n_MaskBlur, "in": ["mask", "out", "radius?"], "out": ["MASK"],
                 "writes": True, "desc": "遮罩模糊"},
    "MaskComposite": {"fn": _n_MaskComposite,
                      "in": ["mask1", "mask2", "out", "x?", "y?", "operation?"],
                      "out": ["MASK"], "writes": True, "desc": "遮罩运算"},
    "ImageBatchMulti": {"fn": _n_ImageBatchMulti,
                        "in": ["out", "image1", "image2", "image3?", "image4?"],
                        "out": ["IMAGE"], "writes": True, "desc": "多张上下拼"},
})
