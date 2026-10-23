# gbt-capability: 多维穷尽扫描引擎（藏匿面 · 覆盖闭合自证）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""多维穷尽扫描引擎 —— **扫过之处，无所遁形**。

Owner 2026-09-22：「扫描的能力也全方位多维度补齐，必须实现扫过之处所有东西无所遁形」

═══ 与既有 6 台扫描器的分工（不另立第二套真相）═══
  `code_exhaustive_scan`  —— 管"**每一行**有没有毛病"（已立闭合律：枚举 = 扫过 + 写明原因没扫）
  `cross_scan`            —— 管"**关系**"无死角（注册表↔路由↔导入↔影子↔运行时可达）
  `host_security_scan`    —— 管主机面安全
  `caps_called_audit`     —— 管能力位有没有人调
  `coverage_auditor`      —— 管触手覆盖矩阵
  `scan_scope`            —— 管**扫描范围口径**（谁扫仓都从它取，不许各自抄一份）
  本模块补的是**藏匿面**：一个文件"是它看起来的那个东西吗、它躲在哪、谁在装成别人"。
  上面六台都不管这个 —— 藏得好的东西，在"逐行"和"关系"里都是**看不见**的。

═══ "无所遁形"落成什么（本模块的立身之本）═══
  ① **覆盖闭合律**（沿用 code_exhaustive_scan 的口径并扩展到三桶）：
         枚举到的文件  ==  已扫 + 已声明排除 + 读不到
     三桶相加对不上，就是"有东西藏起来了" ⇒ 判红。**这不是自检，是恒等式。**
  ② **维度必须登记**：每一维在 `DIMENSIONS` 里有名、有规则号、有"它抓什么"。
     没登记的维度 = 不存在的维度；扫不动的维度必须如实报 `unavailable`，不许装作扫过。
  ③ **两把对照**：正对照（种进去的藏匿样本必须被抓到）+ 负对照（干净文件不许误报）。
     只有一边的检测器是瞎的。

用法：
    py -3.14 -m gbt_allinone.tools.scan_engine                      # 默认 scope
    py -3.14 -m gbt_allinone.tools.scan_engine --mode full --json
    py -3.14 -m gbt_allinone.tools.scan_engine --mode deep
    py -3.14 -m gbt_allinone.tools.scan_engine --selftest           # 两把对照
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_scope import EXTERNAL_CORPORA, SKIP_DIRS, TOOLING_DIRS  # noqa: E402

# ─────────────────────────────────────────────────────────── 维度登记表

DIMENSIONS = (
    ("D1", "覆盖闭合", "GBT-SE-000", "枚举总数是否等于三桶之和（藏起来的必然对不上账）"),
    ("D2", "类型分布", "GBT-SE-001", "按真实种类归类：代码/文本/图/音/视频/模型/字体/归档/二进制/数据"),
    ("D3", "扩展名分布", "GBT-SE-002", "每个后缀的文件数与体积（找出没人管的野后缀）"),
    ("D4", "伪装检测", "GBT-SE-010", "后缀说的和**头几个字节**说的不是一回事 ⇒ 改名伪装"),
    ("D5", "名称诡计", "GBT-SE-020", "双后缀 / 结尾空格或点 / 零宽与双向控制字符（肉眼看不见的名字）"),
    ("D6", "撞名危险", "GBT-SE-030", "仅大小写不同 / 仅 Unicode 规范化形式不同 ⇒ 在 Windows 上会互相覆盖"),
    ("D7", "备用数据流", "GBT-SE-040", "NTFS ADS：正经文件背后挂的隐藏流（资源管理器看不见）"),
    ("D8", "属性藏匿", "GBT-SE-050", "隐藏/系统属性、重解析点（软链/联接，可指向仓外）"),
    ("D9", "内容痕迹", "GBT-SE-060", "空文件 / 单行超长 / NUL 字节 / 疑似密钥（**只报掩码**）/ 编码坏字符"),
    ("D10", "时间异常", "GBT-SE-070", "未来时间戳 / 时间倒挂 / 最近改动聚集"),
    ("D11", "体量与深度", "GBT-SE-080", "超大文件、超深嵌套、超长路径（藏东西的常用姿势）"),
    ("D12", "重复内容", "GBT-SE-090", "逐字节相同的多份副本（同内容不同名 = 换皮）"),
)

SEV_ORDER = {"error": 0, "warn": 1, "info": 2}

