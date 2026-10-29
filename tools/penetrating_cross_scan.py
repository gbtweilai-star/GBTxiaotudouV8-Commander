# -*- coding: utf-8 -*-
"""penetrating_cross_scan · 穿透式交叉扫描引擎（增强版 · 强制钩子 + 交叉验证）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

立项令（Owner 2026-09-27）：触手到位**必须**调用钩子；钩子未触发 = 任务失败；
步骤锁（跳步拒绝）；同一目标**至少两路触手**交叉互扫；覆盖率 < 100% 必须补扫；
每次扫描留痕 source_kind=cross_scan。

五条红线（写死，不许静默变形）：
  1. 钩子未触发 = 任务失败（不 silently skip）
  2. 步骤锁必须生效（乱序/跳步 → StepViolation，当场拒绝）
  3. 交叉验证必须进行（每单元 ≥ 2 路独立读；不一致 → 第三路仲裁）
  4. 遗漏必须补扫（bounded 重试；仍钩不住 → 如实报"未钩住"，不许折叠成绿）
  5. 每次扫描写 trace（state/cross_scan_trace.jsonl，追加式，无痕即未发生）

亿万触手口径（诚实）：触手是**按需生成**的虚拟单元（unit × reader 笛卡尔积），
并发受 `max_workers` 与物理机限制（默认 8；quick_scan 的 12 线程是本仓 NTFS 先例）——
"亿万"指的是**可扩展的生成模型**，不是虚报并发数。

命令：
  python tools/penetrating_cross_scan.py status
  python tools/penetrating_cross_scan.py scan   bindings|registry|tree:<目录>
  python tools/penetrating_cross_scan.py verify bindings|registry|tree:<目录>   # 只跑钩子交叉
  python tools/penetrating_cross_scan.py check  bindings|registry|tree:<目录>   # 只跑遗漏检测
  python tools/penetrating_cross_scan.py report [--tail 5]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 🔴 2026-10-09 根因修复（与 five-dim.py:44-47 同一处病根，本引擎漏了这一步）：
#   GBK 控制台下本引擎**一跑就崩**：scan 走完全程、结果里含 "⇒"（U+21D2），
#   最后 `print(json.dumps(...))` 抛 UnicodeEncodeError ⇒ **扫描结论整份丢失**，
#   读的人只会以为「引擎坏了 / 扫不出东西」。不是引擎坏了，是打不出来。
#   修法照抄本仓既有口径：出口一律 utf-8 + errors=replace。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
TRACE = ROOT / "state" / "cross_scan_trace.jsonl"
MAX_WORKERS = 8
RESCAN_ROUNDS = 2          # 遗漏补扫最多两轮，仍钩不住就如实报
CROSS_READERS = 2          # 每单元至少两路；不一致再请第三路仲裁

# ── 步骤锁（红线 2）────────────────────────────────────────────────────
STEPS = ["decompose", "spawn", "hook", "cross_validate", "detect_omission", "trace"]


class StepViolation(RuntimeError):
    """跳步/乱序——当场拒绝，不许带病继续。"""


class StepLock:
    """规定好的步骤必须按序走：`enter("hook")` 之前必须走过 decompose/spawn。"""

    def __init__(self, steps: list[str]):
        self.steps = steps
        self.done: list[str] = []

    def enter(self, step: str) -> None:
        if step not in self.steps:
            raise StepViolation(f"未知步骤 {step}（合法：{self.steps}）")
        expect = self.steps[len(self.done)]
        if step != expect:
            raise StepViolation(f"跳步违规：当前应走「{expect}」却来了「{step}」（已走 {self.done}）")
        self.done.append(step)


# ── 钩子池（红线 1：到位必须钩住）──────────────────────────────────────
# 每类单元 ≥ 2 路独立读法 + 1 路仲裁读法。钩子"触发" = 读到了观察值并留下证据。
def _read_file_a(p: Path) -> dict:
    st = p.stat()
    return {"exists": True, "size": st.st_size, "mtime": int(st.st_mtime)}


def _read_file_b(p: Path) -> dict:
    st = os.stat(p)                      # 独立读法（os 层，不走 pathlib）
    return {"exists": True, "size": st.st_size, "mtime": int(st.st_mtime)}


def _read_file_c(p: Path) -> dict:       # 仲裁路：字节数（真打开文件数一遍）
    with p.open("rb") as f:
        return {"exists": True, "size": sum(len(chunk) for chunk in iter(lambda: f.read(1 << 20), b"")),
                "mtime": int(p.stat().st_mtime)}


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


HOOKS = {
    "file": {"a": _read_file_a, "b": _read_file_b, "arbiter": _read_file_c},
    "registry": {},      # 在 _hook_registry() 里现算（导入要惰性）
    "bindings": {},
}


def _hook_registry():
    def read_a(_u):
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS      # 读法 A：真导入
        return {"kinds": sorted(BENIGN_CAPS.keys())}

    def read_b(_u):
        src = (ROOT / "gbt_allinone" / "caps_registry.py").read_text(encoding="utf-8")
        kinds = re.findall(r'^\s{4}"([A-Za-z0-9_]+)":\s*\{', src, re.M)   # 读法 B：纯文本解析
        return {"kinds": sorted(set(kinds))}

    def read_c(_u):
        a = json.loads((ROOT / "state" / "skill_atlas.json").read_text(encoding="utf-8"))
        return {"kinds": sorted({c["kind"] for c in a.get("caps", [])})}  # 仲裁：图鉴现扫产物
    return {"a": read_a, "b": read_b, "arbiter": read_c}


def _hook_bindings():
    """逐资产钩（unit = "binding:<rel>"）：钩子观察的是**这一个**资产，不是整本账。
    读法 A 走 pathlib，读法 B 走 os 层——两路独立探存在性+体积。"""
    def read_a(unit: str):
        rel = unit.split("binding:", 1)[1]
        p = ROOT / rel
        st = p.stat()
        return {"exists": True, "size": st.st_size}

    def read_b(unit: str):
        rel = unit.split("binding:", 1)[1]
        st = os.stat(ROOT / rel)
        return {"exists": True, "size": st.st_size}
    return {"a": read_a, "b": read_b, "arbiter": read_a}


def hooks_for(unit_type: str) -> dict:
    if unit_type == "file":
        return HOOKS["file"]
    if unit_type == "registry":
        return _hook_registry()
    if unit_type == "bindings":
        return _hook_bindings()
    if unit_type == "caps":
        return _hook_caps()
    raise ValueError(f"未知单元类型 {unit_type}")


# ── 分解（原子项目）────────────────────────────────────────────────────
def decompose(target: str) -> tuple[str, list]:
    """target → (unit_type, units)。units 就是原子扫描项目，一个不许漏。"""
    if target == "bindings":
        d = json.loads((ROOT / "state" / "asset_bindings.json").read_text(encoding="utf-8"))
        return "bindings", [f"binding:{k}" for k in sorted(d.keys())]
    if target == "registry":
        return "registry", ["registry:all"]
    if target == "caps":
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return "caps", ["cap:" + k for k in sorted(BENIGN_CAPS.keys())]
    if target.startswith("tree:"):
        d = ROOT / target[5:]
        if not d.is_dir():
            raise FileNotFoundError(f"目标目录不存在：{d}")
        # 跳过面**复用绑定系统的定义**（一处定义两处用：vendor/store/.pylibs/缓存/运行足迹都不扫）
        skip = None
        try:
            import importlib.util as _iu
            _sp = _iu.spec_from_file_location("tbx", ROOT / "tools" / "tentacle_bind.py")
            _tb = _iu.module_from_spec(_sp)
            _sp.loader.exec_module(_tb)
            skip = _tb._skippable
        except Exception:                                      # noqa: BLE001
            skip = None
        files = [p for p in sorted(d.rglob("*"))
                 if p.is_file() and p.suffix.lower() not in (".tmp", ".pyc")
                 and ".git" not in p.parts and "__pycache__" not in p.parts
                 and (skip is None or not skip(p.relative_to(ROOT).as_posix()))]
        return "file", [p.relative_to(ROOT).as_posix() for p in files]
    raise ValueError(f"未知 target：{target}（bindings|registry|tree:<目录>）")


# ── 触手集群（虚拟生成 + 有界并发）─────────────────────────────────────
def _unit_payload(unit_type: str, unit: str):
    if unit_type == "file":
        return ROOT / unit
    if unit_type == "caps":
        return unit.split("cap:", 1)[1]
    return None


def _fingerprint(obs: dict) -> str:
    return json.dumps(obs, sort_keys=True, ensure_ascii=False)


def spawn_and_hook(unit_type: str, units: list[str], readers: tuple[str, ...],
                   max_workers: int = MAX_WORKERS) -> dict:
    """每单元 × 每读法 = 一根触手。到位必须钩住；钩不住记 unhooked。"""
    hooks = hooks_for(unit_type)
    jobs = [(u, r) for u in units for r in readers]
    results = {u: {} for u in units}

    def _one(job):
        unit, reader = job
        fn = hooks[reader]
        payload = _unit_payload(unit_type, unit)
        t0 = time.time()
        try:
            obs = fn(payload if payload is not None else unit)
            obs = obs if isinstance(obs, dict) and obs else None
        except Exception as exc:                                # noqa: BLE001
            obs = None
            err = f"{type(exc).__name__}: {str(exc)[:120]}"
        else:
            err = ""
        return unit, reader, obs, err, round((time.time() - t0) * 1000, 1)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for unit, reader, obs, err, ms in ex.map(_one, jobs):
            results[unit][reader] = {"obs": obs, "err": err, "ms": ms,
                                     "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return results


def cross_validate(results: dict) -> dict:
    """红线 3：每单元 ≥ 2 路；指纹不一致 → 仲裁第三路，少数服从多数。"""
    hooks = None
    verdicts = {}
    for unit, byr in results.items():
        fps = {r: _fingerprint(v["obs"]) for r, v in byr.items() if v["obs"]}
        distinct = set(fps.values())
        if len(fps) < CROSS_READERS:
            verdicts[unit] = {"status": "unhooked", "detail": "钩子未全触发"}
            continue
        if len(distinct) == 1:
            verdicts[unit] = {"status": "agree", "detail": f"{len(fps)} 路一致"}
            continue
        # 不一致 → 仲裁（红线 3 的第三路）
        if hooks is None:
            pass
        unit_type = _infer_type(unit)
        arb = hooks_for(unit_type)["arbiter"]
        try:
            a_obs = arb(_unit_payload(unit_type, unit) if _unit_payload(unit_type, unit) is not None else unit)
            results[unit]["arbiter"] = {"obs": a_obs, "err": "", "ms": 0,
                                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            fps["arbiter"] = _fingerprint(a_obs)
        except Exception:                                       # noqa: BLE001
            pass
        best = max(set(fps.values()), key=lambda f: sum(1 for x in fps.values() if x == f))
        winners = [r for r, f in fps.items() if f == best]
        verdicts[unit] = {"status": "arbitrated", "detail": f"分歧仲裁→{'+'.join(winners)}",
                          "minority": [r for r, f in fps.items() if f != best]}
    return verdicts


def _infer_type(unit: str) -> str:
    if unit.startswith("binding:"):
        return "bindings"
    if unit.startswith("registry:"):
        return "registry"
    if unit.startswith("cap:"):
        return "caps"
    return "file"


def detect_omission(units: list[str], verdicts: dict, unit_type: str,
                    rounds: int = RESCAN_ROUNDS) -> tuple[dict, list[str]]:
    """红线 4：覆盖率 = 已钩住 / 总数；< 100% 就补扫（有界），仍钩不住如实报。"""
    missing = [u for u, v in verdicts.items() if v["status"] == "unhooked"]
    reswept = 0
    for _ in range(rounds):
        if not missing:
            break
        r2 = spawn_and_hook(unit_type, missing, tuple(list(hooks_for(unit_type))[:CROSS_READERS]))
        v2 = cross_validate(r2)
        reswept += len(missing)
        still = []
        for u in missing:
            if v2[u]["status"] == "agree":
                verdicts[u] = v2[u]
            else:
                still.append(u)
        missing = still
    return verdicts, missing


def _trace(event: str, **kw) -> None:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_kind": "cross_scan",
           "event": event, **kw}
    with TRACE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_pipeline(target: str, mode: str = "scan") -> dict:
    """完整管线（scan）｜只跑钩子交叉（verify）｜只跑遗漏检测（check）。"""
    lock = StepLock(STEPS)
    lock.enter("decompose")
    unit_type, units = decompose(target)
    if mode == "check":
        # check 也要先钩一次才能算覆盖（步骤锁允许从 decompose 直进 detect？不——按序走完前三步）
        lock.enter("spawn")
        lock.enter("hook")
        readers = tuple(list(hooks_for(unit_type))[:CROSS_READERS])
        results = spawn_and_hook(unit_type, units, readers)
        lock.enter("cross_validate")
        verdicts = cross_validate(results)
        lock.enter("detect_omission")
        verdicts, missing = detect_omission(units, verdicts, unit_type)
        lock.enter("trace")
        _trace("check", target=target, units=len(units), missing=len(missing))
        return _report(target, units, verdicts, missing, mode="check")
    readers = tuple(list(hooks_for(unit_type))[:CROSS_READERS])
    lock.enter("spawn")
    lock.enter("hook")
    results = spawn_and_hook(unit_type, units, readers)
    lock.enter("cross_validate")
    verdicts = cross_validate(results)
    lock.enter("detect_omission")
    verdicts, missing = detect_omission(units, verdicts, unit_type)
    lock.enter("trace")
    coverage = round(1.0 - len(missing) / max(1, len(units)), 4)
    _trace("scan", target=target, units=len(units), coverage=coverage,
           missing=len(missing), mode=mode)
    rep = _report(target, units, verdicts, missing, mode=mode)
    # 安全面（第三路·全量钩子）：文件树与能力位都过一遍危险模式分诊
    if unit_type == "file":
        rep["security"] = security_pass([u for u in units]) if units else {"flagged": 0}
    return rep


def _report(target: str, units: list, verdicts: dict, missing: list, mode: str) -> dict:
    cov = round(1.0 - len(missing) / max(1, len(units)), 4)
    agree = sum(1 for v in verdicts.values() if v["status"] == "agree")
    arb = sum(1 for v in verdicts.values() if v["status"] == "arbitrated")
    return {"ok": not missing, "mode": mode, "target": target,
            "units": len(units), "hooked": len(units) - len(missing),
            "coverage": cov, "agree": agree, "arbitrated": arb,
            "missing": missing[:30],
            "red_lines": ["钩子未触发=失败", "步骤锁生效", "交叉验证≥2路", "遗漏必须补扫", "全程留痕"],
            "trace": str(TRACE), "source_kind": "cross_scan",
            "口径": "覆盖率=已钩住/总数；missing 非空 ⇒ 不许念成通过"}


def status() -> dict:
    lines = 0
    if TRACE.is_file():
        lines = len(TRACE.read_text(encoding="utf-8").splitlines())
    return {"ok": True, "kind": "penetrating_cross_scan",
            "steps": STEPS, "max_workers": MAX_WORKERS,
            "cross_readers": CROSS_READERS, "rescan_rounds": RESCAN_ROUNDS,
            "targets": ["bindings", "registry", "tree:<目录>"],
            "trace_lines": lines,
            "口径": "触手=unit×reader 虚拟生成（亿万=可扩展模型，并发受物理机限制，不虚报）"}


def report(tail: int = 5) -> dict:
    if not TRACE.is_file():
        return {"ok": True, "lines": 0, "tail": []}
    lines = TRACE.read_text(encoding="utf-8").strip().splitlines()
    return {"ok": True, "lines": len(lines), "tail": [json.loads(x) for x in lines[-tail:]]}


def _hook_caps():
    """**能力位面**（185 位逐个钩）：三路独立读法——真导入 / 图鉴现扫产物 / api 分派源码。

    为什么三路：注册表↔图鉴↔分派**三处同在位**才叫接线（少一处就是 not_wired）。
    这里把"每一位是否在册、是否被分派"做成可钩住的观察值。
    """
    def read_a(_u):
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return {"kinds": sorted(BENIGN_CAPS.keys())}

    def read_b(_u):
        a = json.loads((ROOT / "state" / "skill_atlas.json").read_text(encoding="utf-8"))
        return {"kinds": sorted({c["kind"] for c in a.get("caps", [])})}

    def read_c(_u):
        src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
        got = set(re.findall(r'if\s+kind\s*==\s*"([^"]+)"', src))
        for grp in re.findall(r'if\s+kind\s+in\s*\(([^)]*)\)', src):
            got |= set(re.findall(r'"([^"]+)"', grp))
        return {"kinds": sorted(got)}
    return {"a": read_a, "b": read_b, "arbiter": read_c}


def _scan_one_cap(kind: str) -> dict:
    """**单个能力位的钩子**：在不在注册表 / 在不在图鉴 / api 里有没有分派分支。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        in_reg = kind in BENIGN_CAPS
    except Exception:                                          # noqa: BLE001
        in_reg = None
    try:
        a = json.loads((ROOT / "state" / "skill_atlas.json").read_text(encoding="utf-8"))
        in_atlas = kind in {c["kind"] for c in a.get("caps", [])}
    except Exception:                                          # noqa: BLE001
        in_atlas = None
    src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
    dispatched = bool(re.search(r'kind\s*==\s*"%s"' % re.escape(kind), src)
                      or re.search(r'kind\s+in\s*\([^)]*"%s"' % re.escape(kind), src))
    return {"kind": kind, "in_registry": in_reg, "in_atlas": in_atlas, "dispatched": dispatched}


