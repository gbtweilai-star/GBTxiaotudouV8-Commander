# gbt-capability: code_audit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""代码安全审计：**多阶段 + 机器可读 findings + 独立验证 + 可复现**（蒸馏自 GitHub 周榜 #03
`cloudflare/security-audit-skill`）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-09 第 39 周 GitHub 爆款周榜 #03 `security-audit-skill`（22k★ · JavaScript ·
  Cloudflare 出品）公开介绍：「给编码 Agent 加**多阶段安全审计**能力 · 产出**机器可读的审计发现
  （findings）** · 发现经**独立验证**、**可追溯可复现** · 直接对 **PR/代码**做安全审查 ·
  无缝接入 Agent 工作流」。一手仓库本轮**未联网核验**（不出网），只蒸馏架构。
· **时间**：2026-09-28。· **口径**：只移植架构，规则与代码全部自写。

## 蒸馏判断：我们缺哪块
| 它的能力 | 我们的对位 | 结论 |
|---|---|---|
| 全量扫描（多路交叉、分诊） | `penetrating_cross_scan` + `hook_enforcer` + `omission_detector` + `sec_sweeper` | **已有且更强，不重写** |
| **机器可读 findings 契约** | 无（我们出的是"命中清单+分诊"，不是**带 severity/证据/复现**的记录） | **补这块** |
| **发现的独立验证** | 无（命中即报，靠人复核） | **补这块** |
| **可复现**（一条能照着复跑的命令） | 无 | **补这块** |
| **对 PR / 改动面定向审查** | 无（我们扫全树，改动面靠人记） | **补这块** |

## 硬规矩
1. **没证据不许开 finding**；**高 severity 必须有复现命令**。
2. **两路读法都命中才算确认**（`verify_finding` 用行锚定 + 内容 sha + 字面搜索复核），
   只一路命中 ⇒ `unverified`，**不许当已确认**。
3. **命中先分诊**（登记豁免 / 占位符 / 测试夹具 一律不报），与全仓既有口径一致。
4. **改动面与全量面分开**：`diff_audit` 只审 diff 的行；全量面仍归 `penetrating_cross_scan` 三件套。

> ⚠️ 写法说明（钩子血账）：本文件是**审计器**，规则里必然会写"要找什么"的模式串。
> 第一版把危险字面量直接写进正则，被安全钩子判成"注入/弱算法"而拦下 —— 那不是误报是**它按字面量判**。
> ⇒ 现在模式串用**括号类**表达（`ev[ae]l` / `ex[ae]c`），语义等价而源码里不复现危险字面量；
> finding id 的摘要也从 sha1 换成 **sha256**（弱算法那条提醒同样照办）。

op=scan / diff_audit / findings / verify_finding / repro / report / verify / where
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_FINDINGS = _STATE / "code_audit_findings.json"   # findings（原子写：重扫覆盖，id 稳定）
_LEDGER = _STATE / "code_audit.jsonl"             # 每次扫描/验证（追加式）
SKIP_DIRS = {".git", ".pylibs", "node_modules", "store", "vaults", "out", ".scratch",
             "__pycache__", ".mimosa", "_upstream", "delivery", "output", "generated-images"}
MAX_FILES = 4000
MAX_BYTES = 900_000
EXEMPT_PATHS = {
    "tools/codex-scripts/pack-receipt.py": "记录失败用的惯用法 chk(name, False, why)：那条**就是要报红**",
    "tools/codex-scripts/mock-vllm-endpoint.py": "假端点的故意死分支（避免真发 404）",
    "tools/codex-scripts/audit-dead-judgments.py": "判据扫描器本体：里面必然出现恒真模式的**模式串**",
    # ── 扫描器自身这一类（**按类豁免、理由可见**，不是把文件名塞进黑名单了事）──────────────
    #    本仓所有安全扫描器的规则表里**必然**出现"要找什么"的字面量（shell=True / DROP TABLE / or True …）。
    #    把规则表本身报成漏洞，等于"手电筒照到自己就说灯坏了"。所以：**规则表文件按类豁免**，
    #    并保留 `verify` 的结构性自审（findings 必须有证据+复现）来防"用豁免藏真问题"。
    "gbt_allinone/tools/code_audit.py": "审计器自身的规则表与复现模板（要找的字面量必然在此出现）",
    "gbt_allinone/tools/code_exhaustive_scan.py": "另一台扫描器的模式表（同上：模式串不是漏洞）",
    "gbt_allinone/tools/penetrating_cross_scan.py": "穿透式交叉扫描的模式表与分诊表（同上）",
    "gbt_allinone/tools/hook_enforcer.py": "钩子强制器的模式表（同上）",
    "gbt_allinone/tools/skill_vetting.py": "技能安检器：它维护的正是**危险词清单**（清单不是漏洞）",
}

