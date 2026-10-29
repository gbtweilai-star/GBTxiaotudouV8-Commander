# -*- coding: utf-8 -*-
# gbt-instrument: 本件是**量具**（枚举仓内路径来决定搬谁），所以它自己提到的路径
#   不算"有人引用" —— 见 referenced_names() / instrument_files() 的注释。
#   2026-09-23 第 30 轮加：不加这个标记，PAGE_TARGETS 里写了谁，谁就永远清不掉。
"""残骸清理器 · **进回收站**（不硬删）· 带引用守卫（2026-09-23 Owner 令）。

## 为什么要有守卫

Owner 说"把该清理的清理出去到回收站就好了"。但本仓的 `.scratch` **不是**纯垃圾堆：
它被 `checkpoint.py` 定义为"一次性工作区（备份/暂存/探针产物，按设计天天变）"，
而**同一片目录里同时住着活代码正在读写的东西**，实测至少这些：

    .scratch/_traces/            ← gbt_allinone/tools/exec_trace.py:44  TRACE_DIR
    .scratch/_dsh_home/          ← holo_pet/panel_server.py:2736
    .scratch/vision_probe/       ← gbt_allinone/tools/vision_probe.py:28
    .scratch/scan-20260923/      ← tools/codex-scripts/omni.py（本地工具面两条）
    .scratch/_deploy_app_last.json / _organ_check.json / _stamp_*.json
    .scratch/*_ledger.jsonl      ← holo_pet_w3/ledger/sink.py（默认承载物）
    .scratch/_w3_layout_tests_result.json ← holo_pet_w3/tests/run_tests.py:44
    .scratch/_panel_audit.json / _gbt_catalog.json / _cross_scan_panels.json ← plugins/gbt-master/tools/
    .scratch/旁观者契约稿.md / DSH旁观者接入设计稿.md ← panel_server.py:399 当证据读

⇒ **无脑 `rm -rf .scratch` 会当场弄坏面板、留痕、跑测、面板审计。**
所以本件按**引用守卫**办事：候选项的**文件名**只要在仓内代码/配置/文档里出现过，
一律**不搬**，并在报告里逐条写明"因为谁在引用"。守卫是**宁多留不误删**的方向。

## 分层（每层都能单独跑）

    build    __pycache__ 目录 + 散落 *.pyc/*.pyo            ← 纯构建产物，零风险
    trash    .trash/ 下的东西                                ← 它本身就是回收暂存区
    backups  .backups/ 下的东西                              ← 历次作业的旧备份快照
    temp     本工具自家在 %TEMP% 落的扫描产物                ← gbt-quickscan / gbt-capprobe* / 隔离 store
    scratch  .scratch 下**名字即残骸**（_*.py / *.tmp / *.bak / *.old …）且**无人引用**的
    tempscan .scratch 下**旧的平铺扫描产物**（scan_v*.json / _xscan.json …）且无人引用

## 用法

    py -3.14 tools/codex-scripts/clean_residue.py                 # 只出清单（默认，不动盘）
    py -3.14 tools/codex-scripts/clean_residue.py --tier build    # 只看某一层
    py -3.14 tools/codex-scripts/clean_residue.py --go            # 真搬进回收站
    py -3.14 tools/codex-scripts/clean_residue.py --go --tier build,trash,backups,temp

## 纪律

  · **只进回收站**（`Microsoft.VisualBasic.FileIO.FileSystem` 的 `SendToRecycleBin`），可还原；
  · 删之前**先报**：条数 / 体积 / 被守卫拦下的逐条理由；
  · 引用守卫**扫描的是全仓文本面**（`git grep`），不是"我记得没人用"；
  · 生产 store（`gbt_allinone/store/`）、git 索引（`git rm --cached`）**都不碰** ——
    那两件是另外的题目，需要单独的决断。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent

# 与 quick_scan 的 P3 面同一套残骸正则（口径不许有两份）
RESIDUE_RE = re.compile(r"(^_\w+\.py$)|(\.tmp$)|(\.temp$)|(\.bak$)|(\.old$)"
                        r"|(\.orig$)|(\.rej$)|(~$)|(\.swp$)|(^~\$)", re.I)

# .scratch 下**永远不动**的（活代码读写目标；守卫之外再加一层白名单，防守卫漏判）
SCRATCH_KEEP = {
    "_traces", "_dsh_home", "vision_probe", "scan-20260923", "_deploy_app_last.json",
    "_organ_check.json", "旁观者契约稿.md", "DSH旁观者接入设计稿.md",
    "_panel_audit.json", "_gbt_catalog.json", "_cross_scan_panels.json",
    "_w3_layout_tests_result.json",
}

# 旧平铺扫描产物（名字精确匹配；仍要过守卫）
TEMPSCAN_NAMES = {
    "scan_v2.json", "scan_v3.json", "scan_v4.json", "scan_v5.json",
    "_xscan.json", "workspace_inventory.json", "_shadow_filelist.json",
    "relay_dump.jsonl",
}

_TEMP_PREFIXES = ("gbt-quickscan", "gbt-capprobe", "gbt_scan_store_",
                  "gbt-smoke-store", "gbt_capprobe_iso_", "q-a.json", "q-b.json")

# ── pages 档：仓根/固定位置的**生成镜像与临时页**（版本族由 plan() 现算，不在此列）──
# 每条都必须写得出理由；写不出理由的不许进这张表。
PAGE_ARCHIVE = ROOT / "archive"
PAGE_TARGETS = [
    (".shadow-repo",
     "整份影子仓：`build_shadow_repo.py` 生成 + `.gitignore` 已列 ⇒ 可重建；"
     "它是**重复页面最大的一个来源**（206 个 html / 15.5MB）"),
    (".scratch/_v22_stage", "V22 施工暂存 —— 现行版已在仓根"),
    (".scratch/_recovered", "V21 恢复副本 —— 已被 V22 超越"),
    (".scratch/_overlay_old.html", "旧遮罩页（名字自带 old）"),
    (".openclaw/tmp", "临时报告页目录 —— `tmp` 本身就是暂存"),
    ("outputs/tentacle-studio/archive", "触手工作流旧版存档 —— 同目录有现行版"),
    ("holo_pet/archive", "生产树里的旧版形象页 —— 新壳在 holo_pet_w3/"),
    # ── 2026-09-23 第 30 轮补（Owner 第三次提「旧页面要清掉别搞混」后，用 dup-pages.py 现扫出来的）──
    ("deploy/gbt-prototype.html",
     "同一份「能力中枢 · 可交互原型 V21」在本仓的**第三份**。"
     "另外两份是：`deploy/index.html`（**那是面板 #12**，见 plugins/gbt-master/README.md:36，"
     "且是**外网写入落点** ⇒ 绝不许动）与仓根 `V22 …可交互原型.html`（现行版）。"
     "本件实测 **0 引用** —— 唯一提到它的是本仓探针自己的源码（量具自污染）。"),
    ("agent-gvmz-gbtv8/.openclaw/tmp",
     "另一个 agent 工作区里的 `tmp` 草稿（`*_fix.html` / `v11_fixed.html` / `v92_wl2.html`，约 1.06 MB）。"
     "判据不是我看它像草稿，是**框架自己两处写明了**："
     "`gbt_allinone/tools/scan_scope.py` 把 `.openclaw` 列进 `TOOLING_DIRS`（缓存/临时/归档/数据面）；"
     "`gbt_allinone/tools/gate_visibility.py` 把 `agent-gvmz-gbtv8` 列进 `DECLARED_NOT_WATCHED`"
     "（「另一个 agent 的工作区，不是本框架的源码面」）。"
     "⚠️ **只动 `tmp/`**：同树的 `agent-gvmz-gbtv8/DELIVERY/` 那 14 份带日期的交付报告**保留** ——"
     "那是记录，不是草稿；Owner 说的是「别搞混」，不是「把历史删了」。"),
    # ── 2026-09-23 第 44 轮补（Owner 第三次提「旧页面」后，用 old-pages.py 现扫出来的）──
    ("outputs/tentacle-studio/V1 触手工作流-无限画布.html",
     "同目录**同族的 V2 已在**（`V2 触手工作流-无限画布.html`）⇒ V1 入口被超越。"
     "判据是名字族 + 同目录更高版，**不是「看着旧」**；两件都是 0.3-0.4 KB 的**入口壳**"
     "（只挂同目录 studio.js/studio.css），V2 那两件**保留**（它们是该 app 的现行入口）。"),
    ("outputs/tentacle-studio/V1 触手工作流-可交互原型.html",
     "同上：同族已有 `V2 触手工作流-可交互原型.html`。"),
]
# 不入表、也永不搬的（**别人的页面 / 上游素材**）：写在这里是为了让下一个人一眼看到边界
PAGE_NEVER = ("_upstream", "vendor", "gbt_allinone", "审美相关skill", "node_modules", ".git",
              "delivery", "plugins", "holo_pet_w3")


def manifest_paths() -> tuple:
    """**声明式消费者护栏**：面板清单/窗口注册表里**点名过的**文件，一律不许搬。

    ## 为什么必须有这一件（2026-09-23 真出过事）

    我按「旧页面都要清理掉」清掉了 `holo_pet/{index.html,styles.css,app.js}` ——
    依据是"引用扫描"的结果。**结果面板从 12/12 掉到 11/12**（缺「主控台 W1 · 数字人面板」）。

    真因：面板清单在 **`plugins/gbt-master/host.js`** 第 83 行：

        { id: 'pet', name: '主控台 W1 · 数字人面板', file: 'holo_pet/index.html', apiShim: true }

    而我的扫描面写的是 `plugins\\**\\*.py` + `plugins\\**\\*.cjs` —— **漏了 `.js`**。
    ⇒ 这不是"没注意"，是**扫描面漏了一整类文件**；而漏掉的那类，恰好是**声明式消费者**住的地方。

    ## 判据

    「谁在用这个文件」有**三种**，缺一种就会误删：
      ① 进程正拿着（`live_paths` 管这个）；
      ② **清单/注册表里点名**（本函数管这个）；
      ③ 代码里 import/引用（引用底账管这个）。
    ⇒ 三样齐了才敢说"没人用"。
    """
    pats = ("plugins/**/*.js", "plugins/**/*.mjs", "plugins/**/*.json", "plugins/**/*.py",
 # 2026-09-23 第 30 轮补 `.md`：**面板清单还有一份写在 README 里**。
            # 实测：`plugins/gbt-master/README.md:36` 那张表就是「12 个面板各是谁、落哪个文件」，
            # 而 `deploy` 那条写着 `deploy/index.html` —— 上一版扫描面**没有 .md**，
            # 于是"面板 #12 是谁"这件事只有 `lib/*.js` 一条线索。
            # 漏掉 `.md` 的后果上一次已经演过一遍（漏 `.js` ⇒ 面板 12/12 → 11/12），
            # 那次教训写在本函数 docstring 里：**扫描面漏一整类文件 = 不是没注意，是设计缺陷。**
            "plugins/**/*.md",
            "holo_pet_w3/shell/*.json", "holo_pet_w3/shell/*.cjs", "holo_pet_w3/shell/*.js",
            "holo_pet_w3/**/*.json", "state/*.json", "sources.json")
    found, scanned = {}, 0
    for pat in pats:
        for f in ROOT.glob(pat):
            if not f.is_file() or "__pycache__" in f.parts or "node_modules" in f.parts:
                continue
            scanned += 1
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in re.finditer(r"[A-Za-z0-9_./\\一-鿿-]+\.(?:html|htm|css|js|mjs|cjs|json|glb|png)\b", txt):
                seg = m.group(0).replace("/", "\\").strip("\\").lower()
                if seg:
                    found.setdefault(seg, set()).add(str(f.relative_to(ROOT)))
    # ── **传递闭包**（2026-09-23 补：差这一层就还是漏）──
 # 自证时发现：`holo_pet/index.html` 被清单点名 ，但它引用的 `styles.css` / `app.js`
 # 判成"清单没提" 。而**清单点名的那个页面引用的东西，一样是活的** ——
    # 删了样式表，那个面板照样烂。⇒ 从被点名的文件出发，把它引用到的本地件也算活（走两层）。
    frontier = set()
    for seg in list(found.keys()):
 # 种子是**被点名的那个文件本身**（`found` 的键），不是引用它的那个文件（值）——
        #    首版把两者搞反了，于是 `holo_pet/index.html`（.html，该当种子）没进 frontier，
        #    而 `host.js`（.js）被 `.html` 过滤挡掉 ⇒ 闭包空转，`styles.css` 照样漏。
        for cand in (ROOT / seg, ROOT / seg.replace("\\", "/")):
            if cand.is_file() and cand.suffix.lower() in (".html", ".htm"):
                frontier.add(cand)
    for _depth in range(2):
        nxt = set()
        for op in frontier:
            try:
                txt = op.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for m in re.finditer(r"""(?:href|src)\s*=\s*["']\.?/?([^"'?#]+\.(?:css|js|mjs|json|html))""", txt):
                rel = m.group(1).replace("/", "\\").strip("\\").lower()
                if rel and rel not in found:
                    found[rel] = {"（传递）%s" % op.relative_to(ROOT)}
                    nxt.add(ROOT / rel)
        frontier = {p for p in nxt if p.is_file()}
    return found, scanned


def guard_manifest(path, man: dict) -> str:
    """返回"不能搬"的理由（清单里点名过）；空串 = 清单没提它。"""
    s = str(path).replace("/", "\\").strip("\\").lower()
    leaf = s.rsplit("\\", 1)[-1]
    for seg, owners in (man or {}).items():
        if seg == s or seg.endswith("\\" + leaf) or s.endswith("\\" + seg) or seg == leaf:
            return ("**清单里点名过**（%s）—— 那是声明式消费者，删了它对应的面板/窗口会掉"
                    % ", ".join(sorted(owners)[:3]))
    return ""


def _resolve_frag(frag):
    """把命令行里抠出来的片段收敛成**盘上真实存在的路径**；收敛不出来返回 None。

    🔴 为什么必须收敛（2026-09-23 第 30 轮实测抓到的）：
    下面那个正则 `[A-Za-z]:\\\\[^\\"']+` 会一直吃到下一个引号为止，实测抠出来过
    `c:\\python312\\python.exe -m pytest c:\\users\\admin\\desktop\\g...` —— **整条命令行**。
    拿这种串去做路径前缀判断，命中与否全看运气。

    收敛办法：整串先试，再从右往左按空白边界逐段砍，**取第一个真的存在的**。
    「存在性」是硬证据 —— 比任何启发式都可靠；砍到头还不存在，就当没这条。

    🔴 **必须 `.resolve()` 成绝对路径**（这是我第一版修法当场翻车的地方）：
    正则抠出来的往往是**相对路径**（面板服务那条命令行里就是 `holo_pet\\launch_panel.py`），
    而 `Path("holo_pet\\launch_panel.py").exists()` 是相对**本进程的 cwd** 判的 ——
    于是它一次性把**真的活服务**也筛掉了（实测：活路径从 185 条掉到 **0 条**）。
    那次是**正对照**（面板服务必须被认出来）把它抓住的：
    只测"噪声没了"会以为修好了，**必须同时测"该认的还认不认"**。
    """
    s = str(frag).strip().strip('"').strip("'")
    for _ in range(16):
        if not s:
            return None
        try:
            p = Path(s).resolve()
            if p.exists():
                return p
        except (OSError, ValueError):
            return None
        cut = max(s.rfind(" "), s.rfind("\t"))
        if cut <= 0:
            return None
        s = s[:cut].rstrip()
    return None


def live_paths() -> dict:
    """**活进程护栏**：正在运行的进程命令行里出现过的路径 —— 这些**一个都不许搬**。

    ## 为什么要这一件（2026-09-23 差点出大事）

    主人令「旧页面都要清理掉别留在项目里面容易搞混」。我按这条去清点时，
    `holo_pet/` 看上去就是"旧生产树" —— 但实测：

        C:\\Python310\\python.exe  holo_pet\\launch_panel.py --host 127.0.0.1 --port 8765 --no-browser

    ⇒ **`holo_pet/` 是正在给 12/12 面板供餐的活服务**（pid 7440 / 端口 8765），
      外加 **1.42 GB 数字人交付资产**（`assets/`）。
      按"旧页面"字面去删它 = **面板当场全灭 + 交付物没了**。

    ## 判据

    「**看着像旧目录**」不是判据，「**有没有活进程在用**」才是。
    ⇒ 清理前先问系统：哪些路径有进程正拿着？拿着的，一律 `add_guarded`（**留下并说理由**）。

    ⚠️ 已知边界（**不许当成"安全"**）：只查命令行**字面**出现的路径，
      查不到"动态拼出来的路径""已加载进内存但命令行没写"的情况。
      所以它是**护栏**（拦得住整目录误删），**不是证明**（证不了绝对安全）。
    """
    import csv
    import io
    out = {}
    root_key = str(ROOT).replace("/", "\\").strip("\\").lower()
    ps = ("Get-CimInstance Win32_Process | "
          "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Csv -NoTypeInformation")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        rows = list(csv.DictReader(io.StringIO(r.stdout or "")))
 # **排除本进程的祖先链**（2026-09-23 第 30 轮加）——量具不许量到自己头上。
        # 实测症状：我为了诊断跑了一条命令，命令行里写了 `.scratch\_hv\demo.html` 与
        # `deploy\index.html`，于是**这两个路径当场被判成"活进程在用"**。
        # 而且这不是偶发：清理器自己的调用、任何并发的管理命令，都会把它提到的路径标成活。
        # ⇒ 从 os.getpid() 往上走父链，把这些 pid 一律剔除 —— 它们只是"正在命名这个路径"，
        #   不是"正在用这个路径"。**排掉之后，留下来的才是真的消费者。**
        by_pid = {str(x.get("ProcessId")): x for x in rows}
        mine, cur, hops = set(), str(os.getpid()), 0
        while cur and cur in by_pid and hops < 16:
            mine.add(cur)
            cur = str(by_pid[cur].get("ParentProcessId") or "")
            hops += 1
        for row in rows:
            if str(row.get("ProcessId")) in mine:
                continue
            cmd = (row.get("CommandLine") or "")
            if not cmd:
                continue
            who = "%s(pid %s)" % (row.get("Name") or "?", row.get("ProcessId"))
            seen = set()
            # 抽出命令行里出现的、位于本仓内的路径片段
            for m in re.finditer(r"[A-Za-z]:\\[^\"']+|(?<![\w.])[\w./\\一-鿿-]+\.(?:py|js|cjs|json|html)\b", cmd):
                p = _resolve_frag(m.group(0))
                if p is None:
                    continue                       # ① 收敛不出来 = 不是真路径，丢掉
                key = str(p).replace("/", "\\").strip("\\").lower()
                if key == root_key or not key.startswith(root_key + "\\"):
                    continue                       # ② 仓根 / 仓外 = cwd 噪声，不参与
                if key in seen:
                    continue
                seen.add(key)
                out.setdefault(key, []).append(who)
    except Exception as e:                                          # noqa: BLE001
        return {"__error__": ["%s: %s" % (type(e).__name__, str(e)[:80])]}
    return out


def guard_live(path, live: dict) -> str:
    """返回"不能搬"的理由（活进程在用）；空串 = 没查到活进程用。

    🔴 **匹配必须父子双向**（首版只做单向，漏掉了最危险的那种）：
      实测 `holo_pet\\launch_panel.py` 被判"活"，但**整目录 `holo_pet/` 判成"可以搬"** ——
      而搬整目录才是真危险的那个动作（里面还有 1.42 GB 数字人交付资产）。
      根因：判据写的是"候选串里含不含有活路径"，没写"候选是不是活路径的**父目录**"。

      ⇒ 三种都算活：
        ① 候选 == 活路径；
        ② 候选**在活路径里面**（活的是目录，候选是它下面的东西）；
        ③ **活路径在候选里面**（候选是父目录 —— 删父等于删活的那个）。
    """
    s = str(path).replace("/", "\\").strip("\\").lower()
    for frag, procs in (live or {}).items():
        if frag == "__error__":
            continue
        f = str(frag).replace("/", "\\").strip("\\").lower()
        if not f:
            continue
 # 2026-09-23 第 30 轮修：**去掉裸子串判定 `f in s`**（原来挂在最后一条 or 上）。
        # 那不是路径关系 —— `f="c:\users\admin"` 会命中任何含这串的路径；而真正该管的
        # 三种关系（相等 / 候选是活路径的父目录 / 候选在活路径里面）下面已经盖全。
        # 留着它只制造**假"活"**；假"活"一多，人就学会无视护栏 —— 那比没有护栏更坏。
        if f == s:
            why = "候选就是活路径"
        elif f.startswith(s + "\\"):
            why = "候选是活路径的**父目录**（删它 = 删掉活的那个）"
        elif s.startswith(f + "\\"):
            why = "候选在活路径**里面**"
        else:
            continue
        return ("**活进程在用**（%s）—— %s，搬了会当场断服务"
                % (", ".join(sorted(set(procs))[:3]), why))
    return ""


def _walk_files(p: Path):
    for dp, _dn, fn in os.walk(p):
        for f in fn:
            yield Path(dp) / f


def _size(p: Path) -> int:
    if p.is_file():
        try:
            return p.stat().st_size
        except OSError:
            return 0
    return sum(_safe_size(f) for f in _walk_files(p))


def _safe_size(f: Path) -> int:
    try:
        return f.stat().st_size
    except OSError:
        return 0


def instrument_files() -> set:
    """标了 `gbt-instrument` 的文件 = **量具**；它在底账里的"引用"不算消费，一律剔除。

    🔴 为什么必须有这一件（2026-09-23 第 30 轮实测，症状很典型）：
    我为了查清 `deploy/gbt-prototype.html` 到底有没有人用，写了个探针；
    **探针源码里当然写着那个路径** ⇒ 引用底账立刻记上一笔「有引用」
    ⇒ 护栏把候选拦下 ⇒ **量具把自己的结论堵死了**，一个字节都清不动。
    （同一个病在 `live_paths` 那边也犯过一次：我的一条诊断命令让两个路径当场变成"活进程在用"。
      两次是同一个根因：**量具被算进了被量的东西里面**。）

    为什么用**标记**而不是内建黑名单：黑名单是藏在代码里的决定，没人看得见；
      标记是**写在被排除的那个文件自己头上**的，`grep -rn gbt-instrument` 一条命令就能审。
      本仓已有同类惯例（`# gbt-capability: …` 标记）。
    """
    out = set()
    d = ROOT / "tools" / "codex-scripts"
    if not d.is_dir():
        return out
    for p in _walk_files(d):
        if p.suffix not in (".py", ".js", ".cjs", ".mjs", ".md"):
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:2500]
        except OSError:
            continue
        if "gbt-instrument" in head:
            out.add(str(p.relative_to(ROOT)).replace("\\", "/"))
    return out


