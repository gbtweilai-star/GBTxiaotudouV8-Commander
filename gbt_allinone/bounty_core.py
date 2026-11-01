"""GBT小土豆V8 · 赏金核心：CVSS 3.1 计算 / CWE 映射 / 发现状态机 / 报告

从 bounty.py 拆出来，避免单文件过大；bounty.py 继续做项目/范围/账本。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import math

# ── CVSS 3.1 base score ────────────────────────────────────────────────
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}


def _roundup(x: float) -> float:
    """CVSS 3.1 Roundup：>= 输入的最小一位小数。"""
    return math.ceil(round(x, 5) * 10) / 10.0


def _parse_vector(vector: str) -> dict:
    parts = {}
    for tok in str(vector or "").strip().split("/"):
        if ":" in tok:
            k, v = tok.split(":", 1)
            parts[k.upper()] = v.upper()
    return parts


def cvss3(vector: str) -> dict:
    """CVSS 3.1 base score（只算 base，不碰 temporal/environmental）。"""
    p = _parse_vector(vector)
    need = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
    missing = [k for k in need if k not in p]
    if missing:
        return {"ok": False, "reason": "向量缺 %s（例：AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H）" % missing}
    try:
        scope_changed = p["S"] == "C"
        iss = 1 - (1 - _CIA[p["C"]]) * (1 - _CIA[p["I"]]) * (1 - _CIA[p["A"]])
        if scope_changed:
            impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
        else:
            impact = 6.42 * iss
        pr = (_PR_C if scope_changed else _PR_U)[p["PR"]]
        exploit = 8.22 * _AV[p["AV"]] * _AC[p["AC"]] * pr * _UI[p["UI"]]
        if impact <= 0:
            base = 0.0
        elif scope_changed:
            base = _roundup(min(1.08 * (impact + exploit), 10))
        else:
            base = _roundup(min(impact + exploit, 10))
    except KeyError as e:
        return {"ok": False, "reason": "向量取值非法：%s" % e}
    sev = severity_of(base)
    return {"ok": True, "vector": "CVSS:3.1/" + "/".join(
        "%s:%s" % (k, p[k]) for k in need), "base_score": round(base, 1),
        "severity": sev}


def severity_of(score: float) -> str:
    s = float(score)
    if s <= 0:
        return "none"
    if s < 4.0:
        return "low"
    if s < 7.0:
        return "medium"
    if s < 9.0:
        return "high"
    return "critical"


def default_vector(severity: str) -> str:
    sev = severity_of({"none": 0, "low": 2.6, "medium": 5.4, "high": 8.1, "critical": 9.8}
                      .get(str(severity).lower(), 5.4))
    table = {
        "critical": "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",   # 9.8
        "high": "AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",       # 8.8
        "medium": "AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",     # 6.1
        "low": "AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N",        # 3.1
        "none": "AV:N/AC:H/PR:N/UI:R/S:U/C:N/I:N/A:N",
    }
    return "CVSS:3.1/" + table.get(sev, table["medium"])


# ── CWE 映射（常见洞；没收录的如实返回未知）──────────────────────────
CWE = {
    "CWE-79": {"name": "跨站脚本（XSS）",
               "fix": "按输出上下文转义（HTML/JS/URL）；加严格 CSP；框架默认转义不要关。"},
    "CWE-89": {"name": "SQL 注入",
               "fix": "全部参数化查询/预编译语句；禁止字符串拼接 SQL；最小权限 DB 账号。"},
    "CWE-22": {"name": "路径穿越",
               "fix": "规范化路径后校验仍在白名单目录内（realpath + relative_to）；禁用 ../。"},
    "CWE-200": {"name": "信息泄漏",
                "fix": "生产关闭 debug 端点；错误页不回显堆栈/环境；日志脱敏。"},
    "CWE-306": {"name": "关键功能缺少认证",
                "fix": "管理功能强制登录 + 角色校验；默认拒绝（deny by default）。"},
    "CWE-639": {"name": "IDOR / 越权访问对象",
                "fix": "对象级授权：每次访问校验 resource.owner == current_user；不要用可枚举 id 直查。"},
    "CWE-693": {"name": "防护机制缺失（安全头等）",
                "fix": "加 CSP / X-Content-Type-Options: nosniff / X-Frame-Options / Referrer-Policy。"},
    "CWE-78": {"name": "OS 命令注入",
               "fix": "避免 shell=True；参数用数组传递；白名单校验；沙箱执行。"},
    "CWE-352": {"name": "CSRF",
                "fix": "同站 cookie + CSRF token + 校验 Origin/Referer。"},
    "CWE-918": {"name": "SSRF",
                "fix": "URL 白名单/内网地址黑名单；DNS 解析后校验 IP；禁用重定向跟随。"},
}


def cwe_info(cwe: str) -> dict:
    key = str(cwe or "").strip().upper().replace("CWE-", "CWE-")
    if key in CWE:
        return {"ok": True, "cwe": key, **CWE[key]}
    return {"ok": False, "cwe": key or None, "name": "未收录", "fix": "按通用修复原则处理；建议补充到 CWE 表"}


# ── 提交状态机 ────────────────────────────────────────────────────────
STATUSES = ["draft", "submitted", "triaged", "duplicate", "paid", "closed"]
TRANSITIONS = {
    "draft": {"submitted", "closed"},
    "submitted": {"triaged", "duplicate", "closed"},
    "triaged": {"paid", "closed"},
    "duplicate": {"closed"},
    "paid": {"closed"},
    "closed": set(),
}


def can_transition(frm: str, to: str) -> bool:
    return to in TRANSITIONS.get(frm, set())
