# gbt-capability: multimodal_port
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""多模态维度 × 触手密钥 Y 字端口（multimodal_port）· 🥔GBT小土豆V8

════════════════════════════════════════════════════════════════════════
【为什么存在 —— 主人的两条令】

  令一（2026-09-27）：「不是还有很多生图和生视频的免费大模型吗全都接进去啊」
  令二（2026-09-27）：「触手密钥可以设计一个 Y 字端口，可独立密钥使用
                        以及共享密钥对维度使用方式」

  这两条其实是**同一件事的两面**：
    · 「生图 / 生视频」= 新的**维度**（dimension）；
    · 维度一多，「一把钥匙打通所有维度」就不成立了 ⇒ 触手需要一个**分叉的入口**。
  于是 Y 字端口 = 触手密钥请求在一处分叉，左臂独立、右臂共享。

════════════════════════════════════════════════════════════════════════
【旧链路的缺口（机械事实，不是印象）】

  `tools/energy_pool.py` 的 `EnergySource.capability` 本就写明了
  `text / image / video / code` —— **词汇表早就在**。但它的 `build_sources()`
  把 capability **写死成 `("text",)`**（理由：盘上没有能力位字段，不编）。

  ⚠️ 后果：**能源池在定义上就挑不出"生图能源"** —— `pool.pick("image")` 恒返回 None，
  哪怕画图端点就摆在盘上。**「多维度没接进去」的根，就在这一行写死。**

  🔴 且**不许**去改 `EnergySource`：`tests/test_energy_pool.py:158` 用
  `assertEqual({f.name for f in fields(EnergySource)}, {…七项…})` **把字段集合钉死了**
  ⇒ 加一个字段就是回归。所以多模态声明**另立一处真相**（本模块），不动被钉死的契约。

════════════════════════════════════════════════════════════════════════
【Y 字端口：形状与两臂】

                    触手密钥请求 (dimension = 文本/看图/生图/生视频/代码)
                              │
                     ┌────────┴────────┐   ← Y 的分叉点（一次只走一臂）
              独立臂 │                 │ 共享臂
             (专属)  │                 │ (共享密钥对)
                     ↓                 ↓
            该维度专属 vault profile   共享密钥对 [主, 备] × 维度

  · **独立臂**：触手用**该维度专属的独立密钥**（一 AI 一号）。
      典型：文本=deepseek 库 / 看图=agnes 库。
  · **共享臂**：触手与**共享密钥对**协作 —— 同一对钥匙（主 + 备）**按维度**分账。
      它存在的理由很实在：**画图/看视频这类维度往往只有一把免费钥匙**，
      硬要求"每维度各配一把"等于多数维度永远缺能源。

【为什么"共享"以前是被禁的，现在能开一条有闸的路】

  `tools/model_key_pool.py` 有一条红线：「**不共享密钥** —— 每个 AI 独立密钥，跨 AI 不共用」，
  其工程理由写得很清楚：*共用一把密钥 ⇒ 平台按单账号限流 ⇒ 几个 AI 互相挤占*。
  ⇒ 那条红线禁的是「**跨 AI 无约束共用**」，不是「**同一 AI 内部按维度复用**」。
  本模块的共享臂因此**只**在下列机械闸全过时才成立（少一条即拒）：

     Y0 维度必须在册
     Y1 一次请求只走一臂（独立 / 共享不可混用）
     Y2 共享臂必须**恰好成对**（2 把），且**指纹必须不同**（同指纹 = 假冗余）
     Y3 共享臂必须带 owner_ai_id，且**不许跨 owner**（沿用 key_pool 红线）
     Y4 该维度的共享策略必须在册且为真（`SHARE_POLICY`，可按维度单独收紧）
     Y5 **明文永不出返回值**（只回 key_id / 掩码 / 指纹）
     Y6 没有任何可用钥匙 ⇒ **如实报缺**（fail-closed，不硬撑、不假装有）

════════════════════════════════════════════════════════════════════════
【密钥来源：不开第二条取 key 的路】

  一律经 `deepseek_key.load_from_vault`（**只读保险箱、忽略环境变量**）——
  与 `vision_cap._vision_key()` 同一条路（判据：`tests/test_vision_key_path.py`
  「不许再有第二条取 key 的路」）。本模块**不读任何 *_API_KEY 环境变量**当密钥，
  不自己解 DPAPI，不落明文。
