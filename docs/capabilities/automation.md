# 浏览器自动化 · `automation`（2 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `browser` | 只读 | 是 | `url` | `user_error` | 浏览器自动化入口（良性子集）。op=open/search/fetch/automate 走 browser_cap 三级后端；op=native（别名 deep/controller/cdp）走原生浏览器窗口 native_browser.py（Chrome DevTools… |
| `n8n_wf` | **需授权** | — | —（注册表：无必填） | `user_error` / `failed` | n8n 工作流控制（我们自己的自托管 n8n 2.30·数据在 ~/.n8n）：status/list 只读直连；export/import/active/hook 过 filesystem_write 门；hook 可 POST /webhook/gbt 触发 n8n 工作流—… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `browser`

- **域**：`automation`（浏览器自动化）
- **类型**：只读（不改状态、不出网） · **需参数**：是 —— 默认 op=open 必须要 url；只读路请写 op=native + action=status
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：`url` —— 默认 op=open 必须要 url；只读路请写 op=native + action=status
- **常见错误**：缺参 / 参数非法 → `user_error`（必填：`url`）
- **它做什么**：浏览器自动化入口（良性子集）。op=open/search/fetch/automate 走 browser_cap 三级后端；op=native（别名 deep/controller/cdp）走原生浏览器窗口 native_browser.py（Chrome DevTools Protocol，自带最小 RFC6455 客户端、零第三方依赖），动作放 action：status/list_tabs/get_title/get_url/get_text/dom_query/get_cookies/intercept_events/intercept_status 为只读免卡，launch/ensure/create_tab/close_tab/activate_tab/navigate/reload/back/forward/click_element/type_text/execute_script/inject_script/set_cookies/privacy_mode/intercept_requests/intercept_stop/pin_window 需 browser_control，screenshot 另需 filesystem_write
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap browser '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `n8n_wf`

- **域**：`automation`（浏览器自动化）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（注册表 `requires_params=false`；空载荷落到该位默认 op）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：n8n 工作流控制（我们自己的自托管 n8n 2.30·数据在 ~/.n8n）：status/list 只读直连；export/import/active/hook 过 filesystem_write 门；hook 可 POST /webhook/gbt 触发 n8n 工作流——「N8N 有的我们都有」的双向桥（n8n→能力网关 已导桥接工作流，框架→n8n 由本能力位负责）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap n8n_wf '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
