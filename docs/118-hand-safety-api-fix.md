# 118 · API 安全闸修复：裸奔配置不再崩，结构化拒绝

## 一、问题
上一步发现：直接模块调用安全闸生效，但走万能插 `run_task` 时，
`pre_clamp=false` 先触发 `coding_discipline.prepare_payload` 的
`dict(payload)` ValueError，返回的是 Python 异常，不是安全拒绝。

## 二、修复
`coding_discipline.prepare_payload` 现在对 payload 做类型归一：
- `None` → `{}`
- `dict` → 浅拷贝
- `str` → `{"text": ...}`
- 其它 → `{"payload": ...}`

不再对非 dict 直接 `dict(...)` 崩掉。

## 三、实测（走 api.run_task）
| 项 | 结果 |
|---|---|
| 返回类型 | dict |
| status | **unsafe_rejected** |
| safety_guard | true |
| payload ValueError | 无 |
| 测试 | `tests/test_hand_safety_api.py` **ALL PASS** |

## 四、边界
- 安全闸仍是软件层；真机要硬件急停/力矩上限/看门狗；
- 摄像头未通；loopback 仿真。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
