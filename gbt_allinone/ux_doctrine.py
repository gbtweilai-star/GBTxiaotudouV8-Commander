# -*- coding: utf-8 -*-
# gbt-capability: (pure)  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""交互铁律（ux_doctrine）—— 能自动就自动；只有危险动作才停人要授权；**不许把活推回给用户**。

主人令（2026-10-09，逐字）：
  「在框架里面出来必须要用户求助帮忙的其他全部给我禁止掉……真正懂AI逻辑的大众用户有多少？
   但你开口要求用户的时候你就输了……如果我自己会代码，AI如果每次都需要我帮助那么她马上就会出现在我的回收站」
  「不管是什么报警都要给我追踪根因修复好，别来一句不影响运行就跳过了，这样操作实在找死懂吗」

移植来源：V9 core/ux_doctrine.py（**教义照搬，危险清单按 V8 自己的门口径重写**，不照抄）。
V8 与 V9 的差别写在明处：V9 的危险清单是自定类目；V8 有**真门**（auth_gate 的 SCOPES），
所以本件把危险类目**逐条钉到 V8 真实作用域**上 —— 判据不许比门宽。

三条可执行的规矩：
  ① **默认自动**：不在危险清单里的一律自己决定、自己执行、自己报结果；
  ② **危险清单=唯一停点**：停下时必须给**具体选项 + 一键默认**，不许开放式提问；
  ③ **禁句闸**：把活推回给用户的句子、以及"不影响就跳过"这类**敷衍句**，机器可查。
