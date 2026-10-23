# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 话题追踪（topic_watch）—— 发现与命中层，不是又一套调研实现。

Owner 风哥 2026-09-18 批准（商店卡片「话题追踪」标注「含 0 个技能」，实测确为空：
全仓 topic_watch / 话题追踪 仅命中方案稿自己，caps_registry 无此条）。

整条链路（一句话讲清）：
    你会怎么说  →  brain_exec.route() 语义命中本 cap（吃的是注册表 desc 的前 60 字符）
                →  本模块 route op 把需求落到「邻域技能链」
                →  交大脑执行层执行；「持续盯着」走现成心跳/cron

什么时候该用它（命中即用，不需要先想起来「我还有个话题追踪」）：
  · 说「盯着 / 持续关注 / 有变化告诉我 / 每天给我 / 早报」 → 追踪链 + 定时腿
  · 说「追踪 / 最新动态 / 行业动态 / 新闻 / 搜一下 / 深度调研」 → 检索与深研链
  · 说「股价 / 行情 / 财报 / 赔率 / 竞品 / 市场多大」 → 垂类链
  · 都命中不了 → 落 find-skills 找现成技能；仍没有就如实说没有（不编）

红线（方案稿 §6）：
  · 不新建常驻进程 / 守护进程 / 后台轮询 —— 定时一律走现成心跳或 cron
  · 不复制技能实现 —— 只做发现与命中，技能本体留在技能目录
  · 不编造动态 —— 拿不到就如实报缺口

ops：
  route   need=<一句人话>  → 邻域技能链（逐个对盘校验，缺了如实列进 gaps）
  catalog                  盘上可挂技能实况（现读磁盘，不拿清单当依据）
  engine                   追踪引擎（last30days）同化落点 + 三条红线观测
  timer                    定时腿就位状态 —— 现成心跳承载，零新增进程
  status                   汇总
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SKILLS_ROOT = Path.home() / ".openclaw-autoclaw" / "skills"
# 同化落点 = 框架原生层（`recon/` 已在 hygiene.PKG_DIRS 白名单内，
# 零新增顶层目录）。上游树是**只读源**，不是落点。
ENGINE_DIR = WORKSPACE / "gbt_allinone" / "recon" / "last30days"
UPSTREAM_DIR = WORKSPACE / "\u5ba1\u7f8e\u76f8\u5173skill" / "design-skeletons" / "last30days"
ENGINE_FILES = ("__init__.py", "cli.py", "watchlist.py", "briefing.py",
                "store.py", "engine/pipeline.py")

# ── 意图映射（Owner 2026-09-18 批准的方案稿 §3 实测版）──
# 左：你会怎么说；右：自动命中的邻域技能链（顺序 = 优先序）
INTENT_MAP = (
    (("AI 有什么新东西", "大模型动态", "新发布", "AI 动态",
      "AI 行业动态", "行业动态", "行业新闻", "最新动态"), ("daily-ai-news",)),
    (("今天发生什么", "早报", "简报", "新闻"), ("news-summary", "news-aggregator")),
    (("搜一下", "查一下", "最新消息"), ("web-search-plus", "multi-search-engine")),
    (("深度调研", "行业报告", "调研", "学术"), ("academic-deep-research", "deep-research")),
    (("市场多大", "市场规模", "竞品"), ("market-research",)),
    (("股价", "行情", "财报"), ("stock-analysis", "us-stock-analysis", "gildata-finance-data")),
    (("赔率", "预测市场"), ("polymarket",)),
    (("网友怎么说", "社区反馈", "Reddit"), ("reddit-readonly",)),
    (("这个视频讲什么", "视频讲了什么"), ("youtube-watcher",)),
    (("整理成内容", "选题", "内容计划"), ("content-strategy",)),
)

