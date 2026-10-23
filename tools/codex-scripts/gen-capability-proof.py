#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把三路真跑证据合成**一份**能力自证账（341 位全覆盖，一位一行，绝不重叠）。

三路来源：
  1. `data/capability-live-test.json`   —— 只读且无需参数位的逐位真调（probe-caps-live.py）
  2. `data/params-probe.json`           —— 需参数位的「带真参」真跑（probe-caps-params*.py）
  3. `data/write-face-probe.json`       —— 写口位的隔离 store 真跑（probe-caps-write.py）

口径（写死）：
  · 341 位**恰好分到一个桶**：ok / needs_ticket / needs_input / needs_dependency / failed / not_run_high_risk；
  · 桶由**证据**决定，不由"registry 说它 safe"决定；
  · 分桶合计不等于 341 就报错退出（不许悄悄漏位）；
  · 旧账里把"缺参/缺依赖"混成 failed 的，按回执原文重新归类，并在 note 里留下原文。

产出：outputs/open-source-release/data/capability-live-test.json（v2 架构）
用法：py -3.12 tools/codex-scripts/gen-capability-proof.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from gbt_allinone import caps_registry as R          # noqa: E402

DATA = ROOT / "outputs" / "open-source-release" / "data"

INPUT_HINTS = ("缺少", "要 ", "必须给", "不能为空", "need_", "要 image/out", "user_error")
DEP_HINTS = ("needs_dependency", "HTTP 0", "未安装", "not running", "no_such")


