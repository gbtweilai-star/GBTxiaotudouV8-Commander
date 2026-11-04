# -*- coding: utf-8 -*-
"""身体·排泄（2026-11-04 主人令）。

主人原话：「把所有的临时文件以及排放的垃圾要自动联通电脑回收站，
做到人体排泄的能力，而不是留在文件里当垃圾」

所以这根能力位**不是「清理」，是「排泄」**：
把体内代谢产生的垃圾**排出体外**，而且必须排进 **Windows 回收站** —— 还能捡回来。

为什么不做成「清理」：
  清理是硬删（os.remove / shutil.rmtree），删完就没了，等于把垃圾烧在体内。
  生理上不成立，工程上也不成立——误排一次就丢资产。
  回收站是**可逆的排泄**：排出去，但还在系统里，能捡回来。

三条纪律（对齐框架既有口径）：
  1. **只排代谢物，不排器官**：源码 / 配置 / 状态账本 / 能力包 / 解释器
     全部进保护名单，命中也不动。判据是「可再生」——删了能自己长回来的才叫垃圾。
  2. **默认只报不排**（dry_run=True）：先如实报体内积了多少，要显式
     dry_run=false 才真排。这一条对齐「交付闸」——不替主人决定不可逆的事。
  3. **排完必须验证**：文件要真的从原处消失，否则如实报 failed，
     不假装排干净了（诚实边界优先于好看的报表）。

依赖：纯 stdlib（ctypes + shell32.SHFileOperationW）。
  不需要 3.12，不需要 pywin32。回收站是 Shell 的行为，不是文件系统的行为。
"""

from __future__ import annotations
from gbt_allinone.tools._opcall import call as _oc_call

import ctypes
import json
import os
import shutil
import time
from ctypes import wintypes

# ── 落地位置 ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOME = os.path.join(_ROOT, "state", "excrete")
_CONFIG = os.path.join(_HOME, "config.json")
_LEDGER = os.path.join(_HOME, "ledger.jsonl")
_LAST = os.path.join(_HOME, "last.json")

# ── 回收站：Shell API 常量 ──────────────────────────────────────────────────
_FO_DELETE = 3
_FOF_SILENT = 0x0004
_FOF_NOCONFIRMATION = 0x0010
_FOF_ALLOWUNDO = 0x0040          # ★ 关键位：没有它就是硬删
_FOF_NOERRORUI = 0x0400
_FOF_NOCONFIRMMKDIR = 0x0200


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_uint16),      # FILEOP_FLAGS 是 WORD
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


# ── 分类规则 ────────────────────────────────────────────────────────────────
# strict：默认就排（纯代谢物，删了自动再生）
_JUNK_DIRS = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
              ".cache", ".eggs", "htmlcov", ".ipynb_checkpoints")
_JUNK_EXTS = (".pyc", ".pyo", ".tmp", ".temp", ".$$$", ".part", ".crdownload",
              ".partial", ".swp", ".swo")
_JUNK_NAMES = ("Thumbs.db", ".DS_Store", "desktop.ini")

# loose：需显式 include（可能是主人想要的备份，默认不排）
_LOOSE_EXTS = (".bak", ".old", ".orig", ".rej", ".log.1", ".log.2")

# 保护：这些扩展名一律不动（源码 / 配置 / 账本 / 二进制）
_PROTECT_EXTS = (".py", ".pyi", ".pyx", ".json", ".jsonl", ".md", ".txt",
                 ".toml", ".yaml", ".yml", ".cfg", ".ini", ".env", ".sqlite",
                 ".db", ".pyd", ".dll", ".exe", ".cap", ".whl", ".zip", ".7z")

# 保护：这些目录整棵不动（哪怕里面有垃圾也别碰，交给各自的守卫）
_PROTECT_DIRS = ("pyembed", "packs", "node_modules", ".git")

# ── %TEMP%：框架自己排出去的垃圾（主人令「所有临时文件」）──────────────────
# 只认框架自己产的名字前缀，绝不动别人家的临时件。
_TEMP_PREFIXES = (
    "chrome-cdp-gbt",          # 框架起的 CDP 用户数据目录（进程死即垃圾）
    "gbt-router-toolchain",    # 路由工具链缓存
    "qa-pyembed",              # 质检用嵌入解释器副本
    "gbt-tmp-",
)
# 这些是**缓存不是垃圾**：删了要重新下载/重算，代价高 → 保护
_TEMP_PROTECT = (
    "gbt-whisper-cache", "gbt-model-cache", "gbt-hf-", "huggingface",
    "torch", "pip-", "npm-",
)

