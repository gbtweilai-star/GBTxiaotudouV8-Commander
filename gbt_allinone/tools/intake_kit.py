# gbt-capability: intake_kit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""intake_kit —— **外部件接入图鉴**（七步法第 1–2 步的真读数 + 六件知识面 → 人话一次问到"该读哪一份"）。

## 来历（主人令：「这几个分类吞噬不能跳过任何步骤必须全部吞噬」）

按本仓 `gbt-vendor-intake` 七步法接入**七件**，**一步不跳**：

| 件 | 来源 | 许可 | 真值钱的面 |
|---|---|---|---|
| `motionsites.ai` | `TheSatyam-Singh/motionsites.ai` | MIT | **65 条网页设计提示词**（Hero/落地页/SaaS） |
| `impeccable` | `pbakaus/impeccable` | Apache-2.0 | **设计语言系统**（agent 插件 · 24 份 SKILL + reference） |
| `hyperframes` | `heygen-com/hyperframes` | Apache-2.0 | 写 HTML 就渲染视频（40 份 SKILL + packages） |
| `ai-engineering-from-scratch` | `rohitg00/...` | MIT | **20 阶段**（上游自述 523 课）+ SKILL **26 份**（排除依赖/产物目录后现扫） |
| `Agent-Reach` | `Panniantong/Agent-Reach` | MIT | 一条 CLI 读/搜 **15 个平台** |
| `ponytail` | `DietrichGebert/ponytail` | MIT | **让 Agent 少写代码**的规则包（12 份 SKILL） |
| `DeepSeek-Bot` | `Fei2411/DeepSeek-Bot` | Apache-2.0 | **DeepSeek Harness 的 bot 插件**：长期存活的 Bot 团队 + 群聊轮流发言 + 上下文管家 |

## 本件做什么（第 4–7 步落到这一位）

`build` 扫七件的**知识面**（各件 `SKILL.md` · motionsites 的提示词 · ai-engineering 的阶段 · Agent-Reach 的文档 ·
DeepSeek-Bot 的文档与功能表）
⇒ 一条一行（**带 `文件#L行号`**）落 `store/intake_kit/index.jsonl`；`find` 人话 → 该读**哪一件的哪一份**。
每件另附**只读体检台账**（第 2 步的真读数）。

## 铁律

1. **只读 · 零执行 · 零出网**：不装依赖、不跑它们的代码、不 npm i。
2. **不改 `_upstream/**` 一个字节**。
3. **不编**：说明只从文件现读（frontmatter / 首个标题 / 首句散文）；取不到留空。
4. **体检读数带日期**（写死会过期 ⇒ 标成"某日某探针的读数"，不假装是实时值）。
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_UP = _ROOT / "_upstream"
_OPS = ("status", "build", "find", "api", "where")

