# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""offense_ops —— 自主渗透编排（主人令 2026-10-16：把 pentagi 全部能力蒸成我们的原生能力）

蒸自 **vxControl/pentagi**（MIT · Go · 30.5k 星 · 多智能体自主渗透测试系统）的**思想**，不搬代码：
  多智能体分工（researcher / pentester / coder / reporter）· 工具面（terminal/browser/search/embeddings）
  · 跨任务记忆（向量检索）· 证据链与报告 · self-hosted 自主执行。
**红线（我们的护栏优先于它的自主性）**：
  只打**主人在终端明确授权**的范围；fail-closed；不可回滚动作先问；凭据只报已配/未配；
  发现只报**可复现**的；**不外发**任何目标数据。
op：plan / roles / tools / evidence / memory / gate / check / route（**全只读·零作用域·不出网·不动手**）
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "pentagi-自主渗透-蒸馏.md"
OUT = ROOT / "state" / "offense"
# 2026-11-06 主人令：挖洞能力「原生优先、不许外挂、除危险/资金外不许拒绝」。
#   新增 hunt / swarm / coverage / knowledge 四个 op —— 全是**在本机把已有能力位编排起来**，
#   不引任何云服务、不装第三方扫描器、不出网。
OPS = ("plan", "roles", "tools", "evidence", "memory", "gate", "check", "route",
       "hunt", "swarm", "coverage", "knowledge")
PHASES = ["侦察（被动优先）", "武器化（清单化）", "利用（只打授权面）", "后渗透（最小必要）", "报告（可复现）"]


def plan(target: str = "", scope: str = "") -> dict:
    t = (target or "").strip()
    if not t:
        return {"ok": False, "reason": "need_target", "how": "给目标；**并给授权范围**（谁授权的、范围边界）"}
    if not (scope or "").strip():
        return {"ok": False, "reason": "need_scope", "how": "**没有授权范围就没有这一步**：先写清授权范围（fail-closed）"}
    return {"ok": True, "op": "plan", "kind": "offense_ops", "target": t, "scope": scope,
            "phases": PHASES,
            "loop": ["计划 → 执行 → 取证 → 复核（每条发现必须可复现）→ 报告 → 复盘"],
            "judges": ["每一步能指回授权范围", "每条发现带复现步骤与影响", "越界即停并如实报"],
            "source": "vxControl/pentagi（MIT · 只蒸思想）", "doc": str(DOC)}


def roles() -> dict:
    return {"ok": True, "op": "roles", "kind": "offense_ops",
            "roles": [
                {"角色": "researcher（侦察）", "干什么": "收集公开信息与资产面", "判据": "每条来源可指回"},
                {"角色": "pentester（利用）", "干什么": "在授权面上验证可复现问题", "判据": "复现步骤 + 影响 + 时间戳"},
                {"角色": "coder（工具）", "干什么": "写脚本/解析/自动化取证", "判据": "脚本可复跑，不硬编码凭据"},
                {"角色": "reporter（报告）", "干什么": "出可复核报告与修复建议", "判据": "结论 → 证据 → 建议三段齐"},
            ],
            "note": "多智能体是**分工**不是**放飞**：每个角色都过同一道授权门（见 op=gate）",
            "source": "vxControl/pentagi（MIT）"}


def tools() -> dict:
    return {"ok": True, "op": "tools", "kind": "offense_ops",
            "surfaces": ["terminal（命令执行）", "browser（页面取证）", "search（公开检索）", "embeddings（跨任务记忆检索）"],
            "local_readback": "本机已配/未配由各自能力位现读（pod_link/browser/sec_*）；**取不到就写未读到**",
            "judges": ["每个动作留痕", "凭据只报已配/未配", "危险动作先问主人"]}


