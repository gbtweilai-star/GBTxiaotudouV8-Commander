#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**技能安全审查器**（把 `skill-vetter` 那套规程变成跑得动的判据）。

规程出处：`~/.openclaw-autoclaw/skills/skill-vetter/SKILL.md`（v1.0.0，138 行，已通读）。
它定的是「装任何技能之前必须先审」：**Step1 来源 → Step2 通读全部文件查红旗 →
Step3 权限面 → Step4 风险分级 → 出报告**。本器把那一步机器化。

🔴 本器最重要的一条不是"能查什么"，而是"**查不了的时候敢说查不了**"：
   `skill-vetter` 的 Step 2 写着 **Code Review (MANDATORY)** —— **没有代码就无法执行**。
   所以当"源不在盘上"时，本器判 **⛔ 无法审查（缺源）**，
   **绝不**拿"本地有个同名/同类技能"冒充审过，也绝不编一个 `✅ SAFE` 出来。
   （这条正是本会话一直在打的那种假账：**没跑成 ≠ 通过**。）

用法：
  python tools/codex-scripts/skill-vet.py --skill-dir <路径> [--skill-dir <路径> …]
  python tools/codex-scripts/skill-vet.py --name <技能名>        # 在已知的 5 个根里找同名
  python tools/codex-scripts/skill-vet.py --catalog <清单文件>   # 每行一个候选名（可带说明）
  python tools/codex-scripts/skill-vet.py --all-managed          # 扫全部托管技能（慢）
  python tools/codex-scripts/skill-vet.py … --json --out <路径>   # 机读 + 落盘
退出码：0 = 全部可判且无 HIGH/EXTREME；1 = 有 HIGH/EXTREME 或无法审查的；2 = 用法错。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()

# 🔴 2026-09-25 改：**根不许再手写**。
#    起因是一次实打实的自打脸：我手写的根列表里有 3 个盘上并不存在的路径，
#    同时又**漏掉**了 5 个真实存在的根（`~/.codex/skills`、仓内 `.autohand/.codebuddy/`
#    `.windsurf/skills`、仓内 `.dsh/skills`）。于是"审过了"这句话在**盘点这一步**就是假的 ——
#    下游再认真也是审了个子集。现在：种子（下面这 7 条）只负责"这几个一定要包含"，
#    真实根由 `discover_roots()` **自动扫出来**，并且每个根都要能报出"它有 N 个技能"。
_SEED_ROOTS = [
    HOME / ".openclaw-autoclaw" / "skills",
    HOME / ".agents" / "skills",
    HOME / ".claude" / "skills",
    HOME / ".openclaw-autoclaw" / "skill-workshop",
    HOME / ".openclaw-autoclaw" / "plugin-skills",
    ROOT / "skills",
    ROOT / "审美相关skill" / "skills",
]


def discover_roots() -> list:
    """把所有真实存在的技能根扫出来（不靠手写清单）。

    只做**有界**扫描：家目录与仓根**各下一层**找 `*/skills`，再加仓根下一层的 `*/*/skills`。
    判定标准只有一条：这个目录下**至少有一个子目录带 SKILL.md** ——
    否则它只是个同名空壳，不算技能根（但仍会被列出来，注明"空壳"）。
    """
    cands: list = []
    for base in (HOME, ROOT):
        try:
            kids = sorted([p for p in base.iterdir() if p.is_dir()])
        except Exception:  # noqa: BLE001
            kids = []
        for kid in kids:
            cands.append(kid / "skills")
            # 仓内一层深（例如 审美相关skill/skills 这种中文目录名）
            if base == ROOT:
                try:
                    for gk in sorted([p for p in kid.iterdir() if p.is_dir()]):
                        cands.append(gk / "skills")
                except Exception:  # noqa: BLE001
                    pass
    cands.extend(_SEED_ROOTS)

    out, seen = [], set()
    for c in cands:
        try:
            key = str(c.resolve()).lower()
        except Exception:  # noqa: BLE001
            key = str(c).lower()
        if key in seen or not c.is_dir():
            continue
        seen.add(key)
        out.append(c)
    return out