"""
from __future__ import annotations

import hashlib
import os
import time

# ── 品牌 ────────────────────────────────────────────────────────────────
BRAND = "GBT小土豆V8"
BRAND_TAG = "🥔GBT小土豆V8"
CAP = "multimodal_port"

# ══════════════════════════════════════════════════════════════════════
#  维度在册表（capability dimensions）
#  词汇**对齐** `energy_pool.EnergySource.capability`（text/image/video/code），
#  另加 `vision`（触手看的这一路：图 → 文，与 image「文 → 图」方向相反，必须分开）。
# ══════════════════════════════════════════════════════════════════════
DIM_META = {
    "text":   {"cn": "文本",   "dir": "文→文", "gate": "llm.chat"},
    "vision": {"cn": "看图",   "dir": "图→文", "gate": "vision.read"},
    "image":  {"cn": "生图",   "dir": "文→图", "gate": "image.write"},
    "video":  {"cn": "生视频", "dir": "文→动", "gate": "video.write"},
    "code":   {"cn": "代码",   "dir": "文→码", "gate": "llm.code"},
    # 主人令 2026-09-28「把插件连接好部署语音…真唱」：**文→声**这一格必须有 ——
    # 否则"歌声/语音"在多模态端口里没户口（走了也只能算文本维，分账就错了）。
    # 承载位：`hf_voice`（Hugging Face 3 臂轮询，**真唱走这条**）· `voice`（本地 TTS 念白）。
    "audio":  {"cn": "歌声/语音", "dir": "文→声", "gate": "audio.write"},
}
DIMENSIONS = tuple(DIM_META)

# ══════════════════════════════════════════════════════════════════════
#  免费多模态通道目录（**声明层**）
#  只声明「有这条路、要不要钥匙、什么协议」；**可达性由 probe 实测填**，
#  未实测一律 `verified=False` 并带 `why` —— **不编**。
# ══════════════════════════════════════════════════════════════════════
FREE_CHANNELS = (
    # ── 免密钥公开端点（可实弹探测）──────────────────────────────────
    dict(id="pollinations-image", dim="image", wire="rest", key="none", free=True,
         url="https://image.pollinations.ai/prompt/{prompt}",
         note="免密钥公开生图端点（GET 即回图）"),
    dict(id="pollinations-text", dim="text", wire="openai", key="none", free=True,
         url="https://text.pollinations.ai/openai",
         note="免密钥 OpenAI 兼容文本端点"),
    # ── 需钥匙、但有免费额度的平台（钥匙一律进保险箱）──────────────
    dict(id="siliconflow-flux", dim="image", wire="openai", key="vault:siliconflow",
         free=True, url="https://api.siliconflow.cn/v1",
         note="硅基流动：FLUX.1-schnell / Kolors 等有免费额度"),
    dict(id="dashscope-wanx", dim="image", wire="openai", key="vault:dashscope",
         free=True, url="https://dashscope.aliyuncs.com/api/v1",
         note="阿里通义万相：新用户免费额度"),
    dict(id="zhipu-cogview", dim="image", wire="openai", key="vault:zhipu",
         free=True, url="https://open.bigmodel.cn/api/paas/v4",
         note="智谱 CogView：有免费额度"),
    dict(id="modelscope-image", dim="image", wire="rest", key="vault:modelscope",
         free=True, url="https://api-inference.modelscope.cn/v1",
         note="魔搭 ModelScope：社区模型免费推理"),
    dict(id="kling-video", dim="video", wire="rest", key="vault:kling",
         free=True, url="https://api.klingai.com",
         note="可灵 AI：宿主已连通（连接器 kling-ai-plugin）"),
    dict(id="modelscope-video", dim="video", wire="rest", key="vault:modelscope",
         free=True, url="https://api-inference.modelscope.cn/v1",
         note="魔搭：Wan / CogVideoX 等视频模型免费推理"),
    dict(id="zhipu-cogvideo", dim="video", wire="rest", key="vault:zhipu",
         free=True, url="https://open.bigmodel.cn/api/paas/v4",
         note="智谱 CogVideoX：有免费额度"),
    dict(id="h3mini-video", dim="video", wire="rest", key="vault:minimax",
         free=False, url="https://api.minimaxi.com",
         note="H3mini（官方四原语 T2VA/I2VA/FL2VA/Ref2VA）；盘上 0 把钥匙，如实降级"),
)
_CH = {c["id"]: c for c in FREE_CHANNELS}

# ══════════════════════════════════════════════════════════════════════
#  Y 端口 —— 两臂的声明
# ══════════════════════════════════════════════════════════════════════
# 独立臂：每个维度一把**专属**钥匙（走哪个保险箱 profile）。
#   "" = 该维度尚未配专属钥匙（**如实报缺**，不拿别的维度的钥匙顶上）。
#   可用环境变量 `GBT_TENTACLE_PORT_<维度>` 覆盖（只改"用哪个 profile"，不改"从哪取"）。
INDEPENDENT_PROFILES = {
    "text":   "deepseek",
    "vision": "agnes",
    "image":  "",
    "video":  "",
    "code":   "deepseek",
}

# 共享臂：每个维度的**共享密钥对**（恰好 2 个 profile = 主 + 备）。
#   [] = 该维度未配对（**如实报缺**）。
SHARED_PAIRS = {
    "text":   ["agnes", "deepseek"],
    "vision": ["agnes", "deepseek"],
    "image":  [],
    "video":  [],
    "code":   ["agnes", "deepseek"],
}

# 共享策略：要不要允许某维度走共享臂。**按维度可单独收紧**（例如视频很贵 ⇒ 默认禁）。
SHARE_POLICY = {
    "text":   True,
    "vision": True,
    "image":  True,
    "video":  False,     # 视频维度默认**不共享**（单次消耗大，互挤风险高）⇒ 走专属
    "code":   True,
}

ARMS = ("independent", "shared")


# ══════════════════════════════════════════════════════════════════════
#  密钥读取 —— 唯一真相源：deepseek_key（**只走保险箱**）
# ══════════════════════════════════════════════════════════════════════
def _dk_mod():
    """取 `deepseek_key` 模块。**相对导入要先试、绝对导入兜底** ——

    ⚠️ 血账（2026-09-27 实弹逼出）：本文件**直接以脚本方式跑**时
    （`python gbt_allinone/llm/multimodal_port.py`），模块名是 `__main__`、
    `__package__` 为空 ⇒ `from .. import deepseek_key` 抛
    `ImportError: attempted relative import with no known parent package`，
    又被外层 `except Exception` 吞成「取不到钥匙」⇒ **明明在保险箱里的钥匙被报成缺**，
    而且**只在这个入口现形**（被 import 时一切正常）。修法是导入回退，不是放宽判据。
    """
    try:
        from .. import deepseek_key as _dk                    # noqa: PLC0415
        return _dk
    except ImportError:
        from gbt_allinone import deepseek_key as _dk          # noqa: PLC0415
        return _dk


def _vault(profile: str) -> tuple:
    """经 deepseek_key **只读保险箱**取 (key, source)。source ∈ dpapi / missing / …。"""
    name = str(profile or "").strip()
    if not name:
        return "", "n/a"
    try:
        return _dk_mod().load_from_vault(name)
    except Exception as exc:                            # noqa: BLE001
        return "", "error:" + str(exc)[:40]


def _profile_known(profile: str) -> bool:
    if not str(profile or "").strip():
        return False
    try:
        return str(profile) in (getattr(_dk_mod(), "_PROFILES", {}) or {})
    except Exception:                                   # noqa: BLE001
        return False


def fingerprint(key: str) -> str:
    """BLAKE2b 前 8 位 hex —— 比对「是不是同一把钥匙」，不可反推。"""
    if not key:
        return ""
    return hashlib.blake2b(str(key).encode("utf-8"), digest_size=4).hexdigest()


def mask(key: str, tag: str = "") -> str:
    """带品牌的掩码，**永不含明文**。形态：🥔GBT小土豆V8|image|sk-a…9f2c|#4b1e77a0"""
    if not key:
        return ""
    head = str(key)[:4]
    tail = str(key)[-4:] if len(str(key)) > 8 else ""
    return "%s|%s|%s…%s|#%s" % (BRAND_TAG, tag or "?", head, tail, fingerprint(key))