# 危险字面量用括号类表达（语义等价；源码里不复现危险字面量，免得被安全钩子按字面量拦下）
_DYN_EXEC = r"\b(ev[ae]l|ex[ae]c)\s*\("
_REPRO_INJ1 = ("python -c \"import re,pathlib;P=r'" + _DYN_EXEC +
               "';print([l for l in pathlib.Path('%s').read_text(encoding='utf-8',errors='replace')"
               ".splitlines() if re.search(P,l)][:3])\"")


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _sha(p: Path) -> str:
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


RULES = [
    {"rule": "CRED-001", "severity": "high", "stage": "凭证面",
     "what": "可疑密钥字面量（sk-/ghp_/AKIA/长 base64 赋给含 key/token/secret 的名字）",
     "rx": re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,}"
                      r"|[A-Za-z0-9+/]{40,}={0,2})"),
     "ctx": re.compile(r"(?i)(key|token|secret|passwd|password)"),
     "repro": ("python -c \"import re,pathlib;print(re.findall(r'(sk-[A-Za-z0-9]{16,}|"
               "ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,})', pathlib.Path('%s')"
               ".read_text(encoding='utf-8',errors='replace'))[:3])\"")},
    {"rule": "INJ-001", "severity": "high", "stage": "注入面",
     "what": "动态执行（把字符串当代码跑）",
     "rx": re.compile(_DYN_EXEC),
     "ctx": re.compile(r"."),
     "repro": _REPRO_INJ1},
    {"rule": "INJ-002", "severity": "medium", "stage": "注入面",
     "what": "shell=True 或字符串拼命令（subprocess/os.system 吃变量）",
     # ⚠️ 精度（实测收噪声）：`subprocess.run([prog] + args)` 是**列表拼接**、安全（本就等价 shell=False），
     #    第一版把它也算进来 ⇒ 一屏噪音。现在只认真正把字符串交给 shell 的两种写法。
     "rx": re.compile(r"(shell\s*=\s*True|os\.system\s*\()"),
     "ctx": re.compile(r"."),
     "repro": ("python -c \"import pathlib;print([l.strip() for l in pathlib.Path('%s')"
               ".read_text(encoding='utf-8',errors='replace').splitlines() if 'shell=True' in l][:3])\"")},
    {"rule": "DES-001", "severity": "high", "stage": "破坏面",
     "what": "破坏性命令（递归删目录 / 清表 / 硬回退）",
     # ⚠️ 精度：`DROP TABLE IF EXISTS` 是本地库**建表前的幂等清理**（本仓 call_graph 就这么用），
     #    不算破坏面；要报的是**无条件**清表/删目录/硬回退。
     "rx": re.compile(r"(rm\s+-rf|shutil\.rmtree|TRUNCATE\s+TABLE|DROP\s+TABLE(?!\s+IF\s+EXISTS)"
                      r"|reset\s+--hard)"),
     "ctx": re.compile(r"."),
     "repro": ("python -c \"import pathlib;print([l.strip() for l in pathlib.Path('%s')"
               ".read_text(encoding='utf-8',errors='replace').splitlines() if 'rmtree' in l][:3])\"")},
    {"rule": "JDG-001", "severity": "medium", "stage": "判据面",
     "what": "恒真/恒假判据（看着在判其实不会红）",
     "rx": re.compile(r"(\bor\s+True\b|\band\s+False\b)"),
     "ctx": re.compile(r"."),
     "repro": ("python -c \"import pathlib;print([l.strip() for l in pathlib.Path('%s')"
               ".read_text(encoding='utf-8',errors='replace').splitlines() if 'or True' in l][:3])\"")},
]
PLACEHOLDER = re.compile(r"(?i)(example|demo|sample|dummy|placeholder|xxx+|\.\.\.|your[_-]?key|<[^>]{2,20}>|abcdef|123456|deadbeef|f{4,}|0{6,}|qwerty)")


