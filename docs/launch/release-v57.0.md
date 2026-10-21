## 这一版给了什么

**两件实物 + 一本可核对的账**：一个能直接加载的 40 骨机械臂 GLB、一个自包含的 2 万触手 3D 看件页，以及每一次能力调用都留痕的单门运行时。

| 项 | 现读读数 | 证据 |
|---|---|---|
| 能力位 / 域 | **341 位 / 30 域** | `data/capabilities.json`（由注册表现读生成，非手抄） |
| 逐位真跑 | **340 通过 / 0 失败 / 1 缺输入** | `docs/07-capability-proof.md` |
| 335 题基准 PASS45 | **99.10%（第 1 轮）/ 98.51%（第 2 轮）** | `docs/04-evaluation.md` |
| 多域回归 | 29 域 236 位：**221 ok · 15 要票 · 回归 0** | `docs/12-multidomain-monitor.md` |
| 反向调用云端算力 | 模型 `200·1.2s` ｜ 出图 **3/3·29.7s** ｜ 本机 CPU **321.1 GFLOP/s** ｜ 出片 **27.0s · 49,893 B · sha_match=true** | `docs/13-omni-plug.md` |

## 🦾 Omni-Arm（附件可下载）

- **`omni-arm-rigged.glb`** — 1 网格 / 1 蒙皮 / **40 骨** / **1,080 顶点** / 未绑 0 / 权重非归一 0 / 高 0.6002 m
- **`tentacle3d.html`** — 2 万触手 3D 看件页（自包含，双击即开，带骨架开关与资产自证）
- 八条自检 8/8 过，构建环境 Blender **4.2.16 LTS** · `blender_rc=0`（明细见 `arms/README.md`）

老实说一句：上游那几份设计稿**不能直接跑**（FK 只算 2D、IK 不是 CCD、骨架轴靠 `random` 不可复现、导出路径写死 `/mnt/data`），
这个 GLB 是重写实现的产物 —— 确定性规格 → Blender 建骨/建几何/绑权重 → GLB，所以它可复现、可自检。

## 30 秒自己验（零依赖、不需要模型权重）

```bash
git clone https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander && cd GBTxiaotudouV8-Commander
python demo.py "turn this Markdown into a PPT"
python -m gbt_commander stats
python -m unittest discover -s tests -q      # 21 条判据，含"编造能力位必须被拒"的负对照
```

## 已知缺口（不藏）

- **7.6B 权重不在本仓库**：`docs/05-deployment.md` 写了怎么用 vLLM serve。
- `codex_interrupt` 仍是 `needs_input`（上游串行化），**没算通过**。
- 意图词表只有 24 条，未覆盖的说法会退回 IDF 检索，CLI 会把两条路标清楚。

**不隶属任何厂商**：仓库里的 `tesla-optimus` 之类联想是别人的比喻，本项目与 Tesla 无任何关系。
