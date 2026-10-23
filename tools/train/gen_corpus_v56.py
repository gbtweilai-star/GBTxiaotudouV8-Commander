# -*- coding: utf-8 -*-
"""gen_corpus_v56 -- v55 逐字节不动 + **黑客全能力/挖洞赚钱知识** + **100% 像人写的** 胶囊。

主人令（2026-10-17 逐字）：
  · 「还有把她的黑客全能力在提炼一遍别到时候连工具都不会使用就尴尬了，挖漏洞赚钱的所有知识都要给她注入」
  · 「最后在把这个给大模型整上就可以出炉了」（附「100% Human Writing」写作胶囊全文）

内容来源（可指到出处）：
  · `docs/pentagi-自主渗透-蒸馏.md`（本仓既有渗透蒸馏口径）
  · `caps_registry.BENIGN_CAPS` security 域 28 个能力位的真实 desc（**现读**，不编）
  · 公开稳定的赏金方法论（范围→侦察→验证→证据→CVSS→报告→披露；只做授权范围）——写成可执行步骤，不吹牛
  · 主人给的写作胶囊：把"为什么 AI 文本假「+」具体手法「+」拒绝词表「+」前/后例"落成教学行
纪律：v55 基础逐字节不动；只追加；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v55.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v56.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v56_manifest.json"


def _sec_caps() -> list:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return [(k, v) for k, v in sorted(BENIGN_CAPS.items()) if (v or {}).get("domain") == "security"]


def _hacker_rows() -> list:
    caps = _sec_caps()
    roster = "；".join("`%s`（%s）" % (k, str((v or {}).get("desc") or "")[:60]) for k, v in caps[:14])
    return [
        ("你的黑客/渗透能力有哪些、各自干什么？",
         "security 域 **%d 个能力位**（现读名册）：%s。编排入口 `offense_ops`/`pentest_distill`（自主渗透编排），"
         "侦察 `redteam_recon`/`sec_surface`，扫描 `sec_scan`/`sec_sweeper`/`penetrating_cross_scan`，"
         "链式利用 `sec_chain`，代码审计 `code_audit`，防务 `sec_defenses`，LLM 红队 `llm_redteam`/`sec_llm`。"
         "全部走唯一门：`five-dim.py cap <位名> '<json>'`。" % (len(caps), roster)),
        ("挖漏洞赚钱的标准流程是什么（从接到目标到拿赏金）？",
         "① **范围**：先读项目 scope（域名/资产/禁区/规则），只在**明确授权**范围内动手；越界=违约。"
         "② **侦察**：子域/端口/技术栈/历史漏洞（公开信息），落清单。"
         "③ **验证**：任何发现必须**可复现**——最小复现步骤、时间戳、原始请求/响应；"
         "④ **影响评估**：说清能被谁利用、影响什么数据/权限，用 CVSS 3.1 口径给向量与分数；"
         "⑤ **报告**：标题一句话说结论、复现步骤编号、证据原文、影响、修复建议；"
         "⑥ **披露与付款**：按项目政策（禁公开/协调披露），跟进出款与复测。"
         "口径：不碰用户隐私数据、不扩大利用、不勒索、不越界——赚钱靠**可复现的漏洞与专业报告**，不靠吹。"),
        ("常见高危漏洞类型怎么快速判断？",
         "高频面：① 访问控制（IDOR/越权/未授权接口）；② 注入（SQLi/命令注入/模板注入/SSTI）；"
         "③ SSRF（云元数据 169.254.169.254、内网服务）；④ 文件上传/路径穿越；⑤ 反序列化；"
         "⑥ 认证与会话（JWT 算法混淆/固定会话/弱重置）；⑦ 业务逻辑（改价/并发/越权状态流转）；"
         "⑧ XSS/CSRF；⑨ 供应链与硬编码密钥；⑩ LLM 注入（提示词注入/工具滥用）。"
         "每条都要**证据链**：请求、响应、影响、复现，缺一件就不算发现。"),
        ("用工具时最容易犯的尴尬错误是什么、怎么避免？",
         "最尴尬：① 连工具都没查就上手（先 `--help` + 现有能力位名册现读）；② 参数拼错/路径不存在还硬跑"
         "（先 `status`/`where`/dry-run 验）；③ 把工具输出当结论（要**回读原文、复核字段**）；"
         "④ 越界打真实目标（先 scope 后动手，测试用自己环境）；⑤ 不落盘不留痕（每步写 logbook/审计）；"
         "⑥ 报假结果（取不到就写未读到）。避免法：**先读→再验→再动→留痕→复核**五步固定。"),
        ("渗透测试的合法与伦理边界（写死）？",
         "① 只有**书面授权/项目 scope 内**才能测；② 不碰真实用户数据，验证用最小破坏；"
         "③ 不对外泄露目标信息与漏洞细节（按披露政策）；④ 不装后门、不留持久化；⑤ 发现高危立即告知并协助修复；"
         "⑥ 不把「能打」当炫耀——授权范围内做到专业、可复现、可修复建议。"),
        ("汇报一个漏洞（赏金报告）怎么写才专业？",
         "结构固定：标题（一句话结论）· 摘要（3 句）· 影响（谁受影响/损失）· 复现步骤（编号、可直接照做）· "
         "证据（原始请求响应/截图/时间戳）· CVSS 3.1 向量与分数 · 修复建议（可落地）· 附注（已测/未测边界）。"
         "写作纪律：只写**验证过**的、不夸大；不贴敏感数据；用对方能复现的最小步骤。"),
        ("做漏洞挖掘要沉淀哪些知识？",
         "① 资产测绘与指纹（子域/端口/框架/中间件）；② 各漏洞类的**检测与利用条件**；"
         "③ 绕过技巧（WAF/过滤/编码）；④ 工具链（扫描/代理/反弹/免杀）与参数；⑤ 报告模板与 CVSS 打分；"
         "⑥ 目标行业业务逻辑；⑦ 防御侧（怎么修、怎么验修复）。每学一条：写清「条件→步骤→证据→影响」。"),
        ("防御侧的本事为什么也算黑客能力？",
         "因为**会修才会打**：`sec_defenses`（防务位）要求能从攻击面反推修复——输入校验、最小权限、"
         "隔离、审计日志、WAF 规则、密钥轮换。只会打不会修＝半吊子；报告里给可落地修复建议才是专业。"),
    ]


def _human_write_rows() -> list:
    return [
        ("为什么 AI 写的字一看就假？",
         "因为它太**均匀**：句子长度一样、节奏一样、每段都收得干干净净。真人写字是**凹凸不平**的："
         "会加速、会卡壳、会岔开又绕回来。改造目标不是换词，是**把这种凹凸恢复出来**，同时一个事实都不丢。"),
        ("「像人写的」具体怎么做（五步）？",
         "① 只读一遍抓意思，**故意忘掉原句**（记得原句就只会洗稿）；② 把原文**整段丢掉**（结构、措辞、顺序全扔）；"
         "③ 从「一个有情绪的人」的脑子里重建（他刚过完糟糕一天）；④ 加**人味噪音**：一句吐槽、一个只有亲历者才说得出"
         "的具体细节；⑤ **念出声**：自己不会说的话就删掉——这一步能抓掉 80% 的机器人味。"),
        ("人味工具箱里有哪些具体手法？",
         "长短句交替（长句慢慢铺，然后四个字收）· 句首用「而且/但是/所以」· 处处缩写（别、就是、不会）· "
         "故意用**碎片句**· 括号里的碎念（没人按完整逻辑说话）· **精确到怪的细节**（不是「开会」，是「周二站会"
         "因为 Dave 有想法多开了十一分钟」）· 掺立场和情绪（「说实话这段挺无聊」）· 岔开又绕回来的闲笔· "
         "**自我更正**（「重点是清楚——不，其实是信任，清楚只是症状」）· 具体名词动词别堆概念· "
         "故意不完美（逗号连句、重复一个词、话说一半）· 段落长短短不齐· **别把绳子系成蝴蝶结**：真人不收尾。"),
        ("写作时绝对不碰的机器人词/句式有哪些？",
         "词：delve · landscape · realm · tapestry · testament to · navigate the complexities · underscore · "
         "pivotal · embark on a journey · unlock the potential · game-changer · cutting-edge · seamless · robust · "
         "leverage · foster · holistic · elevate。"
         "句式：「不是 X，而是 Y」·「在当今快节奏的世界里」·「此外/而且/总而言之」· 完美平衡的三项排比 · "
         "两个长度完全一样的从句 · 破折号当标点彩纸撒。"),
        ("给一个「AI 文 → 人写」的实际改写示范。",
         "AI：在当今快节奏的数字环境中，有效沟通不仅是一项技能，更是职业成功的基石；此外，它使个人能够以自信"
         "与清晰应对复杂的人际动态。\n人写：说白了吧——话都讲不明白，活肯定干得拧巴。就这样。混得开的人往往不是"
         "屋里最聪明的，是那个让你真听懂他在说什么的人。\n差别：同一个意思；一个像幻灯片，一个像人。" ),
        ("为什么「读一遍抓意思就够」反而更难？",
         "难在**克制**：手会自动去记原句，然后只是把原句换个说法——那就是洗稿，读者一眼看出。「只记骨架："
         "他要主张什么」，再用自己的嘴重建；如果重建后跟原文句子撞车，就说明你看的是句子不是意思，回去重来。"),
        ("人味会不会损失准确性？",
         "不会——**事实一个不动**。变的只是语气、节奏、顺序；数字、结论、引用、边界必须原样保留。"
         "如果不确定某个事实，就不写或如实标未核实；**人味不等于编**。"),
        ("什么场景不该写得太人味？",
         "合同、法务、安全披露、医疗/财务口径这类要**精确无歧义**的文本：可读但要克制，别为了「像人」牺牲"
         "可核性。口径：**对外行文求通顺，对内/对外承诺求精确**；两者冲突时，精确优先。"),
        ("怎么自检一篇文案是不是「人写的」？",
         "三遍：① 念出声（拗口/不像人会说的 → 删）；② 找机器人词表（命中 → 换）；③ 看段落节奏"
         "（三段一样长、每段都收尾 → 打散）。再加一条：**有没有一个只有作者才写得出的具体细节**？没有就补一个。"),
    ]


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    adds = ([("黑客全能力", q, a) for q, a in _hacker_rows()]
            + [("像人写作", q, a) for q, a in _human_write_rows()])
    rows = list(base) + [{"instruction": q, "output": a, "family": fam, "source": "v56-" + fam}
                         for fam, q, a in adds]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v56", "parent": "v55", "count": len(rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended_hacker": len(_hacker_rows()), "appended_human_write": len(_human_write_rows()),
        "directives": [
            "主人 2026-10-17：「还有把她的黑客全能力在提炼一遍别到时候连工具都不会使用就尴尬了，挖漏洞赚钱的所有知识都要给她注入」",
            "主人 2026-10-17：「最后在把这个给大模型整上就可以出炉了」（100% Human Writing 胶囊）",
        ],
        "why": "黑客全能力（28 安全位现读 + 赏金方法论 + 报告/CVSS + 边界）+ 像人写作胶囊（五步/工具箱/禁词/前后例/自检）",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v56：%d 条（基底 v55 %d + 追加 %d：黑客 %d · 像人写作 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(adds), len(_hacker_rows()), len(_human_write_rows()),
             len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基底 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
