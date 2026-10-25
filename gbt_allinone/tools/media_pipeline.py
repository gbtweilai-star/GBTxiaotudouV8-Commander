"""AI 短视频 / 电影 / 音乐流水线。

这是编排和审查层，不是假装拥有某个外部生成服务。所有产物先进入独立
room dimension，经过自审和排练；不可逆的外部发布永远返回人工授权要求。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

KINDS = {
    "short_video": ("短视频", ("script", "storyboard", "assets", "edit", "export")),
    "film": ("AI电影", ("concept", "script", "shots", "sound", "edit", "export")),
    "music": ("AI音乐", ("lyrics", "arrangement", "audio", "master", "export")),
}

MEDIA_KNOWLEDGE = {
    "short_video": {
        "objective": "在最短时间内建立注意力、交付单一明确价值并引导可归因行动",
        "roles": ["商业机会研究员", "短视频策划", "分镜导演", "AI视觉制片", "配音与混音", "短片剪辑", "独立质审", "发布归因"],
        "craft": ["首 3 秒建立冲突或收益承诺", "每个镜头只承载一个信息", "画面、旁白、字幕语义一致", "节奏服务信息而不是堆转场"],
        "quality": ["首屏可读", "无黑帧或静音段", "字幕不遮挡主体", "音量与峰值稳定", "素材授权可追溯"],
        "metrics": ["前 3 秒留存", "完播率", "有效播放成本", "转化率", "净收益"],
    },
    "film": {
        "objective": "用连续角色、空间、声音与因果构建可持续观看的长叙事",
        "roles": ["制片人", "总编剧", "视觉开发导演", "分镜导演", "角色一致性监督", "AI摄影", "声音导演", "长片剪辑", "连续性审计", "发行归因"],
        "craft": ["先锁定主题、欲望、阻力与变化", "角色形象、声音、服饰和场景建立连续性护照", "每场戏必须改变信息或关系", "镜头语法、节奏和声音共同推进情绪"],
        "quality": ["角色与场景连续", "台词与口型可接受", "镜头无闪烁崩坏", "声画同步", "章节转折清晰", "版权与人物授权完整"],
        "metrics": ["章节留存", "平均观看时长", "单分钟成本", "二次观看率", "项目净收益"],
    },
    "music": {
        "objective": "创作具有明确情绪、记忆点、结构和可商业交付版权链的音乐",
        "roles": ["音乐策划", "作词", "作曲", "编曲", "人声导演", "声音设计", "混音工程师", "母带工程师", "版权审计", "发行归因"],
        "craft": ["先定义情绪曲线、速度、调性和参考边界", "主旋律和节奏动机必须可识别", "配器为人声和核心动机留出空间", "混音与母带按目标平台交付"],
        "quality": ["无爆音、削波与异常噪声", "响度和真峰值合格", "人声可懂度达标", "段落动态有对比", "样本、声纹与旋律来源可追溯"],
        "metrics": ["完整收听率", "收藏率", "授权转化", "单曲制作成本", "版权净收益"],
    },
}

COMMON_GATES = [
    "需求与受众证据", "成本上限", "脚本事实核验", "角色与品牌一致性",
    "素材授权清单", "技术读数", "独立 checker", "镜像排练", "主人发布授权", "发布后收益归因",
]


def _audit(event, meta):
    try:
        from ..store import audit
        audit(event, meta)
    except Exception:
        pass


def _sha(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def plan(kind: str, title: str, brief: str = "") -> dict:
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown media kind: {kind}"}
    label, stages = KINDS[kind]
    return {
        "ok": True, "schema": "gbt-media-pipeline/v1", "kind": kind,
        "label": label, "title": str(title or "").strip(),
        "brief": str(brief or "").strip(), "stages": list(stages),
        "gates": ["asset_integrity", "copyright", "safety", "brand", "quality",
                  "owner_review", "publish_auth"],
        "publish_policy": "draft_or_blocked_until_owner_authorization",
    }


def knowledge(kind: str = "") -> dict:
    if kind:
        if kind not in MEDIA_KNOWLEDGE:
            return {"ok": False, "error": f"unknown media kind: {kind}"}
        return {"ok": True, "kind": kind, "knowledge": MEDIA_KNOWLEDGE[kind],
                "common_gates": list(COMMON_GATES), "external_generators_connected": False}
    return {"ok": True, "kinds": {key: dict(value) for key, value in MEDIA_KNOWLEDGE.items()},
            "common_gates": list(COMMON_GATES), "external_generators_connected": False}


def collaborate(kind: str, objective: str, *, cycle_id: str = "") -> dict:
    if kind not in KINDS:
        return {"ok": False, "error": f"unknown media kind: {kind}"}
    objective = str(objective or "").strip()
    if not objective:
        return {"ok": False, "error": "objective is required"}
    spec = MEDIA_KNOWLEDGE[kind]
    _, stages = KINDS[kind]
    roles = spec["roles"]
    packets = []
    for index, stage in enumerate(stages):
        packets.append({
            "step_id": f"{kind}-{index + 1:02d}-{stage}",
            "stage": stage,
            "role": roles[min(index, len(roles) - 1)],
            "room_id": f"media-{cycle_id or 'draft'}-{kind}-{index + 1:02d}",
            "objective": objective,
            "inputs": ["previous_stage_manifest", "brand_contract", "rights_ledger", "budget"],
            "required_outputs": ["artifact_ref", "sha256", "readings", "self_check", "evidence"],
            "on_failure": "checkpoint_then_bounded_retry_then_owner_escalation",
        })
    packets.append({
        "step_id": f"{kind}-{len(stages) + 1:02d}-independent-review",
        "stage": "independent_review", "role": "独立质量审计官",
        "room_id": f"media-{cycle_id or 'draft'}-{kind}-review", "objective": objective,
        "inputs": ["complete_manifest", "rights_ledger", "technical_readings"],
        "required_outputs": ["checker_id", "findings", "decision", "evidence"],
        "on_failure": "return_to_named_stage_without_direct_edit",
    })
    packets.append({
        "step_id": f"{kind}-{len(stages) + 2:02d}-owner-release",
        "stage": "owner_release", "role": "主人决策席",
        "room_id": f"media-{cycle_id or 'draft'}-{kind}-release", "objective": objective,
        "inputs": ["approved_manifest", "rollback_ref", "independent_review"],
        "required_outputs": ["deploy_publish_grant_or_rejection"],
        "on_failure": "remain_blocked",
    })
    return {"ok": True, "schema": "gbt-media-collaboration/v1", "kind": kind,
            "objective": objective, "cycle_id": cycle_id, "packets": packets,
            "knowledge": spec, "gates": list(COMMON_GATES),
            "flow": "plan -> isolated production -> self review -> independent review -> owner release -> attribution -> next cycle"}


def launch_cycle(kind: str, objective: str, task_id: str, *, cycle_id: str = "") -> dict:
    collaboration = collaborate(kind, objective, cycle_id=cycle_id or task_id)
    if not collaboration.get("ok"):
        return collaboration
    from . import long_run_supervisor
    created = long_run_supervisor.create(
        task_id, objective,
        [{"title": f"{packet['role']} / {packet['stage']}"} for packet in collaboration["packets"]],
        room_id=f"media-cycle-{cycle_id or task_id}",
    )
    return {"ok": bool(created.get("ok")), "collaboration": collaboration,
            "supervision": created, "execution": "waiting_for_worker_claim"}


def self_review(manifest: dict, room_id: str = "") -> dict:
    """对镜像房间产物做结构审查，不把缺失的生成服务伪装成成功。"""
    manifest = dict(manifest or {})
    kind = manifest.get("kind", "")
    expected = KINDS.get(kind, ("", ()))[1]
    assets = manifest.get("assets") or {}
    checks = {
        "kind_known": kind in KINDS,
        "title_present": bool(str(manifest.get("title") or "").strip()),
        "brief_present": bool(str(manifest.get("brief") or "").strip()),
        "stages_declared": bool(expected),
        "stage_outputs_bound": all(stage in assets for stage in expected),
        "asset_hashes_present": bool(assets) and all(
            isinstance(value, dict) and value.get("sha256") for value in assets.values()
        ),
        "copyright_attested": bool(manifest.get("copyright_attested")),
        "safety_reviewed": bool(manifest.get("safety_reviewed")),
        "owner_reviewed": bool(manifest.get("owner_reviewed")),
    }
    passed = sum(checks.values())
    result = {
        "ok": passed == len(checks),
        "room_id": room_id,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "blocked_reasons": [name for name, ok in checks.items() if not ok],
        "publish": "blocked_until_owner_authorization",
    }
    _audit("media_self_review", {
        "kind": kind, "room_id": room_id, "passed": passed, "total": len(checks)
    })
    return result


def compose(kind: str, title: str, brief: str, room_id: str,
            assets: dict | None = None, *, copyright_attested=False,
            safety_reviewed=False, owner_reviewed=False) -> dict:
    """把编排清单写入房间；真正生成器作为外部能力按 stage 接入。"""
    from .. import room_space
    manifest = plan(kind, title, brief)
    if not manifest["ok"]:
        return manifest
    normalized_assets = {}
    for stage, value in (assets or {}).items():
        if isinstance(value, dict):
            normalized_assets[stage] = dict(value)
            normalized_assets[stage].setdefault("sha256", _sha(json.dumps(value, sort_keys=True)))
        else:
            normalized_assets[stage] = {"ref": str(value), "sha256": _sha(value)}
    manifest.update({
        "room_id": room_id, "assets": normalized_assets,
        "copyright_attested": bool(copyright_attested),
        "safety_reviewed": bool(safety_reviewed),
        "owner_reviewed": bool(owner_reviewed),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    room_space.create(room_id, purpose=f"{manifest['label']}自动化排练")
    room_space.shape(
        room_id, "media/manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
        note="media pipeline manifest",
    )
    review = self_review(manifest, room_id)
    room_space.shape(
        room_id, "media/self_review.json",
        json.dumps(review, ensure_ascii=False, indent=2),
        note="media self review",
    )
    return {"ok": True, "manifest": manifest, "self_review": review}


def publish(room_id: str, *, authorization: str = "") -> dict:
    """发布门：没有主人授权只返回草稿/阻断状态，不连接外部平台。"""
    if not authorization:
        return {
            "ok": False, "blocked": True, "room_id": room_id,
            "reason": "发布属于不可逆外部动作，需要主人一次性授权",
            "next": "先在镜像房间完成自审和排练，再由主人发放 deploy_publish",
        }
    return {
        "ok": False, "blocked": True, "room_id": room_id,
        "reason": "授权令牌只允许通过统一 run_task 发布门消费；模块不接受自带令牌绕门",
    }


def run(op="status", **params):
    if op == "status":
        return {"ok": True, "kinds": list(KINDS), "policy": "mirror-first, self-review, owner-gated publish"}
    if op == "plan":
        return plan(params.get("kind", ""), params.get("title", ""), params.get("brief", ""))
    if op == "knowledge":
        return knowledge(params.get("kind", ""))
    if op == "collaborate":
        return collaborate(params.get("kind", ""), params.get("objective", ""),
                           cycle_id=params.get("cycle_id", ""))
    if op == "launch_cycle":
        return launch_cycle(params.get("kind", ""), params.get("objective", ""),
                            params.get("task_id", ""), cycle_id=params.get("cycle_id", ""))
    if op == "compose":
        return compose(
            params.get("kind", ""), params.get("title", ""), params.get("brief", ""),
            params.get("room_id", ""), params.get("assets") or {},
            copyright_attested=params.get("copyright_attested", False),
            safety_reviewed=params.get("safety_reviewed", False),
            owner_reviewed=params.get("owner_reviewed", False),
        )
    if op == "review":
        return self_review(params.get("manifest") or {}, params.get("room_id", ""))
    if op == "publish":
        return publish(params.get("room_id", ""), authorization=params.get("authorization", ""))
    return {"ok": False, "error": f"unknown op: {op}"}
