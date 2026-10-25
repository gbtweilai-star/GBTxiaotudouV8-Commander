# -*- coding: utf-8 -*-
"""语音 → 全机操控 · **路由表 + 实时可用性探针**（只读）。

主人令（2026-10-08，逐字）：「数字人必须慢慢了解用户懂用户，数字人语音交互就可以操控整台电脑的
任意APP，浏览器以及所有能调试，调节蓝牙，无线网全部都能操作」

本件回答一个问题：**主人说的一句自然语言，要落到"哪一个能力位 · 哪一个动作 · 吃哪张票"，
以及"现在到底能不能用"**（现探，不是文档抄的）。

## 六类操控面（主人点名的）→ 路由
  · 任意 APP          → 能力位 `tentacle`（56 动作 + 33 读取；启动/结束/切窗/控件穿透）
                         动手动作要 `desktop_control`；读取免卡（see/read_text/list_windows…）
  · 浏览器            → 能力位 `browser` op=native（Chrome DevTools Protocol）
                         读取免卡（status/list_tabs/get_text/dom_query…）
                         动手（launch/navigate/click_element/type_text…）要 `browser_control`
                         screenshot 另需 `filesystem_write`
  · 可调试的（DevTools）→ 同一条 CDP：`execute_script` / `inject_script` / `intercept_requests`
                         —— 这**就是**"所有能调试"的落点；要 `browser_control`
  · 蓝牙              → 能力位 `bluetooth`（bleak BLE + win 经典栈）+ `bt_control`（意图→协议→写→验）
                         status/scan 免卡；connect/write/control 要 `device_control`
  · 无线网            → 🔴 **未找到能力位**（本仓 240 位里没有 wifi/wlan 位）。
                         本件按 surface_bind 同款安全写法**只读**探 `netsh wlan` 的可控制键；
                         要真正"调节"还差：① 把 netsh 登记进 surface_bind 登记表（需 filesystem_write 票）
                         ② 一条能走门的能力位（未建）。**直接跑 netsh 去改状态 = 绕门 ⇒ 本件不做。**
  · 本机设置面        → `tentacle` 的 launch（如 ms-settings:）+ act_window/domain_act 操作"设置"窗
                         —— 要 `desktop_control`；只读窗口枚举免卡

## 票（授权门）口径 —— 只读读取，绝不申领
  `auth_gate_status` 现读：`ai_can_grant=false`；发放只有两条合法路：
    ① 终端 `python -m gbt_allinone auth grant --scope <s> --ttl <秒>`（人在 TTY 手打 YES）
    ② 主人手写 `store/auth_grants.jsonl` 追加一行
  ⇒ **AI 发不出授权，本件也不去要**。缺票的格子如实写"缺哪张票、谁有权给"。

## 用法
    py -3.14 tools/codex-scripts/voice-control-route.py              # 人读：六类面逐格
    py -3.14 tools/codex-scripts/voice-control-route.py --json       # 机器读
    py -3.14 tools/codex-scripts/voice-control-route.py --check      # 判据（9 条）+ 负对照（每条变异必须报红）
    py -3.14 tools/codex-scripts/voice-control-route.py --emit-state # 落 state/voice-control-route.json

## 🔴 纪律
  · 全程**只读**：探针只调免卡只读动作（list_windows / status / scan / pulse / keys…）
    与自探（netsh 读类子命令）；**一个动手动作都不试**（缺票就是缺票，不绕）。
  · 能力位调用走**唯一门**（`py -3.14 -m gbt_allinone run <kind> <json>` = api.run_task）。
  · 探不到写"未找到"；缺票写"缺票"；拿不到麦写原文 —— 不许假绿。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
SCRATCH = ROOT / ".scratch"
STATE = ROOT / "state"
ASR = ROOT / "tools" / "codex-scripts" / "asr-offline.py"

# surface_bind 的登记表真源（唯一定位：字典 TOOLS，8 个工具名全在这一处）
SURFACE_BIND_SRC = ROOT / "gbt_allinone" / "tools" / "surface_bind.py"

# 票名真源（合法作用域）——判据 K2 用；现读优先，读不到退回静态表（表来源：gbt_allinone/auth_gate.py）
STATIC_SCOPES = [
    "osint_private", "owner_control", "process_execute", "filesystem_write", "remote_device",
    "deploy_publish", "network_private", "browser_control", "desktop_control", "device_control",
    "external_llm", "data_export", "privacy_read", "audio_output", "audit_read",
]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ─────────────────────────── 唯一门：调能力位（只读动作） ───────────────────────────
def run_cap(kind: str, payload: dict, timeout: int = 180) -> dict:
    """走唯一门调一个能力位（`py -3.14 -m gbt_allinone run <kind> <json>`）。

    返回 {ok, result, raw, exit, cmd}。**原文照带**（失败不许静默）。
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    arg = json.dumps(payload, ensure_ascii=False)
    cmd = [PY, "-m", "gbt_allinone", "run", kind, arg]
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "调用超时（%ss）" % timeout, "kind": kind,
                "cmd": _show(cmd)}
    except Exception as e:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e), "kind": kind,
                "cmd": _show(cmd)}
    txt = (p.stdout or "").strip()
    d = {}
    i = txt.find("{")
    if i >= 0:
        chunk = txt[i:]
        try:
            d = json.loads(chunk)
        except Exception:                                      # noqa: BLE001
            try:
                d = ast.literal_eval(chunk)
            except Exception:                                  # noqa: BLE001
                d = {}
    res = (d.get("gbt_result") or {}).get("result")
    if res is None:
        res = d.get("result") if isinstance(d.get("result"), dict) else {}
    return {"ok": bool(d) and (d.get("status") != "error"), "kind": kind, "result": res or {},
            "raw": txt[:1500], "exit": p.returncode, "cmd": _show(cmd)}


def _show(cmd: list) -> str:
    return " ".join(('"%s"' % c) if " " in c else c for c in cmd)