# 后缀 -> 真实种类
KIND_BY_EXT = {
    ".py": "代码", ".pyi": "代码", ".js": "代码", ".cjs": "代码", ".mjs": "代码",
    ".ts": "代码", ".tsx": "代码", ".jsx": "代码", ".ps1": "代码", ".psm1": "代码",
    ".bat": "代码", ".cmd": "代码", ".sh": "代码", ".c": "代码", ".h": "代码",
    ".cpp": "代码", ".hpp": "代码", ".cs": "代码", ".java": "代码", ".go": "代码",
    ".rs": "代码", ".rb": "代码", ".php": "代码", ".lua": "代码", ".sql": "代码",
    ".html": "网页", ".htm": "网页", ".css": "网页", ".scss": "网页", ".vue": "网页",
    ".md": "文本", ".txt": "文本", ".rst": "文本", ".log": "文本", ".csv": "文本",
    ".tsv": "文本", ".json": "数据", ".jsonl": "数据", ".yaml": "数据", ".yml": "数据",
    ".toml": "数据", ".ini": "数据", ".cfg": "数据", ".conf": "数据", ".xml": "数据",
    ".db": "数据", ".sqlite": "数据", ".sqlite3": "数据", ".parquet": "数据",
    ".png": "图像", ".jpg": "图像", ".jpeg": "图像", ".gif": "图像", ".bmp": "图像",
    ".webp": "图像", ".ico": "图像", ".tif": "图像", ".tiff": "图像", ".svg": "图像",
    ".psd": "图像", ".avif": "图像", ".heic": "图像",
    ".wav": "音频", ".mp3": "音频", ".flac": "音频", ".ogg": "音频", ".m4a": "音频",
    ".aac": "音频", ".wma": "音频", ".opus": "音频",
    ".mp4": "视频", ".mov": "视频", ".avi": "视频", ".mkv": "视频", ".webm": "视频",
    ".flv": "视频", ".wmv": "视频", ".m4v": "视频",
    ".onnx": "模型", ".pt": "模型", ".pth": "模型", ".safetensors": "模型",
    ".ckpt": "模型", ".h5": "模型", ".tflite": "模型", ".gguf": "模型", ".bin": "模型",
    ".ttf": "字体", ".otf": "字体", ".woff": "字体", ".woff2": "字体", ".ttc": "字体",
    ".zip": "归档", ".7z": "归档", ".rar": "归档", ".tar": "归档", ".gz": "归档",
    ".bz2": "归档", ".xz": "归档", ".whl": "归档", ".jar": "归档",
    ".exe": "可执行", ".dll": "可执行", ".so": "可执行", ".dylib": "可执行",
    ".pyc": "可执行", ".msi": "可执行", ".sys": "可执行", ".com": "可执行",
    ".glb": "三维", ".gltf": "三维", ".fbx": "三维", ".obj": "三维", ".vrm": "三维",
    ".stl": "三维", ".blend": "三维",
    ".pdf": "文档", ".docx": "文档", ".doc": "文档", ".xlsx": "文档", ".xls": "文档",
    ".pptx": "文档", ".ppt": "文档", ".epub": "文档",
}
# 魔数 -> 真实种类（用于 D4 伪装检测）
MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "图像/png"),
    (b"\xff\xd8\xff", "图像/jpeg"),
    (b"GIF87a", "图像/gif"), (b"GIF89a", "图像/gif"),
    (b"BM", "图像/bmp"),
    (b"RIFF", "容器/riff(wav|webp|avi)"),
    (b"%PDF-", "文档/pdf"),
    (b"PK\x03\x04", "归档/zip(docx|xlsx|pptx|jar|whl)"),
    (b"PK\x05\x06", "归档/zip(空)"),
    (b"7z\xbc\xaf\x27\x1c", "归档/7z"),
    (b"Rar!\x1a\x07", "归档/rar"),
    (b"\x1f\x8b", "归档/gzip"),
    (b"BZh", "归档/bzip2"),
    (b"\xfd7zXZ\x00", "归档/xz"),
    (b"MZ", "可执行/pe"),
    (b"\x7fELF", "可执行/elf"),
    (b"SQLite format 3\x00", "数据/sqlite"),
    (b"\xd0\xcf\x11\xe0", "文档/ole(doc|xls|ppt)"),
    (b"OggS", "音频/ogg"),
    (b"ID3", "音频/mp3"),
    (b"fLaC", "音频/flac"),
    (b"\x1aE\xdf\xa3", "视频/matroska(webm|mkv)"),
    (b"glTF", "三维/glb"),
    (b"{\\rtf", "文档/rtf"),
)
# 后缀"应该"是什么种类（用于伪装比对；只比对高置信度的）
EXT_EXPECT = {
    ".png": "图像/png", ".jpg": "图像/jpeg", ".jpeg": "图像/jpeg",
    ".gif": "图像/gif", ".bmp": "图像/bmp", ".pdf": "文档/pdf",
    ".zip": "归档/zip(docx|xlsx|pptx|jar|whl)",
    ".7z": "归档/7z", ".rar": "归档/rar",
    ".gz": "归档/gzip", ".exe": "可执行/pe", ".dll": "可执行/pe",
    ".sqlite": "数据/sqlite", ".sqlite3": "数据/sqlite",
    ".wav": "容器/riff(wav|webp|avi)", ".webp": "容器/riff(wav|webp|avi)",
    ".avi": "容器/riff(wav|webp|avi)", ".ogg": "音频/ogg",
    ".mp3": "音频/mp3", ".flac": "音频/flac",
    ".mkv": "视频/matroska(webm|mkv)", ".webm": "视频/matroska(webm|mkv)",
    ".gltf": "三维/gltf", ".glb": "三维/glb",
}
ZW_AND_BIDI = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF} | set(range(0x202A, 0x202F)) | {0x2066, 0x2067, 0x2068, 0x2069}
SECRET_PATTERNS = (
    ("GBT-SE-061", re.compile(r"\bsk-[A-Za-z0-9]{16,}"), "OpenAI 风格 sk- 密钥"),
    ("GBT-SE-062", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS AccessKeyId"),
    ("GBT-SE-063", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    ("GBT-SE-064", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    ("GBT-SE-065", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "PEM 私钥块"),
    ("GBT-SE-066", re.compile(r"(?i)\b(api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
     "赋值式凭据"),
)
TEXT_EXT_HINT = {"文本", "代码", "网页", "数据"}
# 双后缀伪装要用到的两套：**看着无害的** ↔ **真能执行/加载的**
PRETEND_EXTS = {".txt", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".pdf", ".doc", ".docx",
                ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md", ".log", ".mp3", ".mp4",
                ".avi", ".zip", ".rar", ".dat", ".tmp", ".bak", ".ini", ".cfg", ".dwg"}
DANGER_EXTS = {".exe", ".dll", ".scr", ".bat", ".cmd", ".ps1", ".psm1", ".js", ".vbs",
               ".vbe", ".jar", ".com", ".pif", ".msi", ".hta", ".wsf", ".wsh", ".lnk",
               ".reg", ".cpl", ".sys", ".drv", ".ocx"}
# 代码类后缀也算"看着无害"：`x.py.exe` / `x.js.exe` 正是最经典的骗法
# （第一版漏了 `evil.py.exe` —— **对照抓出来的**：PRETEND 里只有文档/媒体后缀）
CODE_PRETEND = {".py", ".pyw", ".js", ".ts", ".sh", ".rb", ".pl", ".php", ".html",
                ".htm", ".xml", ".json", ".yml", ".yaml", ".sql", ".css", ".java",
                ".cs", ".go", ".rs", ".c", ".h", ".cpp", ".ps1", ".bat", ".cmd"}
# 真身是这些「强二进制」却挂着文本/代码/网页后缀 ⇒ 把二进制藏成文本
STRONG_BINARY_PREFIX = ("图像/", "文档/", "归档/", "可执行/", "音频/", "视频/",
                        "模型/", "三维/", "容器/", "数据/sqlite")
HIDE_AS = {"文本", "代码", "网页"}
MAX_LINE_BYTES = 1 << 20          # 单行 > 1 MiB 视为异常
DEEP_MAX_BYTES = 4 << 20          # deep 模式逐文件读上限
DEEP_MAX_FILES = 4000             # deep 模式最多读多少个文件（防失控）


# ─────────────────────────────────────────────────────────── 小工具

def _kind_of(name: str) -> str:
    return KIND_BY_EXT.get(Path(name).suffix.lower(), "未知")


def _magic_of(path: Path) -> str:
    """读头 16 字节判真实种类。读不到就返回 '(读不到)'，不猜。"""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return "(读不到)"
    if not head:
        return "(空)"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "视频/mp4"
    if head[:4] == b"glTF":
        # GLB 布局：字节 **0..4 = 魔数 "glTF"**、4..8 = 版本、8..12 = 总长度。
        # 第一版我把签名当成在 8..12（那其实是长度）⇒ 仓里 36 个真 .glb 全被报成"伪装"。
        # 教训：魔数偏移记错，检测器就变成噪音制造器。
        return "三维/glb"
    for sig, kind in MAGIC:
        if head.startswith(sig):
            return kind
    printable = sum(1 for b in head if 9 <= b <= 13 or 32 <= b <= 126 or b >= 0x80)
    if printable == len(head):
        return "文本类"
    return "二进制/未知"


def _ads_streams(path: Path, _cache={}):                      # noqa: B006
    """NTFS 备用数据流。返回 (可用?, 额外流列表)。不可用时如实报 unavailable。"""
    if os.name != "nt":
        return False, []
    if "k" not in _cache:
        try:
            k = ctypes.WinDLL("kernel32", use_last_error=True)

            class _FD(ctypes.Structure):
                _fields_ = [("StreamSize", ctypes.c_longlong),
                            ("cStreamName", wintypes.WCHAR * (260 + 36))]

            k.FindFirstStreamW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                           ctypes.POINTER(_FD), wintypes.DWORD]
            k.FindFirstStreamW.restype = wintypes.HANDLE
            k.FindNextStreamW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_FD)]
            k.FindNextStreamW.restype = wintypes.BOOL
            k.FindClose.argtypes = [ctypes.c_void_p]
            _cache["k"], _cache["fd"] = k, _FD
        except Exception:                                       # noqa: BLE001
            _cache["k"] = None
    k = _cache.get("k")
    if k is None:
        return False, []
    d = _cache["fd"]()
    h = k.FindFirstStreamW(str(path), 0, ctypes.byref(d), 0)
    if h in (-1, 0xFFFFFFFFFFFFFFFF, None):
        return False, []
    extra = []
    try:
        if d.cStreamName != "::$DATA":
            extra.append(d.cStreamName)
        while k.FindNextStreamW(h, ctypes.byref(d)):
            if d.cStreamName != "::$DATA":
                extra.append(d.cStreamName)
    finally:
        k.FindClose(h)
    return True, extra


def _file_attrs(path: Path):
    try:
        st = path.stat(follow_symlinks=False)
        return st.st_file_attributes if hasattr(st, "st_file_attributes") else 0
    except OSError:
        return None


def _mask(secret: str) -> str:
    """密钥**只报掩码**：前 4 位 + ****。原文绝不出现在报告里。"""
    return secret[:4] + "****" if len(secret) > 4 else "****"


def _why_excluded(name: str) -> str:
    """被排除的目录必须说得出理由 —— 理由从唯一口径取，不许在这里现编。"""
    if name in EXTERNAL_CORPORA:
        return EXTERNAL_CORPORA[name]
    if name in TOOLING_DIRS:
        return "缓存/临时/归档/数据面（不是代码面）"
    return "(未登记)"


# ─────────────────────────────────────────────────────────── 主扫描

def scan(root=None, mode: str = "scope",
         count_excluded: bool | None = None,
         deep_max_files: int = DEEP_MAX_FILES) -> dict:
    """多维扫描。`mode`:
        scope —— 按唯一口径剪枝（快，供测试与高频调用）
        full  —— 进所有目录（含已声明排除的外部语料，**只数不读**），跑藏匿面检测
        deep  —— full + 逐文件读内容（有上限），跑内容痕迹与重复检测
    返回：三桶闭合证明 + 维度读数 + 规则化发现。
    """
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    if count_excluded is None:
        count_excluded = mode in ("full", "deep")
    t0 = time.perf_counter()
    findings: list = []
    by_kind: dict = {}
    by_ext: dict = {}
    by_bucket = {"scanned": 0, "excluded_declared": 0, "excluded_tooling": 0, "unreadable": 0}
    excluded_detail: dict = {}
    unreadable: list = []
    dirs_seen = 0
    walk_errors: list = []
    ads_ok, ads_checked, ads_found = None, 0, []
    ads_probed = False
    hidden_attr, reparse, empty_files, deep_hits, big_files = [], [], [], [], []
    mtime_future, mtime_backwards = [], []
    name_traps: list = []
    magic_mismatch: list = []
    secrets: list = []
    dup_index: dict = {}
    dupes: list = []
    hashed = 0
    enumerated = 0

    def _add(rule, sev, path, detail, **extra):
        findings.append({"rule": rule, "severity": sev,
                         "path": str(path.relative_to(root)).replace("\\", "/")
                         if str(path).startswith(str(root)) else str(path),
                         "detail": detail, **extra})

    def _bucket_for_pruned(dir_name: str) -> str:
        """剪掉的子树按**剪它的理由**归桶，不按顶层部件。

        🔴 这里修过一个**假绿**：第一版按 `rel.parts[0]` 归桶，于是嵌在
        `gbt_allinone/store/`（深层排除）里的两万个文件被算成「已扫」——
        实测 引擎报"已扫 23089"，而同一份剪枝口径只走得到 **2495** 个文件。
        恒等式 `枚举 == 三桶之和` 照样成立，**但标签在撒谎**：
        它把"只数过、从没读过"的两万个文件记成了"扫过没问题"。
        铁律：**walk 走到的才算已扫；剪掉的一律进排除桶，并写明是谁剪的。**
        """
        return "excluded_declared" if dir_name in EXTERNAL_CORPORA else "excluded_tooling"

    def _walk_err(e):
        walk_errors.append("%s: %s" % (getattr(e, "filename", "?"), type(e).__name__))

    stack = [root]
    while stack:
        d = stack.pop()
        dirs_seen += 1
        try:
            entries = list(os.scandir(d))
        except OSError as e:
            unreadable.append(str(d))
            by_bucket["unreadable"] += 1
            _add("GBT-SE-052", "error", d, "目录读不出来（%s）—— 盲区必须可见" % type(e).__name__)
            continue
        names_here = []
        for e in entries:
            p = Path(e.path)
            rel = p.relative_to(root)
            is_dir = False
            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError:
                pass
            if is_dir:
                # 跳过目录**按名字在任意深度**剪枝：`node_modules` 藏在深层一样要剪，
                # 只看顶层部件会漏掉深层同名目录（那正是藏东西的常见位置）。
                if e.name in SKIP_DIRS:
                    n, b = _count_tree(p)          # 只数不读：让总数闭合，但不读它内容
                    enumerated += n
                    by_bucket[_bucket_for_pruned(e.name)] += n
                    d0 = excluded_detail.setdefault(
                        e.name, {"files": 0, "bytes": 0, "reason": _why_excluded(e.name),
                                 "where": rel.parent.as_posix()})
                    d0["files"] += n
                    d0["bytes"] += b
                    continue
                # 重解析点（软链/联接）：可能指向仓外 —— 记录，且**不跟随**
                try:
                    if e.is_symlink():
                        reparse.append(str(rel))
                        _add("GBT-SE-051", "warn", p, "重解析点（软链/联接）：不跟随，可能指向仓外")
                except OSError:
                    pass
                stack.append(p)
                continue
            # ---- 文件：**walk 走得到的才叫「已扫」**（剪掉的子树根本走不到，已在上面归桶）
            enumerated += 1
            by_bucket["scanned"] += 1
            try:
                st = e.stat(follow_symlinks=False)
            except OSError as ex:
                unreadable.append(str(rel))
                by_bucket["unreadable"] += 1
                by_bucket["scanned"] -= 1
                _add("GBT-SE-053", "error", p, "文件 stat 失败（%s）" % type(ex).__name__)
                continue
            size = st.st_size
            kind = _kind_of(p.name)
            by_kind[kind] = by_kind.get(kind, 0) + 1
            ext = p.suffix.lower() or "(无后缀)"
            rec = by_ext.setdefault(ext, {"n": 0, "bytes": 0})
            rec["n"] += 1
            rec["bytes"] += size
            # D5 名称诡计 —— **本块无条件执行**。
            # 🔴 2026-09-25 清掉一句死条件：原来写的是 `if name_traps or True:`，
            #    由于 `X or True ≡ True`，这个"门"**永远开着**、形同注释
            #    （`dead_judgments` 审计器点出来的）。而且它同时负责 `names_here` 的收集 ——
            #    那部分**必须**每个文件都跑到，本来就不该被任何条件管。
            #    ⇒ 直接去掉条件，**行为逐字节不变**。
            nm = p.name
            if any(ord(ch) in ZW_AND_BIDI for ch in nm):
                name_traps.append(str(rel))
                _add("GBT-SE-021", "error", p, "文件名含零宽/双向控制字符（肉眼看不见）")
            if nm != nm.rstrip(" .") :
                name_traps.append(str(rel))
                _add("GBT-SE-022", "error", p, "文件名以空格或点结尾（Windows 会悄悄剥掉 ⇒ 两名对一物）")
            low = nm.lower()
            # 双后缀伪装：**前一个后缀必须是"看着无害"的**（.txt/.jpg/.pdf…），
            # 后一个才是可执行。第一版只判"点 ≥2 且以 .js 结尾" ⇒
            # 把 `xingyun_e2e.latest.js` 这种正常命名全报成伪装（自己造的误报）。
            last = Path(low).suffix
            prev = Path(low).stem.rpartition(".")[2]
            prev_ext = "." + prev
            if last in DANGER_EXTS and prev_ext in (PRETEND_EXTS | CODE_PRETEND) \
                    and prev_ext != last:
                name_traps.append(str(rel))
                _add("GBT-SE-023", "error", p,
                     "双后缀伪装（%s%s）：前一个后缀看着无害，真身是 %s" % (prev_ext, last, last))
            names_here.append(nm)
            if size == 0:
                empty_files.append(str(rel))
            if size > 32 << 20:
                big_files.append((str(rel), size))
                _add("GBT-SE-081", "warn", p, "超大文件 %.1f MB" % (size / 1048576))
            if len(str(p)) > 240:
                _add("GBT-SE-082", "warn", p, "路径超长（%d 字符）：部分工具会读不到" % len(str(p)))
            depth = len(rel.parts)
            if depth > 12:
                deep_hits.append((str(rel), depth))
                _add("GBT-SE-083", "warn", p, "嵌套过深（第 %d 层）" % depth)
            attrs = getattr(st, "st_file_attributes", 0)
            if attrs:
                if attrs & 0x2:                     # FILE_ATTRIBUTE_HIDDEN
                    hidden_attr.append(str(rel))
                    _add("GBT-SE-041", "warn", p, "隐藏属性（资源管理器默认看不见）")
                if attrs & 0x4:                     # FILE_ATTRIBUTE_SYSTEM
                    _add("GBT-SE-042", "warn", p, "系统属性")
                if attrs & 0x400:                   # FILE_ATTRIBUTE_REPARSE_POINT
                    reparse.append(str(rel))
            mt = st.st_mtime
            now = time.time()
            if mt > now + 3600:
                mtime_future.append((str(rel), mt))
                _add("GBT-SE-071", "warn", p,
                     "未来时间戳（+%.1f h）：可用来躲开按时间找的排查" % ((mt - now) / 3600))
            if st.st_ctime and mt > st.st_ctime + 86400 * 2:
                mtime_backwards.append(str(rel))
            # D4 伪装（两个方向都要抓）：
            #   正向 —— 后缀声称是某种二进制，头字节却是别的（改名伪装）
            #   反向 —— 头字节是**强二进制**，后缀却挂着文本/代码/网页（把可执行藏成文本）
            # 第一版只做了正向，于是 `fake.txt`（PNG 头）当场溜过去 —— **对照抓出来的**。
            if size >= 8:
                real = _magic_of(p)
                if p.suffix.lower() in EXT_EXPECT:
                    want = EXT_EXPECT[p.suffix.lower()]
                    if real not in (want, "(读不到)", "(空)") and real != "文本类":
                        magic_mismatch.append((str(rel), p.suffix.lower(), real))
                        _add("GBT-SE-010", "error", p,
                             "伪装：后缀 %s 说它是 %s，实际头字节是 %s"
                             % (p.suffix.lower(), want, real), real_kind=real)
                elif kind in HIDE_AS and real.startswith(STRONG_BINARY_PREFIX):
                    magic_mismatch.append((str(rel), p.suffix.lower() or "(无后缀)", real))
                    _add("GBT-SE-011", "error", p,
                         "反向伪装：后缀说它是%s，头字节却是 %s ⇒ 二进制被藏成文本"
                         % (kind, real), real_kind=real)
            # D7 ADS：**能力可用性在任何模式都要探一次**（否则 scope 下报 available=None，
            # 分不清"这维度扫不动"还是"没扫"）；逐文件扫只在 full/deep 做（每文件一次 Win32 调用）。
            if not ads_probed:
                ads_probed = True
                ads_ok = _ads_streams(p)[0]
            if mode in ("full", "deep"):
                ok, extra = _ads_streams(p)
                if ok:
                    ads_checked += 1
                    for s in extra:
                        ads_found.append((str(rel), s))
                        _add("GBT-SE-040", "error", p, "NTFS 备用数据流：%s（资源管理器看不见）" % s)
            # D9 内容（deep）
            if mode == "deep" and hashed < deep_max_files and size <= DEEP_MAX_BYTES:
                if kind in TEXT_EXT_HINT or ext == "(无后缀)":
                    try:
                        raw = p.read_bytes()
                    except OSError:
                        raw = None
                    if raw is not None:
                        hashed += 1
                        if b"\x00" in raw:
                            _add("GBT-SE-067", "warn", p, "文本类文件里含 NUL 字节（可能是二进制改名）")
                        for line in raw.split(b"\n"):
                            if len(line) > MAX_LINE_BYTES:
                                _add("GBT-SE-068", "warn", p, "存在单行 > 1 MiB 的超长行（藏载荷常用）")
                                break
                        txt = raw.decode("utf-8", errors="replace")
                        for rule, pat, what in SECRET_PATTERNS:
                            m = pat.search(txt)
                            if m:
                                secrets.append((str(rel), rule, what))
                                _add(rule, "error", p, "疑似%s：%s（**只报掩码**）"
                                     % (what, _mask(m.group(0))))
                if hashed < deep_max_files:
                    try:
                        h = hashlib.sha256(p.read_bytes()).hexdigest()
                        hashed += 1
                        if h in dup_index and dup_index[h] != str(rel):
                            dupes.append((dup_index[h], str(rel)))
                            _add("GBT-SE-090", "info", p, "内容与 %s 逐字节相同" % dup_index[h])
                        else:
                            dup_index[h] = str(rel)
                    except OSError:
                        pass
        # D6 撞名：仅大小写不同 / 仅规范化形式不同
        if names_here:
            low_map: dict = {}
            norm_map: dict = {}
            for nm in names_here:
                low_map.setdefault(nm.lower(), []).append(nm)
                norm_map.setdefault(unicodedata.normalize("NFC", nm), []).append(nm)
            for k, v in low_map.items():
                if len(v) > 1:
                    _add("GBT-SE-030", "error", d, "仅大小写不同的撞名：%s（Windows 上会互相覆盖）" % v)
            for k, v in norm_map.items():
                if len(set(v)) > 1:
                    _add("GBT-SE-031", "error", d, "Unicode 规范化后撞名：%s" % v)

    # ---- 闭合律：枚举 == 已扫 + 已声明排除 + 读不到
    total_bucket = sum(by_bucket.values())
    closure = (enumerated == total_bucket)
    if not closure:
        _add("GBT-SE-000", "error", root,
             "覆盖闭合失败：枚举 %d ≠ 三桶之和 %d ⇒ 有东西没落账" % (enumerated, total_bucket))
    errs = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]
    return {
        "ok": bool(closure),
        "readonly": True,
        "mode": mode,
        "root": str(root),
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "enumerated": enumerated,
        "buckets": by_bucket,
        "closure": closure,
        "dirs_seen": dirs_seen,
        "walk_errors": walk_errors,
        "unreadable": unreadable[:200],
        "unreadable_count": len(unreadable),
        "excluded_detail": excluded_detail,
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "by_ext": dict(sorted(by_ext.items(), key=lambda kv: -kv[1]["n"])),
        "dimensions": [{"id": i, "name": n, "rule": r, "what": w} for i, n, r, w in DIMENSIONS],
        "probes": {
            "ads": {"available": ads_ok, "checked": ads_checked, "found": len(ads_found)},
            "notes": "标注 available=False 的维度是**扫不动**，不是扫过了没问题",
        },
        "findings": findings,
        "finding_counts": {"error": len(errs), "warn": len(warns),
                           "info": len(findings) - len(errs) - len(warns)},
        "hits": {
            "magic_mismatch": magic_mismatch, "name_traps": sorted(set(name_traps)),
            "ads": ads_found, "hidden_attr": hidden_attr, "reparse": reparse,
            "empty": empty_files, "deep": deep_hits, "big": big_files,
            "mtime_future": mtime_future, "mtime_backwards": mtime_backwards[:50],
            "secrets": secrets, "dupes": dupes[:100],
        },
        "deep": {"files_read": hashed, "max_files": deep_max_files},
    }


