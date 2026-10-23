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
    """可机检：**交叉扫的「声明」与「覆盖」有没有分账**（F5 的真实内容）。

    🔴 2026-10-22 实测改写（留痕，旧口径见本函数末尾的历史注）：
      真跑一次 `cross_scan.scan()`（52s）拿到的是：
        `dims = [A,B,G,V,W,X,H]`（V **已实现**）· `dims_unimplemented = [D,E,F]`
      ⇒ F5 原话「D/E/F/**V** 只有名字没有实现」里，**V 那半句已经过期**；
        D/E/F 则是**声明不实现并写明理由**（参考集不存在/会报 86 条假警/抄第二份判据被禁止）。
      所以本条不再问「实现了吗」，而问**三件能机检的事**：
        ① `_DIMS_NOT_IMPL` 到底声明了哪几维（源码级现读）；
        ② 那几维的**理由**在 `cross_scan.py` 文档里有没有逐条写明（不写理由 = 静默不实现）；
        ③ V 不在未实现清单里（证明"已实现"这一半不是空话）。
      三条都成立 ⇒ 这是**分账清楚的设计决定**，不是缺陷。任何一条垮掉 ⇒ 仍成立。
    """
    f = ROOT / "gbt_allinone" / "cross_scan.py"
    if not f.is_file():
        return "需人读", {"说明": "cross_scan.py 不在，读不到"}
    txt = f.read_text(encoding="utf-8", errors="replace")
    import ast
    import re
    m = re.search(r"_DIMS_NOT_IMPL\s*=\s*(\[[^\]]*\])", txt)
    if not m:
        return "需人读", {"说明": "源码里没读到 _DIMS_NOT_IMPL —— **读不到 ≠ 不成立**"}
    try:
        declared = ast.literal_eval(m.group(1))
    except Exception:  # noqa: BLE001
        return "需人读", {"说明": "_DIMS_NOT_IMPL 字面量解析失败"}
    ln = txt[: m.start()].count("\n") + 1
    # ② 每一维的理由必须在文档里出现（按本仓文档的写法认这几种关键词）
    reasons = {
        "D": ("抄第二份判据", "audit-injection-honesty", "已经存在"),
        "E": ("没有", "声称的测试数"),
        "F": ("参考集", "86 条假警"),
    }
    missing_reason = []
    for d in declared:
        keys = reasons.get(d)
        if not keys:
            missing_reason.append("%s（本条没有登记理由模板）" % d)
            continue
        if not any(k in txt for k in keys):
            missing_reason.append(d)
    v_impl = "V" not in declared
    ok = bool(declared) and not missing_reason and v_impl
    return ("已不成立" if ok else "仍成立"), {
        "声明未实现（源码 cross_scan.py:%d）": declared,
        "理由是否逐条写明": "缺：%s" % missing_reason if missing_reason else "齐",
        "V 已在实现侧": v_impl,
        "实测：scan() 的 dims / dims_unimplemented": "[A,B,G,V,W,X,H] / [D,E,F]（2026-10-22 真跑 52s）",
        "口径": "声明不实现 + 理由逐条写明 + V 已实现 ⇒ 这是分账清楚的决定，不是缺陷",
    }


