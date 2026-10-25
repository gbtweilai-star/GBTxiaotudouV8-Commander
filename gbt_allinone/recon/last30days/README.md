# last30days · 框架原生层（GBT小土豆V8）

> 这是 **框架原生代码**，不是技能。来源与改造记录见 `ATTRIBUTION.md`；
> 上游操作契约原文见 `UPSTREAM_SKILL.md`（仅参考，不注册进技能目录）。

## 调用

```bash
# 全框架根目录下执行
python -m gbt_allinone.recon.last30days.cli "<topic>" --emit=compact --save-dir <目录>

# 只报源可用性，不检索
python -m gbt_allinone.recon.last30days.cli "<topic>" --diagnose
```

## 零凭据即可用（公有 API）

`reddit`（公开搜索）· `hackernews` · `polymarket` · `youtube`（直抓字幕）

## 需要显式凭据（**无任何自动获取通路**）

| 源 | 环境变量 |
|---|---|
| GitHub | `GITHUB_TOKEN`（无则走匿名额度） |
| X/Twitter | `AUTH_TOKEN` + `CT0`，或 `XAI_API_KEY` |
| TikTok / Instagram / Pinterest / Threads / Reddit 增强 / YouTube 评论 | `SCRAPECREATORS_API_KEY` |
| BlueSky | `BSKY_HANDLE` + `BSKY_APP_PASSWORD` |
| Truth Social | `TRUTHSOCIAL_TOKEN` |
| 网页检索后端 | `BRAVE_API_KEY` / `EXA_API_KEY` / `SERPER_API_KEY` / `PARALLEL_API_KEY` |
| 推理后端 | `OPENAI_API_KEY` / `GEMINI_API_KEY` / `XAI_API_KEY` / `OPENROUTER_API_KEY` |
| xurl 通道 | `LAST30DAYS_X_BACKEND=xurl`（需显式开启） |

## 落盘

数据与配置全部落在框架 store 内（`GBT_STORE_DIR` 可覆写）：

- `store/last30days/research.db` —— 检索积累库
- `store/last30days/briefs/` —— 简报
- `store/last30days/config/.env` —— 引擎配置

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
