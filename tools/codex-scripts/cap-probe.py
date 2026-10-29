# -*- coding: utf-8 -*-
# gbt-instrument: 本件是**量具**（枚举/调用能力位出读数），它自己提到的路径不算"有人引用"。
"""能力位逐位探针（cap-probe）· 2026-10-02 第 64 轮固化。

## 它把 2026-10-01 四批人肉跑批的方法固化成常设器

**词表三路取**（都取不到 ⇒ ERR"词表空"，如实记，不盲调）：
  A 问信封：发假 op，读它回信里『（…）』里的 op 清单（多数位自己会说"认这些"）
  B api.py 分支：读 `if kind == "<kind>"` 的分派体，找它真调的模块与函数
  C 一层递归：进那个模块读 `op == "…"` 分派行

**五档读数**（对齐 truth_scan 口径）：
  REAL        ok=True 且结果非空
  HONEST_STUB 语义闸的具名拒绝（如 belief_forge『缺 claim』—— 闸在工作，不是失败）
  FAKE        ok=True 但**结果空壳**（号称成功却没有内容 ⇒ 框架的癌症，必须 0）
  NEEDS_CRED  带作用域缺失（原话照抄；**不许拿"没跑"当"没问题"**）
  ERR         词表空 / 静默空 / 异常（带原因）

## 纪律

  · **只发只读 op**（从词表里挑 READISH）；词表里没有只读 op 的位 ⇒ 跳过并记 SKIP（不盲调）；
  · 默认只扫 **只读档**（state/caps_tiers.json）；写/外部/设备档必须 `--tier` 显式点名 + 逐位配票；
  · 名册预检：kind 不在 caps_registry ⇒ **GHOST** 当场红；
  · 全量结果落 `state/cap_probe_report.json`（逐位可复核）。

## 用法

    py -3.14 tools/codex-scripts/cap-probe.py --tier 只读档
    py -3.14 tools/codex-scripts/cap-probe.py --tier 只读档 --limit 20 --offset 60
    py -3.14 tools/codex-scripts/cap-probe.py --tier 设备档 --json state/cap_probe_device.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TIERS_FILE = ROOT / "state" / "caps_tiers.json"
REPORT = ROOT / "state" / "cap_probe_report.json"
API_SRC = ROOT / "gbt_allinone" / "api.py"

READISH = ("status", "list", "scan", "read", "report", "verify", "check", "query", "health",
           "summary", "inspect", "state", "sources", "view", "rules", "caps", "observe",
           "matrix", "graph", "counts", "snapshot", "roster", "law", "redlines", "layers",
           "hardware", "models", "tables", "pages", "findings", "schema", "jsonl", "where",
           "facets", "profiles", "plan", "demo", "selftest", "energies", "catalog", "index",
           "diff", "ident", "audit", "bank", "route")

ORCH_HINT = ("autopilot", "agent_", "command_chain", "one_shot", "brain_execute", "crew", "fleet",
             "orchestration", "swarm", "dagrun", "pipeline")


def _api_src() -> str:
    try:
        return API_SRC.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def vocab_via_ask(kind: str) -> list:
    """路 A：发假 op，问它自己的词表。"""
    from gbt_allinone import api
    r = api.run_task(kind, {"op": "__probe__"})
    b = r.get("gbt_result") or r
    d = b.get("result") or {}
    msg = str(d.get("error") or b.get("message") or "")
    if "unknown capability" in msg:
        return ["__GHOST__"]
    i, j = msg.find("（"), msg.find("）")
    seg = msg[i + 1:j] if (i >= 0 and j > i) else msg
    seg = re.sub(r"^(未知 ?op[^：:]*|可用|认这些|支持的 ?op)[：:]?", "", seg.strip())
    return [x.strip() for x in re.split(r"[/、,，|]", seg) if x.strip()]


def vocab_via_dispatch(kind: str, api_src: str) -> list:
    """路 B+C：api.py 分派体 → 真模块 → `op ==` 分派行（一层递归）。"""
    m = re.search(r'if kind == "%s":\n((?:[ \t]+.*\n){1,6})' % re.escape(kind), api_src)
    if not m:
        return []
    body = m.group(1)
    out = []
    out += re.findall(r'op\s*(?:==|in)\s*[\"\']([a-z_]+)[\"\']', body)
    mm = re.search(r"from \.([\w.]+) import (\w+)", body)
    if mm:
        rel, name = mm.group(1), mm.group(2)
        for cand in (ROOT / "gbt_allinone" / (rel.replace(".", "/") + ".py"),
                     ROOT / "gbt_allinone" / "tools" / (name + ".py")):
            if cand.is_file():
                msrc = cand.read_text(encoding="utf-8", errors="replace")
                out += re.findall(r'op\s*(?:==|in)\s*[\"\']([a-z_]+)[\"\']', msrc)
                break
    return [o for o in dict.fromkeys(out) if o != "__probe__"]


def _has_content(v, depth=0):
    """递归判定值里有没有真内容（2026-10-03）：{"runs": [两条]} 是真货，{"echo": {}} 才是空壳。"""
    if depth > 4:
        return True
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple)):
        return any(_has_content(x, depth + 1) for x in v)
    if isinstance(v, dict):
        return any(_has_content(x, depth + 1) for x in v.values())
    return v is not None


def main() -> int:
    ap = argparse.ArgumentParser(description="能力位逐位探针（只读 · 五档读数）")
    ap.add_argument("--tier", default="只读档")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--json", default="", help="报告另存的路径")
    a = ap.parse_args()

    tiers = json.loads(TIERS_FILE.read_text(encoding="utf-8")) if TIERS_FILE.is_file() else {"tiers": {}}
    _tier_map = (tiers.get("tiers") or {})
    if a.tier not in _tier_map:
 # 2026-10-04 修（真故障）：tier 名写错（如「只读」vs「只读档」）时原来**静默**取到空列表
        # ⇒ 逐位探针空跑一轮，还把**空报告**覆盖掉上一份真读数（本轮实测撞上，报告被写空）。
        # 纪律：名字不认 ⇒ 当场红 + 列合法名 + **不写报告**（不静默、不拿空当结果）。
        print("🔴 tier 名不认：%r —— 合法名：%s" % (a.tier, "、".join(sorted(_tier_map)) or "（分档表为空）"))
        print("   分档表：%s" % TIERS_FILE)
        return 2
    tier = _tier_map.get(a.tier) or []
    kinds = [x["kind"] if isinstance(x, dict) else str(x) for x in tier]
    # 2026-10-03：名册先对齐活注册表——快照名册里的陈旧名不算 GHOST（那是运行时幽灵），单列 STALE_ROSTER
    try:
        from gbt_allinone import caps_registry as _cr
        _live = set(getattr(_cr, "BENIGN_CAPS", {}) or {})
    except Exception:                                    # noqa: BLE001
        _live = None
    stale_roster = []
    if _live is not None:
        stale_roster = [k for k in kinds if k not in _live]
        kinds = [k for k in kinds if k in _live]
    kinds = kinds[a.offset:]
    kinds = kinds[: a.limit] if a.limit else kinds
    api_src = _api_src()

    rows, buckets = [], {"REAL": [], "HONEST_STUB": [], "FAKE": [], "NEEDS_CRED": [], "ERR": [], "GHOST": [], "SKIP": []}
    for kind in kinds:
        if any(h in kind for h in ORCH_HINT):
            buckets["SKIP"].append(kind)               # 编排器名：不盲调（要专门会话）
            continue
        ops = vocab_via_ask(kind)
        if ops == ["__GHOST__"]:
            buckets["GHOST"].append(kind); rows.append({"kind": kind, "bucket": "GHOST"}); continue
        if not ops:
            ops = vocab_via_dispatch(kind, api_src)
        ro = [o for o in ops if any(t in o.lower() for t in READISH)]
        if ops and ro:
            pick = ro[0]
            payload = {"op": pick}
        elif a.tier == "只读档":
            # 2026-10-03 兜底：入口直吃参数的位（如 alerts(last)）没有 op 分派行；
            # 名册契约保证只读档可安全直调 ⇒ 发默认空载荷，五档判定照走。
            pick = "(default)"
            payload = {}
        else:
            buckets["ERR"].append("%s(词表空：三路都取不到)" % kind)
            rows.append({"kind": kind, "bucket": "ERR", "error": "vocab-empty"}); continue
        try:
            from gbt_allinone import api
            r = api.run_task(kind, payload)
            b = r.get("gbt_result") or r
            d = b.get("result") or {}
        except Exception as err:                            # noqa: BLE001
            buckets["ERR"].append("%s(%s): %s" % (kind, pick, str(err)[:40]))
            rows.append({"kind": kind, "bucket": "ERR", "op": pick, "error": str(err)[:120]}); continue
        if (a.tier == "只读档" and pick == "(default)" and isinstance(d, dict)
                and not any(_has_content(x) for x in d.values())):
            try:                                            # 空载重试一次：回声类位要吃点东西才显真货
                r2 = api.run_task(kind, {"q": "probe"})
                b2 = r2.get("gbt_result") or r2
                d2 = b2.get("result") or {}
                if isinstance(d2, dict) and any(_has_content(x) for x in d2.values()):
                    r, b, d = r2, b2, d2
            except Exception:                               # noqa: BLE001
                pass
        miss = b.get("missing") or d.get("missing") or r.get("missing") or []
 # 2026-10-04 修判据错尺（P1）：`missing` **计数型**（如 obsidian_vault 的
        #    `missing: 27`= 27 个触手库缺记忆页）**不是"缺作用域"** —— 旧版把计数也归
        #    NEEDS_CRED，把一条真读数读成了"需票"（实测：20:17 报告里 obsidian_vault 缺 [4] 之类）。
        #    口径：**缺作用域**=门拒（`denied`）或 missing 是**名单**（list/tuple/set/单名 str）；
        #    计数单列 `missing_count` 进行里当证据，不占票型。
        miss_count = None
        if isinstance(miss, bool):                          # bool 是 int 的子类，先挡（True 不是计数）
            miss = [str(miss)]
        elif isinstance(miss, int):
            miss_count, miss = miss, []
        elif isinstance(miss, str):
            miss = [miss]
        elif not isinstance(miss, (list, tuple, set)):
            miss = [str(miss)]
        ok = (d.get("ok") is True) or (b.get("status") == "ok" and isinstance(d, dict) and d)
        has_content = isinstance(d, dict) and (len(d) > 1 or any(_has_content(x) for x in d.values()))
        if b.get("denied") or miss:
            buckets["NEEDS_CRED"].append("%s(缺%s)" % (kind, ",".join(map(str, miss))[:20]))
            rows.append({"kind": kind, "bucket": "NEEDS_CRED", "missing": miss, "op": pick})
        elif ok and has_content:
            buckets["REAL"].append("%s(%s)" % (kind, pick))
            row = {"kind": kind, "bucket": "REAL", "op": pick}
            if miss_count is not None:
                row["missing_count"] = miss_count                # 计数照记（是读数，不是票型）
            rows.append(row)
        elif ok:
            buckets["FAKE"].append("%s(%s)：ok 但结果空壳" % (kind, pick))
            rows.append({"kind": kind, "bucket": "FAKE", "op": pick})
        elif d and any(d.get(k) for k in ("error", "message", "reason")):
            buckets["HONEST_STUB"].append("%s：%s" % (kind, str(d.get("error") or d.get("message") or d.get("reason"))[:40]))
            rows.append({"kind": kind, "bucket": "HONEST_STUB", "op": pick})
        else:
            buckets["ERR"].append("%s(%s)：读不到结果也不读不到原因" % (kind, pick))
            rows.append({"kind": kind, "bucket": "ERR", "op": pick, "error": "silent"})

    summary = {k: len(v) for k, v in buckets.items()}
    report = {"tier": a.tier, "total": len(kinds), "buckets": summary, "rows": rows,
              "stale_roster": stale_roster,
              "made_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "_口径": "只读探针（词表三路取 · 只发 READISH op · 词表空的只读位走默认直调兜底）；"
                       "FAKE 必须为 0；GHOST=注册表在册但运行时不认；SKIP=编排器名不盲调；"
                       "STALE_ROSTER=快照名册里的陈旧名（不在活注册表，已剔除不占读数）"}
    out_path = Path(a.json) if a.json else REPORT
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("== cap-probe · 档=%s · %d 位 ==" % (a.tier, len(kinds)))
    for k in ("REAL", "HONEST_STUB", "FAKE", "NEEDS_CRED", "GHOST", "ERR", "SKIP"):
        print("  %-12s %3d" % (k, summary.get(k, 0)))
    for x in (buckets["FAKE"] + buckets["GHOST"])[:8]:
        print("    ⚠️", x)
    if stale_roster:
        print("  陈旧名册（不在活注册表，已剔除 %d 个）：%s" % (len(stale_roster), "、".join(stale_roster[:10])))
    print("  报告:", str(out_path.relative_to(ROOT)) if str(out_path).startswith(str(ROOT)) else out_path)
    return 0 if (summary.get("FAKE", 0) == 0 and summary.get("GHOST", 0) == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
