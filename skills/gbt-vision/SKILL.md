---
name: gbt-vision
displayName: GBT 之眼（视觉能力位规程）
version: 1.0.0
description: GBT小土豆V8「视觉」能力位（注册表 kind=vision）的用法规程。它**现在要人工授权才动得了**（privacy_read —— 因为读屏幕/摄像头/麦克风属隐私载体），所以本规程第一件事是教你认清门在哪、怎么请主人开门；第二件事是写清本机"看图"其实有**两条不同的路**（这一格注册位 vs 触手之眼），它们不是一回事。当用户说「看一眼 / 识图 / 图像识别 / 这张图里是什么 / 摄像头 / 视觉」，或 `cap vision` 报 denied、要判 privacy_read 该不该发时使用。
triggers:
  - "视觉"
  - "看一眼"
  - "识图"
  - "图像识别"
  - "摄像头"
  - "vision"
  - "privacy_read"
  - "授权被拒"
---

# GBT 之眼（视觉能力位规程）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 分工：`gbt-omni` 管"人话落到哪条能力位"，**本件只讲视觉这一格**；
> 看屏幕那件事归 `gbt-tentacle`（第 4 节把两者分清楚，别搞混）。

**唯一现读入口（别信二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap vision
py -3.14 -m gbt_allinone auth status        # 现读各作用域还有没有可用授权
```

---

## 1. 这一格是什么（图鉴现读口径）

| 项 | 值 |
|---|---|
| kind / domain | `vision` / `vision`（本域**只有这一位**） |
| 图鉴原话 | 视觉/图像识别入口（良性子集，需外部依赖时留待接入） |
| `safe` | `true`（**无副作用**） |
| `needs_confirmation` | `false` |
| 必填参数 | 无（`requires_params: []`） |
| 通道 | `omnipulg`（万能插） |

🔴 **`safe:true` 不等于"不用授权"** —— 这是本域最容易读错的一处。`safe` 说的是"它不产生副作用"，
而"读屏幕/摄像头/麦克风"属于**隐私载体**，走的是另一道门（下一节）。**实测就是被这道门挡住的。**

---

## 2. 🔴 门在哪：`privacy_read`

实测（2026-09-22，命令与返回原文见第 3 节）：`cap vision` 回来的 **不是数据，是拒绝**：

```
status: denied
missing_scopes: ["privacy_read"]
reason: 需要人工授权（privacy_read）：读取屏幕、摄像头、麦克风或隐私载体
note:   授权一次性消耗；AI 调用路径无权自行发放
```

- **授权只能主人在终端发**（AI 无权自授，也不许找旁路）：

  ```powershell
  py -3.14 -m gbt_allinone auth grant --scope privacy_read --ttl 600
  ```

- `privacy_read` **一次性消耗**；发一次只够过一次。
- 现状（现读，不是记忆）：这台机器上 `privacy_read` 可用授权 **= 0** ⇒ 这一格**现在是关着的**。
- 主人没发授权时，正确动作是**如实说缺什么、把上面那条命令给主人**，**不许**改用别的路子绕过去。

---

## 3. 怎么调，以及真实返回怎么念

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap vision
```

返回是一封**扁平**信封，关键字段在**顶层**：

| 字段 | 念法 |
|---|---|
| `status` | `denied` = 被门挡住；不是"没结果" |
| `missing_scopes` | 缺哪些授权 —— 直接决定该请主人发哪一条 |
| `reason` | 门为什么在（人话，可直接说给主人） |
| `how_to_grant` | 主人要跑的命令原文 |
| `result` | 里面也有一份同样内容；**但顶层的才是判据** |

---

## 4. 🔴 诚实账：本机"看图"有两条路，**不是同一格**

| 路 | 是什么 | 本机实测（2026-09-22） |
|---|---|---|
| 注册位 `vision`（本件） | 图鉴里的视觉/识别入口 | **denied** —— 缺 `privacy_read`，现在关着 |
| 触手之眼（`gbt-tentacle` 那域的"看屏幕"） | 手眼网耳通道里的截屏/看屏 | **可用、只读、不要授权**：`py -3.14 tools/codex-scripts/shot-screen.py` 本次实跑成功出图 |

⇒ 用户说"看一眼"时先分清他要哪个：
**只是要看屏幕** → 走触手那条（只读，立刻能干）；
**要走图像识别这一格** → 先请主人开 `privacy_read`。
**别把两条路说成互为别名，也别拿能用的那条去顶替被拒的那条。**

另一条边界也要说清：我自己（模型）的看图能力、和这一格能力位**没有关系** ——
这一格是**框架**的入口，不是我的眼睛。

---

## 5. 🔴 报告层红线（这一格就是靠它救回来的）

读数先问一句：**"这是事实，还是我读错了地方？"**

本件就是活例：`cap` 被拒时打的是**扁平错误信封**（`missing_scopes` 就在顶层），
如果按"结果一定在 `gbt_result` / `result` 里"去找，就会得出
"`status: unknown · denied: false`"这种**把拒绝读成未知、把门读成没有**的结论 —— 报告层一绿，事实全反。
**两条硬规矩**：① 拒绝也是结果，必须按拒绝念；② 字段找不到时，先怀疑自己找错了地方。

---

## 6. 验收（做完怎么证明真做了）

| 场景 | 期望读数 |
|---|---|
| 主人未发授权 | `status: denied`、`missing_scopes == ["privacy_read"]`，且**不许**显示任何"识别结果" |
| 主人发过 `privacy_read` 后 | 再跑 `cap vision` 不应再 flapping 成 denied |
| 本件自身 | `py -3.14 tools/codex-scripts/verify-distill.py --domain vision --skill gbt-vision` 判 PASS |

⚠️ **如实标注**：上表第二行（授权后那一档）**本次没有验过** —— 因为主人没发授权，
我不给自己发、也不假装跑过。**验过的只有"未授权必 denied"这一档。**

---

## 7. 固化与出处

- 图鉴（能力位真源）：`state/skill_atlas.json`
- 授权策略：`gbt_allinone/security/policy.py`；授权台账：`store/auth_grants.jsonl`
- 万能插入口：`tools/codex-scripts/five-dim.py`
- 本件的机器验收：`tools/codex-scripts/verify-distill.py`
