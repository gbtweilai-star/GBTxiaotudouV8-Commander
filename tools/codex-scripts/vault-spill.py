#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""云仓 spill 编排器：把本地大件推上云、**本地释放**、需要时拉回并逐字节验。

## 为什么要有它（而不是手敲 cloud-vault put）
主人要的是「**自动化长视频**」⇒ spill 必须是**一条能跑进流水线的命令**，
而不是每次人工挑文件。本工具负责：挑件 → 走云仓（字节级校验）→ 只在**验过之后**才删本地 → 记账。

## 三条硬规矩（沿用本仓教训）
1. **只在远端校验通过后才删本地**（`对不上不删`，来自 r2-move 的语义）。
2. **删之前先写账**（`state/cloud-vault.jsonl` 由 cloud-vault 落），账写不进去就不删。
3. **`--dry-run` 默认先看**：把"要搬什么、能腾多少"先摆出来，真搬要显式 `--apply`。

用法：
    py -3.14 tools/codex-scripts/vault-spill.py scan  <目录> [--min-mb 20] [--top 20]
    py -3.14 tools/codex-scripts/vault-spill.py spill <目录> [--min-mb 20] [--limit 3] --apply
    py -3.14 tools/codex-scripts/vault-spill.py restore <云上键> <本地路径>
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
VAULT = ROOT / "tools" / "codex-scripts" / "cloud-vault.py"
PY = [sys.executable]
KEY_PREFIX = "spill"


def _vault(*args: str) -> tuple[int, str]:
    r = subprocess.run(PY + [str(VAULT), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _free_gb() -> float:
    try:
        import shutil
        return shutil.disk_usage(str(ROOT)).free / 2 ** 30
    except Exception:
        return -1.0


def _candidates(d: pathlib.Path, min_mb: float) -> list:
    out = []
    for p in d.rglob("*"):
        try:
            if p.is_file() and p.stat().st_size >= min_mb * 2 ** 20:
                out.append(p)
        except OSError:
            continue
    out.sort(key=lambda x: -x.stat().st_size)
    return out


def cmd_scan(a) -> int:
    d = pathlib.Path(a.dir)
    if not d.is_dir():
        print(json.dumps({"ok": False, "why": "目录不存在", "dir": str(d)}, ensure_ascii=False))
        return 2
    cand = _candidates(d, a.min_mb)[: a.top]
    total = sum(p.stat().st_size for p in cand)
    print(json.dumps({
        "dir": str(d.relative_to(ROOT)) if str(d).startswith(str(ROOT)) else str(d),
        "门槛 MB": a.min_mb, "命中件数": len(cand),
        "合计 MB": round(total / 2 ** 20, 1),
        "本地可用 GB": round(_free_gb(), 2),
        "清单": [{"M": round(p.stat().st_size / 2 ** 20, 1),
                "p": str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p)}
               for p in cand],
        "口径": "本命令**只读**，不搬不删",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_spill(a) -> int:
    d = pathlib.Path(a.dir)
    cand = _candidates(d, a.min_mb)[: a.limit]
    if not cand:
        print(json.dumps({"ok": True, "why": "没有达到门槛的件", "门槛 MB": a.min_mb},
                         ensure_ascii=False))
        return 0
    before = _free_gb()
    rows, freed = [], 0
    for p in cand:
        # 🔴 必须在调用**之前**取 size：cloud-vault put 成功后会**删掉本地**，
        #    之后再 p.stat() 就是 FileNotFoundError —— 我第一次就是这么崩的
        #    （而 C 盘 +140 MB 说明搬运其实成功了：**量具坏，不是被测对象坏**）。
        size = p.stat().st_size
        rel = str(p.relative_to(ROOT)).replace("\\", "/") if str(p).startswith(str(ROOT)) else p.name
        key = "%s/%s" % (KEY_PREFIX, rel)
        if not a.apply:
            rows.append({"dry_run": True, "M": round(size / 2 ** 20, 1), "key": key})
            continue
        rc, out = _vault("put", str(p), "--key", key)      # 云仓：上传 + 远端字节级校验 + 删本地
        ok = (rc == 0) and ('"ok": true' in out)
        if ok:
            freed += size
        rows.append({"key": key, "M": round(size / 2 ** 20, 1),
                     "ok": ok, "rc": rc,
                     "tail": out[-200:] if not ok else "远端校验通过，本地已释放"})
    after = _free_gb()
    print(json.dumps({
        "apply": bool(a.apply), "件数": len(rows),
        "腾出 MB": round(freed / 2 ** 20, 1),
        "本地可用 GB": {"前": round(before, 2), "后": round(after, 2),
                    "差": round(after - before, 2)},
        "明细": rows,
        "账": "state/cloud-vault.jsonl（cloud-vault 落；写不进就不删）",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_restore(a) -> int:
    rc, out = _vault("get", a.key, a.out)
    print(json.dumps({"rc": rc, "key": a.key, "out": a.out, "tail": out[-300:]},
                     ensure_ascii=False, indent=1))
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="云仓 spill 编排器")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("dir")
    s.add_argument("--min-mb", type=float, default=20.0)
    s.add_argument("--top", type=int, default=20)
    s.set_defaults(func=cmd_scan)
    s2 = sub.add_parser("spill")
    s2.add_argument("dir")
    s2.add_argument("--min-mb", type=float, default=20.0)
    s2.add_argument("--limit", type=int, default=3)
    s2.add_argument("--apply", action="store_true", help="真搬（缺省只预演）")
    s2.set_defaults(func=cmd_spill)
    s3 = sub.add_parser("restore")
    s3.add_argument("key")
    s3.add_argument("out")
    s3.set_defaults(func=cmd_restore)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
