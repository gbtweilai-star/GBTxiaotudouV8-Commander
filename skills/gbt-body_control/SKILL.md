---
name: gbt-body_control
displayName: GBT · body_control 职业域用法规程（1 个能力位：body_control）
version: 1.0.0
description: GBT小土豆V8 的 `body_control` 职业域（身体控制 / 触手 / 全息投影状态口）用法规程。这个域**只有 1 个能力位**：`body_control`。本文件把它写全：op=schema/status/inventory/move/verify 逐个点名、**零作用域纯数据**（不调模型/不出网/不写盘/不驱动硬件）、**如实报缺**的纪律（缺感觉/执行器报 not_supported，全绑定也最多 partial 且 `executed=false`，**没有 ready**）、传感器与执行器清单、绑定来源、失败典型样子（`move` 永远拒、`needs_dependency` 不是坏了）、与 gbt-tentacle（看屏幕那条路）和 gbt-vision（视觉位）的边界；并记下实测读数。当用户要问身体/触手/全息投影能不能动、要看感觉与执行器清单、或 body_control 报 not_supported 时使用。
triggers:
  - "body_control"
  - "身体控制"
  - "触手"
  - "全息投影"
  - "not_supported"
  - "执行器"
  - "感觉"
---

# GBT · body_control 职业域用法规程（1 个能力位：`body_control`）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这份规程解决什么**：`body_control` 是一位一域的最小域，它是**身体控制的状态口**——
> 管感觉（sensor）与执行器（actuator）的清单与绑定，**不驱动任何硬件**。
> 它的核心纪律是主人 2026-11-02 定的：**「深度学习 + 无模型不等于能动——缺感觉/缺执行器时如实报缺，不假装能动」**。
> 本文件把「哪个 op、要不要授权、失败长什么样、读数该看哪个字段」逐个钉死。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```bash
python tools/codex-scripts/five-dim.py cap body_control ['<JSON载荷>'] [--full]
```

一律走 `gbt_allinone.run_task`（**唯一门**）；被门拒绝就**如实报缺什么作用域**，不绕路。

---

## 0. 一位一域（先确认名字）

现读 `gbt_allinone/caps_registry.py`（`domain == "body_control"`）**只有一条**：

| 域 | 能力位（kind） | handler | safe | 注册表 desc 原文 |
|---|---|---|---|---|
| `body_control` | **`body_control`** | `body_control` | **true** | 身体控制 / 触手 / 全息投影状态口；**如实报缺**：缺感觉/执行器报 not_supported；全绑定也最多 partial 且 `executed=false`；**zero-scope**，只读状态/清单，不驱动任何硬件 |

**它不干什么**：不驱动硬件、不调模型、不出网、不写盘。它是**纯数据状态口**。

分派链（实测可调）：
`api.py:314`（`kind == "body_control"` → `from .tools import body_control as _bc`）
→ `gbt_allinone/tools/body_control.py`（`run(op, **params)` 111-125 行是全部分派）

---

## 1. 什么时候用（意图 → 落点）

| 人想干什么 | 落到哪个 op | 只读还是要授权 |
|---|---|---|
| 看身体控制整体状态 | `status` | 只读，**零作用域** |
| 看感觉/执行器清单 | `inventory` | 只读，**零作用域** |
| 看支持哪些 op / 状态取值 | `schema` | 只读，**零作用域** |
| **想让它真动（挥手/走路）** | `move` | 🔴 **永远拒**（`executed=false`，无执行器/无安全闭环） |
| 自检判据 | `verify` | 只读，**零作用域** |

**不在这 1 个位里的事**：看屏幕/操作鼠标键盘 → `gbt-tentacle`；看图/摄像头 → `gbt-vision`；
驱动真硬件 → **本件不承接**（`move` 永远拒，见 §4）。

---

## 2. 🔴 要过哪道门：**整域零作用域**

**实测（本机 · `policy.evaluate` 逐 op 真跑）**：

```python
policy.evaluate("body_control", {"op": "status"}).scopes      # → ()    零作用域
policy.evaluate("body_control", {"op": "inventory"}).scopes   # → ()    零作用域
policy.evaluate("body_control", {"op": "schema"}).scopes      # → ()    零作用域
policy.evaluate("body_control", {"op": "move"}).scopes        # → ()    零作用域（但本体永远拒）
policy.evaluate("body_control", {"op": "verify"}).scopes      # → ()    零作用域
```

