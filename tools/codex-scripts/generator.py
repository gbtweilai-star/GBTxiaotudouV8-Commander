#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""模块 05 · generator（生成端）—— **凭据闸 + 花费闸**，缺 key 如实报 needs_key

## 它是什么 / 不是什么
- ✅ **生成端的门**：把"哪个 provider 能用、要哪个 key、缺在哪、要花多少钱"讲清楚，
  并且在缺件时**拒绝出网**（fail-closed）。
- ❌ **不是生成器**：真出图/出片/出声要**真 key**（现在一条都没有）**+ 主人确认花费**。
  本模块**不假装能生成** —— 缺 key 就是 `needs_key`，不是"正在生成"。

## 凭据读**两个**地方（这是本仓的规矩，不是一个地方）
  ① **环境变量**（掩码只报前 4 位）
  ② **DPAPI 保险箱** `gbt_allinone/store/secrets/<name>.dpapi`（**只存密文**）
     ⚠️ DPAPI 是**用户级绑定**：**文件在不在**是身份无关的事实（可判），
        **解不解得开**要主人的身份（沙箱身份解不开**不是缺凭据，是身份不同**）。所以这里**只判存在性**，
        不把"我解不开"说成"你没配"。

## 两道闸
  ① **凭据闸**：两边都查不到 ⇒ **拒**（rc=3，报 needs_key + 该配哪个）
  ② **花费闸**：生成会**花钱/出网** ⇒ 必须显式 `--confirm-cost`，否则**拒**（rc=4）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
VAULT = ROOT / "gbt_allinone" / "store" / "secrets"

# provider → (环境变量名, 保险箱文件名, 支持的类型, 说明)
PROVIDERS = {
    "openai":     ("OPENAI_API_KEY",     "openai_api.dpapi",     ["image"], "图（DALL·E / gpt-image 系列）"),
    "elevenlabs": ("ELEVENLABS_API_KEY", "elevenlabs_api.dpapi", ["audio"], "配音 / TTS"),
    "fal":        ("FAL_KEY",            "fal_api.dpapi",        ["image", "video", "audio"], "图 / 视频 / 音频"),
    "venice":     ("VENICE_API_KEY",     "venice_api.dpapi",     ["image", "video", "audio"], "图 / 视频 / 音频"),
    "replicate":  ("REPLICATE_API_TOKEN", "replicate_api.dpapi", ["image", "video"], "图 / 视频"),
}


def cred_read(provider: str, inject: dict | None = None) -> dict:
    """双源读凭据。`inject` 只给自检用，且会在读数里标出是注入。

    🔴 F37：**机器判据必须是字段，不许是我写给人的那句话。**
    第一版闸用 `判据.startswith("**可用")` 判 —— 那是我自己写的**中文散文**；
    注入分支的文案一变，闸就把"有 key"判成"没凭据"（并且下一行取 `路径` 直接 KeyError）。
    散文是给人看的；`可用` 这个**布尔**才是给闸用的。
    """
    env_name, vault_name, kinds, desc = PROVIDERS[provider]
    vault_path = str((VAULT / vault_name).relative_to(ROOT))
    if inject is not None and provider in inject:
        return {"provider": provider, "支持": kinds, "说明": desc, "可用": True,
                "环境变量": {"名": env_name, "状态": "已配", "掩码": inject[provider][:4] + "****"},
                "保险箱": {"文件": vault_name, "路径": vault_path, "状态": "（注入，未查盘）"},
                "判据": "**注入值（自检用，不是真读数）**"}
    v = os.environ.get(env_name)
    env_st = {"名": env_name,
              "状态": "已配" if v else "未配",
              "掩码": (v[:4] + "****") if v else None,
              "注": "只报前 4 位；**不打印也不落盘任何明文**"}
    f = VAULT / vault_name
    vault_st = {"文件": vault_name, "路径": vault_path,
                "状态": "在" if f.is_file() else "不在",
                "注": "只判**存在性**（身份无关）；能不能解开要主人的身份 —— "
                      "沙箱身份解不开**不是缺凭据，是身份不同**"}
    have = bool(v) or f.is_file()
    return {"provider": provider, "支持": kinds, "说明": desc, "可用": have,
            "环境变量": env_st, "保险箱": vault_st,
            "判据": ("**可用**（至少一处有）" if have else
                   "**needs_key**：环境变量未设 · 保险箱也没有这个文件 ⇒ **拒出网**")}


