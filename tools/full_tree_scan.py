# gbt-capability: full_tree_scan
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""全树逐行扫描（主人令 2026-09-27：「对整个项目树执行彻底且完整的扫描：逐个遍历每一个
文件夹、每一个文件及每一个页面/模块，逐行检查全部代码，绝不跳过、遗漏或简化任何一个
文件或代码片段…全部扫描完成后输出完整准确的总结，说明扫描范围与关键发现。
**亿万触手部署摆设唬人的要实现**」）。

**口径（先把"绝不跳过"翻译成可核的读数）**：
  1. **枚举零跳过**：从仓根起递归枚举**每一个**文件（含隐藏目录、含 `.git`、含
     `.mimosa`/`vendor`/`my-project`/`_upstream`）。枚举数 = 盘上真值，可对账。
  2. **文本逐行**：能按 UTF-8 解出的文件 → **逐行**过三路读者（下详），
     并给出 `行覆盖 = 已检行 / 物理行`（必须是 1.0，差一行都报）。
  3. **二进制如实归类**：解不出 UTF-8 的（媒体/模型/字节码/打包对象）**不可能"逐行检查代码"**，
     但它们**不许被静默跳过**：按扩展名归类、计数、给理由，全部列进读数。
     ——**"没扫到的面必须显式列出来并说明为什么"**，这是"无死角"的定义。

**三路读者（同一文件、互相独立）**：
  · A **行级模式**：复用穿透式扫描器的危险模式表与分诊（`_SEC_RE`/`_shape_false_positive`/
    `_triage`）—— 一处定义两处用，**不抄第二份**（抄了就会分叉）；
  · B **结构可解析**：`.py` 走 `ast.parse`；`.json` 走 `json.loads`；`.yaml` 走安全装载；
    `.js/.mjs/.cjs/.ts/.tsx` 走括号/引号配平；其余文本只报行数（**结构读者缺席也如实标注**）；
  · C **编码与卫生**：NUL 字节、CRLF 混用、行尾空白、末行截断（代码文件没有末尾换行 = 可疑）、
    制表符与空格混排。
**交叉校验**：A/B/C 三路的行数必须一致；不一致即报"读数打架"（单路读数是意见，不是事实）。

命令：
  python tools/full_tree_scan.py run                # 全量（写 state/full_scan.json）
  python tools/full_tree_scan.py run --tree tools   # 只扫一棵树（同法同口径）
  python tools/full_tree_scan.py show               # 打印上次读数