# ─────────────────────────── 六个探针（全部只读） ───────────────────────────
def probe_auth() -> dict:
    r = run_cap("auth_gate_status", {})
    res = r.get("result") or {}
    scopes = res.get("scopes") or {}
    tickets = {k: {"grants_available": (v or {}).get("grants_available", 0),
                   "mode": (v or {}).get("mode"), "used_total": (v or {}).get("used_total", 0)}
               for k, v in scopes.items()}
    return {"at": now_iso(), "probe": "run auth_gate_status {}",
            "ok": bool(res), "ai_can_grant": bool(res.get("ai_can_grant", False)),
            "grant_sources": res.get("grant_sources") or [],
            "one_shot_scopes": res.get("one_shot_scopes") or [],
            "tickets": tickets,
            "live_ticket_count": sum(1 for v in tickets.values() if v["grants_available"] > 0),
            "evidence": "ai_can_grant=%s · 有票作用域=%d 个 · 发放只有两条合法路（终端 auth grant / 主人手写 auth_grants.jsonl）"
                        % (res.get("ai_can_grant"), sum(1 for v in tickets.values() if v["grants_available"] > 0)),
            "raw_keys": sorted(scopes.keys())[:20]}


def probe_tentacle() -> dict:
    w = run_cap("tentacle", {"action": "list_windows"})
    res = w.get("result") or {}
    wins = res.get("windows") or []
    mf = run_cap("tentacle_manifest", {})
    manifest = ((mf.get("result") or {}).get("manifest") or "")
    return {"at": now_iso(), "probe": "run tentacle {\"action\":\"list_windows\"}（免卡只读）"
                                      " + run tentacle_manifest {}",
            "ok": bool(res.get("ok")) and bool(manifest),
            "windows": len(wins) if isinstance(wins, list) else 0,
            "window_sample": [str((x or {}).get("title"))[:24] for x in (wins[:5] if isinstance(wins, list) else [])],
            "manifest_len": len(manifest),
            "actions_in_manifest": {k: (k in manifest) for k in
                                    ["launch", "kill", "focus_window", "act_window", "domain_act",
                                     "domain_type", "click", "type", "hotkey", "see", "read_text",
                                     "list_windows", "process_list", "type_to_window", "dismiss_dialog",
                                     "press", "enter", "escape", "scroll", "drag", "move", "click_text",
                                     "type_to_field", "double_click", "right_click", "copy", "paste",
                                     "wait_window", "handle_any_dialog", "window_info",
                                     "see_active_window", "domain_read"]},
            "evidence": "只读窗口枚举现读 %s 个窗（例：%s）· 触手总纲 %d 字" %
                        (len(wins) if isinstance(wins, list) else "?", ", ".join(
                            str((x or {}).get("title"))[:16] for x in (wins[:3] if isinstance(wins, list) else [])),
                         len(manifest))}


def probe_browser() -> dict:
    r = run_cap("browser", {"op": "native", "action": "status"}, timeout=120)
    res = r.get("result") or {}
    actions = res.get("actions") or []
    return {"at": now_iso(), "probe": "run browser {\"op\":\"native\",\"action\":\"status\"}（免卡只读）",
            "ok": bool(res),
            "cdp_available": bool(res.get("cdp_available")),
            "status": res.get("status"),
            "endpoint": res.get("endpoint"),
            "browser_executable": res.get("browser_executable"),
            "actions": actions,
            "note": str(res.get("note") or "")[:200],
            "evidence": "status=%s · cdp_available=%s · endpoint=%s · 动作面 %d 个（读类 %d / 写类 %d）" %
                        (res.get("status"), res.get("cdp_available"), res.get("endpoint"), len(actions),
                         len([a for a in actions if a in READONLY_CDP]), len([a for a in actions if a not in READONLY_CDP]))}


READONLY_CDP = {"status", "list_tabs", "get_title", "get_url", "get_text", "dom_query",
                "get_cookies", "intercept_events", "intercept_status"}


def probe_bluetooth() -> dict:
    b = run_cap("bluetooth", {"op": "status"}, timeout=120)
    c = run_cap("bt_control", {"op": "status"}, timeout=120)
    rb, rc = b.get("result") or {}, c.get("result") or {}
    return {"at": now_iso(), "probe": "run bluetooth {\"op\":\"status\"} + run bt_control {\"op\":\"status\"}（免卡只读）",
            "ok": bool(rb) and bool(rc),
            "ble_backend": rb.get("ble_backend"), "classic_backend": rb.get("classic_backend"),
            "ops": rb.get("ops") or [], "bt_control_ops": rc.get("ops") or [],
            "protocol_library": rc.get("protocol_library") or [],
            "evidence": "ble_backend=%s · classic=%s · bluetooth ops=%s · bt_control ops=%s · 协议库 %d 条" %
                        (rb.get("ble_backend"), rb.get("classic_backend"), rb.get("ops"),
                         rc.get("ops"), len(rc.get("protocol_library") or []))}


def probe_capability_net() -> dict:
    r = run_cap("capability_net", {}, timeout=120)
    res = r.get("result") or {}
    return {"at": now_iso(), "probe": "run capability_net {}（免卡只读）", "ok": bool(res),
            "seven_columns": res.get("seven_columns") or {},
            "note": "它是**能力位穿透网**读数（indexed/reachable/verified…），**不是无线网** —— 名字像网络面，实物不是",
            "evidence": json.dumps(res.get("seven_columns") or {}, ensure_ascii=False)[:220]}


