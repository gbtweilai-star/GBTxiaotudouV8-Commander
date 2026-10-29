# -*- coding: utf-8 -*-
"""能力超级visor · **自动报警 + 自我修复 + 安全回滚**（主人令 2026-10-07）。

主人原话：「把每接好的全部接好，断连或者缺失就自动报警自我修复，以及安全回滚都要设计好。」

本件是 `tools/codex-scripts/capability-audit.py`（能力审计 · 逐项真探）的**姊妹件**：
  · 审计件管**看清楚**（四态真探 + 面板）；
  · 本件管**动手**（报警 / 自愈）+ **不动手的边界**（升级给人）。

## 两个子命令

    py -3.14 tools/codex-scripts/capability-supervisor.py watch     # 跑一轮审计 → 判定 → 打印报警
    py -3.14 tools/codex-scripts/capability-supervisor.py heal      # 只对**白名单内、可回滚**的项动手

    heal --dry-run            只出计划，不落手
    heal --only <item-id>     只修一条（可重复）
    heal --rollback <备份id>  从某次自愈的备份**回滚**

## 白名单（只放这三类；其余一律只报警）

  ① **缺/旧的生成产物** —— 重跑它**自己的**生成器（产物是生成的，重跑即可复原）。
  ② **面板桥没起** —— 起 `holo_pet/launch_panel.py`（本机回环 127.0.0.1:8765）。
  ③ **DSH 没接上** —— 走 `holo_pet_w3/shell/dsh-launch.cjs` 的既有做法：`dsh web --no-open`。

## 每个动作三步走（缺一不可）

    ① 先备份 —— 文件类：把现件**复制**到 `state/_heal_backup/<id>/`（**不删原件**）；
                进程类：把「起之前是什么样」写进 manifest（**不动已有进程**）。
    ② 再执行 —— 跑生成器 / 起进程（**只起自己这一个**）。
    ③ 后复验 —— 用审计件的 `probe_item()` **真重探**那一条；不过 ⇒ **自动回滚**并把原文打出来。

## 不许做的（有界）

  · 不许杀**不属于自己**的进程（进程类动作只回滚**自己 spawn 的那个 pid**）；
  · 不许删文件（备份是**复制**，回滚是**复制回去**）；
  · 不许改配置、不许动 `~/.dsh`；
  · **不可逆 / 需要凭据 / 涉及外部服务的，一律只报警不动手** —— 输出「缺什么、谁有权给」。

## 记账

**每一个动作（含回滚）都往记录本 `append` 一条**（`state/logbook.jsonl`，只追加 · 自链哈希）。
直接改 jsonl = 断链，禁止 —— 一律走 `tools/codex-scripts/logbook.py append`。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT_PY = ROOT / "tools" / "codex-scripts" / "capability-audit.py"
LOGBOOK_PY = ROOT / "tools" / "codex-scripts" / "logbook.py"
LEDGER = ROOT / "state" / "capability-audit.json"
BACKUP_ROOT = ROOT / "state" / "_heal_backup"

S_OK, S_BAD, S_MISS, S_UNK = "接上", "断连", "缺失", "未探测"

CMD_WATCH = "py -3.14 tools/codex-scripts/capability-supervisor.py watch"
CMD_HEAL = "py -3.14 tools/codex-scripts/capability-supervisor.py heal"
CMD_AUDIT = "py -3.14 tools/codex-scripts/capability-audit.py"

ACTOR = "capability-supervisor.py"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ts_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except Exception:                                                    # noqa: BLE001
        return None
    return m


CA = _load_mod("_gbt_capability_audit", AUDIT_PY)


def log(what: str, where: list, evidence: str, kind: str = "change", actor: str = ACTOR) -> dict:
    """记一条到记录本（**唯一**写法：走 logbook.py append，不碰 jsonl）。"""
    cmd = [sys.executable, str(LOGBOOK_PY), "append", "--kind", kind, "--actor", actor,
           "--what", what, "--evidence", evidence]
    for w in where:
        cmd += ["--where", str(w)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=60)
        out = (p.stdout or "").strip() or (p.stderr or "").strip()
        print("  🗒  记录本：%s" % out.replace("\n", " ")[:200])
        return {"ok": p.returncode == 0, "out": out, "detail": {"what": what, "where": where,
                                                               "evidence": evidence, "kind": kind}}
    except Exception as e:                                               # noqa: BLE001
        print("  🔴 记录本写入失败：%s: %s" % (type(e).__name__, e))
        return {"ok": False, "out": str(e), "detail": {"what": what, "where": where,
                                                      "evidence": evidence, "kind": kind}}


# ══════════════════════════════════════════════════════════════════════════
# 报警 / 升级（不可自愈的项：只说要什么、谁有权给）
# ══════════════════════════════════════════════════════════════════════════
ESCALATE = {
    "svc.freellmapi": ("FreeLLMAPI 免费模型池（127.0.0.1:31415）没在跑",
                       "主人 / 本机运维：启动 FreeLLMAPI（它的上游 API key 与配额在主人手里）"),
    "svc.ollama": ("本机 Ollama（127.0.0.1:11434）没在跑",
                   "主人 / 本机运维：`ollama serve` 并拉好模型（权重是本机私有资产）"),
    "svc.autoglm-token": ("AutoGLM 本机 token 服务（127.0.0.1:18432/get_token）没在跑",
                          "主人：该 token 与企业凭据在主人侧，AI 无凭据可起"),
    "svc.cliproxy": ("cliproxy 本机口（127.0.0.1:8317）没在跑",
                     "主人：cliproxy 需上游凭据（见 cliproxy.cmd）"),
    "svc.potato": ("小土豆本机口（127.0.0.1:8111）没在跑",
                   "主人：该口对应主人侧服务，需主人决定是否拉起"),
    "svc.genoffice-bridge": ("GenOffice 统一密钥桥（127.0.0.1:31716）没在跑",
                             "主人：桥需 `gbtv8-` 统一密钥，AI 不该自造凭据"),
    "svc.panel-bridge-raw": ("面板桥（127.0.0.1:8765）没在跑",
                             "本件可自愈（见 bridge.panel-8765 白名单动作）"),
}
CAT_ESCALATE = {
    "framework": ("框架能力位登记了、但 `gbt_allinone/api.py` 里找不到分派着落",
                  "主人 / 框架维护者：补 api.py 的分派分支（AI 不擅自改 api.py）"),
    "cloud": ("云插件探测不过（外部 Worker）",
              "主人：云端 Worker 的部署与网关鉴权在主人侧"),
    "shell-window": ("壳窗注册表 `windows.json` 点名的页面不在盘",
                     "主人：`windows.json` 与壳内页面由主人统一登记（AI 不动这些文件）"),
    "panel-page": ("面板 `PAGES` 清单点名的页面到不了（清单说有、实际到不了）",
                   "主人：面板清单与页面由主人统一登记"),
}
GEN_ESCALATE = ("生成产物缺失或陈旧，且**重跑生成器也修不动**（生成器报错 / 依赖不在）",
                "主人：看该产物生成器的报错原文，可能是上游源件或依赖缺失")


def escalate_for(item: dict) -> tuple:
    iid = item.get("id") or ""
    if iid in ESCALATE:
        return ESCALATE[iid]
    return CAT_ESCALATE.get(item.get("category"), GEN_ESCALATE)


# ══════════════════════════════════════════════════════════════════════════
# 白名单与动作
# ══════════════════════════════════════════════════════════════════════════
def _norm_cmd(cmd: list) -> list:
    """把写成人读形态的命令（`py -3.14 xxx.py …`）换成**当前解释器**（`sys.executable`）。

    为什么：生成器命令是以 `py -3.14 …` 记的（给人看的，与仓里别处一致）；真正 spawn 时
    用 `sys.executable`，免得依赖 PATH 上的 `py` 启动器（也免得多一层进程）。
    """
    c = list(cmd)
    if c and Path(c[0]).name.lower() in ("py", "python", "python3", "python.exe", "py.exe"):
        c = c[1:]
        if c and re.match(r"^-3\.\d+$", c[0]):
            c = c[1:]
    return [sys.executable] + c


def artifact_action(item: dict):
    """缺/旧产物 ⇒ 重跑它自己的生成器。返回 (label, cmd_list) 或 None（白名单外）。"""
    if CA is None:
        return None
    iid = item.get("id") or ""
    for row in CA.ARTIFACTS:
        aid, rel, human, gen, stale_vs = row[0], row[1], row[2], row[3], row[4]
        if aid == iid:
            return {"label": "重跑生成器：%s" % gen, "cmd": _norm_cmd(gen.split()),
                    "cmd_text": gen, "target": rel, "kind": "artifact", "reversible": True}
    return None


def bridge_action(item: dict):
    if item.get("id") != "bridge.panel-8765":
        return None
    return {"label": "起面板桥：py -3.14 holo_pet/launch_panel.py --no-browser",
            "cmd": [sys.executable, "holo_pet/launch_panel.py", "--no-browser"],
            "cwd": str(ROOT), "kind": "process", "port": 8765, "reversible": True}


def dsh_action(item: dict):
    iid = item.get("id") or ""
    if not iid.startswith("dsh.web-"):
        return None
    port = int(iid.split("-", 1)[1])
    return {"label": "起 DSH：dsh web --no-open（dsh-launch.cjs 既有做法 · 端口 %d）" % port,
            "cmd": "dsh web --no-open", "shell": True, "kind": "process", "port": port,
            "reversible": True}


def plan_action(item: dict):
    """给一条报警项配一个白名单动作；白名单外返回 None ⇒ **只报警不动手**。"""
    if not item or item.get("state") not in (S_BAD, S_MISS):
        return None
    for fn in (artifact_action, bridge_action, dsh_action):
        a = fn(item)
        if a:
            if a.get("kind") == "process" and not a.get("reversible"):
                return None
            return a
    return None


# ══════════════════════════════════════════════════════════════════════════
# 备份 / 回滚
# ══════════════════════════════════════════════════════════════════════════
def make_backup(bid: str, item: dict, action: dict) -> dict:
    """① 先备份。文件类**复制**现件；进程类只记「起之前是什么样」（**不删不动**）。"""
    d = BACKUP_ROOT / bid
    d.mkdir(parents=True, exist_ok=True)
    man = {"id": bid, "at": now(), "item": item.get("id"), "action": action.get("label"),
           "kind": action.get("kind"), "files": [], "process": None,
           "note": "只复制、不删除；回滚 = 复制回原件（文件类）/ 只停**本次 spawn** 的 pid（进程类）"}
    if action.get("kind") == "artifact":
        src = ROOT / action["target"]
        if src.is_file():
            dst = d / Path(action["target"]).name
            shutil.copy2(src, dst)
            man["files"].append({"path": action["target"], "backup": str(dst),
                                 "size": src.stat().st_size})
    elif action.get("kind") == "process":
        man["process"] = {"port": action.get("port"), "listening_before": port_listening(
            action.get("port")), "spawned_pid": None, "log": None}
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def port_listening(port, host="127.0.0.1", timeout=0.4) -> bool:
    import socket
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        return True
    except Exception:                                                    # noqa: BLE001
        return False
    finally:
        try:
            s.close()
        except Exception:                                                # noqa: BLE001
            pass


def run_generator(cmd: list) -> dict:
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        return {"rc": p.returncode, "out": (p.stdout or "").strip(), "err": (p.stderr or "").strip(),
                "secs": round(time.perf_counter() - t0, 2)}
    except Exception as e:                                               # noqa: BLE001
        return {"rc": -1, "out": "", "err": "%s: %s" % (type(e).__name__, e),
                "secs": round(time.perf_counter() - t0, 2)}


def spawn_process(action: dict, bid: str) -> dict:
    logdir = BACKUP_ROOT / bid
    logdir.mkdir(parents=True, exist_ok=True)
    logp = logdir / "spawn.log"
    f = open(str(logp), "w", encoding="utf-8")
    try:
        if action.get("shell"):
            p = subprocess.Popen(action["cmd"], shell=True, cwd=str(ROOT), stdout=f, stderr=f)
        else:
            p = subprocess.Popen(action["cmd"], cwd=action.get("cwd") or str(ROOT), stdout=f, stderr=f)
        return {"pid": p.pid, "log": str(logp), "obj": p}
    except Exception as e:                                               # noqa: BLE001
        return {"pid": None, "log": str(logp), "err": "%s: %s" % (type(e).__name__, e), "obj": None}
    finally:
        pass


def http_probe(url: str, timeout: float = 3.0) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            return {"http": r.status, "raw": raw[:200]}
    except urllib.error.HTTPError as e:                                  # noqa: BLE001
        return {"http": e.code, "raw": e.read().decode("utf-8", "replace")[:200]}
    except Exception as e:                                               # noqa: BLE001
        return {"http": None, "raw": "%s: %s" % (type(e).__name__, str(e)[:140])}


def verify(item_id: str, wait_s: float = 0.0) -> dict:
    """③ 后复验：**真重探**那一条（用审计件的 probe_item）。"""
    if wait_s:
        time.sleep(wait_s)
    if CA is None or not callable(getattr(CA, "probe_item", None)):
        return {"state": S_UNK, "why": "审计件载入失败 ⇒ 复验做不到（不许假绿）", "item": None}
    it = CA.probe_item(item_id)
    if it is None:
        return {"state": S_UNK, "why": "复验探不到这一条（probe_item 返回 None）", "item": None}
    return {"state": it.get("state"), "item": it, "evidence": it.get("evidence")}


def rollback(bid: str, item_id: str, man: dict, spawned: dict, reason: str) -> str:
    """**自动回滚**：文件复制回去；进程只停**本次 spawn** 的 pid。返回回滚原文摘要。"""
    lines = []
    for f in man.get("files") or []:
        src = Path(f["backup"])
        dst = ROOT / f["path"]
        try:
            shutil.copy2(src, dst)
            lines.append("已回滚文件：%s ← %s（%d 字节）" % (f["path"], src, dst.stat().st_size))
        except Exception as e:                                           # noqa: BLE001
            lines.append("🔴 回滚文件失败：%s → %s：%s" % (src, dst, e))
    if man.get("process") is not None:
        pid = (spawned or {}).get("pid")
        obj = (spawned or {}).get("obj")
        if obj is not None:
            try:
                obj.terminate()
                lines.append("已停**本次 spawn** 的进程 pid=%s（只停自己起的那个）" % pid)
            except Exception as e:                                       # noqa: BLE001
                lines.append("🔴 停进程失败 pid=%s：%s" % (pid, e))
        else:
            lines.append("本次没起进程（无可回滚）")
    out = " ｜ ".join(lines) or "（没有可回滚的东西）"
    print("  ↩️  自动回滚（原因：%s）：%s" % (reason, out))
    log("自愈自动回滚：%s（原因：%s）" % (item_id, reason),
        [str(BACKUP_ROOT / bid)], "回滚原文：%s" % out)
    return out


# ══════════════════════════════════════════════════════════════════════════
# watch：跑一轮审计 → 判定 → 打印报警
# ══════════════════════════════════════════════════════════════════════════
def load_ledger() -> dict:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:                                                    # noqa: BLE001
        return {}


def run_audit() -> int:
    print("— 跑一轮审计（真探 + 生成面板）：%s" % CMD_AUDIT)
    p = subprocess.run([sys.executable, str(AUDIT_PY)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=600)
    tail = (p.stdout or "").strip().splitlines()
    for ln in tail[-6:]:
        print("   | %s" % ln)
    if p.returncode != 0:
        print("   🔴 审计退出码 %d：%s" % (p.returncode, (p.stderr or "").strip()[:300]))
    return p.returncode


def cmd_watch(_args) -> int:
    if run_audit() != 0:
        print("🔴 审计没能跑通 ⇒ 不宣称「看清楚了」（不许假绿）。")
        return 1
    model = load_ledger()
    items = model.get("items") or []
    if not items:
        print("🔴 台账里没有 items ⇒ 判定不了。")
        return 1
    c = model.get("counts") or {}
    alarms = [i for i in items if i.get("state") in (S_BAD, S_MISS)]
    print("=" * 78)
    print("能力 supervisOR · 报警（%s）" % now())
    print("=" * 78)
    print("  总数 %d · 接上 %d · 断连 %d · 缺失 %d · 未探测 %d"
          % (c.get("total"), c.get(S_OK), c.get(S_BAD), c.get(S_MISS), c.get(S_UNK)))
    print("-" * 78)
    if not alarms:
        print("  ✅ 没有断连、没有缺失。")
        return 0
    healable, human = [], []
    for i in alarms:
        (healable if plan_action(i) else human).append(i)
    print("  🔴 报警 %d 条：可自愈（白名单内、可回滚）%d 条 · 需升级给人 %d 条"
          % (len(alarms), len(healable), len(human)))
    print("-" * 78)
    print("  【可自愈 —— %s】" % CMD_HEAL)
    for i in healable:
        a = plan_action(i)
        print("    · [%s] %s" % (i.get("state"), i.get("id")))
        print("        动作：%s" % a.get("label"))
        print("        原文：%s" % (i.get("evidence") or "")[:220])
    if not healable:
        print("    （无）")
    print("-" * 78)
    print("  【升级给人 —— 只报警不动手：缺什么 / 谁有权给】")
    for i in human:
        what, who = escalate_for(i)
        print("    · [%s] %s ｜ %s" % (i.get("state"), i.get("id"), i.get("name")))
        print("        缺什么：%s" % what)
        print("        谁有权给：%s" % who)
        print("        原文：%s" % (i.get("evidence") or "")[:220])
    if not human:
        print("    （无）")
    print("-" * 78)
    print("  判据：py -3.14 tools/codex-scripts/capability-audit.py --check")
    return 0


# ══════════════════════════════════════════════════════════════════════════
# heal：白名单内 · 三步走（备份 → 执行 → 复验；不过则回滚）
# ══════════════════════════════════════════════════════════════════════════
def cmd_heal(args) -> int:
    if getattr(args, "rollback", ""):
        return do_rollback(args.rollback)
    if not hasattr(args, "_model"):
        if run_audit() != 0:
            print("🔴 审计跑不通 ⇒ 不自愈（不许闭眼动手）。")
            return 1
        args._model = load_ledger()
    items = args._model.get("items") or []
    alarms = [i for i in items if i.get("state") in (S_BAD, S_MISS)]
    only = set(getattr(args, "only", []) or [])
    if only:
        alarms = [i for i in alarms if i.get("id") in only]
    plan = [(i, plan_action(i)) for i in alarms]
    todo = [(i, a) for i, a in plan if a]
    skipped = [i for i, a in plan if not a]

    print("=" * 78)
    print("能力 supervisOR · 自愈（%s）%s" % (now(), "【DRY-RUN · 只出计划】" if args.dry_run else ""))
    print("=" * 78)
    print("  报警 %d 条 · 白名单内可自愈 %d 条 · 白名单外（不动手）%d 条"
          % (len(alarms), len(todo), len(skipped)))
    for i, a in todo:
        print("  ▶ [%s] %s" % (i.get("state"), i.get("id")))
        print("      动作：%s" % a.get("label"))
    for i in skipped:
        what, who = escalate_for(i)
        print("  ⏸ [%s] %s —— 白名单外，只报警：%s（谁有权给：%s）"
              % (i.get("state"), i.get("id"), what, who))
    if not todo:
        print("  ✅ 没有白名单内需要动手的项。")
        return 0
    if args.dry_run:
        print("  （DRY-RUN：未落手）")
        return 0

    bid = ts_id()
    fixed, failed = [], []
    for item, action in todo:
        iid = item.get("id")
        print("-" * 78)
        print("  ▣ 处理 %s（%s）" % (iid, item.get("state")))
        log("自愈开始：%s（%s）" % (iid, item.get("state")), [str(BACKUP_ROOT / bid)],
            "动作：%s ｜ 触发原文：%s" % (action.get("label"), (item.get("evidence") or "")[:200]))
        # ① 先备份
        man = make_backup(bid, item, action)
        print("    ① 备份：%s" % (str(BACKUP_ROOT / bid)))
        if man.get("files"):
            for f in man["files"]:
                print("       复制 %s（%d 字节）→ %s" % (f["path"], f["size"], f["backup"]))
        if man.get("process") is not None:
            print("       进程类：记录「起之前 %s 是否在听 = %s」（**不动已有进程**）"
                  % (man["process"]["port"], man["process"]["listening_before"]))
        # ② 再执行
        spawned = {}
        if action.get("kind") == "artifact":
            print("    ② 执行：%s" % (action.get("cmd_text") or " ".join(action["cmd"])))
            r = run_generator(action["cmd"])
            print("       rc=%s 用时 %ss" % (r["rc"], r["secs"]))
            for ln in (r["out"] or "").splitlines()[-4:]:
                print("       | %s" % ln)
            if r["err"]:
                print("       ! stderr: %s" % r["err"][:300])
        else:
            print("    ② 执行：%s" % action.get("cmd"))
            spawned = spawn_process(action, bid)
            man["process"]["spawned_pid"] = spawned.get("pid")
            (BACKUP_ROOT / bid / "manifest.json").write_text(
                json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            print("       起进程 pid=%s（日志 %s）" % (spawned.get("pid"), spawned.get("log")))
            if spawned.get("err"):
                print("       ! %s" % spawned["err"])
        # ③ 后复验
        wait = 2.0 if action.get("kind") == "process" else 0.0
        v = verify(iid, wait_s=wait)
        print("    ③ 复验：%s" % v.get("state"))
        print("       原文：%s" % (v.get("evidence") or v.get("why") or "")[:300])
        if v.get("state") == S_OK:
            print("       ✅ 复验通过：%s 现在「接上」" % iid)
            log("自愈完成：%s → 接上" % iid, [str(BACKUP_ROOT / bid)],
                "动作：%s ｜ 复验原文：%s" % (action.get("label"), (v.get("evidence") or "")[:240]))
            fixed.append(iid)
        else:
            print("       🔴 复验**不过** ⇒ 自动回滚")
            rb = rollback(bid, iid, man, spawned, "复验不过（%s）" % v.get("state"))
            print("       回滚后复验原文已打出；该项**没修好**，升级给人。")
            failed.append((iid, v.get("state"), rb))
    print("=" * 78)
    print("  自愈收工：修好 %d 条 · 没修好 %d 条 ｜ 备份目录 %s"
          % (len(fixed), len(failed), BACKUP_ROOT / bid))
    for iid, st, rb in failed:
        print("    🔴 %s 仍为「%s」（已回滚）" % (iid, st))
    print("  提示：把这轮读数写进面板 → %s" % CMD_WATCH)
    return 0 if not failed else 1


def do_rollback(bid: str) -> int:
    d = Path(bid)
    if not d.is_absolute():
        d = BACKUP_ROOT / bid
    manp = d / "manifest.json"
    if not manp.is_file():
        print("🔴 找不到备份 manifest：%s" % manp)
        return 1
    man = json.loads(manp.read_text(encoding="utf-8"))
    print("=" * 78)
    print("能力 supervisOR · 手动回滚（%s）" % d.name)
    print("=" * 78)
    print("  该备份对应：%s ｜ 动作：%s ｜ 备份于 %s" % (man.get("item"), man.get("action"), man.get("at")))
    lines = []
    for f in man.get("files") or []:
        src = Path(f["backup"])
        dst = ROOT / f["path"]
        try:
            shutil.copy2(src, dst)
            lines.append("已复制回：%s（%d 字节）" % (f["path"], dst.stat().st_size))
            print("  ✔ %s" % lines[-1])
        except Exception as e:                                           # noqa: BLE001
            lines.append("🔴 失败：%s：%s" % (f["path"], e))
            print("  🔴 %s" % lines[-1])
    if man.get("process") is not None:
        pid = (man["process"] or {}).get("spawned_pid")
        if pid:
            # **只停我们自己 spawn 的 pid**；不确定归属一律不动
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                               timeout=20)
                lines.append("已停本次 spawn 的 pid=%s" % pid)
                print("  ✔ %s" % lines[-1])
            except Exception as e:                                       # noqa: BLE001
                lines.append("🔴 停 pid=%s 失败：%s" % (pid, e))
                print("  🔴 %s" % lines[-1])
        else:
            lines.append("该备份无 spawn pid（无可停）")
            print("  · %s" % lines[-1])
    out = " ｜ ".join(lines) or "（没有可回滚的东西）"
    log("手动回滚：%s（%s）" % (man.get("item"), d.name), [str(d)], "回滚原文：%s" % out)
    return 0


# ══════════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                                # noqa: BLE001
            pass
    p = argparse.ArgumentParser(description="能力 supervisOR · 报警 + 自愈 + 回滚")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("watch", help="跑一轮审计 → 判定 → 打印报警")
    h = sub.add_parser("heal", help="白名单内自愈（备份→执行→复验；不过则回滚）")
    h.add_argument("--dry-run", action="store_true", help="只出计划，不落手")
    h.add_argument("--only", action="append", default=[], help="只修某条 item-id（可重复）")
    h.add_argument("--rollback", default="", help="从某次自愈的备份回滚（备份 id 或路径）")
    args = p.parse_args(argv)
    if args.cmd == "watch":
        return cmd_watch(args)
    if args.cmd == "heal":
        return cmd_heal(args)
    print("用法：capability-supervisor.py [watch | heal [--dry-run] [--only ID] [--rollback ID]]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
