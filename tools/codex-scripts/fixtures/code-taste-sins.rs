// 负对照 · Rust 侧（**只做行级判据**）

pub fn export_all(rows: &[Row]) -> String {
    dbg!(&rows);
    serde_json::to_string(rows).unwrap()
}
