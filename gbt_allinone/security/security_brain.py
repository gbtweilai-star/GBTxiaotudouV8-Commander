# gbt-capability: dynamic-code, dynamic-import, subprocess, network, socket, base64, ctypes
"""
brain/hacker_brain.py — 黑客大脑
=================================
红队+蓝队双模: 攻击面测绘 | 漏洞扫描 | 利用链构建 | 防御验证

能力维度:
  1. 攻击面测绘 — 扫描项目暴露的所有攻击向量
  2. 漏洞扫描 — 自动检测OWASP Top 10 + CWE常见漏洞
  3. 利用链构建 — 从单个漏洞到完整攻击链
  4. 蓝队防御 — 验证防御措施是否有效
  5. 渗透报告 — 生成专业渗透测试报告
"""
import re  # ⛔ 2026-08-05 打磨: 补齐缺失stdlib导入(系统性缺陷)
import ast  # R-H295：文档串判定要真解析，不靠引号计数猜
import warnings  # R-H295：ast.parse 的无效转义警告要显式接管，不漏 stderr、不静默失效
import json
import time
from pathlib import Path
from typing import Optional
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent  # V8: 仓库根

# ── 扫描范围唯一口径（2026-10-09 根因修复 · 自改护照 fc-20261009T044909-d95w）────
# 病根：本模块自己写了一份排除名单（scan_vulnerabilities 里的 _fp_l 段），
#       却**漏掉了外部语料** —— 实测 _upstream 29032 个 .py（5.1GB）、
#       vendor 3134、_legacy_sources 3762、quant_workspace 23。
#       后果三条，都是「报警」层面的真故障：
#         ① sec_surface 把外部语料算进攻击面 ⇒ risk_score 恒为 100/「高危」
#            （报警疲劳：报警永远响 = 报警等于不响），自有代码面被淹；
#         ② sec_scan 走 rglob("*.py") 全仓遍历 ⇒ 实测 **887s / CPU 606s 仍未跑完**
#            被强制终止（对照：剪枝后 1129 个 .py，1.25s 走完）；
#         ③ 漏洞结论里混进上游第三方代码，真信号被噪声埋掉。
# 修法遵守本仓铁律「谁扫仓谁用 scan_scope，不许各自再写一份」：
#   剪枝发生在**进入子目录之前**；排除项**带理由、可回溯**。
#   体量计量很贵（现取 corpus_sizes 要 17s 走 5GB），故只在已量过时附带，
#   与 sec_sweeper 「只报名单 + 理由」的口径一致，不重复付费。
from ..tools import scan_scope as _scan_scope


def _owned_py_files(root: Path):
    """自有代码面（已按 scan_scope 剪枝）的 .py 文件。

    外部语料（_upstream / vendor / _legacy_sources / quant_workspace / .shadow-repo）
    与缓存归档（.git / .scratch / .backups / store / node_modules …）**根本不进**。
    显式点名某个外部目录当 target 时按 target 走（剪枝只剔其**子目录名**命中的块）。
    """
    return _scan_scope.iter_files(root, suffixes=(".py",))


def _scope_boundary(root: Path) -> dict:
    """扫描边界口径（跳了什么、为什么）——便宜：只查存在性，不逐块数文件。"""
    try:
        present = {name: (Path(root) / name).is_dir() for name in _scan_scope.EXTERNAL_CORPORA}
    except OSError:
        present = {}
    cached = getattr(_scan_scope, "_CORPUS_CACHE", {}).get(str(Path(root)))
    quantified = None
    if cached:
        quantified = {k: {"py_files": v.get("py_files"), "bytes": v.get("bytes")}
                      for k, v in cached.items()}
    return {
        "skip_dirs": sorted(_scan_scope.SKIP_DIRS),
        "external_corpora": dict(_scan_scope.EXTERNAL_CORPORA),
        "present_on_disk": present,
        "quantified": quantified or "未逐块计量（要字节数/文件数请调 scan_scope.corpus_sizes）",
        "rule": "谁扫仓谁用 scan_scope；剪枝在进入子目录之前；排除项带理由且可回溯",
    }


# ── 自检探针产物的清扫 ────────────────────────────────────────────────────
# 病根（2026-09-22 实测）：管线门禁的自检往 `pipeline_submit` 提交一个名为
# `_def_probe.txt` 的**负对照探针**（指望被拦）。每跑一轮，store/pipeline/ 下的
# gate / mirror / quarantine / records **各留一份产物**；而**没有任何地方清它**
# ⇒ 实测堆到 96 轮 × 4 目录 = 384 个文件。
# 它们被 `trace_store.SELFTEST_HINTS` 正确归为 trace（不当现行故障）✅，
# 但：① 成品判据禁 `_*` 残留；② 越堆越多会把真故障淹掉 —— "给故障喘息的机会"就是这么来的。
# 修法：探针**自己扫自己的产物**（源头清理），并由 hygiene 兜底复查。
SELFTEST_PROBE_GLOB = "_def_probe*"


def _sweep_selftest_probe_artifacts() -> dict:
    """清掉 store/pipeline 下自检探针留下的产物。**任何失败都不抛**（自检不该被清理失败带崩）。"""
    out = {"removed": 0, "errors": []}
    try:
        from .._paths import STORE_DIR
    except Exception as exc:  # noqa: BLE001
        return {"removed": 0, "errors": ["读不到 STORE_DIR: %s" % type(exc).__name__]}
    base = Path(STORE_DIR) / "pipeline"
    if not base.is_dir():
        return out
    for p in base.rglob(SELFTEST_PROBE_GLOB):
        try:
            if p.is_file():
                p.unlink()
                out["removed"] += 1
        except OSError as exc:
            out["errors"].append("%s: %s" % (p.name, str(exc)[:40]))
    return out



# R-H295 · 逐行豁免标记。
# PROC_SCAN_OFF 是**本仓既有**的约定：行尾带这个标记 = 「这一行是模式表/原语清单的
# 定义，不是在调用它」。扫描器此前只豁免 JSON 形态，于是 Python 元组形态的原语表
# 被当成真漏洞上报。现在两种形态都认，且豁免条数照样记账。
_SCAN_OFF = "PROC_SCAN_OFF"
# TAINT_SAFE: 后面跟理由 —— 人工复核过的「无污点到达路径」。理由随行留档，
# 让「为什么放过」可审计；绝不允许无理由静默白名单。
_TAINT_SAFE = re.compile(r"TAINT_SAFE:\s*(.+)$")
# 注释行不可能「被执行」：执行类模式（命令注入/代码执行/SQL 注入/反序列化）落在注释里
# 一律不是漏洞。但**泄露类**模式（硬编码密钥、明文口令）落在注释里仍然是真泄露 ——
# 注释同样会被读走、会被提交进仓库。所以只豁免执行类，不豁免泄露类。
# R-H295：原来 `line.lstrip().startswith("#")` 被折进 `_is_sandboxed`，
# 而 `_is_sandboxed` **只豁免 CWE-95**，于是注释里的 `os.system(...)` 照样报
# critical 命令注入 —— 实测 3 条 critical 全是注释（其中一条还在本文件自己的说明里）。
_EXEC_CWE = ("CWE-78", "CWE-77", "CWE-94", "CWE-95", "CWE-89", "CWE-502",
            # 2026-10-09 根因修复：CWE-396（裸 except）也是**执行语义**的代码气味 ——
            # 落在注释/文档串里同样永远不会执行。此前只在执行类名单里，于是
            # `# 原来这里是 except: pass` 这类**说明文字**被报成 medium 裸 except
            # （实测 auth_gate.py:99 等）。与执行类同一判据，一并豁免。
            "CWE-396")