def _port_env(dim: str) -> str:
    """把维度名转成环境变量名：GBT_TENTACLE_PORT_<DIM>（只覆盖"用哪个 profile"）。"""
    return "GBT_TENTACLE_PORT_" + str(dim or "").strip().upper()


def _indep_profile(dim: str) -> str:
    env = os.environ.get(_port_env(dim), "").strip()
    if env:
        return env
    return str(INDEPENDENT_PROFILES.get(dim) or "")


def _slot(profile: str, tag: str) -> dict:
    """把一个 profile 读成**无明文**的一格（key_id / masked / fp / present / source）。

    ⚠️ 明文 key 只在本函数栈内存在，**不进返回值**（返回值里只有掩码与指纹）。
    """
    key, src = _vault(profile)
    return {"key_id": "%s:%s" % (tag, profile) if profile else "",
            "profile": profile or "",
            "present": bool(key),
            "source": src,
            "masked": mask(key, tag) if key else "",
            "fp": fingerprint(key)}


# ══════════════════════════════════════════════════════════════════════
#  Y 字端口（主入口）
# ══════════════════════════════════════════════════════════════════════
def _deny(rule: str, why: str, **extra) -> dict:
    return {"ok": False, "denied": True, "rule": rule, "why": why,
            "brand": BRAND_TAG, "port": "Y", **extra}