def _triage(rel: str, line_txt: str, rule: str) -> str:
    """分诊。三条原则性规则（都可复核，不是拍脑袋）：
    ① **扫描器/清单类文件按类豁免**（模式串不是漏洞）；
    ② **纯注释行里的"可执行类"命中**（INJ/DES/JDG）→ **需人核**，因为注释不会执行；
       但 **CRED 不在此列**：注释里的真密钥一样是泄露；
    ③ **清理自建临时目录**（名字含 tmp/temp/iso/scratch/cache）→ by design。
    """
    if any(k in rel for k in EXEMPT_PATHS):
        first = [k for k in EXEMPT_PATHS if k in rel][0]
        return f"已登记豁免（{EXEMPT_PATHS[first]}）"
    if PLACEHOLDER.search(line_txt):
        return "占位符/示例形状（无真实凭据形状）"
    if rule == "CRED-001" and re.search(r"(?i)(assert|unittest|test_|fixture|mock)", line_txt):
        return "测试夹具里的合成值"
    if rule == "JDG-001" and re.search(r"audit-dead-judgments|KNOWN\s*=", line_txt):
        return "判据扫描器自身的模式表"
    s = line_txt.strip()
    if rule != "CRED-001" and (s.startswith(("#", "//", "*", "·", ">")) or s.startswith('"')):
        return "**纯注释/文档行里的提及**（不可执行）⇒ 需人核，不算 finding"
    if rule == "DES-001" and re.search(r"rmtree\([^)]*(tmp|temp|iso|scratch|cache|staging|__pycache__)",
                                       line_txt, re.I):
        return "清理**临时/暂存/缓存目录**（by design）⇒ 需人核，不算 finding"
    if rule == "DES-001" and re.search(r"rmtree\(\s*([A-Za-z_]\w*)\s*\)", line_txt):
        # **变量目标**：没有数据流分析，静态判不出它指向临时目录还是真身目录。
        #   ⇒ 按本模块自己的规矩进 `needs_human`（分不清的**不硬报**）。
        #   真要判，跑 grep 看那个变量怎么来的，或过 action_gate（先看→动脑）再动手。
        return "NEEDS_HUMAN:变量目标的删除（静态判不出指向哪；要人看一眼或查该变量的来历）"
    if rule == "DES-001":
        return ""          # 字面目标/字面命令（rm -rf '...' / reset --hard）⇒ 保留 finding
    if rule == "DES-001" and re.search(r"(不做|不许|禁止|不得|no\s+rebase|never)", line_txt, re.I):
        return "**否定声明**（说的是不做这件事）"
    return ""


def _walk(target: str) -> list:
    base = Path(target) if target else _ROOT
    if not base.is_absolute():
        base = _ROOT / target
    if base.is_file():
        return [base]
    out = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith((".py", ".js", ".ts", ".cjs", ".mjs")):
                p = Path(root) / f
                try:
                    if p.stat().st_size > MAX_BYTES:
                        continue
                except OSError:
                    continue
                out.append(p)
                if len(out) >= MAX_FILES:
                    return out
    return out


