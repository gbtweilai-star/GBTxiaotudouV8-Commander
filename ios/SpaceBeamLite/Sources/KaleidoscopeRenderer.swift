import MetalKit
import UIKit

/// 渲染一张「万花筒」纹理，并同时推到主屏与外接屏。
/// 对齐 SpaceBeam 的 KaleidoscopeRenderer + Presentation 组合。
final class KaleidoscopeRenderer: NSObject, MTKViewDelegate, ObservableObject {

    struct Params {
        var segments: Float = 2
        var rotation: Float = 0
        var zoom: Float = 1.0
        var aspect: Float = 16.0 / 9.0
    }

    var params = Params()

    private let device: MTLDevice
    private let queue: MTLCommandQueue
    private var pipeline: MTLRenderPipelineState?
    private var samplerState: MTLSamplerState?
    private var sourceTexture: MTLTexture?
    private var textureCache: CVMetalTextureCache?

    /// 每个 MTKView 一个 draw 回调目标
    private var views: [MTKView] = []

    init?() {
        guard let dev = MTLCreateSystemDefaultDevice(),
              let q = dev.makeCommandQueue() else { return nil }
        device = dev
        queue = q
        super.init()
        buildPipeline()
        CVMetalTextureCacheCreate(nil, nil, device, nil, &textureCache)
    }

    func attach(_ view: MTKView) {
        view.device = device
        view.colorPixelFormat = .bgra8Unorm
        view.framebufferOnly = true
        view.delegate = self
        view.preferredFramesPerSecond = 60
        if !views.contains(view) { views.append(view) }
    }

    func detach(_ view: MTKView) {
        views.removeAll { $0 === view }
    }

    private func buildPipeline() {
        // 着色器编译：本工程把 .metal 直接编进 main bundle
        guard let lib = device.makeDefaultLibrary(),
              let vfn = lib.makeFunction(name: "vs_fullscreen"),
              let ffn = lib.makeFunction(name: "fs_kaleidoscope") else {
            print("[render] shader 没编进来 —— 检查 .metal 是否在 Build Phases → Compile Sources")
            return
        }
        let desc = MTLRenderPipelineDescriptor()
        desc.vertexFunction = vfn
        desc.fragmentFunction = ffn
        desc.colorAttachments[0].pixelFormat = .bgra8Unorm
        pipeline = try? device.makeRenderPipelineState(descriptor: desc)
    }

    /// 相机帧 → 纹理
    func update(sampleBuffer: CMSampleBuffer) {
        guard let cache = textureCache,
              let px = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        let w = CVPixelBufferGetWidth(px), h = CVPixelBufferGetHeight(px)
        var cvTex: CVMetalTexture?
        CVMetalTextureCacheCreateTextureFromImage(nil, cache, px, nil,
                                                 .bgra8Unorm, w, h, 0, &cvTex)
        guard let cvTex, let tex = CVMetalTextureGetTexture(cvTex) else { return }
        sourceTexture = tex
        params.aspect = Float(w) / Float(max(h, 1))
    }

    func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}

    func draw(in view: MTKView) {
        guard let pipeline,
              let drawable = view.currentDrawable,
              let pass = view.currentRenderPassDescriptor,
              let cmd = queue.makeCommandBuffer(),
              let enc = cmd.makeRenderCommandEncoder(descriptor: pass) else { return }

        enc.setRenderPipelineState(pipeline)
        if let tex = sourceTexture {
            enc.setFragmentTexture(tex, index: 0)
        } else {
            // 还没帧：清屏，避免花屏
            enc.endEncoding()
            cmd.present(drawable)
            cmd.commit()
            return
        }
        var p = params
        enc.setFragmentBytes(&p, length: MemoryLayout<Params>.stride, index: 0)
        enc.drawPrimitives(type: .triangle, vertexStart: 0, vertexCount: 3)
        enc.endEncoding()
        cmd.present(drawable)
        cmd.commit()
    }
}
