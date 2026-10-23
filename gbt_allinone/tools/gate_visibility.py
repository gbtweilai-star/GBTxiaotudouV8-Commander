# gbt-capability: gate_visibility
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""门可见性审计（gate_visibility）· R-H248 只读骨架。

坑册 §60（门元规则）：**门必须知道自己看不见什么。**

为什么要有它（同一族第二次）：
  · R-H166：改了 `holo_pet_w3/shell/main.cjs`，门记 `changed_files: 0`；
  · R-H247：只改了 `.md`（待落刀登记），门同样记 `changed_files: 0`；
  · 两次都不是「没改」，是「**门看不见它**」。
判据：**看见的记「已纳入」；判过不纳的记「显式不纳入」（必须带理由出处）；其余的记「未决定」——
绝不许默认沉默。** 未决定一栏就是**门盲区清单**。

三态由机器算，不靠人抄：
  已纳入     = 命中门**自己的**扫描函数（`framework_gate._watched`）—— 判据只有一处，不写第二套
  显式不纳入 = ① 门自己声明的跳过目录（依赖树/缓存/产物）② 已有判定文档判过不纳的目录（**引用出处**）
  未决定     = 其余全部（**这就是盲区**，等主人逐条拍「纳 / 不纳」）

R-H249（Owner 2026-09-20 四类拍板）之后，门长了两条新规则：
  · `.ps1` 进 `_WATCH_SUFFIX`（gbt_allinone/deploy/ 那 10 个真部署脚本）；
  · 根级 `.md` / `.bat` / `.py` 按后缀收（**USER.md / MEMORY.md 显式排除**）。
  · 图纸面 `gbt_allinone/docs/*.md` 与取证后无调用点的 `brain/` `caps/` ⇒ **显式不纳**（带理由出处）。

四条红线（写死）：
  ① 只读：不改门、不改监视范围、不写任何 store；
  ② 判据单一：可见范围**只从 framework_gate 读**，本模块不许复刻一份范围表；
  ③ 显式不纳入必须带理由与出处（不许无标注的不纳 —— 与坑册 §57 同族）；
  ④ 空清单不许当通过（坑册 §45）：样本数为 0 时报 `no_sample` 红，不报绿。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CAP_KIND = "gate_visibility"
DOMAIN = "framework"
CAP_TYPE = "local"

STATES = ("已纳入", "显式不纳入", "未决定")

WATCH_DOC = "gbt_allinone/docs/自改门监视范围判定.md"
BLIND_DOC = "gbt_allinone/docs/门盲区清单.md"