# 六件（第 1 步落位 + 第 2 步体检的结论）—— `verdict` 是**七步法走到哪**的口径
_PIECES = (
    {"name": "motionsites.ai", "repo": "TheSatyam-Singh/motionsites.ai", "license": "MIT",
     "what": "65 条网页设计提示词（Hero / 落地页 / SaaS 界面）+ 视频预览",
     "verdict": "接了 · 提示词面", "take": "prompts/*.md"},
    {"name": "impeccable", "repo": "pbakaus/impeccable", "license": "Apache-2.0",
     "what": "专为 AI 设计链路打造的设计语言系统（agent 插件 · SKILL + reference）",
     "verdict": "接了 · 技能面", "take": "**/SKILL.md + reference/*.md"},
    {"name": "hyperframes", "repo": "heygen-com/hyperframes", "license": "Apache-2.0",
     "what": "写 HTML 就能渲染视频的框架（SKILL + packages: cli/core/engine）",
     "verdict": "已在册 · 技能面早前已接（本轮核过同一批 40 份 SKILL）", "take": "skills/**"},
    {"name": "ai-engineering-from-scratch", "repo": "rohitg00/ai-engineering-from-scratch",
     "license": "MIT",
     "what": "AI 工程动手学习路径：**20 阶段**（上游自述 523 课）+ SKILL 26 份（排除依赖/产物目录后现扫）",
     "verdict": "接了 · 课程与技能面", "take": "phases/* + **/SKILL.md"},
    {"name": "Agent-Reach", "repo": "Panniantong/Agent-Reach", "license": "MIT",
     "what": "一条 CLI 让 Agent 读/搜 15 个平台（Twitter/Reddit/YouTube/GitHub/B站/小红书… · 零 API 费用）",
     "verdict": "接了 · 知识面（执行面走既有触手，不新起进程）", "take": "llms.txt + docs/**"},
    {"name": "ponytail", "repo": "DietrichGebert/ponytail", "license": "MIT",
     "what": "让 Agent 少写代码的规则包（最好的代码是没写的那行）· SKILL + AGENTS.md",
     "verdict": "接了 · 规则面", "take": "**/SKILL.md + AGENTS.md"},
    # 主人令「还漏了一个对我们最重要的」⇒ 补上（`gh search` 现搜找到，非猜名）
    {"name": "DeepSeek-Bot", "repo": "Fei2411/DeepSeek-Bot", "license": "Apache-2.0",
     "what": "**DeepSeek Harness 的 bot 插件**：把 dsh 变成**一支长期存活的 Bot 团队**——"
             "bot 间 `message_bot` 传话 · **群聊轮流发言 / `@` 传棒 / 没人加料就 `[PASS]`** · "
             "**上下文管家 + 检查点压缩 + FTS5 全文索引**（长聊不爆窗口）· 每 Bot 记忆 + 团队共享 · "
             "密钥只出卡片、Bot 看不到值",
     "verdict": "接了 · 架构与功能面", "take": "README + AGENTS.md + docs + ds-bot/README 功能表"},
)
# 🔴 **只读体检读数**（2026-10-13 探针 `.scratch/_intake_health.py` 现扫得出，跑完即回收）
#    —— 带日期存，**不许**当成实时值念；重扫要重跑探针。
_HEALTH_20261013 = {
    "motionsites.ai": {"files": 233, "MB": 802.7, "hit": {}, "postinstall": []},
    "impeccable": {"files": 3903, "MB": 74.1,
                   "hit": {"net_call": 480, "base64_decode": 42, "child_process": 38,
                           "subprocess": 2, "eval(": 37}, "postinstall": []},
    "hyperframes": {"files": 9278, "MB": 881.7,
                    "hit": {"child_process": 532, "net_call": 361, "base64_decode": 13,
                            "subprocess": 33, "exec(": 13, "eval(": 32, "hardcoded_key": 1},
                    "postinstall": ["prepare: test -d .git && lefthook install || true"]},
    "ai-engineering-from-scratch": {"files": 6928, "MB": 88.0,
                                    "hit": {"subprocess": 443, "net_call": 179, "eval(": 73,
                                            "hardcoded_key": 1, "exec(": 15, "child_process": 45,
                                            "os.system": 9, "shell_exec": 2, "base64_decode": 1},
                                    "postinstall": []},
    "Agent-Reach": {"files": 121, "MB": 1.2,
                    "hit": {"net_call": 69, "subprocess": 196, "hardcoded_key": 5},
                    "postinstall": []},
    "ponytail": {"files": 202, "MB": 10.1,
                 "hit": {"eval(": 2, "exec(": 6, "child_process": 11, "subprocess": 25,
                         "net_call": 11}, "postinstall": []},
    "DeepSeek-Bot": {"files": 211, "MB": 4.95,
                     "hit": {"net_call": 34, "child_process": 8}, "postinstall": []},
}
# 三处 `hardcoded_key` 的**落实结论**（逐条读过上下文才敢这么写）
_KEY_VERDICTS = {
    "hyperframes": "`packages/*/src/telemetry/*.ts` 的 **PostHog 客户端公钥**（源码注释：public project key, "
                   "safe to embed in client code）⇒ **不是泄漏**；但**确有遥测外呼**，用之前要知道",
    "ai-engineering-from-scratch": "`manuals/**/sources/*.md` 的**教学占位符**"
                                   "（`api_key=\"not-needed-when-no-api-key-flag\"`）⇒ 不是泄漏",
    "Agent-Reach": "`tests/test_*.py` 的**测试假值**（`super-secret-key-12345`）⇒ 不是泄漏",
}

