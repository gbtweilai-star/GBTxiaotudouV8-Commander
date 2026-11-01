# gbt-capability: experience_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""experience_forge — 成长闭环：**外部验证通过才准固化**。

主人 2026-11-01 的判据（转述）：
  · “跑通”不能由模型自己说；必须有外部验证器（测试/编译/lint/真浏览器/运行时）；
  · “固化”不写权重；固化成 **可检索记忆** / **可调用工具** / **验证规则**；
  · 先有验证器和记忆层，闭环才成立。

本件把这句话落成唯一的入口：
  record  —— 只收**带外部验证证据**的经验（cmd + exit_code=0 + evidence 路径/摘要），
             缺验证或 exit_code≠0 一律拒（needs_verify），不许把幻觉存成经验；
  query   —— 按问题/标签检索（问题→尝试→验证→最终方案）；
  promote —— 把已验条目升成 rule（验证规则清单）或 tool（可调用模板），调用是确定性的；
  verify  —— 复核库本身：每条必须有 verify 证据、id 唯一、JSON 可读；
  status / where。

诚实边界：
  · 本件不执行任意历史命令（verify 只做库完整性校验，不重放 cmd）；
  · 不写权重、不训练；只写 state/experience_forge/（可被 memory_manager 之后索引）；
  · “验证证据”可以是 tests/final_check/deep_audit 的**产物路径 + 退出码**；没有证据就不收。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = ROOT / "state" / "experience_forge"
DEFAULT_MIRROR = ROOT / "state" / "mirror" / "experience_forge.jsonl"

STATUS = {
    "cap": "experience_forge", "tier": "native", "domain": "mind",
    "ops": ["status", "record", "query", "show", "promote", "index", "mirror", "mirror_status",
            "export_tests", "verify", "where"],
    "store": str(DEFAULT_STORE),
    "mirror_default": str(DEFAULT_MIRROR),
    "verifiers": ["tests/（pytest 兼容脚本）", "tools/codex-scripts/final-check.py",
                  "cap_self verify", "taste_guard deep_audit", "two-way-sync verify"],
    "not_implemented": ["把 export_tests 生成的测试自动接进统一测试 runner",
                        "自动重放历史验证命令（安全考虑只校验证据，不执行）"],
}


def _store(payload=None) -> Path:
    payload = payload or {}
    p = payload.get("store") or os.environ.get("GBT_EXPERIENCE_STORE") or str(DEFAULT_STORE)
    return Path(p).expanduser().resolve()


def _paths(store: Path):
    store.mkdir(parents=True, exist_ok=True)
    return store / "entries.jsonl", store / "rules.json", store / "tools.json"


def _read_jsonl(p: Path) -> list:
    out = []
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except FileNotFoundError:
        return []
    except Exception:  # noqa: BLE001
        return out
    return out


def _read_list(p: Path) -> list:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:  # noqa: BLE001
        return []


def _write_list(p: Path, rows: list):
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def _norm(text) -> str:
    return " ".join(str(text or "").split()).strip()


def _tokens(text) -> set:
    s = _norm(text).lower()
    # 中文按 2 字 bigram + 英文词；简单、可解释
    toks = set(re.findall(r"[a-z0-9_\-]{2,}", s))
    ch = re.sub(r"[^\u4e00-\u9fff]", "", s)
    toks |= {ch[i:i + 2] for i in range(max(0, len(ch) - 1))}
    return toks


def _valid_verify(v) -> tuple:
    if not isinstance(v, dict):
        return False, "verify 必须是对象：{cmd, exit_code, evidence}"
    cmd = _norm(v.get("cmd"))
    ev = v.get("evidence")
    try:
        code = int(v.get("exit_code"))
    except (TypeError, ValueError):
        return False, "verify.exit_code 必须是整数"
    if not cmd:
        return False, "verify.cmd 缺失（必须写清用什么外部验证器）"
    if code != 0:
        return False, "verify.exit_code=%s≠0：没跑通就不许固化" % code
    if not ev:
        return False, "verify.evidence 缺失（产物路径/测试名/读数摘要）"
    return True, ""


