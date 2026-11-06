# gbt-capability: taste_guard
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""taste_guard — 反 AI 烂大街设计闸（蒸馏自 Leonxlnx/taste-skill · MIT，只蒸规则不搬代码）。

为什么长这一位：主人 2026-11-01 看到 "Taste Skill — The anti-slop frontend framework for AI agents"
后说「来继续让天真把这个吞噬了」。上游的魂是**先定方向、再按真实素材做、最后用真浏览器量**；
本件把两段都吞进来：
  · 静态扫 HTML/CSS：渐变 / 玻璃 / 阴影 / 小字距大写眉标 / 等宽 / 编号 / 图标卡阵 / emoji /
    紫靛助手色 / 奶油+赭石 / lorem / 假仪表盘灰条 / 标题缺失 / 图片不足；
  · `deep_audit`：真调上游 `inspect.mjs`（Node + 本机 Chrome/Edge），在 1440/768/390 三宽度
    量标题行数、字体、颜色、留白、边距、动效元素数，并截图——**不是模拟，是上游原脚本**；
  · `brief`：给一次构建的硬约束；只报，不自动改页面；FAIL / WARN 分开，分数可复核。

诚实边界：
  · 真浏览器闸依赖 Node 22+ 与本机 Chrome/Edge；缺了如实 `needs_dependency`，不冒充；
  · 主观陪审/自动修片仍未接；上游 `assets.mjs` 图库取图、`draw.mjs` 方向发牌未接；
  · 上游 `vendor/taste-skill` 原库保留（MIT）；本模块只写自己的规则与适配，不复制其代码。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STATUS = {
    "cap": "taste_guard", "tier": "native", "domain": "creation",
    "ops": ["status", "rules", "audit", "deep_audit", "brief", "where"],
    "upstream": "Leonxlnx/taste-skill (design-taste-frontend v2) · MIT",
    "absorbed": "2026-11-01 · 静态 18 条规则 + 上游 inspect.mjs 真浏览器闸（Node/Chrome）",
    "not_implemented": ["截图陪审/看片修片循环",
                        "assets.mjs 开放图库取图", "draw.mjs 方向发牌库"],
    "not_checked": ["主观评审/评分", "每节构图差异", "首屏“是否像成品”的人判"],
}

# 上游 house rules 的短表；id 用于 audit 读数
RULES = [
    {"id": "headline_lines", "sev": "FAIL", "rule": "标题最多两行（任何宽度）",
     "instead": "先删字，再放宽，最后才缩字号"},
    {"id": "clear_title", "sev": "FAIL", "rule": "首屏必须有一个 h1，且每节有标题",
     "instead": "名字 + 它做什么；活动写日期地点"},
    {"id": "no_eyebrow", "sev": "FAIL", "rule": "标题上方不许小眉标 / 胶囊 / New 标签",
     "instead": "信息写进标题或第一句"},
    {"id": "no_gradient", "sev": "FAIL", "rule": "不许渐变（背景/按钮/文字）；照片压字可加中性 scrim",
     "instead": "平涂，或真实照片"},
    {"id": "no_glass", "sev": "FAIL", "rule": "不许玻璃拟态 / backdrop blur / 浮动胶囊导航",
     "instead": "普通栏：字标 + 少量链接 + 一个动作"},
    {"id": "no_shadow_rest", "sev": "FAIL", "rule": "静止元素不许阴影/发光；只有浮层（菜单/弹窗）可以",
     "instead": "用一层色调差分开表面"},
    {"id": "no_monospace", "sev": "FAIL", "rule": "真代码块之外不许等宽字体",
     "instead": "正文用正文字体；数字对齐用 tabular figures"},
    {"id": "no_index", "sev": "FAIL", "rule": "不许 01/02/03、(001)、Step 2 这类编号装饰",
     "instead": "用位置/大小/文字表示顺序；真有序用 <ol>"},
    {"id": "no_thin_rules", "sev": "FAIL", "rule": "不许发丝线/1px 描边框/网格线/裁切标记",
     "instead": "留白、色调台阶、尺度变化或实心形状"},
    {"id": "no_tiny_caps", "sev": "FAIL", "rule": "不许小字号 + 大写 + 大字距的标签",
     "instead": "句子大小写，可读字号"},
    {"id": "no_icon_cards", "sev": "FAIL", "rule": "不许图标顶着的功能卡阵 / 一排同样的卡片",
     "instead": "按节蓝图，换成真实内容/图/色块"},
    {"id": "no_emoji", "sev": "FAIL", "rule": "不许 emoji / 渐变球 / 装饰形状 / 灰条假仪表盘",
     "instead": "真图、真界面片段，或什么都不放"},
    {"id": "no_assistant_palette", "sev": "FAIL", "rule": "不许紫/靛“AI 助手色”，不许奶油+赭石",
     "instead": "一底一墨一强调，取自题材本身"},
    {"id": "no_accent_word", "sev": "FAIL", "rule": "标题里不许单独变色/斜体/衬线/下划线的“重点词”",
     "instead": "一种字体一种颜色，让字义承担强调"},
    {"id": "max_two_faces", "sev": "WARN", "rule": "最多两种字体（通常一种）",
     "instead": "上游研究：三分之一获奖站只用一种"},
    {"id": "real_images", "sev": "WARN", "rule": "真实图片 ≥4（照片/档案/地图/版画/视频帧；SVG 不算）",
     "instead": "用题材世界的真实图，或为题材画一套平面语言"},
    {"id": "motion_count", "sev": "WARN", "rule": "真动效元素 ≥8（入场/滚动/控件反馈至少三段）",
     "instead": "一个签名动作 + 每节错峰入场 + 控件反馈 + 一张会动的图"},
    {"id": "no_lorem", "sev": "FAIL", "rule": "不许 lorem ipsum / TODO 占位 / “示例文本”",
     "instead": "写完整内容；样例细节可标“待客户确认”"},
]