| op | 作用域（实测） | risk | restricted |
|---|---|---|---|
| `schema` / `status` / `inventory` / `verify` | **零** | low | false |
| `move` | **零**（但本体永远 `executed=false`） | low | false |

🔴 **"零作用域"≠"能动"**：本域**整域零作用域**（policy 层不挂任何作用域），
但 `move` 在**本体层**永远拒（`tools/body_control.py:62-67`）——门不拦它，是它自己不执行。
⇒ **别把"零作用域"读成"能动"**。

**本域不需要任何授权**：所有 op 都不挂作用域，未受信会话也能直接调（读 op 当然可以；`move` 调了也只会拿到拒）。

---

## 3. 怎么调（真命令）

```bash
# ── 只读这一档（零作用域；本规程真跑过，见 §6）──
python tools/codex-scripts/five-dim.py cap body_control                      # 空载荷 = status
python tools/codex-scripts/five-dim.py cap body_control '{"op":"status"}'
python tools/codex-scripts/five-dim.py cap body_control '{"op":"inventory"}'
python tools/codex-scripts/five-dim.py cap body_control '{"op":"schema"}'
python tools/codex-scripts/five-dim.py cap body_control '{"op":"verify"}'

# ── 动作口（永远拒，但可照调看拒的原文）──
python tools/codex-scripts/five-dim.py cap body_control '{"op":"move","action":"wave"}'
```

`bindings` 由调用方传入（服务端读 `state/body_control.json`）；不传 = 未绑定 = 全缺。

---

## 4. 有哪些 op（源码逐个点名 · `tools/body_control.py:111-125`）

| op | 去处 | 性质 |
|---|---|---|
| `schema` | `run("schema")` → 返回 sensors/actuators 清单 + statuses | 只读 |
| `status` | `status(bindings)` → 算 not_supported/partial + missing 清单 | 只读 |
| `inventory` | `inventory(bindings)` → 感觉/执行器布尔表 | 只读 |
| `move` | `move(action, **params)` → **永远 `ok:false` + `executed:false` + `not_supported`** | 🔴 永远拒 |
| `verify` | `verify()` → 20 条判据自检 | 只读 |
| 未知 op | `raise ValueError("未知 op: …")` | 拒（非门拒） |

**状态取值只有两个**：`not_supported`（未接线）/ `partial`（有绑定但执行器未接）。**没有 `ready`**。

---

## 5. 落点 / 外部面

| 维度 | 实测 |
|---|---|
| **传感器清单** | `camera` / `microphone` / `screen` / `depth` / `tentacle_bus`（5 个） |
| **执行器清单** | `tentacle_bus` / `holographic_projection` / `digital_human_display` / `robot_arm`（4 个） |
| **绑定来源** | 调用方传入 `bindings`；服务端读 `state/body_control.json`；不传=未绑定 |
| **落点** | 不写盘、不出网、不调模型；纯内存数据 |
| **`wired` 字段** | **永远 `false`**（本件没有执行器驱动/安全闭环） |

---

## 6. 实测读数（本机真跑，原文抄录）

### 6.1 `cap body_control '{"op":"status"}'`（空 bindings）

```json
{"gate":"run_task","kind":"body_control","status":"ok","stamp":true,"denied":false,
 "result":{"ok":true,"domain":"body_control","status":"not_supported","wired":false,
  "sensors":{"camera":false,"microphone":false,"screen":false,"depth":false,"tentacle_bus":false},
  "actuators":{"tentacle_bus":false,"holographic_projection":false,"digital_human_display":false,"robot_arm":false},
  "missing":{"sensors":["camera","microphone","screen","depth","tentacle_bus"],
             "actuators":["tentacle_bus","holographic_projection","digital_human_display","robot_arm"]},
  "executor":"not_wired","note":"缺感觉/执行器…不假装能动、不伪造动作回执","binding_source":"调用方未提供"}}
```

**读法**：`status:"ok"` 是外层（调用成功）；`result.status:"not_supported"` 是内层（身体控制未接线）。
**判"调用成功了吗"看外层；判"身体能不能动"看内层 `status`。**

### 6.2 `cap body_control '{"op":"move","action":"wave"}'`

```json
{"ok":false,"status":"not_supported","executed":false,"domain":"body_control",
 "requested":"wave","reason":"body_control 未接线：没有绑定执行器/安全闭环，动作不执行"}
```

