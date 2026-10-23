# gbt-capability: cadgen
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""cadgen —— 本机 CAD 链的口（能力位）。**薄壳**：一切走真件，不手搓实现。

## 为什么有这一位（2026-10-13 · 主人令「把这三个蒸馏提炼出契合我们的就可以了」）

图上那件 **FreeCAD-MCP 我们不搬**（本机没有 FreeCAD；我们自己的宿主 `cadgen` 本就带 MCP 出口）。
但现读发现**它是一根没接到触手上的手**：

| 查什么 | 现读 |
|---|---|
| 真件 | `cadgen 0.7.15`（`~/.local/bin/cadgen.exe`）· `cadgen doctor` ⇒ kernel OK(OCP) · python 3.13.15(uv) |
| 册上 271 位 | **没有 CAD 位**（3D 只有 blender / tripo / gs_h3） |
| `state/asset_bindings.json` | 搜 `cad/SKILL` ⇒ **0 命中** |
| 人话路由 | 实测 `omni ask "帮我建一个3D零件并导出STEP"` ⇒ **零命中 CAD** |

⇒ 能力栏页、绑定判据（C1–C15）、人话导航**都看不见它**。本件把它**登记成一位**：
不重写 CAD 内核、不装 FreeCAD、不手搓几何 —— 只做「口」。

## 铁律

1. **只调真件**：每条 op 都真跑 `cadgen`，参数**照它自己的 `--help` 现读**（不编 flag）。
2. **只认原生 rc**：走 `tools/native_rc.run_native`（`shell=False`）；**不许拿它打印的话判成败**。
3. **不假装**：二进制不在 ⇒ `needs_dependency`；`mcp` 要起长驻服务 ⇒ 本件**不接**，如实报 `not_wired`。
4. **本机没有 FreeCAD** 这条写进 `status` —— 免得后人以为本位接的是 FreeCAD。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_OPS = ("status", "where", "version", "doctor", "help", "snapshot")
_SUBS = ("step", "3mf", "glb", "dxf", "sdf", "srdf", "snapshot", "mcp", "daemon")


def _binary() -> str:
    """真件在哪：先查 PATH，再查 uv/本地装点。找不到回空串（不编路径）。"""
    hit = shutil.which("cadgen")
    if hit:
        return hit
    for cand in (Path.home() / ".local" / "bin" / ("cadgen.exe" if os.name == "nt" else "cadgen"),
                 Path.home() / "AppData" / "Roaming" / "uv" / "tools" / "cadgen" / "Scripts" / "cadgen.exe"):
        if cand.is_file():
            return str(cand)
    return ""


def _freecad_paths() -> list:
    if os.name != "nt":
        return []
    out = []
    for base in (r"C:\Program Files", r"C:\Program Files (x86)"):
        try:
            out.extend(str(p) for p in Path(base).glob("FreeCAD*"))
        except Exception:                                    # noqa: BLE001
            continue
    return out


def _run(args: list, timeout: float = 120.0) -> dict:
    """跑真件：**只认原生 rc**（`shell=False`，不许经管道/不许看它打印的话判成败）。"""
    b = _binary()
    if not b:
        return {"ok": False, "status": "needs_dependency", "missing": ["cadgen（真件不在 PATH 与 uv 装点）"],
                "checked": ["PATH", "~/.local/bin", "~/AppData/Roaming/uv/tools/cadgen"]}
    from . import native_rc as _rc                          # 本仓判码件（R97：只读原生 rc）
    try:
        rc, out, err = _rc.run_native([b] + [str(x) for x in args], timeout=timeout)
    except Exception as e:                                   # noqa: BLE001（含 TimeoutExpired）
        return {"ok": False, "status": "timeout" if "Timeout" in type(e).__name__ else "process_error",
                "error_class": type(e).__name__, "error": str(e)[:200],
                "cmd": [b] + [str(x) for x in args], "timeout_s": timeout}
    dec = lambda x: x.decode("utf-8", "replace")             # noqa: E731
    return {"ok": rc == 0, "rc": rc, "cmd": [b] + [str(x) for x in args],
            "stdout": dec(out)[:4000], "stderr": dec(err)[:2000]}


