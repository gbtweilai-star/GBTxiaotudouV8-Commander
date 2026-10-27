import SwiftUI
import AVFoundation
import MetalKit
import Vision

/// 主界面：选镜头 / 选预设 / 调参数 / 投到外屏。
/// 对齐 SpaceBeam 的 MainActivity 面板（9 个预设 + 滑杆 + 摄像头选择）。
struct ContentView: View {
    @StateObject private var camera = CameraController()
    @StateObject private var renderer = KaleidoscopeRenderer()   // class 要 ObservableObject + StateObject
    @State private var display: ExternalDisplay?      // boot() 里用真实渲染器创建
    @State private var segments: Double = 2
    @State private var rotation: Double = 0
    @State private var zoom: Double = 1.0
    @State private var useHandDriver = false
    @StateObject private var store = PresetStore()
    @StateObject private var recorder = Recorder()



    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                previewCard
                lensPicker
                presetRow
                sliders
                actionRow
            }
            .padding()
            .navigationTitle("SpaceBeamLite")
            .onAppear(perform: boot)
        }
    }

    // MARK: - 子视图

    private var previewCard: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 14).fill(.black)
            Text(camera.running ? "相机运行中 \(renderer.params.aspect > 0 ? "" : "")" : "点下方启动相机")
                .foregroundStyle(.white.opacity(0.6))
            if display?.isAttached == true {
                Text("已投到外屏").font(.caption).foregroundStyle(.green)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                    .padding(8)
            }
        }
        .frame(height: 220)
    }

    private var lensPicker: some View {
        Picker("镜头", selection: Binding(
            get: { camera.current?.id ?? "" },
            set: { id in
                if let l = camera.lenses.first(where: { $0.id == id }) {
                    camera.switchTo(l)
                }
            })) {
            ForEach(camera.lenses) { l in
                Text(l.name).tag(l.id)
            }
        }
        .pickerStyle(.segmented)
    }

    private var presetRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(store.presets) { p in
                    Button(p.name) {
                        segments = p.segments; rotation = p.rotation; zoom = p.zoom
                        renderer.params.segments = Float(p.segments)
                        renderer.params.rotation = Float(p.rotation)
                        renderer.params.zoom = Float(p.zoom)
                        if let id = p.lensID,
                           let l = camera.lenses.first(where: { $0.id == id }) {
                            camera.switchTo(l)
                        }
                    }
                    .buttonStyle(.bordered)
                    .tint(abs(segments - p.segments) < 0.01 ? .accentColor : .gray)
                }
                Button("＋存当前") {
                    store.add(Preset(name: "我的 \(store.presets.count + 1)",
                                     segments: segments, rotation: rotation,
                                     zoom: zoom, lensID: camera.current?.id))
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private var sliders: some View {
        VStack {
            HStack { Text("旋转"); Slider(value: $rotation, in: 0...(2 * .pi)) }
                .onChange(of: rotation) { _, v in renderer.params.rotation = Float(v) }
            HStack { Text("缩放"); Slider(value: $zoom, in: 0.4...2.5) }
                .onChange(of: zoom) { _, v in renderer.params.zoom = Float(v) }
            Toggle("手势驱动（Vision 手部关键点）", isOn: $useHandDriver)
        }
        .font(.footnote)
    }

    private var actionRow: some View {
        HStack {
            Button(camera.running ? "停止" : "启动相机") {
                camera.running ? camera.stop() : camera.start()
            }
            .buttonStyle(.borderedProminent)

            Button(recorder.recording ? "停止录制" : "录制") {
                Recorder.ensurePhotoPermission { ok in
                    if ok { recorder.toggle() } else { recorder.lastError = "没有相册权限" }
                }
            }
            .buttonStyle(.bordered)
            .tint(recorder.recording ? .red : .gray)

            Button(display?.isAttached == true ? "断开外屏" : "投到外屏") {
                if display?.isAttached == true {
                    display?.detach()
                } else if UIScreen.screens.count > 1 {
                    display?.attach(to: UIScreen.screens[1])
                }
            }
            .buttonStyle(.bordered)
        }
    }

    // MARK: - 启动

    private func boot() {
        camera.discover()
        let ex = ExternalDisplay(renderer: renderer)
        display = ex
        camera.onFrame = { buf in
            renderer.update(sampleBuffer: buf)
            if useHandDriver { HandDriver.shared.feed(buf) { hand in
                if let hand { renderer.params.rotation = Float(hand) }
            } }
        }
        if UIScreen.screens.count > 1 { ex.attach(to: UIScreen.screens[1]) }
    }
}
