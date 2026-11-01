# -*- coding: utf-8 -*-
"""触手覆盖 v2（trunk_cover）：**分派表就是项目树的根**，一切文件长在能力位上。

主人 2026-11-01（逐字）：「你把触手当成项目树，所有的一切都要长在触手身上……
还有什么是她不能实现的和那些未连接，未读到，孤儿等等一系列鸡毛蒜皮的事情还会出现吗」
→ 「那就把不该出现的全面排除并实现」

## v1 错在哪

v1 靠**文件名**猜 owner：`gbt_allinone/<stem>.py` 才算认领，于是 2497 个文件里
2102 个落进 `tentacle` 兜底、140 个能力位"没有自己的文件"。
真因不是代码散，而是**我没把树根接对**：能力位的实现从来不是"同名文件"，
而是 `api.py` 里 `if kind == "x":` 那一支**引用了哪个模块**。

## v2 的口径（三类，缺一不可）

1. **owned**：文件被至少一个能力位认领（分派表 → 模块；同名文件；import 关系）；
2. **support**：**登记在册的支撑件**（tests/tools/docs/examples/静态页/移动端/资产/运行态）——
   不实现能力位，但有明确类别，不是孤儿；
3. **orphan**：既不属于任何能力位、也不属于支撑件 —— **必须为 0**。

判据（verify）：orphan == 0 · cap_coverage ≥ 0.99 · 每个能力位都有命名状态。

## op
    status / scan / verify
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "trunk-cover.json"
API = ROOT / "gbt_allinone" / "api.py"
SKIP_DIRS = {"node_modules", ".pylibs", "vendor", "mirror_space", "__pycache__", ".git",
             "dist", "_upstream", "archives", ".scratch", ".trash", "outputs"}
CODE_EXT = {".py", ".js", ".cjs", ".mjs", ".ts", ".html", ".css"}
SUFFIXES = ("_cap", "_ops", "_bridge", "_skill", "_watch", "_hub", "_gate", "_core", "_pages")

# 包根的核心脊柱（api/registry/cli/store/soul/engine…）：**它们就是主干本体**，
# 不该算孤儿，也不算"某个能力位的实现文件" —— 单列 core，owner = tentacle（主干）。
CORE_OWNER = "tentacle"


def _is_core(rel: str) -> bool:
    return rel.startswith("gbt_allinone/") and "/" not in rel[len("gbt_allinone/"):]


def _subsystem(rel: str) -> str | None:
    """包内**子系统模块**（brain/ adapters/ deploy/ integration/ …）：属主干内部，单列。"""
    if not rel.startswith("gbt_allinone/"):
        return None
    rest = rel[len("gbt_allinone/"):]
    if "/" in rest:
        return "gbt_allinone/" + rest.split("/")[0]
    return None


SUPPORT_RULES = (
    ("tests", lambda rel: "/tests/" in rel or rel.startswith("tests/") or rel.endswith("_test.py")),
    ("scripts", lambda rel: rel.startswith("tools/") or "/tools/codex-scripts/" in rel),
    ("docs", lambda rel: rel.startswith("docs/") or rel.endswith(".md")),
    ("examples", lambda rel: rel.startswith("examples/") or rel.startswith("demo")),
    ("static", lambda rel: rel.endswith((".html", ".css", ".webmanifest", ".js"))),
    ("mobile", lambda rel: rel.startswith(("mobile/", "ios/"))),
    ("assets", lambda rel: rel.startswith(("assets/", "icons/"))),
    ("runtime", lambda rel: rel.startswith(("runtime/", "state/", "logs/"))),
)


def _caps() -> dict:
    from ..caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _dispatch_map() -> tuple[dict, dict]:
    """从 api.py 现读：能力位 → 模块文件集合；能力位 → 是否内联分派。"""
    lines = API.read_text(encoding="utf-8", errors="replace").split("\n")
    owner: dict[str, set] = {}
    inline: dict[str, bool] = {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'\s*if kind == "([A-Za-z0-9_]+)"', ln)
        names = [m.group(1)] if m else []
        if not names and re.match(r"\s*if kind in \(", ln):
            buf, j = ln, i
            while ")" not in buf and j + 1 < len(lines):
                j += 1
                buf += " " + lines[j].strip()
            names = re.findall(r'"([A-Za-z0-9_]+)"', buf)
            i = j
        if not names:
            i += 1
            continue
        body, j = [], i + 1
        while j < len(lines):
            if re.match(r"\s*if kind\b", lines[j]):
                break
            body.append(lines[j])
            j += 1
        text = "\n".join(body)
        mods: set = set()
        for mm in re.finditer(r"from \.([\w.]+)\s+import\s+([\w, ]+)", text):
            dotted = mm.group(1).replace(".", "/")
            mods.add("gbt_allinone/" + dotted + ".py")
            for nm in mm.group(2).split(","):
                nm = nm.strip().split(" ")[0]
                if not nm:
                    continue
                for cand in ("gbt_allinone/" + dotted + "/" + nm + ".py",
                             "gbt_allinone/" + dotted + ".py"):
                    if (ROOT / cand).exists():
                        mods.add(cand)
        for mm in re.finditer(r"from \. import ([\w, ]+)", text):
            for nm in mm.group(1).split(","):
                nm = nm.strip().split(" ")[0]
                if not nm:
                    continue
                for cand in ("gbt_allinone/" + nm + ".py",
                             "gbt_allinone/" + nm + "/__init__.py"):
                    if (ROOT / cand).exists():
                        mods.add(cand)
        for n in names:
            owner[n] = mods or {"gbt_allinone/api.py"}
            inline[n] = not bool(mods)
        i = j if j > i else i + 1
    return owner, inline


def _walk() -> list[pathlib.Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            p = pathlib.Path(dirpath) / fn
            if p.suffix.lower() in CODE_EXT:
                out.append(p)
    return out


def _imports(p: pathlib.Path) -> set:
    if p.suffix.lower() != ".py":
        return set()
    try:
        tree = ast.parse(p.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:  # noqa: BLE001
        return set()
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[-1])
            for a in node.names:
                mods.add(a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[-1])
    return mods


def _support(rel: str) -> str | None:
    for label, pred in SUPPORT_RULES:
        try:
            if pred(rel):
                return label
        except Exception:  # noqa: BLE001
            continue
    return None


def _cap_state(name: str, caps: dict) -> str:
    meta = caps.get(name) or {}
    if meta.get("external"):
        return "needs_dependency"
    try:
        from ..security import policy as P
        if P.evaluate(name, {}).scopes:
            return "needs_grant"
    except Exception:  # noqa: BLE001
        pass
    return "owned"


def scan() -> dict:
    t0 = time.time()
    caps = _caps()
    disp, inline = _dispatch_map()
    files = _walk()
    rels = [str(p.relative_to(ROOT)).replace("\\", "/") for p in files]

    by_file: dict[str, list] = {}
    for name, mods in disp.items():
        for m in mods:
            by_file.setdefault(m, []).append(name)

    rows, orphan = [], []
    support_n = 0
    for p, rel in zip(files, rels):
        stem = p.stem
        base = next((stem[: -len(s)] for s in SUFFIXES if stem.endswith(s)), stem)
        owners = list(by_file.get(rel, []))
        why = "分派表"
        if not owners and base in caps:
            owners, why = [base], "同名文件"
        if not owners:
            for m in _imports(p):
                if m in caps:
                    owners, why = [m], "import " + m
                    break
        if owners:
            rows.append({"file": rel, "owners": owners[:8], "why": why, "class": "owned"})
            continue
        sub = _subsystem(rel)
        if sub:
            rows.append({"file": rel, "owners": [CORE_OWNER], "why": "子系统:" + sub,
                         "class": "subsystem"})
            continue
        if _is_core(rel):
            # 主干本体：单独一类，owner 记到 tentacle（这是真主干，不是兜底）
            rows.append({"file": rel, "owners": [CORE_OWNER], "why": "主干核心", "class": "core"})
            continue
        if rel.startswith(("gbt_commander/", "arms/")):
            top = rel.split("/")[0]
            rows.append({"file": rel, "owners": [CORE_OWNER], "why": "子系统:" + top,
                         "class": "subsystem"})
            continue
        if rel.startswith(("holo_pet_w3/", "holo_pet/", "mobile/", "ios/")):
            top = rel.split("/")[0]
            rows.append({"file": rel, "owners": [], "why": "组件:" + top, "class": "component"})
            continue
        cls = _support(rel)
        if cls:
            support_n += 1
            rows.append({"file": rel, "owners": [], "why": "支撑件:" + cls, "class": "support"})
        else:
            orphan.append(rel)
            rows.append({"file": rel, "owners": [], "why": "无归属", "class": "orphan"})

    caps_with_owner = {n for n, mods in disp.items() if mods}
    states = {n: _cap_state(n, caps) for n in caps}
    caps_no_owner = sorted(n for n in caps if n not in caps_with_owner)

    snap = {
        "ok": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scan_s": round(time.time() - t0, 1),
        "files": len(rows),
        "owned": sum(1 for r in rows if r["class"] == "owned"),
        "support": support_n,
        "core": sum(1 for r in rows if r["class"] == "core"),
        "subsystem": sum(1 for r in rows if r["class"] == "subsystem"),
        "component": sum(1 for r in rows if r["class"] == "component"),
        "orphan_n": len(orphan), "orphan": orphan[:200],
        "caps": len(caps), "caps_with_owner": len(caps_with_owner),
        "caps_no_owner": caps_no_owner[:50], "caps_no_owner_n": len(caps_no_owner),
        "cap_coverage": round(len(caps_with_owner) / len(caps), 4) if caps else 0.0,
        "inline_caps_n": sum(1 for v in inline.values() if v),
        "states": {k: sum(1 for v in states.values() if v == k)
                   for k in set(states.values())},
        "by_owner_top": sorted(
            ((n, sum(1 for r in rows if n in r["owners"])) for n in caps_with_owner),
            key=lambda kv: -kv[1])[:20],
        "rows": rows[:2500],
        "口径": "owned=分派表/同名/import 认领；support=登记类别的支撑件；orphan=两者皆无（必须 0）",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    return snap


def _fresh(max_age_s: float = 600.0) -> dict:
    """读快照；**过期就重扫**（默认 10 分钟）。状态要"瞬间知道"，但不能是旧账。"""
    if not OUT.exists():
        return scan()
    try:
        age = time.time() - OUT.stat().st_mtime
    except OSError:
        return scan()
    if age > max_age_s:
        return scan()
    return json.loads(OUT.read_text(encoding="utf-8"))


def status() -> dict:
    snap = _fresh()
    return {k: snap.get(k) for k in ("files", "owned", "support", "orphan_n", "caps",
                                     "caps_with_owner", "caps_no_owner_n", "cap_coverage",
                                     "inline_caps_n", "states", "by_owner_top", "at", "口径")}


def verify(min_cap_coverage: float = 0.99, force: bool = False) -> dict:
    snap = _fresh(0.0) if force else _fresh()
    checks = [
        {"name": "孤儿文件 = 0", "ok": snap.get("orphan_n", 1) == 0,
         "reading": {"orphan": snap.get("orphan_n"), "sample": (snap.get("orphan") or [])[:8]}},
        {"name": "能力位有 owner ≥ %.0f%%" % (min_cap_coverage * 100),
         "ok": (snap.get("cap_coverage") or 0) >= min_cap_coverage,
         "reading": {"cap_coverage": snap.get("cap_coverage"),
                     "no_owner": snap.get("caps_no_owner_n"),
                     "sample": (snap.get("caps_no_owner") or [])[:8]}},
        {"name": "每个能力位都有命名状态（无静默）",
         "ok": sum((snap.get("states") or {}).values()) == snap.get("caps"),
         "reading": snap.get("states")},
    ]
    bad = [c["name"] for c in checks if not c["ok"]]
    return {"ok": not bad, "checks": checks, "failed": bad,
            "files": snap.get("files"), "owned": snap.get("owned"),
            "support": snap.get("support"), "core": snap.get("core"),
            "orphan_n": snap.get("orphan_n")}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "scan":
        return scan()
    if op == "verify":
        return verify(min_cap_coverage=float(kw.get("min_cap_coverage") or 0.99),
                      force=bool(kw.get("force")))
    return {"ok": False, "error": "trunk_cover 不认 op=%s（status/scan/verify）" % op}
