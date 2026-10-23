# GBT小土豆 V8 · 3D 全息数字人面板

这是独立新增的 Web 全息层，不替换、不删除现有 Qt / Live2D 数字人。
旧版前端完整保留在 `archive/`，现有 `potato_pet` 后端能力也原样保留。

## 已接通

- 真实 Codex App Server：initialize、thread、turn、流式消息、审批与工具事件。
- 原有 LLM 降级：Codex 或外部模型暂时不可用时，面板仍能继续对话。
- 任务时间线：思考、命令、文件修改、计划和结果统一进入右侧执行轨迹。
- 3D 形象：**默认走本地**（`local-avatar-3d.js` + three.js + `assets/digital-human/raw/rig/model-rigged-anim.glb`）。
  🔴 旧路径 `assets/digital-human/tripo-human.glb` **已作废、全树不存在**，别再指它（改指上面的 `raw/` 分层真身）。
  读数现读（`plugins/gbt-master/tools/audit-avatar-baseline.py`）：3.22 MB · 22 关节 · T-pose 夹角 +1.6° · 顶点 16017 ·
  动作 idle 8.00s / walk 1.10s（walk 有髋部位移轨）· 贴图 3 张 2.23 MB。
  带弹簧骨的那件是另一份：`raw/rig/model-springs-hair.glb`（**7 根**：SkirtF/B/L/R + HairB/L/R）。
  星云（`xingyun_e2e.latest.js` + `/api/xingyun`）是**手动备用**，由形象区的切换按钮按需拉起。
  GLB 加载失败或 WebGL 不可用时显示 `#stage-fallback` 里的纯样式降级形象。
- 蓝牙设备总线：状态、BLE 扫描、经典蓝牙枚举、GATT 连接、读取和受控写入。
- 蓝牙写入保护：界面必须明确确认后，才会发送 `confirm: true`。
- 语音输入与播报：浏览器支持时使用 Web Speech API。
- 心智映射：读取 `mind_engine.pulse()`，驱动情绪、颜色和数字人状态。
- 五维状态图：脑、眼、耳、嘴、手直接读取心智、视觉、语音与触手真实状态。
- 状态详情只读：点击节点查看后端摘要与指标，不触发采集、执行或设备操作。
- 受限状态如实展示：采集会话不可用、框架 ASR 未配置等情况不会伪装成绿色在线。
- Notion 资料舱：只读显示最近页面、关键词搜索、页面正文与会议转录状态。
- Notion 凭证边界：前端不持有密钥，后端只从环境变量或 Windows DPAPI 加密文件读取。
- Notion 当前不提供创建、编辑、移动或删除接口，保持资料舱为只读知识入口。

## 启动

推荐双击：

```text
holo_pet/start-holo-panel.bat
```

也可以命令行运行：

```powershell
cd "$env:USERPROFILE\Desktop\GBT小土豆V8"
C:\Python310\python.exe holo_pet\launch_panel.py --host 127.0.0.1 --port 8765
```

启动器会先探测同端口面板。如果已经运行，就复用现有服务，不重复启动。

浏览器地址：

```text
http://127.0.0.1:8765/
```

## 3D 依赖

真实 GLB 渲染需要本地 three.js：

```powershell
cd "$env:USERPROFILE\Desktop\GBT小土豆V8\holo_pet"
npm install --no-audit --no-fund
```

未安装 three.js、WebGL 不可用或 GLB 加载失败时，形象区会显示同品牌全息降级形象。
对话、时间线、蓝牙设备总线、审批与语音功能不受影响，不会白屏。

## 蓝牙安全边界

- `status`、`scan`、`classic`：只读/枚举，可直接执行。
- `connect`、`read`：需要明确的设备地址和特征 UUID。
- `write`：先选择可写特征，再填写十六进制值，最后经过面板确认。
- 不猜设备协议、不扫描入侵、不修改已配对设备，也不记录完整私有数据。

所有调用仍通过 `gbt_allinone.api.run_task()`，保留原策略、审计和结果结构。

## 文件

| 文件 | 作用 |
| --- | --- |
| `index.html` | V2 全息面板结构 |
| `styles.css` | 品牌色、状态和动效 |
| `app.js` | Codex 流、审批、语音、蓝牙设备总线、形象源切换 |
| `local-avatar-3d.js` | 本地 three.js GLB 形象渲染（默认形象源） |
| `panel_server.py` | 本地桥接与静态资源服务 |
| `launch_panel.py` | 防重复启动器 |
| `start-holo-panel.bat` | Windows 双击入口 |
| `archive/` | 旧版前端归档 |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
