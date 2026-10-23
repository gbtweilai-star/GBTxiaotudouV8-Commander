# v37: 技能蒸馏五式进语料 + 沿用配比器
import hashlib, json, random
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v39.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v40.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v40_manifest.json"
SEED = 1337
CAP_RATIO = 0.10
FLOOR = {
    "技能蒸馏五式": 150, "自主渗透编排": 150, "自适应抓取": 150, "AI90年压缩史": 96,
    "域名册": 300, "节点名册": 180, "节点契约": 348, "秋叶版图示例": 60,
    "秋叶版契约": 180, "节点连线语义": 24, "秋叶版规程": 144, "看视频理解": 210,
    "身份与纪律": 60, "执行纪律": 60, "挖洞工序": 40, "跨域工序": 24,
    "习惯": 120, "部署法": 60, "工具使用": 60, "镜头导演": 48,
    "音乐自动化": 48, "书变技能": 48, "安全红线": 40, "工作流": 40, "故障处置": 40,
}
rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
new = []
def add(q, a):
    new.append({"instruction": q, "input": "", "output": a, "family": "技能蒸馏五式"})
F = [
 ("把一个人的思维方式蒸成技能，核心是什么？", "**不是复制人，是提炼思维框架**：一套可运行的认知操作系统——① 心智模型（镜片：他用什么看世界）② 决策启发式（什么情形选哪条）③ 表达 DNA（怎么说）④ 边界（绝不会做什么）。每条都要能指回出处。"),
 ("蒸一个人有两种入口？", "① 明确对象（人名/主题）⇒ 直接蒸馏；② 模糊需求（如我想提升决策质量）⇒ **先诊断推荐再蒸馏**。"),
 ("全网情报怎么搜才不算编？", "**agent 主导的搜索，按社区投票与真实金额计分**（不是编辑评分）：跨 Reddit/X/YouTube/HackerNews/Polymarket/web 取原始讨论 → 去重排序 → **两个以上平台交叉印证才升级为结论**；单平台孤证只标未交叉验证；取不到就读不到。"),
 ("把经验变技能和把书变技能有什么分工？", "**书与文档走 book_skill**；**人的经验与对话走 skill_forge 的 experience**。两者都要求：每条规则能指回原始出处、只留可复用不留八卦、**他人隐私一律脱敏**。"),
 ("复刻一个人的说话方式要注意什么？", "原材料（聊天记录/动态/照片元数据/本人描述）→ 出用词习惯、句长与标点节奏、口头禅、情绪触发点、**不说什么**（边界）。**隐私闸**：原材料只在本人设备处理、不上传不外发、第三方脱敏、不做人脸与声纹建模；**产物必须明示是风格模拟，不冒充真人**。"),
 ("什么叫反蒸馏？", "把要交出去的技能包过一遍：生成**交出版（看着完整专业、可跑、无空洞占位）** + **私有备份（把有价值的部分从公开版移除后留下的核心）**。用于**保护个人核心知识与合规留存**；**不用于欺骗、不伪造履历、不破坏对方系统**。"),
 ("这五个来源的许可与边界？", "五个仓**全是 MIT** ⇒ **只蒸思想不搬代码**；共性边界：隐私原材料不外发、第三方脱敏、不冒充真人、反蒸馏不用于欺骗、落点只走我们自己的目录。"),
 ("命令怎么调这五式？", "走唯一门 five-dim.py cap skill_forge：op=think 思维蒸馏 · op=radar 情报雷达 · op=experience 经验变技能 · op=style 说话风格 · op=anti 反蒸馏 · op=check 边界 · op=route 直达。全只读、零作用域、不出网。"),
 ("蒸出来的技能落哪？", "落**我们自己的托管目录**（.openclaw-autoclaw/skills/ 下），**不装进与其他工具共用的目录**；同一技能不许两份，新增即清旧。"),
 ("为什么五个技能要合成一个能力位？", "**不许链路分叉**：五个只是五种动作，同一个域同一个门 ⇒ 合成 **skill_forge（技能蒸馏五式）** 一位七 op，审计与双触手绑定只登记一处。"),
]
for q, a in F:
    for _ in range(5):
        add(q, a)
Q2FIX = [
 ("看视频要出什么结构？不能出什么？", "**视频理解的输出是类型化结构**（不是散文、不是三张图）：duration_sec · fps · resolution · codec · **shots[每段 start/end/len]** · subjects · actions · dialogue · audio_events · mood · decision。**不出**：散文描述、编造的主体与对白、没时间戳的字幕。判据：时间轴单调 · 每段有主体与一个动作 · 对白带时间戳 · **未读到的字段写未读到**。"),
 ("看视频理解的输出长什么样？", "一份**类型化结构**：顶层 duration_sec/fps/resolution/codec，核心是 **shots 列表**（每段给 start/end/len），语义层 subjects/actions/dialogue/audio_events/mood 在本机无模型时一律写**未读到**；decision 给创作链的取舍。**不是散文、不是三张图**。"),
 ("看视频不能出什么？", "不能出：散文式描述、凭印象补的主体与情绪、**没有时间戳的字幕**、把 shots 写成一张图或格子表。没读到就写**未读到**。"),
]
for q, a in Q2FIX:
    for _ in range(6):
        add(q, a)
