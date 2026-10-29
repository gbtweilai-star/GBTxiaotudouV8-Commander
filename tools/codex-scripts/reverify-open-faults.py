#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**未清故障的『前提还成立吗』复核器**（只读 · 离线为主）

为什么要有这一件（一手账）：
  第 37 轮我抓到一件难看的事 —— **F1 与 F6 两条高危故障挂了十几轮，而它们的前提
  （"4 批改动没部署"）是我推的、从来没验过**；只花一个免费 GET 就读出来前提早就不成立了。
  ⇒ 故障清单会**无声腐烂**：写下的那一刻是真的，之后没人再读一次，就变成账里的假话。
  所以：**每条未清故障都要能回答"凭什么现在还算数"**，答不上来的要么补读数、要么结掉。

它怎么做：从 `state/排查台账.json` 的 `open_faults` 取现有条目，按 id 跑一条**探针**，
给出**新鲜读数**，并判三态之一：
  · `仍成立`   —— 探针读出来，前提现在还是真的
  · `已不成立` —— 读出来前提已经没了（**这一条会让本器退出码非零**，逼人回去改账）
  · `需人读`   —— 机器判不了（静态引用、语义问题），如实说"要人看"，**不假装判过**

口径（三条）：
  1. **没有探针 ≠ 通过**：没写探针的 id 一律报 `需人读`，不许默认绿。
  2. **凭据只报存在与长度**，绝不打印值（连掩码都只给前 4 位）。
  3. 只读：不改台账、不写盘、默认不出网（F4 那条是**回环** TCP，不算出网）。

用法：python tools/codex-scripts/reverify-open-faults.py [--json]
退出码：0 = 没有"已不成立"；1 = 至少一条前提已垮（回台账改去）；2 = 台账读不动。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "排查台账.json"

KEY_NAMES = ["DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "KIMI_API_KEY", "OPENAI_API_KEY",
             "TRIPO_API_KEY", "AGNES_API_KEY", "FREELLMAPI_API_KEY", "ABLITERATION_API_KEY"]


def _mask(v: str) -> str:
    v = (v or "").strip()
    return (v[:4] + "****(%d)" % len(v)) if v else "（空）"