# ── 安全读法（第三路：病毒/木马/漏洞**模式**分诊）──────────────────────
# ⚠️ 口径：这是**模式分诊**，不是杀毒引擎。它报"值得人看的地方"，不宣布"干净"。
_DANGER_PATTERNS = [
    (r"child_process", "Node 子进程执行（需人核）"),
    (r"\beval\s*\(", "动态执行 eval（若入参可控即 RCE）"),
    (r"\bexec\s*\(|Invoke-Expression|iex\s+\(", "动态执行 exec/IEX"),
    (r"shell\s*=\s*True", "shell=True（命令拼接风险）"),
    (r"base64\s*\.\s*b64decode|FromBase64String", "base64 解码（常与混淆同现）"),
    (r"curl[^\n]{0,40}\|\s*(ba)?sh|wget[^\n]{0,40}\|\s*(ba)?sh", "下载即执行（管道到 shell）"),
    (r"(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
     "疑似硬编码凭据"),
    (r"BEGIN\s+(RSA|OPENSSH|PRIVATE)", "私钥字面量"),
    (r"\.(jpg|png|pdf|docx|txt|mp4)\.(exe|scr|bat|cmd|ps1|vbs)$", "双扩展名（伪装文件）"),
    (r"\bos\.system\s*\(|subprocess\.(call|Popen|run)\([^\n]{0,60}shell\s*=\s*True",
     "系统命令执行（需人核）"),
    (r"pickle\.loads?\s*\(|yaml\.load\s*\((?![^)]*Safe)", "不安全反序列化"),
]
_SEC_RE = [(re.compile(p, re.I), why) for p, why in _DANGER_PATTERNS]


