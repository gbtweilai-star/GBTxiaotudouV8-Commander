# -*- coding: utf-8 -*-
"""atomic-sync · 原子替换器（把「更新文件」收进可自证的唯一动作）

【为什么要有它】
  主人令（2026-11-03 逐字）：「只要是修复代码必须使用原子替换无伤修复」。
  `gbt_allinone/tools/code_patch.py` 是这条令在**能力位**侧的落地（走唯一门、要授权）；
  但**仓库整理**这一侧没有对应的工具 —— 之前都是 `Copy-Item` 直接盖，
  既没有"改前改后"凭据，也不能回滚，还可能在写一半时留下半个文件。

  本工具补这一侧，**照抄 code_patch 的机械闸**（不另立一套口径）。

【机械闸（每条都有牙）】
  1. 目标必须在**仓内**（解析后必须落在 --root 下，默认 = 本文件向上三级）
  2. `patch` 的 `find` 必须**恰好出现一次**：0 次 not_found / >1 次 ambiguous，绝不替你挑
  3. `find != replace`（空改动直接拒）
  4. `put` 必校验**源文件 sha256 == 落盘 sha256**（读完再算一遍，不信"写完就算了"）
  5. **二进制拒 patch**（前 8 KB 有 NUL）—— 二进制走 `put`，不走文本替换
  6. 一律 **tmp + os.replace**（同盘 rename 是原子的；写一半被杀不会留半个目标文件）
  7. 落盘前把目标备份到 `state/atomic-sync/backup/`，回执记 before/after 哈希 ⇒ 可回滚
  8. 默认 `--dry-run`（只看不写），要落盘必须显式 `--apply`

【两条子命令】
  put    整文件原子更新（源代码整份覆盖 / 权重 / 二进制）
  patch  文本定点原子替换（只动 find 那几个字节，CRLF/BOM 一个字节不碰）

【用法】
  python atomic-sync.py put   --src A --dst B [--root R] [--apply]
  python atomic-sync.py patch --file F --find-file f1 --replace-file f2 [--root R] [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]      # <repo>/tools/codex-scripts/x.py → <repo>
BACKUP_REL = Path("state") / "atomic-sync" / "backup"
LEDGER_REL = Path("state") / "atomic-sync" / "ledger.jsonl"
LIKE_REL = Path("state") / "source-pull" / "like.json"
LIKE_TTL = 600          # 一次点赞 10 分钟内有效（对齐攻击模式 TTL 的做法）
PRODUCT_MARK = "payload"  # 路径里出现这一段 = 产品目录（拉取源码的目标）


# ──────────────────────────────────────────────────────────
# 点赞门（2026-11-04 主人令：「设置一个拉取源码要求点赞」）
#
# 与 `security/policy.py` 的既有口径一致：**approve 在 CLI/终端侧执行，agent 不能自批**。
# 所以 `like` 子命令要求 stdin 是真实 TTY；agent 通过管道/重定向调用时会被拒。
# 点赞是一次性的（used 标记），带 TTL，过期作废，全部进 ledger。
# ──────────────────────────────────────────────────────────
def _like_path(root: Path) -> Path:
    return root / LIKE_REL


def like_status(root: Path) -> dict:
    p = _like_path(root)
    if not p.is_file():
        return {"ok": False, "status": "need_like", "error": "还没有点赞"}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "need_like", "error": f"like.json 读不开：{e}"}
    age = time.time() - float(d.get("at") or 0)
    if d.get("used"):
        return {"ok": False, "status": "need_like", "error": "这次点赞已经用掉了"}
    if age > float(d.get("ttl") or LIKE_TTL):
        return {"ok": False, "status": "need_like",
                "error": f"点赞已过期（{int(age)}s > {int(d.get('ttl') or LIKE_TTL)}s）"}
    return {"ok": True, **d, "age": int(age)}


def do_like(root: Path, note: str) -> dict:
    if not sys.stdin.isatty():
        return {"ok": False, "status": "denied",
                "error": "点赞必须在**终端侧**由主人执行（当前 stdin 不是 TTY）。"
                         "本仓既有口径：approve 不能由 agent 自批。"}
    print("即将授权：拉取源码到产品目录。")
    print(f"备注：{note or '（无）'}")
    ans = input("输入 LIKE 确认点赞（其它任何输入=取消）：").strip()
    if ans != "LIKE":
        return {"ok": False, "status": "cancelled", "error": "未点赞"}
    rec = {"at": time.time(), "at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
           "ttl": LIKE_TTL, "note": note, "used": False, "by": os.environ.get("USERNAME") or "?"}
    p = _like_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(p, json.dumps(rec, ensure_ascii=False, indent=1).encode("utf-8"))
    _ledger(root, {"at": rec["at_human"], "op": "like", "note": note, "ttl": LIKE_TTL})
    return {"ok": True, "status": "liked", **rec}


def _consume_like(root: Path, target: Path) -> dict | None:
    """目标是产品目录时，必须有有效点赞；返回 None 表示放行。"""
    if PRODUCT_MARK not in [p.lower() for p in target.parts]:
        return None
    st = like_status(root)
    if st.get("ok"):
        # 一次性：用掉就作废
        p = _like_path(root)
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d["used"] = True
            _atomic_write_bytes(p, json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return None
    return {"ok": False, "status": "need_like",
            "error": st.get("error") or "拉取源码需要先点赞",
            "how": "在主仓终端执行：python tools/codex-scripts/atomic-sync.py like --note \"说明\"",
            "why": "2026-11-04 主人令：拉取源码要求点赞；agent 不得自批"}


def sha256(p: Path, limit: int | None = None) -> str:
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
            n += len(b)
            if limit and n >= limit:
                break
    return h.hexdigest()


def is_binary(p: Path) -> bool:
    with open(p, "rb") as f:
        return b"\x00" in f.read(8192)


def inside(root: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _backup(root: Path, target: Path, stamp: str) -> Path | None:
    if not target.is_file():
        return None
    rel = target.resolve().relative_to(root.resolve())
    b = root / BACKUP_REL / stamp / rel
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, b)
    return b


def _ledger(root: Path, rec: dict) -> None:
    p = root / LEDGER_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".tmp-{os.getpid()}")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)          # 原子
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────
def do_put(src: Path, dst: Path, root: Path, apply: bool) -> dict:
    if not src.is_file():
        return {"ok": False, "status": "needs_input", "error": f"源不存在: {src}"}
    if not inside(root, dst):
        return {"ok": False, "status": "denied", "error": f"目标不在仓内: {dst}"}
    s_sha, s_sz = sha256(src), src.stat().st_size
    old_sha = sha256(dst) if dst.is_file() else None

    if old_sha == s_sha:
        return {"ok": True, "status": "unchanged", "path": str(dst), "sha256": s_sha}

    if not apply:
        return {"ok": True, "status": "dry_run", "path": str(dst), "src": str(src),
                "bytes": s_sz, "before": old_sha, "after": s_sha}

    gate = _consume_like(DEFAULT_ROOT, dst)          # 点赞门（只在真正写盘时拦）
    if gate:
        return gate

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = _backup(root, dst, stamp)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + f".tmp-{os.getpid()}")
    try:
        with open(src, "rb") as fi, open(tmp, "wb") as fo:
            shutil.copyfileobj(fi, fo, 1 << 22)
            fo.flush()
            os.fsync(fo.fileno())
        new_sha = sha256(tmp)
        if new_sha != s_sha:                       # 闸 4：不信"写完就算了"
            return {"ok": False, "status": "failed",
                    "error": f"落盘哈希与源不一致 {new_sha[:16]} != {s_sha[:16]}"}
        os.replace(tmp, dst)                       # 闸 6：原子
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    rec = {"at": stamp, "op": "put", "path": str(dst), "bytes": s_sz,
           "before": old_sha, "after": s_sha, "backup": str(bak) if bak else None}
    _ledger(root, rec)
    return {"ok": True, "status": "applied", **{k: rec[k] for k in ("path", "bytes", "before", "after")}}


def do_patch(target: Path, find: bytes, replace: bytes, root: Path, apply: bool) -> dict:
    if not target.is_file():
        return {"ok": False, "status": "needs_input", "error": f"目标不存在: {target}"}
    if not inside(root, target):
        return {"ok": False, "status": "denied", "error": f"目标不在仓内: {target}"}
    if is_binary(target):                          # 闸 5
        return {"ok": False, "status": "denied",
                "error": "二进制文件拒 patch（走 put）"}
    if find == replace:                            # 闸 3
        return {"ok": False, "status": "denied", "error": "find 与 replace 相同（空改动）"}

    raw = target.read_bytes()
    n = raw.count(find)
    if n == 0:                                     # 闸 2
        return {"ok": False, "status": "not_found", "error": "find 在目标里出现 0 次"}
    if n > 1:                                      # 闸 2
        return {"ok": False, "status": "ambiguous",
                "error": f"find 出现 {n} 次，绝不替你挑一个"}

    before_sha = hashlib.sha256(raw).hexdigest()
    new_raw = raw.replace(find, replace, 1)
    after_sha = hashlib.sha256(new_raw).hexdigest()

    if not apply:
        return {"ok": True, "status": "dry_run", "path": str(target),
                "occurrences": n, "before": before_sha[:16], "after": after_sha[:16],
                "delta_bytes": len(new_raw) - len(raw)}

    gate = _consume_like(DEFAULT_ROOT, target)      # 点赞门（只在真正写盘时拦）
    if gate:
        return gate

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = _backup(root, target, stamp)
    _atomic_write_bytes(target, new_raw)
    if sha256(target) != after_sha:
        return {"ok": False, "status": "failed", "error": "落盘哈希与预期不一致"}

    rec = {"at": stamp, "op": "patch", "path": str(target),
           "before": before_sha, "after": after_sha,
           "find_sha": hashlib.sha256(find).hexdigest()[:16],
           "delta_bytes": len(new_raw) - len(raw),
           "backup": str(bak) if bak else None}
    _ledger(root, rec)
    return {"ok": True, "status": "applied", "path": str(target),
            "before": before_sha[:16], "after": after_sha[:16],
            "delta_bytes": len(new_raw) - len(raw), "backup": str(bak) if bak else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="原子替换器（put / patch / like）")
    ap.add_argument("cmd", choices=["put", "patch", "like"])
    ap.add_argument("--src")
    ap.add_argument("--dst")
    ap.add_argument("--file")
    ap.add_argument("--find-file")
    ap.add_argument("--replace-file")
    ap.add_argument("--note", default="", help="like 的备注")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--apply", action="store_true", help="不带则 dry-run")
    a = ap.parse_args(argv)

    root = Path(a.root)
    if a.cmd == "like":
        r = do_like(DEFAULT_ROOT, a.note)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a.cmd == "put":
        if not (a.src and a.dst):
            print("put 需要 --src --dst"); return 2
        r = do_put(Path(a.src), Path(a.dst), root, a.apply)
    else:
        if not (a.file and a.find_file and a.replace_file):
            print("patch 需要 --file --find-file --replace-file"); return 2
        find = Path(a.find_file).read_bytes()
        rep = Path(a.replace_file).read_bytes()
        r = do_patch(Path(a.file), find, rep, root, a.apply)

    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
