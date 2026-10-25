# gbt-capability: gods_eye
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""上帝之眼（gods_eye）· 主人令 2026-09-27，**分工口径 2026-09-28 更新**。

主人原话（2026-09-27）：「**上帝之眼是能看到创作页面这些**，毕竟上帝之眼里面的**克劳德**是要给意见
和建议、商量项目架构和方向指引；把 **CodeBuddy 也部署进上帝之眼，让他做杂事，主项目她没有执行权**，
只有服从安排和随时候命；以及**每日的 GBT 探针汇报**和**每日全量扫描框架**指出**缺点、短板、卡点**；
然后你自己跟克劳德在上帝之眼里面**计划优化和提升整体实力**。」

主人原话（2026-09-28）：「把 **Jev 的推理模型**接入上帝之眼来做决策，设计好**要以 Jev 来做决策**，
克劳德给意见和建议以及可以商量，这么来好了之后**由 Jev 做决策**，**Codex 专注编程**，
**DeepSeek Harness 专注执行层**。」

## 四块职责（与主人原话一一对应；**决策口径以 2026-09-28 那条为准**）
  ① **眼睛**（`see`）：看得见**创作页面**（7 个面板）+ 活着的服务（端口在听）；
  ② **四岗分工**（`roles`）—— 写成**机器可读**的表，不是口头分工：
     · **Jev（推理模型）**：**拍板**。快慢双脑（与 `tools/control_loop.py` 同一套 Jev 协议）：
       快脑出候选+置信度 → 不够才升慢脑 → 慢脑没有/回话解析不出候选 ⇒ **挂起**（绝不硬猜）；
       **不许无证据拍板**（`evidence` 必给；证据不在盘上直接拒）；
     · **Claude**：只出**意见与建议**（架构 · 方向 · 评审）+ **可商量**；**不许决策**；
     · **Codex**：**专注编程**（`codex_chat` / `codex_turn_send`，并发 1）；
     · **DeepSeek Harness**：**专注执行层**（`llm_chat` 的 DeepSeek 密钥链 + `brain_execute`）；
     · **主体**（GBT小土豆V8）：编排、留痕、兜底 —— **Jev 挂起时决策也挂起**（不许谁替它拍）。
  ③ **每日汇报**（`daily`）：**GBT 探针汇报** + **全量扫描** ⇒ 出三张清单：**缺点 / 短板 / 卡点**，
     每条都带**来源读数**（不许编）；`plan` 用来把"提升整体实力"落成可追踪的提案与决策。
  ④ **决策留痕**（`decide` → `state/gods_eye_decisions.jsonl`）：一次写入不回改，含证据与所走路径。

ops：
  see                         眼睛：创作页面 + 服务端口（实测在不在听）
  advisors                    两位顾问的权限表（机器可读）+ 当前可用性
  ask advisor=claude|codebuddy text=...   真咨询（过各自能力位；CodeBuddy 走权限校验）
  daily                       每日汇报：探针 + 全量扫描 ⇒ 缺点/短板/卡点（每条带来源）
  roles                       四岗分工（机器可读）：Jev 决策 / 克劳德意见建议 / Codex 编程 / DeepSeek 执行层
  decide question/options/evidence  **Jev 拍板**：先看→快脑→（不够）慢脑→或者挂起（留痕 state/gods_eye_decisions.jsonl）
  plan op=add|list|decide ...  优化计划面（提案 + 采纳/搁置，留痕 state/gods_eye_plan.jsonl）
  panel                       上帝之眼页面（我们视觉语言 · 快照内联）
