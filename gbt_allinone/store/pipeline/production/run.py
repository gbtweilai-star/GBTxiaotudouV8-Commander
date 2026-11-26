# GBT cap: slugify-test
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""caps/slugify-test/run.py — 吞噬知识胶囊: sindresorhus/slugify"""
import json, sys
from pathlib import Path

ABS = Path(__file__).parent / "absorbed_knowledge.md"

def do_knowledge(params=None):
    if ABS.exists():
        return {"ok": True, "knowledge": ABS.read_text(encoding="utf-8")}
    return {"ok": False, "error": "absorbed_knowledge.md 缺失"}

def do_status(params=None):
    return {"ok": True, "cap": "slugify-test", "tier": "knowledge", "has_knowledge": ABS.exists()}

HANDLERS = {"knowledge": do_knowledge, "run": do_knowledge, "status": do_status}

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(HANDLERS.get(action, do_status)(params), ensure_ascii=False))