# ── 读面 ──────────────────────────────────────────────────────────────────
def status(**_kw) -> dict:
    """**纯探（不起进程）**：真件在不在、技能件在不在、本机有没有 FreeCAD。"""
    b = _binary()
    skill = Path.home() / ".agents" / "skills" / "cad" / "SKILL.md"
    fc = _freecad_paths()
    return {"ok": True, "op": "status", "kind": "cadgen",
            "binary": b or None, "binary_present": bool(b),
            "skill": str(skill), "skill_present": skill.is_file(),
            "freecad_present": bool(fc), "freecad_paths": fc,
            "freecad_note": "本机**没有 FreeCAD** —— 本位接的是 `cadgen`（真件），"
                            "**不接** FreeCAD-MCP 那条壳",
            "ops": list(_OPS),
            "mcp": "not_wired：`cadgen mcp` 是**长驻服务**，本位不接（要接请主人在终端点头后单独做）",
            "_口径": "status 是纯探；跑真件的四条（version/doctor/help/snapshot）过 process_execute 门"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "cadgen",
            "entry": "run_task('cadgen', {...})",
            "ops": list(_OPS),
            "what": "本机 CAD 链的**口**：只调真件 `cadgen`，不重写几何、不装 FreeCAD",
            "真件能力面（照它自己的 --help 现读）": ["mcp（serve CAD over MCP stdio）", "doctor", "snapshot",
                                                    "step / 3mf / glb build", "dxf / sdf / srdf validate"],
            "hard_rules": ["参数照真件 --help 现读，不编 flag",
                           "只认原生 rc（native_rc.run_native · shell=False）",
                           "二进制不在 ⇒ needs_dependency；未知 op ⇒ fail-closed",
                           "mcp 起长驻服务不接（not_wired）"],
            "how_to": "version/doctor 现读真件；help --sub <子命令> 现读它的真参数；"
                      "snapshot --target <图> --out <png> 真渲一张",
            "边界": "本机没有 FreeCAD；要那个 GUI 生态得先装（改本机环境，须主人点头）"}


# ── 跑面 ──────────────────────────────────────────────────────────────────
def version(**_kw) -> dict:
    r = _run(["--version"], timeout=60.0)
    r["op"] = "version"
    return r


def doctor(**_kw) -> dict:
    r = _run(["doctor"], timeout=120.0)
    r["op"] = "doctor"
    return r


def help(sub: str = "snapshot", **_kw) -> dict:
    """现读**真件的真参数**（本位不替它写文档）。"""
    s = str(sub or "").strip()
    if s and s not in _SUBS:
        return {"ok": False, "op": "help", "fail_closed": True,
                "error": "没这个子命令：%s" % s, "known": list(_SUBS)}
    r = _run([s, "--help"] if s else ["--help"], timeout=60.0)
    r["op"] = "help"
    r["sub"] = s or "(顶层)"
    return r


def snapshot(target=None, out=None, timeout: float = 300.0, **_kw) -> dict:
    """真渲一张：`cadgen snapshot TARGET OUT`（真件的签名词序，见它自己的 --help）。"""
    if not target:
        return {"ok": False, "op": "snapshot", "fail_closed": True, "status": "needs_params",
                "error": "要 target（STEP/STP/STL/3MF/GLB/DXF/URDF/SRDF/SDF 任一种）"}
    t = Path(str(target))
    if not t.is_file():
        return {"ok": False, "op": "snapshot", "status": "not_found",
                "error": "target 不在盘：%s" % t}
    o = Path(str(out)) if out else (t.with_suffix(".png"))
    o.parent.mkdir(parents=True, exist_ok=True)
    r = _run(["snapshot", str(t), str(o)], timeout=float(timeout))
    r["op"] = "snapshot"
    r["target"] = str(t)
    r["out"] = str(o)
    r["out_exists"] = o.is_file()
    r["out_bytes"] = o.stat().st_size if o.is_file() else 0
    # 🔴 不许"渲完就报成功"：rc=0 但**没产物**也是没成
    if r.get("ok") and not r["out_exists"]:
        r["ok"] = False
        r["error"] = "原生 rc=0 但**产物不在盘** ⇒ 不算渲出来"
    return r


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("where", where), ("version", version),
                   ("doctor", doctor), ("help", help), ("snapshot", snapshot)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "op": op, "fail_closed": True,
            "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    import json
    ap = argparse.ArgumentParser(description="本机 CAD 链的口（cadgen 薄壳）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}", help='入参 JSON，如 {"sub":"snapshot"}')
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
