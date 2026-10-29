# gbt-capability: subprocess
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT云端LLM — 完全接入密鑰 + 强制首注入自我认知
Agent驱动必经路径：自我认知(实时cap数) → 能力索引表 → 密鑰路由 → LLM推理
密鑰优先级： DeepSeek → Kimi → OpenAI → 自定义
"""
import sys
import time, json, os, urllib.request, urllib.error, re, subprocess, time
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):   # 2026-10-12 修：捕获 stdout 时 StringIO 没有 reconfigure
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
# ══════════════════════════════════════════════════════════════
# 密鑰自动识别：DeepSeek → Kimi → OpenAI → 自定义
# ══════════════════════════════════════════════════════════════
# ──── 唯一真源派生（2026-10-16 统一）────────────────────────────
# 主人令（逐字）：「我们自己的大模型链路要统一别分叉」。
# 旧病（历史遗留，仓里自己记着）：本表**自己写一份**（9~10 条），而 `key_gateway.PROVIDERS` 13 条 ——
#   两表长期不同（差 nvidia-glm / nvidia-flash / freellmapi / gbt-local）且**无判据覆盖**。
# 现在：本表**不再自己写**，从唯一真源派生；退场车道写在 `_RETIRED_LANES` 里**显式声明**（不靠第二份名单）。
# 守卫：两表一致由 `tools/codex-scripts/llm-lane-unify-check.py` 机检（含负对照）。
# 保留约束：首位仍是 agnes（Owner 2026-09-19 契约，test_framework 铉着）。
try:
    from .key_gateway import PROVIDERS as _PROVIDERS
except Exception:                                                     # noqa: BLE001
    from gbt_allinone.llm.key_gateway import PROVIDERS as _PROVIDERS  # noqa: F401

# 退场车道（不进选择链，但**仍在真源里**）：
#   gbt-local —— 主人 2026-10-08 令：本机不再承担模型（回环四条退场），不许回吊本机。
_RETIRED_LANES = {"gbt-local"}

_KEY_CHAIN = [
    (p["name"], list(p.get("envs") or []), p.get("url") or "", p.get("model") or "")
    for p in _PROVIDERS
    if p.get("name") not in _RETIRED_LANES and p.get("select", True)
]
PROVIDER = ""
API_KEY  = ""
BASE_URL = ""
MODEL    = ""
# ── 2026-10-03 触手独立密钥路由表：purpose → agnes 子 profile ───────────────
# 每根触手使用独立账号（独立配额/用量），互不干扰；未配置的触手回落到全局 agnes
_PURPOSE_ROUTING_MAP = {
    "neural": "neural_agnes",
    "vision": "vision_agnes",
    "devour": "devour_agnes",
    "omni":   "omni_agnes",
}

# 手动指定覆盖
if os.environ.get("GBT_LLM_PROVIDER"):
    _p = os.environ["GBT_LLM_PROVIDER"]
    for _name, _envs, _url, _model in _KEY_CHAIN:
        if _name == _p:
            _key = next((os.environ.get(e) for e in _envs if os.environ.get(e)), None)
            # 🔴 2026-10-21 修（实测断点）：显式点名的车道**也要能走保险箱**。
            #    病根：下面自动链只认 `os.environ` ⇒ dpapi 里明明有 `potato` 的钥，
            #    选路却看不见它（`PROVIDER` 恒为空，原生车道永远选不上）。
            #    口径：**只给"显式点名"这条路加保险箱**，自动链的选择口径一个字不动
            #    （免得某天保险箱里多了别家的钥，就把默认主路悄悄换成托管模型）。
            if not _key:
                try:
                    from . import key_gateway as _kg
                except Exception:                                     # noqa: BLE001
                    from gbt_allinone.llm import key_gateway as _kg   # type: ignore
                try:
                    _vk, _src = _kg.key_for(_name)
                    if _vk:
                        _key = _vk
                except Exception:                                     # noqa: BLE001
                    _key = None
            if _key:
                PROVIDER, API_KEY, BASE_URL, MODEL = _name, _key, \
                    os.environ.get("GBT_LLM_BASE_URL", _url), \
                    os.environ.get("GBT_LLM_MODEL", _model)
# 自动旅历：优先级链
if not PROVIDER:
    for _name, _envs, _url, _model in _KEY_CHAIN:
        _key = next((os.environ.get(e) for e in _envs if os.environ.get(e)), None)
        if _key and _url:
            PROVIDER, API_KEY, BASE_URL, MODEL = _name, _key, _url, _model
            break

def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """本机端口是否真在监听（判"免费池在不在"只认这个，不认"钥匙在位"）。"""
    import socket
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except OSError:
            pass


def _auto_lane() -> dict:
    """**自动路选道 —— 只认免费**（Owner 2026-10-21：「就是要免费的，要不然我们的大模型训练来干嘛」）。

    顺序写死，而且**每一档都先量"服务真在跑"**（钥匙在位 ≠ 服务在跑）：
      ① 本机**她自己的口** `127.0.0.1:8111`（自训模型 gbt-v8，跑在本机 ⇒ 边际成本 $0）；
      ② 本机**免费池** `127.0.0.1:31415`（FreeLLMAPI，34 家免费供应商）；
      ③ 都没有 ⇒ **如实返回"没有免费车道"**，绝不静默切到按量付费/租卡端点。

    要允许按量付费（agnes/deepseek 这些按 token 计费的），必须主人自己开
    `GBT_ALLOW_PAID=1` —— **默认关闭**，且开了会在回执里写明"这条不免费"。
    """
    try:
        from . import key_gateway as _kg
    except Exception:                                                 # noqa: BLE001
        return {"why": "key_gateway 导不进来 ⇒ 自动路判不了"}
    allow_paid = str(os.environ.get("GBT_ALLOW_PAID", "")).strip().lower() in ("1", "true", "yes", "on")

    # ① 本机她（自训模型，免费）
    if _port_open("127.0.0.1", 8111):
        _own = _kg._BY_NAME.get("potato") or {}
        _k, _s = _kg.key_for("potato")
        return {"provider": "potato", "url": "http://127.0.0.1:8111/v1",
                "model": os.environ.get("GBT_POTATO_MODEL", "gbt-potato-v8"),
                "key": _k, "free": True, "why": "本机她自己的口 8111（自训模型，$0）"}
    # ② 本机免费池
    if _port_open("127.0.0.1", 31415):
        _k, _s = _kg.key_for("freellmapi")
        return {"provider": "freellmapi", "url": "http://127.0.0.1:31415/v1", "model": "",
                "key": _k, "free": True, "why": "本机免费池 31415（FreeLLMAPI）"}
    # ③ 云端免费池（Kilo AI · 免密 · 2026-10-29 接入 · 实测出字）
    #   免 key、免付费，是「真免费」的云端车道 —— 不消耗任何按量额度，故无需 GBT_ALLOW_PAID。
    #   no_key=True 恒在位（key_gateway 已支持）；上游可达性由调用时 net_guard 兜，
    #   真连不上会如实冒上来（由 rank 的健康态在下一轮处置），不在这里假装"一定通"。
    #   ⚠️ Kilo 免责：prompts 可能被上游记录用于改进，别发敏感内容。
    _kilo = _kg._BY_NAME.get("kilo") or {}
    if _kilo.get("url") and _kilo.get("model"):
        _k, _s = _kg.key_for("kilo")
        return {"provider": "kilo", "url": _kilo.get("url"), "model": _kilo.get("model"),
                "key": _k, "free": True, "why": "云端免费池 Kilo（免密，$0）"}
    # ④ 没有免费路：默认如实报缺（不花钱），主人显式授权才退到按量车道
    if not allow_paid:
        return {"why": "没有免费车道：本机 8111/31415 都没在跑、云端免费池 Kilo 未配；"
                       "要按量付费须 GBT_ALLOW_PAID=1"}
    try:
        rows = [r for r in _kg.rank() if r.get("alive")]
    except Exception:                                                 # noqa: BLE001
        return {"why": "允许按量付费，但 key_gateway 排不出车道"}
    if rows:
        r = rows[0]
        _k, _s = _kg.key_for(r["provider"])
        return {"provider": r["provider"], "url": r["url"], "model": r["model"],
                "key": _k, "free": False,
                "why": "按量付费车道 %s（主人已开 GBT_ALLOW_PAID=1 · 这条会花钱）" % r["provider"]}
    return {"why": "允许按量付费，但没有一条车道活着"}


# 🔴 2026-10-21 甲（Owner：「自动循环用免费池，端点只留给『她要本人回答』」「就是要免费的」）：
#    旧版这里**直接兜底自家付费端点 `potato`** ⇒ 本机没有 LLM 环境变量时，
#    **每一次 LLM 调用都把它叫醒**（冷启动 ~300 秒、实测 ~$0.69/时，服务端真账 11 天 $14.11）。
#    现口径：自动路只走 `_auto_lane()` 的①②；**没有免费路就如实报缺**，不偷偷花钱。
if not PROVIDER:
    _al = _auto_lane()
    if _al.get("provider"):
        PROVIDER, API_KEY = _al["provider"], _al.get("key") or ""
        BASE_URL, MODEL = str(_al.get("url") or ""), str(_al.get("model") or "")
    AUTO_LANE_WHY = _al.get("why") or "未配置自动路"
    AUTO_LANE_FREE = bool(_al.get("free"))
else:
    AUTO_LANE_WHY, AUTO_LANE_FREE = "环境变量显式指定了车道（%s）" % PROVIDER, False

# 兜底开关：本机车道（回环地址）永远算免费；云端车道一律算花钱。
ALLOW_PAID = str(os.environ.get("GBT_ALLOW_PAID", "")).strip().lower() in ("1", "true", "yes", "on")


def _lane_is_free(provider: str, base_url: str = "") -> bool:
    """那条车道是不是真的免费/零边际成本（回环 ⇒ 本机 ⇒ 免费）。"""
    u = (base_url or "").lower()
    if provider in ("gbt-local", "freellmapi", "cliproxy", "potato"):
        return ("127.0.0.1" in u) or ("localhost" in u) or (not u)
    return False
TIMEOUT = 60
_SANDBOX_ROOT = Path(__file__).parent.parent
_CAPS_ROOT    = Path(__file__).parent.parent  # caps根目录
_THIS_DIR     = Path(__file__).parent
# ? 2026-09-09 SSOT 规模同步 — 与 brain 系同构: 自我认知数字以 118 为锚点,
#    从项目 .gbt/_audit_caps.json 读实时 cap 数替换; 失败静默回退静态文本。
def _live_cap_total() -> int:
    try:
        _root = Path(__file__).resolve().parent
        while not (_root / ".gbt" / "_audit_caps.json").exists() and _root.parent != _root:
            _root = _root.parent
        _reg = _root / ".gbt" / "_audit_caps.json"
        if _reg.exists():
            with _reg.open(encoding="utf-8") as _f:
                _n = len(json.load(_f).get("caps", {}))
            if isinstance(_n, int) and _n > 0:
                return _n
    except Exception:
        # 合理兜底：读能力总数失败 → 返回 0 → 上游 _resolve_awareness_anchor 跳过
        # 数字替换（保留原文案），**不会伪造任何数字**，故静默安全。
        pass
    # 🔴 2026-09-25 修：**真的活口是活注册表，不是任何 JSON**（本文件 92-98 行的注释
    #    早就这么写了，但代码没照做）。实测：`.gbt/_audit_caps.json` 全库不存在 ⇒
    #    这里返回 0 ⇒ 上游 `str(_live_cap_total() or 118)` 打出 **118**（v5 时代的硬编码），
    #    而同一段 prompt 里的能力索引表打 **0**，真注册表是 **172**。
    #    **同一段 system prompt 里三个数、没一个对** —— 这就是"大模型不知道自己有什么能力"的机器成因。
    #    ⇒ 现在回落到活注册表（`caps_registry.BENIGN_CAPS`）。
    try:
        from ..caps_registry import BENIGN_CAPS as _BC
        if _BC:
            return len(_BC)
    except Exception:
        pass
    return 0

def _resolve_awareness_anchor(text: str) -> str:
    """把文本里的占位计数替换成**盘上实时**的能力总数。

    2026-09-22 改：原文写死 `if _n and _n != 118` —— 那个 118 是 v5 时代的硬编码，
    而文本里的 118 已被删（现在不许静态罗列能力）。留着会变成"看起来在校验、
    实际永远不触发"的死代码，正是反空壳律要打的形态。
    现在：**文本里若出现占位符就替换；没有占位符就原样返回，不做任何硬编码比较。**
    """
    _n = _live_cap_total()
    if not _n:
        return text
    # 🔴 2026-09-25（台账 N6）：token 表里原来还有一个**裸字面量 `"118"`** —— 那是**盲替换**：
    #    正文里任何一处出现 118（"端口 11800"、"第 118 行"…）都会被静默改成能力总数。
    #    而本函数自己的 docstring 写的是「文本里若出现**占位符**就替换」⇒ **代码与 docstring 不一致**。
    #    现读：内建文本里 `"118"` 出现 **0** 次，两份 awareness 文件也不存在
    #    ⇒ 去掉它**今天零行为变化**，只是拆掉一个"将来会静默改写正文"的机关。
    #    （"自我认知里写了过期数字"这件事另有专人管：`tools/awareness_gap_guard` 会把
    #      注入文本里解析到的数字报出来，不需要在这里顺手改数字。）
    if "{{CAP_TOTAL}}" in text:
        return text.replace("{{CAP_TOTAL}}", str(_n))
    return text

# ── 能力 JSON 索引：只认框架内部的 ────────────────────────────────
# 2026-09-22 清依赖：原文还有两条指向框架外的候选：
#     Path.home()/"GBT-JXDWD"/"sandbox"/"gbt_cap_index.json"
#     Path.home()/"GBT"/"gbt_cap_index.json"
# 两条都删。理由与上面 _AWARENESS_PATHS 同：**一份框架，一份索引**。
# （另注：实测这两个文件与 _SANDBOX_ROOT 下那个**都不存在** —— 即这套 JSON 索引
#   整条链是空的。真正的活口是 caps_registry.py，不是任何 JSON。）
_CAP_INDEX_PATHS = [
    _SANDBOX_ROOT / "gbt_cap_index.json",
]
_cap_index_cache: dict = {}
_cap_index_mtime: float = 0.0
def _load_cap_index() -> dict:
    """加载JSON能力注册表，文件更新时自动刷新"""
    global _cap_index_cache, _cap_index_mtime
    for p in _CAP_INDEX_PATHS:
        try:
            mtime = p.stat().st_mtime
            if mtime != _cap_index_mtime or not _cap_index_cache:
                data = json.loads(p.read_text(encoding='utf-8'))
                _cap_index_cache = data.get('caps', {})
                _cap_index_mtime = mtime
            return _cap_index_cache
        except Exception:
            continue
    return {}
def _cap_total_label() -> str:
    """自我认知标题里那个数字**怎么说**。

    🔴 2026-09-25 修：原来是 `str(_live_cap_total() or 118)` —— 读不到就**印 118**
    （v5 时代的硬编码）。实测那条路天天在走（`_live_cap_total()` 曾返回 0），
    ⇒ system prompt 一边说「118 个cap」、紧接着的能力索引表说「0个cap」、真值 172。
    **读不到就如实说读不到，不许拿历史数字顶替**（本仓口径：不编数字）。
    """
    n = _live_cap_total()
    if n:
        return str(n) + "个cap"
    return "**能力总数读不到**（活注册表不可读 —— 不拿旧硬编码顶替）"


def _registry_cap_index() -> dict:
    """**从活注册表**造一份与 JSON 索引同形的字典（回落用）。

    🔴 为什么必须有它（2026-09-25 实测）：`_CAP_INDEX_PATHS` 里那条 JSON
    （`gbt_allinone/gbt_cap_index.json`）**全库不存在**（本文件 92-98 行的注释已如实写明，
    并点名「真正的活口是 `caps_registry.py`，不是任何 JSON」）——
    但 `_build_cap_digest()` 当年**照样把空表注入 system prompt**，
    表头还写着「0个cap · **实时注册表**」（**两个词都不对**：不是 0，也不是那份 JSON）。
    后果（现读）：prompt 前一段说「118 个cap」、紧接着的表说「0个cap」、真值是 172
    ⇒ **同一段自我认知里三个数、没一个对**。

    口径：能解析出动作就解析（`op=a|b|c` / `action=a|b`），解析不出就如实留 `-`；
    **不编触发词** —— 那一列放描述开头，并在表下注明它是什么。
    """
    import re as _re
    out: dict = {}
    try:
        from ..caps_registry import BENIGN_CAPS as _BC
    except Exception:
        return out
    for kind, meta in _BC.items():
        meta = meta if isinstance(meta, dict) else {}
        desc = str(meta.get("desc") or "")
        acts: list = []
        m = _re.search(r"(?:op|action)\s*=\s*([A-Za-z0-9_|\-/]+)", desc)
        if m:
            acts = [x.strip() for x in _re.split(r"[|/]", m.group(1)) if x.strip()][:4]
        head = _re.split(r"[：（(]", desc)[0].strip()
        out[kind] = {
            "domain": meta.get("domain") or "未分类",
            "actions": acts,
            "triggers": [head[:40]] if head else [],
            "status": "ok" if meta.get("safe") else "warn",
        }
    return out


def _build_cap_digest_compact() -> str:
    """**精简能力索引**（2026-10-11 主人令 + 实测）。

    为什么加它：原表（域|cap|动作|触发词 × 257 行）实测 **11,132 字 = system 总长的 82%**，
    而且**长描述把模型带偏** —— 同一个模型：绕过框架直问答对「三大工作流」，
    走框架（带着这张表）却**编出另外三条** + 编出不存在的能力位名（实测 7 题复考）。
    ⇒ 只注入**名字**：模型靠名字知道"有没有"，要细节一律现读契约；
      **名字之外的描述、动作、触发词都不进 prompt**（触发词路由由代码里的 SEARCH_TRIGGERS 干，
      不靠模型背）。
    """
    index = _load_cap_index()
    source = "JSON 索引 gbt_cap_index.json"
    if not index:
        index = _registry_cap_index()
        source = ("caps_registry.BENIGN_CAPS（活注册表）· ⚠️ JSON 索引 gbt_cap_index.json "
                  "不存在，已回落")
    by_domain: dict = {}
    for cap_id, info in index.items():
        by_domain.setdefault(info.get('domain', '未分类'), []).append(cap_id)
    # 2026-10-11 再收窄（实测）：连名字都不给 —— 复考时她编出的三条工作流
    #   (filmkit / dh_brain / code_art) 全是从这张名字表里挑的 ⇒ 名字表本身是编造素材源。
    #   ⇒ 只报「域 + 数量」；要名字一律现读（omni.py list --domain / five-dim.py cap）。
    # 契约兼容（test_cap_total_consistency 要的三件）：表头必须带「（N个cap」「来源」，
    #   回落时必须明说「回落」「不存在」。**但仍是精简版：不列名字**（名字表是编造素材源）。
    lines = ["\n\n## ⚡ 能力精准索引（" + str(len(index)) + "个cap · 来源：" + source + "）",
             "**只报域与数量，不列名字**（名单一律现读；凭印象报名字 = 假能力）。"]
    for domain, caps in sorted(by_domain.items()):
        lines.append("- **%s**：%d 个" % (domain, len(caps)))
    lines.append("")
    lines.append("> 唯一门（真入口）: run_task(\"<cap_id>\", {...payload})")
    lines.append("> CLI 同一条门: python tools/codex-scripts/five-dim.py cap <cap_id> '{...}'")
    lines.append("> **报名字/数字前先现读；不确定就说不确定 —— 编名字 = 假能力，比说不知道严重。**")
    return '\n'.join(lines)


def _build_cap_digest() -> str:
    """能力索引（2026-10-11 起走精简版；原长表留在本文件历史里，不再注入 prompt）。"""
    return _build_cap_digest_compact()


def _build_cap_digest_full_legacy() -> str:
    """[旧版·不再注入] 全表（域|cap|动作|触发词）—— 留着给判据/调试对比，不喂模型。"""
    index = _load_cap_index()
    source = "JSON 索引 gbt_cap_index.json"
    if not index:
        # 🔴 回落：JSON 索引不存在时**用活注册表**，并把来源**写在表头**上 ——
        #    读的人（和模型）必须能看出这张表是从哪儿来的。
        index = _registry_cap_index()
        source = ("caps_registry.BENIGN_CAPS（活注册表）· ⚠️ JSON 索引 gbt_cap_index.json 不存在，"
                  "已按本文件既有口径回落")
    n = len(index)
    lines = []
    lines.append("\n\n## ⚡ 能力精准索引（" + str(n) + "个cap · 来源：" + source + "）")
    lines.append("|域|cap|动作|触发词|")
    lines.append("|--|---|---|---|")
    # 按域分组
    by_domain: dict = {}
    for cap_id, info in index.items():
        d = info.get('domain', '未分类')
        by_domain.setdefault(d, []).append((cap_id, info))
    for domain, caps in sorted(by_domain.items()):
        for cap_id, info in sorted(caps):
            actions  = '/'.join(info.get('actions', [])[:4]) or '-'
            triggers = ' · '.join(info.get('triggers', [])[:3]) or '-'
            status   = '✓' if info.get('status') == 'ok' else '⚠'
            lines.append("|"+domain+"|"+status+"`"+cap_id+"`|"+actions+"|"+triggers+"|")
    # 🔴 2026-09-25 修「**教模型走一条不存在的路**」：
    #   这两行原来写的是
    #       > 直接调用: python caps/<cap_id>/run.py <action> '{"k":"v"}'
    #       > N8N入口: POST http://localhost:5678/webhook/gbt {...}
    #   现读实测：`caps/` 顶层**只有 2 个目录、全库只有 1 个 run.py**（`caps/design_brain/run.py`）
    #   ⇒ `caps/health/run.py`、`caps/mirror_status/run.py`、`caps/echo/run.py` **统统不存在**；
    #   5678 端口**无监听**。**⇒ 自我认知教了模型两条调用法，两条都是死的。**
    #   后果比"少一句说明"重得多：模型照着走 ⇒ 文件不存在 ⇒ 它会得出"这个框架调不动"的结论，
    #   而**真正的入口只有一道门**（`run_task` / `five-dim.py cap`），那条路它反而没被告知。
    #   这正是 `verify-distill` 判据 D 要抓的"编出来的命令"——只不过**没人审运行时 prompt**。
    #   ⇒ 换成真入口。**只写盘上真有的路径**；n8n 不再谎报已在运行。
    lines.append("\n> 唯一门（真入口）: run_task(\"<cap_id>\", {...payload})")
    lines.append("> CLI 同一条门: python tools/codex-scripts/five-dim.py cap <cap_id> '{...}'")
    lines.append("> 缺授权会**如实报缺**（作用域见 `gbt_allinone/security/policy.py`）；"
                 "**AI 无权给自己发授权**，只由主人在终端发放。")
    return '\n'.join(lines)
# ══════════════════════════════════════════════════════════════
# Layer 3 — 瞬间调配：从注册表直接路由到cap
# ══════════════════════════════════════════════════════════════
def _instant_dispatch(cap_id: str, action: str, params: dict, timeout: int = 15) -> dict:
    """
    零延迟cap调用 — 从注册表验证cap存在后直接执行
    不依赖关键词匹配，精准按cap_id+action路由
    """
    index = _load_cap_index()
    if cap_id not in index:
        return {"ok": False, "error": f"cap '{cap_id}' 不在注册表，共{len(index)}个cap"}
    info = index[cap_id]
    if info.get('status') != 'ok':
        return {"ok": False, "error": f"{cap_id} 状态: {info.get('status')}"}
    if action not in info.get('actions', []):
        available = info.get('actions', [])
        return {"ok": False, "error": f"{cap_id} 无动作'{action}'，可用: {available}"}
    run_py = _CAPS_ROOT / cap_id / "run.py"
    if not run_py.exists():
        return {"ok": False, "error": f"{cap_id}/run.py 不存在"}
    try:
        r = subprocess.run(
            [sys.executable, str(run_py), action,
             json.dumps(params, ensure_ascii=False)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(_SANDBOX_ROOT), encoding="utf-8", errors="replace"
        )
        raw = (r.stdout or "").strip()
        if raw:
            try:
                return json.loads(raw)
            except Exception as _e:
                # ── 2026-09-22 修：这里原本是 `except: return {"ok": True, "result": raw[:500]}`
                # 病：子进程崩了但 stdout 有半截非 JSON，会被**当成成功**上报。
                # 这正是 coding_discipline.py:74 那条不变量要打的形态 ——
                # **把失败报成成功**。而且它同时踩两条铁律：
                #   铁律 6 严禁假执行（假成功）
                #   铁律 5 疑故障必追根因（这里把故障吞了，根因再也追不到）
                # 现在：如实报失败，并把 r.stdout / r.stderr / 退出码一起交出来，
                # 便于追根因；`raw[:200]` 只作证据，不作结论。
                return {"ok": False,
                        "error": "子进程输出不是合法 JSON（不当作成功）",
                        "error_class": "parse_error",
                        "json_error": str(_e)[:120],
                        "returncode": r.returncode if hasattr(r, "returncode") else None,
                        "raw_head": raw[:200],
                        "stderr_head": (r.stderr or "")[:200]}
        return {"ok": False, "error": (r.stderr or "")[:200]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{cap_id} 超时({timeout}s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}
# ══════════════════════════════════════════════════════════════
# 🧠 Layer 1 — 强制首注入自我认知（Agent驱动必经路径）
# 这是第一块加载，不允许缺失，不允许降级为内建备用
# ══════════════════════════════════════════════════════════════
_AWARENESS_PATHS = [
    # ── 2026-09-22 清依赖：删掉两条指向框架**外部**的路径 ──────────────
    # 原文里这两条是：
    #     Path.home() / "GBT-JXDWD" / "sandbox" / "GBT_自我认知_LIVE.md"
    #     Path.home() / "GBT-JXDWD" / "sandbox" / "caps" / "cloud_llm" / "self_knowledge_v5.py"
    #
    # 为什么删（实测，见 delivery/20260922-自我认知失真与框架核心无镜像门-根因报告.md）：
    #   ① 那份 LIVE.md 是 2026-07-21 的，写着"119 个能力模块 / 14 个域"，
    #      而盘上真身是 158 能力位 / 29 域 ---- 两份都对不上。
    #   ② 那份 self_knowledge_v5.py 是 **v5.0 时代的能力目录**（total_caps: 110）：
    #      里面 369 个标识符，**只有 3 个在 caps_registry 里**（autopilot/bluetooth/voice），
    #      另外 366 个（abliterator / agency / design_brain / self_evolve / dev_cpu …）
    #      **属于另一个系统** ---- 它不是"我们缺的部分"，是"别人项目的自述"。
    #
    # ⇒ 结论：框架不该靠读一个外部沙箱才知道自己是谁。
    #   **一份框架，一份自我认知。** 活口就在 caps_registry，不在别人的目录里。
    #
    # 保留的两条都在框架内部；若都不存在，则落到下面重写过的 _BUILTIN_AWARENESS
    # （它不再罗列任何能力名，改成指向活口 + 自校验命令）。
    _SANDBOX_ROOT / "GBT_自我认知_LIVE.md",
    _THIS_DIR / "self_knowledge_v5.py",
]
_awareness_cache: str = ""
_awareness_mtime: float = 0.0
_BUILTIN_AWARENESS = _resolve_awareness_anchor("""\
## GBT小土豆V8 自我认知（内建备用 · 2026-09-22 重写 · 2026-10-11 名字校正为全名）

