# -*- coding: utf-8 -*-
"""brain.gatekeeper 兼容垫片：旧 omni_* 的截图写盘改走 V8 镜像管线（submit）。

修复断头路：omni_vision.screenshot 引用 brain.gatekeeper.publish，
V8 独立成家后该路径断头。本垫片把写盘诉求转接 V8 pipeline.submit（受保护写盘）。
"""
import shutil
from pathlib import Path


def publish(file_path: str, content: str = None, context: str = "") -> dict:
    """V8 镜像管线写盘（旧 gatekeeper.publish 的等价转接）。"""
    try:
        from gbt_allinone import pipeline as _pipe
        from gbt_allinone._paths import STORE_DIR

        p = Path(file_path)
        name = p.name
        r = _pipe.submit(name, content or "",
                         {"actor": "tentacle_vision", "purpose": context or "视觉产物写盘"})
        if isinstance(r, dict) and r.get("status") == "published":
            prod = STORE_DIR / "pipeline" / "production" / name
            # 调用方给了具体目录时，发布后同步复制到目标位置
            if p.parent and p.parent != prod.parent:
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(prod, p)
                return {"ok": True, "file": str(p), "via": "mirror_pipeline+copy"}
            return {"ok": True, "file": str(prod), "via": "mirror_pipeline"}
        if isinstance(r, dict) and r.get("status") == "blocked":
            return {"ok": False, "error": f"管线拦截: {r.get('stage3_publish', {}).get('reason', '?')}"}
        return {"ok": False, "error": str(r)[:120]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"gatekeeper 垫片: {str(e)[:120]}"}


# AGENTS.md 兼容入口
get_gatekeeper = publish
