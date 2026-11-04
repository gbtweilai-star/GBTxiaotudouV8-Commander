# 165 · 焦点栈 focus_stack + 记忆审计（P1）

> 主人 P1：「focus_stack + 记忆审计」。
> 对照上游参考项目的焦点线程/记忆审计：只取**判据**，不搬 SQLite/表结构。
> 落成我们自己的：焦点栈有界（12）+ 提分不重复 + 记忆记录只读体检。

## 一、四件

| 件 | 落点 |
|---|---|
| 模块/契约 | [`gbt_allinone/tools/focus_stack.py`](../../gbt_allinone/tools/focus_stack.py) · `verify()` **18 项** |
| 统一门 | 注册能力位 **`focus_stack`**（`run_task`，纯数据 zero-scope，`policy.py` 未改） |
| API | `GET/POST /api/focus`：snapshot / push / pop / clear / audit；真实读 `state/memory_bank.jsonl` 做只读审计；写 `outputs/focus/audit.jsonl` |
| APP 接线 | console 右栏「焦点栈」：分数排序、× 弹出、刷新；审计行显示 verdict/记录数/源 |
| 验收 | [`tests/test_focus_stack.py`](../../tests/test_focus_stack.py) |

## 二、判据

**焦点栈**
- 上限 12；同 id 再 push = 提分（+1，不重复堆）；
- 按 `score`/时间排序，`top` 取最高；score 0..100；title 必填；空 id 自动生成。

**记忆审计**（只读，不改记录/不回显凭据）
- 缺 id/文本/时间；重复 id；文本过短/超长；
- 明显凭据（`sk-…` / `api_key=` / `password=` / `token=`）→ `secret_like`，只记问题不展示原文；
- 输出 `{ok,count,issues,totals,verdict}`，`verdict=clean/needs_review`。

## 三、真机读数（2026-11-02 APP）

| 项 | 读数 |
|---|---|
| `GET /api/focus` | focus 空；audit `clean`、记录 0、源 `state/memory_bank.jsonl`（文件不存在也如实 0，不假绿） |
| push ×3 | 盯构建80 / 回主人70 / 记忆体检40；右栏显示 `2/12`（清空后重压两条） |
| 审计（夹具） | 3 条 → `needs_review`；duplicate_ids=1、missing_time=1、too_short=1、secret_like=1；凭据原文不回显 |
| UI | 右栏焦点栈：分数/标题/kind/×；审计行「干净 · 记录0 · 源 …」 |
| 能力数 | 394（含 body_control） |

![焦点栈 + body_control 状态（APP 真机右栏）](../assets/app-focus-body.png)

## 四、边界（说死）

1. 焦点栈在 **console-server 进程内存**（重启清空）；只落 push/pop/clear 审计，不做恢复；
2. 审计只覆盖 `state/memory_bank.jsonl` 的印章行（现在文件不存在 → 0 条 clean，不伪造）；
3. `audit` 只体检调用方给的记录，不读别的记忆库、不改记录；要接 memory_manager DB 另做；
4. UI 只读+pop；push 由主循环/API 调用，不提供手工输入；
5. 统一门零作用域，不写盘；审计追加由服务端 trusted-owner 做。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_focus_stack.py
# GET/POST http://127.0.0.1:8766/api/focus
# CDP: window.__focusRefresh()
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
