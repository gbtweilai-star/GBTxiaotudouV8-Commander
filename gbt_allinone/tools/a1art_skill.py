# gbt-capability: a1art_skill
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""a1.art API 技能（a1art_skill）· R-H206 只读骨架。

**它是"门"（external）**：a1.art 的开放 API 入口。
五原语：``LOOKUP → UPLOAD → GENERATE → OPTIMIZE → POLL``。

四条红线（做成机械闸）：
  ① 密钥只存 DPAPI（不许明文落盘 / 不许进返回值）；
  ② 结果必须**下载到本地**（链接会失效 ⇒ 不许只留 a1.art 链接）；
  ③ **不调不支持的组件**（数字分身 / wordart / 合照 / Video 组件）；
  ④ 余额不足**如实报**（810012 ⇒ 不重试、不硬撑）。

本骨架只读：**不装、不调、不出网、不落盘**。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

SKILL_SOURCE = "a1.art 开放 API（平台正在逐步停止服务 · 接入是存量窗口）"
CAP_KIND = "a1art_skill"
# R-H215：domain 按**官方口径**修正 —— 主人明确 = `image_video`（此前我们写 `image`）
DOMAIN = "image_video"
CAP_TYPE = "external"                      # 它是门，不是内调型

# 五原语（缺一即开环）
PRIMITIVES: Tuple[Dict[str, str], ...] = (
    {"key": "lookup", "cn": "LOOKUP · 获取应用基础信息与生图入参",
     "note": "图生图 / 图生视频**之前**的必调步骤（不先取入参 = 拿不准参数就发请求）"},
    {"key": "upload", "cn": "UPLOAD · 上传图片",
     "note": "图生图 / 图生视频依赖的图片"},
    {"key": "generate", "cn": "GENERATE · 发起生成",
     "note": "按 LOOKUP 拿到的入参契约发起，不猜参数"},
    {"key": "optimize", "cn": "OPTIMIZE · 高清处理（精绘）",
     "note": "**3 积分/张**（官方口径）"},
    {"key": "poll", "cn": "POLL · 轮询结果",
     "note": "拿到结果地址后**必须立刻下载到本地**（链接会失效）"},
)

# 明说不调的组件（不是"暂时不调"，是**不调**）
UNSUPPORTED_COMPONENTS = ("数字分身", "wordart", "合照", "Video 组件")

# ── R-H211 · API 能力矩阵（官方口径 · 5 个核心接口）──
# 规律：**创建类 = POST …/images/*；查询类 = GET …/{appId | taskId}**
API_BASE = "https://a1.art/open-api/v1/a1"
API_ENDPOINTS = (
    {"n": 1, "primitive": "lookup", "cn": "获取 APP 信息",
     "method": "GET", "path": "/open-api/v1/a1/apps/{appId}",
     "note": "**图生图 / 图生视频前必须调用，获取依赖参数**（没先调它 = 拿不准参数就发请求）"},
    {"n": 2, "primitive": "upload", "cn": "上传图片",
     "method": "POST", "path": "/open-api/v1/a1/images/upload",
     "note": "图生图 / 图生视频依赖的图片（素材进 OSS）"},
    {"n": 3, "primitive": "generate", "cn": "生成图片 / 视频",
     "method": "POST", "path": "/open-api/v1/a1/images/generate",
     "note": "**传入参数，得到 `taskId`**（下一轮轮询的钥匙）。"
             "⚠️ 路径写 `images`、作用写「图片/视频」 —— 原样记，不擅自改"},
    {"n": 4, "primitive": "optimize", "cn": "图片精绘",
     "method": "POST", "path": "/open-api/v1/a1/images/optimize",
     "note": "高清处理 · **3 积分/张**"},
    {"n": 5, "primitive": "poll", "cn": "查询任务结果",
     "method": "GET", "path": "/open-api/v1/a1/tasks/{taskId}",
     "note": "拿 GENERATE 返回的 `taskId` 换结果；**拿到地址后必须落本地**"},
)

# 与 R-H206 五原语的对照（**实测印证，不是猜的**）
PRIMITIVE_ENDPOINT_MAP = {e["primitive"]: e["path"] for e in API_ENDPOINTS}

# ── R-H213 · 接口详情（参数契约 + 硬限制 · 官方口径）──
AUTH_HEADER = "apiKey"          # 访问授权：Base URL https://a1.art + apiKey 请求头
AUTH_BASE_URL = "https://a1.art"

SIZE_ID_MAP = {1: "1:1", 2: "3:4", 3: "1:2", 4: "4:3",
               5: "2:1", 6: "16:9", 7: "9:16"}

UPLOAD_LIMITS = {
    "exts": (".png", ".jpg", ".jpeg"),
    "max_files": 1,
    "max_bytes": 10 * 1024 * 1024,      # 10M
    "max_side": 2048,                   # R-H215：尺寸 ≤2048×2048（错误码 400006）
    "file_or_url": ("file", "imageUrl"),  # 二选一，必传其一
    "returns": ("imageUrl", "path"),      # 生图接口依赖这两个
}

# R-H215 · 「不支持组件」的**官方出处**（此前 Video 组件标"待核"，现已有出处）
UNSUPPORTED_EVIDENCE = {
    "official": "不支持查询带有 数字分身组件 / wordart 组件 / "
                "group photo 组件为 user upload 模式 / **Video 组件** 的 app",
    "codes": ("324010", "324018"),
    "note": "四个组件**出处均已证**；『很大一部分热门应用不开放 API』",
}

GENERATE_FIELDS = (
    {"f": "appId", "type": "string", "required": True, "cn": "应用 id"},
    {"f": "versionId", "type": "string", "required": True, "cn": "应用版本 id"},
    {"f": "generateNum", "type": "string", "required": True,
     "cn": "生成数量（**1～4 张**）", "range": (1, 4)},
    {"f": "cnet", "type": "array", "required": False, "cn": "说明待补"},
    {"f": "description", "type": "array", "required": False, "cn": "说明待补"},
    {"f": "styleId", "type": "string", "required": False, "cn": "风格 id"},
    {"f": "size", "type": "object", "required": False,
     "cn": "尺寸（sizeId 1-7）", "enum": tuple(SIZE_ID_MAP)},
)

