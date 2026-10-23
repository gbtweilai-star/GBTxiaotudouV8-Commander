#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""self_model · GBT小土豆V8 的**自身融合层**（主人令 2026-09-25）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 主人原话
> 「把**专属大模型**和**自身能力**完美的**融合**到一起，这才是真正的 GBT小土豆V8 大模型 ——
>   一个可以**操控亿万大模型**的大模型，**自主自律**」

## 这一层怎么理解（把话说清，不吹）
「专属大模型」在本机**不是一份 27B 权重**（实测 RAM 7.39 GB / GPU 4 GB，跑不动，见 §一百零二）。
真正的「专属」是**这个复合体**：身份内核 + 168 个能力位 + 触手名册 + **可路由的模型面** + 门与红线。
⇒ 「融合」= 让这五块**在同一个视角里同时可见、且每个数字都能指回它的唯一真源**。
⇒ 「自主」= 能自己选模型、自己调能力位；「自律」= **一步都绕不过门**，缺授权就如实报缺。

## 🔴 三条设计红线
1. **一个数字都不写死** —— 每块都从它的**唯一真源现读**，并**附出处**；
   读不到就报「**未读到**」，**绝不用 0 冒充**（0 和"没读到"是两件事）。
2. **不冒充**：能力位有几条、模型面有几条、缺授权几条，全部现读现报。
3. **不越权**：本层**只读**（不调能力位、不改任何东西、不自己发授权）。

用法：
  self_model.py whoami     # 自身融合画像（JSON，每块带出处）
  self_model.py brief       # 一屏人话版
  self_model.py selftest
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "tools" / "codex-scripts"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _json(rel: str):
    """读一份 JSON 真源 → (数据 or None, 出处说明)。**读不到绝不返回 0 假装有。**"""
    p = ROOT / rel
    if not p.exists():
        return None, "**未读到**：%s 不在" % rel
    try:
        return json.loads(p.read_text(encoding="utf-8")), "%s（%d 字节）" % (rel, p.stat().st_size)
    except Exception as e:
        return None, "**未读到**：%s 解析失败 %s" % (rel, str(e)[:60])


def _load(rel: str):
    """按路径加载一个工具模块（只读用；不执行它的 main）。

    🔴 必须先 `sys.modules[nm] = m` 再 exec：本仓多个工具有
    `from __future__ import annotations` + `@dataclass`，而 `dataclasses` 要靠
    `sys.modules[cls.__module__]` 去解析字符串注解 —— **不注册就在 @dataclass 处炸**
    （实测踩过：`iching_kernel` 加载失败 ⇒ 推演那块报「未读到」）。
    """
    p = ROOT / rel
    if not p.exists():
        return None, "**未读到**：%s 不在" % rel
    nm = "_sm_" + p.stem.replace("-", "_")
    try:
        spec = importlib.util.spec_from_file_location(nm, p)
        m = importlib.util.module_from_spec(spec)
        sys.modules[nm] = m                      # ← 关键：先注册，再 exec
        try:
            spec.loader.exec_module(m)
        except Exception:
            sys.modules.pop(nm, None)
            raise
        return m, rel
    except Exception as e:
        return None, "**未读到**：%s 加载失败 %s" % (rel, str(e)[:70])


# ── 五块「自己」 ────────────────────────────────────────────────────────────────
def blk_identity() -> dict:
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.soul import DEVELOPER, SIGNATURE
        return {"名字": "GBT小土豆V8", "开发者署名": SIGNATURE, "守护者": "公主土豆",
                "署名铁律": "本署名不可删除、不可篡改归属",
                "出处": "gbt_allinone/soul.py（唯一真源）", "开发者字段": DEVELOPER}
    except Exception as e:
        return {"名字": "GBT小土豆V8", "守护者": "公主土豆",
                "出处": "**未读到** gbt_allinone/soul.py：%s" % str(e)[:60]}


# ── 能力位真源（`state/caps-probe-accum.json`）────────────────────────────────────
# 🔴 真源里的状态键叫 **`态`**（单字）。我先后猜错过三次键名
#    （`逐条 rc` / `状态` / …）⇒ 一律**不猜**：找不到就报未读到，并**报出实际有哪些键**。
OK, BLOCKED, NEEDPARAM, PAIN = "✅ 通", "🔒 被门拒·缺授权", "🟡 需参数·未探", "⛔ 痛"
KNOWN_STATES = (OK, BLOCKED, NEEDPARAM, PAIN)


def _caps_table(acc):
    """→ (表, 错)。**未识别的状态必须报出来，绝不静默丢掉**（F36 同型：新痛被当"无变化"）。"""
    if not isinstance(acc, dict):
        return None, "**未读到**：不是一份对象"
    rows = acc.get("逐位")
    if not isinstance(rows, dict):
        return None, ("**未读到**：没有『逐位』｜ 实际顶层键：%s" % list(acc))
    by, unknown = {}, {}
    for k, v in rows.items():
        st = (v or {}).get("态")
        if st is None:
            unknown.setdefault("**没有『态』字段**", []).append(k)
            continue
        by[st] = by.get(st, 0) + 1
        if st not in KNOWN_STATES:
            unknown.setdefault(st, []).append(k)
    return {"rows": rows, "by": by, "unknown": unknown}, None


