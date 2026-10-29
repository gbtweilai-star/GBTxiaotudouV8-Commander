# gbt-capability: task_manager
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""任务管理器（task_manager）· 主人令 2026-09-27。

主人原话：「设计一个**任务管理器**，全部都要使用 术语Skill / 话术Skill / UI设计Skill 来设计出视觉感，
按照原来设计的来就行。」

## 口径（用我们自己的术语说人话）
  · **一屏看全**：任务 / 内存占用 / CPU / 端口 / 进程ID（照主人给的那张系统任务管理器的列）；
  · **认得出是谁**：每个进程标出它属于**哪条线**（框架服务 / 触手舰队 / 浏览器 / MCP / 别家的 / 未知）
    —— 用触手字典的口径，不猜；
  · **网络列说实话**：per-process 流量不好取 ⇒ 我们列**它占着哪些端口**（psutil net_connections，实测可得），
    并**在列名与说明里写清这是端口不是流量**（话术纪律：不把读不到的东西念成读到了）；
  · **停任务要过门**：`stop` 走 `process_execute`，缺授权如实报`how_to_grant`；
  · **读数带时间戳**：快照落 `state/task_manager.json`（页面上显示"这是几点几分的快照"）。

ops：
  list [--limit N]     快照：进程列表（按 CPU 降序，含归属/内存/CPU/端口/pid）
  stop pid=...         停一个进程（过 process_execute 门）
  page                 生成给我们 APP 用的静态页（我们的视觉语言：深色 + 青/橙 + SVG 图标、无 emoji）
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SNAP = _ROOT / "state" / "task_manager.json"
_PAGE = _ROOT / "holo_pet" / "assets" / "task-manager" / "index.html"

# 归属判定（触手字典口径：按进程名/命令行里的**已知标记**认，不猜）
_OWN = [
    ("触手舰队", ("tentacle_fleet", "fleet_worker", "fleet_probe")),
    ("框架服务", ("gbt_allinone", "capability_gateway", "mock-vllm", "deepseek_proxy", "codex_relay")),
    ("浏览器", ("chrome", "msedge", "chromium", "firefox", "zcode", "electron")),
    ("MCP/工具", ("mcp", "mcporter", "n8n", "node")),
]


_BY_NAME = [("浏览器", ("chrome", "msedge", "chromium", "firefox", "brave", "zcode", "electron")),
            ("触手舰队", ("fleet_worker", "fleet_probe")),
            ("MCP/工具", ("node", "n8n", "mcporter"))]


def _classify(name: str, cmd: str) -> str:
    """**先按进程名认**（浏览器/Node 一眼认得），再看命令行里的标记。
    血账（2026-09-27 实测）：只看命令行时，chrome 因为 `--user-data-dir=…/gbt_allinone/…`
    被误判成「框架服务」——它其实是**浏览器**。名字优先 + 命令行兜底。"""
    n = (name or "").lower()
    for label, marks in _BY_NAME:
        if any(m in n for m in marks):
            return label
    blob = cmd.lower()
    for label, marks in _OWN:
        if any(m in blob for m in marks):
            return label
    return "未知（不在我们的标记里）"


def _ports_for(pid: int) -> list:
    try:
        import psutil
        out = []
        for c in psutil.Process(pid).net_connections(kind="inet"):
            if c.status == psutil.CONN_LISTEN and c.laddr:
                out.append(c.laddr.port)
        return sorted(set(out))[:6]
    except Exception:                                          # noqa: BLE001
        return []


