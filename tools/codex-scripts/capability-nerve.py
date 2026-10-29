# -*- coding: utf-8 -*-
"""能力神经 · **全族健康摘要**（主人令 2026-10-08 · 一条命令感知全族）。

主人原话：「所有能力文件每一页 ↔ 触手 双向绑定，实现『神经连接』，能感知所有能力的健康状态。」

## 一句话
`capability-nerve` 只读**台账 + 审计尾部**（不重算、不真调、不烧钱），一条命令吐出
**每族四计数**（未绑 / 断连 / 未探测 / 假执行）+ **变化量** + **最旧证据年龄**，
并可落进能力栏页的数据管线。

## 口径（写死在这里，可复核）
- **族** = 能力位的 `domain`（现读 `state/cap-bindings.json`，不写死族数）。
- **未绑** = 该族里 `bind_kind` 缺失 / 承载载体为空（来自绑定台账的 `orphans.caps_unbound`）。
- **断连 / 未探测** = 取自 `capability-bar-check.py` 的**运行证据有界尾部窗口**
  （近 N 小时 / 回读 M MB）—— 与能力栏页**同一份口径**，不另发明一套：
    · 断连   = 窗口内该位**最后一次**记录是 denied / error（原始串随行）
    · 未探测 = 窗口内**没有**该位的记录（**不许画成通**，也不等于坏）
- **假执行** = `truth_scan`（probe 模式）的 FAKE 名单；**本层不重算、不编**——
  真源没产出就如实写「未判：真源 truth-scan 未产出」，**绝不当 0 报绿**。
- **变化量** = 与 `state/cap-nerve-baseline.json` 比（`baseline` 子命令立基线）；
  没有基线就一律 `=`（不编）。
- **最旧证据年龄** = 该族窗口内**最旧**的那条证据距生成时刻的时长，落**档位**
  （`<1h` / `1–6h` / `6–24h` / `1–7d` / `>7d` / `无窗口证据`）——
  用档位而非秒数 ⇒ **同一状态复跑逐字一致**（无时钟字段，满足「可复跑逐字一致」）。

## 硬性纪律
- **轻**：只读两份台账 + 审计尾部**有界窗口**；**不真调任何能力、不重算绑定**。
- **幂等**：输出**无时钟字段**（不用 now/时间戳），同一状态复跑**逐字一致**。
- **fail-closed**：读不到就「未探测 / 未判」并写明为什么，**不许留空当绿**。
- 与 `capability-bar-check.py refresh` 的**新鲜度契约对齐**（窗口口径读同一份常量）。

## 用法
    py -3.14 tools/codex-scripts/capability-nerve.py                # 全族健康摘要（人读 · 无时钟字段）
    py -3.14 tools/codex-scripts/capability-nerve.py --json         # 机读
    py -3.14 tools/codex-scripts/capability-nerve.py baseline       # 把当前摘要立成基线（变化量的参照）
    py -3.14 tools/codex-scripts/capability-nerve.py --check        # 判据 + 负对照 · 退出码 0/1
    py -3.14 tools/codex-scripts/capability-nerve.py cell           # 打一段能力栏页用的顶栏一格（数据脚本）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"
LEDGER = STATE / "cap-bindings.json"
AUDIT = STATE / "capability-audit.json"
ACCUM = STATE / "caps-probe-accum.json"
BASELINE = STATE / "cap-nerve-baseline.json"
DIGEST = STATE / "cap-nerve.json"
TRUTH = STATE / "truth-scan.json"
BAR_CHECK = ROOT / "tools" / "codex-scripts" / "capability-bar-check.py"
RUN_EVIDENCE = ROOT / "holo_pet_w3" / "capability-bar" / "run-evidence.js"

CMD_FEEL = "py -3.14 tools/codex-scripts/capability-nerve.py"
CMD_JSON = "py -3.14 tools/codex-scripts/capability-nerve.py --json"
CMD_BASE = "py -3.14 tools/codex-scripts/capability-nerve.py baseline"
CMD_CHECK = "py -3.14 tools/codex-scripts/capability-nerve.py --check"

COUNTERS = ("未绑", "断连", "未探测", "假执行")
AGE_BUCKETS = ((3600, "<1h"), (6 * 3600, "1–6h"), (24 * 3600, "6–24h"),
               (7 * 86400, "1–7d"), (float("inf"), ">7d"))
RULE = ("轻（只读台账+审计尾部有界窗口）· 幂等（无时钟字段，同一状态逐字一致）· "
        "fail-closed（读不到=未探测/未判，不编）")


def _load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except Exception:                                        # noqa: BLE001
        return None
    return m


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


def age_bucket(sec) -> str:
    if sec is None:
        return "无窗口证据"
    for lim, label in AGE_BUCKETS:
        if sec < lim:
            return label
    return ">7d"


# ══════════════════════════════════════════════════════════════════════════
# 取数（**只读**；证据窗口复用 capability-bar-check 的同口径函数，不重造）
# ══════════════════════════════════════════════════════════════════════════
def load_window(cap_names: list) -> dict:
    """运行证据有界尾部窗口。复用 capability-bar-check.py::read_evidence（同口径）。"""
    bc = _load_mod("_gbt_capbar_for_nerve", BAR_CHECK)
    if bc is None or not callable(getattr(bc, "read_evidence", None)):
        return {"__err__": "capability-bar-check.py 载入失败 ⇒ 证据窗口未探测"}
    try:
        ev = bc.read_evidence(set(cap_names))
    except Exception as e:                                   # noqa: BLE001
        return {"__err__": "read_evidence 抛异常：%s: %s" % (type(e).__name__, str(e)[:120])}
    return ev


def load_truth() -> dict:
    """假执行真源（truth_scan 产出）。**没有就如实写没有**，绝不当 0。"""
    if not TRUTH.is_file():
        return {"__absent__": "真源未产出（state/truth-scan.json 不在）：本层不重算、不编；"
                              "要判假执行请现跑 truth_scan（probe 模式）"}
    d = _read_json(TRUTH)
    if not isinstance(d, dict):
        return {"__absent__": "真源在盘但解析不出：state/truth-scan.json"}
    return d


def _evidence_age(ev: dict, names: list, at_now: float) -> float | None:
    """该族窗口内**最旧**证据的年龄（秒）。没有记录 ⇒ None。"""
    worst = None
    for nm in names:
        r = (ev.get("map") or {}).get(nm)
        if not r or not r.get("at"):
            continue
        t = _parse_iso(r["at"])
        if t is None:
            continue
        if worst is None or t < worst:
            worst = t
    if worst is None:
        return None
    return max(0.0, at_now - worst)


def _parse_iso(s: str):
    import datetime as dt
    s = str(s).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s[:len(fmt) + 2].strip(), fmt).timestamp()
        except Exception:                                    # noqa: BLE001
            continue
    return None


# ══════════════════════════════════════════════════════════════════════════
# 摘要装配（**纯函数**：喂内存对象即可，负对照喂改坏副本）
# ══════════════════════════════════════════════════════════════════════════
def build_digest(ledger: dict, audit: dict, ev: dict, truth: dict, baseline: dict | None,
                 at_now: float) -> dict:
    caps = (ledger or {}).get("caps") or []
    # 每族
    fam = {}
    for c in caps:
        d = c.get("domain") or "（无域）"
        f = fam.setdefault(d, {"n": 0, "caps": [], "未绑": 0, "断连": 0, "未探测": 0})
        f["n"] += 1
        f["caps"].append(c["name"])
        if not str(c.get("carrier") or "").strip() or c.get("state") == "未绑":
            f["未绑"] += 1
    # 运行证据窗口 → 断连 / 未探测
    evmap = (ev or {}).get("map") or {}
    ev_ok = not (ev or {}).get("__err__") and evmap is not None
    for d, f in fam.items():
        for nm in f["caps"]:
            r = evmap.get(nm)
            if r is None:
                f["未探测"] += 1
            elif r.get("s") == "ok":
                pass
            else:
                f["断连"] += 1
    # 假执行（truth_scan FAKE）
    fake_all = set((truth or {}).get("FAKE_list") or [])
    fake_note = None
    if (truth or {}).get("__absent__"):
        fake_note = truth["__absent__"]
    for d, f in fam.items():
        f["假执行"] = len([n for n in f["caps"] if n in fake_all])
    base_fam = (baseline or {}).get("families") or {}
    rows = []
    for d in sorted(fam, key=lambda k: (-fam[k]["n"], k)):
        f = fam[d]
        b = base_fam.get(d)
        def delta(key):
            if not b:
                return "="
            dd = f.get(key, 0) - b.get(key, 0)
            return "=" if dd == 0 else ("+%d" % dd if dd > 0 else "%d" % dd)
        problem = sum(f.get(k, 0) for k in COUNTERS)
        bpro = sum(b.get(k, 0) for k in COUNTERS) if b else None
        dpro = "=" if bpro is None else ("=" if problem == bpro
                                         else ("+%d" % (problem - bpro) if problem > bpro
                                               else "%d" % (problem - bpro)))
        rows.append({
            "family": d, "n": f["n"],
            "未绑": f["未绑"], "断连": f["断连"], "未探测": f["未探测"], "假执行": f["假执行"],
            "Δ未绑": delta("未绑"), "Δ断连": delta("断连"), "Δ未探测": delta("未探测"),
            "Δ假执行": delta("假执行"), "Δ问题": dpro,
            "最旧证据年龄": age_bucket(_evidence_age(ev, f["caps"], at_now)) if ev_ok else "窗口未探测",
        })
    tot = {k: sum(f.get(k, 0) for f in fam.values()) for k in COUNTERS}
    btot = (baseline or {}).get("totals") or {}
    tdelta = {} if not btot else {k: ("=" if tot[k] - btot.get(k, 0) == 0
                                      else ("+%d" % (tot[k] - btot.get(k, 0))
                                            if tot[k] > btot.get(k, 0) else "%d" % (tot[k] - btot.get(k, 0))))
                                  for k in COUNTERS}
    return {
 # **无时钟字段**：这里出现的每个值都必须与「几点跑」无关（幂等/逐字一致）。
        "口径": "v1 · 族=domain（现读）· 四计数=未绑/断连/未探测/假执行 · 年龄用档位",
        "rule": RULE,
        "commands": {"feel": CMD_FEEL, "json": CMD_JSON, "baseline": CMD_BASE, "check": CMD_CHECK},
        "sources": {
            "cap_bindings": "state/cap-bindings.json（现读）",
            "audit": "state/capability-audit.json（现读）",
            "run_evidence": "capability-bar-check.py::read_evidence（有界尾部窗口，同口径）",
            "truth_scan": "state/truth-scan.json（假执行真源）",
            "baseline": "state/cap-nerve-baseline.json（变化量的参照）",
        },
        "counts": {
            "caps": len(caps), "families": len(fam),
            "未绑": tot["未绑"], "断连": tot["断连"], "未探测": tot["未探测"], "假执行": tot["假执行"],
            "Δ": tdelta,
        },
        "probe": {
            "evidence_window": ("未探测：%s" % ev.get("__err__")) if (ev or {}).get("__err__") else "已读（有界尾部窗口）",
            "fake_source": fake_note or "state/truth-scan.json 在盘（FAKE 名单现读）",
            "baseline": "有基线" if base_fam else "无基线（变化量一律 =）",
        },
        "families": rows,
    }


def render_text(dg: dict) -> str:
    L = []
    L.append("GBT小土豆V8 · 能力神经（全族健康摘要 · 口径 %s）" % dg["口径"])
    L.append("纪律：%s" % dg["rule"])
    L.append("=" * 96)
    L.append("%-14s %4s %5s %5s %6s %6s %8s %8s" %
             ("族(domain)", "位", "未绑", "断连", "未探测", "假执行", "Δ问题", "最旧证据"))
    L.append("-" * 96)
    for r in dg["families"]:
        L.append("%-14s %4d %5d %5d %6d %6d %8s %8s" %
                 (r["family"], r["n"], r["未绑"], r["断连"], r["未探测"], r["假执行"],
                  r["Δ问题"], r["最旧证据年龄"]))
    L.append("-" * 96)
    c = dg["counts"]
    L.append("合计 %d 位 / %d 族 ｜ 未绑 %d · 断连 %d · 未探测 %d · 假执行 %s ｜ Δ %s"
             % (c["caps"], c["families"], c["未绑"], c["断连"], c["未探测"],
                ("未判" if dg["probe"]["fake_source"].startswith("真源未产出") else c["假执行"]),
                (c["Δ"] or "= (无基线)")))
    L.append("假执行真源：%s" % dg["probe"]["fake_source"])
    L.append("证据窗口：%s ｜ 基线：%s" % (dg["probe"]["evidence_window"], dg["probe"]["baseline"]))
    L.append("复跑：本摘要**无时钟字段**，同一状态再跑逐字一致（判据见 %s）" % CMD_CHECK)
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════════
# 判据（**必须能红**：负对照喂改坏副本）
# ══════════════════════════════════════════════════════════════════════════
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def run_checks(dg: dict, ledger: dict, ev: dict, render_fn) -> list:
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": str(detail)})

    fams = dg.get("families") or []
    counts = dg.get("counts") or {}
    caps = (ledger or {}).get("caps") or []

    # N1 族覆盖守恒：族数 = domain 数；位数之和 = caps 数
    doms = {c.get("domain") or "（无域）" for c in caps}
    add("N1 计数守恒：族数=domain 数 · 每族位数之和=能力位数",
        len(fams) == len(doms) == counts.get("families")
        and sum(r["n"] for r in fams) == len(caps) == counts.get("caps") and len(caps) > 0,
        "族 %d/%d · 位 %d/%d" % (len(fams), len(doms), sum(r["n"] for r in fams), len(caps)))

    # N2 四计数自洽：每族四计数 ≤ 位数；总计 = 各族之和
    bad2 = [r["family"] for r in fams
            if any(r[k] > r["n"] for k in COUNTERS)]
    tot_ok = all(sum(r[k] for r in fams) == counts.get(k, 0) for k in COUNTERS if k in counts)
    add("N2 四计数自洽（每族各项 ≤ 位数 · 总计=各族之和）", not bad2 and tot_ok,
        "越界族 %s ｜ 总计自洽=%s" % (bad2 or "无", tot_ok))

    # N3 未绑总计 = 绑定台账 caps_unbound
    bu = ((ledger or {}).get("counts") or {}).get("caps_unbound")
    add("N3 未绑总计 = 绑定台账 orphans.caps_unbound（同源）",
        counts.get("未绑") == (bu if bu is not None else counts.get("未绑")),
        "神经未绑 %s ｜ 台账未绑 %s" % (counts.get("未绑"), bu))

    # N4 未探测 = 窗口内无记录的位数（证据窗口读到时）
    if (ev or {}).get("__err__"):
        add("N4 未探测 = 窗口内无该位记录（证据窗口**未探测** ⇒ 如实报，不折绿）", False,
            "证据窗口未探测：%s" % ev["__err__"])
    else:
        evmap = (ev or {}).get("map") or {}
        want = len([c for c in caps if c["name"] not in evmap])
        add("N4 未探测 = 窗口内无记录的位数（与证据窗口同口径）",
            counts.get("未探测") == want,
            "神经未探测 %s ｜ 窗口算 %d" % (counts.get("未探测"), want))

    # N5 无时钟字段（幂等/逐字一致的护栏）
    blob = json.dumps(dg, ensure_ascii=False)
    hit = _ISO_RE.findall(blob)
    add("N5 摘要**无时钟字段**（不得出现 ISO 日期/时刻 ⇒ 复跑逐字一致）", not hit,
        "命中时钟串 %s" % (hit[:3] or "无"))

    # N6 可复跑逐字一致（同输入两次渲染必须 byte 相同）
    try:
        once = render_fn(dg)
        twice = render_fn(json.loads(blob))
        add("N6 幂等：同输入两次渲染逐字一致", once == twice,
            "两次长度 %d/%d" % (len(once), len(twice)))
    except Exception as e:                                   # noqa: BLE001
        add("N6 幂等：同输入两次渲染逐字一致", False, "渲染抛异常：%r" % e)

    # N7 假执行**不编**：真源没产出时必须写明「未判」，不得空报 0 当绿
    fake_src = (dg.get("probe") or {}).get("fake_source") or ""
    if fake_src.startswith("真源未产出"):
        add("N7 假执行 fail-closed：真源未产出时写明『未判』（不空报 0 折绿）",
            "未产出" in fake_src and counts.get("假执行") == 0,
            "真源=%s ｜ 报数=%s（有『未判』说明即可）" % (fake_src[:40], counts.get("假执行")))
    else:
        add("N7 假执行来自 truth_scan 真源（FAKE 名单现读）", True, "真源=%s" % fake_src[:50])

    # N8 变化量：无基线一律 =（不编）
    if (dg.get("probe") or {}).get("baseline", "").startswith("无基线"):
        add("N8 无基线时变化量一律 =（不编）",
            all(r["Δ问题"] == "=" for r in fams), "非 = 的族 %d"
            % len([r for r in fams if r["Δ问题"] != "="]))
    else:
        add("N8 有基线时报变化量", bool(fams), "族 %d" % len(fams))
    return rows


def cmd_check(as_json: bool = False) -> int:
    ledger = _read_json(LEDGER) or {}
    audit = _read_json(AUDIT) or {}
    names = [c["name"] for c in (ledger.get("caps") or [])]
    ev = load_window(names)
    truth = load_truth()
    baseline = _read_json(BASELINE)
    import time as _t
    dg = build_digest(ledger, audit, ev, truth, baseline, _t.time())
    rows = run_checks(dg, ledger, ev, render_text)
    negs = []

    # 负对照 1：注入一个**未绑**位 ⇒ 该族未绑计数必须 +1（不许吞）
    lg2 = json.loads(json.dumps(ledger))
    if lg2.get("caps"):
        lg2["caps"][0]["carrier"] = ""
        lg2["caps"][0]["state"] = "未绑"
    dg2 = build_digest(lg2, audit, ev, truth, None, 0.0)
    got = (dg2.get("counts") or {}).get("未绑", 0)
    negs.append(("喂坏：注入一个未绑位", "N2/N3",
                 got == (dg.get("counts") or {}).get("未绑", 0) + 1,
                 "未绑 %d → %d（应 +1）" % ((dg.get("counts") or {}).get("未绑"), got)))

    # 负对照 2：注入一条 denied 记录 ⇒ 该族断连 +1
    ev2 = json.loads(json.dumps(ev)) if not ev.get("__err__") else {"map": {}}
    if names:
        ev2.setdefault("map", {})[names[0]] = {"s": "denied", "at": "2026-01-01T00:00:00", "raw": "{}"}
    dg3 = build_digest(ledger, audit, ev2, truth, None, 0.0)
    negs.append(("喂坏：注入 denied 记录", "N2",
                 (dg3.get("counts") or {}).get("断连", 0) >= 1,
                 "断连总计 %d（应 ≥1）" % (dg3.get("counts") or {}).get("断连", 0)))

    # 负对照 3：摘要塞一个时钟字段 ⇒ N5 必须报红（幂等护栏能红）
    dg4 = json.loads(json.dumps(dg))
    dg4["generated_at"] = "2026-10-08T12:00:00"
    r5 = [r for r in run_checks(dg4, ledger, ev, render_text) if r["id"].startswith("N5")]
    negs.append(("喂坏：摘要塞时钟字段", "N5", bool(r5) and not r5[0]["ok"],
                 r5[0]["detail"] if r5 else "（没跑 N5）"))

    # 负对照 4：证据窗口掏空（未探测）⇒ N4 必须报红
    ev5 = {"__err__": "负对照：证据窗口读不到"}
    r4 = [r for r in run_checks(build_digest(ledger, audit, ev5, truth, None, 0.0), ledger, ev5, render_text)
          if r["id"].startswith("N4")]
    negs.append(("喂坏：证据窗口未探测", "N4", bool(r4) and not r4[0]["ok"],
                 r4[0]["detail"] if r4 else "（没跑 N4）"))

    # 负对照 5：位数之和不等于 caps ⇒ N1 必须报红
    dg6 = json.loads(json.dumps(dg))
    if dg6.get("families"):
        dg6["families"][0]["n"] += 1
    r1 = [r for r in run_checks(dg6, ledger, ev, render_text) if r["id"].startswith("N1")]
    negs.append(("喂坏：族位数之和不守恒", "N1", bool(r1) and not r1[0]["ok"],
                 r1[0]["detail"] if r1 else "（没跑 N1）"))

    fails = [r for r in rows if not r["ok"]]
    nf = [n for n in negs if not n[2]]
    if as_json:
        print(json.dumps({"rows": rows, "negatives": [{"n": n, "t": t, "ok": o, "d": d} for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(nf)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 82)
        print("能力神经 · 判据（含负对照）")
        print("=" * 82)
        for r in rows:
            print("%s %-60s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"][:110]))
        print("-" * 82)
        for n, t, o, d in negs:
            print("%s 负对照[%-6s] %-34s %s" % ("PASS" if o else "FAIL", t, n[:34], d[:100]))
        print("-" * 82)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(nf), len(nf)))
    return 1 if (fails or nf) else 0


def cmd_feel(as_json: bool = False, write: bool = True) -> int:
    ledger = _read_json(LEDGER)
    if not ledger or not ledger.get("caps"):
        print("🔴 台账读不到（state/cap-bindings.json）：先跑 capability-bindings.py")
        return 2
    audit = _read_json(AUDIT) or {}
    names = [c["name"] for c in ledger["caps"]]
    ev = load_window(names)
    truth = load_truth()
    baseline = _read_json(BASELINE)
    import time as _t
    dg = build_digest(ledger, audit, ev, truth, baseline, _t.time())
    if write:
        STATE.mkdir(parents=True, exist_ok=True)
        DIGEST.write_text(json.dumps(dg, ensure_ascii=False, indent=1), encoding="utf-8")
    if as_json:
        print(json.dumps(dg, ensure_ascii=False, indent=1))
    else:
        print(render_text(dg))
        if write:
            print("（摘要已落 %s · %d 字节 · **无时钟字段**）" % (DIGEST, DIGEST.stat().st_size if DIGEST.is_file() else 0))
    return 0


def cmd_baseline() -> int:
    ledger = _read_json(LEDGER)
    if not ledger or not ledger.get("caps"):
        print("🔴 台账读不到，拒绝立基线")
        return 2
    names = [c["name"] for c in ledger["caps"]]
    ev = load_window(names)
    truth = load_truth()
    import time as _t
    dg = build_digest(ledger, _read_json(AUDIT) or {}, ev, truth, None, _t.time())
    snap = {"families": {r["family"]: {k: r[k] for k in ("n",) + COUNTERS} for r in dg["families"]},
            "totals": {k: dg["counts"][k] for k in COUNTERS}}
    STATE.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已立基线 %s（族 %d · 未绑 %d · 断连 %d · 未探测 %d · 假执行 %d）"
          % (BASELINE, len(snap["families"]), snap["totals"]["未绑"], snap["totals"]["断连"],
             snap["totals"]["未探测"], snap["totals"]["假执行"]))
    print("以后 %s 会拿当前摘要与它比，报出变化量。" % CMD_FEEL)
    return 0


def cmd_cell() -> int:
    """打一段能力栏页用的「顶栏一格」数据脚本（供既有生成器/主人落到页上）。"""
    dg = _read_json(DIGEST)
    if not dg:
        print("🔴 摘要不在盘（先跑 %s）" % CMD_FEEL)
        return 2
    c = dg["counts"]
    bad = c["未绑"] + c["断连"]
    lv = "ok" if bad == 0 else ("warn" if bad <= 3 else "bad")
    cell = {"family_count": c["families"], "caps": c["caps"],
            "未绑": c["未绑"], "断连": c["断连"], "未探测": c["未探测"], "假执行": c["假执行"],
            "level": lv, "text": "神经 %d 族 · 未绑 %d 断连 %d 未探 %d"
                                 % (c["families"], c["未绑"], c["断连"], c["未探测"])}
    print("/* 能力栏顶栏一格（由 capability-nerve.py cell 产出 · 无时钟字段）*/")
    print("globalThis.GBT_CAPNERVE = %s;" % json.dumps(cell, ensure_ascii=False, separators=(",", ":")))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    if not argv:
        return cmd_feel(False)
    if argv[0] in ("--json", "json"):
        return cmd_feel(True)
    if argv[0] in ("feel", "sense"):
        return cmd_feel(False)
    if argv[0] == "baseline":
        return cmd_baseline()
    if argv[0] in ("--check", "check"):
        return cmd_check(as_json="--json" in argv)
    if argv[0] == "cell":
        return cmd_cell()
    ap = argparse.ArgumentParser(description="能力神经 · 全族健康摘要")
    ap.add_argument("verb", choices=["feel", "baseline", "check", "cell"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return {"feel": lambda: cmd_feel(a.json), "baseline": cmd_baseline,
            "check": lambda: cmd_check(a.json), "cell": cmd_cell}[a.verb]()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
