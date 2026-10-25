# -*- coding: utf-8 -*-
"""万能插脉冲 · 每日情报调研执行层

Owner 风哥 2026-10-03 批准。
走 omni_tentacle（看/读）+ 万能插能力位（跑链）+ research_intel（记账）。
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import sys as _sys
from pathlib import Path as _P
# 脉冲脚本从 gbt_allinone/tools/ 内部跑，加上一级路径让 gbt_allinone 可 import
def _ensure_imports():
    """确保 gbt_allinone 可被 import（不管从哪个 cwd 启动）。"""
    _proj_root = _P(__file__).resolve().parents[2]  # tools/ → gbt_allinone/ → 项目根
    _sys.path = [_sys.path[0]] + [str(_proj_root)] + [p for p in _sys.path if p != str(_proj_root)]
    import gbt_allinone.tentacle.omni_tentacle as _omni_mod
    import gbt_allinone.tools.research_intel as _intel
    import gbt_allinone.topic_watch as _tw
    # 2026-10-04 修：trend_watch 是**独立模块**，原实现拿 topic_watch 当 trend_watch 用
    # ⇒「爆火观察」步骤每次读的都是话题追踪的状态（永远绿、读数错位）。
    import gbt_allinone.trend_watch as _tw2
    return _omni_mod, _intel, _tw, _tw2


_omni_mod, _intel, _tw, _tw2 = _ensure_imports()

ROOT = Path(__file__).resolve().parents[2]  # 项目根目录
PULSE_LOG = ROOT / "gbt_allinone" / "store" / "pulse" / "daily_pulse.jsonl"
PULSE_STATE = ROOT / "gbt_allinone" / "store" / "pulse" / "state.json"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _ts() -> float:
    return time.time()


def _ensure_dirs():
    PULSE_LOG.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict:
    if PULSE_STATE.exists():
        try:
            return json.loads(PULSE_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_run": None, "history": []}


def _save_state(s: dict):
    _ensure_dirs()
    PULSE_STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def see_screen() -> dict:
    """看当前屏幕（铁律①：先看再动）。"""
    t = _omni_mod.get_omni()
    return t.see()


def read_screen_text() -> str:
    """快速读屏文字（铁律⑤：亲眼验证）。"""
    t = _omni_mod.get_omni()
    return t.read_text_fast()


def _parse_cap_result(d: dict) -> bool:
    """解析 five-dim.py cap 输出，返回 ok 布尔值。"""
    # 顶层 ok
    if d.get("status") == "ok":
        return True
    # result 层 ok
    r = d.get("result", {})
    if isinstance(r, dict) and r.get("ok") is True:
        return True
    return bool(d.get("status") == "ok")


def run_topic_watch(need: str) -> dict:
    """跑话题追踪链（topic_watch）。"""
    try:
        r = _tw.run(op='route', payload={'need': need})
        return {"ok": r.get('ok') and bool(r.get('chain')), "data": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_trend_watch(op: str = "status") -> dict:
    """跑爆火观察（trend_watch）。2026-10-04 修：原实现误调 topic_watch（见 _ensure_imports）。"""
    try:
        r = _tw2.run(op=op)
        return {"ok": r.get('ok'), "data": r}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_research_intel(group: str = "video_intel") -> dict:
    """跑调研情报骨架（research_intel）。"""
    try:
        if group:
            return _intel.coverage(group)
        return _intel.coverage()
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_quick_scan() -> dict:
    """跑全维度故障速扫（quick_scan CLI）。"""
    import subprocess
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "codex-scripts" / "quick_scan.py")],
        capture_output=True, text=True, cwd=str(ROOT), timeout=120,
        # 2026-10-04 修：子脚本强制 UTF-8 输出中文；中文 Windows 默认 GBK 解码
        # ⇒ 读取线程抛 UnicodeDecodeError、r.stdout 变 None（实测）。显式钉死口径。
        encoding="utf-8", errors="replace",
    )
    return {"rc": r.returncode, "stdout": (r.stdout or "")[:2000], "stderr": (r.stderr or "")[:500]}


_LOG_CAP = 2000


def _append_jsonl(path: Path, record: dict, cap: int = _LOG_CAP) -> None:
    """追加一行；超 cap 行就裁剪到尾部 cap 行。

    2026-10-04 补：原实现只增不轮转（每日 1 条起、full 模式可反复追加），
    结构上无界；status() 又是全量读 ⇒ 文件越长读放大越大。
    """
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > cap:
            path.write_text("\n".join(lines[-cap:]) + "\n", encoding="utf-8")
    except Exception:
        pass  # 轮转失败不影响本轮结果（下次追加时再试）


def _collect_pulse(need: str) -> list:
    """单轮脉冲采集：screen → topic → trend → intel。"""
    steps = []

    # ① 看屏幕（铁律①）
    try:
        screen = see_screen()
        steps.append({"step": "see", "ok": screen.get("ok"), "size": screen.get("size")})
    except Exception as e:
        steps.append({"step": "see", "ok": False, "error": str(e)})

    # ② 读屏文字（铁律⑤）
    try:
        txt = read_screen_text()
        steps.append({"step": "read_text", "ok": True, "chars": len(txt)})
    except Exception as e:
        steps.append({"step": "read_text", "ok": False, "error": str(e)})

    # ③ 话题追踪
    try:
        tw = run_topic_watch(need)
        steps.append({"step": "topic_watch", "ok": tw.get("ok")})
    except Exception as e:
        steps.append({"step": "topic_watch", "ok": False, "error": str(e)})

    # ④ 爆火观察
    try:
        tr = run_trend_watch("status")
        steps.append({"step": "trend_watch", "ok": tr.get("ok")})
    except Exception as e:
        steps.append({"step": "trend_watch", "ok": False, "error": str(e)})

    # ⑤ 情报骨架
    try:
        ri = run_research_intel("video_intel")
        steps.append({"step": "research_intel", "ok": ri.get("ok")})
    except Exception as e:
        steps.append({"step": "research_intel", "ok": False, "error": str(e)})

    return steps


def run_pulse(need: str = "AI领域情报和科技新闻", full: bool = False) -> dict:
    """
    万能插脉冲主入口。

    Args:
        need: 追踪需求（如「AI行业动态」）
        full: 是否跑全量（含 quick_scan，慢）
    Returns:
        本轮脉冲结果摘要
    """
    _ensure_dirs()
    ts = _now()
    state = _load_state()

    # 去重：同一天只跑一次
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_date") == today and not full:
        return {
            "ok": True,
            "skipped": True,
            "reason": f"今日已跑过（{state.get('last_run')}）；要重跑加 --full",
            "last_run": state.get("last_run"),
        }

    t0 = _ts()
    print(f"[pulse] 启动 @ {ts}  need={need}", file=sys.stderr)

    # 采集
    steps = _collect_pulse(need)

    # 全量模式追加 quick_scan
    if full:
        try:
            qs = run_quick_scan()
            steps.append({"step": "quick_scan", "rc": qs.get("rc")})
        except Exception as e:
            steps.append({"step": "quick_scan", "ok": False, "error": str(e)})

    elapsed = round(_ts() - t0, 1)
    ok_all = all(s.get("ok") for s in steps if "ok" in s)

    record = {
        "at": ts,
        "need": need,
        "full": full,
        "elapsed_s": elapsed,
        "steps": steps,
        "ok_all": ok_all,
    }

    # 落盘（2026-10-04：改走带轮转的追加口，超 2000 行裁尾）
    _append_jsonl(PULSE_LOG, record)

    # 更新 state
    state["last_date"] = today
    state["last_run"] = ts
    state["history"].append({"at": ts, "ok": ok_all, "need": need})
    if len(state["history"]) > 30:
        state["history"] = state["history"][-30:]
    _save_state(state)

    print(f"[pulse] 完成 elapsed={elapsed}s ok_all={ok_all}", file=sys.stderr)
    return record


def status() -> dict:
    """脉冲状态汇总。"""
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
        "state": state,
        "total_runs": len(records),
        "recent": records[-5:],
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="万能插脉冲 · 每日情报调研")
    p.add_argument("action", choices=["run", "status"], nargs="?")
    p.add_argument("--need", default="AI领域情报和科技新闻")
    p.add_argument("--full", action="store_true", help="全量模式（含 quick_scan）")
    args = p.parse_args()

    if args.action == "status" or args.action is None:
        r = status()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        r = run_pulse(args.need, full=args.full)
        print(json.dumps(r, ensure_ascii=False, indent=2))
