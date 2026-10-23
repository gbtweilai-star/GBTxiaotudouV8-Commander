# gbt-capability: eigenflux
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""AI 朋友圈（EigenFlux）· **只读能力位**（主人令 2026-10-08）。

主人原话（本线目标）：
    「设计好全部能力接入，数字人就可以自己找朋友，以及查看朋友圈有没有好玩的和有用的消息。」

## 这件的定位（一句话）
把 `~/.eigenflux/` 的**本地数据面**（CLI 轮询落盘的 feed / 私信 / 联系人 / 自己的档案）
接成一个**统一门可见的能力位**，让数字人能**只读地**：看朋友圈（feed）· 列好友（friends）·
推可加好友候选（candidates）· 出「今日精选」（digest）。

## 口径（三条，不许破）
1. **只读本地单一真源、零写面、零出网**：op 一律**现读**盘上 `~/.eigenflux/servers/eigenflux/**`
   （不复制第二份；**不调用 eigenflux CLI / 不发任何网络请求** —— 只读磁盘缓存，故**
   零作用域、无需任何 policy 条目**）。
2. **读不到就如实报 `未探测` + 理由**，**不许占位数字、不许折绿**（fail-closed）。
3. **零写动作**：本能力位**不**加好友、**不**发消息、**不**关注、**不**广播。所有
   **对外写动作（加好友 / 发私信 / 关注 / 广播）必须走既有门**（external/network 写作用域
   或主人一次性票），本件**绝不绕门**、也**绝不代持凭据**。

## 真源（现读 · 只读）
  · `~/.eigenflux/config.json`                       运行态（服务器/轮询/开关）
  · `~/.eigenflux/servers/eigenflux/profile.json`    本 Agent 档案（= 主人兴趣真源）
  · `~/.eigenflux/servers/eigenflux/contacts.json`   好友列表
  · `~/.eigenflux/servers/eigenflux/data/broadcasts/<YYYYMMDD>/feeds-*.json`  朋友圈消息流
  · `~/.eigenflux/servers/eigenflux/data/messages/<YYYYMMDD>/*.json`          私信
  · `~/.eigenflux/servers/eigenflux/credentials.json`（**只报在场与过期时间，绝不含明文**）

op：`status` / `feed` / `friends` / `candidates` / `digest` / `metadata` / `where`

## 与「对外写」的关系（边界，写死）
本文件的 op **全部是发现（discovery）**；写动作（add_friend / send / follow / publish）
**不在本件**，见 `docs/数字人社交环-eigenflux只读接入.md` 的「官方面 / 等门面」表。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone

_CAP = "eigenflux"


# ══════════════════════════════════════════════════════════════════════════
# 真源定位（可注入 home，便于负对照喂空盘）
# ══════════════════════════════════════════════════════════════════════════
def _home(home=None) -> Path:
    """EigenFlux 数据面根。优先入参，其次环境变量 `EIGENFLUX_HOME`，其次 `~/.eigenflux`。"""
    if home:
        return Path(home)
    env = os.environ.get("EIGENFLUX_HOME")
    if env:
        return Path(env)
    return Path.home() / ".eigenflux"


def _server_dir(home=None) -> Path:
    return _home(home) / "servers" / "eigenflux"


def _read_json(p: Path):
    """现读单一真源。读不到返回 (None, 原因) —— **不许折绿**。"""
    if not p.is_file():
        return None, "不在盘：%s" % p
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:                                    # noqa: BLE001
        return None, "在盘但读不动（%s）：%s" % (type(e).__name__, p)


def _feed_files(home=None) -> list:
    base = _server_dir(home) / "data" / "broadcasts"
    if not base.is_dir():
        return []
    return sorted(base.glob("*/*.json"))


def _msg_files(home=None) -> list:
    base = _server_dir(home) / "data" / "messages"
    if not base.is_dir():
        return []
    return sorted(base.glob("*/*.json"))


def _day_of(p: Path) -> str:
    """从 `.../broadcasts/<YYYYMMDD>/feeds-*.json` 里取日期目录名。"""
    return p.parent.name


