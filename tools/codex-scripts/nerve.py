#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""神经总线 · 全身感知（主人 2026-09-24 令）

主人原话：

> 「必须在总控上面把**所有能力功能模块一切都使用触手连接**，确保全量都在你的掌控之内，
>   就像**人类的身体**一样，哪里痛、受伤了、或者想看哪里，都能**第一时间知道**以作应变，
>   不会影响工作效率。」

## 这个工具干什么
把"掌控"变成**能读的东西**，而不是一句口号：

1. **神经末梢**：`deploy-panel` 排班表里**每一个**能力/插件，这里都有一条**探针**（真的会去跑）。
2. **触手连接**：每条末梢都挂在某一根触手上（排班表决定），并指向它**独占的隔离位**。
3. **痛觉**：探针 rc≠0 / 超时 / 缺件 ⇒ **⛔ 痛**，带 rc、输出尾、以及**应变**（备用位来自 failover）。
4. **想看哪里**：`probe <编号>` 现读单个；`map` 看全身；`pain` 只看痛的地方。
5. **诚实分级**：探针分**强/中/弱**，并且**没有探针的能力如实写「❓未知」，绝不当成健康**。

## 🔴 三条不许破的线
- **探针不许写盘、不许改云**：全部是只读或自带替身云的自检。**没读数 = 未知，不是健康。**
- **超时也是痛**：探针卡住 ⇒ 记 ⛔（不是 ✅）。"不问就不知道"在这里是缺陷，不是省事。
- **强弱必须标**：弱探针（只看文件在不在）**不能**拿来证明"功能是好的"。这一条写进输出里。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
DP_PATH = ROOT / "tools" / "codex-scripts" / "deploy-panel.py"
SCRIPTS = ROOT / "tools" / "codex-scripts"
PY = [sys.executable]
TIMEOUT_S = 60
_DP = None


