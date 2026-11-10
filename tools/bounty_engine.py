#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tools/bounty_engine.py · 赏金插件 python 引擎桥（GBT 原生两路 lane）

契约来源：`超级万能插/plugins/bounty/SPEC.md` §4 `lib/engine.mjs`（回执 schema 严格对齐）：
    { ok, action:'scan-code', root, lanes:[{id,engine,ok,ms,coverage?,error?}],
      findings:[{id,engine,file,line,cwe,severity,title,snippet,
                 evidence:{fileSha256,lineText,howFound},repro,confidence,kind}],
      coverage:{complete,files_eligible,files_scanned,rate,truncated,unread:[{lane,why,missed?}]},
      notes:[...] }

硬口径（不许静默变形）：
  1. **stdout 只有一个 JSON**。所有日志/进度一律走 stderr —— 宿主管道按 `JSON.parse(stdout)`
     读回执，混进一行日志整份就失败。参数不合法时 stdout 仍只打一个 needs_input JSON。
  2. **不碰源文件**：lane1 用运行期 monkey-patch（`_ROOT` 指向 --root，`_FINDINGS/_LEDGER`
     重定向到 --out，跑完还原），不复制、不改 `gbt_allinone/tools/code_audit.py`。
  3. **覆盖诚实**：任一 lane 失败/超时/截断/未读（大文件跳过、钩子未钩住）⇒
     `coverage.unread[]` + `coverage.complete=false`，绝不把"没扫到"折成 0 条干净。
  4. **No exploit, no report**：scan-code 阶段的条目一律 `kind='candidate'`；
     `verify-code` 三查（文件 sha256 / 行文本 / snippet 字面搜索）都过了才是 `kind='finding'`。
  5. **code_audit 的 needs_human 不丢**：分诊为「需人核」的命中同样映射成候选
     （confidence='low'，evidence.howFound 注明分诊原因），lane1 的举证不因分诊而消失；
     与 lane2 同 (file,line,cwe) 的条目由合并去重收口，不重复计数。

用法（Python 必须用仓内 pyembed；embeddable 包 `-m`/PYTHONPATH 都失效，见 AGENTS §3.1-C）：
    .\\pyembed\\python.exe tools\\bounty_engine.py --action selfcheck
    .\\pyembed\\python.exe tools\\bounty_engine.py --action scan-code --root <绝对目录> --out <输出目录> [--timeout 240]
    .\\pyembed\\python.exe tools\\bounty_engine.py --action verify-code --root <目录> --findings <json文件>
    .\\pyembed\\python.exe tools\\bounty_engine.py --action enrich --findings <json文件>

退出码：0=回执 ok；1=回执 ok=false（真失败/部分失败）；2=参数不全（needs_input）。

失败三态照实回（AGENTS §2.1）：`needs_input`（缺参数/路径无效）、
`needs_dependency`（模块/目录不可用）、`failed`（真失败，带上游原话）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import sys
import threading
import time
import traceback
from pathlib import Path

# ── 出口编码（照抄本仓既有口径：GBK 控制台下中文会 UnicodeEncodeError ⇒ 结论整份丢失）──
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]          # GBT 仓根（= tools/ 的上一层）
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS_DIR = ROOT / "tools"
PCS_PATH = TOOLS_DIR / "penetrating_cross_scan.py"
MAX_SNIPPET = 160

# code_audit 规则 → CWE（只做映射，不改它的判定；CWE 未收录时 bounty_core.cwe_info 会给通用修复建议）
RULE_CWE = {
    "CRED-001": "CWE-798",   # 硬编码凭据
    "INJ-001": "CWE-95",     # 动态执行
    "INJ-002": "CWE-78",     # 命令注入面（shell=True）
    "DES-001": "CWE-78",     # 破坏性命令 = OS 命令执行面
    "JDG-001": "CWE-571",    # 恒真判据
}
# needs_human（分诊为「需人核」）也映射成候选时用的 severity/title（与 code_audit RULES 对齐）
RULE_SEVERITY = {"CRED-001": "high", "INJ-001": "high", "INJ-002": "medium",
                 "DES-001": "high", "JDG-001": "medium"}
RULE_TITLE = {"CRED-001": "可疑密钥字面量", "INJ-001": "动态执行（把字符串当代码跑）",
              "INJ-002": "shell=True 或字符串拼命令", "DES-001": "破坏性命令",
              "JDG-001": "恒真/恒假判据"}

# 穿透式交叉扫描 security_pass 的 why → (CWE, 默认 severity)
PCS_WHY_MAP = (
    ("动态执行 eval", "CWE-95", "high"),
    ("动态执行 exec", "CWE-95", "high"),
    ("shell=True", "CWE-78", "high"),
    ("系统命令执行", "CWE-78", "high"),
    ("下载即执行", "CWE-78", "high"),
    ("Node 子进程执行", "CWE-78", "medium"),
    ("疑似硬编码凭据", "CWE-798", "high"),
    ("私钥字面量", "CWE-321", "high"),
    ("不安全反序列化", "CWE-502", "high"),
    ("双扩展名", "CWE-506", "medium"),
    ("base64 解码", "CWE-506", "low"),
)
SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "none": 0}


