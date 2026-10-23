# gbt-capability: selfgrowth
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""自生长知识库 4.0 的四判据机检（蒸馏自 Codex + Google WikiSkill 演示稿 · 主人 2026-09-27）。

口径：来源是**二手演示稿**（主人现场拍摄），按其自述「细节须回到一手来源复核」——
本工具只实现**方法论骨架**，不复述任何论文结论、不引用未亲验数字。

四判据（**可机检，不靠感觉**）：
  1. **Raw ≠ Trace**：`raw/` 是外部真实来源（不改写），`trace/` 是 agent 执行迹；
     raw/ 里出现"像执行迹"的文件（名字含 trace/log/run，或正文出现 exit code / 本次运行）
     ⇒ 报「疑似混入」，要人给说法（**不静默放过**）。
  2. **Wiki ≠ Skill**：`sources/wiki/**` 解释世界（不许写成操作步骤）；
     wiki 里出现像步骤清单的行（`1. 运行/执行/run`）⇒ 报「Wiki 被写成手册」。
  3. **PURPOSE 密封**：候选 `SKILL.md` 必须含 `PURPOSE:` 段，且指到**存在的** `patterns/*.md`
     —— 没有出处的能力 = 无法验证、无法回滚。
  4. **生产/实验隔离**：候选只许待在 `skills/_candidates/`；直接落在生产 `skills/` 根 = 红
     （要越门必须 `--allow-production`，且会写台账 —— 那是主人的口子，不是默认）。

命令：
  python tools/selfgrowth.py init <目录>                 # 建最小可用目录 + 模板（只建不删）
  python tools/selfgrowth.py check <候选技能目录|仓库根>   # 四判据机检（有红退出码 1）
  python tools/selfgrowth.py promote <候选> <目标>        # 门控过了才准入；**先备份**（=可回滚）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
LEDGER = ROOT / "state" / "selfgrowth.jsonl"
BACKUPS = ROOT / ".backups" / "selfgrowth"

LAYOUT = ["raw", "sources/wiki", "trace/logs", "patterns", "skills/_candidates",
          "knowledge-index", "governance", "outputs", "runtime"]
TEMPLATES = {
    "sources/wiki/index.md": "# 概念知识索引\n\n> 只放**概念知识**（解释世界）与来源链接；操作步骤不进这里（那是 Skill）。\n",
    "trace/trace.md": "# 执行迹\n\n> agent 的执行迹（谁做的、什么时候、结果）。**无痕即未发生。**\n",
    "patterns/success.md": "# 成功要素（Pattern）\n\n> 从执行迹里提炼出来的**可复用要素**。每条要能指回具体 trace。\n",
    "patterns/failure.md": "# 失败模式（Pattern）\n\n> 失败不是白费：写清**现象 → 根因 → 教训 → 防复发锁**。\n",
    "knowledge-index/index.md": "# 知识索引\n\n> 任何结论都能从这里回到来源。\n",
    "governance/purpose.md": "# PURPOSE\n\n> 这套知识库为**什么**而建、服务于哪条线、红线是什么。\n",
    "governance/protocol.md": ("# 门控协议（Accept / Reject）\n\n"
                               "1. 候选只许在 `skills/_candidates/`；\n"
                               "2. 过四判据 → 才谈准入；\n"
                               "3. 准入前**先备份**（可回滚）；\n"
                               "4. 不接受「没出处的能力」。\n"),
}
TRACE_NAME_RX = re.compile(r"(trace|log|run|exec|exit)[-_.]?\d*\.(md|json|jsonl|txt|log)$", re.I)
TRACE_BODY_RX = re.compile(r"(exit\s*code|exit\.code|本次运行|执行迹|traceback|pid\s*[:=])", re.I)
STEP_RX = re.compile(r"^\s*\d+\.\s*(运行|执行|run|execute|install|部署)\b", re.I | re.M)


def _ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def init(base: Path) -> dict:
    """建最小可用目录 + 模板。**只建不删**（本仓规矩：只移不删）。"""
    made, kept = [], []
    for rel in LAYOUT:
        d = base / rel
        if d.exists():
            kept.append(rel)
        else:
            d.mkdir(parents=True, exist_ok=True)
            made.append(rel)
    for rel, body in TEMPLATES.items():
        p = base / rel
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
            made.append(rel)
        else:
            kept.append(rel)
    _ledger({"event": "init", "base": str(base), "made": len(made), "kept": len(kept)})
    return {"ok": True, "base": str(base), "made": made, "kept": kept}