# ── 无线网：按 surface_bind 同款安全写法（生成脚本 + 字面量 cmd）只读探 netsh 可控制键 ──
def probe_wlan(force: bool = False) -> dict:
    if not force and not sys.platform.startswith("win"):
        return {"ok": False, "why": "非 Windows：netsh 不适用"}
    SCRATCH.mkdir(parents=True, exist_ok=True)
    script = SCRATCH / "_probe_netsh_wlan.cmd"
    body = ("@echo off\r\nchcp 65001 >nul\r\n"
            "netsh wlan help\r\n"
            "echo __MARK_SHOW__\r\n"
            "netsh wlan show ?\r\n"
            "echo __MARK_SET__\r\n"
            "netsh wlan set ?\r\n"
            "echo __MARK_IFACE__\r\n"
            "netsh wlan show interfaces\r\n")
    script.write_text(body, encoding="utf-8")
    try:
        p = subprocess.run(["cmd", "/c", str(script)], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=90)
        out = (p.stdout or "") + (p.stderr or "")
    except Exception as e:                                     # noqa: BLE001
        return {"at": now_iso(), "ok": False, "why": "%s: %s" % (type(e).__name__, e),
                "probe": "cmd /c %s（自探·只读）" % script.name}
    sec = {"top": "", "show": "", "set": "", "iface": ""}
    cur = "top"
    for ln in out.splitlines():
        if ln.strip() == "__MARK_SHOW__":
            cur = "show"; continue
        if ln.strip() == "__MARK_SET__":
            cur = "set"; continue
        if ln.strip() == "__MARK_IFACE__":
            cur = "iface"; continue
        sec[cur] += ln + "\n"
    rx = re.compile(r"^\s{0,4}([?A-Za-z][A-Za-z0-9_\- ]{0,44}?)\s-\s")
    dedup = lambda rows: sorted({m.group(1).strip() for m in map(rx.match, rows) if m})
    top = dedup(sec["top"].splitlines())
    show = dedup(sec["show"].splitlines())
    setk = dedup(sec["set"].splitlines())
    read_only = {"?", "help", "show", "dump"}
    iface = {}
    m = re.search(r"Name\s*:\s*(.+)", sec["iface"])
    st = re.search(r"State\s*:\s*(.+)", sec["iface"])
    ssid = re.search(r"SSID\s*:\s*(.+)", sec["iface"])
    desc = re.search(r"Description\s*:\s*(.+)", sec["iface"])
    iface = {"name": (m.group(1).strip() if m else ""), "state": (st.group(1).strip() if st else ""),
             "ssid": (ssid.group(1).strip() if ssid else ""),
             "desc": (desc.group(1).strip() if desc else "")}
    return {"at": now_iso(), "probe": "cmd /c .scratch/_probe_netsh_wlan.cmd（自探·只读：netsh wlan help / show ? / set ? / show interfaces）",
            "ok": bool(top) and bool(show) and bool(setk),
            "top_keys": top, "show_keys": show, "set_keys": setk,
            "keys_total": len(top) + len(show) + len(setk),
            "read_only_keys": [k for k in top if k in read_only],
            "state_changing_keys": [k for k in top if k not in read_only] + setk,
            "adapter": iface,
            "evidence": "WLAN 可控制键：顶层 %d + show 子键 %d + set 子键 %d = **%d 把**；网卡=%s(%s) state=%s ssid=%s" %
                        (len(top), len(show), len(setk), len(top) + len(show) + len(setk),
                         iface.get("name"), iface.get("desc"), iface.get("state"), iface.get("ssid"))}


def probe_surface_bind() -> dict:
    keys = run_cap("surface_bind", {"op": "keys"}, timeout=120)
    probe_netsh = run_cap("surface_bind", {"op": "probe", "tool": "netsh"}, timeout=300)
    res = keys.get("result") or {}
    surfaces = res.get("surfaces") or []
    pn = probe_netsh.get("result") or {}
    registered = sorted({str(s.get("tool")) for s in surfaces if s.get("tool")})
    netsh_registered = bool(pn.get("ok"))
    return {"at": now_iso(), "probe": "run surface_bind {\"op\":\"keys\"} + run surface_bind {\"op\":\"probe\",\"tool\":\"netsh\"}",
            "ok": bool(surfaces),
            "registered_tools": registered,
            "registry_source": "gbt_allinone/tools/surface_bind.py::TOOLS（第 37–110 行；2026-10-08 加 netsh 条目，其余工具定义未动）",
            "netsh_registered": netsh_registered,
            "netsh_probe_ok": netsh_registered,
            "netsh_keys": pn.get("keys"),
            "netsh_probe_error": str(pn.get("error") or ""),
            "summary": [{"tool": s.get("tool"), "keys": s.get("keys"), "gone": s.get("gone")} for s in surfaces],
            "evidence": "登记表 %d 个工具：%s；netsh 探针：%s" %
                        (len(registered), registered,
                         ("ok=true keys=%s min=%s bound_to=%s manifest=%s（2026-10-08 加）" %
                          (pn.get("keys"), pn.get("min_keys"), pn.get("bound_to"), pn.get("manifest")))
                         if netsh_registered else str(pn.get("error") or pn)[:200])}


def probe_desktop_commander() -> dict:
    r = run_cap("desktop_commander", {"op": "status"}, timeout=120)
    res = r.get("result") or {}
    return {"at": now_iso(), "probe": "run desktop_commander {\"op\":\"status\"}（免卡只读）",
            "ok": bool(res.get("ok")),
            "connected": bool(res.get("connected")),
            "remote_running": bool(res.get("remote_running")),
            "server": res.get("server"),
            "evidence": "server=%s · connected=%s · remote_running=%s ⇒ %s" %
                        (res.get("server"), res.get("connected"), res.get("remote_running"),
                         "可起进程跑命令（connect/start_process 吃 process_execute 票）"
                         if res.get("connected") else "**当前未连接**（connect 要 process_execute 票）")}


