# gbt-capability: transformer
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""变压器（transformer）· 按原设计接上 · **能力核心已按成熟成品吃透后重做**（2026-09-27）。

## 为什么会有这个文件（主人令：「排查变压器是什么问题，为什么老是能源供给不足，重新设计好接上」
## + 追加：「**从新精准抓取能力核心学习吃透了再把细节看一遍再动手，免得老是接不上用不了**」）

**诊断结论**：变压器**从来没坏 —— 它从来没被接上**。
  · 09-22 设计稿写明「网关前置的**两级变压器**（压缩 + 快速输出，带前后两个数）」；
  · 09-26 日报结论：「`panel_server.py` 登记 pending · **从未接线**」；
  · 全仓 grep `变压器` 只命中设计稿与交付单，**零实现** ⇒ 每次调用全量送模型 ⇒ token 不降 ⇒ 能源必紧。

## 能力核心（精准抓取两处成熟成果，吃透再动手 —— 两处都是**一手源**，含它自己写的坑）
· **LLMLingua（microsoft/LLMLingua）核心**：用小模型给 token 打**重要性分**，按**显式预算**删次要 token
  （`rate=0.55` 或 `target_token=200`）；**段落可标记 `compress=False` 保护** —— 原文强调
  「retention of original prompt information like **ICL and reasoning**」；示例读数 2365 → 211 tokens（11.2x）。
  **它的坑**：压完文本"**看得见的破碎**"、需要一个小模型（有开销）、对域外数据效果差（LLMLingua-2 才针对域外）。
· **GPTCache（zilliztech/GPTCache）核心**：**语义近似命中** —— 查询嵌入 + 向量库 + 相似度阈值
  （`similarity_threshold=0.2`）判定命中；宣称 10x 成本 / 100x 速度。
  **它的坑（最要命的一条）**：**假命中（返回错答案）比不命中更坏**；另有假不命中、按行数淘汰会 OOM。

## 我们的落地口径（在本地能力范围内**取核心、避坑**）
  1. **指令保真**（LLMLingua 的 `compress=False` 思想）—— **指令段/结构段一个字都不压**，只压参考叙述；
  2. **显式预算** —— 支持 `rate=` 与 `target_chars=`；预算只作用于参考段；
  3. **近似缓存（GPTCache 思想的本地近似）** —— simhash + 汉明距离；**但假命中禁令**：
     近似命中**默认只报告、不返回答案**，要拿答案必须调用方显式 `allow_approx=True`；
  4. **真"语义"要嵌入模型** —— 本机没有本地嵌入 ⇒ **如实标注为"近似"**，并写清升级路径（换嵌入 + 向量库）。
  5. **可旁路（fail-open）** —— 字面量包含关系不成立、或没省下来 ⇒ **回原样**；宁可没省，不许压坏。

## 硬判据（原设计 §1.4：**必须给前后两个数**）
  · 压缩率（原字符 vs 压后）· 受保护行数/被压行数 · **字面量包含关系**（identifiers/files/commands 一个不丢）。

ops：
  compress   text=... [rate=0.6|target_chars=N]   分段保真压缩（给前后两个数）
  cache_get  text=... [threshold=3] [allow_approx] 精确命中 / 近似命中（近似默认只报不返答案）
  cache_put  text=... answer=...                   写缓存（同时存 simhash）
  autosize   context=... [limit_chars=...]         上下文快满 ⇒ **原文先落盘**再压（资料不丢）
  stats / selftest
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CACHE = _ROOT / "state" / "transformer_cache.json"
_LEDGER = _ROOT / "state" / "transformer_ledger.jsonl"
_SPILL = _ROOT / "state" / "context_spill"
_BITS = 64                        # simhash 位数

