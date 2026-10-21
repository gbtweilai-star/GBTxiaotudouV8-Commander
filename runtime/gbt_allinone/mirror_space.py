"""GBT小土豆V8 · 镜像多维度空间（部署维度）——所有假设与架构虚拟的最终归宿。

Owner 定调（2026-09-11）：镜像多维度空间是生产最后的防线（与 pipeline 同源同律）。
任何项目要上线，必须先在镜像空间的一个维度里成形、打磨、验证——
维度内随便改（假设/推翻/重来，生产永远无感知），跨维晋升才写生产：
一次性全量、不修改一次、不污染文件、一步到位（打败"Claude 式生产边改边崩"）。

维度语义（与 pipeline 的镜像→门禁→生产同构，升维到整项目部署）：
  store/mirror_space/dimension/     镜像维度（随便改：假设/架构虚拟/反复打磨全在这里）
  store/mirror_space/reality/       生产现实（唯一真实：只经跨维晋升一次性写入）
  store/mirror_space/timelines/     时间线（每次晋升的全量快照——回滚=回到过去的时间线）
  store/mirror_space/passports/     跨维护照（清单+逐文件指纹+验证矩阵+版本）

能力（维度操作）：
  mirror_shape     维度成形（写镜像维度——可反复、可覆盖、不设限）
  mirror_scan      维度体检（完整性/署名/纪律/入口——跨维晋升前置）
  mirror_ascend    跨维晋升（验证全绿才放行；一次性全量写入现实+护照+时间线）
  mirror_status    维度状态（镜像/现实指纹、现实漂移检测、时间线史）
  mirror_rewind    时间线回滚（同样一次性全量替换，不改现实单文件）
"""
import hashlib
import json
import shutil
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent


def _resolve_store() -> Path:
    """store 基址单一来源（O35 扩展）：包内走 _paths.STORE_DIR；独立加载
    （checkpoint._load_sibling 走 spec_from_file_location，无包上下文）按同目录
    _paths.py 回退；两者都不可用才退回 GBT_STORE_DIR / 默认（保底，勿依赖）。"""
    try:
        from . import _paths as _p           # 包内导入（首选）
        return Path(_p.STORE_DIR)
    except Exception:
        pass
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "gbt_mirror_space__paths", Path(__file__).resolve().parent / "_paths.py")
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return Path(_mod.STORE_DIR)
    except Exception:
        pass
    _env = __import__("os").getenv("GBT_STORE_DIR")
    return Path(_env).resolve() if _env else (_BASE / "store")


_STORE = _resolve_store()
_MIRROR = _STORE / "mirror_space"
_DIM = _MIRROR / "dimension"
_REALITY = _MIRROR / "reality"
_TIMELINES = _MIRROR / "timelines"
_PASSPORTS = _MIRROR / "passports"


def _audit(event, meta):
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


def _sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _tree_fingerprint(root: Path) -> dict:
    """全量清单：{相对路径: {sha, size}}（仅文件，跳过空目录）。"""
    out = {}
    if not root.exists():
        return out
    for f in sorted(root.rglob("*")):
        if f.is_file():
            rel = f.relative_to(root).as_posix()
            out[rel] = {"sha": _sha_file(f), "size": f.stat().st_size}
    return out


# ── 镜像部署区（沙箱：随便改）──

def _replace_tree(src: Path, dst: Path) -> None:
    """整树一次性替换（先清后拷）—— 镜像 / 房间 / 生产共用同一处实现。

    由来（2026-09-19 · R-H97）：`room_space.release()` 一直在调本函数，
    而本模块**从来没有过它** ⇒ 房间放行这条路结构上一次都没跑通过
    （`AttributeError: module 'gbt_allinone.mirror_space' has no attribute '_replace_tree'`）。
    同类"名字对不上"已出现三次（`mirror_release` 的入参、`one_key_deploy` 的入参、这里）——
    凡是跨模块调用的私有名，都必须有一条用例把它钉住。
    """
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def shape(path: str, content: str, note: str = "") -> dict:
    """写镜像部署区（可反复覆盖——假设/试验/打磨全在这里，永不触碰生产）。"""
    p = _DIM / path
    # 防越界（stage 内相对路径）
    resolved = p.resolve()
    if not str(resolved).startswith(str(_DIM.resolve())):
        return {"ok": False, "error": "路径越界：只允许 stage 内相对路径"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(content), encoding="utf-8")
    _audit("deploy_stage_write", {"path": path, "bytes": len(str(content)), "note": note[:60]})
    return {"ok": True, "path": path, "sha": _sha_file(p), "stage": True}


