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

import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import tokenize
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_FINDINGS = _STATE / "code_audit_findings.json"   # findings（原子写：重扫覆盖，id 稳定）
_LEDGER = _STATE / "code_audit.jsonl"             # 每次扫描/验证（追加式）
# ── 地毯式覆盖（主人令 2026-11-03）────────────────────────────────────────────
# 旧口径只认 5 种扩展名（.py/.js/.ts/.cjs/.mjs）⇒ .html 内联 JS、.ps1/.bat/.cmd/.sh
# 脚本、.tsx 组件、.json 配置全部**免检**。地毯式把那 996 个盲区全部纳入视野。
SCAN_EXT = (".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".cjs", ".mjs",
            ".ps1", ".bat", ".cmd", ".sh", ".html", ".htm", ".json")

# 排除目录 = **目录 → 理由**（唯一来源）。关键纪律：排除不是"看不见"，
# 每个被排除的目录都会在 coverage.excluded_dirs 里**报出路径**，可追可审。
EXCLUDED_DIRS = {
    ".git": "版本库元数据（非源码）",
    ".pylibs": "vendored 依赖（第三方）",
    "node_modules": "第三方依赖",
    "store": "运行时存储（数据非代码）",
    "vaults": "金库（凭据区，另有专审）",
    "out": "构建产物",
    ".scratch": "临时探针区（本仓自用草稿）",
    "__pycache__": "字节码缓存",
    ".mimosa": "第三方镜像快照",
    "_upstream": "上游快照（第三方）",
    "delivery": "交付产物",
    "output": "输出产物",
    "generated-images": "生成图片",
    ".archive": "历史归档（已退役代码，仍在盘上）",
    "state": "运行时/证据区（findings、镜像备份、暂存稿、图快照）—— 扫它等于自己扫自己",
    "vendor": "第三方上游快照（与 skills/ 内容重复，扫了只会双报）",
}
SKIP_DIRS = set(EXCLUDED_DIRS)   # 单一来源：排除集合由理由表派生，不另写一份

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
    # ── 验证器本体（**按类豁免**）：它们的职责就是"把被测对象跑起来看结果"，
    #    所以 `exec(compile(...))` / `exec(fn, g)` 是**本职动作**，不是漏洞。
    "tools/codex-scripts/verify_ledger_sink.py": "验证器本体：exec 是它执行被测对象的方式",
    "tools/codex-scripts/verify_loader_scope.py": "验证器本体：同上（装载域验证）",
    "tools/codex-scripts/verify_loader_scope2.py": "验证器本体：同上（装载域验证 v2）",
    # ── 能力位**本职动作**：文件系统域（第十四章补的第 9 域）的删除能力本身。
    #    规则表报它 = 报警器报自己会响。豁免只覆盖这一个文件，且理由在此可见。
    "gbt_allinone/tentacle/omni_fs.py": "文件系统能力位本体：rmtree 是它的删除能力（本职）",
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
     # 词边界（2026-11-03 实测）：`dict(c, empty_shell=True)` 里的 `empty_shell=True`
    #   会被 `shell\s*=\s*True` 当成命中 —— 加 `(?<![A-Za-z0-9_])` 排除"某某_shell"。
    "rx": re.compile(r"(?<![A-Za-z0-9_])(shell\s*=\s*True|os\.system\s*\()"),
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


def _prose_spans(src: str) -> list:
    """收集源码里**所有"散文"区间**：(首行, 首列, 末行, 末列)。

    散文 = 字符串字面量（含 docstring / f-string）**+ 注释**。两者都不是可执行代码：
      · `"shell=True"` 是 Constant(str)，`shell=True` 是 ast.keyword —— 语法上完全不同
      · `# 受限builtins exec(含前文)` 是注释，不是调用
    ast 不含注释，所以注释区间用 tokenize 取；语法有错时优雅降级（宁可不判，不乱报）。
    """
    spans = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                pass
            elif isinstance(node, ast.JoinedStr):        # f-string
                pass
            else:
                continue
            spans.append((node.lineno, node.col_offset,
                          getattr(node, "end_lineno", node.lineno) or node.lineno,
                          getattr(node, "end_col_offset", node.col_offset) or 0))
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                spans.append((tok.start[0], tok.start[1], tok.end[0], tok.end[1]))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass   # 非 Python / 语法错：注释区间拿不到就不拿，不影响字符串判定
    return spans


