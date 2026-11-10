#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_bounty_engine.py · 赏金引擎桥端到端自测（真跑 CLI，不 mock）

判据（每条都要能指回一次真实命令输出）：
  1. `--action selfcheck`：仓内 pyembed 跑、两模块可导入、PCS 可加载；
  2. `--action scan-code`：stdout **只有一个 JSON**；两条 lane 都 ok；
     coverage 结构齐全（complete/files_eligible/files_scanned/rate/truncated/unread）、
     真的扫到临时目录里的文件、findings 含 code_audit 与 pcs 两种来源、按 (file,line,cwe) 去重；
  3. `--action verify-code`：三查（sha256/行文本/snippet 字面搜索）reads 齐全，证据一致 ⇒ verified；
  4. `--action enrich`：每条补 cvss{score,vector,severity} 与 cweInfo{name,fix}；
  5. PCS `decompose("tree:<绝对目录>")`：units>0 且单位是绝对路径；
     相对路径旧行为不变（tree:tools ⇒ 相对单位，_unit_payload 仍拼 ROOT）；
  6. 参数缺失走 needs_input（失败三态，不包装成 failed）。

临时目录放在仓内 `out/`（DSH 沙箱禁止写系统 TEMP；`out/` 是构建产物区），跑完删除。

跑法（embeddable 包不能 -m，必须跑脚本文件）：
    .\\pyembed\\python.exe tests\\test_bounty_engine.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE = ROOT / "tools" / "bounty_engine.py"
PCS_PATH = ROOT / "tools" / "penetrating_cross_scan.py"
PY = sys.executable
FAILS = []

FIXTURE = '''import os
import subprocess

API_KEY = "sk-AbCdEf0123456789xyzQ"


def run(cmd):
    subprocess.run(cmd, shell=True)


if os.getenv("X") or True:
    pass


if True:
    import shutil
    shutil.rmtree("C:/build/out")
'''


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)
    return ok