def log(msg: str) -> None:
    """日志只走 stderr（stdout 留给唯一一个 JSON 回执）。"""
    print("[bounty_engine] %s" % msg, file=sys.stderr, flush=True)


# ── 工具函数 ────────────────────────────────────────────────────────────
_BasePath = type(Path())


class _OutPath(_BasePath):
    """out 目录可能不在 target root 下；code_audit.scan 结尾会做
    `_FINDINGS.relative_to(_ROOT)`，越界会 ValueError。这里只让那一次**展示**用路径
    原样返回（真实文件读写仍走本类的父类实现，行为不变）。"""
    def relative_to(self, other, *args, **kwargs):
        try:
            return super().relative_to(other, *args, **kwargs)
        except ValueError:
            return self


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_root(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = ROOT / p
    try:
        return p.resolve()
    except OSError:
        return p


def _resolve_out(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = ROOT / p
    return p


def _rel(root: Path, p) -> str:
    """文件路径 → 相对 root 的 posix 路径（不在 root 下就原样 posix，不假装相对）。"""
    pp = Path(p)
    try:
        return pp.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return pp.as_posix()


def _read_lines(p: Path) -> list:
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _write_json_atomic(path: Path, obj) -> None:
    """原子写（tmp + fsync + os.replace）+ 写后读回校验（AGENTS §2.4 原子替换唯一写法）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    json.loads(path.read_text(encoding="utf-8"))     # 写后读回：不合法就在这里炸，别留下坏档


def _finding_id(file_rel: str, line: int, cwe: str) -> str:
    seed = "%s|%s|%s" % (file_rel, line, cwe)
    return "BF-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


class _Timeout(RuntimeError):
    pass


def _run_with_timeout(fn, seconds: float, label: str):
    """lane 级硬超时：跑在 daemon 线程里，join 超时即报 failed（不许假装扫完）。"""
    box = {}

    def _target():
        try:
            box["value"] = fn()
        except BaseException as exc:                    # noqa: BLE001 - 要连 SystemExit 一起收
            box["error"] = exc
            box["trace"] = traceback.format_exc()

    th = threading.Thread(target=_target, name="bounty-lane-%s" % label, daemon=True)
    th.start()
    th.join(float(seconds) if seconds and seconds > 0 else None)
    if th.is_alive():
        raise _Timeout("超时 %ss（lane=%s，后台线程已放弃，结果不采用）" % (seconds, label))
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _load_pcs(trace_path=None):
    """importlib 加载 tools/penetrating_cross_scan.py（该文件支持绝对路径 tree: 目标）。"""
    if not PCS_PATH.is_file():
        raise FileNotFoundError("穿透式交叉扫描不在盘上：%s" % PCS_PATH)
    name = "bounty_pcs_runtime_%d" % time.time_ns()
    spec = importlib.util.spec_from_file_location(name, str(PCS_PATH))
    if spec is None or spec.loader is None:
        raise ImportError("importlib 无法加载：%s" % PCS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if trace_path is not None:
        # 留痕重定向到本次 out（不改仓库 state/，两次 run 不互踩）
        mod.TRACE = Path(trace_path)
    return mod


# ── lane1：code_audit（运行期 monkey-patch 到任意 root）─────────────────
def _lane_code_audit(root: Path, out_dir: Path, timeout_s: float):
    t0 = time.time()
    lane = {"id": "code_audit", "engine": "code_audit", "ok": False, "ms": 0}
    box = {}

    def _work():
        from gbt_allinone.tools import code_audit as ca     # 延迟导入：导入失败也算 lane 失败
        saved = (ca._ROOT, ca._STATE, ca._FINDINGS, ca._LEDGER)
        ca._ROOT = root
        ca._STATE = out_dir
        ca._FINDINGS = _OutPath(str(out_dir / "code_audit_findings.json"))
        ca._LEDGER = _OutPath(str(out_dir / "code_audit.jsonl"))
        try:
            box["scan"] = ca.scan(target=str(root))
            box["doc"] = json.loads(ca._FINDINGS.read_text(encoding="utf-8"))
            box["findings_file"] = str(ca._FINDINGS)
        finally:
            ca._ROOT, ca._STATE, ca._FINDINGS, ca._LEDGER = saved

    try:
        _run_with_timeout(_work, timeout_s, "code_audit")
    except Exception as exc:                                # noqa: BLE001
        lane["ms"] = int((time.time() - t0) * 1000)
        lane["error"] = "%s: %s" % (type(exc).__name__, exc)
        return lane, [], {}

    res = box.get("scan") or {}
    doc = box.get("doc") or {}
    cov = res.get("coverage") or {}
    lane["ms"] = int((time.time() - t0) * 1000)
    lane["ok"] = bool(res.get("ok"))
    if not lane["ok"]:
        lane["error"] = str(res.get("error") or "code_audit scan 返回 ok=false")
    lane["coverage"] = {
        "eligible": cov.get("eligible"),
        "scanned": cov.get("scanned"),
        "rate": cov.get("rate"),
        "truncated_at": cov.get("truncated_at") or [],
        "skipped_big": cov.get("skipped_big") or [],
        "skipped_big_count": cov.get("skipped_big_count", len(cov.get("skipped_big") or [])),
        "full": cov.get("full"),
        "no_silent_gap": cov.get("no_silent_gap"),
        "files": res.get("files"),
        "lines": res.get("lines"),
        "findings": len(doc.get("findings") or []),
        "needs_human": len(doc.get("needs_human") or []),
        "findings_file": box.get("findings_file", ""),
        "口径": cov.get("_口径", ""),
    }
    f_main = _convert_code_audit(doc.get("findings") or [])
    f_needs = _convert_code_audit_needs(root, doc.get("needs_human") or [])
    lane["coverage"]["needs_human_candidates"] = len(f_needs)
    return lane, f_main + f_needs, cov


def _convert_code_audit(rows) -> list:
    """code_audit finding → 引擎统一 schema（相对 root 的 file 由 lane1 已保证）。"""
    out = []
    for f in rows:
        rule = str(f.get("rule") or "")
        line = int(f.get("line") or 0)
        rel = str(f.get("file") or "").replace("\\", "/")
        ev = f.get("evidence") or {}
        out.append({
            "engine": "code_audit",
            "file": rel,
            "line": line,
            "cwe": RULE_CWE.get(rule, ""),
            "severity": str(f.get("severity") or "medium"),
            "title": str(f.get("what") or rule or "code_audit 命中"),
            "snippet": str(f.get("snippet") or "")[:MAX_SNIPPET],
            "evidence": {
                "fileSha256": str(ev.get("file_sha256") or ""),
                "lineText": str(ev.get("line_text") or ""),
                "howFound": "code_audit 规则 %s 正则命中（第 1 路读法）" % rule,
            },
            "repro": str(f.get("repro") or ""),
            "confidence": "medium",
            "kind": "candidate",
            "sources": ["code_audit"],
        })
    return out


def _convert_code_audit_needs(root: Path, rows) -> list:
    """code_audit 分诊为「需人核」的命中 → 候选条目（lane1 举证不丢，confidence=low）。

    needs_human 行只有 rule/file/line/snippet/why（没有 evidence/repro），这里补三件：
    文件 sha256、真实行文本、同一行的 python 读取命令（与 lane1 finding 同一套证据口径，
    所以 verify-code 的三查同样能复核它）。
    """
    out = []
    for f in rows:
        rule = str(f.get("rule") or "")
        line_no = int(f.get("line") or 0)
        rel = str(f.get("file") or "").replace("\\", "/")
        why = str(f.get("why") or "")
        p = root / rel
        exists = p.is_file()
        lines = _read_lines(p) if exists else []
        line_text = ""
        if 0 < line_no <= len(lines):
            line_text = lines[line_no - 1].strip()[:MAX_SNIPPET]
        snippet = line_text or str(f.get("snippet") or "")[:MAX_SNIPPET]
        out.append({
            "engine": "code_audit",
            "file": rel,
            "line": line_no,
            "cwe": RULE_CWE.get(rule, ""),
            "severity": RULE_SEVERITY.get(rule, "medium"),
            "title": "%s（需人核）" % RULE_TITLE.get(rule, rule or "code_audit 命中"),
            "snippet": snippet,
            "evidence": {
                "fileSha256": _sha256_file(p) if exists else "",
                "lineText": line_text,
                "howFound": "code_audit 分诊为需人核：%s（规则 %s，进 needs_human，未定论）"
                            % (why, rule),
            },
            "repro": _repro_for(p, line_no),
            "confidence": "low",
            "kind": "candidate",
            "sources": ["code_audit"],
        })
    return out


# ── lane2：穿透式交叉扫描（绝对路径 tree: 目标）─────────────────────────
def _lane_pcs(root: Path, out_dir: Path, timeout_s: float):
    t0 = time.time()
    lane = {"id": "pcs", "engine": "pcs", "ok": False, "ms": 0}
    box = {}
    trace = out_dir / "cross_scan_trace.jsonl"

    def _work():
        pcs = _load_pcs(trace)
        box["rep"] = pcs.run_pipeline("tree:" + str(root))
        box["trace"] = str(trace)

    try:
        _run_with_timeout(_work, timeout_s, "pcs")
    except Exception as exc:                                # noqa: BLE001
        lane["ms"] = int((time.time() - t0) * 1000)
        lane["error"] = "%s: %s" % (type(exc).__name__, exc)
        return lane, [], {}

    rep = box.get("rep") or {}
    sec = rep.get("security") or {}
    lane["ms"] = int((time.time() - t0) * 1000)
    lane["ok"] = True
    lane["coverage"] = {
        "units": rep.get("units"),
        "hooked": rep.get("hooked"),
        "coverage": rep.get("coverage"),
        "full_coverage": bool(rep.get("full_coverage")),
        "agree": rep.get("agree"),
        "arbitrated": rep.get("arbitrated"),
        "missing": rep.get("missing") or [],
        "dead_spots": rep.get("dead_spots") or [],
        "dead_spot_count": rep.get("dead_spot_count"),
        "security": {
            "ok": sec.get("ok"),
            "scanned": sec.get("scanned"),
            "flagged": sec.get("flagged"),
            "needs_human": sec.get("needs_human"),
            "findings": sec.get("findings") or [],
            "口径": sec.get("口径", ""),
        },
        "trace": box.get("trace", ""),
        "口径": rep.get("口径", ""),
    }
    return lane, _convert_pcs(rep, root), rep


def _pcs_why_map(why: str):
    for needle, cwe, sev in PCS_WHY_MAP:
        if needle in why:
            return cwe, sev
    return "CWE-693", "low"


def _repro_for(p: Path, line_no: int) -> str:
    if line_no < 1:
        return ""
    return ("python -c \"import pathlib;print(pathlib.Path(r'%s').read_text(encoding='utf-8',"
            "errors='replace').splitlines()[%d])\"" % (p.as_posix(), line_no - 1))


def _convert_pcs(rep, root: Path) -> list:
    """security_pass 的 hits → 候选条目（只有分诊=需人核 的进候选；其余留在 lane coverage）。"""
    sec = rep.get("security") or {}
    out = []
    for row in sec.get("findings") or []:
        unit = str(row.get("unit") or "")
        if not unit:
            continue
        p = Path(unit)
        rel = _rel(root, p)
        exists = p.is_file()
        lines = _read_lines(p) if exists else []
        file_sha = _sha256_file(p) if exists else ""
        for hit in row.get("hits") or []:
            if str(hit.get("triage") or "") != "需人核":
                continue
            why = str(hit.get("why") or "")
            cwe, sev = _pcs_why_map(why)
            line_no = int(hit.get("line") or 0)
            line_text = ""
            if 0 < line_no <= len(lines):
                line_text = lines[line_no - 1].strip()[:MAX_SNIPPET]
            snippet = line_text or str(hit.get("snip") or "").replace("\n", " ")[:MAX_SNIPPET]
            out.append({
                "engine": "pcs",
                "file": rel,
                "line": line_no,
                "cwe": cwe,
                "severity": sev,
                "title": why,
                "snippet": snippet,
                "evidence": {
                    "fileSha256": file_sha,
                    "lineText": line_text,
                    "howFound": "穿透式交叉扫描 security_pass 模式分诊（第 3 路）：%s" % why,
                },
                "repro": _repro_for(p, line_no),
                "confidence": "low",
                "kind": "candidate",
                "sources": ["pcs"],
            })
    return out


# ── 合并 / 覆盖账 ──────────────────────────────────────────────────────
def _merge_findings(*groups) -> list:
    """按 (file,line,cwe) 去重；保留两条 lane 来源（sources 与 howFound 都写清）。"""
    merged, index = [], {}
    for group in groups:
        for f in group or []:
            key = (str(f.get("file") or ""), int(f.get("line") or 0), str(f.get("cwe") or ""))
            if key in index:
                tgt = merged[index[key]]
                for src in f.get("sources") or []:
                    if src not in tgt["sources"]:
                        tgt["sources"].append(src)
                extra = str((f.get("evidence") or {}).get("howFound") or "")
                if extra and extra not in str(tgt["evidence"].get("howFound") or ""):
                    tgt["evidence"]["howFound"] = ("%s；另有 %s"
                                                   % (tgt["evidence"].get("howFound") or "", extra))
                if SEVERITY_ORDER.get(f.get("confidence", ""), 0) > SEVERITY_ORDER.get(
                        tgt.get("confidence", ""), 0):
                    tgt["confidence"] = f["confidence"]
                if SEVERITY_ORDER.get(str(f.get("severity") or ""), 0) > SEVERITY_ORDER.get(
                        str(tgt.get("severity") or ""), 0):
                    tgt["severity"] = f["severity"]
                continue
            item = dict(f)
            item["id"] = _finding_id(key[0], key[1], key[2])
            item["sources"] = list(f.get("sources") or [])
            index[key] = len(merged)
            merged.append(item)
    return merged


def _assemble_coverage(lane1: dict, cov1: dict, lane2: dict, pcs_rep: dict) -> dict:
    unread = []
    lane1_ok = bool(lane1.get("ok"))
    lane2_ok = bool(lane2.get("ok"))
    if not lane1_ok:
        unread.append({"lane": "code_audit",
                       "why": "lane 失败：%s" % str(lane1.get("error") or "未运行"),
                       "missed": None})
    else:
        for t in cov1.get("truncated_at") or []:
            unread.append({"lane": "code_audit",
                           "why": "撞到 MAX_FILES 上限（truncated_at），后续文件未读",
                           "missed": str(t)})
        for b in cov1.get("skipped_big") or []:
            unread.append({"lane": "code_audit",
                           "why": "文件超过 MAX_BYTES 未读（skipped_big）",
                           "missed": str(b)})
    if not lane2_ok:
        unread.append({"lane": "pcs",
                       "why": "lane 失败：%s" % str(lane2.get("error") or "未运行"),
                       "missed": None})
    else:
        for u in (pcs_rep or {}).get("dead_spots") or []:
            unread.append({"lane": "pcs",
                           "why": "钩子未触发/交叉验证未钩住（unhooked），该单元未确认",
                           "missed": str(u)})

    if lane1_ok:
        eligible = int(cov1.get("eligible") or 0)
        scanned = int(cov1.get("scanned") or 0)
        truncated = bool(cov1.get("truncated_at"))
    else:
        pcs_cov = (lane2.get("coverage") or {}) if lane2_ok else {}
        eligible = int(pcs_cov.get("units") or 0)
        scanned = int(pcs_cov.get("hooked") or 0) if lane2_ok else 0
        truncated = False
    if eligible:
        rate = round(scanned / float(eligible), 4)
    else:
        rate = 1.0 if scanned else 0.0
    complete = bool(lane1_ok and lane2_ok and not truncated and not unread)
    return {
        "complete": complete,
        "files_eligible": eligible,
        "files_scanned": scanned,
        "rate": rate,
        "truncated": truncated,
        "unread": unread,
    }


def _scan_notes(out_dir: Path) -> list:
    return [
        "lane1 code_audit：运行期 _ROOT=<root>、_FINDINGS/_LEDGER 重定向到 out（两个 run 不互踩），"
        "扫完立即还原全局，源文件未改动。",
        "lane2 pcs：importlib 加载 tools/penetrating_cross_scan.py，run_pipeline('tree:<root>')；"
        "步骤锁/钩子/交叉验证/遗漏补扫原样保留，TRACE 重定向到 out。",
        "findings 按 (file,line,cwe) 去重，sources 记录来源 lane；scan-code 阶段一律 kind='candidate'"
        "（No exploit, no report：verify-code 三查通过才升 'finding'）。",
        "pcs 的 security_pass 只把分诊=需人核 的 hit 收进候选；其余分诊类别保留在 "
        "lanes[1].coverage.security 里（可复核，不折叠）。",
        "code_audit 的 needs_human（分诊为需人核）同样映射成候选（confidence=low，"
        "howFound 注明分诊原因）；与 lane2 同 (file,line,cwe) 的条目去重合并。",
        "findings 文件读取用 utf-8-sig：PowerShell Set-Content -Encoding UTF8 写出的 BOM 不影响解析。",
        "覆盖率口径：files_eligible/files_scanned 来自 lane1（SCAN_EXT 地毯式）；"
        "lane2 的 units/hooked/coverage/full_coverage 在 lanes[1].coverage。",
        "回执原文落盘：%s" % (out_dir / "scan-code.receipt.json"),
        "code_audit findings 原文：%s" % (out_dir / "code_audit_findings.json"),
        "pcs 留痕：%s" % (out_dir / "cross_scan_trace.jsonl"),
    ]


# ── action: scan-code ─────────────────────────────────────────────────
def _do_scan(args) -> int:
    if not args.root:
        return _emit(_fail("scan-code", "needs_input", "缺 --root（目标目录绝对路径）"), 2)
    if not args.out:
        return _emit(_fail("scan-code", "needs_input", "缺 --out（输出目录）"), 2)
    root = _resolve_root(args.root)
    if not root.is_dir():
        return _emit(_fail("scan-code", "needs_input", "目标目录不存在：%s" % root), 2)
    out_dir = _resolve_out(args.out)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _emit(_fail("scan-code", "needs_dependency", "无法创建 out 目录：%s" % exc), 2)
    try:
        timeout_s = float(args.timeout if args.timeout is not None else 240)
    except (TypeError, ValueError):
        timeout_s = 240.0
    if timeout_s < 5:
        timeout_s = 5.0

    log("scan-code 开始：root=%s out=%s timeout=%ss" % (root, out_dir, timeout_s))
    lane1, f1, cov1 = _lane_code_audit(root, out_dir, timeout_s)
    log("lane code_audit：ok=%s ms=%s findings=%s 错误=%s"
        % (lane1.get("ok"), lane1.get("ms"),
           (lane1.get("coverage") or {}).get("findings"), lane1.get("error") or "-"))
    lane2, f2, pcs_rep = _lane_pcs(root, out_dir, timeout_s)
    cov_sec = (lane2.get("coverage") or {}).get("security") or {}
    log("lane pcs：ok=%s ms=%s units=%s hooked=%s security_flagged=%s 错误=%s"
        % (lane2.get("ok"), lane2.get("ms"),
           (lane2.get("coverage") or {}).get("units"),
           (lane2.get("coverage") or {}).get("hooked"),
           cov_sec.get("flagged"), lane2.get("error") or "-"))

    findings = _merge_findings(f1, f2)
    coverage = _assemble_coverage(lane1, cov1, lane2, pcs_rep)
    lanes_ok = bool(lane1.get("ok")) and bool(lane2.get("ok"))
    errors = [str(l.get("error")) for l in (lane1, lane2) if l.get("error")]
    receipt = {
        "ok": lanes_ok,
        "status": "ok" if lanes_ok else "failed",
        "action": "scan-code",
        "root": str(root),
        "lanes": [lane1, lane2],
        "findings": findings,
        "coverage": coverage,
        "notes": _scan_notes(out_dir),
        "error": ("；".join(errors) if errors else None),
    }
    try:
        _write_json_atomic(out_dir / "scan-code.receipt.json", receipt)
    except Exception as exc:                                # noqa: BLE001
        log("回执落盘失败（不影响 stdout 回执）：%s" % exc)
        receipt["notes"].append("回执落盘失败：%s" % exc)
    log("scan-code 完成：findings=%d coverage.complete=%s unread=%d"
        % (len(findings), coverage["complete"], len(coverage["unread"])))
    return _emit(receipt, 0 if receipt["ok"] else 1)


# ── action: verify-code ───────────────────────────────────────────────
def _load_findings_file(path: str) -> list:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT / p
    if not p.is_file():
        raise FileNotFoundError("findings 文件不存在：%s" % p)
    # utf-8-sig：无 BOM 时行为等同 utf-8；带 BOM（PowerShell Set-Content -Encoding UTF8）也能读
    doc = json.loads(p.read_text(encoding="utf-8-sig"))
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for key in ("findings", "rows", "items"):
            val = doc.get(key)
            if isinstance(val, list):
                return val
    raise ValueError("findings 文件里找不到 findings 数组（顶层应是 list，或 dict 含 findings/rows）")


def _verify_one(root: Path, f: dict) -> dict:
    fid = str(f.get("id") or "")
    raw_file = str(f.get("file") or "")
    p = Path(raw_file)
    if not p.is_absolute():
        p = root / raw_file
    ev = f.get("evidence") or {}
    line_no = int(f.get("line") or 0)
    reads = []

    exists = p.is_file()
    text = ""
    sha = ""
    if exists:
        try:
            sha = _sha256_file(p)
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            exists = False
            text = ""
            reads.append({"check": "read", "ok": False,
                          "detail": "文件读取失败：%s" % exc})
    if not exists and not reads:
        reads.append({"check": "read", "ok": False, "detail": "文件不存在：%s" % p})

    # 第 1 查：文件 sha256
    want_sha = str(ev.get("fileSha256") or "")
    if not exists:
        reads.append({"check": "fileSha256", "ok": False, "detail": "文件不在，无法算 sha256"})
    elif not want_sha:
        reads.append({"check": "fileSha256", "ok": False,
                      "detail": "finding 没有 evidence.fileSha256（无第一路证据）"})
    else:
        reads.append({"check": "fileSha256", "ok": sha == want_sha,
                      "detail": "一致" if sha == want_sha else "不一致（文件已改，行号/内容可能失效）"})

    # 第 2 查：行锚定 + 行文本
    lines = text.splitlines() if exists else []
    want_line = str(ev.get("lineText") or "")
    if not exists:
        reads.append({"check": "lineText", "ok": False, "detail": "文件不在，无法行锚定"})
    elif line_no < 1 or line_no > len(lines):
        reads.append({"check": "lineText", "ok": False,
                      "detail": "行号超出文件长度（%d 行）" % len(lines)})
    else:
        actual = lines[line_no - 1].strip()
        if not want_line:
            reads.append({"check": "lineText", "ok": False,
                          "detail": "finding 没有 evidence.lineText"})
        else:
            same = actual == want_line.strip()
            reads.append({"check": "lineText", "ok": same,
                          "detail": "一致" if same else "该行内容与扫描时不一致"})

    # 第 3 查：snippet 字面搜索（与正则/行号无关的独立读法）
    snippet = str(f.get("snippet") or "").strip()
    if not exists:
        reads.append({"check": "snippetLiteral", "ok": False, "detail": "文件不在，无法字面搜索"})
    elif not snippet:
        reads.append({"check": "snippetLiteral", "ok": False, "detail": "没有 snippet 可复核"})
    else:
        hit = snippet[:40] in text
        if not hit and len(snippet) > 40:
            hit = snippet in text
        reads.append({"check": "snippetLiteral", "ok": bool(hit),
                      "detail": "字面复现" if hit else "字面搜索没复现（片段已不在文件里）"})

    verified = all(r.get("ok") for r in reads)
    bad = [str(r.get("detail")) for r in reads if not r.get("ok")]
    verdict = ("三查都过：文件 sha256 + 行文本 + snippet 字面搜索"
               if verified else "未通过：" + "；".join(bad))
    return {"id": fid, "verified": bool(verified), "verdict": verdict, "reads": reads,
            "kind": "finding" if verified else "candidate"}


def _do_verify(args) -> int:
    if not args.root:
        return _emit(_fail("verify-code", "needs_input", "缺 --root"), 2)
    if not args.findings:
        return _emit(_fail("verify-code", "needs_input", "缺 --findings（scan-code 回执 JSON）"), 2)
    root = _resolve_root(args.root)
    if not root.is_dir():
        return _emit(_fail("verify-code", "needs_input", "目录不存在：%s" % root), 2)
    try:
        rows = _load_findings_file(args.findings)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit(_fail("verify-code", "needs_input", "findings 无法解析：%s" % exc), 2)

    results = [_verify_one(root, f) for f in rows]
    verified = sum(1 for r in results if r["verified"])
    receipt = {
        "ok": True,
        "status": "ok",
        "action": "verify-code",
        "root": str(root),
        "counts": {"total": len(results), "verified": verified,
                   "unverified": len(results) - verified},
        "findings": results,
        "notes": [
            "第二路读法三查：文件 sha256 / 行锚定+行文本 / snippet 字面搜索；三查都过才算 verified。",
            "未 verified 的条目按 No exploit, no report 只能留在 candidates，不得生成可提交报告。",
            "文件被改动（sha 不一致）⇒ 先重跑 scan-code 拿新行号与 sha，再验一次。",
        ],
    }
    log("verify-code：total=%d verified=%d" % (len(results), verified))
    return _emit(receipt, 0)


# ── action: enrich ────────────────────────────────────────────────────
def _do_enrich(args) -> int:
    if not args.findings:
        return _emit(_fail("enrich", "needs_input", "缺 --findings"), 2)
    try:
        rows = _load_findings_file(args.findings)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit(_fail("enrich", "needs_input", "findings 无法解析：%s" % exc), 2)
    try:
        from gbt_allinone import bounty_core as BC
    except Exception as exc:                                # noqa: BLE001
        return _emit(_fail("enrich", "needs_dependency",
                           "gbt_allinone.bounty_core 不可导入：%s: %s"
                           % (type(exc).__name__, exc)), 2)

    enriched = []
    for f in rows:
        item = dict(f)
        sev = str(f.get("severity") or "medium").lower()
        vector = BC.default_vector(sev)
        calc = BC.cvss3(vector)
        if calc.get("ok"):
            item["cvss"] = {"score": calc.get("base_score"),
                            "vector": calc.get("vector"),
                            "severity": calc.get("severity")}
        else:
            item["cvss"] = {"score": None, "vector": vector, "severity": sev,
                            "error": calc.get("reason")}
        info = BC.cwe_info(f.get("cwe") or "")
        item["cweInfo"] = {"name": info.get("name"), "fix": info.get("fix")}
        enriched.append(item)

    receipt = {
        "ok": True,
        "status": "ok",
        "action": "enrich",
        "counts": {"total": len(enriched)},
        "findings": enriched,
        "notes": [
            "cvss 向量按 severity 取 bounty_core.default_vector（不是逐条人工定向量）；"
            "要精确环境分/时间分请手工改 vector 后重算。",
            "cweInfo 来自 bounty_core.CWE 表；未收录的 CWE 给「未收录」+ 通用修复原则。",
        ],
    }
    log("enrich：total=%d" % len(enriched))
    return _emit(receipt, 0)


# ── action: selfcheck ─────────────────────────────────────────────────
def _do_selfcheck(args) -> int:
    pyembed = (ROOT / "pyembed" / "python.exe")
    try:
        is_pyembed = Path(sys.executable).resolve() == pyembed.resolve()
    except OSError:
        is_pyembed = False
    modules = {}

    try:
        from gbt_allinone.tools import code_audit as ca
        modules["gbt_allinone.tools.code_audit"] = {
            "ok": True, "rules": [r["rule"] for r in ca.RULES],
            "path": str(Path(ca.__file__).resolve()),
        }
    except Exception as exc:                                # noqa: BLE001
        modules["gbt_allinone.tools.code_audit"] = {
            "ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    try:
        from gbt_allinone import bounty_core as bc
        modules["gbt_allinone.bounty_core"] = {
            "ok": True, "cwe_count": len(getattr(bc, "CWE", {}) or {}),
            "defaults": {s: bc.default_vector(s) for s in ("critical", "high", "medium", "low")},
        }
    except Exception as exc:                                # noqa: BLE001
        modules["gbt_allinone.bounty_core"] = {
            "ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    pcs_info = {"ok": False}
    try:
        pcs = _load_pcs(None)
        pcs_info = {
            "ok": True,
            "path": str(PCS_PATH),
            "has": [n for n in ("decompose", "_unit_payload", "run_pipeline", "security_pass")
                    if hasattr(pcs, n)],
            "steps": list(getattr(pcs, "STEPS", []) or []),
            "targets": list(getattr(pcs, "status", lambda: {})().get("targets") or []),
        }
    except Exception as exc:                                # noqa: BLE001
        pcs_info = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    modules["tools/penetrating_cross_scan.py"] = pcs_info
    modules_ok = all(bool(m.get("ok")) for m in modules.values())
    receipt = {
        "ok": bool(modules_ok),
        "status": "ok" if modules_ok else "needs_dependency",
        "action": "selfcheck",
        "python": {"version": platform.python_version(), "full": sys.version.splitlines()[0],
                   "executable": sys.executable, "platform": platform.platform()},
        "pyembed": {"ok": bool(is_pyembed), "expected": str(pyembed),
                    "actual": sys.executable,
                    "note": "跑仓内 python 一律用 pyembed（embeddable：-m/PYTHONPATH 失效）"},
        "gbt_root": str(ROOT),
        "modules": modules,
        "capabilities": {
            "actions": ["scan-code", "verify-code", "enrich", "selfcheck"],
            "lanes": ["code_audit", "pcs"],
            "targets": ["tree:<目录>（绝对路径=任意目录；相对路径=仓内相对 ROOT）"],
            "finding_kind": ["candidate", "finding"],
            "stdout": "只输出一个 JSON；日志走 stderr",
        },
    }
    if not is_pyembed:
        log("警告：当前解释器不是仓内 pyembed（%s）；仓库口径要求用 pyembed 跑。" % sys.executable)
        receipt["notes"] = ["当前解释器不是仓内 pyembed，结果可能缺依赖；请用 pyembed 重跑。"]
    return _emit(receipt, 0 if receipt["ok"] else 1)


# ── CLI ───────────────────────────────────────────────────────────────
class _UsageError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _build_parser() -> _Parser:
    p = _Parser(prog="bounty_engine.py", description="GBT 赏金引擎桥（code_audit + 穿透式交叉扫描）")
    p.add_argument("--action", required=True,
                   choices=["scan-code", "verify-code", "enrich", "selfcheck"])
    p.add_argument("--root", default=None, help="scan-code/verify-code 的目标目录（推荐绝对路径）")
    p.add_argument("--out", default=None, help="scan-code 的输出目录（findings/台账/回执都落这里）")
    p.add_argument("--findings", default=None, help="verify-code/enrich 的 findings JSON")
    p.add_argument("--timeout", type=float, default=240.0, help="单 lane 超时秒数（默认 240）")
    return p


def _fail(action, status: str, error: str, notes=None) -> dict:
    return {"ok": False, "status": status, "action": action,
            "error": str(error), "notes": notes or []}


def _emit(receipt: dict, code: int = 0) -> int:
    """stdout 的唯一出口：保证只打一个 JSON。"""
    try:
        sys.stdout.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    except (TypeError, ValueError) as exc:
        log("回执不可序列化（%s），降级为 ensure_ascii=True" % exc)
        sys.stdout.write(json.dumps(receipt, ensure_ascii=True) + "\n")
    sys.stdout.flush()
    return int(code)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except _UsageError as exc:
        return _emit(_fail(None, "needs_input", "参数不合法：%s" % exc,
                           ["用法见 tools/bounty_engine.py 模块 docstring"]), 2)
    handlers = {
        "scan-code": _do_scan,
        "verify-code": _do_verify,
        "enrich": _do_enrich,
        "selfcheck": _do_selfcheck,
    }
    try:
        return handlers[args.action](args)
    except Exception as exc:                                # noqa: BLE001 - 任何异常都折成一个 failed 回执
        log(traceback.format_exc())
        return _emit(_fail(args.action, "failed", "%s: %s" % (type(exc).__name__, exc)), 1)


if __name__ == "__main__":
    sys.exit(main())