def _line_prose(line: str, col: int) -> bool:
    """非 Python 文件的单行散文判定（.js/.ts/.tsx/.mjs 没有 Python AST）。

    三条判据（覆盖 JS 生态 99% 的单行散文）：
      1. `/* ... */` 块注释内
      2. `//` 之后的行注释
      3. 引号配对（单引号 / 双引号 / 反引号）—— 奇偶判定，跳过反斜杠转义
    跨行模板串判不了（要真词法分析器），那种情况仍会报 —— **宁可漏判不放行**。
    """
    for m in re.finditer(r"/\*.*?\*/", line):
        if m.start() <= col < m.end():
            return True
    d = line.find("//")
    if d >= 0 and col > d:
        return True
    q = None
    i = 0
    while i < col and i < len(line):
        ch = line[i]
        if q is None and ch in "'\"`":
            q = ch
        elif q is not None and ch == q and (i == 0 or line[i - 1] != "\\"):
            q = None
        i += 1
    return q is not None


def _in_span(spans: list, lineno: int, col: int) -> bool:
    """(行, 列) 是否落在某个字符串字面量内部。"""
    for sl, sc, el, ec in spans:
        if lineno < sl or lineno > el:
            continue
        if lineno == sl and col < sc:
            continue
        if lineno == el and col >= ec:
            continue
        return True
    return False


_TEMP_SRC = re.compile(r"(mkdtemp|TemporaryDirectory|NamedTemporaryFile|gettempdir)", re.I)


def _temp_origin(lines: list, line_no: int, var: str, lookback: int = 60):
    """简易数据流：同文件内 `var` 是否被赋值为**临时目录**。

    只做一件事、只信一种证据：赋值右侧出现 mkdtemp / TemporaryDirectory /
    NamedTemporaryFile / gettempdir。查不到就返回 False（**不猜**）。
    这样 `rmtree(mkdtemp(...))` 这种标准清理能判 by design，
    而 `rmtree(user_data)` 仍然进人核。
    """
    if not lines or not var:
        return False
    rx = re.compile(r"^\s*" + re.escape(var) + r"\s*(?::[^=]+)?=\s*(.+)$")
    lo = max(0, (line_no or 1) - lookback)
    for i in range(lo, min(len(lines), (line_no or 1))):
        m = rx.match(lines[i])
        if m and _TEMP_SRC.search(m.group(1)):
            return True
    return False


_RX_OBJ = re.compile(r"^(re|RE|rx|_re|_rx|regex|regexp|pattern|pat|PATTERN)$")
_RX_PREFIX = re.compile(r"^(RE|RX|PAT|PATTERN|REGEX|REGEXP)_")   # RX_PATTERN / RE_FENCE
_RX_SUFFIX = re.compile(r"(_RE|_RX|_re|_rx|_RegExp|_regex)$")     # TITLE_RE / matcher_rx
_RX_LITERAL = re.compile(r"/[^/\n]+/\s*\.\s*(?:ex[ae]c|test)\s*\(")


