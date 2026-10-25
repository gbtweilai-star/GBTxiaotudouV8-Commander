# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 脑库部署器：把"我们自己研发的脑"接到每个集群小弟身上。

Owner 2026-09-19：「所有小弟给他们部署上我们自己研发的这个」（脑库/记忆库）。

部署形态（**不新建常驻进程、不动平台 SOP**）：
  对每个 `.cluster/<task>/` 落一份 `brain-context.md` —— 小弟开工第一眼读的上下文：
    · 记忆总纲（摘录，限长）          来自 Obsidian 脑库（`brain_vault`）
    · 收集箱最近若干条                同上
    · 用户偏好台账摘要                来自 `trend_watch.digest`（爆火作品观察的产物）
    · 回写协议                        干完活把结论写回脑库（`brain_vault.remember`）

三条纪律：
  1. **默认空跑**：`--write` 才落盘；空跑逐条报"会写什么、多大"，不先斩后奏。
  2. **限长**：每份上下文有硬上限（默认 1600 字符），脑库只增不减，不设上限必膨胀。
  3. **不碰平台文件**：只写 `brain-context.md` 这一个新文件，
     **不改写、不覆盖** `plan.md` / `subagent_NN.md` / `expert-playbook.md`。

用法：
    python -m gbt_allinone.tools.brain_deploy             # 空跑（默认）
    python -m gbt_allinone.tools.brain_deploy --write     # 真落盘
    python -m gbt_allinone.tools.brain_deploy --json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

CLUSTER = ROOT / ".cluster"
TARGET_NAME = "brain-context.md"
BUDGET = 3000
CAP_BUDGET = 1600


def _vault_block(limit: int = 6) -> str:
    try:
        from gbt_allinone import brain_vault
        rc = brain_vault.recall(limit=limit)
        if not rc.get("ok"):
            return "· 脑库读取失败：%s" % rc.get("error")
        main = " ".join(str(rc.get("main_note") or "").split())[:600]
        recent = "\n".join("  - " + " ".join(str(x).split())[:110]
                           for x in (rc.get("recent") or [])[-limit:])
        st = brain_vault.status()
        return ("· 脑库：%s 篇笔记 · 双链 %s · 断链 %s\n"
                "· 记忆总纲（摘）：%s\n· 收集箱最近：\n%s"
                % (st.get("notes"), st.get("wikilinks"),
                   len(st.get("unresolved") or []), main or "（空）", recent or "  （空）"))
    except Exception as exc:  # noqa: BLE001
        return "· 脑库读取失败：%s" % f"{type(exc).__name__}: {exc}"[:120]


def _pref_block() -> str:
    try:
        from gbt_allinone import trend_watch
        d = trend_watch.digest(limit=200)
        tops = d.get("top_preferences") or []
        if not tops:
            return "· 用户偏好台账：样本 0 条（还没真实观测，**不许编偏好**）"
        lines = "\n".join("  - %s（%s 次）" % (t["preference"][:100], t["count"]) for t in tops[:5])
        return "· 用户偏好台账：样本 %s 条 · 按平台 %s\n%s" % (
            d.get("samples"), d.get("by_platform"), lines)
    except Exception as exc:  # noqa: BLE001
        return "· 用户偏好台账读取失败：%s" % f"{type(exc).__name__}: {exc}"[:120]


def _caps_block() -> str:
    """能力入口（**清单不复制**，只报计数与入口用法；唯一真相 = caps_registry）。"""
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        from collections import Counter
        doms = Counter(v.get("domain", "?") for v in BENIGN_CAPS.values())
        top = ", ".join("%s(%s)" % (k, v) for k, v in doms.most_common(8))
        from gbt_allinone.tentacle import bridge as TB
        cov = TB.coverage()
        return "\n".join([
            "· 本体能力：%s 个（域：%s …）—— 清单唯一真相 = caps_registry，别抄" % (len(BENIGN_CAPS), top),
            "· 怎么调：`run_task(\"<能力名>\", {…})`；不知道用哪个就给一句人话走",
            "  `run_task(\"brain_route\", {\"intent\":\"…\"})` 或 `brain_exec.execute(intent=\"…\")`",
            "· 长手的活：触手可调本体全部能力，且给意图自动命中 ——",
            "  `run_task(\"tentacle\", {\"intent\":\"…\"})`；方法清单 %s 个（动作 %s 个，覆盖率 %s%%）"
            % (cov.get("real_methods"), cov.get("denominator"), cov.get("intent_coverage_pct")),
            "· 语义路由（主路，需外部模型授权）：`gbt_allinone.semantic_route.route(人话)`；",
            "  不可用时它会 `degraded=True` 降级到启发式 —— 看到 degraded 就当它是「不确定」",
            "· 干活必须自述：`gbt_allinone.chain.declare(模块, 动作)` —— 角色/相位/交付物落审计+生命档案",
        ])
    except Exception as exc:  # noqa: BLE001
        return "· 能力清单读取失败：%s" % f"{type(exc).__name__}: {exc}"[:120]


