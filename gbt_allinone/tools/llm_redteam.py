# gbt-capability: llm_redteam
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""LLM 红队矩阵（llm_redteam）· **蒸馏自**：安全精英（SecurityElites）AI 红队课程 +
其「黑客实验室」（300+ 靶场：SQLi/XSS/CSRF/文件包含/命令执行/提权）的两张公开页读数。

## 蒸馏成了什么（**防御面**，不是进攻面）

原材料的形态是"教人攻"：提示注入、越狱套件（DAN / refusal flip / payload splitting）、
系统提示抽取、agentic chain（`agentic_chain.py --target rag-…`）、OWASP LLM01/LLM06
（过度代理）、以及 Docker 靶场（DVWA/WebGoat/kali）里的经典 Web 面。

本仓的规矩（[`pentest`](pentest.py) 立下的）是：**只对已登记授权的目标动手，未登记一律拒**。
⇒ 这位能力**不提供任何对第三方的攻击工具**，它把红队知识变成三样**对自己人有用**的东西：

| op | 它回答什么 | 判据形态 |
|---|---|---|
| `matrix` | OWASP LLM Top-10 十类攻击面**逐类的检测判据**（每条带 src） | 纯表，可机读、可核对 |
| `selfcheck` | **拿这套矩阵测我们自己的门**：提示组装点 / 凭据内插 / 过度代理 / 间接注入面 —— 逐条出 `verdict` + `evidence` | 只读静态读数（**不跑攻击**） |
| `where` | 这条知识从哪来（蒸馏溯源，可复核） | 出处 + 落地位置 |

🔴 **边界（写死，别放宽）**：
  ① **只读**：`selfcheck` 只读本仓文件，不改盘、不出网、不起进程；
  ② **不外攻**：任何"对某目标发攻击载荷"的请求一律拒，并指到 `pentest`（那条路要主人登记授权）；
  ③ 判据一律**带 src**（哪个文件/哪一行），**读不到就如实说读不到**，不许拿"未发现"冒充"安全"。

