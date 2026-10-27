import ReplayKit
import Photos
import UIKit

/// 录制 —— 对齐 SpaceBeam 的 MediaRecorder（它用 MediaCodec 录制 EGL 画面）。
/// iOS 用 ReplayKit 录「App 内画面」，包含万花筒输出；录完直接落相册。
final class Recorder: NSObject, ObservableObject {

    @Published private(set) var recording = false
    @Published var lastError: String?

    private let recorder = RPScreenRecorder.shared()

    func toggle() {
        recording ? stop() : start()
    }

    func start() {
        guard recorder.isAvailable else {
            lastError = "这台设备不支持录制（模拟器一定不行）"
            return
        }
        // 麦克风按需；投影演示通常不需要
        recorder.isMicrophoneEnabled = false
        recorder.startRecording { [weak self] error in
            DispatchQueue.main.async {
                if let error {
                    self?.lastError = "开始失败：\(error.localizedDescription)"
                } else {
                    self?.recording = true
                }
            }
        }
    }

    func stop() {
        recorder.stopRecording { [weak self] preview, error in
            guard let self else { return }
            if let error {
                DispatchQueue.main.async { self.lastError = "停止失败：\(error.localizedDescription)" }
                return
            }
            // 没有 preview（部分机型不给），就只结束录制
            guard let preview else {
                DispatchQueue.main.async { self.recording = false }
                return
            }
            preview.previewControllerDelegate = self
            DispatchQueue.main.async {
                self.recording = false
                // 交给系统的预览界面，用户点“存储”即进相册
                UIApplication.shared.connectedScenes
                    .compactMap { $0 as? UIWindowScene }
                    .first?.keyWindow?.rootViewController?
                    .present(preview, animated: true)
            }
        }
    }

    /// 权限：写相册（iOS 14+ 用 addOnly）
    static func ensurePhotoPermission(_ done: @escaping (Bool) -> Void) {
        PHPhotoLibrary.requestAuthorization(for: .addOnly) { st in
            DispatchQueue.main.async { done(st == .authorized || st == .limited) }
        }
    }
}

extension Recorder: RPPreviewViewControllerDelegate {
    func previewControllerDidFinish(_ previewController: RPPreviewViewController) {
        previewController.dismiss(animated: true)
    }
}

extension UIWindowScene {
    var keyWindow: UIWindow? {
        windows.first { $0.isKeyWindow } ?? windows.first
    }
}
