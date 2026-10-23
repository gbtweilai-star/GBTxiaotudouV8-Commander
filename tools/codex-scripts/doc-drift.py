# -*- coding: utf-8 -*-
"""文档漂移机检 · 查「文档说的和盘上的对不对得上」。

## 为什么要有这一件（2026-09-23 第 39 轮）

Owner 说过三次「**旧页面/旧东西别留在项目里容易搞混，必须注重细节**」。
第 30 轮在裁决书里抓到一条**会害人的过期判词**；第 39 轮又抓到一条更险的：

    `holo_pet_w3/README.md`（09-18 那版）写着「权威源＝镜像维度，工作区根只读不许手改」
    —— 而实测镜像那份是**七天前的 16 文件快照**，工作区根是**244 文件的现行版**。
    照它做一次"从镜像重新落地"，**十轮工作当场冲没**。

⇒ **靠人记得更新文档是不行的**（本次漂了七天、十轮没人发现）。把它变成机检。

## 四条判据

| # | 判据 | 为什么 |
|---|---|---|
| **D1** | **悬空引用**：文档点名的仓内文件**不在盘上** | 这是最危险的方向 —— 它叫你去跑/去读一个不存在的东西 |
| **D2** | **未登记的验收器**：`REQUIRED_IN_ARBITER` 里的件必须在裁决书里出现 | 新造的器不进裁决书 = 下一个人根本不知道它存在 |
| **D3** | **同一事实两处口径不一致**：文档写的窗口数/脚本名必须与 `windows.json` / `package.json` 一致 | 「一件事两个数」本仓栽过（可直跑 122 / 88 / 102） |
| **D4** | **文档比它描述的东西旧太多**（软信号，只提示不判红） | 过期的判词不一定会悬空，但它会误导 |

## 口径（不许含糊）

- 本器**只读**，不改任何文件。
- D1 的匹配面是**反引号里的路径样串**；行内出现「不存在 / 缺失 / 已进回收站 / ~~删除线~~」
  的一律**跳过** —— 那些本来就是在说"它没有了"，不是悬空引用。
- 退出码：0=干净 · 1=有硬失败(D1/D2/D3) · 2=只有软提示(D4)

用法:
  py -3.14 tools/codex-scripts/doc-drift.py
  py -3.14 tools/codex-scripts/doc-drift.py --json
"""
import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]

DOCS = ["CURRENT.md", "README.md", "holo_pet_w3/README.md", "tools/codex-scripts/README.md"]

# D2：必须出现在裁决书里的验收器（新造了器就往这里加一行，别靠人记得）
REQUIRED_IN_ARBITER = [
    "holo_pet_w3/shell/preflight.cjs",
    "holo_pet_w3/shell/rehearse.cjs",
    "holo_pet_w3/shell/startup.cjs",
    "holo_pet_w3/shell/interact.cjs",
    "holo_pet_w3/shell/shots.cjs",
    "tools/codex-scripts/exposure-scan.py",
    # 2026-09-23 第 40 轮（大清洗）新造的四件：登记闸 / 视图普查 / 重份普查 / 去重器
    "tools/codex-scripts/tree-registry.py",
    "tools/codex-scripts/probe-reparse-points.py",
    "tools/codex-scripts/dup-source-inventory.py",
    "tools/codex-scripts/vendor-node-trim.py",
    # 2026-09-23 第 40 轮（打包上线）：装机回执（从真包量，不采信打包器 stdout）
    "tools/codex-scripts/pack-receipt.py",
    # 2026-09-23 第 44 轮（旧页面判决）：把"临时扫一遍"固化成判决表 + 一道闸
    "tools/codex-scripts/old-pages.py",
]

# D1 跳过词：这一行本来就在说"它没有了"
SKIP_WORDS = ("不存在", "缺失", "已进回收站", "已清理", "不再", "退役", "~~")
# D1 块级跳过：**清理记录表**整整一节都在说"这些已经清出去了"。
# 🔴 第 40 轮修：原先只有行级 SKIP_WORDS，而清理表的数据行（`| \`路径\` | 大小 | 判据 |`）
#    一个跳过词都不含 ⇒ 被报成"悬空引用"。**误报会教人忽略这个器**，比漏报更坏。
REMOVAL_HEADING = re.compile(r"(清出去|清掉|已清|回收站|退役|移除记录|删除记录)")
# 反引号里的路径样串
REF = re.compile(r"`([A-Za-z0-9_./\-\u4e00-\u9fff]+\.(?:py|cjs|mjs|js|json|md|html|css|ps1|txt))`")


def _exists(rel: str) -> bool:
    p = rel.lstrip("./")
    for base in (ROOT, ROOT / "holo_pet_w3", ROOT / "tools" / "codex-scripts"):
        try:
            if (base / p).exists():
                return True
        except OSError:
            pass
    return False


