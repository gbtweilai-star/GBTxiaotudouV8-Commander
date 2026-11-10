# -*- coding: utf-8 -*-
"""把 plugins/dsh 打成 npm 标准 tarball（`package/` 前缀），供 dpx plugin add 直接装。

为什么要自己打包：她的 AGENTS.md 明确「profile 插件树由 pnpm 安装，别手塞 node_modules」，
而 `dpx plugin add <tarball>` 是官方入口。这里只产出一个文件，不安装、不碰她的环境。
"""
from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = ["package.json", "plugin.mjs", "cordis.patch.yml", "README.md",
         "bridge/gbt_bridge.py"]
MTIME = 1762700000   # 固定时间戳 ⇒ 同内容同哈希，便于核对


def main() -> int:
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    version = pkg["version"]
    dist = ROOT / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / ("gbt-dsh-cap-bridge-%s.tgz" % version)
    with tarfile.open(out, "w:gz") as tar:
        for rel in FILES:
            src = ROOT / rel
            data = src.read_bytes()
            info = tarfile.TarInfo("package/" + rel.replace("\\", "/"))
            info.size = len(data)
            info.mtime = MTIME
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))
    with tarfile.open(out, "r:gz") as tar:
        names = tar.getnames()
    print(json.dumps({"ok": True, "tarball": str(out), "bytes": out.stat().st_size,
                      "members": names}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
