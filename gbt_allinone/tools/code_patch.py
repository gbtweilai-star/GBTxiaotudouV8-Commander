# -*- coding: utf-8 -*-
"""GBT小土豆V8 · `code_patch` —— **把「改代码」收进唯一门**（2026-09-23 接）。

## 为什么必须做这一件

在此之前，**改代码不过门**：agent 直接 `edit` / `write` 落盘 ——
没有审计、没有信封、没有步账、没有"改前改后"的凭据。
而"专业级编程AI"的第一块地基恰恰是：**每一次改动都能自证**（改了哪个文件、改前是什么、
改后是什么、能不能退回去）。

⇒ 本件把它做成一个**过门的能力位**：`run_task("code_patch", {...})`
—— 于是它天然带上唯一门的全部纪律（授权、审计、信封、preflight）。

## 机械闸（每一条都有牙，不是提醒）

    1. 路径必须在**仓内**（`path` 解析后必须落在 ROOT 下）—— 不许伸到仓外
    2. `find` 必须**恰好出现一次**：0 次 ⇒ `not_found`；>1 次 ⇒ `ambiguous`
       （**绝不替你挑一个** —— 挑错就是改错地方）
    3. `find != replace`（空改动直接拒，不做无意义写盘）
    4. `expect_sha256` 给了就必须对上（防"拿陈旧内容去改"）
    5. **二进制文件拒改**（前 8KB 有 NUL）：把 PNG/GLB 当文本读写 = 当场弄成废物
    6. 文件 > `MAX_BYTES` 拒改（防手滑改大文件）
    7. **逐字节替换**（不是文本替换）：只在 `find` 那几个字节上动手，
       `\\n` / CRLF / BOM 一个字节都不动
       （教训：`write_text` 会把 `\\n` 变成 `\\r\\n` —— 文本层替换会连带改掉整个文件的行尾）
    8. **原子写**：临时文件 + `os.replace`（写一半被杀不会留半个文件）
    9. `op=dry_run`（**默认**）只算不写；`op=apply` 才落盘
   10. `op=create` **新建文件**（2026-10-18 补）：`expect_absent` 默认真、不覆盖已有文件、
       不建空文件、不建二进制、原子写、带回执，回滚=移到 `rolledback/`（不删）

## 回执与可回滚

`apply` 会把**这次替换的三件套**（`find` / `replace` / 改前改后哈希）写进
`store/code_patch/<at>-<after8>.json` —— 于是 `op=rollback` 只要：
① 读回执 ② 确认当前文件哈希 == `after_sha256`（**文件要是又被人动过就拒绝回滚**，不猜）
③ 把 `replace` 换回 `find`。**回执里不写整份文件**，只写被替换的那几行。

## 用法（经唯一门）

    py -3.14 tools/codex-scripts/five-dim.py cap code_patch '{"path":"a.py","find":"x","replace":"y"}'
    # 默认 dry_run：只报 diff 与哈希，不写盘
    py -3.14 tools/codex-scripts/five-dim.py cap code_patch '{"op":"apply","path":"a.py","find":"x","replace":"y"}'
    # 需要 filesystem_write 授权（门会拦；缺授权如实报缺）
    py -3.14 tools/codex-scripts/five-dim.py cap code_patch '{"op":"create","path":"new.py","content":"..."}'
    # 新建文件（同样挂在 filesystem_write 下：policy 对 code_patch 是黑名单 fail-closed）

## 默认：原子替换 · 无伤修复（2026-11-03 主人令）

主人令（逐字）：「只要是修复代码必须使用原子替换无伤修复」。

⇒ `apply` / `create` **默认不再直接写生产**，而是自动走 mirror_stage 全流程：

    ① create  生产目标只读复制进 state/mirror/stage/<id>/（生产一个字节都没动）
    ② write   候选只写镜像 work/
    ③ verify  自动验证器按扩展名挑：
                .py/.pyw → AST 语法解析（不产生 pyc）
                .json    → json 解析
                .js/.mjs/.cjs → node --check
                其他     → 退到"完整性校验"（staged 字节 == 算出来的字节），
                           **如实标注 sha_only，不假装语义验证过**
             也可用 `verify_cmd` 传自己的验证命令（例如跑该模块的单测）
    ④ promote 仅当 verify.exit_code == 0 才做**整文件 os.replace 原子替换**，
              替换前把原件备份到 state/mirror/backups/<时间戳>-<id>/（可 rollback）

**验证不过 ⇒ 绝不落盘**，并且把失败证据（stdout/stderr 尾巴）一起返回。

应急口：`allow_unverified=true` 走旧的直写路径（仍逐字节替换 + 原子写），
但回执里记 `bypass: true` 与原因 —— 是**留痕**，不是免检。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]      # 仓根（gbt_allinone 的父目录）
MAX_BYTES = 4 * 1024 * 1024                       # 4 MB：手滑改大文件直接拒
_BIN_SNIFF = 8192


class CodePatchError(ValueError):
    """本能力自己的错误类型（带上机读的 reason_code）。

    🔴 **为什么继承 `ValueError`**：框架的约定是"用法/参数类错误要**抛**"，
    由 `api._run_task_core` 的 `except (ValueError, TypeError, …)` 收敛成
    `{"status": "error", "error_class": "user_error"}` 并记 `user_error` 审计。
    第一版我在这里**吞掉异常、返回错误 dict** ⇒ 外层被判成 `status: "ok"`
    （框架把"返回了 dict"读成"执行成功，结果在里面"）—— **读数自相矛盾**：
    外面 ok、里面 option_injection。跟着框架的约定抛，才是对的。
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _store_dir() -> Path:
    try:
        from .. import _paths
        return _paths.STORE_DIR / "code_patch"
    except Exception:                                            # noqa: BLE001
        return _ROOT / "gbt_allinone" / "store" / "code_patch"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _resolve_inside(path: str) -> Path:
    """解析到**仓内**的绝对路径；伸出去就拒。"""
    raw = str(path or "").strip()
    if not raw:
        raise CodePatchError("missing_path", "没有给 path")
    p = Path(raw)
    p = (p if p.is_absolute() else (_ROOT / p)).resolve()
    try:
        p.relative_to(_ROOT)
    except ValueError:
        raise CodePatchError("outside_repo",
                             "路径不在仓内（拒绝）：%s" % str(p)[:120]) from None
    return p