# 已有判定文档判过「不纳」的顶层目录 —— **只登记理由出处，不许在本模块改判**。
# 要改判：先改上面那份判定文档，再回来对出处。
# R-H990（2026-10-15 · 主人令「必须补齐，绝对不能有任何盲区」）：**后缀级**显式不纳。
#   只列「非源码」后缀（媒体 / 数据 / 文档 / 缓存 / 临时件）——**源码后缀一个都不在里面**。
#   出处统一指 `gbt_allinone/docs/自改门监视范围判定.md · 三`。
_SRC = "gbt_allinone/docs/\u81ea\u6539\u95e8\u76d1\u89c6\u8303\u56f4\u5224\u5b9a.md \u00b7 \u4e09"
DECLARED_NOT_WATCHED_EXT: Dict[str, Dict[str, str]] = {
    ".png": {"why": "\u4f4d\u56fe/\u4ea7\u7269", "source": _SRC},
    ".jpg": {"why": "\u4f4d\u56fe/\u4ea7\u7269", "source": _SRC},
    ".jpeg": {"why": "\u4f4d\u56fe/\u4ea7\u7269", "source": _SRC},
    ".webp": {"why": "\u4f4d\u56fe/\u4ea7\u7269", "source": _SRC},
    ".svg": {"why": "\u56fe\u5f62\u8d44\u6e90", "source": _SRC},
    ".mp4": {"why": "\u6210\u7247\u4ea7\u7269", "source": _SRC},
    ".glb": {"why": "3D \u8d44\u4ea7", "source": _SRC},
    ".json": {"why": "\u6570\u636e\u5feb\u7167/\u53f0\u8d26\uff08\u771f\u6e90\u5934\u8d70\u663e\u5f0f\u5355\u6587\u4ef6\u7eb3\u5165\uff09", "source": _SRC},
    ".jsonl": {"why": "\u8ffd\u52a0\u5f0f\u53f0\u8d26", "source": _SRC},
    # 2026-10-17 补（实测 6 件门盲区里 1 件是它）：PWA 清单是前端静态资产，不是策略/配置真源。
    ".webmanifest": {"why": "PWA \u6e05\u5355\uff08\u524d\u7aef\u9759\u6001\u8d44\u4ea7\uff0c\u4e0d\u662f\u7b56\u7565/\u914d\u7f6e\u771f\u6e90\uff09", "source": _SRC},
    ".md": {"why": "\u56fe\u7eb8/\u8bb0\u5fc6\u9762\uff08\u540c R-H249 \u56db\uff1a\u4e0d\u6539\u8fd0\u884c\u65f6\u884c\u4e3a\uff09", "source": _SRC},
    ".txt": {"why": "\u6587\u672c\u4ea7\u7269/\u65e5\u5fd7", "source": _SRC},
    ".log": {"why": "\u65e5\u5fd7", "source": _SRC},
    ".lock": {"why": "\u9501\u6587\u4ef6", "source": _SRC},
    ".source": {"why": "\u7b2c\u4e09\u65b9\u5de5\u5177\u4f1a\u8bdd\u5feb\u7167\uff08.mimosa \u4e00\u5bb6 10 \u4e07\uff09", "source": _SRC},
    ".out": {"why": "\u547d\u4ee4\u8f93\u51fa\u4ea7\u7269", "source": _SRC},
    ".sqlite": {"why": "\u672c\u5730\u5e93\u6587\u4ef6", "source": _SRC},
    ".sqlite-shm": {"why": "\u672c\u5730\u5e93\u4fa7\u4ea7\u7269", "source": _SRC},
    ".sqlite-wal": {"why": "\u672c\u5730\u5e93\u4fa7\u4ea7\u7269", "source": _SRC},
    ".zip": {"why": "\u6253\u5305\u4ea7\u7269", "source": _SRC},
    ".csv": {"why": "\u6570\u636e\u4ea7\u7269", "source": _SRC},
    ".yml": {"why": "\u914d\u7f6e\u4fa7\u4ea7\u7269", "source": _SRC},
    ".yaml": {"why": "\u914d\u7f6e\u4fa7\u4ea7\u7269", "source": _SRC},
    ".code": {"why": "\u7b2c\u4e09\u65b9\u5de5\u5177\u7f13\u5b58", "source": _SRC},
    ".bmp": {"why": "\u4f4d\u56fe", "source": _SRC},
    ".woff": {"why": "\u5b57\u4f53\u8d44\u6e90", "source": _SRC},
    ".woff2": {"why": "\u5b57\u4f53\u8d44\u6e90", "source": _SRC},
    ".ttf": {"why": "\u5b57\u4f53\u8d44\u6e90", "source": _SRC},
    ".bak": {"why": "\u4e34\u65f6\u5907\u4efd\uff08\u5e94\u56de\u6536\uff0c\u89c1 supersede-check\uff09", "source": _SRC},
    ".mp3": {"why": "音频产物", "source": _SRC},
    ".m4a": {"why": "音频产物", "source": _SRC},
    ".wav": {"why": "音频产物", "source": _SRC},
    ".db": {"why": "本地库文件", "source": _SRC},
    ".geojson": {"why": "地图数据产物", "source": _SRC},
    ".pdf": {"why": "交付产物", "source": _SRC},
    ".exe": {"why": "二进制工具", "source": _SRC},
    ".wasm": {"why": "二进制工具", "source": _SRC},
    ".blend": {"why": "Blender 源文件（资产）", "source": _SRC},
    ".fbx": {"why": "3D 资产", "source": _SRC},
    ".vrm": {"why": "3D 资产", "source": _SRC},
    ".tmp": {"why": "临时件（应回收）", "source": _SRC},
    ".example": {"why": "示例模板", "source": _SRC},
    ".dpapi": {"why": "🔴 **凭据密文件**——绝不入账（入账就是把密钥名字写进护照）", "source": _SRC},
    ".vars": {"why": "🔴 **环境变量/凭据件**（.dev.vars）——绝不入账", "source": _SRC},
    ".prisma": {"why": "Prisma 模型（独立服务）", "source": _SRC},
    ".sql": {"why": "SQL 脚本（独立服务面）", "source": _SRC},
    ".ini": {"why": "测试口径侧配置（非框架运行时）", "source": _SRC},
    "": {"why": "\u65e0\u540e\u7f00\u4ef6\uff08\u9501/\u6807\u8bb0/\u4e34\u65f6\uff09", "source": _SRC},
}

