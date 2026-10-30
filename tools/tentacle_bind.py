# gbt-capability: tentacle_bind
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""资产 ↔ 触手 穿透式绑定（主人令 2026-09-26：每一页资料都要连着触手）。

纲领：一切以触手为中心——
  · 每个资产（文件/目录/项目）都绑定到**产生它/维护它的触手**（能力位 kind）；
  · **新增自动补绑**（`auto`/`sweep`）、**产出自动登记**（filmkit 等工具产出后自动 bind）；
  · 全量体检 `scan`：资产在不在 + 触手在不在注册表 ⇒ 红点只剩「触手断连」一种；
  · **一切留记录**：state/asset_bindings.jsonl 追加式台账，只增不删。

命令：
  python tools/tentacle_bind.py bind <资产路径> <触手kind> [--note "..."]
  python tools/tentacle_bind.py unbind <资产路径> <触手kind>
  python tools/tentacle_bind.py auto <目录> <触手kind>          # 目录下所有文件批量绑定
  python tools/tentacle_bind.py sweep <目录>                   # 按路径启发式为未绑文件补绑
  python tools/tentacle_bind.py scan                           # 全量体检（断连清单）
  python tools/tentacle_bind.py coverage <目录>                # 穿透率读数
  python tools/tentacle_bind.py ledger [--tail 30]             # 台账
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# 留痕（2026-10-19 · 新增 impact_check 时当场撞到）：本件 docstring 里带「↔」，
# 而 Windows 默认 stdout 是 GBK ⇒ `py -3.14 tools/tentacle_bind.py --help` 直接
# UnicodeEncodeError 退出（触手主干判据 L4 给的操作指令本身跑不起来 = 驱动件坏了，P8）。
# 修法对齐本仓其它模块：入口先 reconfigure 成 utf-8。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# 🔴 2026-10-30 修：硬编码 Windows 根在 Linux 上会被当成**相对路径**，
#   于是每次运行都在仓里造一个叫 `C:\Users\ADMIN\...` 的垃圾目录。
ROOT = Path(__import__("os").environ.get("GBT_ROOT")
            or Path(__file__).resolve().parents[1])
STATE = ROOT / "state"
BINDINGS = STATE / "asset_bindings.json"
LEDGER = STATE / "asset_bindings.jsonl"

# 路径启发式：产出特征 → **真触手**（必须存在于 caps_registry，否则 scan 报「不在册」）
# ⚠️ 匹配规则（2026-09-26 修）：**后缀按真后缀锚定，路径片段按整段命中**——
#    改用子串匹配时会咬错（实测：`_eye_test.png-3d1d20bf….bin` 被 `.png` 咬中、
#    `610.js.LICENSE.txt` 被 `.txt` 咬中 ⇒ 2595 条内部状态被误绑）。
HEURISTICS = [
    # 动作镜头控制系统：拍子表/静帧/段/成片全归自己的触手（2026-09-27 · 置顶防被通用规则抢走）
    ("/actioncam", "actioncam"),
    # 音频族 → voice（与 audio_extract 支持的八格式对齐）
    (".mp3", "voice"), (".wav", "voice"), (".m4a", "voice"), ("_audio.", "voice"),
    (".flac", "voice"), (".ogg", "voice"), (".aac", "voice"), (".opus", "voice"), (".wma", "voice"),
    # 图像族 → filmkit
    (".jpg", "filmkit"), (".png", "filmkit"), (".jpeg", "filmkit"),
    (".webp", "filmkit"), (".gif", "filmkit"), (".bmp", "filmkit"),
    (".tiff", "filmkit"), (".heic", "filmkit"),
    # 视频族 → filmkit
    (".mp4", "filmkit"), ("_seg.", "filmkit"),
    (".webm", "filmkit"), (".mov", "filmkit"), (".mkv", "filmkit"), (".avi", "filmkit"),
    # 字幕族 → filmkit
    (".srt", "filmkit"), (".vtt", "filmkit"), (".ass", "filmkit"), (".lrc", "filmkit"),
    # 三维族 → blender（2026-09-26 补：92 个数字人模型曾无触手）
    (".glb", "blender"), (".fbx", "blender"), (".obj", "blender"),
    (".blend", "blender"), (".stl", "blender"),
    ("assemble", "filmkit"), ("manifest", "filmkit"),
    (".docx", "genoffice"), (".xlsx", "genoffice"), (".pptx", "genoffice"), (".pdf", "genoffice"),
    (".md", "project_context"), ("/产线/", "filmkit"), ("/编剧室/", "project_context"),
    (".txt", "filmkit"),
    # 页面/模板与交付包 → project_context（2026-09-26 补）
    (".html", "project_context"), (".htm", "project_context"),
    (".zip", "project_context"), (".7z", "project_context"), (".tar", "project_context"),
    # 外部工作流插件：整个插件目录归它的触手（2026-09-27 补 · 三节点一个不差）
    ("/gs-prompt-extend/", "gs_h3"),
]
# 不进绑定系统的路径（插件内部/缓存/版本库——不是我们的资产）
# 任意位置命中即跳过（工具/缓存目录——这些名字在任何层级都是"不是资产"的意思）
# 🔴 2026-10-05 补 `/.venv/` 与 `/site-packages/`：与 `/node_modules/` **同族**（第三方依赖树，
#    不是资产）。实测：`_upstream/VoiceStudio` 带一整个 .venv ⇒ 漏绑巡检一次报 **1306 条**，
#    其中 **950 条**是 litellm/scipy/matplotlib 的图标与测试数据（依赖件）——不跳的话，它们
#    会被 `sweep` 当"产出"绑进台账（纯噪声，且把真缺口淹在 1306 条里看不见）。
SKIP_PARTS = ("/.mimosa/", "/.git/", "/__pycache__/", "/.scratch/", "/node_modules/",
              "/.vscode/", "/.venv/", "/site-packages/")
