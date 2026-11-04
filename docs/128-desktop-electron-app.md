# 128 · 桌面 APP（Electron 窗口版）

日期：2026-11-02 · 截图：`desktop-app-window.png`（真实应用窗口内容，1920×1095）

## 交付物（桌面）
| 项 | 路径 |
|---|---|
| 桌面应用 | `C:\Users\Lenovo\...\Desktop\GBT小土豆V8桌面版\` |
| 启动程序 | `GBT小土豆V8.exe`（Electron 窗口，没有浏览器地址栏） |
| 快捷方式 | `桌面\GBT小土豆V8.lnk`（双击即开） |
| 内置数据 | `payload\pyembed`（Python 3.13）+ 服务 + 界面 + `payload\state` |
| 体积 | 416.9 MB / 2680 文件 |

## 行为
- 双击 exe/快捷方式：窗口打开，主进程先探测 `127.0.0.1:8766/api/ping`，不通就用内置 Python 拉起 `tools/console-server.py`，就绪后加载界面；
- 关闭窗口：退出应用并杀掉自己拉起的服务；
- 单实例锁：重复双击会聚焦已有窗口；
- 窗口最大化适配屏幕；外链用系统浏览器打开；菜单栏隐藏；
- 换模型：设置 ⚙ → 模型 → Base URL（OpenAI 兼容）/ API Key / 模型名 → 测试连接 → 保存。

## 其他包
- `GBT小土豆V8便携版/` + `GBT小土豆V8-portable.zip`（25.5MB）：浏览器版本，给别的机器或当备份。

## 注意
Electron 未签名，Windows SmartScreen 可能提示「未知发布者」→ 点「更多信息 → 仍要运行」。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
