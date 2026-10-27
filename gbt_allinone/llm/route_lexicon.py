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
        "id": "health_check",
        "patterns": ["健康", "体检", "自检", "状态如何", "还活着", "health", "五维"],
        "kinds": ["health", "brain_health", "mirror_status", "svc_inspect"],
        "reason": "健康/体检一类：整体看 health，大脑自身看 brain_health",
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


# 长意图阈值：像"能力位描述"那种长文本里全是顺手词，
# 允许 1 个命中就劫持会误伤（实测：browser 描述含"窗口"被导到 ring_context，
# coze_mail 含"绑定"被导到 tentacle_bind，n8n_wf 含"双向"同上）。
# 规则：意图长度 > LONG_INTENT 时要求 ≥2 个不同命中；短人话 ≥1 即可。
LONG_INTENT = 60


def match(intent: str, min_hits: int = 0) -> dict:
    """返回 {ok, entry, score, hits, ranked}。没命中就 ok=False，不硬编。"""
    text = str(intent or "")
    if not text:
        return {"ok": False, "why": "空意图"}
    need = min_hits or (2 if len(text) > LONG_INTENT else 1)
    ranked = []
    for e in LEXICON:
        sc, hits = _score(text, e)
        if sc >= need:
            ranked.append({"id": e["id"], "score": sc, "hits": hits[:6],
                           "need": need,
                           "kinds": e["kinds"], "reason": e["reason"]})
    if not ranked:
        return {"ok": False, "why": "词表未命中"}
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"ok": True, "entry": ranked[0], "ranked": ranked[:3]}


def _self_label(cap_desc: str) -> str:
    """从描述里取"自称谓"：第一个「：」之前、最后一个「·」之后那段。

    为什么需要它：能力位名是**英文**（brain_health / brain_verify / model_key_pool），
    而描述全是中文（"健康维"/"验证维"/"模型密钥池"）——实测位名 token
    在描述里**一个都不出现**，所以"按位名自识别"对这类位完全失效。
    中文自称谓才是它们在文本里的真实身份。
    """
    import re as _re
    # 🔴 2026-10-28 第三次修（每次都是实测撞出来的）：
    #   ① markdown 污染：26 个位自称谓里带 **粗体** / `代码` / __下划线__
    #   ② 长度守卫丢掉带括号说明的整段（llm_watch 的「**守望**（主人令…）」> 20 字）
    #   ③ **截断顺序错了**：offload_distill 的描述开头没有「：」，
    #      旧的 split("·")[-1] 会抓到很靠后的段 ⇒ 取到空 ⇒ 永远走兜底。
    #      正确顺序：剥 md → 在「：」截断 → 在「（(」截断 → 最后才按「·」分段。
    text = _re.sub(r"\*\*|__|`|~~|\[|\]", "", str(cap_desc or ""))
    # 半角冒号也要认：不少位描述是英文（"Claude Code CLI: official ..."），
    # 只切全角「：」会让整段超长 ⇒ 自称谓取空 ⇒ 只能靠语义抖（实测 claude_code）
    import re as _re2
    text = _re2.split(r"[：:]", text, 1)[0]
    text = _re.split(r"[（(]", text)[0]
    seg = text.split("·")[-1].strip()
    seg = seg.strip(" 　·:：，,。.）)」』】")
    return seg if 2 <= len(seg) <= 20 else ""


def name_hint(intent: str) -> dict:
    """在词表之前先认"自称谓"。命中越长的标签越优先（具体压笼统）。

    🔴 2026-10-28 修两处（都实测撞出来）：
      ① **比对污染**：标签是剥过 markdown 的，而原文带 `**` ⇒ 子串永远不中。
         实测 multimodal_port 因此被词表的「维度」劫持。现在两边都先剥。
      ② **自称谓撞车**：omni_plug 与 wf_cache_clear 的中文名都叫「万能插」，
         同权重时随机挑一个。现在撞车时：名字出现在意图里的优先，
         否则取**名字最短**的（更泛化的那个），并标 ambiguous 让人看得见。
    """
    import re as _re
    text = _re.sub(r"\*\*|__|`|~~|\[|\]", "", str(intent or ""))
    if not text:
        return {"ok": False, "why": "空意图"}
    try:
        from ..caps_registry import all_caps
    except Exception:                                         # noqa: BLE001
        try:
            from gbt_allinone.caps_registry import all_caps   # type: ignore
        except Exception:                                     # noqa: BLE001
            return {"ok": False, "why": "注册表不可用"}

    cands: list[dict] = []
    for c in all_caps():
        if not isinstance(c, dict):
            continue
        lab = _self_label(c.get("desc") or "")
        if not lab or lab not in text:
            continue
        cands.append({"cap": str(c.get("name")), "label": lab,
                      "weight": len(lab), "domain": c.get("domain")})
    if not cands:
        return {"ok": False, "why": "无自称谓命中"}

    top_w = max(x["weight"] for x in cands)
    top = [x for x in cands if x["weight"] == top_w]
    ambiguous = len(top) > 1
    if ambiguous:
        named = [x for x in top if x["cap"].lower() in text.lower()]
        pick = (sorted(named, key=lambda x: len(x["cap"])) or
                sorted(top, key=lambda x: len(x["cap"])))[0]
    else:
        pick = top[0]
    pick = dict(pick)
    pick["ambiguous"] = ambiguous
    pick["tied"] = [x["cap"] for x in top] if ambiguous else []
    return {"ok": True, "best": pick}


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