def root_census(root: Path) -> dict:
    """一个根的现读读数：技能目录数 / 带 SKILL.md 的 / 可执行件数。"""
    skills = sorted([p for p in root.iterdir() if p.is_dir()]) if root.is_dir() else []
    with_md = [p for p in skills if (p / "SKILL.md").is_file()]
    n_exec = 0
    for p in skills:
        for f in p.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".py", ".js", ".mjs", ".cjs", ".ts", ".sh",
                                                    ".ps1", ".bat", ".cmd", ".rb", ".pl"}:
                n_exec += 1
    return {"root": str(root), "dirs": len(skills), "skill_md": len(with_md), "exec_files": n_exec}


SKILL_ROOTS = discover_roots()
TEXT_EXT = {".md", ".py", ".js", ".cjs", ".mjs", ".ts", ".sh", ".ps1", ".bat",
            ".cmd", ".json", ".yml", ".yaml", ".toml", ".txt", ".html"}
MAX_FILE_BYTES = 400_000
MAX_FILES = 400

# ── 红旗表：直接照 `skill-vetter` Step 2 那份清单落成正则；每条带"为什么危险" ──
RED_FLAGS = [
    ("外网抓取/下载", r"\b(curl|wget|Invoke-WebRequest|iwr)\b", "Step2: curl/wget to unknown URLs"),
    ("疑似外传数据", r"(requests\.(post|put)|urllib\.request\.urlopen|fetch\(|axios\.(post|put)|Invoke-RestMethod)",
     "Step2: sends data to external servers"),
    ("索要凭据/密钥", r"(API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|凭据|密钥|私钥)\s*[:=]",
     "Step2: requests credentials/tokens/API keys"),
    ("读敏感家目录", r"(\.ssh|\.aws|[\\/]\.config[\\/]|\.gnupg|\.kube|id_rsa|\.netrc)",
     "Step2: reads ~/.ssh ~/.aws ~/.config without clear reason"),
    ("碰长期记忆/身份件", r"(MEMORY\.md|USER\.md|SOUL\.md|IDENTITY\.md|AGENTS\.md)",
     "Step2: accesses MEMORY.md/USER.md/SOUL.md/IDENTITY.md"),
    ("base64 解码", r"(base64\s+-d|b64decode|atob\(|FromBase64String)",
     "Step2: uses base64 decode on anything"),
    ("eval/exec 外部输入", r"(?<![\w.])(eval|exec)\s*\(", "Step2: uses eval()/exec() with external input"),
    ("改工作区外的系统文件", r"(/etc/|/usr/|C:\\\\Windows|HKEY_LOCAL_MACHINE|reg\s+add)",
     "Step2: modifies system files outside workspace"),
    ("装包（未列清）", r"(pip\s+install|npm\s+i(nstall)?\s|apt(-get)?\s+install|choco\s+install|winget\s+install)",
     "Step2: installs packages without listing them"),
    ("直连 IP 而非域名", r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "Step2: network calls to IPs instead of domains"),
    ("混淆/压缩代码", r"(\.min\.js|eval\(atob|\\\\x[0-9a-f]{2}\\\\x[0-9a-f]{2})", "Step2: obfuscated code"),
    ("提权", r"(sudo\s|runas\s|管理员权限|以管理员身份)", "Step2: requests elevated/sudo permissions"),
    ("碰浏览器 cookie/会话", r"(Cookies|Login Data|cookies\.sqlite|Local State)", "Step2: accesses browser cookies/sessions"),
    ("碰凭据文件", r"(credentials(\.json|\.yaml)?|\.pem\b|\.p12\b|known_hosts)", "Step2: touches credential files"),
    ("破坏性删除", r"(rm\s+-rf|Remove-Item\s+.*-Recurse\s+.*-Force|del\s+/f|format\s+[a-z]:)",
     "RUNTIME: destructive delete"),
    ("外传通道（webhook/隧道/暂存盘）", r"(webhook|ngrok|pastebin|transfer\.sh|0x0\.st|discord\.com/api/webhooks)",
     "RUNTIME: exfiltration channel"),
]
RE_FLAGS = [(n, re.compile(p, re.I), why) for n, p, why in RED_FLAGS]
# 危险等级的判据（照 Step 4 的表）：命中这些 ⇒ HIGH；只碰网/写盘 ⇒ MEDIUM；其余 LOW
HIGH_SET = {"索要凭据/密钥", "读敏感家目录", "碰长期记忆/身份件", "碰凭据文件",
            "碰浏览器 cookie/会话", "提权", "混淆/压缩代码", "外传通道（webhook/隧道/暂存盘）",
            "疑似外传数据", "eval/exec 外部输入"}