# **只在仓根**命中才跳过（框架自己的内部树；`store`/`config`/`state` 这类通用名
# 在第三方仓内部是正常源码目录 —— 2026-09-26 实测误伤过
# `_upstream/openhuman/crates/.../src/config/*.rs`，故改成根锚定）
SKIP_ROOT_DIRS = {"store", "state", "config", "vendor", ".pylibs", "snapshots", ".backups"}
# 框架内部树（**前缀锚定**）。口径（2026-09-26 用真实数据定，不是拍脑袋）：
#   `gbt_allinone/store/` 里 96% 是缓存与产物（native_browser 8925 个/5.9GB、
#   pipeline 1651、mirror_space 1507），**但 `devoured/`（消化知识）· `life_vault/`（档案）·
#   `visual_memory/` · `vision/`（视觉记忆）是真资料**。
#   ⇒ `store/` **改用白名单**（`STORE_KEEP`）：只有这几个子树进账，其余（含 store 根下的
#     `audit.jsonl` / `sync_steps.json` 等内部记录）默认跳过。
#     为什么不用黑名单：2026-09-26 实测——黑名单只列了子树，**store 根文件全部漏网**
#     （`audit.jsonl` 被 autobind 当产出绑给了 `echo`），黑名单永远列不全，白名单才是安全默认。
SKIP_PREFIXES = (
    "gbt_allinone/.pylibs/",
    "gbt_allinone/archived_logs/",
)
STORE_KEEP = ("devoured", "life_vault", "visual_memory", "vision", "life")


def _skippable(rel: str) -> bool:
    posix = rel.replace("\\", "/")
    low = "/" + posix.lower() + "/"
    if any(p in low for p in SKIP_PARTS):
        return True
    if posix.lower().startswith(SKIP_PREFIXES):
        return True
    parts = posix.split("/")
    # `gbt_allinone/store/` 白名单（见 STORE_KEEP 上方注释）
    if len(parts) > 2 and parts[0].lower() == "gbt_allinone" and parts[1].lower() == "store":
        return parts[2] not in STORE_KEEP
    first = parts[0].lower()
    if first in SKIP_ROOT_DIRS:
        return True
    # 运行足迹（与 inventory 的 transient 判据**逐字对齐**）：
    # `_*.py` / `_*.txt` / `*.tmp` / `*.deleted` 是扫描器/试跑自己留下的东西，不是资产。
    # ⚠️ `__init__.py` 例外（2026-09-27 修）：按"`_` 开头 + `.py` 结尾"它会被误判成
    #    临时文件，而它是**包入口**（`gs_engine` 那类插件全靠它）——实体必须入账。
    name = Path(rel).name.lower()
    if name.endswith((".tmp", ".deleted")):
        return True
    if name == "__init__.py":
        return False
    return name.startswith("_") and name.endswith((".py", ".txt"))


def _suffix_of(rel: str) -> str:
    return Path(rel).suffix.lower()


def _frag_hit(rel: str, frag: str, suffix: str | None = None) -> bool:
    """路径片段命中：带 `/` 的按整段找；不带 `/` 的只认**文件名真后缀或整名结尾**。

    `suffix` 可由调用方预先算好传进来（**性能**：12817 个文件 × 40 条启发式时，
    每条都 `Path(rel).suffix` 会构造 50 万个 Path 对象 —— 实测 20 秒就是这么烧掉的）。
    """
    low = "/" + rel.replace("\\", "/").lower()
    if frag.startswith("."):
        s = suffix if suffix is not None else _suffix_of(rel)
        return s == frag or low.endswith(frag)
    return frag in low


def _load() -> dict:
    if BINDINGS.is_file():
        try:
            return json.loads(BINDINGS.read_text(encoding="utf-8"))
        except Exception:                                      # noqa: BLE001
            return {}
    return {}