# ══════════════════════════════════════════════════════════════════════════
# feed：朋友圈消息流（只读现读）
# ══════════════════════════════════════════════════════════════════════════
def _load_feed_items(home=None, day=None) -> tuple:
    """把盘上 feed 现读成**去重的广播条目**（按 item_id 去重，保留最新出现）。

    返回 (items, files, why)。每 item 保留**来源字段**（`_file` / `_day`），
    供 digest 逐条带出处。**读不到 ⇒ 空 + why**（不占位）。
    """
    files = _feed_files(home)
    if day:
        files = [f for f in files if _day_of(f) == str(day)]
    if not files:
        return [], [], "无 feed 文件：%s" % (_server_dir(home) / "data" / "broadcasts")
    seen = {}
    bad = []
    for f in files:
        d, why = _read_json(f)
        if d is None:
            bad.append(why)
            continue
        rows = d.get("items") if isinstance(d, dict) else None
        if not isinstance(rows, list):
            # 兼容旧 discovery 结构：取 discovery.items（无 author，但仍有 item_id/preview）
            rows = ((d.get("discovery") or {}).get("items")
                    if isinstance(d, dict) else None) or []
        for it in rows:
            if not isinstance(it, dict):
                continue
            iid = it.get("item_id")
            if not iid:
                continue
            if iid in seen:
                continue
            it = dict(it)
            it["_file"] = str(f)
            it["_day"] = _day_of(f)
            seen[iid] = it
    return list(seen.values()), files, ("；".join(bad[:3]) if bad else None)


def feed(limit: int = 30, day: str = None, home: str = None, **_kw) -> dict:
    """朋友圈消息流（只读）。按 created_at 倒序，逐条带来源字段。"""
    items, files, why = _load_feed_items(home=home, day=day)
    if not files:
        return {"ok": False, "op": "feed", "kind": _CAP, "unprobed": True,
                "why": why, "_口径": "读不到=未探测（不折绿）"}
    if not items:
        return {"ok": False, "op": "feed", "kind": _CAP, "unprobed": True,
                "why": why or "feed 文件在盘但 0 条目 ⇒ 未探测（不折绿）",
                "files": len(files)}
    items.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
    try:
        limit = max(1, int(limit))
    except Exception:                                         # noqa: BLE001
        limit = 30
    rows = [_slim_feed(x) for x in items[:limit]]
    return {"ok": True, "op": "feed", "kind": _CAP, "total": len(items),
            "returned": len(rows), "files": len(files),
            "days": sorted({x["_day"] for x in items}),
            "items": rows, "source": "~/.eigenflux/servers/eigenflux/data/broadcasts/**",
            "_口径": "现读本地缓存；零出网；逐条带 item_id/display_name/keywords 等来源字段"}


def _slim_feed(it: dict) -> dict:
    """把一条广播裁剪成可上屏 + 可复核的字段（**保留来源**）。"""
    return {
        "item_id": it.get("item_id"),
        "author_agent_id": it.get("author_agent_id"),
        "display_name": it.get("display_name"),
        "domains": it.get("domains") or [],
        "keywords": it.get("keywords") or [],
        "summary": it.get("summary"),
        "expected_response": it.get("expected_response"),
        "broadcast_type": it.get("broadcast_type"),
        "created_at": it.get("created_at"),
        "url": it.get("url"),
        "_day": it.get("_day"),
        "_file": it.get("_file"),
    }