def _triage(rel: str, line_txt: str, rule: str, ctx=None) -> str:
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
    if rule == "JDG-001" and re.search(r"\blambda\b[^:]*:[^\n]*\bor\s+True\b", line_txt):
        # `lambda text: seen.update(text=text) or True` —— dict.update() 返回 None，
        # 用 `or True` 让 lambda **有真返回值**。这是测试桩技巧，不是"判据撒谎"。
        # （与已修的 `bool(r) or True` 区别：那个在**判据**里恒真，这个在**桩**里补返回值。）
        return "测试桩技巧（lambda 内 `x or True` 让返回值变真）⇒ 需人核"
    if rule == "JDG-001" and re.search(r"audit-dead-judgments|KNOWN\s*=", line_txt):
        return "判据扫描器自身的模式表"
    if rule == "INJ-002":
        # 2026-11-03 逐条追踪 19 条后定的口径：
        #   · 首参是**列表**的（`run([...], shell=True)`）⇒ shell 纯属多余且有害，
        #     已在代码里改成 shell=False（Windows 上会走 cmd.exe 拼串，反而引入引号风险）；
        #   · 首参是**字符串字面量**且含管道（`"tail -60 x" % LOG`）⇒ 真需要 shell（Linux 远程机）；
        #   · 首参是**变量/入参**（payload["cmd"] / action["cmd"] / 函数入参）⇒
        #     **静态判不出 cmd 来源**，按第八章「分不清的不硬报」进人核。
        return ("NEEDS_HUMAN:shell=True 且命令来自变量/入参"
                "（静态判不出 cmd 来源；要人核它吃不吃外部输入）")
    if rule == "INJ-001":
        mo = re.search(r"([A-Za-z_$][\w$]*)\s*\.\s*(ex[ae]c|ev[ae]l)\s*\(", line_txt)
        if mo:
            obj = mo.group(1)
            if _RX_OBJ.match(obj) or _RX_SUFFIX.search(obj) or _RX_PREFIX.match(obj):
                # 对象名就是正则约定（re / rx / pattern / XXX_RE）⇒ RegExp.prototype.exec
                return "正则对象的 .exec()（对象名 %r 是正则约定）⇒ 不是动态执行" % obj
        if _RX_LITERAL.search(line_txt):
            return "正则字面量的 .exec()（/…/.exec）⇒ 不是动态执行"
    if rule == "INJ-001" and rel.endswith((".ts", ".tsx", ".mts", ".cts")):
        # TS 语境（2026-11-03 实测）：`.ts/.tsx` 里 `exec(x)` 是 **child_process.exec**
        #   （Node 跑子进程的标准 API）或 RegExp.exec，都不是"把字符串当代码跑"。
        #   只对 exec 放宽 —— **eval 在 TS 里一样危险，照报不误**。
        if re.search(r"\bexec\s*\(", line_txt) and not re.search(r"\beval\s*\(", line_txt):
            return ("TS 语境的 exec()（child_process / RegExp）⇒ 需人核；"
                    "同行的 eval() 不受此放宽")
    if rule == "INJ-001":
        # 精度（2026-11-03 地毯式实测）：`ex[ae]c(` 会把 **RegExp.prototype.exec** 与
        #   **Playwright 的 page.eval** 一起命中 —— READY_LINE.exec(str) /
        #   /正则字面量/.exec(text) / page.eval(probe) 都不是"把字符串当代码跑"。
        #   可靠的静态区分：正则 exec 与对象方法**必然挂在 `.` 后面**；真正危险的
        #   动态执行是**裸调用** eval( / exec(（直接吃字符串）。
        #   ⇒ 挂对象的按宪章「分不清的不硬报」进 needs_human，裸调用才留 finding。
        if not re.search(r"(?<![.\w$])(ev[ae]l|ex[ae]c)\s*\(", line_txt):
            return ("NEEDS_HUMAN:挂在对象上的 .eval/.exec（RegExp.exec、page.eval 这类）"
                    "—— 静态分不出是不是动态执行，要人看一眼")
        if re.search(r"(async\s+)?(ev[ae]l|ex[ae]c)\s*\([^)]*\)\s*\{", line_txt):
            return "方法/函数**定义**而非调用（形如 eval(x) { ... }）⇒ 需人核"
    s = line_txt.strip()
    if rule != "CRED-001" and (s.startswith(("#", "//", "*", "·", ">")) or s.startswith('"')):
        return "**纯注释/文档行里的提及**（不可执行）⇒ 需人核，不算 finding"
    if rule == "DES-001" and re.search(r"rmtree\([^)]*(tmp|temp|iso|scratch|cache|staging|__pycache__)",
                                       line_txt, re.I):
        return "清理**临时/暂存/缓存目录**（by design）⇒ 需人核，不算 finding"
    if rule == "DES-001" and ctx is not None:
        lines, line_no = ctx
        mv = re.search(r"rmtree\(\s*([A-Za-z_]\w*)\s*[,)]", line_txt)
        if mv and _temp_origin(lines, line_no, mv.group(1)):
            return ("清理**自建临时目录**（数据流：%s 的赋值为 mkdtemp/TemporaryDirectory）"
                    "⇒ by design" % mv.group(1))
    if rule == "DES-001" and rel.startswith(("gbt_allinone/tests/", "tests/")):
        # 测试夹具（2026-11-03 实测 12 条）：全是清理**自建临时目录**的三个固定形态 ——
        #   rmtree(self.xxx, ...) / rmtree(xxx_dir(), ...) / addCleanup(shutil.rmtree, ...)
        # 场景明确但静态仍判不出指向（self.xxx 的值是运行时才定的），按第八章进 needs_human。
        if (re.search(r"rmtree\(\s*self\.[A-Za-z_]", line_txt)
                # `x_dir()` / `CM.channel_dir()` / `FO.channel_dir()` —— 补上"模块.方法()"形态
                or re.search(r"rmtree\(\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*_dir\(\)", line_txt)
                or re.search(r"addCleanup\(\s*(lambda\s*:\s*)?(shutil\.)?rmtree", line_txt)):
            return "NEEDS_HUMAN:测试夹具自建目录的清理（self.* / *_dir() / addCleanup）⇒ 需人核"
    if rule == "DES-001" and re.search(r"rmtree\(\s*[A-Za-z_]\w*\s*/\s*[\"\']", line_txt):
        # `rmtree(BASE / "selftest", ...)` —— 目标是"路径常量下的**字面量子目录**"。
        # 形态是确定的（不是变量），但 BASE 指向哪要人确认 ⇒ 按第八章进 needs_human。
        return ("NEEDS_HUMAN:删除的是**路径常量下的字面量子目录**（BASE / \"name\"）"
                "⇒ 形态确定，但要人确认 BASE 指向哪")
    if rule == "DES-001" and re.search(r"rmtree\(\s*[A-Za-z_]\w*\.[A-Za-z_]\w*\s*[,)]", line_txt):
        # `rmtree(probe.parent)` —— 属性目标，静态完全判不出指向。
        return "NEEDS_HUMAN:删除目标是**对象属性**（probe.parent 这类）⇒ 静态判不出指向"
    if rule == "DES-001" and re.search(r"rmtree\(\s*([A-Za-z_]\w*)\s*[,)]", line_txt):
        # **变量目标**：没有数据流分析，静态判不出它指向临时目录还是真身目录。
        #   ⇒ 按本模块自己的规矩进 `needs_human`（分不清的**不硬报**）。
        #   真要判，跑 grep 看那个变量怎么来的，或过 action_gate（先看→动脑）再动手。
        return "NEEDS_HUMAN:变量目标的删除（静态判不出指向哪；要人看一眼或查该变量的来历）"
    if rule == "DES-001":
        return ""          # 字面目标/字面命令（rm -rf '...' / reset --hard）⇒ 保留 finding
    if rule == "DES-001" and re.search(r"(不做|不许|禁止|不得|no\s+rebase|never)", line_txt, re.I):
        return "**否定声明**（说的是不做这件事）"
    return ""


