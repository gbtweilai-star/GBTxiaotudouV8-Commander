# -*- coding: utf-8 -*-
# gbt-capability: media-publish
"""三方向发布到**赚钱平台**的准备与授权门（native 能力位 `media_publish`）。

## 它做什么、**不做什么**（这条最重要）

Owner 2026-09-23 令：「把发布歌曲赚钱的平台也要集成进去，让她实现自动化到发布，另外两个也一样」。

本能力位把这条链**推到最后一格**，但**不越过那格**：

    集成平台（口径）→ **备好发布包**（元数据/封面/许可摘录/十道闸清单/目标平台）→ ⛔ **授权门** → 发布

- ✅ **做到**：把"发布"这件不可逆外部动作之前**所有能自动化的东西**做完 ——
  发布包（每个产物一份 JSON：sha256 + 许可 + 元数据模板 + 目标平台 + 闸清单）；
- ⛔ **不做**：真的发出去。理由有三，且都是硬的：
  1. 框架自己的门：`media_pipeline.publish` 是**硬门**（"发布属于不可逆外部动作，需要主人一次性授权"），
     而且它**拒绝自带令牌绕门**（"模块不接受自带令牌绕门"）—— 本能力位**不替它开路**；
  2. 本机**没有**任何平台凭据（密钥池 `keys_total:0`），没凭据的"发布"只能是一条假回执；
  3. 发布一次不可撤（平台侧删不干净），这是主人的动作，不是我的。

## 平台口径**复用**，不另造

- **音乐**：直接复用能力位 `music_publishing`（`tools/music_publishing.py`，13 个平台，
  全标「**未核实**」并如实写"出网被挡 ⇒ 结构与口径今天能落，实调不能；『在』不等于『能用』"）。
  本能力位**只引用它**，不复制它的表。
- **短视频 / 电影**：框架里**没有**现成表 ⇒ 本能力位给出一份**同样标「未核实」**的候选表，
  并把"未核实"写在每条上 —— **不许把它们说成"已接通"**。

## 红线

1. **零出网**：本能力位只写本地发布包，不发任何请求。
2. **不许假回执**：`submit` 永远返回 `blocked` + 主人该敲的那条命令；**绝不说"已发布"**。
3. 发布包落 `projects/_shared/publish/<方向>/`（**不落 18 格抽屉** —— 抽屉有家规：命名/类型/许可）。
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .media_license import run as lic_run     # noqa: E402  许可账（单一来源）
from .audio_extract import write_guard        # noqa: E402  写面守卫（单一来源）

_IMPL_VERSION = "1.0"
READ_OPS = ("status", "platforms")
WRITE_OPS = ("prepare", "submit")
PUB_ROOT = "_shared/publish"

KIND_CN = {"short_video": "短视频", "film": "AI电影", "music": "AI音乐"}

# 短视频 / 电影：框架里**没有**现成平台表 ⇒ 候选表，**每条都标未核实**
# （口径照 music_publishing 的诚实标准：结构与入口今天能落，实调不能）
PLATFORMS = {
    "short_video": [
        {"name": "抖音", "class": "国内主平台", "earn": "创作者激励 / 星图 / 直播 / 小店", "needs": "实名 + 创作者账号 + 授权", "verified": False},
        {"name": "快手", "class": "国内主平台", "earn": "创作者激励 / 快分销", "needs": "实名 + 授权", "verified": False},
        {"name": "视频号", "class": "国内主平台", "earn": "创作分成 / 直播", "needs": "微信生态账号 + 授权", "verified": False},
        {"name": "B 站", "class": "国内主平台", "earn": "激励计划 / 充电", "needs": "实名 + 创作激励开通", "verified": False},
        {"name": "小红书", "class": "国内主平台", "earn": "薯条 / 商单", "needs": "专业号 + 授权", "verified": False},
        {"name": "YouTube Shorts", "class": "海外主平台", "earn": "Shorts 分成（需入 YPP）", "needs": "频道 + 1000 订阅/门槛 + 授权", "verified": False},
        {"name": "TikTok", "class": "海外主平台", "earn": "Creator Rewards", "needs": "地区资质 + 授权", "verified": False},
    ],
    "film": [
        {"name": "爱奇艺（号/自制）", "class": "长视频平台", "earn": "分账（有效播放）+ 自制采购", "needs": "版权方/机构资质 + 授权", "verified": False},
        {"name": "腾讯视频", "class": "长视频平台", "earn": "分账 + 采购", "needs": "版权方资质 + 授权", "verified": False},
        {"name": "优酷", "class": "长视频平台", "earn": "分账 + 采购", "needs": "版权方资质 + 授权", "verified": False},
        {"name": "B 站（影视区）", "class": "长视频平台", "earn": "激励 / 联合出品", "needs": "实名 + 授权", "verified": False},
        {"name": "YouTube（长片）", "class": "海外", "earn": "广告分成（需入 YPP）", "needs": "频道门槛 + 授权", "verified": False},
        {"name": "海外发行/影展", "class": "发行渠道", "earn": "版权销售 / 采购 / 奖金", "needs": "成片 + 版权链 + 投递", "verified": False},
    ],
}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _platforms(kind: str) -> dict:
    """平台口径 —— 音乐**复用** `music_publishing`，另两个用本文件里同样标未核实的候选表。"""
    if kind == "music":
        try:
            from .. import api as _api
            r = _api.run_task("music_publishing", {"op": "status"})
            i = (r.get("result") or {}).get("result") or {}
            return {"ok": bool(i.get("ok")), "source": "复用能力位 `music_publishing`（不另造）",
                    "counts": i.get("counts"), "classes": i.get("classes"),
                    "honest": i.get("honest")}
        except Exception as e:                                        # noqa: BLE001
            return {"ok": False, "error": "读 music_publishing 失败：%s" % str(e)[:120]}
    rows = PLATFORMS.get(kind) or []
    return {"ok": True, "source": "本能力位内置候选表（框架里没有现成表）",
            "counts": {"total": len(rows), "verified": 0, "unverified": len(rows)},
            "platforms": rows,
            "honest": "**全部标「未核实」**：结构、入口、变现方式今天能落；能不能真调，"
                      "要凭据与授权到位才知道 —— **「在」不等于「能用」**。"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "impl": "media_publish", "version": _IMPL_VERSION,
                "kind": "media_publish", "domain": "video",
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "prepare_root": "projects/" + PUB_ROOT,
                "kinds": list(KIND_CN),
                "gate": "发布是**不可逆外部动作** ⇒ 停在主人的授权门前：需要 `deploy_publish` 一次性授权；"
                        "本能力位**零出网**、**不发任何请求**、**绝不返回「已发布」**。",
                "note": "做到「发布前所有能自动化的」为止：发布包（sha256 + 许可 + 元数据 + 目标平台 + 闸清单）。"}
    if op == "platforms":
        k = str(kw.get("kind") or "")
        if k not in KIND_CN:
            return {"ok": False, "error": "不认的方向 %r（认这些：%s）" % (k, "、".join(KIND_CN))}
        return {"ok": True, "kind": k, "label": KIND_CN[k], **_platforms(k)}
    if op == "prepare":
        return _prepare(str(kw.get("kind") or ""), str(kw.get("product") or kw.get("file") or ""),
                        str(kw.get("title") or ""), str(kw.get("desc") or ""),
                        list(kw.get("tags") or []), str(kw.get("cover") or ""))
    if op == "submit":
        return _submit(str(kw.get("kind") or ""), str(kw.get("package") or ""),
                       str(kw.get("authorization") or ""))
    return {"ok": False, "error": "不认的 op：%s（读 %s / 写 %s）"
                                 % (op, "/".join(READ_OPS), "/".join(WRITE_OPS))}


def _prepare(kind: str, product: str, title: str, desc: str, tags: list, cover: str) -> dict:
    if kind not in KIND_CN:
        return {"ok": False, "error": "不认的方向 %r" % kind}
    if not product:
        return {"ok": False, "error": "op=prepare 需要 product（要发布的产物路径）"}
    p = Path(product)
    ap = (p if p.is_absolute() else (_ROOT / p)).resolve()
    if not ap.is_file():
        return {"ok": False, "error": "产物不在盘上：%s" % product}
    lic = lic_run("list")
    entry = next((e for e in (lic.get("entries") or [])
                  if (_ROOT / e.get("file", "")).resolve() == ap), None)
    rel_out = "projects/%s/%s/%s.publish.json" % (PUB_ROOT, kind, ap.stem)
    g = write_guard(rel_out)
    if not g.get("ok"):
        return {"ok": False, "error": g["why"], "refused": True}
    pkg = {
        "version": 1, "kind": kind, "label": KIND_CN[kind],
        "product": {"file": str(ap.relative_to(_ROOT)).replace("\\", "/"),
                    "sha256": _sha256(ap), "bytes": ap.stat().st_size},
        "license": ({"file": entry.get("file"), "sha256": entry.get("sha256"),
                     "source": entry.get("source"), "license": entry.get("license")}
                    if entry else None),
        "metadata": {"title": title or ap.stem, "desc": desc, "tags": tags,
                     "cover": cover or None,
                     "note": "标题/简介/标签先落模板；平台侧字段各平台不同，提交时再按平台整形"},
        "targets": _platforms(kind).get("classes") or _platforms(kind).get("platforms"),
        "preflight": {
            "license_registered": bool(entry),
            "naming_compliant": bool(__import__("re").match(
                r"^\d{8}-(?:short-video|film|music)-.+-(?:\d{2}[a-z]+|rehearsal)(?:-v\d+)?\.[A-Za-z0-9]+$",
                ap.name)),
            "rehearsal": "-rehearsal" in ap.name,
            "note": "**彩排件不要发布**；正式件的文件名不带 -rehearsal（本栏只报事实，不替你判）。",
        },
        "gate": {"required_scope": "deploy_publish",
                 "how": "python -m gbt_allinone auth grant --scope deploy_publish --ttl 600",
                 "why": "发布不可逆 + 零凭据 ⇒ 必须主人一次性授权"},
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    dst = Path(g["abs"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(pkg, ensure_ascii=False, indent=2), encoding="utf-8")
    ready = pkg["preflight"]["license_registered"] and pkg["preflight"]["naming_compliant"]
    return {"ok": True, "package": g["rel"], "ready_for_owner_review": ready, "preflight": pkg["preflight"],
            "targets_n": len(pkg["targets"] or []),
            "note": "发布包已备好（**这一步是自动化的终点**）；下一步是**主人的授权门**。"}


def _submit(kind: str, package: str, authorization: str) -> dict:
    """⛔ **这一步永远返回 blocked** —— 见模块头三条硬理由。"""
    if not package:
        return {"ok": False, "error": "op=submit 需要 package（发布包路径）"}
    p = Path(package)
    ap = (p if p.is_absolute() else (_ROOT / p)).resolve()
    if not ap.is_file():
        return {"ok": False, "error": "发布包不在盘上：%s" % package}
    return {"ok": False, "blocked": True, "package": str(ap.relative_to(_ROOT)).replace("\\", "/"),
            "reason": "发布是**不可逆外部动作**，且本机**零平台凭据**（密钥池 keys_total:0）"
                      "⇒ 框架自标「编排/审查层」，`media_pipeline.publish` 也明写"
                      "「模块不接受自带令牌绕门」。本能力位**不替它开路**。",
            "owner_actions": [
                "① 在终端发一次性授权：`python -m gbt_allinone auth grant --scope deploy_publish --ttl 600`",
                "② 给平台凭据（哪几个平台、以什么身份发）—— 本机现在一个都没有",
                "③ 正式件去掉 `-rehearsal`（彩排件不该发出去）",
            ],
            "never": "本能力位**零出网**，任何情况下都不会返回「已发布」。",
            "authorization_seen": bool(authorization),
            "note": "传了 authorization 也一样 blocked —— 门在 run_task 那一层，不在这个参数上。"}
