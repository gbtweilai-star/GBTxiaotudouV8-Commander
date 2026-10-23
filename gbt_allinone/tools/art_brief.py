# gbt-capability: art_brief
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""art_brief —— **作品策划位**（人话一次问，四路知识同时到位，并给出可直接照抄的出片命令）。

## 来历（主人令：把前几刀散着的器官「串成一条链、封成一位」）

前几刀陆续吞出四个**知识器官**，各管一段，但**没人把它们串起来**：

| 器官 | 管什么 |
|---|---|
| `ui_kit` | **可渲件** —— 纯 HTML/CSS 组件（`uiverse-io/galaxy` · 一把 3802 件） |
| `bits_kit` | **参考件** —— react-bits 216 个动效组件（React 实现，**只学不搬**：许可禁止再分发/移植） |
| `motion_kit` | **动效 API** —— anime.js 的 67 个导出（怎么让它动起来） |
| `design_atlas` | **技法节** —— 18 份设计手册里该读哪一节（带 `文件#L行号`） |
| `art_chain` | **出片** —— 挑件 → 取件 → 真渲 → 调优 |

本件把它们串成**一条链**：`plan` 一次问齐四路（**全是零作用域的读**），给出「用哪件 · 为什么 · 怎么动 · 学哪节」
与**下一步可直接执行的命令**；`run` 则真去跑 `art_chain` 出片，**内层门缺什么就如实带出什么**。

## 铁律

1. **每路都走既有门**（`run_task`），**不直连模块、不重写任何一环**。
2. **缺哪一路就如实报缺**（命中 0 就是 0），不许拿别的路凑数。
3. **失败停在原地并说清哪一步、被什么挡的**（内层门拒就把 `missing_scopes` 原样带出来）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OPS = ("status", "where", "plan", "run")

# 四路知识点：kind → (中文路名, 这东西管什么)
_LEGS = (
    ("ui_kit", "可渲件", "纯 HTML/CSS 组件，**能直接进渲染器出图**"),
    ("bits_kit", "参考件", "react-bits 的 React 实现，**读来学**（许可禁止再分发/移植 ⇒ 不搬成品）"),
    ("motion_kit", "动效API", "anime.js 的真 API（带签名与出处行号）—— 让画面动起来"),
    ("design_atlas", "技法节", "18 份设计手册里该读哪一节（带 文件#L行号）"),
)

# 🔴 2026-10-13 补洞（真跑咬出来的）：**这条链听不懂「作品类型的口语」**。
#    病象：问「产品落地页首屏」⇒ 四路里只有 `design_atlas` 命中 613；问「短视频片头」⇒ **四路全 0**。
#    因：四路收的是 **组件名 / API 名 / 手册小节名**（全是英文），而人话问的是**作品类型**。
#    ⇒ 先把作品类型**拆成四路听得懂的词**，再问（这叫拆解，不是编造：拆出的词全是我们自己定的检索口径）。
_WORK_TYPES = {
    "落地页": "hero 英雄区 按钮 卡片 渐变 毛玻璃 阴影 滚动 悬停",
    "首屏": "hero 英雄区 渐变 毛玻璃 滚动",
    "英雄区": "hero 渐变 毛玻璃",
    "官网": "hero 导航 卡片 渐变",
    "导航": "nav 菜单 悬停",
    "定价页": "卡片 按钮 表格",
    "仪表盘": "卡片 进度 图表 数字",
    "登录页": "表单 输入框 按钮",
    "注册页": "表单 输入框 按钮",
    "作品集": "画廊 卡片 悬停",
    "画廊": "gallery 卡片 悬停",
    "加载页": "加载 进度 骨架屏",
    "错误页": "加载 按钮 卡片",
    "公告条": "通知 提示",
}
# 四路**管不着**的域：如实说出来，并指向该去的地方（不许硬凑一个候选给它）
_OUT_OF_SCOPE = {
    "片头": "视频/成片", "片尾": "视频/成片", "短视频": "视频/成片", "短片": "视频/成片",
    "电影": "视频/成片", "剪辑": "视频/成片", "转场": "视频/成片", "字幕": "视频/成片",
    "音乐": "音频", "配音": "音频", "配乐": "音频", "语音": "音频", "歌曲": "音频",
}


def _cap(kind: str, payload: dict) -> dict:
    """调**既有能力位** —— 走唯一门 `run_task`（不直连模块、不绕门）。"""
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    import gbt_allinone as _g
    r = _g.run_task(kind, payload)
    res = None
    if isinstance(r.get("gbt_result"), dict):
        res = (r["gbt_result"] or {}).get("result")
    if res is None and isinstance(r.get("result"), dict):
        res = r.get("result")
    return {"status": r.get("status"), "denied": bool(r.get("denied")),
            "missing_scopes": r.get("missing_scopes"), "result": res or {}}


