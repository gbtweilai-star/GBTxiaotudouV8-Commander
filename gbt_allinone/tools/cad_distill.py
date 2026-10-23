# gbt-capability: cad_distill
"""蒸馏件：**把 CAD 内核挂成 agent 工作区**的取法（挂真内核 · 脚本即接口 · 改前读回 · 结论要算）。

吞入件：neka-nat/freecad-mcp（MIT · 2833★ · Python ·「Control FreeCAD from Claude Desktop and other MCP clients.
Create and edit models, run Python scripts, inspect documents, and run FEM analyses.」）。
本位**不是接入端**（不联网、不起 FreeCAD、不装 uvx、只读+纯算）⇒ 零作用域。

## 为什么是「取法」不是「建平行位」
CAD 的位我们**已有** `cadgen`（建/改参数化模型、导出 STEP/STL/3MF/GLB）⇒ 照抄会撞
「新增即清旧」的「同功能两份」。本位只蒸它那四条**挂载取法**。

## 蒸馏四条（每条指回原话，见 op=provenance）
1. **挂真内核，不另起一个**：它把 addon 装进 FreeCAD **里面**、开 RPC server，客户端接的是**在跑的那个内核**
   （原文：an addon running inside FreeCAD and an MCP server launched by your client / click Start RPC Server）。
2. **脚本即接口**：原文「run Python scripts」→ 复杂建模走脚本，别硬编码成几百条命令。
3. **改前先读回**：原文「inspect documents」→ 动之前先把当前文档状态读回来（同 tentacle 铁律 1）。
4. **工程结论必须算出来**：原文「run FEM analyses」→ 力学/热学的结论要**跑**，不许估（同 machine_distill ①）。

op=method / source / provenance / where
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULE = _ROOT / "gbt_allinone" / "store" / "devoured" / "devoured_neka-nat_freecad-mcp"

_METHOD = (
    {"序": "①", "取法": "挂真内核，不另起一个",
     "原话": "an addon running inside FreeCAD and an MCP server launched by your client … click Start RPC Server",
     "我们的落点": "能力位挂的是**在跑的那个内核**；不偷偷起第二个实例（不然模型对不上）",
     "我们已有": "cadgen（建/改模型）· desktop_commander（起进程那条线）"},
    {"序": "②", "取法": "脚本即接口",
     "原话": "run Python scripts",
     "我们的落点": "复杂建模交给**脚本**，不把每条动作硬编码成一串命令",
     "我们已有": "code_patch（改代码那一门）· 万能插的脚本口径"},
    {"序": "③", "取法": "改前先读回",
     "原话": "inspect documents",
     "我们的落点": "动 CAD 之前先读回当前文档状态（同 tentacle 铁律 1「先看再动」）",
     "我们已有": "tentacle（read_text / list_windows）"},
    {"序": "④", "取法": "工程结论必须算出来",
     "原话": "run FEM analyses",
     "我们的落点": "力学/热学结论要**跑**出来；不许目测（同 machine_distill ①）",
     "我们已有": "machine_distill ①（每帧真解）· sec_chain（带依据推演）"},
)


def method(**_kw) -> dict:
    return {"ok": True, "op": "method", "kind": "cad_distill", "条目": [dict(r) for r in _METHOD],
            "口径": "**取法**不是**建位**：四条落在已有承接位/纪律上（CAD 位已有 `cadgen`，不建平行位）"}


def source(**_kw) -> dict:
    if not _CAPSULE.is_dir():
        return {"ok": False, "op": "source", "error": "胶囊不在盘上：" + str(_CAPSULE)}
    files = []
    for f in sorted(_CAPSULE.rglob("*")):
        if f.is_file():
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            files.append({"name": f.name, "bytes": f.stat().st_size, "sha256": h.hexdigest()[:16]})
    return {"ok": True, "op": "source", "kind": "cad_distill",
            "repo": "neka-nat/freecad-mcp", "license": "MIT", "stars": 2833,
            "胶囊": str(_CAPSULE.relative_to(_ROOT)).replace("\\", "/"), "文件": files}


def provenance(**_kw) -> dict:
    return {"ok": True, "op": "provenance", "kind": "cad_distill",
            "吞入件": {"repo": "neka-nat/freecad-mcp", "license": "MIT", "stars": 2833,
                       "胶囊": "gbt_allinone/store/devoured/devoured_neka-nat_freecad-mcp/"},
            "蒸馏映射": [
                {"原话/出处": "an addon running inside FreeCAD and an MCP server launched by your client（README：Quick start）",
                 "落成": "op=method ①（挂真内核）"},
                {"原话/出处": "run Python scripts（README：首段）", "落成": "op=method ②（脚本即接口）"},
                {"原话/出处": "inspect documents（README：首段）", "落成": "op=method ③（改前读回）"},
                {"原话/出处": "run FEM analyses（README：首段）", "落成": "op=method ④（结论要算）"},
                {"原话/出处": "git clone … / claude_desktop_config.json 的 uvx freecad-mcp（README：安装）",
                 "落成": "**未蒸馏（故意）**：装它 = 改别的 agent 配置 + 起 RPC 服务，不取"},
            ],
            "边界": "接入端 ≡ 我们**已有**的 `cadgen`；本位 ≡ 蒸馏件（挂载取法）",
            "口径": "蒸馏 = 把外面**契合我们**的那部分取法变成我们自己的判据；没蒸的如实标在「未蒸馏」行"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "cad_distill", "tentacle": "cad_distill",
            "entry": "run_task('cad_distill', {'op': …})",
            "ops": ["method", "source", "provenance", "where"],
            "files": {"handler": "gbt_allinone/tools/cad_distill.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_neka-nat_freecad-mcp/"},
            "scopes": "零作用域（只读 + 纯算：无 subprocess / 无 urllib / 无写盘）"}


_OPS = {"method": method, "source": source, "provenance": provenance, "where": where}
_ALLOWED = {"method": set(), "source": set(), "provenance": set(), "where": set()}


def run_op(op: str = "where", **params) -> dict:
    op = (op or "where").strip().lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "op": op, "fail_closed": True, "error": "未知 op：" + op, "ops": sorted(_OPS)}
    extra = set(params) - _ALLOWED[op]
    if extra:
        return {"ok": False, "op": op, "fail_closed": True, "error": "不认的参数：" + str(sorted(extra))}
    return fn(**params)
