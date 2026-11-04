# -*- coding: utf-8 -*-
# gbt-capability: ref3d  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""技能「参考图 → 可拆解 3D 交互页」—— 现在用**我们自己的数字人 DH-V7**。

主人 2026-11-03：不要 Salticus 蜘蛛，换成我们自己的数字人。
页面 `/teardown/` 加载我们自己的 GLB（voice-theater / dh-v7-detail.glb），
可旋转/缩放/皮肤透明/骨架/线框/拆解层/动作；参考图只提供配色/比例，不改资产结构。
本模块是能力位：schema/status/build/verify；build 复制独立页并写 meta（过 filesystem_write 门）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGE = ROOT / "holo_pet_w3" / "teardown" / "index.html"
THREE = ROOT / "holo_pet_w3" / "assets" / "vendor" / "three.global.js"
LOADER = ROOT / "holo_pet_w3" / "assets" / "vendor" / "GLTFLoader.global.js"
MODEL = ROOT / "holo_pet_w3" / "assets" / "dh" / "dh-v7-detail.glb"
SKILL = ROOT / "skills" / "ref-to-3d" / "SKILL.md"
OUT = ROOT / "state" / "ref3d"
MESHES = 1
BONES = 66


def spec() -> dict:
    return {"ok": True, "skill": "ref-to-3d", "name": "Digital Human DH-V7",
            "mode": "own_digital_human", "mesh": MESHES, "bones": BONES,
            "model": str(MODEL.relative_to(ROOT)), "page": str(PAGE.relative_to(ROOT)),
            "outputs": str(OUT.relative_to(ROOT)), "local": True, "network": False,
            "note": "我们自己的数字人；参考图只给外观；可拆解/可透视；不是照片级重建"}


def status() -> dict:
    return {"ok": PAGE.is_file() and MODEL.is_file(),
            "skill": SKILL.is_file(), "page": PAGE.is_file(),
            "three": THREE.is_file(), "loader": LOADER.is_file(),
            "model": MODEL.is_file(), "model_mb": round(MODEL.stat().st_size / 1e6, 1) if MODEL.is_file() else None,
            "mesh": MESHES, "bones": BONES, "api": "/api/ref3d"}


def _gate(detail: str):
    try:
        from .. import auth_gate
        got = auth_gate.check_and_consume("filesystem_write", detail=str(detail)[:60])
        if got.get("ok"):
            return None
        return {"ok": False, "denied": True, "gate": "filesystem_write",
                "error": got.get("error"),
                "how_to_grant": got.get("how_to_grant"),
                "note": "ref3d build 写页面副本必须过 filesystem_write 门"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "gate": "filesystem_write",
                "error": "gate 不可用，fail-closed: %s" % type(e).__name__}


def build(out_dir=None, image=None) -> dict:
    denied = _gate("ref3d build")
    if denied:
        return denied
    dest = pathlib.Path(out_dir) if out_dir else OUT / time.strftime("dh-v7-%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    page = dest / "index.html"
    shutil.copy2(PAGE, page)
    meta = {"ok": True, "skill": "ref-to-3d", "model": str(MODEL),
            "mesh": MESHES, "bones": BONES, "image": str(image or ""),
            "page": str(page), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "note": "我们自己的数字人页面副本；参考图仅外观；build 不生成新资产"}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    ck("页面存在", PAGE.is_file())
    ck("Three.js 本地", THREE.is_file() and THREE.stat().st_size > 1000000,
       THREE.stat().st_size if THREE.is_file() else None)
    ck("GLTFLoader 本地", LOADER.is_file() and LOADER.stat().st_size > 50000)
    ck("数字人 GLB", MODEL.is_file() and MODEL.stat().st_size > 1000000,
       round(MODEL.stat().st_size / 1e6, 1) if MODEL.is_file() else None)
    page = PAGE.read_text(encoding="utf-8") if PAGE.is_file() else ""
    ck("__dh3d API", "__dh3d" in page and "buildFromImage" in page)
    ck("加载我们自己的 GLB", "dh-v7-detail.glb" in page)
    ck("拆解/骨架/透明", all(x in page for x in ("skeleton", "applyOpacity", "wire")))
    ck("同源状态", "state.opacity" in page and "state.explode" in page and "state.mode" in page)
    ck("技能已安装", SKILL.is_file() and "DH-V7" in SKILL.read_text(encoding="utf-8"))
    try:
        from ..tentacle import skills_hub
        sk = skills_hub.run("get", name="ref-to-3d")
        ck("skills_hub 可读", sk.get("ok") is True, sk.get("error"))
    except Exception as e:  # noqa: BLE001
        ck("skills_hub 可读", False, type(e).__name__)
    try:
        from ..caps_registry import BENIGN_CAPS
        ck("能力位已注册", "ref3d" in BENIGN_CAPS)
    except Exception:
        ck("能力位已注册", False)
    ck("骨架/网格读数", "bones" in page and "meshes" in page)
    return {"ok": all(x["ok"] for x in checks), "checks": len(checks),
            "failed": [x for x in checks if not x["ok"]],
            "mesh": MESHES, "bones": BONES,
            "sha": hashlib.sha256(page.encode()).hexdigest()[:12]}


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op in ("schema", "spec"):
        return spec()
    if op == "status":
        return status()
    if op == "build":
        return build(params.get("out_dir"), params.get("image"))
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/status/build/verify）" % op)