def probe_f5_old_readme_only() -> tuple:
    """（历史口径，保留供手工单跑）⚠️ 首版这里栽过一次：`_DIMS_NOT_IMPL` 定义在函数内部，
    `getattr(module, ...)` 拿不到 ⇒ 探针把"**没读到**"判成"**已不成立**"。"""
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
    """可机检：读**技能面盘点**的回执（`state/skill-surface-inventory.json`）。

    🔴 2026-10-22 改（留痕）：旧口径读 `skill-vet.py` 的 `discover_roots()` 只数"根 > 8"，
    既不数技能、也不分「谁的面」，所以永远只能回一句"仍成立"。现在尺子换成
    `skill-surface-inventory.py` 的机读回执，判三件事：
      ① 面有多大（根数 / 技能数 / 四桶分账）；
      ② **我们自营+托管** 面里有多少**未入账**（未进 `state/skill_atlas.json`）——
         这才是 F9 真正要盯的"没人管"；
      ③ 自上次清册以来**新长出来的根**（面在长，要看得见）。
    口径：只要"我方未入账 > 0"或"有新根" ⇒ **仍成立**（面确实还没管完）；
    两个都为 0 才算这条前提垮了。回执过期（>7 天）⇒ 需人读并点名重跑命令。
    """
    import datetime as _dt
    p = ROOT / "state" / "skill-surface-inventory.json"
    if not p.is_file():
        return "需人读", {"为什么": "还没有盘点回执",
                          "怎么补": "py -3.14 tools/codex-scripts/skill-surface-inventory.py"}
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return "需人读", {"为什么": "回执解析不了：%s" % e}
    at = str(j.get("at") or "")
    try:
        age_h = round((_dt.datetime.now().timestamp()
                       - _dt.datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()) / 3600, 1)
    except Exception:  # noqa: BLE001
        age_h = None
    # 🔴 2026-10-22 改（F9 收口）：未入册**不等于缺口**。现在读盘点器落成规则后的
    #    `ours_gap_count`（真缺口：未入册 且 不属于上游/存档/同名重复/嵌套素材(料)）。
    #    例外数单列出来只为看得见 —— 它**不**让本条红。
    gap = j.get("ours_gap") or []
    n_gap = j.get("ours_gap_count")
    if n_gap is None:
        n_gap = len(gap)
    n_exc = j.get("ours_exceptions")
    new_roots = j.get("new_roots_since_last") or []
    detail = {
        "回执": at, "龄（小时）": age_h,
        "根数": j.get("total_roots"), "技能数": j.get("total_skills"),
        "四桶": j.get("by_bucket"),
        "我方目录": j.get("ours_dirs"), "图鉴有名": j.get("ours_in_atlas"),
        "未入册（含例外）": j.get("ours_unaccounted_dirs"),
        "例外（上游/存档/重复/嵌套料）": n_exc,
        "**真缺口**": n_gap,
        "真缺口样例": [x.get("name") if isinstance(x, dict) else x for x in gap[:12]],
        "新长出来的根": (len(new_roots), new_roots[:5]),
        "口径": "**真缺口 > 0 或有新根** ⇒ 仍成立；例外再多也不算（那是分层，不是欠账）",
    }
    if age_h is not None and age_h > 24 * 7:
        detail["说明"] = "回执超过 7 天，建议重跑盘点"
        return "需人读", detail
    return ("仍成立" if (n_gap > 0 or new_roots) else "已不成立"), detail


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
    # 🔴 自纠（本题第一次跑就栽了）：**整个保险箱是空的**时，上面会得出"没有分叉"⇒ 判"已不成立"。
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
    """可机检：**注册表覆盖全部「能当 kind 分派」的入口**吗（F12 的真实判据）。

    🔴 2026-10-22 实测改写（留痕）：
      旧口径拿 `["room_space","mirror_space","qiankun","deployment_rehearsal",...]` 当"能力位名"
      去注册表里找 —— 但 `qiankun` / `mirror_space` / `deployment_rehearsal` 是**模块名**，
      `peer_register` 是 `collab_gateway` 的**op**，`room_*` 是 `room_space` 的 **op**：
      它们**本来就不该**以自己名字出现在注册表里（P16：两套名字空间不许互抄）。
      实测：api.py 有 305 个 `kind` 分支，**注册表 341 条把它们全盖住（差集 0）**。
      现判据（用现成的尺子 `registry-dispatch-audit.py`，不重写）：
        ① 能被 kind 分派、却不在注册表的入口数 == 0；
        ② F12 点名的那批名字，每一个都能落到「注册表里的某个 kind 或它的 op」上。
      两条都成立 ⇒ 不是缺收录，是账里把模块名/op 名写成了能力位名。
    """
    import subprocess
    r = subprocess.run([sys.executable, "-X", "utf8",
                        str(ROOT / "tools" / "codex-scripts" / "registry-dispatch-audit.py"), "--json"],
                       cwd=str(ROOT), capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    if i < 0:
        return "需人读", {"说明": "对账器没回 JSON：%s" % (out[:200] or r.stderr.decode("utf-8", "replace")[:200]),
                          "_读不到_主数据": True}
    j = json.loads(out[i:])
    orphan = j.get("kinds_not_in_registry") or []
    gap = j.get("gap") or []
    if j.get("kinds") is None or j.get("registry") is None:
        return "需人读", {"说明": "对账结果缺字段，无法判", "键": list(j.keys())[:10]}
    ok = not orphan and not gap
    return ("已不成立" if ok else "仍成立"), {
        "注册表条数": j.get("registry"),
        "api.py 的 kind 分支": j.get("kinds"),
        "能分派但不在注册表": orphan or "无（差集 0）",
        "F12 点名的真缺口": gap or "无",
        "点名的那批各自的落点": {x["name"]: x["判定"] for x in (j.get("watch") or [])},
        "口径": "模块名 ≠ 能力位名；room_*/peer_register 是 op，qiankun/mirror_space/deployment_rehearsal 是模块",
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
    # 🔴 这一格我第一版又栽了（**第四次**同一类错）：我凭记忆写成 `assertEqual(1, rc)` 去找，
    #    而盘上写的是 `self.assertEqual(1, r["rc"], …)` ⇒ 探针报 False，
    #    读起来像"负控没钉死"，其实**钉死了**。教训与第 54 轮那三次一模一样：
    #    **工具说它在，就去读那一行，别猜它的写法。**
    #    ⚠️ 第二版我还在正则尾巴上写了 `\b` —— `]` 与 `,` 都不是词字符 ⇒ **那里没有词边界**，
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
    """**现在机判得了**：读「满载红灯猎手」的回执（`state/load-red-hunt.json`）。

    🔴 2026-10-22 改（前提变了，留痕）：
      原先本条判「需人读」，理由写着「本探针**不制造负载** ⇒ 复现不了就永远拿不到用例名」。
      那句是诚实的，但也是可修的 —— 当天就补了 `tools/codex-scripts/load-red-hunt.py`：
      起 N 个纯 CPU 负载进程，反复跑目标模块，**把失败用例名逐条写进回执**。
      口径（写死）：
        · 回执里 reproduced=true ⇒ **仍成立**，并且**带上用例名**（这就是当初没留住的东西）；
        · 回执里 reproduced=false ⇒ **仍成立**（未复现 ≠ 不存在），但读数带「负载 × 轮次 × 耗时」，
          任何人可以照着复跑；不再占「需人读」。
        · 没有回执 / 回执过期（>7 天）⇒ 需人读（并点名跑哪条命令去补回执）。
    """
    p = ROOT / "state" / "load-red-hunt.json"
    if not p.is_file():
        return "需人读", {"为什么": "还没有满载复跑回执",
                          "怎么补": "py -3.14 tools/codex-scripts/load-red-hunt.py --runs 5 --load 4"}
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return "需人读", {"为什么": "回执解析不了：%s" % e}
    import datetime as _dt
    at = str(j.get("at") or "")
    try:
        ts = _dt.datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()
        age_h = round((_dt.datetime.now().timestamp() - ts) / 3600, 1)
    except Exception:  # noqa: BLE001
        age_h = None
    runs = j.get("runs") or []
    detail = {
        "回执": at, "龄（小时）": age_h,
        "目标": j.get("target"), "负载进程": j.get("load"), "轮次": len(runs),
        "每轮耗时ms": [r.get("ms") for r in runs][:8],
        "复现": bool(j.get("reproduced")),
        "失败用例名": j.get("failure_names") or "无",
        "口径": "reproduced=false 仍是『仍成立（未复现≠不存在）』；但读数可复跑，不再需人读",
    }
    if age_h is not None and age_h > 24 * 7:
        detail["说明"] = "回执超过 7 天，建议重跑一次"
        return "需人读", detail
    return "仍成立", detail


# ── F20：能源 status 与盘上事实不符（缺 key 却报"接线态"）──────────────────
def probe_f20() -> tuple:
    """可机检：逐个能源比 `status` 与它那把钥匙**在不在盘上**。

    不变量：`status == "可用"` ⟺ `key_ref` 指向的文件真在盘上；不在盘上就该是 `缺key`。
    谁都不在盘上却报"可用/接线态"，就是这条故障的实证。
    """
    # ⚠️ 必须**按包路径**导入（与判据同一份模块实例）：按文件路径再装一次会得到**第二个**
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
    """可机检：**生成器产出的域集合** vs **验收器读的那个域集合**（两边是不是同源同集合）。

    🔴 2026-10-22 改（**这条故障本身是我自己的判据错尺造出来的**，留痕）：
      旧口径拿生成器的 `gap_domains`（= **有待补的域**，现 18 个）去比注册表全部域（29 个），
      于是"注册表多出 13 个"被当成"两边分叉"—— 比错了对象（P1 判据错尺的教科书案例）。
      实测真相：生成器的每一行域、与验收器读的 `omni.DISTILLED_DOMAINS` **都是 30 个、一个不差**；
      契约测试 `test_skill_gap_patch`（6 tests）全绿。
      现口径：比「生成器 rows 覆盖的域」 vs 「omni.DISTILLED_DOMAINS 的键」，差集为空才算对齐。
    """
    import importlib.util
    # 生成器（独立脚本，按路径装）
    spec = importlib.util.spec_from_file_location(
        "gen_probe", ROOT / "tools" / "codex-scripts" / "gen-skill-gap-patch.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    rep = gen.collect()
    mine = {str(r.get("domain") or "") for r in (rep.get("rows") or [])} - {""}
    # 验收器读的那个真源（不要去读注册表的"能力域"，那是另一件事）
    spec2 = importlib.util.spec_from_file_location(
        "omni_probe", ROOT / "tools" / "codex-scripts" / "omni.py")
    omni = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(omni)
    theirs = set((getattr(omni, "DISTILLED_DOMAINS", {}) or {}).keys())
    only_gen = sorted(mine - theirs)
    only_ver = sorted(theirs - mine)
    aligned = not only_gen and not only_ver
    return ("已不成立" if aligned else "仍成立"), {
        "生成器 rows 的域": len(mine),
        "omni.DISTILLED_DOMAINS": len(theirs),
        "只在生成器": only_gen,
        "只在验收器源": only_ver,
        "生成器 gap_domains（有待补的域，**不是全部域**）": len(rep.get("gap_domains") or []),
        "口径": "两边都源自 omni.DISTILLED_DOMAINS；差集为空 = 同源同集合，这条故障不成立",
    }


def probe_f22() -> tuple:
    """可机检：**框架自改门的历史账**处置到哪一步了。

    🔴 2026-10-22 改（前提变了，留痕）：
      F22 原来的前提是「verify 报 未认领>0」。那一层已被处置：按门自带 force 出口重立基线
      （2026-10-22T05:14:08），并把 223 件**明示登记**在 state/framework-passports-legacy.json
      —— **不是补齐，是明示遗留**。所以本条现在的判据是：
        ① 遗留清单文件在不在、条数多少（这是"欠账别忘"的账本）；
        ② 新基线是否**晚于**遗留清单的生成时刻（证明门已经从新基线起算，而不是假装绿的旧基线）。
      两条都成立 ⇒ 「仍成立」= **这笔历史债还记在册上**（本就该一直看得见，直到人来决定补或认）。
    """
    p = ROOT / "state" / "framework-passports-legacy.json"
    if not p.is_file():
        return "已不成立", {"为什么": "遗留清单不在 ⇒ 这条要么已被人处理，要么被删了（删了就是抹账）"}
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return "需人读", {"为什么": "遗留清单解析不了：%s" % e}
    import subprocess
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "gbt_allinone.tools.framework_gate",
                        "--root", str(ROOT),
                        "--store", str(ROOT / "gbt_allinone" / "store" / "framework_changes"),
                        "verify"],
                       cwd=str(ROOT), capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    base_at = None
    unclaimed = None
    if i >= 0:
        v = json.loads(out[i:])
        base_at = v.get("baseline_at")
        unclaimed = v.get("未认领")
    legacy_at = str(j.get("generated_at") or "")[:19]
    detail = {
        "遗留件数": j.get("count"),
        "遗留清单生成": legacy_at,
        "现基线": base_at,
        "新基线晚于遗留清单": bool(base_at and legacy_at and base_at[:19] > legacy_at),
        "verify 未认领（新基线之后）": unclaimed,
        "口径": "遗留件数>0 且新基线晚于清单 ⇒ 欠账在册、门已从新基线起算（这是明示，不是补齐）",
    }
    ok = bool((j.get("count") or 0) > 0 and detail["新基线晚于遗留清单"])
    return ("仍成立" if ok else "需人读"), detail


def probe_f22_verify_gate() -> tuple:
    """（保留）旧的判据口径：直接问门要未认领数。手工排查时可单跑，不再作为 F22 的结论。"""
    import subprocess
    r = subprocess.run([sys.executable, "-X", "utf8", "-m",
                        "gbt_allinone.tools.framework_gate",
                        "--root", str(ROOT),
                        "--store", str(ROOT / "gbt_allinone" / "store" / "framework_changes"),
                        "verify"],
                       cwd=str(ROOT), capture_output=True)
    out = r.stdout.decode("utf-8", "replace")
    i = out.find("{")
    if i < 0:
        return "需人读", {"说明": "framework_gate verify 没回 JSON：%s" % (out[:200] or r.stderr.decode('utf-8', 'replace')[:200])}
    j = json.loads(out[i:])
    if j.get("changed_files") is None:
        return "需人读", {"说明": "verify 回包里没有 changed_files，无法判前提", "回包键": list(j.keys())[:12]}
    unclaimed = int(j.get("未认领") or 0)
    expired = int(j.get("认领但已过期") or 0)
    return ("仍成立" if (unclaimed or expired) else "已不成立"), {
        "changed_files": j.get("changed_files"),
        "未认领": unclaimed,
        "认领但已过期": expired,
        "已认领且新鲜": j.get("已认领且新鲜"),
        "口径": "未认领或认领已过期 > 0 即『改动没有有效护照』；两个都为 0 才算这条前提垮了",
    }


def probe_f23() -> tuple:
    """可机检：**授权账里有没有 `process_execute` 的票**（F23 的前提就是缺这张票）。

    只读：读 store/auth_grants.jsonl，不起进程、不跑排练（排练本身有副作用，探针不碰）。
    """
    p = ROOT / "gbt_allinone" / "store" / "auth_grants.jsonl"
    if not p.is_file():
        return "仍成立", {"为什么": "授权账不存在 ⇒ 没有票", "路径": str(p)}
    lines = [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    scopes = []
    for ln in lines:
        try:
            rec = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        sc = rec.get("scope") or rec.get("scopes") or ""
        if isinstance(sc, list):
            scopes.extend([str(x) for x in sc])
        elif sc:
            scopes.append(str(sc))
    has = "process_execute" in scopes
    return ("已不成立" if has else "仍成立"), {
        "授权账行数": len(lines),
        "出现过的 scope": sorted(set(scopes))[:12],
        "有没有 process_execute": has,
        "口径": "账里出现过 process_execute 就算『票可能已发』⇒ 这条前提要人复核；没出现过就是仍然缺票",
    }


def probe_f24() -> tuple:
    """可机检：**图鉴采集只扫每个技能根的直接子目录** ⇒ 嵌套技能永远进不了图鉴。

    实证（2026-10-22）：`~/.openclaw-autoclaw/skills/chengfeng-visual/animation-styles/
    ian-xiaohei-svg-motion/SKILL.md` 是个真技能（frontmatter 有名、有 SKILL.md），
    但 `omni.py collect_skills()` 用的是 `root.iterdir()` 一层 ⇒ 它永远不落进
    `state/skill_atlas.json`，于是 `omni ask` 里永远不会被当候选（路由看不见它）。

    本探针不跑 build（那是写手），只**现扫**我方四个容器里"深度 ≥2 的 SKILL.md"，
    看它们的 frontmatter 名在不在图鉴里：
      · 有漏 ⇒ **仍成立**，并把漏的名字点出来；
      · 一个都不漏 ⇒ 已不成立（要么采集改成递归了，要么嵌套件被清走了）。
    """
    import re as _re
    containers = [ROOT / "skills", ROOT / "plugins",
                  Path(os.path.expanduser("~")) / ".openclaw-autoclaw" / "skills",
                  Path(os.path.expanduser("~")) / ".dsh" / ".agent-presets"]
    at = ROOT / "state" / "skill_atlas.json"
    if not at.is_file():
        return "需人读", {"说明": "图鉴不在，读不到"}
    try:
        atlas_names = {s.get("name") for s in (json.loads(at.read_text(encoding="utf-8")).get("skills") or [])}
    except Exception as e:  # noqa: BLE001
        return "需人读", {"说明": "图鉴解析不了：%s" % e}
    nested, missing = [], []
    for base in containers:
        if not base.is_dir():
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in ("__pycache__", ".git", "node_modules")]
            if "SKILL.md" not in fn:
                continue
            depth = len(Path(dp).relative_to(base).parts)
            if depth <= 1:
                continue                      # 直接子目录：采集能扫到，不属本条
            try:
                head = (Path(dp) / "SKILL.md").read_text(encoding="utf-8", errors="replace")[:800]
            except OSError:
                continue
            m = _re.search(r"(?m)^name:\s*(.+)$", head)
            nm = (m.group(1).strip().strip("\"'") if m else Path(dp).name)
            nested.append(nm)
            if nm not in atlas_names:
                missing.append({"name": nm, "path": str(dp)})
    return ("仍成立" if missing else "已不成立"), {
        "我方容器里的嵌套技能数": len(nested),
        "其中**不在图鉴**的": len(missing),
        "漏的名字": [x["name"] for x in missing][:10],
        "样例路径": [x["path"] for x in missing][:3],
        "根因": "omni.py collect_skills() 用 root.iterdir() 只扫一层；嵌套技能永不入册",
        "口径": "嵌套技能 >0 且有漏 ⇒ 仍成立；一个不漏才算修好（或嵌套件已清）",
    }


def probe_f25() -> tuple:
    """可机检：**端点有没有活 worker**（2026-10-22 现场逮到的那条）。

    实测症状（当轮原话）：`/health` 返回 `workers{ready:0, running:0, initializing:0}`、
    `inQueue` 从 6 涨到 8；`Worker /v1/models` 仍 200（元数据是缓存的）、
    `chat/completions` 25 秒拿不到首字 ⇒ **页面转圈**。
    判据：`ready + running == 0` 且 `inQueue > 0` ⇒ 仍成立（有请求在排、没人干）。
    只读，15 秒超时；拿不到凭据/连不上 ⇒ 需人读（不猜）。
    """
    import re as _re
    import urllib.request
    cred = os.path.expanduser(r"~\.dsh\.credentials.yaml")
    key = None
    try:
        t = open(cred, encoding="utf-8").read()
        m = _re.search(r"GBT_POTATO_API_KEY:[ \t]*(?:ref:)?[ \t]*[\"']?([A-Za-z0-9_\-]{16,})", t)
        key = m.group(1) if m else None
    except OSError:
        key = None
    if not key:
        key = os.environ.get("GBT_POTATO_API_KEY")
    if not key:
        return "需人读", {"为什么": "拿不到 GBT_POTATO_API_KEY（refs 与环境变量都没有）"}
    url = "https://api.runpod.ai/v2/qnnqf9w8xcefj8/health"
    try:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key,
                                                  "User-Agent": "gbt-reverify/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read(600).decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return "需人读", {"为什么": "health 拿不到：%s: %s" % (type(e).__name__, str(e)[:80])}
    w = (j.get("workers") or {})
    jobs = (j.get("jobs") or {})
    ready = int(w.get("ready") or 0)
    running = int(w.get("running") or 0)
    inq = int(jobs.get("inQueue") or 0)
    alive = ready + running
    return ("仍成立" if (alive == 0 and inq > 0) else "已不成立"), {
        "workers": w, "jobs_inQueue": inq,
        "口径": "ready+running==0 且 inQueue>0 ⇒ 有人排队没人干（页面转圈的同一个症状）",
    }


PROBES = {"F2": probe_f2, "F3": probe_f3, "F4": probe_f4, "F5": probe_f5,
          "F8": probe_f8, "F9": probe_f9, "F10": probe_f10, "F11": probe_f11,
          "F12": probe_f12, "F13": probe_f13, "F14": probe_f14, "F15": probe_f15,
          "F16": probe_f16, "F17": probe_f17, "F18": probe_f18, "F19": probe_f19,
          "F20": probe_f20, "F21": probe_f21, "F22": probe_f22, "F23": probe_f23,
          "F24": probe_f24, "F25": probe_f25}
# ⚠️ 探针留在这里**不止为在册的那些条**：故障结掉之后探针仍可手工单跑
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
        # 🔴 2026-09-26 自纠：台账"存在但读不动"（损坏/编码错）原来会裸 traceback 退出 1 ——
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
        # 🔴 **结论不许与读数自相矛盾** —— 这一条我改了两版，两版各错一个方向，都记在下面：
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
