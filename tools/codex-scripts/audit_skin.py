# -*- coding: utf-8 -*-
"""皮肤分流机检器（2026-09-23 起）—— 把「别跟旧皮肤混」从口头约定变成读数。

## 为什么要这一件

风哥令：「**你先看清楚皮肤别跟旧皮肤混到一起去免得有混了**」。
实扫之后发现仓里**不止两套**皮肤，至少有五套在同时存在着色：

| # | 皮肤 | 落在哪 | 主色（实扫） | 判 |
|---|---|---|---|---|
| 甲 | **新壳皮肤** | `holo_pet_w3/window.css` + `deck3d.css` 的 `:root` | 土豆金 `#F5B041` / 赛博青 `#00E5FF` / 深空紫 `#7C4DFF` | ✅ **准用（唯一）** |
| 乙 | **旧生产树皮肤** | `holo_pet/styles.css`（68 KB） | 见本器现算的「禁用集」 | 🔴 **退役** |
| 丙 | **交付页皮肤** | `V22 …可交互原型/无限画布.html` | `#2AD4F0` `#F5B544` `#3DDC97` … | ⚠️ 交付物专用，**不许进壳** |
| 丁 | 工作区散页皮肤 | `capabilities.html` / `brain.html` | `#E8B04A` `#D9964F` `#5D6A8A` … | ⚠️ 各是一套，不许进壳 |
| 戊 | 参考稿皮肤 | 风哥贴的那份 mock | Tailwind 蓝紫 `#3B82F6` `#8B5CF6` | 🔴 **明确不采纳**（AI 指纹） |

## 判据（**两条都不写死，全部现算**）

- **准用集** ← 从 `window.css` + `deck3d.css` 的 `:root` 里**现读**声明的色值；
- **禁用集** ← 从 `holo_pet/styles.css` 里**现读**出现频次最高的那批值 + 一份众数 AI 指纹清单。

⇒ 皮肤换了、token 改了，本器**自动跟着走**；写死一次就过期一次（本仓最贵的教训）。

## 用法

    py -3.14 tools/codex-scripts/audit_skin.py                 # 默认只看新壳
    py -3.14 tools/codex-scripts/audit_skin.py --add <文件…>    # 加看别的页
    py -3.14 tools/codex-scripts/audit_skin.py --json out.json

退出码：`0` 干净 · `1` 有混入（准用集之外的颜色）· `2` 用法错/找不到准用集。
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
SHELL = ROOT / "holo_pet_w3"

# 准用集的来源（**现读**，不写死色值）
#   · 壳品牌皮肤：window.css + deck3d.css
#   · 各窗**专业皮肤**：`skin-*.css`（约定：皮肤文件必须以 `skin-` 开头，
#     且文件头要写明它引用的是 `审美相关skill/design-systems/` 里的哪一套）
#     ⇒ 这条约定让"上专业皮肤"和"混进第二套皮"能被机器分开：
#       有名字、有出处、在 skin- 文件里的 = 专业皮肤；散落在版式文件里的 = 混入。
TOKEN_FILES = [SHELL / "window.css", SHELL / "deck3d.css"]
TOKEN_FILES += sorted(SHELL.glob("**/skin-*.css"))
# 禁用集的来源：旧生产树皮肤（现读它的高频色）
OLD_SKIN = ROOT / "holo_pet" / "styles.css"

# 众数 AI 指纹（Tailwind indigo/violet/blue/pink 家族）。这不是"皮肤"，
# 是**一眼看得出是 AI 做的**那批默认色；gbt-aesthetic §3.1 的 P0-1/P0-2 就是它们。
AI_FINGERPRINT = {
    "#3B82F6", "#60A5FA", "#2563EB", "#6366F1", "#4F46E5", "#4338CA", "#3730A3",
    "#8B5CF6", "#7C3AED", "#A855F7", "#9333EA", "#EC4899", "#DB2777", "#F472B6",
}

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# 🔴 首跑发现的**自家洞**：JS 里的颜色常写成数字字面量 `0x00e5ff`，
#    `#[…]` 那条正则**一个字都扫不到** ⇒ `brain.js` 里换掉品牌色本器会报"干净"（假绿）。
#    补上这一条，器才配说"零混入"。
NUM = re.compile(r"\b0x([0-9a-fA-F]{6})\b")
RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
EXTS = (".css", ".js", ".html", ".cjs")
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__"}


def _norm(h: str) -> str:
    """`#abc` → `#AABBCC`；带 8 位 alpha 的取前 6 位（色相相同即算同族）。"""
    h = h.upper().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h[:6]


def _root_block(text: str) -> tuple:
    """取**第一个** `:root{…}` 的内容与"其余部分"。与 test_brand_tokens.cjs 同一套判据。"""
    i = text.find(":root")
    if i < 0:
        return None, None
    o = text.find("{", i)
    c = text.find("}", o) if o >= 0 else -1
    if o < 0 or c < 0:
        return None, None
    return text[o + 1:c], text[:o] + text[c + 1:]


def allowed_set() -> tuple:
    """准用集：**现读** token 文件的 `:root`。返回 `(hex集, rgba集, 出处)`。"""
    hexes, rgbas, srcs = set(), set(), []
    for p in TOKEN_FILES:
        if not p.is_file():
            continue
        inner, _ = _root_block(p.read_text(encoding="utf-8", errors="replace"))
        if inner is None:
            continue
        srcs.append(str(p.relative_to(ROOT)))
        for m in HEX.finditer(inner):
            hexes.add(_norm(m.group(0)))
        for m in RGBA.finditer(inner):
            rgbas.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return hexes, rgbas, srcs


def banned_set() -> tuple:
    """禁用集：**现读**旧生产树皮肤的高频色（取前 12）+ AI 指纹。

    🔴 **2026-09-23 加"冻结兜底"**：原实现**只从 `holo_pet/styles.css` 现读** ——
    于是**审计器对那个文件产生了硬依赖**：文件一删（清理旧皮肤时正该删），
    "旧皮肤指纹"这项能力就静默消失，而**没有任何地方会报**。
    这是我自己造出来的依赖，属于"删除一个文件，默默废掉另一个功能"的典型。
    ⇒ 现在：**文件在就读它（保持跟踪）；文件不在就用冻结值（带出处）** —— 两条路都说得清。
    """
    old = Counter()
    src = ""
    if OLD_SKIN.is_file():
        for m in HEX.finditer(OLD_SKIN.read_text(encoding="utf-8", errors="replace")):
            old[_norm(m.group(0))] += 1
        src = str(OLD_SKIN.relative_to(ROOT))
    if old:
        return {h for h, _ in old.most_common(12)}, AI_FINGERPRINT, src
    return set(FROZEN_OLD_SKIN), AI_FINGERPRINT, "（冻结值：holo_pet/styles.css 已清理，2026-09-23 取样）"


# 退役皮肤的**冻结指纹**：2026-09-23 从 `holo_pet/styles.css` 现读取得的高频 12 色。
# 为什么冻结而不是丢掉：删掉那个文件**不该**让"旧皮肤指纹"这项检查静默失效 ——
# 旧皮肤随时可能从回收站还原、或被复制到别处；指纹留着，它一露头就还能被抓到。
FROZEN_OLD_SKIN = ("#00E5FF", "#050711", "#06151A", "#111621", "#7C4DFF", "#8FD0DD",
                   "#9FB4D8", "#CFE2EE", "#E06C75", "#F5B041", "#FF6B72", "#FFB0B4")


def _strip_comments(text: str) -> str:
    """去掉注释再扫。**这一条是必须的，不是顺手**：

    首跑时剩下的 7 处"混入"**全是我自己写在注释里的旧色号** ——
    因为本仓的纪律要求「改一处就记下它原来是什么、为什么改」（见 connect.html 的改版说明）。
    若把注释算违规，就变成**"记录历史 = 永远报红"** ⇒ 人会选择**不记录**，
    而那比色号混入更贵。⇒ 器必须只看**会被渲染/执行的部分**。

    安全做法：`/* … */` 与 `<!-- … -->` 一律剥；`//` 只在**前面不是冒号**时剥（否则会把 `http://` 腰斩）。
    🔴 首版只剥了 CSS 注释，漏了 **HTML 注释** —— 于是在 HTML 里写"这里原来是什么色"照样报红，
       又回到"记录历史 = 永远报红"那个坑。三种注释都得剥。
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"(?<!:)//[^\n]*", " ", text)
    return text


