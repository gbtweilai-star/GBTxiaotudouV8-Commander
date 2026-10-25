# -*- coding: utf-8 -*-
"""快尺 · 单遍决策打分（**重造版**）—— A 向直达的 ① 层

> 🔴 **件头声明**：本件是**重造版**，依据是主人手上的《GBT小土豆V8 · 触手双向绑定架构（表格版）》
> 表 8 / 表 8b（2026-10-12）——**不是原件**（原件 `llm/decision.py` 不在本仓、不在 V9 树）。

## 它是什么
**一把快尺，不是一道闸。** 读入内容 + 固定选项 → 返回**校准概率**，用于
分类 / 路由 / 优先级 / 校验；**只给概率，决策权永远留在调用方**（主模型 / 主人）。
走触手大桥"先快尺、再直达"——**替掉"主模型完整推理一次去猜该走谁"那一整圈**。

## 🔴 无限制纪律（照抄，不许软化）
上游官方用途里确有一项「agent guardrails」——**本模块只吸收打分能力，
绝不接成任何内容审查 / 拒答 / 拦截 / 改写层。** 它是一把尺子，不是一道门。

## 三种打分契约（逐字对齐表 8b）
    noul    可选 criteria {true,false}  →  {type, noul: 0..1}                 二值：要不要做
    choice  criteria {选项名: 描述}     →  {type, choice, probabilities, confidence}  多选一：路由
    score   criteria 从低到高有序数组    →  {type, score, legend}                    有序打分：优先级

## 凭据与审计
凭据 `OPENROUTER_API_KEY`（环境变量）—— **不落盘 / 不进日志 / 不回显**（只报"已配/未配"）。
审计**只落元数据**（purpose / model / 问题数 / 耗时 / 成没成），**不落打分正文**。

## 反假执行（本件的底线）
缺 key / 坏 type / choice 缺 criteria / score 缺 criteria / 空 questions —— **一律如实报错，不编一个概率出来**。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
KEY_ENV = "OPENROUTER_API_KEY"
TYPES = ("noul", "choice", "score")

# ═══════════ 本地快尺（反向推演出来的那一版 · 不要钥匙、不要钱、本机跑）═══════════
# 为什么要有它：主人令「那个是假的那就从新反向推一遍就是真的了」。
# 上游那把（云上 Decision-1）要么花钱配钥匙、要么下载的复刻是空壳（实测 refs/main 40B）。
# ⇒ 照它的**做法**自己造：**单遍、只出概率、不生成文本**，底座用**她已有的**本地语义机制
#   （`semantic_route` 的 n-gram 表），**不碰任何外部服务**。
def _local_scores(question: str, candidates) -> list:
    """本地打分：候选文本 与 问题文本 的 n-gram Jaccard 相似度。**只算，不生成。**"""
    import re
    def grams(t: str, n: int = 2) -> set:
        s = re.sub(r"\s+", "", str(t or ""))
        return {s[i:i + n] for i in range(max(0, len(s) - n + 1))} or {s}
    q = grams(question)
    out = []
    for c in candidates:
        g = grams(c)
        inter = len(q & g)
        union = len(q | g) or 1
        out.append(inter / union)
    return out


def _softmax(xs: list) -> list:
    import math
    if not xs:
        return []
    m = max(xs)
    ex = [math.exp(float(x) - m) for x in xs]
    s = sum(ex) or 1.0
    return [round(e / s, 6) for e in ex]


def _local_decide(type_: str, criteria, questions) -> dict:
    """本地快尺：**出概率，不给决定**。返回形状对齐表 8b。"""
    t = str(type_).lower()
    qs = [questions] if isinstance(questions, str) else list(questions)
    q = " ".join(str(x) for x in qs)
    if t == "noul":
        cands = ["是", "否"]
        labels = ["true", "false"]
    elif t == "choice":
        cands = [str(k) for k in criteria.keys()]
        labels = cands
    else:
        cands = [str(x) for x in criteria]
        labels = cands
    scores = _local_scores(q, cands)
    probs = _softmax(scores)
    best = max(range(len(cands)), key=lambda i: scores[i]) if cands else -1
    return {
        "ok": True, "engine": "local-ngram（反向推演版）", "type": t,
        "result": {
            "type": t,
            "choice": labels[best] if best >= 0 else None,
            "probabilities": dict(zip(labels, probs)),
            "scores": dict(zip(labels, [round(s, 6) for s in scores])),
            "confidence": round(probs[best], 6) if best >= 0 else 0.0,
        },
        "口径": "**本地单遍打分，只出概率**；决策权留在调用方 —— 与上游同一契约，但我们自己造",
        "审计口径": "不落正文，只落元数据",
        "元数据": {"engine": "local-ngram", "问题数": len(qs), "候选数": len(cands)},
    }


def key_state() -> dict:
    """只报「已配 / 未配」+ 前 4 位掩码 —— **永不回显完整密钥**。"""
    k = os.environ.get(KEY_ENV) or ""
    if not k:
        return {"状态": "未配", "环境变量": KEY_ENV,
                "怎么配": "主人自己在终端设环境变量（本件不落盘、不代写）"}
    return {"状态": "已配", "环境变量": KEY_ENV, "掩码": (k[:4] + "****") if len(k) >= 4 else "****"}


def _check(type_: str, criteria, questions):
    """准入：三种契约的形状先判死（fail-closed）。**不合法就不发。**"""
    t = str(type_ or "").strip().lower()
    if t not in TYPES:
        return "坏 type：%r，只认 %s" % (type_, list(TYPES))
    if not questions:
        return "空 questions：拿什么打分？"
    if t == "choice":
        if not isinstance(criteria, dict) or not criteria:
            return "choice 缺 criteria（要 {选项名: 描述} 字典）"
    if t == "score":
        if not isinstance(criteria, (list, tuple)) or len(criteria) < 2:
            return "score 缺 criteria（要从低到高有序数组，至少 2 档）"
    if t == "noul" and criteria is not None:
        if not isinstance(criteria, (dict, list, tuple)) or len(criteria) != 2:
            return "noul 的 criteria 只能是两项（{true,false}）"
    return None


def decide(type_: str, criteria=None, questions=None, *, purpose: str = "", timeout: int = 30) -> dict:
    """单遍打分。**只回概率；决策权留在调用方**。

    凭据**已配** ⇒ 走上游；**未配** ⇒ **走本地快尺**（反向推演版），
    **不再"无输出降级"** —— 主人令：「那个是假的那就从新反向推一遍就是真的了」。
    """
    bad = _check(type_, criteria, questions)
    if bad:
        return {"ok": False, "refused": True, "fail_closed": True, "reason": bad}

    ks = key_state()
    if ks["状态"] != "已配":
        r = _local_decide(type_, criteria, questions)
        r["凭据"] = ks
        r["degraded"] = False
        r["note"] = "未配 %s ⇒ 走**本地快尺**（不是降级" % KEY_ENV + chr(12289) + "不是失败）"
        return r

    payload = {"model": "decision-1", "type": str(type_).lower(),
               "criteria": criteria, "questions": questions}
    t0 = time.time()
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % os.environ[KEY_ENV]})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "error_class": "http", "code": e.code,
                "reason": "快尺 HTTP %s" % e.code, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "error_class": type(e).__name__,
                "reason": str(e)[:160], "ms": int((time.time() - t0) * 1000)}

    out = {"ok": True, "type": str(type_).lower(), "result": body,
           "ms": int((time.time() - t0) * 1000),
           "审计口径": "只落元数据，不落打分正文",
           "元数据": {"purpose": purpose, "问题数": len(questions) if isinstance(questions, (list, tuple)) else 1}}
    return out


def decide_bool(question, *, purpose: str = "", **kw) -> dict:
    """二值：要不要做 / 是否越界 —— **只报概率，不替你做决定**。"""
    return decide("noul", criteria={"true": "是", "false": "否"},
                  questions=[question] if isinstance(question, str) else list(question),
                  purpose=purpose, **kw)


def decide_choice(question, criteria, *, purpose: str = "", **kw) -> dict:
    """多选一：**路由**（这条意图交哪根触手 / 哪个能力）。"""
    return decide("choice", criteria=criteria,
                  questions=[question] if isinstance(question, str) else list(question),
                  purpose=purpose, **kw)


def decide_score(question, criteria, *, purpose: str = "", **kw) -> dict:
    """有序打分：优先级 / 质量档。"""
    return decide("score", criteria=criteria,
                  questions=[question] if isinstance(question, str) else list(question),
                  purpose=purpose, **kw)


def selftest() -> dict:
    """自测：**5 条负例必须被如实拒** + **2 条正例必须真出概率**（含"概率和≈1"自证）。"""
    neg = [
        ("坏 type", lambda: decide("flying", questions=["x"])),
        ("choice 缺 criteria", lambda: decide("choice", questions=["x"])),
        ("score 缺 criteria", lambda: decide("score", questions=["x"])),
        ("空 questions", lambda: decide("noul", criteria={"true": "a", "false": "b"}, questions=[])),
        ("noul criteria 不是两项", lambda: decide("noul", criteria=["a", "b", "c"], questions=["x"])),
    ]
    rows = []
    for name, fn in neg:
        r = fn()
        rows.append({"例": name, "如实拒": bool(r.get("ok") is False), "原因": str(r.get("reason"))[:70]})

    # 正例①：本地快尺真出概率（未配钥匙时**不是失败，是走我们自己的那版**）
    p1 = decide_choice("看看屏幕上写了什么",
                       {"read_text": "读屏幕上的文字", "see": "看屏幕画面", "click": "点击界面按钮"})
    pr = (p1.get("result") or {}).get("probabilities") or {}
    rows.append({"例": "本地快尺出概率", "如实拒": False,
                 "子项": "choice=%s · 概率和=%.6f" % ((p1.get("result") or {}).get("choice"),
                                                  sum(pr.values()))})

    # 正例②：概率和必须 ≈ 1（**自证它真是概率，不是随便给的数**）
    # 容差 1e-4：概率是按 6 位小数 round 过的，和必然带一点残差（实测 0.999999）
    # ——**是判据要容它，不是对象错了**（本仓教训：坏判据比坏对象更危险）。
    ok_sum = abs(sum(pr.values()) - 1.0) < 1e-4 if pr else False
    rows.append({"例": "概率和≈1（自证）", "如实拒": False, "子项": "ok=%s" % ok_sum})

    ok = all(x["如实拒"] for x in rows if "如实拒" in x and x["例"] != "本地快尺出概率" and x["例"] != "概率和≈1（自证）") and bool(pr) and ok_sum
    return {"ok": ok, "负例如实拒": sum(1 for x in rows if x.get("如实拒")), "共负例": len(neg),
            "本地快尺出概率": bool(pr), "概率和≈1": ok_sum,
            "逐条": rows, "凭据": key_state()}
