"""GBT小土豆V8 · 自有靶场只读扫描器（GET only，不破坏）

对 127.0.0.1 的自有靶场做只读探测，产出结构化 findings（供 bounty 工作台录单）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def _get(base: str, path: str, params: dict | None = None, timeout: float = 5.0):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "gbt-lab-scan/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, {}, str(e)


def scan(base: str) -> list:
    findings = []

    # 1) 反射型 XSS：p 标签内原样回显
    marker = "<script>alert(1)</script>"
    st, _, body = _get(base, "/search", {"q": marker})
    if st == 200 and marker in body:
        findings.append({
            "title": "反射型 XSS：/search 未转义回显", "severity": "medium",
            "cwe": "CWE-79", "cvss": "6.1",
            "steps": "GET /search?q=<script>alert(1)</script>，响应体原样包含该 payload",
            "impact": "可执行任意前端脚本（钓鱼/会话窃取）",
            "remediation": "输出上下文转义（HTML escape），加 CSP",
            "evidence": body[:300],
        })

    # 2) IDOR：无鉴权拿 id=2 的管理员记录
    st, _, body = _get(base, "/api/user", {"id": "2"})
    if st == 200 and ("api_token" in body or '"role": "admin"' in body.replace("'", '"')):
        findings.append({
            "title": "IDOR：/api/user?id= 无鉴权读取他人（管理员）记录", "severity": "high",
            "cwe": "CWE-639", "cvss": "7.5",
            "steps": "GET /api/user?id=2，直接返回 admin 记录与 api_token",
            "impact": "越权读取敏感数据",
            "remediation": "鉴权 + 对象级授权校验（只允许读自己）",
            "evidence": body[:300],
        })

    # 3) 路径穿越：../secret.txt
    st, _, body = _get(base, "/download", {"file": "../secret.txt"})
    if st == 200 and "SECRET-LAB-FLAG" in body:
        findings.append({
            "title": "路径穿越：/download 可读 public 之外文件", "severity": "high",
            "cwe": "CWE-22", "cvss": "7.5",
            "steps": "GET /download?file=../secret.txt，返回靶场 secret",
            "impact": "任意文件读取",
            "remediation": "规范化路径 + 白名单目录校验",
            "evidence": body[:300],
        })

    # 4) 调试信息泄漏
    st, _, body = _get(base, "/debug")
    if st == 200 and '"debug": true' in body.replace("'", '"'):
        findings.append({
            "title": "调试信息泄漏：/debug 暴露环境与工作目录", "severity": "low",
            "cwe": "CWE-200", "cvss": "3.1",
            "steps": "GET /debug，返回 debug=true、env、cwd",
            "impact": "泄露部署细节，辅助后续攻击",
            "remediation": "生产关闭 debug 端点",
            "evidence": body[:300],
        })

    # 5) 未授权管理页
    st, _, body = _get(base, "/admin")
    if st == 200 and "Admin Console" in body:
        findings.append({
            "title": "未授权访问：/admin 无鉴权", "severity": "high",
            "cwe": "CWE-306", "cvss": "8.1",
            "steps": "GET /admin，直接返回管理页",
            "impact": "未授权进入管理功能",
            "remediation": "强制登录 + 角色校验",
            "evidence": body[:300],
        })

    # 6) 缺安全响应头
    st, hdrs, _ = _get(base, "/")
    missing = [h for h in ("Content-Security-Policy", "X-Content-Type-Options",
                           "X-Frame-Options", "Referrer-Policy")
               if h.lower() not in {k.lower() for k in hdrs}]
    if st == 200 and missing:
        findings.append({
            "title": "缺少安全响应头", "severity": "low", "cwe": "CWE-693",
            "cvss": "2.6",
            "steps": "GET /，响应缺少：" + "、".join(missing),
            "impact": "点击劫持/嗅探/MIME 混淆风险",
            "remediation": "加 CSP / X-Content-Type-Options / X-Frame-Options / Referrer-Policy",
            "evidence": json.dumps({"missing_headers": missing}, ensure_ascii=False),
        })

    return findings


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18866"
    print(json.dumps(scan(base), ensure_ascii=False, indent=2))