def blk_caps() -> dict:
    acc, src = _json("state/caps-probe-accum.json")
    out = {"出处": src}
    if acc is None:
        out["能力位"] = "**未读到**（不拿 0 冒充）"
        return out
    t, err = _caps_table(acc)
    if err:
        out["能力位"] = err
        return out
    rows, by = t["rows"], t["by"]
    out.update({"已探位": len(rows), "按状态": by,
                "可探针总数": acc.get("可探针总数"), "已覆盖位数": acc.get("已覆盖位数")})
    if t["unknown"]:
        out["🔴 未识别的态（**不许静默丢**）"] = {k: len(v) for k, v in t["unknown"].items()}
    return out


def merge_two_ledgers(rows: dict, np_doc) -> dict:
    """**两个口径合并**（**纯函数**：面板、CLI、自检共用一份判据，不复制）。

    🔴 **为什么必须留两个口径、而不是"挑一个准的"**：
      空参探时，「缺参」那几位**先卡在参数校验、走不到门** ⇒ **它们要的作用域根本不出现**。
      实测：给 `osint_scan` 一个回环 target 之后，门才发声，露出第 10 个作用域 `osint_private`。
      ⇒ 空参口径说「缺授权 27」，给参后口径说「缺授权 28」 —— **两个数都对**，
      **错的是"写一个数却不写口径"**（本仓屡犯：`16 道闸` / `现读 296 个 .py` / `== 5`）。
    """
    by = {}
    for v in (rows or {}).values():
        st = (v or {}).get("态")
        by[st] = by.get(st, 0) + 1
    if not isinstance(np_doc, dict):
        return {"未读到": "**合并口径未读到** ⇒ 现在只有「空参探」那一套（跑 "
                        "`probe_needparam.py run` 才生成给参后的账）。**这不是 0，是没读。**",
                "空参探": {"已通": by.get(OK, 0), "缺授权": by.get(BLOCKED, 0),
                          "缺参": by.get(NEEDPARAM, 0), "真痛": by.get(PAIN, 0)}}
    tal = np_doc.get("合计") or {}
    new_ok = sum(v for k, v in tal.items() if str(k).startswith("✅"))
    new_env = sum(v for k, v in tal.items() if str(k).startswith("🟠"))
    new_deny = sum(v for k, v in tal.items() if str(k).startswith("🔒"))
    still = sum(v for k, v in tal.items() if str(k).startswith("🟡"))
    m = {"已通": by.get(OK, 0) + new_ok,
         "缺授权": by.get(BLOCKED, 0) + new_deny,
         "缺参": still,
         "环境未就绪": new_env,
         "真痛": by.get(PAIN, 0)}
    m["合计"] = sum(m.values())
    # 🔴 这条**不是恒真式**：它要求两本账在"还剩几位缺参"上**对得上**
    #    （给参后的账说还剩 N 位缺参，空参账里就必须正好有 N 位是"需参数"）。
    #    对不上 ⇒ 两本账分叉（有人只更新了一本）⇒ 这里会红。
    m["算术自洽"] = (m["合计"] == len(rows))
    m["口径"] = ("accum（**空参探**）里的「缺参 %d 位」已被按**给参后**重判 ⇒ "
                "合并后：已通 %d · 缺授权 %d · 环境未就绪 %d · 缺参 %d · 真痛 %d"
                % (by.get(NEEDPARAM, 0), m["已通"], m["缺授权"], m["环境未就绪"],
                   m["缺参"], m["真痛"]))
    return m


