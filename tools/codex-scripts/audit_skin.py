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
# 首跑发现的**自家洞**：JS 里的颜色常写成数字字面量 `0x00e5ff`，
#    `#[…]` 那条正则**一个字都扫不到** ⇒ `brain.js` 里换掉品牌色本器会报"干净"（假绿）。
#    补上这一条，器才配说"零混入"。
NUM = re.compile(r"\b0x([0-9a-fA-F]{6})\b")
RGBA = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)")
EXTS = (".css", ".js", ".html", ".cjs")
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__"}


def _norm(h: str) -> str:
    """`#abc` → `#AABBCC`；`#abc_`（4 位）→ 展开后取 RGB；带 8 位 alpha 的取前 6 位。

    🔴 2026-10-27 修：原来只处理 `len==3`。`#000a` 这种 **4 位形态**（= `#RGBA`，
    黑 + 透明度 0xAA）会原样返回 `#000A`（5 字符），下游 `h[5:7]` 切出空串 ⇒
    `int('', 16)` **直接崩**（实测：给 skin-semantic.css 的注释里写了 `#000a` 就崩了，
    读的是注释，说明 `:root` 里的注释当时也被当成了调色板 —— 两处一起修）。
    4 位与 3 位一样逐字翻倍即可：`0,0,0,A` → `00,00,00,AA` → 前 6 位正好是 RGB。
    """
    h = h.upper().lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    return "#" + h[:6]


def _tokens_from(inner: str) -> tuple:
    """纯函数：从 `:root` 内容里取 `(hex集, RGB三元组集)`。**先剥注释**。

    🔴 2026-10-27 修：原来直接对 `inner` 扫。而本仓纪律要求「改一处就记下原来是什么」，
    于是注释里必然出现旧色号 —— 注释被当成调色板 ⇒ **在注释里写一句 `#000a`
    就能把一个颜色「洗」进准用集**，而且崩在上面那个 4 位 bug 上（见 `_norm`）。
    `scan()` 早就对 outer 剥了注释，这里漏了，属于同一件事只做了一半。
    """
    inner = _strip_comments(inner or "")
    hexes, rgbas = set(), set()
    for m in HEX.finditer(inner):
        hexes.add(_norm(m.group(0)))
    for m in RGBA.finditer(inner):
        rgbas.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for h in hexes:
        rgbas.add((int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)))
    return hexes, rgbas


def _root_block(text: str) -> tuple:
    """取**所有** `:root{…}` 的内容（合并）与"其余部分"。

    🔴 2026-10-27 修：原来只取**第一个** `:root`。本仓已有先例 —— 当年
    `test_brand_tokens.cjs` 只认第一个 :root，把主题块（文件末尾第二个 :root）里的
    合法令牌定义全判成裸色值，实测假红 45 处。同一个坑在这里重犯了：
    `energy/index.html` 的第二个 `:root` 是**语义别名层**
    （`--okbg:#0f2a20` / `--badbg:#2a1414` …），被当成正文 ⇒ 判违规。
    判据必须认**所有** `:root`（先剥注释由调用方做）。
    """
    spans, inners = [], []
    for m in re.finditer(r":root\s*\{", text):
        o = text.find("{", m.start())
        c = text.find("}", o) if o >= 0 else -1
        if o < 0 or c < 0:
            continue
        inners.append(text[o + 1:c])
        spans.append((o, c + 1))
    if not inners:
        return None, None
    parts, prev = [], 0
    for (o, c) in spans:
        parts.append(text[prev:o])
        prev = c
    parts.append(text[prev:])
    return "\n".join(inners), "".join(parts)


def allowed_set() -> tuple:
    """准用集：**现读** token 文件的 `:root`。返回 `(hex集, RGB三元组集, 出处)`。

    🔴 2026-10-27 加 RGB 集：`rgba()` 的 RGB 分量要和 hex **同一套判**。
    原来的问题是"rgba 一律只数个数不判色" ⇒ 把 `rgba(232,236,248,.56)`
    （= 准用色 `#E8ECF8` + 透明度）也当成混入，制造了大批假工作量
    （实测：`voice-theater/index.html` 60 处 rgba 里绝大多数是准用色）。
    """
    hexes, rgbas, srcs = set(), set(), []
    for p in TOKEN_FILES:
        if not p.is_file():
            continue
        inner, _ = _root_block(p.read_text(encoding="utf-8", errors="replace"))
        if inner is None:
            continue
        srcs.append(str(p.relative_to(ROOT)))
        h, r = _tokens_from(inner)
        hexes |= h
        rgbas |= r
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


