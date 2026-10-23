# gbt-capability: sec_sweeper
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""安全棒（sec_sweeper）· 主人令 2026-09-27。

主人原话：「设计一根触手做**安全棒**，**每半天**调用万能插进行**全量穿透式交叉无死角扫描**，
各种代码病因、病毒、木马一系列所有问题都要排查；以及一个**独立的健康面板显示屏**，
发现任何异常都要**报警提示**；设立一个专门的**密钥填装 / 安全帮的启动能源连接口**；
其他都是**同步记忆上下文**，这样本体就不需要一直读取和多扫一遍了。」

## 它是什么
一根**专职安全触手**：自己不算，**把我们的尺子挨个过一遍唯一门**（这符合"写/跑动作走 run_task"），
把结果收成**一份健康账**，异常就**报警**。

## 四件事（对应主人四句话）
1. **每半天全量**：`start` 跑全套 —— 穿透式交叉扫描（钩子/步骤锁/交叉验证/遗漏补扫）、
   安全模式分诊（eval/exec/shell/凭据/反序列化…）、覆盖矩阵（无死角）、双向绑定、技能源↔装；
2. **独立健康面板**：`panel` 出一块**自带报警**的屏（快照内联，没网也能看）；
3. **专用口子**：`keys`（装/查密钥 —— **只走引用与掩码**，值不进仓）+
   `energy`（启动能源检查：能源池 + 免费池真连一次）+ `start`（三样齐了才开跑）；
4. **同步记忆上下文**：`state/sec_sweeper_ctx.json` 记**每棵树的指纹**（文件数/最新mtime/总字节）——
   指纹没变 ⇒ **复用上次结果**并把"复用"标出来；变了才真扫。
   ⇒ 这就是"本体不用一直读取、不用多扫一遍"：**扫一次，记上下文，下次只补差**。

ops：
  start [full=false]   一键：能源 → 密钥 → 增量全量扫描 → 健康账 → 报警
  sweep                只跑扫描（增量；full=true 强制全量）
  keys                 专用口：填装/查看密钥（**引用 + 掩码**；值走 model_key_pool 的 DPAPI）
  energy               启动能源检查（能源池读数 + 免费池真连一次）
  panel                生成健康面板（报警内置）
  health               读当前健康账（人读/机读）
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_CTX = _STATE / "sec_sweeper_ctx.json"
_HEALTH = _STATE / "health.json"
_LEDGER = _STATE / "health_ledger.jsonl"
_PANEL = _ROOT / "holo_pet" / "assets" / "health-panel" / "index.html"

# 扫哪些树（顶层；与覆盖矩阵同一口径：**排除必须带理由**）
TREES = ["gbt_allinone", "tools", "skills", "docs", "state", "memory", "deploy",
         "projects", "holo_pet", "holo_pet_w3", "plugins", "config", "potato_pet"]
EXCLUDED = {
    ".git": "版本库本体（被审计的账，不是被扫的面）",
    "_upstream": "第三方参考仓（只读、永不入史）",
    "vendor": "第三方内嵌运行时（可由 requirements 重建）",
    "dist": "构建产物",
    ".fleet": "触手舰队工作区（每根一份 worktree 副本）",
    ".trash": "暂存区",
    ".backups": "备份区（覆盖前留档）",
}


