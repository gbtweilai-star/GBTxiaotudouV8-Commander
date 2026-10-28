# 27 · 工具域 (`tools`)

> 9 能力位 · 改代码唯一过门入口 · 版本库读写 · 发布面 · 工具地图
>
> 这一域回答一个问题：**"改代码"和"回滚"这两件事，门在哪里。**
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表）

| 能力位 | 类型 | 说明 |
|---|---|---|
| `code_patch` | **需授权** | **改代码的唯一过门入口**：此前 agent 直接 edit/write 落盘 ⇒ 不过门、不留痕；本件把写盘收成一条路 |
| `git_read` | 只读 | **版本库只读面**：补 `code_patch` 的另一半——「改完要能看、要能回滚」 |
| `git_write` | **需授权** | **版本库写面**（只两个 op，且**永远要点名路径**）：`stage`（`git add -- <paths>`）· 其余 |
| `repo_publish` | 只读 | **远端发布面**：补 `git_write` 的另一半（tools 域只有本地面，缺远端） |
| `awesome_tools_index` | 只读 | Awesome Tools 蒸馏索引（只读骨架·地图）：四原语 INDEX / LOOKUP / MAP / VERIFY；三条带牙判据 |
| `capability_net` | 只读 | 穿透网七栏只读读数：indexed / entry_known / reachable / verified×2 / has_test / … |
| `freebuff_term` | 只读 | freebuff 终端集成：把 freebuff 终端接进对话面板，编程走这条 |
| `projection_card` | 只读 | 空间投射只读卡片：5 原语全标**未核实** + **ARM ≠ LIVE** 红线（只呈现不执行） |
| `pulse_direct` | 只读 | **脉冲直达**：把脉冲给大模型，让她把全部能力按触手双向绑定的部署方式**急速运行** |

---

## 为什么「改代码」必须只有一个门

```
    ❌ 旧路径（实测事故）
    agent ──直接──▶ edit / write 落盘
                    ↓
              不过门 · 不留痕 · 无法回滚 · 无审计

    ✅ 现路径
    agent ──▶ code_patch（过门）──▶ 写盘 + 审计 + 可回滚
                   │
                   └──▶ git_read 看改了什么
                   └──▶ git_write 点名路径暂存
                   └──▶ repo_publish 推远端
```

**实测教训（2026-09-23 接 `code_patch` 时记）**：此前 agent 直接 `edit`/`write` 落盘 ⇒ **不过门、不留痕**。功能上"成功了"，纪律上是**未经审计的源码写入**。

---

## API 参考

### 改代码（code_patch）

```python
import gbt_allinone as gbt

result = gbt.run_task("code_patch", {
    "op": "apply",
    "path": "gbt_allinone/example.py",
    "old": "return None",
    "new": "return {'ok': True}"
})
# 返回: {ok, path, lines_changed, backup: "store/patches/xxx.bak"}
```

**过门要求**：`filesystem_write` 授权。缺票如实报 `needs_grant`，不静默改盘。

### 看改了什么（git_read）

```python
# 状态
gbt.run_task("git_read", {"op": "status"})

# 差异
gbt.run_task("git_read", {"op": "diff", "path": "gbt_allinone/example.py"})

# 日志
gbt.run_task("git_read", {"op": "log", "limit": 10})
```

### 暂存（git_write）

```python
# 永远要点名路径（不许 git add -A）
gbt.run_task("git_write", {
    "op": "stage",
    "paths": ["gbt_allinone/example.py"]
})
```

**纪律**：只两个 op，且**永远要点名路径**——`git add -A` 会把不该进仓的东西一起带走。

### 推远端（repo_publish）

```python
gbt.run_task("repo_publish", {
    "op": "status"
})
```

### 工具地图（awesome_tools_index）

```python
# 建索引
gbt.run_task("awesome_tools_index", {"op": "INDEX"})

# 查一个工具
gbt.run_task("awesome_tools_index", {"op": "LOOKUP", "name": "ffmpeg"})

# 映射到能力位
gbt.run_task("awesome_tools_index", {"op": "MAP"})

# 验证（三条带牙判据）
gbt.run_task("awesome_tools_index", {"op": "VERIFY"})
```

### 穿透网读数（capability_net）

```python
result = gbt.run_task("capability_net", {})
# 返回七栏只读读数：
# {indexed, entry_known, reachable, verified_static, verified_runtime, has_test, ...}
```

### 空间投射（projection_card）

```python
result = gbt.run_task("projection_card", {})
# 5 原语全部标「未核实」
# 红线：ARM ≠ LIVE（只呈现不执行）
```

**这条红线很重要**：卡片上显示"已布防"不等于"真的在运行"。ARM 是意图，LIVE 是事实，两者不许混。

---

## 纪律汇总

| 纪律 | 说明 |
|---|---|
| **写盘只有一条路** | 改代码必须走 `code_patch`，不许直接 `edit`/`write` |
| **暂存要点名** | `git_write` 永远传 `paths`，不许 `-A` |
| **读写在两个位** | 读面 `git_read` 只读、写面 `git_write` 需授权——不混成一个大位 |
| **ARM ≠ LIVE** | 卡片显示"布防"不等于"运行中" |
| **未核实就标未核实** | `projection_card` 5 原语默认全标未核实，不冒充已验证 |

## 授权门

| 能力位 | 作用域 |
|---|---|
| `code_patch` | `filesystem_write` |
| `git_write` | `filesystem_write` |
| 其余 | 只读，零作用域 |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