def _dp():
    global _DP
    if _DP is None:
        spec = importlib.util.spec_from_file_location("_dp_mod6", DP_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _DP = m
    return _DP


def _s(name: str) -> str:
    return str(SCRIPTS / name)


# ── 神经末梢表：每条 = 一个能力的**真探针** ────────────────────────────────────────
# 强度：强 = 真功能自检 / 中 = 真只读读数 / 弱 = 只看在场（**弱不许当健康证据**）
# 第 4 项 = 探针的 cwd（有些工具必须在**自己的工程目录**里跑，例如 remotion）。
PROBES = {
    "P01": (PY + [_s("deploy-panel.py"), "selftest"], "强", "顺序门 11 行自检", None),
    "P02": (PY + [_s("render-agent.py"), "modules"], "中", "读模块图（只读）", None),
    "P03": ([shutil.which("npx") or "npx", "--yes", "wrangler", "--version"], "中", "wrangler 版本", None),
    # 🔴 F35：第一版写成 `remotion --version` —— **remotion 没有这个 flag**，rc=1 ⇒ 报了**假痛**。
    #    正确姿势是 `remotion versions`，且必须在**工程目录**里跑（--no-install 需要本地 node_modules）。
    "P04": ([shutil.which("npx") or "npx", "--no-install", "remotion", "versions"], "中",
            "remotion versions", str(ROOT / ".scratch" / "remotion-smoke")),
    "P05": (PY + ["-c", "import pathlib,sys;"
                  "p=pathlib.Path(r'%s');"
                  "sys.exit(0 if (p/'renders').is_dir() else 1)" % str(ROOT / ".scratch" / "hyperframes-smoke")],
            "弱", "只看 HyperFrames 工程在不在（**弱：不证明渲染可用**）", None),
    "P06": ([shutil.which("ffprobe") or "ffprobe", "-version"], "中", "ffprobe 版本", None),
    "P07": (PY + ["-c", "import pathlib,sys;"
                  "b=pathlib.Path.home()/'.cache'/'puppeteer';"
                  "sys.exit(0 if b.is_dir() else 1)"], "弱", "只看 puppeteer 缓存目录", None),
    "P08": (["node", "--version"], "中", "node 版本", None),
    "P09": (PY + [_s("asset-pool.py"), "ls"], "强", "真读云素材索引", None),
    "P10": (PY + [_s("cloud-vault.py"), "stat"], "强", "真读仓登记", None),
    "P11": (PY + [_s("vault-spill.py"), "--help"], "弱", "只看能起（**弱**）", None),
    "P12": (PY + [_s("r2-move.py"), "--help"], "弱", "只看能起（**弱**）", None),
    "P13": (PY + [_s("quick_scan.py"), "--help"], "弱", "只看能起（**弱**；全扫太慢）", None),
    "P14": (PY + [_s("quickscan_evolve.py"), "--selftest"], "强", "判据 15 行自检", None),
    "P15": (PY + [_s("five-dim.py"), "cap", "health"], "中", "走唯一门读健康位", None),
    # 🔴 F35 同型：第一版把路径写成 tools/codex-scripts/framework_gate.py ⇒ **文件不在那儿**（真身在
    #    gbt_allinone/tools/）⇒ 又报了一个**假痛**。下面这条"探针体检"就是为它加的。
    "P16": (PY + [str(ROOT / "gbt_allinone" / "tools" / "framework_gate.py"), "verify"], "强",
            "真读框架门红绿", None),
    "P17": (PY + [_s("frame-cache.py"), "ls"], "强", "真读云帧索引", None),
    "P18": (PY + [_s("orchestrator.py"), "selftest"], "强", "闸正负控 6 行", None),
    "P19": (PY + [_s("assemble.py"), "selftest"], "强", "真 ffmpeg 编码自检 6 行", None),
    "P20": (PY + [_s("failover.py"), "guard"], "强", "真读物理内存", None),
    "P21": (PY + [_s("nerve.py"), "selftest"], "强", "痛觉七态自检", None),
    "P22": (PY + [_s("publish.py"), "check"], "中", "真读授权现状（发布门卫）", None),
    "P23": (PY + [_s("generator.py"), "providers"], "中", "真读生成端凭据（双源）", None),
    "P24": (PY + [_s("lint_cjk_quotes.py"), "tools/codex-scripts"], "强",
            "中文串 ASCII 引号闸（0 命中 rc=0）", None),
    # 🔴 探针**只验架子**（`--self`），不跑完整 checkup —— 否则
    #    nerve selftest → checkup → nerve selftest → … **无限递归**。
    # 🔴 措辞里**不许出现条数**：这里曾写「五步齐」，而体检长到 22 步后
    #    `checkup --self` 因写死的 `== 5` 恒 rc=4 ⇒ **P25 长期假痛**，无人看见。
    "P25": (PY + [_s("checkup.py"), "--self"], "中",
            "体检脚本架子在（**步骤齐 · 引用的脚本都在** · 不重跑体检）", None),
}

CACHE = ROOT / "state" / "nerve-last.json"
HISTORY = ROOT / "state" / "nerve-history.jsonl"


def classify(prev: dict, cur: dict) -> list[dict]:
    """**纯函数**：比对两轮读数，给变化分类。自检不跑探针也能验它（这是关键——
    "变化分类"要是错了，巡检就会漏报新痛或虚报痊愈）。"""
    rows = []
    for pid in sorted(set(prev) | set(cur)):
        a = (prev.get(pid) or {}).get("感觉")
        b = (cur.get(pid) or {}).get("感觉")
        if a is None:
            # 🔴 F36：新增末梢**如果是痛的，那就是新痛**，不许归成中性的"新增"。
            #    第一版把它归"新增末梢"，而判决只看"新痛" ⇒ 会打出【✅ 无变化，无新痛】
            #    —— **假的全清**。假全清比漏报更坏：它让人放心地不去看。
            chg = ("🔴 **新痛**（新增末梢）" if b.startswith("⛔")
                   else "❓ 新增未知" if b.startswith("❓") else "＋ 新增末梢")
        elif b is None:
            chg = "－ 末梢消失"
        elif a.startswith("✅") and b.startswith("⛔"):
            chg = "🔴 **新痛**"
        elif a.startswith("⛔") and b.startswith("✅"):
            chg = "🟢 新愈"
        elif a.startswith("⛔") and b.startswith("⛔"):
            chg = "🟡 未愈"
        elif a.startswith("❓") or b.startswith("❓"):
            chg = "❓ 未知"
        elif a == b:
            chg = "— 稳定"
        else:
            chg = "⚠️ 变化"
        rows.append({"编号": pid, "上轮": a, "本轮": b, "变化": chg})
    return rows


def coverage(all_ids: list, measured: list) -> dict:
    """**纯函数**：算覆盖率。为 F38 而抽出来 —— 部分覆盖必须能被机检，
    否则面板会把"只测了 13/23"念成"没有痛"。"""
    untested = [i for i in all_ids if i not in set(measured)]
    return {"全机末梢": len(all_ids), "已测": len(all_ids) - len(untested), "未测": len(untested),
            "未测名单": untested,
            "警告": "**已测 %d / 全机 %d** —— 未测的按『未知』算，未测里可能有真痛"
            "（例如框架门）。**不许把部分覆盖念成全清。**"
            % (len(all_ids) - len(untested), len(all_ids))}


def _plan(deep: bool) -> list[str]:
    """巡检深度。🔴 **默认只跑中/弱探针** —— 强探针里好几个是整套自检（各要十几秒），
    每轮都跑会把"巡检"变成负担，而主人明确要求**不影响工作效率**。
    强探针交给 `--deep`（我来值守时跑），或 `probe <编号>` 单点看。"""
    pids = [p[0] for p in _dp().PLUGIN_SLOTS]
    if deep:
        return pids
    return [p for p in pids if PROBES.get(p, ("", "—"))[1] != "强"]


def cmd_patrol(a) -> int:
    """**巡检**：不问也自己看一遍，只报**变化**（新痛/新愈/未愈），并落历史账。
    这才是"第一时间知道"：不是等人来问，是每轮自己比上一轮。"""
    prev = {}
    if CACHE.is_file():
        try:
            d = json.loads(CACHE.read_text(encoding="utf-8"))
            for e in d.get("明细", []):
                prev[e["编号"]] = {"感觉": e["感觉"]}
        except Exception:
            prev = {}
    pids = _plan(a.deep)
    rows = _rows(pids, a.timeout)
    cur = {r["编号"]: {"感觉": r["感觉"]} for r in rows}
    changes = classify(prev, cur)
    new_pain = [c for c in changes if "新痛" in c["变化"]]
    healed = [c for c in changes if "新愈" in c["变化"]]
    chronic = [c for c in changes if "未愈" in c["变化"]]
    unknown = [c for c in changes if "未知" in c["变化"]]
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "深度": "deep" if a.deep else "quick",
                            "探针数": len(rows), "合计": _summary(rows),
                            "新痛": [c["编号"] for c in new_pain],
                            "新愈": [c["编号"] for c in healed],
                            "未愈": [c["编号"] for c in chronic]}, ensure_ascii=False) + "\n")
    # 覆盖缓存：但**只覆盖本轮跑过的**，没跑的保留上轮（否则会被误判成"末梢消失"）
    if CACHE.is_file():
        try:
            old = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    else:
        old = {}
    # 🔴 F38：缓存必须**同时记住"有多少末梢"和"这轮测了多少"**。
    #    第一版只存测过的 ⇒ 面板打「末梢 13 · 痛 0」，而全机有 **23** 个末梢，
    #    没测的那 10 个里**正好包括真红的 framework_gate** ⇒ 又是一次**假的全清**。
    #    部分覆盖**绝不能念成"没有痛"**。
    all_ids = [p[0] for p in _dp().PLUGIN_SLOTS]
    merged = {e["编号"]: e for e in old.get("明细", [])}
    for r in rows:
        merged[r["编号"]] = {"编号": r["编号"], "名称": r["名称"], "感觉": r["感觉"],
                           "强度": r["强度"], "为什么": r.get("为什么") or r.get("读数尾")}
    [i for i in all_ids if i not in merged]
    CACHE.write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "触手根数": _dp()._tentacles()[0],
        "合计": _summary(list(merged.values())),
        "覆盖": coverage(all_ids, list(merged)),
        "痛或未知": [e for e in merged.values() if not str(e.get("感觉")).startswith("✅")],
        "明细": list(merged.values()),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    out = {
        "巡检": {"深度": "deep（含强探针）" if a.deep else "quick（只跑中/弱探针，省时）",
               "本轮跑": len(rows), "未跑（强探针留给 --deep）": len(_dp().PLUGIN_SLOTS) - len(rows)},
        "变化": [c for c in changes if a.all or c["变化"] not in ("— 稳定",)],
        "判决": ("🔴 **出现新痛**：%s" % [c["编号"] for c in new_pain]) if new_pain else
        ("❓ 有未知（**不等于健康**）：%s" % [c["编号"] for c in unknown]) if unknown else
        ("🟢 有新愈：%s" % [c["编号"] for c in healed]) if healed else
        ("🟡 未愈仍在：%s" % [c["编号"] for c in chronic]) if chronic else "✅ 无变化，无新痛",
        "账本": str(HISTORY.relative_to(ROOT)),
        "口径": "只报**变化**；全量看 map，痛处看 pain。未知 ≠ 健康。",
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if not new_pain else 5


def probe_sanity() -> list[dict]:
    """**探针体检**：探针自己引用的脚本/程序必须在盘上。
    为 F35 而加 —— 路径写错时，探针会**永远失败**，把"我的手指坏了"报成"身体痛"。
    假痛和假绿一样坏：一个让人白忙，一个让人漏诊。"""
    bad = []
    for pid, (cmd, strength, what, cwd) in PROBES.items():
        for tok in cmd:
            if not isinstance(tok, str) or not tok.endswith(".py"):
                continue
            if not pathlib.Path(tok).is_file():
                bad.append({"编号": pid, "探针": what, "缺的脚本": tok})
        if cwd and not pathlib.Path(cwd).is_dir():
            bad.append({"编号": pid, "探针": what, "缺的目录": cwd})
    return bad


def probe_one(pid: str, timeout: int = TIMEOUT_S) -> dict:
    """跑一条探针，给**感觉**。fail-closed：跑不起来/超时都算痛或未知，绝不算健康。"""
    ent = PROBES.get(pid)
    if not ent:
        return {"编号": pid, "感觉": "❓ 未知", "为什么": "**这条能力没有探针**（如实报，不当健康）",
                "强度": "—"}
    cmd, strength, what, cwd = ent
    exe = cmd[0]
    if not exe or (shutil.which(exe) is None and not pathlib.Path(exe).exists()):
        return {"编号": pid, "感觉": "⛔ 痛", "为什么": "可执行文件不在：%s" % exe,
                "强度": strength, "探针": what}
    if cwd and not pathlib.Path(cwd).is_dir():
        return {"编号": pid, "感觉": "⛔ 痛", "为什么": "探针要的工程目录不在：%s" % cwd,
                "强度": strength, "探针": what}
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, cwd=str(cwd or ROOT))
    except subprocess.TimeoutExpired:
        return {"编号": pid, "感觉": "⛔ 痛", "为什么": "探针超时 %ds（卡住也是痛）" % timeout,
                "强度": strength, "探针": what, "秒": round(time.time() - t0, 1)}
    except Exception as e:
        return {"编号": pid, "感觉": "⛔ 痛", "为什么": "探针起不来：%s" % e,
                "强度": strength, "探针": what}
    secs = round(time.time() - t0, 1)
    tail = ((r.stdout or "") + (r.stderr or "")).strip().replace("\n", " ")[-160:]
    if r.returncode == 0:
        return {"编号": pid, "感觉": "✅ 通", "强度": strength, "探针": what, "秒": secs,
                "读数尾": tail}
    return {"编号": pid, "感觉": "⛔ 痛", "强度": strength, "探针": what, "秒": secs,
            "rc": r.returncode, "读数尾": tail}