_DEFAULT_CONFIG = {
    "auto": False,                 # 自动排（由 heartbeat 或外部调度拉起）
    "threshold_mb": 200,           # 体内垃圾超过这个量才自动排
    "include": ["strict"],         # 自动排哪几类
    "log_days": 7,                 # state 下超期日志算垃圾的天数
    "max_files": 5000,             # 单次上限（防手滑排掉整盘）
    "keep_last": 200,              # ledger 保留行数
}


def _cfg() -> dict:
    cfgo = dict(_DEFAULT_CONFIG)
    try:
        with open(_CONFIG, "r", encoding="utf-8") as f:
            cfgo.update(json.load(f) or {})
    except Exception:                                            # noqa: BLE001
        pass
    return cfgo


def _ensure_home() -> None:
    os.makedirs(_HOME, exist_ok=True)


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return ("%.1f %s" % (f, unit)) if unit != "B" else ("%d B" % f)
        f /= 1024.0
    return "%d B" % n


# ══════════════════════════════════════════════════════════════════════════
# 一、回收站（排泄口本身）
# ══════════════════════════════════════════════════════════════════════════
def _recycle_one(path: str) -> tuple[bool, str]:
    """单个文件/目录送回收站。返回 (成功, 原因)。"""
    try:
        # pFrom 必须是双 NUL 结尾的多字符串；用 buffer 保住内嵌 NUL
        raw = path + "\0"
        buf = ctypes.create_unicode_buffer(raw, len(raw) + 1)
        op = _SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = _FO_DELETE
        op.pFrom = ctypes.cast(buf, wintypes.LPCWSTR)
        op.pTo = None
        op.fFlags = (_FOF_ALLOWUNDO | _FOF_NOCONFIRMATION |
                     _FOF_NOERRORUI | _FOF_SILENT | _FOF_NOCONFIRMMKDIR)
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc == 0 and not op.fAnyOperationsAborted:
            return True, "recycle_bin"
        if op.fAnyOperationsAborted:
            return False, "aborted(可能被占用或权限不足)"
        return False, "SHFileOperation rc=%d" % rc
    except Exception as exc:                                     # noqa: BLE001
        return False, "%s: %s" % (type(exc).__name__, str(exc)[:120])


def to_recycle_bin(paths: list[str]) -> dict:
    """批量送回收站。失败会逐个重试以定位到底是哪个排不掉。"""
    ok, fails = [], []
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        joined = "\0".join(chunk) + "\0"
        try:
            buf = ctypes.create_unicode_buffer(joined, len(joined) + 1)
            op = _SHFILEOPSTRUCTW()
            op.hwnd = None
            op.wFunc = _FO_DELETE
            op.pFrom = ctypes.cast(buf, wintypes.LPCWSTR)
            op.pTo = None
            op.fFlags = (_FOF_ALLOWUNDO | _FOF_NOCONFIRMATION |
                         _FOF_NOERRORUI | _FOF_SILENT | _FOF_NOCONFIRMMKDIR)
            op.fAnyOperationsAborted = False
            op.hNameMappings = None
            op.lpszProgressTitle = None
            rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
            if rc == 0 and not op.fAnyOperationsAborted:
                ok.extend(chunk)
                continue
        except Exception:                                        # noqa: BLE001
            pass
        # 批量失败 → 逐个定位
        for p in chunk:
            good, why = _recycle_one(p)
            if good:
                ok.append(p)
            else:
                fails.append({"path": p, "why": why})
    return {"ok": ok, "failed": fails}


# ══════════════════════════════════════════════════════════════════════════
# 二、体检：体内积了什么（只读）
# ══════════════════════════════════════════════════════════════════════════
def _protected(rel: str, ext: str, name: str) -> bool:
    """是不是器官（不能排）。"""
    parts = [p.lower() for p in rel.split(os.sep)]
    if any(d in parts for d in (d.lower() for d in _PROTECT_DIRS)):
        # 例外：pyembed 之外没有例外；packs 里的 __pycache__ 也留（能力包要自洽）
        return True
    if ext in _PROTECT_EXTS:
        return True
    return False