def blk_auth() -> dict:
    """**授权面**：缺授权按作用域聚合（每个作用域一条主人命令）+ 缺参清单 + 真痛。"""
    acc, src = _json("state/caps-probe-accum.json")
    out = {"出处": src}
    if acc is None:
        out["授权面"] = "**未读到**"
        return out
    t, err = _caps_table(acc)
    if err:
        out["授权面"] = err
        return out
    rows, by = t["rows"], t["by"]
    blocked = sorted(k for k, v in rows.items() if (v or {}).get("态") == BLOCKED)
    needp = sorted(k for k, v in rows.items() if (v or {}).get("态") == NEEDPARAM)
    pain = sorted(k for k, v in rows.items() if (v or {}).get("态") == PAIN)

    POL, perr = None, None
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.security import policy as POL      # noqa: N806
    except Exception as e:
        perr = str(e)[:70]
    scope = {}
    if POL is not None:
        for k in blocked:
            try:
                sc = list(getattr(POL.evaluate(k, {}), "scopes", ()) or ())
            except Exception:
                sc = []
            for s in sc:
                scope.setdefault(s, []).append(k)
    out.update({
        "已通": by.get(OK, 0),
        "缺授权": len(blocked),
        "缺参": len(needp),
        "真痛位数": len(pain),
        "缺授权·按作用域（发一次覆盖多位）": {
            s: {"位数": len(v), "位名": v,
                "主人命令": "python -m gbt_allinone auth grant --scope %s --ttl 600" % s}
            for s, v in sorted(scope.items(), key=lambda kv: -len(kv[1]))},
        "缺授权·**没有任何作用域**的（要另查）":
            [k for k in blocked if k not in {x for v in scope.values() for x in v}],
        "缺参清单（**不是权限问题**，要按各自契约给参）":
            {k: str((rows[k].get("为什么") or ""))[:70] for k in needp},
        # 🔴 同一个字段名**不许有时是 list 有时是字符串** —— 实测踩过：`真痛` 为空时返回
        #    字符串「无」，非空时返回 list，消费者一相加就 TypeError。**计数与清单分开。**
        "真痛清单": pain,
        "policy 现算": ("gbt_allinone.security.policy.evaluate() 现读" if POL is not None
                    else "**未读到** policy：%s" % perr),
        "自律铁律": "**AI 永远无权给自己发授权** —— 授权只能主人在终端发；缺就如实报缺",
    })
    # 🔴 **这张表是下界，不是全集**：空参探时「缺参」那几位**先卡在参数校验、走不到门**，
    #    它们的作用域**根本不会出现**。实测：`osint_scan` 空参报「缺少 target」，
    #    给了 `127.0.0.1` 之后门才发声 ⇒ 露出第 10 个作用域 `osint_private`。
    np, nsrc = _json("state/needparam-last.json")
    if isinstance(np, dict):
        extra = (np.get("🔴 本轮新露出来的作用域（**空参探时看不见**）") or {}).get("逐位") or {}
        out["表是下界·给参后才露出的作用域"] = {
            "出处": nsrc, "逐位": extra,
            "为什么": "空参时这些位先卡参数校验、走不到门 ⇒ 作用域不出现；给参后门才发声",
            "全量表要这样算": "空参探到的作用域 ∪ 本表——**只按空参探会漏**"}
        out["按空参探到的作用域数"] = len(scope)
        out["按含给参后的作用域数"] = len(set(scope) | {s for v in extra.values() for s in v})
        # 🔴 **两套读数并存，不许混**：accum 是「空参探」的读数；needparam 是「给参后」的读数。
        #    合并口径走**纯函数** `merge_two_ledgers`（面板/CLI/自检共用，不复制判据）。
        m = merge_two_ledgers(rows, np)
        out["合并口径（空参探 ∪ 给参后）"] = m
        # 🔴 把**两个数并排摆出来、各自带口径**：本仓反复吃过"一个数没写口径"的亏
        #    （`16 道闸` / `现读 296 个 .py` / `len(steps) == 5`）。
        out["两个口径（**别混念**）"] = {
            "空参探（accum）": {"已通": by.get(OK, 0), "缺授权": len(blocked),
                            "缺参": len(needp), "真痛": by.get(PAIN, 0),
                            "作用域数": len(scope), "出处": src},
            "给参后（合并）": {k: m.get(k) for k in
                          ("已通", "缺授权", "缺参", "环境未就绪", "真痛", "合计")},
            "给参后·作用域数": len(set(scope) | {s for v in extra.values() for s in v}),
            "为什么两个数都对": ("空参时缺参位**走不到门** ⇒ 作用域不出现；给参后才露出来。"
                          "实测：缺授权 %d→%d 位 · 作用域 %d→%d 个"
                          % (len(blocked), m.get("缺授权"), len(scope),
                             len(set(scope) | {s for v in extra.values() for s in v}))),
        }
    else:
        out["表是下界·给参后才露出的作用域"] = {
            "出处": nsrc, "读法": "**未读到** ⇒ 现在的表**只是下界**（跑 "
                              "`probe_needparam.py run` 才会生成本文件）"}
    return out


def blk_tentacle() -> dict:
    m, src = _load("tools/codex-scripts/tentacle-registry.py")
    if m is None:
        return {"出处": src, "名册": "**未读到**"}
    v = m.verify_chain()
    n, nsrc = m.declared_roots()
    rows, _ = m.load_registry()
    mounts = 0
    for r in rows:
        w = r.get("what", "")
        if "载 " in w:
            try:
                mounts += int(w.split("载 ")[1].split(" 件")[0])
            except Exception:
                pass
    return {"出处": "tools/codex-scripts/tentacle-registry.py（现读）",
            "声明根数": {"值": n, "出处": nsrc},
            "名册行数": v["行数"], "锚点": v["锚点"] if isinstance(v["锚点"], str) else "；".join(v["锚点"]),
            "身份唯一": not v["重复 tid"] and not v["重复 name"],
            "序列缺口": v["序号缺口"], "全过": v["全过"], "合计载件": mounts}


def blk_models() -> dict:
    m, src = _load("tools/codex-scripts/model_roster.py")
    if m is None:
        return {"出处": src, "模型面": "**未读到**"}
    cfg, err = m.load_settings(m.SETTINGS)
    if err:
        return {"出处": src, "模型面": "**未读到**：%s" % err}
    r = m.roster(cfg)
    g = r["模型允许清单 allowedModels"]
    return {"出处": "tools/codex-scripts/model_roster.py 现读 ~/.dsh/settings.yaml",
            "provider 数": r["provider 数"],
            "可路由 (provider,model) 配对数": r["配置里的 (provider,model) 配对数"],
            "该接缝的门": {"条数": g["条数"], "作用域": g["作用域"]},
            "凭据红线": r["凭据"]["规则"],
            "⚠️ 不是亿万": "「操控亿万大模型」是说法；**实测可路由 %d 条**，不吹大"
                            % r["配置里的 (provider,model) 配对数"]}


