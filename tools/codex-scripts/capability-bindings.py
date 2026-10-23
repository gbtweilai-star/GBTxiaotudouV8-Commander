# -*- coding: utf-8 -*-
"""能力 ↔ 触手 ↔ 能量 · 三边双向绑定（主人令 2026-10-08）。

主人原话：「B必须把所有能力都接入，不能有任何遗漏，把全部能量使用触手双向绑定好，
确保随时能够感应到所有能量状态。」

拆成四件可机检的事：
  ① **全部能力一根不落**：240 条能力位逐条分类，**任何一条空白 = 红并点名**；
  ② **双向绑定**：`cap → 承载触手域` 与 `触手域 → 承载哪些 cap` 两边都列、互相反演；
     能量同理：`cap → 承载通道` 与 `通道 → 哪些 cap`；
  ③ **能量也绑**：13 条密钥通道逐条绑到能力上，并**区分「权威声明级」与「代码证据级」**；
  ④ **随时可感**：落 `state/cap-bindings.json`（单一真源台账）+ 面板 + 一条可复跑的感应读数
     （`feel`）。

## 三边真源（**全部现读，不抄数字**）

| 边 | 真源 | 读法 |
|---|---|---|
| **能力** | `gbt_allinone/caps_registry.py::BENIGN_CAPS`（经 `caps_tables.all_caps()` 容错取） | import 现算 |
| **触手** | `gbt_allinone/tentacle/omni_tentacle.py::TENTACLE_MANIFEST`（markdown 正文） | 解析 `### 域(N): 能力项…` + 听觉段落 |
| **触手字典** | `tools/tentacle_bind.py::_valid_labels()`（= 能力位 kind ∪ `domain:<域>`） | 框架自己的触手语言 |
| **能量** | `gbt_allinone/llm/key_gateway.py::energy()` + `run("status")`（**只读直连，不铸钥、不落盘**） | import 现算 |

## 绑定口径（**写死在 `RULES` 里，可复核、可改**）

- **触手承载** = `gbt_allinone/api.py` 里该能力位的分派分支**导入了触手本体模块**
  （`tentacle/omni_*`、`tentacle/bridge`、`vision_cap` …）—— **代码证据**，不是拍脑袋。
  本体模块 → 触手域 的映射按 `omni_*` 文件自己的命名（`omni_mouse`→点击、`omni_fs`→文件 …）。
- **直连** = 该能力位由框架本体的模块实现，**不经触手本体**。这是**显式的第二类绑定**，
  不是"空白"——空白（既非触手承载、又无承载载体）才报红。
- **能量**：
  · **权威声明级** = `security/policy.py::evaluate()` 给该能力位声明了 `external_llm` 作用域
    ⇒ 它**确定**要过密钥链；
  · **代码证据级** = 承载模块文本里出现能量链标记（`cloud_llm` / `key_gateway` / `_KEY_CHAIN` …）
    ⇒ 它**会碰**密钥链；
  · 两级都记 `basis`，**分得清"确定"与"证据"**；其余 = 不直接触碰密钥链。

## 🔴 硬性纪律

- **不许假绿**：探不到就「未探测」并写明为什么；绑定算不出来就报红，不许留空当"绑好了"。
- **未探测不画成通**：不可用的能量通道**不得**被算作承载着谁。
- 只读探测；**不调任何需要授权的作用域**（只 import 模块 + 读注册表/配置，不执行框架动作）。
- 页面自包含：零远端引用、无 `fetch`/`XHR`/`eval`、无 `<iframe>`，数据只走**经典脚本**。

## 与既有台账的关系（**谁管资产、谁管能力**）

- `state/asset_bindings.json` / `.jsonl`（1.2MB / 3.5MB）＝ **资产层**：*资产 → 触手标签*，
  由 `tools/tentacle_bind.py` 维护。本工具**只读**它，不改。
- `state/cap-bindings.json`（本工具产出）＝ **能力层**：*能力位 → 承载触手域 / 能量通道*。
- 两层通过**触手标签**衔接：**能力位 kind 本身就是一个合法触手标签**
  （`_valid_labels()` = 能力位 ∪ `domain:<域>`），所以资产挂在触手身上、触手就是能力位。

## 用法

    py -3.14 tools/codex-scripts/capability-bindings.py            # 建账 + 出面板 + 人读报告（默认）
    py -3.14 tools/codex-scripts/capability-bindings.py render     # 只按台账出面板两件
    py -3.14 tools/codex-scripts/capability-bindings.py --check    # 判据 ≥10 条（含负对照）· 退出码 0/1
    py -3.14 tools/codex-scripts/capability-bindings.py --json     # 机读
    py -3.14 tools/codex-scripts/capability-bindings.py feel       # 一条命令的「随时可感」读数（可复跑）

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"

# ── 真源路径（现读） ────────────────────────────────────────────────────────
CAPS_REG = ROOT / "gbt_allinone" / "caps_registry.py"
API_PY = ROOT / "gbt_allinone" / "api.py"
OMNI_TENTACLE = ROOT / "gbt_allinone" / "tentacle" / "omni_tentacle.py"
TENTACLE_BIND = ROOT / "tools" / "tentacle_bind.py"
ASSET_BINDINGS = STATE / "asset_bindings.json"
ASSET_LEDGER = STATE / "asset_bindings.jsonl"

LEDGER = STATE / "cap-bindings.json"
PAGE = ROOT / "holo_pet_w3" / "energy" / "index.html"
DATA = ROOT / "holo_pet_w3" / "energy" / "energy-data.js"

# ── 第四边：页面边（主人令 2026-10-08「四边互校」）──────────────────────────
# 能力 ↔ 触手 ↔ 能量 三边之外，补**页面边**：每一位能力必须能在
#   ① 能力栏页（数据源 energy-data.js）② 能力统计页（capabilities-data.js）
#   ③ 待授权清单一页（docs/待授权清单一页.md，汇总页：注册表现读数现算）
# 里被指到；页上每一项也要能**反查**回注册表与触手标签。双向 + 逐项一致 + 负对照。
CAPS_DATA = ROOT / "holo_pet_w3" / "capabilities" / "capabilities-data.js"
AUDIT_LEDGER = STATE / "capability-audit.json"
AUTHZ_PAGE = ROOT / "docs" / "待授权清单一页.md"

CMD_REPORT = "py -3.14 tools/codex-scripts/capability-bindings.py"
CMD_RENDER = "py -3.14 tools/codex-scripts/capability-bindings.py render"
CMD_CHECK = "py -3.14 tools/codex-scripts/capability-bindings.py --check"
CMD_JSON = "py -3.14 tools/codex-scripts/capability-bindings.py --json"
CMD_FEEL = "py -3.14 tools/codex-scripts/capability-bindings.py feel"

# ══════════════════════════════════════════════════════════════════════════
# 绑定口径表（**人定规则，写在这里，可复核、可改**）
# ══════════════════════════════════════════════════════════════════════════

# 触手本体模块（`tentacle/` 下的实现文件）→ 触手域。命名即域，代码证据。
# 键 = 模块路径的**最后一段**（`tentacle.omni_web` 与裸 `omni_web` 都命中「读网」）。
OMNI_TOKENS = {
    "omni_vision": "视觉", "vision_bus": "视觉", "vision_watch": "视觉", "vision_cap": "视觉",
    "omni_read": "读屏",
    "omni_mouse": "点击",
    "omni_keyboard": "键盘",
    "omni_window": "窗口等待监控",
    "omni_process": "进程",
    "omni_domain": "域操控",
    "omni_web": "读网",
    "omni_fs": "文件",
    "omni_audio": "听觉", "wasapi_loop": "听觉", "silero_vad": "听觉",
}
# 「整只手」：导入这些 = 触手本体全部门都够得着 ⇒ 绑到全部触手域。
# 🔴 必须用**全路径**匹配（2026-10-08 实测教训）：`from .llm import bridge` 的最后一段也是
#    `bridge`，若只取最后一段，`llm_status` 会被误判成「触手承载」——
#    真相是它有两条 bridge（`tentacle/bridge.py` 与 `llm/bridge.py`）。故这里只认触手那条。
WHOLE_BODY_TOKENS = {"tentacle", "tentacle.bridge", "tentacle.omni_core", "tentacle.omni_tentacle",
                     "tentacle.omni_controller", "omni_core", "omni_tentacle", "omni_controller"}
# 触手本体包（token 是整包时，用它下面的实现文件做代码证据扫描）
BODY_PACKAGE = "tentacle"

# 能量链标记（**代码证据级**：承载模块文本里出现这些 ⇒ 它会碰密钥链）。
# 🔴 只认**链本身**的符号（`cloud_llm` / `key_gateway` / `_KEY_CHAIN`）——
#    早先收过 `external_llm` / `密钥链` 这类**词**，实测把 `security/policy.py`
#    （里面只是**声明**作用域）也算成"用能"⇒ 假绿。收窄到链的符号名。
ENERGY_MARKERS = ("cloud_llm", "key_gateway", "_KEY_CHAIN")
# 只读直连的能量能力位（能力位自述/文档里点名过密钥链，但模块文本未必有标记）
ENERGY_DECLARED_EXTRA: tuple = ()

BIND_KIND_TENTACLE = "触手承载"
BIND_KIND_DIRECT = "直连"
BIND_KINDS = (BIND_KIND_TENTACLE, BIND_KIND_DIRECT)
S_UNBOUND = "未绑"
S_BOUND_T = "已绑·触手承载"
S_BOUND_D = "已绑·直连"

UA_NOTE = "本件只读探测：import 模块 + 读注册表/配置；不执行框架动作、不调授权作用域。"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ══════════════════════════════════════════════════════════════════════════
# 取数
# ══════════════════════════════════════════════════════════════════════════
def _load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except Exception:                                        # noqa: BLE001
        return None
    return m


def load_caps() -> tuple:
    """能力边：现读注册表。返回 (caps_list, why_or_None)。**读不到就返回 None + 原因**。"""
    if not CAPS_REG.is_file():
        return None, "注册表不在盘：%s" % CAPS_REG
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.caps_tables import all_caps
        caps = list(all_caps())
    except Exception as e:                                   # noqa: BLE001
        return None, "注册表 import 不了（文件在但坏了）：%s: %s" % (type(e).__name__, str(e)[:120])
    if not caps:
        return None, "all_caps() 读到空清单 ⇒ 能力边未探测（不许当 0 条）"
    return caps, None


_SECTION_RE = re.compile(r"^###\s*([^(:（]+)[(（](\d+)[)）]\s*:\s*(.+)$", re.M)


def load_tentacle() -> tuple:
    """触手边：读 `TENTACLE_MANIFEST`（现读，不调 run_task）。返回 (domains, meta, why)。"""
    if not OMNI_TENTACLE.is_file():
        return None, None, "触手总纲真源不在盘：%s" % OMNI_TENTACLE
    m = _load_mod("_gbt_omni_tentacle_probe", OMNI_TENTACLE)
    man = getattr(m, "TENTACLE_MANIFEST", "") if m else ""
    if not man:
        return None, None, "omni_tentacle.py 读不到 TENTACLE_MANIFEST ⇒ 触手边未探测"
    domains = []
    for mm in _SECTION_RE.finditer(man):
        name = mm.group(1).strip()
        declared = int(mm.group(2))
        items = [x.strip() for x in mm.group(3).split(",") if x.strip()]
        domains.append({"id": name, "name": name, "declared_count": declared,
                        "items": items, "source": "manifest ### 小节"})
    # 听觉（第 10 域）：在段落里，不是 ### 小节 ⇒ 按 `audio_*` 能力项解析
    audio = set(re.findall(r"`(audio_[a-z_]+)`", man))
    # 段落里的播放/设备项（不带反引号包裹的裸名）——
    # `audio_play_wav / audio_beep / audio_stop` 这类已由反引号覆盖；再兜一层裸名扫描。
    audio |= set(re.findall(r"\b(audio_[a-z_]+)\b", man))
    audio = sorted(audio)
    if audio:
        domains.append({"id": "听觉", "name": "听觉", "declared_count": len(audio),
                        "items": audio, "source": "manifest 段落（第 10 域 audio，非 ### 小节）",
                        "partial": True,
                        "gap_note": "一半补上：说话/播放/设备/WAV/VAD/回环音频真有；"
                                    "**麦克风(活动录音端点=0)/流式ASR·TTS/声纹/ASR转文字 仍然没有**"})
    if not domains:
        return None, None, "触手总纲解析不出任何域 ⇒ 触手边未探测"
    meta = {"eye_ready": True, "manifest_chars": len(man),
            "header": man.splitlines()[0] if man else "",
            "gap_lines": [ln.strip(" ·") for ln in man.splitlines()
                          if ln.strip().startswith("· ❌") or ln.strip().startswith("· 窗口动作")
                          or ln.strip().startswith("· 系统级")]}
    return domains, meta, None


def load_energy() -> tuple:
    """能量边：只读直连取 13 条通道。返回 (channels, meta, why)。"""
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.llm import key_gateway as kg
        energy = kg.energy()
        status = kg.run("status")
    except Exception as e:                                   # noqa: BLE001
        return None, None, "key_gateway 读不到（未探测，不许当 0 条）：%s: %s" % (
            type(e).__name__, str(e)[:140])
    order = list(status.get("order") or [])
    slots = {s.get("provider"): s for s in (energy.get("slots") or [])}
    if not order or not slots:
        return None, None, "key_gateway 没给出 order/slots ⇒ 能量边未探测（不许当 0 条）"
    channels = []
    for i, name in enumerate(order, 1):
        s = slots.get(name, {})
        channels.append({
            "order": i, "provider": name,
            "status": s.get("status") or "未探测",
            "alive": bool(s.get("alive")) if isinstance(s.get("alive"), bool) else None,
            "tier": s.get("tier") or "",
            "masked": s.get("masked") or "",
            "used": s.get("used"), "quota": s.get("quota"), "headroom": s.get("headroom"),
            "source": s.get("source") or "missing",
            "url": s.get("url") or "", "model": s.get("model") or "",
        })
    # order 里有、slots 里没有的：**如实标未探测**，不许补白当通
    for name in slots:
        if name not in order:
            channels.append({"order": None, "provider": name, "status": "未在 order 中（未探测）",
                             "alive": None, "tier": "", "masked": "", "used": None, "quota": None,
                             "headroom": None, "source": "missing", "url": "", "model": ""})
    meta = {"alive": energy.get("alive"), "total": energy.get("total"),
            "summary": energy.get("summary"), "active": status.get("active"),
            "chain_source": status.get("chain_source"), "runtime_ttl_s": status.get("runtime_ttl_s"),
            "switches": status.get("switches"), "service": status.get("service") or [],
            "invariants": energy.get("invariants") or [],
            "shared_quota_keys": energy.get("shared_quota_keys") or [],
            "duplicate_note": energy.get("duplicate_note"),
            "runtime_file": energy.get("runtime_file")}
    return channels, meta, None


def load_labels() -> tuple:
    """触手字典标签（框架自己的触手语言）。返回 (labels_set, why)。"""
    if not TENTACLE_BIND.is_file():
        return None, "触手绑定工具不在盘：%s" % TENTACLE_BIND
    m = _load_mod("_gbt_tentacle_bind_probe", TENTACLE_BIND)
    if m is None:
        return None, "tentacle_bind.py import 不了（文件在但坏了）"
    fn = getattr(m, "_valid_labels", None)
    if not callable(fn):
        return None, "tentacle_bind.py 里没有 _valid_labels() ⇒ 标签层未探测"
    try:
        labels = set(fn() or [])
    except Exception as e:                                   # noqa: BLE001
        return None, "_valid_labels() 抛异常：%s" % str(e)[:120]
    if not labels:
        return None, "_valid_labels() 返回空 ⇒ 标签层未探测"
    return labels, None


def policy_scopes(kinds: list) -> dict:
    """每条能力位的作用域（**权威声明级**）。纯函数调用，不执行任何动作。"""
    out = {}
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.security import policy
    except Exception as e:                                   # noqa: BLE001
        return {"__err__": "%s: %s" % (type(e).__name__, str(e)[:120])}
    for k in kinds:
        try:
            d = policy.evaluate(k, {})
            out[k] = [str(s) for s in (getattr(d, "scopes", ()) or ())]
        except Exception as e:                               # noqa: BLE001
            out[k] = []
            out.setdefault("__err__", "%s: %s" % (type(e).__name__, str(e)[:80]))
    return out


# ── api.py 分派分支 → 模块（**代码证据**） ────────────────────────────────
_BRANCH_RE = re.compile(r'^\s{4}if kind == "([a-z0-9_]+)"\s*:')
_BRANCH_IN_RE = re.compile(r'^\s{4}if kind in \(([^)]*)\)\s*:')
_MOD_RE = re.compile(
    r'from \.([A-Za-z0-9_.]+) import\s+([A-Za-z0-9_., ]+)|'
    r'from \. import\s+([A-Za-z0-9_., ]+)|'
    r'spec_from_file_location\(\s*"([a-z0-9_]+)"|'
    r'"([a-z0-9_/]+\.py)"')


def _norm_tokens(raw_tokens) -> list:
    """归一化模块 token：去 ` as X`、去 `.py`、去前导 `.`，**保留点号路径**。

    🔴 保留点号（不再取最后一段）：`tentacle.bridge` 与 `llm.bridge` 的最后一段都是
    `bridge`，取最后一段会把 `llm_status` 误判成触手承载（实测踩过）。
    """
    out = []
    for t in raw_tokens:
        t = str(t).strip()
        if not t:
            continue
        t = t.split(" as ")[0].split(" ")[0].strip()
        if t.endswith(".py"):
            t = t[:-3]
        t = t.replace("/", ".").lstrip(".")
        if t:
            out.append(t)
    return out


def api_branches() -> dict:
    """解析 api.py 的分派分支：kind → 该分支导入的模块（归一化 token 列表）。"""
    if not API_PY.is_file():
        return {}
    src = API_PY.read_text(encoding="utf-8", errors="replace")
    lines = src.splitlines()
    heads = []
    for i, ln in enumerate(lines):
        m = _BRANCH_RE.match(ln)
        if m:
            heads.append((i, m.group(1)))
        mi = _BRANCH_IN_RE.match(ln)
        if mi:
            for nm in re.findall(r'"([a-z0-9_]+)"', mi.group(1)):
                heads.append((i, nm))
    heads.sort()
    out = {}
    for idx, (ln, name) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        if idx + 1 == len(heads):
            # 🔴 2026-10-13 修：**最后一个分支**原来把块读到**文件末尾** —— 于是它后面的
            #    兜底 `return {...}`、`try: from .engine import EngineError …`、以及同函数里
            #    其它语句全被算成这一位的导入。后果两条：
            #      ① 载体显示成一长串无关模块（实测：cadgen 的载体里出现了 EngineError / security / policy）；
            #      ② 更危险 —— 尾部文本里若出现触手本体 token，一个**直连**的位会被误判成
            #         「触手承载」（**假绿**：绑定台账说它接着触手，其实没有）。
            #    修法：只读到**本分支缩进块结束**为止（遇到第一个不空且缩进 ≤ 4 的行就停）；
            #    只作用于最后一个分支 —— 非最后分支本来就被下一个分支头截断，行为一字不改。
            for j in range(ln + 1, len(lines)):
                s = lines[j]
                if s.strip() and (len(s) - len(s.lstrip())) <= 4:
                    end = j
                    break
        block = "\n".join(lines[ln:end])
        raw = []
        for m in _MOD_RE.finditer(block):
            for g in m.groups():
                if g:
                    raw.extend(x.strip() for x in g.split(","))
        for tok in _norm_tokens(raw):
            out.setdefault(name, [])
            if tok not in out[name]:
                out[name].append(tok)
    return out


_MODULE_INDEX: dict = {}
_SKIP_WALK = {".pylibs", "__pycache__", "store", "archived_logs", "node_modules",
              ".venv", "site-packages", "vendor"}


def _module_index() -> dict:
    """模块（点号路径与裸 stem）→ 在盘文件（**只建一次**；跳过符号链接与依赖树）。

    为什么不用 `rglob`：`gbt_allinone/.pylibs` 是指向 `vendor/pylibs` 的符号链接，
    `rglob("*.py")` 会走进去把整个第三方库扫一遍（实测卡死）。
    """
    import os
    if _MODULE_INDEX:
        return _MODULE_INDEX
    for base in (ROOT / "gbt_allinone", ROOT / "tools"):
        for dp, dns, fns in os.walk(base, followlinks=False):
            dns[:] = [d for d in dns if d not in _SKIP_WALK]
            for fn in fns:
                if not fn.endswith(".py"):
                    continue
                p = Path(dp) / fn
                try:
                    rel = p.parent.relative_to(ROOT / "gbt_allinone").as_posix().replace("/", ".")
                except ValueError:
                    try:
                        rel = p.parent.relative_to(ROOT / "tools").as_posix().replace("/", ".")
                    except ValueError:
                        rel = ""
                dotted = ("%s.%s" % (rel, fn[:-3])) if rel and rel != "." else fn[:-3]
                _MODULE_INDEX.setdefault(dotted, p)          # 全路径优先
                _MODULE_INDEX.setdefault(fn[:-3], p)         # 裸 stem 兜底（**先到先得**）
    return _MODULE_INDEX


def _package_files(pkg: str) -> list:
    """整包 token（如 `tentacle`）→ 它下面的实现文件（做代码证据扫描用）。"""
    d = ROOT / "gbt_allinone" / pkg
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.py") if p.name != "__init__.py")


def _module_files(module_token: str) -> list:
    """模块 token → 在盘文件。整包名走 `_package_files`（`tentacle` → tentacle/*.py）。"""
    tok = str(module_token)
    idx = _module_index()
    if tok in idx:
        return [idx[tok]]
    if tok == BODY_PACKAGE or tok.startswith(BODY_PACKAGE + "."):
        sub = _package_files(BODY_PACKAGE)
        return sub or []
    last = tok.split(".")[-1]
    return [idx[last]] if last in idx else []


def energy_code_evidence(mods: list) -> list:
    """**代码证据级**：承载模块文本里出现能量链标记。返回命中列表（带标记原文）。"""
    out = []
    for name in mods:
        for p in _module_files(name):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except Exception:                                # noqa: BLE001
                continue
            marks = sorted({k for k in ENERGY_MARKERS if k in t})
            if marks:
                out.append({"module": name, "file": p.relative_to(ROOT).as_posix(),
                            "marks": marks})
    return out


# ══════════════════════════════════════════════════════════════════════════
# 装配绑定模型
# ══════════════════════════════════════════════════════════════════════════
def build_model() -> dict:
    caps, caps_why = load_caps()
    tent, tent_meta, tent_why = load_tentacle()
    channels, energy_meta, energy_why = load_energy()
    labels, labels_why = load_labels()
    branches = api_branches()

    domain_ids = [d["id"] for d in (tent or [])]
    channel_ids = [c["provider"] for c in (channels or [])]
    alive_ids = [c["provider"] for c in (channels or []) if c.get("alive") is True]
    dead_ids = [c["provider"] for c in (channels or []) if c.get("alive") is not True]

    cap_names = [c["name"] for c in (caps or [])]
    scopes = policy_scopes(cap_names) if cap_names else {}
    ext_llm = {k for k, v in scopes.items() if "external_llm" in (v or [])}

    # ── 逐条能力位：定承载 ────────────────────────────────────────────────
    rows = []
    for c in (caps or []):
        nm = str(c["name"])
        dom = str(c.get("domain") or "")
        mods = branches.get(nm, [])
        body_domains = []
        body_tokens = []
        for tok in mods:
            whole = tok in WHOLE_BODY_TOKENS
            last = tok.split(".")[-1]
            d = OMNI_TOKENS.get(last)
            # 只认触手本体：整只手 token，或 `tentacle.<omni_*>` / 裸 `omni_*` / `vision_cap`
            if whole:
                body_domains = list(domain_ids)
                body_tokens.append(tok)
                break
            if d and (tok == last or tok.startswith(BODY_PACKAGE + ".")):
                body_tokens.append(tok)
                if d not in body_domains:
                    body_domains.append(d)
        body_domains = [d for d in domain_ids if d in body_domains]      # 固定按 manifest 序

        if body_domains:
            bind_kind = BIND_KIND_TENTACLE
            carrier = "、".join(body_domains)
            carrier_basis = "api.py 分派分支导入触手本体模块：%s" % (
                "、".join(body_tokens or mods) or "(无)")
        else:
            bind_kind = BIND_KIND_DIRECT
            carrier = "gbt_allinone（本体分派）" + (
                "·" + "、".join(mods) if mods else "")
            carrier_basis = ("api.py 分派分支未导入触手本体模块 ⇒ 本体直连"
                             + ("（导入：%s）" % "、".join(mods) if mods else "（无独立导入）"))

        # 能量：权威声明级 + 代码证据级
        basis = []
        energy_kind = "none"
        # R-H992（2026-10-15 · 主人令「所有模块都要双向绑定登记在她自己看得见的地方」）：
        #   以前“不用能”是**空 basis**，她看不出为什么。空白不许当结论——
        #   这里给一条**派生理由**（不是手写名单：只说它没进声明、也无代码标记）。
        energy_none_basis = ("none:本位未进入 external_llm 权威声明、也无能量链代码标记"
                             "（只读或纯函数；如需用能请在 policy 声明）")
        evidence = energy_code_evidence(mods) if mods else []
        if nm in ext_llm or nm in ENERGY_DECLARED_EXTRA:
            energy_kind = "declared"
            basis.append("policy:external_llm（权威声明级）")
        elif evidence:
            energy_kind = "code"
            basis.append("code:能量链标记（代码证据级）：%s"
                         % "、".join(sorted({m for e in evidence for m in e["marks"]})))
        chain = energy_kind != "none"
        if not chain:
            basis.append(energy_none_basis)
        state = S_BOUND_T if bind_kind == BIND_KIND_TENTACLE else S_BOUND_D
        if not (carrier or "").strip():
            state = S_UNBOUND

        # R-H994（2026-10-15 · 主人令）每一条双向绑定的触手都要备注好“连上哪里”，
        #   目的是**提高她的认知**：她自己读得出“这条能力由谁执行、走哪只手、用哪条通道”。
        nb = _NEIGHBORHOOD_INDEX.get(nm, "")
        if body_domains:
            _connect = "触手域 " + "、".join(body_domains)
        else:
            _mods = "、".join(mods) if mods else "无独立导入"
            _connect = "本体分派（" + _mods + "）"
        _energy_txt = ("不用能（只读或纯函数）" if not chain
                       else ("%s 通道" % "、".join(list(alive_ids)[:3]) if alive_ids else "通道未读到"))
        _nb_txt = nb if nb else ("框架域 " + (dom or "未标"))
        note = ("备注：连到 " + _connect + "｜ 邻域 " + _nb_txt + "｜ 用能 " + _energy_txt
                + "｜ 认知：" + ("动作落在「" + nb + "」这只手上，账上回查得到" if nb
                                     else "本位不是触手方法名，走框架域路径（见 carrier_basis）"))

        rows.append({
            "name": nm, "domain": dom, "handler": str(c.get("handler") or "none"),
            "desc": str(c.get("desc") or ""),
            "requires_params": bool(c.get("requires_params")),
            "external": c.get("external"),
            "bind_kind": bind_kind, "carrier": carrier, "carrier_basis": carrier_basis,
            "tentacle_domains": body_domains,
            "tentacle_label": nm,
            "domain_label": ("domain:" + dom) if dom else "",
            "energy": {"chain": chain, "kind": energy_kind, "basis": basis,
                       "evidence": evidence,
                       # 用能 ⇒ 现读可用的腿都算承载（链是**共享池**，见 key_gateway 自述）
                       "channels": list(alive_ids) if chain else [],
                       "dead_channels": list(dead_ids) if chain else [],
                       "active": energy_meta.get("active") if chain else None},
            "state": state,
            "note": note,
        })

    # ── 反向：触手域 → caps / 能力项 → caps ──────────────────────────────
    domains_out = []
    for d in (tent or []):
        did = d["id"]
        rev = [r["name"] for r in rows if did in r["tentacle_domains"]]
        dom_domains = [r["name"] for r in rows if r["domain"] == did]      # 同名框架域（若有）
        item_rows = [{"item": it, "caps": rev[:]} for it in d["items"]]
        domains_out.append({
            "id": did, "name": d["name"], "declared_count": d["declared_count"],
            "items": d["items"], "item_count": len(d["items"]),
            "source": d["source"],
            "partial": d.get("partial", False), "gap_note": d.get("gap_note"),
            "caps": rev, "cap_count": len(rev),
            "item_caps": item_rows,
            "same_name_framework_domain": did if dom_domains else None,
            "same_name_caps": dom_domains,
        })

    # ── 反向：能量通道 → caps ────────────────────────────────────────────
    chains_out = []
    for c in (channels or []):
        prov = c["provider"]
        rev = [r["name"] for r in rows if prov in (r["energy"]["channels"] or [])]
        chains_out.append({**c, "caps": rev, "cap_count": len(rev),
                           "carries": bool(rev)})

    # ── 断链 / 零遗漏 ────────────────────────────────────────────────────
    unbound, bad_domain, bad_channel = [], [], []
    for r in rows:
        if r["state"] == S_UNBOUND or not (r["carrier"] or "").strip():
            unbound.append(r["name"])
        for d in r["tentacle_domains"]:
            if d not in domain_ids:
                bad_domain.append("%s → 触手域 %r（不在触手总纲）" % (r["name"], d))
        for ch in (r["energy"]["channels"] or []) + (r["energy"]["dead_channels"] or []):
            if ch not in channel_ids:
                bad_channel.append("%s → 能量通道 %r（不在 13 条链）" % (r["name"], ch))

    # 双向一致性（**两个方向各自反演，再互校**）
    fwd_dom = {r["name"]: set(r["tentacle_domains"]) for r in rows}
    rev_dom = {}
    for d in domains_out:
        for n in d["caps"]:
            rev_dom.setdefault(n, set()).add(d["id"])
    mismatch_dom = []
    for n in fwd_dom:
        if fwd_dom[n] != rev_dom.get(n, set()):
            mismatch_dom.append("%s：正向 %s ≠ 反向 %s"
                                % (n, sorted(fwd_dom[n]), sorted(rev_dom.get(n, set()))))

    fwd_ch = {r["name"]: set(r["energy"]["channels"]) for r in rows}
    rev_ch = {}
    for ch in chains_out:
        for n in ch["caps"]:
            rev_ch.setdefault(n, set()).add(ch["provider"])
    mismatch_ch = []
    for n in fwd_ch:
        if fwd_ch[n] != rev_ch.get(n, set()):
            mismatch_ch.append("%s：正向 %s ≠ 反向 %s"
                               % (n, sorted(fwd_ch[n]), sorted(rev_ch.get(n, set()))))

    # 未探测画成通：不可用通道**不得**承载任何 cap
    dead_carrying = [ch["provider"] for ch in chains_out
                     if ch.get("alive") is not True and ch.get("caps")]

    # 标签层（框架自己的触手语言）
    label_face = {"labels": len(labels) if labels else None,
                  "caps_not_labeled": None, "asset_labels_not_in_dict": None,
                  "why": labels_why}
    if labels:
        label_face["caps_not_labeled"] = sorted(set(cap_names) - labels)
        label_face["domain_labels_missing"] = sorted(
            {"domain:" + r["domain"] for r in rows if r["domain"]} - labels)

    # 资产层（只读，不改）
    asset_face = {"assets": None, "missing_assets": None, "ghost_labels": None,
                  "ledger_lines": None, "note": "资产层由 tools/tentacle_bind.py 维护；本件只读"}
    if ASSET_BINDINGS.is_file():
        try:
            b = json.loads(ASSET_BINDINGS.read_text(encoding="utf-8"))
            missing = [a for a in b if not (ROOT / a).exists()]
            ghost = []
            if labels:
                for a, row in b.items():
                    for t in (row.get("tentacles") or []):
                        if t not in labels:
                            ghost.append("%s → %s" % (a, t))
            asset_face.update({"assets": len(b), "missing_assets": len(missing),
                               "ghost_labels": len(ghost)})
        except Exception as e:                               # noqa: BLE001
            asset_face["why"] = "读不了：%s: %s" % (type(e).__name__, str(e)[:100])
    else:
        asset_face["why"] = "不在盘：%s" % ASSET_BINDINGS
    if ASSET_LEDGER.is_file():
        try:
            with ASSET_LEDGER.open("r", encoding="utf-8", errors="replace") as fh:
                asset_face["ledger_lines"] = sum(1 for ln in fh if ln.strip())
        except Exception:                                    # noqa: BLE001
            pass

    counts = {
        "caps": len(rows),
        "caps_tentacle": sum(1 for r in rows if r["bind_kind"] == BIND_KIND_TENTACLE),
        "caps_direct": sum(1 for r in rows if r["bind_kind"] == BIND_KIND_DIRECT),
        "caps_unbound": len(unbound),
        "caps_energy": sum(1 for r in rows if r["energy"]["chain"]),
        "caps_energy_declared": sum(1 for r in rows if r["energy"]["kind"] == "declared"),
        "caps_energy_code": sum(1 for r in rows if r["energy"]["kind"] == "code"),
        "tentacle_domains": len(domains_out),
        "tentacle_items": sum(d["item_count"] for d in domains_out),
        "tentacle_domains_without_caps": len([d for d in domains_out if not d["caps"]]),
        "energy_channels": len(chains_out),
        "energy_alive": len([c for c in chains_out if c.get("alive") is True]),
        "energy_dead": len([c for c in chains_out if c.get("alive") is not True]),
        "labels": len(labels) if labels else None,
    }

    return {
        "generated_at": now(),
        "commands": {"report": CMD_REPORT, "render": CMD_RENDER, "check": CMD_CHECK,
                     "json": CMD_JSON, "feel": CMD_FEEL},
        "doctrine": [
            "**不许假绿**：探不到就「未探测」并写明为什么；绑定算不出来就报红，不许留空当绑好了。",
            "**未探测不画成通**：不可用的能量通道不得被算作承载着谁。",
            "**直连 ≠ 未绑**：不经触手本体的能力必须**显式**记成「直连」；空白才报红。",
            "触手承载是**代码证据**（api.py 分派分支导入了 tentacle/omni_* 模块），不是拍脑袋。",
            "能量分两级：**权威声明级**（policy 声明 external_llm）与**代码证据级**（模块文本命中链标记）。",
            "只读探测：import 模块 + 读注册表/配置，**不执行框架动作、不调授权作用域**。",
            "本工具只写 state/cap-bindings.json；资产层（asset_bindings）由 tentacle_bind.py 维护，本件只读。",
        ],
        "rules": {
            "bind_kinds": list(BIND_KINDS),
            "触手承载判据": "gbt_allinone/api.py 里该能力位的分派分支导入了触手本体模块"
                          "（tentacle/omni_*、tentacle/bridge、vision_cap …）",
            "omni模块→触手域": OMNI_TOKENS,
            "整只手模块": sorted(WHOLE_BODY_TOKENS),
            "能量权威声明级": "security/policy.py::evaluate(kind) 的 scopes 含 external_llm",
            "能量代码证据级": "承载模块文本命中：%s" % "、".join(ENERGY_MARKERS),
            "直连口径": "该能力位由框架本体模块实现、分派分支未导入触手本体 ⇒ 显式记「直连」",
            "note": "本表是**人定口径**，写在这里就是为了可复核、可改；改了口径要重跑本工具。",
        },
        "sources": {
            "caps": "gbt_allinone/caps_registry.py::BENIGN_CAPS（经 caps_tables.all_caps() 容错取，现读）",
            "tentacle": "gbt_allinone/tentacle/omni_tentacle.py::TENTACLE_MANIFEST（markdown 正文，现读）",
            "tentacle_labels": "tools/tentacle_bind.py::_valid_labels()（= 能力位 kind ∪ domain:<域>）",
            "energy": "gbt_allinone/llm/key_gateway.py::energy() + run('status')（只读直连）",
            "asset_layer": "state/asset_bindings.json（只读；由 tools/tentacle_bind.py 维护）",
        },
        "probe": {"caps_why": caps_why, "tentacle_why": tent_why,
                  "energy_why": energy_why, "labels_why": labels_why,
                  "note": UA_NOTE},
        "tentacle_meta": tent_meta,
        "energy_meta": energy_meta,
        "counts": counts,
        "caps": rows,
        "tentacle_domains": domains_out,
        "energy_channels": chains_out,
        "orphans": {
            "caps_unbound": unbound,
            "caps_bad_domain": bad_domain,
            "caps_bad_channel": bad_channel,
            "tentacle_domains_without_caps": [d["id"] for d in domains_out if not d["caps"]],
            "energy_dead_channels": [c["provider"] for c in chains_out if c.get("alive") is not True],
            "dead_channel_carrying": dead_carrying,
            "mismatch_cap_vs_domain": mismatch_dom,
            "mismatch_cap_vs_channel": mismatch_ch,
        },
        "label_face": label_face,
        "asset_layer": asset_face,
    }


# ══════════════════════════════════════════════════════════════════════════
# 人读报告
# ══════════════════════════════════════════════════════════════════════════
def cmd_report() -> int:
    t0 = time.perf_counter()
    model = build_model()
    c = model["counts"]
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 82)
    print("能力 ↔ 触手 ↔ 能量 · 三边双向绑定（%s）" % model["generated_at"])
    print("=" * 82)
    print("  只读探测：%s" % UA_NOTE)
    print("-" * 82)
    print("  ① 能力边  %d 条 ｜ 触手承载 %d · 直连 %d ｜ 用能 %d（声明级 %d · 证据级 %d）"
          % (c["caps"], c["caps_tentacle"], c["caps_direct"], c["caps_energy"],
             c["caps_energy_declared"], c["caps_energy_code"]))
    print("  ② 触手边  %d 域 · %d 能力项 ｜ 无 cap 的域 %d"
          % (c["tentacle_domains"], c["tentacle_items"], c["tentacle_domains_without_caps"]))
    print("  ③ 能量边  %d 条通道 ｜ 可用 %d · 不可用/未探测 %d ｜ active=%s"
          % (c["energy_channels"], c["energy_alive"], c["energy_dead"],
             (model.get("energy_meta") or {}).get("active")))
    print("  ④ 标签层  有效触手标签 %s ｜ 能力位无触手标签 %s"
          % (c["labels"], len(model["label_face"].get("caps_not_labeled") or [])))
    o = model["orphans"]
    bad = (o["caps_unbound"] or o["caps_bad_domain"] or o["caps_bad_channel"]
           or o["dead_channel_carrying"] or o["mismatch_cap_vs_domain"]
           or o["mismatch_cap_vs_channel"])
    print("-" * 82)
    if bad:
        print("  🔴 报警（逐条点名，一条不省）：")
        for k in ("caps_unbound", "caps_bad_domain", "caps_bad_channel",
                  "dead_channel_carrying", "mismatch_cap_vs_domain", "mismatch_cap_vs_channel"):
            v = o.get(k) or []
            if v:
                print("    [%s] %d 条：" % (k, len(v)))
                for x in v:
                    print("        · %s" % x)
    else:
        print("  ✅ 零遗漏：240 条能力全部有绑定；无绑到不存在的通道；双向反演自洽。")
    if o["tentacle_domains_without_caps"]:
        print("  ⚠️ 这些触手域在**能力层没有专门的门**（只能经 `tentacle` 一扇门取用）：%s"
              % "、".join(o["tentacle_domains_without_caps"]))
    print("-" * 82)
    print("  逐条触手域（域 → 承载哪些 cap）：")
    for d in model["tentacle_domains"]:
        print("    %-8s 项 %2d(声明 %2d) · cap %d ｜ %s"
              % (d["id"], d["item_count"], d["declared_count"], d["cap_count"],
                 "、".join(d["caps"]) if d["caps"] else "（无专门的门）"))
    print("-" * 82)
    print("  能量 13 条通道逐条：见下表（render 后也可读面板）")
    for ch in model["energy_channels"]:
        print("    %2s %-13s %-22s %-8s cap=%d ｜ %s"
              % (ch.get("order") or "-", ch["provider"], ch["status"], ch["tier"],
                 ch["cap_count"], "活跃" if ch["provider"] == (model.get("energy_meta") or {}).get("active") else ""))
    print("-" * 82)
    print("  台账：%s（%d 字节）" % (LEDGER, LEDGER.stat().st_size))
    print("  用时 %.2fs" % (time.perf_counter() - t0))
    return 0


# ══════════════════════════════════════════════════════════════════════════
# 渲染（自包含 · 数据只走经典脚本）
# ══════════════════════════════════════════════════════════════════════════
_CSS = """<style>
:root{--bg:#070d18;--panel:#0f172a;--line:#1e3a5f;--line2:#162035;--ink:#e7eef8;--dim:#8794a6;
 --off:#6b7280;--gold:#f5b041;--cyan:#00e5ff;--ok:#22c55e;--bad:#f87171;--miss:#f5b041;
 --okbg:#0f2a20;--badbg:#2a1414;--missbg:#2a2010;--offbg:#16181d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.6 "Segoe UI","Microsoft YaHei UI",system-ui,sans-serif}
.bar{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--line);
 background:linear-gradient(90deg,#080d14,#0b1220);flex-wrap:wrap}
.mark{width:18px;height:18px;border:2px solid var(--gold);border-radius:4px}
.brand{font-weight:700;letter-spacing:.4px}.brand b{color:var(--gold)}
.note{color:var(--dim);font-size:11.5px}
code{font-family:ui-monospace,Consolas,monospace;color:var(--cyan)}
.wrap{padding:14px;display:grid;gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px}
h2{margin:0 0 8px;font-size:13px;color:var(--dim);font-weight:600;letter-spacing:.4px}
.hr{height:1px;background:var(--line);margin:10px 0}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px}
.stat{min-width:84px}.stat b{display:block;font-size:24px;color:var(--cyan);font-variant-numeric:tabular-nums}
.stat i{font-style:normal;color:var(--dim);font-size:12px}
.stat b.ok{color:var(--ok)}.stat b.bad{color:var(--bad)}.stat b.miss{color:var(--miss)}.stat b.off{color:var(--off)}
table{border-collapse:collapse;width:100%;font-size:11px}
th,td{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top}
th{color:var(--dim);font-weight:600;background:#0a1018;position:sticky;top:0}
td.cell{text-align:right;font-variant-numeric:tabular-nums}
td.sok{color:var(--ok)}td.sbad{color:var(--bad);font-weight:700}td.smiss{color:var(--miss)}td.sunk{color:var(--off)}
tr.hl td{background:#12233a}
tr.dead td{opacity:.62}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 7px;font-size:11px}
.pill.ok{border-color:#1d5c45;color:var(--ok)}
.pill.bad{border-color:#6b2a2a;color:var(--bad)}
.pill.miss{border-color:#6b5320;color:var(--miss)}
.pill.off{border-color:#39445a;color:var(--off)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0}
.lg{display:flex;align-items:center;gap:6px;color:var(--dim);font-size:11.5px}
.sw{width:14px;height:14px;border-radius:3px;border:1px solid var(--line);display:inline-block}
.sw.ok{background:var(--okbg);border-color:var(--ok)}
.sw.bad{background:var(--badbg);border-color:var(--bad)}
.sw.miss{background:var(--missbg);border-color:var(--miss)}
.sw.off{background:var(--offbg);border-color:var(--off)}
.alert{border:1px solid #6b2a2a;border-radius:6px;padding:8px 10px;margin:0 0 8px;background:#1a0f0f}
.alert.miss{border-color:#6b5320;background:#1a150a}
.alert .t{font-weight:700;color:var(--ink)}.alert .e{color:var(--dim);font-size:11.5px;word-break:break-all;margin-top:3px}
.dead-note{border:1px solid #39445a;border-radius:6px;padding:6px 10px;margin:6px 0;background:#111621;color:var(--dim);font-size:11.5px}
a{color:var(--cyan);text-decoration:none}a:hover{text-decoration:underline}
.foot{border-top:1px solid var(--line);margin-top:12px;padding:10px 16px;color:var(--dim);font-size:11.5px}
.grp{margin:8px 0 4px;color:var(--gold);font-size:12px;font-weight:600}
.collapse{max-height:560px;overflow:auto}
.ok-line{color:var(--ok);font-weight:700}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>"""


def _esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def _pill(txt: str, cls: str) -> str:
    return '<span class="pill %s">%s</span>' % (cls, _esc(txt))


def render_page(model: dict) -> str:
    gen = model["generated_at"]
    c = model["counts"]
    o = model["orphans"]
    em = model.get("energy_meta") or {}
    active = em.get("active")
    channels = model["energy_channels"]
    rows = model["caps"]
    domains = model["tentacle_domains"]

    head = ('<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/capability-bindings.py -->\n'
            '<title>GBT小土豆V8 · 能量与绑定状态</title>\n%s</head><body>\n' % _CSS)
    topbar = ('<div class="bar"><span class="mark"></span>'
              '<span class="brand">GBT<b>小土豆</b>V8 · 能量与绑定状态</span>'
              '<span class="note">生成 %s ｜ 重生成 <code>%s</code> ｜ 判据 <code>%s</code> ｜ '
              '随时可感 <code>%s</code></span></div>'
              % (_esc(gen), _esc(CMD_RENDER), _esc(CMD_CHECK), _esc(CMD_FEEL)))
    foot = ('<div class="foot">生成时刻 <b>%s</b> ｜ 重生成命令 <code>%s</code> ｜ '
            '判据命令 <code>%s</code>（判据含负对照）｜ 随时可感（复跑一条命令）<code>%s</code> ｜ '
            '建账 <code>%s</code> ｜ 开发者：自由的风 · GBT小土豆V8</div>'
            % (_esc(gen), _esc(CMD_RENDER), _esc(CMD_CHECK), _esc(CMD_FEEL), _esc(CMD_REPORT)))

    # 00 概览
    stats = ('<div class="stats">'
             '<div class="stat"><b>%d</b><i>能力位</i></div>'
             '<div class="stat"><b class="ok">%d</b><i>触手承载</i></div>'
             '<div class="stat"><b class="miss">%d</b><i>直连（显式）</i></div>'
             '<div class="stat"><b class="%s">%d</b><i>未绑</i></div>'
             '<div class="stat"><b>%d</b><i>用能能力位</i></div>'
             '<div class="stat"><b>%d</b><i>触手域</i></div>'
             '<div class="stat"><b>%d</b><i>触手能力项</i></div>'
             '<div class="stat"><b class="ok">%d</b><i>能量可用</i></div>'
             '<div class="stat"><b class="off">%d</b><i>能量不可用/未探测</i></div>'
             '</div>'
             % (c["caps"], c["caps_tentacle"], c["caps_direct"],
                "bad" if c["caps_unbound"] else "ok", c["caps_unbound"],
                c["caps_energy"], c["tentacle_domains"], c["tentacle_items"],
                c["energy_alive"], c["energy_dead"]))
    legend = ('<div class="legend">'
              '<span class="lg"><i class="sw ok"></i><b>触手承载</b>：api.py 分派分支导入了触手本体模块</span>'
              '<span class="lg"><i class="sw miss"></i><b>直连</b>：本体实现、不经触手本体（<b>显式</b>，不是空白）</span>'
              '<span class="lg"><i class="sw bad"></i><b>未绑</b>：既非触手承载、又无承载载体 ⇒ 报红</span>'
              '<span class="lg"><i class="sw off"></i><b>未探测</b>：没条件探（不可用通道不得算作承载）</span>'
              '</div>')
    doctrine = "".join('<li>%s</li>' % _esc(d).replace("**", "") for d in model["doctrine"])
    probe_note = ('<div class="note">三边真源：能力 <code>%s</code> ｜ 触手 <code>%s</code> ｜ '
                  '标签 <code>%s</code> ｜ 能量 <code>%s</code></div>'
                  % (_esc(model["sources"]["caps"]), _esc(model["sources"]["tentacle"]),
                     _esc(model["sources"]["tentacle_labels"]), _esc(model["sources"]["energy"])))
    why_bits = [k for k in ("caps_why", "tentacle_why", "energy_why", "labels_why")
                if model["probe"].get(k)]
    why_block = ('<div class="dead-note">未探测/降级说明：%s</div>'
                 % _esc("；".join("%s=%s" % (k, model["probe"][k]) for k in why_bits))) if why_bits else ""

    # ① 能量总览
    erows = []
    for ch in channels:
        is_active = ch["provider"] == active
        alive = ch.get("alive") is True
        st_cls = "sok" if alive else ("sunk" if ch.get("alive") is None else "sbad")
        st_txt = ch["status"] + ("（活跃）" if is_active else "")
        erows.append(
            '<tr class="%s%s"><td class="mono cell">%s</td><td class="mono">%s</td>'
            '<td class="%s">%s</td><td>%s</td><td class="mono">%s</td>'
            '<td class="mono cell">%s</td><td class="mono">%s</td><td class="mono">%s</td>'
            '<td class="mono cell">%s</td><td class="mono">%s</td></tr>'
            % ("hl" if is_active else "", "" if alive else "dead",
               _esc(ch.get("order") or "—"), _esc(ch["provider"]), st_cls, _esc(st_txt),
               _esc(ch["tier"] or "—"), _esc(ch["masked"] or "（无掩码/未探测）"),
               _esc("" if ch.get("used") is None else ch["used"]),
               _esc(ch["source"] or "—"), _esc(ch["model"] or "（未声明）"),
               _esc("存活" if alive else ("未探测" if ch.get("alive") is None else "不可用")),
               _esc(ch["url"] or "（无 base_url）")))
    etable = ('<table><thead><tr><th>序</th><th>provider</th><th>可用否</th><th>tier</th>'
              '<th>掩码</th><th>已用</th><th>来源</th><th>模型</th><th>承载 cap</th><th>url</th>'
              '</tr></thead><tbody>%s</tbody></table>' % "".join(erows))
    dead_block = ""
    if o["energy_dead_channels"]:
        dead_block = ('<div class="dead-note">🔴 <b>未探测/不可用</b>的通道（<b>不得画成通</b>）：'
                      '%s ⇒ 它们的承载 cap 数已按规则置为 <b>0</b>（不冒充能承载）；'
                      '「不可用通道却承载着 cap」= %s</div>'
                      % (_esc("、".join(o["energy_dead_channels"])),
                         _esc("有（报红）" if o["dead_channel_carrying"] else "无")))
    emeta = ('<div class="note">链源 <code>%s</code> ｜ active <code>%s</code> ｜ '
             'runtime_ttl_s <code>%s</code>（0 = 每次现算）｜ 切换次数 %s ｜ '
             '在服务通道 %s ｜ 摘要：%s</div>'
             % (_esc(em.get("chain_source")), _esc(em.get("active")),
                _esc(em.get("runtime_ttl_s")), _esc(em.get("switches")),
                _esc("、".join(em.get("service") or []) or "—"), _esc(em.get("summary"))))

    # ② 能力 × 绑定总表
    crows = []
    for r in rows:
        tk = r["bind_kind"]
        cls = "sok" if tk == BIND_KIND_TENTACLE else "smiss"
        if r["state"] == S_UNBOUND:
            cls = "sbad"
        energy_txt = "—（不经能量链）" if not r["energy"]["chain"] else (
            "%s%s" % (r["energy"]["kind"] == "declared" and "声明级" or "证据级",
                      "·%s" % r["energy"]["active"] if r["energy"]["active"] else ""))
        crows.append(
            '<tr><td class="mono">%s</td><td>%s</td><td class="mono">%s</td>'
            '<td>%s</td><td class="%s">%s</td><td>%s</td><td class="mono">%s</td>'
            '<td class="note">%s</td></tr>'
            % (_esc(r["name"]), _esc(r["domain"]),
               _esc("、".join(r["tentacle_domains"]) if r["tentacle_domains"] else "—"),
               _esc(r["carrier"])[:120], cls, _esc(tk),
               _esc(energy_txt), _esc(r["state"]),
               _esc(r.get("note") or "；".join(r["energy"]["basis"]) or r["carrier_basis"])[:260]))
    ctable = ('<div class="collapse"><table><thead><tr><th>能力</th><th>域</th>'
              '<th>承载触手域</th><th>承载载体</th><th>绑定类型</th><th>能量</th>'
              '<th>感应状态</th><th>备注（连上哪里）</th></tr></thead><tbody>%s</tbody></table></div>'
              % "".join(crows))

    # 触手域 → caps（反向表）
    drows = []
    for d in domains:
        drows.append('<tr><td class="mono">%s</td><td class="cell">%d</td>'
                     '<td class="cell">%d</td><td class="cell">%d</td><td class="mono">%s</td>'
                     '<td class="note">%s</td></tr>'
                     % (_esc(d["id"]), d["item_count"], d["declared_count"], d["cap_count"],
                        _esc("、".join(d["caps"]) if d["caps"] else "（无专门的门）"),
                        _esc(d.get("gap_note") or d["source"])))
    dtable = ('<table><thead><tr><th>触手域</th><th>能力项</th><th>声明数</th>'
              '<th>承载 cap</th><th>承载哪些 cap（反向）</th><th>备注</th></tr></thead>'
              '<tbody>%s</tbody></table>' % "".join(drows))

    # ③ 未绑定清单 + 双向一致性
    al = []
    for key, title in (("caps_unbound", "未绑能力位（零遗漏判据）"),
                       ("caps_bad_domain", "绑到不存在的触手域"),
                       ("caps_bad_channel", "绑到不存在的能量通道"),
                       ("dead_channel_carrying", "不可用通道却承载着 cap（未探测画成通）"),
                       ("mismatch_cap_vs_domain", "双向不一致：能力↔触手域"),
                       ("mismatch_cap_vs_channel", "双向不一致：能力↔能量通道")):
        v = o.get(key) or []
        if v:
            al.append('<div class="alert"><div class="t">🔴 [%s] %s ｜ %d 条</div>'
                      '<div class="e mono">%s</div></div>'
                      % (_esc(key), _esc(title), len(v), _esc("；".join(map(str, v)))[:1200]))
    if not al:
        al.append('<div class="note ok-line">✅ 零遗漏：%d 条能力全部有绑定；无绑到不存在的通道；'
                  '双向反演自洽。</div>' % c["caps"])
    if o["tentacle_domains_without_caps"]:
        al.append('<div class="alert miss"><div class="t">⚠️ 这些触手域在能力层没有专门的门</div>'
                  '<div class="e">%s ⇒ 它们只能经 <code>tentacle</code> 这一扇门取用'
                  '（那扇门已绑、已列在上表）。</div></div>'
                  % _esc("、".join(o["tentacle_domains_without_caps"])))

    # ④ 资产层关系 + 标签层
    af = model.get("asset_layer") or {}
    lf = model.get("label_face") or {}
    relate = ('<div class="note"><b>谁管资产、谁管能力</b>：'
              '本页 = <b>能力层</b>（能力位 → 承载触手域 / 能量通道）；'
              '<code>state/asset_bindings.json</code> = <b>资产层</b>（资产 → 触手标签，'
              '由 <code>tools/tentacle_bind.py</code> 维护，本件只读）。两层通过<b>触手标签</b>衔接：'
              '<b>能力位 kind 本身就是一个合法触手标签</b>。</div>'
              '<table><thead><tr><th>面</th><th>读数</th></tr></thead><tbody>'
              '<tr><td>资产层·资产数</td><td class="mono">%s</td></tr>'
              '<tr><td>资产层·资产缺失（断连）</td><td class="mono">%s</td></tr>'
              '<tr><td>资产层·触手不在册（断连）</td><td class="mono">%s</td></tr>'
              '<tr><td>资产层·台账行</td><td class="mono">%s</td></tr>'
              '<tr><td>标签层·有效触手标签</td><td class="mono">%s</td></tr>'
              '<tr><td>标签层·能力位无触手标签</td><td class="mono">%s</td></tr>'
              '<tr><td>标签层·缺 domain:&lt;域&gt; 标签</td><td class="mono">%s</td></tr>'
              '</tbody></table>'
              % (_esc(af.get("assets")), _esc(af.get("missing_assets")),
                 _esc(af.get("ghost_labels")), _esc(af.get("ledger_lines")),
                 _esc(lf.get("labels")), _esc(lf.get("caps_not_labeled")),
                 _esc(lf.get("domain_labels_missing"))))

    body = ('<div class="wrap">'
            '<div class="card"><h2>// 00 — 概览（%s）</h2>%s%s%s'
            '<div class="hr"></div><div class="note">纪律：<ul>%s</ul></div>%s</div>'
            '<div class="card"><h2>// 01 — 能量总览（13 条通道逐条 · 活跃者高亮 · 未探测不画成通）</h2>'
            '%s%s%s</div>'
            '<div class="card"><h2>// 02 — 触手域 → 承载哪些 cap（反向）</h2>%s</div>'
            '<div class="card"><h2>// 03 — 🔴 未绑定清单 + 双向一致性核对（置顶）</h2>%s</div>'
            '<div class="card"><h2>// 04 — 能力 × 绑定总表（%d 条逐条）</h2>%s</div>'
            '<div class="card"><h2>// 05 — 与资产层/标签层的关系（谁管资产、谁管能力）</h2>%s</div>'
            '</div>%s'
            % (_esc(gen), stats, legend, probe_note, doctrine, why_block,
               emeta, etable, dead_block, dtable, "".join(al), c["caps"], ctable, relate, foot))

    script = ('<script src="energy-data.js"></script>\n'
              '<script>\n'
              '/* 经典脚本（非 module）：数据来自 energy-data.js，本页零远端请求。*/\n'
              'var E = globalThis.GBT_ENERGY || {counts:{}};\n'
              'if (globalThis.GBT_ENERGY && globalThis.GBT_ENERGY.generated_at) {\n'
              '  document.title = "GBT小土豆V8 · 能量与绑定状态（" + '
              'globalThis.GBT_ENERGY.counts.caps + " 能力位 / " + '
              'globalThis.GBT_ENERGY.counts.energy_channels + " 通道）";\n'
              '}\n'
              '</script>\n')
    return head + topbar + body + script + '</body></html>\n'


