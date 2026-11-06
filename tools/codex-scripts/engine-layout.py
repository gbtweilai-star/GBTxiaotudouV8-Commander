# -*- coding: utf-8 -*-
r"""引擎布局体检：给一个根目录，如实报「exe / 聊天模板 / 权重」三样找不找得到。

    .\pyembed\python.exe tools\codex-scripts\engine-layout.py
    .\pyembed\python.exe tools\codex-scripts\engine-layout.py "D:\GBT-builds\GBT小土豆V8桌面版\payload"

为什么要它（2026-11-06 血账）：`commander` 原先只认开发仓布局（exe 与模板都在
`vendor/llama/`），打包版把它们放在 `tools/llama/` ⇒ 打包版报「没有 exe」起不来，
而且模板缺失时引擎会退回 GGUF 内置 Qwen 模板、顶着别人名字说话。
这两处已改成「两处都扫」，本工具就是那条口径的现场读数。

只读：不写盘、不起进程、不加载权重。
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    if not (root / "gbt_allinone").is_dir():
        print("❌ %s 不是可运行的仓/包目录（缺 gbt_allinone/）" % root)
        return 2
    sys.path.insert(0, str(root))
    from gbt_allinone.tentacle import commander as C

    C.ROOT = root
    C.WEIGHTS_DIR = root / "state" / "weights"
    C.ACTIVE_JSON = C.WEIGHTS_DIR / "ACTIVE.json"

    eng = C._engine_bin()
    w = C.weights()
    tpl = C._chat_template(eng.get("path")) if eng.get("ok") else None

    print("根目录   : %s" % root)
    print("引擎 exe : %s" % ("✅ " + str(eng.get("path")) + "（" + str(eng.get("source")) + "）"
                          if eng.get("ok") else "❌ " + str(eng.get("reason"))))
    print("聊天模板 : %s" % ("✅ " + str(tpl) if tpl else
                          "❌ 没找到 gbt-user-assistant.jinja —— 引擎会用 GGUF 内置模板"
                          "（可能顶着别人名字说话）"))
    print("权重     : %s" % ("✅ %s · %.2f GB · %s" % (w.get("name"), w.get("size_gb") or 0, w.get("source"))
                          if w.get("ok") else "❌ " + str(w.get("reason"))))
    bad = [n for n, ok in (("exe", eng.get("ok")), ("模板", bool(tpl)), ("权重", w.get("ok"))) if not ok]
    if bad:
        print("\n结论：缺 %s —— 起来也跑不对，先补齐再启动。" % "、".join(bad))
        return 1
    print("\n结论：三样齐活。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