# 字面量抽取器（原设计 §1.3 指定的抓手：knowledge_base 的抽取器就是一台压缩机）
_RX = {
    "identifiers": re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b"),
    "files": re.compile(r"\b[\w./\\-]+\.(?:py|md|json|jsonl|ya?ml|txt|csv|xlsx|docx|pptx|pdf|mp4|png|jpg|html|js|ts|ps1|cmd|bat|sh)\b", re.I),
    # ⚠️ 血账：早先抓「命令词 + 后面 60 字符」⇒ 周边文本一变，同一个命令被判成"丢了"（判据不稳）。改为只抓稳定前缀。
    "commands": re.compile(r"\b(?:python|py|pip|npm|node|git|ffmpeg|curl|powershell|pwsh|cmd|docker|gh)\s+\S+"),
}

# 段落分级（**核心：指令一个字都不压** —— 判据照 LLMLingua 的 compress=False 落成可执行规则）
_INSTRUCTION_RX = re.compile(
    r"(必须|不许|禁止|务必|切记|红线|授权|命令[:：]|op=|任务[:：]|要求[:：]|"
    r"MUST|NEVER|REQUIRED|IMPORTANT|TODO|调用|不要)", re.I)
_STRUCT_RX = re.compile(r"^\s*(```|~~~|\{|\}|\[|\]|#|\||[-*]\s|\d+[.、])")


def _extract(text: str) -> dict:
    return {k: set(rx.findall(text or "")) for k, rx in _RX.items()}


def classify_lines(text: str) -> dict:
    """把行分成 指令 / 结构 / 参考 —— **只有参考段允许压**。"""
    # ⚠️ 血账（2026-09-27 实测）：早先还有一条"短行（<12 字符）也算结构"⇒ 80 行短填充文本
    # **全被保护**、一个字都压不动（protected_lines = 全部）⇒ 变压器等于没用。短行不是结构。
    b = {"instruction": [], "structure": [], "reference": []}
    for i, ln in enumerate((text or "").splitlines()):
        if _INSTRUCTION_RX.search(ln):
            b["instruction"].append(i)
        elif _STRUCT_RX.match(ln) and len(ln.strip()) > 0:
            b["structure"].append(i)
        else:
            b["reference"].append(i)
    return b


def _dedupe_lines(lines: list, ref: list) -> tuple:
    """去重：**原地标出**重复的参考行（不搬家）。返回 (要删的下标集合, 删了几行)。

    🔴 2026-10-29 改造（原来真会搬家，这是它只能默认关的真原因）：
      旧实现先把**整个参考段**拼成一整块，再插回「第一个参考位」，后面的参考行原地丢弃 ⇒
      结构行（标题/列表）被挤到文末、与它下面的正文脱钩。
      实测：205 行文档（每 40 行一个 `## 小标题`）压完，5 个标题全挤在末尾
      （位置 [0,122,123,124,125]），正文顺序彻底乱掉。
      省 6% token 换来「文档结构错乱」——对读上下文的模型是**负收益**。
      现在只回答「删哪几行」，拼装由 `compress()` 按原序走 ⇒ 只删行、never 搬家。
    """
    seen, drop, dup = set(), set(), 0
    for i in ref:
        key = re.sub(r"\s+", " ", lines[i]).strip()
        if len(key) <= 24:
            continue          # 短行不去重：信息密度高，删一个数字就伤内容
        if key in seen:
            drop.add(i)
            dup += 1
        else:
            seen.add(key)
    return drop, dup


def _collapse_json(text: str) -> tuple:
    """结构化压缩：重复 JSON 块折叠成一份 + 引用（**保留第一份**，标记打在后面）。

    🔴 2026-10-29 重写成**单次扫描**（先定位、再按段拼回），旧实现见 `_collapse_json_legacy`：
    它逐块对**全文**做 `str.replace`，耗时随「块数 × 当前全文长度」涨。
    实测（块数 ×4）：旧 7.5–7.8 倍，新 3.7–4.2 倍（线性应 ≈4 倍）。
    ⚠️ 顺带修掉旧实现一个位置上的错：`str.replace(b, …, 1)` 总是替换**全文第一个**，
    于是标记打在前面、留下的是**最后一份**。折叠数对，但「去重保序」的契约应当是**保留第一份**。
    """
    src = text or ""
    spans, seen, collapsed = [], set(), 0
    for m in re.finditer(r"(?s)\{[^{}]{40,}\}", src):
        b = m.group(0)
        norm = re.sub(r"\s+", "", b)
        if norm in seen:
            spans.append(m.span())
            collapsed += 1
        else:
            seen.add(norm)
    if not spans:
        return src, 0
    out, cur = [], 0
    for a, b in spans:
        out.append(src[cur:a])
        out.append("[同上：结构相同的 JSON 块，已折叠]")
        cur = b
    out.append(src[cur:])
    return "".join(out), collapsed


