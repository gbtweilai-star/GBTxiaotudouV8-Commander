# 18 · 浏览器自动化 (`browser`)

> 3+ 能力位 · 原生浏览器 · Playwright · 穿透网
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 能力清单

| 能力位 | 说明 |
|---|---|
| `browser` | 浏览器自动化（需Playwright/Selenium） |
| `native_browser` | 原生浏览器（CDP直连，无驱动依赖） |
| `omni_web` | 穿透网（网页操作全能力） |
| `scrapling_cap` | 自适应抓取 |
| `page_scan` | 按绑定逐页并发扫 |

## 三种模式

| 模式 | 技术 | 优点 | 缺点 |
|---|---|---|---|
| **原生** | CDP直连 | 无驱动依赖、启动快 | 需Chrome/Edge |
| **Playwright** | 驱动 | 跨浏览器、稳定 | 需装浏览器 |
| **穿透网** | 混合 | 抗反爬 | 复杂 |

## API参考

### 原生浏览器（CDP）

```python
import gbt_allinone as gbt

# 启动
result = gbt.run_task("native_browser", {"op": "launch", "headless": False})
# 返回: {ok, ws_endpoint: "ws://127.0.0.1:9222/devtools/browser/..."}

# 打开网页
gbt.run_task("native_browser", {"op": "goto", "url": "https://example.com"})

# 截图
gbt.run_task("native_browser", {"op": "screenshot", "out": "shot.png"})

# 读文本
result = gbt.run_task("native_browser", {"op": "text", "selector": "body"})

# 点击
gbt.run_task("native_browser", {"op": "click", "selector": "#login-btn"})

# 输入
gbt.run_task("native_browser", {"op": "type", "selector": "#username", "text": "admin"})

# 执行JS
result = gbt.run_task("native_browser", {
    "op": "eval",
    "script": "document.title"
})

# 关闭
gbt.run_task("native_browser", {"op": "close"})
```

### Playwright模式

```python
result = gbt.run_task("browser", {
    "op": "goto",
    "url": "https://example.com",
    "engine": "playwright"
})
```

### 穿透网（omni_web）

```python
# 全能力网页操作
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

## 反爬对抗

| 手段 | 应对 |
|---|---|
| UA检测 | 真实UA池 |
| 指纹检测 | 真实浏览器指纹 |
| 验证码 | **不绕**（遵守边界） |
| 频率限制 | 退避重试 |

## 边界

- 不绕验证码
- 不撞库
- 不抓个人隐私
- 只操作授权目标

## 授权门

| 作用域 | 覆盖 |
|---|---|
| `browser_control` | 操控系统浏览器或自动化浏览器执行点击/输入 |

## 性能

| 操作 | 耗时 |
|---|---|
| 启动（CDP） | ~500ms |
| 打开网页 | ~800ms |
| 截图 | ~150ms |
| 点击 | ~100ms |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
