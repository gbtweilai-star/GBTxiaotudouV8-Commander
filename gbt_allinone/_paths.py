# -*- coding: utf-8 -*-
"""统一路径解析 — 全框架 store 基址单一来源，支持 GBT_STORE_DIR 隔离（测试用）。"""
import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent  # gbt_allinone/


def _resolve_store() -> Path:
    env = os.getenv("GBT_STORE_DIR")
    return Path(env).resolve() if env else (_BASE / "store")


STORE_DIR = _resolve_store()


# ---- O53 甲案（风哥 2026-09-18 拍）：绑定快照，写入口前比对 ----
# `_resolve_store()` 只在 import 时刻读一次 env；此后 env 再变，绑定不会跟着变，
# 读写会**静默走旧绑定**。这里把绑定时刻的 env 快照留下来：写入口前比对，不一致
# 就 fail-fast —— 不自动改绑、不静默重绑。只读路径**不挂**这条检查（底线）。
STORE_DIR_ENV_AT_BIND = os.getenv('GBT_STORE_DIR')


def verify_store_binding() -> None:
    """写入口前的绑定一致性检查（O53 甲案）。不一致 -> RuntimeError，拒绝写入。"""
    current = os.getenv('GBT_STORE_DIR')
    if current != STORE_DIR_ENV_AT_BIND:
        raise RuntimeError(
            'store 绑定与环境变量不一致，拒绝写入 —— 绑定路径=%s 绑定时刻 '
            'GBT_STORE_DIR=%r 当前 GBT_STORE_DIR=%r'
            % (STORE_DIR, STORE_DIR_ENV_AT_BIND, current))

