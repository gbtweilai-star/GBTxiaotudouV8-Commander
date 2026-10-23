# -*- coding: utf-8 -*-
"""实探 AI朋友圈（EigenFlux）能不能连：CLI 在不在、登没登、feed/friends 取不取得到。只读。"""
import shutil
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

print("=" * 84)
print("① CLI 在不在 PATH 上")
print("=" * 84)
for exe in ("eigenflux", "eigenflux.exe", "eigenflux.cmd", "ef"):
    p = shutil.which(exe)
    print("  %-16s %s" % (exe, p or "（PATH 上找不到）"))

print("\n" + "=" * 84)
print("② 走 potato_pet 的适配器问它（它自己会挑 CLI 或退回本地缓存）")
print("=" * 84)
try:
    from potato_pet.eigenflux_client import EigenFluxClient
    c = EigenFluxClient()
    print("  已安装 installed :", c.installed())
    print("  已登录 authenticated :", c.authenticated())
    for name in ("status", "profile", "friends", "feed"):
        try:
            v = getattr(c, name)()
            s = str(v)
            print("  %-9s → %s" % (name, s[:220].replace("\n", " ")))
        except Exception as e:  # noqa: BLE001
            print("  %-9s → 抛错 %s: %s" % (name, type(e).__name__, str(e)[:150]))
except Exception as e:  # noqa: BLE001
    print("  适配器导入失败: %s: %s" % (type(e).__name__, str(e)[:200]))

print("\n" + "=" * 84)
print("③ 本地有没有 EigenFlux 的配置/缓存")
print("=" * 84)
homes = [Path.home() / ".eigenflux", Path.home() / ".ef", Path.home() / ".config" / "eigenflux",
         BASE / ".eigenflux", BASE / "potato_pet" / ".eigenflux"]
for h in homes:
    if h.exists():
        print("  ✓", h)
        for f in list(h.rglob("*"))[:12]:
            print("      ", f.relative_to(h))
    else:
        print("  ×", h)