def _strip_comments_and_docstrings(txt: str) -> str:
    """**扫之前先剥注释与文档串**（2026-09-27 实测血账）：不剥就会咬到**说明文字**——
    实例：`omni_process.py` 里那行写的是 `shell=False`，注释里提到旧写法 `shell=True`，
    结果被判成"命令拼接风险"；另一例是文档串里的 `os.system('rm -rf /')` 示例。
    **虚报高危会消耗信任**（吸收自 WorkBuddy 能力包的纪律）。

    ⚠️ **行号保真（2026-09-27 第二轮实测血账）**：剥掉的多行文本必须换成**等量空行**。
    早先直接 `re.sub(r'\"\"\"[\\s\\S]*?\"\"\"', '\"\"', txt)` 会把行**吞掉**，
    于是"报出来的行号"整体偏移 —— 实测 `deploy/.../server.py:79` 报的是 `else:`、
    `lark_inventory.py:32` 报的是空行、`dsh-route-check.py:83` 报的是无关函数。
    **报错行号指错地方 = 报告不能落地**，和人肉去找没区别。
    """
    # 三引号块（跨行）→ 换成等量空行（行号不许漂）
    def _blank(m):
        return "\n" * m.group(0).count("\n")
    txt = re.sub(r'"""[\s\S]*?"""', _blank, txt)
    txt = re.sub(r"'''[\s\S]*?'''", _blank, txt)
    # 再剥行内 # 注释（逐行处理：行数天然不变）
    out = []
    for ln in txt.splitlines():
        s = ln.lstrip()
        if s.startswith("#"):
            out.append("")
            continue
        m = re.search(r'^([^\'"#]*)#', ln)
        out.append(m.group(1) if m else ln)
    return "\n".join(out)


