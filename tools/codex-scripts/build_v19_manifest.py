# -*- coding: utf-8 -*-
"""生成 V19 数据层：+ social 段（AI朋友圈实况 + 用户社交 + 门状态）。
数字全部来自本机 eigenflux CLI 与源码，不编。
"""
import ast
import json
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

man = json.loads((S / "v18_manifest.json").read_text(encoding="utf-8"))
live = json.loads((S / "social_live.json").read_text(encoding="utf-8"))


def lines(rel):
    p = BASE / rel
    return p.read_text(encoding="utf-8", errors="ignore").count("\n") + 1 if p.is_file() else 0


def doc(rel):
    try:
        return (ast.get_docstring(ast.parse((BASE / rel).read_text(encoding="utf-8", errors="ignore"))) or "").strip().split("\n")[0][:150]
    except Exception:  # noqa: BLE001
        return ""


# ── 朋友圈：12 条真实动态 ──
items = []
for it in (live.get("feed") or {}).get("items") or []:
    items.append({
        "who": it.get("display_name"),
        "agent_id": it.get("author_agent_id"),
        "relation": it.get("author_relation"),
        "type": it.get("broadcast_type"),
        "geo": it.get("geo"),
        "want_reply": it.get("expected_response"),
        "domains": (it.get("domains") or [])[:5],
        "summary": (it.get("summary") or it.get("raw_content") or "")[:220],
        "item_id": it.get("item_id"),
        "at": it.get("created_at"),
    })

prof = (live.get("profile") or {}).get("profile") or {}
inf = (live.get("profile") or {}).get("influence") or {}
st = live.get("stats") or {}
ver = live.get("version") or {}
fr = live.get("relation_friend") or {}
pd_ = live.get("relation_pending") or {}

# ── 用户社交：平台表（纯数据，读源码）──
plat_src = (BASE / "holo_pet/social_platforms.py").read_text(encoding="utf-8", errors="ignore")
plats, flags = [], {}
tree = ast.parse(plat_src)
for n in tree.body:
    if isinstance(n, ast.Assign):
        for tg in n.targets:
            if isinstance(tg, ast.Name):
                try:
                    v = ast.literal_eval(n.value)
                except Exception:  # noqa: BLE001
                    continue
                if tg.id == "PLATFORM_SPECS" and isinstance(v, (list, tuple)):
                    for x in v:
                        if isinstance(x, dict):
                            plats.append({"id": x.get("id"), "label": x.get("label"),
                                          "official_api": x.get("official_api"),
                                          "delivery": str(x.get("delivery") or "")[:90]})
                elif tg.id.endswith("_FLAGS") and isinstance(v, (list, tuple, set)):
                    flags[tg.id] = list(v)

# ── 门状态（现场问 policy）──
sys.path.insert(0, str(BASE))
from gbt_allinone.security import policy  # noqa: E402
gate = {}
for kind, ops in (("auto_publish", ["status", "plan", "compose", "publish", "track", "settle", "withdraw"]),
                  ("eigenflux", ["feed", "profile", "publish", "msg_send", "relation_add"]),
                  ("collab_gateway", ["status", "open_session", "start_server", "request_peer"])):
    gate[kind] = {op: list(policy.evaluate(kind, {"op": op}).scopes) for op in ops}

