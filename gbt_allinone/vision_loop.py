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
    """**眼**：优先取**当前最新一帧**（连续帧流，不阻塞）—— age_ms 是**真读数**。

    🔴 2026-10-10 修：原来这里把 age_ms **写死成 0** ⇒ 「帧龄超过 STALE_MS 就不许动手」那条
    判据**永远为假**（永远放行）—— 那是一条**假绿**判据，等于没有。现在：
      · 有实时眼 ⇒ 报**眼给的真 age_ms**（并带上帧号，可做"动作后必须见到新帧"的同步判据）；
      · 没有实时眼 ⇒ 退回按需抓，并把**这次抓取的真实耗时**当 age_ms（**不写 0**）。
    """
    m = _eye()
    if m is not None:
        try:
            lk = m.eyes("vision_loop").look()
            if lk.get("ok"):
                return {"ok": True, "op": "look", "at": lk.get("帧号"),
                        "age_ms": lk.get("age_ms"), "来源": "连续帧流（eye-stream）",
                        "尺寸": lk.get("尺寸"), "帧号": lk.get("帧号"),
                        "为什么": "看到了（最新帧）"}
        except Exception:                                    # noqa: BLE001
            pass
    t0 = time.time()
    s = _see()
    return {"ok": s["ok"], "op": "look", "at": s["at"],
            "age_ms": int((time.time() - t0) * 1000),
            "来源": "按需抓（实时眼不可用，如实标）",
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
    """**脑**：观测 → 类型化动作（System-One 契约；可换云上 Laya，调用方不动）。

    🔴 2026-10-10 补「**预期的画面变化**」（口径照 V9 core/senses_gate.py 的②）：
       V9 那条原文 —— 「**脑：必须带决策记录（目标 + 理由 + 预期的画面变化）→ 否则拒动
       （这就是"无脑操作"的解药）**」。
       本件原来只有"目标 + 决策"，**没有预期** ⇒ 第④步的"验"没有基准：
       它只能说"变了/没变"，**证不了"变对了没有"**（变了也可能是别的窗口弹出来了）。
       ⇒ 现在 expect 是决策记录的一部分；**空 expect 在 dry 之外一律拒动**（不许无脑动手）。
    """
    ctl = _ctl()
    nodes = obs.get("nodes") or []
    d = ctl.fast_policy({"goal": goal, "nodes": nodes,
                         "age_ms": int(obs.get("age_ms") or 0),
                         "done_evidence": obs.get("done_evidence")})
    ok, why = ctl.guard({"goal": goal, "nodes": nodes, "age_ms": int(obs.get("age_ms") or 0)},
                        d, max_age_ms=STALE_MS)
    expect = str(expect or "").strip()
    return {"op": "think", "决策": d.get("op"), "目标": d.get("target_index"),
            "置信度": d.get("confidence"), "两查": {"过": ok, "说明": why},
            "预期": expect or None,
            "预期判据": ("**没写预期 ⇒ 不许动手**（无脑操作就是这么来的）" if not expect
                        else "动作后画面应出现：%s" % expect[:60]),
            "脑": "System-One 契约（control_loop.fast_policy）· 云侧 Laya 未配置"}


def act(decision: dict, obs: dict) -> dict:
    """**手**：走唯一门下动作。**没有新鲜观测、或两查没过 ⇒ 拒动。**"""
    age = int(obs.get("age_ms") or 0)
    if age > STALE_MS:
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "观测已过期 %dms > %dms ⇒ **看不到就不动**（原生视觉闭环第①步）"
                          % (age, STALE_MS)}
    if not decision.get("两查", {}).get("过"):
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "两查没过 ⇒ 拒动：%s" % decision.get("两查", {}).get("说明")}
    if decision.get("决策") in (None, "BLOCKED"):
        return {"ok": False, "op": "act", "拒动": True,
                "为什么": "决策脑给的是 BLOCKED ⇒ **没脑就不动**，不许硬猜"}
    # 🔴 2026-10-10 补（照 V9 core/senses_gate.py 的②）：
    #    **没写「预期的画面变化」⇒ 不许动手** —— 这是在**动作之前**就掐掉「无脑操作」，
    #    而不是等第④步验完才发现白动一次。理由：没预期的动作，验的时候没有基准，
    #    「变了」会被误念成「成了」。所以宁可不动。
    if not str(decision.get("预期") or "").strip():
        return {"ok": False, "op": "act", "拒动": True, "在哪一步": "②脑",
                "为什么": "**没写「预期的画面变化」⇒ 不许动手**（无脑操作就是这么来的）："
                          "先说清【这一下动完，画面里该出现什么】"}
    try:
        import sys
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone import api
        r = api.run_task("tentacle", {"op": "click", "index": decision.get("目标")})
    except Exception as exc:                                 # noqa: BLE001
        return {"ok": False, "op": "act", "error": "%s: %s" % (type(exc).__name__, exc)}
    return {"ok": bool(isinstance(r, dict) and (r.get("ok") or r.get("status") == "ok")),
            "op": "act", "结果": r}


def verify(before: dict, after: dict, expect: str = "") -> dict:
    """**验**：动完再看一次并比对。**三态**，不许把"变了"一律念成"成了"。

    🔴 2026-10-10 补（照 V9 senses_gate 的④）：原来只有两态（变了=已生效 / 没变=没动成）——
    可「变了」也可能是**别的窗口弹出来**造成的。有 expect 之后判**三态**：
      · 没变                      ⇒ **没动成**
      · 变了 且 画面里出现 expect  ⇒ **按预期生效**（词命中，如实写清是词命中）
      · 变了 但 expect 没出现      ⇒ **变了，但不是预期的那种变化** ← 这一态原来会被误念成"已生效"
    """
    b = json.dumps(before.get("raw"), ensure_ascii=False, sort_keys=True)
    a = json.dumps(after.get("raw"), ensure_ascii=False, sort_keys=True)
    changed = b != a
    exp = str(expect or "").strip()
    if not changed:
        state, note = "没动成", "**没动成**（前后一致）—— 如实报，不许算成功"
    elif not exp:
        state, note = "变了（无预期可比）", "**变了但没写预期** ⇒ 只能如实说'变了'，**不敢说'成了'**"
    elif exp and exp in a:
        state, note = "按预期生效", "画面里出现预期串「%s」" % exp[:40]
    else:
        state, note = "变了但非预期", "**变了，但不是预期的那种变化**（预期「%s」没出现）—— 不许念成已生效" % exp[:40]
    return {"op": "verify", "画面变了吗": changed, "三态": state, "预期": exp or None,
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
        return loop(str(kw.get("goal") or ""), dry=bool(kw.get("dry", True)))
    if op == "hear":
        return hear(int(kw.get("seconds") or 6))
    if op == "speak":
        return speak(str(kw.get("text") or ""))
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["status", "look", "hear", "speak", "think", "act", "verify", "loop"]}