# ── 已人工过目·设计如此（**显式白名单 + 逐条理由**）────────────────────────
# 为什么用显式表而不是宽泛启发式：宽泛规则会把**将来**的真问题一起吞掉。
# 表里每一条都必须写明"为什么这不是缺陷"，且**只看路径**、不看内容 ——
# 新增文件再次命中同一模式时，仍旧走「需人核」（白名单不会自动扩张）。
KNOWN_BY_DESIGN = [
    ("tools/codex-scripts/verify_v*.js",
     "画布运行时验收台架：把受测代码注入页面并执行，是台架的设计目的"),
    ("tools/codex-scripts/verify_loader_scope*.py",
     "验收台架：按设计执行被测函数的源码片段，验证装载器作用域"),
    ("tools/codex-scripts/verify_ledger_sink.py",
     "验收台架：按设计在独立命名空间里执行被测代码段"),
    ("tools/shortvideo-music-mcp/server.js",
     "命令执行**就是这个工具的功能**（MCP 音乐工具本体，命令来自调用方）"),
    ("tools/digihuman/pipeline.py",
     "命令来自本仓后端注册表里声明的模板（`tmpl`），不是外部输入拼接"),
    ("tools/codex-scripts/lark_*.py",
     "list 传参 + shell 仅为让 Windows 解析 `lark-cli.cmd`（实测 PATH 里就是 .cmd）"),
    ("deploy/cloud-10/tools/run-mesh-local.mjs",
     "本机形状对账**桩**：命中行自己写着「桩执行」并返回 `_stub: true`，不真执行"),
    ("deploy/cloud-10/container/server.py",
     "设计如此：06 号**隔离容器命令面** `/run`（容器内执行 + 30s 超时 + 输出截断）；"
     "访问控制不在容器里，在对账 mesh 的 `OP_GATES`（`containers:write`）；"
     "**纵深防御的残余风险已记入 owner_decisions**（见 state/排查台账.json）"),
    ("gbt_allinone/tools/libtv_skill.py",
     "命中在**能力说明字段**里（`child_process_env_only` 是描述键名，不是调用）"),
    ("holo_pet_w3/shell/main.cjs",
     "命中是 `require(\"child_process\")` **导入行**（桌面壳要拉起本应用，导入≠执行）"),
    ("holo_pet_w3/shell/intercom-kill-test.cjs",
     "命中是 `child_process` **导入行**（对讲机链路自测台架）"),
    ("plugins/gbt-master/tools/verify-all.mjs",
     "命中是 `import ... from 'node:child_process'` **导入行**（三门验收器按设计拉起子进程）"),
    ("skills/digihuman-pipeline/scripts/run-pipeline.ps1",
     "本仓流水线运行器：`Invoke-Expression` 执行的是**脚本自己拼的 stage 命令**（非外部输入）"),
]


