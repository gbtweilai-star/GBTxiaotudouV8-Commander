# -*- coding: utf-8 -*-
"""让 `python -m gbt_commander <子命令>` 能用。"""
from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
