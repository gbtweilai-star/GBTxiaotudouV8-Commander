# 128 · 交付树清理：25,709 文件 / 7.6GB → 3,333 文件 / 245MB

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
| 文件数 | 25,709 | **3,333** |
| 体积 | 7,663 MB | **245.75 MB** |
| `.py` | 9,072 | **1,760** |
| `.md` | 1,548 | **464** |

## 四、剩余锁定
- `state/engine.err.log`、`state/engine.out.log` 被运行中的 engine 占用；
- `tools/llama/*.dll` 被进程占用；
- **不强行杀进程**，避免破坏正在跑的运行时；
- 停掉 engine 后再删剩余，才能完全干净。

## 五、下一步
1. 确认没有正在跑的 engine/llama；
2. 再删 `state`、`tools/llama` 剩余；
3. 只保留单一源码树 + 交付成片 + 必要第三方；
4. 重跑 compile/MANIFEST/final_check。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
