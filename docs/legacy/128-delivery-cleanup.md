# 128 · 交付树清理：25,709 文件 / 7.6GB → 3,223 文件 / 176.9MB

## 一、发现
全量回归时发现交付树被并行写入运行时/重复树：
- 25,709 文件 / 7,663 MB；
- `state` 5GB、`tools/3d` 1.3GB、`tools/dsh-superagent`、`tools/repo`、`pyembed`、`dist`、`outputs`、`desktop`、`.archive` 等；
- 全量 `py_compile` 因 `__pycache__` 拒绝访问，不可信。

## 二、已清理（明确绝对路径校验后删）
- `state/`（大部分）
- `pyembed/`
- `dist/`
- `outputs/`
- `desktop/`
- `.archive/`
- `tools/3d/`
- `tools/llama/`（部分 DLL 被占用，未能全删）
- `tools/dsh-superagent/`
- `tools/repo/`
- `tools/git/`、`tools/gh/`、`git.zip`、`gh.zip`
- `tools/__pycache__/`
- 用户 `camera.mp4` 移到工作区 `.scratch/lead/camera-user.mp4`（未删）

## 三、结果
| 指标 | 清理前 | 清理后 |
|---|---|---|
| 文件数 | 25,709 | **3,224** |
| 体积 | 7,663 MB | **176.8 MB** |
| `.py` | 9,072 | **1,760** |
| `.md` | 1,548 | **465** |

## 四、锁定解除
- 用户确认后停止 `GBT小土豆V8桌面版`、`llama-server.exe`、桌面版 console-server；
- `state/` 与 `tools/llama/` 已彻底删除；
- 最终 `MANIFEST.json`：3217 条目 / 176.26MB / py_ok 1760 / size_bad 0 / sha256_bad 0 / extra 0 / pycache 0。

## 五、下一步
1. 只保留单一源码树 + 交付成片 + 必要第三方；
2. 重跑 compile/MANIFEST/final_check（本次已过）；
3. 运行时权重放回 `state/` 时会重新长大，需在启动脚本里隔离，不写回交付。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属


