# -*- coding: utf-8 -*-
"""护栏审查 · **框架只有三道护栏**（主人令 2026-10-10，逐字）

主人原话：
  「整个框架只有三个护栏，第一就是黑客全能力使用要人工授权，第二是付款需要人工授权，
    第三就是镜像多维度空间可以跑任何东西，唯独不是生成代码禁止入生产面板。」

## 本件要解决的**真问题**：政策层说"三道"，机制层却有 14 个作用域
policy.py 的 SCOPE_DESCRIPTIONS 是**机制层**（哪些动作要过门）；
主人的三道是**政策层**（为什么要人管）。两者不是一个层级，**不能硬塞**。
⇒ 本件做的是：**逐条分类、归不进去的列出来请主人裁定** —— 不静默通过，也不替主人归类。

## 判据（**四档**，牙齿长在「有没有人给它归过类」上）
  🔴 **本件 2026-10-10 第二版自纠**：第一版把「归不进三道」直接写成「**疑似第四道护栏**」——
     这个设计**不对**：「护栏」与「作用域」本来就不是一个层级。
     主人说的是**政策层的三道护栏**；而 policy.py 里的是**机制层的作用域**。
     ⇒ 正解是把分类**列全**（四档），让判据的牙齿长在
        **「有没有人给它归过类」**上，而不是长在「必须塞进三道」上。

  ① 三护栏之一        ⇒ 记名下（政策层：为什么要人管）
  ② **通道件**        ⇒ 不是护栏（它是授权本身，或只读）
  ③ **自我保护机制**  ⇒ 机制层的门，**性质是机制不是政策**（见下）。**主人令 2026-10-10 逐字：
        「那这是自我保护机制**不能删**啊」** ⇒ 它**留着**，只是不塞进政策层的三道。
  ④ **没归过类**      ⇒ 🔴 **红** —— 那才是真有了一道没人交代过的门

  ⇒ **三护栏缺失**也红：某一道在机制层完全没有对应实现 = 说了护栏却没人把门。

## 负控（真植入）
  往作用域表里塞一个**假作用域** ⇒ 必须被点成「疑似第四道护栏」。

用法: py -3.14 -X utf8 tools/codex-scripts/guardrail-check.py [--selftest]
"""
import pathlib
import re
import sys

WS = pathlib.Path(__file__).resolve().parents[2]
POLICY = WS / "gbt_allinone" / "security" / "policy.py"

G1 = "① 黑客全能力使用 ⇒ 人工授权"
G2 = "② 付款 ⇒ 人工授权"
G3 = "③ 镜像空间可跑任何东西，唯独「生成代码」禁止入生产面板"