def _save(d: dict, tries: int = 6) -> None:
    """**原子写 + 退避重试**（2026-09-27 实测血账）。

    事故形态：补连接跑到第 271 件时，`write_text` 在 **`open()` 那一刻**抛
    `OSError: [Errno 22] Invalid argument: state\\asset_bindings.json`
    —— 同一份文件被同一进程反复开合两百多次后，系统（占用/满盘/杀毒扫描）开始拒绝打开。
    一轮补连接就整轮崩在这里，且**看不出是谁的错**（文件本身没问题、也能改名）。

    处方：
      · 写**临时文件**再 `os.replace` **原子替换** ⇒ 任何时刻都不会留下半份坏账；
      · 失败**退避重试**（0.2s 起，逐次加倍）⇒ 扛过瞬时占用；
      · 仍失败就**如实抛出**（不吞），但原件仍是上一份完好的。

    🔴 2026-10-08 加**回退闸**（当天实测事故）：物化视图被某次重建写花 ——
      盘上从 **7,245** 个资产掉到 **415**（事件账 `asset_bindings.jsonl` 完好，重放即 7,939 对），
      连带全仓报出 **3,923 条假"漏绑"**（`gaps` 读数被人当真的看）⇒ 已按事件账重放恢复。
      闸的形状：**新账资产数 < 盘上 60% 且净少 > 200 个 ⇒ 拒写**并给出恢复办法；
      真要做大批量清理（如整树删除后的 prune）就显式设 `GBT_BIND_ALLOW_SHRINK=1`。
      —— 与"临时文件原子替换"同属一条纪律：**坏账宁可写不进去，也不许悄悄写进去**。
    """
    if os.environ.get("GBT_BIND_ALLOW_SHRINK") != "1" and BINDINGS.is_file():
        try:
            old_n = len(json.loads(BINDINGS.read_text(encoding="utf-8")) or {})
        except Exception:  # noqa: BLE001
            old_n = 0
        new_n = len(d)
        if old_n > 200 and new_n < old_n * 0.6 and (old_n - new_n) > 200:
            raise RuntimeError(
                "绑定账回退闸：本次要写 %d 个资产，盘上现有 %d 个（掉 %.0f%%）——拒写。\n"
                "  · 若你**真的**在整批清理：设 GBT_BIND_ALLOW_SHRINK=1 再跑（并说明理由）。\n"
                "  · 若是意外缩水：事件账 state/asset_bindings.jsonl 是追加式、没丢 ——\n"
                "    按事件顺序重放（bind 建 / unbind 删 / prune 移出 / reset 清空）即可恢复。"
                % (new_n, old_n, 100.0 * (old_n - new_n) / max(1, old_n)))
    STATE.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(d, ensure_ascii=False, indent=1)
    tmp = BINDINGS.with_name(BINDINGS.name + ".tmp")
    last: Exception | None = None
    for i in range(tries):
        try:
            tmp.write_text(blob, encoding="utf-8")
            os.replace(tmp, BINDINGS)
            return
        except OSError as exc:
            last = exc
            time.sleep(0.2 * (2 ** i))
    raise last if last else OSError("save failed")


def _log(event: str, **kw) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **kw}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _rel(p) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except Exception:                                          # noqa: BLE001
        return str(p)


_ROOT_PREFIX = str(ROOT) + os.sep


def _rel_fast(p) -> str:
    """**热路径版** `_rel`：scandir 走出来的路径本来就是绝对+规范路径，直接切前缀。

    为什么要有它（实测）：`_rel` 里的 `Path.resolve()` 在 Windows 上每次都调
    `nt._getfinalpathname`（还要解 junction/symlink）—— 全仓巡检 31693 次调用
    烧掉 **11.3 秒**（cProfile 实证）。热路径切前缀，慢路（符号链接等）回退到 `_rel`。
    """
    s = str(p)
    if s.startswith(_ROOT_PREFIX):
        return s[len(_ROOT_PREFIX):].replace("\\", "/")
    return _rel(p)


def _tentacles() -> set:
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return set(BENIGN_CAPS.keys())
    except Exception:                                          # noqa: BLE001
        return set()


_DOMAINS_CACHE: list = []


def _domains() -> set:
    """注册表里的**职业域**（30 个）——域级标签 `domain:<名>` 的合法取值来源。

    ⚠️ 结果**缓存**：本函数在 `suggest()` 的热路径上（12817 个文件 × 每文件一次
    就是 12817 次导入+集合推导 —— 实测这是 `gaps` 慢的第二个原因）。
    """
    if not _DOMAINS_CACHE:
        sys.path.insert(0, str(ROOT))
        try:
            from gbt_allinone.caps_registry import BENIGN_CAPS
            _DOMAINS_CACHE.append({c.get("domain", "") for c in BENIGN_CAPS.values()} - {""})
        except Exception:                                      # noqa: BLE001
            _DOMAINS_CACHE.append(set())
    return _DOMAINS_CACHE[0]


_DOMAINS_LOWER: list = []


def _domains_lower() -> set:
    if not _DOMAINS_LOWER:
        _DOMAINS_LOWER.append({d.lower() for d in _domains()})
    return _DOMAINS_LOWER[0]


# 🔴 2026-10-17 加（留痕 · 单一词表）：账里的标签其实有**三层**，必须一处定义 ——
#   ① 能力位 kind（`_tentacles()`）：真实触手；
#   ② 路径域 `domain:<注册表域>`（`_domain_label`）：代码按「目录名 ↔ 域同名」归属；
#   ③ **文件类型族** `domain:<族>`：`tentacle-double-plug` 的「类一根」层 ——
#      给非代码资产（md / json / 图片 / 源码…）一根**类型族**触手，保证"每份资产至少两根"。
#   病根（实测）：第③层**从没登记进词表**，而 double-plug 早已往账里写了 **4953 条**
#   （domain:docs 3478 · media 954 · state 509 · code 12）⇒ 反向校验把它们全判成
#   「绑到了不存在的能力位」。
#   **这是词表缺一层，不是数据脏**；补词表也**不是放宽口径** —— 第③层本就是设计
#   （见 tentacle-double-plug 的 `_second_type`「扩展名族兜底」，它与第②层不同：
#   ②按目录域归属，③按文件类型族归属）。
FAMILY_LABELS = frozenset({"domain:docs", "domain:media", "domain:state",
                           "domain:code", "domain:tentacle", "domain:tools"})