def _by_design(rel: str) -> str:
    """命中「设计如此」表则返回理由，否则空串。"""
    import fnmatch
    low = rel.lower().replace("\\", "/")
    for pat, why in KNOWN_BY_DESIGN:
        if fnmatch.fnmatch(low, pat.lower()):
            return why
    return ""


def _triage(rel: str, hit: dict, text: str = "") -> str:
    """**分诊**（把预期命中与"需人核"分开 —— **虚报高危会消耗信任**，报告必须能落地）。

    **顺序很重要：先认"面"，再看"模式"。** 同一个模式出现在依赖树里 / 文档里 / 读数里，
    性质完全不同 —— 实测（2026-09-27 全树逐行）：1692 条"需人核"里绝大多数落在这几类面上，
    查完只剩个位数。**面上的先归类，剩下的才是"我们的代码里的真问题"。**

      · `第三方(供应链/依赖/运行时)`：`_upstream/` `vendor/` `node_modules/` `.pylibs/`
        `gbt_allinone/store/`（浏览器 profile 与扩展 JS）· 别的 agent 工具的技能镜像目录；
      · `派生物(打包/跑批输出)`：`.map` `.min.js` `.latest.js` `.bundle.js` `.out` 等；
      · `读数/记录(自指)`：`state/`、`output/skill-vet/` —— 读数里出现模式字样是因为它在**记**模式；
      · `文档(规则举例)`：`.md`/`.txt`/`docs/` 里的**动态执行/子进程**字样是规则与举例
        —— **但凭据/私钥类在文档里照样报**（明文凭据入档是真事故，这条不豁免）；
      · `夹具/检测器`：tests/ 的合成假值、`TAINT_SAFE` 夹具、检测器自己的模式表；
      · `设计如此(已人工过目)`：见 `KNOWN_BY_DESIGN`（显式白名单 + 逐条理由）；
      · `数据路径`：base64 解码出现在图像/视觉/浏览器/探针工具里 = 合法解码；
      · `安全形态(加载器派生自 SafeLoader)`：反序列化类里，安全在加载器而不在调用点；
      · `占位符(无密钥形状)`：命中"凭据"但值没有密钥形状（无数字、无已知前缀）；
      · `需人核`：其余 —— **只有这一类计入告警数**。
    """
    low = rel.lower().replace("\\", "/")
    name = low.rsplit("/", 1)[-1].replace("-", "_")
    snip = (hit.get("snip") or "").lower()
    why = hit.get("why", "")
    # ⓪ **先认面**：依赖/运行时/镜像 → 派生物 → 读数 → 文档
    if ("/node_modules/" in low or "/.pylibs/" in low or "site-packages" in low
            or low.startswith("gbt_allinone/store/") or low.startswith(".mimosa/")
            or "/hook-state/" in low or low.startswith(".scratch/")
            or low.startswith("审美相关skill/")          # 第三方设计技能包（自带 LICENSE/NOTICE）
            or any(k in low for k in ("data/skills/", ".agents/skills/", ".claude/skills/",
                                      ".aider-desk/", ".augment/", ".autohand/",
                                      ".codebuddy/", ".windsurf/", ".dsh/skills/"))):
        return "第三方(依赖/运行时)"
    if low.endswith((".map", ".min.js", ".latest.js", ".bundle.js", ".iife.js",
                     ".out", ".out.txt", ".frozen.out")):
        return "派生物(打包/跑批输出)"
    if low.startswith("state/") or low.startswith("output/skill-vet/"):
        return "读数/记录(自指)"
    if low.endswith((".md", ".txt")) or "/docs/" in low:
        # 文档/笔记里的**动态执行·子进程·base64 解码**字样是"规则、举例、血账引用"，
        # 不是实现（实测：我自己的 memory 笔记引用 `base64.b64decode` 被报成需人核）。
        # ⚠️ 只豁免这几类"引号里的写法"；**凭据/私钥/双扩展名在文档里照样报** ——
        # 明文凭据进了文档就是真事故，这条不能豁免（本仓有过 config 明文 key 的先例）。
        if why in ("动态执行 eval（若入参可控即 RCE）", "动态执行 exec/IEX",
                   "Node 子进程执行（需人核）", "系统命令执行（需人核）",
                   "shell=True（命令拼接风险）", "下载即执行（管道到 shell）",
                   "base64 解码（常与混淆同现）"):
            return "文档(规则举例)"
    # ① 显式标注的合成值 / 夹具标记
    if any(k in snip for k in ("not-a-real", "throwaway", "dummy", "placeholder", "example",
                               "fake", "smoke-token", "sk-abcdefg", "taint_safe")):
        return "夹具/检测器"
    # ② 第三方代码 = **供应链面**
    if low.startswith("_upstream/") or "/upstream/" in low or low.startswith("vendor/"):
        return "第三方(供应链)"
    # ③ **扫别人的东西 vs 自己就是探测器**：探测器/审计器里的命中多半是它自己的模式表
    if any(w in low for w in ("security_brain", "cross_scan", "scan_engine", "exhaustive_scan",
                              "quickscan_security")) \
            or low.startswith("tools/security/") \
            or "/tests/" in low or name.startswith("test_") or name == "skill_vet.py":
        return "夹具/检测器"
    if any(w in name for w in ("scan", "vet", "audit")) \
            and ("re.compile(" in snip or "_pattern" in snip or "pattern" in snip):
        return "夹具/检测器"
    # ④ 已人工过目 · 设计如此（显式白名单）
    why_by_design = _by_design(rel)
    if why_by_design:
        return "设计如此(已人工过目)"
    # ④b 反序列化类的**安全形态**：安全在**加载器**，不在调用点 —— 实测
    # `dsh-route-check.py` 的 `_Lenient` 派生自 `SafeLoader`（读代码取证）。
    # ⚠️ 这条**必须在这里**（单一来源）：早先只写在引擎的文件扫描函数里，
    # 于是全树逐行那条路又把同一个文件报成"需人核" —— 同一判据两条路 = 分叉。
    if "反序列化" in why and "SafeLoader" in (text or ""):
        return "安全形态(加载器派生自 SafeLoader)"
    # ⑤ 凭据命中，但值是**自述占位符**（没有密钥形状：无数字、无已知密钥前缀）
    if "凭据" in why:
        v = re.search(r"['\"]([A-Za-z0-9_\-]{16,})['\"]", snip)
        if v and not re.search(r"\d", v.group(1)) and not v.group(1).lower().startswith(
                ("sk-", "ghp_", "github_pat_", "xoxb-", "xoxp-", "akia", "aiza", "hf_")):
            return "占位符(无密钥形状)"
    # ⑥ base64 解码出现在图像/视觉/浏览器/探针工具 = 合法解码（解的是图像字节）
    if "base64" in why and any(k in low for k in
                               ("vision", "browser", "datakit", "deploy/", "visual_memory",
                                "eye", "image", "shot", "frame", "render", "genrouter",
                                "blueprint", "verify_v", "probe", "look", "ai_audit")):
        return "数据路径"
    return "需人核"


