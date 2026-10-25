# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 语义路由（主路）与启发式降级（辅路）—— Owner 2026-09-19 定架构。

为什么要升维：第三批全新句子的泛化读数是 **10/24 = 41.7%**（判据 80%，未达标）。
归因指向一个**架构天花板**，不是词表不够勤快：
  · 泛动词黑洞：'读/看' 在字符 2-gram 下，"读终端输出" 与 "读剪贴板" 数学距离几乎一样；
  · 口语 vs 书面语：'挪 / 翻一屏 / 处理掉' 是活人说话，词表是动作名；
  · 同族谁更具体：`scroll` vs `scroll_to_bottom` 靠字符分不开。
结论：字符匹配的泛化上限就在四成量级；再补词是自我消耗（这条有数字，不是感觉）。

分工（Owner 口径）：
  **主路**：把 89 个触手方法（名 + 邻域 + 别名）做成工具表交给统一大模型，让它选；
  **辅路**：词表 + 方向层，退居二线 —— 模型不可用时降级，模型给出结果后做二次校验防幻觉。

三条纪律：
  1. **不许假绿**：模型不可用（未授权/断网/超时/输出不合法）⇒ 返回 `ok: False` 并**标明降级**，
     绝不用启发式结果冒充语义路由结果。
  2. **幻觉防护**：模型给出不在真实方法表里的名字 ⇒ 判 `invalid_method`，**不采信、不模糊匹配**。
  3. **只读**：本模块不执行任何动作，只输出"选哪个"，执行仍走既有门禁与审计。
