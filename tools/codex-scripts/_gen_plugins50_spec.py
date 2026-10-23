"""生成 50 槽位云插件规格表（deploy/cloud-10/plugins50.json）—— 主人 2026-10-04 蓝图的单一真源。

蓝图（主人原话拆条）：
  · 图3 = Cloudflare Workers AI 云插件，**大模型与工作流主要部署面**；
  · 图4 = 自研修改原生大模型底座（Ninfer 式：专用推理引擎 + 单卡）⇒ 1 组；
  · 图6 = Laya 决策引擎（33ms 非自回归决策，RL 训出）⇒ 同 1 组；
  · 图5 = AI 短剧 / AI 电影 / AI 音乐三条工作流（及其操控/调节按键）⇒ 2 组；
  · 3 组 = 本机资产分类入云；4–5 组 = 备用；
  · 绑定：**每槽与其余 49 槽双向互绑**（50×49 = 2450 条有向边），组内、组间同权，随时可调任一部位；
  · 每槽一根触手 + 一个**永久邮箱**（注册用）。

本生成器只写**结构与绑定关系**；邮箱、云端发布、5090 底座属主人侧（在表里标 owner_side）。

用法：py -3.14 tools/codex-scripts/_gen_plugins50_spec.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "deploy" / "cloud-10" / "plugins50.json"

# 每组 10 槽：role=这槽承载什么；driver=绑哪根触手（**必须是活注册表里的能力位名**）；
# email=永久邮箱占位（主人侧建好后回填真值，本表只存占位说明，不存凭据）
GROUP1 = [
    ("自研原生大模型底座（图4 · Ninfer 式专用推理引擎 + 单卡）", "local_brain", "底座权重与推理引擎自持"),
    ("决策引擎 Laya（图6 · 33ms 非自回归 · RL 训出）", "control_loop", "决策不动手：动作仍走门"),
    ("自研模型第二副本（热备/量化档）", "llm_chat", "副本走统一密钥链"),
    ("模型权重与检查点仓（版本化）", "model_key_pool", "只存引用与摘要"),
    ("推理路由（本地→云→CLI 车道）", "brain_route", "意图→能力动态路由；车道由统一密钥链承载"),
    ("模型评测台（基准与回归）", "brain_health", "五维自检评分"),
    ("训练/微调配方（就绪闸 + 七阶段）", "train_recipe", "没 src 不收"),
    ("安全卸载/审查面（abliteration 通道）", "sec_llm", "独立通道，不混统一链"),
    ("模型服务守护（探活/重启/用量）", "svc_inspect", "只看不动"),
    ("模型台账（谁在用、用量、成本）", "event_ledger", "账本单一真源"),
]
GROUP2 = [
    ("AI 短剧工作流（脚本→分镜→素材→剪辑→成片）", "media_run", "三步一链，每步落真件"),
    ("AI 电影工作流（概念→剧本→镜头→声音→剪辑）", "media_pipeline", "镜像房间编排 + 自审"),
    ("AI 音乐工作流（词→编曲→音频→母带→发行）", "audio_mix", "两遍法 loudnorm"),
    ("剪辑引擎（时间线语义：轨/片/变速/转场）", "edit_pipeline", "真渲染 1080×1920"),
    ("动作镜头系统（10 运镜 × 4 机位）", "actioncam", "拍子表为唯一真相"),
    ("调色/外观库（词即指令）", "look_grade", "单帧试看→全片"),
    ("影片装配线（清单制·任意增删重制）", "filmkit", "manifest.json 唯一真相"),
    ("音轨抽取/音频件（8 格式）", "audio_extract", "产出即回读验证"),
    ("一句话→全链计划（节奏/帧率/调色/模板）", "one_shot", "只读：plan 不写盘"),
    ("素材许可账（无许可不进成品格）", "media_license", "source/license 空一律拒"),
]
GROUP3 = [
    ("本机文档/表格/文本资产分类入云", "datakit", "只读转换，结果从返回给"),
    ("全树资产索引（软链真身去重）", "asset_index", "find 不扫盘（17–22ms）"),
    ("记忆库（FTS5 秒搜）", "memory_manager", "索引增量，不整表清空"),
    ("Obsidian 永久记忆（只追加）", "obsidian_vault", "无删除路径"),
    ("记忆来源印章（防篡改）", "memory_bank", "trace 比 sha"),
    ("上下文归档（索引+检索层）", "context_vault", "只引用不复制"),
    ("资产单点损失体检", "asset_vault_freeze", "不加密不冻结"),
    ("文件卫生（家规自检+归位）", "file_hygiene", "散落/空壳/越界/缓存"),
    ("仓库读写面（万能触手·Web 六态）", "omni_web", "读源码/改文件（过门）"),
    ("资产↔触手穿透绑定（台账只增）", "tentacle_bind", "红点只剩断连一种"),
]
GROUP45 = [
    ("备用槽位（待主人指派承载）", "", "保留：不预置、不编用途"),
]


def build() -> dict:
    mods = []
    seq = 0
    for gi, rows in ((1, GROUP1), (2, GROUP2), (3, GROUP3)):
        for role, drv, why in rows:
            seq += 1
            mods.append({"seq": seq, "group": gi, "slot": "g%d-%02d" % (gi, seq),
                         "role": role, "local_driver": drv, "driver_why": why,
                         "email": {"needed": True, "kind": "永久邮箱（注册用）",
                                   "value": "<owner_side：主人侧建好回填，本表不存凭据>"},
                         "status": "spec"})
    for gi in (4, 5):
        for _ in range(10):
            seq += 1
            mods.append({"seq": seq, "group": gi, "slot": "g%d-%02d" % (gi, seq),
                         "role": GROUP45[0][0], "local_driver": "", "driver_why": GROUP45[0][2],
                         "email": {"needed": False, "kind": "备用槽（暂不注册）", "value": ""},
                         "status": "reserve"})
    n = len(mods)
    return {
        "spec": "plugins50",
        "made_by": "tools/codex-scripts/_gen_plugins50_spec.py",
        "note": "主人 2026-10-04 蓝图：图3(CF Workers AI) 部署面 · 图4 自研底座&图6 Laya ⇒ 1 组 · 图5 三条工作流+按键 ⇒ 2 组 · 本机资产分类 ⇒ 3 组 · 4–5 备用。",
        "groups": [
            {"id": 1, "name": "自研模型组", "carries": "图4 自研原生大模型底座 + 图6 Laya 决策引擎（**只这两类**）"},
            {"id": 2, "name": "工作流组", "carries": "图5 三条工作流 + 全部操控/调节按键（按键双向绑定见 surface_bind）"},
            {"id": 3, "name": "本机资产组", "carries": "本机文件/记忆/资产分类后入云"},
            {"id": 4, "name": "备用组 A", "carries": "保留（不预置）"},
            {"id": 5, "name": "备用组 B", "carries": "保留（不预置）"},
        ],
        "binding": {"rule": "每槽与其 49 槽双向互绑（组内组间同权，随时可调任一部位能力）",
                    "directed_expected": n * (n - 1), "undirected_expected": n * (n - 1) // 2,
                    "self_loop_expected": 0},
        "modules": mods,
    }


def main() -> int:
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    b = data["binding"]
    print("已写 %s（槽位 %d · 组 %d · 有向边 %d · 无向 %d）"
          % (OUT, len(data["modules"]), len(data["groups"]),
             b["directed_expected"], b["undirected_expected"]))
    for g in data["groups"]:
        got = [m for m in data["modules"] if m["group"] == g["id"]]
        print("  组%d %-8s %2d 槽 · %s" % (g["id"], g["name"], len(got), g["carries"][:44]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