def referenced_names() -> set:
    """全仓文本面里出现过的**文件名**（引用守卫的底账）。

    口径：`git grep` 追踪 + 未追踪的文本文件，排掉 `.scratch/` 自己
    （它自己出现自己的名字不算"有人引用"）。粗粒度但方向正确：**宁多留**。

    🔴 **2026-09-23 修的一个真窟窿**：原字符类 `[A-Za-z0-9_\\u4e00-\\u9fff.-]` **不含空格** ⇒
    `archive/V21 GBT小土豆V8-可交互原型.html` 这种**带空格的中文页名，守卫一个字都匹配不到**
    —— 等于对本仓最要紧的那批交付页**完全没有守卫**（它们全是 `V{n} {项目名}-{形态}.html` 的形状）。
    加空格后会**多匹配**（跨词），但本守卫的方向是"宁多留"，多匹配是安全的那一侧。

    🔴 **2026-09-23 第 30 轮再修**：改用**带来源**的抓法（去掉 `-h`）——
    只有知道"这句话是谁说的"，才能把**量具自己**说的话剔掉（见 `instrument_files`）。
    改之前 `deploy/gbt-prototype.html` 永远清不掉，唯一"引用者"是我自己的探针。
    """
    names = set()
    inst = instrument_files()
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "grep", "--untracked", "-I", "-o",
             "-E", r"[A-Za-z0-9_\u4e00-\u9fff. -]{3,80}\.(py|json|jsonl|md|txt|html|png|cjs|js)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        for line in (out.stdout or "").splitlines():
            src, sep, match = line.rpartition(":")
            match = match.strip().strip('"').strip("'")
            if not sep or not match or match.startswith("//"):
                continue
            src = src.strip().strip('"')          # git 对含中文/空格的路径会加引号
            if src.replace("\\", "/").lstrip("./") in inst:
                continue                            # **量具的"引用"不算消费**
            names.add(match)
    except Exception:                                            # noqa: BLE001
        pass
    return names


