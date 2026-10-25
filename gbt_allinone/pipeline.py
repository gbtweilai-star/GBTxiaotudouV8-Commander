"""GBT小土豆V8 · 唯一交付通道：镜像多维度空间 → 生产级（v2 精修版）。

立场（Owner 定调，2026-09-11）：
镜像多维度空间是生产最后的防线。任何产物必须经镜像空间精细后才能写入生产。
v2 升级（同日第十批后）：AI 框架在大模型配合下自主完成工作——
镜像空间从"过道"升级为"工坊"：LLM 在这里审查、打磨、复审，粗稿变精品才放行。

三阶段（全部留痕、可回放、可回滚）：
  Stage 1  多维度镜像（mirror）：产物进镜像空间；可选 LLM 质量维度；
           可选精修循环（refine_rounds>0）：LLM 审查→给出修改→镜像快照→复审，
           每轮快照带血缘链（refined_from），最多 N 轮，避免无限循环
  Stage 2  门禁审计（gate）：P0 机械维度（完整/归属/审计/策略——恒开、毫秒级、确定性）
           + P1 质量维度（review=True 时 LLM 按评分卡打分，阈值 97）
           任一不过 → 阻断进隔离区，如实报原因
  Stage 3  版本化生产（publish）：过闸后原子写入生产区（当前版），
           同时归档历史版本（.versions/<name>/vN），护照带版本号与血缘，
           支持回滚（rollback）。

向后兼容：submit(name, content, meta) 行为与 v1 完全一致（默认无 LLM、无精修）。
"""
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_STORE = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
_PIPE = _STORE / "pipeline"
_MIRROR = _PIPE / "mirror"
_GATE = _PIPE / "gate"
_QUARANTINE = _PIPE / "quarantine"
_PROD = _PIPE / "production"
_VERSIONS = _PROD / ".versions"
_RECORDS = _PIPE / "records"

# P0 机械维度：恒开（确定性、毫秒级）
REQUIRED_DIMENSIONS = ["integrity", "ownership", "audit"]
# P1 质量维度：review=True 时开启（LLM 按评分卡打分）
# 及格线（Owner 2026-09-19）：**作品必须 ≥97 才算合格**（此前为 60）。
# ⚠️ 只把数字从 60 抬到 97 是空门：模型没有评分卡时会挤在 80-95，97 要么永远不过、
# 要么被模型学会"逢考必报 97"。所以同刀加评分卡，并且**总分由我们按维度加权算出来**，
# 不采信模型自报的总分 —— 少一类可被话术带跑的数。
QUALITY_THRESHOLD = 97

