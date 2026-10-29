# -*- coding: utf-8 -*-
# gbt-capability: heartbeat_tentacle
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""heartbeat_tentacle —— **每个分类一根心跳触手**，定点自检并把状态交回大脑执行层。

## 主人令（2026-10-30，逐字）

「把所有原生能力以及操控部位分类好**必须严格分类好**，然后**每一个分类部署一根心跳触手**
来对分类内的**一切**进行**定点自检**和**状态返回给大脑执行层分析**，再**返回执行指令**。」

## 这条链怎么落

```
cap_taxonomy(12 类)                       ← 分类真源（349 条精确覆盖，自校验）
        ↓ 每类一根
HeartbeatTentacle.pulse()                 ← 定点自检（五层，只读，零授权）
        ↓ status
state/heartbeat/tentacle-<类>.json        ← 落盘（可回看、可比对漂移）
        ↓ 汇总
brain_exec.heartbeat()                    ← 大脑执行层接收
        ↓ 分析
brain_exec.advise()                       ← 返回执行指令（带优先级/依据/证据）
```

## 六层定点自检（每层都只读，且必须能说清"查了什么、查到什么"）

| 层 | 查什么 | 判据 |
|---|---|---|
| ① 登记 | 该类的能力位是否都在真源里、条数是否与分类表一致 | 缺一条即红 |
| ② 分派 | 该类每条能力位的 handler 是否真在 `api.py` 分派表里 | 有漏即红（静态解析，不执行） |
| ③ 策略 | 该类每条能力位过 `policy.evaluate` 是否抛异常 | 抛异常即红 |
| ④ 探针 | 该类专属器官探针（身体/眼/引擎/模块面…） | 探针自身报红即红 |
| ⑤ 漂移 | 与上一次心跳比：成员进出、状态翻转 | 只报不判红（漂移是信息，不一定是错） |
| ⑥ 卫生 | 自己的抽屉里：垃圾 / 超额扫描件 / 外来混入 / 状态被写脏 | 混入与错位即红；垃圾与超额只报（默认 dry-run，`--clean` 才删） |

## 卫生层的三条纪律（主人令 2026-10-30 追加）

「分类触手在自检的时候要懂得清理垃圾和整理自身文件整洁，不被其他东西混入」

1. **只动自己的抽屉** —— 清理范围仅 `state/heartbeat/`，绝不伸到 outputs/ projects/ 或用户内容；
2. **外来物只报不删** —— 判定为"不是我们的东西"时**一律不动**，别人的东西不该由触手处置；
3. **默认 dry-run** —— 不显式 `--clean` 就只出清单。删除是写面，得有人明确要。

## 两档节奏（为什么需要）

实测（2026-10-30 本机）：`body_map` 6,488ms / `tentacle_status` 364ms / `wf_status` 20ms。
心跳图的是**频**，不能每次都跑 6.5 秒的全身扫描。

- `light`（默认）：只跑快探针（≤400ms 级）+ 四层静态检查
- `full`：加上 `body_map` 全身扫描（7 感官 6 动作逐根回读）

档位写进状态里，读数不会含糊。
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from . import cap_taxonomy as TX

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

_ROOT = Path(__file__).resolve().parent
_STATE_DIR = _ROOT.parent / "state" / "heartbeat"

# 探针成本分级（实测所得，不猜）
TIER_LIGHT = "light"
TIER_FULL = "full"

