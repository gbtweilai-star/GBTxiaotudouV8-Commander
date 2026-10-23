"""真实协议验证：thread/start 是否接受 developerInstructions 与 dynamicTools。

不发 turn，不消耗模型额度；只验证参数结构被 app-server 接受。
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from gbt_allinone import codex_bridge as cb  # noqa: E402


def main() -> int:
    server = cb.CodexAppServer(cwd=_ROOT)
    print("[codex]", server.codex_path)
    server.start()
    print("[server]", json.dumps(server.server_info, ensure_ascii=False)[:200])

    instructions = cb.default_developer_instructions("你是小土豆，一个数字人搭档。")
    print("[instructions chars]", len(instructions))

    result = server.start_thread(
        model=None,
        sandbox="read-only",
        approval_policy="on-request",
        approvals_reviewer="user",
        developer_instructions=instructions,
        dynamic_tools=cb.dynamic_tool_specs(),
        ephemeral=True,
    )
    thread = result.get("thread") or {}
    print("[thread id]", thread.get("id"))
    print("[thread model]", result.get("model"))
    print("[thread cwd]", thread.get("cwd"))
    print("[thread sandbox]", thread.get("sandbox"))
    print("[ephemeral]", thread.get("ephemeral"))

    models = server.list_models()
    print("[models]", [m.get("id") or m.get("model") for m in models][:8])
    print("[status]", json.dumps(server.status(), ensure_ascii=False)[:200])
    server.stop()
    print("[done] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