DECLARED_NOT_WATCHED: Dict[str, Dict[str, str]] = {
    # R-H990（2026-10-15 · 主人令「绝对不能有任何盲区」）：三方工具库与产物面
    "projects": {"why": "项目资料与素材（音频/模型），不改运行时行为", "source": _SRC},
    "skills": {"why": "第三方 skill 库（.tsx/.ts/.mjs 是它们自带的），非本框架源码", "source": _SRC},
    ".agents": {"why": "第三方 agent 工具技能缓存", "source": _SRC},
    ".claude": {"why": "第三方 agent 工具技能缓存", "source": _SRC},
    ".zcode": {"why": "第三方工具缓存", "source": _SRC},
    ".fleet": {"why": "第三方工具缓存", "source": _SRC},
    "plugins": {"why": "外部插件面（非本框架源码；若有在役件改走显式单文件纳入）", "source": _SRC},
    "auth-service": {"why": "独立认证服务（自有入口与部署）", "source": _SRC},
    "prisma": {"why": "独立服务的 ORM 面", "source": _SRC},
    "out": {"why": "产物目录", "source": _SRC},
    "output": {"why": "产物目录", "source": _SRC},
    "videos": {"why": "成片产物", "source": _SRC},
    "video-src": {"why": "视频源素材", "source": _SRC},
    "vercel-brand-protected": {"why": "部署侧产物", "source": _SRC},
    "state": {"why": "产物与账本面（**真源头 state/theme/** 已走显式单文件纳入**）", "source": _SRC},
    "memory": {"why": "记忆面（同 R-H249 四）", "source": _SRC},
    "docs": {"why": "图纸面（同 R-H249 四）", "source": _SRC},
    "vaults": {"why": "记忆库/资料面", "source": _SRC},
    "render": {"why": "渲染产物", "source": _SRC},
    "assets": {"why": "素材库", "source": _SRC},
    "data": {"why": "数据/资料面", "source": _SRC},
    "config": {"why": "配置面（非框架运行时代码）", "source": _SRC},
    ".openclaw": {"why": "外部工具目录，内容几乎全是 tmp 临时脚本（是草稿不是源）",
                  "source": WATCH_DOC + " · 二 · 逐个判定"},
    "审美相关skill": {"why": "设计素材库（skill 骨架示例 html），是资料不是运行代码",
                      "source": WATCH_DOC + " · 二 · 逐个判定"},
    "agent-gvmz-gbtv8": {"why": "另一个 agent 的工作区，不是本框架的源码面",
                         "source": WATCH_DOC + " · 二 · 逐个判定"},
    "delivery": {"why": "交付产物（生成的 html/png），产物变化不该触发「框架被改」",
                 "source": WATCH_DOC + " · 二 · 逐个判定"},
    ".backups": {"why": "备份快照；R-H176 起已显式列入门的跳过目录（免得被顺手纳进来）",
                 "source": WATCH_DOC + " · 二 · 逐个判定"},
    # R-H249 · 四类拍板：
    "gbt_allinone/docs": {
        "why": "**图纸面**（设计文档 / 报告 / 图纸）：改了不改**运行时行为** ⇒ 不占门的监视成本；"
               "仍然走 git + memory + 待落刀登记，不是「没人管」",
        "source": BLIND_DOC + " · 四 · 图纸面显式不纳（Owner 2026-09-20 拍板）"},
    "brain": {
        "why": "R-H249 取证：**0 真导入 · 0 动态引用 · 0 启动器引用**（只在文档里被提到）"
               "⇒ 当下不是运行时面；**将来真接上调用点，再纳**",
        "source": BLIND_DOC + " · 四 · 取证后不纳（Owner 2026-09-20 拍板）"},
    "caps": {
        "why": "同上：caps/design_brain/run.py 有 `# gbt-capability:` 头但**无注册、无调用点**；"
               "⇒ 取证后不纳，接上再纳",
        "source": BLIND_DOC + " · 四 · 取证后不纳（Owner 2026-09-20 拍板）"},
}