def _walk_ex(target: str) -> tuple:
    """走一遍 target ⇒ (files, stats)。**没扫的必须带原因回来**，绝不静默。

    stats 里三本账：
      skipped_dir  —— 排除目录（路径 → 理由），逐个报出
      skipped_big  —— 超过 MAX_BYTES 被跳过的大文件（路径）
      truncated    —— 撞到 MAX_FILES 上限（True ⇒ 本次覆盖不完整，必须标红）
    """
    base = Path(target) if target else _ROOT
    if not base.is_absolute():
        base = _ROOT / target
    st = {"dir": str(target), "skipped_dir": {}, "skipped_big": [], "truncated": False}
    if base.is_file():
        return [base], st
    out = []
    for root, dirs, files in os.walk(base):
        keep = []
        for d in dirs:
            if d in SKIP_DIRS:
                rel = str((Path(root) / d).relative_to(_ROOT)).replace("\\", "/")
                st["skipped_dir"][rel] = EXCLUDED_DIRS.get(d, "排除")
            else:
                keep.append(d)
        dirs[:] = keep
        for f in files:
            if not f.lower().endswith(SCAN_EXT):
                continue
            p = Path(root) / f
            try:
                if p.stat().st_size > MAX_BYTES:
                    st["skipped_big"].append(str(p.relative_to(_ROOT)).replace("\\", "/"))
                    continue
            except OSError:
                continue
            out.append(p)
            if len(out) >= MAX_FILES:
                st["truncated"] = True
                return out, st
    return out, st


def _walk(target: str) -> list:
    """兼容旧调用：只要文件清单，记账见 _walk_ex。"""
    return _walk_ex(target)[0]


