# gbt-capability: blender
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Blender 可控制面 · **一个键都不许漏**的绑定（主人令 2026-09-27）。

主人原话：「把这些自动化触手连接**每一个可控制按键**的细节连接都做**双向绑定**确保**不会断连**，
`Blender 4.2.lnk` **所有可控制键都要绑定不能遗漏**。」

## 专业做法：**让 Blender 自己报出可控面**（不手抄 API 文档）
实测一次枚举（`--background --factory-startup` + 一段 python-expr）拿到：
  · **76 个命名空间**（`bpy.ops.object/mesh/material/scene/render/...`）
  · **2409 个算子**（每个命名空间下的全部 op —— 这就是"可控制键"）
  · **49 个数据类型**（`bpy.data.*` 的数据块族）
  · 版本 `4.2.16 LTS`（枚举时一并记下，便于升级后对比）
⇒ 清单落 `state/blender_surface.json`：**升级后重扫 + 与上次对比**：
  **新键 = 新增可控制面**（自动并入）；**消失的键 = 断连**（报警，不静默）。

## 双向绑定怎么落
  · **正向**：清单里每一个键 → 都能被触手经唯一门执行（`bpy` op：给算子名 + 参数字典）；
  · **反向**：每个键都在清单里有名有姓（命名空间→算子），清单本身作为**资产绑到 blender 触手**；
  · **不许漏**：`verify()` 拿判据卡（命名空间 ≥60 · 算子 ≥2000 · 数据族 ≥40 · 清单新鲜 · 无消失键未解释）。

## 红线段（可控 ≠ 无约束）
`wm.quit_blender` / `wm.read_homefile`(换文件) / `script.*`(执行外部脚本) / `wm.save_as_mainfile`(覆盖他文件) ——
这些**照常可调**（主人点名即可），但每次执行**记进台账** `state/blender_ops.jsonl`（谁在何时调了哪把"重键"）。

