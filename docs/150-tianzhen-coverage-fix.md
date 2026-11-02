# 150 · 天真 coverage 口径对齐：不再虚报 traditional 缺口

## 一、问题
桌面 `/api/tianzhen?op=coverage` 原来用 `comfy_native._op_coverage` 自己的简化分类器：
- 把 3D/模型名误塞进 traditional；
- 报 `traditional` 缺口 177；
- 与 `tools/comfy-harvest.py` 的 **traditional 0** 矛盾。

## 二、修复
把 `_op_coverage._cat` 改成与 `comfy-harvest.py` 同口径：
1. 云端 Node 后缀；
2. 厂商/API 前缀；
3. 3D/几何 → unknown；
4. 模型面 hints；
5. 云端 hints；
6. traditional hints；
7. 其余 unknown。

## 三、实测
`GET /api/tianzhen?op=coverage`（桌面真实进程）：
```json
{"ok": true, "contract_total": 1000, "native_total": 148,
 "coverage": 0.148,
 "missing_by_cat": {
   "traditional": {"count": 0},
   "model": {"count": 402},
   "cloud": {"count": 365},
   "unknown": {"count": 85}}}
```
- **traditional 缺口 0**，与源码 parity/harvest 一致；
- 不再把 3D/模型误报成“可补传统算子”；
- 覆盖率仍是 **14.8%**，没有借修口径抬高。

## 四、边界
- 参照仍是核心面 1000，不是秋叶 1495；
- 402 模型 + 365 云端不接；
- 85 unknown 里多数是 3D/训练/硬件，不硬造。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
