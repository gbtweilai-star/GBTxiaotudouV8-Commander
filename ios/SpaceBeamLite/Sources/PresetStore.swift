import Foundation

/// 预设：段数 / 旋转 / 缩放 / 镜头，存 UserDefaults。
/// 对齐 SpaceBeam 的 9 个预设按钮（它把预设写进 assets，我们存 JSON）。
struct Preset: Codable, Identifiable, Equatable {
    var id = UUID()
    var name: String
    var segments: Double
    var rotation: Double
    var zoom: Double
    var lensID: String?
}

final class PresetStore: ObservableObject {
    @Published var presets: [Preset] = []
    private let key = "spacebeam.presets"

    init() { load() }

    func load() {
        guard let data = UserDefaults.standard.data(forKey: key),
              let list = try? JSONDecoder().decode([Preset].self, from: data) else {
            presets = PresetStore.defaults; return
        }
        presets = list.isEmpty ? PresetStore.defaults : list
    }

    func save() {
        if let data = try? JSONEncoder().encode(presets) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }

    func add(_ p: Preset) { presets.append(p); save() }
    func remove(at i: Int) { guard presets.indices.contains(i) else { return }
        presets.remove(at: i); save() }

    static let defaults: [Preset] = [
        .init(name: "2×2",  segments: 2, rotation: 0, zoom: 1.0),
        .init(name: "3×3",  segments: 3, rotation: 0, zoom: 1.0),
        .init(name: "4 向", segments: 4, rotation: 0, zoom: 1.0),
        .init(name: "6 向", segments: 6, rotation: 0, zoom: 1.0),
        .init(name: "8 向", segments: 8, rotation: 0, zoom: 1.0),
        .init(name: "慢旋", segments: 6, rotation: 0.4, zoom: 1.2),
        .init(name: "特写", segments: 3, rotation: 0, zoom: 1.8),
    ]
}
