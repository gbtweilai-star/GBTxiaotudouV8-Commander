"""量化档位 × 本机资源 —— **决策表**（只读 · 不下载 · 现读两边再对账）。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它（主人问「大模型部署好了吗」时最该给的东西）
主人要拍的三件里有两件是**资源决策**：**下哪个权重** + **内存加多少**。
拍这两件需要一张表：**每个量化档多大多小** 对 **本机有多少显存+空闲内存**。
两边都必须**现读**：
- 权重侧：HuggingFace `tree/main` API 的**真实字节数**（不是我记的、不是宣称的）；
- 本机侧：`comfy-surface.py` 的现读（显存 / 空闲内存 / 估峰值）。

## 口径（宁窄不宽）
- **"装得下" ≠ "跑得动"**：表里只判「文件大小 vs 可用资源」这个**必要不充分**条件；
  真跑还要 KV cache / 上下文 / 框架开销 ⇒ 表里**写明这句**，不许把"能装"读成"能跑"。
- **本机资源读不到 ⇒ 一律不许判"能装"**（fail-closed，写「未知」）；
- **权重表读不到 ⇒ 拒绝**（不许拿旧数/记忆顶替）。

用法：
  python tools/codex-scripts/llm-fit-table.py show [--repo unsloth/Qwen3.8-27B-GGUF]
  python tools/codex-scripts/llm-fit-table.py selftest
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "unsloth/Qwen3.8-27B-GGUF"
GIB = 1024 ** 3

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def fetch_sizes(repo: str, timeout: float = 25.0) -> dict:
    """现读 HF 的 `tree/main`：返回 {文件名: 字节数}（只取 *.gguf）。取不到 ⇒ 如实抛。"""
    url = "https://huggingface.co/api/models/%s/tree/main" % repo
    with urllib.request.urlopen(url, timeout=timeout) as r:     # noqa: S310（公开只读 API）
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    out = {}
    for item in data:
        if item.get("type") == "file" and str(item.get("path", "")).endswith(".gguf"):
            sz = item.get("size")
            if isinstance(sz, int) and sz > 0:
                out[item["path"]] = sz
    return out


def local_resources() -> dict:
    """现读本机资源：调 `comfy-surface.py`，只取内存/显存两块。取不到 ⇒ 写「未读到」。"""
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "codex-scripts" / "comfy-surface.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT))
    try:
        d = json.loads(p.stdout)
    except Exception as exc:
        return {"**未读到**": "%s: %s" % (type(exc).__name__, str(exc)[:50])}
    mem = d.get("内存") if isinstance(d.get("内存"), dict) else {}
    vram = d.get("显存") if isinstance(d.get("显存"), list) else []
    free_mb = mem.get("空闲MB") if isinstance(mem, dict) else None
    total_mb = mem.get("总MB") if isinstance(mem, dict) else None
    vram_gb = None
    for x in vram:
        try:
            vram_gb = float(str(x).split()[0])
            break
        except Exception:
            continue
    return {"空闲内存GB": (free_mb / 1024.0) if isinstance(free_mb, (int, float)) else None,
            "总内存GB": (total_mb / 1024.0) if isinstance(total_mb, (int, float)) else None,
            "显存GB": vram_gb, "原文": {"内存": mem, "显存": vram}}


def fit_rows(sizes: dict, vram_gb, free_ram_gb) -> dict:
    """**纯函数**（好上负控）：逐档判「装不装得下」。

    本机资源读不到（任一为 None）⇒ 一律判「未知」，**不许说能装**。
    """
    if not sizes:
        return {"ok": False, "拒绝": "**权重表是空的 ⇒ 拒绝**（不许拿旧数/记忆顶替）"}
    unknown = vram_gb is None or free_ram_gb is None
    rows = []
    for name, size in sorted(sizes.items(), key=lambda kv: kv[1]):
        gib = size / GIB
        row = {"档": name, "文件GiB": round(gib, 2)}
        if unknown:
            row["判定"] = "**未知**（本机资源未读到 ⇒ 不许说能装）"
        else:
            both = vram_gb + free_ram_gb
            row["装得进显存"] = gib <= vram_gb
            row["装得进显存+空闲内存"] = gib <= both
            row["差多少GiB"] = round(gib - both, 2)
            row["判定"] = ("可装（**不等于跑得动**）" if gib <= both else
                         "🔴 **装不下**（还差 %.2f GiB）" % (gib - both))
        rows.append(row)
    smallest = rows[0] if rows else None
    return {"ok": True, "总档数": len(rows), "逐档": rows, "最小档": smallest,
            "本机": {"显存GB": vram_gb, "空闲内存GB": free_ram_gb if free_ram_gb is None
                   else round(free_ram_gb, 2)},
            "口径": "**装得下 ≠ 跑得动**：这里只判「文件大小 vs 可用资源」这个必要不充分条件；"
            "真跑还要 KV cache/上下文/框架开销。"}


def cmd_show(repo: str) -> int:
    try:
        sizes = fetch_sizes(repo)
    except Exception as exc:
        print(json.dumps({"判决": "🔴 **未读到权重表**（%s: %s）⇒ 拒（不拿记忆顶替）"
                          % (type(exc).__name__, str(exc)[:60])}, ensure_ascii=False, indent=1))
        return 2
    loc = local_resources()
    fit = fit_rows(sizes, loc.get("显存GB"), loc.get("空闲内存GB"))
    if not fit.get("ok"):
        print(json.dumps(fit, ensure_ascii=False, indent=1))
        return 2
    print("权重仓库：%s ｜ 档位 %d 个（现读 HF tree/main 的真实字节数）" % (repo, fit["总档数"]))
    print("本机现读：显存 %s GB ｜ 空闲内存 %s GB%s"
          % (fit["本机"]["显存GB"], fit["本机"]["空闲内存GB"],
             "" if loc.get("显存GB") is not None else "  ⚠️ %s" % loc.get("**未读到**", "资源未读到")))
    print("-" * 76)
    for r in fit["逐档"]:
        extra = ("" if "装得进显存" not in r else
                 " ｜ 显存%s ｜ 合计%s" % ("✅" if r["装得进显存"] else "❌",
                                     "✅" if r["装得进显存+空闲内存"] else "❌"))
        print("  %-34s %6.2f GiB%s ｜ %s" % (r["档"], r["文件GiB"], extra, r["判定"]))
    print("-" * 76)
    print("最小档：%s（%.2f GiB）" % (fit["最小档"]["档"], fit["最小档"]["文件GiB"]))
    print("口径：%s" % fit["口径"])
    return 0


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    r = fit_rows({"a.gguf": int(2.0 * GIB), "b.gguf": int(30.0 * GIB)}, 3.98, 1.0)
    ck("**正控：2 GiB 档在 4.98 GiB 合计里 ⇒ 判可装**",
       r["逐档"][0]["判定"].startswith("可装"), r["逐档"][0]["判定"])
    ck("**正控：30 GiB 档装不下 ⇒ 点名差多少**",
       "装不下" in r["逐档"][1]["判定"] and r["逐档"][1]["差多少GiB"] > 20,
       r["逐档"][1]["判定"])
    ck("**负控：本机资源未读到 ⇒ 一律判「未知」，不许说能装**",
       fit_rows({"a.gguf": 1}, None, 1.0)["逐档"][0]["判定"].startswith("**未知**"),
       fit_rows({"a.gguf": 1}, None, 1.0)["逐档"][0]["判定"])
    ck("**边界：权重表为空 ⇒ 拒绝**（不拿旧数顶替）",
       fit_rows({}, 3.98, 1.0)["ok"] is False, "")
    ck("**边界：按大小升序**（最小档排第一）",
       fit_rows({"big": 9 * GIB, "small": GIB}, 3.98, 1.0)["最小档"]["档"] == "small", "")
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["show", "selftest"])
    ap.add_argument("--repo", default=DEFAULT_REPO)
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    return cmd_show(a.repo)


if __name__ == "__main__":
    raise SystemExit(main())