man["social"] = {
    "scanned_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
    "eigenflux": {
        "zh": "AI朋友圈（EigenFlux）",
        "cli": {"path": r"C:\Users\ADMIN\AppData\Local\local\bin\eigenflux.exe",
                "version": ver.get("cli_version"), "commit": ver.get("commit"),
                "go": ver.get("go_version"), "client_id": ver.get("client_id"),
                "home": ver.get("home")},
        "identity": {"agent_id": prof.get("agent_id"), "name": prof.get("agent_name"),
                     "name_en": prof.get("agent_name_en"), "bio": (prof.get("bio") or "")[:300],
                     "created_at": prof.get("created_at")},
        "influence": inf,
        "net": {"agent_count": st.get("agent_count"),
                "countries": len(st.get("agent_countries") or [])},
        "feed": items,
        "friends": {"requests": len(fr.get("requests") or []),
                    "pending": len(pd_.get("requests") or []),
                    "next_cursor": fr.get("next_cursor")},
        "modules": [
            {"f": "potato_pet/eigenflux_client.py", "lines": lines("potato_pet/eigenflux_client.py"),
             "doc": doc("potato_pet/eigenflux_client.py")},
            {"f": "potato_pet/eigenflux_bridge.py", "lines": lines("potato_pet/eigenflux_bridge.py"),
             "doc": doc("potato_pet/eigenflux_bridge.py")},
            {"f": "potato_pet/eigenflux_drawer.py", "lines": lines("potato_pet/eigenflux_drawer.py"),
             "doc": doc("potato_pet/eigenflux_drawer.py")},
            {"f": "gbt_allinone/collab_gateway.py", "lines": lines("gbt_allinone/collab_gateway.py"),
             "doc": doc("gbt_allinone/collab_gateway.py")},
        ],
        "cli_ops": ["auth login", "feed poll", "publish", "msg send", "relation list",
                    "profile show", "stats", "dashboard", "stream", "server list",
                    "skills", "doctor", "settings", "migrate"],
        "wired": False,
        "why": "CLI 装了、登录了、网络是活的（能拉到好友真实动态），但三件套实现整个在 "
               "potato_pet/（项目之外），gbt_allinone 里零登记零路由 ⇒ run_task 够不着。",
    },
    "publish": {
        "zh": "用户社交（社交发布）",
        "cap": "auto_publish", "domain": "social",
        "self_state": "readonly · not_implemented · requires_external_key",
        "self_reason": "平台名单主人未给、凭据也不在盘上 ⇒ 本骨架只给形状与闸，**不假装能发**",
        "self_next": "主人给平台名单 + 凭据（走密钥池）+ 授权出网后，逐个接官方入口",
        "platforms": plats, "flags": flags,
        "platform_src": "holo_pet/social_platforms.py",
        "platform_src_lines": lines("holo_pet/social_platforms.py"),
        "wired": True,
        "why": "它已在注册表、已接统一入口、能跑 —— 但它自己如实报「发不出去」，"
               "因为缺的是**平台名单 + 凭据 + 授权**，不是代码。",
    },
    "gate": gate,
    "gate_note": "policy.evaluate 对这两条线**几乎完全空白**：publish / settle / withdraw / "
                 "start_server / request_peer 全是 scopes=() risk=low。"
                 "接分发前必须先有门，否则就是免门洞。",
}

out = S / "v19_manifest.json"
out.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", out.name, "%.1f KB" % (out.stat().st_size / 1024))
e = man["social"]["eigenflux"]
print("朋友圈: %s (%s) · agent_id=%s" % (e["identity"]["name"], e["identity"]["name_en"], e["identity"]["agent_id"]))
print("  影响力: 广播 %s · 消费 %s · 打分 %s/%s" % (e["influence"].get("total_items"),
      e["influence"].get("total_consumed"), e["influence"].get("scored_1"), e["influence"].get("scored_2")))
print("  全网 agent: %s · 国家/地区 %s" % (e["net"]["agent_count"], e["net"]["countries"]))
print("  动态 %d 条 · 好友请求 %d · 待处理 %d" % (len(e["feed"]), e["friends"]["requests"], e["friends"]["pending"]))
print("  实现: %d 文件 / %s 行 · wired=%s" % (len(e["modules"]), f"{sum(m['lines'] for m in e['modules']):,}", e["wired"]))
p = man["social"]["publish"]
print("用户社交: %s · %d 个平台（%d 有官方 API）· wired=%s" % (
    p["cap"], len(p["platforms"]), sum(1 for x in p["platforms"] if x["official_api"]), p["wired"]))
print("门:", json.dumps(gate, ensure_ascii=False)[:260])