OPTIMIZE_LIMITS = {
    "params": ("path", "imageUrl"),        # 均为上传接口返回值
    "points_per_call": 3,
    "max_side": 2048,                      # 尺寸限制 2048×2048
    "returns": "同生成接口（taskId）",
}

TASK_STATES = {0: "已提交", 10: "已完成", 20: "失败", 30: "进行中"}
SECTION_HEADER = "section"
SECTION_CN = "cn"                          # 中国区传 cn

# 🔴 官方原话：「生成的图片地址后续可能会失效，**建议将结果保存在自己的 CDN 上**」
# ⇒ 这把「不许只留链接」从我们的主张变成**官方建议**，且落点是「自己的」（可控）
RESULT_PERSISTENCE = {
    "official": "生成的图片地址后续可能会失效，建议将结果保存在**自己的 CDN** 上",
    "our_rule": "必须落到**可控落点**（本地或自有 CDN）；只留平台临时链接 ⇒ 拒",
    "gate": "must_localize（link_only_result / oss_link_only）",
}

# ── R-H216 · 官方「三条带牙用例」对账（3/3 与我们一致 · 双源印证）──
TEETH_CASES = (
    {"n": 1, "official": "返回值不许带明文 apiKey；必须走 DPAPI / 密钥池",
     "our_gates": ("plaintext_key_in_return", "key_source_not_pool"),
     "match": True},
    {"n": 2, "official": "生成结果必须下载到**本地 CDN / 工作区**，"
                         "不许只留 a1.art 链接",
     "our_gates": ("link_only_result",),
     "match": True,
     "increment": "落点清单更明确：**本地 CDN / 工作区**（此前只写『本地』）"},
    {"n": 3, "official": "不调不支持的组件",
     "our_gates": ("unsupported_component",), "match": True},
)

# R-H216 · 允许的落点（官方口径）：**本地 CDN / 工作区**
ALLOWED_LANDINGS = ("本地 CDN", "工作区", "local_cdn", "workspace")

# ── R-H217 · 官方「四条红线（写死）」对账（**4/4 已有现成闸，不新造**）──
REDLINES_OFFICIAL = (
    {"n": 1, "official": "密钥只存 DPAPI",
     "our_gates": ("key_must_be_dpapi",)},
    {"n": 2, "official": "apiKey 走密钥池，不许明文落盘",
     "our_gates": ("key_source_not_pool", "key_persisted_to_file")},
    {"n": 3, "official": "结果必须落盘",
     "our_gates": ("link_only_result", "landing_not_allowed")},
    {"n": 4, "official": "不调不支持的组件",
     "our_gates": ("unsupported_component",)},
)

# R-H217 · LOOKUP 的**三重角色**（此前只认识到第一重）
LOOKUP_ROLES = (
    {"n": 1, "role": "拿依赖参数", "why": "formArr / styleArr / cost / processTime"},
    {"n": 2, "role": "续期", "why": "versionId 会过期（错误码 324013）⇒ 需重新 LOOKUP"},
    {"n": 3, "role": "**预检组件**", "why": "appInfo 里能看出是否含不支持的组件 ⇒ "
                                            "**请求前就拦住**，而不是等 324010 回来"},
)

# 积分消耗体系：⚠️ 主人未给 ⇒ 留追加位，不编
CREDIT_SYSTEM = {"known": ("精绘 3 点数/次",), "unknown": True,
                 "note": "官方《积分消耗体系》一节主人未给 ⇒ 留追加位"}

# ── R-H214 · 错误码体系（**18 个** · 官方口径 · 逐条给）──
# `retry` 的判据：**是"钱的问题"还是"节奏的问题"** —— 只有节奏类才退避重试。
ERROR_CODES = (
    {"code": "0", "msg_cn": "成功", "class": "ok", "retry": False},
    {"code": "10001", "msg_cn": "无效的参数", "class": "param", "retry": False},
    {"code": "10002", "msg_cn": "不支持的文件后缀", "class": "param", "retry": False},
    {"code": "10410", "msg_cn": "缺少 API key", "class": "auth", "retry": False},
    {"code": "10411", "msg_cn": "无效的 API key", "class": "auth", "retry": False},
    {"code": "20000", "msg_cn": "接口访问触发限流", "class": "transient", "retry": True},
    {"code": "20002", "msg_cn": "服务器错误", "class": "transient", "retry": True},
    {"code": "20003", "msg_cn": "服务内部错误", "class": "transient", "retry": True},
    {"code": "20100", "msg_cn": "文件异常", "class": "asset", "retry": False},
    {"code": "20101", "msg_cn": "文件后缀异常", "class": "asset", "retry": False},
    {"code": "324010", "msg_cn": "此应用不支持通过 API 访问", "class": "access",
     "retry": False,
     "detail": "具体：数字分身 / wordart / 合照 · **user upload 模式**不支持"},
    {"code": "324011", "msg_cn": "单个应用单次请求生图数量 1～4 张", "class": "param",
     "retry": False},
    {"code": "324012", "msg_cn": "无效的应用 ID", "class": "param", "retry": False},
    {"code": "324013", "msg_cn": "应用版本已更新，请重新获取应用信息", "class": "stale",
     "retry": False, "action": "relookup"},
    {"code": "324018", "msg_cn": "调用他人的未发布应用 API", "class": "access",
     "retry": False,
     "detail": "表单式只支持调用**自己的**未发布应用"},
    {"code": "324019", "msg_cn": "没有使用 VIP app 的权益", "class": "entitlement",
     "retry": False},
    {"code": "810012", "msg_cn": "账户余额不足", "class": "credit", "retry": False},
    {"code": "400000", "msg_cn": "缺少图片文件", "class": "asset", "retry": False},
)
# R-H215 · 口径修正：官方标题写「18 个」，但主人后续又给了 3 个 ⇒ **18 不是上限**。
# 改成 **as_of 语义**（"截至某次采集收到 N 个"），**不承诺是全集** ——
# 与「死角永远会有，关键是有没有登记」同源。
ERROR_CODE_AS_OF = "2026-09-20 · 主人逐条给"


