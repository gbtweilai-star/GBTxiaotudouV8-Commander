# -*- coding: utf-8 -*-
"""能力族级深排 · **241 全表** + **真执行证据**（主人令 2026-10-08）。

## 干什么
对**每一族**（domain）产出一行：族名 ｜ 位数 ｜ 接上/断连/缺失/未探测（现读）｜
孤儿/未分型（`caps_called_audit` 现读）｜ **真执行证据**（族内抽 1–2 位**穿门真调**，
**必须有副作用证据**：审计账本落痕 + 返回非空非占位）｜ 结论与缺口。
落 `docs/能力族深排-241全表.md`（页头写可复跑命令）。

## 🔴 口径（不许假绿 · 不许假验）
- **接上/断连/缺失/未探测** = 现读 `state/capability-audit.json`（framework 类逐位）。
- **孤儿/未分型** = 现读能力位 `caps_called_audit`（走唯一门 `run_task`）。
- **真执行** = 本轮**真** `run_task('<kind>', <payload>)`（**穿门**）：
    · **有副作用证据** = ① 审计账本出现该 kind 的新落痕；② 返回**非空且非占位话术** ⇒ 记 `真执行·ok`
    · **报 ok 无副作用** = 返回空/占位 ⇒ 记 `假执行嫌疑`，**单独列**，不入绿
    · 缺授权 / 需参 / 缺依赖 / 超时 ⇒ **如实报**，不算真执行、也不算假执行
- **安全族**：真调归**另一条线**（不在本表重跑；本表只出它的绑定/页面/神经轴读数）。

## 用法
    py -3.14 tools/codex-scripts/capability-family-deepscan.py probe     # 真调各族的代表位（穿门 · 落账）
    py -3.14 tools/codex-scripts/capability-family-deepscan.py render    # 出 docs/能力族深排-241全表.md
    py -3.14 tools/codex-scripts/capability-family-deepscan.py           # probe + render
    py -3.14 tools/codex-scripts/capability-family-deepscan.py --json    # 机读

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"
LEDGER = STATE / "cap-bindings.json"
AUDIT = STATE / "capability-audit.json"
ACCUM = STATE / "caps-probe-accum.json"
AUDIT_JSONL = ROOT / "gbt_allinone" / "store" / "audit.jsonl"
DEEP = STATE / "family-deepscan.json"
OUT = ROOT / "docs" / "能力族深排-241全表.md"

CMD_PROBE = "py -3.14 tools/codex-scripts/capability-family-deepscan.py probe"
CMD_RENDER = "py -3.14 tools/codex-scripts/capability-family-deepscan.py render"

# 每族抽 1–2 位**代表**（优先 只读 / 免参 / safe · 不碰改状态；**避开**出网/花钱/发布重的位）。
# 安全族真调归另一条线（留空）。
REPS = {
    "system": ["health", "caps_called_audit"],
    "llm": ["llm_status", "brain_health"],
    "pipeline": ["pipeline_status", "ghost_guard"],
    "mind": ["local_brain", "meta_cognition"],
    "video": ["libtv_skill"],
    "tentacle": ["tentacle_status", "tentacle_manifest"],
    "recon": ["verification_watch", "film_intel"],
    "data": ["echo", "db_probe"],
    "tools": ["capability_net", "awesome_tools_index"],
    "devour": ["devour_fusion"],
    "finance": ["quant_strategy", "quant_params"],
    "engine": ["wf_status", "sched_status"],
    "longrun": ["lr_status", "tactics_advise"],
    "project": ["platform_profile", "project_context"],
    "voice": ["voice_orchestra"],
    "brain": ["absorb_loop", "dream_replay"],
    "collab": ["stigmergy"],
    "desktop": ["control_loop"],
    "comms": ["coze_mail"],
    "framework": ["gate_visibility"],
    "image_video": ["a1art_skill"],
    "infra": ["cloud_pc"],
    "life": ["life"],
    "social": ["auto_publish"],
    "integration": ["feishu_embed"],
    "creation": ["console_pages"],
    # 安全族：**不重跑**（归另一条线）。只留一条"它的结论是起点"的注。
    "security": [],
}


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


def _audit_tail_kinds(nbytes: int = 1024 * 1024) -> dict:
    """只读审计账本**尾部有界窗口**：kind → 最后一条 {event, iso}。轻。"""
    out = {}
    if not AUDIT_JSONL.is_file():
        return out
    size = AUDIT_JSONL.stat().st_size
    with open(AUDIT_JSONL, "rb") as f:
        f.seek(max(0, size - nbytes))
        text = f.read().decode("utf-8", "replace")
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                                    # noqa: BLE001
            continue
        k = (r.get("meta") or {}).get("kind")
        if k:
            out[k] = {"event": r.get("event"), "iso": r.get("iso")}
    return out


PLACEHOLDER = ("placeholder", "待实现", "not implemented", "todo", "stub")


def _parse_envelope(stdout: str):
    """CLI 打的是 **Python dict repr**（单引号）⇒ 先试 JSON，再 ast.literal_eval。抠不出返回 None。"""
    i = stdout.find("{")
    if i < 0:
        return None
    seg = stdout[i:]
    try:
        env, _ = json.JSONDecoder().raw_decode(seg)
        return env
    except Exception:                                        # noqa: BLE001
        pass
    try:
        return ast.literal_eval(seg.strip().splitlines()[0] if seg.strip() else seg)
    except Exception:                                        # noqa: BLE001
        pass
    # 多行/尾部有噪声：截到最后一个配平的 '}' 再 literal_eval
    depth = 0
    for j, ch in enumerate(seg):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return ast.literal_eval(seg[:j + 1])
                except Exception:                            # noqa: BLE001
                    return None
    return None


def _classify(stdout: str, before: dict, after: dict, kind: str) -> dict:
    """穿门真调的**副作用判据**。返回 {verdict, why, side_effect, result_ok}。"""
    se = None
    b = before.get(kind)
    a = after.get(kind)
    if a and (b is None or a.get("iso") != b.get("iso")):
        se = "账本新落痕 kind=%s event=%s iso=%s" % (kind, a.get("event"), a.get("iso"))
    # 解析返回信封里 result 是否非空非占位
    result_ok = None
    res_txt = ""
    env = _parse_envelope(stdout)
    if isinstance(env, dict):
        body = env.get("gbt_result") if isinstance(env.get("gbt_result"), dict) else (
            env.get("result") if isinstance(env.get("result"), dict) else env)
        r = (body or {}).get("result")
        st = (body or {}).get("status")
        res_txt = json.dumps(r, ensure_ascii=False)[:160] if r is not None else ""
        if st == "ok":
            low = res_txt.lower()
            if not r or (isinstance(r, dict) and not r):
                result_ok = False
            elif any(w in low for w in PLACEHOLDER):
                result_ok = False
            else:
                result_ok = True
        elif st == "error":
            msg = str((body or {}).get("message") or "")
            if "needs_dependency" in msg or "依赖" in msg:
                return {"verdict": "缺依赖", "why": msg[:80], "side_effect": se, "result_ok": False}
            return {"verdict": "错", "why": msg[:80], "side_effect": se, "result_ok": False}
    # 只有**信封抠不出**时才退回文本启发（抠得出就不许拿子串猜 —— 本仓血泪：否定的 denied 被读成肯定）
    if not isinstance(env, dict):
        low = stdout.lower()
        if "缺少作用域" in stdout or '"denied": true' in stdout or "missing_scopes" in low:
            return {"verdict": "缺授权", "why": "被门拒（缺作用域）", "side_effect": se, "result_ok": False}
        if "缺少" in stdout or "必填" in stdout:
            return {"verdict": "需参数", "why": stdout[-120:].replace("\n", " "), "side_effect": se, "result_ok": False}
    if result_ok is True and se:
        return {"verdict": "真执行·ok", "why": "返回非空非占位 + 账本落痕", "side_effect": se, "result_ok": True}
    if result_ok is False and se:
        return {"verdict": "假执行嫌疑", "why": "报 ok 但返回空/占位（无真副作用）", "side_effect": se, "result_ok": False}
    return {"verdict": "未判定", "why": (res_txt or stdout[-120:].replace("\n", " ")), "side_effect": se, "result_ok": None}


def cmd_probe() -> int:
    print("=" * 84)
    print("能力族级深排 · 真调各族的代表位（**穿门** run_task · 超时 30s）")
    print("=" * 84)
    results = collections.OrderedDict()
    for fam, kinds in REPS.items():
        if not kinds:
            results[fam] = {"probe": [], "note": "安全族真调归**另一条线**（本表不重跑；只出绑定/页面/神经轴）"}
            print("  [%-12s] — 归另一条线（不重跑）" % fam)
            continue
        rows = []
        for kind in kinds:
            before = _audit_tail_kinds()
            cmd = [sys.executable, "-m", "gbt_allinone", "run", kind, "{}"]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=30, cwd=str(ROOT))
                out = (r.stdout or "") + (r.stderr or "")
                rc = r.returncode
                cls = _classify(out, before, _audit_tail_kinds(), kind)
                cls.update({"kind": kind, "rc": rc, "tail": out.strip().replace("\n", " ")[-160:]})
            except subprocess.TimeoutExpired:
                cls = {"kind": kind, "rc": None, "verdict": "超时", "why": "30s 未回（按超时如实报）",
                       "side_effect": None, "result_ok": None, "tail": ""}
            rows.append(cls)
            print("  [%-12s] %-22s → %-14s %s" % (fam, kind, cls["verdict"], (cls.get("why") or "")[:48]))
        results[fam] = {"probe": rows}
    d = {"generated_by": "capability-family-deepscan.py probe", "results": results}
    DEEP.parent.mkdir(parents=True, exist_ok=True)
    DEEP.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-" * 84)
    n_ok = sum(1 for f in results.values() for p in f.get("probe", []) if p.get("verdict") == "真执行·ok")
    n_fake = sum(1 for f in results.values() for p in f.get("probe", []) if p.get("verdict") == "假执行嫌疑")
    print("真执行·ok %d ｜ 假执行嫌疑 %d ｜ 台账：%s" % (n_ok, n_fake, DEEP))
    return 0


def _yes(x) -> str:
    return "是" if x else "否"


def cmd_render() -> int:
    b = _read_json(LEDGER) or {}
    a = _read_json(AUDIT) or {}
    acc = (_read_json(ACCUM) or {}).get("逐位") or {}
    deep = (_read_json(DEEP) or {}).get("results") or {}
    caps = b.get("caps") or []

    # 审计 framework 逐位 state
    fw = {}
    for it in a.get("items") or []:
        if str(it.get("id") or "").startswith("framework.cap."):
            fw[it["name"]] = it.get("state")
    # accum 真探态
    def ac(k):
        return (acc.get(k) or {}).get("态")
    # 能力位调用点审计（孤儿/未分型）—— 走唯一门
    census = {}
    try:
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as gbt
        r = gbt.run_task("caps_called_audit", {})
        census = (r.get("gbt_result", {}) or {}).get("result") or {}
    except Exception as e:                                   # noqa: BLE001
        census = {"__err__": "%s: %s" % (type(e).__name__, str(e)[:100])}

    fam = collections.defaultdict(lambda: {"caps": [], "states": collections.Counter()})
    for c in caps:
        d = c.get("domain") or "（无域）"
        fam[d]["caps"].append(c["name"])
        fam[d]["states"][fw.get(c["name"], "未探测")] += 1

    L = []
    A = L.append
    A("# 能力族深排 · 241 全表（族级 · 现读 · 含真执行证据）")
    A("")
    A("> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属")
    A("")
    A("> **可复跑命令（页头）**")
    A(">")
    A("> ```")
    A("> py -3.14 -m gbt_allinone list                              # 家底（族×位数现读）")
    A("> py -3.14 tools/codex-scripts/%s probe   # 真调各族代表位（穿门·落账）" % Path(__file__).name)
    A("> py -3.14 tools/codex-scripts/%s render  # 出本表" % Path(__file__).name)
    A("> py -3.14 tools/codex-scripts/capability-audit.py probe    # 四态真探（本表「接上/断连/缺失/未探测」源）")
    A("> py -3.14 tools/codex-scripts/capability-bindings.py --check # 三边+页面边判据（含负对照）")
    A("> py -3.14 tools/codex-scripts/capability-nerve.py          # 全族健康摘要（神经）")
    A("> ```")
    A("")
    cc = census if not census.get("__err__") else {}
    A("**家底（现读）**：能力位 **%d** 条 / **%d** 族 ｜ 绑定台账触手承载 %s · 直连 %s · 未绑 %s"
      " ｜ 审计项 %s（四态：接上 %s · 断连 %s · 缺失 %s · 未探测 %s）"
      % (len(caps), len(fam),
         (b.get("counts") or {}).get("caps_tentacle"), (b.get("counts") or {}).get("caps_direct"),
         (b.get("counts") or {}).get("caps_unbound"),
         (a.get("counts") or {}).get("total"), (a.get("counts") or {}).get("接上"),
         (a.get("counts") or {}).get("断连"), (a.get("counts") or {}).get("缺失"),
         (a.get("counts") or {}).get("未探测")))
    A("")
    if cc:
        A("**调用点审计（caps_called_audit 现读）**：总 %s · 已接线 %s · **孤儿 %s** · 入口型(不报孤儿) %s · 同自称-仅 %s。"
          % (cc.get("total"), cc.get("wired_count"), cc.get("orphan_count"),
             len(cc.get("cap_types") or {}), len(cc.get("self_ref_only") or [])))
    else:
        A("**调用点审计**：未取到（%s）—— 如实报，不编。" % census.get("__err__"))
    A("")
    A("> 🔴 **真执行口径**：`真执行·ok` = 穿门 `run_task` 且**返回非空非占位 + 审计账本落痕**（真副作用）；"
      "`假执行嫌疑` = 报 ok 但返回空/占位（**单独列，不入绿**）；缺授权/需参/缺依赖/超时=如实报。"
      "安全族真调归**另一条线**，本表不重跑。")
    A("")
    # 主表
    A("## 一 · 族级全表（%d 族逐族）" % len(fam))
    A("")
    A("| 族 | 位数 | 接上 | 断连 | 缺失 | 未探测 | 触手承载 | 直连 | 用能 | 真执行证据（本轮代表位） | 结论/缺口 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    order = sorted(fam, key=lambda d: (-len(fam[d]["caps"]), d))
    n_fam_ok = n_fam_fake = n_fam_none = 0
    for d in order:
        f = fam[d]
        st = f["states"]
        tent = sum(1 for c in caps if (c.get("domain") == d and c.get("bind_kind") == "触手承载"))
        dire = sum(1 for c in caps if (c.get("domain") == d and c.get("bind_kind") != "触手承载"))
        en = sum(1 for c in caps if (c.get("domain") == d and (c.get("energy") or {}).get("chain")))
        dp = deep.get(d, {})
        probes = dp.get("probe") or []
        if not probes:
            ev = "—（%s）" % (dp.get("note") or "无代表位")
            concl_bits = []
            if d == "security":
                concl_bits.append("真调归另一条线")
            n_fam_none += 1
        else:
            bits = []
            has_ok = has_fake = False
            for p in probes:
                v = p.get("verdict")
                if v == "真执行·ok":
                    has_ok = True
                    bits.append("`%s` ✓真执行" % p["kind"])
                elif v == "假执行嫌疑":
                    has_fake = True
                    bits.append("`%s` ⚠假执行嫌疑(单独列)" % p["kind"])
                else:
                    bits.append("`%s` %s" % (p["kind"], v))
            ev = "；".join(bits)
            if has_ok and not has_fake:
                n_fam_ok += 1
            elif has_fake:
                n_fam_fake += 1
            concl_bits = []
        # 结论/缺口
        gap = []
        if st.get("断连"):
            gap.append("断连 %d" % st["断连"])
        if st.get("未探测"):
            gap.append("未探测 %d" % st["未探测"])
        if acc:
            notok = [c for c in f["caps"] if ac(c) in ("⛔ 痛", "🔒 被门拒·缺授权", "🟡 需参数·未探")]
            if notok:
                gap.append("真探账里 %d 位非通" % len(notok))
        concl_bits.append("；".join(gap) if gap else "无")
        if d == "security":
            concl_bits.append("安全族真调归另一条线")
        A("| %s | %d | %d | %d | %d | %d | %d | %d | %d | %s | %s |"
          % (d, len(f["caps"]), st.get("接上", 0), st.get("断连", 0), st.get("缺失", 0),
             st.get("未探测", 0), tent, dire, en, ev, "；".join([x for x in concl_bits if x]) or "无"))
    A("")
    A("**族级真执行汇总**：真执行·ok 的族 %d ｜ 有假执行嫌疑的族 %d ｜ 无代表位/归另一条线的族 %d"
      % (n_fam_ok, n_fam_fake, n_fam_none))
    A("")
    # 假执行单独列
    fake_rows = [(d, p) for d, f in deep.items() for p in (f.get("probe") or [])
                 if p.get("verdict") == "假执行嫌疑"]
    A("## 二 · ⚠️「报 ok 无副作用」＝假执行嫌疑（**单独列，不入绿**）")
    A("")
    if fake_rows:
        A("| 族 | 位 | 证据 | 返回尾 |")
        A("|---|---|---|---|")
        for d, p in fake_rows:
            A("| %s | `%s` | %s | %s |"
              % (d, p["kind"], (p.get("why") or "")[:60], (p.get("tail") or "")[:70]))
    else:
        A("（本轮无「报 ok 无副作用」的位。）")
    A("")
    A("## 三 · 真执行逐位明细（穿门全表）")
    A("")
    A("| 族 | 位 | 结论 | 副作用证据 | rc | 返回尾 |")
    A("|---|---|---|---|---|---|")
    for d, f in deep.items():
        for p in (f.get("probe") or []):
            A("| %s | `%s` | %s | %s | %s | %s |"
              % (d, p["kind"], p.get("verdict"), (p.get("side_effect") or "—")[:64],
                 p.get("rc"), (p.get("tail") or "")[:60]))
    A("")
    A("## 四 · 未取得真执行证据的族（如实列）")
    A("")
    for d in order:
        dp = deep.get(d, {})
        if not (dp.get("probe") or []):
            A("- **%s**：%s" % (d, dp.get("note") or "本轮未抽代表位"))
    A("")
    A("## 五 · 口径与边界")
    A("")
    A("1. 「接上/断连/缺失/未探测」是**接线层**（清单/真源里有它、api.py 有分派着落），**不是运行证据**；")
    A("   运行证据见 `capability-nerve.py` 与能力栏页（来自审计账本有界尾窗口）。")
    A("2. 「真执行」的**副作用证据** = 审计账本新落痕 + 返回非空非占位；**报 ok 无副作用单列**。")
    A("3. 余额/密钥类**探活有成本或风险**的族（finance/voice/comms 等），代表位一律**只读/免参**。")
    A("4. 安全族以另一条线的结论为起点，本表不重跑真调。")
    A("")
    text = "\n".join(L)
    OUT.write_text(text, encoding="utf-8")
    print("已落盘 %s（%d 字节）· 族 %d" % (OUT, len(text), len(fam)))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    if not argv:
        cmd_probe()
        return cmd_render()
    if argv[0] == "probe":
        return cmd_probe()
    if argv[0] in ("render", "build"):
        return cmd_render()
    if argv[0] in ("--json", "json"):
        print(json.dumps({"deep": _read_json(DEEP), "ledger": _read_json(LEDGER)},
                         ensure_ascii=False, indent=1))
        return 0
    print("用法：capability-family-deepscan.py [probe | render | --json]（无参 = probe + render）")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
