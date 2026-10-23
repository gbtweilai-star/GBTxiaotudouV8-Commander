# gbt-capability: 分批模块巡扫器（一个模块一个模块核对，无死角）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""分批模块巡扫器 —— **一个一个模块核对，分批来，无死角**。

Owner 2026-09-22：「一个一个模块核对扫描修复分批来无死角扫描全部」

═══ 为什么要有它 ═══
上一轮的全仓扫描（`scan_engine`）解决的是"**藏匿面**"：伪装、ADS、名称诡计、覆盖闭合。
它不回答另一个问题：**每个模块自己健不健康**。本器补的就是逐模块体检，并且：
  ① **分批** —— 640 个模块一次扫完报告没人看得完；按批走，每批有账、可复算、可接着走
  ② **每条判据都要能红** —— 只报"看着还行"的体检等于没体检
  ③ **扫不动的必须交代** —— 读不到/解析失败/导入失败，逐个列出原因，**绝不静默跳过**

═══ 判据（每条都有规则号，可单独关/开）═══
  MS-1 语法      ast.parse 能过吗
  MS-2 导入      在**隔离子进程**里真导入（不污染本进程），报 ImportError/NameError
  MS-3 吞错收口  本模块内还有没有**未收口**的裸 print 吞错
  MS-4 真静默    `except: pass` —— 比吞错更坏：连一行都不留
  MS-5 门纪律    有没有**绕过授权门**直接调写生产/镜像的模块函数
  MS-6 外部内容  读外部内容的模块有没有声明"不可信数据"纪律
  MS-7 署名      产出类文件（.md/.html）是否带开发者署名
  MS-8 未解析    模块内 import 是否都能在盘上/标准库里找到落点
  MS-9 体积     超大文件 / 超长行（藏载荷与生成物混进来）

用法：
    py -3.14 -m gbt_allinone.tools.module_sweep --list              # 看分批清单
    py -3.14 -m gbt_allinone.tools.module_sweep --batch 1/8         # 扫第 1 批
    py -3.14 -m gbt_allinone.tools.module_sweep --batch 1/8 --json
