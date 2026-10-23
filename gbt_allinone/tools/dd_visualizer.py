# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""DD小分队 · 立体作战沙盘（Owner 2026-09-19 设计）。

三块信息拼在一起：**中间 3D 战场**（任务节点+连线+指挥核心）·**左下任务板**·**右侧项目树**。

与 Owner 初稿的两处**必修改动**（都有实测依据，不是偏好）：
  1. **不用 CDN，用盘上本地 three**。初稿写 `https://cdn.jsdelivr.net/.../three@0.160.0/build/three.min.js`，
     但实测本地 `holo_pet/node_modules/three/build/` 只有 `three.module.js` / `three.cjs` /
     `three.webgpu.js` —— **r150+ 已移除 UMD 的 `three.min.js`**，那条 URL 会 404，沙盘白屏。
     现改为由本服务转发 `./three/*` 到本地 `node_modules/three`，页面用 ES module import。
  2. **数据走 `/api/data` 轮询，不把 JSON 塞进模板**。少了转义风险，顺带白拿"实时刷新"。

安全口径（必须让主人知情）：
  · 只绑 `127.0.0.1`（不对外）；
  · **这是一个新的监听进程** —— 与"不新建常驻进程"的常规纪律相反，
    因为它是主人**明确要求**的看板。要停就 Ctrl+C，不做自启动。
  · `/api/data` 会**暴露项目树结构**（限深度 3、每层前 50 项）。本机自用；若要外访先加鉴权。

用法：
    python -m gbt_allinone.tools.dd_visualizer --port 8866
    浏览器打开 http://127.0.0.1:8866/