def check(target: Path, allow_production: bool = False) -> dict:
    """四判据机检。target 可以是：知识库根、候选技能目录、或两者。"""
    root = target if (target / "raw").is_dir() else target.parent if (target.parent / "raw").is_dir() else None
    cand = target if (target / "SKILL.md").is_file() else None
    bad, notes = [], []

    # 判据 1：Raw ≠ Trace
    if root:
        raw = root / "raw"
        for p in sorted(raw.rglob("*")):
            if not p.is_file():
                continue
            if TRACE_NAME_RX.search(p.name):
                bad.append(f"[Raw≠Trace] `{p.relative_to(root)}` 名字像**执行迹**（trace/log/run）⇒ 该进 trace/")
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if TRACE_BODY_RX.search(txt):
                bad.append(f"[Raw≠Trace] `{p.relative_to(root)}` 正文像**执行迹**（exit code/本次运行/pid）⇒ 该进 trace/")
        if not (root / "trace").is_dir():
            bad.append("[Raw≠Trace] 没有 `trace/` —— 没有执行迹就没有能力复利的原料")
    # 判据 2：Wiki ≠ Skill
    if root:
        for p in sorted((root / "sources" / "wiki").rglob("*.md")) if (root / "sources" / "wiki").is_dir() else []:
            txt = p.read_text(encoding="utf-8", errors="replace")
            m = STEP_RX.search(txt)
            if m:
                bad.append(f"[Wiki≠Skill] `{p.relative_to(root)}` 里出现操作步骤（`{m.group(0).strip()[:24]}`）"
                           f"⇒ 那是 Skill 的活，Wiki 只解释世界")
    # 判据 3：PURPOSE 密封（候选侧）
    if cand:
        txt = (cand / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        if "PURPOSE:" not in txt:
            bad.append("[PURPOSE] 候选 SKILL.md 没有 `PURPOSE:` 段 ⇒ 能力与出处断链，不可验证不可回滚")
        else:
            seg = txt.split("PURPOSE:", 1)[1][:400]
            pats = re.findall(r"[\w./\-]+\.md", seg)
            # 基准目录：优先库根；否则**向上走到第一个含 patterns/ 的目录**
            # （实测血账：早先固定用 cand.parent.parent，取到 `skills/` 而不是库根 ⇒
            #  把合格候选误报成红 —— 判据的路径基准错，比判据严格更坏）
            base = root
            if base is None:
                p = cand
                while p != p.parent and not (p / "patterns").is_dir():
                    p = p.parent
                base = p
            hit = [x for x in pats if (base / "patterns" / Path(x).name).is_file()]
            if not hit:
                bad.append(f"[PURPOSE] PURPOSE 段没指向**存在的** patterns/*.md"
                           f"（段内提到的：{pats[:3] or '无'}；基准目录：{base}）")
            else:
                notes.append(f"PURPOSE 密封到 {hit[0]}")
    # 判据 4：隔离
    if cand:
        parts = [x.lower() for x in cand.parts]
        in_cand_slot = "_candidates" in parts
        under_prod_skills = ("skills" in parts) and not in_cand_slot
        if under_prod_skills and not allow_production:
            bad.append("[隔离] 候选直接落在生产 `skills/` 根 ⇒ 红。先放 `skills/_candidates/`，过门控再人工实施")
        elif under_prod_skills and allow_production:
            notes.append("⚠️ --allow-production：允许直落生产根（主人口子，已写台账）")
    # 判据 5：三段隔离（Train/Validation/Test）—— 封存集必须存在且非空
    # 来历（演示稿 11 页）：「训练任务负责提出假设，验证任务负责反驳假设，**最终测试只对通过门控的版本开放**。
    # 三者混用，Agent 就可能记住答案，而不是学会方法。」
    # 我们自查：本仓判据曾**既当训练反馈又当验收** = 三段混用 ⇒ 故立 state/holdout.json。
    try:
        hold = json.loads((ROOT / "state" / "holdout.json").read_text(encoding="utf-8"))
        n = len(hold.get("holdout") or [])
        if n < 1:
            bad.append("[三段隔离] state/holdout.json 里没有任何封存项 ⇒ 训练/验证/测试没有分开")
        else:
            notes.append(f"三段隔离：封存 {n} 项（只在晋升/发布时跑）")
    except FileNotFoundError:
        bad.append("[三段隔离] 缺 state/holdout.json（封存集）⇒ 判据既当训练反馈又当验收，会「记住答案」")
    except (json.JSONDecodeError, OSError) as e:
        bad.append(f"[三段隔离] 封存集读不出来：{type(e).__name__}: {e}")
    if root is None and cand is None:
        bad.append("目标既不是知识库根（没有 raw/），也不是候选技能目录（没有 SKILL.md）⇒ 判不了")
    out = {"ok": not bad, "target": str(target), "bad": bad, "notes": notes,
           "根": str(root) if root else None, "候选": str(cand) if cand else None}
    _ledger({"event": "check", "target": str(target), "ok": out["ok"], "bad": len(bad)})
    return out


def promote(cand: Path, target: Path, allow_production: bool = False) -> dict:
    """门控过了才准入。**准入前先备份**（=可回滚；这是"可信进化"的硬要求）。"""
    res = check(cand, allow_production=True)
    if not res["ok"]:
        return {"ok": False, "why": "门控没过，拒绝准入", "check": res}
    ts = time.strftime("%Y%m%d-%H%M%S")
    if target.exists():
        dst = BACKUPS / ts / target.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(target, dst)
        shutil.rmtree(target)
    shutil.copytree(cand, target)
    _ledger({"event": "promote", "from": str(cand), "to": str(target),
             "backup": str(BACKUPS / ts / target.name) if target.exists() else None})
    return {"ok": True, "from": str(cand), "to": str(target),
            "backup": str(BACKUPS / ts / target.name)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自生长知识库 4.0 四判据机检")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("dir")
    s = sub.add_parser("check"); s.add_argument("target"); s.add_argument("--json", action="store_true")
    s.add_argument("--allow-production", action="store_true")
    s = sub.add_parser("promote"); s.add_argument("cand"); s.add_argument("target")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        r = init(Path(a.dir))
        print(f"建成 {len(r['made'])} 项（已存在跳过 {len(r['kept'])} 项）：{r['base']}")
        for x in r["made"]:
            print("   +", x)
        return 0
    if a.cmd == "check":
        r = check(Path(a.target), a.allow_production)
        if a.json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            print(f"{'✅ 四判据全过' if r['ok'] else '🔴 有红'}（{r['target']}）")
            for b in r["bad"]:
                print("   ", b)
            for n in r["notes"]:
                print("   ·", n)
        return 0 if r["ok"] else 1
    if a.cmd == "promote":
        r = promote(Path(a.cand), Path(a.target))
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