# ── 卫生层（主人令 2026-10-30 追加）──────────────────────────────────────
# 「分类触手在自检的时候要懂得清理垃圾和整理自身文件整洁，不被其他东西混入」
#
# 三条纪律，写死在常量里，不许临场放宽：
#   ① **只动自己的抽屉**：清理范围仅限 `state/heartbeat/`（本系统自己产的件），
#      绝不伸到 outputs/ projects/ 或任何用户内容。
#   ② **外来物只报不删**：判定为"不是我们的东西"时**一律不动** —— 别人的东西不该由触手处置。
#   ③ **默认 dry-run**：不显式要 `--clean` 就只出清单。删除属写面，得有人明确要。
KEEP_SCANS = 20          # scan-*.json 环形保留份数（再多就是垃圾）
_GARBAGE_SUFFIX = (".tmp", ".temp", ".pyc", ".pyo", ".orig", ".rej", ".swp", ".part")
_GARBAGE_NAMES = ("thumbs.db", ".ds_store", "desktop.ini")
_GARBAGE_DIRS = ("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
# 本目录里"合法属于我们"的三种件：汇总/清单/各触手自己那一格
_ALLOWED_EXACT = ("latest.json", "MANIFEST.json")
_ALLOWED_PREFIX = ("tentacle-", "scan-")

# 类 → 探针定义。kind: cap=调只读能力位 / modules=查模块面 / runtime=本机运行时 / policy=逐条过策略
PROBES: dict = {
    "身": {"kind": "cap", "name": "body_map", "tier": TIER_FULL,
           "note": "七根感官 + 六根动作逐根回读（全身扫描，慢但全）"},
    "感": {"kind": "eye", "tier": TIER_LIGHT,
           "note": "眼是否就绪（eye_ready / eye_error，进程内查，不抓帧所以不拖心跳）"},
    "知": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.brain.brain_council", "gbt_allinone.brain.cognition",
                       "gbt_allinone.brain.deep_reasoner", "gbt_allinone.brain.intent_broker"],
           "note": "认知四件（议会/认知/深推理/意图）是否在位"},
    "言": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.llm.key_gateway", "gbt_allinone.llm.cloud_llm",
                       "gbt_allinone.llm.ring_context", "gbt_allinone.llm.fact_gate"],
           "note": "模型四件（密钥网关/云模型/上下文环/事实闸）是否在位"},
    "造": {"kind": "cap", "name": "wf_status", "tier": TIER_LIGHT,
           "note": "创作引擎可用性"},
    "工": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.omni_plug", "gbt_allinone.tools", "gbt_allinone.engine"],
           "note": "万能插 + 工具包 + 引擎"},
    "察": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.recon", "gbt_allinone.tentacle.omni_domain",
                       "gbt_allinone.tentacle.bridge"],
           "note": "侦察面（域穿透 + 触手桥）"},
    "守": {"kind": "policy", "tier": TIER_LIGHT,
           "note": "安全域的每一条逐条过策略门，看规则是否还能判"},
    "调": {"kind": "runtime", "tier": TIER_LIGHT,
           "note": "Python 版本 / 磁盘余量 / 进程数 / 状态目录可写"},
    "数": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.store", "gbt_allinone.trace_store", "gbt_allinone.brain_vault"],
           "note": "数据仓 / 轨迹账 / 脑库（资产库无独立模块、内联在 api.py，故不进模块探针）"},
    "群": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.integration", "gbt_allinone.adapters"],
           "note": "集成面与适配器"},
    "进": {"kind": "modules", "tier": TIER_LIGHT,
           "targets": ["gbt_allinone.devour", "gbt_allinone.longrun", "gbt_allinone.life_archive"],
           "note": "吞噬 / 长跑 / 生命账"},
}


# ── 基础工具 ──────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _dispatch_kinds() -> set:
    """静态解析 api.py 的分派表（不执行任何能力），返回可分派的 kind 集合。

    三种写法都要认，漏一种就是假红：
      if kind == "x"        /  elif kind == "x"  /  if kind in ("a","b")
    """
    src_path = _ROOT / "api.py"
    try:
        src = src_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return set()
    kinds = set()
    kinds |= set(re.findall(r'kind == ["\']([A-Za-z0-9_]+)["\']', src))
    for m in re.finditer(r"if kind in \(([^)]*)\)", src):
        kinds |= set(re.findall(r'["\']([A-Za-z0-9_]+)["\']', m.group(1)))
    return kinds


def _module_exists(dotted: str) -> tuple:
    """查模块是否真的可解析（find_spec 不执行模块代码，无副作用）。"""
    try:
        spec = importlib.util.find_spec(dotted)
        return (spec is not None, "" if spec is not None else "find_spec 返回 None")
    except Exception as e:  # noqa: BLE001
        return (False, f"{type(e).__name__}: {str(e)[:80]}")


def _state_path(code: str) -> Path:
    return _STATE_DIR / f"tentacle-{code}.json"


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _write_json(p: Path, data: dict) -> bool:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return True
    except Exception:  # noqa: BLE001
        return False


# ── 触手本体 ──────────────────────────────────────────────────────────────