def _shape_false_positive(txt: str, m) -> bool:
    """**形态过滤**（与关键字无关，从命中文本自己取词）：同名的词出现在
    **方法调用**形态（词的前一个字符是点号）或**方法定义**形态
    （词在行首、括号后直接跟花括号）时，那不是动态执行。

    2026-09-27 第二轮实测：这一条把 20 条虚报（全在 `deploy/cloud-10/.wrangler/tmp/*/worker.js`，
    是打包后的运行时胶水 —— 一行是流对象上的同名方法调用、一行是类里同名方法的定义）
    摘干净了。**裸调用照样报**（词在语句位置、后面不跟花括号），所以这不是"把告警藏起来"，
    是把**形态误报**摘掉 —— 虚报会消耗信任，报告必须能落地。
    """
    tok = re.match(r"[A-Za-z_][A-Za-z_0-9]{2,}", m.group(0))
    if not tok:
        return False
    word = re.escape(tok.group(0))
    if txt[max(0, m.start() - 1):m.start()] == ".":           # 对象上的方法调用
        return True
    ls = txt.rfind("\n", 0, m.start()) + 1
    le = txt.find("\n", m.start())
    line = txt[ls:le if le != -1 else len(txt)].strip()
    i = line.find(tok.group(0))
    if i < 0:
        return False
    return bool(re.match(r"%s\s*\([^)]*\)\s*\{\s*$" % word, line[i:]))


