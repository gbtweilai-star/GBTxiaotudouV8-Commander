# gbt-capability: 扫描范围唯一口径（谁扫仓谁用它，不许各自再写一份）
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""全仓扫描的**唯一范围口径**。

由来（2026-09-22 实测，一天之内被同一类病咬了三次）：
  `test_api_probe` 全仓扫描 **5216 文件 / 42.12s**、`caps_called_audit.audit()`
  **19.5–33.2s**、`gate_visibility.scan()` 直接走不完 —— 三台各自独立写的扫描器，
  全都因为工作区变大（vendor/pylibs 3106 个 .py、_upstream 889 个、.shadow-repo 546 个）
  而撞爆 pytest 30s 单测超时。
  **逐个等超时抓是错的打法**：同一份名单被抄了三遍，就会有三份各自过期的名单。
  故收敛到这一处：名单 + 剪枝走法都从这里取。

两条纪律：
  ① **剪枝要发生在进入子目录之前**（`os.walk` 里改 `dirnames`），
     不是"走完再过滤"——实测 rglob 先吐 10549 个 .py 要 3.99s，
     剪枝后同样结果只要 0.05s（80×）。
  ② **排除必须是贴了标签、报了尺寸的边界**，不是没贴标签的天窗：
     每一块被排除的语料都要有 ≥15 字的实质理由，且能被数出来。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

# ── 被排除在扫描范围之外的外部语料：名字 -> 实质理由（≥15 字，不是"没用"这种空话）
EXTERNAL_CORPORA = {
    "vendor": "第三方 vendored 依赖（pylibs 等），非本仓编写，不构成生产调用面",
    "_upstream": "外部上游仓（Scrapling/career-ops 等）原样停放区，供蒸馏参考，非本仓代码",
    ".shadow-repo": "本仓影子镜像副本，与主面同源重复，扫它会把同一处命中数两遍",
    # ── 2026-10-04 增（两个收编区，都是「停进来的外部源码」，不是本仓代码面）──
# 2026-10-16 对齐：_legacy_sources 整树已永久删除（主人令），原排除项变成**指空** ⇒ 删；清单留档 state/_recycled/legacy_sources-20261016.json
    "quant_workspace": "量化收割引擎源码收编区（2026-10-04 由 Desktop\\Workspace 收编进仓），生产只读消费",
}

# ── 缓存 / 临时 / 归档 / 数据面：不是代码，也不是产物
TOOLING_DIRS = {
    ".git", "__pycache__", "node_modules", ".pylibs", ".playwright-cli",
    ".opencode", ".cluster", ".scratch", ".backups",
    ".openclaw", ".openclaw-attachments", "agent-gvmz-gbtv8", "generated-images",
    "outputs", "infinite-canvas-output", "archive",
    "store",            # 镜像数据面（不是代码）
    "dist", "build",    # 构建产物
    # 🔴 2026-10-25 · 补三类「不是我们的代码」，因为它们是量出来的真数
    #    （_owned_py_files(ROOT) 现读 13383 个 .py，其中 .venv-sadtalker 10117、
    #     Python/ 1159、third_party/SadTalker 109 都是第三方树 ⇒ 剪掉后只剩 3266）：
    ".venv-sadtalker",  # SadTalker 的虚拟环境（site-packages 全是第三方）
    "Python",           # 仓根内嵌的 CPython 运行时（pythoncore-3.15-64）
    "third_party",      # vendored 外部件（SadTalker）
}

# 扫描时一律跳过（含外部语料）
SKIP_DIRS = frozenset(TOOLING_DIRS) | frozenset(EXTERNAL_CORPORA)

# 兜底上限：单个 .py 超过它就别解析了（防止哪天有人丢进一个巨型生成文件）
MAX_FILE_BYTES = 8 * 1024 * 1024


def walk(root, onerror=None):
    """剪枝版 `os.walk`：被排除的树**根本不进**。

    `onerror` 会收到 scandir 的错误 —— 调用方**必须**把它变成可见读数，
    否则读不到的目录就是没贴标签的天窗（`os.walk` 默认静默吞掉）。
    """
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror):
        # 🔴 2026-10-25 · 虚拟环境不只叫 .venv-sadtalker：凡是 .venv* / venv /
        #    site-packages 一律不进（这一条是**前缀规则**，不是点名，避免下次换个名字又漏）。
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS
                       and not d.startswith(".venv")
                       and d not in ("venv", "site-packages")]
        yield Path(dirpath), dirnames, filenames


def iter_files(root, suffixes=None, onerror=None):
    """仓内文件迭代器（已剪枝）。`suffixes` 形如 `(".py", ".js")`。"""
    for dirpath, _dirnames, filenames in walk(root, onerror=onerror):
        for name in filenames:
            if suffixes and not name.endswith(tuple(suffixes)):
                continue
            yield dirpath / name


def iter_text_files(root, suffixes=None, onerror=None, max_bytes=MAX_FILE_BYTES):
    """逐个读出文本；读不出/超限的**跳过但可被调用方记账**（故 yield 二元组）。"""
    for p in iter_files(root, suffixes=suffixes, onerror=onerror):
        try:
            if p.stat().st_size > max_bytes:
                yield p, None
                continue
            yield p, p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            yield p, None