"""
from __future__ import annotations

import argparse
import http.server
import json
import socketserver
from datetime import datetime
from pathlib import Path

DEVELOPER = "自由的风"
BRAND = "DD小分队 · 立体作战沙盘"

# ─────────────────────────────────────────────────────────────
# 导演身份（Owner 2026-09-19 钦定）
# 它本职就是"盯着谁在干活、谁在待命、谁在卡壳" —— 这活儿有名字，叫**导演**。
# 但导演的权限**只有看见**，没有编：
#   她可以指出"这个位置没人"，但**不许把空编点成兵力**来让戏好看；
#   她可以说"这条任务没人交"，但**不许替谁把状态改成已完成**。
# 一句话：**她是唯一看得见全场的人，也是唯一不许改剧本的人。**
# ─────────────────────────────────────────────────────────────
DIRECTOR = {
    "title": "沙盘导演",
    "name": "DD-导演",
    "sees": "兵团在岗/空编 · 任务板状态 · 项目树 · 征召单队列",
    "duty": "一眼看清谁在干活、谁在待命、谁卡住了；只呈现读数，不替谁下结论",
    "power": "看见（只读）",
    "redline": ("空编不点成兵力 · 未测不标绿 · 没有 receipt/report 就不算任务中 · "
                "不代替任何成员交付"),
    "why": ("抓假绿这件事需要一个有人格的岗位，否则它永远只是零散纪律；"
            "导演就是那个岗位 —— 她盯着全场，且她的话必须能追到盘上的文件。"),
}

SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".pytest_cache",
             ".mypy_cache", ".ruff_cache", "store", "archived_logs"}


def _levels(nodes) -> list:
    """把 DAG 折成层（同层可并行）——可视化用的最小拓扑分层，只读、不改数据。

    为什么在这儿算而不让前端算：前端只管画，口径只留一份；
    真有环（`wf_define` 本该拦住）也不许死循环——如实把剩下的塞进最后一层。
    """
    ids = [n.get("id") for n in nodes if n.get("id")]
    deps = {n.get("id"): set(n.get("depends_on") or []) for n in nodes if n.get("id")}
    levels, seen = [], set()
    while len(seen) < len(ids):
        cur = [i for i in ids if i not in seen and not (deps.get(i, set()) - seen)]
        if not cur:
            cur = [i for i in ids if i not in seen]
        levels.append(cur)
        seen.update(cur)
    return levels


def _api_read(kind: str, payload: dict) -> dict:
    """沙盘取数的**唯一口径**（R-H101）——统一接口 + probe=True + 形状固定 + 错误如实。

    · 统一接口：沙盘不自己去翻框架内部账本，改一处两处一起变（口径只留一份）；
    · `probe=True`：看板 5 秒轮询一次，不能把审计刷成一堵墙；
    · 形状固定：`{"ok", "data", "error", "source"}` —— 取不到**只许报原因，不许编**。
    """
    try:
        import sys
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from gbt_allinone import api
        env = api.run_task(kind, dict(payload or {}), probe=True)
        body = env.get("gbt_result", env) if isinstance(env, dict) else {}
        data = body.get("result", body) if isinstance(body, dict) else {}
        status = str((body or {}).get("status") or "")
        if status and status != "ok":
            return {"ok": False, "data": data, "source": kind,
                    "error": str(body.get("error") or body.get("message") or status)}
        return {"ok": True, "data": data, "error": None, "source": kind}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "data": None, "source": kind,
                "error": "%s: %s" % (type(exc).__name__, exc)}


def plug_snapshot(limit: int = 8) -> dict:
    """万能插只读快照（R-H99d）：工作流定义（含分层）+ 最近运行 + 各工作流最近一次节点状态。

    口径（与"导演"同一条）：**只呈现，不执行**。
      · 数据只从统一接口的只读口 `wf_status(include_workflows=True)` 取；
      · 用 `probe=True` 调用 —— 沙盘 5 秒轮询一次，不该把审计刷成一堵墙；
      · 取不到就**如实报错**（`ok:false` + 原因），绝不编一套好看的假数据顶上
        （红线：空编不点成兵力、未测不标绿）。
    """
    try:
        got = _api_read("wf_status", {"limit": limit, "include_workflows": True})
        if not got["ok"]:
            return {"ok": False, "readonly": True, "source": got["source"],
                    "error": got["error"], "workflows": [], "runs": [],
                    "workflow_count": 0, "run_count": 0}
        data = got["data"] or {}
        workflows = [dict(w) for w in (data.get("workflows") or [])]
        runs = list(data.get("runs") or [])

        # 每个工作流挂"最近一次运行"的节点状态（runs 已按时间倒序，取第一条即最近）
        latest = {}
        recent = {}
        for r in runs:
            name = r.get("workflow")
            if name and name not in latest:
                latest[name] = {"run_id": r.get("run_id"), "status": r.get("status"),
                                "nodes": r.get("nodes") or {}, "finished_at": r.get("finished_at"),
                                "elapsed_s": r.get("elapsed_s")}
            if name:
                # 运行行（R-H103）：只给"最近 3 次"，且**缺就空** —— 画面据此说"没有运行记录"。
                bucket = recent.setdefault(name, [])
                if len(bucket) < 3:
                    bucket.append({"run_id": r.get("run_id"), "status": r.get("status"),
                                   "finished_at": r.get("finished_at"),
                                   "elapsed_s": r.get("elapsed_s")})
        for w in workflows:
            w["levels"] = _levels(w.get("nodes") or [])
            w["latest"] = latest.get(w.get("name"), {})
            w["recent"] = recent.get(w.get("name"), [])

        return {"ok": True, "readonly": True, "workflows": workflows, "runs": runs,
                "workflow_count": len(workflows), "run_count": len(runs)}
    except Exception as exc:  # noqa: BLE001 —— 取不到就报原因，不装
        return {"ok": False, "readonly": True, "error": "%s: %s" % (type(exc).__name__, exc),
                "workflows": [], "runs": [], "workflow_count": 0, "run_count": 0}


TOOLCHAIN_MANIFEST = Path(".cluster") / "dd_squad" / "toolchain_manifest.json"


def load_toolchain(root: Path) -> dict:
    """只读加载工具链清单（R-H99e）——与 `launcher_inventory` 同口径：**只呈现，不执行**。

    两个诚实约束（缺一不可）：
      1. **单一来源**：清单只活在 `.cluster/dd_squad/toolchain_manifest.json`，
         可视化不另抄一份（改了文件，沙盘下一轮刷新就跟着变）。
      2. **核实状态如实透出**：清单里 `verified=false` 就照原样报出去 ——
         沙盘不许把"口述清单"画成"已核实可用战力"（同"空编不点成兵力"）。
    """
    path = root / TOOLCHAIN_MANIFEST
    if not path.is_file():
        return {"ok": False, "readonly": True, "verified": False,
                "error": "清单不存在：%s（先落 toolchain_manifest.json，可视化不自己编一份）" % path,
                "groups": {}, "counts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "readonly": True, "verified": False,
                "error": "清单不是合法 JSON：%s: %s" % (type(exc).__name__, exc),
                "groups": {}, "counts": {}}
    groups = data.get("groups") or {}
    counts = {k: len(v or []) for k, v in groups.items()}
    flow = data.get("flow_claim") or {}
    return {"ok": True, "readonly": True,
            "verified": bool(data.get("verified")),
            "verified_note": data.get("verified_note") or "",
            "source": data.get("source") or "",
            "generated_at": data.get("generated_at") or "",
            "groups": groups, "counts": counts, "total": sum(counts.values()),
            "pending_verification": list(data.get("pending_verification") or []),
            # 分层 DAG（R-H101）：层与边**来自清单**，不是代码里另编一套；
            # `flow_verified=false` 表示这套流向只是口述、没实测过 —— 画面必须带这个括号。
            "layers": list(flow.get("layers") or []),
            "edges": [list(e) for e in (flow.get("edges") or [])],
            "flow_note": flow.get("layer_note") or flow.get("note") or "",
            "flow_verified": bool(flow.get("verified")),
            "flow_claim": flow,
            "path": str(path)}


# ── 空间投射技能只读卡片（R-H108）：只呈现，不执行；5/5 原语未核实就照原样报 ──
PROJECTION_MODULE = "gbt_allinone/tools/projection_skill.py"


def projection_snapshot(root: Path) -> dict:
    """空间投射技能卡片（R-H108）——与 `launcher_inventory` 同口径：**只呈现，不执行**。

    两个诚实约束（缺一不可）：
      1. **单一来源**：卡片内容只从 `gbt_allinone/tools/projection_skill.py` 取（那是定义的家）；
         清单（`.cluster/dd_squad/toolchain_manifest.json`）里只放**引用** ——
         两处对不上就**如实报 drift**，不许挑一个好看的报。
      2. **未核实就标未核实**：5/5 原语未核实 ⇒ 画面照原样报，不许把"在"画成"能用"。
    """
    try:
        import sys
        pkg_root = Path(__file__).resolve().parents[2]
        if str(pkg_root) not in sys.path:
            sys.path.insert(0, str(pkg_root))
        from gbt_allinone.tools import projection_skill as PS
        card = PS.skill_card()
    except Exception as exc:  # noqa: BLE001 —— 卡片读不出来就报原因，不装
        return {"ok": False, "readonly": True, "verified": False, "card": None,
                "primitive_count": 0, "unverified_count": 0,
                "registered_in_manifest": False, "manifest_ref": None, "drift": [],
                "manifest_note": "技能卡片读不出来：%s: %s" % (type(exc).__name__, exc),
                "error": "%s: %s" % (type(exc).__name__, exc)}

    ref, note = None, ""
    path = root / TOOLCHAIN_MANIFEST
    if not path.is_file():
        note = "清单不存在（%s）：卡片仍然成立，但沙盘口述清单里**没有登记它**" % path
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in (data.get("skills") or []):
                if str(row.get("source_of_truth") or "") == PROJECTION_MODULE:
                    ref = row
                    break
            if ref is None:
                note = ("清单里没有引用 %s —— 卡片成立，但清单里没登记它（不许当成已登记）"
                        % PROJECTION_MODULE)
        except Exception as exc:  # noqa: BLE001
            note = ("清单读不出来（%s: %s）：这一轮**不知道**有没有登记 —— "
                    "不许当成未登记，也不许当成已登记" % (type(exc).__name__, exc))

    drift = []
    if ref is not None:
        if str(ref.get("status") or "") != str(card["status"]):
            drift.append("状态漂移：卡片 %s vs 清单 %s" % (card["status"], ref.get("status")))
        if int(ref.get("primitives") or 0) != int(card["primitive_count"]):
            drift.append("原语条数漂移：卡片 %d vs 清单 %s"
                         % (card["primitive_count"], ref.get("primitives")))
        if bool(ref.get("verified")) != bool(card["verified"]):
            drift.append("核实状态漂移：卡片 verified=%s vs 清单 verified=%s"
                         % (card["verified"], ref.get("verified")))
    return {"ok": True, "readonly": True, "verified": bool(card["verified"]),
            "card": card, "primitive_count": card["primitive_count"],
            "unverified_count": card["unverified_count"],
            "registered_in_manifest": ref is not None, "manifest_ref": ref,
            "drift": drift, "manifest_note": note, "error": None}


# 挖漏洞（R-H104）：这是**扫描器清单**（口径来自框架自己的能力表），面板只读"最近一次读数"。
SCANNERS = (
    ("selfscan", "综合自检"), ("cross_scan", "十维深扫"), ("truth_scan", "真实性审计"),
    ("ghost_guard", "防复发检测"), ("file_hygiene", "文件卫生"),
    ("signature_guard", "署名守卫"), ("inventory", "全息盘点"),
)


def dig_snapshot(root: Path, tail_kb: int = 256) -> dict:
    """挖漏洞面板的只读快照（R-H104）。

    两条硬约束（都写在代码里，不靠自觉）：
      1. **绝不触发扫描**：只读审计账本与坑册 —— `cross_scan` 一次 ~58 秒，
         5 秒轮询里跑它等于把看板变成自杀式负载。要新读数就人自己去跑一次。
      2. **只读尾部**：账本已经 36 MB，轮询不许把磁盘吃了 ⇒ 只读最后 `tail_kb` KB，
         并把这句写进读数里（读了多少、覆盖到哪一刻）。
    """
    audit = root / "gbt_allinone" / "store" / "audit.jsonl"
    pit = root / "gbt_allinone" / "store" / "pit_log.json"
    out = {"ok": True, "readonly": True, "source": "audit.jsonl 尾部 + pit_log.json",
           "tail_kb": tail_kb, "scanners": [], "pits": {}, "how": [
               "① 量现状：扫描器逐条打一枪，读数进审计账本（不是我先说结论）",
               "② 找漂移：声明与执行不一致的地方就是洞（纸面能力/恒真断言/未挂作用域）",
               "③ 钉死：一个洞配一条有牙用例（变异负对照必须变红）",
               "④ 留账：改动走框架自改门，原因·证据·回滚点·印章写进护照",
           ]}
    latest = {}
    scanned_bytes = 0
    if audit.is_file():
        try:
            size = audit.stat().st_size
            with audit.open("rb") as fh:
                start = max(0, size - tail_kb * 1024)
                fh.seek(start)
                blob = fh.read()
            scanned_bytes = len(blob)
            for line in blob.decode("utf-8", errors="replace").splitlines():
                if '"event"' not in line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:  # noqa: BLE001 —— 甩掉半截行（尾部截断的必然产物）
                    continue
                meta = row.get("meta") or {}
                for kind, label in SCANNERS:
                    hit = (row.get("event") == kind) or (meta.get("kind") == kind)
                    if hit:
                        latest[kind] = {"at": row.get("iso"), "meta": meta}
        except OSError as exc:
            out.update({"ok": False, "error": "读审计账本失败：%s" % exc})
    else:
        out.update({"ok": False, "error": "审计账本不存在：%s" % audit})
    for kind, label in SCANNERS:
        got = latest.get(kind)
        meta = (got or {}).get("meta") or {}
        out["scanners"].append({
            "kind": kind, "label": label, "at": (got or {}).get("at"),
            "verdict": str(meta.get("verdict") or meta.get("status") or ("ok" if got else "")),
            "findings": meta.get("findings", meta.get("missing")),
            "fixed": meta.get("fixed", meta.get("restored")),
            "ever_ran": bool(got),
        })
    out["audit_bytes_read"] = scanned_bytes
    if pit.is_file():
        try:
            data = json.loads(pit.read_text(encoding="utf-8"))
            pits = data.get("pits") if isinstance(data, dict) else data
            pits = pits if isinstance(pits, list) else []
            keep = ("id", "title", "severity", "status", "at", "date")
            out["pits"] = {"count": len(pits),
                           "latest": [{k: p.get(k) for k in keep if k in p}
                                      for p in pits[-3:] if isinstance(p, dict)]}
        except Exception as exc:  # noqa: BLE001
            out["pits"] = {"count": None, "error": "%s: %s" % (type(exc).__name__, exc)}
    else:
        out["pits"] = {"count": None, "error": "坑册不存在：%s" % pit}
    return out


RING_ZONES = (("结构层", "谁连谁"), ("抑制层", "谁否决谁"), ("可塑层", "谁调整谁"),
              ("感知运动层", "谁感知谁执行"), ("闭环层", "谁反馈谁"), ("幽灵信号", "一闪而逝"))
# 哪些审计事件算"一次幽灵信号"：拒绝 / 变红 / 复核 —— 都是"从环上冒出、只留一条痕迹"的东西。
SIGNAL_EVENTS = ("denied", "auth_denied", "auth_grant_aborted", "review_denied",
                 "preflight_blocked", "pipeline_blocked", "user_error")


def ring_snapshot(root: Path, tail_kb: int = 256, limit: int = 12) -> dict:
    """幽灵信号环（R-H106）：六区环 + 最近信号痕迹。**无中心 · 不驻留 · 只留痕**。

    口径：
      · 信号 = 审计账本里真实发生过的「拒绝/变红/复核」事件（不是模拟出来的闪光）；
      · 只读尾部（账本 36 MB，轮询不许吃盘），**不触发任何扫描/动作**；
      · 一条信号只出现一次、只留一行痕迹 —— 不驻留、不放大（这正是"一闪而逝"）。
    """
    audit = root / "gbt_allinone" / "store" / "audit.jsonl"
    out = {"ok": True, "readonly": True, "center": None, "tail_kb": tail_kb,
           "zones": [{"name": n, "duty": d} for n, d in RING_ZONES],
           "law": ["信号不从中心发出：单方证据不能自证，必须由另一个 checker 发起复核",
                   "一闪而逝：只留一条痕迹（审计一行），不驻留、不放大",
                   "包围式安静：没有总指挥，判断住在接线拓扑里"],
           "signals": [], "counts": {}}
    if not audit.is_file():
        out.update({"ok": False, "error": "审计账本不存在：%s" % audit})
        return out
    try:
        size = audit.stat().st_size
        with audit.open("rb") as fh:
            fh.seek(max(0, size - tail_kb * 1024))
            blob = fh.read()
    except OSError as exc:
        out.update({"ok": False, "error": "读账本失败：%s" % exc})
        return out
    out["audit_bytes_read"] = len(blob)
    for line in blob.decode("utf-8", errors="replace").splitlines():
        if '"event"' not in line:
            continue
        try:
            row = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        event = str(row.get("event") or "")
        if event not in SIGNAL_EVENTS:
            continue
        meta = row.get("meta") or {}
        origin = str(meta.get("kind") or meta.get("scope") or meta.get("action") or "环上")
        detail = str(meta.get("reason") or meta.get("error") or meta.get("detail")
                     or meta.get("missing") or "")[:90]
        out["signals"].append({"at": row.get("iso"), "event": event, "origin": origin,
                               "trace": "%s → %s" % (origin, event),
                               "detail": detail})
        out["counts"][event] = out["counts"].get(event, 0) + 1
    out["signals"] = out["signals"][-limit:]
    out["signal_count_in_tail"] = sum(out["counts"].values())
    return out


def collect(root: Path, max_depth: int = 3) -> dict:
    squad = root / ".cluster" / "dd_squad"
    board = []
    bf = squad / "board.json"
    if bf.is_file():
        try:
            board = json.loads(bf.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            board = [{"error": "%s: %s" % (type(exc).__name__, exc)}]
    # 兵团名册：**实报**，不美化。空编就是空编 —— 画成浅色"坑位"，不点成兵力。
    roster, summary = [], {}
    rf = squad / "roster.json"
    if rf.is_file():
        try:
            roster = json.loads(rf.read_text(encoding="utf-8"))
            real = sum(1 for m in roster if m.get("backed_by"))
            summary = {"编制": len(roster), "实有": real, "空编": len(roster) - real}
        except Exception as exc:  # noqa: BLE001
            summary = {"error": "%s: %s" % (type(exc).__name__, exc)}

    def scan(p: Path, d: int = 0) -> dict:
        node = {"name": p.name or str(p), "type": "dir" if p.is_dir() else "file"}
        if p.is_dir():
            kids = []
            if d < max_depth:
                try:
                    for c in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
                        if c.name in SKIP_DIRS or (c.name.startswith(".") and c.name != ".cluster"):
                            continue
                        kids.append(scan(c, d + 1))
                except OSError:
                    pass
            node["children"] = kids[:50]
        else:
            try:
                node["size"] = p.stat().st_size
            except OSError:
                node["size"] = 0
        return node

    return {"timestamp": datetime.now().isoformat(timespec="seconds"),
            "meta": {"developer": DEVELOPER, "brand": BRAND, "director": DIRECTOR},
            "board": board, "roster": roster, "roster_summary": summary,
            "project_tree": scan(root),
            "plug": plug_snapshot(),
            "toolchain": load_toolchain(root),
            "dig": dig_snapshot(root),
            "ring": ring_snapshot(root),
            "projection": projection_snapshot(root)}


_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>DD小分队 · 立体作战沙盘</title>
<style>
 *{margin:0;padding:0;box-sizing:border-box}
 body{background:radial-gradient(ellipse at center,#0a0e27 0%,#000 100%);color:#e0e0e0;
      font-family:'Segoe UI','PingFang SC',monospace;overflow:hidden;height:100vh}
 #c3d{position:fixed;inset:0;width:100%;height:100%}
 .panel{position:fixed;background:rgba(10,14,39,.85);border:1px solid #1e88e5;border-radius:8px;
        padding:12px;box-shadow:0 0 20px rgba(30,136,229,.3)}
 #hdr{top:16px;left:50%;transform:translateX(-50%);text-align:center;padding:8px 26px}
 #hdr h1{font-size:17px;color:#64b5f6;letter-spacing:2px}
 #hdr .sub{font-size:11px;color:#888;margin-top:3px}
 #board{left:16px;bottom:16px;width:400px;max-height:42vh;overflow-y:auto}
 #tree{right:16px;top:74px;width:320px;max-height:40vh;overflow-y:auto}
 #digpanel{right:16px;top:calc(74px + 42vh);width:320px;max-height:24vh;overflow-y:auto}
 #ringpanel{left:430px;bottom:16px;width:360px;max-height:30vh;overflow-y:auto}
 h2{font-size:13px;color:#64b5f6;margin-bottom:8px}
 .task{background:rgba(30,40,70,.6);border-left:3px solid #666;padding:7px 11px;margin-bottom:6px;
       border-radius:4px;font-size:12px}
 .task.done{border-left-color:#4caf50}.task.running{border-left-color:#ff9800}
 .task.blocked{border-left-color:#f44336}
 .tid{color:#64b5f6;font-weight:bold}.tst{float:right;font-size:10px;padding:1px 6px;
       border-radius:3px;background:#333}
 .tnode{font-size:11px;padding:1px 0;color:#aaa}.tnode.dir{color:#81c784;font-weight:bold}
 .tch{padding-left:13px;border-left:1px dashed #333}
 #lg{right:16px;bottom:16px;font-size:11px;padding:9px 13px}
 .li{margin:3px 0}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;
      margin-right:6px;vertical-align:middle}
 #plug{left:16px;top:74px;width:400px;max-height:28vh;overflow-y:auto}
 #toolpanel{left:16px;top:calc(74px + 30vh);width:400px;max-height:28vh;overflow-y:auto}
 #projpanel{left:16px;top:calc(74px + 60vh);width:400px;max-height:22vh;overflow-y:auto}
 #tip{position:fixed;display:none;background:rgba(10,14,39,.96);border:1px solid #1e88e5;
      border-radius:6px;padding:8px 10px;font-size:11px;color:#cfe3ff;max-width:340px;
      pointer-events:none;z-index:9;line-height:1.6}
 .wf{background:rgba(30,40,70,.6);border-left:3px solid #1e88e5;padding:7px 11px;
     margin-bottom:6px;border-radius:4px;font-size:12px}
 .wf-h{display:flex;justify-content:space-between;margin-bottom:4px}
 .wid{color:#64b5f6;font-weight:bold}
 .wf-lv{color:#888;font-size:11px;margin:2px 0;line-height:1.5}
 .nd{display:inline-block;padding:1px 6px;margin:1px 3px 1px 0;border-radius:3px;
     background:#222c44;color:#9fb3d1;font-size:11px}
 .nd.ok{background:#1b3a24;color:#81c784}.nd.denied{background:#3a1b1b;color:#ef9a9a}
 .nd.error{background:#3a241b;color:#ffb74d}.nd.skipped{background:#2a2a2a;color:#888}
 .nd.unverified{background:#3a2f1b;color:#ffcc80;border:1px dashed #ffb74d}
 .lgline{color:#888;font-size:11px;margin:2px 0 6px;line-height:1.9}
 .wf-run{color:#888;font-size:11px;margin-top:3px}
 #err{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);color:#f44336;font-size:13px}
</style></head><body>
<canvas id="c3d"></canvas>
<div id="hdr" class="panel"><h1>DD小分队 · 立体作战沙盘</h1>
  <div class="sub">__DIR__ · 看见但不改剧本 · 开发者：__DEV__ · <span id="ts">…</span></div></div>
<div id="board" class="panel"><h2>任务板</h2><div id="bc"></div></div>
<div id="tree" class="panel"><h2>项目树</h2><div id="tc"></div></div>
<div id="plug" class="panel"><h2>万能插 · 工作流 <span style="color:#666;font-weight:normal">（只读 · 不执行）</span></h2><div id="pc"></div></div>
<div id="toolpanel" class="panel"><h2>工具链 · 生成/短剧/发布 <span style="color:#666;font-weight:normal">（只读 · 不执行）</span></h2><div id="chain"></div></div>
<div id="digpanel" class="panel"><h2>挖漏洞 · 扫描器读数 <span style="color:#666;font-weight:normal">（只读 · 不触发扫描）</span></h2><div id="dig"></div></div>
<div id="ringpanel" class="panel"><h2>幽灵信号环 <span style="color:#666;font-weight:normal">（无中心 · 一闪而逝 · 只留痕）</span></h2><div id="ring"></div></div>
<div id="projpanel" class="panel"><h2>空间投射 · 只读技能卡片 <span style="color:#666;font-weight:normal">（只呈现 · 不执行 · 未核实就标未核实）</span></h2><div id="proj"></div></div>
<div id="tip"></div>
<div id="lg" class="panel">
  <div class="li"><span class="dot" style="background:#4caf50"></span>已完成</div>
  <div class="li"><span class="dot" style="background:#ff9800"></span>进行中</div>
  <div class="li"><span class="dot" style="background:#f44336"></span>通道阻塞</div>
  <div class="li"><span class="dot" style="background:#1e88e5"></span>待认领</div>
</div>
<div id="err"></div>
<script type="module">
import * as THREE from "/three/build/three.module.js";
const COLOR = {完成:0x4caf50, 进行:0xff9800, 阻塞:0xf44336};
function colorOf(s){ for (const k in COLOR) if (String(s||"").includes(k)) return COLOR[k];
                     return 0x1e88e5; }
function drawBoard(b){
  const el=document.getElementById('bc');
  if(!b||!b.length){ el.innerHTML='<div style="color:#666">暂无任务</div>'; return; }
  el.innerHTML=b.map(t=>{
    const s=t.status||'待认领';
    let c='task'; if(String(s).includes('完成'))c+=' done';
    else if(String(s).includes('进行'))c+=' running';
    else if(String(s).includes('阻塞'))c+=' blocked';
    return `<div class="${c}"><span class="tid">${t.task_id||'?'}</span>
      <span class="tst">${s}</span>
      <div style="margin-top:4px">${t.title||''}</div>
      <div style="color:#888;font-size:11px">负责人: ${t.assigned_to||'待认领'}</div></div>`;
  }).join('');
}
function drawTree(n,d=0){
  if(!n||d>3) return '';
  const dir=n.type==='dir';
  let h=`<div class="tnode ${dir?'dir':''}">${dir?'▸':'·'} ${n.name}</div>`;
  if(dir&&n.children&&n.children.length)
    h+=`<div class="tch">${n.children.map(c=>drawTree(c,d+1)).join('')}</div>`;
  return h;
}
// 万能插（只读）：每个工作流画成"分层 DAG"——同层可并行，节点色 = 最近一次运行的节点状态。
// 诚实口径：没有运行记录的节点**不着色**（不点成绿）；取不到数据就显示原因，不画好看的假图。
function drawPlug(p){
  const el=document.getElementById('pc');
  if(!p){ el.innerHTML='<div style="color:#666">无数据</div>'; return; }
  if(!p.ok){ el.innerHTML=`<div style="color:#f44336">取不到万能插数据：${p.error||'未知原因'}</div>`; return; }
  const list=p.workflows||[];
  if(!list.length){ el.innerHTML='<div style="color:#666">还没有工作流定义（wf_define 之后会出现在这里）</div>'; return; }
  // 图例（R-H102）：色=状态这条口径必须看得见。**没有运行记录的节点不着色**（不点成绿）。
  const legend=`<div class="lgline">节点色=最近一次运行：`
    +`<span class="nd ok">ok</span><span class="nd denied">denied</span>`
    +`<span class="nd error">error</span><span class="nd skipped">skipped</span>`
    +`<span class="nd">未跑（不着色）</span></div>`;
  el.innerHTML=legend+list.map(w=>{
    const latest=(w.latest&&w.latest.nodes)||{};
    const rows=(w.levels||[]).map(lv=>lv.map(id=>{
      const st=latest[id];
      const cls=st?`nd ${st}`:'nd';
      const tip=st?`${id} · 最近 ${st}`:`${id} · 最近没有运行记录`;
      return `<span class="${cls}" title="${tip}">${id}</span>`;
    }).join('<span style="color:#456">→</span>')).join('<br>');
    // 运行行（R-H103）：最近 3 次，状态色沿用同一套图例；一条都没有就明说"没有运行记录（不着色）"。
    const recents=(w.recent||[]);
    const lr=recents.length
      ? `最近 ${recents.length} 次运行：`+recents.map(r=>{
          const st=String(r.status||'');
          const cls=st?`nd ${st}`:'nd';
          return `<span class="${cls}" title="${r.run_id||''}">${st||'?'}</span>`
            +`<span style="color:#888"> ${r.finished_at||''} · ${r.elapsed_s??''}s</span>`;}).join('<br>')
      : '最近没有运行记录（不着色）';
    return `<div class="wf"><div class="wf-h"><span class="wid">${w.name}</span>`
      +`<span class="tst">${w.node_count} 节点</span></div>`
      +`<div class="wf-lv">${rows}</div><div class="wf-run">${lr}</div></div>`;
  }).join('');
}
// ── 工具链（只读 · 未核实就标未核实）：生成端=内环(蓝) · 短剧专线=中环(紫) · 发布端=外环(金) ──
// 红线与"导演"同一条：**只呈现，不执行**；口述清单不许画成已核实的战力。
const CHAIN_RING=[['generation',4.5,6,0x1e88e5],['drama',8,9.5,0x9c27b0],
                  ['publishing',11.5,13,0xffb300]];
const CHAIN_LABEL={generation:'生成端（内环·蓝）',drama:'短剧专线（中环·紫）',
                   publishing:'发布端（外环·金）'};
let chainObjs=[],chainData={};
function drawToolchain(t){
  const el=document.getElementById('chain');
  if(!t){ el.innerHTML='<div style="color:#666">无数据</div>'; return; }
  if(!t.ok){ el.innerHTML=`<div style="color:#f44336">${t.error||'取不到工具链清单'}</div>`; return; }
  const tag=t.verified?'<span style="color:#81c784">已核实</span>'
                      :'<span style="color:#ffb74d">未联网核实（口述清单）</span>';
  let h=`<div style="color:#888;font-size:11px;margin-bottom:6px">来源：${t.source||'?'} · ${tag}`
       +(t.flow_verified?'':' · <span style="color:#ffb74d">流向未实测</span>')+`</div>`;
  // 图例（R-H102）：工具链这套用的是**核实状态色**，跟工作流那套（运行状态色）不是一回事，
  // 所以各带各的图例，不许混成一个色系让人猜。
  h+=`<div class="lgline">卡片色=核实状态：<span class="nd unverified">未核实（口述）</span>`
    +`<span class="nd ok">已核实</span></div>`;
  // 分层 DAG（R-H101）：层与边都来自清单；未实测的流向必须在标题旁括号里写出来。
  const layers=(t.layers&&t.layers.length)?t.layers:[['generation'],['drama'],['publishing']];
  const edges=(t.edges||[]).map(e=>e.join('→'));
  h+=`<div style="color:#888;font-size:11px;margin-bottom:6px">分层：`
    +layers.map(l=>l.map(g=>CHAIN_LABEL[g]||g).join(' / ')).join(' <span style="color:#456">→</span> ')
    +`</div>`;
  layers.forEach((layer,idx)=>{
    h+=`<div class="wf"><div class="wf-h"><span class="wid">第 ${idx+1} 层</span>`
      +`<span class="tst">${layer.length} 组</span></div>`;
    layer.forEach(g=>{
      const items=(t.groups&&t.groups[g])||[];
      h+=`<div style="color:#9fb3d1;font-size:11px;margin:3px 0">${CHAIN_LABEL[g]||g} · ${items.length} 项</div>`;
      h+=`<div class="wf-lv">`+items.map(it=>{
         const pl=(it.platforms||[]);
         const tip=[it.name,it.license?('协议：'+it.license):'',
                    pl.length?('平台：'+pl.join('、')):'',
                    it.verified===false?'核实：未联网核实':''].filter(Boolean).join(' · ');
         const vcls=it.verified===false?'nd unverified':'nd ok';
         return `<span class="${vcls}" title="${tip}">${it.name}</span>`;}).join('')+`</div>`;
    });
    h+=`</div>`;
    if(idx<layers.length-1)
      h+=`<div style="color:#456;text-align:center;font-size:13px;margin:-2px 0 4px">↓</div>`;
  });
  if(edges.length) h+=`<div class="wf-run">层间边（口述·未实测）：${edges.join(' · ')}</div>`;
  const pv=t.pending_verification||[];
  if(pv.length) h+=`<div class="wf-run" style="color:#ffb74d">另有 ${pv.length} 项只在口述里出现过、`
                  +`没有 repo/协议出处：${pv.map(x=>x.name).join('、')}</div>`;
  el.innerHTML=h;
}
// 挖漏洞（R-H104）：扫描器读数 + 坑册 + "挖法四步"。只读账本，**不触发扫描**。
// 幽灵信号环（R-H106）：六区环 + 最近信号痕迹。没有中心节点——信号从环上冒出、闪过、只留一行。
function drawRing(r){
  const el=document.getElementById('ring');
  if(!r){ el.innerHTML='<div style="color:#666">无数据</div>'; return; }
  if(!r.ok){ el.innerHTML=`<div style="color:#f44336">${r.error||'读不到信号账本'}</div>`; return; }
  const zones=(r.zones||[]).map(z=>`<span class="nd" title="${z.duty}">${z.name}</span>`).join('');
  let h=`<div class="lgline">环上六区（无中心）：${zones}</div>`;
  h+=`<div class="lgline">信号 = 账本里真实发生过的拒绝/变红/复核 · 尾部共 ${r.signal_count_in_tail||0} 条`
    +`（只读 ${r.tail_kb} KB）</div>`;
  const sig=r.signals||[];
  h+=sig.length ? sig.map(s=>`<div class="wf-run">`
      +`<span class="nd ${s.event==='auth_consumed'?'ok':'denied'}">${s.event}</span>`
      +`<span style="color:#888"> ${s.at||''} · ${s.origin||''}</span>`
      +(s.detail?`<div style="color:#666;font-size:11px">↳ ${s.detail}</div>`:'')+`</div>`).join('')
    : `<div class="wf-run">尾部没有信号：安静（安静 ≠ 没事，也可能是没人复核）</div>`;
  h+=`<div class="lgline">`+(r.law||[]).map(x=>`<div>· ${x}</div>`).join('')+`</div>`;
  el.innerHTML=h;
}
function drawDig(g){
  const el=document.getElementById('dig');
  if(!g){ el.innerHTML='<div style="color:#666">无数据</div>'; return; }
  if(!g.ok){ el.innerHTML=`<div style="color:#f44336">${g.error||'读不到扫描账本'}</div>`; return; }
  const cls=v=>{ if(!v) return 'nd'; const s=String(v).toLowerCase();
    if(s.includes('clean')||s.includes('ok')||s.includes('pass')) return 'nd ok';
    if(s.includes('messy')||s.includes('missing')||s.includes('fail')||s.includes('p0')||s.includes('p1')) return 'nd denied';
    return 'nd error'; };
  let h=`<div class="lgline">读数来源：${g.source} · 只读尾部 ${g.tail_kb} KB`
       +`（实读 ${g.audit_bytes_read||0} 字节）· 看板<strong>不会</strong>替你跑扫描</div>`;
  h+=(g.scanners||[]).map(s=>`<div class="wf"><div class="wf-h"><span class="wid">${s.label}</span>`
     +`<span class="${cls(s.ever_ran?s.verdict:'')}">${s.ever_ran?(s.verdict||'ok'):'从未跑过'}</span></div>`
     +`<div class="wf-run">${s.at?s.at+(s.findings===undefined||s.findings===null?'':` · 发现 ${s.findings}`)
        +(s.fixed===undefined||s.fixed===null?'':` · 已处置 ${s.fixed}`):'账本尾部里没有它的读数'}</div></div>`).join('');
  const p=g.pits||{};
  h+=`<div class="wf"><div class="wf-h"><span class="wid">坑册</span>`
    +`<span class="tst">${p.count===null||p.count===undefined?'读不到':p.count+' 条'}</span></div>`
    +`<div class="wf-run">${p.error?p.error:'（最近 3 条已入册）'}</div></div>`;
  h+=`<div class="lgline">挖法：`+(g.how||[]).map(x=>`<div>${x}</div>`).join('')+`</div>`;
  el.innerHTML=h;
}
// 空间投射（只读卡片）：把"技能定义"画出来，**一个像素都不点亮**。
// 红线与"导演"同一条：只呈现，不执行；判据是 ARM ≠ LIVE —— 准备态永不点亮，GO LIVE 只能操作者按键。
function drawProjection(p){
  const el=document.getElementById('proj');
  if(!p){ el.innerHTML='<div style="color:#666">无数据</div>'; return; }
  if(!p.ok){ el.innerHTML=`<div style="color:#f44336">读不出技能卡片：${p.error||'未知原因'}</div>`; return; }
  const c=p.card||{};
  let h=`<div class="lgline">红线：<span class="nd denied">ARM ≠ LIVE</span>`
    +`<span class="nd">GO LIVE 只能操作者按钮</span>`
    +`<span class="nd">硬件门禁未全绿不 LIVE</span></div>`;
  h+=`<div style="color:#888;font-size:11px;margin-bottom:4px">`
    +`${c.name||'空间投射'} · 原语 ${p.unverified_count}/${p.primitive_count} 未核实`
    +(p.registered_in_manifest?' · 清单已引用':' · <span style="color:#ffb74d">清单未登记</span>')
    +`</div>`;
  h+=(c.primitives||[]).map(x=>`<span class="nd unverified" title="${x.duty||''}`
    +`｜层：${x.layer||''}｜为什么未核实：${x.why_unverified||''}`
    +`">${x.name} · ${x.status}</span>`).join('<span style="color:#456">→</span>');
  h+=`<div class="wf-run">闭环：${(c.closed_loop||[]).join(' → ')}</div>`;
  if((p.drift||[]).length)
    h+=`<div style="color:#f44336;font-size:11px">漂移：${p.drift.join('；')}</div>`;
  if(p.manifest_note)
    h+=`<div style="color:#ffb74d;font-size:11px">${p.manifest_note}</div>`;
  h+=`<div class="wf-run">参考：${(c.reference_projects||[]).map(r=>r.name).join(' · ')}`
    +`（口述参考 · 未联网核实）</div>`;
  el.innerHTML=h;
}
function chainTip(c){
  const it=(c&&c.item)||{};
  const pl=(it.platforms||[]).join('、');
  return [it.name?`<b>${it.name}</b>`:'', it.kind?`类型：${it.kind}`:'',
          pl?`平台：${pl}`:'', it.license?`协议：${it.license}`:'',
          it.repo?`repo：${it.repo}`:'', it.pipeline?`链路：${it.pipeline}`:'',
          it.claim?`口述：${it.claim}`:'',
          it.verified===false?'<span style="color:#ffb74d">核实状态：未联网核实（口述清单）</span>':''
         ].filter(Boolean).join('<br>');
}
function rebuildToolchain(t){
  chainObjs.forEach(o=>scene.remove(o)); chainObjs=[]; chainData=t||{};
  if(!t||!t.ok) return;
  CHAIN_RING.forEach(([g,R,Y,col])=>{
    const items=(t.groups&&t.groups[g])||[];
    if(!items.length) return;
    const ring=new THREE.Mesh(new THREE.RingGeometry(R-0.15,R+0.15,96),
      new THREE.MeshBasicMaterial({color:col,side:THREE.DoubleSide,transparent:true,opacity:.3}));
    ring.rotation.x=Math.PI/2; ring.position.y=Y; scene.add(ring); chainObjs.push(ring);
    items.forEach((it,i)=>{
      const a=(i/items.length)*Math.PI*2;
      const s=new THREE.Mesh(new THREE.SphereGeometry(0.55,16,16),
        new THREE.MeshPhongMaterial({color:col,emissive:col,emissiveIntensity:.5}));
      s.position.set(Math.cos(a)*R,Y+Math.sin(i*1.9)*0.8,Math.sin(a)*R);
      s.userData={chain:{group:g,item:it}}; scene.add(s); chainObjs.push(s);
    });
  });
}
let scene,camera,renderer,agents=[],t0=performance.now();
function init3D(){
  const canvas=document.getElementById('c3d');
  scene=new THREE.Scene(); scene.fog=new THREE.FogExp2(0x0a0e27,0.02);
  camera=new THREE.PerspectiveCamera(60,innerWidth/innerHeight,0.1,1000);
  renderer=new THREE.WebGLRenderer({canvas,antialias:true});
  renderer.setSize(innerWidth,innerHeight); renderer.setPixelRatio(devicePixelRatio);
  scene.add(new THREE.AmbientLight(0x404080,1.2));
  const l1=new THREE.PointLight(0x64b5f6,2,50); l1.position.set(10,20,10); scene.add(l1);
  const l2=new THREE.PointLight(0xff64b5,1.5,50); l2.position.set(-10,-10,10); scene.add(l2);
  const grid=new THREE.GridHelper(60,30,0x1e88e5,0x1a237e); grid.position.y=-5; scene.add(grid);
  const core=new THREE.Mesh(new THREE.IcosahedronGeometry(1.8,2),
    new THREE.MeshPhongMaterial({color:0x64b5f6,emissive:0x1e88e5,emissiveIntensity:.6}));
  scene.add(core); agents.push(core);
  animate();
}
function rebuild(b){
  agents.filter(a=>a.userData&&a.userData.task).forEach(a=>scene.remove(a));
  agents=agents.filter(a=>!(a.userData&&a.userData.task));
  (b||[]).forEach((t,i,arr)=>{
    const ang=(i/arr.length)*Math.PI*2, R=8;
    const x=Math.cos(ang)*R, z=Math.sin(ang)*R, y=Math.sin(i*1.7)*3;
    const col=colorOf(t.status);
    const m=new THREE.Mesh(new THREE.SphereGeometry(1.2,32,32),
      new THREE.MeshPhongMaterial({color:col,emissive:col,emissiveIntensity:.4,shininess:100}));
    m.position.set(x,y,z); m.userData={task:t,baseY:y,phase:i}; scene.add(m); agents.push(m);
    const ring=new THREE.Mesh(new THREE.RingGeometry(1.5,1.7,32),
      new THREE.MeshBasicMaterial({color:col,side:THREE.DoubleSide,transparent:true,opacity:.5}));
    ring.position.copy(m.position); ring.rotation.x=Math.PI/2; scene.add(ring);
    const g=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0),new THREE.Vector3(x,y,z)]);
    scene.add(new THREE.Line(g,new THREE.LineBasicMaterial({color:col,transparent:true,opacity:.3})));
  });
}
function animate(){
  requestAnimationFrame(animate);
  const t=(performance.now()-t0)/1000;
  agents.forEach(a=>{
    if(a.userData&&a.userData.baseY!==undefined){
      a.position.y=a.userData.baseY+Math.sin(t+a.userData.phase)*.3; a.rotation.y+=.01;
    } else { a.rotation.x+=.005; a.rotation.y+=.008; }
  });
  camera.position.x=Math.sin(t*.15)*25; camera.position.z=Math.cos(t*.15)*25;
  camera.lookAt(0,0,0); renderer.render(scene,camera);
}
// 兵团阵列：内环=指挥核心 · 中环=在岗(真) · 外环=空编(坑位)
// 诚实口径：**空编点画成极浅的灰蓝、半径更大、不加发光** —— 一眼能看出"那不是人，是坑位"。
let rosterObjs=[];
function rebuildRoster(r){
  rosterObjs.forEach(o=>scene.remove(o)); rosterObjs=[];
  if(!r||!r.length) return;
  const ring=(R,op,col)=>{ const m=new THREE.Mesh(new THREE.RingGeometry(R,R+0.2,96),
    new THREE.MeshBasicMaterial({color:col,side:THREE.DoubleSide,transparent:true,opacity:op}));
    m.rotation.x=Math.PI/2; scene.add(m); rosterObjs.push(m); };
  ring(9,0.12,0x1e88e5);     // 中环：在岗环
  ring(16,0.05,0x64b5f6);    // 外环：空编环
  const onDuty=r.filter(m=>m.backed_by), vacant=r.filter(m=>!m.backed_by);
  onDuty.forEach((m,i)=>{ const a=(i/Math.max(1,onDuty.length))*Math.PI*2;
    const s=new THREE.Mesh(new THREE.SphereGeometry(0.8,16,16),
      new THREE.MeshPhongMaterial({color:0xff9800,emissive:0xff9800,emissiveIntensity:.5}));
    s.position.set(Math.cos(a)*9,0,Math.sin(a)*9); scene.add(s); rosterObjs.push(s);
    const g=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0),s.position]);
    const L=new THREE.Line(g,new THREE.LineBasicMaterial({color:0xff9800,transparent:true,opacity:.35}));
    scene.add(L); rosterObjs.push(L); });
  vacant.forEach((m,i)=>{ const a=(i/Math.max(1,vacant.length))*Math.PI*2;
    const s=new THREE.Mesh(new THREE.SphereGeometry(0.4,12,12),
      new THREE.MeshPhongMaterial({color:0x1b2740,emissive:0x0d1526,transparent:true,opacity:.75}));
    s.position.set(Math.cos(a)*16,Math.sin(i*2.3)*2.2,Math.sin(a)*16);
    scene.add(s); rosterObjs.push(s); });
}
async function pull(){
  try{
    const r=await fetch('/api/data'); const d=await r.json();
    const S=d.roster_summary||{};
    document.getElementById('ts').textContent =
      '刷新于 '+d.timestamp+' · 编制 '+(S['编制']||0)+' / 实有 '+(S['实有']||0)+
      ' / 空编 '+(S['空编']||0)+' · 工作流 '+(((d.plug||{}).workflows)||[]).length+
      ' / 运行 '+(((d.plug||{}).runs)||[]).length;
    drawBoard(d.board); document.getElementById('tc').innerHTML=drawTree(d.project_tree);
    drawPlug(d.plug);
    drawProjection(d.projection);
    drawToolchain(d.toolchain); rebuildToolchain(d.toolchain);
    drawDig(d.dig);
    drawRing(d.ring);
    rebuild(d.board); rebuildRoster(d.roster);
    document.getElementById('err').textContent='';
  }catch(e){ document.getElementById('err').textContent='数据拉取失败: '+e; }
}
try{ init3D(); }catch(e){ document.getElementById('err').textContent='3D 初始化失败: '+e; }
// 悬停拾取：只查工具链节点（chainObjs 里带 userData.chain 的那些）——纯展示，不触发任何调用。
const raycaster=new THREE.Raycaster(), pointer=new THREE.Vector2();
addEventListener('pointermove',(e)=>{
  const tip=document.getElementById('tip');
  if(!tip||!camera||!renderer) return;
  pointer.x=(e.clientX/innerWidth)*2-1; pointer.y=-(e.clientY/innerHeight)*2+1;
  raycaster.setFromCamera(pointer,camera);
  const hits=raycaster.intersectObjects(chainObjs.filter(o=>o.userData&&o.userData.chain),false);
  if(hits.length){ tip.innerHTML=chainTip(hits[0].object.userData.chain);
    tip.style.display='block'; tip.style.left=(e.clientX+14)+'px'; tip.style.top=(e.clientY+14)+'px'; }
  else { tip.style.display='none'; }
});
pull(); setInterval(pull, 5000);
addEventListener('resize',()=>{ if(camera&&renderer){ camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight);} });
</script></body></html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    root = Path(".")
    three = Path(".")

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            page = (_PAGE.replace("__DEV__", DEVELOPER)
                         .replace("__DIR__", "%s %s" % (DIRECTOR["name"], DIRECTOR["title"])))
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/data":
            self._send(200, json.dumps(collect(self.root), ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        if path.startswith("/three/"):
            base = self.three.resolve()
            cand = (base / path[len("/three/"):]).resolve()
            try:
                cand.relative_to(base)
            except ValueError:
                self._send(403, b"forbidden", "text/plain")
                return
            if cand.is_file():
                ctype = ("application/javascript" if cand.suffix == ".js"
                         else "application/octet-stream")
                self._send(200, cand.read_bytes(), ctype)
                return
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):  # 静默
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=BRAND)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--port", type=int, default=8866)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    three = root / "holo_pet" / "node_modules" / "three"
    if not (three / "build" / "three.module.js").is_file():
        print("⚠️ 本地 three 不在: %s —— 3D 会起不来（页面会显示原因）" % three)
    Handler.root, Handler.three = root, three
    with socketserver.TCPServer(("127.0.0.1", a.port), Handler) as httpd:
        print("=" * 58)
        print(" %s · 开发者：%s" % (BRAND, DEVELOPER))
        print(" 沙盘：http://127.0.0.1:%d/" % a.port)
        print(" 数据：http://127.0.0.1:%d/api/data" % a.port)
        print(" three：本地 %s" % three)
        print(" ⚠️ 仅绑 127.0.0.1；这是看板进程，Ctrl+C 停，不自启动")
        print("=" * 58)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[沙盘] 已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
