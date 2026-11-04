# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""能力图鉴生成器（skill_atlas）· 2026-11-04 补齐

## 为什么有这个文件

判据 A 要求「能力位三处齐：登记 · **图鉴** · 分派」，判据链
（`test_chain_readiness` / `test_cap_bind_bidirectional`）都要读
`state/skill_atlas.json`，其结构是 `{"caps": [{"kind": <能力位名>, ...}, ...]}`。

**但图鉴的数据、生成器、定义三者全缺**：
  · `state/skill_atlas.json` 不在盘；
  · 生成器 `omni.py` 在本仓不存在（`tools/omni.py`、`gbt_allinone/tools/omni.py` 均无，
    git 全历史 0 条）——而 `growth_hooks.py:86` 写着「跑 omni.py build 重建图鉴」；
  · 「图鉴」与 `caps_registry` 的关系没有任何文字说明。

## 本生成器的口径（不猜，只投影）

图鉴 = **注册表 `all_caps()` 的投影**。一个能力位在注册表里 ⇒ 就在图鉴里。
这不是原作者的原始实现（原实现不可考），而是**按判据语义能做到的最诚实版本**：
- 条目全部来自现读，没有一个字是编的；
- 每条都带 `src` 与 `generated_at`，任何人重跑都能得到同一份；
- 若主人日后给出真正的 `omni.py build`，直接用它覆盖本文件即可（结构兼容）。

## 用法

    python tools/build-skill-atlas.py            # 生成/覆盖 state/skill_atlas.json
    python tools/build-skill-atlas.py --check    # 只比对，不写盘（CI 可用）
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "skill_atlas.json"
META = {
    "_generated_by": "tools/build-skill-atlas.py",
    "_source": "gbt_allinone/caps_registry.all_caps()（现读，非硬编码）",
    "_note": "原始生成器 omni.py 在本仓从未存在；本图鉴是注册表的投影，"
             "语义 = 「该能力位在册即收录」。若日后拿到 omni.py build，可整体覆盖本文件",
    "_口径": "caps[].kind 就是能力位名；判据只读这个字段",
}


def build() -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import caps_registry as CR

    caps = CR.all_caps()
    rows = []
    for c in sorted(caps, key=lambda x: x.get("name") or ""):
        if not isinstance(c, dict) or not c.get("name"):
            continue
        rows.append({
            "kind": c["name"],
            "domain": c.get("domain"),
            "safe": c.get("safe"),
            "requires_params": c.get("requires_params"),
            "status": c.get("status"),
            "desc": (c.get("desc") or "")[:160],
        })
    return {
        **META,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(rows),
        "by_domain": {d: sum(1 for r in rows if r["domain"] == d)
                      for d in sorted({r["domain"] for r in rows if r["domain"]})},
        "caps": rows,
    }


def main() -> int:
    doc = build()
    check = "--check" in sys.argv
    if check:
        if not OUT.is_file():
            print(f"❌ 图鉴不在盘：{OUT}")
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        a = {(c.get("kind"), c.get("domain")) for c in old.get("caps") or []}
        b = {(c.get("kind"), c.get("domain")) for c in doc["caps"]}
        if a != b:
            print(f"❌ 图鉴已漂移：盘上 {len(a)} 条 · 现读 {len(b)} 条 "
                  f"· 多出 {sorted(b - a)[:5]} · 少了 {sorted(a - b)[:5]}")
            return 1
        print(f"✅ 图鉴与注册表一致（{len(b)} 条）")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT)
    print(f"✅ 已生成 {OUT.relative_to(ROOT)}：{doc['count']} 条 · "
          f"{len(doc['by_domain'])} 个域")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