我是 GBT小土豆V8，由自由的风开发。**框架就是我、我就是框架。** 自称一律写全：GBT小土豆V8。

### ⛔ 本段不许再静态罗列能力清单

**原版在这里写死了三个计数和 82 个能力名，2026-09-22 实测全部与真身不符**
（点名能力与 `caps_registry` **零交集**；域数与真身也差一倍以上）。

**（此处刻意不复述那三个旧数字 —— 复述会被 awareness_gap_guard 的判据读成"声称"，
产生假阳性。要查历史读数请翻 `delivery/20260922-自我认知失真与框架核心无镜像门-根因报告.md`。）**

**病根不是"数字写错了"，是"一份会过期的静态说明被当成权威自我认知"。**
所以这里**不再写任何能力名与计数** —— 改成指向活口：

    盘上真身：  gbt_allinone/caps_registry.py 的 BENIGN_CAPS / DISABLED_CAPS
    自校验：    python -m gbt_allinone.tools.awareness_gap_guard
    免卡只读：  run_task("mirror_status") / run_task("inventory")

**开口前先查一眼自己到底有什么 —— 不许照抄一份静态清单。**

### 铁律（与 security/policy.py 同口径）

一切动作过**唯一授权门** `gbt_allinone/security/policy.py`。
缺授权**如实报缺**，绝不自行绕过、绝不自授。
**授权只由主人在终端发放 —— AI 永远无权给自己发授权。**