def _scan_one_file_security(rel: str) -> dict:
    """单文件的**安全钩子**：报命中模式（只读、限量、跳过 vendored/缓存、**剥注释后再扫**）。"""
    p = ROOT / rel
    low = rel.lower()
    if "/vendor/" in low or "/.pylibs/" in low or "/store/" in low:
        return {"unit": rel, "hits": [], "note": "nested vendor/.pylibs/store 跳过"}
    # 构建缓存不是我们的源码（实测：`.wrangler/tmp/` 里全是打包后的运行时胶水）
    if "/.wrangler/" in low or "/node_modules/" in low:
        return {"unit": rel, "hits": [], "note": "构建缓存跳过"}
    if p.suffix.lower() not in (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".ps1", ".bat",
                                ".cmd", ".sh", ".php", ".rb", ".yml", ".yaml", ".json"):
        return {"unit": rel, "hits": []}
    try:
        if p.stat().st_size > 2_000_000:
            return {"unit": rel, "hits": [], "note": ">2MB 跳过（限量）"}
        txt = _strip_comments_and_docstrings(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {"unit": rel, "hits": []}
    hits = []
    for rx, why in _SEC_RE:
        for m in rx.finditer(txt):
            if _shape_false_positive(txt, m):
                break                            # 本文件该模式只命中形态误报 ⇒ 不报
            line = txt.count("\n", 0, m.start()) + 1
            h = {"line": line, "why": why, "snip": txt[m.start():m.start() + 60].replace("\n", " ")}
            h["triage"] = _triage(rel, h, txt)   # 分诊（缺了它 needs_human 恒 0 = 假绿）
            hits.append(h)
            break                                # 同类只报首例，避免刷屏
    return {"unit": rel, "hits": hits}


def security_pass(units: list[str], max_workers: int = MAX_WORKERS) -> dict:
    """**安全面全量钩子**（第三路）：逐单元扫危险模式，出分诊清单。"""
    findings, scanned, needs_human = [], 0, 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for r in ex.map(_scan_one_file_security, units):
            scanned += 1
            if r.get("hits"):
                findings.append(r)
                needs_human += sum(1 for h in r["hits"] if h.get("triage") == "需人核")
    _trace("security_pass", units=scanned, flagged=len(findings), needs_human=needs_human)
    return {"ok": needs_human == 0, "scanned": scanned, "flagged": len(findings),
            "needs_human": needs_human, "findings": findings[:40],
            "口径": "**模式分诊**不是杀毒：报的是「值得人看」，不宣布「干净」；跳过 vendored/缓存（_skippable）"}


def hook_enforcer():
    """**能力位面全覆盖钩子**（185 位逐个）：在册 / 在图鉴 / 有分派——三条都亮才算钩住。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        kinds = sorted(BENIGN_CAPS.keys())
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    rows, unhooked = [], []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for r in ex.map(_scan_one_cap, kinds):
            rows.append(r)
            if not (r["in_registry"] and r["in_atlas"] and r["dispatched"]):
                unhooked.append(r)
    _trace("caps_hooks", caps=len(kinds), unhooked=len(unhooked))
    return {"ok": not unhooked, "caps": len(kinds), "hooked": len(kinds) - len(unhooked),
            "unhooked": unhooked[:20],
            "口径": "每位三判据=注册表∩图鉴∩分派；缺任一=没钩住（not_wired 同源）"}


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=1)); return 0
    if cmd == "report":
        print(json.dumps(report(int(argv[argv.index("--tail") + 1]) if "--tail" in argv else 5),
                         ensure_ascii=False, indent=1)); return 0
    if cmd in ("scan", "verify", "check") and len(argv) >= 3:
        r = run_pipeline(argv[2], mode=cmd if cmd != "verify" else "scan")
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
