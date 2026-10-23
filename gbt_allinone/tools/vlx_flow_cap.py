# -*- coding: utf-8 -*-
"""vlx_flow 能力位 —— VLX-Flow（om-ai-lab）的**流式观察 + 两层记忆**落到小土豆的眼上。

钢印：接自 https://github.com/om-ai-lab/VLX-Flow（七步法第一步落 _upstream/VLX-Flow/）。

## 体检（七步法第二步 · 只读体检三行 · 2026-10-11 现读）
  是什么：**streaming VLM for real-time general vision intelligence** —— 流式视觉语言模型，
          把视频切**连续块**逐块编码，**增量更新内部流记忆**；路线是
          offline video request -> full reprocessing -> answer
          改成 continuous observation -> **incremental memory update** -> instant interaction。
  依赖干净吗：**该仓当前一个代码文件都没有**（只有 README.md / README_zh.md / CONTRIBUTING.md /
          LICENSE / .gitignore + assets 里的 jpg/png/mp4），单分支 main、无 tag、
          全史里零个 .py/.json/.yaml/.toml/.txt/.sh；README 第 150-152 行写着
          「## Release · **Checkpoints: Coming soon**」⇒ **代码与权重都还没发布**。
          故**无供应链风险可言，也无代码可抄** —— 这一点如实写在这里。
  偏门在哪：它**真值钱的是设计**（流式分块 · 两层记忆 · cache-aware 增量推理），不是它的权重。
          按七步法「招一 纯逻辑直取」：取它的**架构契约**（零依赖）；
          按「招三 手用我们自己的」：**语义那一步用我们自己的模型链**，
          不逼任何人下它的权重、配它的环境。

## 落点（长在现有骨架上，**不重写眼**）
  视觉缓存那一层：复用 gbt_allinone/tentacle/vision_bus.py
      snapshot（快照+TTL）· _ahash/_grid_hashes（视觉指纹）· diff_regions（分格差异）
      **stream_record / stream_replay**（流记录与回放，落 store/vision/<name>.json）
  语义记忆那一层：**本件新增** —— 把一条流的**变化段**蒸馏成可检索的语义条目，
      落 store/vision/semantic_memory.jsonl（**只追加**）。

## op（读面免门 · 写面过 filesystem_write · 未列出 = fail-closed）
  status    在位/依赖/两层记忆三读数（只读）
  memory    两层记忆现状：视觉缓存 N 条流 + 语义 M 条（只读）
  timeline  读一条流的时间线（走 vision_bus.stream_replay）（只读）
  recall    按词检索语义记忆（只读）
  digest    把一条流的变化段蒸馏成语义条目（**写**；模型不可用时**如实报缺**，不编）
  remember  手工追加一条语义（**写**）

## 铁律
  · **不编**：模型取不到就回 needs_dependency，**绝不伪造语义**；
  · **只追加**：语义记忆不删不改（要改就再追加一条纠正）；
  · **如实标来源**：每条语义都带 stream 名与帧/时间范围，可回溯到那条流。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

_BASE = pathlib.Path(__file__).resolve().parent
_ROOT = _BASE.parents[1]


def _store() -> pathlib.Path:
    sd = os.environ.get("GBT_STORE_DIR")
    if sd:
        return pathlib.Path(sd)
    return _ROOT / "gbt_allinone" / "store"


def _vision_dir() -> pathlib.Path:
    return _store() / "vision"


def _mem_file() -> pathlib.Path:
    return _vision_dir() / "semantic_memory.jsonl"


_BUS_ERR = ""


def _bus():
    """取现有视觉总线（长在它上面，不重写）。

    🔴 2026-10-11 修：直接跑本文件时 sys.path[0] 是 gbt_allinone/tools/，
    **不是仓根** ⇒ 按包导入 gbt_allinone.tentacle.vision_bus 会失败
    （实测首跑 bus_available=false，而同一句在仓根下 import 是 OK 的）。
    ⇒ 先把仓根塞进 sys.path 再导；导不到也**如实把原因留在 _BUS_ERR** 里，
    不许静默返回 None（那会让"总线没接上"看起来像"总线没有"）。
    """
    global _BUS_ERR
    try:
        if str(_ROOT) not in sys.path:
            sys.path.insert(0, str(_ROOT))
        from gbt_allinone.tentacle import vision_bus as vb
        _BUS_ERR = ""
        return vb
    except Exception as e:  # noqa: BLE001
        _BUS_ERR = "%s: %s" % (type(e).__name__, e)
        return None


_OPS = ("status", "memory", "timeline", "recall", "digest", "remember")
_WRITE_OPS = ("digest", "remember")


def _read_mem() -> list:
    f = _mem_file()
    if not f.is_file():
        return []
    out = []
    for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:  # noqa: BLE001
            continue
    return out


def _append_mem(row: dict) -> None:
    d = _vision_dir()
    d.mkdir(parents=True, exist_ok=True)
    with _mem_file().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + chr(10))


def _stream_files() -> list:
    d = _vision_dir()
    if not d.is_dir():
        return []
    return sorted((f for f in d.glob("*.json") if f.name != "semantic_memory.jsonl"),
                  key=lambda f: f.stat().st_mtime, reverse=True)


def _op_status() -> dict:
    vb = _bus()
    files = _stream_files()
    mem = _read_mem()
    return {"ok": True, "capability": "vlx_flow", "in_position": True,
            "upstream": "om-ai-lab/VLX-Flow（**纯文档仓**，Checkpoints: Coming soon）",
            "visual_cache_layer": {
                "by": "gbt_allinone/tentacle/vision_bus.py",
                "bus_available": vb is not None,
                "bus_error": (_BUS_ERR or None),
                "streams": len(files),
                "latest_stream": (files[0].stem if files else None),
                "has_snapshot": bool(vb and hasattr(vb, "snapshot")),
                "has_stream_record": bool(vb and hasattr(vb, "stream_record")),
                "has_stream_replay": bool(vb and hasattr(vb, "stream_replay")),
                "has_grid_diff": bool(vb and hasattr(vb, "diff_regions")),
            },
            "semantic_memory_layer": {
                "by": "本件（新增）",
                "file": str(_mem_file()),
                "entries": len(mem),
                "append_only": True,
            },
            "ops": list(_OPS),
            "write_ops": list(_WRITE_OPS)}


def _op_memory() -> dict:
    files = _stream_files()
    mem = _read_mem()
    return {"ok": True, "visual_cache": {"streams": len(files),
                                          "names": [f.stem for f in files[:10]]},
            "semantic_memory": {"entries": len(mem),
                                "latest": (mem[-1] if mem else None)},
            "note": "视觉缓存=指纹与变化段（数字层）；语义记忆=把变化段翻成人话（可检索层）"}


def _op_timeline(payload: dict) -> dict:
    vb = _bus()
    if vb is None:
        return {"ok": False, "error": "needs_dependency: 取不到 vision_bus"}
    name = payload.get("stream") or None
    try:
        r = vb.stream_replay(name=name, limit=int(payload.get("limit") or 50))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "stream_replay 失败: %s" % e}
    return r if isinstance(r, dict) else {"ok": False, "error": "返回形状不认识"}


def _op_recall(payload: dict) -> dict:
    q = str(payload.get("q") or payload.get("query") or "").strip()
    mem = _read_mem()
    if not q:
        return {"ok": True, "q": "", "hits": mem[-10:], "total": len(mem)}
    hits = [m for m in mem if q in json.dumps(m, ensure_ascii=False)]
    return {"ok": True, "q": q, "hits": hits[-20:], "total": len(mem),
            "matched": len(hits)}


def _digest(payload: dict) -> dict:
    """把一条流的**变化段**蒸馏成语义条目。

    诚实的边界：语义那一步要模型 —— **取不到模型就回 needs_dependency，绝不伪造语义**。
    但**变化段本身是现成的**（vision_bus 已算好），所以本 op 即使没有模型也能
    落一条**结构化的**（非编造）记忆：它记的是**哪几段变了、多久、多少帧**。
    """
    vb = _bus()
    if vb is None:
        return {"ok": False, "error": "needs_dependency: 取不到 vision_bus"}
    name = payload.get("stream") or None
    try:
        rep = vb.stream_replay(name=name, limit=int(payload.get("limit") or 200))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "stream_replay 失败: %s" % e}
    if not isinstance(rep, dict):
        return {"ok": False, "error": "stream_replay 返回形状不认识"}
    segs = rep.get("segments") or []
    frames = rep.get("frames") or rep.get("timeline") or []
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "stream_digest",
        "stream": (rep.get("name") or name),
        "frames": len(frames) if isinstance(frames, list) else rep.get("frames"),
        "changes": rep.get("changes"),
        "segments": len(segs),
        "segment_spans": segs[:20],
        "source": "vision_bus.stream_replay",
        "semantic_by_model": False,
    }
    row["text"] = ("该流共 %s 帧、变化 %s 次、变化段 %s 段（%s）"
                   % (row["frames"], row["changes"], len(segs), row["stream"]))
    _append_mem(row)
    return {"ok": True, "appended": row,
            "note": ("**结构化记忆**（哪几段变了/多久/多少帧）—— 这一步不编；"
                     "要把它翻成自然语言叙述（semantic_by_model=true），本轮未做：模型链未接，如实报缺")}


def _remember(payload: dict) -> dict:
    text = str(payload.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "user_error: 缺 text"}
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "manual",
           "text": text, "source": "vlx_flow.remember", "semantic_by_model": False}
    _append_mem(row)
    return {"ok": True, "appended": row}


def run(payload: dict | None = None) -> dict:
    payload = dict(payload or {})
    op = str(payload.get("op") or "status").strip().lower()
    if op not in _OPS:
        return {"ok": False, "fail_closed": True,
                "error": "user_error: 未列出的 op（fail-closed）",
                "ops": list(_OPS), "write_ops": list(_WRITE_OPS)}
    if op == "status":
        return _op_status()
    if op == "memory":
        return _op_memory()
    if op == "timeline":
        return _op_timeline(payload)
    if op == "recall":
        return _op_recall(payload)
    if op == "digest":
        return _digest(payload)
    return _remember(payload)


def cli(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    payload = {}
    if argv:
        try:
            payload = json.loads(argv[0])
        except Exception:  # noqa: BLE001
            payload = {"op": argv[0]}
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
        except Exception:
            pass
    print(json.dumps(run(payload), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())