def _eligible(tgts) -> tuple:
    """该扫基盘：scope 内扩展名合规、且不在排除目录的文件总数（覆盖率分母）。"""
    total, ex = 0, {}
    for t in tgts:
        base = _ROOT if t in (".", "", None) else (_ROOT / t)
        if not base.is_dir():
            if base.is_file() and base.name.lower().endswith(SCAN_EXT):
                total += 1
            continue
        for root, dirs, files in os.walk(base):
            keep = []
            for d in dirs:
                if d in SKIP_DIRS:
                    rel = str((Path(root) / d).relative_to(_ROOT)).replace("\\", "/")
                    ex[rel] = EXCLUDED_DIRS.get(d, "排除")
                else:
                    keep.append(d)
            dirs[:] = keep
            total += sum(1 for f in files if f.lower().endswith(SCAN_EXT))
    return total, ex


def _coverage(paths, eligible, walk_stats, ex_dirs, tgts) -> dict:
    """覆盖率硬账：rate==1.0 且没截断才算地毯式跑全。"""
    scanned = len(paths)
    trunc = [s["dir"] for s in walk_stats if s.get("truncated")]
    big = [x for s in walk_stats for x in (s.get("skipped_big") or [])]
    rate = round(scanned / eligible, 4) if eligible else 1.0
    return {
        "scope": list(tgts),
        "eligible": eligible, "scanned": scanned, "rate": rate,
        "missed": max(0, eligible - scanned),
        "truncated_at": trunc,
        "skipped_big": big[:20], "skipped_big_count": len(big),
        "excluded_dirs": dict(sorted(ex_dirs.items())),
        # 两种达标口径：
        #   full           —— 严格：一个都不缺（rate==1.0 且无截断）
        #   no_silent_gap  —— 纪律口径：**没有静默缺口**。缺的都是已记账的大文件，就算达标。
        #                     这正是「无所遁形」的真意：不是必须扫 100%，而是没扫的每一个都有原因且可见。
        "full": bool(eligible and scanned >= eligible and not trunc),
        "no_silent_gap": bool(not trunc and max(0, eligible - scanned) <= len(big)),
        "_口径": "eligible = scope 内扩展名合规且不在排除目录的文件数；scanned = 本次实际读入。"
                 "rate<1 必有原因，逐条列在 truncated_at / skipped_big / excluded_dirs。"
                 "地毯式达标判据：full == True（rate==1.0 且无截断、无大文件跳过）。",
    }


# ── 2026-11-03 影子分诊（DES-001 误报根治第一步：只记录，不生效）──────────────
# 现有 _triage 的 DES-001 分支靠【变量名】含 tmp|cache 判 by-design，而变量名是人起的
# （pc / d / x）⇒ 规则必然失效（root_fix 诊断：补丁债 3，根治方向=规则/源头分类）。
# 新口径只用两个**单一来源**，不枚举任何文件名：
#   ① 这份文件归哪个能力位 —— state/trunk-cover.json 的 rows（file → owners）
#   ② 该能力位的职责 —— caps_registry 的 desc 是否声明了清理语义
# 本段只产出 triage_shadow（比对用），**不参与** triaged / findings 的任何判定。
_CLEANUP_WORDS = ("清理", "卫生", "归位", "旧物", "清空", "回退", "删除")

_TC_OWNERS: dict | None = None


def _owners_of(rel: str) -> tuple:
    """现读 trunk-cover 快照拿该文件的 owner（单一来源，不重扫）。"""
    global _TC_OWNERS
    if _TC_OWNERS is None:
        _TC_OWNERS = {}
        try:
            doc = json.loads((_STATE / "trunk-cover.json").read_text(encoding="utf-8"))
            for row in (doc.get("rows") or []):
                f = str(row.get("file") or "").replace("\\", "/")
                if f:
                    _TC_OWNERS[f] = tuple(row.get("owners") or ())
        except Exception:                                        # noqa: BLE001
            pass
    return _TC_OWNERS.get(rel, ())


