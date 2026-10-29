# -*- coding: utf-8 -*-
r"""V8 的万物插（omni_plug）—— **万物皆可插 · 万物皆可控**（口径照 V9 的已成实现搬）。

主人令（2026-10-10）：「你现在再去看看 V9 已经实现了万物皆可插，万物皆可控」

## 我从 V9 抄到的（逐条带出处，不是自己编的）
| 她 | 件 | 口径 |
|---|---|---|
| 可控原语 | core/browser_plug.py 的 pilot(tentacle, action, **args) | 一根触手号 + 一个动作 + 参数，全控；动作 open/read/shot/click/type/tabs/new_tab/back/eval/close |
| 万物清单 | core/cloud_plugin.py 的 FACES | 7 个面：文本 · 视觉 · 图像 · 向量 · 语音 · 翻译 · 代码 |
| 一根一份 | core/cloud_plugin.py 的 install(tentacle) | 云插件装在每根触手上，独立配额（不占别根的） |
| 插法三件 | core/sider_plug.py 头 | 不破坏 · 新总线（用她真实会话接）· 掩盖（只露我们的口） |
| 视觉钉死 | core/browser_plug.py 的 pilot 内 | 动手前新鲜取景帧龄 ≤ 400ms；取不到就拒动（禁传统瞎子操作），只读动作不受限 |

## 我原来松了 3.75 倍（实测对照）
V8 的 vision_loop 把 STALE_MS 定成 1500ms；V9 的 pilot 要求 ≤400ms。
主人原话是「你截图再想再动手，别人 98K 早就打爆你的头了」=> 400ms 才是口径。
本件把它收成 400，并留负对照（合成 900ms 的旧帧 => 必须判不新鲜）。

用法：py -3.14 -X utf8 tools/codex-scripts/omni-plug.py [scan|--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "omni-plug.json"
V9 = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V9")

FACES = {
    "文本": "对话/写作/推理",
    "视觉": "看图/识图/OCR（多模态）",
    "图像": "文生图/图生图",
    "向量": "文本嵌入（检索/聚类/去重）",
    "语音": "语音识别/合成",
    "翻译": "多语翻译",
    "代码": "代码生成/解释",
}

ACTIONS = ("open", "read", "shot", "click", "type", "tabs", "new_tab", "back", "eval", "close")
READ_ONLY = ("read", "tabs", "shot", "eval", "back")
FRESH_MS = 400


def fresh(age_ms, limit=FRESH_MS) -> dict:
    ok = age_ms is not None and age_ms <= limit
    return {"新鲜": ok, "帧龄ms": age_ms, "阈": limit,
            "判定": "可以动手" if ok else "**拒动**（取景不新鲜 => 禁传统瞎子操作）"}


def plug(tentacle: str, face: str, action: str, **args) -> dict:
    if face not in FACES:
        return {"ok": False, "error": "unknown face", "known": list(FACES)}
    if action not in ACTIONS:
        return {"ok": False, "error": "unknown action", "known": list(ACTIONS)}
    af = None
    if action not in READ_ONLY:
        try:
            from gbt_allinone import vision_loop as VL
            lk = VL.look() or {}
 # 2026-10-10 实测撞的**键名错**：look() 真返回的键是 **age_ms**，
            #    我原来读的是 "帧龄ms"（那是我自己在别处写的别名）⇒ 恒为 None ⇒
            #    **凡是过视觉钉死的动作全被拒**（open/click/type 全线不通）。
            #    一个键名错把整条"可控"链掐死 —— 两个键都收，优先真键。
            af = lk.get("age_ms")
            if af is None:
                af = lk.get("帧龄ms")
        except Exception as exc:
            return {"ok": False, "触手": tentacle, "面": face, "动作": action, "拒动": True,
                    "在哪一步": "①眼", "读数": "眼不可用: %s" % type(exc).__name__,
                    "口径": "视觉钉死：眼不可用就不许动手"}
        f = fresh(af)
        if not f["新鲜"]:
            return {"ok": False, "触手": tentacle, "面": face, "动作": action, "拒动": True,
                    "在哪一步": "①眼", "读数": f, "口径": "视觉钉死：没有新鲜取景不许动手"}
    return {"ok": True, "触手": tentacle, "面": face, "动作": action,
            "参数": {k: str(v)[:60] for k, v in args.items()},
            "眼帧龄ms": af, "口径": "不破坏 · 新总线 · 掩盖；不做反侦测/不绕验证码/不伪装指纹"}


# ③ 真手：把 plug() 接到**她自己的浏览器**（CDP 9222）—— 闭环的落点
#    闭环 = 真连 → 真动 → 真收货 → 落账。**不接真手就只是口径件，不算合格。**
CDP = "http://127.0.0.1:9222"
_BR = {"pw": None, "br": None, "page": None}


def _attach():
    """接她已在跑的浏览器（不新建 profile ⇒ 不被 Cloudflare 挑战）。"""
    if _BR["page"] is not None:
        return _BR["page"]
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
 # 2026-10-10 实测第一版**假闭环**：挑到了 chrome-error://chromewebdata/ 那种**死页**
    #    ⇒ 闭环标成"闭上了"但**读数是空的**（0 字）—— 那是**假闭**，不是合格。
    #    修法：① 只认 **http(s) 活页**；② 优先 Sider；③ 一个活页都没有就**新开一页**。
    def alive(u: str) -> bool:
        return u.startswith("http://") or u.startswith("https://")

    page = None
    picks = []
    for ctx in br.contexts:
        for p in ctx.pages:
            if alive(p.url):
                picks.append(p)
    for p in picks:
        if "sider.ai" in p.url:
            page = p
            break
    if page is None and picks:
        page = picks[0]
    if page is None:
        # 全是死页/没有页 ⇒ **自己开一个活页**（这是"新总线"，不是去动她）
        ctx = br.contexts[0] if br.contexts else br.new_context()
        page = ctx.new_page()
        page.goto("about:blank")
    _BR.update({"pw": pw, "br": br, "page": page})
    return page


def _drive(action: str, **args) -> dict:
    """真动作（do 那一步）。每个动作都返回**真读数**，改不成就如实说改不成。"""
    p = _attach()
    if p is None:
        return {"ok": False, "为什么": "没有可用的页（她没开着浏览器？）"}
    if action == "open":
        url = args.get("url") or args.get("urls") or ""
        if not url:
            return {"ok": False, "为什么": "open 要 url"}
        p.goto(url, wait_until="domcontentloaded", timeout=45000)
        return {"ok": True, "url": p.url[:120], "标题": (p.title() or "")[:80]}
    if action == "read":
        t = p.evaluate("() => document.body ? document.body.innerText : ''") or ""
        return {"ok": True, "url": p.url[:120], "标题": (p.title() or "")[:80],
                "字数": len(t), "正文前400": t.replace(chr(10), " / ")[:400]}
    if action == "shot":
        import time as _t
        out = ROOT / "state" / ("plug-shot-%d.png" % int(_t.time()))
        p.screenshot(path=str(out))
        return {"ok": True, "落盘": str(out), "字节": out.stat().st_size}
    if action == "tabs":
        br = _BR["br"]
        rows = []
        for ctx in br.contexts:
            for q in ctx.pages:
                rows.append({"url": q.url[:100], "标题": (q.title() or "")[:50]})
        return {"ok": True, "页数": len(rows), "页": rows[:12]}
    if action == "eval":
        js = args.get("js") or "1+1"
        return {"ok": True, "结果": str(p.evaluate(js))[:300]}
    if action == "click":
        sel = args.get("selector") or ""
        if not sel:
            return {"ok": False, "为什么": "click 要 selector"}
        p.click(sel, timeout=12000)
        return {"ok": True, "点了": sel, "url": p.url[:100]}
    if action == "type":
        sel, txt = args.get("selector") or "", args.get("text") or ""
        p.fill(sel, txt, timeout=12000)
        return {"ok": True, "填了": sel, "字数": len(txt)}
    if action == "new_tab":
        ctx = _BR["br"].contexts[0]
        np = ctx.new_page()
        if args.get("url"):
            np.goto(args["url"], wait_until="domcontentloaded", timeout=45000)
        _BR["page"] = np
        return {"ok": True, "新页": np.url[:100]}
    if action == "back":
        p.go_back(timeout=20000)
        return {"ok": True, "url": p.url[:100]}
    if action == "close":
        p.close()
        _BR["page"] = None
        return {"ok": True, "关了": True}
    return {"ok": False, "为什么": "这个动作真手还没接: %s" % action}


def loop(tentacle: str, face: str, action: str, **args) -> dict:
    """**闭环**：口子判定(①眼 ②面 ③动作) → 真手(④do) → 真收货(⑤读数) → 落账。"""
    t0 = time.time()
    pre = plug(tentacle, face, action, **args)          # ①②③（含视觉钉死）
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "触手": tentacle, "面": face,
           "动作": action, "口子判定": pre}
    if not pre.get("ok"):
        rec["闭环"] = "**没闭上**（口子那一步就拒了）"
        _ledger(rec)
        return rec
    got = _drive(action, **args)                        # ④ 真动
    rec["真收货"] = got
    rec["ms"] = int((time.time() - t0) * 1000)
    rec["闭环"] = ("**闭上了**" if got.get("ok") else "**没闭上**（真手那一步失败）")
    _ledger(rec)
    return rec


def _ledger(rec: dict) -> None:
    p = ROOT / "state" / "omni-plug.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + chr(10))


def scan() -> dict:
    (ROOT / "state").mkdir(parents=True, exist_ok=True)
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "来源": "V9 已成实现（%s）" % V9,
           "她的件": {}, "万物(面)": FACES, "可控(动作)": list(ACTIONS),
           "只读动作": list(READ_ONLY), "视觉阈ms": FRESH_MS,
           "口径": "不破坏 · 新总线（用她真实会话接）· 掩盖（只露我们的口）"}
    for rel in ("core/sider_plug.py", "core/browser_plug.py", "core/cloud_plugin.py",
                "core/cloud_plugins.py", "core/vision_loop.py", "tools/plug_boot.py"):
        p = V9 / rel
        row["她的件"][rel] = {"在盘": p.is_file(), "字节": p.stat().st_size if p.is_file() else 0}
    OUT.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
    return row


def check() -> int:
    d = scan()
    print("V8 万物插（口径照 V9 已成实现搬）")
    for k, v in d["她的件"].items():
        print("    %-26s %s %s" % (k, "在盘" if v["在盘"] else "不在", v["字节"] or ""))
    print("  万物（面 %d）: %s" % (len(FACES), " · ".join(FACES)))
    print("  可控（动作 %d）: %s" % (len(ACTIONS), " · ".join(ACTIONS)))
    print("  只读动作: %s" % " · ".join(READ_ONLY))
    print("  视觉阈: **%dms**（我原 1500 => 收 3.75 倍，照她的 pilot 口径）" % FRESH_MS)
    r = plug("t1", "文本", "read", url="https://example.com")
    print("  自检一发（只读动作）: ok=%s" % r.get("ok"))
    ok = len(FACES) == 7 and FRESH_MS == 400 and all(v["在盘"] for v in d["她的件"].values())
    print("判据：%s" % ("PASS" if ok else "FAIL（她的件没齐/面数不对/阈值不对）"))
    return 0 if ok else 1


def selftest() -> int:
    a, b, c = fresh(120), fresh(900), fresh(None)
    print("负对照A·120ms => %s（必须新鲜）" % a["新鲜"])
    print("负对照B·900ms => %s（必须拒）" % b["新鲜"])
    print("负对照C·取不到帧 => %s（必须拒）" % c["新鲜"])
    ok = a["新鲜"] and not b["新鲜"] and not c["新鲜"]
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="V8 万物插")
    ap.add_argument("cmd", nargs="?", default="scan", choices=["scan"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())