def _owner(pid: str, n: int) -> str:
    idx = [p[0] for p in _dp().PLUGIN_SLOTS].index(pid)
    return "T%02d" % (idx % n + 1) if n else "未分"


def _rows(pids: list[str], timeout: int) -> list[dict]:
    dp = _dp()
    n = dp._tentacles()[0]
    meta = {p[0]: p for p in dp.PLUGIN_SLOTS}
    out = []
    for pid in pids:
        p = meta[pid]
        r = probe_one(pid, timeout)
        r.update({"名称": p[1], "做什么": p[2], "落点": p[3],
                  "归属触手": _owner(pid, n),
                  "隔离位": "state/tentacle-slots/%s" % _owner(pid, n)})
        out.append(r)
    return out


def _summary(rows: list[dict]) -> dict:
    s = {"末梢数": len(rows), "通": 0, "痛": 0, "未知": 0,
         "按强度": {"强": 0, "中": 0, "弱": 0, "—": 0}}
    for r in rows:
        if r["感觉"].startswith("✅"):
            s["通"] += 1
        elif r["感觉"].startswith("⛔"):
            s["痛"] += 1
        else:
            s["未知"] += 1
        s["按强度"][r.get("强度", "—")] = s["按强度"].get(r.get("强度", "—"), 0) + 1
    return s


