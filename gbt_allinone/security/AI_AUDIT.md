# AI 应用层旁路审计

这套审计只记录 GBT 自己明确接入的 AI 出口，不安装全局代理、不抓系统流量、
不读取其他进程，也不修改请求或响应。

## 记录内容

- 每次调用的 provider、模型、目标主机、HTTP 状态、耗时、重试序号；
- 消息数量、角色序列、字符数、内容 SHA-256；
- token usage（上游返回时记录）；
- 请求头名称，不记录请求头值；
- 错误只记录异常类型，不复制上游响应正文。

完整 prompt、完整回复、历史消息、Cookie、Authorization、API Key、密码、
私钥和环境变量值都不会写入 AI 审计。

## 存储与失效策略

- Windows 默认使用当前用户 DPAPI 加密整条记录，文件本身不可直接读取；
- 非 Windows 可通过 `GBT_AI_AUDIT_KEY` 提供 Fernet 密钥；
- 安全存储不可用时跳过审计记录，原 AI 调用继续执行；
- 审计写入失败不会阻断、重试或改变模型请求。

## 端点白名单

内置识别 OpenAI、DeepSeek、Kimi、智谱、Anthropic、Gemini、abliteration、
Tripo3D 的官方主机。自定义或本地端点（包括自定义 ASR）必须通过
`GBT_AI_AUDIT_HOSTS` 显式加入：

```text
GBT_AI_AUDIT_HOSTS=llm.example.internal,127.0.0.1
```

只有 GBT 自己的应用层出口代码会调用审计模块；白名单检查失败时直接不记录。
Tripo 的任务轮询属于高频只读查询，默认不写审计；生成、文件上传、绑骨和动画
等写操作会记录。ASR 只记录模型、文件大小、音频指纹和结果指纹，不保存音频
或转写正文。

## 读取

```python
from gbt_allinone.security import ai_audit

rows = ai_audit.query(limit=100)
status = ai_audit.status()
```

审计目录仅由框架本地查询使用，不通过协作网关、Web 服务或共享目录暴露。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
