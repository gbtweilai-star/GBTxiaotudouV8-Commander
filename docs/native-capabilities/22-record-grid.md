# 22 · 行式记录网格 (`record_grid`)

> 1 能力位 · 陌生文本结构化解析 · 七路转接
>
> 吸收2000年代AI链接清单格式的**方法**（行式记录+闭集词表+位置分隔+解析期守契约），
> 不复制其数据；合上原件重建，并补上原件没有的四点。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 七路转接

| op | 作用 |
|---|---|
| `presets` | 内置格式语法（当前 `link_index`：标题[*] URL 标签,标签.类别 备注） |
| `profile` | 陌生文本结构画像：分隔方式/列数一致性/每列类型/候选词表/表头与标记 |
| `draft` | 画像 → plan骨架（附warnings，词表待人工确认，不冒充成品） |
| `parse` | 逐行解析；坏行带行号/原文/可执行诊断进 `invalid[]`，不废整卷 |
| `verify` | 回写自证：parse → emit → parse 记录指纹必须一致 |
| `emit` | 记录 → 文本；`out` 只能写进 `store/record_grid/`，越界即拒 |
| `vocab` | 受控词表校验，越界值保留上报（不静默丢弃） |

## 补上原件没有的四点

1. **坏行不废整卷** — 单行解析失败不影响其他行，坏行进 `invalid[]` 带诊断
2. **显式解码与位置感知分词** — 不靠猜测，显式声明编码与分词方式
3. **词表越界降级为 finding** — 不静默丢弃，保留上报
4. **回写自证（parse∘emit幂等）** — 解析→生成→再解析，指纹必须一致

## API参考

### 结构画像

```python
import gbt_allinone as gbt

result = gbt.run_task("record_grid", {
    "op": "profile",
    "text": open("links.txt", encoding="utf-8").read()
})
# 返回: {
#   ok,
#   delimiter: " ",
#   columns: 4,
#   consistent: true,
#   column_types: ["text", "url", "tags", "note"],
#   vocab_candidates: {tags: [...], category: [...]},
#   has_header: false,
#   markers: ["[*]"]
# }
```

### 生成草案骨架

```python
result = gbt.run_task("record_grid", {
    "op": "draft",
    "profile": {...}
})
# 返回: {
#   ok, plan: {...},
#   warnings: ["词表待人工确认：tags有14个值", "备注列含非ASCII"]
# }
```

### 逐行解析

```python
result = gbt.run_task("record_grid", {
    "op": "parse",
    "preset": "link_index",
    "text": "..."
})
# 返回: {
#   ok,
#   records: [{title, url, tags: [...], category, note}],
#   valid: 820, invalid: 0,
#   invalid_details: [
#     {line: 15, raw: "...", diagnosis: "URL格式不合规"}
#   ],
#   ms: 13
# }
```

### 回写自证

```python
result = gbt.run_task("record_grid", {
    "op": "verify",
    "records": [...]
})
# 返回: {ok, idempotent: true, fingerprint_match: true}
```

### 生成文本

```python
result = gbt.run_task("record_grid", {
    "op": "emit",
    "records": [...],
    "out": "output.txt"   # 只能写进 store/record_grid/
})
# 返回: {ok, path: "store/record_grid/output.txt", bytes: 68118}
```

### 词表校验

```python
result = gbt.run_task("record_grid", {
    "op": "vocab",
    "records": [...],
    "vocab": {"tags": ["AI", "工具", "开源"]}
})
# 返回: {
#   ok, valid: true,
#   out_of_vocab: [{line: 3, field: "tags", value: "未知标签"}]
# }
```

## 实测数据

| 指标 | 结果 |
|---|---|
| 语料 | old-links 68118 B / 820 行 |
| 解析 | **820/820** |
| 坏行 | **0** |
| 回写幂等 | **true** |
| 画像识别 | 4列 + 「多值.单值」组合字段（左14值/右10值，与语料一致） |
| 解析速度 | **13ms（≈62862行/秒）** |
| 第三方依赖 | **零** |

## 格式语法（link_index）

```
标题[*] URL 标签,标签.类别 备注

示例：
Python异步编程指南[*] https://example.com/async 异步,教程.Python 入门必读
Rust所有权机制[*] https://example.com/rust 系统编程,语言.Rust 深入理解
```

| 元素 | 说明 |
|---|---|
| `标题` | 记录标题 |
| `[*]` | 标记（表示这是链接记录） |
| `URL` | 链接地址 |
| `标签,标签` | 多值标签（逗号分隔） |
| `.类别` | 单值类别（点号前缀） |
| `备注` | 自由文本 |

## 设计心法

完整心法与账目见 `docs/GBT解析器灵魂笔记.md`。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
