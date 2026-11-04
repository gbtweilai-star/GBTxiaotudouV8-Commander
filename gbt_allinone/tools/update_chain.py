# -*- coding: utf-8 -*-
# gbt-capability: update_chain  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""本地更新链（P2-13，主人 2026-11-03 选 1：无密钥 hash-only）。

**只在 `state/updates-test/` 里跑**：不下载网络、不碰正式 APP、不重启：
  · init：生成小测试包 + **无签名**清单（sha256 + size + path）；
  · stage：校验清单字段/路径/sha256 → 安全解包到 stages/<id> → 返回一次性 confirm_token；
  · confirm：备份 target → 替换 target → 记 applied；失败回滚；
  · rollback：用最近备份恢复 target。
边界：这是**本机信任文件系统**的 hash-only 链；没有发布签名/信任根，
不能证明“包来自某台构建机”。要跨机分发时再换本地 keypair 方案。
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import time
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = _ROOT / "state" / "updates-test"
TEST_APP_ID = "gbt-xiaotudou-v8-test"
MAX_FILES = 200
MAX_UNCOMPRESSED = 20 * 1024 * 1024


class ChainError(ValueError):
    pass


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_join(root: Path, rel: str) -> Path:
    rel = str(rel or "").replace("\\", "/").strip()
    if not rel or rel.startswith("/") or ".." in rel.split("/") or ":" in rel.split("/")[0]:
        raise ChainError("路径越界")
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ChainError("路径越界")
    return p


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def _guard_root(root) -> Path:
    """更新链根的硬守卫 —— 拦结构锚点，不枚举业务路径。

    由来（2026-11-03 · code_audit DES-001 high / needs_human）：
        `api.py:184` 把 payload **全量透传**成 `**kw`，于是 `root=` 可被外部指定；
        而 confirm/rollback 会对 `root/"target"` 做整树删除
        （本文件 165 / 185 / 202 三处）⇒ root 传歪一次就打到站外目录。

    只拦"结构上绝不该被当成更新链根"的目录：
        磁盘根 / 家目录 / 系统目录 / 仓库根 / 仓库一级目录。
    **不拦** `state/updates-test`，也**不拦** pytest 的 `tempfile.mkdtemp()`
    —— 测试就是用临时目录跑全链（tests/test_update_chain.py:32），守卫不能误伤它。
    """
    r = Path(root).resolve()
    anchors = {
        Path(r.anchor).resolve(),                                        # C:\ 这类磁盘根
        Path.home().resolve(),
        Path(os.environ.get("WINDIR") or "C:/Windows").resolve(),
        Path(os.environ.get("ProgramFiles") or "C:/Program Files").resolve(),
        _ROOT.resolve(),                                                 # 仓库根
    }
    if r in anchors:
        raise ChainError("拒绝：更新链根不能是 %s" % r)
    repo = _ROOT.resolve()
    if repo in r.parents and len(r.relative_to(repo).parts) == 1:
        raise ChainError("拒绝：更新链根不能是仓库一级目录 → %s" % r)
    if r.exists() and not r.is_dir():
        raise ChainError("拒绝：更新链根不是目录 → %s" % r)
    return r