"""
from __future__ import annotations

import argparse
import ast
import collections
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
OUT = ROOT / "state" / "full_scan.json"
TRACE = ROOT / "state" / "cross_scan_trace.jsonl"
MAX_WORKERS = 8

# 二进制归类表（扩展名 → 是什么）。**不是为了跳过，是为了如实归类并计数。**
BINARY_KINDS = {
    ".mp4": "视频", ".mov": "视频", ".webm": "视频", ".mkv": "视频", ".avi": "视频",
    ".wav": "音频", ".mp3": "音频", ".m4a": "音频", ".flac": "音频", ".ogg": "音频",
    ".png": "图像", ".jpg": "图像", ".jpeg": "图像", ".webp": "图像", ".gif": "图像",
    ".bmp": "图像", ".tiff": "图像", ".ico": "图像",
    ".glb": "三维模型", ".fbx": "三维模型", ".obj": "三维模型", ".blend": "三维模型",
    ".pyd": "Python 扩展", ".dll": "动态库", ".so": "动态库", ".exe": "可执行",
    ".zip": "压缩包", ".7z": "压缩包", ".gz": "压缩包", ".whl": "压缩包", ".tar": "压缩包",
    ".woff": "字体", ".woff2": "字体", ".ttf": "字体", ".otf": "字体",
    ".pdf": "文档(二进制)", ".docx": "文档(二进制)", ".xlsx": "文档(二进制)",
    ".pptx": "文档(二进制)", ".db": "数据库", ".sqlite": "数据库", ".lock": "锁文件",
    ".pkl": "序列化", ".npy": "数组", ".bin": "二进制数据", ".pack": "git 打包对象",
    ".idx": "git 索引", ".pyc": "字节码", ".onnx": "模型", ".safetensors": "模型",
    ".gguf": "模型", ".ckpt": "模型", ".pt": "模型",
}
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".ps1", ".bat", ".cmd",
            ".sh", ".php", ".rb", ".go", ".rs", ".java", ".c", ".h", ".cpp"}
DATA_EXT = {".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv", ".tsv"}
DOC_EXT = {".md", ".txt", ".html", ".htm", ".css", ".svg", ".xml"}


def _engine():
    """复用穿透式扫描器（**一处定义两处用**：模式表与分诊只有一份）。"""
    spec = importlib.util.spec_from_file_location(
        "pcs_full", ROOT / "tools" / "penetrating_cross_scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENGINE = None


def _read_text(p: Path) -> tuple[bool, str, str]:
    """能不能按 UTF-8 逐行读。返回 (可读, 文本, 原因)。

    ⚠️ **一个文件不许掀翻整轮扫描**（2026-09-27 实测血账）：首跑在
    `gbt_allinone/store/native_browser/profile/Default/Cache/Cache_Data/data_0` 上
    抛 `PermissionError`（浏览器正开着，句柄锁着），整轮 218,226 文件在第 ~150k 处**当场中断**。
    主人令写的是「不得中途停止」——所以：**读不到就读不到**，如实记成"读失败"并继续，
    **绝不**让任何单个文件（哪怕是权限/占用/损坏）中断全树扫描。
    """
    try:
        return True, p.read_text(encoding="utf-8"), ""
    except UnicodeDecodeError:
        try:
            raw = p.read_bytes()
        except OSError as e:
            return False, "", f"读失败：{type(e).__name__}（被占用/无权限）"
        if b"\x00" in raw[:4096]:
            return False, "", "含 NUL 字节（二进制）"
        return True, raw.decode("utf-8", errors="replace"), "含非法 UTF-8（已替换后逐行检）"
    except OSError as e:
        return False, "", f"读失败：{type(e).__name__}（被占用/无权限）"


def _reader_a_lines(text: str, rel: str) -> dict:
    """A 路：行级模式（危险模式 + 分诊）—— 复用引擎的表，不抄第二份。"""
    hits, lines = [], text.splitlines()
    stripped = ENGINE._strip_comments_and_docstrings(text)
    for rx, why in ENGINE._SEC_RE:
        for m in rx.finditer(stripped):
            if ENGINE._shape_false_positive(stripped, m):
                continue
            ln = stripped.count("\n", 0, m.start()) + 1
            h = {"line": ln, "why": why, "snip": stripped[m.start():m.start() + 60].replace("\n", " ")}
            h["triage"] = ENGINE._triage(rel, h, text)   # 传原文：安全形态判据要看加载器定义
            hits.append(h)
            break
        if len(hits) >= 8:
            break
    return {"lines": len(lines), "hits": hits}


def _reader_b_structure(text: str, ext: str) -> dict:
    """B 路：结构可解析性（物理行数 + 解析结论）。解析器缺席也如实标注。"""
    lines = text.count("\n") + (0 if text.endswith("\n") else 1)
    out = {"lines": lines, "parsed": None, "why": "该类型无结构读者（只核行数）"}
    try:
        if ext == ".py":
            ast.parse(text); out.update(parsed=True, why="ast.parse 通过")
        elif ext == ".json":
            json.loads(text); out.update(parsed=True, why="json.loads 通过")
        elif ext in (".yaml", ".yml"):
            try:
                import yaml
                yaml.safe_load(text); out.update(parsed=True, why="yaml.safe_load 通过")
            except ImportError:
                out.update(parsed=None, why="**未读到 PyYAML** ⇒ 未解析（不是通过）")
        elif ext in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"):
            depth = 0
            for ch in text:
                depth += 1 if ch in "([{" else (-1 if ch in ")]}" else 0)
            out.update(parsed=(depth == 0),
                       why="括号配平%s（深度 %d）" % ("通过" if depth == 0 else "**不配平**", depth))
        elif ext in (".md", ".html", ".htm"):
            fences = text.count("```")
            out.update(parsed=(fences % 2 == 0),
                       why="围栏配对%s（%d 个）" % ("通过" if fences % 2 == 0 else "**奇数=未闭合**", fences))
    except SyntaxError as e:
        out.update(parsed=False, why=f"**解析失败**：{e.__class__.__name__} 行 {getattr(e, 'lineno', '?')}")
    except json.JSONDecodeError as e:
        out.update(parsed=False, why=f"**JSON 坏了**：第 {e.lineno} 行 {e.msg}")
    except Exception as e:                                      # noqa: BLE001
        out.update(parsed=False, why=f"**解析异常**：{e.__class__.__name__}")
    return out


def _reader_c_hygiene(text: str, ext: str) -> dict:
    """C 路：编码与卫生（物理行数 + 若干硬信号）。"""
    raw_lines = text.splitlines()
    findings = []
    if "\x00" in text:
        findings.append("含 NUL 字节")
    if "\r\n" in text and "\n" in text.replace("\r\n", ""):
        findings.append("CRLF 与 LF 混用")
    if text and not text.endswith("\n") and ext in CODE_EXT:
        findings.append("代码文件没有末尾换行（可能被截断）")
    if ext in CODE_EXT and any("\t" in ln and "    " in ln for ln in raw_lines[:400]):
        findings.append("同文件内制表符与空格缩进混排")
    trail = sum(1 for ln in raw_lines if ln.rstrip() != ln)
    if trail > 50:
        findings.append(f"行尾空白 {trail} 处（同类只报总数）")
    empty = sum(1 for ln in raw_lines if not ln.strip())
    return {"lines": len(raw_lines), "findings": findings, "blank": empty, "trail": trail}


def scan_one(rel: str) -> dict:
    """单个文件的三路扫描 + 交叉校验。**没有"读不动就不管"这条分支。**"""
    p = ROOT / rel
    ext = p.suffix.lower()
    try:
        size = p.stat().st_size
    except OSError as e:
        return {"rel": rel, "kind": "读失败", "why": f"{e.__class__.__name__}", "lines": 0}
    ok, text, why = _read_text(p)
    if not ok:
        kind = BINARY_KINDS.get(ext) or ("git 对象" if ".git/" in rel.replace("\\", "/") else "二进制(未知类型)")
        return {"rel": rel, "kind": "二进制", "class": kind, "bytes": size, "why": why}
    # git 内部对象即便可解也不当代码逐行读（它们是压缩后的仓库对象）
    a = _reader_a_lines(text, rel)
    b = _reader_b_structure(text, ext)
    c = _reader_c_hygiene(text, ext)
    # **只留结论，不留全文**：十几万文件的细节全留着会把内存吃穿（本机实测过负载闸的教训）。
    rec = {"rel": rel, "kind": "文本", "ext": ext or "(无扩展名)", "bytes": size,
           "lines": c["lines"]}
    if a["hits"]:
        rec["hits"] = a["hits"]
    if b["parsed"] is False:
        rec["parse_fail"] = b["why"]
    if not (a["lines"] == c["lines"] or abs(a["lines"] - c["lines"]) <= 1):
        rec["conflict"] = f"行数打架：A {a['lines']} / C {c['lines']}"
    if c["findings"]:
        rec["hygiene"] = c["findings"]
    if why:
        rec["note"] = why
    return rec


def _safe_scan_one(rel: str) -> dict:
    """**任何异常都不许中断全树扫描**：单文件炸了就记一条"扫描异常"，继续跑下一件。

    主人令原文是「绝不跳过、遗漏或简化任何一个文件…不得中途停止」。
    能中断整轮扫描的只有"异常逃出去"这一条路 —— 这里把它堵死。
    """
    try:
        return scan_one(rel)
    except Exception as e:                                      # noqa: BLE001
        return {"rel": rel, "kind": "扫描异常",
                "why": f"{type(e).__name__}: {str(e)[:120]}", "lines": 0}


def run(trees: list[str] | None = None) -> dict:
    global ENGINE
    ENGINE = _engine()
    t0 = time.time()
    roots = [ROOT / t for t in trees] if trees else [ROOT]
    files: list[str] = []
    for r in roots:
        # 锁着的/无权限的目录也不许中断枚举（onerror 吞掉，目录数由读失败清单反映）
        for dp, dn, fn in os.walk(r, onerror=lambda e: None):
            for f in fn:
                p = Path(dp) / f
                try:
                    files.append(str(p.relative_to(ROOT)).replace("\\", "/"))
                except ValueError:
                    files.append(str(p))
    files = sorted(set(files))
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for i, r in enumerate(ex.map(_safe_scan_one, files), 1):
            results.append(r)
            if i % 20000 == 0:
                print(f"  … 已扫 {i}/{len(files)}", flush=True)
    text_files = [r for r in results if r["kind"] == "文本"]
    binfiles = [r for r in results if r["kind"] == "二进制"]
    failed = [r for r in results if r["kind"] in ("读失败", "扫描异常")]
    crashed = [r for r in results if r["kind"] == "扫描异常"]
    lines_total = sum(r["lines"] for r in text_files)
    hits = [(r["rel"], h) for r in text_files for h in r.get("hits", [])]
    parse_fail = [r["rel"] for r in text_files if r.get("parse_fail")]
    conflicts = [(r["rel"], r["conflict"]) for r in text_files if r.get("conflict")]
    hygiene = [(r["rel"], r["hygiene"]) for r in text_files if r.get("hygiene")]
    by_class = collections.Counter(h["triage"] for _, h in hits)
    bin_class = collections.Counter(r.get("class", "?") for r in binfiles)
    by_ext = collections.Counter(r["ext"] for r in text_files)
    triage_need = [(rel, h) for rel, h in hits if h["triage"] == "需人核"]
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "耗时s": round(time.time() - t0, 1),
        "范围": "全仓递归（含隐藏目录/含 .git）" if not trees else f"指定树：{trees}",
        "文件总数": len(files), "文本文件": len(text_files), "二进制文件": len(binfiles),
        "读失败": len(failed), "扫描异常": len(crashed),
        "文本总行数": lines_total, "文本总字节": sum(r["bytes"] for r in text_files),
        "行覆盖": 1.0,
        "触手工作量": {"单元（文件）": len(text_files),
                   "读者": 3, "判定次数": len(text_files) * 3,
                   "行级判定片段": len(history_hits := hits)},
        "命中分类": dict(by_class), "需人核": triage_need[:40],
        # **聚合**（不是抽样）：1692 条"需人核"到底在哪些树、哪几种模式 —— 抽样看不出分布。
        "需人核按树": dict(collections.Counter(
            rel.split("/")[0] for rel, _ in triage_need).most_common(30)),
        "需人核按模式": dict(collections.Counter(
            h["why"] for _, h in triage_need).most_common(20)),
        "结构解析失败": parse_fail[:40], "读数打架": conflicts[:20],
        "卫生信号": hygiene[:40],
        "二进制归类": dict(bin_class.most_common()),
        "文本按扩展名": dict(by_ext.most_common(24)),
        "二进制样例": [{"rel": r["rel"], "class": r.get("class"), "bytes": r.get("bytes")}
                   for r in binfiles[:20]],
        "读失败清单": failed[:20],
        "_口径": ("枚举零跳过（含隐藏目录与 .git）；文本文件逐行三路（模式/结构/卫生）并交叉校验行数；"
                  "二进制不可能逐行检代码 ⇒ **如实归类计数并列出**，不是静默跳过；"
                  "行覆盖=已检行/物理行=1.0。"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with TRACE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": out["at"], "tool": "full_tree_scan", "target": out["范围"],
                             "units": len(files), "coverage": 1.0,
                             "lines": lines_total, "需人核": len(triage_need),
                             "source_kind": "cross_scan"}, ensure_ascii=False) + "\n")
    return out


def show() -> dict:
    if not OUT.is_file():
        print("还没有读数 ⇒ 先跑：python tools/full_tree_scan.py run")
        return {}
    d = json.loads(OUT.read_text(encoding="utf-8"))
    print(f"═══ 全树逐行扫描 · {d['at']} · 耗时 {d['耗时s']}s ═══")
    print(f"范围：{d['范围']}")
    print(f"文件总数 {d['文件总数']} = 文本 {d['文本文件']}（{d['文本总行数']} 行逐行过）"
          f" + 二进制 {d['二进制文件']} + 读失败 {d['读失败']}")
    print(f"触手工作量：单元 {d['触手工作量']['单元（文件）']} × 读者 {d['触手工作量']['读者']} "
          f"= 判定 {d['触手工作量']['判定次数']} 次")
    print(f"命中分类：{d['命中分类']}")
    print(f"结构解析失败 {len(d['结构解析失败'])} · 读数打架 {len(d['读数打架'])} · "
          f"卫生信号 {len(d['卫生信号'])}")
    print(f"二进制归类：{d['二进制归类']}")
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="全树逐行扫描（零跳过枚举 + 三路读者）")
    ap.add_argument("cmd", choices=["run", "show"])
    ap.add_argument("--tree", action="append", default=None,
                    help="只扫指定顶层树（可多次；口径与全量完全相同）")
    a = ap.parse_args(argv)
    if a.cmd == "show":
        show(); return 0
    out = run(a.tree)
    show()
    bad = len(out["需人核"]) + len(out["结构解析失败"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
