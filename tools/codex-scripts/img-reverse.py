# -*- coding: utf-8 -*-
"""img-reverse -- 洗图「反推环」v2：本机像素读数(vision analyze) -> 形式化反推；语义反推缺通道时如实标。"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable

def call_vision(img: Path):
    payload = json.dumps({"op": "see", "image": str(img)}, ensure_ascii=False)
    r = subprocess.run([PY, "-X", "utf8", "tools/codex-scripts/five-dim.py", "cap", "vision", payload, "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=300)
    return (r.stdout or "") + (r.stderr or "")

def formal_prompt(raw: str):
    if '"denied": true' in raw:
        i = raw.find("missing_scopes")
        return None, ["privacy_read"], raw
    nums = [float(x) for x in re.findall(r"-?\d+\.\d+", raw)]
    grid = None
    m = re.search(r'"grid"\s*:\s*(\d+)', raw)
    if m:
        grid = int(m.group(1))
    if not nums:
        return None, [], raw
    avg = sum(nums) / len(nums)
    lo, hi = min(nums), max(nums)
    parts = []
    parts.append("低照度" if avg < 60 else ("中调" if avg < 160 else "高调"))
    parts.append("强对比" if (hi - lo) > 120 else "弱对比")
    parts.append("%d宫格取样" % grid if grid else "未读到网格")
    left = sum(nums[:len(nums)//2]) / max(1, len(nums)//2)
    right = sum(nums[len(nums)//2:]) / max(1, len(nums) - len(nums)//2)
    parts.append("左重" if left > right * 1.08 else ("右重" if right > left * 1.08 else "左右均衡"))
    return "，".join(parts), [], raw

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    img = Path(a.image)
    doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "image": str(img), "ring": "reverse",
           "README": "本机 vision analyze 是**像素级读数**（亮度网格），不是图像理解模型：形式化可反推，语义需外部通道"}
    if not img.is_file():
        doc["ok"] = False; doc["reason"] = "图片不存在"
    else:
        raw = call_vision(img)
        draft, miss, _ = formal_prompt(raw)
        doc["ok"] = bool(draft)
        doc["formal_prompt"] = draft or "（未读到像素数值）"
        doc["semantic_prompt"] = ("未读到（缺图像理解通道：teamorouter 401 / 本地 8111 未监听；"
                                  "需 key 或起端点）")
        if miss:
            doc["missing_scopes"] = miss
            doc["how"] = "python -m gbt_allinone auth grant --scope privacy_read --ttl 600"
        doc["receipt_tail"] = raw[-200:]
    out = Path(a.out) if a.out else (ROOT / ".scratch" / ("reverse_" + img.stem + ".json"))
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("反推环 v2：形式化=**%s**" % doc.get("formal_prompt"))
    print("           语义=%s" % doc.get("semantic_prompt"))
    if doc.get("missing_scopes"):
        print("           缺钥匙: %s" % doc["missing_scopes"])
    print("           落盘: %s" % out.relative_to(ROOT))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
