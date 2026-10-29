# -*- coding: utf-8 -*-
"""项目蓝图可视化面板 · 生成器 / 判据（主人令 2026-10-07）。

## 它做什么

把**仓里已有的四样真源**现读现算，落成「一页看全项目蓝图」的自包含页 + 数据件：

| 块 | 真源 | 现读什么 |
|---|---|---|
| 边界环（主从 / 允许 / 禁止） | `PROJECT_BLUEPRINT.md` §一 | 三小节的 bullet 逐条（不抄表、不手打） |
| 蓝图骨架（§一…§九） | 同上 | 每节标题 + 起行（行号现数） |
| 树登记表 | `state/tree-registry.json` | 按 `class` 分组，逐棵 `path` + `why` |
| 窗口登记表 | `holo_pet_w3/shell/windows.json` | `id` / `title` / `file` / 默认可见 |
| 落地顺序 Phase 0–5 | `PROJECT_BLUEPRINT.md` §六 | 六段的 bullet |
| 风险登记 | `PROJECT_BLUEPRINT.md` §五 | `R1…R7` 逐条 |
| 故障登记（F 编号） | `PROJECT_BLUEPRINT.md` §九 | `FL1…FL10` 逐条 + 9.1 的 Q1–Q3 |
| 装机回执读数 | `state/desktop-install-receipt.json`（若存在） | 逐项机检 |

## 三条纪律（照仓内先例）

1. **一切数字现算**：章节行号、树数、窗口数、Phase 段数、FL 条数 —— 全部 `--check` 现读现数。
   源文件改了，面板就跟着变；**不写死一个数字**（写死一次就过期一次）。
2. **数据走经典脚本**：页面走 `file://`，`fetch()` 读不到本地 json ⇒ 数据以
   `<script src="blueprint-data.js">` **经典脚本**内嵌（`brain-feed.py` 起头的仓内做法，不是新发明）。
   页面**同时把每块静态烘进 HTML**（照 `cloud-plugins.py` 的「生成期落图」）—— 脚本被禁也看得见。
3. **缺源就报红**，不许出个空页面装作正常。`--check` 的判据带**正负对照**：
   正对照 = 真源在册、九节齐、三分类非空；负对照 = 把模型故意掏空 / 塞坏数据，
   判据必须**报红**（自证不是「无脑全绿」）。

## 用法

    py -3.14 tools/codex-scripts/blueprint-feed.py            # 生成页 + 数据件（同 gen）
    py -3.14 tools/codex-scripts/blueprint-feed.py --check    # 逐条判据（退出码 0=全过）
    py -3.14 tools/codex-scripts/blueprint-feed.py --check --json

只读真源；只写下面三个文件；不联网、不起服务、不删东西。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
# 审美令牌（内联版）：唯一实现在 `_taste_inline.py`（别在这里再抄一份）。
# 本页 C8 判据要求「自包含 · 零外链」，所以只能生成期内联，不能挂 <link>。
from _taste_inline import site_root_block  # noqa: E402
from _page_emit import clean_html  # noqa: E402

BLUEPRINT = ROOT / "PROJECT_BLUEPRINT.md"
TREES = ROOT / "state" / "tree-registry.json"
WINDOWS = ROOT / "holo_pet_w3" / "shell" / "windows.json"
RECEIPT = ROOT / "state" / "desktop-install-receipt.json"

DATA_JS = ROOT / "holo_pet_w3" / "blueprint" / "blueprint-data.js"
PAGE = ROOT / "holo_pet_w3" / "blueprint" / "index.html"

# 重生成命令（写在页面上，主人照抄即可）—— 与 windows.json 里登记的口径一致
REGEN_CMD = "py -3.14 tools/codex-scripts/blueprint-feed.py"

# 九节的锚（**按标题现匹配**，不按行号写死）：改序、插节都不会让骨架错位
SEC_ANCHORS = [
    ("一", "系统边界", r"^##\s*一、\s*系统边界"),
    ("二", "系统 DAG", r"^##\s*二、\s*系统\s*DAG"),
    ("三", "模块状态", r"^##\s*三、\s*模块状态"),
    ("四", "关键依赖链", r"^##\s*四、\s*关键依赖链"),
    ("五", "风险登记", r"^##\s*五、\s*风险登记"),
    ("六", "落地顺序", r"^##\s*六、\s*落地顺序"),
    ("七", "完成判定", r"^##\s*七、\s*完成判定"),
    ("八", "基线验证", r"^##\s*八、\s*基线验证"),
    ("九", "故障登记", r"^##\s*九、\s*故障登记（.*?）?\s*$|^##\s*九、\s*故障登记"),
]


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════════════
# 探针：把 markdown 切成「九节 + 各节体」，再从节体里取表 / 取 bullet
# ══════════════════════════════════════════════════════════════════════════════

def split_sections(text: str) -> dict:
    """按 `SEC_ANCHORS` 现切九节。返回 `{节号: {title, line, body, body_lines}}`。

    为什么必须按标题切、不按行号：本文件是**活文档**（尾部挂着一长串「挂账变更」），
    行号天天动；写死行号就是把面板绑死在一个过期快照上。
    """
    lines = text.splitlines()
    hits = {}
    for n, title, rx in SEC_ANCHORS:
        pat = re.compile(rx)
        for i, ln in enumerate(lines):
            if pat.match(ln.strip()):
                hits[n] = {"title": title, "idx0": i}
                break
    out = {}
    order = [n for n, _t, _r in SEC_ANCHORS]
    for k, n in enumerate(order):
        if n not in hits:
            continue
        start = hits[n]["idx0"]
        end = len(lines)
        for m in order[k + 1:]:                      # 下一节的开头 = 本节结尾
            if m in hits:
                end = hits[m]["idx0"]
                break
        out[n] = {"title": hits[n]["title"], "line": start + 1,
                  "body_lines": lines[start:end],
                  "body": "\n".join(lines[start:end])}
    return out


def first_table(body: str) -> list:
    """取节体里的**第一张** markdown 表，返回 `[ {列名: 值} … ]`（表头按原样当键）。"""
    out = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        head = lines[i].strip()
        if head.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            cols = [c.strip() for c in head.strip("|").split("|")]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                if len(cells) == len(cols):
                    out.append(dict(zip(cols, cells)))
                j += 1
            return out
        i += 1
    return out


def bullets(body: str) -> list:
    """取 `- ` 开头的行（去 markdown 装饰符 `**` 留给渲染层处理）。"""
    return [ln.strip()[2:].strip() for ln in body.splitlines()
            if ln.strip().startswith("- ") and ln.strip() != "-"]


def subsections(body: str) -> dict:
    """把节体按 `### ` 小节切开：`{小节标题: 体}`。"""
    out, cur, buf = {}, None, []
    for ln in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", ln)
        if m:
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1).strip(), []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def mermaid_text(body: str) -> str:
    """取第一个 ```mermaid 代码块的内容（DAG / 依赖链现读，不画假线）。"""
    m = re.search(r"```mermaid\s*\n(.*?)```", body, re.S)
    return m.group(1) if m else ""


# ══════════════════════════════════════════════════════════════════════════════
# 四个解析器（都吃「文本 / 数据」，不吃文件路径 ⇒ 判据的负对照能拿坏料喂它们）
# ══════════════════════════════════════════════════════════════════════════════

def parse_blueprint(text: str) -> dict:
    secs = split_sections(text or "")
    n_lines = len((text or "").splitlines())

    # §一 系统边界：三小节 = 三类。缺一小节就是缺一类 ⇒ 判据会红。
    boundary = {"master_slave": [], "allowed": [], "forbidden": []}
    b1 = subsections(secs.get("一", {}).get("body", ""))
    for key, rx in (("master_slave", r"^1\.1"), ("allowed", r"^1\.2"), ("forbidden", r"^1\.3")):
        for title, sub in b1.items():
            if re.match(rx, title):
                boundary[key] = bullets(sub)
                break

    # §二 系统 DAG：现数节点与边（mermaid）
    dag = mermaid_text(secs.get("二", {}).get("body", ""))
    dag_nodes = sorted({m.group(1) for m in re.finditer(r"^\s*([A-Za-z_]\w*)\[", dag, re.M)})
    dag_edges = len(re.findall(r"-->\s*[A-Za-z_]\w*", dag))
    # 节点分组（classDef/class 行现读）—— 骨架里给出自治层数
    dag_classes = [m.group(1).strip() for m in re.finditer(r"^\s*class\s+([^;\n]+?)\s+\w+\s*$", dag, re.M)]

    # §三 模块状态
    modules = first_table(secs.get("三", {}).get("body", ""))

    # §四 关键依赖链：mermaid 里的 `[标签]` 逐段取
    chain_fig = mermaid_text(secs.get("四", {}).get("body", ""))
    chain = [m.group(1).strip() for m in re.finditer(r"\[([^\]]+)\]", chain_fig)]

    # §五 风险登记
    risks = first_table(secs.get("五", {}).get("body", ""))

    # §六 落地顺序：Phase N + 其下 bullet
    phases, cur = [], None
    for ln in secs.get("六", {}).get("body", "").splitlines():
        m = re.match(r"^###\s*Phase\s*(\d+)\s*[：:]\s*(.+?)\s*$", ln)
        if m:
            cur = {"n": int(m.group(1)), "id": "Phase %d" % int(m.group(1)),
                   "title": m.group(2).strip(), "items": []}
            phases.append(cur)
        elif cur is not None and ln.strip().startswith("- "):
            cur["items"].append(ln.strip()[2:].strip())
    phases.sort(key=lambda p: p["n"])

    # §七 完成判定
    done = bullets(secs.get("七", {}).get("body", ""))

    # §八 基线验证：三张「红项」表的条数（现读现数，不抄 89 项那类旧结论）
    b8 = subsections(secs.get("八", {}).get("body", ""))
    baseline = []
    for title, sub in b8.items():
        rows = first_table(sub)
        if rows:
            baseline.append({"title": title.strip(), "n": len(rows),
                             "cols": list(rows[0].keys())})

    # §九 故障登记（F 编号体系）：FL 表 + 9.1 的 Q 表
    b9 = subsections(secs.get("九", {}).get("body", ""))
    faults = first_table(secs.get("九", {}).get("body", ""))
    faults = [r for r in faults if r.get("ID", "").startswith("FL")]
    q_rows = []
    for title, sub in b9.items():
        if title.startswith("9.1"):
            q_rows = first_table(sub)
            break

    return {
        "lines": n_lines,
        "bytes": len((text or "").encode("utf-8", "replace")),
        "sha16": _sha16(text or ""),
        "sections": [{"n": n, "title": secs[n]["title"], "line": secs[n]["line"],
                      "body_lines": len(secs[n]["body_lines"])}
                     for n, _t, _r in SEC_ANCHORS if n in secs],
        "boundary": boundary,
        "dag": {"nodes": len(dag_nodes), "edges": dag_edges,
                "node_names": dag_nodes, "class_groups": len(dag_classes)},
        "modules": modules,
        "chain": chain,
        "risks": risks,
        "phases": phases,
        "done": done,
        "baseline": baseline,
        "faults": faults,
        "fault_q": q_rows,
    }


def parse_trees(data: dict) -> dict:
    trees = list((data or {}).get("trees") or [])
    groups, order = {}, []
    for t in trees:
        c = str(t.get("class") or "未分类")
        if c not in groups:
            groups[c] = []
            order.append(c)
        groups[c].append({"path": t.get("path"), "class": c,
                          "why": t.get("why") or ""})
    grouped = [{"class": c, "n": len(groups[c]), "items": groups[c]} for c in order]
    return {
        "updated": (data or {}).get("updated"),
        "note": (data or {}).get("note") or "",
        "count": len(trees),
        "class_count": len(order),
        "groups": grouped,
        "forks": (data or {}).get("forks") or [],
        "view_families": (data or {}).get("view_families") or [],
        "protected": (data or {}).get("protected") or [],
        "pending_owner": (data or {}).get("pending_owner") or [],
    }


def parse_windows(data: dict) -> dict:
    wins = list((data or {}).get("windows") or [])
    items = [{"id": w.get("id"), "title": w.get("title"),
              "file": (w.get("file") or "").replace("\\", "/"),
              "role": w.get("role"), "visible": bool(((w.get("default") or {}).get("visible"))),
              "note": (w.get("note") or "")[:200]}
             for w in wins]
    return {"shell": (data or {}).get("shell"), "count": len(items),
            "visible_default": sum(1 for i in items if i["visible"]), "items": items}


def parse_receipt(data: dict) -> dict:
    d = data or {}
    art = d.get("artifact") or {}
    checks = list(d.get("checks") or [])
    return {"exists": True, "at": d.get("at"), "verdict": d.get("verdict"),
            "exe_bytes": art.get("exe_bytes"), "files": art.get("files"),
            "bytes": art.get("bytes"), "electronVersion": art.get("electronVersion"),
            "checks": [{"check": c.get("check"), "ok": bool(c.get("ok")),
                        "detail": c.get("detail")} for c in checks],
            "checks_n": len(checks),
            "checks_ok": sum(1 for c in checks if c.get("ok"))}


def build_model(blueprint_text: str, trees_data: dict, windows_data: dict,
                receipt_data: dict | None) -> dict:
    bp = parse_blueprint(blueprint_text)
    trees = parse_trees(trees_data)
    wins = parse_windows(windows_data)
    rc = parse_receipt(receipt_data) if receipt_data else {"exists": False}
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "regen_cmd": REGEN_CMD,
        "sources": {
            "blueprint": _rel(BLUEPRINT),
            "trees": _rel(TREES),
            "windows": _rel(WINDOWS),
            "receipt": _rel(RECEIPT),
        },
        "blueprint": bp,
        "trees": trees,
        "windows": wins,
        "receipt": rc,
        "counts": {
            "blueprint_lines": bp["lines"],
            "sections": len(bp["sections"]),
            "boundary_master": len(bp["boundary"]["master_slave"]),
            "boundary_allowed": len(bp["boundary"]["allowed"]),
            "boundary_forbidden": len(bp["boundary"]["forbidden"]),
            "dag_nodes": bp["dag"]["nodes"],
            "dag_edges": bp["dag"]["edges"],
            "modules": len(bp["modules"]),
            "chain_steps": len(bp["chain"]),
            "risks": len(bp["risks"]),
            "phases": len(bp["phases"]),
            "done": len(bp["done"]),
            "faults": len(bp["faults"]),
            "fault_q": len(bp["fault_q"]),
            "trees": trees["count"],
            "tree_classes": trees["class_count"],
            "windows": wins["count"],
            "windows_visible_default": wins["visible_default"],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# 判据（正负对照）
# ══════════════════════════════════════════════════════════════════════════════

def validate(model: dict, page_html: str = None, data_js: str = None,
             with_neg: bool = True) -> list:
    """把模型 / 页面 / 数据件过一遍判据。返回 `[(id, ok, detail)]`。

    这里**不碰文件系统**（面交给调用方）：负对照要能拿一个掏空的模型直接喂进来，
    必须当场见红 —— 否则这套判据和「无脑全绿」没有区别。
    `with_neg=False` 供**负对照自己**复跑判据时用（否则会无限递归）。
    """
    rows = []
    bp = model.get("blueprint") or {}
    tr = model.get("trees") or {}
    wn = model.get("windows") or {}
    c = model.get("counts") or {}
    bd = bp.get("boundary") or {}

    def add(cid, ok, detail):
        rows.append((cid, bool(ok), detail))

    # C1 真源可解析：九节齐 + 行数量级
    secs = {s["n"] for s in (bp.get("sections") or [])}
    add("C1 真源可解析·九节齐",
        secs >= {"一", "二", "三", "四", "五", "六", "七", "八", "九"} and (bp.get("lines") or 0) > 1000,
        "PROJECT_BLUEPRINT.md %s 行 / %s 字节 / sha16 %s · 命中节 %s"
        % (bp.get("lines"), bp.get("bytes"), bp.get("sha16"), "".join(sorted(secs)) or "无"))

    # C2 边界环三类非空（§一 1.1/1.2/1.3）
    add("C2 边界环·三分类非空",
        all(len(bd.get(k) or []) >= 1 for k in ("master_slave", "allowed", "forbidden")),
        "主从 %d 条 · 允许 %d 条 · 禁止 %d 条"
        % (len(bd.get("master_slave") or []), len(bd.get("allowed") or []), len(bd.get("forbidden") or [])))

    # C3 树登记表：非空 + 每棵有 path/why + 分组数
    n_tree, n_cls = int(tr.get("count") or 0), int(tr.get("class_count") or 0)
    bad_tree = [t["path"] for g in (tr.get("groups") or []) for t in g["items"]
                if not t.get("path") or not t.get("why")]
    add("C3 树登记表·逐棵有 path+why",
        n_tree >= 40 and not bad_tree and n_cls >= 5,
        "树 %d 棵 / 分组 %d 类 · 缺 why 或 path 的：%s"
        % (n_tree, n_cls, bad_tree or "无"))

    # C4 窗口登记表：非空 + 每窗 id/title/file
    n_win, n_vis = int(wn.get("count") or 0), int(wn.get("visible_default") or 0)
    bad_win = [w["id"] for w in (wn.get("items") or [])
               if not w.get("id") or not w.get("title") or not w.get("file")]
    add("C4 窗口登记表·每窗 id+title+file",
        n_win >= 5 and not bad_win,
        "窗口 %d 扇（默认可见 %d）· 缺件的：%s" % (n_win, n_vis, bad_win or "无"))

    # C5 落地顺序 Phase 0–5 六段齐 + 每段有 bullet
    nums = sorted(p["n"] for p in (bp.get("phases") or []))
    empty_ph = [p["id"] for p in (bp.get("phases") or []) if not p.get("items")]
    add("C5 落地顺序·Phase 0–5 六段齐且每段有料",
        nums == [0, 1, 2, 3, 4, 5] and not empty_ph,
        "段号 %s · 空段：%s" % (nums or "无", empty_ph or "无"))

    # C6 风险登记 R 编号 + 故障登记 FL 编号，逐条在册
    r_ids = [r.get("ID", "") for r in (bp.get("risks") or [])]
    f_ids = [r.get("ID", "") for r in (bp.get("faults") or [])]
    add("C6 风险 R + 故障 FL 逐条在册",
        len(r_ids) >= 3 and all(re.match(r"^R\d+$", x) for x in r_ids)
        and len(f_ids) >= 5 and all(re.match(r"^FL\d+$", x) for x in f_ids),
        "风险 %s · 故障 %s" % ("、".join(r_ids) or "无", "、".join(f_ids) or "无"))

    # C7 骨架：九节每节都有起行与体量
    add("C7 蓝图骨架·每节有起行+体量",
        len(bp.get("sections") or []) == 9 and all(s.get("line") and s.get("body_lines") for s in (bp.get("sections") or [])),
        "；".join("§%s:%d 行/%d 行体" % (s["n"], s["line"], s["body_lines"]) for s in (bp.get("sections") or []))[:220] or "无")

    # C8 页面在盘上 + 自包含 + 数据走经典脚本
    if page_html is None:
        add("C8 页面在盘上且自包含", False, "未提供页面文本")
    else:
        remote = re.findall(r'(?:src|href)\s*=\s*["\']https?://[^"\']+', page_html, re.I)
        has_fetch = bool(re.search(r"\bfetch\s*\(", page_html))
        has_eval = bool(re.search(r"\beval\s*\(", page_html))
        has_module = bool(re.search(r'<script[^>]*type\s*=\s*["\']module["\']', page_html, re.I))
        has_data = 'src="blueprint-data.js"' in page_html
        n_blocks = page_html.count('class="card"')
        add("C8 页面自包含·零外链/无fetch/无eval/非module",
            not remote and not has_fetch and not has_eval and not has_module and has_data and n_blocks >= 6,
            "外链 %s · fetch %s · eval %s · module %s · 数据脚本 %s · 块 %d"
            % (remote[:2] or "无", has_fetch, has_eval, has_module, has_data, n_blocks))

    # C9 数据件与页面同源：数据件里的计数 == 模型计数，且页面把关键数也写上了
    if data_js is None:
        add("C9 数据件与真源一致", False, "未提供数据件文本")
    else:
        m = re.search(r"globalThis\.GBT_BLUEPRINT\s*=\s*(\{.*\})\s*;", data_js, re.S)
        same = False
        why = "抽不到 globalThis.GBT_BLUEPRINT"
        if m:
            try:
                got = json.loads(m.group(1))
                same = (got.get("counts") or {}) == c
                why = "数据件计数与模型%s" % ("一致" if same else "**不一致**")
            except Exception as e:                                   # noqa: BLE001
                why = "数据件 JSON 解析失败：%s" % str(e)[:80]
        add("C9 数据件与真源一致（计数逐项相等）", same, why)

    # C10 装机回执（存在才判）：机检逐项 ok
    rc = model.get("receipt") or {}
    if rc.get("exists"):
        add("C10 装机回执·机检全绿",
            rc.get("checks_n", 0) >= 1 and rc.get("checks_ok") == rc.get("checks_n"),
            "回执 %s %s · 机检 %s/%s 绿"
            % (rc.get("verdict"), rc.get("at"), rc.get("checks_ok"), rc.get("checks_n")))
    else:
        add("C10 装机回执·存在且有件", False, "回执缺失：%s" % model.get("sources", {}).get("receipt"))

    # ── 负对照（自证不是「无脑全绿」）：把模型掏空 / 塞坏，判据必须见红 ──
    if not with_neg:
        return rows
    empty = {"blueprint": {"lines": 0, "sections": [], "boundary": {},
                           "phases": [], "risks": [], "faults": []},
             "trees": {"count": 0, "class_count": 0, "groups": []},
             "windows": {"count": 0, "items": []}, "receipt": {"exists": False},
             "counts": {}, "sources": {}}
    n_red = sum(1 for _id, ok, _d in validate(empty, "<html></html>", "Nothing", with_neg=False) if not ok)
    add("N1 负对照·空模型必见红（至少 8 条 FAIL）", n_red >= 8,
        "空模型触发 %d 条红（期望 ≥8）⇒ 判据不是摆设" % n_red)

    bad_bp = parse_blueprint("# 空文件\n\n没什么内容\n")
    add("N2 负对照·坏蓝图不产出边界/Phase",
        not bad_bp["boundary"]["master_slave"] and not bad_bp["phases"] and not bad_bp["sections"],
        "坏蓝图 ⇒ 主从 %d 条 · Phase %d 段 · 命中节 %d（都应 0）"
        % (len(bad_bp["boundary"]["master_slave"]), len(bad_bp["phases"]), len(bad_bp["sections"])))

    bad_page = '<html><head><script src="https://cdn.example.com/x.js"></script></head><body>fetch("/x")</body></html>'
    page_rows = validate(model, bad_page, data_js, with_neg=False)
    c8 = next((ok for cid, ok, _d in page_rows if cid.startswith("C8")), True)
    add("N3 负对照·带外链+fetch 的页必须见红", c8 is False,
        "含 https 外链与 fetch 的页 ⇒ C8 = %s（应 False）" % c8)

    bad_data = "globalThis.GBT_BLUEPRINT = {};"
    data_rows = validate(model, page_html, bad_data, with_neg=False)
    c9 = next((ok for cid, ok, _d in data_rows if cid.startswith("C9")), True)
    add("N4 负对照·数据件掏空必须见红", c9 is False,
        "计数掏空的数据件 ⇒ C9 = %s（应 False）" % c9)

    return rows


# ══════════════════════════════════════════════════════════════════════════════
# 渲染：**生成期静态落地**（照 cloud-plugins.py：脚本被禁也看得见，脚本只管交互）
# ══════════════════════════════════════════════════════════════════════════════

# 品牌 token 与专业皮肤：值照抄 `holo_pet_w3/window.css:4-46`（品牌三色 + 语义 token）
# 与 `holo_pet_w3/skin-mission-control.css:38-63`（MC 表面/描边/圆角/字号，@Mission Control）。
# **内联进本页**（照 plugins-mesh/index.html 的写法）：页面走 file://，外链一步都不许有。
# 2026-10-26：最前面先落一段**站点审美令牌**（`_taste_inline.site_root_block()`，
#    来源 state/taste/*.json → theme/taste-tokens.css），再把表面/文字/描边接上去 ——
#    **单一源仍然是 pin**，这里只是"把源搬进页面"。取不到令牌表时是空串，一切退回原值。
_TOKENS = site_root_block() + """
:root{
 --gbt-gold:#F5B041; --gbt-cyan:#00E5FF; --gbt-violet:#7C4DFF;
 --gbt-ok:#22C55E; --gbt-warn:#F5B041; --gbt-fault:#EF4444; --gbt-off:#6B7280;
 --gbt-text:var(--taste-text,#E8ECF8); --gbt-dim:var(--taste-muted,#9AA4C4);
 --gbt-warn-bg:rgba(245,176,65,.06); --gbt-cyan-bg:rgba(0,229,255,.06);
 --mc-bg:var(--taste-ground,#0B1120); --mc-surface:var(--taste-surface,#111827);
 --mc-border:var(--taste-border,#1E3A5F); --mc-border-subtle:var(--taste-rule,#162035);
 --mc-mono:"JetBrains Mono","Cascadia Mono",Consolas,ui-monospace,monospace;
 --mc-sans:"Segoe UI","Microsoft YaHei UI",system-ui,sans-serif;
 --mc-r:4px; --mc-r-pill:2px;
}
"""

_CSS = _TOKENS + """
*{box-sizing:border-box}
body{margin:0;background:var(--mc-bg);color:var(--gbt-text);font:13px/1.6 var(--mc-sans)}
.gbt-topbar{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--mc-border);
 /* 2026-10-26：原为 linear-gradient(90deg,#111827,#111827) —— 两档微渐变，取中点纯色。 */
 background:#0e141f;flex-wrap:wrap}
.mark{width:18px;height:18px;border:2px solid var(--gbt-gold);border-radius:var(--mc-r-pill)}
.brand{font-weight:700;letter-spacing:.5px}.brand b{color:var(--gbt-gold)}
.topbar-meta{margin-left:auto;text-align:right;font:11px/1.5 var(--mc-mono);color:var(--gbt-dim)}
.topbar-meta .mono{color:var(--gbt-cyan)}
.wrap{columns:2;column-gap:14px;padding:14px}
@media(max-width:1080px){.wrap{columns:1}}
.card{break-inside:avoid;background:var(--mc-surface);border:1px solid var(--mc-border);border-radius:var(--mc-r);
 padding:12px;margin:0 0 14px}
h2{margin:0 0 8px;font:600 13px/1.3 var(--mc-sans);color:var(--gbt-dim);text-transform:uppercase;letter-spacing:.06em}
.srcnote{font:11px/1.5 var(--mc-mono);color:var(--gbt-off);margin:-4px 0 8px}
.stats{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:6px}
.stat b{display:block;font:700 22px/1 var(--mc-mono);font-variant-numeric:tabular-nums;color:var(--gbt-gold)}
.stat i{font-style:normal;color:var(--gbt-dim);font-size:11px}
table{border-collapse:collapse;width:100%;font-size:11px}
th,td{border:1px solid var(--mc-border-subtle);padding:3px 5px;text-align:left;vertical-align:top}
th{color:var(--gbt-dim);font-weight:600;background:#111827}
td.k{font-family:var(--mc-mono);color:var(--gbt-cyan);white-space:nowrap}
.mono{font-family:var(--mc-mono)}
.dim{color:var(--gbt-dim)}
.off{color:var(--gbt-off)}
ul{margin:4px 0 0;padding-left:16px}li{margin:2px 0}
.pill{display:inline-block;border:1px solid var(--mc-border);border-radius:var(--mc-r-pill);padding:1px 6px;
 margin:2px 4px 2px 0;color:var(--gbt-dim);font-size:10.5px}
.pill.g{border-color:var(--gbt-ok);color:var(--gbt-ok)}
.pill.w{border-color:var(--gbt-warn);color:var(--gbt-warn);background:var(--gbt-warn-bg)}
.pill.b{border-color:#1E3A5F;color:var(--gbt-cyan)}
.pill.f{border-color:var(--gbt-fault);color:var(--gbt-fault)}
.ring{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
@media(max-width:760px){.ring{grid-template-columns:1fr}}
.ring>div{border:1px solid var(--mc-border-subtle);border-radius:var(--mc-r);padding:8px}
.ring h3{margin:0 0 6px;font:600 11.5px/1.3 var(--mc-sans);text-transform:uppercase;letter-spacing:.05em}
.ring .t-master h3{color:var(--gbt-gold)}.ring .t-allow h3{color:var(--gbt-ok)}.ring .t-forbid h3{color:var(--gbt-fault)}
.hr{height:1px;background:var(--mc-border-subtle);margin:8px 0}
.grp{margin:0 0 6px}
.chips{margin:2px 0 6px}
.small{font-size:11px}
footer{padding:10px 16px;border-top:1px solid var(--mc-border);color:var(--gbt-off);font:11px/1.6 var(--mc-mono)}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important}}
"""


_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2700-\u27BF\u2600-\u26FF\u2B00-\u2BFF\uFE0F]")


def _esc(s) -> str:
    """转义 + **出口清洗 emoji**（2026-10-26 主人令：界面/注释一律不留 emoji）。

    实测：本页「近空落点」那几行里的 ⚠️ 是**数据带来的**（不是模板写死），
    在转义口统一清掉，比去数据源头改更稳（数据是别的工具产的，会反复写回）。
    """
    s = _EMOJI.sub("", str("" if s is None else s))
    return (s.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _md(s) -> str:
    """极简内联渲染：`**粗**` → 粗体；其余转义。**不引任何库**。"""
    s = _esc(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def _srcnote(model: dict, src: str, extra: str = "") -> str:
    return ('<div class="srcnote">真源：%s%s · 现算：%s</div>'
            % (_esc(src), ("　" + _esc(extra)) if extra else "", _esc(model["generated_at"])))


def render_blocks(model: dict) -> dict:
    bp, tr, wn, rc = model["blueprint"], model["trees"], model["windows"], model["receipt"]
    c = model["counts"]
    gen = model["generated_at"]
    S = model["sources"]

    # ① 边界环
    bd = bp["boundary"]
    def _ul(items):
        return "<ul>" + "".join("<li>%s</li>" % _md(x) for x in items) + "</ul>" if items else "<div class='off'>（源里没有）</div>"
    ring = ('<div class="ring">'
            '<div class="t-master"><h3>不可动摇的主从关系 · %d</h3>%s</div>'
            '<div class="t-allow"><h3>允许自动化 · %d</h3>%s</div>'
            '<div class="t-forbid"><h3>明确禁止自动化 · %d</h3>%s</div></div>'
            % (len(bd["master_slave"]), _ul(bd["master_slave"]),
               len(bd["allowed"]), _ul(bd["allowed"]),
               len(bd["forbidden"]), _ul(bd["forbidden"])))

    # ② 骨架
    sk = ["<table><thead><tr><th>节</th><th>标题</th><th>起行</th><th>体量</th></tr></thead><tbody>"]
    for s in bp["sections"]:
        sk.append("<tr><td class='k'>§%s</td><td>%s</td><td class='k'>%d</td><td class='dim'>%d 行</td></tr>"
                  % (_esc(s["n"]), _esc(s["title"]), s["line"], s["body_lines"]))
    sk.append("</tbody></table>")
    sk.append("<div class='small dim' style='margin-top:6px'>§二 DAG 现数：%d 节点 / %d 条边 / %d 个 class 层　"
              "§三 模块状态 %d 行　§四 依赖链 %d 段　§七 完成判定 %d 条</div>"
              % (bp["dag"]["nodes"], bp["dag"]["edges"], bp["dag"]["class_groups"],
                 len(bp["modules"]), len(bp["chain"]), len(bp["done"])))
    if bp["baseline"]:
        sk.append("<div class='hr'></div><div class='small dim'>§八 基线验证（本节内表的现读条数）："
                  + "　".join("%s → %d 条" % (_esc(b["title"]), b["n"]) for b in bp["baseline"]) + "</div>")
    skeleton = "".join(sk)

    # ③ 树登记表
    tp = ["<div class='chips'>%d 棵 · %d 类：" % (tr["count"], tr["class_count"])
          + "".join("<span class='pill b'>%s %d</span>" % (_esc(g["class"]), g["n"]) for g in tr["groups"])
          + "</div>"]
    tp.append("<table><thead><tr><th>路径</th><th>分类</th><th>为什么它在册</th></tr></thead><tbody>")
    for g in tr["groups"]:
        for it in g["items"]:
            tp.append("<tr><td class='k'>%s</td><td class='dim'>%s</td><td class='small'>%s</td></tr>"
                      % (_esc(it["path"]), _esc(it["class"]), _md(it["why"])))
    tp.append("</tbody></table>")
    tp.append("<div class='small dim' style='margin-top:6px'>表更新 %s · forks %d 条 · 视图族 %d 条 · 保护册 %d 条 · 待主人裁 %d 条</div>"
              % (_esc(tr["updated"]), len(tr["forks"]), len(tr["view_families"]),
                 len(tr["protected"]), len(tr["pending_owner"])))
    trees_html = "".join(tp)

    # ④ 窗口登记表
    wp = ["<table><thead><tr><th>id</th><th>标题</th><th>来源页面</th><th>启动即见</th></tr></thead><tbody>"]
    for w in wn["items"]:
        wp.append("<tr><td class='k'>%s</td><td>%s</td><td class='k'>%s</td><td>%s</td></tr>"
                  % (_esc(w["id"]), _esc(w["title"]), _esc(w["file"]),
                     "<span class='pill g'>是</span>" if w["visible"] else "<span class='pill off'>否（宿主不打扰律）</span>"))
    wp.append("</tbody></table>")
    wp.append("<div class='small dim' style='margin-top:6px'>壳 %s · 登记 %d 扇 · 启动默认可见 %d 扇</div>"
              % (_esc(wn["shell"]), wn["count"], wn["visible_default"]))
    windows_html = "".join(wp)

    # ⑤ 落地顺序
    ph = []
    for p in bp["phases"]:
        ph.append("<div><span class='pill w'>%s · %s</span> <span class='off small'>%d 条</span>%s</div>"
                  % (_esc(p["id"]), _esc(p["title"]), len(p["items"]), _ul(p["items"])))
        ph.append("<div class='hr'></div>")
    phases_html = "".join(ph) or "<div class='off'>（源里没有 Phase）</div>"

    # ⑥ 风险登记
    rp = ["<table><thead><tr><th>ID</th><th>风险</th><th>连带影响</th><th>当前控制</th><th>下一步</th></tr></thead><tbody>"]
    for r in bp["risks"]:
        rp.append("<tr><td class='k'>%s</td><td>%s</td><td class='dim'>%s</td><td class='dim'>%s</td><td class='dim'>%s</td></tr>"
                  % (_esc(r.get("ID")), _md(r.get("风险")), _md(r.get("连带影响")),
                     _md(r.get("当前控制")), _md(r.get("下一步"))))
    rp.append("</tbody></table>")
    risks_html = "".join(rp)

    # ⑦ 故障登记
    fp = ["<table><thead><tr><th>F 编号</th><th>层</th><th>故障点数</th><th>其中 P0</th><th>挂点</th><th>本轮实测状态</th></tr></thead><tbody>"]
    for r in bp["faults"]:
        p0 = r.get("其中 P0", "")
        p0cell = ("<span class='pill f'>%s</span>" % _esc(p0)) if str(p0).strip() not in ("", "0") else "<span class='dim'>0</span>"
        fp.append("<tr><td class='k'>%s</td><td>%s</td><td class='mono'>%s</td><td>%s</td><td class='k'>%s</td><td class='small dim'>%s</td></tr>"
                  % (_esc(r.get("ID")), _esc(r.get("层")), _esc(r.get("故障点数")), p0cell,
                     _esc(r.get("挂点")), _md(r.get("本轮实测状态"))))
    fp.append("</tbody></table>")
    if bp["fault_q"]:
        fp.append("<div class='hr'></div><div class='small'><b>9.1 故障普查新发现（登记在案，未修）</b></div>")
        fp.append("<table><thead><tr><th>#</th><th>问题</th><th>证据</th><th>定级</th></tr></thead><tbody>")
        for r in bp["fault_q"]:
            fp.append("<tr><td class='k'>%s</td><td>%s</td><td class='dim small'>%s</td><td>%s</td></tr>"
                      % (_esc(r.get("#")), _md(r.get("问题")), _esc(r.get("证据")),
                         "<span class='pill f'>%s</span>" % _esc(r.get("定级"))))
        fp.append("</tbody></table>")
    faults_html = "".join(fp)

    # ⑧ 装机回执
    if rc.get("exists"):
        rce = ["<div class='stats'><div class='stat'><b>%s</b><i>verdict</i></div>"
               "<div class='stat'><b>%s</b><i>机检绿</i></div>"
               "<div class='stat'><b>%.1f</b><i>exe MB</i></div>"
               "<div class='stat'><b>%s</b><i>整包文件</i></div></div>"
               % (_esc(rc.get("verdict")), _esc("%s/%s" % (rc.get("checks_ok"), rc.get("checks_n"))),
                  (rc.get("exe_bytes") or 0) / 1048576.0, _esc(rc.get("files")))]
        rce.append("<table><thead><tr><th>机检</th><th>结果</th><th>读数</th></tr></thead><tbody>")
        for ck in rc["checks"]:
            rce.append("<tr><td>%s</td><td>%s</td><td class='dim small'>%s</td></tr>"
                       % (_esc(ck["check"]),
                          "<span class='pill g'>PASS</span>" if ck["ok"] else "<span class='pill f'>FAIL</span>",
                          _md(ck["detail"])))
        rce.append("</tbody></table>")
        rce.append("<div class='small dim' style='margin-top:6px'>回执时刻 %s · electron %s · 整包 %s 字节</div>"
                   % (_esc(rc.get("at")), _esc(rc.get("electronVersion")), _esc(rc.get("bytes"))))
        rce.append("<div class='small dim'>注：回执记的是 **2026-09-23 那次打包**（包内 8 扇）；"
                   "本页窗口表是**现行注册表**（%d 扇）—— 两者口径不同，不混算。</div>" % wn["count"])
        receipt_html = "".join(rce)
    else:
        receipt_html = "<div class='off'>未找到 %s —— 如实标缺，不编读数。</div>" % _esc(S["receipt"])

    return {"ring": ring, "skeleton": skeleton, "trees": trees_html, "windows": windows_html,
            "phases": phases_html, "risks": risks_html, "faults": faults_html, "receipt": receipt_html}


_PAGE = """<!doctype html>
<html data-page-id="blueprint" lang="zh-CN"><head><meta charset="utf-8">
<title>GBT小土豆V8 · 项目蓝图（一节一源 · 现算现落）</title>
<style>__CSS__</style></head><body>
<div class="gbt-topbar"><span class="mark"></span>
 <span class="brand">GBT<b>小土豆</b>V8 · 项目蓝图面板</span>
 <span class="off small">只读真源 · 不联网 · 不 fetch</span>
 <span class="topbar-meta" id="meta">
   生成时刻 <span class="mono" id="gen-at">__GEN__</span><br>
   重生成 <span class="mono">__REGEN__</span></span>
</div>
<div class="wrap">

 <div class="card">
  <h2>// 00 — 数据面总览（数字全部现算）</h2>
  __SRCNOTE0__
  <div class="stats" id="stats">__STATS__</div>
  <div class="small dim" id="data-note">数据件：<span class="mono">blueprint-data.js</span>（经典脚本内嵌 · 页面走 file:// 时 fetch 读不到本地 json）
   —— 本页每块在生成期已静态落地，脚本被禁也看得见。</div>
 </div>

 <div class="card">
  <h2>// 01 — 边界环（三类：主从 / 允许 / 禁止）</h2>
  __SRCNOTE1__
  __RING__
 </div>

 <div class="card">
  <h2>// 02 — 蓝图骨架（§一…§九 · 起行现数）</h2>
  __SRCNOTE2__
  __SKELETON__
 </div>

 <div class="card">
  <h2>// 03 — 树登记表（按 class 分组 · 逐棵 path / why）</h2>
  __SRCNOTE3__
  __TREES__
 </div>

 <div class="card">
  <h2>// 04 — 窗口登记表（现行注册表 · 一扇一行）</h2>
  __SRCNOTE4__
  __WINDOWS__
 </div>

 <div class="card">
  <h2>// 05 — 落地顺序 Phase 0–5（照 §六 逐条）</h2>
  __SRCNOTE5__
  __PHASES__
 </div>

 <div class="card">
  <h2>// 06 — 风险登记（§五 · R 编号逐条）</h2>
  __SRCNOTE6__
  __RISKS__
 </div>

 <div class="card">
  <h2>// 07 — 故障登记（§九 · F 编号逐条）</h2>
  __SRCNOTE7__
  __FAULTS__
 </div>

 <div class="card">
  <h2>// 08 — 装机回执读数（若存在）</h2>
  __SRCNOTE8__
  __RECEIPT__
 </div>

</div>
<footer>生成 __GEN__ · 重生成 <span>__REGEN__</span> · 判据 py -3.14 tools/codex-scripts/blueprint-feed.py --check · 开发者：自由的风 · GBT小土豆V8</footer>
<script src="blueprint-data.js"></script>
<script>
/* 数据件的**唯一消费者**：把总览数字与生成时刻对一遍。
   静态块已烘进 HTML（生成期落图），这里只做「数据面自检」——
   数据件读不到就当场标红，不静默（照 brain/index.html 的诚实边界）。 */
(function(){
  var D = window.GBT_BLUEPRINT;
  var stats = document.getElementById("stats");
  var note = document.getElementById("data-note");
  var genAt = document.getElementById("gen-at");
  if (!D) {
    if (note) { note.innerHTML = "<b style='color:#EF4444'>数据件 blueprint-data.js 没读到</b> —— "
      + "本页静态块仍在（生成期已落图），但总览数字这次不可用。";
      note.style.color = "#EF4444"; }
    return;
  }
  var c = D.counts || {};
  var items = [
    ["蓝图行数", c.blueprint_lines], ["节（§一…§九）", c.sections],
    ["边界三类", (c.boundary_master||0) + "/" + (c.boundary_allowed||0) + "/" + (c.boundary_forbidden||0)],
    ["树（分类）", c.trees + "（" + c.tree_classes + "）"],
    ["窗口（默认可见）", c.windows + "（" + c.windows_visible_default + "）"],
    ["Phase", c.phases], ["风险", c.risks], ["故障 F", c.faults]
  ];
  if (stats) {
    stats.innerHTML = items.map(function(kv){
      return "<div class='stat'><b>" + kv[1] + "</b><i>" + kv[0] + "</i></div>";
    }).join("");
  }
  if (genAt && D.generated_at) { genAt.textContent = D.generated_at; }
})();
</script><script src="../shell/tentacle-kit.js" defer></script></body></html>
"""


def render_page(model: dict) -> str:
    b = render_blocks(model)
    gen = model["generated_at"]
    srcs = model["sources"]
    page = (_PAGE
            .replace("__CSS__", _CSS)
            .replace("__STATS__", "<div class='stat'><b>…</b><i>读数据件</i></div>")
            .replace("__SRCNOTE0__", _srcnote(model, "%s · %s · %s · %s"
                                              % (srcs["blueprint"], srcs["trees"], srcs["windows"], srcs["receipt"])))
            .replace("__SRCNOTE1__", _srcnote(model, srcs["blueprint"] + " §一"))
            .replace("__SRCNOTE2__", _srcnote(model, srcs["blueprint"] + " 全部 `## ` 标题"))
            .replace("__SRCNOTE3__", _srcnote(model, srcs["trees"]))
            .replace("__SRCNOTE4__", _srcnote(model, srcs["windows"]))
            .replace("__SRCNOTE5__", _srcnote(model, srcs["blueprint"] + " §六"))
            .replace("__SRCNOTE6__", _srcnote(model, srcs["blueprint"] + " §五"))
            .replace("__SRCNOTE7__", _srcnote(model, srcs["blueprint"] + " §九"))
            .replace("__SRCNOTE8__", _srcnote(model, srcs["receipt"]))
            .replace("__RING__", b["ring"]).replace("__SKELETON__", b["skeleton"])
            .replace("__TREES__", b["trees"]).replace("__WINDOWS__", b["windows"])
            .replace("__PHASES__", b["phases"]).replace("__RISKS__", b["risks"])
            .replace("__FAULTS__", b["faults"]).replace("__RECEIPT__", b["receipt"])
            .replace("__GEN__", gen).replace("__REGEN__", model["regen_cmd"]))
    return page


