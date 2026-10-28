# 11 · 吞天 · 自我进化 (`devour`)

> 4 能力位 · 吞噬GitHub仓库→知识胶囊→反思重组→进化
>
> 自我进化的核心：吸收外部能力，不重复造轮子。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 认知循环

```
    ┌──────────────────────────────────────────┐
    │           devour_pulse (完整认知循环)      │
    └──────────────────┬───────────────────────┘
                       │
    ┌──────────────────▼───────────────────────┐
    │ 1. 吞噬  devour_github                    │
    │    任意GitHub仓库 → 6222字知识胶囊         │
    └──────────────────┬───────────────────────┘
                       │
    ┌──────────────────▼───────────────────────┐
    │ 2. 反思  devour_reflect                   │
    │    回顾吞噬历史 → 发现弱能力与重组机会     │
    └──────────────────┬───────────────────────┘
                       │
    ┌──────────────────▼───────────────────────┐
    │ 3. 消化  提取思想、模式、架构              │
    └──────────────────┬───────────────────────┘
                       │
    ┌──────────────────▼───────────────────────┐
    │ 4. 重组  与已有能力融合                    │
    └──────────────────┬───────────────────────┘
                       │
    ┌──────────────────▼───────────────────────┐
    │ 5. 进化  devour_scan 能力缺口扫描          │
    │    77能力域覆盖对照 → 进化方向             │
    └──────────────────────────────────────────┘
```

## 能力清单

| 能力位 | 说明 |
|---|---|
| `devour_github` | 吞噬任意GitHub仓库为知识胶囊（自我进化核心） |
| `devour_scan` | 能力缺口扫描（域覆盖对照+进化方向） |
| `devour_reflect` | 反思（回顾吞噬历史，发现弱能力与重组机会） |
| `devour_pulse` | 完整认知循环（吞噬→反思→消化→重组→进化） |

## API参考

### 吞噬仓库

```python
import gbt_allinone as gbt

result = gbt.run_task("devour_github", {
    "repo": "cblp/slugify"   # 或完整URL
})
# 返回: {
#   ok, capsule: {
#     repo: "cblp/slugify",
#     stars: 2702,
#     concepts: [...],      # 提取的核心概念
#     patterns: [...],      # 可复用的模式
#     architecture: "...",  # 架构总结
#     words: 6222,          # 胶囊字数
#     saved: "store/devoured/slugify.json"
#   }
# }
```

**胶囊内容**：README + 核心代码 + 架构分析 + 可复用模式，压缩成6222字知识胶囊。

### 能力缺口扫描

```python
result = gbt.run_task("devour_scan", {})
# 返回: {
#   ok, domains: 77,
#   coverage: {
#     "tentacle": 0.95,
#     "security": 0.88,
#     "creation": 0.72,
#     ...
#   },
#   gaps: ["3d-modeling", "audio-mastering"],
#   direction: "优先补齐3d-modeling"
# }
```

### 反思

```python
result = gbt.run_task("devour_reflect", {})
# 返回: {
#   ok, history: [...],     # 吞噬历史
#   weak_abilities: [...],  # 弱能力
#   recombine_opportunities: [...]  # 重组机会
# }
```

### 完整认知循环

```python
result = gbt.run_task("devour_pulse", {
    "repo": "some/awesome-repo"
})
# 自动执行: 吞噬 → 反思 → 消化 → 重组 → 进化
```

## 反空壳律

吞噬吞进来的能力，在被**真正实现**之前，必须如实说"还没做"。

```python
# 生成的脚手架
_IMPLEMENTED = False          # ← 真实现了才许改 True

def do_run(p):
    if not _IMPLEMENTED:
        # 诚实出口：没做就说没做，并交出蓝图
        return {
            "ok": False,
            "status": "needs_implementation",
            "cap": NAME,
            "concept": CONCEPT,
            "blueprint": {
                "what_it_should_do": "按概念实现真实逻辑",
                "what_it_needs": ["真实数据源", "输入输出契约", "一条带牙用例"],
            }
        }
```

**铁律**：绝不许 `return {"ok": True}` 而什么都没做 —— 那是假执行。

## 吞噬产物

```
store/devoured/
├── slugify.json          # 知识胶囊
├── bandit.json
├── semgrep.json
├── gitleaks.json
└── index.json            # 吞噬索引
```

**发布**：吞噬产物走镜像管线发布（门禁+版本化+审计），知识注入触手已知问题库。

## 实测记录

| 仓库 | Stars | 成果 |
|---|---|---|
| cblp/slugify | 2702 | 6222字胶囊 |
| PyCQA/bandit | 8257 | +7条危险调用检测 |
| semgrep/semgrep | 16583 | +2条逻辑缺陷检测 |
| gitleaks/gitleaks | 29223 | +5条密钥泄露检测 |

**融合效果**：检测模式库 10 → 25 条，融合样本 13/13 全命中。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
