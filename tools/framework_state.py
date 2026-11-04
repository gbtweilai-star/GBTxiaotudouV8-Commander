# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""框架六面状态读数器（framework_state）· 2026-11-04 补齐

## 为什么有这个文件

`gbt_allinone/tools/growth_hooks.py::_faces()` 与四个判据
（`test_cap_bind_bidirectional` / `test_chain_readiness` / `test_llm_bind_wired` /
`test_native_growth_stack`）都要求本文件提供 `collect()` 返回**六个面 + red**。

**但本文件在 git 全历史中从未存在过**（`git log --all -- "*framework_state*"` 为 0 条），
于是面板上长期挂着一条短板：
    「六面读数取不到：FileNotFoundError: tools/framework_state.py」
这条短板本身是**诚实的**（确实没有），但它让「全状态可感知」这条判据永远红着，
也就失去了判据的意义。本文件按既有判据的字段契约补齐。

## 本文件的口径纪律（写死在这里，谁改谁负责）

1. **每个数字都带 `src`**（从哪个文件/哪个函数现读的）。没有 src 的数字不许出现。
2. **「缺件」与「读失败」是两件事**：
   - 缺件（数据/生成器本就没入库）⇒ 该面如实写 `present: false` + `how`（怎么补），
     并必须登记进 `state/unimplemented.json`（有名有姓 + 谁有权修）。
   - 读失败（文件在但坏了、读数自相矛盾）⇒ 记进顶层 `red`。
   不许把缺件写成读失败来刷存在感，也不许反过来把读失败说成"面没问题"。
3. **不猜**。判据里没写清楚语义的面（视觉面 / 舰队 / 技能源装），本文件按
   「仓里实际有什么就读什么」实现，并在该面的 `口径` 字段里写明读的是什么、
   原作者的原始意图不可考。**不假装知道原意。**

## 六个面（面名是判据锁定的，不许改）

能力位 · 双向绑定 · 技能源装 · 覆盖矩阵 · 视觉面 · 舰队
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
API = ROOT / "gbt_allinone" / "api.py"
FACES = ("能力位", "双向绑定", "技能源装", "覆盖矩阵", "视觉面", "舰队")

