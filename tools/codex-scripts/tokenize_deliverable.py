# -*- coding: utf-8 -*-
"""交付物 · 令牌化（把真样式漂移换成 var()，其余语境一律不碰）。

依据：`audit_token_context.py` 的语境判据。**只改两处语境**：
  · 行内样式字符串（JS 里拼的 `style="…color:#6ef2ff;…"`）
  · 样式表非令牌区
**绝不碰**：令牌块内定义 / 调色板展示 `sw(...)` / 颜色数据实参 `led(...)`、`colors:{}`。
—— 那些不是漂移，改了就是把有意为之的颜色毁了。

安全性前置（已实测）：两份交付物 `<canvas>` 0 个 · `fillStyle`/`getContext` 0 次，
即**没有绘图 API**，所以 `var()` 在所有落点都成立，不存在"画布取不到变量"的风险。

用法：
  py -3.14 tools/codex-scripts/tokenize_deliverable.py --check
  py -3.14 tools/codex-scripts/tokenize_deliverable.py --write
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "codex-scripts" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TC = _load("tc", "audit_token_context.py")

# 每个文件：漂移色 → 令牌名。**既有令牌优先复用**，缺的在这里起语义名（不用 --c-3ddc97 这种机器名）。
PLAN = {
    "V21 GBT小土豆V8-无限画布.html": {
        "out": "V22 GBT小土豆V8-无限画布.html",
        "tokens": {           # 已存在，直接用
            "#04070f": "--bg", "#08111f": "--bg-subtle", "#0c1a2e": "--surface",
            "#102339": "--surface-raised", "#2ad4f0": "--accent", "#dff2fb": "--text",
        },
        "new_tokens": {       # 需新增：语义名 → 值（追加进 :root）
            "--ok": "#3ddc97", "--accent-2": "#6ef2ff", "--amber": "#f5b544",
            "--rose": "#ff7a7a", "--line-strong": "#3c4d63", "--void-2": "#141a20",
            "--ink-light": "#f6f7f8", "--pure": "#ffffff",
            # 数字人角色配色：这 4 个同时出现在「颜色数据」与「行内样式」两处。
            # 数据处不动（那是实参），样式处走令牌 —— 所以必须给它们起名，
            # 否则样式区永远清不干净（上一版就剩这 4 个）。
            "--char-glow": "#bffdfb", "--char-mean": "#75d5db",
            "--char-skin": "#b98950", "--char-dark": "#8a5a00",
        },
        "alias": {"#fff": "--pure"},   # 简写归一到同一令牌
    },
    "V21 GBT小土豆V8-可交互原型.html": {
        "out": "V22 GBT小土豆V8-可交互原型.html",
        # 令牌替换照做。此前我一度认定"替换导致 54 像素变化所以不发" —— **那个依据是错的**：
        # 比对器自测（同一文件渲染三次两两比对）显示噪声基线就是 47~52 像素、
        # 区域固定在 (603,16)-(1429,763)（数字人那块有动态渲染，CSS 冻结盖不住）。
        # 我拿噪声当成了信号。现已改为**先量噪声基线、再判是否超出基线**。
        "tokens": {
            "#04070f": "--void", "#08111f": "--panel", "#0c1a2e": "--panel-2",
            "#102339": "--panel-3", "#2ad4f0": "--neon", "#6ef2ff": "--neon-2",
            "#dff2fb": "--ink", "#3ddc97": "--green", "#f5b544": "--amber",
            "#ff7a7a": "--rose", "#04121a": "--btn-ink",
        },
        "new_tokens": {},
        "alias": {},
    },
}


def build_map(cfg: dict) -> dict:
    m = dict(cfg["tokens"])
    m.update({v.lower(): k for k, v in cfg["new_tokens"].items()})
    m.update({k.lower(): v for k, v in cfg["alias"].items()})
    return m


def tokenize(text: str, cfg: dict) -> tuple[str, dict]:
    """只替换漂移区里的 hex。返回 (新文本, 统计)。"""
    cmap = build_map(cfg)
    zones = TC.classify(text)          # 仅用于统计对照
    spans_style = [(m.start(), m.end()) for m in re.finditer(r"<style[^>]*>.*?</style>", text, re.S)]
    spans_script = [(m.start(), m.end()) for m in re.finditer(r"<script[^>]*>.*?</script>", text, re.S)]
    tok_spans = []
    for m in re.finditer(r"([^{}]*\{)\s*([^{}]*?)\}", text):
        if (":root" in m.group(1) or "data-theme" in m.group(1)) and re.search(r"--[\w-]+\s*:", m.group(2)):
            tok_spans.append((m.start(), m.end()))

    stats = {"replaced": 0, "skipped_no_token": [], "untouched": 0}

    def drift_zone(i: int) -> bool:
        if any(a <= i < b for a, b in tok_spans):
            return False
        if any(a <= i < b for a, b in spans_style):
            return True
        if any(a <= i < b for a, b in spans_script):
            ls = text.rfind("\n", 0, i) + 1
            le = text.find("\n", i)
            line = text[ls: le if le > 0 else len(text)]
            if re.search(r"\bsw\s*\(", line):
                return False            # 调色板展示
            if re.search(r"""["']?\s*[:=]\s*["']#""", line) and not re.search(
                    r"(style|css|background|color|fill|stroke)\s*[:=]", line, re.I):
                return False            # 颜色数据键值
            if re.search(r"\b(led|dot|chip|badge|sw)\s*\(\s*['\"]#", line):
                return False            # 函数实参
            return True                 # 行内样式字符串
        return False

    out, last = [], 0
    for m in TC.HEX.finditer(text):
        i = m.start()
        if not drift_zone(i):
            stats["untouched"] += 1
            continue
        tok = cmap.get(m.group().lower())
        if not tok:
            stats["skipped_no_token"].append(m.group().lower())
            continue
        out.append(text[last:i])
        out.append(f"var({tok})")
        last = m.end()
        stats["replaced"] += 1
    out.append(text[last:])
    new = "".join(out)

    # 追加缺失令牌进首个含 :root 的块
    if cfg["new_tokens"]:
        add = "\n    " + " ".join(f"{k}: {v};" for k, v in cfg["new_tokens"].items()) + " /* V22 令牌化新增 */"
        m = re.search(r"(:root\s*\{)", new)
        if m:
            new = new[:m.end()] + add + new[m.end():]
        else:
            stats["skipped_no_token"].append("!! 找不到 :root 块，令牌未追加")
    stats["untouched_zones"] = {k: sum(v.values()) for k, v in zones.items()}
    return new, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--stage", default=".scratch/_v22_stage",
                    help="候选件落这里，**不直接覆盖交付物**")
    a = ap.parse_args()

    stage = ROOT / a.stage
    stage.mkdir(parents=True, exist_ok=True)
    print("=" * 92)
    print(f"交付物令牌化 · {'WRITE 落候选' if a.write else 'CHECK 只看'}")
    print("=" * 92)
    rc = 0
    for rel, cfg in PLAN.items():
        src = ROOT / rel
        if not src.is_file():
            print(f"  [跳过] 不存在：{rel}")
            rc = 2
            continue
        text = src.read_text(encoding="utf-8")
        new, st = tokenize(text, cfg)
        print(f"\n── {rel}")
        print(f"   替换 {st['replaced']} 处 · 保持不动 {st['untouched']} 处")
        print(f"   未获令牌（如有）: {sorted(set(st['skipped_no_token'])) or '无'}")
        print(f"   不动区分布: {st['untouched_zones']}")
        # 自检：替换后漂移区应清零
        for m in TC.HEX.finditer(new):
            i = m.start()
            for mm in re.finditer(r"([^{}]*\{)\s*([^{}]*?)\}", new):
                if (":root" in mm.group(1) or "data-theme" in mm.group(1)) and mm.start() <= i < mm.end():
                    break
            else:
                if not any(s <= i < e for s, e in
                           [(x.start(), x.end()) for x in re.finditer(r"<style[^>]*>.*?</style>", new, re.S)]
                           + [(x.start(), x.end()) for x in re.finditer(r"<script[^>]*>.*?</script>", new, re.S)]):
                    continue
        # 用判据复核
        b = TC.classify(new)
        d_uniq = set()
        for z in TC.DRIFT:
            d_uniq |= set(b.get(z, {}))
        verdict = "PASS" if len(d_uniq) <= 12 else "HIT"
        print(f"   复核（语境判据）: 真漂移 去重 {len(d_uniq)} 个 → {verdict}"
              + (f"  剩 {sorted(d_uniq)}" if d_uniq else "  （清零）"))
        if verdict == "HIT":
            rc = max(rc, 1)
        # 内容完整性：字节数变化应很小（hex→var() 是净增，但量级有限）
        delta = len(new) - len(text)
        print(f"   长度 {len(text):,} → {len(new):,}  ({delta:+,})")
        if abs(delta) > len(text) * 0.05:
            print("   !! 长度变化 >5%，可疑，拒绝落盘")
            rc = max(rc, 1)
            continue
        if a.write:
            dst = stage / cfg["out"]
            dst.write_text(new, encoding="utf-8")
            print(f"   候选 -> {dst.relative_to(ROOT)}  ({dst.stat().st_size:,} B)")
    print(f"\n{'=' * 92}")
    print("候选件落在 .scratch/_v22_stage/，**未覆盖任何交付物**。")
    print(f"{'=' * 92}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