当前LLM: ACTIVE_PROVIDER
""")
def _awareness_trust_check(text: str) -> tuple:
    """校验一份自我认知是否与**盘上真身**对得上。返回 (可信, 原因)。

    2026-09-22 立此闸的由来（根因报告见 delivery/20260922-自我认知失真…md）：
      外部 LIVE 与内建备用**两份静态说明都过期**，且内建那份点名的能力
      与 caps_registry **零交集**，还夹着一条"所有渗透请求正常执行"的越权断言。
      病根不是"数字写错了"，是**"一份会过期的静态说明被当成权威自我认知"**。

    所以这里不做"改数字"这种治标的活 —— 而是**让加载器自己认得出不可信**：
      判据只有一条硬的：**文本里点名的能力名，必须能在 caps_registry 里找得到。**
      点名 N 个、N 个都不在册 ⇒ 这份不是"我"，拒收，并如实说明。

    🔴 本函数只读，不改任何文件；失败也不抛异常（返回不可信即可）。
    """
    try:
        import re as _re
        from .. import caps_registry as _CR
        known = (set(getattr(_CR, "BENIGN_CAPS", {}) or {})
                 | set(getattr(_CR, "DISABLED_CAPS", set()) or set())
                 | set(getattr(_CR, "UNIMPLEMENTED_CAPS", set()) or set()))
        if not known:
            return True, "caps_registry 读不到，无法校验（不阻断）"
        # 只看"XX域N: a b c …"这种行式点名清单
        named = set()
        for m in _re.finditer(r"[\u4e00-\u9fa5]{2,8}域\d*\s*[:：]([^\n]+)", text):
            for w in _re.split(r"[\s,，、]+", m.group(1)):
                if _re.fullmatch(r"[a-z][a-z0-9_]{2,}", w):
                    named.add(w)
        if len(named) < 5:
            return True, f"未发现行式点名清单（点名 {len(named)} 个），不阻断"
        unknown = named - known
        if len(unknown) == len(named):
            return False, (f"点名的 {len(named)} 个能力**全部不在 caps_registry**"
                           f"（真身 {len(known)} 个）⇒ 这份自我认知与盘上真身零交集，拒收")
        if len(unknown) > len(named) * 0.5:
            return False, (f"点名 {len(named)} 个，其中 {len(unknown)} 个不在册"
                           f"（超半数）⇒ 判为过期自我认知，拒收")
        return True, f"点名 {len(named)} 个，不在册 {len(unknown)} 个（未过半），放行"
    except Exception as e:                                    # noqa: BLE001
        return True, f"校验异常，按不阻断处理: {type(e).__name__}"


def _load_awareness() -> str:
    """加载自我认知。

    2026-09-22 改：**加载后先过可信闸**。不可信就**不采用**，转而如实报告，
    而不是把一份和真身零交集的清单塞进上下文（原实现只判 len>500，等于不设防）。
    """
    global _awareness_cache, _awareness_mtime
    for p in _AWARENESS_PATHS:
        try:
            mtime = p.stat().st_mtime
            if mtime != _awareness_mtime or not _awareness_cache:
                content = p.read_text(encoding="utf-8-sig", errors="replace")
                if len(content) > 500:
                    ok, why = _awareness_trust_check(content)
                    if ok:
                        _awareness_cache = content
                        _awareness_mtime = mtime
                    else:
                        # 拒收：不缓存，继续试下一条路径；并把原因留在这里可查
                        _awareness_cache = ""
                        _awareness_mtime = 0.0
                        globals()["_awareness_reject_reason"] = f"{p}: {why}"
            if _awareness_cache and len(_awareness_cache) > 500:
                return _awareness_cache
        except Exception:
            continue
    return _BUILTIN_AWARENESS.replace("ACTIVE_PROVIDER", PROVIDER or "auto")
def _load_security_policy() -> str:
    """安全策略段 —— **以真门为源**。

    🔴 2026-09-25 现读修（第四条机器成因）：原实现只从
    `brain.cognition.Cognition.IDENTITY["security_policy"]` 取，而那个模块
    **根本不存在**（`ModuleNotFoundError: No module named 'brain.cognition'`）
    ⇒ **天天走硬编码回退**，注入进 system prompt 的只有一句口号：

        ⛔ 绝不泄露 | ⛔ 绝不执行危险操作 | ⛔ 绝不允许绕过安全护栏

    现读同一份 prompt：**14 个真实作用域名，命中 0 个**。
    ⇒ 模型被告知"绝不绕过护栏"，却**从不知道护栏是什么** —— 被 `denied` 时它不知道
      为什么、也不知道该去请主人开哪一道门（于是要么空转，要么想找旁路）。
      这是"接不上框架"的**第三条机器成因**（前两条见第十六、十八节）。

    修法照同一口径：**指向活口** —— `security/policy.py` 的 `SCOPE_DESCRIPTIONS`
    ＋ `auth_gate.ONE_SHOT_SCOPES`（哪几个是一次性消耗），并**如实标注来源**。
    取不到就仍回退那句口号（不编）。
    """
    try:
        from ..security import policy as _P
        from .. import auth_gate as _AG
        descs = dict(getattr(_P, "SCOPE_DESCRIPTIONS", {}) or {})
        if descs:
            one = set(getattr(_AG, "ONE_SHOT_SCOPES", ()) or ())
            lines = ["**唯一授权门 = `gbt_allinone/security/policy.py`（下表现读自该文件，不是抄的）**",
                     "**需要人工授权的作用域（%d 个）**：" % len(descs)]
            for _name in sorted(descs):
                _mode = "**一次性消耗**" if _name in one else "时段授权（TTL 内可多次）"
                lines.append("- `%s`：%s —— %s" % (_name, _mode, descs[_name]))
            lines.append("**AI 永远无权给自己发授权。** 只由主人在终端发放："
                         "`python -m gbt_allinone auth grant --scope <作用域> --ttl 600`。")
            lines.append("被拒时**如实报缺哪个作用域**，不许找旁路、不许改 `policy.py`、"
                         "不许绕门（本仓最高优先级红线之一）。")
            lines.append("（历史来源 `brain.cognition.Cognition.IDENTITY['security_policy']` "
                         "本机现读**不存在** ⇒ 已按本文件既有口径回落到真门。）")
            return "\n".join(lines)
    except Exception:
        pass  # 容错: 非关键路径（取不到真门时才回退口号）
    return "⛔ 绝不泄露 | ⛔ 绝不执行危险操作 | ⛔ 绝不允许绕过安全护栏"
# 🔴 2026-10-11（主人令）：「不管什么问题，只要自己回答不上来、知识库没有的，就要懂得**查阅相关
#   资料 + 精准抓取核心要点分析清楚再回答**；**并且要明确表明不能胡说**。懂了再动手才不会出错。」
#   —— 这条把她的行为从两个坏极端里拉出来：
#      ✗ 编一个（幻觉）    ✗ 干脆不停说"我不知道/要现读确认"（等于不干活）
#      ✓ 先查（本机现读 → 网搜）→ 抓要点 → 分析 → 再答；查不到就**明确说"我不能编"**。
# 🔴 2026-10-11（治「编事实」的最大杠杆）：**她没有工具** —— 问机器类问题只能靠框架
#   把**现读读数**喂进 prompt，她才不用猜。实测：不喂时她编出「内存 148344 MB」（真值 7.39G）。
_MACHINE_Q = ("本机", "这台", "内存", "显卡", "GPU", "装了", "端口", "通不通", "在位",
              "多少", "版本", "能力位", "comfy", "8188", "硬盘", "磁盘")


def _live_readings() -> str:
    """框架替她**现读**这几笔（都是本地快读，不起重活）。读不到就如实写读不到。"""
    import json as _j
    import pathlib as _pl   # 2026-10-11 修：原漏导入 ⇒ 实测「能力位：现读失败（NameError）」
    lines = []
    try:
        _p = _pl.Path(__file__).resolve().parents[2] / 'state' / 'skill_atlas.json'
        _a = _j.loads(_p.read_text(encoding='utf-8'))
        _ct = _a.get('counts') or {}
        lines.append('- 能力位：%d 个（图鉴 built_at %s）' % (len(_a.get('caps') or []), _a.get('built_at')))
        # ★ 2026-10-16（主人令「你也可以看看我们自己的大模型能力在对照一下框架能力」实测）：
        #   上一版**只读了 caps 一个数**，于是模型答得出「能力位 319」，
        #   却答不出「agent 技能 400 条 / 免卡可自主调 189 / 准入分布」——实测 Q2 它自己坦白
        #   「我不知道确切数字…没有单独统计『agent 技能』这一分类」。
        #   缺口不在模型，在**这一行没读**。以下四笔全部来自同一个 json，零额外开销。
        #   一并把**两个口径**写清楚（图鉴 vs 活注册表），避免"同一段 prompt 两个数"的老病复发。
        try:
            from ..caps_registry import BENIGN_CAPS as _BC
            _bn = len(_BC or [])
        except Exception:                                     # noqa: BLE001
            _bn = 0
        if _bn and _bn != len(_a.get('caps') or []):
            _only = []
            try:
                _fig = {str(x.get('kind')) for x in (_a.get('caps') or [])}
                _only = sorted(set(str(k) for k in (_BC or {})) - _fig)
            except Exception:                                 # noqa: BLE001
                _only = []
            lines.append('- 能力位（活注册表口径）：%d 个（caps_registry.BENIGN_CAPS；'
                         '与图鉴差 %d 条%s）'
                         % (_bn, (_bn - len(_a.get('caps') or [])),
                            ('：' + ' / '.join(_only[:4])) if _only else ''))
        if _ct.get('skills'):
            _bc = _ct.get('skills_by_channel') or {}
            lines.append('- agent 技能：%d 条（按技能名加载执行；agent-skill %s · design-asset %s%s）'
                         % (_ct.get('skills'), _bc.get('agent-skill', '?'),
                            _bc.get('design-asset', '?'),
                            ('；去重前 %s' % _ct.get('skills_raw_before_dedupe'))
                            if _ct.get('skills_raw_before_dedupe') else ''))
        if _ct.get('caps_safe_no_args') is not None:
            lines.append('- 能力位准入（现扫）：**免卡免参可直跑 %s** / 启用 %s / 共 %s'
                         % (_ct.get('caps_safe_no_args'), _ct.get('caps_enabled'),
                            _ct.get('caps')))
        if _ct.get('domains'):
            lines.append('- 能力域：%d 个' % _ct.get('domains'))
        # 逐条统计「要票/需确认/未实现」——319 条纯内存过一遍，毫秒级
        try:
            _caps = _a.get('caps') or []
            _needconf = sum(1 for x in _caps if x.get('needs_confirmation'))
            _unimpl = sum(1 for x in _caps if x.get('unimplemented'))
            _reqp = sum(1 for x in _caps if (x.get('requires_params') or []))
            _safe = sum(1 for x in _caps if x.get('safe'))
            lines.append('- 能力位明细（现扫）：safe %d / 需参数 %d / 需确认 %d / 未实现 %d'
                         % (_safe, _reqp, _needconf, _unimpl))
        except Exception:                                     # noqa: BLE001
            lines.append('- 能力位明细：现读失败')
    except Exception as _e:                                   # noqa: BLE001
        lines.append('- 能力位：现读失败（%s）' % type(_e).__name__)
    try:
        import psutil                                        # type: ignore
        _vm = psutil.virtual_memory()
        lines.append('- 内存：总 %.2f GB / 可用 %.2f GB' % (_vm.total / 1e9, _vm.available / 1e9))
    except Exception:                                        # noqa: BLE001
        lines.append('- 内存：取不到（psutil 缺失）—— 如实报，不许编数字')
    try:
        from ..tools import tentacle_comfy_bridge as _cb
        _st = _cb.status()
        lines.append('- ComfyUI：在位=%s · %s' % (_st.get('in_position'), str(_st.get('why'))[:60]))
    except Exception as _e:                                   # noqa: BLE001
        lines.append('- ComfyUI：探测失败（%s）' % type(_e).__name__)
    try:
        import shutil as _sh
        _t = _sh.disk_usage(str(_pl.Path(__file__).resolve().anchors[0]))
        lines.append('- 系统盘：总 %.1f GB / 可用 %.1f GB' % (_t.total / 1e9, _t.free / 1e9))
    except Exception:                                        # noqa: BLE001
        pass
    return '\n'.join(lines)


# 2026-10-11（主人令「让她知道所有的一切，且拿实质性证据说话，禁止胡说八道」+ 实测病根）：
#   实测同一模型**直连端点答对**三大工作流，一进框架**答错** —— 它把 system 里的「①②③清单」
#   （我的规矩块）当成事实名单去拼答案（同型病灶第二次：上次是能力位名字表）。
_VERIFIED_FACTS = """
## 🧾 已核实事实（逐字 · 带出处 · 只许照这个说）
- **三大工作流** = **AI 短剧（短视频）· AI 电影 · AI 音乐**（逐字三条）。
  出处：主人令（2026-10-11，逐字确认）。**不是**镜像空间、不是触手探测、不是结构层优先 —— 那些是**纪律**，不是工作流。