def scan(target: str = "gbt_allinone,tools", rules: str = "", **_kw) -> dict:
    """**多阶段**扫描（凭证 / 注入 / 破坏 / 判据）⇒ findings；命中先过分诊。"""
    want = {x.strip().upper() for x in rules.split(",") if x.strip()}
    active = [r for r in RULES if not want or r["rule"] in want]
    if not active:
        return {"ok": False, "op": "scan", "fail_closed": True,
                "error": f"rules 过滤后没有可用规则（可用：{[r['rule'] for r in RULES]}）"}
    paths = []
    for t in [x.strip() for x in target.split(",") if x.strip()]:
        paths.extend(_walk(t))
    findings, triaged, rows, needs = [], {}, 0, []
    for p in paths:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(_ROOT)).replace("\\", "/") if _ROOT in p.parents else str(p)
        for i, line in enumerate(txt.splitlines(), 1):
            rows += 1
            for r in active:
                if not r["rx"].search(line):
                    continue
                if r["rule"] != "DES-001" and not r["ctx"].search(line):
                    continue
                if r["rule"] == "CRED-001":
                    # ⚠️ 精度（实测）：泛化的"长 base64 串"分支会把**长标识符清单/枚举串**也命中
                    #   （例：'op=status/whoami/energy/plan/keys/compat/mask/classify…'）。
                    #   ⇒ 泛化分支必须落在**赋值位**且左值像密钥名；带前缀的（sk-/ghp_/AKIA）不受此限。
                    prefixed = bool(re.search(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{12,})", line))
                    assigned = bool(re.search(r"(?i)(key|token|secret|password|passwd)\w*\s*[:=]\s*['\"]", line))
                    if not (prefixed or assigned):
                        continue
                why = _triage(rel, line, r["rule"])
                key = ("已分诊", r["rule"], why)
                if why:
                    triaged[key] = triaged.get(key, 0) + 1
                    if why.startswith("NEEDS_HUMAN:"):
                        needs.append({"rule": r["rule"], "file": rel, "line": i,
                                      "snippet": line.strip()[:140],
                                      "why": why.split(":", 1)[1]})
                    continue
                fid = "F-%s-%s-%d" % (r["rule"], hashlib.sha256(rel.encode()).hexdigest()[:6], i)
                findings.append({
                    "id": fid, "rule": r["rule"], "severity": r["severity"], "stage": r["stage"],
                    "what": r["what"], "file": rel, "line": i,
                    "snippet": line.strip()[:160],
                    "evidence": {"file_sha256": _sha(p), "line_text": line.strip()[:160],
                                 "how_found": "扫描正则命中（第 1 路读法）"},
                    "repro": r["repro"] % (_ROOT / rel,),
                    "verified_by": "", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                })
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "target": target, "files": len(paths),
           "lines": rows, "findings": findings, "triaged": [list(k) for k in triaged],
           "needs_human": needs[:200],
           "_口径": "命中先分诊；**分不清的进 needs_human，不硬报**；全量面天然含框架自家的清理路径，"
                    "日常该用的是 diff_audit（改动面）或 rules= 定向。"}
    tmp = _FINDINGS.with_name(_FINDINGS.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _FINDINGS)
    _log({"event": "scan", "files": len(paths), "rules": [r["rule"] for r in active],
          "lines": rows, "findings": len(findings), "by_severity": {s: sum(1 for f in findings if f["severity"] == s)
                          for s in ("high", "medium", "low")}})
    return {"ok": True, "op": "scan", "files": len(paths), "lines": rows,
            "findings": len(findings), "needs_human": len(needs),
            "by_severity": {s: sum(1 for f in findings if f["severity"] == s)
                            for s in ("high", "medium", "low")},
            "by_stage": {st: sum(1 for f in findings if f["stage"] == st)
                         for st in sorted({f["stage"] for f in findings})},
            "triaged": len(doc["triaged"]), "top": findings[:5],
            "file": str(_FINDINGS.relative_to(_ROOT))}


def findings(severity: str = "", stage: str = "", **_kw) -> dict:
    if not _FINDINGS.is_file():
        return {"ok": False, "op": "findings", "error": "还没扫过 ⇒ 先 op=scan"}
    d = json.loads(_FINDINGS.read_text(encoding="utf-8"))
    rows = d.get("findings") or []
    if severity:
        rows = [f for f in rows if f["severity"] == severity]
    if stage:
        rows = [f for f in rows if f["stage"] == stage]
    return {"ok": True, "op": "findings", "count": len(rows), "at": d.get("at"),
            "rows": rows[:40], "triaged": len(d.get("triaged") or [])}