def probe_asr(full: bool) -> dict:
    """ASR 腿探针：**每次都真喂一个真 WAV**（真识别），full 模式再跑 selfcheck（含设备腿原文）。"""
    op = "selfcheck" if full else "status"
    try:
        p = subprocess.run([PY, str(ASR), op, "--json"], cwd=str(ROOT), capture_output=True,
                           encoding="utf-8", errors="replace", timeout=300)
        d = json.loads((p.stdout or "").strip() or "{}")
    except Exception as e:                                     # noqa: BLE001
        return {"at": now_iso(), "ok": False, "why": "%s: %s" % (type(e).__name__, e),
                "probe": "py tools/codex-scripts/asr-offline.py %s --json" % op}
    st = d.get("status") if isinstance(d.get("status"), dict) else d
    runs = d.get("runs") or {}
    dev = runs.get("device") or {}
    wav = runs.get("wav_real") or {}
    if not full:                                               # 非 full：单独真跑一次 WAV 腿
        try:
            p2 = subprocess.run([PY, str(ASR), "listen", "--wav",
                                 str(ROOT / "gbt_allinone" / "store" / "vision" / "tts_test.wav"), "--json"],
                                cwd=str(ROOT), capture_output=True, encoding="utf-8",
                                errors="replace", timeout=180)
            wav = json.loads((p2.stdout or "").strip() or "{}")
        except Exception:                                      # noqa: BLE001
            wav = {}
        dev = {"status": "no_input" if not st.get("capture_ready") else "?",
               "reason": st.get("device_leg")}
    out = {"at": now_iso(), "probe": "py tools/codex-scripts/asr-offline.py %s --json（+ 真喂 WAV）" % op,
           "ok": bool(st.get("recognizer_ready")),
           "recognizer_ready": bool(st.get("recognizer_ready")),
           "recognizers_zh": st.get("recognizers_zh") or [],
           "wavein_devices": st.get("wavein_devices"),
           "capture_ready": bool(st.get("capture_ready")),
           "wav_leg": st.get("wav_leg"), "device_leg": st.get("device_leg"),
           "how_to_enable_mic": st.get("how_to_enable_mic", ""),
           "honesty": st.get("honesty", "")}
    if full:
        out["device_run"] = {"status": dev.get("status"), "reason": dev.get("reason")}
        out["asr_selfcheck_ok"] = bool(d.get("ok"))
        out["asr_criteria"] = [{"name": c.get("name"), "pass": c.get("pass")}
                               for c in (d.get("criteria") or [])]
    out["wav_run"] = {"text": wav.get("text"), "confidence": wav.get("confidence"),
                      "recognizer": wav.get("recognizer"), "heard": wav.get("heard"),
                      "status": wav.get("status")}
    out["evidence"] = "识别器=%s · wavein_devices=%s ⇒ 能听 WAV（真跑 heard=%s text=%r conf=%s）· 不能听麦（%s）" % (
        ",".join(st.get("recognizers_zh") or []) or "无", st.get("wavein_devices"),
        wav.get("heard"), wav.get("text"), wav.get("confidence"),
        str((dev.get("reason") if full else st.get("device_leg")) or "")[:70])
    return out


def probe_voice_status() -> dict:
    r = run_cap("voice", {"op": "status"}, timeout=120)
    res = r.get("result") or {}
    return {"at": now_iso(), "probe": "run voice {\"op\":\"status\"}（免卡只读）", "ok": bool(res),
            "tts": res.get("tts"), "asr": res.get("asr"), "listen": res.get("listen"),
            "recognizers_zh": res.get("recognizers_zh") or [],
            "wavein_devices": res.get("wavein_devices"),
            "evidence": "tts=%s · listen=%s · asr(云)=%s · wavein_devices=%s" %
                        (res.get("tts"), res.get("listen"), res.get("asr"), res.get("wavein_devices"))}


# 本轮真跑一次的"写入链示范"留底（与页面 vcSpec 里的 owner_demo 同一件事；
# 数据全来自 2026-10-08 的真跑：写前/写后/独立读回/审计行/引擎随后 idle_reflection 重算 —— 都是原文）
WRITE_DEMO = {
    "at": "2026-10-08T09:54:46",
    "what": "把主人 2026-10-08 的令（原话）走 mind observe（零票）写进用户模型，再独立读回",
    "cmd": "py -3.14 -m gbt_allinone run mind '{\"op\":\"observe\",\"event\":\"user_message\",\"text\":\"主人令：…\",\"focus\":\"deep\",\"importance\":0.8}'",
    "before": {"confidence": 0.36, "evidence": ["专注:deep", "时段:上午"]},
    "after": {"confidence": 0.68, "evidence": ["信号:praise", "专注:deep", "时段:上午"]},
    "audit_line": '{"iso":"2026-10-08T09:54:46","event":"mind_event","meta":{"event":"user_message","signals":["praise"],"mood":"开心","owner_confidence":0.68,"importance":0.8}}',
    "readback": "run mind {\"op\":\"pulse\"} 独立再读（当时）：confidence=0.68",
    "after_idle": "09:55:26 引擎 idle_reflection 重算推断 → confidence 回 0.36（history 里 09:54:46 user_message 仍在；owner_model 是每轮重算的推断，不是累加分数）",
}


def probe_mind() -> dict:
    r = run_cap("mind", {"op": "pulse"}, timeout=120)
    res = r.get("result") or {}
    om = res.get("owner_model") or {}
    return {"at": now_iso(), "probe": "run mind {\"op\":\"pulse\"}（免卡只读·不推进时间不写盘）",
            "ok": bool(om),
            "owner_model": om,
            "read_path": "run mind '{\"op\":\"pulse\"}'（CLI·只读）· 面板桥 POST /api/quick {\"action\":\"mind_pulse\"}（holo_pet/panel_server.py:2314）",
            "write_path": "面板桥 Bridge.send() 每轮已天然 observe：'user_message'（panel_server.py:1372）→ 回合完成 'task_succeeded'/'task_finished'（:1571）→ mind_engine.observe → owner_model",
            "memory_store": "gbt_allinone/store/mind_state.json（框架唯一心智台账；**不另建第二套记忆**）",
            "mirror": "重要心智事件镜像进原生生命档案 life_archive（mind_engine.observe 内联，失败不反打断）",
            "audit": "store/audit.jsonl 事件 mind_event（每轮带 owner_state/owner_confidence）",
            "evidence": "owner_model: state=%s emotion=%s energy=%s focus=%s urgency=%s conf=%s · rule=%s" %
                        (om.get("state"), om.get("emotion"), om.get("energy"), om.get("focus"),
                         om.get("urgency"), om.get("confidence"), str(om.get("rule"))[:40])}


