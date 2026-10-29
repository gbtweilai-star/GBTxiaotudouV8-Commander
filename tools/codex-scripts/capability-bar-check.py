# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 能力栏（三态一色 · 一屏可读）· 运行证据快照生成器 + 判据（含负对照）

一、这个件干什么（两件事，一个文件 —— 与 capability-bindings.py 的 build/render/--check 同款组织）

    ① `refresh`    生成 **运行证据快照** `holo_pet_w3/capability-bar/run-evidence.js`
       —— 从 `gbt_allinone/store/audit.jsonl` 的**有界尾部窗口**里现读每个能力位的
          最近一次记录（ok / denied / error），给能力栏页面在 file:// 下也能显示三态。
       窗口口径写死在数据件里：**近 24 小时 + 最多回读 N MB（触顶如实标 capped）**，
       它**不是全史** —— 这一点必须跟着数字一起发出去，否则又是一个"看起来是实时"的快照。

    ② `--check`    判据（≥10 条 + 负对照 ≥6 条），退出码 0/1。
       负对照喂的是**内存副本**，一个字节都不写盘（照 capability-audit.py 的 run_checks 口径）。

二、为什么要"运行证据"这一层（口径，别删）

    能力栏要把在册能力位（位数现读，不写死）画成「接上 / 断连 / 未探测」三态。绑定台账（state/cap-bindings.json）
    能证明的是**接线有代码证据**（三边零未绑），它**证明不了"跑得动"**。
    把"已绑"直接画成"接上"，正是本仓反复打过的**假绿**。
    所以三态的证据取**运行记录**：
      · 接上   = 窗口内该位**最后一次**记录是 `ok`
      · 断连   = 窗口内最后一次记录是 `denied` / `error`（**原始串随行**，照审计口径）
      · 未探测 = 窗口内**没有**该位的记录（**不许画成通**；也写明"不等于坏"）
    窗口有界 ⇒ 数字必须带窗口口径与时刻一起显示。这是本仓《数据新鲜度契约》的要求。

三、用法

    py -3.14 tools/codex-scripts/capability-bar-check.py refresh          # 生成/刷新运行证据快照
    py -3.14 tools/codex-scripts/capability-bar-check.py --check          # 判据（含负对照）· 退出码 0/1
    py -3.14 tools/codex-scripts/capability-bar-check.py --check --live   # 追加一条真浏览器端到端（页面自报 vs 真源现算）
    py -3.14 tools/codex-scripts/capability-bar-check.py refresh --json   # 机读

