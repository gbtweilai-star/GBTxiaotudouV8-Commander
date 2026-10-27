#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""route_lexicon —— 意图领域词表（确定性路由，排在语义路之前）

为什么要有这一层（2026-10-28 实测驱动）：
  `brain_route` 的主路是 `semantic_route`（要统一大模型）。A19 不在 / 断网时
  它降级到**字符 2-gram 启发式**，实测：

      意图「上下文异常纠正：near_overflow。请给出纠正动作…」
      返回 best = libtv_workflow（视频节点工作流）· degraded=true
      ⇒ 跟上下文**完全不相干**

  2-gram 靠字面重合打分，而「上下文/溢出/纠正」这类词在能力位描述里几乎不出现，
  于是被"libv/LibTV"这种恰好共字的位抢走。

  词表这一层**不猜**：命中的是人工钉死的「领域 → 能力位」映射，
  命中即 `path=lexicon · degraded=false`；没命中就照原路走，不影响别的意图。

纪律：
  · 只做**加分**，不覆盖主路 —— 主路若明确给出更贴的，仍以主路为准（见 brain_exec.route）
  · 词表里写错的映射会立刻被 `--audit` 抓出来（引用了不存在的能力位就报错）
  · 每条映射都要能被一句话解释清楚（reason 字段），不接受"感觉像"
"""
from __future__ import annotations

# 形如：[{patterns, kinds, reason}]
# patterns 用**子串**匹配（中文不分词，子串比 2-gram 稳）
LEXICON: list[dict] = [
    {
        "id": "context_overflow",
        "patterns": ["上下文", "溢出", "窗口", "环形", "落库", "秒查", "丢条", "复读",
                     "near_overflow", "overflow", "ring_context", "context_guard"],
        "kinds": ["ring_context", "context_vault", "brain_route"],
        "tools": ["tools/context_guard.py"],
        "reason": "上下文/溢出一类：环本身是 ring_context，归档检索是 context_vault",
    },
    {
        "id": "mirror_space",
        "patterns": ["镜像", "维度", "排练", "晋升", "回滚", "指纹", "一致性", "drift",
                     "mirror", "rehearse", "ascend", "parity"],
        "kinds": ["mirror_status", "mirror_scan", "mirror_plan", "mirror_simulate",
                  "mirror_parity", "mirror_rehearse", "mirror_release"],
        "reason": "先在一模一样的那个世界里跑绿，再一次性晋升（docs/09）",
    },
    {
        "id": "tentacle_bind",
        "patterns": ["触手", "绑定", "双向", "穿透", "tentacle", "bind"],
        "kinds": ["tentacle_bind", "tentacle"],
        "tools": ["tools/tentacle_bench.py"],
        "reason": "资产↔触手穿透式绑定",
    },
    {
        "id": "concurrency",
        "patterns": ["并发", "吞吐", "QPS", "backlog", "监听队列", "asyncio", "扇出", "限流"],
        "kinds": ["health", "svc_inspect"],
        "tools": ["tools/async_bench.py", "tools/fanout_bench.py"],
        "reason": "并发/吞吐一类的观测与压测入口",
    },
    {
        "id": "llm_router",
        "patterns": ["路由", "意图", "落位", "能力位", "派活", "route", "dispatch"],
        "kinds": ["brain_route", "brain_execute", "one_shot"],
        "reason": "把一句话落到一个能力位",
    },
    {
        "id": "audit_align",
        "patterns": ["对齐", "审计", "体检", "普查", "无死角", "多域", "基线", "回归"],
        "kinds": ["impact_check", "mirror_scan", "health", "coverage_auditor"],
        "reason": "改一处要整面复查（docs/12 多域监控）",
    },
]


def _score(intent: str, entry: dict) -> tuple[int, list[str]]:
    hit = [p for p in entry["patterns"] if p and p.lower() in intent.lower()]
    return len(hit), hit


def match(intent: str, min_hits: int = 1) -> dict:
    """返回 {ok, entry, score, hits, ranked}。没命中就 ok=False，不硬编。"""
    text = str(intent or "")
    if not text:
        return {"ok": False, "why": "空意图"}
    ranked = []
    for e in LEXICON:
        sc, hits = _score(text, e)
        if sc >= min_hits:
            ranked.append({"id": e["id"], "score": sc, "hits": hits[:6],
                           "kinds": e["kinds"], "reason": e["reason"]})
    if not ranked:
        return {"ok": False, "why": "词表未命中"}
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"ok": True, "entry": ranked[0], "ranked": ranked[:3]}


def audit() -> dict:
    """词表自检：引用的能力位必须真实存在。写错了要当场报，不许静默失效。"""
    try:
        from ..caps_registry import all_caps
    except Exception:                                         # noqa: BLE001
        try:
            from gbt_allinone.caps_registry import all_caps   # type: ignore
        except Exception as exc:                              # noqa: BLE001
            return {"ok": False, "why": "能力注册表不可用: %s" % exc}
    real = {str(c.get("name")) for c in all_caps() if isinstance(c, dict)}
    bad = []
    for e in LEXICON:
        for k in e["kinds"]:   # 只校验**能力位**；tools 是文件路径，不参与路由
            if k not in real:
                bad.append({"entry": e["id"], "kind": k})
    return {"ok": not bad, "entries": len(LEXICON),
            "kinds": sum(len(e["kinds"]) for e in LEXICON),
            "unknown": bad,
            "known_caps": len(real)}


if __name__ == "__main__":
    import json
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    a = audit()
    print(json.dumps(a, ensure_ascii=False, indent=1))
    if len(sys.argv) > 1:
        print(json.dumps(match(" ".join(sys.argv[1:])), ensure_ascii=False, indent=1))
    sys.exit(0 if a["ok"] else 1)