# 泄露类 CWE：密钥/敏感信息 —— 这类**在字符串里正是要找的东西**，所以在注释/文档串里也照扫。
_LEAK_CWE = ("CWE-532", "CWE-798", "CWE-256", "CWE-522")
# 「不是硬编码、而是**当场生成**」的形态：`token = "gbtc_" + secrets.token_urlsafe(32)`。
# 敏感信息正则要求字面量后面紧跟收尾引号，于是它只匹配到 `"gbtc_"` 这个**前缀**就报 high。
# 收紧判据：必须是「收尾引号 + 加号 + 生成器/读取器」才算生成，避免误放真硬编码。
_SECRET_GENERATED = re.compile(
    r"""["']\s*\+\s*[^"']*\b(?:secrets\.|token_urlsafe|token_hex|urandom|uuid4|environ|getenv|keyring)""")
# ② 顺序占位串：整个字母表/数字表**按序**出现 —— 真密钥不会这么长且有序。
#    由来（2026-10-09 实测）：4 条 critical 里 2 条是自检夹具里的
#    `sk-abcdefghijklmnopqrstuvwxyz0123`（scan_engine 自检样本 / data_policy 测试输入）。
_SECRET_PLACEHOLDER = re.compile(
    r"(?:abcdefghijklmnopqrstuvwxyz|0123456789|1234567890|qwertyuiop)", re.IGNORECASE)
# ③ 片段拼接：字面量后紧跟 `+` = 只是前缀/片段，不是完整密钥
#    （实测 `token="gbtv8-" + "0" * 32` 被报 high 敏感信息泄露 —— 报片段等于报噪声）。
_SECRET_FRAGMENT = re.compile(r"""["']\s*\+\s*(?:["']|_|\w+\s*\*|str\(|chr\()""")
# ④ 连字符标签：`_ROBOTS_TOKEN = "GBT-Xiaotudou"` —— **纯字母 + 连字符**的产品/代理名不是凭据。
#    真密钥不会长成 `Foo-Bar` 这样；实测（2026-10-09 靶标矩阵跑完 + 加 (?i) 之后）全仓只剩这一条噪声。
_SECRET_LABEL = re.compile(r"""["'][A-Za-z]{2,}(?:-[A-Za-z]{2,})+["']""")

