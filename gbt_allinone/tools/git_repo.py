# -*- coding: utf-8 -*-
"""GBT小土豆V8 · git 能力位（2026-09-23 接，补"改完能回滚"那一半）。

## 为什么拆成**两个**能力位

`git_read`（只读）与 `git_write`（写面）**分开登记**，不合成一个带 `op` 的大件。理由：

  · `safe` 是**按能力位**记的，不是按 op 记的。合成一件就必须回答"它到底 safe 不 safe"，
    而正确答案是"看 op"—— 那正是含糊的来源。
  · 拆开之后门的判据**平凡正确**：`git_read` **永远零作用域**；`git_write` **永远挂
    `filesystem_write`**。没有"这个 op 算不算写"的判断题，也就没有判错的机会。
  · 面板/omni 的自动代调也只认 `safe`：只读那件可以被代调，写面那件一律不代调。

## 机械闸（每一条都有牙）

  1. **绝不过 shell**：一律 `subprocess.run([...], shell=False)` —— 调用方给的字串
     永远进不了命令行解析
  2. **反选项注入**：`rev` / `branch` / `message` / 每个 `path` **都不许以 `-` 开头**
     （否则会被 git 当选项吃，经典 `--upload-pack=…` 就是这么塞进去的）
  3. **路径必须在仓内**：解析后必须落在仓根下（与 `code_patch` 同一条规矩）
  4. **每条 git 命令都带 `--`**：路径参数一律放在 `--` 之后，杜绝"路径被当版本"
  5. **写面必须点名路径**：`stage` / `commit` **不许空 paths**
     —— 本仓现在有 4 万多行 porcelain，`commit -a` 一次就把不相干的东西全卷进去
  6. **超时 + 输出上限**：60s / 200KB（不许挂死，也不许把巨型 diff 灌回来）
  7. **读面零作用域**：`git_read` 在 `policy` 里**不挂任何 scope**

## 写面（2026-11-03 补齐）

  · `stage` / `commit`：点名路径；commit 仍用 pathspec-limited，不动别的暂存内容。
  · `push` / `force_push`：真 `git push`；`force_push` 用 `--force-with-lease`；
    必须有 `confirm=true` + `remote` + `branch`，不允许 force 到任意 URL。
  · `rebase`：工作区必须干净；`confirm=true`；冲突时返回冲突列表，不自动 `--abort`。
  · `reset --hard`：**破坏性**；`confirm=true` + 明确 `rev`；只动本地工作区。
  · 以上全部仍走 `git_write` 的 `filesystem_write` 门；push 另在返回里标 `network=true`，
    需要出网授权时由调用方/门决定，**能力自己不偷偷推**。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 60


def _git_exe() -> str:
    """Windows 安装 Git 后当前进程 PATH 未必刷新；按常见落点兜底。"""
    found = shutil.which("git")
    if found:
        return found
    for p in (r"C:\Program Files\Git\cmd\git.exe",
              r"C:\Program Files (x86)\Git\cmd\git.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "cmd", "git.exe")):
        if p and Path(p).is_file():
            return p
    return "git"

MAX_OUT = 200 * 1024

_READ_OPS = ("status", "diff", "log", "show", "branch_list", "branch", "stash_list")
_WRITE_OPS = ("stage", "add", "commit", "push", "force_push", "rebase", "reset")


class GitRepoError(ValueError):
    """本能力自己的错误类型（带机读 reason_code）。

    继承 `ValueError`：框架约定"用法/参数类错误要抛"，由 `api._run_task_core` 的
    `except (ValueError, …)` 收敛成 `status: error` + `error_class: user_error`。
    **吞掉异常返回错误 dict 会让外层判成 ok** —— 那是读数自相矛盾。
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _no_leading_dash(name: str, value) -> str:
    """反选项注入：以 `-` 开头的值会被 git 当选项吃。"""
    s = str(value if value is not None else "").strip()
    if s.startswith("-"):
        raise GitRepoError("option_injection",
                           "%s 以 `-` 开头（会被 git 当选项吃）⇒ 拒：%s" % (name, s[:60]))
    return s


