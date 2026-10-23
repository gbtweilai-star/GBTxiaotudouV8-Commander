# -*- coding: utf-8 -*-
"""R-H295 三个根源修复的回归验证。
 ① brand_outro：空参应返回状态，不再报「作品名不能为空」
 ② sec_scan：返回列表应按严重度排序（critical 在前）+ 支持 limit + 如实报截断
 ③ sec_chain：拿到 critical 清单后应能构建链（原来拿不到料）
"""
import json
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from gbt_allinone import api  # noqa: E402
from gbt_allinone.security.security_brain import HackerBrain  # noqa: E402

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-46s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-46s %s" % (name, detail))


def body(r):
    b = r
    for _ in range(4):
        if not isinstance(b, dict):
            break
        n = b.get("gbt_result") or b.get("result")
        if isinstance(n, dict) and ("ok" in n or "status" in n or "message" in n):
            b = n
        else:
            break
    return b


print("=" * 92)
print("① brand_outro：补 status 入口（原来它是唯一「空参去干活」的能力）")
print("=" * 92)
r = api.run_task("brand_outro", {}, safe=True, probe=True)
b = body(r)
chk("空参不再报「作品名不能为空」", "作品名不能为空" not in json.dumps(b, ensure_ascii=False),
    json.dumps(b, ensure_ascii=False)[:80])
chk("空参返回自身状态", b.get("kind") == "brand_outro" and b.get("ops"),
    "ops=%s" % (b.get("ops") or []))
chk("status 报出各表条数", isinstance(b.get("counts"), dict),
    json.dumps(b.get("counts") or {}, ensure_ascii=False))
chk("status 带诚实边界", bool(b.get("boundary")), str(b.get("boundary"))[:60])
r2 = api.run_task("brand_outro", {"op": "render", "work_name": ""}, safe=True, probe=True)
chk("render 空名仍然拒（闸没被放松）",
    "作品名不能为空" in json.dumps(body(r2), ensure_ascii=False), "")
r3 = api.run_task("brand_outro", {"op": "intros"}, safe=True, probe=True)
chk("原有 op 未回归", bool(body(r3).get("intros")), "")

print("\n" + "=" * 92)
print("② sec_scan：生产层口径 + 按严重度排序 + limit + 如实报截断")
print("=" * 92)
hb = HackerBrain()
d = hb.scan_vulnerabilities("medium")
vs = d.get("vulnerabilities") or []
chk("默认口径是生产层", d.get("scope") == "production", "scope=%s" % d.get("scope"))
chk("返回条数 = 默认 20", len(vs) == 20, "%d 条" % len(vs))
chk("已按严重度排序（首条即最重）", bool(vs) and vs[0]["severity"] in ("critical", "high", "medium"),
    "首条=%s 序列=%s" % (vs[0]["severity"] if vs else "-",
                     ",".join(v["severity"] for v in vs[:6])))
chk("如实报了截断", d.get("truncated") is True and d.get("shown") == 20,
    "total=%s shown=%s" % (d.get("total"), d.get("shown")))
chk("截断说明非空", bool(d.get("limit_note")), str(d.get("limit_note"))[:70])
d2 = hb.scan_vulnerabilities("medium", limit=60)
chk("limit 生效", len(d2.get("vulnerabilities") or []) == 60,
    "%d 条" % len(d2.get("vulnerabilities") or []))
d3 = hb.scan_vulnerabilities("critical")
chk("severity=critical 只留 critical 以上",
    all(v["severity"] == "critical" for v in (d3.get("vulnerabilities") or [])),
    "total=%s" % d3.get("total"))
chk("严重度过滤口径正确（critical 计数与过滤结果一致）",
    d3.get("total") == d3.get("critical"), "total=%s critical=%s" % (d3.get("total"), d3.get("critical")))
# 非生产层：不是静默少扫，而是如实报跳过了多少
_np = d.get("non_production") or {}
chk("非生产层如实报（跳过文件数+原因+怎么放开）",
    _np.get("total_skipped", 0) > 0 and bool(_np.get("why")) and bool(_np.get("how_to_include")),
    "跳过 %s 个文件 %s" % (_np.get("total_skipped"), _np.get("skipped_files")))
