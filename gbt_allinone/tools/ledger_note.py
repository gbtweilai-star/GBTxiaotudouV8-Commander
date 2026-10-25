# -*- coding: utf-8 -*-
"""万能插 · 系统域加装：**台账登记（Ledger Note）**。

为什么有它：这一段时间「往 待落刀登记.md 追加一行」是靠外面手写的一次性脚本做的
（.scratch/_rhNNN_append.py）。脚本每次都把同一套机械保证重抄一遍 —— 抄漏一处就出事。
本模块把那一套保证**收进能力位**，从此这条路径**只有一种走法**：调它。

三原语（只有 APPEND 会写，且**只追加**）：
  RULES   读这台机器的七道硬闸（只读）
  PREVIEW 预演一行（只读：算出形状与将要增加的字节数，**一个字节都不落**）
  APPEND  往台账**文件尾机械追加一行**（唯一写原语）

七道机械闸（全是闸，不是口号）：
  ① **目标固定**：只能写这一份台账（`gbt_allinone/docs/待落刀登记.md`）—— 调用方**传不了路径**
  ② **只追加**：目标末尾必须是换行；不是换行就**拒写**（不修、不补、不猜）
  ③ **单物理行**：行内不许出现换行 ⇒ 每一刀就是**一个物理行**
  ④ **禁半角双引号**：与台账既有口径一致（中文串一律用「」）
  ⑤ **行首形状**：必须 `> **<label> 补记` —— 复核脚本按行首锚定，形状错了它找不到
  ⑥ **幂等**：同一 label 已存在 ⇒ **拒写**（不给重复登记开后门）
  ⑦ **缺前驱拒写**：给了 `after` 就必须是**当前最后一条**，否则拒（防插队、防回填）

边界（如实说）：
  · 本模块**不碰图纸**、**不出网**、**不装环境**、**不登记别的能力位**；
  · 它**不判断内容对不对** —— 内容正确与否是「取证 + 独立复核」那两步的事，不是它的活；
  · 写失败一律**抛错**，不返回半成功。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..safe_io import locked_append_text

CAP_KIND = "ledger_note"
DOMAIN = "system"
CAP_TYPE = "internal"
TRACE_SOURCE_KIND = "ledger_note"

# 目标**固定**：由本文件位置推出（gbt_allinone/tools/ledger_note.py → gbt_allinone/docs/…）
TARGET = Path(__file__).resolve().parents[1] / "docs" / "待落刀登记.md"

ROW_PREFIX = "> **"
ROW_MARK = " 补记"
QUOTE = chr(34)          # 半角双引号：台账那行**一个都不许有**

PRIMITIVES = (
    {"name": "RULES", "作用": "读七道硬闸 + 目标路径 + 当前最后一条 label", "判据": "只读"},
    {"name": "PREVIEW", "作用": "预演一行：返回形状、行长、将要增加的字节数", "判据": "只读，不落盘"},
    {"name": "APPEND", "作用": "往台账文件尾**机械追加一行**", "判据": "七道闸全过才写；幂等；只追加"},
)

GATES: Tuple[Tuple[str, str], ...] = (
    ("target_fixed", "只能写固定那一份台账；调用方传不了路径"),
    ("append_only", "目标末尾必须是换行，否则拒写（不修不补）"),
    ("single_physical_line", "行内不许有换行 ⇒ 一刀一个物理行"),
    ("no_halfwidth_quote", "行内不许有半角双引号（中文串用「」）"),
    ("row_shape", "行首必须 `> **<label> 补记`"),
    ("idempotent", "同一 label 已存在 ⇒ 拒写"),
    ("predecessor_required", "给了 after 就必须是当前最后一条"),
)

LABEL_RE = re.compile(r"^R-H\d+$")


class LedgerNoteError(Exception):
    """任何一道闸没过的统一出口（带 reason_code，便于用例断言）。"""

    def __init__(self, reason_code: str, message: str):
        super().__init__("%s: %s" % (reason_code, message))
        self.reason_code = reason_code
        self.message = message


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _rows(text: str) -> List[str]:
    return [ln for ln in text.split("\n") if ln.startswith(ROW_PREFIX)]


def _last_label(text: str) -> str:
    rows = [ln for ln in text.split("\n") if ln.startswith(ROW_PREFIX)]
    if not rows:
        return ""
    m = re.match(r"^> \*\*(R-H\d+)", rows[-1])
    return m.group(1) if m else ""


def build_line(label: str, body: str, title: str = "") -> str:
    """拼出**那一行**；只管形状，不管内容对错。"""
    label = str(label or "").strip()
    body = str(body or "")
    title = str(title or "").strip()
    if not LABEL_RE.match(label):
        raise LedgerNoteError("bad_label", "label 必须形如 R-H123，收到 %r" % label)
    if not body.strip():
        raise LedgerNoteError("empty_body", "body 不许为空")
    if "\n" in body or "\r" in body:
        raise LedgerNoteError("multi_line_body", "body 里不许有换行（一刀一行）")
    head = ("%s%s%s（%s）**：" % (ROW_PREFIX, label, ROW_MARK, title)
            if title else "%s%s%s**：" % (ROW_PREFIX, label, ROW_MARK))
    line = head + body
    if QUOTE in line:
        raise LedgerNoteError("no_halfwidth_quote",
                              "那一行里出现了半角双引号（台账口径：中文串用「」）")
    return line


def preview(label: str, body: str, title: str = "", path: Optional[Path] = None) -> Dict[str, Any]:
    """只读预演：算出这一行 + 会变成多少字节。**不落盘。**"""
    target = Path(path) if path is not None else TARGET
    line = build_line(label, body, title)
    text = _read(target) if target.is_file() else ""
    if target.is_file() and not text.endswith("\n"):
        raise LedgerNoteError("append_only", "目标末尾不是换行，拒绝盲追加")
    if label in text:
        raise LedgerNoteError("idempotent", "%s 已在台账里，拒绝重复登记" % label)
    block = "\n" + line + "\n"
    return {
        "ok": True,
        "dry_run": True,
        "target": str(target),
        "label": label,
        "line": line,
        "line_len": len(line),
        "physical_lines": 1,
        "file_len_before": len(text),
        "file_len_after": len(text) + len(block),
        "bytes_delta": len(block.encode("utf-8")),
        "last_label": _last_label(text),
    }


def append_line(label: str, body: str, title: str = "", after: str = "",
                path: Optional[Path] = None) -> Dict[str, Any]:
    """唯一写原语：先过七道闸，再**文件尾机械追加一行**。"""
    target = Path(path) if path is not None else TARGET
    if not target.is_file():
        raise LedgerNoteError("no_such_ledger", "台账不在盘上：%s" % target)

    line = build_line(label, body, title)
    text = _read(target)

    if not text.endswith("\n"):
        raise LedgerNoteError("append_only", "目标末尾不是换行，拒绝盲追加")
    if text.count("%s%s%s" % (ROW_PREFIX, label, ROW_MARK)) > 0:
        raise LedgerNoteError("idempotent", "%s 已在台账里，拒绝重复登记" % label)
    if not line.startswith("%s%s%s" % (ROW_PREFIX, label, ROW_MARK)):
        raise LedgerNoteError("row_shape", "行首形状不对")

    last = _last_label(text)
    if after and last != after:
        raise LedgerNoteError("predecessor_required",
                              "前驱应为 %s，盘上最后一条是 %s" % (after, last or "（空）"))

    block = "\n" + line + "\n"
    locked_append_text(target, block, encoding="utf-8")

    back = _read(target)
    own = [ln for ln in back.split("\n") if ln.startswith("%s%s%s" % (ROW_PREFIX, label, ROW_MARK))]
    if len(own) != 1 or not back.endswith(line + "\n"):
        raise LedgerNoteError("write_mismatch", "写后复核不一致（物理行数 %d）" % len(own))

    return {
        "ok": True,
        "appended": True,
        "dry_run": False,
        "target": str(target),
        "label": label,
        "physical_lines": 1,
        "file_len_before": len(text),
        "file_len_after": len(back),
        "bytes_delta": len(block.encode("utf-8")),
        "predecessor": last,
    }


def rules(path: Optional[Path] = None) -> Dict[str, Any]:
    """只读：这台机器的七道硬闸 + 目标现状。"""
    target = Path(path) if path is not None else TARGET
    text = _read(target) if target.is_file() else ""
    return {
        "ok": True,
        "readonly": True,
        "target": str(target),
        "gates": [{"gate": g, "含义": d} for g, d in GATES],
        "rows": len(_rows(text)),
        "last_label": _last_label(text),
        "honest_boundary": "不判内容对错 · 不碰图纸 · 不出网 · 不装环境 · 不登记别的能力位",
    }


def run(op: str = "status", **kw: Any) -> Dict[str, Any]:
    """能力位入口。op: status / rules / preview / append（未列出的一律拒）。"""
    op = str(op or "status").lower()
    if op in ("status", "rules"):
        return rules()
    if op == "preview":
        return preview(kw.get("label", ""), kw.get("body", ""), kw.get("title", ""))
    if op == "append":
        return append_line(kw.get("label", ""), kw.get("body", ""), kw.get("title", ""),
                           str(kw.get("after") or ""))
    raise LedgerNoteError("unknown_op", "未列出的动作一律拒绝：%s" % op)


__all__ = ["CAP_KIND", "DOMAIN", "CAP_TYPE", "TARGET", "GATES", "LedgerNoteError",
           "build_line", "preview", "append_line", "rules", "run"]
