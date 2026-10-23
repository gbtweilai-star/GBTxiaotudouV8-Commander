#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""model_roster · 可操控的**模型面**现读（主人令 2026-09-25：「一个可以操控亿万大模型的大模型」）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它回答什么
1. 本机**实际能路由到**哪些 provider / 哪些模型（现读 `~/.dsh/settings.yaml`，不写死）；
2. 有没有**模型允许清单**（`allowedModels`）—— 这就是模型面上的**门**；
3. 有多少模型**在清单之外**（⇒ 自律那条：不在清单里的不许调）。

## 🔴 凭据红线（写死成代码，不是嘴上说）
读的是 **settings.yaml**（结构），**不读 `.credentials.yaml`**。
输出一律**丢弃**形如 key/token/secret/password/credential/auth 的键，
以及 `baseURL`（可能含内网地址）—— 只报「已省略」。`--selftest` 里有一条负控：
**喂一份带假 apiKey 的配置进去，输出里必须一个字都不出现**。

用法：
  model_roster.py roster      # 模型面现读
  model_roster.py gate        # 只报模型面的门（allowedModels）
  model_roster.py schema      # 只看 YAML 键结构（值全隐）
  model_roster.py selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HOME = Path.home()
SETTINGS = HOME / ".dsh" / "settings.yaml"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 🔴 出现这些形状的键**一律不输出**（大小写不敏感）
SECRET_RE = re.compile(r"(?i)key|token|secret|password|credential|auth|cookie|session")
# 🔴 这些键输出但**值隐去**（可能是内网地址/路径）
MASK_VALUE = {"baseurl", "url", "endpoint", "path", "dir", "home"}


def _scrub(node, path=""):
    """递归净化：丢掉密键、隐去地址值。**返回 (净化后, 被丢弃的键路径列表)**。"""
    dropped = []
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            ks = str(k)
            here = "%s.%s" % (path, ks) if path else ks
            if SECRET_RE.search(ks):
                dropped.append(here + "（形似凭据 ⇒ 丢弃）")
                continue
            if ks.lower() in MASK_VALUE:
                out[ks] = "<已省略>"
                dropped.append(here + "（可能是内网地址 ⇒ 值隐去）")
                continue
            out[ks], d = _scrub(v, here)
            dropped += d
        return out, dropped
    if isinstance(node, list):
        out = []
        for i, v in enumerate(node):
            sv, d = _scrub(v, "%s[%d]" % (path, i))
            out.append(sv)
            dropped += d
        return out, dropped
    return node, dropped


def _find(node, key, path=""):
    """在整棵 YAML 里找某个键（返回 [(路径, 值)…]）。"""
    hits = []
    if isinstance(node, dict):
        for k, v in node.items():
            here = "%s.%s" % (path, k) if path else str(k)
            if str(k) == key:
                hits.append((here, v))
            hits += _find(v, key, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            hits += _find(v, key, "%s[%d]" % (path, i))
    return hits


def load_settings(path: Path):
    try:
        import yaml
    except Exception as e:
        return None, "没有 yaml 解析器：%s" % e
    if not path.exists():
        return None, "settings.yaml 不在：%s" % path
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}, None
    except Exception as e:
        return None, "settings.yaml 解析失败：%s" % e


