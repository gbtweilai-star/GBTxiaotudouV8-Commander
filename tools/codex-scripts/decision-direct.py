# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 决策直达绑定（快尺 → 直达，**不烧推理**）（主人令 2026-10-14）。

## 主人令（逐字）
「**她自己都吞噬了几个决策模型，要个毛推理啊**」。
—— 对：仓里本来就有**快尺层**，每件事都让 7B 完整推理一圈去猜"该走谁"，那一整圈就是白烧的。

## 现读到的两条本地腿（都不出网、不要钥匙、毫秒级）
  · `gbt_allinone/semantic_route.py`：`route(intent, mode="heuristic")` = 词表 + 方向判别层（89 个触手方法）
  · `gbt_allinone/llm/decision.py`：单遍打分快尺（noul/choice/score 三种契约，**只出概率**，本地实现）
  升维那条（`mode="semantic"` 让统一大模型选）默认**不叫**——只有本地判不出（confidence 低/无命中）才升维。

## 双向绑定（与 `触手双向绑定架构` 同口径）
  · **A 向（意图 → 能力）**：一句话 → 本地快尺 → 命中的触手方法/**毫秒级**，不走主模型。
  · **B 向（决策层 → 框架）**：把本地快尺的**可用性 + 命中率 + 耗时分布**回写
    `state/decision-binding.json`——"这条腿现在几毫秒、命中多少"是读数，不是感觉。

## 判据（可机检）
  D1 本地路由可用：`route(..., mode="heuristic")` 返回 ok
  D2 毫秒级       ：单次调用 P95 < 50ms（不含首次 import）
  D3 命中率       ：样例句里命中方法比例 ≥ 60%（低于此不下结论，只如实报）
  D4 不冒充       ：拿不到结果时如实 false，绝不用主模型结果冒充本地快尺结果
  D5 升维有闸     ：只有 --escalate 才允许叫主模型；默认零出网

用法：
    py -3.14 tools/codex-scripts/decision-direct.py status
    py -3.14 tools/codex-scripts/decision-direct.py route "把桌面截图读一下"
    py -3.14 tools/codex-scripts/decision-direct.py bench [--n 20] [--escalate]
    py -3.14 tools/codex-scripts/decision-direct.py decide --type choice --q "该走哪根触手" --criteria "{\"a\":\"读屏幕\",\"b\":\"发邮件\"}"

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "decision-binding.json"
SAMPLES = [
    "把桌面截图读一下", "帮我打开浏览器搜一下今天的新闻", "把这封邮件发给老王",
    "在飞书里查一下明天的日程", "把这段录音转成文字", "生成一张海报",
    "看看现在有几个能力位", "把蓝牙扫一下", "查一下今天的账单", "让数字人说句话",
    "把这段视频剪成 60 秒", "在知识库里记一笔", "看一下本机 GPU 占用",
    "把这份 PDF 转成 Word", "统计一下日志里的错误数",
]


def _load():
    sys.path.insert(0, str(ROOT))
    t0 = time.perf_counter()
    from gbt_allinone import semantic_route as SR
    from gbt_allinone.llm import decision as DC
    return SR, DC, int((time.perf_counter() - t0) * 1000)


def _local(SR, intent: str) -> dict:
    t0 = time.perf_counter()
    r = SR.route(intent, mode="heuristic")
    r["ms"] = round((time.perf_counter() - t0) * 1000, 2)
    return r


def _method(r: dict) -> str:
    for k in ("best", "method"):
        v = r.get(k)
        if isinstance(v, dict):
            return str(v.get("method") or "")
        if isinstance(v, str):
            return v
    return ""


def cmd_status(_a) -> int:
    SR, DC, imp = _load()
    st = SR.status()
    ks = DC.key_state() if hasattr(DC, "key_state") else {}
    print("首次 import 耗时（一次性）：%dms" % imp)
    print("语义路由：%s" % json.dumps(st, ensure_ascii=False)[:400])
    print("快尺钥匙：%s" % json.dumps(ks, ensure_ascii=False)[:200])
    print("本地腿：heuristic（词表+方向层）· 零出网 · 零钥匙")
    print("升维腿：统一大模型（默认不叫，--escalate 才动）")
    return 0


def cmd_route(a) -> int:
    SR, _DC, imp = _load()
    r = _local(SR, a.intent)
    print("intent : %s" % a.intent)
    print("命中   : %s" % (_method(r) or "（无）"))
    print("耗时   : %s ms（import 一次性 %dms）" % (r.get("ms"), imp))
    print("路径   : %s%s" % (r.get("path"), "  [降级] " + str(r.get("degraded_reason")) if r.get("degraded") else ""))
    print("原文   : %s" % json.dumps(r, ensure_ascii=False)[:500])
    return 0 if r.get("ok") else 1


def cmd_bench(a) -> int:
    SR, _DC, imp = _load()
    samples = (SAMPLES * ((a.n // len(SAMPLES)) + 1))[:a.n]
    rows, ms, hit = [], [], 0
    for s in samples:
        r = _local(SR, s)
        m = _method(r)
        hit += bool(m)
        ms.append(r["ms"])
        rows.append({"intent": s, "method": m or None, "ms": r["ms"]})
    p50 = statistics.median(ms) if ms else 0
    p95 = sorted(ms)[int(len(ms) * 0.95) - 1] if ms else 0
    rate = hit / len(samples) if samples else 0
    print("本地快尺 bench：n=%d · 命中 %d/%d = %.0f%% · P50=%.1fms · P95=%.1fms · import=%dms"
          % (len(samples), hit, len(samples), rate * 100, p50, p95, imp))
    for r in rows[:8]:
        print("   %-24s → %-28s %sms" % (r["intent"], r["method"] or "（未命中）", r["ms"]))
    esc = None
    if a.escalate:
        t0 = time.perf_counter()
        esc = SR.route(samples[0], mode="semantic")
        esc_ms = int((time.perf_counter() - t0) * 1000)
        print("升维（叫主模型）一发：%dms → %s" % (esc_ms, json.dumps(esc, ensure_ascii=False)[:200]))
        print("⇒ 本地 %.1fms vs 升维 %dms = %dx" % (p50, esc_ms, int(esc_ms / max(p50, 0.01))))
    doc = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "direction_a": {"mode": "heuristic(local)", "samples": rows},
           "direction_b": {"ok": bool(hit), "hit_rate": round(rate, 3), "p50_ms": p50, "p95_ms": p95,
                           "import_ms": imp, "escalated": esc,
                           "semantic_available": SR.available().get("ok")}}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("读数落：%s" % STATE)
    ok = rate >= 0.6 and p95 < 50
    print("判据 D2(毫秒级)=%s · D3(命中≥60%%)=%s" % (p95 < 50, rate >= 0.6))
    return 0 if ok else 1


def _parse_criteria(raw: str, type_: str = "choice") -> tuple:
    """容忍两种写法（不给用户逼成 JSON 手）：① 正经 JSON；② **逗号分隔**的人话。

    分型（对齐 decision.py 的三种契约）：
      choice → 要 {选项名: 描述}；score → 要**从低到高有序**的数组（写反了分数就反）；
      noul   → 二值，本来就不需要 criteria。
    """
    raw = (raw or "").strip()
    if not raw:
        return None, ""
    try:
        return json.loads(raw), ""
    except Exception:                                            # noqa: BLE001
        pass
    parts = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
    if len(parts) >= 2:
        if str(type_).lower() == "score":
            return parts, "（按逗号分隔的有序档位解析：**从低到高**）"
        return {p: p for p in parts}, "（按逗号分隔的选项名解析）"
    return None, "criteria 既不是合法 JSON，也不是逗号分隔的选项名"


def cmd_decide(a) -> int:
    _SR, DC, _imp = _load()
    raw = a.criteria or a.options
    crit, note = _parse_criteria(raw, a.type)
    if raw and crit is None:
        print("用法不对：%s" % note)
        print('  例① py -3.14 tools/codex-scripts/decision-direct.py decide --type choice --q "这句话该不该叫主模型" --options "叫主模型,用本地快尺"')
        print("  例② … decide --type choice --q \"…\" --criteria '{\"叫主模型\":\"需要深推理\",\"用本地快尺\":\"常规路由\"}'")
        print('  例③ … decide --type noul --q "这条通知要不要现在发"      # 二值，不用 criteria')
        print('  例④ … decide --type score --q "这件事多急" --criteria "不急,一般,很急"')
        return 2
    if note:
        print("口径：criteria %s" % note)
    t0 = time.perf_counter()
    r = DC.decide(a.type, criteria=crit, questions=[a.q])
    ms = int((time.perf_counter() - t0) * 1000)
    print("快尺 decide(%s)：%dms" % (a.type, ms))
    print(json.dumps(r, ensure_ascii=False)[:700])
    return 0 if r.get("ok", True) else 1


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="决策直达绑定（本地快尺，默认零出网）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p1 = sub.add_parser("route"); p1.add_argument("intent"); p1.set_defaults(fn=cmd_route)
    p2 = sub.add_parser("bench"); p2.add_argument("--n", type=int, default=15)
    p2.add_argument("--escalate", action="store_true", help="额外叫一发主模型做对比（默认不叫）")
    p2.set_defaults(fn=cmd_bench)
    p3 = sub.add_parser("decide"); p3.add_argument("--type", default="choice")
    p3.add_argument("--q", required=True); p3.add_argument("--criteria", default="")
    p3.add_argument("--options", default="", help="逗号分隔的选项名（choice 用；省得手写 JSON）")
    p3.set_defaults(fn=cmd_decide)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