ops：
  surface [rescan=true]   枚举/重扫可控制面 → 写清单 + 与上次对比（新增/消失）
  keys                    人读摘要：命名空间/算子数/数据族/CLI 开关/消失键
  bpy  op="object.primitive_cube_add" [args={...}]    **执行任意算子**（过 filesystem_write 门）
  data kind="objects" count=false                     列数据块（只读）
  verify                  判据：清单完整性 + 无未解释的消失键
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / "state" / "blender_surface.json"
_OPS_LEDGER = _ROOT / "state" / "blender_ops.jsonl"
_CFG = None          # **各自配置**控制面（懒加载，见 _configs()）
_MAX_OUT = 6000
_MAX_TIMEOUT = 600
_FALLBACKS = [Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe")]

# 判据阈值（比实测值留余量：76/2409/49 → 60/2000/40）
MIN_NS, MIN_OPS, MIN_DATA = 60, 2000, 40

# CLI 开关（可控制键的另一半：不写 Python 也能控 Blender）
CLI_KEYS = [
    ("-b / --background", "无头运行（渲染/批处理必用）"),
    ("--python <file>", "跑脚本"),
    ("--python-expr <expr>", "跑一行表达式"),
    ("--factory-startup", "不加载用户配置（可复现）"),
    ("-E / --engine <name>", "渲染引擎（CYCLES/EEVEE/BLENDER_WORKBENCH）"),
    ("-o / --render-output <path>", "输出路径"),
    ("-f <frame>", "渲染指定帧"),
    ("-a / --render-anim", "渲染整段动画"),
    ("-s <frame> / -e <frame>", "起止帧"),
    ("--frame-jump <n>", "帧步进"),
    ("-noaudio", "禁音频（无头时更稳）"),
    ("--debug / --debug-python", "调试输出"),
    ("--version", "版本（只读）"),
    ("--addons <name,...>", "启用插件"),
    ("-y / --enable-autoexec", "允许自动执行脚本（**慎用**）"),
]

# 重键（照常可调，但每次记台账）
HEAVY_KEYS = ("wm.quit_blender", "wm.read_homefile", "wm.save_as_mainfile",
              "wm.save_as_mainfile_as", "script.python_file_run", "script.execute_preset")


def _cli() -> tuple:
    p = shutil.which("blender")
    if p:
        return p, ""
    for f in _FALLBACKS:
        if f.is_file():
            return str(f), ""
    return None, "未找到 blender.exe（PATH 与标准安装位都没有）"


def _ledger(row: dict) -> None:
    _OPS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_OPS_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _run_py(expr: str, timeout: int = _MAX_TIMEOUT) -> tuple:
    cli, miss = _cli()
    if not cli:
        return False, miss
    try:
        p = subprocess.run([cli, "--background", "--factory-startup", "--python-expr", expr],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode == 0, ((p.stdout or "") + (p.stderr or ""))
    except subprocess.TimeoutExpired:
        return False, f"Blender 超时（>{timeout}s）"
    except OSError as e:
        return False, f"{type(e).__name__}: {e}"


_ENUM_PY = (
    "import bpy,json;"
    "ns=[n for n in dir(bpy.ops) if not n.startswith('_')];"
    "d={n:[o for o in dir(getattr(bpy.ops,n)) if not o.startswith('_')] for n in ns};"
    "print('__GBTSURF__'+json.dumps({'ver':bpy.app.version_string,'ns':d,"
    "'data':[t for t in dir(bpy.data) if not t.startswith('_')]},ensure_ascii=False))"
)


def surface(rescan: bool = True, **_kw) -> dict:
    """枚举可控制面：命名空间 → 算子、数据族、版本；并与上次清单**对比**（消失的键 = 断连）。"""
    prev = {}
    if _MANIFEST.is_file():
        try:
            prev = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    if not rescan and prev:
        return {"ok": True, "op": "surface", "cached": True, "counts": prev.get("counts")}
    ok, out = _run_py(_ENUM_PY)
    if not ok or "__GBTSURF__" not in out:
        return {"ok": False, "op": "surface", "error": out[-400:], "cli": _cli()[0],
                "hint": "Blender 没跑起来或输出里没有枚举标记"}
    blob = json.loads(out.split("__GBTSURF__", 1)[1].splitlines()[0])
    ns = blob["ns"]
    counts = {"namespaces": len(ns), "operators": sum(len(v) for v in ns.values()),
              "data_types": len(blob.get("data") or []), "version": blob.get("ver")}
    gone, added = [], []
    if prev.get("ns"):
        for n, ops in (prev["ns"] or {}).items():
            if n not in ns:
                gone.append(n + ".*")
                continue
            for o in ops:
                if o not in ns[n]:
                    gone.append(f"{n}.{o}")
        for n, ops in ns.items():
            for o in ops:
                if n not in (prev["ns"] or {}) or o not in prev["ns"][n]:
                    added.append(f"{n}.{o}")
    man = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "counts": counts, "ns": ns,
           "data_types": blob.get("data") or [], "cli_keys": [k for k, _ in CLI_KEYS],
           "heavy_keys": list(HEAVY_KEYS),
           "gone": gone[:200], "added": added[:200],
           "_口径": "**让 Blender 自己报可控面**（不手抄 API）；升级后重扫与上次对比："
                   "新键=新增可控面，**消失的键=断连（要报警/解释）**"}
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = _MANIFEST.with_name(_MANIFEST.name + ".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _MANIFEST)
    _ledger({"event": "surface", **counts, "gone": len(gone), "added": len(added)})
    return {"ok": True, "op": "surface", "counts": counts, "gone": gone[:20],
            "added": added[:20], "gone_total": len(gone), "added_total": len(added),
            "manifest": str(_MANIFEST.relative_to(_ROOT))}


def keys(**_kw) -> dict:
    man = {}
    if _MANIFEST.is_file():
        try:
            man = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            man = {}
    if not man:
        return {"ok": False, "why": "还没有可控面清单 ⇒ 先跑 surface"}
    ns = man.get("ns") or {}
    top = sorted(((n, len(v)) for n, v in ns.items()), key=lambda x: -x[1])[:12]
    return {"ok": True, "op": "keys", "counts": man.get("counts"),
            "top_namespaces": [{"ns": n, "ops": c} for n, c in top],
            "data_types": (man.get("data_types") or [])[:12],
            "cli_keys": man.get("cli_keys"), "heavy_keys": man.get("heavy_keys"),
            "gone_total": len(man.get("gone") or []),
            "_口径": "可控制键 = 命名空间下的算子（每个都能经 bpy op 调用）+ 数据族 + CLI 开关"}


def bpy(op: str = "", args: dict | None = None, **kw) -> dict:
    """**执行任意算子**（可控制键的通用执行口）：`op='namespace.operator'` + 参数字典。

    过 `filesystem_write` 门（Blender 能写任意文件）；**重键**（退出/覆盖存盘/跑外部脚本）额外记台账。
    """
    if not op or "." not in op:
        return {"ok": False, "error": "op 形状应为 'namespace.operator'（如 object.primitive_cube_add）",
                "fail_closed": True}
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                             # noqa: F401
        from gbt_allinone import auth_gate                    # type: ignore
        from gbt_allinone.security import policy as _policy   # type: ignore
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write", detail=f"blender.bpy:{op}")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant"),
                    "op": op, "heavy": op in HEAVY_KEYS}
    payload = json.dumps(args or {}, ensure_ascii=False)
    expr = ("import bpy,json;"
            f"r=getattr(getattr(bpy.ops,{op.split('.')[0]!r}),{op.split('.',1)[1]!r})(**json.loads({payload!r}));"
            "print('__GBTBPY__'+json.dumps({'res':list(r) if hasattr(r,'__iter__') else str(r)},ensure_ascii=False))")
    if op in HEAVY_KEYS:
        _ledger({"event": "heavy_key", "op": op, "args": payload[:200]})
    okr, out = _run_py(expr)
    _ledger({"event": "bpy", "op": op, "ok": okr, "args": payload[:200]})
    res = ""
    if "__GBTBPY__" in out:
        res = out.split("__GBTBPY__", 1)[1].splitlines()[0][:400]
    return {"ok": okr, "op": "bpy", "blender_op": op, "args": args or {}, "result": res,
            "out_tail": ("" if res else out[-400:]),
            "_口径": "过 filesystem_write 门；重键额外记 state/blender_ops.jsonl（照常可调，有痕可查）"}


