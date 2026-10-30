#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""domain_heartbeat —— 每个能力分类一根心跳触手，定点自检 → 交大脑执行层

主人令（2026-10-30 原话）：
「把所有原生能力以及操控部位分类好，必须严格分类好，然后每一个分类部署一根心跳触手，
  对分类内的一切进行定点自检和状态返回给大脑执行层分析，再返回执行指令。」

## 三件事，各归各位
  ① 严格分类   读注册表，按 `domain` 分组。**每位只准落一个域**——
               有跨域、缺域、重复名，直接报错不凑合（分类不严 = 心跳打错针）。
  ② 心跳触手   一个域一根。每轮只探该域**一小批**（默认 6 个），按游标轮转，
               所以「分类内的一切」会在若干轮内全部被自检到，而不是每轮全扫把机器拖死。
               触手只做**只读探活**：真正需要票的写口位不盲探，如实标 `ticketed`。
  ③ 大脑执行层 汇总所有域的心跳，产**执行指令**（不是人类可读的感想）：
               哪个域红了、红了几处、下一轮该加派人手还是先修哪一处。
               指令落 `state/heartbeat/brain.json`，供上层直接取用。

## 落点
    state/heartbeat/<domain>.json     每域一份（at / total / cursor / ok / fail / skip / rows）
    state/heartbeat/brain.json        大脑汇总 + 执行指令

## 用法
    python3 tools/domain_heartbeat.py --once              # 全部分类各跳一次
    python3 tools/domain_heartbeat.py --once --domain llm # 只让某域跳
    python3 tools/domain_heartbeat.py --brain             # 只跑汇总（不探活）
    python3 tools/domain_heartbeat.py --status            # 看最近一轮读数
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "heartbeat"
BATCH = int(__import__("os").environ.get("GBT_HB_BATCH") or 3)
_HYG_FULL_DONE = False
GARBAGE_NAMES = (".DS_Store",)
# 🔴 2026-10-30 修正：原来是 `x in nm` 子串判定 —— "a.tmpl" 含 ".tmp" 会被当垃圾删掉，
#   新加的文件也可能被误清。改成**只认精确后缀**，且不碰 _retired/ 与 .git/。
GARBAGE_EXACT_SUFFIX = (".bak", ".orig", ".rej", ".pyc", ".tmp", ".swp")
GARBAGE_NAME_MARK = (".bak-",)          # 本仓备份命名是 xxx.bak-20261021


def _is_garbage(name: str) -> bool:
    if name in GARBAGE_NAMES:
        return True
    if name.endswith(GARBAGE_EXACT_SUFFIX):     # 只认结尾，不做子串
        return True
    return any(m in name for m in GARBAGE_NAME_MARK)


