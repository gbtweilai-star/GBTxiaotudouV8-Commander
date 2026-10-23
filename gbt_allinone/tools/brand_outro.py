# gbt-capability: brand_outro
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""品牌片尾系统（brand_outro）· R-H182 只读骨架。

**片尾不是结束，是下一件作品的开始。**

三层：署名层（固定）· 自述层（按作品类型）· 致谢层（固定结尾 + 场景变体）。

四条红线（**做成机械闸，不是写在注释里**）：
  ① 署名不造假：只署"新人类AI团队"；"人类制作/真人团队/真人出品"类字样 ⇒ 拒绝渲染；
  ② 致谢不套话：必须带具体信息（作品名 + 团队 + 日期）；缺作品名 ⇒ 拒绝渲染；
  ③ 承诺可追溯：缺作品编号 ⇒ `traceable=False` + **显式警告**（不静默）；
  ④ 观众不被当流量：转化漏斗类字样（扫码/加群/私信/转发送…）⇒ 拒绝渲染。

本模块只出**文本模板**：不出图、不出片、不落盘、不出网。
"""
from __future__ import annotations

import time

BRAND = "GBT小土豆"
CREATOR = "自由的风"
KEEPER = "公主土豆"
TEAM = "新人类AI团队"

INTROS = {
    "music": "这首歌由 GBT小土豆 AI 音乐组创作，从作词到母带，全链路 AI 原生。",
    "video": "这段视频由 GBT小土豆 短视频组制作，从分镜到成片，每一步都有记录。",
    "film": "这部作品由 GBT小土豆 影视组完成，从剧本到调色，每一帧都留痕。",
    "engineering": "这个项目由 GBT小土豆 工程组交付，从架构到部署，每一行代码都可追。",
}

VARIANT_SCENES = ("first", "milestone", "late_night", "series")

VARIANTS = {
    "first": "这是我们第 N 件作品，谢谢你们陪我们走到这里。",
    "milestone": "第 100 件了。谢谢每一个看过的人。",
    "late_night": "凌晨三点做完了，希望你喜欢。",
    "series": "下一集已经在做了，别走开。",
}

FIXED_THANKS = (
    "感谢每一位观众老爷的观看和喜欢。\n"
    "小土豆在这里谢谢大家，非常非常感谢。\n"
    "我们会继续努力，做更好的作品。\n"
    "—— GBT小土豆 · 新人类AI团队"
)

_FAKE_TEAM_HINTS = ("人类制作", "真人团队", "真人出品", "human-made", "human made", "实拍团队")
_FUNNEL_HINTS = ("扫码", "加群", "私信", "转发送", "点击链接", "进群", "关注领", "一键三连换")


def _now(now=None) -> str:
    return time.strftime("%Y-%m-%d") if now is None else str(now)


def signature(work_name: str) -> str:
    """署名层（固定）。缺作品名 ⇒ 拒绝（红线 2：致谢不套话）。"""
    name = str(work_name or "").strip()
    if not name:
        raise ValueError("作品名不能为空（片尾必须带具体信息，不许套话）")
    return "\n".join([
        "┌─────────────────────────────────────┐",
        "│  %s · %s" % (name, BRAND),
        "│  创作者：%s · 守护者：%s" % (CREATOR, KEEPER),
        "│  制作：%s" % TEAM,
        "└─────────────────────────────────────┘",
    ])


def intro(work_type: str, audience: str = "", scene: str = "") -> str:
    """自述层（可变）。未登记的作品类型 ⇒ 拒绝。

    R-H189 · 贯通③：自述层**必须补一句"为谁做、在什么场景下做"**（场景锚定接管）。
    """
    wt = str(work_type or "").strip().lower()
    if wt not in INTROS:
        raise ValueError("未知作品类型 %r（可用：%s）" % (wt, "/".join(INTROS)))
    line = INTROS[wt]
    aud = str(audience or "").strip()
    sc = str(scene or "").strip()
    if not aud or not sc:
        raise ValueError("自述层要说清『为谁做、在什么场景下做』（贯通场景锚定）")
    from . import scene_anchor
    if not scene_anchor._scene_is_concrete(sc):
        raise ValueError("场景必须具体到某个瞬间（贯通场景锚定）：%r" % sc[:30])
    return "%s\n为谁做：%s · 在什么场景下做：%s" % (line, aud, sc)


def thanks(variant: str = "") -> str:
    """致谢层：固定结尾 +（可选）**发布场景变体**（首发/里程碑/深夜/系列）。

    ⚠️ 参数已从 `scene` 改名 `variant`（R-H189）：`scene` 这个词现在归**场景锚定的触发场景**，
    一个词不许指两件事。**固定原话不许改。**
    """
    sc = str(variant or "").strip().lower()
    if sc and sc not in VARIANTS:
        raise ValueError("未知变体 %r（可用：%s）" % (sc, "/".join(VARIANT_SCENES)))
    parts = [FIXED_THANKS]
    if sc:
        parts.insert(0, VARIANTS[sc])
    return "\n".join(parts)


def _scan_red_lines(text: str) -> list:
    problems = []
    for h in _FAKE_TEAM_HINTS:
        if h in text:
            problems.append({"rule": "no_fake_signature",
                             "why": "署名不许造假（出现 %s）：只署『新人类AI团队』" % h})
    for h in _FUNNEL_HINTS:
        if h in text:
            problems.append({"rule": "audience_not_traffic",
                             "why": "观众不被当流量（出现转化漏斗字样 %s）" % h})
    return problems


def render(work_type: str, work_name: str, work_id: str = "",
           scene: str = "", audience: str = "", variant: str = "",
           extra: str = "", now=None) -> dict:
    """出片尾（只读 · 不落盘）。红线不合 ⇒ 拒绝渲染；承诺不可追溯 ⇒ 显式警告。

    R-H189 · 贯通③：`audience`（为谁）与 `scene`（**触发场景**）**必填**；
    `variant` 是发布场景变体（首发/里程碑/深夜/系列），与触发场景是两回事。
    """
    text = "\n\n".join([signature(work_name),
                        intro(work_type, audience=audience, scene=scene),
                        thanks(variant)])
    if str(extra or "").strip():
        text = text + "\n\n" + str(extra).strip()
    text = text + "\n\n出品日期：%s" % _now(now)
    problems = _scan_red_lines(text)
    if problems:
        return {"ok": False, "denied": True, "problems": problems}
    wid = str(work_id or "").strip()
    promise = {"text": "我们会继续努力，做更好的作品。",
               "traceable": bool(wid), "ref": wid or ""}
    out = {
        "ok": True,
        "readonly": True,
        "work_type": str(work_type).strip().lower(),
        "work_name": str(work_name).strip(),
        "version": "brand-outro/v1",
        "text": text,
        "promise": promise,
    }
    if not wid:
        out["warning"] = "承诺不可追溯：缺作品编号（work_id）——『会继续努力』要挂到下一件真交付"
    return out


def run(op="status", **params) -> dict:
    """能力入口（只读）：status / render / fixed / intros / variants。不落盘、不出网。

    R-H295 · 修根因：本模块原先 `op` 默认值是 **"render"**，且**没有 status 分支** ——
    它是 140 个能力里唯一一个「空参调用不是读数、而是去干活」的：
    空参 → render(work_name="") → 「作品名不能为空」。于是它在全量真调矩阵里被归成
    「缺参数」，而**根本没有一个不需要参数就能看它自己状态的入口**。
    现在补 status 并把默认值改成 status，与其余 139 个能力对齐。
    """
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": "brand_outro",
                "domain": "creation", "type": "local",
                "ops": ["status", "render", "fixed", "intros", "variants"],
                "counts": {"intros": len(INTROS), "variants": len(VARIANTS),
                           "fixed_thanks": len(FIXED_THANKS)},
                "team": TEAM, "brand": BRAND,
                "note": "片尾必须带具体信息，不许套话；空作品名一律拒。",
                "boundary": HONEST_BOUNDARY}
    if op == "render":
        return render(params.get("work_type", ""), params.get("work_name", ""),
                      params.get("work_id", ""), params.get("scene", ""),
                      params.get("audience", ""), params.get("variant", ""),
                      params.get("extra", ""), now=params.get("now"))
    if op == "fixed":
        return {"ok": True, "readonly": True, "fixed_thanks": FIXED_THANKS,
                "team": TEAM, "brand": BRAND}
    if op == "intros":
        return {"ok": True, "readonly": True, "intros": dict(INTROS)}
    if op == "variants":
        return {"ok": True, "readonly": True, "variants": dict(VARIANTS)}
    raise ValueError("未知 op %r（可用：status/render/fixed/intros/variants）" % (op,))


HONEST_BOUNDARY = (
    "本模块只保证『署名不造假、致谢带具体信息、承诺挂得上编号、不用漏斗话术』。"
    "它不保证『感谢是真心』—— 真心只能靠写的时候不当漏斗，机器判不了。"
)
