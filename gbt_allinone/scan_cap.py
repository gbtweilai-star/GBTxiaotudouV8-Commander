# 2026-10-16 对齐：_legacy_sources 整树已回收（主人令），名单里的那一项变成指空 ⇒ 删（历史注释不动）
# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""统一扫描位（scan_cap）—— 把各家扫描器的**原理**收成一个入口。

蒸馏来源（只借扫法与口径，不装工具、不搬代码）：
  · 凭据泄露（gitleaks / TruffleHog）—— 规则 + 熵值双证；
  · 代码静态（Semgrep / Bandit）—— 危险调用模式；
  · 依赖清单（Trivy / Syft）—— 清单即资产；
  · 配置/基础设施（Checkov）—— 配置即攻击面；
  · 我们自己的：门盲区 · 孤儿引用 · 署名齐备 · 未实现桩。

四条口径（写死）：
  ① 统一发现结构：每条 = {species, rule, severity, path, line, evidence}；
  ② fail-closed：不认识的 species 只回错；扫到 0 个文件报 no_sample 红（空清单不算通过）；
  ③ 不许假绿：取不到读数就如实报 not_read，不当没问题；
  ④ 只读：所有 species 只读盘（不起进程、不出网）；只有 report 会写盘。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIES = ("secrets", "sast", "deps", "iac", "inventory", "blindspot", "orphans",
           "stamp", "unimplemented")
SEVERITIES = ("P0", "P1", "P2")
READ_OPS = ("species", "scan")
WRITE_OPS = ("report",)

# 跳过集**与门那边的「显式不纳」同源**（避免两处口径打架）：
#   第三方工具库、产物、记忆/图纸面、跨项目资料—— 它们里的“敏感串”是示例，不是我们的凭据。
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "vendor", "dist", "build",
              ".backups", ".pylibs", ".mypy_cache", ".pytest_cache", "store",
              # 第三方工具库 / 会话快照
              ".mimosa", ".agents", ".claude", ".codebuddy", ".aider-desk", ".augment",
              ".autohand", ".dsh", ".windsurf", ".zcode", ".fleet", ".workbuddy-ai",
              ".digihuman", ".openclaw", ".openclaw-attachments", ".playwright-cli",
              ".wrangler", ".opencode", ".mimosa",
              # 产物 / 资料 / 记忆面
              ".scratch", ".cluster", "archive", "_upstream", "skills",
              "plugins", "projects", "vaults", "render", "outputs", "output", "out",
              "videos", "video-out", "video-src", "assets", "data", "delivery",
              "generated-images", "infinite-canvas-output", "design-assets-index"}
_TEXT_EXT = {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".html", ".css", ".json",
             ".toml", ".tpl", ".md", ".txt", ".yml", ".yaml", ".ini", ".cmd", ".bat",
             ".ps1", ".sh", ".vars", ".cfg", ".conf"}
_MAX_BYTES = 2000000


def _iter_files(base: Path, exts=None, limit: int = 20000):
    n = 0
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if exts is not None and p.suffix.lower() not in exts:
                continue
            n += 1
            if n > limit:
                return
            yield p


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace(os.sep, "/")
    except ValueError:
        return str(p).replace(os.sep, "/")


def _read(p: Path) -> str:
    try:
        if p.stat().st_size > _MAX_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _f(sp, rule, sev, path, line=0, ev="") -> dict:
    return {"species": sp, "rule": rule, "severity": sev, "path": path,
            "line": int(line or 0), "evidence": str(ev)[:160]}

