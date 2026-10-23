# -*- coding: utf-8 -*-
"""影子检查器 · 常驻防线（**只读**）。

判据来源：O49（家根影子大扫）+《影子大扫方案稿》第八条。
规则：**工作区根**存在与 `gbt_allinone/` 同名的 `*.py`，或与 `gbt_allinone/<name>/` 同名的子目录 -> 报红。
`__pycache__` **单列**，不计入红（字节码缓存不是影子模块）。

用法：
    py -3.10 gbt_allinone/tools/shadow_check.py [--root <dir>] [--pkg <dir>] [--json]
退出码：0 = 绿（无影子）· 1 = 红（有影子）· 2 = 参数错。

供门禁复用：`from gbt_allinone.tools.shadow_check import shadow_report`
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "gbt_allinone"

# 扫描可达性时要跳过的子树（**列出而不静默跳过** —— 跳了什么必须写在回执里）
_SKIP_PARTS = {".pylibs", "__pycache__", "store", ".git"}

_IMPORT_RE = re.compile(
    r"^\s*(?:import\s+(?P<plain>[\w\s,\.]+)|from\s+(?P<from>[\w\.]+)\s+import\b)"
)


def unqualified_imports(pkg: Path, names) -> dict:
    """量「影子模块**有没有人真的非限定引用**」。

    为什么要有这一层：`verdict=RED_SHADOW_PRESENT` 只说明"影子存在"，
    说明不了"影子有没有造成影响"。二者差别极大：
      · 影子存在 + 无人引用 = **潜在隐患**，代价 0，不该当作常红挂着；
      · 影子存在 + 有人引用 = **活的解析错位**，`import tools` 会拿到根上那个。
    分不开就会二选一犯错：要么长期挂红当噪声，要么直接放过真问题。

    判据只认**非限定**顶层导入：`import tools` / `from tools import x` 算命中；
    `from gbt_allinone import tools`、`from . import tools` 都是限定的，**不算**。

    🔴 2026-10-04 修（真故障）：本函数原来**按行文本匹配**，会把**文档字符串里的示例**
    当成真导入 —— 实测 `tentacle/omni_controller.py:21` 的用法示例（docstring 里的
    `from brain.omni_controller import get_omni`）被报成「影子被非限定引用（活错位）」，
    把 exposure 从 latent 顶成 live、连累 `test_cross_scan_clean` 常红。
    ⇒ 改用 **AST 判**：只认真正的 `ast.Import` / `ast.ImportFrom`（且 `level == 0` = 非限定）。
    解析不了的文件**如实记 parse_failed**，不静默跳过。
    """
    import ast

    names = set(names or ())
    hits: list[dict] = []
    parse_failed: list[dict] = []
    scanned = 0
    if not names:
        return {"hits": [], "scanned_files": 0, "names": [], "parse_failed": [],
                "skipped_subtrees": sorted(_SKIP_PARTS), "state": "not_applicable"}
    try:
        files = [p for p in pkg.rglob("*.py")
                 if not (_SKIP_PARTS & set(p.parts))]
    except OSError as exc:
        return {"hits": [], "scanned_files": 0, "names": sorted(names), "parse_failed": [],
                "skipped_subtrees": sorted(_SKIP_PARTS),
                "state": "unreadable", "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        rel = str(f.relative_to(pkg)).replace("\\", "/")
        try:
            tree = ast.parse(txt)
        except SyntaxError as exc:
            parse_failed.append({"file": rel, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:                       # 相对导入 = 限定，不算
                    continue
                top = (node.module or "").split(".")[0]
                if top in names:
                    hits.append({"name": top, "file": rel, "line": node.lineno,
                                 "text": ("from %s import %s" % (node.module or "", ",".join(
                                     a.name for a in node.names)))[:160]})
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in names:
                        hits.append({"name": top, "file": rel, "line": node.lineno,
                                     "text": ("import " + alias.name)[:160]})
    return {"hits": hits, "scanned_files": scanned, "names": sorted(names),
            "parse_failed": parse_failed,
            "skipped_subtrees": sorted(_SKIP_PARTS),
            "state": "live" if hits else "latent"}


def _cannot_scan(rule: str, why: str, missing) -> dict:
    """R-H295 · ⑥ G1/G2：检查器**扫不了**时的结构化上报。

    《触手覆盖矩阵.md》§三：镜组 6 个模块只有 4 个能报"做不了"，本文件是缺的那一类。
    病根不是"少一个字"，而是 `pkg.glob/iterdir()` 在目标不存在时**直接抛异常** ——
    调用方拿不到"是 root 不在、还是 pkg 不在、还是读不了"。
    检查器扫不了却说不出为什么，比报错更坏：上层会把异常当成程序 bug，
    而实际上只是路径不对。
    """
    return {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": rule,
        "action": "shadow_report",
        "missing": list(missing or ()),
        "why": str(why)[:240],
        "error": str(why)[:240],  # 向后兼容：老调用方读 error
        "shadow_files": [], "shadow_dirs": [], "cache_dirs": [],
        "red": None, "verdict": "INCONCLUSIVE",
        "shadow_reachable": None, "exposure": "unknown",
        "note": "扫不了 = 没验成（**不是 GREEN**）：不许把'没扫'折算成'没影子'。",
    }


def shadow_report(root: Path | str = ROOT, pkg: Path | str = PKG) -> dict:
    """只读扫描：返回根级影子清单。不做任何写盘。

    R-H295：目标不存在/读不了时返回**结构化拒绝**（verdict=INCONCLUSIVE），
    不再让 `iterdir()` 的异常穿出去。**INCONCLUSIVE 不是 GREEN** ——
    "没扫成"和"扫了没影子"是两回事，不许混为一谈。
    """
    root = Path(root).resolve()
    pkg = Path(pkg).resolve()
    if not root.is_dir():
        return _cannot_scan("shadow_scan_root_missing",
                            "仓库根不存在或不是目录：%s" % root, ["root"])
    if not pkg.is_dir():
        return _cannot_scan("shadow_scan_pkg_missing",
                            "包目录不存在或不是目录：%s" % pkg, ["pkg"])
    try:
        pkg_py = {p.name for p in pkg.glob("*.py")}
        pkg_dirs = {p.name for p in pkg.iterdir() if p.is_dir()}
        entries = sorted(x for x in root.iterdir() if x.is_dir())
    except OSError as exc:
        return _cannot_scan("shadow_scan_unreadable",
                            "读目录失败：%s: %s" % (type(exc).__name__, str(exc)[:160]),
                            ["read_permission"])

    shadow_files = sorted(p.name for p in root.glob("*.py") if p.name in pkg_py)
    shadow_dirs, cache_dirs = [], []
    for p in entries:
        if p.name not in pkg_dirs:
            continue
        (cache_dirs if p.name == "__pycache__" else shadow_dirs).append(p.name)
    red = len(shadow_files) + len(shadow_dirs)

    # ── 可达性：影子存在 ≠ 影子有害（2026-09-21 加 · 起因见下） ──
    # 交叉扫（dim W）报了 `deploy` / `tools` 两个家根影子子目录 ⇒ RED_SHADOW_PRESENT。
    # 但实测全包**没有任何非限定 `import tools|deploy`** ⇒ 代价为 0 的潜在隐患，
    # 不是活的解析错位。原实现分不开这两者，只能长期挂红。
    # 区分开之后：latent 可登记为已知豁免；一旦有人写出非限定导入，live 立刻炸出来。
    _names = set(shadow_files) | set(shadow_dirs)
    reach = unqualified_imports(pkg, _names)
    exposure = "none" if red == 0 else reach.get("state", "unknown")

    return {
        "root": str(root),
        "pkg": str(pkg),
        "shadow_files": shadow_files,
        "shadow_dirs": shadow_dirs,
        "cache_dirs": cache_dirs,
        "pkg_py_total": len(pkg_py),
        "red": red,
        "ok": red == 0,
        "verdict": "GREEN" if red == 0 else "RED_SHADOW_PRESENT",
        "shadow_reachable": reach,
        "exposure": exposure,
        "exposure_note": (
            "none：无影子" if red == 0 else
            "latent：影子存在但全包无非限定引用 ⇒ 潜在隐患、当前代价 0"
            if exposure == "latent" else
            "live：影子存在**且**有非限定引用 ⇒ 活的解析错位，`import 同名` 会拿到根上那个"
            if exposure == "live" else
            "unknown：可达性没量到（不许折算成 latent）"
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="家根影子检查器（只读）")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--pkg", default=str(PKG))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = shadow_report(a.root, a.pkg)
    except Exception as e:
        print("shadow_check: 参数/路径错误：%s" % e)
        return 2
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("root  :", rep["root"])
        print("verdict:", rep["verdict"], "(red=%d)" % rep["red"])
        print("exposure:", rep.get("exposure"), "—", rep.get("exposure_note", ""))
        if rep["shadow_files"]:
            print("  同名 .py :", ", ".join(rep["shadow_files"]))
        if rep["shadow_dirs"]:
            print("  同名子目录:", ", ".join(rep["shadow_dirs"]))
        if rep["cache_dirs"]:
            print("  单列(不入红):", ", ".join(rep["cache_dirs"]))
        _r = rep.get("shadow_reachable") or {}
        if _r:
            print("  可达性扫描: %d 个 .py（跳过 %s）" % (
                _r.get("scanned_files", 0), ",".join(_r.get("skipped_subtrees") or [])))
            for h in _r.get("hits") or []:
                print("    ! %s:%s  %s" % (h["file"], h["line"], h["text"]))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
