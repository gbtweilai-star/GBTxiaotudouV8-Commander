# 183 · email_cap（通信域审计别名 → 真实 coze_mail）

> 主人 2026-11-03 截图：审计把 `email_cap` 报成 `having=0 / file=<未读到> / code=0 / doc=0 / test=0`。
> 结论不是“没有邮件能力”，是**审计只认字面名，漏了真实实现 `coze_mail`**。这次把别名接回真件。

## 一、真实对应

| 名 | 事实 |
|---|---|
| `coze_mail` | 通信域真实能力位：主人自有单一地址收发/整理；白名单默认空=全拒、confirm_token 绑定内容、正文不入档、独立通道 `coze_mail` |
| `email_cap` | **审计别名**，handler=`email_cap`，API 直接转 `coze_mail_cap`；不是第二套实现 |
| transport | 默认 `_UnwiredTransport`：没有 Coze 官方邮件端点/`ref:` 凭据时**如实 `needs_dependency`**，不伪造已连接 |
| 已实现 | 闸门、白名单、confirm_token、配额（日 20）、账本、通道写预检、状态 TTL |
| 未实现 | 真正出网/收信的后端注入（需要主人给端点/凭据，或后续接 SMTP/IMAP） |

真机 `email_cap status`：

```json
{"ok":false,"channel":"coze_mail","quota_limit":20,"connected":false,
 "status":"needs_dependency","detail":"backend_not_wired: ..."}
```

**`ok:false` 是如实报“后端未接线”，不是“能力不存在”。**

## 二、统一门/API/验收

- 注册表：`email_cap` 与 `coze_mail` 都在；
- `api.run_task("email_cap", {"op":"status"})` → 转 `coze_mail_cap`；
- 验收：`tests/test_email_cap.py`（别名、真实 channel、needs_dependency、不伪造 connected、配额/文档/payload）。

## 三、边界

1. 别名不等于第二套收发实现；只有 `coze_mail` 一套；
2. 没有 transport 就不发信、不收信，返回 `needs_dependency`；
3. 审计器若仍只按 `email_cap` 查文件/代码，会继续误报；正确口径是**查别名指向的 handler/模块**；
4. 真出网需要主人提供邮件端点/凭据；能力侧不存明文。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
