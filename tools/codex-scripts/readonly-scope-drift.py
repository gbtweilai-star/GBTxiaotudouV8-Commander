#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""只读作用域漂移判据（readonly-scope-drift）

主人令 2026-10-15：「**这里设计只读不需要票**」

它查一件事：**看着是读的 op，到底要不要票**。
  ① 程序接口面：op 的自述（docstring 第一行）开头是 读/看/列/查/取 ⇒ **读候选**
  ② 门的口径：`policy._READ_ONLY_*` 白名单
  ③ 对照：读候选却**不在**白名单 ⇒ 红（只读却要票）；
      写动词却**在**白名单 ⇒ 红（写动作被当成读）。

铁律：本件**只读 policy，不改 policy**（改它是主人专属；而且“把自己要票的 op 挪到不要票” = 自己给自己减授权，本仓红线点名禁止）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys

for _s in (sys.stdout, sys.stderr):                    # 2026-10-15 对齐：输出编码守门（本仓口径）
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

READ_VERBS = ("读", "看", "列", "查", "取", "测", "监测", "快照")
WRITE_VERBS = ("写", "删", "移", "复制", "改名", "打开", "定位", "执行", "发送", "上传")


def _ops_of(module_path: Path, prefix: str) -> dict:
    """把某个面上所有 `prefix*` op 及其自述第一行打出来。

    实测踩过：签名跨行的 op（如 `file_read_text(self, path,
        max_bytes,
        encoding)`）会被“单行正则”漏掉 ⇒ 判据只报一条。现在先定位到 `def`，
再在后面一段里找三引号。
    """
    src = module_path.read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(r"\n    def (" + prefix + r"[a-z_]+)\(", src):
        op = m.group(1)
        seg = src[m.end():m.end() + 800]
        d = re.search(r'"""([^\n]*)', seg)
        if d:
            out[op] = d.group(1).strip()
    return out


def audit() -> dict:
    from gbt_allinone.security import policy
    checks = [
        ("tentacle", ROOT / "gbt_allinone" / "tentacle" / "omni_fs.py", "file_",
         set(getattr(policy, "_READ_ONLY_TENTACLE", ()) or ())),
    ]
    findings = []
    for kind, path, prefix, whitelist in checks:
        for op, doc in sorted(_ops_of(path, prefix).items()):
            d = policy.evaluate(kind, {"action": op})
            scopes = sorted(getattr(d, "scopes", ()) or ())
            looks_read = doc.startswith(READ_VERBS)
            looks_write = doc.startswith(WRITE_VERBS)
            if looks_read and scopes:
                findings.append({"kind": kind, "op": op, "doc": doc[:60], "scopes": scopes,
                                 "why": "看着是读却要票"})
            if looks_write and not scopes:
                findings.append({"kind": kind, "op": op, "doc": doc[:60], "scopes": scopes,
                                 "why": "写动作却零票"})
            if op in whitelist and scopes:
                findings.append({"kind": kind, "op": op, "doc": doc[:60], "scopes": scopes,
                                 "why": "在白名单里却仍被要票"})
    return {"ok": not findings, "kind": "readonly_scope_drift", "findings": findings,
            "count": len(findings),
            "note": "只读判据；修法在 `security/policy.py`，**主人专属**",
            "how": "把读候选 op 加进 `_READ_ONLY_TENTACLE`（同族 `_READ_ONLY_DC_TOOLS` 已这么算）"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="只读作用域漂移判据")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = audit()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("== 只读作用域漂移 ==")
        for f in r["findings"]:
            print("  ✖ %-16s %-46s %s" % (f["op"], f["why"], ",".join(f["scopes"]) or "(零)"))
        print("合计：%s 条" % r["count"])
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