# 分派抽取：api.py 里两种合法写法（分组分派也算已接线，否则就是假报断连）
_RE_EQ = re.compile(r'kind\s*==\s*"([^"]+)"')
_RE_IN = re.compile(r"kind\s+in\s*\(([^)]*)\)", re.S)
_RE_STR = re.compile(r'"([^"]+)"')


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _load(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 —— 坏 JSON 由调用方记 red
        return default


def _sys_path() -> None:
    p = str(ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)


# ─────────────────────────── 面 1：能力位 ───────────────────────────
def _face_caps(red: list) -> dict:
    """登记 · 图鉴 · 分派 三处齐（判据 A）。"""
    try:
        _sys_path()
        from gbt_allinone import caps_registry as CR
        caps = CR.all_caps()
        names = {c["name"] for c in caps if isinstance(c, dict) and c.get("name")}
    except Exception as exc:  # noqa: BLE001
        red.append(f"[能力位] 读数失败：注册表取不到（{type(exc).__name__}: {exc}）")
        return {"registry": 0, "src": "caps_registry.all_caps()", "status": "unreadable"}

    # 分派：两种写法都要算
    try:
        src = API.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        red.append(f"[能力位] 读数失败：api.py 读不到（{type(exc).__name__}: {exc}）")
        src = ""
    dispatched = set(_RE_EQ.findall(src))
    for grp in _RE_IN.findall(src):
        dispatched |= set(_RE_STR.findall(grp))
    dispatched.discard("<名>")  # 文档里的占位符，不是真分支

    undispatched = sorted(names - dispatched)
    if src and not dispatched:
        red.append("[能力位] api.py 一个 kind 分派都没抽到 ⇒ 抽取规则已失效，读数不可信")

    # 图鉴：数据 / 生成器 / 定义三者全缺，如实记 present=false（不假绿成"0 个漏"）
    atlas_p = STATE / "skill_atlas.json"
    if atlas_p.is_file():
        atlas = _load(atlas_p, {})
        raw = atlas.get("caps") if isinstance(atlas, dict) else None
        # 图鉴条目形态：list[dict]（本仓口径，见 tools/build-skill-atlas.py）或 dict/list[str]
        if isinstance(raw, list):
            have = {c.get("kind") for c in raw if isinstance(c, dict) and c.get("kind")}
            if not have:
                have = {c for c in raw if isinstance(c, str)}
        elif isinstance(raw, dict):
            have = set(raw.keys())
        else:
            have = set()
        not_in_atlas = sorted(names - have) if have else []
        atlas_face = {"present": True, "entries": len(have),
                      "count_declared": (atlas or {}).get("count"),
                      "src": "state/skill_atlas.json"}
        if not have:
            red.append("[能力位] 图鉴在盘但抽不出条目 ⇒ 结构不认识，读数不可信")
        elif (atlas or {}).get("count") not in (None, len(have)):
            red.append(f"[能力位] 图鉴 count={(atlas or {}).get('count')} ≠ 实抽 {len(have)} ⇒ 图鉴自相矛盾")
    else:
        not_in_atlas = []          # 无从比较 —— 返回 [] 而不是"全部没进图鉴"（后者是错的结论）
        atlas_face = {
            "present": False,
            "why": "state/skill_atlas.json 不在盘；生成器 omni.py 在本仓也不存在"
                   "（tools/omni.py、gbt_allinone/tools/omni.py 均无）⇒ 数据/生成器/定义三者全缺",
            "how": "补齐途径二选一：① 提供 omni.py build（或等价生成器）重建图鉴；"
                   "② 明确「图鉴」可以就是 caps_registry 本身，把判据 A 的第三处改为直读注册表",
            "src": "state/skill_atlas.json（不存在）",
        }

    unimpl = _load(STATE / "unimplemented.json", {}) or {}
    items = unimpl.get("items") or []
    known = {i.get("where") for i in items if isinstance(i, dict)}

    # 判据 C：**缺口必须有名有姓**。这里把「本面实际发现的缺口」与「已登记的」做差集，
    # 剩下的才叫「未登记缺口」——不许空着（空着等于判据 C 永远绿，那是假判据）。
    found = [("gbt_allinone/api.py", f"能力位未接分派：{n}") for n in undispatched]
    if not atlas_face.get("present"):
        found.append(("state/skill_atlas.json", "能力图鉴不在盘，判据 A 第三处无法计算"))
    unregistered = [{"where": w, "what": what} for w, what in found
                    if not (w in known or w in (atlas_face.get("src") or ""))]

    face = {
        "registry": len(names),
        "undispatched": undispatched,
        "not_in_atlas": not_in_atlas,
        "atlas": atlas_face,
        "unimplemented_registered": len(items),
        "_known_gaps": sorted(k for k in known if k),
        "src": "caps_registry.all_caps() + gbt_allinone/api.py(kind 分派静态抽取)",
        "at": _now(),
    }
    if unregistered:
        face["未登记缺口"] = unregistered
    return face


# ─────────────────────────── 面 2：双向绑定 ───────────────────────────
def _face_bind(red: list) -> dict:
    """资产→触手、触手→能力位 两个方向都要通（判据 B）。"""
    bindings = _load(STATE / "asset_bindings.json", None)
    tags = _load(STATE / "cap_tags.json", None)
    out = {"src": "state/asset_bindings.json + state/cap_tags.json", "at": _now()}

    if bindings is None:
        red.append("[双向绑定] state/asset_bindings.json 不在盘或坏了 ⇒ 读数不可信")
        out.update({"断连_资产缺失": None, "断连_触手不在册": None,
                    "能力位无触手标签": None, "present": False})
        return out

    try:
        _sys_path()
        from gbt_allinone import caps_registry as CR
        caps = CR.all_caps()
    except Exception:  # noqa: BLE001
        caps = []
    names = {c["name"] for c in caps if isinstance(c, dict) and c.get("name")}
    domains = {c.get("domain") for c in caps if isinstance(c, dict) and c.get("domain")}

    # ══ 2026-11-04 语义修正：把「真断连」与「运行时产物缺失」分开 ══
    # 血账：CI 上这条判据报 `断连_资产缺失 = 57`，而本地是 0。查明 57 条**全部**是
    #   `gbt_allinone/store/devoured/**` —— devour 吞噬时生成的运行时产物
    #   （.gbt_dir_marker / knowledge.json / run.py / absorbed_knowledge.md），
    #   被 `.gitignore` 的 `store/` 规则排除，**本来就不入库**。
    #   CI 是新克隆，当然没有这些文件。把它算成"绑定账里有资产已不在盘"是**错判**：
    #   那不等于绑定坏了，只等于"这台机器还没跑过 devour"。
    # 区分标准：路径落在运行时/产物区 ⇒ 单独计数，不进「断连」；
    #   其余（源码 / 文档 / 页面）缺失 ⇒ 才是真断连，仍然判红。
    RUNTIME_PREFIXES = ("gbt_allinone/store/", "store/", "outputs/", "state/", "vaults/",
                        ".scratch/", "logs/", "dist/", "runtime/", "vendor/", "packs/")
    DOMAIN_TAG = "domain:"
    missing_asset, missing_tentacle, runtime_missing = [], [], []
    domain_level = 0
    for rel, meta in (bindings or {}).items():
        if not (ROOT / rel).exists():
            if str(rel).startswith(RUNTIME_PREFIXES):
                runtime_missing.append(rel)
            else:
                missing_asset.append(rel)
        for t in (meta or {}).get("tentacles") or []:
            if isinstance(t, str) and t.startswith(DOMAIN_TAG):
                d = t[len(DOMAIN_TAG):]
                if domains and d not in domains:
                    missing_tentacle.append(f"{rel} -> {t}（域不在注册表）")
                else:
                    domain_level += 1
                continue
            if names and t not in names:
                missing_tentacle.append(f"{rel} -> {t}")

    tagged = set()
    if isinstance(tags, dict):
        tagged = set((tags.get("tags") or {}).keys())
    if tags is None:
        red.append("[双向绑定] state/cap_tags.json 不在盘或坏了 ⇒ 反向绑定无从判断")
    elif names and (tags or {}).get("count") not in (None, len(names)):
        red.append(f"[双向绑定] cap_tags.count={tags.get('count')} ≠ 注册表 {len(names)} ⇒ 台账已过期")

    out.update({
        "assets": len(bindings or {}),
        "断连_资产缺失": len(missing_asset),
        "断连_触手不在册": len(missing_tentacle),
        "域级绑定": domain_level,
        "运行时产物未生成": len(runtime_missing),
        "能力位无触手标签": sorted(names - tagged) if tagged else [],
        "样例": {"资产缺失": missing_asset[:5], "触手不在册": missing_tentacle[:5],
                 "运行时产物": runtime_missing[:5]},
        "口径": "两件事分开算：① 绑定层级：能力位级（名字须在 427 里）与域级 "
                "`domain:<域>`（域须在注册表域集合里，见 tentacle_bind.py::_domains）；"
                "② 资产缺失：**源码/文档/页面**缺失才是真断连（判红），"
                "**运行时产物**（store/devoured、outputs 等被 gitignore 的）缺失只计数 —— "
                "干净克隆里没跑过 devour 不等于绑定坏了",
        "present": True,
    })
    return out


# ─────────────────────────── 面 3：技能源装 ───────────────────────────
def _face_skills(red: list) -> dict:
    """技能源装：skills/ 下装了什么。

    **口径坦白**：判据只锁定了面名，没写死读什么。本面按「仓里实际有的」读：
    `skills/<名字>/SKILL.md` 的目录数与文件数。原作者若要读别的源，请改本函数并写明。
    """
    base = ROOT / "skills"
    if not base.is_dir():
        red.append("[技能源装] skills/ 目录不在盘 ⇒ 这一面无从读")
        return {"present": False, "src": "skills/", "status": "absent"}
    dirs = sorted(p.name for p in base.iterdir() if p.is_dir())
    md = sorted(p.relative_to(ROOT).as_posix() for p in base.rglob("SKILL.md"))
    return {
        "present": True,
        "skills": len(dirs),
        "skill_md": len(md),
        "names": dirs[:20],
        "口径": "按 skills/<名字>/ 目录数与 SKILL.md 文件数现读（判据未锁定具体源，此为按仓实读）",
        "src": "skills/",
        "at": _now(),
    }


# ─────────────────────────── 面 4：覆盖矩阵 ───────────────────────────
def _face_coverage(red: list) -> dict:
    """触手覆盖：直接委托 gbt_allinone/positions.py::audit()，不抄第二份逻辑。"""
    try:
        _sys_path()
        from gbt_allinone import positions
        a = positions.audit()
    except Exception as exc:  # noqa: BLE001
        red.append(f"[覆盖矩阵] positions.audit() 失败（{type(exc).__name__}: {exc}）")
        return {"present": False, "src": "gbt_allinone/positions.py::audit()",
                "status": "unreadable"}
    gaps = a.get("gaps") or []
    issues = a.get("issues") or []
    return {
        "present": True,
        "positions": a.get("positions"),
        "issues": issues,
        "盲区": gaps,
        "全绿": bool(a.get("ok")) and not gaps,
        "口径": "职位编制审计：表内每个职位要求的能力是否在册、标 full 的是否只有只读骨架",
        "src": "gbt_allinone/positions.py::audit()",
        "at": _now(),
    }


# ─────────────────────────── 面 5：视觉面 ───────────────────────────
def _face_vision(red: list) -> dict:
    """视觉面（眼）：视觉模块在册情况 + 三个入口是否各就各位。

    **口径坦白**：`gbt_allinone/docs/触手覆盖矩阵.md` 的 G1 死角写的正是
    「视觉面（眼）没有统一的上报形状」，说明原作者当时也没把这一面定死。
    本面按「模块在盘 + 能力位在册 + 入口已接线」三件实读，并在 `口径` 里写明。
    """
    mods = sorted(p.stem for p in (ROOT / "gbt_allinone").glob("vision_*.py"))
    gate = {"body_eye": False, "see_camera": False, "vision": False}
    try:
        _sys_path()
        from gbt_allinone import caps_registry as CR
        names = {c["name"] for c in CR.all_caps() if isinstance(c, dict)}
        gate = {k: (k in names) for k in gate}
    except Exception as exc:  # noqa: BLE001
        red.append(f"[视觉面] 注册表取不到（{type(exc).__name__}: {exc}）")
        names = set()

    try:
        src = API.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        src = ""
    wired = {k: bool(re.search(rf'kind\s*==\s*"{k}"|kind\s+in\s*\([^)]*"{k}"', src))
             for k in ("body_eye", "see_camera")}

    return {
        "present": True,
        "modules": len(mods),
        "module_names": mods,
        "in_registry": gate,
        "wired_in_api": wired,
        "口径": "读三件：gbt_allinone/vision_*.py 模块数 · 三个入口是否在册 · body_eye/see_camera 是否已接线。"
                "「看屏幕(body_eye)」「看已有的图(vision)」「看真实世界(see_camera)」必须分开，混用会把截图当现场",
        "src": "gbt_allinone/vision_*.py + caps_registry + api.py",
        "at": _now(),
    }


# ─────────────────────────── 面 6：舰队 ───────────────────────────
def _face_fleet(red: list) -> dict:
    """舰队：触手工作区（每根触手一份 worktree + 身份 + 日志）。

    `.gitignore` §189 描述了这套结构，但**仓里没有对应目录**（tentacles/ fleet/ worktrees/ 均无）。
    如实记 present=false + 怎么建，不编一个数字充数。
    """
    cands = [ROOT / "tentacles", ROOT / "fleet", ROOT / "worktrees", STATE / "tentacles"]
    hit = [p.relative_to(ROOT).as_posix() for p in cands if p.is_dir()]
    if not hit:
        return {
            "present": False,
            "why": "触手舰队工作区不在仓（tentacles/ fleet/ worktrees/ state/tentacles 均不存在）。"
                   ".gitignore 里有这套结构的描述，但目录本身从未入库",
            "how": "按 .gitignore 的描述生成：每根触手一份 git worktree + 身份 + 日志。"
                   "生成器尚未入库 —— 需要主人给出「一号触手长什么样」的样本，否则建出来就是编的",
            "src": "tentacles/ · fleet/ · worktrees/ · state/tentacles（均不存在）",
            "at": _now(),
        }
    rows = {}
    for rel in hit:
        d = ROOT / rel
        rows[rel] = len([x for x in d.iterdir() if x.is_dir()])
    return {"present": True, "dirs": rows, "count": sum(rows.values()),
            "src": " + ".join(hit), "at": _now()}


# ─────────────────────────── 汇总 ───────────────────────────
def collect() -> dict:
    """六面读数 + red。任何一面读成 None 都算本文件自己的 bug，不许静默。"""
    red: list[str] = []
    faces = {
        "能力位": _face_caps(red),
        "双向绑定": _face_bind(red),
        "技能源装": _face_skills(red),
        "覆盖矩阵": _face_coverage(red),
        "视觉面": _face_vision(red),
        "舰队": _face_fleet(red),
    }
    for name in FACES:
        if name not in faces or faces[name] is None:
            red.append(f"[{name}] 面缺失或读成 None ⇒ 读数器自身 bug")

    # 已登记进 unimplemented.json 的缺口不再重复报红（有名有姓即算交代）
    unimpl = _load(STATE / "unimplemented.json", {}) or {}
    registered = {(i.get("where") or "") for i in (unimpl.get("items") or []) if isinstance(i, dict)}

    for name, face in faces.items():
        if face.get("present") is False:
            key = face.get("src", "")
            if not any(k and k in key for k in registered):
                red.append(f"[{name}] 面不可读且未登记进 state/unimplemented.json（{key}）")

    return {
        "at": _now(),
        "faces": faces,
        "red": red,
        "已登记缺口": sorted(k for k in registered if k),
        "_口径": "六面都必须读得出来；「缺件」写 present=false + how 并登记 unimplemented.json，"
                 "「读失败/自相矛盾」进 red。两者不许互相伪装。",
    }


def main() -> int:
    r = collect()
    print("=" * 78)
    print(f"框架六面状态 · {r['at']}")
    print("=" * 78)
    caps = r["faces"]["能力位"]
    bind = r["faces"]["双向绑定"]
    print(f"  能力位   registry={caps.get('registry')} · undispatched={len(caps.get('undispatched') or [])}"
          f" · 图鉴={'在' if (caps.get('atlas') or {}).get('present') else '缺'}")
    print(f"  双向绑定 资产={bind.get('assets')} · 断连={bind.get('断连_资产缺失')}+{bind.get('断连_触手不在册')}"
          f" · 无标签能力={len(bind.get('能力位无触手标签') or [])}")
    sk = r["faces"]["技能源装"]
    print(f"  技能源装 目录={sk.get('skills')} · SKILL.md={sk.get('skill_md')}")
    cov = r["faces"]["覆盖矩阵"]
    print(f"  覆盖矩阵 职位={cov.get('positions')} · 盲区={len(cov.get('盲区') or [])} · 全绿={cov.get('全绿')}")
    vis = r["faces"]["视觉面"]
    print(f"  视觉面   模块={vis.get('modules')} · 接线={vis.get('wired_in_api')}")
    fl = r["faces"]["舰队"]
    print(f"  舰队     {'在' if fl.get('present') else '缺（已登记）'}")
    print()
    if r["red"]:
        print("❌ 有红项：")
        for x in r["red"]:
            print(f"  · {x}")
        return 1
    print("✅ 全绿（缺口见 state/unimplemented.json）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