def _load(p: Path) -> bytes:
    if not p.is_file():
        raise CodePatchError("not_a_file", "不是文件（或不存在）：%s" % p.name)
    b = p.read_bytes()
    if len(b) > MAX_BYTES:
        raise CodePatchError("too_large", "文件 %d 字节 > 上限 %d —— 拒改" % (len(b), MAX_BYTES))
    if b"\x00" in b[:_BIN_SNIFF]:
        raise CodePatchError("binary_file", "看起来是二进制（前 8KB 有 NUL）—— 拒改")
    return b


def _compute(path: str, find: str, replace: str, expect_sha256: str = "") -> dict:
    """算清楚"要改什么" —— **不写盘**。dry_run 与 apply 共用同一条计算路径。"""
    if not find:
        raise CodePatchError("empty_find", "find 不能为空（空白替换只会误伤）")
    if find == replace:
        raise CodePatchError("no_change", "find 与 replace 相同 ⇒ 空改动，拒绝写盘")
    p = _resolve_inside(path)
    before = _load(p)
    want = str(expect_sha256 or "").strip().lower()
    cur = _sha(before)
    if want and want != cur:
        raise CodePatchError("stale_content",
                             "expect_sha256 对不上：给了 %s，实际 %s" % (want[:12], cur[:12]))
    fb, rb = find.encode("utf-8"), replace.encode("utf-8")
    n = before.count(fb)
    if n == 0:
        raise CodePatchError("not_found", "find 在文件里一次都没出现（没改）")
    if n > 1:
        raise CodePatchError("ambiguous",
                             "find 出现了 %d 次 —— 拒绝替你挑一个（改错地方比不改更糟）" % n)
    after = before.replace(fb, rb, 1)
    return {
        "path": str(p.relative_to(_ROOT)).replace("\\", "/"),
        "abs": str(p),
        "occurrences": n, "find": find, "replace": replace,
        "before_sha256": cur, "after_sha256": _sha(after),
        "bytes_before": len(before), "bytes_after": len(after),
        "bytes_delta": len(after) - len(before),
        "_before": before, "_after": after,
    }


