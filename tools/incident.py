"""GBT小土豆V8 · 受攻击响应（合法反制 CLI）

用法：
  python tools/incident.py collect --agents 32          # 极限并发取证（本机只读）
  python tools/incident.py reclaim --apply              # 回收我们自己的非必需进程
  python tools/incident.py respond --reason "被扫描" --evidence "日志" --apply
  python tools/incident.py counterstrike --op power_off # ← 会被拒绝（黑客反击非法）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import attack_forensics as AF  # noqa: E402


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]

    def opt(name, default=""):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return default

    if cmd == "collect":
        out = AF.collect(agents=int(opt("--agents", "32")))
    elif cmd == "reclaim":
        out = AF.reclaim_own_workers(apply="--apply" in argv)
    elif cmd == "respond":
        out = AF.respond(opt("--reason", "detected attack"), opt("--evidence"),
                         int(opt("--agents", "32")), int(opt("--ttl", "600")),
                         reclaim="--apply" in argv)
    elif cmd == "counterstrike":
        out = AF.counterstrike(opt("--op"))
    else:
        print(__doc__)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