def _valid_labels() -> set:
    """账里允许出现的标签 = 能力位 kind ∪ `domain:<域>` ∪ **文件类型族**（三层，一处定义）。"""
    return _tentacles() | {"domain:" + d for d in _domains()} | FAMILY_LABELS


def _domain_label(rel: str) -> str:
    """**域级归属**：`gbt_allinone/<域>/…` ⇒ `domain:<域>`（目录名与注册表域同名才成立）。

    为什么要有第二层：代码文件没有"能力位 kind"可挂，此前一律记 `no_kind`——
    实测 `gbt_allinone` 486 个、`tools` 506 个未绑全是这一类。**代码也要有归属**，
    但不能乱塞 kind（那才是假绿）；按**目录名 ↔ 域同名**精确归属，是唯一站得住的规则。
    """
    parts = rel.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0].lower() == "gbt_allinone":
        seg = parts[1].lower()
        if seg in _domains_lower():
            return "domain:" + seg
    return ""


# 「实现文件 → 它实现的触手」：只认代码类后缀（文档/配置不按此规则咬）
_CODE_SUFFIX = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".php",
                ".ps1", ".sh", ".bat", ".cmd", ".lua", ".rb", ".go", ".rs")
_KIND_CACHE: set | None = None


def _code_kind(rel: str) -> str:
    """文件名（去 `_cap`）正好等于注册表里的某个触手 kind ⇒ 绑到它。

    语义：**这个实现文件属于哪根触手**（`tools/filmkit.py` → `filmkit`、
    `genoffice_cap.py` → `genoffice`）。**只认精确同名**——不做模糊匹配，
    咬不中就是 `no_kind`（代码不是"资料"，没有对应触手时如实不绑）。
    """
    global _KIND_CACHE
    if _suffix_of(rel) not in _CODE_SUFFIX:
        return ""
    if _KIND_CACHE is None:
        _KIND_CACHE = _tentacles()
    stem = Path(rel).stem.lower()
    cands = (stem, stem[:-4]) if stem.endswith("_cap") else (stem,)
    for c in cands:
        if c and c in _KIND_CACHE:
            return c
    return ""