def scan(files: list, allow_hex: set) -> list:
    """逐文件找「准用集之外」的颜色。**:root 块里不算违规**（那是定义处）。

    两条**不算违规**的例外（都是首跑看出来的真情况，写下来免得下一个人又纠结）：
      · `#RRGGBB00` 八位 alpha=0 ⇒ 它表示**透明**，不是颜色（`main.cjs` 里窗口底就是它）；
      · `holo_pet_w3/tests/` 下的 `#000000` ⇒ 那是**负对照夹具**的合成文本，不是被渲染的皮肤。
    """
    out = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        _inner, outer = _root_block(text)
        if outer is None:
            outer = _strip_comments(text)
        else:
            outer = _strip_comments(outer)
        hits = []
        for m in HEX.finditer(outer):
            raw = m.group(0)
            if len(raw) == 9 and raw.endswith("00"):     # alpha=0 ⇒ 透明，不是颜色
                continue
            n = _norm(raw)
            if n not in allow_hex:
                line = outer[:m.start()].count("\n") + 1
                hits.append({"v": n, "line": line})
        for m in NUM.finditer(outer):
            n = "#" + m.group(1).upper()
            if n not in allow_hex:
                line = outer[:m.start()].count("\n") + 1
                hits.append({"v": n + "（JS 数字字面量）", "line": line})
        # rgba 不做"是哪个 token"的判定（合法用途太杂），只统计个数供人看
        n_rgba = len(RGBA.findall(outer))
        if hits:
            out.append({"file": str(f.relative_to(ROOT)), "hits": hits,
                        "raw_hex_in_root": len(HEX.findall(_inner or "")), "rgba_outside": n_rgba})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="皮肤分流机检（新壳只许用新壳皮肤）")
    ap.add_argument("--add", nargs="*", default=[], help="额外要看的文件/目录")
    ap.add_argument("--json", default="")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--include-tests", action="store_true",
                    help="连 tests/ 一起扫（默认跳过：那是故意合成的违规夹具）")
    a = ap.parse_args()

    allow_hex, allow_rgba, srcs = allowed_set()
    if not allow_hex:
        print("🔴 读不到准用集 —— token 文件不在或没有 :root 块，判不了（不猜）")
        return 2
    ban_old, ban_ai, old_src = banned_set()

    files = []
    for dp, dn, fn in __import__("os").walk(SHELL):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        if not a.include_tests and Path(dp).name == "tests":
            continue     # 夹具是**故意合成的**违规样本，不是被渲染的皮肤；默认不扫，但报出来
        files += [Path(dp) / n for n in fn if n.endswith(EXTS)]
    for extra in a.add:
        p = Path(extra)
        if p.is_dir():
            for dp, dn, fn in __import__("os").walk(p):
                dn[:] = [d for d in dn if d not in SKIP_DIRS]
                files += [Path(dp) / n for n in fn if n.endswith(EXTS)]
        elif p.is_file():
            files.append(p)
    files = sorted(set(files))

    print("=" * 78)
    print("皮肤分流机检 —— 「新壳只许用新壳皮肤」")
    print("=" * 78)
    print("  准用集（现读）%d 色 ← %s" % (len(allow_hex), " + ".join(srcs)))
    print("      %s" % " ".join(sorted(allow_hex)))
    print("  禁用·旧皮肤 %d 色 ← %s" % (len(ban_old), old_src or "（旧皮肤文件不在）"))
    print("      %s" % (" ".join(sorted(ban_old)) or "—"))
    print("  禁用·AI 指纹 %d 色（gbt-aesthetic §3.1 P0-1/P0-2）" % len(ban_ai))
    print("-" * 78)
    print("  扫了 %d 个文件：%s" % (len(files), ", ".join(str(f.relative_to(ROOT)) for f in files[:6])
                              + (" …" if len(files) > 6 else "")))

    bad = scan(files, allow_hex)
    total = sum(len(b["hits"]) for b in bad)
    n_old = sum(1 for b in bad for h in b["hits"] if h["v"] in ban_old)
    n_ai = sum(1 for b in bad for h in b["hits"] if h["v"] in ban_ai)

    if not bad:
        print("  ✅ **零混入**：新壳里出现的每一个 hex 都在准用集内")
    else:
        print("  🔴 **%d 处准用集之外的颜色**，落在 %d 个文件：" % (total, len(bad)))
        for b in bad:
            tag = ""
            if any(h["v"] in ban_ai for h in b["hits"]):
                tag = "  ← **含 AI 指纹色**"
            elif any(h["v"] in ban_old for h in b["hits"]):
                tag = "  ← **含旧皮肤色**"
            print("      %s%s" % (b["file"], tag))
            for h in b["hits"][:8]:
                mark = "AI指纹" if h["v"] in ban_ai else ("旧皮肤" if h["v"] in ban_old else "外来")
                print("          L%-5d %s  [%s]" % (h["line"], h["v"], mark))
    print("-" * 78)
    print("  旧皮肤色命中 %d 处 · AI 指纹色命中 %d 处" % (n_old, n_ai))
    print("  退出码：0=干净可交 · 1=有混入 · 2=判不了")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"allowed": sorted(allow_hex), "allowed_src": srcs,
             "banned_old": sorted(ban_old), "banned_ai": sorted(ban_ai),
             "files": len(files), "mixed": bad,
             "n_old": n_old, "n_ai": n_ai, "skipped_tests": not a.include_tests},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("  产物: %s" % a.json)
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