def load(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def refine(verdict: str, status: str, note: str) -> tuple[str, str]:
    """把「failed」按回执原文再分一次（缺参/缺依赖不是能力坏）。"""
    n = note or ""
    low = n.lower()
    if verdict != "failed":
        return verdict, note
    if any(h.lower() in low for h in DEP_HINTS):
        return "needs_dependency", "缺依赖：" + n[:120]
    if any(h.lower() in low for h in INPUT_HINTS):
        return "needs_input", "缺输入：" + n[:120]
    if status == "ok":
        return "failed", "信封绿但本体 ok=false：" + n[:120]
    return "failed", n[:140] or "unknown"


def main() -> int:
    caps = [c["name"] for c in R.all_caps()]
    verdict: dict[str, dict] = {}

    # ① 只用旧账里"真的跑过"的那些（旧账把需参数/写口也标了 needs_params/needs_auth，这里不用它们）
    # 输入用**独立快照**：绝不在自己的输出上读（否则跑第二次就没有只读证据了）
    old = load("capability-readonly-live.json")
    if old.get("schema") == "capability-proof-v2":
        print("!! 输入文件被 v2 覆盖过：请恢复只读快照")
        return 3
    # ①b 监控账（90s 超时）是**更新的**读数：旧的只读探针用 12s 超时，把 sec_*/cross_scan 这类
    #     慢位判成 timeout；监控账跑过 90s 超时且逐位真调 ⇒ 以监控账为准（慢 ≠ 坏）。
    mon = {}
    mon_file = ROOT / "state" / "monitor" / "domain-baseline.json"
    if mon_file.is_file():
        mon = json.loads(mon_file.read_text(encoding="utf-8")).get("per_cap") or {}
    for row in (old.get("rows") or []):
        cap = row.get("capability") or row.get("cap")
        if not cap:
            continue
        v = row.get("result") or row.get("verdict")
        if v in ("ok", "denied", "failed", "timeout", "exception", "bad_shape"):
            if v == "ok":
                verdict[cap] = {"bucket": "ok", "src": "read", "note": "空 payload 真调通过"}
            elif v == "denied":
                verdict[cap] = {"bucket": "needs_ticket", "src": "read",
                                "note": "缺票：" + str(row.get("missing_scopes") or "门拒")}
            else:
                b, n = refine("failed", "error", str(row.get("why") or v))
                verdict[cap] = {"bucket": b, "src": "read", "note": n}

    # ①c 监控账覆盖（同一位：监控是 90s 超时的新读数）
    for cap, row in mon.items():
        res = row.get("result")
        if res == "ok":
            verdict[cap] = {"bucket": "ok", "src": "monitor",
                            "note": "监控账 90s 超时下真调通过（%sms）" % row.get("ms")}
        elif res == "denied":
            verdict[cap] = {"bucket": "needs_ticket", "src": "monitor",
                            "note": "缺票：" + str(row.get("why") or "门拒")[:80]}


    # ② 需参数位
    par = load("params-probe.json")
    for row in par.get("rows") or []:
        b, n = refine(row.get("verdict"), row.get("status"), row.get("note"))
        verdict[row["cap"]] = {"bucket": b, "src": "params", "note": n}

    # ③ 写口位
    wf = load("write-face-probe.json")
    for row in wf.get("rows") or []:
        b, n = refine(row.get("verdict"), row.get("status"), row.get("note"))
        verdict[row["cap"]] = {"bucket": b, "src": "write", "note": n}
    # ①d 带票真跑（最高优先级：主人发票后真跑过的位，以它为准）
    tk = load("ticket-probe.json")
    for row in tk.get("rows") or []:
        b, n = refine(row.get("verdict"), row.get("status"), row.get("note"))
        verdict[row["cap"]] = {"bucket": b, "src": "ticket", "note": n}
    for cap in wf.get("skipped") or []:
        verdict[cap] = {"bucket": "not_run_high_risk", "src": "write",
                        "note": "高危未跑（会写生产交付区/起进程/出网/改版本库/渲染大件）"}

    # ①e 最后一批真跑（主人的「全部都要跑通」）：隐私载体/起进程/生产写入/出网 + 高危 8 位，
    #     隔离 store（mirror_* 另跑在真 store 的临时镜像空间）⇒ 以它为准。
    rm = load("remaining-probe.json")
    for row in rm.get("rows") or []:
        b, n = refine(row.get("verdict"), row.get("status"), row.get("note"))
        verdict[row["cap"]] = {"bucket": b, "src": "remaining", "note": n}

    # ①f0 出图交付门（figure_gate）：判据在它自己手里，**去问它**（只读 op），不手抄。
    #     2026-10-21 立：此前一直挂在 needs_input（rounds 0/4），真相是「从没真看过图就想过门」；
    #     这一轮逐张看图 → 逮到 3 处真问题（豆腐块/新旧口径混句/来源写死）→ 修完复看清零。
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import figure_gate as _FG          # noqa: E402
        fg = _FG.verdict()
        if fg.get("ok"):
            verdict["figure_gate"] = {
                "bucket": "ok", "src": "figure",
                "note": ("出图门自判可交付：%d 轮看图 · 最新一轮未清 %d · 数已声明（%s）"
                         % (fg.get("rounds"), len(fg.get("open_issues") or []),
                            (fg.get("numbers") or {}).get("source"))),
            }
        else:
            verdict["figure_gate"] = {
                "bucket": "needs_input", "src": "figure",
                "note": "出图门自判不可交付：" + "；".join(fg.get("reasons") or [])[:160],
            }
    except Exception as exc:                                # noqa: BLE001
        print("!! figure_gate 判据取不到（按原样留旧账，不假装）：", exc)

    # ①f 一次性票位（one_key_deploy）：「排练 → 盖章 → 原子替换」这条链到底跑没跑通，
    #     **不手写**，直接读房间自己的报告（framework 产出的证据，和门读的是同一份）。
    #     口径：rehearsals/latest.json 的 ok=true 且 reality 非空 ⇒ 晋升真落地。
    #     2026-10-21 立：这一位此前一直挂在 needs_input（旧回执 rehearse=False），而真相是
    #     两处真缺陷 ——「目标树没有入口」+「没跑到被写成跑失败」；修好后重跑全绿。
    #     证据不手抄，从房间报告现读（P9：账必须有写手）。
    rooms_root = ROOT / "gbt_allinone" / "store" / "mirror_space" / "rooms"
    best = None
    if rooms_root.is_dir():
        for room in sorted(rooms_root.glob("*")):
            rep = room / "rehearsals" / "latest.json"
            if not rep.is_file():
                continue
            try:
                room_report = json.loads(rep.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not room_report.get("ok"):
                continue
            reality = room / "reality"
            n_reality = (sum(1 for p in reality.rglob("*") if p.is_file())
                         if reality.is_dir() else 0)
            if n_reality == 0:
                continue
            when = str(room_report.get("rehearsed_at") or "")
            if best is None or when > best[0]:
                best = (when, room.name, n_reality, room_report)
    if best:
        verdict["one_key_deploy"] = {
            "bucket": "ok", "src": "room",
            "note": ("房间 %s 真跑全绿并晋升：acceptance=%s 真执行 · reality %d 件 · %s"
                     % (best[1], ",".join(best[3].get("acceptance") or []) or "(无)",
                        best[2], best[0])),
        }

    # ①k 云卡出片的**免费腿**：comfy_cloud 是否已能"付费卡没空卡就转 HF 免费节点"，
    #     证据来自 data/comfy-freegpu-live.json（真回执，不是手抄）。
    fg = load("comfy-freegpu-live.json")
    if fg.get("schema") == "comfy-freegpu-live-v1" and fg.get("ok"):
        verdict["comfy_cloud"] = {
            "bucket": "ok", "src": "freegpu",
            "note": ("免费 GPU 路真跑：route=%s · %s · %ss · %s 字节 · sha256=%.12s…（付费卡 %s/%s 运行）"
                     % (fg.get("route"), fg.get("space"), fg.get("elapsed_s"), fg.get("bytes"),
                        str(fg.get("sha256")), (fg.get("paid_pod") or {}).get("running"),
                        (fg.get("paid_pod") or {}).get("total"))),
        }
    # ①h 进攻面两兄弟：由 probe-offense-live.py 现读（目标只用本机回环；plan 不动手）
    off = load("offense-pentest-live.json")
    if off.get("schema") == "offense-pentest-live-v1":
        oo = off.get("offense_ops") or {}
        if oo.get("ok"):
            verdict["offense_ops"] = {
                "bucket": "ok", "src": "offense",
                "note": ("本机回环目标（%s）真跑 op=plan：五阶段 %d 条 · 三条判据；"
                         "只出计划不动手" % (off.get("target"),
                                        len(oo.get("phases") or []))),
            }
        else:
            verdict["offense_ops"] = {
                "bucket": "needs_input", "src": "offense",
                "note": "op=plan 未过：" + str(oo.get("error") or "见 data/offense-pentest-live.json")[:120],
            }
        pt = off.get("pentest") or {}
        if pt.get("ok"):
            verdict["pentest"] = {
                "bucket": "ok", "src": "offense",
                "note": "本机回环目标真跑 op=verify（已登记授权目标 %s）" % off.get("target"),
            }
        elif pt.get("denied"):
            verdict["pentest"] = {
                "bucket": "needs_ticket", "src": "offense",
                "note": ("目标已登记（%s），门只剩一张票：%s —— 主人终端发 "
                         "`auth grant --scope network_private` 即可，模型无权自给"
                         % (off.get("target"),
                            "network_private" if "network_private" in str(pt.get("error"))
                            else str(pt.get("error"))[:60])),
            }
        else:
            verdict["pentest"] = {
                "bucket": "needs_input", "src": "offense",
                "note": "op=verify 未过：" + str(pt.get("error") or "见 data/offense-pentest-live.json")[:120],
            }
    # ①g codex 打断链：结论由**同进程三步探针**（probe-codex-interrupt.py）现读，不手写。
    #    绿 ⇒ ok；不绿 ⇒ 仍记 needs_input，但 note 换成**当前真原因**（不是那句过期的
    #    「no active turn」，那是跨进程调用造成的假象）。
    ci = load("codex-interrupt-live.json")
    if ci.get("schema") == "codex-interrupt-live-v1":
        steps = ci.get("steps") or {}
        if ci.get("ok"):
            verdict["codex_interrupt"] = {
                "bucket": "ok", "src": "chain",
                "note": "同进程三步真跑通：thread_new → turn_send → interrupt（%ss）"
                        % ci.get("elapsed_s"),
            }
        else:
            broken = [k for k in ("thread_new", "turn_send", "interrupt")
                      if not (steps.get(k) or {}).get("ok")]
            why = ((steps.get(broken[0]) or {}).get("error")
                   if broken else "") or "见 data/codex-interrupt-live.json"
            verdict["codex_interrupt"] = {
                "bucket": "needs_input", "src": "chain",
                "note": ("同进程三步探针：断在 %s —— %s（不是「没有这个功能」，是"
                         "「打断活回合的前置不成立」，逐条原因见 data/codex-interrupt-live.json）"
                         % ("/".join(broken), str(why)[:120])),
            }
    # ④ 一位都没碰到的（既不在三路证据里）——如实列出来，不假装
    missing = [c for c in caps if c not in verdict]
    for c in missing:
        verdict[c] = {"bucket": "not_run_high_risk", "src": "none", "note": "没有任何一路证据覆盖到"}

    cnt: dict[str, int] = {}
    for v in verdict.values():
        cnt[v["bucket"]] = cnt.get(v["bucket"], 0) + 1
    total = sum(cnt.values())
    if total != len(caps):
        print("!! 分桶合计 %d ≠ 341（%d）" % (total, len(caps)))
        return 2

    by_src: dict[str, int] = {}
    for v in verdict.values():
        by_src[v["src"]] = by_src.get(v["src"], 0) + 1

    # 兼容旧字段名（fig-caps 与 07 页读的是这几个键）
    doc = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema": "capability-proof-v2",
        "total": len(caps),
        "counts": {
            "ok": cnt.get("ok", 0),
            "denied": cnt.get("needs_ticket", 0),
            "needs_params": cnt.get("needs_input", 0),
            "needs_auth": cnt.get("not_run_high_risk", 0),
            "needs_dependency": cnt.get("needs_dependency", 0),
            "failed": cnt.get("failed", 0),
            "timeout": 0, "exception": 0,
        },
        "buckets": cnt,
        "by_source": by_src,
        "sources": {
            "read": "只读且无需参数：空 payload 真调（probe-caps-live.py）",
            "params": "需参数：人写样本参数真跑（probe-caps-params*.py，隔离 store、非主人会话）",
            "write": "写口：隔离 store 真跑（probe-caps-write.py），高危 8 位不跑",
            "none": "三路都没覆盖到（如实列出）",
        },
        "rows": {c: verdict[c] for c in sorted(verdict)},
    }
    out = DATA / "capability-live-test.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("341 位分桶：", cnt)
    print("按来源：", by_src)
    print("落账 →", out)
    for b in ("failed", "needs_input", "needs_dependency", "not_run_high_risk"):
        names = [c for c, v in verdict.items() if v["bucket"] == b]
        if names:
            print("%-18s %2d：%s" % (b, len(names), ", ".join(names[:14])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



