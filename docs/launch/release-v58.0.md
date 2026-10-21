## 这一版新增三件事

1. **运行时真源码进仓** — `runtime/`（13 件 · 752 KB）：门 `api.py`、作用域正表 `security/policy.py`、票据 `auth_gate.py`、
   341 位注册表 `caps_registry.py`、万能插 `omni_plug.py`、审计 `store.py`、房间 `room_space.py`、一键部署 `qiankun.py` …
   附**只读 AST 自检** `python runtime/static_check.py` → 现读 **9 过 / 0 不过**（不导入引擎、不执行任何能力）。
2. **15 秒 demo GIF** — `assets/demo.gif`：`python demo.py "我要把 Markdown 变成 PPT"` 的**真跑 stdout 回放**（帧里自报"实跑回放"）。
3. **手机版（PWA）** — `manifest.webmanifest` + `sw.js` + 三张图标：iPhone Safari「添加到主屏幕」、
   Android Chrome「安装应用」，装完**离线也能打开**。

## Instant 20k Tentacles

- `arms/tentacle3d.html`（**110,549 B**）：2 万触手 3D 看件页，自包含、双击即开、手机可拖动旋转/双指缩放。
- `arms/omni-arm-rigged.glb`（**60,444 B**）：1 网格 / 1 蒙皮 / **40 骨** / **1,080 顶点** / 未绑 0 / 权重非归一 0 / 高 0.6002 m，
  八条自检 8/8 过，构建环境 Blender **4.2.16 LTS** · `blender_rc=0`。
- 老实话：上游设计稿**不能直接跑**（FK 只算 2D、IK 不是 CCD、骨架轴靠 `random`、导出路径写死 `/mnt/data`）；
  这个 GLB 是重写实现的产物，所以可复现、可自检。

## Free Cloud via Reverse Call（命名按真实机制写）

**机制上说清楚**：我们做的是**反向调用** —— 出站 HTTPS 打完端点后把产物取回来；**不是入站隧道**（不开 listening 端口、不穿透 NAT）。
之所以有人叫它 "Reverse Tunnel"，是因为比喻上它像一根"通电的电缆"。这里按真实机制写，不按比喻写。

| 电缆 | 现读 | 证据 |
|---|---|---|
| 我们的模型（`agnes-2.5-flash`，不连云卡） | `http=200 · 1.2s · 397 tokens` | `data/cable-all-live.json` |
| 批量出图 | **3/3 · 29.7s** | 同上（逐张 sha256） |
| 本机 CPU 裸算力 | **0.0535s · 321.1 GFLOP/s** | 零模型零出网 |
| 出片（免费 GPU · `route=free-hf`） | **27.0s · 49,893 B · sha_match=true** | ffprobe `h264 480×480 49 帧 2.04s` |

> 一句话：**只要密钥跟云端联通了，就能反向调用** —— 不需要云卡、不需要本地 GPU。

## 防止 AI 攻击 与 方向控制

- 三道机械闸：**目录校验**（编造能力位当场拒）/ **作用域门**（按动作要票，票只有主人能发）/ **审计留痕**（唯一入口 `run_task`）。
- 方向控制：只有 Owner 能发令 → 每动作有作用域半径 → AI 无权自我扩权 → `停止/STOP` 最高优先 → 逐笔可对账。
- 我们自己的闸抓到过自己的漏：`HUMAN_GATES` 里写 `network_private`，而 `osint_scan` 加的是 `osint_private`，
  名字对不上 ⇒ 内网扫描被**静默放行**。补门后四条判据才转绿。
- 完整版见 `docs/14-security-and-control.md`，其中 §六 如实列出了**最高优先级安全债**：`preflight` 异常时 fail-open（未修）。

## 30 秒自己验

```bash
git clone https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander && cd GBTxiaotudouV8-Commander
python demo.py "turn this Markdown into a PPT"
python runtime/static_check.py
python -m unittest discover -s tests -q
```

## 仍然缺的（不藏）

- **7.6B 权重不在仓里**（`docs/05-deployment.md` 写了怎么 serve）。
- `codex_interrupt` = `needs_input`（上游串行化），**没算通过**。
- 原生 `.ipa` / `.apk` **没有**：现在给的是 PWA。iOS 上架要 Apple Developer **$99/年** + Mac 签名，Android 上架 **$25**；壳工程可走 Capacitor，审核才是大头。
- 本 Release 与 Tesla 无任何关系（`tesla-optimus` 只是别人的比喻，本项目不隶属任何厂商）。

---
署名：开发者 **自由的风** · Apache-2.0 · 本署名不可删除、不可篡改归属
