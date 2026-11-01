"""GB T小土豆V8 · 全开失败归因（CLI）

用法：python tools/omni-attr.py [run_id]
输出：state/omni-attribution.json + outputs/omni-attribution-<run_id>.md

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone import omni_attr

rid = sys.argv[1] if len(sys.argv) > 1 else ""
r = omni_attr.attribute(rid)
print(json.dumps({k: r[k] for k in ("run_id", "executed", "failed", "categories", "report")},
                 ensure_ascii=False, indent=2))
