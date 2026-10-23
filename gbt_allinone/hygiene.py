# -*- coding: utf-8 -*-
"""文件卫生层：按 LAYOUT.md 自检乱放 + 自动归位 + 审计留痕。

判定规则与 LAYOUT.md 铁律一一对应（家规与执行永远一致）。
"""
import ast
import json
import time
from pathlib import Path

from . import _paths

_BASE = Path(__file__).resolve().parent          # gbt_allinone/
_HOME = _BASE.parent                             # 家根

# ── 家规常量（与 LAYOUT.md 同步）──
# 家根归属单一来源（v2 根治版）：不再枚举白名单（枚举永远追不上变化）——
# 唯一裁判是 inventory._classify（framework / environment / transient / foreign）。
# 框架三件之外，凡 inventory 判为 environment（OpenClaw 工作区）或 transient（运行足迹）一律放行。
HOME_ALLOWED = {"README.md", "requirements.txt", "gbt_allinone"}


def _home_allowed(p) -> bool:
    """家根单文件归属裁决（单一来源：inventory 分类）。"""
    name = p.name if hasattr(p, "name") else str(p)
    if name in HOME_ALLOWED:
        return True
    try:
        from .inventory import _is_environment
        if _is_environment(name):
            return True
        from .inventory import _classify
        return _classify(p if hasattr(p, "name") else __import__("pathlib").Path(str(p))) == "transient"
    except Exception:
        return False
PKG_MD_ALLOWED = {"README.md", "SOUL.md", "CODING_DISCIPLINE.md", "LAYOUT.md"}
PKG_DIRS = {"adapters", "bridge", "deploy", "docs", "examples", "integration",
            "ledger", "llm", "recon", "security", "store", "tentacle", "tests",
            "wallet", "archived_logs", ".pylibs"}
DATA_SUFFIX = {".jsonl"}
TEMP_PREFIXES = ("_",)
SKIP_TREES = {".pylibs", "archived_logs", "store", "__pycache__"}   # 这些树内部不按顶层规则管
# 🔴 2026-09-22 第 36 轮修（错报治理）：缓存**必须按"被扫的根"分键**。
#     原来是单槽 `{"value": None}` —— 与根无关，谁先问就定死。
_LIVE_STEMS_CACHE = {}          # {str(根): 名字集合}
# 读不懂的 .py（{str(根): [{path, error}, ...]}）—— 与 stems 同键，**必须交出去**：
# `live_stems` 不全时，temp_leftover 那条判据就可能把活模块误判成残留（假阳性）。
_UNPARSED_PY = {}