# ── F2：密钥在 User 作用域，进程/子进程看不到 ──────────────────────────────
def probe_f2() -> tuple:
    env_hits = {k: _mask(os.environ.get(k, "")) for k in KEY_NAMES if os.environ.get(k)}
    user_hits = {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            i, names = 0, []
            while True:
                try:
                    names.append(winreg.EnumValue(k, i)[0])
                    i += 1
                except OSError:
                    break
        for n in KEY_NAMES:
            if n in names:
                user_hits[n] = "在（长度不读）"
    except Exception as exc:  # noqa: BLE001
        user_hits["<注册表读不到>"] = type(exc).__name__
    dotenv = ROOT / ".env"
    dot = {}
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k = line.split("=", 1)[0].strip()
                if k:
                    dot[k] = "有值" if line.split("=", 1)[1].strip() else "空"
    still = (not env_hits) and bool(user_hits)
    return ("仍成立" if still else "已不成立"), {
        "进程可见": env_hits or "一个都没有",
        "User 作用域在册": user_hits,
        ".env 里的键": dot or "（无 .env 或无键）",
    }


# ── F3：preflight 异常 fail-open ───────────────────────────────────────────
def probe_f3() -> tuple:
    f = ROOT / "gbt_allinone" / "api.py"
    if not f.is_file():
        return "需人读", {"说明": "api.py 不在"}
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [(i + 1, li.strip()) for i, li in enumerate(lines)
            if "preflight" in li.lower() and ("except" in li or "log" in li or "except" in li)]
    seg = [(i + 1, li.rstrip()) for i, li in enumerate(lines[1570:1600], start=1570)]
    has_return_in_except = any("return" in li or "raise" in li for _n, li in seg)
    return "需人读", {
        "api.py 里带 preflight 的异常/留痕行": ["%d: %s" % h for h in hits[:6]],
        "原引用段 1571-1600 里有没有 return/raise（有=已收紧）": has_return_in_except,
        "结论": "机器判不了『该不该收紧』—— 这是语义问题，需人读（甲=收紧 / 乙=只加可观测）",
    }


# ── F4：gbt-free 死路由 127.0.0.1:31415 ───────────────────────────────────
def probe_f4() -> tuple:
    cfg_hits = []
    for p in list((ROOT / "gbt_allinone").rglob("*.py")) + list((ROOT / "tools" / "codex-scripts").glob("*.py")):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "31415" in t:
            cfg_hits.append(str(p.relative_to(ROOT)))
    alive = False
    s = socket.socket()
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", 31415))
        alive = True
    except Exception:  # noqa: BLE001
        alive = False
    finally:
        s.close()
    return ("已不成立" if alive else "仍成立"), {
        "回环 127.0.0.1:31415": "通（有东西在听）" if alive else "不通（超时/拒绝）",
        "还引用 31415 的源码": cfg_hits[:6],
    }


# ── F5：cross_scan 的 D/E/F/V 只有名字没有实现 ─────────────────────────────
def probe_f5() -> tuple:
    """⚠️ 首版这里栽了一次，记下来：`_DIMS_NOT_IMPL` 是**定义在函数内部**的常量
    （`cross_scan.py:459`，缩进 4 空格）⇒ `getattr(module, ...)` 拿不到 ⇒ 我的探针
    把"**没读到**"直接判成了"**已不成立**"。那正是本器存在的理由的反面。
    ⇒ 改成两层：先试模块属性；拿不到就**静态读源码**（`ast.literal_eval` 解析那行字面量）；
    两层都拿不到才报 `需人读`。**永远不允许由"读不到"推出"已不成立"。**
    """
    # 一层：模块属性
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone import cross_scan as cs
        not_impl = getattr(cs, "_DIMS_NOT_IMPL", None)
        if not_impl is not None:
            return ("仍成立" if not_impl else "已不成立"), {
                "来源": "模块属性 _DIMS_NOT_IMPL（模块级）",
                "声明未实现的维度": list(not_impl),
            }
    except Exception as exc:  # noqa: BLE001
        _imp = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    else:
        _imp = "模块属性里没有这个名字（它定义在函数内部）"

    # 二层：静态读源码
    f = ROOT / "gbt_allinone" / "cross_scan.py"
    if f.is_file():
        import ast
        import re
        txt = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"_DIMS_NOT_IMPL\s*=\s*(\[[^\]]*\])", txt)
        if m:
            try:
                vals = ast.literal_eval(m.group(1))
            except Exception:  # noqa: BLE001
                vals = None
            if vals is not None:
                ln = txt[: m.start()].count("\n") + 1
                return ("仍成立" if vals else "已不成立"), {
                    "来源": "静态读源码 cross_scan.py:%d（模块属性拿不到）" % ln,
                    "声明未实现的维度": vals,
                    "为什么走这条": _imp,
                }
    return "需人读", {"说明": "模块属性与源码两处都没读到 _DIMS_NOT_IMPL —— **读不到 ≠ 不成立**",
                   "模块属性一层": _imp, "_读不到_主数据": True}


# ── F8：mcporter 引用的目录没进版本库 ─────────────────────────────────────
def probe_f8() -> tuple:
    d = "tools/shortvideo-music-mcp"
    tracked = subprocess.run(["git", "ls-files", d], cwd=str(ROOT), capture_output=True,
                             text=True, encoding="utf-8", errors="replace").stdout.strip()
    exists = (ROOT / d).is_dir()
    cfg = ROOT / "config" / "mcporter.json"
    referenced = False
    if cfg.is_file():
        referenced = d.replace("/", "\\") in cfg.read_text(encoding="utf-8", errors="replace") or d in cfg.read_text(encoding="utf-8", errors="replace")
    return ("仍成立" if (exists and not tracked and referenced) else "已不成立"), {
        "目录在盘上": exists, "已跟踪文件数": len(tracked.splitlines()) if tracked else 0,
        "mcporter.json 仍引用它": referenced,
    }


