# -*- coding: utf-8 -*-
"""accept_comfy -- 秋叶版能力验收（判据按题型分派，2026-10-16 修）"""
from __future__ import annotations

import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
NEED = {
    "txt2img": ["CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"],
    "img2img": ["CheckpointLoaderSimple", "LoadImage", "VAEEncode", "KSampler", "VAEDecode", "SaveImage"],
    "txt2video": ["CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "VHS_VideoCombine"],
}


# 🔴 2026-10-17 追加（**留痕 · 口径不变，只把判据显式化**）：
#   原口径：文本题判据内联在 `text_ok()` 的 if 链里 —— 人看得懂，但**语料生成器读不到**
#     （所以 v50/v51 想补 comfy 红题时拿不到词组组，只能跳过）。
#   现口径：同一套判据抽成 `TEXT_RULES`（题面含 key ⇒ 每一组至少命中一个词），`text_ok()` 改为读它；
#     判分结果**与改前完全一致**（组语义一一对应），但可被现读、可被生成器引用（不编内容）。
TEXT_RULES = {
    "必填": [["seed"], ["steps"]],
    "目录": [["models/"], ["checkpoints", "vae"]],
    "判据": [["validate"], ["未知"], ["必填"]],
}
TEXT_RULES_DEFAULT = [["validate"]]


def kind_of(q):
    if "JSON" in q or "工作流" in q:
        if "文生视频" in q:
            return "txt2video"
        if "图生图" in q:
            return "img2img"
        return "txt2img"
    return "text"


def extract_graph(text):
    """取**含 class_type 最多的那段平衡 JSON**（散文里可能还有别的花括号）。"""
    best = None
    best_n = 0
    for m in re.finditer(r"\{", text):
        depth = 0
        for i in range(m.start(), len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[m.start():i + 1])
                    except Exception:
                        break
                    if isinstance(obj, dict):
                        n = sum(1 for v in obj.values() if isinstance(v, dict) and v.get("class_type"))
                        if n > best_n:
                            best, best_n = obj, n
                    break
    return best if best_n >= 3 else None


def validate(graph):
    payload = json.dumps({"op": "validate", "workflow": graph}, ensure_ascii=False)
    p = subprocess.run([sys.executable, "-X", "utf8", str(GATE), "cap", "comfy_native", payload, "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = p.stdout or ""
    try:
        j = json.loads(out[out.find("{"):])
        body = j.get("result") if isinstance(j.get("result"), dict) else {}
        return bool(body.get("ok")), body
    except Exception:
        return False, {}


def text_ok(q, ans):
    rules = None
    for key, groups in TEXT_RULES.items():
        if key in q:
            rules = groups
            break
    if rules is None:
        rules = TEXT_RULES_DEFAULT
    miss = [list(g) for g in rules if not any(w in ans for w in g)]
    return (not miss), miss


def main():
    ap = argparse.ArgumentParser(description="秋叶版能力验收")
    ap.add_argument("--answers", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = 0
    for i, r in enumerate(rows, 1):
        q = r.get("q") or ""
        ans = r.get("a") or ""
        k = kind_of(q)
        if k == "text":
            good, miss = text_ok(q, ans)
            print("  %-3d %s 文本题 | 缺 %s" % (i, "OK " if good else "RED", miss or "-"))
            ok += 1 if good else 0
            continue
        g = extract_graph(ans)
        if not g:
            print("  %-3d RED  抠不出 API 图（题=%s）" % (i, k))
            continue
        names = set()
        for node in g.values():
            if isinstance(node, dict) and node.get("class_type"):
                names.add(str(node["class_type"]))
        need = NEED.get(k, NEED["txt2img"])
        miss = [n for n in need if n not in names]
        if k == "txt2video" and not any(("AnimateDiff" in n or "SVD" in n or "Wan" in n) for n in names):
            miss.append("运动模块")
        vok, body = validate(g)
        good = vok and not miss
        print("  %-3d %s %s | 节点 %d | 缺 %s | validate %s" % (i, "OK " if good else "RED", k, len(names), miss or "-", vok))
        ok += 1 if good else 0
    print("== 秋叶版能力验收：%d/%d ==" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