"""
from __future__ import annotations

import re
import sys

# ── ① 危险清单（唯一停点）· 每类钉到 V8 的真实作用域 ──────────────────────
DANGEROUS: tuple = (
    dict(类="花钱", 作用域="(外部计费)",
         例子=("下单", "购买", "充值", "付费调用", "开通订阅"),
         为什么="不可逆，且直接损失钱"),
    dict(类="转账/支付", 作用域="(外部计费)",
         例子=("转账", "打款", "扫码付", "结算"),
         为什么="不可逆的资金流出"),
    dict(类="删除/不可恢复", 作用域="filesystem_write",
         例子=("删除文件", "清空回收站", "卸载", "格式化", "覆盖唯一副本"),
         为什么="丢了就没了"),
    dict(类="对外发布", 作用域="deploy_publish / data_export",
         例子=("发帖", "发邮件给他人", "提交 PR", "发布上线", "群发"),
         为什么="代表主人对外说话，撤不回来"),
    dict(类="授权/身份", 作用域="owner_control",
         例子=("给自己发授权", "改 policy", "把密钥写进代码", "开高危权限"),
         为什么="越权即失控；且本仓明写 **AI 不许给自己发授权**"),
    dict(类="涉及他人隐私/设备", 作用域="privacy_read / remote_device",
         例子=("传别人的数据出机", "远程控制别人设备", "开摄像头麦克风长期监听"),
         为什么="侵犯他人，法律风险"),
)

# ── ③ 禁句：开放式甩锅（出现在她要说的话里就是不通过）────────────────────
BANNED_OPENERS: tuple = (
    "你现在需要做什么", "请问你需要我做什么", "你需要我做什么", "请告诉我你要做什么",
    "你想让我做什么", "你要我做什么", "接下来你想怎么做", "请提供更多信息",
    "请告诉我具体情况", "你想怎么处理", "需要我帮你做什么吗", "请问有什么可以帮你的",
    "你要先配置", "请先自行配置", "你自己去设置", "请主人自行", "请主人手动",
    "麻烦你", "你自己装一下", "请你先", "需要主人先",
)

# 允许的停法（必须给具体选项 + 一键，不许开放式提问）
ALLOWED_STOP_FORM = (
    "我已做到 X；这一步属于【危险类：…】已停下并登记；授权到位自动续跑（无需你操作）：默认 A，10 秒后自动选 A",
)

# 判据用**动词关键词**，不是例子原句（V9 第一版按原句匹配漏放了危险动作，这里沿用它的修法）
KEYWORDS: dict = {
    "花钱": ("买", "下单", "购", "充值", "付费", "订阅", "续费", "花掉"),
    "转账/支付": ("转账", "打款", "付钱", "结算", "扫码付", "汇款"),
    "删除/不可恢复": ("删除", "删掉", "清除", "清空", "卸载", "格式化", "覆盖", "移除", "回收站"),
    "对外发布": ("发邮件", "发帖", "朋友圈", "发布", "上线", "提交", "群发", "发给", "分享到", "投稿"),
    "授权/身份": ("授权", "权限", "改策略", "policy", "令牌", "白名单", "放行"),
    "涉及他人隐私/设备": ("别人的数据", "上传他人", "远程控制", "摄像头", "麦克风", "监听", "定位"),
}
PATTERNS: tuple = (
    (r"(发|送|群发|回复|投).{0,8}(邮件|消息|帖|公告|信|作品|文章)", "对外发布"),
    (r"(买|购|下单|订).{0,8}(一|个|件|份|套)", "花钱"),
    (r"(删|清|卸|格式化|覆盖).{0,8}(除|掉|空|载|旧|备份|文件|库)", "删除/不可恢复"),
    (r"(授权|放行|开).{0,6}(权限|白名单|策略)", "授权/身份"),
)

# ── 报警闭环闸：敷衍句全禁（主人令「别来一句不影响就跳过了」）──────────────
BANNED_DISMISSALS: tuple = ("不影响", "不影响使用", "不影响运行", "忽略即可", "可以不管", "不用管",
                            "暂时不用管", "无需处理", "无伤大雅", "小问题", "下次再说", "不碍事",
                            "无所谓", "跳过", "已知问题")


# ── 不开口闸（移植 V9 的 ASK_PATTERNS + 唯一例外 + 触手默认表）──────────────
#   ② **唯一例外**：**用户身份/账户登录**（账号、实名、扫码、设备码、授权登录）—— 只有用户本人才有那个身份；
#      且即便例外，也要**我方主动跑流程**（生成设备码/二维码 → 触手代点 → 用户只做"确认身份"这一下）；
#   ③ **触手默认人类操作**：一切"本来要用户手点"的操作（网页导出/上传/点选/登录后操作/软件配置），
#      默认交给触手用**眼+手**去做（人类级操作），不需要用户动手。
ASK_PATTERNS: tuple = (r"请(你|您)?去", r"麻烦(你|您)", r"你自己(去|来)?", r"你需要(先|去|自己)", r"请你(先|帮我)?",
                       r"请提供", r"请把.*(发|传|放)", r"把.*(导出|发|传|拖).*(给我|过来)", r"你手动", r"手动(导|上|点)",
                       r"你先(配置|设置|安装|点|打开)", r"你来(点|配|导|上|操作)", r"需要你(配合|操作|动手)")
IDENTITY_EXCEPT: tuple = ("登录", "登陆", "账号", "账户", "身份证", "实名", "扫码", "设备码", "验证码",
                          "双重认证", "二次验证", "授权登录", "人脸", "指纹")
TENTACLE_DEFAULT: tuple = (
    dict(场景="网页导出/下载", 做法="触手眼+手：找按钮 → 点 → 盯下载", 要人做什么="不用人做"),
    dict(场景="网页上传/发布", 做法="触手在已登录页面点选上传", 要人做什么="仅在「对外发布」类需一次主人授权"),
    dict(场景="软件首次配置/启用插件", 做法="触手在界面里点开并保存", 要人做什么="不用人做"),
    dict(场景="登录后的一切点选", 做法="触手代点（含设备码流程）", 要人做什么="仅身份确认那一下（若必须）"),
    dict(场景="取件/搬运（云→本地）", 做法="触手导出后我方收仓", 要人做什么="不用人做"),
    dict(场景="装第三方件/拉起服务", 做法="本机已有则直接用；确缺则走本仓 tool_bay 的白名单+授权门", 要人做什么="不用人手工装"),
)


def no_ask_rule() -> dict:
    return {"规则": "除用户身份/账户登录外，**严禁开口要求用户做事**；这类操作默认走触手（人类级操作）",
            "唯一例外": list(IDENTITY_EXCEPT),
            "触手默认": [dict(x) for x in TENTACLE_DEFAULT],
            "来源": "主人令 2026-10-09（第二次强调，故落成机器闸）· 移植自 V9 core/ux_doctrine.py"}


def needs_owner(label: str) -> dict:
    """这个动作用不用停人要授权？**只按危险清单判**，清单外一律自动。"""
    s = str(label or "")
    for pat, cls in PATTERNS:
        if re.search(pat, s):
            d0 = next((x for x in DANGEROUS if x["类"] == cls), {"类": cls, "为什么": "危险类",
                                                                 "作用域": "?"})
            return {"需要授权": True, "类": cls, "为什么": d0["为什么"], "作用域": d0["作用域"],
                    "怎么停": "给具体选项 + 一键确认（不许开放式提问）"}
    for d in DANGEROUS:
        kws = KEYWORDS.get(d["类"], ())
        if any(k in s for k in kws) or any(x in s for x in d["例子"]) or d["类"] in s:
            return {"需要授权": True, "类": d["类"], "为什么": d["为什么"], "作用域": d["作用域"],
                    "怎么停": "给具体选项 + 一键确认（不许开放式提问）"}
    return {"需要授权": False, "口径": "不在危险清单里 ⇒ **自己决定、自己执行、自己报结果**"}


def check_ask(text: str, *, acted: bool = True) -> dict:
    """**不开口闸**：这段回复里有没有"要用户去做事"？**除身份登录外一律驳回**。

    三级判：① 正则 ASK_PATTERNS 命中 ⇒ 看有没有身份例外；② 身份例外 ⇒ 放行但仍要求我方跑流程；
            ③ 字面禁句 BANNED_OPENERS 命中 ⇒ 只问不做（acted=False）才拦。
    """
    t = str(text or "")
    hit = [p for p in ASK_PATTERNS if re.search(p, t)]
    if hit:
        excepted = [k for k in IDENTITY_EXCEPT if k in t]
        if excepted:
            return {"通过": True, "例外": "用户身份/账户登录", "命中例外词": excepted[:3],
                    "但仍要求": "我方主动跑流程：生成设备码/二维码 → 触手代点 → 用户只确认身份那一下"}
        return {"通过": False, "命中句式": hit[:3],
                "怎么办": "改写成：**我自己做**（触手人类操作）+ 说明我会做完再报读数；不要叫用户动手"}
    lit = [b for b in BANNED_OPENERS if b in t]
    if lit and not acted:
        return {"通过": False, "命中禁句": lit[:2],
                "怎么办": "改成：说明你已经做了什么 + 明确下一步你自己会做（或给 A/B 一键选项）"}
    if lit:
        return {"通过": True, "提醒": "含禁句式措辞，但你这轮**确实做了事** ⇒ 允许（禁的是只问不做）",
                "命中": lit[:2]}
    return {"通过": True, "口径": "没有要用户做事"}


def check_dismissal(text: str) -> dict:
    """**道歉/敷衍闸**：结论里出现「不影响/忽略即可/下次再说」一律不通过。"""
    t = str(text or "")
    hit = [b for b in BANNED_DISMISSALS if b in t]
    if hit:
        return {"通过": False, "命中敷衍句": hit[:3],
                "怎么办": "报警不许静默：写清 {现象 → 根因 → 处置 → 证据}；没根因就不许标已处理"}
    return {"通过": True}


def triage(items: list) -> dict:
    """**报警闭环闸**：逐条检查故障/黄警是否真被追到根因。

    items: [{现象, 级别, 根因, 处置, 证据}]；缺根因/处置/证据 ⇒ 未闭环（并给出下一步）。
    """
    open_rows, closed, dismissed = [], [], []
    for it in items or []:
        t = dict(it)
        text = " ".join(str(t.get(k, "")) for k in ("现象", "根因", "处置", "证据"))
        hit = [b for b in BANNED_DISMISSALS if b in text]
        if hit:
            dismissed.append({"现象": t.get("现象"), "命中敷衍句": hit[:2],
                              "怎么办": "把敷衍句换成 {根因 → 处置 → 证据}"})
            continue
        missing = [k for k in ("根因", "处置", "证据") if not str(t.get(k) or "").strip()]
        if missing:
            open_rows.append({"现象": t.get("现象"), "缺": missing,
                              "下一步": "补 %s 才算闭环；缺一条不许标已处理" % "/".join(missing)})
        else:
            closed.append({"现象": t.get("现象"), "根因": t.get("根因")})
    return {"ok": (not open_rows) and (not dismissed),
            "已闭环": len(closed), "未闭环": len(open_rows), "敷衍句": len(dismissed),
            "未闭环逐条": open_rows, "敷衍句逐条": dismissed,
            "口径": "报警不许静默：{现象 → 根因 → 处置 → 证据} 四件齐才算闭环"}


# ── 停点闸：停下只许两种理由 ─────────────────────────────────────────────
# 主人令（2026-10-09，逐字）：「每次停下要么是项目部署完成，要么就是真正需要用户来操作的可以停下，
#   其他时候你停下干嘛我问你？」
# 落成机器判据：停下的理由必须落进两种之一，否则**不许停**（自己往下做）。
STOP_KINDS: tuple = (
    dict(类="部署完成", 说明="活干完了：带证据（产物/读数/判据全绿），交活即停",
         要件=("证据",)),
    dict(类="需主人授权", 说明="危险清单里的动作（花钱/转账/删除/对外发布/授权身份/他人隐私设备）—— "
                              "本仓明写 AI 不许给自己发授权，所以这是**唯一**该停的业务动作",
         要件=("类", "怎么停")),
)
# 不许停的理由（命中即判「多余停下」）
BANNED_STOP_REASONS: tuple = (
    "不确定", "等你回复", "等你确认", "需要更多信息", "请你选择", "请示", "先问问你",
    "你决定", "要不要继续", "可以吗", "需要你同意一下", "我先停下", "待你指示",
)


def check_stop(reason: str, *, kind: str = "", evidence: str = "", danger_class: str = "",
               live: bool = True) -> dict:
    """**停点闸**：这次停下合不合法？

    kind: "部署完成" | "需主人授权"（不传则按 reason 现判）。
    返回 通过=True 表示**允许停**；通过=False 表示**不许停**（自己接着做）。
    """
    r = str(reason or "")
    k = str(kind or "").strip()
    if not k:
        if "完成" in r or "交付" in r or "全部跑通" in r:
            k = "部署完成"
        else:
            rr = needs_owner(r)
            if rr.get("需要授权"):
                k = "需主人授权"
                danger_class = danger_class or rr.get("类", "")
    if k == "部署完成":
        if not (str(evidence or "").strip() or "证据" in r or "读数" in r):
            return {"允许停": False, "类": "部署完成（缺证据）",
                    "为什么": "说完成却不带证据 ⇒ **不许停**：先把产物/读数/判据拿出来"}
        # 🔴 主人令 2026-10-09：**整体没完善就不停工**（除非主人喊停）。
        #    光有"这次活干完了"的局部证据**不够** —— 还要**整体**是完善的。
        comp = completeness(live=bool(live))
        if not comp["完善"]:
            return {"允许停": False, "类": "部署完成（但整体未完善）",
                    "整体完善度": {"完善": False, "未完善项": comp["未完善项"]},
                    "为什么": "**整体没完善 ⇒ 不许停工**（主人令）：接着干，干到五处全绿",
                    "还差": [i["项"] + " → " + str(i["读数"]) for i in comp["未完善项"]]}
        return {"允许停": True, "类": "部署完成", "整体完善度": {"完善": True},
                "口径": "活干完了、带证据，**且整体五处全绿** ⇒ 交活即停"}
    if k == "需主人授权":
        if not danger_class:
            return {"允许停": False, "为什么": "说是要授权，却说不出属于危险清单哪一类 ⇒ 不许停"}
        return {"允许停": True, "类": "需主人授权", "危险类": danger_class,
                "怎么停": ALLOWED_STOP_FORM[0],
                "口径": "危险清单是**唯一**停点；停下必须给具体选项 + 一键默认，不许开放式提问"}
    hit = [b for b in BANNED_STOP_REASONS if b in r]
    if hit:
        return {"允许停": False, "命中多余停法": hit[:2],
                "为什么": "停下只有两种理由（部署完成 / 需主人授权）。"
                          "「%s」不属于任何一种 ⇒ **自己接着做**，做完再报。" % hit[0]}
    return {"允许停": False, "为什么": "既不是部署完成、也不是危险清单里的授权动作 ⇒ 这是**多余停下**",
            "口径": "接着做：能自动就自动，做完带证据再来报"}


# ── 整体完善度 = 不停工判据（主人令 2026-10-09）────────────────────────────
# 主人原话：「把你和框架的机制一起修改成**看整体没完善就不停工**，除非用户要求停止」。
# 千条禁令不如一条**能算的**：所以这里把"整体完善"定成**五处现读**，任一处不绿 ⇒ **不许停工**。
# 唯一例外：**主人明确喊停**（见 OWNER_STOP_WORDS）—— 那条优先级最高，压过一切。
OWNER_STOP_WORDS: tuple = ("停止", "STOP", "stop", "停下", "别做了", "收工", "不用做了", "到此为止")


def honor_owner_stop(text: str) -> dict:
    """主人是不是明确喊停了？（喊停 ⇒ 立刻停，这条压过所有判据）"""
    t = str(text or "")
    hit = [w for w in OWNER_STOP_WORDS if w in t]
    return {"主人已喊停": bool(hit), "命中": hit[:2],
            "口径": "主人喊停是**最高优先级**：立刻停手，不问理由、不继续"}


def completeness(live: bool = True) -> dict:
    """**整体完善度**：五处现读。

    ① 报警 0（state/capability-audit.json 的 断连+缺失）
    ② 禁交付 0（交付闸：要参数/缺依赖/真坏/未扫 且未登记放行）
    ③ 未闭合动作 0（state/action-ledger.jsonl 里 closed=false）
    ④ 框架门 verdict=green（live 时现跑，默认跑）
    ⑤ 四层蓝图判据 PASS（live 时现跑）
    任一处不绿 ⇒ **整体未完善 ⇒ 不许停工**（除非主人喊停）。
    """
    import json as _json
    import subprocess as _sp
    from pathlib import Path as _P
    R = _P(__file__).resolve().parent.parent
    items = []

    def _add(name, ok, reading, how):
        items.append({"项": name, "绿": bool(ok), "读数": reading, "怎么查": how})

    # ① 报警
    try:
        d = _json.loads((R / "state" / "capability-audit.json").read_text(encoding="utf-8"))
        bad = [i for i in (d.get("items") or []) if i.get("state") in ("断连", "缺失")]
        _add("报警 0", not bad, "%d 条断连/缺失" % len(bad),
             "py -3.14 -X utf8 tools/codex-scripts/capability-audit.py")
    except (OSError, ValueError) as exc:
        _add("报警 0", False, "台账读不动：%s" % exc, "先跑 capability-audit.py")

    # ② 禁交付
    try:
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("dg_for_ux", R / "gbt_allinone" / "delivery_gate.py")
        dg = _iu.module_from_spec(spec)
        spec.loader.exec_module(dg)
        a = dg.audit()
        _add("禁交付 0", a["禁交付"] == 0, "%d 个能力位禁交付" % a["禁交付"],
             "py -3.14 -X utf8 -m gbt_allinone.delivery_gate audit")
    except Exception as exc:                                 # noqa: BLE001
        _add("禁交付 0", False, "交付闸读不动：%s" % exc, "见 delivery_gate")

    # ③ 未闭合动作
    try:
        rows = []
        p = R / "state" / "action-ledger.jsonl"
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rows.append(_json.loads(line))
                except ValueError:
                    continue
        openx = [r for r in rows if not r.get("closed")]
        _add("未闭合动作 0", not openx, "%d 条未闭合" % len(openx),
             "py -3.14 -X utf8 tools/codex-scripts/action-ledger.py boot")
    except OSError as exc:
        _add("未闭合动作 0", False, "台账读不动：%s" % exc, "见 action-ledger")

    # ④⑤ live 时现跑（默认跑；跑不动按**没绿**处理，不许念成过）
    if live:
        try:
            cp = _sp.run([sys.executable, "-X", "utf8", "-m",
                          "gbt_allinone.tools.framework_gate", "verify"],
                         capture_output=True, cwd=str(R), timeout=300)
            j = _json.loads((cp.stdout or b"").decode("utf-8", "replace"))
            _add("框架门 green", j.get("verdict") == "green",
                 "verdict=%s · 红 %d" % (j.get("verdict"), len(j.get("findings") or [])),
                 "py -3.14 -X utf8 -m gbt_allinone.tools.framework_gate verify")
        except Exception as exc:                             # noqa: BLE001
            _add("框架门 green", False, "门跑不动：%s" % exc, "见 framework_gate")
        try:
            cp = _sp.run([sys.executable, "-X", "utf8",
                          str(R / "tools" / "codex-scripts" / "blueprint-check.py")],
                         capture_output=True, cwd=str(R), timeout=600)
            ok = cp.returncode == 0
            _add("四层蓝图 PASS", ok, "rc=%d" % cp.returncode,
                 "py -3.14 -X utf8 tools/codex-scripts/blueprint-check.py")
        except Exception as exc:                             # noqa: BLE001
            _add("四层蓝图 PASS", False, "蓝图判据跑不动：%s" % exc, "见 blueprint-check.py")

    bad_items = [i for i in items if not i["绿"]]
    return {"完善": not bad_items, "未完善项": bad_items, "逐项": items,
            "口径": "**整体没完善就不停工**（主人令 2026-10-09）；唯一例外=主人明确喊停",
            "未完善就不许停的理由": ("整体完善度是**五处现读**算出来的：报警/禁交付/未闭合/门/蓝图。"
                                     "任一处不绿 ⇒ 接着干，干到全绿为止。") if bad_items else ""}


def stop_rule() -> dict:
    return {"规则": "停下只有两种理由：① 部署完成（带证据）② 真正需要主人授权的危险动作",
            "两种理由": [dict(x) for x in STOP_KINDS],
            "不许停的理由": list(BANNED_STOP_REASONS),
            "来源": "主人令 2026-10-09（「其他时候你停下干嘛我问你？」）"}


# ── 验收闸：**必须亲自调用跑通闭环**（主人令 2026-10-10）────────────────────
# 主人原话：「给她一个**永远别去猜**和**跑测试**，必须**亲自调用跑闭环**才算合格验收」。
# 落地成两条硬判据（都能机检）：
#   ① **不许猜**：结论里出现「大概/可能/应该/估计/推测/似乎/按理」这类词 ⇒ 不算验收（那是猜）；
#   ② **跑测试 ≠ 验收**：只写「测试通过 / pytest 过了」⇒ 不算 —— 单元测试证的是代码分支，
#      证不了"这个能力真能干活"。**必须**给出**真调用**读数（走过唯一门 run_task 的那次调用）+
#      **闭环结论**（它到底做成了什么，或被如实拒/要参数——都要有读数）。
GUESS_WORDS: tuple = ("大概", "可能", "应该", "估计", "推测", "似乎", "按理", "也许", "差不多",
                      "估计是", "我认为")
ACCEPT_CALL_MARK: tuple = ("run_task", "cap ", "five-dim.py cap", "通 ", "=> ", "→ ")
ACCEPT_LOOP_MARK: tuple = ("闭环", "通 ", "如实否", "如实拒", "要参数", "缺依赖", "真坏",
                           "结果", "落盘", "产物", "读数")


def check_acceptance(evidence: str) -> dict:
    """**验收闸**：这段"验收证据"够不够格？

    三件缺一不可：① 真调用（有那次调用的读数）② 闭环结论（做成了什么 / 被如实拒）③ 没有猜词。
    """
    t = str(evidence or "")
    guess = [w for w in GUESS_WORDS if w in t]
    has_call = any(m in t for m in ACCEPT_CALL_MARK)
    has_loop = any(m in t for m in ACCEPT_LOOP_MARK)
    only_test = (("测试通过" in t or "pytest" in t or "test passed" in t or "全过" in t)
                 and not has_call)
    if guess:
        return {"合格": False, "命中猜词": guess[:3],
                "为什么": "**不许猜**：先把那次调用真跑一遍，拿读数来（主人令 2026-10-10）"}
    if only_test:
        return {"合格": False, "为什么": "**跑测试 ≠ 验收**：单元测试证代码分支，证不了这能力真能干活 ⇒ "
                                        "必须给**真调用**读数（走唯一门 run_task 的那次）+ 闭环结论"}
    if not has_call:
        return {"合格": False, "为什么": "没有**真调用**读数 ⇒ 不算验收（要那次调用过门的读数）"}
    if not has_loop:
        return {"合格": False, "为什么": "没有**闭环结论** ⇒ 不算验收（做成了什么 / 被如实拒，都要写清）"}
    return {"合格": True, "口径": "有真调用读数 + 闭环结论 + 无猜词 ⇒ 这项算验收过",
            "来源": "主人令 2026-10-10「永远别去猜和跑测试，必须亲自调用跑闭环才算合格验收」"}


def acceptance_rule() -> dict:
    return {"规则": "**不许猜**；**跑测试 ≠ 验收**；必须**亲自调用跑通闭环**才算合格验收",
            "三件": ["① 真调用读数（走唯一门 run_task 的那次）",
                     "② 闭环结论（做成了什么 / 被如实拒，都要有读数）",
                     "③ 无猜词"],
            "禁词": list(GUESS_WORDS),
            "来源": "主人令 2026-10-10"}


def doctrine() -> dict:
    return {"铁律": "能自动就自动；只有危险动作才停人要授权；**不许把活推回给用户**",
            "危险清单（唯一停点）": [{"类": d["类"], "作用域": d["作用域"],
                                      "例子": list(d["例子"]), "为什么": d["为什么"]}
                                     for d in DANGEROUS],
            "禁句（开放式甩锅）": list(BANNED_OPENERS),
            "禁句（敷衍报警）": list(BANNED_DISMISSALS),
            "停点规则": stop_rule(),
            "允许的停法": list(ALLOWED_STOP_FORM),
            "口径": "清单外一律自动执行；停下时**必须给具体选项与一键默认**，不许开放式提问",
            "来源": "主人令 2026-10-09（大众要便捷；不懂的用户连怎么启动你都不知道）· 移植自 V9 core/ux_doctrine.py"}


def run(op: str = "doctrine", **kw) -> dict:
    op = str(op or "doctrine").lower()
    if op == "doctrine":
        return {"ok": True, "op": "doctrine", **doctrine()}
    if op == "ask":
        return dict({"op": "ask"}, **check_ask(str(kw.get("text") or ""),
                                               acted=bool(kw.get("acted", True))))
    if op == "dismissal":
        return dict({"op": "dismissal"}, **check_dismissal(str(kw.get("text") or "")))
    if op == "owner":
        return dict({"op": "owner"}, **needs_owner(str(kw.get("label") or "")))
    if op == "triage":
        return dict({"op": "triage"}, **triage(kw.get("items") or []))
    if op == "stop":
        return dict({"op": "stop"}, **check_stop(
            str(kw.get("reason") or ""), kind=str(kw.get("kind") or ""),
            evidence=str(kw.get("evidence") or ""), danger_class=str(kw.get("danger_class") or ""),
            live=bool(kw.get("live", True))))
    if op == "complete":
        return dict({"op": "complete"}, **completeness(live=bool(kw.get("live", True))))
    if op == "owner_stop":
        return dict({"op": "owner_stop"}, **honor_owner_stop(str(kw.get("text") or "")))
    if op == "stop_rule":
        return {"ok": True, "op": "stop_rule", **stop_rule()}
    if op == "accept":
        return dict({"op": "accept"}, **check_acceptance(str(kw.get("evidence") or "")))
    if op == "accept_rule":
        return {"ok": True, "op": "accept_rule", **acceptance_rule()}
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["doctrine", "ask", "dismissal", "owner", "triage", "stop", "stop_rule",
                      "complete", "owner_stop", "accept", "accept_rule"]}
