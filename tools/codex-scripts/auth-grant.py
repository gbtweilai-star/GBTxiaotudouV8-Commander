# -*- coding: utf-8 -*-
"""发放授权票 —— `python -m gbt_allinone auth grant` 在 pyembed 下**跑不了**。

血账（2026-11-06，主人当场撞上）：
    照 AGENTS.md / denied 回执里的指引敲
        .\\pyembed\\python.exe -m gbt_allinone auth grant --scope external_llm --ttl 600
    得到的是 `No module named gbt_allinone` —— 因为 `._pth` 让解释器进 isolated 模式，
    cwd 不进 sys.path、PYTHONPATH 被整个忽略（见 AGENTS.md §3.1 坑 C）。
    也就是说：**产品自带的运行时跑不了产品自带的授权命令**。
    人发不出票 ⇒ 危险能力全关 ⇒ 票门从"守门"变成"锁死"。
    所以这个壳不是便利，是**唯一能在 pyembed 下走通的发放路径**。

用法（在仓根执行）：
    .\\pyembed\\python.exe tools\\codex-scripts\\auth-grant.py --scope external_llm --ttl 600
    .\\pyembed\\python.exe tools\\codex-scripts\\auth-grant.py --scope process_execute --ttl 600
    .\\pyembed\\python.exe tools\\codex-scripts\\auth-grant.py status

`--scope` / `--ttl` 开头的写法等价于 `auth grant`（少打两个词）；
`grant` / `status` 开头则原样转给 CLI。
发放是**交互式**的：终端会要求敲 YES 才算数 —— agent 无法自批，这是设计。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from gbt_allinone.cli import main  # noqa: E402


def build_argv(raw: list) -> list:
    """把简写补成 CLI 认的 `auth ...`。纯函数，便于自检。"""
    a = list(raw or [])
    if not a:
        return ["auth", "status"]
    if a[0] in ("grant", "status"):
        return ["auth"] + a
    if a[0].startswith("--"):
        return ["auth", "grant"] + a
    return ["auth"] + a


if __name__ == "__main__":
    sys.exit(main(build_argv(sys.argv[1:])))