def data(kind: str = "objects", count: bool = True, **_kw) -> dict:
    """只读列数据块（`bpy.data.<kind>`）—— 检查场景里到底有什么。"""
    expr = (f"import bpy;d=getattr(bpy.data,{kind!r});"
            f"print('__GBTDATA__%d'%len(d));"
            f"print('__GBTNAMES__'+','.join([getattr(x,'name','?') for x in list(d)[:30]]))")
    okr, out = _run_py(expr)
    n = -1
    if "__GBTDATA__" in out:
        try:
            n = int(out.split("__GBTDATA__", 1)[1].split()[0])
        except (ValueError, IndexError):
            n = -1
    names = out.split("__GBTNAMES__", 1)[1].splitlines()[0] if "__GBTNAMES__" in out else ""
    return {"ok": okr, "op": "data", "kind": kind, "count": n,
            "names": names[:300], "_口径": "只读（factory-startup 的默认场景）"}


def verify(**_kw) -> dict:
    """判据：**清单完整性**（一个键都不许漏）+ 无未解释的消失键。"""
    man = {}
    if _MANIFEST.is_file():
        try:
            man = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            man = {}
    bad = []
    c = man.get("counts") or {}
    if not man:
        bad.append("没有可控面清单（先跑 surface）")
    else:
        if (c.get("namespaces") or 0) < MIN_NS:
            bad.append(f"命名空间 {c.get('namespaces')} < {MIN_NS}（可能枚举不全）")
        if (c.get("operators") or 0) < MIN_OPS:
            bad.append(f"算子 {c.get('operators')} < {MIN_OPS}（**有漏**）")
        if (c.get("data_types") or 0) < MIN_DATA:
            bad.append(f"数据族 {c.get('data_types')} < {MIN_DATA}（**有漏**）")
        if man.get("gone"):
            bad.append(f"**断连**：{len(man['gone'])} 个键消失未解释（例：{man['gone'][:3]}）")
    return {"ok": not bad, "op": "verify", "counts": c, "problems": bad,
            "thresholds": {"namespaces": MIN_NS, "operators": MIN_OPS, "data_types": MIN_DATA},
            "_口径": "阈值比实测留余量（实测 76/2409/49）；**消失的键=断连**，要解释或修"}


