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

# 🔴 2026-10-25：原来写死 Windows 绝对路径 `C:\Users\ADMIN\Desktop\GBT小土豆V8`，
#    Linux 上拼出来的路径不存在 ⇒ look_grade 整个能力位报 FileNotFoundError。
#    改成**按本文件位置推仓根**（gbt_allinone/tools/x.py → parents[2]），换机器零改动。
ROOT = Path(__file__).resolve().parents[2]
_FG = ROOT / "tools" / "filmgrade.py"
READ_OPS = ("list", "pick", "qc")
WRITE_OPS = ("preview",)


class ImplMissing(RuntimeError):
    """实现文件不在仓库里 —— 与"代码坏了"要分开报。"""


def _fg():
    # 🔴 生产口径（2026-10-25）：Commander 仓库**没有随发布 tools/filmgrade.py**。
    #    以前这里直接 exec_module ⇒ 整个能力位报 FileNotFoundError，
    #    跟"代码写坏了"看起来一模一样。现在显式区分：缺文件走 ImplMissing。
    if not _FG.is_file():
        try:
            shown = str(_FG.relative_to(ROOT))
        except ValueError:
            shown = str(_FG)
        raise ImplMissing("实现文件未随仓库发布: %s" % shown)
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
    try:
        fg = _fg()
    except ImplMissing as e:
        # 实现文件不在仓库 ⇒ 如实报，归到"未实现"，不是"代码坏了"
        return {"ok": False, "op": op, "kind": "look_grade",
                "reason_code": "impl_missing", "error": str(e),
                "how_to_fix": "把 tools/filmgrade.py 一起纳入仓库（它是外观库的真实实现）"}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "op": op, "kind": "look_grade",
                "reason_code": "impl_error", "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
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