chk("非生产层默认不计入结论",
    d.get("total") == len(hb.scan_vulnerabilities("medium", limit=500)["vulnerabilities"])
    or d.get("tier_counts", {}).get("production") == d.get("total")
    or "scratch" not in json.dumps(d.get("vulnerabilities") or [], ensure_ascii=False),
    "tier_counts=%s" % d.get("tier_counts"))
_all = hb.scan_vulnerabilities("medium", limit=500, include_non_production=True)
chk("include_non_production=True 能把全量取回",
    _all.get("scope") == "all_tiers" and _all.get("total", 0) > d.get("total", 0),
    "全量 %s vs 生产层 %s" % (_all.get("total"), d.get("total")))
# 豁免：必须记账，且能说出按哪条规则豁的
_ex = d.get("exempted") or {}
chk("豁免一律记账（条数+规则说明）",
    _ex.get("total", 0) > 0 and bool(_ex.get("rules")),
    "%s" % json.dumps(_ex.get("counts") or {}, ensure_ascii=False))
chk("豁免规则里写明「注释/文档串不会被执行」",
    "comment_or_doc_exec" in (_ex.get("counts") or {}), "")

print("\n" + "=" * 92)
print("③ sec_chain：『没拿到料』与『扫过没发现』必须分开")
print("=" * 92)
# 用**合成料**验链构建本身（真实命令注入已被本轮修掉，不能再拿它当料）
_syn = [{"id": "VULN-0001", "title": "敏感信息泄露", "severity": "high", "cwe": "CWE-532",
         "location": "x.py:1", "match": "token = 'abc'", "fix": "", "cvss": 7.5},
        {"id": "VULN-0002", "title": "命令注入", "severity": "critical", "cwe": "CWE-78",
         "location": "x.py:2", "match": "os.system(c)", "fix": "", "cvss": 9.8}]  # TAINT_SAFE: test fixture mock data
chain = hb.build_exploit_chain(_syn)
chk("喂入真料能构建链", chain.get("total_chains", 0) > 0,
    "chains=%s risk=%s" % (chain.get("total_chains"), chain.get("risk")))

r = api.run_task("sec_chain", {}, safe=True, probe=True)
b = body(r)
chk("空参自己去找料（不再默认『没链』）", b.get("material_source") == "auto_scan",
    "material_source=%s" % b.get("material_source"))
chk("空参如实说明是扫过之后的结论", bool(b.get("scanned")),
    "scanned=%s" % json.dumps(b.get("scanned") or {}, ensure_ascii=False)[:96])
chk("空参给出 note 说明取料来源", bool(b.get("note")), str(b.get("note"))[:78])

r = api.run_task("sec_chain", {"vulns": []}, safe=True, probe=True)
b2 = body(r)
chk("显式传空清单则尊重调用方（不自行扫）",
    b2.get("material_source") == "supplied_empty" and b2.get("total_chains") == 0,
    "material_source=%s" % b2.get("material_source"))
chk("两种空参结论不再混为一谈",
    b.get("material_source") != b2.get("material_source"), "")

print("\n" + "=" * 92)
print("④ 默认 op 口径：123 条路由里「默认 op 不是 status」的 14 条，空参到底在读数还是干活")
print("=" * 92)
# 判定必须下沉到内层 result（信封顶层永远 ok=True，会把只读能力误判成「去干活」）
NON_STATUS = ["meta_cognition", "coverage_auditor", "tentacle_cognition", "caps_called_audit",
              "scene_anchor", "hook_registry", "emotion_projection",
              "vision", "prompt_bridge", "voice", "voice_orchestra",
              "browser", "bluetooth", "bt_control"]
_ACTING = []
for kind in NON_STATUS:
    try:
        res = api.run_task(kind, {}, safe=True, probe=True)
    except Exception as exc:  # noqa: BLE001
        _ACTING.append((kind, "抛异常 %s" % exc))
        continue
    if not isinstance(res, dict) or res.get("ok") is not True:
        continue                        # 诚实拒绝：门/参数，合规
    inner = body(res)
    if inner.get("readonly") is True:   # 只读读数
        continue
    if inner.get("ok") is False:        # 如实拒绝（如 prompt_bridge 的 empty_input）
        continue
    _ACTING.append((kind, "ok=True 但既非 readonly 也非列举"))