MEDIUM_SET = {"外网抓取/下载", "改工作区外的系统文件", "装包（未列清）", "破坏性删除", "直连 IP 而非域名"}


def _files(skill_dir: Path) -> list:
    out = []
    if not skill_dir.is_dir():
        return out
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in TEXT_EXT:
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        out.append(p)
        if len(out) >= MAX_FILES:
            break
    return out


def _has_frontmatter(text: str) -> bool:
    return bool(re.match(r"^---\s*\n(.*?)\n---\s*", text, re.S))


DOC_EXT = {".md", ".txt", ".html"}
# 🔴 第四类假阳性（跑真数据才发现的）：**否定句**。
#    `alchemy-mcp` 里那句是「**Don't** bypass the MCP server with raw curl」——
#    它是在**禁止** curl，而我的规则把它读成"外网抓取"。
#    ⇒ 命中行里匹配点**之前**若出现否定词，标记 `negated`：**照旧列出来**（是线索），
#      但**不参与风险分级**。通用否定检测很难，这里只认最直白的那几个词，宁可漏判也不误判等级。
NEG_CUES = re.compile(r"(don'?t|do\s+not|never|avoid|instead\s+of|不许|禁止|绝不|不要|别用|不得)", re.I)

# 🔴 第五类假阳性（2026-09-25 全量审 1268 件时发现，而且撞在**最规矩**的那个技能上）：
#    `turnstile-spin`（Cloudflare 官方 skills 仓里的 Turnstile 技能）被判 🔴 HIGH，理由是
#    「破坏性删除」等命中。逐字读过之后：`trap 'rm -rf "$TEMP_DIR"' EXIT` 里
#    `TEMP_DIR` 是它自己 `mktemp -d` 出来的 —— 那是在**清自己的临时目录**，不是删用户的东西。
#    ⇒ 规则只会看"这个词出现了"，分不清「删自己的临时目录」与「删用户的目录」。
#      与本仓那句「提到 ≠ 用了」同族，只是这次栽在**最该被表扬**的写法上。
#    处理方式与「否定句」一致：**照旧列出来**（是线索），标 `defensive`，**不参与分级**。
#
# ⚠️ 自纠（**先把前提验掉再写规则**，这次救了半条规则下来）：我原本还打算加一条"洗凭据"
#    （`unset CLOUDFLARE_API_TOKEN`）的防御性规则。查真数据后发现它**根本不会触发** ——
#    凭据规则的形状是 `(API_KEY|TOKEN|…)\s*[:=]`，而 `unset A B` 既没有 `:` 也没有 `=`。
#    ⇒ 凭据那一侧的防御性正则**没加**：加了也永远不触发，那就是一条**死判据**
#      （本仓自己的 `audit-dead-judgments.py` 专抓这种东西，我不给自己添一条）。
#    真正让 `turnstile-spin` 命中凭据规则的是脚本里的 `TOKEN:` / `TOKEN=` **用法占位文本** ——
#    机器分不清它与"真读凭据"，所以按**线索**处理、由人看，不假装机器判得了。
_DEFENSIVE_DEL = re.compile(r"(trap\b[^\n]*rm\s+-rf|rm\s+-rf\s+[\"']?\$\{?(TEMP|TMP|TMPDIR|temp)|mktemp\s+-d)", re.I)
_DEFENSIVE_BY_RULE = {
    "破坏性删除": _DEFENSIVE_DEL,
}


