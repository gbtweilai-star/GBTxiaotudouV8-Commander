# gbt-capability: drama_forge
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""drama-prep.py — 把剧本切成镜，并把每镜旁白文本写成 txt（供 PowerShell SAPI 配音）。

用法：py -B -X utf8 tools/codex-scripts/drama-prep.py <repo> <script_file> <audio_dir> <out_json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
script_file = Path(sys.argv[2]).resolve()
audio_dir = Path(sys.argv[3]).resolve()
out_json = Path(sys.argv[4]).resolve()
sys.path.insert(0, str(repo))
from gbt_allinone import drama  # noqa: E402

script = script_file.read_text(encoding="utf-8", errors="replace")
res = drama.parse_timed(script)
if not res.get("ok"):
    print(json.dumps({"ok": False, **res}, ensure_ascii=False))
    sys.exit(2)
audio_dir.mkdir(parents=True, exist_ok=True)
shots = []
for sh in res["shots"]:
    text = (sh.get("dialogue") or sh.get("desc") or "").strip()
    tf = audio_dir / ("shot-%02d.txt" % sh["idx"])
    tf.write_text(text, encoding="utf-8-sig")
    shots.append({"idx": sh["idx"], "text": text, "txt": str(tf),
                  "wav": str(audio_dir / ("shot-%02d.wav" % sh["idx"]))})
out = {"ok": True, "script": script, "shots": shots,
       "total_dur": res.get("total_dur")}
out_json.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({"ok": True, "shots": len(shots), "json": str(out_json)}, ensure_ascii=False))