四、纪律

    · **只读真源**：本件不写 state/、不写 gbt_allinone/ —— 只写 `holo_pet_w3/capability-bar/run-evidence.js`。
    · **不做减法**：不碰任何既有页、不碰 shell/**、不碰 gbt-master/**（本件只读它们的文件名做断言）。
    · 负对照必须能红；不能红的判据不算判据（本仓《扫描器自证律》）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent

# ── 真源（只读）──────────────────────────────────────────────────────────────
CAP_BINDINGS = ROOT / "state" / "cap-bindings.json"          # 在册能力位 × 触手 10 域 × 能量 13 通道（位数现读）
CAP_AUDIT = ROOT / "state" / "capability-audit.json"         # 审计总项四态（接上/断连/缺失/未探测；项数现读）
AUDIT_LEDGER = ROOT / "gbt_allinone" / "store" / "audit.jsonl"   # 运行证据账本（只读尾部窗口）
KEY_RUNTIME = ROOT / "gbt_allinone" / "store" / "key_gateway" / "runtime.json"
LOGBOOK = ROOT / "state" / "logbook.jsonl"

# ── 本件的产物 + 页面（能力栏本体）────────────────────────────────────────────
BAR_DIR = ROOT / "holo_pet_w3" / "capability-bar"
BAR_PAGE = BAR_DIR / "index.html"
BAR_EVIDENCE = BAR_DIR / "run-evidence.js"

# ── 能力神经（全族健康摘要 · 主人令 2026-10-08 追加）──────────────────────────
# 「能力栏页顶栏一格」= 把神经摘要折进**本件已经产出的数据件** run-evidence.js
# （页本来就加载它）—— 页面**不自取数**、不重算；本件只是把神经那一格随证据一起发出去。
# 神经**不重算**：用本件**已经算好的**窗口 ev 现喂给 capability-nerve 的纯函数，
# 一次读尾窗口即可（轻）。页**结构**不动（`holo_pet_w3/**` 只经生成器产；本件是它的数据源）。
NERVE_PY = ROOT / "tools" / "codex-scripts" / "capability-nerve.py"
NERVE_DIGEST = ROOT / "state" / "cap-nerve.json"

# ── 页面要用的"既有数据件"（并行任务的生成物，**只读、不改**）─────────────────
ENERGY_DATA = ROOT / "holo_pet_w3" / "energy" / "energy-data.js"
CAPS_DATA = ROOT / "holo_pet_w3" / "capabilities" / "capabilities-data.js"

# ── 插件半边（A 腿）──────────────────────────────────────────────────────────
PLUGIN = ROOT / "plugins" / "gbt-capability-bar"
PLUGIN_HOST = PLUGIN / "lib" / "host.js"
PLUGIN_CLIENT = PLUGIN / "lib" / "client.js"
PLUGIN_PKG = PLUGIN / "package.json"

# ── 窗口口径（**写死在这里，页面与宿主读同一份说法**）──────────────────────────
WINDOW_HOURS = 24                    # 只认"近 24 小时"的记录
READ_CHUNK = 4 * 1024 * 1024         # 回读块
READ_MAX = 24 * 1024 * 1024          # 回读上限（触顶 = capped，如实标出）
EVENTS = ("ok", "denied", "error")

# 三态/四态的类名（页面、判据、宿主三边同一套说法；改这里 = 三边一起改）
STATE_CLASS = {"接上": "on", "断连": "off", "未探测": "unk", "缺失": "miss"}

CMD_REFRESH = "py -3.14 tools/codex-scripts/capability-bar-check.py refresh"
CMD_CHECK = "py -3.14 tools/codex-scripts/capability-bar-check.py --check"

# 域名 → 中文（抄自 tools/codex-scripts/make_capability_console.py::DOMAIN_CN，
# 仅补两个当前在册、那张表还没有的：desktop。表不全时页面回落显示英文 token，不编中文名。）
DOMAIN_CN = {
    "system": "系统", "llm": "内核", "tentacle": "触手", "device": "设备",
    "data": "数据", "finance": "金融", "project": "项目", "recon": "侦察",
    "security": "安全", "engine": "引擎", "longrun": "长程", "pipeline": "产出",
    "creation": "创作", "comms": "通信", "life": "生命", "mind": "心智",
    "vision": "视觉", "voice": "语音", "automation": "自动化",
    "digital_human": "数字人", "devour": "吞天", "brain": "脑域", "collab": "协作",
    "framework": "框架", "image_video": "影像", "infra": "基建",
    "integration": "集成", "social": "社交", "tools": "工具", "video": "视频",
    "desktop": "桌面", "dangerous": "禁用",
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════
# ① 运行证据：有界尾部窗口（近 24h / 最多 READ_MAX）
# ══════════════════════════════════════════════════════════════════════════
def read_evidence(caps: set) -> dict:
    """从账本尾部**有界回读**：近 WINDOW_HOURS 小时、最多 READ_MAX 字节。

    返回：{at, window_hours, read_bytes, file_bytes, capped, reached_cutoff,
           records, map: {cap: {s, at, raw}}, ledger}
    `map` 只收**在册**能力位（不在册的 kind 不收 —— 收了就会拿别人的记录冒充它的）。
    """
    out = {
        "at": now_iso(),
        "window_hours": WINDOW_HOURS,
        "file_bytes": 0,
        "read_bytes": 0,
        "capped": False,
        "reached_cutoff": False,
        "records": 0,
        "map": {},
        "ledger": "gbt_allinone/store/audit.jsonl",
    }
    if not AUDIT_LEDGER.is_file():
        out["error"] = "账本不在盘上：" + str(AUDIT_LEDGER)
        return out
    size = AUDIT_LEDGER.stat().st_size
    out["file_bytes"] = size
    cutoff = time.time() - WINDOW_HOURS * 3600
    text = ""
    read = 0
    end = size
    with open(AUDIT_LEDGER, "rb") as f:
        while end > 0 and read < READ_MAX:
            start = max(0, end - READ_CHUNK)
            f.seek(start)
            seg = f.read(end - start)
            read += len(seg)
            text = seg.decode("utf-8", "replace") + text
            first_ts = None
            for ln in seg.decode("utf-8", "replace").split("\n"):
                if ln.strip():
                    try:
                        first_ts = json.loads(ln).get("ts")
                    except Exception:                                   # noqa: BLE001
                        continue
                    break
            if first_ts is not None and first_ts < cutoff:
                out["reached_cutoff"] = True
                break
            end = start
    if read < size:
        # 回读是**从尾部往前**拼的 ⇒ 最前面那行可能是截半的（要么掐掉，要么根本不是行首）
        first_nl = text.find("\n")
        if first_nl >= 0:
            text = text[first_nl + 1:]
    out["read_bytes"] = read
    out["capped"] = bool(not out["reached_cutoff"] and read >= READ_MAX)
    last = {}
    records = 0
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:                                           # noqa: BLE001
            continue
        ev = r.get("event")
        if ev not in EVENTS:
            continue
        meta = r.get("meta") or {}
        kind = str(meta.get("kind") or "")
        if kind not in caps:
            continue                                    # 不在册的 kind 不收（不冒充）
        ts = r.get("ts") or 0
        if ts < cutoff:
            continue
        records += 1
        iso = str(r.get("iso") or "")
        cur = last.get(kind)
        if cur is None or iso > cur[0]:
            last[kind] = (iso, ev, json.dumps(meta, ensure_ascii=False)[:160])
    out["records"] = records
    out["map"] = {k: {"s": v[1], "at": v[0], "raw": v[2]} for k, v in sorted(last.items())}
    return out


def render_evidence_js(ev: dict) -> str:
    head = (
        "/* GBT小土豆V8 · 能力栏 · 运行证据快照（**自动生成，别手改**）。\n"
        "   重生成：{cmd}\n"
        "   判据（含负对照）：{chk}\n"
        "   真源：{ledger}（**只读尾部有界窗口**：近 {h} 小时 · 回读 {rb} · 上限 {mx}）\n"
        "   口径：接上=窗口内最后一次是 ok · 断连=最后一次是 denied/error（原始串随行）·\n"
        "        未探测=窗口内没有它的记录（**不许画成通**，也不等于坏）。\n"
        "   本文件只写这一处；页面、宿主都读它，不改它。\n"
        "   另含 nerve：全族健康摘要（由 capability-nerve.py 口径同源 · 只需现读这一份）。 */\n"
    ).format(cmd=CMD_REFRESH, chk=CMD_CHECK, ledger=ev.get("ledger"),
             h=ev.get("window_hours"), rb=ev.get("read_bytes"), mx=READ_MAX)
    body = json.dumps(ev, ensure_ascii=False, separators=(",", ":"))
    return head + "globalThis.GBT_CAPBAR_EVIDENCE = " + body + ";\n"