_PATTERNS = [
    ("no_gradient", "FAIL", re.compile(r"(?:linear|radial|conic)-gradient\s*\(", re.I), "渐变"),
    ("no_glass", "FAIL", re.compile(r"backdrop-(?:filter|blur)|backdrop-filter\s*:", re.I), "玻璃拟态"),
    ("no_shadow_rest", "FAIL", re.compile(r"box-shadow\s*:", re.I), "阴影"),
    ("no_tiny_caps", "FAIL", re.compile(r"text-transform\s*:\s*uppercase", re.I), "大写标签"),
    ("no_lorem", "FAIL", re.compile(r"lorem\s+ipsum|示例文本|TODO", re.I), "占位文本"),
    ("no_index", "FAIL", re.compile(r"(?:^|[>\s])(?:0[1-9]|\(00[1-9]\)|第\s*[一二三四五六七八九]\s*步)", re.M), "编号装饰"),
    ("no_accent_word", "WARN", re.compile(r"<em\b[^>]*>|<i\b[^>]*>", re.I), "强调词"),
]

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_VIOLET = re.compile(r"#(?:6366f1|8b5cf6|a855f7|7c3aed|4f46e5)\b", re.I)
_CREAM = re.compile(r"#(?:f5f5dc|fffdd0|faf0e6|e2725b|b7410e)\b", re.I)


def _strip_code(html: str) -> str:
    return re.sub(r"<(pre|code)[\s\S]*?</\1>", " ", html, flags=re.I)


def _scan(html: str, css: str = "") -> dict:
    raw = str(html or "")
    text = _strip_code(raw)
    low = text.lower()
    findings = []

    def add(rid, sev, evidence):
        rule = next((r for r in RULES if r["id"] == rid), {"rule": rid, "instead": ""})
        findings.append({"id": rid, "sev": sev, "rule": rule["rule"],
                         "instead": rule.get("instead", ""), "evidence": evidence[:160]})

    for rid, sev, rx, label in _PATTERNS:
        m = rx.search(text)
        if m:
            add(rid, sev, "%s：%s" % (label, m.group(0)))
    if _EMOJI.search(text):
        add("no_emoji", "FAIL", "emoji：" + "".join(_EMOJI.findall(text))[:20])
    if _VIOLET.search(raw):
        add("no_assistant_palette", "FAIL", "紫/靛：" + _VIOLET.search(raw).group(0))
    elif _CREAM.search(raw):
        add("no_assistant_palette", "FAIL", "奶油+赭石：" + _CREAM.search(raw).group(0))

    # 等宽：去掉 code/pre 后仍出现 monospace
    if re.search(r"font-family\s*:[^;{}]*monospace", low):
        add("no_monospace", "FAIL", "font-family: monospace")
    # 卡片阵：同一 class 含 card 的 ≥3 个
    cards = re.findall(r'class="[^"]*\b(?:card|feature)\b[^"]*"', text, re.I)
    if len(cards) >= 3:
        add("no_icon_cards", "FAIL", "同类卡片 %d 个" % len(cards))
    # 标题
    h1 = re.findall(r"<h1\b[^>]*>[\s\S]*?</h1>", text, re.I)
    if not h1:
        add("clear_title", "FAIL", "没有 <h1>")
    # 图片
    imgs = re.findall(r"<img\b", text, re.I)
    if len(imgs) < 4:
        add("real_images", "WARN", "<img> %d 个" % len(imgs))
    # 字体种数
    faces = set(re.findall(r"font-family\s*:\s*([^;{}]+)", low))
    if len(faces) > 2:
        add("max_two_faces", "WARN", "font-family 声明 %d 组" % len(faces))
    # 动效粗计
    anim = len(re.findall(r"@keyframes|transition\s*:|animation\s*:", low + "\n" + str(css or "").lower()))
    if anim < 3:
        add("motion_count", "WARN", "动效声明 %d 处" % anim)

    fails = [f for f in findings if f["sev"] == "FAIL"]
    warns = [f for f in findings if f["sev"] == "WARN"]
    score = max(0, min(100, 100 - 8 * len(fails) - 3 * len(warns)))
    return {"ok": not fails, "verdict": "PASS" if not fails else "FAIL",
            "score": score, "fail_n": len(fails), "warn_n": len(warns),
            "findings": findings, "checked": len(RULES),
            "not_checked": STATUS["not_checked"],
            "note": "静态规则闸：渲染项（留白/边距/构图）未量，别把 PASS 当成真浏览器通过"}


