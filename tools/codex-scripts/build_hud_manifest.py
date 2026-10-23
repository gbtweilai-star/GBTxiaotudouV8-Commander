# -*- coding: utf-8 -*-
"""HUD 版数据层：为 V3 采集全部真实读数（一个都不编）。
产出 .scratch/hud_manifest.json
  meta / runtime(本机实时) / domains(30) / radar(六维·真算法) / channels(三条通道) /
  faults(真实故障) / gaps(真实接线缺口) / caps(151)
雷达口径：六维 = 能力地图的六个功能区，把 30 个真实域全量划分进去（不重不漏 140 项），
          每一维的分数 = 该维**接线率**（已接线能力 / 该维能力总数），可由 caps_called_audit 复核。
"""
import ctypes
import json
import sys
import time
from collections import defaultdict
from ctypes import wintypes as wt
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
OUT = BASE / ".scratch" / "hud_manifest.json"

from gbt_allinone import api as API           # noqa: E402
from gbt_allinone import caps_registry as CR  # noqa: E402
from gbt_allinone import selfscan as SS       # noqa: E402

# ── 本机实时读数（Windows API，不引第三方库） ──


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wt.DWORD), ("dwMemoryLoad", wt.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def mem():
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return {"mem_load": int(st.dwMemoryLoad),
            "mem_total_gb": round(st.ullTotalPhys / 1024 ** 3, 1),
            "mem_free_gb": round(st.ullAvailPhys / 1024 ** 3, 1)}


def cpu_pct():
    k32 = ctypes.windll.kernel32
    idle, kern, user = wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
    k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))

    def q(f):
        return (f.dwHighDateTime << 32) | f.dwLowDateTime
    i0, k0, u0 = q(idle), q(kern), q(user)
    time.sleep(0.25)
    k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    i1, k1, u1 = q(idle), q(kern), q(user)
    dk, du, di = (k1 - k0), (u1 - u0), (i1 - i0)
    total = dk + du
    return int(round(100.0 * (total - di) / total)) if total > 0 else 0


# ── 六维划分（把 30 个真实域全量分入，不重不漏） ──
DIM_OF = {
    "感知": ["recon", "vision", "device", "automation", "digital_human"],
    "认知": ["mind", "brain", "devour", "data"],
    "决策": ["pipeline", "engine", "longrun"],
    "执行": ["tentacle", "system", "tools"],
    "交互": ["llm", "voice", "comms", "integration", "social", "creation"],
    "协同": ["project", "finance", "security", "framework", "image_video",
           "infra", "video", "life", "collab"],
}
DIM_GLOSS = {
    "感知": "看与听：情报、视觉、设备",
    "认知": "想与记：心智、吞天、数据",
    "决策": "定与排：管线、编排、长程",
    "执行": "做与验：触手、系统、工具",
    "交互": "说与创：大模型、语音、创作",
    "协同": "与他人与钱：项目、安全、生活",
}

caps_all = API.list_capabilities(filter_dangerous=False)
caps_ok = [c for c in caps_all if c.get("status") != "disabled"]
disabled = [c for c in caps_all if c.get("status") == "disabled"]
routing = SS.check_routing()
scan = SS.scan(autofix=False)
sec = (scan.get("sections") or {})
audit_sec = sec.get("audit") or {}

try:
    r = API.run_task("caps_called_audit", {}, safe=True)
    ca = ((r or {}).get("gbt_result") or {}).get("result") or {}
except Exception:  # noqa: BLE001
    ca = {}
wired = {x.get("kind") for x in (ca.get("wired") or [])}
gaps = sorted({c["name"] for c in caps_ok} - wired)

param_req = getattr(CR, "PARAM_REQUIRED", {}) or {}
GATED_DOMAINS = {"security"}
GATED_NAMES = {"one_key_deploy", "mirror_ascend", "mirror_release", "mirror_rewind",
               "pipeline_submit", "pipeline_rollback", "mirror_rehearse",
               "codex_thread_new", "codex_turn_send", "codex_interrupt", "codex_chat",
               "codex_models", "coze_mail", "auto_publish", "devour_github",
               "osint_scan", "sec_llm"}

DOMAIN_GLOSS = {
    "system": "体检·盘点·卫生", "llm": "大模型·推演·Codex", "pipeline": "镜像·晋升·管线",
    "engine": "工作流·调度·算子", "creation": "剧本·渲染·创作", "recon": "情报·监视·扫描",
    "tentacle": "触手·MCP·桌面", "mind": "心智·脑库·元认知", "data": "记录·审计·查询",
    "security": "黑客大脑·攻防", "devour": "吞天·消化·进化", "finance": "量化·回测",
    "longrun": "长程任务图", "tools": "索引·穿透·投射", "video": "视频生成·工作流",
    "brain": "吸收·做梦", "device": "蓝牙·设备", "project": "项目上下文",
    "voice": "语音·编排", "automation": "浏览器自动化", "collab": "协作信息素",
    "comms": "自有多址通信", "digital_human": "3D 数字人", "framework": "门与可见性",
    "image_video": "图像生成", "infra": "云电脑", "integration": "飞书镶嵌",
    "life": "生命档案", "social": "发布与收益", "vision": "视觉识别",
}