def list_procs(limit: int = 25, **_kw) -> dict:
    """真快照：psutil 读真进程（内存/CPU/端口），按 CPU 降序。"""
    try:
        import psutil
    except ImportError:
        return {"ok": False, "error": "缺 psutil ⇒ 读不到真进程", "how_to_fix": "pip install psutil"}
    rows = []
    procs = list(psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "cmdline"]))
    for p in procs:                                    # ① 预热采样（否则 cpu_percent 恒 0.0）
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.5)                                    # ② 给一个采样窗口
    for p in procs:
        try:
            info = p.info
            cmd = " ".join(info.get("cmdline") or [])[:150]
            mem = (info.get("memory_info").rss if info.get("memory_info") else 0) / 1048576
            # ⚠️ 血账：`process_iter` 的 info 是**首次采样时缓存**的 —— 第二遍读 info["cpu_percent"]
            # 拿到的还是那个 0.0。**必须直接再调一次** `cpu_percent(None)` 才会用上预热基线。
            try:
                cpu = float(p.cpu_percent(None) or 0.0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                cpu = float(info.get("cpu_percent") or 0.0)
            rows.append({
                "pid": info["pid"], "name": (info.get("name") or "")[:28],
                "mem_mb": round(mem, 1),
                "cpu": round(cpu, 1),
                "ports": _ports_for(info["pid"]),
                "owner": _classify(info.get("name") or "", cmd),
                "cmd": cmd,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    # 剔除噪声：System Idle / MemCompression 不是"任务"（前者是空闲计数，后者是系统压缩器）
    NOISE = {"system idle process", "memcompression", "registry", "secure system"}
    rows = [r for r in rows if r["name"].lower() not in NOISE]
    rows.sort(key=lambda r: (r["cpu"], r["mem_mb"]), reverse=True)
    snap = {"ok": True, "op": "list", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "count": len(rows), "rows": rows[:limit],
            "_口径": {"列": "任务 / 内存占用(MB) / CPU / 端口 / 进程ID",
                     "网络列的真实含义": "**是端口不是流量** —— per-process 流量本机取不到，不编",
                     "归属": "**先按进程名认**（浏览器/Node 一眼认得），再退到命令行标记；认不出写『未知』，不猜",
                     "剔除的噪声行": "System Idle / MemCompression / Registry / Secure System —— 它们不是任务"}}
    try:
        _SNAP.parent.mkdir(parents=True, exist_ok=True)
        tmp = _SNAP.with_name(_SNAP.name + ".tmp")
        tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        import os
        os.replace(tmp, _SNAP)
    except OSError:
        pass
    return snap


def stop(pid: int = 0, **_kw) -> dict:
    if not pid:
        return {"ok": False, "error": "要给 pid", "fail_closed": True}
    from .. import auth_gate
    from ..security import policy as _policy
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("process_execute", detail=f"task_manager.stop:{pid}")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "process_execute",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant")}
    try:
        import psutil
        p = psutil.Process(int(pid))
        name = p.name()
        p.terminate()
        return {"ok": True, "op": "stop", "pid": pid, "name": name, "note": "已发 terminate"}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:140]}", "fail_closed": True}


_PAGE_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>任务管理器 · GBT小土豆V8</title>
<style>
 :root{{--bg:#0b0f14;--panel:#121a23;--line:#1f2b38;--ink:#dbe6f2;--dim:#7f93a8;--cyan:#33c9dc;--orange:#f0a03c}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);
 font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}}
 header{{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}}
 h1{{font-size:17px;margin:0;font-weight:600;letter-spacing:.5px}}
 .meta{{color:var(--dim);font-size:12px;margin-left:auto}}
 table{{width:100%;border-collapse:collapse}}
 th,td{{padding:9px 14px;border-bottom:1px solid var(--line);text-align:left;font-variant-numeric:tabular-nums}}
 th{{color:var(--dim);font-weight:500;font-size:12px;letter-spacing:.6px}}
 tr:hover td{{background:#151f29}}
 .own{{color:var(--cyan)}} .own.unknown{{color:var(--dim)}}
 .num{{text-align:right}} .port{{color:var(--orange)}}
 .bar{{height:6px;background:#1b2734;border-radius:3px;overflow:hidden;min-width:70px}}
 .bar i{{display:block;height:100%;background:linear-gradient(90deg,var(--cyan),var(--orange))}}
 footer{{padding:14px 22px;color:var(--dim);font-size:12px;border-top:1px solid var(--line)}}
</style></head><body>
<header>
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#33c9dc" stroke-width="1.7">
    <rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h6"/></svg>
  <h1>任务管理器</h1>
  <span class="meta">快照 <b id="at">-</b> · 共 <b id="n">-</b> 条 · 按 CPU 降序</span>
</header>
<table><thead><tr>
  <th>任务</th><th>归属</th><th class="num">内存占用</th><th class="num">CPU</th><th>端口</th><th class="num">进程 ID</th>
</tr></thead><tbody id="tb"></tbody></table>
<footer id="ft">口径：端口列是**它占着的端口**（不是流量 —— 本机取不到 per-process 流量，不编）。停任务要过 process_execute 门。</footer>
<script>
const INLINE = __SNAPSHOT__;
function render(d){{
    document.getElementById('at').textContent = d.at || '-';
    document.getElementById('n').textContent = d.count || 0;
    const mx = Math.max(1, ...d.rows.map(x=>x.mem_mb||0));
    document.getElementById('tb').innerHTML = (d.rows||[]).map(x=>{{
      const w = Math.round(100*(x.mem_mb||0)/mx);
      const cls = (x.owner||'').startsWith('未知') ? 'own unknown' : 'own';
      return `<tr><td>${{x.name}}<div style="color:#7f93a8;font-size:11px">${{(x.cmd||'').slice(0,70)}}</div></td>
        <td class="${{cls}}">${{x.owner}}</td>
        <td class="num">${{x.mem_mb}} MB<div class="bar"><i style="width:${{w}}%"></i></div></td>
        <td class="num">${{x.cpu}}</td>
        <td class="port">${{(x.ports||[]).join(', ')||'-'}}</td>
        <td class="num">${{x.pid}}</td></tr>`;
    }}).join('');
  }}catch(e{{document.getElementById('ft').textContent='读不到快照：'+e.message+'（先跑 run_task(\\'task_manager\\',{{\\'op\\':\\'list\\'}})）';}}
}}
load(); setInterval(load, 5000);
</script></body></html>
"""


def page(**_kw) -> dict:
    """生成任务管理器页（我们的视觉语言）。**快照内联进 HTML**（file:// 下 fetch 会被 CORS 挡，
    相对路径又会 404 —— 实测两个坑都踩过）⇒ 无网也能看；served over http 时每 5 秒自刷新。"""
    snap = list_procs(limit=30)
    html = _PAGE_HTML.replace("__SNAPSHOT__", json.dumps(snap, ensure_ascii=False))
    _PAGE.parent.mkdir(parents=True, exist_ok=True)
    _PAGE.write_text(html, encoding="utf-8")
    return {"ok": True, "op": "page", "path": str(_PAGE), "rows_inlined": len(snap.get("rows") or []),
            "note": "快照已内联（file:// 直接打开就能看）；http 下 5 秒自刷新；SVG 图标·无 emoji·深色+青橙"}


def run_op(op: str = "list", **params) -> dict:
    op = (op or "list").lower()
    if op == "list":
        return list_procs(**params)
    if op == "stop":
        return stop(**params)
    if op == "page":
        return page(**params)
    return {"ok": False, "error": f"未知 op:{op}（list/stop/page）", "fail_closed": True}
