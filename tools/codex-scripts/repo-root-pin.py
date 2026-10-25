# -*- coding: utf-8 -*-
r"""把**仓根**钉到大家都知道的地方（repo-root-pin）—— 让**打包态**的壳能认家。

主人截图暴露的真故障（2026-10-10）：上帝视角「看任务 / 看账本」全 ENOENT，读的是
  C:\Users\ADMIN\AppData\Local\gbt_allinone\store\...
而真账本在**仓里**的 gbt_allinone/store/ 与 state/。

根因：便携版运行时解包到 %TEMP%\<hash>\resources\app\shell ⇒ 壳从那儿往上走 12 层
**永远走不到桌面** ⇒ ROOT=null ⇒ 路径回落到 userData（那里当然没有真账本）。

修法（两半，本件是仓这一半）：**仓把自己的根写进指针文件**，壳那边 findRepoRoot 读它
（见 holo_pet_w3/shell/main.cjs 的三级兜底：环境变量 → 指针文件 → 常见位置）。

写哪几处（都写，写成功几处报几处；一处都写不成就原样报错，不静默）：
  · %LOCALAPPDATA%\gbt_allinone\repo-root.txt   （壳的 userData 常在这里）
  · %APPDATA%\gbt_allinone\repo-root.txt
判据：写完后**再读回来核对**（写了但读不回 = 没写成）。
用法：py -3.14 -X utf8 tools/codex-scripts/repo-root-pin.py [--check]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
MARK = ROOT / "gbt_allinone" / "caps_registry.py"
SPOTS = [Path(os.environ.get("LOCALAPPDATA", "")) / "gbt_allinone",
         Path(os.environ.get("APPDATA", "")) / "gbt_allinone"]


def pin() -> dict:
    if not MARK.is_file():
        return {"ok": False, "why": "本件不在仓里（认不到 gbt_allinone/caps_registry.py）：%s" % MARK}
    wrote, failed = [], []
    for d in SPOTS:
        if not str(d) or str(d) == ".":
            continue
        try:
            d.mkdir(parents=True, exist_ok=True)
            f = d / "repo-root.txt"
            f.write_text(str(ROOT) + "\n", encoding="utf-8")
            back = f.read_text(encoding="utf-8").strip()          # 写完**读回来核对**
            (wrote if back == str(ROOT) else failed).append(str(f))
        except OSError as exc:
            failed.append("%s（%s）" % (d, exc))
    return {"ok": bool(wrote), "仓根": str(ROOT), "写了": wrote, "没写成": failed}


def check() -> int:
    r = pin()
    print("仓根 = %s" % r["仓根"])
    for w in r["写了"]:
        print("  ✅ 已钉（并读回核对通过）：%s" % w)
    for f in r["没写成"]:
        print("  ❌ 没写成：%s" % f)
    print("\n判据：%s" % ("PASS" if r["ok"] else "FAIL（一处都没写成 ⇒ 打包态仍认不到家）"))
    return 0 if r["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="把仓根钉到大家都知道的地方")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    r = pin()
    print("已钉仓根 %s → %d 处" % (r["仓根"], len(r["写了"])))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