_FM_NAME = re.compile(r"^name:\s*[\"']?(.+?)[\"']?\s*$")
_FM_DESC = re.compile(r"^description:\s*[\"']?(.+?)[\"']?\s*$")
_H1 = re.compile(r"^#\s+(.+?)\s*$")
_CAT = re.compile(r"^\>\s*\*\*Category:\*\*\s*(.+?)\s*$")
_TYPE = re.compile(r"^\>\s*\*\*Type:\*\*\s*(.+?)\s*$")
_LIC = re.compile(r"^\>\s*\*\*License:\*\*\s*(.+?)\s*$")
_SKIP_DIR = {".git", "node_modules", "dist", "build", "__pycache__", "assets", "outputs"}
_EXTS = (".md", ".mdx")

# 中文口语 → 英文关键词（同族教训：四路名字全英文，中文人话没有桥就 0 命中）
_CN_BRIDGE = {
    "设计": "design", "审美": "aesthetic craft taste", "改版": "redesign audit",
    "评审": "critique review audit", "审查": "audit review", "无障碍": "accessibility a11y",
    "配色": "color colorize palette", "排版": "typography layout", "动效": "animate animation motion",
    "打磨": "polish finish craft", "质感": "craft delight", "落地页": "landing hero saas",
    "首屏": "hero", "英雄区": "hero", "官网": "landing saas site", "作品集": "portfolio",
    "代码": "code dev engineering", "少写": "lazy minimal", "冗余": "redundancy cleanup",
    "课程": "course lesson curriculum", "学习": "learn course", "数学": "math foundations",
    "深度学习": "deep learning", "变压器": "transformer", "视觉": "computer vision",
    "语音": "speech audio", "强化学习": "reinforcement", "评测": "evaluation eval",
    "视频": "video render html", "渲染": "render", "字幕": "caption subtitle",
    "读网页": "read web url", "搜索": "search discover", "小红书": "xiaohongshu",
    "推特": "twitter x", "油管": "youtube", "哔哩": "bilibili", "知乎": "in",
    "群聊": "group chat bots", "长期存活": "long-lived bot", "机器人": "bot bots",
    "上下文": "context steward checkpoint compaction", "记忆": "memory notes",
    "密钥": "secrets api key", "用量": "usage tokens",
}
_WORD_SPLIT = re.compile(r"([a-z0-9])([A-Z])")
_WORD = re.compile(r"[a-z0-9]+")


def _store_dir() -> Path:
    d = os.environ.get("GBT_STORE_DIR")
    return Path(d) if d else (_ROOT / "gbt_allinone" / "store")


def _index_path() -> Path:
    p = _store_dir() / "intake_kit"
    p.mkdir(parents=True, exist_ok=True)
    return p / "index.jsonl"


def _rel(p: Path) -> str:
    return p.relative_to(_ROOT).as_posix()


def _head_text(p: Path, n: int = 120) -> list:
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()[:n]
    except OSError:
        return []


def _front(lines: list) -> tuple:
    """YAML frontmatter → (name, desc)。取不到给 ('','')."""
    if not lines or lines[0].strip() != "---":
        return "", ""
    name = desc = ""
    for ln in lines[1:60]:
        if ln.strip() == "---":
            break
        m = _FM_NAME.match(ln)
        if m and not name:
            name = m.group(1).strip()
        m = _FM_DESC.match(ln)
        if m and not desc:
            desc = m.group(1).strip()
    return name, desc