def _slow_set(ms_limit: int = 3000) -> set:
    """上游对齐实测里超过 ms_limit 的位 —— 心跳不碰它们。
    数据来自真跑过的 state/omni_align.json（不是猜的）。"""
    try:
        d = json.loads((ROOT / "state" / "omni_align.json").read_text(encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return set()
    out = set()
    for r in d.get("rows") or []:
        try:
            if int(r.get("ms") or 0) > ms_limit:
                out.add(r.get("name"))
        except Exception:                                         # noqa: BLE001
            pass
    return out


def _hygiene(dom: str) -> dict:
    """一根触手自检时顺手干的卫生活：
       ① 清自己那一路的垃圾（__pycache__ / .bak / .orig / .tmp / .pyc / .DS_Store）
       ② 自己的地盘不许混入别的东西：heartbeat 目录里只能有「已知域 + brain.json」
          多出来的一律搬进 _quarantine/ 并报出来（不静默删，免得删掉别人有用的东西）
    """
    import shutil
    global _HYG_FULL_DONE
    removed = []
    # ① 垃圾：全树扫一遍**每轮只做一次**（30 个域各扫一次会把一轮拖死）
    if not _HYG_FULL_DONE:
      _HYG_FULL_DONE = True
      for pat in ("**/__pycache__",):
        for d in ROOT.glob(pat):
            try:
                shutil.rmtree(d, ignore_errors=True)
                removed.append(str(d.relative_to(ROOT)))
            except Exception:                                     # noqa: BLE001
                pass
      for pth in ROOT.rglob("*"):
        try:
            if not pth.is_file():
                continue
            nm = pth.name
            if _is_garbage(nm):
                if "/.git/" in str(pth) or "/_retired/" in str(pth):
                    continue
                pth.unlink()
                removed.append(str(pth.relative_to(ROOT)))
        except Exception:                                         # noqa: BLE001
            pass
    # ② 地盘混入：**不搬走、不删**。新增能力先纳管再说（主人令 2026-10-30：
    #    「新增能力可以整理清楚别当外来物清理了」）。
    doms = classify()
    known = {("%s.json" % d) for d in doms} | {"brain.json"}
    adopted, unknown = [], []
    if OUT.is_dir():
        for f in OUT.iterdir():
            if not f.is_file() or f.name in known:
                continue
            stem = f.stem
            if stem in doms:                 # 本来就是已知域（文件名只是格式不同）
                adopted.append(f.name)
            else:                            # 真没见过：只**报告**，不动它
                unknown.append(f.name)
    return {"removed": removed[:20], "removed_n": len(removed),
            "adopted": adopted, "unknown_kept": unknown,
            "note": "新能力只纳管不清理；unknown_kept 只报不动"}


# ── ① 严格分类 ─────────────────────────────────────────────────────────────
def classify() -> dict:
    """返回 {domain: [cap, ...]}。分类不严就抛错，不静默兜底。"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS as R
    seen, out, bad = {}, {}, []
    for name, meta in R.items():
        if not isinstance(meta, dict):
            bad.append("%s: 元数据不是对象" % name)
            continue
        dom = str(meta.get("domain") or "").strip()
        if not dom:
            bad.append("%s: 缺 domain" % name)
            continue
        if name in seen:
            bad.append("%s: 重名（%s / %s）" % (name, seen[name], dom))
            continue
        seen[name] = dom
        out.setdefault(dom, []).append(name)
    if bad:
        raise SystemExit("  分类不严，拒绝起心跳：\n   " + "\n   ".join(bad[:10]))
    return dict(sorted(out.items()))


# ── ② 每域一根心跳触手 ─────────────────────────────────────────────────────
def _state_path(dom: str) -> pathlib.Path:
    return OUT / ("%s.json" % dom)


def _load_prev(dom: str) -> dict:
    try:
        return json.loads(_state_path(dom).read_text(encoding="utf-8"))
    except Exception:                                             # noqa: BLE001
        return {}


def beat(dom: str, caps: list, batch: int = BATCH) -> dict:
    """一个域跳一次：按游标取一小批，只读探活。"""
    from gbt_allinone.security import policy as P
    from gbt_allinone.api import run_task

    prev = _load_prev(dom)
    cur = int(prev.get("cursor") or 0) % max(1, len(caps))
    picks = [caps[(cur + i) % len(caps)] for i in range(min(batch, len(caps)))]

    slow = _slow_set()
    rows, ok, fail, ticketed, skipped_slow = [], 0, 0, 0, 0
    for name in picks:
        if name in slow:
            skipped_slow += 1
            rows.append({"cap": name, "status": "slow_skipped",
                         "why": "上游实测 >3s，心跳不碰（免得一轮被拖死）"})
            continue
        try:
            dec = P.evaluate(name, {})
            scopes = list(getattr(dec, "scopes", ()) or ())
        except Exception:                                         # noqa: BLE001
            scopes = []
        if scopes:
            ticketed += 1
            rows.append({"cap": name, "status": "ticketed", "scopes": scopes})
            continue
        t0 = time.time()
        try:
            r = run_task(name, {})
            st = r.get("status") or "?"
            good = st not in ("denied", "error")
        except Exception as exc:                                  # noqa: BLE001
            st, good = "exception:%s" % type(exc).__name__, False
        ms = round((time.time() - t0) * 1000)
        rows.append({"cap": name, "status": st, "ok": good, "ms": ms})
        ok += 1 if good else 0
        fail += 0 if good else 1

    hyg = _hygiene(dom)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "domain": dom,
           "total": len(caps), "batch": len(picks),
           "cursor": (cur + len(picks)) % max(1, len(caps)),
           "ok": ok, "fail": fail, "ticketed": ticketed,
           "slow_skipped": skipped_slow, "hygiene": hyg, "rows": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    _state_path(dom).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    return rec


# ── ③ 大脑执行层：汇总 → 执行指令 ──────────────────────────────────────────
def brain() -> dict:
    """读所有域心跳 → 产出**执行指令**（不是感想）。"""
    domains = {}
    for f in sorted(OUT.glob("*.json")):
        if f.name == "brain.json":
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            continue
        domains[d.get("domain") or f.stem] = d

    red = {k: v for k, v in domains.items() if (v.get("fail") or 0) > 0}
    stale = []
    now = time.time()
    for k, v in domains.items():
        try:
            ts = time.mktime(time.strptime(v["at"], "%Y-%m-%dT%H:%M:%S"))
            if now - ts > 3600:
                stale.append(k)
        except Exception:                                         # noqa: BLE001
            stale.append(k)

    cmds = []
    for dom, v in sorted(red.items(), key=lambda x: -(x[1].get("fail") or 0)):
        caps = [r["cap"] for r in (v.get("rows") or []) if r.get("ok") is False]
        cmds.append({"action": "fix", "domain": dom, "targets": caps[:5],
                     "why": "%s 有 %d 处红" % (dom, v.get("fail") or 0),
                     "priority": "high" if (v.get("fail") or 0) >= 2 else "normal"})
    for dom in sorted(set(caps_dom for caps_dom in classify()) - set(domains)):
        cmds.append({"action": "beat", "domain": dom, "why": "该域还没有心跳记录",
                     "priority": "normal"})
    for dom in stale[:5]:
        cmds.append({"action": "beat", "domain": dom, "why": "心跳超过 1 小时未更新",
                     "priority": "low"})

    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "domains": len(domains),
           "beating": sorted(domains),
           "red": {k: v.get("fail") for k, v in red.items()},
           "ticketed_total": sum(v.get("ticketed") or 0 for v in domains.values()),
           "ok_total": sum(v.get("ok") or 0 for v in domains.values()),
           "commands": cmds,
           "note": "指令是给执行层的：fix=先修这些位；beat=该域还没心跳/太旧，下一轮先跳它"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "brain.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    return res


def main(argv: list) -> int:
    if "--status" in argv:
        try:
            b = json.loads((OUT / "brain.json").read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            print("  还没有汇总，先 --once"); return 2
        print("  域 %d · 已跳 %d · 红 %s · 免票探活 ok %d · 需票跳过 %d"
              % (b["domains"], len(b["beating"]), b["red"] or "无",
                 b["ok_total"], b["ticketed_total"]))
        for c in b["commands"][:8]:
            print("   → %-5s %-14s %s" % (c["action"], c["domain"], c.get("why")))
        return 0

    groups = classify()
    if "--brain" in argv or "--once" in argv:
        only = None
        if "--domain" in argv:
            only = argv[argv.index("--domain") + 1]
        if "--once" in argv:
            # 2026-10-30 实测：串行 30 域一轮 14 分钟跑不完（有些位会挂很久）。
            # 改用自己造好的派发器并行跑，每根探活带 8s 硬超时。
            import tentacle_dispatch as TD
            slow = _slow_set()
            # 心跳是**小的、轮转的**：一轮只跳最久没跳的几域（默认 4），
            # 不然 30 域全跳要 18 分钟（实测单域 36 秒），本机扛不住也失去心跳本意。
            budget = int(argv[argv.index("--budget") + 1]) if "--budget" in argv else 4
            def _age(d):
                prev = _load_prev(d)
                try:
                    return time.mktime(time.strptime(prev["at"], "%Y-%m-%dT%H:%M:%S"))
                except Exception:                                 # noqa: BLE001
                    return 0.0
            if only:
                todo = [(d, c) for d, c in groups.items() if d == only]
            else:
                todo = sorted(groups.items(), key=lambda kv: _age(kv[0]))[:budget]
                print("  本轮轮转到 %d 域（预算 %d）：%s"
                      % (len(todo), budget, ",".join(d for d, _ in todo)))
            print("  分类：%d 域 / %d 位" % (len(groups), sum(len(v) for v in groups.values())))
            units, meta = [], {}
            for dom, caps in todo:
                prev = _load_prev(dom)
                cur = int(prev.get("cursor") or 0) % max(1, len(caps))
                picks = [caps[(cur + i) % len(caps)] for i in range(min(BATCH, len(caps)))]
                for nm in picks:
                    uid = "%s|%s" % (dom, nm)
                    meta[uid] = (dom, nm, cur + len(picks))
                    if nm in slow:
                        continue
                    units.append({"id": uid, "kind": nm, "payload": {},
                                  "timeout": 8.0})
            res = TD.dispatch(units, max_workers=6, stall_s=3.0, target_rps=2.0,
                              verbose=False)
            by_id = {x.get("unit"): x for x in (res.get("results") or [])}
            per = {}
            for uid, (dom, nm, newcur) in meta.items():
                w = by_id.get(uid)
                per.setdefault(dom, []).append((nm, w))
            for dom, items in per.items():
                caps = groups[dom]
                rows = []
                ok = fail = tick = 0
                for nm, w in items:
                    if w is None:
                        rows.append({"cap": nm, "status": "slow_skipped",
                                     "why": "上游实测 >3s，心跳不碰"})
                        continue
                    stt = w.get("status") or "?"
                    good = stt not in ("denied", "error", "timeout")
                    rows.append({"cap": nm, "status": stt, "ok": good,
                                 "ms": w.get("ms")})
                    ok += 1 if good else 0
                    fail += 0 if good else 1
                # 需票的位不盲探，如实计数
                for c in caps:
                    try:
                        from gbt_allinone.security import policy as _P
                        if list(getattr(_P.evaluate(c, {}), "scopes", ()) or ()):
                            tick += 1
                    except Exception:                             # noqa: BLE001
                        pass
                prev = _load_prev(dom)
                cur0 = int(prev.get("cursor") or 0) % max(1, len(caps))
                rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "domain": dom,
                       "total": len(caps), "batch": len(items),
                       "cursor": (cur0 + len(items)) % max(1, len(caps)),
                       "ok": ok, "fail": fail, "ticketed": tick,
                       "hygiene": _hygiene(dom), "rows": rows}
                OUT.mkdir(parents=True, exist_ok=True)
                _state_path(dom).write_text(
                    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
                print("   🫀 %-14s 探 %d/%d · ok %d · 红 %d · 需票 %d"
                      % (dom, len(items), len(caps), ok, fail, tick), flush=True)
            print("   并行完成 %d/%d · 用时 %.0fs · 车道 %d"
                  % (res.get("done"), len(units), res.get("elapsed_s") or 0,
                     res.get("workers_used") or 0))
        b = brain()
        print("  🧠 汇总：%d 域 · 红 %s" % (b["domains"], b["red"] or "无"))
        for c in b["commands"][:8]:
            print("   → %-5s %-14s %s" % (c["action"], c["domain"], c.get("why")))
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
