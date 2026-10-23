# gbt-capability: look_grade
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""look_grade · 外观库触手（**词即指令**：想让她是什么样，她就变成什么样）

岗位：全产线的**外观（调色）中枢**——一处定义 N 种味道，actioncam / filmkit 同款引用；
支持**人话取味**（说「潮湿阴冷」「热血一点」「像老照片」就取到对应味）与**单帧试看**（定了再上全片）。

op：
  · `list`    只读：列出外观库（名字 + 一句话）
  · `pick`    只读：人话 → 外观名（含命中词/回落说明，**认不出如实标回落**）
  · `preview` 写面：单帧出样（过 filesystem_write 门）
  · `qc`      只读+台账：黑帧/卡帧/亮度机械化审计（总监令工作流第 1 步）

边界：本件只管**外观与审计**；拍子表/装配走 `actioncam`，剧本装配走 `filmkit`。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
_FG = ROOT / "tools" / "filmgrade.py"
READ_OPS = ("list", "pick", "qc")
WRITE_OPS = ("preview",)


def _fg():
    spec = importlib.util.spec_from_file_location("filmgrade", _FG)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _gate(what: str) -> dict | None:
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume("filesystem_write", detail=f"look_grade:{what}"[:60])
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": g.get("error"), "how_to_grant": g.get("how_to_grant")}


def status(**_kw) -> dict:
    return {"ok": True, "op": "status", "kind": "look_grade",
            "impl": str(_FG), "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
            "口径": "list/pick/qc 免门；preview 写盘过 filesystem_write；外观库一处定义、两条产线同款引用"}


def run(op: str = "list", **kw) -> dict:
    op = (op or "list").lower()
    fg = _fg()
    if op == "status":
        return status(**kw)
    if op == "list":
        return fg.looks_list()
    if op == "pick":
        intent = str(kw.get("intent") or kw.get("say") or "")
        if not intent:
            return {"ok": False, "error": "需要 intent=人话（如 '潮湿阴冷' / '热血一点'）"}
        return {"ok": True, **fg.pick_explain(intent), "label": fg.LOOKS[fg.pick(intent)]["label"]}
    if op == "preview":
        deny = _gate("preview")
        if deny:
            return deny
        src = str(kw.get("src") or "")
        if not src:
            return {"ok": False, "error": "需要 src=源图路径"}
        # 🔴 2026-10-13（主人令「每一个调节都要触手可控」）：`grain`（颗粒强度）原来**传不进来** ——
        #    `grade_chain(spec, grain)` 支持它，但 preview 没暴露 ⇒ 颗粒永远吃默认 6。
        #    现在从 op=preview 透传（不传 = None = 走原默认，行为不变）。
        return fg.preview(src, str(kw.get("look") or kw.get("intent") or "filmic"),
                          out=str(kw.get("out") or ""), grain=kw.get("grain"),
                          adjust=kw.get("adjust"))       # 补光族独立旋钮（brightness/contrast/saturation/gamma）
    if op == "qc":
        film = str(kw.get("film") or "")
        if not film:
            return {"ok": False, "error": "需要 film=成片路径"}
        p = Path(film) if Path(film).is_absolute() else ROOT / film
        return fg.qc(p, label=str(kw.get("label") or ""))
    return {"ok": False, "error": f"未知 op:{op}（{'/'.join(READ_OPS + WRITE_OPS)}）",
            "fail_closed": True}
