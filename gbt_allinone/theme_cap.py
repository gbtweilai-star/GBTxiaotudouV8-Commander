# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""主题能力位（theme_cap）—— 把“单一色源”接成框架内的一等能力。

蒸馏自 Omarchy 的“`colors.toml` 主色 + 模板重生成全系统配置”；
本件只把现有渲染器接进来，**不搬代码、不另写一份逻辑**。

四件各司一职（现状，不是设计图）：
  ① 单一真源  state/theme/palettes/*.toml     ← [colors] + [dims]
  ② 模板真源  state/theme/templates/*.css.tpl   ← @@token@@
  ③ 渲染引擎  tools/theme-render.py             ← 本件直接加载它（不拷贝）
  ④ 落地点    4 个 CSS 尾部的 GBT-THEME 标记块

三条纪律：
  ① **没装就如实报**：渲染引擎加载不到 ⇒ ok=false + reason，不假装能用；
  ② **默认不落盘**：无论 render 还是预览，都不动原文件；只有 apply=True 才写；
  ③ **门按 op 挂**：读类零作用域（只读文件）；apply 挂 filesystem_write，未知 op fail-closed。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_ENGINE = None
_ENGINE_ERR = ""

READ_OPS = ("list", "show", "check", "discover")
WRITE_OPS = ("apply",)


def _engine():
    """加载现有渲染器（只加载不拷贝）。加载不到就记下原因。"""
    global _ENGINE, _ENGINE_ERR
    if _ENGINE is not None:
        return _ENGINE
    path = ROOT / "tools" / "theme-render.py"
    if not path.exists():
        _ENGINE_ERR = "渲染引擎不在：%s" % path
        return None
    try:
        spec = importlib.util.spec_from_file_location("gbt_theme_render_engine", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _ENGINE = mod
        return mod
    except Exception as exc:                                       # noqa: BLE001
        _ENGINE_ERR = "%s: %s" % (type(exc).__name__, str(exc)[:160])
        return None


def _palette(name: str):
    eng = _engine()
    if eng is None:
        return None, None, None
    pname, meta, values, colors, dims = eng.load_palette(name)
    return eng, meta, (pname, values, colors, dims)


def list_palettes() -> dict:
    """列色源（只读）。"""
    eng = _engine()
    if eng is None:
        return {"ok": False, "op": "list", "reason": "engine_unavailable", "detail": _ENGINE_ERR}
    rows = eng.list_palettes()
    if not rows:
        return {"ok": False, "op": "list", "reason": "no_palette",
                "detail": "未读到任何色源：%s" % eng.PALETTES_DIR}
    return {"ok": True, "op": "list", "count": len(rows), "palettes": rows}


def show(name: str = "default") -> dict:
    """看一份色源的取值空间（只读）。"""
    eng, meta, got = _palette(name)
    if eng is None:
        return {"ok": False, "op": "show", "reason": "engine_unavailable", "detail": _ENGINE_ERR}
    if not got or got[0] is None:
        return {"ok": False, "op": "show", "reason": "palette_not_found", "palette": name}
    pname, values, colors, dims = got
    return {"ok": True, "op": "show", "palette": pname, "meta": meta or {},
            "colors": colors, "dims": dims, "counts": {"colors": len(colors), "dims": len(dims)}}


def check(name: str = "default") -> dict:
    """判据（只读）：漂移 + 悬空引用。pass=False 就是不合格。"""
    eng, meta, got = _palette(name)
    if eng is None:
        return {"ok": False, "op": "check", "reason": "engine_unavailable", "detail": _ENGINE_ERR}
    if not got or got[0] is None:
        return {"ok": False, "op": "check", "reason": "palette_not_found", "palette": name}
    _pname, values, _colors, _dims = got
    scan = eng.scan(values, meta)
    drift = eng.drift(values, meta)
    passed = bool(scan["ok"] and drift["ok"])
    return {"ok": passed, "op": "check", "pass": passed, "palette": name,
            "files": scan["files"], "skipped": scan["skipped"],
            "errors": scan["errors"], "notes": scan.get("notes", []),
            "drifted": drift["drifted"]}


def render(name: str = "default", outdir: str = "") -> dict:
    """预览：算出该长什么样，**原文件一字不动**。"""
    eng, meta, got = _palette(name)
    if eng is None:
        return {"ok": False, "op": "render", "reason": "engine_unavailable", "detail": _ENGINE_ERR}
    if not got or got[0] is None:
        return {"ok": False, "op": "render", "reason": "palette_not_found", "palette": name}
    _pname, values, _colors, _dims = got
    scan = eng.scan(values, meta)
    out = {"ok": bool(scan["ok"]), "op": "render", "palette": name,
           "would_write": [x["file"] for x in scan["files"]],
           "skipped": scan["skipped"], "errors": scan["errors"], "wrote": []}
    if outdir and scan["ok"]:
        d = Path(outdir)
        if not d.is_absolute():
            d = ROOT / d
        d.mkdir(parents=True, exist_ok=True)
        for rel in eng.TARGETS:
            p = ROOT / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            if not eng.has_block(text):
                continue
            dst = d / Path(rel).name
            dst.write_text(eng.build_template(text, values, meta, eng._template_of(rel)),
                           encoding="utf-8")
            out["wrote"].append(str(dst))
    return out


def discover() -> dict:
    """现读收录（只读）：色源目录、模板目录、四个目标各自有没有标记块。"""
    eng = _engine()
    if eng is None:
        return {"ok": False, "op": "discover", "reason": "engine_unavailable", "detail": _ENGINE_ERR}
    _, meta, got = _palette("default")
    values = got[1] if got else {}
    rows = []
    for rel in eng.TARGETS:
        p = ROOT / rel
        tpl = eng.TEMPLATES_DIR / (Path(rel).name + ".tpl")
        rows.append({"file": rel, "exists": p.exists(),
                     "has_block": bool(p.exists() and eng.has_block(p.read_text(encoding="utf-8"))),
                     "has_template": tpl.exists()})
    missing = [r["file"] for r in rows if not (r["has_block"] and r["has_template"])]
    s = eng.scan(values, meta) if values else {"files": [], "skipped": [], "errors": []}
    return {"ok": not missing, "op": "discover",
            "palettes_dir": str(eng.PALETTES_DIR), "templates_dir": str(eng.TEMPLATES_DIR),
            "targets": rows, "missing": missing,
            "files": s["files"], "skipped": s["skipped"], "errors": s["errors"]}


def apply_palette(name: str = "default", backup: bool = True) -> dict:
    """真写：四个 CSS 的主题块重生成。原文件先留 `.bak`。"""
    eng, meta, got = _palette(name)
    if eng is None:
        return {"ok": False, "op": "apply", "reason": "engine_unavailable", "detail": _ENGINE_ERR}
    if not got or got[0] is None:
        return {"ok": False, "op": "apply", "reason": "palette_not_found", "palette": name}
    _pname, values, _colors, _dims = got
    res = eng.apply(values, meta, backup=backup)
    return {"ok": bool(res["ok"]), "op": "apply", "palette": name,
            "written": res["written"], "count": len(res["written"])}


def run(op: str = "check", **kw) -> dict:
    """能力位统一入口。未知 op **fail-closed**。"""
    o = (op or "check").strip().lower()
    known = list(READ_OPS) + list(WRITE_OPS)
    if o == "list":
        return list_palettes()
    if o == "show":
        return show(kw.get("palette", kw.get("name", "default")))
    if o == "check":
        return check(kw.get("palette", kw.get("name", "default")))
    if o == "render":
        return render(kw.get("palette", kw.get("name", "default")), kw.get("outdir", ""))
    if o == "discover":
        return discover()
    if o == "apply":
        return apply_palette(kw.get("palette", kw.get("name", "default")),
                             bool(kw.get("backup", True)))
    return {"ok": False, "reason": "unknown_op", "op": o, "known": known,
            "detail": "未知 op 只回错，不执行任何东西（fail-closed）"}