def _rel_inside(raw) -> str:
    """路径必须在仓内；返回**仓内相对路径**（用 `/`）。"""
    s = _no_leading_dash("path", raw)
    if not s:
        raise GitRepoError("empty_path", "给了空路径")
    p = Path(s)
    p = (p if p.is_absolute() else (_ROOT / p)).resolve()
    try:
        rel = p.relative_to(_ROOT)
    except ValueError:
        raise GitRepoError("outside_repo", "路径不在仓内：%s" % str(p)[:120]) from None
    return str(rel).replace("\\", "/")


def _git(args: list, *, timeout: int = TIMEOUT_S) -> dict:
    """跑一条 git。**永远 shell=False**。返回 `{ok, rc, out, err, truncated}`。"""
    try:
        p = subprocess.run([_git_exe(), *args], cwd=str(_ROOT), shell=False,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise GitRepoError("git_missing", "本机找不到 git") from None
    except subprocess.TimeoutExpired:
        raise GitRepoError("timeout", "git 超过 %ds 没返回（已掐断）" % timeout) from None
    out = p.stdout or ""
    trunc = len(out) > MAX_OUT
    if trunc:
        out = out[:MAX_OUT] + "\n…（截断：超过 %d 字节）" % MAX_OUT
    return {"ok": p.returncode == 0, "rc": p.returncode, "out": out,
            "err": (p.stderr or "")[:2000], "truncated": trunc}


# ── 只读面 ─────────────────────────────────────────────────────────────────
def run_read(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get("op") or "status").strip().lower()
    if op not in _READ_OPS:
        raise GitRepoError("unknown_op",
                           "git_read 不认 op=%s（只认 %s）" % (op, "/".join(_READ_OPS)))

    if op in ("status", "branch"):
        r = _git(["status", "--porcelain=v1", "--branch"])
        lines = [l for l in r["out"].splitlines() if l.strip()]
        head = next((l for l in lines if l.startswith("##")), "")
        changes = [l for l in lines if not l.startswith("##")]
        return {"ok": r["ok"], "readonly": True, "op": "status",
                "branch_line": head,
                "dirty_n": len(changes), "dirty_sample": changes[:40],
                "note": "porcelain=v1；只报数量与前 40 条（本仓脏行可能上万，全量灌回来没意义）"}

    if op == "diff":
        args = ["diff"]
        if p.get("staged"):
            args.append("--cached")
        args.append("--stat")
        path = p.get("path")
        if path:
            args += ["--", _rel_inside(path)]
        r = _git(args)
        return {"ok": r["ok"], "readonly": True, "op": "diff", "stat": r["out"],
                "staged": bool(p.get("staged")), "path": path or ""}

    if op == "log":
        try:
            limit = max(1, min(200, int(p.get("limit") or 20)))
        except Exception:                                            # noqa: BLE001
            raise GitRepoError("bad_limit", "limit 必须是整数") from None
        r = _git(["log", "-%d" % limit, "--format=%h %cI %s"])
        return {"ok": r["ok"], "readonly": True, "op": "log", "limit": limit,
                "commits": [l for l in r["out"].splitlines() if l.strip()]}

    if op == "show":
        rev = _no_leading_dash("rev", p.get("rev") or "HEAD") or "HEAD"
        args = ["show", "--stat", "--format=%h %cI %s", rev]
        path = p.get("path")
        if path:
            args += ["--", _rel_inside(path)]
        r = _git(args)
        return {"ok": r["ok"], "readonly": True, "op": "show", "rev": rev, "text": r["out"]}

    # branch_list / stash_list
    r = _git(["branch", "--list", "--format=%(refname:short) %(HEAD)"] if op == "branch_list"
             else ["stash", "list"])
    return {"ok": r["ok"], "readonly": True, "op": op,
            "items": [l for l in r["out"].splitlines() if l.strip()]}


# ── 写面（永远挂 filesystem_write；永远要点名路径）──────────────────────────
def _need_confirm(p: dict, op: str) -> None:
    if p.get("confirm") is not True:
        raise GitRepoError("confirm_required",
                           "%s 是写/破坏/出网动作，必须显式 confirm=true（不接受默认）" % op)


def _safe_ref(name: str, field: str) -> str:
    s = str(name or "").strip()
    if not s or s.startswith("-") or any(c in s for c in " \t\n\r"):
        raise GitRepoError("bad_%s" % field, "%s 非法：%r" % (field, name))
    return s


def run_write(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get("op") or "").strip().lower()
    if op not in _WRITE_OPS:
        raise GitRepoError("unknown_op",
                           "git_write 不认 op=%s（只认 %s）" % (op, "/".join(_WRITE_OPS)))

    if op in ("push", "force_push"):
        _need_confirm(p, op)
        remote = _safe_ref(p.get("remote") or "origin", "remote")
        branch = _safe_ref(p.get("branch") or "", "branch")
        if not branch:
            raise GitRepoError("branch_required", "push 必须点名 branch（不猜当前分支）")
        args = ["push"] + (["--force-with-lease"] if op == "force_push" else []) + [remote, branch]
        r = _git(args, timeout=120)
        return {"ok": r["ok"], "readonly": False, "op": op, "remote": remote,
                "branch": branch, "network": True, "text": r["out"] or r["err"],
                "note": "已真推；force_push 只允许 --force-with-lease，绝不裸 --force"}
    if op == "rebase":
        _need_confirm(p, op)
        onto = _safe_ref(p.get("onto") or p.get("rev") or "origin/main", "onto")
        st = _git(["status", "--porcelain"])
        if (st["out"] or "").strip():
            raise GitRepoError("worktree_dirty", "rebase 前工作区必须干净（有未提交改动）")
        r = _git(["rebase", onto], timeout=180)
        return {"ok": r["ok"], "readonly": False, "op": "rebase", "onto": onto,
                "conflict": (not r["ok"]), "text": r["out"] or r["err"],
                "note": "冲突不自动 abort；由调用方看 text 后决定 git rebase --abort/--continue"}
    if op == "reset":
        _need_confirm(p, op)
        rev = _safe_ref(p.get("rev") or "HEAD", "rev")
        if rev == "HEAD":
            raise GitRepoError("rev_required", "reset --hard 必须点名 rev，不接受默认 HEAD")
        r = _git(["reset", "--hard", rev], timeout=120)
        return {"ok": r["ok"], "readonly": False, "op": "reset", "rev": rev,
                "destructive": True, "text": r["out"] or r["err"],
                "note": "只动本地工作区/索引；不推远端"}

    raw_paths = p.get("paths") or ([p["path"]] if p.get("path") else [])
    if not isinstance(raw_paths, (list, tuple)) or not raw_paths:
        raise GitRepoError("paths_required",
                           "写面**必须点名路径** —— 本仓脏行可能上万，"
                           "`commit -a` 一次就把不相干的全卷进去")
    paths = [_rel_inside(x) for x in raw_paths]

    if op in ("stage", "add"):
        r = _git(["add", "--", *paths])
        return {"ok": r["ok"], "readonly": False, "op": "stage", "paths": paths,
                "note": "已把点名的路径加入索引（`git add -- <paths>`）"}

    msg = _no_leading_dash("message", p.get("message"))
    if not msg:
        raise GitRepoError("message_required", "commit 必须给 message")
    # pathspec-limited：只提交点名的路径，**不动索引里别的暂存内容**
    r = _git(["commit", "-m", msg, "--", *paths])
    return {"ok": r["ok"], "readonly": False, "op": "commit", "paths": paths,
            "text": r["out"] or r["err"],
            "note": "pathspec-limited commit（`git commit -m … -- <paths>`）：别的暂存内容不受影响"}
