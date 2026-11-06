# -*- coding: utf-8 -*-
"""commission —— 交办单：人是怎么「交代」一件事的。

为什么要有这一层（2026-11-06）
------------------------------
本机是 4.8G 权重在 16G 机器上跑，p50 一次对话 20 秒级；算子闸门把 427 个位压到
几个只要 10ms。差距不在「懂不懂」，在**人说话本来就不说全**：

    省略   「把那个发一下」        → 靠指代锚点
    默认   「照上次那样」          → 靠习惯沉淀
    纠偏   「不对，左边那个」      → 靠增量修正
    验收   「就这样」              → 靠收尾判据

这四件事都是**状态**，不是智力。小模型记不住也推不出，但把它显式写出来，
模型至少知道「哪一件他没说」—— 该问就问，不该问就别问（空问率是「烦人度」第一指标）。

本模块**不生成动作、不调模型、不写任何能力位契约**，只做三件事：
  ① `parse()`  口语 → {kind, goal, object, constraints, accept, fallback, missing, ask}
  ② `note()`   压成一行（≤120 字）塞进 prompt
  ③ `record()` 落 `state/commission-log.jsonl`，供以后算「空问率 / 该问没问率」

原则：**宁可少填，不许瞎填**。抽不出来就是空，`missing` 里如实列。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "commission-log.jsonl"

# 「帮我 / 麻烦你 / 小土豆」这类客气话不影响交办内容，先剥掉再判断。
_POLITE = re.compile(r"^\s*(?:小土豆|土豆)?\s*(?:帮我|帮忙|给我|麻烦你?|请你?|替我)\s*[，,、\s]*")
_QUESTION_END = re.compile(r"[吗呢嘛]\s*[?？]?\s*$|[?？]\s*$")
_QUESTION_HEAD = re.compile(r"^\s*(?:是否|能不能|可不可以|会不会|有没有|要不要|什么是|为什么|怎么|如何|哪(?:个|些))")
# 及物动词：有它却没说对象，才是「缺对象」；不及物/状态类不算。
_TRANSITIVE = re.compile(
    r"(打开|关闭|关掉|删除|删掉|复制|拷贝|移动|改名|重命名|导出|发送|发一下|传给|生成|渲染|"
    r"剪辑|切开|切片|合并|拼接|上传|下载|安装|卸载|运行|执行|启动|停止|改成|换成|调到|加到|放到|"
    r"写进|写进|贴到|填进|转成|压成|拆成)")
_OBJ = [
    re.compile(r"(?:把|将)\s*([^\s，,。；;：:]{1,20})"),
    re.compile(r"(?:对|给|在|从)\s*([^\s，,。；;：:]{1,20})"),
    re.compile(r"(这个|那个|这张|那张|这段|那段|这条|那条|这份|那份)([^\s，,。；;：:]{0,10})"),
]
# 「把 X 导出成」里 X 只到名词为止：抽到 把/将 后面的串常常连着动词，
# 不切掉就会得到「对象：那段视频导出成」这种假对象（2026-11-06 实测）。
_OBJ_TAIL = re.compile(
    r"(导出|发给|发送|生成|渲染|剪辑|切开|切片|合并|拼接|上传|下载|打开|关闭|删除|复制|"
    r"移动|转成|压成|拆成|验收|检查|改成|换成|调到|加到|放到|写进|填进|跑一下|弄一下).*$")
_CONSTRAINT = re.compile(
    r"(\d{3,4}\s*[x×]\s*\d{3,4}|\d+(?:\.\d+)?\s*(?:秒|s|分钟|min|帧|fps|个|张|条|字|字/秒)"
    r"|\d+\s*[:：]\s*\d+|竖屏|横屏|4K|1080p|720p"
    r"|[A-Za-z]:\\[^\s，,。]+|\.(?:mp4|mov|mkv|ass|srt|wav|mp3|json|png|jpg)\b)")
_ACCEPT = re.compile(r"(过线|合格|验收|检查|核对|确认|对不对|行不行|看看有没有问题|别翻车)")
_FALLBACK = re.compile(r"(不行就|不合格就|不对就|不满意就|否则|退而|兜底|备选|fallback|实在不行|宁可)")
# 疑问模态：出现在句子中间也算问句（「这个能不能过线」）。
# 判错的代价不对称：把问句当任务 ⇒ 模型被塞一句「要办：…」（更坏）；
# 把任务当问句 ⇒ 只是少一句提示（无害）。所以这里**偏向判成问句**。
_MODAL_Q = re.compile(r"(能不能|可不可以|会不会|是否有|有没有|是否|算不算|值不值得)")
_ASK = {"object": "说的是哪个？", "constraints": "要什么规格？"}


def parse(text: str) -> dict:
    raw = str(text or "").strip()
    body = _POLITE.sub("", raw)
    if (_QUESTION_END.search(body) or _QUESTION_HEAD.search(body)
            or (_MODAL_Q.search(body) and not _TRANSITIVE.match(body))):
        kind = "question"
    else:
        kind = "task" if body else "empty"
    obj = ""
    for pat in _OBJ:
        m = pat.search(body)
        if m:
            obj = "".join(g for g in m.groups() if g).strip()
            obj = _OBJ_TAIL.sub("", obj).strip(" 的，,。")
            break
    constraints = [c.strip() for c in _CONSTRAINT.findall(body)]
    out = {
        "ok": True, "status": "ok", "text": raw, "kind": kind,
        "goal": body[:40],
        "object": obj,
        "constraints": constraints,
        "accept": bool(_ACCEPT.search(body)),
        "fallback": bool(_FALLBACK.search(body)),
        "missing": [],
    }
    if kind == "task" and not obj and _TRANSITIVE.search(body):
        out["missing"].append("object")
    out["ask"] = _ASK.get(out["missing"][0], "") if out["missing"] else ""
    out["complete"] = not out["missing"]
    return out


def note(parsed: dict, max_chars: int = 120) -> str:
    """压成一行塞进 prompt。只在**有信息**时给，什么都不缺就返回空串（不占 token）。"""
    if not parsed or parsed.get("kind") != "task":
        return ""
    bits = []
    if parsed.get("goal"):
        bits.append("要办：" + str(parsed["goal"])[:32])
    if parsed.get("object") and str(parsed["object"]) not in str(parsed.get("goal") or ""):
        bits.append("对象：" + str(parsed["object"])[:16])
    if parsed.get("constraints"):
        bits.append("规格：" + " / ".join(parsed["constraints"][:3]))
    if parsed.get("missing"):
        names = {"object": "对象"}.get(parsed["missing"][0], parsed["missing"][0])
        bits.append("他没说：" + names + "（只问这一件，别追问别的）")
    elif parsed.get("accept"):
        bits.append("他要验收")
    if not bits:
        return ""
    line = "（交办单：%s。）" % "；".join(bits)
    if len(line) > max_chars:
        line = line[:max_chars - 1] + "）"
    return line


def record(parsed: dict, gate=None, outcome: str = "", dry: bool = False) -> dict:
    """落账。**只追加、只吞异常** —— 记账绝不许弄坏一次真对话。"""
    if dry:
        return {"ok": True, "recorded": False, "reason": "dry"}
    row = {
        "ts": round(time.time(), 3),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "kind": (parsed or {}).get("kind"),
        "goal": (parsed or {}).get("goal"),
        "object": (parsed or {}).get("object"),
        "constraints": (parsed or {}).get("constraints"),
        "missing": (parsed or {}).get("missing"),
        "accepted": (parsed or {}).get("accept"),
        "cap": ((gate or {}).get("top") or [{}])[0].get("cap") if gate else None,
        "hit": bool((gate or {}).get("hit")) if gate else None,
        "outcome": outcome,
    }
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"ok": True, "recorded": True, "path": str(LEDGER)}
    except Exception as exc:                             # noqa: BLE001
        return {"ok": False, "recorded": False, "error": type(exc).__name__}


def stats(path=None) -> dict:
    p = Path(path) if path else LEDGER
    if not p.is_file():
        return {"ok": True, "total": 0, "path": str(p),
                "note": "还没有数据：聊过天才积累"}
    kinds, missing, caps = {}, 0, {}
    total = 0
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:                            # noqa: BLE001
                continue
            total += 1
            kinds[r.get("kind") or "?"] = kinds.get(r.get("kind") or "?", 0) + 1
            if r.get("missing"):
                missing += 1
            if r.get("cap"):
                caps[r["cap"]] = caps.get(r["cap"], 0) + 1
    except Exception as exc:                             # noqa: BLE001
        return {"ok": False, "status": "failed", "error": type(exc).__name__}
    tasks = kinds.get("task", 0)
    return {"ok": True, "total": total, "kinds": kinds, "path": str(p),
            "missing_pct": round(100.0 * missing / tasks, 1) if tasks else None,
            "top_caps": sorted(caps.items(), key=lambda kv: -kv[1])[:5],
            "note": ("missing_pct = 交办里「缺对象」的占比；它是「该问就问」的分母，"
                     "不是越高越好 —— 高说明人话本来就省，模型别把省略当空白")}


def schema() -> dict:
    return {"ok": True, "status": "ok", "ops": ["schema", "parse", "note", "stats", "recent"],
            "fields": ["kind", "goal", "object", "constraints", "accept", "fallback",
                       "missing", "ask"],
            "states": ["ok", "failed", "needs_input"],
            "note": "只解析不执行：本模块没有动作面，谁也别指望它有副作用"}


def recent(n: int = 5, path=None) -> dict:
    p = Path(path) if path else LEDGER
    if not p.is_file():
        return {"ok": True, "rows": [], "note": "还没有数据"}
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, int(n)):]:
        try:
            rows.append(json.loads(line))
        except Exception:                                # noqa: BLE001
            continue
    return {"ok": True, "rows": rows, "path": str(p)}


def run(op: str = "schema", **kw) -> dict:
    op = str(op or "schema").strip().lower()
    if op in ("schema", "help", ""):
        return schema()
    if op == "parse":
        if not str(kw.get("text") or "").strip():
            return {"ok": False, "status": "needs_input", "missing": "text"}
        return parse(kw["text"])
    if op == "note":
        return {"ok": True, "note": note(parse(kw.get("text") or ""))}
    if op == "stats":
        return stats(kw.get("path"))
    if op == "recent":
        return recent(kw.get("n") or 5, kw.get("path"))
    return {"ok": False, "status": "failed", "detail": "不认的 op：%s" % op}
