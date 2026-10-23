# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write, subprocess  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""触手自配装备与账号（tentacle_equip）—— 职业 → 需要什么 → 走门配上。

主人令（2026-10-09，逐字）：「还有触手自主注册配置自己的装备你看清楚」「还有职业也是一个不能少」。

本仓的两半（**都在 V8 自己这边**）：
  · **职业**：「tools/agency_tentacles.py」（职业触手中枢 · 五元身份 · 只读 frontmatter 不执行正文）；
    职业册现读落在「vaults/agency_tentacles/library/zh」（**条数与分域数现算，本文件不写数**，
    三件套 count=272 examined=272 truncated=False）。
  · **装备坞**：「tool_bay.py」（白名单 + 授权令牌 + 真探测 + 落账）。
  · **账号**：「tools/account_registry.py」（只记路径、禁存明文、一人一号）。

本件只做第二步：**按职业算出「这根触手要什么服务位 + 什么装备」→ 走上面两道门把它配上**。
纪律（照两道门自己的口径，不新造旁路）：
  · 不发明第三个账号库；凭据只从环境变量读，读不到就**如实报缺口**，不编账号；
  · 装装备必须过白名单 + 令牌；没令牌如实报 needs_grant —— **绝不假装装上了**；
  · 没立职业（职业名对不上册）→ **空需求**，不瞎配；
  · 每算一次、每配一次都落账。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
LIB_ZH = _ROOT / "vaults" / "agency_tentacles" / "library" / "zh"
LEDGER = _ROOT / "state" / "tentacle_equip.jsonl"

# ── 分域 → 需要的服务位（账号）与装备 ──
# ⚠ 本表是**本仓自定口径**（上游职业定义里没有「需要哪个账号」这一栏），依据 = 分域 + 职业名关键词。
DIVISION_NEEDS: dict = {
    "engineering": {"services": ("开源仓库", "数据库"), "tools": ("git", "sqlite", "json_tool")},
    "testing": {"services": ("开源仓库",), "tools": ("screen", "http", "json_tool")},
    "security": {"services": ("开源仓库", "邮箱"), "tools": ("http", "json_tool")},
    "gis": {"services": ("数据库",), "tools": ("image_ops", "http")},
    "design": {"services": ("邮箱",), "tools": ("image_ops", "http")},
    "marketing": {"services": ("邮箱",), "tools": ("http", "json_tool")},
    "paid-media": {"services": ("邮箱",), "tools": ("http", "json_tool")},
    "sales": {"services": ("邮箱",), "tools": ("json_tool",)},
    "support": {"services": ("邮箱",), "tools": ("json_tool",)},
    "product": {"services": ("数据库",), "tools": ("sqlite", "json_tool")},
    "project-management": {"services": ("邮箱", "数据库"), "tools": ("sqlite", "json_tool")},
    "finance": {"services": ("数据库",), "tools": ("sqlite", "json_tool")},
    "game-development": {"services": ("开源仓库",), "tools": ("git", "image_ops")},
    "spatial-computing": {"services": (), "tools": ("image_ops", "http")},
    "academic": {"services": ("数据库",), "tools": ("sqlite", "http")},
    "specialized": {"services": ("数据库",), "tools": ("json_tool",)},
    "supply-chain": {"services": ("数据库",), "tools": ("sqlite",)},
    "hr": {"services": ("邮箱",), "tools": ("json_tool",)},
    "legal": {"services": ("邮箱", "数据库"), "tools": ("sqlite", "json_tool")},
}
# 关键词 → 额外装备（从职业名/职责现算，不写死到某个角色）
KEYWORD_TOOLS = (("视频", "ffmpeg"), ("剪辑", "ffmpeg"), ("影像", "ffmpeg"), ("渲染", "ffmpeg"),
                 ("画面", "image_ops"), ("图", "image_ops"), ("视觉", "screen"), ("截图", "screen"),
                 ("界面", "ui_tree"), ("无障碍", "ui_tree"), ("GUI", "ui_tree"),
                 ("爬", "http"), ("抓取", "http"), ("检索", "http"), ("网络", "http"),
                 ("数据", "sqlite"), ("仓库", "git"), ("代码", "git"),
                 ("三维", "blender"), ("3D", "blender"), ("建模", "blender"),
                 ("压缩", "sevenzip"), ("打包", "sevenzip"), ("识别", "ocr"), ("文字", "ocr"),
                 ("网页", "puppeteer"), ("自动化", "puppeteer"), ("出图", "comfyui"), ("绘图", "comfyui"))