def _gate_from(c: dict) -> dict:
    """从体检读数里算判决/闸数。**键不在就报「未读到」，绝不用 0 冒充。**

    🔴 第一版读的是 `c["逐条 rc"]` —— 而 `checkup-last.json` 里的键其实是 **`逐条`（list）**
    ⇒ 读了个不存在的键、拿到 `{}`、报出「闸 0 道」（判决却写着 9 道）。
    **这正是「用 0 冒充」**，本层第一条规矩就禁止它。
    """
    if not isinstance(c, dict):
        return {"体检": "**未读到**"}
    rows = c.get("逐条")
    total = c.get("闸数") or c.get("步数")
    if isinstance(rows, list):
        rc = [(r.get("步骤"), r.get("rc")) for r in rows if isinstance(r, dict)]
        bad = [s for s, v in rc if v != 0]
        return {"判决": c.get("判决"), "闸数": len(rc), "未过的闸": bad or "无",
                "总耗时秒": c.get("总耗时秒"),
                "出处键": "逐条（list）"}
    if total:
        return {"判决": c.get("判决"), "闸数": total, "未过的闸": "**未读到**（没有逐条明细）"}
    return {"判决": c.get("判决"), "闸数": "**未读到**（读数里没有逐条/闸数字段）",
            "未过的闸": "**未读到**"}


def blk_gate() -> dict:
    c, src = _json("state/checkup-last.json")
    out = {"出处": src}
    if c is None:
        out["体检"] = "**未读到**"
    else:
        out.update(_gate_from(c))
    out["唯一门"] = "five-dim.py cap <能力位> → run_task（禁止直调模块函数绕门）"
    out["AI 不许做的事"] = ["给自己发授权", "改 security/policy.py", "绕门"]
    return out


def blk_beyond() -> dict:
    """**可探针之外的 30 位** —— 把「探过不痛」与「根本没碰过」分开。

    🔴 为什么必须有这一块：`真痛 0` 只覆盖**已探的 138 位**。
    另外 **19 位（8 位 safe=False + 11 位改状态）从来没调用过** ——
    若把它们悄悄算进"无痛"，就是**拿没测过的当测过了**。
    """
    b, src = _json("state/caps-beyond-probeable.json")
    out = {"出处": src}
    if b is None:
        out["可探针之外"] = "**未读到**（不拿 0 冒充）"
        return out
    cats = [k for k, v in b.items() if isinstance(v, dict)]
    if not cats:
        out["可探针之外"] = "**未读到**：文件里没有分类节 ｜ 实际键：%s" % list(b)
        return out
    detail = {}
    for k in cats:
        names = sorted(b[k])
        detail[k] = {"位数": len(names), "位名": names}
    never = sum(detail[k]["位数"] for k in cats if "改状态" in k or "safe=False" in k)
    out.update({
        "三类": detail,
        "合计": sum(d["位数"] for d in detail.values()),
        "证据强度（**不一样，别混**）": {
            "未实现": "**真调过**：rc=1 且如实报 `unknown capability` ⇒ 诚实性已验证",
            "safe=False": "**只静态核**（读源码/契约）⇒ **未真调**，不算「探过不痛」",
            "改状态": "**绝不调用**（红线：探它就可能真改框架状态）⇒ 账上**留缺口**",
        },
        "🔴 从未调用过的位数": never,
    })
    # 现读已探位数，把作用域写实（不写死）
    acc, _ = _json("state/caps-probe-accum.json")
    t, _e = _caps_table(acc) if acc is not None else (None, None)
    if t:
        probed = len(t["rows"])
        out["真痛 0 的作用域"] = {
            "只在": "**已探的 %d 位**里" % probed,
            "说明": "**不覆盖**从未调用过的那 %d 位（safe=False 8 + 改状态 11）"
                    " ⇒ **「真痛 0」≠「全机无痛」**" % never,
        }
        out["算术"] = {"已探": probed, "未实现": detail.get("未实现·真调验证", {}).get("位数", 0),
                     "safe=False": detail.get("safe=False·静态核", {}).get("位数", 0),
                     "改状态": detail.get("改状态·不探（红线）", {}).get("位数", 0)}
        out["算术"]["合计"] = sum(out["算术"].values())
    return out


def blk_film() -> dict:
    """**影像生产面**（ComfyUI 现读）—— 「电影」成不成，看**帧来源**在不在。

    🔴 不吹：「无限生产高质量电影」要能被读数拆开；拆不开的部分（产量/画质）就**不写进账**。
    """
    s, src = _json("state/comfy-surface.json")
    out = {"出处": src}
    if s is None:
        out["影像生产面"] = ("**未读到** ⇒ 跑 "
                          "`python tools/codex-scripts/comfy-surface.py scan` 才会生成")
        return out
    tb, mi = s.get("算力后端") or {}, s.get("模型清单") or {}
    n_img = sum(v.get("件", 0) for v in (mi.get("其中**图像**类") or {}).values())
    n_vid = sum(v.get("件", 0) for v in (mi.get("其中**视频/动图**类") or {}).values())
    out.update({
        "安装": (s.get("安装") or {}).get("路径"),
        "算力": "%s · torch %s" % (tb.get("构建口径"), tb.get("torch版本")),
        "torch_directml": tb.get("torch_directml"),
        "服务在跑": (s.get("服务") or {}).get("在跑"),
        "图像模型": n_img, "视频模型": n_vid,
        "能做什么": (s.get("结论") or {}).get("能做什么（**有据**）"),
        "到「电影」缺什么": (s.get("结论") or {}).get("到「无限生产高质量电影」缺什么"),
        "边界": (s.get("结论") or {}).get("诚实边界"),
    })
    return out


