# 117 · 落地闭环：路由 → 派单 → 留痕（附全景清单）

> 主人 2026-11-02：「继续全方位推进直至落地」。
> 最后一环补齐：职业路由之后**真派单**，执行结果与账本当场回填。

## 一、闭环链路

```
任务文本
  → gbt_allinone.profession_router.plan(task)       # 21 职业打分（代码动词 +20 优先 coder）
  → gbt_allinone.profession_dispatch.dispatch(task) # 只挑 safe 候选，逐条 run_task
  → run_task 执行（能力位自身写 audit.jsonl）
  → orchestration.record("dispatch", ...)            # orchestration-ledger 留痕
  → 返回 {profession, results[{cap,ok,ms}], ok_count, fail_count, ledger}
```

**安全口径（写死）**：
- 只派 `safe=true` 的候选；需授权位只列不跑（要票）；
- 默认 `dry_run=True`（只出计划）；真执行必须 `confirm=True`；
- 该职业没有 safe 候选时**如实拒绝**，不假装执行成功；
- 失败逐条返回，不折叠成"全成功"。

## 二、接口与界面

- `POST /api/dispatch` body `{"task": "...", "confirm": true, "max_caps": 3}`
- 职业视图（`#prof`）：输入任务 →「职业路由」出候选 →「派单（安全候选）」真执行（浏览器内确认框）
- 巡检标记：`data-route`、`data-dispatch = ok:<职业>:<成功数>/<总数>`

## 三、实测

```
模块：dispatch("扫描安全疑点做无死角", dry_run=False, confirm=True, max_caps=1)
  → 安全 / 穿透 · ok=True · results=[('asset_vault_freeze', True)] · ledger=orchestration-ledger +1

API：POST /api/dispatch {"task":"剪一条30秒短视频","confirm":false}
  → 短视频编导 · executed=False · caps=['a1art_skill','anim_audit']
API：POST /api/dispatch {"task":"扫描安全疑点做无死角","confirm":true,"max_caps":1}
  → 安全 / 穿透 · ok=True · asset_vault_freeze ✓ · ledger +1
```

## 四、落地全景清单（截至 2026-11-02）

| 模块 | 状态 | 证据 |
|---|---|---|
| 认知界面 11 视图（对话/功能表/技能栏/3D 星图/大脑执行层/万能插/触手协作/思维导图/穿透扫描/职业/仪表盘） | ✅ | `docs/102-116`，页面 `#hash` 可直达 |
| 能力位 385（注册=快照=派发） | ✅ | `cap_self verify` 385=385=385 |
| 技能 23（Agent Skills 合规） | ✅ | `skills_hub validate` clean 23 |
| 真实穿透扫描 + 无死角（coverage=1.0，0 死角，70 死角已修） | ✅ | `docs/112-114` |
| 触手职业 21 种 · 覆盖 385/385 位 · 30/30 域 · 孤儿 0 | ✅ | `data/professions.json` coverage |
| **职业路由 + 派单闭环 + 账本** | ✅ | 本文 |
| 触手协作 SSE + 脉冲特效 | ✅ | `docs/105/111` |
| 原生 APP 自启认知界面服务（Electron/Python 壳/启动器） | ✅ | `docs/109`，`console_service.py` |
| GitHub 私有仓全量同步 | ✅ | private=True，HEAD 见最后一次推送 |
| 全量测试 + 五维守卫 | ✅ | `tests/`（console/console_service/doc_counts/skills/chain/guards…） |

## 五、落地时清零的历史失败（3 个）

全量测试 30 个文件，落地时清掉 3 个历史失败：

| 失败 | 根因 | 修法 |
|---|---|---|
| `test_experience_rules` / `test_experience_generated`（h1/imgs） | 拆 28 面板时把 `holo_pet_w3/index.html` 改成跳转壳，丢了首屏 h1 与真图 | 重建**落地首页**（h1 + 4 张真实界面截图 + 入口 + 签名），规则满足 |
| 同上（VOICE_DEFAULT 断言） | 2026-11-01 女声口径改成**本地优先 local**，rules.json 还写着旧的 Edge 女声 | rules.json 口径改 local 并**重新生成**测试（不手改生成文件） |
| `test_voice_defaults` | 同上（代码/脚本/配置已 local，测试还断言旧值） | 测试口径改 local（含 `local_pending_zh_tw`），docstring 注明决定日期 |

复跑：三个全 PASS；全量 30 个测试文件全绿。

## 六、边界（如实）

- 派单只跑 safe 候选；危险能力（终端危险操作、转账拿票）仍需人；
- 路由是关键词打分，不接语义模型；新任务类型要补关键词；
- 派单结果写账本，但**不会自动回喂到对话**（下一步：dispatch → 对话回复自动摘要）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
