# 113 · 穿透扫描接真实扫描结果（不再是静态 safe 字段）

> 主人 2026-11-01：「可以继续」——上一版扫描图里的红/绿是按能力位的 `safe` 字段算的，
> 这一版改成**真跑 penetrating_cross_scan 的结果**驱动，扫的是什么就画什么。

## 一、数据链（全真跑）

```
tools/penetrating_cross_scan.py scan <target>
   └─ 步骤锁 6 步（decompose→spawn→hook→cross_validate→detect_omission→trace）
   └─ 每 unit 两路以上独立读，不一致第三路仲裁
        ↓  _report() 新增 unit_details（unit / status / detail），原来只有聚合数
tools/export-scan-data.py
   └─ 跑 bindings / registry / tree:gbt_allinone，写 state/scan-data.json
tools/gen-console-data.py
   └─ 把 scan（含 unit_details）并进 state/console-data.js
holo_pet_w3/console/scan3d.js
   └─ 节点 = unit_details，颜色 = 真实 status
```

## 二、颜色口径（不折叠）

| 状态 | 颜色 | 含义 |
|---|---|---|
| `agree` | 绿 | 两路以上读数一致（真通过） |
| `arbitrated` | 琥珀 | 两路不一致，第三路仲裁 → **真疑点** |
| `unhooked` / missing | 红 | 没钩住，如实报（绝不念成绿） |

HUD 显示：目标 / 扫过 N/total / 疑点 / 反思 / 穿透；右上角可切换真实扫描目标
（`bindings(1913) · registry(1) · tree:gbt_allinone(943)`）。

## 三、实测（真数据）

```
data-scan3d = ok:bindings:1913单元+0疑点   （bindings 全 agree）
data-scan3d-green=1913  amber=0  red=0
切到 registry（?target=registry）：
data-scan3d = ok:registry:1单元+1疑点      amber=1  ← 真实仲裁出来的疑点
tree:gbt_allinone = 943 单元全 agree
```

## 四、过程仍然完整

扫描线自上而下；遇非绿点：**大脑反思（环）→ 手穿透（纵深束）→ 扫描放慢 0.8s**；
一轮扫完**嘴巴报结论**；每轮开始**眼睛看**、**耳朵听**。五感面板写死「眼睛=视觉全谱·不止 OCR」+ 11 个真实视觉能力位。

## 五、边界（如实）

- 扫描结果是**导出时快照**（`state/scan-data.json`），不是每次打开页面现跑（现跑 bindings 210ms / tree 2.4s，要做实时可加按钮）；
- registry 只有 1 个 unit，所以切过去画面只有一个琥珀点——这是真实结果，不是画不出来；
- 当前三份真实扫描都 0 个 unhooked，所以没有红点；等真有没钩住的会直接变红。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