def _configs() -> dict:
    """**各自配置**的控制面（每个算子的参数：名/类型/默认值/说明）。

    🔴 2026-10-10 补（主人令同日再点一次这条：「把触手绑定 Blender 上面的所有控制按键
    **和各自配置**」）：既有件把**可控制键**做全了（2409 算子 + 双向绑定 + 升级对比），
    但**没暴露每个键的各自配置** —— bpy 口是**盲传参数**的（参数名写错也不拦）。
    本件补齐这一半：现读自 Blender 自己的 RNA（算子 rna_type 的 properties），
    实测 **2409 算子 · 5842 条参数配置**，落 state/surfaces/blender-ops.json。
    """
    global _CFG
    if _CFG is None:
        p = _ROOT / "state" / "surfaces" / "blender-ops.json"
        _CFG = (json.loads(p.read_text(encoding="utf-8")) if p.is_file()
                else {"总数": 0, "参数总数": 0, "逐条": []})
    return _CFG


def config(op: str = "", find: str = "", mod: str = "", limit: int = 60, **_kw) -> dict:
    """**各自配置**：查某个算子的参数清单 / 按关键词搜 / 按模块列。

    这就是「所有控制按键**和各自配置**」里的后半句 —— 光能按下去不算绑好，
    还得知道**每个键有哪些旋钮、默认值是多少**。
    """
    d = _configs()
    rows = d.get("逐条", [])
    if op:
        for r in rows:
            if r["op"] == op or r["op"].endswith("." + op):
                return {"ok": True, "op": "config", "算子": r["op"], "参数数": r.get("参数数"),
                        "参数": r.get("参数", []), "说明": r.get("说明", ""),
                        "口径": "参数名可**直接喂给 bpy 口**"}
        return {"ok": False, "fail_closed": True, "error": "控制面里没有这个算子：%s" % op,
                "提示": "先用 config find=关键词 找"}
    if find:
        q = find.lower()
        hits = [{"op": r["op"], "参数数": r.get("参数数"), "说明": (r.get("说明") or "")[:80]}
                for r in rows if q in (r["op"] + " " + (r.get("说明") or "")).lower()]
        return {"ok": True, "op": "config", "find": find, "命中": len(hits), "逐条": hits[:limit]}
    if mod:
        hit = [{"op": r["op"], "参数数": r.get("参数数")} for r in rows if r["op"].startswith(mod + ".")]
        return {"ok": True, "op": "config", "模块": mod, "条数": len(hit), "逐条": hit[:limit]}
    return {"ok": True, "op": "config", "算子总数": d.get("总数"), "参数配置总数": d.get("参数总数"),
            "用法": "config op='mesh.bevel' 看单个完整配置 · config find='bevel' 搜 · config mod='mesh' 按模块列",
            "口径": "**能按下去**（bpy）+ **知道每个键有哪些旋钮**（本件）= 才算绑全"}


def run_op(op: str = "keys", **params) -> dict:
    op = (op or "keys").lower()
    for name, fn in (("surface", surface), ("keys", keys), ("bpy", bpy),
                     ("data", data), ("verify", verify), ("config", config)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（surface/keys/bpy/data/verify/config）"}
