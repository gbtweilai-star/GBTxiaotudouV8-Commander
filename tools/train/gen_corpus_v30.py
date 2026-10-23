# v30 corpus: Seedance 2.0 Skill OS distilled into shot_director family
import hashlib, io, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v29.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v30.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v30_manifest.json"
base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
new = []
def add(q, a):
    new.append({"instruction": q, "input": "", "output": a, "family": "镜头导演"})
F = [
 ("视频模型到底是什么？",
  "视频模型 = **一个从没见过你的剧组**：不能提问 · **按字面渲染** · 只做它理解的**第一个**动作 · **跨镜头忘记光位与站位** · **不告诉它就不移镜**。所以要说**相机会记录的东西**，不说小说家说的话。"),
 ("习语直接写会怎样？",
  "会被**字面渲染**或**直接忽略**（脸沉下来 → 脸变灰）。改法：**感觉的一个普通词 + 一个物理锚** —— 他愣住，惊慌，眼睛盯着门口的她，喉结动了一下。"),
 ("一句提示词里能给几个动作？",
  "**一镜一动作**。给四个动作 ⇒ 模型只做**第一个**、丢掉其余。别人要照常生活（idle business），但**不许写保持不动**（会冻成人体模型）。"),
 ("反应怎么写？",
  "**感觉 + 一个物理锚**。写成**肌肉清单**（嘴角压下）会读成生闷气 ⇒ 要写：被当场问住，礼貌的笑收住了，他咽了一下。"),
 ("道具动作怎么写？",
  "写**一只手**在做什么（否则茶杯会被当酒瓶一样倒空）。"),
 ("每个镜头的收尾要写什么？",
  "写**锁定句**：复述**光 · 人 · 站位**。不写就会暖光两镜后变蓝、人已离开门口却还在门口说话。"),
 ("人物位置要重复写吗？",
  "要。**位置与地理每镜必须重述**；**走动必须写出来**，否则下一镜她会瞬移到杯边、主客门关系会反。"),
 ("结尾怎么写才到得了？",
  "结尾必须落在**本镜真实存在的构图**里；为这一镜没有的构图写的结尾**永远不到**。"),
 ("提示词和镜头表谁先？",
  "**镜头表（shot table）先于任何散文**。列：镜号 · 时长 · **一个动作** · 反应（感觉+物理锚）· 道具（一只手）· 光 · 人（谁在场、朝向）· 站位 · **锁定句**。"),
 ("多镜多人要注意什么？",
  "加**多镜语法**；人物位置、朝向、地理**每镜重述**。"),
 ("提交前要做什么？",
  "过**合规预筛**：分类器拒的是**词**，不是意图 ⇒ 把意图翻成中性、字面的词；被拒就如实报，不绕分类器。**生成与费用归视频提供方，我们不代付**。"),
 ("这条能力位的证据口径？",
  "每条规则都要能指回**哪次实拍的哪处故障**；指不回就标**未验**。对方证据是三拍同场景（2026-09-26/27）的十处故障 ⇒ 我们**未复现**，如实标。"),
]
for q, a in F:
    add(q, a)
    add("（换问法）" + q, a)
out = base + new
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
blob = OUT.read_bytes()
fam = defaultdict(int)
for r in out:
    fam[r.get("family") or "?"] += 1
MAN.write_text(json.dumps({"gen": "v30", "parent": "v29", "count": len(out), "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(),
                           "by_family": dict(sorted(fam.items(), key=lambda x: -x[1]))},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("v30 count", len(out), "| new", len(new), "| bytes", len(blob), "| sha", hashlib.sha256(blob).hexdigest()[:16])
print("镜头导演", fam.get("镜头导演"), "| 节点契约", fam.get("node_contract"), "| 域名册", fam.get("域名册"))