"""
from __future__ import annotations

import json
import os
import re                      # 🔴 2026-10-01 补：`_slow_brain` 用 `re.search` 解析候选编号，
                              # 而这个 import 一直缺着 —— 以前每次都先卡在"慢脑调不动（缺授权）"
                              # 就 return 了，**这段代码从来没被执行到**；票一发、云脑一接上，
                              # 才当场暴露 `name 're' is not defined`。
                              # 教训：**被前置条件挡住的代码 = 从没验过的代码**（同"接上了用不了"一族）。
import socket
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_PLAN = _STATE / "gods_eye_plan.jsonl"
_SNAP = _STATE / "gods_eye.json"
_PANEL = _ROOT / "holo_pet" / "assets" / "godview" / "index.html"
_PROBE_WS = Path(r"C:\Users\ADMIN\Desktop\GBT探针")

# 创作页面（眼睛要看得见的那些）+ 服务端口
CREATION_PAGES = [
    ("console3d", "3D 大脑执行层（172+ 能力位球面 / run_task 脉冲流）"),
    ("automation", "三套自动化闭环（音乐试听 / 短视频试看 / 电影分幕）"),
    ("structure", "框架结构浏览器（三栏）"),
    ("godview", "上帝之眼（本页）"),
    ("health-panel", "健康面板（安全棒读数 · 异常报警）"),
    ("task-manager", "任务管理器（真进程 · 归属/内存/CPU/端口）"),
    ("music", "音乐线面板"),
]
PORTS = [(31415, "FreeLLMAPI（免费算力池）"), (8188, "ComfyUI（本地生图/生视频）"),
         (31717, "capability_gateway（能力网关）"), (8111, "mock-vllm（本地替身）")]

# **顾问权限表**（机器可读；主人原话逐条对上）
ADVISORS = {
    "claude": {
        "role": "意见建议（架构 · 方向 · 评审）",
        "may": ["出意见", "出建议", "评审与挑刺", "商量架构与方向"],
        "may_not": ["决策（决策权在主体）", "直接改主项目"],
        "capability": "claude_code",
        "must_install": "npm i -g @anthropic-ai/claude-code",
    },
    "codebuddy": {
        "role": "杂事（服从安排 · 随时候命）",
        "may": ["杂事：路径排查", "日志整理", "取数/搜索", "跑腿"],
        "may_not": ["对主项目有执行权", "决策", "改主项目文件"],
        "capability": "codebuddy",
        "main_project_paths": ["projects/", "gbt_allinone/", "skills/", "tools/", "state/"],
    },
}
# ═══════════════════════ 分工（主人令 2026-09-28）═══════════════════════
# 主人原话：「把 Jev 的推理模型接入上帝之眼来做决策，设计好**要以 Jev 来做决策**，
#   克劳德给意见和建议以及可以商量，这么来好了之后**由 Jev 做决策**，
#   **Codex 专注编程**，**DeepSeek Harness 专注执行层**。」
#
# 四岗**机器可读**（不是口头分工）：谁可以干什么、谁不许干什么，都写成表，
# 判据逐条查（`test_gods_eye` A/F/G）。
ROLES = {
    "jev": {
        "role": "决策（拍板）",
        "may": ["拍板", "裁决", "在候选里选一个", "否掉不成熟的提案", "定优先级"],
        "may_not": ["绕过授权门", "**无证据拍板**", "自己动手执行", "替编程/执行层干活"],
        "how": "快慢双脑（蒸馏自 Jev/TypeSafe System One）：快脑出候选+置信度；"
               "置信度不够才升慢脑；慢脑没有或回话解析不出候选 ⇒ **挂起**，绝不硬猜",
        "protocol": "tools/control_loop.py（同一套 Jev 协议：枚举动作 · 两查 · DONE 要独立验证）",
        "probe": None,          # 本地协议：在位与否看模块文件（下面 _role_probe 里查）
        "slow_brain": ["llm_chat（DeepSeek/Kimi/OpenAI 密钥链）", "local_brain（本地模型）"],
    },
    "claude": {
        "role": "意见建议 + 商量（不给决策）",
        "may": ["出意见", "出建议", "评审与挑刺", "商量架构与方向"],
        "may_not": ["决策（拍板是 Jev 的活）", "直接改主项目"],
        "capability": "claude_code",
        "probe": {"kind": "claude_code", "op": "status"},   # 只读（真查 PATH），不消耗
        "must_install": "npm i -g @anthropic-ai/claude-code",
    },
    "codex": {
        "role": "专注编程",
        "may": ["写码", "改码", "重构", "评审代码", "跑测试"],
        "may_not": ["决策（拍板是 Jev 的活）", "跳过判据直接改生产"],
        "capability": "codex_chat",
        # ⚠️ 探针用 codex_status（**只读**）：拿 codex_chat 的 status 会被门拒（它要 process_execute），
        #   那会探出"没有读数"，而不是"不可用" —— 两件事必须分清。
        "probe": {"kind": "codex_status", "op": "status"},
        "how": "codex_chat（同步对话）/ codex_turn_send（回合并流式回传）· 并发上限 1，需 process_execute+external_llm",
    },
    "deepseek": {
        "role": "专注执行层（DeepSeek Harness）",
        "may": ["执行动作", "跑链", "调能力位落地", "批量作业"],
        "may_not": ["决策（拍板是 Jev 的活）", "自作主张改方向"],
        "capability": "llm_chat",
        # DeepSeek 的可用性 = **密钥槽在不在位**（只读）：问 automation_keys 的 deepseek 槽。
        "probe": {"kind": "automation_keys", "op": "status"},
        "how": "llm_chat 的 DeepSeek 密钥链（automation_keys 的 deepseek 槽）+ 大脑执行层 brain_execute",
    },
}
DECIDER = ("**Jev（推理模型）拍板** —— 意见与建议来自克劳德（可商量）；"
           "Codex 专注编程；DeepSeek Harness 专注执行层；主体（GBT小土豆V8）负责编排、留痕与兜底。"
           "Jev 挂起时**决策也挂起**（不许谁替它拍）")

DECIDE_THRESHOLD = 0.6            # 快脑置信度低于此值 ⇒ 升慢脑；没有慢脑 ⇒ 挂起
DECIDE_MAX_PER_MIN = 6            # 预算闸：每分钟决策上限（对着 control_loop 的成本口径自设）


def _port_open(p: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.35)
        return s.connect_ex(("127.0.0.1", p)) == 0


def _gate(kind: str, payload: dict) -> dict:
    sys.path.insert(0, str(_ROOT))
    import gbt_allinone as g
    r = g.run_task(kind, payload)
    d = r.get("result") if isinstance(r, dict) else None
    while isinstance(d, dict) and isinstance(d.get("result"), dict) and set(d) <= {"status", "kind", "result", "ok"}:
        d = d["result"]
    return {"gate_ok": bool(isinstance(r, dict) and r.get("ok", True)), "payload": d or {}}


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def _log(row: dict) -> None:
    _PLAN.parent.mkdir(parents=True, exist_ok=True)
    with open(_PLAN, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def see(**_kw) -> dict:
    """眼睛：创作页面（在不在）+ 服务（端口在不在听）。

    ⚠️ 2026-09-28 改口径：页面清单**不再自带** —— 改为读 `console_hub.pages`（**单一真相**）。
    血账：这里原来自带一个 7 页硬清单，而盘上其实有 **20 个独立页**（扫描抓到的：总入口 · 三方向自动化面板 ·
    仙侠皮肤预览 · V22 可交互原型/无限画布 · 本轮新建的工作台/3D 全景/四条工作流页）
    —— **各维护一份清单 = 必然看不见新增的页**。`console_hub` 读不到时退回自带清单（fail-soft，但如实标退路）。
    """
    pages, src = [], ""
    rows = (_gate("console_hub", {"op": "pages"}).get("payload") or {}).get("rows") or []
    if rows:
        src = "console_hub.pages（单一真相）"
        for r in rows:
            pages.append({"page": r.get("page"), "why": r.get("what"), "kind": r.get("kind"),
                          "workflow": r.get("workflow"), "exists": bool(r.get("exists")),
                          "kb": r.get("kb"), "open": r.get("path")})
    else:
        src = "退路：gods_eye 自带 7 页清单（console_hub 读不到）"
        for name, why in CREATION_PAGES:
            p = _ROOT / "holo_pet" / "assets" / name / "index.html"
            pages.append({"page": name, "why": why, "exists": p.is_file(),
                          "kb": round(p.stat().st_size / 1024, 1) if p.is_file() else 0,
                          "open": f"holo_pet/assets/{name}/index.html"})
    services = [{"port": p, "what": w, "listening": _port_open(p)} for p, w in PORTS]
    return {"ok": True, "op": "see", "pages": pages, "pages_source": src,
            "pages_ok": sum(1 for x in pages if x["exists"]), "pages_total": len(pages),
            "services": services, "services_up": sum(1 for x in services if x["listening"]),
            "_口径": "页面=真读文件（清单来自 console_hub 单一真相）；服务=真连一次端口"}


def advisors(**_kw) -> dict:
    """两位顾问的权限表 + 当前可用性（过各自能力位实测）。"""
    out = {}
    for name, spec in ADVISORS.items():
        st = _gate(spec["capability"], {"op": "status"})
        d = st.get("payload") or {}
        avail = bool(d.get("available")) if name == "claude" else bool(d.get("found"))
        out[name] = {**spec, "available": avail,
                     "evidence": (d.get("install_hint") if name == "claude" and not avail
                                  else (d.get("found") or [{}])[0].get("path") if isinstance(d.get("found"), list) and d.get("found") else str(d)[:120])}
    return {"ok": True, "op": "advisors", "advisors": out, "decider": DECIDER,
            "_口径": "**权限是机器可读的表**（may / may_not）；可用性过各自能力位实测，不猜"}


def _ask_payload(text: str, timeout: int = 0) -> dict:
    """给到底层 CLI 智能体（`cli_agents.run`）的载荷。

    ⚠️ **血账（2026-09-27 实测）**：`cli_agents.run` 认的是 **`prompt` / `q`** 两个键，
    而这里早先只传了 `text=` —— 结果是**即使拿到了授权也只会回「缺少 prompt」**：
    表面接通、实际永远得不到意见（就是"接上了用不了"那一类）。所以 `text` 与 `prompt`
    **一起传**，谁认哪个都能通；这个函数单独存在，就是为了让判据能直接盯住这个键。
    """
    p = {"op": "ask", "text": text, "prompt": text}
    if timeout:
        p["timeout"] = int(timeout)
    return p


def ask(advisor: str = "", text: str = "", timeout: int = 0, **_kw) -> dict:
    """真咨询：过顾问自己的能力位。**CodeBuddy 走权限校验**（主项目路径一律拒）。"""
    a = (advisor or "").lower()
    if a not in ADVISORS:
        return {"ok": False, "fail_closed": True, "error": f"顾问只有 {sorted(ADVISORS)}"}
    if not text.strip():
        return {"ok": False, "fail_closed": True, "error": "text 不能为空"}
    low = text.replace("\\", "/").lower()
    if a == "codebuddy":
        hit = [p for p in ADVISORS[a]["main_project_paths"] if p in low]
        if hit:
            return {"ok": False, "refused": True, "advisor": a, "hit": hit,
                    "why": "CodeBuddy **对主项目没有执行权**（主人令）：它只做杂事、服从安排、随时候命",
                    "how_to": "把它要碰的主项目动作交回主体（我）来做；派给它的活请只涉杂事"}
    if a == "claude":
        st = _gate("claude_code", {"op": "status"})
        if not (st.get("payload") or {}).get("available"):
            return {"ok": False, "advisor": a, "available": False,
                    "why": "Claude Code CLI 未安装 ⇒ 咨询不了（如实报，不假装）",
                    "how_to": ADVISORS[a]["must_install"]}
    d = _gate(ADVISORS[a]["capability"], _ask_payload(text, timeout))
    pay = d.get("payload")
    _log({"event": "ask", "advisor": a, "chars": len(text), "ok": d.get("gate_ok")})
    # **被门拒 ≠ 顾问答了**：拒了就不许把拒绝理由塞进 `answer` 冒充"意见"。
    if isinstance(pay, dict) and pay.get("denied"):
        return {"ok": False, "op": "ask", "advisor": a, "denied": True,
                "why": pay.get("reason") or "该顾问需要人工授权",
                "scopes": pay.get("scopes") or [], "missing": pay.get("missing") or [],
                "how_to": pay.get("how_to_grant") or [],
                "note": "授权只能**主人在终端**发放；AI 无权自批（我不会去自批）"}
    return {"ok": d.get("gate_ok"), "op": "ask", "advisor": a, "answer": str(pay)[:800],
            "note": "顾问只出意见/杂事；**决策权在主体**"}


_DECISIONS = _STATE / "gods_eye_decisions.jsonl"
_RISK_WORDS = ("删除", "清空", "上线", "发布", "推送", "改生产", "回滚", "清库", "覆盖生产")


def _log_decision(row: dict) -> None:
    _DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(_DECISIONS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _decide_budget() -> dict:
    """预算闸：每分钟决策上限（照 control_loop 的成本口径，我们记自己的账）。"""
    now = time.time()
    n = 0
    if _DECISIONS.is_file():
        for ln in _DECISIONS.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            ts = r.get("ts") or 0
            if now - float(ts) < 60:
                n += 1
    return {"ok": n < DECIDE_MAX_PER_MIN, "last_min": n, "limit": DECIDE_MAX_PER_MIN}


def _fast_judge(options: list, readings: dict) -> dict:
    """**快脑**：候选 + 置信度（确定性地从读数推，**不装成模型**）。

    打分三件事（都可复核）：
      ① 候选压在**最短板**上（读数里 weight 高的条目）—— 对上高分；
      ② 候选带**风险词**（上线/删除/改生产…）—— 扣分；
      ③ 候选里有**读数字样**（命中短板条目里的词）—— 加分。
    置信度 = 头名与次名差距归一；**差距接近 0（选不出）就是低置信** ⇒ 该升慢脑。
    """
    tops = (readings.get("shortboard_top") or [])
    dims = {str(x.get("dim") or ""): float(x.get("weight") or 0) for x in tops}
    words = set()
    for x in tops:
        for w in str(x.get("what") or "").replace("：", " ").replace("，", " ").split():
            w = w.strip("：:（）()【】[]，,。")
            if len(w) >= 2:
                words.add(w)
    # 🔴 2026-10-01 第 63 轮：**条目自己的话也算读数**。
    # 实测（永动机第一轮）：本机 `growth_hooks` 的短板读数不在盘上 ⇒ `tops` 空 ⇒ 每个候选都打 0 分、
    # gap=0、置信度恒 0.5 < 阈值 0.6 ⇒ **每条卡点都升慢脑，而慢脑又不可用 ⇒ 全挂**，回路空转。
    # 把条目文本并进 `words` 之后，"候选词面与条目对得上"的那个就能赢 —— 这仍然是**确定性**打分
    # （可复算、每条命中都在 `命中读数` 里列出来），不是模型输出，也不假装是。
    for w in str(readings.get("item_text") or "").replace("：", " ").replace("，", " ").replace("（", " ").replace("）", " ").split():
        w = w.strip("：:（）()【】[]，,。")
        if len(w) >= 2:
            words.add(w)
    scores, why = [], []
    for o in options:
        s = 0.0
        for d, w in dims.items():
            if d and d in o:
                s += w / 100.0
        hit = [w for w in words if w and w in o]
        s += 0.15 * len(hit)
        risk = [r for r in _RISK_WORDS if r in o]
        s -= 0.5 * len(risk)
        scores.append(s)
        why.append({"option": o[:60], "score": round(s, 3), "命中读数": hit[:4], "风险词": risk})
    order = sorted(range(len(options)), key=lambda i: -scores[i])
    best = options[order[0]] if options else ""
    gap = (scores[order[0]] - scores[order[1]]) if len(scores) > 1 else (scores[0] if scores else 0)
    conf = max(0.0, min(0.95, 0.5 + gap)) if options else 0.0
    return {"choice": best, "confidence": round(conf, 3), "scores": why,
            "_口径": "确定性打分（短板权重 + 读数命中 + 风险词扣分）；**不是模型输出，不装成模型**"}

def _slow_brain(question: str, options: list, readings: dict) -> dict:
    """**慢脑**：真问一次对话模型（过 llm_chat 的门）。回话解析不出候选 ⇒ 按 Jev 规矩挂起。"""
    opts = " / ".join("[%d] %s" % (i + 1, o) for i, o in enumerate(options))
    prompt = ("你是决策辅助。只回一个编号，不要解释。\n问题：%s\n候选：%s\n读数：%s"
              % (question[:400], opts, str(readings)[:600]))
    r = _gate("llm_chat", {"op": "chat", "prompt": prompt})
    pay = r.get("payload")
    if not r.get("gate_ok"):
        return {"ok": False, "why": "慢脑调不动（多半缺 external_llm 授权）", "raw": str(pay)[:200]}
    txt = str(pay or "")
    m = re.search(r"\[?(\d+)\]?", txt)
    if not m or not (1 <= int(m.group(1)) <= len(options)):
        return {"ok": False, "why": "慢脑回话**解析不出候选** ⇒ 按 Jev 的规矩挂起（宁可 BLOCKED，也不乱选）",
                "raw": txt[:200]}
    return {"ok": True, "choice": options[int(m.group(1)) - 1], "raw": txt[:200]}


def decide(question: str = "", options: str = "", evidence: str = "", **kw) -> dict:
    """**Jev 拍板**：先看（证据）→ 快脑 →（不够就）慢脑 → 或者挂起；全程留痕。

    `options` 逗号分隔；`evidence` 逗号分隔的读数路径（**没有证据不许拍板**）。
    """
    if not question.strip() or not options.strip():
        return {"ok": False, "op": "decide", "fail_closed": True, "error": "question 与 options 都要给"}
    opts = [x.strip() for x in options.split(",") if x.strip()]
    if len(opts) < 2:
        return {"ok": False, "op": "decide", "fail_closed": True, "error": "至少给两个候选（一个候选不叫决策）"}
    # ① 先看：没有证据 = 不拍板
    if not evidence.strip():
        return {"ok": False, "op": "decide", "refused": True, "decider": "Jev（推理模型）",
                "why": "**没有证据不许拍板**（无脑决策比无脑操作更贵）",
                "how": "先把相关读数过一遍，把证据路径填进 evidence"}
    ev = []
    for p in [x.strip() for x in evidence.split(",") if x.strip()]:
        fp = Path(p)
        if not fp.is_absolute():
            fp = _ROOT / p
        ev.append({"path": str(p), "exists": fp.exists(),
                   "age_s": int(time.time() - fp.stat().st_mtime) if fp.exists() else None})
    missing = [e["path"] for e in ev if not e["exists"]]
    if missing:
        return {"ok": False, "op": "decide", "refused": True, "decider": "Jev（推理模型）",
                "why": "证据不在盘上：%s" % missing[:3], "evidence": ev}
    # ② 预算闸
    b = _decide_budget()
    if not b["ok"]:
        return {"ok": False, "op": "decide", "refused": True, "decider": "Jev（推理模型）",
                "why": "预算闸：一分钟内已决策 %d 次（上限 %d）—— 别拿决策刷分"
                       % (b["last_min"], b["limit"]), "budget": b}
    # ③ 快脑 →（不够）慢脑 → 或者挂起
    #    `kw["context"]`（可选）＝**把这一条自己的读数给快脑**（永动机回路用；见 `_fast_judge` 的注释：
    #    没有它，本机短板读数缺席时快脑恒判不出，回路会全挂）。
    readings = {"shortboard_top": _shortboard_top(), "evidence": ev,
                "item_text": str(kw.get("context") or "")}
    fast = _fast_judge(opts, readings)
    path, decision, note = "fast", fast, ""
    if fast["confidence"] < DECIDE_THRESHOLD:
        slow = _slow_brain(question, opts, readings)
        if slow.get("ok"):
            path, decision = "slow", {"choice": slow["choice"], "confidence": None, "scores": fast["scores"]}
            note = "快脑置信度不足 ⇒ 已升慢脑"
        else:
            _log_decision({"ts": time.time(), "event": "decide", "decider": "Jev（推理模型）",
                           "question": question[:200], "options": opts, "path": "blocked",
                           "confidence": fast["confidence"], "why": slow.get("why"), "evidence": ev})
            return {"ok": False, "op": "decide", "blocked": True, "decider": "Jev（推理模型）",
                    "path": "blocked", "fast": fast, "why": slow.get("why"),
                    "how_to_unblock": ["发 external_llm 时段授权让慢脑可问",
                                       "或配本地脑（local_brain）",
                                       "或把问题改成读数能分出高下的形式（补证据）"],
                    "note": "**Jev 挂起 ⇒ 决策挂起**：不许谁替它拍板，也不许硬猜一个"}
    _log_decision({"ts": time.time(), "event": "decide", "decider": "Jev（推理模型）",
                   "question": question[:200], "choice": decision["choice"], "path": path,
                   "confidence": decision.get("confidence"), "evidence": ev, "note": note})
    return {"ok": True, "op": "decide", "decider": "Jev（推理模型）", "question": question[:200],
            "choice": decision["choice"], "path": path, "confidence": decision.get("confidence"),
            "scores": fast["scores"], "evidence": ev, "note": note,
            "_口径": "决策人=**Jev**；克劳德只出意见；主体负责编排与留痕。挂起时不许替拍。"}


def _shortboard_top() -> list:
    try:
        p = _STATE / "shortboard.json"
        if p.is_file():
            return (json.loads(p.read_text(encoding="utf-8")).get("top") or [])
    except (OSError, json.JSONDecodeError):
        pass
    return []


def _role_probe(name: str, spec: dict) -> tuple:
    """某个岗现在到底能不能用 —— **只读探针 + 读不到按不可用（fail-closed）**。

    ⚠️ 血账：第一版写成 `bool(d.get("available", d.get("found", True)))` —— **默认真**。
    而 `codex_chat` / `llm_chat` 的 `status` 会被门拒（它们要 process_execute / external_llm），
    返回里**根本没有 available/found 键** ⇒ 探出"没有读数"，却被默认成了"可用"。
    这正是本仓反复吃的"读不到当成没问题"。⇒ 现在：**读不到一律 False**，并如实写"探针没给读数"。
    """
    if name == "jev":
        # Jev 是本地协议：看协议模块在不在；慢脑能不能问是**另一件事**，一并报出来
        proto = _ROOT / "tools" / "control_loop.py"
        slow = _gate("llm_chat", {"op": "status"})
        slow_ok = bool((slow.get("payload") or {}).get("ok"))
        return bool(proto.is_file()), {
            "快脑协议": str(proto.relative_to(_ROOT)) if proto.is_file() else "缺失",
            "慢脑可问": slow_ok,
            "慢脑读数": "llm_chat.status 有 ok 读数" if slow_ok else "llm_chat.status 没给读数（多半被门拒）",
        }
    pr = spec.get("probe") or {}
    if not pr:
        return False, {"探针": "没配探针 ⇒ 按不可用（fail-closed）"}
    d = _gate(pr["kind"], {"op": pr["op"]}).get("payload") or {}
    if name == "deepseek":
        slots = d.get("slots") or []
        hit = [s for s in slots if s.get("slot") == "deepseek"]
        present = bool(hit and hit[0].get("present"))
        return present, {"密钥槽 deepseek": "在位" if present else "不在位",
                         "来源": "automation_keys.status（只读）"}
    if name == "codex":
        # Codex 的只读读数给的是 codex_path + connected ⇒ 可用性看**装没装**，
        # "连没连上"单独一栏报（装了就可用，没连上只是当前没有会话）
        p_ = str(d.get("codex_path") or "")
        return bool(d.get("ok") and p_), {"探针": "codex_status.status（只读）",
                                          "已装": p_ or "未装", "已连接": bool(d.get("connected"))}
    if not d:
        return False, {"探针": f"{pr['kind']}.{pr['op']} 没给读数（多半被门拒）⇒ 按不可用"}
    avail = bool(d.get("available", d.get("found")))    # **默认 None ⇒ False**
    return avail, {"探针": f"{pr['kind']}.{pr['op']}",
                   "install_hint": str(d.get("install_hint") or "")[:80]}


def roles(**_kw) -> dict:
    """四岗分工（机器可读）：Jev 决策 / 克劳德意见建议 / Codex 编程 / DeepSeek 执行层。"""
    out = {}
    for name, spec in ROLES.items():
        avail, ev = _role_probe(name, spec)
        out[name] = {**spec, "available": bool(avail), "evidence": ev}
    return {"ok": True, "op": "roles", "roles": out, "decider": DECIDER,
            "threshold": DECIDE_THRESHOLD, "budget_per_min": DECIDE_MAX_PER_MIN,
            "_口径": "分工是**机器可读的表**：谁的 may / may_not 都在上面，判据逐条查；"
                     "可用性=**只读探针真读**，读不到一律按不可用（fail-closed，不拿'应该能用'顶替）"}


def _probe_report() -> dict:
    """GBT 探针汇报：读探针工作区最新交付/证据 + 抓取台账尾。"""
    if not _PROBE_WS.is_dir():
        return {"available": False, "why": f"探针工作区不在：{_PROBE_WS}"}
    out = {"available": True, "deliverables": [], "evidence": [], "ledger_tail": ""}
    for sub, key in (("01-交付物", "deliverables"), ("02-证据", "evidence")):
        d = _PROBE_WS / sub
        if d.is_dir():
            for day in sorted(d.iterdir())[-1:]:
                if day.is_dir():
                    out[key] = [x.name for x in sorted(day.iterdir())][-6:]
    lg = _PROBE_WS / "04-调研" / "抓取台账.md"
    if lg.is_file():
        out["ledger_tail"] = "\n".join(lg.read_text(encoding="utf-8", errors="replace").splitlines()[-4:])
    return out


def _auth_status() -> dict:
    """授权门读数（**只读**，不消耗任何一张票）。

    走**包路径**导入（`from gbt_allinone import auth_gate`）—— 直接按文件路径装
    `auth_gate.py` 会因为它的 `from . import _paths` 相对导入而失败；早先这里就是那样
    失败又被吞掉的（这条卡点因此从没出现过）。包路径不通就退回把仓库根塞进 sys.path 再试。
    失败返回 `{}`，由调用方**当卡点报出来**（不静默）。
    """
    for attempt in (0, 1):
        try:
            if attempt:
                sys.path.insert(0, str(_ROOT))
            from gbt_allinone import auth_gate as ag      # noqa: PLC0415
            return ag.status() or {}
        except Exception:                                 # noqa: BLE001
            continue
    return {}


def _scan_findings() -> dict:
    """全量扫描读数 → 缺点/短板/卡点（**每条带来源**）。"""
    health = _load(_STATE / "health.json", {})
    cov = _load(_STATE / "coverage_matrix.json", {})
    full = _load(_STATE / "full_scan.json", {})
    unimpl = _load(_STATE / "unimplemented.json", {"items": []})
    ledger = _load(_STATE / "排查台账.json", {"open_faults": []})
    ak = _gate("automation_keys", {"op": "status"}).get("payload") or {}
    sur = _load(_STATE / "gods_eye.json", {})
    gaps, shorts, blockers = [], [], []

    # 缺点（缺陷类）
    if (health.get("alerts") or []):
        gaps.append({"item": f"安全棒报警 {len(health['alerts'])} 条", "src": "state/health.json"})
    if not cov.get("全绿", True):
        gaps.append({"item": f"覆盖矩阵非全绿（盲区 {len(cov.get('盲区') or [])}）", "src": "state/coverage_matrix.json"})
    if full.get("需人核"):
        gaps.append({"item": f"全树扫描需人核 {len(full['需人核'])} 条", "src": "state/full_scan.json"})
    of = ledger.get("open_faults") or []
    if of:
        gaps.append({"item": f"未清故障 {len(of)} 条（{[f.get('id') for f in of][:5]}）", "src": "state/排查台账.json"})

    # 短板（能力/配置类）
    um = unimpl.get("items") or []
    if um:
        shorts.append({"item": f"未实现登记 {len(um)} 条（{[i.get('kind') for i in um][:4]}）", "src": "state/unimplemented.json"})
    slots = ak.get("slots") or []
    miss_slots = [s["slot"] for s in slots if s.get("present") is False]
    if miss_slots:
        shorts.append({"item": f"密钥槽未就位 {len(miss_slots)} 个（{miss_slots}）", "src": "automation_keys.status"})
    adv = advisors().get("advisors") or {}
    off = [k for k, v in adv.items() if not v.get("available")]
    if off:
        shorts.append({"item": f"顾问位不可用：{off}", "src": "gods_eye.advisors"})
    if health.get("energy", {}).get("free_pool") is False:
        shorts.append({"item": "免费算力池不可达（FreeLLMAPI 未启动）", "src": "state/health.json"})

    # 安全棒健康账（每半天的全量穿透扫描读数就在这）：报警直接进缺点
    sw = _gate("sec_sweeper", {"op": "health"}).get("payload") or {}
    for a in (sw.get("alerts") or [])[:3]:
        gaps.append({"item": f"安全棒报警：{str(a)[:90]}", "src": "sec_sweeper.health"})

    # ── 成长栈四面（主人令 2026-09-27：永久记忆 / 吞天融合 / 标签许可 / 短板）──
    # 在这里读它们，日报才是"框架整体实力"的日报；同时这四个能力位就有了**常设调用者**
    # （判据 `test_caps_called_audit` 专门盯"内调型孤儿"，摆设是不许的）。
    ov = _gate("obsidian_vault", {"op": "status"}).get("payload") or {}
    if ov.get("missing"):
        shorts.append({"item": f"永久记忆没铺满：触手库 {ov.get('vaults')}/{ov.get('tentacles')}"
                               f"（缺 {ov['missing']}）", "src": "obsidian_vault.status"})
    df = _gate("devour_fusion", {"op": "audit"}).get("payload") or {}
    if df.get("not_fused"):
        shorts.append({"item": f"吞入未融合 {df['not_fused']} 条（三件不齐 ⇒ 还不算融合）",
                       "src": "devour_fusion.audit"})
    ct = _gate("cap_tags", {"op": "audit"}).get("payload") or {}
    if ct.get("without_permit"):
        blockers.append({"item": f"主人未许可的 owner 类能力位 {ct['without_permit']} 个（要用时按名单批）",
                         "src": "cap_tags.audit", "how": ct.get("how_to") or
                         "python -m gbt_allinone.tools.cap_tags permit --tag <TAG> --ttl 600"})
    gh = _gate("growth_hooks", {"op": "shortboard"}).get("payload") or {}
    for tp in (gh.get("top") or [])[:2]:
        shorts.append({"item": f"最短板[{tp.get('dim')}] {str(tp.get('what'))[:80]}",
                       "src": tp.get("src") or "growth_hooks.shortboard"})

    # 卡点（阻塞类：要授权 / 缺环境 / 慢）
    # 授权面读数（只读 `auth_gate.status()`，**不消耗**任何授权）。
    # ⚠️ 血账（2026-09-27 实测）：这里原来用 spec_from_file_location 直接装 auth_gate.py，
    # 而它第一行就是 `from . import _paths`（相对导入）⇒ 报 ImportError，又被 `except: pass`
    # 吞掉 ⇒ 这条卡点**从来没出现过**（"接上了没生效"的又一例）。现在：走包路径导入，
    # 且读不到读数时**把它本身当卡点报出来**，不许静默。
    auth_st = _auth_status()
    adv_now = adv or {}
    if not auth_st:
        blockers.append({"item": "授权面读数读不到（auth_gate.status 取不到）⇒ 无法判断现在能干什么",
                         "src": "gbt_allinone/auth_gate.py", "how": "修 _auth_status 的导入路径"})
    else:
        sc = auth_st.get("scopes") or {}
        need = [s for s in ("process_execute", "external_llm")
                if not (sc.get(s) or {}).get("grants_available")]
        if need and (adv_now.get("claude") or {}).get("available"):
            blockers.append({"item": f"顾问（claude）**要授权才能问**：{need} 现在 0 张 ⇒ 意见取不到",
                             "src": "auth_gate.status（只读）",
                             "how": f"python -m gbt_allinone auth grant --scope {need[0]} --ttl 600"})
        elif not need:
            blockers.append({"item": "授权在窗口内（process_execute / external_llm 有票）⇒ 顾问可问、可跑",
                             "src": "auth_gate.status（只读）", "how": "TTL 到点自动失效，用完不必手动撤"})
    st = _gate("comfyui", {"op": "status"}).get("payload") or {}
    if st.get("type") == "cpu":
        blockers.append({"item": f"ComfyUI 跑在 CPU（{st.get('version')}）⇒ 出片慢（不是不能出）",
                         "src": "gods_eye.daily/comfyui.status"})
    return {"缺点": gaps, "短板": shorts, "卡点": blockers, "advisors": adv}


def daily(**_kw) -> dict:
    """每日汇报：探针 + 全量扫描 ⇒ 缺点/短板/卡点（每条带来源）。"""
    probe = _probe_report()
    scan = _scan_findings()
    out = {"ok": True, "op": "daily", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "探针汇报": probe, "全量扫描": {"缺点": scan["缺点"], "短板": scan["短板"], "卡点": scan["卡点"]},
           "计数": {"缺点": len(scan["缺点"]), "短板": len(scan["短板"]), "卡点": len(scan["卡点"]),
                  "探针可用": probe.get("available")},
           "_口径": "每一条都带 `src`（哪个读数文件/哪个能力位）—— **不许编**；探针汇报读的是探针工作区的真文件"}
    # 面板上要看得见**分工**与**最近一次决策**（不然"谁拍板"只在代码里）
    last = []
    if _DECISIONS.is_file():
        for ln in _DECISIONS.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]:
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("event") == "decide":
                last.append({k: r.get(k) for k in ("at", "choice", "path", "decider", "question")})
    _SNAP.write_text(json.dumps({**out, "顾问": scan["advisors"], "分工": ROLES,
                                 "决策人": DECIDER, "最近决策": last[-3:]},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def plan(op: str = "list", item: str = "", src: str = "", decision: str = "", **_kw) -> dict:
    """优化计划面：add（提案，通常来自 Claude 的建议）/ list / decide（采纳 or 搁置，**决策权在主体**）。"""
    op = (op or "list").lower()
    if op == "add":
        if not item.strip():
            return {"ok": False, "fail_closed": True, "error": "item 不能为空"}
        _log({"event": "proposal", "item": item[:300], "src": src[:120], "by": "claude-or-self"})
        return {"ok": True, "op": "plan.add", "item": item[:120], "src": src}
    if op == "decide":
        if decision not in ("采纳", "搁置"):
            return {"ok": False, "fail_closed": True, "error": "decision 必须是 采纳 / 搁置"}
        _log({"event": "decision", "item": item[:300], "decision": decision, "decider": DECIDER})
        return {"ok": True, "op": "plan.decide", "item": item[:120], "decision": decision, "decider": DECIDER}
    rows = []
    if _PLAN.is_file():
        for ln in _PLAN.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return {"ok": True, "op": "plan.list", "count": len(rows), "tail": rows[-12:], "decider": DECIDER}


_PANEL_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>上帝之眼 · GBT小土豆V8</title><style>
 :root{--bg:#080b10;--panel:#101822;--line:#1d2836;--ink:#dfe9f4;--dim:#7d90a6;--cyan:#33c9dc;--orange:#f0a03c;--red:#e5484d;--green:#3fb950;--violet:#a371f7}
 *{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 20% -10%,#0d1723,#080b10);color:var(--ink);font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
 header{padding:20px 24px;border-bottom:1px solid var(--line);display:flex;gap:14px;align-items:center}
 h1{font-size:18px;margin:0;font-weight:600;letter-spacing:.5px}
 .sub{color:var(--dim);font-size:12px}.meta{margin-left:auto;color:var(--dim);font-size:12px}
 .wrap{display:grid;grid-template-columns:1.1fr 1fr;gap:16px;padding:20px 24px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
 .card h2{font-size:13px;margin:0 0 10px;color:var(--dim);font-weight:500;letter-spacing:.6px}
 .item{padding:7px 0;border-top:1px solid var(--line);font-size:13px}
 .item:first-child{border-top:0}
 .src{color:var(--dim);font-size:11px}
 .ok{color:var(--green)}.bad{color:var(--red)}.warn{color:var(--orange)}.adv{color:var(--violet)}
 table{width:100%;border-collapse:collapse}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;font-size:12.5px}
 th{color:var(--dim);font-weight:500}
 footer{padding:14px 24px;color:var(--dim);font-size:12px;border-top:1px solid var(--line)}
</style></head><body>
<header>
 <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#33c9dc" stroke-width="1.6"><path d="M12 5c-5 0-9 4.5-9 7s4 7 9 7 9-4.5 9-7-4-7-9-7z"/><circle cx="12" cy="12" r="3"/></svg>
 <h1>上帝之眼</h1><span class="sub">看得见创作页面 · 两位顾问 · 每日汇报 · 计划与决策</span>
 <span class="meta" id="at">-</span>
</header>
<div class="wrap">
 <div class="card"><h2>创 作 页 面（眼睛能看到）</h2><div id="pages"></div></div>
 <div class="card"><h2>四 岗 分 工 · 谁 拍 板</h2><div id="roles"></div></div>
 <div class="card"><h2>最 近 决 策（Jev）</h2><div id="decisions"></div></div>
 <div class="card"><h2>两 位 顾 问 · 权 限</h2><div id="adv"></div></div>
 <div class="card"><h2>缺 点</h2><div id="gaps"></div></div>
 <div class="card"><h2>短 板 / 卡 点</h2><div id="short"></div><div id="block" style="margin-top:10px"></div></div>
</div>
<footer>口径：每条都带来源（哪个读数文件/哪个能力位）；页面=真读文件，服务=真连端口；**由 Jev 拍板**（克劳德只出意见；Codex 编程；DeepSeek 执行层；主体编排留痕）。</footer>
<script>
const INLINE = __SNAPSHOT__;
const PAGES = __PAGES__;
function li(x){return '<div class="item">'+x+'</div>';}
function render(d){
  document.getElementById('at').textContent = (d && d.at) || '-';
  document.getElementById('pages').innerHTML = (PAGES||[]).map(p=>li(
    '<b>'+p.page+'</b> <span class="'+(p.exists?'ok':'bad')+'">'+(p.exists?'可见':'缺')+'</span> · '+
    '<span class="src">'+p.why+'</span>')).join('') +
    '<div class="item"><span class="src">服务：'+((d&&d.services)||[]).map(s=>s.what.split('（')[0]+(s.listening?' 🟢':' ⚪')).join(' · ')+'</span></div>';
  const R=(d&&d.分工)||{};
  document.getElementById('roles').innerHTML = Object.entries(R).map(([k,v])=>li(
    '<b class="adv">'+k+'</b> <span class="src">'+v.role+'</span><br>'+
    '<span class="src">可：'+(v.may||[]).join(' / ')+'<br>不可：'+(v.may_not||[]).join(' / ')+'</span>')).join('')
    + li('<span class="src">'+(d&&d.决策人||'')+'</span>');
  const D=(d&&d.最近决策)||[];
  document.getElementById('decisions').innerHTML = D.length ? D.map(x=>li(
    '<b>'+(x.path==='blocked'?'⏸ 挂起':'✔ '+(x.choice||'-'))+'</b> <span class="src">'+x.path+'</span><br>'+
    '<span class="src">'+(x.question||'')+'　·　'+x.at+'</span>')).join('')
    : li('<span class="src">还没有决策记录（跑 run_task('gods_eye', {'op':'decide', …})）</span>');
  const A=(d&&d.顾问)||{};
  document.getElementById('adv').innerHTML = Object.entries(A).map(([k,v])=>li(
    '<b class="adv">'+k+'</b> <span class="'+(v.available?'ok':'warn')+'">'+(v.available?'可用':'不可用')+'</span> · '+
    '<span class="src">'+v.role+'</span><br><span class="src">可：'+v.may.join(' / ')+'<br>不可：'+v.may_not.join(' / ')+'</span>')).join('')
    + li('<span class="src">决策：'+(d&&d.decider||'-')+'</span>');
  const S=(d&&d.全量扫描)||{};
  document.getElementById('gaps').innerHTML = ((S.缺点||[]).map(x=>li('<span class="bad">'+x.item+'</span><br><span class="src">'+x.src+'</span>')).join('')) || li('<span class="ok">无</span>');
  document.getElementById('short').innerHTML = ((S.短板||[]).map(x=>li('<span class="warn">'+x.item+'</span><br><span class="src">'+x.src+'</span>')).join('')) || li('<span class="ok">无</span>');
  document.getElementById('block').innerHTML = ((S.卡点||[]).map(x=>li('<span class="bad">'+x.item+'</span><br><span class="src">'+x.src+'</span>')).join(''));
}
render(INLINE);
async function refresh(){try{const r=await fetch('state/gods_eye.json',{cache:'no-store'});render(await r.json());}catch(e){}}
setInterval(refresh, 15000);
</script></body></html>
"""