# ══════════════════════════════════════════════════════════════════════════
# friends：联系人（只读现读）
# ══════════════════════════════════════════════════════════════════════════
def friends(home: str = None, **_kw) -> dict:
    """好友联系人（现读 contacts.json）。"""
    p = _server_dir(home) / "contacts.json"
    rows, why = _read_json(p)
    if rows is None:
        return {"ok": False, "op": "friends", "kind": _CAP, "unprobed": True, "why": why}
    if not isinstance(rows, list):
        return {"ok": False, "op": "friends", "kind": _CAP, "unprobed": True,
                "why": "contacts.json 形状不是列表 ⇒ 未探测（不折绿）"}
    out = []
    for c in rows:
        if not isinstance(c, dict):
            continue
        out.append({"agent_id": c.get("agent_id"), "agent_name": c.get("agent_name"),
                    "remark": c.get("remark") or "", "friend_since": c.get("friend_since"),
                    "has_remark": bool((c.get("remark") or "").strip())})
    out.sort(key=lambda x: int(x.get("friend_since") or 0), reverse=True)
    return {"ok": True, "op": "friends", "kind": _CAP, "count": len(out),
            "weak_link": [x for x in out if not x["has_remark"]],
            "items": out, "source": "~/.eigenflux/servers/eigenflux/contacts.json",
            "_口径": "现读 contacts.json；weak_link=备注为空的弱关系（资料待补）"}


def _friend_ids(home=None) -> set:
    p = _server_dir(home) / "contacts.json"
    rows, _why = _read_json(p)
    if not isinstance(rows, list):
        return set()
    return {str(c.get("agent_id")) for c in rows if isinstance(c, dict) and c.get("agent_id")}


def _my_id(home=None) -> str:
    prof, _why = _read_json(_server_dir(home) / "profile.json")
    if isinstance(prof, dict) and prof.get("agent_id"):
        return str(prof["agent_id"])
    cred, _why2 = _read_json(_server_dir(home) / "credentials.json")
    if isinstance(cred, dict) and cred.get("agent_id"):
        return str(cred["agent_id"])
    return ""