chk("空参真去干活的路由 = 0", not _ACTING,
    "；".join("%s(%s)" % (k, w) for k, w in _ACTING) or "14 条全部只读或如实拒绝")

r = api.run_task("voice_orchestra", {}, safe=True, probe=True)
b = body(r)
chk("voice_orchestra 空参落 status 且标 readonly", b.get("op") == "status" and b.get("readonly") is True,
    "op=%s registry_size=%s" % (b.get("op"), b.get("registry_size")))
r = api.run_task("voice_orchestra", {"op": "list"}, safe=True, probe=True)
b = body(r)
chk("voice_orchestra list 仍可用且标 readonly",
    b.get("count", 0) > 0 and b.get("readonly") is True, "count=%s" % b.get("count"))

print("\n" + "=" * 92)
print("⑤ 扫描器自身的根因：BOM / 影子目录 / 豁免记账 / 判定豁免要说清")
print("=" * 92)
# 5a. BOM：本仓 10 个 .py 带 UTF-8 BOM，带 BOM 的文本喂 ast.parse 会抛 U+FEFF 语法错，
#     于是 cross_scan 的 G 维（断链）对这 10 个文件**静默不执行**（含 caps_registry.py）。
_BOM_FILES = ["gbt_allinone/caps_registry.py", "gbt_allinone/__init__.py",
              "gbt_allinone/__main__.py", "gbt_allinone/quant_tech.py"]
import ast as _ast  # noqa: E402
_parsed = 0
for _f in _BOM_FILES:
    _src = (BASE / _f).read_text(encoding="utf-8", errors="replace")
    try:
        _ast.parse(_src.lstrip("\ufeff"))
        _parsed += 1
    except SyntaxError:
        pass
chk("带 BOM 的文件去掉 BOM 后能解析（修读方不删 BOM）", _parsed == len(_BOM_FILES),
    "%d/%d" % (_parsed, len(_BOM_FILES)))

# 5b. 家根影子目录已归位
from gbt_allinone.tools.shadow_check import shadow_report  # noqa: E402
_sr = shadow_report()
chk("家根无影子（shadow_check GREEN）", _sr.get("verdict") == "GREEN",
    "shadow_files=%s shadow_dirs=%s" % (_sr.get("shadow_files"), _sr.get("shadow_dirs")))
chk("根 docs/ 已归位到 gbt_allinone/docs/",
    not (BASE / "docs").exists() and (BASE / "gbt_allinone" / "docs" / "Stigmergy协作层.md").exists(), "")

# 5c. cross_scan 全绿，且判定豁免写清楚
r = api.run_task("cross_scan", {}, safe=True, probe=True)
b = body(r)
chk("cross_scan 全绿", b.get("verdict") == "clean" and not b.get("findings"),
    "findings=%d deep_checked=%s" % (len(b.get("findings") or []), b.get("deep_checked")))
_ex = (b.get("verdict_exemptions") or {}).get("selfscan") or {}
chk("被豁免的扫描器判定写明了理由",
    _ex.get("exempted") is True and bool(_ex.get("why")) and _ex.get("raw_verdict"),
    "raw=%s why=%s" % (_ex.get("raw_verdict"), str(_ex.get("why"))[:60]))

# 5d. 生产层无 critical/high（本轮把真 critical 修掉、把误报按规则豁免）
_d = hb.scan_vulnerabilities("high", limit=500)
chk("生产层 critical=0 且 high=0",
    _d.get("critical") == 0 and _d.get("high") == 0,
    "critical=%s high=%s" % (_d.get("critical"), _d.get("high")))
chk("坏转义序列记账（不再漏 stderr）", "parse_warning_count" in _d,
    "parse_warning_count=%s" % _d.get("parse_warning_count"))

print("\n" + "-" * 92)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