def _first_prose(lines: list, skip: int = 0) -> str:
    for ln in lines[skip:]:
        t = ln.strip()
        if t and not t.startswith(("#", ">", "-", "*", "|", "```", "---")):
            return re.sub(r"\s+", " ", t)[:180]
    return ""


def _walk_md(root: Path, names=("SKILL.md",)) -> list:
    out = []
    if not root.is_dir():
        return out
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in _SKIP_DIR]
        for f in fn:
            if f in names and f.lower().endswith(_EXTS):
                out.append(Path(dp) / f)
    return sorted(out)


def _scan_skills(piece: str, root: Path) -> list:
    rows = []
    for p in _walk_md(root):
        lines = _head_text(p, 40)
        name, desc = _front(lines)
        title, line = "", 0
        for i, ln in enumerate(lines):
            m = _H1.match(ln)
            if m:
                title, line = m.group(1).strip(), i + 1
                break
        if not name:
            name = title or p.parent.name
        rows.append({"kind": "skill", "piece": piece, "name": name, "title": title,
                     "desc": desc or _first_prose(lines, line), "path": _rel(p),
                     "line": line or 1})
    return rows


def _scan_prompts(piece: str, root: Path) -> list:
    """motionsites.ai：`prompts/*.md` —— 每份带 `> **Category:** …` 结构。"""
    rows = []
    d = root / "prompts"
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        lines = _head_text(p, 60)
        title, cat, typ, lic = "", "", "", ""
        for i, ln in enumerate(lines):
            if not title:
                m = _H1.match(ln)
                if m:
                    title = m.group(1).strip()
            for rx, key in ((_CAT, "cat"), (_TYPE, "typ"), (_LIC, "lic")):
                m = rx.match(ln)
                if m and not {"cat": cat, "typ": typ, "lic": lic}[key]:
                    if key == "cat":
                        cat = m.group(1).strip()
                    elif key == "typ":
                        typ = m.group(1).strip()
                    else:
                        lic = m.group(1).strip()
        rows.append({"kind": "prompt", "piece": piece, "name": title or p.stem,
                     "title": title, "cat": cat, "type": typ, "lic": lic,
                     "desc": "类别 %s · 类型 %s · 许可 %s" % (cat or "?", typ or "?", lic or "?"),
                     "path": _rel(p), "line": 1})
    return rows


def _scan_phases(piece: str, root: Path) -> list:
    """ai-engineering-from-scratch：`phases/<NN>-<slug>/` —— 一条一行。"""
    rows = []
    d = root / "phases"
    if not d.is_dir():
        return rows
    for sub in sorted(x for x in d.iterdir() if x.is_dir()):
        rd = next((sub / n for n in ("README.md", "readme.md") if (sub / n).is_file()), None)
        desc, line = "", 1
        if rd is not None:
            lines = _head_text(rd, 40)
            for i, ln in enumerate(lines):
                if _H1.match(ln):
                    line = i + 1
                    break
            desc = _first_prose(lines, line)
        rows.append({"kind": "phase", "piece": piece, "name": sub.name, "title": sub.name,
                     "desc": desc, "path": _rel(rd) if rd else _rel(sub), "line": line})
    return rows


def _scan_mds(piece: str, root: Path, extra=()) -> list:
    """给定 md 清单 → 一条一行（H1 作名，首个散文件段落作说明）。"""
    cands = [root / n for n in ("README.md", "README.zh.md", "AGENTS.md", "CHANGELOG.md",
                                "CONTRIBUTING.md")] + [root / e for e in extra]
    d = root / "docs"
    if d.is_dir():
        cands += sorted(d.glob("*.md"))
    rows = []
    for p in cands:
        if not p.is_file():
            continue
        lines = _head_text(p, 40)
        title, line = p.stem, 1
        for i, ln in enumerate(lines):
            m = _H1.match(ln)
            if m:
                title, line = m.group(1).strip(), i + 1
                break
        rows.append({"kind": "doc", "piece": piece, "name": title, "title": title,
                     "desc": _first_prose(lines, line), "path": _rel(p), "line": line})
    return rows


