"""Read-only project context for the GBT workspace.

The module gives Codex and the local panel a small, auditable retrieval layer:

- ``blueprint`` reads the authoritative PROJECT_BLUEPRINT.md;
- ``brief`` returns a compact orientation without copying the full document;
- ``search`` rank-searches only approved workspace documents;
- ``status`` reports the indexed scope and blueprint fingerprint.

It never writes files, executes commands, follows symlinks outside the project,
or searches secret-bearing locations.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from .security.data_policy import redact_text

_MAX_BLUEPRINT_BYTES = 512_000
_MAX_DOC_BYTES = 256_000
_MAX_SEARCH_LIMIT = 20
_SNIPPET_CHARS = 220

_EXACT_DOCUMENTS = (
    ("blueprint", "PROJECT_BLUEPRINT.md"),
    ("governance", "AGENTS.md"),
    ("identity", "SOUL.md"),
    ("identity", "USER.md"),
    ("memory", "MEMORY.md"),
    ("governance", "LAYOUT.md"),
    ("governance", "CODING_DISCIPLINE.md"),
    ("overview", "README.md"),
    ("overview", "gbt_allinone/README.md"),
    ("overview", "gbt_allinone/LAYOUT.md"),
    ("overview", "gbt_allinone/CODING_DISCIPLINE.md"),
    ("overview", "holo_pet/README.md"),
    ("overview", "potato_pet/readme.md"),
)

_GLOB_DOCUMENTS = (
    ("memory", "memory/*.md"),
    ("docs", "gbt_allinone/docs/*.md"),
    ("docs", "gbt_allinone/security/*.md"),
)

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_LATIN_TERM_RE = re.compile(r"[A-Za-z0-9_./-]{2,}")
_CJK_BLOCK_RE = re.compile(r"[\u3400-\u9fff]{2,}")


def _project_root() -> Path:
    override = os.environ.get("GBT_PROJECT_ROOT")
    root = Path(override).expanduser() if override else Path(__file__).resolve().parents[1]
    return root.resolve()


def _relative_path(path: Path) -> str:
    return path.relative_to(_project_root()).as_posix()


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(_project_root())
        return True
    except (OSError, ValueError):
        return False


def _read_text(path: Path, max_bytes: int) -> tuple[str, bool]:
    resolved = path.resolve()
    if not _inside_root(resolved):
        raise ValueError("文档路径超出项目根目录")
    if not resolved.is_file():
        raise FileNotFoundError(f"文档不存在: {_relative_path(resolved)}")
    size = resolved.stat().st_size
    data = resolved.read_bytes()[:max_bytes]
    text = data.decode("utf-8", errors="replace")
    return text, size > max_bytes


def _document_entries() -> dict[str, dict]:
    root = _project_root()
    entries: dict[str, dict] = {}
    for source_class, rel in _EXACT_DOCUMENTS:
        path = root / rel
        if path.is_file() and _inside_root(path):
            entries[path.resolve().as_posix()] = {
                "path": rel,
                "source_class": source_class,
            }
    for source_class, pattern in _GLOB_DOCUMENTS:
        for path in root.glob(pattern):
            if path.is_file() and _inside_root(path):
                entries[path.resolve().as_posix()] = {
                    "path": _relative_path(path),
                    "source_class": source_class,
                }
    return entries


def _blueprint_meta(text: str) -> dict:
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    updated = ""
    baseline = ""
    match = re.search(r"更新时间：\s*([^\s>]+)", text)
    if match:
        updated = match.group(1)
    match = re.search(r"基线版本：\s*([^\s>]+)", text)
    if match:
        baseline = match.group(1)
    return {
        "title": title,
        "updated": updated,
        "baseline": baseline,
        "sections": [item.strip() for item in _SECTION_RE.findall(text)],
    }


def blueprint() -> dict:
    """Return the authoritative blueprint and a stable content fingerprint."""
    root = _project_root()
    path = root / "PROJECT_BLUEPRINT.md"
    text, truncated = _read_text(path, _MAX_BLUEPRINT_BYTES)
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return {
        "status": "ok",
        "path": "PROJECT_BLUEPRINT.md",
        "sha256": digest,
        "chars": len(text),
        "truncated": truncated,
        **{k: v for k, v in _blueprint_meta(text).items() if k != "sections"},
        "sections": _blueprint_meta(text)["sections"],
        "content": text,
    }


def brief() -> dict:
    """Return a compact orientation for a new or resumed Codex turn."""
    data = blueprint()
    text = data.get("content", "")
    risks = []
    for line in text.splitlines():
        if re.match(r"^\|\s*R\d+\s*\|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) >= 3:
                risks.append({
                    "id": cells[0],
                    "risk": cells[1],
                    "impact": cells[2],
                })
    return {
        "status": "ok",
        "path": data["path"],
        "sha256": data["sha256"],
        "updated": data.get("updated"),
        "baseline": data.get("baseline"),
        "sections": data.get("sections", []),
        "risks": risks[:8],
        "read_order": [
            "PROJECT_BLUEPRINT.md",
            "AGENTS.md",
            "SOUL.md",
            "USER.md",
            "memory/YYYY-MM-DD.md",
            "LAYOUT.md",
            "CODING_DISCIPLINE.md",
        ],
        "rule": (
            "蓝图是项目和架构的事实索引，不是主人指令的替代品。"
            "实现前先检索相关上下文，验证后更新蓝图。"
        ),
    }


def _terms(query: str) -> list[str]:
    value = str(query or "").lower()
    terms = set(_LATIN_TERM_RE.findall(value))
    for block in _CJK_BLOCK_RE.findall(value):
        if len(block) <= 4:
            terms.add(block)
        else:
            terms.update(block[index:index + 2] for index in range(len(block) - 1))
            terms.update(block[index:index + 3] for index in range(len(block) - 2))
    return sorted((term for term in terms if term), key=len, reverse=True)[:24]


def _snippet(line: str, terms: list[str]) -> str:
    lowered = line.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    start = max(0, min(positions) - 60) if positions else 0
    snippet = line[start:start + _SNIPPET_CHARS].strip()
    if start:
        snippet = "..." + snippet
    if start + _SNIPPET_CHARS < len(line):
        snippet += "..."
    return redact_text(snippet)[0]


def search(query: str, limit: int = 8) -> dict:
    """Rank approved local documents without building a persistent index."""
    query = str(query or "").strip()
    if not query:
        # 同上（主人令 2026-10-09）：陈述缺什么 + 给可直接照抄的示例，不要叫用户"提供"。
        raise ValueError("缺少 query（要检索的项目问题）。例：{\"query\": \"发布链在哪\"}")
    limit = max(1, min(int(limit or 8), _MAX_SEARCH_LIMIT))
    terms = _terms(query)
    if not terms:
        raise ValueError("query 中没有可检索的有效词项")

    hits = []
    scanned = 0
    for entry in _document_entries().values():
        path = _project_root() / entry["path"]
        text, truncated = _read_text(path, _MAX_DOC_BYTES)
        scanned += 1
        for line_number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if not any(term in lowered for term in terms):
                continue
            score = sum(lowered.count(term) * max(1, len(term)) for term in terms)
            if line.lstrip().startswith("#"):
                score += 5
            if entry["source_class"] == "blueprint":
                score += 8
            if entry["source_class"] == "memory":
                score += 2
            hits.append({
                "path": entry["path"],
                "source_class": entry["source_class"],
                "line": line_number,
                "score": score,
                "snippet": _snippet(line, terms),
            })
    hits.sort(key=lambda item: (-item["score"], item["path"], item["line"]))
    return {
        "status": "ok",
        "query": query,
        "terms": terms,
        "scanned_documents": scanned,
        "result_count": len(hits),
        "results": hits[:limit],
    }


def status() -> dict:
    entries = list(_document_entries().values())
    result = {
        "status": "ok",
        "root_source": "GBT_PROJECT_ROOT" if os.environ.get("GBT_PROJECT_ROOT") else "package_parent",
        "documents": sorted(entries, key=lambda item: item["path"]),
        "document_count": len(entries),
        "search_scope": "approved markdown only",
        "writes": False,
        "executes_commands": False,
    }
    try:
        data = blueprint()
        result["blueprint"] = {
            "path": data["path"],
            "sha256": data["sha256"],
            "updated": data.get("updated"),
            "baseline": data.get("baseline"),
            "sections": len(data.get("sections", [])),
        }
    except FileNotFoundError:
        result["blueprint"] = {"status": "missing"}
    return result


def run(op: str = "brief", **kwargs) -> dict:
    operation = str(op or "brief").strip().lower()
    if operation == "brief":
        return brief()
    if operation == "blueprint":
        return blueprint()
    if operation == "search":
        return search(kwargs.get("query", ""), kwargs.get("limit", 8))
    if operation == "status":
        return status()

    # ── 2026-09-23 加：**代码结构四面**（本模块原先只管文档检索，对编程AI 是半身）──
    # 实现落在 `tools/code_structure.py`；这里只做转发，**不把两件事揉进一个文件**。
    # 四面全部只读；每一面都把「诚实边界」跟着结果一起带出去（见各函数 docstring）。
    if operation in ("symbols", "deps", "calls", "tests", "structure"):
        from .tools import code_structure as _cs
        root = kwargs.get("root")
        limit = int(kwargs.get("limit") or 40)
        if operation == "symbols":
            return _cs.symbols(root, name=str(kwargs.get("name") or ""), limit=limit)
        if operation == "deps":
            return _cs.deps(root, limit=limit)
        if operation == "tests":
            return _cs.tests(root, limit=limit)
        if operation == "structure":
            return _cs.structure(root, limit=limit)
        return _cs.calls(root, name=str(kwargs.get("name") or ""),
                         what=str(kwargs.get("what") or "callers"),
                         depth=int(kwargs.get("depth") or 3),
                         do_dead=bool(kwargs.get("dead")))
    return {"status": "error", "message": f"未知 project_context 操作: {operation}"}
