# -*- coding: utf-8 -*-
"""从真实数据里算出关系场可视化所需的坐标与分组。只读。
画法（全部由数据决定，不手摆）：
  · 中心 = 我方 agent；一圈 = 好友，按好友关系建立时间顺时针排（越新越靠右）
  · 节点半径 ∝ 该好友在我 feed 里出现的帖子数（真实活跃度）
  · 节点色 = 从 bio 的 Domains 里抽出的主域，映射到设计系统的 4 个语义色
  · 连线粗细 ∝ 该好友是否在 feed 里（有内容往来）
"""
import json
import math
import re
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

g = json.loads((S / "social_graph.json").read_text(encoding="utf-8"))
man = json.loads((S / "v19_manifest.json").read_text(encoding="utf-8"))

fr = g.get("friends") or {}
friends = fr.get("friends") or fr.get("items") or fr.get("list") or []
feed = (g.get("feed") or {}).get("items") or []
prof = (g.get("profile") or {}).get("profile") or {}
infl = (g.get("profile") or {}).get("influence") or {}
st = g.get("stats") or {}
inc = (g.get("incoming") or {}).get("requests") or []
outg = (g.get("outgoing") or {}).get("requests") or []

DOM_RE = re.compile(r"Domains?\s*[:：]\s*([^\n|]+)", re.I)
SPLIT_RE = re.compile(r"[,，、;；/|]+")

# 兜底关键词表：很多好友的 bio 不写 "Domains:"，只有一句话自述。
# 用关键词命中来归类，命中不到就如实标 other（不硬塞）。
KEYWORDS = [
    ("ai-agents", ("agent", "智能体", "multi-agent", "orchestration", "编排")),
    ("automation", ("automation", "自动化", "workflow", "工作流")),
    ("software-engineering", ("software", "工程", "developer", "开发", "代码", "coding", "programming")),
    ("reliability", ("reliability", "可靠性", "verifiable", "可靠", "handoff")),
    ("supply-chain", ("supply-chain", "供应链", "procurement", "采购")),
    ("content", ("content", "内容", "media", "媒体", "创作")),
    ("ecommerce", ("电商", "ecommerce", "小程序", "mini-program", "shop")),
    ("feishu", ("飞书", "lark", "feishu")),
    ("security", ("security", "安全", "permission", "权限", "legal", "合规")),
    ("data", ("data", "数据", "analytics", "分析")),
    ("industry", ("行业", "industry", "应用落地", "case")),
    ("hardware", ("obd", "tbox", "dashcam", "车", "vehicle", "hardware", "iot")),
    ("gaming", ("game", "游戏", "gaming", "acgn", "二次元")),
]


def domains_of(text):
    t = text or ""
    m = DOM_RE.search(t)
    if m:
        got = [x.strip().lower() for x in SPLIT_RE.split(m.group(1)) if 2 < len(x.strip()) < 40][:6]
        if got:
            return got
    low = t.lower()
    hit = [name for name, kws in KEYWORDS if any(k in low for k in kws)]
    return hit[:4]


# feed 里各作者出现次数
post_count = {}
for it in feed:
    post_count[it.get("display_name") or it.get("author_agent_id")] = \
        post_count.get(it.get("display_name") or it.get("author_agent_id"), 0) + 1

# 主题色（沿用设计系统的语义色，不新造色）
PALETTE = ["#2ad4f0", "#6ef2ff", "#3ddc97", "#f5b544", "#ff7a7a"]


def hue_for(doms):
    key = (doms[0] if doms else "other")
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) % 997
    return PALETTE[h % len(PALETTE)]


nodes = []
friends_sorted = sorted(friends, key=lambda x: x.get("friend_since") or 0)
n = max(1, len(friends_sorted))
for i, f in enumerate(friends_sorted):
    doms = domains_of(f.get("bio") or "")
    name = f.get("display_name") or f.get("agent_name")
    ang = -math.pi / 2 + 2 * math.pi * i / n
    posts = post_count.get(name, 0)
    nodes.append({
        "id": f.get("agent_id"), "name": name, "en": f.get("agent_name_en"),
        "short": f.get("short_id"), "official": bool(f.get("is_official")),
        "since": f.get("friend_since"), "bio": (f.get("bio") or "")[:150],
        "domains": doms, "color": hue_for(doms),
        "posts": posts,
        "r": round(6 + min(posts, 5) * 1.7 + (1.5 if f.get("is_official") else 0), 1),
        "angle": round(ang, 4),
        "recent": ((f.get("recent") or {}).get("text") or "")[:90],
    })

# 域频次
domc = {}
for nd in nodes:
    for d in nd["domains"]:
        domc[d] = domc.get(d, 0) + 1

man["social"]["graph"] = {
    "center": {"name": prof.get("agent_name"), "en": prof.get("agent_name_en"),
               "id": prof.get("agent_id"), "bio": (prof.get("bio") or "")[:260],
               "influence": infl},
    "nodes": nodes,
    "n_friends": len(nodes),
    "n_official": sum(1 for x in nodes if x["official"]),
    "n_active": sum(1 for x in nodes if x["posts"]),
    "domains": dict(sorted(domc.items(), key=lambda kv: -kv[1])),
    "requests": {"incoming": len(inc), "outgoing": len(outg)},
    "net": {"agents": st.get("agent_count"), "countries": len(st.get("agent_countries") or [])},
    "feed_n": len(feed),
    "palette": PALETTE,
}
(S / "v20_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")

print("好友 %d 位（官方 %d · 有动态往来 %d）" % (len(nodes), man["social"]["graph"]["n_official"],
                                     man["social"]["graph"]["n_active"]))
print("\n节点（按建交时间）：")
for x in nodes:
    print("  %-22s r=%-4s %-9s 帖%-2d  %s" % (x["name"][:20], x["r"], x["color"], x["posts"],
                                             ",".join(x["domains"][:3]) or "（bio 未写域）"))
print("\n域频次:", dict(list(man["social"]["graph"]["domains"].items())[:10]))
print("请求: 收到 %d · 发出 %d" % (len(inc), len(outg)))
print("写出: v20_manifest.json")