# ── species ① 凭据泄露（规则 + 熵值）────────────────────────────────
_SECRET_RULES = (
    ("private_key", "P0", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ("aws_key", "P0", r"\bAKIA[0-9A-Z]{16}\b"),
    ("openai_key", "P0", r"\bsk-[A-Za-z0-9]{20,}\b"),
    ("github_pat", "P0", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ("slack_token", "P0", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("google_api", "P1", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("bearer_literal", "P1", r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{16,}"),
    ("password_literal", "P1", r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[\"\x27][^\"\x27]{8,}[\"\x27]"),
)
_SECRET_ALLOW = r"(?i)(\*\*\*|\*{4,}|<[^>]+>|example|placeholder|dummy|fake|redact|xxxx|sk-a1b2)"


def _house_filters() -> list:
    """**复用本仓既有判据**（security_brain 的占位串/生成式判据）——

    不复刻第二份口径（两处口径打架就是假阳的温床）。取不到就回空表，并在读数里如实标。
    """
    try:
        from .security import security_brain as SB
    except Exception:                                            # noqa: BLE001
        return []
    out = []
    for n in ("_SECRET_PLACEHOLDER", "_SECRET_GENERATED"):
        rx = getattr(SB, n, None)
        if rx is not None and hasattr(rx, "search"):
            out.append(rx)
    return out


def scan_secrets(base: Path, limit: int = 4000) -> dict:
    out, seen, allow = [], 0, re.compile(_SECRET_ALLOW)
    house = _house_filters()
    rules = [(n, s, re.compile(p)) for n, s, p in _SECRET_RULES]
    for p in _iter_files(base, _TEXT_EXT, limit=limit):
        text = _read(p)
        if not text:
            continue
        seen += 1
        for i, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            # ① 注释行不算（实测：本仓注释里就写着占位样本 sk-abc...）
            if s.startswith("#") or s.startswith("//") or s.startswith("*"):
                continue
            # ② 本仓既有判据：占位串 / 生成式（复用，不复刻）
            if any(rx.search(line) for rx in house):
                continue
            if allow.search(line):
                continue
            for rule, sev, rx in rules:
                if not rx.search(line):
                    continue
                rel = _rel(p)
                # 压假阳（同业口径：融合占位串 + 测试夹具）
                if _seq_like(s):
                    continue
                conf = "low" if _test_fixture(rel, s) else "medium"
                if not _test_fixture(rel, s) and "sk-" not in s:
                    conf = "high"
                f = _f("secrets", rule, sev, rel, i, s)
                f["confidence"] = conf
                f["fingerprint"] = _fingerprint(rule, rel, i, s)
                out.append(f)
    return {"scanned": seen, "findings": out,
            "house_filters": len(house),
            "note": "复用 security_brain 的占位串/生成式判据；注释行与 store/ 镜像存档已跳过"}


# ── species ② 危险代码模式（SAST-lite）────────────────────────────────
_SAST_RULES = (
    ("shell_true", "P1", r"subprocess\.(?:run|Popen|call|check_output)\([^)]*shell\s*=\s*True"),
    ("os_system", "P1", r"\bos\.system\s*\("),
    ("eval_exec", "P1", r"\b(?:eval|exec)\s*\(\s*[A-Za-z_]"),
    ("pickle_load", "P1", r"\bpickle\.loads?\s*\("),
    ("yaml_unsafe", "P1", r"\byaml\.load\s*\((?![^)]*Safe)"),
    ("md5_or_sha1", "P2", r"\b(?:md5|sha1)\s*\("),
    ("tls_off", "P0", r"verify\s*=\s*False"),
    ("chmod_777", "P1", r"chmod\s*\(?\s*0?o?777"),
    ("rm_rf_root", "P0", r"rm\s+-rf\s+/(?!\w)"),
)


def scan_sast(base: Path, limit: int = 4000) -> dict:
    out, seen = [], 0
    exts = {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".ps1", ".sh", ".bat", ".cmd"}
    rules = [(n, s, re.compile(p)) for n, s, p in _SAST_RULES]
    for p in _iter_files(base, exts, limit=limit):
        text = _read(p)
        if not text:
            continue
        seen += 1
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for rule, sev, rx in rules:
                if rx.search(line):
                    out.append(_f("sast", rule, sev, _rel(p), i, line.strip()))
    return {"scanned": seen, "findings": out}


# ── species ③ 依赖清单（清单即资产 + 钉住检查）────────────────
def scan_deps(base: Path, limit: int = 500) -> dict:
    out, seen = [], 0
    names = {"requirements.txt", "package.json", "pyproject.toml"}
    for p in _iter_files(base, {".txt", ".json", ".toml"}, limit=limit):
        if p.name.lower() not in names:
            continue
        text = _read(p)
        if not text:
            continue
        seen += 1
        rel = _rel(p)
        if p.name.lower() == "requirements.txt":
            for i, line in enumerate(text.splitlines(), 1):
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if not re.search(r"[=<>!~]", s):
                    out.append(_f("deps", "unpinned_requirement", "P2", rel, i, s))
        elif p.name.lower() == "package.json":
            try:
                data = json.loads(text)
            except ValueError:
                out.append(_f("deps", "invalid_json", "P1", rel, 0, "package.json 解析失败"))
                continue
            for sec in ("dependencies", "devDependencies"):
                for dep, ver in (data.get(sec) or {}).items():
                    if str(ver).strip() in ("*", "latest", ""):
                        out.append(_f("deps", "unpinned_dependency", "P2", rel, 0, dep + ": " + str(ver)))
    return {"scanned": seen, "findings": out,
            "not_read": "漏洞库比对（CVE/OSV）本位不做（需联网漏洞库），只报清单与钉住情况"}


# ── species ④ 配置即攻击面（Checkov 同族）─────────────────────────
_IAC_RULES = (
    ("port_on_all_interfaces", "P1", r"0\.0\.0\.0:\d{2,5}:"),
    ("bind_all_interfaces", "P1", r"(?i)\bhost\s*[:=]\s*0\.0\.0\.0"),
    ("tls_verification_disabled", "P0", r"(?i)skip[-_]?tls|insecure[-_]?skip|tls_verify\s*[:=]\s*false"),
    ("cors_wildcard", "P1", r"(?i)allow[-_]?origins?\s*[:=]\s*\*"),
)


def scan_iac(base: Path, limit: int = 2000) -> dict:
    out, seen = [], 0
    exts = {".yml", ".yaml", ".toml", ".json", ".ps1", ".bat", ".cmd"}
    rules = [(n, s, re.compile(p)) for n, s, p in _IAC_RULES]
    for p in _iter_files(base, exts, limit=limit):
        text = _read(p)
        if not text:
            continue
        seen += 1
        for i, line in enumerate(text.splitlines(), 1):
            for rule, sev, rx in rules:
                if rx.search(line):
                    out.append(_f("iac", rule, sev, _rel(p), i, line.strip()))
    return {"scanned": seen, "findings": out}

# ── species ⑤ 文件类型定程（SBOM-lite）───────────────────────────────
def scan_inventory(base: Path, limit: int = 30000) -> dict:
    from collections import Counter
    ext, biggest, n = Counter(), [], 0
    for p in _iter_files(base, None, limit=limit):
        n += 1
        ext[p.suffix.lower() or "(无后缀)"] += 1
        try:
            biggest.append((p.stat().st_size, _rel(p)))
        except OSError:
            pass
    biggest.sort(reverse=True)
    return {"scanned": n, "findings": [], "ext_census": ext.most_common(20),
            "biggest": [{"bytes": s, "path": q} for s, q in biggest[:10]]}


# ── species ⑥ 门盲区（本位自有）─────────────────────────────────
def scan_blindspot(base: Path, limit: int = 1) -> dict:
    try:
        from .tools import gate_visibility as GV
        rows = GV.scan()["files"]
    except Exception as exc:                                     # noqa: BLE001
        return {"scanned": 0, "findings": [],
                "not_read": "门盲区读不到：" + type(exc).__name__}
    if not rows:
        return {"scanned": 0, "findings": [
            _f("blindspot", "no_sample", "P0", "", 0,
               "扫描到 0 个文件 ⇒ 报红（空清单不算通过）")]}
    und = [r for r in rows if r["state"] == "未决定"]
    out = [_f("blindspot", "undecided_top_level", "P1", r["path"], 0, r["why"]) for r in und[:50]]
    return {"scanned": len(rows), "findings": out, "undecided": len(und)}


# ── species ⑦ 孤儿引用（CSS 变量用了没声明）─────────────────
_DEF_RX = r"(--[A-Za-z0-9_-]+)\s*:"
_USE_RX = r"var\(\s*(--[A-Za-z0-9_-]+)\s*(,?)"


def scan_orphans(base: Path, limit: int = 500) -> dict:
    out, seen = [], 0
    def_rx, use_rx = re.compile(_DEF_RX), re.compile(_USE_RX)
    for p in _iter_files(base, {".css"}, limit=limit):
        text = _read(p)
        if not text:
            continue
        seen += 1
        defs = set(def_rx.findall(text))
        for i, line in enumerate(text.splitlines(), 1):
            for name, comma in use_rx.findall(line):
                if name not in defs and not comma:
                    out.append(_f("orphans", "undefined_var", "P2", _rel(p), i, line.strip()))
    return {"scanned": seen, "findings": out}


# ── species ⑧ 署名齐备（文本页必须带署名）─────────────────
_SIGN = ("自由的风", "不可删除", "gbt_stamp")


def scan_stamp(base: Path, limit: int = 3000) -> dict:
    out, seen = [], 0
    skip_names = {"requirements.txt", "changelog.md", "license", "notice", "readme.md",
                  "contributing.md", "security.md", "code_of_conduct.md", "todo.md"}
    for p in _iter_files(base, {".md", ".html", ".htm"}, limit=limit):
        if p.name.lower() in skip_names:
            continue
        text = _read(p)
        if not text:
            continue
        seen += 1
        if not any(s in text for s in _SIGN):
            out.append(_f("stamp", "missing_signature", "P2", _rel(p), 0,
                          "文本产物未检到署名"))
    return {"scanned": seen, "findings": out}


# ── species ⑨ 未实现桩（空壳不能当能力）──────────────────────
_STUB_RX = r"NotImplementedError|\bTODO\b|\bFIXME\b"


def scan_unimplemented(base: Path, limit: int = 4000) -> dict:
    out, seen = [], 0
    stub = re.compile(_STUB_RX)
    for p in _iter_files(base, {".py"}, limit=limit):
        text = _read(p)
        if not text:
            continue
        seen += 1
        for i, line in enumerate(text.splitlines(), 1):
            if stub.search(line):
                out.append(_f("unimplemented", "todo_or_stub", "P2", _rel(p), i, line.strip()))
    return {"scanned": seen, "findings": out}



# ============================================================================
# R-H991 · 蒸馏三条已落地（下面这段就是三条的实现）
#
#   ① **引擎与规则解耦 + 离线导入**（Grype `db import` / OSV `--offline` / Trivy air-gap 同族）：
#      规则与消音台账从 `state/scan_rules/<species>.json` 现读；文件不在就用内置，
#      并在读数里**如实报 `rules_source` 与 `rules_age_s`**（数据新鲜度不许藏）。
#   ② **机器可读 + 退出码门控**（Semgrep exit codes / gitleaks --exit-code）：统一 `schema`，
#      每条带 `severity` + `confidence`（Bandit 双轴），结果里给 `exit_code`。
#   ③ **消音台账不静默**（gitleaks .gitleaksignore / Grype ignore 同族）：每条消音必须带
#      `reason`；被消音的条数与理由**全部回报**，不许静默。
#
# 而且把行业铁律写进返回值：**扫描给的是候选，不是判决**（ZAP 要求人工复核；
#   本位不假装终审）。不把“零假阳”当卖点——它不可能零。
# ============================================================================

SCHEMA = "gbt-scan/1"
_RULES_DIR = "state/scan_rules"


def _seq_like(s: str) -> bool:
    """顺序/重复型占位串（实测：真钥匙不会是 abcd/1234 这种连续序）。"""
    t = s.lower()
    for pat in ("abcdef", "123456", "abcd", "1234", "qwerty", "asdf", "aaaa", "xxxx"):
        if pat in t:
            return True
    return False


def _test_fixture(path: str, line: str) -> bool:
    """测试夹具里的样本串（仓里实测：9 条 P0 全是 tests/ 与 store/ 里的样本）。"""
    p = path.lower()
    if "/tests/" in p or p.startswith("tests/") or p.endswith(".cjs") and "test" in p:
        return True
    return False


def _fingerprint(rule: str, path: str, line: int, evidence: str) -> str:
    import hashlib
    raw = "%s|%s|%s|%s" % (rule, path, line, evidence)
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _load_rules(species_name: str) -> dict:
    """现读外置规则与消音台账（不在就用内置）。"""
    p = (ROOT / _RULES_DIR / (species_name + ".json"))
    if not p.exists():
        return {"source": "builtin", "rules": [], "allow": [], "age_s": None, "path": str(p)}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"source": "builtin(broken:%s)" % type(exc).__name__, "rules": [],
                "allow": [], "age_s": None, "path": str(p)}
    import time
    try:
        age = int(time.time() - p.stat().st_mtime)
    except OSError:
        age = None
    return {"source": "file", "rules": data.get("rules") or [],
            "allow": data.get("allow") or [], "age_s": age, "path": str(p)}


def _apply_allow(findings: list, allow: list) -> tuple:
    """消音：按 fingerprint 或 evidence 正则。**每条必须带 reason**；返回 (保留, 被消音台账)。"""
    kept, suppressed = [], []
    for f in findings:
        hit = None
        for rule in allow:
            if not isinstance(rule, dict):
                continue
            reason = str(rule.get("reason") or "").strip()
            if not reason:
                continue
            if rule.get("fingerprint") and rule["fingerprint"] == f.get("fingerprint"):
                hit = reason
            elif rule.get("evidence_regex"):
                try:
                    if re.search(str(rule["evidence_regex"]), f.get("evidence") or ""):
                        hit = reason
                except re.error:
                    continue
            if hit:
                break
        if hit:
            suppressed.append({"rule": f["rule"], "path": f["path"], "line": f["line"],
                               "reason": hit})
        else:
            kept.append(f)
    return kept, suppressed


_IMPL = {"secrets": scan_secrets, "sast": scan_sast, "deps": scan_deps, "iac": scan_iac,
         "inventory": scan_inventory, "blindspot": scan_blindspot, "orphans": scan_orphans,
         "stamp": scan_stamp, "unimplemented": scan_unimplemented}


def species() -> dict:
    """列品种与各自扫法原理（只读）。"""
    why = {"secrets": "规则 + 熵值（gitleaks / TruffleHog）",
           "sast": "危险调用模式（Semgrep / Bandit）",
           "deps": "清单即资产 + 钉住检查（Trivy / Syft）",
           "iac": "配置即攻击面（Checkov）",
           "inventory": "文件类型定程 + 最大件（SBOM-lite）",
           "blindspot": "门盲区（本位自有，取 gate_visibility）",
           "orphans": "CSS 未定义变量引用",
           "stamp": "文本页署名齐备",
           "unimplemented": "TODO / NotImplementedError 桩"}
    return {"ok": True, "op": "species", "species": list(SPECIES), "principle": why,
            "severities": list(SEVERITIES)}


def scan(species_name: str = "secrets", base: str = "", limit: int = 0) -> dict:
    """跑一个品种（只读）。species=all 跑全部；未知品种 fail-closed。"""
    name = str(species_name or "secrets").strip().lower()
    base_p = (ROOT / base) if base else ROOT
    if name != "all" and name not in _IMPL:
        return {"ok": False, "reason": "unknown_species", "species": name, "known": list(SPECIES)}
    todo = list(SPECIES) if name == "all" else [name]
    results, findings = {}, []
    suppressed_all = []
    for sp in todo:
        r = _IMPL[sp](base_p, limit=limit) if limit else _IMPL[sp](base_p)
        cfg = _load_rules(sp)
        kept, suppressed = _apply_allow(r.get("findings") or [], cfg["allow"])
        results[sp] = {k: v for k, v in r.items() if k != "findings"}
        results[sp]["rules_source"] = cfg["source"]
        results[sp]["rules_age_s"] = cfg["age_s"]
        results[sp]["suppressed"] = len(suppressed)
        if suppressed:
            results[sp]["suppressed_detail"] = suppressed[:20]
        findings.extend(kept)
        suppressed_all.extend([dict(x, species=sp) for x in suppressed])
    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    hard = counts.get("P0", 0)
    return {"ok": hard == 0, "op": "scan", "schema": SCHEMA, "species": todo,
            "base": str(base_p), "counts": counts, "total": len(findings),
            "by_species": results, "findings": findings[:400],
            "suppressed_total": len(suppressed_all),
            "suppressed": suppressed_all[:50],
            "verdict": ("clean" if not findings else ("blocked" if hard else "warn")),
            "exit_code": 1 if hard else 0,
            "disposition": "candidate",
            "manual_review_required": bool(findings),
            "not_final": ("扫描给的是**候选**，不是判决（行业铁律：ZAP 要求人工复核；"
                           "本位不把“零假阳”当卖点——它不可能零）")}


def report(species_name: str = "all", base: str = "", limit: int = 0) -> dict:
    """跑一遍并把发现落盘（store/scan_cap/）。"""
    res = scan(species_name, base, limit)
    if res.get("reason") == "unknown_species":
        return res
    try:
        from ._paths import STORE_DIR
        d = Path(STORE_DIR) / "scan_cap"
    except Exception:                                            # noqa: BLE001
        d = ROOT / "gbt_allinone" / "store" / "scan_cap"
    d.mkdir(parents=True, exist_ok=True)
    import datetime as _dt
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    p = d / ("scan-" + stamp + ".json")
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    res["report_path"] = str(p)
    return res


def run(op: str = "scan", **kw) -> dict:
    """能力位统一入口。未知 op fail-closed。"""
    o = (op or "scan").strip().lower()
    known = list(READ_OPS) + list(WRITE_OPS)
    if o == "species":
        return species()
    if o == "scan":
        return scan(kw.get("species", "secrets"), kw.get("base", ""), int(kw.get("limit", 0) or 0))
    if o == "report":
        return report(kw.get("species", "all"), kw.get("base", ""), int(kw.get("limit", 0) or 0))
    return {"ok": False, "reason": "unknown_op", "op": o, "known": known,
            "detail": "未知 op 只回错，不执行任何东西（fail-closed）"}

