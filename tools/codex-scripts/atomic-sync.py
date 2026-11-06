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
  7. 落盘前把目标备份到 `state/atomic-sync/backup/`，回执记 before/after 哈希 -> 可回滚
  8. 默认 `--dry-run`（只看不写），要落盘必须显式 `--apply`

【六条子命令】
  put        整文件原子更新（源代码整份覆盖 / 权重 / 二进制）
  patch      文本定点原子替换（只动 find 那几个字节，CRLF/BOM 一个字节不碰）
  manifest   把一批「相对路径」编成清单（带每个文件的 sha256），只写清单、不碰产品目录
  put-batch  按清单批量原子更新：**一次点赞只对一份清单有效**（清单指纹绑定）
  policy     把风险分级规则摆到台面上（哪些自决、哪些要终端 YES；可配 --paths-file 试算）

【分级闸（2026-11-06 主人令）】
  只有 danger（危险件）与 finance（资金件）要终端 LIKE；
  normal（文档/技能/素材/普通代码）由 GBT 自行决策，并落 auto_approve 账。

【批量门（2026-11-06 主人令：一次 LIKE 授权一批，但必须锁死是哪一批）】
  · `like --manifest M` 会把 sha256(M) 写进 like.json；`put-batch` 只认**同一份清单**
  · 清单里每个文件都带 sha256：源在点赞之后被改过，整批拒写（一个都不写，不是写一半）
  · 仍然是一次性 + TTL 600s + 真实 TTY + 全落账；单文件 put 不能挪用清单点赞

【用法】
  python atomic-sync.py put   --src A --dst B [--root R] [--apply]
  python atomic-sync.py patch --file F --find-file f1 --replace-file f2 [--root R] [--apply]
  python atomic-sync.py manifest  --src-root D --dst-root P --paths-file L --out M
  python atomic-sync.py like      --manifest M --note "说明"
  python atomic-sync.py put-batch --manifest M --root P [--apply]
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
# 风险分级闸（2026-11-06 主人令，逐字）：
#   「我们权重大模型和APP只有危险能力使用和资金转账需要终端YES
#     其他的GBT小土豆V8就可以自行决策不需要人工」
#
# 口径：拉取源码到产品目录**不再一律要 LIKE** —— 只有危险件与资金件要。
#   danger  可执行载体（.exe/.dll/.ps1/.bat/.cjs…）、授权门与审计本体、系统自启位置
#   finance 转账/付款/钱包/账单类路径
#   normal  其余（文档 / 技能 / 面板素材 / 普通 .py .json .md）
#
# 三条硬纪律：
#   1. 判不准 -> 升到 danger（fail closed）：分类器出错只会多要票，不会少要票；
#   2. 一批里只要有一个 danger/finance -> **整批**要 LIKE，不拆开偷偷放行；
#   3. 自改门也要票：本文件、policy/auth_gate/caps_registry 都在 danger 白名单里。
#
# 旧行为（每件都要票）：设 GBT_SYNC_STRICT=1。
# ──────────────────────────────────────────────────────────
TIER_NORMAL, TIER_DANGER, TIER_FINANCE = "normal", "danger", "finance"
_TIER_RANK = {TIER_NORMAL: 0, TIER_DANGER: 1, TIER_FINANCE: 2}

FINANCE_MARKERS = (
    "transfer", "payment", "payout", "wallet", "billing", "invoice", "checkout",
    "cashier", "remittance",
    "转账", "汇款", "付款", "收款", "账单", "余额", "银行卡", "资金",
)