# 根级**指令类**文件：改一个字就改行为，但门的根级白名单只按**名字**收。
# 本模块**不擅自替门决定**纳不纳 —— 只把这批列出来，交主人拍（这就是「未决定」的价值）。
ROOT_INSTRUCTION_HINT = (
    "IDENTITY.md", "SELF_INTRO.md", "TOOLS.md", "DESIGN.md", "INDEX.md",
    "INTERACTIONS.md", "TASK_ROUTER.md", "REDESIGN.md", "OUTPUT_RULES.md",
    "PRD_INGESTION.md", "CODE_INGESTION.md", "UI-check.md",
    "visual-asset-director.md",
)


def _gate():
    from . import framework_gate as fg
    return fg


def _norm(rel: str) -> str:
    return str(rel).replace("\\", "/").strip("/")


def classify(rel: str) -> Tuple[str, str]:
    """**纯函数**：给一个相对路径，回 (状态, 备注)。测试直接驱动它。"""
    r = _norm(rel)
    if not r:
        return "未决定", "空路径"
    fg = _gate()
    parts = r.split("/")
    top = parts[0]
    name = parts[-1]
    under_watch_dir = top in fg._WATCH_DIRS
    suffix = os.path.splitext(name)[1].lower()

    # ① 门自己声明的跳过目录（依赖树 / 缓存 / 产物）—— 命中即「显式不纳入」
    if any(p in fg._SKIP_DIRS for p in parts):
        skipped = [p for p in parts if p in fg._SKIP_DIRS]
        return "显式不纳入", "门自己声明的跳过目录：%s" % ",".join(skipped)

    # ② 已纳入：按门**自己的**四条规则判（目录+后缀 / 根级名白名单 / 根级后缀 / 显式单文件）
    #    ⚠️ 顺序刻意放在"声明"之前：门看得见的，不许被本清单标成"不纳"（标了就是两处打架）
    if under_watch_dir and name.lower().endswith(tuple(fg._WATCH_SUFFIX)):
        return "已纳入", "目录 %s + 后缀 %s" % (top, suffix)
    if "/" not in r and name not in tuple(fg._WATCH_ROOT_EXCLUDE) \
            and name.lower().endswith(tuple(fg._WATCH_ROOT_SUFFIX)):
        return "已纳入", "根级行为面（R-H249：根级 %s 按后缀收）" % suffix
    if "/" not in r and r in fg._WATCH_ROOT_FILES:
        return "已纳入", "根级指令文件白名单"
    if r in tuple(fg._WATCH_EXTRA_FILES):
        return "已纳入", "显式单文件（被代码真读）"

    # ③ 主人记忆载体：**显式不纳**（门自己写明的排除），不是"忘了纳"
    if "/" not in r and name in tuple(fg._WATCH_ROOT_EXCLUDE):
        return "显式不纳入", "主人自己的记忆载体（门显式排除：另有归属规则，不属于框架自改）"

    # ④ 已判过不纳的目录 / 前缀 —— 引用出处，本清单不改判
    for key, row in DECLARED_NOT_WATCHED.items():
        if r == key or r.startswith(key + "/"):
            return "显式不纳入", "%s（出处：%s）" % (row["why"], row["source"])

    # ④c 备份散件（文件名含 `.bak`）—— R-H990 补（2026-10-17 实测：6 件门盲区里 5 件是它）。
    #     `cloud_llm.py.bak-inject` / `model-rigged-anim.glb.bak-metal0-…` 的后缀是
    #     `.bak-inject` / `.bak-metal0-…`（**没有可识别后缀**）⇒ 原先全落进 ⑤ 未决定。
    #     它们不是"门要看的真源"（备份=旧内容副本，改了不影响运行时行为）⇒ 对门**显式不纳**；
    #     清理归「新增即清旧」（supersede / clean_residue），**不在这里判生死**。
    if ".bak" in name.lower():
        return "显式不纳入", ("备份散件（文件名含 .bak）——不是门要看的真源；"
                              "清理由「新增即清旧」负责（出处：%s）" % _SRC)

    # ④b 后缀级显式不纳（R-H990 · 2026-10-15）——
    #     「非源码后缀」此前一律落在 ⑤ 未决定 ⇒ 11 万个文件全是"盲区"（`.mimosa` 一家就 10 万）。
    #     本清单按主人令「绝对不能有任何盲区」把它们**逐类显式声明**（理由见文档 §三），
    #     不是静默放过：**凡是真源码后缀（.py/.js/.mjs/.ts/…）都不在此表内**，
    #     新出现的后缀由 `test_blindspot_registry.py` 咬住并要求先入门再声明。
    if suffix in DECLARED_NOT_WATCHED_EXT:
        row = DECLARED_NOT_WATCHED_EXT[suffix]
        return "显式不纳入", "%s（出处：%s）" % (row["why"], row["source"])
    if not suffix and "" in DECLARED_NOT_WATCHED_EXT:
        row = DECLARED_NOT_WATCHED_EXT[""]
        return "显式不纳入", "%s（出处：%s）" % (row["why"], row["source"])

    # ⑤ 其余 = 未决定（**门盲区**）
    if "/" not in r and r in ROOT_INSTRUCTION_HINT:
        return "未决定", "根级指令类文件（R-H249 前的老口径；现已按后缀纳入，此行不该再出现）"
    if "/" not in r:
        return "未决定", "根级文件（既不在门的后缀规则里，也没有声明）"
    return "未决定", "顶层目录 %s 不在门的可见范围内" % top


