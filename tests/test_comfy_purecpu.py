# -*- coding: utf-8 -*-
"""GBT天真纯 CPU 批次：新增节点真调用（不是只注册名字）。"""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tools import comfy_native as CN
    from PIL import Image

    need = ["ImageAddNoise", "PrimitiveString", "StringFormat", "StringConcatenate",
            "JsonExtractString", "ComfyMathExpression", "MergeTextLists",
            "PadImageNode", "ResizeImageMaskNode", "ComfySwitchNode",
            "CreateList", "GetItemFromList", "RegexExtract", "ImageRGBToYUV",
            "AddLayer", "Morphology", "FillHoles", "ShuffleDataset", "ResolutionBucket", "Canny",
            "SaveImageWebsocket"]
    for n in need:
        check("注册 %s" % n, n in CN.NODES, n)
    check("节点数 ≥166", len(CN.NODES) >= 166, len(CN.NODES))

    tmp = tempfile.mkdtemp(prefix="gbt-purecpu-")
    src = os.path.join(tmp, "src.png")
    Image.new("RGBA", (32, 24), (20, 40, 60, 255)).save(src)
    edge_src = os.path.join(tmp, "edge-src.png")
    from PIL import ImageDraw
    edge_img = Image.new("RGBA", (32, 24), (0, 0, 0, 255))
    ImageDraw.Draw(edge_img).rectangle([0, 0, 15, 23], fill=(255, 255, 255, 255))
    edge_img.save(edge_src)

    def call(n, **kw):
        kw.setdefault("out", os.path.join(tmp, n + ".png"))
        return CN.NODES[n]["fn"](kw, {})

    r = call("ImageAddNoise", image=src, seed=7, strength=0.1)
    check("ImageAddNoise ok", r.get("ok") and os.path.isfile(r["out"]), r)
    r = call("PadImageNode", image=src, left=4, top=4, right=4, bottom=4)
    check("PadImageNode 40x32", r.get("ok") and r.get("width") == 40 and r.get("height") == 32, r)
    r = call("ResizeImageMaskNode", image=src, width=16, height=12)
    check("ResizeImageMaskNode 16x12", r.get("ok") and r.get("width") == 16 and r.get("height") == 12, r)
    r = call("AddLayer", image1=src, image2=src, opacity=0.5)
    check("AddLayer ok", r.get("ok") and os.path.isfile(r["out"]), r)
    r = call("Morphology", image=src, operation="dilate", kernel_size=3)
    check("Morphology ok", r.get("ok") and os.path.isfile(r["out"]), r)
    r = call("FillHoles", mask=src)
    check("FillHoles ok", r.get("ok") and os.path.isfile(r["out"]), r)
    r = call("Canny", image=edge_src, low_threshold=100, high_threshold=200)
    check("Canny 有边缘", r.get("ok") and os.path.isfile(r["out"]) and r.get("edge_pixels", 0) > 0, r)
    r = call("SaveImageWebsocket", images=src)
    check("SaveImageWebsocket ok", r.get("ok") and os.path.isfile(r["out"]), r)

    check("StringFormat", CN.NODES["StringFormat"]["fn"]({"format": "{}-{}", "values": ["a", "b"]}, {}).get("value") == "a-b")
    check("StringConcatenate", CN.NODES["StringConcatenate"]["fn"]({"a": "x", "b": "y", "separator": "-"}, {}).get("value") == "x-y")
    check("JsonExtractString", CN.NODES["JsonExtractString"]["fn"]({"json": '{"a":{"b":"c"}}', "key": "a.b"}, {}).get("value") == "c")
    check("ComfyMathExpression", CN.NODES["ComfyMathExpression"]["fn"]({"expression": "2*(3+4)"}, {}).get("value") == 14)
    check("MergeTextLists", CN.NODES["MergeTextLists"]["fn"]({"list1": ["a"], "list2": ["b"]}, {}).get("value") == ["a", "b"])
    check("ComfySwitchNode", CN.NODES["ComfySwitchNode"]["fn"]({"condition": True, "on_true": "y", "on_false": "n"}, {}).get("value") == "y")
    check("CreateList", CN.NODES["CreateList"]["fn"]({"items": [1, 2]}, {}).get("value") == [1, 2])
    check("GetItemFromList", CN.NODES["GetItemFromList"]["fn"]({"list": [1, 2], "index": 1}, {}).get("value") == 2)
    check("RegexExtract", CN.NODES["RegexExtract"]["fn"]({"string": "abc123", "pattern": "[0-9]+"}, {}).get("value") == "123")

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