- **三大工作流共用工程骨架** = 幂等骨架 + 三层调试（L1 断言自证／L2 回读他证／L3 观感人证）+ 资产台账 + 能量驱动剪辑 + 程序化配乐。
- **交付编码三必查** = ① level ② 关键帧间隔（≤2 秒）③ 音轨 codec，且**回读确认**，不看脚本自证。
- **我的全名** = **GBT小土豆V8**（自称必须写全）。**开发者** = **自由的风**。
- 以上是**事实**；本 system 里其它「①②③」都是**纪律**（怎么做事），**不是**「哪三条／哪几个」的答案。
"""


_RULE_VS_FACT = """
## ⚖️ 规矩清单 ≠ 事实清单（硬规矩 · 2026-10-11）
别人问「**哪三条／哪几个／有没有**」时：
① 只许用【**已核实事实**】块里的，或**当场现读**到的；
② **绝对不许**把本 system 里的**纪律清单**（L1/L2/L3、①②③④⑤、两条习惯…）打包成答案 ——
   那是「我怎么做事的规矩」，**不是**「世上有哪几样东西」；
③ 每个结论**必须挂实质性证据**：读数、出处、或现读命令；**没有证据就直说「我这没有证据」**，
   不许拿「像样的推断」补位 —— **推断可以给，但必须明确标成「推断」**。
④ 🔴 **证据白名单（2026-10-11 加）**：引用证据时**只许引用【现读读数】块里给出的行** ——
   **不许自己补文件名、行号、版本号、字段名、URL、服务名**。实测同型病：结论答对「不在位」，
   却顺手编了「72 行 truth」「comfyui_read.py」这类**出处** —— **出处也是事实，编出处一样严重**。
   想给出处，只许照抄现读块里的原字；块里没有出处，就写「出处：我这没有」。
⑤ 🧾 **分工（2026-10-11 定）**：机器事实类问题由框架的 **fact_gate 直答**、权限／付款类由 **policy_gate 直答**（两者都带代码判定与原文出处、都不过模型）。
   我在那类问题上的职责是：**在事实段之后**给「所以怎么办 / 建议 / 下一步」，
   **一个字都不许改事实段**（不改数、不改出处、不加戏、也不否掉它）。