# ── 「这条色不是皮肤」的两个域（2026-10-27 加，都是实扫才发现的）────────────
# ① **生成产物**：`energy/energy-data.js` 11 处、`logbook/logbook-data.js` 3 处。
#    文件头自己写着「自动生成，别手改」/「生成产物…不许手改」，由 render 命令覆盖。
#    里面的色是**台账数据**（能量等级、记录本分类标记），不是界面配色；
#    手改了下一轮重建就冲掉 —— 属于「不适用、不算欠账」。
# ② **3D 渲染光照**：`voice-theater/dh3d.js` 4 处，全是
#    `new THREE.HemisphereLight(0x9fb6d6, 0x141821, .85)` / `DirectionalLight(0xffe3b8, 2.5)`
#    —— 这是**打光的天空色/地面色/主光/补光**，数字人脸要怎么亮是美术，不是 UI 皮肤。
#    把它们收进调色板会真的改掉 3D 观感，而和"皮肤混用"毫无关系。
#
# 🔴 两条都**必须报出来**（走 `nonskin`），不许静默放行 —— 判据的三种态是
#    PASS / FAIL / **不适用**，「不适用」要有理由，不是"没看见"。
GEN_HINT = re.compile(r"自动生成|生成产物|不许手改|别手改")
GEN_CMD = re.compile(r"render|重建")
THREE_CTX = re.compile(r"THREE\.\w*Light\(|MeshStandardMaterial|new THREE\.Color"
                       r"|HemisphereLight|DirectionalLight|PointLight\(|AmbientLight\(")


def _domain(is_gen: bool, ctx: str) -> str:
    """纯函数：把一处命中归到 `skin` / `gen`（生成产物）/ `3d`（3D 光照）。"""
    if is_gen:
        return "gen"
    return "3d" if THREE_CTX.search(ctx or "") else "skin"


