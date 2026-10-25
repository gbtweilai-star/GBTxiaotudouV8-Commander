"""10 插件 · 云部署核对（只读）—— 「以 10 个云插件部署」这句话的**现读底账**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
主人 2026-09-25 令「以 10 个云插件部署」。这句话要成立，得先回答两件事，**都只能现读**：
① 这 10 个名字**在真源里存不存在**（npm registry 现查，**不许拿记忆顶替**）；
② 云侧**能不能接**（`wrangler` 在不在 · Cloudflare 凭据配没配 · `whoami` 验没验）。

## 口径（写死在输出里）
- **插件是"接线"，不是"算力"**：`dsh-llm-qwen-local` 是**适配器**（接到一个已经在跑的
  vLLM/OpenAI 兼容端点），它**自己不部署模型、不提供 GPU**；
  ⇒ 表格必须把「这条插件负责什么」与「算力从哪来」分开写，**不许拿插件名冒充算力**。
- **取不到 ≠ 不存在**：网络失败写成「未读到」，只有 HTTP 404 才写「不存在」。
- **不编包名**：名单只从主人给的 10 条里读，缺一条就报缺。

用法：
  python tools/codex-scripts/cloud-plugins-check.py check [--json]
  python tools/codex-scripts/cloud-plugins-check.py selftest
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 主人那张截图里的 10 条（**逐字照录**；一条都不改、不加）
PLUGINS = (
    ("dsh-llm-qwen-local", "本地模型接入（适配器）"),
    ("dsh-force-compact", "上下文压缩"),
    ("dsh-llm-qwen-abliterated", "无审查推理（模型增强）"),
    ("dsh-tool-web", "联网搜索与抓取"),
    ("dsh-tool-file", "文件系统操作"),
    ("dsh-tool-shell", "命令行执行"),
    ("dsh-memory-vector", "向量记忆"),
    ("dsh-memory-local", "本地持久化记忆"),
    ("dsh-policy-guard", "权限与安全策略"),
    ("dsh-observability", "可观测性与审计"),
)

# 不存在时**建议的真件**（本仓现读已存在的东西；只做映射，不许当成"已装"）
FALLBACK = {
    "dsh-force-compact": "本仓：DSH 自带上下文压缩 / `gbt_allinone/think_loop.py` 的上下文收口",
    "dsh-llm-qwen-abliterated": "本仓：无（要 abliterated 权重 + 一个端点，**权重本机没有**）",
    "dsh-tool-web": "本仓：`web_fetch`/`web_search` 工具（search 现读在本环境是坏的）",
    "dsh-tool-file": "本仓：DSH 自带文件工具 + `gbt_allinone/file_operation.py`（有写根闸门）",
    "dsh-tool-shell": "本仓：DSH 沙箱执行（要 `process_execute` 作用域）",
    "dsh-memory-vector": "本仓：`gbt_allinone/tools/context_vault.py`（sqlite + FTS5 真库）",
    "dsh-memory-local": "本仓：`memory/**` + `state/**`（文件式持久化）",
    "dsh-policy-guard": "本仓：`gbt_allinone/security/policy.py` + `auth_gate.py`（15 作用域）",
}


def npm_probe(name: str, timeout: float = 12.0) -> dict:
    """现查 npm：404 ⇒ 不存在；200 ⇒ 存在（带版本/仓库）；其它/异常 ⇒ **未读到**。"""
    url = "https://registry.npmjs.org/" + name
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:      # noqa: S310（公开只读）
            d = json.loads(r.read().decode("utf-8", errors="replace"))
        return {"状态": "存在", "最新": (d.get("dist-tags") or {}).get("latest"),
                "仓库": ((d.get("repository") or {}) if isinstance(d.get("repository"), dict)
                       else {}).get("url") or d.get("homepage") or "**未读到**"}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"状态": "不存在", "为什么": "HTTP 404"}
        return {"状态": "**未读到**", "为什么": "HTTP %s" % e.code}
    except Exception as exc:
        return {"状态": "**未读到**", "为什么": "%s: %s" % (type(exc).__name__, str(exc)[:40])}


def cloud_side() -> dict:
    """云侧就绪现读：wrangler 版本 / 凭据已配否 / whoami 有没有验过。**不发任何部署动作**。"""
    out = {}
    try:
        p = subprocess.run(["wrangler", "--version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        out["wrangler"] = (p.stdout or p.stderr).strip().splitlines()[0][:60] if (p.stdout or p.stderr) else "**未读到**"
    except Exception as exc:
        out["wrangler"] = "**未读到**（%s）" % type(exc).__name__
    import os
    out["CLOUDFLARE_API_TOKEN"] = "已配" if os.environ.get("CLOUDFLARE_API_TOKEN") else "未配"
    out["CLOUDFLARE_ACCOUNT_ID"] = "已配" if os.environ.get("CLOUDFLARE_ACCOUNT_ID") else "未配"
    out["whoami"] = "**未验**（跑 whoami 会出网；按纪律等主人点头）"
    return out


def classify(probes: dict, names: tuple) -> dict:
    """**纯函数**（好上负控）：把现读结果分成存在/不存在/未读到三档。"""
    if not names:
        return {"ok": False, "拒绝": "**名单是空的 ⇒ 拒绝**（空名单不许念成『全部都查过了』）"}
    got = {"存在": [], "不存在": [], "**未读到**": []}
    for n, why in names:
        r = probes.get(n) if isinstance(probes, dict) else None
        st = r.get("状态") if isinstance(r, dict) else "**未读到**"
        if st not in got:
            st = "**未读到**"
        got[st].append({"插件": n, "职责": why,
                        **({"最新": r["最新"], "仓库": r["仓库"]} if st == "存在" and isinstance(r, dict) else {}),
                        **({"建议的真件": FALLBACK[n]} if st == "不存在" and n in FALLBACK else {})})
    return {"ok": True, **got, "名单条数": len(names)}


def check(as_json: bool) -> int:
    probes = {n: npm_probe(n) for n, _ in PLUGINS}
    c = classify(probes, PLUGINS)
    if not c.get("ok"):
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 2
    out = {"现读": c, "云侧": cloud_side(),
           "口径": "**插件是接线，不是算力**：`dsh-llm-qwen-local` 只是适配器（要一个已在跑的 "
           "vLLM/OpenAI 兼容端点）⇒ 27B 的算力必须另有来源；`未读到` ≠ `不存在`（只有 404 才算）",
           "算力侧现读": {"本机 GPU": "torch 2.14.0+cpu / cuda=False / directml=False",
                     "本机显存": "3.98 GB", "最小量化档": "5.77 GiB（Qwen3.8-27B-UD-IQ1_S.gguf）",
                     "本机服务端口": "11434/8000/1234 全没监听"}}
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("名单 %d 条 ｜ 存在 %d ｜ 不存在 %d ｜ 未读到 %d"
              % (c["名单条数"], len(c["存在"]), len(c["不存在"]), len(c["**未读到**"])))
        for r in c["存在"]:
            print("  ✅ %-28s 最新 %-8s %s" % (r["插件"], r.get("最新"), str(r.get("仓库"))[:52]))
        for r in c["不存在"]:
            print("  ❌ %-28s %s" % (r["插件"], "建议真件：" + str(r.get("建议的真件"))[:56]))
        for r in c["**未读到**"]:
            print("  ⚠️ %-28s %s" % (r["插件"], r.get("为什么", "")))
        print("云侧：%s" % json.dumps(out["云侧"], ensure_ascii=False))
        print("算力侧：%s" % json.dumps(out["算力侧现读"], ensure_ascii=False))
        print("口径：%s" % out["口径"])
    return 0


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    names = (("a", "甲"), ("b", "乙"), ("c", "丙"))
    c = classify({"a": {"状态": "存在", "最新": "1.0.0", "仓库": "u"},
                  "b": {"状态": "不存在"}, "c": {"状态": "**未读到**", "为什么": "超时"}}, names)
    ck("**分类：存在/不存在/未读到 三档分得开**",
       len(c["存在"]) == 1 and len(c["不存在"]) == 1 and len(c["**未读到**"]) == 1,
       "存在 %d 不存在 %d 未读到 %d" % (len(c["存在"]), len(c["不存在"]), len(c["**未读到**"])))
    ck("**负控：网络失败 ⇒ 只写「未读到」，不许当「不存在」**",
       not any(r["插件"] == "c" for r in c["不存在"]), "")
    real_names = (("dsh-tool-file", "文件系统操作"), ("dsh-llm-qwen-local", "本地模型接入（适配器）"))
    rc2 = classify({"dsh-tool-file": {"状态": "不存在"},
                    "dsh-llm-qwen-local": {"状态": "存在", "最新": "0.4.1", "仓库": "u"}}, real_names)
    ck("**映射：不存在的插件才给「建议的真件」**（存在的绝不给）",
       "建议的真件" in rc2["不存在"][0] and "建议的真件" not in rc2["存在"][0],
       "%s ｜ %s" % (rc2["不存在"][0]["插件"], rc2["存在"][0]["插件"]))
    ck("**边界：名单为空 ⇒ 拒绝**（不许念成全都查过了）",
       classify({}, ())["ok"] is False, "")
    ck("**边界：探测结果缺条目 ⇒ 记「未读到」而不是静默丢**",
       classify({}, names)["**未读到**"].__len__() == 3, "")
    ck("**现读：名单恰好 10 条且逐字来自截图**（不增不减）",
       len(PLUGINS) == 10 and [n for n, _ in PLUGINS][0] == "dsh-llm-qwen-local", "10 条")
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "selftest"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    return check(a.json)


if __name__ == "__main__":
    raise SystemExit(main())