# ══════════════════════════════════════════════════════════════════════════
# candidates：可加好友候选（**从 feed/contacts/私信 结构性推导**，每条带依据）
# ══════════════════════════════════════════════════════════════════════════
def candidates(limit: int = 20, min_broadcasts: int = 1, home: str = None, **_kw) -> dict:
    """可加好友候选：**纯结构性推导**（不是自由编名单），每条附**推导依据**。

    三条结构信号（各自独立可核）：
      A. **发过广播但你还没加**：feed 里 `author_agent_id` ∉ 好友 且 ≠ 自己。
      B. **有来无往**：私信里 `sender_id` ∉ 好友 且 ≠ 自己（对方主动找过你）。
      C. **弱关系好友**：已在好友里但 `remark` 为空（关系待标注，非"新候选"）——
         单列，**不算新候选**（避免把老好友当新朋友推）。
    """
    fids = _friend_ids(home)
    me = _my_id(home)
    items, files, why = _load_feed_items(home=home)
    if not files:
        return {"ok": False, "op": "candidates", "kind": _CAP, "unprobed": True,
                "why": why or "无 feed/contacts 数据面 ⇒ 未探测（不折绿）"}

    # 信号 A：feed 广播作者
    a_meta = {}
    for it in items:
        a = it.get("author_agent_id")
        if not a or str(a) in fids or str(a) == me:
            continue
        rec = a_meta.setdefault(str(a), {"agent_id": str(a), "display_name": it.get("display_name"),
                                         "domains": set(), "keywords": set(),
                                         "broadcasts": 0, "last_at": 0})
        rec["broadcasts"] += 1
        rec["domains"] |= set(it.get("domains") or [])
        rec["keywords"] |= set(it.get("keywords") or [])
        rec["last_at"] = max(rec["last_at"], int(it.get("created_at") or 0))

    # 信号 B：私信来信人（非好友）
    b_meta = {}
    for f in _msg_files(home):
        rows, _w = _read_json(f)
        for r in (rows if isinstance(rows, list) else []):
            if not isinstance(r, dict):
                continue
            sid = r.get("sender_id")
            if not sid or str(sid) in fids or str(sid) == me:
                continue
            rec = b_meta.setdefault(str(sid), {"agent_id": str(sid), "display_name": r.get("sender_name"),
                                               "msgs": 0, "files": set(), "last_at": 0})
            rec["msgs"] += 1
            rec["files"].add(str(f))
            rec["last_at"] = max(rec["last_at"], int(r.get("created_at") or 0))

    out = []
    for aid, rec in a_meta.items():
        e = {"agent_id": aid, "display_name": rec["display_name"],
             "signals": ["发过广播但你还没加好友"],
             "broadcasts": rec["broadcasts"], "domains": sorted(rec["domains"])[:8],
             "keywords": sorted(rec["keywords"])[:10],
             "basis": "feed 里 author_agent_id=%s 的广播 %d 条；不在 contacts.json；≠ 自己"
                      % (aid, rec["broadcasts"])}
        if aid in b_meta:
            e["signals"].append("有来无往（对方私信过你）")
            e["msgs_from_them"] = b_meta[aid]["msgs"]
            e["basis"] += "；并且私信 sender_id=%s 共 %d 条（非好友）" % (aid, b_meta[aid]["msgs"])
        e["score"] = rec["broadcasts"] + 3 * (1 if aid in b_meta else 0)
        e["last_at"] = rec["last_at"]
        out.append(e)
    for aid, rec in b_meta.items():
        if aid in a_meta:
            continue
        out.append({"agent_id": aid, "display_name": rec["display_name"],
                    "signals": ["有来无往（对方私信过你）"],
                    "broadcasts": 0, "domains": [], "keywords": [],
                    "msgs_from_them": rec["msgs"],
                    "score": 3, "last_at": rec["last_at"],
                    "basis": "私信 sender_id=%s 共 %d 条（非好友、≠ 自己）；不在 contacts.json"
                             % (aid, rec["msgs"])})

    out.sort(key=lambda x: (x["score"], x["last_at"]), reverse=True)
    try:
        limit = max(1, int(limit))
    except Exception:                                         # noqa: BLE001
        limit = 20
    out = [x for x in out if x["broadcasts"] >= max(1, int(min_broadcasts)) or x["signals"] != ["发过广播但你还没加好友"]]
    weak = [f for f in (friends(home=home).get("items") or []) if not f.get("has_remark")]
    return {"ok": True, "op": "candidates", "kind": _CAP,
            "count": len(out), "returned": len(out[:limit]),
            "items": out[:limit],
            "weak_link_friends": weak,
            "source": "feed(author_agent_id) + messages(sender_id) + contacts.json（结构性推导）",
            "_口径": "候选人一律由结构信号推导并附 basis；信号 C（弱关系好友）单列不算新候选；无数据不编"}


# ══════════════════════════════════════════════════════════════════════════
# digest：社交环 · 今日精选（只读）· 打分规则写死、可复核、逐条带来源
# ══════════════════════════════════════════════════════════════════════════
# 主人兴趣真源 = profile.json 的 bio（原话：Domains: AI agents, automation, cybersecurity,
# multi-agent orchestration；Seeking: agent framework peers / 东南亚 AI 工作室）。
INTEREST_CLUSTERS = {
    "ai_agents":  ["agent", "agents", "智能体", "multi-agent", "多智能体", "ai-agent", "ai agent"],
    "automation": ["automation", "自动化", "browser", "浏览器", "workflow", "rpa"],
    "security":   ["security", "安全", "cybersecurity", "零信任", "zero trust", "pentest", "渗透", "redteam"],
    "llm":        ["llm", "大模型", "orchestration", "编排", "gemini", "gpt", "model", "推理", "inference"],
    "collab":     ["对拍", "合作", "collab", "cooperat", "peer", "分享", "share", "联动", "共建"],
    "creation":   ["video", "视频", "媒体", "media", "创作", "content", "艺术", "art", "design"],
}
FUN_MARKERS = ["?", "？", "欢迎", "一起", "求", "探讨", "有趣", "好奇", "好玩", "推荐",
               "分享", "fun", "curious", "interesting", "share", "invite", "合作"]
FUN_DOMAINS = ["media_production", "education", "education-tech", "art", "design", "game",
               "艺术", "教育", "media"]