MAP = {
    "process_execute": (G1, "启动进程/执行命令 —— 攻击面的基础原语"),
    "remote_device":   (G1, "远程设备中继/外部接管通道 —— 就是接管本身"),
    "network_private": (G1, "本机/内网/保留地址/非标准端口 —— 攻击面的入口"),
    "privacy_read":    (G1, "屏幕/摄像头/麦克风 —— 黑客能力里的看与听"),
    # 2026-11-04 补：`osint_private` 一直**漏在分类表外**。
    #   它在 auth_gate.SCOPES 与 ENFORCED_SCOPES 里（2026-10-21 补的真门），
    #   但本件遍历的是 policy.SCOPE_DESCRIPTIONS，而它不在那张表里 ⇒ 判据根本看不见这道门。
    #   这次是「门与判据一致性」那条新牙齿把它抓出来的（自检当场红）。
    "osint_private":   (G1, "对私有网段做 OSINT 扫描 —— 内网探测，黑客行为"),
    "external_llm":    (G2, "发数据到外部大模型 —— 按量计费"),
    # 2026-11-04 补：`transfer` 是主人**明确点名**必须拿票的一条（「资金转账需要找我拿票」），
    #   但它此前只在 policy.HUMAN_GATES 里、**不在** ENFORCED_SCOPES ⇒ 机制层实际放行。
    #   这次由「门与判据一致性」那条牙齿抓出（自检当场红）。归 G2 资金类。
    "transfer":        (G2, "转账/付款 —— 钱不能让她自己拍（主人令：资金转账必须拿票）"),
    "data_export":     (G2, "数据出框架 —— 出网就可能计费，且发出去就收不回"),
    "deploy_publish":  (G3, "部署/晋升/回滚/写生产交付区 —— 生成代码禁入的就是这里"),
    "deploy_force":    (G3, "放行生产面那道闸（未全绿晋升 / 未声明落点 / 公网中继登记）——"
                            "第③道护栏的**专用钥匙**，单独一次性；有它才能越过体检结论，没它一个字都过不去"),
    "owner_control":   ("__通道件__", "主人总控授权 —— 它就是授权本身，不是第四道护栏"),
    "audit_read":      ("__通道件__", "读审计/授权/运行历史 —— 只读"),

    # ── 2026-11-04 口径翻正：这 4 条**移出票门**（主人令，逐字）──
    #   「不能有能力上的限制以及能力阉割，只要是技术能达到的地方都可以；
    #     危险能力和资金转账需要找我拿票，其他全面开放」
    #   判定标准：**只有「可能伤害主人之外的对象」或「不可逆/资金损失」才要票。**
    "browser_control": ("__自动放行__",
                        "操控浏览器点击/输入 —— 接管的是**主人自己的**会话；"
                        "它是 body_* 那批「设备即本体」能力位的底座，要票就等于把那批位阉割掉"),
    "desktop_control": ("__自动放行__",
                        "桌面触手：鼠标/键盘/窗口 —— 操作的是**主人自己的**本机；同上"),
    "device_control":  ("__自动放行__",
                        "蓝牙与外部设备 —— 主人自己的外设；同上"),
    "audio_output":    ("__自动放行__",
                        "TTS/发声 —— 本仓既定选择是 edge-tts（免费）/ 本地 SAPI 兜底，"
                        "不产生费用 ⇒ 不构成「付款」；留着要票只会让「说句话」被莫名拦住"),

    # ③ **常备门**：机制层的门，性质是**机制**不是政策 —— 它既不属三道，也不是"第四道护栏"。
    #      主人说的是**政策层的三道护栏**（为什么要人管）；而它是**机制层**的门
    #      （保的是"未经允许不改你的文件"）。它不花钱、不是攻击、也不决定上不上线 ⇒ 塞进三道是硬塞。
    #      但它**确实是道门**（实测：本会话做无主收纳时，正是它把"硬删"挡成"进回收站"）。
    # **主人令 2026-10-10 逐字裁定：「那这是自我保护机制不能删啊」** ⇒ 留着 + 归这档。
    # 2026-10-19 主人令「除了黑客全能力和转账要票其他都去掉」⇒ 它已**不在 ENFORCED_SCOPES**，
    #   即机制保留、票门撤掉。两件事不矛盾：机制是代码里的判断，票门是人工发授权。
    "filesystem_write": ("__自动放行__",
                         "通用写盘 —— **自我保护机制**（未经允许不改你的文件）保留在代码里，"
                         "但按 2026-10-19 主人令**不再要票**；性质是机制不是政策"),
}

# 已知归不进去的一条（如实写在文件里，不藏）：
#   filesystem_write = "写入、移动、删除或自动整理文件"
#   它既不是黑客能力、也不是付款、也不是生产面板 —— 而是**通用写盘**。
#   ⇒ 本件把它报成「疑似第四道护栏」，请主人裁定。
UNRESOLVED_HINT = {"filesystem_write": "通用写盘：不属黑客/付款/生产面板三道 —— 请主人裁定"}


def read_scopes(path=None):
    p = pathlib.Path(path or POLICY)
    src = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"SCOPE_DESCRIPTIONS\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return None, "读不到 SCOPE_DESCRIPTIONS"
    out = {}
    for line in m.group(1).splitlines():
        mm = re.match(r'\s*"([a-z_]+)"\s*:\s*"(.*?)"\s*,?\s*$', line)
        if mm:
            out[mm.group(1)] = mm.group(2)
    return out, ""


def enforced_scopes():
    """现读真门：auth_gate.ENFORCED_SCOPES。判据必须与门同源，不许各算各的。"""
    try:
        sys.path.insert(0, str(WS))
        from gbt_allinone.auth_gate import ENFORCED_SCOPES
        return set(ENFORCED_SCOPES), ""
    except Exception as exc:                                   # noqa: BLE001
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"


