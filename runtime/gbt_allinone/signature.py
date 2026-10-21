"""GBT小土豆V8 · 开发者署名守卫（Signature Guard）。

开发者：自由的风 —— 框架每一页（文档/网页/产物）必须携带此署名，禁止删除。

职责：
- inject: 幂等地给文本/网页/文档注入署名（已存在则不动）
- has_signature: 校验页面是否携带署名
- audit: 扫描全框架页面（.md 文档 + 生产管线文本/网页产物），报告缺失并可按需恢复

「禁止删除」的技术实现：任何页面被去掉署名 → audit 立即发现 → restore 自动补回 → 审计留痕。
"""
import re
import time
from pathlib import Path

from .soul import DEVELOPER, SIGNATURE

_BASE = Path(__file__).resolve().parent      # gbt_allinone/
_HOME = _BASE.parent                         # 家根

SIG_MARK = SIGNATURE                         # "开发者：自由的风"
SIG_BANNED = "本署名不可删除、不可篡改归属"
SIG_TAG = "GBT小土豆V8"

# 需要携带署名的页面类型
_PAGE_SUFFIX = {".md", ".html", ".htm"}
_TEXT_SUFFIX = {".txt", ".md", ".html", ".htm", ".csv"}


def _md_footer() -> str:
    return f"\n\n---\n\n> {SIG_MARK} · {SIG_TAG} · {SIG_BANNED}\n"


def _html_footer() -> str:
    return (f'\n<footer class="gbt-signature" data-developer="{DEVELOPER}">'
            f'{SIG_MARK} · {SIG_TAG} · {SIG_BANNED}</footer>\n')


def _text_footer() -> str:
    return f"\n—— {SIG_MARK} · {SIG_TAG} · {SIG_BANNED}\n"


def has_signature(text: str) -> bool:
    return isinstance(text, str) and SIG_MARK in text


def _is_html(path: Path, text: str) -> bool:
    if path.suffix in (".html", ".htm"):
        return True
    head = text[:200].lower()
    return "<html" in head or "<!doctype html" in head


def inject(text: str, path=None) -> str:
    """幂等注入署名。已带署名原样返回。"""
    if has_signature(text):
        return text
    name = str(path or "")
    if name.lower().endswith((".html", ".htm")) or _is_html(Path(name or "x"), text):
        if "</body>" in text:
            return text.replace("</body>", _html_footer() + "</body>", 1)
        return text + _html_footer()
    if name.lower().endswith(".md"):
        return text.rstrip() + _md_footer()
    return text.rstrip() + _text_footer()


def _scan_pages():
    """收集所有应带署名的页面（框架的文档 + 生产产物的文本/网页）。

    越权修复（2026-09-11）：只签框架页面——归属分类以 inventory 为准
    （environment=桌面端工作区文档，不是框架产物，不签不查）。
    """
    pages = []
    # 1) 包内全部 .md 文档（框架本体）
    for p in _BASE.rglob("*.md"):
        if any(t in str(p) for t in (".pylibs", "archived_logs", "__pycache__", "store")):
            continue   # store/ 是数据区（吞天胶囊/管线产物）——数据不是页面，不签不查
        pages.append(p)
    # 2) 家根文档——仅框架自己的（README），环境文档不签
    for p in _HOME.glob("*.md"):
        try:
            from .inventory import _classify
            if _classify(p) != "framework":
                continue
        except Exception:
            pass
        pages.append(p)
    # 3) 生产管线里的文本/网页产物（每一页）
    # 🔴 2026-09-26 修：原来硬编码包内 store/pipeline —— 隔离 store 下会扫到真实生产树。
    from . import _paths
    prod = Path(_paths.STORE_DIR) / "pipeline" / "production"
    if prod.exists():
        for p in prod.rglob("*"):
            if p.is_file() and p.suffix.lower() in _TEXT_SUFFIX and p.suffix.lower() != ".jsonl":
                pages.append(p)
    return [p for p in pages if p.is_file()]   # 只收真文件（版本快照是同名目录，排除）


def audit(restore: bool = False) -> dict:
    """扫描页面署名完整性。restore=True 时自动补回被删署名。"""
    t0 = time.time()
    missing, restored, checked = [], [], 0
    for p in _scan_pages():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        checked += 1
        if has_signature(text):
            continue
        missing.append(str(p.relative_to(_HOME)))
        if restore:
            new = inject(text, p)
            if new != text:
                p.write_text(new, encoding="utf-8")
                restored.append(str(p.relative_to(_HOME)))

    verdict = "clean" if not missing else ("restored" if restored else "missing")
    result = {
        "ok": True,
        "verdict": verdict,
        "developer": DEVELOPER,
        "pages_checked": checked,
        "missing": missing,
        "restored": restored,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
    }
    try:
        from .store import audit as _a
        _a("signature_guard", {"verdict": verdict, "missing": len(missing), "restored": len(restored)})
    except Exception:
        pass
    return result


def stamp_pages() -> dict:
    """给所有页面盖署名（幂等），返回盖章统计。"""
    return audit(restore=True)
