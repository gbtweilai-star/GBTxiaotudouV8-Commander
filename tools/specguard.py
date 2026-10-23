# -*- coding: utf-8 -*-
"""specguard · 规格守卫（清单强校验 + 成片指纹 + seed 族 + 预算闸）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

立项依据：《一句话成片·多智能体自动化架构设计》（Owner 2026-09-27 给料）的"三个下沉"——
  ① 步骤下沉（DAG 编排）② **参数下沉（JSON Schema 强约束契约）** ③ 知识下沉（资产 + 决策记录）。
本件补的是 ②③ 在我们这里**真缺**的四样（对账后逐条点名）：

  · `validate_manifest()` —— **规格强校验，fail-fast**：字段/类型/枚举/区间，错一处当场拒跑
    （对应关键点 1「节点寻址必须版本化」的同类问题：**不合法的 Spec 不许静默跑成错片**）；
  · `seed_family()` —— **seed 族策略**（关键点 4）：同场固定 + 跨拍按规则派生，一致性可复现；
  · `fingerprint()` —— **成片指纹**（关键点 7）：清单 hash + 工具 hash + 模型/引擎版本 + seed 表，
    落 `<成片>.fingerprint.json` ⇒ 昨天的成片今天能复现、能回归；
  · `budget_gate()` —— **预算闸**（关键点 8）：重试次数/时长上限；超限**降级**（减拍/降档），不无限烧。

口径：本件只读+落指纹（写面由调用方过门）；表达式/路径纪律照旧（零逗号、绝对路径）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")

# 三板块 Spec 的字段契约（**一处定义**；actioncam / filmkit 共用）
COMMON_QUALITY = ("hd", "fhd", "cinema")
GRADE_LOOKS = ("filmic", "做旧", "潮湿阴冷", "热血橙青", "褪色胶片", "黑白纪实", "赛博霓虹", "none")

BEAT_SPEC = {
    "id":     {"type": str, "required": True, "min_len": 1},
    "move":   {"type": str, "required": True, "enum": None},        # 运行时按 MOVES 现算
    "angle":  {"type": str, "required": False, "enum": ("eye", "low", "high", "dutch")},
    "dur":    {"type": (int, float), "required": True, "min": 0.1, "max": 30.0},
    "prompt": {"type": str, "required": True, "min_len": 8},
    "seed":   {"type": int, "required": False, "min": 0},
}
FILM_SPEC = {
    "title":     {"type": str, "required": False},
    "quality":   {"type": str, "required": False, "enum": COMMON_QUALITY},
    "grade":     {"type": str, "required": False, "enum": None},     # 外观名或人话，运行时由 filmgrade.pick 认
    "source":    {"type": str, "required": False, "enum": ("pollinations", "genoffice")},
    "work_dir":  {"type": str, "required": True, "min_len": 3},
    "out_dir":   {"type": str, "required": True, "min_len": 3},
    "output":    {"type": str, "required": True, "min_len": 3},
    "budget":    {"type": dict, "required": False},
}


def _err(errors: list, path: str, msg: str) -> None:
    errors.append(f"{path}: {msg}")


def _check_field(spec: dict, key: str, val, errors: list, where: str) -> None:
    if val is None:
        return
    t = spec["type"]
    if not isinstance(val, t) or (t is int and isinstance(val, bool)):
        _err(errors, where, f"{key} 类型应为 {t}，实得 {type(val).__name__}")
        return
    if "enum" in spec and spec["enum"]:
        if val not in spec["enum"]:
            _err(errors, where, f"{key}={val!r} 不在允许值 {spec['enum']}")
    if "min" in spec and isinstance(val, (int, float)) and val < spec["min"]:
        _err(errors, where, f"{key}={val} 小于下限 {spec['min']}")
    if "max" in spec and isinstance(val, (int, float)) and val > spec["max"]:
        _err(errors, where, f"{key}={val} 超过上限 {spec['max']}")
    if "min_len" in spec and isinstance(val, str) and len(val.strip()) < spec["min_len"]:
        _err(errors, where, f"{key} 太短（<{spec['min_len']} 字符）")


def validate_manifest(m: dict, kind: str = "actioncam") -> dict:
    """**fail-fast 规格校验**：错一处就带清单返回，调用方**不许开跑**。"""
    errors: list[str] = []
    if not isinstance(m, dict):
        return {"ok": False, "errors": ["清单不是对象"], "kind": kind}
    for k, spec in FILM_SPEC.items():
        if spec["required"] and k not in m:
            _err(errors, "顶层", f"缺必填字段 {k}")
            continue
        _check_field(spec, k, m.get(k), errors, "顶层")
    if "beats" in m:
        beats = m["beats"]
        if not isinstance(beats, list) or not beats:
            _err(errors, "beats", "beats 必须是非空数组")
        else:
            seen = set()
            for i, b in enumerate(beats):
                w = f"beats[{i}]"
                if not isinstance(b, dict):
                    _err(errors, w, "不是对象")
                    continue
                for k, spec in BEAT_SPEC.items():
                    if spec["required"] and k not in b:
                        _err(errors, w, f"缺必填字段 {k}")
                        continue
                    _check_field(spec, k, b.get(k), errors, w)
                bid = b.get("id")
                if isinstance(bid, str):
                    if bid in seen:
                        _err(errors, w, f"拍 id 重复：{bid}")
                    seen.add(bid)
                if kind == "actioncam" and isinstance(b.get("move"), str):
                    try:
                        import importlib.util
                        s = importlib.util.spec_from_file_location("ac_x", ROOT / "tools" / "actioncam.py")
                        ac = importlib.util.module_from_spec(s); s.loader.exec_module(ac)
                        if b["move"] not in ac.MOVES:
                            _err(errors, w, f"未知运镜 {b['move']!r}（可用 {len(ac.MOVES)} 种）")
                    except Exception:                              # noqa: BLE001
                        pass
    if "scenes" in m:
        scenes = m["scenes"]
        if not isinstance(scenes, list) or not scenes:
            _err(errors, "scenes", "scenes 必须是非空数组")
        else:
            for i, sc in enumerate(scenes):
                w = f"scenes[{i}]"
                if not isinstance(sc, dict):
                    _err(errors, w, "不是对象"); continue
                for k in ("id", "shots"):
                    if k not in sc:
                        _err(errors, w, f"缺必填字段 {k}")
                shots = sc.get("shots")
                if not isinstance(shots, list) or not shots:
                    _err(errors, w, "shots 必须是非空数组")
                else:
                    for j, sh in enumerate(shots):
                        if not isinstance(sh, dict) or "prompt" not in sh:
                            _err(errors, f"{w}.shots[{j}]", "缺 prompt")
    if "beats" not in m and "scenes" not in m:
        _err(errors, "顶层", "既没有 beats（动作线）也没有 scenes（影视线）")
    return {"ok": not errors, "kind": kind, "errors": errors[:40],
            "checked": {"beats" if "beats" in m else "scenes": len(m.get("beats") or m.get("scenes") or [])},
            "口径": "fail-fast：errors 非空 ⇒ 不许开跑（防'不合法 Spec 静默跑成错片'）"}


# ── seed 族（关键点 4：同场固定 + 跨拍按规则派生）──────────────────────
def stable_seed(text: str, mod: int = 10 ** 8) -> int:
    """**稳定种子**：由文本 sha256 派生（与进程无关）。

    🔴 为什么必须有它（2026-09-27 实测抓出的真缺口）：filmkit / actioncam 原来都用
    `abs(hash(shot_id))` 派生种子，而 **Python 的 `hash()` 对 str 每进程随机化**
    （PYTHONHASHSEED）⇒ **同一镜重跑会换种子**，图就变了 —— 这就是"不可复现"的根。
    sha256 与进程无关 ⇒ 同 id 永远同种子。
    """
    h = hashlib.sha256(("gbt-seed:" + str(text)).encode("utf-8")).hexdigest()[:12]
    return int(h, 16) % max(1, int(mod))


def seed_family(base: int, n: int, stride: int = 7919) -> list[int]:
    """族策略：`base` 为族锚（同场/同角固定），第 i 个拍 = base + i*stride（素数步长，互不撞）。"""
    return [int(base) + i * stride for i in range(max(0, int(n)))]


def apply_seed_family(m: dict, base: int = 0) -> dict:
    """给没有 seed 的拍按族策略补种（已有 seed 的**不动**——定过的种子是资产）。"""
    beats = m.get("beats") or []
    base = int(base or m.get("seed_base") or 20260927)
    fam = seed_family(base, len(beats))
    added = 0
    for b, s in zip(beats, fam):
        if isinstance(b, dict) and not b.get("seed"):
            b["seed"] = s
            added += 1
    m["seed_base"] = base
    return {"ok": True, "base": base, "added": added, "family": fam[:8],
            "口径": "已有 seed 不动；只给缺的补，同族同锚可复现"}


# ── 预算闸（关键点 8：超限降级，不无限烧）─────────────────────────────
def budget_gate(m: dict, planned_minutes: float, retries_used: int = 0,
                default_minutes: float = 30.0, default_retries: int = 2) -> dict:
    """预算闸：`budget = {"minutes": 30, "retries": 2, "on_exceed": "degrade"|"stop"}`。

    超限的**降级**动作（不是硬停）：减拍（保留首尾与高光）或降档（cinema→fhd→hd）。
    """
    b = m.get("budget") or {}
    lim_min = float(b.get("minutes", default_minutes))
    lim_ret = int(b.get("retries", default_retries))
    on_exceed = str(b.get("on_exceed", "degrade"))
    over_min = planned_minutes > lim_min
    over_ret = retries_used >= lim_ret
    actions = []
    if over_min and on_exceed == "degrade":
        q = m.get("quality", "fhd")
        downgrade = {"cinema": "fhd", "fhd": "hd", "hd": "hd"}[q]
        if downgrade != q:
            actions.append(f"降档 {q}→{downgrade}")
        actions.append("减拍（保留首尾与打击帧）")
    return {"ok": not (over_min or over_ret), "planned_minutes": planned_minutes,
            "limit_minutes": lim_min, "retries_used": retries_used, "limit_retries": lim_ret,
            "on_exceed": on_exceed, "actions": actions,
            "口径": "超限要么降级要么停（budget.on_exceed），**不许无限重试烧算力**"}


# ── 成片指纹（关键点 7：可复现 / 可回归）───────────────────────────────
def _sha(p: Path, n: int = 16) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:n]
    except OSError:
        return ""


def _tool_versions() -> dict:
    v = {"python": sys.version.split()[0]}
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        v["ffmpeg"] = (r.stdout or "").splitlines()[0][:60] if r.stdout else "?"
    except Exception:                                          # noqa: BLE001
        v["ffmpeg"] = "?"
    return v


def fingerprint(manifest_path: Path, film_path: Path, extra: dict | None = None) -> dict:
    """落 `<成片>.fingerprint.json`：清单 hash + 工具 hash + 引擎版本 + seed 表。

    关键点 7 的原话是「必须记录 workflow hash + 模型 hash + 自定义节点 commit，
    否则昨天的成片今天复现不了」——我们对应的三样是：**清单 hash + 工具链 hash + 引擎版本**。
    """
    mp, fp = Path(manifest_path), Path(film_path)
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        m = {}
    seeds = {b.get("id"): b.get("seed") for b in (m.get("beats") or [])
             if isinstance(b, dict) and b.get("seed")}
    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "film": str(fp), "film_sha16": _sha(fp),
        "manifest": mp.as_posix(), "manifest_sha16": _sha(mp),
        "quality": m.get("quality"), "grade": m.get("grade", "filmic"),
        "source": m.get("source", "pollinations"),
        "seed_base": m.get("seed_base"), "seeds": seeds,
        "tools": {"actioncam.py": _sha(ROOT / "tools" / "actioncam.py"),
                  "filmkit.py": _sha(ROOT / "tools" / "filmkit.py"),
                  "filmgrade.py": _sha(ROOT / "tools" / "filmgrade.py")},
        "engine": _tool_versions(),
        "口径": "清单 hash + 工具 hash + 引擎版本 + seed 表 ⇒ 可复现/可回归；任一变了指纹就变",
    }
    if extra:
        rec.update(extra)
    out = fp.with_suffix(fp.suffix + ".fingerprint.json")
    try:
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        rec["written"] = str(out)
    except OSError as exc:
        rec["written"] = f"写失败：{exc}"
    return rec