_CORPUS_CACHE: dict = {}

# ── 定向检索（Owner 令 2026-10-17 逐字：「把 grep 超时的问题换成定向检索」）──
# 原口径：整树 `os.walk` **数完为止**。
# 为什么翻：全量跑里 `test_blindspot_registry.setUpClass → gate_visibility.scan → corpus_sizes
#   → _count_py → os.walk` **撞 120s 硬超时**，整轮 pytest 被线程超时打断（本仓第三次踩
#   "全树遍历/先遍历再过滤"这个病：`test_precommit_secret_scan`、`iron-rules-check` 同族）。
# 现口径：**有界定向检索** ——
#   ① **不跟 junction / 符号链接**（防环：影子副本/junction 能把树放大成无限）；
#   ② 单词料预算（文件数 150k / 2.0s），到线就收；
#   ③ 超限**如实标 `truncated`** —— 数出来的数是**下界**，不冒充全量（"登记 ≠ 忽略"照旧）。
_COUNT_BUDGET_FILES = 150_000
_COUNT_BUDGET_S = 2.0


def _is_junction(p: Path) -> bool:
    """是不是 junction/重解析点（跟进去可能绕环）。取不到就按"跳板"处理（fail-closed）。"""
    try:
        return bool(p.is_junction())            # Python 3.12+
    except OSError:
        return True
    except AttributeError:                       # 老解释器：没有这个 API ⇒ 不据此跳
        return False


def _count_py(d) -> tuple:
    """剪枝 + **有界**走法数 .py 与字节数。返回 `(n, b, truncated)`。

    自打脸的一刀：本模块存在的意义就是消灭 rglob，而 `corpus_sizes` 第一版自己
    写的是 `d.rglob("*.py")` —— 实测它在串跑时把 `test_gate_visibility` 顶过 30s 硬超时。
    改成 `os.walk` 剪枝后：**串跑仍会撞 120s**（语料树太大）⇒ 现在再加**预算 + 防环**。
    """
    n = 0
    b = 0
    truncated = False
    t0 = time.time()
    for dirpath, dirnames, filenames in os.walk(d, onerror=lambda _e: None):
        base = Path(dirpath)
        dirnames[:] = [x for x in dirnames
                       if x not in SKIP_DIRS and not _is_junction(base / x)]
        for name in filenames:
            if name.endswith(".py"):
                n += 1
                try:
                    b += os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    pass
        if n >= _COUNT_BUDGET_FILES or (time.time() - t0) >= _COUNT_BUDGET_S:
            truncated = True
            break
    return n, b, truncated


def corpus_sizes(root) -> dict:
    """被排除的语料**逐块量化**（文件数 / 字节数），进程内记忆。

    这条是"登记 ≠ 忽略"的落点：边界可以被数出来，才叫声明；数不出来，就是藏。
    """
    key = str(Path(root))
    if key in _CORPUS_CACHE:
        return _CORPUS_CACHE[key]
    root = Path(root)
    out = {}
    for name in EXTERNAL_CORPORA:
        d = root / name
        if not d.is_dir():
            out[name] = {"exists": False, "py_files": 0, "bytes": 0}
            continue
        n, b, truncated = _count_py(d)
        out[name] = {
            "exists": True,
            "py_files": n,
            "bytes": b,
            "truncated": truncated,
            "reason": EXTERNAL_CORPORA[name],
        }
        if truncated:
            out[name]["note"] = ("有界遍历：命中预算即收口 ⇒ py_files/bytes 是**下界**，"
                                 "不是全量（「登记 ≠ 忽略」照旧，但不冒充数完）")
    _CORPUS_CACHE[key] = out
    return out


def scope_report(root) -> dict:
    """给体检/报告用的口径快照：跳了什么、为什么、跳掉了多少。"""
    return {
        "skip_dirs": sorted(SKIP_DIRS),
        "external_corpora": dict(EXTERNAL_CORPORA),
        "sizes": corpus_sizes(root),
        "rule": "剪枝发生在进入子目录之前；排除项必须带理由且可量化",
    }