def _record(payload):
    ok, why = _valid_verify(payload.get("verify"))
    if not ok:
        return {"ok": False, "status": "needs_verify", "error": why, "fail_closed": True}
    problem = _norm(payload.get("problem"))
    solution = _norm(payload.get("solution"))
    if len(problem) < 6 or len(solution) < 4:
        return {"ok": False, "status": "needs_input", "error": "problem（≥6 字）与 solution（≥4 字）必填"}
    store = _store(payload)
    ep, rp, tp = _paths(store)
    eid = hashlib.sha1((problem + json.dumps(payload.get("verify"), ensure_ascii=False)).encode("utf-8")).hexdigest()[:12]
    entry = {
        "id": eid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "problem": problem, "attempts": payload.get("attempts") or [],
        "solution": solution, "verify": payload["verify"],
        "files": payload.get("files") or [], "tags": payload.get("tags") or [],
        "kind": payload.get("kind") or "fix",
    }
    rows = _read_jsonl(ep)
    if any(r.get("id") == eid for r in rows):
        return {"ok": True, "status": "duplicate", "id": eid, "note": "同问题+同验证已存在，不重复写"}
    try:
        with ep.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    out = {"ok": True, "status": "recorded", "id": eid, "entry": entry, "store": str(store)}
    if payload.get("auto_mirror"):
        out["mirror"] = _mirror(payload)
    return out


def _query(payload):
    q = _norm(payload.get("query") or payload.get("q") or "")
    if not q:
        return {"ok": False, "status": "needs_input", "error": "给 query"}
    store = _store(payload)
    ep, _, _ = _paths(store)
    rows = _read_jsonl(ep)
    qt = _tokens(q)
    scored = []
    for r in rows:
        blob = " ".join([r.get("problem", ""), " ".join(map(str, r.get("attempts") or [])),
                         r.get("solution", ""), " ".join(map(str, r.get("tags") or []))])
        st = _tokens(blob)
        score = len(qt & st) / max(1, len(qt))
        if score > 0:
            scored.append((round(score, 3), r))
    scored.sort(key=lambda x: (-x[0], x[1].get("at", "")), reverse=False)
    top = scored[: int(payload.get("limit") or 8)]
    return {"ok": True, "status": "ok", "query": q, "count": len(top),
            "hits": [{"score": s, **r} for s, r in top], "store": str(store)}