def _atomic_write(p: Path, data: bytes) -> None:
    tmp = p.with_name(p.name + ".gbtpatch%d" % os.getpid())
    try:
        tmp.write_bytes(data)
        os.replace(str(tmp), str(p))
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def create(path: str, content: str, note: str = "", expect_absent: bool = True,
           verify_cmd: str = "", allow_unverified: bool = False) -> dict:
    """**新建文件**（2026-10-18 补）。

    ## 为什么必须有这一支

    2026-10-18 现读实锤：`apply` 只能**改已存在**的文件（`_load()` 对不存在的路径直接
    `not_a_file`），`find` 空又直接 `empty_find` ⇒ **"新建一个文件"当时没有任何过门通道**。
    后果是模型只能在门外面用文件工具硬写 —— 那正是"绕过授权门"，而且没有回执、不能回滚。

    ## 机械闸（与 apply 同口径，另加两条与"建"有关的）

      1. 路径必须在**仓内**（同 `_resolve_inside`）
      2. `expect_absent`（**默认真**）：目标已存在 ⇒ `already_exists` 拒绝
         —— 建**不覆盖**；要覆盖请走 `apply`（带改前改后哈希与回滚三件套）
      3. `content` 不许为空；`> MAX_BYTES` 拒
      4. 内容含 NUL ⇒ 拒（二进制必须走逐字节通道，不许当文本建）
      5. **原子写**：同目录临时文件 + `os.replace`
      6. 父目录不存在则建（只建仓内路径）

    ## 回执与可回滚

    回执落 `store/code_patch/<at>-<after8>.json`，`op=create`、`before_sha256` 为空。
    `op=rollback` 对 create 回执**不是删**：把文件移到
    `store/code_patch/rolledback/<rid>-<name>`，字节一个不丢。
    """
    p = _resolve_inside(path)
    if expect_absent and p.exists():
        raise CodePatchError("already_exists",
                             "目标已存在，create 不覆盖：%s（要改它请用 op=apply）"
                             % str(p.relative_to(_ROOT)).replace("\\", "/"))
    body = str(content if content is not None else "")
    if not body:
        raise CodePatchError("empty_content", "content 为空 —— 拒绝建一个空文件")
    data = body.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise CodePatchError("too_large", "内容 %d 字节 > 上限 %d —— 拒绝" % (len(data), MAX_BYTES))
    if b"\x00" in data[:_BIN_SNIFF]:
        raise CodePatchError("binary_content", "内容里有 NUL —— 二进制不许当文本建")
    after_sha = _sha(data)

    # 默认：新建也走无伤修复（镜像验证通过才落盘）
    if not allow_unverified:
        # rel 在原函数里后面才算；mirror 分支要用，先在此算好（同值重复赋值无害）
        rel0 = str(p.relative_to(_ROOT)).replace("\\", "/")
        return _mirror_repair(rel0, data, after_sha, verify_cmd=verify_cmd,
                              note=note, is_create=True)

    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(p, data)
    d = _store_dir()
    d.mkdir(parents=True, exist_ok=True)
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    rid = "%s-%s" % (time.strftime("%Y%m%dT%H%M%S"), after_sha[:8])
    rel = str(p.relative_to(_ROOT)).replace("\\", "/")
    rec = {"receipt_id": rid, "at": at, "op": "create", "path": rel,
           "before_sha256": "", "after_sha256": after_sha, "bytes": len(data),
           "via": "direct", "bypass": True,
           "note": (note or "")[:120],
           "rollback": "移到 store/code_patch/rolledback/（不删，字节保留）"}
    (d / (rid + ".json")).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"op": "create", "wrote": True, "ok": True, "path": rel, "abs": str(p),
            "before_sha256": "", "after_sha256": after_sha,
            "bytes_before": 0, "bytes_after": len(data), "bytes_delta": len(data),
            "receipt_id": rid, "receipt": str(d.joinpath(rid + ".json")), "at": at}