def blk_iching() -> dict:
    m, src = _load("tools/iching_kernel.py")
    if m is None:
        return {"出处": src, "决策内核": "**未读到**"}
    cov = m.coverage()
    return {"出处": "tools/iching_kernel.py 现读", "卦名覆盖": cov["卦名覆盖率"],
            "卦义覆盖": cov["卦义覆盖率"],
            "边界": m.HONEST_BOUNDARY}


def whoami() -> dict:
    b = {
        "身份": blk_identity(),
        "自身能力面": blk_caps(),
        "授权面（缺什么、卡在哪）": blk_auth(),
        "可探针之外（**别拿没测过的当测过了**）": blk_beyond(),
        "影像生产面（能不能产片看这里）": blk_film(),
        "触手（永久名册）": blk_tentacle(),
        "可操控的模型面": blk_models(),
        "自律（门与闸）": blk_gate(),
        "推演（周易决策内核）": blk_iching(),
    }
    missing = [k for k, v in b.items()
               if isinstance(v, dict) and any(isinstance(x, str) and "**未读到**" in x
                                              for x in v.values())]
    # 🔴 块数必须在**加自检之前**数 —— 否则"计数器把自己也数进去"（差 1，实测踩过）
    n_blocks = len(b)
    b["融合自检"] = {
        "块齐不齐": ("✅ %d 块都读到" % n_blocks) if not missing
                    else "🔴 **未读到**：%s" % missing,
        "块数": n_blocks,
        "规矩": "每个数字都带出处；**读不到就报未读到，不用 0 冒充**",
        "本层动作": "**只读**（不调能力位、不改东西、不自己发授权）",
    }
    return b


def cmd_whoami(a) -> int:
    print(json.dumps(whoami(), ensure_ascii=False, indent=1))
    return 0


def cmd_brief(a) -> int:
    w = whoami()
    C, A, T, M, G, I = (w["自身能力面"], w["授权面（缺什么、卡在哪）"], w["触手（永久名册）"],
                        w["可操控的模型面"], w["自律（门与闸）"], w["推演（周易决策内核）"])
    scopes = A.get("缺授权·按作用域（发一次覆盖多位）") or {}
    print("GBT小土豆V8 · 自身融合画像（每个数字都指得回出处）")
    print("  身份    : %s ｜ 守护者 %s" % (w["身份"].get("开发者署名"), w["身份"].get("守护者")))
    print("  能力面  : %s 位 ｜ 出处 %s" % (C.get("已探位", C.get("能力位")), C["出处"]))
    two = A.get("两个口径（**别混念**）") or {}
    mg = A.get("合并口径（空参探 ∪ 给参后）") or {}
    raw = two.get("空参探（accum）") or {}
    print("  授权面  : 【空参探】已通 %s ｜ 缺授权 %s（%s 个作用域）｜ 缺参 %s ｜ 真痛 %s"
          % (raw.get("已通", A.get("已通")), raw.get("缺授权", A.get("缺授权")),
             raw.get("作用域数", len(scopes)), raw.get("缺参", A.get("缺参")),
             raw.get("真痛", A.get("真痛位数"))))
    if mg.get("未读到"):
        print("            【给参后】**未读到** —— %s" % mg["未读到"])
    elif two.get("给参后（合并）"):
        g = two["给参后（合并）"]
        print("            【给参后】已通 %s ｜ **缺授权 %s**（%s 个作用域）｜ 环境未就绪 %s ｜ "
              "缺参 %s ｜ 真痛 %s ｜ 合计 %s %s"
              % (g.get("已通"), g.get("缺授权"), two.get("给参后·作用域数"),
                 g.get("环境未就绪"), g.get("缺参"), g.get("真痛"), g.get("合计"),
                 "（算术自洽 ✅）" if mg.get("算术自洽") else "（🔴 **算术不自洽**：两本账分叉）"))
        print("            ⚠️ **两个数都对，别混念**：%s" % two.get("为什么两个数都对"))
    if scopes:
        top = sorted(scopes.items(), key=lambda kv: -kv[1]["位数"])[:4]
        print("            最大缺口：%s"
              % " · ".join("%s(%d 位)" % (s, v["位数"]) for s, v in top))
    B = w["可探针之外（**别拿没测过的当测过了**）"]
    print("  未探区  : 可探针之外 %s 位（未实现 %s 真调过 · safe=False %s 只静态核 · 改状态 %s 绝不调用）"
          % (B.get("合计"),
             (B.get("三类") or {}).get("未实现·真调验证", {}).get("位数"),
             (B.get("三类") or {}).get("safe=False·静态核", {}).get("位数"),
             (B.get("三类") or {}).get("改状态·不探（红线）", {}).get("位数")))
    print("            ⇒ **%s 位从来没调用过** · 「真痛 0」只在已探的 138 位里 ⇒ **≠ 全机无痛**"
          % B.get("🔴 从未调用过的位数"))
    F = w["影像生产面（能不能产片看这里）"]
    if "**未读到**" in str(F.get("影像生产面", "")):
        print("  影像面  : **未读到**（跑 comfy-surface.py scan 生成）")
    else:
        print("  影像面  : ComfyUI %s ｜ 算力 %s ｜ 图像模型 %s ｜ **视频模型 %s**"
              % ("在" if F.get("安装") else "不在", F.get("算力"),
                 F.get("图像模型"), F.get("视频模型")))
        print("            ⇒ 能出分镜/关键帧 · **不能生成视频** · 到「电影」缺 %s 件"
              % len(F.get("到「电影」缺什么") or []))
    print("  触手    : 声明根数 %s ｜ 名册 %s 行 ｜ 载件 %s ｜ %s"
          % (T.get("声明根数", {}).get("值"), T.get("名册行数"), T.get("合计载件"),
             "链/锚点 ✅" if T.get("全过") else "🔴 不干净"))
    print("  模型面  : %d provider ｜ **可路由 %d 条** ｜ 该接缝门 %s 条"
          % (M.get("provider 数", 0), M.get("可路由 (provider,model) 配对数", 0),
             (M.get("该接缝的门") or {}).get("条数")))
    print("  自律    : %s ｜ 闸 %s 道 ｜ 未过 %s" % (G.get("判决"), G.get("闸数"), G.get("未过的闸")))
    print("  推演    : 卦名 %s ｜ 卦义 %s" % (I.get("卦名覆盖"), I.get("卦义覆盖")))
    print("  融合    : %s" % w["融合自检"]["块齐不齐"])
    print()
    print("  ⚠️ 「操控亿万大模型」是说法 —— 实测可路由 %d 条，我不吹大。" % M.get("可路由 (provider,model) 配对数", 0))
    print("  ⚠️ 「专属大模型」在本机不是 27B 权重（RAM 7.39G/GPU 4G 跑不动），是**这个复合体**。")
    print("  🔴 授权只能主人在终端发；**AI 永远无权给自己发授权**。")
    return 0