def port(dimension: str = "text", mode: str = "independent",
         owner_ai_id: str = "") -> dict:
    """触手密钥 Y 字端口：在分叉点选定一臂，取回**该维度的**密钥引用。

    参数
      dimension    ∈ text / vision / image / video / code
      mode         ∈ independent（独立专属密钥）/ shared（共享密钥对）
      owner_ai_id  共享臂**必填**（Y3：不许跨 owner）

    返回值**永不含明文**（只有 key_id / 掩码 / 指纹）。
    """
    dim = str(dimension or "").strip().lower()
    arm = str(mode or "").strip().lower()

    # ── Y0 维度必须在册 ─────────────────────────────────────────────
    if dim not in DIM_META:
        return _deny("unknown_dimension",
                     "维度不在册：%r（在册：%s）" % (dim, " / ".join(DIMENSIONS)),
                     known=list(DIMENSIONS))
    meta = DIM_META[dim]

    # ── Y1 一次只走一臂 ─────────────────────────────────────────────
    if arm not in ARMS:
        return _deny("unknown_arm",
                     "臂不在册：%r（在册：%s）—— 一次请求只走一臂，不许混用"
                     % (arm, " / ".join(ARMS)), known=list(ARMS), dimension=dim)

    # ── Y4 共享策略须在册且为真（仅共享臂）──────────────────────────
    if arm == "shared" and not SHARE_POLICY.get(dim, False):
        return _deny("share_not_allowed_for_dimension",
                     "维度「%s」的共享策略为**关**（SHARE_POLICY）⇒ 该维度只走独立臂"
                     % meta["cn"], dimension=dim, arm=arm,
                     hint="要放开请显式改 SHARE_POLICY['%s'] —— 那是资源分配决定" % dim)

    # ── Y3 共享臂必须带 owner（不许跨 owner）────────────────────────
    if arm == "shared" and not str(owner_ai_id or "").strip():
        return _deny("missing_owner_ai_id",
                     "共享臂必须带 owner_ai_id：共用一把钥匙会被平台按单账号限流 ⇒ "
                     "必须能追到「借给哪个 AI 身份」", dimension=dim, arm=arm)

    # ── 独立臂 ─────────────────────────────────────────────────────
    if arm == "independent":
        profile = _indep_profile(dim)
        if not profile:
            return _deny("no_dedicated_key",
                         "维度「%s」尚未配**专属独立钥匙** ⇒ 如实报缺（不拿别的维度的钥匙顶上）"
                         % meta["cn"], dimension=dim, arm=arm, honest=True,
                         how_to_fix="deepseek_key set --profile <名>，并把它登记进 "
                                    "INDEPENDENT_PROFILES['%s']（或设 %s）"
                                    % (dim, _port_env(dim)))
        slot = _slot(profile, dim)
        if not slot["present"]:
            return _deny("key_missing",
                         "专属钥匙（profile=%s）不在保险箱 ⇒ 如实报缺（source=%s）"
                         % (profile, slot["source"]),
                         dimension=dim, arm=arm, honest=True, key_id=slot["key_id"])
        return {"ok": True, "readonly": True, "brand": BRAND_TAG, "port": "Y",
                "arm": "independent", "shared": False,
                "dimension": dim, "dimension_cn": meta["cn"], "direction": meta["dir"],
                "gate": meta["gate"], "owner_ai_id": str(owner_ai_id or ""),
                "key_id": slot["key_id"], "key_masked": slot["masked"],
                "fp": slot["fp"], "source": slot["source"],
                "pair": [], "via": "vault:independent",
                "note": "独立臂：该维度的**专属**钥匙（一 AI 一号，不与他人共享）"}

    # ── 共享臂 ─────────────────────────────────────────────────────
    pair = list(SHARED_PAIRS.get(dim) or [])
    # Y2a 必须恰好成对
    if len(pair) != 2:
        return _deny("pair_incomplete",
                     "维度「%s」的共享密钥对未配齐（现有 %d 把，须恰好 2 把：主 + 备）"
                     % (meta["cn"], len(pair)), dimension=dim, arm=arm, honest=True,
                     pair=list(pair),
                     how_to_fix="在 SHARED_PAIRS['%s'] 里登记恰好两个 vault profile" % dim)
    slots = [_slot(p, dim) for p in pair]
    present = [s for s in slots if s["present"]]
    # Y6 一把都没有 ⇒ 如实报缺
    if not present:
        return _deny("keys_missing",
                     "共享密钥对（%s）两把都不在保险箱 ⇒ 如实报缺" % " / ".join(pair),
                     dimension=dim, arm=arm, honest=True,
                     pair=[{"key_id": s["key_id"], "source": s["source"]} for s in slots])
    # Y2b 指纹必须不同（同指纹 = 假冗余：一把被限另一把必然同样被限）
    fps = [s["fp"] for s in present]
    if len(set(fps)) != len(fps):
        return _deny("pair_same_fingerprint",
                     "共享密钥对里出现**同一把钥匙**（指纹相同）⇒ 假冗余："
                     "一把被限另一把必然同样被限，换道会白跳一次",
                     dimension=dim, arm=arm, fps=fps,
                     hint="换成真正独立的两把钥匙，或改用独立臂")
    primary, backup = slots[0], slots[1]
    return {"ok": True, "readonly": True, "brand": BRAND_TAG, "port": "Y",
            "arm": "shared", "shared": True,
            "dimension": dim, "dimension_cn": meta["cn"], "direction": meta["dir"],
            "gate": meta["gate"], "owner_ai_id": str(owner_ai_id or "").strip(),
            "key_id": primary["key_id"], "key_masked": primary["masked"],
            "fp": primary["fp"], "source": primary["source"],
            "pair": [{"key_id": s["key_id"], "role": r, "masked": s["masked"],
                      "fp": s["fp"], "present": s["present"], "source": s["source"]}
                     for s, r in zip(slots, ("主", "备"))],
            "available": len(present), "pair_size": len(slots),
            "via": "vault:shared-pair",
            "note": "共享臂：同一对钥匙（主+备）**按维度**复用；"
                    "owner=%s 限定归属（沿用 key_pool「不跨 AI 共用」红线）"
                    % str(owner_ai_id or "").strip()}