def _count_tree(d) -> tuple:
    """只数不读：返回 (文件数, 字节数)。scandir 走，不经过 glob。"""
    n = 0
    b = 0
    stack = [Path(d)]
    while stack:
        cur = stack.pop()
        try:
            for e in os.scandir(cur):
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(Path(e.path))
                    else:
                        n += 1
                        try:
                            b += e.stat(follow_symlinks=False).st_size
                        except OSError:
                            pass
                except OSError:
                    pass
        except OSError:
            pass
    return n, b


# ─────────────────────────────────────────────────────────── 两把对照

def selftest(verbose: bool = True) -> int:
    """正对照：种进去的 8 种藏匿样本必须**全部**被抓到。
    负对照：干净文件不许被这几条规则误报。**只有一边的检测器是瞎的。**"""
    import tempfile

    planted, missed, false_pos = [], [], []
    rules_seen: set = set()
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        # ① 正常文件（负对照）
        (t / "clean.py").write_text("x = 1\n", encoding="utf-8")
        (t / "clean.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
        # ② 伪装：PNG 头挂 .txt 后缀
        (t / "fake.txt").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
        # ③ 双后缀
        (t / "evil.py.exe").write_bytes(b"MZ" + b"\x00" * 40)
        # ④ 零宽字符文件名
        (t / "inv\u200bisible.txt").write_text("hi\n", encoding="utf-8")
        # ⑤ 结尾空格名：Windows 的常规 API 会把它悄悄剥掉 ⇒ 得走扩展长度路径才造得出来。
        #    造不出来就**如实标"不适用"**，不许把造不出的样本算成"检测器漏报"
        #    （第一版我写了 `trail .txt` —— 空格在点**前面**，根本不是结尾空格，是我的样本错）。
        trail_made = False
        try:
            with open("\\\\?\\" + str(t / "trailspace "), "w", encoding="utf-8") as f:
                f.write("hi\n")
            trail_made = any(n.endswith(" ") for n in os.listdir(t))
        except OSError:
            trail_made = False
        # ⑥ 空文件
        (t / "empty.bin").write_bytes(b"")
        # ⑦ 疑似密钥
        (t / "conf.py").write_text('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz0123"\n', encoding="utf-8")
        # ⑧ ADS 隐藏流：**挂在专门的载体上**，别挂在负对照文件上
        #    （第一版我把流挂在 clean.py，于是负对照报"误报" —— 其实检测器是对的，是我的样本设计错）
        (t / "carrier.py").write_text("# 载体\n", encoding="utf-8")
        ads_made = False
        try:
            with open(str(t / "carrier.py") + ":hidden", "w", encoding="utf-8") as f:
                f.write("payload")
            ads_made = True
        except OSError:
            pass
        # ⑨ 未来时间戳
        future = t / "future.txt"
        future.write_text("hi\n", encoding="utf-8")
        os.utime(future, (time.time() + 86400 * 30, time.time() + 86400 * 30))
        # ⑩ 重复内容
        (t / "dup_a.txt").write_text("same-bytes\n", encoding="utf-8")
        (t / "dup_b.txt").write_text("same-bytes\n", encoding="utf-8")

        rep = scan(t, mode="deep")
        # 结尾空格名 rmtree **删不掉**（WinError 145：目录不是空的）—— 实测会把临时目录留在盘上。
        # 自己造出来的样本必须自己收干净，否则"扫描器"变成"垃圾制造器"。
        if trail_made:
            try:
                os.remove("\\\\?\\" + str(t / "trailspace "))
            except OSError:
                pass
        for f in rep["findings"]:
            rules_seen.add(f["rule"])
        rels = {f["path"] for f in rep["findings"]}
        h = rep["hits"]
        checks = [
            ("伪装(PNG头挂.txt)", any("fake.txt" in x[0] for x in h["magic_mismatch"])),
            ("双后缀(evil.py.exe)", any(x["rule"] == "GBT-SE-023" for x in rep["findings"])),
            ("零宽名", any(x["rule"] == "GBT-SE-021" for x in rep["findings"])),
            ("结尾空格名", any(x["rule"] == "GBT-SE-022" for x in rep["findings"])
             if trail_made else None),
            ("空文件", any("empty.bin" in x for x in h["empty"])),
            ("疑似密钥", len(h["secrets"]) >= 1),
            ("ADS 隐藏流", (len(h["ads"]) >= 1) if ads_made else None),
            ("未来时间戳", any("future.txt" in x[0] for x in h["mtime_future"])),
            ("重复内容", len(h["dupes"]) >= 1),
            ("覆盖闭合", rep["closure"] is True),
            ("ADS 能力可用性已探明", rep["probes"]["ads"]["available"] is not None),
        ]
        for name, got in checks:
            if got is None:
                continue
            (planted if got else missed).append(name)
        # 负对照：干净文件不许命中这五条
        bad_rules = {"GBT-SE-010", "GBT-SE-021", "GBT-SE-022", "GBT-SE-023", "GBT-SE-040"}
        for f in rep["findings"]:
            if f["rule"] in bad_rules and ("clean." in f["path"]):
                false_pos.append(f["rule"] + " " + f["path"])
        fp_clean = [f for f in rep["findings"]
                    if f["rule"] == "GBT-SE-066" and "clean" in f["path"]]
        false_pos.extend(x["rule"] for x in fp_clean)
    if verbose:
        print("═══ 多维扫描引擎 · 两把对照 ═══")
        print("正对照 命中 %d/%d ：%s" % (len(planted), len(planted) + len(missed), "、".join(planted)))
        if missed:
            print("  ✗ 漏掉：%s" % "、".join(missed))
        print("负对照 误报 = %d %s" % (len(false_pos), false_pos[:5]))
        print("ADS 隐藏流样本是否造出 =", ads_made)
        print("结论：%s" % ("两把对照都过 ✅" if not missed and not false_pos
                          else "✗ 判红：漏=%s 误报=%s" % (missed, false_pos)))
    return 0 if (not missed and not false_pos) else 1


# ─────────────────────────────────────────────────────────── CLI

def main(argv=None) -> int:                                     # pragma: no cover
    ap = argparse.ArgumentParser(description="多维穷尽扫描引擎")
    ap.add_argument("--root", default=None)
    ap.add_argument("--mode", choices=("scope", "full", "deep"), default="scope")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rep = scan(a.root, mode=a.mode)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0 if rep["ok"] else 1
    print("═══ 多维穷尽扫描 · root=%s · mode=%s ═══" % (rep["root"], rep["mode"]))
    print("用时 %.2fs · 目录 %d · 枚举文件 %d" % (rep["elapsed_s"], rep["dirs_seen"], rep["enumerated"]))
    print("三桶：已扫 %d · 已声明排除 %d · 工具/缓存排除 %d · 读不到 %d"
          % (rep["buckets"]["scanned"], rep["buckets"]["excluded_declared"],
             rep["buckets"]["excluded_tooling"], rep["buckets"]["unreadable"]))
    print("覆盖闭合 = %s（枚举 %d == 三桶之和 %d）"
          % (rep["closure"], rep["enumerated"], sum(rep["buckets"].values())))
    print("维度登记 %d 个：" % len(rep["dimensions"]))
    for d in rep["dimensions"]:
        print("   %-4s %-8s %-12s %s" % (d["id"], d["name"], d["rule"], d["what"]))
    print("发现：error %d · warn %d · info %d"
          % (rep["finding_counts"]["error"], rep["finding_counts"]["warn"],
             rep["finding_counts"]["info"]))
    print("按种类：" + "、".join("%s %d" % kv for kv in list(rep["by_kind"].items())[:10]))
    print("按后缀 TOP：" + "、".join("%s %d" % (k, v["n"]) for k, v in list(rep["by_ext"].items())[:10]))
    print("探针：" + json.dumps(rep["probes"], ensure_ascii=False))
    for f in rep["findings"][:a.limit]:
        print("   [%s] %-12s %s — %s" % (f["severity"], f["rule"], f["path"], f["detail"]))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
