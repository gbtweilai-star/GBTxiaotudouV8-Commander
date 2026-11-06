# -*- coding: utf-8 -*-
"""薄壳：真正的实现在 ``gbt_allinone/operator_index.py``。

    python tools/codex-scripts/build-operator-index.py build
    python tools/codex-scripts/build-operator-index.py check
    python tools/codex-scripts/build-operator-index.py score "看屏幕"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone import operator_index as OI  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(OI.main())