def bind(asset: str, tentacle: str, note: str = "", quiet: bool = False,
         force: bool = False) -> dict:
    a = _rel(asset)
    # ⚠️ 闸（2026-09-27 血账）：**标签必须是有效触手名**（能力位 / `domain:<域>` / 项目等）。
    # 来历：账上被塞过 `status`（把**操作名**当成触手名）⇒ `scan` 报「触手不在册」= 断连；
    # 实测反向自检时又塞进一条（README.md → status）⇒ 从这里**源头拒收**，force=True 才越过。
    try:
        _valid = _valid_labels()
    except Exception:                                          # noqa: BLE001
        _valid = set()
    if _valid and tentacle not in _valid and not force:
        return {"ok": False, "asset": a, "tentacle": tentacle, "fail_closed": True,
                "error": f"标签 {tentacle!r} 不在册（有效触手名 {len(_valid)} 个）—— "
                         f"用真能力位或 domain:<域>；确要强塞请 force=True"}
    d = _load()
    row = d.setdefault(a, {"tentacles": [], "note": note, "bound_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    if tentacle not in row["tentacles"]:
        row["tentacles"].append(tentacle)
        row["note"] = note or row.get("note", "")
        _save(d)
        _log("bind", asset=a, tentacle=tentacle, note=note)
        if not quiet:
            print(f"  ✔ 绑定 {a} → {tentacle}")
    elif not quiet:
        print(f"  = 已存在 {a} → {tentacle}")
    return {"ok": True, "asset": a, "tentacle": tentacle}


def unbind(asset: str, tentacle: str, why: str = "") -> dict:
    a = _rel(asset)
    d = _load()
    if a in d and tentacle in d[a]["tentacles"]:
        d[a]["tentacles"].remove(tentacle)
        if not d[a]["tentacles"]:
            d.pop(a)
        _save(d)
        _log("unbind", asset=a, tentacle=tentacle, why=why[:120])
        print(f"  ✔ 解绑 {a} → {tentacle}")
        return {"ok": True}
    print(f"  ✘ 没有这条绑定 {a} → {tentacle}")
    return {"ok": False}


def auto(dirp: str, tentacle: str) -> dict:
    d = ROOT / dirp if not Path(dirp).is_absolute() else Path(dirp)
    n = 0
    for f in sorted(d.rglob("*")):
        if f.is_file() and f.suffix.lower() not in (".tmp", ".pyc"):
            bind(str(f), tentacle, note="auto", quiet=True)
            n += 1
    _log("auto", dir=dirp, tentacle=tentacle, files=n)
    print(f"  ✔ auto：{n} 个文件 → {tentacle}（{dirp}）")
    return {"ok": True, "files": n}


def prune(verbose: bool = False) -> dict:
    """清掉**账上已不在盘上**的绑定（产出即绑会撞上转瞬即逝的中间产物）。

    为什么要有这条：账的不变量是"**账里的资产都真在盘上**"（`test_cap_bind_bidirectional`
    与 `test_wiring_all_tentacles` 都盯着它）。而产出即绑按 mtime 抓"此后新增"，
    会抓到**转瞬即逝**的东西 —— 血账：`gbt_allinone/recon/capability.json` 是吞天胶囊的
    中间产物，`ghost_guard` 会按设计把它清掉（「胶囊降威完整性」条款），于是那一行绑定
    永久把审计顶红，而人只会看到"资产缺失 1"却找不到东西可修。
    ⇒ 自愈：**不在盘上的绑定由 autobind 顺手清掉**，理由写进台账（可追溯）。
    """
    d = _load()
    gone = []
    for rel in list(d):
        if (ROOT / rel).exists():
            continue
        gone.append((rel, (d.get(rel) or {}).get("tentacles")))
        d.pop(rel, None)
    if gone:
        _save(d)
        for rel, tents in gone:
            _log("prune", asset=rel, tentacles=tents, why="不在盘上（转瞬即逝的中间产物）")
        if verbose:
            for rel, _t in gone:
                print(f"  ✂ 剪掉已不在盘上的绑定 {rel}")       # noqa: T201
    return {"ok": True, "pruned": len(gone), "sample": [g[0] for g in gone[:6]]}


def suggest(path: str) -> str:
    """按启发式给出触手 kind。

    ⚠️ 2026-09-26 修：后缀类片段（以 `.` 开头）**只认真后缀或整名结尾**，
    不再用裸子串——裸子串会把 `x.png-….bin` 判成 image、把 `foo.js.LICENSE.txt` 判成文本类，
    实测因此误绑 2595 条内部状态（已随 SKIP_PARTS 收窄一起清账）。
    ⚠️ 2026-09-26 补：加**代码归属规则**（`_code_kind`）——
    `tools/filmkit.py` → `filmkit`、`genoffice_cap.py` → `genoffice`；
    只认精确同名，咬不中归 `no_kind`。
    ⚠️ 2026-09-26 性能：后缀**每文件只算一次**（`suf`）传进 `_frag_hit`；
    每条启发式都重算一次 `Path(rel).suffix` 会把全仓巡检烧到 20 秒。
    """
    suf = _suffix_of(path)
    for pat, kind in HEURISTICS:
        if _frag_hit(path, pat, suf):
            return kind
    return _code_kind(path) or _domain_label(path)


def sweep(dirp: str) -> dict:
    d = ROOT / dirp if not Path(dirp).is_absolute() else Path(dirp)
    cur = _load()
    added = skipped = 0
    for f in sorted(d.rglob("*")):
        if not f.is_file() or f.suffix.lower() in (".tmp", ".pyc"):
            continue
        rel = _rel(f)
        if rel in cur or _skippable(rel):
            skipped += 1
            continue
        kind = suggest(rel)
        if not kind:
            continue
        bind(str(f), kind, note="sweep", quiet=True)
        # 🔴 2026-10-15 双插（主人令）：sweep 原先每文件只写一根；这里按路径**追加**第二根域触手
        #    （bind 本身是追加式 ⇒ 永不覆盖/删除；已有记录仍由 tentacle-double-plug.py 回溯补）
        _r2 = str(f).replace("\\", "/")
        _t2 = ("filmkit" if ("/产线/" in _r2 or "/成片/" in _r2 or "/编剧室/" in _r2)
               else "domain:tools" if "/tools/" in _r2
               else "domain:docs" if _r2.endswith((".md", ".html", ".htm", ".txt", ".csv"))
               else "project_context" if _r2.startswith("projects/")
               else "")
        if _t2 and _t2 != kind:
            bind(str(f), _t2, note="sweep·双插", quiet=True)
        added += 1
    _log("sweep", dir=dirp, added=added, skipped=skipped)
    print(f"  ✔ sweep：补绑 {added} · 已有 {skipped}（{dirp}）")
    return {"ok": True, "added": added, "skipped": skipped}


def scan(verbose: bool = False) -> dict:
    """全量体检：断连清单（资产缺失 / 触手不在注册表）。

    `verbose=True` 才打人读行 —— **API 路由调它时必须是 False**：
    `run_task` 的返回是 JSON 契约，人读行混进 stdout 会把严格 JSON 消费者打挂
    （实测：`five-dim.py cap tentacle_bind` 的输出无法被 `json.load` 解析）。
    """
    d = _load()
    have = _valid_labels()
    missing_asset, ghost_tentacle = [], []
    for a, row in d.items():
        if not (ROOT / a).exists():
            missing_asset.append(a)
        for t in row["tentacles"]:
            if have and t not in have:
                ghost_tentacle.append(f"{a} → {t}")
    _log("scan", bindings=len(d), missing_asset=len(missing_asset),
         ghost_tentacle=len(ghost_tentacle))
    if verbose:
        print(f"绑定总数 {len(d)} · 资产缺失 {len(missing_asset)} · 触手不在册 {len(ghost_tentacle)}")
        for a in missing_asset[:10]:
            print(f"  🔴 资产缺失: {a}")
        for g in ghost_tentacle[:10]:
            print(f"  🔴 触手不在册: {g}")
        if not missing_asset and not ghost_tentacle:
            print("  ✅ 全部连通（断连 = 0）")
    return {"ok": not (missing_asset or ghost_tentacle), "bindings": len(d),
            "missing_asset": missing_asset, "ghost_tentacle": ghost_tentacle}


# ── 产出即绑（自动绑定三件套之一 · 2026-09-26 补）─────────────────────────
# 背景（主人问「穿透都连好了嘛」时抓出的配置缺口）：
#   `_autobind` 原来**只挂在 filmkit 一处** ⇒ "产出即绑"只在电影产线成立，
#   别的触手产出要靠人工 `sweep` 才进账。这里把它提升成**总闸级**能力：
#   任何一次 `run_task` 调用（非 probe）返回后，把**这次调用期间新出现/新改动的资产**
#   自动绑到它该挂的标签（先按属性自判，判不出才用调用方 kind 兜底）。
#
# 三条纪律（为什么这么写）：
#   · **只看资产根**（projects/output/render/delivery/holo_pet/docs/skills/tools/memory），
#     不做全仓遍历；`_upstream`（第三方仓，9800+ 文件）**不在其列**——它只在 sweep 时收录；
#   · **水位线 + 节流**：`state/.bind_watermark` 记上次扫到的时间；调用间隔 < 3s 直接跳过
#     （避免 cross_scan 那种一次连调上百个能力时反复遍历）；跳过不丢——下次扫照样收；
#   · **永不炸**：任何异常都吞掉（绑定绝不许弄坏一次真调用）。
ASSET_ROOTS = ("projects", "output", "render", "delivery", "holo_pet", "docs",
               "skills", "tools", "memory", "gbt_allinone")
# 巡检（gaps）范围比自动绑定宽：`_upstream`（第三方仓）只在巡检里数，不进自动绑定
SCAN_ROOTS = ASSET_ROOTS + ("_upstream",)
WATERMARK = STATE / ".bind_watermark"
_AUTOBIND_MIN_INTERVAL = 60.0   # 🔴 2026-10-15 修：扫描成本 ~4s > 3s 窗口 ⇒ 节流永远追不上自己（实测每发都重扫）。
                         #    改为 60s（远大于单次扫描）；绑定新鲜度由 _iter_new 的水位线保证，不靠频率。
_last_autobind = [0.0]
#  🔴 2026-10-15 修（实测根因）：节流器是进程内变量，而调用形态是「一发一进程」（CLI 每发新解释器）
#     ⇒ 3 秒节流永久失效，每发全树扫（实测 3,848 次 scandir / 327k 调用 / 4.15 秒/发）。
#     ⇒ 补跨进程时间戳（文件）作节流真源；内存值仍作同进程快路径。
_AUTOBIND_STAMP = WATERMARK.parent / ".autobind_stamp"


def _stamp_seen() -> float:
    """跨进程节流真源（CLI 每发新进程也能吃到）。"""
    try:
        return float(_AUTOBIND_STAMP.read_text(encoding="utf-8").strip())
    except Exception:                                          # noqa: BLE001
        return 0.0


def _watermark() -> float:
    try:
        return float(WATERMARK.read_text(encoding="utf-8").strip())
    except Exception:                                          # noqa: BLE001
        return 0.0


def _iter_new(root: Path, since: float):
    """产出即绑的**快速遍历**（os.scandir 版）——返回 (rel, Path) 里 mtime > since 的文件。

    为什么不用 `Path.rglob` + `Path.stat`：实测 **14.3 秒/次**（12817 个文件），
    挂在总闸上不可接受；`os.scandir` 在 Windows 上 `entry.stat()` **免额外系统调用**，
    同一棵树实测降到亚秒级。被跳过的子树**连进都不进**（省时间也省权限坑）。

    ⚠️ 联接/符号链接（Windows junction）：`skills/remotion-*` 这类**联接点**
    要按**解析后的真实路径**记账（否则与 `.agents/skills/...` 的老账"重影"——
    2026-09-26 实测 161 条 fake gap）。只对联接点做解析（全仓就十来个），
    换来行速度不丢。
    """
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        name = e.name
                        if e.is_dir(follow_symlinks=False):
                            if name in (".git", "__pycache__", "node_modules", ".scratch",
                                        ".vscode", ".mimosa"):
                                continue
                            try:
                                if e.is_junction() or e.is_symlink():
                                    stack.append(Path(os.path.realpath(e.path)))
                                    continue
                            except (OSError, AttributeError):
                                pass
                            stack.append(Path(e.path))
                            continue
                        if not e.is_file(follow_symlinks=False):
                            continue
                        if e.stat(follow_symlinks=False).st_mtime <= since:
                            continue
                        p = Path(e.path)
                        yield _rel_fast(p), p
                    except OSError:
                        continue
        except OSError:
            continue


def autobind(kind_hint: str = "", force: bool = False, verbose: bool = False) -> dict:
    """把**新出现/新改动**的资产绑上标签。`kind_hint` = 调用方能力位（兜底用）。"""
    now = time.time()
    if not force and (now - max(_last_autobind[0], _stamp_seen())) < _AUTOBIND_MIN_INTERVAL:
        return {"ok": True, "skipped": "throttled", "bound": 0}
    _last_autobind[0] = now
    try:
        _AUTOBIND_STAMP.write_text(repr(now), encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass
    since = _watermark()
    if not since:
        # 首次运行**只立基线、不绑**：没有水位线时"新于 0"= 全部历史文件，
        # 那不是"这次产出"，是历史存量 —— 存量归 `sweep` 管，产出即绑只管"此后新增"。
        try:
            WATERMARK.write_text("%.3f" % now, encoding="utf-8")
        except OSError:
            pass
        _log("autobind", baseline=True)
        return {"ok": True, "baseline": True, "found": 0, "bound": 0}
    found, bound = [], []
    try:
        for root in ASSET_ROOTS:
            p = ROOT / root
            if not p.is_dir():
                continue
            for rel, f in _iter_new(p, since):
                if _skippable(rel):
                    continue
                found.append(rel)
                label = suggest(rel) or kind_hint
                if label:
                    bind(f, label, note="autobind", quiet=True)
                    bound.append(f"{rel} → {label}")
        WATERMARK.write_text("%.3f" % now, encoding="utf-8")
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}",
                "found": len(found), "bound": len(bound)}
    # ── 产出即绑的**第二个动作：新技能自动接上枢纽**（2026-09-27 补的真缺口）────────
    # 血账：早先"仓内新建技能"要**手工**跑 `tools/skills_sync.py sync` 才会出现在运行时读的
    # 枢纽里 —— **靠记性 = 会忘**（主人原话："别又自动化新增又失败"）。
    # 现在：autobind（6 小时环本来就会跑）顺手把源↔装对齐；覆盖前依旧先备份（可回滚）。
    skills_sync = {"ok": True, "synced": [], "note": "未触发"}
    try:
        import importlib.util as _iu
        _sp = _iu.spec_from_file_location("skills_sync_auto", ROOT / "tools" / "skills_sync.py")
        _ss = _iu.module_from_spec(_sp)
        _sp.loader.exec_module(_ss)
        st = _ss.survey()
        need = [r["skill"] for r in st["rows"]
                if r["own"] and r["status"] in ("未安装", "分叉")]
        if need:
            out = _ss.do_sync()
            skills_sync = {"ok": True, "synced": [d["skill"] for d in out["synced"]],
                           "backup_root": out["backup_root"],
                           "note": "新技能/分叉技能已自动装到枢纽（覆盖前先备份）"}
            _log("autobind", skills_synced=skills_sync["synced"])
        else:
            skills_sync = {"ok": True, "synced": [], "note": f"技能源↔装 {st['summary']['ok']} 一致，无需动作"}
    except Exception as exc:                                   # noqa: BLE001
        skills_sync = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:140]}",
                       "note": "技能同步没跑成 —— **如实报**，别让新增技能悄悄停在源里"}
    if found:
        pruned = prune(verbose=verbose)        # 顺手剪掉已不在盘上的（防"摸不到的资产缺失"永久顶红）
        _log("autobind", files=len(found), bound=len(bound), hint=kind_hint,
             pruned=pruned.get("pruned"))
        if pruned.get("pruned"):
            bound.append(f"（剪掉 {pruned['pruned']} 条已不在盘上的绑定）")
    if verbose and bound:
        for b in bound[:20]:
            print(f"  ✔ 产出即绑 {b}")
    return {"ok": True, "found": len(found), "bound": len(bound), "files": bound[:50],
            "skills_sync": skills_sync}


