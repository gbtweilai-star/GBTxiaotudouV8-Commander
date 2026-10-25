# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""DD小分队 · 协作指挥群（文件即频道 / 任务板即指挥群）。

Owner 2026-09-19 设计，主公实现。**一句实话必须写在最前面**：

  ⚠️ 文件指挥群解决的是「**放置**」，不解决「**送达**」。
    2026-09-19 实测：传话通道不投递（spawn 初始消息 / followup ×2 全空），
    启动读物送得到但按纪律**不算指令**（子代理读到了当天账本却不认领 —— 它们做对了）。
    ⇒ 光把军令状放进 `.cluster/dd_squad/` 不会有人来领。
      真正通的派单通道是 **`HEARTBEAT.md`**：开工必读 · 定义上就是指令
      （AGENTS.md 原文 "Follow it strictly"）· 且 AGENTS.md 明确授权 agent 编辑它。
      所以本工具只做"板子 + 军令状 + 收账"，**派单那一脚走 HEARTBEAT.md**。

三个零件：
  board.json      任务板（状态机：待认领 / 进行中 / 已完成 / 通道阻塞）
  task_<ID>.md    军令状（含回执要求与自证句）
  report_<ID>.md  战报（小弟必须自己写；**不写就不算交付**）

用法：
    python -m gbt_allinone.tools.dd_squadron --deploy    # 下发军令状
    python -m gbt_allinone.tools.dd_squadron --collect   # 收账核对
    python -m gbt_allinone.tools.dd_squadron --status    # 看板
    python -m gbt_allinone.tools.dd_squadron --update DD-01 进行中 app2_3d
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DEVELOPER = "自由的风"
BRAND = "DD小分队 · 协作指挥群"

# ─────────────────────────────────────────────────────────────
# 兵团建制（Owner 2026-09-19 要求 50 人建制）
# ⚠️ 诚实口径（这一条是本文件最重要的东西）：
#   编制 ≠ 实有。2026-09-19 实测：传话通道不投递，root 能开的成员上限 3 个，
#   且开出来也收不到任务 ⇒ **那 47 个"预备役"现在并不存在**。
#   所以每个编制位必须带 `backed_by`：
#     backed_by 非空  → 真有成员在岗（值是真实成员 id）
#     backed_by 为空  → **空编**，只是"可征召的坑位"，不许显示成"在岗/抢修中"
#   `mobilize()` 只下**征召单**（写进征召队列 + HEARTBEAT 提示），
#   **不谎称"已唤醒"** —— 真正把它填上，只能由 root 真的 spawn 一个成员并回填 id。
# ─────────────────────────────────────────────────────────────
SPECIALTIES = ("前端", "后端", "视觉", "系统", "抢修")


@dataclass
class SquadMember:
    member_id: str
    name: str
    specialty: str
    status: str = "空编"            # 空编 / 在岗 / 任务中 / 抢修中
    current_task: str = ""
    backed_by: str = ""             # 真实成员 id；空 = 该编制位没人

    @property
    def is_real(self) -> bool:
        return bool(self.backed_by)


def _build_establishment() -> list:
    """50 人建制：3 个现役位（对应 DD-01..03）+ 47 个空编。

    现役位也标 `backed_by=""` —— 因为**它们也还没被真的填上**（DD-01 是我自己干的，
    DD-02/03 待认领）。等谁真的接了，再由 `--assign` 回填 id。
    """
    rows = [
        SquadMember("M-001", "现役-3D侦察兵", "视觉", "空编", "DD-01"),
        SquadMember("M-002", "现役-空白面排查兵", "前端", "空编", "DD-02"),
        SquadMember("M-003", "现役-安装节工程兵", "系统", "空编", "DD-03"),
    ]
    for i in range(4, 51):
        spec = SPECIALTIES[i % len(SPECIALTIES)]
        rows.append(SquadMember("M-%03d" % i, "预备-%s-%02d" % (spec, i), spec))
    return rows