def nerve_cell(ev: dict) -> dict:
    """把「全族健康摘要」折成一格（**复用** capability-nerve 的纯函数口径，不另算一套）。

    🔴 神经**不重算**：本件已经把有界尾窗口 ev 算好了，直接喂给 nerve 的 build_digest。
    读不到能力神经 ⇒ 如实报 `{"error": ...}`（**不折绿**）。
    """
    spec = importlib.util.spec_from_file_location("_gbt_capnerve_for_bar", NERVE_PY)
    if spec is None or spec.loader is None:
        return {"error": "capability-nerve.py 不在盘：%s" % NERVE_PY}
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:                                               # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:100])}
    try:
        ledger = json.loads(CAP_BINDINGS.read_text(encoding="utf-8"))
        audit = json.loads(CAP_AUDIT.read_text(encoding="utf-8"))
    except Exception as e:                                               # noqa: BLE001
        return {"error": "台账读不到：%s" % str(e)[:80]}
    truth = m.load_truth() if callable(getattr(m, "load_truth", None)) else {"__absent__": "n/a"}
    dg = m.build_digest(ledger, audit, ev, truth, None, 0.0)
    c = dg["counts"]
    bad = c["未绑"] + c["断连"]
    which = ["未绑", "断连", "未探测"]
    fam_top = sorted(dg["families"], key=lambda r: -sum(r[k] for k in which))[:6]
    return {
        "families": c["families"], "caps": c["caps"],
        "未绑": c["未绑"], "断连": c["断连"], "未探测": c["未探测"], "假执行": c["假执行"],
        "level": "ok" if bad == 0 else ("warn" if bad <= 3 else "bad"),
        "text": "神经 %d 族 · 未绑 %d 断连 %d 未探 %d"
                % (c["families"], c["未绑"], c["断连"], c["未探测"]),
        "detectable": [r["family"] + ":" + ",".join("%s%d" % (k, r[k]) for k in which if r[k])
                       for r in fam_top],
        "rule": "轻 · 幂等（无时钟字段）· fail-closed",
    }


def cmd_refresh(as_json: bool = False) -> int:
    caps = load_cap_names()
    if caps is None:
        print("🔴 真源读不到：state/cap-bindings.json —— 不生成快照（不编）")
        return 1
    ev = read_evidence(caps)
    if ev.get("error"):
        print("🔴 " + ev["error"])
        return 1
    # 能力神经：把「全族健康摘要」折进同一份数据件（页顶栏那一格读它；口径与 nerve 同源）
    ev["nerve"] = nerve_cell(ev)
    BAR_DIR.mkdir(parents=True, exist_ok=True)
    BAR_EVIDENCE.write_text(render_evidence_js(ev), encoding="utf-8")
    st = {}
    for v in ev["map"].values():
        st[v["s"]] = st.get(v["s"], 0) + 1
    if as_json:
        print(json.dumps({"ok": True, "at": ev["at"], "records": ev["records"],
                          "map": len(ev["map"]), "states": st,
                          "read_bytes": ev["read_bytes"], "capped": ev["capped"],
                          "file": str(BAR_EVIDENCE)}, ensure_ascii=False))
    else:
        print("运行证据快照已生成 · %s" % BAR_EVIDENCE)
        print("  窗口：近 %d 小时 · 回读 %.1f MB / 账本 %.1f MB · capped=%s · 窗口内记录 %d 条 · 命中在册位 %d"
              % (ev["window_hours"], ev["read_bytes"] / 1048576, ev["file_bytes"] / 1048576,
                 ev["capped"], ev["records"], len(ev["map"])))
        print("  三态（%d 位）：接上 %d · 断连 %d · 未探测 %d"
              % (len(caps), st.get("ok", 0), st.get("denied", 0) + st.get("error", 0),
                 len(caps) - len(ev["map"])))
        nc = ev.get("nerve") or {}
        if nc.get("error"):
            print("  神经：🔴 未接（%s）" % nc["error"])
        else:
            print("  神经（顶栏一格）：%s" % nc.get("text"))
    return 0


# ══════════════════════════════════════════════════════════════════════════
# ② 判据（只读内存 art；负对照喂改坏副本）
# ══════════════════════════════════════════════════════════════════════════
def load_cap_names() -> set | None:
    try:
        d = json.loads(CAP_BINDINGS.read_text(encoding="utf-8"))
    except Exception:                                               # noqa: BLE001
        return None
    return {c["name"] for c in d.get("caps") or []}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:                                               # noqa: BLE001
        return ""