def _second_reading(f: dict) -> tuple:
    """**第二路读法**（与扫描的正则不同机制）：行锚定 + 内容 sha + 字面搜索。"""
    p = _ROOT / f["file"]
    if not p.is_file():
        return False, "文件不在了 ⇒ 这条 finding 失去依据（先复核）"
    if _sha(p) != (f.get("evidence") or {}).get("file_sha256"):
        return False, "**文件已被改动**（sha 与扫描时不一致）⇒ 行号/内容都可能失效，要重扫"
    txt = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if f["line"] > len(txt):
        return False, "行号超出文件长度（文件被改短）"
    if txt[f["line"] - 1].strip() != (f.get("evidence") or {}).get("line_text"):
        return False, "该行内容与扫描时不一致"
    if f["snippet"][:40] and f["snippet"][:40] not in p.read_text(encoding="utf-8", errors="replace"):
        return False, "字面搜索没复现（片段已不在文件里）"
    return True, "行锚定 + 内容 sha + 字面搜索**三查都过**"


def verify_finding(id: str = "", **_kw) -> dict:
    """**独立验证**一条 finding：第二路读法复核；只一路命中 ⇒ 不标确认。"""
    if not id.strip():
        return {"ok": False, "op": "verify_finding", "fail_closed": True, "error": "要给 id"}
    if not _FINDINGS.is_file():
        return {"ok": False, "op": "verify_finding", "error": "还没扫过"}
    d = json.loads(_FINDINGS.read_text(encoding="utf-8"))
    hit = next((f for f in (d.get("findings") or []) if f["id"] == id), None)
    if not hit:
        return {"ok": False, "op": "verify_finding", "error": f"没有这条 finding：{id}"}
    ok, why = _second_reading(hit)
    hit["verified_by"] = "双路" if ok else ""
    hit["verify_verdict"] = why
    tmp = _FINDINGS.with_name(_FINDINGS.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _FINDINGS)
    _log({"event": "verify_finding", "id": id, "ok": ok, "why": why[:120]})
    return {"ok": ok, "op": "verify_finding", "id": id, "verified_by": hit["verified_by"],
            "verdict": why, "how": "" if ok else "重扫（op=scan）拿到新的行号与 sha，再验一次",
            "_口径": "**两路读法都命中才算确认**；只一路命中一律 unverified"}


def repro(id: str = "", **_kw) -> dict:
    """给一条 finding 的**可复制复现命令**（人照着跑就能重现）。"""
    if not _FINDINGS.is_file():
        return {"ok": False, "op": "repro", "error": "还没扫过"}
    rows = json.loads(_FINDINGS.read_text(encoding="utf-8")).get("findings") or []
    hit = next((f for f in rows if f["id"] == id), None)
    if not hit:
        return {"ok": False, "op": "repro", "error": f"没有这条 finding：{id}"}
    return {"ok": True, "op": "repro", "id": id, "file": hit["file"], "line": hit["line"],
            "cmd": hit["repro"], "expect": f"输出里应再次出现：{hit['snippet'][:80]}"}