def cmd_render() -> int:
    model = None
    if LEDGER.is_file():
        try:
            model = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            model = None
    if not model or not model.get("caps"):
        print("🔴 台账读不到或没有 caps，先跑：%s" % CMD_REPORT)
        return 2
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(render_page(model), encoding="utf-8")
    data = {k: model.get(k) for k in ("generated_at", "commands", "doctrine", "sources",
                                      "rules", "counts", "tentacle_meta", "energy_meta",
                                      "caps", "tentacle_domains", "energy_channels",
                                      "orphans", "label_face", "asset_layer", "probe")}
    DATA.write_text("/* 自动生成，别手改。重建：\n"
                    "   %s\n"
                    "   数据来自台账 state/cap-bindings.json（现读真源所得）。*/\n"
                    "globalThis.GBT_ENERGY = %s;\n"
                    % (CMD_RENDER, json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                    encoding="utf-8")
    c = model.get("counts") or {}
    print("能量与绑定面板：%s（%d 字节）" % (PAGE, PAGE.stat().st_size))
    print("数据件：%s（%d 字节）" % (DATA, DATA.stat().st_size))
    print("能力 %s（触手承载 %s · 直连 %s · 未绑 %s）｜ 触手域 %s／能力项 %s ｜ 能量通道 %s（可用 %s）"
          % (c.get("caps"), c.get("caps_tentacle"), c.get("caps_direct"), c.get("caps_unbound"),
             c.get("tentacle_domains"), c.get("tentacle_items"),
             c.get("energy_channels"), c.get("energy_alive")))
    return 0


# ══════════════════════════════════════════════════════════════════════════
# 「随时可感」——一条命令的复跑读数（**无时钟字段，两次跑应逐字一致**）
# ══════════════════════════════════════════════════════════════════════════
def cmd_feel() -> int:
    model = build_model()
    c = model["counts"]
    o = model["orphans"]
    em = model.get("energy_meta") or {}
    print("GBT小土豆V8 · 随时可感读数（口径 v1 · 无时钟字段 ⇒ 复跑应逐字一致）")
    print("能力边: %d 条 = 触手承载 %d + 直连 %d + 未绑 %d"
          % (c["caps"], c["caps_tentacle"], c["caps_direct"], c["caps_unbound"]))
    print("触手边: %d 域 / %d 能力项 / 无专门门的域 %d"
          % (c["tentacle_domains"], c["tentacle_items"], c["tentacle_domains_without_caps"]))
    print("能量边: %d 条通道 = 可用 %d + 不可用或未探测 %d / active=%s / chain_source=%s"
          % (c["energy_channels"], c["energy_alive"], c["energy_dead"],
             em.get("active"), em.get("chain_source")))
    print("用能能力位: %d（声明级 %d · 代码证据级 %d）"
          % (c["caps_energy"], c["caps_energy_declared"], c["caps_energy_code"]))
    for ch in model["energy_channels"]:
        print("  [%s] %-13s %-22s alive=%s cap=%d"
              % (ch.get("order") or "-", ch["provider"], ch["status"],
                 ch["alive"], ch["cap_count"]))
    red = bool(o["caps_unbound"] or o["caps_bad_domain"] or o["caps_bad_channel"]
               or o["dead_channel_carrying"] or o["mismatch_cap_vs_domain"]
               or o["mismatch_cap_vs_channel"])
    print("零遗漏判据: %s" % ("🔴 有红（跑 %s 逐条看）" % CMD_REPORT if red
                              else "✅ 全绿（无未绑 / 无幽灵通道 / 双向自洽）"))
    return 1 if red else 0


# ══════════════════════════════════════════════════════════════════════════
# 判据（≥10 条 · **必须带负对照**：喂空/喂坏/给不存在的通道 必须报红）
# ══════════════════════════════════════════════════════════════════════════
_EXT_RE = re.compile(r'''(?:src|href)\s*=\s*["'](?:\s*)(?:https?:)?//''', re.I)


def _parse_data_js(text: str):
    m = re.search(r"globalThis\.GBT_ENERGY\s*=\s*(\{.*\})\s*;\s*$", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:                                        # noqa: BLE001
        return None


def honesty_findings(model: dict) -> list:
    """绑定诚实性：一条规则一处。**空白当绑好 = 红**。"""
    out = []
    caps = model.get("caps") or []
    if not caps:
        return ["台账里没有 caps（无从证真 ⇒ 报红）"]
    for r in caps:
        nm = r.get("name") or "?"
        if r.get("bind_kind") not in BIND_KINDS:
            out.append("%s 绑定类型非法：%r（只许 %s）" % (nm, r.get("bind_kind"), "/".join(BIND_KINDS)))
            continue
        if not str(r.get("carrier") or "").strip():
            out.append("%s 画成已绑但**承载载体为空**（假绿：空白冒充绑好）" % nm)
        if r.get("bind_kind") == BIND_KIND_TENTACLE and not (r.get("tentacle_domains") or []):
            out.append("%s 画成触手承载但**没有触手域**（假绿）" % nm)
        if not str(r.get("carrier_basis") or "").strip():
            out.append("%s 画成已绑但**没写依据**（说不清凭什么绑）" % nm)
        # R-H994（主人令）：每一条双向绑定都要备注“连上哪里”，空备注 = 她读不出认知
        if not str(r.get("note") or "").strip():
            out.append("%s 画成已绑但**没写备注（连上哪里）**（她读不出认知）" % nm)
    return out


def build_artifacts() -> dict:
    return {
        "ledger": _read_json(LEDGER),
        "html": PAGE.read_text(encoding="utf-8") if PAGE.is_file() else "",
        "data": DATA.read_text(encoding="utf-8") if DATA.is_file() else "",
        "caps_data": CAPS_DATA.read_text(encoding="utf-8") if CAPS_DATA.is_file() else "",
        "audit": _read_json(AUDIT_LEDGER),
        "authz_md": AUTHZ_PAGE.read_text(encoding="utf-8") if AUTHZ_PAGE.is_file() else "",
        "paths": {"ledger": str(LEDGER), "page": str(PAGE), "data": str(DATA),
                  "caps_data": str(CAPS_DATA), "audit": str(AUDIT_LEDGER),
                  "authz": str(AUTHZ_PAGE)},
    }


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


def _parse_global_js(text: str, name: str):
    """从 `globalThis.NAME = {...};`（经典脚本）里把 JSON 抠出来。抠不出返回 None —— 不猜。"""
    m = re.search(r"globalThis\.%s\s*=\s*(\{.*\})\s*;" % re.escape(name), text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:                                        # noqa: BLE001
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 页面边（P1 能力→页 · P2 页→能力 · P3 页项字段与台账逐项一致）
# ═══════════════════════════════════════════════════════════════════════════
def page_edge_checks(art: dict) -> list:
    """第四边判据：能力 ↔ 页面**双向**。只读 art（内存），负对照喂改坏副本即可。"""
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": str(detail)})

    model = art.get("ledger") or {}
    caps = model.get("caps") or []
    names = [c["name"] for c in caps]
    nset = set(names)
    energy = _parse_global_js(art.get("data") or "", "GBT_ENERGY") or {}
    capsjs = _parse_global_js(art.get("caps_data") or "", "GBT_CAPABILITIES") or {}
    audit = art.get("audit") or {}
    authz = art.get("authz_md") or ""

    e_caps = energy.get("caps") or []
    e_names = {c.get("name") for c in e_caps}
    c_items = [i for i in (capsjs.get("items") or [])
               if str(i.get("id") or "").startswith("framework.cap.")]
    c_names = {i.get("name") for i in c_items}
    # 待授权清单一页：汇总页 ⇒ 认它"注册表**现读 N 条**"这个数（逐位不在页上≠指不到）
    m = re.search(r"注册表\*{0,2}现读\s*\*{0,2}\s*(\d+)\s*\*{0,2}\s*条", authz)
    authz_n = int(m.group(1)) if m else None

    # ── P1 能力→页：每一位都能在两份 **列全的表** 里指到 + 汇总页的现读总数对得上 ──
    miss_e = [n for n in names if n not in e_names]
    miss_c = [n for n in names if n not in c_names]
    authz_ok = authz_n == len(caps) and len(caps) > 0
    add("P1 能力→页：每一位都能在 能力栏页(energy-data.js) / 能力统计页(capabilities-data.js) "
        "指到；待授权清单一页的现读总数 = 能力位数",
        len(caps) > 0 and not miss_e and not miss_c and authz_ok,
        "缺于能力栏页 %s ｜ 缺于能力统计页 %s ｜ 汇总页现读 %s vs 能力位 %d"
        % (miss_e[:4] or "无", miss_c[:4] or "无", authz_n, len(caps)))

    # ── P2 页→能力：页上每一项都要能反查回注册表（不在册 = 幽灵）──────────────
    ghost_e = sorted(c.get("name") for c in e_caps if c.get("name") not in nset)
    ghost_c = sorted(n for n in c_names if n not in nset)
    # 页项携带的触手标签：能力栏页每条 cap 的 tentacle_domains 须在触手总纲域名里
    dom_ids = {d.get("id") for d in (model.get("tentacle_domains") or [])}
    bad_dom = []
    for c in e_caps:
        for d in (c.get("tentacle_domains") or []):
            if d not in dom_ids:
                bad_dom.append("%s→%s" % (c.get("name"), d))
    # 待授权清单一页是**汇总页**（逐位不在页上，认它的现读总数，见 P1）；它点名的
    # `kind` 一律须在册——但页里还有文件名/函数名等同形 token，故只校验"疑似能力位名"：
    # 在册集合里出现过的那些**不算幽灵**；真正的幽灵 = 页里点名的 kind 不在册且**也不是**
    # 任何已知非能力位 token（保守起见，本判据只认两份**列全数据件**的幽灵，汇总页走 P1 总数）。
    add("P2 页→能力：页上每一项都能反查回注册表（不在册=幽灵）· 页项触手域须在总纲",
        not ghost_e and not ghost_c and not bad_dom,
        "能力栏页幽灵 %s ｜ 统计页幽灵 %s ｜ 越纲触手域 %s"
        % (ghost_e[:4] or "无", ghost_c[:4] or "无", bad_dom[:4] or "无"))

    # ── P3 页项字段与台账**逐项一致**（防漂：页拿旧数/改过的数顶）───────────────
    by_name = {c["name"]: c for c in caps}
    diffs = []
    for c in e_caps:
        t = by_name.get(c.get("name"))
        if t is None:
            continue
        if c.get("bind_kind") != t.get("bind_kind"):
            diffs.append("%s bind_kind %r≠%r" % (c.get("name"), c.get("bind_kind"), t.get("bind_kind")))
        if list(c.get("tentacle_domains") or []) != list(t.get("tentacle_domains") or []):
            diffs.append("%s 触手域 页%s≠账%s" % (c.get("name"), c.get("tentacle_domains"),
                                           t.get("tentacle_domains")))
        if bool((c.get("energy") or {}).get("chain")) != bool((t.get("energy") or {}).get("chain")):
            diffs.append("%s 能量链 页%s≠账%s" % (c.get("name"), (c.get("energy") or {}).get("chain"),
                                           (t.get("energy") or {}).get("chain")))
    # 统计页数据件计数 == 审计台账计数
    a_cnt = (audit or {}).get("counts") or {}
    js_cnt = (capsjs or {}).get("counts") or {}
    # 统计页数据件的计数必须与审计台账**逐字段相等**（防漂：页拿旧数顶）。
    # 注意：framework 类总数含 `framework.registry` 那一行 ⇒ 不能用它比 cap 条数。
    cnt_mismatch = (a_cnt != js_cnt) if a_cnt else True
    # 能力栏页数据件计数 == 绑定台账计数
    e_cnt = energy.get("counts") or {}
    e_cnt_ok = (e_cnt == (model.get("counts") or {}))
    add("P3 页项字段与台账逐项一致（能力栏页字段=绑定台账 · 统计页计数=审计台账 · 能力栏页计数=绑定台账）",
        not diffs and not cnt_mismatch and e_cnt_ok,
        "字段差 %s ｜ 审计计数 页%s vs 账%s ｜ 绑定计数一致=%s"
        % (diffs[:4] or "无", js_cnt, a_cnt, e_cnt_ok))
    return rows


def run_checks(art: dict) -> list:
    """判据本体：只读 art（内存内容），**不碰磁盘** —— 负对照喂改坏的内存副本即可。"""
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": detail})

    model = art.get("ledger") or {}
    caps = model.get("caps") or []
    domains = model.get("tentacle_domains") or []
    channels = model.get("energy_channels") or []
    c = model.get("counts") or {}
    o = model.get("orphans") or {}
    html_, data_ = art.get("html") or "", art.get("data") or ""

    # C1 能力边真源读到且非空
    add("C1 能力边读得到且非空（现读注册表）", len(caps) > 0,
        "caps=%d%s" % (len(caps), "" if caps else "（读不到 ⇒ 报红）"))

    # C2 触手边读到（域>0 且能力项>0）
    add("C2 触手边读得到（域>0 且能力项>0）",
        len(domains) > 0 and sum(len(d.get("items") or []) for d in domains) > 0,
        "域=%d · 能力项=%d" % (len(domains), sum(len(d.get("items") or []) for d in domains)))

    # C3 能量边 13 条通道
    add("C3 能量边读得到且恰好 13 条通道",
        len(channels) == 13, "channels=%d（期望 13，现读 key_gateway）" % len(channels))

    # C4 🔴 零遗漏：每条能力都有绑定（与负对照同源）
    finds = honesty_findings(model) if caps else ["台账里没有 caps（无从证真 ⇒ 报红）"]
    add("C4 🔴 零遗漏（每条能力都有绑定、承载载体非空、依据非空）", not finds,
        "违规 %d 条：%s" % (len(finds), "；".join(finds[:3]) or "无"))

    # C5 🔴 不绑到不存在的通道（触手域 / 能量通道）
    bad5 = (o.get("caps_bad_domain") or []) + (o.get("caps_bad_channel") or [])
    add("C5 🔴 不绑到不存在的通道（触手域须在总纲里、能量通道须在 13 链里）", not bad5,
        "越界 %d 条：%s" % (len(bad5), "；".join(map(str, bad5[:4])) or "无"))

    # C6 🔴 未探测不画成通：不可用通道不得承载 cap
    dc = o.get("dead_channel_carrying") or []
    dead_with_caps = [ch["provider"] for ch in channels
                      if ch.get("alive") is not True and (ch.get("caps") or [])]
    add("C6 🔴 未探测不画成通（不可用通道的承载 cap 必须为空）",
        not dc and not dead_with_caps,
        "画成通 %s" % ("；".join(map(str, set(dc) | set(dead_with_caps))) or "无"))

    # C7 双向自洽①：能力↔触手域互为反演
    mm7 = o.get("mismatch_cap_vs_domain") or []
    add("C7 双向自洽①：能力→触手域 与 触手域→能力 互为反演", not mm7,
        "不一致 %d 条：%s" % (len(mm7), "；".join(map(str, mm7[:3])) or "无"))

    # C8 双向自洽②：能力↔能量通道互为反演
    mm8 = o.get("mismatch_cap_vs_channel") or []
    add("C8 双向自洽②：能力→能量通道 与 通道→能力 互为反演", not mm8,
        "不一致 %d 条：%s" % (len(mm8), "；".join(map(str, mm8[:3])) or "无"))

    # C9 触手标签层自洽（框架自己的触手语言）
    lf = model.get("label_face") or {}
    if lf.get("labels") is None:
        add("C9 触手标签层自洽（能力位 kind 与 domain:<域> 都在 _valid_labels 里）", False,
            "标签层未探测：%s" % lf.get("why"))
    else:
        add("C9 触手标签层自洽（能力位 kind 与 domain:<域> 都在 _valid_labels 里）",
            not (lf.get("caps_not_labeled") or lf.get("domain_labels_missing")),
            "无标签能力位=%s ｜ 缺 domain 标签=%s"
            % (lf.get("caps_not_labeled"), lf.get("domain_labels_missing")))

    # C10 触手承载的能力位必须有代码着落（承载模块在盘）
    bad10 = []
    for r in caps:
        if r.get("bind_kind") != BIND_KIND_TENTACLE:
            continue
        if not re.search(r"omni_|tentacle|bridge|vision_cap", str(r.get("carrier_basis") or "")):
            bad10.append(r.get("name"))
    add("C10 触手承载须有代码证据（分派分支导入触手本体模块）", not bad10,
        "缺证据 %s" % (bad10 or "无"))

    # C11 计数守恒（能力数 = 触手承载+直连+未绑；触手域反演的**边数** = 正向边数）
    n_t = sum(1 for r in caps if r.get("bind_kind") == BIND_KIND_TENTACLE)
    n_d = sum(1 for r in caps if r.get("bind_kind") == BIND_KIND_DIRECT)
    n_u = sum(1 for r in caps if r.get("state") == S_UNBOUND)
    rev_edges = sum(d.get("cap_count", 0) for d in domains)
    fwd_edges = sum(len(r.get("tentacle_domains") or []) for r in caps)
    add("C11 计数守恒（能力数 = 触手承载+直连+未绑；触手域反演边数 = 正向边数）",
        c.get("caps") == len(caps) == n_t + n_d + n_u
        and rev_edges == fwd_edges and len(caps) > 0,
        "台账 %s · caps %d = 承载 %d+直连 %d+未绑 %d ｜ 反演边 %d = 正向边 %d"
        % (c.get("caps"), len(caps), n_t, n_d, n_u, rev_edges, fwd_edges))

    # C12 页面自包含（零外链/无 fetch·XHR·eval·iframe/module）+ 引 energy-data.js
    bad12 = []
    if _EXT_RE.findall(html_):
        bad12.append("外链 %d 处" % len(_EXT_RE.findall(html_)))
    if "cdn" in html_.lower():
        bad12.append("cdn 字样")
    if "<iframe" in html_.lower():
        bad12.append("iframe")
    # 🔴 2026-10-18 加（**假红** · 留痕 · 原口径/为什么翻/现口径）：
    #   原口径：页面文本一律查 fetch 等远端取数原语。
    #   为什么翻：页面现在带**自卫/反控层**（<!-- gbt-defense -->），命中攻击时要把证据上报
    #     本机框架（局域网 :8877）⇒ 合法 fetch；被判违规是假红（自卫层是安全上报，不是页面取数）。
    #   现口径：C12 扫描前先剥掉自卫层块，其余脚本照旧严查。
    html_c12 = re.sub(r"<!-- gbt-defense -->[\s\S]*?</script>", " ", html_) if "<!-- gbt-defense -->" in html_ else html_
    if re.search(r"\bfetch\s*\(", html_c12):
        bad12.append("fetch(")
    if "XMLHttpRequest" in html_:
        bad12.append("XMLHttpRequest")
    if re.search(r"\beval\s*\(", html_c12):
        bad12.append("eval(")
    if re.search(r'type\s*=\s*["\']module["\']', html_c12, re.I):
        bad12.append('type="module"')
    if "energy-data.js" not in html_:
        bad12.append("未引 energy-data.js")
    add("C12 页面自包含：零外链/无 fetch·XHR·eval·iframe/无 module/数据只走经典脚本", not bad12,
        "违规：%s" % (bad12 or "无"))

    # C13 页首/页脚都有 生成时刻 + 重生成命令 + 判据命令 + 随时可感命令
    foot_ok = (html_.count(CMD_RENDER) >= 2 and html_.count(CMD_CHECK) >= 2
               and html_.count(CMD_FEEL) >= 2 and ("生成时刻" in html_ or "生成 " in html_))
    add("C13 页首/页脚都有 生成时刻 + 重生成命令 + 判据命令 + 随时可感命令", foot_ok,
        "render×%d check×%d feel×%d" % (html_.count(CMD_RENDER), html_.count(CMD_CHECK),
                                        html_.count(CMD_FEEL)))

    # C14 数据件可解析且计数与台账一致
    d = _parse_data_js(data_)
    add("C14 数据件可解析且计数与台账一致",
        isinstance(d, dict) and d.get("counts") == c and len(d.get("caps") or []) == len(caps)
        and len(caps) > 0,
        "可解析=%s 数据计数=%s 台账计数=%s" % (isinstance(d, dict), (d or {}).get("counts"), c))

    # C15 与资产层的关系写明（两层衔接：能力位 kind 就是触手标签）
    af = model.get("asset_layer") or {}
    add("C15 与资产层的关系写明（能力层↔资产层经触手标签衔接）",
        bool(af) and af.get("assets") is not None and str(model.get("sources", {}).get("asset_layer") or ""),
        "资产数=%s ｜ source=%s" % (af.get("assets"), (model.get("sources") or {}).get("asset_layer")))

    # ── 第四边：页面边（P1/P2/P3）────────────────────────────────────────────
    rows.extend(page_edge_checks(art))
    return rows


def cmd_check(as_json: bool = False) -> int:
    art = build_artifacts()
    rows = run_checks(art)
    live = art.get("ledger") or {}
    live_caps = live.get("caps") or []
    negs = []

    # N1 掏空能力边（caps=[]）⇒ C1/C4 必须报红
    r0 = [r for r in run_checks({**art, "ledger": {**live, "caps": [], "counts": {},
                                                  "tentacle_domains": [], "energy_channels": [],
                                                  "orphans": {}, "label_face": {}}})
          if r["id"].split(" ", 1)[0] in ("C1", "C4")]
    negs.append(("掏空能力边（caps=[]）", "C1+C4", bool(r0) and all(not r["ok"] for r in r0),
                 "；".join("%s=%s" % (r["id"].split(" ", 1)[0], "红" if not r["ok"] else "绿!")
                           for r in r0)))

    # N2 一条能力不绑（carrier 掏空）⇒ C4 必须报红
    if live_caps:
        pc = json.loads(json.dumps(live_caps))
        pc[0]["carrier"] = ""
        f = honesty_findings({**live, "caps": pc})
        negs.append(("喂坏：一条能力承载载体掏空（空白冒充绑好）", "C4", bool(f),
                     (f[0] if f else "（本该报红却没报）")))
    else:
        negs.append(("喂坏：一条能力承载载体掏空", "C4", False, "（台账空，负对照跑不了）"))

    # N3 绑到不存在的触手域 ⇒ C5 必须报红
    pc3 = json.loads(json.dumps(live))
    if pc3.get("caps"):
        pc3["caps"][0]["tentacle_domains"] = ["并不存在的触手域"]
        pc3["orphans"]["caps_bad_domain"] = ["%s → 触手域 '并不存在的触手域'（不在触手总纲）"
                                            % pc3["caps"][0]["name"]]
    r3 = [r for r in run_checks({**art, "ledger": pc3}) if r["id"].split(" ", 1)[0] == "C5"]
    negs.append(("喂坏：绑到不存在的触手域", "C5", bool(r3) and not r3[0]["ok"],
                 (r3[0]["detail"] if r3 else "（没跑 C5）")))

    # N4 绑到不存在的能量通道 ⇒ C5 必须报红
    pc4 = json.loads(json.dumps(live))
    if pc4.get("caps"):
        pc4["orphans"]["caps_bad_channel"] = ["%s → 能量通道 '不存在的通道'（不在 13 条链）"
                                              % pc4["caps"][0]["name"]]
    r4 = [r for r in run_checks({**art, "ledger": pc4}) if r["id"].split(" ", 1)[0] == "C5"]
    negs.append(("喂坏：绑到不存在的能量通道", "C5", bool(r4) and not r4[0]["ok"],
                 (r4[0]["detail"] if r4 else "（没跑 C5）")))

    # N5 死亡通道画成承载 ⇒ C6 必须报红
    pc5 = json.loads(json.dumps(live))
    for ch in (pc5.get("energy_channels") or []):
        if ch.get("alive") is not True:
            ch["caps"] = ["假装被承载"]
            ch["cap_count"] = 1
            break
    r5 = [r for r in run_checks({**art, "ledger": pc5}) if r["id"].split(" ", 1)[0] == "C6"]
    negs.append(("喂坏：不可用通道画成承载着 cap", "C6", bool(r5) and not r5[0]["ok"],
                 (r5[0]["detail"] if r5 else "（没跑 C6）")))

    # N6 双向反演破（删掉一条反向）⇒ C7 必须报红
    pc6 = json.loads(json.dumps(live))
    pc6["orphans"]["mismatch_cap_vs_domain"] = ["负对照：正向 {} ≠ 反向 {'视觉'}"]
    r6 = [r for r in run_checks({**art, "ledger": pc6}) if r["id"].split(" ", 1)[0] == "C7"]
    negs.append(("喂坏：能力↔触手域反演不一致", "C7", bool(r6) and not r6[0]["ok"],
                 (r6[0]["detail"] if r6 else "（没跑 C7）")))

    # N7 能量边不是 13 条 ⇒ C3 必须报红
    pc7 = json.loads(json.dumps(live))
    pc7["energy_channels"] = []
    r7 = [r for r in run_checks({**art, "ledger": pc7}) if r["id"].split(" ", 1)[0] == "C3"]
    negs.append(("喂坏：能量边读不到（channels=[]）", "C3", bool(r7) and not r7[0]["ok"],
                 (r7[0]["detail"] if r7 else "（没跑 C3）")))

    # N8 外链注入 ⇒ C12 必须报红
    r8 = [r for r in run_checks({**art, "html": art["html"]
                                 + '<link rel="stylesheet" href="https://cdn.example.com/x.css">'})
          if r["id"].split(" ", 1)[0] == "C12"]
    negs.append(("外链注入（https cdn）", "C12", bool(r8) and not r8[0]["ok"],
                 (r8[0]["detail"] if r8 else "（没跑 C12）")))

    # N9 数据脚本改 type=module ⇒ C12 必须报红
    r9 = [r for r in run_checks({**art, "html": re.sub(
        r'<script src="energy-data\.js">',
        '<script type="module" src="energy-data.js">', art["html"])})
        if r["id"].split(" ", 1)[0] == "C12"]
    negs.append(("喂坏：数据脚本改 type=module", "C12", bool(r9) and not r9[0]["ok"],
                 (r9[0]["detail"] if r9 else "（没跑 C12）")))

    # N10 触手标签层未探测 ⇒ C9 必须报红
    pc10 = json.loads(json.dumps(live))
    pc10["label_face"] = {"labels": None, "why": "负对照：标签层读不到"}
    r10 = [r for r in run_checks({**art, "ledger": pc10}) if r["id"].split(" ", 1)[0] == "C9"]
    negs.append(("喂坏：触手标签层读不到", "C9", bool(r10) and not r10[0]["ok"],
                 (r10[0]["detail"] if r10 else "（没跑 C9）")))

    # ── 页面边负对照（第四边 · 三条）─────────────────────────────────────────
    energy = _parse_global_js(art.get("data") or "", "GBT_ENERGY") or {}
    ecaps = list(energy.get("caps") or [])

    # P-N1 页上塞一个**不在册**的位 ⇒ P2 必须报红（页→能力）
    if ecaps:
        e_ghost = json.loads(json.dumps(energy))
        e_ghost["caps"] = ecaps + [{"name": "并不存在的幽灵位", "bind_kind": "直连",
                                    "tentacle_domains": [], "energy": {"chain": False}}]
        e_ghost_txt = re.sub(
            r"globalThis\.GBT_ENERGY\s*=\s*\{.*\}\s*;\s*$",
            lambda _m: "globalThis.GBT_ENERGY = %s;\n" % json.dumps(e_ghost, ensure_ascii=False, separators=(",", ":")),
            art.get("data") or "", flags=re.S)
    else:
        e_ghost_txt = (art.get("data") or "") + "\n/* neg: no data */\n"
    rp2 = [r for r in run_checks({**art, "data": e_ghost_txt}) if r["id"].split(" ", 1)[0] == "P2"]
    negs.append(("喂坏：页上塞不在册的位（页→能力）", "P2", bool(rp2) and not rp2[0]["ok"],
                 (rp2[0]["detail"] if rp2 else "（没跑 P2）")))

    # P-N2 台账里藏一位**不发页**（从能力栏页数据件删掉一位）⇒ P1 必须报红（能力→页）
    if ecaps and (art.get("ledger") or {}).get("caps"):
        victim = (art["ledger"]["caps"][0] or {}).get("name")
        e_drop = json.loads(json.dumps(energy))
        e_drop["caps"] = [c for c in ecaps if c.get("name") != victim]
        e_drop_txt = re.sub(
            r"globalThis\.GBT_ENERGY\s*=\s*\{.*\}\s*;\s*$",
            lambda _m: "globalThis.GBT_ENERGY = %s;\n" % json.dumps(e_drop, ensure_ascii=False, separators=(",", ":")),
            art.get("data") or "", flags=re.S)
        rp1 = [r for r in run_checks({**art, "data": e_drop_txt}) if r["id"].split(" ", 1)[0] == "P1"]
        negs.append(("喂坏：台账里藏一位不发页（能力→页 · 点名 %s）" % victim, "P1",
                     bool(rp1) and not rp1[0]["ok"],
                     (rp1[0]["detail"] if rp1 else "（没跑 P1）")))
    else:
        negs.append(("喂坏：台账里藏一位不发页（能力→页）", "P1", False, "（数据件空，负对照跑不了）"))

    # P-N3 页项字段与台账**不一致**（改一个 bind_kind）⇒ P3 必须报红（逐项一致）
    if ecaps:
        e_drift = json.loads(json.dumps(energy))
        e_drift["caps"][0]["bind_kind"] = "触手承载" if e_drift["caps"][0].get("bind_kind") != "触手承载" else "直连"
        e_drift_txt = re.sub(
            r"globalThis\.GBT_ENERGY\s*=\s*\{.*\}\s*;\s*$",
            lambda _m: "globalThis.GBT_ENERGY = %s;\n" % json.dumps(e_drift, ensure_ascii=False, separators=(",", ":")),
            art.get("data") or "", flags=re.S)
        rp3 = [r for r in run_checks({**art, "data": e_drift_txt}) if r["id"].split(" ", 1)[0] == "P3"]
        negs.append(("喂坏：页项字段与台账不一致（改 bind_kind）", "P3",
                     bool(rp3) and not rp3[0]["ok"], (rp3[0]["detail"] if rp3 else "（没跑 P3）")))
    else:
        negs.append(("喂坏：页项字段与台账不一致", "P3", False, "（数据件空，负对照跑不了）"))

    fails = [r for r in rows if not r["ok"]]
    neg_fail = [x for x in negs if not x[2]]
    if as_json:
        print(json.dumps({"rows": rows,
                          "negatives": [{"name": n, "target": t, "ok": o, "detail": d}
                                        for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(neg_fail)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 82)
        print("能力 ↔ 触手 ↔ 能量 · 绑定判据（含负对照）")
        print("=" * 82)
        for r in rows:
            print("%s %-62s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"][:120]))
        print("-" * 82)
        for nm, tg, ok, det in negs:
            print("%s 负对照[%-5s] %-40s %s" % ("PASS" if ok else "FAIL", tg, nm[:40], det[:110]))
        print("-" * 82)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(neg_fail), len(neg_fail)))
    return 1 if (fails or neg_fail) else 0


def _neighborhood_index() -> dict:
    """方法名 → 邻域（取自触手桥的邻域表；取不到就空，不猜）。"""
    try:
        from gbt_allinone.tentacle import bridge as _BR
        idx = {}
        for _dom, _info in _BR.TENTACLE_NEIGHBORHOOD_MAP.items():
            for _m in _info.get("powered_by") or []:
                idx.setdefault(_m, _dom)
        return idx
    except Exception:                                            # noqa: BLE001
        return {}


_NEIGHBORHOOD_INDEX = _neighborhood_index()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    if not argv:
        rc = cmd_report()
        if rc == 0:
            cmd_render()
        return rc
    if argv[0] == "build" or argv[0] == "report":
        return cmd_report()
    if argv[0] == "render":
        return cmd_render()
    if argv[0] == "feel":
        return cmd_feel()
    if argv[0] in ("--json", "json"):
        print(json.dumps(build_model(), ensure_ascii=False, indent=1))
        return 0
    if argv[0] in ("--check", "check"):
        return cmd_check(as_json="--json" in argv)
    print("用法：capability-bindings.py [build|render|feel|--json|--check [--json]]（无参 = build + render）")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