def _iter_all(root: Path):
    """全量快速遍历（os.scandir 版）：yield (rel, Path)。给巡检/读数用。

    联接点（junction）按**解析后的真实路径**继续走（与 `_iter_new` 同款口径，
    否则 `skills/remotion-*` 会与 `.agents/skills/...` 的老账重影）。
    """
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name in (".git", "__pycache__", "node_modules", ".scratch",
                                          ".vscode", ".mimosa"):
                                continue
                            try:
                                if e.is_junction() or e.is_symlink():
                                    stack.append(Path(os.path.realpath(e.path)))
                                    continue
                            except (OSError, AttributeError):
                                pass
                            stack.append(Path(e.path))
                            continue
                        if e.is_file(follow_symlinks=False):
                            p = Path(e.path)
                            yield _rel_fast(p), p
                    except OSError:
                        continue
        except OSError:
            continue


def gaps(verbose: bool = False, sample: int = 20) -> dict:
    """**漏绑巡检**（自动绑定三件套之三）：有标签可挂、却没进账的文件 = 真缺口。

    与 `coverage` 的分工：coverage 报"率"，本巡检报"**清单**"——
    只列**本来该有标签却没绑**的（`suggest()` 命中但账里没有），
    没标签可挂的（代码/配置/第三方）**不算缺口**，如实分列。
    """
    d = _load()
    missing, no_kind, scanned, third_party = [], 0, 0, []
    for root in SCAN_ROOTS:
        p = ROOT / root
        if not p.is_dir():
            continue
        for rel, _f in _iter_all(p):
            try:
                if _skippable(rel):
                    continue
                scanned += 1
                if rel in d:
                    continue
                if not suggest(rel):
                    no_kind += 1
                    continue
                # 🔴 2026-10-11 修（**判据与设计自相矛盾，实测暴露**）：
                #    本文件 L466/L472 的设计口径写着：「_upstream（第三方仓，9800+ 文件）
                #    **不进自动绑定**，只在巡检里数」—— 而这里却把它算进 missing（真缺口）。
                #    后果实测：克隆一个外部件进 _upstream/ 就**凭空多出十几条真缺口**，
                #    把**真正的**缺口淹掉（2026-10-11 克隆 VLX-Flow 后 gaps 从 1 条真缺口
                #    变成 18 条，其中 17 条全是那个第三方仓的 README/assets）。
                #    ⇒ 第三方仓的命中**单独分列**：**如实可见（不静默），但不计缺口**。
                if rel.startswith("_upstream/"):
                    third_party.append(rel)
                    continue
                missing.append(rel)
            except OSError:
                continue
    _log("gaps", missing=len(missing), no_kind=no_kind, scanned=scanned,
         third_party=len(third_party))
    if verbose:
        print(f"漏绑巡检：真缺口 {len(missing)} 个（有标签可挂却没绑）· 无标签 {no_kind} 个"
              f"（代码/配置，不算缺口）· 第三方仓命中 {len(third_party)} 个（**不计缺口**，见下）")
        for m in missing[:sample]:
            print(f"  🔴 该绑未绑: {m}")
        for m in third_party[:5]:
            print(f"  · 第三方仓（**设计上不自动绑**，只列出）: {m}")
        if not missing:
            print("  ✅ 无漏绑")
    return {"ok": not missing, "missing": len(missing), "no_kind": no_kind,
            "third_party": len(third_party), "scanned": scanned,
            "sample": missing[:sample], "third_party_sample": third_party[:sample]}