def panel(**_kw) -> dict:
    snap = _load(_SNAP, {})
    if not snap:
        snap = daily()
    pages = see()["pages"]
    html = _PANEL_HTML.replace("__SNAPSHOT__", json.dumps(snap, ensure_ascii=False)) \
                      .replace("__PAGES__", json.dumps(pages, ensure_ascii=False))
    _PANEL.parent.mkdir(parents=True, exist_ok=True)
    _PANEL.write_text(html, encoding="utf-8")
    return {"ok": True, "op": "panel", "path": str(_PANEL.relative_to(_ROOT)),
            "pages": len(pages), "note": "快照内联（file:// 直接看）；http 下 15 秒自刷新"}


# ═══════════ 永动机：卡点 → 方案 → 拍板 → 执行 → 回账（2026-10-01 第 63 轮）═══════════
# 主人令：「把每次的卡点和问题回到上帝之眼，让它决策出方案，然后小土豆自己决策执行。」
#
# 三条硬边界（写死，别改）：
#   ① **只自动执行"不带门"的白名单动作** —— 主人 2026-09-27 立的规矩是
#      「只自动做不带门的，撞 holdout 拦」。带门的一律搁置并进「需主人」清单；
#      **AI 不给自己发授权**（本仓最高优先级红线）。
#   ② **四段留痕**：方案 / 决策 / 执行 / 复核，一段不缺，落 `state/gods_eye_loop.jsonl`。
#   ③ **决策不另造一套**：走 `decide()`（先看证据 → 快脑 → 慢脑 → 或者挂起）。
#      慢脑不可用（缺 external_llm 授权 / 本地脑没起）⇒ **如实挂起**，不许硬猜。
#
# ⚠️ 白名单里**全是只读动作**（自检 / 调用点审计 / 镜像扫描）⇒ "自动执行"的最坏后果
#    只是白跑一次读数。要往里加**任何会写盘或出网**的动作，必须先改这一段的口径。
_LOOP_LOG = _STATE / "gods_eye_loop.jsonl"