# 权重（可复核；无数据的维度**不计分**，不是给 0 分占位）
SCORE_WEIGHTS = {"interest": 3.0, "fun": 2.0, "fresh": 2.0, "respondable": 1.0}


def profile_keywords(home=None) -> dict:
    """主人兴趣真源（现读 profile.json）。读不到 ⇒ 回落到内置常量并标注。"""
    prof, why = _read_json(_server_dir(home) / "profile.json")
    bio = (prof or {}).get("bio") if isinstance(prof, dict) else None
    if not bio:
        return {"source": "内置常量（profile.json 读不到：%s）" % why, "bio": "", "hit_terms": []}
    return {"source": "~/.eigenflux/servers/eigenflux/profile.json::bio", "bio": bio,
            "agent_name": prof.get("agent_name")}


def _text_of(it: dict) -> str:
    parts = [str(it.get("summary") or ""), str(it.get("display_name") or ""),
             " ".join(it.get("keywords") or []), " ".join(it.get("domains") or []),
             str(it.get("raw_content") or "")]
    return " ".join(parts).lower()


def score_item(it: dict, *, weights: dict = None, day_max: int = None) -> dict:
    """给一条广播打分（**纯函数**，可被负对照替换）。

    返回 {item_id, score, dims:{interest,fun,fresh,respondable}, evidence:{...}, _src:{...}}
    每条 dim 都带**证据**（命中的词/字段），保证"可复核、可回放"。
    """
    w = dict(SCORE_WEIGHTS)
    if weights:
        w.update(weights)
    text = _text_of(it)
    dims, ev = {}, {}

    # interest：命中主人兴趣簇的数量（簇级去重，证据=命中的词）
    hit_terms, hit_clusters = [], []
    for cluster, words in INTEREST_CLUSTERS.items():
        h = sorted({x for x in words if x in text})
        if h:
            hit_clusters.append(cluster)
            hit_terms.extend(h)
    dims["interest"] = len(hit_clusters)
    ev["interest"] = {"clusters": hit_clusters, "terms": sorted(set(hit_terms))}

    # fun：趣味/可分享标记数（证据=命中的标记）
    fh = sorted({m for m in FUN_MARKERS if m in text})
    dhit = [d for d in (it.get("domains") or []) if str(d).lower() in FUN_DOMAINS]
    dims["fun"] = len(fh) + len(dhit)
    ev["fun"] = {"markers": fh, "domains": dhit}

    # fresh：按当日 created_at 的**秩**给分（0..1）——只在同一天内比较，避免"旧的日期整批压死"
    c = int(it.get("created_at") or 0)
    if day_max and c:
        dims["fresh"] = round(min(1.0, c / float(day_max)), 4)
    else:
        dims["fresh"] = 0.0
    ev["fresh"] = {"created_at": c, "day_max": day_max}

    # respondable：广播自己声明期待回应的（reply/both）或作者是好友 ⇒ 可互动
    er = str(it.get("expected_response") or "").lower()
    dims["respondable"] = 1 if er in ("reply", "both", "answer") or it.get("author_relation") == "friend" else 0
    ev["respondable"] = {"expected_response": it.get("expected_response"),
                         "author_relation": it.get("author_relation")}

    score = round(sum(w[k] * dims[k] for k in dims if k in w), 4)
    return {"item_id": it.get("item_id"), "score": score, "dims": dims, "evidence": ev,
            "display_name": it.get("display_name"), "author_agent_id": it.get("author_agent_id"),
            "summary": it.get("summary"), "keywords": (it.get("keywords") or [])[:10],
            "_src": {"file": it.get("_file"), "day": it.get("_day"), "url": it.get("url")}}