def cmd_map(a) -> int:
    pids = [p[0] for p in _dp().PLUGIN_SLOTS]
    rows = _rows(pids, a.timeout)
    n = _dp()._tentacles()[0]
    body = []
    for k in range(n):
        mine = [r for r in rows if r["归属触手"] == "T%02d" % (k + 1)]
        body.append({"触手": "T%02d" % (k + 1),
                     "隔离位": "state/tentacle-slots/T%02d" % (k + 1),
                     "隔离位已真建": (ROOT / "state" / "tentacle-slots" / ("T%02d" % (k + 1))).is_dir(),
                     "末梢数": len(mine), "痛": sum(1 for r in mine if r["感觉"].startswith("⛔")),
                     "末梢": [{"编号": r["编号"], "名称": r["名称"], "感觉": r["感觉"],
                             "强度": r["强度"], "做什么": r["做什么"]} for r in mine]})
    out = {
        "全身图": body,
        "合计": _summary(rows),
        "触手根数": n,
        "口径": "每条末梢都是**真跑过的探针**；**没有读数就是未知，不是健康**；弱探针不证明功能可用",
    }
    # 落一份**带时间戳**的读数缓存：面板读它时必须标"上次读数"，**不当现读用**
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "触手根数": n,
        "合计": out["合计"],
        "痛或未知": [{"编号": r["编号"], "名称": r["名称"], "感觉": r["感觉"], "强度": r["强度"],
                  "为什么": r.get("为什么") or r.get("读数尾")} for r in rows
                 if not r["感觉"].startswith("✅")],
        "明细": [{"编号": r["编号"], "名称": r["名称"], "感觉": r["感觉"], "强度": r["强度"],
                "为什么": r.get("为什么") or r.get("读数尾")} for r in rows],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    out["读数已缓存"] = str(CACHE.relative_to(ROOT))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_probe(a) -> int:
    pids = [p[0] for p in _dp().PLUGIN_SLOTS]
    if a.pid:
        if a.pid not in pids:
            print(json.dumps({"ok": False, "why": "排班表里没有这个编号",
                              "合法编号": pids}, ensure_ascii=False))
            return 2
        pids = [a.pid]
    rows = _rows(pids, a.timeout)
    print(json.dumps({"现读末梢": rows, "合计": _summary(rows)},
                     ensure_ascii=False, indent=1))
    return 0 if all(r["感觉"].startswith("✅") for r in rows) else 5


def cmd_pain(a) -> int:
    """只看痛的地方 + **应变**（备用位）。这是"哪里痛第一时间知道"的答案。"""
    dp = _dp()
    fo_spec = importlib.util.spec_from_file_location("_fo_mod6", SCRIPTS / "failover.py")
    fo = importlib.util.module_from_spec(fo_spec)
    fo_spec.loader.exec_module(fo)
    sb = {r["编号"]: r for r in fo.table()}
    rows = [r for r in _rows([p[0] for p in dp.PLUGIN_SLOTS], a.timeout)
            if not r["感觉"].startswith("✅")]
    for r in rows:
        r["应变·备用位"] = sb.get(r["编号"], {}).get("备用位", "—")
        r["应变·触发"] = sb.get(r["编号"], {}).get("触发条件", "—")
    print(json.dumps({"痛/未知": rows, "条数": len(rows),
                      "说明": "未知 ≠ 健康：没探针的能力在这里也列出来，逼着补探针"},
                     ensure_ascii=False, indent=1))
    return 0 if not rows else 5


def caps_scan() -> dict:
    """**能力位覆盖层**：把框架的 157 个能力位也纳进神经网（此前只覆盖我自己那 23 件工具）。

    🔴 最重要的一条判据：**探针清单必须与「改状态」集合零交集**。
    「改状态」的唯一定义来自 `preflight.state_changing_kinds()`（**单一真源**，
    §八十四 我修掉的那个"手抄名单各算各的"—— 这里正是它的第一个正经消费方）。
    宁可少探 11 个，也**不许**为了覆盖率去碰会改状态的位（`wf_cache_clear` 当年真清过缓存）。
    """
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from gbt_allinone import caps_registry as R
        from gbt_allinone import preflight as P
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": "注册表加载失败：%s" % e}
    B = dict(getattr(R, "BENIGN_CAPS", {}) or {})
    sc = set(P.state_changing_kinds())
    un = set(getattr(R, "UNIMPLEMENTED_CAPS", {}) or {})
    rows, buckets = [], {"可探针": [], "须排除·改状态": [], "须排除·safe=False": [],
                         "须排除·需参数": []}
    for k in sorted(B):
        v = B[k] or {}
        if k in sc:
            cls = "须排除·改状态"
        elif v.get("safe") is False:
            cls = "须排除·safe=False"
        elif v.get("requires_params"):
            cls = "须排除·需参数"
        else:
            cls = "可探针"
        buckets[cls].append(k)
        rows.append({"kind": k, "域": v.get("domain"), "类": cls, "desc": v.get("desc")})
    probeable = buckets["可探针"]
    return {
        "ok": True,
        "良性表条数": len(B), "未实现条数": len(un), "合计口径": len(B) + len(un),
        "改状态定义条数": len(sc),
        "分类计数": {k: len(v) for k, v in buckets.items()},
        "覆盖率": "%.1f%%（%d / %d 可探针）" % (100.0 * len(probeable) / max(len(B), 1),
                                        len(probeable), len(B)),
        "可探针": probeable,
        "须排除·改状态": buckets["须排除·改状态"],
        "须排除·safe=False": buckets["须排除·safe=False"],
        "须排除·需参数": buckets["须排除·需参数"],
        "未实现（不在良性表，不可探针）": sorted(un),
        "红线判据": ("**可探针 ∩ 改状态 == ∅** —— 由自检咬住；"
                 "覆盖率低不是问题，**碰了会改状态的位才是问题**"),
        "明细": rows,
    }


# 🔴 **重件档**（本轮实测定的）：有些位的**代码自己就声明了长预算**，不是坏了。
#    `cross_scan.scan(deep=True)` docstring 原话：「含 H 维（**全能力运行时可达——较慢**）」，
#    H 维逐个调全部能力；X 维跑 4 个隔离扫描器、**每个 `timeout_s=240`** ⇒ 最坏近 1000s。
#    ⇒ **阈值必须按"这类活本来多慢"给**。一刀切会把"慢"报成"病"（与"把病报成好"同类的错读数）。
HEAVY_KINDS = ("cross_scan", "sec_scan", "sec_chain")
HEAVY_TIMEOUT_S = 900