_LOOP_ACTIONS = (
    # 🔴 2026-10-01（主人选 2）：这一条**会写 R2**，所以它带 `needs` —— 执行前**现读授权账**，
    #   没票就不跑、只记"缺什么"。它**不是**"无门自动"那一类（那条边界不变）。
    {"id": "cloud_image", "cap": None, "payload": {},
     "what": "云端出图（Workers AI · 出图字节由云端写 R2）", "tags": ("出图", "图像", "作图", "画", "封面", "插画", "海报"),
     "needs": ('external_llm',), "exec": "cloud_image"},
    {"id": "selfscan", "cap": "selfscan", "payload": {},
     "what": "跑一遍自检（只读）", "tags": ("自检", "缺陷", "缺点", "短板", "体检")},
    {"id": "orphan_audit", "cap": "caps_called_audit", "payload": {},
     "what": "能力位调用点审计（只读）", "tags": ("能力位", "调用点", "孤儿", "重复", "闲置")},
    {"id": "mirror_scan", "cap": "mirror_scan", "payload": {},
     "what": "镜像/生产面扫描（只读）", "tags": ("镜像", "漂移", "生产面")},
)


def _log_loop(row: dict) -> None:
    _LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOOP_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


# 标签 → 盘上真文件（`daily()` 的 `src` 是**读数来源的标签**，不是路径；
# 而 `decide()` 的规矩是"证据必须是盘上文件、且当场验存在"）。
# 实测（2026-10-01 第一轮回路）：不补这一层映射，每条卡点都会卡在
# 「证据不在盘上：['cap_tags.audit']」⇒ 全轮挂起，回路空转。
_EVIDENCE_MAP = (
    ("cap_tags", "state/cap_tags.json"),
    ("auth_gate", "gbt_allinone/store/auth_grants.jsonl"),
    ("growth_hooks", "state/gods_eye.json"),
    ("comfyui", "state/gods_eye.json"),
)


