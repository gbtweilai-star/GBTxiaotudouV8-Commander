# gbt-capability: train_recipe
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""训练配方与就绪闸：**七阶段配方 + 如实报缺什么**（蒸馏自 train-llm-from-scratch，只取流程核）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `FareedKhan-dev/train-llm-from-scratch`（#10 · 当周 +1,179★ ·
  LLM TRAINING）：「用纯 PyTorch 从数据、分词和 Transformer 预训练开始，一路手写实现 SFT、奖励模型、
  PPO、DPO、GRPO、评测和对话。」
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），只蒸馏**阶段流程**，
  不引用它的代码/超参/结果数字。
· **时间**：2026-09-28。
· **口径**：**本机零算力**（本仓既有结论）⇒ **不接真训练**。本件做的是训练这件事的
  **两件能真做的事**：① **就绪闸**（现读硬件/依赖/数据/磁盘，缺什么如实报）；
  ② **七阶段配方**（每阶段输入/输出/判据，照 `gbt-ai-anything` 五步法的口径写清）。

## 蒸馏判断：它的核里我们真缺哪块
| 它的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 真训练（预训练/SFT/RLHF） | 无 GPU、无数据、无预算 | **不接**（造了也是空壳） |
| **阶段流程与每步契约** | 五步法（拆/选/连/闸/固）在技能里 | **补成可调用的配方** |
| **训练前的就绪检查** | 无 | **补这块（本件）** |

## 硬规矩
1. **就绪闸说真话**：GPU 不在、依赖缺失、数据目录没有、磁盘不够 ⇒ 逐条如实报（**缺什么、谁能补**），
   **不因为"反正也不训"就跳过检查**。
2. **配方不含编造数字**：超参给的是**量级建议**且标注"待按硬件定"，绝不写"跑出来准确率xx"。
3. **实验账只增不删**：`train_recipe_ledger.jsonl` 追加式；每条带 `src`（谁在什么机器上量的）。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LEDGER = _ROOT / "state" / "train_recipe_ledger.jsonl"

STAGES = [
    {"n": 1, "stage": "数据", "in_": "原始语料（路径/来源）", "out": "清洗后语料 + 去重率读数",
     "判据": "每条语料可追来源（src）；重复率有数；不含私密/凭据（过 precommit-secret-scan）"},
    {"n": 2, "stage": "分词", "in_": "清洗后语料", "out": "tokenizer 文件 + 词表大小",
     "判据": "词表大小与语种匹配有理由；OOV 率有数；特殊 token 齐（pad/bos/eos）"},
    {"n": 3, "stage": "预训练", "in_": "token 流", "out": "基座权重 + loss 曲线",
     "判据": "loss 真下降（有曲线，不是印象）；显存峰值有数；能断点续训"},
    {"n": 4, "stage": "SFT", "in_": "指令数据（输入/输出对）", "out": "微调权重",
     "判据": "指令数据每条可追来源；过拟合有对照（留出集）；**不许拿训练集当验收集**"},
    {"n": 5, "stage": "奖励模型", "in_": "偏好对（A 比 B 好）", "out": "奖励模型 + 一致性读数",
     "判据": "标注者一致率有数；奖励模型在留出对上能过随机基线"},
    {"n": 6, "stage": "对齐（PPO/DPO/GRPO）", "in_": "SFT 权重 + 奖励/偏好", "out": "对齐后权重",
     "判据": "对齐前后**都要有读数**（退化必须看得见）；KL 约束有数；不做无对照的'更好'"},
    {"n": 7, "stage": "评测与对话", "in_": "对齐后权重", "out": "评测报告 + 可对话服务",
     "判据": "评测集**封存**（不许当训练用）；对话服务有真端口冒烟；失败样例留档"},
]


