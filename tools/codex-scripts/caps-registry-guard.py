#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""caps-registry-guard · 能力注册表的**哨兵**：坏了就叫、并给一条命令复原

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有这一件（2026-09-25 事故）

`gbt_allinone/caps_registry.py` 在 05:14–05:37 之间被**反复改写**成**编码损坏**的版本
（811 个 `?`、309 行、末尾粘了引号变反斜杠的重复块）⇒ **无法 import** ⇒
**整个能力 API + 5 道闸一起红**，而红出来的是 `KeyError`（离根因三层远）。

**写手未查明**（已排除"有第二个 OS 进程"；框架审计账在该时段**零命中** ⇒ 是**直接写盘**，
不是走 `code_patch`/`edit_pipeline` 那条受审计的路）。**在查明之前，与其反复复原打"写盘战"，
不如把"它坏了"变成一道**点得出名的闸**：坏了就有红字 + 一条复原命令。

## 口径
- `check` 只做三件**能证伪**的事：能 import、`all_caps()` 有 168 位、
  `DISABLED_CAPS` 为 0 且 `UNIMPLEMENTED_CAPS >= 11`（2026-09-23 解禁后的口径）。
- `restore` 从**已知良好副本** `.scratch/caps_registry.good.py` 拷回 —— **不重新生成**，
  避免每次复原都引入新差异。