def _extra_error_codes() -> tuple:
    """R-H215 追加的三条（上传族补充）。"""
    return (
        {"code": "400001", "msg_cn": "一次只支持上传一张图片", "class": "asset",
         "retry": False, "gate": "too_many_files"},
        {"code": "400003", "msg_cn": "图片文件不能超过 10M", "class": "asset",
         "retry": False, "gate": "file_too_large"},
        {"code": "400006", "msg_cn": "图片文件尺寸不能超过 2048×2048", "class": "asset",
         "retry": False, "gate": "image_too_large_dimension"},
    )

# 使用范式（官方给 · 计价口径**各不同**）
USAGE_PARADIGMS = (
    {"key": "form_app", "cn": "表单式应用生图", "pricing": "1 积分/张",
     "unpublished": "**支持**调用**自己的**未发布应用"},
    {"key": "node_app", "cn": "节点式应用生图", "pricing": "**按节点个数**扣除",
     "unpublished": "**不支持**草稿应用的 API 调用"},
    {"key": "optimize", "cn": "精绘图片", "pricing": "3 积分/张",
     "unpublished": "—", "limit": "尺寸 ≤ 2048×2048"},
    {"key": "image_to_video", "cn": "图生视频", "pricing": "10 积分/个",
     "unpublished": "—"},
)

# 定价（官方给）
PRICING = {
    "packages": ({"points": 1000, "usd": 19.99},
                 {"points": 5000, "usd": 89.99},
                 {"points": 50000, "usd": 799.99}),
    "membership": {"monthly_usd_per_month": 27.99, "yearly_usd_per_month": 22.99},
    "quoted_unit": "$0.010/积分",
    # ⚠️ 存疑：套餐折算单价都**高于**标注单价 ⇒ 并排记，不擅自解释
    "unit_check": {"1000": round(19.99 / 1000, 5), "5000": round(89.99 / 5000, 5),
                   "50000": round(799.99 / 50000, 6)},
    "unit_conflict": True,
}

# 🔴 两处**未解冲突**（并排记，等主人一句话）
OPEN_CONFLICTS = {
    "topup": {
        "said_a": "不再提供 API 积分充值（用完即止）—— R-H206 / R-H211",
        "said_b": "一张完整定价表（1000/5000/50000 点数 + 会员）—— R-H214",
        "likely": "A. 『API 侧』不再单独提供充值，但产品/网页侧仍可购买；"
                  "API 消耗的是账户积分 ⇒ 两者可并存",
        "pending": True,
    },
    "unit": {
        "said_a": "接口 4 精绘：**3 个点数**/次",
        "said_b": "精绘图片：**3 积分**/张 · 表单式 **1 积分**/张",
        "likely": "两处数字一致（都是 3）⇒ 倾向『点数 = 积分』",
        "pending": True,
    },
}

# 口径（官方给的，不是我们猜的）
POLICIES = {
    "credits": "高清处理 **3 积分/张**；余额不足由平台返回错误码 810012",
    "error_810012": "810012 ⇒ **直接上报，不重试、不硬撑**（重试只会继续烧额度）",
    "link_expiry": "生成结果地址**可能失效** ⇒ 必须下载到本地，不许只留 a1.art 链接",
    "lifecycle": "平台正在**逐步停止服务** ⇒ 接入它是合理的，"
                 "但要知道**它不是长期基础设施**",
    "no_topup": "🔴 **不再提供 API 积分充值** ：现有积分**用完即止** ⇒ "
                "积分是**一次性存量**，不存在「续上」这回事；"
                "任何长期规划都必须先承认这一点",
}

# 规模口径：**两个数并排记，不挑一个当真相**（等主人定口径）
PLATFORM_SCALE = {
    "figures": ({"n": "45,000+", "said": "应用（只有一部分开放 API）",
                 "from": "主人 R-H206 那次"},
                {"n": "100,000+", "said": "影像生成应用 · 每月新增上百个",
                 "from": "主人《a1.art API 使用指南》那次"}),
    "conflict": True,
    "why": "两个数不一样：可能是「总量 vs 开放 API 的量」两个口径，也可能是文档更新 ⇒ "
           "**如实并排，不擅自合并**；要报数时**两个一起报**或标注来源",
}

# 平台定位（官方口径）
PLATFORM_POSITION = (
    "a1.art 是**开放的内容社区**：任何人都能创建并发布 APP / 滤镜；"
    "发布后**其他用户可以自由调用 API**、消耗积分来生成图片或视频。"
)

RED_LINES = (
    "密钥只存 DPAPI（不许明文落盘、不许贴进对话、不许进返回值）",
    "结果必须落盘（链接会失效 ⇒ 不许只回一个 a1.art 链接）",
    "不调不支持的组件（数字分身 / wordart / 合照 / Video 组件）",
    "余额不足如实报（810012 ⇒ 不重试、不硬撑、直接上报）",
)

EXTERNAL_KEY_ENVS = ("A1ART_API_KEY", "A1_ART_API_KEY", "A1ART_KEY",
                     "A1ART_TOKEN", "A1_ART_KEY", "A1ART_ACCESS_KEY")

_PLAINTEXT_KEY_RX = re.compile(r"\b(?:sk|ak|lt|a1)[-_][A-Za-z0-9_\-]{16,}\b")

# 盘上取证快照（R-H206 实测 · 带出处）
FORENSICS = {
    "as_of": "2026-09-20T13:1x",
    "a1art_hits_on_disk": 0,               # 代码/配置/图纸：命中 0
    "key_envs_set": 0,                     # 六个候选 env 全未设置
    "dpapi_on_disk": ["cloudflare_api.dpapi", "deepseek_api.dpapi",
                      "feishu_app.dpapi", "notion_api.dpapi", "xingyun_app.dpapi"],
    "a1art_dpapi_on_disk": False,          # 保险箱里**没有** a1art
    "api_doc_on_disk": False,              # 真实接口文档不在盘上 ⇒ 不编造 endpoint
    "source": "tools/a1art_skill.py 取证（.scratch/_rh206_a1art_forensics.py）",
}