def guard(name: str, refs: set) -> str:
    """返回"不能搬"的理由；空串 = 可以搬。"""
    if name in refs:
        return "有引用（全仓文本面出现过这个文件名）"
    return ""


def plan(tiers: set, refs: set) -> tuple:
    items, kept = [], []
    live = live_paths()
    man, _n = manifest_paths()

    def add(tier, path, why=""):
 # **两道护栏**（顺序有讲究：先说"谁点名了"，再说"谁正拿着"）
        #    ① 清单护栏：面板/窗口注册表里点名过的 —— 2026-09-23 就是漏了这道，
        #       删掉 `holo_pet/index.html` 把面板从 12/12 打到 11/12；
        #    ② 活进程护栏：系统里有进程正拿着这条路径。
        for g in (guard_manifest(path, man), guard_live(path, live)):
            if g:
                add_guarded(tier, path, g)
                return
        items.append({"tier": tier, "path": path, "bytes": _size(path), "why": why})

    def add_guarded(tier, path, why):
        kept.append({"tier": tier, "path": path, "why": why})

    # ── build：__pycache__ / *.pyc ──
    if "build" in tiers:
        for dp, dn, _fn in os.walk(ROOT):
            if ".git" in Path(dp).parts:
                dn[:] = []
                continue
            if "__pycache__" in dn:
                add("build", Path(dp) / "__pycache__", "纯构建产物")
                dn.remove("__pycache__")

    # ── trash / backups：整片搬（它们本身就是暂存区）──
    if "trash" in tiers:
        _t = ROOT / ".trash"
        for c in (_t.glob("*") if _t.is_dir() else []):
            add("trash", c, "回收暂存区内的东西")
    if "backups" in tiers:
        _b = ROOT / ".backups"
        for c in (_b.glob("*") if _b.is_dir() else []):
            add("backups", c, "历次作业的旧备份快照")

    # ── temp：本工具自家在 %TEMP% 落的产物 ──
    if "temp" in tiers:
        tmp = Path(tempfile.gettempdir())
        if tmp.is_dir():
            for c in tmp.iterdir():
                if any(c.name.startswith(p) or c.name == p for p in _TEMP_PREFIXES):
                    add("temp", c, "本工具自家的扫描产物")

    # ── scratch：名字即残骸 + 无人引用 ──
    S = ROOT / ".scratch"
    if ("scratch" in tiers or "tempscan" in tiers) and S.is_dir():
        for c in sorted(S.iterdir()):
            if c.name in SCRATCH_KEEP:
                add_guarded("scratch", c, "白名单：活代码读写目标")
                continue
            if "tempscan" in tiers and c.is_file() and c.name in TEMPSCAN_NAMES:
                g = guard(c.name, refs)
                (add_guarded if g else add)("tempscan", c, g or "旧平铺扫描产物，无人引用")
                continue
            if "scratch" not in tiers:
                continue
            if c.is_dir():
                # 目录只在**整棵都无人引用**时才动；保守：目录一律先留着，逐层报出来
                add_guarded("scratch", c, "是目录 —— 不递归搬（怕里面有活目标），只逐文件看")
                continue
            if not RESIDUE_RE.search(c.name):
                continue
            g = guard(c.name, refs)
            (add_guarded if g else add)("scratch", c, g or "名字即残骸（_*.py/*.tmp/*.bak…），无人引用")

        # scratch 里的**散落残骸**（深层）：同样过正则 + 守卫
        if "scratch" in tiers:
            for f in _walk_files(S):
                if f.parent == S:
                    continue                          # 一层上面已处理
                if not RESIDUE_RE.search(f.name):
                    continue
                g = guard(f.name, refs)
                (add_guarded if g else add)("scratch", f, g or "深层残骸名，无人引用")

    # ── pages：旧页面 ──
    # 风哥 2026-09-23 **第三次**令：「旧页面都要清理掉别留在项目里面容易搞混」。
 # 判据定死为「**被超越**」，不是「看着旧」或「时间早」：
    #   ① **版本族**：`archive/V<n> X.html` 只有在**仓根存在同后缀的更高版** `V<m> X.html`（m>n）时才算被超越；
    #      找不到更高版 ⇒ **它是唯一的**，一律留着（不许靠猜删历史）。
    #   ② **生成镜像**：整份目录是工具生成的（生成器在盘上 + `.gitignore` 已列 ⇒ 可重建）。
    #   ③ **临时 / 备份页**：显式清单，逐条写明理由。
 # 三条护栏一条不少：现行版永不搬 · `referenced_names()` 命中就不搬（宁多留）· 不碰别人的页面。
    if "pages" in tiers:
        import re as _re

        # ① 版本族：先算出仓根**现行版**里每个后缀的最大版本号
        cur = {}
        for f in ROOT.glob("V*"):
            m = _re.match(r"^V(\d+)\s+(.+)$", f.name)
            if m and f.is_file():
                suf, n = m.group(2), int(m.group(1))
                cur[suf] = max(cur.get(suf, 0), n)
        for f in sorted(PAGE_ARCHIVE.iterdir()) if PAGE_ARCHIVE.is_dir() else []:
            m = _re.match(r"^V(\d+)\s+(.+)$", f.name)
            if not m or not f.is_file():
                add_guarded("pages", f, "归档里不是 `V<n> 名字` 的形状 —— 不猜，留着")
                continue
            n, suf = int(m.group(1)), m.group(2)
            if suf not in cur:
                add_guarded("pages", f, "仓根没有同后缀的现行版 —— 它可能是唯一的，留着")
            elif cur[suf] <= n:
                add_guarded("pages", f, "仓根现行版 V%d 不高于它 —— 留着" % cur[suf])
            else:
                g = guard(f.name, refs)
                (add_guarded if g else add)(
                    "pages", f, g or "被仓根现行版 **V%d %s** 超越（历史快照）" % (cur[suf], suf))

        # ②③ 生成镜像与临时/备份页：显式清单，逐条带理由
        for rel, why in PAGE_TARGETS:
            p = ROOT / rel
            if not p.exists():
                continue
            if p.is_dir():
                add("pages", p, why)
                continue
            g = guard(p.name, refs)
            (add_guarded if g else add)("pages", p, g or why)

    return items, kept