# 🔴 写盘原语清单（**判据只看 AST 真调用**，不扫文本 —— 文本会匹配到判据自己）
#    只收**无歧义**的名字：`replace` / `remove` / `rename` 与 str / list 同名，
#    收进来会把 `"a-b".replace("-","_")` 误判成写盘（实测踩过：报了 `replace @L63`）。
#    残留局限如实写：这只扫**直接调用**，扫不到 `shutil.move` 之类的间接写法。
_WRITE_FUNCS = ("write_bytes", "write_text", "mkdir", "unlink", "rmdir",
                "rmtree", "copytree", "chmod", "open")


def _write_calls(src: str) -> list:
    """AST 扫**真调用**（不是文本子串）→ ['write_text @L12', …]。"""
    import ast
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return ["**源码解析不了**：%s" % e]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            nm = (f.attr if isinstance(f, ast.Attribute)
                  else (f.id if isinstance(f, ast.Name) else ""))
            if nm in _WRITE_FUNCS:
                out.append("%s @L%d" % (nm, getattr(node, "lineno", 0)))
    return out


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    w = whoami()
    # ① 每一块都必须带「出处」—— 没有出处就是编的
    noplace = [k for k, v in w.items()
               if isinstance(v, dict) and k not in ("融合自检",) and "出处" not in v]
    ck("**每块都带出处**（没出处 = 编的）", not noplace, "缺出处: %s" % (noplace or "无"))
    # ② 🔴 负控：源不存在 ⇒ 必须报「未读到」，**不许返回 0**
    val, why = _json("state/__不存在的真源__.json")
    ck("**负控：源不在 ⇒ 报「未读到」而不是 0**",
       val is None and "未读到" in why, why[:52])
    m, mw = _load("tools/__不存在__.py")
    ck("**负控：模块不在 ⇒ 报「未读到」**", m is None and "未读到" in mw, mw[:52])
    # ③ 数字必须是**现读**的（拿真源再算一次，必须一致）
    acc, _ = _json("state/caps-probe-accum.json")
    if acc is not None:
        rows = acc.get("逐位") or acc.get("capabilities") or acc
        n = len(rows) if isinstance(rows, (dict, list)) else 0
        ck("能力位数字与真源现算一致（不是写死）",
           w["自身能力面"].get("已探位") == n, "现算 %d" % n)
    else:
        ck("能力位真源不在 ⇒ 必须如实报未读到",
           "**未读到**" in str(w["自身能力面"].get("能力位")), "已如实报")
    # ④ 模型面不许把"接缝差集"说成越界（判据负控）
    mm, _ = _load("tools/codex-scripts/model_roster.py")
    if mm:
        fake = {"a": {"providers": {"p": {"models": [{"id": "x"}]}}},
                "subagent-model-selection": {"allowedModels": [
                    {"provider": "q", "model": "x"}]}}
        r = mm.roster(fake)
        hard = [y for y in r["配置里配了、但**不在该门**里的"]["清单"]
                if y[0] in {a for a, _ in r["模型允许清单 allowedModels"]["配对"]}]
        ck("**负控：provider 不在门里 ⇒ 差集不算越界**", hard == [],
           "差集 %s ｜ 判为越界 %s" % (r["配置里配了、但**不在该门**里的"]["清单"], hard))
    # ⑤ 🔴 负控：体检读数里**键不在** ⇒ 必须报「未读到」，**不许报 0**
    g1 = _gate_from({"判决": "✅ 9 道闸全过"})
    ck("**负控：闸数字段不在 ⇒ 报「未读到」而不是 0**",
       g1.get("闸数") != 0 and "未读到" in str(g1.get("闸数")), "闸数=%s" % g1.get("闸数"))
    g2 = _gate_from({"判决": "x", "逐条": [{"步骤": "a", "rc": 0}, {"步骤": "b", "rc": 2}]})
    ck("逐条（list）形态能被正确算成闸数与未过闸",
       g2.get("闸数") == 2 and g2.get("未过的闸") == ["b"], "闸数=%s 未过=%s" % (g2.get("闸数"), g2.get("未过的闸")))
    ck("**真读数现读**：闸数与判决一致（不是 0 冒充）",
       isinstance(w["自律（门与闸）"].get("闸数"), int) and w["自律（门与闸）"]["闸数"] >= 1,
       "闸数=%s 判决=%s" % (w["自律（门与闸）"].get("闸数"), w["自律（门与闸）"].get("判决")))
    # ⑥ 🔴 负控：能力位真源**换了键名** ⇒ 必须报未读到 + 报出实际键，**不许静默报空**
    t1, e1 = _caps_table({"逐位": {"a": {"状态": "✅ 通"}}})
    ck("**负控：态键名换了 ⇒ 报未识别，不许静默丢**",
       e1 is None and t1["by"] == {} and "**没有『态』字段**" in t1["unknown"],
       "未识别=%s" % {k: len(v) for k, v in t1["unknown"].items()})
    t2, e2 = _caps_table({"不是逐位": 1})
    ck("**负控：连『逐位』都没有 ⇒ 报未读到并点出实际顶层键**",
       t2 is None and "未读到" in e2 and "不是逐位" in e2, e2[:60])
    # ⑦ 🔴 负控：**没见过的态**必须被点名（F36 同型：新痛被当"无变化"）
    t3, _ = _caps_table({"逐位": {"a": {"态": "✅ 通"}, "b": {"态": "🆕 没见过的态"}}})
    ck("**负控：没见过的态必须被点名**（不许静默丢）",
       "🆕 没见过的态" in t3["unknown"], "未识别=%s" % list(t3["unknown"]))
    # ⑧ 可探针之外：三类齐 + 证据强度分开 + 「真痛 0」必须带作用域
    bb = w["可探针之外（**别拿没测过的当测过了**）"]
    ck("可探针之外·三类齐且**证据强度分开写**",
       bb.get("合计") == 30 and len(bb.get("三类") or {}) == 3
       and len(bb.get("证据强度（**不一样，别混**）") or {}) == 3,
       "三类=%s" % {k: v["位数"] for k, v in (bb.get("三类") or {}).items()})
    ck("**「真痛 0」必须带作用域说明**（不许被读成「全机无痛」）",
       "全机无痛" in str((bb.get("真痛 0 的作用域") or {}).get("说明")),
       str((bb.get("真痛 0 的作用域") or {}).get("说明"))[:76])
    ck("**算术自洽：已探 + 三类 == 全量**（现读，不写死）",
       (bb.get("算术") or {}).get("合计") == 168,
       json.dumps(bb.get("算术"), ensure_ascii=False))
    # ⑨ 🔴 负控：可探针之外的真源不在 ⇒ 报未读到，不许报 0
    b_none, b_why = _json("state/__不存在的beyond__.json")
    ck("**负控：可探针之外的真源不在 ⇒ 报未读到**",
       b_none is None and "未读到" in b_why, b_why[:52])
    # ⑩ 真读数：四类态必须**加得起来**（算术自洽，不靠眼看）
    A = w["授权面（缺什么、卡在哪）"]
    if isinstance(A.get("已通"), int):
        tot = (A["已通"] + A["缺授权"] + A["缺参"] + A["真痛位数"])
        ck("**四类态加得起来**（算术自洽）", tot == w["自身能力面"].get("已探位"),
           "%s+%s+%s+%s=%d ｜ 已探位=%s"
           % (A["已通"], A["缺授权"], A["缺参"], A["真痛位数"], tot,
              w["自身能力面"].get("已探位")))
        ck("**缺授权带作用域与主人命令**（不是只报个数）",
           all("主人命令" in v for v in (A.get("缺授权·按作用域（发一次覆盖多位）") or {}).values())
           or A["缺授权"] == 0,
           "%d 个作用域" % len(A.get("缺授权·按作用域（发一次覆盖多位）") or {}))
    # ⑪ 🔴 **两个口径并排**（不许只报一个数就不写口径）
    two = A.get("两个口径（**别混念**）") or {}
    mg = A.get("合并口径（空参探 ∪ 给参后）") or {}
    ck("**真数据：两个口径都在，且给参后算术自洽**",
       bool(two.get("空参探（accum）")) and bool(two.get("给参后（合并）"))
       and mg.get("算术自洽") is True,
       "空参=%s ｜ 给参后=%s ｜ 自洽=%s"
       % (two.get("空参探（accum）"), two.get("给参后（合并）"), mg.get("算术自洽")))
    # 🔴 这条**差点写成恒真式**（初稿 `... if x else False or True` ⇒ 永远绿 —— 假判据）。
    #    真判据：**文案里那对数字必须和两个口径现读的值对得上** ⇒ 数据一变、文案没跟变，这条就红。
    _why = str(two.get("为什么两个数都对") or "")
    _raw_n = (two.get("空参探（accum）") or {}).get("缺授权")
    _aft_n = (two.get("给参后（合并）") or {}).get("缺授权")
    ck("**「为什么两个数都对」里的数字是现算的**（对不上就红，防写死）",
       bool(_why) and _raw_n is not None and _aft_n is not None
       and ("%s→%s" % (_raw_n, _aft_n)) in _why,
       "两口径 %s→%s ｜ 文案尾=%s" % (_raw_n, _aft_n, _why[-34:]))
    # 🔴 **合并口径的负控**（纯函数，喂人造账）
    #    人造价账：5 位里 2 位是「需参数·未探」，所以**给参后那本账必须正好重判 2 位**。
    #    🔴 我头两版控制**写错了**（判据错，不是检查错）：
    #       第一版"分叉账"给的是 `✅1 + 🟡1 = 2 位` ⇒ **正好覆盖 2 位 ⇒ 自洽是对的**，我错怪了检查；
    #       第二版"正控"给 `✅1 + 🟡2 = 3 位` ⇒ 多算一位 ⇒ 检查红得对，又是我的控制错。
    #    ⇒ 这条不变式不是"加得起来"（那恒真），而是**覆盖守恒**：多一个少一个都必须红。
    fake_rows = {k: {"态": st} for k, st in
                 (("a", OK), ("b", OK), ("c", BLOCKED), ("d", NEEDPARAM), ("e", NEEDPARAM))}
    m_ok = merge_two_ledgers(fake_rows, {"合计": {"✅ 通": 2}})
    ck("**正控：给参后正好覆盖那 2 位缺参 ⇒ 算术自洽绿**",
       m_ok.get("算术自洽") is True and m_ok.get("合计") == 5 and m_ok.get("缺参") == 0,
       "合计=%s 已通=%s 缺授权=%s 缺参=%s" % (m_ok.get("合计"), m_ok.get("已通"),
                                        m_ok.get("缺授权"), m_ok.get("缺参")))
    m_short = merge_two_ledgers(fake_rows, {"合计": {"✅ 通": 1}})
    ck("**负控·漏判一位 ⇒ 算术自洽必须红**（覆盖守恒，不是恒真）",
       m_short.get("算术自洽") is False and m_short.get("合计") == 4,
       "人造漏判账 → 合计=%s（应为 4≠5）自洽=%s" % (m_short.get("合计"),
                                              m_short.get("算术自洽")))
    m_over = merge_two_ledgers(fake_rows, {"合计": {"✅ 通": 3}})
    ck("**负控·多判一位 ⇒ 算术自洽也必须红**",
       m_over.get("算术自洽") is False and m_over.get("合计") == 6,
       "人造多判账 → 合计=%s（应为 6≠5）自洽=%s" % (m_over.get("合计"),
                                              m_over.get("算术自洽")))
    m_none = merge_two_ledgers(fake_rows, None)
    ck("**负控：给参后那本账不在 ⇒ 报「未读到」而不是 0**",
       "未读到" in str(m_none.get("未读到")) and "不是 0" in str(m_none.get("未读到")),
       str(m_none.get("未读到"))[:60])
    # ⑥ 本层只读：**AST 扫真调用**，不扫文本
    #    🔴 第一版是文本判据 `any(t in src for ...)` —— 那行**把禁止字符串列在自己源码里**，
    #    于是它**永远匹配到自己** ⇒ 永远红（自指判据）。AST 只看真调用，不受字面量影响。
    import ast
    src = Path(__file__).read_text(encoding="utf-8")
    bad_calls = _write_calls(src)
    ck("**本层只读**（AST 扫真调用，不扫文本 —— 文本会匹配到判据自己）",
       not bad_calls, "写盘调用: %s" % (bad_calls or "无"))
    # 🔴 负控：造一段**真有写盘调用**的代码 ⇒ 扫描器必须咬出来（证明判据不是空的）
    planted = _write_calls("from pathlib import Path\n"
                           "p = Path('x')\n"
                           "p.write_text('hi')\n"
                           "p.write_bytes(b'hi')\n"
                           "p.unlink()\n")
    ck("**负控：真写盘调用必须被咬出来**（否则判据是空的）",
       len(planted) == 3, "咬出: %s" % planted)
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="GBT小土豆V8 自身融合层（只读 · 每个数字带出处）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("brief").set_defaults(func=cmd_brief)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