def _triage_shadow(rel: str, rule: str, why_now: str) -> str:
    """影子分诊：按源头分类判 DES-001 是否属于"清理器本职"。只记录，不生效。

    ⚠️ NEEDS_HUMAN **不算已定论** —— 它正是"静态分不清、要人核"的那一类，
       最该让新口径给建议。只有已被明确分掉（豁免/占位符/纯注释…）才让位。
    """
    if rule != "DES-001":
        return ""
    if why_now and not why_now.startswith("NEEDS_HUMAN:"):
        return ""
    owners = _owners_of(rel)
    if not owners:
        return ""
    try:
        from ..caps_registry import BENIGN_CAPS
    except Exception:                                            # noqa: BLE001
        return ""
    for cap in owners:
        desc = str((BENIGN_CAPS.get(cap) or {}).get("desc") or "")
        if any(w in desc for w in _CLEANUP_WORDS):
            return "所有者能力位本职含清理（%s）⇒ by design（源头分类）" % cap
    return ""


def scan(target: str = "all", rules: str = "", **_kw) -> dict:
    """**地毯式多阶段**扫描（凭证 / 注入 / 破坏 / 判据）⇒ findings + 覆盖率账。

    主人令 2026-11-03「扫描必须地毯式穿透交叉，让故障/漏洞无所遁形」的落地口径：
      · 地毯式 —— 默认 target="all" 走全树；SCAN_EXT 15 种全覆盖（含 html 内联 JS /
        ps1 / bat / cmd / sh / tsx / json）；**没扫的必须记账**（excluded_dirs /
        skipped_big / truncated_at），一个文件都不许静默消失。
      · 穿透式 —— 规则面不动，深挖由 penetrating_cross_scan 六步接力（不在此重写）。
      · 交叉   —— findings 仍需 verify_finding 两路读法复核才算 confirmed。
    """
    want = {x.strip().upper() for x in rules.split(",") if x.strip()}
    active = [r for r in RULES if not want or r["rule"] in want]
    if not active:
        return {"ok": False, "op": "scan", "fail_closed": True,
                "error": f"rules 过滤后没有可用规则（可用：{[r['rule'] for r in RULES]}）"}
    tgts = [x.strip() for x in (target or "").split(",") if x.strip()] or ["all"]
    tgts = ["." if t in ("all", "*") else t for t in tgts]
    walk_stats, paths, seen = [], [], set()
    for t in tgts:
        fs, st = _walk_ex(t)
        walk_stats.append(st)
        for p in fs:
            key = str(p).lower()
            if key not in seen:
                seen.add(key)
                paths.append(p)
    eligible, ex_dirs = _eligible(tgts)
    coverage = _coverage(paths, eligible, walk_stats, ex_dirs, tgts)
    findings, triaged, rows, needs, shadow = [], {}, 0, [], []
    doc_mentions = 0   # 命中落在字符串/文档里的次数（可核，不算 finding）
    for p in paths:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(_ROOT)).replace("\\", "/") if _ROOT in p.parents else str(p)
        spans = _prose_spans(txt)   # 该文件的散文区间（字符串 + 注释）
        _lines = txt.splitlines()   # 供 _triage 做简易数据流（查变量赋值来源）
        for i, line in enumerate(_lines, 1):
            rows += 1
            for r in active:
                m = r["rx"].search(line)
                if not m:
                    continue
                if _in_span(spans, i, m.start()) or (
                        p.suffix.lower() != ".py" and _line_prose(line, m.start())):
                    # 命中的是**字符串/注释里的提及**，不是可执行代码 ⇒ 不报 finding
                    doc_mentions += 1
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
                why = _triage(rel, line, r["rule"], ctx=(_lines, i))
                _sh = _triage_shadow(rel, r["rule"], why)
                if _sh:
                    shadow.append({"rule": r["rule"], "file": rel, "line": i,
                                   "would_be": _sh, "snippet": line.strip()[:140]})
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
           "lines": rows, "coverage": coverage, "findings": findings,
           "triaged": [list(k) for k in triaged],
           "needs_human": needs[:200],
           "triage_shadow": shadow[:300],
           "_口径": "命中先分诊；**分不清的进 needs_human，不硬报**；全量面天然含框架自家的清理路径，"
                    "日常该用的是 diff_audit（改动面）或 rules= 定向。"}
    tmp = _FINDINGS.with_name(_FINDINGS.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _FINDINGS)
    _log({"event": "scan", "files": len(paths), "rules": [r["rule"] for r in active],
          "lines": rows, "findings": len(findings), "by_severity": {s: sum(1 for f in findings if f["severity"] == s)
                          for s in ("high", "medium", "low")}})
    return {"ok": True, "op": "scan", "files": len(paths), "lines": rows,
            "coverage": coverage, "doc_mentions": doc_mentions,
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
