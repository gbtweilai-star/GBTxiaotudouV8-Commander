# -*- coding: utf-8 -*-
# gbt-capability: process_execute, privacy_read, desktop_control  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""原生视觉闭环（vision_loop）—— **眼 → 脑 → 手 → 验**，缺一步就拒动。

主人令（2026-10-09，逐字）：
  「为什么她的视觉每次都要**跟手分开**去使用传统的**瞎子操作**……把视觉这么使用给她**钉死在上面**」
  「我看她每次执行任务就是**瞎还没脑**都要给我整吐了」

两句拆成两条硬规矩：
  · **瞎** = 不看就动手 ⇒ 门那一层已钉死（凡 desktop_control **必须同时**有 privacy_read，见
    tools/codex-scripts/vision-pinned-check.py）；本件做**运行期**的同一件事：
    **没有新鲜观测，绝不下发动作**。
  · **没脑** = 不判就动手 ⇒ 动作前必须过**决策脑**（System-One 契约，与云插件 c02 Laya 同一个插槽），
    拿不到决策就如实 BLOCKED，**不许硬猜着动**。

四步（每步都留读数）：
  ① 眼 look    —— 真去看（tentacle see），带时间戳 ⇒ 算年龄
  ② 脑 think   —— 观测喂决策脑（control_loop.fast_policy，**可换 Laya**）⇒ 类型化动作 + 置信度
  ③ 手 act     —— 走**唯一门** run_task 下发（门里再查一遍 desktop_control+privacy_read）
  ④ 验 verify  —— **动完再看一次**，与动前比对；没变化要如实说"没动成"，不许算成功

ops：look / think / act / verify / loop / status
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
AUDIT = _ROOT / "state" / "vision_loop.jsonl"
_EYE = None                                              # 连续帧流那只眼（懒加载，见 _eye()）
# 🔴 2026-10-10 收紧：1500 → **400**。
#    依据（主人令「你现在再去看看 V9 已经实现了万物皆可插，万物皆可控」对照出来的）：
#      V9 的 core/browser_plug.py 的 pilot() 原文：「动手前必须有**新鲜取景**（帧龄 ≤ 400ms）；
#      取不到新鲜帧就**拒动**（不许传统瞎子操作）」。
#      主人原话：「你截图再想再动手，别人 **98K 早就打爆你的头了**」⇒ **400ms 才是口径**。
#    我原来 1500ms = 松了 3.75 倍 —— 那不是"宽一点"，那是**默认允许用 1.5 秒前的画面动手**。
#    V8 与 V9 是同一套神经系统，口径必须同一条：**400**。
STALE_MS = 400           # 观测超过这个年龄就不许动手（"新鲜度"那一查）


def _log(rec: dict) -> None:
    try:
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _ctl():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ctl_vl", _ROOT / "tools" / "control_loop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _see() -> dict:
    """**眼**：真去看一眼（走唯一门；tentacle see 是只读口，不需要票）。"""
    try:
        import sys
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone import api
        # 🔴 载荷形状（现读 api.py:433）：tentacle 要的是 **action**（或 intent 走自动路由），
        #    不是 op。第一版给 {"op":"see"} ⇒ 被拒「缺少 action」⇒ 闭环如实停在①眼。
        r = api.run_task("tentacle", {"action": "see"})
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "why": "看不了：%s: %s" % (type(exc).__name__, exc),
                "at": time.time()}
    ok = bool(isinstance(r, dict) and (r.get("ok") or r.get("status") == "ok"))
    return {"ok": ok, "at": time.time(),
            "raw": r if not ok else (r.get("result") or r),
            "why": "" if ok else ("看不了：" + str((r or {}).get("error")
                                                 or (r or {}).get("status") or "未知"))}



# ─────────────────────────── 打通：7788 触手 + 8792 权重 ───────────────────────────
_TICK = {"at": 0.0}