def _slim(kind: str, row: dict) -> dict:
    """每路只留**最该知道的几格**（不把整行倒给调用方）。"""
    keep = {
        "ui_kit": ("path", "cat", "text", "urls", "effects", "score"),
        "bits_kit": ("name", "category", "desc", "src", "reg", "deps", "net", "license", "score"),
        "motion_kit": ("name", "module", "kind", "doc", "sig", "where", "score"),
        "design_atlas": ("kind", "file", "title", "summary", "where", "score"),
    }.get(kind, tuple(row))
    return {k: row.get(k) for k in keep if k in row}


def plan(q: str = "", limit: int = 3, **_kw) -> dict:
    """人话一次问 → **四路知识同时到位** + **下一步可直接照抄的命令**。**缺哪一路就如实报缺**。"""
    if not str(q or "").strip():
        return {"ok": False, "op": "plan", "fail_closed": True, "status": "needs_params",
                "error": "要给 q（人话，如「复古霓虹按钮的动效」）"}
    qs = str(q).strip()
    # ① 作品类型 → 拆成四路听得懂的词（**我们自己的检索口径**，不是对上游数据的断言）
    hit_types = [k for k in _WORK_TYPES if k in qs]
    extra = " ".join(_WORK_TYPES[k] for k in hit_types)
    qq = (qs + " " + extra).strip()
    # ② 四路管不着的域（视频/音频）如实说，并指向该去的地方 —— **不许硬凑一个候选给它**
    oos = sorted({v for k, v in _OUT_OF_SCOPE.items() if k in qs})
    t0 = time.time()
    legs, missing, steps = {}, [], []
    for kind, cn, what in _LEGS:
        r = _cap(kind, {"op": "find", "q": qq, "limit": limit})
        res = r["result"]
        hits, items = res.get("hits"), (res.get("items") or [])
        # 🔴 2026-10-13 修（换全新 store 时被真读数咬出来）：这一路**索引还没建**时，
        #    内层返回的是 `needs_build` 且**根本没有 `hits` 键** ⇒ 首版会给出 `hits: null`，
        #    看着像"命中 0"，其实**根本没就绪**。⇒ 必须显式区分「没就绪」与「命中 0」。
        ready = bool(res.get("ok")) and hits is not None
        legs[cn] = {"from": kind, "管什么": what, "gate": r["status"], "ready": ready,
                    "hits": hits, "头几件": [_slim(kind, it) for it in items]}
        if not items:
            if not ready:
                why = "**这一路没就绪**（先给它 op=build）：%s" % (res.get("error") or res.get("status"))
            elif r.get("denied"):
                why = "内层门拒（缺 %s）" % r.get("missing_scopes")
            else:
                why = "命中 0 —— 表里没有这个说法，不硬塞"
            missing.append({"路": cn, "from": kind, "为什么": why})
        steps.append({"step": kind, "gate": r["status"], "hits": hits,
                      "ready": ready, "denied": r.get("denied")})
    nxt = ("python tools/codex-scripts/five-dim.py cap art_chain '"
           + json.dumps({"op": "run", "q": q}, ensure_ascii=False) + "'")
    out = {"ok": True, "op": "plan", "q": q, "四路": legs, "steps": steps,
            "缺哪一路": missing,
            "下一步": nxt,
            "怎么读这份简报": "① **可渲件**是能直接进渲染器的（纯 HTML/CSS）；② **参考件**是 React 实现，"
                              "**只读来学、照着手写自己的**（许可禁止再分发/移植）；③ **动效API** 给到签名与"
                              "`文件#L行号`；④ **技法节**给到该读哪份手册哪一节。",
            "seconds": round(time.time() - t0, 2),
            "_口径": "**四路全是零作用域的读**（走唯一门 `run_task`）；某一路命中 0 就如实报 0，"
                     "**不拿别的路凑数**；`run` 才是真出片，且内层门缺什么会原样带出来"}
    if hit_types:
        out["拆解"] = {"作品类型": hit_types, "加的词": extra,
                       "口径": "人话问的是**作品类型**，四路收的是**组件名/API名/手册小节名** ⇒ "
                               "先按这张表拆成四路听得懂的词再问（表是我们自己定的，可复核可改）"}
    if oos:
        out["范围外提示"] = {"域": oos,
                            "为什么": "这四路是 **web/UI 侧**的知识（组件 · 动效 · 设计技法）；"
                                      "**视频/音频不归它们管** ⇒ 四路给 0 是**正常的空**，不是坏了",
                            "该去哪": {"视频/成片": "`video` 域 / `media_pipeline` / `art_chain`（只出静态图）",
                                       "音频": "`voice` 域（TTS/ASR）"}}
    return out