def _live_module_stems() -> set:
    """包内**被真 import** 的模块名集合（R-H170 · 走 AST，不扫文本）。

    用途：`_*.py` 不等于"临时残留" —— `recon/last30days/_pids.py` 是 `cli.py`
    真导入的活模块（上游入口与库共用它），却被"看名字"的规则判成 temp_leftover。
    判据据此从"**看名字猜**"改成"**看有没有人真引用它**"。

    🔴 2026-09-22 第 36 轮修（缓存无键 · 实测事故链）：本函数原来用**单槽缓存**
    `_LIVE_STEMS_CACHE = {"value": None}`，与"扫的是哪个根"无关。真实事故：
    `test_framework` 有一条用例把 `hygiene._BASE` mock 到一个**空临时目录**去验归位落点，
    里面调了 `H.scan(fix=True)` ⇒ 本函数在那个空根下被调用 ⇒ `stems = set()` 被**缓存**；
    `mock.patch` 会还原 `_BASE`，**但还原不了这个缓存** ⇒ 出 mock 之后本函数**永远返回空集**
    ⇒ 排在它后面的 `test_scan_contracts` 断言 `"_pids" in stems` 当场红
    （而那条用例**单独跑是绿的** —— 典型的"全量红、单文件绿"）。
    实测读数：干净时 495 个名字、`_pids` 在场；被毒后 = `set()` / 0 个。
    ⇒ **按根分键**：扫临时根再也不会覆盖真实根的结论。
    （一般教训：**缓存必须带上"它在什么前提下算出来的"**；
      没有键的缓存 = 一个迟早会说谎的全局变量。）
    """
    key = str(_BASE)
    cached = _LIVE_STEMS_CACHE.get(key)
    if cached is not None:
        return cached
    stems = set()
    unparsed = []          # 🔴 读不懂的文件**记名**（不许静默跳过，见下面 return 处的交代）
    for p in _BASE.rglob("*.py"):
        parts = p.relative_to(_BASE).parts
        if parts[0] in SKIP_TREES:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            # 🔴 2026-09-22 第 39 轮修（错报治理）：这里原来是**裸 `continue`** ——
            #    读不懂的文件既不算活模块、也不留痕迹。后果是**假阳性**：
            #    若"引用 `_pids` 的那个文件"正好读不懂，`_pids` 就不在 stems 里
            #    ⇒ 被 temp_leftover 规则判成"临时残留"（而它其实是被真 import 的活模块）。
            #    同仓的 `cross_scan` G 维早就做对了：它报
            #    「解析失败（**该文件断链检测未执行**）」—— 点名 + 说原因 + **声明自己没做什么**。
            #    这里照同一条口径：记名，并在返回值里交代"活模块判定可能不全"。
            unparsed.append({"path": str(p.relative_to(_BASE)),
                             "error": "%s: %s" % (type(exc).__name__, str(exc)[:80])})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    stems.add(node.module.split(".")[-1])
                for a in node.names:
                    stems.add(a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    stems.add(a.name.split(".")[-1])
    _LIVE_STEMS_CACHE[key] = stems
    _UNPARSED_PY[key] = unparsed          # 与 stems 同键存放：谁读到的、谁读不懂的，一起记
    return stems


def _audit(event, meta):
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


def scan(fix: bool = False) -> dict:
    """体检家规执行情况。fix=True 时自动归位/清理并留审计。"""
    t0 = time.time()
    findings = []
    fixed = []

    def _fix(action, detail):
        fixed.append({"action": action, "detail": detail})

    # ── 铁律 1：零游离（家根只允许三样；_*.py 临时脚本=运行足迹，观察者效应，不算游离）──
    for p in _HOME.iterdir():
        if p.name in (".git",):
            continue
        if not _home_allowed(p):
            findings.append({"rule": "home_stray", "path": p.name,
                             "why": "家根归属异常（inventory 判为 foreign——既非框架、环境、也非运行足迹）"})
            if fix:
                # 归位：md -> gbt_allinone/docs/（除非与家规冲突），脚本类 -> 删（临时残留）
                if p.suffix == ".py" and p.name.startswith(TEMP_PREFIXES):
                    p.unlink()
                    _fix("del_temp_script", str(p))
                else:
                    print(f"[hygiene] 需人工确认的家根游离物: {p}（不自动移动）")

    # ── 铁律 1b：包根 md 白名单 ──
    for p in _BASE.iterdir():
        if p.is_file() and p.suffix == ".md" and p.name not in PKG_MD_ALLOWED:
            findings.append({"rule": "pkg_md_stray", "path": p.name,
                             "why": f"包根 md 只允许 {sorted(PKG_MD_ALLOWED)}"})
            if fix:
                target = _BASE / "docs" / p.name
                target.parent.mkdir(exist_ok=True)
                p.rename(target)
                _fix("mv_md_to_docs", f"{p.name} -> docs/")

    # ── 铁律 2：零临时残留（包内 _*.py / *.tmp；dunder 与 _paths.py 是家规内文件）──
    # ⚠️ 2026-09-19 加固（原生扫描自曝）：`_*.py` 不等于"临时残留"——`recon/last30days/_pids.py`
    # 是 `cli.py` 真导入的活模块，却被本规则判为 temp_leftover；旧写法在 fix=True 时直接 unlink，
    # 等于**框架自带一条删自己活模块的路径**。与钢印"禁止删除"冲突，故：
    #   .tmp  → 可自动清（真临时）
    #   .py   → 只报不删（删代码必须留人工确认；findings 照旧，不静默失效）
    KEEP = {"__init__.py", "__main__.py", "_paths.py"}
    live_mods = []
    live_stems = _live_module_stems()
    for p in _BASE.rglob("*"):
        parts = p.relative_to(_BASE).parts
        if parts[0] in SKIP_TREES:
            continue
        if p.is_file() and p.name not in KEEP and (
                p.name.startswith(TEMP_PREFIXES) and p.suffix == ".py" or p.suffix == ".tmp"):
            rel = str(p.relative_to(_BASE))
            if p.suffix == ".py":
                if p.stem in live_stems:
                    # R-H170：被真引用的 `_*.py` 是**活模块**，不是残留 ⇒ 不进 findings
                    # （不进 findings 才不会再让 file_hygiene 整体判成 messy）；
                    # 但**也不静默**：在结果里如实列出，谁想看都看得到。
                    live_mods.append(rel)
                    continue
                findings.append({"rule": "temp_leftover", "path": rel,
                                 "why": "疑似工作脚本（只报不删：删代码必须人工确认）",
                                 "auto": False})
                continue
            findings.append({"rule": "temp_leftover", "path": rel,
                             "why": "临时文件（.tmp）用完应删"})
            if fix:
                p.unlink()
                _fix("del_temp", rel)

    # ── 铁律 3：零缓存入库（__pycache__ 顺带清）──
    n_cache = 0
    for pc in _BASE.rglob("__pycache__"):
        if pc.is_dir():
            n_cache += 1
            if fix:
                import shutil
                shutil.rmtree(pc)
    if n_cache and fix:
        _fix("clear_pycache", f"{n_cache} 个")

    # ── 铁律 4：空壳目录（只含 marker）──
    for d in _BASE.iterdir():
        if d.is_dir() and d.name not in PKG_DIRS and d.name != "__pycache__":
            inner = list(d.iterdir())
            if inner and all(f.name == ".gbt_dir_marker" for f in inner):
                findings.append({"rule": "shell_dir", "path": d.name, "why": "空壳残骸（真身在 store/devoured/）"})
                if fix:
                    import shutil
                    shutil.rmtree(d)
                    _fix("del_shell", d.name)

    # ── 铁律 5：数据不越界（代码目录里的 .jsonl；store/ 与 archived_logs/ 是合法数据家）──
    for p in _BASE.rglob("*.jsonl"):
        parts = p.relative_to(_BASE).parts
        if parts[0] in ("store", "archived_logs"):
            continue
        findings.append({"rule": "data_outside_store", "path": str(p.relative_to(_BASE)),
                         "why": "数据文件一律进 store/"})
        if fix:
            _paths.STORE_DIR.mkdir(parents=True, exist_ok=True)   # R86b：新 store / 隔离 store 也要能归位（契约实证）
            target = _paths.STORE_DIR / p.name
            i = 1
            while target.exists():
                target = _paths.STORE_DIR / f"{p.stem}_{i}{p.suffix}"
                i += 1
            p.rename(target)
            _fix("mv_data_to_store", f"{p.name} -> store/")

    # ── 铁律 9：署名完整性（开发者：自由的风，禁止删除）──
    try:
        from . import signature as _sig
        for p in _sig._scan_pages():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not _sig.has_signature(text):
                findings.append({"rule": "missing_signature", "path": str(p.relative_to(_BASE)),
                                 "why": f"页面缺开发者署名（{_sig.DEVELOPER}）——禁止删除"})
                if fix:
                    p.write_text(_sig.inject(text, p), encoding="utf-8")
                    _fix("restore_signature", str(p.relative_to(_BASE)))
    except Exception:
        pass

    # ── 铁律 10：源码入库边界（纯全能 AI 框架，不接纳无关业务模块）──
    # 定位：GBT-V8 是单纯的全能 AI 框架。资金/钱包/支付类业务模块不属于框架本体，
    # 其独立归档地是 Workspace/03_收款钱包与支付/。框架内只允许能力路由的优雅降级占位，
    # 不允许实体模块混入。检测到实体存在时报告 foreign_module，不自动删（人工确认）。
    FOREIGN_MODULE_MARKERS = {
        "wallet": "资金/钱包模块（归家：Workspace/03_收款钱包与支付/）",
        "ledger": "账本/交易所式记账模块（归家：Workspace/03_收款钱包与支付/）",
        "bridge": "链上入账桥模块（归家：Workspace/03_收款钱包与支付/）",
        "payment": "支付网关模块（归家：Workspace/03_收款钱包与支付/）",
    }
    for marker, why in FOREIGN_MODULE_MARKERS.items():
        d = _BASE / marker
        if d.is_dir() and any(d.iterdir()):
            # 白名单：框架自身必需的转发壳（仅 __init__.py 且不含业务逻辑）不算混入
            inner = [f for f in d.iterdir() if f.name != "__init__.py" and f.name != "__pycache__"]
            if inner:
                findings.append({"rule": "foreign_module", "path": marker + "/",
                                 "why": f"非框架本体模块混入源码：{why}。"
                                        f"GBT-V8 是纯全能 AI 框架，业务模块应物归原主，"
                                        f"框架内只保留能力降级占位"})
                # 不自动删——迁移需人工确认（防误删）

    elapsed = round(time.time() - t0, 3) * 1000
    verdict = "clean" if not findings else ("fixed" if (fix and fixed) else "messy")
    result = {
        "ok": True,
        "verdict": verdict,
        "findings": findings,
        "fixed": fixed,
        "live_underscore_modules": live_mods,
        # 🔴 2026-09-22 第 39 轮加：**读不懂的文件必须交出来**。
        #    原来它们被裸 `continue` 静默跳过 ⇒ `live_stems` 可能不全 ⇒
        #    temp_leftover 那条判据会把"被真 import 但引用者读不懂"的活模块误判成残留。
        #    口径同 `cross_scan` G 维：点名 + 原因 + **声明这次没做什么**。
        "unparsed_py": _UNPARSED_PY.get(str(_BASE), []),
        "live_stems_complete": not _UNPARSED_PY.get(str(_BASE)),
        "live_stems_note": ("活模块判定只统计**可解析**文件里的 import；"
                            + ("本次全部可解析（判定完整）"
                               if not _UNPARSED_PY.get(str(_BASE)) else
                               "%d 个文件读不懂 ⇒ 判定**可能不全**（未检查 ≠ 没有）"
                               % len(_UNPARSED_PY.get(str(_BASE)) or []))),
        "cache_cleared": n_cache,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_ms": elapsed,
        "rules": "LAYOUT.md 铁律 + 源码入库边界（纯全能 AI 框架定位）",
    }
    _audit("file_hygiene", {"verdict": verdict, "findings": len(findings), "fixed": len(fixed)})
    return result
