# -*- coding: utf-8 -*-
"""审计流完整性 —— **计数 + 告警**（蓝图 §9.1 · Q3，2026-10-08 立）。

## 为什么这件必须存在

登记在案的问题（P1 · 审计完整性）：
    生产审计流里有**坏 JSON 行**（登记时 287,891 行里 311 行，0.108%），
    而**当前无人计数、无人告警** —— 也就是说这本账坏到什么程度，没人知道。

2026-10-08 现算复测：**447,830 行里 330 行坏**（0.074%）⇒ 账在长、坏行也在长
（311 → 330），仍然没有计数与告警。所以把它落成一件**能天天跑的判据**：
坏行 > 0 就退出码 1（告警），并且**如实报出坏行的样子**，不许只说"有坏行"。

## 口径（不许含糊）

- **物理非空行**才算分母（空行是排版，不是账）；
- 坏行 = 这一行 `json.loads` 失败 —— **不猜它"本来想写什么"**；
- 分类只做**形态描述**（片段/交错/其它），不下根因结论：根因要靠写入侧的证据；
- **不修账**：这本流是**只追加**的账，手改一行就是伪造历史。要修只能由写入侧
  补一条"XX 行损坏"的说明记录 —— 那是账主的决定，不是本工具的。

用法：
    py -3.14 tools/codex-scripts/audit-integrity.py                     # 默认查生产审计流
    py -3.14 tools/codex-scripts/audit-integrity.py --path <file>       # 查别的 jsonl
    py -3.14 tools/codex-scripts/audit-integrity.py --json              # 机器读
    py -3.14 tools/codex-scripts/audit-integrity.py --samples 5         # 多看几条坏行
退出码：0 = 干净 · 1 = 有坏行（告警）· 2 = 查不了（文件不在/读不动）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET = ROOT / "gbt_allinone" / "store" / "audit.jsonl"


def classify(raw: str) -> str:
    """只描述**形态**，不下根因结论。

    实测见到的两类（2026-10-08）：`[]}}`、`ad_keys": []}}` —— 都是 JSON 的**尾片段**，
    与"两个写者同时追加、各自写了一半"的形态一致；但也可能来自别的原因，
    所以这里只标形态，把判断留给写入侧的证据。
    """
    s = raw.strip()
    if not s:
        return "空白"
    if s.startswith("{") or s.startswith("["):
        return "截断（开头像 JSON，尾巴断了）"
    if s.endswith("}}") or s.endswith("]}}") or s.endswith('"}'):
        return "尾片段（像是上一行被截走的尾巴）"
    return "其它"


def scan(path: Path, samples: int) -> dict:
    total = bad = 0
    bad_samples = []
    kinds = {}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            total += 1
            try:
                json.loads(line)
            except Exception as exc:                                  # noqa: BLE001
                bad += 1
                k = classify(line)
                kinds[k] = kinds.get(k, 0) + 1
                if len(bad_samples) < samples:
                    bad_samples.append({"line": i, "kind": k,
                                        "text": line[:120].rstrip(),
                                        "why": str(exc)[:70]})
    return {"path": str(path), "lines": total, "bad": bad,
            "ratio_pct": round(100.0 * bad / total, 4) if total else 0.0,
            "kinds": kinds, "samples": bad_samples}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="审计流完整性：坏 JSON 行计数 + 告警")
    p.add_argument("--path", default=str(DEFAULT_TARGET))
    p.add_argument("--json", action="store_true")
    p.add_argument("--samples", type=int, default=3)
    args = p.parse_args(argv)

    target = Path(args.path)
    if not target.is_file():
        msg = {"ok": False, "why": "文件不在：%s" % target}
        print(json.dumps(msg, ensure_ascii=False) if args.json
              else "查不了：文件不在 %s" % target)
        return 2

    res = scan(target, args.samples)
    res["ok"] = res["bad"] == 0

    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print("=" * 78)
        print("审计流完整性（**只计数、不修账**：这本流只许追加，手改一行就是伪造历史）")
        print("=" * 78)
        print("  文件：%s" % res["path"])
        print("  物理非空行：%d" % res["lines"])
        print("  坏 JSON 行：%d（%.4f%%）" % (res["bad"], res["ratio_pct"]))
        if res["kinds"]:
            print("  形态分布：%s" % " · ".join("%s×%d" % (k, v) for k, v in res["kinds"].items()))
        for s in res["samples"]:
            print("    · 第 %d 行 [%s] %r ← %s" % (s["line"], s["kind"], s["text"], s["why"]))
        print("-" * 78)
        if res["bad"]:
            print("  🔴 告警：有 %d 行坏账 ⇒ 退出码 1。" % res["bad"])
            print("     **怎么修**：不许手改账；由**写入侧**查并发追加是否加锁，"
                  "再补一条说明记录。")
        else:
            print("  ✅ 干净：0 行坏账。")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
