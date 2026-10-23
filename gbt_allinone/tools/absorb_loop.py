# gbt-capability: absorb_loop
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""吞天闭环（absorb_loop）· R-H258 只读骨架。

主人口径（2026-09-20）：**「吞天能力里面加入蒸馏提炼吸收自动跑通闭环，
避免留下垃圾导致吞噬失败」**。

⇒ 把「吞」拆成**三阶段 + 一回灌**，并且**每阶段结束必须清场**：

```
DISTILL 蒸馏  原始料 → 要点（去重 / 去噪 / 去掉不相关）
REFINE  提炼  要点 → 结构（可复用条目 / 模板 / 口径）
ABSORB  吸收  结构 → 落地（能力位 / 文档 / 口径）+ 登记
   ↺ 回灌：吸收的结论回喂蒸馏的过滤器 ⇒ 下次别再吞同类垃圾
```

🔴 为什么这条要紧（**取证，盘上有标本**）：
  · `gbt_allinone/devour.py` 的 `_v8_deploy` 每次覆盖都会留一个 `.deploy_bak`，
    而**全模块 grep 不到任何清理逻辑**（`清理|cleanup|清场` 0 命中）；
  · 实测：`gbt_allinone/store/devoured/`（**吞噬自己的产物目录**）26 个条目里，
    已经躺着 1 个 `gap_deploy/knowledge.json.deploy_bak`。
  ⇒ 「留下垃圾导致吞噬失败」不是假想 —— 产物目录自己就在攒垃圾。

四条机械闸（都带牙）：
  ① `check_stage_clean` 阶段之间**不许留垃圾**（`.tmp` / `.deploy_bak` / `.partial` …）
  ② `check_loop_closed` 三阶段必须齐 **且回灌一次** —— 少一段就不叫闭环
  ③ `check_scan_junk`  扫盘：垃圾必须**要么清掉、要么显式登记**，不许静默留
  ④ `check_resumable`  中断必须留**续跑点**（不留半成品卡住下一次）

五条红线（写死）：
  ① 吞完必须清场（阶段收尾扫垃圾，有则清或写理由）
  ② 闭环必须可续（中断留续跑点，不留半成品）
  ③ 每阶段留痕（trace_store，source_kind=absorb）
  ④ 不许吞未取证来源（没有出处的料，拒收 —— 与「未取证不引外部」同族）
  ⑤ 垃圾不许静默留（要么清、要么显式登记理由）

本骨架**只读**：不跑吞噬、不删任何文件、不写 store。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

CAP_KIND = "absorb_loop"
DOMAIN = "brain"
CAP_TYPE = "local"
TRACE_SOURCE_KIND = "absorb"

STAGES = (
    {"key": "DISTILL", "cn": "蒸馏", "in": "原始料", "out": "要点",
     "what": "去重 / 去噪 / 去掉不相关；不压缩掉出处"},
    {"key": "REFINE", "cn": "提炼", "in": "要点", "out": "结构",
     "what": "压成可复用条目 / 模板 / 口径；不替原话下结论"},
    {"key": "ABSORB", "cn": "吸收", "in": "结构", "out": "落地物",
     "what": "落成能力位 / 文档 / 口径并登记；吸收完必须清场"},
)
LOOP = {"key": "FED_BACK", "cn": "回灌",
        "what": "吸收的结论回喂蒸馏过滤器 ⇒ 下次别再吞同类垃圾（闭环的「闭」就在这一步）"}

# 垃圾后缀：吞的过程中最容易被留下的几类
JUNK_SUFFIXES = (".tmp", ".deploy_bak", ".partial", ".crdownload", ".swp")
# 默认扫描面：吞噬自己的产物与账本（**只看，不动**）
SCAN_ROOTS = ("gbt_allinone/store/devoured", "gbt_allinone/store")


def _hit_junk(name: str) -> Optional[str]:
    low = str(name).lower()
    for suf in JUNK_SUFFIXES:
        if low.endswith(suf):
            return suf
    return None


