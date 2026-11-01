# 109 · 原生 APP 里自动执行认知界面服务（不再手敲 :8766）

> 主人 2026-11-01 令：「服务重启后要跑 python tools/console-server.py --port 8766。
> 这个直接做到原生 APP 里面自动执行就好了。」
> 这一轮把自启挂进三条原生入口，并给出登录自启的一次性安装。

## 一、三条入口（都已挂）

| 入口 | 文件 | 做法 |
|---|---|---|
| **Electron 原生壳** | `holo_pet_w3/shell/console-service.cjs` + `shell/main.cjs` | `app.whenReady()` 里**建窗之前**调 `ensureConsoleServer()`；先在跑就直接用，没跑就用 `pyembed\python.exe` detached 起，最多等 12s 接管；失败只打日志、不拖垮壳启动 |
| **Python 桌面壳** | `gbt_allinone/console_service.py` + `app.py` | `main()` 先 `ensure_server()` 再 `run_gui()`；同样失败不牵连 |
| **一键启动器** | `启动-GBT.cmd` | 桥之后、GUI 之前插 `[2/4] ensuring cognitive console :8766`：探 `/api/state` → 没起就 `pyembed\python.exe tools\console-server.py` → 等 20s |

共同点：**幂等**（先探端口，不会起第二个）、**detached**（壳退了服务不跟着死）、**不假装**（起不来返回 `ok:false + reason`，日志里如实写）。

## 二、登录自启（开机后不用开 APP 也有）

- 仓库内包装器：`tools/autostart/GBT-console.cmd`（cd 到仓库 + pyembed 起服务，最小化）
- 一键安装：**双击 `tools/设置开机自启.cmd`** → 拷进 `%APPDATA%\...\Startup\GBT-console.cmd`
- 也可命令行：`python tools/install-autostart.py --install|--remove|--status`

**为什么不是我自己装好的**：本会话的写入策略不允许写 `Startup` 目录、也不允许写 HKCU Run（实测 `PermissionError` / `WinError 5`）。
所以 `install-autostart.py` 在无权限时**返回 exit 2 并说清楚**，不假装成功 —— 主人双击一次即可（用户态执行不受此限）。

## 三、实测（真起真停）

```
1) 先停掉手动起的服务 → /api/state 已离线（URLError）
2) 调 ensure_server()（与 Electron/Python 壳同一条逻辑）
   → [console] 认知界面服务已自启（等了 981 ms）
   → {'ok': True, 'already': False, 'pid': 3028, 'caps': 385}
3) 第二次调用 → {'ok': True, 'already': True, 'caps': 385}（幂等，没起第二个）
4) Electron 侧同一模块：node require + ensureConsoleServer()
   → {"ok":true,"already":true,"caps":385,"port":8766}
5) tests/test_console_service.py ALL OK：
   隔离端口 18766 真起（caps 385）→ 真停 → 端口离线 → 8766 恢复在线；
   三条入口静态检查全过。
```

## 四、边界（如实）

- **引擎（llama-server）仍单独启动**：`tools/engine-on.cmd`。认知界面/3D 不需要它，只有「对话」要；
  这一轮没有把 5.2GB 权重塞进壳启动路径（会让开 APP 变慢），需要的话可另加「按需起引擎」按钮；
- Electron 自启只做了模块级验证（`node --check` + `require` + `ensure`），没有整壳拉起
  （本机 Electron 探针有已知 GPU/环境问题，见 `holo_pet_w3/package.json` 的 `comment_probe_env`）；
- 登录自启需要主人双击一次（沙箱不能代写 Startup）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