def assert_no_plaintext(payload: Any, where: str = "") -> dict:
    """红线①：返回值里出现明文 key ⇒ 拒。"""
    import json
    blob = json.dumps(payload, ensure_ascii=False, default=str)
    if _PLAINTEXT_KEY_RX.search(blob):
        return {"ok": False, "denied": True, "rule": "plaintext_key_in_return",
                "where": str(where or ""),
                "why": "密钥只从 DPAPI / 密钥池取；返回值只许带 key_id / 掩码 / 状态"}
    return {"ok": True, "readonly": True}


def lease_key(owner_ai_id: str, tentacle_id: str = "a1art") -> dict:
    """红线①：**只从密钥池借** —— 不许读环境变量、不许明文落盘。"""
    if not str(owner_ai_id or "").strip():
        return {"ok": False, "denied": True, "rule": "missing_owner_ai_id",
                "why": "a1.art 的密钥也要按一 AI 一号借（触手不是身份）"}
    try:
        from . import model_key_pool as mkp
        got = mkp.ModelKeyPool().lease(tentacle_id, owner_ai_id)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "rule": "key_pool_unavailable",
                "why": "密钥池不可用：%s" % str(e)[:80]}
    if not got.get("ok"):
        return {"ok": False, "denied": True,
                "rule": got.get("rule") or "no_key_for_owner",
                "why": got.get("why") or "该 AI 身份尚未在密钥池配置 a1.art 密钥（拒执行并上报）"}
    out = {"ok": True, "readonly": True, "lease_id": got.get("lease_id"),
           "key_id": got.get("owner_ai_id"), "leased": True,
           "key_masked": "****（池内持有，不出池）"}
    guard = assert_no_plaintext(out, where="lease_key.return")
    return out if guard.get("ok") else guard


def must_localize(result: Optional[Dict] = None, local_path: str = "") -> dict:
    """红线②：**结果必须落盘** —— 只回链接 ⇒ 拒（链接会失效）。"""
    r = dict(result or {})
    p = str(local_path or r.get("local_path") or "").strip()
    if not p:
        return {"ok": False, "denied": True, "rule": "link_only_result",
                "why": "只留 a1.art 链接不算产出：生成地址可能失效 ⇒ "
                       "必须下载到本地并给出 local_path"}
    # R-H216：官方把落点写明确了 —— **本地 CDN / 工作区**
    landing = str(r.get("landing") or "").strip()
    if landing and landing not in ALLOWED_LANDINGS:
        return {"ok": False, "denied": True, "rule": "landing_not_allowed",
                "landing": landing, "allowed": list(ALLOWED_LANDINGS),
                "why": "落点必须是**本地 CDN / 工作区**（可控落点）——"
                       "别又落回平台临时链接或不明第三方"}
    return {"ok": True, "readonly": True, "local_path": p,
            "landing": landing or "（未声明，按可控落点处理）",
            "allowed_landings": list(ALLOWED_LANDINGS),
            "note": "落盘后再进 trace_store（无痕即未发生）"}


def refuse_unsupported(component: str) -> dict:
    """红线③：**不调不支持的组件**（明说不调，不是"暂时不调"）。"""
    c = str(component or "").strip()
    if not c:
        return {"ok": False, "denied": True, "rule": "missing_component",
                "why": "要说清调哪个组件，不许空调用"}
    hit = [x for x in UNSUPPORTED_COMPONENTS if x.lower() in c.lower()]
    if hit:
        return {"ok": False, "denied": True, "rule": "unsupported_component",
                "component": c, "unsupported": hit,
                "why": "该组件不在支持面内（%s）—— 不调，也不假装能调" % " / ".join(hit)}
    return {"ok": True, "readonly": True, "component": c}


def classify_error(code: Any, message: str = "") -> dict:
    """红线④ + R-H214：按**官方 18 个错误码**归类，并给出**可否重试**。

    判据的核心：**是"钱的问题"还是"节奏的问题"** —— 只有节奏类才退避重试。
    """
    s = str(code if code is not None else "").strip()
    if not s:
        return {"ok": False, "denied": True, "rule": "missing_error_code",
                "why": "没有错误码就别说'失败了'——先把码与原文拿到手"}
    row = next((x for x in ERROR_CODES if x["code"] == s), None)
    if row is None:
        return {"ok": False, "denied": True, "rule": "unknown_error_code",
                "code": s, "known": [x["code"] for x in ERROR_CODES],
                "why": "不在官方 18 个错误码里 ⇒ **如实报未知**，不许硬塞一个原因"}
    out = {"ok": row["class"] == "ok", "readonly": True, "code": s,
           "msg_cn": row["msg_cn"], "class": row["class"], "retry": row["retry"],
           "message": str(message)[:200]}
    if s == "810012":
        out["rule"] = "insufficient_credit"
        out["why"] = "账户余额不足 ⇒ **直接上报，不重试不硬撑**（重试只会继续烧额度）"
    elif row.get("action") == "relookup":
        out["rule"] = "stale_app_version"
        out["action"] = "relookup"
        out["why"] = "应用版本已更新 ⇒ **重新 LOOKUP** 拿新 versionId，" \
                     "不许拿旧 versionId 硬重试"
    elif row["class"] == "transient" and row["retry"]:
        out["rule"] = "retryable_transient"
        out["why"] = "临时类（限流 / 服务器）⇒ **可退避重试**（不是钱的问题）"
    else:
        out["rule"] = "a1art_%s" % row["class"]
        out["why"] = "官方错误码：%s ⇒ 不重试，先把根因修掉" % row["msg_cn"]
    if row.get("detail"):
        out["detail"] = row["detail"]
    return out