def evidence() -> dict:
    return {"ok": True, "op": "evidence", "kind": "offense_ops",
            "chain": ["时间戳", "命令/请求原文", "响应要点（脱敏）", "复现步骤", "影响范围", "修复建议"],
            "judges": ["**可复现/重现**才算有效发现", "只有影响没有复现步骤 ⇒ 标未验证",
                       "证据不外发；报告里第三方信息脱敏"],
            "standard": "与 sec_* 同口径：定级用平台/标准口径，不自编"}


def memory() -> dict:
    return {"ok": True, "op": "memory", "kind": "offense_ops",
            "what": "跨任务记忆：把目标画像、已试手法、已验证结论入我们自己的库（向量/关键词检索）",
            "rules": ["**不外发**（记忆与上下文永不外发）", "过期读数带 cached/ts",
                      "新增即清旧：同一目标只留一份最新画像", "落点只走我们自己的目录"]}


def gate(action: str = "") -> dict:
    a = (action or "").strip()
    return {"ok": True, "op": "gate", "kind": "offense_ops", "action": a or "（未指定动作）",
            "gates": [
                {"闸": "授权", "判据": "主人在终端明确授权范围；**没有范围不动手**", "fail": "拒绝并报缺什么"},
                {"闸": "不可回滚", "判据": "删除/改写/付款/接管设备类动作先问主人", "fail": "停下等人点头"},
                {"闸": "凭据", "判据": "只用已配凭据；只报已配/未配", "fail": "如实报未配"},
                {"闸": "出网", "判据": "只对授权目标出网；不扫无关资产", "fail": "拒绝"},
                {"闸": "留痕", "判据": "每步进审计账（公理一：无痕即不存在）", "fail": "该步视为未发生"},
            ], "is_instruction": False}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "offense_ops",
            "rules": ["MIT ⇒ 只蒸思想不搬代码", "**护栏优先于自主性**（pentagi 的自主执行必须在我们的授权门内）",
                      "只在授权范围动手；越界即停", "发现必须可复现；不可复现标未验证",
                      "目标数据不外发；凭据不入档", "本 op 集**全只读**，真动手走各自能力位（sec_* / 触手）"],
            "doc": str(DOC)}


def route(target: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "offense_ops", "target": (target or "").strip(),
            "map": [{"要什么": "定阶段与范围", "走": "cap offense_ops op=plan"},
                    {"要什么": "分工", "走": "cap offense_ops op=roles"},
                    {"要什么": "工具面现状", "走": "cap offense_ops op=tools + 各能力位现读"},
                    {"要什么": "证据与报告口径", "走": "cap offense_ops op=evidence"},
                    {"要什么": "跨任务记忆", "走": "cap offense_ops op=memory"},
                    {"要什么": "过授权闸", "走": "cap offense_ops op=gate"},
                    {"要什么": "真扫/真打", "走": "sec_surface / sec_scan / sec_chain / code_audit / pentest_distill"}],
            "direct": True}


# ── 原生挖洞链（2026-11-06）───────────────────────────────────────────────
# 一条「触手」= 一条**独立扫描链**，各自出独立回执；合并时去重并记覆盖账。
# 全部调本仓既有能力位：不引云、不装外部扫描器、不出网、零作用域。
LANES = (
    {"id": "surface", "cap": "sec_surface", "params": {}, "what": "攻击面测绘（入口点/网络/文件/用户输入）"},
    {"id": "owasp", "cap": "sec_scan", "params": {"limit": 500},
     "what": "OWASP Top-10 + CWE 模式库（拉满；截断会进 unread）"},
    {"id": "sast", "cap": "code_audit", "params": {"op": "scan"},
     "then": {"cap": "code_audit", "params": {"op": "findings"}},
     "what": "多阶段 SAST + 证据 + 复现"},
    {"id": "llm", "cap": "llm_redteam", "params": {"op": "selfcheck"},
     "what": "OWASP LLM Top-10 实测探针"},
    {"id": "flow", "cap": "pentest_flow", "params": {"op": "surface"},
     "needs_files": True, "what": "渗透流水线：source->sink 候选（污点近似）"},
)
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
# 这些触手出的是**候选**（污点近似/启发式），必须过 validate 才能叫漏洞
CANDIDATE_LANES = frozenset({"flow"})
_SEV_CN = {"紧急": "critical", "严重": "critical", "高危": "high", "中危": "medium",
           "低危": "low", "提示": "info"}