class HeartbeatTentacle:
    """一根心跳触手：只盯自己那一个分类，别的一概不管。"""

    def __init__(self, code: str):
        if code not in TX.CATEGORIES:
            raise ValueError(f"未知分类：{code}（可选：{'/'.join(TX.CATEGORIES)}）")
        self.code = code
        self.spec = TX.CATEGORIES[code]
        self.name = f"heartbeat-{code}"
        self.title = self.spec["title"]

    # ── 五层自检 ──

    def _check_registry(self, members: list) -> dict:
        """① 登记层：成员是否都在真源、条数是否对得上。"""
        from .caps_registry import BENIGN_CAPS

        missing = [m for m in members if m not in BENIGN_CAPS]
        # 反查：真源里属于本类的条数（不依赖缓存，现算）
        doms = set(self.spec["domains"])
        live = [n for n, meta in BENIGN_CAPS.items() if meta.get("domain") in doms]
        # 🔴 `and members` 会返回列表本身（真值不是 True）⇒ 必须显式 bool()。
        #    不修的话 ok 会是一个 29 元素的清单，判断上碰巧还对，但读数被污染成大串。
        ok = bool(not missing and len(live) == len(members) and members)
        return {
            "ok": ok,
            "count": len(members),
            "live_count": len(live),
            "missing": missing[:10],
            "detail": f"分类表 {len(members)} 条 / 真源现算 {len(live)} 条" + (
                f"，缺 {missing[:5]}" if missing else ""),
        }

    def _check_dispatch(self, members: list) -> dict:
        """② 分派层：每条能力位的 handler 是否真在分派表里。"""
        from .caps_registry import BENIGN_CAPS

        kinds = _dispatch_kinds()
        if not kinds:
            return {"ok": False, "detail": "分派表解析失败（api.py 读不到或格式变了）"}
        bad = []
        for m in members:
            h = (BENIGN_CAPS.get(m) or {}).get("handler")
            if not h or h not in kinds:
                bad.append((m, h))
        return {
            "ok": not bad,
            "total": len(members),
            "unrouted": len(bad),
            "sample": bad[:8],
            "detail": f"{len(members)-len(bad)}/{len(members)} 条 handler 在分派表内",
        }

    def _check_policy(self, members: list) -> dict:
        """③ 策略层：每条能力位过 policy.evaluate，不许抛。"""
        from .security import policy

        errs = []
        with_scope = 0
        for m in members:
            try:
                d = policy.evaluate(m, {})
                if list(d.scopes):
                    with_scope += 1
            except Exception as e:  # noqa: BLE001
                errs.append((m, f"{type(e).__name__}: {str(e)[:60]}"))
        return {
            "ok": not errs,
            "total": len(members),
            "with_scope": with_scope,
            "readonly": len(members) - with_scope,
            "errors": errs[:8],
            "detail": f"需过门 {with_scope} 条 / 零作用域 {len(members)-with_scope} 条"
                      + (f"，抛异常 {len(errs)}" if errs else ""),
        }

    def _probe(self, mode: str) -> dict:
        """④ 探针层：该类专属器官探针。"""
        p = PROBES.get(self.code) or {}
        if not p:
            return {"ok": None, "skipped": True, "detail": "本类未配探针"}

        tier = p.get("tier", TIER_LIGHT)
        if mode == TIER_LIGHT and tier == TIER_FULL:
            return {"ok": None, "skipped": True, "tier": tier,
                    "detail": f"高级探针（{p.get('name')}）在 light 档跳过；要全身扫描用 full"}

        kind = p.get("kind")
        t0 = time.time()

        if kind == "cap":
            from .api import run_task

            try:
                r = run_task(p["name"], {})
                body = (r or {}).get("gbt_result", {}) or {}
                status = body.get("status")
                res = body.get("result") or {}
                ok = status == "ok"
                detail = {"status": status}
                # 身体扫描要报"七根感官几根好、六根动作几根在"
                if p["name"] == "body_map":
                    senses = res.get("senses") or []
                    acts = res.get("actuators") or []
                    s_ok = sum(1 for s in senses if s.get("state") == "ok")
                    detail.update({
                        "senses": f"{s_ok}/{len(senses)}",
                        "actuators": len(acts),
                        "score": res.get("score"),
                        "bad_limbs": [s.get("limb") for s in senses if s.get("state") != "ok"],
                    })
                elif p["name"] == "tentacle_status":
                    diag = res.get("diagnose") or {}
                    ok = ok and bool(diag.get("ok", True))
                    detail.update({"eye_error": diag.get("eye_error")})
                elif p["name"] == "wf_status":
                    detail.update({"engine": res.get("status")})
                return {"ok": ok, "tier": tier, "probe": p["name"], "note": p.get("note"),
                        "detail": detail, "ms": round((time.time() - t0) * 1000)}

            except Exception as e:  # noqa: BLE001
                return {"ok": False, "tier": tier, "probe": p["name"],
                        "detail": f"探针调用失败：{type(e).__name__}: {str(e)[:100]}",
                        "ms": round((time.time() - t0) * 1000)}

        if kind == "modules":
            targets = p.get("targets") or []
            miss = []
            for t in targets:
                exists, why = _module_exists(t)
                if not exists:
                    miss.append({"module": t, "why": why})
            return {"ok": not miss, "tier": tier, "probe": "modules", "note": p.get("note"),
                    "detail": {"checked": len(targets), "missing": miss,
                               "present": [t for t in targets if t not in [x["module"] for x in miss]]},
                    "ms": round((time.time() - t0) * 1000)}

        if kind == "eye":
            # 进程内查眼，不抓帧、不截图 —— 心跳要的是"通不通"，不是"这一帧长什么样"
            try:
                from .tentacle import bridge as TB

                ready = bool(TB.eye_ready())
                err = "" if ready else str(TB.eye_error())[:120]
            except Exception as e:  # noqa: BLE001
                ready, err = False, f"{type(e).__name__}: {str(e)[:100]}"
            return {"ok": ready, "tier": tier, "probe": "eye_ready", "note": p.get("note"),
                    "detail": {"eye_ready": ready, "eye_error": err or None},
                    "ms": round((time.time() - t0) * 1000)}

        if kind == "policy":
            from .security import policy

            members = TX.members(self.code)
            errs = []
            for m in members:
                try:
                    policy.evaluate(m, {})
                except Exception as e:  # noqa: BLE001
                    errs.append(f"{m}: {type(e).__name__}")
            return {"ok": not errs, "tier": tier, "probe": "policy", "note": p.get("note"),
                    "detail": {"evaluated": len(members), "errors": errs[:8]},
                    "ms": round((time.time() - t0) * 1000)}

        if kind == "runtime":
            import shutil
            import platform

            try:
                du = shutil.disk_usage(str(_ROOT.parent))
                disk_free_gb = round(du.free / 1024 ** 3, 1)
            except Exception:  # noqa: BLE001
                disk_free_gb = None
            writable = os.access(str(_ROOT.parent / "state"), os.W_OK)
            ok = writable and (disk_free_gb is None or disk_free_gb > 1)
            return {"ok": ok, "tier": tier, "probe": "runtime", "note": p.get("note"),
                    "detail": {"py": platform.python_version(), "disk_free_gb": disk_free_gb,
                               "state_writable": writable},
                    "ms": round((time.time() - t0) * 1000)}

        return {"ok": None, "skipped": True, "detail": f"未知探针类型 {kind}"}

    def _hygiene(self, clean: bool) -> dict:
        """⑥ 卫生层：清理垃圾 / 整理自身 / 防外来混入（只在自己抽屉里动）。

        抽屉 = `state/heartbeat/`，12 根**共用一个抽屉**（各自一格）。于是定一条值日规矩：

        · **12 根都查、都清**（clean 幂等，先跑的清完后面的查到 0 条）—— 这是"每根都懂得清理"；
        · **但抽屉层面的问题只由值日的那根上报**（第一类「身」），否则同一个外来文件会被
          12 根各报一遍、12 根全红，读数就淹在重复里了。

        判据三类：

        | 类 | 判定 | 处置 |
        |---|---|---|
        | 垃圾 | `*.tmp/.pyc/.orig…`、`__pycache__`、`Thumbs.db` | 有 `clean` 才删，否则只列 |
        | 超额 | `scan-*.json` 超过 KEEP_SCANS 份（按 mtime 由新到旧保留） | 有 `clean` 才删最旧的 |
        | 混入 | 既不是我们那三种件、也不是垃圾 ⇒ **别人的东西** | **只报不删**（没资格处置） |

        另做「整理」：各触手 `tentacle-*.json` 的 `category` 必须与文件名一致 ——
        错位就是被别的进程写脏了，这条谁写脏谁负责，**不归值日**。

        判定：值日那根的 `ok` 含"外来混入"；其余各根只管自己那格是否错位。
        """
        keeper = (self.code == next(iter(TX.CATEGORIES)))
        d = _STATE_DIR
        res = {"ok": True, "dir": str(d), "clean_requested": bool(clean),
               "keeper": keeper,
               "garbage": [], "overflow": [], "foreign": [], "misplaced": [],
               "cleaned": [], "errors": []}
        if not d.exists():
            res["detail"] = "目录还没建（首跳会自建）"
            return res

        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name)
        except Exception as e:  # noqa: BLE001
            res["ok"] = False
            res["errors"].append(f"列目录失败：{type(e).__name__}: {str(e)[:80]}")
            return res

        scans = []
        for p in entries:
            name = p.name
            low = name.lower()

            # ① 垃圾目录（整个子树都是垃圾）
            if p.is_dir() and low in _GARBAGE_DIRS:
                res["garbage"].append(name + "/")
                if clean:
                    try:
                        import shutil as _sh
                        _sh.rmtree(p, ignore_errors=False)
                        res["cleaned"].append(name + "/")
                    except Exception as e:  # noqa: BLE001
                        res["errors"].append(f"{name}: {type(e).__name__}")
                continue

            # ② 垃圾文件
            if p.is_file() and (low in _GARBAGE_NAMES or low.endswith(_GARBAGE_SUFFIX)):
                res["garbage"].append(name)
                if clean:
                    try:
                        p.unlink()
                        res["cleaned"].append(name)
                    except Exception as e:  # noqa: BLE001
                        res["errors"].append(f"{name}: {type(e).__name__}")
                continue

            # ③ 合法件
            if p.is_file() and (name in _ALLOWED_EXACT or name.startswith(_ALLOWED_PREFIX)):
                if name.startswith("scan-") and name.endswith(".json"):
                    try:
                        scans.append((p.stat().st_mtime, p))
                    except Exception:  # noqa: BLE001
                        pass
                continue

            # ④ 剩下的都不是我们产的 ⇒ 外来混入，只报不删
            res["foreign"].append(name)

        # ⑤ 整理：文件数超额 → 环形保留最新 KEEP_SCANS 份
        scans.sort(reverse=True)
        if len(scans) > KEEP_SCANS:
            res["overflow"] = [p.name for _, p in scans[KEEP_SCANS:]]
            if clean:
                for _, p in scans[KEEP_SCANS:]:
                    try:
                        p.unlink()
                        res["cleaned"].append(p.name)
                    except Exception as e:  # noqa: BLE001
                        res["errors"].append(f"{p.name}: {type(e).__name__}")

        # ⑥ 整理：各触手那一格的 category 必须与文件名一致（错位=被写脏）
        for code in TX.CATEGORIES:
            fp = _state_path(code)
            if not fp.exists():
                continue
            data = _read_json(fp)
            if not data:
                res["misplaced"].append({"file": fp.name, "why": "内容不是合法 JSON"})
                continue
            cat = data.get("category")
            if cat and cat != code:
                res["misplaced"].append({"file": fp.name,
                                         "why": f"文件说 {code}，内容说 {cat}"})

        # ⑦ 写清单（"什么才算属于这里"的书面依据，免得下次又靠记忆判）
        if clean:
            manifest = {
                "at": _now(),
                "purpose": "12 根分类心跳触手的自有抽屉；除下列件外一律视为外来混入",
                "allowed_exact": list(_ALLOWED_EXACT),
                "allowed_prefix": list(_ALLOWED_PREFIX),
                "keep_scans": KEEP_SCANS,
                "tentacles": {c: f"tentacle-{c}.json" for c in TX.CATEGORIES},
            }
            _write_json(d / "MANIFEST.json", manifest)

        # ⑧ 读数口径：`garbage`/`overflow` 报**现存**（clean 后重算），`*_found` 报发现数。
        #    不这么分就会读出「已清 4 / 剩余垃圾 4」这种自相矛盾的账。
        res["garbage_found"] = len(res["garbage"])
        res["overflow_found"] = len(res["overflow"])
        if clean:
            res["garbage"] = [g for g in res["garbage"] if (d / g.rstrip("/")).exists()]
            res["overflow"] = [o for o in res["overflow"] if (d / o).exists()]

        # 判定：值日那根把「外来混入」也算红；其余各根只管自己那格错位。
        # 垃圾与超额是**常态**（跑多了自然有），有 clean 就清、没 clean 就列，从不判红。
        res["ok"] = (not res["misplaced"] and not res["errors"]
                     and not (res["foreign"] if keeper else []))
        res["detail"] = (f"发现垃圾 {res['garbage_found']} · 现存 {len(res['garbage'])} · "
                         f"超额发现 {res['overflow_found']} · 现存 {len(res['overflow'])} · "
                         f"外来 {len(res['foreign'])} · 错位 {len(res['misplaced'])}"
                         + (f" · 已清 {len(res['cleaned'])}" if clean else "（dry-run，未删）"))
        res["scans_kept"] = min(len(scans), KEEP_SCANS)
        return res

    def _drift(self, prev: dict, members: list, checks: dict) -> dict:
        """⑤ 漂移层：与上次心跳比。只报不判红。"""
        if not prev:
            return {"first_beat": True}
        out = {"first_beat": False}
        prev_members = set(prev.get("members_list") or [])
        now_members = set(members)
        added = sorted(now_members - prev_members)
        removed = sorted(prev_members - now_members)
        if added:
            out["members_added"] = added[:10]
        if removed:
            out["members_removed"] = removed[:10]
        prev_ok = (prev.get("checks") or {})
        flips = []
        for k in ("registry", "dispatch", "policy", "probe", "hygiene"):
            a = (prev_ok.get(k) or {}).get("ok")
            b = (checks.get(k) or {}).get("ok")
            if a is not None and b is not None and a != b:
                flips.append({"check": k, "was": a, "now": b})
        if flips:
            out["state_flips"] = flips
        out["prev_at"] = prev.get("at")
        out["prev_score"] = prev.get("score")
        return out

    # ── 一次心跳 ──

    def pulse(self, mode: str = TIER_LIGHT, persist: bool = True, clean: bool = False) -> dict:
        """打一次心跳：六层自检 → 返回状态（并落盘）。

        clean=False（默认）时卫生层只出清单不删；要真清得显式传 True。
        """
        t0 = time.time()
        members = TX.members(self.code)
        prev = _read_json(_state_path(self.code)) if persist else {}

        checks = {
            "registry": self._check_registry(members),
            "dispatch": self._check_dispatch(members),
            "policy": self._check_policy(members),
            "probe": self._probe(mode),
            "hygiene": self._hygiene(clean),
        }
        drift = self._drift(prev, members, checks)

        # 判定：probe 允许 skipped(None) 不算红；hygiene 的"垃圾/超额"是常态、不判红
        #      （它只在 foreign/misplaced 时自己 ok=False，那才是真卫生问题）
        judged = [c for k, c in checks.items() if k != "probe"]
        probe = checks["probe"]
        if probe.get("ok") is not None:
            judged.append(probe)
        ok_count = sum(1 for c in judged if c.get("ok"))
        score = round(ok_count / len(judged) * 100, 1) if judged else 0.0
        ok = ok_count == len(judged)

        signals = self._signals(checks, drift)

        status = {
            "tentacle": self.name,
            "category": self.code,
            "title": self.title,
            "at": _now(),
            "mode": mode,
            "beat": int(prev.get("beat") or 0) + 1,
            "ok": ok,
            "score": score,
            "checks": checks,
            "drift": drift,
            "signals": signals,
            "members_total": len(members),
            "members_list": members,
            "domains": self.spec["domains"],
            "action_domains": [d for d, c in TX.ACTION_DOMAIN_TO_CATEGORY.items() if c == self.code],
            "ms": round((time.time() - t0) * 1000),
        }

        if persist:
            _write_json(_state_path(self.code), status)
        return status

    def _signals(self, checks: dict, drift: dict) -> list:
        """把检查结果翻译成给大脑执行层看的信号（带级别与依据）。"""
        sig = []

        def add(level, code, msg):
            sig.append({"level": level, "code": code, "msg": msg})

        r = checks["registry"]
        if not r.get("ok"):
            add("P0", "registry_gap",
                f"{self.title} 登记不全：分类表 {r.get('count')} 条 vs 真源 {r.get('live_count')} 条"
                + (f"，缺 {r.get('missing')}" if r.get("missing") else ""))

        d = checks["dispatch"]
        if not d.get("ok"):
            if d.get("unrouted"):
                add("P0", "dispatch_gap",
                    f"{self.title} 有 {d.get('unrouted')} 条能力位 handler 不在分派表内：{d.get('sample')}")
            else:
                add("P0", "dispatch_unreadable", f"{self.title} 分派表解析失败：{d.get('detail')}")

        p = checks["policy"]
        if not p.get("ok"):
            add("P0", "policy_break",
                f"{self.title} 有 {len(p.get('errors') or [])} 条能力位过策略门时抛异常：{p.get('errors')}")

        pr = checks["probe"]
        if pr.get("ok") is False:
            add("P1", "probe_dead",
                f"{self.title} 器官探针报红（{pr.get('probe')}）：{pr.get('detail')}")
        elif pr.get("skipped"):
            add("INFO", "probe_skipped",
                f"{self.title} 探针在 {pr.get('tier', '?')} 档跳过：{pr.get('detail')}")

        if drift.get("members_added"):
            add("INFO", "members_added", f"{self.title} 新增成员：{drift['members_added']}")
        if drift.get("members_removed"):
            add("P1", "members_removed", f"{self.title} 成员消失：{drift['members_removed']}")
        if drift.get("state_flips"):
            add("P1", "state_flip", f"{self.title} 状态翻转：{drift['state_flips']}")

        # ── 卫生层信号（抽屉层面只由值日那根报，免得 12 根重复报同一条）──
        hy = checks.get("hygiene") or {}
        if hy.get("misplaced"):
            add("P1", "misplaced_state",
                f"{self.title} 状态文件被写脏（category 与文件名不符）：{hy['misplaced'][:4]}")
        if hy.get("keeper"):
            if hy.get("foreign"):
                add("P1", "foreign_intrusion",
                    f"心跳抽屉（值日：{self.title}）里有 {len(hy['foreign'])} 个不是我们产的件："
                    f"{hy['foreign'][:6]} —— **只报不删**（别人的东西不该由触手处置），要人来定去留")
            if hy.get("garbage") or hy.get("overflow"):
                if hy.get("cleaned"):
                    add("INFO", "garbage_cleaned",
                        f"心跳抽屉已清 {len(hy['cleaned'])} 个垃圾/超额件"
                        f"（保留最近 {KEEP_SCANS} 份扫描）")
                else:
                    add("P2", "garbage_found",
                        f"心跳抽屉有垃圾 {len(hy.get('garbage') or [])} 个 · 超额 {len(hy.get('overflow') or [])} 份"
                        f" —— 要清跑 `scan --clean`（默认 dry-run 不删）")
            if hy.get("errors"):
                add("P1", "hygiene_error",
                    f"心跳抽屉清理时出错：{hy['errors'][:4]}")

        return sig

    def status(self) -> dict:
        """只读上次心跳（不打新心跳）。"""
        s = _read_json(_state_path(self.code))
        if not s:
            return {"tentacle": self.name, "category": self.code,
                    "ok": None, "never_beaten": True,
                    "detail": "这根触手还没打过心跳（先跑 heartbeat scan）"}
        return s


