# gbt-capability: omni_arm
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Omni-Arm 能力位（V57 那套 22DoF 手 + 9 骨手臂 + 8 段触手）—— 真几何 · 真绑骨 · 真 GLB。

## 来历（主人 2026-10-19 给六件设计稿）
`vendor/omni-arm/source/` 是逐字节归档的设计稿（Omni-Arm.py · Omni-Arm-3d-Rig.py ·
Omni-Arm-Blender.py · Omni-Arm-Threejs.json · Limit-Tentacles-3d.json）。
**它们不能直接跑**（本器已实测并把真因写进 `tools/codex-scripts/omni-arm-build.py` 头部）：
fk 只算 2D、ik 不是 CCD、random 决定骨架轴（不可复现）、生成的 Blender 脚本本身语法坏、
导出路径写死 /mnt/data。本能力位调用的是**重做后的实现**：
  `py -3.14 tools/codex-scripts/omni-arm-build.py`（确定性规格 → Blender 4.2 建骨/建几何/绑权重 → GLB）

## 它产出什么（现读）
  · `outputs/omni-arm/omni-arm-rigged.glb` —— 40 骨 / 1 网格 / 1 蒙皮 / 未绑 0 / 权重归一
  · `outputs/omni-arm/omni-arm-spec.json` —— 骨骼规格（零随机，可复现）
  · `outputs/omni-arm/omni-arm-report.json` —— 八条自检读数
  · 看件页：`holo_pet_w3/omni-arm/index.html`（骨架开关 · 骨骼树 · 现读体检 · 资产 sha16 自证）

## 门（处理器层挂闸，不碰 policy.py）
  · 读面免门：`status` / `spec`
  · 写面挂 `filesystem_write`：`build`（跑 Blender 建件并落 GLB/规格/报告）

ops：`status` / `spec` / `build` / `where`
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

WS = Path(__file__).resolve().parents[2]
BUILD = WS / "tools" / "codex-scripts" / "omni-arm-build.py"
OUT = WS / "outputs" / "omni-arm"
GLB = OUT / "omni-arm-rigged.glb"
SPEC = OUT / "omni-arm-spec.json"
REPORT = OUT / "omni-arm-report.json"
PAGE = WS / "holo_pet_w3" / "omni-arm" / "index.html"
SRC = WS / "vendor" / "omni-arm" / "source"
OPS = ("status", "spec", "build", "where")


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(WS)).replace("\\", "/")
    except ValueError:
        return str(p)


def _run(argv: list, timeout: int) -> dict:
    try:
        p = subprocess.run([sys.executable] + [str(a) for a in argv], cwd=str(WS),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=int(timeout))
        return {"ok": p.returncode == 0, "exit": p.returncode,
                "full": p.stdout or "", "out": (p.stdout or "")[-4000:],
                "err": (p.stderr or "")[-2000:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "fail_closed": True, "error": "超时（>%ss）" % timeout}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "fail_closed": True,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    got = auth_gate.check_and_consume("filesystem_write", detail=str(what)[:60])
    if got.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
            "note": "build 会跑 Blender 建件并落 GLB —— 写面必须人工授权"}


def status(**_kw) -> dict:
    report = {}
    if REPORT.is_file():
        try:
            report = json.loads(REPORT.read_text(encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            report = {}
    return {"ok": BUILD.is_file(), "op": "status", "kind": "omni_arm",
            "builder": _rel(BUILD), "builder_在位": BUILD.is_file(),
            "glb": _rel(GLB), "glb_在位": GLB.is_file(),
            "glb_bytes": GLB.stat().st_size if GLB.is_file() else 0,
            "page": _rel(PAGE), "page_在位": PAGE.is_file(),
            "设计稿归档": _rel(SRC), "设计稿": sorted(p.name for p in SRC.glob("*")) if SRC.is_dir() else [],
            "上次建件": {"at": report.get("at"), "ok": report.get("ok"),
                        "bones": report.get("bones"),
                        "八条": [c.get("名") for c in (report.get("checks") or [])]},
            "口径": "读面免门；build 过 filesystem_write（处理器层）；零随机，两次建件应逐字节一致",
            "ops": list(OPS)}


def spec(**_kw) -> dict:
    if SPEC.is_file():
        try:
            return {"ok": True, "op": "spec", "source": _rel(SPEC),
                    "data": json.loads(SPEC.read_text(encoding="utf-8"))}
        except Exception as exc:                               # noqa: BLE001
            return {"ok": False, "op": "spec", "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
    got = _run([BUILD, "--spec"], 120)
    if not got.get("ok"):
        return {"ok": False, "op": "spec", "error": got.get("error") or got.get("err")}
    try:
        return {"ok": True, "op": "spec", "data": json.loads(got.get("full") or "{}")}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "spec", "error": "规格不是 JSON：%s" % exc}


def build(timeout: int = 900, **_kw) -> dict:
    if not BUILD.is_file():
        return {"ok": False, "op": "build", "error": "建件器不在：%s" % _rel(BUILD)}
    denied = _gate("omni_arm:build")
    if denied:
        return {"op": "build", **denied}
    got = _run([BUILD, "--json"], timeout)
    data = None
    try:
        data = json.loads(got.get("full") or "")
    except Exception:                                          # noqa: BLE001
        data = None
    return {"ok": bool(got.get("ok")) and bool(data and data.get("ok")), "op": "build",
            "exit": got.get("exit"), "error": got.get("error"),
            "glb": (data or {}).get("glb"), "bytes": (data or {}).get("bytes"),
            "bones": (data or {}).get("bones"),
            "checks": (data or {}).get("checks"),
            "glb_check": (data or {}).get("glb_check"),
            "tail": (got.get("full") or "")[-800:] if not data else ""}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "omni_arm",
            "entry": "py -3.14 tools/codex-scripts/five-dim.py cap omni_arm '{\"op\":\"status\"}'",
            "建件": "cap omni_arm '{\"op\":\"build\"}'（要 filesystem_write 票）",
            "看件": _rel(PAGE), "产物": _rel(OUT), "设计稿": _rel(SRC),
            "骨数口径": "臂 9 + 掌 1 + 指 22 + 触手 8 = 40（skin.joints 为真源）"}


def run_op(op: str = "status", **kw) -> dict:
    table = {"status": status, "spec": spec, "build": build, "where": where}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table),
                "fail_closed": True}
    return fn(**kw)


if __name__ == "__main__":
    print(json.dumps(run_op(sys.argv[1] if len(sys.argv) > 1 else "status"),
                     ensure_ascii=False, indent=1))