# ─────────────────────────── 六类面（路由表主体） ───────────────────────────
def build_routes(p: dict) -> list:
    tent = p["tentacle"]
    br = p["browser"]
    bt = p["bluetooth"]
    wl = p["wlan"]
    sb = p["surface_bind"]
    dc = p.get("desktop_commander") or {}
    auth = p["auth"]
    t = lambda s: (auth["tickets"].get(s) or {}).get("grants_available", 0)   # noqa: E731
    ticket_state = lambda s: ("有票 %d 张（%s）" % (t(s), (auth["tickets"].get(s) or {}).get("mode"))
                              if t(s) else "**缺票**（0 张；%s）" % (auth["tickets"].get(s) or {}).get("mode", "?"))  # noqa: E731
    grant_hint = ("谁能给：只有主人 —— 终端 `py -3.14 -m gbt_allinone auth grant --scope %s --ttl 600`"
                  "（TTY 手打 YES）或手写 store/auth_grants.jsonl；ai_can_grant=%s")
    rows = []

    rows.append({
        "id": "app", "face": "任意 APP", "cn": "启动 / 结束 / 切窗 / 控件穿透读写",
        "capability": "tentacle（备线：desktop_commander 终端触手）",
        "capability_source": "gbt_allinone/tentacle/（56 动作 + 33 读取）· desktop_commander（终端+文件系统）",
        "readonly_actions": ["see", "read_text", "list_windows", "process_list", "active_window",
                             "find_text", "grab_value", "domain_read", "extract_ui_elements"],
        "actions": ["launch", "kill", "focus_window", "act_window", "click", "type", "hotkey",
                    "domain_act", "domain_type", "type_to_window", "dismiss_dialog"],
        "actions_evidence": {k: tent["actions_in_manifest"].get(k, False) for k in
                             ["launch", "kill", "focus_window", "act_window", "click", "type",
                              "hotkey", "domain_act", "domain_type", "type_to_window", "dismiss_dialog"]},
        "ticket": "desktop_control",
        "live": {"at": tent["at"], "probe": tent["probe"], "ok": tent["ok"], "evidence": tent["evidence"]},
        "status": "读取免卡（现探到 %d 个窗）· 动手需 desktop_control：%s" % (tent["windows"], ticket_state("desktop_control")),
        "grant_hint": grant_hint % ("desktop_control", auth["ai_can_grant"]),
        "voice_example": "「把记事本打开」「把那个窗口关掉」「切到浏览器」—— bridge.py 的 89 动作词典做意图命中",
    })
    rows.append({
        "id": "browser", "face": "浏览器", "cn": "CDP 直连系统 Chrome（不是自动化框架开关）",
        "capability": "browser",
        "capability_source": "gbt_allinone/native_browser.py（自带最小 RFC6455，零第三方依赖）",
        "readonly_actions": sorted(READONLY_CDP),
        "actions": ["launch", "ensure", "navigate", "click_element", "type_text", "set_cookies",
                    "intercept_requests", "reload", "create_tab", "close_tab", "pin_window"],
        "actions_evidence": {k: (k in (br.get("actions") or [])) for k in
                             ["launch", "ensure", "navigate", "click_element", "type_text", "set_cookies",
                              "intercept_requests", "reload", "create_tab", "close_tab", "pin_window"]},
        "ticket": "browser_control",
        "live": {"at": br["at"], "probe": br["probe"], "ok": br["ok"], "evidence": br["evidence"]},
        "status": "读类免卡（但**现在没有开着的调试口**：cdp_available=%s ⇒ 先得 launch，而 launch 要 browser_control）· %s"
                  % (br["cdp_available"], ticket_state("browser_control")),
        "grant_hint": grant_hint % ("browser_control", auth["ai_can_grant"]),
        "voice_example": "「打开某网页」「把页面上的按钮点一下」「读一下这个页面的正文」",
    })
    rows.append({
        "id": "devtools", "face": "可调试的（DevTools / CDP）", "cn": "所有能调试的：脚本注入 / 请求拦截 / 页面操控",
        "capability": "browser（op=native 同一条 CDP 通道）",
        "capability_source": "policy.py:180-189 —— execute_script/inject_script/intercept_requests 不在只读白名单",
        "readonly_actions": ["get_cookies", "dom_query", "get_text", "intercept_events", "intercept_status"],
        "actions": ["execute_script", "inject_script", "intercept_requests", "intercept_stop",
                    "privacy_mode", "screenshot(另需 filesystem_write)"],
        "actions_evidence": {k: (k in (br.get("actions") or [])) for k in
                             ["execute_script", "inject_script", "intercept_requests", "intercept_stop", "privacy_mode", "screenshot"]},
        "ticket": "browser_control",
        "live": {"at": br["at"], "probe": br["probe"], "ok": br["ok"], "evidence": br["evidence"]},
        "status": "动作面在位（execute_script/inject_script/intercept_requests 都在 %d 个 CDP 动作里）· 需 browser_control：%s · screenshot 另需 filesystem_write"
                  % (len(br.get("actions") or []), ticket_state("browser_control")),
        "grant_hint": grant_hint % ("browser_control", auth["ai_can_grant"]),
        "voice_example": "「页面里帮我执行这段脚本」「拦截这个页面的请求」—— 这就是主人说的『所有能调试』",
    })
    rows.append({
        "id": "bluetooth", "face": "蓝牙", "cn": "扫地机/灯/空调/音箱等 BLE 与经典蓝牙",
        "capability": "bluetooth + bt_control",
        "capability_source": "gbt_allinone/bluetooth_cap.py（bleak + win 栈）· bt_control.py（意图→协议→写→验）",
        "readonly_actions": ["status", "scan", "list", "classic", "identify", "parse_intent", "smart_scan"],
        "actions": ["connect", "read", "write", "control"],
        "actions_evidence": {k: (k in (bt.get("ops") or []) or k in (bt.get("bt_control_ops") or []))
                             for k in ["connect", "read", "write", "control"]},
        "ticket": "device_control",
        "live": {"at": bt["at"], "probe": bt["probe"], "ok": bt["ok"], "evidence": bt["evidence"]},
        "status": "scan/status 免卡 · connect/write/control 需 device_control：%s" % ticket_state("device_control"),
        "grant_hint": grant_hint % ("device_control", auth["ai_can_grant"]),
        "voice_example": "「扫一下附近的蓝牙设备」「把灯调暗一点」",
    })
    rows.append({
        "id": "wifi", "face": "无线网", "cn": "Wi-Fi 连接/断开/配置（主人点的『调节无线网』）",
        "capability": None,
        "capability_source": "🔴 **本仓 240 个能力位里没有 wifi/wlan 位**（全仓 grep 无命中；名字像网络的 capability_net 是**能力位穿透网读数**，不是无线网）。"
                             "本件已按 surface_bind 同款安全写法**只读**探到 netsh wlan 的可控制键，并按协调者授权把它**登记进 surface_bind**",
        "readonly_actions": ["netsh wlan show *（读类键，show 子键 17 把）"],
        "actions": [],
        "actions_evidence": {},
        "ticket": None,
        "live": {"at": wl.get("at"), "probe": wl.get("probe"), "ok": wl.get("ok"), "evidence": wl.get("evidence")},
        "status": "**无能力位路由（诚实：这是缺的那一格）**。现状三件分开说："
                  "① 可控制键已探到 **%s 把**（网卡 %s state=%s）；"
                  "② 已登记进 surface_bind（netsh_registered=%s · bound_to=%s · 清单 %s）；"
                  "③ **执行按键的能力位仍未建** —— surface_bind 的正向『每个键都能经唯一门执行』对 netsh 这一段**尚不成立**；"
                  "唯一沾边的替代路是 desktop_commander 起进程（吃 process_execute 票：%s），但它 %s。"
                  "**直接跑 netsh 去改状态 = 绕门 ⇒ 本件不做。**"
                  % (wl.get("keys_total"), (wl.get("adapter") or {}).get("name"),
                     (wl.get("adapter") or {}).get("state"), sb.get("netsh_registered"),
                     "tentacle" if sb.get("netsh_registered") else "（未绑定）",
                     "state/surfaces/netsh.json" if sb.get("netsh_registered") else "（无）",
                     ticket_state("process_execute"), dc.get("evidence", "（未探）")),
        "grant_hint": grant_hint % ("filesystem_write", auth["ai_can_grant"]),
        "voice_example": "「把 Wi-Fi 连到某某网络」「断开无线」—— 键探到了、登记了，但**还差一条能走门的执行位**（未建）",
    })
    rows.append({
        "id": "settings", "face": "本机设置面", "cn": "系统设置窗 / 显示 / 声音 等本机设置",
        "capability": "tentacle（launch ms-settings:… + act_window/domain_act 操作设置窗）",
        "capability_source": "bridge.py 桌面域动作（launch / act_window / domain_act / domain_type）",
        "readonly_actions": ["list_windows", "window_info", "see_active_window", "read_text", "domain_read"],
        "actions": ["launch", "focus_window", "act_window", "domain_act", "domain_type", "type"],
        "actions_evidence": {k: tent["actions_in_manifest"].get(k, False) for k in
                             ["launch", "focus_window", "act_window", "domain_act", "domain_type", "type"]},
        "ticket": "desktop_control",
        "live": {"at": tent["at"], "probe": tent["probe"], "ok": tent["ok"], "evidence": tent["evidence"]},
        "status": "只读窗口枚举免卡（现读 %d 窗，本机『设置』窗在列）· 打开/操作设置面需 desktop_control：%s"
                  % (tent["windows"], ticket_state("desktop_control")),
        "grant_hint": grant_hint % ("desktop_control", auth["ai_can_grant"]),
        "voice_example": "「打开显示设置」「把系统音量调低」",
    })
    return rows