def scan_junk(root: Optional[Path] = None,
              roots: Optional[Sequence[str]] = None,
              limit: int = 5000) -> Dict[str, Any]:
    """只读扫盘：找残留垃圾。**不删任何东西。**"""
    from . import framework_gate as fg
    base = Path(root) if root else Path(fg.ROOT)
    rels = list(roots or SCAN_ROOTS)
    hits: List[Dict[str, str]] = []
    seen = set()
    scanned = 0
    for rel in rels:
        top = base / rel
        if not top.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
            for name in filenames:
                scanned += 1
                if scanned > limit:
                    break
                suf = _hit_junk(name)
                if suf:
                    p = Path(dirpath) / name
                    rel_p = str(p.relative_to(base)).replace("\\", "/")
                    if rel_p in seen:      # 扫描面互相嵌套（devoured 在 store 里）⇒ 去重
                        continue
                    seen.add(rel_p)
                    hits.append({"path": rel_p, "suffix": suf})
    return {"ok": True, "readonly": True, "scanned": scanned,
            "junk": hits, "count": len(hits), "roots": rels}


def check_stage_clean(stage: str, leftovers: Optional[Sequence[str]] = None) -> dict:
    """闸①：阶段之间**不许留垃圾**（下一个阶段不许在垃圾堆上开工）。"""
    st = str(stage or "").upper()
    known = [s["key"] for s in STAGES] + [LOOP["key"]]
    if st not in known:
        return {"ok": False, "denied": True, "rule": "unknown_stage",
                "stage": stage, "allowed": known}
    left = [str(x) for x in (leftovers or []) if str(x or "").strip()]
    dirty = [x for x in left if _hit_junk(os.path.basename(x))]
    if dirty:
        return {"ok": False, "denied": True, "rule": "stage_dirty",
                "stage": st, "junk": dirty[:5],
                "why": "阶段收尾没清场：把垃圾带进下一阶段 ⇒ 越吞越脏（红线①⑤）"}
    return {"ok": True, "readonly": True, "stage": st, "clean": True}


def check_loop_closed(stages_ran: Optional[Sequence[str]] = None,
                      fed_back: bool = False) -> dict:
    """闸②：三阶段必须齐 **且回灌一次** —— 少一段就不叫闭环。"""
    got = [str(s).upper() for s in (stages_ran or [])]
    need = [s["key"] for s in STAGES]
    missing = [k for k in need if k not in got]
    if missing:
        return {"ok": False, "denied": True, "rule": "loop_not_closed",
                "missing": missing, "ran": got,
                "why": "缺阶段 ⇒ 吞进来的东西停在中途（没吸收也没回灌）"}
    if not fed_back:
        return {"ok": False, "denied": True, "rule": "loop_not_closed",
                "missing": [LOOP["key"]], "ran": got,
                "why": "三阶段都跑了但**没回灌** ⇒ 是直线不是闭环：下次还会吞同类垃圾"}
    return {"ok": True, "readonly": True, "ran": got, "fed_back": True}


def check_scan_junk(paths: Optional[Sequence[str]] = None,
                    declared: Optional[Sequence[str]] = None) -> dict:
    """闸③：盘上的垃圾必须**要么清掉、要么显式登记理由**，不许静默留。"""
    ps = [str(p) for p in (paths or []) if str(p or "").strip()]
    dec = {str(d) for d in (declared or [])}
    junk = [p for p in ps if _hit_junk(os.path.basename(p))]
    silent = [p for p in junk if p not in dec]
    if silent:
        return {"ok": False, "denied": True, "rule": "junk_left_silently",
                "junk": silent[:5], "count": len(silent),
                "why": "有垃圾但既没清、也没登记理由 ⇒ 静默留（红线⑤）"}
    return {"ok": True, "readonly": True, "junk": len(junk),
            "declared": sorted(dec & set(junk))}


def check_resumable(state: Optional[Dict[str, Any]] = None) -> dict:
    """闸④：中断必须留**续跑点**（不留半成品卡住下一次）。"""
    st = dict(state or {})
    done = [str(s).upper() for s in (st.get("stages_done") or [])]
    all_stages = [s["key"] for s in STAGES]
    interrupted = st.get("interrupted")
    if interrupted or (done and len(done) < len(all_stages)):
        point = st.get("resume_from")
        if not point:
            return {"ok": False, "denied": True, "rule": "not_resumable",
                    "stages_done": done,
                    "why": "中断了却没留续跑点 ⇒ 下次只能从头吞（半成品还可能挡住重跑）"}
        if str(point).upper() not in all_stages:
            return {"ok": False, "denied": True, "rule": "bad_resume_point",
                    "resume_from": point, "allowed": all_stages}
        return {"ok": True, "readonly": True, "resume_from": str(point).upper()}
    return {"ok": True, "readonly": True, "resume_from": None}


