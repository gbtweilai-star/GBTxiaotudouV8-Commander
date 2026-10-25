# 同化归属与改造记录（ATTRIBUTION）

> 本目录是 **GBT小土豆V8 框架原生代码**，不是外部技能、不挂在技能目录。
> 它的能力来源是一份 MIT 许可的开源引擎，按 V8 的「吞噬-消化-衍生」流程并入框架本体。

## 一、上游来源

| 项 | 值 |
|---|---|
| 引擎名 | `last30days`（v3.0.0 线） |
| 上游仓库 | https://github.com/mvanhorn/last30days-skill |
| 原始作者 | Matt Van Horn |
| 许可 | MIT（全文见本目录 `LICENSE`） |
| 原始形态 | Open Design / OpenClaw 技能（`SKILL.md` + `scripts/`） |
| 同化日期 | 2026-09-18 |
| 同化前指纹 | 75 文件 / 865,372 B · 目录树 sha256 前 16 位 `d852c7cc7cf15281` |

## 二、二次分发依赖

| 项 | 值 |
|---|---|
| 组件 | `@steipete/bird` v0.8.0 子集（X/Twitter GraphQL 检索） |
| 位置 | `engine/vendor/bird-search/` |
| 作者 | Peter Steinberger |
| 许可 | MIT（全文见 `engine/vendor/bird-search/LICENSE`） |
| 裁剪 | 只保留 `withSearch`（**只读检索**，无发推 / 上传 / 书签能力） |

## 三、同化改动清单（逐条可溯源）

### 3.1 整块移除 —— 凭据自动获取

| 移除项 | 原位置 | 理由 |
|---|---|---|
| `setup` 子命令 | `cli.py`（原 `scripts/last30days.py`） | 会用本机 GitHub PAT POST 给 `api.scrapecreators.com` 换 API key |
| `setup_wizard.py` | 原 `scripts/lib/` | 同上；含 `gh auth token` 调用与 Device Flow |
| `cookie_extract.py` | 原 `scripts/lib/` | 读本机 Firefox/Chrome/Safari cookie 库 |
| `chrome_cookies.py` | 原 `scripts/lib/` | macOS Keychain + openssl 解密 Chrome cookie |
| `safari_cookies.py` | 原 `scripts/lib/` | 解析 Safari 二进制 cookie 文件 |
| 浏览器分支 | `engine/vendor/bird-search/lib/cookies.js` | 改写为**只认环境变量**；导出 `extractCookiesFrom*` 保留为显式禁用桩 |

### 3.2 整块拆除 —— 休眠开关（当时不可达，仍按红线拆除）

| 移除项 | 原位置 | 理由 |
|---|---|---|
| `CODEX_AUTH_FILE` 常量 | `engine/env.py` | 指向宿主 `~/.codex/auth.json` |
| `load_codex_auth` / `get_codex_access_token` | `engine/env.py` | 读取宿主 Codex 登录令牌 |
| `extract_chatgpt_account_id` / `_decode_jwt_payload` / `_token_expired` | `engine/env.py` | 同上（JWT 解析） |
| `codex_auth_file` 字段 | `engine/env.py` `OpenAIAuth` | 同上 |
| `AUTH_SOURCE_CODEX` | `engine/env.py` | 上游已注释为 `intentionally skipped`，分支不可达 |
| `CODEX_RESPONSES_URL` + `AUTH_SOURCE_CODEX` 分支 | `engine/providers.py` | 会把宿主令牌 POST 给 `chatgpt.com/backend-api/codex/responses` |
| `_parse_codex_stream` | `engine/providers.py` | 只服务于上述通路 |

### 3.3 落盘锚点改道 —— 不写用户主目录

| 位置 | 上游默认 | 同化后 |
|---|---|---|
| `store.py` `DB_DIR` | `~/.local/share/last30days` | `<GBT store>/last30days` |
| `briefing.py` `BRIEFS_DIR` | `~/.local/share/last30days/briefs` | `<GBT store>/last30days/briefs` |
| `env.py` `CONFIG_DIR` | `~/.config/last30days` | `<GBT store>/last30days/config` |

三者统一经 `gbt_allinone._paths.STORE_DIR`（全框架 store 基址单一来源），
`GBT_STORE_DIR` 隔离语义原样生效。

### 3.4 结构调整 —— 依赖方向单一

| 改动 | 说明 |
|---|---|
| `scripts/lib/` → `engine/` | 去掉顶层 `lib` 包名，避免与宿主 `sys.path` 撞名 |
| `scripts/last30days.py` → `cli.py` | 去掉 `sys.path.insert` 引导，改包内相对导入 |
| 新增 `_pids.py` | 上游入口与 `lib/bird_x.py` 互相 `import`（循环）；拆出独立模块 |
| `from lib import X` → `from .engine import X` | 10 处 |
| `from last30days import ...` → `from .._pids import ...` | 2 处 |

## 四、未改动（原样保留）

检索主干与渲染层全部原样搬运，仅改导入与落盘锚点：

- 检索/规划：`pipeline.py` · `planner.py` · `resolve.py` · `fanout.py` · `competitors.py`
- 排序/聚合：`dedupe.py` · `cluster.py` · `fusion.py` · `rerank.py` · `relevance.py` · `signals.py`
- 渲染：`render.py` · `html_render.py` · `ui.py`
- 源适配：`hackernews.py` · `polymarket.py` · `reddit_public.py` · `reddit.py` ·
  `github.py` · `youtube_yt.py` · `bluesky.py` · `truthsocial.py` · `tiktok.py` ·
  `instagram.py` · `pinterest.py` · `threads.py` · `xquik.py` · `xai_x.py` ·
  `xurl_x.py` · `bird_x.py` · `xiaohongshu_api.py` · `reddit_enrich.py`
- 基座：`http.py`（含重试 / 429 退避 / URL 凭据打码）· `subproc.py` ·
  `schema.py` · `normalize.py` · `sources` 相关 · `preflight.py` · `quality_nudge.py` · `log.py`

## 五、红线（本目录持续约束）

1. 不保留任何「自动获取凭据」通路 —— 凭据一律经环境变量显式提供。
2. 不读取、不回传宿主凭据（Codex / 浏览器 cookie / Keychain）。
3. 不写用户主目录 —— 数据一律进框架 store。
4. 不新增外发域名 —— 外发面 = 各源自己的官方 API + 用户显式配置的 webhook。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