@dataclass
class SquadTask:
    task_id: str
    title: str
    description: str
    assigned_to: str = "待认领"
    status: str = "待认领"          # 待认领 / 进行中 / 已完成 / 通道阻塞
    deliverable: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def task_file(self) -> str:
        return f"task_{self.task_id}.md"

    @property
    def report_file(self) -> str:
        return f"report_{self.task_id}.md"


DEFAULT_TASKS = (
    SquadTask("DD-01", "3D 与资源加载",
              "holo_pet/app.js:2126 写着「3D 引擎待安装」。查真因：面板前端期望哪个 3D 引擎/资源，"
              "是缺依赖、缺模型文件、缺路径、还是加载失败。能补就在 holo_pet/ 内补；"
              "补不了给出确切安装清单（包名+版本+来源）。必须用离屏截图工具或等价方式看过真实渲染，"
              "看不见就如实写「看不见」，不许假装看到。"),
    SquadTask("DD-02", "空白面排查",
              "主人两次抱怨面板「空空如也」。把 holo_pet 面板逐个段落跑一遍，找出渲染为空的段落，"
              "每个要双证据：① app.js 里对应 setup*() 往哪个 DOM id 写、什么条件下不写（函数名+行号）；"
              "② 该段落依赖的接口实测返回什么。产出空段落清单 + 原因分类。"),
    SquadTask("DD-03", "下载/安装节",
              "面板对 下载/install/apk/安装 的 grep 零命中，主人说过「要在 APP 上安装/下载却空白」。"
              "查清该不该有这一节；要补就按现有 UI 规范补（内容真可用、指向真实存在的脚本/文件/命令）；"
              "不能补就给硬理由。"),
)