def run_chain(q: str = "", look=None, size: int = 1800, sharpen: float = 0.8,
              grain: int = 3, grade_fmt: str = ".png", name: str = "",
              width: int = 900, height: int = 600, **_kw) -> dict:
    """真出片：把整条链交给 `art_chain`（**不重写任何一环**）。**失败停在原地并说清被什么挡的**。"""
    if not str(q or "").strip():
        return {"ok": False, "op": "run", "fail_closed": True, "status": "needs_params",
                "error": "要给 q（人话）"}
    r = _cap("art_chain", {"op": "run", "q": q, "look": look, "size": size, "sharpen": sharpen,
                           "grain": grain, "grade_fmt": grade_fmt, "name": name,
                           "width": width, "height": height})
    res = r["result"]
    ok = bool(res.get("ok"))
    out = {"ok": ok, "op": "run", "q": q, "gate": r["status"], "stage": res.get("stage"),
           "product": res.get("product"), "verdict": res.get("verdict"),
           "清晰度变化_pct": res.get("清晰度变化_pct"), "steps": res.get("steps"),
           "seconds": res.get("seconds"), "ledger": res.get("ledger")}
    if not ok:
        out["error"] = res.get("error")
        # 🔴 内层门拒时，**原样带出缺什么**（不许把它折成一句"失败了"）
        out["inner_denied"] = res.get("inner_denied")
        out["inner_missing_scopes"] = res.get("inner_missing_scopes") or r.get("missing_scopes")
        out["_口径"] = ("失败**停在原地**：`stage` 是断在哪一步；`inner_*` 是**内层门**缺什么"
                        "（外层过了门、内层还要它自己那一份授权 ⇒ 要么主人发一次时段授权，"
                        "要么把该步改成编排位自己落盘）")
    return out


def status(**_kw) -> dict:
    legs = []
    for kind, cn, what in _LEGS:
        r = _cap(kind, {"op": "status"})
        res = r["result"]
        legs.append({"from": kind, "路名": cn, "gate": r["status"], "ok": bool(res.get("ok")),
                     "在位": res.get("indexed", res.get("src_present")), "管什么": what})
    r_ac = _cap("art_chain", {"op": "status"})
    return {"ok": True, "op": "status", "kind": "art_brief", "ops": list(_OPS),
            "四路": legs,
            "出片": {"from": "art_chain", "gate": r_ac["status"],
                     "链": (r_ac["result"] or {}).get("chain")},
            "_口径": "本位是**编排位**：`plan` 走四路**零作用域的读**，`run` 把整条链交给 `art_chain`；"
                     "自己不重写任何一环、不直连模块"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "art_brief",
            "entry": "run_task('art_brief', {'op':'plan','q':'复古霓虹按钮的动效'})", "ops": list(_OPS),
            "what": "把前几刀散着的四个知识器官 + 出片链**串成一位**：人话一次问 → 用哪件 · 怎么动 · 学哪节 · 怎么出片",
            "链": [{"路": cn, "from": k, "管什么": w} for k, cn, w in _LEGS]
                    + [{"路": "出片", "from": "art_chain", "管什么": "挑件 → 取件 → 真渲 → 调优"}],
            "hard_rules": ["每路都走既有门 `run_task`（不直连模块、不绕门、不重写任何一环）",
                           "缺哪一路就如实报缺（命中 0 就是 0，不拿别的路凑数）",
                           "失败停在原地并说清哪一步、被什么挡的（内层门拒就带出 missing_scopes）",
                           "**许可纪律**：`bits_kit` 那一路是**参考件**（许可禁止再分发/移植）⇒ 只读来学，不搬成品"],
            "上游": ["ui_kit", "bits_kit", "motion_kit", "design_atlas", "art_chain"],
            "下游": "产物落 `outputs/art-chain/`；好不好看是人的判断，本件只给读数与命令"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    if op == "plan":
        return plan(**params)
    if op == "run":
        return run_chain(**params)
    for nm, fn in (("status", status), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    try:                        # 本机控制台默认 GBK ⇒ 中文直接打会 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="作品策划位（人话 → 四路知识 + 出片命令）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
