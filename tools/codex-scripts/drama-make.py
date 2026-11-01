# gbt-capability: drama_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""drama-make.py — 调 drama_forge.make（请求体从 JSON 文件读，避免命令行转义）。

用法：py -B -X utf8 tools/codex-scripts/drama-make.py <repo> <request_json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
req = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
sys.path.insert(0, str(repo))
from gbt_allinone import api  # noqa: E402

r = api.run_task("drama_forge", req)
inner = (r.get("gbt_result") or {}).get("result") or {}
print(json.dumps(inner, ensure_ascii=False, indent=1))
sys.exit(0 if inner.get("ok") else 1)