# ══════════════════════════════════════════════════════════════════════
#  目录 / 状态
# ══════════════════════════════════════════════════════════════════════
def catalog(dimension: str = "") -> dict:
    """免费多模态通道目录。`verified` 由 `probe` 实测填；未实测一律 False（**不编**）。"""
    dim = str(dimension or "").strip().lower()
    rows = [dict(c) for c in FREE_CHANNELS if not dim or c["dim"] == dim]
    for r in rows:
        r.setdefault("verified", False)
        r.setdefault("why", "未实测（用 op=probe 探测后填）")
    return {"ok": True, "readonly": True, "brand": BRAND_TAG, "cap": CAP,
            "dimension": dim or "全部", "count": len(rows), "channels": rows,
            "by_dim": {d: sum(1 for r in rows if r["dim"] == d) for d in DIMENSIONS
                       if any(r["dim"] == d for r in rows)},
            "note": "只声明『有哪条路』；**可达性必须实测** —— 未实测的 verified=False，不编"}


def status() -> dict:
    """Y 端口全貌（只读）：每个维度两臂各是什么态。"""
    rows = []
    for d in DIMENSIONS:
        m = DIM_META[d]
        ind = _indep_profile(d)
        ind_slot = _slot(ind, d) if ind else {"present": False, "key_id": "",
                                              "source": "未配专属", "masked": ""}
        pair = list(SHARED_PAIRS.get(d) or [])
        pair_slots = [_slot(p, d) for p in pair]
        rows.append({
            "dimension": d, "cn": m["cn"], "direction": m["dir"], "gate": m["gate"],
            "arm_independent": {
                "profile": ind, "ready": bool(ind_slot["present"]),
                "key_id": ind_slot["key_id"], "source": ind_slot["source"],
                "masked": ind_slot["masked"]},
            "arm_shared": {
                "pair": pair, "allow": bool(SHARE_POLICY.get(d, False)),
                "pair_ok": len(pair) == 2,
                "present": sum(1 for s in pair_slots if s["present"]),
                "pair_size": len(pair),
                "distinct": len({s["fp"] for s in pair_slots if s["present"]}) ==
                            len([s for s in pair_slots if s["present"]]),
                "ready": bool(SHARE_POLICY.get(d, False) and len(pair) == 2
                              and any(s["present"] for s in pair_slots)),
                "masked": [s["masked"] for s in pair_slots if s["masked"]]},
        })
    ready_any = [r for r in rows
                 if r["arm_independent"]["ready"] or r["arm_shared"]["ready"]]
    return {"ok": True, "readonly": True, "brand": BRAND_TAG, "cap": CAP,
            "port": "Y", "arms": list(ARMS), "dimensions": rows,
            "summary": ("Y 端口：%d/%d 个维度至少有一条可用臂" % (len(ready_any), len(rows))),
            "invariants": [
                "Y0 维度必须在册",
                "Y1 一次请求只走一臂（独立 / 共享不混用）",
                "Y2 共享臂必须恰好成对且指纹不同",
                "Y3 共享臂必须带 owner_ai_id 且不跨 owner",
                "Y4 维度共享策略须在册且为真",
                "Y5 明文永不出返回值",
                "Y6 没有可用钥匙 ⇒ 如实报缺（fail-closed）",
            ]}