# ── 十二根一起跳 ──────────────────────────────────────────────────────────


def scan_all(mode: str = TIER_LIGHT, persist: bool = True, clean: bool = False) -> dict:
    """12 根心跳触手各打一次，汇总成一份报告交给大脑执行层。

    clean=False（默认）卫生层只出清单；True 才真删（只删自己抽屉里的垃圾与超额扫描）。
    """
    t0 = time.time()
    statuses = {}
    for code in TX.CATEGORIES:
        try:
            statuses[code] = HeartbeatTentacle(code).pulse(mode=mode, persist=persist, clean=clean)
        except Exception as e:  # noqa: BLE001
            statuses[code] = {
                "tentacle": f"heartbeat-{code}", "category": code,
                "title": TX.CATEGORIES[code]["title"], "at": _now(),
                "mode": mode, "ok": False, "score": 0.0,
                "error": f"{type(e).__name__}: {str(e)[:160]}",
                "signals": [{"level": "P0", "code": "tentacle_crash",
                             "msg": f"触手自身崩了：{type(e).__name__}: {str(e)[:120]}"}],
                "checks": {}, "members_total": 0,
            }

    total = len(statuses)
    ok_n = sum(1 for s in statuses.values() if s.get("ok") is True)
    all_sig = []
    for s in statuses.values():
        for x in s.get("signals") or []:
            all_sig.append({**x, "category": s.get("category"), "tentacle": s.get("tentacle")})

    by_level = {}
    for x in all_sig:
        by_level[x["level"]] = by_level.get(x["level"], 0) + 1

    # 卫生汇总：抽屉层面的项只取值日那根（否则同一个外来文件会被 12 根各算一遍，
    # 报出 12 倍的假数）；错位是各根自己的事，全收。
    hyg = {"garbage": [], "overflow": [], "foreign": [], "misplaced": [],
           "cleaned": [], "errors": []}
    for s in statuses.values():
        h = (s.get("checks") or {}).get("hygiene") or {}
        if h.get("misplaced"):
            hyg["misplaced"].extend(h["misplaced"])
        if h.get("keeper"):
            for k in ("garbage", "overflow", "foreign", "cleaned", "errors"):
                if h.get(k):
                    hyg[k].extend(h[k])

    report = {
        "at": _now(),
        "mode": mode,
        "clean": bool(clean),
        "tentacles_total": total,
        "tentacles_ok": ok_n,
        "tentacles_red": total - ok_n,
        "score": round(ok_n / total * 100, 1) if total else 0.0,
        "taxonomy": TX.audit(),
        "statuses": statuses,
        "signals": all_sig,
        "signals_by_level": by_level,
        "hygiene": {k: (len(v) if isinstance(v, list) else v) for k, v in hyg.items()},
        "ms": round((time.time() - t0) * 1000),
    }

    if persist:
        _write_json(_STATE_DIR / "latest.json", report)
        _write_json(_STATE_DIR / f"scan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json", report)
    return report