def scan(root: Optional[Path] = None) -> Dict[str, Any]:
    """只读扫描：把盘上每个文件归到三态之一。**不写盘、不改门。**

    2026-09-22 改动：扫描范围收敛到 `tools/scan_scope.py` 的**唯一口径**。
    此前这里自己维护一份 `fg._SKIP_DIRS`，与别处三份名单各自过期，
    结果本机这棵树上**直接走不完 30s 单测超时**（vendor/pylibs 3106 个 .py 等）。
    被排除的外部语料**不是消失，而是各占一行**标为「显式不纳入」并写明体量 ——
    边界要看得见，才不叫天窗；读不到的目录同样留一行，盲区必须可见。
    """
    from . import scan_scope

    fg = _gate()
    base = Path(root) if root else Path(fg.ROOT)
    rows: List[Dict[str, Any]] = []
    skip = set(scan_scope.SKIP_DIRS) | set(getattr(fg, "_SKIP_DIRS", ())) | {".git"}

    def _err(e):                                            # noqa: ANN001
        rows.append({"path": str(getattr(e, "filename", "?") or "?"), "state": "未决定",
                     "why": "读不到的目录（%s）—— 盲区必须可见" % type(e).__name__,
                     "ext": "(目录)"})

    for dirpath, dirnames, filenames in os.walk(base, onerror=_err):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                rel = _norm(str(p.relative_to(base)))
            except ValueError:
                continue
            state, why = classify(rel)
            rows.append({"path": rel, "state": state, "why": why,
                         "ext": os.path.splitext(name)[1].lower() or "(无后缀)"})
    sizes = scan_scope.corpus_sizes(base)
    for cname, reason in scan_scope.EXTERNAL_CORPORA.items():
        s = sizes.get(cname) or {}
        if not s.get("exists"):
            continue
        rows.append({
            "path": cname + "/", "state": "显式不纳入",
            "why": "%s（%d 个 .py / %.1f MB，整棵不入扫描范围）"
                   % (reason, s["py_files"], s["bytes"] / 1048576),
            "ext": "(目录)"})
    return {"ok": True, "readonly": True, "root": str(base),
            "files": rows, "count": len(rows)}


