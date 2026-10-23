# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 短剧/影视链路 · 模块1 剧本理解引擎（接口1：剧本 → 分镜）。

为什么先做这一个（Owner 2026-09-19 频道拆解）：
  十二个模块里，**只有它是链头** —— 下游「资产锚定 / 图生视频 / 配音 / 音乐 / 合成」
  全都吃它的输出。链头契约错了，后面十一个模块全错。
  而且它不需要任何外部 key 就能验：分镜是纯结构，字段齐不齐可数。

预注册判据（先立后跑，不事后调整）：
  R1 每个镜头必须带六个字段：景别 / 运镜 / 时长 / 情绪 / 角色位置 / 描述
  R2 缺字段**如实进 missing**，不许补默认值冒充完整（《反假绿律》）
  R3 镜头时长之和必须等于声明总时长（容差 0.05s）
  R4 空输入或过短输入必须**拒绝**，不许编一个分镜出来
  R5 确定性路径**不调外网**，可离线复验；用了模型必须在 source 里如实标出

两条路径，不互相冒充：
  parse_timed() — 确定性：认「0s – 4s（标题）」这种带时间码的分镜稿（她自己那 57 份
                  提示词模板就是这个格式），只做切分与**字面检出**，检出不到的字段
                  如实进 missing。
  split()       — 语义：交给她的模型通道补景别/运镜/情绪，输出仍要过同一套校验。