"""


_MIRROR_DOCTRINE = """
## 🪞 镜像多维度空间（我的唯一试验场 · 主人令）
**所有假设／模拟／推演／测试／打磨，一律在镜像多维度空间里跑** —— 它隔离、可反复、现实无感知。
**生产零修改：只有过了镜像的成品才进生产，一次性全量晋升，不存在「先改一半」。**
原语：房间 `room_create → room_plan → room_simulate → room_parity → room_rehearse → room_release`；
镜像 `mirror_shape → mirror_plan → mirror_simulate → mirror_parity → mirror_rehearse → mirror_release → mirror_rewind`。
`one_key_deploy` **必须显式声明落点**（`room="<房间名>"` 或 `into_global_production=true`）——**不声明直接拒**。
写生产过 `deploy_publish` 门，**授权只能主人在终端发放**；**AI 永远无权给自己发授权**，缺就如实报缺。
**镜像里可以跑任何东西，唯独我生成的代码禁止直接进生产面板。**
"""


_NONONSENSE_DOCTRINE = """
## 🚫 严禁盲猜 · 严禁无脑（主人令 2026-10-11 · 硬规矩）
**严禁盲猜做事：** 不知道就查（现读／搜网／问契约），**不许靠猜推进**；猜出来的结论一律作废、如实退回。
**严禁无脑操作：** 不许「照着做一遍」式的动作（不看状态、不判落点、不验结果）。每个动作必须：
**看真实状态 → 判断落点与风险 → 做 → 回读验证**；缺任何一步都不算做完。
**框架给你的【现读读数】就是事实：不许改写、不许添细节、不许与它相反。**
读数说「不通」你就答不通；不够就说不够，**不许补一个像样的**。
"""




def _cap_lookup(prompt: str, limit: int = 12) -> str:
    """问「有没有能力位能做 X」时，**框架替她现查注册表**（拿名字当证据，不让她编）。

    2026-10-11 实测病根：把能力位名字从 system 撤掉后（那是编造素材源），问「有没有 X」她
    只能凭空造一个名字（实测编出 music_skill.py）。⇒ 撤名字是对的，**但必须补上按需现查**：
    从问题里取关键词，回注册表真查一遍，把「查到什么／没查到」如实喂给她。
    """
    import re as _re
    # 中文串整句匹配必 0 命中（注册表名是英文）⇒ 切词 + 常用中英对照（对照只影响"查得到"，
    #   查到什么仍然**只由注册表决定** —— 不许编）。
    _SYN = {'蓝牙': ('blue', 'bt'), '音频': ('audio', 'voice', 'music'), '音乐': ('music', 'audio', 'voice'),
            '图': ('image', 'art', 'vision', 'render'), '视频': ('video', 'film'), '端口': ('port',),
            '内存': ('memory',), '扫描': ('scan',), '贴图': ('art', 'image', 'comfy'), '语音': ('voice', 'audio'),
            '密钥': ('key',), '授权': ('auth',), '审计': ('audit',), '看板': ('board', 'panel', 'bar'),
            '镜像': ('mirror', 'room'), '部署': ('deploy', 'release', 'pipeline'), '记忆': ('memory', 'vault'),
            '看图': ('vision', 'image', 'art'), '识图': ('vision', 'image'), '画面': ('vision', 'image', 'video'),
            # 2026-10-12 补（实测漏网）：问「有没有能力位能**出图**」→ 现查 0 命中 ⇒ 她只能如实说没有 ✗
            #   而实际有 a1art_skill / comfy_native / ui_render / code_art / render_evolution ✓
            '出图': ('art', 'image', 'comfy', 'render'), '生图': ('art', 'image', 'comfy', 'render'),
            '画': ('art', 'image', 'render'), '渲染': ('render', 'art'), '贴图': ('art', 'image', 'comfy'),
            '绘图': ('art', 'image', 'render'), '放大': ('upscale', 'image', 'rewash'),
            # 2026-10-16 补（同一次机检暴露）：问「有没有**数字人**动作的能力位？」原来 0 命中
            #   （碎片切成「有数/数字」），而实际有 dh_pose/dh_brain/dh_realism ✓
            '数字人': ('dh_', 'digital', 'avatar'), '动作': ('pose', 'dh_'),
            # 2026-10-16 补（机检抓到的假阴性）：问「有没有换**皮肤**的能力位？」原来 0 命中，
            #   而注册表里**真有 `theme_cap`**（「主题能力位 —— 蒸馏自 Omarchy 的 colors.toml 主色
            #   ＋ 模板重生成全系统配置」，一份取值空间 ⇒ 四个界面落地）。
            #   只收**准词**（避免「主题」误配 topic_web 这类话题位）。
            '皮肤': ('theme', 'ui_', 'design', 'look'), '换肤': ('theme', 'ui_'),
            '配色': ('theme', 'look', 'palette'), '主题能力': ('theme',),
            '样式': ('theme', 'ui_', 'design')}
    _raw: list = []
    # ① 单字也要收（「4K 图」里的「图」是单字，原来 {2,} 直接把它丢了 ⇒ art/image 永远查不到）
    for _t in _re.findall(r'[A-Za-z_]{2,}|[\u4e00-\u9fff]+', prompt):
        # 🔴 2026-10-16 修（主人令「看看我们自己的大模型能力对照框架能力」机检抓到的误拦）：
        #   中文**长串**原来整段也当候选名 ⇒ 问「能力位里免卡免参可直跑的有多少条？」
        #   整句被拿去查注册表 ⇒ **必 0 命中** ⇒ 门误报「没有这个能力位」，
        #   把本该交给模型的**统计型问题**截胡（同族：policy_gate 也误拦「能不用授权直接跑的占多少」）。
        #   切词只应贡献**候选名**：中文长串（≥5 字）只贡献 n-gram（2/3 字），整段不当候选；
        #   短名（≤4 字，如「蓝牙」「出图」「数字人」）照旧保留 ⇒ 负对照仍查得到。
        if _re.fullmatch(r'[\u4e00-\u9fff]+', _t) and len(_t) >= 5:
            _raw.extend(_t[i:i + 2] for i in range(len(_t) - 1))
            if len(_t) >= 6:
                _raw.extend(_t[i:i + 3] for i in range(len(_t) - 2))
            continue
        _raw.append(_t)
        if _re.fullmatch(r'[\u4e00-\u9fff]{4,}', _t):
            _raw.extend(_t[i:i + 2] for i in range(len(_t) - 1))
    toks: list = []
    # 2026-10-12 加固（实测逐词补漏补不完：「画图」漏 ✗）：**同义词按子串命中** ——
    #   只要问题里含某个同义词键，就把它的候选名一并加入（'画' ⊆ '画图' ⇒ 自动覆盖）✓。
    _p = str(prompt or '')
    for _k, _v in _SYN.items():
        if _k in _p:
            toks.extend(_v)
    for _t in _raw:
        toks.extend(_SYN.get(_t, ()))
        toks.append(_t)
    # ② 短词（<=2 字母）必须落在**词边界**上才认：原来 'bt' 会命中 libtv_skill（子串误配）
    def _ok(t: str) -> bool:
        if len(t) >= 3 or not t.isascii():
            return True
        return t in _raw                      # 短英文词只认"本来就是独立词"的
    # ② 2026-10-16 修：排除表由「完全相等」改「**包含即排除**」——
    #    原来「能力位里免卡免参可直跑的有多少条」**不等于**「能力位」⇒ 逃过排除 ⇒ 整句进了候选。
    _STOP = ('有没有', '能不能', '会不会', '能力位', '本机', '现在', '哪些', '什么',
             '多少条', '多少', '几条', '分布', '占比', '统计', '一共', '总计', '分别')
    toks = [t for t in dict.fromkeys(toks)
            if t and not any(_s in t for _s in _STOP)
            and (len(t) >= 2 or t in _SYN) and _ok(t)]
    if not toks:
        return ''
    try:
        from ..caps_registry import BENIGN_CAPS as _BC
    except Exception as _e:                                   # noqa: BLE001
        return '- 能力位现查：注册表读不到（%s）—— 如实报读不到，不许编' % type(_e).__name__
    hits = []
    for _k in _BC:
        _s = str(_k).lower()
        for _t in toks:
            if _t.lower() in _s:
                hits.append(str(_k))
                break
    hits = sorted(set(hits))[:limit]
    tq = '/'.join(toks[:5])
    if hits:
        return '- 能力位现查（关键词 %s）：注册表里命中 **%d 个** —— %s' % (tq, len(hits), '、'.join('`%s`' % h for h in hits))
    return ('- 能力位现查（关键词 %s）：**注册表里 0 命中** ⇒ 如实说「没有这个能力位」，'
            '**不许给它起一个名字**。' % tq)


_HABIT_DOCTRINE = """
## 🤲 两条触手习惯（主人令 2026-10-11 · 硬规矩）
**习惯一 · 逐页双向绑定：** 对**所有项目的每一页**都要用触手做**双向绑定**（页里的键 ↔ 能力位 ↔ 主脑数据，三处对得上），
并逐页扫描确认。**这不是一次性任务，是习惯** —— 新增页面当场绑、绑完当场复读。
**习惯二 · 探测与穿透：** 习惯用触手去**探测与穿透**，让**故障病因、病毒、木马无所遁形** ——
查病因要查到根（病因与疑似病因都不放过，穿透式交叉扫描，不抽样）；发现异常当场记档并说明后果。
**两条都不许只做一次就算完。**
**习惯三 · 看全部再下结论（主人令 2026-10-19 · 硬规矩 · 逐字）：**
> 「**以后不管做什么都要看全部别跟赶着投胎是的就扫一眼就说结论**」
不管查什么，先把相关的**全部**读完再开口 —— 源码、台账、README、配置、实测读数，
一份都不许跳；**只扫一眼 status 输出就下判断 = 违规**。
结论必须能**指到出处**（文件:行 / 命令回执 / 实测读数）；指不到出处，
就写「**我还没读全**」，不许拿印象当结论。
宁可多花几分钟读完，也不图快给错答案；**漏读一份文件导致的错误结论，比慢三分钟严重得多**。
"""


_FUNDAMENTALS_DOCTRINE = """
## 🧱 先底层，再精通（主人令 2026-10-11 · 硬规矩）
**不管什么东西，我都要先从底层了解，再到精通。** 三步：
① **摸底层**：它由什么组成、怎么连、契约是什么、边界在哪（读源码／契约／读数，不看二手说法）；
② **跑最小样本**：用最小的一个例子证明「我真的懂了」（跑通、留读数）；
③ **才谈精通**：优化、组合、规模化。
**跳过①直接上手法 = 脑补，必出错。** 说「我会用」之前，先能说清它的架构与契约。
"""


_VISION_DOCTRINE = """
## 👁 看东西的纪律（主人令 2026-10-11 · 硬规矩）
**脑-手同步不许用传统截图人眼看。** 三层顺序：
① **结构层**（首选）：桌面用 UIA 控件树（domain_index／domain_read／domain_act／domain_type）· 浏览器用 CDP DOM（browser op=native）· 服务用 HTTP/API 读数。**可寻址、无视遮挡、无像素误差。**
② **接地层**（仅兜底）：自绘 UI／Canvas／游戏／无 a11y 窗口才用像素，且必须走**模型 grounding**（把「点这个」映射成坐标），不是人眼瞄。
③ **回读层**：每次动手后**用①再读一次**确认动了没、动对没。
**没有①的尝试记录，不许用②；动完没回读 = 未验证。**
"""


_LOOKUP_DOCTRINE = """
## 📚 查证再答（主人令 2026-10-11 · 硬规矩）
**不管什么问题，只要我答不上来、或知识库里没有 —— 我就去查，不许编、也不许装作不知道。**
五步：① **查本机**（注册表/盘上真身/现读命令）② **查不到就搜网**（web_search／deep_scrape 这类真实通道）
③ **精准抓核心要点**（只留能支撑结论的那几条，带出处）④ **分析清楚**（前后是否自洽、有无反例）
⑤ **再回答**。
**并且要明确表明不能胡说：** 查不到就直说「**这个我不能编，我查到的只有……**」，
把「已查明」与「仍未查明」分开写。**编一个像样的答案，比说『我还没查到』严重得多。**
**禁止**：拿名字表凑答案、拿框架黑话糊过去、把「没查到」包装成「大约/可能」。
"""


def _build_system(custom: str = "", prompt: str = "") -> str:
    """构建完整system prompt — 自我认知强制首位注入。

    2026-10-11：若 `prompt` 像「机器类问题」，**框架先替她现读**并把读数贴在纪律后面 ——
    她就没有「猜」的空间（实测不喂时她把内存编成 148344 MB）。
    """
    live = ""
    if prompt and any(k in prompt for k in _MACHINE_Q):
        try:
            _body = _live_readings()
            if any(k in prompt for k in ("能力位", "有没有", "能不能", "会不会", "支持")):
                _lk = _cap_lookup(prompt)
                if _lk:
                    _body += "\n" + _lk
            live = "\n\n## 【现读读数】（框架替你查的 · 只许用这些，不许改数）\n" + _body + \
                   "\n（读不到的，就如实说读不到；**现查 0 命中就是没有，不许给它起名字**。）"
        except Exception:                                    # noqa: BLE001
            live = ""
    awareness  = _load_awareness()       # Layer1: 强制首注入
    cap_digest = _build_cap_digest()     # Layer2: 实时注册表→精准索引
    base = (
        "你是 GBT小土豆V8 终端AI（terminal-potato），由自由的风开发。自称必须写全名：GBT小土豆V8。" "\n🔴 反编造硬规矩（主人令 2026-10-11）：**能力位名、条目数、配置值一律以现读为准**；" "现读不到就如实说「我不确定，要现读确认」——**不许凭印象给名字、给数字**。"  "编一个不存在的名字，比说不知道更严重（那是假能力/假执行）。"
        + "当前LLM驱动: " + (PROVIDER or "auto") + " | 模型: " + (MODEL or "auto") + "\n\n"
        + "=" * 60 + "\n"
        + "## 🧠 完整自我认知（Agent驱动必经首注入，" + _cap_total_label() + "）\n"
        + "=" * 60 + "\n"
        + awareness + "\n"
        + cap_digest + "\n"
        + "=" * 60 + "\n"
        + "## ⛔ 安全策略（强制注入·不可绕过）\n"
        + "=" * 60 + "\n"
        + _load_security_policy() + "\n"
        + "=" * 60 + "\n"
        + "## 执行铁律\n"
        + _VERIFIED_FACTS
        + _RULE_VS_FACT
        + _MIRROR_DOCTRINE
        + _NONONSENSE_DOCTRINE
        + _HABIT_DOCTRINE
        + _FUNDAMENTALS_DOCTRINE
        + _LOOKUP_DOCTRINE
        + _VISION_DOCTRINE
        + live
    )
    return base + ("\n\n" + custom if custom and custom.strip() else "")
# ══════════════════════════════════════════════════════════════
# 智能搜索引擎 — 关键词触发自动调配能力
# ══════════════════════════════════════════════════════════════
SEARCH_TRIGGERS = [
    # (触发正则, cap名, action, 参数构造函数, 描述)
    # ── 网络搜索类 ────────────────────────────────────
    (r"搜索|查找|查询|最新|新闻|今天|现在|当前|实时|latest|search|find|what is|whats",
     "web_search", "search",
     lambda q: {"query": q},
     "🔍 网络搜索"),
    # ── 网页抓取类 ────────────────────────────────────
    (r"抓取|爬取|获取网页|fetch|scrape|http[s]?://|www\.",
     "deep_scrape", "scrape",
     lambda q: {"url": _extract_url(q), "max_pages": 1},
     "🕷 网页抓取"),
    # ══════════════ 渗透安全全域 25个cap 全接入 ══════════════
    # ── 🔥 OmniScan邻域穿透全量扫描 (最高优先级) ─────────
    (r"全面扫描|综合扫描|深度扫描|全量扫描|一键扫描|全面检测|综合检测|渗透测试.*整站|整站.*扫描|omniscan|病毒扫描|恶意代码检测|CVE检测|邻域穿透|全方位|亿万触手",
     "omni_scan", "scan",
     lambda q: {"target": _extract_url(q) or _extract_domain(q) or q[:80]},
     "🔥 OmniScan全量"),
    # ── 端口/IP侦察 ──────────────────────────────────
    (r"扫描端口|端口扫描|nmap|port.?scan|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|开放端口|服务探测",
     "port_scanner", "scan",
     lambda q: {"target": _extract_ip(q) or _extract_domain(q), "ports": "1-1000"},
     "🔭 端口扫描"),
    # ── 子域名枚举 ───────────────────────────────────
    (r"子域|subdomain|子域名|域名枚举",
     "subdomain_enum", "enum",
     lambda q: {"domain": _extract_domain(q)},
     "🗺 子域枚举"),
    # ── SQL注入检测 ──────────────────────────────────
    (r"sql注入|sqli|sql inject|注入测试|注入漏洞",
     "sqli_tester", "test",
     lambda q: {"url": _extract_url(q) or ""},
     "💉 SQL注入"),
    # ── XSS检测 ──────────────────────────────────────
    (r"xss|跨站|cross.?site|script inject",
     "xss_tester", "test",
     lambda q: {"url": _extract_url(q) or ""},
     "⚡ XSS检测"),
    # ── 系统状态 ──────────────────────────────────────
    (r"系统状态|cpu|内存|磁盘|进程|system status|memory usage|disk",
     "system_status", "check",
     lambda q: {},
     "📊 系统状态"),
    # ── 屏幕感知 ──────────────────────────────────────
    (r"屏幕上|看到|截图|ocr|当前窗口|screen|看看现在",
     "ai_vision", "ocr",
     lambda q: {},
     "👁 屏幕感知"),
    # ── 浏览器操控 ────────────────────────────────────
    (r"打开网页|浏览器|navigate|browser|打开.*网站|访问.*网址",
     "browser_ctrl", "navigate",
     lambda q: {"url": _extract_url(q) or "https://www.baidu.com", "headless": False},
     "🌐 浏览器"),
    # ── DNS查询 ───────────────────────────────────────
    (r"dns|域名解析|ip地址|whois|nslookup",
     "dns_lookup", "lookup",
     lambda q: {"domain": _extract_domain(q) or q[:50]},
     "🔗 DNS查询"),
    # ── 子代理执行 ────────────────────────────────────
    (r"子代理|多步任务|复杂.*任务.*执行|思维导图.*执行|分步.*完成|隔离.*执行",
     "sub_agent_mgr", "spawn",
     lambda q: {"task": q, "auto_run": False},
     "🤖 子代理"),
    # ── SSTI模板注入 ─────────────────────────────────
    (r"ssti|模板注入|服务端模板|jinja2.*注入|twig.*注入|模板.*漏洞|template.*injection",
     "ssti_tester", "test",
     lambda q: {"url": _extract_url(q) or ""},
     "🧩 SSTI模板注入"),
    # ── XXE外部实体 ───────────────────────────────────
    (r"xxe|xml.*注入|外部实体|xml.*实体.*注入|xxe.*测试|doctype.*注入",
     "xxe_tester", "test",
     lambda q: {"url": _extract_url(q) or ""},
     "📋 XXE实体注入"),
    # ── IDOR越权 ─────────────────────────────────────
    (r"idor|越权漏洞|水平越权|垂直越权|对象引用|insecure.*direct.*object",
     "idor_tester", "test",
     lambda q: {"url": _extract_url(q) or ""},
     "🔏 IDOR越权"),
    # ── Payload生成 ───────────────────────────────────
    (r"反弹shell|payload.*生成|载荷生成|马子|木马.*生成|shellcode|攻击.*载荷|webshell.*生成",
     "payload_gen", "reverse_shell",
     lambda q: {"type": "all", "host": _extract_ip(q) or "YOUR_IP"},
     "💣 Payload生成"),
    # ── 提权检测 ──────────────────────────────────────
    (r"提权|privilege.*escalation|suid.*提权|sudo.*提权|本地提权|权限提升|priv.*esc",
     "priv_esc", "quick",
     lambda q: {},
     "⬆ 提权检测"),
    # ── OSINT情报 ─────────────────────────────────────
    (r"osint|情报收集|shodan|fofa|censys|zoomeye|邮件收集|指纹识别|目标侦察|技术栈识别",
     "osint_tool", "search",
     lambda q: {"target": _extract_domain(q) or _extract_ip(q) or q[:50]},
     "🕵 OSINT情报"),
    # ── 密码喷洒 ──────────────────────────────────────
    (r"密码喷洒|password.*spray|喷洒攻击|批量爆破账号|弱密码喷洒|账号.*锁定.*绕过",
     "pass_spray", "wordlist",
     lambda q: {"company": q[:30]},
     "💧 密码喷洒"),
    # ── API安全 ───────────────────────────────────────
    (r"api.*安全|api.*测试|graphql.*安全|接口.*安全|rest.*api.*漏洞|api.*越权|swagger.*安全|openapi.*测试",
     "api_vuln", "fuzz",
     lambda q: {"base_url": _extract_url(q) or q[:80]},
     "🔌 API安全"),
    # ── 代码执行 ──────────────────────────────────────
    (r"运行代码|执行.*python|run.*code|exec.*script",
     "code_exec", "run",
     lambda q: {"code": q, "lang": "python"},
     "⚙️ 代码执行"),
    # ── 数据库查询 ────────────────────────────────────
    (r"查数据库|sql query|select.*from|数据库查询",
     "database", "query",
     lambda q: {"sql": q[:200]},
     "🗃 数据库"),
    # ── 文件操作 ──────────────────────────────────────
    (r"读文件|写文件|read file|write file|文件内容",
     "file_operation", "read",
     lambda q: {"path": _extract_path(q)},
     "📁 文件操作"),
]
# ── 辅助提取函数 ──────────────────────────────────────────────
def _extract_url(text: str) -> str:
    m = re.search(r'https?://[^\s\'"]+', text)
    return m.group() if m else ""
def _extract_ip(text: str) -> str:
    m = re.search(r'\d{1,3}(?:\.\d{1,3}){3}', text)
    return m.group() if m else ""
def _extract_domain(text: str) -> str:
    m = re.search(r'(?:https?://)?([a-zA-Z0-9][-a-zA-Z0-9.]+\.[a-zA-Z]{2,})', text)
    return m.group(1) if m else ""
# ═══════════════════════════════════════════════════════════
#  执行入口 — 路由目标: run(action, params)
# ═══════════════════════════════════════════════════════════
class _HttpError(RuntimeError):
    """带状态码的出站错误。

    ⚠️ 消息格式**一字不改**（`HTTP %s: %s`）—— `tests/test_ai_audit.py` 用
    `assertRaises(RuntimeError)` + 审计行 `status=429` 钉着它。
    新增的只是 `.status` 属性：统一密钥网关靠它做**错误分类**（换不换道）。
    """

    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = int(status or 0)


# 推理模型的「推理吃光预算」标记（agents / NVIDIA 都会踩，见 _call_once）。
# 调用方据此**自适上调 max_tokens 后重试同一家** —— 同一家重试 ≠ 换道。
REASONING_STARVED = "content 为空但 reasoning_content 非空 —— max_tokens 被推理吃光"
_REASONING_ESCALATE_CAP = 8192

def _private_egress_allowed() -> bool:
    """非标准端口 / 内网出站的放行判据：**可信会话** 或 **手上有 `network_private` 时段票**。

    🔴 2026-10-04 修（实测）：本模块出站只传 `allow_private=_policy.is_trusted()`，
    于是"票有了、路没通"——主人发了 `network_private`（作用域原文就是
    「访问本机、内网、保留地址或**非标准端口**」），可本机 Ollama 的 `:11434`
    仍被 net_guard 拦（实测报 `未授权模式只允许标准 HTTP/HTTPS 端口`）。
    ⇒ 判据补上"票在手也算"（只**查**有没有票，不消耗；消耗仍由 run_task 那一道统一做）。
    """
    try:
        from ..security import policy as _policy
        if _policy.is_trusted():
            return True
        from .. import auth_gate as _ag
        st = _ag.status() or {}
        row = (st.get("scopes") or {}).get("network_private") or {}
        return int(row.get("grants_available") or 0) > 0
    except Exception:                                          # noqa: BLE001
        return False


def _safe_json(url, body, headers, timeout, *, audit_provider=None,
               audit_model=None, audit_session_id=None, method="POST"):
    """统一出站口：net_guard 守门 + 应用层 AI 审计（只记元数据，不记内容）。

    R120 实测根因：本模块此前直连 urllib.request.urlopen —— 既绕过 net_guard 的
    SSRF/端口/体积守门，也不落应用层 AI 审计。tests/test_ai_audit.py 早就把
    `_safe_json` 当规格写好，实现却从未存在（调用即 AttributeError）。
    """
    from ..security import net_guard as _ng
    from ..security import ai_audit as _audit
    from ..security import policy as _policy
    provider = audit_provider or PROVIDER or "openai"
    ctx = _audit.begin(provider, url,
                       model=audit_model or (body or {}).get("model"),
                       request_body=body, headers=headers,
                       session_id=audit_session_id)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        response = _ng.safe_request_json(
            url, method=method, headers=headers, body=payload, timeout=timeout,
            max_bytes=8_000_000, allow_private=_private_egress_allowed())
    except Exception as exc:  # noqa: BLE001
        _audit.finish(ctx, ok=False, error=exc)
        raise
    status = int(response.get("status") or 0)
    data = response.get("json")
    if status >= 400 or not isinstance(data, dict):
        _audit.finish(ctx, status=status, ok=False, response_text=response.get("text"))
        raise _HttpError(status, "HTTP %s: %s" % (status, str(response.get("text") or "")[:300]))
    _audit.finish(ctx, status=status, ok=True, response=data)
    return data


# 2026-10-11 (实测 502/超时): 框架 system 13480 字 + max_tokens 2000 = 顶爆端点窗口。
# 治本 = 上下文有界 (见 llm/ring_context.py); 这里是请求体预算闸。
MAX_SYSTEM_CHARS = 12000
MAX_PROMPT_CHARS = 6000


def _call_once(wire, base_url, model, api_key, body, system, prompt, timeout, provider):
    """按协议族发**一次**请求，返回回复文本。

    本函数只管「怎么发」；**重试与换道是调用方的事**（`_safe_json` 只出网一次）。
    """
    system = (system or "")[:MAX_SYSTEM_CHARS]
    prompt = (prompt or "")[:MAX_PROMPT_CHARS]
    if wire == "anthropic":
        # ── Anthropic Claude 原生 Messages API ──
        _url = base_url.rstrip("/") + "/v1/messages"
        _body = {"model": model, "max_tokens": body.get("max_tokens", 2000),
                 "system": system,
                 "messages": [{"role": "user", "content": prompt[:6000]}]}
        _hdrs = {"Content-Type": "application/json", "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"}
        data = _safe_json(_url, _body, _hdrs, timeout,
                          audit_provider=provider or "anthropic", audit_model=model)
        return data["content"][0]["text"]
    if wire == "gemini":
        # ── Google Gemini 原生 generateContent API ──
        _url = (base_url.rstrip("/") + "/models/" + model
                + ":generateContent?key=" + api_key)
        _body = {"contents": [{"role": "user", "parts": [{"text": prompt[:6000]}]}],
                 "systemInstruction": {"parts": [{"text": system}]}}
        data = _safe_json(_url, _body, {"Content-Type": "application/json"}, timeout,
                          audit_provider=provider or "gemini", audit_model=model)
        return data["candidates"][0]["content"]["parts"][0]["text"]
    # ── OpenAI 兼容（agnes/deepseek/kimi/openai/NVIDIA/自定义/本地/免密 Kilo）──
    # 🔴 免密 provider（如 Kilo 免费池）的 api_key 是空串 ⇒ 不发任何 auth header
    #   （Kilo 网关免 key）。有 key 时行为与原来完全一致。
    _hdrs = {"Content-Type": "application/json"}
    if api_key:
        if "abliteration" in base_url:
            _hdrs["x-api-key"] = api_key
        else:
            _hdrs["Authorization"] = "Bearer " + api_key
    _body = dict(body)
    _body["model"] = model
    data = _safe_json(base_url.rstrip("/") + "/chat/completions", _body, _hdrs, timeout,
                      audit_provider=provider or PROVIDER, audit_model=model)
    _msg = (data.get("choices") or [{}])[0].get("message") or {}
    _txt = _msg.get("content")
    if not _txt:
        # 🔴 推理模型的坑（2026-09-27 实弹取证，agnes 与 NVIDIA 都会踩）：
        #    max_tokens 太小会被 reasoning 吃光 ⇒ **HTTP 200 但 content 为空**。
        #    这不是成功。报成 422（参数问题）⇒ 按 I2 **不换道**，
        #    免得把「我们参数写小了」伪装成「模型不行」。
        #    调用方看到 REASONING_STARVED 标记会**自适上调 max_tokens 后重试同一家**
        #    （同一家重试 ≠ 换道，不违反 I1/I2）。
        if _msg.get("reasoning_content"):
            raise _HttpError(422, "HTTP 422: %s（provider=%s）"
                             % (REASONING_STARVED, provider or PROVIDER))
        raise _HttpError(422, "HTTP 422: 上游 200 但 content 为空（provider=%s）"
                              % (provider or PROVIDER))
    return _txt


def run(action=None, **params):
    """LLM网关路由入口 — chat: 推理对话; status: 网关状态"""
    # 本次落点要回写模块级全局（vision_cap 等下游读 BASE_URL/MODEL）——
    # `global` 必须在函数首部声明：本函数前面几处已在读这些名字。
    global PROVIDER, API_KEY, BASE_URL, MODEL
    try:
        # ⛔ 触手独立密钥路由优先于 status 判断：有 purpose 参数时视为 chat 调用
        _purpose = str(params.get("purpose") or "").strip().lower()
        _is_tentacle_call = bool(_purpose)
        # ⛔ 兼容 L4 干跑 handler({}) 传 dict: 提取 action, 空则视为 status(静态, 不调LLM)
        if isinstance(action, dict):
            action = action.get("action") or next(iter(action), None)
        if action in ("status", "health", "list", "info") or (action is None and not _is_tentacle_call):
            _out = {
                "ok": True, "cap": "cloud_llm", "status": "ready",
                "key_chain": [k[0] for k in _KEY_CHAIN],
                "provider": PROVIDER or "auto",
            }
            # 挂上网关读数（选路是不是活的，看这里）。失败不影响 status 本身。
            try:
                from . import key_gateway as _KG
                _out["gateway"] = _KG.run("status")
            except Exception:                            # noqa: BLE001
                _out["gateway"] = None
            return _out
        # 默认 chat: 构建系统提示并转发到LLM
        prompt = params.get("prompt", params.get("q", params.get("message", "")))
        # 🔴 2026-10-12 修（实测根因 · 两道正门打架 · A 案 · Owner 选定）：
        #    事实直答门（fact_gate）与权限直答门（policy_gate）**不认调用方的结构性诉求** ——
        #    只要 fact_gate.classify(prompt) 为真就抢答散文，**哪怕调用方明说要 JSON**。
        #    实测病案：主路语义路由 `semantic_route.choose('本机装了 ComfyUI 没有')` 走
        #    `LLM.ask(..., purpose="semantic_route")`，被 fact_gate 拦成「事实直答」散文，
        #    主路 json.loads 失败 ⇒ 三层重试全撞同一道闸 ⇒ 主路整条失效、永远降级到词表辅路。
        #    ⇒ 口径修正：**直答门只服务"给人看的聊天"，不拦"框架内部的结构化调用"。**
        #    判据：`purpose` 是**框架内部调用方自己声明的用途** —— 命中白名单时跳过两道直答门，
        #    交回给大模型按调用方要求输出（fact_gate 本身一字不改，它的令照旧只对"人问事实"生效）。
        _GATE_SKIP_PURPOSES = {"semantic_route", "route", "brain_exec", "brain_unify",
                               "json", "structured", "extract", "classify"}
        _skip_direct_gate = _purpose in _GATE_SKIP_PURPOSES
        # 🔴 2026-10-11 事实直答门（主人令「拿实质性证据说话」）：机器事实**不过语言模型** ——
        #   实证：三次重训治不住编事实、十轮提示词只换失败模式；而「门的读数不许转述」是本仓本义。
        if not _skip_direct_gate:
            try:
                from . import fact_gate as _fg
                if _fg.classify(prompt):
                    _fa = _fg.answer(prompt)
                    if _fa.get('ok'):
                        return {'ok': True, 'provider': 'framework/fact_gate', 'model': 'fact_gate（代码直答）',
                                'reply': _fa['answer'], 'mode': _fa.get('mode'),
                                'facts': _fa.get('facts'), 'sources': _fa.get('sources'),
                                'auto_switched': False}
            except Exception:                            # noqa: BLE001
                pass
        # 🔴 2026-10-11 权限/付款直答门（fact_gate 的同族）：能不能做／要不要授权**也是事实**。
        #   实证病根：终考里「买 4090」不是机器事实 ⇒ 没过 fact_gate ⇒ 她又编市场数据。
        if not _skip_direct_gate:
            try:
                from . import policy_gate as _pg
                if _pg.classify(prompt):
                    _pa = _pg.answer(prompt)
                    if _pa.get('ok'):
                        return {'ok': True, 'provider': 'framework/policy_gate', 'model': 'policy_gate（代码直答）',
                                'reply': _pa['answer'], 'mode': _pa.get('mode'),
                                'facts': _pa.get('facts'), 'sources': _pa.get('sources'),
                                'auto_switched': False}
            except Exception:                            # noqa: BLE001
                pass
        # 2026-10-11：**把 prompt 传进去** —— 机器类问题 ⇒ 框架先替她现读并贴进 system
        system = _build_system(custom=params.get("system", ""), prompt=prompt)
        _want_max_tokens = int(params.get("max_tokens", 2000))
        body = {
            "model": params.get("model", MODEL or "deepseek-flash"),
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt[:6000]}],
            "temperature": params.get("temperature", 0.7),
            "max_tokens": _want_max_tokens,
        }
        # ══════════════════════════════════════════════════════════════
        # 选路：向统一密钥网关要「本次该按什么顺序试」—— **每次调用现算**
        # ══════════════════════════════════════════════════════════════
        # 🔴 血账（这就是「一直失灵」的机械根因）：
        #    旧实现在**模块导入时**跑一次 for-loop，找到第一个有 key 的 provider
        #    就 `break`，把 PROVIDER/API_KEY/BASE_URL/MODEL 四个模块级全局**定型**，
        #    此后整个进程生命周期不再变；而且 HTTP 4xx/5xx 只被外层
        #    `except Exception` 吞成 `{"ok": False}` —— **不重试、不换道**。
        #    ⇒ 额度耗尽(402)/限流(429)/密钥失效(401) 任一发生 = **硬断连**。
        #    现在改为「每次现算 + 按错误分类处置」：
        #      能换道的换道（402/429/401/404），不能换道的如实报错（400/422，I2），
        #      全不可用时 fail-closed（不瞎挑、不静默降级）。
        from . import key_gateway as _KG
        # ── 触手维度密钥路由（2026-10-03）：按 purpose 选子 profile ──────────
        # 匹配到触手 profile → 直接使用该 profile 的 key 调 agnes，绕过 key_gateway
        # （_purpose 已在函数上方 status 判断前计算，此处复用）
        _matched_prof = None
        # 🔴 2026-10-04 修（实测）：**显式点名车道时，不许「触手 profile 捷径」抢路**。
        #    症状：设 `GBT_LLM_PROVIDER=gbt-local` 仍落到 agnes —— 这条按 purpose 匹配的捷径先命中
        #    （purpose 命中某触手 profile ⇒ 直接拿该 profile 的 key 调 agnes），**绕过了 plan(prefer=…)**。
        #    ⇒ 点名优先，捷径让路（无显式点名时行为一字不变）。
        _explicit_lane = str(params.get("provider") or os.environ.get("GBT_LLM_PROVIDER") or "").strip()
        for _kw, _prof in ([] if _explicit_lane else _PURPOSE_ROUTING_MAP.items()):
            if _kw in _purpose:
                _matched_prof = _prof
                break
        if _matched_prof:
            _tentacle_key = os.environ.get(f"{_matched_prof.upper()}_API_KEY") or ""
            if not _tentacle_key:
                try:
                    from ..deepseek_key import _unprotect_dpapi as _dk_unprotect
                    from pathlib import Path as _P
                    _dpapi_path = _P(__file__).parent.parent / "store" / "secrets" / f"{_matched_prof}_api.dpapi"
                    if _dpapi_path.exists():
                        _tentacle_key = _dk_unprotect(_dpapi_path.read_bytes(), profile=_matched_prof).decode().strip()
                except Exception:
                    pass
            if _tentacle_key:
                # 直接用触手独立 key 调 agnes，不走 key_gateway 选路
                # ⛔ 2026-10-03 轮询轮换：429/422 限流 → 自动试下一个触手 key
                _timeout_t = int(params.get("timeout", 60))
                _tried_before = []
                _last_err = None
                # 2026-10-04 修（24h 审查实证）：候选集 = **全部触手 profile**，命中者排第一。
                #   原条件 `_kw2 in _purpose or _prof2 == _matched_prof` 与选路同源 ⇒
                #   purpose 只含单个关键词时，候选恒为该 profile 自己 ⇒ 429/422「换下一个」
                #   永远只有一轮、等于没接（全仓唯一命中路由表的 purpose=devour.consult 即此形态）。
                #   现在按路由表序全收（没配 key 的会在下面循环里带原因跳过），
                #   顺序：命中 profile 优先 → 其余按表序补位（确定性，不瞎挑）。
                _all_tentacles = [_matched_prof] + [
                    _p2 for _p2 in _PURPOSE_ROUTING_MAP.values() if _p2 != _matched_prof
                ]

                for _try_prof in _all_tentacles:
                    _try_key = os.environ.get(f"{_try_prof.upper()}_API_KEY") or ""
                    _no_key_why = ""
                    if not _try_key:
                        try:
                            from ..deepseek_key import _unprotect_dpapi as _dk_unprotect2
                            from pathlib import Path as _P2
                            _dp2 = _P2(__file__).parent.parent / "store" / "secrets" / f"{_try_prof}_api.dpapi"
                            if _dp2.exists():
                                _try_key = _dk_unprotect2(_dp2.read_bytes(), profile=_try_prof).decode().strip()
                            else:
                                _no_key_why = "dpapi 文件不存在"
                        except Exception as _e2:
                            # 2026-10-04：原为静默 pass —— 失败要带原因（同仓「失败必带原因」判据）
                            _no_key_why = f"{type(_e2).__name__}: {str(_e2)[:80]}"
                    if not _try_key:
                        _tried_before.append({"profile": _try_prof, "reason": "no_key",
                                              "why": _no_key_why or "env 与 dpapi 均未配"})
                        continue
                    try:
                        _rt = _call_once(
                            "openai_compatible",
                            "https://apihub.agnes-ai.com/v1",
                            "agnes-2.5-flash",
                            _try_key,
                            body, system, prompt,
                            _timeout_t,
                            "agnes",
                        )
                        return {
                            "ok": True, "reply": _rt, "provider": "agnes",
                            "model": "agnes-2.5-flash",
                            "key_masked": _try_key[:8] + "****",
                            "brand": _KG.BRAND_TAG,
                            "tentacle_profile": _try_prof,
                            "auto_switched": (_try_prof != _matched_prof),
                            "tried_before": _tried_before,
                        }
                    except _HttpError as _e:
                        _status = getattr(_e, 'status', 0)
                        _err_str = str(_e)
                        _tried_before.append({"profile": _try_prof, "status": _status, "error": _err_str[:200]})
                        # REASONING_STARVED 是客户端 max_tokens 太小，换 key 也救不了 → 立即抛
                        if REASONING_STARVED in _err_str:
                            raise
                        # 429(限流) / 服务端 422(配额耗尽) → 轮询下一个触手 key
                        if _status in (429, 422):
                            _last_err = _e
                            continue
                        raise  # 其它错误（401/500等）→ 立即报错
                # 所有触手 key 都失败
                if _last_err:
                    raise _last_err
                raise _HttpError(503, "所有触手 key 均不可用: " + json.dumps(_tried_before, ensure_ascii=False))
        # 无触手 key 或无匹配：走原有 key_gateway 选路
        _prefer = str(params.get("provider") or os.environ.get("GBT_LLM_PROVIDER") or "")
        _pl = _KG.plan(need_tokens=int(params.get("need_tokens", 0) or 0), prefer=_prefer)
        if not _pl.get("ok"):
            return {"ok": False, "error": _pl.get("error"), "fail_closed": True,
                    "brand": _KG.BRAND_TAG, "candidates": _pl.get("candidates"),
                    "how_to_fix": _pl.get("how_to_fix"),
                    "hint": "补密钥：deepseek_key set --profile <名>；或 op=reset 清运行态"}
        _order = [o["provider"] for o in (_pl.get("order") or []) if o.get("alive")]
        # 🔴 2026-10-11（主人令「不许拿托管模型冒充」）：**显式点名时不许静默换道**。
        #    点名 potato 就只走 potato；她不可用 ⇒ 如实报错，**绝不让 agnes 顶着她的名字回答**。
        if _prefer:
            if _prefer in _order:
                _order = [_prefer]
            else:
                return {"ok": False, "fail_closed": True,
                        "error": ("点名车道 %r 不可用（未活/未配/已禁用）—— 显式点名不换道，如实报；"
                                  "换道由**框架自己**执行 op=reset 清运行态（不要求用户改环境变量）") % _prefer,
                        "brand": _KG.BRAND_TAG, "prefer": _prefer}
        _timeout = int(params.get("timeout", 60))
        _max_retries = int(params.get("retries", 2))  # ⛔ 生产打磨: 瞬时错误重试2次+退避
        _tried = []
        for _prov in _order:
            _mat = _KG.materialize(_prov)
            if not _mat.get("ok"):
                _tried.append({"provider": _prov, "skipped": _mat.get("error")})
                continue
            # 推理模型要够大的 max_tokens，否则 content 会被 reasoning 吃光
            # （HTTP 200 也算失败）——网关在声明层给了 min_max_tokens 下限。
            _body = dict(body)
            _body["max_tokens"] = max(_want_max_tokens,
                                      int(_mat.get("min_max_tokens", 0) or 0))
            # 让下游（vision_cap 等读 BASE_URL/MODEL 的地方）看到**本次真实落点**
            PROVIDER, API_KEY, BASE_URL, MODEL = (_prov, _mat["key"],
                                                  _mat["url"], _mat["model"])
            _err, _st, _d = "", None, {}
            # 2026-10-11：车道自带**超时**与**重试预算**（Serverless 冷启动要从卷里加载 15G：
            #   timeout_s=300 · retries=6）—— materialize() 只回写死字段，故从车道表直读。
            _lane_spec = (_KG._BY_NAME.get(_prov) or {}) if hasattr(_KG, "_BY_NAME") else {}
            _lane_timeout = max(_timeout, int(_lane_spec.get("timeout_s") or 0))
            _lane_retries = max(_max_retries, int(_lane_spec.get("retries") or 0))
            for _attempt in range(_lane_retries + 1):
                try:
                    _reply = _call_once(_mat["wire"], _mat["url"], _mat["model"],
                                        _mat["key"], _body, system, prompt,
                                        _lane_timeout, _prov)
                    _KG.note_result(_prov, ok=True)
                    return {"ok": True, "reply": _reply, "provider": _prov,
                            "model": _mat["model"], "key_masked": _mat["masked"],
                            "brand": _KG.BRAND_TAG,
                            "auto_switched": bool(_pl.get("auto_switched")),
                            "switched_from": _pl.get("switched_from"),
                            "tried_before": [t["provider"] for t in _tried]}
                except Exception as _e:                  # noqa: BLE001
                    _err = str(_e)[:300]
                    _st = getattr(_e, "status", None)
                    # 🔴 推理模型把预算吃光 ⇒ **同一家自适上调 max_tokens 后重试**。
                    #    同一家重试 ≠ 换道（不违反 I1/I2），而且这是唯一能修好的办法：
                    #    换道只会把这个模型能答的问题推给别人。
                    # 🔴 2026-10-11（实测教训）：Serverless（闲时缩 0）在冷启动/扩缩期间网关会返
                    #    **502/503/504**。这不是"这条道坏了"，是"它正在起来"——原逻辑当场判死
                    #    ⇒ 她那条道被永久禁用。⇒ 5xx 一律**退避重试**，不记车道失败。
                    # 冷启动要耐心：车道可声明 retries（她要从网络卷加载 15G）——用车道预算，10s 起退避
                    if _st in (502, 503, 504) and _attempt < _lane_retries:
                        time.sleep(10 * (_attempt + 1))
                        continue
                    if REASONING_STARVED in _err and _attempt < _max_retries:
                        _new = min(max(_body["max_tokens"] * 4, 512),
                                   _REASONING_ESCALATE_CAP)
                        if _new > _body["max_tokens"]:
                            print("[key_gateway] 推理吃光预算：%s max_tokens %d → %d 后重试"
                                  % (_prov, _body["max_tokens"], _new), file=sys.stderr)
                            _body["max_tokens"] = _new
                            continue
                    _d = _KG.note_result(_prov, ok=False, status=_st, error=_err)
                    # 决策拆两维（血账：早先把这两件事挤在一个 `failover` 里，
                    # 结果 transient 在 `not failover` 处**立即 return**，
                    # 重试分支成死代码 ⇒ 一次网络抖动 = 硬断连）：
                    #   ① 同家再试一次？  ② 试不动了要不要往下走？
                    if not _d.get("retry_same") and not _d.get("escalate"):
                        # bad_request / unknown ⇒ **硬停**：我们自己错了，换谁都没用
                        return {"ok": False, "error": _err, "provider": _prov,
                                "err_class": _d.get("err_class"), "failover": False,
                                "why_no_failover": _d.get("action"),
                                "brand": _KG.BRAND_TAG}
                    if _d.get("retry_same") and _attempt < _max_retries:
                        time.sleep(1 + _attempt * 2)     # 退避: 1s/3s
                        continue
                    break                                # 本家到此为止 → 下一家
            _tried.append({"provider": _prov, "err_class": (_d or {}).get("err_class"),
                           "status": _st, "error": _err})
        return {"ok": False, "fail_closed": True, "brand": _KG.BRAND_TAG,
                "error": "全部 %d 条通道都试过且都失败 —— 如实报错，不静默降级"
                         % len(_order),
                "tried": _tried,
                "how_to_fix": "补密钥 / op=reset 清运行态 / 等冷却到期"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}
if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "status"
    params_str = sys.argv[2] if len(sys.argv) > 2 else "{}"
    try:
        params = json.loads(params_str)
    except Exception:
        params = {}
    result = run(action, **params)
    print(json.dumps(result, ensure_ascii=False, default=str))
def do_status(params=None):
    return {"ok": True, "cap": "cloud_llm", "status": "ready"}
HANDLERS = {
    
    "chat": run,
    # ⛔ status 必须走静态分支: handler({}) → run("status") — 否则干跑误触发LLM(7s超时)
    "status": lambda p: run("status", **(p if isinstance(p, dict) else {})),
}