def _evidence_for(it: dict) -> str:
    """给一条卡点凑出**盘上真文件**当证据。
    顺序：① 这一条**自带**的 `ev`（从台账里来的条目有个明确的家）→
    ② 扫描记录本身（`state/gods_eye.json`，说明"它出现在这次扫描里"）→
    ③ 标签 → 真文件的映射。**全都必须当场验存在**（`decide()` 会再验一遍）。"""
    ev = []
    own = str(it.get("ev") or "").strip()
    if own and (_ROOT / own).exists():
        ev.append(own)
    if "state/gods_eye.json" not in ev and (_ROOT / "state/gods_eye.json").exists():
        ev.append("state/gods_eye.json")
    blob = (it.get("src") or "") + " " + (it.get("item") or "")
    for token, path in _EVIDENCE_MAP:
        if token in blob and (_ROOT / path).exists() and path not in ev:
            ev.append(path)
    return ",".join(ev)


def _loop_pool() -> list:
    """**全仓卡点池**（2026-10-01 第 63 轮扩）：不只扫描，还有台账与未实现登记。
    主人原话是「把**每次的**卡点和问题回到上帝之眼」—— 所以三处都收，每条带**真文件**当证据：
      ① `daily()` 的全量扫描（缺点/短板/卡点）
      ② `state/排查台账.json` 的**未清故障** + **待办**（N 系列）
      ③ `state/unimplemented.json` 的**未实现条目**（有名字没东西的那些）
    """
    pool = []
    d = daily()
    scan = d.get("全量扫描") or {}
    for kind in ("卡点", "短板", "缺点"):
        for it in (scan.get(kind) or []):
            pool.append({"kind": kind, "item": str(it.get("item") or "")[:160],
                         "src": str(it.get("src") or "")})
    led = _load(_STATE / "排查台账.json", {})
    for f in (led.get("open_faults") or []):
        if isinstance(f, dict) and f.get("what"):
            pool.append({"kind": "未清故障[%s]" % (f.get("id") or "?"),
                         "item": str(f.get("what"))[:160],
                         "src": "排查台账.json·%s" % (f.get("id") or "?"),
                         "ev": "state/排查台账.json"})
    for nd in (led.get("not_done") or []):
        if isinstance(nd, dict) and nd.get("what"):
            pool.append({"kind": "待办[%s]" % (nd.get("id") or "?"),
                         "item": "%s（%s）" % (str(nd.get("what"))[:120], str(nd.get("why"))[:40]),
                         "src": "排查台账.json·%s" % (nd.get("id") or "?"),
                         "ev": "state/排查台账.json"})
    unim = _load(_STATE / "unimplemented.json", {})
    for it in (unim.get("items") or []):
        if isinstance(it, dict) and it.get("missing"):
            pool.append({"kind": "未实现[%s]" % str(it.get("kind"))[:24],
                         "item": str(it.get("missing"))[:160],
                         "src": str(it.get("where"))[:90],
                         "ev": "state/unimplemented.json"})
    return pool


