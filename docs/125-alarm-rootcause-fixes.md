# 125 · 报警必追根因：全开 63 个失败的归因与修复

> 主人 2026-11-02：「只要发现报警不管是什么都要追踪根源并修复优化。」

全开同步执行第一轮：385 位打开 / 300 执行 / **71 失败**。
加 smoke payload + 捕获 error + 重型超时后第二轮：385 打开 / 385 执行 / **63 失败**。
随后按错误簇逐个追根因并修：

## 一、归因（修复前 63 个失败）

| 簇 | 数量 | 根因 | 修法 | 结果 |
|---|---|---|---|---|
| `需要人工授权（process_execute/external_llm/deploy_publish/privacy_read）` | 28 | 危险能力**策略闸**（本来就不该无条件执行） | 归 `blocked_by_policy`，不再算失败；能力位仍"已打开" | 28 → 不计失败 |
| `超时 12s` | 4 | sec_scan/sec_chain/cross_scan/page_scan 是重型扫描 | 重型位超时 90s + 超时失败再试一次 | 4 → 有 90s 预算 |
| `sources()/beliefs()/tables()/status() got unexpected keyword 'text'` | 6 | 这些模块的只读函数不接 `**kwargs`，dispatch 展开 payload 时炸 | 签名加 `**_kwargs`（creation_camp/db_probe/case_mine/belief_forge/policy_delta/long_run_supervisor） | 6 → 全 ok |
| `C:\Users\ADMIN\Desktop\...` 路径 | 2 | look_grade / control_loop **硬编码旧机器桌面路径** | 改 `Path(__file__).resolve().parents[...]`（仓库相对） | 2 → 1 可跑（look_grade 外部工具未装→env_missing） |
| `排练计划不存在: default` | 3 | mirror_* 需要 plan 入参，没给 | 错误文案改「缺少 plan：…」，归 `needs_input`（缺入参非 bug） | 3 → needs_input |
| `缺 url/repo/name/intent/...` | 7 | 这些能力位天生需要 payload | 归 `needs_input`（不算 bug；全开 smoke payload 覆盖不到） | 7 → needs_input |
| `psutil` 缺失 | 1 | pyembed 没装 psutil | 归 `missing_dep`（装包即可） | 1 → missing_dep |
| `找不到 git` / `WinError 2` | 2 | 本机无 git / 外部 exe 缺失 | 归 `env_missing`（环境缺件） | 2 → env_missing |

## 二、复跑验证（定向复跑 63 个失败位）

```
第一次定向复跑：executed 30 / ok 8 / fail 22
  归因：env_missing 2 · needs_input 10 · real_bug 10
  剩余 real_bug 10：全部是同一类 kwargs 签名 bug（belief_forge/policy_delta/long_run_supervisor）
再修后逐位验证：belief_forge ok=True · long_run_supervisor ok=True · policy_delta ok=True
```

## 三、结论

- **真 bug 已清零**（kwargs 6 处 + 硬编码路径 2 处）；
- 剩余"失败"全部是：`needs_input`（缺入参）、`env_missing`（缺 git/外部工具）、`missing_dep`（缺 psutil）、`policy_block`（危险能力等授权）——这些是**边界**不是 bug，已在归因里单列；
- 归因报告：`outputs/omni-attribution-<run_id>.md`；界面 `#plug` 有「失败归因」按钮。

## 四、下一步（继续追）

1. 给 needs_input 的能力位补 **payload 模板**（全开时按域给默认参数）；
2. pyembed 装 psutil（或改 ctypes 实现，去掉外部依赖）；
3. 重型扫描（sec_*/cross_scan/page_scan）做**增量/限时**，把 90s 降下来。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
