import UIKit
import MetalKit

/// 外接屏（HDMI 转接器 / AirPlay 接收端）上的全屏输出。
/// 对齐 SpaceBeam 的 ExternalDisplayHelper（DisplayManager + Presentation）。
///
/// iOS 的做法：监听 UIScreen.didConnect/didDisconnect，为外接屏建一个
/// **独立 UIWindow**（windowScene 绑定到那个 screen），把 MTKView 铺满。
final class ExternalDisplay {

    private var window: UIWindow?
    private var view: MTKView?
    private let renderer: KaleidoscopeRenderer

    init(renderer: KaleidoscopeRenderer) {
        self.renderer = renderer
        NotificationCenter.default.addObserver(
            self, selector: #selector(screensChanged),
            name: UIScreen.didConnectNotification, object: nil)
        NotificationCenter.default.addObserver(
            self, selector: #selector(screensChanged),
            name: UIScreen.didDisconnectNotification, object: nil)
    }

    @objc private func screensChanged() {
        // 有第二块屏就自动投上去，拔掉就收掉
        if UIScreen.screens.count > 1 {
            attach(to: UIScreen.screens[1])
        } else {
            detach()
        }
    }

    func attach(to screen: UIScreen) {
        detach()
        let win = UIWindow(frame: screen.bounds)
        // iOS 13+ 需要 windowScene；直接从 connectedScenes 里挑绑定到该 screen 的
        if let scene = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .first(where: { $0.screen === screen }) {
            win.windowScene = scene
        }
        let mtk = MTKView(frame: screen.bounds)
        mtk.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        mtk.isPaused = false
        mtk.enableSetNeedsDisplay = false
        win.addSubview(mtk)
        win.rootViewController = {
            let vc = UIViewController()
            vc.view.backgroundColor = .black
            vc.view.addSubview(mtk)
            return vc
        }()
        win.isHidden = false
        win.makeKeyAndVisible()      // 少了这句，部分机型外接屏黑屏
        renderer.attach(mtk)
        window = win
        view = mtk
        print("[display] 外接屏已连接：\(screen.bounds.size)")
    }

    func detach() {
        if let v = view { renderer.detach(v) }
        window?.isHidden = true
        window = nil
        view = nil
    }

    var isAttached: Bool { window != nil }
}