def _loop_candidates(it: dict) -> list:
    """给一条卡点出候选方案（**至少两个**：一个候选不叫决策）。"""
    out = []
    blob = (it.get("item") or "") + " " + (it.get("src") or "")
    for a in _LOOP_ACTIONS:
        if any(t in blob for t in a["tags"]):
            out.append({"label": "修：%s" % a["what"], "action": a})
    out.append({"label": "搁置：等主人授权或资源"})
    out.append({"label": "降级：只记读数、不动手"})
    return out[:3]


def loop(max_items: int = 3, execute: bool = True, **_kw) -> dict:
    """**永动机一轮**：把卡点送回上帝之眼 → 出方案 → Jev 拍板 → （白名单内）执行 → 回账。

    `execute=False` = 干跑（只出方案与决策，不动手）。默认真跑 —— 白名单**全是只读**，
    自动执行的最坏后果只是白跑一次读数（要加写动作请先改 `_LOOP_ACTIONS` 的口径）。
    """
    pool = _loop_pool()
    n = max(1, min(int(max_items or 3), 8))          # 有界：一轮最多 8 条
    picked = pool[:n]
    rows, need_owner = [], []
    for it in picked:
        opts = _loop_candidates(it)
        ev = _evidence_for(it)
        q = "【%s】%s" % (it["kind"], it["item"])
        dec = decide(question=q, options=",".join(o["label"] for o in opts),
                     evidence=ev, context=q)
        row = {"kind": it["kind"], "item": it["item"], "src": it["src"],
               "evidence": ev, "options": [o["label"] for o in opts],
               "decision": {"ok": dec.get("ok"), "choice": dec.get("choice"),
                            "path": dec.get("path"), "blocked": dec.get("blocked"),
                            "why": dec.get("why")}}
        chosen = next((o for o in opts if o["label"] == dec.get("choice")), None) if dec.get("ok") else None
        if not dec.get("ok"):
            # 挂起之后干什么？**仓里自己写的出路是"补证据"** ——
            # `decide()` 的 how_to_unblock 原文：「或把问题改成读数能分出高下的形式（**补证据**）」。
            # ⇒ 挂起时只做**只读取证**（白名单动作），并把读数写进这一条，
            #   下一轮它就有了"能分出高下"的读数。**这不是决策执行**，回执里逐字标清楚。
            pick = next((o for o in opts if o.get("action")), None)
            if pick and execute:
                act = pick["action"]
                t0 = time.time()
                if act.get("exec") == "cloud_image":
                    out = _cloud_image((it.get("item") or "")[:300])
                    row["executed"] = {"kind": "云端出图", "needs": list(act.get("needs") or ()),
                                       "ok": out.get("ok"), "disabled": out.get("disabled"),
                                       "saved": out.get("saved"), "bytes": out.get("bytes"),
                                       "how_to": out.get("how_to")}
                    row["verified"] = {"how": "落点键写在回执里（R2）；真要验图另跑 image 复读"}
                    rows.append(row)
                    if not out.get("ok"):
                        need_owner.append({"why": out.get("why") or "云端出图不可用", "item": it["item"],
                                           "src": it["src"], "how": out.get("how_to") or []})
                    continue
                r = _gate(act["cap"], dict(act["payload"]))
                pay = r.get("payload") if isinstance(r.get("payload"), dict) else {}
                row["executed"] = {"cap": act["cap"], "kind": "取证补证（**不是决策执行**：Jev 挂起）",
                                   "gate_ok": r.get("gate_ok"), "ms": int((time.time() - t0) * 1000),
                                   "reads": {k: pay.get(k) for k in
                                             ("ok", "verdict", "orphan_count", "wired_count",
                                              "passed", "total") if k in pay},
                                   "note": "只读；依据 `decide.how_to_unblock` 的『补证据』一条"}
            else:
                row["executed"] = {"skipped": "决策挂起（Jev 不硬猜），且本条无只读取证动作"}
            need_owner.append({"why": (dec.get("why") or "决策挂起"), "item": it["item"],
                               "src": it["src"], "how": dec.get("how_to_unblock") or []})
        elif chosen and chosen.get("action") and execute:
            act = chosen["action"]
            t0 = time.time()
            r = _gate(act["cap"], dict(act["payload"]))
            pay = r.get("payload") if isinstance(r.get("payload"), dict) else {}
            row["executed"] = {"cap": act["cap"], "gate_ok": r.get("gate_ok"),
                               "ms": int((time.time() - t0) * 1000),
                               "reads": {k: pay.get(k) for k in
                                         ("ok", "verdict", "orphan_count", "wired_count",
                                          "passed", "total") if k in pay},
                               "note": "白名单动作：只读，无作用域"}
        elif chosen and chosen.get("action"):
            row["executed"] = {"skipped": "干跑（execute=False）"}
        else:
            row["executed"] = {"skipped": "选中项不含自动动作（搁置）"}
            need_owner.append({"why": "选中方案不含白名单动作", "item": it["item"],
                               "src": it["src"], "choice": dec.get("choice")})
        rows.append(row)
    _log_loop({"event": "loop", "pool": len(pool), "picked": len(picked), "rows": rows})
    return {"ok": True, "op": "loop", "pool": len(pool), "picked": len(picked),
            "rounds": rows, "need_owner": need_owner,
            "note": "一轮 = 卡点→方案→拍板→执行→回账；**带门的一律搁置**（AI 不发授权）",
            "log": str(_LOOP_LOG.relative_to(_ROOT))}