def audit(scopes):
    # 遍历范围 = policy 声明 ∪ 真门 ∪ auth_gate 注册表（**三者并集**）
    # 血账：原先只遍历 policy.SCOPE_DESCRIPTIONS，而 `osint_private` 在 auth_gate.SCOPES
    #   与 ENFORCED_SCOPES 里、**不在** policy 那张表里 ⇒ 这道真门对判据完全不可见
    #   （2026-11-04 由「门与判据一致性」新牙齿抓出）。少看一处，就等于少看一道门。
    names = dict(scopes or {})
    enf_pre, _e = enforced_scopes()
    for s in (enf_pre or set()):
        names.setdefault(s, "（在 ENFORCED_SCOPES 里、policy 表里没有 ⇒ 原先判据看不见）")
    try:
        sys.path.insert(0, str(WS))
        from gbt_allinone.auth_gate import SCOPES as _AG_SCOPES
        for s, d in _AG_SCOPES.items():
            names.setdefault(s, d)
    except Exception:                                          # noqa: BLE001
        pass

    covered = {G1: [], G2: [], G3: []}
    channels, standing, auto, unclassified = [], [], [], []
    for name, desc in sorted(names.items()):
        hit = MAP.get(name)
        if hit is None:
            # 真正该红的那一档：**没人给它归过类的门**
            unclassified.append({"作用域": name, "描述": desc,
                                 "为什么": UNRESOLVED_HINT.get(name, "**没人给它归过类** ⇒ 请交代它是什么")})
        elif hit[0] == "__通道件__":
            channels.append({"作用域": name, "描述": desc, "为什么不是护栏": hit[1]})
        elif hit[0] in ("__自动放行__", "__自我保护__"):
            (standing if hit[0] == "__自我保护__" else auto).append(
                {"作用域": name, "理由": hit[1]})
        else:
            covered[hit[0]].append({"作用域": name, "理由": hit[1]})

    missing = [g for g, v in covered.items() if not v]

    # ── 门与判据一致性（2026-11-04 新增的牙齿）──────────────────────────
    # 血账：门的集合在 auth_gate.py，分类表在本文件 —— 改了一边不改另一边，
    # 本件会照旧打印旧分类（实测：把 4 条移出票门后，本件仍报「① 黑客 7 条」）。
    # 这种「门和判据各算各的」比没有判据更坏。这里锁死：
    #   ① 归到三道里的作用域，必须**正好**是 ENFORCED_SCOPES；
    #   ② ENFORCED_SCOPES 里的每条，必须在本件归到三道之一（不能归到自动放行/通道件）。
    enf, err = enforced_scopes()
    drift = []
    if enf is None:
        drift.append(f"读不到 ENFORCED_SCOPES：{err}")
    else:
        claimed = {x["作用域"] for rows in covered.values() for x in rows}
        for s in sorted(claimed - enf):
            drift.append(f"{s} 在本件归到「护栏」，但不在 ENFORCED_SCOPES ⇒ 实际不要票")
        for s in sorted(enf - claimed):
            drift.append(f"{s} 在 ENFORCED_SCOPES 里，但本件没归到三道 ⇒ 判据看不见这道门")
        for x in auto:
            if x["作用域"] in enf:
                drift.append(f"{x['作用域']} 被归到「自动放行」，却在 ENFORCED_SCOPES 里 ⇒ 自相矛盾")

    return {"三护栏": covered, "通道件": channels, "自我保护机制": standing,
            "自动放行": auto, "没归过类": unclassified, "缺实现": missing,
            "门判一致": not drift, "漂移": drift}