# ── 内容指纹（2026-09-23 第 52 轮加）：让"这次跑的时候树没被改"从**考古**变成**证明** ──
# 由来：第 51 轮的两份回归读数**都被并发写入污染**了 ——
#   `file_operation.py` 08:52 落在模式① 窗口内 · `caps_registry.py` 08:59 落在模式② 内，
#   而我是**事后按 mtime 去查**才发现的。那是考古，不是证明：
#   ① mtime 只能事后查，跑的时候不知道；② 它证明不了"内容"没变（同秒写两次看不出来）。
#   而 `regression_stamp` 只盖 `git head` —— **并发会话的未提交改动它盖不到**。
# ⇒ 有了指纹，"绿"才能**自己证明**自己干净；没有指纹，"绿"永远靠人事后解释。
CODE_SUFFIXES = (".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".jsx", ".sh", ".ps1")


def tree_fingerprint(root, suffixes=CODE_SUFFIXES, onerror=None, with_rows=False,
                     subdir=None) -> dict:
    """整棵（**已剪枝**）代码树的内容指纹。`subdir` 给定时只算那棵子树。

    返回 `{"sha256", "files", "bytes", "unreadable", "subdir"}`；
    `with_rows=True` 时**另带 `rows`**（逐文件的 path/bytes/sha256）——
    有了它才能在事后说清**是哪个文件动了**（见 `diff_trees`）。

    🔴 `subdir`（2026-09-23 第 56 轮加）＝**依赖面**那一刀。由来与实测：
       连续好几轮，模式② 的读数都被并发会话写 `holo_pet_w3/*.js` 判成"不作收据"——
       而**那些文件模式② 根本不 import**（模式② 跑的是 `gbt_allinone/tests`）。
       实测（`.scratch/measure_dep_face.py`：真起一次 pytest 收集后 dump `sys.modules`）：
       **依赖面 = 199 个文件，全部落在 `gbt_allinone/` 之内**；
       近几轮导致"不作收据"的 13 个改动里 **只有 1 个在面内**（`gbt_allinone/api.py`），
       另外 **12 个都在面外**（`holo_pet_w3/*` 与 `tools/codex-scripts/*`）。
       ⇒ 所以"包"就是那一刀：**面内改动 ⇒ 真会影响读数**；面外改动 ⇒ 与读数无关。
         ⚠️ 取的是**保守的超集**（包内 351 个 .py ⊃ 依赖面 199 个）——
           宁可把"其实无关的包内改动"也算进去，也不漏掉真依赖。
         ⚠️ 边界：依赖面量的是**收集期**；用例体里再 import 的东西不在里面。

    ⚠️ **读不了的文件必须列出来**：读不了是"未知"，**不是"没变"** ——
       把它们悄悄跳过，指纹就会在"有文件读不了"时照样报"没变化"。
    ⚠️ 指纹**只对剪枝后的范围成立**（`store` / `.pylibs` / `_upstream` 等不进指纹）——
       与所有扫描器同一套 `SKIP_DIRS`，所以"指纹没变"这句话的作用域也是同一个。
    """
    import hashlib
    root = Path(root)
    base = (root / subdir) if subdir else root
    rows, unreadable = [], []
    for p in iter_files(base, suffixes=suffixes, onerror=onerror):
        try:
            b = p.read_bytes()
            rows.append((str(p.relative_to(root)).replace("\\", "/"),
                         len(b), hashlib.sha256(b).hexdigest()))
        except OSError as e:
            unreadable.append((str(p), type(e).__name__))
    rows.sort()
    h = hashlib.sha256()
    for rel, size, dig in rows:
        h.update(("%s\0%d\0%s\0" % (rel, size, dig)).encode("utf-8"))
    out = {"sha256": h.hexdigest(), "files": len(rows),
           "bytes": sum(r[1] for r in rows), "unreadable": unreadable,
           "subdir": subdir or ""}
    if with_rows:
        out["rows"] = [{"path": rel, "bytes": size, "sha256": dig} for rel, size, dig in rows]
    return out


def diff_trees(before, after) -> dict:
    """**是哪个文件动了** —— 把「不作收据」变成「不作收据，因为 A/B/C 动了」。

    🔴 2026-09-23 第 53 轮加。由来：指纹装好之后连着两轮，模式② 都报
    「树在扫描中途被改了 ⇒ 不作收据」，可**它只说"变了"，不说"谁变的"** ——
    于是我还得回头查 mtime，**又绕回考古**。
    第 52 轮实测：一轮里 4 个文件动过（我自己 1 个 + 并发会话 3 个），
    而屏幕上只有一句"变了"。**读数要能追责，才叫读数。**

    要求两侧都带 `rows`（`tree_fingerprint(..., with_rows=True)`）；
    缺了就说"说不出是谁动的"，**不假装没变化**。
    """
    b = {r["path"]: r["sha256"] for r in (before or {}).get("rows") or []}
    a = {r["path"]: r["sha256"] for r in (after or {}).get("rows") or []}
    if not b or not a:
        return {"available": False, "added": [], "removed": [], "changed": [],
                "note": "两次指纹里至少有一次没带 rows ⇒ **说不出是谁动的**（这不是『没动』）"}
    return {"available": True,
            "added": sorted(set(a) - set(b)),
            "removed": sorted(set(b) - set(a)),
            "changed": sorted(p for p in (set(a) & set(b)) if a[p] != b[p]),
            "note": "added/removed/changed 都是**相对路径**；范围同 `SKIP_DIRS`"}


def _selftest() -> int:                                     # pragma: no cover
    root = Path(__file__).resolve().parents[2]
    rep = scope_report(root)
    print("扫描范围口径 · %s" % root)
    for name, s in rep["sizes"].items():
        print("  排除 %-14s %s  %5d 个 .py  %7.1f MB  ← %s" % (
            name, "在盘" if s["exists"] else "缺席",
            s["py_files"], s["bytes"] / 1048576, EXTERNAL_CORPORA[name]))
    n = sum(1 for _ in iter_files(root, suffixes=(".py",)))
    print("剪枝后仓内 .py =", n)
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(_selftest())
