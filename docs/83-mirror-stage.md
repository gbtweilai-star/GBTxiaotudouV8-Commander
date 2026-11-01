# 83 · 镜像工作空间（mirror_stage）

> 2026-11-01 · 主人口径：**生产永不被试验污染；没跑通的代码严禁进生产面板。**
> 生产要改，就在镜像里多候选试，跑通后**整页原子替换**；不是一直污染生产。

## 一、它替掉哪种坏习惯

| 坏习惯 | 本件 |
|---|---|
| 直接在生产页面上改，改坏了再回滚 | 生产只读复制进镜像；候选只写 `stage/work/` |
| 试了十版，生产被改了十次 | 多个 stage id = 多候选，互不覆盖 |
| “我觉得能跑”就上线 | `verify` 必须在镜像里跑外部验证器（cmd + exit_code）；失败/没验 **promote 直接拒** |
| 上线靠手抄/局部 patch | `promote` 对每个目标做**整文件 `os.replace` 原子替换**，先备份，可 `rollback` |

## 二、状态机

```
create  → 生产文件复制进 state/mirror/stage/<id>/work/（生产只读）
write   → 只写已登记 target 的镜像候选（可多候选）
verify  → 在 work/ 里跑 cmd；exit_code=0 才 verified
promote → confirm=true 且 verified → 备份 + 整文件 os.replace
rollback→ 从备份原子还原
```

硬门：
- 没 `verify` / `exit_code≠0` ⇒ `not_verified`，**生产不动**；
- 没 `confirm=true` ⇒ `needs_confirm`；
- 目标不在 `create` 登记列表 / 越出 repo ⇒ 拒；
- 只替换登记 target，整文件替换，不做隐式局部 patch。

## 三、实测（`tests/test_mirror_stage.py` ALL PASS）

- create/write 后生产仍是 `OLD`；
- 没验 → promote 拒；
- verify exit 1 → promote 拒；
- verify exit 0 → promote：生产变 `NEW`，有备份；rollback 回 `OLD`；
- 两候选 `a/b` 独立，生产不动。

## 四、与远程协助的边界（重要）

主人说的“镜像多维度空间也是远程协助 / 千里语音 / 万能插接管远端电脑”，是**另一条能力面**：
- 本件 `mirror_stage` 只做**本机文件级 staging + 原子替换**；
- 远控需要：**双向同意/授权凭证、端到端会话、屏幕/输入通道、隧道、审计**；这些不能塞进本件假装已通；
- 本机已有零件：`screen_sniff`（本地屏幕采集）、`control_loop`（动作枚举）、`remote_domain`/`warm_switch`（中继/链路口径）、`voice`；但**还没有**组装成“远端点同意 → 万能插接管”的端到端能力。
- 下一步应单独立 `remote_assist`：先做**授权令牌 + 会话协议 + 本机端到端**，再谈公网隧道；不做“无同意远控”。

## 五、op

| op | 作用 |
|---|---|
| `status` | 仓根/stage 数/规则 |
| `create` | 复制生产目标进镜像 |
| `list` | 所有候选与验证状态 |
| `write` | 只写镜像候选 |
| `verify` | 镜像内跑校验命令 |
| `promote` | 验过后原子整页替换（需 confirm） |
| `rollback` | 备份还原 |
| `where` | 入口 |

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