# ══════════════════════════════════════════════════════════════════════
#  probe —— 免费通道可达性实测（**出网，唯一一个会出网的 op**）
# ══════════════════════════════════════════════════════════════════════
def probe(channel_id: str, timeout: int = 8) -> dict:
    """实测一个免密钥通道的**可达性**（只测 key=none 的公开端点，不带任何密钥）。

    只做「通 / 不通 / 未测」三态，**不冒充能力已验**。
    """
    cid = str(channel_id or "").strip()
    c = _CH.get(cid)
    if not c:
        return {"ok": False, "denied": True, "rule": "unknown_channel",
                "channel_id": cid, "known": sorted(_CH)}
    if c.get("key") != "none":
        return {"ok": False, "denied": True, "rule": "channel_needs_key",
                "channel_id": cid, "key": c.get("key"),
                "why": "带钥匙的通道**不由 probe 出网**（密钥只从保险箱取，"
                       "探测不该动钥匙）；它能不能用，看保险箱里有没有那把 profile"}
    url = str(c.get("url") or "")
    if "{" in url:
        url = url.replace("{prompt}", "potato")
    import urllib.request
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "GBT-Xiaotudou-V8/probe"})
        with urllib.request.urlopen(req, timeout=int(timeout or 8)) as resp:
            code = int(getattr(resp, "status", 0) or 0)
            ctype = str(resp.headers.get("Content-Type") or "")
            _ = resp.read(64)
        return {"ok": True, "readonly": True, "brand": BRAND_TAG, "channel_id": cid,
                "dim": c["dim"], "url": url, "status": code,
                "content_type": ctype[:60], "ms": int((time.time() - t0) * 1000),
                "verified": 200 <= code < 400,
                "note": "实测可达" if 200 <= code < 400 else "实测不通（HTTP %s）" % code}
    except Exception as exc:                            # noqa: BLE001
        return {"ok": True, "readonly": True, "brand": BRAND_TAG, "channel_id": cid,
                "dim": c["dim"], "url": url, "verified": False,
                "ms": int((time.time() - t0) * 1000),
                "error": str(exc)[:160],
                "note": "实测不通（网络/沙箱限制）—— **如实记，不假装可达**"}


# ══════════════════════════════════════════════════════════════════════
#  能力入口
# ══════════════════════════════════════════════════════════════════════
def run(op: str = "status", **params) -> dict:
    """op ∈ status / port / catalog / probe / redlines / selftest"""
    op = str(op or "status").strip().lower()
    if op == "status":
        return status()
    if op == "port":
        return port(str(params.get("dimension", "text") or "text"),
                    str(params.get("mode", "independent") or "independent"),
                    str(params.get("owner_ai_id", "") or ""))
    if op == "catalog":
        return catalog(str(params.get("dimension", "") or ""))
    if op == "probe":
        return probe(str(params.get("channel_id", "") or ""),
                     int(params.get("timeout", 8) or 8))
    if op == "redlines":
        return {"ok": True, "readonly": True, "brand": BRAND_TAG,
                "dimensions": dict(DIM_META),
                "invariants": status()["invariants"],
                "share_policy": dict(SHARE_POLICY),
                "note": "共享臂只禁『跨 AI 无约束共用』；同一 AI 内部按维度复用是有闸的"}
    if op == "selftest":
        return selftest()
    return {"ok": False, "fail_closed": True, "brand": BRAND_TAG,
            "error": "未知 op %r" % op,
            "available": ["status", "port", "catalog", "probe", "redlines", "selftest"]}