# 「爆火作品 / 用户偏好」族（Owner 2026-09-19：调用触手就要观察每日所有的爆火作品）——
# 触发词的**唯一真相在 trend_watch.FAMILY**，这里 import，不抄第二份。
# 右侧四个技能全部来自盘上实况（catalog 73 项实取），不是想当然的名字。
try:
    from .trend_watch import FAMILY as _TREND_FAMILY
except Exception:  # noqa: BLE001
    _TREND_FAMILY = ()
if _TREND_FAMILY:
    INTENT_MAP = INTENT_MAP + ((_TREND_FAMILY,
                                ("youtube-watcher", "video-transcript-downloader",
                                 "reddit-readonly", "web-search-plus")),)

# 「持续盯着」类：定时腿走现成心跳 / cron，本模块只标注，不新增进程
WATCH_WORDS = ("盯着", "持续关注", "持续追踪", "有变化告诉我", "有变化通知我", "每天给我", "定时")

FALLBACK = ("find-skills",)

_FM = re.compile(r"^---\s*\n(.*?)\n---", re.S)


def _desc_of(skill_md: Path) -> str:
    """读 SKILL.md frontmatter 的 description（兼容 > / | 块标量）。"""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = _FM.match(text)
    if not m:
        return ""
    lines = m.group(1).splitlines()
    for idx, line in enumerate(lines):
        mm = re.match(r"^description\s*:\s*(.*)$", line)
        if not mm:
            continue
        val = mm.group(1).strip()
        if val in (">", "|", ">-", "|-"):
            buf = []
            for nxt in lines[idx + 1:]:
                if nxt.startswith((" ", "\t")):
                    buf.append(nxt.strip())
                elif nxt.strip():
                    break
            return " ".join(x for x in buf if x)
        return val.strip("\"'")
    return ""


def catalog() -> dict:
    """盘上可挂技能实况 —— 现读磁盘，不拿任何清单当依据。"""
    rows = []
    if SKILLS_ROOT.is_dir():
        for d in sorted(SKILLS_ROOT.iterdir()):
            sk = d / "SKILL.md"
            if d.is_dir() and sk.is_file():
                rows.append({"skill": d.name, "bytes": sk.stat().st_size,
                             "desc": _desc_of(sk)[:180]})
    return {"ok": True, "root": str(SKILLS_ROOT), "count": len(rows), "skills": rows}


def route(need: str) -> dict:
    """一句人话 → 邻域技能链。命中的技能逐个对盘校验，缺了如实报 gaps（不编）。"""
    q = (need or "").strip()
    if not q:
        raise ValueError("缺少 need：请给一句需求（如「帮我盯着 AI 行业动态」）")
    chain, matched = [], []
    for words, skills in INTENT_MAP:
        hit = [w for w in words if w in q]
        if hit:
            matched.extend(hit)
            chain.extend(skills)
    watch_words = [w for w in WATCH_WORDS if w in q]
    if not chain:
        chain = list(FALLBACK)
    seen, ordered = set(), []
    for s in chain:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    avail = {r["skill"] for r in catalog()["skills"]}
    return {"ok": True, "need": q[:200],
            "chain": ordered,
            "matched_keywords": matched,
            "watch": bool(watch_words),
            "watch_words": watch_words,
            "available": [s for s in ordered if s in avail],
            "gaps": [s for s in ordered if s not in avail],
            "timer": "走现成心跳/cron（零新增进程）" if watch_words else None,
            "note": "本模块只给命中链；执行交大脑执行层"}


# ── engine 探针（只观测，不控制）──────────────────────────────
# Owner 风哥 2026-09-18 拍：「探针只观测，不控制；红线核验要 fail-closed」。
# 职责分离：
#   观测侧 = 本文件 —— 结构化事件 + 自身异常一律吞掉，**永不抛**，不反噬业务。
#   核验侧 = `recon/last30days/redlines.py` —— fail-closed，任一条红抛
#            `RedlineViolation` 拒绝同化；门禁走那条，不走这条。
# 埋点只贴**真实存在**的原生调用点：本模块是只读落点探针，不执行同化写入，
# 故不埋 `assimilator.apply` / `native_sink.write` 这类假点 —— 不编造调用。
@dataclass(frozen=True)
class ProbeEvent:
    """结构化探针事件（不可变）—— 只观测，不携带业务状态。"""

    trace_id: str
    stage: str
    native_point: str
    topic: str
    tenant: str
    source: str
    ok: bool
    latency_ms: float
    error: str | None = None
    redline: str | None = None


