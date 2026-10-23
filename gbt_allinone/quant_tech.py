"""GBT 量化技术能力（读取 Workspace 项目真实代码，返回真实技术分析）。

只读：解析量化引擎/回测 API 的类、信号、参数模型。不读取 .env/密钥，不触发任何交易。"""
import os
import re
from pathlib import Path

# 🔴 2026-09-26 修：原来写死本机绝对路径 —— 换机/换用户即静默降级 no_engine_found；现在可用环境变量改
# 🔴 2026-10-04 修：默认落点从 `Desktop\Workspace` **收编进仓内** `quant_workspace/`
#    （主人令「源码集中到一棵工作树」；旧桌面 Workspace 已归档到 .old-projects-20261004）
WS = Path(os.environ.get("GBT_QUANT_WS")
          or str(Path(__file__).resolve().parent.parent / "quant_workspace"))
ENGINE_FILES = [
    WS / "01_量化收割引擎" / "cis_scalper" / "cis_quant_engine.py",
    WS / "01_量化收割引擎" / "cis_harvesting" / "cis_harvesting_system_v2.py",
]
BACKTEST_FILES = [
    WS / "01_量化收割引擎" / "backtest" / "backtest_api_v3.py",
    WS / "01_量化收割引擎" / "backtest" / "backtest_engine_v3.py",
]


def _read_first(p, n=400):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:n]
    except Exception:
        return ""


def _extract_enums(text):
    """提取所有 enum 类名与其成员。"""
    enums = []
    for m in re.finditer(r"class\s+(\w+)\(Enum\):([^\n]*(?:\n\s{4}\w+[^\n]*)*)", text):
        name = m.group(1)
        members = re.findall(r"^\s{4}(\w+)\s*=\s*[\"']?([^\"'\n]*)", m.group(2), re.M)
        enums.append({"enum": name, "members": [a for a, b in members]})
    return enums


def _extract_dataclass_fields(text):
    """提取标 @dataclass 的类及其字段。

    🔴 2026-09-22 修（深蒸 finance 域时抓到的真缺陷 —— **假空**，不是推测）：
    原正则 `@dataclass\\s*\\nclass\\s+(\\w+):\\n((?:[ \\t]+\\w+.*\\n)+)` 要求**类体首行以 \\w 开头**，
    而真实类体首行常是 docstring / 注释 ⇒ **整块失配**：文件里明明有两个 @dataclass，
    读数却报 `dataclasses: []`（实测 `cis_quant_engine.py` → `[]`，放宽版才命中
    `['CISPosition','CISConfig']`）。"看起来没有"和"真没有"是两件事，这条是前者。
    改法：先按行锚定类头（不会被 `@dataclass` 里的 `dataclass` 字样干扰），
    再逐行收**带注解的字段**，跳过 docstring/注释/装饰器/方法定义，遇到缩进结束即止。
    """
    out = []
    for m in re.finditer(r"(?m)^[ \t]*@dataclass[^\n]*\n[ \t]*class[ \t]+(\w+)[ \t]*:", text):
        cls = m.group(1)
        fields = []
        for line in text[m.end():].splitlines():
            if not line.strip():
                continue
            if not line[:1].isspace():      # 缩进结束 = 类体结束
                break
            s = line.strip()
            if s.startswith(("#", '"', "'", "@", "def ", "class ")):
                continue
            if s.startswith(("return", "if ", "for ", "while ", "with ", "try", "except", "else", "elif")):
                continue
            name = s.split(":")[0].strip().lstrip("*")
            if ":" in s and name.isidentifier():
                fields.append(name)
        out.append({"class": cls, "fields": fields})
    return out


def quant_strategy():
    """读取真实量化引擎，返回策略信号模型与仓位模型。"""
    report = {}
    for p in ENGINE_FILES:
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        report[p.name.replace(".py", "")] = {
            "enums": _extract_enums(t),
            "dataclasses": _extract_dataclass_fields(t),
            "bytes": len(t.encode("utf-8")),
        }
    if not report:
        return {"status": "no_engine_found", "hint": str(WS)}
    return {"engine_files": [p.name for p in ENGINE_FILES if p.exists()], "models": report}