def check_retry(code: Any, attempts: int = 0, max_attempts: int = 3) -> dict:
    """R-H214 · 重试闸：**只有临时类才退避重试**，且要有次数上限。"""
    c = classify_error(code)
    if c.get("rule") == "missing_error_code":
        return c
    if not c.get("retry"):
        return {"ok": False, "denied": True, "rule": "retry_not_allowed",
                "code": str(code), "msg_cn": c.get("msg_cn"),
                "why": "该错误码**不可重试**（%s）：重试只会重复同一个失败，"
                       "甚至继续花钱" % c.get("msg_cn")}
    if int(attempts or 0) >= int(max_attempts):
        return {"ok": False, "denied": True, "rule": "retry_exhausted",
                "attempts": attempts, "max_attempts": max_attempts,
                "why": "退避重试到上限就停 —— **不许无限重试**"}
    return {"ok": True, "readonly": True, "code": str(code),
            "attempts": int(attempts or 0) + 1, "max_attempts": int(max_attempts),
            "note": "临时类 ⇒ 可退避重试（第 %d 次）" % (int(attempts or 0) + 1)}


def estimate_cost(paradigm: str = "", count: int = 1) -> dict:
    """R-H214 · 成本估算：**先算够不够，再发请求**（积分不再补充）。"""
    p = str(paradigm or "").strip().lower()
    row = next((x for x in USAGE_PARADIGMS if x["key"] == p), None)
    if row is None:
        return {"ok": False, "denied": True, "rule": "unknown_paradigm",
                "known": [x["key"] for x in USAGE_PARADIGMS],
                "why": "计价口径**因范式而异**（表单式/节点式/精绘/图生视频）——"
                       "先说是哪种，别拿一个数套所有"}
    if p == "node_app":
        return {"ok": True, "readonly": True, "paradigm": p,
                "pricing": row["pricing"],
                "note": "**按节点个数扣**，不是按张 —— 单价待补 ⇒ 现在**算不出确定成本**"}
    unit = {"form_app": 1, "optimize": 3, "image_to_video": 10}[p]
    n = int(count or 1)
    return {"ok": True, "readonly": True, "paradigm": p, "unit": unit,
            "count": n, "total": unit * n,
            "note": "按官方表价估算；权威成本以 `appInfo.cost` 为准（接口 1 返回）"}


def check_endpoint(endpoint: str = "") -> dict:
    """R-H211 · 端点白名单闸：**只认官方那 5 个**；自己拼请求 ⇒ 拒。"""
    e = str(endpoint or "").strip()
    if not e:
        return {"ok": False, "denied": True, "rule": "missing_endpoint",
                "known": [x["path"] for x in API_ENDPOINTS],
                "why": "要说清调哪个官方端点"}
    # ⚠️ 判据顺序很重要（实测踩过）：先剥官方前缀，再查可疑形状。
    # 第一版拿 `/api/v\d` 去查，**误伤了官方路径 `/open-api/v1/…`** ⇒ 正确调用被判成"自己拼请求"。
    if re.search(r"https?://", e, re.I) and not re.search(r"https?://a1\.art", e, re.I):
        return {"ok": False, "denied": True, "rule": "handmade_api_request",
                "seen": e[:120], "why": "只认官方域名 a1.art —— 别的域名一律不认"}
    norm = re.sub(r"^https?://a1\.art", "", e)
    if not norm.startswith("/open-api/"):
        return {"ok": False, "denied": True, "rule": "handmade_api_request",
                "seen": norm[:120],
                "why": "不许自己拼请求：只走官方 `/open-api/v1/a1/*`"
                       "（绕开 = 绕过平台验证）"}
    # 占位符与具体值**都要认**：从模板生成正则，把 `{appId}` / `{taskId}` 变成 `[^/]+`
    # （实测踩过两次：① 只认模板 ⇒ `/tasks/abc123` 判 unknown；② 两边都归一成 X ⇒ 仍不相等）
    def _tpl_to_rx(t: str) -> str:
        pat = re.escape(str(t))
        return re.sub(r"\\\{[^}]+?\\\}", "[^/]+", pat)

    for x in API_ENDPOINTS:
        if re.fullmatch(_tpl_to_rx(x["path"]), norm):
            return {"ok": True, "readonly": True, "primitive": x["primitive"],
                    "cn": x["cn"], "method": x["method"], "path": x["path"]}
    return {"ok": False, "denied": True, "rule": "unknown_endpoint",
            "endpoint": norm, "known": [x["path"] for x in API_ENDPOINTS],
            "why": "官方能力矩阵只有这 5 个端点；别的路子不认"}


def must_lookup_first(looked_up: bool = False, app_id: str = "") -> dict:
    """R-H211 · 顺序闸：**图生图 / 图生视频前必须先调 LOOKUP**。

    依据官方备注：「图生图/图生视频前**必须调用**，获取依赖参数」。
    """
    if not str(app_id or "").strip():
        return {"ok": False, "denied": True, "rule": "missing_app_id",
                "why": "LOOKUP 要带 appId（`GET /open-api/v1/a1/apps/{appId}`）"}
    if not looked_up:
        return {"ok": False, "denied": True, "rule": "lookup_required",
                "app_id": str(app_id),
                "why": "**没先调 LOOKUP 就生成 = 拿不准依赖参数就发请求**；"
                       "官方口径：图生图/图生视频前必须调用"}
    return {"ok": True, "readonly": True, "app_id": str(app_id), "looked_up": True}


def must_task_id(task_id: str = "", for_what: str = "poll") -> dict:
    """R-H211 · 钥匙闸：**POLL / 精绘前必须带 `taskId`**（GENERATE 的产出物）。"""
    t = str(task_id or "").strip()
    if not t:
        return {"ok": False, "denied": True, "rule": "missing_task_id",
                "for": str(for_what or "poll"),
                "why": "`taskId` 是 GENERATE 的产出物、后续操作的**唯一钥匙**；"
                       "丢了只能重新生成（= 白花积分，而积分**不再充值**）"}
    return {"ok": True, "readonly": True, "task_id": t, "for": str(for_what or "poll")}


