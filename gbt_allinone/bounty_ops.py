"""安全众测闭环（bounty_ops）—— 把 6 个散装模块收成**一个入口**。

由来（2026-11-04 清理时捞出来的）：这 6 个模块 2026-11-02 就写完了，但**从没注册能力位、
也从没被任何地方 import** —— 属于「做出来了但大脑调不到」，跟当初 vision_detect /
vision_embed / vision_ui 三个是同一个病。它们原本躺在
`state/proactive/work/g-1/`（一份失败工单的旧仓库快照）里，清旧副本时如果不先捞出来，
就永久丢了。

收进来的 6 件与各自职责：
  `bounty_core`       CVSS 3.1 Base/Temporal/Environmental + CWE 中文修复建议 + 状态机
  `security_policy`   能力位级放行闸（与主干 `security/policy.py` 的**作用域闸是两层，不重复**）：
                      ① 黑客全能力必须主人终端确认；② 受攻击时进极限并发模式（最高决策=自己判断）；
                      ③ 转账任何时候都要主人确认，攻击模式也不例外
  `attack_evidence`   举证门槛：没强证据或主人陈述，**不许说被攻击**
  `attack_forensics`  本机取证与合法防御（多采集器并发 → 证据链 + ZIP）
  `scope_import`      平台 scope 文档归一化（HackerOne / Bugcrowd 等）
  `platform_sync`     平台状态只读同步

## 三条纪律
1. **只读优先**：`check` / `classify` / `explain` / `detect` / `status` 全部零副作用，直接跑。
2. **高危必须显式**：`enter_attack_mode` / `approve` / `respond` / `import_doc` 会改放行状态或
   对外动作 —— 本门面**不代批**，缺 `confirm=true` 就如实拒，并告诉你该在哪做（终端）。
3. **不假装**：没证据就说没证据；模块报错如实透传，不吞成「成功」。

op：
  status                         现况（6 个模块是否可 import + 放行态 + 证据数）
  cvss    vector=...             算 CVSS 3.1 分与等级
  cwe     cwe=CWE-79             CWE 中文名 + 修复建议
  policy  cap=...                放行判定（allow / need_terminal_confirm / blocked_transfer / attack_mode_allow）
  classify cap=...               normal / hacker / transfer
  evidence                       证据清单 + 交代（举证门槛是否满足）
  detect  [denied_burst=8]       本地只读检测候选证据（**不判定**，只举证）
  baseline                       记录关键文件 hash 基线
  scope   doc={...} | path=...   平台 scope 文档归一化（不联网）
  sync    [dry_run=true]         平台状态只读同步
  collect agents=[...]           本机取证采集（产出证据包）
  respond reason=... confirm=true 受攻击响应（**高危**：会进攻击模式 + 回收自有进程）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPS = ("status", "cvss", "cwe", "policy", "classify", "evidence", "detect",
       "baseline", "scope", "sync", "collect", "respond")

# 只读 op：零副作用，直接放行
READ_ONLY = {"status", "cvss", "cwe", "policy", "classify", "evidence", "detect", "scope"}
# 高危 op：必须 confirm=true，且如实告诉调用方它动了什么
DANGEROUS = {"respond"}


def _mod(name):
    """延迟 import：任何一个模块坏了都不该拖垮整位（各自如实报）。"""
    import importlib
    return importlib.import_module("gbt_allinone." + name)


def _status() -> dict:
    mods = ("bounty_core", "security_policy", "attack_evidence",
            "attack_forensics", "scope_import", "platform_sync")
    st = {}
    for m in mods:
        try:
            _mod(m)
            st[m] = True
        except Exception as e:                                        # noqa: BLE001
            st[m] = "%s: %s" % (type(e).__name__, str(e)[:120])
    out = {"ok": all(v is True for v in st.values()), "modules": st, "ops": list(OPS)}
    try:
        out["policy"] = _mod("security_policy").status()
    except Exception as e:                                            # noqa: BLE001
        out["policy"] = {"error": str(e)[:150]}
    try:
        ex = _mod("attack_evidence").explain()
        out["evidence"] = {"count": ex.get("evidence_count"), "conclusion": ex.get("conclusion"),
                           "admitted": ex.get("admitted")}
    except Exception as e:                                            # noqa: BLE001
        out["evidence"] = {"error": str(e)[:150]}
    return out


def _ok(op, r):
    """统一补 ok —— 模块自带的 ok 优先；没 ok 但也没抛异常 ⇒ 视为执行成功。

    为什么必须补：`security_policy.check()` 只回 decision 不回 ok，
    原样透传会让调用方把「已经判定完成」误读成「调用失败」（实测 ok=None）。
    """
    if isinstance(r, dict):
        r = dict(r)
        r.setdefault("ok", True)
    else:
        r = {"value": r, "ok": True}
    return dict({"op": op}, **r)


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").strip() or "status"
    if op not in OPS:
        return {"ok": False, "error": "unknown_op", "op": op, "supported": list(OPS),
                "why": "bounty_ops 没这个 op —— 拒绝而不是悄悄当 status"}

    if op in DANGEROUS and not (kw.get("confirm") is True):
        return {"ok": False, "op": op, "error": "need_confirm",
                "why": "这是高危动作，会改放行状态或对外出手；必须显式 confirm=true",
                "what_it_does": "进极限并发攻击模式（TTL 内最高决策交给本机）+ 回收自有进程 + 极限并发取证",
                "note": "没有举证就不要走这一步 —— 先跑 op=evidence / op=detect 拿证据"}

    try:
        if op == "status":
            return _ok(op, _status())

        if op == "cvss":
            core = _mod("bounty_core")
            v = str(kw.get("vector") or "").strip()
            if not v:
                return {"ok": False, "op": op, "reason": "缺参数：vector（CVSS 3.1 向量串）",
                        "example": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}
            r = core.cvss3(v)
            if r.get("ok") and r.get("base_score") is not None:
                r["severity_zh"] = {"critical": "严重", "high": "高危", "medium": "中危",
                                    "low": "低危", "none": "无"}.get(r.get("severity"), r.get("severity"))
            return _ok(op, r)

        if op == "cwe":
            core = _mod("bounty_core")
            c = str(kw.get("cwe") or "").strip()
            if not c:
                return {"ok": False, "op": op, "reason": "缺参数：cwe（如 CWE-79）"}
            return _ok(op, core.cwe_info(c))

        if op == "policy":
            sp = _mod("security_policy")
            cap = str(kw.get("cap") or "").strip()
            if not cap:
                return {"ok": False, "op": op, "reason": "缺参数：cap（能力位名）"}
            return _ok(op, sp.check(cap))

        if op == "classify":
            sp = _mod("security_policy")
            cap = str(kw.get("cap") or "").strip()
            if not cap:
                return {"ok": False, "op": op, "reason": "缺参数：cap"}
            return {"ok": True, "op": op, "cap": cap, "kind": sp.classify(cap),
                    "note": "normal=常跑 / hacker=要主人终端确认 / transfer=任何时候都要确认（攻击态也不例外）"}

        if op == "evidence":
            ae = _mod("attack_evidence")
            out = ae.explain()
            if kw.get("list") or kw.get("limit"):
                out["items"] = ae.list_evidence(int(kw.get("limit") or 20))
            return _ok(op, out)

        if op == "detect":
            ae = _mod("attack_evidence")
            cand = ae.detect_signals(denied_burst=int(kw.get("denied_burst") or 8),
                                     window_s=int(kw.get("window_s") or 3600))
            return {"ok": True, "op": op, "candidates": cand, "count": len(cand),
                    "note": "这里只**举证**，不判定。要入攻击模式还得走 admission（强证据≥1 或主人陈述）"}

        if op == "baseline":
            ae = _mod("attack_evidence")
            files = kw.get("files")
            r = ae.record_baseline(files) if files else ae.record_baseline()
            return _ok(op, r)

        if op == "scope":
            si = _mod("scope_import")
            doc = kw.get("doc")
            if doc is None and kw.get("path"):
                doc = si.load_sample(str(kw.get("path")))
            if doc is None:
                return {"ok": False, "op": op, "reason": "缺参数：doc（平台 JSON）或 path（本地文件）"}
            return _ok(op, si.normalize(doc))

        if op == "sync":
            ps = _mod("platform_sync")
            r = ps.sync(provider=str(kw.get("provider") or ""),
                        dry_run=bool(kw.get("dry_run", True)),
                        program=str(kw.get("program") or ""))
            return _ok(op, r)

        if op == "collect":
            af = _mod("attack_forensics")
            agents = kw.get("agents") or ["system", "processes", "connections", "audit", "files"]
            r = af.collect(agents=agents, incident=str(kw.get("incident") or ""))
            return _ok(op, r)

        if op == "respond":
            af = _mod("attack_forensics")
            reason = str(kw.get("reason") or "").strip()
            if not reason:
                return {"ok": False, "op": op, "reason": "缺参数：reason（为什么认为被攻击）",
                        "note": "空理由不允许进攻击模式"}
            r = af.respond(reason=reason, user_report=str(kw.get("user_report") or ""),
                           ttl=int(kw.get("ttl") or 600), reclaim=bool(kw.get("reclaim", False)),
                           incident=str(kw.get("incident") or ""))
            return _ok(op, r)

    except Exception as e:                                            # noqa: BLE001
        return {"ok": False, "op": op, "error": type(e).__name__, "reason": str(e)[:300]}

    return {"ok": False, "op": op, "error": "unreachable", "supported": list(OPS)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else "status"), ensure_ascii=False, indent=1))