def _collapse_json_legacy(text: str) -> tuple:
    """**旧实现原件**（逐块对全文 `str.replace`）。

    ⛔ 只给 `selftest` 用：① 做「复杂度形状」的负对照 ② 记录它那个位置上的错（标记打在前面、
    留下最后一份）。**绝不许接进请求路径** —— 它就是把满窗口压缩拖慢的那个形状。
    """
    blocks = re.findall(r"(?s)\{[^{}]{40,}\}", text or "")
    out, collapsed, seen = text or "", 0, set()
    for b in blocks:
        norm = re.sub(r"\s+", "", b)
        if norm in seen:
            out = out.replace(b, "[同上：结构相同的 JSON 块，已折叠]", 1)
            collapsed += 1
        else:
            seen.add(norm)
    return out, collapsed


def _plan_trim(ref_live: list, keep_tail_lines: int) -> tuple:
    """裁陈旧：**只裁中段**（头 8 行=任务定义，尾=近期上下文）。返回 (要裁的下标集合, 标记点)。

    ⚠️ 这里同样**不搬家**：返回的是「要删哪些行」，标记点告诉拼装层在原位置插一行说明。
    """
    if not keep_tail_lines or len(ref_live) <= int(keep_tail_lines):
        return set(), None
    head_n = 8
    tail_n = max(1, int(keep_tail_lines) - head_n)
    mid = ref_live[head_n:len(ref_live) - tail_n]
    if not mid:
        return set(), None
    return set(mid), (mid[0], len(mid))


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _critical(text: str) -> set:
    """**关键**字面量（只有这些丢了才算压坏）：
      · 全部 `files`（文件名/路径）· 全部 `commands`（命令行）·
      · **指令行里**的 identifiers（指令里的名字一个不许丢）。
    ⚠️ 血账（2026-09-27 实测）：早先拿"全部 identifiers"当必留 ⇒ 真实长文本**永远旁路、一次也省不下来**
      —— 正是主人说的「接上了用不了」。参考叙述里的普通词**允许被压掉**（LLMLingua 也是这么干的）。
    """
    crit = set(_extract(text)["files"]) | set(_extract(text)["commands"])
    b = classify_lines(text)
    lines = (text or "").splitlines()
    for i in b["instruction"]:
        crit |= set(_RX["identifiers"].findall(lines[i]))
    return crit