def quant_backtest():
    """读取真实回测 API，返回类/函数/参数线索。"""
    report = []
    for p in BACKTEST_FILES:
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        # 🔴 2026-09-22 修（同批抓到的第二处缺陷 —— **假名**）：
        # 原正则 `class\s+(\w+)` **不加行锚**，而 `@dataclass` 这个词本身含 "class" 字样
        # ⇒ 从 `dataclass` 尾部起匹配、`\s+` 吃掉换行、`(\w+)` 抓走下一行的字面量 `class`：
        # 实测 `backtest_engine_v3.py` 的 classes = ['class','class','BaseStrategy',…]
        # —— 两条垃圾进榜，**真类名（Position/Trade）反被吃掉**。
        # 改法：行锚 `(?m)^\s*class\s+(\w+)`，行首必须是 class 本身。
        classes = re.findall(r"(?m)^[ \t]*class[ \t]+(\w+)", t)
        funcs = re.findall(r"def\s+(\w+)", t)
        params = re.findall(r"(\w+)\s*:\s*[A-Za-z_][\w.]*\s*=\s*([^\n,]+)", t)
        report.append({"file": p.name, "classes": classes[:20], "functions": funcs[:20],
                       "default_params": dict(params[:30])})
    return {"backtest_modules": report}


_PROFILE_CACHE = {"ts": 0.0, "data": None}


def platform_profile(ttl: int = 30):
    """读取 Workspace 项目结构（真实；TTL 缓存——目录遍历 87ms→首次后 0ms）。

    缓存 30 秒：项目结构不会秒级变化，而调用方（autopilot/巡检）可能高频调。
    """
    import time as _t
    if _PROFILE_CACHE["data"] is not None and _t.time() - _PROFILE_CACHE["ts"] < ttl:
        return dict(_PROFILE_CACHE["data"])
    profile = {"workspace": str(WS), "exists": WS.exists(), "top_level_dirs": [],
               "quant_py": 0, "py_total": 0}
    if WS.exists():
        from .tools import scan_scope                     # 局部导入：避免模块级串环
        profile["top_level_dirs"] = sorted(d.name for d in WS.iterdir() if d.is_dir())
        # 仓内 .py 走**唯一扫描口径**（tools/scan_scope）：剪枝发生在进入子目录之前。
        # 2026-09-22 修：此前 `WS.rglob("*.py")` 会把 vendor/pylibs(3106)、
        # _upstream(889)、.shadow-repo(627) 全数吞进去 —— 本机实测直接把
        # `platform_profile` 拖到走不完。这是**生产路径**，不是测试，性质更重。
        # 现在只算本仓代码面，并**把被排除的量一并报出来**：
        # 免得"数字变小了却说不清小在哪"（那和作假只差一层纸）。
        profile["py_total"] = sum(1 for _ in scan_scope.iter_files(WS, suffixes=(".py",)))
        profile["py_excluded"] = {k: v["py_files"]
                                  for k, v in scan_scope.corpus_sizes(WS).items()
                                  if v.get("exists")}
        qdir = WS / "01_量化收割引擎"
        profile["quant_py"] = sum(1 for _ in scan_scope.iter_files(qdir, suffixes=(".py",))) \
            if qdir.exists() else 0
    _PROFILE_CACHE["ts"] = _t.time()
    _PROFILE_CACHE["data"] = profile
    return dict(profile)


def quant_params():
    """读取真实量化引擎的数值型策略参数（如动量周期/阈值/止损倍数）。"""
    out = {}
    for p in ENGINE_FILES:
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        params = {}
        for m in re.finditer(r"^\s*(\w+)\s*:\s*(?:int|float)\s*=\s*([0-9]+(?:\.[0-9]+)?)", t, re.M):
            params[m.group(1)] = float(m.group(2))
        out[p.name] = params
    return {"engine_params": out}