def run_cli(args, timeout=240):
    return subprocess.run([PY, str(ENGINE)] + [str(a) for a in args],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def parse_single_json(cp):
    """engine 的 stdout 必须恰好是一个 JSON（不能有日志混进去）。"""
    raw = cp.stdout or ""
    lines = [ln for ln in raw.strip().splitlines() if ln.strip()]
    if len(lines) != 1:
        return None, "stdout 期望 1 行 JSON，实际 %d 行：%r" % (len(lines), raw[:300])
    try:
        return json.loads(lines[0]), ""
    except json.JSONDecodeError as exc:
        return None, "stdout 不是合法 JSON：%s · %r" % (exc, lines[0][:300])


def load_pcs():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pcs_for_test_%s" % uuid.uuid4().hex[:8],
                                                  str(PCS_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    base = ROOT / "out" / "_bounty_engine_selftest"
    work = base / uuid.uuid4().hex[:8]
    target_root = work / "root"
    out_dir = work / "out"
    try:
        target_root.mkdir(parents=True)
        (target_root / "sample_vuln.py").write_text(FIXTURE, encoding="utf-8")

        # ── [0] 失败三态：缺参数必须 needs_input，且 stdout 仍只有一个 JSON ──
        print("[0] needs_input（缺 --root）")
        cp = run_cli(["--action", "scan-code", "--out", str(out_dir)], timeout=60)
        r, err = parse_single_json(cp)
        check("缺参 stdout 单 JSON", r is not None, err)
        check("缺参 status=needs_input", (r or {}).get("status") == "needs_input", (r or {}).get("status"))
        check("缺参 exit=2", cp.returncode == 2, cp.returncode)

        # ── [1] selfcheck ────────────────────────────────────────────
        print("[1] selfcheck")
        cp = run_cli(["--action", "selfcheck"], timeout=120)
        r, err = parse_single_json(cp)
        check("selfcheck stdout 单 JSON", r is not None, err)
        r = r or {}
        check("selfcheck action", r.get("action") == "selfcheck", r.get("action"))
        check("selfcheck ok", r.get("ok") is True, r.get("error"))
        check("selfcheck 用 pyembed", (r.get("pyembed") or {}).get("ok") is True,
              (r.get("pyembed") or {}).get("actual"))
        mods = r.get("modules") or {}
        check("code_audit 可导入", (mods.get("gbt_allinone.tools.code_audit") or {}).get("ok") is True,
              (mods.get("gbt_allinone.tools.code_audit") or {}).get("error"))
        check("bounty_core 可导入", (mods.get("gbt_allinone.bounty_core") or {}).get("ok") is True,
              (mods.get("gbt_allinone.bounty_core") or {}).get("error"))
        check("pcs 可加载", (mods.get("tools/penetrating_cross_scan.py") or {}).get("ok") is True,
              (mods.get("tools/penetrating_cross_scan.py") or {}).get("error"))
        check("能力清单含四动作",
              set((r.get("capabilities") or {}).get("actions") or []) ==
              {"scan-code", "verify-code", "enrich", "selfcheck"})

        # ── [2] scan-code ────────────────────────────────────────────
        print("[2] scan-code（临时目录 + 含 shell=True 与硬编码 key 的 .py）")
        cp = run_cli(["--action", "scan-code", "--root", str(target_root),
                      "--out", str(out_dir), "--timeout", "120"], timeout=240)
        r, err = parse_single_json(cp)
        check("scan-code stdout 单 JSON（日志不混入）", r is not None, err or (cp.stderr or "")[-300:])
        r = r or {}
        check("scan-code ok", r.get("ok") is True, r.get("error"))
        check("scan-code action", r.get("action") == "scan-code")
        check("scan-code root 对得上", pathlib.Path(str(r.get("root"))).resolve() == target_root.resolve(),
              r.get("root"))

        lanes = r.get("lanes") or []
        check("两条 lane", [str(l.get("id")) for l in lanes] == ["code_audit", "pcs"],
              [l.get("id") for l in lanes])
        check("两条 lane 都 ok", all(bool(l.get("ok")) for l in lanes),
              [(l.get("id"), l.get("error")) for l in lanes])
        check("lane 有 ms", all(isinstance(l.get("ms"), int) for l in lanes), [l.get("ms") for l in lanes])

        cov = r.get("coverage") or {}
        need = {"complete", "files_eligible", "files_scanned", "rate", "truncated", "unread"}
        check("coverage 结构齐全", need.issubset(set(cov.keys())), sorted(cov.keys()))
        check("coverage 真扫到文件", int(cov.get("files_scanned") or 0) >= 1, cov.get("files_scanned"))
        check("coverage eligible>=scanned", int(cov.get("files_eligible") or 0) >= int(cov.get("files_scanned") or 0),
              (cov.get("files_eligible"), cov.get("files_scanned")))
        check("coverage rate=1.0", float(cov.get("rate") or 0) == 1.0, cov.get("rate"))
        check("coverage complete=true（无缺口）", cov.get("complete") is True, cov.get("unread"))
        check("coverage unread=[]", cov.get("unread") == [], cov.get("unread"))

        pcs_cov = (lanes[1].get("coverage") or {}) if len(lanes) > 1 else {}
        check("pcs 带出 units/hooked/full_coverage/missing/dead_spots/agree",
              {"units", "hooked", "full_coverage", "missing", "dead_spots", "agree"}.issubset(set(pcs_cov.keys())),
              sorted(pcs_cov.keys()))
        check("pcs full_coverage=true", pcs_cov.get("full_coverage") is True, pcs_cov.get("missing"))
        check("pcs security.findings 带出", isinstance((pcs_cov.get("security") or {}).get("findings"), list),
              list((pcs_cov.get("security") or {}).keys()))

        fs = r.get("findings") or []
        check("findings 非空", len(fs) >= 1, len(fs))
        req_keys = {"id", "engine", "file", "line", "cwe", "severity", "title", "snippet",
                    "evidence", "repro", "confidence", "kind"}
        check("findings schema 齐全", all(req_keys.issubset(set(f.keys())) for f in fs),
              [sorted(set(f.keys()) ^ req_keys) for f in fs][:2])
        check("findings 一律 candidate（未验证）", all(f.get("kind") == "candidate" for f in fs),
              sorted({f.get("kind") for f in fs}))
        check("evidence 三键齐全", all({"fileSha256", "lineText", "howFound"}.issubset(set((f.get("evidence") or {}).keys()))
                                    for f in fs))
        check("file 是相对 root", all(not pathlib.Path(str(f.get("file"))).is_absolute() for f in fs),
              [f.get("file") for f in fs if pathlib.Path(str(f.get("file"))).is_absolute()][:2])
        srcs = {s for f in fs for s in (f.get("sources") or [])}
        check("保留两条 lane 来源", {"code_audit", "pcs"}.issubset(srcs), sorted(srcs))
        keys = [(f.get("file"), f.get("line"), f.get("cwe")) for f in fs]
        check("(file,line,cwe) 去重", len(keys) == len(set(keys)),
              [k for k in set(keys) if keys.count(k) > 1][:3])
        check("含 shell=True 候选（pcs）",
              any("shell=True" in str(f.get("title")) or "shell=True" in str((f.get("evidence") or {}).get("howFound"))
                  for f in fs),
              [f.get("title") for f in fs])
        check("含硬编码凭据候选（cwe-798）",
              any(str(f.get("cwe")) == "CWE-798" for f in fs),
              sorted({str(f.get("cwe")) for f in fs}))
        check("含 code_audit 真规则命中（JDG/DES）",
              any(str(f.get("id")) and "code_audit" in (f.get("sources") or []) for f in fs))
        check("code_audit needs_human 也进候选（lane1 举证不丢）",
              any("code_audit" in (f.get("sources") or [])
                  and "需人核" in str((f.get("evidence") or {}).get("howFound") or "")
                  and f.get("kind") == "candidate" and f.get("confidence") == "low"
                  for f in fs),
              [str((f.get("evidence") or {}).get("howFound") or "")[:46] for f in fs])
        check("out 落盘 code_audit_findings.json", (out_dir / "code_audit_findings.json").is_file())
        check("out 落盘 scan-code.receipt.json", (out_dir / "scan-code.receipt.json").is_file())
        check("out 落盘 pcs 留痕", (out_dir / "cross_scan_trace.jsonl").is_file())

        receipt_path = out_dir / "scan-code.receipt.json"
        saved = json.loads(receipt_path.read_text(encoding="utf-8"))
        check("落盘回执与 stdout 一致", len(saved.get("findings") or []) == len(fs),
              (len(saved.get("findings") or []), len(fs)))

        # ── [3] verify-code ─────────────────────────────────────────
        print("[3] verify-code（sha256 + 行文本 + snippet 字面搜索）")
        cp = run_cli(["--action", "verify-code", "--root", str(target_root),
                      "--findings", str(receipt_path)], timeout=120)
        v, err = parse_single_json(cp)
        check("verify-code stdout 单 JSON", v is not None, err)
        v = v or {}
        check("verify-code action", v.get("action") == "verify-code")
        vrows = v.get("findings") or []
        check("verify 条目数=findings 数", len(vrows) == len(fs), (len(vrows), len(fs)))
        check("每条 3 路读法", all(len(x.get("reads") or []) == 3 for x in vrows),
              [len(x.get("reads") or []) for x in vrows][:3])
        check("全部 verified（证据真实一致）", all(x.get("verified") is True for x in vrows),
              [(x.get("id"), x.get("verdict")) for x in vrows if not x.get("verified")][:3])
        check("verdict 非空", all(bool(x.get("verdict")) for x in vrows))
        check("verified 升为 finding", all(x.get("kind") == "finding" for x in vrows),
              sorted({x.get("kind") for x in vrows}))

        # ── [4] enrich ──────────────────────────────────────────────
        print("[4] enrich（CVSS + CWE 修复建议）")
        cp = run_cli(["--action", "enrich", "--findings", str(receipt_path)], timeout=120)
        e, err = parse_single_json(cp)
        check("enrich stdout 单 JSON", e is not None, err)
        e = e or {}
        erows = e.get("findings") or []
        check("enrich 条目数=findings 数", len(erows) == len(fs), (len(erows), len(fs)))
        def _cvss_ok(x):
            c = x.get("cvss") or {}
            return (isinstance(c.get("score"), (int, float)) and float(c["score"]) > 0
                    and str(c.get("vector") or "").startswith("CVSS:3.1/")
                    and bool(c.get("severity")))
        def _cwe_ok(x):
            c = x.get("cweInfo") or {}
            return bool(c.get("name")) and bool(c.get("fix"))
        check("cvss{score,vector,severity} 齐全", all(_cvss_ok(x) for x in erows),
              [(x.get("id"), x.get("cvss")) for x in erows if not _cvss_ok(x)][:2])
        check("cweInfo{name,fix} 齐全", all(_cwe_ok(x) for x in erows),
              [(x.get("id"), x.get("cweInfo")) for x in erows if not _cwe_ok(x)][:2])

        print("[4b] UTF-8 BOM 的 findings 文件（PowerShell Set-Content -Encoding UTF8 形态）")
        bom_path = work / "scan.receipt.bom.json"
        bom_path.write_bytes(b"\xef\xbb\xbf" + receipt_path.read_bytes())
        cp = run_cli(["--action", "enrich", "--findings", str(bom_path)], timeout=120)
        eb, err = parse_single_json(cp)
        check("enrich 接受 BOM findings", (eb or {}).get("ok") is True
              and len((eb or {}).get("findings") or []) == len(fs),
              err or (eb or {}).get("error"))
        cp = run_cli(["--action", "verify-code", "--root", str(target_root),
                      "--findings", str(bom_path)], timeout=120)
        vb, err = parse_single_json(cp)
        check("verify-code 接受 BOM findings", (vb or {}).get("ok") is True
              and len((vb or {}).get("findings") or []) == len(fs),
              err or (vb or {}).get("error"))

        # ── [5] PCS 绝对目录支持 + 相对行为不变 ─────────────────────
        print("[5] PCS decompose 绝对目录 / 相对目录")
        pcs = load_pcs()
        utype, units = pcs.decompose("tree:" + str(target_root))
        check("绝对目标 unit_type=file", utype == "file", utype)
        check("绝对目标 units>0", len(units) > 0, len(units))
        check("绝对目标单位是绝对路径", all(pathlib.Path(u).is_absolute() for u in units), units[:3])
        check("_unit_payload 绝对单位原样", pcs._unit_payload("file", units[0]) == pathlib.Path(units[0]),
              pcs._unit_payload("file", units[0]))
        utype2, units2 = pcs.decompose("tree:tools")
        check("相对目标 units>0", len(units2) > 0, len(units2))
        check("相对目标单位仍是相对路径", all(not pathlib.Path(u).is_absolute() for u in units2), units2[:3])
        check("_unit_payload 相对单位仍拼 ROOT",
              pcs._unit_payload("file", units2[0]) == ROOT / units2[0], pcs._unit_payload("file", units2[0]))
        check("PCS 步骤锁/红线仍在",
              getattr(pcs, "STEPS", None) == ["decompose", "spawn", "hook", "cross_validate",
                                              "detect_omission", "trace"],
              getattr(pcs, "STEPS", None))
    finally:
        shutil.rmtree(work, ignore_errors=True)
        try:
            if base.is_dir() and not any(base.iterdir()):
                base.rmdir()
        except OSError:
            pass

    print()
    if FAILS:
        print("FAILED: %d 项 —— %s" % (len(FAILS), FAILS))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