def _recycle_batch(paths: list) -> tuple:
    """用 PowerShell 的 Microsoft.VisualBasic 送回收站（本机实测可用）。返回 (实搬, 失败表, 已消失)。

    为什么不用 `Remove-Item`：那件是**硬删**，Owner 要的是**可还原**。

    🔴 **2026-09-23 第 30 轮补 `skip` 这一格**（一次实测读到的报告谎）：
    计划表里可能**同时列了目录和它里面的文件**（`__pycache__/` 与其中的 `*.pyc`）。
    先搬目录，后面那些文件自然就不存在了 —— 而 PowerShell 那边对"路径已不存在"是
    `continue` **静默跳过**，于是实测出现「合计 178 项」而「已进回收站 121 项 · 失败 0 项」：
    **差额 57 项既不报错也不解释**，读的人只能怀疑"是不是悄悄丢了东西"。
    ⇒ 现在把跳过数原样带回来，汇总行如实写成三段：
      实搬 N · 随父项一并搬走 K（**不是失败**）· 失败 0。
    """
    ok, bad = 0, []
    skip = 0
    skip = 0
    # 每批都重开进程太慢；把路径写进临时清单，一次交给 PowerShell
    lst = Path(tempfile.gettempdir()) / "gbt_recycle_list.txt"
    lst.write_text("\n".join(str(p) for p in paths), encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName Microsoft.VisualBasic;"
        "$n=0;$bad=@();$skip=0;"
        "foreach($p in [System.IO.File]::ReadAllLines('%s', [System.Text.Encoding]::UTF8)){"
        "  if([string]::IsNullOrWhiteSpace($p)){continue}"
        "  try{"
        "    if([System.IO.Directory]::Exists($p)){"
        "      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p,'OnlyErrorDialogs','SendToRecycleBin')"
        "    } elseif([System.IO.File]::Exists($p)){"
        "      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p,'OnlyErrorDialogs','SendToRecycleBin')"
        "    } else { $skip++; continue }"
        "    $n++"
        "  } catch { $bad += ($p + ' :: ' + $_.Exception.Message) }"
        "};"
        "Write-Output ('OK=' + $n);"
        "Write-Output ('SKIP=' + $skip);"
        "if($bad.Count){ $bad | ForEach-Object { Write-Output ('BAD=' + $_) } }"
    ) % str(lst).replace("'", "''")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=1800)
        for line in (out.stdout or "").splitlines():
            if line.startswith("OK="):
                ok = int(line[3:] or 0)
            elif line.startswith("SKIP="):
                skip = int(line[5:] or 0)
            elif line.startswith("BAD="):
                bad.append(line[4:])
    except Exception as e:                                       # noqa: BLE001
        bad.append("powershell 调用失败: %s" % e)
    finally:
        try:
            lst.unlink()
        except OSError:
            pass
    return ok, bad, skip


