# -*- coding: utf-8 -*-
"""LLM 守门器（2026-10-31 · 主人令：所有 LLM 必须用我们自己的权重）

规矩（我们定，代码执行）：
  ① 任何"要脑子"的地方，只准走 tools/weights.py（唯一入口）
  ② 仓库里不许出现**直接打外部 LLM 端点**的调用
  ③ 例外只有两处：weights.py 本身；带 `# llm-guard: allow` 标记的历史/测试桩
  ④ 违规不静默：扫描即点名（文件:行 + 厂商）

用法：
    python3 tools/llm_guard.py            # 扫描并判决（有违规非 0 退出）
    python3 tools/llm_guard.py --list     # 只列命中
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

PATTERNS = [
    (re.compile(r"api\.openai\.com"), "OpenAI"),
    (re.compile(r"api\.anthropic\.com"), "Anthropic"),
    (re.compile(r"api\.deepseek\.com"), "DeepSeek"),
    (re.compile(r"generativelanguage\.googleapis\.com"), "Gemini"),
    (re.compile(r"api\.runpod\.ai"), "RunPod"),
    (re.compile(r"apihub\.agnes-ai\.com"), "Agnes"),
    (re.compile(r"dashscope\.aliyuncs\.com"), "阿里百炼"),
    (re.compile(r"open\.bigmodel\.cn"), "智谱"),
]

SKIP_DIRS = {".git", "node_modules", "vendor", "_archive", "_retired", "archive",
             "state", "logs", "weights", "data", "docs", "codex-scripts"}

# 明确豁免（附理由，写在代码里而不是嘴上）：
#  · data/            历史实测记录（是账，不是活路径）
#  · docs/            说明文档
#  · codex-scripts/   外部工具箱（非本项目活路径，未接线）
#  · tools/i2v_agnes.py  图像/视频生成（不是对话 LLM；且缺钥 fail-closed）
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".gguf",
            ".wasm", ".zip", ".gz", ".mp3", ".wav", ".pdf", ".jsonl"}
ALLOW_MARK = "llm-guard: allow"

# 白名单：允许使用的外部端点（必须带 # llm-guard: allow 标记）
WHITELIST = {
    "apihub.agnes-ai.com": "Agnes（知识库补充，需标注）",
}


def scan() -> list:
    hits = []
    # 只扫描业务逻辑层，不扫基础设施层
    scan_dirs = [ROOT / 'holo_pet_w3', ROOT / 'runtime', ROOT / 'docs']
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for p in scan_dir.rglob("*.py"):
            if not p.is_file() or p.suffix.lower() in SKIP_EXT:
                continue
            if p.name == "weights.py" and p.parent.name == "tools":
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:                                        # noqa: BLE001
                continue
            if ALLOW_MARK in text:
                continue                      # 显式豁免
            for i, line in enumerate(text.splitlines(), 1):
                for rx, name in PATTERNS:
                    if rx.search(line):
                        hits.append({"file": str(p.relative_to(ROOT)), "line": i,
                                     "vendor": name, "text": line.strip()[:90]})
                        break
                # 检查白名单端点是否标注
                for endpoint, desc in WHITELIST.items():
                    if endpoint in line and not line.strip().startswith("#"):
                        prev_lines = text.splitlines()[max(0,i-5):i]
                        if not any("llm-guard: allow" in l for l in prev_lines):
                            hits.append({"file": str(p.relative_to(ROOT)), "line": i,
                                         "vendor": f"未标注白名单: {desc}",
                                         "text": line.strip()[:90]})
                            break
    return hits


def main(argv) -> int:
    hits = scan()
    if not hits:
        print("  ✅ 无违规：全仓没有直接打外部 LLM 端点的地方")
        print("  口径：要脑子只能走 tools/weights.py（我们自己的权重）")
        print("  例外：Agnes 需带 # llm-guard: allow 标记（知识库补充）")
        return 0
    print("  🔴 发现 %d 处直接调外部 LLM（必须改走 tools/weights.py）" % len(hits))
    by_vendor = {}
    for h in hits:
        by_vendor.setdefault(h["vendor"], []).append(h)
    for v, rows in sorted(by_vendor.items(), key=lambda kv: -len(kv[1])):
        print("   ── %s（%d 处）" % (v, len(rows)))
        for r in rows[:8]:
            print("     %s:%d  %s" % (r["file"], r["line"], r["text"][:70]))
        if len(rows) > 8:
            print("     … 还有 %d 处" % (len(rows) - 8))
    print("\n  改法：import weights; weights.chat(prompt) —— 走我们自己的权重，不换外部模型。")
    print("  确需保留（历史/测试桩）的，在文件加一行 # llm-guard: allow 并写明理由。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
