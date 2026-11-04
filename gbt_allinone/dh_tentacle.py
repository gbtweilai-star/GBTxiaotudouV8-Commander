# -*- coding: utf-8 -*-
"""数字人 · 触手骨架动作引擎（2026-11-02）

主人令：「每一个动作都要细节做到位」「连接和绑骨都使用我们的触手来操控」。

做法：
  · 骨头 / 轴 / 正负号**全部来自实测骨位表**（holo_pet_w3/digital-human/bone-map.js，
    由 tools/codex-scripts/dh-bone-map.py 反查实测位移生成）；
  · 每个动作写成多骨骼关键帧（预备 → 主动作 → 收尾回正），带肩/脊/头/腿/脚/腕的联动；
  · 服务端按 30fps 采样成帧，前端只负责按帧叠骨 —— 动作由触手层说了算，前端不写死姿势。
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BONE_MAP_JS = ROOT / "holo_pet_w3" / "digital-human" / "bone-map.js"
BINDINGS = ROOT / "state" / "dh-tentacle-bindings.json"
BLENDER = ROOT / "tools" / "3d" / "blender" / "blender.exe"


def _load_map() -> dict:
    try:
        txt = BONE_MAP_JS.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"window\.GBT_BONE_MAP\s*=\s*(\{.*?\})\s*;?\s*$", txt, re.S)
        if not m:
            m = re.search(r"window\.GBT_BONE_MAP\s*=\s*(\{.*?\})\s*;", txt, re.S)
        if m:
            return json.loads(m.group(1))
    except Exception:  # noqa: BLE001
        pass
    return {"bones": []}


BONE_MAP = _load_map()
_BY_NAME = {b.get("name"): b for b in (BONE_MAP.get("bones") or [])}


def drive(bone: str, key: str) -> dict | None:
    b = _BY_NAME.get(bone) or {}
    return (b.get("drive") or {}).get(key)


def kf(*pairs):
    return [list(p) for p in pairs]


# 关键帧单位：弧度；正数 = 骨位表 drive 的 want 方向（符号由实测 sign 决定）
ACTIONS = {
    "ready": {"dur": 1.6, "tracks": {
        "Head.nod": kf((0, 0), (0.5, 0.06), (1.1, 0.0)),
        "Spine1.bend": kf((0, 0), (0.5, 0.03), (1.2, 0)),
    }},
    "wave": {"dur": 3.0, "tracks": {
        "RightArm.abduct": kf((0, 0), (0.45, 1.15), (1.9, 1.15), (2.5, 1.0), (2.9, 0)),
        "RightArm.flex": kf((0, 0), (0.45, 0.18), (1.9, 0.18), (2.9, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 0.55), (1.9, 0.55), (2.6, 0.2), (2.9, 0)),
        "RightHand.wave": kf((0, 0), (0.7, 0.10), (0.95, 0.34), (1.2, -0.22), (1.45, 0.34),
                             (1.7, -0.22), (1.95, 0.28), (2.2, 0.05), (2.6, 0)),
        "Head.turn": kf((0, 0), (0.6, -0.12), (2.0, -0.12), (2.6, 0)),
        "Head.nod": kf((0, 0), (0.5, 0.06), (2.0, 0.06), (2.5, 0)),
        "Head.tilt": kf((0, 0), (0.7, 0.06), (2.0, 0.06), (2.5, 0)),
        "Spine2.side": kf((0, 0), (0.6, 0.05), (2.0, 0.05), (2.5, 0)),
        "LeftArm.abduct": kf((0, 0), (0.7, 0.12), (2.0, 0.12), (2.5, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.8, 0.15), (2.0, 0.15), (2.5, 0)),
        "Hips.twist": kf((0, 0), (0.8, 0.05), (1.9, 0.05), (2.6, 0)),
    }},
    "nod": {"dur": 1.8, "tracks": {
        "Head.nod": kf((0, 0), (0.35, 0.22), (0.55, 0.02), (0.8, 0.20),
                       (1.0, 0.02), (1.3, 0.10), (1.6, 0)),
        "Neck.nod": kf((0, 0), (0.35, 0.10), (0.55, 0.0), (0.8, 0.09), (1.3, 0.05), (1.6, 0)),
        "Spine2.bend": kf((0, 0), (0.4, 0.04), (1.2, 0.02), (1.6, 0)),
    }},
    "shake": {"dur": 2.0, "tracks": {
        "Head.turn": kf((0, 0), (0.3, 0.26), (0.55, -0.26), (0.8, 0.22), (1.05, -0.20),
                        (1.3, 0.12), (1.55, 0)),
        "Neck.turn": kf((0, 0), (0.3, 0.12), (0.55, -0.12), (0.8, 0.10), (1.1, -0.08), (1.5, 0)),
        "Spine2.twist": kf((0, 0), (0.4, 0.05), (0.9, -0.04), (1.4, 0)),
        "Head.tilt": kf((0, 0), (0.4, 0.05), (0.9, -0.04), (1.4, 0)),
    }},
    "bow": {"dur": 3.2, "tracks": {
        "Spine1.bend": kf((0, 0), (0.5, 0.42), (2.0, 0.42), (2.8, 0.05), (3.1, 0)),
        "Spine2.bend": kf((0, 0), (0.55, 0.34), (2.0, 0.34), (2.8, 0.04), (3.1, 0)),
        "Hips.bend": kf((0, 0), (0.55, 0.10), (2.0, 0.10), (2.8, 0.02), (3.1, 0)),
        "Neck.bend": kf((0, 0), (0.6, 0.18), (2.0, 0.18), (2.7, 0.04), (3.1, 0)),
        "Head.nod": kf((0, 0), (0.65, 0.12), (2.0, 0.12), (2.7, 0.02), (3.1, 0)),
        "LeftArm.flex": kf((0, 0), (0.6, 0.18), (2.0, 0.18), (2.7, 0.04), (3.1, 0)),
        "RightArm.flex": kf((0, 0), (0.6, 0.18), (2.0, 0.18), (2.7, 0.04), (3.1, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.6, 0.22), (2.0, 0.22), (2.7, 0.05), (3.1, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 0.22), (2.0, 0.22), (2.7, 0.05), (3.1, 0)),
        "LeftUpLeg.flex": kf((0, 0), (0.6, 0.06), (2.0, 0.06), (2.8, 0)),
        "RightUpLeg.flex": kf((0, 0), (0.6, 0.06), (2.0, 0.06), (2.8, 0)),
        "LeftLeg.flex": kf((0, 0), (0.6, 0.10), (2.0, 0.10), (2.8, 0)),
        "RightLeg.flex": kf((0, 0), (0.6, 0.10), (2.0, 0.10), (2.8, 0)),
    }},
    "hug": {"dur": 3.0, "tracks": {
        "LeftArm.abduct": kf((0, 0), (0.5, 0.55), (2.1, 0.55), (2.7, 0)),
        "RightArm.abduct": kf((0, 0), (0.5, 0.55), (2.1, 0.55), (2.7, 0)),
        "LeftArm.flex": kf((0, 0), (0.5, 0.55), (2.1, 0.55), (2.7, 0)),
        "RightArm.flex": kf((0, 0), (0.5, 0.55), (2.1, 0.55), (2.7, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.6, 1.45), (2.1, 1.45), (2.7, 0.2), (2.9, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 1.45), (2.1, 1.45), (2.7, 0.2), (2.9, 0)),
        "Spine2.bend": kf((0, 0), (0.7, 0.10), (2.1, 0.10), (2.7, 0)),
        "Head.nod": kf((0, 0), (0.7, 0.08), (2.1, 0.08), (2.7, 0)),
        "Head.tilt": kf((0, 0), (0.7, 0.08), (2.1, 0.08), (2.7, 0)),
        "LeftHand.wave": kf((0, 0), (0.7, 0.25), (2.1, 0.25), (2.7, 0)),
        "RightHand.wave": kf((0, 0), (0.7, 0.25), (2.1, 0.25), (2.7, 0)),
    }},
    "heart": {"dur": 3.0, "tracks": {
        "LeftArm.abduct": kf((0, 0), (0.5, 0.50), (2.2, 0.50), (2.8, 0)),
        "RightArm.abduct": kf((0, 0), (0.5, 0.50), (2.2, 0.50), (2.8, 0)),
        "LeftArm.flex": kf((0, 0), (0.5, 0.95), (2.2, 0.95), (2.8, 0)),
        "RightArm.flex": kf((0, 0), (0.5, 0.95), (2.2, 0.95), (2.8, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.6, 1.85), (2.2, 1.85), (2.8, 0.2), (3.0, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 1.85), (2.2, 1.85), (2.8, 0.2), (3.0, 0)),
        "LeftHand.wave": kf((0, 0), (0.7, 0.35), (2.2, 0.35), (2.8, 0)),
        "RightHand.wave": kf((0, 0), (0.7, -0.35), (2.2, -0.35), (2.8, 0)),
        "Head.tilt": kf((0, 0), (0.7, 0.14), (2.2, 0.14), (2.8, 0)),
        "Spine2.side": kf((0, 0), (0.7, 0.05), (2.2, 0.05), (2.8, 0)),
    }},
    "clap": {"dur": 2.8, "tracks": {
        "LeftArm.abduct": kf((0, 0), (0.4, 0.42), (2.1, 0.42), (2.6, 0)),
        "RightArm.abduct": kf((0, 0), (0.4, 0.42), (2.1, 0.42), (2.6, 0)),
        "LeftArm.flex": kf((0, 0), (0.4, 0.95), (2.1, 0.95), (2.6, 0)),
        "RightArm.flex": kf((0, 0), (0.4, 0.95), (2.1, 0.95), (2.6, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.5, 1.15), (0.7, 0.85), (0.9, 1.15), (1.1, 0.85),
                               (1.3, 1.15), (1.5, 0.85), (1.7, 1.15), (2.1, 1.05), (2.6, 0)),
        "RightForeArm.flex": kf((0, 0), (0.5, 1.15), (0.7, 0.85), (0.9, 1.15), (1.1, 0.85),
                                (1.3, 1.15), (1.5, 0.85), (1.7, 1.15), (2.1, 1.05), (2.6, 0)),
        "Spine2.bend": kf((0, 0), (0.5, 0.05), (1.2, 0.08), (1.9, 0.04), (2.4, 0)),
        "Head.nod": kf((0, 0), (0.5, 0.07), (1.2, 0.12), (1.9, 0.05), (2.4, 0)),
        "Hips.twist": kf((0, 0), (0.6, 0.04), (1.4, -0.03), (2.2, 0)),
    }},
    "think": {"dur": 3.4, "tracks": {
        "RightArm.abduct": kf((0, 0), (0.5, 0.35), (2.6, 0.35), (3.1, 0)),
        "RightArm.flex": kf((0, 0), (0.5, 0.75), (2.6, 0.75), (3.1, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 1.95), (2.6, 1.95), (3.1, 0.2), (3.3, 0)),
        "RightHand.wave": kf((0, 0), (0.7, 0.45), (2.6, 0.45), (3.1, 0)),
        "Head.tilt": kf((0, 0), (0.6, 0.16), (2.6, 0.16), (3.1, 0)),
        "Head.turn": kf((0, 0), (0.6, -0.10), (2.6, -0.10), (3.1, 0)),
        "Head.nod": kf((0, 0), (0.6, 0.05), (2.6, 0.05), (3.1, 0)),
        "LeftArm.flex": kf((0, 0), (0.6, 0.45), (2.6, 0.45), (3.1, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.7, 1.30), (2.6, 1.30), (3.1, 0.2), (3.3, 0)),
        "Spine2.bend": kf((0, 0), (0.7, 0.05), (2.6, 0.05), (3.1, 0)),
        "Hips.twist": kf((0, 0), (0.7, 0.05), (2.6, 0.05), (3.1, 0)),
    }},
    "shy": {"dur": 3.0, "tracks": {
        "LeftArm.flex": kf((0, 0), (0.5, 0.55), (2.3, 0.55), (2.8, 0)),
        "RightArm.flex": kf((0, 0), (0.5, 0.55), (2.3, 0.55), (2.8, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.6, 2.05), (2.3, 2.05), (2.8, 0.2), (3.0, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 2.05), (2.3, 2.05), (2.8, 0.2), (3.0, 0)),
        "LeftHand.wave": kf((0, 0), (0.7, 0.35), (2.3, 0.35), (2.8, 0)),
        "RightHand.wave": kf((0, 0), (0.7, -0.35), (2.3, -0.35), (2.8, 0)),
        "Head.bend": kf((0, 0), (0.6, 0.22), (2.3, 0.22), (2.8, 0)),
        "Head.turn": kf((0, 0), (0.6, 0.10), (2.3, 0.10), (2.8, 0)),
        "Head.tilt": kf((0, 0), (0.6, 0.10), (2.3, 0.10), (2.8, 0)),
        "Spine2.twist": kf((0, 0), (0.7, 0.07), (2.3, 0.07), (2.8, 0)),
    }},
    "angry": {"dur": 3.0, "tracks": {
        "LeftArm.abduct": kf((0, 0), (0.4, 0.85), (2.4, 0.85), (2.9, 0)),
        "RightArm.abduct": kf((0, 0), (0.4, 0.85), (2.4, 0.85), (2.9, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.5, 1.55), (2.4, 1.55), (2.9, 0)),
        "RightForeArm.flex": kf((0, 0), (0.5, 1.55), (2.4, 1.55), (2.9, 0)),
        "Head.turn": kf((0, 0), (0.5, 0.20), (0.75, -0.20), (1.0, 0.18),
                        (1.25, -0.16), (1.5, 0.10), (1.8, 0)),
        "Head.nod": kf((0, 0), (0.5, 0.08), (2.4, 0.08), (2.9, 0)),
        "Spine2.bend": kf((0, 0), (0.5, 0.08), (2.4, 0.08), (2.9, 0)),
        "LeftShoulder.shrug": kf((0, 0), (0.5, 0.12), (2.4, 0.12), (2.9, 0)),
        "RightShoulder.shrug": kf((0, 0), (0.5, 0.12), (2.4, 0.12), (2.9, 0)),
        "RightFoot.flex": kf((0, 0), (0.5, 0.18), (0.8, 0), (1.1, 0.18), (1.4, 0),
                             (1.7, 0.14), (2.0, 0)),
    }},
    "surprise": {"dur": 2.4, "tracks": {
        "LeftArm.abduct": kf((0, 0), (0.35, 0.95), (1.9, 0.95), (2.3, 0)),
        "RightArm.abduct": kf((0, 0), (0.35, 0.95), (1.9, 0.95), (2.3, 0)),
        "LeftArm.flex": kf((0, 0), (0.35, 0.45), (1.9, 0.45), (2.3, 0)),
        "RightArm.flex": kf((0, 0), (0.35, 0.45), (1.9, 0.45), (2.3, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.35, 0.35), (1.9, 0.35), (2.3, 0)),
        "RightForeArm.flex": kf((0, 0), (0.35, 0.35), (1.9, 0.35), (2.3, 0)),
        "Spine1.bend": kf((0, 0), (0.35, -0.12), (1.9, -0.12), (2.3, 0)),
        "Head.bend": kf((0, 0), (0.35, -0.15), (1.9, -0.15), (2.3, 0)),
        "Head.tilt": kf((0, 0), (0.35, 0.08), (1.9, 0.08), (2.3, 0)),
        "RightUpLeg.abduct": kf((0, 0), (0.35, 0.08), (1.9, 0.08), (2.3, 0)),
    }},
    "laugh": {"dur": 3.0, "tracks": {
        "Spine2.bend": kf((0, 0), (0.4, 0.06), (0.7, 0.13), (1.0, 0.05), (1.3, 0.12),
                          (1.6, 0.04), (2.0, 0.08), (2.5, 0)),
        "Head.nod": kf((0, 0), (0.4, 0.10), (0.65, 0.02), (0.9, 0.10), (1.15, 0.02),
                       (1.4, 0.08), (1.7, 0.02), (2.2, 0)),
        "LeftArm.flex": kf((0, 0), (0.5, 0.75), (2.2, 0.75), (2.7, 0)),
        "RightArm.flex": kf((0, 0), (0.5, 0.75), (2.2, 0.75), (2.7, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.5, 1.40), (2.2, 1.40), (2.7, 0.2), (2.9, 0)),
        "RightForeArm.flex": kf((0, 0), (0.5, 1.40), (2.2, 1.40), (2.7, 0.2), (2.9, 0)),
        "LeftShoulder.shrug": kf((0, 0), (0.5, 0.10), (0.8, 0.04), (1.1, 0.10), (1.5, 0.04), (2.0, 0)),
        "RightShoulder.shrug": kf((0, 0), (0.5, 0.10), (0.8, 0.04), (1.1, 0.10), (1.5, 0.04), (2.0, 0)),
        "Hips.twist": kf((0, 0), (0.6, 0.05), (1.4, -0.04), (2.2, 0)),
    }},
    "stretch": {"dur": 3.8, "tracks": {
        "LeftArm.abduct": kf((0, 0), (0.6, 2.25), (2.6, 2.25), (3.4, 0)),
        "RightArm.abduct": kf((0, 0), (0.6, 2.25), (2.6, 2.25), (3.4, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.6, 0.20), (2.6, 0.20), (3.4, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 0.20), (2.6, 0.20), (3.4, 0)),
        "Spine1.bend": kf((0, 0), (0.6, -0.14), (2.6, -0.14), (3.4, 0)),
        "Spine2.bend": kf((0, 0), (0.6, -0.10), (2.6, -0.10), (3.4, 0)),
        "Head.bend": kf((0, 0), (0.6, -0.12), (2.6, -0.12), (3.4, 0)),
        "LeftFoot.point": kf((0, 0), (0.6, 0.22), (2.6, 0.22), (3.4, 0)),
        "RightFoot.point": kf((0, 0), (0.6, 0.22), (2.6, 0.22), (3.4, 0)),
    }},
    "point": {"dur": 2.4, "tracks": {
        "RightArm.flex": kf((0, 0), (0.4, 1.25), (1.9, 1.25), (2.3, 0)),
        "RightArm.abduct": kf((0, 0), (0.4, 0.18), (1.9, 0.18), (2.3, 0)),
        "RightForeArm.flex": kf((0, 0), (0.4, 0.08), (1.9, 0.08), (2.3, 0)),
        "RightHand.wave": kf((0, 0), (0.5, 0.10), (1.9, 0.10), (2.3, 0)),
        "Head.turn": kf((0, 0), (0.5, 0.16), (1.9, 0.16), (2.3, 0)),
        "Spine2.twist": kf((0, 0), (0.5, 0.06), (1.9, 0.06), (2.3, 0)),
        "LeftArm.flex": kf((0, 0), (0.5, 0.10), (1.9, 0.10), (2.3, 0)),
    }},
    "salute": {"dur": 2.6, "tracks": {
        "RightArm.abduct": kf((0, 0), (0.35, 0.75), (2.0, 0.75), (2.5, 0)),
        "RightArm.flex": kf((0, 0), (0.35, 0.45), (2.0, 0.45), (2.5, 0)),
        "RightForeArm.flex": kf((0, 0), (0.4, 2.05), (2.0, 2.05), (2.5, 0.2), (2.6, 0)),
        "RightHand.wave": kf((0, 0), (0.5, 0.35), (2.0, 0.35), (2.5, 0)),
        "Head.nod": kf((0, 0), (0.4, 0.10), (0.8, 0.02), (1.5, 0.06), (2.2, 0)),
        "Spine1.bend": kf((0, 0), (0.4, -0.03), (2.0, -0.03), (2.5, 0)),
    }},
    "shrug": {"dur": 2.0, "tracks": {
        "LeftShoulder.shrug": kf((0, 0), (0.4, 0.18), (1.6, 0.18), (1.9, 0)),
        "RightShoulder.shrug": kf((0, 0), (0.4, 0.18), (1.6, 0.18), (1.9, 0)),
        "LeftArm.abduct": kf((0, 0), (0.4, 0.32), (1.6, 0.32), (1.9, 0)),
        "RightArm.abduct": kf((0, 0), (0.4, 0.32), (1.6, 0.32), (1.9, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.4, 0.55), (1.6, 0.55), (1.9, 0)),
        "RightForeArm.flex": kf((0, 0), (0.4, 0.55), (1.6, 0.55), (1.9, 0)),
        "LeftHand.wave": kf((0, 0), (0.5, 0.35), (1.6, 0.35), (1.9, 0)),
        "RightHand.wave": kf((0, 0), (0.5, -0.35), (1.6, -0.35), (1.9, 0)),
        "Head.tilt": kf((0, 0), (0.5, 0.12), (1.6, 0.12), (1.9, 0)),
    }},
    "turn": {"dur": 3.6, "root": {
        "yaw": kf((0, 0), (0.7, math.pi), (2.6, math.pi), (3.4, 0)),
    }, "tracks": {
        "Hips.twist": kf((0, 0), (0.7, 0.25), (2.6, 0.25), (3.4, 0)),
        "Spine2.twist": kf((0, 0), (0.7, -0.10), (2.6, -0.10), (3.4, 0)),
        "Head.turn": kf((0, 0), (0.5, 0.35), (2.6, 0.35), (3.4, 0)),
        "LeftFoot.point": kf((0, 0), (0.5, 0.15), (0.9, 0), (2.2, 0.15), (2.8, 0)),
        "RightFoot.point": kf((0, 0), (0.9, 0), (1.2, 0.15), (2.4, 0)),
    }},
    "squat": {"dur": 3.4, "root": {
        "y": kf((0, 0), (0.8, -0.42), (2.4, -0.42), (3.2, 0)),
    }, "tracks": {
        "LeftUpLeg.flex": kf((0, 0), (0.8, 0.95), (2.4, 0.95), (3.2, 0)),
        "RightUpLeg.flex": kf((0, 0), (0.8, 0.95), (2.4, 0.95), (3.2, 0)),
        "LeftLeg.flex": kf((0, 0), (0.8, 1.55), (2.4, 1.55), (3.2, 0)),
        "RightLeg.flex": kf((0, 0), (0.8, 1.55), (2.4, 1.55), (3.2, 0)),
        "LeftFoot.flex": kf((0, 0), (0.8, 0.55), (2.4, 0.55), (3.2, 0)),
        "RightFoot.flex": kf((0, 0), (0.8, 0.55), (2.4, 0.55), (3.2, 0)),
        "Spine1.bend": kf((0, 0), (0.8, 0.22), (2.4, 0.22), (3.2, 0)),
        "Spine2.bend": kf((0, 0), (0.8, 0.16), (2.4, 0.16), (3.2, 0)),
        "Head.bend": kf((0, 0), (0.8, 0.10), (2.4, 0.10), (3.2, 0)),
        "LeftArm.flex": kf((0, 0), (0.8, 0.55), (2.4, 0.55), (3.2, 0)),
        "RightArm.flex": kf((0, 0), (0.8, 0.55), (2.4, 0.55), (3.2, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.8, 0.45), (2.4, 0.45), (3.2, 0)),
        "RightForeArm.flex": kf((0, 0), (0.8, 0.45), (2.4, 0.45), (3.2, 0)),
    }},
    "dance": {"dur": 6.0, "tracks": {
        "Hips.twist": kf((0, 0), (0.6, 0.18), (1.2, -0.18), (1.8, 0.18), (2.4, -0.18),
                         (3.0, 0.18), (3.6, -0.18), (4.2, 0.18), (4.8, -0.18), (5.4, 0)),
        "Spine2.side": kf((0, 0), (0.6, 0.10), (1.2, -0.10), (1.8, 0.10), (2.4, -0.10),
                          (3.0, 0.10), (3.6, -0.10), (4.2, 0.10), (4.8, -0.10), (5.4, 0)),
        "Head.tilt": kf((0, 0), (0.6, 0.10), (1.2, -0.10), (1.8, 0.10), (2.4, -0.10),
                        (3.0, 0.10), (3.6, -0.10), (4.2, 0.10), (4.8, -0.10), (5.4, 0)),
        "LeftArm.abduct": kf((0, 0), (0.6, 1.0), (1.5, 0.35), (2.4, 1.0), (3.3, 0.35),
                             (4.2, 1.0), (5.0, 0.35), (5.6, 0)),
        "RightArm.abduct": kf((0, 0), (0.6, 0.35), (1.5, 1.0), (2.4, 0.35), (3.3, 1.0),
                              (4.2, 0.35), (5.0, 1.0), (5.6, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.6, 1.2), (1.5, 0.6), (2.4, 1.2), (3.3, 0.6),
                               (4.2, 1.2), (5.0, 0.6), (5.6, 0)),
        "RightForeArm.flex": kf((0, 0), (0.6, 0.6), (1.5, 1.2), (2.4, 0.6), (3.3, 1.2),
                                (4.2, 0.6), (5.0, 1.2), (5.6, 0)),
        "LeftHand.wave": kf((0, 0), (0.6, 0.3), (1.2, -0.2), (1.8, 0.3), (2.4, -0.2),
                            (3.0, 0.3), (3.6, -0.2), (4.2, 0.3), (4.8, -0.2), (5.4, 0)),
        "RightHand.wave": kf((0, 0), (0.6, -0.2), (1.2, 0.3), (1.8, -0.2), (2.4, 0.3),
                             (3.0, -0.2), (3.6, 0.3), (4.2, -0.2), (4.8, 0.3), (5.4, 0)),
        "LeftUpLeg.flex": kf((0, 0), (0.6, 0.18), (1.2, 0), (1.8, 0.18), (2.4, 0),
                             (3.0, 0.18), (3.6, 0), (4.2, 0.18), (4.8, 0), (5.4, 0)),
        "RightUpLeg.flex": kf((0, 0), (0.6, 0), (1.2, 0.18), (1.8, 0), (2.4, 0.18),
                              (3.0, 0), (3.6, 0.18), (4.2, 0), (4.8, 0.18), (5.4, 0)),
    }},
    "talk": {"dur": 4.0, "tracks": {
        "Head.nod": kf((0, 0), (0.4, 0.06), (0.8, 0.01), (1.2, 0.05), (1.6, 0.01),
                       (2.0, 0.05), (2.4, 0.01), (2.8, 0.04), (3.4, 0)),
        "Head.tilt": kf((0, 0), (0.6, 0.05), (1.6, -0.04), (2.6, 0.05), (3.4, 0)),
        "RightArm.flex": kf((0, 0), (0.5, 0.45), (2.6, 0.45), (3.4, 0)),
        "RightForeArm.flex": kf((0, 0), (0.5, 1.20), (0.9, 0.95), (1.4, 1.25),
                                (1.9, 0.95), (2.4, 1.15), (3.0, 0.9), (3.4, 0)),
        "LeftArm.flex": kf((0, 0), (0.5, 0.12), (2.6, 0.12), (3.4, 0)),
        "LeftForeArm.flex": kf((0, 0), (0.5, 0.35), (2.6, 0.35), (3.4, 0)),
        "Spine2.bend": kf((0, 0), (0.6, 0.03), (2.0, 0.05), (3.0, 0.02), (3.6, 0)),
        "Spine2.twist": kf((0, 0), (0.8, 0.03), (2.2, -0.03), (3.2, 0)),
    }},
    "walk": {"dur": 2.6, "clip": True},
    "grip": {"dur": 2.6, "hand": "fist", "tracks": {
        "RightArm.flex": kf((0, 0), (0.4, 0.85), (2.0, 0.85), (2.5, 0)),
        "RightArm.abduct": kf((0, 0), (0.4, 0.20), (2.0, 0.20), (2.5, 0)),
        "RightForeArm.flex": kf((0, 0), (0.4, 0.65), (2.0, 0.65), (2.5, 0)),
        "Head.nod": kf((0, 0), (0.4, 0.08), (2.0, 0.06), (2.5, 0)),
        "Spine2.bend": kf((0, 0), (0.4, 0.04), (2.0, 0.04), (2.5, 0)),
    }},
    "pinch": {"dur": 2.4, "hand": "pinch", "tracks": {
        "RightArm.flex": kf((0, 0), (0.35, 0.80), (1.9, 0.80), (2.3, 0)),
        "RightArm.abduct": kf((0, 0), (0.35, 0.18), (1.9, 0.18), (2.3, 0)),
        "RightForeArm.flex": kf((0, 0), (0.35, 1.10), (1.9, 1.10), (2.3, 0)),
        "Head.tilt": kf((0, 0), (0.4, 0.06), (1.9, 0.06), (2.3, 0)),
    }},
    "ok_sign": {"dur": 2.6, "hand": "ok", "tracks": {
        "RightArm.flex": kf((0, 0), (0.4, 0.95), (2.0, 0.95), (2.5, 0)),
        "RightArm.abduct": kf((0, 0), (0.4, 0.45), (2.0, 0.45), (2.5, 0)),
        "RightForeArm.flex": kf((0, 0), (0.4, 1.30), (2.0, 1.30), (2.5, 0)),
        "Head.nod": kf((0, 0), (0.4, 0.08), (0.8, 0.02), (1.6, 0.05), (2.4, 0)),
    }},
    "thumbs_up": {"dur": 2.4, "hand": "thumbs_up", "tracks": {
        "RightArm.flex": kf((0, 0), (0.35, 1.15), (1.9, 1.15), (2.3, 0)),
        "RightArm.abduct": kf((0, 0), (0.35, 0.30), (1.9, 0.30), (2.3, 0)),
        "RightForeArm.flex": kf((0, 0), (0.35, 0.95), (1.9, 0.95), (2.3, 0)),
        "Head.nod": kf((0, 0), (0.4, 0.10), (1.9, 0.08), (2.3, 0)),
        "Spine2.bend": kf((0, 0), (0.4, 0.03), (1.9, 0.03), (2.3, 0)),
    }},
    "open_palm": {"dur": 2.6, "hand": "open", "tracks": {
        "RightArm.abduct": kf((0, 0), (0.4, 1.05), (2.0, 1.05), (2.5, 0)),
        "RightArm.flex": kf((0, 0), (0.4, 0.30), (2.0, 0.30), (2.5, 0)),
        "RightForeArm.flex": kf((0, 0), (0.4, 0.25), (2.0, 0.25), (2.5, 0)),
        "Head.turn": kf((0, 0), (0.5, -0.08), (2.0, -0.08), (2.5, 0)),
    }},
}



# ── 灵巧手（吞入件 hand_retarget / hand_bridge 的接线，2026-11-02） ──────────
HAND_DOF = ["thumb_mcp", "thumb_pip", "thumb_dip",
            "index_mcp", "index_pip", "index_dip",
            "middle_mcp", "middle_pip", "middle_dip",
            "ring_mcp", "ring_pip", "ring_dip",
            "pinky_mcp", "pinky_pip", "pinky_dip"]

HAND_POSES = {
    "relaxed": [0.12, 0.14, 0.10, 0.10, 0.12, 0.08, 0.10, 0.12, 0.08,
                0.10, 0.12, 0.08, 0.10, 0.12, 0.08],
    "open": [0.0] * 15,
    "fist": [1.00, 1.20, 0.95, 1.30, 1.50, 1.20, 1.30, 1.50, 1.20,
             1.30, 1.50, 1.20, 1.30, 1.50, 1.20],
    "pinch": [0.75, 1.00, 0.80, 0.85, 1.05, 0.85, 0.08, 0.10, 0.06,
              0.08, 0.10, 0.06, 0.08, 0.10, 0.06],
    "point": [0.25, 0.45, 0.30, 0.02, 0.02, 0.02, 1.25, 1.45, 1.15,
              1.25, 1.45, 1.15, 1.25, 1.45, 1.15],
    "thumbs_up": [0.00, 0.05, 0.02, 1.30, 1.50, 1.20, 1.30, 1.50, 1.20,
                  1.30, 1.50, 1.20, 1.30, 1.50, 1.20],
    "ok": [0.70, 1.05, 0.90, 0.75, 1.00, 0.85, 0.05, 0.05, 0.04,
           0.05, 0.05, 0.04, 0.05, 0.05, 0.04],
}

FINGER_BONES = {
    "thumb": ["LeftHandThumb1", "LeftHandThumb2", "LeftHandThumb3", "LeftHandThumb4"],
    "index": ["LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3", "LeftHandIndex4"],
    "middle": ["LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3", "LeftHandMiddle4"],
    "ring": ["LeftHandRing1", "LeftHandRing2", "LeftHandRing3", "LeftHandRing4"],
    "pinky": ["LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3", "LeftHandPinky4"],
}
_FINGER_IX = [("thumb", 0), ("index", 3), ("middle", 6), ("ring", 9), ("pinky", 12)]


def hand_pose(name: str = "relaxed") -> dict:
    """用吞入件 hand_retarget 做限位/单位换算，返回 15-DOF 目标角。"""
    raw = HAND_POSES.get(str(name or "relaxed"), HAND_POSES["relaxed"])
    joints = {k: float(v) for k, v in zip(HAND_DOF, raw)}
    try:
        from .tentacle import hand_retarget as HR
        r = HR.run("retarget", joints=joints, model="generic_15dof", unit="rad")
        if r.get("ok"):
            got = r.get("joints") or {}
            if got:
                joints = {k: float(got.get(k, joints[k])) for k in HAND_DOF}
    except Exception:  # noqa: BLE001
        pass
    return joints


def hand_tracks(pose: str, side: str = "both") -> list:
    """15-DOF 手姿 → Mixamo 手指骨轨道（每指 3 段 + 末端跟第 3 段）。"""
    j = hand_pose(pose)
    out = []
    sides = ["Left", "Right"] if side == "both" else [side]
    for sd in sides:
        for finger, ix in _FINGER_IX:
            names = [n.replace("Left", sd) for n in FINGER_BONES[finger]]
            vals = [j[HAND_DOF[ix]], j[HAND_DOF[ix + 1]], j[HAND_DOF[ix + 2]]]
            for k, nm in enumerate(names):
                v = vals[min(k, 2)] * (0.55 if k == 3 else 1.0)
                out.append({"bone": nm, "axis": "z",
                            "sign": -1.0 if sd == "Left" else 1.0,
                            "frames": [round(v, 4)]})
    return out


def _ease(p: float) -> float:
    return p * p * (3 - 2 * p)


def _sample(track, dur, fps):
    n = max(2, int(round(dur * fps)) + 1)
    out = []
    for i in range(n):
        t = i / (n - 1) * dur
        a = track[0][1]
        b = track[0][1]
        for j in range(len(track) - 1):
            t0, v0 = track[j]
            t1, v1 = track[j + 1]
            if t0 <= t <= t1:
                u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                a = v0
                b = v1
                k = _ease(u)
                out.append(a + (b - a) * k)
                break
        else:
            out.append(track[-1][1])
    return out


def plan(gesture: str) -> dict:
    g = str(gesture or "").strip().lower()
    spec = ACTIONS.get(g)
    if not spec:
        return {"ok": False, "error": "unknown gesture: %s" % g,
                "available": sorted(ACTIONS.keys())}
    fps = 30
    dur = float(spec.get("dur") or 2.0)
    tracks = []
    missing = []
    if spec.get("clip"):
        return {"ok": True, "gesture": g, "type": "clip", "dur": dur, "fps": fps,
                "note": "walk 用资产自带 clip 播放；触手层只发命令"}
    for key, kfs in (spec.get("tracks") or {}).items():
        bone, _, dk = key.partition(".")
        info = drive(bone, dk)
        if not info:
            missing.append(key)
            continue
        tracks.append({
            "bone": bone, "axis": info.get("axis"),
            "sign": float(info.get("sign") or 1),
            "frames": [round(v, 5) for v in _sample(kfs, dur, fps)],
        })
    finger_tracks = []
    if spec.get("hand"):
        pose = spec.get("hand")
        side = spec.get("hand_side") or "both"
        finger_tracks = hand_tracks(pose, side)
    root_tracks = []
    for rk, kfs in (spec.get("root") or {}).items():
        root_tracks.append({"kind": rk, "frames": [round(v, 5) for v in _sample(kfs, dur, fps)]})
    return {"ok": True, "gesture": g, "dur": dur, "fps": fps,
            "frames": max([len(t["frames"]) for t in tracks] or [0]),
            "tracks": tracks + finger_tracks, "root": root_tracks,
            "hand": spec.get("hand") or "",
            "unmapped": missing,
            "source": "bone-map/want-axis（触手骨位表）"}


def bindings() -> dict:
    try:
        return json.loads(BINDINGS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"actions": {g: {"tracks": list((ACTIONS[g].get("tracks") or {}).keys())}
                            for g in ACTIONS}, "updated_at": None}


def status() -> dict:
    tools = {}
    blender = BLENDER if BLENDER.is_file() else None
    tools["blender"] = {"found": bool(blender), "path": str(blender or ""),
                        "install_hint": "tools/3d/blender/blender.exe（便携版）"}
    return {"ok": True, "bones": len(BONE_MAP.get("bones") or []),
            "map_at": BONE_MAP.get("at"), "actions": sorted(ACTIONS.keys()),
            "bindings": bindings().get("actions", {}), "tools": tools,
            "rig_source": str(BONE_MAP_JS)}