def roster(cfg: dict) -> dict:
    """从配置里抽 `(provider, model)` **配对**，并与 `allowedModels` 按**配对**比对。

    🔴 第一版这里用**模型 id** 去比 `allowedModels`，而后者是 `{provider, model}` **配对**
    ⇒ 永远比不中 ⇒ 报了"73 条在清单外"的**假警报**。
    同因还有一处自欺：`deepseek-v4-flash` 被 deepseek-official 与 opencode **同时提供**，
    按 id 去重会数出 73，而真实配对是 74 —— 「两个源差 1」其实是我自己的去重造的。
    **按配对比，两个源就一致了（74 = 74）。**
    """
    prov_hits = _find(cfg, "providers")
    providers, pairs = {}, set()
    for p, v in prov_hits:
        if isinstance(v, dict):
            for name, body in v.items():
                models = []
                if isinstance(body, dict):
                    ms = body.get("models")
                    if isinstance(ms, list):
                        for m in ms:
                            if isinstance(m, dict):
                                models.append(m.get("id") or m.get("name") or str(sorted(m)[:2]))
                            else:
                                models.append(str(m))
                    elif isinstance(ms, dict):
                        models = sorted(ms)
                providers[str(name)] = {"模型数": len(models), "模型": models, "配置节": p}
                pairs |= {(str(name), m) for m in models}
    allow_pairs, allow_path = [], []
    for p, v in _find(cfg, "allowedModels"):
        allow_path.append(p)
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and "provider" in x and "model" in x:
                    allow_pairs.append((str(x["provider"]), str(x["model"])))
                elif x:
                    allow_pairs.append(("?", str(x)))
    allow_set = set(allow_pairs)
    outside = sorted(pairs - allow_set) if allow_set else []
    allowed_but_absent = sorted(allow_set - pairs) if allow_set else []
    # 🔴 **作用域要看它在哪个父节下面** —— 同一个键名放在不同父节，管的范围完全不同。
    #    第一版把它当成"模型面的门"，其实它在 `subagent-model-selection` 之下，
    #    **只管 subagent 的模型选择**，管不到主 agent。
    allow_scope = allow_path[0].rsplit(".", 1)[0] if allow_path else "（未知）"
    default_model = None
    for p, v in _find(cfg, "agent-default-model"):
        default_model = {"出处": p, "值": v}
        break
    return {
        "provider 数": len(providers),
        "配置里的 (provider,model) 配对数": len(pairs),
        "配置里**不同**模型 id 数": len({m for _, m in pairs}),
        "providers": providers,
        "模型允许清单 allowedModels": {
            "条数": len(allow_pairs), "配对": allow_pairs[:200],
            "出处": "~/.dsh/settings.yaml", "键路径": allow_path,
            "作用域": "**只在这个父节下生效**：`%s`" % allow_scope,
            "含义": "这是 `%s` 的门 —— **不是全局模型门**（主 agent 的模型在 `agent-default-model`）"
            % allow_scope},
        "主 agent 默认模型（**另一个接缝**）": default_model or "未读到",
        "配置里配了、但**不在该门**里的": {"条数": len(outside), "清单": outside,
                              "读法": "⚠️ **不等于越界** —— 两个接缝各自维护："
                              "provider 表在 `llm-pi-ai.providers`，"
                              "允许清单在 `%s`。差集只说明**两边没对齐**。" % allow_scope},
        "门里有、但 provider 表里没配的": {"条数": len(allowed_but_absent),
                                 "清单": allowed_but_absent[:20],
                                 "读法": "多来自**别的插件**注册的 provider（例如 deepseek 那条独立接缝）"},
        "凭据": {"读的文件": "只有 settings.yaml（**不读 .credentials.yaml**）",
               "规则": "形似凭据的键一律丢弃；地址类值隐去；见 --selftest 负控"},
    }


def cmd_roster(a) -> int:
    cfg, err = load_settings(Path(a.settings))
    if err:
        print(json.dumps({"ok": False, "读不到": err}, ensure_ascii=False, indent=1))
        return 2
    r = roster(cfg)
    _, dropped = _scrub(cfg)
    r["被丢弃/隐去的键"] = dropped
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


def cmd_gate(a) -> int:
    cfg, err = load_settings(Path(a.settings))
    if err:
        print(json.dumps({"ok": False, "读不到": err}, ensure_ascii=False, indent=1))
        return 2
    r = roster(cfg)
    g = r["模型允许清单 allowedModels"]
    print(json.dumps({"门": {"条数": g["条数"], "键路径": g["键路径"],
                            "作用域": g["作用域"], "含义": g["含义"]},
                      "provider 表配对": r["配置里的 (provider,model) 配对数"],
                      "两边差集①配了但不在该门": r["配置里配了、但**不在该门**里的"],
                      "两边差集②门里有但没配": r["门里有、但 provider 表里没配的"],
                      "主 agent 默认模型": r["主 agent 默认模型（**另一个接缝**）"]},
                     ensure_ascii=False, indent=1))
    if g["条数"] == 0:
        print("⚠️ **没读到 allowedModels** ⇒ 该接缝上**没有声明式门**（如实报，不假装有）")
        return 3
    # 🔴 **判据修正**：两边差集**默认不是越界**（两个接缝各自维护）。
    #    只有「**同一个 provider 名**在门里出现过、却又在配置里配了门外的模型」才算真不一致。
    in_gate_prov = {p for p, _ in g["配对"]}
    hard = [x for x in r["配置里配了、但**不在该门**里的"]["清单"] if x[0] in in_gate_prov]
    if hard:
        print("🔴 **同一个 provider 在门里、却配了门外的模型** ⇒ 真不一致：%s" % hard)
        return 4
    print("✅ 该接缝的门读到 %d 条；两边差集是**接缝不同**（%d / %d），**不是越界**"
          % (g["条数"], r["配置里配了、但**不在该门**里的"]["条数"],
             r["门里有、但 provider 表里没配的"]["条数"]))
    return 0