def check_service_window() -> dict:
    """R-H211 · 停服窗口闸：**积分是一次性存量，不存在"续上"**。"""
    return {"ok": True, "readonly": True, "writable": False,
            "topup_available": False,
            "lifecycle": POLICIES["no_topup"],
            "action": "plan_as_consumable",
            # ⚠️ R-H214：定价表与"不再充值"**冲突未解** ⇒ 本值**待主人确认**，不擅自翻转
            "conflict": OPEN_CONFLICTS["topup"],
            "why": "把 a1.art 当**存量窗口**规划：先算「这点积分够做几件事」，"
                   "再决定要不要把流程挂上去；**不许把它当长期基础设施**"}


def check_upload(files: Optional[List] = None, image_url: str = "") -> dict:
    """R-H213 · 上传硬限制：**png/jpg/jpeg · 单张 · ≤10M**；file 与 imageUrl 二选一。"""
    rows = list(files or [])
    if not rows and str(image_url or "").strip():
        return {"ok": True, "readonly": True, "via": "imageUrl",
                "note": "file 与 imageUrl **传其一**即可"}
    if not rows:
        return {"ok": False, "denied": True, "rule": "missing_file_or_url",
                "why": "`file` 与 `imageUrl` 必须**传其一**（都不传 = 空上传）"}
    if len(rows) > UPLOAD_LIMITS["max_files"]:
        return {"ok": False, "denied": True, "rule": "too_many_files",
                "got": len(rows), "max": UPLOAD_LIMITS["max_files"],
                "why": "**每次仅可上传一张**"}
    for r in rows:
        d = dict(r or {})
        name = str(d.get("name") or "")
        ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
        size = d.get("size")
        if ext and ext not in UPLOAD_LIMITS["exts"]:
            return {"ok": False, "denied": True, "rule": "unsupported_file_type",
                    "name": name, "ext": ext,
                    "allowed": list(UPLOAD_LIMITS["exts"]),
                    "why": "仅支持 png / jpg / jpeg"}
        if isinstance(size, (int, float)) and size > UPLOAD_LIMITS["max_bytes"]:
            return {"ok": False, "denied": True, "rule": "file_too_large",
                    "name": name, "size": size,
                    "max_bytes": UPLOAD_LIMITS["max_bytes"],
                    "why": "图片文件大小不可大于 **10M**"}
        # R-H215 补缺口：**上传也有尺寸限制**（错误码 400006）——
        # 此前只查了后缀/数量/体积，**漏了尺寸**，这条是照报照补。
        for kk, label in (("width", "width"), ("height", "height")):
            v = d.get(kk)
            if isinstance(v, (int, float)) and v > UPLOAD_LIMITS["max_side"]:
                return {"ok": False, "denied": True,
                        "rule": "image_too_large_dimension", "side": label,
                        "value": v, "max": UPLOAD_LIMITS["max_side"],
                        "name": name,
                        "why": "图片文件尺寸不能超过 **2048×2048**（错误码 400006）"}
    return {"ok": True, "readonly": True, "files": len(rows),
            "returns": list(UPLOAD_LIMITS["returns"]),
            "note": "上传返回 `imageUrl` + `path` ⇒ **生图接口依赖这两个，必须存住**"}


def check_generate_params(params: Optional[Dict] = None) -> dict:
    """R-H213 · 生成参数契约：必传三个（`appId`/`versionId`/`generateNum`）+ 区间与枚举。"""
    p = dict(params or {})
    for spec in GENERATE_FIELDS:
        if not spec["required"]:
            continue
        if not str(p.get(spec["f"]) or "").strip():
            return {"ok": False, "denied": True, "rule": "missing_param",
                    "param": spec["f"], "cn": spec["cn"],
                    "why": "必传字段缺失：%s（%s）" % (spec["f"], spec["cn"])}
    n = str(p.get("generateNum") or "").strip()
    if not re.fullmatch(r"\d+", n) or not (1 <= int(n) <= 4):
        return {"ok": False, "denied": True, "rule": "num_out_of_range",
                "generateNum": n, "range": [1, 4],
                "why": "生成数量只允许 **1～4 张**"}
    size = p.get("size")
    if isinstance(size, dict) and size:
        sid = size.get("sizeId", size.get("id"))
        if sid is not None and str(sid).strip() != "" and int(sid) not in SIZE_ID_MAP:
            return {"ok": False, "denied": True, "rule": "bad_size_id",
                    "sizeId": sid, "allowed": dict(SIZE_ID_MAP),
                    "why": "sizeId 只允许 1-7"}
    return {"ok": True, "readonly": True,
            "required": [s["f"] for s in GENERATE_FIELDS if s["required"]],
            "optional": [s["f"] for s in GENERATE_FIELDS if not s["required"]]}


def check_optimize(path: str = "", image_url: str = "",
                   width: Any = None, height: Any = None) -> dict:
    """R-H213 · 精绘限制：参数须为上传返回值 · **3 点数/次** · 尺寸 ≤ **2048×2048**。"""
    if not str(path or "").strip() or not str(image_url or "").strip():
        return {"ok": False, "denied": True, "rule": "missing_upload_refs",
                "need": list(OPTIMIZE_LIMITS["params"]),
                "why": "精绘要 `path` + `imageUrl`，**且都必须是上传接口的返回值**"
                       "（自己拼的路径不认）"}
    for v, label in ((width, "width"), (height, "height")):
        if v is not None and str(v).strip() != "" and float(v) > OPTIMIZE_LIMITS["max_side"]:
            return {"ok": False, "denied": True, "rule": "optimize_size_limit",
                    "side": label, "value": v, "max": OPTIMIZE_LIMITS["max_side"],
                    "why": "精绘图片尺寸限制为 %d×%d"
                           % (OPTIMIZE_LIMITS["max_side"], OPTIMIZE_LIMITS["max_side"])}
    return {"ok": True, "readonly": True, "points": OPTIMIZE_LIMITS["points_per_call"],
            "note": "每次消耗 %d 个点数（点数**不再充值** ⇒ 每次都要算清）"
                    % OPTIMIZE_LIMITS["points_per_call"]}


