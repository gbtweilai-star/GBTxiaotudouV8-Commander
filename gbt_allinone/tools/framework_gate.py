# -*- coding: utf-8 -*-
r"""框架自改门（framework_gate）· R-H99（Owner 2026-09-19 拍板：下一刀做框架自改门，含测试）

为什么要有它
------------
产品有镜像门，框架自己一直裸奔：R-H95 / R-H96 / R-H98 三轮都改了框架源码，没有一次留下
"改前基线 → 改后证据 → 回滚点"。R-H96 §五 挂出的那个问题（框架自身改动要不要走镜像）结论是
**不塞进产品镜像**：那套矩阵是给交付物设计的（查入口 index.html/main.py、文本页署名、
无 _*.py 残留），套到框架源码上会误伤——_paths.py 是正常模块、__main__.py 不在入口白名单；
而且门是框架的一部分，让框架改动走框架自己的产品管线 = 递归绕圈。

所以另立一道门，只管一件事：**改框架自己，必须有账**。

三条硬规则（fail-closed）
------------------------
1. 改前有基线：snapshot 记下每个被监视文件的 sha256；没有基线 ⇒ verify 直接红（no_baseline）。
2. 改后有护照：open（为什么改）→ 动手 → close（证据 / 回滚点 / 印章）。
   close 缺件、或证据不是 "命令 => 读数" 的形状 ⇒ 拒绝关闭（rc=2）。
3. 没护照 = 红：verify 逐文件比对当前指纹与基线，任何变动必须被"已关闭、且 after 哈希与当前
   一致"的护照认领，否则 no_passport / stale_passport ⇒ rc=1。

**多脑复核（R-H105 · 主人 2026-09-19）**：一个 AI 可能犯傻，整个脑子不会同时傻 ——
所以"我自己说改好了"不算数。护照必须有**独立复核**：`--review "<checker>: <命令> => <读数>"`，
且 `checker` 与任何 `--evidence` 的标签**不许相同**（同一方既当运动员又当裁判 = 退回单方证据）。
机械上能查的是"形式独立"（标签不同、读数独立）；"复核是否真独立、是否真懂"查不了 —— 这条
边界如实写在 verify 输出里，不假装门能替人做判断。

分工：镜像门管"把成品放出去"，本门管"改框架自己"。共同纪律只有一条：没有证据的结论不采信。

用法
----
    python -m gbt_allinone.tools.framework_gate snapshot --label "R-H99 起点"
    python -m gbt_allinone.tools.framework_gate open --reason "修 X 的根因"
    python -m gbt_allinone.tools.framework_gate close --id fc-20260919T1130-ab12 \
        --evidence "py -3.10 gbt_allinone/tests/test_framework.py -k auth => Ran 6 tests OK" \
        --stamp .scratch/_stamp_xxx.json --rollback "按护照 before 哈希逐字节还原"
    python -m gbt_allinone.tools.framework_gate verify
    python -m gbt_allinone.tools.framework_gate status

--root 可指向别的工作区（测试用隔离树），--store 可指向别的账本目录（测试用临时目录）。
本工具只写自己的账本，不碰镜像维度、不碰生产面、不碰授权门。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import string
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# 监视范围：框架自身源码 + APP 侧源码（**改了会改变系统行为**的文件）
#
# R-H166（Owner 2026-09-19）：加 holo_pet_w3。实测教训（R-H165）——改了
# holo_pet_w3/shell/main.cjs（40,572 → 40,725 B，W3 壳的出口清单），而护照上记的是
# **changed_files: 0**。不是"没改"，是"门看不见它"：W3 3D 壳是真实产品面
# （holo_pet/启动3D数字人.bat 的入口壳），却在门的可见范围之外 ⇒ **账实不符**。
# 判据：**凡是"改了它，系统行为就会变"的源码面，都必须在可见范围内。**
# 逐个目录的判定与理由见 docs/自改门监视范围判定.md。
# R-H176 补齐三个缺口（登记簿 §五 G1/G2/G3 —— 全是"门看不见"的现场）：
#   G1 potato_pet/：checkpoint.py 的 PROD_TREE_ROOTS 含它、holo_pet 在读它的 config、
#      tests/test_framework.py 还把它插进 sys.path ⇒ **它的代码被框架测试真跑到**；
#   G2 .bat：启动器改一行就是行为变化（holo_pet 4 个 + potato_pet 2 个）；
#   G3 .json：被代码真读的"单一真相源"（dd_squad/toolchain_manifest.json）——
#      放宽成"全 json"会把 store/state 全卷进来，所以走**显式单文件**（见 _WATCH_EXTRA_FILES）。
# R-H249（Owner 2026-09-20 四类拍板 · 由"门盲区清单"长出的一刀）：
#   ① 纳入 `.ps1`：10 个真部署脚本就在 gbt_allinone/deploy/（backup / healthcheck /
#      install_service_windows …），改一行就换行为 —— 与 R-H176 的 `.bat` 缺口同族；
#   ② 纳入**根级行为面**：根级 `.md`（设计流程指令与 AGENTS.md 同级）+ 根级 `.bat` / `.py`
#      启动器（`deploy-app-one-click.bat` → `deploy_app_oneclick.py` 这一对就是真入口）。
#   ③ 图纸面**显式不纳**：`gbt_allinone/docs/*.md` 是设计文档/报告，改了不改运行时行为 ⇒
#      不占门的监视成本（但走 git / 待落刀登记，不是"没人管"）。声明见 docs/门盲区清单.md。
#   判据始终一句：**凡是"改了它，系统行为就会变"的源码面，都必须在可见范围内。**
# 🔴 2026-10-09 L2 口径（主人令「选择开始扫清所有故障和疑是故障的全部追踪根因彻底排查」）：
#   **生成物不由护照管，由「生成器 + 陈旧检测」管。**
#   判据（三条全中才算生成物，缺一条不许排除）：
#     ① 文件**自己声明**了「自动生成，别手改」；
#     ② 声明里给了**重建命令**（生成器在盘上、可复跑）；
#     ③ 它被 capability-audit 的 ARTIFACTS/陈旧检测覆盖（改了会被"陈旧"咬住）。
#   为什么这条不是"静默收窄"：门**每次 verify 都要把排除面与依据打出来**（见 verify 的
#   「生成物已排除」一栏）—— 范围看得见，才敢收。真源码（改了行为就变）一条都不许出圈。
_WATCH_GENERATED = (
    # (路径前缀, 生成器, 依据)
    ("holo_pet_w3/brain/caps/", "py -3.14 tools/codex-scripts/cap-pages.py",
     "页头自声明「自动生成，别手改」；一能力一页（94 页）"),
    ("holo_pet_w3/eye/frames.js", "py -3.14 tools/codex-scripts/eye-feed.py --loop",
     "页头自声明「由 eye-feed.py 生成 · 不要手改：下一次抓帧就覆盖」；"
     "**运行中的抓帧环持续改写它**，不排除则门永远红（这不是变更，是心跳）"),
    # 🔴 2026-10-23 补（判据翻正，留痕；实测 17 件未认领里 11 件是这批）：
    #    `holo_pet/assets/<面板>/index.html` 是 **monitor-loop 每 6 小时 `bake-all-pages` 的烘烤产物**
    #    —— 它们是**生成物**，不是源码：改它们不改任何行为，只有生成器的数据源变了才应当变。
    #    把它们算成「自改未记账」= 让调度器每 6 小时给账本加一批假变动，门红在自己制造的风里。
    #    口径只认这个前缀；`holo_pet/assets` 下的**手写**件若有，应移出该目录或改走生成器。
    ("holo_pet/assets/", "py -3.14 tools/codex-scripts/bake-all-pages.py（monitor-loop 每 6h 驱动）",
     "快照页由烘烤器从 state/ 数据重写；页内无手写内容；改了它不改行为"),
)
# R-H990（2026-10-15 · 主人令「必须补齐，绝对不能有任何盲区」）：
#   `tools/` 纳入。它是**在役脚本面**（561 个 .py：capability-bindings / supersede-check /
#   theme-render / gate_visibility …全是我们每天真跑的），2026-10-13 那次只点名纳了 1 件并写
#   「其余待主人点头再逐个纳」——主人今天点了头。代价：首次纳会一次算成 ~600 件变动（一次假红），
#   之后才是准的。判据同首句：**凡是"改了它，系统行为就会变"的源码面，都必须在可见范围内。**
_WATCH_DIRS = ("gbt_allinone", "holo_pet", "holo_pet_w3", "potato_pet", "tools",
               "tests", "deploy")   # R-H990：顶层 tests/ 与 deploy/ 也是真源码面
# R-H990：补**真源码后缀**（此前只有 7 个）。判据同首句——改了行为就变的后缀必须在表里：
#   `.ts` / `.tsx` / `.mjs`（脚本与前端源码）、`.toml` / `.tpl`（配置即源码、模板即真源）、
#   `.go` / `.rs` / `.rb` / `.php`（tools/ 下真有的源码）、`.ini`（pytest 口径）。
_WATCH_SUFFIX = (".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".html", ".css", ".bat", ".ps1",
                 ".toml", ".tpl", ".go", ".rs", ".rb", ".php", ".ini")
# 显式单文件：不在 _WATCH_DIRS 里、也不吃后缀规则，但**被代码真读**、改了行为就变。
#
# 🔴 2026-10-13 补（**踩出来的盲区**）：`tools/` 从来不在 `_WATCH_DIRS` 里 ⇒
#    `tools/codex-scripts/boot-selfcheck.py`（**开机自检本体**）改了门看不见。
#    现场：主人令把自检改成并发+面板，改完才发现**护照无文件可认领、关不上** ——
#    这正是本文件自己的判据「凡是『改了它，系统行为就会变』的源码面，都必须在可见范围内」
#    在打自己的脸。**全量纳入 `tools/` 会把 500+ 个既有件一次算成"新增变动"⇒ 假红**，
#    所以按既有机制走**显式单文件**，先纳**自检机件**这一件（其余待主人点头再逐个纳）。
_WATCH_EXTRA_FILES = (
    ".cluster/dd_squad/toolchain_manifest.json",
    "tools/codex-scripts/boot-selfcheck.py",
    # R-H990（2026-10-15 · 主人令「必须补齐，绝对不能有任何盲区」）：
    #   主题系统的**单一真源**落在 `state/`（不在 _WATCH_DIRS 里），生成器落在 `tools/`
    #   （同 2026-10-13 那次 `tools/` 缺口）⇒ 改了它们，四界面外观就变，却全在门盲区。
    #   按既有机制走**显式单文件**（全量纳入 `state/` / `tools/` 会把产物与 500+ 件一次算成变动⇒假红）。
    #   判据同本文件首句：**凡是"改了它，系统行为就会变"的源码面，都必须在可见范围内。**
    "tools/theme-render.py",                                  # 在役渲染引擎（能力位 theme_cap 直接加载）
    "state/theme/palettes/default.toml",                       # 单一色源：52 色 + 46 尺寸
    "state/theme/templates/window.css.tpl",                    # 四份模板真源（@@token@@）
    "state/theme/templates/deck3d.css.tpl",
    "state/theme/templates/styles.css.tpl",
    "state/theme/templates/skin-mission-control.css.tpl",
    # 主题模板与色源是第一位能力位的源头；上面 6 件已覆盖现役全量
)
# 根级**指令文件**：它们改一个字就能改系统行为，比源码更该留账（R-H99 第二刀）。
# 不含 USER.md / MEMORY.md —— 那两份是主人自己的记忆载体，另有归属规则，不属于"框架自改"。
_WATCH_ROOT_FILES = ("AGENTS.md", "HEARTBEAT.md", "CHARTER.md", "SOUL.md", "CODING_DISCIPLINE.md")
# R-H249：根级行为面**按后缀**收（不再只靠名字白名单）。
# 依据：根级那 13 个设计流程指令与 AGENTS.md 同级（运行时被读），
#       根级 .bat/.py 是启动器（deploy-app-one-click.bat → deploy_app_oneclick.py）。
# R-H990：补根级 `.cmd` 与 `.html` —— R-H249 ② 收了 `.bat` 却**漏了 `.cmd`**（本机 8 个启动器
#   全是 `.cmd`：auth / cliproxy / quick-scan / deepseek_watch / freebuff-start / hf-voice /
#   voicestudio / 接管V9-换脑启动），以及根级 7 个 `.html`（index / brain / capabilities /
#   media-console / skin-preview / V22 可交互原型 / V22 无限画布 = 主人入口产品面）。
_WATCH_ROOT_SUFFIX = (".md", ".bat", ".py", ".cmd", ".html", ".ts")   # .ts：根级 prisma7.config.ts（配置即源码）
# 主人自己的记忆载体：**显式不纳**（另有归属规则），不是"忘了纳"。
_WATCH_ROOT_EXCLUDE = ("USER.md", "MEMORY.md")
# 依赖树 / 缓存 / 产物 / 版本库：不是源码，改了也不该红（宁可漏报噪声，不许误报）
_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".pylibs", "store", ".scratch",
    "archive", "resources", "dist", "build", ".venv", "site-packages",
    # R-H176 建议落地：`.backups` 从"恰好没纳"改成"**显式声明不纳**"（免得以后被顺手纳进来）
    ".backups",
    # 🔴 2026-10-22 补（判据翻正，留痕；实测 236 件未认领里 24 件是这个）：
    #    `.wrangler/` 是 **wrangler 每次 dev/deploy 自己重写的构建临时区**
    #    （`deploy/cloud-10/.wrangler/tmp/bundle-*/middleware-*.js` 等）。
    #    它既不是源码、也没有"改了它行为就变"这回事 —— 把它算成"自改未记账"，
    #    等于每跑一次 wrangler 就给账本加一批**假变动**，门会红在自己制造的风里。
    ".wrangler",
}
# 🔴 2026-10-22 补（同上，留痕）：**归档目录**不纳监视。
#    口径只认前缀 `_archive`（本仓现存的 `holo_pet_w3/_archive-20261021/` 就是这类：
#    旧页/旧脚本整目录搬进去留档，**不在役**、不被运行时加载）。
#    不按"名字里带 archive"判，免得把将来真在役的 archive_service 误排掉。
_SKIP_DIR_PREFIX = ("_archive",)

# 🔴 R-H466 §61：门盲区**台账** —— §60 说「门必须知道自己看不见什么」；
#    §61 说「既然知道，就要把**盲区清单登记在册**」。
#    盲区面 = **图纸面**（gbt_allinone/docs/**.md）+ **记忆面**（memory/**.md）
#      —— 它们**显式不纳监视**（改了不改运行时行为），但**改了要留账**。
#    guard（机械）：close 时若 `changed_files == 0` 而盲区面**有改动** ⇒ 追加一条盲区日志；
#      同类累计 ⇒ 进「待纳入 / 显式不纳」判定（依据：§51「复发两次要事前拦」在门侧的应用）。
#    ⚠️ 本扫描**只看 mtime、不读内容**（不碰写路径、不碰 store）。
_BLINDSPOT_DIRS = ("gbt_allinone/docs", "memory")
_BLINDSPOT_SUFFIX = (".md",)


def _ts(iso: str) -> float:
    """把门自己写的 ISO 时间串换成时间戳（解析不了就返回 0 = 不筛）。"""
    try:
        return time.mktime(time.strptime(str(iso), "%Y-%m-%dT%H:%M:%S"))
    except Exception:  # noqa: BLE001
        return 0.0


def blindspot_scan(root: Path, since_ts: float) -> dict:
    """扫**盲区面**里比 since_ts 新的文件（只 stat，不读内容）。返回读数，不做判定。"""
    hits, scanned = [], 0
    for top in _BLINDSPOT_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                            if d not in _SKIP_DIRS
                            and not any(d.startswith(_p) for _p in _SKIP_DIR_PREFIX)]
            for name in filenames:
                if not name.lower().endswith(_BLINDSPOT_SUFFIX):
                    continue
                p = Path(dirpath) / name
                try:
                    mt = p.stat().st_mtime
                except OSError:
                    continue
                scanned += 1
                if since_ts and mt > since_ts:
                    hits.append(p.relative_to(root).as_posix())
    return {"scanned": scanned, "changed": len(hits), "samples": sorted(hits)[:10]}


def _blindspot_log(store: Path) -> Path:
    return store / "blindspot_log.jsonl"


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _default_store() -> Path:
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import _paths
        return Path(_paths.STORE_DIR) / "framework_changes"
    except Exception:  # noqa: BLE001
        return ROOT / "gbt_allinone" / "store" / "framework_changes"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


# 生成物的**自声明标记**：文件头自己写着"别手改/自动生成"才算（不是我们替它认领）。
_GEN_MARK = ("自动生成", "生成产物", "不要手改", "不许手改", "别手改")
_GEN_CMD = ("重生成", "重建", "render", "--loop", "生成：", "由 ")


def _is_generated(rel: str, path: Path = None) -> tuple:
    """这条是不是**生成物**（是 ⇒ 返回 (True, 生成器, 依据)）。

    🔴 判据看**文件自声明**，不是维护一张越来越长的路径表（2026-10-09 打地鼠教训：
       先列了 caps 页、又冒出 frames.js、再冒出 logbook-data.js —— 按路径列永远列不完）。
    三条全中才算（缺一条不许排除）：
      ① 文件头**自声明**「自动生成/生成产物/别手改」；
      ② 同一段里给了**重建/生成命令**字样；
      ③ 它由**运行中的生成器覆盖**（由 ①② 的存在证明；显式表 _WATCH_GENERATED 为兜底）。
    """
    for pref, gen, why in _WATCH_GENERATED:
        if rel.startswith(pref):
            return True, gen, why
    if path is not None and path.is_file() and rel.endswith(_WATCH_SUFFIX):
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:600]
        except OSError:
            return False, "", ""
        if any(m in head for m in _GEN_MARK) and any(c in head for c in _GEN_CMD):
            first = next((l.strip()[:80] for l in head.splitlines() if any(m in l for m in _GEN_MARK)), "")
            return True, "（自声明）", "文件头自声明生成物：" + first
    return False, "", ""


def _watched(root: Path) -> list:
    out = []
    for name in _WATCH_ROOT_FILES:
        p = root / name
        if p.is_file():
            out.append(p)
    # R-H249：根级行为面按后缀收（.md / .bat / .py）；主人记忆载体显式排除
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if not p.is_file() or p.name in _WATCH_ROOT_EXCLUDE:
                continue
            if p.name.lower().endswith(_WATCH_ROOT_SUFFIX):
                out.append(p)
    # R-H176：显式单文件（G3）——路径写死，不受后缀规则与目录范围影响
    for rel in _WATCH_EXTRA_FILES:
        p = root / rel
        if p.is_file():
            out.append(p)
    for top in _WATCH_DIRS:
        base = root / top
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                            if d not in _SKIP_DIRS
                            and not any(d.startswith(_p) for _p in _SKIP_DIR_PREFIX)]
            for name in filenames:
                if not name.lower().endswith(_WATCH_SUFFIX):
                    continue
                p = Path(dirpath) / name
                gen, _g, _w = _is_generated(p.relative_to(root).as_posix(), p)
                if gen:
                    continue          # 生成物：由生成器+陈旧检测管（理由与生成器名见 _WATCH_GENERATED）
                out.append(p)
    return sorted(out)


def fingerprint(root: Path) -> dict:
    """当前指纹：相对路径（/ 分隔）→ sha256。"""
    return {p.relative_to(root).as_posix(): _sha(p) for p in _watched(root)}


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _new_id() -> str:
    tail = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return "fc-%s-%s" % (time.strftime("%Y%m%dT%H%M%S"), tail)


def _baseline_path(store: Path) -> Path:
    return store / "baseline.json"


def _passports_dir(store: Path) -> Path:
    return store / "passports"


def _passports(store: Path) -> list:
    rows = []
    for p in sorted(_passports_dir(store).glob("*.json")):
        d = _load(p)
        if d.get("id"):
            d["_path"] = str(p)
            rows.append(d)
    return rows


def _label_of(entry: str) -> str:
    """证据条目的"出具方"标签：`--review` 用 `<checker>: ...` 显式声明；evidence 取第一段。"""
    text = str(entry or "").strip()
    if ":" in text.split("=>")[0]:
        head = text.split(":", 1)[0].strip()
        if head and " " not in head:
            return head
    return text.split("=>")[0].split()[0] if text.split("=>")[0].split() else ""


def _diff(before: dict, after: dict) -> dict:
    return {k: {"before": before.get(k), "after": after.get(k)}
            for k in set(before) | set(after) if before.get(k) != after.get(k)}


def cmd_snapshot(args) -> int:
    root, store = Path(args.root).resolve(), Path(args.store).resolve()
    # 坑册第 30 条（R-H107）：**基线不能吞护照**。任何能抹掉变更证据的动作，
    # 本身必须先被门挡一次 —— 开着护照重立基线，会让"没护照=红"这条规则被绕过
    # （实测踩过：护照还开着，verify 却先变绿了）。
    open_ps = [p for p in _passports(store) if not p.get("closed_at")]
    if open_ps and not getattr(args, "force", False):
        print(json.dumps({
            "ok": False, "stage": "snapshot", "blocked": True,
            "reason_code": "passport_open",
            "open_passports": [p["id"] for p in open_ps],
            "error": "存在未关闭护照：重立基线会把它们的改动吞进基线，等于抹掉变更证据",
            "how_to": "先 close 那些护照；确要吞掉就显式 --force --reason \"为什么值得\"（这次吞并会留痕）",
        }, ensure_ascii=False, indent=1))
        return 2
    fp = fingerprint(root)
    rec = {"at": _now(), "label": args.label or "", "note": args.note or "",
           "root": str(root), "files": fp, "count": len(fp),
           "forced_over_open_passports": [p["id"] for p in open_ps] if open_ps else [],
           "force_reason": (getattr(args, "reason", "") or "") if open_ps else ""}
    _save(_baseline_path(store), rec)
    out = {"ok": True, "stage": "snapshot", "at": rec["at"],
           "label": rec["label"], "files": len(fp), "store": str(store)}
    if open_ps:
        # 坑册一族（R-H141 实测）：**吞并 ≠ 结案**。被吞的护照仍然是"开着"的，
        # 所以它**会继续挡下一次 snapshot**。不提示的话，操作者以为吞完就完了。
        out["forced_note"] = ("被吞的护照仍在开：%s —— 要么 close 它们，要么它们会继续挡下一次 snapshot"
                              "（吞并 ≠ 结案）" % ", ".join(p["id"] for p in open_ps))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_open(args) -> int:
    root, store = Path(args.root).resolve(), Path(args.store).resolve()
    reason = (args.reason or "").strip()
    if len(reason) < 8:
        print(json.dumps({"ok": False, "stage": "open", "reason_code": "reason_too_short",
                          "error": "reason 太短：自改护照必须写清『为什么改』（>=8 字）"},
                         ensure_ascii=False, indent=1))
        return 2
    cid = _new_id()
    rec = {"id": cid, "opened_at": _now(), "closed_at": None, "label": args.label or "",
           "reason": reason, "root": str(root), "before": fingerprint(root), "after": None,
           "evidence": [], "rollback": "", "stamp": None, "no_stamp_reason": "",
           "decision": "", "changed": {}}
    _save(_passports_dir(store) / (cid + ".json"), rec)
    print(json.dumps({"ok": True, "stage": "open", "id": cid, "reason": reason,
                      "files_at_open": len(rec["before"])}, ensure_ascii=False, indent=1))
    return 0


def cmd_close(args) -> int:
    store = Path(args.store).resolve()
    path = _passports_dir(store) / (args.id + ".json")
    rec = _load(path)
    if not rec:
        print(json.dumps({"ok": False, "stage": "close", "reason_code": "passport_not_found",
                          "error": "找不到护照 " + args.id}, ensure_ascii=False, indent=1))
        return 2

    # 🔴 F39 根治：先把「相对基线的偏差」算出来 —— 它是**认领范围的来源**，而范围必须
    #    在**校验阶段**就参与判决（不能像原来那样等到写库时才第一次出现）。
    after = fingerprint(Path(args.root).resolve())
    base_files = (_load(_baseline_path(store)).get("files") or {})
    ref = base_files or (rec.get("before") or {})
    pending = _diff(ref, after)

    problems = []
    evidence = [str(e).strip() for e in (args.evidence or []) if str(e).strip()]
    if not evidence:
        problems.append("缺证据：--evidence 至少一条")
    if any("=>" not in e for e in evidence):
        problems.append("证据形状不对：每条都要写成『命令 => 读数』")
    rollback = (args.rollback or "").strip()
    if len(rollback) < 8:
        problems.append("缺回滚点：--rollback 要说清怎么退回去（>=8 字）")
    stamp = None
    if args.stamp:
        sp = Path(args.stamp)
        if not sp.exists():
            problems.append("--stamp 指向的文件不存在：" + str(sp))
        else:
            stamp = {"path": str(sp), "sha256": _sha(sp), "at": _now()}
            data = _load(sp)
            if isinstance(data, dict) and data:
                # 🔴 2026-09-23 第 51 轮修（**"四元组"少了两元却一声不响**）：
                #    这里原来只写 `if k in data` —— 而印章文件里**没有** `python`/`comparability`
                #    这两个键（实测盘上 52 个印章，四元组齐的 **0 个**），
                #    于是护照里的"四元组"长期只记到 **2/4**，**没有任何提示**。
                #    ⇒ 取到的照旧记；**取不到的必须列出来**（缺项 = 未知，不是"没有这一项"）。
                _want = ("python", "store", "comparability", "identity")
                stamp["four_tuple"] = {k: data.get(k) for k in _want if k in data}
                _miss = [k for k in _want if k not in data]
                if _miss:
                    stamp["four_tuple_missing"] = _miss
                    stamp["four_tuple_note"] = (
                        "印章里**没有**这几个键：%s ⇒ 四元组只记到 %d/4。"
                        "缺项是**未知**，不是『这一项没问题』。"
                        % ("、".join(_miss), len(stamp["four_tuple"])))
                    # 只**报**、不阻断：把它塞进 problems 会改变关门判决（那是主人的口径决定）。
                    print("[gate] ⚠️ 印章四元组不全：缺 %s（只记到 %d/4）"
                          % ("、".join(_miss), len(stamp["four_tuple"])), file=sys.stderr)
    elif not (args.no_stamp_reason or "").strip():
        problems.append("缺回归印章：给 --stamp <印章.json>，或显式写 --no-stamp-reason 『为什么这轮没法盖章』")

    # 多脑复核（R-H105）：单方证据不许算过关
    reviews = [str(r).strip() for r in (args.review or []) if str(r).strip()]
    if not reviews and not (args.no_review_reason or "").strip():
        problems.append("缺独立复核：给 --review \"<checker>: <命令> => <读数>\"（另一个 checker 出具的读数），"
                        "或显式写 --no-review-reason 『为什么这轮没有独立复核』")
    if any("=>" not in r for r in reviews):
        problems.append("复核形状不对：每条复核都要写成『<checker>: <命令> => <读数>』")
    if reviews:
        ev_labels = {_label_of(e) for e in evidence if _label_of(e)}
        rv_labels = {_label_of(r) for r in reviews if _label_of(r)}
        same = sorted(ev_labels & rv_labels)
        if same:
            problems.append(f"复核不独立：{same} 同时出现在证据与复核里（同一方既当运动员又当裁判）")
        if len(rv_labels) < len(reviews):
            problems.append("复核缺 checker 标签：每条复核都要以 `<checker>: ` 开头")

    # ── 🔴 认领范围闸（F39 根治 · 本文件曾经最大的假绿来源）────────────────────────
    # 病史：`changed` 由 `_diff(整份基线, after)` 得出 ⇒ 护照**没有范围这个概念**，
    #      关一张只讲 A 的护照会把 A+B+C…**整批**记进它的账。
    #      F31 认领 20 个（19 个早于 opened_at）· F39 理由写 2 个、实际 22 个 —— **两次都因此把红洗成绿**。
    # 修法：范围必须在**判决阶段**就落地，而不是事后解释。
    _root_res = Path(args.root).resolve()
    declared = []
    for _d in (getattr(args, "files", None) or []):
        _d = str(_d).strip()
        if not _d:
            continue
        _p = Path(_d)
        if _p.is_absolute():
            try:
                _d = str(_p.resolve().relative_to(_root_res))
            except Exception:  # noqa: BLE001
                pass
        declared.append(_d.replace("\\", "/"))
    if declared:
        _not_pending = [d for d in declared if d not in pending]
        if _not_pending:
            problems.append(
                "--files 里有文件**相对基线没有变动**（或路径写错）：%s。"
                "认领一个没变的文件 = 账目虚增，一律拒。" % _not_pending)
        claimed = {k: v for k, v in pending.items() if k in set(declared)}
    else:
        claimed = dict(pending)
        if len(pending) > 1:
            problems.append(
                "**认领范围未声明**：当前相对基线有 %d 个文件变动，"
                "必须用 --files 逐个列出你要认领的那些（可重复给）。"
                "不带 --files 会把 %d 个文件**整批**记进这一张护照 —— "
                "「我只改了这个」在账里就表达不出来了，一张理由不符的护照足以把红洗成绿。"
                % (len(pending), len(pending)))
    unclaimed = sorted(set(pending) - set(claimed))

    if problems:
        print(json.dumps({"ok": False, "stage": "close", "id": args.id, "blocked": True,
                          "problems": problems, "reason_code": "passport_incomplete",
                          "note": "拒绝关闭：护照不完整就不算改完（fail-closed）"},
                         ensure_ascii=False, indent=1))
        return 2

    # 认领范围 = **显式声明的那几个**（不再等于"所有偏差"）。
    # ⚠️ 保留 R-H99 的教训：范围仍以**相对基线的偏差**为基准（不是"开护照那一刻"），
    #    因为真实顺序常常是"先改、后想起开护照"，按 open→close 算会认领不到 ⇒ verify 永远红。
    rec.update({"closed_at": _now(), "after": after, "evidence": evidence,
                "review": reviews,
                "no_review_reason": (args.no_review_reason or "").strip(),
                "rollback": rollback, "stamp": stamp,
                "no_stamp_reason": (args.no_stamp_reason or "").strip(),
                "decision": (args.decision or "").strip(),
                "changed": claimed,
                "declared_scope": declared,
                "claimed_all_pending": not declared,
                "pending_at_close": sorted(pending),
                "unclaimed_after_close": unclaimed,
                "changed_ref": "baseline" if base_files else "open_state",
                "open_diff": _diff(rec.get("before") or {}, after)})
    # 🔴 R-H466 §61：**盲区台账** —— changed_files==0 但有实际改动时，必须留账
    blindspot = blindspot_scan(Path(args.root).resolve(), _ts(rec.get("opened_at")))
    rec["blindspot"] = blindspot
    logged = None
    if not rec["changed"] and blindspot["changed"] > 0:
        logged = {"at": _now(), "id": rec.get("id"), "label": rec.get("label") or "",
                  "changed_files": 0, "blindspot_changed": blindspot["changed"],
                  "scanned": blindspot["scanned"], "samples": blindspot["samples"],
                  "rule": "R-H466 §61：changed_files=0 但盲区面（图纸/记忆）有改动 ⇒ 记一条"}
        _append_jsonl(_blindspot_log(store), logged)
    _save(path, rec)
    print(json.dumps({"ok": True, "stage": "close", "id": args.id,
                      "changed_files": len(rec["changed"]),
                      "changed": sorted(rec["changed"])[:20],
                      "认领方式": ("显式 --files 声明" if declared else "未声明（变动只有 1 个，恰好认领它）"),
                      "声明范围": declared or None,
                      "**本次未认领**（≠ 无人认领，别的护照可能已兜着它 —— 以 verify 为准）": unclaimed,
                      "has_stamp": bool(stamp), "closed_at": rec["closed_at"],
                      "blindspot": blindspot, "blindspot_logged": bool(logged)},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_verify(args) -> int:
    root, store = Path(args.root).resolve(), Path(args.store).resolve()
    base = _load(_baseline_path(store))
    if not base.get("files"):
        print(json.dumps({"ok": False, "stage": "verify", "verdict": "red",
                          "reason_code": "no_baseline",
                          "how_to": "先跑 snapshot 立基线，再改框架源码"},
                         ensure_ascii=False, indent=1))
        return 1

    current = fingerprint(root)
    changed = _diff(base["files"], current)
    closed = [p for p in _passports(store) if p.get("closed_at") and p.get("after")]
    findings = []
    covered_by = {}
    for rel, info in sorted(changed.items()):
        owners = [p for p in closed if rel in (p.get("changed") or {})]
        fresh = [p for p in owners if (p.get("after") or {}).get(rel) == info["after"]]
        if not owners:
            findings.append({"file": rel, "reason_code": "no_passport",
                             "detail": "改了但没有自改护照认领"})
        elif not fresh:
            findings.append({"file": rel, "reason_code": "stale_passport",
                             "detail": "护照之后又改过；涉及护照 "
                                       + str(sorted(p["id"] for p in owners))})
        # 🔴 F39 加固：**分层输出** —— 不只给红绿，还要给出"这个文件是被谁的哪条理由认领的、
        #    那张护照当时有没有声明范围"。读者据此自己判这个 green 值不值得采信。
        covered_by[rel] = {
            "现状": "已覆盖且新鲜" if fresh else ("被覆盖但已过期" if owners else "无护照认领"),
            "认领护照": [{"id": p["id"], "reason": (p.get("reason") or "")[:90],
                          "声明范围": (p.get("declared_scope") or "**未声明 · 整批认领**"),
                          "整批认领": bool(p.get("claimed_all_pending")),
                          "新鲜": p in fresh} for p in owners],
        }
    # 历史遗留：**没声明范围却认领了多个文件**的护照 —— 这些是"范围含糊"的账，单独点名。
    # 🔴 加固（2026-09-25 实测抓到自己的洞）：老护照里**根本没有** `declared_scope` /
    #    `claimed_all_pending` 这两个键（实测 fhnb：两键皆 None）。第一版探测器写成
    #    `p.get("claimed_all_pending") and …` ⇒ **历史那批一个都抓不到**，而它们恰恰就是
    #    F31/F39 那一批。改成按**事实**判：**没有声明范围** 且 认领了 >1 个文件 ⇒ 含糊。
    overbroad = sorted(p["id"] for p in closed
                       if (not p.get("declared_scope")) and len(p.get("changed") or {}) > 1)
    out = {"ok": not findings, "stage": "verify",
           "verdict": "green" if not findings else "red",
           "baseline_at": base.get("at"), "baseline_files": base.get("count"),
           "changed_files": len(changed), "passports_closed": len(closed),
           "已认领且新鲜": sum(1 for v in covered_by.values() if v["现状"] == "已覆盖且新鲜"),
           "未认领": sum(1 for v in covered_by.values() if v["现状"] == "无护照认领"),
           "认领但已过期": sum(1 for v in covered_by.values() if v["现状"] == "被覆盖但已过期"),
           "covered_by": covered_by,
           "范围含糊的旧护照": overbroad,
           "范围含糊说明": ("上面这些护照**没声明范围**却认领了多个文件（F31/F39 同源）—— "
                            "它们的账**可能与理由不符**，读到 green 时请对照 covered_by 自己判。"),
           "stamp_waived_passports": [p["id"] for p in closed if not p.get("stamp")],
           "review_waived_passports": [p["id"] for p in closed if not (p.get("review") or [])],
           "findings": findings,
           "law": "改框架自己也要有账：改前基线 → 改后护照（原因/证据/**独立复核**/回滚）→ 没护照就是红",
           "honest_limit": ("门能查的是**形式独立**（复核 checker 标签不同、读数独立）；"
                            "复核到底独不独立、懂不懂，门查不了 —— 那一步只能靠人或多脑交叉，不假装门能替。")}
    if findings and args.json:
        out["changed"] = {k: v["after"] for k, v in list(changed.items())[:50]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if not findings else 1


def cmd_status(args) -> int:
    store = Path(args.store).resolve()
    base = _load(_baseline_path(store))
    rows = [{"id": p["id"], "opened_at": p.get("opened_at"), "closed_at": p.get("closed_at"),
             "reason": p.get("reason"), "changed_files": len(p.get("changed") or {}),
             "has_stamp": bool(p.get("stamp")),
             "complete": bool(p.get("closed_at") and p.get("evidence") and p.get("rollback"))}
            for p in _passports(store)]
    print(json.dumps({"ok": True, "stage": "status", "store": str(store),
                      "baseline_at": base.get("at"), "baseline_files": base.get("count"),
                      "passports": rows, "count": len(rows)}, ensure_ascii=False, indent=1))
    return 0


def cmd_blindspots(args) -> int:
    """§61：门盲区**台账**（只读）—— 每次「changed_files=0 但盲区面有改动」都在这里。"""
    store = Path(args.store).resolve()
    log = _blindspot_log(store)
    rows = []
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    by_suffix = {}
    for r in rows:
        for one in (r.get("samples") or []):
            ext = Path(one).suffix.lower() or "(无后缀)"
            by_suffix[ext] = by_suffix.get(ext, 0) + 1
    print(json.dumps({"ok": True, "stage": "blindspots", "count": len(rows),
                      "by_suffix": by_suffix, "recent": rows[-5:],
                      "watched_suffix": list(_WATCH_SUFFIX),
                      "blindspot_dirs": list(_BLINDSPOT_DIRS),
                      "note": "§61：门必须**知道自己看不见什么**，并且**既然知道就要登记在册**；"
                              "同类累计 ⇒ 进「待纳入 / 显式不纳」判定（依据 §51）"},
                     ensure_ascii=False, indent=1))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="框架自改门：改框架自己必须留账（fail-closed）")
    ap.add_argument("--root", default=str(ROOT), help="工作区根（默认本仓；测试可指隔离树）")
    ap.add_argument("--store", default=str(_default_store()),
                    help="账本目录（默认 store/framework_changes）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("snapshot", help="立基线：记下当前所有被监视文件的 sha256")
    s1.add_argument("--label", default="")
    s1.add_argument("--note", default="")
    s1.add_argument("--force", action="store_true",
                    help="存在未关闭护照时仍要立基线（=承认会吞掉变更证据，必须配 --reason）")
    s1.add_argument("--reason", default="", help="--force 时必填：为什么值得吞")
    s1.set_defaults(func=cmd_snapshot)

    s2 = sub.add_parser("open", help="开一张自改护照（写清为什么改）")
    s2.add_argument("--reason", required=True)
    s2.add_argument("--label", default="")
    s2.set_defaults(func=cmd_open)

    s3 = sub.add_parser("close", help="关闭护照（证据 / 回滚点 / 印章，缺一不可）")
    s3.add_argument("--id", required=True)
    s3.add_argument("--evidence", action="append", default=[])
    s3.add_argument("--review", action="append", default=[],
                    help="独立复核（多脑复核）：\"<checker>: <命令> => <读数>\"，checker 不许与证据同标签")
    s3.add_argument("--no-review-reason", default="",
                    help="确无独立复核时显式写原因（verify 会把它当豁免列出来）")
    s3.add_argument("--rollback", default="")
    s3.add_argument("--files", action="append", default=[],
                    help="🔴 显式声明本护照**认领哪些文件**（可重复）。"
                         "不声明时：变动只有 1 个文件才允许（等于恰好认领它）；"
                         "变动 >1 个文件时**必须**逐个列出 —— 否则一张理由不符的护照"
                         "会把整批未记账变动洗成『有账』（F31/F39 同源事故）")
    s3.add_argument("--stamp", default="")
    s3.add_argument("--no-stamp-reason", default="")
    s3.add_argument("--decision", default="")
    s3.set_defaults(func=cmd_close)

    s4 = sub.add_parser("verify", help="对账：有变动没护照 ⇒ 红（rc=1）")
    s4.add_argument("--json", action="store_true", help="附上变动文件清单")
    s4.set_defaults(func=cmd_verify)

    s5 = sub.add_parser("status", help="看基线 + 护照清单（只读）")
    s5.set_defaults(func=cmd_status)

    s6 = sub.add_parser("blindspots", help="§61 门盲区台账：changed_files=0 但有改动的每一次（只读）")
    s6.set_defaults(func=cmd_blindspots)
    return ap


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
