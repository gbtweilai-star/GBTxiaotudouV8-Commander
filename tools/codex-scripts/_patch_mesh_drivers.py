"""给 mesh.json 的每个云插件补 `local_driver`（插件 → 本机触手能力位）—— 单一真源改表。

主人令 2026-10-04：「每个插件都要触手互相绑定、资源共享互通」。
绑定必须**指向真实存在的能力位**（判据在 cloud-plugins.py verify 里逐名核注册表），
所以这里只写名字，存在性由判据把关；映射理由写进 `driver_why` 供人复核。

用法：py -3.14 tools/codex-scripts/_patch_mesh_drivers.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESH = ROOT / "deploy" / "cloud-10" / "mesh.json"

# 插件 seq → (本机触手能力位, 为什么是它)
DRIVERS = {
    1: ("llm_chat", "模型接入与推理路由 = 统一密钥链的 llm_chat（本机口）"),
    2: ("transformer", "上下文压缩与预算收口 = 变压器（LLMLingua/GPTCache 口径重做）"),
    3: ("sec_llm", "无审查通道 = 独立模型通道 sec_llm（不与统一链混用）"),
    4: ("scrapling", "联网检索与抓取 = Scrapling 自适应抓取（公网 + net_guard 边界）"),
    5: ("omni_web", "文件读写（对象存储）= 万能触手 Web 六态里的读源码/改文件面"),
    6: ("desktop_commander", "命令执行（隔离容器）= 桌面指挥官（终端 + 文件系统全能力）"),
    7: ("memory_manager", "记忆向量 = 记忆管理（FTS5 万能秒搜 + 能力位端出）"),
    8: ("obsidian_vault", "本地记忆 = Obsidian 永久记忆层（只追加、无删除路径）"),
    9: ("action_gate", "策略护栏 = 先看→动脑→执行前置闸（证据必须真在盘上）"),
    10: ("alerts", "可观测 = 框架声带（近期异常摘要 + 根源线索）"),
}


def main() -> int:
    mesh = json.loads(MESH.read_text(encoding="utf-8"))
    n = 0
    for m in mesh.get("modules") or []:
        seq = m.get("seq")
        if seq in DRIVERS:
            drv, why = DRIVERS[seq]
            m["local_driver"] = drv
            m["driver_why"] = why
            n += 1
    MESH.write_text(json.dumps(mesh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已补 local_driver：%d 个模块 → %s" % (n, MESH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