def probe_cap(kind: str, timeout: int = 300) -> dict:
    eff = max(timeout, HEAVY_TIMEOUT_S) if kind in HEAVY_KINDS else timeout
    """真探**一个能力位**：走唯一门 `five-dim.py cap <kind>`（空参）。
    🔴 四态，不许把"探不动"混成"通"或"痛"：
        rc=0 ⇒ 通 ｜ 缺参 ⇒ **需参数·未探**（不是痛）｜ 被门拒 ⇒ **缺授权**（不是痛）｜ 其它 ⇒ 痛 ｜ 超时 ⇒ 痛

    🔴 **默认阈值 300s，不是 60s**（实测教训）：一刀切 60s 把两个**重扫描件**判成假痛 ——
    `sec_chain` 真值 **209.4s**、`sec_scan` **180.0s**，放宽后都 **✅ 通**。
    ⇒ 阈值必须按"这类活本来多慢"给，**不许拿一个数卡所有位**。
    （放宽后仍卡的只剩 `cross_scan`：**301.2s 还没回** ⇒ 那个是真痛，另查。）
    """
    five = ROOT / "tools" / "codex-scripts" / "five-dim.py"
    t0 = time.time()
    try:
        r = subprocess.run(PY + [str(five), "cap", kind], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=eff, cwd=str(ROOT))
    except subprocess.TimeoutExpired:
        return {"kind": kind, "态": "⛔ 痛",
                "为什么": "探针超时 %ds%s" % (eff, "（**重件档**）" if kind in HEAVY_KINDS else
                                       "（卡住也是痛）"),
                "重件": kind in HEAVY_KINDS, "秒": round(time.time() - t0, 1)}
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode == 0:
        return {"kind": kind, "态": "✅ 通", "秒": round(time.time() - t0, 1),
                "读数尾": out.strip().replace("\n", " ")[-110:]}
    low = out.lower()
    # ══ 分类：**解析信封**，不许拿子串猜 ═══════════════════════════════════════
    # 🔴 病史（本轮实测抓出，比跑数重要）：第一版用 `"denied" in low` 判"被门拒"，
    #    而门返回是**两层信封** —— **外层恒有 `"denied": false`** ⇒ 那个子串**永远成立**，
    #    于是把「缺少 kind 或 parallel」这种**缺参**（`error_class: user_error`）判成了"被门拒"。
    #    **一处否定信号被读成肯定信号。** 真值在 `result.error_class` / `result.message` 里。
    env = None
    i = out.find("{")
    if i >= 0:
        try:
            env, _end = json.JSONDecoder().raw_decode(out[i:])
        except Exception:  # noqa: BLE001
            env = None
    if isinstance(env, dict):
        res = env.get("result") if isinstance(env.get("result"), dict) else {}
        ec = str(res.get("error_class") or "")
        msg = str(res.get("message") or "")
        scopes = env.get("missing_scopes") or res.get("missing_scopes")
        if env.get("denied") is True or scopes:
            return {"kind": kind, "态": "🔒 被门拒·缺授权", "秒": round(time.time() - t0, 1),
                    "为什么": "**被门拒**（信封 denied=true / missing_scopes 非空）："
                    "这道位能探，但要主人发作用域",
                    "缺作用域": scopes, "读数尾": out.strip().replace("\n", " ")[-400:]}
        if ec == "user_error" or any(w in msg for w in ("缺少", "必填", "required", "missing")):
            return {"kind": kind, "态": "🟡 需参数·未探", "秒": round(time.time() - t0, 1),
                    "为什么": "空参探不动（user_error）：**%s** —— 要按它的契约给参再探" % (msg or ec),
                    "读数尾": out.strip().replace("\n", " ")[-400:]}
        return {"kind": kind, "态": "⛔ 痛", "rc": r.returncode, "秒": round(time.time() - t0, 1),
                "为什么": "信封 status=error 且非 user_error/非门拒：%s（%s）" % (msg or "-", ec or "-"),
                "读数尾": out.strip().replace("\n", " ")[-400:]}
    # 看不到 JSON 才退回文本启发 —— 且**否定的 denied 不算证据**（必须 `: true`）
    if re.search(r'"denied"\s*:\s*true', out) or "缺少作用域" in out or "missing_scopes" in low:
        return {"kind": kind, "态": "🔒 被门拒·缺授权", "秒": round(time.time() - t0, 1),
                "为什么": "**被门拒**（文本启发命中 missing_scopes）",
                "读数尾": out.strip().replace("\n", " ")[-400:]}
    if "缺少" in out or "必填" in out or "requires param" in low:
        return {"kind": kind, "态": "🟡 需参数·未探", "秒": round(time.time() - t0, 1),
                "为什么": "空参探不动（文本启发命中「缺少」）",
                "读数尾": out.strip().replace("\n", " ")[-400:]}
    return {"kind": kind, "态": "⛔ 痛", "rc": r.returncode, "秒": round(time.time() - t0, 1),
            "读数尾": out.strip().replace("\n", " ")[-400:]}


def run_list(limit: int = 0, only: str = "", skip: int = 0) -> dict:
    """**纯函数**：算出这次真探哪些位，并在运行期**再判一次排除**（fail-closed）。

    这是本层唯一会"动手"的地方，所以排除判据必须在**这里**也成立一次，
    不能只在分类阶段成立过一次就信任它。
    """
    cs = caps_scan()
    if not cs.get("ok"):
        return {"ok": False, "why": cs.get("why")}
    probeable = list(cs["可探针"])
    if only:
        probeable = [k for k in probeable if k == only]
        if not probeable:
            return {"ok": False, "why": "%r 不在可探针清单里（可能被排除或不存在）" % only,
                    "提示": "被排除的位**不许探** —— 改状态 %d + safe=False %d"
                    % (len(cs["须排除·改状态"]), len(cs["须排除·safe=False"]))}
    if skip:
        probeable = probeable[skip:]
    if limit:
        probeable = probeable[:limit]
    banned = set(cs["须排除·改状态"]) | set(cs["须排除·safe=False"])
    clash = sorted(set(probeable) & banned)
    if clash:
        return {"ok": False, "why": "**运行期排除判据被打破 ⇒ 拒绝执行**（fail-closed）",
                "撞上的位": clash}
    return {"ok": True, "待探": probeable, "条数": len(probeable),
            "运行期排除复核": "待探 ∩ (改状态 ∪ safe=False) = ∅ ✅",
            "被排除": {"改状态": cs["须排除·改状态"], "safe=False": cs["须排除·safe=False"]}}