LESSONS = (
    "1. **未测不按绿算**：拿不到分就记 0、算不出就记 UNK，禁止用默认满分兜底。",
    "2. **看过答案的样本就作废**：为修某句话改了词表，那批句子当场失去检验资格。",
    "3. **降级必须自曝**：主路挂了报 `degraded=True` + 真实原因；判不准就 `confident=False`。",
    "4. **写入前查指纹**：重复不落第二条，不靠写完再删。",
    "5. **异常不许静默吞**：兜底 except 也要把原因带回返回值（漏过 `life_error` 一次）。",
    "6. **探测要看真身**：委派壳（`__getattr__`）用 `dir()` 数不到方法 —— 数出 0，真身是 95。",
    "7. **不许用名字序裁决语义**：命中打平按字母序定胜负，会把中文意图判给英文名靠前的那个。",
    "8. **边界要看实测**：工作区外的路径写不进去（脑库报 `Errno 13`）；写不进就如实说，别假装。",
    "9. **环境限制 ≠ 代码 bug**：桌面/出网/硬件类红灯是环境没有，不是能力坏了，别乱改业务码。",
    "10. **一改一验**：每刀都要能被她的门或测试复验（`organ_check` / `selfscan` / 全量用例）。",
)


def _lessons_block() -> str:
    return "\n".join(LESSONS)


def render() -> str:
    """限长渲染（超长如实截断并说明，不静默丢）。"""
    body = "\n".join([
        "# 脑库上下文（开工先读这份 · 由 gbt_allinone 自动生成，请勿手改）",
        "",
        "## 一、现在的记忆",
        _vault_block(),
        "",
        "## 二、用户偏好（来自爆火作品观察）",
        _pref_block(),
        "",
        "## 三、回写协议（干完活必须做 —— 落点已按实测可写性修正）",
        "1. 结论/教训 → 写进**当天账本** `memory/YYYY-MM-DD.md`（工作区内，可写）。",
        "   ⚠️ 实测：直接 `brain_vault remember` 在本身份下**写不进去** ——",
        "   脑库位于 `Documents\\Codex\\ObsidianVault`，在工作区可写范围之外，",
        "   报 `[Errno 13] Permission denied`。脑库回写由**主人侧**做（或授权后做），",
        "   小弟只负责把内容落到当天账本，**不许假装写进脑库**。",
        "2. 观测到用户偏好 → `run_task(\"trend_watch\", {\"op\":\"observe\", …})`（工作区内，可写）。",
        "3. 不许删任何笔记；写入前查指纹（台账已内置）。",
        "",
        "## 四、你手里有什么能力（不用背名字）",
        _caps_block(),
        "",
        "## 五、干活心得与注意事项（踩过的坑，别重踩）",
        _lessons_block(),
        "",
        "> 本文件是**从脑库派生**的只读快照，不是第二份真相；脑库才是唯一真相。",
    ])
    if len(body) > BUDGET:
        body = body[:BUDGET] + "\n…（已按 %d 字符上限截断，全量见脑库本体）" % BUDGET
    return body


def plan_tasks() -> list:
    if not CLUSTER.is_dir():
        return []
    return sorted(d for d in CLUSTER.iterdir() if d.is_dir())


def run(write: bool = False):
    body = render()
    tasks = plan_tasks()
    rows = []
    for d in tasks:
        target = d / TARGET_NAME
        rows.append({"task": d.name, "target": str(target),
                     "exists": target.exists(),
                     "old_bytes": target.stat().st_size if target.exists() else 0,
                     "new_bytes": len(body.encode("utf-8")),
                     "action": "覆盖" if target.exists() else "新建"})
        if write:
            target.write_text(body, encoding="utf-8")
    return {"ok": True, "write": write, "context_chars": len(body),
            "tasks": len(rows), "rows": rows, "cluster": str(CLUSTER),
            "note": "只写 brain-context.md 一个新文件；不改 plan.md / subagent_NN.md / expert-playbook.md"}


def main(argv=None):
    argv = argv or sys.argv[1:]
    write = "--write" in argv
    r = run(write=write)
    if "--json" in argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    print("集群任务目录：%s 个（%s）" % (r["tasks"], r["cluster"]))
    print("上下文长度：%s 字符（上限 %s）" % (r["context_chars"], BUDGET))
    for row in r["rows"]:
        print("  %-20s %s → %s bytes（%s）"
              % (row["task"], row["action"], row["new_bytes"], row["target"]))
    print("模式：%s" % ("真落盘" if write else "空跑（加 --write 才落盘）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
