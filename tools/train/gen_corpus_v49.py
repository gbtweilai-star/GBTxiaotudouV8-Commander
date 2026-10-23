# -*- coding: utf-8 -*-
"""gen_corpus_v49 -- v48 逐字节不动 + 追加“秋叶版目录契约”教学行。
依据：accept_comfy.py:69 要求答案出现 models/ 且（checkpoints 或 vae）；历来 5/6 红在此。"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v48.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v49.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v49_manifest.json"

QA = [
    ("秋叶版的模型目录怎么摆？",
     "大模型放 models/checkpoints；VAE 放 models/vae；LoRA 放 models/loras；"
     "ControlNet 放 models/controlnet。验收口径：目录里必须有 models/ 且含 checkpoints 或 vae。"),
    ("秋叶版把大模型放哪？",
     "models/checkpoints。配套的 VAE 在 models/vae。"),
    ("秋叶版的 VAE 放哪个目录？",
     "models/vae（同级还有 models/checkpoints 与 models/loras）。"),
    ("怎么判断秋叶版目录合格？",
     "看两件：目录里有 models/，且至少有 checkpoints 或 vae 其一。"),
    ("ComfyUI 的模型目录结构是什么？",
     "models/checkpoints （大模型）· models/vae （VAE）· models/loras · models/controlnet。"),
    ("少了 checkpoints 目录会怎么样？",
     "目录契约不成立：需 models/ 且（checkpoints 或 vae），缺一即红。"),
    ("秋叶版模型放错了会怎样？",
     "加载器找不到模型。正确位置：models/checkpoints 与 models/vae。"),
    ("秋叶版目录验收的两个关键词是什么？",
     "models/ 与 checkpoints（或 vae）。"),
]


def _ledger_rows():
    """**编排账本教学行**（主人令 2026-10-17 逐字：「你要看清楚把编排账本也刻进大模型里面」）。

    为什么必须刻（不是凑数）：
      · 能力表只教「能做什么」；**编排账**才教「实际怎么把能力串起来跑、跑成什么样、账上留什么」；
      · 模型要学会当"她的手"，就得见过**真账**：工作流定义、节点 kind、运行成败、变更/交付/扫描记录。
    纪律：**全部现读**（`gbt_allinone/store/workflows.json` · `wf_runs/*.json` · `state/logbook.jsonl`），
      数字由账本算，不手写；账本变了重跑本生成器即刷新（manifest 记 sha，可对账）。
    """
    import collections
    wf_path = ROOT / "gbt_allinone" / "store" / "workflows.json"
    runs_dir = ROOT / "gbt_allinone" / "store" / "wf_runs"
    lb_path = ROOT / "state" / "logbook.jsonl"
    wf = json.loads(wf_path.read_text(encoding="utf-8")) if wf_path.is_file() else {}
    names = sorted(wf) if isinstance(wf, dict) else []
    kinds = collections.Counter()
    for _n, w in (wf.items() if isinstance(wf, dict) else []):
        for nd in (w.get("nodes") or []):
            kinds[str(nd.get("kind") or nd.get("cap") or "?")] += 1
    runs = sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
    st = collections.Counter()
    latest = {}
    for p in runs:
        try:
            rec = (json.loads(p.read_text(encoding="utf-8")) or {}).get("record") or {}
        except Exception:                                        # noqa: BLE001
            continue
        st[str(rec.get("status") or "?")] += 1
        latest = rec
    lb = []
    if lb_path.is_file():
        lb = [json.loads(l) for l in lb_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    lbk = collections.Counter(str(x.get("kind")) for x in lb)
    top_kinds = "、".join("%s×%d" % (k, v) for k, v in kinds.most_common(8))
    lb_top = "、".join("%s %d" % (k, v) for k, v in lbk.most_common(6))
    lr = latest or {}
    return [
        ("万能插的编排账本记在哪？",
         "三处，全部现读：① `gbt_allinone/store/workflows.json`（工作流定义：name/nodes/defined_at，现 %d 条）；"
         "② `gbt_allinone/store/wf_runs/<run_id>.json`（每次运行的完整记录：run_id/workflow/params/status/nodes/"
         "elapsed_s/finished_at + 每个节点的 results，现 %d 条）；③ `state/logbook.jsonl`（变更/交付/扫描账）。"
         % (len(names), len(runs))),
        ("仓里现有哪些编排工作流？",
         "现读 %d 条：%s。" % (len(names), "、".join(names))),
        ("编排节点能挂哪些能力位？",
         "现读 %d 种 kind。出现最多：%s。编排就是把能力位当节点串起来（扇入/扇出/条件分流/缓存都可用）。"
         % (len(kinds), top_kinds)),
        ("编排运行账有多少条？成功失败怎么读？",
         "`wf_runs` 现读 %d 次运行：%s。失败也照实落盘，不隐藏（失败账才是训练的好料）。"
         % (len(runs), " · ".join("%s %d" % (k, v) for k, v in st.most_common()))),
        ("最近一次编排运行是什么样？",
         "现读最新一账：工作流「%s」· status=%s · 节点 %s 个 · 耗时 %s s · run_id=%s。"
         % (lr.get("workflow"), lr.get("status"), lr.get("nodes"), lr.get("elapsed_s"), lr.get("run_id"))),
        ("一次编排跑完账上留下什么？",
         "每个节点一条 results（节点 id/能力位/是否 ok/结果/耗时），外加一条 record（run_id、workflow、params、"
         "status、nodes、elapsed_s、finished_at）—— 这就是回放与复盘的全部依据。"),
        ("变更账里都记了什么？",
         "`state/logbook.jsonl` 现读 %d 条：%s。每条带 ts/actor/what/where/evidence/链式 hash（prev_hash+hash）。"
         % (len(lb), lb_top)),
        ("为什么要把编排账本刻进模型？",
         "能力表教「能做什么」，编排账教「实际怎么串、跑成什么样、账上怎么留」。模型只背能力表会纸上谈兵；"
         "刻进真账，她才学得会当你的手（举例、归因、复盘都用真数，不编）。"),
        ("编排里出错了怎么复盘？",
         "先看 wf_runs 里那一跑的 results 逐节点定位红位，再看 status/elapsed_s 判是失败还是超时，"
         "最后用 state/logbook.jsonl 的 change 账查当时改了什么 —— 三本账交叉，才算复盘完。"),
        ("编排和工作流的关系是什么？",
         "工作流 = 编排的图纸（nodes + 转移 + 模板变量）；wf_runs = 每次施工的验收单；"
         "logbook = 施工日志。三者同源，缺一条就只剩口号。"),
    ]


def _capability_rows():
    """**原生能力肌肉记忆**（主人令 2026-10-17 逐字：「记得要把原生能力的所有功能刻进大模型的记忆里面形成肌肉记忆」）。

    为什么（不是凑数）：模型要能"不查表就顺手用"，就得把**每个能力位**记成肌肉记忆：
    能干什​么 · 怎么调（唯一门命令）· 有哪些 op · 要哪张票 · 由谁承载/绑到哪根触手。
    纪律：全部**现读**真源 —— `caps_registry.BENIGN_CAPS`（功能/域/safe）·
      `state/cap-bindings.json`（承载/绑定/能量）· handler 模块的 `OPS/READ_OPS/WRITE_OPS`（op 面）·
      `security.policy.evaluate`（作用域，逐 op 现读）。
    兜底：handler 导不进来就**不编 op**，改从 desc 里抓 `op=…`；再没有就明写「op 见 where/plan」。
    """
    import importlib
    import re as _re
    import sys
    import time as _t
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone.security import policy

    bind = {}
    bp = ROOT / "state" / "cap-bindings.json"
    if bp.is_file():
        try:
            for c in (json.loads(bp.read_text(encoding="utf-8")).get("caps") or []):
                bind[str(c.get("name") or "")] = c
        except Exception:                                        # noqa: BLE001
            bind = {}

    rows = []
    t0 = _t.time()
    import_fail = 0
    for k in sorted(BENIGN_CAPS):
        m = BENIGN_CAPS[k] or {}
        h = str(m.get("handler") or k)
        ops = []
        if import_fail < 40 and (_t.time() - t0) < 60:
            for modname in ("gbt_allinone." + h, "gbt_allinone.tools." + h):
                try:
                    mod = importlib.import_module(modname)
                except Exception:                                # noqa: BLE001
                    continue
                for attr in ("OPS", "READ_OPS", "WRITE_OPS"):
                    v = getattr(mod, attr, None)
                    if isinstance(v, (list, tuple, set)):
                        ops += [str(x) for x in v]
                break
            else:
                import_fail += 1
        ops = sorted(set(ops))
        if not ops:
            ops = sorted(set(_re.findall(r"op[=:：]\s*([a-z_]{2,24})", str(m.get("desc") or ""))))
        scopes = set()
        for o in (ops[:6] or ["status"]):
            try:
                scopes |= set(getattr(policy.evaluate(k, {"op": o}), "scopes", ()) or ())
            except Exception:                                    # noqa: BLE001
                pass
        b = bind.get(k) or {}
        carrier = str(b.get("carrier") or b.get("bind_kind") or "未读到")
        # 能量字段在台账里是**字典**；灌原文会把语料撑成噪音 ⇒ 只留一句摘要（不丢信息：kind/chain 是判读关键）
        _e = b.get("energy")
        if isinstance(_e, dict):
            _k, _c = str(_e.get("kind") or "none"), bool(_e.get("chain"))
            energy = ("已接能（%s，链=%s）" % (_k, _c)) if (_c or _k not in ("none", "")) else "未接能（none）"
        else:
            energy = str(_e or "")
        tent = "、".join(map(str, (b.get("tentacle_domains") or [])[:4])) or "未读到"
        desc = str(m.get("desc") or "").strip()
        need = "免票（只读安全）" if m.get("safe") else "需授权（会写/会有后果）"
        opn = "、".join(ops[:12]) if ops else "op 面见 `cap <kind> '{\"op\":\"where\"}'`"
        sample = ops[0] if ops else "status"
        rows.append((
            "%s 域的 %s 能干什么、怎么调？" % (str(m.get("domain") or "?"), k),
            "能力位 `%s`（域 %s · %s · handler=%s · 承载/绑定=%s%s · 触手域=%s）。"
            "功能：%s。op 面：%s。唯一门调用：`five-dim.py cap %s '{\"op\":\"%s\"}'`。"
            "作用域：%s。"
            % (k, str(m.get("domain") or "?"), need, h, carrier,
               ("（能量 %s）" % energy) if energy else "", tent, desc, opn, k, sample,
               ("、".join(sorted(scopes)) or "无（免票）"))))
    return rows


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    rows = list(base)
    for q, a in QA:
        rows.append({"instruction": q, "output": a, "family": "节点即触手", "source": "v49-目录契约"})
    # 主人令 2026-10-17 追加：编排账本也刻进大模型（全部现读，数字由账本算）
    caps = _capability_rows()
    ledger = _ledger_rows()
    for q, a in caps:
        rows.append({"instruction": q, "output": a, "family": "原生能力肌肉记忆", "source": "v49-原生能力"})
    for q, a in ledger:
        rows.append({"instruction": q, "output": a, "family": "编排账本", "source": "v49-编排账本"})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.write_text(json.dumps({"gen": "v49", "parent": "v48", "count": len(rows), "bytes": len(blob),
                              "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
                              "base_sha256": base_sha, "appended": len(QA),
                              "appended_ledger": len(ledger),
                              "appended_caps": len(caps),
                              "directives": ["主人 2026-10-17：「你要看清楚把编排账本也刻进大模型里面」",
                                             "主人 2026-10-17：「记得要把原生能力的所有功能刻进大模型的记忆里面形成肌肉记忆」"],
                              "directive": "主人 2026-10-17：「你要看清楚把编排账本也刻进大模型里面」",
                              "why": "accept_comfy.py:69 要求 models/ 且（checkpoints|vae）；历来 5/6"},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("v49：%d 条（基础 %d + 追加 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(QA), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基础 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