# 服务位 → 认它「已配」的环境变量（只看有没有，绝不回显值）
SERVICE_ENV = {"邮箱": "GBT_MAIL_ACCOUNT", "开源仓库": "GITHUB_TOKEN",
               "数据库": "GBT_DB_URL", "云插件": "GBT_CLOUD_KEY"}


@dataclass
class Need:
    slug: str
    profession: str
    division: str
    services: tuple = ()
    tools: tuple = ()
    reason: dict = field(default_factory=dict)


def _log(event: str, detail: str, ok: bool = True) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event,
                                "ok": ok, "detail": detail[:200]}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def professions(lang: str = "zh") -> dict:
    """现读职业册（**三件套 count/examined/truncated 不截断地报**）。读不到就如实报。"""
    from .tools import agency_tentacles as AT
    src = LIB_ZH if lang == "zh" else LIB_ZH.parent / "en"
    if not src.is_dir():
        return {"ok": False, "error": "职业源不在：%s" % src, "professions": []}
    return AT.catalog(str(src))


def find_profession(key: str, lang: str = "zh") -> dict:
    """按 slug 或名字找一职业（找不到 → 空 dict，不猜）。"""
    found = professions(lang)
    k = str(key or "").strip().lower()
    for row in found.get("professions") or []:
        if row.get("slug", "").lower() == k or str(row.get("name") or "").lower() == k:
            return row
    for row in found.get("professions") or []:
        if k and (k in str(row.get("slug") or "").lower() or k in str(row.get("name") or "")):
            return row
    return {}


def needs_for(row: dict) -> Need:
    """按职业行算出装备与账号需求。没立职业 → 空需求（不瞎配）。"""
    if not row or not row.get("name"):
        return Need("", "", "", (), (), {"说明": "未立职业：先 assign 再谈装备"})
    div = str(row.get("division") or "specialized")
    base = DIVISION_NEEDS.get(div, {"services": ("数据库",), "tools": ("json_tool",)})
    services, tools = list(base["services"]), list(base["tools"])
    text = "%s %s" % (row.get("name") or "", row.get("description") or "")
    kw_hit = {}
    for kw, tool in KEYWORD_TOOLS:
        if kw in text and tool not in tools:
            tools.append(tool)
            kw_hit[tool] = kw
    return Need(str(row.get("slug") or ""), str(row.get("name") or ""), div,
                tuple(services), tuple(tools),
                {"分域口径": div, "关键词补齐": kw_hit,
                 "口径来源": "本仓自定（上游职业定义无账号栏）"})


def _account_state() -> dict:
    """账号现状：先看环境变量在不在（只报已配/未配），再看登记表。"""
    out = {}
    for svc, env in SERVICE_ENV.items():
        out[svc] = "已配" if os.environ.get(env) else "未配"
    try:
        from .tools import account_registry as AR
        reg = AR.load()
        for row in reg.get("accounts") or []:
            nm = str(row.get("service") or row.get("platform") or "")
            if nm:
                out.setdefault(nm, "已登记")
    except Exception:                                              # noqa: BLE001
        pass
    return out


def _tool_state() -> dict:
    from . import tool_bay as TB
    return {n: v["state"] for n, v in TB.ToolBay().state().items()}



