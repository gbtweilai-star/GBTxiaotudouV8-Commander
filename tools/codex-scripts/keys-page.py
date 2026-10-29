# -*- coding: utf-8 -*-
# gbt-instrument: 本件是**量具/生成器**（读凭据槽位状态并生成页面），它自己提到的路径不算"有人引用"。
"""密钥台生成器（2026-10-01 第 63 轮 · 主人令「包含密钥生成页面都要给我做好」）。

## 它回答什么

主人要的是「**密钥在哪、怎么用**」一眼看见 —— 而不是记住一堆 setx 命令。

**它绝不落任何明文**（本仓硬规 + 安全钩子）：
  · 只从**本机密钥文件**（`deploy/cloud-10/.dev.vars`）与**环境变量**读；
  · 页面里只出现**掩码**（前 4 位 + 长度）与**槽位状态**（在/不在）；
  · 生成的 HTML **零脚本零外链**（静态可读，纯文本可复制，file:// 也能看）。

## 用法

    py -3.14 tools/codex-scripts/keys-page.py

产物：`holo_pet/assets/keys/index.html`（面板静态发出去：`http://127.0.0.1:8765/assets/keys/index.html`）。
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "holo_pet" / "assets" / "keys" / "index.html"
DEVVARS = ROOT / "deploy" / "cloud-10" / ".dev.vars"


def _user_env(name: str) -> str:
    """读**用户级**环境变量（`setx` 写的那个）。读不到就回空串，由调用方回退进程环境。

    为什么非要有这一层（本会话实测的真缺陷）：`setx` 改的是注册表，**已在运行的进程**
    继承的是旧环境 —— 拿进程环境当"本机设置"会显示过期值（实测：进程里 `loca****`，
    注册表里已是新令牌）。**读数必须取自真源**。
    """
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::GetEnvironmentVariable('%s','User')" % name],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        return (out.stdout or "").strip()
    except Exception:                                  # noqa: BLE001
        return ""


def masked(v: str) -> str:
    """一律只回掩码：前 4 位 + 长度（明文永远不出这个函数）。"""
    v = str(v or "")
    return "(未设)" if not v else "%s**** len=%d" % (v[:4], len(v))


def read_devvars() -> dict:
    out = {}
    if DEVVARS.is_file():
        for ln in DEVVARS.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, _, v = ln.partition("=")
                out[k.strip()] = v.strip()
    return out


def slots() -> list:
    dv = read_devvars()
    tok = dv.get("GBT_ENDPOINT_TOKEN", "")
    rows = [
        {"id": "cloud_endpoint_token",
         "what": "云端端点令牌（Worker gbt-potato-cloud-10；/v1 与 /rpc 都认它）",
         "where": "deploy/cloud-10/.dev.vars · Cloudflare secret GBT_ENDPOINT_TOKEN / GBT_ENDPOINT_TOKENS",
         "state": ("在（本机）" if tok else "本机没有 ⇒ 要换一把（wrangler secret put）"),
         "mask": masked(tok),
         "load_env": "GBT_LLM_API_KEY（对话面用） · GBT_POTATO_API_KEY（框架 LLM 链用）",
         "rotate": "printf '%s' \"$TOK\" | npx wrangler secret put GBT_ENDPOINT_TOKENS --config wrangler.toml"
                   "（**复数那条优先**；单数那条也要一起换，两条同值）"},
        {"id": "llm_endpoint", "what": "我们自己的权重端点（千问原生）",
         "where": "deploy/cloud-10/wrangler.toml [vars] LLM_ENDPOINT / LLM_MODEL",
         "state": "**空**（现在跑托管上游 ⇒ weights_ours:false）",
         "mask": "—", "load_env": "—",
         "rotate": "把权重包成 OpenAI 兼容 /v1 → 填 LLM_ENDPOINT 与 LLM_MODEL → npx wrangler deploy（代码不动）"},
        {"id": "image_endpoint", "what": "图像面自建端点（真无审查那一档）",
         "where": "deploy/cloud-10/wrangler.toml [vars] IMAGE_ENDPOINT / IMAGE_MODEL / IMAGE_API_KEY",
         "state": "**空**（现有两档：自建端点+免费上游 · Workers AI 兜底）",
         "mask": "—", "load_env": "—",
         "rotate": "上游包成 /v1/images/generations → 填三个值 → npx wrangler deploy（代码不动）"},
        {"id": "owner_token", "what": "云端 /admin/grant 的主人令牌（发云端运行时授权）",
         "where": "Cloudflare secret OWNER_TOKEN",
         "state": "**未配**（fail-closed：没它云端没有自发授权的口子）",
         "mask": "—", "load_env": "—",
         "rotate": "npx wrangler secret put OWNER_TOKEN（它与云端 GRANTED_SCOPES 是两件事）"},
    ]
    for k in ("GBT_LLM_API_KEY", "GBT_POTATO_API_KEY", "GBT_POTATO_BASE_URL", "GBT_POTATO_MODEL",
              "GBT_LLM_PROVIDER", "UNIFIED_API_KEY"):
 # 2026-10-01 修（真缺陷）：**读用户注册表**，不是读本进程的环境。
        #   病根：`setx` 写的是**用户级环境变量**，而已在运行的进程（含生成器、含那班自动化）
        #   继承的是它启动时那份旧环境 ⇒ 页面上会把主人**已经设过**的变量显示成「未设」，
        #   也会把旧值当现值（本会话实测：`GBT_POTATO_API_KEY` 进程里还是 `loca****`，
        #   而注册表里早已是新令牌）。**读数必须取自真源**：注册表(User) → 回退进程环境。
        v = _user_env(k) or os.environ.get(k, "")
        is_secret = ("KEY" in k) or ("TOKEN" in k)
        rows.append({"id": k, "what": "环境变量（本机 · 用户级）",
                     "where": "setx %s（用户注册表）" % k,
                     "state": "在" if v else "未设",
                     "mask": masked(v) if is_secret else (v[:44] or "(未设)"),
                     "load_env": "—",
                     "rotate": "setx %s \"<值>\"（设完**重启对话面/App**才生效）" % k})
    return rows


def build_html(rows: list) -> str:
    h = ["<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
         "<title>密钥台 · GBT小土豆V8</title>",
         "<link rel=\"stylesheet\" href=\"../../window.css\">",
         "<style>body{background:var(--gbt-deep);color:var(--gbt-text);font:14px/1.7 'Segoe UI','Microsoft YaHei',sans-serif;margin:0;padding:28px}",
         "h1{font-size:19px;margin:0 0 6px;color:var(--gbt-gold)}",
         ".sub{color:var(--gbt-dim);font-size:12.5px;margin-bottom:16px}",
         "table{width:100%;border-collapse:collapse;margin-top:8px}",
         "th,td{padding:9px 10px;border-bottom:1px solid var(--gbt-hair);text-align:left;font-size:12.5px;vertical-align:top}",
         "th{color:var(--gbt-dim);font-weight:500}",
         "code{background:var(--gbt-deep-2);color:var(--gbt-gold);border:1px solid var(--gbt-hair);border-radius:6px;padding:2px 6px;font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-all}",
         ".note{color:var(--gbt-off);font-size:12px;margin-top:14px}",
         "</style></head><body>",
         "<h1>密钥台</h1>",
         "<div class=\"sub\">只显示<b>掩码</b>与槽位状态；明文只存在于 "
         "<code>deploy/cloud-10/.dev.vars</code> 与本机环境变量。本页零脚本零外链。</div>",
         "<table><tr><th>槽位</th><th>是什么</th><th>在哪 / 现在什么状态</th><th>怎么灌进环境</th><th>换一把（rotate）</th></tr>"]
    for r in rows:
        h.append("<tr><td><b>%s</b></td><td>%s</td><td>%s<br><code>%s</code></td><td>%s</td><td><code>%s</code></td></tr>"
                 % (r["id"], r["what"], r["state"], r["where"], r["load_env"], r["rotate"]))
    h.append("</table>")
    h.append("<div class=\"note\">口径：凭据<b>只从环境变量/密钥服务读</b>；页面与源码里<b>不许出现明文</b>"
             "（安全钩子会拦）。换钥三步：① 生新值 → ② <code>wrangler secret put</code>（+ 本机 "
             "<code>.dev.vars</code>）→ ③ <code>setx</code> 灌进环境（对话面要重启）。</div>")
    h.append("</body></html>")
    return "\n".join(h)


def main() -> int:
    rows = slots()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_html(rows), encoding="utf-8")
    print(json.dumps({"ok": True, "page": str(OUT.relative_to(ROOT)), "slots": len(rows),
                      "明文入页": 0,
                      "note": "页面只含掩码与命令；零脚本零外链；面板静态发得出去"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