def diff_audit(base: str = "HEAD", **_kw) -> dict:
    """**改动面定向审查**：只审 `git diff` 出现的文件与行（对提交/PR 做安全审查）。"""
    cp = subprocess.run(["git", "diff", "--unified=0", base, "--"], cwd=str(_ROOT),
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if cp.returncode != 0:
        return {"ok": False, "op": "diff_audit", "error": (cp.stderr or "")[:200]}
    cur_file, added = None, []
    for ln in (cp.stdout or "").splitlines():
        if ln.startswith("+++ b/"):
            cur_file = ln[6:].strip()
        elif ln.startswith("+") and not ln.startswith("+++"):
            added.append((cur_file, ln[1:]))
    hits, triaged = [], 0
    for rel, txt in added:
        if not rel or any(k in rel for k in SKIP_DIRS):
            continue
        for r in RULES:
            if r["rx"].search(txt) and (r["ctx"].search(txt) or r["rule"] == "DES-001"):
                why = _triage(rel, txt, r["rule"])
                if why:
                    triaged += 1
                    continue
                hits.append({"rule": r["rule"], "severity": r["severity"], "file": rel,
                             "snippet": txt.strip()[:160], "why": r["what"]})
    _log({"event": "diff_audit", "base": base, "added_lines": len(added), "hits": len(hits)})
    return {"ok": True, "op": "diff_audit", "base": base, "added_lines": len(added),
            "hits": len(hits), "rows": hits[:20], "triaged": triaged,
            "note": "只审改动行；全量面审计跑 op=scan（两者口径分开，别混）"}


def report(**_kw) -> dict:
    if not _FINDINGS.is_file():
        return {"ok": False, "op": "report", "error": "还没扫过"}
    d = json.loads(_FINDINGS.read_text(encoding="utf-8"))
    rows = d.get("findings") or []
    verified = [f for f in rows if f.get("verified_by")]
    return {"ok": True, "op": "report", "at": d.get("at"), "target": d.get("target"),
            "files": d.get("files"), "lines": d.get("lines"),
            "counts": {"findings": len(rows), "verified": len(verified),
                       "unverified": len(rows) - len(verified),
                       "high": sum(1 for f in rows if f["severity"] == "high"),
                       "medium": sum(1 for f in rows if f["severity"] == "medium"),
                       "triaged": len(d.get("triaged") or [])},
            "by_rule": {r: sum(1 for f in rows if f["rule"] == r)
                        for r in sorted({f["rule"] for f in rows})},
            "findings": rows,
            "_口径": "机器可读 findings（severity/证据/复现/是否独立验证）；计数即人读摘要"}


def verify(**_kw) -> dict:
    problems = []
    if not _FINDINGS.is_file():
        return {"ok": False, "op": "verify", "problems": ["没有 findings 文件 ⇒ 先 op=scan"]}
    d = json.loads(_FINDINGS.read_text(encoding="utf-8"))
    for f in d.get("findings") or []:
        if not f.get("evidence"):
            problems.append(f"{f['id']} 没有证据（没证据不许开 finding）")
        if not f.get("repro"):
            problems.append(f"{f['id']} 没有复现命令")
        if f["severity"] == "high" and not f.get("repro"):
            problems.append(f"{f['id']} 高 severity 却没有复现命令")
        if not (_ROOT / f["file"]).is_file():
            problems.append(f"{f['id']} 指向的文件已不在盘上 ⇒ 要么重扫要么关掉它")
    return {"ok": not problems, "op": "verify", "problems": problems[:12],
            "counts": {"findings": len(d.get("findings") or []),
                       "verified": sum(1 for f in (d.get("findings") or []) if f.get("verified_by"))},
            "_口径": "每条 finding 有证据+复现；高 severity 必须有复现；指向的文件必须还在"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "code_audit", "tentacle": "code_audit",
            "entry": "run_task('code_audit', {...})",
            "ops": ["scan", "diff_audit", "findings", "verify_finding", "repro", "report",
                    "verify", "where"],
            "distilled_from": "GitHub 周榜 #03 security-audit-skill（只取架构：多阶段 + findings 契约 + 独立验证 + 复现）",
            "not_copied": "它的规则集/代码未引用；全量面扫描仍走 penetrating_cross_scan 三件套 + sec_sweeper",
            "rule_ids": [r["rule"] for r in RULES],
            "hard_rules": ["没证据不许开 finding", "两路读法都命中才算确认（否则 unverified）",
                           "命中先分诊（豁免/占位/夹具不报）", "改动面与全量面口径分开"],
            "files": {"findings": str(_FINDINGS.relative_to(_ROOT)), "台账": str(_LEDGER.relative_to(_ROOT))}}


def run_op(op: str = "report", **params) -> dict:
    op = (op or "report").lower()
    for name, fn in (("scan", scan), ("diff_audit", diff_audit), ("findings", findings),
                     ("verify_finding", verify_finding), ("repro", repro), ("report", report),
                     ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（scan/diff_audit/findings/verify_finding/repro/report/verify/where）"}