def coverage(dirp: str, verbose: bool = False) -> dict:
    """穿透率读数。

    ⚠️ 读数纪律（2026-09-26 细化，**门槛不动**）：
    `pct` 仍按"**全部活文件**"算（老口径、保守，不挪门线变绿），`ok` 仍挂 `pct >= 95.0`；
    另外**把成分摊开**给人看——`no_kind`（类型没有对应触手：代码/配置/矢量图，不是"断连"）
    与 `skipped`（故意跳过的内部树）。**"断连"只有 `scan` 判**（资产缺失 / 触手不在册），
    这里判的是"完整性"；两个数不许混着念。
    """
    d = ROOT / dirp if not Path(dirp).is_absolute() else Path(dirp)
    cur = _load()
    files = [f for f in d.rglob("*") if f.is_file() and f.suffix.lower() not in (".tmp", ".pyc")]
    skipped = [f for f in files if _skippable(_rel(f))]
    live = [f for f in files if not _skippable(_rel(f))]
    bound = [f for f in live if _rel(f) in cur]
    no_kind = [f for f in live if _rel(f) not in cur and not suggest(_rel(f))]
    unbound = [_rel(f) for f in live if _rel(f) not in cur and suggest(_rel(f))][:12]
    pct = round(100.0 * len(bound) / max(1, len(live)), 1)
    _log("coverage", dir=dirp, files=len(files), live=len(live), bound=len(bound),
         pct=pct, no_kind=len(no_kind), skipped=len(skipped))
    if verbose:
        print(f"穿透率 {pct}%（{len(bound)}/{len(live)} 活文件）· {dirp}")
        if no_kind:
            print(f"  · 无对应触手类型（代码/配置/矢量图，不是断连）: {len(no_kind)}")
        if skipped:
            print(f"  · 故意跳过（内部树）: {len(skipped)}")
        for u in unbound:
            print(f"  ○ 未绑(该有类型却没绑): {u}")
    return {"ok": pct >= 95.0, "files": len(files), "live": len(live), "bound": len(bound),
            "pct": pct, "no_kind": len(no_kind), "skipped": len(skipped), "unbound": unbound}


