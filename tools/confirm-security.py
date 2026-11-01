"""GBT小土豆V8 · 终端确认闸（主人侧 CLI）

AI 只能"申请"；**批准/拒绝必须在终端由主人执行**。攻击模式也由这里开关。

命令：
  python tools/confirm-security.py status
  python tools/confirm-security.py request <cap> --reason "用途"
  python tools/confirm-security.py approve <token>          # 主人在终端执行 = 放行
  python tools/confirm-security.py deny <token>
  python tools/confirm-security.py check <cap>
  python tools/confirm-security.py attack-on --reason "被扫描攻击" --evidence "日志/端口"
  python tools/confirm-security.py attack-off

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import security_policy as SP  # noqa: E402


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    arg = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else ""

    def opt(name, default=""):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    if cmd == "status":
        import json
        print(json.dumps(SP.status(), ensure_ascii=False, indent=2))
    elif cmd == "request":
        import json
        print(json.dumps(SP.request_confirm(arg, opt("--reason")), ensure_ascii=False, indent=2))
    elif cmd == "approve":
        import json
        print(json.dumps(SP.approve(arg), ensure_ascii=False, indent=2))
    elif cmd == "deny":
        import json
        print(json.dumps(SP.deny(arg), ensure_ascii=False, indent=2))
    elif cmd == "check":
        import json
        print(json.dumps(SP.check(arg), ensure_ascii=False, indent=2))
    elif cmd == "attack-on":
        import json
        print(json.dumps(SP.enter_attack_mode(opt("--reason", "detected attack"),
                                              opt("--evidence"),
                                              int(opt("--ttl", "600"))),
                         ensure_ascii=False, indent=2))
    elif cmd == "attack-off":
        import json
        print(json.dumps(SP.exit_attack_mode(opt("--reason")), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
