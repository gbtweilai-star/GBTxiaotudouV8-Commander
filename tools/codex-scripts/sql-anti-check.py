# -*- coding: utf-8 -*-
"""sql-anti-check -- 数据库反模式机检（胶囊第 8 节 12 条）。命中即报，退出码非零。
用法：--file <sql> | --text "<sql>"
"""
from __future__ import annotations
import argparse, re

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


RULES = [
    ("SELECT * 宽表", r"select\s+\*\s+from"),
    ("OFFSET > 10000", r"limit\s+\d{5,}\s*,"),
    ("函数包裹索引列", r"where\s+\w+\s*\(\s*(\w*ts|\w*time|\w*date|created_at)\s*\)"),
    ("隐式类型转换", r"where\s+\w*id\w*\s*=\s*'\d+'"),
    ("分区表 DELETE 按范围", r"delete\s+from\s+\w+\s+where\s+\w*ts\w*\s*<"),
    ("ClickHouse 单行 INSERT", r"insert\s+into\s+\w+\s*\([^)]*\)\s*values\s*\([^)]*\)\s*;?\s*$"),
    ("DISTINCT 掩盖 fan-out", r"select\s+distinct.*\bjoin\b"),
    ("order_by('?')", r"order_by\s*\(\s*['\"]\?['\"]\s*\)"),
    ("NOT IN 子查询", r"not\s+in\s*\(\s*select"),
    ("前缀通配 LIKE", r"like\s+'%"),
    ("COUNT(*) 做分页总数", r"select\s+count\(\*\)\s+from\s+\w+\s*;?\s*$"),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--text")
    a = ap.parse_args()
    t = (open(a.file, encoding="utf-8", errors="replace").read() if a.file else (a.text or "")).lower()
    hits = [(n, rx) for n, rx in RULES if re.search(rx, t, re.S | re.M)]
    if not hits:
        print("SQL 反模式检查：未命中（%d 条规则全过）" % len(RULES))
        return 0
    print("SQL 反模式检查：命中 %d 条" % len(hits))
    for n, _ in hits:
        print("   [RED] %s" % n)
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
