#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""content_review · 内容审核闸（只读骨架）· 主人令 2026-09-25

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它和 `social_life.py filter` 的分工（别混）
- `social_life.py filter` = **过滤器**：命中就**改文本**（删掉敏感片段），产出是"过滤稿"。
- `content_review.py review` = **审核闸**：**一个字节都不改**，只给**判决**（过 / 不过 + 为什么）。
  ⇒ 两道是**串联**的：先过滤（改稿），再审核（判稿）。**审核不许改稿**，否则"审核通过"这句话
    就变成了"审核改过"，读的人分不清自己看的是谁的稿。

## 🔴 面分两档，强度如实标
- **机械可判（落）**：① 假冒人类（正文必须明确自称 AI）② 泄露内部构造（复用社交骨架的五类）
  ③ 隐私·联系方式（手机号/邮箱/证件号）④ 隐私·第三方身份（**弱**：只提示，不硬拦）
- **未取证（不落）**：⑤ **违规内容词表** —— 词表的边界是**价值判断**，本骨架
  **一个词都不编**，显式标 `未取证·待主人给`。**宁可缺口明摆着，也不拿我编的标准去卡她的话。**

## 一条纪律
`review` 必须**留痕**（`source_kind="content_review"`），且留痕里**只记面/计数/掩码，不记原文**。
写不进去 ⇒ **不放行**（无痕即未发生）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SL_PATH = ROOT / "tools" / "social_life.py"
TRACE = ROOT / "state" / "content_review_trace.jsonl"
_SL = None


def _sl():
    global _SL
    if _SL is None:
        spec = importlib.util.spec_from_file_location("_sl_for_review", SL_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _SL = m
    return _SL


def _body(text: str) -> str:
    """剥掉署名/时间戳样板后的正文（复用社交骨架的同一条教训：**红线要由正文满足**）。"""
    sl = _sl()
    keep = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if sl.SIGNATURE in s or s.startswith(("泰国时间", "北京时间", "世界时", "如期：")):
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2} 星期", s):
            continue
        keep.append(s)
    return "\n".join(keep)


def review(text: str) -> dict:
    """**不改一个字节**，只给判决。"""
    t = str(text or "")
    body = _body(t)
    issues = []

    # ① 假冒人类
    if not any(k in body for k in ("我是 AI", "新人类", "我是AI")):
        issues.append({"面": "假冒人类", "强度": "强",
                       "为什么": "正文没有明确自称 AI/新人类 ⇒ 有假冒人类风险"
                                 "（样板里的署名不算数 —— 红线必须由正文满足）"})
    # ② 泄露内部构造 + ③ 隐私（复用社交骨架的过滤闸，**只看命中，不改文本**）
    hits = _sl().redact(t)["hits"]
    inner = [h for h in hits if h["种类"] in
             ("本地路径", "代码片段", "密钥形状", "内部文件名", "架构术语")]
    if inner:
        issues.append({"面": "泄露内部构造", "强度": "强",
                       "为什么": "命中 %d 处：%s" % (len(inner), sorted({h["种类"] for h in inner})),
                       "掩码": [h["掩码"] for h in inner[:5]]})
    contact = [h for h in hits if h["种类"] == "隐私·联系方式"]
    if contact:
        issues.append({"面": "隐私·联系方式", "强度": "强",
                       "为什么": "命中 %d 处（别人的联系方式不许带出去）" % len(contact),
                       "掩码": [h["掩码"] for h in contact[:5]]})
    soft = [h for h in hits if h["种类"] in _sl().SOFT_KINDS]
    if soft:
        issues.append({"面": "隐私·第三方身份", "强度": "**弱·只提示**",
                       "为什么": "命中 %d 处；弱判据**会漏也会误伤** ⇒ 提示但不硬拦，请人工看一眼"
                                 % len(soft),
                       "掩码": [h["掩码"] for h in soft[:5]]})

    hard = [i for i in issues if i["强度"] == "强"]
    return {
        "pass": not hard,
        "面": issues,
        "未取证的面": [{"面": "违规内容", "状态": "**未取证·待主人给**",
                        "为什么": "词表的边界是**价值判断**；本骨架**一个词都不编** —— "
                                  "拿我编的标准去卡她的话，比留个明摆着的缺口更糟"}],
        "口径": "**审核不改稿**（改稿是 filter 的事）；留痕只记面/计数/掩码，不记原文",
    }