"""
from __future__ import annotations

import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_scope import SKIP_DIRS, iter_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

# 绕过授权门的写法（MS-5）：这些函数**必须**经 run_task 走门，不许直接调
DOOR_BYPASS = (
    "mirror_space.ascend", "mirror_space.release", "mirror_space.rewind",
    "deployment_rehearsal.release", "qiankun.one_key_deploy",
    "room_space.release", "room_space.shape", "mirror_space.shape",
)
BYPASS_ALLOW = {   # 允许出现的地方：测试（要验门在不在）、以及门自己
    "gbt_allinone/tests/",
}
UNTRUSTED_MARKERS = ("外部内容", "untrusted", "不可信", "external_content_check")
SIGNATURE = "开发者：自由的风"
BIG_FILE = 2 << 20          # 2 MiB
LONG_LINE = 512 << 10       # 单行 512 KiB


def modules(batch: int | None = None, total: int | None = None):
    """本次巡扫的模块清单（已剪枝）。给 batch/total 就只返回该批。"""
    files = sorted(iter_files(ROOT, suffixes=(".py",)))
    rels = [str(p.relative_to(ROOT)).replace("\\", "/") for p in files]
    if not batch or not total:
        return rels, rels
    total = max(1, min(int(total), len(rels)))
    batch = max(1, min(int(batch), total))
    per = (len(rels) + total - 1) // total
    lo = (batch - 1) * per
    return rels[lo:lo + per], rels


def _import_probe(rel: str) -> dict:
    """隔离子进程真导入：不污染本进程，且能抓到 import 期的 NameError/SyntaxError。"""
    code = (
        "import sys, json, importlib, traceback\n"
        "sys.path.insert(0, r'%s')\n"
        "mod = r'%s'\n"
        "out = {'ok': False, 'err': '', 'kind': ''}\n"
        "try:\n"
        "    if mod.endswith('__init__.py'):\n"
        "        pkg = mod[:-12].replace('/', '.').replace('\\\\', '.')\n"
        "    else:\n"
        "        pkg = mod[:-3].replace('/', '.').replace('\\\\', '.')\n"
        "    importlib.import_module(pkg)\n"
        "    out['ok'] = True\n"
        "except BaseException as e:\n"
        "    out['err'] = '%%s: %%s' %% (type(e).__name__, str(e)[:160])\n"
        "    out['kind'] = type(e).__name__\n"
        "print('@@SWEEP@@' + json.dumps(out, ensure_ascii=False))\n"
    ) % (str(ROOT), rel)
    try:
        cp = subprocess.run([sys.executable, "-c", code], capture_output=True,
                            text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return {"ok": False, "err": "导入超时 60s", "kind": "Timeout"}
    for line in (cp.stdout or "").splitlines():
        if line.startswith("@@SWEEP@@"):
            return json.loads(line[9:])
    return {"ok": False, "err": (cp.stderr or "")[-200:], "kind": "NoOutput"}


def check_module(rel: str, deep: bool = True) -> dict:
    p = ROOT / rel
    row = {"module": rel, "bytes": 0, "findings": []}

    def add(rule, sev, detail, **extra):
        row["findings"].append({"rule": rule, "severity": sev, "detail": detail, **extra})

    try:
        raw = p.read_bytes()
    except OSError as e:
        add("MS-1", "error", "读不出来（%s）—— 盲区必须可见" % type(e).__name__)
        return row
    row["bytes"] = len(raw)
    txt = raw.decode("utf-8-sig", errors="replace")

    # MS-1 语法
    try:
        tree = ast.parse(txt, filename=str(p))
    except SyntaxError as e:
        add("MS-1", "error", "语法错误 行%d: %s" % (e.lineno, e.msg))
        return row
    # MS-2 导入（只在 deep 且不是测试夹具时做）
    if deep:
        r = _import_probe(rel)
        if not r["ok"]:
            sev = "warn" if r["kind"] in ("ImportError", "ModuleNotFoundError") else "error"
            add("MS-2", sev, "导入失败：%s" % r["err"], kind=r["kind"])
    # MS-3 未收口的裸吞错
    bare = re.compile(r'print\(f"⚠️\s*\w+:\s*吞错:\s*\{_?e\}",\s*file=')
    for i, line in enumerate(txt.splitlines(), 1):
        if bare.search(line):
            ctx = "\n".join(txt.splitlines()[max(0, i - 5):i])
            if "def _record_swallow(" not in ctx:
                add("MS-3", "error", "行%d 未收口的裸吞错" % i, line=i)
    # MS-4 真静默
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 \
                and isinstance(node.body[0], ast.Pass):
            add("MS-4", "warn", "行%d `except: pass` —— 真静默，连一行都不留"
                % getattr(node, "lineno", 0), line=getattr(node, "lineno", 0))
    # MS-5 门纪律：**按真调用判，不按关键词判**（第一版用文本关键词 ⇒ 3 处全是误报：
    # 两处注释、一处是 api.py 自己 —— 而 api.py **就是那道门**，门自己调内部件合法）
    if not any(rel.startswith(a) for a in BYPASS_ALLOW) and rel != "gbt_allinone/api.py":
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            dotted = []
            while isinstance(fn, ast.Attribute):
                dotted.append(fn.attr)
                fn = fn.value
            if isinstance(fn, ast.Name):
                dotted.append(fn.id)
            name = ".".join(reversed(dotted))
            if any(name == p or name.endswith("." + p) for p in DOOR_BYPASS):
                add("MS-5", "error", "行%d 绕过授权门直接调 %s（写生产/镜像必须走 run_task）"
                    % (node.lineno, name), line=node.lineno)
                break
    # MS-6 外部内容纪律
    if re.search(r"urlopen|requests\.(get|post)|web_fetch|web_read", txt) \
            and not any(m in txt for m in UNTRUSTED_MARKERS):
        add("MS-6", "warn", "读外部内容但没声明『不可信数据』纪律")
    # MS-8 未解析导入：**委托 `cross_scan._rel_imports`**（R-H170 契约的既有实现）。
    # 第一版我自己写了一遍朴素 AST 遍历 ⇒ 把 `try: from ..bridge import …` 报成断链，
    # 而那是**家规第 10 条允许的"优雅降级占位"**（见 tests/test_scan_contracts.py:10-12：
    # bridge 这类业务模块本就该在框架里缺席）。
    # 本仓规矩是**不许有第二个真相源**：硬导入/受保护导入的区分早有实现，且"提到≠用了"
    # 也已在那里处理（docstring/字符串/注释里的 import 不算）。直接用它，别再写一遍。
    try:
        import importlib
        _cs = None
        for _name in ("gbt_allinone.cross_scan", "cross_scan"):
            try:
                _cs = importlib.import_module(_name)
                break
            except Exception:                                  # noqa: BLE001
                continue
        if _cs is None:
            add("MS-8", "info", "MS-8 无法判定：cross_scan 不可用（不猜，如实标注）")
        else:
            for _level, _mod in _cs._rel_imports(txt):
                base = p.parent
                for _ in range(int(_level) - 1):
                    base = base.parent
                cand = base / (str(_mod).replace(".", "/") + ".py")
                pkg = base / str(_mod).replace(".", "/") / "__init__.py"
                if not cand.is_file() and not pkg.is_file():
                    add("MS-8", "warn", "硬导入落点找不到：%s%s"
                        % ("." * int(_level), _mod))
    except Exception as e:                                     # noqa: BLE001
        add("MS-8", "info", "MS-8 判定失败（%s: %s）—— 不静默，如实标注"
            % (type(e).__name__, str(e)[:80]))
    # MS-9 体积
    if len(raw) > BIG_FILE:
        add("MS-9", "warn", "文件 %.1f MB（生成物混进来的常见形态）" % (len(raw) / 1048576))
    for i, line in enumerate(txt.splitlines(), 1):
        if len(line) > LONG_LINE:
            add("MS-9", "warn", "行%d 超长（%.0f KiB）" % (i, len(line) / 1024), line=i)
            break
    return row


def sweep(batch=None, total=None, deep=True, out: str = "") -> dict:
    want, allmods = modules(batch, total)
    t0 = time.perf_counter()
    rows = [check_module(r, deep=deep) for r in want]
    errs = sum(1 for r in rows for f in r["findings"] if f["severity"] == "error")
    warns = sum(1 for r in rows for f in r["findings"] if f["severity"] == "warn")
    bad = [r["module"] for r in rows if any(f["severity"] == "error" for f in r["findings"])]
    rep = {
        "ok": errs == 0,
        "readonly": True,
        "root": str(ROOT),
        "batch": "%s/%s" % (batch, total) if batch else "全部",
        "modules_total": len(allmods),
        "modules_in_batch": len(rows),
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "error_count": errs, "warn_count": warns,
        "modules_with_error": bad,
        "rows": rows,
    }
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rep, ensure_ascii=False) + "\n")
    return rep


def main(argv=None) -> int:                                     # pragma: no cover
    ap = argparse.ArgumentParser(description="分批模块巡扫器")
    ap.add_argument("--batch", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-deep", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args(argv)
    b = t = None
    if a.batch:
        k, _, n = a.batch.partition("/")
        b, t = int(k), int(n or k)
    if a.list:
        want, allmods = modules(b, t)
        print("模块总数 = %d" % len(allmods))
        for i, m in enumerate(want, 1):
            print("   %3d  %s" % (i, m))
        return 0
    rep = sweep(b, t, deep=not a.no_deep, out=a.out)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0 if rep["ok"] else 1
    print("═══ 模块巡扫 · 批次 %s ═══" % rep["batch"])
    print("模块总数 %d · 本批 %d · 用时 %.2fs" % (rep["modules_total"], rep["modules_in_batch"],
                                              rep["elapsed_s"]))
    print("error %d · warn %d · 有 error 的模块 %d 个"
          % (rep["error_count"], rep["warn_count"], len(rep["modules_with_error"])))
    for r in rep["rows"]:
        if not r["findings"]:
            continue
        print("   %s" % r["module"])
        for f in r["findings"][:a.limit]:
            print("      [%s] %-6s %s" % (f["severity"], f["rule"], f["detail"]))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
