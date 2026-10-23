"""通过统一入口对本仓源码生成可追溯报告；输出由回归印章保存。"""
import hashlib
import json
from pathlib import Path

from gbt_allinone import api


def main():
    root = Path(__file__).resolve().parents[2]
    subjects = (
        ("executor", "gbt_allinone/tools/agency_tentacles.py",
         "futures.ThreadPoolExecutor(", "职业并发入口使用线程池。"),
        ("media", "gbt_allinone/tools/media_pipeline.py",
         "def compose(", "媒体流水线提供 compose 清单编排入口。"),
        ("video", "gbt_allinone/tools/libtv_workflow.py",
         "能力入口（只读骨架）", "此视频工作流入口仍声明为只读骨架。"),
    )
    sources, claims = [], []
    for source_id, relative, quote, finding in subjects:
        content = (root / relative).read_text(encoding="utf-8")
        sources.append({"id": source_id, "origin": "repo:" + relative,
                        "content": content,
                        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
        claims.append({"text": finding, "source_id": source_id, "quote": quote})
    payload = {"op": "report", "question": "职业并发与媒体执行入口目前实现到哪一层？",
               "sources": sources, "claims": claims}
    result = api.run_task("video_intel", payload, stamp=False)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
