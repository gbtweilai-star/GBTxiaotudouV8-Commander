# -*- coding: utf-8 -*-
"""病因追踪工具箱（RCA toolkit）· 把热门项目的机制落到本仓自己的病因线

**为什么是这六法**（抓取热门项目后蒸馏，出处见文件末尾）：
  ① bisect    —— 二分定位"哪个提交引入的"（git 原生，工业界最硬的一招）
  ② szz       —— 从修复提交反推 **bug-introducing commit**（SZZ / PR-SZZ 系）
  ③ ddmin     —— Zeller 增量调试：把失败输入**最小化**到最小可复现例（MRE）
  ④ faultloc  —— 覆盖率可疑度排序（Ochiai 公式）⇒ 最可能出问题的那几行
  ⑤ correlate —— 遥测拐点相关（RCAEval 系）⇒ 谁先坏、谁是因
  ⑥ playbook  —— **病因 → 改法**（补本仓登记未闭环项：病因只驱动重试、没驱动改法）

与本仓现有病因线的关系：**不另造词**。分类词表直接复用
`gbt_allinone/tentacle/nav_etiology.py` 的 `NAV_CAUSES / CAUSE_KEYS / RETRY_HINT`；
本文件只补"**怎么找因**"和"**因定了怎么改**"。

    python tools/etiology/rca.py playbook [病因]        # 病因→改法（可点名单个病因）
    python tools/etiology/rca.py bisect <repo> --good <sha> --bad <sha> -- <判定命令...>
    python tools/etiology/rca.py szz <repo> [--path <p>] [--limit 20]
    python tools/etiology/rca.py ddmin -- <判定命令...>   # 从 stdin 逐行读候选元素，输出最小集
    python tools/etiology/rca.py faultloc <coverage.json> # {"tests":[{"name","pass","lines":[...]}]}
    python tools/etiology/rca.py correlate <series.json>  # {"metric":[[t,v],...],...}
    python tools/etiology/rca.py ledger                    # 账本
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import time

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
LEDGER = WS / ".etiology/ledger.jsonl"

# ── 分类词表：直接复用本仓病因线（import 失败则用同值兜底，绝不静默改词）──
try:
    sys.path.insert(0, str(WS / "gbt_allinone" / "tentacle"))
    import nav_etiology as NAV                     # type: ignore
    CAUSE_KEYS = list(NAV.CAUSE_KEYS)
    CAUSE_CN = dict(NAV.CAUSE_CN)
    RETRY_HINT = dict(NAV.RETRY_HINT)
    SOURCE = "nav_etiology（本仓真身）"
except Exception as e:                             # 兜底：显式标注来源，不冒充
    CAUSE_KEYS = ["element_not_found", "timeout", "modal_blocked", "denied_by_gate",
                  "stale_state", "backend_failed", "structure_unavailable", "unknown"]
    CAUSE_CN = dict(zip(CAUSE_KEYS, CAUSE_KEYS))
    RETRY_HINT = {k: "未知" for k in CAUSE_KEYS}
    SOURCE = f"兜底词表（nav_etiology 不可用：{type(e).__name__}）"

# ── ⑥ 病因 → **改法**（本仓登记的未闭环项，这里补上）─────────────────────
PLAYBOOK = {
    "element_not_found": ("目标元素不在当前画面/树上", [
        "先读真名（read_text/list_windows）确认目标是否存在，别凭猜的名字重试",
        "滚动/展开找（铁律③）；再不行改文字特征重找",
        "仍找不到 ⇒ 如实报『界面结构与预期不符』，**不要用坐标硬点一个大概位置**"]),
    "window_lost": ("目标窗口已消失/句柄失效", [
        "重新枚举窗口（list_windows）；确认目标是否被关掉或崩了",
        "必要时重新拉起目标程序；再走一遍『先看再动』",
        "句柄类引用**绝不跨轮复用**（复用旧 hwnd 是这类病的主因）"]),
    "timeout": ("等到超时仍不满足条件", [
        "先取一帧：确认是**真慢**、**死锁**、还是**根本没发生**（三种病因三种改法）",
        "真慢 ⇒ 抬阈值并把新阈值记进配置；死锁 ⇒ 修调用链；没发生 ⇒ 动作压根没发进去（转 modal/action_no_effect）",
        "等待要**等状态**而不是等固定秒数（判据自证）"]),
    "modal_blocked": ("被弹窗/遮罩挡住", [
        "先看清弹窗问什么再关（铁律④）；关完**取一帧确认真的没了**",
        "把弹窗特征写进 detect_dialog 词表，下次自动先关",
        "弹窗还在时**不许**继续点原目标（会点到弹窗上）"]),
    "denied_by_gate": ("被授权门/权限拒绝", [
        "🔴 **绝不重试**（重试就是绕门的开始）—— 如实报缺哪个 scope",
        "给出主人要跑的那一行（例：auth grant --scope desktop_control --ttl 600 --purpose …）",
        "检查是否把『计费动作』当『只读动作』；计费动作先报价再确认"]),
    "backend_unavailable": ("后端/依赖不可用（缺模块、服务没起）", [
        "先分『缺件』还是『坏件』（本仓血泪：跑不动多是缺件）",
        "缺件 ⇒ 报缺什么 + 给安装/授权命令；坏件 ⇒ 先用 ddmin 缩到最小复现再修",
        "换后端前确认**契约没变**（能力位/输入输出同构才换）"]),
    "stale_target": ("元素/句柄取到过但已失效", [
        "重新取一次元素再动作，**别复用旧引用**",
        "把『读后即用』改成『读-判-用』：动手前验一下引用还活着吗",
        "界面刚重绘的窗口要等稳定（wait_stable）再取"]),
    "action_no_effect": ("动作发出但看不出效果（判不出就别猜）", [
        "**前后对比截图**（铁律⑥）—— 这是唯一可靠判据，不许凭感觉",
        "确认动作真发进了目标（UIA 回读 / 焦点检查），而不是发到了别的窗口",
        "真判不出来 ⇒ 如实报『不确定』并留下前后两帧，别写成成功"]),
}


def log(entry: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entry["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run(cmd, cwd=None, timeout=600):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))


# ── ① bisect ───────────────────────────────────────────────────────────────
def cmd_bisect(repo, good, bad, predicate):
    """git bisect run 原生二分：找**第一个坏提交**。门 = 找到 + 它的父提交是好的。"""
    repo = pathlib.Path(repo)
    run(["git", "bisect", "reset"], cwd=repo)
    rc, out = run(["git", "bisect", "start", bad, good], cwd=repo)
    if rc != 0:
        print(f"❌ bisect start 失败：{out.strip()[:120]}")
        return 1
    rc, out = run(["git", "bisect", "run"] + predicate, cwd=repo, timeout=1800)
    culprit = None
    m = re.search(r"([0-9a-f]{7,40}) is the first bad commit", out)
    if m:
        culprit = m.group(1)
    # ★ 不靠措辞：`bisect run` 结束时 HEAD 就停在首个坏提交 —— 直接读它（措辞会变，HEAD 不会）
    if not culprit:
        rc4, head = run(["git", "rev-parse", "HEAD"], cwd=repo)
        h = head.strip()
        if re.fullmatch(r"[0-9a-f]{7,40}", h) and "bisect" in out.lower() and "bad" in out.lower():
            culprit = h
    run(["git", "bisect", "reset"], cwd=repo)
    ok = culprit is not None
    if ok:
        rc2, log1 = run(["git", "log", "-1", "--format=%h %s", culprit], cwd=repo)
        rc3, parent = run(["git", "rev-parse", culprit + "^"], cwd=repo)
        print(f"  首个坏提交：{log1.strip()}")
        print(f"  其父提交：{parent.strip()[:12]}")
    else:
        # ★ 不许把诊断吞掉：失败时把 bisect 输出尾部原样打出来（"没证据"本身就是缺陷）
        tail = [l for l in out.strip().splitlines() if l.strip()][-6:]
        print("  未定位到，bisect 原始输出尾部：")
        for l in tail:
            print("    | " + l[:140])
    print(f"S-病因门: {'✅' if ok else '❌'} {'已定位引入提交' if ok else '未定位'}")
    log({"op": "bisect", "repo": str(repo), "culprit": culprit, "ok": ok})
    return 0 if ok else 1


# ── ② szz（SZZ-lite：修复提交删掉的行，blame 回引入提交）──────────────────
FIX_RE = re.compile(r"\b(fix|fixes|fixed|bug|issue|修复|修|问题)\b", re.I)


def cmd_szz(repo, path=None, limit=20):
    repo = pathlib.Path(repo)
    rc, out = run(["git", "log", "--format=%H%x09%s", "-n", str(limit)], cwd=repo)
    fixes = [l.split("\t", 1) for l in out.strip().splitlines() if "\t" in l]
    fixes = [(h, s) for h, s in fixes if FIX_RE.search(s)]
    if not fixes:
        print("S-SZZ: ❌ 最近提交里没有『修复类』提交（可加大 --limit）")
        return 1
    found = []
    for h, s in fixes[:5]:
        args = ["git", "show", "--unified=0", "--format=", h]
        if path:
            args += ["--", path]
        rc, diff = run(args, cwd=repo)
        removed = [m.group(1) for m in re.finditer(r"^-(?!-)(.*)$", diff, re.M) if m.group(1).strip()]
        for line in removed[:20]:
            rc, bl = run(["git", "log", "-1", "--format=%h %s", "-S", line.strip()[:60], h + "^",
                          "--"] + ([path] if path else []), cwd=repo)
            if bl.strip():
                found.append({"fix": h[:8], "line": line.strip()[:70], "introduced_by": bl.strip()[:80]})
                break
    ok = bool(found)
    print(f"  SZZ：扫了 {len(fixes[:5])} 个修复提交，反推出 {len(found)} 条引入线索")
    for f in found[:6]:
        print(f"    修复 {f['fix']} ← 该行由 {f['introduced_by']} 引入")
    print(f"S-SZZ 门: {'✅' if ok else '❌'} {'有引入提交线索' if ok else '无线索'}")
    log({"op": "szz", "repo": str(repo), "found": len(found), "ok": ok})
    return 0 if ok else 1


# ── ③ ddmin（Zeller 增量调试）─────────────────────────────────────────────
def cmd_ddmin(predicate, elements):
    """把"失败集合"最小化：返回仍能触发失败的**最小子集**。判据= predicate 仍失败且集合最小。"""
    def fails(sub):
        p = subprocess.run(predicate, input="\n".join(sub), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        return p.returncode != 0

    if not fails(elements):
        print("S-ddmin: ❌ 全集不失败（判定命令语义反了？退出码非 0 才算失败）")
        return 1
    n = 2
    cur = list(elements)
    while len(cur) >= 2:
        chunk = max(1, len(cur) // n)
        reduced = False
        for i in range(0, len(cur), chunk):
            subset = cur[:i] + cur[i + chunk:]
            if subset and fails(subset):
                cur, n, reduced = subset, max(2, n - 1), True
                break
        if not reduced:
            if n >= len(cur):
                break
            n = min(len(cur), n * 2)
    ok = fails(cur) and len(cur) >= 1
    print(f"  ddmin：{len(elements)} → **{len(cur)}** 个元素仍触发失败")
    for e in cur[:10]:
        print(f"    · {e[:90]}")
    print(f"S-ddmin 门: {'✅' if ok else '❌'} {'已最小化且仍复现' if ok else '最小集不再复现（实现有误）'}")
    log({"op": "ddmin", "before": len(elements), "after": len(cur), "ok": ok})
    return 0 if ok else 1


# ── ④ faultloc（Ochiai 可疑度）─────────────────────────────────────────────
def cmd_faultloc(cov_file):
    d = json.loads(pathlib.Path(cov_file).read_text(encoding="utf-8"))
    tests = d.get("tests", [])
    if not tests:
        print("S-faultloc: ❌ coverage.json 里没有 tests")
        return 1
    from collections import defaultdict
    a = defaultdict(int)   # 失败且覆盖
    b = defaultdict(int)   # 通过且覆盖
    tf = sum(1 for t in tests if not t.get("pass"))
    tp = sum(1 for t in tests if t.get("pass"))
    for t in tests:
        for ln in t.get("lines", []):
            if t.get("pass"):
                b[ln] += 1
            else:
                a[ln] += 1
    # 🔴 2026-09-26 自纠：守卫必须含 tf —— 全部用例通过（tf=0）时分母为 0.0，原版会 ZeroDivisionError
    scores = {ln: a[ln] / ((tf * (a[ln] + b[ln])) ** 0.5) if (tf and (a[ln] + b[ln])) else 0 for ln in set(a) | set(b)}
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:8]
    ok = bool(top) and top[0][1] > 0
    print(f"  faultloc：{len(tests)} 个用例（失败 {tf}/通过 {tp}）· Ochiai 前 8 行：")
    for ln, s in top:
        print(f"    line {ln:>5}  可疑度 {s:.3f}  （失败覆盖 {a[ln]} / 通过覆盖 {b[ln]}）")
    print(f"S-faultloc 门: {'✅' if ok else '❌'} {'可疑行已排序' if ok else '无可疑行（用例数据不足）'}")
    log({"op": "faultloc", "tests": len(tests), "top": top[:3], "ok": ok})
    return 0 if ok else 1


# ── ⑤ correlate（遥测拐点：谁先坏 = 谁是因）────────────────────────────────
def _onset(series):
    """变点判据（不是 2.5σ —— 短序列/小波动用 σ 检不出来，实测踩过）。
    判据：相邻一阶差分的最大值 > 全序列跨度的 25% ⇒ 该点即拐点。"""
    if not series or len(series) < 2:
        return None
    vals = [v for _, v in series]
    rng = max(vals) - min(vals)
    if rng <= 0:
        return None
    best_i, best_d = None, 0.0
    for i in range(1, len(series)):
        d = abs(vals[i] - vals[i - 1])
        if d > best_d:
            best_i, best_d = i, d
    if best_i is not None and best_d > 0.25 * rng:
        return series[best_i]
    return None


def cmd_correlate(f):
    d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
    onsets = []
    for k, s in d.items():
        o = _onset(s)
        if o:
            onsets.append((o[0], k, o[1]))
    onsets.sort()
    ok = len(onsets) >= 1
    print(f"  correlate：{len(d)} 条指标，检出拐点 {len(onsets)} 条（按时间排序 ⇒ **越靠前越可能是因**）")
    for t, k, v in onsets[:8]:
        print(f"    t={t:<8} {k:<28} 值 {v}")
    if len(onsets) >= 2:
        print(f"  → 首选可疑因：**{onsets[0][1]}**（最早拐点；其余按先后排序为果）")
    print(f"S-correlate 门: {'✅' if ok else '❌'} {'有拐点可排因果序' if ok else '无拐点'}")
    log({"op": "correlate", "metrics": len(d), "onsets": len(onsets), "ok": ok})
    return 0 if ok else 1


def cmd_playbook(one=None):
    keys = [one] if one else CAUSE_KEYS
    bad = [k for k in keys if k not in PLAYBOOK]
    print(f"病因 → 改法（词表来源：{SOURCE}）")
    for k in keys:
        if k not in PLAYBOOK:
            continue
        cn, steps = PLAYBOOK[k]
        print(f"\n【{cn}】{k}   （重试策略：{RETRY_HINT.get(k, '—')}）")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {s}")
    ok = not bad
    if bad:
        print(f"\n❌ 未覆盖的病因：{bad}（词表变了 ⇒ 改法表必须跟着更新）")
    print(f"\nS-playbook 门: {'✅' if ok else '❌'} 覆盖 {len([k for k in keys if k in PLAYBOOK])}/{len(keys)} 类病因")
    log({"op": "playbook", "asked": len(keys), "ok": ok})
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "playbook":
        return sys.exit(cmd_playbook(a[1] if len(a) > 1 else None))
    if cmd == "bisect":
        if "--" not in a:
            print("用法: bisect <repo> --good <sha> --bad <sha> -- <判定命令...>")
            return
        i = a.index("--")
        opts = a[1:i]
        repo = opts[0] if opts else "."
        good = opts[opts.index("--good") + 1]
        bad = opts[opts.index("--bad") + 1]
        return sys.exit(cmd_bisect(repo, good, bad, a[i + 1:]))
    if cmd == "szz":
        repo = a[1] if len(a) > 1 else "."
        path = a[a.index("--path") + 1] if "--path" in a else None
        limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 20
        return sys.exit(cmd_szz(repo, path, limit))
    if cmd == "ddmin":
        elems = [l.rstrip("\n") for l in sys.stdin if l.strip()]
        if "--" not in a:
            print("用法: ddmin -- <判定命令...>   （候选元素从 stdin 逐行读入）")
            return
        return sys.exit(cmd_ddmin(a[a.index("--") + 1:], elems))
    if cmd == "faultloc":
        return sys.exit(cmd_faultloc(a[1]))
    if cmd == "correlate":
        return sys.exit(cmd_correlate(a[1]))
    if cmd == "ledger":
        if LEDGER.exists():
            for line in LEDGER.read_text(encoding="utf-8").strip().splitlines()[-12:]:
                print("  " + line)
        else:
            print("  （账本还没落盘）")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