class CommandCenter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.dir = self.root / ".cluster" / "dd_squad"
        self.board_file = self.dir / "board.json"
        self.roster_file = self.dir / "roster.json"
        self.draft_file = self.dir / "drafts.jsonl"      # 征召单队列
        self.dir.mkdir(parents=True, exist_ok=True)
        self.tasks = self._load()
        self.members = self._load_roster()

    def _load_roster(self) -> list:
        if self.roster_file.is_file():
            try:
                data = json.loads(self.roster_file.read_text(encoding="utf-8"))
                return [SquadMember(**m) for m in data]
            except Exception as exc:  # noqa: BLE001
                print("[兵团] 名册读取失败（保留原文件不覆盖）: %s" % exc)
                return _build_establishment()
        rows = _build_establishment()
        self._save_roster(rows)
        return rows

    def _save_roster(self, rows=None) -> None:
        rows = rows if rows is not None else self.members
        self.roster_file.write_text(
            json.dumps([asdict(m) for m in rows], ensure_ascii=False, indent=2),
            encoding="utf-8")

    def roster_summary(self) -> dict:
        """兵力**实报**：编制数、实有数、空编数分开算，不许合并成一个好看的数字。"""
        est = len(self.members)
        real = sum(1 for m in self.members if m.is_real)
        by_status = {}
        for m in self.members:
            by_status[m.status] = by_status.get(m.status, 0) + 1
        return {"编制": est, "实有": real, "空编": est - real,
                "按状态": by_status,
                "口径": "实有 = backed_by 非空（真有成员在岗）；其余一律算空编"}

    def assign(self, member_id: str, agent_id: str) -> dict:
        """把一名**真实成员**回填到编制位（这是唯一让「实有」增加的方式）。"""
        for m in self.members:
            if m.member_id == member_id:
                m.backed_by = str(agent_id)
                # ⚠️ 只写「在岗」，**不写「任务中」**：编制位挂着 DD-01，不代表这位成员
                #    真的在干 DD-01（实测它收不到任务）。在岗 ≠ 任务中，别让看板替它吹。
                #    要升到「任务中」，得等它真的交了 receipt/report（`--collect` 会给证据）。
                m.status = "在岗"
                self._save_roster()
                return {"ok": True, "member": member_id, "status": m.status,
                        "backed_by": m.backed_by,
                        "note": "在岗 = 这个编制位有真人；是否「任务中」要看它有没有交 receipt/report"}
        return {"ok": False, "error": "没有这个编制位: %s" % member_id}

    def mobilize(self, task_id: str, specialty: str) -> dict:
        """紧急调度：**只下征召单，不谎称已唤醒**。

        实测约束：传话通道不通 ⇒ 本函数**没有能力**真的叫醒谁。
        所以它做三件诚实的事：找一个空编位 → 写一张征召单入队 → 返回"待 root 派单"。
        编制位**保持空编**，直到 `--assign` 回填了真实成员 id。
        """
        pick = None
        for m in self.members:
            if not m.is_real and m.status == "空编" and m.specialty == specialty:
                pick = m
                break
        if pick is None:
            return {"ok": False, "error": "该专长没有空编位: %s" % specialty,
                    "roster": self.roster_summary()}
        draft = {
            "draft_id": "DR-%s-%s" % (task_id, specialty),
            "task_id": task_id, "specialty": specialty,
            "member_slot": pick.member_id,
            "at": datetime.now().isoformat(timespec="seconds"),
            "status": "待派单",
            "honest_note": ("本单只代表「该派一个人去」，**不代表已经有人**。"
                            "要真的补上，必须由 root spawn 一名成员并回填 backed_by。"),
            "how_to_fulfil": ("① root 开一个成员 → ② 拿到成员 id → "
                              "`dd_squadron --assign %s <成员id>`" % pick.member_id),
        }
        with self.draft_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(draft, ensure_ascii=False) + "\n")
        return {"ok": True, "woke": False, "draft": draft,
                "roster": self.roster_summary(),
                "note": "征召单已下；**没有人被唤醒** —— 传话通道不通，这件事我做不到。"}

    def drafts(self) -> list:
        if not self.draft_file.is_file():
            return []
        out = []
        for ln in self.draft_file.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:  # noqa: BLE001
                    continue
        return out

    def _load(self) -> list:
        if self.board_file.is_file():
            try:
                data = json.loads(self.board_file.read_text(encoding="utf-8"))
                return [SquadTask(**t) for t in data]
            except Exception as exc:  # noqa: BLE001
                print("[指挥群] 任务板读取失败（保留原文件不覆盖）: %s" % exc)
                return []
        return list(DEFAULT_TASKS)

    def save(self) -> None:
        self.board_file.write_text(
            json.dumps([asdict(t) for t in self.tasks], ensure_ascii=False, indent=2),
            encoding="utf-8")

    def deploy(self) -> dict:
        wrote = []
        for t in self.tasks:
            body = "\n".join([
                "# 【军令状】%s" % t.title,
                "",
                "## 任务编号", t.task_id,
                "",
                "## 任务描述", t.description,
                "",
                "## 回执要求（不做 = 没干）",
                "1. **开工前先落一个自证文件** `receipt_%s.md`，第一行原样写：" % t.task_id,
                "   `通道自证：我已读到 %s %s 号军令状，正在开工。`" % (BRAND, t.task_id),
                "   没有这句 ⇒ 说明你没收到任务 ⇒ **立刻停下报「通道不可用」，不许硬开工**。",
                "2. 干完把报告写进 `%s`，五段式：**结论 / 证据 / 分析 / 缺口与风险 / 建议落点**。" % t.report_file,
                "3. 每条断言标 **读数** 还是 **推断**；引用的文件/脚本必须真实存在（验过再写）。",
                "",
                "## 纪律（本项目传下来的）",
                "- 未测不按绿算 · 降级必须自曝 · 异常不许静默吞",
                "- **一改一验**：改完跑自检（`organ_check` / `selfscan` / 相关用例），把数字写进报告",
                "- 不许改 `AGENTS.md` / `MEMORY.md` / `USER.md` / `.cluster/expert-playbook.md`",
                "- 不许给自己发授权；需要授权写进「缺口与风险」",
                "",
                "（开发者：%s · %s · 禁止删除）" % (DEVELOPER, BRAND),
                "",
            ])
            p = self.dir / t.task_file
            p.write_text(body, encoding="utf-8")
            wrote.append({"task": t.task_id, "file": str(p), "bytes": len(body.encode("utf-8"))})
        self.save()
        return {"ok": True, "deployed": len(wrote), "files": wrote, "board": str(self.board_file)}

    def collect(self) -> dict:
        rows = []
        for t in self.tasks:
            receipt = self.dir / ("receipt_%s.md" % t.task_id)
            report = self.dir / t.report_file
            delivered = report.is_file()
            if delivered:
                t.status = "已完成"
            rows.append({"task": t.task_id, "title": t.title,
                         "receipt": receipt.is_file(), "report": delivered,
                         "bytes": report.stat().st_size if delivered else 0,
                         "status": t.status})
        self.save()
        return {"ok": True, "delivered": sum(1 for r in rows if r["report"]),
                "total": len(rows), "rows": rows}

    def update(self, task_id: str, status: str, who: str = "") -> dict:
        for t in self.tasks:
            if t.task_id == task_id:
                t.status = status
                if who:
                    t.assigned_to = who
                self.save()
                return {"ok": True, "task": task_id, "status": status, "assigned_to": t.assigned_to}
        return {"ok": False, "error": "没有这条任务: %s（现有 %s）"
                % (task_id, [t.task_id for t in self.tasks])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=BRAND)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--update", nargs="+", metavar="TASK_ID STATUS [WHO]")
    ap.add_argument("--roster", action="store_true", help="看兵团兵力（编制/实有/空编）")
    ap.add_argument("--mobilize", nargs=2, metavar=("TASK_ID", "SPECIALTY"),
                    help="下征召单（不唤醒任何人，见文件头说明）")
    ap.add_argument("--assign", nargs=2, metavar=("MEMBER_ID", "AGENT_ID"),
                    help="把真实成员回填到编制位（唯一让实有增加的方式）")
    ap.add_argument("--drafts", action="store_true", help="看征召单队列")
    a = ap.parse_args(argv)
    cc = CommandCenter(Path(a.root))
    if a.roster:
        s = cc.roster_summary()
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    if a.mobilize:
        r = cc.mobilize(a.mobilize[0], a.mobilize[1])
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if a.assign:
        r = cc.assign(a.assign[0], a.assign[1])
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0
    if a.drafts:
        for d in cc.drafts():
            print("%s  %s/%s  编制位 %s  [%s]" % (d.get("draft_id"), d.get("task_id"),
                                                  d.get("specialty"), d.get("member_slot"),
                                                  d.get("status")))
        return 0
    if a.deploy:
        r = cc.deploy()
        print("军令状已下发：%s 份" % r["deployed"])
        for f in r["files"]:
            print("  %-8s %s (%s bytes)" % (f["task"], f["file"], f["bytes"]))
        print("任务板：%s" % r["board"])
        print("\n⚠️ 下发 ≠ 送达。派单那一脚走 HEARTBEAT.md（见文件头说明）。")
        return 0
    if a.collect:
        r = cc.collect()
        for row in r["rows"]:
            mark = "已交付" if row["report"] else "未交付"
            print("%-8s %-12s 自证:%-6s 报告:%-6s %s"
                  % (row["task"], row["title"], row["receipt"], row["report"], mark))
        print("合计交付 %s / %s" % (r["delivered"], r["total"]))
        return 0
    if a.status:
        for t in cc.tasks:
            print("%-8s %-12s %-6s %s" % (t.task_id, t.title, t.status, t.assigned_to))
        return 0
    if a.update:
        r = cc.update(a.update[0], a.update[1], a.update[2] if len(a.update) > 2 else "")
        print(json.dumps(r, ensure_ascii=False))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
