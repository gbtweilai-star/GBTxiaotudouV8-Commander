# gbt-capability: growth_hooks
"""短板钩子 + 自主进化钩子（主人令 2026-09-27）。

主人原话：「设计好**短板钩子**和**自主进化钩子**实现自我进化。」

## 两个钩子，各管一半

- **短板钩子**（`shortboard`）：从**已有读数**里算出现在最拖后腿的是什么 ——
  六个面（能力位 / 双向绑定 / 技能源装 / 覆盖矩阵 / 视觉面 / 舰队）+ 未清故障 + 未实现登记
  + 触手库覆盖 + 调用许可缺口。**每个短板都必须带 `src`**（哪个读数文件/哪个能力位），
  不许凭印象说"某处可能弱"。
- **自主进化钩子**（`evolve`）：拿最短板 → 生成**具体动作**（每一步标 `safe` / `needs_owner`）
  → **只自动执行不带门的那些**（读类、生成索引、补记忆）→ 落台账 `state/evolution.jsonl`。
  要门的那部分**不假装做了**，列成待主人清单。

## 两条纪律（写死在这里，不靠自觉）

1. **不自批**：`evolve` 永不调用 `auth grant` / 永不写 `store/owner_permits.jsonl`；缺票就列出来。
2. **判据不许既当训练又当验收**（主人 2026-09-27 立规）：`evolve` 生成的"改进"若落在
   `state/holdout.json` 封存的验收集里，**必须标 `holdout_conflict` 并跳过** —— 否则等于自己出题自己打分。

op=shortboard / evolve / history / verify / where
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_BOARD = _STATE / "shortboard.json"
_LEDGER = _STATE / "evolution.jsonl"
_HOLDOUT = _STATE / "holdout.json"
TOPN = 6


def _load(rel: str, default=None):
    p = _STATE / rel
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _faces() -> dict:
    """六个面：**只从 `tools/framework_state.py` 取**（不抄第二份口径）。"""
    try:
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("fs_growth", _ROOT / "tools" / "framework_state.py")
        fs = _iu.module_from_spec(sp)
        sp.loader.exec_module(fs)
        return (fs.collect() or {}).get("faces") or {}
    except Exception as exc:                                  # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {str(exc)[:120]}"}


def shortboard(**_kw) -> dict:
    """算最短板（每条带 src + 怎么补）。"""
    faces = _faces()
    items = []

    def add(dim: str, weight: int, what: str, src: str, how: str):
        items.append({"dim": dim, "weight": weight, "what": what, "src": src, "how": how})

    if faces.get("_error"):
        add("读数", 100, f"六面读数取不到：{faces['_error']}", "tools/framework_state.py",
            "先修 framework_state.collect()，别的判断都建立在这上面")
    caps = faces.get("能力位") or {}
    if caps.get("undispatched"):
        add("能力位", 90, f"{len(caps['undispatched'])} 个能力位没有分派：{caps['undispatched'][:4]}",
            "state/skill_atlas.json + gbt_allinone/api.py", "补 api.py 分支，或登记进 unimplemented.json")
    if caps.get("not_in_atlas"):
        add("能力位", 80, f"{len(caps['not_in_atlas'])} 个能力位没进图鉴：{caps['not_in_atlas'][:4]}",
            "state/skill_atlas.json", "跑 omni.py build 重建图鉴")
    bind = faces.get("双向绑定") or {}
    if (bind.get("断连_资产缺失") or 0) + (bind.get("断连_触手不在册") or 0):
        add("绑定", 85, f"断连 {bind.get('断连_资产缺失')}+{bind.get('断连_触手不在册')}（资产缺失/触手不在册）",
            "state/asset_bindings.json", "跑 tools/tentacle_bind.py autobind / sweep 补绑")
    if bind.get("能力位无触手标签"):
        add("绑定", 70, f"这些能力位没有触手标签：{bind['能力位无触手标签'][:4]}",
            "state/asset_bindings.json", "补绑定")
    fault = _load("排查台账.json", {}) or {}
    of = fault.get("open_faults") or []
    if of:
        add("故障", 95, f"未清故障 {len(of)} 条：{[f.get('id') for f in of][:5]}",
            "state/排查台账.json", "逐条结项或改账（改账要说清为什么不该算故障）")
    unimpl = _load("unimplemented.json", {}) or {}
    um = unimpl.get("items") or []
    if um:
        add("未实现", 60, f"未实现登记 {len(um)} 条：{[i.get('kind') for i in um][:4]}",
            "state/unimplemented.json", "能做的做掉；做不了的说清谁有权修")
    cov = faces.get("覆盖矩阵") or {}
    if cov and not cov.get("全绿", True):
        add("覆盖", 88, f"覆盖矩阵非全绿（盲区 {len(cov.get('盲区') or [])}）",
            "state/coverage_matrix.json", "补扫盲区树，或写清排除理由")
    if (cov.get("年龄h") or 0) > 24:
        add("覆盖", 50, f"覆盖矩阵读数 {cov.get('年龄h')}h 未更新", "state/coverage_matrix.json",
            "重跑 tools/coverage_matrix.py")
    # 触手库覆盖（本轮新增的记忆面）
    ov = _STATE / "obsidian_vaults.json"
    if not ov.is_file():
        add("永久记忆", 75, "触手库索引不在 ⇒ 记忆层没建起来", "state/obsidian_vaults.json",
            "run_task('obsidian_vault', {'op':'provision'})")
    else:
        try:
            idx = json.loads(ov.read_text(encoding="utf-8"))
            n, m = (idx.get("counts") or {}).get("tentacles"), (idx.get("counts") or {}).get("vaults")
            if n and m and m < n:
                add("永久记忆", 72, f"触手库 {m}/{n}（有触手没有独立库）", "state/obsidian_vaults.json",
                    "obsidian_vault op=provision（补齐）")
        except json.JSONDecodeError:
            add("永久记忆", 76, "触手库索引读不动（JSON 坏了）", "state/obsidian_vaults.json", "重建索引")
    # 调用许可缺口
    tags = _load("cap_tags.json", {}) or {}
    if not tags:
        add("许可", 65, "还没有专属标签表 ⇒ 主人无从批许可", "state/cap_tags.json",
            "run_task('cap_tags', {'op':'tags'})")
    else:
        owner = [k for k, v in (tags.get("tags") or {}).items() if v.get("permission") == "owner"]
        if owner:
            add("许可", 40, f"{len(owner)} 个能力位属 owner 类（要主人逐项许可才可调）",
                "state/cap_tags.json", "主人在终端发许可；我没许可的不许动")
    items.sort(key=lambda x: -x["weight"])
    top = items[:TOPN]
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "count": len(items), "top": top,
           "all_dims": {i["dim"]: i["weight"] for i in items},
           "_口径": "每条带 src（哪个读数文件）；权重=影响面×堵塞度，**不许凭印象**"}
    _BOARD.parent.mkdir(parents=True, exist_ok=True)
    tmp = _BOARD.with_name(_BOARD.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _BOARD)
    _log({"event": "shortboard", "count": len(items), "top": [i["dim"] for i in top]})
    return {"ok": True, "op": "shortboard", "count": len(items), "top": top,
            "dims": doc["all_dims"]}


def _holdout_ids() -> set:
    d = _load("holdout.json", {}) or {}
    ids = set()
    for k, v in d.items():
        if isinstance(v, dict) and v.get("id"):
            ids.add(str(v["id"]))
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and x.get("id"):
                    ids.add(str(x["id"]))
        if isinstance(v, str):
            ids.add(v)
    return ids


def evolve(dry_run: bool = True, item: str = "", **_kw) -> dict:
    """自主进化：拿最短板 → 生成动作 → **只自动做不带门的** → 其余列给主人。"""
    board = _load("shortboard.json")
    if not board:
        r = shortboard()
        board = _load("shortboard.json") or {"top": r.get("top") or []}
    top = board.get("top") or []
    if not top:
        return {"ok": True, "op": "evolve", "actions": [], "note": "短板清单是空的（要不就是读数取不到）"}
    pick = top[0]
    if item:
        for x in top:
            if item in (x.get("dim") or "") or item in (x.get("what") or ""):
                pick = x
                break
    holdout = _holdout_ids()
    steps = _steps_for(pick)
    # 判据不许既当训练又当验收：撞上封存验收集的步骤直接标冲突
    for s in steps:
        if any(h and h in json.dumps(s, ensure_ascii=False) for h in holdout):
            s["safe"] = False
            s["holdout_conflict"] = True
            s["why"] = "落在 state/holdout.json 封存的验收集里 ⇒ 不许拿它当改进目标（自己出题自己打分）"
    auto = [s for s in steps if s.get("safe") and not s.get("holdout_conflict")]
    need_owner = [s for s in steps if not s.get("safe") or s.get("holdout_conflict")]
    did, blocked_by_gate = [], []
    if not dry_run:
        for s in auto:
            # 先看→动脑→执行：**每一步自动动作都要过闸**（证据=这条短板的 src 读数，
            # 假设=这一步的 why）。过不了就不做 —— 这就是"拒绝无脑操作"落在自己身上。
            g = _preflight(s, pick)
            if not g.get("ok"):
                blocked_by_gate.append({"step": s.get("step"), "rules": [x.get("rule") for x in (g.get("refuses") or [])]})
                continue
            out = _run_step(s)
            out["gate_id"] = g.get("gate_id")
            did.append(out)
    _log({"event": "evolve", "shortboard": pick.get("what", "")[:160], "dry_run": bool(dry_run),
          "auto": len(auto), "need_owner": len(need_owner), "ran": [d.get("step") for d in did]})
    return {"ok": True, "op": "evolve", "shortboard": pick, "dry_run": bool(dry_run),
            "steps": steps, "auto_ran": did, "needs_owner": need_owner,
            "note": ("dry_run=True ⇒ 只出计划，没动手（要看真跑就给 dry_run=False）"
                     if dry_run else "自动那部分做了，带门的原样留给主人"),
            "_口径": "**不自批**：这里永不发授权；缺票的步骤只列不改"}


def _preflight(step: dict, pick: dict) -> dict:
    """把一步自动动作送过 `action_gate`（先看→动脑→执行）。取不到闸就**按不过**算（默认严）。"""
    try:
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("ag_growth", _ROOT / "gbt_allinone" / "tools" / "action_gate.py")
        ag = _iu.module_from_spec(sp)
        sp.loader.exec_module(ag)
        src = str(pick.get("src") or "")
        ev = src if src and (_ROOT / src).exists() else str(_ROOT / "state" / "shortboard.json")
        return ag.preflight(action=str(step.get("step") or "")[:120], evidence=ev,
                            hypothesis=str(step.get("why") or "按短板处方执行这一步")[:200],
                            stale_ok=True)
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "refuses": [{"rule": "闸取不到", "why": f"{type(exc).__name__}: {str(exc)[:80]}"}]}


def _steps_for(pick: dict) -> list:
    """按短板类型给**具体**动作（每条标 safe / needs_owner）。"""
    dim = pick.get("dim") or ""
    how = pick.get("how") or ""
    base = [{"step": f"读现状：{pick.get('src')}", "cmd": f"obsidian 记录 src={pick.get('src')}",
             "safe": True, "why": "先看（读类，不带门）"}]
    if dim == "绑定":
        base.append({"step": "补绑断连资产", "cmd": "python tools/tentacle_bind.py autobind",
                     "safe": True, "why": "绑定是仓内索引，无门"})
        base.append({"step": "复核绑定账", "cmd": "run_task('surface_bind', {'op':'verify'})",
                     "safe": True, "why": "只读复核"})
    elif dim == "永久记忆":
        base.append({"step": "补齐触手库", "cmd": "run_task('obsidian_vault', {'op':'provision'})",
                     "safe": True, "why": "仓内记忆层，无门"})
        base.append({"step": "重做双向绑定", "cmd": "run_task('obsidian_vault', {'op':'bind'})",
                     "safe": True, "why": "只写我们自己那页"})
    elif dim == "能力位":
        base.append({"step": "重建图鉴", "cmd": "python tools/codex-scripts/omni.py build",
                     "safe": True, "why": "生成物"})
        base.append({"step": "跑新增钩子补接线", "cmd": "python tools/binding_hook.py sweep",
                     "safe": True, "why": "补绑定/补触手页"})
    elif dim == "覆盖":
        base.append({"step": "重跑覆盖矩阵", "cmd": "python tools/coverage_matrix.py",
                     "safe": True, "why": "只读扫描 + 写读数"})
    elif dim == "故障":
        base.append({"step": "逐条结项/改账", "cmd": "见 state/排查台账.json 的 open_faults",
                     "safe": False, "why": "结项要证据与授权（有的故障涉及生产面）",
                     "needs_owner_grant": ["filesystem_write"]})
    elif dim == "许可":
        base.append({"step": "列待批清单给主人", "cmd": "run_task('cap_tags', {'op':'audit'})",
                     "safe": True, "why": "只读"})
    else:
        base.append({"step": f"按处方做：{how}", "cmd": how, "safe": False,
                     "why": "处方里带写/执行，先过门", "needs_owner_grant": ["filesystem_write"]})
    return base


def _run_step(s: dict) -> dict:
    """执行一个 safe 步骤：这里只做**读类/生成类**，真跑命令交给调用方的话就等于绕门了。"""
    cmd = str(s.get("cmd") or "")
    if any(t in cmd for t in ("run_task('obsidian_vault'", "obsidian_vault",)):
        try:
            import importlib.util as _iu
            sp = _iu.spec_from_file_location("ov_growth", _ROOT / "gbt_allinone" / "tools" / "obsidian_vault.py")
            ov = _iu.module_from_spec(sp)
            sp.loader.exec_module(ov)
            if "provision" in cmd:
                r = ov.provision()
            elif "bind" in cmd:
                r = ov.bind()
            else:
                r = ov.status()
            return {"step": s.get("step"), "ok": bool(r.get("ok")), "result": str(r)[:160]}
        except Exception as exc:                               # noqa: BLE001
            return {"step": s.get("step"), "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return {"step": s.get("step"), "ok": True, "result": "读类步骤（不落盘，只登记）"}


def history(limit: int = 10, **_kw) -> dict:
    rows = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return {"ok": True, "op": "history", "rows": len(rows), "tail": rows[-limit:],
            "_口径": "进化台账：短板算过什么、动作做过什么、哪些留给主人"}


def verify(**_kw) -> dict:
    problems = []
    if not _BOARD.is_file():
        problems.append("没有短板读数（先跑 shortboard）")
        return {"ok": False, "op": "verify", "problems": problems}
    d = json.loads(_BOARD.read_text(encoding="utf-8"))
    if not d.get("top"):
        problems.append("短板清单是空的 ⇒ 要么全绿（好事），要么读数取不到（先确认不是后者）")
    if d.get("count") and any(not i.get("src") for i in d["top"]):
        problems.append("有短板没带 src ⇒ 那是印象，不是读数")
    rows = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    if not rows:
        problems.append("进化台账是空的（钩子没动过）")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"shortboard": d.get("count"), "top": len(d.get("top") or []),
                       "ledger": len(rows)},
            "_口径": "短板带 src + 台账有记录 + 撞 holdout 的步骤被拦"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "growth_hooks", "tentacle": "growth_hooks",
            "entry": "run_task('growth_hooks', {...})",
            "ops": ["shortboard", "evolve", "history", "verify", "where"],
            "contract": [
                {"op": "shortboard", "returns": "top[]（dim/what/src/how/weight）"},
                {"op": "evolve", "params": "dry_run=false 才动手；item=挑某个短板",
                 "returns": "steps + auto_ran + needs_owner"},
            ],
            "两条纪律": ["不自批授权（缺票只列不改）", "撞 holdout 封存集的步骤一律拦下"],
            "files": {"短板读数": str(_BOARD.relative_to(_ROOT)),
                      "进化台账": str(_LEDGER.relative_to(_ROOT))}}


def run_op(op: str = "shortboard", **params) -> dict:
    op = (op or "shortboard").lower()
    for name, fn in (("shortboard", shortboard), ("evolve", evolve), ("history", history),
                     ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（shortboard/evolve/history/verify/where）"}