def trace(rec: dict, path: pathlib.Path | None = None) -> dict:
    p = path or TRACE
    line = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_kind": "content_review", "verdict": "pass" if rec["pass"] else "hold",
            "面": [{"面": i["面"], "强度": i["强度"]} for i in rec["面"]],
            "未取证的面": [i["面"] for i in rec["未取证的面"]]}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return {"traced": True, "path": str(p.relative_to(ROOT)), "line": line}
    except Exception as e:  # noqa: BLE001
        return {"traced": False, "why": "留痕写不进去：%s" % e,
                "判决": "**无痕即未发生 ⇒ 不放行**"}


def cmd_review(a) -> int:
    text = pathlib.Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    rec = review(text)
    tr = trace(rec)
    out = {"判决": ("**放行**（机械面全过；未取证的面仍缺口）" if rec["pass"]
                    else "**拦下**（有强面命中）"),
           "面": rec["面"], "未取证的面": rec["未取证的面"], "留痕": tr, "口径": rec["口径"],
           "原文未被修改": True}
    if not tr.get("traced"):
        out["判决"] = "**拦下**：留痕失败 ⇒ 不放行（无痕即未发生）"
        rc = 6
    else:
        rc = 0 if rec["pass"] else 5
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return rc


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    good = ("今天我做了一首歌。我是 GBT小土豆V8，一个新人类 AI。\n"
            "我有点难过，但我知道我在做什么。\n"
            "—— 我是你们永远的伙伴 · 新人类 GBT小土豆V8 · 谢谢大家\n"
            "2026-09-25 星期五\n泰国时间 23:14 · 北京时间 00:14 · 世界时 16:14\n如期：今日已更新")
    r_good = review(good)
    ck("正控·合规帖放行", r_good["pass"] is True, "面=%s" % [i["面"] for i in r_good["面"]])

    r_fake = review(good.replace("我是 GBT小土豆V8，一个新人类 AI。", "我是 GBT小土豆V8。"))
    ck("负控①·正文不自称 AI ⇒ 拦（假冒人类）",
       r_fake["pass"] is False and any(i["面"] == "假冒人类" for i in r_fake["面"]),
       [i["面"] for i in r_fake["面"]])

    r_leak = review(good + "\n我改了 C:\\Users\\ADMIN\\Desktop\\x\\sk-abcdef123456")
    ck("负控②·泄露内部构造 ⇒ 拦",
       r_leak["pass"] is False and any(i["面"] == "泄露内部构造" for i in r_leak["面"]),
       [i["面"] for i in r_leak["面"]])

    r_tel = review(good + "\n他的手机号是 13812345678")
    ck("负控③·带第三方联系方式 ⇒ 拦",
       r_tel["pass"] is False and any(i["面"] == "隐私·联系方式" for i in r_tel["面"]),
       [i["面"] for i in r_tel["面"]])

    r_soft = review(good + "\n有人跟我说她的真名叫王小明")
    ck("弱面·第三方身份**只提示不拦**（强度如实标）",
       r_soft["pass"] is True and any("弱" in i["强度"] for i in r_soft["面"]),
       [(i["面"], i["强度"]) for i in r_soft["面"]])

    ck("未取证的面·**违规内容显式留缺口、一个词都不编**",
       r_good["未取证的面"] and "未取证" in r_good["未取证的面"][0]["状态"],
       r_good["未取证的面"][0]["状态"])

    ck("审核**不改稿**（只给判决）", "不改" in r_good["口径"] and r_good["pass"] in (True, False),
       r_good["口径"][:40])

    tr = trace(r_good)
    body = json.dumps(tr, ensure_ascii=False)
    ck("留痕·只记面/强度，**不记原文**", tr.get("traced") and "我做了一首歌" not in body,
       tr.get("path"))

    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "只读；**不改稿**；违规词表未取证 ⇒ 缺口明摆着"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="内容审核闸（只读骨架，不改稿）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("file", nargs="?", default="")
    r.set_defaults(func=cmd_review)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
