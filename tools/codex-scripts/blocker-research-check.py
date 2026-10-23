#!/usr/bin/env python
# gbt-capability: none
"""blocker-research-check.py —— 「卡点三查 + 能力自知」的机械闸（**只读：不写任何盘**）。

为什么要这件
------------
主人令（2026-10-08，逐字）：
    「给框架也注入遇到卡点要懂得查资料以及自身能力自知，别跟个傻逼是的」

今天真实栽的跟头（本闸就是为它立的）：
    本会话探到「浏览器 `enumerateDevices` 0 个 audioinput + `getUserMedia` 抛 NotFoundError
    + WASAPI 活动录音端点 0」，就下了结论「**这台机器没有可用的麦 / 只有主人能启用设备**」，停了。
    主人一句「**白龙马开源项目的麦克风这么部署的你不看的吗**」——去查才发现两件事：
      ① 白龙马 `electron/main.cjs` 第 779-787 行**显式给 media 权限放行**
         （`setPermissionRequestHandler` / `setPermissionCheckHandler`），而且三个窗都放行
         （主窗 779-787 · focusBannerWindow 974-981 · wakeProbeWindow 1463-1467）；
      ② 采集端 `src/ui/brain-ui/voice-core.js` 有**约束对象 + deviceId 回退链 + 显式采样率 +
         Worklet→ScriptProcessor 双路径**（623-630 约束 · 646-668 回退链 · 731-734 采样率 · 779-815 双路径）。
    ⇒ **真因首先是"我们壳没放媒体权限"**（本仓 `holo_pet_w3/shell/*.cjs` 全文件 grep
      `setPermissionRequestHandler|setPermissionCheckHandler|media` = **0 命中**），
      **不是"没麦"**。而本机触手总纲自己写着「在册 5 个录音设备（DISABLED 1 …）」
      —— 这两条现成资料都没查，就开口说了"做不到"。这就是"不查资料 + 对自己能力不自知"。

所以本工具干一件很窄的事：**扫文档里那些"做不到/没有/只能靠主人"式的结论句，
看看它旁边有没有三查留痕**；没有 ⇒ 报红。它**不判对错**，只判"你查没查、留没留痕"。

判据（每条都写清"怎么算坏"；共 11 条，`--selftest` 逐条验）
------------------------------------------------------------
* **C1 · 结论句识别（强词）** —— 整句出现强结论词（`做不到 / 办不到 / 不支持 / 只能靠主人 /
  无法实现 / 无法做到 / 不可能做到 / 无此能力 / 没有能力 / 没有可用的 / 没有这个能力 /
  不能做 / 没法做`）⇒ 该句被判为**结论句**，须有三查。
  🔴 为什么**不**收 `不可能`：实测（2026-10-08 首跑）它绝大多数不是卡点结论句，而是修辞与验收问句
  （「怎么让同类问题**不可能**再发生」「物理上不可能」「不可能是"已完成"」），逐条看全是假红。
  只保留 `不可能做到` 这种明确"做不到"形态。**词表写死在这里，放宽即违规。**
* **C2 · 结论句识别（弱词相邻式）** —— 弱词（`没有 / 无法 / 不能 / 未支持 / 缺 / 缺了 /
  未接 / 未装`）**必须与能力语素相邻**（中间只许夹一个动词，如「没有**可用**能力位」
  「缺**调用**接口」）才算结论句；或能力语素 + `不可用 / 未支持 / 拿不到` 的**倒装**形态
  （「4 条通道不可用」）。
  🔴 为什么弱词要卡相邻：**不卡就会把普通散文判成结论**。实测（本仓 `docs/*.md` + `AGENTS.md`）：
  不卡相邻 ⇒ 255 句命中（"没有网络"这种叙事全进来了，全是假红）；
  卡成"词+能力语素"相邻 ⇒ 43 句，逐条看都是真结论句。**阈值与规则写死在这里，放宽即违规。**
* **C3 · 豁免词表（授权态不算能力结论）** —— `缺授权 / 缺票 / 缺权限 / 缺作用域`
  **不计**结论句：那是"谁能给"的授权态（口径第三档，有明确接法：主人发作用域），
  不是"做不到"。**但**：把它写成强词（`做不到 / 只能靠主人 / 不支持`）的句子，C1 照样抓。
* **C4 · 代码块与引号不算** —— 两块豁免：
  (a) ```` ``` ```` / `~~~` 围起来的块内**不判结论句、也不算三查留痕**（块里是样例句、命令回执、
      被引用的他人原文——拿它当证据就是回声）；
  (b) **引号内只由词表词组成的片段**（`"做不到"` 「只能靠主人」）以及**含元话语标记的行里的引号片段**
      （元话语标记 = `口径/词表/留痕/三查/判据/规则/格式/标准/定义/引用/原话/照抄/模板`）
      —— 那是"**在讨论这些词**"，不是断言；例：「没有三查出处的"**做不到**"，不许写进交付物」。
      引号判据是**机械的**（正则 + 词表 fullmatch），不是"看着像引用就不算"。
  ⇒ **三查留痕请写在正文段落里**，塞在代码块里的留痕本闸不认。
* **C5 · 三查覆盖（同段落或其后 15 行）** —— 结论句所在**段落**（空行分隔）内，
  或**其后 15 行**内，须同时出现 `查①` `查②` `查③` **三种**标记（也认 `查1/查2/查3`）。
  只出现一两种 ⇒ 红（说明留痕只写了半截）。
* **C6 · 出处可解析** —— 每个三查标记的**同一从句**里（到 `·` / `;` / `。` / 换行 为止）
  须带出处形态：括号内容（`（…）`）、路径 token（含斜杠或 `文件.扩展名`）、
  命令行（`--flag`）、URL、`文件:行` 之一。**指不出处的标记不算标记**（"我查过了"不是出处）。
* **C7 · 含糊不算数（fail-closed）** —— 结论句里带 `可能 / 也许 / 大概 / 未必 / 不确定 /
  说不好 / 应该吧` 之类的骑墙词，而三查又不满三条 ⇒ 红（卡点要的是二值结论，不是"大概不行"）。
* **C8 · 文件级 fail-closed** —— 目标文件读不了、一个文件都没匹配上、或**代码围栏不成对**
  ⇒ 红 + **退出码 2**（不许"扫不动就当没事"）。
* **C9 · 读数必须自报** —— 输出必须带：扫描文件数 / 命中结论句数 / 三查齐（绿）/ 缺三查（红）
  / 每一条红的 `文件:行` + 原文。`--json` 给同一份读数的机器版。
* **C10 · 退出码语义（可复跑）** —— `0` = 全绿；`1` = 有红（缺三查/含糊/来源不可解析）；
  `2` = 用法或 IO 错（fail-closed）。
* **C11 · 负对照（自证）** —— `--selftest` 在**临时目录**里现造样例：
  正例（三查齐）⇒ 必须绿 · 负例（只有结论）⇒ 必须红 · 未知/坏格式（围栏不成对）⇒ 必须红且退出码 2 ·
  授权态句（缺授权，非结论）⇒ 必须不判红。四例全符 ⇒ `--selftest` 退出码 0，任一不符 ⇒ 1，并贴原文。
  🔴 自测**只许用临时目录样例**，不许拿别人的交付文档当靶子（会误报，也会踩到并行任务的件）。

口径边界（不许念过头）
----------------------
本工具**不判结论对不对**（那要人查资料），只判"**结论旁边有没有三查留痕**"。
它绿，只说明"这段写了三查"，**不等于三查是真的**——出处真假仍要人核。
同理它红，也可能是"这条不是卡点结论"（如引用他人原文、表格标题）——
**红条目一律贴原文**，让人一眼判，不替人下结论。

用法
----
    py -3.14 tools/codex-scripts/blocker-research-check.py                  # 默认扫 docs/*.md + AGENTS.md
    py -3.14 tools/codex-scripts/blocker-research-check.py --json           # 机器版读数（同退出码）
    py -3.14 tools/codex-scripts/blocker-research-check.py --files docs/能力接线总表.md AGENTS.md
    py -3.14 tools/codex-scripts/blocker-research-check.py --selftest       # 正负对照（临时目录）
    py -3.14 tools/codex-scripts/blocker-research-check.py --limit 80       # 打印条数上限

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]

# ── 口径常量（写死；放宽即违规，见 C2/C3） ────────────────────────────────
DEFAULT_TARGETS = ("docs/*.md", "AGENTS.md")
WINDOW_LINES = 15                      # 命中句之后多少行内找三查（C5）

# C1 强结论词：整句命中即算结论句
STRONG = re.compile(
    r"做不到|办不到|不支持|只能靠主人|无法实现|无法做到|不可能做到|无此能力|"
    r"没有能力|没有可用的|没有这个能力|不能做|没法做"
)
# C2 弱词 + 能力语素（必须相邻，中间只许夹一个动词）
NOUN = (
    r"(能力位|能力|接口|端点|通道|设备|麦克风|摄像头|声卡|音频|GPU|"
    r"门|服务|端口|脚本|工具|组件|函数|模块|字段|钩子|路线|臂|权重|模型|密钥|仓库)"
)
WEAK = re.compile(
    r"((没有|无法|不能|未支持|缺|缺了|未接|未装)\s*"
    r"(调用|使用|跑|装|接|支持|实现|提供|找到|拿到|连上|启动|走通|启用|开|读)?\s*"
    r"(的)?\s*" + NOUN + r"|" + NOUN + r"\s*(不可用|未支持|不可得|拿不到))"
)
# C3 授权态豁免（不是能力结论）
GRANT_EXEMPT = re.compile(r"缺(授权|票|权限|作用域)")
# C7 骑墙词
HEDGE = re.compile(r"(?<!不)可能|也许|大概|未必|不确定|说不好|应该吧")

# C4b 引号 + 元话语：引号里只是在"讨论这些词"时不算断言（机械判据，见判据说明）
BLOCK_TOKENS = ("做不到", "办不到", "不支持", "只能靠主人", "无法实现", "无法做到",
                "不可能做到", "无此能力", "没有能力", "没有可用的", "没有这个能力",
                "不能做", "没法做", "能不能做", "没有", "无法", "不能", "不可用", "未支持")
# ⚠️ 引号必须**按成对类型**匹配（「」/『』/“”/""），**不许跨类型配对**：
#    首跑撞过 —— 一行里「…"…" 混用时，跨类型配对会把"引号外的正文"整段吞掉或错位，
#    造出"看着像引号里其实没盖上"的假红（§7 表格行就这么被误判过一次）。
_QA, _QB = "「", "」"      # 「 」
_QC, _QD = "『", "』"      # 『 』
_QL, _QR = "“", "”"      # “ ”
QUOTE = re.compile(
    _QA + r"([^" + _QA + _QB + r"]{0,80})" + _QB + "|" +
    _QC + r"([^" + _QC + _QD + r"]{0,80})" + _QD + "|" +
    _QL + r"([^" + _QL + _QR + r"]{0,80})" + _QR + "|" +
    '"([^"]{0,80})"'
)
QUOTE_SPLIT = re.compile(r"[\s/、·|,，;；:：]+")
META = re.compile(r"口径|词表|留痕|三查|判据|规则|格式|标准|定义|引用|原话|照抄|模板|门规|写法"
                  r"|红条|读数|命中|统计|本闸|闸")

FENCE = re.compile(r"^\s*(```+|~~~+)")
# 句号级切分：中英文句末 + 分号 + 换行
SENT_SPLIT = re.compile(r"[^。；！？\n]+")

# C5 三查标记
MARK_CHAR = {"①": "①", "1": "①", "②": "②", "2": "②", "③": "③", "3": "③"}
MARK = re.compile(r"查\s*[①②③1-3]")
# C6 出处形态
SRC_PATHISH = re.compile(r"[A-Za-z0-9_][\w.\-]*[./\\][\w./\\\-]*|[\w\-]+\.(py|md|json|jsonl|js|cjs|mjs|html|txt|ps1|psm1|toml|yml|yaml)")
SRC_CLI = re.compile(r"--[A-Za-z][\w\-]*|\bgh api\b|https?://")
SRC_ANCHOR = re.compile(r"[\w./\\\-]+[：:]\d{1,5}(-\d{1,5})?")


def now_ts() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def read_text(p: Path) -> str | None:
    try:
        return p.read_bytes().decode("utf-8-sig", "replace")
    except Exception:  # noqa: BLE001
        return None


def fence_mask(lines: list[str]) -> tuple[list[bool], bool]:
    """返回 (每行是否在代码围栏内, 围栏是否成对)。C4/C8。"""
    inside = []
    state = None
    unclosed = False
    for ln in lines:
        m = FENCE.match(ln)
        if m:
            tok = m.group(1)[:3]
            if state is None:
                state = tok
                inside.append(True)
                continue
            if state == tok:
                state = None
                inside.append(True)      # 闭合行本身也不算正文
                continue
            inside.append(True)
            continue
        inside.append(state is not None)
    if state is not None:
        unclosed = True
    return inside, unclosed


def split_paragraph(lines: list[str]) -> list[int]:
    """每行 → 段落号（空行分段；C5「同段落」用）。"""
    pid = []
    cur = 0
    for ln in lines:
        if ln.strip() == "":
            cur += 1
            pid.append(-1)
        else:
            pid.append(cur)
    return pid


def strip_quotes(line: str) -> str:
    """C4b：按机械判据把"只是在讨论这些词"的引号片段抹掉。"""
    def repl(m: re.Match) -> str:
        span = next((g for g in m.groups() if g is not None), "")
        toks = [t for t in QUOTE_SPLIT.split(span) if t]
        if toks and all(t in BLOCK_TOKENS for t in toks):
            return "〔引〕"
        if META.search(line):
            return "〔引〕"
        return m.group(0)
    return QUOTE.sub(repl, line)


def clause_of(text: str, pos: int, span: int = 90) -> str:
    """取标记之后的同一从句（到 · ；。 或换行 为止）。C6 用。

    ⚠️ **不按 `|` 切**（表格线不是从句边界）：文档里三查留痕常写在表格单元格里，
    若按 `|` 切，标记后的"出处"列会被切掉，使**正确**的表格留痕被误判成"缺出处"（实测撞过）。
    """
    tail = text[pos:pos + span]
    cut = len(tail)
    for ch in ("·", "；", ";", "。", "\n"):
        i = tail.find(ch)
        if i != -1:
            cut = min(cut, i)
    return tail[:cut]


def marker_has_source(text: str, m: re.Match) -> bool:
    cl = clause_of(text, m.end())
    # 括号内容：全角（…）与半角 (…) 都认（留痕格式 `查①…(出处)` 用的是半角，实测撞过）
    for lo, hi in (("（", "）"), ("(", ")")):
        if lo in cl and hi in cl and len(cl.split(lo, 1)[1].split(hi, 1)[0].strip()) >= 2:
            return True
    if SRC_ANCHOR.search(cl) or SRC_CLI.search(cl):
        return True
    if SRC_PATHISH.search(cl):
        return True
    return False


def find_hits(path: Path) -> dict:
    """扫一个文件，返回结论句命中与三查覆盖判定。"""
    res = {"file": str(path), "hits": [], "covered": 0, "missing": 0,
           "malformed": 0, "notes": []}
    txt = read_text(path)
    if txt is None:
        res["malformed"] += 1
        res["notes"].append("读不了（解码/IO 失败）⇒ fail-closed 红")
        return res
    lines = txt.splitlines()
    inside, unclosed = fence_mask(lines)
    if unclosed:
        res["malformed"] += 1
        res["notes"].append("代码围栏不成对（``` 没闭合）⇒ fail-closed 红")
    pids = split_paragraph(lines)

    for i, ln in enumerate(lines):
        if inside[i]:
            continue                       # C4：代码块不判
        plain = strip_quotes(ln)          # C4b：引号里"讨论词形"不算断言
        if not (STRONG.search(plain) or WEAK.search(plain)):
            continue
        for sm in SENT_SPLIT.finditer(plain):
            s = sm.group(0).strip()
            if not s:
                continue
            strong = STRONG.search(s)
            weak = WEAK.search(s)
            if not (strong or weak):
                continue
            kind = "强词" if strong else "弱词相邻"
            if not strong and GRANT_EXEMPT.search(s) and not WEAK.search(
                    GRANT_EXEMPT.sub("", s)):
                continue                   # C3：授权态豁免
            # C5：同段落 + 其后 15 行
            ctx_ids = {pids[i]}
            ctx = ln
            j = i + 1
            while j < len(lines) and j <= i + WINDOW_LINES:
                ctx += "\n" + lines[j]
                if pids[j] != -1:
                    ctx_ids.add(pids[j])
                j += 1
            block_txt = "\n".join(lines[k] for k in range(len(lines))
                                  if pids[k] in ctx_ids)
            marks = {}
            mark_src_ok = True
            for mm in MARK.finditer(block_txt):
                ch = mm.group(0)[-1]
                key = MARK_CHAR.get(ch, ch)
                if not marker_has_source(block_txt, mm):
                    mark_src_ok = False
                marks[key] = marks.get(key, 0) + 1
            three = all(k in marks for k in ("①", "②", "③"))
            hedge = bool(HEDGE.search(s))
            if three and mark_src_ok:
                res["covered"] += 1
                verdict = "绿（三查齐）"
            elif three and not mark_src_ok:
                res["missing"] += 1
                verdict = "红（三查标记缺出处：指不出处的不算查过 · C6）"
            elif hedge:
                res["missing"] += 1
                verdict = "红（结论骑墙且三查不满三条 · C7）"
            else:
                res["missing"] += 1
                got = "".join(sorted(marks)) or "无"
                verdict = "红（缺三查：只见 %s）" % got
            res["hits"].append({
                "line": i + 1,
                "sentence": s[:220],
                "kind": kind,
                "marks": marks,
                "verdict": verdict,
            })
    return res


def aggregate(files: list[Path]) -> dict:
    """按「文件 + 归一化句子」聚合（同一形态重复 N 处只报一条，带次数）。"""
    out = {"files": [], "entries": [], "counts": {
        "files": 0, "hits": 0, "covered": 0, "missing": 0, "malformed": 0}}
    for p in files:
        r = find_hits(p)
        rel = os.path.relpath(p, ROOT).replace("\\", "/") if str(p).startswith(str(ROOT)) else str(p)
        r["file"] = rel
        out["files"].append({"file": rel, "hits": len(r["hits"]),
                             "covered": r["covered"], "missing": r["missing"],
                             "malformed": r["malformed"], "notes": r["notes"]})
        agg = {}
        for h in r["hits"]:
            key = re.sub(r"\s+", "", h["sentence"])[:60]
            e = agg.setdefault(key, {"file": rel, "sentence": h["sentence"],
                                     "verdict": h["verdict"], "kind": h["kind"],
                                     "lines": [], "count": 0})
            e["count"] += 1
            if len(e["lines"]) < 5:
                e["lines"].append(h["line"])
        out["entries"].extend(agg.values())
        out["counts"]["files"] += 1
        out["counts"]["hits"] += len(r["hits"])
        out["counts"]["covered"] += r["covered"]
        out["counts"]["missing"] += r["missing"]
        out["counts"]["malformed"] += r["malformed"]
    return out


def verdict_of(agg: dict) -> tuple[int, list]:
    reds = [e for e in agg["entries"] if e["verdict"].startswith("红")]
    male = [f for f in agg["files"] if f["malformed"]]
    if agg["counts"]["files"] == 0:
        return 2, ["一个文件都没匹配上 ⇒ fail-closed（C8）"]
    if male:
        return 2, ["%s：%s" % (f["file"], "；".join(f["notes"])) for f in male]
    if reds:
        return 1, []
    return 0, []


def collect_targets(patterns: list[str], files: list[str]) -> list[Path]:
    got: list[Path] = []
    for pat in patterns:
        for s in _glob.glob(str(ROOT / pat)) if not os.path.isabs(pat) else _glob.glob(pat):
            p = Path(s)
            if p.is_file():
                got.append(p)
    for f in files:
        p = Path(f)
        if not p.is_absolute():
            p = ROOT / f
        if p.is_file():
            got.append(p)
        else:
            got.append(p)                  # 点名却不在 ⇒ 交给 verdict 判（读不了 = 红）
    seen, uniq = set(), []
    for p in got:
        k = str(p).lower()
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


# ── C11 负对照：临时目录样例 ────────────────────────────────────────────
CASE_POS = """# 正例：三查齐全（结论句与留痕同段）