"""
from __future__ import annotations

import json
import os

SYSTEM = ("你是能力路由员。给一句人话，从给定方法清单里选**一个**最合适的方法名。"
          "只输出 JSON，不要解释：{\"method\": \"<方法名>\", \"confidence\": <0-1小数>, "
          "\"reason\": \"<一句话>\"}。清单里没有合适的就输出 {\"method\": null}，"
          "**不许编造清单外的名字**。")


def grams(text, n: int = 2) -> set:
    """字符 n-gram（中文无空格也能命中）。

    2026-09-19（Owner：路由不许三处真相）：本函数是**全框架唯一实现** ——
    `brain_exec` 与 `tentacle.bridge` 的启发式打分一律 import 这里，不再各留一份
    同名 `_grams`。算法只有一份，改口径只改这一处。
    """
    s = str(text).lower()
    out = {s[i:i + n] for i in range(max(0, len(s) - n + 1))}
    # 2026-10-13 两条 gram 卫生（都实测过、都只踢"不承载语义"的东西）：
    #   ① 纯数字串不算词 ② **含空白的 gram 不算词**
    # ② 的实测病象：`把这张图放大到 2560 并锐化一下` 里，`vision_grounding`/`media_stamp`/
    #    `answer_shaper` 各拿 4.5，命中项**全是** `' 2'` / `'0 '` / `'到 '` 这类跨空格垃圾；
    #    而真该命中的 `zimage_rewash` 只靠 `'放大'` 拿 1.5。⇒ 空白不承载语义，踢掉。
    #    只踢"含空白的 gram"（不做全文去空格）⇒ 英文非空格 n-gram 照旧，英文匹配不受损。
    out = {g for g in out if not g.isdigit() and not any(c.isspace() for c in g)}
    if len(s) <= n and not s.isdigit() and not any(c.isspace() for c in s):
        out.add(s)
    return out


def method_table() -> dict:
    """把触手方法做成工具表（名 + 邻域 + 别名）。清单唯一真相仍是 bridge 那两份表。"""
    from .tentacle import bridge as TB
    owner = {}
    for dom, info in TB.TENTACLE_NEIGHBORHOOD_MAP.items():
        for m in info["powered_by"]:
            owner.setdefault(m, dom)
    items = []
    for m in sorted(owner):
        items.append({"method": m, "neighborhood": owner[m],
                      "hint": TB.INTENT_ALIASES.get(m, "")[:80]})
    return {"ok": True, "count": len(items), "items": items}


def available() -> dict:
    """主路可用性：只看**真配置**，不做试探性调用（省一次出网）。

    R-H296（2026-09-22 根因修复）：原来未配置时只说一句「统一大模型通道未配置」——
    **读的人没法行动**：是缺 key？缺 base？缺 model？还是缺 provider？该设哪个环境变量？
    现在把 **缺哪几项** 与 **认哪些环境变量** 一并报出来（**只看有没有，不回显任何密钥值**）。
    为什么这是根因修复而不是"话术"：模糊错会被读成"这功能坏了"，
    指名错会被读成"去设这个变量" —— 后者一次就能修好，前者会一直挂着。
    """
    try:
        from .llm import cloud_llm as CL
        provider = CL.PROVIDER or ""
        fields = {"PROVIDER": bool(provider), "API_KEY": bool(CL.API_KEY),
                  "BASE_URL": bool(CL.BASE_URL), "MODEL": bool(CL.MODEL)}
        ready = all(fields.values())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"通道不可读: {type(exc).__name__}",
                "fallback": "heuristic",
                "missing": ["通道模块读不到"], "how": []}
    out = {"ok": ready, "provider": provider or None,
           "fallback": "heuristic",
           "note": "可用 ≠ 已授权：真跑仍受 external_llm 人工授权门约束，"
                   "未授权时调用会如实返回门禁拒绝，不会降级冒充。"}
    if ready:
        out["reason"] = None
        return out
    # 未配置：把缺项与认的变量名一并给出（**只报变量名与有无，不碰值**）
    missing = [k for k, v in fields.items() if not v]
    cands: list[str] = []
    how: list[str] = []
    try:
        for name, envs, _url, _model in getattr(CL, "_KEY_CHAIN", ()):
            cands += list(envs)
            if any(os.environ.get(e) for e in envs):
                how.append("检测到 %s 已设 ⇒ 但未生效，检查 GBT_LLM_PROVIDER/GBT_LLM_BASE_URL/GBT_LLM_MODEL"
                           % envs[0])
    except Exception as exc:  # noqa: BLE001
        # 🔴 绝不静默吞：吞掉的错会变成**半真话** —— 上面这份 accepted_env 会只列到出错那一家为止，
        # 读的人以为"就这些变量"，其实是我中途炸了。实测就踩过（当时 os 没导入）。
        how.append("⚠ 候选环境变量只读到一半：%s: %s —— 别把这份清单当全量"
                   % (type(exc).__name__, str(exc)[:60]))
    if not how:
        how.append("任一 provider 的环境变量设上即可自动选中；或显式指定 "
                   "GBT_LLM_PROVIDER + 对应的 *_API_KEY")
    out.update({
        "reason": "统一大模型通道未配置：缺 %s" % "、".join(missing),
        "missing": missing,
        "accepted_env": cands,
        "how": how,
        "config_source": "gbt_allinone/llm/cloud_llm.py 的 _KEY_CHAIN（7 家 provider 的优先级链）",
    })
    return out


def choose(intent: str, *, provider: str = "tentacle_method") -> dict:
    """主路：让统一大模型在真实方法表里选一个。失败一律如实报，不降级冒充。"""
    text = str(intent or "").strip()
    if not text:
        return {"ok": False, "error": "需要 intent", "path": "semantic"}
    table = method_table()
    lines = "\n".join(f"- {i['method']}（{i['neighborhood']}）{i['hint']}"
                      for i in table["items"])
    # 🔴 2026-10-12 修（实测根因：一句寒暄「你好，我是主人」被模型当聊天回，
    #    没输出 JSON ⇒ 主路整条失效 ⇒ 永远降级到词表辅路 ⇒ intent 路由不出能力）。
    #    两处加固，都只在这一个函数内，不动架构：
    #      ① **格式约束提到结尾再钉一次**（长清单会把模型的格式注意力冲散，
    #         实测把「只输出 JSON」放 system 里不够，必须在人话之后**最后一句**再说）；
    #      ② **非 JSON / 空返回 ⇒ 追加一句纠正重试一次**（偶发跑偏不该判整条主路死刑）。
    #    纪律不变：仍不许把降级结果冒充主路结果；两次都不合法才如实报错降级。
    def _strip_fence(s: str) -> str:
        b = str(s or "").strip()
        if b.startswith("```"):
            b = b.strip("`")
            b = b.split("\n", 1)[1] if "\n" in b else b
        return b.strip()

    prompt = (f"方法清单（共 {table['count']} 个）：\n{lines}\n\n人话：{text}\n\n"
              "现在只输出 JSON 对象本身（第一个字符必须是 {），不要任何解释、"
              "不要寒暄、不要 Markdown 代码块围栏。")
    # 🔴 2026-10-12 第二次加固（实测残留：约 1/6 的句子两轮都不给 JSON ——
    #    第 2 轮仍带着 89 条方法清单，模型的格式注意力**又被冲散**）。
    #    => 第 2 轮**把清单撤掉**，只留「人话 + 待选名字」和一句纯格式要求：
    #       模型这时的任务从"在长清单里挑"退成"把已定的事写成 JSON"，跑偏面小得多。
    #       纪律不变：这样拿到的仍必须是**清单内的真名字**（下面 invalid_method 照样拦）。
    _retry_prompt = (
        f"人话：{text}\n\n"
        f"可选方法名（只许从这些里选一个，或 null）：{', '.join(i['method'] for i in table['items'])}\n\n"
        "立刻只输出这一行 JSON，不要任何别的字："
        "{\"method\": \"<上面的名字之一，或 null>\", \"confidence\": <0-1小数>, "
        "\"reason\": \"<一句话>\"}")
    raw, r, data, err = "", None, None, ""
    _attempts_detail: list = []
    for _attempt in (1, 2, 3):
        _msg = (prompt if _attempt == 1 else
                _retry_prompt if _attempt == 2 else
                # 🔴 2026-10-12 第三次兜底（实测残留：约 1/6 句子两轮仍不给 JSON，
                #    且**不同句子的失败在轮次间会换人** ⇒ 说明是模型侧随机跑偏，
                #    不是某个 prompt 写坏了）。第 3 轮做两件事：**清单再缩一次**
                #    （只给名字，砍掉邻域与提示词），并把格式要求压成最短一句。
                #    仍不合法 ⇒ 如实报三层都失败，绝不冒充。
                f"从下列名字里选一个，或 null：{', '.join(i['method'] for i in table['items'])}\n"
                f"人话：{text}\n"
                "只回 JSON：{\"method\": null, \"confidence\": 0, \"reason\": \"\"}")
        try:
            from .llm import unified as LLM
            r = LLM.ask(_msg, system=SYSTEM, temperature=0.0, max_tokens=300,
                        timeout=60, purpose="semantic_route")
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"[:160]
            _attempts_detail.append({"attempt": _attempt, "error": err})
            continue
        if not r.get("ok"):
            return {"ok": False, "path": "semantic", "provider": r.get("provider"),
                    "error": r.get("error", "模型调用失败"),
                    "note": "主路不可用 ⇒ 上层应如实降级到辅路，并把降级这件事报出来"}
        raw = str(r.get("reply") or "")
        try:
            data = json.loads(_strip_fence(raw))
            err = ""
            break
        except Exception as exc:  # noqa: BLE001
            err = f"模型输出不是合法 JSON: {exc}"
            _attempts_detail.append({"attempt": _attempt, "raw_head": raw[:120]})
    if data is None:
        return {"ok": False, "path": "semantic", "error": err or "模型输出不是合法 JSON",
                "raw_head": raw[:200], "attempts": 3,
                "attempts_detail": _attempts_detail,
                "note": "三层加固（原样 / 去长清单 / 只给名字）都不合法 ⇒ 如实降级，不冒充"}
    picked = data.get("method")
    if picked is None:
        return {"ok": True, "path": "semantic", "method": None,
                "reason": data.get("reason") or "模型判定清单里没有合适的",
                "provider": r.get("provider"), "model": r.get("model")}
    if picked not in {i["method"] for i in table["items"]}:
        # 幻觉防护：清单外的方法名一律不采信，也不做模糊匹配替它猜
        return {"ok": False, "path": "semantic", "error": "invalid_method",
                "invalid": picked, "note": "模型给的名字不在真实方法表里 ⇒ 不采信"}
    return {"ok": True, "path": "semantic", "method": picked,
            "confidence": data.get("confidence"), "reason": data.get("reason"),
            "provider": r.get("provider"), "model": r.get("model")}


def route(intent: str, mode: str = "auto") -> dict:
    """路由入口。mode: auto（主路可用就走主路，否则降级并**如实标注**）/ semantic / heuristic。"""
    from .tentacle import bridge as TB
    m = str(mode or "auto").lower()
    if m in ("heuristic", "local"):
        r = TB.route_method(intent)
        r["path"] = "heuristic"
        return r
    if m in ("semantic", "llm", "auto"):
        avail = available()
        if m != "semantic" and not avail.get("ok"):
            r = TB.route_method(intent)
            r["path"] = "heuristic"
            r["degraded"] = True
            r["degraded_reason"] = avail.get("reason") or "主路不可用"
            return r
        sem = choose(intent)
        if sem.get("ok"):
            sem["heuristic_second_opinion"] = (
                TB.route_method(intent).get("best") or {}).get("method")
            return sem
        if m == "semantic":
            return sem
        r = TB.route_method(intent)          # auto：主路失败→降级，但**标注出来**
        r["path"] = "heuristic"
        r["degraded"] = True
        r["degraded_reason"] = sem.get("error")
        return r
    return {"ok": False, "error": f"未知 mode: {mode}（auto / semantic / heuristic）"}


def status() -> dict:
    a = available()
    t = method_table()
    return {"ok": True, "semantic_available": a.get("ok"), "provider": a.get("provider"),
            "reason": a.get("reason"), "methods_in_table": t["count"],
            "gate": "external_llm 人工授权（未授权时主路如实报拒绝，不冒充）",
            "frozen_reading": {"holdout3": "10/24 = 41.7%（第三批全新句子，已冻结，不得据此调参）"}}
