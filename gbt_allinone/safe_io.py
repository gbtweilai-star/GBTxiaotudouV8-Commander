# gbt-capability: filesystem
"""统一安全 I/O：路径边界、跨进程锁、原子写与 JSON 更新。

目标不是削弱能力，而是让所有已有能力在崩溃、并发和异常路径下保持一致：
- 路径必须落在调用方声明的根目录内；
- 读改写必须持跨进程锁；
- 文件先完整写入同目录临时文件，再原子替换；
- 写后 fsync，降低掉电或进程崩溃造成半文件的风险。
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable


class SafeIOError(ValueError):
    """路径、锁或持久化参数不符合安全约束。"""


class WriteRejected(SafeIOError):
    """写入被 validator 拒绝 —— **目标文件保持原样**（R97 · 改法 1）。

    R97 复核补充：validator 跑在 `mkstemp` **之前**，所以拒绝路径**不产生任何文件**，
    `tmp` 恒为空串 `""`（早先"先建临时文件、拒绝时 finally unlink"那版已作废）。
    """

    def __init__(self, path, reason, tmp):
        super().__init__("写入被拒绝：%s（%s）" % (path, reason))
        self.path = path
        self.reason = reason
        self.tmp = tmp

def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def safe_relative_path(root: Path | str, value: str, *, allow_empty: bool = False) -> Path:
    """把调用方路径解析到 root 内，拒绝绝对路径、盘符、UNC、NUL 与父级逃逸。"""
    raw = str(value or "")
    if "\x00" in raw:
        raise SafeIOError("路径包含 NUL 字符")
    if not raw.strip():
        if allow_empty:
            return Path(root).resolve()
        raise SafeIOError("路径不能为空")
    if Path(raw).is_absolute() or PurePosixPath(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
        raise SafeIOError("只允许根目录内的相对路径")
    win = PureWindowsPath(raw)
    if win.drive or win.root:
        raise SafeIOError("路径不能包含盘符或 UNC 根")
    posix = PurePosixPath(raw.replace("\\", "/"))
    if any(part in ("", ".", "..") for part in posix.parts):
        raise SafeIOError("路径不能包含空段、当前目录或父级跳转")
    root_resolved = Path(root).expanduser().resolve()
    candidate = (root_resolved / Path(*posix.parts)).resolve()
    if not _is_within(root_resolved, candidate) or candidate == root_resolved:
        raise SafeIOError("路径越界：目标不在允许根目录内")
    return candidate


def _fsync_dir(path: Path) -> None:
    """POSIX 上同步目录项；Windows 不提供等价的可移植目录 fsync。"""
    if os.name == "nt":
        return
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


NEWLINE_CRLF = "\r\n"
NEWLINE_LF = "\n"


def align_newlines(text: str, newline: str) -> str:
    """把 text 里所有换行形态（\r\n / \r / \n）统一成 newline。"""
    if newline not in (NEWLINE_CRLF, NEWLINE_LF):
        raise SafeIOError("newline 只允许 '\\r\\n' 或 '\\n'")
    return str(text).replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)


def newline_profile(path: Path | str) -> dict:
    """byte 级只读目标文件，给出换行符分布。不写盘、不改盘。"""
    target = Path(path)
    if not target.exists():
        return {"exists": False, "bytes": 0, "crlf": 0, "lf": 0, "bare_cr": 0,
                "dominant": "", "mixed": False}
    data = target.read_bytes()
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    bare_cr = data.count(b"\r") - crlf
    kinds = [k for k, n in (("crlf", crlf), ("lf", lf), ("bare_cr", bare_cr)) if n]
    return {"exists": True, "bytes": len(data), "crlf": crlf, "lf": lf, "bare_cr": bare_cr,
            "dominant": NEWLINE_CRLF if crlf > lf else (NEWLINE_LF if lf > crlf else ""),
            "mixed": len(kinds) > 1}


def detect_newline(path: Path | str, *, default: str = NEWLINE_LF) -> str:
    """写入**之前**先读目标文件，返回它的主流换行符（风哥 2026-09-17 批）。

    主流 CRLF -> "\r\n"；主流 LF -> "\n"。
    文件不存在 / 空 / 无换行 / 两形态打平 -> 返回 default。
    """
    prof = newline_profile(path)
    if not prof["exists"] or not prof["dominant"]:
        return default
    return prof["dominant"]


def _anchor_newline(anchor: str) -> str:
    """锚点自身若只带一种换行形态，用它当兜底（目标混行尾打平时用）。"""
    crlf = str(anchor).count("\r\n")
    lf = str(anchor).count("\n") - crlf
    if crlf and not lf:
        return NEWLINE_CRLF
    if lf and not crlf:
        return NEWLINE_LF
    return ""


def _py_syntax_validator(data: bytes, path: str) -> None:
    """`.py` 默认 validator：**在 bytes 层**做语法检查，零字节落盘。

    为什么是 bytes 而不是 str：CRLF / BOM / 编码声明走**同一套 PEP 263 解码**，
    与最终落盘字节完全一致 —— 避免「校验的内容 ≠ 写入的内容」。
    两条实测反例（R97，都写进契约测试）：
      · latin-1 声明且含 0xE9 字节 -> 先 decode("utf-8") 再 compile 抛 UnicodeDecodeError；
      · UTF-8 BOM 开头 -> 先 decode 再 compile 抛 SyntaxError: invalid non-printable U+FEFF。
    （更正：`compile(str)` 带 coding cookie 在 CPython 3.10 **不抛** —— 早先那条理由作废。）

    为什么用 `compile()` 而不是 `py_compile`：后者会往 `__pycache__/` 落 `.pyc`，
    会让「目标目录零新增文件」的判据变成**假绿**。

    已知 limitation：校验的是**当前解释器**的语法（本机 CPython 3.10.11），
    **不保证目标运行时等价** —— `match` / `type` 语句之类在新旧解释器之间会假绿或假红。
    不假装它能跨版本。（`dont_inherit=True` 实测 3.10 下无差异，故不写。）

    R97 复核补充（风哥 2026-09-18 拍「三条实证全补」）：
      · 未知 cookie —— `# -*- coding: bogus-9 -*-` 抛 `SyntaxError: unknown encoding: ...`
        （底层是 `LookupError`，被 tokenizer 包成 SyntaxError）。同内容走 `compile(str)`
        **放行（假绿）** —— str 路径根本不读 cookie。cookie 名还带**前缀归一化**：
        `utf-8-extra` 这种不存在的名字会被当成 `utf-8` 放行 —— 本 validator 只保证
        「按声明的编码能解码 + 能编译」，**不保证 cookie 名真实存在**。
      · BOM（EF BB BF 开头）—— bytes 放行；先 `decode("utf-8")` 再 compile 是**假红**
        （`invalid non-printable character U+FEFF`），要 `utf-8-sig` 才对。本仓实测
        **10 个 `.py` 是 BOM 开头**（全在 `gbt_allinone/`）—— str 路径会让它们整体假红。
      · NUL 字节 —— `ValueError: source code string cannot contain null bytes`，
        位置无关（注释 / 字符串字面量 / docstring 内都一样）。
        **R-H295 更正**：这个**类型**在 Python 3.14 起变了 —— 3.14 抛的是
        `SyntaxError: source code string cannot contain null bytes`。本仓声明口径是
        3.14.5，所以下面那句按类型写的老口径在声明口径上就是错的。
        现按**消息**判定并把 NUL 归一化回 `ValueError` 上报（见下方 except 分支），
        使 reason 跨解释器稳定。
      可达性（`compile()` 这条路径实测）：语法坏 -> SyntaxError；cookie 名不存在（含 BOM
      冲突）-> SyntaxError；非 UTF-8 坏字节 -> **SyntaxError（被包装）**；源码含 NUL ->
      ValueError。**`UnicodeDecodeError` 在本路径不可达** —— 它只在
      `tokenize.detect_encoding()` + 显式 `.decode()` 那条路径上裸露
      （风哥 2026-09-18 撤回「它是本路径的第三型」）。
    """
    try:
        compile(data, path, "exec")
    except (SyntaxError, ValueError) as exc:
        # R-H295：NUL 字节的**异常类型随解释器漂了** —— 3.13 及以前是
        # `ValueError: source code string cannot contain null bytes`，3.14 起改成
        # `SyntaxError: ...`。本仓声明口径是 3.14.5，于是 docstring 里写的那条
        # 与 test_safe_io 「reason 必须是 ValueError」**在声明口径上长期是红的**。
        # 类型会漂、语义不会：按**消息**判定，把 NUL 这一类归一化成 ValueError 上报，
        # 跨解释器稳定，也让 reason 与契约一致（不是把测试改绿，是把上报口径钉住）。
        _name = type(exc).__name__
        if "null bytes" in str(exc):
            _name = "ValueError"
        raise WriteRejected(str(path), "%s: %s" % (_name, exc), "") from exc
    except Exception as exc:   # 兜底（风哥 2026-09-18 拍）
        # 约束（风哥 2026-09-18 补）：兜底要**窄** —— 只兜 `compile()` 的前置错误
        # （`LookupError` / `TypeError` 这类），reason 保留**原始类型名**
        # （形如 `validator_unexpected: LookupError`）。不许长成第二个万能兜底。
        raise WriteRejected(str(path), "validator_unexpected: %s" % type(exc).__name__, "") from exc


def _default_validator(target: Path):
    """按目标后缀选默认 validator；非 `.py` 返回 None（逐字节不变）。"""
    return _py_syntax_validator if str(target).lower().endswith(".py") else None


def atomic_write_bytes(path: Path | str, data: bytes, *, mode: int | None = None,
                       validator: Callable[[bytes, str], None] | None = None) -> Path:
    """同目录临时文件 + fsync + os.replace，保证读者只会看到旧版或完整新版。

    validator(data, path)（R97 · 改法 1）：**先校验、后 mkstemp** —— 拒绝路径结构上
    **不产生任何文件**。validator 抛 `WriteRejected` -> 原样透传；抛 `SyntaxError` /
    `ValueError`（`UnicodeDecodeError` 是它的子类，已含在内）-> 包成 `WriteRejected`；
    其余异常原样上抛 —— 不许吞，外部 validator 的 bug 不该被伪装成「内容不合法」。
    注：`compile()` 路径上 `UnicodeDecodeError` **不可达**（实测：非 UTF-8 坏字节被
    tokenizer 包成 `SyntaxError`），只在 `tokenize.detect_encoding()` + 显式 `.decode()`
    那条路径上裸露 —— 所以本元组只留两型，不留死 `except`。
    NUL 字节抛的是 `ValueError: source code string cannot contain null bytes` ——
    只抓 SyntaxError 会让它逃出去变成未捕获崩溃。

    权限：`os.replace` 是整体替换，mkstemp 的临时文件权限会顶掉目标原权限 ——
    所以替换前按**目标原 mode** 回填（目标不存在则保持 mkstemp 结果）。
    目录 fsync 走 `_fsync_dir()`（Windows 不支持目录 fsync，函数内已提前返回）。
    默认 `None` = 逐字节直写，既有调用点行为不变。
    """
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    blob = data if isinstance(data, (bytes, bytearray)) else bytes(data)
    if validator is not None:
        try:
            validator(bytes(blob), str(target))
        except WriteRejected:
            raise
        except (SyntaxError, ValueError) as exc:
            raise WriteRejected(str(target), "%s: %s" % (type(exc).__name__, exc),
                                "") from exc
    keep_mode = mode
    if keep_mode is None:
        try:
            keep_mode = os.stat(target).st_mode & 0o777
        except OSError:
            keep_mode = None
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        if keep_mode is not None:
            try:
                os.chmod(tmp, keep_mode)
            except OSError:
                pass
        os.replace(tmp, target)
        _fsync_dir(target.parent)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return target

def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8",
                      mode: int | None = None, align_to_existing: bool = False,
                      default_newline: str = NEWLINE_LF) -> Path:
    """原子写文本。

    align_to_existing=True 时，**先读目标文件换行符再对齐**（源头防线）；
    默认 False = 逐字节直写，保持既有调用点行为不变（风哥口径：默认行为不动）。
    """
    body = str(text)
    if align_to_existing:
        body = align_newlines(body, detect_newline(path, default=default_newline))
    return atomic_write_bytes(path, body.encode(encoding), mode=mode)


def atomic_write_text_aligned(path: Path | str, text: str, *, encoding: str = "utf-8",
                              mode: int | None = None,
                              default_newline: str = NEWLINE_LF,
                              verify: bool = True) -> Path:
    """**文档写入层的默认入口**：检测目标换行符 -> 新增内容按它对齐 -> 原子写 -> 写完自证。

    自证（不是"事后修"）：写盘后重读目标，若仍是混行尾则报 SafeIOError。
    """
    target = Path(path).expanduser().resolve()
    body = align_newlines(str(text), detect_newline(target, default=default_newline))
    atomic_write_bytes(target, body.encode(encoding), mode=mode)
    if verify:
        prof = newline_profile(target)
        if prof["mixed"]:
            raise SafeIOError(
                "写入后自证失败：%s 仍是混行尾（crlf=%d lf=%d bare_cr=%d）"
                % (target, prof["crlf"], prof["lf"], prof["bare_cr"]))
    return target


def edit_text_once(path: Path | str, old: str, new: str, *, expected: int = 1,
                   encoding: str = "utf-8", verify: bool = True,
                   default_newline: str = NEWLINE_LF,
                   newline: str | None = None) -> dict:
    """外科式改写：只替换 old -> new 命中处，**其余行行尾原样保留**（不整文档归一化）。

    old / new 里的换行符先对齐到目标文件的主流形态；
    目标混行尾打平 / 无换行时，用锚点自带的形态兜底，锚点也给不出则用 default_newline。
    **newline=None（默认）** -> 按目标**主流**形态拼行（现行行为，默认不动）；
    **newline="\r\n" / "\n"** -> **显式覆盖**主流 —— 目标**区段混行尾**时用
    （实证 `tests/test_framework.py`：主流 CRLF，命中行落在纯 LF 区段），
    否则新增行按主流拼 = 往纯 LF 区段里灌 CRLF。参数只收 "\r\n" / "\n"，其余抛 SafeIOError。
    命中数 != expected -> 不写盘，返回 {"ok": False, "reason": "anchor_count"}。
    `.py` 目标额外过语法 validator（R97 · 改法 1）：语法坏 -> 抛 `WriteRejected`，目标不动。
    往 `.py` **分步插入**时，每一步都必须自身语法完整 —— 否则中间态会被 validator 判红。
    """
    target = Path(path).expanduser().resolve()
    prof = newline_profile(target)
    if not prof["exists"]:
        return {"ok": False, "reason": "missing_target", "path": str(target),
                "count": 0, "written": False}
    if newline is None:
        nl = prof["dominant"] or _anchor_newline(old) or default_newline
        nl_source = "dominant"
    else:
        if newline not in (NEWLINE_CRLF, NEWLINE_LF):
            raise SafeIOError("newline 只允许 '\\r\\n' 或 '\\n'")
        nl = newline
        nl_source = "explicit"
    raw = target.read_bytes().decode(encoding)
    old_aligned = align_newlines(old, nl)
    new_aligned = align_newlines(new, nl)
    count = raw.count(old_aligned)
    if count != expected:
        return {"ok": False, "reason": "anchor_count", "path": str(target),
                "expected": expected, "count": count, "newline": nl, "written": False}
    out = raw.replace(old_aligned, new_aligned, expected)
    atomic_write_bytes(target, out.encode(encoding), validator=_default_validator(target))
    prof_after = newline_profile(target)
    result = {"ok": True, "reason": "ok", "path": str(target), "expected": expected,
              "count": count, "newline": nl, "newline_source": nl_source, "written": True,
              "mixed_before": prof["mixed"], "mixed_after": prof_after["mixed"],
              "bytes_before": prof["bytes"], "bytes_after": prof_after["bytes"]}
    if verify and prof_after["mixed"] and not prof["mixed"]:
        result["ok"] = False
        result["reason"] = "verify_mixed_after_write"
    return result


def insert_lines_aligned(path: Path | str, anchor: str, addition: str, *,
                         position: str = "after", expected: int = 1,
                         encoding: str = "utf-8") -> dict:
    """按锚点插入新增行 —— 补丁脚本专用入口（《写入必须同换行符》源头防线）。

    规则：**先读目标文件的换行符**，锚点串与新增内容都按它拼行；
    命中数 != expected -> 不写盘，返回原因（不许"写完再修"）。
    position 只允许 "after" / "before"。

    **插入点自动归位到行边界（甲案 · R105）** —— 插入点不在行边界时，先把命中区
    搬到行边界再插，**不要求调用方自带前导换行**：

      · ``position="after"``：插入点 = 命中区**末尾**。锚点末字符之后**不是行尾**时，
        吃掉锚点**自带**的那一个行尾（``甲\r\n`` -> ``甲\r\n新增``）；后面没有行尾
        可吃才补一个，让新增行独立成行；
      · ``position="before"``：插入点 = 命中区**开头**。**前一字符不是行尾**时，在
        ``addition`` 前补一个行尾；锚点已在行首**不补** —— 补了会多出一个空行。

    改前六型实测（``.scratch/_r105p_ilal_exact.py``，逐字节）：
      锚点自带行尾（现有 11 处契约调用的形态）-> 结果**逐字节不变**（不重复补）；
      ``addition`` 仍需**自带结尾换行**（这条没变）—— 不补尾，新增行会与下一行粘连。

    ``addition`` 为空串 -> **原样重写一次**（`written=True`，内容**逐字节不变**）——
    **不是**「拒绝写盘」；本刀**不新增守卫**（加守卫 = 改默认行为），别按「拒绝写盘」去加。
    命中数 != expected -> 不写盘。``expected > 1`` 时行边界按**首次命中**判定。
    `.py` 目标继承 `edit_text_once` 的语法 validator（R97 · 改法 1）——
    分步插入要每步语法完整；拼不完整就改一次性整块替换，**不许放宽 validator**。

    注：判定行边界要**读一次目标**，随后 ``edit_text_once`` **再读一次**并复核命中数 ——
    两次读之间目标若被改动，命中数对不上就**不写盘**（失败方向安全）。
    """
    if position not in ("after", "before"):
        raise SafeIOError("position 只允许 'after' 或 'before'")
    target = Path(path).expanduser().resolve()
    prof = newline_profile(target)
    if not prof["exists"]:
        body = addition + anchor if position == "before" else anchor + addition
        return edit_text_once(target, anchor, body, expected=expected, encoding=encoding)
    nl = prof["dominant"] or _anchor_newline(anchor) or NEWLINE_LF
    raw = target.read_bytes().decode(encoding)
    old = align_newlines(anchor, nl)
    add = align_newlines(addition, nl)
    new = old + add if position == "after" else add + old
    if raw.count(old) == expected:
        idx = raw.find(old)
        if position == "after":
            if not old.endswith(nl):
                tail = raw[idx + len(old): idx + len(old) + len(nl)]
                if tail == nl:
                    old = old + nl
                    new = old + add
                else:
                    new = old + nl + add
        else:
            at_head = idx == 0 or raw[max(0, idx - len(nl)): idx] == nl
            if not at_head:
                new = nl + add + old
    return edit_text_once(target, old, new, expected=expected, encoding=encoding)




def atomic_write_json(path: Path | str, data: Any, *, indent: int | None = 2,
                      ensure_ascii: bool = False, mode: int | None = None) -> Path:
    text = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent, default=str)
    try:
        return atomic_write_text(path, text + "\n", mode=mode)
    except UnicodeEncodeError:
        # 🔴 2026-10-19 实测撞出来的（F3 同族）：payload 里混进**孤立代理对**（\udxxx）时，
        #    `ensure_ascii=False` 会把它原样写进文件，utf-8 编码当场抛 `surrogates not allowed`
        #    ⇒ 上层 preflight 把这次写当成"感知层故障"，对**有副作用**的调用 fail-closed 拒掉。
        #    正确姿势：**落盘要稳** —— 改用 `ensure_ascii=True` 重写（代理对转义成 \\udxxx，
        #    JSON 合法、读回来还是同一串字符）。语义不变，只是把"写不下去"变成"写完能读回"。
        text = json.dumps(data, ensure_ascii=True, indent=indent, default=str)
        return atomic_write_text(path, text + "\n", mode=mode)


def locked_append_text(path: Path | str, text: str, *, encoding: str = "utf-8",
                        lock_timeout: float = 30.0, align_to_existing: bool = False,
                        default_newline: str = NEWLINE_LF) -> Path:
    """在跨进程锁内追加文本并 fsync，保证 JSONL/日志行不会交错或半落盘。

    align_to_existing=True 时在**锁内**读目标主流换行符并对齐追加内容
    （锁内读，避开"读-写"竞争）；默认 False = 行为不变。
    """
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(target.name + ".lock")
    with FileLock(lock_path, timeout=lock_timeout):
        body = str(text)
        if align_to_existing:
            body = align_newlines(body, detect_newline(target, default=default_newline))
        with open(target, "a", encoding=encoding, newline="") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
    return target


def load_json(path: Path | str, default: Any = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return default


class FileLock:
    """跨进程协作锁；Windows 使用 msvcrt，POSIX 使用 fcntl。"""

    def __init__(self, path: Path | str, timeout: float = 30.0, poll: float = 0.05):
        self.path = Path(path).expanduser().resolve()
        self.timeout = max(0.0, float(timeout))
        self.poll = max(0.01, float(poll))
        self._fh = None

    def acquire(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+b")
        if self.path.stat().st_size == 0:
            self._fh.write(b"\0")
            self._fh.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fh.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError as exc:
                if time.monotonic() >= deadline:
                    self._fh.close()
                    self._fh = None
                    raise TimeoutError(f"获取文件锁超时: {self.path}") from exc
                time.sleep(self.poll)

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            self._fh.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "FileLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def locked_json_update(path: Path | str, default: Any, mutator: Callable[[Any], Any] | None = None,
                       *, lock_timeout: float = 30.0):
    """持锁读取 JSON、调用 mutator、原子落盘，返回 mutator 的返回值。

    mutator 为 None 时只保证读改写临界区，返回更新后的数据。
    """
    target = Path(path).expanduser().resolve()
    lock_path = target.with_name(target.name + ".lock")
    with FileLock(lock_path, timeout=lock_timeout):
        data = load_json(target, default)
        result = mutator(data) if mutator else data
        atomic_write_json(target, data)
    return result