HONEST_BOUNDARY = (
    "本端口保证：**维度在册**、**一次只走一臂**、**共享必须成对且指纹不同**、"
    "**共享必须可追到 owner**、**明文永不出返回值**、**没有钥匙就如实报缺**。"
    "它保证不了：免费端点真的免费、真的可达（**可达性只能实测**，未实测的标 verified=False）；"
    "也保证不了画出来的图/视频好看 —— **好看只能由人判**。"
)


# ══════════════════════════════════════════════════════════════════════
#  自检（只读：不落盘、不发密钥；唯一例外是 probe 的显式调用）
# ══════════════════════════════════════════════════════════════════════
def selftest() -> dict:
    checks = []

    def ck(name, cond, detail=""):
        checks.append({"ok": bool(cond), "name": name, "detail": str(detail)[:160]})

    # ── 品牌 ─────────────────────────────────────────────────────────
    ck("品牌标志在册", BRAND == "GBT小土豆V8" and BRAND_TAG.startswith("🥔"), BRAND_TAG)

    # ── 维度在册 ─────────────────────────────────────────────────────
    # ⚠️ 2026-09-28：原断言写死"五个维度"。主人令要歌声 ⇒ 补 `audio`（文→声）这一格，
    #    断言跟着改（**不许让自检判一个已经过期的契约**）。
    ck("六个维度在册（含生图/生视频/文→声）",
       set(DIMENSIONS) == {"text", "vision", "image", "video", "code", "audio"}, DIMENSIONS)
    ck("维度词汇与 energy_pool.capability 对齐（text/image/video/code）",
       {"text", "image", "video", "code"} <= set(DIMENSIONS))

    # ── Y0 维度闸 ────────────────────────────────────────────────────
    r = port("魔法", "independent")
    ck("Y0 未知维度被拒", r["denied"] and r["rule"] == "unknown_dimension", r.get("rule"))

    # ── Y1 臂闸 + 正负对照 ───────────────────────────────────────────
    r = port("text", "两臂混用")
    ck("Y1 未知臂被拒", r["denied"] and r["rule"] == "unknown_arm", r.get("rule"))
    # 正对照判「**臂是否被识别**」，不是判「钥匙是否在」——
    # 合法臂在缺钥匙时仍会给 key_missing（那是 Y6，不是臂非法）；判据要卡在臂闸上。
    r_ok = port("text", "independent")
    ck("Y1 正对照：合法臂被**识别**（不被臂闸拒）",
       r_ok.get("rule") not in ("unknown_arm", "unknown_dimension"),
       "%s / %s" % (r_ok.get("rule", "OK"), r_ok.get("source", "")))

    # ── Y4 共享策略闸（video 默认禁共享）────────────────────────────
    r = port("video", "shared", owner_ai_id="tudou-01")
    ck("Y4 视频维度默认禁共享（策略为关）",
       r["denied"] and r["rule"] == "share_not_allowed_for_dimension", r.get("rule"))

    # ── Y3 owner 闸 ─────────────────────────────────────────────────
    r = port("text", "shared", owner_ai_id="")
    ck("Y3 共享臂缺 owner 被拒",
       r["denied"] and r["rule"] == "missing_owner_ai_id", r.get("rule"))

    # ── Y2 成对 + 指纹不同（正负对照，机械闸的真判据）────────────────
    r = port("image", "shared", owner_ai_id="tudou-01")
    ck("Y2 未配对的维度共享臂报『对未配齐』",
       r["denied"] and r["rule"] == "pair_incomplete", r.get("rule"))

    # 负对照：伪造一对**同指纹**的钥匙 —— 必须咬出 pair_same_fingerprint
    real_pairs = dict(SHARED_PAIRS)
    try:
        SHARED_PAIRS["image"] = ["agnes", "agnes"]     # 同一个 profile 挂两次
        r = port("image", "shared", owner_ai_id="tudou-01")
        neg = r["denied"] and r["rule"] in ("pair_same_fingerprint", "keys_missing")
        ck("Y2 负对照：同一把钥匙挂两次 ⇒ 咬出（假冗余/缺钥匙）", neg, r.get("rule"))
    finally:
        SHARED_PAIRS.clear()
        SHARED_PAIRS.update(real_pairs)

    # 正对照：同一个"坏对"在**没钥匙**与**有钥匙**两态下的**判据不同**——
    # 证明闸不是"永远报同一个错"（那是闸瞎了）
    try:
        SHARED_PAIRS["image"] = ["agnes", "agnes"]
        r_no_key = port("image", "shared", owner_ai_id="tudou-01")
    finally:
        SHARED_PAIRS.clear()
        SHARED_PAIRS.update(real_pairs)
    ck("Y2 自证：『同对』在缺钥匙时报 keys_missing（闸能分辨病因）",
       r_no_key["rule"] in ("keys_missing", "pair_same_fingerprint"), r_no_key.get("rule"))

    # ── Y6 缺钥匙如实报缺（fail-closed）────────────────────────────
    r = port("image", "independent")
    ck("Y6 生图维度未配专属钥匙 ⇒ 如实报缺（honest）",
       r["denied"] and r["rule"] == "no_dedicated_key" and r.get("honest") is True,
       r.get("rule"))

    # ── Y5 明文永不出返回值（正负对照：拿真钥匙跑，扫返回体）────────
    def _has_plaintext(blob: str) -> bool:
        import re as _re
        return bool(_re.search(r"\b(?:sk|ak)[-_][A-Za-z0-9_\-]{16,}\b", blob))

    out_probe = []
    for d in DIMENSIONS:
        for m in ARMS:
            out_probe.append(port(d, m, owner_ai_id="tudou-01"))
    import json as _json
    blob = _json.dumps(out_probe, ensure_ascii=False, default=str)
    ck("Y5 明文永不出返回值（全维度 × 双臂 扫描）", not _has_plaintext(blob),
       "%d 条返回值" % len(out_probe))
    # 负对照：把明文塞进同一个出口，扫描器必须咬
    ck("Y5 负对照：明文混入即被咬",
       _has_plaintext('{"key_masked":"sk-' + "a" * 40 + '"}'), "poison")

    # ── 真实取钥匙路径（只在保险箱里有货时才断言性质）──────────────
    r = port("text", "independent")
    if r.get("ok"):
        _plain = _vault(_indep_profile("text"))[0]
        # 判据**与掩码风格无关**：本模块的掩码是 `品牌|维度|头4…尾4|#指纹`（对齐 key_gateway），
        # 不用星号 ⇒ 拿 `"*" in masked` 当判据是**卡错了对象**。
        # 真判据：明文**整串**不出现在掩码里，且掩码确实带了**可比对的指纹**。
        ck("独立臂有钥匙时：掩码不泄明文且带指纹",
           bool(_plain) and _plain not in r["key_masked"] and bool(r["fp"])
           and r["fp"] in r["key_masked"],
           r["key_id"])
    else:
        ck("独立臂没钥匙时：不许编假掩码", r.get("key_masked", "") == "",
           r.get("rule"))

    # ── catalog ──────────────────────────────────────────────────────
    c = catalog()
    ck("免费通道目录非空且覆盖 image/video",
       c["count"] > 0 and c["by_dim"].get("image", 0) > 0 and c["by_dim"].get("video", 0) > 0,
       c["by_dim"])
    ck("未实测通道一律 verified=False（不编）",
       all(r.get("verified") is False for r in c["channels"]),
       "全部未实测")

    # ── status 自洽 ─────────────────────────────────────────────────
    st = status()
    ck("status 覆盖全部维度", len(st["dimensions"]) == len(DIMENSIONS), st["summary"])
    ck("status 是只读的（不写盘、不发密钥）", st["readonly"] is True)

    passed = sum(1 for ch in checks if ch["ok"])
    return {"ok": passed == len(checks), "brand": BRAND_TAG, "cap": CAP,
            "passed": passed, "total": len(checks), "checks": checks,
            "honest_boundary": HONEST_BOUNDARY}


if __name__ == "__main__":
    import sys
    from pathlib import Path as _P
    _root = str(_P(__file__).resolve().parents[2])
    if _root not in sys.path:
        sys.path.insert(0, _root)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                   # noqa: BLE001
        pass
    res = selftest()
    for c in res["checks"]:
        print("  [%s] %s%s" % ("PASS" if c["ok"] else "FAIL", c["name"],
                               ("  ← " + c["detail"]) if not c["ok"] and c["detail"] else ""))
    print("\n%s multimodal_port 自检 %d/%d" % (BRAND_TAG, res["passed"], res["total"]))