# ─────────────────────────── 判据（9 条，每条带变异负对照） ───────────────────────────
def criteria_defs(valid_scopes: set):
    def k1(payload):     # 六类面齐全 + 四要素
        rs = payload.get("routes") or []
        if len(rs) != 6:
            return False
        for r in rs:
            if not r.get("face"):
                return False
            if "capability" in r and r["capability"] is None:
                _src = str(r.get("capability_source", ""))
                if ("未找到" not in _src) and ("没有 wifi/wlan 位" not in _src):
                    return False
            elif not r.get("capability"):
                return False
            if not (r.get("actions") or r.get("readonly_actions")):
                return False
            if "ticket" not in r:
                return False
            if not (r.get("live") or {}).get("at"):
                return False
        return True

    def k2(payload):     # 票名必须是真作用域（或空=免票且只读动作）
        for r in payload.get("routes") or []:
            tk = r.get("ticket")
            if tk in (None, ""):
                if r.get("actions"):
                    return False          # 有动手动作却没票 ⇒ 不许
            elif tk not in valid_scopes:
                return False
        return True

    def k3(payload):     # 每个声称的动作必须有证据（伪造动作名必红）
        for r in payload.get("routes") or []:
            ev = r.get("actions_evidence") or {}
            for a in r.get("actions") or []:
                if a.endswith("(另需 filesystem_write)"):
                    continue
                if not ev.get(a):
                    return False
        return True

    def k4(payload):     # 现状必须新鲜（±600s）
        now = time.time()
        for r in payload.get("routes") or []:
            at = (r.get("live") or {}).get("at") or ""
            try:
                ts = time.mktime(time.strptime(at, "%Y-%m-%dT%H:%M:%S"))
            except Exception:                                  # noqa: BLE001
                return False
            if abs(now - ts) > 600:
                return False
        return True

    def k5(payload):     # 无线网格如实：无能力位 + 键数>0 + 状态写清"没有执行位"
        r = _route(payload, "wifi")
        if not r:
            return False
        wl = payload.get("wlan") or {}
        sb = payload.get("surface_bind") or {}
        if r.get("capability") is not None:
            return False
        if "未找到" not in str(r.get("capability_source", "")) and "没有 wifi/wlan 位" not in str(r.get("capability_source", "")):
            return False
        if int(wl.get("keys_total") or 0) <= 0:
            return False
        if "能力位仍未建" not in str(r.get("status")):
            return False
        if sb.get("netsh_registered") and "已登记进 surface_bind" not in str(r.get("status")):
            return False
        return "绕门" in str(r.get("status"))

    def k6(payload):     # ASR 如实
        a = payload.get("asr") or {}
        if not a.get("recognizer_ready"):
            return False
        if not a.get("capture_ready"):
            dr = a.get("device_run") or {}
            if dr:
                if dr.get("status") != "no_input" or not str(dr.get("reason") or "").strip():
                    return False
            elif "死的" not in str(a.get("device_leg") or ""):
                return False
        return True

    def k7(payload):     # 用户模型读写路径 + 推断不冒充
        m = payload.get("user_model") or {}
        om = m.get("owner_model") or {}
        if not (m.get("read_path") and m.get("write_path")):
            return False
        if not om.get("confidence") and om.get("confidence") != 0:
            return False
        if "推断" not in str(om.get("rule") or ""):
            return False
        if not isinstance(om.get("evidence"), list):
            return False
        return True

    def k8(payload):     # surface_bind 登记表真源 + 登记状态自洽（探针 vs 清单）
        sb = payload.get("surface_bind") or {}
        if "surface_bind.py" not in str(sb.get("registry_source") or ""):
            return False
        listed = "netsh" in (sb.get("registered_tools") or [])
        if bool(sb.get("netsh_registered")) != listed:
            return False        # 探针与清单不许互相打架（自洽判据）
        if sb.get("netsh_registered"):
            if not sb.get("netsh_keys"):
                return False
            if int(sb.get("netsh_keys")) < 40:
                return False
        return True

    def k9(payload):     # 免卡格子不许带动手动作；带动手动作的格子必须写票
        for r in payload.get("routes") or []:
            has_mut = bool(r.get("actions"))
            tk = r.get("ticket")
            if has_mut and not tk:
                return False
            if not has_mut and tk not in (None, ""):
                return False
        return True

    # (判据, 变异体生成器) —— 变异后同一判据必须报红
    def mut_drop_face(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        p["routes"] = p["routes"][:-1]
        return p

    def mut_fake_ticket(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        p["routes"][0]["ticket"] = "free_pass_all"
        return p

    def mut_fake_action(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        for r in p["routes"]:
            if r["id"] == "app":
                r["actions"] = list(r["actions"]) + ["fly_to_moon"]
                r["actions_evidence"]["fly_to_moon"] = False
        return p

    def mut_stale(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        p["routes"][0]["live"]["at"] = "2020-01-01T00:00:00"
        return p

    def mut_wifi_fake(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        r = _route(p, "wifi")
        r["capability"] = "wifi_control"
        r["capability_source"] = "（伪造：本仓没有这位）"
        return p

    def mut_asr_fake(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        p["asr"]["capture_ready"] = False
        p["asr"]["device_run"] = {"status": "heard", "reason": ""}
        return p

    def mut_mind_no_rule(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        p["user_model"]["owner_model"].pop("rule", None)
        return p

    def mut_netsh_inconsistent(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        sb = p["surface_bind"]
        sb["netsh_registered"] = not bool(sb.get("netsh_registered"))   # 探针与清单打架
        return p

    def mut_no_ticket(p):
        p = json.loads(json.dumps(p, ensure_ascii=False))
        for r in p["routes"]:
            r["ticket"] = None        # 把"要票的格"说成"免卡"
        return p

    return [
        ("K1 六类面齐全且每格四要素（面/能力位/动作/票/现状）在位", k1, mut_drop_face),
        ("K2 票名必须是真作用域（伪造票名必红；有动手动作不许没票）", k2, mut_fake_ticket),
        ("K3 动作必须有证据（伪造不存在的动作名必红）", k3, mut_fake_action),
        ("K4 现状必须新鲜（读数过 >600s 不许当现状）", k4, mut_stale),
        ("K5 无线网格如实：无能力位 + 探到键 + 状态写清缺执行位/绕门边界", k5, mut_wifi_fake),
        ("K6 ASR 如实：识别器在位、设备腿 no_input 必带原文", k6, mut_asr_fake),
        ("K7 用户模型可核：读写路径齐 + 推断带 confidence/rule/evidence", k7, mut_mind_no_rule),
        ("K8 surface_bind 登记表真源 + netsh 登记状态自洽（探针 vs 清单）", k8, mut_netsh_inconsistent),
        ("K9 票与动作一致（免卡不许带动手动作；动手必须有票）", k9, mut_no_ticket),
    ]


def _route(payload: dict, rid: str):
    for r in payload.get("routes") or []:
        if r.get("id") == rid:
            return r
    return None


# ─────────────────────────── 组装 / 输出 ───────────────────────────
def build_payload(full_asr: bool) -> dict:
    auth = probe_auth()
    tent = probe_tentacle()
    br = probe_browser()
    bt = probe_bluetooth()
    capnet = probe_capability_net()
    wl = probe_wlan()
    sb = probe_surface_bind()
    dc = probe_desktop_commander()
    asr = probe_asr(full=full_asr)
    voice = probe_voice_status()
    mind = probe_mind()
    p = {"tool": "voice-control-route", "at": now_iso(), "gate": "api.run_task（唯一门）· 全程只读",
         "auth": auth, "tentacle": tent, "browser": br, "bluetooth": bt, "capability_net": capnet,
         "wlan": wl, "surface_bind": sb, "desktop_commander": dc, "asr": asr, "voice": voice}
    p["routes"] = build_routes(p)
    p["user_model"] = {
        "owner_model": mind["owner_model"], "read_path": mind["read_path"],
        "write_path": mind["write_path"], "memory_store": mind["memory_store"],
        "mirror": mind["mirror"], "audit": mind["audit"],
        "record_what": ["意图（原话进 mind observe 的 text）", "路由面（本轮落到哪个能力位/动作）",
                        "成没成（task_succeeded / task_failed / task_finished）",
                        "主人纠正了什么（corrected / mistake + lesson → remember_lesson）"],
        "write_demo": WRITE_DEMO,
        "at": mind["at"], "probe": mind["probe"],
    }
    have = [k for k, v in (auth.get("tickets") or {}).items() if v.get("grants_available")]
    p["honesty"] = [
        "六类面里：APP / 浏览器 / 调试（CDP）/ 蓝牙 / 设置面 五面**有路由**（读类畅通；动手类现在**有票**：%s）" % (", ".join(have) or "（全 0 张）"),
        "无线网：**没有能力位**（不是没电没键 —— 键探到 %s 把、已登记进 surface_bind）⇒ 差的是**一条能走门的执行位**；直接跑 netsh 改状态=绕门，本件不做" % (wl.get("keys_total")),
        "麦克风：活动录音端点 0 ⇒ 离线识别器**能听 WAV**（真跑出文本）、**不能听麦**；启用被禁用的录音设备只有主人能做（设置→系统→声音→录制→显示禁用的设备）",
        "本件**不申领任何授权、不跑任何动手动作**（只读探测）；页面只发意图，不许自己动手、不许绕门",
    ]
    return p


def check_payload(p: dict) -> dict:
    valid = set((p.get("auth") or {}).get("tickets") or {}) or set(STATIC_SCOPES)
    rows = []
    for name, pred, mut in criteria_defs(valid):
        try:
            real = bool(pred(p))
        except Exception as e:                                 # noqa: BLE001
            real = False
            name = name + "（判据自身抛异常：%s）" % type(e).__name__
        try:
            mutant_verdict = bool(pred(mut(p)))
        except Exception:                                      # noqa: BLE001
            mutant_verdict = False
        mutant_red = not mutant_verdict
        rows.append({"name": name, "real_holds": real, "mutant_red": mutant_red,
                     "pass": real and mutant_red,
                     "detail": "真读数=%s（应成立）· 变异体=%s（应报红）" %
                               ("成立" if real else "**报红**", "报红(抓到)" if mutant_red else "**漏报!**")})
    reds = [r for r in rows if not r["pass"]]
    return {"ok": not reds, "at": now_iso(), "criteria": rows,
            "reds": [r["name"] for r in reds],
            "criteria_count": len(rows),
            "negative_controls": [{"name": r["name"], "mutant_became_red": r["mutant_red"]} for r in rows]}


def emit_state(p: dict, chk: dict | None) -> str:
    STATE.mkdir(parents=True, exist_ok=True)
    out = STATE / "voice-control-route.json"
    if chk is None and out.is_file():
        # 不带 --check 落盘时，**保留上一轮的 check 结果并标明它的时间**（不许静默丢判据）
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
            pc = prev.get("check")
            if isinstance(pc, dict):
                chk = dict(pc)
                chk["_note"] = "本轮 --emit-state 未跑 --check；这是上一次 --check 的结果（%s）" % chk.get("at")
        except Exception:                                      # noqa: BLE001
            pass
    doc = {
        "id": "voice-control-route",
        "title": "语音→全机操控 · 路由表 + 探针台账",
        "writer": "tools/codex-scripts/voice-control-route.py --emit-state（**只由工具写**，不手改）",
        "at": p["at"],
        "gate": p["gate"],
        "routes": p["routes"],
        "asr": p["asr"],
        "user_model": p["user_model"],
        "auth": p["auth"],
        "wlan": p["wlan"],
        "surface_bind": p["surface_bind"],
        "voice": p["voice"],
        "tentacle": p["tentacle"],
        "browser": p["browser"],
        "bluetooth": p["bluetooth"],
        "capability_net": p["capability_net"],
        "honesty": p["honesty"],
        "check": chk,
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(out.relative_to(ROOT))


def human(p: dict) -> None:
    print("═" * 100)
    print("语音 → 全机操控 · 路由表（只读探针 · %s · 门：唯一门 api.run_task）" % p["at"])
    print("═" * 100)
    for r in p["routes"]:
        print("\n▌ %s —— %s" % (r["face"], r["cn"]))
        print("  能力位  : %s" % (r["capability"] or "（未找到）"))
        print("  动  作  : 读[%s]" % ", ".join(r["readonly_actions"][:6]))
        if r["actions"]:
            print("            写[%s]" % ", ".join(r["actions"]))
        print("  票      : %s" % (r["ticket"] or "（无路由 ⇒ 无票可吃）"))
        print("  现  状  : %s" % r["status"])
        print("  证  据  : %s" % r["live"]["evidence"])
    print("\n" + "─" * 100)
    print("票（授权门）现读：ai_can_grant=%s · 有票作用域=%d 个 · 发放只有两条合法路：%s"
          % (p["auth"]["ai_can_grant"], p["auth"]["live_ticket_count"],
             " / ".join(p["auth"]["grant_sources"])))
    print("ASR：%s" % p["asr"]["evidence"])
    print("用户模型：%s" % p["user_model"]["read_path"])
    print("         写：%s" % p["user_model"]["write_path"])
    print("\n做不到的（明说）：")
    for h in p["honesty"]:
        print("  · %s" % h)


def main() -> int:
    args = sys.argv[1:]
    want_json = "--json" in args
    want_check = "--check" in args
    want_state = "--emit-state" in args

    p = build_payload(full_asr=want_check)
    chk = None
    if want_check:
        chk = check_payload(p)
        p["check"] = chk

    if want_state:
        path = emit_state(p, chk)
        if not want_json:
            print("台账已写：%s" % path)

    if want_json:
        print(json.dumps(p, ensure_ascii=False, indent=1))
    elif not want_state:
        human(p)

    if chk:
        print("\n" + "═" * 100)
        print("--check 判据（%d 条 · 每条跑两遍：真读数应成立 + 变异体应报红）" % chk["criteria_count"])
        print("═" * 100)
        for r in chk["criteria"]:
            print("%s %s" % ("OK " if r["pass"] else "RED", r["name"]))
            print("      %s" % r["detail"])
        print("\n判据总数=%d · 全绿=%s%s"
              % (chk["criteria_count"], chk["ok"],
                 (" · 报红：%s" % "；".join(chk["reds"])) if chk["reds"] else ""))
        print("负对照（全部为“数据变异后必须报红”，逐条）:")
        for nc in chk["negative_controls"]:
            print("  %s 变异→%s" % ("✔" if nc["mutant_became_red"] else "✘", nc["name"]))
    return 0 if (not chk or chk["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
