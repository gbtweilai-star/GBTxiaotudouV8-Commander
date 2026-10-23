# gbt-capability: blender
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Blender 4.2 三维引擎能力（本机已装 4.2.16 LTS · 2026-09-26 主人令编入工具栏）。

岗位：《末班义庄》AAA 画面线的三维引擎——3D 场景（义庄/血月/墨线阵）、Cycles 电影级渲染、
      摄影机动画、VSE 视频剪辑、几何节点——AAA 画面蒸馏手册绝活一二的全部落地工具。

边界：
  * status 直连（只读体检）；**一切 run（场景/渲染/脚本执行）过 filesystem_write 门**——
    Blender 能写任意文件、跑任意 Python，闸必须挂在处理器层（不碰 security/policy.py）；
  * CLI 发现顺序：shutil.which → Program Files 标准位（launcher 不写注册文件）；
  * 无头优先（-b）：渲染走 Cycles CPU 或 EEVEE（有显示/gpu 模块时）；
  * 超时 300s（渲染可慢），输出截断 4KB。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_FALLBACKS = [
    Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"),
]
_MAX_OUT = 4000
_MAX_TIMEOUT = 300
_READ_ONLY = {"--version"}


def _cli() -> tuple[str | None, str]:
    found = shutil.which("blender")
    if found:
        return found, ""
    for p in _FALLBACKS:
        if p.is_file():
            return str(p), ""
    return None, ("未找到 blender.exe（launcher 与标准安装位都没有）—— "
                  "确认 Blender 4.2 安装或把 blender.exe 路径加入 PATH")


def status(**_kw) -> dict:
    cli, miss = _cli()
    out = {"ok": True, "op": "status", "kind": "blender",
           "cli": cli or "", "billing": {"local_render": "免费（Cycles/Eevee 本地）"}}
    if not cli:
        out.update({"installed": False, "error": miss})
        return out
    try:
        p = subprocess.run([cli, "--version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        out["version"] = (p.stdout or "").splitlines()[0] if p.stdout else "?"
        out["headless"] = True
        out["engines"] = ["CYCLES（电影级光追·CPU/GPU）", "EEVEE_NEXT（实时·需显示环境）", "VSE（视频剪辑）"]
        out["口径"] = "status 免门；一切 run（渲染/脚本/导出）过 filesystem_write 门"
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = str(exc)[:160]
    return out


def run(args: list | None = None, timeout: int = 300, **_kw) -> dict:
    """透传 blender CLI 参数。args 示例：
    ["-b","-P","scene.py","--","--out","render.png"]  （-P 跑剧本脚本建场渲染）
    ["-b","--python-expr","import bpy; ..."]           （表达式快速操作）
    所有 run 一律过 filesystem_write 门（Blender 可写任意文件、执行任意 Python）。"""
    if not isinstance(args, list) or not all(isinstance(a, (str, int, float)) for a in args):
        return {"ok": False, "error": "args 必须是字符串/数字列表", "fail_closed": True}
    cli, miss = _cli()
    if not cli:
        return {"ok": False, "error": miss}
    from .. import auth_gate
    from ..security import policy as _policy
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write",
                                           detail="blender:" + " ".join(map(str, argv_safe := [str(a) for a in args]))[:60])
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant"),
                    "note": "Blender 可执行任意 Python 并写任意文件——写面必须人工授权"}
    t = max(30, min(_MAX_TIMEOUT, int(timeout)))
    try:
        p = subprocess.run([cli] + [str(a) for a in args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=t, cwd=str(_ROOT_OF()))
        out_text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {"ok": p.returncode == 0, "exit": p.returncode,
                "out": out_text[-_MAX_OUT:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Blender 超时（>{t}s）", "fail_closed": True}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "fail_closed": True}


def _ROOT_OF():
    return Path(__file__).resolve().parents[2]


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    if op == "status":
        return status(**params)
    if op == "run":
        return run(args=params.get("args"), timeout=params.get("timeout", 300),
                   **{k: v for k, v in params.items() if k != "args"})
    # 可控制面（主人令 2026-09-27「每一个可控制按键都要双向绑定」）：
    # 让 Blender 自己报出 76 命名空间 / 2409 算子 / 49 数据族，落 state/blender_surface.json；
    # 升级后重扫对比，**消失的键=断连**（报警，不静默）。执行口 bpy 过 filesystem_write 门。
    # 🔴 2026-10-10 补 config（主人令同日再点一次这条：「所有控制按键**和各自配置**」）：
    #    上一条主人令（2026-09-27）把**可控制键**绑全了（2409 算子 + 双向绑定 + 升级对比），
    #    但**没暴露每个键的各自配置** —— bpy 口是盲传参数的（参数名写错也不拦）。
    #    config = 每个算子的参数清单（名/类型/默认值/说明），现读自 Blender 自己的 RNA：
    #    实测 **2409 算子 · 5842 条参数配置**（state/surfaces/blender-ops.json）。
    if op in ("surface", "keys", "bpy", "data", "verify", "config"):
        import importlib.util as _iu
        _sp = _iu.spec_from_file_location("blender_surface", _ROOT_OF() / "gbt_allinone" / "tools" / "blender_surface.py")
        _bs = _iu.module_from_spec(_sp)
        _sp.loader.exec_module(_bs)
        return _bs.run_op(op, **params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（可用：status / run / surface / keys / bpy / data / verify / config）"}