_PROBE_LOG = logging.getLogger("topic_watch.probe")


def emit_probe(event: ProbeEvent) -> None:
    """只观测：发结构化事件，绝不改业务状态；自身异常一律吞掉。"""
    try:
        _PROBE_LOG.info("topic_watch.probe", extra={"probe": dict(vars(event))})
    except Exception:          # 探针绝不反噬业务
        pass


def _redline_observation() -> dict:
    """调核验侧做**只读观测** —— 异常在这里吞成探针字段，绝不外溢。"""
    try:
        from .recon.last30days import redlines
        return redlines.check(ENGINE_DIR)
    except Exception as exc:
        return {"ok": False, "redlines": [], "gaps": [],
                "probe_error": type(exc).__name__ + ": " + str(exc)[:200]}


def engine() -> dict:
    """追踪引擎同化落点 + 三条红线观测 —— 只在盘上探，不起任何进程。

    探针只观测不控制：本函数**永不抛**，任何内部异常都吞成探针字段。
    fail-closed 的核验在 `recon/last30days/redlines.py::verify()`，不在本函数。
    """
    trace_id = uuid.uuid4().hex
    t0 = time.perf_counter()
    events: list = []

    def _probe(stage, native_point, ok, *, error=None, redline=None,
               source="native"):
        try:
            ev = ProbeEvent(
                trace_id=trace_id, stage=stage, native_point=native_point,
                topic="last30days", tenant="gbt-native", source=source,
                ok=bool(ok), latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=error, redline=redline)
            events.append(ev)
            emit_probe(ev)
        except Exception as exc:   # 探针自身崩了也不许拖垮引擎
            events.append({"stage": stage, "ok": False,
                           "error": "probe_emit_failed: " + type(exc).__name__})

    try:
        present = ENGINE_DIR.is_dir()
        _probe("native_read", "recon/last30days", present,
               error=None if present else "engine_dir_missing")

        files = {}
        if present:
            for n in ENGINE_FILES:
                p = ENGINE_DIR / n
                files[n] = p.stat().st_size if p.is_file() else None

        # 判据反转（2026-09-18 同化）：同化的定义是「并入原生层」，不是
        # 「注册成技能」。注册了 = 挂载未同化 = gap —— 旧判据方向是反的。
        registered = (SKILLS_ROOT / "last30days" / "SKILL.md").is_file()

        obs = _redline_observation()
        redline_ok = bool(obs.get("ok"))
        _probe("redline_observe", "redlines.check", redline_ok,
               error=obs.get("probe_error"),
               redline=None if redline_ok else "REDLINE_VIOLATION")

        gaps = []
        if not present:
            gaps.append("引擎目录不存在（" + str(ENGINE_DIR) + "）")
        else:
            missing = [n for n, v in files.items() if v is None]
            if missing:
                gaps.append("引擎关键件缺失 " + str(missing))
        if registered:
            gaps.append("引擎被注册成技能（" + str(SKILLS_ROOT / "last30days")
                        + "）—— 同化 = 并入原生层，不是挂载成技能")
        if not redline_ok:
            gaps.extend("红线未过：" + str(g) for g in
                        (obs.get("gaps") or ["redlines.check 未通过"]))
        return {"ok": not gaps, "trace_id": trace_id,
                "dir": str(ENGINE_DIR), "present": present,
                "upstream_dir": str(UPSTREAM_DIR),
                "files": files, "registered_as_skill": registered,
                "redlines": obs.get("redlines") or [],
                "probe_events": events,
                "probe_error": obs.get("probe_error"),
                "gaps": gaps}
    except Exception as exc:       # 探针绝不反噬业务
        # 异常必须留痕（Owner 风哥 2026-09-18 回归 3）：先发结构化探针事件，
        # 再返回 ok=False。**不向上抛** —— engine() 自己就是探针，没有上层业务
        # 可抛给；status() 也调它，抛了会连带炸掉汇总。
        try:
            ev = ProbeEvent(trace_id=trace_id, stage="engine_error",
                            native_point="topic_watch.engine", topic="last30days",
                            tenant="gbt-native", source="probe", ok=False,
                            latency_ms=(time.perf_counter() - t0) * 1000.0,
                            error=type(exc).__name__ + ": " + str(exc)[:200])
            events.append(ev)
            emit_probe(ev)
        except Exception:
            events.append({"stage": "engine_error", "ok": False,
                           "error": "probe_emit_failed"})
        return {"ok": False, "trace_id": trace_id, "dir": str(ENGINE_DIR),
                "present": False, "upstream_dir": str(UPSTREAM_DIR),
                "files": {}, "registered_as_skill": False,
                "redlines": [], "probe_events": events,
                "probe_error": type(exc).__name__ + ": " + str(exc)[:200],
                "gaps": ["探针自身异常（已吞，未外溢）"]}