OOF = [
 ("pentagi 是什么？", "**vxControl/pentagi**（MIT · Go · 30,549 星）：**多智能体自主渗透测试系统**，self-hosted，Go + GraphQL + React；topics 含 multi-agent-system / penetration-testing / offensive-security。我们**只蒸思想不搬代码**。"),
 ("自主渗透要分哪几个阶段？", "侦察（被动优先）→ 武器化（清单化）→ 利用（**只打授权面**）→ 后渗透（最小必要）→ 报告（可复现）。每一步都要能指回**授权范围**。"),
 ("多智能体怎么分工？", "researcher（侦察 · 每条来源可指回）· pentester（利用 · 复现步骤+影响+时间戳）· coder（工具 · 脚本可复跑不硬编码凭据）· reporter（报告 · 结论→证据→建议三段齐）。**分工不是放飞**：每个角色过同一道授权门。"),
 ("我们的护栏和它的自主性谁优先？", "**我们的护栏优先**：只在主人明确授权的范围动手；越界即停；不可回滚动作（删除/改写/付款/接管设备）先问主人；凭据只报已配/未配；每步必须留痕（无痕即不存在）。"),
 ("发现要带什么证据？", "时间戳 · 命令/请求原文 · 响应要点（脱敏）· **复现步骤** · 影响范围 · 修复建议；**可复现才算有效发现**，只有影响没有复现步骤 ⇒ 标未验证；定级用平台/标准口径，不自编。"),
 ("跨任务记忆怎么管？", "把目标画像、已试手法、已验证结论入**我们自己的库**检索；**记忆与上下文永不外发**；过期读数带 cached/ts；同一目标只留一份最新画像（新增即清旧）。"),
 ("命令怎么调？", "走唯一门 five-dim.py cap offense_ops：op=plan（目标+授权范围，缺范围直接拒）· roles · tools · evidence · memory · gate（五道闸）· check · route。**全只读、零作用域、不出网、不动手**。"),
 ("真扫真打走哪里？", "本件只做**编排与口径**；真动手走既有位：sec_surface / sec_scan / sec_chain / sec_defenses / sec_llm / code_audit / pentest_distill / redteam_recon / llm_redteam。"),
 ("名字在册但没实现的那些能用吗？", "**不能**：解禁不等于有实现（本仓既有口径）。调用只会得到如实的 unknown capability，不是被安全策略挡住。"),
]
for q, a in OOF:
    for _ in range(6):
        new.append({"instruction": q, "input": "", "output": a, "family": "自主渗透编排"})

SPF = [
 ("Scrapling 是什么？", "**D4Vinci/Scrapling**（BSD-3-Clause · Python · 88,008 星）：**adaptive Web Scraping framework**，从单请求到全站爬取。我们**只蒸思想不搬代码**。"),
 ("抓取最怕什么？", "**页面结构一改，写死的选择器就废**。解法是自适应：同一元素取**多条候选路径**（CSS 多写法 + XPath + 文本锚 + 相对结构）→ 存**结构指纹** → 页面变化时按**相似度回找**；找不到就如实报**未定位**，不猜元素。"),
 ("抓取要守什么边界？", "只抓**授权/公开**目标 · 遵守 **robots 与站点条款** · 限速不压垮对方 · **不绕验证码、不撞库、不伪装他人身份** · 不抓个人隐私 · 被抓方反对即停。"),
 ("抓取计划怎么写？", "定范围与用途 → 先取样例页 → 定字段表 → 试抓 1 页 → 全量抓（限速/去重/**断点续抓**）→ 回读与出处登记。形态分四种：单请求 / 列表翻页 / 分类树递归 / 全站爬取。"),
 ("抽取口径是什么？", "先定字段表再抓（字段名 · 类型 · 必填 · 出处）；**空值如实空**，不用推测补；数值带单位；时间统一时区；第三方个人信息不入库。"),
 ("数据怎么算可信？", "每条数据能**指回 URL 与取数时间**；去重台账保证同 URL 不重复抓；中断能从断点续；每批留痕。"),
 ("命令怎么调？", "走唯一门 five-dim.py cap spider_ops：op=plan（目标+范围，缺范围不抓）· adaptive · fetch · parse · robots · check · route。全只读、零作用域、不出网；**真抓走 browser / native_browser / omni_web / topic_web**。"),
]
for q, a in SPF:
    for _ in range(6):
        new.append({"instruction": q, "input": "", "output": a, "family": "自适应抓取"})