def _scan_features(piece: str, root: Path, rel: str) -> list:
    """把 `ds-bot/README.md` 的 `- **功能名**：说明` 逐条抽出来 —— **这才是那件里真值钱的东西**。"""
    p = root / rel
    if not p.is_file():
        return []
    rows = []
    for i, ln in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()):
        m = re.match(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*[:：]?\s*(.*)$", ln)
        if not m:
            continue
        name, desc = m.group(1).strip(), re.sub(r"\s+", " ", m.group(2)).strip()
        if not desc:                       # 说明在下一行（缩进续行）时，取最近的非空行
            continue
        rows.append({"kind": "feature", "piece": piece, "name": name, "title": name,
                     "desc": desc[:300], "path": _rel(p), "line": i + 1})
    return rows


def _scan_docs(piece: str, root: Path) -> list:
    """Agent-Reach：`llms.txt` 的 `## 小节` + `docs/*.md`。"""
    rows = []
    llms = root / "llms.txt"
    if llms.is_file():
        lines = llms.read_text(encoding="utf-8", errors="replace").splitlines()
        cur, cur_line = None, 0
        for i, ln in enumerate(lines):
            m = re.match(r"^##\s+(.+?)\s*$", ln)
            if m:
                cur, cur_line = m.group(1).strip(), i + 1
                rows.append({"kind": "doc", "piece": piece, "name": "llms.txt · " + cur,
                             "title": cur, "desc": "", "path": _rel(llms), "line": cur_line})
                continue
            if cur and ln.startswith("- ") and len(ln) > 8:
                txt = re.sub(r"\s+", " ", ln.strip("- ").strip())[:170]
                rows.append({"kind": "doc", "piece": piece, "name": txt[:60], "title": cur,
                             "desc": txt, "path": _rel(llms), "line": i + 1})
    for p in sorted((root / "docs").glob("*.md")) if (root / "docs").is_dir() else []:
        lines = _head_text(p, 30)
        title, line = p.stem, 1
        for i, ln in enumerate(lines):
            m = _H1.match(ln)
            if m:
                title, line = m.group(1).strip(), i + 1
                break
        rows.append({"kind": "doc", "piece": piece, "name": title, "title": title,
                     "desc": _first_prose(lines, line), "path": _rel(p), "line": line})
    return rows


def build(force: bool = False, **_kw) -> dict:
    """扫六件的**知识面**建索引（只追加）；每件另附体检台账。"""
    rows, per = [], {}
    for pc in _PIECES:
        root = _UP / pc["name"]
        if not root.is_dir():
            per[pc["name"]] = {"rows": 0, "why": "不在盘"}
            continue
        got = []
        if pc["name"] == "motionsites.ai":
            got += _scan_prompts(pc["name"], root)
        elif pc["name"] == "ai-engineering-from-scratch":
            got += _scan_phases(pc["name"], root) + _scan_skills(pc["name"], root)
        elif pc["name"] == "Agent-Reach":
            got += _scan_docs(pc["name"], root)
        elif pc["name"] == "DeepSeek-Bot":
            got += _scan_mds(pc["name"], root, extra=("ds-bot/README.md",))
            got += _scan_features(pc["name"], root, "ds-bot/README.md")
        else:
            got += _scan_skills(pc["name"], root)
        per[pc["name"]] = {"rows": len(got),
                           "kinds": {k: sum(1 for r in got if r["kind"] == k)
                                     for k in {r["kind"] for r in got}}}
        rows += got
    if not rows:
        return {"ok": False, "error": "六件一份都抽不出 ⇒ 不写空库（fail-closed）"}
    idx = _index_path()
    if idx.is_file() and not force:
        items = _load()
        return {"ok": True, "reused": True, "rows": len(items), "index": str(idx),
                "note": "索引已在；要重扫给 force=true"}
    with idx.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "intake_kit_index",
                             "pieces": len(_PIECES), "count": len(rows),
                             "items": rows}, ensure_ascii=False) + "\n")
    return {"ok": True, "indexed": len(rows), "by_piece": per,
            "体检台账_20261013": {k: _HEALTH_20261013.get(k, {}) for k in per},
            "hardcoded_key_落实": _KEY_VERDICTS, "index": str(idx)}