# ── 触手 ↔ 职业：持久化认领（一触手一职业 · UNIQUE）────────────────────────────
# V8 的落点：state/tentacle_professions.json（V8 自己的 state 仓，不新造库）。
# 五元身份里本件只管两元：tentacle_id + profession（其余三元由 agency_tentacles 的 lease 负责）。
ASSIGN_FILE = _ROOT / "state" / "tentacle_professions.json"


def _load_assign() -> dict:
    try:
        return json.loads(ASSIGN_FILE.read_text(encoding="utf-8")) if ASSIGN_FILE.is_file() else {}
    except (OSError, ValueError):
        return {}


def _save_assign(d: dict) -> None:
    ASSIGN_FILE.parent.mkdir(parents=True, exist_ok=True)
    ASSIGN_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def assign(tentacle: str, profession: str, *, force: bool = False) -> dict:
    """给某根触手立职业（**先有职业才谈装备**）。一触手一职业，重复立要 force。"""
    tid = str(tentacle or "").strip()
    if not tid:
        return {"ok": False, "why": "要给哪根触手立职业？tentacle 不能空"}
    row = find_profession(profession)
    if not row:
        _log("assign:%s" % tid, "职业不在册：%s" % profession, ok=False)
        return {"ok": False, "tentacle": tid, "why": "职业不在册里：%s" % profession,
                "怎么找": "tentacle_equip professions 看全册，或按名字模糊匹配"}
    d = _load_assign()
    if tid in d and not force:
        return {"ok": False, "tentacle": tid, "why": "这根触手已立过职业：%s（要改加 force）"
                % d[tid].get("profession")}
    d[tid] = {"tentacle": tid, "slug": row.get("slug"), "profession": row.get("name"),
              "division": row.get("division"), "source_path": row.get("source_path"),
              "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    _save_assign(d)
    _log("assign:%s" % tid, "%s·%s" % (row.get("name"), row.get("division")), ok=True)
    return {"ok": True, "tentacle": tid, "职业": row.get("name"), "分域": row.get("division"),
            "存": str(ASSIGN_FILE), "已有": len(d)}


def assigned() -> dict:
    """现读：谁立了什么职业（逐根，不报合计）。"""
    d = _load_assign()
    return {"ok": True, "根数": len(d), "逐根": d, "存": str(ASSIGN_FILE)}


def _resolve(key: str) -> dict:
    """key 可以是**触手 id**（查它立的职业）或**职业 slug/名**。查不到 → 空。"""
    d = _load_assign()
    if key in d:
        return find_profession(str(d[key].get("slug") or ""))
    return find_profession(key)

def plan(key: str) -> dict:
    """这根触手该配什么、现在缺什么（只读，不动手）。"""
    row = _resolve(key)          # 触手 id 或职业都能认
    need = needs_for(row)
    acc = _account_state()
    tools = _tool_state()
    _log("plan:%s" % key, need.profession or "未立", ok=bool(row))
    return {"ok": bool(row), "key": key, "职业": need.profession or "未立", "分域": need.division,
            "需要服务位": list(need.services), "需要装备": list(need.tools),
            "账号现状": {s: acc.get(s, "未占位") for s in need.services},
            "装备现状": {t: tools.get(t, "不在白名单") for t in need.tools},
            "账号缺口": [s for s in need.services if acc.get(s) != "已配"],
            "装备缺口": [t for t in need.tools if tools.get(t) != "已装"],
            "口径": need.reason,
            "说明": "只读：这一步不装、不写、不开户" if row else "未立职业 → 空需求，不瞎配"}


def equip(key: str, *, accounts: bool = True, tools: bool = True,
          dry_run: bool = True, grant=None) -> dict:
    """按职业把装备与账号配上（**走两道门**）。dry_run 默认真 —— 只算不动。"""
    row = _resolve(key)
    if not row:
        _log("equip:%s" % key, "未立职业", ok=False)
        return {"ok": False, "key": key, "why": "未立职业：先立职业再谈装备", "动作": []}
    need = needs_for(row)
    acts = []
    if tools:
        from . import tool_bay as TB
        tb = TB.ToolBay()
        for name in need.tools:
            if dry_run:
                st = tb.state().get(name, {}).get("state", "不在白名单")
                acts.append({"部件": "装备", "件": name, "干": "只算", "现状": st})
            else:
                r = tb.install(name, grant=grant)
                acts.append({"部件": "装备", "件": name, "干": "装",
                             "结果": ("已装" if r.get("ok") else (
                                 ("需授权:" + str(r["needs_grant"])) if r.get("needs_grant") else (
                                     "需主人装" if r.get("needs_owner_manual") else r.get("why")))),
                             "evidence": r.get("evidence")})
    if accounts:
        acc = _account_state()
        for svc in need.services:
            env = SERVICE_ENV.get(svc, "")
            if acc.get(svc) == "已配":
                acts.append({"部件": "账号", "位": svc, "干": "查", "结果": "已配"})
            else:
                acts.append({"部件": "账号", "位": svc, "干": "查", "结果": "未配",
                             "怎么给": "设环境变量 %s（**凭据不进本仓、不入日志**）" % env})
    ok = bool(acts) and all(a.get("结果") in ("已装", "已配", "只算") for a in acts)
    _log("equip:%s" % key, "%s 动作%d dry=%s" % (need.profession, len(acts), dry_run), ok=bool(ok))
    return {"ok": bool(ok), "key": key, "职业": need.profession, "分域": need.division,
            "dry_run": bool(dry_run), "动作": acts,
            "总账": {"装备": len(need.tools), "服务位": len(need.services)},
            "说明": "dry_run 只算不动" if dry_run else "真配（装备走白名单+令牌；账号只认 env，不编）"}


def report(*, n: int = 50) -> dict:
    """全册体检：按分域统计「需要什么装备」——不动手。"""
    found = professions()
    rows = (found.get("professions") or [])[:max(1, int(n))]
    by_div, tool_need = {}, {}
    for row in rows:
        need = needs_for(row)
        by_div[need.division] = by_div.get(need.division, 0) + 1
        for t in need.tools:
            tool_need[t] = tool_need.get(t, 0) + 1
    return {"ok": bool(found.get("ok")), "职业总数": found.get("count"),
            "已体检": len(rows), "分域分布": by_div,
            "装备需求热度": dict(sorted(tool_need.items(), key=lambda kv: -kv[1])),
            "口径": {k: list(v["tools"]) for k, v in DIVISION_NEEDS.items()}}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        found = professions()
        from . import tool_bay as TB
        return {"ok": bool(found.get("ok")), "op": "status",
                "职业源": str(LIB_ZH), "职业总数": found.get("count"),
                "已看": found.get("examined"), "截断": found.get("truncated"),
                "分域数": len({r.get("division") for r in (found.get("professions") or [])}),
                "装备白名单": sorted(TB.CATALOG)}
    if op == "professions":
        return dict({"op": "professions"}, **professions(str(kw.get("lang") or "zh")))
    if op == "plan":
        return dict({"op": "plan"}, **plan(str(kw.get("key") or kw.get("slug") or "")))
    if op == "equip":
        return dict({"op": "equip"}, **equip(
            str(kw.get("key") or kw.get("slug") or ""),
            accounts=bool(kw.get("accounts", True)), tools=bool(kw.get("tools", True)),
            dry_run=bool(kw.get("dry_run", True)), grant=kw.get("grant")))
    if op == "report":
        return dict({"op": "report"}, **report(n=int(kw.get("n") or 50)))
    if op == "assign":
        return dict({"op": "assign"}, **assign(str(kw.get("tentacle") or ""),
                                                str(kw.get("profession") or kw.get("key") or ""),
                                                force=bool(kw.get("force"))))
    if op in ("assigned", "roster"):
        return dict({"op": "assigned"}, **assigned())
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["status", "professions", "plan", "equip", "report", "assign", "assigned"]}