def render_data_js(model: dict) -> str:
    return ("/* 自动生成，别手改。重建：\n"
            "   py -3.14 tools/codex-scripts/blueprint-feed.py\n"
            "   数据全部现读于本仓真源（PROJECT_BLUEPRINT.md / state/tree-registry.json /\n"
            "   holo_pet_w3/shell/windows.json / state/desktop-install-receipt.json）。\n"
            "   页面走 file://，fetch 读不到本地 json ⇒ 以**经典脚本**内嵌。 */\n"
            "globalThis.GBT_BLUEPRINT = "
            + json.dumps(model, ensure_ascii=False, separators=(",", ":")) + ";\n")


# ══════════════════════════════════════════════════════════════════════════════

def _read_json(p: Path):
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:                                                # noqa: BLE001
        return None


def load_sources() -> dict:
    bp_text = BLUEPRINT.read_text(encoding="utf-8", errors="replace") if BLUEPRINT.is_file() else ""
    return {"blueprint_text": bp_text, "trees": _read_json(TREES),
            "windows": _read_json(WINDOWS), "receipt": _read_json(RECEIPT)}


def cmd_gen() -> int:
    s = load_sources()
    model = build_model(s["blueprint_text"], s["trees"], s["windows"], s["receipt"])
    DATA_JS.parent.mkdir(parents=True, exist_ok=True)
    page_html = render_page(model)
    PAGE.write_text(clean_html(page_html), encoding="utf-8")
    DATA_JS.write_text(render_data_js(model), encoding="utf-8")
    c = model["counts"]
    print("蓝图面板：%s（%d 字节）" % (_rel(PAGE), PAGE.stat().st_size))
    print("数据件：%s（%d 字节）" % (_rel(DATA_JS), DATA_JS.stat().st_size))
    print("蓝图 %d 行 / 九节 %d · 边界 %d/%d/%d · DAG %d 节点 %d 边 · 树 %d 棵 %d 类 · "
          "窗口 %d 扇 · Phase %d 段 · 风险 %d · 故障 F %d"
          % (c["blueprint_lines"], c["sections"], c["boundary_master"], c["boundary_allowed"],
             c["boundary_forbidden"], c["dag_nodes"], c["dag_edges"], c["trees"], c["tree_classes"],
             c["windows"], c["phases"], c["risks"], c["faults"]))
    print("重生成：%s" % model["regen_cmd"])
    return 0