def _audit(payload):
    p = payload.get("path") or payload.get("html_file")
    html = payload.get("html") or payload.get("text") or ""
    if p:
        try:
            html = Path(p).read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "status": "read_failed", "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    if not str(html).strip():
        return {"ok": False, "status": "needs_input", "error": "给 html 片段或 path 指向 HTML 文件"}
    # 动效只能在 CSS 里（单扫 HTML 恒报 0 处 = 假红）。同目录 CSS 一并喂给 _scan，
    # 并把「真读到了哪几份」写进回执 —— 读失败不靠猜，回执里看得见。
    css, css_files, css_missed = "", [], []
    if p:
        parts = []
        for f in sorted(Path(p).resolve().parent.glob("*.css")):
            try:
                parts.append(f.read_text(encoding="utf-8", errors="replace"))
                css_files.append(f.name)
            except OSError as e:
                css_missed.append("%s(%s)" % (f.name, type(e).__name__))
        css = "\n".join(parts)
    r = _scan(html, css)
    r["css_scanned"] = css_files
    if css_missed:
        r["css_missed"] = css_missed
    r["cap"] = "taste_guard"
    return r


def _brief(payload):
    sector = str(payload.get("sector") or "通用").strip()
    tone = str(payload.get("tone") or "quiet").strip()
    return {"ok": True, "cap": "taste_guard", "sector": sector, "tone": tone,
            "constraints": {
                "direction": "先定一个能承载题材自身材料的方向，再谈样式；方向不熟才对",
                "idea": "一句话：这个题材的____，变成方向要求的____（换成本地题材就说不通才算专属）",
                "colors": "一底一墨一强调；强调只给动作+最多一处；正文用满墨，不用灰",
                "type": "两到三档字号：一个很大、一个小、中间没有；标题两行内；最多两种字体",
                "frame": "一套等边距；左右边距相等；每节有标题；相邻节构图不同",
                "images": "真实图片 ≥4（照片/档案/地图/版画/视频帧）；SVG 不算；一张主导图胜过六张小图",
                "motion": "一个签名动作 + 每节 60–90ms 错峰入场 + 控件反馈 + 一张会动的图；reduced-motion 保内容",
                "no_slop": [r["rule"] for r in RULES if r["sev"] == "FAIL"],
            },
            "gate": "写完后用 op=audit 静态扫；渲染项要真浏览器（本机未接 Node inspector，不冒充）",
            "source": STATUS["upstream"]}


