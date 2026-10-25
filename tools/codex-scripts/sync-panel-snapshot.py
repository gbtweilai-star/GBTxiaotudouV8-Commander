#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**把面板里那份过期快照对齐到现读**（只动工作区源稿，绝不碰 `deploy/`）。

由来（2026-09-25 主人现读发现）：
    面板上写着「**11 个能力已禁用** · 危险项只登记不提供入口」。
    而注册表现读：`DISABLED_CAPS = 0`、`UNIMPLEMENTED_CAPS = 0` —— **一个都没禁**。
    真正的原因：面板里嵌的是 **`scanned_at: 2026-09-21T03:05:28` 的快照**，
    而**重建它的脚本跑不动**（`tools/codex-scripts/` 那批 `.parent.parent` 算错一层，
    86 个文件；已由 `fix-base-paths.py` 修好）⇒ 快照从此再没人能刷新。

本脚本做的事（**逐项可复核**）：
  1. 用**现读真身**重算 `meta`（能力总数/可用/禁用/门/缺口/接线/判定…）；
  2. 把 `caps_source` 的 `benign` / `disabled` 与 `domain_dist` 对齐现读；
  3. 把面板那句**过期的原因**改成**两种状态都成立**的说法
     （原文「危险项只登记不提供入口」在 9-25 接线后已不成立）。

🔴 只写 `--file` 指定的那一份（默认工作区源稿）。
   `deploy/index.html` 是**已发布件 + 外网写入落点**（仓里明写「绝不许动」）⇒ 不是它的活，
   要不要重新发布由主人决定。

用法：
  python tools/codex-scripts/sync-panel-snapshot.py                # dry-run：只报差异
  python tools/codex-scripts/sync-panel-snapshot.py --apply        # 落盘
  python tools/codex-scripts/sync-panel-snapshot.py --file <路径> --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gbt_allinone.caps_registry import BENIGN_CAPS, DISABLED_CAPS, UNIMPLEMENTED_CAPS  # noqa: E402

DEFAULT_FILE = ROOT / "V22 GBT小土豆V8-可交互原型.html"
STALE_CLAUSE = "· 危险项只登记不提供入口"
NEW_CLAUSE = "· 危险项已接实现、逐一走人工授权门"


MANIFEST = ROOT / ".scratch" / "hud_manifest.json"


def fresh() -> dict:
    """现读真身。

    🔴 优先用**修好的生成器**刚吐出来的 `.scratch/hud_manifest.json`（`build_hud_manifest.py`）——
       因为它算的不只是"注册表几条"，还有 gated / wired / 审计窗口 / 判定 等一整组读数；
       只从注册表重算会漏掉那些键 ⇒ **改成只对齐一半 = 毛坯**（本仓最忌）。
       生成器还没跑过时，退回注册表能算的那几个，并**如实说明**少对齐了哪些。
    """
    dist = Counter((v or {}).get("domain") for v in BENIGN_CAPS.values())
    base = {
        "total": len(BENIGN_CAPS),
        "executable": len(BENIGN_CAPS),
        "disabled": len(DISABLED_CAPS),
        "unimplemented": len(UNIMPLEMENTED_CAPS),
        "domains": len([d for d in dist if d]),
        "domain_dist": dict(sorted(dist.items())),
        "_source": "caps_registry（现算）",
    }
    if MANIFEST.is_file():
        try:
            m = json.loads(MANIFEST.read_text(encoding="utf-8")).get("meta") or {}
            base.update({k: v for k, v in m.items() if not k.startswith("_")})
            base["_source"] = str(MANIFEST.relative_to(ROOT)) + "（生成器现吐）"
        except Exception as e:                                   # noqa: BLE001
            base["_manifest_error"] = "%s: %s" % (type(e).__name__, str(e)[:80])
    return base


