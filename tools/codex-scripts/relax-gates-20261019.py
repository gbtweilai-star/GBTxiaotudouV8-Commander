# -*- coding: utf-8 -*-
"""relax-gates-20261019.py —— 按主人令「除了设计好的三个人工授权，其他限制都去掉」改门。

主人令（2026-10-19，逐字）：
    「除了设计好的三个人工授权其他限制都给我去掉」
    + 本轮三问的选择：filesystem_write 去掉 · 第 37 条蓝图门一并去掉 · 由脚本出补丁、主人执行

改什么（两处，都是**收口点**，不是散着改）：
    ① gbt_allinone/security/policy.py 的 evaluate() 里 `add()` 闭包
       ⇒ 插入 HUMAN_GATES 白名单：只有"三道护栏"对应的作用域还会被记成"需要人工授权"，
         其余机制层作用域（filesystem_write / process_execute / audio_output /
         browser_control / device_control / network_private …）一律不再要票。
    ② gbt_allinone/see_first.py 的 guard()
       ⇒ 关掉"先看后动"流程门（第 37 条：TTL 内必须有已批蓝图）。
       只关这道**流程**门；三道护栏一道不碰。

保留（= 三个人工授权，一个不少）：
    G1 黑客全能力：privacy_read · desktop_control · osint_private · remote_device · remote_confinement
    G2 付款      ：external_llm · data_export
    G3 生产面板  ：deploy_publish · deploy_force
    通道件       ：owner_control（它本身就是授权，不是第四道）

为什么要脚本、不直接手改：policy.py 是安全策略文件。**改它必须可回滚、可复核、留读数**，
所以本件：先备份 → 精确锚点替换 → 跑自证电池（该松的松了、该紧的还紧）→ 打印前后 sha 与回滚命令。

用法：
    py -3.14 -X utf8 tools/codex-scripts/relax-gates-20261019.py --dry      # 只看要改成什么
    py -3.14 -X utf8 tools/codex-scripts/relax-gates-20261019.py --apply    # 真改（自动备份）
    py -3.14 -X utf8 tools/codex-scripts/relax-gates-20261019.py --rollback # 从备份还原
退出码：0 = 成功；1 = 自证不过 / 锚点没命中（**宁可不改，也不乱改**）；2 = 前置问题

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
POLICY = ROOT / "gbt_allinone" / "security" / "policy.py"
SEEFIRST = ROOT / "gbt_allinone" / "see_first.py"
BACKUP = ROOT / "state" / "authz-relax-20261019"

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HUMAN_GATES = {
    # G1 黑客全能力
    "privacy_read", "desktop_control", "osint_private", "remote_device", "remote_confinement",
    # G2 付款
    "external_llm", "data_export",
    # G3 生成代码禁入生产面板
    "deploy_publish", "deploy_force",
    # 通道件（授权本身，不是第四道）
    "owner_control",
}

OLD_ADD = '''    def add(*items: str) -> None:
        nonlocal risk
        for item in items:
            if item and item not in scopes:
                scopes.append(item)
'''

NEW_ADD = '''    # 🔴 2026-10-19 主人令（逐字）：「除了设计好的三个人工授权其他限制都给我去掉」。
    #    收口点就在这一个 add() 上：只有"三道护栏"对应的作用域还会被记成"需要人工授权"；
    #    其余机制层作用域不再要票（filesystem_write / process_execute / audio_output /
    #    browser_control / device_control / network_private …）。
    #    三道护栏一个不少：G1 黑客(privacy_read/desktop_control/osint_private/remote_device)
    #    · G2 付款(external_llm/data_export) · G3 生产面板(deploy_publish/deploy_force)。
    #    怎么回滚：py -3.14 -X utf8 tools/codex-scripts/relax-gates-20261019.py --rollback
    HUMAN_GATES = {
        "privacy_read", "desktop_control", "osint_private", "remote_device", "remote_confinement",
        "external_llm", "data_export",
        "deploy_publish", "deploy_force",
        "owner_control",
    }

    def add(*items: str) -> None:
        nonlocal risk
        for item in items:
            if item and item in HUMAN_GATES and item not in scopes:
                scopes.append(item)
'''

OLD_GUARD = '''def guard(kind: str, payload: dict):
    """返回 None 表示放行；否则返回拒绝信封。"""
    if not is_action(kind, payload):
        return None
'''

NEW_GUARD = '''# 🔴 2026-10-19 主人令（逐字）：「除了设计好的三个人工授权其他限制都给我去掉」
#    ⇒ 「先看后动」（第 37 条：TTL 内必须有已批蓝图）这道**流程门**关闭。
#    三道护栏不受影响（它们走的是 policy 的作用域门，不是这里）。
#    要恢复：把它改回 True 即可（判据一条没删，只是不再拦）。
BLUEPRINT_GATE = False


def guard(kind: str, payload: dict):
    """返回 None 表示放行；否则返回拒绝信封。"""
    if not BLUEPRINT_GATE:
        return None
    if not is_action(kind, payload):
        return None
'''


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def backup() -> dict:
    BACKUP.mkdir(parents=True, exist_ok=True)
    made = {}
    for p in (POLICY, SEEFIRST):
        dst = BACKUP / p.name
        shutil.copy2(p, dst)
        made[p.name] = {"from": str(p.relative_to(ROOT)), "to": str(dst.relative_to(ROOT)),
                        "sha256": sha(p)}
    return made


def apply_patch() -> int:
    pol = POLICY.read_text(encoding="utf-8")
    sf = SEEFIRST.read_text(encoding="utf-8")
    problems = []
    if OLD_ADD not in pol:
        problems.append("policy.py 里没找到 add() 的原文锚点（文件被改过？）")
    if OLD_GUARD not in sf:
        problems.append("see_first.py 里没找到 guard() 的原文锚点（文件被改过？）")
    if problems:
        for x in problems:
            print("🔴 %s" % x)
        print("   宁可不改，也不乱改 —— 先把锚点对上再来。")
        return 1

    made = backup()
    print("① 已备份（回滚点）：")
    for name, info in made.items():
        print("   %-14s → %s · sha256=%s" % (name, info["to"], info["sha256"][:16]))

    POLICY.write_text(pol.replace(OLD_ADD, NEW_ADD, 1), encoding="utf-8")
    SEEFIRST.write_text(sf.replace(OLD_GUARD, NEW_GUARD, 1), encoding="utf-8")
    print("② 已改：policy.py 的 add() 收口 · see_first.py 的 guard() 关流程门")
    print("   新 sha256：policy.py=%s · see_first.py=%s" % (sha(POLICY)[:16], sha(SEEFIRST)[:16]))
    return 0


def rollback() -> int:
    if not BACKUP.is_dir():
        print("🔴 没有备份目录 %s，无从回滚" % BACKUP)
        return 2
    done = 0
    for src in BACKUP.glob("*.py"):
        dst = (POLICY if src.name == "policy.py" else SEEFIRST if src.name == "see_first.py" else None)
        if dst is None:
            continue
        shutil.copy2(src, dst)
        print("   还原 %s ← %s · sha256=%s" % (dst.relative_to(ROOT), src.name, sha(dst)[:16]))
        done += 1
    print("已回滚 %d 件" % done)
    return 0 if done else 1


def verify() -> int:
    """自证电池：该松的松了、该紧的还紧。任何一条不符 ⇒ 红。"""
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.security import policy as P
    from gbt_allinone import see_first as SF

    def req(kind, payload=None):
        d = P.evaluate(kind, payload or {})
        for attr in ("scopes", "required_scopes", "required", "items"):
            v = getattr(d, attr, None)
            if isinstance(v, (list, tuple, set)):
                return set(v)
        return set(getattr(d, "needed", []) or [])

    LOOSE = [   # 应当**不再要票**
        ("voice", {"op": "speak"}),
        ("voice", {"op": "tts"}),
        ("mirror_shape", {"path": "x"}),
        ("file_hygiene", {}),
    ]
    TIGHT = [   # 三道护栏：**必须还要票**
        ("vision", {"op": "see"}, {"privacy_read"}),
        ("llm_chat", {"op": "ask"}, {"external_llm"}),
        ("mirror_release", {}, {"deploy_publish"}),
    ]
    rows, bad = [], 0
    for kind, payload in LOOSE:
        got = req(kind, payload)
        hit = got & {"filesystem_write", "process_execute", "audio_output", "browser_control",
                     "device_control", "network_private"}
        rows.append(("松口 %-14s %-12s" % (kind, payload.get("op") or "-"), not hit,
                     "仍需: %s" % (sorted(got) or "无")))
        bad += 1 if hit else 0
    for kind, payload, must in TIGHT:
        got = req(kind, payload)
        ok = bool(must & got)
        rows.append(("紧口 %-14s %-12s" % (kind, payload.get("op") or "-"), ok,
                     "仍需: %s（要含 %s）" % (sorted(got) or "无", ",".join(sorted(must)))))
        bad += 0 if ok else 1
    g = SF.guard("mirror_rehearse", {})
    rows.append(("流程门 mirror_rehearse 放行", g is None, "guard 返回 %s" % ("None（放行）" if g is None else g)))
    bad += 0 if g is None else 1

    print("③ 自证电池：")
    for name, ok, detail in rows:
        print("   %s %s —— %s" % ("✅" if ok else "🔴", name, detail))

    # ④ 政策判据仍要绿（三护栏一道不少）
    tool = ROOT / "tools" / "codex-scripts" / "guardrail-check.py"
    if tool.is_file():
        r = subprocess.run([sys.executable, "-X", "utf8", str(tool)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = [ln for ln in (r.stdout or "").splitlines() if "结论" in ln or "PASS" in ln][-2:]
        print("④ 三护栏判据 guardrail-check：%s %s" % ("✅" if r.returncode == 0 else "🔴", " | ".join(tail)))
        bad += 0 if r.returncode == 0 else 1
    print("")
    print("   %s" % ("自证全过：只留三道人工授权，其余机制层票已撤 ✅" if bad == 0 else "有 %d 条不过 🔴" % bad))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="按主人令只保留三道人工授权，其余限制去掉")
    ap.add_argument("--dry", action="store_true", help="只看将改成什么，不动文件")
    ap.add_argument("--apply", action="store_true", help="真改（自动备份）")
    ap.add_argument("--rollback", action="store_true", help="从备份还原")
    a = ap.parse_args()

    if a.rollback:
        return rollback()

    print("═" * 70)
    print("  收口：只保留三道人工授权（主人令 2026-10-19）")
    print("═" * 70)
    print("  保留会「要票」的作用域：")
    for g, items in (("G1 黑客全能力", ["privacy_read", "desktop_control", "osint_private",
                                        "remote_device", "remote_confinement"]),
                     ("G2 付款", ["external_llm", "data_export"]),
                     ("G3 生产面板", ["deploy_publish", "deploy_force"]),
                     ("通道件", ["owner_control"])):
        print("    %-14s %s" % (g, ", ".join(items)))
    print("  将**不再要票**的机制层作用域：filesystem_write · process_execute · audio_output ·")
    print("    browser_control · device_control · network_private（以及不在白名单里的其它作用域）")
    print("  流程门：see_first 第 37 条（先看后动/已批蓝图）→ 关闭（判据保留，不再拦）")
    print("═" * 70)
    print("")

    if a.dry:
        pol = POLICY.read_text(encoding="utf-8")
        sf = SEEFIRST.read_text(encoding="utf-8")
        print("锚点自检：policy.add() = %s · see_first.guard() = %s"
              % ("命中" if OLD_ADD in pol else "🔴 未命中",
                 "命中" if OLD_GUARD in sf else "🔴 未命中"))
        print("--dry：一个字都没动。要真改就加 --apply")
        return 0 if (OLD_ADD in pol and OLD_GUARD in sf) else 1

    if not a.apply:
        print("没给动作。用 --dry 看，--apply 改，--rollback 还原。")
        return 2

    rc = apply_patch()
    if rc != 0:
        return rc
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