_NODE_ROLE = {"Button": "button", "SplitButton": "button", "Edit": "textbox",
              "ComboBox": "combobox", "MenuItem": "menuitem", "TabItem": "tabitem",
              "Hyperlink": "link", "ListItem": "listitem", "CheckBox": "checkbox",
              "RadioButton": "radio", "TreeItem": "treeitem", "Image": "image"}


def _plug(tool: str, args: dict | None = None, timeout: float = 60.0) -> dict:
    """直连 7788 触手网关（APP 侧同一条口）：POST /call {tool, args}。"""
    import urllib.request
    body = json.dumps({"tool": tool, "args": args or {}}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:7788/call", data=body,
                                 headers={"content-type": "application/json; charset=utf-8"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as exc:                             # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
    ok = bool(isinstance(j, dict) and j.get("ok"))
    return {"ok": ok, "result": (j.get("result") if ok else None), "raw": j,
            "ms": (j.get("ms") if isinstance(j, dict) else None)}


def _nodes_from_scene(sc: dict) -> list:
    """把 scene 的三层（UIA 控件 / OCR 文字 / 视觉块）摊平成快脑要的 nodes 形状。

    坐标一律是**原生命中**（UIA 框 / OCR 框 / 视觉块），权重只负责"挑哪一个"。
    """
    nodes: list = []
    seen = set()
    for e in ((sc.get("uia") or {}).get("elements") or []):
        name = str(e.get("name") or "").strip()
        if not name or ("u:" + name) in seen:
            continue
        seen.add("u:" + name)
        x, y, w, h = int(e.get("x") or 0), int(e.get("y") or 0), int(e.get("w") or 0), int(e.get("h") or 0)
        nodes.append({"name": name, "role": _NODE_ROLE.get(str(e.get("type") or ""), "control"),
                      "source": "uia", "x": x, "y": y, "w": w, "h": h,
                      "cx": x + w // 2, "cy": y + h // 2})
    for l in ((sc.get("ocr") or {}).get("lines") or []):
        name = str(l.get("text") or "").strip()
        if not name or ("o:" + name) in seen:
            continue
        seen.add("o:" + name)
        x, y, w, h = int(l.get("x") or 0), int(l.get("y") or 0), int(l.get("w") or 0), int(l.get("h") or 0)
        nodes.append({"name": name, "role": "text", "source": "ocr",
                      "x": x, "y": y, "w": w, "h": h, "cx": x + w // 2, "cy": y + h // 2})
    for i, b in enumerate(((sc.get("visual") or {}).get("blocks") or [])):
        nodes.append({"name": "区域#%d" % i, "role": "region", "source": "block",
                      "x": b.get("x"), "y": b.get("y"), "w": b.get("w"), "h": b.get("h"),
                      "cx": b.get("cx"), "cy": b.get("cy")})
    for e in ((sc.get("shell") or {}).get("elements") or []):
        name = str(e.get("name") or "").strip()
        if not name or ("s:" + name) in seen:
            continue
        seen.add("s:" + name)
        x, y, w, h = int(e.get("x") or 0), int(e.get("y") or 0), int(e.get("w") or 0), int(e.get("h") or 0)
        nodes.append({"name": name, "role": _NODE_ROLE.get(str(e.get("type") or ""), "control"),
                      "source": "shell", "x": x, "y": y, "w": w, "h": h,
                      "cx": x + w // 2, "cy": y + h // 2})
    for i, n in enumerate(nodes):
        n["index"] = i
    return nodes


def _shortlist(goal: str, nodes: list, k: int = 12) -> list:
    """按目标把候选筛成短名单：权重模型在 5-12 个里挑得准，30 个就会糊。"""
    g = set(str(goal or ""))
    scored = []
    for n in nodes:
        name = str(n.get("name") or "")
        if not name:
            continue
        if len(name) > 24:      # 一整段正文不是控件名，别进候选
            continue
        shared = len([ch for ch in set(name) if ch in g])
        # 控件类优先（region 只是"有东西"，语义最弱）
        bonus = {"button": 3, "menuitem": 3, "tabitem": 2, "link": 2, "textbox": 2,
                 "checkbox": 2, "radio": 2, "combobox": 2}.get(n.get("role"), 0)
        scored.append((shared * 2 + bonus, n))
    scored.sort(key=lambda x: -x[0])
    return [n for _, n in scored[:k]]


def _slow_brain(goal: str, nodes: list, limit: int = 12) -> dict:
    """**慢脑**：权重大模型在短名单里挑一个（只回答序号，坐标仍取原生命中）。

    契约来自实测（2026-11-06）：给 5-12 个纯名字候选，它 1.4 秒答 "2"；
    给 30 个带 role 前缀的长清单，它会保守地答 -1。**候选要短、要干净。**
    """
    import sys
    import urllib.request
    sys.path.insert(0, str(_ROOT))
    try:
        from gbt_allinone import weights as W
    except Exception as exc:                             # noqa: BLE001
        return {"ok": False, "why": "weights 指针读不到：%s" % exc}
    ep = W.endpoint()
    if not ep:
        return {"ok": False, "why": W.diag().get("why") or "没有权重端点"}
    cap = _shortlist(goal, nodes, limit)
    if not cap:
        return {"ok": False, "why": "没有可候选的节点"}
    lines = "\n".join("%d. %s" % (i, str(n.get("name"))[:30]) for i, n in enumerate(cap))
    prompt = ("目标：%s\n候选：\n%s\n\n选出最匹配的一项，只输出序号数字；都不匹配就输出 none。"
              % (goal, lines))
    body = json.dumps({"model": W.model() or "gbt-v8", "temperature": 0, "max_tokens": 10,
                       "messages": [{"role": "user", "content": prompt}]}, ensure_ascii=False).encode("utf-8")
    t0 = time.time()
    req = urllib.request.Request(ep + "/chat/completions", data=body,
                                 headers={"content-type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as exc:                             # noqa: BLE001
        return {"ok": False, "why": "权重端点不可达：%s: %s" % (type(exc).__name__, exc)}
    txt = str(((j.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    ms = int((time.time() - t0) * 1000)

    # 认三种回法：裸数字 / none / 自带信封的 JSON
    pick = None
    m = re.search(r"-?\d+", txt)
    if txt.lower().startswith("none"):
        pick = -1
    elif m:
        pick = int(m.group(0))
    else:
        a, b = txt.find("{"), txt.rfind("}")
        if a >= 0 and b > a:
            try:
                jj = json.loads(txt[a:b + 1])
                for k in ("i", "index", "target_index"):
                    if isinstance(jj.get(k), int):
                        pick = jj[k]
                        break
                if pick is None:
                    for k in ("assignments", "payload", "rows"):
                        for it in (jj.get(k) or []):
                            if isinstance(it, dict) and isinstance(it.get("i"), int):
                                pick = it["i"]
                                break
            except Exception:                            # noqa: BLE001
                pick = None
    if pick is None:
        return {"ok": False, "why": "慢脑没给可用序号：%s" % txt[:60], "ms": ms}
    if pick < 0 or pick >= len(cap):
        return {"ok": False, "why": "慢脑说没有匹配项（%s）" % txt[:40], "ms": ms}
    n = cap[pick]
    return {"ok": True, "op": "CLICK", "target_index": int(n["index"]),
            "confidence": 0.7, "name": n.get("name"), "model": W.model(),
            "ms": ms, "候选数": len(cap), "原话": txt[:40]}

def _confirm_fresh(obs: dict, node: dict | None = None) -> dict:
    """动手前的现场复验：**现在这一帧**还和做决策时看到的一样吗？

    这是「400ms 新鲜度」在慢管线里的等价物：不拿"3 秒前的图"直接点，
    而是先确认屏幕没变（帧差为 0）再落手；变了就如实拒动、要求重看。
    """
    shot = obs.get("screenshot")
    if not shot:
        return {"ok": False, "why": "没有可复验的截图"}
    cap = _plug("screen_capture", {}, timeout=30)
    now = ((cap.get("result") or {}).get("path")) if cap.get("ok") else None
    if not now:
        return {"ok": False, "why": "复验拍不到新帧：%s" % (cap.get("error") or cap.get("raw"))}
    d = _plug("vision_diff", {"pathA": shot, "pathB": now, "threshold": 18}, timeout=30)
    if not d.get("ok"):
        return {"ok": False, "why": "复验帧差失败：%s" % (d.get("error") or d.get("raw"))}
    areas = (d.get("result") or {}).get("areas") or []
    if node and int(node.get("w") or 0) > 0:
        # 只看**目标框内**：光标闪、计时器走、别的窗口重绘都不该让目标"过期"
        nx, ny = int(node.get("x") or 0), int(node.get("y") or 0)
        nw, nh = int(node.get("w") or 0), int(node.get("h") or 0)
        pad = 8

        def _hit(a):
            ax, ay = int(a.get("x") or 0), int(a.get("y") or 0)
            aw, ah = int(a.get("w") or 0), int(a.get("h") or 0)
            return (ax < nx + nw + pad and ax + aw > nx - pad and
                    ay < ny + nh + pad and ay + ah > ny - pad)

        rel = [a for a in areas if _hit(a)]
        return {"ok": not rel, "changed": len(rel), "全屏": len(areas), "now": now,
                "why": ("目标区域未变（全屏 %d 处变动都在框外）" % len(areas)) if not rel
                else ("目标区域变了（%d 处）" % len(rel))}
    changed = int((d.get("result") or {}).get("changed") or 0)
    return {"ok": changed == 0, "changed": changed, "now": now,
            "why": "画面未变（帧差 0 处），观测仍有效" if changed == 0 else "画面已变（%d 处），观测过期" % changed}


def _eye():
    """**连续帧流**那只眼（tools/codex-scripts/eye-stream.py）—— 有就用它，没有就退回按需抓。

    🔴 2026-10-10 修的真实理由：V9 的 core/vision_loop.py 是**连续帧流**（独立抓帧线程 + 只留
    最新帧，端到端约 24ms、实测 640x360 约 57~75fps），而本件原来是**按需截图** ——
    那正是 V9 自己承认过的病根（「一帧一停，等于盲人摸象」）。
    用按需截图的帧去卡「帧龄 <= 400ms」⇒ 频繁拒动 ⇒ **反过来限制了她的能力**。
    """
    global _EYE
    if _EYE is not None:
        return _EYE
    try:
        import importlib.util as _u
        p = _ROOT / "tools" / "codex-scripts" / "eye-stream.py"
        if p.is_file():
            spec = _u.spec_from_file_location("_gbt_eye_stream", p)
            m = _u.module_from_spec(spec)
            spec.loader.exec_module(m)
            _EYE = m
    except Exception:                                        # noqa: BLE001
        _EYE = None
    return _EYE


def look() -> dict:
    """**眼**：一次取全（UIA 控件 + OCR 文字 + 视觉块），并给出快脑要的 nodes。

    走 7788 触手网关的 vision_scene —— APP 侧同一条口，不走旁路。
    age_ms 是**这张图从抓下来到现在的真实年龄**（不写 0）；动手前由 act() 现场复验。
    """
    t0 = time.time()
    p = _plug("vision_scene", {"limit": 200}, timeout=90)
    if p.get("ok") and isinstance(p.get("result"), dict):
        sc = p["result"]
        nodes = _nodes_from_scene(sc)
        shot = ((sc.get("ocr") or {}).get("path")) or None
        return {"ok": True, "op": "look", "at": t0,
                "age_ms": int((time.time() - t0) * 1000),
                "confirm_required": True,
                "来源": "7788 · vision_scene（UIA+OCR+视觉块）",
                "节点数": len(nodes), "nodes": nodes,
                "screenshot": shot, "raw": sc, "为什么": "看到了"}
    s = _see()
    return {"ok": s["ok"], "op": "look", "at": s["at"],
            "age_ms": int((time.time() - t0) * 1000), "confirm_required": True,
            "来源": "按需抓（7788 不可用，退回 tentacle see）",
            "节点数": 0, "nodes": [], "screenshot": None, "raw": s.get("raw"),
            "为什么": s.get("why") or "看到了"}

def hear(seconds: int = 6) -> dict:
    """**耳**：真听一段（voice 的 listen 口：录音 + 识别）。

    🔴 教训（Owner 2026-10-08 亲自纠过）：**别一看端点 0 就下"没麦"的结论** ——
       真因往往是**我们壳没放媒体权限**。壳里已现读确认：main.cjs:1252
       「entry.id === 'digital-human' || entry.media_capture === true」才装 media 放行 ⇒
       数字人那扇窗**有耳**；其它窗要在注册表显式登记 media_capture。
    """
    try:
        import sys
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone import api
        r = api.run_task("voice", {"op": "listen", "seconds": int(seconds)})
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "op": "hear", "why": "%s: %s" % (type(exc).__name__, exc)}
    ok = bool(isinstance(r, dict) and (r.get("ok") or r.get("status") == "ok"))
    return {"ok": ok, "op": "hear", "at": time.time(),
            "文本": (r or {}).get("text") or (r or {}).get("result"),
            "为什么": "" if ok else str((r or {}).get("error") or (r or {}).get("status") or "听不到")}


def speak(text: str) -> dict:
    """**嘴**：真出声（voice 的 TTS 口）。**没内容就不说**（不许空说）。"""
    if not str(text or "").strip():
        return {"ok": False, "op": "speak", "拒说": True, "为什么": "**没内容就不说**"}
    try:
        import sys
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone import api
        r = api.run_task("voice", {"text": str(text)})
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "op": "speak", "why": "%s: %s" % (type(exc).__name__, exc)}
    ok = bool(isinstance(r, dict) and (r.get("ok") or r.get("status") == "ok"))
    return {"ok": ok, "op": "speak", "说了": str(text)[:60],
            "为什么": "" if ok else str((r or {}).get("error") or (r or {}).get("status") or "说不出")}


def think(goal: str, obs: dict, expect: str = "") -> dict:
    """**脑**：快脑（规则）先判；判不出就交权重大模型（8792）在候选里挑。

    坐标永远取原生层（UIA/OCR/视觉块）的像素，权重只回答"点哪一个"。
    """
    ctl = _ctl()
    nodes = obs.get("nodes") or []
    age = int(obs.get("age_ms") or 0)
    d = ctl.fast_policy({"goal": goal, "nodes": nodes, "age_ms": age,
                         "done_evidence": obs.get("done_evidence")})
    brain = "快脑 · control_loop.fast_policy"
    slow = None
    if d.get("op") == "BLOCKED" and nodes:
        slow = _slow_brain(goal, nodes)
        if slow.get("ok"):
            d = {"op": slow["op"], "target_index": slow["target_index"],
                 "confidence": slow.get("confidence", 0.5), "why": slow.get("why")}
            brain = "慢脑 · 权重大模型 %s（%sms）" % (slow.get("model") or "", slow.get("ms"))
    ok, why = ctl.guard({"goal": goal, "nodes": nodes,
                         "age_ms": 0 if obs.get("confirm_required") else age},
                        d, max_age_ms=STALE_MS)
    expect = str(expect or "").strip()
    return {"op": "think", "决策": d.get("op"), "目标": d.get("target_index"),
            "置信度": d.get("confidence"), "两查": {"过": ok, "说明": why},
            "预期": expect or None,
            "预期判据": ("**没写预期 => 不许动手**" if not expect
                        else "动作后画面应出现：%s" % expect[:60]),
            "脑": brain, "慢脑": slow,
            "新鲜度": ("决策用的图已超过 %dms，动手前由 act() 现场复验帧差" % STALE_MS
                       if obs.get("confirm_required") else "观测是新鲜的")}

def act(decision: dict, obs: dict) -> dict:
    """**手**：走 7788 落点。**没有新鲜观测、两查没过、或画面已变 => 拒动。**"""
    age = int(obs.get("age_ms") or 0)
    if age > STALE_MS and not obs.get("confirm_required"):
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "观测已过期 %dms > %dms => **看不到就不动**" % (age, STALE_MS)}
    if not decision.get("两查", {}).get("过"):
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "两查没过 => 拒动：%s" % decision.get("两查", {}).get("说明")}
    if decision.get("决策") in (None, "BLOCKED"):
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "决策脑给的是 BLOCKED => **没脑就不动**"}
    if not str(decision.get("预期") or "").strip():
        return {"ok": False, "op": "act", "拒动": True, "在哪一步": "②脑",
                "为什么": "**没写「预期的画面变化」=> 不许动手**"}
    nodes = obs.get("nodes") or []
    idx = decision.get("目标")
    node = nodes[idx] if isinstance(idx, int) and 0 <= idx < len(nodes) else None
    if node is None:
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "决策给的序号 %r 不在观测里（观测过期？）" % (idx,)}
    # 现场复验：慢管线用"帧差为 0"兑现 400ms 新鲜度
    conf = _confirm_fresh(obs, node)
    if not conf.get("ok"):
        return {"ok": False, "op": "act", "拒动": True, "复验": conf,
                "为什么": "**%s** => 拒动（不许拿过期的图动手）" % conf.get("why")}
    x, y = int(node.get("cx") or 0), int(node.get("cy") or 0)
    r = _plug("input_click", {"x": x, "y": y}, timeout=30)
    return {"ok": bool(r.get("ok")), "op": "act", "在": {"x": x, "y": y},
            "点的是": {"名字": node.get("name"), "来源": node.get("source")},
            "复验": conf, "结果": r.get("result"), "raw": r.get("raw"),
            "为什么": "" if r.get("ok") else str(r.get("error") or r.get("raw"))[:120]}

def verify(before: dict, after: dict, expect: str = "") -> dict:
    """**验**：动完再看一次并比对。**三态**，不许把"变了"一律念成"成了"。

    比对口径 = **节点名字集合**（UIA 控件 + OCR 文字 + 视觉块）。
    不拿整份 scene JSON 比 —— 里面的截图路径每秒都在变，会把"没变"误判成"变了"。
    """
    bnames = {str(n.get("name")) for n in (before.get("nodes") or [])}
    anames = {str(n.get("name")) for n in (after.get("nodes") or [])}
    added = sorted(anames - bnames)[:8]
    removed = sorted(bnames - anames)[:8]
    changed = bool(added or removed)
    exp = str(expect or "").strip()
    hit = [n for n in anames if exp and exp in n][:3] if exp else []
    if not changed:
        state, note = "没动成", "**没动成**（前后节点一致）—— 如实报，不许算成功"
    elif not exp:
        state, note = "变了（无预期可比）", "**变了但没写预期** => 只能说'变了'，不敢说'成了'"
    elif hit:
        state, note = "按预期生效", "画面里出现预期「%s」：%s" % (exp, " / ".join(hit))
    else:
        state, note = "变了但非预期", "**变了，但不是预期的那种变化**（预期「%s」没出现）" % exp[:40]
    return {"op": "verify", "画面变了吗": changed, "三态": state, "预期": exp or None,
            "新增节点": added, "消失节点": removed,
            "结论": note, "算成功": state == "按预期生效"}

def loop(goal: str, dry: bool = True, expect: str = "") -> dict:
    """**四步闭环一次跑完**；任何一步不成立就**停在原地并说清是哪一步**。

    expect = **预期的画面变化**（动完画面里该出现什么）。非 dry 时**必填**。
    """
    steps = []
    obs = look()
    steps.append({"步": "①眼", "ok": obs["ok"], "读数": obs.get("为什么"),
                  "帧龄ms": obs.get("age_ms"), "来源": obs.get("来源")})
    if not obs["ok"]:
        out = {"ok": False, "op": "loop", "goal": goal, "停在第": "①眼",
               "为什么": "看不到 ⇒ **绝不下发动作**（原生视觉）：" + str(obs.get("为什么")),
               "步骤": steps}
        _log(out)
        return out
    dec = think(goal, obs, expect=expect)
    steps.append({"步": "②脑", "ok": dec["两查"]["过"], "读数": "决策=%s" % dec["决策"]})
    if not dec["两查"]["过"] or dec["决策"] == "BLOCKED":
        out = {"ok": False, "op": "loop", "goal": goal, "停在第": "②脑",
               "为什么": "决策脑没给出可执行动作（BLOCKED）⇒ **没脑就不动**", "步骤": steps}
        _log(out)
        return out
    if dry:
        out = {"ok": True, "op": "loop", "goal": goal, "dry": True, "步骤": steps,
               "会做什么": dec["决策"], "口径": "dry 只走到②脑，不落手"}
        _log(out)
        return out
    res = act(dec, obs)
    steps.append({"步": "③手", "ok": res.get("ok"), "读数": str(res.get("为什么") or "已下发")[:80]})
    if not res.get("ok"):
        out = {"ok": False, "op": "loop", "goal": goal, "停在第": "③手", "步骤": steps}
        _log(out)
        return out
    after = look()
    ver = verify(obs, after, expect=expect)
    steps.append({"步": "④验", "ok": ver["算成功"], "读数": "%s · %s" % (ver["三态"], ver["结论"])})
    out = {"ok": ver["算成功"], "op": "loop", "goal": goal, "步骤": steps, "验证": ver,
           "口径": "**只有【按预期生效】才算成功**；变了但非预期、变了但没写预期，都不算"}
    _log(out)
    return out


def status() -> dict:
    return {"ok": True, "op": "status", "口径": "**眼·耳·嘴·手四觉** → 脑 → 手 → 验；缺一觉就不许动/说",
            "四觉": {"眼": "tentacle see（已实测可看）",
                     "耳": "voice op=listen（壳已对 digital-human 放 media；其它窗需登记 media_capture）",
                     "嘴": "voice TTS（没内容不说）",
                     "手": "tentacle click/type（门层眼手同票）"},
            "新鲜度阈_ms": STALE_MS,
            "门层钉死": "凡 desktop_control 必须同时有 privacy_read（tools/codex-scripts/vision-pinned-check.py）",
            "决策脑": "System-One 契约（control_loop.fast_policy）· 云侧 Laya c02 未配置",
            "账": str(AUDIT)}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "look":
        return look()
    if op == "think":
        return think(str(kw.get("goal") or ""), kw.get("obs") or {})
    if op == "act":
        return act(kw.get("decision") or {}, kw.get("obs") or {})
    if op == "verify":
        return verify(kw.get("before") or {}, kw.get("after") or {})
    if op == "loop":
        return loop(str(kw.get("goal") or ""), dry=bool(kw.get("dry", True)),
                expect=str(kw.get("expect") or ""))
    if op == "hear":
        return hear(int(kw.get("seconds") or 6))
    if op == "speak":
        return speak(str(kw.get("text") or ""))
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["status", "look", "hear", "speak", "think", "act", "verify", "loop"]}