def check_task_state(state: Any = None) -> dict:
    """R-H213 · 任务四态：0 已提交 / 10 已完成 / 20 失败 / 30 进行中。"""
    if state is None or str(state).strip() == "":
        return {"ok": False, "denied": True, "rule": "missing_state",
                "states": dict(TASK_STATES),
                "why": "没有 state 就别下结论（**未测不按绿**）"}
    try:
        s = int(state)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "bad_state",
                "state": str(state), "states": dict(TASK_STATES)}
    if s not in TASK_STATES:
        return {"ok": False, "denied": True, "rule": "bad_state",
                "state": s, "states": dict(TASK_STATES),
                "why": "state 只认 0 / 10 / 20 / 30"}
    done = s == 10
    failed = s == 20
    return {"ok": True, "readonly": True, "state": s, "cn": TASK_STATES[s],
            "done": done, "failed": failed,
            "note": ("已完成 ⇒ 记住：**结果地址会失效，必须落到可控落点**"
                     if done else ("失败 ⇒ 如实报，别当成功" if failed
                                   else "还没完 ⇒ 继续轮询（带游标），**别当失败**"))}


def check_section(section: str = "") -> dict:
    """R-H213 · 区域口径：查询接口 header 的 `section`，**中国区传 cn**。"""
    s = str(section or "").strip().lower()
    if not s:
        return {"ok": False, "denied": True, "rule": "missing_section",
                "hint": "中国区传 %s" % SECTION_CN,
                "why": "查询任务结果必须带 section（中国区 = %s）" % SECTION_CN}
    return {"ok": True, "readonly": True, "section": s,
            "is_cn": s == SECTION_CN}


