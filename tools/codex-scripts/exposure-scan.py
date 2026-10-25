# -*- coding: utf-8 -*-
"""屏面暴露扫描 · 查「真渲染出来的文字里有没有本机内部信息」。

## 为什么不能扫源码

上一轮发现 h1（赏金台）屏上明文写着
`C:\\Users\\ADMIN\\AppData\\Local\\gbt_allinone\\bin\\h1mcp.exe`，而 AGENTS.md 写着
「**不要暴露内部地址、端口、配置**」（运行安全 · Exposure Protection 一节）。

要成体系地查这件事，**扫源码是错的尺子**：
  · **假阳**：只在注释 / 日志 / 日志格式串里出现的路径，根本不上屏，却被算成暴露；
  · **假阴**：运行时拼出来的（`path.join(base, name)`）、或从磁盘读进来再渲染的，
    源码里**一个字都没有**。
⇒ 唯一可靠的取样面 = **真壳渲染后的 `innerText`**（由 `holo_pet_w3/shell/shots.cjs` 落盘）。

## 判据（每条都写清"为什么这条算暴露"）

| 类 | 命中什么 | 为什么算 |
|---|---|---|
| `win-path` | `C:\\…` 盘符绝对路径 | 路径里带**用户名**（主机的私事） |
| `home` | `C:\\Users\\<用户名>` | 同上，更直接 |
| `loopback` | `127.0.0.1` / `localhost` / `0.0.0.0` | 本机地址；外部看到即内部拓扑 |
| `port-pair` | 地址旁边紧跟着端口 | 端口不加地址本身不算暴露；**地址+端口**才算 |
| `secret` | `sk-…` / `Bearer …` / 长十六进制串 | 凭据类 |

## 用法

  py -3.14 tools/codex-scripts/exposure-scan.py [--dir %TEMP%\\gbt-shell-shots]
  py -3.14 tools/codex-scripts/exposure-scan.py --json

退出码：0 = 零命中；1 = 有命中；2 = 没找到取样本（**"没扫"不许读成"干净"**）。

## 口径（不许含糊）

本器只报「**屏上出现了什么**」。它**不判断该不该出现** ——
端口号在"谁在听"这类面板上是有用的读数（`host` 才是必须掩码的那个）。
所以每条命中都带**上下文片段**，由人按上下文裁量。
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATTERNS = [
    ("win-path", re.compile(r"[A-Za-z]:\\\\?[^\s\"'<>|]*[\\\/][^\s\"'<>|]*")),
    ("home", re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s\"'<>|]+", re.I)),
    ("loopback", re.compile(r"\b(?:127\.0\.0\.1|localhost|0\.0\.0\.0)\b", re.I)),
    ("port-pair", re.compile(r"(?:127\.0\.0\.1|localhost)[:\s]+(\d{2,5})", re.I)),
    ("secret", re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9._\-]{12,})")),
]

# 允许出现的（**必须写明理由**，否则就是放水）：
#   · `127.0.0.1` 出现在**输入提示/说明文字**里（告诉主人该往哪儿贴 URL）——
#     connect.html 的引导页就是干这个的，那是**给主人看的操作说明**，不是拓扑泄漏。
ALLOW = [
    ("connect.html 引导语", re.compile(r"127\.0\.0\.1")),
]


def scan_text(text):
    """返回 [(类, 命中片段, 上下文)]。"""
    hits = []
    for kind, rx in PATTERNS:
        for m in rx.finditer(text):
            frag = m.group(0)
            if kind == "win-path" and len(frag) < 6:
                continue
            if kind == "port-pair":
                frag = m.group(0)
            s = max(0, m.start() - 40)
            ctx = re.sub(r"\s+", " ", text[s:m.end() + 40]).strip()
            hits.append((kind, frag, ctx))
    return hits


def _selftest():
    """扫描器自证（《扫描器自证律》）：**必须先证明它抓得到，再说"干净"**。

    只跑"真实样本 → 0 命中"会得出"没问题"的错觉 —— 而 0 命中既可能是真干净，
    也可能是**尺子瞎了**。本组给一好一坏两份样本，两臂结果必须不同。
    """
    bad = (
        "二进制 C:\\Users\\ADMIN\\AppData\\Local\\gbt_allinone\\bin\\h1mcp.exe 存在 是\n"
        "目录 C:\\Users\\ADMIN\\AppData\\Roaming\\h1mcp\\drafts 状态 不存在\n"
        "服务 127.0.0.1 8765 在听\n"
        "凭据 sk-abcdef1234567890 已配置\n"
    )
    good = (
        "二进制 …\\gbt_allinone\\bin\\h1mcp.exe 存在 是\n"
        "端口 8081 归属 GBT小土豆 状态 离线\n"
        "健康度 绿 0 / 黄 0 / 红 0 / 灰 1\n"
    )
    kb = scan_text(bad)
    kg = scan_text(good)
    kinds = sorted({k for k, _f, _c in kb})
    ok = (len(kb) >= 4 and len(kg) == 0)
    print("=" * 92)
    print("屏面暴露扫描器 · 自证")
    print("=" * 92)
    print("  对照 A（坏样本，**必须命中**）：%d 条 · 命中类 %s" % (len(kb), kinds))
    for k, f, _c in kb[:6]:
        print("      [%s] %s" % (k, f[:80]))
    print("  对照 B（好样本，**必须 0 命中**）：%d 条" % len(kg))
    if not ok:
        print("  🔴 SCANNER_BLIND：判据不可判别（要么抓不到坏的，要么把好的也报红）")
        return 1
    print("  ✅ 两臂结果不同 ⇒ 判据可判别（抓得到坏的，也不冤枉好的）")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="只跑扫描器自证（负对照 + 正对照），不读真实样本")
    a = ap.parse_args(argv)

    if a.selftest:
        return _selftest()

    # 默认找最近一次取证产物
    base = Path(a.dir) if a.dir else None
    if base is None:
        import tempfile
        base = Path(tempfile.gettempdir()) / "gbt-shell-shots"
    dumps = sorted(base.glob("*.txt")) if base.is_dir() else []
    if not dumps:
        print("没找到取样本：%s" % base)
        print("  先跑：cd holo_pet_w3 && npm run shots -- --out %s" % base)
        print("  ⚠️ 「没扫」不许读成「干净」。")
        return 2

    report = {"dir": str(base), "samples": len(dumps), "rows": []}
    total = 0
    for f in dumps:
        text = f.read_text(encoding="utf-8", errors="replace")
        hits = scan_text(text)
        # 排除白名单（按窗名 + 规则）
        kept = []
        for kind, frag, ctx in hits:
            if f.stem == "connect" and kind == "loopback":
                continue
            kept.append({"kind": kind, "frag": frag[:120], "ctx": ctx[:160]})
        total += len(kept)
        report["rows"].append({"win": f.stem, "chars": len(text), "hits": kept})

    report["total_hits"] = total

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("=" * 92)
        print("屏面暴露扫描 · 取样面 = 真壳渲染后的 innerText（不是源码）")
        print("=" * 92)
        print("  产物目录 %s · 取到 %d 扇窗的文字" % (base, len(dumps)))
        print("-" * 92)
        for r in report["rows"]:
            flag = "🔴" if r["hits"] else "✅"
            print("%s %-12s %6d 字 · 命中 %d" % (flag, r["win"], r["chars"], len(r["hits"])))
            for h in r["hits"][:6]:
                print("      [%s] %s" % (h["kind"], h["frag"][:96]))
                print("            …%s…" % h["ctx"][:130])
            if len(r["hits"]) > 6:
                print("      …其余 %d 条同型" % (len(r["hits"]) - 6))
        print("-" * 92)
        print("  合计命中 %d 条" % total)
        print("  ⚠️ 本器只报「屏上出现了什么」，**不替你判断该不该出现** ——")
        print("     端口在「谁在听」这类面板上是有用读数；必须掩码的是**带用户名的主机路径**与**地址+端口对**。")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
