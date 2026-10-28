# 18 · 浏览器与网页自动化 (`browser` / `omni_web` / `scrapling` / `page_scan` / `topic_web`)

> 5 能力位（横切 3 个域）· 浏览器入口 · 穿透网 · 自适应抓取 · 逐页扫 · 话题追踪
>
> ⚠️ **口径更正（2026-10-28 按注册表现读）**：本文旧版写了 `native_browser` 与
> `scrapling_cap` 两个能力位名。**注册表里没有这两个名字**——真名是
> `browser`（域 `automation`）与 `scrapling`（域 `recon`）。
> 按旧名调用只会得到 `unknown capability`。
> 核验：`python docs/native-capabilities/verify_cap.py show browser`
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单（逐位，取自注册表）

| 能力位 | 域 | 类型 | 说明 |
|---|---|---|---|
| `browser` | `automation` | 只读 | 浏览器自动化入口（良性子集）：`op=open/search/fetch/automate` 走 `browser_cap` 三条通道 |
| `omni_web` | `tentacle` | 只读 | 穿透网：网页操作全能力（点/填/抽，先看后动） |
| `scrapling` | `recon` | 只读 | 自适应抓取：多候选路径 + 结构指纹 + 相似度回找 |
| `page_scan` | `system` | 只读 | **按绑定逐页并发扫**：源 = `state/page-bindings.json`，按契约判色 |
| `topic_web` | `recon` | 只读 | 话题追踪：跨站跟踪一个话题的演进 |

---

## 三条通道（`browser` 的 op）

| op | 通道 | 说明 |
|---|---|---|
| `open` | 打开 | 起浏览器、开地址 |
| `search` | 搜索 | 走搜索引擎取结果 |
| `fetch` | 抓取 | 直接取页面内容（不起浏览器） |
| `automate` | 自动化 | 起浏览器做多步操作 |

---

## API参考

### 浏览器入口（browser）

```python
import gbt_allinone as gbt

# 打开
gbt.run_task("browser", {"op": "open", "url": "https://example.com"})

# 搜索
result = gbt.run_task("browser", {"op": "search", "q": "GBT小土豆V8"})
# 返回: {ok, results: [{title, url, snippet}]}

# 抓取（不起浏览器）
result = gbt.run_task("browser", {"op": "fetch", "url": "https://example.com"})
# 返回: {ok, html, text, status: 200}

# 多步自动化
result = gbt.run_task("browser", {
    "op": "automate",
    "steps": [
        {"act": "open", "url": "https://example.com"},
        {"act": "wait", "ms": 1000},
        {"act": "click", "text": "登录"},
        {"act": "type", "label": "用户名", "value": "admin"},
        {"act": "screenshot"}
    ]
})
```

### 穿透网（omni_web）

```python
result = gbt.run_task("omni_web", {
    "op": "act",
    "url": "https://example.com",
    "steps": [
        {"act": "goto", "url": "..."},
        {"act": "wait", "ms": 1000},
        {"act": "click", "text": "登录"},
        {"act": "type", "label": "用户名", "value": "admin"},
        {"act": "screenshot"}
    ]
})
```

**先看后动**：每步操作后截图确认，不盲点。

### 自适应抓取（scrapling）

```python
# 计划：多候选路径 + 结构指纹
gbt.run_task("scrapling", {"op": "plan", "url": "https://example.com/list"})

# 抓取
gbt.run_task("scrapling", {"op": "fetch", "url": "...", "selectors": [...]})

# 自适应解析（结构变了也能找回）
gbt.run_task("scrapling", {"op": "adaptive", "html": "...", "fingerprint": "..."})
```

**核心是 adaptive**：页面结构一变选择器就废 ⇒ **多候选路径 + 结构指纹 + 相似度回找**。

### 逐页扫（page_scan）

```python
result = gbt.run_task("page_scan", {})
# 源 = state/page-bindings.json 的逐页（页→落点→正向_能力位）
# 按契约判色：
#   绿 = 跑通
#   黄 = 需参数或需授权
#   红 = 触手断连
```

### 话题追踪（topic_web）

```python
result = gbt.run_task("topic_web", {"op": "track", "topic": "GBT小土豆V8"})
# 返回: {ok, mentions: [{site, url, at, snippet}], timeline: [...]}
```

---

## 反爬对抗

| 手段 | 应对 |
|---|---|
| UA 检测 | 真实 UA 池 |
| 指纹检测 | 真实浏览器指纹 |
| 验证码 | **不绕**（遵守边界） |
| 频率限制 | 退避重试 |

---

## 边界

- 不绕验证码
- 不撞库
- 不抓个人隐私
- 只操作授权目标
- 遵守 robots 与站点条款
- 每条数据可指回 URL 与时间

---

## 授权门

| 作用域 | 覆盖 |
|---|---|
| `browser_control` | 操控系统浏览器或自动化浏览器执行点击/输入 |

> `fetch` / `search` 这类不起浏览器的通道不碰 `browser_control`；
> `open` / `automate` 起浏览器动手，要票。

---

## 性能

| 操作 | 耗时 |
|---|---|
| 启动（CDP） | ~500ms |
| 打开网页 | ~800ms |
| 截图 | ~150ms |
| 点击 | ~100ms |
| `fetch`（不起浏览器） | ~300ms |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
