# 172 · GBT天真 i2v_svd 真图生视频节点/API

## 一、节点
- 名称：`i2v_svd`
- 位置：`gbt_allinone/tools/comfy_nodes_extra.py`
- 引擎：本地 SVD-XT，CPU fp32（fp16 在 CPU 不可用）
- 权重：`vendor/hf/svd-xt-fp16`
- 输入：`image, out, frames, width, height, steps, fps, seed, motion`
- 输出：真运动 MP4
- 不碰 ComfyUI/云端

## 二、节点实测
```
2 帧 / 128×256 / 1 步 / 8fps
load 29.09s
generation 63.22s
out node-i2v-test.mp4 (10,031 B)
ok=True
```

## 三、桌面 API
`POST /api/tianzhen`
```json
{"op":"i2v_svd","image":"...closeup.png","out":"...api-i2v-test.mp4",
 "frames":2,"width":128,"height":256,"steps":1,"fps":8}
```
实测：
- `ok=true`
- load 58.58s
- generation 71.36s
- 10,031 B
- 端口测试用 8767；主服务 8766 需重启后加载新代码

## 四、链路
```
GBT天真 i2v_svd 节点
→ native_t2i_worker（op=i2v_svd）
→ native_t2i_bridge
→ /api/tianzhen
```

## 五、边界
- CPU 很慢：2帧约 1 分钟，8帧约 7-11 分钟；
- 输出为循环真帧视频，不是全片新生成；
- 分辨率默认 256×448；
- 不是秋叶权重。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