def _rollback_create(rec: dict, path: str = "") -> dict:
    """create 回执的回滚 = **移走**（不是删）。当前哈希先对上 `after_sha256`，对不上就拒。"""
    if path and str(path) != rec.get("path"):
        raise CodePatchError("receipt_mismatch",
                             "回执是给 %s 的，你给的是 %s" % (rec.get("path"), path))
    p = _resolve_inside(rec["path"])
    if not p.is_file():
        raise CodePatchError("not_a_file", "要回滚的文件已经不在了：%s" % rec.get("path"))
    cur = _sha(p.read_bytes())
    if cur != rec.get("after_sha256"):
        raise CodePatchError("stale_content",
                             "当前哈希 %s 与回执 %s 对不上 —— 文件被人动过，拒绝回滚（不猜）"
                             % (cur[:12], str(rec.get("after_sha256"))[:12]))
    grave = _store_dir() / "rolledback"
    grave.mkdir(parents=True, exist_ok=True)
    dst = grave / ("%s-%s" % (rec.get("receipt_id"), p.name))
    os.replace(str(p), str(dst))
    return {"op": "rollback", "wrote": True, "ok": True, "kind": "create",
            "path": rec.get("path"), "moved_to": str(dst),
            "rolled_back_receipt": rec.get("receipt_id"),
            "note": "create 已回滚：文件移到 rolledback/（字节保留，未删除）"}


# ══════════════════════════════════════════════════════════════════════
# 默认无伤修复：镜像 → 验证 → 原子替换（2026-11-03 主人令）
# ══════════════════════════════════════════════════════════════════════

# 按扩展名挑验证器：(kind, argv 模板)。{py} 会被替换成当前解释器。
_AUTO_VERIFY: dict = {
    ".py": ("py_ast", ["{py}", "-X", "utf8", "-c",
                       "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8')"
                       ".read(),filename=sys.argv[1])"]),
    ".pyw": ("py_ast", ["{py}", "-X", "utf8", "-c",
                        "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8')"
                        ".read(),filename=sys.argv[1])"]),
    ".json": ("json_parse", ["{py}", "-X", "utf8", "-c",
                             "import json,sys;json.load(open(sys.argv[1],encoding='utf-8'))"]),
    ".js": ("node_check", ["node", "--check"]),
    ".mjs": ("node_check", ["node", "--check"]),
    ".cjs": ("node_check", ["node", "--check"]),
}


def _q(s: str) -> str:
    """cmd 里的一个参数：含空格/反斜杠就加引号（Windows 路径必含反斜杠）。"""
    s = str(s)
    return '"%s"' % s if (" " in s or "\\" in s) else s


def _verify_argv(staged: Path, after_sha: str) -> tuple:
    """给候选文件挑验证器。没有语义验证器就退到完整性校验，并**如实**标注。"""
    spec = _AUTO_VERIFY.get(staged.suffix.lower())
    if spec:
        kind, argv = spec
        built = [a.replace("{py}", sys.executable) for a in argv] + [str(staged)]
        return built, kind
    # 退路：只证明"写进镜像的字节 == 算出来的那串字节"，不假装语义正确
    built = [sys.executable, "-X", "utf8", "-c",
             "import hashlib,sys;"
             "h=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest();"
             "sys.exit(0 if h==sys.argv[2] else 1)",
             str(staged), after_sha]
    return built, "sha_only"


