# gbt-capability: art_chain
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""art_chain —— **作品链**（一条命令：挑组件 → 取件 → 真渲 → 调优，每步带读数）。

## 来历

前两刀把两个口做出来了（`ui_kit`：哪一件；`design_atlas`：该学哪一节），然后**手工**串了五步出了一张作品。
手工链不算器官 —— 本件把它封成**一位**：`run(q=人话)` 一次跑完，返回**每步读数 + 最终 verdict**。

## 链（每一步都调**既有位/既有件**，不重写任何一环）

    ① ui_kit.find(q)        → 挑头一件（带外链数）
    ② ui_kit.take(...)      → 拷进 outputs/art-chain/（**不许改上游**）
    ③ render_page.py        → **真 Chromium 渲**（该件自己禁网 + 逐条记拦获）
    ④ vision_print.polish   → 清晰度 + 补光/味道（**默认 look=原样**）

## 🔴 默认值是上一刀学到的教训

上一刀我手工出片时选了 `look=filmic`，把白底组件页压暗了 **−60** 亮度（有意的，但那是**我在替用户加戏**）。
所以本件默认 **`look="原样"`**（只调旋钮、不套味道）—— 要味道请**显式点名**。

## 铁律

1. **每一步走既有门/既有件**：`ui_kit`/`vision_print` 一律 `run_task`；渲染一律调 `render_page.py`（**不重写渲染器**）。
2. **失败停在原地并说清**（哪一步、错什么），**不许把半成品念成作品**。
3. **上游一个字节不动**。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OUT = _ROOT / "outputs" / "art-chain"
_OPS = ("status", "where", "run")
_RENDER = _ROOT / "tools" / "codex-scripts" / "render_page.py"


def _cap(kind: str, payload: dict) -> dict:
    """调**既有能力位** —— 走唯一门 `run_task`（不直连模块、不绕门）。"""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import gbt_allinone as _g
    r = _g.run_task(kind, payload)
    res = None
    if isinstance(r.get("gbt_result"), dict):
        res = (r["gbt_result"] or {}).get("result")
    if res is None and isinstance(r.get("result"), dict):
        res = r.get("result")
    return {"status": r.get("status"), "denied": bool(r.get("denied")),
            "missing_scopes": r.get("missing_scopes"), "result": res or {}}


def _render(page: Path, png: Path, w: int, h: int, timeout: int = 600) -> dict:
    """③ 真渲：调既有渲染取证件（禁网 + 逐条记拦获）。**不重写渲染器**。"""
    if not _RENDER.is_file():
        return {"ok": False, "status": "needs_dependency", "missing": [str(_RENDER)]}
    argv = [sys.executable, str(_RENDER), str(page), "--out", str(png),
            "--w", str(int(w)), "--h", str(int(h))]
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    txt = (p.stdout or b"").decode("utf-8", "replace")
    ok = p.returncode == 0 and png.is_file() and png.stat().st_size > 0
    return {"ok": ok, "rc": p.returncode, "png": str(png.relative_to(_ROOT)),
            "bytes": png.stat().st_size if png.is_file() else 0,
            "zero_outbound": ("零出网请求" in txt),
            "err": "" if ok else (p.stderr or b"").decode("utf-8", "replace")[-300:]}