def compress(text: str = "", keep_tail_lines: int = 120, rate: float = 0.0,
             target_chars: int = 0, **_kw) -> dict:
    """**核心版**：分段 → 只压参考段 → **按原序**拼回 → 报前后两个数。

    三条判据（每条都能红，见 `selftest`）：
      ① 指令/结构段**一字不动**；
      ② **段落顺序不变** —— 只删行，绝不把参考段搬去开头；
      ③ **关键**字面量一个不丢，丢了就 fail-open 回原样。
    """
    src = text or ""
    before = len(src)
    if before == 0:
        return {"ok": True, "op": "compress", "bypass": False, "chars_before": 0,
                "chars_after": 0, "ratio": 1.0, "protected_lines": 0, "note": "空输入"}
    crit_before = _critical(src)
    lines = src.splitlines()
    b = classify_lines(src)
    prot = set(b["instruction"]) | set(b["structure"])
    ref = b["reference"]

    # ① 去重（原地标出，不搬家）
    drop, dup = _dedupe_lines(lines, ref)
    # ② JSON 折叠：**逐行**折叠同一行里的重复块（行序不动）
    fold, folded = {}, 0
    for i in ref:
        if i in drop:
            continue
        new, c = _collapse_json(lines[i])
        if c:
            fold[i] = new
            folded += c
    # ③ 裁陈旧（只裁中段，头 8 行 + 尾部保留）
    live = [i for i in ref if i not in drop]
    mid_drop, marker = _plan_trim(live, keep_tail_lines)
    drop |= mid_drop
    trimmed = len(mid_drop)
    # ④ 预算（只作用于参考段）：target_chars 是**总目标**，要扣掉保护段占的字节。
    #    裁的顺序 = 先中段（③），仍超才从**尾部**再裁 —— 头尾都比中段重要。
    cost = {i: len(fold.get(i, lines[i])) + 1 for i in range(len(lines))}
    budget = 0
    if target_chars:
        budget = max(0, int(target_chars) - sum(len(lines[i]) + 1 for i in prot))
    elif rate:
        budget = max(0, int(sum(cost[i] for i in ref) * max(0.0, min(1.0, float(rate)))))
    tail_dropped = 0
    if budget:
        total = sum(cost[i] for i in range(len(lines)) if i not in drop)
        for i in reversed([x for x in ref if x not in drop]):
            if total <= budget:
                break
            drop.add(i)
            total -= cost[i]
            tail_dropped += 1
    # ⑤ **按原序**拼装：只跳过被删的行，位置一律不动（这是 2026-10-29 修的根因）
    out_lines = []
    for i, ln in enumerate(lines):
        if i in drop:
            if marker and i == marker[0]:
                out_lines.append("…〔中间 %d 行按相关性裁去〕…" % marker[1])
            continue
        out_lines.append(fold.get(i, ln))
    if tail_dropped:
        out_lines.append("…〔超出预算，尾部 %d 行未纳入〕…" % tail_dropped)
    joined = "\n".join(out_lines)
    after = len(joined)
    crit_after = _critical(joined)
    lost = sorted(crit_before - crit_after)
    keep_ok = not lost
    bypass = (not keep_ok) or (after >= before)
    if bypass:
        joined, after = src, before
    out = {"ok": True, "op": "compress", "bypass": bypass,
           "chars_before": before, "chars_after": after, "ratio": round(after / before, 4),
           "saved_chars": before - after,
           "protected_lines": len(prot), "compressed_lines": len(b["reference"]),
           "deduped": dup, "json_folded": folded, "lines_trimmed": trimmed + tail_dropped,
           "mid_trimmed": trimmed, "tail_dropped": tail_dropped,
           "budget_chars": budget, "critical_kept": keep_ok, "lost_critical": lost[:6],
           "text": joined,
           "_口径": "**指令/结构段一字不动**、**段落顺序不变（只删行不搬家）**；只压参考叙述；"
                   "**关键**字面量（files/commands/指令里的名字）一个不丢，丢了就 fail-open 回原样"}
    _log({"event": "compress", "before": before, "after": after, "bypass": bypass,
          "protected": len(prot), "ref": len(ref), "deduped": dup,
          "folded": folded, "trimmed": trimmed, "tail_dropped": tail_dropped,
          "budget": budget})
    return out


# ── 近似缓存（GPTCache 思想的本地近似；**假命中禁令**）────────────────────────
def _simhash(text: str, bits: int = _BITS) -> int:
    """simhash：token 词频 → 位向量投票。**这是"近似"，不是语义嵌入**（诚实标注）。"""
    toks = re.findall(r"[\w\u4e00-\u9fa5]+", (text or "").lower())
    if not toks:
        return 0
    vec = [0] * bits
    for t in toks:
        h = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(bits):
            vec[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i, v in enumerate(vec):
        if v > 0:
            out |= (1 << i)
    return out


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:4000]


def _key(text: str) -> str:
    return hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()[:20]


