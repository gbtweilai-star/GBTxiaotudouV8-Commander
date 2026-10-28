# 21 · 脑库记忆 (`brain_vault`)

> 1 能力位 · Obsidian 记忆库读写 · 追加式 · 没有删除路径
>
> 写进去的想忘都忘不了。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 设计理念

> 脑库接入：Obsidian 记忆库的读（recall=记忆总纲+收集箱）/
> 写（remember=追加一条）/ 体检（status）—— **追加式、没有任何删除路径**，
> 写进去的想忘都忘不了。

## 能力清单

| 能力位 | 说明 |
|---|---|
| `brain_vault` | 脑库接入：recall（读）/ remember（写）/ status（体检） |

## API参考

### 读记忆总纲

```python
import gbt_allinone as gbt

result = gbt.run_task("brain_vault", {"op": "recall"})
# 返回: {
#   ok, vault_path: "C:/Users/xxx/Obsidian/GBT",
#   index: "...",           # 记忆总纲
#   inbox: [...],           # 收集箱条目
#   total_notes: 245
# }
```

### 追加记忆

```python
result = gbt.run_task("brain_vault", {
    "op": "remember",
    "text": "2026-10-28: 完成了原生能力全量开源",
    "tags": ["开源", "里程碑"]
})
# 返回: {ok, note_path: "GBT/inbox/2026-10-28.md", line: 15}
```

**追加式**：只往文件末尾追加，不修改已有内容，不删除任何东西。

### 体检

```python
result = gbt.run_task("brain_vault", {"op": "status"})
# 返回: {
#   ok, vault_exists: true,
#   note_count: 245,
#   inbox_count: 12,
#   last_modified: "2026-10-28T06:00:00",
#   broken_links: []
# }
```

## 存储结构

```
Obsidian/GBT/
├── index.md              # 记忆总纲
├── inbox/
│   ├── 2026-10-28.md     # 当日收集箱
│   ├── 2026-10-27.md
│   └── ...
├── projects/
│   ├── GBT小土豆V8.md
│   └── ...
└── lessons/
    ├── 部署纪律.md
    └── ...
```

## 记忆分层

| 层 | 内容 | 写入时机 |
|---|---|---|
| **总纲** | 长期项目笔记、规范 | 手动/重大决策 |
| **收集箱** | 当日工作日志 | 每完成实质工作 |
| **项目** | 项目专属笔记 | 项目里程碑 |
| **教训** | 踩坑记录、纪律 | 犯错后 |

## 与其他记忆层的关系

| 层 | 位置 | 作用域 |
|---|---|---|
| 云端记忆 | 服务器 | 跨会话用户画像 |
| 用户级本地记忆 | `~/.workbuddy-ai/MEMORY.md` | 跨项目用户偏好 |
| 工作区记忆 | `.workbuddy-ai/memory/` | 当前项目 |
| **脑库** | Obsidian vault | **永久知识资产** |

**脑库是最外层**：它不随会话结束、不随项目切换，是框架的长期知识底座。

## 无删除路径

```python
# 这个能力位没有 delete 操作
# 想"忘掉"什么？只能追加一条"作废"记录
gbt.run_task("brain_vault", {
    "op": "remember",
    "text": "作废：2026-10-27的XXX结论（原因：实测推翻）"
})
```

**为什么这样设计**：记忆的价值在于可追溯。删掉的东西无法追溯，也无法从错误中学习。作废记录保留完整的认知演化路径。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