def _value_span(text: str, key: str, start: int, end: int):
    """找 `"key": <value>` 里 **value 的精确跨度**（`(vstart, vend)`）——用 JSON 解码器定位。

    🔴 2026-09-25 **当场修我自己的错**：第一版拿正则 `(:\\s*)([^,\\n]+)(,?)` 抓值，
       而它对**多行对象**只会抓到 ` {`（到换行就断）⇒ 替换后把原对象的身体留在原地，
       **把整块嵌数据写坏了**（`"audit_by_event": {…}` 后面多出一段孤儿键值）。
       而 `verify_v22.py` **没报**（它那条"无 undefined 字面量"检查里写着 `or True`，等于空转）。
       ⇒ 改成：从冒号后起用 `json.JSONDecoder().raw_decode` **按 JSON 语法**吃掉一个完整值，
         拿它的真实跨度做替换 —— 对象/数组/字符串/数字一视同仁。
    """
    m = re.search(r'"%s"\s*:\s*' % re.escape(key), text[start:end])
    if not m:
        return None
    vstart = start + m.end()
    try:
        _, vend = json.JSONDecoder().raw_decode(text, vstart)
    except ValueError:
        return None
    return vstart, vend


def meta_patch(text: str, now: dict) -> tuple:
    """只改 `"meta": {…}` 那一段里的键（**按 JSON 值的真实跨度**替换，不动别处）。"""
    i = text.find('"meta": {')
    if i < 0:
        return text, ["找不到 meta 块"]
    j = text.find("\n  },", i)
    if j < 0:
        return text, ["找不到 meta 块结尾"]
    notes = []
    for key, val in now.items():
        if key.startswith("_"):
            continue
        span = _value_span(text, key, i, j)
        if span is None:
            continue                      # meta 里本来没有这个键 ⇒ 不硬塞（保持原结构）
        a, b = span
        old = text[a:b]
        new = json.dumps(val, ensure_ascii=False)
        if old != new:
            notes.append("meta.%s: %s -> %s" % (key, old[:40].replace("\n", " "), new[:60]))
            text = text[:a] + new + text[b:]
            j += len(new) - len(old)
    return text, notes


def blob_probe(text: str) -> tuple:
    """嵌数据`const V21 = …{…}` 的**精确跨度**与合法性。

    🔴 同样修过一版：第一版用**手写花括号计数**找结尾 —— 而 559KB 的嵌数据里
       **字符串值里就有花括号**，计数器被带偏，跨度算错（"找不到 const V21"就是这么来的）。
       ⇒ 改用 `json.JSONDecoder().raw_decode`：它按 JSON 语法走，字符串/转义一律正确处理。
    """
    i = text.find("const V21 = ")
    if i < 0:
        return None, "找不到 `const V21 = `"
    j = text.find("{", i)
    try:
        _, end = json.JSONDecoder().raw_decode(text, j)
        return (j, end), "OK（%d 字符）" % (end - j)
    except ValueError as e:
        return None, "%s" % str(e)[:140]


def blob_is_valid(text: str) -> tuple:
    sp, why = blob_probe(text)
    return (sp is not None), why


def repair_orphans(text: str) -> tuple:
    """修掉"值后面跟了一段孤儿键值"的那种损坏（把多行对象当单值替换留下的伤）。"""
    notes = []
    for key in re.findall(r'"([a-z_0-9]+)"\s*:\s*\{', text):
        pass
    i = text.find('"audit_by_event"')
    if i < 0:
        return text, notes
    span = _value_span(text, "audit_by_event", i, i + 4000)
    if span is None:
        return text, notes
    a, b = span
    tail = text[b:]
    if tail.lstrip().startswith((",", "}")):
        return text, notes                       # 没有孤儿
    end = tail.find("\n  }")
    if end < 0:
        return text, ["audit_by_event 后面有东西，但找不到孤儿块的结尾 —— 没敢改"]
    orphan = text[b:b + end + len("\n  }")]
    notes.append("修孤儿块：删掉 %d 字符（原是 9-21 的 audit_by_event 身体）" % len(orphan))
    return text[:b] + text[b + len(orphan):], notes


