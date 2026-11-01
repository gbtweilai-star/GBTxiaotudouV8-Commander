"""GBT小土豆V8 · 职业路由（任务 → 职业 → 能力位 → 派单计划）

主人 2026-11-01：「下一步」——职业表建好后，要能让任务找到对口的触手。

做法（不引入新能力位，避免动 385 的锁）：
  · 读 data/professions.json（21 职业，全覆盖 385 能力位）；
  · 关键词打分：职业标题/域/能力位名/工具/KPI 命中即加分，中文关键词单独一张表；
  · route(task) → 排序后的职业 + 命中词 + 候选能力位（只挑 safe 的，需授权位标注出来）；
  · plan(task) → 给「协同/指挥」的派单计划（首选职业 + 兜底职业 + 候选能力位 + 留痕要求）。

只读：不执行任何能力位；真正派单仍走 run_task（危险/转账永远要票）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROF_PATH = ROOT / "data" / "professions.json"

# 中文/英文关键词 → 职业 id（命中即加分；多词累加）
KEYWORDS = {
    "coder": ["写代码", "改代码", "修 bug", "修bug", "重构", "实现", "开发", "补丁", "patch",
              "code", "bug", "refactor", "commit", "git", "函数", "模块", "单元测试"],
    "reviewer": ["审查", "评审", "review", "code review", "看代码", "静态检查", "审计代码"],
    "qa": ["测试", "验证", "跑测试", "回归", "test", "qa", "断言", "真跑", "验收", "自检", "巡检"],
    "security": ["安全", "渗透", "扫描", "漏洞", "无死角", "疑点", "pentest", "scan", "security"],
    "ops": ["部署", "上线", "服务", "端口", "引擎", "重启", "运维", "ops", "deploy", "server", "自检"],
    "architect": ["架构", "设计", "契约", "链路", "五处", "architect", "design", "registry"],
    "data": ["数据", "指标", "回测", "口径", "账本", "data", "metric", "backtest"],
    "vision": ["看图", "截图", "识别", "ocr", "视觉", "image", "vision", "图表"],
    "media": ["语音", "配音", "字幕", "音频", "voice", "audio", "tts", "asr"],
    "recon": ["调研", "搜索", "资料", "来源", "recon", "research", "arxiv", "蒸馏"],
    "writer": ["文档", "写作", "说明", "readme", "changelog", "文案", "写作", "doc"],
    "shortvideo": ["短视频", "抖音", "口播", "分镜", "钩子", "完播", "short video", "reel", "剪辑"],
    "music": ["音乐", "作曲", "编曲", "混音", "母带", "歌", "music", "song", "beat", "伴奏"],
    "film": ["电影", "影视", "短片", "剧本", "镜头", "film", "movie", "cinema", "成片"],
    "digitalhuman": ["数字人", "直播", "口型", "动作", "形象", "avatar", "live", "digital human"],
    "design": ["设计", "配色", "版式", "品牌", "海报", "logo", "design", "brand", "审美"],
    "gamedev": ["游戏", "3d", "建模", "场景", "blender", "three", "game", "模型"],
    "integration": ["接入", "集成", "mcp", "飞书", "telegram", "whatsapp", "notion",
                    "webhook", "integration", "桥"],
    "cli": ["命令行", "终端", "cli", "shell", "命令"],
    "life": ["生活", "提醒", "习惯", "陪伴", "life", "remind"],
    "orchestrator": ["派单", "编排", "协同", "调度", "交接", "orchestrate", "dispatch", "任务分派"],
}


def load_professions() -> dict:
    try:
        return json.loads(PROF_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"professions": [], "coverage": {}}


def _safe_caps(prof: dict, cap_meta: dict) -> list:
    """候选能力位分成 safe / needs-ticket，不混在一起。"""
    safe, gated = [], []
    for name in prof.get("caps") or []:
        meta = cap_meta.get(name) or {}
        if meta.get("safe", False):
            safe.append(name)
        else:
            gated.append(name)
    return safe, gated


def _cap_meta() -> dict:
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return {k: {"safe": bool((v or {}).get("safe"))} for k, v in BENIGN_CAPS.items()}
    except Exception:  # noqa: BLE001
        return {}


def _score(task: str, prof: dict) -> tuple:
    """返回 (分数, 命中词)。标题/域/能力位/工具/KPI 都算。"""
    text = task.lower()
    hits = []
    score = 0
    # 中文关键词（按职业）
    for kw in KEYWORDS.get(prof.get("id", ""), []):
        if kw.lower() in text:
            score += 5
            hits.append(kw)
    # 标题/域/工具/KPI 词面命中
    for field, weight in (("title", 4), ("headline", 2), ("kpi", 2)):
        val = str(prof.get(field) or "").lower()
        for token in re.split(r"[ /·、,，]+", val):
            if len(token) >= 2 and token in text:
                score += weight
                hits.append(token)
    for dom in prof.get("domains") or []:
        if dom.lower() in text:
            score += 2
            hits.append(dom)
    for cap in prof.get("caps") or []:
        if cap.lower() in text:
            score += 3
            hits.append(cap)
    # 代码类动词优先给编程工程师（"修 bug"/"改代码"/"实现功能"不该被 QA 抢走）
    if prof.get("id") == "coder" and re.search(
            r"(修|改|实现|开发|补|重写).{0,6}(bug|代码|模块|功能|逻辑|接口)", text):
        score += 20
        hits.append("代码类动词优先")
    return score, sorted(set(hits))


def route(task: str, top_k: int = 3) -> dict:
    box = load_professions()
    profs = box.get("professions") or []
    meta = _cap_meta()
    ranked = []
    for prof in profs:
        score, hits = _score(task or "", prof)
        safe, gated = _safe_caps(prof, meta)
        if score > 0:
            ranked.append({
                "profession": prof.get("title"), "id": prof.get("id"),
                "score": score, "matched": hits[:8],
                "cap_count": prof.get("cap_count"),
                "safe_caps": safe[:12], "gated_caps": gated[:12],
                "tools": prof.get("tools"), "kpi": prof.get("kpi"),
            })
    ranked.sort(key=lambda x: (-x["score"], -(x.get("cap_count") or 0)))
    routed = ranked[:top_k]
    return {
        "ok": bool(routed),
        "task": task,
        "routed": routed,
        "fallback": {"profession": "协同 / 指挥", "id": "orchestrator"},
        "rule": "关键词命中标题/域/能力位/工具/KPI；同分按能力位数量；没命中走协同/指挥。",
        "readonly": True,
    }


def plan(task: str) -> dict:
    r = route(task, top_k=3)
    routed = r.get("routed") or []
    if not routed:
        return {"ok": False, "task": task, "reason": "没有命中任何职业（走协同/指挥人工定）",
                "fallback": r.get("fallback")}
    first = routed[0]
    return {
        "ok": True,
        "task": task,
        "profession": first["profession"],
        "id": first["id"],
        "matched": first["matched"],
        "safe_candidates": first["safe_caps"][:8],
        "gated_candidates": first["gated_caps"][:8],
        "alternatives": [x["profession"] for x in routed[1:]],
        "tools": first["tools"],
        "kpi": first["kpi"],
        "ledger": "orchestration-ledger（每次派单必须留痕）",
        "readonly": True,
    }


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "修一个 bug 并跑测试"
    print(json.dumps(plan(task), ensure_ascii=False, indent=2))