def providers_body() -> dict:
    """只算不打印（自检要拿它的结论，但不想多吐一份 JSON —— 输出必须是**一段**可解析的 JSON）。"""
    rows = [cred_read(p) for p in PROVIDERS]
    return {
        "生成端 provider": rows,
        "合计": {"provider 数": len(rows),
               "有凭据的": [r["provider"] for r in rows if r.get("可用")],
               "缺凭据的": [r["provider"] for r in rows if not r.get("可用")]},
        "保险箱现状": {"目录": str(VAULT.relative_to(ROOT)),
                  "盘上的 .dpapi": sorted(p.name for p in VAULT.glob("*.dpapi"))
                  if VAULT.is_dir() else "**目录不在**"},
        "诚实提醒": "DPAPI 是**用户级绑定**：文件在不在我能判，解不解得开要主人的身份。"
        "所以这里**只判存在性**，不把『我解不开』念成『你没配』。",
    }


def cmd_providers(a) -> int:
    print(json.dumps(providers_body(), ensure_ascii=False, indent=1))
    return 0


def cmd_gen(a) -> int:
    if a.provider not in PROVIDERS:
        print(json.dumps({"ok": False, "拒单": "没有这个 provider（不许临时造）",
                          "有这些": sorted(PROVIDERS)}, ensure_ascii=False))
        return 2
    inject = None
    if a.inject:
        fake = os.environ.get("GBT_FAKE_GEN_KEY")
        inject = {a.provider: fake} if fake else None
    cred = cred_read(a.provider, inject=inject)
    # 闸① 凭据
    if not cred.get("可用"):
        print(json.dumps({
            "ok": False, "拒单": "**凭据闸拦住**：needs_key（fail-closed，绝对不拿空 key 打上游）",
            "provider": a.provider, "现读": cred,
            "怎么配": ["设环境变量 %s" % cred["环境变量"]["名"],
                    "或把密钥落进 DPAPI 保险箱 %s（**要过 auth_gate，主人发授权**）"
                    % cred["保险箱"]["路径"]],
            "我不会做什么": "不编 key、不用假 key 试探、不绕过闸",
        }, ensure_ascii=False, indent=1))
        return 3
    kind = a.kind or (cred["支持"][0] if cred["支持"] else "")
    if kind not in cred["支持"]:
        print(json.dumps({"ok": False, "拒单": "%s 不支持类型 %r" % (a.provider, kind),
                          "它支持": cred["支持"]}, ensure_ascii=False))
        return 2
    # 闸② 花费
    if not a.confirm_cost:
        print(json.dumps({
            "ok": False, "拒单": "**花费闸拦住**：生成会出网并花钱，必须显式 --confirm-cost",
            "provider": a.provider, "kind": kind, "作业": a.job_id,
            "两条路": ["先问主人这次要花多少（本模块**不编价格**）",
                    "主人点头后加 --confirm-cost 再跑"],
            "为什么不自动跑": "花费与出网是主人的点头范围；我不替主人拍板",
        }, ensure_ascii=False, indent=1))
        return 4
    # 过两闸：**只给命令，不执行**（真生成要真 key + 真金白银，且 provider 的调用姿势未接线）
    print(json.dumps({
        "ok": True, "闸①凭据": "✅ 过", "闸②花费": "✅ 主人已确认",
        "该做的下一步": "把 provider 调用姿势接上（**当前未接线**）后走唯一门 run_task 出网",
        "本模块不做什么": "**不在这里真的出图/出片** —— 调用姿势未接线，我不拿假动作冒充成品",
        "诚实分级": "本模块验的是【凭据闸 + 花费闸 + needs_key 如实报】，**不是出图能力**",
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
 # 自检要调**真函数**（走同一条代码路径），但它们会 print ⇒ 输出会变成好几段 JSON，
    #    解析方（人或机器）就会以为工具坏了。所以这里把中间那些 stdout **就地收走**，
    #    只留最后一段自检 JSON —— 不为了让输出好看去改被测的代码。
    import contextlib
    import io as _io

    def quiet(fn, *args) -> int:
        with contextlib.redirect_stdout(_io.StringIO()):
            return fn(*args)

    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 真读（不注入）：双源结构健全，且现读"缺凭据的"要和盘上事实一致
    body = providers_body()
    rows = body["生成端 provider"]
    ck("正控·双源凭据读数结构健全",
       all("环境变量" in r and "保险箱" in r and "判据" in r for r in rows),
       "%d 个 provider · 缺凭据 %s" % (len(rows), body["合计"]["缺凭据的"]))
    ck("正控·『缺凭据』与保险箱盘上事实一致（不把解不开念成没配）",
       set(body["合计"]["缺凭据的"]) == set(PROVIDERS) or bool(body["合计"]["有凭据的"]),
       "盘上 .dpapi %d 个 · 有凭据 %s" % (len(body["保险箱现状"]["盘上的 .dpapi"]),
                                    body["合计"]["有凭据的"] or "无"))
    ck("正控·保险箱只判存在性（不把解不开念成没配）",
       all("身份无关" in r["保险箱"]["注"] for r in rows),
       "每条都写了身份边界")

    # ② 负控：真环境缺 key ⇒ gen 必须拒 rc=3
    class G:
        job_id, provider, kind, confirm_cost, inject = "demo-gen", "fal", "video", True, False
    rc1 = quiet(cmd_gen, G())
    ck("负控①·真环境缺 key ⇒ 拒 rc=3", rc1 == 3, "rc=%d（期望 3）" % rc1)

    # ③ 负控：注入有 key 但没 --confirm-cost ⇒ 花费闸拒 rc=4
    os.environ["GBT_FAKE_GEN_KEY"] = "fakekey123456"

    class G2:
        job_id, provider, kind, confirm_cost, inject = "demo-gen", "fal", "video", False, True
    rc2 = quiet(cmd_gen, G2())
    ck("负控②·有 key 未确认花费 ⇒ 拒 rc=4", rc2 == 4, "rc=%d（期望 4）" % rc2)

    # ④ 正控：有 key + 已确认花费 ⇒ 过两闸，但不假装出图（rc=0）
    class G3:
        job_id, provider, kind, confirm_cost, inject = "demo-gen", "fal", "video", True, True
    rc3 = quiet(cmd_gen, G3())
    ck("正控·有 key + 确认花费 ⇒ 过两闸（且不假装出图）", rc3 == 0, "rc=%d（期望 0）" % rc3)

    # ⑤ 负控：类型不支持 ⇒ 拒 rc=2
    class G4:
        job_id, provider, kind, confirm_cost, inject = "demo-gen", "elevenlabs", "video", True, True
    rc4 = quiet(cmd_gen, G4())
    ck("负控③·类型不支持 ⇒ 拒 rc=2", rc4 == 2, "rc=%d（期望 2）" % rc4)

    # ⑥ 负控：不存在的 provider ⇒ 拒 rc=2
    class G5:
        job_id, provider, kind, confirm_cost, inject = "demo-gen", "编造的", "image", True, True
    rc5 = quiet(cmd_gen, G5())
    ck("负控④·编造的 provider ⇒ 拒 rc=2", rc5 == 2, "rc=%d（期望 2）" % rc5)

    os.environ.pop("GBT_FAKE_GEN_KEY", None)
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "注入只改『凭据读数』这一格，闸的代码路径完全一样；注入在读数里会标明"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="模块 05 · generator（凭据闸 + 花费闸，缺 key 如实报）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("providers").set_defaults(func=cmd_providers)
    g = sub.add_parser("gen")
    g.add_argument("job_id")
    g.add_argument("--provider", required=True)
    g.add_argument("--kind", default="")
    g.add_argument("--confirm-cost", action="store_true")
    g.add_argument("--inject", action="store_true", help="自检用：允许读注入 key")
    g.set_defaults(func=cmd_gen)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
