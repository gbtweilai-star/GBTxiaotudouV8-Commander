import AVFoundation
import UIKit

/// 摄像头枚举与切换 —— 对齐 SpaceBeam 的 enumerateCameras()。
/// 关键点：把「后置广角 / 超广角 / 长焦」按焦距排出来，用户能像 SpaceBeam 一样切。
final class CameraController: NSObject, ObservableObject {

    struct Lens: Identifiable, Hashable {
        let id: String          // uniqueID
        let name: String        // Back / Ultrawide / Telephoto
        let deviceType: AVCaptureDevice.DeviceType
        let position: AVCaptureDevice.Position
        let focalLength: Float
    }

    /// 给外部（渲染器）提供的帧回调
    var onFrame: ((CMSampleBuffer) -> Void)?

    private let session = AVCaptureSession()
    private let queue = DispatchQueue(label: "camera.session")
    private var videoInput: AVCaptureDeviceInput?
    private let output = AVCaptureVideoDataOutput()

    @Published private(set) var lenses: [Lens] = []
    @Published private(set) var current: Lens?
    @Published private(set) var running = false

    // MARK: - 枚举

    /// iOS 没有 Camera2 的 cameraIdList；用 DiscoverySession 枚举，
    /// 再按焦距命名（与 SpaceBeam 的命名规则一致：最短=Ultrawide，最长=Telephoto）。
    func discover() {
        let types: [AVCaptureDevice.DeviceType] = [
            .builtInWideAngleCamera,      // 标准
            .builtInUltraWideCamera,      // 超广角
            .builtInTelephotoCamera       // 长焦
        ]
        let ds = AVCaptureDevice.DiscoverySession(
            deviceTypes: types, mediaType: .video, position: .unspecified)

        var found: [Lens] = []
        for d in ds.devices {
            let fl = d.activeFormat.videoFieldOfView   // 用作排序的近似值
            let name: String
            switch d.deviceType {
            case .builtInUltraWideCamera: name = "Ultrawide"
            case .builtInTelephotoCamera: name = "Telephoto"
            default: name = d.position == .front ? "Front" : "Wide"
            }
            found.append(Lens(id: d.uniqueID, name: name, deviceType: d.deviceType,
                              position: d.position, focalLength: fl))
        }
        // 后置优先，焦距（视场角）从小到大的顺序排
        found.sort { a, b in
            if a.position != b.position { return a.position == .back }
            return a.focalLength < b.focalLength
        }
        DispatchQueue.main.async {
            self.lenses = found
            if self.current == nil { self.current = found.first }
        }
    }

    // MARK: - 起停

    func start(lens: Lens? = nil) {
        queue.async { [weak self] in
            guard let self else { return }
            self.configureIfNeeded(lens ?? self.current)
            if !self.session.isRunning { self.session.startRunning() }
            DispatchQueue.main.async { self.running = true }
        }
    }

    func stop() {
        queue.async { [weak self] in
            guard let self else { return }
            if self.session.isRunning { self.session.stopRunning() }
            DispatchQueue.main.async { self.running = false }
        }
    }

    func switchTo(_ lens: Lens) {
        queue.async { [weak self] in
            guard let self else { return }
            self.configureIfNeeded(lens, force: true)
            DispatchQueue.main.async { self.current = lens }
        }
    }

    private func configureIfNeeded(_ lens: Lens?, force: Bool = false) {
        guard let lens,
              let device = AVCaptureDevice(uniqueID: lens.id) else { return }
        if !force, videoInput != nil { return }

        session.beginConfiguration()
        session.sessionPreset = .high

        if let old = videoInput { session.removeInput(old) }
        do {
            let input = try AVCaptureDeviceInput(device: device)
            if session.canAddInput(input) {
                session.addInput(input)
                videoInput = input
            }
        } catch {
            print("[camera] input failed: \(error)")
        }

        if output.delegate == nil {
            output.videoSettings = [
                kCVPixelBufferPixelFormatTypeKey as String:
                    Int(kCVPixelFormatType_32BGRA)
            ]
            output.alwaysDiscardsLateVideoFrames = true
            output.setSampleBufferDelegate(self, queue: DispatchQueue(label: "video.frames"))
            if session.canAddOutput(output) { session.addOutput(output) }
        }

        session.commitConfiguration()
    }
}

// MARK: - 帧回调

extension CameraController: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        onFrame?(sampleBuffer)
    }
}