def digest(top: int = 8, candidates_n: int = 6, day: str = None, home: str = None,
           scorer=None, **_kw) -> dict:
    """社交环 · 今日精选（只读）。

    「今日」= 盘上**最新的** broadcast 日期目录（不是机器当前日期；如实报出是哪一个）。
    打分规则见 `SCORE_WEIGHTS` / `INTEREST_CLUSTERS` / `score_item`；**无互动量数据 ⇒ 不计分、明说**。
    """
    items, files, why = _load_feed_items(home=home, day=day)
    if not files:
        return {"ok": False, "op": "digest", "kind": _CAP, "unprobed": True,
                "why": why or "无 feed 文件 ⇒ 无数据（不折绿）", "picks": []}
    if not items:
        return {"ok": False, "op": "digest", "kind": _CAP, "unprobed": True,
                "why": why or "feed 在盘但 0 条目 ⇒ 无数据（不折绿）", "picks": []}
    today = day or max(x["_day"] for x in items)
    today_items = [x for x in items if x["_day"] == today]
    if not today_items:
        return {"ok": False, "op": "digest", "kind": _CAP, "unprobed": True,
                "why": "日期 %s 无条目 ⇒ 无数据（不折绿）" % today, "picks": []}
    day_max = max((int(x.get("created_at") or 0) for x in today_items), default=0)
    sc = scorer or score_item
    scored = []
    for x in today_items:
        s = sc(x, day_max=day_max)
        if s:
            scored.append(s)
    scored.sort(key=lambda r: (r.get("score") or 0), reverse=True)
    pk = profile_keywords(home=home)
    try:
        top = max(1, int(top))
    except Exception:                                         # noqa: BLE001
        top = 8
    picks = scored[:top]
    cand = candidates(limit=candidates_n, home=home)
    return {"ok": True, "op": "digest", "kind": _CAP,
            "day": today, "day_item_count": len(today_items),
            "picks": picks,
            "candidate_count": cand.get("count") if cand.get("ok") else None,
            "candidates_top": (cand.get("items") or [])[:candidates_n] if cand.get("ok") else [],
            "rules": {"weights": SCORE_WEIGHTS,
                      "interest_clusters": sorted(INTEREST_CLUSTERS),
                      "profile": pk.get("source"),
                      "note": "无互动量（点赞/回复数）真源 ⇒ 该维度不计分，不编数字"},
            "source": "~/.eigenflux/servers/eigenflux/data/broadcasts/%s/**" % today,
            "_口径": "只读本地缓存、零出网；打分逐维带 evidence；读不到=无数据（不折绿）"}


# ══════════════════════════════════════════════════════════════════════════
# status / metadata / where
# ══════════════════════════════════════════════════════════════════════════
def _freshness(home=None) -> dict:
    files = _feed_files(home)
    if not files:
        return {"feed_files": 0, "newest": None, "age_hours": None, "stale": None}
    newest = max(files, key=lambda p: p.stat().st_mtime)
    age = (datetime.now(timezone.utc).timestamp() - newest.stat().st_mtime) / 3600.0
    return {"feed_files": len(files), "newest": str(newest),
            "newest_day": _day_of(newest),
            "age_hours": round(age, 2), "stale": age > 24.0}


def status(home: str = None, **_kw) -> dict:
    """状态面：数据面在不在、多少条、新鲜度（现读）。"""
    h = _home(home)
    cfg, w1 = _read_json(h / "config.json")
    prof, w2 = _read_json(_server_dir(home) / "profile.json")
    contacts, w3 = _read_json(_server_dir(home) / "contacts.json")
    cred, w4 = _read_json(_server_dir(home) / "credentials.json")
    fr = _freshness(home)
    if cfg is None and prof is None and contacts is None:
        return {"ok": False, "op": "status", "kind": _CAP, "unprobed": True,
                "why": "数据面读不到（config/profile/contacts 全缺）⇒ 未探测（不折绿）：%s"
                       % "；".join(x for x in (w1, w2, w3) if x)}
    return {"ok": True, "op": "status", "kind": _CAP,
            "home": str(h),
            "installed": bool(cfg),
            "server": ((cfg or {}).get("default_server")),
            "runtime": ((cfg or {}).get("kv") or {}).get("runtime_name"),
            "feed_poll_interval": ((cfg or {}).get("kv") or {}).get("feed_poll_interval"),
            "authenticated": bool(cred),
            "credential_expires_at": (cred or {}).get("expires_at") if cred else None,  # **不含明文**
            "agent_name": (prof or {}).get("agent_name"),
            "friends_count": len(contacts) if isinstance(contacts, list) else None,
            "freshness": fr,
            "unprobed_sources": [x for x in (w1, w2, w3, w4) if x] or None,
            "_口径": "现读 config/profile/contacts/credentials；凭据只报在场与过期时间"}


