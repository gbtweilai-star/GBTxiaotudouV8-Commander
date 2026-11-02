# 153 · 天真桌面 API 负例验证（fail-closed）

## 一、测了什么
真实桌面进程 `POST /api/tianzhen`：

1. 未知节点 workflow
```json
{"op":"run","workflow":{"nodes":[{"id":"x","node":"DefinitelyNotAComfyNode","inputs":{}}],"edges":[]}}
```
结果：
```json
{"ok": false, "error": "user_error: 白名单里没有这些节点：['DefinitelyNotAComfyNode']"}
```
HTTP 200 但业务 fail-closed，不执行。

2. 不允许的 op
```json
{"op":"delete_all"}
```
结果：**HTTP 400**。

3. 只读 coverage
```
GET /api/tianzhen?op=coverage
```
结果：**200**，native 148 / 0.148 / traditional 0。

## 二、结论
- 天真 API 不是无脑执行器；
- 未知节点不落盘、不跑；
- 非白名单 POST 直接 400；
- 只读查询正常。

## 三、边界
- 仍是核心面 1000 参照，不是秋叶 1495；
- 模型/云端不接；
- 负例通过不等于已一比一。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