def check_source_evidenced(source: Optional[str] = None) -> dict:
    """红线④：不许吞**未取证来源**（没有出处的料，拒收）。"""
    s = str(source or "").strip()
    if not s:
        return {"ok": False, "denied": True, "rule": "source_unspecified",
                "why": "没写来源 ⇒ 不许吞（吞进来的每一条都要能回到出处）"}
    if s.lower() in ("unknown", "无", "none", "n/a", "?"):
        return {"ok": False, "denied": True, "rule": "source_not_evidenced",
                "source": s,
                "why": "来源未取证 ⇒ 拒收（与「未取证不引外部」同族）"}
    return {"ok": True, "readonly": True, "source": s}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / stages / loop / junk / gates。

    🔴 2026-10-19 实测修的「通电不达」（主人令「通电秒达，没秒到就是那里不通」）：
       原来 `status` 里同步跑 `scan_junk()` —— 它会**走目录树**，实测一发 **2254 ms**；
       而同一批 337 根触手里其它发都是 12~43 ms，只有它超预算。
       status 是"电表读数"，不该每次都扫盘 ⇒ 默认只报配置（`scan=False`）；
       要看真实杂物就 `op=junk` 或显式 `{"scan": true}`（慢，但那是"真扫"）。
    """
    op = str(op or "status")
    if op == "status":
        fast = not bool(params.get("scan"))
        sc = None if fast else scan_junk(params.get("root"))
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "stages": [s["key"] for s in STAGES],
                "loop": LOOP["key"],
                "junk_now": (sc or {}).get("count"),
                "junk_sample": (sc or {}).get("junk", [])[:3],
                "scan_roots": (sc or {}).get("roots") or [],
                "scan_skipped": fast,
                "scan_hint": ("要看真实杂物就 cap absorb_loop {\"op\":\"junk\"}（会走目录树，较慢）"
                              if fast else ""),
                "evidence": "devour.py 无清理逻辑（grep 0 命中）；"
                            "devoured 产物目录实测已留 .deploy_bak",
                "red_lines": len(RED_LINES)}
    if op == "stages":
        return {"ok": True, "readonly": True,
                "stages": [dict(s) for s in STAGES], "loop": dict(LOOP)}
    if op == "junk":
        return scan_junk(params.get("root"))
    if op == "gate_stage":
        return check_stage_clean(params.get("stage"), params.get("leftovers"))
    if op == "gate_loop":
        return check_loop_closed(params.get("stages_ran"),
                                 bool(params.get("fed_back")))
    if op == "gate_junk":
        return check_scan_junk(params.get("paths"), params.get("declared"))
    if op == "gate_resume":
        return check_resumable(params.get("state"))
    if op == "gate_source":
        return check_source_evidenced(params.get("source"))
    raise ValueError("未知 op %r（可用：status/stages/junk/gate_stage/gate_loop/"
                     "gate_junk/gate_resume/gate_source）" % (op,))


RED_LINES = (
    "吞完必须清场：阶段收尾扫垃圾，有则清、或写明理由（不许带进下一阶段）",
    "闭环必须可续：中断留续跑点，不留半成品卡住下一次",
    "每阶段留痕：写 trace_store，source_kind=absorb",
    "不许吞未取证来源：没出处的料拒收（与「未取证不引外部」同族）",
    "垃圾不许静默留：要么清、要么显式登记理由（与坑册 §57 同族）",
)


HONEST_BOUNDARY = (
    "本骨架保证『三阶段 + 一回灌 + 四条闸 + 五条红线』可查、可判、可复算；"
    "它**保证不了**「吞噬引擎已经自动跑通闭环」——"
    "真接线要改 `devour.py`（目前 grep 不到任何清理逻辑），那是下一刀的事；"
    "本刀**只读**：不跑吞噬、不删任何文件、不写 store。"
)
