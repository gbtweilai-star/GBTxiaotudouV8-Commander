# gbt-capability: dependency-bootstrap
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""ABI-aware local dependency paths.

The bundled ``.pylibs`` tree may contain wheels for several Python versions.
C-extension packages must not be imported by a different ABI, so each runtime
gets an optional ``.pylibs/<abi>`` overlay ahead of the legacy shared tree.
"""

from __future__ import annotations

import sys
from pathlib import Path


def abi_tag() -> str:
    """Return a stable directory tag such as ``cp314`` or ``py3-none``."""
    cache_tag = str(getattr(sys.implementation, "cache_tag", "") or "")
    if cache_tag.startswith("cpython-"):
        return "cp" + cache_tag.split("-", 1)[1]
    major = sys.version_info.major
    minor = sys.version_info.minor
    flattened = cache_tag.replace("-", "")
    return flattened or f"py{major}{minor}"


def local_dependency_paths() -> list[Path]:
    """Ordered dependency roots for the current interpreter, highest priority first."""
    base = Path(__file__).resolve().parent / ".pylibs"
    return [base / abi_tag(), base]

def _readable_abi_overlay(path: Path) -> bool:
    """Avoid putting sandbox-blocked or partially hydrated wheels on sys.path."""
    if not path.is_dir():
        return False
    probes = (path / "numpy" / "__init__.py", path / "PIL" / "__init__.py")
    for probe in probes:
        if not probe.exists():
            continue
        try:
            with probe.open("rb") as stream:
                stream.read(1)
            return True
        except OSError:
            return False
    return True


def activate_local_dependencies() -> list[Path]:
    """Put ABI-specific dependencies ahead of the shared legacy directory."""
    activated = []
    abi_path, base = local_dependency_paths()
    if _readable_abi_overlay(abi_path):
        text = str(abi_path)
        if text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)
        activated.append(abi_path)
    if base.is_dir():
        text = str(base)
        if text in sys.path:
            sys.path.remove(text)
        # System/site packages win over the legacy tree so a wrong-ABI wheel
        # can never shadow a working installation.
        sys.path.append(text)
        activated.append(base)
    return activated