def scan(files: list, allow_hex: set, allow_rgb: set = None) -> list:
    """逐文件找「准用集之外」的颜色。**:root 块里不算违规**（那是定义处）。

    两条**不算违规**的例外（都是首跑看出来的真情况，写下来免得下一个人又纠结）：
      · `#RRGGBB00` 八位 alpha=0 ⇒ 它表示**透明**，不是颜色（`main.cjs` 里窗口底就是它）；
      · `holo_pet_w3/tests/` 下的 `#000000` ⇒ 那是**负对照夹具**的合成文本，不是被渲染的皮肤。

    🔴 2026-10-27 改：`rgba()` **按 RGB 三分量判**（与 hex 同一套准用集），不再"只数个数"。
    实测：`voice-theater/index.html` 的 60 处 rgba 里绝大多数是 `rgba(232,236,248,.56)`
    这种"准用色 + 透明度"，一律算混入会造出假工作量。

    🔴 2026-10-27 再改：命中的色**再按用途域分一次**（`skin` / `gen` / `3d`，见上方常量）。
    只有 `skin` 进 `hits`（= 真违规）；另两类进 `nonskin`，**单列报出、不计入退出码**。
    """
    allow_rgb = allow_rgb or set()
    out = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        head = text[:600]
        is_gen = bool(GEN_HINT.search(head) and GEN_CMD.search(head))
        _inner, outer = _root_block(text)
        if outer is None:
            outer = _strip_comments(text)
        else:
            outer = _strip_comments(outer)
        outer_lines = outer.split("\n")

        raw_hits = []
        for m in HEX.finditer(outer):
            raw = m.group(0)
            if len(raw) == 9 and raw.endswith("00"):     # alpha=0 ⇒ 透明，不是颜色
                continue
            n = _norm(raw)
            # 🔴 2026-10-27 修**判据不对称**：hex 原来只按**字符串**比准用集，
            #    rgba 却按 **RGB 三元组**比。于是同一个颜色写成两种记法结论不同 ——
            #    实测 `skin-semantic.css` 里令牌写成 `rgba(0,0,0,.67)`，
            #    页面里写成 `#000a`（规范化后 `#000000`）就被判成外来，
            #    而它其实就是那个令牌。**判的单位是 RGB 三元组，不是记法。**
            rgb = (int(n[1:3], 16), int(n[3:5], 16), int(n[5:7], 16))
            if n not in allow_hex and rgb not in allow_rgb:
                raw_hits.append((n, m.start()))
        for m in NUM.finditer(outer):
            n = "#" + m.group(1).upper()
            rgb = (int(n[1:3], 16), int(n[3:5], 16), int(n[5:7], 16))
            if n not in allow_hex and rgb not in allow_rgb:
                raw_hits.append((n + "（JS 数字字面量）", m.start()))
        # rgba：按 RGB 三分量判（与 hex 同一套准用集）。不在集内的才记。
        n_rgba = 0
        for m in RGBA.finditer(outer):
            n_rgba += 1
            rgb = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if rgb in allow_rgb:
                continue                      # 准用色 + 透明度 ⇒ 不算混入
            raw_hits.append(("#%02X%02X%02X（rgba）" % rgb, m.start()))

        hits, nonskin = [], []
        for v, pos in raw_hits:
            ln = outer[:pos].count("\n")
            ctx = outer_lines[ln] if ln < len(outer_lines) else ""
            dom = _domain(is_gen, ctx)
            item = {"v": v, "line": ln + 1}
            if dom == "skin":
                hits.append(item)
            else:
                item["domain"] = "生成产物" if dom == "gen" else "3D 光照"
                nonskin.append(item)
        # 🔴 2026-10-27 修：原来条件是 `if hits:`（只认 hex）⇒ **只有 rgba、没有 hex 的文件
        #    整个不进列表**，连"这个文件有混入"都看不见。现在 hex 或 rgba 任一命中都收录。
        #    再改：`nonskin`（不适用域）也要收录，否则"不适用"就变成"没看见"。
        if hits or nonskin:
            # 🔴 2026-10-27 修：原来直接 `f.relative_to(ROOT)`，**仓外文件会抛 ValueError**
            #    ⇒ `--add <仓外路径>` 一直是崩的（是自检的第一条断言撞出来的）。
            #    仓内用相对路径（读数好认），仓外用绝对路径。
            try:
                rel = str(f.relative_to(ROOT))
            except ValueError:
                rel = str(f)
            out.append({"file": rel, "hits": hits, "nonskin": nonskin,
                        "raw_hex_in_root": len(HEX.findall(_inner or "")), "rgba_outside": n_rgba})
    return out


def count_hits(bad: list) -> tuple:
    """数总数 ⇒ `(总处数, hex 处数, rgba 处数)`。**纯函数**，为的是能被断言。

    🔴 抽出来的理由：原来 `total = sum(len(b["hits"]))` 写在 `main()` 里，
    只数 hex、rgba 从没进过总数 ⇒ 报 361 实际 542。写在 main 里就**没法测**，
    所以那个错活到了被人工发现才修。判据要点必须能被单独喂，这是本仓的老教训。
    """
    n_all = sum(len(b["hits"]) for b in bad)
    n_rgba = sum(1 for b in bad for h in b["hits"] if h["v"].endswith("（rgba）"))
    return n_all, n_all - n_rgba, n_rgba