def _load() -> list:
    idx = _index_path()
    if not idx.is_file():
        return []
    last = None
    for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                last = json.loads(line)
            except Exception:                                # noqa: BLE001
                continue
    return (last or {}).get("items") or []


def _fields(r: dict) -> dict:
    """df 与打分**共用同一份字段**（同族踩过：两处口径不一致 ⇒ 假结论）。"""
    return {"name": "%s %s" % (r.get("name") or "", r.get("title") or ""),
            "piece": r.get("piece") or "",
            "desc": "%s %s %s" % (r.get("desc") or "", r.get("cat") or "", r.get("type") or ""),
            "path": (r.get("path") or "").replace("/", " ").replace("_", " ").replace("-", " ")}


def _words(s) -> set:
    return set(_WORD.findall(_WORD_SPLIT.sub(r"\1 \2", str(s)).lower()))


def _allwords(r: dict) -> set:
    out: set = set()
    for v in _fields(r).values():
        out |= _words(v)
    return out


def find(q: str = "", limit: int = 8, piece: str = "", kind: str = "", **_kw) -> dict:
    """人话 → **该读哪一件的哪一份**（带 `文件#L行号`）。**命中 0 就如实报 0**。"""
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 ⇒ 先 op=build"}
    from ..semantic_route import grams
    qs = str(q or "")
    bridge = [cn for cn in _CN_BRIDGE if cn in qs.lower()]
    qtext = " ".join([qs] + [_CN_BRIDGE[cn] for cn in bridge])
    qg = grams(qtext) if qtext.strip() else set()
    qw = _words(qtext)
    n = max(1, len(items))
    df, dfw = {}, {}
    if qg:
        for r in items:
            seen = set()
            for v in _fields(r).values():
                seen |= (qg & grams(v))
            for t in seen:
                df[t] = df.get(t, 0) + 1
    if qw:
        for r in items:
            for t in (qw & _allwords(r)):
                dfw[t] = dfw.get(t, 0) + 1
    idf = {t: math.log(1.0 + n / (1.0 + c)) for t, c in df.items()}
    idfw = {t: math.log(1.0 + n / (1.0 + c)) for t, c in dfw.items()}
    w = {"name": 2.5, "piece": 1.2, "desc": 1.2, "path": 0.6}
    out = []
    for r in items:
        if piece and r["piece"].lower() != str(piece).lower():
            continue
        if kind and r["kind"] != kind:
            continue
        v = _fields(r)
        s, why = 0.0, []
        for k in w:
            hit = qg & grams(v[k])
            if hit:
                s += w[k] * sum(idf.get(t, 0.0) for t in hit)
                why.append("%s命中%d" % (k, len(hit)))
        wh = qw & _allwords(r)
        if wh:
            s += 4.0 * sum(idfw.get(t, 0.0) for t in wh)
            why.append("词命中:" + ",".join(sorted(wh))[:60])
        if qg and s <= 0:
            continue
        out.append({**r, "score": round(s, 3), "why": why,
                    "where": "%s#L%d" % (r["path"], r["line"])})
    out.sort(key=lambda r: -r["score"])
    return {"ok": True, "q": q, "hits": len(out), "items": out[:int(limit)], "indexed": len(items),
            "bridge": bridge,
            "_口径": "打分 = Σ(字段权重 × gram-idf)[名 2.5 · 件 1.2 · 说明 1.2 · 路径 0.6] "
                     "+ 4.0 × Σ(词-idf)；命中项给 `文件#L行号` ⇒ 直接去读那份；**命中 0 就是 0**"}