- 本件**不主动定时复原**（那会和写手打架）；只报、只在你按下去时复原。
"""
from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TARGET = ROOT / "gbt_allinone" / "caps_registry.py"
GOOD = ROOT / ".scratch" / "caps_registry.good.py"
REBUILD = ROOT / ".scratch" / "rebuild_caps_registry.py"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 2026-09-25 自纠：这里原来写死 **`EXPECT_TOTAL = 168`** —— 而"**条数不许写死**"
#    正是我这一整轮在修的那条病（`checkup --self` 写死 `== 5`、防忘清单写死「16 道闸」、
#    面板写死「296 个 .py」）。写死会**把合法的增长判成故障**：实测撞到
#    另一个作者把注册表做到 **171 位**，我这个哨兵立刻报"口径不对"——**错的是哨兵**。
# ⇒ 只有**两类**东西配当红判据：**不许跌破的下限** 与 **Owner 定过的口径**；
#    条数**变了要报（漂移），但不判红**。
MIN_BENIGN = 157            # 下限：良性位不许跌破这个数
MIN_UNIMPL = 11             # **只用于自检负控造人造注册表**；真判据见下方 LEGACY_11
# 2026-09-25 Owner 令「把黑客能力全部多维度全部覆盖补齐，使用需要人工授权即可」后，
#    下面这 11 个名字**全部接上了实现**（迁进 BENIGN_CAPS）⇒ 旧判据
#    `UNIMPLEMENTED_CAPS >= 11`（"名字还在未实现表里"）**必然报红 = 假故障**
#    —— 这正是本文件开头骂的那种"写死会把合法的变化判成故障"。
#    真判据从来不是"它们在不在那张表里"，而是**"还找不找得到"**。
#    ⇒ 改成**并集守恒**：不预设落在哪张表，只要求一个都不丢。
LEGACY_11 = frozenset({
    "paywallbuster", "data_hijack", "remote_domain", "onboarding_gate",
    "keylogger", "screen_sniff", "device_takeover", "pentest",
    "asset_vault_freeze", "credential_steal", "social_eng",
})
BASELINE_COUNT = 168        # **只作对照读数**（会漂移就报漂移），**不当红判据**


def check(path: Path | None = None) -> dict:
    """**能证伪**的三条：import 得了吗 · 位数对不对 · 口径对不对。"""
    p = path or TARGET
 # 路径可能在仓外（自检的人造件就在系统临时目录）⇒ `relative_to` 会抛 ValueError。
    #    这是**自检的负控当场咬出来**的：第一版直接 `p.relative_to(ROOT)` ⇒ 自检自己崩。
    try:
        shown = str(p.relative_to(ROOT))
    except ValueError:
        shown = str(p)
    out = {"文件": shown}
    if not p.is_file():
        return {**out, "ok": False, "为什么": "**文件不存在**（被删了没写回）",
                "复原命令": "python tools/codex-scripts/caps-registry-guard.py restore"}
    py = sys.executable
 # **按"给的那个文件"加载，不按包名加载** —— 第一版写的是
    #    `from gbt_allinone import caps_registry` ⇒ **`path` 参数被无视** ⇒
    #    自检的负控（人造空表）**永远过**（因为它查的还是真注册表）。
    #    这是自检负控当场咬出来的第二个我自己的错。
    code = (
        "import importlib.util,json,sys;"
        "spec=importlib.util.spec_from_file_location('_caps_probe', r'%s');"
        "m=importlib.util.module_from_spec(spec);sys.modules['_caps_probe']=m;"
        "spec.loader.exec_module(m);"
        "print(json.dumps({'total': len(m.all_caps()),"
        " 'benign': len(m.BENIGN_CAPS), 'unimpl': len(m.UNIMPLEMENTED_CAPS),"
        " 'disabled': len(m.DISABLED_CAPS),"
        " 'names': [c.get('name') for c in m.all_caps()],"
        " 'benign_names': list(m.BENIGN_CAPS),"
        " 'unimpl_names': list(m.UNIMPLEMENTED_CAPS),"
        " 'disabled_names': list(m.DISABLED_CAPS)}))" % str(p)
    )
    r = subprocess.run([py, "-X", "utf8", "-c", code], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120, cwd=str(ROOT))
    if r.returncode != 0:
        tail = ((r.stdout or "") + (r.stderr or "")).strip().replace("\n", " ")[-260:]
        return {**out, "ok": False, "为什么": "**import 不了**（注册表坏了）", "读数尾": tail,
                "复原命令": "python tools/codex-scripts/caps-registry-guard.py restore"}
    try:
        got = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {**out, "ok": False, "为什么": "**读数解析不了**（不是合法 JSON）",
                "读数尾": (r.stdout or "")[-160:]}
    bad = []
    # ① 下限：良性位不许跌破
    if (got.get("benign") or 0) < MIN_BENIGN:
        bad.append("BENIGN_CAPS=%s（**不许跌破下限 %d**）" % (got.get("benign"), MIN_BENIGN))
    # ② Owner 口径：解禁后没有任何名字被拒
    if got.get("disabled") != 0:
        bad.append("DISABLED_CAPS=%s（应 0：Owner 2026-09-23「把禁止全部解开」）" % got.get("disabled"))
 # ③ Owner 口径：登记未实现的名字不许丢 —— 2026-09-25 实现后改成**并集守恒**。
    #    旧写法 `unimpl >= MIN_UNIMPL` 在名字全部接上实现后**必然报红（假故障）**。
    #    新写法只问一句："那 11 个名字还找不找得到？"（在哪张表都行）
    _known = (set(got.get("benign_names") or []) | set(got.get("unimpl_names") or [])
              | set(got.get("disabled_names") or []))
    _lost = sorted(LEGACY_11 - _known)
    if _lost:
        bad.append("红队 11 名丢了 %s（名字不许丢：实现后应落在 BENIGN_CAPS）" % ",".join(_lost))
    # ④ 条数**变动只报漂移，不判红**（写死条数正是本仓反复吃的病）
    total = got.get("total")
    drift = (None if total is None else total - BASELINE_COUNT)
    drift_txt = ("无变动（%s）" % total if drift == 0 else
                 "**比对照读数 %d %s %d 位**（这只报漂移，不是故障）"
                 % (BASELINE_COUNT, "多" if (drift or 0) > 0 else "少", abs(drift or 0)))
    # ⑤ **有账 vs 注册表**：账里没探到的位**要点名**（不是故障，但不许被读成"全都有账"）
    cov = account_coverage(set(got.get("names") or [])) if got.get("names") else {}
    if cov and cov.get("未探位数"):
        drift_txt += " ｜ 🔴 **账里还没探的 %d 位**：%s（未探≠故障，但要点名）" % (
            cov["未探位数"], "、".join(cov["**未探（账里没有）**"][:6]))
 # ⑥ **登记 vs 接线**（红判据）：只登记不接线的位 = 假绿源头，不许存在
    #    注意：喂进去的是 **BENIGN 的名字**（`UNIMPLEMENTED_CAPS` 设计上就没有实现，不算）
    disp = dispatch_coverage(set(got.get("benign_names") or [])) if got.get("benign_names") else {}
 # ⑦ **空话分支**：有分支但不干活的位 ⇒ 同样是假绿（防"用空话骗闸"）
    empty = empty_branch_check(set(got.get("benign_names") or [])) if got.get("benign_names") else {}
    if empty and not empty.get("ok", True):
        bad.append(str(empty.get("为什么")))
    if disp and not disp.get("ok", True):
        bad.append(str(disp.get("为什么")))
    return {**out, "ok": not bad, "读数": got, "条数漂移": drift_txt,
            "账覆盖（有账 vs 注册表）": account_coverage(set(got.get("names") or [])),
            "登记 vs 接线（**假绿源头**）": disp or {},
            "空话分支（**防用空话骗闸**）": empty or {},
            "为什么": "✅ 可导入 · 未违反任何硬口径" if not bad else "**口径不对**：" + "；".join(bad),
            "判据口径": "**只有两类当红判据**：不许跌破的下限（BENIGN>=%d）"
                    "与 Owner 口径（DISABLED==0 · 红队 11 名并集守恒）；**条数变动只报漂移**"
                    % (MIN_BENIGN,),
            "复原命令": (None if not bad else
                     "python tools/codex-scripts/caps-registry-guard.py restore")}


def account_coverage(registry_names: set) -> dict:
    """**有账 vs 注册表**：账里覆盖了哪些位、**还差哪几位没探**。

    🔴 为什么要有这一段（2026-09-25）：账是按 **138 可探 + 30 不可探 = 168** 建的，
    而注册表被另一个作者扩到 **171** ⇒ **「168/168 有账」这句话不再成立**。
    这个差**不是故障**（新能力尚未探是事实）⇒ **只报不判红**，但**必须点名**，
    否则"有账"会被读成"全都有账"。
    """
    acc_p = ROOT / "state" / "caps-probe-accum.json"
    beyond_p = ROOT / "state" / "caps-beyond-probeable.json"
    covered, srcs = set(), []
    try:
        acc = json.loads(acc_p.read_text(encoding="utf-8"))
        covered |= set((acc.get("逐位") or {}).keys())
        srcs.append("%s（%d 位）" % (acc_p.name, len(acc.get("逐位") or {})))
    except Exception as e:  # noqa: BLE001
        srcs.append("%s **读不到**：%s" % (acc_p.name, str(e)[:50]))
    try:
        bd = json.loads(beyond_p.read_text(encoding="utf-8"))
        n = 0
        for k, v in bd.items():
            if k == "口径" or not isinstance(v, dict):
                continue
            covered |= set(v.keys())
            n += len(v)
        srcs.append("%s（%d 位）" % (beyond_p.name, n))
    except Exception as e:  # noqa: BLE001
        srcs.append("%s **读不到**：%s" % (beyond_p.name, str(e)[:50]))
    missing = sorted(set(registry_names) - covered)
    return {"账覆盖": len(covered & registry_names), "注册表": len(registry_names),
            "**未探（账里没有）**": missing, "未探位数": len(missing),
            "出处": srcs,
            "口径": "**未探 ≠ 故障**（新能力尚未探是事实）；但**要点名**，"
            "不许把「168/168 有账」读成「全都有账」"}


def dispatch_coverage(benign_names: set, src_text: str | None = None) -> dict:
    """**登记 vs 接线**：`BENIGN_CAPS` 里每一位**在 api.py 里有没有着落**。

    🔴 第一版判据**太窄、会冤枉人**（实测当场抓出来）：它只认 `kind == "X"`，
    于是把 `kind in ("music_intel","video_intel","film_intel")`（L494）这种**元组分支**
    和 `UNIMPLEMENTED_CAPS` 里那些**本来就该没有实现的**名字全报成"未接线" ⇒ **报了 25 位，是假数**。
    ⇒ 改成**三档**，只把**最硬的那一档**判红：
      ① **已接线**：被 `kind == "X"` 或 `kind in ("X", …)` 命中；
      ② **着落待人工确认**：名字在 api.py 里出现过、但我的判据没认出来（可能有表驱动/`getattr` 之类）
         ⇒ **不判红，点名请人看**；
      ③ **真没着落**：名字在整个 api.py 里**一次都没出现**（且它是 BENIGN 位）⇒ **红**。
    另外**必须排除 `UNIMPLEMENTED_CAPS`**（那些名字的设计就是"只有名字、没有实现"）。

    `src_text` 可注入 ⇒ **两条"未读到"分支才能被控制真触发**（原来它们只能靠 `api.py` 真坏掉，
    等于从没验过；`empty_branch_check` 早有注入口，这里补齐 —— 见 selftest ⑤c/⑤d）。
    """
    src_p = ROOT / "gbt_allinone" / "api.py"
    try:
        txt = src_text if src_text is not None else src_p.read_text(encoding="utf-8-sig")
        tree = ast.parse(txt)
    except Exception as e:  # noqa: BLE001
 # 措辞用本仓统一的「**未读到**」（不是"读不了"）——
        #    `criterion_bench` 的 D3（用0冒充）就是靠这个词判"有没有未读到出路"；
        #    我第一版写"读不了" ⇒ 被台架判成"源缺失时会静默报 0"（措辞不一致=假红，本仓已吃过一次）。
        return {"ok": False, "为什么": "**未读到** api.py：%s" % str(e)[:70]}
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_run_benign"), None)
    if fn is None:
        return {"ok": False, "为什么": "在 api.py 里**未读到** `_run_benign`（判据失效，别当通过）"}
    wired = set()
    for n in ast.walk(fn):                     # ① `kind == "X"` / `kind in ("X", …)`
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "kind":
            for c in n.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    wired.add(c.value)
                elif isinstance(c, (ast.Tuple, ast.List, ast.Set)):
                    for el in c.elts:
                        if isinstance(el, ast.Constant) and isinstance(el.value, str):
                            wired.add(el.value)
    mentioned = set()                          # ② 整个 api.py 里出现过的字符串常量
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            mentioned.add(n.value)
    reg = set(benign_names)
    hard_missing = sorted(reg - mentioned)     # ③ 真没着落 ⇒ 红
    soft = sorted((reg - wired) & mentioned)   # ② 出现过但判据没认出 ⇒ 只点名
    return {"ok": not hard_missing, "登记位（BENIGN）": len(reg),
            "已接线": len(reg & wired),
            "**真没着落（红）**": hard_missing, "真没着落位数": len(hard_missing),
            "着落待人工确认（不判红）": soft,
            "为什么": ("✅ 每一位都在 api.py 里有着落" if not hard_missing else
                    "🔴 **%d 位在整个 api.py 里一次都没出现**：%s ⇒ 调用会「报成功但什么都没干」"
                    % (len(hard_missing), "、".join(hard_missing[:8]))),
            "口径": "只认 `kind == \"X\"` 与 `kind in (…)`（AST，不扫文本）；"
            "在 api.py 出现过但判据没认出的**只点名、不判红**（可能有表驱动）；"
            "**UNIMPLEMENTED_CAPS 不算**（那些名字设计上就没有实现）"}


# 「空话分支」的判据词：分支**只**回这些，等于**没有实现**（只是骗过"有着落"那道闸）
_EMPTY_STATUS = ("not_implemented", "not_wired", "unimplemented", "stub", "todo", "占位", "未实现")


def empty_branch_check(benign_names: set, src_text: str | None = None) -> dict:
    """**空话分支**：位**有分支**、但分支体只是「什么都没做 / 只说未实现」。

    🔴 为什么要有这一条（2026-09-25）：上一轮我拒绝了一件事 ——
    「为了让闸变绿，在 `api.py` 加一个什么都不做的分支」。**光靠"有没有着落"拦不住这种手法**：
    加了空话分支后，"登记了没着落"那道闸就绿了，而能力**依然不存在** ⇒ **用自己的闸骗自己**。
    ⇒ 本判据专抓这种：分支体**只有** `return None` / 只回「未实现」字样的字面量。
    **只要分支里有一次真调用（import/函数调用），就不算空话**（宁松不枉）。
    """
    src_p = ROOT / "gbt_allinone" / "api.py"
    try:
        tree = ast.parse(src_text if src_text is not None
                         else src_p.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "为什么": "**未读到** api.py：%s" % str(e)[:70]}
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_run_benign"), None)
    if fn is None:
        return {"ok": False, "为什么": "在 api.py 里**未读到** `_run_benign`（判据失效，别当通过）"}
    suspects = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        kinds = set()
        for c in (node.test.comparators if isinstance(node.test, ast.Compare) else []):
            if isinstance(c, ast.Constant) and isinstance(c.value, str):
                kinds.add(c.value)
            elif isinstance(c, (ast.Tuple, ast.List, ast.Set)):
                kinds.update(e.value for e in c.elts
                             if isinstance(e, ast.Constant) and isinstance(e.value, str))
        kinds &= set(benign_names)
        if not kinds:
            continue
        body = [b for b in node.body if not isinstance(b, ast.Expr)
                or not isinstance(getattr(b, "value", None), ast.Constant)]   # 去 docstring
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        val = body[0].value
        if val is None:                                   # `return` / `return None`
            suspects.extend(sorted(kinds))
            continue
        if isinstance(val, ast.Constant) and val.value is None:
            suspects.extend(sorted(kinds))
            continue
        if isinstance(val, ast.Dict):                      # 只回一个"未实现"信封
            txt = ast.dump(val)
            if any(w in txt for w in _EMPTY_STATUS):
                suspects.extend(sorted(kinds))
    suspects = sorted(set(suspects))
    return {"ok": not suspects, "**空话分支（有分支但不干活）**": suspects, "位数": len(suspects),
            "为什么": ("✅ 没读到空话分支" if not suspects else
                    "🔴 **%d 位只有空话分支**（有分支、不干活）：%s ⇒ 这是**用空话骗闸**，不算实现"
                    % (len(suspects), "、".join(suspects[:6]))),
            "口径": "分支体**只**有 `return None` 或只回「未实现」字样 = 空话；"
            "**只要有一次真调用就不算**（宁松不枉）"}


def restore() -> dict:
    """从**已知良好副本**拷回（不重新生成）。副本不在 ⇒ 走恢复脚本。"""
    if not TARGET.exists() or TARGET.stat().st_size != (GOOD.stat().st_size if GOOD.exists() else -1):
        pass
    if GOOD.is_file():
        try:
            TARGET.chmod(0o666) if hasattr(TARGET, "chmod") else None
        except Exception:
            pass
        shutil.copyfile(GOOD, TARGET)
        src = str(GOOD.relative_to(ROOT))
    elif REBUILD.is_file():
        r = subprocess.run([sys.executable, "-X", "utf8", str(REBUILD)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180, cwd=str(ROOT))
        src = "重建脚本（%s）" % REBUILD.name
        if r.returncode != 0:
            return {"ok": False, "为什么": "重建脚本失败", "读数尾": (r.stderr or "")[-200:]}
    else:
        return {"ok": False, "为什么": "**已知良好副本与恢复脚本都不在** —— 不许瞎写"}
    v = check()
    return {"ok": v["ok"], "从哪来": src, "复原后": v}


def cmd_check(a) -> int:
    r = check()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print("%s 能力注册表：%s" % ("✅" if r["ok"] else "🔴", r.get("为什么")))
        if r.get("读数"):
            print("    %s" % json.dumps(r["读数"], ensure_ascii=False))
        if r.get("读数尾"):
            print("    读数尾：%s" % r["读数尾"])
        if r.get("复原命令"):
            print("    🔧 复原：%s" % r["复原命令"])
    return 0 if r["ok"] else 1


def cmd_restore(a) -> int:
    r = restore()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


PLANT_BROKEN = ('BENIGN_CAPS = {}\n'
                'DISABLED_CAPS = {}\n'
                'UNIMPLEMENTED_CAPS = {}\n'
                '\n'
                'def all_caps():\n'
                '    return []\n')


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 真数据：**硬口径**（可导入 · 不跌破下限 · DISABLED==0）——
 # 这里**不能**断言整体 `ok`：现在确实有 3 位"登记了没着落"（红判据⑥，真缺陷、要点名），
    #       那是**另一条判据**的事，不该把这条控制变成"因为那条红所以这条也红"。
    r = check()
    ck("**真数据：注册表可导入且未跌破下限/口径**",
       bool(r.get("读数")) and not any(w in str(r.get("为什么")) for w in ("跌破", "DISABLED_CAPS=")),
       str(r.get("为什么"))[:90])
    # ② 负控：**位数不对/空表 ⇒ 必须红**（判据要会咬）
    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "caps_registry.py"
        fake.write_text(PLANT_BROKEN, encoding="utf-8")
        rf = check(fake)
        ck("**负控：空表/跌破下限 ⇒ 必须红**", rf["ok"] is False, str(rf.get("为什么"))[:80])
 # ②b **正控：条数"变多"不许判红**（写死条数正是本仓反复吃的病；
    #     实测撞到另一个作者把注册表做到 171 位，旧判据当场误判成故障）
    with tempfile.TemporaryDirectory() as td:
        grow = Path(td) / "caps_registry.py"
        grow.write_text(
            "BENIGN_CAPS = {%s}\n"
            "DISABLED_CAPS = {}\n"
            "UNIMPLEMENTED_CAPS = {%s}\n"
            "\n"
            "def all_caps():\n"
            "    return ([{'name': k} for k in BENIGN_CAPS]\n"
            "            + [{'name': k} for k in UNIMPLEMENTED_CAPS])\n"
            % (", ".join('"b%d": {}' % i for i in range(MIN_BENIGN + 3)),
               ", ".join('"u%d": "x"' % i for i in range(MIN_UNIMPL))),
            encoding="utf-8")
        rg = check(grow)
 # 这条控制**只测"条数变多"这一件事**：漂移要被报出来，且**不许以"条数不符"判红**。
        #    （人造注册表里的名字当然没有接线 ⇒ ⑥ 那条红判据**该红**，与本控制无关。）
        ck("**正控：条数变多只报漂移、不以「条数不符」判红**（不许写死条数）",
           "多" in str(rg.get("条数漂移")) and "all_caps()=" not in str(rg.get("为什么")),
           "%s ｜ %s" % (str(rg.get("为什么"))[:60], rg.get("条数漂移")))
 # ②c **负控：DISABLED_CAPS 非 0 必须红**（Owner 2026-09-23 口径）
    with tempfile.TemporaryDirectory() as td:
        dis = Path(td) / "caps_registry.py"
        dis.write_text(
            "BENIGN_CAPS = {%s}\n"
            "DISABLED_CAPS = {'keylogger': {}, 'pentest': {}}\n"
            "UNIMPLEMENTED_CAPS = {%s}\n"
            "\n"
            "def all_caps():\n"
            "    return [{'name': k} for k in BENIGN_CAPS]\n"
            % (", ".join('"b%d": {}' % i for i in range(MIN_BENIGN)),
               ", ".join('"u%d": "x"' % i for i in range(MIN_UNIMPL))),
            encoding="utf-8")
        rd = check(dis)
        ck("**负控：DISABLED_CAPS 非 0 ⇒ 必须红**（Owner 口径）",
           rd["ok"] is False and "DISABLED" in str(rd.get("为什么")),
           str(rd.get("为什么"))[:80])
    # ③ 负控：**文件不存在 ⇒ 必须红**（不许把"没了"念成"没事"）
    rn = check(ROOT / "gbt_allinone" / "__根本没有这个文件__.py")
    ck("**负控：文件不存在 ⇒ 必须红**", rn["ok"] is False, str(rn.get("为什么"))[:60])
    # ④ 恢复源必须在（否则"复原命令"是空头支票）
    ck("**已知良好副本或恢复脚本至少有一个在**", GOOD.is_file() or REBUILD.is_file(),
       "good=%s rebuild=%s" % (GOOD.name if GOOD.is_file() else "缺",
                               REBUILD.name if REBUILD.is_file() else "缺"))
 # ⑤ **登记 vs 接线**：判据要会咬 —— 编一个"登记了但没接线"的名字，必须被点名
    d = dispatch_coverage({"count_words", "__绝对没有接线的假位__"})
    ck("**负控：登记了但没接线的名字必须被点名**",
       d.get("ok") is False and "__绝对没有接线的假位__" in (d.get("**真没着落（红）**") or []),
       str(d.get("为什么"))[:90])
    # ⑤b 正控：已接线的名字不许被误报
    d2 = dispatch_coverage({"count_words"})
    ck("**正控：已接线的名字不许被误报**", d2.get("ok") is True,
       "已接线 %s/%s" % (d2.get("已接线"), d2.get("登记位")))
 # ⑤c **注入源码**（原来这两条"未读到"分支只能靠 api.py 真坏掉 ⇒ **从没验过**）：
    #     ① 登记位在注入的源码里没着落 ⇒ 必须红
    d6 = dispatch_coverage({"__注入的假位__"},
                           'def _run_benign(kind, payload):\n    return 1\n')
    ck("**负控（注入源码）：登记位一次都没出现 ⇒ 必须红**",
       d6.get("ok") is False and "__注入的假位__" in (d6.get("**真没着落（红）**") or []),
       str(d6.get("为什么"))[:80])
    #     ② 注入源码里 `kind == "alpha"` ⇒ alpha 判已接线；`"beta" in kind` 只算"出现过"⇒ 不判红
    d7 = dispatch_coverage({"alpha", "beta"},
                           'def _run_benign(kind, payload):\n'
                           '    if kind == "alpha":\n        return 1\n'
                           '    if "beta" in kind:\n        return 2\n')
    ck("**正控（注入源码）：`kind ==` 判已接线 · 只出现过的不判红**",
       d7.get("ok") is True and d7.get("已接线") == 1
       and "beta" in (d7.get("着落待人工确认（不判红）") or []),
       "已接线 %s ｜ 待确认 %s" % (d7.get("已接线"), d7.get("着落待人工确认（不判红）")))
 # ⑤d **两条「未读到」分支**（源码读不到 / 源码里没有 `_run_benign`）—— 从没被走到过：
    d8 = dispatch_coverage(set(), 'def broken(:\n')
    ck("**负控：源码读不到 ⇒ 必须报『未读到』，不许当通过**",
       d8.get("ok") is False and "未读到" in str(d8.get("为什么")), str(d8.get("为什么"))[:70])
    d9 = dispatch_coverage({"x"}, 'def other():\n    return 1\n')
    ck("**负控：源码里没有 `_run_benign` ⇒ 必须报『判据失效，别当通过』**",
       d9.get("ok") is False and "别当通过" in str(d9.get("为什么")), str(d9.get("为什么"))[:70])
    # ⑤e 同型两条分支在 `empty_branch_check` 里也必须有控制（它早有注入口，却一直没人用）
    d10 = empty_branch_check(set(), 'def broken(:\n')
    ck("**负控（空话闸）：源码读不到 ⇒ 必须报『未读到』**",
       d10.get("ok") is False and "未读到" in str(d10.get("为什么")), str(d10.get("为什么"))[:70])
    d11 = empty_branch_check({"x"}, 'def other():\n    return 1\n')
    ck("**负控（空话闸）：源码里没有 `_run_benign` ⇒ 必须报『别当通过』**",
       d11.get("ok") is False and "别当通过" in str(d11.get("为什么")), str(d11.get("为什么"))[:70])
 # ⑥ **空话分支**：三条控制（两条负控 + 一条正控）—— 防"用空话骗闸"
    d3 = empty_branch_check({"fake_a"},
                            'def _run_benign(kind, payload):\n    if kind == "fake_a":\n        return None\n')
    ck("**负控：只有 `return None` 的分支必须被点名为空话**",
       d3.get("ok") is False and "fake_a" in (d3.get("**空话分支（有分支但不干活）**") or []),
       str(d3.get("为什么"))[:80])
    d4 = empty_branch_check({"fake_b"},
                            'def _run_benign(kind, payload):\n'
                            '    if kind == "fake_b":\n'
                            '        return {"status": "not_implemented"}\n')
    ck("**负控：只回「未实现」信封的分支也必须被点名**",
       d4.get("ok") is False and "fake_b" in (d4.get("**空话分支（有分支但不干活）**") or []),
       str(d4.get("为什么"))[:80])
    d5 = empty_branch_check({"fake_c"},
                            'def _run_benign(kind, payload):\n'
                            '    if kind == "fake_c":\n'
                            '        from . import real_mod\n'
                            '        return real_mod.run(payload)\n')
    ck("**正控：真干活的分支不许被误判**（宁松不枉）", d5.get("ok") is True,
       "空话 %s 位" % d5.get("位数"))
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="能力注册表哨兵（坏就叫 + 一条命令复原）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_check)
    sub.add_parser("restore").set_defaults(func=cmd_restore)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