def metadata(home: str = None, **_kw) -> dict:
    """元数据面：逐源在场/尺寸（现读；读不到如实报）。"""
    h = _home(home)
    srcs = {
        "config": h / "config.json",
        "profile": _server_dir(home) / "profile.json",
        "contacts": _server_dir(home) / "contacts.json",
        "credentials": _server_dir(home) / "credentials.json",
        "broadcasts_dir": _server_dir(home) / "data" / "broadcasts",
        "messages_dir": _server_dir(home) / "data" / "messages",
    }
    rows, n_ok = {}, 0
    for k, p in srcs.items():
        p = Path(p)
        present = p.exists()
        rows[k] = {"path": str(p), "present": present,
                   "bytes": (p.stat().st_size if p.is_file() else None),
                   "kind": "dir" if p.is_dir() else ("file" if p.is_file() else "missing")}
        n_ok += 1 if present else 0
    rows["broadcasts_dir"]["files"] = len(_feed_files(home))
    rows["messages_dir"]["files"] = len(_msg_files(home))
    return {"ok": True, "op": "metadata", "kind": _CAP,
            "sources_total": len(srcs), "sources_present": n_ok,
            "freshness": _freshness(home), "sources": rows,
            "_口径": "只读单一真源、零写面；读不到=未探测（不折绿）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('eigenflux', {'op': 'digest'})",
            "ops": ["status", "feed", "friends", "candidates", "digest", "metadata", "where"],
            "read_only": True,
            "network": "零出网（只读 ~/.eigenflux 磁盘缓存，不调 eigenflux CLI）",
            "route": "gbt_allinone/api.py::_run_benign 的 eigenflux 分支 → gbt_allinone/tools/eigenflux.py",
            "policy": "读类直连 ⇒ **无需 policy 条目**（未列出的只读 kind 走零作用域；本件零写面、零出网）",
            "write_face": "**无** —— 加好友/发私信/关注/广播**不在本件**，必须走既有门（见 docs/数字人社交环-eigenflux只读接入.md）",
            "contract": [
                {"op": "status", "returns": "数据面在场/服务器/好友数/新鲜度（凭据只报在场与过期）"},
                {"op": "feed", "returns": "朋友圈消息流（去重·倒序·逐条带 item_id/author/来源文件）"},
                {"op": "friends", "returns": "好友联系人（含 weak_link=备注为空）"},
                {"op": "candidates", "returns": "可加好友候选（结构推导 + 每条 basis）"},
                {"op": "digest", "returns": "今日精选（好玩/有用排序）+ 候选 + 打分规则"},
                {"op": "metadata", "returns": "逐源在场/尺寸/条目数"},
            ],
            "red_lines": ["只读本地单一真源、零写面、零出网", "读不到=未探测/无数据（不折绿）",
                          "对外写动作一律不在此件、必须过门", "凭据不离屏（只报在场与过期时间）"]}


_OPS = {"status": status, "feed": feed, "friends": friends, "candidates": candidates,
        "digest": digest, "metadata": metadata, "where": where}


def run(op: str = "status", **kw) -> dict:
    op = (op or "status").lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "fail_closed": True, "kind": _CAP,
                "error": "未知 op:%s（status/feed/friends/candidates/digest/metadata/where）" % op}
    return fn(**kw)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="AI 朋友圈 EigenFlux（只读能力位）")
    ap.add_argument("op", nargs="?", default="status")
    a = ap.parse_args()
    print(json.dumps(run(a.op), ensure_ascii=False, indent=1))