def api(name: str = "", **_kw) -> dict:
    """按**准确名**取一条。名字对不上就是 0。"""
    if not str(name or "").strip():
        return {"ok": False, "fail_closed": True, "error": "要 name（用 op=find 拿候选名）"}
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 ⇒ 先 op=build"}
    nm = str(name).strip().lower()
    hit = [r for r in items if (r.get("name") or "").lower() == nm
           or (r.get("title") or "").lower() == nm]
    return {"ok": True, "name": name, "hits": len(hit),
            "items": [{**r, "where": "%s#L%d" % (r["path"], r["line"])} for r in hit]}


def status(**_kw) -> dict:
    items = _load()
    per = {}
    for r in items:
        per[r["piece"]] = per.get(r["piece"], 0) + 1
    return {"ok": True, "op": "status", "kind": "intake_kit", "upstream": str(_UP),
            "indexed": len(items), "by_piece": per, "ops": list(_OPS),
            "件": [{"name": p["name"], "repo": p["repo"], "license": p["license"],
                    "what": p["what"], "verdict": p["verdict"],
                    "on_disk": (_UP / p["name"]).is_dir()} for p in _PIECES],
            "体检台账_20261013": _HEALTH_20261013, "hardcoded_key_落实": _KEY_VERDICTS,
            "_口径": "七件均按 `gbt-vendor-intake` 七步法接入（克隆→只读体检→…）；"
                     "本件**只读 · 零执行 · 零出网**；体检读数是**2026-10-13 探针**扫出来的，不是实时值"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "intake_kit",
            "entry": "run_task('intake_kit', {'op':'find','q':'落地页提示词'})", "ops": list(_OPS),
            "what": "七件外部件的**接入图鉴**：身份 · 许可 · 体检读数 · 知识面在哪（带 文件#L行号）",
            "七件": [{"件": p["name"], "许可": p["license"], "口径": p["verdict"]} for p in _PIECES],
            "hard_rules": ["只读 · 零执行 · 零出网（不装依赖、不跑它们的代码）",
                           "不改 `_upstream/**` 一个字节",
                           "说明只从文件现读（frontmatter / 标题 / 首句），取不到留空",
                           "体检读数**带日期**（2026-10-13），不许当实时值念"],
            "七步法走到哪": {"1 克隆落位": "六件全落 `_upstream/`（深度 1）",
                             "2 只读体检": "六件全扫（危险命中逐条落实，见 `hardcoded_key_落实`）",
                             "3 垫片代偿": "未需（六件的真值钱面都是**文本**：提示词/技能/课程/文档/规则）",
                             "4 包成能力位": "本件（注册表 + 分派 + 门）",
                             "5 路由与读数": "走唯一门 `run_task`；未知名 fail-closed",
                             "6 咬合触手": "autobind 全链（分型→承载→刷页→判据→记账）",
                             "7 挂机检判据": "`gbt_allinone/tests/test_intake_kit.py`"},
            "上游": "motionsites.ai · impeccable · hyperframes · ai-engineering-from-scratch · Agent-Reach · ponytail",
            "下游": "design_atlas / bits_kit / motion_kit（设计侧）· art_brief（策划）· gbt-code-taste（代码侧）"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("build", build), ("find", find), ("api", api),
                   ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    import sys
    try:                        # 本机控制台默认 GBK ⇒ 中文直接打会 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="外部件接入图鉴（六件 · 七步法）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
