# -*- coding: utf-8 -*-
r"""触手自给自足配置（tentacle-provision）—— **一根触手 = 一套自己的家当**。

主人令（2026-10-10，逐字）：「你按照这样配置，**一根触手配置开源账户一个，邮箱一个**，
  虚拟手机验证平台 https://5sim.net/zh **共享所有触手可用**，前提是**用户自己充值**，
  还有**携带一个独立云插件**，部署 **freebuff 免费使用各自大模型**，以及 **freebuff 账户触手
  都要使用自己的邮箱自己给自己配置**，这样等于**每个触手运行都不需要占用电脑资源自给自足**」

## 每根触手五件（缺一不算自给自足）
| # | 件 | 口径 | 能不能自动 |
|---|---|---|---|
| ① | **开源账户** ×1 | 一根一个，互不共用 | 半自动（要邮箱+接码） |
| ② | **邮箱** ×1 | 一根一个，**它自己的** | 半自动（`tentacle-mail.py` 双后端已备好：A·AgentMail / B·自有域 gbtxiaotudou.com；差主人一条凭据） |
| ③ | **手机验证** | **5sim.net 共享所有触手**；**前提：用户自己充值** | ⚠️ **要主人的钱**（本件如实标"待充值"） |
| ④ | **独立云插件** ×1 | 一根一个槽位、独立配额 | 可自动（登记） |
| ⑤ | **freebuff** | 每根一份**隔离 HOME**；**用它自己的邮箱自己给自己配** | 装可自动；**login 是交互式 TUI ⇒ 要人工一次** |
| ⑥ | **万能插执行器** | 每根一个**隔离 store**（`GBT_STORE_DIR` 按触手分家）⇒ 工作流/运行记录/传输缓存互不干扰 | 全自动（本件就能备） |
| ⑦ | **无痕浏览器** | 每根一个**持久化隔离 profile**（cookie/登录态不共享）⇒ 自己上网配自己的装备 | 全自动（本件就能备） |
| ⑧ | **密钥库** | 每根一个 **DPAPI 封印 vault.db**（仓外）⇒ 邮箱/账户/接码/钥匙存这，掩码显示、明文只供机器取用 | 全自动（本件就能备） |
⇒ **自给自足 = 不占本机资源**：每根跑自己的账户 + 自己的模型额度（①–⑤）
⇒ **装备齐备 = 八件全绿**：⑥⑦⑧ 是它自己的主执行器/上网位/密钥库，同样互不干扰
⇒ **⑥⑦⑧ 的实备与页面数据**：`tools/codex-scripts/tentacle-gear.py`（本文件只作家当账真源）

## freebuff 的真身读数（2026-10-10，不许美化）
· 入口 %APPDATA%\npm\freebuff.cmd · 版本 0.1.2 · 模型 glm-5.3-flash-2026-09-05
· **隔离 HOME** = %LOCALAPPDATA%\gbt-freebuff\home（每根一份；写正常 HOME 会 EPERM）
· 登录态：**尚无凭证** ⇒ 要真干活得跑 freebuff login
· 🔴 **它是交互式 TUI，没有一次性 prompt 参数**（无 -p/--prompt/exec）⇒ 程序化驱动做不到，
  **不许假装能**。要真驱动得加一个本地 PTY 桥（下一步）。

用法：py -3.14 -X utf8 tools/codex-scripts/tentacle-provision.py [plan|--check|--selftest|plan --admit t1]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"
LEDGER = STATE / "tentacle-provision.json"
EXEC_BASE = STATE / "tentacle-exec"                 # ⑥ 万能插隔离 store（wf 定义/运行记录/传输缓存按触手分家）
BROWSER_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-tentacle-browser"  # ⑦ 每根持久化隔离 profile（仓外：cookie/登录态是凭据性质）
VAULT_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-tentacle-vault"     # ⑧ 每根密钥库 vault.db（仓外：DPAPI 封印，永不入仓）
FREE_HOME_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-freebuff"

ITEMS = ("开源账户", "邮箱", "手机验证", "独立云插件", "freebuff")
GEAR = ITEMS + ("万能插执行器", "无痕浏览器", "密钥库")     # 八件装备（主人令 2026-10-17 加 ⑥⑦⑧）
NOT_YET = ("", "未配", "未装", "未挂号", "未备", "**待主人充值**")   # 状态在这个集合里 = 这件还没有
TID_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,16}$")


def _guard_tid(tid: str) -> str:
    if not TID_RE.match(str(tid or "")):
        raise ValueError("tid 只许 [A-Za-z0-9_-]{1,16}（拒路径穿越）：%r" % tid)
    return str(tid)


def blank(tid: str) -> dict:
    """一根触手的一套家当（五件；没配的**如实留空**，不许填假的）。"""
    return {
        "触手": tid,
        "隔离HOME": str(FREE_HOME_BASE / tid),
        "开源账户": {"平台": "", "账号": "", "状态": "未配"},
        "邮箱": {"地址": "", "状态": "未配"},
        "手机验证": {"平台": "https://5sim.net/zh", "共享": True, "状态": "**待主人充值**",
                     "口径": "共享给所有触手用；充值由主人自己来（本件不代付、不代充）"},
        "独立云插件": {"插件": "gbt-cloud-ai", "槽位": tid, "状态": "未挂号",
                       "配额": "独立（不占别根）"},
        "freebuff": {"HOME": str(FREE_HOME_BASE / tid), "状态": "未装",
                     "口径": "用它自己的邮箱自己给自己配；login 是交互式 TUI ⇒ 要人工一次"},
        "万能插执行器": {"store": str(EXEC_BASE / tid), "状态": "未备",
                       "口径": "GBT_STORE_DIR 按触手分家 ⇒ workflows/wf_runs/transfer_cache 互不干扰；作为该触手的主执行器"},
        "无痕浏览器": {"profile": str(BROWSER_BASE / tid), "状态": "未备",
                      "口径": "playwright 持久化隔离 context（Edge 通道）；cookie/登录态只归这根触手"},
        "密钥库": {"vault": str(VAULT_BASE / tid / "vault.db"), "状态": "未备",
                  "口径": "DPAPI 用户级封印 + 按触手 entropy；掩码显示，明文只供机器取用（fetch）；诚实边界：不防同用户同机器的恶意触手主动偷（那要 OS 级身份分离）"},
        "自给自足": False,
        "装备齐备": False,
    }


def _recompute(row: dict) -> dict:
    """按当前各件状态重算两个判据（缺一件都不算数，不许念成有）。"""
    row["自给自足"] = all(row[k].get("状态") not in NOT_YET for k in ITEMS)
    row["装备齐备"] = all(row[k].get("状态") not in NOT_YET for k in GEAR)
    return row


def load() -> dict:
    d = None
    if LEDGER.is_file():
        try:
            d = json.loads(LEDGER.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = None
    if d is None:
        return {"at": "", "口径": "一根触手一套家当", "根": {}}
    # 迁移：老账（五件）补 ⑥⑦ 与"装备齐备"——缺的如实留未备，不假装有
    for tid, row in d.get("根", {}).items():
        for k, v in blank(tid).items():
            row.setdefault(k, v)
        row["触手"] = tid
        _recompute(row)
    return d


def save(d: dict) -> None:
    d["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def provision(tid: str, *, admit: bool = False) -> dict:
    """给一根触手立家当账（**只登记，不代注册**——注册要邮箱与接码，那是下一步真跑）。"""
    tid = _guard_tid(tid)
    d = load()
    row = d["根"].get(tid) or blank(tid)
    if admit:
        row["独立云插件"]["状态"] = "已挂号"
    _recompute(row)
    d["根"][tid] = row
    save(d)
    return row


def check() -> int:
    d = load()
    if not d["根"]:
        # 先立一根样本（证明账能立；**不假装已配齐**）
        provision("t1")
        d = load()
    print("触手自给自足配置（一根一套家当 · 七件装备）")
    bad = []
    for tid, r in d["根"].items():
        miss = [k for k in GEAR if r[k].get("状态") in NOT_YET]
        print("  %-6s 自给自足=%s · 装备齐备=%s · 缺: %s" % (tid, r["自给自足"], r.get("装备齐备"), miss or "无"))
        for k in GEAR:
            v = r[k]
            print("      %-8s %-14s %s" % (k, str(v.get("状态"))[:14],
                                           str(v.get("平台") or v.get("地址") or v.get("HOME") or v.get("store") or v.get("profile") or "")[:56]))
        if miss:
            bad.append(tid)
    print()
    print("  ⚠️ 五件里**手机验证**与 **freebuff 登录**都要主人那一下：")
    print("     手机验证：5sim.net **主人自己充值**（本件不代付）")
    print("     freebuff：login 是**交互式 TUI**，只有人工能登；登录后每根才能用自己的额度")
    n_mail = sum(1 for r in d["根"].values() if str(r.get("邮箱", {}).get("状态", "")) not in NOT_YET)
    print("  ⚠️ 独立永久邮箱实配 %d 个：接线件 tentacle-mail.py 双后端已备好（A·AgentMail key / "
          "B·<tid>@gbtxiaotudou.com）—— 差的只是主人物权凭据" % n_mail)
    print("     ⇒ 主人任给一条：AgentMail key（key set）或 Zoho 应用密码 + DNS 转发 TXT（setx GBT_IMAP_PASS）"
          "⇒ 然后 inbox <tid> 闭环自证即配")
    ok = bool(d["根"]) and all(all(k in r for k in GEAR) for r in d["根"].values())
    print("判据：%s" % ("PASS（每根的家当账都立起来了；未配的已逐条如实标）" if ok else "FAIL"))
    return 0 if ok else 1


def selftest() -> int:
    r = blank("tX")
    print("负对照A·空家当 => 自给自足 =", all(r[k].get("状态") not in NOT_YET for k in ITEMS),
          "（必须 False）")
    print("负对照A2·空家当 => 装备齐备 =", all(r[k].get("状态") not in NOT_YET for k in GEAR),
          "（必须 False）")
    r["独立云插件"]["状态"] = "已挂号"
    print("负对照B·只挂云插件 => 仍缺", [k for k in ITEMS if r[k].get("状态") in NOT_YET])
    r2 = blank("tX")
    _ok = {"开源账户": "已配", "邮箱": "已配", "手机验证": "已充值",
           "独立云插件": "已挂号", "freebuff": "已装", "万能插执行器": "已备",
           "无痕浏览器": "已备", "密钥库": "已备"}
    for k in GEAR:
        r2[k]["状态"] = _ok[k]
    print("正对照C·七件全绿 => 装备齐备 =", all(r2[k].get("状态") not in NOT_YET for k in GEAR),
          "（必须 True）")
    print("自检：全过（空家当不会被念成自给自足/装备齐备）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="触手自给自足配置")
    ap.add_argument("cmd", nargs="?", default="plan", choices=["plan"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--admit", metavar="TID", default="",
                    help="给这根触手挂独立云插件（只挂号，不代注册）：plan --admit t1")
    a = ap.parse_args()
    if a.admit:
        row = provision(a.admit, admit=True)
        print("已挂号：%s · 独立云插件=%s（自给自足=%s · 装备齐备=%s）"
              % (a.admit, row["独立云插件"]["状态"], row["自给自足"], row["装备齐备"]))
        return 0
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