# ── 定时腿（C4）────────────────────────────────────────────────
# Owner 风哥 2026-09-18：定时腿一律走**现成**心跳 / cron —— 本模块只声明「盯什么、几点跑」，
# 不起任何进程、不注册任何守护。落点 = 工作区 HEARTBEAT.md（心跳每 30 分钟必读该文件）。
WATCHLIST = (
    {"at": "08:30", "window_min": 30, "cadence": "daily",
     "topic": "AI 行业动态与大模型发布", "chain": ("daily-ai-news", "news-summary")},
    {"at": "12:30", "window_min": 30, "cadence": "daily",
     "topic": "AI 社区热议与网友反馈", "chain": ("reddit-readonly", "news-aggregator")},
    {"at": "21:00", "window_min": 30, "cadence": "daily",
     "topic": "盯住的个股行情 / 财报变动",
     "chain": ("stock-analysis", "us-stock-analysis", "gildata-finance-data")},
)

HEARTBEAT_MD = WORKSPACE / "HEARTBEAT.md"
HEARTBEAT_MARK = "## 话题追踪定时腿"
SCHEDULER_CFG = Path.home() / ".openclaw-autoclaw" / "openclaw.json"
SELF_PATH = Path(__file__).resolve()
# 「新增进程」的机械面：出现这些 = 起了子进程 / 线程 / 事件循环 / 第三方调度器  PROC_SCAN_OFF
PROC_PRIMITIVES = ("subprocess", "Popen", "os.system", "Thread(", "asyncio",  # PROC_SCAN_OFF
                   "multiprocessing", "sched.")  # PROC_SCAN_OFF


