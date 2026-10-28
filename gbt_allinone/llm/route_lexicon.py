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


def _post_colon(cap_desc: str) -> str:
    """冒号后那一小句（去掉 markdown / 括号），用来在自称谓撞车时分出彼此。

    实测：codex_interrupt / codex_models / codex_thread_new 的**自称谓完全一样**
    （「官方 Codex 写操作」/「官方 Codex 只读」），不延展就永远分不开。
    延展后分别变成「…中断当前回合」/「…可用模型清单」/「…新建线程」。
    """
    import re as _re
    t = _re.sub(r"\*\*|__|`|~~|\[|\]", "", str(cap_desc or ""))
    parts = _re.split(r"[：:]", t, 1)
    if len(parts) < 2:
        return ""
    tail = _re.split(r"[（(]", parts[1])[0].strip()
    tail = tail.strip(" 　·:：，,。.）)」』】")
    return tail[:14] if 2 <= len(tail) <= 14 else ""


def name_hint(intent: str) -> dict:
    """在词表之前先认"自称谓"。三条判据依次收紧：

      ① **位置优先**：多个自称谓同长度时，**在文本里出现得更早的赢**
         （主语通常先出现。实测 brain_execute 的「执行维」在前、
          「万能插」在后 → 应归 brain_execute；
          replan_loop 的「回流环」在前、「任务图」在后 → 应归 replan_loop）
      ② **延展标签**：自称谓撞车（完全相同）时，带上冒号后那一小句再比
         （codex_interrupt / codex_models / codex_thread_new 靠这条分开）
      ③ **名字 token 兜底**：自称谓取空但**英文名字出现在文本里**时用它
         （genoffice_bridge 描述里就写着 GenOffice）
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
        desc = c.get("desc") or ""
        lab = _self_label(desc)
        if lab and lab in text:
            cands.append({"cap": str(c.get("name")), "label": lab,
                          # 描述**开头**就是这一位自己的名字（主语），后文出现的多半只是"提到别人"。
                          # 实测 cloud_plugin：「云插件」在位置 0，却被后文的
                          # 「ComfyUI」按长度压过 ⇒ 开头给压倒性权重。
                          # 位置 0 的标签就是这一位自己的名字（描述的主语）；后文出现的多是"提到别人"。
                          # 加成必须进 weight 本身 —— 因为决策段用 max(weight) 取最长，
                          # 光改排序键不起作用（实测 cloud_plugin 仍被后文的 ComfyUI 压过）。
                          "weight": len(lab) + (1000 if text.find(lab) == 0 else 0),
                          "pos": text.find(lab),
                          "how": "label", "domain": c.get("domain")})
    # ③ 名字 token **始终参竞**（不是只在没自称谓时才用）。
    #    实测 genoffice_bridge：描述里写着「GenOffice AI 线 → 统一密钥网关的…」，
    #    同时命中了 key_gateway 的自称谓「统一密钥网关」⇒ 若只在"无自称谓"时
    #    才看名字 token，它就永远被 key_gateway 抢走。
    # ③ 名字 token **只在完全没有自称谓命中时**才用（纯兜底）。
    #    🔴 试过"始终参竞"，结果通用词 over-match 严重：
    #       omni_plug 被 brain_execute 抢走（因为描述里有 "execute"），
    #       replan_loop / task_graph 被 wf_status 抢走（"status"）。
    #    素材上分不开的（如 genoffice vs genoffice_bridge），
    #    **宁可标 ambiguous 交人，也不硬猜一个。**
    if not cands:
        # 🔴 2026-10-28：**归一化整名命中优先**（放在 token 匹配之前）。
        #   实测 ul_tars_desktop 描述是英文 "Ul-TARS Desktop desktop agent"，
        #   自称谓取空、token 匹配又和别的 desktop 系打平而被抢走。
        #   整名（去 _ - 空格、小写）出现在文本里 ⇒ 就是它自己。
        _txtf = _re.sub(r"[\s_\-]+", "", text.lower())
        for c in all_caps():
            if not isinstance(c, dict):
                continue
            _n = str(c.get("name") or "")
            _flat = _re.sub(r"[\s_\-]+", "", _n.lower())
            if _flat and _flat in _txtf:
                cands.append({"cap": _n, "label": _n, "weight": 999,
                              "pos": _txtf.find(_flat), "how": "name_exact",
                              "domain": c.get("domain")})
        if cands:
            # 🔴 2026-10-28：排序键 = **位置 0 优先 → 更长的标签优先 → 位置靠前优先**。
            #   ① 位置 0 就是这一位自己的名字（cloud_plugin 的「云插件」在开头的
            #      却被后文「ComfyUI」按长度压过 ⇒ 位置优先修掉）
            #   ② 同为位置 0 时取更长更具体的（absorb_loop 的「吞天闭环」
            #      必须压过 devour_scan 的短标签「吞天」）
            best = sorted(cands, key=lambda x: (0 if x["pos"] == 0 else 1, -x["weight"], x["pos"]))[0]
            return {"ok": True, "best": best, "tied": [], "ambiguous": False,
                    "how": "name_exact"}

    if not cands:
        GENERIC = {"status", "models", "model", "tools", "tool", "board",
                   "index", "check", "verify", "watch", "queue", "route",
                   "plan", "read", "write", "list", "show", "info", "data"}
        for c in all_caps():
            if not isinstance(c, dict):
                continue
            nm = str(c.get("name") or "")
            toks = [t for t in _re.split(r"[_\W]+", nm.lower())
                    if len(t) >= 5 and t not in GENERIC]
            hit = [t for t in toks if t in text.lower()]
            if hit:
                t0 = max(hit, key=len)
                cands.append({"cap": nm, "label": t0, "weight": len(t0),
                              "pos": text.lower().find(t0),
                              "how": "name_token", "domain": c.get("domain")})
        if not cands:
            return {"ok": False, "why": "无自称谓、无名字 token 命中"}

    # ② 撞车（同 label）时延展
    tops = max(x["weight"] for x in cands)
    tied = [x for x in cands if x["weight"] == tops]
    if len(tied) > 1 and all(x["how"] == "label" for x in tied):
        for x in tied:
            d = ""
            for c in all_caps():
                if isinstance(c, dict) and str(c.get("name")) == x["cap"]:
                    d = _post_colon(c.get("desc") or "")
                    break
            if d and d in text:
                x["weight"] += len(d)
                x["label"] = "%s：%s" % (x["label"], d)
                x["how"] = "label+tail"
        tops = max(x["weight"] for x in cands)
        tied = [x for x in cands if x["weight"] == tops]

    # ① 位置优先；再平手才按名字长度
    tied.sort(key=lambda x: (x["pos"], len(x["cap"])))
    pick = dict(tied[0])
    pick["ambiguous"] = len(tied) > 1
    pick["tied"] = [x["cap"] for x in tied] if len(tied) > 1 else []
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