def cmd_check(as_json: bool = False) -> int:
    s = load_sources()
    model = build_model(s["blueprint_text"], s["trees"], s["windows"], s["receipt"])
    page_html = PAGE.read_text(encoding="utf-8", errors="replace") if PAGE.is_file() else None
    data_js = DATA_JS.read_text(encoding="utf-8", errors="replace") if DATA_JS.is_file() else None
    rows = validate(model, page_html, data_js)
    fails = [r for r in rows if not r[1]]
    if as_json:
        print(json.dumps({"rows": [{"id": a, "ok": b, "detail": c} for a, b, c in rows],
                          "pass": len(rows) - len(fails), "fail": len(fails)},
                         ensure_ascii=False, indent=1))
    else:
        print("=" * 90)
        print("项目蓝图面板 · 判据（正负对照）—— 真源现读，退出码 0 = 全过")
        print("=" * 90)
        for cid, ok, detail in rows:
            print("%s %-42s %s" % ("PASS" if ok else "FAIL", cid, detail))
        print("-" * 90)
        print("PASS %d · FAIL %d" % (len(rows) - len(fails), len(fails)))
    return 1 if fails else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                            # noqa: BLE001
            pass
    if not argv or argv[0] in ("gen", "--gen"):
        return cmd_gen()
    if argv[0] in ("--check", "verify", "check"):
        return cmd_check(as_json="--json" in argv)
    print("用法：blueprint-feed.py [gen | --check [--json]]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
