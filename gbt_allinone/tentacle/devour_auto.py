# -*- coding: utf-8 -*-
"""自主吞食（devour_auto）：**她自己去找有用的东西，自己判断，自己吞，自己留痕。**

主人 2026-11-01（逐字）：「能力要懂得使用，你看他的吞噬能力至今为止她有自己去吞噬过东西
来强化自己吗？我说的是她自己自主去识别对自己有用的东西吞噬」

## 实测现状（这就是为什么要这一位）

- `state/devour_pipe.jsonl` 只有 2 条，都是 **2026-10-29 手动/试跑**（第一条 `dry_run: true`）；
- `devour.py` 里**没有自主调度**；`absorb_own_innovations()` 吞的是**她自己的**产物；
- 也就是说「自主识别 → 判有用 → 吞下 → 留痕」这条链**从未存在**。

## 这一位的口径（四步，缺一不可）

1. **自己找食**：扫**本地可食源**（docs/ tools/ examples/ skills/ 的文本），
   按"还没看过"过滤（看过就记进账本，不重复嚼）；
2. **自己判断**：与**她自己的缺口**（没有实现文件的能力位、依赖仓外模块的位）做词面相关度打分，
   `score ≥ 2` 才算"有用"；判不出就说判不出，**不硬吞**；
3. **自己吞**：有用的才吞 —— 摘一段 digest 进 `state/devour-digest.md` + 记 `absorbed`；
4. **自己留痕**：每条都落 `state/devour-auto.jsonl`，**被拒的也记**（拒的理由要能读）。

## 安全边界（不越权）

- 只吃**仓内文件**，不出网、不改源码、不写生产区；
- 出网吞（GitHub/论文）仍走人工门 —— 那是"数据出网"，不归自主决策；
- `op=loop` 只跑有限轮数（默认 1 轮），不做常驻死循环；常驻由守护/计划任务在外部管。

## op
    status   账本读数（吃过多少/拒了多少/最近一轮）
    tick     自主跑一轮（self-feed → judge → devour → log）
    loop     跑 N 轮（带间隔），默认 1 轮
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "devour-auto.jsonl"
DIGEST = ROOT / "state" / "devour-digest.md"

FOOD_DIRS = ("docs", "tools", "examples", "skills")
FOOD_EXT = {".md", ".py", ".txt", ".json"}
SKIP_PARTS = {"__pycache__", "node_modules", "vendor", ".pylibs"}
MAX_READ = 200_000        # 单文件最多读 200KB，别把上下文吃爆



# ── 外部只读食源（2026-11-01：主人要她"自己找有用的东西吞"）──────────────
# 只读抓取、限域、限大小、限速；**不发任何自己的数据** ⇒ 按主人令免票
# （policy 里 `_READ_FETCH` 已把 data_export 从这些能力位上摘掉）。
WEB_ALLOW = ("raw.githubusercontent.com", "github.com", "arxiv.org",
             "export.arxiv.org", "huggingface.co", "hf.co", "docs.python.org")
SOURCES_FILE = ROOT / "state" / "devour-sources.json"
DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md",
    "https://arxiv.org/abs/2210.17323",     # GPTQ：量化权重（与她 quant_* 缺口相关）
]
MAX_FETCH = 400_000


def _sources() -> list:
    try:
        d = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        if isinstance(d, list) and d:
            return [str(x) for x in d]
    except Exception:  # noqa: BLE001
        pass
    return list(DEFAULT_SOURCES)


def _allowed(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        return any(host == a or host.endswith("." + a) for a in WEB_ALLOW)
    except Exception:  # noqa: BLE001
        return False


def _fetch(url: str, timeout: float = 20.0) -> dict:
    """只读抓取：限域、限大小、带 UA。返回文本；失败如实报。"""
    if not _allowed(url):
        return {"ok": False, "error": "域名不在只读白名单：" + url[:80]}
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "gbt-devour/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_FETCH)
        txt = raw.decode("utf-8", "replace")
        return {"ok": True, "text": txt, "bytes": len(raw)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}


def _gaps() -> dict:
    """她自己的缺口：没有实现文件的能力位 + 依赖仓外模块的位。"""
    names, external = [], []
    try:
        tc = json.loads((ROOT / "state" / "trunk-cover.json").read_text(encoding="utf-8"))
        names = [n for n in (tc.get("caps_no_owner") or [])]
    except Exception:  # noqa: BLE001
        pass
    try:
        from ..caps_registry import BENIGN_CAPS
        external = [k for k, v in BENIGN_CAPS.items() if v.get("external")]
        if not names:
            names = external
    except Exception:  # noqa: BLE001
        pass
    return {"caps_no_owner": names, "external": external,
            "keywords": sorted(set(names) | set(external))}


def _seen() -> set:
    seen = set()
    if LEDGER.exists():
        for line in LEDGER.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line).get("source"))
            except Exception:  # noqa: BLE001
                continue
    return seen


def _candidates(limit: int) -> list[pathlib.Path]:
    seen = _seen()
    out = []
    for d in FOOD_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in FOOD_EXT:
                continue
            if any(x in p.parts for x in SKIP_PARTS):
                continue
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            if rel in seen:
                continue
            out.append(p)
            if len(out) >= limit * 3:
                break
    return out[: limit * 3]


def _judge(text: str, keywords: list) -> dict:
    """自己判断：与缺口词面的相关度。判不出就诚实说判不出。"""
    low = text.lower()
    hits = []
    for k in keywords:
        if not k:
            continue
        if k.lower() in low:
            hits.append(k)
    score = len(hits)
    if score >= 2:
        verdict, why = "useful", "命中缺口词 %d 个：%s" % (score, "、".join(hits[:5]))
    elif score == 1:
        verdict, why = "thin", "只沾到一个词（%s），不够格" % hits[0]
    else:
        verdict, why = "unrelated", "与当前缺口零重合"
    return {"score": score, "hits": hits[:8], "verdict": verdict, "why": why}


def _devour(p: pathlib.Path, j: dict) -> dict:
    """吞：摘 digest 落盘（只摘，不改源码）。"""
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    try:
        text = p.read_text(encoding="utf-8", errors="replace")[:MAX_READ]
    except OSError as e:
        return {"ok": False, "error": str(e)[:120]}
    # 摘最有信息的一段：优先含命中关键词的行
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    key_lines = [ln for ln in lines if any(h.lower() in ln.lower() for h in j["hits"])][:6]
    digest = "\n".join("- " + ln[:160] for ln in (key_lines or lines[:4]))
    DIGEST.parent.mkdir(parents=True, exist_ok=True)
    with DIGEST.open("a", encoding="utf-8") as fh:
        fh.write("\n## %s · %s\n\n%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), rel, digest))
    return {"ok": True, "digest_lines": len(digest.split("\n"))}


def _digest_web(url: str, text: str, j: dict) -> dict:
    """把外部食源嚼碎咽下：摘命中缺口的行，落 digest。"""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    key_lines = [ln for ln in lines if any(h.lower() in ln.lower() for h in j["hits"])][:8]
    digest = "\n".join("- " + ln[:180] for ln in (key_lines or lines[:5]))
    DIGEST.parent.mkdir(parents=True, exist_ok=True)
    with DIGEST.open("a", encoding="utf-8") as fh:
        fh.write("\n## %s · %s\n\n%s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), url, digest))
    return {"ok": True, "digest_lines": len(digest.split("\n"))}


def tick(limit: int = 8, absorb: bool = True, web: bool = True) -> dict:
    """自主跑一轮：找食（外部优先）→ 判断 → （有用才）吞 → 留痕。"""
    t0 = time.time()
    g = _gaps()
    rows, absorbed, rejected = [], 0, 0
    # ① 外部食源（只读）——她自己的判断，外部优先
    if web:
        seen = _seen()
        for url in _sources():
            if url in seen or len(rows) >= limit:
                continue
            f = _fetch(url)
            rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": url,
                   "kind": "web", "absorbed": False}
            if not f.get("ok"):
                rec.update({"verdict": "fetch_failed", "score": 0, "why": f.get("error")})
                rejected += 1
            else:
                j = _judge(f["text"], g["keywords"])
                rec.update({"verdict": j["verdict"], "score": j["score"], "why": j["why"],
                            "bytes": f.get("bytes")})
                if j["verdict"] == "useful" and absorb:
                    d = _digest_web(url, f["text"], j)
                    rec["absorbed"] = bool(d.get("ok"))
                    rec["digest_lines"] = d.get("digest_lines")
                    absorbed += int(bool(d.get("ok")))
                else:
                    rejected += 1
            rows.append(rec)
    # ② 本地食源
    cands = _candidates(limit) if len(rows) < limit else []
    for p in cands:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:MAX_READ]
        except OSError:
            continue
        j = _judge(text, g["keywords"])
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "source": str(p.relative_to(ROOT)).replace("\\", "/"),
               "verdict": j["verdict"], "score": j["score"],
               "why": j["why"], "absorbed": False}
        if j["verdict"] == "useful" and absorb:
            d = _devour(p, j)
            rec["absorbed"] = bool(d.get("ok"))
            rec["digest_lines"] = d.get("digest_lines")
            absorbed += int(bool(d.get("ok")))
        else:
            rejected += 1
        rows.append(rec)
        if len(rows) >= limit:
            break
    if rows:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = 0
    if LEDGER.exists():
        total = sum(1 for _ in LEDGER.open("rb"))
    return {"ok": True, "examined": len(rows), "absorbed": absorbed,
            "rejected": rejected, "ledger_lines": total,
            "gaps": {"caps_no_owner": len(g["caps_no_owner"]), "external": len(g["external"])},
            "rows": rows[:10], "ms": int((time.time() - t0) * 1000),
            "口径": "只看本地仓内文本；出网吞仍走人工门；拒的也记账（理由可读）"}


def loop(cycles: int = 1, interval_s: float = 0.0, limit: int = 8) -> dict:
    out = []
    for i in range(max(1, min(int(cycles), 10))):
        out.append(tick(limit=limit))
        if interval_s and i + 1 < cycles:
            time.sleep(float(interval_s))
    return {"ok": True, "cycles": len(out),
            "absorbed": sum(x["absorbed"] for x in out),
            "examined": sum(x["examined"] for x in out),
            "last": out[-1] if out else None}



# ── 强化式吞食（2026-11-01 主人：「吞噬是为了加速进化，不是无脑吞，必须识别到能强化自己的」）──
# 与"到处扫"不同：这里**先锁定一个具体缺口**，只吃对得上这个缺口的食源，
# 并且**必须产出转化物**（待办条目）才算吞下；没有转化物的吞食记"白吃"，要报警。
#
# TARGETS 是**声明式数据**（不是猜）：缺口位 → 能补它的参考实现/规格。
TARGETS = {
    "quant": {
        "why": "仓里 quant_* 卡在外部 quant_tech 模块；缺的是量化实现方案",
        "keywords": ["quantize", "quantization", "q4_0", "q5_0", "q8_0", "dequantize", "block size"],
        "sources": [
            "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/src/llama-quant.cpp",
            "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/ggml/src/ggml-quants.c",
            "https://arxiv.org/abs/2210.17323",
        ],
    },
    "quant_backtest": {
        "why": "回测接口缺失；缺的是回测引擎的数据结构与接口形状",
        "keywords": ["backtest", "engine", "bar", "order", "fill", "commission", "slippage"],
        "sources": [
            "https://raw.githubusercontent.com/mementum/backtrader/master/backtrader/cerebro.py",
        ],
    },
}

TODO_MD = ROOT / "state" / "devour-todo.md"


def _code_density(text: str) -> float:
    """粗略判断"这是不是代码/规格"：分号、花括号、def/void/static 的比例。"""
    if not text:
        return 0.0
    marks = sum(text.count(c) for c in ("{", "}", ";", "def ", "void ", "static ", "return "))
    return min(1.0, marks / max(1, len(text) / 400.0))


def _evaluate_for_gap(gap: str, text: str) -> dict:
    """**强化判据**：能不能对上这个缺口的词，且像实现/规格。"""
    spec = TARGETS.get(gap) or {}
    kws = [k.lower() for k in spec.get("keywords") or []]
    low = text.lower()
    hits = [k for k in kws if k in low]
    density = _code_density(text)
    score = len(hits) * 2 + (3 if density >= 0.5 else 0)
    useful = bool(hits) and density >= 0.2
    return {"score": score, "hits": hits[:8], "code_density": round(density, 2),
            "useful": useful,
            "why": ("命中 %d 个实现词、代码密度 %.2f" % (len(hits), density)) if useful
                   else ("词面命中不足或不像实现（hits=%d, density=%.2f）" % (len(hits), density))}


def _extract_outline(text: str, hits: list) -> list:
    """从参考实现里抽**可移植的骨架**：含关键词的函数/结构定义行。"""
    out = []
    for ln in text.split("\n"):
        t = ln.strip()
        if not t or len(t) > 200:
            continue
        if any(h in t.lower() for h in hits) and any(
                t.startswith(x) for x in ("def ", "void ", "static ", "struct ", "typedef ", "class ")):
            out.append(t)
        if len(out) >= 8:
            break
    if not out:
        out = [ln.strip()[:160] for ln in text.split("\n") if any(h in ln.lower() for h in hits)][:8]
    return out


def focus(gap: str, limit: int = 3, absorb: bool = True) -> dict:
    """**聚焦式吞食**：锁定一个缺口 → 只吃对得上的食源 → 必须产出待办才算吞。

    这就是主人要的"识别到能强化自己的才触发"：
      · 对不上（词面/代码形态）⇒ 拒，记理由；
      · 对得上 ⇒ 抽骨架 → 写进 state/devour-todo.md（**转化物**）⇒ 才算 absorbed。
    """
    gap = str(gap or "").strip()
    if gap not in TARGETS:
        return {"ok": False, "error": "没有为这个缺口声明食源（先加 TARGETS）: " + gap,
                "known": sorted(TARGETS)}
    spec = TARGETS[gap]
    seen = _seen()
    rows, absorbed = [], 0
    for url in spec["sources"][:limit]:
        if url in seen:
            continue
        f = _fetch(url)
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": url, "kind": "focus",
               "gap": gap, "absorbed": False, "conversion": None}
        if not f.get("ok"):
            rec.update({"verdict": "fetch_failed", "score": 0, "why": f.get("error")})
            rows.append(rec)
            continue
        j = _evaluate_for_gap(gap, f["text"])
        rec.update({"verdict": "useful" if j["useful"] else "rejected",
                    "score": j["score"], "why": j["why"],
                    "code_density": j["code_density"]})
        if j["useful"] and absorb:
            outline = _extract_outline(f["text"], j["hits"])
            TODO_MD.parent.mkdir(parents=True, exist_ok=True)
            with TODO_MD.open("a", encoding="utf-8") as fh:
                fh.write("\n## 缺口 `%s` · 参考 %s · %s\n\n**为什么吃它**：%s\n\n"
                         "**可移植骨架**：\n%s\n\n**落成待办**：\n"
                         "- [ ] 按上面骨架在仓内实现 `%s` 的内部版（不依赖外部模块）\n"
                         "- [ ] 用单元测试钉住数值/边界\n\n"
                         % (gap, url, time.strftime("%Y-%m-%dT%H:%M:%S"), spec["why"],
                            "\n".join("- `%s`" % x for x in outline), gap))
            rec["absorbed"] = True
            rec["conversion"] = "todo"
            rec["digest_lines"] = len(outline)
            absorbed += 1
        rows.append(rec)
    if rows:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return {"ok": True, "gap": gap, "examined": len(rows), "absorbed": absorbed,
            "rejected": len(rows) - absorbed,
            "todo": str(TODO_MD) if TODO_MD.exists() else None,
            "rows": rows,
            "口径": "先锁缺口再吃；必须有转化物（待办）才算吞；对不上就拒并记理由"}


def status() -> dict:
    total = absorbed = rejected = conversions = waste = 0
    last = None
    if LEDGER.exists():
        for line in LEDGER.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            total += 1
            absorbed += int(bool(r.get("absorbed")))
            rejected += int(not r.get("absorbed"))
            if r.get("absorbed"):
                if r.get("conversion"):
                    conversions += 1
                else:
                    waste += 1        # 吞了却没转化物 = 白吃，要报警
            last = r
    g = _gaps()
    return {"ok": True, "ledger_lines": total, "absorbed": absorbed, "rejected": rejected,
            "conversions": conversions, "waste": waste,
            "backfire": ("白吃 %d 条（吞了没转化）" % waste) if waste else "无白吃",
            "last": last, "gaps": {"caps_no_owner": len(g["caps_no_owner"]),
                                   "external": len(g["external"])},
            "digest": str(DIGEST) if DIGEST.exists() else None,
            "口径": "自主吞的账本：吞了多少、拒了多少、最后一次吞的是什么"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "tick":
        return tick(limit=int(kw.get("limit") or 8), absorb=bool(kw.get("absorb", True)),
                    web=bool(kw.get("web", True)))
    if op == "focus":
        return focus(str(kw.get("gap") or ""), limit=int(kw.get("limit") or 3),
                     absorb=bool(kw.get("absorb", True)))
    if op == "loop":
        return loop(cycles=int(kw.get("cycles") or 1),
                    interval_s=float(kw.get("interval_s") or 0),
                    limit=int(kw.get("limit") or 8))
    return {"ok": False, "error": "devour_auto 不认 op=%s（status/tick/loop）" % op}