def run_chain(q: str = "", look=None, size: int = 1800, sharpen: float = 0.8,
              grain: int = 3, grade_fmt: str = ".png", name: str = "",
              width: int = 900, height: int = 600, **_kw) -> dict:
    """一条命令：挑件 → 取件 → 真渲 → 调优。**每一步失败就停在原地并说清**。"""
    if not str(q or "").strip():
        return {"ok": False, "op": "run", "fail_closed": True, "status": "needs_params",
                "error": "要给 q（人话，如「霓虹按钮」）"}
    t0 = time.time()
    steps = []
    r1 = _cap("ui_kit", {"op": "find", "q": q, "limit": 3})
    items = (r1.get("result") or {}).get("items") or []
    if not items:
        return {"ok": False, "op": "run", "stage": "find", "steps": steps,
                "missing_scopes": r1.get("missing_scopes"),
                "error": "没挑到件（命中 %s）" % (r1.get("result") or {}).get("hits")}
    pick = items[0]
    steps.append({"step": "find", "gate": r1["status"], "ok": True, "q": q,
                  "picked": pick["path"], "cat": pick["cat"], "urls": pick.get("urls"),
                  "score": pick.get("score")})
    nm = name or Path(pick["path"]).stem
    _OUT.mkdir(parents=True, exist_ok=True)
    r2 = _cap("ui_kit", {"op": "take", "path": pick["path"],
                         "out": "outputs/art-chain/%s.html" % nm})
    res2 = r2.get("result") or {}
    if not res2.get("ok"):
        # 🔴 失败必须**如实带出"被什么挡的"**（首版只带了 error，内层是门拒时 error=None ⇒ 看着像空失败）
        return {"ok": False, "op": "run", "stage": "take", "steps": steps,
                "error": res2.get("error") or res2.get("message") or "内层 ui_kit.take 没成",
                "inner_status": res2.get("status"),
                "inner_denied": res2.get("denied") or r2.get("denied"),
                "inner_missing_scopes": res2.get("missing_scopes") or r2.get("missing_scopes"),
                "inner": res2}
    steps.append({"step": "take", "gate": r2["status"], "ok": True, "html": res2.get("out"),
                  "urls": res2.get("urls"), "effects": res2.get("effects")})
    page = _ROOT / str(res2["out"])
    png = _OUT / ("%s.png" % nm)
    r3 = _render(page, png, width, height)
    steps.append({"step": "render", **r3})
    if not r3.get("ok"):
        return {"ok": False, "op": "run", "stage": "render", "steps": steps,
                "error": r3.get("error") or ("渲染没成（%s）" % r3.get("status"))}
    final = _OUT / ("%s-final%s" % (nm, grade_fmt))
    r4 = _cap("vision_print", {"op": "polish", "image": str(png.relative_to(_ROOT)),
                               "out": str(final.relative_to(_ROOT)), "look": look or "原样",
                               "size": size, "sharpen": sharpen, "grain": grain,
                               "grade_fmt": grade_fmt, "name": nm})
    res4 = r4.get("result") or {}
    steps.append({"step": "polish", "gate": r4["status"], "ok": bool(res4.get("ok")),
                  "verdict": res4.get("verdict"), "pct": res4.get("清晰度变化_pct"),
                  "out": res4.get("out")})
    if not res4.get("ok"):
        return {"ok": False, "op": "run", "stage": "polish", "steps": steps,
                "error": res4.get("error"), "missing_scopes": r4.get("missing_scopes")}
    return {"ok": True, "op": "run", "q": q, "picked": pick["path"], "look": look or "原样",
            "product": res4.get("out"), "verdict": res4.get("verdict"),
            "清晰度变化_pct": res4.get("清晰度变化_pct"), "steps": steps,
            "seconds": round(time.time() - t0, 2), "ledger": res4.get("ledger"),
            "_口径": "ok=**四步链真跑通**；好不好看是人的判断，本件只给读数。"
                     "默认 `look=原样`（只调旋钮不套味道）—— 要味道请显式点名"}


def status(**_kw) -> dict:
    return {"ok": True, "op": "status", "kind": "art_chain", "ops": list(_OPS),
            "chain": ["ui_kit.find", "ui_kit.take", "render_page.py（真渲·禁网）",
                      "vision_print.polish"],
            "default_look": "原样", "out": str(_OUT.relative_to(_ROOT)),
            "render_page": str(_RENDER.relative_to(_ROOT)),
            "render_page_present": _RENDER.is_file(),
            "_口径": "每一步都调**既有位/既有件**（不重写任何一环）；失败停在原地并说清"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "art_chain",
            "entry": "run_task('art_chain', {'op':'run','q':'霓虹按钮'})", "ops": list(_OPS),
            "what": "把「挑组件→取件→真渲→调优」四步手工链封成一位",
            "hard_rules": ["每步走既有门/既有件（不重写渲染器、不绕门）",
                           "失败停在原地并说清哪一步错什么",
                           "上游 `_upstream/galaxy/**` 一个字节不动",
                           "默认 look=原样（不替用户加戏）"],
            "旋钮": {"q": "人话（挑什么件）", "look": "味道（默认原样）", "size": "放大到多宽",
                     "sharpen": "锐化强度", "grain": "颗粒", "grade_fmt": ".png 无损 / .jpg"},
            "上游": ["ui_kit（uiverse-io/galaxy · MIT）", "vision_print.polish", "render_page.py"]}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    if op == "run":
        return run_chain(**params)
    for nm, fn in (("status", status), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="作品链：挑组件→取件→真渲→调优")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