def selftest() -> int:
    """本器自己的判据：2026-10-27 修的四处缺陷，每处一条正控 + 一条负对照。

    ## 为什么必须补这个

    那四处缺陷（漏掉只含 rgba 的文件 / 总数不数 rgba / rgba 一律算混入 /
    只认第一个 `:root`）**全部是靠人肉发现的**，器自己一声不吭。
    其中"只认第一个 :root"是本仓**第二次**犯（当年 `test_brand_tokens` 假红 45 处）。
    ⇒ 修完不补断言 = 下次改回去没人知道。

    计数用真计数（不写死数字），并设断言条数下限防"删断言".
    """
    import tempfile

    fails, total = [], [0]

    def ck(name, cond, detail=""):
        total[0] += 1
        if not cond:
            fails.append("%s :: %s" % (name, detail))

    # ① `_root_block`：所有 :root 都算定义处（不只第一个）
    src = ":root{--a:#111111}\n.x{color:#222222}\n:root{--b:#333333}\n.y{color:#444444}"
    inner, outer = _root_block(src)
    ck("① 第二个 :root 也算定义处", "#333333" in (inner or ""), str(inner))
    ck("① 正文仍留在 outer", "#222222" in (outer or "") and "#444444" in (outer or ""), str(outer))
    ck("① 第一个 :root 也还在", "#111111" in (inner or ""))
    # 负对照：只剥第一个 :root 的旧写法，第二个 :root 会被留在 outer 里（= 被判违规）
    i = src.find(":root")
    o, c = src.find("{", i), -1
    c = src.find("}", o)
    old_outer = src[:o] + src[c + 1:]
    ck("① 负对照·旧写法确实会漏第二个", "#333333" in old_outer, "旧写法居然也剥掉了")

    # ② `scan`：只含 rgba 命中、没有 hex 的文件也必须收录
    allow_hex = {"#0B1120"}
    allow_rgb = {(11, 17, 32)}
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "only-rgba.html"
        p.write_text("<style>.a{background:rgba(200,10,10,.5)}</style>", encoding="utf-8")
        got = scan([p], allow_hex, allow_rgb)
        ck("② 只含 rgba 的文件被收录", len(got) == 1, str(got))
        ck("② 该 rgba 记为违规", bool(got) and got[0]["hits"][0]["v"].endswith("（rgba）"), str(got))

        # ②-bis 负对照：rgba 的 RGB 在准用集里 ⇒ **不算**违规（这是"假工作量"那条）
        q = Path(td) / "ok-rgba.html"
        q.write_text("<style>.b{background:rgba(11,17,32,.56)}</style>", encoding="utf-8")
        ck("② 准用色+透明度的 rgba 不算混入", scan([q], allow_hex, allow_rgb) == [],
           str(scan([q], allow_hex, allow_rgb)))

    # ③ `count_hits`：总数 = hex + rgba（原来只数 hex）
    fake = [{"file": "a", "hits": [{"v": "#111111", "line": 1}]},
            {"file": "b", "hits": [{"v": "#222222（rgba）", "line": 1},
                                   {"v": "#333333（rgba）", "line": 2}]}]
    n_all, n_hex, n_rgba = count_hits(fake)
    ck("③ 总数含 rgba", n_all == 3, "%d" % n_all)
    ck("③ hex 与 rgba 分得开", (n_hex, n_rgba) == (1, 2), "%d/%d" % (n_hex, n_rgba))
    # 负对照：只数 len(hits) 的旧写法会少算
    ck("③ 负对照·旧写法在纯 rgba 文件上少算",
       count_hits([fake[1]])[0] == 2, "本器在纯 rgba 上应得 2")

    # ④ 准用集来自**现读**，不是写死
    hexes, rgbas, srcs = allowed_set()
    ck("④ 准用集非空", len(hexes) >= 10, str(len(hexes)))
    ck("④ 准用集有出处", len(srcs) >= 1, str(srcs))
    ck("④ RGB 集包含 hex 换算值", (11, 17, 32) in rgbas, str(sorted(rgbas))[:60])

    # ⑤ `_norm`：短 hex 不许崩（2026-10-27 实测本器因 `#000a` 直接抛 ValueError）
    ck("⑤ 3 位短 hex 展开", _norm("#abc") == "#AABBCC", _norm("#abc"))
    ck("⑤ 4 位 short hex（#RGBA）取 RGB", _norm("#000a") == "#000000", _norm("#000a"))
    ck("⑤ 8 位 hex 取前 6", _norm("#11223344") == "#112233", _norm("#11223344"))
    # ⑤ 负对照：原实现在 4 位上会切出空串 —— 用同一条切片复现，证明这个洞是真的
    old_norm = "#000A"
    ck("⑤ 负对照·旧实现切出空串", old_norm[5:7] == "", old_norm[5:7])

    # ⑥ `:root` 里的**注释**不许进调色板（否则在注释写一句就把颜色洗白了）
    h2, r2 = _tokens_from("--a:#123456; /* 原来写的是 #ABCDEF，已改 */ --b:rgba(9,8,7,.5)")
    ck("⑥ 真令牌进集", "#123456" in h2, str(h2))
    ck("⑥ 注释里的色号不进集", "#ABCDEF" not in h2, str(h2))
    ck("⑥ 负对照·不剥注释就会进集",
       "#ABCDEF" in {_norm(m.group(0)) for m in HEX.finditer("--a:#123456; /* #ABCDEF */")},
       "不剥注释的写法居然也没进集 ⇒ 这条判据量不出问题")
    ck("⑥ rgba 的 RGB 也进集", (9, 8, 7) in r2, str(r2))

    # ⑦ 「非皮肤域」只对**特定的文件头/上下文**成立，换个地方立刻恢复违规
    with tempfile.TemporaryDirectory() as td:
        gen = Path(td) / "gen-data.js"
        gen.write_text("/* 自动生成，别手改。重建：py x.py render */\n"
                       "var M={c:'#AA0011'};", encoding="utf-8")
        g = scan([gen], {"#0B1120"}, {(11, 17, 32)})
        ck("⑦ 生成产物·进 nonskin", bool(g) and len(g[0]["hits"]) == 0
           and len(g[0]["nonskin"]) == 1, str(g))
        ck("⑦ 生成产物·理由写明", bool(g) and g[0]["nonskin"][0]["domain"] == "生成产物", str(g))
        # ⑦ 负对照：**同样的颜色**放进普通页面 ⇒ 必须还是违规（证明不是一刀切放行）
        plain = Path(td) / "plain.html"
        plain.write_text("<style>.a{color:#AA0011}</style>", encoding="utf-8")
        pl = scan([plain], {"#0B1120"}, {(11, 17, 32)})
        ck("⑦ 负对照·无生成头仍判违规", bool(pl) and len(pl[0]["hits"]) == 1, str(pl))

        drei = Path(td) / "scene.js"
        drei.write_text("scene.add(new THREE.HemisphereLight(0x9fb6d6, 0x141821, .85));",
                        encoding="utf-8")
        d = scan([drei], {"#0B1120"}, {(11, 17, 32)})
        ck("⑦ 3D 光照·进 nonskin", bool(d) and len(d[0]["hits"]) == 0
           and len(d[0]["nonskin"]) == 2, str(d))
        # ⑦ 负对照：同一组色号写成 CSS ⇒ 必须还是违规
        css3 = Path(td) / "scene.css"
        css3.write_text(".a{color:#9FB6D6;background:#141821}", encoding="utf-8")
        c3 = scan([css3], {"#0B1120"}, {(11, 17, 32)})
        ck("⑦ 负对照·同色号写成 CSS 仍违规",
           bool(c3) and len(c3[0]["hits"]) == 2, str(c3))

    n = total[0]
    ck("元检查·断言条数 >= 12", n >= 12, "只有 %d 条" % n)

    print("audit_skin selftest：%d/%d 通过" % (n - len(fails), n))
    for f in fails:
        print("  ✗ " + f)
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="皮肤分流机检（新壳只许用新壳皮肤）")
    ap.add_argument("--add", nargs="*", default=[], help="额外要看的文件/目录")
    ap.add_argument("--json", default="")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--include-tests", action="store_true",
                    help="连 tests/ 一起扫（默认跳过：那是故意合成的违规夹具）")
    ap.add_argument("--selftest", action="store_true",
                    help="只跑本器自己的判据（不起扫描、不读仓）")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

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

    bad = scan(files, allow_hex, allow_rgba)
    # 🔴 2026-10-27 修（两次，记下来免得再犯）：
    #    ① 原来 `total = sum(len(hits))` 只数 hex，`rgba_outside` 从没进过总数 ⇒ 报 361、实际 542；
    #    ② 把 rgba 一律计入又造出假工作量（准用色 + 透明度被当混入）。
    #    **正解**：rgba 按 RGB 三分量判，违规的**进 hits**（能定位能改），准用的不算。
    #    所以现在 `hits` 里 hex 与 rgba 混装，`total` 就是 `len(hits)` 之和，
    #    再按后缀拆出两者构成（`rgba_outside` 只剩"该文件里 rgba 总处数"这个参考值）。
    total = sum(len(b["hits"]) for b in bad)
    n_rgba_bad = sum(1 for b in bad for h in b["hits"] if h["v"].endswith("（rgba）"))
    n_hex = total - n_rgba_bad
    rgba_seen = sum(int(b.get("rgba_outside") or 0) for b in bad)
    n_old = sum(1 for b in bad for h in b["hits"] if h["v"] in ban_old)
    n_ai = sum(1 for b in bad for h in b["hits"] if h["v"] in ban_ai)

    # 🔴 2026-10-27 加：**在役 / 归档分开判**。
    #    归档区（`_archive-*` / `shell-junk` / `_broken`）按本仓口径是「不适用 = 明确不需要、
    #    **不算欠账**」。原来把归档混进总数 ⇒ 报 301 而其中 224 在归档，
    #    读数看着像"永远收不完"，实际在役只有 72。**退出码只按在役算**。
    def _is_arch(p):
        low = p.lower().replace("/", "\\")
        return any(k in low for k in ("_archive", "shell-junk", "_broken"))

    live = [b for b in bad if not _is_arch(b["file"]) and b["hits"]]
    arch = [b for b in bad if _is_arch(b["file"]) and b["hits"]]
    n_live = sum(len(b["hits"]) for b in live)
    n_arch = sum(len(b["hits"]) for b in arch)
    n_rgba_live = sum(1 for b in live for h in b["hits"] if h["v"].endswith("（rgba）"))
    # 「不适用」= 生成产物 / 3D 光照里的色。**明确不需要、不算欠账**，但必须报出来。
    nonskin = [(b["file"], h) for b in bad if not _is_arch(b["file"]) for h in b["nonskin"]]

    if not bad:
        print("  ✅ **零混入**：新壳里出现的每一个 hex 与 rgba 的 RGB 都在准用集内")
    elif not live:
        print("  ✅ **在役皮肤零混入** —— 准用集外只剩「不适用域」（见下）")
    else:
        print("  🔴 **在役 %d 处**准用集之外的颜色，落在 %d 个文件（hex %d + rgba %d）；"
              "另有 %d 处 rgba 是准用色+透明度，**不算混入**"
              % (n_live, len(live), n_live - n_rgba_live, n_rgba_live,
                 max(0, rgba_seen - n_rgba_bad)))
        for b in live:
            tag = ""
            if any(h["v"] in ban_ai for h in b["hits"]):
                tag = "  ← **含 AI 指纹色**"
            elif any(h["v"] in ban_old for h in b["hits"]):
                tag = "  ← **含旧皮肤色**"
            print("      %s%s" % (b["file"], tag))
            for h in b["hits"][:8]:
                mark = "AI指纹" if h["v"] in ban_ai else ("旧皮肤" if h["v"] in ban_old else "外来")
                print("          L%-5d %s  [%s]" % (h["line"], h["v"], mark))
    if n_arch:
        print("  ⏳ 归档区另有 %d 处（%d 个文件）—— **不适用、不算欠账**，不计入退出码"
              % (n_arch, len(arch)))
    if nonskin:
        # 「不适用」要有理由，不许静默放行 —— 三态里的第三态就是这个
        per = {}
        for fp, h in nonskin:
            per.setdefault((fp, h["domain"]), []).append(h["v"])
        print("  ⚪ 不适用 %d 处（**不是欠账**，但仍列出来，免得下次有人当成漏掉）："
              % len(nonskin))
        for (fp, dom), vs in sorted(per.items()):
            print("      %-44s %-8s %d 处：%s"
                  % (fp, dom, len(vs), " ".join(sorted(set(vs)))))
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
    # 退出码**只按在役**：归档区是「不适用、不算欠账」，不该把打包闸/CI 卡住
    return 1 if live else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