# ── F9：28 个技能根 / 多人份第三方技能 ────────────────────────────────────
def probe_f9() -> tuple:
    import importlib.util
    spec = importlib.util.spec_from_file_location("skill_vet", ROOT / "tools" / "codex-scripts" / "skill-vet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    roots = mod.discover_roots()
    total = 0
    for r in roots:
        if r.is_dir():
            total += len([x for x in r.iterdir() if x.is_dir() and (x / "SKILL.md").is_file()])
    return ("仍成立" if len(roots) > 8 else "已不成立"), {
        "自动发现的技能根": len(roots), "在场技能": total,
        "样本": [str(r) for r in roots[:4]],
    }


# ── F10：生产许可账里有不以 projects/ 开头的路径 ──────────────────────────
def probe_f10() -> tuple:
    """可机检：直接问那本账要 list，数出不以 `projects/` 开头的条目。

    给它写探针是**有意的** —— 这条故障的前提机器判得了，就不该留在"需人读"里。
    而且主人一旦处置掉（挪件重登记或撤登记），本探针会自己报 `已不成立`，
    提醒回台账结条目 —— **不需要谁记得回来手工关它**。
    """
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.tools import media_license as ML
        lst = ML.run("list")
    except Exception as exc:  # noqa: BLE001
        return "需人读", {"说明": "读不到许可账：%s: %s" % (type(exc).__name__, str(exc)[:100]),
                       "_读不到_主数据": True}
    ents = lst.get("entries") or []
    bad = [str(e.get("file")) for e in ents if not str(e.get("file") or "").startswith("projects/")]
    return ("仍成立" if bad else "已不成立"), {
        "账总条数": len(ents),
        "不以 projects/ 开头的条数": len(bad),
        "那几条": bad,
        "边界": "本探针只判**路径口径**；条目的 sha256/字节是否与真件一致要另核（本轮已核过 3/3 一致）",
    }


# ── F11：同一个密钥两份存量已分叉（agnes）─────────────────────────────────
def probe_f11() -> tuple:
    """可机检：逐 profile 比「保险箱」与「User 作用域注册表」。

    主人一旦把分叉同步掉，本探针会自己报 `已不成立`，提醒回台账结条目 —— 不用谁记得回来关。
    只印掩码与指纹，明文只在内存里比。
    """
    try:
        import hashlib
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            i, reg = 0, {}
            while True:
                try:
                    n, v, _t = winreg.EnumValue(k, i)
                    reg[n] = v
                    i += 1
                except OSError:
                    break
    except Exception as exc:  # noqa: BLE001
        return "需人读", {"说明": "读不到注册表：%s: %s" % (type(exc).__name__, str(exc)[:80]),
                       "_读不到_主数据": True}
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import deepseek_key as dk

    def fp(v: str) -> str:
        v = (v or "").strip()
        return "%d/%s" % (len(v), hashlib.sha256(v.encode("utf-8")).hexdigest()[:12]) if v else ""

    split, nonempty = [], 0
    for name in sorted(dk._PROFILES):
        vk, _s = dk.load_from_vault(name)
        rv = (reg.get(dk._PROFILES[name]["env"]) or "").strip()
        if vk:
            nonempty += 1
        if vk and rv and vk != rv:
            split.append({"profile": name, "库": dk.mask(vk), "库指纹": fp(vk),
                          "注册表": dk.mask(rv), "注册表指纹": fp(rv)})
 # 自纠（本题第一次跑就栽了）：**整个保险箱是空的**时，上面会得出"没有分叉"⇒ 判"已不成立"。
    #    而空保险箱**不代表主人的分叉修好了**，只代表**我这次看的 store 不对**
    #    （开机自检强制跑在隔离 store 里，所以它必然看到空库）。
    #    ⇒ 一个库都没读到 ⇒ 报 `需人读` + 打机器键 `_读不到_主数据`，**绝不由"没读到"推出"已不成立"**。
    if nonempty == 0:
        return "需人读", {
            "说明": "整个保险箱一个 profile 都没读到 ⇒ **不能**据此判『分叉已修好』"
            "（多半是本次 store 不是生产 store —— 开机自检就是跑在隔离 store 里的）",
            "本器看到的 vault 路径": str(ROOT / "gbt_allinone" / "store" / "secrets"),
            "权威读数在哪": "python tools/codex-scripts/key-consistency-check.py（对生产 store 跑）",
            "_读不到_主数据": True,
        }
    return ("仍成立" if split else "已不成立"), {
        "有内容的库数": nonempty, "分叉条数": len(split), "分叉明细": split,
        "边界": "只比**存量**；不判密钥是否有效（那要真打一次接口 = 出网）",
    }


# ── F12：注册表没收生产管线原语 ────────────────────────────────────────────
def probe_f12() -> tuple:
    """可机检：逐个查那批"真在跑却没在册"的名字还在不在 `all_caps()` 之外。

    主人一旦拍板（补进注册表 / 或明确登记只收能力位），本探针会自己报 `已不成立` 提醒结条目。
    """
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone import caps_registry as CR
        names = {c["name"] for c in CR.all_caps()}
    except Exception as exc:  # noqa: BLE001
        return "需人读", {"说明": "读不到注册表：%s: %s" % (type(exc).__name__, str(exc)[:80]),
                       "_读不到_主数据": True}
    watch = ["room_space", "mirror_space", "qiankun", "deployment_rehearsal", "collab_gateway",
             "notion", "tripo"]
    absent = [n for n in watch if n not in names]
    return ("仍成立" if absent else "已不成立"), {
        "注册表条数": len(names),
        "仍不在册的": absent,
        "边界": "只查『在不在册』；**不判该不该在册**（那是主人拍板的口径问题，见 D13）",
    }


def _strip_py_docstrings(text: str) -> str:
    """剥掉模块 docstring 与 `#` 注释，只留**会跑的代码**。

    为什么要剥：故障记录与工具的说明**必须**引用那些旧数字/旧路径才讲得清来由，
    而"引用"不该被当成"又写死了一遍"。第 54 轮我在另一条判据上正栽过这个跟头
    （台账里的 F17 记录被误判成"还指向 TEMP"）—— 结论：**逮文档 = 逼人删掉来由才绿**。
    """
    t = re.sub(r'"""(?:.|\n)*?"""', "", text)
    t = re.sub(r"'''(?:.|\n)*?'''", "", t)
    return "\n".join(li for li in t.splitlines() if not li.lstrip().startswith("#"))


# ── F13：isolation_sweep 被压着时 rc=2 ⇒ 判红 ─────────────────────────────
def probe_f13() -> tuple:
    """这条的前提**机器判不了**（要真把机器压满再跑一次），所以只验**缓解还在不在**：
    缓解在 ⇒ 负载下那次 rc=2 会被如实说成「本次无法判定」而不再算红；
    缓解不在 ⇒ 退回到"假红 + 假绿"两个方向的错。**本探针不制造负载。**
    """
    lib = ROOT / "gbt_allinone" / "tools" / "isolation_sweep.py"
    tst = ROOT / "gbt_allinone" / "tests" / "test_isolation_sweep.py"
    if not lib.is_file() or not tst.is_file():
        return "需人读", {"说明": "isolation_sweep.py 或它的判据不在盘上",
                       "_读不到_主数据": True}
    lt = lib.read_text(encoding="utf-8", errors="replace")
    tt = tst.read_text(encoding="utf-8", errors="replace")
    lib_mit = ("_cannot_tell" in lt) and ("本次无法判定" in lt)
    tst_mit = ("_cannot_tell" in tt) and ("本次无法判定" in tt)
 # 这一格我第一版又栽了（**第四次**同一类错）：我凭记忆写成 `assertEqual(1, rc)` 去找，
    #    而盘上写的是 `self.assertEqual(1, r["rc"], …)` ⇒ 探针报 False，
    #    读起来像"负控没钉死"，其实**钉死了**。教训与第 54 轮那三次一模一样：
    #    **工具说它在，就去读那一行，别猜它的写法。**
 # 第二版我还在正则尾巴上写了 `\b` —— `]` 与 `,` 都不是词字符 ⇒ **那里没有词边界**，
    #       于是照样匹配不上。尾巴必须写成显式的分隔符 `[,)]`，不许用 `\b` 蒙。
    neg_pinned = bool(re.search(r'assertEqual\(\s*1\s*,\s*(?:r\["rc"\]|rc)\s*[,)]', tt))
    neg_old = len(re.findall(r"assertNotEqual\(\s*r\[\"rc\"\]\s*,\s*0", tt))
    return ("已不成立" if (lib_mit and tst_mit and neg_pinned) else "仍成立"), {
        "库里的缓解（_cannot_tell + 本次无法判定）": lib_mit,
        "判据里的缓解": tst_mit,
        "负控钉死 rc == 1（不再用 assertNotEqual(rc,0)）": neg_pinned,
        "还没改回去的老写法 assertNotEqual(rc,0)": "%d 处（别的用例可能合法在用，本探针不据此判）" % neg_old,
        "边界": "只读源码；**不制造负载** ⇒ 永远不能据此说『负载下不会 rc=2』。"
        "绿不绿由 `test_isolation_sweep` 那条判据回答",
    }


# ── F14：待授权清单一页半手抄 / 生成器写死总数 ─────────────────────────────
def probe_f14() -> tuple:
    gen = ROOT / "tools" / "codex-scripts" / "gen-authz-page.py"
    page = ROOT / "docs" / "待授权清单一页.md"
    pdata = ROOT / "state" / "caps-probe-accum.json"
    if not gen.is_file():
        return "需人读", {"说明": "生成器不在仓里（它该在 tools/codex-scripts/）",
                       "_读不到_主数据": True}
    code = _strip_py_docstrings(gen.read_text(encoding="utf-8", errors="replace"))
    hard = sorted(set(re.findall(r"\b(?:138|157|183)\b", code)))
    live = None
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import caps_registry as CR   # noqa: PLC0415
        live = len(CR.all_caps())
    except Exception:  # noqa: BLE001
        live = None
    ptxt = page.read_text(encoding="utf-8", errors="replace") if page.is_file() else ""
    live_in_page = bool(live) and ("现读 %d 条" % live) in ptxt
    age_h = None
    if pdata.is_file():
        age_h = (time.time() - pdata.stat().st_mtime) / 3600.0
    residue = []
    if hard:
        residue.append("生成器**会跑的代码**里还有写死总数 %s" % hard)
    if not live_in_page:
        residue.append("页头没写注册表现读条数，或与现读 %s 不符" % live)
    if age_h is None:
        residue.append("逐位真探数据不在盘上")
    elif age_h > 12:
        residue.append("逐位真探数据已 %.1f 小时（阈值 12）⇒ ①『重跑真探』仍未做" % age_h)
    return ("仍成立" if residue else "已不成立"), {
        "生成器位置": "tools/codex-scripts/gen-authz-page.py（③ 已做）",
        "会跑的代码里写死的总数": hard or "无（② 已做）",
        "页头注册体现读条数对得上": live_in_page,
        "逐位真探数据年龄（小时）": None if age_h is None else round(age_h, 1),
        "仍未做的": residue or "无",
    }


# ── F15：台账时间戳偏移写错 ───────────────────────────────────────────────
def probe_f15() -> tuple:
    try:
        led = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return "需人读", {"说明": "台账读不动：%s" % type(exc).__name__, "_读不到_主数据": True}
    logs = led.get("log") or []
    newest = str(logs[-1].get("at") if logs else "")
    off = newest[-6:]
    machine_off = _dt.datetime.now().astimezone().strftime("%z")
    machine_off = machine_off[:3] + ":" + machine_off[3:] if len(machine_off) == 5 else machine_off
    off_ok = off in (machine_off, "+00:00") or newest.endswith("Z")
    kou = str(led.get("_口径") or "")
    doc_ok = ("+08:00" in kou) and ("+07:00" in kou)
    tst = ROOT / "gbt_allinone" / "tests" / "test_progress_ledger_contract.py"
    inv_ok = tst.is_file() and ("TimestampOffsetIsRealTest" in
                                tst.read_text(encoding="utf-8", errors="replace"))
    residue = []
    if not off_ok:
        residue.append("最新一笔 log 的偏移是 %s，机器真实偏移是 %s" % (off, machine_off))
    if not doc_ok:
        residue.append("台账 `_口径` 没写明历史上偏移写错这件事")
    if not inv_ok:
        residue.append("契约里没有偏移不变量（TimestampOffsetIsRealTest）")
    return ("仍成立" if residue else "已不成立"), {
        "最新一笔 log 的偏移": off, "机器真实偏移": machine_off,
        "口径里写明了历史缺陷": doc_ok, "契约里有偏移不变量": inv_ok,
        "历史条目不追改（有意）": True,
        "仍未做的": residue or "无 ⇒ 这条可以结掉（历史不追改是有意的，不是欠账）",
    }


# ── F16：描述面写死能力条数 ───────────────────────────────────────────────
def probe_f16() -> tuple:
    surfaces = {"plugins/gbt-master/lib/host.js": "host.js 面板注",
                "plugins/gbt-master/README.md": "插件 README 面板表",
                "index.html": "根 index.html 能力球描述"}
    dirty, missing = [], []
    for rel, label in surfaces.items():
        p = ROOT / rel
        if not p.is_file():
            missing.append(rel)
            continue
        if "158 项能力" in p.read_text(encoding="utf-8", errors="replace"):
            dirty.append(label)
    readme = ROOT / "plugins" / "gbt-master" / "README.md"
    relabelled = readme.is_file() and ("快照 · 2026-09-22" in
                                       readme.read_text(encoding="utf-8", errors="replace"))
    caps = ROOT / "capabilities.html"
    selflabels = caps.is_file() and ("CAPS_SOURCE='snapshot'" in
                                     caps.read_text(encoding="utf-8", errors="replace"))
    residue = []
    if dirty:
        residue.append("还在写死 158 项能力：%s" % dirty)
    if not relabelled:
        residue.append("README 那张表没改成『快照』")
    if not selflabels:
        residue.append("capabilities.html 没自报 source=snapshot（等于还在冒充现读）")
    if missing:
        residue.append("描述面文件不在：%s" % missing)
    return ("仍成立" if residue else "已不成立"), {
        "还在写死 158 的面": dirty or "无",
        "README 表已改名『快照』": relabelled,
        "capabilities.html 自报 source=snapshot": selflabels,
        "旧快照本身（183 条）": "仍在，但它自称快照 ⇒ 不再冒充现读；重生成属另一件活",
        "仍未做的": residue or "无",
    }


# ── F17：强制自审工具只在 %TEMP% 且依赖明文参照 ───────────────────────────
def probe_f17() -> tuple:
    tool = ROOT / "tools" / "codex-scripts" / "precommit-secret-scan.py"
    if not tool.is_file():
        return "需人读", {"说明": "自审工具不在仓里", "_读不到_主数据": True}
    code = _strip_py_docstrings(tool.read_text(encoding="utf-8", errors="replace"))
    uses_vault = "load_from_vault" in code
    no_plain_ref = "before-dpapi.bak" not in code
    selftest_rc = None
    try:
        p = subprocess.run([sys.executable, str(tool), "--selftest"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        selftest_rc = p.returncode
    except Exception:  # noqa: BLE001
        selftest_rc = None
    bak = Path(tempfile.gettempdir()) / "mcporter.json.before-dpapi.bak"
    residue = []
    if not uses_vault:
        residue.append("① 逐字比对没走 DPAPI 保险箱")
    if not no_plain_ref:
        residue.append("代码里还引用那份明文参照文件")
    if selftest_rc != 0:
        residue.append("离线自证没跑成（退出码 %s）" % selftest_rc)
    return ("仍成立" if residue else "已不成立"), {
        "工具在仓里": True,
        "① 走保险箱（load_from_vault）": uses_vault,
        "代码不依赖明文参照文件": no_plain_ref,
        "离线自证退出码": selftest_rc,
        "⚠️ %TEMP% 那份明文备份还在": bak.is_file(),
        "边界": "那条明文备份的去留**另案**（台账 D14），本条只管工具",
        "仍未做的": residue or "无",
    }


# ── F18：台账注入块从未进进程 ─────────────────────────────────────────────
def probe_f18() -> tuple:
    """**这条探针会在主人重启后自己报『已不成立』** —— 不用谁记得回来关它。

    读的是**活的那份** `/gbt-master` payload 的 `contexts` 字段（宿主自报注册成功哪几块）。
    回环 HTTP，与 F4 的回环 TCP 同一条口径：不算出网。
    """
    try:
        with urllib.request.urlopen("http://127.0.0.1:3080/gbt-master", timeout=20) as r:
            cat = json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return "需人读", {"说明": "取不到 /gbt-master：%s: %s" % (type(exc).__name__, str(exc)[:80]),
                       "_读不到_主数据": True}
    want = ("gbt-master-panels", "gbt-digital-human", "gbt-progress-ledger")
    ctxs = cat.get("contexts")
    if not isinstance(ctxs, list):
        return "仍成立", {
            "进程自报 version": cat.get("version"),
            "payload 里有没有 contexts": "没有 ⇒ 跑的还是没这个字段的旧代码",
            "结论": "台账块仍在进程之外 ⇒ **重启之前不许说『自动读取已生效』**",
        }
    got = {str(c.get("name")): bool(c.get("ok")) for c in ctxs if isinstance(c, dict)}
    missing = [n for n in want if n not in got]
    failed = [n for n in want if got.get(n) is False]
    return ("仍成立" if (missing or failed) else "已不成立"), {
        "进程自报 version": cat.get("version"),
        "进程内已注册块": sorted(got),
        "三块里缺的": missing or "无",
        "注册失败的": failed or "无",
    }


# ── F19：横扫里那条复现不出来的假红 ───────────────────────────────────────
def probe_f19() -> tuple:
    """**机器判不了**，但能把"落盘日志里这个文件红过几次"现数一遍 ——
    复现一次就自动把它从"未复现"变成"有据可查"。**未复现 ≠ 不存在。**
    """
    logs = sorted((ROOT / "output" / "blueprint-audit").glob("2026-09-26-满仓横扫-第*.log"))
    red = green = 0
    hits = []
    for f in logs:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "test_regression_stamp" not in line:
                continue
            if ("❌" in line) or ("FAILED" in line):
                red += 1
                hits.append("%s: %s" % (f.name, line.strip()[:110]))
            else:
                green += 1
    return "需人读", {
        "落盘日志份数": len(logs),
        "该文件红过的行": red, "绿过的行": green,
        "红的那几行": hits[:4] or "无",
        "为什么判不了": "本探针**不制造负载** ⇒ 复现不了就永远拿不到用例名；"
        "**未复现 ≠ 不存在**（负载相关的假红会一直污染横扫的可信度）",
    }


# ── F20：能源 status 与盘上事实不符（缺 key 却报"接线态"）──────────────────
def probe_f20() -> tuple:
    """可机检：逐个能源比 `status` 与它那把钥匙**在不在盘上**。

    不变量：`status == "可用"` ⟺ `key_ref` 指向的文件真在盘上；不在盘上就该是 `缺key`。
    谁都不在盘上却报"可用/接线态"，就是这条故障的实证。
    """
 # 必须**按包路径**导入（与判据同一份模块实例）：按文件路径再装一次会得到**第二个**
    #    模块对象，它内部依赖的注册表在二次装载下为 None ⇒ 探针自己抛
    #    `AttributeError: 'NoneType' object has no attribute '__dict__'`（实测踩过）。
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.tools import energy_pool as ep
    r = ep.run("sources")
    bad = []
    for s in (r.get("sources") or []):
        key_ref = s.get("key_ref")
        rel = str(key_ref or "")
        prefix = str(getattr(ep, "SECRETS_DIR", "")).rstrip("/") + "/"
        if rel.startswith(prefix):
            rel = rel[len(prefix):]
        on_disk = bool(rel) and (ep._secrets_dir() / rel).is_file()
        expect = "可用" if on_disk else "缺key"
        if s.get("status") != expect:
            bad.append({"source": s.get("source_id"), "status": s.get("status"),
                        "key_ref": key_ref, "在盘": on_disk, "应为": expect})
    return ("仍成立" if bad else "已不成立"), {
        "能源数": r.get("count"), "不一致的": bad[:5],
        "口径": "status==可用 ⟺ key_ref 在盘；不在盘却报可用/接线态 = 故障仍在",
    }


# ── F21：技能缺口生成器与验收器各算各的域集合 ──────────────────────────────
def probe_f21() -> tuple:
    """可机检：**生成器**报出来的域 vs **注册表**里的域。

    验收器是按注册表/引擎表逐域跑的（它报出的 FAIL 域里出现过 tools/tentacle/image_video），
    所以"注册表有、生成器没有"的域就是两边分叉的实证。本探针不跑验收器（那要 600s），
    只判分叉**在不在**：账要的是"前提还成立吗"，不是"两边跑一遍"。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_probe", ROOT / "tools" / "codex-scripts" / "gen-skill-gap-patch.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    mine = set(gen.collect().get("gap_domains") or [])   # 生成器是独立脚本，按路径装是对的
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    reg = {str((v or {}).get("domain") or "") for v in BENIGN_CAPS.values()} - {""}
    only_reg = sorted(reg - mine)
    return ("仍成立" if only_reg else "已不成立"), {
        "生成器的域": sorted(mine), "注册表的域": sorted(reg),
        "只在注册表里的（= 验收器会跑、生成器不产）": only_reg,
        "口径": "差集非空即两边分叉；差集为空说明已对齐",
    }


PROBES = {"F2": probe_f2, "F3": probe_f3, "F4": probe_f4, "F5": probe_f5,
          "F8": probe_f8, "F9": probe_f9, "F10": probe_f10, "F11": probe_f11,
          "F12": probe_f12, "F13": probe_f13, "F14": probe_f14, "F15": probe_f15,
          "F16": probe_f16, "F17": probe_f17, "F18": probe_f18, "F19": probe_f19,
          "F20": probe_f20, "F21": probe_f21}
# 探针留在这里**不止为在册的那些条**：故障结掉之后探针仍可手工单跑
#    （`python -c "import ...; print(probe_f13())"`），用于"它有没有复发"。
#    本器只对**台账里在册**的 id 出结论 —— 结掉的条目不再被咨询。


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="未清故障的前提复核（只读）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not LEDGER.is_file():
        print("台账不在：%s" % LEDGER)
        return 2
    try:
        led = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
 # 2026-09-26 自纠：台账"存在但读不动"（损坏/编码错）原来会裸 traceback 退出 1 ——
        #    而本器契约里 2 = 台账读不动、1 = 有前提已不成立，两个信号被混掉。
        print("台账读不动（%s: %s）：%s" % (type(exc).__name__, str(exc)[:120], LEDGER))
        return 2
    faults = led.get("open_faults") or []

    rows = []
    for f in faults:
        fid = f.get("id")
        probe = PROBES.get(fid)
        if probe is None:
            verdict, reading = "需人读", {"说明": "本器没有这条的探针 —— **没有探针 ≠ 通过**，要人看"}
        else:
            try:
                verdict, reading = probe()
            except Exception as exc:  # noqa: BLE001
                verdict, reading = "需人读", {"说明": "探针自己出错：%s: %s" % (type(exc).__name__, str(exc)[:120])}
 # **结论不许与读数自相矛盾** —— 这一条我改了两版，两版各错一个方向，都记在下面：
        #    第一版：读数写着"拿不到这个名字"，结论却报了"已不成立"（**由读不到推出结论**）。
        #    第二版：改成"读数里只要有『拿不到/出错』字样就降级"⇒ 把 F5 **误降级**了 ——
        #            它的静态读源码那层**明明读到了** `['D','E','F','V']`，只是旁边有一句
        #            *解释为什么走了这条路* 的说明里带了"拿不到"三个字。
        #    ⇒ 教训：**靠散文推断机器状态，两个方向都会错**。
        #    现在改为**机器键**：探针只在"主数据真的没读到"时打 `_读不到_主数据: True`，
        #    本器只认这个键。散文归散文，判定归判定。
        if reading.get("_读不到_主数据") and verdict != "需人读":
            verdict = "需人读"
            reading = dict(reading, **{"被本器降级": "探针自报『主数据没读到』 ⇒ 结论强制降为"
                                       "『需人读』（不许由读不到推出已不成立）"})
        rows.append({"id": fid, "what": f.get("what"), "verdict": verdict, "reading": reading,
                     "台账原记的 state": f.get("state")})

    broken = [r for r in rows if r["verdict"] == "已不成立"]
    if a.json:
        print(json.dumps({"ok": not broken, "at": led.get("updated_at"), "rows": rows},
                         ensure_ascii=False, indent=2))
    else:
        print("═══ 未清故障 · 前提复核（%d 条）═══" % len(rows))
        for r in rows:
            tag = {"仍成立": "✅ 仍成立", "已不成立": "🔴 已不成立", "需人读": "🟡 需人读"}[r["verdict"]]
            print("\n%s  %s" % (tag, r["id"]))
            print("   台账记的是：%s" % str(r["what"])[:96])
            for k, v in r["reading"].items():
                print("     · %s：%s" % (k, v))
        print("")
        print("结论：仍成立 %d · **已不成立 %d** · 需人读 %d"
              % (sum(1 for r in rows if r["verdict"] == "仍成立"), len(broken),
                 sum(1 for r in rows if r["verdict"] == "需人读")))
        if broken:
            print("🔴 这些条目的前提已经垮了 ⇒ **回台账改账**（结掉或重写），不许让它继续挂着：%s"
                  % "、".join(r["id"] for r in broken))
        print("边界：**没有探针 ≠ 通过**；本器不改台账、不出网（F4 那条是回环 TCP）。")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
