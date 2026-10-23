# -*- coding: utf-8 -*-
"""社交发布 · 平台表（纯数据，无 IO、无副作用、无网络）。

口径三条：
  · 一行数据 = 一个平台。这里只描述"平台是什么"，不描述"该怎么请求" ——
    投递实现属于执行链路，本仓尚未实现，不在这里假装。
  · 未登记的平台一律 spec_for() -> None，调用方必须如实报 spec_known=False。
    不猜、不补默认值：猜测会把"不知道"写成"知道"。
  · official_api=False 表示该平台没有官方发布接口。这是事实记录，不是待办 ——
    本舱区不做，也不会用浏览器自动化去绕。

delivery / daily_limit / credential_field 取自各平台官方文档，是"参考数据"，
不是本机核验结果；任何响应都不得把它当成已证实的本地状态。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

# 四条门禁的字段名：前三门是"平台闸"，第四门只说凭据在不在本机。
GATE_FLAGS = ("app_registered", "scope_audited", "account_authorized",
              "credential_registered")

DECLARATION_FLAGS = ("app_registered", "scope_audited", "account_authorized")

# 旧形状（没有 platforms 键）读成一个隐式平台。给它一个显式 id，
# 免得"把旧布尔当成某个平台的布尔"这件事藏在代码里。
# 探针有效期：一次通过不是永久证明。默认 12 小时（2026-09-18 定），可由
# social.json 的 probe_ttl_seconds 覆盖。过期一律降级为"未核验"，不是"失败"。
DEFAULT_PROBE_TTL_SECONDS = 12 * 3600

# 路由 = "我们打算怎么驱动它"。这不是平台事实，是我们自己的声明，
# 所以必须显式写出来：同一个平台走触手还是走官方接口，门禁语义完全不同，
# 混着读就是把 A 路由的结论安到 B 路由头上。空串 = 没声明，不是"默认官方"。
ROUTE_OFFICIAL = "official"
ROUTE_TENTACLE = "tentacle"

ROUTE_LABELS = {
    ROUTE_OFFICIAL: "官方接口",
    ROUTE_TENTACLE: "本机触手",
}

ROUTE_NOTES = {
    ROUTE_OFFICIAL: ("官方接口路由：登记 / 过审 / 授权三道闸 + 凭据 + 只读探针，"
                     "每一格都能证伪。"),
    ROUTE_TENTACLE: ("本机触手路由：不开开发者应用、不走官方三步闸，改用本机已登录的"
                     "浏览器会话投递。代价写在明处 —— 这条路由没有可证伪的只读探针："
                     "官方令牌过期会给 401，可以判、可以退避；而平台对自动化是静默降权，"
                     "本机看不出任何异常，直到号废。所以它一律不参与无人值守。"),
}

# 「未启用」= 登记表里的一句意愿声明，**不参与门禁计算**：
# 它说的是"这个渠道本机不打算用"，不是"它现在能不能跑"（那是 blocked_by 的事），
# 也不放行、不拦截任何请求。
# 缺字段 != 声明为 true，所以未声明时什么都不印 —— 别把"没写"读成"已启用"。
ENABLED_LABEL_DISABLED = "未启用"

LEGACY_PLATFORM_ID = "legacy"
LEGACY_PLATFORM_LABEL = "未命名平台（旧形状）"

PLATFORM_SPECS = (
    {
        "id": "tiktok",
        "label": "TikTok",
        "official_api": True,
        "delivery": "三步：init → 分片 PUT → status/fetch",
        "audit_gate": "未过审的客户端所发内容只能私密可见",
        "daily_limit": None,
        "credential_field": "access_token",
    },
    {
        "id": "youtube",
        "label": "YouTube Shorts",
        "official_api": True,
        "delivery": "单步可续传上传：videos.insert",
        "audit_gate": "未验证项目上传的视频锁为私密",
        "daily_limit": 100,
        "credential_field": "access_token",
    },
    {
        "id": "instagram",
        "label": "Instagram Reels",
        "official_api": True,
        "delivery": "两步：media 建容器 → media_publish",
        "audit_gate": "需商业/创作者账号并绑定主页",
        "daily_limit": None,
        "credential_field": "access_token",
    },
    {
        "id": "douyin",
        "label": "抖音",
        "official_api": True,
        "delivery": "三步：create → 上传 → 发布",
        "audit_gate": "需主体资质并申请发布权限",
        "daily_limit": None,
        "credential_field": "client_secret",
    },
    {
        "id": "bilibili",
        "label": "B 站",
        "official_api": True,
        "delivery": "分 P / 分片投递",
        "audit_gate": "开放平台权限以企业/邀请制为主",
        "daily_limit": None,
        "credential_field": "access_token",
    },
    {
        "id": "kuaishou",
        "label": "快手",
        "official_api": True,
        "delivery": "三步：create → 上传 → 发布",
        "audit_gate": "需开放平台资质",
        "daily_limit": None,
        "credential_field": "access_token",
    },
    {
        "id": "wechat_channels",
        "label": "微信视频号",
        "official_api": False,
        "delivery": "",
        "audit_gate": "无官方发布接口：官方文档明确不提供代用户发布",
        "daily_limit": 0,
        "credential_field": "",
    },
)

_SPEC_BY_ID = {spec["id"]: spec for spec in PLATFORM_SPECS}


def spec_for(platform_id):
    """平台的参考数据；未登记的平台返回 None —— 不猜。"""
    return _SPEC_BY_ID.get(str(platform_id or "").strip().lower())


def normalize_route(value):
    """路由名归一；没有声明就返回空串 —— 空串不是"官方"，不许替人默认。"""
    return str(value or "").strip().lower()


def is_tentacle(value):
    return normalize_route(value) == ROUTE_TENTACLE


def route_label(value):
    """路由的人读名称；认不出的路由如实写出来，不假装成已登记的路由。"""
    key = normalize_route(value)
    if not key:
        return ""
    return ROUTE_LABELS.get(key, "未登记路由（%s）" % key)


def route_note(value):
    """路由的代价说明；没声明路由就没有说明，不编。"""
    return ROUTE_NOTES.get(normalize_route(value), "")


def declared_platforms(config):
    """把 social.json 归一成 (平台条目列表, schema 名, 结构错误)。

    条目形如::

        {"id": "tiktok", "label": "TikTok",
         "flags": {"app_registered": True, ...}, "spec": {...} | None}

    schema:
      "legacy" —— 没有 platforms 键：按旧形状读成单一隐式平台（空对象也算，
                  它的含义是"一个未命名平台的四项都未登记"，不是"没有平台"）
      "multi"  —— platforms 是对象：逐条读
    """
    if not isinstance(config, dict):
        return [], "legacy", "社交配置顶层不是对象"
    raw = config.get("platforms")
    if raw is None:
        return [{
            "id": LEGACY_PLATFORM_ID,
            "label": LEGACY_PLATFORM_LABEL,
            "flags": {flag: bool(config.get(flag)) for flag in GATE_FLAGS},
            "spec": None,
        }], "legacy", ""
    if not isinstance(raw, dict):
        return [], "multi", "社交配置的 platforms 不是对象"
    entries = []
    for key, value in raw.items():
        platform_id = str(key or "").strip().lower()
        if not platform_id:
            return [], "multi", "社交配置的 platforms 里有空平台名"
        if not isinstance(value, dict):
            return [], "multi", "社交配置的 platforms.%s 不是对象" % platform_id
        spec = spec_for(platform_id)
        label = str(value.get("label") or "").strip()
        probe_raw = value.get("capability_probe")
        if probe_raw is not None and not isinstance(probe_raw, dict):
            return [], "multi", (
                "社交配置的 platforms.%s.capability_probe 不是对象" % platform_id)
        entries.append({
            "id": platform_id,
            "label": label or (spec["label"] if spec else platform_id),
            "flags": {flag: bool(value.get(flag)) for flag in GATE_FLAGS},
            "spec": spec,
            "probe_raw": probe_raw,
            "enabled_declared": "enabled" in value,
            "enabled": bool(value.get("enabled")),
        })
    return entries, "multi", ""


def _parse_epoch(value):
    """把 checked_at 解析成 epoch 秒；解析不了就返回 None —— 不猜。

    接受 epoch 秒（数字或数字字符串）与 ISO8601。ISO8601 不带时区时按本机
    时区解释（fromisoformat 的默认行为），带 Z 或带偏移按其自身时区。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def evaluate_probe(spec, credential_present, raw, ttl_seconds=DEFAULT_PROBE_TTL_SECONDS,
                   now=None, route=""):
    """探针三态：ok / stale / unknown。

    ok    —— 有可解析的 checked_at 且未超期：这是唯一能为 True 的状态。
    stale —— 探过但过期，或"通过"却没有时间戳：降级为未核验。
    unknown —— 没探过、没凭据、没探针定义、上次未通过。

    status 管"能不能放行"，state 管"为什么"——它把 unprobed（已登记、没探过）
    与 spec_unknown（连探针定义都没有）分开，这样上级不必去看 reason 猜成因。
    """
    now = time.time() if now is None else float(now)
    try:
        ttl = int(ttl_seconds)
    except (TypeError, ValueError):
        ttl = DEFAULT_PROBE_TTL_SECONDS
    if ttl <= 0:
        ttl = DEFAULT_PROBE_TTL_SECONDS
    result = {"status": "unknown", "state": "unknown", "known": False, "reason": "",
              "checked_at": None, "checked_age_seconds": None, "ttl_seconds": ttl}

    if spec is not None and not spec.get("official_api"):
        result["state"] = "unsupported"
        result["reason"] = "该平台没有官方发布接口，本舱区不做，故无探针"
        return result
    if spec is None:
        result["state"] = "spec_unknown"
        result["reason"] = "未登记的平台：没有探针定义，不猜"
        return result
    if is_tentacle(route) and not isinstance(raw, dict):
        # 触手路由既没有令牌、也没有官方只读接口；它的探测对象是"本机是否已有该平台的
        # 登录会话"，而这个探针本仓尚未实现。没实现的探针就是没有探针，
        # 所以这里只能报未探测 —— 绝不许把官方探针的结论搬过来当它的结论。
        result["state"] = "unprobed"
        result["reason"] = ("触手路由：探测对象是「本机是否已有该平台的登录会话」，"
                            "该探针尚未实现，故无法核验")
        return result
    if not credential_present:
        result["state"] = "unprobed"
        result["reason"] = "凭据未登记：无凭据不发起探针"
        return result
    if not isinstance(raw, dict):
        result["state"] = "unprobed"
        result["reason"] = "探针尚未实现：凭据已登记，但本机还没有只读能力探针"
        return result

    if str(raw.get("status") or "").strip().lower() != "ok":
        detail = str(raw.get("detail") or "未给出原因")[:120]
        result["state"] = "failed"
        result["reason"] = "上次探测未通过：%s" % detail
        return result

    checked = raw.get("checked_at")
    result["checked_at"] = checked
    epoch = _parse_epoch(checked)
    if epoch is None:
        result["status"] = "stale"
        result["state"] = "stale"
        result["reason"] = "探测结果没有可解析的时间戳，无法判断新鲜度，按过期处理"
        return result
    age = int(max(0, now - epoch))
    result["checked_age_seconds"] = age
    if age > ttl:
        result["status"] = "stale"
        result["state"] = "stale"
        result["reason"] = "上次成功探测在 %ss 前，已超过有效期 %ss，需复验" % (age, ttl)
        return result
    result["status"] = "ok"
    result["state"] = "ok"
    result["known"] = True
    result["reason"] = "%ss 前探测通过，仍在有效期内" % age
    return result