def _sev(v) -> str:
    s = str(v or "").strip().lower()
    if s in SEV_ORDER:
        return s
    for k, mapped in _SEV_CN.items():
        if k in s:
            return mapped
    return "info"


def _split_loc(loc: str):
    """`path:line` -> (path, line)。Windows 盘符里的 `C:` 不算分隔。"""
    s = str(loc or "").strip()
    if not s:
        return ("", 0)
    head, sep, tail = s.rpartition(":")
    if sep and tail.isdigit():
        return (head, int(tail))
    return (s, 0)


def _norm_row(lane: str, it: dict) -> dict:
    f, ln = str(it.get("file") or ""), int(it.get("line") or 0)
    loc = it.get("location") or it.get("where") or ""
    if loc and not f:
        f, ln = _split_loc(loc)
    return {"file": f.replace("\\", "/") if f else "",
            "line": ln,
            "cwe": str(it.get("cwe") or it.get("owasp") or it.get("rule")
                       or it.get("category") or ""),
            "severity": _sev(it.get("severity")),
            "title": str(it.get("title") or it.get("what") or it.get("desc")
                         or it.get("evidence") or it.get("snip")
                         or it.get("snippet") or "")[:160],
            "fix": str(it.get("fix") or it.get("advice") or "")[:160],
            "lane": lane,
            "kind": "candidate" if lane in CANDIDATE_LANES else "finding",
            "confidence": it.get("confidence")}


def _lane_rows(lane: str, d) -> list:
    if not isinstance(d, dict):
        return []
    out = []
    for key in ("vulnerabilities", "findings", "rows", "items", "results", "top", "candidates"):
        seq = d.get(key)
        if isinstance(seq, list):
            out += [_norm_row(lane, x) for x in seq if isinstance(x, dict)]
    probes = d.get("probes")
    if isinstance(probes, list):
        for pr in probes:
            if not isinstance(pr, dict):
                continue
            for hit in (pr.get("hits") or []):
                if isinstance(hit, dict):
                    row = _norm_row(lane, hit)
                    row["cwe"] = row["cwe"] or str(pr.get("owasp") or "")
                    out.append(row)
    return [r for r in out if r["file"] or r["title"]]


FLOW_EXTS = {".py", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".sh"}
FLOW_SKIP = {"pyembed", "node_modules", "state", "outputs", ".git", ".scratch",
             ".archive", ".backups", "__pycache__", "store", "vendor", "_upstream"}
# 生产面优先：先喂这些目录，再补其余。否则按路径序会把 `.archive` 的退役代码先喂满。
FLOW_ROOTS = ("gbt_allinone", "tools", "holo_pet_w3", "runtime", "gbt_commander")


