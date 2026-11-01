# 122 · 可提交包：时间分/环境分 + 修复 diff + 附件 + ZIP

> 主人 2026-11-02：「下一步」——报告模板再加时间分/环境分、修复 diff、证据附件，
> 并把「报告 + JSON + 证据 + 附件 + manifest」打成一个可直接提交的包。

## 一、CVSS 3.1 三段分（Base / Temporal / Environmental）

`bounty_core.cvss3()` 现在：
- **Base**：原有 8 个指标；
- **Temporal**：`E`（利用成熟度）× `RL`（修复级别）× `RC`（报告可信度）；
- **Environmental**：`M*`（modified 指标）+ `CR/IR/AR`（CIA 需求权重），按 3.1 规范裁剪后算。

实测：
```
9.8 Base（AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H）
+ E:P/RL:O/RC:C → Temporal 8.8（9.8×0.94×0.95）
+ CR:H/IR:H/AR:H → Environmental 9.8（CIA 已满权重）
```

## 二、修复 diff（可直接贴给 triage）

`add_finding(..., fix_diff="--- a/... +++ b/...")`，报告里渲染：```diff``` 块；
没给就明说「未提供补丁 diff：建议给出最小修复 diff，平台 triage 更快」——不假装有。

## 三、证据附件（图片可预览）

`attachments=[...]`：按扩展名识别 `image`/`file`，都带 sha256；
报告里图片用 `![name](path)` 渲染，其它文件列路径 + sha256（缺失会标"缺失"）。

## 四、可提交包（bundle）

`bounty.bundle(finding_id)` 产出：

```
outputs/bounty/<finding>/
  F-....md            # 报告
  F-....json          # 侧车（finding + program + report sha256）
  ev-<证据/附件文件>   # 拷贝进来的证据与附件
  manifest.json       # 每个文件 sha256 + bytes + 授权依据 + 提交提醒
outputs/bounty/<finding>-bundle.zip   # 上面整个目录压缩（带 zip sha256/bytes）
```

实测：目录 ✓ ZIP ✓ manifest sha256 ✓。

## 五、界面与接口

- `#bounty` 发现卡新增「**生成提交包**」按钮（生成后显示 ZIP 路径 + 文件数 + zip sha256）；
- 接口：`POST /api/bounty {"op":"bundle","finding":"F-..."}`；
- `add_finding` 透传 `fix_diff` / `attachments`。

## 六、边界（如实）

- Environmental 用 modified 指标 + CIA 需求权重，**未做**平台自定义权重；
- `CR/IR/AR` 乘后裁剪到 `[0,0.56]`，不改变 Scope 语义；
- 提交包不自动上传平台（提交仍是人/API 手工动作）。

## 七、下一步

1. 真实项目 JSON 导入 → 工作台跑一遍；
2. 报告接平台 API（可选、只读）；
3. 把靶场发现换成真实授权资产（需主人提供 scope）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