def render(r):
    print("=" * 74)
    print("护栏审查 · 框架只有三道护栏（主人令 2026-10-10）")
    print("=" * 74)
    for g, rows in r["三护栏"].items():
        print("")
        print("%s  —— 机制层对应 %d 条" % (g, len(rows)))
        for x in rows:
            print("    %-18s %s" % (x["作用域"], x["理由"]))
    print("")
    print("🔓 自动放行（主人令 2026-11-04：其他全面开放）—— %d 条" % len(r["自动放行"]))
    for x in r["自动放行"]:
        print("    %-18s %s" % (x["作用域"], x["理由"]))
    print("")
    print("机制层通道件（不是护栏，是授权本身或只读）—— %d 条" % len(r["通道件"]))
    for x in r["通道件"]:
        print("    %-18s %s" % (x["作用域"], x["为什么不是护栏"]))
    if r["自我保护机制"]:
        print("")
        print("③ 自我保护机制（**机制层**的门，性质是机制不是政策 · **不能删**）—— %d 条"
              % len(r["自我保护机制"]))
        for x in r["自我保护机制"]:
            print("    %-18s %s" % (x["作用域"], x["理由"]))
    print("")
    if r["没归过类"]:
        print("🔴 **没归过类的门**（那才是真有了一道没人交代过的门）—— %d 条" % len(r["没归过类"]))
        for x in r["没归过类"]:
            print("    %-18s %s" % (x["作用域"], x["为什么"]))
    else:
        print("🔴 没归过类的门：**0 条** ✅（每个作用域都有人交代过它是什么）")
    print("")
    if r.get("门判一致"):
        print("🔒 门与判据一致：本件归到三道的，**正好**是 auth_gate.ENFORCED_SCOPES ✅")
    else:
        print("🔴 **门与判据漂移**（改了一边没改另一边，判据会照旧打印旧分类）：")
        for d in r.get("漂移") or []:
            print("    · " + d)
    if r["缺实现"]:
        print("")
        print("🔴 三护栏里在机制层完全没有对应实现的：%s" % " / ".join(r["缺实现"]))
    print("")


def selftest():
    ok = []
    real, err = read_scopes()
    if not real:
        print("  自检: " + err)
        return 2
    r = audit(real)
    ok.append(("真件·读到作用域表（非空）", len(real) > 5, "%d 条" % len(real)))
    ok.append(("真件·三护栏每道都有机制层实现", not r["缺实现"], "缺: %s" % (r["缺实现"] or "无")))
    ok.append(("真件·每个作用域都有人归过类（没归过类的 = 0）",
               not r["没归过类"], "没归过类: %s" % ([x["作用域"] for x in r["没归过类"]] or "无")))
    # 2026-11-04 口径翻正：filesystem_write 已按 2026-10-19 主人令**不再要票**，
    # 它现在归「自动放行」（机制留在代码里、票门撤掉）。原断言要求它属于「自我保护机制」，
    # 那条断言会永远红 —— 改成测真正该保的事：它在自动放行档、且不在 ENFORCED.
    ok.append(("真件·filesystem_write 归「自动放行」（机制保留、票门已撤）",
               any(x["作用域"] == "filesystem_write" for x in r["自动放行"]),
               "自动放行: %s" % [x["作用域"] for x in r["自动放行"]]))
    ok.append(("真件·**门与判据不许漂移**（本件归到三道的正好是 ENFORCED_SCOPES）",
               bool(r.get("门判一致")), "漂移: %s" % (r.get("漂移") or "无")))
 # 真植入负控：塞一个**没人归过类**的作用域 ⇒ 必须红
    planted = dict(real)
    planted["quantum_teleport"] = "凭空搬运 —— 不存在的能力"
    rp = audit(planted)
    ok.append(("真植入负控·塞一个没人归过类的门 ⇒ 必须红",
               any(x["作用域"] == "quantum_teleport" for x in rp["没归过类"]),
               "点名: %s" % [x["作用域"] for x in rp["没归过类"]][:4]))
 # 真植入负控（**改掉上一条假负控** —— 上一版只是把一条删掉，根本没测到东西）：
    #    塞一个**看着像已归类、其实没归类**的名字（filesystem_write_v2）⇒ 必须红。
    #    这条测的是**按名精确匹配**：若 MAP 用了子串匹配，它就会被错放行。
    planted2 = dict(real)
    planted2["filesystem_write_v2"] = "冒充已归类的门"
    rp2 = audit(planted2)
    ok.append(("真植入负控·塞一个**冒充已归类**的门（filesystem_write_v2）⇒ 必须红",
               any(x["作用域"] == "filesystem_write_v2" for x in rp2["没归过类"]),
               "没归过类: %s" % [x["作用域"] for x in rp2["没归过类"]][:4]))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-54s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("guardrail-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 0 if not bad else 1


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    scopes, err = read_scopes()
    if not scopes:
        print("读不到作用域表: " + err)
        return 2
    r = audit(scopes)
    render(r)
 # 牙齿：**没归过类的门** 或 **三护栏缺实现** ⇒ 红
    return 1 if (r["没归过类"] or r["缺实现"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
