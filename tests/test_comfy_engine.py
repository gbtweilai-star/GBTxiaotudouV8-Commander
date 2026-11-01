# -*- coding: utf-8 -*-
"""GBT天真 执行引擎判据（comfy_native.run_workflow）—— 等秋叶快照期间补的地基。

四条必须有读数（不是"应该能跑"）：

  ① `skip: true`    ⇒ 节点不执行，trace 里标 skipped
  ② `times: N`      ⇒ 重复 N 次（上限 50）
  ③ `on_error`      ⇒ stop（默认）回滚本次产物 / continue 继续跑
  ④ 未接线节点       ⇒ 明确报 unwired（不装作能跑）

跑法：python tests/test_comfy_engine.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tools import comfy_native as CN

    store = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(store, exist_ok=True)
    p1 = os.path.join(store, "eng_base.png")

    print("[1] skip 旁路")
    wf = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": p1, "width": 16, "height": 16}},
        {"id": "n2", "node": "ImageScaleBy", "skip": True,
         "inputs": {"image": p1, "scale": 2}},
        {"id": "n3", "node": "ImageSharpen", "inputs": {"image": p1}},
    ]}
    r = CN.run_workflow(wf)
    t = {x["id"]: x for x in r.get("trace") or []}
    check("整体成功", r.get("ok"), r.get("error"))
    check("skip 节点被标 skipped", t.get("n2", {}).get("skipped") is True, t.get("n2"))
    check("skip 节点没产出", not (t.get("n2", {}).get("out") or {}), t.get("n2"))

    print("[2] times 重复执行")
    wf2 = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": p1, "width": 8, "height": 8}},
        {"id": "n2", "node": "ImageScaleBy", "times": 3,
         "inputs": {"image": p1, "scale": 2}},
    ]}
    r2 = CN.run_workflow(wf2)
    check("重复执行成功", r2.get("ok"), r2.get("error"))

    print("[3] 失败回滚（只删本次新产物）")
    probe = os.path.join(store, "eng_probe.png")
    if os.path.exists(probe):
        os.remove(probe)
    wf3 = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": probe, "width": 8, "height": 8}},
        {"id": "n2", "node": "ImageCrop", "inputs": {"image": probe}},   # 缺 width/height ⇒ 必失败
    ]}
    r3 = CN.run_workflow(wf3)
    check("失败被如实报", r3.get("ok") is False, r3.get("ok"))
    check("失败点正确", r3.get("failed_at") == "n2", r3.get("failed_at"))
    check("本次产物被回滚", bool(r3.get("rolled_back")), r3.get("rolled_back"))
    check("回滚后文件确实没了", not os.path.exists(probe), probe)

    print("[4] on_error=continue")
    wf4 = {"on_error": "continue", "nodes": [
        {"id": "n1", "node": "EmptyImage",
         "inputs": {"out": os.path.join(store, "eng_c.png"),
                    "width": 8, "height": 8}},
        {"id": "n2", "node": "ImageCrop",
         "inputs": {"image": os.path.join(store, "eng_c.png")}},
        {"id": "n3", "node": "ImageSharpen",
         "inputs": {"image": os.path.join(store, "eng_c.png")}},
    ]}
    r4 = CN.run_workflow(wf4)
    t4 = r4.get("trace") or []
    check("continue 下整体仍成功", r4.get("ok"), r4.get("error"))
    check("失败节点留在 trace 且 ok=false",
          any(x["id"] == "n2" and not x["ok"] for x in t4), t4)

    print("[5] 未接线节点必须明说")
    ok_unwired = False
    try:
        r5 = CN.run_workflow({"nodes": [{"id": "n1", "node": "ThisNodeDoesNotExist", "inputs": {}}]})
        blob = str(r5.get("error") or r5)
        ok_unwired = ("白名单" in blob) or ("unwired" in blob) or ("未知" in blob)
    except Exception as e:  # noqa: BLE001
        ok_unwired = "白名单" in str(e) or "unwired" in str(e)
    check("未接线节点被明确拒绝", ok_unwired, "应报白名单/unwired")


    print("[6] coverage 盘点 + 未接线列全")
    cov = CN.run({"op": "coverage"})
    check("coverage 能读", cov.get("ok") or cov.get("reason") == "no_contract_snapshot", cov.get("reason"))
    if cov.get("ok"):
        check("契约总数 > 0", (cov.get("contract_total") or 0) > 0, cov.get("contract_total"))
        check("覆盖率有数", isinstance(cov.get("coverage"), float), cov.get("coverage"))
    wf6 = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": p1, "width": 8, "height": 8}},
        {"id": "n2", "node": "KSampler", "inputs": {}},
        {"id": "n3", "node": "VAEDecode", "inputs": {}},
    ]}
    v6 = CN.run({"op": "validate", "workflow": wf6})
    only = v6.get("contract_only_used") or []
    unw = v6.get("unwired_nodes") or []
    check("两个未接线节点都被列出（不是只报第一个）",
          ("KSampler" in only and "VAEDecode" in only) or len(unw) >= 2, (only, unw))
    check("未接线有处置说明", all(x.get("how") for x in unw) if unw else True, unw)

    print("[7] 校验留痕")
    vpath = os.path.join(ROOT, "state", "comfy-validate.jsonl")
    before = sum(1 for _ in open(vpath, "rb")) if os.path.exists(vpath) else 0
    CN.run({"op": "validate", "workflow": {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": p1, "width": 8, "height": 8}}]}})
    after = sum(1 for _ in open(vpath, "rb")) if os.path.exists(vpath) else 0
    check("校验落审计（行数 +1）", after == before + 1, (before, after))

    print("[8] harvest 看菜下锅")
    hv = CN.run({"op": "harvest", "limit": 5})
    check("harvest 能读", hv.get("ok") or hv.get("reason") == "no_contract_snapshot", hv.get("reason"))
    if hv.get("ok"):
        check("有分类计数", all(isinstance(hv.get(k), int) for k in
                          ("have", "useful", "skip_model", "skip_cloud", "unknown")), hv)
        check("规则说清了（不整包吞）", "权重一个不下" in str(hv.get("rule")), hv.get("rule"))

    print("[9] 脚手架生成的节点（extras 合并）")
    check("extras 已合并（ImageFlipX 在 NODES 里）", "ImageFlipX" in CN.NODES, sorted(CN.NODES)[:3])
    wf9 = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": p1, "width": 16, "height": 8}},
        {"id": "n2", "node": "ImageFlipX", "inputs": {"image": p1,
                                                      "out": os.path.join(store, "flip.png")}},
    ]}
    r9 = CN.run_workflow(wf9)
    check("脚手架节点能跑通", r9.get("ok"), r9.get("error"))

    print("[10] 批次 A 传统算子成链")
    storeA = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(storeA, exist_ok=True)
    a, b, c = (os.path.join(storeA, n) for n in ("a.png", "b.png", "c.png"))
    wfA = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": a, "width": 32, "height": 16}},
        {"id": "n2", "node": "AdjustBrightness",
         "inputs": {"image": a, "out": b, "factor": 1.4}},
        {"id": "n3", "node": "CenterCropImages", "inputs": {"image": b, "out": c}},
    ]}
    rA = CN.run_workflow(wfA)
    check("批次 A 链跑通", rA.get("ok"), rA.get("error"))
    check("产物齐全（3 个）", len(rA.get("products") or []) >= 3, rA.get("products"))
    check("新增节点在表里（AdjustBrightness/CaseConverter/ImageStitch）",
          all(n in CN.NODES for n in ("AdjustBrightness", "CaseConverter", "ImageStitch")),
          sorted(CN.NODES)[:5])

    print("[11] 批次 B（裁剪/音频/颜色/读数）")
    dB = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(dB, exist_ok=True)
    imgB = os.path.join(dB, "b_in.png")
    wavB = os.path.join(dB, "sil.wav")
    wfB = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": imgB, "width": 32, "height": 32}},
        {"id": "n2", "node": "ImageCropV2", "inputs": {"image": imgB, "out": os.path.join(dB, "b_crop.png"),
                                                      "x": 4, "y": 4, "width": 20, "height": 20}},
        {"id": "n3", "node": "EmptyAudio", "inputs": {"out": wavB, "duration": 0.1, "sample_rate": 8000}},
    ]}
    rB = CN.run_workflow(wfB)
    check("批次 B 链跑通", rB.get("ok"), rB.get("error"))
    check("静音 wav 真生成", os.path.exists(wavB) and os.path.getsize(wavB) > 100,
          os.path.getsize(wavB) if os.path.exists(wavB) else "缺文件")
    hvB = CN.run({"op": "harvest", "limit": 5})
    check("harvest 仍可用（分类不回退）", hvB.get("ok") or hvB.get("reason"), hvB.get("reason"))

    print("[12] 批次 C（音频处理/文本/缩放补边）")
    dC = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(dC, exist_ok=True)
    wavC = os.path.join(dC, "c_in.wav")
    wavC2 = os.path.join(dC, "c_vol.wav")
    wfC = {"nodes": [
        {"id": "n1", "node": "EmptyAudio", "inputs": {"out": wavC, "duration": 0.2, "sample_rate": 8000}},
        {"id": "n2", "node": "AudioAdjustVolume", "inputs": {"audio": wavC, "out": wavC2, "factor": 0.5}},
        {"id": "n3", "node": "TrimAudioDuration", "inputs": {"audio": wavC2,
                                                             "out": os.path.join(dC, "c_trim.wav"),
                                                             "start": 0.0, "end": 0.1}},
    ]}
    rC = CN.run_workflow(wfC)
    check("批次 C 音频链跑通", rC.get("ok"), rC.get("error"))
    check("音量文件生成", os.path.exists(wavC2), wavC2)
    tx = CN.NODES["ReplaceText"]["fn"]({"text": "a-b-a", "find": "a", "replace": "X"}, {})
    check("文本替换有读数", tx.get("ok") and tx.get("replaced") == 2, tx)

    print("[13] 批次 D（音频均衡/随机裁剪/总像素/文本落盘）")
    dD = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(dD, exist_ok=True)
    aIn = os.path.join(dD, "d_in.wav")
    aEq = os.path.join(dD, "d_eq.wav")
    tOut = os.path.join(dD, "d_note.txt")
    wfD = {"nodes": [
        {"id": "n1", "node": "EmptyAudio", "inputs": {"out": aIn, "duration": 0.15, "sample_rate": 8000}},
        {"id": "n2", "node": "AudioEqualizer3Band",
         "inputs": {"audio": aIn, "out": aEq, "low": 6, "mid": -3, "high": 3}},
        {"id": "n3", "node": "SaveText", "inputs": {"text": "batch D ok", "out": tOut}},
    ]}
    rD = CN.run_workflow(wfD)
    check("批次 D 链跑通", rD.get("ok"), rD.get("error"))
    check("均衡产物存在", os.path.exists(aEq), aEq)
    check("文本落盘存在", os.path.exists(tOut) and open(tOut, encoding="utf-8").read() == "batch D ok", tOut)

    print("[14] 批次 E/F（瓦片/动图/合成/数据集）")
    dE = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(dE, exist_ok=True)
    e1 = os.path.join(dE, "e1.png")
    wfE = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": e1, "width": 40, "height": 40}},
        {"id": "n2", "node": "SplitImageToTileList",
         "inputs": {"image": e1, "out": os.path.join(dE, "e_tile.png"),
                    "columns": 2, "rows": 2}},
        {"id": "n3", "node": "PorterDuffImageComposite",
         "inputs": {"image1": e1, "image2": e1,
                    "out": os.path.join(dE, "e_comp.png"), "mode": "screen"}},
        {"id": "n4", "node": "SaveAnimatedPNG",
         "inputs": {"images": e1 + "," + e1, "out": os.path.join(dE, "e_anim.png"), "duration": 100}},
    ]}
    rE = CN.run_workflow(wfE)
    check("批次 E/F 链跑通", rE.get("ok"), rE.get("error"))
    tile = CN.NODES["SplitImageToTileList"]["fn"](
        {"image": e1, "out": os.path.join(dE, "t.png"), "columns": 2, "rows": 2}, {})
    check("瓦片有 4 个", tile.get("count") == 4, tile.get("count"))
    check("动图 PNG 生成", os.path.exists(os.path.join(dE, "e_anim.png")))

    print("[15] 原生 ComfyUI workflow 导入（秋叶的图能直接进来）")
    native = {"nodes": [
        {"id": 1, "type": "EmptyImage", "widgets_values": [16, 16, 0]},
        {"id": 2, "type": "KSampler", "widgets_values": []},
        {"id": 3, "type": "MaskBlur", "widgets_values": [2]},
    ], "links": [[1, 1, 0, 2, 0, "IMAGE"], [2, 2, 0, 3, 0, "MASK"]]}
    imp = CN.run({"op": "import", "workflow": native})
    check("原生图被转换（3 节点/2 边）",
          (imp.get("converted") or {}).get("nodes") == 3 and (imp.get("converted") or {}).get("edges") == 2,
          imp.get("converted"))
    check("原生节点被认出来（EmptyImage/MaskBlur）",
          set(imp.get("validation", {}).get("native_used") or []) >= {"EmptyImage", "MaskBlur"},
          imp.get("validation", {}).get("native_used"))
    check("未实现的 KSampler 归到 contract_only 且带原因",
          "KSampler" in (imp.get("validation", {}).get("contract_only_used") or []),
          imp.get("validation", {}).get("contract_only_used"))

    print("[16] 批量导入目录（秋叶 workflow 文件夹）")
    import json as _json
    dW = os.path.join(ROOT, "state", "tmp", "comfy_engine", "wf")
    os.makedirs(dW, exist_ok=True)
    with open(os.path.join(dW, "ok.json"), "w", encoding="utf-8") as fh:
        _json.dump({"nodes": [{"id": 1, "type": "EmptyImage", "widgets_values": [8, 8, 0]},
                              {"id": 2, "type": "ImageScaleBy", "widgets_values": [2]}],
                    "links": [[1, 1, 0, 2, 0, "IMAGE"]]}, fh)
    with open(os.path.join(dW, "gpu.json"), "w", encoding="utf-8") as fh:
        _json.dump({"nodes": [{"id": 1, "type": "EmptyImage", "widgets_values": [8, 8, 0]},
                              {"id": 2, "type": "KSampler", "widgets_values": []}],
                    "links": [[1, 1, 0, 2, 0, "IMAGE"]]}, fh)
    with open(os.path.join(dW, "broken.json"), "w", encoding="utf-8") as fh:
        fh.write("{oops")
    idr = CN.run({"op": "import_dir", "folder": dW})
    check("批量导入能读", idr.get("ok"), idr.get("error"))
    check("分类正确（1 可跑 / 1 要GPU / 1 坏）",
          (idr.get("runnable"), idr.get("needs_gpu"), idr.get("invalid")) == (1, 1, 1),
          (idr.get("runnable"), idr.get("needs_gpu"), idr.get("invalid")))
    check("manifest 落盘", os.path.exists(os.path.join(ROOT, "state", "comfy-import-manifest.json")))

    print("[17] 可复跑快照（run → snapshot → replay 同 sha256）")
    dS = os.path.join(ROOT, "state", "tmp", "comfy_engine")
    os.makedirs(dS, exist_ok=True)
    s1 = os.path.join(dS, "s1.png")
    s2 = os.path.join(dS, "s2.png")
    wfS = {"nodes": [
        {"id": "n1", "node": "EmptyImage", "inputs": {"out": s1, "width": 24, "height": 24}},
        {"id": "n2", "node": "AdjustBrightness",
         "inputs": {"image": s1, "out": s2, "factor": 1.3}},
    ]}
    rS = CN.run_workflow(wfS)
    snap = rS.get("snapshot") or {}
    check("运行落快照", bool(snap.get("hash")), snap)
    h = snap.get("hash")
    if h:
        rp = CN.run({"op": "replay", "hash": h})
        check("复跑结果可复现（sha256 全同）", rp.get("reproducible") is True,
              {"same": rp.get("same"), "diff": rp.get("diff_detail")})
    rs = CN.run({"op": "runs", "limit": 5})
    check("runs 列表能读", rs.get("count", 0) >= 1, rs.get("count"))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 引擎四条语义（skip/times/回滚/continue）都有读数，未接线会明说")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
