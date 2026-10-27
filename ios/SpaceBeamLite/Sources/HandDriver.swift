import Foundation
import Vision
import CoreVideo

/// 手部关键点 → 旋转参数（对齐 SpaceBeam 的 MediaPipe 手势驱动）
/// iOS 用 Vision 的 VNDetectHumanHandPoseRequest，取手腕到中指的连线角度当旋转。
final class HandDriver {
    static let shared = HandDriver()
    private let request = VNDetectHumanHandPoseRequest()
    private var busy = false
    private var lastAngle: CGFloat?

    /// 节流：每 ~100ms 处理一帧，别把相机帧全卡住
    func feed(_ sample: CMSampleBuffer, completion: @escaping (CGFloat?) -> Void) {
        if busy { return }
        busy = true
        defer { busy = false }
        guard let px = CMSampleBufferGetImageBuffer(sample) else {
            completion(lastAngle); return
        }
        let handler = VNImageRequestHandler(cvPixelBuffer: px, orientation: .up)
        do {
            try handler.perform([request])
            guard let obs = request.results?.first else { completion(nil); return }
            if let wrist = try? obs.recognizedPoint(.wrist),
               let mid = try? obs.recognizedPoint(.middlePIP),
               wrist.confidence > 0.3, mid.confidence > 0.3 {
                let dx = mid.location.x - wrist.location.x
                let dy = mid.location.y - wrist.location.y
                lastAngle = atan2(dy, dx)
            }
        } catch {
            // 读不到就是读不到，不编一个角度
        }
        completion(lastAngle)
    }
}