def _engine():
    sp = importlib.util.spec_from_file_location("pcs_ss", _ROOT / "tools" / "penetrating_cross_scan.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _gate(kind: str, payload: dict) -> dict:
    """过唯一门（写/跑动作一律走 run_task）。"""
    import sys
    sys.path.insert(0, str(_ROOT))
    import gbt_allinone as g
    r = g.run_task(kind, payload)
    d = r.get("result") if isinstance(r, dict) else None
    while isinstance(d, dict) and isinstance(d.get("result"), dict) and set(d) <= {"status", "kind", "result", "ok"}:
        d = d["result"]
    return {"gate_ok": bool(isinstance(r, dict) and r.get("ok", True)), "payload": d}


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def _save(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _tree_fp(name: str) -> dict:
    """**便宜指纹**（不 hash 全文）：文件数 + 最新 mtime + 总字节。变了才真扫。"""
    d = _ROOT / name
    if not d.is_dir():
        return {"exists": False}
    n = total = 0
    newest = 0.0
    for dp, dns, fns in os.walk(d, onerror=lambda e: None):
        dns[:] = [x for x in dns if x not in (".git", "__pycache__", "node_modules", ".pylibs")]
        for f in fns:
            p = Path(dp) / f
            try:
                st = p.stat()
            except OSError:
                continue
            n += 1
            total += st.st_size
            newest = max(newest, st.st_mtime)
    return {"exists": True, "files": n, "bytes": total, "newest_mtime": round(newest, 1)}


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def energy(**_kw) -> dict:
    """启动能源：能源池读数 + 免费池**真连一次**（只读、不花积分）。"""
    pool = _gate("energy_pool", {"op": "status"})
    ak = _gate("automation_keys", {"op": "test", "slot": "free_pool"})
    ents = (pool.get("payload") or {}).get("count")
    free = (ak.get("payload") or {}).get("results") or []
    free_ok = bool(free and free[0].get("ok"))
    return {"ok": True, "op": "energy", "energy_sources": ents,
            "free_pool_reachable": free_ok, "detail": free[:1],
            "tier_unknown_note": "能源池 tier 仍为 unknown（「免费优先」还没生效）—— 已知缺口，等主人一句话"}


def keys(slot: str = "", ref: str = "", **_kw) -> dict:
    """**专用密钥口**：装/查密钥。三条硬口径 —— 只走**引用**、只回**掩码**、写值走 model_key_pool。
    ⚠️ 按安全约束：**源码/示例/测试里零凭据字面量**；这里只接受 `env:<名>` / `vault:<profile>` / `local`。"""
    if slot and ref:
        return _gate("automation_keys", {"op": "set", "slot": slot, "ref": ref})
    st = _gate("automation_keys", {"op": "status"})
    return {"ok": True, "op": "keys", "readonly": True, "status": st.get("payload"),
            "how_to_set": "keys(slot='<槽位>', ref='env:VAR_NAME') —— 只装引用；真值走 model_key_pool(DPAPI)"}


def sweep(full: bool = False, trees: list | None = None, **_kw) -> dict:
    """全量穿透式交叉扫描（**增量**）：指纹没变 ⇒ 复用上次结果（标出来），变了才真扫。"""
    eng = _engine()
    ctx = _load(_CTX, {"trees": {}})
    targets = trees or TREES
    results, reused, scanned, alerts = {}, 0, 0, []
    for t in targets:
        fp = _tree_fp(t)
        prev = (ctx.get("trees") or {}).get(t) or {}
        if not full and prev.get("fp") == fp and prev.get("ok") is not None:
            results[t] = {**prev, "reused": True}
            reused += 1
            continue
        try:
            r = eng.run_pipeline(f"tree:{t}")
            sec = r.get("security", {}) or {}
            row = {"fp": fp, "units": r.get("units"), "coverage": r.get("coverage"),
                   "missing": len(r.get("missing") or []),
                   "sec_needs_human": sec.get("needs_human", 0),
                   "sec_flagged": sec.get("flagged", 0),
                   "ok": bool(r.get("ok")), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "reused": False}
        except Exception as e:                                  # noqa: BLE001
            row = {"fp": fp, "ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}",
                   "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "reused": False}
        results[t] = row
        scanned += 1
        if not row.get("ok") or (row.get("sec_needs_human") or 0) > 0:
            alerts.append(f"{t}: 覆盖={row.get('coverage')} · 未钩住={row.get('missing')} · "
                          f"需人核={row.get('sec_needs_human')}")
    # 三个横切面（也走唯一门）
    cross = {}
    for kind, payload in (("hook_enforcer", {"op": "report", "tail": 3}),
                          ("omission_detector", {"op": "report", "tail": 3}),
                          ("automation_keys", {"op": "status"})):
        try:
            g = _gate(kind, payload)
            cross[kind] = {"gate_ok": g.get("gate_ok")}
        except Exception as e:                                  # noqa: BLE001
            cross[kind] = {"gate_ok": False, "error": str(e)[:100]}
            alerts.append(f"{kind}: 过门失败 {str(e)[:80]}")
    ctx["trees"] = {k: v for k, v in results.items()}
    ctx["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save(_CTX, ctx)
    out = {"ok": not alerts, "op": "sweep", "at": ctx["last_run"],
           "trees_total": len(targets), "scanned": scanned, "reused": reused,
           "alerts": alerts, "results": results, "cross": cross,
           "_口径": "**增量**：每棵树记指纹（文件数/最新mtime/总字节）；指纹未变 ⇒ 复用上次结果并标 reused=true；"
                   "扫的面与覆盖矩阵同口径，排除项带理由（.git/_upstream/vendor/dist/.fleet/.trash/.backups）"}
    _log({"event": "sweep", "scanned": scanned, "reused": reused, "alerts": len(alerts)})
    return out


def start(full: bool = False, **_kw) -> dict:
    """一键：能源 → 密钥 → 扫描 → 健康账 → 报警。"""
    e = energy()
    k = keys()
    s = sweep(full=full)
    ready = [x for x in ((k.get("status") or {}).get("slots") or []) if x.get("present")]
    # ── 成长栈四面 + 控制回路护栏（安全棒每轮都过一遍 ⇒ 这些能力位有常设调用者，
    #    也是主人令「每半天全量穿透式扫描」要覆盖的面）──
    growth, galerts = {}, []
    # 进程面（task_manager）：框架自己的进程数 + 端口占用者数 —— 异常增长是要看的
    tm = _gate("task_manager", {"op": "list", "limit": 400}).get("payload") or {}
    if tm.get("ok"):
        # ⚠️ 口径：按**行**数（进程条数）与**归属**统计；端口列是"占了哪些口"不是流量（那是它的老口径）
        rows = tm.get("rows") or []
        by_line = {}
        port_owners = 0
        for r in rows:
            # ⚠️ 血账：字段名是 **owner**（我先前猜成 line/归属 ⇒ 329 条全落"未分类"）。
            #   键名不一致的亏在本仓吃过好几次：先读形状再取数，别猜字段。
            line = str(r.get("owner") or "未分类")
            by_line[line] = by_line.get(line, 0) + 1
            if r.get("ports"):
                port_owners += 1
        growth["进程面"] = {"ok": True, "行": len(rows), "端口占用者": port_owners,
                            "按线": by_line}
        fw = by_line.get("框架服务", 0)
        if fw > 40:
            galerts.append(f"[进程面] 框架服务进程 {fw} 个（偏多，看一眼是谁）")
    # 创作页面与服务（gods_eye.see）：自家门面在不在、服务在不在听
    eye = _gate("gods_eye", {"op": "see"}).get("payload") or {}
    if eye.get("pages_total"):
        growth["门面"] = {"ok": eye.get("pages_ok") == eye.get("pages_total"),
                          "页面": f"{eye.get('pages_ok')}/{eye.get('pages_total')}",
                          "服务在听": eye.get("services_up")}
        if (eye.get("pages_ok") or 0) < (eye.get("pages_total") or 0):
            galerts.append("[门面] 有创作页面不在盘上 ⇒ 跑 gods_eye see 看是哪个")
    for kind, op, key in (("obsidian_vault", "verify", "永久记忆"),
                          ("devour_fusion", "verify", "吞天融合"),
                          ("cap_tags", "verify", "标签许可"),
                          ("growth_hooks", "verify", "成长钩子"),
                          ("control_loop", "status", "控制回路")):
        r = _gate(kind, {"op": op}).get("payload") or {}
        ok = bool(r.get("ok")) if kind != "control_loop" else True
        growth[key] = {"ok": ok, "problems": (r.get("problems") or [])[:3]}
        for pr in (r.get("problems") or [])[:2]:
            galerts.append(f"[{key}] {str(pr)[:120]}")
    health = {"ok": bool(s.get("ok")), "at": s.get("at"),
              "energy": {"sources": e.get("energy_sources"), "free_pool": e.get("free_pool_reachable")},
              "keys_ready": len(ready), "keys_total": len((k.get("status") or {}).get("slots") or []),
              "trees": s.get("results"), "alerts": (s.get("alerts") or []) + galerts,
              "growth": growth,
              "scanned": s.get("scanned"), "reused": s.get("reused"),
              "_口径": "健康=无报警；报警项逐条写清（树/覆盖/未钩住/需人核/成长栈四面）"}
    _save(_HEALTH, health)
    _log({"event": "start", "ok": health["ok"], "alerts": len(health["alerts"])})
    return {"ok": health["ok"], "op": "start", "health": health,
            "alerts": health["alerts"]}


def health(**_kw) -> dict:
    return _load(_HEALTH, {"ok": None, "note": "还没有健康账 ⇒ 先跑 start"})


_PANEL_HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>健康面板 · GBT小土豆V8</title><style>
 :root{--bg:#0b0f14;--panel:#121a23;--line:#1f2b38;--ink:#dbe6f2;--dim:#7f93a8;--cyan:#33c9dc;--orange:#f0a03c;--red:#e5484d;--green:#3fb950}
 *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}
 header{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center}
 h1{font-size:17px;margin:0;font-weight:600}
 .pill{margin-left:auto;padding:3px 10px;border-radius:11px;font-size:12px;border:1px solid var(--line)}
 .ok{color:var(--green);border-color:#1d3a26;background:#0f1c14} .bad{color:var(--red);border-color:#4a1d1f;background:#1c0f10}
 .wrap{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;padding:18px 22px}
 .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
 .card h2{font-size:13px;margin:0 0 8px;color:var(--dim);font-weight:500;letter-spacing:.5px}
 .big{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
 .alerts{margin:8px 0 0;padding:0;list-style:none}
 .alerts li{color:var(--red);font-size:12.5px;padding:4px 0;border-top:1px solid #241a1b}
 table{width:100%;border-collapse:collapse;margin-top:6px}
 th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:12.5px}
 th{color:var(--dim);font-weight:500} .num{text-align:right}
 .reuse{color:var(--dim)} .warn{color:var(--orange)}
 footer{padding:14px 22px;color:var(--dim);font-size:12px;border-top:1px solid var(--line)}
</style></head><body>
<header>
 <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#33c9dc" stroke-width="1.7"><path d="M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z"/><path d="M9 12l2 2 4-4"/></svg>
 <h1>健康面板 · 安全棒</h1>
 <span class="pill" id="verdict">-</span>
</header>
<div class="wrap">
 <div class="card"><h2>本 次 扫 描</h2><div class="big" id="scanned">-</div>
   <div id="reuse"></div>
   <div class="card" style="margin-top:10px;background:#0e151d"><h2>能 源 / 密 钥</h2><div id="ek"></div></div>
 </div>
 <div class="card" style="grid-column:span 2"><h2>异 常 报 警</h2><ul class="alerts" id="alerts"></ul>
   <table><thead><tr><th>树</th><th class="num">单元</th><th class="num">覆盖</th><th class="num">未钩住</th><th class="num">需人核</th><th>状态</th></tr></thead>
   <tbody id="tb"></tbody></table>
 </div>
</div>
<footer id="ft">口径：健康=无报警；**覆盖必须 1.0**；排除项带理由（.git/_upstream/vendor/dist/.fleet/.trash/.backups）。</footer>
<script>
const INLINE = __SNAPSHOT__;
function render(d){
  if(!d || !d.at){document.getElementById('ft').textContent='还没有健康账 —— 先跑 run_task(\\'sec_sweeper\\',{\\'op\\':\\'start\\'})';return;}
  const ok = !!d.ok;
  const v = document.getElementById('verdict');
  v.textContent = ok ? '正常' : ('报警 ' + (d.alerts||[]).length + ' 项');
  v.className = 'pill ' + (ok ? 'ok' : 'bad');
  document.getElementById('scanned').textContent = (d.scanned ?? '-') + ' 棵真扫';
  document.getElementById('reuse').innerHTML = '<span class="reuse">复用上下文（指纹未变）' + (d.reused ?? 0) + ' 棵 —— 没重扫</span>';
  const e = d.energy || {};
  document.getElementById('ek').innerHTML = '能源源 <b>' + (e.sources ?? '-') + '</b> · 免费池 ' +
    (e.free_pool ? '<span style="color:var(--green)">可达</span>' : '<span class="warn">不可达</span>') +
    '<br>密钥就绪 <b>' + (d.keys_ready ?? '-') + '</b>/' + (d.keys_total ?? '-') + ' 槽';
  const al = d.alerts || [];
  document.getElementById('alerts').innerHTML = al.length ? al.map(x=>'<li>'+x+'</li>').join('') : '<li style="color:var(--green)">无报警</li>';
  document.getElementById('tb').innerHTML = Object.entries(d.trees||{}).map(([k,r])=>{
    const warn = (r.coverage ?? 1) < 1 || (r.sec_needs_human||0) > 0;
    return '<tr><td>'+k+'</td><td class="num">'+(r.units ?? '-')+'</td><td class="num'+(warn?' warn':'')+'">'+(r.coverage ?? '-')+
      '</td><td class="num">'+(r.missing ?? 0)+'</td><td class="num">'+(r.sec_needs_human ?? 0)+
      '</td><td>'+(r.reused ? '<span class="reuse">复用</span>' : '真扫')+(r.error ? ' <span class="warn">'+((''+r.error).slice(0,40))+'</span>' : '')+'</td></tr>';
  }).join('');
}
render(INLINE);
async function refresh(){ try{ const r = await fetch('state/health.json', {cache:'no-store'}); render(await r.json()); }catch(e){} }
setInterval(refresh, 10000);
</script></body></html>
"""


def panel(**_kw) -> dict:
    h = _load(_HEALTH, {})
    html = _PANEL_HTML.replace("__SNAPSHOT__", json.dumps(h, ensure_ascii=False))
    _PANEL.parent.mkdir(parents=True, exist_ok=True)
    _PANEL.write_text(html, encoding="utf-8")
    return {"ok": True, "op": "panel", "path": str(_PANEL),
            "alerts": len(h.get("alerts") or []),
            "note": "快照内联（file:// 直接看）；http 下 10 秒自刷新；异常项在最上方红色列出"}



# ── 框架垃圾清理 + 加速（主人 2026-09-27 追加：「都要安全棒来做」）──────────────
# 垃圾口径：**教科书级可弃**（缓存/临时/空壳/过期备份），逐类给理由；**默认干跑**，真删过 filesystem_write 门。
JUNK_RULES = [
    ("字节码缓存", lambda p: p.is_dir() and p.name == "__pycache__", "可重建；清它省目录遍历与 stat"),
    ("测试/类型检查缓存", lambda p: p.is_dir() and p.name in (".pytest_cache", ".mypy_cache", ".ruff_cache"), "工具缓存，可重建"),
    ("临时件", lambda p: p.is_file() and p.suffix.lower() in (".tmp", ".temp", ".bak", ".orig", ".rej"), "临时/备份散件"),
    ("空壳目录", lambda p: p.is_dir() and not any(p.iterdir()), "空目录是残骸"),
]


def tidy(dry: bool = True, **_kw) -> dict:
    """框架垃圾清理：逐类清点 → （非干跑时过门）删除 → 报回收量。"""
    found, total_bytes = [], 0
    for name, match, why in JUNK_RULES:
        n = b = 0
        hits = []
        for dp, dns, fns in os.walk(_ROOT, onerror=lambda e: None):
            dns[:] = [d for d in dns if d not in (".git", "node_modules", ".pylibs", ".fleet", "_upstream", "vendor")]
            for x in list(dns) + fns:
                p = Path(dp) / x
                try:
                    if match(p):
                        sz = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
                        n += 1
                        b += sz
                        if len(hits) < 3:
                            hits.append(str(p.relative_to(_ROOT))[:60])
                except OSError:
                    continue
        found.append({"class": name, "why": why, "count": n, "bytes": b, "sample": hits})
        total_bytes += b
    if dry:
        return {"ok": True, "op": "tidy", "dry": True, "classes": found,
                "reclaim_bytes": total_bytes, "reclaim_mb": round(total_bytes / 1048576, 1),
                "_口径": "干跑：只清点不删；真删带 dry=false（过 filesystem_write 门）"}
    # ⚠️ 血账：本文件既被 api.py 当包内模块加载、也被 importlib 独立加载测试 ——
    # 相对导入 `from .. import auth_gate` 在**独立加载**时会炸（实测 ImportError）。
    # 走"先相对、后绝对"两条路，两种上下文都能跑。
    try:
        from .. import auth_gate                                   # noqa: F401
        from ..security import policy as _policy
    except ImportError:
        import sys as _sys
        _sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                                   # noqa: F401
        from gbt_allinone import auth_gate                          # type: ignore
        from gbt_allinone.security import policy as _policy         # type: ignore
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write", detail="sec_sweeper.tidy")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant"),
                    "classes": found, "reclaim_mb": round(total_bytes / 1048576, 1)}
    import shutil as _sh
    removed = 0
    for name, match, why in JUNK_RULES:
        for dp, dns, fns in os.walk(_ROOT, onerror=lambda e: None):
            dns[:] = [d for d in dns if d not in (".git", "node_modules", ".pylibs", "_upstream", "vendor")]
            for x in list(dns) + fns:
                p = Path(dp) / x
                try:
                    if match(p):
                        _sh.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    continue
    _log({"event": "tidy", "removed": removed, "reclaim_mb": round(total_bytes / 1048576, 1)})
    return {"ok": True, "op": "tidy", "dry": False, "removed": removed,
            "reclaim_mb": round(total_bytes / 1048576, 1), "classes": found}


def accelerate(warm_index: bool = True, **_kw) -> dict:
    """框架加速：只做**能给出前后两个数**的加速，并如实标注"省的是什么"。"""
    import subprocess
    import sys as _sys
    before = {}
    after = {}
    # ① 资产索引：查询从"扫盘秒级"到"查索引毫秒级"——加速的是**查询**
    try:
        t0 = time.perf_counter()
        _gate("asset_index", {"op": "find", "q": "gbt_allinone", "limit": 1})
        before["query_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if warm_index:
            _gate("asset_index", {"op": "build"})
            t0 = time.perf_counter()
            _gate("asset_index", {"op": "find", "q": "gbt_allinone", "limit": 1})
            after["query_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    except Exception as e:                                      # noqa: BLE001
        before["index_error"] = str(e)[:100]
    # ② 死绑定退账：账干净 ⇒ 后续每次 scan/gaps 更快（省的是**遍历**）
    try:
        d = _load(_STATE / "asset_bindings.json", {})
        missing = [k for k in d if not (_ROOT / k).exists()]
        if missing:
            import importlib.util as _iu
            sp = _iu.spec_from_file_location("tbx", _ROOT / "tools" / "tentacle_bind.py")
            tb = _iu.module_from_spec(sp)
            sp.loader.exec_module(tb)
            for a in missing:
                for k in list((d.get(a) or {}).get("tentacles") or []):
                    tb.unbind(a, k, why="sec_sweeper.accelerate 退账（资产已不在盘上）")
        after["dead_bindings_retired"] = len(missing)
    except Exception as e:                                      # noqa: BLE001
        after["bind_error"] = str(e)[:100]
    _log({"event": "accelerate", **{f"before_{k}": v for k, v in before.items()},
          **{f"after_{k}": v for k, v in after.items()}})
    return {"ok": True, "op": "accelerate", "before": before, "after": after,
            "_口径": "**省的是什么**写清楚：索引加速=查询（不再扫盘）· 死绑定退账=遍历（scan/gaps 更快）；"
                    "不承诺 CPU/网络提升，也不编没有的数"}

def run_op(op: str = "health", **params) -> dict:
    op = (op or "health").lower()
    for name, fn in (("start", start), ("sweep", sweep), ("keys", keys),
                     ("energy", energy), ("panel", panel), ("health", health),
                     ("tidy", tidy), ("accelerate", accelerate)):
        if op == name:
            return fn(**params)
    return {"ok": False, "error": f"未知 op:{op}（start/sweep/keys/energy/panel/health/tidy/accelerate）",
            "fail_closed": True}