DANGER_PATH_SUFFIXES = (
    "/gbt_allinone/api.py",                  # 唯一门
    "/gbt_allinone/auth_gate.py",            # 授权闸
    "/gbt_allinone/caps_registry.py",        # 427 能力契约
    "/tools/codex-scripts/atomic-sync.py",   # 本工具（自改门）
    "/tools/codex-scripts/auth-grant.py",
    "/tools/codex-scripts/guard-three.py",
    "/tools/codex-scripts/guardrail-check.py",
    "/state/source-pull/like.json",
    "/state/atomic-sync/ledger.jsonl",
    "/state/auth_grants.jsonl",
    "/store/auth_grants.jsonl",
    # ── 2026-11-06 反向审计补洞：这些不是"配置"，是**任意代码执行** ──
    "/gbt_allinone/tentacle/autonomy.py",       # 自主契约本体（改它就能自授权）
    "/gbt_allinone/tools/action_gate.py",       # 动作闸
    "/gbt_allinone/tools/capability_gateway.py",
    "/package.json",                            # 依赖安装会跑 postinstall 脚本
)
DANGER_PATH_PARTS = (
    "/gbt_allinone/security/",               # policy / 护栏整目录
    "/holo_pet_w3/shell/",                   # Electron 主进程（能起子进程）
    "/windows/", "/system32/",               # 系统目录
    "/start menu/programs/startup/",         # 自启
    # ── 同上：解释器/依赖/审计库/钩子，改任一都是执行面 ──
    "/pyembed/",                             # 解释器 + site-packages（.pth 也能注入）
    "/node_modules/",                        # npm 生命周期脚本
    "/gbt_allinone/store/",                  # 审计与授权库
    "/.git/hooks/",                          # git 钩子会执行
)
DANGER_EXT = {
    ".exe", ".dll", ".msi", ".msix", ".com", ".scr", ".sys", ".drv",
    ".pyd", ".so", ".dylib", ".jar", ".apk", ".node",
    ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".jse", ".wsf",
    ".hta", ".reg", ".lnk", ".cjs", ".pth", ".sh", ".pyz",
}


def _bump(tier: str, new: str) -> str:
    return new if _TIER_RANK[new] > _TIER_RANK[tier] else tier