# ═══════════ 任务推进机：没干完的任务**一直留在上帝视角里**，直到生产上线 ═══════════
# 主人令（2026-10-01）：「一个任务在没有执行完还需要向着生产推进，那么就会一直出现在
# 上帝视角里面分析决策给出方案然后执行推进直到生产上线。」
#
# 阶段机（**确定性，写死**）：登记 → 分析 → 方案 → 执行 → 复验 → 待上线(要票) → 已上线
#   · 每轮只推**一格**（有界；一次推进太多步 = 没人能复核）
#   · 每一格都落账（`state/tasks_advance.jsonl`），所以下一轮读得到"上轮推到哪"
#   · **生产那一步永远要主人的票**（`deploy_publish` 等）—— AI 不给自己发授权（最高红线）
#   · 撞到要授权/要资源的格子 ⇒ 停在「待上线」并把缺什么写进账，**任务不消失**，下轮继续出现
_TASK_LEDGER = _STATE / "tasks_advance.jsonl"
_STAGES = ("登记", "分析", "方案", "执行", "复验", "待上线", "已上线")


def _tasks_state() -> dict:
    """读任务账（**追加式**）：每个任务取最后一行 = 它的现状。"""
    out = {}
    if _TASK_LEDGER.is_file():
        for ln in _TASK_LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            tid = str(r.get("task_id") or "")
            if tid:
                out[tid] = r
    return out


def _task_log(row: dict) -> None:
    _TASK_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_TASK_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def advance(task_id: str = "", goal: str = "", max_steps: int = 1,
            to_production: bool = False, **_kw) -> dict:
    """**推进一轮**：把没干完的任务往前推一格，并让它**继续留在上帝视角里**。

    `task_id` 不给 ⇒ 推**第一个还没到「已上线」的任务**；一个都没有 ⇒ 从卡点池登记一个。
    `max_steps` 有界（默认 1，最多 3）——一轮推多格就没人能复核了。
    """
    st = _tasks_state()
    tid = str(task_id or "").strip()
    if not tid:
        open_ones = [k for k, v in st.items() if v.get("stage") != "已上线"]
        tid = open_ones[0] if open_ones else ""
    if not tid:
        # 池子里挑第一条当新任务登记（**有 src 才登记**：没证据的任务不立）
        pool = _loop_pool()
        if not pool:
            return {"ok": False, "op": "advance", "fail_closed": True,
                    "error": "没有可登记的任务（卡点池为空）—— 不凭空造任务"}
        it = pool[0]
        tid = "task-%05d" % (abs(hash(it["item"])) % 100000)
        st[tid] = {"task_id": tid, "goal": str(goal or it["item"])[:160], "src": it.get("src") or "",
                   "evidence": _evidence_for(it), "stage": "登记", "history": []}
        _task_log(st[tid])
    cur = st.get(tid) or {"task_id": tid, "goal": str(goal or tid)[:160], "src": "", "stage": "登记", "history": []}
    steps = 0
    notes = []
    while steps < max(1, min(int(max_steps or 1), 3)) and cur.get("stage") != "已上线":
        stage = cur.get("stage") or "登记"
        evidence = cur.get("evidence") or cur.get("src") or "state/gods_eye.json"
        if stage == "登记":
            cur["stage"] = "分析"
            notes.append("登记 → 分析：任务入账（src=%s）" % (cur.get("src") or "—"))
        elif stage == "分析":
            cur["stage"] = "方案"
            notes.append("分析 → 方案：拿读数出候选（走 decide，先看证据）")
        elif stage == "方案":
            opts = _loop_candidates({"item": cur.get("goal") or "", "src": cur.get("src") or ""})
            d = decide(question="【任务推进】%s" % (cur.get("goal") or ""),
                       options=",".join(o["label"] for o in opts), evidence=evidence,
                       context="%s %s" % (cur.get("goal") or "", cur.get("src") or ""))
            cur["plan"] = {"options": [o["label"] for o in opts], "ok": d.get("ok"),
                           "choice": d.get("choice"), "path": d.get("path"),
                           "why": d.get("why"), "blocked": d.get("blocked")}
            if d.get("ok"):
                pick = next((o for o in opts if o["label"] == d.get("choice")), None)
                cur["stage"] = "执行" if (pick and pick.get("action")) else "待上线"
                notes.append("方案 → %s：Jev 选了「%s」（path=%s）" % (cur["stage"], d.get("choice"), d.get("path")))
            else:
                cur["stage"] = "待上线"
                cur["need_owner"] = d.get("how_to_unblock") or ["发授权/给资源"]
                notes.append("方案 → 待上线：Jev 挂起（%s）⇒ **任务不消失**，下轮继续" % str(d.get("why"))[:60])
        elif stage == "执行":
            pick = None
            for o in _loop_candidates({"item": cur.get("goal") or "", "src": cur.get("src") or ""}):
                if o.get("action") and o["label"] == (cur.get("plan") or {}).get("choice"):
                    pick = o
                    break
            if pick and pick["action"].get("exec") == "cloud_image":
                # 云端出图（会写 R2）：走专用执行器 —— 它**自己先读票**，没票如实 disabled
                out = _cloud_image((cur.get("goal") or "")[:300])
                cur["executed"] = {"kind": "云端出图", "ok": out.get("ok"), "disabled": out.get("disabled"),
                                   "saved": out.get("saved"), "bytes": out.get("bytes"),
                                   "ext": out.get("ext"), "error": out.get("error"),
                                   "how_to": out.get("how_to")}
                cur["stage"] = "复验" if out.get("ok") else "待上线"
                if not out.get("ok"):
                    cur["need_owner"] = [out.get("why") or "云端出图不可用"] + ([out["how_to"]] if out.get("how_to") else [])
                notes.append("执行 → %s：云端出图 ok=%s%s" % (cur["stage"], out.get("ok"),
                            "（落点 %s）" % out.get("saved") if out.get("saved") else ""))
            elif pick:
                r = _gate(pick["action"]["cap"], dict(pick["action"]["payload"]))
                pay = r.get("payload") if isinstance(r.get("payload"), dict) else {}
                cur["executed"] = {"cap": pick["action"]["cap"], "gate_ok": r.get("gate_ok"),
                                   "reads": {k: pay.get(k) for k in
                                             ("ok", "verdict", "orphan_count", "wired_count", "passed", "total")
                                             if k in pay}}
                cur["stage"] = "复验"
                notes.append("执行 → 复验：跑了 %s（gate_ok=%s）" % (pick["action"]["cap"], r.get("gate_ok")))
            else:
                cur["stage"] = "待上线"
                cur["need_owner"] = ["方案的这一格不在只读白名单 ⇒ 要主人授权/人工执行"]
                notes.append("执行 → 待上线：这一格不是无授权的动作 ⇒ 交主人")
        elif stage == "复验":
            if not to_production:
                cur["stage"] = "待上线"
                cur["need_owner"] = ["生产上线要主人的票（如 deploy_publish / one_key_deploy 的显式落点）"]
                notes.append("复验 → 待上线：读数已记，下一步就是生产上线（要票）")
            else:
                # 🔴 **生产链**（2026-10-01 主人令：「底层框架确认就不需要逐步人工确认，
                # 一路向生产推进；每一环必须严格把控」）。落地方式 = **自动化 + 机器判据**，
                # 不是"少一道门"：
                #   · 顺序按仓里既有规程：扫描 → 塑形 → 排练 → 晋升（一步不跳）
                #   · **每一环 gate_ok 才进下一环**；任一环被拒/报错 ⇒ **当场停**并写清缺什么
                #   · 门还是那道门（run_task）；**我不自发票**，缺票就停在门口照实报
                chain = [("mirror_scan", {}), ("mirror_shape", {}),
                         ("mirror_rehearse", {}), ("mirror_release", {})]
                cur["prod_chain"] = []
                for cap, payload in chain:
                    r = _gate(cap, dict(payload))
                    pay = r.get("payload") if isinstance(r.get("payload"), dict) else {}
                    step = {"cap": cap, "gate_ok": bool(r.get("gate_ok")),
                            "denied": bool(pay.get("denied")),
                            "missing": pay.get("missing") or pay.get("scopes") or [],
                            "reads": {k: pay.get(k) for k in ("ok", "clean", "passed", "total", "version")
                                      if k in pay}}
                    cur["prod_chain"].append(step)
                    if not step["gate_ok"] or step["denied"]:
                        cur["stage"] = "待上线"
                        cur["need_owner"] = ["生产链第 %d 环 `%s` 被门拒：缺 %s"
                                             % (len(cur["prod_chain"]), cap,
                                                ",".join(step["missing"]) or "（见 how_to_grant）"),
                                             "发**一次**窗口票即可 —— 发完这条链自己走完，不用逐步确认"]
                        notes.append("复验 → 生产链：`%s` 被拒（缺 %s）⇒ **停在门口**，不绕、不跳"
                                     % (cap, ",".join(step["missing"]) or "?"))
                        break
                    if cap == "mirror_release":
                        cur["stage"] = "已上线"
                        notes.append("生产链四环逐环 gate_ok ⇒ **已上线**")
                if cur.get("stage") != "已上线" and not cur.get("need_owner"):
                    cur["stage"] = "待上线"
                    cur["need_owner"] = ["生产链未跑完：见 prod_chain"]
        else:                                   # 待上线
            if to_production:
                # 🔴 到票就得**重试**，不许原地复述（2026-10-01 实测抓到的空转）：
                # 上一轮停在门口只写了"缺票"；若票到手还不重走，任务会**永远停在待上线**。
                cur.pop("need_owner", None)
                cur.pop("prod_chain", None)
                cur["stage"] = "复验"
                continue                        # 回机器里，重走生产链（门会再判一次）
            cur["stage"] = "待上线"
            cur.setdefault("need_owner", ["生产上线要主人的票"])
            notes.append("待上线：缺 %s ⇒ 任务**留在上帝视角**里，下轮继续出现" % "、".join(cur["need_owner"][:2]))
            break
        cur.setdefault("history", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                              "stage": cur["stage"], "note": notes[-1]})
        _task_log(cur)
        st[tid] = cur
        steps += 1
    return {"ok": True, "op": "advance", "task_id": tid, "stage": cur.get("stage"),
            "goal": cur.get("goal"), "plan": cur.get("plan"), "executed": cur.get("executed"),
            "need_owner": cur.get("need_owner") or [], "steps": steps, "notes": notes,
            "open_tasks": len([k for k, v in st.items() if v.get("stage") != "已上线"]),
            "_口径": "阶段机：登记→分析→方案→执行→复验→待上线→已上线；**生产那一步永远要主人的票**；"
                     "没到「已上线」的任务**每轮都会再出现**（账在 state/tasks_advance.jsonl，追加式）",
            "log": str(_TASK_LEDGER.relative_to(_ROOT))}


