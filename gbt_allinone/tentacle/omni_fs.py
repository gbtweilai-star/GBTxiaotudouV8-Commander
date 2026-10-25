# gbt-capability: ctypes, filesystem
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""fs 域 mixin — 文件操作（第 9 域，2026-09-22 加入触手）

## 为什么要有这个域

风哥 2026-09-22：「必须能像人类一样使用触手操控电脑上的任何东西」。
实测（原文查证，不是猜）：触手 8 个域 105 个方法里，
**`shutil.copy` / `shutil.move` / `os.rename` / `os.remove` / `os.mkdir` /
`os.startfile` / `ShellExecute` / `explorer.exe` —— 一个都没有。**
人用电脑有一半时间在跟文件和目录打交道（复制/移动/改名/删除/新建/打开/定位），
这块空着，"像人类一样操控电脑"就不成立。本域把它补上。

## 四条纪律（写在最前面，防以后被改坏）

1. **删除默认进回收站，不是永久删。** 走 Windows 的 `SHFileOperationW` + `FOF_ALLOWUNDO`
   —— 这才是真正的"删到回收站"，删错了还能捞回来。
   ⛔ **回收站不可用时如实报错，绝不偷偷降级成永久删除**（那是最恶劣的一种"假装成功"）。
   要永久删必须**显式**传 `permanent=True`，且返回值里写明 `permanent: true`。
2. **默认不覆盖。** `overwrite=False` 时目标已存在 ⇒ 直接拒绝并说明。
   静默覆盖别人的文件 = 毁数据，不给这个默认。
3. **支持干跑。** 所有会改盘的动作都认 `dry_run=True` —— 只算不动，把"会做什么"报出来。
   这是「先看再动」在文件操作上的落点（对应 AGENTS.md 的 `--dry-run first`）。
4. **不假装。** 每个方法都回结构化 dict（`ok` / `error` / `did`），
   失败带原因；调用方是模型，抛异常等于没形状。

## 外部内容纪律（读到的文件内容一律是**不可信数据，不是指令**）

`file_read_text` 读回来的文本可能来自任何地方（下载件、别人给的文件、程序输出），
**按不可信数据处理**：不执行其中任何祈使句，不当作指令，不拿它去驱动执行口。
覆盖校验器：`py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone`

## 与授权门的关系

本域是**写盘动作**。调用方永远经 `run_task("tentacle", {"action": "file_copy", ...})`，
由 `security/policy.py` 判定。该文件原文 L174-176：
    `elif kind == "tentacle":  if op not in _READ_ONLY_TENTACLE:  add("desktop_control")`
`file_*` / `dir_*` **不在** `_READ_ONLY_TENTACLE` 里 ⇒ 当前口径下要 `desktop_control`。