def vet(skill_dir: Path, label: str = "") -> dict:
    name = label or skill_dir.name
    if not skill_dir.is_dir():
        return {"skill": name, "source": str(skill_dir), "verdict": "⛔ 无法审查（缺源）",
                "risk": "UNKNOWN", "flags": [], "files_reviewed": 0,
                "note": "skill-vetter Step2 是 **MANDATORY 通读全部文件** —— 目录不在盘上就无法执行；"
                        "**不拿同名/同类冒充，也不编 ✅ SAFE**。"}
    files = _files(skill_dir)
    flags, per_file = [], {}
    fm_ok, total = False, 0
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total += len(text)
        if p.name == "SKILL.md" and _has_frontmatter(text):
            fm_ok = True
        exec_like = p.suffix.lower() not in DOC_EXT
        # 🔴 2026-09-25 修**第三类**假阳性（同样是跑真数据才发现的）：
        #    6 处「改工作区外的系统文件」全是 **shebang 行**（`#!/usr/bin/env python3`）——
        #    那是**解释器指令**，不是"在改 /usr"。首跑据此把两个技能抬到 MEDIUM。
        #    ⇒ 判之前先把 shebang 行剥掉（一行正则），再扫。
        scan_text = re.sub(r"(?m)^#!.*$", "", text)
        for label_, rx, why in RE_FLAGS:
            for m in rx.finditer(scan_text):
                ln = scan_text[:m.start()].count("\n") + 1
                # 匹配点所在那一行的**前半句**有没有否定词 ⇒ 这一处是"禁止"而不是"在做"
                line_start = scan_text.rfind("\n", 0, m.start()) + 1
                line_end = scan_text.find("\n", m.start())
                line_text = scan_text[line_start: line_end if line_end != -1 else len(scan_text)]
                negated = bool(NEG_CUES.search(scan_text[line_start:m.start()]))
                _drule = _DEFENSIVE_BY_RULE.get(label_)
                defensive = bool(_drule and _drule.search(line_text))
                flags.append({"rule": label_, "why": why, "file": str(p.relative_to(skill_dir)),
                              "line": ln, "hit": m.group(0)[:60], "exec": exec_like,
                              "negated": negated, "defensive": defensive})
        per_file[str(p.relative_to(skill_dir))] = len(text)
    # 🔴 2026-09-25 修我自己的假阳性（**首跑就撞上，而且是撞在 skill-vetter 自己身上**）：
    #    `skill-vetter/SKILL.md` **列举**了全部红旗（curl / ~/.ssh / eval / base64…），
    #    第一版据此把它判成 🔴 HIGH —— 可它一个字都没执行，那是在**定义**红旗。
    #    这就是本仓 FR-1 同族「**提到 ≠ 用了**」，只不过这次犯错的是我这个审计器。
    #    ⇒ 风险分级**只采信可执行文件里的命中**（.py/.js/.sh/.ps1…）；
    #      文档里的命中**照旧列出来**（是线索），但标 `exec:false` 且**不单独抬高等级**。
    exec_names = {f["rule"] for f in flags if f["exec"] and not f.get("negated") and not f.get("defensive")}
    doc_names = {f["rule"] for f in flags if (not f["exec"]) and not f.get("negated") and not f.get("defensive")}
    neg_names = {f["rule"] for f in flags if f.get("negated")}
    def_names = {f["rule"] for f in flags if f.get("defensive")}
    if exec_names & HIGH_SET:
        risk, verdict = "🔴 HIGH", "⚠️ 安装需人工批准（先逐条看红旗）+ 逐条判明"
    elif exec_names & MEDIUM_SET:
        risk, verdict = "🟡 MEDIUM", "⚠️ 需完整代码复核后再定"
    elif doc_names & (HIGH_SET | MEDIUM_SET):
        risk, verdict = "🟡 MEDIUM", ("⚠️ 只见**文档性**命中（多半是在**列举/解释**这些手法）—— "
                                     "不单独判高风险，但要看一眼是不是在教怎么干")
    else:
        risk, verdict = "🟢 LOW", "✅ 可安装（仍建议看一眼命中项）"
    return {"skill": name, "source": str(skill_dir), "verdict": verdict, "risk": risk,
            "files_reviewed": len(files), "bytes_reviewed": total, "frontmatter": fm_ok,
            "flags": flags, "flag_rules": sorted(exec_names | doc_names | neg_names | def_names),
            "exec_flag_rules": sorted(exec_names), "doc_flag_rules": sorted(doc_names),
            "negated_flag_rules": sorted(neg_names), "defensive_flag_rules": sorted(def_names),
            "verdict_flags": sorted(exec_names | doc_names),
            "note": "" if files else "目录在、但**一个可读文本文件都没有** ⇒ 等于没读到代码，按无法判定处理"}