本机活动录音端点 0 ⇒ 乍看"这台机器没有可用的麦克风"。
查①本机既有实现：`state/surfaces/netsh.json` 43 把键 + `run tentacle_manifest` 回执（在册 5 个录音设备，DISABLED 1）；
查②上游参照项目：`BaiLongma/electron/main.cjs` 第 779-787 行给 media 放行（gh api 现读原文）；
查③官方文档/本机 API 清单：`py -3.14 -m gbt_allinone list` 回执（240 位）→ 结论：能做到，怎么做到：给壳加权限放行 + deviceId 回退链。
"""

CASE_NEG = """# 负例：只有结论、没有三查

本机麦克风这条腿本机是真没有，做不到语音采集，只能靠主人去系统设置里启用设备。
"""

CASE_HEDGE = """# 负例：骑墙结论、没有三查

麦克风大概是没有的，可能做不到，也许要主人才能开。
"""

CASE_GRANT = """# 授权态（不是能力结论）：不该报红

这一格缺授权，要主人发作用域；缺票的能力位调用会如实报缺什么。
"""

CASE_BAD = """# 未知/坏格式：围栏不成对

```python
print("没闭合")
本机做不到语音采集，没有可用的麦克风。
"""


def selftest() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="blocker-research-selftest-"))
    try:
        files = {"case_pos.md": CASE_POS, "case_neg.md": CASE_NEG,
                 "case_hedge.md": CASE_HEDGE, "case_grant.md": CASE_GRANT,
                 "case_bad.md": CASE_BAD}
        paths = []
        for name, body in files.items():
            p = tmp / name
            p.write_text(body, encoding="utf-8")
            paths.append(p)
        agg = aggregate(paths)
        code, notes = verdict_of(agg)
        per = {f["file"].replace("\\", "/"): f for f in agg["files"]}
        def st(name):
            for k, v in per.items():
                if k.endswith(name):
                    return v
            return None
        checks = []
        pos = st("case_pos.md")
        checks.append(("正例（三查齐）⇒ 绿",
                       pos is not None and pos["covered"] == 1 and pos["missing"] == 0,
                       "%s" % (pos or {})))
        neg = st("case_neg.md")
        checks.append(("负例（只有结论）⇒ 红",
                       neg is not None and neg["missing"] >= 1,
                       "%s" % (neg or {})))
        hd = st("case_hedge.md")
        checks.append(("负例（骑墙结论）⇒ 红",
                       hd is not None and hd["missing"] >= 1,
                       "%s" % (hd or {})))
        gr = st("case_grant.md")
        checks.append(("授权态句（缺授权/缺票）⇒ 不判红",
                       gr is not None and gr["missing"] == 0 and gr["hits"] == 0,
                       "%s" % (gr or {})))
        bad = st("case_bad.md")
        checks.append(("坏格式（围栏不成对）⇒ 红且退出码 2",
                       bad is not None and bad["malformed"] >= 1 and code == 2,
                       "%s" % (bad or {})))
        print("== blocker-research-check · 负对照（%s）==" % tmp)
        ok_all = True
        for name, ok, detail in checks:
            ok_all = ok_all and ok
            print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
            if not ok:
                print("        实读：%s" % detail)
        # 逐条贴原文（正负各一行）
        raw = {p.name: read_text(p).splitlines() for p in paths}
        print("  · 正例原文：%s" % raw["case_pos.md"][2][:100])
        print("  · 负例原文：%s" % raw["case_neg.md"][2][:100])
        print("  读数：命中 %d · 绿 %d · 红 %d · 坏格式文件 %d"
              % (agg["counts"]["hits"], agg["counts"]["covered"],
                 agg["counts"]["missing"], agg["counts"]["malformed"]))
        print("  ⇒ %s（退出码 %d，临时目录已清）" % ("负对照全符" if ok_all else "负对照不符", 0 if ok_all else 1))
        return 0 if ok_all else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="GBT小土豆V8 · 卡点三查机械闸（只读）：结论句旁边有没有三查留痕")
    ap.add_argument("--targets", default=None,
                    help="目标 glob（逗号分隔，相对仓根）· 默认 %s；给了 --files 就以点名为准" % ",".join(DEFAULT_TARGETS))
    ap.add_argument("--files", nargs="*", default=[],
                    help="点名文件（**优先**：点名了就不扫默认集，避免把别人的件卷进来）")
    ap.add_argument("--json", action="store_true", help="机器版读数（退出码同）")
    ap.add_argument("--limit", type=int, default=40, help="打印红条上限")
    ap.add_argument("--selftest", action="store_true", help="负对照（临时目录样例）")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.targets:
        pats = [s.strip() for s in args.targets.split(",") if s.strip()]
    elif args.files:
        pats = []                      # 点名优先：不含默认集
    else:
        pats = list(DEFAULT_TARGETS)
    files = collect_targets(pats, args.files)
    agg = aggregate(files)
    code, notes = verdict_of(agg)
    agg["tool"] = "blocker-research-check"
    agg["generated_at"] = now_ts()
    agg["targets"] = pats
    agg["exit_code"] = code
    agg["fail_closed"] = notes

    if args.json:
        print(json.dumps(agg, ensure_ascii=False, indent=1))
        return code

    print("== 卡点三查机械闸 · %s ==" % agg["generated_at"])
    print("   目标：%s（点名 %d 件）" % (" · ".join(pats), len(args.files)))
    print("   读数：扫描文件 %d · 命中结论句 %d · 三查齐(绿) %d · 缺三查(红) %d · 坏格式文件 %d"
          % (agg["counts"]["files"], agg["counts"]["hits"], agg["counts"]["covered"],
             agg["counts"]["missing"], agg["counts"]["malformed"]))
    for n in notes:
        print("   🔴 fail-closed：%s" % n)
    reds = [e for e in agg["entries"] if e["verdict"].startswith("红")]
    if reds:
        print("   —— 红条（贴原文，供人一眼判；本闸不替人下结论）——")
        for e in reds[:args.limit]:
            print("   🔴 %s:%s（同一形态 %d 处）%s" % (e["file"], e["lines"][0], e["count"], e["verdict"]))
            print("        原文：%s" % e["sentence"][:150])
        if len(reds) > args.limit:
            print("   …（还有 %d 条未打印，用 --limit 放宽）" % (len(reds) - args.limit))
    else:
        print("   ✅ 没有缺三查的结论句（命中句都有三查留痕）")
    print("   退出码：%d（0 全绿 / 1 有红 / 2 fail-closed）" % code)
    return code


if __name__ == "__main__":
    sys.exit(main())