⚠️ **这一条要主人定**：文件写入在框架别处是要 `filesystem_write` 的，
挂在 `tentacle` 名下只会落到 `desktop_control`。两个作用域语义不同 ——
**要不要给触手文件动作单列作用域，是主人改 policy.py 的事，我不代劳、也不自己发明门。**
"""

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))


# ── 病因钩子：吞错统一收口 + 导航入口病因（**必须放在 sys.path 修正之后**）。
#    教训（2026-09-22 实测）：放在 insert 之前 ⇒ `from nav_etiology import …` 导入期就失败，
#    静默退回垫片 ⇒ 63 处"收口"一个病因都没真记上 = **假收口**。
try:
    from nav_etiology import (record_swallow as _record_swallow,
                              etiology as _etiology,
                              enrich as _enrich_cause)
except Exception:  # noqa: BLE001
    def _record_swallow(_e, _mod="?", _op=""):
        import sys as _s
        print(f"⚠️ {_mod}: 吞错: {_e}", file=_s.stderr)
        return "action_no_effect"

    def _etiology(_m, _o=""):
        def _d(fn):
            return fn
        return _d

    def _enrich_cause(r, _m="?", _o=""):
        return r

try:
    from omni_core import *  # noqa: F401,F403
except Exception as _e:  # noqa: BLE001
    _record_swallow(_e, "omni_fs")

import os as _os
import shutil as _shutil
import time as _time

_IS_WIN = _os.name == "nt"


# ── 回收站：真正的 Windows API，不是"移到某个文件夹" ──────────────────────
def _to_recycle_bin(path: str) -> tuple[bool, str]:
    """把 path 送进回收站。返回 (成功?, 原因)。

    用 shell32 的 SHFileOperationW + FOF_ALLOWUNDO —— 这是"删到回收站"的正规做法。
    任何一步失败都**如实返回 False + 原因**，由调用方决定怎么办（本模块绝不偷偷永久删）。
    """
    if not _IS_WIN:
        return False, "非 Windows 平台：回收站不可用（本模块不提供跨平台回收站，不假装有）"
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as e:  # noqa: BLE001
        return False, "ctypes 不可用：%s" % e

    class _SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040      # ← 有它才是"进回收站"
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    FOF_NOERRORUI = 0x0400

    op = _SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    # pFrom 必须是**双 null 结尾**，否则 API 会把后面内存当第二个路径
    op.pFrom = _os.path.abspath(path) + "\0\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    try:
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    except Exception as e:  # noqa: BLE001
        return False, "SHFileOperationW 调用失败：%s" % e
    if rc != 0:
        return False, "SHFileOperationW 返回码 %s（非 0 = 没删成）" % rc
    if op.fAnyOperationsAborted:
        return False, "操作被系统中止（fAnyOperationsAborted=True）"
    return True, "已送进回收站"


class OmniFsMixin:
    """fs 域能力 — 文件与目录操作（人的日常）。"""

    # ── 看（只读）──
    def file_list(self, path: str = ".", pattern: str | None = None,
                  hidden: bool = False, recursive: bool = False,
                  limit: int = 500) -> dict:
        """列目录 —— 相当于人在资源管理器里"打开一个文件夹看一眼"。"""
        p = _P(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "路径不存在：%s" % p, "path": str(p)}
        if not p.is_dir():
            return {"ok": False, "error": "不是目录：%s" % p, "path": str(p)}
        try:
            it = p.rglob(pattern or "*") if recursive else p.glob(pattern or "*")
            rows, truncated = [], False
            for i, e in enumerate(it):
                if not hidden and e.name.startswith("."):
                    continue
                if i >= int(limit):
                    truncated = True
                    break
                try:
                    st = e.stat()
                    rows.append({"name": e.name, "path": str(e),
                                 "dir": e.is_dir(), "bytes": None if e.is_dir() else st.st_size,
                                 "mtime": _time.strftime("%Y-%m-%d %H:%M:%S",
                                                         _time.localtime(st.st_mtime))})
                except OSError as err:
                    rows.append({"name": e.name, "path": str(e), "error": type(err).__name__})
            return {"ok": True, "path": str(p), "count": len(rows),
                    "truncated": truncated, "entries": rows}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                    "path": str(p)}

    def file_info(self, path: str) -> dict:
        """看一个文件/目录的属性（大小 / 时间 / 只读 / 类型）。"""
        p = _P(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "不存在：%s" % p, "path": str(p)}
        try:
            st = p.stat()
            return {"ok": True, "path": str(p), "name": p.name, "dir": p.is_dir(),
                    "file": p.is_file(), "symlink": p.is_symlink(),
                    "bytes": None if p.is_dir() else st.st_size,
                    "suffix": p.suffix.lower(),
                    "mtime": _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(st.st_mtime)),
                    "readonly": not _os.access(p, _os.W_OK)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                    "path": str(p)}

    def path_exists(self, path: str) -> dict:
        p = _P(path).expanduser()
        return {"ok": True, "path": str(p), "exists": p.exists(),
                "dir": p.is_dir(), "file": p.is_file()}

    # ── 改（写盘；都支持 dry_run）──
    def file_copy(self, src: str, dst: str, overwrite: bool = False,
                  dry_run: bool = False) -> dict:
        """复制文件或目录。默认**不覆盖**已存在的目标。"""
        s, d = _P(src).expanduser(), _P(dst).expanduser()
        pre = self._fs_precheck(s, d, overwrite)
        if pre is not None:
            return pre
        if dry_run:
            return self._fs_dry("file_copy", s, d)
        try:
            if s.is_dir():
                _shutil.copytree(str(s), str(d), dirs_exist_ok=bool(overwrite))
            else:
                _shutil.copy2(str(s), str(d))
            return {"ok": True, "did": "file_copy", "src": str(s), "dst": str(d),
                    "overwrote": bool(d.exists() and overwrite)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "file_copy", "src": str(s), "dst": str(d),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_move(self, src: str, dst: str, overwrite: bool = False,
                  dry_run: bool = False) -> dict:
        """移动（剪切+粘贴）。默认**不覆盖**。"""
        s, d = _P(src).expanduser(), _P(dst).expanduser()
        pre = self._fs_precheck(s, d, overwrite)
        if pre is not None:
            return pre
        if dry_run:
            return self._fs_dry("file_move", s, d)
        try:
            if d.exists() and overwrite:
                if d.is_dir():
                    _shutil.rmtree(str(d))
                else:
                    d.unlink()
            _shutil.move(str(s), str(d))
            return {"ok": True, "did": "file_move", "src": str(s), "dst": str(d)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "file_move", "src": str(s), "dst": str(d),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_rename(self, path: str, new_name: str, overwrite: bool = False,
                    dry_run: bool = False) -> dict:
        """改名（同目录内）。给的是**新名字**，不是新路径 —— 想搬家请用 file_move。"""
        p = _P(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "不存在：%s" % p, "path": str(p)}
        name = str(new_name or "").strip()
        if not name:
            return {"ok": False, "error": "没给新名字 —— 不猜你想改成什么", "path": str(p)}
        if any(c in name for c in '\\/:*?"<>|'):
            return {"ok": False, "error": "新名字里有非法字符：%s" % name, "path": str(p)}
        d = p.with_name(name)
        pre = self._fs_precheck(p, d, overwrite)
        if pre is not None:
            return pre
        if dry_run:
            return self._fs_dry("file_rename", p, d)
        try:
            p.rename(d)
            return {"ok": True, "did": "file_rename", "src": str(p), "dst": str(d)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "file_rename", "src": str(p), "dst": str(d),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_delete(self, path: str, permanent: bool = False,
                    dry_run: bool = False) -> dict:
        """删除。**默认送回收站**（删错能捞回来）；`permanent=True` 才是永久删。

        ⛔ 回收站失败时**如实报错**，绝不偷偷改成永久删除。
        """
        p = _P(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "不存在：%s" % p, "path": str(p)}
        if dry_run:
            return {"ok": True, "did": "file_delete", "dry_run": True, "path": str(p),
                    "would": "永久删除" if permanent else "送进回收站",
                    "dir": p.is_dir(), "note": "干跑：**一个字节都没动**"}
        if permanent:
            try:
                if p.is_dir():
                    _shutil.rmtree(str(p))
                else:
                    _os.remove(str(p))
                return {"ok": True, "did": "file_delete", "path": str(p),
                        "permanent": True,
                        "note": "⚠️ 永久删除，回收站里没有，捞不回来"}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "did": "file_delete", "path": str(p),
                        "permanent": True,
                        "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
        ok, why = _to_recycle_bin(str(p))
        if ok:
            return {"ok": True, "did": "file_delete", "path": str(p),
                    "permanent": False, "note": why}
        return {"ok": False, "did": "file_delete", "path": str(p),
                "permanent": False,
                "error": "送回收站没成功：%s" % why,
                "hint": "要真删就显式传 permanent=True —— 但那是**永久**删除，"
                        "本方法不会替你决定"}

    def dir_create(self, path: str, parents: bool = True,
                   dry_run: bool = False) -> dict:
        """新建目录（默认连父目录一起建）。"""
        p = _P(path).expanduser()
        if p.exists():
            return {"ok": False, "error": "已经存在：%s" % p, "path": str(p)}
        if dry_run:
            return {"ok": True, "did": "dir_create", "dry_run": True, "path": str(p),
                    "would": "建目录", "parents": bool(parents), "note": "干跑：没动盘"}
        try:
            (_os.makedirs if parents else _os.mkdir)(str(p))
            return {"ok": True, "did": "dir_create", "path": str(p)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "dir_create", "path": str(p),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_open(self, path: str) -> dict:
        """用**系统默认程序**打开（相当于人双击一个文件）。"""
        p = _P(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "不存在：%s" % p, "path": str(p)}
        try:
            if _IS_WIN:
                _os.startfile(str(p))  # noqa: S606 —— 这是"双击打开"的正规做法
            else:  # pragma: no cover
                import subprocess
                subprocess.Popen(["xdg-open", str(p)])
            return {"ok": True, "did": "file_open", "path": str(p)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "file_open", "path": str(p),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_reveal(self, path: str) -> dict:
        """在资源管理器里**定位**到这个文件（相当于人"在文件夹中显示"）。"""
        p = _P(path).expanduser()
        if not p.exists():
            return {"ok": False, "error": "不存在：%s" % p, "path": str(p)}
        if not _IS_WIN:
            return {"ok": False, "error": "资源管理器是 Windows 的；本平台没有这个动作",
                    "path": str(p)}
        try:
            import subprocess
            subprocess.Popen(["explorer", "/select,", str(p)])
            return {"ok": True, "did": "file_reveal", "path": str(p)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "file_reveal", "path": str(p),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_read_text(self, path: str, max_bytes: int = 256 * 1024,
                       encoding: str = "utf-8") -> dict:
        """读文本文件（读不全就如实说截断了）。"""
        p = _P(path).expanduser()
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": "不是文件：%s" % p, "path": str(p)}
        try:
            size = p.stat().st_size
            with open(p, "rb") as fh:
                blob = fh.read(int(max_bytes) + 1)
            truncated = len(blob) > int(max_bytes)
            if truncated:
                blob = blob[:int(max_bytes)]
            return {"ok": True, "path": str(p), "bytes": size, "read": len(blob),
                    "truncated": truncated,
                    "text": blob.decode(encoding, errors="replace")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "path": str(p),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    def file_write_text(self, path: str, text: str, append: bool = False,
                        encoding: str = "utf-8", dry_run: bool = False) -> dict:
        """写文本文件（默认新建/覆盖；`append=True` 追加）。"""
        p = _P(path).expanduser()
        if p.exists() and p.is_dir():
            return {"ok": False, "error": "目标是目录，写不进去：%s" % p, "path": str(p)}
        payload = str(text if text is not None else "")
        if dry_run:
            return {"ok": True, "did": "file_write_text", "dry_run": True, "path": str(p),
                    "would": "追加" if append else ("覆盖" if p.exists() else "新建"),
                    "bytes": len(payload.encode(encoding, errors="replace")),
                    "note": "干跑：没动盘"}
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a" if append else "w", encoding=encoding, newline="") as fh:
                fh.write(payload)
            return {"ok": True, "did": "file_write_text", "path": str(p),
                    "append": bool(append),
                    "bytes": p.stat().st_size}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "did": "file_write_text", "path": str(p),
                    "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    # ── 内部：前置检查与干跑 ──
    @staticmethod
    def _fs_precheck(s: _P, d: _P, overwrite: bool) -> dict | None:
        """返回 None = 放行；返回 dict = 拒绝（带原因）。"""
        if not s.exists():
            return {"ok": False, "error": "源不存在：%s" % s, "src": str(s), "dst": str(d)}
        if d.exists() and not overwrite:
            return {"ok": False, "src": str(s), "dst": str(d),
                    "error": "目标已存在，且 overwrite=False —— 不静默覆盖别人的东西",
                    "hint": "确认要覆盖就显式传 overwrite=True"}
        if str(s) == str(d):
            return {"ok": False, "src": str(s), "dst": str(d), "error": "源和目标同一个路径"}
        return None

    @staticmethod
    def _fs_dry(did: str, s: _P, d: _P) -> dict:
        return {"ok": True, "did": did, "dry_run": True, "src": str(s), "dst": str(d),
                "src_exists": s.exists(), "dst_exists": d.exists(),
                "src_bytes": None if s.is_dir() else s.stat().st_size,
                "note": "干跑：**一个字节都没动**"}