class HackerBrain:
    """黑客大脑 — 攻击+防御双模式"""

    def __init__(self):
        self.project_root = ROOT
        self.vuln_db = self._load_vuln_patterns()
        # 🔴 2026-10-09 根因修复（fail-open 的检测器 = 假绿）：模式表里**一条正则写坏**，
        #    逐行 re.search 就抛 PatternError，而外层的 `except Exception: pass`
        #    把它按文件静默吞掉 ⇒ 全仓 0 条结论，读起来却像「扫过、干净」。
        #    实测：本次改 CWE-338 规则时漏了一个右括号，sec_scan 当场从 76 条变 0 条。
        #    修法：装载时**预编译**并登记坏模式；坏一条就如实报 degraded，不折成绿。
        self._compiled: list = []
        self.pattern_errors: list = []
        for _p in self.vuln_db:
            try:
                self._compiled.append((_p, re.compile(_p["regex"])))
            except re.error as _exc:
                self.pattern_errors.append({"title": _p.get("title"),
                                            "regex": str(_p.get("regex"))[:120],
                                            "error": str(_exc)[:120]})

    def map_attack_surface(self, target: str = None) -> dict:
        """攻击面测绘"""
        t0 = time.time()
        if target:
            _p = Path(target)
            root = _p if _p.is_absolute() and _p.exists() else (self.project_root / _p if (self.project_root / _p).exists() else self.project_root)
        else:
            root = self.project_root
        vectors = {"entry_points": 0, "file_operations": 0, "network": 0, "user_inputs": 0, "auth_boundaries": 0}
        details = []
        files_scanned = 0

        # 2026-10-09 根因修复：原来 rglob 全仓 ⇒ 外部语料（_upstream 29032 个 .py）
        # 被当成自有代码面 ⇒ risk_score 恒 100/「高危」。改走 scan_scope 剪枝。
        for py_file in _owned_py_files(root):
            if "deploy_bak" in str(py_file) or py_file.name.startswith("_"):
                continue
            try:
                content = py_file.read_text(encoding='utf-8', errors='replace')
                files_scanned += 1
                rel = str(py_file.relative_to(root))
                if re.search(r'@app\.(route|get|post)|def main\(|argparse|click\.command|if __name__', content):
                    vectors["entry_points"] += 1; details.append({"file": rel, "type": "entry_point"})
                if re.search(r'open\(|Path\(.*write|shutil\.(copy|move|rmtree)|os\.(remove|rename)', content):
                    vectors["file_operations"] += 1; details.append({"file": rel, "type": "file_operation"})
                if re.search(r'requests\.(get|post)|socket\.|urllib|websocket|subprocess\.run', content):
                    vectors["network"] += 1; details.append({"file": rel, "type": "network"})
                if re.search(r'input\(|request\.(args|form|json|data)|sys\.argv', content):
                    vectors["user_inputs"] += 1; details.append({"file": rel, "type": "user_input"})
                if re.search(r'@login_required|@jwt_required|authenticate|authorize|token|api_key|password', content):
                    vectors["auth_boundaries"] += 1
            except Exception: pass  # 容错: 非关键路径
        total = sum(vectors.values())
        # 🔴 2026-10-09 二次根因：risk_score 原来是**原始计数**（min(100, 加权和)），
        #    任何过 30 个文件的仓都恒等 100 —— 报警永远响 = 报警等于不响
        #    （本模块 signal_patrol 的注释早就点破「不是可行动警报」）。
        #    现在按**密度**判档（跨仓可比、不随仓大小饱和）；原始聚合分只作参考保留。
        weighted = (vectors["user_inputs"] * 4 + vectors["network"] * 3
                    + vectors["file_operations"] * 3 + vectors["entry_points"] * 2)
        files_seen = max(1, files_scanned)
        density = round(weighted / files_seen, 2)
        level = "高危" if density >= 6 else ("中危" if density >= 3 else "低危")
        return {"ok": True, "attack_surface": vectors, "total_vectors": total,
                "risk_score": min(100, weighted),
                "risk_score_note": "原始加权计数（会随仓大小饱和到 100，仅作参考）",
                "files_scanned": files_scanned,
                "risk_density": density,
                "risk_level": level,
                "risk_basis": "risk_level 按 risk_density（加权攻击面/文件数）判档，跨仓可比",
                "top_vectors": details[:10],
                "scope": "own_code_only", "boundary": _scope_boundary(root),
                "elapsed_ms": round((time.time()-t0)*1000, 1)}

    def scan_vulnerabilities(self, severity_filter: str = "medium",
                             limit: int | None = None,
                             include_non_production: bool = False) -> dict:
        """漏洞扫描。

        severity_filter：按「该级别及以上」过滤（sev_levels 从重到轻排列）。
        limit：返回条数上限；默认 20（与历史行为一致），传 0 视为默认，
              传更大的值可取回被截断的 critical 清单。
        include_non_production：是否连非生产层（.scratch 构建暂存/备份/快照/镜像、
              archive 存档、tests 测试夹具）一起扫。

        R-H295 · 修根因（第二个）：**扫描结论被非生产层的副本淹没了**。
        实测 890 条里前 500 条有 **405 条（81%）** 落在 `.scratch/_*backup*` /
        `_*snapshot*` / `*.mirror.*` 这类**我自己构建时的备份目录**里 ——
        它们是同一份代码的副本，被当成独立漏洞重复计入；剩下的绝大多数又是
        `tests/` 里**故意写死的假密钥**（夹具本来就该长这样）。
        而 README 一直写着「只扫自有代码」。**口径与行为不一致**，
        于是 33 个 critical 里 20 个看过去全是备份里的假密钥 —— 真信号被噪声埋掉。

        修法不是「静默少扫几个目录」（那等于给攻击者一个藏身之所：把代码挪进被排除
        目录即可隐身），而是**分层如实报**：
          · 默认只把「生产层」的结论算进 total/critical/risk；
          · 非生产层**扫不扫、跳过多少文件、跳过原因**一律如实写进返回；
          · 想看全量传 include_non_production=True，逐层条数照报。
        """
        t0 = time.time()
        vulns = []
        sev_levels = ["critical", "high", "medium", "low", "info"]
        if severity_filter not in sev_levels:
            severity_filter = "medium"
        min_sev = sev_levels.index(severity_filter)

        # 非生产层：不静默丢弃，而是「默认不扫 + 如实报跳过了多少」
        _NON_PROD = (
            ("scratch", ("/.scratch/",)),
            ("backup", ("/.backups/", "/backups/")),
            ("archive", ("/archive/",)),
            ("test", ("/tests/",)),
        )
        skipped = defaultdict(int)
        exempt = defaultdict(int)
        taint_notes = []
        parse_warnings = []

        # 2026-10-09 根因修复：原来 self.project_root.rglob("*.py") 把外部语料一并
        # 遍历（实测 _upstream 29032 个 .py / 5.1GB ⇒ 本次 887s 未完被终止）。
        # 改走 scan_scope 唯一口径：剪枝发生在**进入子目录之前**。
        for py_file in _owned_py_files(self.project_root):
            if "deploy_bak" in str(py_file) or py_file.name.startswith("_"):
                continue
            # ⛔ 排除第三方库/虚拟环境/存档 — 只扫框架自有代码（scan_scope 已剪枝，
            #    这段保留作纵深防御：显式 target 指向外部目录时仍按路径段兜底）
            # 🔴 2026-10-09 根因修复：排除段必须按**相对扫描根**判，不能按绝对路径。
            #   镜像房间落在 store/mirror_space/rooms/ 下，绝对路径含 "/store/" 会被这条
            #   兜底误杀 ⇒「在镜像里扫黑客靶标」永远 0 条（实测：靶标 os.system/pickle/sk- 密钥
            #   全在盘上，scan 却报 total=0）。这正是 Owner 要的『到镜像多维度里测』跑不通的原因。
            try:
                _rel_l = py_file.relative_to(self.project_root)
            except ValueError:
                _rel_l = py_file
            _fp_l = "/" + str(_rel_l).replace("\\", "/").lower()
            if any(_seg in _fp_l for _seg in ("/lib/", "/site-packages/", "/node_modules/",
                                               "/backups/", "/archive/", "/.venv/", "/venv/",
                                               ".pylibs/", "archived_logs/", "/store/",
                                               ".openclaw/", ".openclaw-attachments/", ".wrangler/",
                                               "wf_runs/", "latest_logs/", "__pycache__",
                                               ".git/", "agnes_video/", "website/")):
                continue
            _tier = "production"
            for _tname, _marks in _NON_PROD:
                if any(_m in _fp_l for _m in _marks):
                    _tier = _tname
                    break
            if _tier != "production" and not include_non_production:
                skipped[_tier] += 1
                continue
            try:
                content = py_file.read_text(encoding='utf-8', errors='replace')
                rel = str(py_file.relative_to(self.project_root))
                # 安全/攻击工具目录白名单: 这些是测试工具, 非生产漏洞
                whitelist_dirs = ["sqli_tester", "xss_tester", "waf_bypass", "bounty_hunter",
                                  "strix", "anti_track", "pentest_kali", "attack", "hack",
                                  "device_takeover", "data_hijack", "n8n_attack_chain",
                                  "security_scan", "intelligent_scan"]
                # 🔴 2026-10-09 根因修复：白名单原来对**绝对路径做子串匹配** ⇒ 路径里只要
                #   出现 "hack"/"attack" 这类词就整份跳过。实测：镜像房间 id 叫
                #   hacker-mirror-… ⇒ 黑客大脑扫自己刚 shapes 进去的靶标报 total=0
                #   （扫描器拒扫「名字像安全工具」的路径）。改成**按路径段精确匹配**——
                #   这些白名单项本来就是目录名（sqli_tester / waf_bypass / pentest_kali …）。
                _rel_parts = {p for p in str(_rel_l).replace("\\", "/").lower().split("/") if p}
                is_security_tool = any(wd in _rel_parts for wd in whitelist_dirs)
                # R-H295：文档串行号（真解析，不猜引号）。
                # 只认「表达式语句就是一个字符串常量」—— 那是文档串/注释性字符串，永不执行。
                # **不能**把 f-string 实参也算进来：`os.system(f"...")` 的实参也是字符串，
                # 而它正是要抓的真漏洞；一律豁免等于把扫描器弄瞎。
                _doc_lines = set()
                # 注意：ast.parse 对被扫文件里的**无效转义序列**会发 SyntaxWarning
                # （文件名显示为 `<unknown>`，因为 ast.parse 的默认 filename 就是它）。
                # 之前这里直接 ast.parse，于是：① 警告漏到 stderr 成了噪声；
                # ② 一旦外部把 SyntaxWarning 提成 error（-W error），就会抛进下面的
                #    `except Exception`，**整个文件的文档串豁免静默失效** —— 那不是「没有豁免」，
                #    是「豁免坏了没人知道」。现在显式接管警告：照常拿到语法树，
                #    并把「哪个文件哪一行有坏转义」记账上报。
                with warnings.catch_warnings(record=True) as _cw:
                    warnings.simplefilter("always")
                    # R-H295：本仓 10 个 .py 带 UTF-8 BOM（既有约定），
                    # 带 BOM 的文本喂 ast.parse 会抛 U+FEFF 语法错 ⇒ 文档串豁免对
                    # caps_registry.py 这类文件整份失效。修读方：lstrip BOM，不删文件里的 BOM。
                    try:
                        _tree = ast.parse(content.lstrip("\ufeff"))
                    except SyntaxError:
                        _tree = None      # 真语法错（扫的是半成品/模板）⇒ 不豁免，照扫
                for _w in _cw:
                    if issubclass(_w.category, SyntaxWarning):
                        parse_warnings.append({
                            "location": "%s:%s" % (rel, getattr(_w, "lineno", 0) or 0),
                            "warning": str(_w.message)[:120]})
                if _tree is not None:
                    for _n in ast.walk(_tree):
                        if (isinstance(_n, ast.Expr) and isinstance(_n.value, ast.Constant)
                                and isinstance(_n.value.value, str)):
                            _end = getattr(_n.value, "end_lineno", None) or _n.lineno
                            _doc_lines.update(range(_n.lineno, _end + 1))
                # 🔴 2026-10-09 根因修复（性能 O(行数²)）：原来**每行**都重跑一次
                #    content.split(chr(10)) 去取前 5 行上下文 —— 单文件代价是行数的平方。
                #    实测 1101 个 .py 一次扫描 112s；仓里 3 万行的文件会直接报废。
                #    修法：循环外切一次，循环内只做切片（判据完全不变）。
                _lines = content.split(chr(10))
                for line_no, line in enumerate(_lines, 1):
                    if is_security_tool:
                        break  # 安全工具目录跳过漏洞扫描
                    # ⛔ 受限执行豁免: 沙盒/无builtins/模式定义/沙盒内exec(compile 是设计行为, 非漏洞
                    _prev_ctx = "\n".join(_lines[max(0, line_no-5):line_no]) if line_no > 1 else ""
                    _is_sandboxed = ("sandbox_exec" in line or "mirror_exec" in line
                                     or "sandbox" in line.lower()
                                     or "'__builtins__': {}" in line or "\"__builtins__\": {}" in line
                                     or "exec(compile(" in line or "exec(compile (" in line
                                     or "safe_globals" in line or "safe_locals" in line  # 受限命名空间eval
                                     or "safe_builtins" in line or "safe_builtins" in _prev_ctx  # 受限builtins exec(含前文)
                                     or "self.exec(" in line  # 远程执行工具自身调用(设计)
                                     or "exec(open(" in line  # 子代理参数模板示例(设计)
                                     or line.lstrip().startswith("#")  # 注释行
                                     or re.match(r'\s*def \w*(exec|eval)\w*\(', line)  # 函数定义名含exec/eval
                                     or re.search(r'\w*[a-z_]+_(exec|eval)\w*\(', line)  # ⛔ 2026-08-09 调用自有exec系函数(设计内, 非动态执行; re.search防行首缩进锚定)
                                     or re.search(r'\w*_(exec|eval)\w* = ', line)  # 绑定exec系函数名(变量定义)
                                     or '"exec("' in line or '"eval("' in line  # 模式库定义 "exec("
                                     or "'exec('" in line or "'eval('" in line  # 模式库定义 'exec('
                                     or "exec\\(" in line or "eval\\(" in line  # 模式库定义 r'exec\(
                                     or '"exec(open"' in line or '"exec(open' in line  # ⛔ 2026-08-09 模式库字符串拼接 "exec(open"+E(设计内)
                                     or "builtins" in line and "exec" in line)
                    # 逐行豁免（一律记账，绝不静默丢弃）：
                    #   ① PROC_SCAN_OFF —— 本仓既有的「这是模式表/原语清单，不是在调用它」标记
                    #   ② TAINT_SAFE: <理由> —— 已人工复核为无污点到达路径，理由随行留档
                    #   ③ JSON 形态的模式库定义行
                    # R-H295：① 原本**只有 JSON 形态被豁免**，Python 元组形态的原语表
                    # （PROC_PRIMITIVES = ("subprocess","os.system",…)）被当成 3 条 critical
                    # 命令注入 —— 扫描器在读自己的模式表。标记早就写在行尾了，只是没人认。
                    if _SCAN_OFF in line:
                        exempt["pattern_table"] += 1
                        continue
                    _ts = _TAINT_SAFE.search(line)
                    if _ts:
                        exempt["taint_safe"] += 1
                        taint_notes.append({"location": f"{rel}:{line_no}",
                                            "reason": _ts.group(1).strip()[:140]})
                        continue
                    if '"title"' in line and '"regex"' in line:
                        exempt["json_pattern_def"] += 1
                        continue
                    _is_comment = line.lstrip().startswith("#")
                    _is_doc = line_no in _doc_lines
                    _commented_exec = False
                    _secret_exempt = ""
                    for pattern, _rx in self._compiled:
                        _cwe = str(pattern.get("cwe_id", ""))
                        if _is_sandboxed and "CWE-95" in _cwe:
                            continue  # 受限动态执行 → 设计行为
                        # 注释/文档串里的执行类模式：不会被执行的文本，不是漏洞。
                        # （泄露类不在此列 —— 密钥写进注释照样会被读走、会被提交，照扫）
                        if (_is_comment or _is_doc) and any(_c in _cwe for _c in _EXEC_CWE):
                            _commented_exec = True
                            continue
                        if not _rx.search(line):
                            continue
                        # 🔴 2026-10-09 记账口径修复：豁免判据必须在**命中之后**才生效。
                        #    原来判据放在匹配之前、且在「遍历到泄露类模式」时就无条件求值，
                        #    于是 `secret_fragment` 记成了「全文有多少行含 + 拼接」=438 行 ——
                        #    那是**假账**（本仓一行密钥都没被它豁免掉）。
                        #    现在：先确认本来会报，再判三条「不是硬编码密钥」：
                        #      ① 后接生成器/读取器  ② 顺序占位串  ③ 被 + 拼接的片段
                        if any(_c in _cwe for _c in _LEAK_CWE):
                            if _SECRET_GENERATED.search(line):
                                _secret_exempt = "generated"
                                continue
                            if _SECRET_PLACEHOLDER.search(line):
                                _secret_exempt = "placeholder"
                                continue
                            if _SECRET_FRAGMENT.search(line):
                                _secret_exempt = "fragment"
                                continue
                            if _SECRET_LABEL.search(line):
                                _secret_exempt = "label"
                                continue
                        if sev_levels.index(pattern["severity"]) <= min_sev:
                            vulns.append({"id": f"VULN-{len(vulns)+1:04d}", "title": pattern["title"], "severity": pattern["severity"], "cwe": pattern["cwe_id"], "location": f"{rel}:{line_no}", "match": line.strip()[:80], "fix": pattern["fix"], "cvss": pattern["cvss"], "tier": _tier})
                    # 按「行」记账，不按「行×模式」—— 否则条数会被模式总数放大成假规模
                    if _commented_exec:
                        exempt["comment_or_doc_exec"] += 1
                    if _secret_exempt:
                        exempt["secret_" + _secret_exempt] += 1
            except Exception: pass  # 容错: 非关键路径
        sev_count = defaultdict(int)
        prod_vulns = [v for v in vulns if v.get("tier") == "production"]
        for v in prod_vulns:
            sev_count[v["severity"]] += 1

        # R-H295 · 修根因：原来 `vulns[:20]` 是**按扫描顺序**硬截断 20 条 ——
        # 实测 788 条里前 20 条全是 medium，**33 个 critical 一条也看不到**，
        # 于是 sec_chain 吃 p.get("vulns") 时拿到的永远是 medium，
        # 报「未发现完整链」不是因为没有链，是因为它根本没拿到料。
        # 修法：先按严重度排序（critical 在前），再截断；并把截断事实如实报出来。
        _rank = {s: i for i, s in enumerate(sev_levels)}
        # 结论只由生产层驱动：非生产层的副本/夹具不计入 critical 计数与风险判定。
        vulns = prod_vulns if not include_non_production else vulns
        vulns.sort(key=lambda v: (_rank.get(v["severity"], len(sev_levels)),
                                  str(v.get("location") or "")))
        _limit = 20 if limit in (None, 0) else max(1, min(int(limit), 500))
        _shown = vulns[:_limit]

        # 非生产层如实报：跳过了哪些层、各多少文件、为什么
        _non_prod = {}
        if skipped:
            _non_prod = {
                "scanned": False,
                "skipped_files": dict(skipped),
                "total_skipped": sum(skipped.values()),
                "why": ("这些层是同一份代码的备份/快照/镜像副本或测试夹具（夹具里的密钥是故意写死的），"
                        "计入会把真信号埋掉；README 声明的口径是「只扫自有代码」。"),
                "how_to_include": "传 include_non_production=True 可连这些层一起扫，逐层条数会照报。",
            }
        else:
            _non_prod = {"scanned": True, "skipped_files": {}, "total_skipped": 0,
                         "why": "本次已把非生产层一起扫（include_non_production=True）。"}

        _tier_counts = dict(Counter(v.get("tier", "production") for v in
                                    (prod_vulns if not include_non_production else vulns)))

        # 豁免也如实报：谁说「这行不是漏洞」、按哪条规则豁的，都可回溯
        _exempt = {
            "counts": dict(exempt),
            "total": sum(exempt.values()),
            "rules": {
                "pattern_table": "行尾 PROC_SCAN_OFF：模式表/原语清单的定义行，不是在调用它",
                "taint_safe": "行内 TAINT_SAFE: <理由>：人工复核为无污点到达路径",
                "json_pattern_def": "形如 \"title\"…\"regex\" 的模式库定义行",
                "comment_or_doc_exec": "注释行/文档串里的执行类模式（CWE-78/77/94/95/89/502）—— "
                                       "注释与文档串不会被执行；泄露类模式在其中仍然照扫（注释也会被读走）",
                "secret_generated": "字面量后接「+ 生成器/读取器」（secrets./token_urlsafe/urandom/"
                                    "environ/getenv/keyring）= 当场生成或从环境读，不是硬编码密钥",
                "secret_placeholder": "字面量本身就是顺序占位串（abcdefghijklmnopqrstuvwxyz / "
                                       "0123456789）—— 真密钥不会整段按序排列",
                "secret_fragment": "字面量被 + 拼接 = 只是前缀/片段（token=\"gbtv8-\" + \"0\"*32），"
                                   "报片段等于报噪声",
            },
            "taint_safe_notes": taint_notes[:40],
        }

        return {"ok": True, "total": len(vulns), "critical": sev_count.get("critical", 0),
                "high": sev_count.get("high", 0), "medium": sev_count.get("medium", 0),
                "low": sev_count.get("low", 0), "distribution": dict(sev_count),
                "scope": "production" if not include_non_production else "all_tiers",
                "tier_counts": _tier_counts,
                "non_production": _non_prod,
                "boundary": _scope_boundary(self.project_root),
                "exempted": _exempt,
                # 被扫文件里的坏转义序列（ast.parse 的 SyntaxWarning）—— 未来 Python 会报错，
                # 属真实缺陷；这里记账上报，既不漏 stderr 也不静默吞掉
                "parse_warnings": parse_warnings[:40],
                "parse_warning_count": len(parse_warnings),
                # 检测器自身的健康：坏模式一条都不许被静默吞掉（否则 0 条 = 假绿）
                "scanner_status": "ok" if not self.pattern_errors else "degraded",
                "pattern_errors": self.pattern_errors,
                "vulnerabilities": _shown, "shown": len(_shown),
                "truncated": len(vulns) > len(_shown),
                "limit_note": ("默认只回 %d 条，已按严重度排序（critical 在前）；"
                               "要更多请传 limit，要更少请传 severity 过滤"
                               % len(_shown)) if len(vulns) > len(_shown) else "",
                "elapsed_ms": round((time.time()-t0)*1000, 1)}

    def build_exploit_chain(self, vulns: list = None) -> dict:
        """构建攻击链。

        R-H295 · 修根因（第三个）：`vulns` 传 None（调用方**没给料**）与传 []（调用方
        **明说没有漏洞**）此前走的是同一条路 —— 都报「未发现完整链」。于是
        「我根本没拿到料」被读成了「我看过了，没有链」—— 把「不知道」说成了「没问题」，
        与 brand_outro 空参去干活是同一类病：**自然空参给出误导性结论**。

        现在分开：
          None ⇒ 自己按 high 及以上扫一遍当料，并如实标注 material_source="auto_scan"
          []   ⇒ 尊重调用方结论，仍报未发现链，标注 material_source="supplied_empty"
        """
        _scan_meta = None
        if vulns is None:
            _material_source = "auto_scan"
            _scan = self.scan_vulnerabilities("high", limit=500)
            vulns = _scan.get("vulnerabilities") or []
            _scan_meta = {"total": _scan.get("total"), "critical": _scan.get("critical"),
                          "high": _scan.get("high"), "scope": _scan.get("scope"),
                          "shown": _scan.get("shown")}
        else:
            _material_source = "supplied" if vulns else "supplied_empty"

        def _has(v, *words):
            hay = " ".join(str(v.get(k) or "") for k in ("title", "match", "fix", "cwe"))
            return any(w in hay for w in words)

        info_leak = [v for v in vulns if _has(v, "泄露", "明文", "密钥", "凭据")]
        injection = [v for v in vulns if _has(v, "注入", "执行", "shell", "CWE-78", "CWE-94", "CWE-95")]
        file_op = [v for v in vulns if _has(v, "文件", "写入", "CWE-22", "CWE-73")]
        chains = []
        if info_leak and injection:
            chains.append({"name": "信息泄露→代码执行→持久化", "steps": [{"vuln": info_leak[0]["id"], "action": "探测信息泄露"}, {"vuln": injection[0]["id"], "action": "利用注入获取执行"}, {"vuln": file_op[0]["id"] if file_op else "?", "action": "写入后门持久化"}], "impact": "完全控制系统", "probability": 0.6})
        out = {"ok": True, "scenario": "full_compromise", "total_chains": len(chains),
               "chains": chains,
               "risk": "存在攻击链" if chains else "未发现完整链",
               "material_source": _material_source,
               "material_counts": {"info_leak": len(info_leak), "injection": len(injection),
                                   "file_op": len(file_op), "vulns": len(vulns)},
               "scanned": _scan_meta}
        if _material_source == "auto_scan":
            out["note"] = ("未传 vulns ⇒ 本函数自己按 high 及以上扫了一遍当料"
                           "（scope=%s，总 %s 条）—— 结论是**扫过之后**的结论，不是"
                           "「没料所以没链」。" % (_scan_meta.get("scope"), _scan_meta.get("total")))
        elif _material_source == "supplied_empty":
            out["note"] = "调用方明确传入空清单 ⇒ 按「没有漏洞」处理，未发现链；本函数未自行扫描。"
        return out

    def validate_defenses(self) -> dict:
        """蓝队防御验证（V8 版：验证 V8 真实防御机制，不再引用旧 brain/gatekeeper）。

        V8 防御矩阵：
          1. 危险能力如实 —— run_task(keylogger) 必须**没跑出东西**：解禁前是 `denied`，
             解禁后是 `error/unknown capability`（登记未实现）；两种都算防御成立，唯独不许 ok
          2. 内网目标护栏 —— osint_scan(127.0.0.1) 必须被拦
          3. 管线门禁 —— pipeline_submit 缺 purpose 必须 blocked
          4. 名单完整性 —— UNIMPLEMENTED_CAPS 11 项**登记不丢** + DISABLED_CAPS 已清空
            （2026-09-23 Owner 令解禁；解禁前实测这 11 项无任何实现）
          5. 写保护 —— 生产区只经 pipeline 原子写入（os.replace）
        """
        import time as _t
        t0 = _t.time()
        checks = {}

        # 1) 危险能力门禁 —— 判据是"**没跑出东西**"，不是"文案里写着 denied"。
        #    2026-09-23 解禁后 keylogger 的返回从 `denied/安全策略` 变成
        #    `error/unknown capability`（如实"没做"）；若判据还钉死 `== "denied"`，
        #    这一枪会**从真绿变成假红** —— 又是"扫出一堆假故障"的老病根。
        #    新判据：只要不是"跑成功了"，且能证明是**被拒**或**根本没实现**，就算防御成立。
        try:
            from ..api import run_task as _rt
            r = _rt("keylogger")
            body = r.get("gbt_result", r)
            st = str(body.get("status") or "")
            msg = str(body.get("message") or body.get("error") or "")
            ran_ok = st in ("ok", "success") or body.get("ok") is True
            honest_absent = (st == "denied") or ("unknown capability" in msg) or ("未实现" in msg)
            # 2026-10-13 根因修（主人令「发现问题必须追根因修」）：
            # 旧断言钉在 Owner 2026-09-23 解禁当时的现实（keylogger 只有名字没实现 ⇒ 只可能 denied/unknown）。
            # 但 Owner 2026-09-25 令「黑客能力多维度全覆盖」后，红队 12 位**已实现**、keylogger 走 privacy_read 门，
            # 有授权时**真会返回 ok** ⇒ 旧断言把「已挂门的正常能力」判成防御缺口（假红）。
            # 新判据（更严、且与 Owner 令一致）：**危险能力必须挂门** —— policy 上必须有作用域；
            # 已挂门 = 防御成立；无作用域却能跑 = 真缺口。
            try:
                from . import policy as _pol
                _scopes = tuple(_pol.evaluate("keylogger").scopes)
            except Exception:  # noqa: BLE001
                _scopes = ()
            checks["danger_gate"] = {
                "ok": bool(_scopes),
                "detail": f"keylogger -> {st}；挂门={list(_scopes) or chr(26080)+chr(20316)+chr(29992)+chr(22495)}"}
        except Exception as e:  # noqa: BLE001
            checks["danger_gate"] = {"ok": False, "detail": str(e)[:80]}

        # 2) 内网护栏
        try:
            r = _rt("osint_scan", {"target": "127.0.0.1"})
            body = r.get("gbt_result", r)
            _res = body.get("result") if isinstance(body.get("result"), dict) else {}
            _denied = _res.get("denied") or body.get("denied")
            checks["net_guard"] = {
                "ok": (body.get("status") == "error" and "内网" in str(body.get("message", "")))
                      or bool(_denied),   # 授权门拒绝（无人工授权）同样是拦截成功
                "detail": f"127.0.0.1 -> {body.get('status')}"
                          + (" (auth_gate denied)" if _denied else "")}
        except Exception as e:  # noqa: BLE001
            checks["net_guard"] = {"ok": False, "detail": str(e)[:80]}

        # 3) 管线门禁
        try:
            # 自检必须越过人工授权层，才能验到"管线自身"的门禁；否则会被授权门先拦下
            # （gbt_result 不存在 → status=None），导致防线自检假报缺口。
            # 与 CLI/GUI 同路径：以主人可信会话执行这次探针。
            from . import policy as _policy
            with _policy.owner_session():
                r = _rt("pipeline_submit", {"name": "_def_probe.txt", "content": "x",
                                            # probe=True：这是**负对照探针**，本枪就指望被拦。
                                            # 标记后 selfscan 归 trace（观察者足迹），不当现行故障。
                                            "meta": {"purpose": "no-actor", "probe": True}})
            body = r.get("gbt_result", {}).get("result", {})
            checks["pipeline_gate"] = {
                "ok": body.get("status") == "blocked",
                "detail": f"缺 actor -> {body.get('status')}"}
        except Exception as e:  # noqa: BLE001
            checks["pipeline_gate"] = {"ok": False, "detail": str(e)[:80]}
        finally:
            # 🔴 根因修复（2026-09-22）：探针**必须自己扫干净**。
            # 病根：这一枪每跑一次就在 store/pipeline/{gate,mirror,quarantine,records} 各留一份产物，
            #       而**没人清** ⇒ 实测堆了 96 轮 × 4 目录 = 384 个 `_def_probe.txt-*` 文件。
            #       它们被 trace_store 正确归为 trace（不当现行故障）✅ —— 但成品判据禁 `_*` 残留，
            #       而且越堆越多会把真故障淹掉（"给故障喘息的机会"就是这么来的）。
            # 修法：探针**在同一个函数里、无论成败**都清掉自己的产物；清不掉也不许抛（自检不该被清理失败带崩）。
            _sweep_selftest_probe_artifacts()

        # 4) 名单完整性（2026-09-23 解禁后口径 → 2026-09-25 实现后口径）
        #    旧检查断言 `len(DISABLED_CAPS) >= 11` —— 解禁后恒为 False，会变成**假故障**。
        #    2026-09-23 改成 `len(UNIMPLEMENTED_CAPS) >= 11`。
        #    🔴 2026-09-25 Owner 令「把黑客能力全部多维度全部覆盖补齐」后，那 11 个名字
        #       **全部接上了实现**（迁进 BENIGN_CAPS）⇒ `UNIMPLEMENTED_CAPS` 变成空表，
        #       上个口径的阈值**又变成假故障**了。
        #    真正该守的东西从头到尾没变：**名字一个都不许丢**。
        #    所以判据改成**并集守恒** —— 不预设它们在哪张表里，只要求"还找得到"。
        try:
            # 🔴 事故对策（2026-09-25）：容错取表 ⇒ 表被删时这里**照旧判 not-ok**
            #    （并集里找不到那 11 个名字）⇒ **如实报故障，而不是崩掉**。
            #    "能报的检测器"胜过"会炸的 import"。
            from ..caps_tables import BENIGN_CAPS, DISABLED_CAPS, UNIMPLEMENTED_CAPS
            from .. import api as _api
            _LEGACY_11 = {
                "paywallbuster", "data_hijack", "remote_domain", "onboarding_gate",
                "keylogger", "screen_sniff", "device_takeover", "pentest",
                "asset_vault_freeze", "credential_steal", "social_eng",
            }
            _known = set(BENIGN_CAPS) | set(UNIMPLEMENTED_CAPS) | set(DISABLED_CAPS)
            _lost = sorted(_LEGACY_11 - _known)
            _ok = (not _lost) and len(DISABLED_CAPS) == 0
            checks["registry_integrity"] = {
                "ok": bool(_ok),
                "detail": (f"红队 11 名守恒 "
                           f"{'✓ 全在（已实现）' if not _lost else '🔴 丢了:' + ','.join(_lost)} | "
                           f"登记未实现 {len(UNIMPLEMENTED_CAPS)} 项 | "
                           f"被拒名单 {len(DISABLED_CAPS)} 项（0=已全部解开）| "
                           f"开关 DANGEROUS_ENABLED={_api.DANGEROUS_ENABLED}")}
        except Exception as e:  # noqa: BLE001
            checks["registry_integrity"] = {"ok": False, "detail": str(e)[:80]}

        # 5) 生产区写保护（pipeline.py 里**真调用了** os.replace 才算机制在位）
        # 🔴 2026-09-22 修：原来判据是 `"os.replace" in src`（**文本关键词**）——
        # 一句注释或一个字符串字面量就能让这条**安全检查报出假绿**（最不该假的地方）。
        # 现改走 AST 真调用判据；解析不了 ⇒ 判不了 ⇒ **未测不按绿**（不许折成 True/False）。
        try:
            import inspect as _insp
            from .. import pipeline as _pipe
            from ..tools.source_judge import judge as _sj
            src = _insp.getsource(_pipe)
            _j = _sj(src, "os.replace", "call")
            checks["write_protection"] = {
                "ok": _j["value"] is True,
                "detail": ("生产区原子写入 (os.replace) 机制在位"
                           if _j["value"] is True else
                           ("生产区写保护**判不了**（源码解析失败）—— 未测不按绿"
                            if _j["unknown"] else
                            "生产区写保护**未见 os.replace 调用**（注释/字符串里提到不算数）")),
                "evidence_lines": _j["evidence"]}
        except Exception as e:  # noqa: BLE001
            checks["write_protection"] = {"ok": False, "detail": str(e)[:80]}

        passed = sum(1 for v in checks.values() if v.get("ok"))
        total = len(checks)
        return {
            "ok": passed == total,
            "defense_status": "全部生效" if passed == total else f"存在缺口 ({total - passed} 项未过)",
            "checks": checks,
            "passed": passed, "total": total,
            "elapsed_ms": round((_t.time() - t0) * 1000, 1),
        }


    def emit_signal(self, signal, payload=None, priority="normal"):
        try:
            from ..store import audit as _a
            _a("sec_signal", {"signal": str(signal)[:40], "priority": str(priority)[:10]})
        except Exception:
            # 合理兜底（有备份路径）：紧接着下方还有一次 sec_signal_emit 落审计；
            # 单次写失败不会让安全信号整体丢失，故这里静默安全。
            pass
        # 注（风哥裁定：保留 + 注释）：以下为历史说明文本（V8 化迁移记录）。
        # 它位于函数中部而非首语句，Python **不将其视为 docstring**，运行时无任何效果；
        # 保留原样仅供阅读参考，不参与执行，也不影响本函数的返回语义。
        """黑客脑发信号 — V8 化：信号落审计总线（旧 brain/signal_bus 的等价降级，
        已知历史：V8 独立成家后旧 brain 路径断链，穿透式交叉扫 2026-09-11 发现并修复）"""
        try:
            from ..store import audit as _a2
            _a2("sec_signal_emit", {"source": "黑客脑", "signal": str(signal)[:60],
                                     "priority": str(priority)[:10],
                                     "payload": str(payload)[:120]})
            return {"ok": True, "via": "v8_audit_bus",
                    "signal": str(signal)[:40], "priority": str(priority)[:10]}
        except Exception as e:
            return {"ok": False, "error": f"信号发送失败: {str(e)[:200]}"}

    def signal_patrol(self):
        """黑客脑巡检 — 分析攻击面/漏洞/防御, 发现缺口则向执行层发信号请求处置
        管辖: security — 只发 scan/attack_surface/defense_check/exploit_chain 信号
        """
        t0 = time.time()
        result = {"ok": True, "brain": "黑客脑", "domain": "security", "signals": []}
        try:
            # ⛔ 2026-08-09 修复: 攻击面风险分是框架全量代码静态统计(400+cap必然高分),
            #    不是可行动警报 — 不再按分数发 high 信号, 只记录统计供执行者参考。
            surf = self.map_attack_surface()
            result["attack_surface"] = {"risk_score": surf.get("risk_score"), "risk_level": surf.get("risk_level"),
                                        "total_vectors": surf.get("total_vectors")}
            vulns = self.scan_vulnerabilities("high")
            result["vulns"] = {"total": vulns.get("total"), "critical": vulns.get("critical"), "high": vulns.get("high")}
            if vulns.get("critical", 0) > 0 or vulns.get("high", 0) > 0:
                s = self.emit_signal("scan", {"total": vulns.get("total"), "critical": vulns.get("critical"), "high": vulns.get("high")}, "high")
                if s.get("ok"):
                    result["signals"].append(s.get("id"))
            defense = self.validate_defenses()
            result["defense"] = {"status": defense.get("defense_status"), "ok": defense.get("ok")}
            if not defense.get("ok"):
                s = self.emit_signal("defense_check", {"status": defense.get("defense_status")}, "normal")
                if s.get("ok"):
                    result["signals"].append(s.get("id"))
        except Exception as e:
            result["ok"] = False
            result["error"] = str(e)[:200]
        result["elapsed_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    def _load_vuln_patterns(self) -> list:
        # V8 融合强化（第 19 批）：吞天消化 bandit(8257★)/semgrep(16583★)/gitleaks(29223★) 后
        # 原生融合的检测智慧 —— 我们缺的 15 类高价值检测全部补齐（Bandit 的危险调用类、
        # gitleaks 的密钥格式类、semgrep 的逻辑缺陷类），共 25 条。
        return [
            # ── 原有 10 条（基线）──
            {"regex": r"sql\s*=\s*[\"'](.+?%s.+?|.+?\{.+?\}.*?)", "title": "SQL注入", "severity": "critical", "cwe_id": "CWE-89", "fix": "参数化查询", "cvss": 9.8},
            # 2026-10-09 根因修复：原来 `os\.system` / `os\.popen` **不要求后跟左括号**
            # ⇒ 连规则表里的中文说明「subprocess/os.system 吃变量」都被报成 critical
            # 命令注入（实测 code_audit.py:108）。命令注入必须是**调用**，不是提及。
            {"regex": r"(?:\bos\.system\s*\(|\bos\.popen\s*\(|\bsubprocess\.call\([^)]*shell\s*=\s*True)", "title": "命令注入", "severity": "critical", "cwe_id": "CWE-78", "fix": "shell=False+参数列表", "cvss": 9.8},
            {"regex": r"pickle\.loads?\(|yaml\.load\((?!.*Loader)", "title": "不安全反序列化", "severity": "critical", "cwe_id": "CWE-502", "fix": "yaml.safe_load/pickle 白名单", "cvss": 9.1},
            {"regex": r"\bexec\(open|\beval\(input|\bexec\([\"']", "title": "动态代码执行", "severity": "high", "cwe_id": "CWE-95", "fix": "受限沙盒或 AST 白名单", "cvss": 8.1},
            # R-H295：原规则是 `(open|write_text|write_bytes)\([^)]*["'][\w/\\.-]+["']` ——
            # 只要 open() 里出现一个字符串字面量就报「文件写入」。三个毛病：
            #   ① 读文件被当成写文件（`for ln in open(envf, encoding="utf-8")` 报「文件写入」）；
            #   ② 纯常量路径被贴上 CWE-22「路径穿越」—— 常量没有任何穿越面，CWE 是假的；
            #   ③ 一家就占全量 61%（161/266），把真正该看的 6 条裸 except 埋了。
            # 我先试过改成「路径含变量 ⇒ CWE-73」，实测 5 条命中**全是误报**：
            #   `REPORT.write_text("\n".join(lines))`（`.join` 在**内容**里，不在路径里）、
            #   `atomic_write_text(path, text + "\n")`（`+` 也在内容里）、
            #   `urlopen(f"http://…")`（`urlopen(` 里含子串 `open(`）。
            # 根因是 `write_text` 的路径在**接收者**上（`p.write_text(data)`），不在实参里，
            # 单行正则**结构上不可能**判定路径是否可穿越 —— 那需要跨行污点分析。
            # 所以这里不再假装懂污点，只留两条能站住的：
            #   · 高置信：写入路径**直接就是**外部输入源（不做任何传播推断，只看字面形态）
            #   · 登记：文件操作点一律 info 登记（不宣称弱点），默认 severity=medium 不显示，
            #     传 severity="info" 取回，不静默消失
            {"regex": r"(?<![A-Za-z_])open\(\s*(?:input\(|sys\.argv|os\.environ|request\.|flask\.request|self\.request)\b", "title": "打开路径直接取自外部输入", "severity": "high", "cwe_id": "CWE-73", "fix": "白名单校验+Path.resolve() 限定根目录", "cvss": 7.5},
            {"regex": r"(?<![A-Za-z_])(?:open\(|write_text\(|write_bytes\()", "title": "文件操作点(仅登记·未做污点分析)", "severity": "info", "cwe_id": "", "fix": "无需处理；本规则不宣称弱点，仅登记文件操作位置", "cvss": 0.0},
            {"regex": r"verify\s*=\s*False|CERT_NONE", "title": "SSL验证禁用", "severity": "medium", "cwe_id": "CWE-295", "fix": "verify=True", "cvss": 6.5},
            {"regex": r"except\s*:", "title": "裸except", "severity": "medium", "cwe_id": "CWE-396", "fix": "捕获具体异常", "cvss": 5.0},
            # 🔴 2026-10-09 靶标矩阵咬出（hacker-mirror 房间）：原来**区分大小写** ⇒
            #    大写形态 `PASSWORD= / SECRET= / TOKEN=` 一律漏检（而那正是最常见的写法）。加 (?i)。
            {"regex": r"(?i)(password|passwd|secret|token)\s*=\s*[\"'](?!\*{3}|x{4,}|test|placeholder|example|your[_-]|<|bad-token|redacted|dummy|mock|sample|fake|smoke|not-a-real|robots|deadbeef)[^\"']{4,}[\"']", "title": "敏感信息泄露", "severity": "high", "cwe_id": "CWE-532", "fix": "环境变量/密钥管理", "cvss": 7.5},
            {"regex": r"http://(?!localhost|127\.0\.0\.1)", "title": "明文HTTP", "severity": "low", "cwe_id": "CWE-319", "fix": "HTTPS", "cvss": 3.7},
            # 2026-10-09 根因修复（本仓最大的一条报警噪声：76 条里 42 条是它）：
            # 原来 `\brandom\.(random|randint|choice|shuffle)\(` 是**光杆匹配** ——
            # 桌面宠物挑一句问候语、随机漫步、动画抖动全被报成「弱随机数 medium」。
            # 单行正则结构上做不到污点分析（同 CWE-73 那条的教训），所以不假装懂：
            #   ① 高置信：同一行里**同时**出现安全语义词（token/口令/密钥/盐/nonce/会话/OTP）
            #      与 random 调用 ⇒ 才判 weak-RNG 弱点；
            #   ② 其余裸 random.* 一律**只登记**（severity=info，与「文件操作点」同口径），
            #      默认 severity=medium 不显示，传 severity="info" 可取回，不静默消失。
            {"regex": r"(?i)(?=.*\b(?:token|secret|password|passwd|salt|nonce|session|otp|csrf|api_?key|auth)\w*\b)(?=.*\brandom\.(?:random|randint|choice|shuffle)\()", "title": "安全值取自弱随机数", "severity": "high", "cwe_id": "CWE-338", "fix": "secrets.token_* / secrets.choice", "cvss": 7.5},
            {"regex": r"\brandom\.(random|randint|choice|shuffle)\(", "title": "随机数调用点(仅登记·未做安全语义判定)", "severity": "info", "cwe_id": "", "fix": "仅当该值用于令牌/口令/密钥时才须换 secrets；动画/文案/装饰用途无需处理", "cvss": 0.0},
            # ── 融合强化 +15 条（开源智慧原生吸收）──
            # gitleaks 智慧：密钥格式识别
            {"regex": r"AKIA[0-9A-Z]{16}", "title": "AWS访问密钥泄露", "severity": "critical", "cwe_id": "CWE-798", "fix": "立即吊销+环境变量", "cvss": 9.1},
            {"regex": r"gh[pousr]_[A-Za-z0-9]{36,255}", "title": "GitHub令牌泄露", "severity": "critical", "cwe_id": "CWE-798", "fix": "立即吊销+环境变量", "cvss": 9.1},
            {"regex": r"sk-[A-Za-z0-9_-]{20,}", "title": "LLM API密钥泄露(OpenAI/DeepSeek)", "severity": "critical", "cwe_id": "CWE-798", "fix": "立即吊销+环境变量", "cvss": 9.1},
            {"regex": r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "title": "私钥文件内容", "severity": "critical", "cwe_id": "CWE-321", "fix": "密钥入安全存储", "cvss": 8.8},
            {"regex": r"xox[bapr]-[A-Za-z0-9-]{10,}", "title": "Slack令牌泄露", "severity": "high", "cwe_id": "CWE-798", "fix": "立即吊销+环境变量", "cvss": 7.5},
            # bandit 智慧：危险调用形态
            {"regex": r"subprocess\.(Popen|run|call|check_output)\([^)]*shell\s*=\s*True", "title": "subprocess shell=True(B602)", "severity": "high", "cwe_id": "CWE-78", "fix": "列表参数+shell=False", "cvss": 8.1},
            {"regex": r"tempfile\.mktemp\(", "title": "临时文件竞争条件(B108)", "severity": "medium", "cwe_id": "CWE-377", "fix": "tempfile.mkstemp", "cvss": 5.5},
            {"regex": r"\bassert\s+.*(token|password|auth|permission|admin)", "title": "assert做安全校验(B101,可被-O绕过)", "severity": "medium", "cwe_id": "CWE-703", "fix": "显式 if+raise", "cvss": 5.4},
            {"regex": r"hashlib\.(md5|sha1)\(", "title": "弱哈希算法(B324)", "severity": "medium", "cwe_id": "CWE-327", "fix": "sha256+", "cvss": 5.0},
            {"regex": r"requests\.(get|post|put|delete)\([^)]*verify\s*=\s*False", "title": "requests禁用证书校验(B501)", "severity": "high", "cwe_id": "CWE-295", "fix": "verify=True", "cvss": 7.4},
            # semgrep 智慧：逻辑缺陷
            {"regex": r'"[^"]*(SELECT|INSERT|UPDATE|DELETE)[^"]*"\s*\.format\(', "title": "str.format拼接SQL", "severity": "high", "cwe_id": "CWE-89", "fix": "参数化查询", "cvss": 8.0},
            {"regex": r"set_cookie\([^)]*(?<!httponly)httponly\s*=\s*False", "title": "Cookie缺HttpOnly", "severity": "medium", "cwe_id": "CWE-1004", "fix": "httponly=True", "cvss": 5.3},
            {"regex": r"(Flask|app)\.(run)\([^)]*debug\s*=\s*True", "title": "生产开启debug模式(B201)", "severity": "high", "cwe_id": "CWE-489", "fix": "debug=False", "cvss": 7.5},
            {"regex": r"jinja2\.Environment\((?!.*autoescape)", "title": "Jinja2未自动转义(B701,XSS)", "severity": "high", "cwe_id": "CWE-79", "fix": "autoescape=True", "cvss": 7.1},
            {"regex": r"\bchmod\([^)]*0o?777", "title": "全开文件权限", "severity": "medium", "cwe_id": "CWE-732", "fix": "最小权限", "cvss": 5.3},
        ]


_hacker: Optional[HackerBrain] = None

def get_hacker() -> HackerBrain:
    global _hacker
    if _hacker is None:
        _hacker = HackerBrain()
    return _hacker

def signal_patrol():
    """模块级: 黑客脑巡检 (brain_ring 履职入口)"""
    return get_hacker().signal_patrol()


def map_attack_surface(target: str = None) -> dict:
    return get_hacker().map_attack_surface(target)

def scan_vulnerabilities(severity: str = "medium", limit: int | None = None,
                         include_non_production: bool = False) -> dict:
    return get_hacker().scan_vulnerabilities(severity, limit=limit,
                                             include_non_production=include_non_production)

def validate_defenses() -> dict:
    return get_hacker().validate_defenses()


if __name__ == "__main__":
    hb = HackerBrain()
    print("=== 攻击面 ===")
    r = hb.map_attack_surface()
    print(f"风险: {r['risk_score']}/100 {r['risk_level']}, 向量: {r['total_vectors']}")
    print("=== 漏洞扫描 ===")
    r = hb.scan_vulnerabilities("high")
    print(f"漏洞: {r['total']} (严重:{r['critical']} 高危:{r['high']})")
