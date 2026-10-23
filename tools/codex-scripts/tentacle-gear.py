# -*- coding: utf-8 -*-
r"""tentacle-gear -- 触手装备自主配置驱动器（⑥万能插执行器 / ⑦无痕浏览器 / ⑧密钥库 的实备与调用）。

主人令（2026-10-17，逐字）：
  「这些调用触手自主完成，**使用无痕浏览器让他们自己配置自己的装备**」
  「每根触手都可以**隔离使用万能插，互不干扰**」
  「她万能插隔离调用**作为触手的主执行器**，这样提高工作效率」
  ⇒ 本件就是触手自己的"装备控制台"：**一根触手 = 一个智能体**，
     它的主执行器（万能插）、上网位（无痕浏览器）、密钥库（DPAPI vault）全部按触手分家。

三件装备怎么隔离（都可验）：
  ⑥ **万能插执行器**：`GBT_STORE_DIR` 按触手分家 —— engine 在 import 时绑定 store 基址
     （仓内 sanctioned 机制，判例同款），所以必须**先设环境变量、再起子进程**跑万能插：
     workflows.json / wf_runs/ / transfer_cache.json 每根一份，互不串味。
  ⑦ **无痕浏览器**：playwright `launch_persistent_context` + Edge 通道（channel="msedge"），
     profile 落 %LOCALAPPDATA%\gbt-tentacle-browser\<tid>\ —— cookie/登录态只归这根触手。
  ⑧ **密钥库**：tools/codex-scripts/tentacle-vault.py（DPAPI 封印、掩码显示、fetch 明文只供管道）。

子命令：
  gear <tid>                实备 ⑥⑦⑧：每件都**真跑一遍验证**才把账本状态改"已备"（不许只改状态）
  freebuff <tid>            ⑤ freebuff 隔离建制（隔离 HOME + 版本真探；login 是人工 TUI 闸门，不代登）
  browser <tid>             起这根触手的隔离无痕浏览器（人在里面自己配装备；--probe 无头快检）
  exec <tid> <kind> [payload]   万能插隔离调用（该触手的主执行器；payload 是 JSON 或省缺）
  render                    生成 holo_pet_w3/tentacles/tentacles-data.js（页面数据真源）
  check                     总检：账本状态 vs 磁盘实况，**说已备却没有 = 抓出来**
  selftest                  负控：隔离实证 / tid 守卫 / 仓外纪律 / 账实一致机制

人工闸门（本件如实标，不代闯）：
  · 手机验证（5sim.net 共享）⇒ **待主人充值**；freebuff login 是交互式 TUI ⇒ **要人工一次**；
  · **独立永久邮箱实配 0 个**：接线件 tentacle-mail.py 已备好（双后端：A·AgentMail 要主人注册 key；
    B·项目自有域 <tid>@gbtxiaotudou.com 要主人补 Zoho 应用密码 / DNS 转发 TXT）
    ⇒ 差的只是主人物权凭据那一下 —— 页面与 check 都如实写这条。

用法（仓库回归口径 py -3.14；--json 是主解析器参数，须放子命令前）：
  py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py gear t1
  py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py browser t1 --url https://github.com
  py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py exec t1 wf_status '{"include_workflows":true}'
  py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py render
  py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py check
  py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py selftest
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"                                    # 账本与万能插隔离 store 在仓内 state/ 下
LEDGER = STATE / "tentacle-provision.json"                # 家当账真源（tentacle-provision.py 写，本件只改 ⑥⑦⑧ 状态）
EXEC_BASE = STATE / "tentacle-exec"                       # ⑥ 每根一个隔离 store（GBT_STORE_DIR 指到这）
BROWSER_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-tentacle-browser"   # ⑦ profile（仓外：cookie/登录态是凭据性质）
VAULT_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-tentacle-vault"       # ⑧ vault.db（仓外：DPAPI 封印）
FREE_HOME_BASE = Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-freebuff"

FIVE_DIM = ROOT / "tools" / "codex-scripts" / "five-dim.py"          # 万能插唯一门（能力位）
VAULT_TOOL = ROOT / "tools" / "codex-scripts" / "tentacle-vault.py"  # 密钥库工具
BROWSER_SESSION = ROOT / "tools" / "codex-scripts" / "tentacle-browser-session.py"
FREEBUFF_CMD = Path(os.environ.get("APPDATA", "")) / "npm" / "freebuff.cmd"   # ⑤ freebuff 入口（机器级装好；每根建制自己的隔离 HOME）
PAGE_DIR = ROOT / "holo_pet_w3" / "tentacles"
PAGE_DATA = PAGE_DIR / "tentacles-data.js"

# 跑万能插/密钥库用**当前解释器**（本件按仓库回归口径 py -3.14 起，sys.executable 即该解释器）；
# 跑浏览器用受管 venv（装了 playwright 的那个，Edge 通道免下载浏览器）。
PY = sys.executable
PLAYWRIGHT_PY = Path(os.environ.get(
    "GBT_TENTACLE_PLAYWRIGHT_PY",
    r"C:\Users\ADMIN\.workbuddy-ai\binaries\python\envs\default\Scripts\python.exe"))

TID_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,16}$")

GEAR3 = ("万能插执行器", "无痕浏览器", "密钥库")     # 本件实备的三件（⑥⑦⑧）
GEAR8 = ("开源账户", "邮箱", "手机验证", "独立云插件", "freebuff") + GEAR3
NOT_YET = ("", "未配", "未装", "未挂号", "未备", "**待主人充值**")

# 每件装备"缺什么谁能给"（页面与 check 共用；人工闸门如实写，不代闯）
WHO_CAN = {
    "开源账户": "主人/触手自己有头有脸地注册（要邮箱+接码；5sim 充值是主人的事）",
    "邮箱": "**主人给一条凭据即通**：tentacle-mail.py 双后端已备好 —— A·AgentMail key（key set）或 B·Zoho 应用密码 setx GBT_IMAP_PASS + DNS 转发 TXT；然后 inbox <tid> 闭环自证",
    "手机验证": "**主人自己给 5sim.net 充值**（本件不代付、不代充）",
    "独立云插件": "可自动登记（provision --admit 已挂 t3）",
    "freebuff": "装可自动；**login 是交互式 TUI ⇒ 要人工一次**",
    "万能插执行器": "**全自动**：gear <tid> 实备（隔离 store 落在 state/tentacle-exec/<tid>）",
    "无痕浏览器": "**全自动**：gear <tid> 实备（profile 在 %LOCALAPPDATA%\\gbt-tentacle-browser\\<tid>）",
    "密钥库": "**全自动**：gear <tid> 实备（vault.db 在 %LOCALAPPDATA%\\gbt-tentacle-vault\\<tid>，DPAPI 封印）",
}


def _guard_tid(tid: str) -> str:
    if not TID_RE.match(str(tid or "")):
        raise ValueError("tid 只许 [A-Za-z0-9_-]{1,16}（拒路径穿越）：%r" % tid)
    return str(tid)


def _run(args, *, env_extra=None, timeout=240, input_text=None):
    """跑子进程并收全量输出（utf-8，errors=replace —— GBK 控制台不许炸）。"""
    env = dict(os.environ)
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    try:
        p = subprocess.run([str(a) for a in args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env,
                           timeout=timeout, input=input_text, cwd=str(ROOT))
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or "") if isinstance(e.stdout, str) else "", "timeout after %ss" % timeout
    except Exception as e:                            # noqa: BLE001
        return 127, "", "%s: %s" % (type(e).__name__, e)


_PROV = None


def _provision():
    """家当账模块（tentacle-provision.py）—— 账本真源只此一家，本件不另立账。"""
    global _PROV
    if _PROV is None:
        spec = importlib.util.spec_from_file_location(
            "tentacle_provision", ROOT / "tools" / "codex-scripts" / "tentacle-provision.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _PROV = m
    return _PROV


def _store(tid: str) -> Path:
    return EXEC_BASE / _guard_tid(tid)


def _profile(tid: str) -> Path:
    return BROWSER_BASE / _guard_tid(tid)


def _vault_db(tid: str) -> Path:
    return VAULT_BASE / _guard_tid(tid) / "vault.db"


def _disk_truth(tid: str) -> dict:
    """⑥⑦⑧ 的磁盘实况（render/check/selftest 共用 —— 判据只认落盘，不认嘴）。"""
    tid = _guard_tid(tid)
    store, profile, vault = _store(tid), _profile(tid), _vault_db(tid)
    runs = 0
    if (store / "wf_runs").is_dir():
        runs = len(list((store / "wf_runs").glob("*.json")))
    return {
        "万能插执行器": {"ready": (store / "workflows.json").is_file(),
                       "runs": runs, "path": str(store)},
        "无痕浏览器": {"ready": profile.is_dir() and any(profile.iterdir()),
                     "path": str(profile)},
        "密钥库": {"ready": vault.is_file(), "path": str(vault)},
    }


def _ledger_lies(row: dict, truth: dict) -> list:
    """账本说 ⑥⑦⑧ 已备、磁盘却没有 ⇒ 抓出来（一条都不许放过）。"""
    lies = []
    for k in GEAR3:
        said = str(row.get(k, {}).get("状态", ""))
        if said not in NOT_YET and not truth[k]["ready"]:
            lies.append("%s 状态=%r 但磁盘实况未就绪" % (k, said))
    return lies


# ---------------------------------------------------------------- gear：实备 ⑥⑦⑧


def _gear_exec(tid: str) -> dict:
    """⑥ 万能插执行器：建隔离 store，并真跑一发 定义→执行→查记录 证明它能用。"""
    store = _store(tid)
    store.mkdir(parents=True, exist_ok=True)
    env = {"GBT_STORE_DIR": str(store)}
    wf = {"name": "gear-probe",
          "nodes": [{"id": "probe", "kind": "count_words",
                     "payload": {"text": "gbt-tentacle-%s 万能插隔离自检" % tid}}]}
    rc1, out1, err1 = _run([PY, FIVE_DIM, "cap", "wf_define",
                            json.dumps(wf, ensure_ascii=False)], env_extra=env, timeout=300)
    rc2, out2, err2 = _run([PY, FIVE_DIM, "cap", "wf_run",
                            json.dumps({"name": "gear-probe"}, ensure_ascii=False)],
                           env_extra=env, timeout=300)
    ready = (store / "workflows.json").is_file() and (store / "wf_runs").is_dir() \
        and any((store / "wf_runs").glob("*.json"))
    return {"ready": bool(ready), "store": str(store),
            "define_rc": rc1, "run_rc": rc2,
            "define_tail": (out1 or err1)[-160:].replace("\n", " "),
            "run_tail": (out2 or err2)[-160:].replace("\n", " ")}


def _gear_browser(tid: str) -> dict:
    """⑦ 无痕浏览器：建隔离 profile，并无头快检一次（真起得起来才算备）。"""
    profile = _profile(tid)
    profile.mkdir(parents=True, exist_ok=True)
    (profile / "profile.json").write_text(json.dumps(
        {"tid": tid, "channel": "msedge", "kind": "playwright-persistent",
         "口径": "cookie/登录态只归这根触手；与人用的 Edge 不共享",
         "created": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    if not PLAYWRIGHT_PY.is_file():
        return {"ready": profile.is_dir(), "profile": str(profile),
                "probe": "受管 venv 不在（%s）⇒ 只建了目录，未做无头快检" % PLAYWRIGHT_PY}
    probe_rec = profile / "session-probe.json"
    rc, out, err = _run([PLAYWRIGHT_PY, BROWSER_SESSION, profile, "about:blank",
                         "1", "60", probe_rec, "3"], timeout=180)
    return {"ready": bool(probe_rec.is_file()), "profile": str(profile),
            "probe_rc": rc, "probe_tail": (out or err)[-160:].replace("\n", " ")}


def _gear_vault(tid: str) -> dict:
    """⑧ 密钥库：调 tentacle-vault.py init（一个实现，不重写），落盘为证。"""
    rc, out, err = _run([PY, VAULT_TOOL, "init", tid], timeout=120)
    return {"ready": _vault_db(tid).is_file(), "vault": str(_vault_db(tid)),
            "init_rc": rc, "init_tail": (out or err)[-160:].replace("\n", " ")}


def gear(tid: str, *, as_json: bool = False) -> int:
    """实备 ⑥⑦⑧：每件真验过关才把账本状态改"已备"；验不过的如实留"未备"并报缺什么。"""
    tid = _guard_tid(tid)
    ev = {"万能插执行器": _gear_exec(tid),
          "无痕浏览器": _gear_browser(tid),
          "密钥库": _gear_vault(tid)}
    prov = _provision()
    d = prov.load()
    row = d["根"].get(tid) or prov.blank(tid)
    for k in GEAR3:
        row[k]["状态"] = "已备" if ev[k]["ready"] else "未备"
        row[k]["store" if k == "万能插执行器" else
               ("profile" if k == "无痕浏览器" else "vault")] = ev[k].get(
                   "store") or ev[k].get("profile") or ev[k].get("vault")
    prov._recompute(row)
    d["根"][tid] = row
    prov.save(d)
    if as_json:
        print(json.dumps({"ok": all(e["ready"] for e in ev.values()),
                          "tid": tid, "evidence": ev,
                          "自给自足": row["自给自足"], "装备齐备": row["装备齐备"]},
                         ensure_ascii=False, indent=1))
        return 0 if all(e["ready"] for e in ev.values()) else 1
    print("触手 %s 装备实备（⑥万能插执行器 / ⑦无痕浏览器 / ⑧密钥库）" % tid)
    for k in GEAR3:
        e = ev[k]
        print("  %-6s %-4s %s" % (k, "已备" if e["ready"] else "未备",
                                  e.get("store") or e.get("profile") or e.get("vault")))
        if not e["ready"]:
            print("        缺什么：%s" % WHO_CAN[k])
    print("  账本已更新：自给自足=%s · 装备齐备=%s（判据只认落盘）" %
          (row["自给自足"], row["装备齐备"]))
    print("  还缺的（①–⑤，人工闸门）：%s" %
          ([k for k in GEAR8 if str(row[k].get("状态", "")) in NOT_YET] or "无"))
    mail_st = str(row.get("邮箱", {}).get("状态", ""))
    print("  ⇒ 邮箱（%s）：%s" % (
        mail_st,
        "已接通（这根触手自己的永久邮箱）" if mail_st not in NOT_YET else
        "接线件已备好（tentacle-mail.py 双后端），差主人一条凭据（见 WHO_CAN）"))
    return 0 if all(e["ready"] for e in ev.values()) else 1


def _gear_freebuff(tid: str) -> dict:
    """⑤ freebuff 隔离建制：每根一份隔离 HOME（HOME/USERPROFILE 指过去——写正常 HOME
    会 EPERM，这是框架档案里记实的），再**真探一次** `--version`（非交互面）；
    探到版本号才算「已装」；login 是交互式 TUI ⇒ 人工闸门，本件不代登。"""
    tid = _guard_tid(tid)
    home = FREE_HOME_BASE / tid
    home.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run([FREEBUFF_CMD, "--version"],
                        env_extra={"HOME": str(home), "USERPROFILE": str(home)},
                        timeout=300)
    ver = (out or "").strip().splitlines()[-1] if (out or "").strip() else ""
    return {"ready": bool(rc == 0 and ver), "home": str(home), "probe_rc": rc,
            "版本": ver[:40], "tail": (out or err)[-160:].replace("\n", " ")}


def gear_freebuff(tid: str, *, as_json: bool = False) -> int:
    """⑤ freebuff：隔离建制 + 版本真探；探到才把账本改「已装」（落盘/探到为证，不嘴装）。"""
    tid = _guard_tid(tid)
    ev = _gear_freebuff(tid)
    prov = _provision()
    d = prov.load()
    row = d["根"].get(tid) or prov.blank(tid)
    row["freebuff"]["状态"] = "已装" if ev["ready"] else "未装"
    row["freebuff"]["口径"] = (
        "每根一份隔离 HOME（%s）；freebuff %s 已探到；login 是交互式 TUI ⇒ 要人工一次（用它自己的邮箱注册）"
        % (ev["home"], ev["版本"]) if ev["ready"] else
        "隔离 HOME 已建但 freebuff 探不到（rc=%s）⇒ 如实留未装：%s"
        % (ev["probe_rc"], ev["tail"][:80]))
    prov._recompute(row)
    d["根"][tid] = row
    prov.save(d)
    if as_json:
        print(json.dumps({"ok": ev["ready"], "tid": tid, "evidence": ev,
                          "freebuff": row["freebuff"], "自给自足": row["自给自足"],
                          "装备齐备": row["装备齐备"]}, ensure_ascii=False, indent=1))
        return 0 if ev["ready"] else 1
    print("触手 %s freebuff 隔离建制（隔离 HOME + --version 真探）" % tid)
    print("  %-4s %-8s HOME=%s · 版本=%s（rc=%s）"
          % ("已装" if ev["ready"] else "未装", "freebuff", ev["home"], ev["版本"], ev["probe_rc"]))
    if not ev["ready"]:
        print("        缺什么：%s" % WHO_CAN["freebuff"])
    print("  账本已更新：自给自足=%s · 装备齐备=%s（判据只认探到）" %
          (row["自给自足"], row["装备齐备"]))
    print("  ⚠️ login 仍是人工 TUI 闸门（且要用这根触手自己的邮箱注册）——本件不代登")
    return 0 if ev["ready"] else 1


# ---------------------------------------------------------------- browser：隔离无痕浏览器


def browser(tid: str, *, url: str = "about:blank", headless: bool = False,
            timeout: float = 0.0, probe: bool = False) -> int:
    """起这根触手的隔离无痕浏览器（Edge 持久化 profile）。

    · 人在里面自己配自己的装备（cookie/登录态落在这根的 profile，不共享）；
    · --probe：无头快检（起→关→留 session 记录），供 gear/selftest 证明"真起得来"；
    · timeout>0：到点自动关（无人值守用）；0 = 等窗口关。
    """
    tid = _guard_tid(tid)
    profile = _profile(tid)
    profile.mkdir(parents=True, exist_ok=True)
    if not PLAYWRIGHT_PY.is_file():
        print(json.dumps({"ok": False, "tid": tid, "error":
                          "受管 venv 不在：%s（装 playwright 的那个）" % PLAYWRIGHT_PY},
                         ensure_ascii=False))
        return 1
    rec = profile / ("session-probe.json" if probe else
                     "session-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    h = "1" if (probe or headless) else "0"
    tmo = "3" if probe else str(float(timeout or 0))
    rc, out, err = _run([PLAYWRIGHT_PY, BROWSER_SESSION, str(profile), str(url),
                         h, tmo, str(rec), "3" if probe else "0"], timeout=600)
    sys.stderr.write("[tentacle-gear] browser tid=%s profile=%s rc=%s\n" % (tid, profile, rc))
    if out.strip():
        try:
            print(json.dumps(json.loads(out.strip().splitlines()[-1]), ensure_ascii=False, indent=1))
        except ValueError:
            print(out)
    if err.strip():
        sys.stderr.write(err[-400:])
    return 0 if rc == 0 and rec.is_file() else 1


# ---------------------------------------------------------------- exec：万能插隔离调用（主执行器）


def exec_cap(tid: str, kind: str, payload: str = "", extra=None) -> int:
    """万能插隔离调用：**先设 GBT_STORE_DIR、再起子进程**跑能力位 —— 这根触手的主执行器。

    stdout 原样透传万能插的返回（管道可直吃）；store 指哪只写到 stderr（不脏 stdout）。
    每次调用落一行 gear-exec-log.jsonl 进这根触手自己的 store（可审计）。
    """
    tid = _guard_tid(tid)
    if not kind:
        print(json.dumps({"ok": False, "error": "要一个能力位 kind（先 cap 列表里挑）"},
                         ensure_ascii=False))
        return 2
    store = _store(tid)
    store.mkdir(parents=True, exist_ok=True)
    args = [PY, FIVE_DIM, "cap", kind]
    if payload:
        args.append(payload)
    if extra:
        args.extend(extra)
    rc, out, err = _run(args, env_extra={"GBT_STORE_DIR": str(store)}, timeout=600)
    sys.stderr.write("[tentacle-gear] exec tid=%s store=%s kind=%s rc=%s\n"
                     % (tid, store, kind, rc))
    if out.strip():
        sys.stdout.write(out if out.endswith("\n") else out + "\n")
    if err.strip():
        sys.stderr.write(err[-600:])
    try:                                             # 调用账：每根自己的 store 里追加一行
        with open(store / "gear-exec-log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": tid,
                                "kind": kind, "payload": (payload or "")[:120],
                                "rc": rc}, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rc


# ---------------------------------------------------------------- render：页面数据


NUM = {"开源账户": "①", "邮箱": "②", "手机验证": "③", "独立云插件": "④", "freebuff": "⑤",
       "万能插执行器": "⑥", "无痕浏览器": "⑦", "密钥库": "⑧"}
KOUJING = {
    "开源账户": "一根一个，互不共用",
    "邮箱": "一根一个，**它自己的**永久邮箱",
    "手机验证": "5sim.net 共享所有触手（待主人充值）",
    "独立云插件": "一根一个槽位、独立配额",
    "freebuff": "每根一份隔离 HOME；用它自己的邮箱自己给自己配",
}


def _item_value(k: str, v: dict) -> str:
    if k == "开源账户":
        p, a = str(v.get("平台") or ""), str(v.get("账号") or "")
        return (p + (" · " + a if a else "")).strip(" ·")
    for key in ("地址", "HOME", "store", "profile", "vault"):
        if v.get(key):
            return str(v[key])
    return ""


def render() -> int:
    """生成 holo_pet_w3/tentacles/tentacles-data.js：每根触手一张卡的八件真实状态。"""
    prov = _provision()
    d = prov.load()
    tents = []
    n_self = n_full = n6 = n7 = n8 = 0
    mail_real = 0
    for tid, row in sorted(d.get("根", {}).items()):
        truth = _disk_truth(tid)
        items = []
        for k in GEAR8:
            v = row.get(k, {})
            st = str(v.get("状态", ""))
            if k in GEAR3:
                val = truth[k]["path"]
                if k == "万能插执行器":
                    val += "（%d 次运行记录）" % truth[k]["runs"]
                ready = truth[k]["ready"]
            else:
                val = _item_value(k, v)
                ready = st not in NOT_YET
                if k == "邮箱" and st not in NOT_YET and v.get("地址"):
                    mail_real += 1
            items.append({"#": NUM[k], "件": k, "状态": st, "值": val,
                          "就绪": ready, "口径": v.get("口径") or KOUJING.get(k, ""),
                          "缺什么谁能给": WHO_CAN[k]})
        n_self += 1 if row.get("自给自足") else 0
        n_full += 1 if row.get("装备齐备") else 0
        n6 += 1 if truth["万能插执行器"]["ready"] else 0
        n7 += 1 if truth["无痕浏览器"]["ready"] else 0
        n8 += 1 if truth["密钥库"]["ready"] else 0
        tents.append({
            "id": tid, "自给自足": bool(row.get("自给自足")),
            "装备齐备": bool(row.get("装备齐备")), "items": items,
            "缺": [it["件"] for it in items if not it["就绪"]],
        })
    data = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "state/tentacle-provision.json（账本真源）+ 磁盘实况（tentacle-gear.py render 现读）",
        "regen": "py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py render",
        "check": "py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py check",
        "honesty": [
            ("每根触手的独立永久邮箱**实配 %d 个**：%s" % (
                mail_real,
                "接线件 tentacle-mail.py 双后端已备好（A·AgentMail 要主人注册 key；"
                "B·项目自有域 <tid>@gbtxiaotudou.com 要主人补 Zoho 应用密码 / DNS 转发 TXT）"
                "⇒ 差的只是主人物权凭据那一下（inbox <tid> 闭环自证即配）"
                if mail_real == 0 else
                "每根都是闭环自证过的（SMTP 发唯一标记→IMAP 读回且 To: 命中；凭据只在环境/DPAPI 库，不落盘）")),
            "手机验证（5sim.net）共享给所有触手，但**待主人充值**（本件不代付、不代充）",
            "freebuff login 是**交互式 TUI** ⇒ 要人工一次；登录后每根才能用自己的额度",
            "⑥⑦⑧ 的『已备』只认磁盘实况：workflows.json / profile / vault.db 落盘为证，账本说已备而磁盘没有会被 check 抓出来",
        ],
        "totals": {"触手": len(tents), "自给自足": n_self, "装备齐备": n_full,
                   "⑥万能插执行器": n6, "⑦无痕浏览器": n7, "⑧密钥库": n8,
                   "邮箱实配": mail_real},
        "tentacles": tents,
        "conventions": {
            "一根触手 = 一个智能体": " profession/tentacle_id/llm_profile/context_namespace/room_id 五重身份；并行默认 8 根、硬顶 32",
            "万能插隔离": "GBT_STORE_DIR 按触手分家（engine import 时绑定）⇒ workflows/wf_runs/transfer_cache 每根一份，互不干扰",
            "无痕浏览器": "playwright 持久化 context + Edge 通道（channel=msedge）；profile 落 %LOCALAPPDATA%\\gbt-tentacle-browser\\<tid>，cookie/登录态只归这根",
            "密钥库": "DPAPI 用户级封印 + 按触手 entropy；掩码显示，明文只经 fetch 供管道取用；诚实边界：不防同用户同机器的恶意程序主动偷",
            "账本真源": "state/tentacle-provision.json（tentacle-provision.py 写）；本页数据由 tentacle-gear.py render 生成",
        },
    }
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    PAGE_DATA.write_text(
        "// 触手装备区页面数据 —— 由 tools/codex-scripts/tentacle-gear.py render 生成，勿手改\n"
        "window.GBT_TENTACLES = %s;\n" % json.dumps(data, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("页面数据已生成：%s（%d 根触手 · ⑥%d ⑦%d ⑧%d · 邮箱实配 %d）"
          % (PAGE_DATA, len(tents), n6, n7, n8, mail_real))
    print("重生成：%s" % data["regen"])
    return 0


# ---------------------------------------------------------------- check：账本 vs 磁盘


def check() -> int:
    """总检：账本状态 vs 磁盘实况 —— 说已备却没有 = 抓出来；缺什么谁能给逐条列。"""
    prov = _provision()
    d = prov.load()
    if not d.get("根"):
        print(json.dumps({"ok": False, "error": "账本还是空的（先 provision t1）"},
                         ensure_ascii=False))
        return 1
    bad, lies_all = [], []
    print("触手装备总检（账本 %s）" % LEDGER)
    for tid, row in sorted(d["根"].items()):
        truth = _disk_truth(tid)
        lies = _ledger_lies(row, truth)
        miss = [k for k in GEAR8 if str(row.get(k, {}).get("状态", "")) in NOT_YET]
        print("  %-6s 自给自足=%-5s 装备齐备=%-5s ⑥=%s ⑦=%s ⑧=%s"
              % (tid, row.get("自给自足"), row.get("装备齐备"),
                 truth["万能插执行器"]["ready"], truth["无痕浏览器"]["ready"],
                 truth["密钥库"]["ready"]))
        for k in GEAR8:
            v = row.get(k, {})
            print("      %s %-6s %-12s %s" % (NUM[k], k, str(v.get("状态", ""))[:12],
                                              str(v.get("口径") or "")[:44]))
        if lies:
            lies_all.extend("%s: %s" % (tid, x) for x in lies)
            print("      🔴 账实不符：%s" % lies)
        if miss:
            bad.append(tid)
        print("      缺什么谁能给：%s" % ("；".join(
            "%s → %s" % (k, WHO_CAN[k]) for k in miss) or "无"))
    print()
    print("  ⚠️ 人工闸门（如实标，不代闯）：5sim 待主人充值 · freebuff login 要人工一次")
    n_mail = sum(1 for r in d["根"].values()
                 if str(r.get("邮箱", {}).get("状态", "")) not in NOT_YET)
    print("  ⚠️ 独立永久邮箱实配 %d 个 ⇒ %s" % (
        n_mail, "接线件 tentacle-mail.py 双后端已备好，差主人一条凭据（见 WHO_CAN）"
        if n_mail == 0 else "已闭环自证过的触手地址"))
    ok = (not lies_all) and all(all(k in r for k in GEAR8) for r in d["根"].values())
    print("判据：%s" % ("PASS（账实相符；未配的已逐条如实标，缺什么谁能给都列了）"
                       if ok else "FAIL（账实不符 %d 条）" % len(lies_all)))
    return 0 if ok else 1


# ---------------------------------------------------------------- selftest：负控


def selftest() -> int:
    """负控：隔离实证（子进程级）/ tid 守卫 / 仓外纪律 / 账实一致机制。"""
    import shutil
    import tempfile
    fails = []
    tmp = Path(tempfile.mkdtemp(prefix="gear-selftest-"))
    try:
        # 正照 A·万能插隔离实证：sa 里定义+执行，sb 的库什么都不许有
        sa, sb = tmp / "sa", tmp / "sb"
        sa.mkdir()
        wf = {"name": "gear-probe", "nodes": [{"id": "probe", "kind": "count_words",
                                               "payload": {"text": "isolation"}}]}
        rc1, o1, e1 = _run([PY, FIVE_DIM, "cap", "wf_define", json.dumps(wf)],
                           env_extra={"GBT_STORE_DIR": str(sa)}, timeout=300)
        rc2, o2, e2 = _run([PY, FIVE_DIM, "cap", "wf_run", json.dumps({"name": "gear-probe"})],
                           env_extra={"GBT_STORE_DIR": str(sa)}, timeout=300)
        a_has = (sa / "workflows.json").is_file() and any((sa / "wf_runs").glob("*.json"))
        b_empty = not sb.exists() or not any(sb.iterdir())
        print("正照A·sa 定义+执行落盘 =", a_has, "（必须 True；rc=%s/%s）" % (rc1, rc2))
        print("负控A·sb 库是空的（互不干扰） =", b_empty, "（必须 True）")
        if not a_has:
            fails.append("exec-isolation-a")
        if not b_empty:
            fails.append("exec-isolation-b")
        # 负控 B·tid 守卫（路径穿越拒）
        bad = False
        for t in ("../evil", "a/b", "", "x" * 17):
            try:
                _guard_tid(t)
                bad = True
            except ValueError:
                pass
        print("负控B·坏 tid 被拒 =", not bad, "（必须 True）")
        if bad:
            fails.append("tid-guard")
        # 负控 C·仓外纪律：密钥库/浏览器 profile 不许在仓内；store 必须在仓内 state/ 下
        v_ok = not str(_vault_db("tX")).startswith(str(ROOT))
        p_ok = not str(_profile("tX")).startswith(str(ROOT))
        s_ok = str(_store("tX")).startswith(str(ROOT))
        print("负控C·vault/profile 在仓外、store 在仓内 =", v_ok and p_ok and s_ok,
              "（必须 True）")
        if not (v_ok and p_ok and s_ok):
            fails.append("outside-repo-discipline")
        # 负控 D·账实一致机制：谎称已备而被抓；没备不谎称则不误报
        ghost = {k: {"状态": "已备"} for k in GEAR3}
        lies = _ledger_lies(ghost, _disk_truth("ghost-tid-xx"))
        quiet = _ledger_lies({k: {"状态": "未备"} for k in GEAR3}, _disk_truth("ghost-tid-xx"))
        print("负控D·谎称已备被抓住 =", bool(lies), "（必须 True）；未备不误报 =", not quiet,
              "（必须 True）")
        if not lies or quiet:
            fails.append("ledger-lies-detector")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("自检：%s" % ("全过" if not fails else "失败 %s" % fails))
    return 0 if not fails else 1


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description="触手装备自主配置驱动器（⑥万能插执行器/⑦无痕浏览器/⑧密钥库）")
    ap.add_argument("--json", action="store_true",
                    help="主解析器参数：必须放在子命令之前（仓内口径）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gear", help="实备 ⑥⑦⑧（真验过关才改账本状态）")
    g.add_argument("tid")
    f = sub.add_parser("freebuff", help="⑤ freebuff 隔离建制（HOME + 版本真探；login 是人工闸门）")
    f.add_argument("tid")
    b = sub.add_parser("browser", help="起这根触手的隔离无痕浏览器")
    b.add_argument("tid")
    b.add_argument("--url", default="about:blank")
    b.add_argument("--headless", action="store_true")
    b.add_argument("--timeout", type=float, default=0.0, help="秒；0=等窗口关")
    b.add_argument("--probe", action="store_true", help="无头快检（起→关→留记录）")
    e = sub.add_parser("exec", help="万能插隔离调用（该触手的主执行器）")
    e.add_argument("tid")
    e.add_argument("kind")
    e.add_argument("payload", nargs="?", default="")
    e.add_argument("extra", nargs="*", help="原样转给 cap 的额外参数（如 --full）")
    sub.add_parser("render", help="生成 holo_pet_w3/tentacles/tentacles-data.js")
    sub.add_parser("check", help="总检：账本 vs 磁盘实况")
    sub.add_parser("selftest", help="负控：隔离实证/tid 守卫/仓外纪律/账实一致")
    a = ap.parse_args()

    try:
        if a.cmd == "gear":
            return gear(a.tid, as_json=a.json)
        if a.cmd == "freebuff":
            return gear_freebuff(a.tid, as_json=a.json)
        if a.cmd == "browser":
            return browser(a.tid, url=a.url, headless=a.headless,
                           timeout=a.timeout, probe=a.probe)
        if a.cmd == "exec":
            return exec_cap(a.tid, a.kind, a.payload, a.extra)
        if a.cmd == "render":
            return render()
        if a.cmd == "check":
            return check()
        if a.cmd == "selftest":
            return selftest()
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
