#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""tentacle-registry · 触手永久名册（主人令 2026-09-25）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 主人原话（本文件的存在理由）
> 「内存如果不够在规划好让**还没注册过的触手**补上，千万**别一根触手重复注册**来列好，
>   做一个**永久记录**必须**不能丢和混乱**了」

## 三条铁律（都做成了可机检的闸，不是嘴上说）
1. **一根触手一行，只注册一次** —— tid 唯一；重复注册**直接拒**（rc=2），不覆盖、不改写。
2. **容量不够只能拿「没注册过的」补** —— `plan` 只从**未注册件**里挑候选，且**明令禁止**
   用「把已注册的再列一遍」来凑数（那正是主人点名要防的）。
3. **永久记录不能丢、不能乱** —— `state/tentacle-registry.jsonl` **只追加**：
   - 序号必须 1..N **连续无缺口**（丢一行 = 缺口 ⇒ 报红）；
   - 每行挂**哈希链**（`prev` = 上一行的 sha）⇒ 抽改/删行/乱序都会断链 ⇒ 报红。

## 🔴 本文件同时修掉的一个真缺陷
面板 `deploy-panel.py::_invariants()` 第①条「每件恰好挂一根触手」用的判据是：
    `idx = [i for k in range(n) for i in range(len(PLUGIN_SLOTS)) if i % n == k]`
每个下标**按构造只被选中一次** ⇒ `dup` **恒为空** ⇒ 该条**无论数据多乱都永远 ✅**。
**这是假判据**（判据的成立与数据无关）。本名册用**身份去重**替代它。