def cmd_schema(a) -> int:
    cfg, err = load_settings(Path(a.settings))
    if err:
        print(json.dumps({"ok": False, "读不到": err}, ensure_ascii=False, indent=1))
        return 2

    def shape(n, d=0):
        if d > 3:
            return "…"
        if isinstance(n, dict):
            return {k: shape(v, d + 1) for k, v in list(n.items())[:40]}
        if isinstance(n, list):
            return ["len=%d" % len(n)] + ([shape(n[0], d + 1)] if n else [])
        return type(n).__name__
    print(json.dumps(shape(cfg), ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    fake = {"llm-pi-ai": {"providers": {"demo": {
        "apiKey": "sk-REALSECRET123456", "token": "tok-abc", "bearer": "b",
        "baseURL": "https://10.0.0.9/internal/v1",
        "models": [{"id": "m1"}, {"id": "m2"}]}}},
        "subagent-model-selection": {"allowedModels": [
            {"provider": "demo", "model": "m1"},
            {"provider": "other", "model": "m2"}]}}   # ← m2 属于 other，不是 demo
    scrubbed, dropped = _scrub(fake)
    blob = json.dumps(scrubbed, ensure_ascii=False)
    # ① 假密钥一个字都不许出现
    ck("**负控：假 apiKey 一个字都不许出现在输出里**",
       "sk-REALSECRET123456" not in blob and "tok-abc" not in blob, "已扫全量输出")
    ck("形似凭据的键被丢弃", len(dropped) >= 2, "丢了 %d 个：%s" % (len(dropped), dropped[:3]))
    ck("**baseURL 值被隐去**（不留内网地址）",
       "10.0.0.9" not in blob and scrubbed["llm-pi-ai"]["providers"]["demo"]["baseURL"] == "<已省略>",
       "providers.demo.baseURL = %s" % scrubbed["llm-pi-ai"]["providers"]["demo"]["baseURL"])
    # ② 真名册仍能抽出来
    r = roster(fake)
    ck("净化后仍能抽出 provider/配对", r["provider 数"] == 1
       and r["配置里的 (provider,model) 配对数"] == 2,
       "provider=%d 配对=%d" % (r["provider 数"], r["配置里的 (provider,model) 配对数"]))
    ck("allowedModels 按**配对**读出来（不是按模型 id）",
       r["模型允许清单 allowedModels"]["条数"] == 2,
       str(r["模型允许清单 allowedModels"]["配对"]))
    ck("**负控：同名模型属于别的 provider ⇒ 照样算进差集**（按 id 比会漏报）",
       r["配置里配了、但**不在该门**里的"]["清单"] == [("demo", "m2")],
       str(r["配置里配了、但**不在该门**里的"]["清单"]))
    ck("门里有、但 provider 表里没配的也被点名",
       r["门里有、但 provider 表里没配的"]["清单"] == [("other", "m2")],
       str(r["门里有、但 provider 表里没配的"]["清单"]))
    ck("**作用域按父节判定**（不是当成全局模型门）",
       "subagent-model-selection" in str(r["模型允许清单 allowedModels"]["作用域"]),
       str(r["模型允许清单 allowedModels"]["作用域"]))
    # ③ 真配置现读（读不到不算错，但要说清）
    cfg, err = load_settings(SETTINGS)
    if err:
        lines.append("· 真配置读不到（%s）—— 另计，不算失败" % err)
    else:
        rr = roster(cfg)
        ck("**真配置现读**：能报出 provider 与配对数",
           rr["provider 数"] >= 1 and rr["配置里的 (provider,model) 配对数"] >= 1,
           "provider=%d 配对=%d ｜ 允许清单 %d"
           % (rr["provider 数"], rr["配置里的 (provider,model) 配对数"],
              rr["模型允许清单 allowedModels"]["条数"]))
    print(json.dumps({"自检": {"条数": len([ln for ln in lines if ln.startswith(("✓", "✗"))]),
                             "通过": len([ln for ln in lines if ln.startswith("✓")]),
                             "不通过": bad}, "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="可操控的模型面现读（不泄密 · 不写死）")
    ap.add_argument("--settings", default=str(SETTINGS))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("roster").set_defaults(func=cmd_roster)
    sub.add_parser("gate").set_defaults(func=cmd_gate)
    sub.add_parser("schema").set_defaults(func=cmd_schema)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