def _parse_global_js(text: str, name: str):
    """从 `globalThis.NAME = {...};`（经典脚本）里把 JSON 抠出来。抠不出返回 None —— 不猜。"""
    m = re.search(r"globalThis\.%s\s*=\s*(\{.*\})\s*;" % re.escape(name), text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:                                               # noqa: BLE001
        return None


def build_artifacts() -> dict:
    bindings = None
    try:
        bindings = json.loads(CAP_BINDINGS.read_text(encoding="utf-8"))
    except Exception:                                               # noqa: BLE001
        bindings = None
    audit = None
    try:
        audit = json.loads(CAP_AUDIT.read_text(encoding="utf-8"))
    except Exception:                                               # noqa: BLE001
        audit = None
    return {
        "bindings": bindings,
        "audit": audit,
        "page": _read(BAR_PAGE),
        "evidence_js": _read(BAR_EVIDENCE),
        "energy_js": _read(ENERGY_DATA),
        "caps_js": _read(CAPS_DATA),
        "host_js": _read(PLUGIN_HOST),
        "client_js": _read(PLUGIN_CLIENT),
        "plugin_pkg": _read(PLUGIN_PKG),
        "paths": {
            "page": str(BAR_PAGE), "evidence": str(BAR_EVIDENCE),
            "energy": str(ENERGY_DATA), "caps": str(CAPS_DATA),
            "plugin": str(PLUGIN),
        },
    }


_EXT_RE = re.compile(r'''(?:src|href)\s*=\s*["'](?:\s*)(?:https?:)?//''', re.I)
_BARE_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")


def _strip_comments(src: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", " ", re.sub(r"(^|[^:])//[^\n]*", r"\1 ", src or ""))


def _root_outside(css: str) -> str | None:
    """拆 :root 块：返回**块外**的文本；拆不出返回 None（读不到 ≠ 读到了）。"""
    at = css.find(":root")
    if at < 0:
        return None
    op = css.find("{", at)
    cl = css.find("}", op)
    if op < 0 or cl < 0:
        return None
    return css[:op] + css[cl + 1:]


def run_checks(art: dict) -> list:
    """判据本体：**只读 art（内存）**，不碰磁盘。返回 [{id, ok, detail}]。"""
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": str(detail)})

    b = art.get("bindings") or {}
    a = art.get("audit") or {}
    caps = b.get("caps") or []
    names = {c.get("name") for c in caps}
    counts = b.get("counts") or {}
    items = a.get("items") or []
    acounts = a.get("counts") or {}

    # C1 真源可读 + 计数守恒（**全部现算，不写死**：曾把 240/326 写死，能力位到 241、审计到 333 时误报红）
 # 2026-10-13 修（**既有红**，已记在 `docs/V8-V9-能力差集-20261012.md:99`）：
    #    这里原来只加「接上/断连/缺失/未探测」四态，而审计器/审计页/文档的口径是**五态**
    #    （第五态 = **按需未启用**：只在用到那个 provider 时才需要、凭据在主人侧 ⇒ **没跑不是故障**）。
    #    ⇒ 只要第五态非 0，C1 就**永远红**（动手前实测 355≠360，同一个失败式）。
    #    改法：**把第五态也纳入守恒**，并**要求五个键都在**（缺键不再当 0 蒙过去）——
    #    这是**补全**不是放宽：守恒式从「四态和=总项」变成「**五态和=总项且五键齐**」；
    #    配套负对照 N0（多报一条「按需未启用」⇒ C1 必须红）保证它仍有牙。
    _AUDIT_STATES = ("接上", "断连", "缺失", "未探测", "按需未启用")
    n_caps = len(caps)
    n_audit = len(items)
    st_sum = sum(acounts.get(k, 0) for k in _AUDIT_STATES)
    cons = (n_caps == counts.get("caps") and counts.get("caps_unbound") == 0
            and (counts.get("caps_tentacle", 0) + counts.get("caps_direct", 0) == n_caps)
            and n_audit == acounts.get("total")
            and all(k in acounts for k in _AUDIT_STATES)
            and st_sum == n_audit)
    add("C1 真源可读且计数守恒（能力位 / 审计项 / 三边零未绑 / 五态和=总数）", cons,
        "caps %d（tentacle %s + direct %s · 未绑 %s）· audit items %d · 五态和 %s"
        % (len(caps), counts.get("caps_tentacle"), counts.get("caps_direct"),
           counts.get("caps_unbound"), len(items), st_sum))

    # C2 族：30 个域全部有中文名（表不全 ⇒ 红；页面不许显示生造中文）
    doms = sorted({c.get("domain") for c in caps if c.get("domain")})
    missing_cn = [d for d in doms if d not in DOMAIN_CN]
    page = art.get("page") or ""
    table_in_page = all(d in page for d in doms)
    add("C2 族（域）30 个：中文名表齐全 + 页面按域现算（不写死族数）",
        (not missing_cn) and len(doms) == 30 and table_in_page,
        "域 %d 个 · 缺中文名 %s · 页面含全部域 token=%s" % (len(doms), missing_cn or "无", table_in_page))

    # C3 三态一色：映射唯一 + 未探测≠接上 + 三色各就各位（品牌三色，不引第四色）
    css_out = _root_outside(page) or ""
    rule_on = re.search(r"\.cb-st-on\b[^{]*\{([^}]*)\}", page)
    rule_off = re.search(r"\.cb-st-off\b[^{]*\{([^}]*)\}", page)
    rule_unk = re.search(r"\.cb-st-unk\b[^{]*\{([^}]*)\}", page)
    miss_same_as_off = re.search(r"\.cb-st-miss\b[^{]*\{([^}]*)\}", page)
    map_ok = ('"接上": "on"' in page.replace("'", '"') or '接上:"on"' in page.replace(" ", "")
              or '接上' in page and '"on"' in page)
    distinct = bool(rule_on) and bool(rule_unk) and (rule_on.group(1) != rule_unk.group(1))
    unk_not_on = bool(rule_unk) and ("--gbt-cyan" not in rule_unk.group(1)) and ("--cb-on" not in rule_unk.group(1))
    on_is_cyan = bool(rule_on) and ("--gbt-cyan" in rule_on.group(1) or "--cb-on" in rule_on.group(1))
    off_is_gold = bool(rule_off) and ("--gbt-gold" in rule_off.group(1) or "--cb-off" in rule_off.group(1))
    unk_is_violet = bool(rule_unk) and ("--gbt-violet" in rule_unk.group(1) or "--cb-unk" in rule_unk.group(1))
    miss_is_gold = bool(miss_same_as_off) and ("--gbt-gold" in miss_same_as_off.group(1)
                                               or "--cb-off" in miss_same_as_off.group(1))
    add("C3 三态一色：接上=青 / 断连=金 / 未探测=紫（**未探测不画成通**）· 缺失=金+虚（不引第四色）",
        map_ok and distinct and unk_not_on and on_is_cyan and off_is_gold and unk_is_violet and miss_is_gold,
        "映射=%s 类各异=%s 未探非青=%s 接上青=%s 断连金=%s 未探紫=%s 缺失金=%s"
        % (map_ok, distinct, unk_not_on, on_is_cyan, off_is_gold, unk_is_violet, miss_is_gold))

    # C4 每个数字带来源与时刻（三源文件名 + 生成时刻 + 页面声明 + 证据窗口口径）
    srcs = [("state/cap-bindings.json", "cap-bindings.json"), ("state/capability-audit.json", "capability-audit.json")]
    has_src = all(tok in page for _, tok in srcs) and "run-evidence.js" in page
    has_times = page.count("generated_at") >= 2 and "at" in page
    ev = _parse_global_js(art.get("evidence_js") or "", "GBT_CAPBAR_EVIDENCE")
    ev_ok = bool(ev) and all(k in ev for k in ("at", "window_hours", "read_bytes", "capped", "ledger", "map"))
    decl = ("window.GBT_DATA" in page) and ("快照" in page)
    add("C4 每个数字带来源与时刻（三源 + 生成时刻 + 窗口口径 + 页面声明形态/时刻）",
        has_src and has_times and ev_ok and decl,
        "源名齐=%s 时刻=%s 证据件含口径=%s 页面声明=%s" % (has_src, has_times, ev_ok, decl))

    # C5 页面自包含：零外链 / 无取数原语 / 无 eval / 无 iframe / 无 module
    body = art.get("page") or ""
    bad = []
    if _EXT_RE.findall(body):
        bad.append("外链 %d 处" % len(_EXT_RE.findall(body)))
    if "cdn" in body.lower():
        bad.append("cdn 字样")
    low = body.lower()
    for tok in ("<iframe", "fetch(", "xmlhttprequest", "eval(", "websocket", "eventsource"):
        if tok in low:
            bad.append(tok)
    if re.search(r'type\s*=\s*["\']module["\']', body, re.I):
        bad.append('type="module"')
    for need in ("run-evidence.js", "../energy/energy-data.js", "../capabilities/capabilities-data.js"):
        if need not in body:
            bad.append("未引 " + need)
    add("C5 页面自包含：零外链 · 无远端取数原语 · 无 eval/iframe/module · 数据只走经典脚本",
        not bad, "违规：%s" % (bad or "无"))

    # C6 裸色值只许在 :root / 三色声明即引用 / 无 emoji 图标
    bare = []
    no_comment = _strip_comments(css_out)
    if _BARE_COLOR.search(no_comment):
        bare = _BARE_COLOR.findall(no_comment)
    all3 = all(("--gbt-" + t) in page for t in ("gold", "cyan", "violet"))
    used3 = all(("var(--gbt-" + t + ")") in no_comment for t in ("gold", "cyan", "violet"))
    emo = _EMOJI.findall(_strip_comments(body))
    add("C6 视觉纪律：裸色值只在 :root · 三色声明即引用 · 无 emoji 图标",
        (not bare) and all3 and used3 and (not emo),
        "裸色值 %s · 三色声明 %s/引用 %s · emoji %s" % (bare[:4] or "无", all3, used3, emo[:3] or "无"))

    # C7 零打扰：尊重 prefers-reduced-motion
    rm = "prefers-reduced-motion" in page
    add("C7 零打扰：有 `prefers-reduced-motion` 块（动效可关）", rm, "块在=%s" % rm)

    # C8 可点到处不掉链：页面里的"详页"指针必须在册（页 id 取 windows.json / panel PAGES 现读）
    ids = set()
    try:
        reg = json.loads((ROOT / "holo_pet_w3" / "shell" / "windows.json").read_text(encoding="utf-8"))
        ids |= {w.get("id") for w in reg.get("windows") or []}
    except Exception:                                               # noqa: BLE001
        pass
    panel = _read(ROOT / "holo_pet_w3" / "panel" / "index.html")
    ids |= set(re.findall(r'id:\s*"([a-z0-9\-]+)"', panel))
    ptr = set()
    m_ptr = re.search(r"PTR_PAGES\s*=\s*\{([^}]*)\}", page)
    if m_ptr:
        ptr = set(re.findall(r'"([a-z0-9\-]+)"\s*:', m_ptr.group(1)))
    dead = sorted(p for p in ptr if p not in ids)
    # 调用法：名字必须**在册**（不许给不存在的能力位写调用法）
    calls = set(re.findall(r"py -3\.14 -m gbt_allinone run ([A-Za-z0-9_]+)", page))
    fake_calls = sorted(c for c in calls if names and c not in names)
    add("C8 可点到处不掉链：详页指针在册 · 调用法给的是在册能力位（或明写无对应页）",
        (not dead) and (not fake_calls) and len(ptr) > 0,
        "详页指针 %s（死链 %s）· 调用法名字 %s（不在册 %s）" % (sorted(ptr), dead or "无", sorted(calls)[:4], fake_calls or "无"))

    # C9 插件半边（A 腿）：加行不加锁 · 零 window.open · 只读白名单 · 不写盘/不碰 ~/.dsh
 # 对**代码**断言、不对**文本**断言（本仓教训：注释里提到这些词不算违规）⇒ 先剥注释。
    host = _strip_comments(art.get("host_js") or "")
    client = _strip_comments(art.get("client_js") or "")
    pkg = art.get("plugin_pkg") or ""
    p9 = []
    if not host or not client or not pkg:
        p9.append("插件半边缺件")
    if re.search(r"window\.open\b", client):
        p9.append("client 用了 window.open")
    if re.search(r"\bdisable\b", client):
        p9.append("client 出现 disable（加法不许减法）")
    for tok in ("writeFile", "appendFile", "mkdir", "createWriteStream"):
        if tok in host:
            p9.append("host 出现写盘原语 " + tok)
    if re.search(r"[~\\/]\.dsh\b", host) or ".dsh/" in host:
        p9.append("host 出现 ~/.dsh 路径（不许碰官方 APP 侧）")
    if '"@deepseek-ai/' in host or "dsh-client-ui-capability" in host:
        p9.append("host 出现内部标识")
    if "sidebar.footer.action" not in client or "shell.overlay" not in client:
        p9.append("client 未注册 左栏脚部/浮层 两格")
    # 三处名字要对得上：宿主路由前缀 / 包名 / bundle id（名字错了 = 挂上去也不对账）
    bundle_id = (re.search(r'__ModuleLoader__\.load\(\s*\{\s*id:\s*"([^"]+)"', client) or [None, ""])[1] \
        if re.search(r'__ModuleLoader__\.load\(\s*\{\s*id:\s*"([^"]+)"', client) else ""
    try:
        pkg_name = (json.loads(pkg) or {}).get("name", "") if pkg else ""
    except Exception:                                               # noqa: BLE001
        pkg_name = ""
    if "/gbt-capability-bar" not in host:
        p9.append("host 路由前缀不是 /gbt-capability-bar")
    if "capability-bar" not in pkg_name:
        p9.append("包名不含 capability-bar（包名即 specifier）")
    if "capability-bar" not in bundle_id:
        p9.append("bundle id 不含 capability-bar：%r" % bundle_id)
    add("C9 插件半边（A 腿）：加法加装（无 window.open / 无 disable）· 宿主只读无写盘 · 不碰 ~/.dsh · 三处名字对账",
        not p9, "；".join(p9) or ("无违规（包名 %s · bundle %s）" % (pkg_name, bundle_id)))

    # C10 快照 ↔ 真源同步（防漂：拿别人的记录冒充他、或条数对不上）
    ev_map = (ev or {}).get("map") or {}
    ghost = sorted(k for k in ev_map if names and k not in names)
    add("C10 运行证据快照与真源同步：map 的键全在册（不拿不在册 kind 冒充）",
        bool(ev) and not ghost and len(ev_map) <= len(names),
        "map 键 %d · 不在册 %s" % (len(ev_map), ghost[:5] or "无"))

    # C11 页面自报契约（--live 端到端门要读它）
    selfrep = "window.__gbtCapBar" in page and "classify" in page
    add("C11 页面自报 `window.__gbtCapBar`（含 classify/计数/源时刻：给端到端门读）", selfrep,
        "自报挂钩=%s" % selfrep)

    # C12 能力栏顶栏一格：**全族健康摘要**（神经）已随证据件落盘且与真源自洽
 # 口径：神经折进 run-evidence.js（页本就加载它）；页**结构**不动（holo_pet_w3 只经生成器产）。
    #    判据只认"证据件里有 nerve 且计数与绑定/审计自洽"，**不认页面有没有画**（那是页的事）。
    ncell = (ev or {}).get("nerve")
    doms_n = len({c.get("domain") for c in caps if c.get("domain")})
    ncz = [
        (isinstance(ncell, dict), "证据件无 nerve 块（顶栏一格未落）"),
        (bool(ncell) and not ncell.get("error"), "神经块带 error：%s" % ((ncell or {}).get("error"))),
        (bool(ncell) and ncell.get("未绑") == counts.get("caps_unbound"),
         "神经未绑 %s ≠ 台账未绑 %s" % ((ncell or {}).get("未绑"), counts.get("caps_unbound"))),
        (bool(ncell) and ncell.get("families") == doms_n,
         "神经族数 %s ≠ 域数 %s" % ((ncell or {}).get("families"), doms_n)),
        (bool(ncell) and ncell.get("caps") == n_caps,
         "神经位数 %s ≠ 能力位 %s" % ((ncell or {}).get("caps"), n_caps)),
    ]
    c12_bad = [why for ok, why in ncz if not ok]
    add("C12 能力栏顶栏一格：全族健康摘要（神经）已随证据件落盘且与真源自洽",
        not c12_bad and bool(ncell),
        "；".join(c12_bad) or ("神经 %s" % (ncell or {}).get("text")))

    return rows


def cmd_check(as_json: bool = False, live: bool = False) -> int:
    art = build_artifacts()
    rows = run_checks(art)
    negs = []

    def neg(name, cid, want_ok_false, art2):
        got = [r for r in run_checks(art2) if r["id"].split(" ", 1)[0] == cid]
        good = bool(got) and all((not r["ok"]) is want_ok_false for r in got)
        negs.append({"name": name, "target": cid, "ok": good,
                     "detail": "；".join("%s=%s" % (r["id"].split(" ", 1)[0], "绿!" if r["ok"] else "红")
                                         for r in got)})

    # N1 页面掏空（空页）⇒ C2/C3/C4/C5/C8 必须报红
    a0 = dict(art)
    a0["page"] = ""
    got = [r for r in run_checks(a0) if r["id"].split(" ", 1)[0] in ("C2", "C3", "C4", "C5", "C8")]
    negs.append({"name": "喂坏：页面掏空", "target": "C2+C3+C4+C5+C8",
                 "ok": bool(got) and all(not r["ok"] for r in got),
                 "detail": "；".join("%s=%s" % (r["id"].split(" ", 1)[0], "绿!" if r["ok"] else "红") for r in got)})

    # N0 **审计五态和 ≠ 总项数**（多报一条「按需未启用」）⇒ C1 必须报红
    #    （2026-10-13 补 C1 第五态时同批补的负对照：判据改了就必须证明它**还咬得住**）
    a9 = dict(art)
    if isinstance(art.get("audit"), dict):
        _aud = json.loads(json.dumps(art["audit"], ensure_ascii=False))
        _aud.setdefault("counts", {})
        _aud["counts"]["按需未启用"] = int(_aud["counts"].get("按需未启用", 0)) + 1
        a9["audit"] = _aud
    neg("喂坏：审计五态和 ≠ 总项数（多报一条「按需未启用」）", "C1", True, a9)

    # N2 **把「未探测」画成「通」**（未探测类的颜色改成青）⇒ C3 必须报红
    a1 = dict(art)
    a1["page"] = re.sub(r"\.cb-st-unk\b([^{]*)\{([^}]*)\}",
                        lambda m: ".cb-st-unk%s{ color: var(--gbt-cyan); }" % m.group(1), art["page"], count=1)
    neg("喂坏：把「未探测」画成「通」（改成品牌青）", "C3", True, a1)

    # N3 **数字缺来源/时刻**（抹掉 generated_at 读取）⇒ C4 必须报红
    a2 = dict(art)
    a2["page"] = art["page"].replace("generated_at", "GENERATED_AT_X").replace("window.GBT_DATA", "window.GBT_DATA_X")
    neg("喂坏：数字缺来源/时刻（抹掉 generated_at 与声明）", "C4", True, a2)

    # N4 **页面出现外链** ⇒ C5 必须报红
    a3 = dict(art)
    a3["page"] = art["page"] + '\n<link rel="stylesheet" href="https://cdn.example.com/x.css">'
    neg("喂坏：页面出现外链（https cdn）", "C5", True, a3)

    # N5 裸色值注入（:root 之外）⇒ C6 必须报红
    a4 = dict(art)
    a4["page"] = art["page"].replace("</style>", ".cb-x{color:#123456;}\n</style>", 1)
    neg("喂坏：:root 之外注入裸色值 #123456", "C6", True, a4)

    # N6 **死链**：把详页指针清单里塞一个不存在的页 id ⇒ C8 必须报红
 # 夹具必须用**同形 id**（小写 ASCII）—— 第一版用了中文串，正则 `[a-z0-9-]+` 本来就匹配不到它，
    #    于是"喂坏"那一臂自身是空的 ⇒ C8 照样绿（负对照自己先假绿了一回，已修，留档防重犯）。
    a5 = dict(art)
    a5["page"] = art["page"].replace('"energy": "能量与绑定',
                                     '"no-such-page": "x", "energy": "能量与绑定', 1)
    neg("喂坏：详页指针清单塞不在册的页 id（死链）", "C8", True, a5)

    # N7 插件半边踩红线（window.open + 写盘 + 碰 ~/.dsh）⇒ C9 必须报红
    a6 = dict(art)
    a6["client_js"] = art["client_js"] + "\nfunction bad(){ window.open('/x'); }"
    a6["host_js"] = art["host_js"] + "\nimport { writeFileSync } from 'node:fs'\nconst p='~/.dsh/profiles/web/x.json'"
    neg("喂坏：插件用了 window.open / 写盘 / 碰 ~/.dsh", "C9", True, a6)

    # N8 拿不在册的 kind 冒充（证据 map 里塞幽灵位）⇒ C10 必须报红
    a7 = dict(art)
    ghost = {"并不存在的位": {"s": "ok", "at": "2026-10-08T00:00:00", "raw": "{}"}}
    a7["evidence_js"] = re.sub(r'"map":\{', '"map":' + json.dumps(ghost, ensure_ascii=False)[:-1] + ",",
                               art["evidence_js"], count=1)
    neg("喂坏：运行证据里塞不在册的幽灵位（拿别人记录冒充）", "C10", True, a7)

    # N9 神经块被掏空（顶栏一格未落）⇒ C12 必须报红
    a8 = dict(art)
    a8["evidence_js"] = re.sub(r'"nerve":\{[^}]*(\{[^}]*\}[^}]*)*\}', '"nerve":{"error":"负对照：掏空"}',
                               art["evidence_js"], count=1)
    neg("喂坏：神经块掏空（顶栏一格未落）", "C12", True, a8)

    live_row = None
    if live:
        live_row = run_live(art)

    fails = [r for r in rows if not r["ok"]]
    nfail = [n for n in negs if not n["ok"]]
    ok = (not fails) and (not nfail) and (live_row is None or live_row["ok"])

    if as_json:
        print(json.dumps({"ok": ok, "rows": rows, "negs": negs, "live": live_row}, ensure_ascii=False))
        return 0 if ok else 1

    print("能力栏 · 判据（含负对照）")
    print("  页面：%s" % art["paths"]["page"])
    print("  证据：%s" % art["paths"]["evidence"])
    print("  插件：%s" % art["paths"]["plugin"])
    print("-" * 90)
    for r in rows:
        print("%s %-70s %s" % ("PASS" if r["ok"] else "FAIL", r["id"][:70], r["detail"][:120]))
    for n in negs:
        print("%s 负对照[%-9s] %-40s %s" % ("PASS" if n["ok"] else "FAIL", n["target"], n["name"][:40],
                                            n["detail"][:110]))
    if live_row is not None:
        print("%s 端到端[--live] %-40s %s" % ("PASS" if live_row["ok"] else "FAIL",
                                              "页面自报 vs 真源现算", live_row["detail"][:150]))
    print("-" * 90)
    print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d%s"
          % (len(rows) - len(fails), len(fails), len(negs) - len(nfail), len(nfail),
             "" if live_row is None else (" ｜ 端到端 %s" % ("PASS" if live_row["ok"] else "FAIL"))))
    return 0 if ok else 1


# ── 端到端门（--live）：真 Electron 打开页面，读页面自报，与真源现算逐项对 ──────
LIVE_JS = r"""
/* 端到端读数器（临时件，落在 %TEMP%）：打开能力栏页面 ⇒ 读 window.__gbtCapBar ⇒ 打印 JSON。
   只读本地 file:// 页面，不联网。 */
const { app, BrowserWindow } = require("electron");
const p = process.argv[2];
app.whenReady().then(async () => {
  const win = new BrowserWindow({ show: false, width: 1400, height: 900,
    webPreferences: { contextIsolation: true, nodeIntegration: false, offscreen: true } });
  const out = { ok: false };
  try {
    await win.loadFile(p);
    await new Promise((r) => setTimeout(r, 900));
    out.report = await win.webContents.executeJavaScript("window.__gbtCapBar || null", true);
    out.errs = await win.webContents.executeJavaScript(
      "(window.__gbtCapBar && window.__gbtCapBar.errors) || []", true);
    out.ok = !!out.report;
  } catch (e) { out.error = String((e && e.message) || e); }
  console.log("GBT_CAPBAR_LIVE_JSON=" + JSON.stringify(out));
  app.exit(0);
});
"""


def run_live(art: dict) -> dict:
    """真浏览器端到端：页面自报的计数必须等于**判据侧从真源现算**的计数。

    ⚠️ 口径：页面在 file:// 下用的是 run-evidence.js 快照，判据侧用**同一份快照**现算，
       所以这是一条"页面渲染链路对不对"的门（不是"真源变没变"的门 —— 那条是 C1/C10）。
    """
    import tempfile
    page = art["paths"]["page"]
    if not Path(page).is_file():
        return {"ok": False, "detail": "页面不在盘上：" + page}
    ev = _parse_global_js(art.get("evidence_js") or "", "GBT_CAPBAR_EVIDENCE") or {}
    b = art.get("bindings") or {}
    names = [(c.get("name"), c.get("domain")) for c in (b.get("caps") or [])]
    want = {}
    for name, _dom in names:
        r = (ev.get("map") or {}).get(name)
        want["接上" if (r and r.get("s") == "ok") else ("断连" if r else "未探测")] = \
            want.get("接上" if (r and r.get("s") == "ok") else ("断连" if r else "未探测"), 0) + 1
    want = {"接上": want.get("接上", 0), "断连": want.get("断连", 0), "未探测": want.get("未探测", 0)}
    tmp = Path(tempfile.gettempdir()) / "gbt-capbar-live.cjs"
    tmp.write_text(LIVE_JS, encoding="utf-8")
    try:
        proc = subprocess.run(["npx", "electron", str(tmp), page], capture_output=True, text=True,
                              timeout=120, cwd=str(ROOT), shell=(os.name == "nt"))
        out = proc.stdout or ""
        m = re.search(r"GBT_CAPBAR_LIVE_JSON=(\{.*\})", out, re.S)
        if not m:
            return {"ok": False, "detail": "取不到页面自报（electron 无输出）：" + (out or proc.stderr or "")[-160:]}
        rep = json.loads(m.group(1))
        r = rep.get("report")
        if not r:
            return {"ok": False, "detail": "页面没有自报 window.__gbtCapBar：" + str(rep.get("error") or rep.get("errs"))[:120]}
        got = {k: (r.get("counts") or {}).get(k, -1) for k in want}
        same = all(got[k] == want[k] for k in want)
        extra = []
        if r.get("counts", {}).get("caps") != len(names):
            extra.append("caps=%s≠%s" % (r.get("counts", {}).get("caps"), len(names)))
        cls = (r.get("classify") or {})
        if cls.get("未探测") == cls.get("接上"):
            extra.append("未探测与接上同类（画成通）")
        return {"ok": bool(same and not extra),
                "detail": "页面自报 %s ｜ 判据现算 %s ｜ 差异 %s ｜ 页内错误 %s"
                          % (got, want, extra or "无", (rep.get("errs") or [])[:2] or "无"),
                "yielded": rep.get("at")}
    except Exception as e:                                          # noqa: BLE001
        return {"ok": False, "detail": "端到端跑不起来：" + repr(e)[:160]}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `--check` 与 `check` 等价（仓里两种写法都有人用）；argparse 会把 `--check` 当未知选项 ⇒ 先归一
    verb = "refresh"
    if "--check" in argv:
        argv = [a for a in argv if a != "--check"]
        verb = "check"
    ap = argparse.ArgumentParser(description="能力栏 · 运行证据快照 + 判据（含负对照）")
    ap.add_argument("verb", nargs="?", default=verb, choices=["refresh", "check"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--live", action="store_true", help="追加真浏览器端到端（页面自报 vs 真源现算）")
    args = ap.parse_args(argv)
    if args.verb == "refresh":
        return cmd_refresh(args.json)
    return cmd_check(args.json, args.live)


if __name__ == "__main__":
    raise SystemExit(main())
