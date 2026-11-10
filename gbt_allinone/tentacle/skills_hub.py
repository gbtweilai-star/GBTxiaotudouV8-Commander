# -*- coding: utf-8 -*-
"""技能库（skills_hub）：把"方法论"做成能力位。

主人 2026-11-01：「先看看有没有你缺失的东西先吞噬强化一下自己」
—— 吞了 superpowers-zh 的 20 个 skill（brainstorming / TDD / systematic-debugging /
writing-plans / verification-before-completion …）。

分工（写死在代码里）：
  · 能力位 = **手**：真跑、过门、留审计；
  · skill   = **做法**：先想清楚再动手（硬门、判据、检查清单）。

op:
    list     列出全部 skill（name / 来源 / 一行描述）
    get      取一个 skill 全文（{"name": "brainstorming"}）
    match    按任务文本匹配最相关的 skill（{"query": "...", "top": 3}）
    verify   体检：数量 / frontmatter 合法 / 名字唯一
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def _parse(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = {"name": path.parent.name, "description": "", "source": "", "tags": [],
            "path": str(path.relative_to(ROOT)), "body": text}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return meta
    fm = m.group(1)
    # 🔴 2026-11-09 修（块标量让 160 个 skill 的描述集体变成 "|"）：
    #   原实现逐行 `split(":", 1)`，遇到 `description: |` 取到的值就是字面量 "|"，
    #   紧跟其后的缩进正文（YAML 块标量）被整段丢掉 ⇒ desc 空 ⇒ match 只能靠文件名猜。
    #   实测吞噬 nexu-io/open-design 后 198 个 skill 里大量 desc == "|"。
    #   这里按 YAML 规则解析 `|` / `>`（含 |-、|+、>- 修饰符）：块内容是其后所有**缩进**行。
    _lines = fm.splitlines()
    _i = 0
    while _i < len(_lines):
        line = _lines[_i]
        if ":" not in line or line.lstrip().startswith("#"):
            _i += 1
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if re.fullmatch(r"[|>][+-]?", v):
            _block = []
            _i += 1
            while _i < len(_lines):
                nxt = _lines[_i]
                if nxt.strip() == "":
                    _block.append("")
                    _i += 1
                    continue
                if nxt[:1] in (" ", "\t"):
                    _block.append(nxt.strip())
                    _i += 1
                else:
                    break
            v = " ".join(x for x in _block if x).strip()
        else:
            v = v.strip('"').strip("'")
            _i += 1
        if k == "name":
            meta["name"] = v or meta["name"]
        elif k == "description":
            meta["description"] = v
        elif k == "source":
            meta["source"] = v
        elif k == "tags":
            meta["tags"] = [x.strip() for x in v.strip("[]").split(",") if x.strip()]
    meta["body"] = text[m.end():]
    return meta


def _all() -> list:
    out = []
    if SKILLS.is_dir():
        for p in sorted(SKILLS.rglob("SKILL.md")):
            try:
                out.append(_parse(p))
            except Exception:
                continue
    return out


# 🔴 2026-11-09 补（中文查询搜不到英文 skill）：
#   吞噬 nexu-io/open-design 的 160 个 skill 后，它们的 description 全是英文，
#   而 _score 的分词只有「空格切词 + 中文 bigram」两种。中文提问「杂志风编辑排版演示」
#   一个 bigram 都落不到英文 desc 上 ⇒ 正主（after-hours-editorial-template /
#   deck-guizang-editorial）得 0 分，反而把 body 里恰好有中文的 web-clone 顶上来。
#   这里只加一层「中文概念 → 英文关键词」的桥，不改任何 skill 原文。
_ZH_EN = {
    "杂志": ("editorial", "magazine"), "编辑": ("editorial",), "排版": ("typography", "layout"),
    "字体": ("typography", "font"), "配色": ("palette", "color"), "颜色": ("color",),
    "演示": ("deck", "slide", "presentation"), "幻灯片": ("slide", "deck"), "简报": ("brief", "deck"),
    "汇报": ("report", "review"), "报告": ("report",), "一页纸": ("one-pager",),
    "动效": ("motion", "animation"), "动画": ("animation", "animate"), "过渡": ("transition",),
    "滚动": ("scroll", "scrolltrigger"), "交互": ("interaction", "interactive"),
    "三维": ("threejs", "3d"), "着色器": ("shader",), "粒子": ("particle",),
    "图表": ("chart", "d3"), "可视化": ("visualization", "d3"), "数据": ("data",),
    "仪表盘": ("dashboard",), "看板": ("dashboard", "kanban"),
    "品牌": ("brand",), "标识": ("logo",), "海报": ("poster",), "封面": ("cover",),
    "卡片": ("card",), "社交": ("social",), "小红书": ("xiaohongshu",),
    "网页": ("web", "website", "frontend"), "网站": ("web", "website"), "落地页": ("landing",),
    "前端": ("frontend",), "组件": ("component", "shadcn"), "界面": ("ui", "interface"),
    "配色方案": ("palette",), "设计体系": ("design-system", "design system"),
    "设计评审": ("design-review", "review"), "评审": ("review",), "打磨": ("polish",),
    "复刻": ("clone",), "克隆": ("clone",), "仿站": ("clone",),
    "视频": ("video", "remotion"), "剪辑": ("video", "clip"), "字幕": ("caption",),
    "图片": ("image", "imagegen"), "生成图": ("imagegen", "image"), "修图": ("image-edit",),
    "简历": ("resume",), "线框": ("wireframe",), "流程图": ("flowchart",),
    "文档": ("doc", "docx"), "表格": ("sheet", "table"), "发票": ("invoice",),
    "品控": ("qa", "review", "gate"), "质感": ("taste", "premium"),
    "高级感": ("premium", "high-end"), "极简": ("minimalist",), "粗野": ("brutalist",),
    "瑞士": ("swiss",), "暗色": ("dark",), "油画": ("oil",), "手绘": ("hand-drawn",),
    "表情": ("sticker", "gif"), "音乐": ("music", "audio"), "配音": ("speech", "voice"),
}


def _expand(q: str) -> list:
    """中文概念 → 英文关键词（只用于补分，不改原查询）。"""
    out = []
    for zh, ens in _ZH_EN.items():
        if zh in q:
            out.extend(ens)
    return sorted(set(out))


def _score(skill: dict, query: str) -> float:
    q = str(query or "").lower()
    if not q:
        return 0.0
    score = 0.0
    name = skill["name"].lower()
    if name in q:
        score += 5.0
    parts = [w for w in re.split(r"[\s,，。；;、/]+", q) if len(w) >= 2]
    desc = (skill.get("description") or "").lower()
    body = skill["body"].lower()
    for w in parts:
        if w in name:
            score += 3.0
        if w in desc:
            score += 2.0
        if w in body:
            score += 0.8
        # 中文 bigram（无空格分词时也能命中）
        for i in range(len(w) - 1):
            bg = w[i:i + 2]
            if bg in name:
                score += 1.2
            elif bg in desc:
                score += 0.8
            elif bg in body:
                score += 0.2
    # 中文→英文桥（英文描述的 skill 也能被中文问到）
    for w in _expand(q):
        if w in name:
            score += 2.6
        if w in desc:
            score += 1.6
        if w in body:
            score += 0.3
    return round(score, 2)


def run(op: str = "list", **kw) -> dict:
    op = (op or "list").lower()
    items = _all()
    if op == "validate":
        return validate(items)
    if op == "pack":
        return pack(str(kw.get("name") or ""), items)
    if op == "install":
        return install(str(kw.get("name") or ""), str(kw.get("dir") or ""),
                       str(kw.get("target") or "claude"), bool(kw.get("dry_run", True)),
                       items)
    if op == "read":
        return read_file(str(kw.get("name") or ""), str(kw.get("file") or ""), items)
    if op == "list":
        return {"ok": True, "count": len(items),
                "skills": [{"name": s["name"], "source": s["source"],
                            "desc": (s["description"] or "")[:80],
                            "path": s["path"]} for s in items]}
    if op == "get":
        name = str(kw.get("name") or "").strip()
        for s in items:
            if s["name"] == name:
                return {"ok": True, "skill": {k: v for k, v in s.items() if k != "body"},
                        "text": s["body"]}
        return {"ok": False, "error": "user_error: 没有这个 skill：%s" % name,
                "have": [s["name"] for s in items]}
    if op == "match":
        q = str(kw.get("query") or "")
        top = max(1, int(kw.get("top") or 3))
        ranked = sorted(((_score(s, q), s) for s in items), key=lambda x: -x[0])
        ranked = [r for r in ranked if r[0] > 0][:top]
        return {"ok": True, "query": q,
                "matches": [{"score": sc, "name": s["name"],
                             "desc": (s["description"] or "")[:100]} for sc, s in ranked],
                "note": "命中 0 条也是合法结果（不硬凑）" if not ranked else ""}
    if op == "verify":
        names = [s["name"] for s in items]
        dup = sorted({n for n in names if names.count(n) > 1})
        no_desc = [s["name"] for s in items if not s["description"]]
        return {"ok": not dup, "count": len(items), "duplicates": dup,
                "no_description": no_desc,
                "verdict": "clean" if not dup else "duplicate_names"}
    return {"ok": False, "error": "skills_hub 不认 op=%s（list/get/match/verify）" % op}

# ═══ Agent Skills 规范（2026-11-01 吸收自 agentskills.io/specification）═══
# 只取"能嵌进我们"的四件事：合规校验 / 打包 / 装进别的 agent / 渐进读取。
# 拒收：直接把 skills-ref 库抄进来（我们自己的解析器已够）、marketplace JSON（平台打包件）。

_NAME_RE = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?")
VALID_FIELDS = {"name", "description", "license", "compatibility", "metadata",
                "allowed-tools", "version", "triggers", "displayName", "source", "upstream"}


def _dir_of(skill: dict) -> pathlib.Path:
    return pathlib.Path(ROOT) / skill["path"] if not str(skill["path"]).startswith("/") else pathlib.Path(skill["path"])


def _frontmatter(skill: dict) -> dict:
    text = skill.get("body") or ""
    path = pathlib.Path(ROOT) / (skill["path"])
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.S)
        fm = {}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line and not line.startswith(" "):
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip('"').strip("'")
        return fm
    except Exception:  # noqa: BLE001
        return {}


def _files(skill: dict) -> dict:
    d = _dir_of(skill).parent
    out = {}
    for sub in ("scripts", "references", "assets"):
        p = d / sub
        out[sub] = sorted(str(x.relative_to(d)).replace("\\", "/")
                          for x in p.rglob("*") if x.is_file()) if p.is_dir() else []
    return out


def validate(items=None) -> dict:
    """按 Agent Skills 规范校验全部 skill（name 规则 / 描述长度 / 目录同名 / 可选字段上限）。"""
    items = items if items is not None else _all()
    errors, warns = [], []
    for s in items:
        fm = _frontmatter(s)
        name = s["name"]
        d = _dir_of(s).parent.name
        e = []
        if not _NAME_RE.fullmatch(name or ""):
            e.append("name 非法（只许 a-z0-9-，不许首尾/连续连字符）")
        if len(name) > 64:
            e.append("name > 64 字符")
        if name != d:
            e.append("name(%s) 与目录名(%s) 不一致" % (name, d))
        desc = s.get("description") or ""
        if not (1 <= len(desc) <= 1024):
            e.append("description 长度 %d 不在 1..1024" % len(desc))
        comp = fm.get("compatibility") or ""
        if comp and len(comp) > 500:
            e.append("compatibility > 500 字符")
        if "metadata" in fm and not fm.get("metadata"):
            warns.append("%s: metadata 为空" % name)
        if e:
            errors.append({"skill": name, "path": s["path"], "errors": e})
    return {"ok": True, "count": len(items), "errors": errors, "warnings": warns,
            "verdict": "clean" if not errors else "broken",
            "spec": "agentskills.io/specification（2026-11-01 吸收）",
            "note": "只校验规范里的硬约束；可选字段缺省不算错"}


def pack(name: str = "", items=None) -> dict:
    """把技能打成 Agent Skills 兼容 zip（<name>/SKILL.md + scripts/references/assets）。"""
    import zipfile

    items = items if items is not None else _all()
    want = [s for s in items if not name or s["name"] == name]
    if not want:
        return {"ok": False, "error": "user_error: 没有这个 skill：%s" % name}
    tmp = pathlib.Path(ROOT) / "state" / "tmp" / "skill-packs"
    tmp.mkdir(parents=True, exist_ok=True)
    made = []
    for s in want:
        d = _dir_of(s).parent
        dst = tmp / (s["name"] + ".zip")
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    z.write(f, str(pathlib.Path(s["name"]) / f.relative_to(d)))
        made.append({"name": s["name"], "zip": str(dst), "bytes": dst.stat().st_size,
                     "files": _files(s)})
    return {"ok": True, "packs": made, "count": len(made),
            "note": "zip 内是 <name>/SKILL.md 结构，符合 Agent Skills 目录结构"}


TARGETS = {
    "claude": "~/.claude/skills",
    "codex": "~/.codex/skills",
    "agents": "~/.agents/skills",
}


def install(name: str = "", dir: str = "", target: str = "claude",
            dry_run: bool = True, items=None) -> dict:
    """把 skill 装进别的 agent 的 skills 目录（默认只演练；真装要过 filesystem_write 门）。"""
    import shutil

    items = items if items is not None else _all()
    s = next((x for x in items if x["name"] == name), None)
    if not s:
        return {"ok": False, "error": "user_error: 没有这个 skill：%s" % name}
    base = pathlib.Path(dir).expanduser() if dir else pathlib.Path(
        TARGETS.get(target, "")).expanduser()
    if not str(base) or not str(base).strip():
        return {"ok": False, "error": "user_error: 需要 dir（或 target ∈ %s）" % ", ".join(TARGETS)}
    src = _dir_of(s).parent
    dst = pathlib.Path(base) / s["name"]
    plan = {"skill": name, "from": str(src), "to": str(dst),
            "dry_run": bool(dry_run),
            "files": [str(f.relative_to(src)).replace("\\", "/")
                      for f in sorted(src.rglob("*")) if f.is_file()]}
    if dry_run:
        return {"ok": True, **plan, "note": "演练：dry_run=true 不写盘；要真装传 dry_run=false"}
    # 真装：写盘门（主人可信会话直接放行）
    try:
        from ..security import policy as P
        if not P.is_trusted():
            from .. import auth_gate
            g = auth_gate.check_and_consume_many(["filesystem_write"], detail="skills_install")
            if not g.get("ok"):
                return {"ok": False, "denied": True, "how_to_grant": g.get("how_to_grant"),
                        "error": "denied: 装 skill 到外部目录需要 filesystem_write 票"}
    except Exception:  # noqa: BLE001
        pass
    try:
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        ok = (dst / "SKILL.md").is_file()
        return {"ok": ok, **plan, "installed": ok,
                "note": "已装到 %s（含 SKILL.md）" % dst}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160]), **plan}


def read_file(name: str = "", file: str = "", items=None) -> dict:
    """渐进读取：只读 skill 目录内的 references/scripts/assets 文件（防路径穿越）。"""
    items = items if items is not None else _all()
    s = next((x for x in items if x["name"] == name), None)
    if not s:
        return {"ok": False, "error": "user_error: 没有这个 skill：%s" % name}
    d = _dir_of(s).parent.resolve()
    p = (d / file).resolve()
    try:
        p.relative_to(d)
    except ValueError:
        return {"ok": False, "error": "user_error: 越界路径（只许 skill 目录内）"}
    if not p.is_file():
        return {"ok": False, "error": "user_error: 没有这个文件：%s" % file,
                "files": _files(s)}
    return {"ok": True, "skill": name, "file": file,
            "text": p.read_text(encoding="utf-8", errors="replace")[:20000],
            "files": _files(s)}