用法：
  tentacle-registry.py scan        # 真读三处来源，查重复注册
  tentacle-registry.py verify      # 只验永久记录：连号 + 链 + 身份唯一
  tentacle-registry.py plan        # 容量规划：缺多少根，从**未注册件**补，禁重复
  tentacle-registry.py register --tid T04 --name xxx --what yyy --evidence zzz
  tentacle-registry.py seed        # 用**现读真实槽位**建初始永久记录（已注册则拒）
  tentacle-registry.py selftest
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # 🔴 parents[2]：本文件在 tools/codex-scripts/
S = ROOT / "tools" / "codex-scripts"
REG = ROOT / "state" / "tentacle-registry.jsonl"
ANCHOR = ROOT / "state" / "tentacle-registry.anchor.json"
ROSTER = ROOT / "state" / "tentacle-roster.json"
PANEL = S / "deploy-panel.py"
NERVE = S / "nerve.py"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── 永久记录：只追加 + 哈希链 ────────────────────────────────────────────────────
def _sha(row: dict) -> str:
    """行的指纹：对**除 sha 外的全部字段**做规范化 JSON 后取 sha256。"""
    body = {k: v for k, v in row.items() if k != "sha"}
    blob = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_registry():
    """→ (rows, 坏行)。坏行**不吞**：解析不了的**逐条报出来**（不静默跳过）。"""
    if not REG.exists():
        return [], []
    rows, bad = [], []
    for i, ln in enumerate(REG.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except Exception as e:
            bad.append("第 %d 行解析失败: %s" % (i, e))
    return rows, bad


def _write_anchor(rows) -> dict:
    """🔴 **锚点**：把「写到第几行、末行指纹是多少」另存一处。

    为什么必须要它（**我自己的测试把它逼出来的**）：只追加的记录里，**抽掉最后一行
    不会造成序号缺口** —— seq 仍然是 1..1 连号 ⇒ 纯连号判据**查不出尾巴被截**。
    两处一对照，截尾、整体清空、只改一处，都会立刻露出来。
    """
    a = {"行数": len(rows), "末行sha": rows[-1]["sha"] if rows else "GENESIS",
         "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "说明": "与 tentacle-registry.jsonl 互为对照；两处不一致 = 记录丢过或被改过"}
    ANCHOR.parent.mkdir(parents=True, exist_ok=True)
    ANCHOR.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return a


def append_row(tid: str, name: str, what: str, evidence: str, note: str = "") -> dict:
    rows, bad = load_registry()
    if bad:
        raise SystemExit("🔴 永久记录已有坏行，先修再写（不覆盖）：%s" % bad[:3])
    if any(r.get("tid") == tid for r in rows):
        raise SystemExit("🔴 **拒绝重复注册**：tid=%s 已在名册第 %s 行"
                         % (tid, next(r.get("seq") for r in rows if r.get("tid") == tid)))
    if any(r.get("name") == name for r in rows):
        hit = next(r for r in rows if r.get("name") == name)
        raise SystemExit("🔴 **拒绝重复注册**：name=%s 已挂在 %s（一根件不许注册两次）"
                         % (name, hit.get("tid")))
    row = {"seq": len(rows) + 1, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "tid": tid, "name": name, "what": what, "evidence": evidence,
           "prev": rows[-1]["sha"] if rows else "GENESIS", "note": note}
    row["sha"] = _sha(row)
    REG.parent.mkdir(parents=True, exist_ok=True)
    with REG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    _write_anchor(rows + [row])          # 每写一行就更新锚点（两处互为对照）
    return row


def verify_chain():
    """① 连号 1..N 无缺口 ② 哈希链不断 ③ 身份唯一。"""
    rows, bad = load_registry()
    gaps = [i for i, r in enumerate(rows, 1) if r.get("seq") != i]
    broken, prev = [], "GENESIS"
    for r in rows:
        if r.get("prev") != prev:
            broken.append("seq=%s prev=%s 应为 %s" % (r.get("seq"), r.get("prev"), prev[:8]))
        if _sha(r) != r.get("sha"):
            broken.append("seq=%s 指纹不符（行被抽改过）" % r.get("seq"))
        prev = r.get("sha")
    tids = [r.get("tid") for r in rows]
    names = [r.get("name") for r in rows]
    dup_t = sorted({t for t in tids if tids.count(t) > 1})
    dup_n = sorted({n for n in names if names.count(n) > 1})
    # 锚点对照：**尾巴被截 / 被整体清空 / 只改一处** 都在这儿露出来
    anchor_bad = []
    if not ANCHOR.exists():
        anchor_bad.append("**锚点文件不在** ⇒ 无法证明尾巴没被截（未锚定 ≠ 完好）")
    else:
        try:
            an = json.loads(ANCHOR.read_text(encoding="utf-8"))
        except Exception as e:
            an = {}
            anchor_bad.append("锚点解析失败: %s" % e)
        if an:
            if an.get("行数") != len(rows):
                anchor_bad.append("行数不符：锚点 %s ≠ 实录 %d（**丢过行**）"
                                  % (an.get("行数"), len(rows)))
            if an.get("末行sha") != (rows[-1]["sha"] if rows else "GENESIS"):
                anchor_bad.append("末行指纹不符（**尾巴被截或末行被改**）")
    return {"行数": len(rows), "坏行": bad, "序号缺口": gaps, "断链/被改": broken,
            "重复 tid": dup_t, "重复 name": dup_n, "锚点": anchor_bad or "✅ 与实录一致",
            "只追加": True,
            "全过": not (bad or gaps or broken or dup_t or dup_n or anchor_bad) and bool(rows)}


# ── 三处来源的真读（AST，不执行模块 ⇒ 无副作用）──────────────────────────────────
def _find_assign(path: Path, var: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == var:
                    return node.value
    return None


def read_slots():
    """面板 PLUGIN_SLOTS → [(编号, 名称, 做什么, 落点, 状态)]（纯字面量，可 literal_eval）。"""
    node = _find_assign(PANEL, "PLUGIN_SLOTS")
    if node is None:
        return []
    return [(r[0], r[1], r[2], r[3], r[6]) for r in ast.literal_eval(node)]


def read_probes():
    """神经 PROBES → {P##: 强度/说明}（值是表达式 ⇒ 只取常量，不执行）。"""
    node = _find_assign(NERVE, "PROBES")
    out = {}
    if not isinstance(node, ast.Dict):
        return out
    for k, v in zip(node.keys, node.values):
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
            continue
        desc = ""
        if isinstance(v, ast.Tuple) and len(v.elts) >= 3:
            e = v.elts[2]
            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                desc = e.value
        out[k.value] = desc
    return out


def _superseded(names):
    """找出被**更高版本**取代的件：`build_v09.py` 之上有 `build_v10.py` ⇒ v09 是历史件。

    🔴 不把历史件当候选池 —— 一拿它当池子，`plan` 就会提议 `build_v3.py` 上触手（**坏判据**）。
    """
    import re
    fam = {}
    for n in names:
        m = re.match(r"^(?P<pre>.+?)_v(?P<n>\d+)(?P<suf>(?:_[a-z0-9]+)?)\.py$", n)
        if m:
            fam.setdefault((m.group("pre"), m.group("suf")), []).append((int(m.group("n")), n))
    dead = set()
    for vals in fam.values():
        if len(vals) > 1:
            top = max(vals)[1]
            dead |= {n for _, n in vals if n != top}
    return dead


def built_but_unregistered():
    """**已建但没注册进触手名册的件** —— 这就是「还没注册过的」那批。

    分三级（**分级只影响排序，不隐藏任何一条**）：
      生产级 = 自带 `selftest` 子命令（有正负控）；一次性 = `probe_*` 探路件；
      历史件 = 被更高版本取代（不提议上触手）。
    """
    rows, _ = load_registry()
    reg_names = {r.get("name") for r in rows}
    slot_names = {s[1] for s in read_slots()}
    pool = []
    for d in (S, ROOT / "tools"):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix not in (".py", ".md") or not p.is_file() or p.name.startswith("_"):
                continue
            if p.name in reg_names or p.name in slot_names:
                continue
            pool.append((p.name, str(p.relative_to(ROOT)), p))
    dead = _superseded([n for n, _, _ in pool])
    out = []
    for n, rel, p in pool:
        if n in dead:
            cls = "历史件"
        elif n.startswith("probe_") or n.startswith("probe-"):
            cls = "一次性"
        else:
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                txt = ""
            cls = "生产级" if '"selftest"' in txt or "'selftest'" in txt else "普通"
        out.append({"件": n, "出处": rel, "级": cls})
    return out


def declared_roots():
    if not ROSTER.exists():
        return None, "state/tentacle-roster.json 不在"
    try:
        d = json.loads(ROSTER.read_text(encoding="utf-8"))
    except Exception as e:
        return None, "roster 解析失败: %s" % e
    return d.get("声明根数"), "roster 的『声明根数』（唯一真源，只有主人能改）"


# ── 命令 ────────────────────────────────────────────────────────────────────────
def cmd_scan(a) -> int:
    slots, probes = read_slots(), read_probes()
    rows, bad = load_registry()
    n_t, src = declared_roots()

    name_counts = {}
    for s in slots:
        name_counts[s[1]] = name_counts.get(s[1], 0) + 1
    dup_slot = {k: v for k, v in name_counts.items() if v > 1}
    tid_counts = {}
    for r in rows:
        tid_counts[r.get("tid")] = tid_counts.get(r.get("tid"), 0) + 1
    dup_tid = {k: v for k, v in tid_counts.items() if v > 1}

    unreg = built_but_unregistered()
    cls = {}
    for u in unreg:
        cls[u["级"]] = cls.get(u["级"], 0) + 1
    prod = [u["件"] for u in unreg if u["级"] == "生产级"]
    print(json.dumps({
        "① 面板槽位": {"条数": len(slots), "身份唯一": not dup_slot,
                   "重复注册的件": dup_slot or "无"},
        "② 神经探针": {"条数": len(probes), "样例": list(probes)[:5]},
        "③ 永久名册": {"行数": len(rows), "坏行": bad,
                   "重复 tid": dup_tid or "无",
                   "链/连号": verify_chain()["全过"]},
        "④ 声明根数": {"值": n_t, "出处": src},
        "⑤ 已建但没注册过的件（容量不够时从这里补）": {
            "总条数": len(unreg), "分级": cls,
            "生产级（自带 selftest）": {"条数": len(prod), "清单": prod[:40]}},
    }, ensure_ascii=False, indent=1))
    hard = bool(dup_slot or dup_tid or bad)
    print("判决：%s" % ("🔴 有重复注册 ⇒ 不许列进面板" if hard else "✅ 三处来源**没有重复注册**"))
    return 2 if hard else 0


def cmd_verify(a) -> int:
    v = verify_chain()
    print(json.dumps(v, ensure_ascii=False, indent=1))
    if not v["全过"]:
        why = []
        if v["坏行"]:
            why.append("坏行")
        if v["序号缺口"]:
            why.append("序号缺口（**丢过行**）")
        if v["断链/被改"]:
            why.append("断链/被抽改")
        if v["重复 tid"]:
            why.append("**一根触手注册了两次**")
        if v["重复 name"]:
            why.append("**同一件注册了两次**")
        if isinstance(v["锚点"], list):
            why.append("锚点对不上/未锚定")
        print("🔴 永久记录不干净：%s" % "、".join(why))
        return 2
    print("✅ 永久记录干净：%d 行连号 · 链完好 · 锚点一致 · 身份唯一（没丢、没乱、没重复）"
          % v["行数"])
    return 0


def probe_selftest(rel: str, timeout: int = 25) -> dict:
    """**真跑**候选的 `selftest`，读它的 rc 与通过条数。

    🔴 为什么必须真跑：上一版 `plan` 的候选排序是**字典序**（`genrouter.py` 排在
    `tentacle-registry.py` 前面，只是因为字母序）—— 那是**没证据的排序**。
    本仓规矩：`selftest` 是自带正负控的只读自检（checkup/nerve 都在用它），跑它属常规操作。
    跑不起来 / 超时 / rc≠0 一律**如实降级**，不假装它能上。
    """
    import re as _re
    import subprocess
    import time as _t
    t0 = _t.time()
    try:
        r = subprocess.run([sys.executable, str(ROOT / rel), "selftest"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, cwd=str(ROOT))
        rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return {"rc": -9, "秒": round(_t.time() - t0, 2), "条数": 0,
                "备注": "超时 >%ds（**不算过**）" % timeout}
    except Exception as e:
        return {"rc": -1, "秒": round(_t.time() - t0, 2), "条数": 0,
                "备注": "跑不起来：%s" % str(e)[:60]}
    m = _re.search(r'"通过"\s*:\s*(\d+)', out)
    n = int(m.group(1)) if m else (out.count("✓"))
    return {"rc": rc, "秒": round(_t.time() - t0, 2), "条数": n,
            "备注": ("rc=0 · %d 条" % n) if rc == 0 else "rc=%d（**不算过**）" % rc}


def ranked_pool():
    """生产级候选**按实测证据排序**：真跑出自检读数的排前，再按条数多的排前，最后才看名字。

    🔴 「rc=0 就能用」是**坏判据**：没有 CLI 的模块 `python x.py selftest` **也会 rc=0**
    ⇒ 必须同时要求**通过条数 ≥ 1**（真报过读数）。自检里 ⑨ 就是咬这条的负控。
    """
    pool = [u for u in built_but_unregistered() if u["级"] == "生产级"]
    out = []
    for u in pool:
        pr = probe_selftest(u["出处"])
        out.append({"件": u["件"], "出处": u["出处"], "自检rc": pr["rc"],
                    "自检条数": pr["条数"], "秒": pr["秒"], "读数": pr["备注"],
                    "可用": pr["rc"] == 0 and pr["条数"] >= 1})
    out.sort(key=lambda r: (0 if r["可用"] else 1, -r["自检条数"], r["件"]))
    return out


def cmd_pool(a) -> int:
    rk = ranked_pool()
    print(json.dumps({"生产级候选（按实测自检排序）": rk,
                      "排序规则": "rc=0 优先 → 通过条数多优先 → 名字；"
                              "**跑不起来/超时/rc≠0 一律不算过**"},
                     ensure_ascii=False, indent=1))
    good = [r for r in rk if r["可用"]]
    trivial = [r["件"] for r in rk if r["自检rc"] == 0 and r["自检条数"] < 1]
    print("真跑出读数的 %d / %d ｜ **rc=0 但一条读数都没报（假过）**：%s"
          % (len(good), len(rk), trivial or "无"))
    return 0


def cmd_plan(a) -> int:
    rows, _ = load_registry()
    n_t, src = declared_roots()
    have = len(rows)
    RULE1 = 5                                     # 主人 2026-09-23 令：最少五根触手同时执行
    print("声明根数 %s（%s）｜ 已注册 %d 根｜ 规矩一下限 %d 根" % (n_t, src, have, RULE1))
    if not n_t:
        print("🔴 根数未声明 ⇒ **不排班**（fail-closed）")
        return 2
    need = max(int(n_t), RULE1)
    if have >= need:
        print("✅ 已注册 %d ≥ 需要 %d ⇒ **不缺**，无需扩容" % (have, need))
        return 0
    gap = need - have
    print("缺 %d 根（按更强的那个口径：声明 %s 与规矩一 %d 取大）。"
          "候选**按实测自检排序**（不是字典序），且**只能用没注册过的**（主人令）：" % (gap, n_t, RULE1))
    ranked = [r for r in ranked_pool() if r["自检rc"] == 0 and r["自检条数"] >= 1]
    if not ranked:
        print("🔴 未注册池里**没有一个候选真跑出过自检读数** ⇒ 不能靠『把已注册的再列一遍』凑数"
              " ⇒ 如实报缺")
        return 3
    proposed, used = [], set()
    for i in range(min(gap, len(ranked))):
        nm = ranked[i]["件"]
        if nm in used:
            continue
        used.add(nm)
        proposed.append({"拟用 tid": "T%02d" % (have + i + 1), "件": nm, "出处": ranked[i]["出处"],
                         "实测自检": ranked[i]["读数"]})
    print(json.dumps({
        "缺口": gap,
        "提议（每根触手一件，**互不重复**；件都跑过自检 rc=0）": proposed,
        "提议里有重复吗": len(used) != len(proposed),
        "自检真过的候选还剩": len(ranked) - len(used),
    }, ensure_ascii=False, indent=1))
    if len(used) != len(proposed):
        print("🔴 提议里出现重复 ⇒ 不许采用")
        return 4
    print("🔴 明令禁止：用已注册的件重复列来填这 %d 个缺口 —— 本次规划**一件只用一次**" % gap)
    return 0


def cmd_register(a) -> int:
    row = append_row(a.tid, a.name, a.what, a.evidence, a.note)
    print(json.dumps(row, ensure_ascii=False, indent=1))
    print("✅ 已追加第 %d 行（只追加，不改旧行）" % row["seq"])
    return 0


def cmd_seed(a) -> int:
    """用**现读真实槽位**建初始永久记录：每根触手一行，行内带它载的件。"""
    slots = read_slots()
    n_t, _ = declared_roots()
    if not slots:
        print("🔴 没读到面板槽位 ⇒ 不建册（fail-closed）")
        return 2
    if not n_t:
        print("🔴 根数未声明 ⇒ 不建册（fail-closed）")
        return 2
    rows, _ = load_registry()
    if rows:
        print("🔴 名册已有 %d 行 ⇒ **不重建**（永久记录不许被覆盖）。如需补，用 register。" % len(rows))
        return 2
    # 按面板同一套轮转把件分到 n_t 根触手上（这里只登记，不改面板排班）
    buckets = [[] for _ in range(n_t)]
    for i, s in enumerate(slots):
        buckets[i % n_t].append(s[1])
    made = []
    for k, b in enumerate(buckets, 1):
        made.append(append_row(
            "T%02d" % k, "触手T%02d" % k,
            "载 %d 件：%s" % (len(b), "、".join(b)),
            "由 deploy-panel.py PLUGIN_SLOTS 现读 %d 条槽位按轮转分派" % len(slots),
            "seed：初始永久记录"))
    print(json.dumps({"建册行数": len(made), "触手": [m["tid"] for m in made],
                      "共载件数": sum(len(b) for b in buckets)},
                     ensure_ascii=False, indent=1))
    return cmd_verify(a)


def cmd_selftest(a) -> int:
    """正负控：**必须能用假数据把每条闸打红**，否则判据是假的。"""
    import tempfile
    global REG, ANCHOR
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    old, olda = REG, ANCHOR
    with tempfile.TemporaryDirectory() as td:
        REG = Path(td) / "r.jsonl"
        ANCHOR = Path(td) / "r.anchor.json"
        # ① 空册 ⇒ 不算过
        ck("空册不算全过（fail-closed）", verify_chain()["全过"] is False, "0 行")
        # ② 正常追加三行 ⇒ 连号 + 链好 + 锚点一致
        append_row("T01", "触手T01", "载 a", "ev1")
        append_row("T02", "触手T02", "载 b", "ev2")
        append_row("T03", "触手T03", "载 c", "ev3")
        v = verify_chain()
        ck("三行连号 + 链完好 + 锚点一致", v["全过"] and v["行数"] == 3,
           "行数=%d 锚点=%s" % (v["行数"], v["锚点"]))
        # ③ 重复 tid ⇒ 拒
        try:
            append_row("T01", "新名", "x", "y")
            ck("重复 tid 必须被拒", False, "居然写进去了")
        except SystemExit as e:
            ck("重复 tid 必须被拒", "拒绝重复注册" in str(e), str(e)[:40])
        # ④ 重复 name ⇒ 拒
        try:
            append_row("T09", "触手T02", "x", "y")
            ck("同一件重复注册必须被拒", False, "居然写进去了")
        except SystemExit as e:
            ck("同一件重复注册必须被拒", "拒绝重复注册" in str(e), str(e)[:40])
        full = REG.read_text(encoding="utf-8").splitlines()
        # ⑤a 抽掉**中间**一行 ⇒ 序号缺口报红
        REG.write_text(full[0] + "\n" + full[2] + "\n", encoding="utf-8")
        va = verify_chain()
        ck("抽掉中间一行 ⇒ 序号缺口报红", bool(va["序号缺口"]), "缺口=%s" % va["序号缺口"])
        # ⑤b 🔴 抽掉**最后**一行 ⇒ 纯连号查不出，**必须靠锚点**查出来
        REG.write_text(full[0] + "\n" + full[1] + "\n", encoding="utf-8")
        vb = verify_chain()
        ck("**截尾**（连号仍是 1..2）⇒ 锚点行数不符报红",
           not vb["序号缺口"] and vb["全过"] is False and "行数不符" in "".join(vb["锚点"]),
           "缺口=%s ｜ 锚点=%s" % (vb["序号缺口"], vb["锚点"]))
        # ⑥ 抽改一行 ⇒ 指纹不符报红
        REG.write_text(full[0] + "\n" + full[1] + "\n" + full[2] + "\n", encoding="utf-8")
        d = json.loads(full[1])
        d["what"] = "被偷改了"
        REG.write_text(full[0] + "\n" + json.dumps(d, ensure_ascii=False, sort_keys=True)
                       + "\n" + full[2] + "\n", encoding="utf-8")
        vc = verify_chain()
        ck("抽改一行 ⇒ 指纹不符报红", bool(vc["断链/被改"]), (vc["断链/被改"] or ["没报"])[0][:46])
        # ⑦ 坏行不许静默吞
        with REG.open("a", encoding="utf-8") as f:
            f.write("{这不是 json\n")
        ck("坏行不许静默吞掉", bool(load_registry()[1]), (load_registry()[1] or ["吞了"])[0][:40])
        # ⑧ 锚点缺失 ⇒ 不许当"完好"
        ANCHOR.unlink()
        ck("锚点不在 ⇒ **未锚定不算完好**", verify_chain()["全过"] is False,
           str(verify_chain()["锚点"])[:46])
    REG, ANCHOR = old, olda
    # ⑨ 🔴 「rc=0 就能用」是**坏判据**：没有 CLI 的模块 `python x.py selftest` 也会 rc=0（假过）
    pr = probe_selftest("tools/iching_king_wen.py")
    ck("**rc=0 但一条读数都没报 ⇒ 不算可用**（假过负控）",
       pr["rc"] == 0 and pr["条数"] == 0,
       "rc=%s 条数=%s（该文件是数据模块、没有 selftest CLI）" % (pr["rc"], pr["条数"]))
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="触手永久名册（一根一行 · 只追加 · 哈希链）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(func=cmd_scan)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    sub.add_parser("pool").set_defaults(func=cmd_pool)
    r = sub.add_parser("register")
    r.add_argument("--tid", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--what", required=True)
    r.add_argument("--evidence", required=True)
    r.add_argument("--note", default="")
    r.set_defaults(func=cmd_register)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