def _mod_ok(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:                                             # noqa: BLE001
        return False


def readiness(**_kw) -> dict:
    """**就绪闸**：现读依赖/GPU/数据/磁盘，缺什么如实报（缺什么、谁能补）。"""
    checks, blockers = {}, []
    torch_ok = _mod_ok("torch")
    checks["torch"] = torch_ok
    if not torch_ok:
        blockers.append({"缺": "torch（纯 PyTorch 路线的前置）", "谁能补": "主人（装包=出网）"})
    cuda = {"available": None, "why": "torch 不在 ⇒ 判不了（未验≠没有）"}
    if torch_ok:
        try:
            import torch                                       # noqa: PLC0415
            cuda = {"available": bool(torch.cuda.is_available()),
                    "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0}
        except Exception as exc:                               # noqa: BLE001
            cuda = {"available": None, "why": "调 torch.cuda 出错：%s" % type(exc).__name__}
    checks["cuda"] = cuda
    if cuda.get("available") is False:
        blockers.append({"缺": "GPU（本机零算力）", "谁能补": "主人（本机没有就是没有；真训要外购算力）"})
    try:
        free_gb = round(shutil.disk_usage(str(_ROOT)).free / (1 << 30), 1)
    except Exception:                                             # noqa: BLE001
        free_gb = None
    checks["磁盘余量_GB"] = free_gb
    if free_gb is not None and free_gb < 50:
        blockers.append({"缺": "磁盘（训练语料/权重动辄几十 GB，现读余 %.1f GB）" % free_gb,
                         "谁能补": "主人（先回收或换盘）"})
    data_candidates = [p for p in (_ROOT / "data", _ROOT / "datasets", _ROOT / "corpus")
                       if p.is_dir()]
    checks["语料目录"] = [str(p.relative_to(_ROOT)) for p in data_candidates] or []
    if not data_candidates:
        blockers.append({"缺": "语料目录（data/ 或 datasets/ 都不在）", "谁能补": "主人（给语料来源）"})
    return {"ok": not blockers, "op": "readiness", "checks": checks, "blockers": blockers,
            "verdict": ("就绪（可以进配方）" if not blockers
                        else "**不具真训条件**：下列缺口如实报——配方仍可出（三步照走），真训要补缺口"),
            "_口径": "未验≠没有：判不了的项标 None 并写明为什么；缺什么、谁能补，逐条写"}


def plan(target: str = "chat-model", scale: str = "量级建议（待按硬件定）", **_kw) -> dict:
    """七阶段配方：每阶段**输入/输出/判据**三件齐（照五步法口径），不含编造数字。"""
    return {"ok": True, "op": "plan", "target": target, "scale": scale, "stages": STAGES,
            "prereq": "先跑 `readiness`——缺口不清就开训 = 把混乱自动化（五步法开篇禁）",
            "_口径": "超参只给量级建议并标注待定；绝不写『跑出来准确率xx』这类没量过的数"}


def ledger(stage: str = "", reading: str = "", src: str = "", note: str = "", **_kw) -> dict:
    """实验账（追加式）：每条必须带 **src**（谁在什么机器上量的）——**没 src 不收**。"""
    if not str(stage or "").strip():
        return {"ok": False, "fail_closed": True, "error": "stage 要给（第几阶段）"}
    if not str(src or "").strip():
        return {"ok": False, "fail_closed": True,
                "error": "src 要给（哪台机器/哪次运行的读数）——**没出处的读数不收**"}
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage,
           "reading": reading, "src": src, "note": note[:200]}
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "ledger", "row": row}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "train_recipe", "tentacle": "train_recipe",
            "entry": "run_task('train_recipe', {...})",
            "ops": ["readiness", "plan", "ledger", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 FareedKhan-dev/train-llm-from-scratch"
                              "（#10 · +1,179★）——只取**七阶段流程**",
            "not_copied": "不引它的训练代码/超参/结果数字；**本机零算力 ⇒ 不接真训练**"
                          "（真训要外购算力，属主人决定）",
            "hard_rules": ["就绪闸说真话（缺 GPU/数据/磁盘逐条报，缺什么谁能补）",
                           "判不了的标 None + 写明原因（未验≠没有）",
                           "配方不含编造数字（超参只给量级 + 标注待定）",
                           "实验账没 src 不收（没出处的读数不收）"],
            "files": {"实验账": str(_LEDGER.relative_to(_ROOT))},
            "contract": [
                {"op": "readiness", "params": "—", "returns": "就绪读数 + 缺口清单（缺什么/谁能补）"},
                {"op": "plan", "params": "[target scale]", "returns": "七阶段（输入/输出/判据）"},
                {"op": "ledger", "params": "stage + reading + src", "returns": "入账（没 src 拒收）"},
            ]}


def run_op(op: str = "readiness", **params) -> dict:
    op = (op or "readiness").lower()
    for n, fn in (("readiness", readiness), ("plan", plan), ("ledger", ledger), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（readiness/plan/ledger/where）"}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="训练配方与就绪闸（train-llm-from-scratch 流程蒸馏）")
    ap.add_argument("cmd", nargs="?", default="readiness")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