def must_preflight(app_components: Optional[List] = None,
                   looked_up: bool = False) -> dict:
    """R-H217 · **请求前必须预检**：撞上不支持组件 ⇒ **别把请求发出去**。

    为什么要"事前"而不是"事后"：等 324010 回来才认错 = **白花一次请求**；
    而积分**不再补充** ⇒ 每一次浪费都是真金白银。
    数据来源：**LOOKUP 的 appInfo**（这就是 LOOKUP 的第三重角色）。
    """
    if not looked_up:
        return {"ok": False, "denied": True, "rule": "preflight_requires_lookup",
                "why": "预检的数据来自 **LOOKUP 的 appInfo** ⇒ 先 LOOKUP 再预检，"
                       "别凭记忆猜这个 app 支持什么"}
    comps = [str(c) for c in (app_components or []) if str(c or "").strip()]
    if not comps:
        return {"ok": False, "denied": True, "rule": "no_components_declared",
                "why": "appInfo 里没拿到组件清单 ⇒ **不许当作「干净」**"
                       "（未测不按绿）；要么补齐，要么如实标未知"}
    hit = [c for c in comps
           if any(u.lower() in c.lower() for u in UNSUPPORTED_COMPONENTS)]
    if hit:
        return {"ok": False, "denied": True, "rule": "preflight_blocked",
                "components": hit, "unsupported": list(UNSUPPORTED_COMPONENTS),
                "why": "**请求前就拦住**：带这些组件的 app 不走 API"
                       "（官方：数字分身 / wordart / 合照 user upload / Video 组件）"}
    return {"ok": True, "readonly": True, "components": comps,
            "note": "预检通过 ⇒ 再发 GENERATE（这样不会白花一次请求）"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / primitives / redlines / policy / forensics
    / gate_localize / gate_component / classify_error。不装、不调、不出网。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE, "skill_source": SKILL_SOURCE,
                "primitives": len(PRIMITIVES), "key_envs": list(EXTERNAL_KEY_ENVS),
                "forensics": FORENSICS,
                "note": "接口文档不在盘上、密钥未配（取证实测）⇒ 『能调』是**待接**，不是现状"}
    if op == "primitives":
        return {"ok": True, "readonly": True,
                "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "policy":
        return {"ok": True, "readonly": True, **POLICIES,
                "unsupported_components": list(UNSUPPORTED_COMPONENTS)}
    if op == "forensics":
        return {"ok": True, "readonly": True, **FORENSICS}
    if op == "gate_localize":
        return must_localize(params, params.get("local_path") or "")
    if op == "gate_component":
        return refuse_unsupported(params.get("component") or "")
    if op == "classify_error":
        return classify_error(params.get("code"), params.get("message") or "")
    # ── R-H211 · API 能力矩阵 ──
    if op == "api":
        return {"ok": True, "readonly": True, "base": API_BASE,
                "endpoints": [dict(x) for x in API_ENDPOINTS],
                "map": dict(PRIMITIVE_ENDPOINT_MAP),
                "rule": "创建类 = POST …/images/*；查询类 = GET …/{appId|taskId}"}
    if op == "gate_endpoint":
        return check_endpoint(params.get("endpoint") or "")
    if op == "gate_lookup_first":
        return must_lookup_first(bool(params.get("looked_up")),
                                 params.get("app_id") or "")
    if op == "gate_task_id":
        return must_task_id(params.get("task_id") or "",
                            params.get("for") or "poll")
    if op == "service_window":
        return check_service_window()
    if op == "scale":
        return {"ok": True, "readonly": True, "position": PLATFORM_POSITION,
                **PLATFORM_SCALE}
    # ── R-H213 · 接口详情（参数契约 + 硬限制）──
    if op == "params":
        return {"ok": True, "readonly": True,
                "auth": {"base_url": AUTH_BASE_URL, "header": AUTH_HEADER},
                "upload_limits": {k: (list(v) if isinstance(v, tuple) else v)
                                  for k, v in UPLOAD_LIMITS.items()},
                "generate_fields": [dict(x) for x in GENERATE_FIELDS],
                "size_id_map": dict(SIZE_ID_MAP),
                "optimize_limits": {k: (list(v) if isinstance(v, tuple) else v)
                                    for k, v in OPTIMIZE_LIMITS.items()},
                "task_states": dict(TASK_STATES),
                "section_cn": SECTION_CN,
                "credits": dict(CREDIT_SYSTEM)}
    if op == "persistence":
        return {"ok": True, "readonly": True, **RESULT_PERSISTENCE}
    if op == "gate_upload":
        return check_upload(params.get("files"), params.get("image_url") or "")
    if op == "gate_generate_params":
        return check_generate_params(params.get("params") or {})
    if op == "gate_optimize":
        return check_optimize(params.get("path") or "",
                              params.get("image_url") or "",
                              params.get("width"), params.get("height"))
    if op == "gate_task_state":
        return check_task_state(params.get("state"))
    if op == "gate_section":
        return check_section(params.get("section") or "")
    # ── R-H214 · 错误码体系 / 定价 / 使用范式 / 未解冲突 ──
    if op == "error_codes":
        codes = [dict(x) for x in ERROR_CODES] + [dict(x) for x in _extra_error_codes()]
        return {"ok": True, "readonly": True,
                "codes": codes, "count": len(codes),
                "as_of": ERROR_CODE_AS_OF,
                "official_title_count": 18,
                "is_exhaustive": False,
                "retryable": [x["code"] for x in codes if x["retry"]],
                "note": "官方标题写「18 个」，**但 18 不是上限**（后续又给 3 个）⇒ "
                        "用 **as_of 语义**，**不承诺全集**；"
                        "retry 的判据＝『钱的问题』还是『节奏的问题』"}
    if op == "gate_retry":
        return check_retry(params.get("code"), params.get("attempts") or 0,
                           params.get("max_attempts") or 3)
    if op == "pricing":
        return {"ok": True, "readonly": True, **PRICING,
                "note": "⚠️ 标称单价与套餐折算单价对不上 ⇒ unit_conflict=True，"
                        "如实并排不解释"}
    if op == "paradigms":
        return {"ok": True, "readonly": True,
                "paradigms": [dict(x) for x in USAGE_PARADIGMS],
                "note": "**计价口径因范式而异**——表单式按张 · 节点式按节点 · "
                        "精绘按张 · 图生视频按个"}
    if op == "estimate":
        return estimate_cost(params.get("paradigm") or "", params.get("count") or 1)
    if op == "conflicts":
        return {"ok": True, "readonly": True, **OPEN_CONFLICTS,
                "note": "两处未解冲突**并排记**，等主人一句话；"
                        "**不擅自改已关账的闸**"}
    # ── R-H215 · 官方五原语对照表 + 不支持组件出处 ──
    if op == "primitives_official":
        return {"ok": True, "readonly": True, "count": 5,
                "source": "官方《五原语》表（主人逐条给）",
                "map": [{"n": i + 1, "primitive": e["primitive"], "cn": e["cn"],
                         "endpoint": e["path"]}
                        for i, e in enumerate(API_ENDPOINTS)],
                "double_source": True,
                "note": "官方 5/5 与我们 R-H206 的推定**逐条一致** ⇒ 双源印证"}
    if op == "unsupported_evidence":
        return {"ok": True, "readonly": True, **UNSUPPORTED_EVIDENCE,
                "components": list(UNSUPPORTED_COMPONENTS),
                "note": "四个组件**出处均已证**（R-H215 起：Video 组件不再是『待核』）"}
    # ── R-H216 · 官方三条带牙用例对账 ──
    if op == "teeth_cases":
        return {"ok": True, "readonly": True,
                "cases": [dict(x) for x in TEETH_CASES],
                "count": len(TEETH_CASES),
                "all_match": all(x["match"] for x in TEETH_CASES),
                "allowed_landings": list(ALLOWED_LANDINGS),
                "note": "官方三条与我方三条**逐条一致**（双源印证）；"
                        "唯一增量＝落点清单明确为『本地 CDN / 工作区』"}
    # ── R-H217 · 官方四条红线对账 + 请求前预检 ──
    if op == "redlines_official":
        return {"ok": True, "readonly": True,
                "redlines": [dict(x) for x in REDLINES_OFFICIAL],
                "count": len(REDLINES_OFFICIAL),
                "all_have_gates": all(x["our_gates"] for x in REDLINES_OFFICIAL),
                "note": "**4/4 全部已有现成闸** ⇒ 本刀不新造闸，只做对账"}
    if op == "lookup_roles":
        return {"ok": True, "readonly": True,
                "roles": [dict(x) for x in LOOKUP_ROLES],
                "note": "LOOKUP 有**三重角色**：拿依赖参数 / 续期 / **预检组件**"}
    if op == "gate_preflight":
        return must_preflight(params.get("components"),
                              bool(params.get("looked_up")))
    raise ValueError("未知 op %r（可用：status/primitives/redlines/policy/forensics/"
                     "gate_localize/gate_component/classify_error/api/"
                     "gate_endpoint/gate_lookup_first/gate_task_id/"
                     "service_window/scale/params/persistence/gate_upload/"
                     "gate_generate_params/gate_optimize/gate_task_state/"
                     "gate_section/error_codes/gate_retry/pricing/paradigms/"
                     "estimate/conflicts/primitives_official/"
                     "unsupported_evidence/teeth_cases/redlines_official/"
                     "lookup_roles/gate_preflight）" % (op,))


HONEST_BOUNDARY = (
    "本骨架只保证『密钥只从池借、结果必须落盘、不调不支持组件、余额不足如实报』"
    "四条判据可执行。它**不保证『a1.art 能用』** —— "
    "取证实测：盘上 a1art 命中 0、六个候选 env 全未设置、保险箱里没有 a1art 密钥、"
    "**真实接口文档不在盘上（endpoint / 入参契约一律未取证，本骨架不编造）**。"
    "另：平台正在**逐步停止服务** ⇒ 它是一条**存量通道**，不是长期基础设施。"
)
