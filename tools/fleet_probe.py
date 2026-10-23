# gbt-capability: tentacle_fleet
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""触手舰队的**内置探针**（固定代码 · 不起任何外部进程 · 只证隔离）。

它做的事只有四件，全部是**自证**：
  1. 报自己的身份：触手 id、专属端口、当前工作目录、解释器路径；
  2. **证工作区隔离**：打印的 cwd 必须等于自己的 worktree（逐字符比）；
  3. **证身份隔离**：打印 HOME/USERPROFILE/XDG_CONFIG_HOME，以及自己的匿名
     `.freebuff/project-id` 是不是在**自己的**工作区里；
  4. **证端口隔离**：真去 bind 自己的端口 —— 成功＝这段端口本触手独占；失败＝有人占了（如实报）。

用法（由舰队编排器生成的启动指令调用，人手也可以直接跑）：
  python tools/fleet_probe.py <触手id> <端口> <工作区>
环境变量 `GBT_FLEET_HOLD`（默认 6 秒）决定它在岗多久 —— 便于看板看到"在跑"。
"""
from __future__ import annotations

import os
import pathlib
import socket
import sys
import time


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("用法：python tools/fleet_probe.py <触手id> <端口> <工作区>")
        return 2
    wid, port, ws = argv[1], int(argv[2]), pathlib.Path(argv[3]).resolve()
    cwd = pathlib.Path.cwd().resolve()
    print(f"[probe] 触手 {wid} · 端口 {port}", flush=True)
    print(f"[probe] 解释器 {sys.executable}", flush=True)
    print(f"[probe] cwd {cwd}", flush=True)
    same = (cwd == ws)
    print(f"[probe] 工作区隔离：cwd {'==' if same else '!='} 自己的 worktree "
          f"⇒ {'✅ 隔离成立' if same else '🔴 没在隔离工作区里'}", flush=True)
    print(f"[probe] HOME={os.environ.get('HOME')}", flush=True)
    print(f"[probe] USERPROFILE={os.environ.get('USERPROFILE')}", flush=True)
    print(f"[probe] XDG_CONFIG_HOME={os.environ.get('XDG_CONFIG_HOME')}", flush=True)
    idf = cwd / ".freebuff" / "project-id"
    if idf.is_file():
        print(f"[probe] 我的匿名身份 {idf.read_text(encoding='utf-8').strip()}"
              f"（文件在**我自己的工作区**里：{idf}）", flush=True)
    else:
        print("[probe] 🔴 没读到自己的身份文件 .freebuff/project-id", flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            s.listen(1)
            print(f"[probe] 端口隔离：{port} 独占 bind 成功 ⇒ ✅ 这段端口归我", flush=True)
            hold = int(os.environ.get("GBT_FLEET_HOLD", "6") or 6)
            print(f"[probe] 在岗 {hold} 秒（看板可看到「在听」）", flush=True)
            end = time.time() + hold
            s.settimeout(0.5)
            while time.time() < end:
                try:
                    s.accept()
                except (socket.timeout, OSError):
                    pass
        except OSError as e:
            print(f"[probe] 🔴 端口 {port} 被占：{e}", flush=True)
    print("[probe] 收工", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
