# -*- coding: utf-8 -*-
r"""判据基础设施 · 退出码只认原生 rc（R97 · 改法 2 · 风哥 2026-09-18 拍）。

规则
----
1. 判 rc 一律不经 shell 管道：`run_native()` 内部 `shell=False`，只返回 `p.returncode`。
   禁止 `subprocess.run(..., shell=True)` 之后读工具报码。
2. 必须经 PowerShell 时：`& cmd *> out.txt` -> `$LASTEXITCODE` **落盘** -> 读该文件，
   不读工具报码。
3. **事实陈述**（免得后人再来"修"一遍）：R96 那次
   `native rc=0 + 一条 stderr + 2>&1 |` -> 工具报 1，是**取证工具链**的报码，
   **不是仓内代码缺陷**。仓内真 `shell=True` 命中 0
   （`security/security_brain.py:303` 里的 `shell\s*=\s*True` 是正则文本，不是调用）。

4. **判成败只看原生 rc + `Ran N tests / OK`** —— 禁止 `cmd 2>&1 | ...` 之后再判成败：
   管道会把 Python 写给 stderr 的正常输出变成 PowerShell 的「错误记录」，外层 rc 报成 1，
   而**原生 rc 其实是 0**（R96 与 R102 两次同坑）。要显示输出就 `cmd; echo "rc=$LASTEXITCODE"` ——
   **管道与判定分离**。

仓内判码点清单（R97 实测 · 8 项 · 只登记不动刀）
------------------------------------------------
| # | 文件:行 | 当前读码方式 | 是否涉及管道 |
|---|---|---|---|
| 1 | `deploy/run_isolated.ps1:41` | `$LASTEXITCODE -ne 0` | 否 |
| 2 | `deploy/run_isolated.ps1:52` | `2>$null` + `$LASTEXITCODE -eq 0` | 否（只重定向） |
| 3 | `deploy/run_isolated.ps1:120` | `exit $LASTEXITCODE` | 否 |
| 4 | `deploy/healthcheck.ps1:59` | `2>$null` + `$LASTEXITCODE -eq 0` | 否（只重定向） |
| 5 | `deploy/healthcheck.ps1:68` | 同上 | 否（只重定向） |
| 6 | `deploy/healthcheck.ps1:79-80` | `& ... 2>&1` | **是** |
| 7 | `deploy/bootstrap_deps.ps1:35 / :49` | `$LASTEXITCODE` | 否 |
| 8 | `deploy/install_codex_relay_watchdog.ps1:64` | `$code = $LASTEXITCODE` | 否 |

第 6 项单列：**半危险** —— 当前无人取其返回值作 rc；将来若被当 rc 必须重写。

结论：8 项全部读原生 rc，**没有**"shell 管道后读工具码"的既有缺陷。
本清单是**规则落地**，不是 bug 修复清单。
"""
from __future__ import annotations

import subprocess
from typing import Sequence

__all__ = ["run_native"]


def run_native(argv: Sequence[str], *, timeout: float | None = None, cwd=None,
               env=None, input_bytes: bytes | None = None):
    """跑一个原生进程，**只认它的 returncode**。

    返回 `(rc, stdout_bytes, stderr_bytes)`；超时抛 `subprocess.TimeoutExpired`
    （`subprocess.run` 已在超时时 kill 子进程）。`shell=False` 是硬约束 ——
    一旦经 shell，rc 就可能是 shell 的，不再是原生的。
    """
    p = subprocess.run(list(argv), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout, cwd=cwd, env=env, input=input_bytes,
                       shell=False)
    return p.returncode, p.stdout, p.stderr