def _node_info() -> dict:
    for cand in (shutil.which("node"), str(ROOT / "vendor" / "node" / "node.exe"),
                 str(ROOT.parent / "vendor" / "node" / "node.exe")):
        if cand and Path(cand).is_file():
            try:
                v = subprocess.run([cand, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
                return {"ok": True, "path": cand, "version": v}
            except Exception:  # noqa: BLE001
                return {"ok": True, "path": cand, "version": "?"}
    return {"ok": False, "path": "", "version": ""}


def _inspector_path() -> str:
    for base in (ROOT, ROOT.parent):
        p = base / "vendor" / "taste-skill" / "skills" / "taste-skill" / "scripts" / "inspect.mjs"
        if p.is_file():
            return str(p)
    return ""


def _browser_info() -> dict:
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if Path(p).is_file():
            return {"ok": True, "path": p}
    return {"ok": False, "path": ""}


def _deep_ready() -> dict:
    node = _node_info()
    ins = _inspector_path()
    br = _browser_info()
    return {"ok": bool(node["ok"] and ins and br["ok"]), "node": node,
            "inspector": ins, "browser": br,
            "hint": "缺 Node 22+/Chrome/Edge 或 vendor/taste-skill 原库"}


def _deep_audit(payload):
    ready = _deep_ready()
    if not ready["ok"]:
        return {"ok": False, "status": "needs_dependency", **ready,
                "how_to_fix": "装 Node 22+，并把上游原库放到 vendor/taste-skill/；本机 Chrome/Edge 已检测"}
    target = payload.get("path") or payload.get("url") or payload.get("target")
    if not target:
        return {"ok": False, "status": "needs_input", "error": "给 path 指向本地 HTML 或 url"}
    out = (ROOT / "outputs" / "taste-guard" / ("inspect-" + time.strftime("%m%d-%H%M%S"))).resolve()
    try:
        out.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "not_writable", "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}
    cmd = [ready["node"]["path"], ready["inspector"], str(target), "--json", "--out", str(out)]
    if payload.get("widths"):
        cmd += ["--widths", str(payload["widths"])]
    if payload.get("app"):
        cmd += ["--app"]
    if payload.get("film"):
        cmd += ["--film"]
    if payload.get("allow"):
        cmd += ["--allow", str(payload["allow"])]
    try:
        t0 = time.time()
        # Chrome/Node 的临时目录：本机 %TEMP% 对 Python 子进程常 EPERM；用 ASCII 路径并显式喂给上游
        tmpdir = ROOT / "outputs" / "taste-guard" / "_tmp"
        try:
            tmpdir.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            tmpdir = ROOT / "outputs" / "taste-guard" / "_tmp"
            tmpdir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["TEMP"] = str(tmpdir)
        env["TMP"] = str(tmpdir)
        env["TASTE_SKILL_TMP"] = str(tmpdir)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=int(payload.get("timeout") or 600), cwd=str(ROOT), env=env)
        elapsed = round(time.time() - t0, 2)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "out": str(out), "cmd": cmd[:3]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "detail": "%s: %s" % (type(e).__name__, str(e)[:160])}
    report_path = out / "report.json"
    report = {}
    try:
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        report = {}
    findings = report.get("findings") or []
    fails = [f for f in findings if f.get("level") == "FAIL"]
    warns = [f for f in findings if f.get("level") == "WARN"]
    shots = []
    for im in report.get("images") or []:
        for k in ("fold",):
            if im.get(k):
                shots.append(im[k])
        for p in im.get("pages") or []:
            shots.append(p)
    score = max(0, min(100, 100 - 8 * len(fails) - 3 * len(warns)))
    ids = sorted({f.get("id") for f in fails if f.get("id")})
    return {"ok": r.returncode == 0, "status": "PASS" if r.returncode == 0 else "FAIL",
            "verdict": "PASS" if r.returncode == 0 else "FAIL",
            "score": score, "fail_n": len(fails), "warn_n": len(warns),
            "fail_ids": ids, "findings": findings[:80], "screenshots": shots[:12],
            "report": str(report_path), "out": str(out), "elapsed_s": elapsed,
            "node": ready["node"]["version"], "inspector": ready["inspector"],
            "browser": ready["browser"]["path"], "exit": r.returncode,
            "stdout_tail": (r.stdout or "")[-400:], "stderr_tail": (r.stderr or "")[-400:],
            "note": "上游 inspect.mjs 真浏览器量；FAIL 要改到 0 才算过，PASS 不等于好看"}


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        return {"ok": True, "op": "status", **STATUS, "deep": _deep_ready()}
    if op == "where":
        return {"ok": True, "op": "where", **STATUS,
                "module": "gbt_allinone/tentacle/taste_guard.py",
                "example": "run_task('taste_guard', {'op':'audit','path':'ui/index.html'})"}
    if op == "rules":
        return {"ok": True, "op": "rules", "count": len(RULES), "rules": RULES,
                "not_checked": STATUS["not_checked"]}
    if op == "audit":
        return _audit(kw)
    if op in ("deep_audit", "inspect"):
        return _deep_audit(kw)
    if op == "brief":
        return _brief(kw)
    return {"ok": False, "op": op, "status": "unknown_op", "error": "未知 op：%s" % op,
            "available": STATUS["ops"], "fail_closed": True}