def _load_cache() -> dict:
    try:
        d = json.loads(_CACHE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def cache_put(text: str = "", answer: str = "", **_kw) -> dict:
    d = _load_cache()
    k = _key(text)
    d[k] = {"answer": answer, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "chars": len(answer or ""), "simhash": _simhash(text), "norm": _norm(text)[:200]}
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CACHE.with_name(_CACHE.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _CACHE)
    _log({"event": "cache_put", "key": k, "chars": len(answer or "")})
    return {"ok": True, "op": "cache_put", "key": k, "entries": len(d)}


def cache_get(text: str = "", threshold: int = 3, allow_approx: bool = False, **_kw) -> dict:
    """查缓存：① 精确命中 ⇒ 直接给答案；② **近似命中**（simhash 汉明距离 ≤ threshold）⇒
    **默认只报告、不返回答案**（照 GPTCache 的假命中教训：错答案比不命中更坏）；
    要拿近似答案必须调用方显式 `allow_approx=true`。"""
    d = _load_cache()
    k = _key(text)
    if k in d:
        _log({"event": "cache", "hit": "exact", "key": k})
        return {"ok": True, "op": "cache_get", "hit": "exact", "key": k, "similarity": 1.0,
                "answer": d[k].get("answer", ""), "approx": False, "saved_calls": 1}
    h = _simhash(text)
    best, best_d = None, 999
    for kk, v in d.items():
        dd = _hamming(h, int(v.get("simhash") or 0))
        if dd < best_d:
            best, best_d = (kk, v), dd
    if best and best_d <= int(threshold):
        sim = round(1 - best_d / _BITS, 4)
        _log({"event": "cache", "hit": "approx", "distance": best_d, "sim": sim})
        return {"ok": True, "op": "cache_get", "hit": "approx", "key": best[0],
                "distance": best_d, "similarity": sim, "approx": True,
                "answer": (best[1].get("answer", "") if allow_approx else ""),
                "answer_withheld": (not allow_approx),
                "saved_calls": 1 if allow_approx else 0,
                "_口径": "**假命中禁令**：近似命中默认只报告不返答案（GPTCache 教训：错答案比不命中更坏）；"
                        "要拿答案须 allow_approx=true；本近似是 simhash，**不是语义嵌入**"}
    _log({"event": "cache", "hit": "miss"})
    return {"ok": True, "op": "cache_get", "hit": "miss", "key": k,
            "nearest_distance": (best_d if best else None), "saved_calls": 0}


def autosize(context: str = "", limit_chars: int = 200_000, spill: bool = True, **_kw) -> dict:
    """**上下文快满就自动压缩**：超过阈值才压；**原文先落盘**（`state/context_spill/`）⇒ 资料不丢。"""
    used = len(context or "")
    if used <= max(1, int(limit_chars)):
        return {"ok": True, "op": "autosize", "need_compress": False, "used": used,
                "limit": int(limit_chars), "headroom": int(limit_chars) - used,
                "_口径": "没到阈值，不压（避免无谓改动）"}
    spill_path = ""
    if spill and context:
        _SPILL.mkdir(parents=True, exist_ok=True)
        sp = _SPILL / f"ctx-{time.strftime('%Y%m%d-%H%M%S')}.md"
        sp.write_text(context, encoding="utf-8")
        spill_path = str(sp.relative_to(_ROOT))
    c = compress(context)
    _log({"event": "autosize", "used": used, "after": c["chars_after"], "spill": spill_path})
    return {"ok": True, "op": "autosize", "need_compress": True, "used": used,
            "limit": int(limit_chars), "chars_before": c["chars_before"],
            "chars_after": c["chars_after"], "ratio": c["ratio"], "spill": spill_path,
            "critical_kept": c["critical_kept"], "bypass": c["bypass"], "text": c["text"],
            "_口径": "**原文先落 spill（资料不丢）再压**；字面量包含关系不成立则旁路"}


def stats(**_kw) -> dict:
    rows = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    comp = [r for r in rows if r.get("event") == "compress"]
    caches = [r for r in rows if r.get("event") == "cache"]
    return {"ok": True, "op": "stats", "compress_calls": len(comp),
            "chars_saved": sum(r.get("before", 0) - r.get("after", 0) for r in comp if not r.get("bypass")),
            "bypass_count": sum(1 for r in comp if r.get("bypass")),
            "protected_lines_total": sum(r.get("protected", 0) for r in comp),
            "usable": (sum(1 for r in comp if not r.get("bypass")) > 0),
            "cache_lookups": len(caches),
            "cache_hits_exact": sum(1 for r in caches if r.get("hit") == "exact"),
            "cache_hits_approx": sum(1 for r in caches if r.get("hit") == "approx"),
            "spill_files": len(list(_SPILL.glob("*.md"))) if _SPILL.is_dir() else 0,
            "_口径": "省字符=输入侧；省调用=输出侧（精确命中才算省整次调用；近似命中默认不返答案）"}


def selftest() -> int:
    """判据自检（**每一条都要能红**）。"""
    bad = 0
    # ① 指令保真：指令行必须一字不动
    ctx = "必须保留这一行指令，一个字都不许改。\n" + "\n".join(f"参考叙述第 {i} 行，用来占位。" for i in range(120))
    r = compress(ctx, target_chars=300)
    instr_kept = "必须保留这一行指令，一个字都不许改。" in r["text"]
    print(f"  [指令保真] 保护行 {r['protected_lines']} · 指令原样保留={instr_kept} · "
          f"{r['chars_before']} → {r['chars_after']}（比 {r['ratio']}）")
    if not instr_kept:
        print("    🔴 指令被压掉了"); bad += 1
    # ② 预算：给了 target_chars 就该接近它
    if r["budget_chars"] and r["chars_after"] > (r["budget_chars"] + r["protected_lines"] * 40) * 1.3:
        print(f"    🔴 没压到预算（{r['chars_after']} vs 预算 {r['budget_chars']}）"); bad += 1
    # ③ 字面量包含关系（不许丢）
    s2 = "命令：python tools/actioncam.py build\n" + "\n".join(f"填充行 {i}" for i in range(80))
    r2 = compress(s2, target_chars=200)
    print(f"  [关键信息] 保住={r2['critical_kept']} · 旁路={r2['bypass']} · "
          f"{r2['chars_before']} → {r2['chars_after']}")
    if not r2["critical_kept"] and not r2["bypass"]:
        print("    🔴 丢了关键信息却没旁路"); bad += 1
    if r2["bypass"] and r2["chars_before"] > 500:
        print("    🔴 真实长文本又旁路了（= 一次也省不下来，等于没用）"); bad += 1
    # ④ 近似缓存：近义查询应"报告近似但扣住答案"（假命中禁令）
    cache_put("把 E1E3 多镜版渲染出来，用 filmic 调色", "答案A")
    near = cache_get("把 E1E3 多镜版渲染出来 用 filmic 调色", threshold=8)
    far = cache_get("今天天气怎么样", threshold=3)
    print(f"  [缓存] 近似命中={near['hit']} · 扣住答案={near.get('answer_withheld')} · "
          f"远查询={far['hit']}（应 miss）")
    if near["hit"] == "approx" and near.get("answer"):
        print("    🔴 近似命中竟然直接给了答案（假命中风险）"); bad += 1
    if far["hit"] != "miss":
        print("    🔴 远查询误命中（假命中）"); bad += 1
    # ⑤ 上下文自动压缩 + 原文不丢
    big = "任务：把上下文压好。\n" + "\n".join(f"上下文行 {i}" for i in range(5000))
    a = autosize(big, limit_chars=2000)
    kept_original = bool(a.get("spill"))
    print(f"  [autosize] 需要压={a['need_compress']} · 原文已留档={kept_original} · "
          f"{a.get('chars_before')} → {a.get('chars_after')}")
    if not a["need_compress"] or not kept_original:
        print("    🔴 超阈值没压 / 原文没留档"); bad += 1
    # ⑥ **段落顺序不变**（2026-10-29 新立：旧实现会把参考段全搬到开头，结构行挤到文末）
    #    ⚠️ 判据**不能只看标题先后**：旧实现里标题的相对先后也没变（它们只是被挤到一起），
    #    真正坏的是「正文跑到了别人的标题底下」。所以判据是**归属**：
    #    每条幸存参考行，必须仍落在原属的那个小标题下面。
    ol = []
    for i in range(200):
        if i % 40 == 0:
            ol.append("## 小标题%d" % i)
        ol.append("参考条第%03d行，写一些普通的叙述内容用来占位。" % i)
    ol_src = "\n".join(ol)

    def _stray(text: str) -> list:
        """跑错节的参考行：它的行号所属小节 ≠ 它当前所在的小标题。"""
        out, cur = [], None
        for ln in text.splitlines():
            if ln.startswith("## 小标题"):
                cur = int(ln.replace("## 小标题", ""))
            elif ln.startswith("参考条第") and cur is not None:
                n = int(ln[4:7])
                if (n // 40) * 40 != cur:
                    out.append((n, cur))
        return out

    ro = compress(ol_src)
    stray_new = _stray(ro["text"])
    # 负对照（**放在自检里，不是终端里跑一把就算**）：把旧实现的「参考段合并成一块、
    # 插回第一个参考位」原样复刻，喂给同一条判据 —— 它必须红，否则判据是假的。
    _lg_drop, _ = _dedupe_lines(ol_src.splitlines(), classify_lines(ol_src)["reference"])
    _lg_kl = [i for i in classify_lines(ol_src)["reference"] if i not in _lg_drop]
    _lg_lines = ol_src.splitlines()
    _lg_block = "\n".join(_lg_lines[i] for i in _lg_kl[:8] + _lg_kl[-(120 - 8):])
    _lg_prot = set(classify_lines(ol_src)["instruction"]) | set(classify_lines(ol_src)["structure"])
    _lg_out, _ins = [], False
    for _i, _ln in enumerate(_lg_lines):
        if _i in _lg_prot:
            _lg_out.append(_ln)
        elif not _ins:
            _lg_out.append(_lg_block)
            _ins = True
    stray_old = _stray("\n".join(_lg_out))
    print(f"  [保序] 新实现跑错节 {len(stray_new)} 条 · 负对照(旧算法)跑错节 {len(stray_old)} 条"
          + (f"（例：第 {stray_old[0][0]} 行跑到小标题{stray_old[0][1]} 下）" if stray_old else ""))
    if not stray_old:
        print("    🔴 负对照没红 —— 这条判据是假的（它抓不到已知会坏的实现）"); bad += 1
    if not ro["bypass"] and stray_new:
        print("    🔴 段落顺序被打乱（压缩把参考段搬家了）"); bad += 1
    # ⑦ 性能：两条 —— ① **绝对**（满窗口压缩 < 2s）② **复杂度形状**（块数 ×4，耗时涨幅须 < 8 倍）
    #    ② 才是根因判据：旧 `_collapse_json` 逐块 `str.replace` 是 O(块数 × 全文)，
    #    块数 ×4 耗时该涨 ~16 倍。只钉绝对秒数会随机器快慢飘，钉**形状**才钉得住。
    perf_src = "\n".join("第%04d行：参考叙述占位文字 %s" % (i, '{"k":"' + 'v' * 60 + '"}')
                         for i in range(400))
    t0 = time.time()
    rp = compress(perf_src)
    cost_s = time.time() - t0
    print(f"  [性能] {len(perf_src)} 字压缩 {cost_s:.3f}s · ratio={rp['ratio']}")
    if cost_s > 2.0:
        print(f"    🔴 满窗口压缩超过 2s（实际 {cost_s:.2f}s）——请求路径上等于挂住"); bad += 1

    def _blk(n: int) -> str:
        """n 个 JSON 块，**只有 4 种不同内容**（不重复就根本走不到 replace 那条路，
        那样量出来的"线性"是假读数 —— 踩过：第一版每块都不重复，量出两者都 1.3x）。"""
        return "\n".join('{"k":"%s","n":%d}' % ("v" * 60, i % 4) for i in range(n))

    def _cost(fn, n: int, reps: int = 3) -> float:
        """取 3 次里最快的一次（毫秒级测量取最好成绩才稳；取平均会被调度噪声带跑）。"""
        src = _blk(n)
        best = 9e9
        for _ in range(reps):
            _t = time.time()
            fn(src)
            best = min(best, time.time() - _t)
        return best

    n1, n4 = 300, 1200
    new1, new4 = _cost(_collapse_json, n1), _cost(_collapse_json, n4)
    old1, old4 = _cost(_collapse_json_legacy, n1), _cost(_collapse_json_legacy, n4)
    grow_new = (new4 / new1) if new1 > 0 else 0
    grow_old = (old4 / old1) if old1 > 0 else 0
    print(f"  [复杂度] 块数 ×4 耗时涨幅：新 {grow_new:.1f}x（{new1:.4f}→{new4:.4f}s） · "
          f"旧 {grow_old:.1f}x（{old1:.4f}→{old4:.4f}s）")
    # 线性应当 ≈4x。实测（2026-10-29 连跑 5 轮）：新稳定 3.7–4.2x，旧稳定 7.5–7.8x。
    # ⚠️ 旧实现**没有**跑出理论上的 16x —— 因为折叠会让文本一路变短，实际涨幅被压住了。
    #   所以这里**不吹"O(n²)"**，只钉两件可复现的事：新实现接近线性；旧实现明显更差。
    if grow_new >= 6:
        print(f"    🔴 新的 `_collapse_json` 不再接近线性（{grow_new:.1f}x，线性应 ≈4x）"); bad += 1
    if grow_old <= grow_new * 1.5:
        print(f"    🔴 这条判据分不出好坏（旧 {grow_old:.1f}x vs 新 {grow_new:.1f}x）"
              f" —— 语料没压到超线性区，量出来的结论不算数"); bad += 1
    # ⑧ **折叠契约**（不是"新旧输出一模一样"）：换实现可以改**位置**，不许改**折叠数**，
    #    也不许把「保留第一份」丢掉。旧实现把标记打在**最早出现的位置**、留下最后一份
    #    （`str.replace(b, …, 1)` 总是替换全文第一个）—— 折叠数对、位置反，这里如实报告。
    MARK = "[同上：结构相同的 JSON 块，已折叠]"
    _eq_blk = '{"k":"%s","n":0}' % ("v" * 60)
    _eq_src = "\n".join([_eq_blk] * 3) + "\n尾巴"
    _n_new, _c_new = _collapse_json(_eq_src)
    _n_old, _c_old = _collapse_json_legacy(_eq_src)

    def _keep_first(t: str) -> bool:
        return t.find(_eq_blk) != -1 and t.find(_eq_blk) < t.find(MARK)

    _kf_new, _kf_old = _keep_first(_n_new), _keep_first(_n_old)
    print(f"  [折叠契约] 折叠数 new/old = {_c_new}/{_c_old} · 保留第一份 new={_kf_new} old={_kf_old}")
    if _c_new != _c_old:
        print("    🔴 折叠数不一致 —— 换实现改了行为（性能优化不许顺手改语义）"); bad += 1
    if not _kf_new:
        print("    🔴 没保留第一份（去重保序的契约被破坏了）"); bad += 1
    if _kf_old:
        print("    （旧实现也保留第一份 ⇒ 两者等价，只是实现路径不同）")
    else:
        print("    （旧实现把标记打在最早出现的位置、留下的是最后一份 —— 旧 bug，"
              "新实现改成保留第一份；折叠数相同，信息量不减）")
    s = stats()
    print(f"  [账] 省字符 {s['chars_saved']} · 精确命中 {s['cache_hits_exact']} · "
          f"近似命中 {s['cache_hits_approx']} · 留档 {s['spill_files']}")
    print(f"\n自检结论：{'全过' if bad == 0 else f'🔴 失败 {bad} 项'}")
    return bad


def run_op(op: str = "stats", **params) -> dict:
    op = (op or "stats").lower()
    if op == "compress":
        return compress(**params)
    if op == "cache_get":
        return cache_get(**params)
    if op == "cache_put":
        return cache_put(**params)
    if op == "autosize":
        return autosize(**params)
    if op == "stats":
        return stats(**params)
    if op == "selftest":
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            nbad = selftest()
        return {"ok": nbad == 0, "failures": nbad, "report": buf.getvalue()}
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（compress/cache_get/cache_put/autosize/stats/selftest）"}