**`move` 永远这样**：`executed:false` + 带原因。**不是坏了，是设计如此**。

---

## 7. 失败典型样子（照着认）

| 症状 | 真因 | 正确读法 |
|---|---|---|
| `result.status:"not_supported"` + `wired:false` | **未接线**（没绑定感觉/执行器） | **不是坏了** —— 本件就是状态口，未接线如实报 |
| `result.status:"partial"` | 有绑定但执行器未接 | 仍不能动；看 `missing.actuators` 缺哪个 |
| `move` 回 `ok:false` + `executed:false` | **永远拒**（无执行器/安全闭环） | **设计如此**，不是故障 |
| `binding_source:"调用方未提供"` | 没传 `bindings` | 要查绑定就传 `bindings`（或看服务端 `state/body_control.json`） |
| 把 `status:"ok"` 读成"身体能动" | 外层 ≠ 内层 | 看 `result.status`（§6.1） |
| 以为"零作用域"=能动 | 零作用域 ≠ 能动 | `move` 本体永远拒（§2） |

---

## 8. 🔴 未验清单

| 动作 | 状态 | 为什么不做 |
|---|---|---|
| `move` 真驱动硬件 | **不做** | 本件无执行器驱动/安全闭环；`move` 永远拒是设计 |
| 接真执行器 | **未验** | 需主人接执行器 + 安全闭环；接好前 `wired` 仍 false |

> **"未验"不是"坏了"**：本件是状态口，它的纪律就是**如实报缺**。

---

## 9. 与相邻域的边界（一句话切干净）

| 相邻 | 谁是谁 | 边界 |
|---|---|---|
| `gbt-tentacle` | 手眼网耳（看屏幕/鼠标键盘） | 那是**输入/操作层**；本域是**身体状态口**，不驱动硬件 |
| `gbt-vision` | 视觉位（看图/摄像头） | 视觉是**感觉的一种**；本域只报"有没有绑定 camera"，不真读图 |
| `gbt-device` | 蓝牙等设备域 | 设备域管具体外设；本域管身体感觉/执行器的**状态清单** |

---

## 10. 🔴 报告层红线

1. **外层 `status:"ok"` ≠ 内层能动**：判调用看外层，判身体状态看 `result.status`（§6.1）。
2. **`not_supported` ≠ 坏了**：它是"未接线"的如实报告（§7）。
3. **`move` 的 `executed:false` 是设计**：不是故障，不是被门拒（门根本没挂作用域）。
4. **"零作用域"必须带"不能动"说**：本域零作用域，但**不等于能动**——单说"零作用域"会误导。
5. **没有 `ready` 状态**：全绑定也最多 `partial`；别编"ready"。

---

## 11. 不许做什么（红线）

1. **不许假装能动**：缺感觉/执行器时**如实报缺**，不伪造 `executed:true`、不编"已动"。
2. **不许给自己发授权**：本域本就零作用域，无需授权；更不许改 `security/policy.py`。
3. **不许绕门**：不直接调 `tools/body_control.py` 的函数替掉 `run_task` 唯一门。
4. **不许**把 `move` 的拒读成"坏了"或"被门拒"——它是本体设计。
5. **不许**替主人编绑定状态（`bindings` 不传就是未绑定，如实报）。

---

## 12. 固化与出处（**重启后要在**）

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-body_control/SKILL.md` |
| 本规程（装机·托管目录） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-body_control\SKILL.md` |
| 注册表条目 | `gbt_allinone/caps_registry.py`（`domain == "body_control"` 唯一条，1565 行） |
| 分派 | `gbt_allinone/api.py:314` → `gbt_allinone/tools/body_control.py`（`run()` 111-125） |
| 授权判据（**单一真相**） | `gbt_allinone/security/policy.py`（本域零作用域，无专属分支） |
| 现读入口 | `tools/codex-scripts/five-dim.py cap body_control` |

**验收（做完怎么证明真的做了）**：

```bash
python tools/codex-scripts/verify-distill.py --domain body_control --skill gbt-body_control
```

1. 必须 **PASS**（覆盖 1/1）；
2. 两份产物**逐字节相同**（sha256 一致）；
3. 再静态查 `policy.evaluate("body_control", {"op":"move"}).scopes` —— 必须**仍是** `()`；
4. 声明"能动"之前先问：**这是实测读数，还是我读错了地方？** 本域的纪律就是如实报缺。