def by_state(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {s: [] for s in STATES}
    for r in rows:
        out.setdefault(r.get("state") or "(无状态)", []).append(r)
    return out


def blind_spots(rows: Optional[List[Dict[str, Any]]] = None,
                root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """**门盲区清单**：所有「未决定」的顶层项（按文件数降序）。"""
    rows = rows if rows is not None else scan(root)["files"]
    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if r["state"] != "未决定":
            continue
        top = r["path"].split("/")[0]
        key = r["path"] if "/" not in r["path"] else top
        row = agg.setdefault(key, {"item": key, "kind": "文件" if "/" not in r["path"] else "目录",
                                   "files": 0, "exts": {}, "why": r["why"]})
        row["files"] += 1
        row["exts"][r["ext"]] = row["exts"].get(r["ext"], 0) + 1
    out = sorted(agg.values(), key=lambda x: (-x["files"], x["item"]))
    for row in out:
        row["top_exts"] = sorted(row["exts"].items(), key=lambda kv: -kv[1])[:4]
    return out


def ext_inventory(rows: Optional[List[Dict[str, Any]]] = None,
                  root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """后缀口径：每种后缀在三态各有多少文件（回答「门吃不吃 .md」这种问题）。"""
    rows = rows if rows is not None else scan(root)["files"]
    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        row = agg.setdefault(r["ext"], {s: 0 for s in STATES})
        row[r["state"]] = row.get(r["state"], 0) + 1
    out = []
    for ext, counts in sorted(agg.items(), key=lambda kv: -sum(kv[1].values())):
        out.append({"ext": ext, "counts": counts,
                    "total": sum(counts.values()),
                    "watched": counts.get("已纳入", 0) > 0})
    return out


# ── 机械闸 ──────────────────────────────────────────────────────────────

def check_three_states(rows: List[Dict[str, Any]]) -> dict:
    """闸①：每个文件必须落在三态之一 —— **不许有沉默的文件**。"""
    bad = [r["path"] for r in rows if r.get("state") not in STATES]
    if bad:
        return {"ok": False, "denied": True, "rule": "state_missing",
                "count": len(bad), "sample": bad[:5],
                "why": "归不到三态 = 门连「自己不知道」都没登记"}
    return {"ok": True, "readonly": True, "checked": len(rows)}


def check_declared_reasons() -> dict:
    """闸②：显式不纳入**必须带理由与出处**（与坑册 §57 同族：不许无标注的空）。"""
    bad = [k for k, v in DECLARED_NOT_WATCHED.items()
           if not str(v.get("why") or "").strip()
           or not str(v.get("source") or "").strip()]
    if bad:
        return {"ok": False, "denied": True, "rule": "declared_without_reason",
                "bad": bad,
                "why": "不纳也要有理由和出处；否则「不纳」和「忘了」分不出来"}
    return {"ok": True, "readonly": True, "declared": len(DECLARED_NOT_WATCHED)}


def check_watched_without_rule(rows: List[Dict[str, Any]]) -> dict:
    """闸③：标成「已纳入」的，必须真命中门的四条规则之一（防标错）。"""
    fg = _gate()
    bad = []
    for r in rows:
        if r["state"] != "已纳入":
            continue
        p = r["path"]
        name = p.split("/")[-1]
        ok = ((p.split("/")[0] in fg._WATCH_DIRS
               and name.lower().endswith(tuple(fg._WATCH_SUFFIX)))
              or ("/" not in p and name not in tuple(fg._WATCH_ROOT_EXCLUDE)
                  and name.lower().endswith(tuple(fg._WATCH_ROOT_SUFFIX)))
              or ("/" not in p and p in fg._WATCH_ROOT_FILES)
              or p in tuple(fg._WATCH_EXTRA_FILES))
        if not ok:
            bad.append(p)
    if bad:
        return {"ok": False, "denied": True, "rule": "watched_without_rule",
                "count": len(bad), "sample": bad[:5],
                "why": "标了「已纳入」但门的三条规则都不认 ⇒ 清单与门已经不一致"}
    return {"ok": True, "readonly": True}


def check_sample(rows: List[Dict[str, Any]]) -> dict:
    """闸④（坑册 §45）：**空清单不是通过** —— 样本数为 0 直接红。"""
    if not rows:
        return {"ok": False, "denied": True, "rule": "no_sample",
                "why": "扫描到 0 个文件 ⇒ 要么路径错、要么被剪枝剪光了；"
                       "空样本不许当绿"}
    return {"ok": True, "readonly": True, "sample": len(rows)}


def audit(root: Optional[Path] = None, rows: Optional[List[Dict[str, Any]]] = None) -> dict:
    """一次跑完全部闸 + 出清单读数。

    🔴 2026-09-23 第 53 轮加 `rows=`（**让"同一时刻的那一份行集"可以被钉住**）：
       原来只能 `audit()` 自己去扫 ⇒ 任何"拿 `audit()` 与另一次 `scan()` 对比"的判据
       **天生要扫两次盘**，中间只要有人动盘，两边就不等 —— 判据在**共用工作区里会飘**。
       第 52 轮树指纹实测：`test_blind_total_matches_scan` 就是这么红的
       （`tree_changed=True`，动盘的是**别人**），而红的原因跟它对不对**毫无关系**。
       ⇒ 允许调用方把行集**递进来**：判据先 `scan()` 一次，再把**同一份**行集交给 `audit()`，
         两次读数取自**同一时刻**，判的还是同一件事（`audit()` 不许拿过期行集算 blind_total）。
       `rows=None` 时行为**与原来逐字相同**（自己去扫）。
    """
    if rows is None:
        sc = scan(root)
        rows = sc["files"]
        root_out = sc["root"]
    else:
        # 行集是调用方给的 ⇒ 根只能照它给的算（不再扫盘）
        root_out = str(root) if root else str(_gate().ROOT)
    gates = {"three_states": check_three_states(rows),
             "declared_reasons": check_declared_reasons(),
             "watched_without_rule": check_watched_without_rule(rows),
             "sample": check_sample(rows)}
    denied = [k for k, v in gates.items() if not v.get("ok")]
    states = by_state(rows)
    return {"ok": not denied, "readonly": True, "root": root_out,
            "counts": {s: len(states.get(s, [])) for s in STATES},
            "gates": gates, "denied": denied,
            "blind_spots": blind_spots(rows),
            "blind_total": len(states.get("未决定", []))}


def run(op="status", **params) -> dict:
    """能力入口（只读）：status / audit / blind / by_ext / not_watched / classify。"""
    op = str(op or "status")
    if op == "status":
        fg = _gate()
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "states": list(STATES),
                "gate_scope": {"dirs": list(fg._WATCH_DIRS),
                               "suffix": list(fg._WATCH_SUFFIX),
                               "root_files": list(fg._WATCH_ROOT_FILES),
                               "root_suffix": list(fg._WATCH_ROOT_SUFFIX),
                               "root_exclude": list(fg._WATCH_ROOT_EXCLUDE),
                               "extra_files": list(fg._WATCH_EXTRA_FILES),
                               "skip_dirs": sorted(fg._SKIP_DIRS)},
                "core": "门必须知道自己看不见什么（坑册 §60）",
                "read_from": "framework_gate 的常量（**本模块不复刻范围表**）",
                "doc": BLIND_DOC}
    if op == "audit":
        return audit(params.get("root"))
    if op == "blind":
        a = audit(params.get("root"))
        return {"ok": True, "readonly": True, "blind_total": a["blind_total"],
                "blind_spots": a["blind_spots"]}
    if op == "by_ext":
        rows = scan(params.get("root"))["files"]
        return {"ok": True, "readonly": True, "exts": ext_inventory(rows)}
    if op == "not_watched":
        return {"ok": True, "readonly": True,
                "declared": {k: dict(v) for k, v in DECLARED_NOT_WATCHED.items()},
                "source_doc": WATCH_DOC}
    if op == "classify":
        st, why = classify(str(params.get("path") or ""))
        return {"ok": True, "readonly": True, "path": params.get("path"),
                "state": st, "why": why}
    if op == "gate_states":
        return check_three_states(scan(params.get("root"))["files"])
    if op == "gate_declared":
        return check_declared_reasons()
    if op == "gate_watched":
        return check_watched_without_rule(scan(params.get("root"))["files"])
    if op == "gate_sample":
        return check_sample(scan(params.get("root"))["files"])
    raise ValueError("未知 op %r（可用：status/audit/blind/by_ext/not_watched/classify/"
                     "gate_states/gate_declared/gate_watched/gate_sample）" % (op,))


HONEST_BOUNDARY = (
    "本模块保证『门看得见什么 / 看不见什么』可查、可判、可复算；"
    "它保证不了『盲区一定该纳』——纳不纳是主人的决定。"
    "它**不动门**：监视范围仍由 framework_gate 的三条常量说了算；"
    "本模块只做两件事：把三态算出来、把「未决定」原样摆在桌面上。"
)
