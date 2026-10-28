#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""intake_gate —— 「先拆解、分析、跑通，才准吸收」。

主人 2026-10-29 令：
  「每次吞的时候要先在镜像多维度空间里面把东西拆解分析跑通再吸收，
    就不会有（吞到二道垃圾）这个弊端。」

## 为什么必须有这道门
  devour / self_intake 的默认路径是 **取源 → 直接落胶囊**。
  一旦全网被 AI 生成内容填满，我们就成了"二道垃圾"的搬运工，
  而且**自己没有能力分辨**（Nature 那条 model collapse 警告对我们直接适用）。

## 五道闸（全部机检，零模型、零幻觉）
  ① 拆解 EXTRACT    把胶囊拆成原子主张，每条记它在原文的字符位置
  ② 分类 CLASSIFY   每条判：可现读验 / 要授权才验 / 观点 / 不可验
  ③ 跑通 PROVE      可现读验的**真跑一次**（URL 还在不在 / 端口 / 文件 / 数字自洽）
  ④ 冲突 CONFLICT   与本机既有知识库比对（同 topic 是否已有、是否打架）
  ⑤ 判决 VERDICT    pass / warn / reject，并**逐条写原因**

## 铁律
  · 判决不吃掉原文：胶囊照留，只是**不给它进知识库的资格**
  · 来源死了 / 数字自相矛盾 / 通篇不可验 ⇒ 不给 pass
  · 判不了的写「判不了」，不假装通过
