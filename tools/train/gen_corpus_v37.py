# v37: 技能蒸馏五式进语料 + 沿用配比器
import hashlib, json, random
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v36.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v37.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v37_manifest.json"
SEED = 1337
CAP_RATIO = 0.10
FLOOR = {
    "技能蒸馏五式": 150,
    "域名册": 300, "节点名册": 180, "节点契约": 348, "秋叶版图示例": 60,
    "秋叶版契约": 180, "节点连线语义": 24, "秋叶版规程": 144, "看视频理解": 150,
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
MAN.write_text(json.dumps({"gen": "v37", "parent": "v36", "seed": SEED, "cap_ratio": CAP_RATIO,
                           "floor": FLOOR, "count": n, "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(), "配比读数卡": card},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("v37", n, "条 | 字节", len(blob), "| sha", hashlib.sha256(blob).hexdigest()[:16], "| cap", cap)
for c in card[:10]:
    print("  %-14s %5d -> %5d | %5.1f%%" % (c["族"], c["原"], c["新"], c["占比"]))
print("被裁:", dict(dropped))
