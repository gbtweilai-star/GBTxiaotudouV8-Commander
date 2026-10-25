"""GBT小土豆V8 · 可终止的执行子进程入口。

仅由 engine._invoke 在有节点超时时调用。请求从 stdin 读取 JSON，结果原子写入
调用方指定的临时文件，避免能力自身的 stdout 输出污染协议。
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from .safe_io import atomic_write_json


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        return 2
    output = Path(args[0])
    try:
        request = json.loads(sys.stdin.read() or "{}")
        from .api import run_task

        result = run_task(request.get("kind"), request.get("params") or {})
        envelope = {"ok": True, "result": result}
    except BaseException as exc:  # noqa: BLE001 - 子进程必须把失败完整回传
        envelope = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-4000:],
        }
    atomic_write_json(output, envelope)
    return 0 if envelope.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