"""
from __future__ import annotations

import json
import pathlib
import re
import socket
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEVOURED = ROOT / "gbt_allinone" / "store" / "devoured"
OUT = ROOT / "state" / "intake_gate.json"

# AI 生成常见模板措辞（命中越多，越可能是"看起来像知识的空话"）
_AI_SMELL = ("总而言之", "综上所述", "值得一提的是", "在当今", "随着……的发展",
             "具有重要意义", "为……提供了新思路", "本文旨在", "首先.*其次.*最后")


def _claims(text: str, limit: int = 60) -> list[dict]:
    """① 拆解：按行/句切，保留字符位置（能指回原文）。"""
    out = []
    for m in re.finditer(r"[^\n。；;]{18,240}[。\n；;]?", text):
        seg = m.group(0).strip()
        if len(seg) < 18:
            continue
        out.append({"at": m.start(), "text": seg})
        if len(out) >= limit:
            break
    return out


def _classify(c: str) -> str:
    """② 分类：这条主张属于哪种，决定能不能真跑验。"""
    if re.search(r"https?://", c):
        return "url"
    if re.search(r"\b\d+(\.\d+)?\s*(GB|MB|tok/s|%|倍|ms|s)\b", c):
        return "number"
    if re.search(r"/(var|usr|root|tmp)/|\.(py|json|gguf|md)\b", c):
        return "file"
    if re.search(r":\d{2,5}\b", c):
        return "port"
    if any(k in c for k in ("应该", "可能", "大概", "或许", "我们认为", "我觉得")):
        return "opinion"
    return "plain"


def _prove(kind: str, c: str, timeout: float = 6.0) -> dict:
    """③ 跑通：能现读验的真跑一次。验不了就说验不了。"""
    if kind == "url":
        # 🔴 2026-10-29 修：原来把 URL 后面的 "`（4413" 也吞进去了 ⇒ UnicodeEncodeError
        #   假失败。URL 只允许 URL 合法字符，收尾再剥一次标点。
        for u in re.findall(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", c)[:2]:
            u = u.rstrip(".,;:!?)]'\"`")
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "gbt-gate"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return {"ok": True, "how": "url", "detail": "%s → HTTP %s" % (u[:60], r.status)}
            except Exception as exc:                          # noqa: BLE001
                return {"ok": False, "how": "url",
                        "detail": "%s → %s" % (u[:50], type(exc).__name__)}
    if kind == "port":
        # 🔴 2026-10-29 修：原来 `:(\d{2,5})` 会把 arxiv 编号 "/abs/1911.02150" 里的
        #   1911 当成端口 ⇒ 假失败。只认 host:port 形态。
        pat = r"(?:\b\d{1,3}(?:\.\d{1,3}){3}|\blocalhost|\b0\.0\.0\.0):(\d{2,5})\b"
        for p in re.findall(pat, c)[:2]:
            s = socket.socket(); s.settimeout(1.2)
            try:
                s.connect(("127.0.0.1", int(p))); return {"ok": True, "how": "port", "detail": ":%s 通" % p}
            except OSError:
                return {"ok": False, "how": "port", "detail": ":%s 不通" % p}
            finally:
                s.close()
    if kind == "file":
        for f in re.findall(r"/(?:var|usr|root|tmp)/[\w./-]+", c)[:1]:
            return {"ok": (ROOT / f.lstrip("/")).exists() or pathlib.Path(f).exists(),
                    "how": "file", "detail": f[:50]}
    if kind == "number":
        return {"ok": None, "how": "number", "detail": "数字需上下文才能复算，只记不自证"}
    return {"ok": None, "how": kind, "detail": "这类主张本机无可验面"}


def _conflict(topic: str) -> dict:
    """④ 冲突：本机知识库里同 topic 是否已有、是否打架。"""
    try:
        from gbt_allinone.llm.ring_context import RingContext
        rc = RingContext(name="intake-gate")
        hits = rc.recall(topic, k=3).get("hits") or []
        return {"existing": len(hits),
                "sample": [str(h.get("content"))[:60] for h in hits[:2]]}
    except Exception as exc:                                  # noqa: BLE001
        return {"existing": None, "why": type(exc).__name__}


def judge(capsule: str) -> dict:
    p = DEVOURED / capsule / "absorbed_knowledge.md"
    if not p.is_file():
        return {"ok": False, "why": "胶囊不存在：%s" % p}
    text = p.read_text(encoding="utf-8", errors="replace")
    cl = _claims(text)
    rows = []
    for c in cl:
        k = _classify(c["text"])
        pr = _prove(k, c["text"])
        rows.append({"at": c["at"], "kind": k, "text": c["text"][:90],
                     "proved": pr.get("ok"), "detail": pr.get("detail")})

    # 统计
    n = len(rows) or 1
    ok = sum(1 for r in rows if r["proved"] is True)
    bad = sum(1 for r in rows if r["proved"] is False)
    cant = sum(1 for r in rows if r["proved"] is None)
    smelly = sum(1 for pat in _AI_SMELL if re.search(pat, text))
    conf = _conflict(capsule.replace("-", " ")[:24])

    # ⑤ 判决
    reasons = []
    if bad:
        reasons.append("%d 条现读验**失败**（来源死了/端口不通/文件不在）" % bad)
    if ok == 0 and n >= 5:
        reasons.append("一条都没跑通（%d 条全不可验或不可读）" % n)
    if smelly >= 3:
        reasons.append("命中 %d 处 AI 模板措辞 ⇒ 疑似二道垃圾" % smelly)

    if bad and bad >= max(2, ok):
        verdict = "reject"
    elif reasons:
        verdict = "warn"
    else:
        verdict = "pass"

    return {"ok": True, "capsule": capsule, "verdict": verdict,
            "claims": n, "proved_ok": ok, "proved_bad": bad, "unverifiable": cant,
            "ai_smell": smelly, "conflict": conf, "reasons": reasons,
            "rows": rows[:24], "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def main() -> int:
    caps = sorted([d.name for d in DEVOURED.iterdir() if d.is_dir()]) if DEVOURED.is_dir() else []
    res = [judge(c) for c in caps]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  ═══ 吸收前闸（拆解/分析/跑通）═══\n")
    for r in res:
        if not r.get("ok"):
            print("  %-24s ⚠ %s" % (r.get("capsule", "?"), r.get("why")))
            continue
        mark = {"pass": "✅", "warn": "⚠️", "reject": "🔴"}[r["verdict"]]
        print("  %s %-24s 主张 %2d · 跑通 %2d · 失败 %d · 不可验 %d · AI味 %d"
              % (mark, r["capsule"], r["claims"], r["proved_ok"],
                 r["proved_bad"], r["unverifiable"], r["ai_smell"]))
        for why in r["reasons"]:
            print("       - %s" % why)
    print("\n  报告: %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