def _collect_files(root, limit: int = 200, cap_bytes: int = 200_000) -> tuple:
    """给 `pentest_flow op=surface` 喂 {路径: 文本}。

    **口径（必须如实写进回执）**：候选文件可能多于 `limit`，只喂前 `limit` 个；
    没喂到的文件**没有扫过**，不等于干净。返回 (files, unread, sample_note, stats)。
    """
    base = Path(root or ROOT)
    files, unread = {}, []
    if not base.is_dir():
        return files, [{"file": str(base), "why": "目标目录不存在"}], "未扫", {
            "eligible": 0, "fed": 0, "not_fed": 0,
            "too_large": 0, "too_large_files": [],
        }
    cands, seen_paths = [], set()
    for sub in FLOW_ROOTS:
        d = base / sub
        if d.is_dir():
            for pth in sorted(d.rglob("*")):
                key = pth.as_posix()
                if key not in seen_paths:
                    seen_paths.add(key)
                    cands.append(pth)
    for pth in sorted(base.rglob("*")):
        key = pth.as_posix()
        if key not in seen_paths:
            seen_paths.add(key)
            cands.append(pth)
    eligible, too_large = [], []
    for pth in cands:
        if not pth.is_file() or pth.suffix.lower() not in FLOW_EXTS:
            continue
        if FLOW_SKIP & set(pth.parts):
            continue
        try:
            rel = pth.relative_to(base).as_posix()
            if pth.stat().st_size > cap_bytes:
                too_large.append(rel)
                continue
        except OSError as e:
            unread.append({"file": str(pth), "why": type(e).__name__})
            continue
        eligible.append((rel, pth))
    for rel, pth in eligible[:limit]:
        try:
            files[rel] = pth.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            unread.append({"file": str(pth), "why": type(e).__name__})
    not_fed = max(0, len(eligible) - len(files))
    stats = {"eligible": len(eligible), "fed": len(files), "not_fed": not_fed,
             "too_large": len(too_large), "too_large_files": too_large[:20]}
    if not_fed:
        note = ("只喂前 %d 个（候选 %d 个）；未喂的 %d 个**没扫过**，不等于干净"
                % (limit, len(eligible), not_fed))
    else:
        note = ("候选 %d 个，全部喂入；另有 %d 个超限大件未扫"
                % (len(eligible), len(too_large)))
    return files, unread, note, stats


def _run_lane(spec: dict) -> dict:
    """跑一条触手。**失败必须带原因**，不许折成「0 条 = 干净」。"""
    from . import api
    t0 = time.time()
    rec = {"id": spec["id"], "cap": spec["cap"], "what": spec["what"]}
    params = dict(spec.get("params") or {})
    if spec.get("needs_files"):
        files, unread, note, stats = _collect_files(spec.get("root") or ROOT)
        params["files"] = files
        rec["files_fed"] = len(files)
        rec["files_eligible"] = stats["eligible"]
        rec["files_not_fed"] = stats["not_fed"]
        rec["files_too_large"] = stats["too_large"]
        rec["files_too_large_list"] = stats["too_large_files"]
        rec["files_unread"] = unread[:20]
        rec["sample_note"] = note
    try:
        env = api.run_task(spec["cap"], params)
        res = (env or {}).get("result") or {}
        body = res.get("result") if isinstance(res.get("result"), dict) else res
        rec["status"] = (env or {}).get("status")
        rec["ok"] = bool(isinstance(body, dict) and body.get("ok"))
        rec["error"] = None if rec["ok"] else str((body or {}).get("error")
                                                  or (body or {}).get("reason") or "")[:200]
        # 报告截断必须进覆盖账：`sec_scan` 默认只回 20 条，不记账就会把「只看了 20 条」
        # 读成「全仓只有 20 条」。这里把 total/shown/truncated 原样带出。
        if isinstance(body, dict):
            for _k in ("total", "shown", "truncated", "limit_note"):
                if _k in body:
                    rec[_k] = body[_k]
        # 覆盖账必须取**扫描那一步**的回执；`then` 步（取行）不带 coverage
        cov0 = (body or {}).get("coverage")
        then = spec.get("then")
        if then and rec["ok"]:
            env2 = api.run_task(then["cap"], dict(then.get("params") or {}))
            res2 = (env2 or {}).get("result") or {}
            body2 = res2.get("result") if isinstance(res2.get("result"), dict) else res2
            if isinstance(body2, dict) and body2.get("ok"):
                body = body2
            else:
                rec["then_error"] = str((body2 or {}).get("error") or "then 步失败")[:160]
        rec["rows"] = _lane_rows(spec["id"], body)
        rec["coverage"] = cov0 if isinstance(cov0, dict) else None
        # 面测绘这类触手给的是**指标**不是发现，单独记，别混进 findings
        if isinstance(body, dict) and isinstance(body.get("attack_surface"), dict):
            rec["metrics"] = {"attack_surface": body["attack_surface"],
                              "risk_level": body.get("risk_level"),
                              "risk_density": body.get("risk_density"),
                              "files_scanned": body.get("files_scanned")}
    except Exception as e:  # noqa: BLE001
        rec.update({"ok": False, "status": "exception", "rows": [],
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])})
    rec["ms"] = round((time.time() - t0) * 1000, 1)
    rec["findings_n"] = len(rec.get("rows") or [])
    return rec