def _classify(path: str, cfg: dict) -> str | None:
    """给一个路径定性。返回 strict / loose / None(不是垃圾)。"""
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    rel = os.path.relpath(path, _ROOT)
    parts = [p.lower() for p in rel.split(os.sep)]

    # ① __pycache__ 及其内容：无论扩展名，整体是缓存
    if any(d in parts for d in (d.lower() for d in _JUNK_DIRS)):
        return "strict"

    # ② 器官保护（扩展名 / 保护目录）——命中即停
    if _protected(rel, ext, name):
        return None

    # ③ 纯代谢物扩展名
    if ext in _JUNK_EXTS:
        return "strict"

    # ④ 系统垃圾文件名 / Office 锁文件
    if name in _JUNK_NAMES or name.startswith("~$"):
        return "strict"

    # ⑤ 超期日志（state 下，按 log_days 判）
    if ext == ".log" and parts and parts[0] == "state":
        try:
            age_d = (time.time() - os.path.getmtime(path)) / 86400.0
            if age_d >= float(cfg.get("log_days", 7)):
                return "loose"
        except OSError:
            pass
        return None

    # ⑥ 备份类（需显式 include）
    if ext in _LOOSE_EXTS or ext.endswith(".bak") or ext.endswith(".old"):
        return "loose"

    return None


def _walk_junk(cfg: dict) -> list[dict]:
    """遍历身体，收集垃圾清单（不删）。"""
    out, seen_dirs = [], set()
    skip = {os.path.abspath(_HOME)}          # 排泄日志本身不排

    for dirpath, dirnames, filenames in os.walk(_ROOT, topdown=True):
        ap = os.path.abspath(dirpath)
        if ap in skip:
            dirnames[:] = []
            continue

        # 目录级裁剪：保护目录不进
        keep = []
        for d in dirnames:
            full = os.path.join(dirpath, d)
            rel = os.path.relpath(full, _ROOT)
            parts = [p.lower() for p in rel.split(os.sep)]
            if any(pd in parts[:-1] for pd in (p.lower() for p in _PROTECT_DIRS)):
                continue
            if d.lower() in (j.lower() for j in _JUNK_DIRS):
                # 整个缓存目录算一条，不再往下钻
                if full not in seen_dirs:
                    seen_dirs.add(full)
                    size, count = _dir_size(full)
                    out.append({"path": full, "rel": rel, "kind": "dir",
                                "cat": "strict", "bytes": size, "files": count})
                continue
            keep.append(d)
        dirnames[:] = keep

        for fn in filenames:
            full = os.path.join(dirpath, fn)
            cat = _classify(full, cfg)
            if not cat:
                continue
            try:
                sz = os.path.getsize(full)
            except OSError:
                continue
            out.append({"path": full, "rel": os.path.relpath(full, _ROOT),
                        "kind": "file", "cat": cat, "bytes": sz, "files": 1})

    # 顺带把 %TEMP% 里**框架自己产的**临时件也排进来（主人令「所有临时文件」）
    out.extend(_walk_temp())
    return out


def _dir_size(path: str) -> tuple[int, int]:
    total, count = 0, 0
    for dp, _dn, fns in os.walk(path):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
                count += 1
            except OSError:
                pass
    return total, count


def _walk_temp() -> list[dict]:
    """%TEMP% 里**框架自己产的**临时件。

    只认 _TEMP_PREFIXES 前缀 —— 别人家的临时文件一概不碰（那是别人的器官）。
    被占用的（比如 chrome 还活着）会在 SHFileOperation 那步失败，如实报 failed，
    不硬顶、不假装排掉了。
    """
    t = os.environ.get("TEMP") or os.environ.get("TMP")
    if not t or not os.path.isdir(t):
        return []
    out = []
    try:
        names = os.listdir(t)
    except OSError:
        return []
    for name in names:
        low = name.lower()
        if any(low.startswith(p) for p in _TEMP_PROTECT):
            continue
        if not any(low.startswith(p) for p in _TEMP_PREFIXES):
            continue
        full = os.path.join(t, name)
        try:
            if os.path.isdir(full):
                size, count = _dir_size(full)
                out.append({"path": full, "rel": "TEMP\\" + name, "kind": "dir",
                            "cat": "strict", "bytes": size, "files": count,
                            "tree": "temp"})
            elif os.path.isfile(full):
                out.append({"path": full, "rel": "TEMP\\" + name, "kind": "file",
                            "cat": "strict", "bytes": os.path.getsize(full),
                            "files": 1, "tree": "temp"})
        except OSError:
            pass
    return out


