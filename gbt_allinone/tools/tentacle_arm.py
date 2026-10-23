# gbt-capability: tentacle_arm
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""触手操控臂（tentacle_arm）—— 把 Omni-Arm 的**五层精度模型**套到我们自己的触手上。

主人令 2026-10-19（逐字）：「你要以这些能力的思路来操控触手，本身触手就是我们的手，
所以必须学会这样的操控精度。」

## 五层怎么落到"能力位当关节"上（一一对应，不是比喻）
| Omni-Arm | 我们这边 | 落点 |
|---|---|---|
| 感知层（先看后动） | 只读面：ruler / scan / status / plan | 本模块 `limits` / `plan` |
| 驱动层（力位一体+反向驱动+冲击保护） | `run_task` 唯一门 + 每个关节自己的限位 | `move`（逐关节，回执原样带回） |
| 遥操作层（主从 + ROS 解耦） | 主人一句话 = 主端；触手 = 从端；关节序列 = 话题 | `plan` → `move` |
| 决策层（端到端） | 主脑路由（选哪个触手/哪个 op） | `plan` 的候选排序 |
| 安全层（排队规则 + 冲击保护 + 离线降级） | 三道护栏 + `filesystem_write` 票 + fail-closed | `limits` 现算 + `_joint_gate` |

## 关节是什么（不许含糊）
一个**关节** = 一次 `(能力位 kind, op, payload)` 的具名动作。它有三个必须现读、不许手写的量：
  · `dof`：这位在注册表里登记了几个 op（op 越多，可转的轴越多）
  · `limits`：`policy.evaluate(kind, {op})` **现算**出来的「要哪些票」——不是我在注释里许愿
  · `reversible`：只读 op 天然可逆；写 op 只有接了回滚的才算可逆（没接就如实标 `不可逆`）

## 冲击保护（对应 `DriveLayer.set_joint_angles` 的越限拒绝）
任何一步在**执行前**先量：① 缺票 ⇒ 直接拒（不动手，回执带 how_to_grant）
② 参数缺必填 ⇒ 直接拒（不空转）③ 未知 op ⇒ 直接拒。**拒绝发生在动手之前**，不是事后报错。

## 误差测量（对应 `ik` 的 eps 判据）
`move` 支持 `expect`（期望回执里出现的字段/值）：动完**量偏差**并如实上报，不把"调了"当"到了"。

ops：`status` / `limits` / `plan` / `move` / `where`
  · `status` / `limits` / `plan` / `where` —— 纯读，免门
  · `move` —— 逐关节走 `run_task`，**每一位的票由那一位自己的门收**（本模块不另加门，也不绕门）
