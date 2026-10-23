# gbt-capability: bi_distill
"""蒸馏件：**拖拽式 BI 的三条取法 + 一条许可红线**。

吞入件：dataease/dataease（**GPL-3.0**（README 徽章明写 GPL v3；GitHub 未识别才标 NOASSERTION）·
24603★ · Java ·「人人可用的开源 BI 工具」）。
本位**不是接入端**（不联网、不起 Docker、不装离线包、只读+纯算）⇒ 零作用域。

## 为什么是「取法」不是「建平行位」
出表/出报表的位我们**已有**：`genoffice`（sheets/docs/slides）· `datakit` · `record_grid` ⇒
照抄建个平行的「dataease 位」会撞「新增即清旧」的「同功能两份」。

## 蒸馏三条 + 一条红线（见 op=provenance）
1. **拖拽即建模**：原文「通过拖拉拽方式快速制作图表」「鼠标点击和拖拽即可完成分析」→
   先做可拖拽的**字段化**数据模型，再谈图表。
2. **连接面要如实列**：原文列了 OLTP/OLAP/数仓/文件/API 五类数据源 → 连得上的**如实列**，
   连不上的**如实说**（不写"支持一切"）。
3. **可分享是产品属性**：原文「方便的与他人分享」→ 分析产物必须能**交出去**（不是留在自己盘里）。
4. 🔴 **许可红线（GPL-3.0）**：只引用不复制 —— 复用其**实现**就要守 GPL；本位只蒸取法。

op=method / source / provenance / where
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULE = _ROOT / "gbt_allinone" / "store" / "devoured" / "devoured_dataease_dataease"

_METHOD = (
    {"序": "①", "取法": "拖拽即建模（字段化在前）",
     "原话": "通过拖拉拽方式快速制作图表 … 鼠标点击和拖拽即可完成分析",
     "我们的落点": "先把数据做成**可拖拽的字段模型**，再谈图；不让用户写查询",
     "我们已有": "genoffice（表格）· datakit · record_grid"},
    {"序": "②", "取法": "连接面如实列（支持=真连得上）",
     "原话": "支持的数据源：OLTP（MySQL/Oracle/…）· OLAP（ClickHouse/Doris/…）· 数仓/数据湖 · 文件（Excel/CSV）· API",
     "我们的落点": "「支持 X」= **真连得上**；连不上的如实说，不写「支持一切」",
     "我们已有": "仓里的「已配/未配」口径 + 未验照实标"},
    {"序": "③", "取法": "可分享是产品属性（不是附加项）",
     "原话": "可以方便的与他人分享 … 支持多种数据分享方式",
     "我们的落点": "分析产物必须能**交出去**（落盘/分享），不留在自己盘里当私货",
     "我们已有": "create（产物登记 + outputs 写入）· genoffice 导出"},
    {"序": "④", "取法": "🔴 许可红线：GPL-3.0，只引用不复制",
     "原话": "License: GPL v3（README 徽章）",
     "我们的落点": "本位只蒸**取法**；要复用它的**实现**，必须先过 GPL 那关（主人定）",
     "我们已有": "仓规「只引用不复制」+ 许可红线（同 CyberStrike 那条）"},
)


def method(**_kw) -> dict:
    return {"ok": True, "op": "method", "kind": "bi_distill", "条目": [dict(r) for r in _METHOD],
            "口径": "**取法**不是**建位**：三条取法 + 一条许可红线；报表位已有 genoffice/datakit，不建平行位"}


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
    return {"ok": True, "op": "source", "kind": "bi_distill",
            "repo": "dataease/dataease", "license": "GPL-3.0", "stars": 24603,
            "胶囊": str(_CAPSULE.relative_to(_ROOT)).replace("\\", "/"), "文件": files}


def provenance(**_kw) -> dict:
    return {"ok": True, "op": "provenance", "kind": "bi_distill",
            "吞入件": {"repo": "dataease/dataease", "license": "GPL-3.0", "stars": 24603,
                       "胶囊": "gbt_allinone/store/devoured/devoured_dataease_dataease/"},
            "蒸馏映射": [
                {"原话/出处": "通过拖拉拽方式快速制作图表 … 极易上手，通过鼠标点击和拖拽即可完成分析（README：什么是 DataEase）",
                 "落成": "op=method ①（拖拽即建模）"},
                {"原话/出处": "DataEase 支持的数据源：OLTP / OLAP / 数据仓库·数据湖 / 数据文件 / API（README）",
                 "落成": "op=method ②（连接面如实列）"},
                {"原话/出处": "可以方便的与他人分享 … 支持多种数据分享方式（README：优势）",
                 "落成": "op=method ③（可分享）"},
                {"原话/出处": "License: GPL v3（README 徽章）",
                 "落成": "op=method ④（许可红线：只引用不复制）"},
                {"原话/出处": "离线安装包 + bash install.sh + 2 核 4G Linux（README：快速开始）",
                 "落成": "**未蒸馏（故意）**：那是**它这个产品**的部署，不是取法"},
            ],
            "边界": "接入端 ≡ 我们**已有**的 `genoffice` / `datakit` / `record_grid`；本位 ≡ 蒸馏件（BI 取法 + 许可红线）",
            "口径": "蒸馏 = 把外面**契合我们**的那部分取法变成我们自己的判据；没蒸的如实标在「未蒸馏」行"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "bi_distill", "tentacle": "bi_distill",
            "entry": "run_task('bi_distill', {'op': …})",
            "ops": ["method", "source", "provenance", "where"],
            "files": {"handler": "gbt_allinone/tools/bi_distill.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_dataease_dataease/"},
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