def main() -> int:
    ap = argparse.ArgumentParser(description="残骸清理器（进回收站 · 带引用守卫）")
    ap.add_argument("--tier", default="build,trash,backups,temp,scratch,tempscan,pages",
                    help="逗号分隔：build,trash,backups,temp,scratch,tempscan,pages")
    ap.add_argument("--go", action="store_true", help="真搬进回收站（默认只出清单）")
    a = ap.parse_args()

    tiers = {t.strip() for t in a.tier.split(",") if t.strip()}
    print("=" * 78)
    print("残骸清理器 · 目标=**回收站**（不硬删）· 引用守卫=开")
    print("=" * 78)
    print("  仓根 %s" % ROOT)
    print("  分层 %s" % sorted(tiers))
    print("  正在建引用底账（全仓文本面）…", flush=True)
    refs = referenced_names()
    print("  引用底账 %d 个文件名" % len(refs))

    items, kept = plan(tiers, refs)
    by_tier = {}
    for it in items:
        by_tier.setdefault(it["tier"], []).append(it)

    print("-" * 78)
    tot_b = 0
    for t in sorted(by_tier):
        lst = by_tier[t]
        b = sum(x["bytes"] for x in lst)
        tot_b += b
        print("  [%-9s] %6d 项  %10.2f MB" % (t, len(lst), b / 1048576))
    print("  %-11s %6d 项  %10.2f MB  ← 将搬进回收站" % ("合计", len(items), tot_b / 1048576))
    print("  %-11s %6d 项              ← 被**守卫/白名单**留下（一条都不动）" % ("留下", len(kept)))

    if kept:
        print("-" * 78)
        print("  守卫留下的（逐条给理由，不静默跳过）：")
        for k in kept[:40]:
            print("      %-34s %s" % (str(k["path"].relative_to(ROOT))[:34], k["why"]))
        if len(kept) > 40:
            print("      …其余 %d 条同型" % (len(kept) - 40))

    if items:
        print("-" * 78)
        print("  将被搬走的（最多列 30 条）：")
        for it in sorted(items, key=lambda x: -x["bytes"])[:30]:
            print("      %9.2f MB  %s" % (it["bytes"] / 1048576,
                                          str(it["path"].relative_to(ROOT))[:60]
                                          if it["path"].is_relative_to(ROOT) else it["path"]))

    if not a.go:
        print("-" * 78)
        print("  （未动盘。要真搬请加 --go）")
        return 0

    if not items:
        print("  没有可搬的。")
        return 0

    print("-" * 78)
    print("  正在送往回收站（%d 项）…" % len(items), flush=True)
    ok, bad, skip = _recycle_batch([it["path"] for it in items])
    # 汇总行**必须把差额说清**：计划 N ≠ 实搬 M 时，差额的去向要写在明面上，
    # 否则读的人会以为"是不是悄悄丢了东西"（第 30 轮实测就撞过这个）。
    _extra = ("· 其中 %d 项随父目录一并搬走（**不是失败**）" % skip) if skip else ""
    print("  ✅ 计划 %d 项 → 实搬 %d 项 %s · 失败 %d 项" % (len(items), ok, _extra, len(bad)))
    for b in bad[:20]:
        print("      BAD %s" % b)
    return 0 if not bad else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