def latest() -> dict:
    """读最近一次全量心跳报告。"""
    r = _read_json(_STATE_DIR / "latest.json")
    if not r:
        return {"ok": None, "never_scanned": True,
                "detail": "还没有全量心跳（先跑：python -m gbt_allinone heartbeat scan）"}
    return r


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(prog="heartbeat_tentacle", description="12 根分类心跳触手")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="12 根各打一次心跳并汇总")
    p_scan.add_argument("--mode", choices=[TIER_LIGHT, TIER_FULL], default=TIER_LIGHT)
    p_scan.add_argument("--no-persist", action="store_true")
    p_scan.add_argument("--clean", action="store_true",
                        help="真删自己抽屉里的垃圾与超额扫描（默认 dry-run 只出清单）")

    p_one = sub.add_parser("pulse", help="只打某一类")
    p_one.add_argument("category", help="分类代号：身/感/知/言/造/工/察/守/调/数/群/进")
    p_one.add_argument("--mode", choices=[TIER_LIGHT, TIER_FULL], default=TIER_LIGHT)
    p_one.add_argument("--clean", action="store_true")

    p_st = sub.add_parser("status", help="读上次心跳（不打新的）")
    p_st.add_argument("category", nargs="?", default="")

    sub.add_parser("taxonomy", help="打印 12 类分类总览与自校验结果")

    a = ap.parse_args()
    if a.cmd == "scan":
        print(json.dumps(scan_all(a.mode, not a.no_persist, clean=a.clean),
                         ensure_ascii=False, indent=1))
    elif a.cmd == "pulse":
        print(json.dumps(HeartbeatTentacle(a.category).pulse(a.mode, clean=a.clean),
                         ensure_ascii=False, indent=1))
    elif a.cmd == "status":
        if a.category:
            print(json.dumps(HeartbeatTentacle(a.category).status(), ensure_ascii=False, indent=1))
        else:
            print(json.dumps(latest(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(TX.describe(), ensure_ascii=False, indent=1))