def _merge(lanes: list) -> tuple:
    """按 (文件, 行, CWE/规则) 去重；同一条留最高严重度并合并来源。

    **候选与已证分开算**（口径照 `No exploit, no report`）：
      · `findings`   = 扫描器直接给出的命中（仍待复核，但已是「看到的」）
      · `candidates` = 污点近似/启发式推出来的**假设**，没有 PoC 就不许当漏洞报
    把两者混在一张表里，会让报告看起来比实际更确定 —— 这是本仓明令禁止的那种错报。
    """
    seen = {}
    for lane in lanes:
        for r in lane.get("rows") or []:
            key = (r["file"].lower(), r["line"], r["cwe"].lower(), r.get("kind") or "finding")
            cur = seen.get(key)
            if cur is None:
                seen[key] = dict(r, lanes=[r["lane"]])
            else:
                if SEV_ORDER[r["severity"]] < SEV_ORDER[cur["severity"]]:
                    cur["severity"], cur["title"] = r["severity"], r["title"] or cur["title"]
                if r["lane"] not in cur["lanes"]:
                    cur["lanes"].append(r["lane"])
    rows = sorted(seen.values(), key=lambda x: (SEV_ORDER[x["severity"]], x["file"], x["line"]))
    confirmed = [r for r in rows if r.get("kind") != "candidate"]
    cands = [r for r in rows if r.get("kind") == "candidate"]
    by = {}
    for r in confirmed:
        by[r["severity"]] = by.get(r["severity"], 0) + 1
    return confirmed, cands, by


def _coverage(lanes: list) -> dict:
    """覆盖账：每条触手自己的覆盖率 + 整链是否闭合。"""
    unread = []
    for lane in lanes:
        if not lane.get("ok"):
            unread.append({"lane": lane["id"], "why": lane.get("error") or lane.get("status")})
            continue
        fed = lane.get("files_fed")
        eligible = lane.get("files_eligible")
        if isinstance(fed, int) and isinstance(eligible, int) and fed < eligible:
            unread.append({"lane": lane["id"],
                           "why": "只喂了 %d/%d 个候选文件（未喂的没扫过）" % (fed, eligible),
                           "missed": eligible - fed})
        too_large = lane.get("files_too_large")
        if isinstance(too_large, int) and too_large > 0:
            unread.append({"lane": lane["id"],
                           "why": "%d 个大件超限未扫" % too_large,
                           "missed": too_large})
        if lane.get("truncated"):
            _shown = lane.get("shown")
            _total = lane.get("total")
            unread.append({"lane": lane["id"],
                           "why": "报告被截断：shown=%s / total=%s" % (_shown, _total),
                           "missed": (max(0, int(_total) - int(_shown))
                                      if isinstance(_total, int) and isinstance(_shown, int)
                                      else None)})
        cov = lane.get("coverage") or {}
        if isinstance(cov.get("rate"), (int, float)) and cov["rate"] < 1.0:
            unread.append({"lane": lane["id"], "why": "覆盖率 %.4f（有没扫到的）" % cov["rate"],
                           "missed": cov.get("missed")})
    scanned = []
    for lane in lanes:
        cov = lane.get("coverage") or {}
        if isinstance(cov.get("scanned"), int):
            scanned.append(cov["scanned"])
        if isinstance(lane.get("files_fed"), int):
            scanned.append(lane["files_fed"])
    return {"lanes_ok": sum(1 for x in lanes if x.get("ok")), "lanes_n": len(lanes),
            "files_scanned": max(scanned) if scanned else 0, "unread": unread,
            "coverage_complete": not unread}