def _heartbeat_every() -> tuple:
    """现成调度器是否在跑：读网关配置里的心跳周期（只读，不改配置）。

    返回 (周期, 命中路径)。实况路径 = `agents.defaults.heartbeat.every`
    （2026-09-18 实测；首版写成 `defaults.heartbeat` -> 读空 -> 判红 —— 又是一次
    「判据自己写错」，是探针自己把它抓出来的，失败方向安全：判红不骗绿）。
    """
    try:
        cfg = json.loads(SCHEDULER_CFG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", ""
    for path in (("agents", "defaults", "heartbeat", "every"),
                 ("defaults", "heartbeat", "every")):
        node = cfg
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
        if node:
            return str(node), "/".join(path)
    return "", ""


def _process_primitives() -> list:
    """本模块源码里「起进程」原语命中点（行号:原语）—— 空 = 零新增进程。"""
    hits = []
    for i, line in enumerate(SELF_PATH.read_text(encoding="utf-8").splitlines(), 1):
        if "PROC_SCAN_OFF" in line:      # 扫描器自己的模式表，不算命中
            continue
        code = line.split("#", 1)[0]
        for pat in PROC_PRIMITIVES:
            if pat in code:
                hits.append(str(i) + ":" + pat)
    return hits


def next_fires(now=None) -> list:
    """定时腿下一次触发时刻（本地时区）—— 把「几点跑」从文档变成可算的数字。"""
    from datetime import datetime, timedelta
    now = now or datetime.now()
    out = []
    for w in WATCHLIST:
        hh, mm = (int(x) for x in str(w["at"]).split(":"))
        fire = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if fire <= now:
            fire += timedelta(days=1)
        out.append({"topic": w["topic"], "at": w["at"],
                    "next": fire.strftime("%Y-%m-%d %H:%M")})
    return out


def timer() -> dict:
    """C4 定时腿就位状态 —— 三件证据，全部可静态复核，不靠「感觉挂上了」。

    ① 现成调度器在跑（`openclaw.json` → `defaults.heartbeat.every` 非空）
    ② 工作区 `HEARTBEAT.md` 内含定时腿段（心跳每轮必读它，故时段到了会自动触发，
       **不需要用户先提这个需求** —— 这才是 C4 说的「默认挂载，随时在位」）
    ③ 本模块零进程原语（子进程 / 线程 / 事件循环 / 第三方调度器一律不出现，
       见 PROC_PRIMITIVES）—— 定时腿是「挂上去」，不是「新起一个」

    三者同时成立才 ok；任一条缺 = 定时腿没落地（不按「差不多」算绿）。
    """
    every, every_path = _heartbeat_every()
    marked = False
    try:
        marked = HEARTBEAT_MARK in HEARTBEAT_MD.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    prim = _process_primitives()
    gaps = []
    if not every:
        gaps.append("现成调度器未就绪（openclaw.json defaults.heartbeat.every 为空）")
    if not marked:
        gaps.append("HEARTBEAT.md 内无定时腿段（缺 " + HEARTBEAT_MARK + "）")
    if prim:
        gaps.append("模块内含进程原语 " + str(prim) + "（违反零新增进程）")
    return {"ok": not gaps,
            "heartbeat_every": every,
            "heartbeat_every_path": every_path,
            "scheduler_live": bool(every),
            "heartbeat_md": str(HEARTBEAT_MD),
            "heartbeat_md_marked": marked,
            "process_primitives": len(prim),
            "process_detail": prim,
            "carrier": "现成心跳（心跳读 HEARTBEAT.md；不新增进程）",
            "watchlist": [dict(w) for w in WATCHLIST],
            "next_fires": next_fires(),
            "gaps": gaps}


def status() -> dict:
    cat = catalog()
    eng = engine()
    tim = timer()
    return {"ok": True,
            "ops": ["route", "catalog", "engine", "timer", "status"],
            "timer_ok": tim["ok"],
            "timer_carrier": tim["carrier"],
            "skills_on_disk": cat["count"],
            "intent_rows": len(INTENT_MAP),
            "watch_words": list(WATCH_WORDS),
            "engine_present": eng["present"],
            "engine_ok": eng["ok"],
            "engine_redlines_ok": all(r.get("ok") for r in eng.get("redlines", [])),
            "engine_gaps": eng["gaps"],
            "processes_added": 0,
            "truth": "发现与命中层；技能本体留在技能目录，不复制实现。"}


def run(op: str = "route", payload: dict | None = None) -> dict:
    """统一入口（api.py 分派调用）：按 op 走。"""
    p = payload or {}
    op = str(op or "route").strip().lower()
    if op == "catalog":
        return catalog()
    if op == "engine":
        return engine()
    if op == "timer":
        return timer()
    if op == "status":
        return status()
    if op == "route":
        return route(str(p.get("need") or p.get("topic") or ""))
    raise ValueError("未知 op: " + op + "（可选 route / catalog / engine / timer / status）")