items, dom_rows = [], defaultdict(lambda: {"total": 0, "wired": 0, "gated": 0})
for c in sorted(caps_ok, key=lambda x: (x.get("domain") or "", x.get("name") or "")):
    name, domain = c.get("name"), c.get("domain") or "(未标域)"
    hint = param_req.get(name) or {}
    if name in gaps:
        status = "gap"
    elif domain in GATED_DOMAINS or name in GATED_NAMES:
        status = "gated"
    else:
        status = "live" if hint else "readonly"
    items.append({"name": name, "domain": domain, "desc": (c.get("desc") or "").strip(),
                  "params": list(hint.get("params") or []), "hint": hint.get("hint") or "",
                  "status": status, "wired": name in wired})
    d = dom_rows[domain]
    d["total"] += 1
    d["wired"] += 1 if name in wired else 0
    d["gated"] += 1 if status == "gated" else 0

for c in sorted(disabled, key=lambda x: x.get("name") or ""):
    items.append({"name": c.get("name"), "domain": "disabled",
                  "desc": (c.get("desc") or "").strip(), "params": [], "hint": "",
                  "status": "disabled", "wired": False})

radar, covered = [], []
for dim, doms in DIM_OF.items():
    tot = sum(dom_rows[d]["total"] for d in doms if d in dom_rows)
    wr = sum(dom_rows[d]["wired"] for d in doms if d in dom_rows)
    radar.append({"dim": dim, "gloss": DIM_GLOSS[dim], "domains": [d for d in doms if d in dom_rows],
                  "total": tot, "wired": wr, "rate": round(100.0 * wr / tot) if tot else 0})
    covered += [d for d in doms if d in dom_rows]

store = BASE / "gbt_allinone" / "store"
store_json = len(list(store.rglob("*.json"))) if store.exists() else 0

faults = []
for f in (audit_sec.get("recent_runtime") or [])[:6]:
    faults.append({"event": f.get("event"), "kind": f.get("kind"),
                   "reason": (f.get("reason") or "")[:150], "at": (f.get("at") or "")})

channels = [
    {"name": "注册 → 路由", "detail": "能力注册后是否都有分发路由",
     "num": routing.get("routed"), "den": routing.get("registered")},
    {"name": "路由 → 调用点", "detail": "路由之后是否真有代码在调它",
     "num": ca.get("wired_count"), "den": ca.get("total")},
    {"name": "授权覆盖", "detail": "需授权能力中，主人已发放的比例",
     "num": 0, "den": sum(1 for i in items if i["status"] == "gated")},
]
for ch in channels:
    ch["pct"] = round(100.0 * (ch["num"] or 0) / ch["den"]) if ch.get("den") else 0

manifest = {
    "meta": {
        "brand": "GBT小土豆V8", "version": "8.0.0", "developer": "自由的风",
        "scanned_at": scan.get("checked_at"), "python": sys.version.split()[0],
        "total": len(items), "executable": len(caps_ok), "disabled": len(disabled),
        "gated": sum(1 for i in items if i["status"] == "gated"),
        "gap_count": len(gaps), "domains": len(dom_rows),
        "routed": routing.get("routed"), "registered": routing.get("registered"),
        "modules_checked": sec.get("modules", {}).get("checked"),
        "modules_failed": len(sec.get("modules", {}).get("failed") or []),
        "wired": ca.get("wired_count"), "audit_total": ca.get("total"),
        "orphans": ca.get("orphan_count"),
        "verdict": scan.get("verdict"),
        "findings": scan.get("findings") or [],
        "audit_window": audit_sec.get("window"),
        "audit_anomalies": audit_sec.get("anomalies"),
        "audit_runtime_faults": audit_sec.get("runtime_faults"),
        "audit_by_event": audit_sec.get("by_event") or {},
    },
    "runtime": dict(cpu_pct=cpu_pct(), store_json=store_json, **mem()),
    "domains": [{"name": k, "gloss": DOMAIN_GLOSS.get(k, ""), "count": v["total"],
                 "wired": v["wired"], "gated": v["gated"]}
                for k, v in sorted(dom_rows.items(), key=lambda kv: kv[0])],
    "radar": radar,
    "channels": channels,
    "faults": faults,
    "gaps": gaps,
    "caps": items,
}

OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print("写出:", OUT)
print("能力", len(items), "| 域", len(dom_rows), "| 六维覆盖域", len(covered), "去重", len(set(covered)))
print("六维:", [(r["dim"], r["total"], "%d%%" % r["rate"]) for r in radar])
print("通道:", [(c["name"], "%d/%d" % (c["num"] or 0, c["den"]), "%d%%" % c["pct"]) for c in channels])
print("故障:", len(faults), "| 缺口:", gaps)
print("本机:", manifest["runtime"])