# ═══════════ 云端出图（2026-10-01 主人选 2）：会写 R2 ⇒ **有票才自动** ═══════════
# 边界（别放宽）：它**不是**"无门自动"。跑之前先读授权账：
#   · 有 `network_read` 或 `external_llm` 的**有效窗口票** ⇒ 才发起；
#   · 没票 ⇒ 如实回 `disabled` 并写清缺哪个作用域（**不自发票、不绕门**）。
# 落点：我们自己的云端 Worker（`GBT_POTATO_BASE_URL` 去掉 /v1 后的 `/rpc/<03 号模块>/image`），
# 出图字节由**云端**写进 R2（回执带 `saved` 键），本机不落图、不吃显存。
def _auth_scopes() -> dict:
    try:
        st = _auth_status() or {}
        return st.get("scopes") or {}
    except Exception:                                  # noqa: BLE001
        return {}


def _cloud_image(prompt: str = "", size: str = "1024x1024") -> dict:
    """调云端出图。**先读票**；没票直接 disabled（fail-closed）。"""
    sc = _auth_scopes()
    have = [k for k in ('external_llm',) if (sc.get(k) or {}).get("grants_available")]
    if not have:
        return {"ok": False, "op": "image", "disabled": True,
                "why": "云端出图会写对象存储 ⇒ 要外呼票（external_llm）；现在 0 张",
                "how_to": "py -3.14 -m gbt_allinone auth grant --scope external_llm --ttl 7200",
                "note": "**不自发票、不绕门**（最高红线）"}
    base = str(os.environ.get("GBT_POTATO_BASE_URL") or "").rstrip("/")
    tok = str(os.environ.get("GBT_POTATO_API_KEY") or "")
    if not base or not tok:
        return {"ok": False, "op": "image", "fail_closed": True,
                "why": "没有云端落点或令牌（GBT_POTATO_BASE_URL / GBT_POTATO_API_KEY 未设）"}
    root = base[:-3] if base.endswith("/v1") else base
    url = root + "/rpc/gbt-c03-uncensored-lane/image"
    try:
        import urllib.request as _u
        req = _u.Request(url, data=json.dumps({"prompt": str(prompt)[:800], "size": size}).encode(),
                         headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok,
                                 # 🔴 2026-10-01：UA 必须是**正常客户端**。
                                 # 实测血账：urllib 默认  被 Cloudflare
                                 # 的 Browser Integrity 判成机器人 ⇒ 边缘直接回 ，
                                 # 请求**根本没进 Worker**（于是 token/作用域全都"看着不对"）。
                                 "User-Agent": "GBT-Potato/8.0 (gbtxiaotudou; +local)",
                                 "Accept": "application/json"},
                         method="POST")
        with _u.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
        # 🔴 2026-10-01 补齐（自己踩出来的）：**云端拒绝的原话必须透传** ——
        #   上一版只映射 ok/via/bytes/saved，把云端写的 `error: "_k is not defined"` 过滤掉了，
        #   于是连续几发都只看到"失败、不知为什么"（哑失败）。现在 error/why/reading/boundary
        #   与真实类型（ext/content_type）**一律带出**，缺一个都不行。
        out = {"ok": bool(j.get("ok")), "op": "image", "via": j.get("via"), "model": j.get("model"),
               "bytes": j.get("bytes"), "saved": j.get("saved"), "ms": j.get("ms"),
               "ext": j.get("ext"), "content_type": j.get("content_type"), "png_magic": j.get("png_magic"),
               "weight_ours": j.get("weights_ours"), "boundary": j.get("boundary")}
        if not out["ok"]:
            out["error"] = j.get("error")
            out["why"] = j.get("error") or j.get("reason") or "云端没给原因（**这是缺陷，不是常态**）"
            out["reading"] = j.get("reading")
        return out
    except _u.HTTPError as err:
        # 🔴 2026-10-01 修（自己踩的）：`urlopen` 在 4xx/5xx 时**先抛异常、不读包体** ——
        # 于是云端自己写的 `denied / missing / reason / boundary` 全被丢掉，只剩一句哑的
        # `HTTP Error 403: Forbidden`。**拒绝必须带原因**是本仓的硬规矩，所以这里显式 `read()`。
        body = ""
        try:
            body = err.read().decode("utf-8", "replace")
        except Exception:                              # noqa: BLE001
            pass
        said = {}
        try:
            j = json.loads(body)
            said = {k: j.get(k) for k in ("reason", "error", "denied", "missing", "missing_scopes",
                                          "boundary", "reading", "detail", "op") if j.get(k) is not None}
        except Exception:                              # noqa: BLE001
            said = {"raw": body[:300]} if body else {"note": "云端没回包体"}
        return {"ok": False, "op": "image", "http": err.code,
                "why": "云端拒绝（HTTP %d）" % err.code, "cloud_said": said,
                "note": "云端自己的话原样带回（拒绝必须带原因）"}
    except Exception as err:                           # noqa: BLE001
        return {"ok": False, "op": "image", "fail_closed": True, "why": "云端出图失败：" + str(err)[:160]}


def _cloud_image_op(prompt: str = "", size: str = "1024x1024", **_kw) -> dict:
    """主人手动出图口（也供回路调用）：票在手就直接出，没票如实拒。"""
    return _cloud_image(prompt, size)


def run_op(op: str = "see", **params) -> dict:
    op = (op or "see").lower()
    for name, fn in (("see", see), ("advisors", advisors), ("ask", ask), ("roles", roles),
                     ("decide", decide), ("daily", daily), ("plan", plan), ("panel", panel),
                     ("loop", loop), ("advance", advance), ("image", _cloud_image_op)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（see/advisors/ask/roles/decide/daily/plan/panel/loop/advance/image）"}