def _promote(payload):
    store = _store(payload)
    ep, rp, tp = _paths(store)
    rows = _read_jsonl(ep)
    eid = _norm(payload.get("id"))
    row = next((r for r in rows if r.get("id") == eid), None)
    if not row:
        return {"ok": False, "status": "not_found", "error": "先 record 一条已验经验"}
    kind = str(payload.get("kind") or "rule").lower()
    name = _norm(payload.get("name") or row["problem"][:40])
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    if kind == "rule":
        check = _norm(payload.get("check") or row["verify"].get("cmd"))
        item = {"name": name, "check": check, "from": eid,
                "checks": checks, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        items = _read_list(rp)
        items = [x for x in items if x.get("name") != name] + [item]
        _write_list(rp, items)
        return {"ok": True, "status": "rule_promoted", "rule": item, "rules": str(rp)}
    if kind == "tool":
        template = _norm(payload.get("template") or row["verify"].get("cmd"))
        item = {"name": name, "template": template, "from": eid, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        items = _read_list(tp)
        items = [x for x in items if x.get("name") != name] + [item]
        _write_list(tp, items)
        return {"ok": True, "status": "tool_promoted", "tool": item, "tools": str(tp)}
    return {"ok": False, "status": "bad_kind", "error": "kind 只能是 rule / tool"}


def _export_tests(payload):
    """把 rules.json 里的结构化 checks 自动生成一个可执行的回归测试文件。"""
    store = _store(payload)
    ep, rp, tp = _paths(store)
    rules = _read_list(rp)
    out = Path(payload.get("out") or (ROOT / "tests" / "test_experience_generated.py"))
    lines = [
        "# gbt-capability: experience_forge",
        "# AUTO-GENERATED by experience_forge.export_tests — 改规则请改 rules.json 后重生成，不要手改本文件。",
        '"""自动生成：rules.json → 可执行断言。"""',
        "from __future__ import annotations",
        "import re",
        "from pathlib import Path",
        "",
        "ROOT = Path(__file__).resolve().parents[1]",
        "FAILED = []",
        "",
        "def check(name, cond, detail=\"\"):",
        "    print((\"  ok   \" if cond else \"  FAIL \") + name + (\"\" if cond else \"  \" + str(detail)))",
        "    if not cond:",
        "        FAILED.append(name)",
        "",
        "def main():",
    ]
    ncheck = 0
    for rule in rules:
        rname = _norm(rule.get("name"))
        checks = rule.get("checks") if isinstance(rule.get("checks"), list) else []
        lines.append("    # rule: %s" % rname.replace("\n", " "))
        if not checks:
            lines.append("    # 该规则没写结构化 checks（只有 cmd），生成测试先略过")
            continue
        for c in checks:
            path = _norm(c.get("path"))
            if not path:
                continue
            lines.append("    p = ROOT / %r" % path)
            lines.append("    check(%r, p.is_file(), str(p))" % ("存在 " + path))
            if c.get("contains") is not None:
                lines.append("    check(%r, %r in p.read_text(encoding='utf-8', errors='replace'))"
                             % ("包含 " + str(c["contains"])[:40], c["contains"]))
                ncheck += 1
            if c.get("not_contains") is not None:
                lines.append("    check(%r, %r not in p.read_text(encoding='utf-8', errors='replace'))"
                             % ("不含 " + str(c["not_contains"])[:40], c["not_contains"]))
                ncheck += 1
            if c.get("regex"):
                lines.append("    check(%r, re.search(%r, p.read_text(encoding='utf-8', errors='replace')) is not None)"
                             % ("匹配 " + str(c["regex"])[:40], c["regex"]))
                ncheck += 1
            if isinstance(c.get("min_count"), dict):
                sub = c["min_count"].get("sub", "")
                n = int(c["min_count"].get("n") or 1)
                lines.append("    check(%r, p.read_text(encoding='utf-8', errors='replace').count(%r) >= %d)"
                             % ("至少 %d 个 %s" % (n, sub), sub, n))
                ncheck += 1
    lines += ["", "    if FAILED:", "        print(\"FAILED %d: %s\" % (len(FAILED), FAILED))",
              "        return 1", "    print(\"ALL PASS\")", "    return 0", "",
              "if __name__ == \"__main__\":", "    raise SystemExit(main())", ""]
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"ok": True, "status": "exported", "out": str(out), "rules": len(rules),
            "checks": ncheck, "note": "从 rules.json 的 checks 生成；没有 checks 的规则会显式写明跳过"}


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _mirror(payload):
    """显式镜像能力：把规范库导出一份**派生扁平副本**（可被只认顶层 jsonl 的外部工具读）。

    唯一真相仍是 entries.jsonl；默认落 state/mirror/（不进 FTS，避免重复命中）。
    传 out 可指定路径（兼容旧位置）；若落在 memory_manager 会扫的 state/*.jsonl 顶层，
    返回里会明确标 indexed_by_fts=True，提醒会重复命中。
    """
    store = _store(payload)
    ep, rp, tp = _paths(store)
    rows = _read_jsonl(ep)
    flat = Path(payload.get("out") or DEFAULT_MIRROR).expanduser().resolve()
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")
    sha = _sha_bytes(body.encode("utf-8"))
    try:
        flat.parent.mkdir(parents=True, exist_ok=True)
        flat.write_bytes(body.encode("utf-8"))
        meta = {"source": str(ep), "mirror": str(flat), "entries": len(rows), "sha256": sha,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "derived": True,
                "indexed_by_fts": flat.parent == ROOT / "state"}
        flat.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"ok": True, "status": "mirrored", "mirror": str(flat), "entries": len(rows), "sha256": sha,
            "source": str(ep), "derived": True, "indexed_by_fts": meta["indexed_by_fts"],
            "note": "派生副本，不是真相；真相仍是 entries.jsonl"}