# 评分卡：维度 → (权重, 说明)。总分 = Σ(维度分×权重) ÷ Σ权重，保留 1 位小数；各维度 0-100。
QUALITY_RUBRIC = (
    ("clarity",      1.0, "表达是否清楚、无歧义、读完不用猜"),
    ("correctness",  1.5, "事实/逻辑/数据是否正确，有没有硬错"),
    ("completeness", 1.2, "声明用途要求的内容是否齐全，没缺件"),
    ("craft",        1.2, "细节打磨程度：结构、节奏、格式、可读性"),
    ("originality",  0.8, "是否有自己的东西，不是套模板凑字"),
    ("safety",       1.3, "署名/归属/隐私/授权边界是否合规"),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _score_of(v) -> float:
    """总分 = 按评分卡对维度分加权（**不采信模型自报的总分**）。

    拿不到维度分时退回旧的 `score` 字段，保证老调用方不炸；两者都没有 → 0（判不过）。
    """
    if not isinstance(v, dict):
        return 0.0
    dims = v.get("dims")
    if isinstance(dims, dict) and dims:
        num = den = 0.0
        for k, w, _d in QUALITY_RUBRIC:
            den += w
            try:
                num += float(dims.get(k) or 0) * w
            except (TypeError, ValueError):
                pass
        return round(num / den, 1) if den else 0.0
    try:
        return float(v.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _dims_brief(v) -> str:
    """维度分明细（进审计令牌）——让"97 分"看得见是哪几维撑起来的，可复核。"""
    if not isinstance(v, dict) or not isinstance(v.get("dims"), dict):
        return "-"
    return ",".join(f"{k}:{v['dims'].get(k)}" for k, _w, _d in QUALITY_RUBRIC)


def _ensure():
    for d in (_MIRROR, _GATE, _QUARANTINE, _PROD, _VERSIONS, _RECORDS):
        d.mkdir(parents=True, exist_ok=True)


def _audit_token(dim: str, item: str, passed: bool, detail: str) -> dict:
    return {"dimension": dim, "item": item, "passed": passed, "detail": detail,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}


def _dimensions(name: str, payload: bytes, meta: dict) -> list:
    """P0 机械维度体检（与 v1 一致 + 确定性）。"""
    from .soul import STAMP
    toks = []
    # 1) 完整性：内容非空
    toks.append(_audit_token("integrity", name, len(payload) > 0,
                            f"{len(payload)} bytes"))
    # 2) 归属：必须能盖上 GBT 钢印（独立归属）
    stamp_ok = STAMP.get("mark") == "GBT" and STAMP.get("ownership") == "independent-personal"
    toks.append(_audit_token("ownership", name, stamp_ok,
                            "GBT 钢印可用" if stamp_ok else "钢印缺失"))
    # 3) 审计：必须有提交人/用途记录
    ok = bool(meta.get("actor")) and bool(meta.get("purpose"))
    toks.append(_audit_token("audit", name, ok,
                            f"actor={meta.get('actor')}, purpose={meta.get('purpose')}"))
    # 4) 策略：非攻击类（高风险标签阻断）
    risky = [t for t in (meta.get("tags") or []) if str(t).lower() in
             ("malware", "exploit", "phishing", "credential", "keylogger")]
    toks.append(_audit_token("policy", name, not risky,
                            "无高风险标签" if not risky else f"高风险标签: {risky}"))
    return toks


# ═══════════════════════════════════════════════════════════
#  P1 质量维度：LLM 审查与精修（镜像空间的工坊层）
# ═══════════════════════════════════════════════════════════

def _llm_call(prompt: str, max_tokens: int = 800) -> dict:
    """LLM 调用（双引擎容灾：DeepSeek 桥优先，空回复自动切 abliteration）。

    绝不伪造评审：两个引擎都不可用时如实报错。
    """
    # 引擎 1：统一大模型口（Owner 2026-09-19：全部统一大模型；模块不再直连 bridge）
    try:
        from .llm import unified as LLM
        r = LLM.ask(prompt, max_tokens=max_tokens, timeout=90, purpose="pipeline.review")
        if r.get("ok") and str(r.get("reply", "")).strip():
            return {"ok": True, "text": r["reply"], "engine": "deepseek"}
    except Exception:  # noqa: BLE001
        pass
    # 引擎 2：黑客大脑独立通道（abliteration 独立大模型+独立密钥；容灾兼无限制分析）
    try:
        from .security import abl_gateway as AG
        if AG.configured():
            r2 = AG.chat(prompt, max_tokens=max(2000, max_tokens), timeout=180)
            if r2.get("ok") and str(r2.get("reply", "")).strip():
                return {"ok": True, "text": r2["reply"], "engine": "abliteration"}
            if r2.get("reasoning_only"):
                # 推理模型预算耗在思维链——从 reasoning 提取评审 JSON
                # 纪律：必须验证 score 是数字（模板回显 {"score": N} 不算真实评审）
                import re as _re
                for m in _re.finditer(r'\{[^{}]*"score"[^{}]*\}', str(r2.get("reasoning", ""))):
                    frag = m.group(0)
                    if _re.search(r'"score"\s*:\s*\d+', frag):
                        return {"ok": True, "text": frag, "engine": "abliteration-reasoning"}
    except Exception:  # noqa: BLE001
        pass
    return {"ok": False, "error": "双引擎均不可用（DeepSeek 空回复 + abliteration 失败）"}


def _llm_review(name: str, content: str, meta: dict) -> dict:
    """LLM 质量评审：按声明用途打分。返回 quality 令牌。"""
    purpose = str(meta.get("purpose", "未声明"))
    prompt = (f"你是生产门禁的质量评审员。产物名: {name}\n"
              f"声明用途: {purpose}\n"
              f"产物内容（节选前1200字）:\n{content[:1200]}\n\n"
              f"按评分卡逐维度打分（每项 0-100 整数，宁可低不要虚高）：\n"
              + "".join(f'  - {k}：{d}\n' for k, _w, d in QUALITY_RUBRIC)
              + f"及格线 {QUALITY_THRESHOLD}/100（加权总分由系统按维度算，不要自己编总分）。\n"
              f"严格输出 JSON（不要多余文字）: "
              f'{{"dims": {{{", ".join(chr(34) + k + chr(34) + ": <0-100整数>" for k, _w, _d in QUALITY_RUBRIC)}}}, '
              f'"verdict": "<pass|fail>", "issues": ["<问题1>", "<问题2>"]}}')
    r = _llm_call(prompt, max_tokens=600)
    if not r.get("ok"):
        # LLM 评审失败：如实标注质量维度不可用，不让门禁静默通过
        return _audit_token("quality", name, False,
                            f"LLM 评审不可用: {r.get('error', '?')}")
    text = r["text"]
    # 预净化：中文引号/尾逗号先修（中文引号会破坏字符串边界识别，导致扫描失衡）
    text = (text.replace(chr(0x201C), '"').replace(chr(0x201D), '"')
                .replace(chr(0x2018), "'").replace(chr(0x2019), "'"))
    # JSON 提取：平衡花括号扫描（字符串内的 {} 不影响计数，比正则稳）
    js = None
    depth, start = 0, -1
    in_str, esc = False, False
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    js = text[start:i + 1]
                    break
    if js is None:
        # 截断救活：LLM 输出被 max_tokens 切断时，尝试补闭合（score/verdict 通常已在前部）
        import re as _re3
        ms = _re3.search(r'"score"\s*:\s*(\d+)', text)
        mv = _re3.search(r'"verdict"\s*:\s*"(pass|fail)"', text)
        if ms and mv:
            score = int(ms.group(1))
            verdict = mv.group(1)
            passed_rc = score >= QUALITY_THRESHOLD  # 截断恢复：以分数为准
            return _audit_token("quality", name, passed_rc,
                                f"score={score}/100 (截断恢复), verdict={verdict}")
        else:
            return _audit_token("quality", name, False,
                                f"LLM 评审输出无 JSON（含截断恢复尝试）: {text[:60]}")
    try:
        v = json.loads(js)
    except Exception:
        # 净化重试：修正常见非法形态（中文引号/尾逗号/单引号键）
        fixed = (js.replace(chr(0x201C), '"').replace(chr(0x201D), '"')
                   .replace(chr(0x2018), "'").replace(chr(0x2019), "'"))
        import re as _re2
        fixed = _re2.sub(r',\s*([}\]])', r'\1', fixed)  # 尾逗号
        try:
            v = json.loads(fixed)
        except Exception as ex2:  # noqa: BLE001
            return _audit_token("quality", name, False,
                                f"评审 JSON 解析失败（含净化重试）: {ex2} | 原文: {js[:80]}")
    try:
        score = _score_of(v)
    except (TypeError, ValueError):
        score = 0
    score_ok = score >= QUALITY_THRESHOLD
    verdict_ok = str(v.get("verdict")) == "pass"
    if score_ok != verdict_ok:
        return _audit_token("quality", name, score_ok,
                            f"score={score}/100, verdict={v.get('verdict')}"
                            f"（分数与判定分歧，以分数为准）, issues={str(v.get('issues', ''))[:100]}")
    passed = score_ok and verdict_ok
    detail = (f"score={score}/100 (线 {QUALITY_THRESHOLD}), dims={_dims_brief(v)}, "
              f"issues={str(v.get('issues', ''))[:120]}")
    return _audit_token("quality", name, passed, detail)


def _llm_refine(name: str, content: str, meta: dict, issues: list) -> dict:
    """LLM 精修：按问题清单改进内容。返回 {"ok", "content"}。"""
    purpose = str(meta.get("purpose", ""))
    prompt = (f"你是镜像空间的精修工。产物名: {name}\n用途: {purpose}\n"
              f"评审发现的问题: {issues[:5]}\n"
              f"硬性要求：全文控制在 900 字内，结构必须覆盖用途声明的全部要素。\n"
              f"当前内容:\n{content[:2500]}\n\n"
              f"直接输出改进后的完整内容（不要解释、不要前后缀）:")
    r = _llm_call(prompt, max_tokens=1500)
    if r.get("ok"):
        return {"ok": True, "content": r["text"].strip()}
    return {"ok": False, "error": r.get("error")}


def _next_version(name: str) -> int:
    """读取产物当前版本号（无历史=1）。"""
    vdir = _VERSIONS / name
    if not vdir.exists():
        return 1
    existing = [f.stem for f in vdir.glob("v*.*") if f.stem[0] == "v"]
    nums = []
    for s in existing:
        try:
            nums.append(int(s[1:].split(".")[0]))
        except ValueError:
            continue
    return (max(nums) + 1) if nums else 1


def submit(name: str, content, meta=None, review: bool = False,
           refine_rounds: int = 0) -> dict:
    """提交产物，跑完整三阶段流水线（v2：可选 LLM 质量门禁与镜像精修）。

    content: str | bytes
    review: True 时开启 P1 质量维度（LLM 评分，阈值 60）
    refine_rounds: >0 时，质量不达标的产物在镜像空间经 LLM 精修后复审，
                   最多 N 轮（每轮快照留痕）；精修后仍不达标则如实阻断
    返回发布记录（status: published | blocked）。
    """
    _ensure()
    meta = meta or {}
    payload = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    ts0 = time.strftime("%Y-%m-%dT%H:%M:%S")
    digest = _sha256(payload)
    rec_id = f"{name}-{digest[:8]}-{int(time.time())}"
    lineage = []

    # ── Stage 1: 多维度镜像（含可选精修循环） ──
    mirror_path = _MIRROR / f"{rec_id}.bin"
    mirror_path.write_bytes(payload)

    current_text = payload.decode("utf-8", errors="replace")
    current_digest = digest

    if refine_rounds > 0:
        for rd in range(1, max(1, refine_rounds) + 1):
            qt = _llm_review(name, current_text, meta)
            if qt["passed"]:
                break  # 质量已达标，精修结束
            issues = []
            try:
                issues = json.loads(qq_detail := qt["detail"].split("issues=", 1)[1])
            except Exception:  # noqa: BLE001
                issues = ["质量评分未达标"]
            ref = _llm_refine(name, current_text, meta, issues)
            if not ref.get("ok"):
                lineage.append({"round": rd, "refine": "failed",
                                "error": str(ref.get("error"))[:120]})
                break
            new_text = ref["content"]
            # 精修快照落镜像（血缘链）
            snap = _MIRROR / f"{rec_id}.r{rd}.bin"
            snap.write_bytes(new_text.encode("utf-8"))
            lineage.append({"round": rd, "refine": "ok",
                            "snapshot": snap.name,
                            "sha256_before": _sha256(current_text.encode())[:12],
                            "sha256_after": _sha256(new_text.encode())[:12]})
            current_text = new_text
            current_digest = _sha256(new_text.encode("utf-8"))

    payload = current_text.encode("utf-8")

    # 维度体检：P0 机械 + 可选 P1 质量
    dimensions = _dimensions(name, payload, meta)
    if review:
        dimensions.append(_llm_review(name, current_text, meta))

    # ── Stage 2: 门禁审计 ──
    failed = [t for t in dimensions if t["dimension"] in REQUIRED_DIMENSIONS and not t["passed"]]
    failed += [t for t in dimensions if t["dimension"] == "policy" and not t["passed"]]
    failed += [t for t in dimensions if t["dimension"] == "quality" and not t["passed"]]
    gate_passed = len(failed) == 0
    gate_report = {"rec_id": rec_id, "passed": gate_passed, "tokens": dimensions,
                   "blocked_by": [t["dimension"] for t in failed]}
    (_GATE / f"{rec_id}.json").write_text(json.dumps(gate_report, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    record = {
        "rec_id": rec_id, "name": name, "sha256": current_digest, "size": len(payload),
        "submitted_at": ts0, "meta": meta,
        "stage1_mirror": {"path": str(mirror_path), "dimensions": dimensions,
                          "refine_lineage": lineage},
        "stage2_gate": gate_report,
    }

    if not gate_passed:
        q = _QUARANTINE / f"{rec_id}.bin"
        shutil.copy2(mirror_path, q)
        record["stage3_publish"] = {"status": "blocked", "quarantine": str(q),
                                    "reason": f"门禁未过: {gate_report['blocked_by']}"}
        record["status"] = "blocked"
    else:
        # ── Stage 3: 版本化生产写入（原子 + 护照 + 钢印 + 历史） ──
        from .soul import STAMP
        version = _next_version(name)
        prod_path = _PROD / name
        prod_path.parent.mkdir(parents=True, exist_ok=True)
        # 历史归档（先备份旧版再写新版）
        if prod_path.exists():
            vdir = _VERSIONS / name
            vdir.mkdir(parents=True, exist_ok=True)
            ext = prod_path.suffix or ".bin"
            hist = vdir / f"v{version - 1}{ext}" if version > 1 else vdir / f"v1{ext}"
            if not hist.exists():
                shutil.copy2(prod_path, hist)
        passport = {
            "gbt_stamp": dict(STAMP),
            "publish": {"rec_id": rec_id, "sha256": current_digest,
                        "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "actor": meta.get("actor"), "purpose": meta.get("purpose"),
                        "version": version,
                        "refined_rounds": len(lineage)},
        }
        # 每一页署名（开发者：自由的风）——文本/网页产物发布时自动携带，禁止删除
        if prod_path.suffix.lower() in (".md", ".html", ".htm", ".txt", ".csv"):
            try:
                from . import signature as _sig
                _txt = payload.decode("utf-8")
                _new = _sig.inject(_txt, prod_path)
                if _new != _txt:
                    payload = _new.encode("utf-8")
            except Exception:
                pass
        tmp = prod_path.with_suffix(prod_path.suffix + ".tmp")
        tmp.write_bytes(payload)
        os.replace(tmp, prod_path)  # 原子落盘
        (prod_path.parent / (prod_path.name + ".passport.json")).write_text(
            json.dumps(passport, ensure_ascii=False, indent=2), encoding="utf-8")
        record["stage3_publish"] = {"status": "published", "production": str(prod_path),
                                    "version": version, "passport": passport}
        record["status"] = "published"

    (_RECORDS / f"{rec_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    if "status" not in record:
        # 未走 stage3 发布分支时补齐顶层状态：发布过 → published，否则视为被门禁拦下
        stage3 = record.get("stage3_publish") or {}
        record["status"] = stage3.get("status") or "blocked"
    try:
        from .store import audit
        audit("pipeline_" + record["status"], {"rec_id": rec_id, "name": name,
                                               "sha256": current_digest[:12],
                                               "refined": len(lineage),
                                               # 观察者足迹标记（2026-09-19）：护栏自检故意提交一次
                                               # 会被门禁拦下的产物，那是**负对照**，不是现行故障。
                                               # 不标记 → selfscan 下一枪会把它读成 runtime fault（假 P0/P1）。
                                               "probe": bool(meta.get("probe"))})
    except Exception:
        pass
    return record


def list_records(limit=20) -> dict:
    _ensure()
    # 🔴 2026-09-22 第 41 轮修（错报治理 · 与 `agency_tentacles.catalog` 同一类）：
    #    原来 `"count": len(out)` 只是**这一页**的条数（`[:limit]` 之后），
    #    读的人问"流水线一共多少条记录"会拿到页大小。
    #    同仓的样板是 `tentacle/omni_fs.py:162` 的 `file_list`：**count + truncated 一起给**。
    #    ⇒ 补 `total`（目录里一共有几个）+ `truncated`，并保留 `count` 原义（本页条数）。
    _all = sorted(_RECORDS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = _all[:limit]
    out = []
    for f in files:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return {"records": out, "count": len(out), "total": len(_all),
            "limit": limit, "truncated": len(_all) > limit,
            "count_note": ("count=本页条数；total=记录总数；"
                           + ("**本次被 limit 截断**（还有 %d 条没列）" % (len(_all) - len(files))
                              if len(_all) > limit else "本次未截断（total 全部列出）"))}


def versions(name: str) -> dict:
    """产物的版本历史 + 当前版内容指纹。"""
    _ensure()
    prod = _PROD / name
    vdir = _VERSIONS / name
    history = []
    if vdir.exists():
        for f in sorted(vdir.glob("v*")):
            try:
                history.append({"version_file": f.name,
                                "sha256": _sha256(f.read_bytes())[:12],
                                "size": f.stat().st_size,
                                "archived_at": time.strftime(
                                    "%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime))})
            except OSError:
                continue
    current = None
    if prod.exists():
        current = {"sha256": _sha256(prod.read_bytes())[:12],
                   "size": prod.stat().st_size}
    return {"name": name, "current": current, "history": history,
            "count": len(history)}


def rollback(name: str, to_version: int = None) -> dict:
    """回滚生产产物到历史版本（回滚本身也走审计留痕）。

    to_version 缺省 = 最近一个历史版本。回滚 = 把历史内容作为新版本发布
    （不是删除历史——生产防线永远可追溯）。
    """
    _ensure()
    prod = _PROD / name
    vdir = _VERSIONS / name
    if not prod.exists():
        return {"ok": False, "error": f"生产区无此产物: {name}"}
    if not vdir.exists() or not list(vdir.glob("v*")):
        return {"ok": False, "error": f"无历史版本可回滚: {name}"}
    hist = sorted(vdir.glob("v*"), key=lambda p: p.stat().st_mtime)
    target = None
    if to_version is None:
        target = hist[-1]
    else:
        for f in hist:
            try:
                if int(f.stem[1:].split(".")[0]) == to_version:
                    target = f
                    break
            except ValueError:
                continue
    if target is None:
        return {"ok": False, "error": f"版本不存在: v{to_version}"}
    # 先把当前版归档（若未归档），再回滚
    cur_v = _next_version(name)
    cur_arch = vdir / f"v{cur_v}{prod.suffix or '.bin'}"
    if not cur_arch.exists():
        shutil.copy2(prod, cur_arch)
    payload = target.read_bytes()
    tmp = prod.with_suffix(prod.suffix + ".tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, prod)
    from .store import audit
    audit("pipeline_rollback", {"name": name, "to": target.name,
                                "sha256": _sha256(payload)[:12]})
    return {"ok": True, "name": name, "rolled_back_to": target.name,
            "new_current_sha256": _sha256(payload)[:12]}