def shape_bytes(path: str, data: bytes, note: str = "") -> dict:
    """写镜像部署区（**二进制安全**）：图片/字体/模型等不许当文本读。

    实测由来（2026-09-19 · R-H96）：`one_key_deploy` 本地模式对每个文件都走
    `read_text(errors="replace")` ⇒ PNG/GLB/字体一律被替换字符污染，**镜像区里的产物当场变废**，
    再晋升出去就是"上线了一个坏的"。文本页走 `shape()`（要注入署名），
    二进制一律走本函数，**逐字节**落盘。
    """
    p = _DIM / path
    resolved = p.resolve()
    if not str(resolved).startswith(str(_DIM.resolve())):
        return {"ok": False, "error": "路径越界：只允许 stage 内相对路径"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(bytes(data))
    _audit("deploy_stage_write", {"path": path, "bytes": len(data), "binary": True, "note": note[:60]})
    return {"ok": True, "path": path, "sha": _sha_file(p), "stage": True, "binary": True}


def unshape(path: str) -> dict:
    p = _DIM / path
    resolved = p.resolve()
    if not str(resolved).startswith(str(_DIM.resolve())):
        return {"ok": False, "error": "路径越界"}
    if p.is_file():
        p.unlink()
    elif p.is_dir():
        shutil.rmtree(p)
    else:
        return {"ok": False, "error": f"stage 不存在: {path}"}
    _audit("deploy_stage_delete", {"path": path})
    return {"ok": True, "deleted": path}


def dimension_tree() -> dict:
    return {"ok": True, "stage": _tree_fingerprint(_DIM)}


# ── 验证（晋升前置条件）──

def scan() -> dict:
    """验证镜像部署区：晋升生产前的全量检查矩阵。"""
    t0 = time.time()
    checks = {}

    # 1) 非空
    tree = _tree_fingerprint(_DIM)
    checks["non_empty"] = {"ok": len(tree) > 0,
                            "detail": f"{len(tree)} 文件"}

    # 2) 完整性：无空文件（0 字节 = 半成品）
    empty = [r for r, v in tree.items() if v["size"] == 0]
    checks["no_empty_files"] = {"ok": not empty, "detail": f"空文件: {empty[:5]}" if empty else "无"}

    # 3) 署名：文本页面须带开发者署名（html/md/txt）
    from . import signature as _sig
    missing_sig = []
    for r in tree:
        p = _DIM / r
        if p.suffix.lower() in (".html", ".htm", ".md", ".txt"):
            try:
                if not _sig.has_signature(p.read_text(encoding="utf-8", errors="replace")):
                    missing_sig.append(r)
            except Exception:
                pass
    checks["signature"] = {"ok": not missing_sig,
                            "detail": f"缺署名: {missing_sig[:5]}" if missing_sig else "全部携带"}

    # 4) 纪律：无临时残留（_*.py / *.tmp / __pycache__）
    junk = [r for r in tree if r.split("/")[-1].startswith("_") and r.endswith(".py")
            or r.endswith(".tmp") or "__pycache__" in r]
    checks["discipline"] = {"ok": not junk,
                             "detail": f"残留: {junk[:5]}" if junk else "干净"}

    # 5) 结构：至少一个入口（index.html / main.py / app.py 之一）
    entries = [r for r in tree if r.split("/")[-1] in ("index.html", "main.py", "app.py", "start.ps1")]
    checks["entry_point"] = {"ok": bool(entries), "detail": f"入口: {entries[:3]}" if entries else "缺入口文件"}

    passed = sum(1 for c in checks.values() if c["ok"])
    result = {"ok": passed == len(checks), "passed": passed, "total": len(checks),
              "checks": checks, "files": len(tree),
              "elapsed_ms": round((time.time() - t0) * 1000, 1)}
    _audit("deploy_validate", {"passed": passed, "total": len(checks), "files": len(tree)})
    return result


# ── 生产晋升（唯一生产写入口）──

def ascend(purpose: str = "", owner_override: bool = False,
           override_reason: str = "") -> dict:
    """一次性全量晋升：验证全绿 → stage 全量复制到 production → 护照 + 版本快照。

    生产区零修改纪律：本函数是唯一写 production 的路径；
    晋升 = 全量替换（不是增量打补丁）——一步到位，不存在"改一半"。

    🔴 2026-10-13（主人令逐字：「**技术层面不能给她有限制只保留人工授权护栏即可**」·
       「**直接改成终端YES才能使用就好了有时候我需要用到的啊**」）：
      「验证未全绿」**不再是一道谁都过不去的死限**，改成**人工授权才放行**：
        · 默认（不带 owner_override）：照旧卡住，并在返回里给出**怎么放行**；
        · 放行：主人在**终端**发**专用一次性钥匙** `deploy_force`（提示符敲 YES 确认）后，
          调用方再**显式**声明 `owner_override=true` ⇒ 晋升照做，并**大声落审计**
          （`deploy_promote_overridden`，含未绿的检查项与放行理由）。
      🔴 钥匙是**门外那道门**认的（`policy.evaluate` 见到 `owner_override` 就改要 `deploy_force`）⇒
      旗标本身**不带任何授权**，模型无法自我解锁；主人也可以只发"正常发布"的钥匙而不发这一把。
    """
    v = scan()
    if not v.get("ok"):
        failed = [k for k, c in v["checks"].items() if not c["ok"]]
        if not owner_override:
            _audit("deploy_promote_blocked", {"failed": failed})
            return {"ok": False, "blocked": True, "reason": "验证未全绿，禁止晋升",
                    "validate": v,
                    "如何放行": ("这不是技术层死限：主人在终端发**专用一次性钥匙** `deploy_force`"
                              "（python -m gbt_allinone auth grant --scope deploy_force --ttl 600，"
                              "提示符敲 YES），再带 owner_override=true 重调即可放行；"
                              "放行会写审计 deploy_promote_overridden。")}
        _reason = str(override_reason or purpose or "(未写理由)")[:200]
        _audit("deploy_promote_overridden", {"failed": failed, "reason": _reason})
        _override = {"放行依据": "主人终端授权（deploy_force · 专用一次性钥匙 · 提示符 YES）+ 调用方显式 owner_override",
                     "放行理由": _reason, "未绿的检查项": failed}
    else:
        _override = None

    tree = _tree_fingerprint(_DIM)
    version = _next_version()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    # 版本快照（晋升前先存档当前 stage 全量）
    vdir = _TIMELINES / f"v{version}"
    if vdir.exists():
        shutil.rmtree(vdir)
    shutil.copytree(_DIM, vdir)

    # 生产全量替换（先清后拷——一步到位）
    if _REALITY.exists():
        shutil.rmtree(_REALITY)
    shutil.copytree(_DIM, _REALITY)

    # 部署护照
    passport = {
        "version": version,
        "promoted_at": ts,
        "purpose": purpose[:120],
        "files": len(tree),
        "manifest": tree,          # 逐文件指纹（生产漂移检测基准）
        "validate": {"passed": v["passed"], "total": v["total"]},
        "override": _override,     # 人工授权放行的凭据（默认 None = 全绿正常晋升）
        "law": "生产零修改：本次晋升后 production 任何变动即视为漂移",
    }
    _PASSPORTS.mkdir(parents=True, exist_ok=True)
    (_PASSPORTS / f"v{version}.json").write_text(
        json.dumps(passport, ensure_ascii=False, indent=2), encoding="utf-8")

    _audit("deploy_promoted", {"version": version, "files": len(tree), "purpose": purpose[:60]})
    return {"ok": True, "version": version, "files": len(tree),
            "promoted_at": ts, "passport": str(_PASSPORTS / f"v{version}.json"),
            "放行依据": _override,
            "law": passport["law"]}


def _next_version() -> int:
    if not _TIMELINES.exists():
        return 1
    nums = [int(d.name[1:]) for d in _TIMELINES.glob("v*") if d.name[1:].isdigit()]
    return (max(nums) + 1) if nums else 1


# ── 状态与漂移检测 ──

def mirror_status() -> dict:
    """部署门状态：stage/production 指纹 + 漂移检测 + 版本史。"""
    stage_tree_ = _tree_fingerprint(_DIM)
    prod_tree = _tree_fingerprint(_REALITY)
    drift = []
    all_keys = set(stage_tree_) | set(prod_tree)
    for k in sorted(all_keys):
        s = stage_tree_.get(k)
        p = prod_tree.get(k)
        if s is None:
            drift.append({"file": k, "kind": "production_extra", "detail": "生产多出（未走晋升）"})
        elif p is None:
            drift.append({"file": k, "kind": "not_yet_promoted", "detail": "镜像有、生产无（待晋升）"})
        elif s["sha"] != p["sha"]:
            drift.append({"file": k, "kind": "diverged", "detail": "镜像与生产分叉"})

    # 生产自身漂移（对照最近护照）
    prod_drift = []
    passports = sorted(_PASSPORTS.glob("v*.json"), key=lambda p: int(p.stem[1:])) if _PASSPORTS.exists() else []
    if passports:
        latest = json.loads(passports[-1].read_text(encoding="utf-8"))
        manifest = latest.get("manifest", {})
        for k in set(manifest) | set(prod_tree):
            m = manifest.get(k)
            p = prod_tree.get(k)
            if m is None:
                prod_drift.append({"file": k, "kind": "added_after_promote", "detail": "晋升后新增"})
            elif p is None:
                prod_drift.append({"file": k, "kind": "deleted_after_promote", "detail": "晋升后被删"})
            elif m.get("sha") != p.get("sha"):
                prod_drift.append({"file": k, "kind": "modified_after_promote", "detail": "晋升后被改（违反零修改纪律）"})

    return {"ok": True,
            "dimension": {"files": len(stage_tree_)},
            "reality": {"files": len(prod_tree),
                         "version": (len(passports) if passports else 0)},
            "dimension_vs_reality": drift[:20],
            "reality_drift": prod_drift[:20],
            "clean": not prod_drift,
            "timelines": len(passports),
            # 旧键兼容（镜像多维度空间话语统一前的名称）
            "stage": {"files": len(stage_tree_)},
            "production": {"files": len(prod_tree), "version": (len(passports) if passports else 0)},
            "stage_vs_prod": drift[:20],
            "production_drift": prod_drift[:20],
            "versions": len(passports)}


# ── 回滚（同样一步到位）──

def rewind(version: int) -> dict:
    """回滚生产到历史版本（全量替换，不改单文件）。"""
    vdir = _TIMELINES / f"v{version}"
    if not vdir.exists():
        return {"ok": False, "error": f"版本不存在: v{version}"}
    if _REALITY.exists():
        shutil.rmtree(_REALITY)
    shutil.copytree(vdir, _REALITY)
    _audit("deploy_rollback", {"to": version})
    return {"ok": True, "rolled_back_to": version,
            "note": "回滚同样是一次性全量替换，不改生产单文件"}


# ── 旧名兼容别名（镜像多维度空间话语统一前的名称）──
stage_write = shape
stage_delete = unshape
stage_tree = dimension_tree
validate = scan
promote = ascend
rollback = rewind
status = mirror_status


# 公开别名（设计 §九② —— 落生产时加在 mirror_space.py 两副本上）
tree_fingerprint = _tree_fingerprint

# AGENTS.md 兼容别名：mirror_fusion.get_mirror() → mirror_space.scan()
get_mirror = scan