def _write_report(payload: dict) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = OUT / ("%s-%s.json" % (payload.get("op") or "hunt", stamp))
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    with open(path, encoding="utf-8") as fh:
        assert json.load(fh)["op"] == payload["op"]
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _hunt_body(op: str, root: str = "", lanes: list | None = None,
               parallel: bool = False, workers: int = 0) -> dict:
    t0 = time.time()
    want = [x for x in (lanes or []) if x]
    specs = [dict(s) for s in LANES if not want or s["id"] in want]
    for s in specs:
        if s.pop("needs_root", False):
            pp = dict(s.get("params") or {})
            pp.setdefault("target", str(root or ROOT))
            s["params"] = pp
        if s.get("needs_files"):
            s["root"] = str(root or ROOT)
    if not specs:
        return {"ok": False, "reason": "unknown_lane", "how": "可用触手：%s"
                % ", ".join(s["id"] for s in LANES)}
    if parallel:
        n = max(1, min(int(workers or len(specs)), len(specs)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
            results = list(ex.map(_run_lane, specs))
    else:
        results = [_run_lane(s) for s in specs]
    rows, cands, by = _merge(results)
    cov = _coverage(results)
    payload = {"ok": True, "kind": "offense_ops", "op": op,
               "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "root": str(root or ROOT),
               "lanes": [{k: v for k, v in r.items() if k != "rows"} for r in results],
               "findings": rows,
               "findings_n": len(rows), "by_severity": by,
               "candidates": cands,
               "candidates_n": len(cands),
               "candidates_note": "候选=污点近似/启发式假设，**没有 PoC 不算漏洞**；"
                                  "要进报告先过 pentest_flow op=validate",
               "metrics": {r["id"]: r.get("metrics") for r in results if r.get("metrics")},
               "coverage": cov,
               "coverage_complete": cov["coverage_complete"],
               "gate": "本链只读、零作用域、不出网；要票的只有危险作用域与资金转账",
               "native": True,
               "elapsed_ms": round((time.time() - t0) * 1000, 1)}
    payload["path"] = _write_report(payload)
    return payload


def hunt(root: str = "", lanes=None, **kw) -> dict:
    """一条原生挖洞链：按 lane 串行跑完所有本仓扫描器，合并去重 + 覆盖账。"""
    return _hunt_body("hunt", root, lanes)


def swarm(root: str = "", lanes=None, workers: int = 0, **kw) -> dict:
    """触手大军：多条扫描链**并行**跑，各出独立回执，合并时去重并记覆盖账。

    边界（如实写）：这里是**同进程线程级并行**；要跨进程/断点续跑，
    走 `tools/swarm.py`（DAG + 租约）或 `tools/tentacle_dispatch.py`（独立进程车队）。
    """
    return _hunt_body("swarm", root, lanes, parallel=True, workers=workers)


def coverage(report: str = "") -> dict:
    """读最近一份挖洞报告，只回答「覆盖到哪、哪里没覆盖到」。"""
    if not report:
        if not OUT.is_dir():
            return {"ok": False, "reason": "no_report", "how": "先跑 offense_ops op=hunt 或 op=swarm"}
        cands = sorted(OUT.glob("*.json"))
        if not cands:
            return {"ok": False, "reason": "no_report", "how": "先跑 offense_ops op=hunt 或 op=swarm"}
        report = str(cands[-1])
    p = Path(report)
    if not p.is_absolute():
        p = ROOT / p
    if not p.is_file():
        return {"ok": False, "reason": "report_missing", "path": str(p)}
    d = json.loads(p.read_text(encoding="utf-8"))
    cov = d.get("coverage") or {}
    return {"ok": True, "op": "coverage", "report": str(p),
            "at": d.get("at"), "lanes": d.get("lanes"), "findings_n": d.get("findings_n"),
            "by_severity": d.get("by_severity"), "coverage": cov,
            "coverage_complete": d.get("coverage_complete"),
            "honesty": ("unread 非空 => 结论只对扫到的那部分成立；"
                        "**读不到 != 没问题**")}


def knowledge() -> dict:
    """主脑的挖洞方法论（机器可读）。与 skills/gbt-pentest 同源，口径一致。"""
    return {"ok": True, "op": "knowledge", "kind": "offense_ops",
            "phases": [
                {"阶段": "① 定面", "做什么": "资产/入口/信任边界清单化", "判据": "每个入口能指回文件:行"},
                {"阶段": "② 取证扫描", "做什么": "按 CWE 类跑模式库 + AST 语义检查", "判据": "命中带 file/line/snippet"},
                {"阶段": "③ 去伪", "做什么": "交叉复核：同一条至少两路读法", "判据": "不一致则第三路仲裁"},
                {"阶段": "④ 验证", "做什么": "只对可复现的定级", "判据": "复现步骤跑得通才算 exploited"},
                {"阶段": "⑤ 成链", "做什么": "把单点拼成攻击路径（入口→权限→影响）", "判据": "每跳有证据"},
                {"阶段": "⑥ 报告", "做什么": "结论→证据→影响→修复四段", "判据": "能复跑；第三方信息脱敏"},
            ],
            "cwe_map": {
                "CWE-78": "命令注入：shell=True / os.system / 拼接命令",
                "CWE-79": "XSS：未转义输出到 HTML/JS 上下文",
                "CWE-89": "SQL 注入：字符串拼 SQL",
                "CWE-22": "路径穿越：用户输入直接 join 路径",
                "CWE-502": "不安全反序列化：pickle/yaml.load/eval",
                "CWE-798": "硬编码凭据",
                "CWE-200": "敏感信息暴露：日志/回执/错误页",
                "CWE-352": "CSRF：状态变更无 token",
                "CWE-918": "SSRF：用户控制 URL 出网",
                "CWE-1333": "ReDoS：灾难性回溯正则",
            },
            "llm_top10": ["提示注入", "不安全输出处理", "训练数据投毒", "模型拒绝服务",
                          "供应链", "敏感信息泄露", "不安全插件", "过度代理",
                          "过度依赖", "模型窃取"],
            "evidence": ["时间戳", "命令/请求原文", "响应要点（脱敏）", "复现步骤",
                         "影响范围", "修复建议"],
            "rules": ["没有复现步骤的发现标「未验证」，不许写成已确认",
                      "读不到的文件必须进 unread；不许把「没扫到」写成「干净」",
                      "定级用 CWE/CVSS 口径，不自编",
                      "只打授权面；越界即停并如实报"],
            "native_route": [{"要什么": "面测绘", "走": "sec_surface / pentest_flow op=surface"},
                             {"要什么": "模式库", "走": "sec_scan"},
                             {"要什么": "多阶段 SAST + 证据", "走": "code_audit op=scan"},
                             {"要什么": "LLM 面（实测）", "走": "llm_redteam op=selfcheck"},
                             {"要什么": "LLM 攻击矩阵（目录）", "走": "llm_redteam op=matrix"},
                             {"要什么": "成链", "走": "sec_chain"},
                             {"要什么": "一根命令跑全链", "走": "offense_ops op=hunt"},
                             {"要什么": "多触手并行", "走": "offense_ops op=swarm"}],
            "headline": "原生优先：全在本机跑，不引云、不装外挂扫描器、不出网"}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "hunt":
        return hunt(kw.get("root") or "", kw.get("lanes"))
    if o == "swarm":
        return swarm(kw.get("root") or "", kw.get("lanes"), kw.get("workers") or 0)
    if o == "coverage":
        return coverage(kw.get("report") or "")
    if o == "knowledge":
        return knowledge()
    if o == "plan":
        return plan(kw.get("target") or "", kw.get("scope") or "")
    if o == "roles":
        return roles()
    if o == "tools":
        return tools()
    if o == "evidence":
        return evidence()
    if o == "memory":
        return memory()
    if o == "gate":
        return gate(kw.get("action") or "")
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("target") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
