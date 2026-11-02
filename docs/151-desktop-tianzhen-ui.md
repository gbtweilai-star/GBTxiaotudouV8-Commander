# 151 · 桌面版天真 UI 入口（状态/覆盖）

## 一、加了什么
左栏新增「**天真**」分组：
- 「天真状态」→ `GET /api/tianzhen?op=status`
- 「天真覆盖」→ `GET /api/tianzhen?op=coverage`

结果复用居中模态框。

## 二、CDP 实测
页面 DOM：
```json
{"hand":["手部图片","手部视频","相机chunks","监视目录","录相机5s"],
 "tianzhen":["天真状态","天真覆盖"],
 "oldPanel":false}
```
点击「天真覆盖」后，模态框读到覆盖率 JSON（含 `missing_by_cat` / `trailing` 样本），不是死按钮。

## 三、接口侧
| 接口 | 读数 |
|---|---|
| `/api/tianzhen?op=status` | 200，PIL 13.0.0，nodes 165 |
| `/api/tianzhen?op=coverage` | 200，native 148 / 0.148，traditional 0 |
| `/api/tianzhen` POST workflow | 5 节点全过 gate |

## 四、边界
- UI 只读查询，不开放任意 workflow 从按钮跑；
- 真·秋叶 1495 快照没有；
- 模型/云端不接。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