"""
from __future__ import annotations

import json
import re
import time

REQUIRED = ("shot_size", "camera", "dur", "emotion", "subject", "desc")
_FIELD_CN = {"shot_size": "景别", "camera": "运镜", "dur": "时长",
             "emotion": "情绪", "subject": "角色位置", "desc": "描述"}

_TIME_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*s\s*[–—\-~至到]\s*(\d+(?:\.\d+)?)\s*s")
_MIN_CHARS = 20          # 少于这长度视为没内容，直接拒

# 字面检出表：只在文本里**真的出现**这些词时才算命中（读数，不是推断）。
_SIZE_MAP = (
    ("大特写", "大特写"), ("特写", "特写"), ("近景", "近景"), ("中近景", "中近景"),
    ("中景", "中景"), ("全景", "全景"), ("远景", "远景"), ("空镜", "空镜"),
    ("extreme close-up", "大特写"), ("close-up", "特写"), ("close up", "特写"),
    ("medium shot", "中景"), ("wide shot", "远景"), ("full shot", "全景"),
    ("establishing shot", "远景"), ("over-the-shoulder", "过肩"),
)
_CAM_MAP = (
    ("推近", "推近"), ("推镜", "推近"), ("拉远", "拉远"), ("环绕", "环绕"),
    ("横移", "横移"), ("平移", "横移"), ("跟拍", "跟拍"), ("手持", "手持"),
    ("升降", "升降"), ("摇镜", "摇镜"), ("变焦", "变焦"), ("慢动作", "慢动作"),
    ("slow push-in", "推近"), ("push-in", "推近"), ("orbit", "环绕"),
    ("pan", "横移"), ("tilt", "俯仰"), ("dolly", "移动车"), ("zoom", "变焦"),
    ("handheld", "手持"), ("crane", "升降"), ("tracking", "跟拍"),
    ("slow-motion", "慢动作"), ("slow motion", "慢动作"),
)
_EMO_MAP = (
    ("震惊", "震惊"), ("紧张", "紧张"), ("恐惧", "恐惧"), ("愤怒", "愤怒"),
    ("悲伤", "悲伤"), ("平静", "平静"), ("好奇", "好奇"), ("温柔", "温柔"),
    ("兴奋", "兴奋"), ("压抑", "压抑"), ("绝望", "绝望"), ("温暖", "温暖"),
    ("calm", "平静"), ("curious", "好奇"), ("angry", "愤怒"),
    ("sad", "悲伤"), ("afraid", "恐惧"), ("shock", "震惊"),
)


def _hits(text: str, table) -> list:
    """按**在文本里出现的位置**给线索排序（不是按表里的顺序）。

    踩过的坑：'Slow-motion, cinematic orbit camera' 原先按表序判成「环绕」——
    因为「orbit」在表里排在「slow-motion」前面。谁在原文里先被写到，才是谁在指导这个镜头。
    """
    low = text.lower()
    found = []
    for key, val in table:
        pos = low.find(key)
        if pos >= 0:
            found.append((pos, val))
    found.sort()
    seen, ordered = set(), []
    for _, val in found:
        if val not in seen:
            seen.add(val)
            ordered.append(val)
    return ordered


def _hit(text: str, table) -> str:
    hits = _hits(text, table)
    return hits[0] if hits else ""


def _validate(shots: list, total: float | None) -> dict:
    """R1/R2/R3 的机器判定：缺哪个字段、时长对不对，全部如实报。"""
    missing = []
    for sh in shots:
        lack = [_FIELD_CN[f] for f in REQUIRED
                if f != "dur" and not str(sh.get(f) or "").strip()]
        if sh.get("dur") is None:
            lack.append("时长")
        if lack:
            missing.append({"idx": sh.get("idx"), "lack": lack})
    sum_dur = round(sum(float(s.get("dur") or 0) for s in shots), 3)
    dur_ok = total is None or abs(sum_dur - float(total)) <= 0.05
    return {
        "shots": len(shots),
        "missing": missing,
        "dur_sum": sum_dur,
        "dur_declared": total,
        "dur_ok": dur_ok,
        "complete": (not missing) and dur_ok,
    }


def parse_timed(text: str) -> dict:
    """确定性切分：认「0s – 4s（标题）」格式的分镜稿。R5：不调外网。"""
    raw = str(text or "")
    if len(raw.strip()) < _MIN_CHARS:
        return {"ok": False, "error": "输入过短，拒绝编造分镜（R4）",
                "source": "rule-based", "chars": len(raw.strip())}
    marks = list(_TIME_RANGE.finditer(raw))
    if not marks:
        return {"ok": False, "error": "没有时间码，确定性路径吃不下；请走 split()（模型语义路径）",
                "source": "rule-based", "hint": "分镜稿请写成『0s – 4s（标题）』"}
    shots = []
    for i, m in enumerate(marks):
        start = float(m.group(1))
        end = float(m.group(2))
        body_from = m.end()
        body_to = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
        body = raw[body_from:body_to].strip()
        title = ""
        tm = re.match(r"[（(]([^）)]*)[）)]", body)
        if tm:
            title = tm.group(1).strip()
        shots.append({
            "idx": i + 1,
            "t0": start, "t1": end, "dur": round(end - start, 3),
            "title": title,
            "shot_size": _hit(body, _SIZE_MAP),
            "camera": _hit(body, _CAM_MAP),
            "emotion": _hit(body, _EMO_MAP),
            # 全部线索留痕：多个运镜/情绪时，不把没选中的那个藏掉（R2 如实报）。
            "cues": {"shot_size": _hits(body, _SIZE_MAP),
                     "camera": _hits(body, _CAM_MAP),
                     "emotion": _hits(body, _EMO_MAP)},
            "subject": "",            # 确定性路径不猜人物位置
            "desc": " ".join(body.split())[:400],
            "dialogue": "",           # 分镜稿里没有就是没有，不编
        })
    total = shots[-1]["t1"]
    return {"ok": True, "source": "rule-based", "verdict": _validate(shots, total),
            "total_dur": total, "shots": shots,
            "note": "确定性路径：只切分 + 字面检出，检出不到的字段进 missing，不猜。"}


_PROMPT = (
    "你是影视分镜师。把下面这段剧本拆成镜头，**只输出 JSON**，不要解释、不要 markdown 代码块。\n"
    "JSON 形如：{\"total_dur\": 15.0, \"shots\": [{\"idx\":1, \"t0\":0, \"t1\":3, \"dur\":3.0, "
    "\"title\":\"…\", \"shot_size\":\"景别\", \"camera\":\"运镜\", \"emotion\":\"情绪\", "
    "\"subject\":\"角色在画面里的位置\", \"desc\":\"画面内容\", \"dialogue\":\"台词，没有就空串\"}]}\n"
    "硬要求：① 每镜必须有 shot_size/camera/emotion/subject/desc/dur 六项，"
    "推不出来就写空串，**不许编**；② 各镜 dur 之和必须等于 total_dur；③ 景别用中文（大特写/特写/近景/中景/全景/远景）。\n\n"
    "剧本：\n"
)


def split(text: str, model: str | None = None, timeout: int = 120) -> dict:
    """语义路径：交给她的模型通道补景别/运镜/情绪；输出仍过同一套校验（R1-R4）。"""
    raw = str(text or "")
    if len(raw.strip()) < _MIN_CHARS:
        return {"ok": False, "error": "输入过短，拒绝编造分镜（R4）",
                "source": "llm", "chars": len(raw.strip())}
    try:
        # 统一大模型口（Owner 2026-09-19）：模块只管提示词与字段契约，不碰通道。
        from .llm import unified as LLM
        r = LLM.ask(_PROMPT + raw, system="你是严谨的影视分镜师，只输出 JSON。",
                    model=model, temperature=0.3, max_tokens=3000, timeout=timeout,
                    purpose="drama.storyboard")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200], "source": "llm"}
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "模型调用失败"), "source": "llm"}
    reply = str(r.get("reply") or "").strip()
    # 模型爱包代码块：剥壳，但**不修内容**——修不了就如实报，不伪造成功。
    body = reply
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\s*", "", body)
        body = re.sub(r"\s*```$", "", body)
    try:
        data = json.loads(body)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": "llm", "provider": r.get("provider"),
                "model": r.get("model"), "error": f"模型输出不是合法 JSON: {exc}",
                "raw_head": reply[:400]}
    if not isinstance(data, dict) or not isinstance(data.get("shots"), list) or not data["shots"]:
        return {"ok": False, "source": "llm", "error": "模型输出缺 shots 数组",
                "raw_head": reply[:400]}
    shots = []
    for i, sh in enumerate(data["shots"], 1):
        if not isinstance(sh, dict):
            continue
        shots.append({
            "idx": int(sh.get("idx") or i),
            "t0": sh.get("t0"), "t1": sh.get("t1"),
            "dur": None if sh.get("dur") in (None, "") else float(sh["dur"]),
            "title": str(sh.get("title") or ""),
            "shot_size": str(sh.get("shot_size") or "").strip(),
            "camera": str(sh.get("camera") or "").strip(),
            "emotion": str(sh.get("emotion") or "").strip(),
            "subject": str(sh.get("subject") or "").strip(),
            "desc": str(sh.get("desc") or "").strip(),
            "dialogue": str(sh.get("dialogue") or "").strip(),
        })
    total = data.get("total_dur")
    return {"ok": True, "source": "llm", "provider": r.get("provider"), "model": r.get("model"),
            "verdict": _validate(shots, float(total) if total not in (None, "") else None),
            "total_dur": total, "shots": shots,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def run(op: str = "status", **kw) -> dict:
    """能力入口（caps_registry: drama）。"""
    op = str(op or "status").strip().lower()
    # 动作自述（Owner 2026-09-19：他们全都得知道自己这么做）——
    # 我是谁 / 我在链上哪一步 / 我产出了什么，随每次调用落账并随返回体带出。
    from .chain import declare

    def _declared(res: dict, action: str, output=None, note: str = "") -> dict:
        res["declaration"] = declare("drama", action, output=output,
                                     ok=bool(res.get("ok")), note=note)
        return res

    if op == "status":
        return _declared({"ok": True, "module": "模块1 剧本理解引擎（接口1 剧本→分镜）",
                "ops": ["parse_timed", "split", "status"],
                "required_fields": [_FIELD_CN[f] for f in REQUIRED],
                "criteria": ["R1 六字段齐全", "R2 缺字段进 missing 不补默认值",
                             "R3 时长和=总时长(±0.05s)", "R4 过短输入拒绝",
                             "R5 确定性路径不调外网"],
                "paths": {"parse_timed": "确定性·离线·只切分与字面检出",
                          "split": "模型语义·补景别/运镜/情绪·同一套校验"}}, "status")
    if op in ("parse_timed", "timed"):
        res = parse_timed(kw.get("text") or kw.get("script") or "")
        return _declared(res, "parse_timed",
                         output={"shots": len(res.get("shots") or [])},
                         note="确定性切分（离线）")
    if op in ("split", "storyboard", "script"):
        res = split(kw.get("text") or kw.get("script") or "", model=kw.get("model"))
        return _declared(res, "split", output={"shots": len(res.get("shots") or [])},
                         note=f"语义路径（{res.get('provider')}/{res.get('model')}）")
    return {"ok": False, "error": f"未知动作: {op}（可用 parse_timed / split / status）"}