"""
from __future__ import annotations

import json
import re
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

OPS = ("status", "limits", "plan", "move", "where")
MAX_JOINTS = 8            # 一条动作链最多 8 个关节（超过要人拆，防止一根触手乱扫）


def _caps() -> dict:
    from ..caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _required(kind: str) -> list:
    from ..caps_tables import required_params
    return list(required_params(kind) or [])


def _scopes_for(kind: str, op: str) -> dict:
    """**现算**限位：这一位这个 op 要什么票。来源是 policy.evaluate，不是我写的表。"""
    from ..security import policy as _policy
    d = _policy.evaluate(kind, {"op": op} if op else {})
    return {"scopes": sorted(getattr(d, "scopes", []) or []),
            "risk": getattr(d, "risk", "?"),
            "allowed": bool(getattr(d, "allowed", True))}


def _ops_of(kind: str) -> list:
    """从注册表 desc 里现读 op 列表（注册表是唯一真源；读不到就如实给空）。"""
    desc = str((_caps().get(kind) or {}).get("desc") or "")
    m = re.search(r"op=([a-z0-9_/、, \-]+)", desc)
    if not m:
        return []
    raw = m.group(1)
    ops = re.split(r"[/、,，\s]+", raw)
    out = []
    for o in ops:
        o = o.strip().strip("（）()")
        if o and re.match(r"^[a-z][a-z0-9_]*$", o) and o not in out:
            out.append(o)
    return out


def _joint(kind: str, op: str = "") -> dict:
    caps = _caps()
    if kind not in caps:
        return {"ok": False, "tentacle": kind, "error": "注册表里没有这一位",
                "nearest": _nearest(kind)}
    ops = _ops_of(kind)
    op = str(op or (ops[0] if ops else "status")).strip().lower()
    sc = _scopes_for(kind, op)
    need = _required(kind)
    # 🔴 限位必须连**处理器层**的闸一起量（2026-10-19 实测的盲区）：
    #    `rig_fix.run` 在 policy.evaluate 里 scopes 是空的（policy 不认这个 kind 的写面），
    #    但它的模块自己在处理器层要 filesystem_write ⇒ 只看 policy 会把"要票"读成"不要票"。
    #    真源用 `preflight.is_side_effect`（全仓唯一那张"会改状态"的表，已挂进开机自检）。
    side, handler_gate = False, []
    try:
        from .. import preflight as _pf
        side = bool(_pf.is_side_effect(kind, {"op": op}))
    except Exception:                                          # noqa: BLE001
        side = False
    if side and "filesystem_write" not in sc["scopes"]:
        handler_gate.append("filesystem_write")
    tickets = list(sc["scopes"]) + handler_gate
    return {"ok": True, "tentacle": kind,
            "domain": (caps.get(kind) or {}).get("domain"),
            "dof": len(ops) or 1,
            "ops": ops,
            "joint": op,
            "limits": {"需票": tickets, "风险": sc["risk"], "门放行": sc["allowed"],
                       "必填参数": need, "处理器层闸": handler_gate,
                       "副作用": side},
            "reversible": "是（只读 op）" if not tickets else "否（写/有副作用，须自带回滚）",
            "safe": bool((caps.get(kind) or {}).get("safe", True))}


def _nearest(name: str) -> list:
    import difflib
    try:
        return difflib.get_close_matches(str(name), list(_caps()), n=4, cutoff=0.5)
    except Exception:                                          # noqa: BLE001
        return []


# ── 读面 ─────────────────────────────────────────────────────────────────────
def status(tentacle: str = "", **_kw) -> dict:
    caps = _caps()
    if tentacle:
        return _joint(tentacle)
    rows = []
    for k in sorted(caps):
        ops = _ops_of(k)
        rows.append({"tentacle": k, "domain": (caps.get(k) or {}).get("domain"),
                     "dof": len(ops) or 1, "safe": bool((caps.get(k) or {}).get("safe", True))})
    return {"ok": True, "op": "status", "kind": "tentacle_arm",
            "触手数": len(rows),
            "关节模型": "一个关节 = 一次 (kind, op, payload)；dof = 注册表登记的几个 op",
            "口径": "limits 现算（policy.evaluate），不手写；move 逐关节走 run_task，票由那一位自己的门收",
            "rows": rows[:400], "rows_总数": len(rows), "ops": list(OPS)}


def limits(tentacle: str, joint: str = "", op: str = "", **_kw) -> dict:
    j = _joint(tentacle, joint or op)
    j["op"] = "limits"
    return j


def _is_subseq(need: str, hay: str) -> bool:
    """need 的字符是否**按序**出现在 hay 里（允许中间夹字：屈指 ⊂ 屈食指）。"""
    it = iter(hay)
    return all(ch in it for ch in need)


def _rig_chain(intent: str):
    """「抬左臂并屈食指」这类**动作人话** → 3 关节链（compile → pose → 八条闸复核）。

    为什么要单独这一支（2026-10-19 主人问「现在可以使用触手完美操控数字人绑骨了吧」时实测）：
    原来 `plan` 只按名字命中能力位，给一行 `dh_pose/status` —— 也就是"先看一眼"，**没有动作编排**。
    而绑骨操控真正要的是三段：① 把人话编成骨角度（免票，可先验）② 出图（要票）③ 八条闸复核。
    意图词**从语义表现读**（state/dh-pose/semantics.json），不在这里手写第二份。
    """
    try:
        from .dh_pose import _spec as _pose_spec
        table = {k: v for k, v in _pose_spec().items() if not str(k).startswith("_")}
    except Exception:                                          # noqa: BLE001
        return None
    acts = [k for k in table if k and k in intent]
    if not acts:
        # 语义表里的动作名不带侧别（抬臂），而人话会说"抬**左**臂"；指类还会说"屈**食**指"。
        # 所以去掉侧别/角度/标点后再做**按序包含**匹配（屈指 ⊂ 屈食指）。
        norm = str(intent)
        for w in ("左", "右", "左侧", "右侧"):
            norm = norm.replace(w, "")
        norm = re.sub(r"-?\d+(?:\.\d+)?", "", norm)
        # 「并指」这类动作名以连词开头：人话「抬臂**并**屈食指」里「并指」会按序命中，
        # 那是把连接词当动作（假命中，会让手指被多折一次）。规则：连词开头的动作名
        # **只有连续出现才算命中**；其它动作名允许按序夹字（屈指 ⊂ 屈食指）。
        _CONJ = ("并", "和", "与", "再", "然后", "接着")
        acts = sorted(
            (k for k in table
             if k and (k in norm or (not k.startswith(_CONJ) and _is_subseq(k, norm)))),
            key=len, reverse=True)[:3]
    if not acts:
        return None
    side = "左" if "左" in intent else ("右" if "右" in intent else "-")
    nums = re.findall(r"-?\d+(?:\.\d+)?", intent)
    deg = float(nums[0]) if nums else 45.0
    cmd = []
    for a in acts[:3]:
        cmd += [a, side, deg]
    steps = []
    for i, (op, note) in enumerate((("compile", "编成骨角度（免票，先看对不对）"),
                                    ("pose", "出图（要 filesystem_write：会起 Blender 并落盘）"),
                                    ("run", "八条闸复核（免票）")), 1):
        kind = "dh_pose" if op in ("compile", "pose") else "dh_asset_gate"
        j = _joint(kind, op)
        steps.append({"step": i, "tentacle": kind, "op": op,
                      "payload": {"cmd": cmd} if kind == "dh_pose" else {},
                      "说明": note,
                      "需票": (j.get("limits") or {}).get("需票"),
                      "必填参数": (j.get("limits") or {}).get("必填参数"),
                      "可逆": j.get("reversible")})
    return {"ok": True, "op": "plan", "intent": intent,
            "步骤": steps, "关节数": len(steps),
            "编译出的命令": cmd,
            "口径": "侧别只认 左/右/-；指类动作必须指定侧（dh_pose 自己会 fail-closed 拒）",
            "先看后动": "第 1 步免票，先跑它确认骨名/角度；第 2 步要票；第 3 步复核"}


def plan(intent: str = "", tentacle: str = "", joint: str = "", op: str = "",
         payload: dict | None = None, **_kw) -> dict:
    """**意图 → 关节序列**（遥操作层的主端）：认得出就给出可分步执行的动作链；认不出如实报。"""
    intent = str(intent or "").strip()
    # ① 绑骨动作人话优先走动作链（compile→pose→闸），而不是只给一行 status
    if tentacle in ("", "dh_pose") and intent:
        chain = _rig_chain(intent)
        if chain:
            return chain
    if tentacle:
        j = _joint(tentacle, joint or op)
        if not j.get("ok"):
            return {**j, "op": "plan", "fail_closed": True}
        steps = [{"step": 1, "tentacle": j["tentacle"], "op": j["joint"],
                  "payload": dict(payload or {}), "需票": j["limits"]["需票"],
                  "必填参数": j["limits"]["必填参数"], "可逆": j["reversible"]}]
        return {"ok": True, "op": "plan", "intent": intent or "(直接指定触手)", "steps": steps,
                "关节数": len(steps), "先看后动": "先跑 limits 确认限位，再 move"}
    # 没指定触手：按意图在能力位里找候选（只给候选与限位，不替人拍）
    hits = []
    for k in _caps():
        if intent and (intent.lower() in k.lower()):
            hits.append(k)
    if not hits:
        toks = [t for t in re.split(r"[\s，。、,]+", intent) if t]
        for k in _caps():
            for t in toks:
                if t and t.lower() in k.lower():
                    hits.append(k)
                    break
    hits = sorted(set(hits))[:MAX_JOINTS]
    if not hits:
        return {"ok": False, "op": "plan", "intent": intent,
                "error": "意图里认不出触手（本器不猜；给 tentacle=<能力位名> 或更具体的人话）",
                "available_sample": sorted(_caps())[:20], "fail_closed": True}
    steps = []
    for i, k in enumerate(hits, 1):
        j = _joint(k)
        steps.append({"step": i, "tentacle": k, "op": j.get("joint"), "需票": (j.get("limits") or {}).get("需票"),
                      "必填参数": (j.get("limits") or {}).get("必填参数"), "可逆": j.get("reversible")})
    return {"ok": True, "op": "plan", "intent": intent, "steps": steps, "关节数": len(steps),
            "注意": "候选按名字命中，**选哪个由主脑定**；执行前列 limits，执行后量误差"}


# ── 驱动面（逐关节走唯一门）─────────────────────────────────────────────────
def move(tentacle: str, joint: str = "", op: str = "", payload: dict | None = None,
         expect: dict | None = None, **_kw) -> dict:
    """执行一个关节：先量限位（缺票/缺参/未知 op 一律**动手前**拒），再走 `run_task`，最后量误差。"""
    j = _joint(tentacle, joint or op)
    if not j.get("ok"):
        return {**j, "op": "move", "fail_closed": True, "moved": False}
    p = dict(payload or {})
    p["op"] = j["joint"]
    need = j["limits"]["必填参数"]
    missing = [k for k in need if k not in p or p.get(k) in (None, "")]
    if missing:
        return {"ok": False, "op": "move", "tentacle": j["tentacle"], "joint": j["joint"],
                "moved": False, "fail_closed": True,
                "error": "缺必填参数：%s" % ", ".join(missing), "必填参数": need}
    if not j["ops"] and not (joint or op):
        return {"ok": False, "op": "move", "tentacle": j["tentacle"], "moved": False,
                "fail_closed": True, "op_已登记": False,
                "error": "这一位的 op 从注册表读不出来（desc 里没有 op= 段）—— **我不猜**："
                         "要么补登记，要么显式给 joint=<op>（你语义核对过才给）"}
    try:
        from .. import run_task
        r = run_task(tentacle, p)
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "move", "tentacle": j["tentacle"], "joint": j["joint"],
                "moved": False, "fail_closed": True,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}
    body = (r.get("gbt_result") or {}).get("result") if isinstance(r, dict) else None
    denied = bool((body or {}).get("denied")) or bool((r or {}).get("denied"))
    out = {"ok": not denied and bool((r or {}).get("ok", True)),
           "op": "move", "tentacle": j["tentacle"], "joint": j["joint"],
           "moved": not denied, "denied": denied,
           "回执": r if len(json.dumps(r, ensure_ascii=False, default=str)) < 4000 else
                   {"ok": (r or {}).get("ok"), "status": (r or {}).get("status"),
                    "note": "回执过长已收窄；要看全量就单独调 cap"},
           "限位": j["limits"]}
    if denied:
        out["how_to_grant"] = (body or {}).get("how_to_grant") or (r or {}).get("how_to_grant")
        out["error"] = (body or {}).get("error") or (r or {}).get("error") or "门拒（缺票）"
        return out
    # 误差测量：expect 是 {字段名: 期望值}，从回执里逐条取值比对
    if expect:
        flat = json.dumps(body if body is not None else r, ensure_ascii=False, default=str)
        errs = []
        for k, want in expect.items():
            m = re.search(r'"%s"\s*:\s*("?)([^",}\]]+)\1' % re.escape(str(k)), flat)
            got = m.group(2).strip() if m else None
            ok = (got is not None and str(got).lower() == str(want).lower())
            errs.append({"字段": k, "期望": want, "实得": got, "对上": ok})
        out["误差"] = {"项": errs, "全对": all(e["对上"] for e in errs)}
    return out


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "tentacle_arm",
            "entry": "py -3.14 tools/codex-scripts/five-dim.py cap tentacle_arm '{\"op\":\"status\"}'",
            "用法": ["limits：先量限位（需票/必填参/可逆）",
                     "plan：意图→关节序列（只给候选，选哪个由主脑定）",
                     "move：逐关节走 run_task，动完量误差"],
            "五层对应": {"感知": "limits/plan", "驱动": "move", "遥操作": "plan→move",
                         "决策": "主脑选触手", "安全": "三道护栏+票+fail-closed"},
            "不许": "不绕门、不自己发票、不把『调了』当『到了』"}


def run_op(op: str = "status", **kw) -> dict:
    table = {"status": status, "limits": limits, "plan": plan, "move": move, "where": where}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table),
                "fail_closed": True}
    return fn(**kw)


if __name__ == "__main__":
    print(json.dumps(run_op(sys.argv[1] if len(sys.argv) > 1 else "status",
                            **(json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})),
                     ensure_ascii=False, indent=1))