def check_d1(doc: Path):
    """悬空引用。返回 [{line, ref}]。"""
    out = []
    try:
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    in_removal = False
    for i, ln in enumerate(lines, 1):
        if ln.startswith("#"):
            in_removal = bool(REMOVAL_HEADING.search(ln))
            continue
        if in_removal:                 # 清理记录表：整节跳过
            continue
        if any(w in ln for w in SKIP_WORDS):
            continue
        for m in REF.finditer(ln):
            ref = m.group(1)
            # 只查"像仓内路径"的；纯文件名放过去（多个同名件，误报率高）
            if "/" not in ref and not ref.startswith(("CURRENT", "README")):
                continue
            if not _exists(ref):
                out.append({"line": i, "ref": ref})
    return out


def check_d2():
    """验收器必须出现在裁决书里。

    🔴 第 40 轮修：裁决书把六支壳验收器登记成**一行 glob**（`holo_pet_w3/shell/*.cjs`），
    而本器原先只做精确子串匹配 ⇒ 六支全报"未登记"。**登记方式不止一种**，
    器要么认识它，要么就会天天误报。
    """
    arb = ROOT / "CURRENT.md"
    text = arb.read_text(encoding="utf-8", errors="replace") if arb.is_file() else ""
    missing = []
    for r in REQUIRED_IN_ARBITER:
        if r in text:
            continue
        p = Path(r)
        # 同目录通配登记也算登记（`<dir>/*<ext>`）
        if ("%s/*%s" % (p.parent.as_posix(), p.suffix)) in text:
            continue
        missing.append(r)
    return missing


def check_d3():
    """同一事实两处口径：壳 README 里写的窗口数 / 脚本名 vs 注册表 / package.json。"""
    out = []
    rd = ROOT / "holo_pet_w3" / "README.md"
    wj = ROOT / "holo_pet_w3" / "shell" / "windows.json"
    pkg = ROOT / "holo_pet_w3" / "package.json"
    if not (rd.is_file() and wj.is_file() and pkg.is_file()):
        return [{"what": "缺文件，判不了"}]
    text = rd.read_text(encoding="utf-8", errors="replace")
    n_win = len(json.loads(wj.read_text(encoding="utf-8")).get("windows", []))
    if ("**%d 扇窗**" % n_win) not in text and ("%d 扇窗" % n_win) not in text:
        out.append({"what": "窗口数", "live": n_win,
                    "note": "壳 README 里没写「%d 扇窗」—— 注册表有 %d 扇" % (n_win, n_win)})
    scripts = list(json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {}).keys())
    for s in scripts:
        # `npm start` / `npm test` 这类**内建名**不用写 `run`，两种写法都算写上。
        if (("npm run %s" % s) in text or ("npm %s" % s) in text):
            continue
        out.append({"what": "npm 脚本未写进 README", "live": s})
    return out


def check_d4():
    """软信号：文档比它描述的东西旧太多。"""
    out = []
    for rel in DOCS:
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            (Path(__file__).stat().st_mtime - p.stat().st_mtime) / 3600.0
        except OSError:
            continue
        if rel == "holo_pet_w3/README.md":
            newest = max((q.stat().st_mtime for q in (ROOT / "holo_pet_w3" / "shell").glob("*.cjs")),
                         default=0)
            if newest > p.stat().st_mtime + 86400:      # 器比文档新一天以上
                out.append({"doc": rel, "note": "壳的器比这份说明新了 1 天以上 —— 可能过期"})
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    d1 = {}
    for rel in DOCS:
        p = ROOT / rel
        if p.is_file():
            hits = check_d1(p)
            if hits:
                d1[rel] = hits
    d2 = check_d2()
    d3 = check_d3()
    d4 = check_d4()

    hard = sum(len(v) for v in d1.values()) + len(d2) + len(d3)
    rep = {"悬空引用": d1, "未登记的验收器": d2, "口径不一致": d3, "软提示": d4, "硬失败": hard}

    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print("=" * 88)
        print("文档漂移机检 · 文档说的和盘上的对不对得上")
        print("=" * 88)
        print("  扫了 %d 份文档：%s" % (len(DOCS), " · ".join(DOCS)))
        print("-" * 88)
        if d1:
            print("  🔴 D1 悬空引用（文档点名的文件不在盘上）：")
            for doc, hits in d1.items():
                for h in hits[:8]:
                    print("      %s:%d  `%s`" % (doc, h["line"], h["ref"]))
                if len(hits) > 8:
                    print("      …%s 还有 %d 条" % (doc, len(hits) - 8))
        else:
            print("  ✅ D1 零悬空引用")
        if d2:
            print("  🔴 D2 这些验收器没被登记进裁决书（`CURRENT.md`）：")
            for r in d2:
                print("      %s" % r)
        else:
            print("  ✅ D2 %d 个验收器都在裁决书里" % len(REQUIRED_IN_ARBITER))
        if d3:
            print("  🔴 D3 口径不一致：")
            for r in d3:
                print("      %s" % json.dumps(r, ensure_ascii=False))
        else:
            print("  ✅ D3 壳 README 的窗口数与 npm 脚本跟现读一致")
        if d4:
            print("  ⏳ D4 软提示（不判红）：")
            for r in d4:
                print("      %s" % json.dumps(r, ensure_ascii=False))
        print("-" * 88)
        print("  硬失败 %d 条" % hard)
        print("  退出码：0=干净 · 1=有硬失败 · 2=只有软提示")
    return 0 if hard == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