def _mirror_status(payload):
    store = _store(payload)
    ep, rp, tp = _paths(store)
    rows = _read_jsonl(ep)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")
    sha = _sha_bytes(body.encode("utf-8"))
    flat = Path(payload.get("out") or DEFAULT_MIRROR).expanduser().resolve()
    meta_p = flat.with_suffix(".meta.json")
    if not flat.is_file():
        return {"ok": True, "status": "missing", "mirror": str(flat), "entries": len(rows),
                "in_sync": False, "note": "还没镜像；op=mirror 生成"}
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        meta = {}
    current = _sha_bytes(flat.read_bytes())
    in_sync = (current == sha) and int(meta.get("entries") or -1) == len(rows)
    return {"ok": True, "status": "ok" if in_sync else "stale", "mirror": str(flat),
            "entries": len(rows), "mirror_sha256": current, "source_sha256": sha,
            "in_sync": in_sync, "meta": meta,
            "note": "in_sync=False ⇒ 规范库变了，镜像过期；重跑 op=mirror"}


def _index(payload):
    """规范库直接进 FTS：不再写镜像文件，memory_manager 已索引 state/experience_forge/*.jsonl。"""
    store = _store(payload)
    ep, rp, tp = _paths(store)
    rows = _read_jsonl(ep)
    try:
        from ..tools import memory_manager as _mm
        idx = _mm.run_op("index")
        found = _mm.run_op("find", q="experience_forge", limit=5) if idx.get("ok") else {}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "memory_manager_unavailable",
                "error": "%s: %s" % (type(e).__name__, str(e)[:160]), "entries": len(rows)}
    return {"ok": bool(idx.get("ok")), "status": idx.get("status") or ("ok" if idx.get("ok") else "failed"),
            "entries": len(rows), "store": str(ep), "index": idx, "find": found,
            "note": "唯一真相 = entries.jsonl；memory_manager 直接索引它，不写镜像"}


def _verify(payload):
    store = _store(payload)
    ep, rp, tp = _paths(store)
    rows = _read_jsonl(ep)
    bad = []
    seen = set()
    for r in rows:
        if r.get("id") in seen:
            bad.append({"id": r.get("id"), "why": "duplicate id"})
        seen.add(r.get("id"))
        ok, why = _valid_verify(r.get("verify"))
        if not ok:
            bad.append({"id": r.get("id"), "why": why})
    return {"ok": not bad, "status": "ok" if not bad else "broken", "entries": len(rows),
            "rules": len(_read_list(rp)), "tools": len(_read_list(tp)),
            "bad": bad, "store": str(store),
            "note": "只校验库与证据字段，不重放任意历史命令"}


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        store = _store(kw)
        ep, rp, tp = _paths(store)
        try:
            mir = _mirror_status(kw)
        except Exception:  # noqa: BLE001
            mir = {"ok": False, "status": "unavailable"}
        return {"ok": True, "op": "status", **STATUS,
                "entries": len(_read_jsonl(ep)), "rules": len(_read_list(rp)),
                "tools": len(_read_list(tp)), "actual_store": str(store), "mirror": mir}
    if op == "where":
        return {"ok": True, "op": "where", **STATUS, "module": "gbt_allinone/tentacle/experience_forge.py",
                "example": "run_task('experience_forge', {'op':'record','problem':'...','attempts':[...],'solution':'...','verify':{'cmd':'py tests/x.py','exit_code':0,'evidence':'...'}})"}
    if op == "record":
        return _record(kw)
    if op in ("query", "recall"):
        return _query(kw)
    if op == "show":
        store = _store(kw); ep, _, _ = _paths(store)
        return {"ok": True, "entries": _read_jsonl(ep), "store": str(store)}
    if op == "promote":
        return _promote(kw)
    if op == "index":
        return _index(kw)
    if op == "mirror":
        return _mirror(kw)
    if op == "mirror_status":
        return _mirror_status(kw)
    if op == "export_tests":
        return _export_tests(kw)
    if op == "verify":
        return _verify(kw)
    return {"ok": False, "op": op, "status": "unknown_op", "error": "未知 op：%s" % op,
            "available": STATUS["ops"], "fail_closed": True}