def init_channel(root=TEST_ROOT) -> dict:
    root = _guard_root(root)
    channel = root / "channel"
    target = root / "target"
    _ensure_dir(channel)
    _ensure_dir(target)
    pkg = channel / "package.zip"
    with zipfile.ZipFile(pkg, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("version.txt", "8.0.1-test\n")
        z.writestr("app/version.txt", "8.0.1-test\n")
        z.writestr("app/README.txt", "GBT local update chain test（hash-only）\n")
    sha = _sha_file(pkg)
    manifest = {"schema": 1, "app_id": TEST_APP_ID, "version": "8.0.1-test",
                "channel": "test", "artifact_path": "package.zip", "sha256": sha,
                "size": pkg.stat().st_size,
                "notes": "local hash-only test chain（无密钥；不发布）"}
    (channel / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    if not (target / "version.txt").is_file():
        (target / "version.txt").write_text("8.0.0-local\n", encoding="utf-8")
    return {"ok": True, "root": str(root), "channel": str(channel), "target": str(target),
            "manifest": manifest, "signature": False,
            "note": "无密钥 hash-only；仅本机测试；跨机分发需另换 keypair"}


def _load_manifest(channel: Path) -> dict:
    p = channel / "manifest.json"
    if not p.is_file():
        raise ChainError("没有测试清单，先 init")
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        raise ChainError("清单 JSON 解析失败")
    if not isinstance(m, dict) or int(m.get("schema") or 0) != 1:
        raise ChainError("清单 schema 不对")
    if str(m.get("app_id") or "") != TEST_APP_ID:
        raise ChainError("不是测试 app_id")
    if not str(m.get("version") or "").strip():
        raise ChainError("version 为空")
    if str(m.get("channel") or "") != "test":
        raise ChainError("本地测试链只收 test 通道")
    artifact = _safe_join(channel, m.get("artifact_path") or "")
    if not artifact.is_file():
        raise ChainError("产物不存在")
    if _sha_file(artifact) != str(m.get("sha256") or "").lower():
        raise ChainError("sha256 不匹配（包被改过）")
    return m


def stage(root=TEST_ROOT) -> dict:
    root = _guard_root(root)
    channel = root / "channel"
    m = _load_manifest(channel)
    stage_id = "st-" + secrets.token_hex(6)
    stages = root / "stages"
    _ensure_dir(stages)
    dest = stages / stage_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    artifact = _safe_join(channel, m["artifact_path"])
    total = 0
    with zipfile.ZipFile(artifact) as z:
        if len(z.infolist()) > MAX_FILES:
            raise ChainError("包内文件过多")
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            out = _safe_join(dest, name)
            total += int(info.file_size)
            if total > MAX_UNCOMPRESSED:
                raise ChainError("解包超过上限")
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
    token = secrets.token_urlsafe(24)
    meta = {"stage_id": stage_id, "version": m["version"], "sha256": m["sha256"],
            "artifact": str(artifact), "token": token, "signature": False,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (dest / "stage.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "stage_id": stage_id, "version": m["version"],
            "files": sum(1 for _ in dest.rglob("*") if _.is_file()),
            "confirm_token": token, "target": str(root / "target"),
            "signature": False, "note": "已暂存（hash-only）；confirm 需要 token；只替换 test target"}


def confirm(root=TEST_ROOT, stage_id="", token="") -> dict:
    root = _guard_root(root)
    sid = str(stage_id or "")
    if not sid.startswith("st-") or "/" in sid or ".." in sid:
        raise ChainError("stage_id 非法")
    src = root / "stages" / sid
    meta_p = src / "stage.json"
    if not meta_p.is_file():
        raise ChainError("没有这个 stage")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    if not token or not secrets.compare_digest(str(token), str(meta.get("token") or "")):
        raise ChainError("confirm_token 不匹配")
    target = root / "target"
    backups = root / "backups"
    _ensure_dir(backups)
    backup = backups / sid
    try:
        if target.exists():
            if backup.exists():
                shutil.rmtree(backup)
            shutil.copytree(target, backup)
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for item in src.iterdir():
            if item.name == "stage.json":
                continue
            dst = target / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        result = {"ok": True, "stage_id": sid, "version": meta.get("version"),
                  "applied": True, "backup": str(backup), "target": str(target),
                  "signature": False,
                  "note": "只替换 state/updates-test/target（hash-only）"}
        (root / "applied.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
        return result
    except Exception as e:  # noqa: BLE001
        try:
            if target.exists():
                shutil.rmtree(target)
            if backup.exists():
                shutil.copytree(backup, target)
        except Exception:  # noqa: BLE001
            pass
        raise ChainError("应用失败并已尝试回滚: %s" % type(e).__name__)


def rollback(root=TEST_ROOT) -> dict:
    root = _guard_root(root)
    backups = root / "backups"
    dirs = sorted([p for p in backups.glob("st-*") if p.is_dir()], key=lambda p: p.stat().st_mtime)
    if not dirs:
        raise ChainError("没有可回滚备份")
    backup = dirs[-1]
    target = root / "target"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(backup, target)
    return {"ok": True, "restored": str(backup), "target": str(target),
            "version": (target / "version.txt").read_text(encoding="utf-8").strip()
            if (target / "version.txt").is_file() else ""}


def status(root=TEST_ROOT) -> dict:
    root = _guard_root(root)
    target = root / "target"
    applied = root / "applied.json"
    stages = list((root / "stages").glob("st-*")) if (root / "stages").is_dir() else []
    backups = list((root / "backups").glob("st-*")) if (root / "backups").is_dir() else []
    return {"ok": True, "root": str(root), "init": (root / "channel" / "manifest.json").is_file(),
            "target_exists": target.is_dir(),
            "target_version": (target / "version.txt").read_text(encoding="utf-8").strip()
            if (target / "version.txt").is_file() else "",
            "stages": len(stages), "backups": len(backups),
            "applied": json.loads(applied.read_text(encoding="utf-8")) if applied.is_file() else None,
            "signature": False, "production_update": False,
            "note": "本地 hash-only 测试链；不下载网络/不碰正式 APP"}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    import tempfile
    d = Path(tempfile.mkdtemp(prefix="gbt-chain-"))
    init = init_channel(d)
    ck("init 无密钥", init["ok"] and init["signature"] is False
       and not (d / "channel/dev-key.pem").exists())
    st = stage(d)
    ck("stage", st["ok"] and st["confirm_token"] and st["files"] >= 2 and st["signature"] is False, st)
    ck("confirm token 拒", _raises(lambda: confirm(d, st["stage_id"], "bad")))
    ap = confirm(d, st["stage_id"], st["confirm_token"])
    ck("confirm", ap["ok"] and ap["applied"] and ap["signature"] is False)
    ck("target 更新", (d / "target/version.txt").read_text(encoding="utf-8").strip() == "8.0.1-test")
    rb = rollback(d)
    ck("rollback", rb["ok"] and (d / "target/version.txt").read_text(encoding="utf-8").strip() == "8.0.0-local", rb)
    ck("status 只读", status(d)["production_update"] is False and status(d)["signature"] is False)
    ck("path 越界拒", _raises(lambda: _safe_join(d, "../x")))
    ck("未知 stage 拒", _raises(lambda: confirm(d, "st-nope", "x")))
    ck("rollback 无备份拒", _raises(lambda: rollback(Path(tempfile.mkdtemp(prefix="gbt-chain-empty-")))))
    pkg = d / "channel/package.zip"
    with open(pkg, "ab") as f:
        f.write(b"tamper")
    ck("篡改包 sha 拒", _raises(lambda: stage(d)))
    ck("schema 可达", "test_root" in run("schema") and "signature" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (ChainError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    root = Path(params.get("root") or TEST_ROOT)
    if op == "schema":
        return {"ok": True, "test_root": str(TEST_ROOT), "app_id": TEST_APP_ID,
                "signature": False, "production_update": False, "network": False,
                "note": "只在 state/updates-test/ 内跑；无密钥 hash-only；安装器/生产信任根未接"}
    if op == "init":
        return init_channel(root)
    if op == "stage":
        return stage(root)
    if op == "confirm":
        return confirm(root, params.get("stage_id"), params.get("token"))
    if op == "rollback":
        return rollback(root)
    if op == "status":
        return status(root)
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/init/stage/confirm/rollback/status/verify）" % op)