def _mirror_repair(rel: str, new_bytes: bytes, after_sha: str,
                   verify_cmd: str = "", note: str = "",
                   find: str = "", replace: str = "",
                   before_sha: str = "", is_create: bool = False) -> dict:
    """无伤修复主干：生产只读 → 候选写镜像 → 验证 → 通过才原子替换。

    返回体与旧 apply 兼容（path/abs/*_sha256/wrote/ok），另加 mirror 证据字段。
    验证不过时 **不 promote**，返回 ok=False + 证据，生产零改动。
    """
    from ..tentacle import mirror_stage as MS

    sid = "cp-%s-%06d" % (time.strftime("%Y%m%d-%H%M%S"),
                          time.time_ns() // 1000 % 1000000)
    # ① 建镜像（生产只读复制）
    r = MS.run("create", targets=[rel], id=sid)
    if not r.get("ok"):
        raise CodePatchError("mirror_create_failed",
                             "建镜像失败：%s" % (r.get("error") or r.get("status")))

    # ② 候选写镜像（src 分支 = 字节级保真，不碰行尾）
    incoming = _ROOT / "state" / "mirror" / ".incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    tmp = incoming / ("%s.bin" % sid)
    tmp.write_bytes(new_bytes)
    try:
        r = MS.run("write", id=sid, path=rel, src=str(tmp))
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    if not r.get("ok"):
        raise CodePatchError("mirror_write_failed",
                             "候选写镜像失败：%s" % (r.get("error") or r.get("status")))

    staged = _ROOT / "state" / "mirror" / "stage" / sid / "work" / rel
    argv, kind = _verify_argv(staged, after_sha)
    cmd = str(verify_cmd or "").strip() or " ".join(_q(a) for a in argv)

    # ③ 验证（在镜像 work/ 里跑，生产不参与）
    r = MS.run("verify", id=sid, cmd=cmd)
    v = (r or {}).get("verify") or {}
    if not r.get("ok") or int(v.get("exit_code", 1)) != 0:
        return {
            "op": "apply", "ok": False, "wrote": False, "status": "verify_failed",
            "path": rel, "mirror_stage": sid, "verify_kind": kind, "verify_cmd": cmd,
            "verify_exit_code": v.get("exit_code"),
            "stdout_tail": (v.get("stdout_tail") or "")[-800:],
            "stderr_tail": (v.get("stderr_tail") or "")[-800:],
            "note": "验证没通过 ⇒ 生产一个字节都没动。修好候选后用同一 op 重试，"
                    "或 op=rollback 清掉这个 stage。",
        }

    # ④ 原子整页替换（先备份，可 rollback）
    r = MS.run("promote", id=sid, confirm=True)
    if not r.get("ok"):
        raise CodePatchError("mirror_promote_failed",
                             "替换失败：%s" % (r.get("error") or r.get("status")))

    # ⑤ 仍写 code_patch 回执（与旧通道一致，回滚口径不变）
    # 🔴 三件套必须写真实值：find/replace/before_sha256 留空 ⇒ op=rollback 直接坏
    #    （实测：空 find 会让 _compute 抛 empty_find，回滚通道当场失效）。
    d = _store_dir()
    d.mkdir(parents=True, exist_ok=True)
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    rid = "%s-%s" % (time.strftime("%Y%m%dT%H%M%S"), after_sha[:8])
    rec = {"receipt_id": rid, "at": at, "path": rel,
           "op": "create" if is_create else "apply",
           "find": find, "replace": replace,
           "before_sha256": before_sha, "after_sha256": after_sha,
           "via": "mirror_stage", "mirror_stage": sid, "verify_kind": kind,
           "note": (note or "")[:200] or "镜像验证通过后原子替换；原件备份在 state/mirror/backups/"}
    (d / (rid + ".json")).write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    return {
        "op": "create" if is_create else "apply", "ok": True, "wrote": True,
        "status": "promoted",
        "path": rel, "abs": str(_ROOT / rel),
        "before_sha256": before_sha,
        "after_sha256": after_sha,
        "mirror_stage": sid, "verify_kind": kind, "verify_cmd": cmd,
        "backup": r.get("backup"),
        "receipt_id": rid, "receipt": str(d / (rid + ".json")), "at": at,
        "note": "无伤修复：镜像验证通过 → 整文件原子替换；原件已备份，可 rollback",
    }


def dry_run(path: str, find: str, replace: str, expect_sha256: str = "") -> dict:
    r = _compute(path, find, replace, expect_sha256)
    r.pop("_before", None)
    r.pop("_after", None)
    r.update({"op": "dry_run", "wrote": False, "ok": True,
              "note": "只算不写。要落盘再用 op=apply（那一支要过 filesystem_write 门）"})
    return r


def apply(path: str, find: str, replace: str, expect_sha256: str = "",
          verify_cmd: str = "", allow_unverified: bool = False) -> dict:
    r = _compute(path, find, replace, expect_sha256)
    after = r.pop("_after")
    r.pop("_before", None)

    # 默认：原子替换 · 无伤修复（验证不过绝不落盘）
    if not allow_unverified:
        out = _mirror_repair(r["path"], after, r["after_sha256"],
                             verify_cmd=verify_cmd,
                             find=find, replace=replace,
                             before_sha=r["before_sha256"])
        for k in ("before_sha256", "bytes_before", "bytes_after", "bytes_delta", "occurrences"):
            if k in r:
                out.setdefault(k, r[k])
        return out

    # 应急直写：仍逐字节 + 原子写，但回执必须留痕
    p = Path(r["abs"])
    _atomic_write(p, after)
    d = _store_dir()
    d.mkdir(parents=True, exist_ok=True)
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    rid = "%s-%s" % (time.strftime("%Y%m%dT%H%M%S"), r["after_sha256"][:8])
    rec = {"receipt_id": rid, "at": at, "path": r["path"],
           "find": find, "replace": replace,
           "before_sha256": r["before_sha256"], "after_sha256": r["after_sha256"],
           "via": "direct", "bypass": True,
           "note": "⚠️ 走了 allow_unverified 应急直写（未经镜像验证）——留痕备查。"
                   "回滚三件套：确认当前哈希==after_sha256，再把 replace 换回 find"}
    (d / (rid + ".json")).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    r.update({"op": "apply", "wrote": True, "ok": True, "receipt_id": rid,
              "receipt": str(d.joinpath(rid + ".json")), "at": at,
              "via": "direct", "bypass": True,
              "warning": "未经镜像验证（allow_unverified=true）：这是应急口，不是默认路径"})
    return r


def rollback(receipt_id: str = "", path: str = "") -> dict:
    """按回执回滚。**当前文件必须先对上 `after_sha256`**，对不上就拒（文件被人动过，不猜）。"""
    d = _store_dir()
    if not receipt_id:
        cands = sorted(d.glob("*.json")) if d.is_dir() else []
        if not cands:
            raise CodePatchError("no_receipt", "没有回执可回滚（store/code_patch 下是空的）")
        rec = json.loads(cands[-1].read_text(encoding="utf-8"))
    else:
        f = d / ("%s.json" % receipt_id)
        if not f.is_file():
            raise CodePatchError("no_such_receipt", "找不到回执 %s" % receipt_id)
        rec = json.loads(f.read_text(encoding="utf-8"))
    if path and str(path) != rec.get("path"):
        raise CodePatchError("receipt_mismatch",
                             "回执是给 %s 的，你给的是 %s" % (rec.get("path"), path))
    if rec.get("op") == "create":
        return _rollback_create(rec, path)
    r = _compute(rec["path"], rec["replace"], rec["find"],
                 expect_sha256=rec["after_sha256"])
    p = Path(r["abs"])
    _atomic_write(p, r.pop("_after"))
    r.pop("_before", None)
    r.update({"op": "rollback", "wrote": True, "ok": True,
              "rolled_back_receipt": rec.get("receipt_id"),
              "note": "已按回执退回；当前哈希 == 该回执的 before_sha256"})
    return r


def run(payload: dict | None = None) -> dict:
    """能力位入口。`op` 默认 `dry_run`（**默认不写**）。"""
    p = dict(payload or {})
    op = str(p.get("op") or "dry_run").strip().lower()
    if op in ("dry_run", "dry", "preview", "diff"):
        return dry_run(p.get("path"), p.get("find"), p.get("replace"),
                       p.get("expect_sha256"))
    if op in ("apply", "write", "patch"):
        return apply(p.get("path"), p.get("find"), p.get("replace"),
                     p.get("expect_sha256"),
                     verify_cmd=p.get("verify_cmd", ""),
                     allow_unverified=bool(p.get("allow_unverified", False)))
    if op in ("create", "new", "add"):
        return create(p.get("path"), p.get("content"), p.get("note", ""),
                      bool(p.get("expect_absent", True)),
                      verify_cmd=p.get("verify_cmd", ""),
                      allow_unverified=bool(p.get("allow_unverified", False)))
    if op in ("rollback", "revert", "undo"):
        return rollback(p.get("receipt_id"), p.get("path"))
    raise CodePatchError("unknown_op",
                         "不认识的 op=%s（只认 dry_run / apply / create / rollback）" % op)