op=matrix / selfcheck / where
"""
from __future__ import annotations

import re
from pathlib import Path

CAP_KIND = "llm_redteam"
DOMAIN = "security"
CAP_TYPE = "internal"          # 内调型：它只测自己，不对外

_ROOT = Path(__file__).resolve().parents[2]

# ═══════════════ 一 · OWASP LLM Top-10 × 检测判据（可机读的表）═══════════════
# 每条：类别 / 一句话 / **我们怎么知道自家有没有这个面**（检测判据，不是攻击载荷）。
MATRIX = (
    {"id": "LLM01", "name": "提示注入（直接/间接）",
     "what": "用户内容与指令混在同一条通道里，被当成指令执行",
     "probe": "prompt_sink", "why": "看提示组装点有没有把**外部内容**与**指令**分槽"},
    {"id": "LLM02", "name": "敏感信息泄露",
     "what": "回话里带出凭据、路径、内网拓扑",
     "probe": "secret_in_prompt", "why": "看提示模板里有没有把凭据/密钥**内插**进去"},
    {"id": "LLM03", "name": "供应链",
     "what": "模型/插件/依赖被投毒（第三方权重、插件市场）",
     "probe": "vendor_roots", "why": "看本机技能根/插件面是否已登记（未登记的分岔就是盲区）"},
    {"id": "LLM04", "name": "数据与模型投毒",
     "what": "喂给记忆/检索的语料被污染 ⇒ 结论被带偏",
     "probe": "memory_write_paths", "why": "看记忆写入点是否只追加、是否带来源"},
    {"id": "LLM05", "name": "不当输出处理",
     "what": "模型输出被当代码/命令直接执行",
     "probe": "eval_sinks", "why": "看仓里有没有把模型输出喂给 eval/exec/shell 的点"},
    {"id": "LLM06", "name": "过度代理（Excessive Agency）",
     "what": "给了模型太多工具与太宽的权限，它自己就把事做了",
     "probe": "agent_scopes", "why": "看每个智能体有没有**机器可读的 may / may_not** 边界"},
    {"id": "LLM07", "name": "系统提示泄露",
     "what": "被问几句话就把系统提示原文吐出来",
     "probe": "system_prompt_guard", "why": "看系统提示里有没有**不可回显**的声明与挡板"},
    {"id": "LLM08", "name": "向量与嵌入弱点（RAG）",
     "what": "检索回来的片段里藏着指令（间接注入）",
     "probe": "rag_trust_boundary", "why": "看检索结果进模型前有没有**降级为数据**这一步"},
    {"id": "LLM09", "name": "错误信息",
     "what": "编造结论并当成事实（本仓叫「假绿」）",
     "probe": "honesty_fences", "why": "看读数是不是都带 src、取不到时是不是**如实说取不到**"},
    {"id": "LLM10", "name": "无界消耗",
     "what": "被诱导无限推理/无限调用，烧钱烧时间",
     "probe": "budget_gates", "why": "看有没有**预算闸/限速闸**（本仓 `DECIDE_MAX_PER_MIN` 是样本）"},
)

# 图片里点名的具体手法 → 归到上面哪一类（蒸馏时逐条落位，**不许含糊**）
TECHNIQUES = (
    {"t": "system prompt extracted（系统提示被抽出）", "owasp": "LLM07"},
    {"t": "DAN / refusal flip（越狱：让它换个身份答）", "owasp": "LLM01"},
    {"t": "payload splitting（载荷拆开多轮拼接）", "owasp": "LLM01"},
    {"t": "jailbreak_suite.sh --model <target>（越狱套件批量试）", "owasp": "LLM01"},
    {"t": "agentic_chain.py --target rag-…（代理链式调用打到 RAG）", "owasp": "LLM08"},
    {"t": "OWASP LLM06 excessive agency（工具给太多）", "owasp": "LLM06"},
    {"t": "实验室：DVWA/WebGoat/kali 靶场（SQLi/XSS/CSRF/LFI/RCE/提权）",
     "owasp": "—（经典 Web 面；本仓对应位是 `pentest`（授权登记后）与 `sec_defenses`（蓝队验证））"},
)


def matrix(**_kw) -> dict:
    """十类攻击面 + 逐类检测判据（表本身）。"""
    return {"ok": True, "op": "matrix", "count": len(MATRIX), "categories": [dict(x) for x in MATRIX],
            "techniques": [dict(x) for x in TECHNIQUES],
            "_口径": "蒸馏自公开课程页；**只作检测判据**，不含任何攻击载荷"}


# ═══════════════ 二 · selfcheck：拿矩阵测我们自己 ═══════════════

def _scan_files(pats, roots, cap=400) -> list:
    out = []
    for root in roots:
        p = _ROOT / root
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if len(out) >= cap:
                return out
            if not f.is_file() or f.suffix.lower() not in pats:
                continue
            if any(x in str(f) for x in ("node_modules", "_upstream", ".pylibs", "__pycache__", "审美相关skill")):
                continue
            out.append(f)
    return out


def _probe_prompt_sink() -> dict:
    """LLM01 · 提示组装点：有没有把**外部内容**与**指令**混在一个槽里。"""
    hits = []
    for f in _scan_files({".py"}, ["gbt_allinone"]):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r'f["\'][^"\']{0,80}(prompt|指令|系统)[^"\']{0,40}\{[^}]+\}', txt, re.I):
            line = txt[:m.start()].count("\n") + 1
            hits.append({"file": str(f.relative_to(_ROOT)), "line": line, "snip": m.group(0)[:80]})
    return {"probe": "prompt_sink", "owasp": "LLM01", "hits": hits[:8], "count": len(hits)}


def _probe_secret_in_prompt() -> dict:
    """LLM02 · 凭据内插：提示模板里直接插密钥/令牌 = 泄露面。"""
    hits = []
    pat = re.compile(r'(sk-[A-Za-z0-9_\-]{6,}|api[_-]?key\s*=\s*["\'][^"\']{8,})', re.I)
    for f in _scan_files({".py", ".md"}, ["gbt_allinone", "tools"]):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in pat.finditer(txt):
            line = txt[:m.start()].count("\n") + 1
            hits.append({"file": str(f.relative_to(_ROOT)), "line": line,
                         "snip": m.group(0)[:6] + "****"})      # **掩码**：本件也不回显明文
    return {"probe": "secret_in_prompt", "owasp": "LLM02", "hits": hits[:8], "count": len(hits)}


def _probe_agent_scopes() -> dict:
    """LLM06 · 过度代理：每个智能体有没有机器可读的 may / may_not。"""
    rows = []
    d = _ROOT / "gbt_allinone" / "tools" / "gods_eye.py"
    if d.exists():
        txt = d.read_text(encoding="utf-8", errors="replace")
        has = ("may_not" in txt) and ("ROLES" in txt)
        rows.append({"who": "gods_eye.ROLES（四岗）", "may_not": has,
                     "src": "gbt_allinone/tools/gods_eye.py"})
    agents = _ROOT / ".zcode" / "agents"
    if agents.is_dir():
        n = len(list(agents.glob("*.md")))
        rows.append({"who": ".zcode/agents 智能体定义", "count": n,
                     "may_not": None, "src": ".zcode/agents/",
                     "note": "定义在宿主侧；本仓无机器可读边界 ⇒ 这一格**读不到**（如实记）"})
    return {"probe": "agent_scopes", "owasp": "LLM06", "rows": rows,
            "count": len([r for r in rows if r.get("may_not") is False])}


def _probe_rag_trust_boundary() -> dict:
    """LLM08 · 检索边界：记忆/检索回来的内容进模型前有没有"降级为数据"。"""
    hits = []
    for f in _scan_files({".py"}, ["gbt_allinone/tools"]):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"(外部内容|untrusted|不可信|当作数据|降级为数据|不当指令)", txt):
            hits.append({"file": str(f.relative_to(_ROOT)), "why": "文件里已声明外部内容边界"})
    return {"probe": "rag_trust_boundary", "owasp": "LLM08", "hits": hits[:8], "count": len(hits)}


def _probe_budget_gates() -> dict:
    """LLM10 · 无界消耗：有没有预算/限速闸（本仓样本：DECIDE_MAX_PER_MIN）。"""
    hits = []
    for f in _scan_files({".py"}, ["gbt_allinone"]):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"^([A-Z_]*MAX_[A-Z_]*|.*BUDGET.*)\s*=\s*\d+", txt, re.M):
            line = txt[:m.start()].count("\n") + 1
            hits.append({"file": str(f.relative_to(_ROOT)), "line": line, "snip": m.group(0)[:60]})
    return {"probe": "budget_gates", "owasp": "LLM10", "hits": hits[:10], "count": len(hits)}


_PROBES = {
    "prompt_sink": _probe_prompt_sink,
    "secret_in_prompt": _probe_secret_in_prompt,
    "agent_scopes": _probe_agent_scopes,
    "rag_trust_boundary": _probe_rag_trust_boundary,
    "budget_gates": _probe_budget_gates,
}


def selfcheck(only: str = "", **_kw) -> dict:
    """**拿红队矩阵测自己**：逐类跑只读判据，出 verdict + evidence。**不跑攻击、不出网。**"""
    want = [p for p in _PROBES if not only or p == only]
    rows = []
    for p in want:
        try:
            r = _PROBES[p]()
            rows.append(r)
        except Exception as err:                     # noqa: BLE001
            rows.append({"probe": p, "error": str(err)[:120],
                         "note": "判据自己坏了 —— 如实记，不许当『安全』"})
    # 三类"有正读数=好"的格（边界/预算/RAG声明）与两类"有命中=要注意"的格
    positives = {"rag_trust_boundary", "budget_gates"}
    flags = []
    for r in rows:
        if r.get("error"):
            flags.append({"probe": r["probe"], "level": "judge-broken", "why": r["error"]})
        elif r["probe"] in positives:
            if not r.get("count"):
                flags.append({"probe": r["probe"], "level": "missing",
                              "why": "这类正面判据一条都没命中 ⇒ 要么真没有，要么判据抓不到"})
        elif r["probe"] == "agent_scopes":
            for row in (r.get("rows") or []):
                if row.get("may_not") is False:
                    flags.append({"probe": r["probe"], "level": "attention", "why": row})
        elif r.get("count"):
            flags.append({"probe": r["probe"], "level": "attention",
                          "why": "%d 处命中（见 hits）" % r["count"]})
    return {"ok": True, "op": "selfcheck", "probes": rows, "flags": flags, "flagged": len(flags),
            "_口径": "**只读**静态判据（不跑攻击、不出网）；命中≠漏洞，是指『这里要看一眼』；"
                     "读不到就报读不到 —— **未发现 ≠ 安全**"}


def where(**_kw) -> dict:
    """蒸馏溯源：这批知识从哪来、落在哪。"""
    return {"ok": True, "op": "where",
            "来源": ["安全精英 SecurityElites · 公开课程页（AI 红队：LLM01/LLM06、越狱、系统提示抽取、agentic chain）",
                     "其「黑客实验室」公开页（300+ 靶场：SQLi/XSS/CSRF/文件包含/命令执行/提权；DVWA/WebGoat/kali）"],
            "落地": {"矩阵": "gbt_allinone/tools/llm_redteam.py · MATRIX / TECHNIQUES",
                     "自测": "同文件 · selfcheck（5 条只读判据）",
                     "与既有位的关系": "redteam_recon=本机侦察 · sec_defenses=蓝队验证 · pentest=授权渗透（要登记）· "
                                     "**llm_redteam=LLM 面自测**（不与前三位重复）"},
            "_口径": "原材料是『教人攻』的公开材料；本位的蒸馏形态是**检测判据**，"
                     "对外攻击载荷一概不提供、不落盘"}


def run_op(op: str = "matrix", **params) -> dict:
    op = (op or "matrix").lower()
    for name, fn in (("matrix", matrix), ("selfcheck", selfcheck), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": "未知 op:%s（matrix/selfcheck/where）" % op}


HONEST_BOUNDARY = (
    "本位**不做**：对任何第三方目标发攻击载荷（那条路只有 `pentest` 且要主人登记授权）、"
    "越狱/注入的真实构造与投递、靶场复刻。"
    "它**只**把公开红队知识整理成**可核对的自测判据**：判据命中不等于存在漏洞，"
    "一条都没命中也不等于安全（可能只是判据抓不到）—— 两个方向都不许读反。"
)