def cmd_caps(a) -> int:
    if a.baseline or a.drift:
        return cmd_caps_drift(a)
    r = caps_scan()
    if not r.get("ok"):
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 3
    inter = sorted(set(r["可探针"]) & set(r["须排除·改状态"]))
    out = {k: v for k, v in r.items() if k != "明细"}
    out["现读核对·交集必须为空"] = inter or "∅（通过）"
    if a.detail:
        out["明细"] = r["明细"]
    if a.domain:
        out["按域过滤"] = [x for x in r["明细"] if x["域"] == a.domain]

    if a.run:
        rl = run_list(limit=a.limit, only=a.kind, skip=a.skip)
        if not rl.get("ok"):
            print(json.dumps({"caps": "拒绝执行", **rl}, ensure_ascii=False, indent=1))
            return 4
        rows = [probe_cap(k, a.timeout) for k in rl["待探"]]
        tally = {"✅ 通": 0, "⛔ 痛": 0, "🟡 需参数·未探": 0, "🔒 被门拒·缺授权": 0}
        for x in rows:
            tally[x["态"]] = tally.get(x["态"], 0) + 1
        snap = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "本次探位数": len(rows),
                "合计": tally, "运行期排除复核": rl["运行期排除复核"],
                "被排除": rl["被排除"], "逐位": rows}
        p = ROOT / "state" / "caps-probe-last.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

        # 🔴 **累积账**（本轮修的真问题）：单点探测**不许冲掉全量视图**。
        #    实测事故：`--run --kind cross_scan` 把 138 位的快照覆盖成"本次探位 1"，
        #    整张能力位面的读数**一句话就没了** ⇒ 单点查询与全量视图必须是**两本账**：
        #    这本按 kind 合并，只更新这次真探到的那几位，其余原样保留。
        acc_p = ROOT / "state" / "caps-probe-accum.json"
        acc = {}
        if acc_p.is_file():
            try:
                olda = json.loads(acc_p.read_text(encoding="utf-8"))
                acc = dict((olda or {}).get("逐位") or {})
            except Exception:  # noqa: BLE001
                acc = {}
        for x in rows:
            acc[x["kind"]] = x
        tally_all = {}
        for x in acc.values():
            tally_all[x["态"]] = tally_all.get(x["态"], 0) + 1
        acc_p.write_text(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "已覆盖位数": len(acc),
            "可探针总数": (caps_scan().get("分类计数") or {}).get("可探针"),
            "合计": tally_all, "本次": {"探位": len(rows), "合计": tally},
            "逐位": acc,
            "口径": "**累积账**：按 kind 合并、只更新这次探到的；单点探测**不会**冲掉全量视图",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        out["真探结果"] = {"本次探位数": len(rows), "合计": tally,
                       "运行期排除复核": rl["运行期排除复核"],
                       "痛": [x["kind"] for x in rows if x["态"] == "⛔ 痛"],
                       "需参数": [x["kind"] for x in rows if x["态"].startswith("🟡")],
                       "被门拒": [x["kind"] for x in rows if x["态"].startswith("🔒")],
                       "落盘": str(p.relative_to(ROOT))}
        # 🔴 两个数分开念
        out["已探针率"] = "%d / %d（可探针）" % (len(rows), r["分类计数"]["可探针"])
        out["口径"] = ("**可探针率 ≠ 已探针率**：87.9% 是「能不能探」，"
                     "上面这个才是「真探了多少」")
        out["仍待真探"] = r["分类计数"]["可探针"] - len(rows)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if not inter else 5


def caps_drift() -> dict:
    """漂移判定（**纯函数**，面板与 CLI 共用一份，不复制判据）。"""
    acc_p = ROOT / "state" / "caps-probe-accum.json"
    base_p = ROOT / "state" / "caps-health-baseline.json"
    if not base_p.is_file():
        return {"ok": False, "why": "还没有健康基线；先跑 caps --baseline",
                "基线文件": str(base_p.relative_to(ROOT))}
    base_doc = json.loads(base_p.read_text(encoding="utf-8"))
    base = base_doc.get("逐位") or {}
    cur = {}
    if acc_p.is_file():
        cur = {k: v.get("态") for k, v in
               (json.loads(acc_p.read_text(encoding="utf-8")).get("逐位") or {}).items()}
    RANK = {"✅ 通": 0, "🟡 需参数·未探": 1, "🔒 被门拒·缺授权": 1, "⛔ 痛": 2}
    worse, better, gone, new, unprobed = [], [], [], [], []
    for k in sorted(set(base) | set(cur)):
        b, c = base.get(k), cur.get(k)
        if b is None:
            new.append({"kind": k, "现在": c})
        elif c is None:
            gone.append({"kind": k, "基线": b})
        elif RANK.get(c, 1) > RANK.get(b, 1):
            # 2026-10-15 对齐（口径自相矛盾修正）：本文件 449 行自己写着
            #   「缺参 ⇒ 需参数·未探（**不是痛**）｜被门拒 ⇒ 缺授权（不是痛）」，
            #   但这里又把它们算进「变坏」⇒ 判决恒红、红得没依据。
            #   现在分开：**没测到 ≠ 变坏**（取不到读数不许当读数用）。
            if c.startswith(("🟡", "🔒")):
                unprobed.append({"kind": k, "基线": b, "现在": c})
            else:
                worse.append({"kind": k, "基线": b, "现在": c})
        elif RANK.get(c, 1) < RANK.get(b, 1):
            better.append({"kind": k, "基线": b, "现在": c})
    return {"ok": True, "基线": {"at": base_doc.get("at"), "位数": len(base)},
            "当前位数": len(cur), "🔴 变坏": worse, "🟢 变好": better,
            "🟡 未探/缺授权（**不算变坏**）": unprobed,
            "＋ 新增": new, "－ 消失": gone,
            "判决": ("🔴 **有 %d 位变坏** ⇒ 立刻查" % len(worse)) if worse else
            "✅ 无变坏（%d 位与基线同级）" % max(len(base) - len(better), 0),
            "口径": "优先级 通(0) < 缺授权/需参数(1) < 痛(2)；只报状态差，细节看累积账"}


def cmd_caps_drift(a) -> int:
    """**能力位健康漂移检测**（可生产化的关键一环）：
    把当前累积账与一份**基线**比，报出**状态变坏**的位（通 → 痛/缺授权/需参数）。

    🔴 为什么这是"可生产"的硬要求：探一次干净只能证明**那一刻**是好的；
    可生产要的是**它坏了你能立刻知道**。基线 + 漂移 = 才有回归检测。
    """
    acc_p = ROOT / "state" / "caps-probe-accum.json"
    base_p = ROOT / "state" / "caps-health-baseline.json"
    if a.baseline:
        if not acc_p.is_file():
            print(json.dumps({"ok": False, "why": "没有累积账可立基线；先跑 caps --run"}, ensure_ascii=False))
            return 3
        acc = json.loads(acc_p.read_text(encoding="utf-8"))
        base_p.write_text(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "来源": str(acc_p.relative_to(ROOT)),
            "合计": acc.get("合计"), "逐位": {k: v.get("态") for k, v in (acc.get("逐位") or {}).items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"ok": True, "立基线": str(base_p.relative_to(ROOT)),
                          "基线合计": acc.get("合计"), "位数": len(acc.get("逐位") or {}),
                          "口径": "以后任何位**从通变坏**，`--drift` 都会报出来"},
                         ensure_ascii=False, indent=1))
        return 0
    d = caps_drift()
    if not d.get("ok"):
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 3
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return 5 if d["🔴 变坏"] else 0


