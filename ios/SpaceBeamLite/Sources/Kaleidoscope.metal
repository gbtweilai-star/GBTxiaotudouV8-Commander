//
//  Kaleidoscope.metal
//  万花筒着色器 —— 对齐 SpaceBeam 的核心视觉（分段镜像 + 旋转 + 缩放）
//  原理：把 UV 转到极坐标，按扇区取模折叠，再采样原图。
//

#include <metal_stdlib>
using namespace metal;

struct VertexOut {
    float4 position [[position]];
    float2 uv;
};

// 全屏三角形，不需要顶点缓冲
vertex VertexOut vs_fullscreen(uint vid [[vertex_id]]) {
    float2 pos[3] = { float2(-1.0, -1.0), float2(3.0, -1.0), float2(-1.0, 3.0) };
    VertexOut out;
    out.position = float4(pos[vid], 0.0, 1.0);
    out.uv = pos[vid] * 0.5 + 0.5;
    return out;
}

struct Params {
    float segments;    // 段数：2 / 3 / 4 / 6 / 8
    float rotation;    // 弧度
    float zoom;        // 1.0 = 原始
    float aspect;      // 宽高比，避免拉伸
};

fragment float4 fs_kaleidoscope(VertexOut in [[stage_in]],
                                texture2d<float> src [[texture(0)]],
                                constant Params &p [[buffer(0)]]) {
    constexpr sampler s(address::clamp_to_edge, filter::linear);

    // 居中 + 修正宽高比
    float2 uv = in.uv - 0.5;
    uv.x *= p.aspect;

    // 旋转
    float c = cos(p.rotation), sn = sin(p.rotation);
    uv = float2(uv.x * c - uv.y * sn, uv.x * sn + uv.y * c);

    // 极坐标
    float r = length(uv);
    float a = atan2(uv.y, uv.x);

    // 扇区折叠：核心一行
    float seg = max(p.segments, 1.0);
    float sector = 6.2831853 / seg;
    a = fmod(a + sector * 0.5, sector);
    a = abs(a - sector * 0.5);

    // 镜像到另一侧，形成对称花瓣
    float2 k = float2(cos(a), sin(a)) * r / max(p.zoom, 0.001);
    k.x /= p.aspect;

    float2 sampleUV = k + 0.5;
    float4 col = src.sample(s, sampleUV);

    // 边缘轻微暗角，避免折边露白
    float v = smoothstep(0.75, 0.35, r);
    col.rgb *= mix(0.82, 1.0, v);
    return col;
}
