#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""云数据仓（无限扩容 · 按触手根数扩 · 目标 32 GB）

## 它是什么 / 不是什么（先钉死，免得被读成"内存变大了"）
- ✅ **容量**方案：本地放不下的东西（帧缓存/代理/中间产物/大素材）spill 到云端（Cloudflare R2），
     逻辑容量按**触手根数**扩，总量封顶 **32 GB**（主人给的目标 = 这台机的主板上限）。
- ❌ **不是速度**方案：云端取数延迟**毫秒~秒级**，替代不了**纳秒级**的内存。
     ⇒ 它让**装得下**，不让**跑得快**。别念成"32 GB 内存"。
     依据：本机页面文件峰值 **12,727 MB** ＞ 物理 **8 GB**（换页已在发生）；
           Remotion 默认并发 **6×**（并发=内存放大器）。云仓缓解"爆"与"盘不够"。

## 🔴 搬运与校验**委托**给已验证的 `r2-move.py`（不自己造更弱的）
本仓的 `r2-move.py` 自带三条我要的规矩，而且**逐字节验过**：
  · 字节级回验、**对不上不删**；· **>300 MiB 自动分片**；· `verify` **不落盘**。
（教训出处：F18 `wrangler` 默认走本地模拟却打印 Upload complete；F20 300 MiB 硬上限；
  F19 解码报错被当成成功。自己再写一遍只会更弱 —— 所以这里只做编排与登记。）

## 容量模型
    slab_per_tentacle = target_gb / tentacles        （每根触手分到多少）
    逻辑容量          = min(tentacles × slab, target_gb)
`--tentacles` 缺省取**实测**（CPU 线程数 = Remotion 取并发的同一把尺）。

用法：
    py -3.14 tools/codex-scripts/cloud-vault.py plan [--tentacles N] [--target-gb 32]
    py -3.14 tools/codex-scripts/cloud-vault.py put  <本地文件> [--key K] [--keep]
    py -3.14 tools/codex-scripts/cloud-vault.py get  <云上键> <本地路径>
    py -3.14 tools/codex-scripts/cloud-vault.py stat
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
R2MOVE = ROOT / "tools" / "codex-scripts" / "r2-move.py"
PY = [sys.executable]
BUCKET = os.environ.get("GBT_VAULT_BUCKET", "gbt-bigfiles")
STATE = ROOT / "state" / "cloud-vault.jsonl"


def sha256_file(p: pathlib.Path, buf: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(buf), b""):
            h.update(chunk)
    return h.hexdigest()


def _r2move(*args: str) -> tuple[int, str]:
    r = subprocess.run(PY + [str(R2MOVE), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _registry() -> list:
    rows = []
    if STATE.exists():
        for ln in STATE.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    return rows


def cmd_plan(a) -> int:
    tent = a.tentacles or (os.cpu_count() or 1)
    target = float(a.target_gb)
    slab = target / tent
    used = sum(r.get("bytes", 0) for r in _registry()) / 2 ** 30
    print(json.dumps({
        "口径": "容量方案，不是速度方案（云端延迟毫秒~秒级，替代不了内存）",
        "bucket": BUCKET, "搬运与校验": "委托 r2-move.py（字节级回验 / 对不上不删 / >300MiB 分片）",
        "触手根数": tent, "每根触手配额 GB": round(slab, 2),
        "逻辑容量 GB": round(min(tent * slab, target), 2), "目标上限 GB": target,
        "已登记占用 GB": round(used, 3), "剩余 GB": round(target - used, 2),
        "真机参照": {"物理内存 GB": 7.39, "页面文件峰值 MB": 12727,
                     "Remotion 默认并发": "6x（并发=内存放大器）"},
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_put(a) -> int:
    src = pathlib.Path(a.file)
    if not src.is_file():
        print(json.dumps({"ok": False, "why": "本地文件不存在", "file": str(src)},
                         ensure_ascii=False))
        return 2
    key = a.key or src.name
    size = src.stat().st_size
    digest = sha256_file(src)
    rc, out = _r2move("put", str(src), "--key", key)
    if rc != 0:
        print(json.dumps({"ok": False, "why": "r2-move put 非零退出", "rc": rc,
                          "tail": out[-400:]}, ensure_ascii=False))
        return 3
    # 🔴 不落盘的字节级校验（r2-move verify）；对不上就**不删本地**
    rc2, out2 = _r2move("verify", key, "--sha256", digest, "--bytes", str(size))
    ok = (rc2 == 0)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "key": key, "bytes": size,
           "sha256": digest, "verified": ok, "kept_local": bool(a.keep)}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if ok and not a.keep:
        src.unlink()
    print(json.dumps({"ok": ok, "key": key, "bytes": size, "sha256_前16": digest[:16],
                      "远端校验": "通过" if ok else "🔴 不通过（本地未删）",
                      "本地已删": bool(ok and not a.keep),
                      "put_tail": out[-160:], "verify_tail": out2[-200:]},
                     ensure_ascii=False, indent=1))
    return 0 if ok else 4


def cmd_get(a) -> int:
    want = None
    for r in _registry():
        if r.get("key") == a.key:
            want = r
    args = ["download", a.key, "--to", a.out]
    if want:
        args += ["--sha256", want["sha256"], "--bytes", str(want["bytes"])]
    rc, out = _r2move(*args)
    got = sha256_file(pathlib.Path(a.out)) if pathlib.Path(a.out).exists() else None
    same = (want is None) or (got == want["sha256"])
    print(json.dumps({"ok": (rc == 0 and same), "rc": rc, "out": a.out,
                      "sha256_前16": (got or "")[:16],
                      "与登记一致": (None if want is None else same),
                      "tail": out[-200:]}, ensure_ascii=False, indent=1))
    return 0 if (rc == 0 and same) else 5


def cmd_stat(a) -> int:
    rc, out = _r2move("list-buckets")
    rows = _registry()
    print(json.dumps({"bucket": BUCKET, "list_rc": rc,
                      "登记条数": len(rows),
                      "登记总字节": sum(r.get("bytes", 0) for r in rows),
                      "校验通过的条数": sum(1 for r in rows if r.get("verified")),
                      "tail": out[-300:]}, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="云数据仓（容量方案；非速度方案）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("plan")
    p1.add_argument("--tentacles", type=int, default=0)
    p1.add_argument("--target-gb", type=float, default=32.0)
    p1.set_defaults(func=cmd_plan)
    p2 = sub.add_parser("put")
    p2.add_argument("file")
    p2.add_argument("--key", default="")
    p2.add_argument("--keep", action="store_true", help="上传校验后保留本地（默认删）")
    p2.set_defaults(func=cmd_put)
    p3 = sub.add_parser("get")
    p3.add_argument("key")
    p3.add_argument("out")
    p3.set_defaults(func=cmd_get)
    p4 = sub.add_parser("stat")
    p4.set_defaults(func=cmd_stat)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