def cmd_selftest(a) -> int:
    """真身自检：**末梢覆盖** + **痛觉四态** + 超时算痛 + 未知不当健康。"""
    lines, bad = [], 0
    dp = _dp()

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 覆盖：每个能力要么有探针，要么**显式登记没有探针**（不许漏）
    pids = [p[0] for p in dp.PLUGIN_SLOTS]
    have = [p for p in pids if p in PROBES]
    ck("覆盖·末梢表与排班表逐条对应", set(have) <= set(pids) and len(have) == len(pids),
       "排班 %d 条 · 有探针 %d 条 · 缺 %s" % (len(pids), len(have), [p for p in pids if p not in PROBES] or "无"))

    # ①b **探针体检**（F35 回归）：探针引用的脚本/目录必须在盘上。
    #     一个路径写错的探针会**永远失败**，把"我的手指坏了"报成"身体痛" ⇒ 假痛。
    sanity = probe_sanity()
    ck("探针体检·所有探针的脚本与目录都在盘上（F35 回归）", not sanity,
       "问题 %s" % (sanity or "无"))

    # ② 痛觉四态：真跑一个必然成功的 + 真跑一个必然失败的 + 不存在的编号
    PROBES["__selftest_ok__"] = (PY + ["-c", "raise SystemExit(0)"], "强", "自检:必成功", None)
    PROBES["__selftest_bad__"] = (PY + ["-c", "raise SystemExit(7)"], "强", "自检:必失败", None)
    r_ok = probe_one("__selftest_ok__")
    r_bad = probe_one("__selftest_bad__")
    r_none = probe_one("__根本没有这条__")
    ck("痛觉·成功探针 ⇒ 通", r_ok["感觉"].startswith("✅"), r_ok["感觉"])
    ck("痛觉·失败探针 ⇒ 痛（带 rc）", r_bad["感觉"].startswith("⛔") and r_bad.get("rc") == 7,
       "%s · rc=%s" % (r_bad["感觉"], r_bad.get("rc")))
    ck("痛觉·没探针 ⇒ 未知（**不当健康**）", r_none["感觉"] == "❓ 未知", r_none["感觉"])

    # ③ 超时也必须算痛（卡住 ≠ 健康）
    PROBES["__selftest_slow__"] = (PY + ["-c", "import time; time.sleep(30)"], "强", "自检:必超时", None)
    t0 = time.time()
    r_slow = probe_one("__selftest_slow__", timeout=2)
    ck("痛觉·超时 ⇒ 痛（不是 ✅）", r_slow["感觉"].startswith("⛔") and "超时" in r_slow.get("为什么", ""),
       "%s · %s · 实测 %.1fs" % (r_slow["感觉"], r_slow.get("为什么", "")[:34], time.time() - t0))

    # ④ 可执行文件不在 ⇒ 痛（不是未知、更不是健康）
    PROBES["__selftest_noexe__"] = (["绝对不存在的程序-xyz"], "中", "自检:缺件", None)
    r_no = probe_one("__selftest_noexe__")
    ck("痛觉·可执行文件缺 ⇒ 痛", r_no["感觉"].startswith("⛔") and "不在" in r_no.get("为什么", ""),
       r_no.get("为什么", "")[:50])

    # ⑤ 变化分类（纯函数，五态）—— 分类错了巡检就会漏报新痛或虚报痊愈
    p = {"A": {"感觉": "✅ 通"}, "B": {"感觉": "⛔ 痛"}, "C": {"感觉": "⛔ 痛"},
         "D": {"感觉": "?"}, "E": {"感觉": "✅ 通"}}
    c = {"A": {"感觉": "⛔ 痛"}, "B": {"感觉": "✅ 通"}, "C": {"感觉": "⛔ 痛"},
         "D": {"感觉": "?"}, "E": {"感觉": "✅ 通"}, "F": {"感觉": "✅ 通"}}
    got = {r["编号"]: r["变化"] for r in classify(p, c)}
    ck("变化分类·通→痛 = 新痛", "新痛" in got.get("A", ""), "A: %s" % got.get("A"))
    ck("变化分类·痛→通 = 新愈", "新愈" in got.get("B", ""), "B: %s" % got.get("B"))
    ck("变化分类·痛→痛 = 未愈", "未愈" in got.get("C", ""), "C: %s" % got.get("C"))
    ck("变化分类·没出现过 = 新增", "新增" in got.get("F", ""), "F: %s" % got.get("F"))
    # 🔴 F36 回归：**空上一轮 + 本轮是痛** ⇒ 必须判成"新痛"，不许判成中性的"新增末梢"
    #    （否则判决会打【✅ 无变化，无新痛】= 假全清）
    g2 = {r["编号"]: r["变化"] for r in classify({}, {"X": {"感觉": "⛔ 痛"}})}
    ck("变化分类·空上轮+本轮痛 ⇒ 新痛（F36 回归）", "新痛" in g2.get("X", ""),
       "X: %s（**不许是「＋ 新增末梢」**）" % g2.get("X"))
    g3 = {r["编号"]: r["变化"] for r in classify({}, {"Y": {"感觉": "❓ 未知"}})}
    ck("变化分类·空上轮+本轮未知 ⇒ 新增未知（不当健康）", "未知" in g3.get("Y", ""),
       "Y: %s" % g3.get("Y"))
    ck("巡检深度·quick 必须跳过强探针（不影响工作效率）",
       len(_plan(False)) < len(_plan(True)) and all(
           PROBES.get(x, ("", "—"))[1] != "强" for x in _plan(False)),
       "quick %d 条 · deep %d 条 · 总数 %d"
       % (len(_plan(False)), len(_plan(True)), len(_dp().PLUGIN_SLOTS)))
    # 🔴 F38 回归：**部分覆盖必须被标出来**，不许让面板把"只测了一部分"念成"没有痛"
    co = coverage(["A", "B", "C", "D"], ["A", "B"])
    ck("覆盖·未测必须点名（F38 回归）",
       co["未测"] == 2 and co["未测名单"] == ["C", "D"] and "不许把部分覆盖念成全清" in co["警告"],
       "已测 %d/%d · 未测名单 %s" % (co["已测"], co["全机末梢"], co["未测名单"]))
    ck("覆盖·已测 == 全机时不该有未测名单", coverage(["A"], ["A"])["未测名单"] == [],
       "未测名单 %s" % coverage(["A"], ["A"])["未测名单"])

    # ── 能力位覆盖层（本轮新增：把 157 位也纳进神经网）───────────────────────
    cs = caps_scan()
    ck("能力位·注册表读得到（不写死条数）",
       cs.get("ok") and cs.get("良性表条数", 0) > 0,
       "良性表 %s 条 · 未实现 %s 条 · 合计 %s" % (cs.get("良性表条数"), cs.get("未实现条数"),
                                        cs.get("合计口径")))
    inter = sorted(set(cs.get("可探针") or []) & set(cs.get("须排除·改状态") or []))
    ck("能力位·**可探针 ∩ 改状态 == ∅**（本条是这一层的命门）", inter == [],
       "交集=%s" % (inter or "∅"))
    cnt = cs.get("分类计数") or {}
    ck("能力位·分类计数自洽（四类之和 == 良性表条数）",
       sum(cnt.values()) == cs.get("良性表条数"),
       "%s ⇒ 和=%d vs 表=%s" % (cnt, sum(cnt.values()), cs.get("良性表条数")))
    ck("能力位·未实现的位**不在**良性表里（口径自洽：157+11=168）",
       not (set(cs.get("未实现（不在良性表，不可探针）") or []) & set(
           x["kind"] for x in (cs.get("明细") or []))),
       "未实现 %d 条 · 与良性表交集 %d" % (
           len(cs.get("未实现（不在良性表，不可探针）") or []),
           len(set(cs.get("未实现（不在良性表，不可探针）") or []) & set(
               x["kind"] for x in (cs.get("明细") or [])))))

    # ── 真探层（caps --run）：**运行期排除必须在"要动手的地方"再成立一次** ──────
    rl = run_list(limit=5)
    banned = set(cs["须排除·改状态"]) | set(cs["须排除·safe=False"])
    ck("真探层·待探清单与排除集合零交集（运行期复核，不是只在分类阶段成立）",
       rl.get("ok") and not (set(rl.get("待探") or []) & banned),
       "待探 %d 位 · 交集 %s" % (rl.get("条数", 0), sorted(set(rl.get("待探") or []) & banned) or "∅"))
    rl_bad = run_list(only=(cs["须排除·改状态"][0] if cs["须排除·改状态"] else "root_fix"))
    ck("真探层·点名一个**被排除的位** ⇒ 拒（不许绕过）",
       rl_bad.get("ok") is False, rl_bad.get("why", "")[:70])
    ck("真探层·limit 生效且条数 ≤ limit", len(rl.get("待探") or []) <= 5,
       "limit=5 ⇒ %d 位" % len(rl.get("待探") or []))

    for k in ("__selftest_ok__", "__selftest_bad__", "__selftest_slow__", "__selftest_noexe__"):
        PROBES.pop(k, None)
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "痛觉四态都是**真跑出来**的；超时/缺件/无探针分别归到痛与未知"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="神经总线：全身感知（每个能力一条真探针）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map")
    m.add_argument("--timeout", type=int, default=TIMEOUT_S)
    m.set_defaults(func=cmd_map)
    p = sub.add_parser("probe")
    p.add_argument("pid", nargs="?", default="")
    p.add_argument("--timeout", type=int, default=TIMEOUT_S)
    p.set_defaults(func=cmd_probe)
    n = sub.add_parser("pain")
    n.add_argument("--timeout", type=int, default=TIMEOUT_S)
    n.set_defaults(func=cmd_pain)
    pt = sub.add_parser("patrol", help="巡检：不问也自己看一遍，只报变化（默认只跑中/弱探针，省时）")
    pt.add_argument("--deep", action="store_true", help="含强探针（整套自检，慢）")
    pt.add_argument("--all", action="store_true", help="连『稳定』也打出来")
    pt.add_argument("--timeout", type=int, default=TIMEOUT_S)
    pt.set_defaults(func=cmd_patrol)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    cp = sub.add_parser("caps", help="能力位覆盖层：157 位分类 + 覆盖率（默认只统计不真调）")
    cp.add_argument("--detail", action="store_true", help="附逐位明细")
    cp.add_argument("--domain", default="", help="只看某个域")
    cp.add_argument("--run", action="store_true", help="**真探**（默认只统计不真调）")
    cp.add_argument("--limit", type=int, default=0, help="--run 时最多探几位（0=全部）")
    cp.add_argument("--skip", type=int, default=0, help="--run 时跳过前 N 位（分批续探用）")
    cp.add_argument("--kind", default="", help="--run 时只探这一位")
    cp.add_argument("--timeout", type=int, default=300,
                    help="默认 300s —— 一刀切 60s 会把重扫描件判成**假痛**"
                         "（实测 sec_chain 209s / sec_scan 180s 放宽后都通）")
    cp.add_argument("--baseline", action="store_true",
                    help="把当前累积账立成**健康基线**（漂移检测的参照）")
    cp.add_argument("--drift", action="store_true",
                    help="与基线比对，报出**状态变坏**的位（可生产化的回归检测）")
    cp.set_defaults(func=cmd_caps)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