def _rel_of(root: Path, target: Path) -> str:
    try:
        return "/" + str(target.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:  # noqa: BLE001
        return "/" + str(target).replace("\\", "/")


def classify_rel(rel: str) -> dict:
    """给一条相对路径定级。判不准就 danger（fail closed）。"""
    r = "/" + str(rel or "").replace("\\", "/").strip("/")
    low = r.lower()
    hits = []
    tier = TIER_NORMAL
    for w in FINANCE_MARKERS:
        if w in low:
            hits.append("资金关键词:" + w)
            tier = _bump(tier, TIER_FINANCE)
    for suf in DANGER_PATH_SUFFIXES:
        if low.endswith(suf):
            hits.append("授权/审计本体:" + suf)
            tier = _bump(tier, TIER_DANGER)
    for part in DANGER_PATH_PARTS:
        if part in low:
            hits.append("危险位置:" + part)
            tier = _bump(tier, TIER_DANGER)
    ext = os.path.splitext(low)[1]
    if ext in DANGER_EXT:
        hits.append("可执行载体:" + ext)
        tier = _bump(tier, TIER_DANGER)
    return {"tier": tier, "rel": r, "reasons": hits}


def classify_many(rels) -> dict:
    """一批路径的唯一结论：取最严的那一级。"""
    counts = {TIER_NORMAL: 0, TIER_DANGER: 0, TIER_FINANCE: 0}
    manual, worst = [], TIER_NORMAL
    for rel in rels:
        d = classify_rel(rel)
        counts[d["tier"]] += 1
        worst = _bump(worst, d["tier"])
        if d["tier"] != TIER_NORMAL:
            manual.append(d)
    return {"tier": worst, "counts": counts, "manual": manual,
            "reasons": [r for d in manual for r in d["reasons"]]}


def _strict_mode() -> bool:
    return (os.environ.get("GBT_SYNC_STRICT") or "").strip().lower() in ("1", "true", "yes", "on")


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


def do_like(root: Path, note: str, manifest: Path | None = None) -> dict:
    if not sys.stdin.isatty():
        return {"ok": False, "status": "denied",
                "error": "点赞必须在**终端侧**由主人执行（当前 stdin 不是 TTY）。"
                         "本仓既有口径：approve 不能由 agent 自批。"}
    extra: dict = {}
    if manifest is not None:
        if not manifest.is_file():
            return {"ok": False, "status": "needs_input", "error": f"清单不存在: {manifest}"}
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": "needs_input", "error": f"清单读不开：{e}"}
        files = doc.get("files") or []
        if not files:
            return {"ok": False, "status": "needs_input", "error": "清单里没有文件"}
        mft_sha = sha256(manifest)
        print("即将授权：**按清单批量**拉取源码到产品目录。")
        print(f"清单：{manifest}")
        print("文件：%d 个 · 合计 %.1f KB" % (len(files), sum(int(f.get("bytes") or 0) for f in files) / 1024.0))
        print(f"清单指纹：{mft_sha[:16]}…（这次点赞只对这份清单有效）")
        for f in files[:5]:
            print("  · " + str(f.get("rel") or f.get("dst")))
        if len(files) > 5:
            print("  · … 其余 %d 个" % (len(files) - 5))
        extra = {"manifest_sha": mft_sha, "manifest_count": len(files),
                 "manifest_path": str(manifest)}
    else:
        print("即将授权：拉取源码到产品目录。")
    print(f"备注：{note or '（无）'}")
    ans = input("输入 LIKE 确认点赞（其它任何输入=取消）：").strip()
    if ans != "LIKE":
        return {"ok": False, "status": "cancelled", "error": "未点赞"}
    rec = {"at": time.time(), "at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
           "ttl": LIKE_TTL, "note": note, "used": False, "by": os.environ.get("USERNAME") or "?", **extra}
    p = _like_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_bytes(p, json.dumps(rec, ensure_ascii=False, indent=1).encode("utf-8"))
    _ledger(root, {"at": rec["at_human"], "op": "like", "note": note, "ttl": LIKE_TTL})
    return {"ok": True, "status": "liked", **rec}


def _consume_like(root: Path, target: Path, manifest_sha: str | None = None,
                  tiers: dict | None = None, rel: str | None = None) -> tuple:
    """写产品目录前的分级闸。返回 (拦下回执 | None, 闸信息)。

    normal -> GBT 自行决策（落 auto_approve 账，带清单指纹）；
    danger / finance -> 仍要主人终端 LIKE（单文件点赞与清单点赞互不挪用）。
    """
    info = {"tier": TIER_NORMAL, "mode": "not_product", "reasons": []}
    if PRODUCT_MARK not in [p.lower() for p in target.parts]:
        return None, info
    tdoc = tiers or classify_rel(rel or _rel_of(root, target))
    info.update({"tier": tdoc.get("tier") or TIER_DANGER,
                 "reasons": list(tdoc.get("reasons") or [])[:12],
                 "mode": "manual"})
    if info["tier"] == TIER_NORMAL and not _strict_mode():
        info["mode"] = "auto"
        _ledger(root, {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "op": "auto_approve",
                       "tier": TIER_NORMAL, "path": str(target),
                       "manifest_sha": manifest_sha,
                       "why": "2026-11-06 主人令：除危险能力与资金转账外，GBT 自行决策"})
        return None, info
    if _strict_mode() and info["tier"] == TIER_NORMAL:
        info["reasons"] = ["GBT_SYNC_STRICT=1（强制逐件点赞）"]
    st = like_status(root)
    if st.get("ok"):
        bound = st.get("manifest_sha")
        if manifest_sha is None and bound:
            return {"ok": False, "status": "need_like",
                    "error": "这次点赞绑定的是清单（批量），不能用来推单个文件",
                    "how": "单文件请重新点赞：atomic-sync.py like --note \"说明\""}, info
        if manifest_sha is not None:
            if not bound:
                return {"ok": False, "status": "need_like",
                        "error": "这次点赞是单文件的，不是给清单的",
                        "how": "批量请用：atomic-sync.py like --manifest <清单> --note \"说明\""}, info
            if str(bound) != str(manifest_sha):
                return {"ok": False, "status": "need_like",
                        "error": "这次点赞不是给这份清单的（清单指纹对不上）",
                        "how": "清单改过就要重新点赞：atomic-sync.py like --manifest <清单> --note \"说明\""}, info
        p = _like_path(root)
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d["used"] = True
            _atomic_write_bytes(p, json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return None, info
    return {"ok": False, "status": "need_like",
            "error": st.get("error") or "拉取源码需要先点赞",
            "how": "在主仓终端执行：python tools/codex-scripts/atomic-sync.py like --note \"说明\"",
            "why": "危险件/资金件仍要终端 YES；其余请用 GBT_SYNC_STRICT=0（默认）"}, info

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

    gate, ginfo = _consume_like(DEFAULT_ROOT, dst, rel=_rel_of(root, dst))
    if gate:
        gate["gate"] = ginfo
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
    return {"ok": True, "status": "applied", "gate": ginfo,
            **{k: rec[k] for k in ("path", "bytes", "before", "after")}}


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

    gate, ginfo = _consume_like(DEFAULT_ROOT, target, rel=_rel_of(root, target))
    if gate:
        gate["gate"] = ginfo
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
    return {"ok": True, "status": "applied", "gate": ginfo, "path": str(target),
            "before": before_sha[:16], "after": after_sha[:16],
            "delta_bytes": len(new_raw) - len(raw), "backup": str(bak) if bak else None}


def build_manifest(src_root: Path, dst_root: Path, rels, out: Path) -> dict:
    files = []
    for rel in rels:
        rel = str(rel or "").strip().strip("/\\")
        if not rel:
            continue
        s = src_root / rel
        if not s.is_file():
            return {"ok": False, "status": "needs_input", "error": f"源不存在: {s}"}
        files.append({"rel": rel.replace("\\", "/"), "src": str(s), "dst": str(dst_root / rel),
                      "bytes": s.stat().st_size, "sha256": sha256(s)})
    if not files:
        return {"ok": False, "status": "needs_input", "error": "没有可登记的文件"}
    tiers = classify_many([f["rel"] for f in files])
    doc = {"v": 1, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
           "src_root": str(src_root), "dst_root": str(dst_root),
           "count": len(files), "tiers": tiers, "files": files}
    _atomic_write_bytes(out, (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return {"ok": True, "status": "written", "manifest": str(out), "count": len(files),
            "tiers": tiers, "need_like": tiers["tier"] != TIER_NORMAL,
            "sha256": sha256(out), "bytes": sum(f["bytes"] for f in files)}


def do_put_batch(manifest: Path, root: Path, apply: bool) -> dict:
    if not manifest.is_file():
        return {"ok": False, "status": "needs_input", "error": f"清单不存在: {manifest}"}
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "needs_input", "error": f"清单读不开：{e}"}
    files = doc.get("files") or []
    if not files:
        return {"ok": False, "status": "needs_input", "error": "清单里没有文件"}

    plan, problems = [], []
    for ent in files:
        src = Path(str(ent.get("src") or ""))
        dst = Path(str(ent.get("dst") or ""))
        want = str(ent.get("sha256") or "")
        if not src.is_file():
            problems.append({"src": str(src), "problem": "源不存在"})
            continue
        if not inside(root, dst):                      # 闸 1：目标必须在 --root 里
            problems.append({"dst": str(dst), "problem": "目标不在 --root 里"})
            continue
        got = sha256(src)
        if got != want:                                # 闸：源在点赞之后被改过
            problems.append({"src": str(src), "problem": f"源变了 {got[:12]} != 清单 {want[:12]}"})
            continue
        old = sha256(dst) if dst.is_file() else None
        plan.append({"src": src, "dst": dst, "sha": got, "before": old,
                     "action": "unchanged" if old == got else "put"})
    if problems:                                       # 预检不过 -> 一个都不写
        return {"ok": False, "status": "denied",
                "error": "清单预检未过，一个都没写", "count": len(problems),
                "problems": problems[:20]}

    todo = [x for x in plan if x["action"] == "put"]
    if not todo:
        return {"ok": True, "status": "unchanged", "count": len(plan)}

    tier_doc = classify_many([_rel_of(root, x["dst"]) for x in todo]) if todo else \
        classify_many([])

    if not apply:                                      # 闸 8：默认只看不写
        return {"ok": True, "status": "dry_run", "count": len(plan), "to_write": len(todo),
                "bytes": sum(x["src"].stat().st_size for x in todo),
                "tiers": tier_doc,
                "need_like": tier_doc["tier"] != TIER_NORMAL,
                "preview": [{"dst": str(x["dst"]), "before": x["before"], "after": x["sha"]}
                            for x in todo[:8]],
                "note": "只看不写；danger/finance 需与清单绑定的一次 LIKE，normal 由 GBT 自决"}

    gate, ginfo = _consume_like(DEFAULT_ROOT, todo[0]["dst"],
                                manifest_sha=sha256(manifest), tiers=tier_doc)
    if gate:
        gate["gate"] = ginfo
        return gate

    stamp = time.strftime("%Y%m%d-%H%M%S")
    done, failed = [], []
    for x in todo:
        src, dst, sha = x["src"], x["dst"], x["sha"]
        try:
            bak = _backup(root, dst, stamp)            # 闸 7
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + f".tmp-{os.getpid()}")
            try:
                with open(src, "rb") as fi, open(tmp, "wb") as fo:
                    shutil.copyfileobj(fi, fo, 1 << 22)
                    fo.flush()
                    os.fsync(fo.fileno())
                if sha256(tmp) != sha:                 # 闸 4
                    raise RuntimeError("落盘哈希与清单不一致")
                os.replace(tmp, dst)                   # 闸 6
            finally:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
            if sha256(dst) != sha:                     # 读回再算一次
                raise RuntimeError("读回哈希与清单不一致")
            _ledger(root, {"at": stamp, "op": "put", "batch": stamp, "path": str(dst),
                           "bytes": dst.stat().st_size, "before": x["before"], "after": sha,
                           "backup": str(bak) if bak else None})
            done.append({"path": str(dst), "after": sha})
        except Exception as e:  # noqa: BLE001
            failed.append({"path": str(dst), "error": f"{type(e).__name__}: {e}"})
            break                                      # 出事就停，不硬着头皮往下写
    _ledger(root, {"at": stamp, "op": "put-batch", "manifest": str(manifest),
                   "manifest_sha": sha256(manifest), "planned": len(todo),
                   "done": len(done), "failed": len(failed)})
    return {"ok": not failed, "status": "applied" if not failed else "partial",
            "gate": ginfo, "count": len(plan), "written": len(done), "failed": failed,
            "written_paths": [d["path"] for d in done]}


def do_policy(paths=None) -> dict:
    """把分级规则摆到台面上：哪些自决、哪些要终端 YES。"""
    doc = {
        "ok": True,
        "rule": "2026-11-06 主人令：只有危险能力使用与资金转账要终端 YES；其余 GBT 自行决策",
        "auto": "normal：文档 / 技能 / 面板素材 / 普通 .py .json .md / 权重",
        "manual": {
            "danger": "可执行载体 + 授权门与审计本体 + 系统自启位置（见下）",
            "finance": "转账 / 付款 / 钱包 / 账单类路径（见下）",
        },
        "danger_path_suffixes": list(DANGER_PATH_SUFFIXES),
        "danger_path_parts": list(DANGER_PATH_PARTS),
        "danger_ext": sorted(DANGER_EXT),
        "finance_markers": list(FINANCE_MARKERS),
        "fail_closed": "判不准 -> danger",
        "strict_env": "GBT_SYNC_STRICT=1 恢复『每件都要 LIKE』",
        "batch_rule": "一批里只要有一个 danger/finance，整批要 LIKE",
    }
    if paths:
        doc["classified"] = [classify_rel(p) for p in paths]
        doc["summary"] = classify_many(list(paths))
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="原子替换器（put / patch / like / manifest / put-batch / policy）")
    ap.add_argument("cmd", choices=["put", "patch", "like", "manifest", "put-batch", "policy"])
    ap.add_argument("--src")
    ap.add_argument("--dst")
    ap.add_argument("--file")
    ap.add_argument("--find-file")
    ap.add_argument("--replace-file")
    ap.add_argument("--note", default="", help="like 的备注")
    ap.add_argument("--manifest", help="manifest 产出的清单文件（like / put-batch 用）")
    ap.add_argument("--paths-file", help="manifest：一行一个仓内相对路径")
    ap.add_argument("--src-root", help="manifest：源根目录（开发仓）")
    ap.add_argument("--dst-root", help="manifest：目标根目录（产品 payload）")
    ap.add_argument("--out", help="manifest：清单写到哪")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--apply", action="store_true", help="不带则 dry-run")
    a = ap.parse_args(argv)

    root = Path(a.root)
    if a.cmd == "policy":
        paths = None
        if a.paths_file:
            paths = [x for x in Path(a.paths_file).read_text(encoding="utf-8").splitlines() if x.strip()]
        r = do_policy(paths)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "like":
        r = do_like(DEFAULT_ROOT, a.note, Path(a.manifest) if a.manifest else None)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a.cmd == "manifest":
        if not (a.src_root and a.dst_root and a.paths_file and a.out):
            print("manifest 需要 --src-root --dst-root --paths-file --out"); return 2
        rels = Path(a.paths_file).read_text(encoding="utf-8").splitlines()
        r = build_manifest(Path(a.src_root), Path(a.dst_root), rels, Path(a.out))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a.cmd == "put-batch":
        if not a.manifest:
            print("put-batch 需要 --manifest"); return 2
        r = do_put_batch(Path(a.manifest), root, a.apply)
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
