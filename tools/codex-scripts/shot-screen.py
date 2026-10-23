# -*- coding: utf-8 -*-
"""用触手之眼截屏 —— **走能力位**（`tentacle {"action":"see"}` → run_task 唯一门）。

为什么要做成工具、不每次内联：
  ① 内联要写一大串 base64 的胶水，容易出错；
  ② 更重要的：**动作要表达成能力位再走 run_task**，否则 `ruler` 的 `brainless_ratio`
     根本量不到这次动作（这是 Owner 点出的 ruler 盲区）。

用法：
    python tools/codex-scripts/shot-screen.py [输出路径] [--json]
    # 默认输出 .scratch/_screen.png
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
DEFAULT_OUT = ROOT / ".scratch" / "_screen.png"


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    out = Path(args[0]) if args else DEFAULT_OUT
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    # 走能力位（唯一门 run_task）——不直接 import 触手内部函数
    import gbt_allinone as g
    r = g.run_task("tentacle", {"action": "see"})
    body = (r.get("gbt_result") or {})
    res = body.get("result") or {}
    b64 = res.get("image_base64")
    if not b64:
        print(json.dumps({"ok": False, "why": "能力位没回 image_base64",
                          "raw_keys": list(res.keys())[:10],
                          "status": body.get("status")}, ensure_ascii=False, indent=1))
        return 1
    data = base64.b64decode(b64)
    # 🔴 扩展名必须跟**真实字节**一致：能力位回的是 jpeg，第一版却默认写 `.png`，
    # 于是读图工具直接拒（"扩展名声明 png，字节是别的格式"）——自作聪明的命名等于坏文件。
    fmt = str(res.get("fmt") or "").lower()
    canon = {"jpeg": ".jpg", "jpg": ".jpg", "png": ".png", "webp": ".webp"}.get(fmt)
    if canon:
        cur = out.suffix.lower()
        same = (cur == canon) or (canon == ".jpg" and cur == ".jpeg")
        if not same:
            out = out.with_suffix(canon)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    info = {"ok": True, "path": str(out.relative_to(ROOT)), "bytes": len(data),
            "size": res.get("size"), "fmt": res.get("fmt"),
            "gate": "run_task", "kind": "tentacle", "stamp": bool(r.get("gbt_stamp"))}
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