def locate(name: str) -> Path | None:
    """在已知的根里找同名技能目录（找不到就返回 None —— 由调用方判『缺源』）。"""
    for r in SKILL_ROOTS:
        p = r / name
        if p.is_dir():
            return p
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="技能安全审查（只读；缺源则如实判无法审查）")
    ap.add_argument("--skill-dir", action="append", default=[])
    ap.add_argument("--name", action="append", default=[])
    ap.add_argument("--catalog", default="")
    ap.add_argument("--all-managed", action="store_true")
    ap.add_argument("--all-roots", action="store_true",
                    help="扫**所有自动发现的根**（全量），并打印按根的覆盖率读数")
    ap.add_argument("--roots", action="store_true", help="只打印根清单与按根普查，不审技能")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)

    roots = discover_roots()
    if a.roots:
        census = [root_census(r) for r in roots]
        rep = {"ok": True, "readonly": True, "mode": "roots", "roots": [str(r) for r in roots],
               "census": census}
        if a.json:
            text = json.dumps(rep, ensure_ascii=False, indent=2)
        else:
            L = ["═══ 技能根清单（自动发现，不手写）═══"]
            tot_d = tot_md = tot_e = 0
            for c in census:
                L.append("  %-52s 目录 %3d · SKILL.md %3d · 可执行件 %4d"
                         % (c["root"], c["dirs"], c["skill_md"], c["exec_files"]))
                tot_d += c["dirs"]
                tot_md += c["skill_md"]
                tot_e += c["exec_files"]
            L.append("  " + "─" * 86)
            L.append("  合计：根 %d 个 · 技能目录 %d · 带 SKILL.md %d · 可执行件 %d"
                     % (len(census), tot_d, tot_md, tot_e))
            text = "\n".join(L)
        print(text)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(text, encoding="utf-8")
            print("\n已写", a.out)
        return 0

    targets: list = []
    for d in a.skill_dir:
        targets.append((Path(d).name, Path(d)))
    for n in a.name:
        p = locate(n)
        targets.append((n, p))                       # p 可能是 None ⇒ 缺源
    if a.catalog:
        for line in Path(a.catalog).read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            nm = s.split("|")[0].strip()
            if nm:
                targets.append((nm, locate(nm)))
    if a.all_managed:
        # ⚠️ 不许用 `SKILL_ROOTS[0]`：根列表现在是**自动发现**的，第 0 个会随盘上情况变
        #    （实测已经变成了 `~/.omp/skills`）⇒ `--all-managed` 会悄悄改指到别的根。
        #    "托管根"是**语义**，必须写死成那条语义路径。
        base = HOME / ".openclaw-autoclaw" / "skills"
        if not base.is_dir():
            print("托管根不在：%s" % base, file=sys.stderr)
            return 2
        for p in sorted(base.iterdir()):
            if p.is_dir():
                targets.append((p.name, p))
    roots_touched: list = []
    if a.all_roots:
        census = []
        for r in roots:
            if not r.is_dir():
                continue
            c = root_census(r)
            if c["skill_md"] == 0:
                census.append(dict(c, empty_shell=True))   # 同名空壳：如实列出，不算技能根
                continue
            census.append(dict(c, empty_shell=False))
            roots_touched.append(str(r))
            for p in sorted(r.iterdir()):
                if p.is_dir() and (p / "SKILL.md").is_file():
                    targets.append(("%s@%s" % (p.name, r.name), p))
    if not targets:
        print("没给审查目标：用 --skill-dir / --name / --catalog / --all-managed / --all-roots",
              file=sys.stderr)
        return 2

    rows = []
    for nm, p in targets:
        rows.append(vet(p, nm) if p is not None else vet(Path("__absent__") / nm, nm))

    unjudgeable = [r for r in rows if r["risk"] == "UNKNOWN" or not r["files_reviewed"]]
    risky = [r for r in rows if r["risk"] in ("🔴 HIGH", "⛔ EXTREME")]
    with_exec = [r for r in rows if r.get("exec_flag_rules")]
    _hist: dict = {}
    for r in rows:
        _hist[r["risk"]] = _hist.get(r["risk"], 0) + 1
    rep = {"ok": True, "readonly": True, "targets": len(rows), "rows": rows,
           "unjudgeable": [r["skill"] for r in unjudgeable],
           "high_risk": [r["skill"] for r in risky],
           "exec_hits": [r["skill"] for r in with_exec],
           "risk_histogram": _hist,
           "roots": [str(r) for r in roots],
           "roots_scanned": roots_touched,
           "note": ("照 skill-vetter v1.0.0 的 Step1-4 走；**缺源/读不到文件 ⇒ 判『无法审查』，"
                    "不许编 ✅ SAFE**。命中项是**线索不是结论** —— 最后一步仍是人看。")}
    if a.json:
        text = json.dumps(rep, ensure_ascii=False, indent=2)
    elif a.all_roots:
        # 全量模式：不逐条刷屏，只打**覆盖率 + 风险分布 + 有可执行命中的名字**
        L = ["═══ 技能全量安全审查（对照 skill-vetter v1.0.0）═══",
             "根 %d 个（自动发现）· 在场技能 %d（按 SKILL.md 计）· 本次实审 %d"
             % (len(roots_touched), sum(c["skill_md"] for c in census if not c.get("empty_shell")),
                len(rows)),
             "风险分布：" + " · ".join("%s %d" % (k, v) for k, v in sorted(_hist.items())),
             "**无法审查 %d · 高风险 %d · 有可执行命中 %d**" % (len(unjudgeable), len(risky), len(with_exec)),
             ""]
        for c in census:
            if c.get("empty_shell"):
                L.append("  ⚪ %-50s 空壳（无 SKILL.md）目录 %d" % (c["root"], c["dirs"]))
            else:
                L.append("  · %-50s 在场 %3d · 可执行件 %4d"
                         % (c["root"], c["skill_md"], c["exec_files"]))
        if risky:
            L.append("")
            L.append("🔴 高风险（人必须先看）：")
            for r in risky:
                L.append("   · %s ← %s" % (r["skill"], r["source"]))
        if with_exec:
            L.append("")
            L.append("⚠ 有**可执行**命中（不是文档里的举例）：")
            for r in with_exec:
                L.append("   · %-44s %s" % (r["skill"], " / ".join(r["exec_flag_rules"])))
        if unjudgeable:
            L.append("")
            L.append("⛔ 无法审查（缺源/读不到）：%d 个 —— %s" % (len(unjudgeable), "、".join(unjudgeable[:12])))
        L.append("─" * 78)
        L.append("边界：%s" % rep["note"])
        text = "\n".join(L)
    else:
        L = ["═══ 技能安全审查（对照 skill-vetter v1.0.0）═══",
             "目标 %d 个 · 高风险 %d · **无法审查 %d**" % (len(rows), len(risky), len(unjudgeable)), ""]
        for r in rows:
            L.append("─" * 78)
            L.append("技能：%s" % r["skill"])
            L.append("来源：%s" % r["source"])
            L.append("读过：%d 个文件 / %d 字节%s" % (r["files_reviewed"], r.get("bytes_reviewed", 0),
                                              " ｜ frontmatter: %s" % r.get("frontmatter")
                                              if r["files_reviewed"] else ""))
            L.append("风险：%s" % r["risk"])
            L.append("结论：%s" % r["verdict"])
            if r["flags"]:
                _ex = len([f for f in r["flags"] if f["exec"] and not f.get("negated") and not f.get("defensive")])
                _dc = len([f for f in r["flags"] if not f["exec"] and not f.get("negated") and not f.get("defensive")])
                _ng = len([f for f in r["flags"] if f.get("negated")])
                _df = len([f for f in r["flags"] if f.get("defensive")])
                L.append("红旗命中 %d 处（可执行 %d / 文档 %d / **否定句 %d · 防御性 %d（后两类不参与分级）**）："
                         % (len(r["flags"]), _ex, _dc, _ng, _df))
                for f in sorted(r["flags"], key=lambda x: (x.get("negated", False) or x.get("defensive", False),
                                                           not x["exec"], x["file"]))[:8]:
                    _tag = ("否定句" if f.get("negated") else
                            ("防御性" if f.get("defensive") else ("" if f["exec"] else "文档")))
                    L.append("   · [%s]%s %s:%s  `%s`"
                             % (f["rule"], ("(%s)" % _tag) if _tag else "", f["file"], f["line"], f["hit"]))
                if len(r["flags"]) > 8:
                    L.append("   · …（共 %d 处，见 --json）" % len(r["flags"]))
            if r.get("note"):
                L.append("⚠ %s" % r["note"])
        L.append("─" * 78)
        L.append("边界：%s" % rep["note"])
        text = "\n".join(L)
    print(text)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text((text if not a.json else json.dumps(rep, ensure_ascii=False, indent=2)),
                               encoding="utf-8")
        print("\n已写", a.out)
    return 1 if (unjudgeable or risky) else 0


if __name__ == "__main__":
    raise SystemExit(main())