def ledger(tail: int = 30) -> int:
    if not LEDGER.is_file():
        print("台账为空"); return 0
    lines = LEDGER.read_text(encoding="utf-8").strip().splitlines()
    for ln in lines[-tail:]:
        print(" ", ln[:150])
    print(f"台账共 {len(lines)} 行：{LEDGER}")
    return 0


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    if cmd == "bind" and len(argv) >= 4:
        return 0 if bind(argv[2], argv[3], note=(argv[argv.index("--note") + 1] if "--note" in argv else "")).get("ok") else 1
    if cmd == "unbind" and len(argv) >= 4:
        return 0 if unbind(argv[2], argv[3]).get("ok") else 1
    if cmd == "auto" and len(argv) >= 4:
        auto(argv[2], argv[3]); return 0
    if cmd == "sweep" and len(argv) >= 3:
        sweep(argv[2]); return 0
    if cmd == "scan":
        return 0 if scan(verbose=True).get("ok") else 1
    if cmd == "gaps":
        return 0 if gaps(verbose=True).get("ok") else 1
    if cmd == "prune":
        r = prune(verbose=True)
        print(f"  剪枝：{r.get('pruned')} 条绑定已不在盘上（理由进了台账）")
        return 0
    if cmd == "autobind":
        r = autobind(force=True, verbose=True)
        print(f"  产出即绑：发现 {r.get('found')} · 绑定 {r.get('bound')}")
        return 0
    if cmd == "coverage" and len(argv) >= 3:
        return 0 if coverage(argv[2], verbose=True).get("ok") else 1
    if cmd == "ledger":
        return ledger(int(argv[argv.index("--tail") + 1]) if "--tail" in argv else 30)
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