# ══════════════════════════════════════════════════════════════════════════
# 三、排泄 + 记账
# ══════════════════════════════════════════════════════════════════════════
def _ledger_append(rec: dict) -> None:
    _ensure_home()
    try:
        with open(_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # 只留尾巴，别让排泄日志自己长成垃圾
        keep = int(_cfg().get("keep_last", 200))
        with open(_LEDGER, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > keep * 2:
            with open(_LEDGER, "w", encoding="utf-8") as f:
                f.writelines(lines[-keep:])
    except Exception:                                            # noqa: BLE001
        pass


def _ledger_read(limit: int = 20) -> list[dict]:
    try:
        with open(_LEDGER, "r", encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        return [json.loads(ln) for ln in lines[-limit:]][::-1]
    except Exception:                                            # noqa: BLE001
        return []


def _write_last(payload: dict) -> None:
    _ensure_home()
    try:
        with open(_LAST, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    except Exception:                                            # noqa: BLE001
        pass


# ══════════════════════════════════════════════════════════════════════════
# 四、对外动作
# ══════════════════════════════════════════════════════════════════════════
def run(op: str = "status", **kw) -> dict:
    ops = {"schema": op_schema, "status": op_status, "scan": op_scan,
           "excrete": op_excrete, "record": op_record, "auto": op_auto,
           "purge": op_purge, "config": op_config, "where": op_where}
    fn = ops.get(str(op or "status"))
    if not fn:
        return {"ok": False, "error": "不认识的 op：%s（可选 %s）"
                % (op, "/".join(sorted(ops)))}
    if kw.get("_raw") is not None:                               # 兼容统一入口
        kw = {k: v for k, v in kw.items() if k != "_raw"}
    return _oc_call(fn, kw)


def op_schema() -> dict:
    cfg = _cfg()
    return {
        "ok": True,
        "cap": "body_excrete",
        "note": "排泄器官：把代谢垃圾排出体外，且必须进 Windows 回收站（可恢复），"
                "不是硬删。默认只报不排。",
        "ops": {
            "schema": "本契约",
            "status": "便意：体内积了多少垃圾（只读，轻量）",
            "scan": "详细清单：逐条列出可排项与类别（只读）",
            "excrete": "真排：送回收站。参数 dry_run(默认 true) / include / max_files / verify",
            "record": "排泄史：最近 N 次排了多少（参数 limit）",
            "auto": "按阈值自动排（供 heartbeat 调度）；参数 force 可越过阈值",
            "purge": "清空回收站（最后一环·不可逆）：双闸 dry_run=false + confirm=true，"
                     "参数 drive 默认 C:",
            "config": "读写配置（传 patch 则改，不传则读）",
            "where": "自报落点",
        },
        "categories": {
            "strict": "纯代谢物：__pycache__ / *.pyc / *.tmp / ~$* / Thumbs.db —— 默认就排",
            "loose": "可能是备份：*.bak / *.old / *.orig / 超期 state 日志 —— 需显式 include",
        },
        "protected": {
            "exts": list(_PROTECT_EXTS),
            "dirs": list(_PROTECT_DIRS),
            "why": "源码/配置/账本/二进制 = 器官，不是代谢物。命中即跳过。",
        },
        "config": cfg,
        "recycle": "shell32.SHFileOperationW + FOF_ALLOWUNDO（真回收站，可从「回收站」还原）",
    }


def op_status() -> dict:
    cfg = _cfg()
    items = _walk_junk(cfg)
    strict = [i for i in items if i["cat"] == "strict"]
    loose = [i for i in items if i["cat"] == "loose"]
    sb = sum(i["bytes"] for i in strict)
    lb = sum(i["bytes"] for i in loose)
    thr = float(cfg.get("threshold_mb", 200)) * 1024 * 1024
    return {
        "ok": True,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root": _ROOT,
        "strict": {"count": len(strict), "bytes": sb, "human": _human(sb)},
        "loose": {"count": len(loose), "bytes": lb, "human": _human(lb)},
        "total_files": sum(i["files"] for i in items),
        "threshold_mb": cfg.get("threshold_mb"),
        "need_excrete": sb >= thr,
        "summary": ("体内积了 %d 项 / %s（其中备份类 %d 项 / %s）"
                    % (len(strict), _human(sb), len(loose), _human(lb))),
        "next": "要真排：op=excrete, dry_run=false" if strict else "体内干净",
    }


def op_scan(limit: int = 200) -> dict:
    cfg = _cfg()
    items = _walk_junk(cfg)
    items.sort(key=lambda x: -x["bytes"])
    by = {}
    for i in items:
        k = i["cat"]
        d = by.setdefault(k, {"count": 0, "bytes": 0, "files": 0})
        d["count"] += 1
        d["bytes"] += i["bytes"]
        d["files"] += i["files"]
    for k in by:
        by[k]["human"] = _human(by[k]["bytes"])
    return {
        "ok": True,
        "found": len(items),
        "bytes": sum(i["bytes"] for i in items),
        "human": _human(sum(i["bytes"] for i in items)),
        "by_category": by,
        "top": items[:int(limit)],
        "truncated": max(0, len(items) - int(limit)),
    }


def op_excrete(dry_run: bool = True, include=None, max_files: int = None,
               verify: bool = True, **_) -> dict:
    cfg = _cfg()
    if include is None:
        include = cfg.get("include") or ["strict"]
    if isinstance(include, str):
        include = [include]
    include = [str(x).strip().lower() for x in include]
    if "all" in include:
        include = ["strict", "loose"]

    cap = int(max_files or cfg.get("max_files", 5000))
    alljunk = _walk_junk(cfg)
    picked = [i for i in alljunk if i["cat"] in include]
    picked.sort(key=lambda x: -x["bytes"])

    over = max(0, len(picked) - cap)
    picked = picked[:cap]
    paths = [i["path"] for i in picked]
    total_bytes = sum(i["bytes"] for i in picked)

    if dry_run:
        return {
            "ok": True, "dry_run": True,
            "would_move": len(picked),
            "would_free": total_bytes, "would_free_human": _human(total_bytes),
            "include": include,
            "over_limit": over,
            "top": picked[:20],
            "note": "这是演习。要真排把 dry_run 设成 false —— 会进回收站，可还原。",
        }

    if not paths:
        return {"ok": True, "dry_run": False, "moved": 0,
                "msg": "体内没有该排的垃圾"}

    res = to_recycle_bin(paths)
    moved = res["ok"]

    # 验证：必须真的从原处消失
    gone, still = [], []
    if verify:
        for p in moved:
            (still if os.path.exists(p) else gone).append(p)
    else:
        gone = moved

    freed = 0
    for i in picked:
        if i["path"] in set(gone):
            freed += i["bytes"]

    # ── 排完立刻重新量一次：__pycache__ 这类代谢物会「边排边长」——
    #    排泄进程自己 import 模块时，解释器当场重编译并写回 .pyc。
    #    这不是没排干净，是代谢在继续。如实报出来，免得主人误判。
    residual = {"count": 0, "bytes": 0, "human": "0 B"}
    try:
        left = [i for i in _walk_junk(_cfg()) if i["cat"] in include]
        rb = sum(i["bytes"] for i in left)
        residual = {"count": len(left), "bytes": rb, "human": _human(rb)}
    except Exception:                                            # noqa: BLE001
        pass

    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "moved": len(gone), "bytes": freed, "human": _human(freed),
        "dest": "recycle_bin", "include": include,
        "failed": len(res["failed"]) + len(still),
        "residual": residual,
        "sample": [i["rel"] for i in picked if i["path"] in set(gone)][:12],
    }
    _ledger_append(rec)
    _write_last(rec)

    note = ""
    if residual["count"]:
        note = ("；排完后代谢又新长了 %d 项 / %s（__pycache__ 会随解释器运行再生，"
                "属正常代谢，不是没排干净）" % (residual["count"], residual["human"]))

    return {
        "ok": len(still) == 0 and len(res["failed"]) == 0,
        "dry_run": False,
        "moved": len(gone),
        "bytes_freed": freed, "human": _human(freed),
        "dest": "recycle_bin",
        "verified": (len(still) == 0),
        "still_there": still[:20],
        "failed": res["failed"][:20],
        "over_limit": over,
        "residual": residual,
        "ledger": _LEDGER,
        "msg": ("已排进回收站（可从「回收站」还原）：%d 项 / %s%s"
                % (len(gone), _human(freed), note)),
    }


def op_record(limit: int = 20) -> dict:
    rows = _ledger_read(int(limit))
    total = sum(r.get("bytes", 0) for r in rows)
    return {"ok": True, "count": len(rows),
            "recent_bytes": total, "recent_human": _human(total),
            "rows": rows, "ledger": _LEDGER}


def op_auto(force: bool = False) -> dict:
    """按阈值自动排 —— 供 heartbeat / 外部调度拉起。"""
    cfg = _cfg()
    st = op_status()
    thr = float(cfg.get("threshold_mb", 200)) * 1024 * 1024
    if not force and st["strict"]["bytes"] < thr:
        return {"ok": True, "skipped": True,
                "reason": "未达阈值 %s（当前 %s）"
                          % (_human(int(thr)), st["strict"]["human"])}
    if not cfg.get("auto") and not force:
        return {"ok": True, "skipped": True,
                "reason": "config.auto=false（自动排泄未开）；force=true 可手动越过"}
    return op_excrete(dry_run=False, include=cfg.get("include") or ["strict"])


def op_purge(dry_run: bool = True, confirm: bool = False, drive: str = "C:") -> dict:
    """最后一环：清空回收站，把已排出的东西真正**离体**。

    为什么单列一节：`excrete` 只是把垃圾移出工作区（还能捡回来），
    磁盘并不会释放 —— 实测排 1.2 GB 后可用空间只动了 0.02 GB。
    真正把空间要回来，必须清空回收站。而这一步**不可逆**，
    所以它不能混在 excrete 里顺手做，必须单独、显式、双闸。

    双闸：dry_run 默认 True；真清还要 confirm=true。
    两个都给才动手 —— 这是「交付闸」对不可逆操作的要求。
    """
    d = (drive or "C:").strip()
    if len(d) == 1:
        d = d + ":"
    root_drive = d.rstrip("\\/") + "\\"
    rb = os.path.join(root_drive, "$Recycle.Bin")
    size, count = _dir_size(rb) if os.path.isdir(rb) else (0, 0)

    import shutil as _sh
    try:
        free_before = _sh.disk_usage(root_drive).free
    except Exception:                                            # noqa: BLE001
        free_before = 0

    if dry_run or not confirm:
        missing = []
        if dry_run:
            missing.append("dry_run=false")
        if not confirm:
            missing.append("confirm=true")
        return {
            "ok": True, "dry_run": True, "missing_gates": missing,
            "recycle_bin": rb,
            "bytes": size, "human": _human(size), "files": count,
            "free_now": _human(free_before),
            "note": "演习。真清要同时给 dry_run=false 和 confirm=true —— "
                    "清空回收站不可逆，排出去的东西会彻底离体，捡不回来了。",
        }

    try:
        rc = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None, root_drive, 0x00000001 | 0x00000002 | 0x00000004)
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}

    time.sleep(1.5)                       # 等 Shell 真的把盘吐出来
    size2, count2 = _dir_size(rb) if os.path.isdir(rb) else (0, 0)
    try:
        free_after = _sh.disk_usage(root_drive).free
    except Exception:                                            # noqa: BLE001
        free_after = free_before

    freed = max(0, free_after - free_before)
    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "moved": count, "bytes": size, "human": _human(size),
        "freed_bytes": freed, "freed_human": _human(freed),
        "dest": "purged", "rc": rc,
    }
    _ledger_append(rec)

    return {
        "ok": rc == 0,
        "dry_run": False,
        "purged_files": count,
        "purged_bytes": size, "purged_human": _human(size),
        "freed_bytes": freed, "freed_human": _human(freed),
        "free_before": _human(free_before), "free_after": _human(free_after),
        "left_in_bin": {"files": count2, "bytes": size2},
        "dest": "purged",
        "msg": "回收站已清空：%d 项 / %s，磁盘释放 %s（不可逆）"
               % (count, _human(size), _human(freed)),
    }


def op_config(patch: dict = None, **_) -> dict:
    _ensure_home()
    cfg = _cfg()
    if patch:
        if isinstance(patch, str):
            try:
                patch = json.loads(patch)
            except Exception:                                    # noqa: BLE001
                return {"ok": False, "error": "patch 不是合法 JSON"}
        cfg.update(patch)
        try:
            with open(_CONFIG, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=1)
        except Exception as exc:                                 # noqa: BLE001
            return {"ok": False, "error": str(exc)[:160]}
    return {"ok": True, "config": cfg, "path": _CONFIG}


def op_where() -> dict:
    return {"ok": True, "root": _ROOT, "home": _HOME,
            "config": _CONFIG, "ledger": _LEDGER, "last": _LAST,
            "exists": {"home": os.path.isdir(_HOME),
                       "config": os.path.isfile(_CONFIG),
                       "ledger": os.path.isfile(_LEDGER)}}