def caps_source_patch(text: str, now: dict) -> tuple:
    """把整个 `caps_source` 对象**照现读重建**（不是只补两个数）。

    🔴 台账 N10：上一轮我只对齐了 `benign` / `disabled`，把 **`domain_dist` 留在 9-21**
       （`llm: 18` 现读 20 · `system: 20` 现读 21 · `data: 5` 现读 6 · `security: 5` 现读 17 …）——
       **只对齐一半 = 毛坯**。这一轮改成整块重建：它的键全部来自注册表现算，一处都不留旧值。
    """
    i = text.find('"caps_source"')
    if i < 0:
        return text, []
    j = text.find("{", i)
    depth, k = 0, j
    while k < len(text):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    if k >= len(text):
        return text, ["caps_source 块没闭合，跳过"]
    old_blk = text[j:k + 1]
    try:
        old = json.loads(old_blk)
    except Exception:                                            # noqa: BLE001
        old = {}
    # 键序照原块保留；原块没有的键追加在后（保持文件形态稳定）
    order = [x for x in ("benign", "disabled", "domains", "file", "domain_dist") if x in old]
    order += [x for x in ("benign", "disabled", "domains", "file", "domain_dist")
              if x not in order]
    src = {"benign": now["total"], "disabled": now["disabled"], "domains": now["domains"],
           "file": "gbt_allinone/caps_registry.py", "domain_dist": now["domain_dist"]}
    new_obj = {x: src[x] for x in order if x in src}
    lines = json.dumps(new_obj, ensure_ascii=False, indent=1).splitlines()
    lines[0] = "{"                                     # 首行的 `{` 与 `"caps_source": ` 同行
    new_blk = "\n".join(("  " if n else "") + ln for n, ln in enumerate(lines))
    notes = []
    for key in ("benign", "disabled", "domains"):
        if str(old.get(key)) != str(src[key]):
            notes.append("caps_source.%s: %s -> %s" % (key, old.get(key), src[key]))
    od = old.get("domain_dist") or {}
    changed = {d: (od.get(d), src["domain_dist"].get(d)) for d in set(od) | set(src["domain_dist"])
               if od.get(d) != src["domain_dist"].get(d)}
    if changed:
        notes.append("caps_source.domain_dist: %d 个域不对（%s…）"
                     % (len(changed), "、".join("%s %s->%s" % (d, a, b)
                                               for d, (a, b) in sorted(changed.items())[:6])))
    if not notes:
        return text, []
    return text[:j] + new_blk + text[k + 1:], notes


def clause_patch(text: str) -> tuple:
    if STALE_CLAUSE in text:
        return text.replace(STALE_CLAUSE, NEW_CLAUSE), ["文案：%s -> %s" % (STALE_CLAUSE, NEW_CLAUSE)]
    return text, []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="把面板快照对齐现读（默认 dry-run）")
    ap.add_argument("--file", default=str(DEFAULT_FILE))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    p = Path(a.file)
    if not p.is_file():
        print("文件不在：%s" % p, file=sys.stderr)
        return 2
    now = fresh()
    print("现读真身：总数 %d · 可用 %d · **禁用 %d** · 未实现 %d · 域 %d"
          % (now["total"], now["executable"], now["disabled"], now["unimplemented"], now["domains"]))
    text = p.read_text(encoding="utf-8", errors="replace")
    ok0, why0 = blob_is_valid(text)
    print("改前嵌数据：%s（%s）" % ("合法" if ok0 else "**不合法**", why0))
    notes = []
    text, n0 = repair_orphans(text)
    notes += n0
    text, n1 = meta_patch(text, now)
    notes += n1
    text, n2 = caps_source_patch(text, now)
    notes += n2
    text, n3 = clause_patch(text)
    notes += n3
    ok1, why1 = blob_is_valid(text)
    print("改后嵌数据：%s（%s）" % ("合法" if ok1 else "**不合法**", why1))
    if not ok1:
        print("\n🔴 改后嵌数据不合法 ⇒ **拒绝落盘**（宁可不动，也不交付一坨坏数据）。", file=sys.stderr)
        return 2
    if not notes:
        print("已经与现读一致，无需改动。")
        return 0
    print("\n将改 %d 处：" % len(notes))
    for x in notes:
        print("   · %s" % x)
    if not a.apply:
        print("\n（dry-run：加 --apply 才落盘）")
        return 1
    p.write_text(text, encoding="utf-8")
    print("\n已落盘：%s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