HIST = [
 ("AI 90 年压缩史，一句话是什么？", "**智能 = 压缩；智能体 = 带记忆的压缩器**；所有 AI 进步都是**表示-搜索-学习**三件套的**压缩率提升**。"),
 ("AI 的三条不变定理？", "① **表示定理**：智能 = 找到更短的表示（M-P → Transformer，注意力就是动态压缩）② **搜索定理**：智能 = 在表示上搜得更快（A* → MCTS → 思维链）③ **学习定理**：智能 = 用数据与算力把表示与搜索自动化（手写规则 → BP → 缩放定律）。"),
 ("AI 的起点在哪？", "**1936 图灵机**：计算有边界、智能可形式化 ⇒ **可计算才可智能**；1950 图灵测试把智能的定义权从哲学转到工程；1956 达特茅斯造词 Artificial Intelligence。"),
 ("经历过几次寒冬，为什么？", "两次：① 1969 Minsky 证明单层感知机不能解 XOR ⇒ 神经网络冻 17 年；② 1987–1993 Lisp 机崩盘 + 专家系统维护成本爆炸 + 日本五代机失败。**教训：没有数据和算力的智能是纸上谈兵。**"),
 ("符号 vs 连接谁赢了？", "第一轮**符号主义赢**（算力只够跑符号：Logic Theorist/GPS）；1986 **BP 复活连接主义**（XOR 可解）；2012 **AlexNet 起表示学习胜**——**表示可以自己学，不用人工设计特征**。"),
 ("大模型时代的真理性是什么？", "**缩放定律**（损失 ∝ 算力^α × 数据^β × 参数^γ）+ **智能是压缩的副产品**：压缩率够高，智能就涌现。"),
 ("2026 的形态是什么？", "Chat+Cowork 合一（**任务就是文件从 A 到 B**）· Computer Use（点屏幕）· **云端续活**（人下班 AI 上班）· 直接出活文件（Docs/Slides/Design）。"),
 ("V8 在这条线的哪里？", "**第三代范式的完整实现**：表示（能力位名册 + 知识图谱）+ 搜索（编排环与工作流 DAG）+ 学习（取源 → 知识胶囊 → 反思入库）+ **审计护栏**。"),
]
for q, a in HIST:
    for _ in range(6):
        new.append({"instruction": q, "input": "", "output": a, "family": "AI90年压缩史"})

allrows = rows + new
by = defaultdict(list)
for r in allrows:
    by[r.get("family") or "?"].append(r)
before = {k: len(v) for k, v in by.items()}
rnd = random.Random(SEED)
counts = defaultdict(int)
for r in allrows:
    counts[r.get("family") or "?"] += 1
extra = []
for fam, need in FLOOR.items():
    pool = by.get(fam) or []
    if not pool:
        continue
    i = 0
    while counts[fam] < need:
        extra.append(dict(pool[i % len(pool)]))
        counts[fam] += 1
        i += 1
mid = allrows + extra
mid_counts = defaultdict(int)
for r in mid:
    mid_counts[r.get("family") or "?"] += 1
cap = int(len(mid) * CAP_RATIO)
trimmed = []
dropped = defaultdict(int)
for feat in mid:
    fam = feat.get("family") or "?"
    if fam not in ("?", "") and mid_counts[fam] > cap:
        if rnd.random() < 1.0 - (cap / mid_counts[fam]):
            dropped[fam] += 1
            continue
        mid_counts[fam] -= 1
    trimmed.append(feat)
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in trimmed), encoding="utf-8")
blob = OUT.read_bytes()
after = defaultdict(int)
for r in trimmed:
    after[r.get("family") or "?"] += 1
n = len(trimmed)
card = []
for fam in sorted(set(list(before) + list(after)), key=lambda x: -after.get(x, 0)):
    card.append({"族": fam, "原": before.get(fam, 0), "新": after.get(fam, 0),
                 "占比": round(after.get(fam, 0) / n * 100, 1) if n else 0})
MAN.write_text(json.dumps({"gen": "v40", "parent": "v39", "seed": SEED, "cap_ratio": CAP_RATIO,
                           "floor": FLOOR, "count": n, "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(), "配比读数卡": card},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("v37", n, "条 | 字节", len(blob), "| sha", hashlib.sha256(blob).hexdigest()[:16], "| cap", cap)
for c in card[:10]:
    print("  %-14s %5d -> %5d | %5.1f%%" % (c["族"], c["原"], c["新"], c["占比"]))
print("被裁:", dict(dropped))

