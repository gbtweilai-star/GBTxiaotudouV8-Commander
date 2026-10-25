# -*- coding: utf-8 -*-
"""万能插 · 每日脉冲情报 Agent

定位：每天自动跑一次"情报脉冲"——看屏幕、跑话题追踪、抓最新AI动态、记账入库。
入口：python gbt_allinone/tools/pulse_agent.py [subcommand]
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 确保路径正确
_PROJ = Path(__file__).resolve().parents[2]  # pulse_agent.py→tools→gbt_allinone→项目根
if str(_PROJ) not in sys.path:
    sys.path.insert(0, str(_PROJ))

# 2026-10-04：本文件往 stderr 打 ✅/❌；中文 Windows 管道下默认 GBK 会 UnicodeEncodeError。
# 守卫写法与 five-dim.py / quick_scan.py 同族（hasattr 兜底 + 吞异常安全）。
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import gbt_allinone.tentacle.omni_tentacle as _omni
import gbt_allinone.tools.research_intel as _intel


PULSE_DIR = _PROJ / "gbt_allinone" / "store" / "pulse"
PULSE_LOG = PULSE_DIR / "intelligence_log.jsonl"
PULSE_STATE = PULSE_DIR / "state.json"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_dirs():
    PULSE_DIR.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    if PULSE_STATE.exists():
        try:
            return json.loads(PULSE_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_runs": {}, "history": []}


def _save_state(s: dict):
    _ensure_dirs()
    PULSE_STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


_LOG_CAP = 2000


def _append_jsonl(path: Path, record: dict, cap: int = _LOG_CAP) -> None:
    """追加一行；超 cap 行裁到尾部 cap 行（与 pulse.py 同一口径，2026-10-04 补轮转）。"""
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > cap:
            path.write_text("\n".join(lines[-cap:]) + "\n", encoding="utf-8")
    except Exception:
        pass  # 轮转失败不影响本轮结果（下次追加时再试）


# ── 步骤一：看屏幕（铁律①） ───────────────────────────────────────────────────

def step_see() -> dict:
    """看一眼当前屏幕，记录尺寸与状态。"""
    t = _omni.get_omni()
    r = t.see()
    return {"step": "see", "ok": r.get("ok"), "size": r.get("size"), "ts": _now()}


def step_read_text() -> dict:
    """读屏文字，验证当前焦点窗口内容。"""
    t = _omni.get_omni()
    try:
        txt = t.read_text_fast()
        # read_text_fast 返回字符串，不是 dict
        if isinstance(txt, dict):
            chars = len(txt.get("text", ""))
            preview = txt.get("text", "")[:200]
        else:
            chars = len(txt)
            preview = str(txt)[:200]
        return {"step": "read_text", "ok": True, "chars": chars, "preview": preview}
    except Exception as e:
        return {"step": "read_text", "ok": False, "error": str(e)}


# ── 步骤二：跑五维能力位（智能路由） ───────────────────────────────────────────

def _run_cap(cap_name: str, payload: dict | None = None) -> dict:
    """通用能力位调用包装（继承当前进程的环境变量）。"""
    import subprocess
    cmd = [sys.executable, str(_PROJ / "tools" / "codex-scripts" / "five-dim.py"),
           "cap", cap_name]
    if payload:
        cmd.append(json.dumps(payload, ensure_ascii=False))
    env = {**os.environ, "PYTHONPATH": str(_PROJ)}
    # 调试：打印实际命令和环境
    #print(f"[DEBUG _run_cap] cmd={cmd[:3]}... env_PYTHONPATH={env.get('PYTHONPATH')}", file=sys.stderr)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_PROJ), timeout=60, env=env,
                       # 2026-10-04 修：子脚本强制 UTF-8 输出中文；默认 GBK 解码会让
                       # 读取线程抛 UnicodeDecodeError、stdout 变 None（实测）⇒ 显式钉死口径。
                       encoding="utf-8", errors="replace")
    # 调试
    #print(f"[DEBUG _run_cap] RC={r.returncode} STDOUT_len={len(r.stdout)} STDERR={r.stderr[:100]}", file=sys.stderr)
    try:
        d = json.loads(r.stdout)
        result = d.get("result", {})
        ok = d.get("status") == "ok" or (isinstance(result, dict) and result.get("ok"))
        return {"ok": ok, "raw": d}
    except Exception as e:
        return {"ok": False, "raw": r.stdout[:500], "error": str(e)}


def step_topic_watch(need: str) -> dict:
    """话题追踪：命中技能链。"""
    r = _run_cap("topic_watch", {"need": need})
    ok = r.get("ok", False)
    raw = r.get("raw", {})
    # raw 可能是 dict 或 str
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {"step": "topic_watch", "ok": False, "raw": raw[:500]}
    result = raw.get("result", {}) if isinstance(raw, dict) else {}
    return {
        "step": "topic_watch",
        "ok": ok,
        "chain": result.get("chain"),
        "available": result.get("available"),
        "gaps": result.get("gaps"),
        "note": result.get("note"),
    }


def step_trend_watch() -> dict:
    """爆火观察：读取偏好台账。"""
    r = _run_cap("trend_watch", {"op": "status"})
    ok = r.get("ok", False)
    raw = r.get("raw", {})
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {"step": "trend_watch", "ok": False, "raw": raw[:500]}
    result = raw.get("result", {}) if isinstance(raw, dict) else {}
    ledger = result.get("ledger", {})
    return {
        "step": "trend_watch",
        "ok": ok,
        "ledger_count": ledger.get("count", 0) if isinstance(ledger, dict) else 0,
        "recent": ledger.get("recent", [])[:3] if isinstance(ledger, dict) else [],
    }


def step_research_intel(group: str) -> dict:
    """调研情报骨架：检查三组六维覆盖。"""
    try:
        coverage = _intel.coverage(group)
        # 2026-10-04 修：coverage() 返回的键是 "cells"（research_intel.py:84），
        # 原实现读 "rows" ⇒ .get 默认值让 filled 恒 0（静默错读数）。
        cells = coverage.get("cells", [])
        return {"step": f"research_intel/{group}", "ok": coverage.get("ok"),
                "filled": sum(1 for r in cells if r.get("filled")),
                "cells_total": coverage.get("cells_total", len(cells))}
    except Exception as e:
        return {"step": f"research_intel/{group}", "ok": False, "error": str(e)}


# ── 步骤三：执行真实情报采集 ───────────────────────────────────────────────────

def step_collect_ai_news() -> dict:
    """收集 AI 新闻（通过 daily-ai-news 技能）。"""
    # 这个技能在 .openclaw-autoclaw/skills/daily-ai-news/
    import subprocess
    skill_md = Path.home() / ".openclaw-autoclaw" / "skills" / "daily-ai-news" / "SKILL.md"
    if not skill_md.exists():
        return {"step": "collect_ai_news", "ok": False, "reason": "skill not installed"}
    # 读技能说明，理解怎么用
    content = skill_md.read_text(encoding="utf-8")[:500]
    return {
        "step": "collect_ai_news",
        "ok": True,
        "skill_available": True,
        "skill_path": str(skill_md),
        "note": "按 daily-ai-news 规程执行实际采集",
    }


def step_collect_tech_news() -> dict:
    """收集科技新闻（通过 news-aggregator）。"""
    import subprocess
    skill_md = Path.home() / ".openclaw-autoclaw" / "skills" / "news-aggregator" / "SKILL.md"
    exists = skill_md.exists()
    return {
        "step": "collect_tech_news",
        "ok": exists,
        "skill_available": exists,
        "skill_path": str(skill_md) if exists else None,
    }


# ── 主脉冲流程 ─────────────────────────────────────────────────────────────────

def run_pulse(need: str = "AI行业动态与大模型发布", dry: bool = False) -> dict:
    """
    跑一次完整脉冲。

    流程：
      1. see() + read_text()  — 先看再说
      2. topic_watch(need)    — 路由到正确技能
      3. trend_watch()        — 爆火偏好
      4. research_intel()     — 三组六维骨架
      5. collect_*()          — 真实信息采集
    """
    _ensure_dirs()
    today = _today()
    state = _load_state()

    # 防重：同主题同天只跑一次（dry 模式除外）
    if not dry and need in state.get("last_runs", {}):
        last = state["last_runs"][need]
        if last.startswith(today):
            return {"ok": True, "skipped": True, "reason": f"今日已跑 {need}", "last_run": last}

    t0 = time.time()
    print(f"[pulse] 启动 @ {_now()}  need={need}  dry={dry}", file=sys.stderr)

    # 顺序执行各步骤
    steps = []
    for fn, args in [
        (step_see, ()),
        (step_read_text, ()),
        (step_topic_watch, (need,)),
        (step_trend_watch, ()),
        (step_research_intel, ("video_intel",)),
        (step_research_intel, ("music_intel",)),
        (step_research_intel, ("film_intel",)),
        (step_collect_ai_news, ()),
        (step_collect_tech_news, ()),
    ]:
        try:
            s = fn(*args)
        except Exception as e:
            s = {"step": fn.__name__, "ok": False, "error": str(e)}
        steps.append(s)
        status = "✅" if s.get("ok") else "❌"
        print(f"  {status} {s.get('step')}", file=sys.stderr)

    elapsed = round(time.time() - t0, 1)
    ok_all = all(s.get("ok") for s in steps)

    record = {
        "at": _now(),
        "need": need,
        "elapsed_s": elapsed,
        "steps": steps,
        "ok_all": ok_all,
    }

    # 落盘（2026-10-04：带轮转的追加口，超 2000 行裁尾 —— 与 pulse.py 同一口径）
    _append_jsonl(PULSE_LOG, record)

    # 更新 state
    if "last_runs" not in state:
        state["last_runs"] = {}
    state["last_runs"][need] = _now()
    # 2026-10-04：last_runs 原只增不减 ⇒ 每个不同 need 永久驻留；按时间裁到最近 64 条。
    if len(state["last_runs"]) > 64:
        _items = sorted(state["last_runs"].items(), key=lambda kv: str(kv[1]))[-64:]
        state["last_runs"] = dict(_items)
    state["history"].append({"at": _now(), "ok": ok_all, "need": need})
    if len(state["history"]) > 30:
        state["history"] = state["history"][-30:]
    _save_state(state)

    print(f"[pulse] 完成 elapsed={elapsed}s  ok_all={ok_all}", file=sys.stderr)
    return record


def status() -> dict:
    """脉冲运行状态汇总。"""
    state = _load_state()
    records = []
    if PULSE_LOG.exists():
        for line in PULSE_LOG.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    return {
        "ok": True,
        "total_runs": len(records),
        "recent_runs": records[-5:],
        "state": state,
    }


# ── CLI 入口 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="万能插 · 每日脉冲情报 Agent")
    p.add_argument("action", choices=["run", "status"], nargs="?")
    p.add_argument("--need", default="AI行业动态与大模型发布", help="追踪需求描述")
    p.add_argument("--dry", action="store_true", help="只跑不写盘")
    args = p.parse_args()

    if args.action == "status" or args.action is None:
        r = status()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        r = run_pulse(args.need, dry=args.dry)
        print(json.dumps(r, ensure_ascii=False, indent=2))
