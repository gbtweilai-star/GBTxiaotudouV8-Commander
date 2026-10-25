# -*- coding: utf-8 -*-
"""派活前置 · 索引直达（给万能插用的那一层）

主人口径：「按需激活压缩最小运行内存」「百分百精准直达」。
本件做的事：给定一句话，**先查索引**，返回：
  · 命中能力位（341 位目录里打分）
  · 命中代码页（分片索引，只读命中片）
  · 建议命令（能力位 → 唯一门的调用形状）
不扫盘、不载全量索引。

用法：
  python3 tools/page_route.py "把 Markdown 变成 PPT"
  python3 tools/page_route.py --json "..."
"""
from __future__ import annotations
import importlib.util, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "state" / "bind"
MANIFEST = BASE / "manifest.json"
SHARDS = BASE / "shards"
CAPS = ROOT / "data" / "capabilities.json"

def _load(path, name):
    """按路径加载同目录下的件（page_lazy 提供 load_manifest：瘦身 manifest 现算推理）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_CJK = re.compile(r"[\u4e00-\u9fff]+")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]{2,}")

# 中文虚词/高频双字：它们不是信号，留着只会把不相干的页顶上来
_STOP = {
    "什么", "之前", "可以", "这个", "那个", "怎么", "需要", "应该", "一个", "我们",
    "你们", "他们", "是不", "不是", "要查", "查询", "请问", "如何", "哪里", "哪些",
    "进行", "操作", "使用", "的是", "了吗", "时候", "东西", "事情", "然后", "因为",
    "所以", "但是", "如果", "还有", "就是", "没有", "有的", "这些", "那些", "现在",
}


def tokens(text: str) -> set:
    """中英混排切词：英文按词、中文按 2 字滑窗，并剔除虚词双字。"""
    out = set(w.lower() for w in _WORD.findall(text))
    for seg in _CJK.findall(text):
        for i in range(len(seg) - 1):
            g = seg[i:i + 2]
            if g not in _STOP:
                out.add(g)
        if len(seg) == 1 and seg not in _STOP:
            out.add(seg)
    return out


def _load_caps() -> list:
    if not CAPS.is_file():
        return []
    try:
        d = json.loads(CAPS.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(d, dict):
        for k in ("capabilities", "caps", "items", "data"):
            if isinstance(d.get(k), list):
                return d[k]
        return []
    return d if isinstance(d, list) else []


def route_caps(text: str, limit: int = 5) -> list:
    tk = tokens(text)
    scored = []
    for c in _load_caps():
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or c.get("id") or "")
        desc = str(c.get("desc") or c.get("description") or c.get("what") or "")
        hay = (name + " " + desc).lower()
        score = 0
        for t in tk:
            if t in hay:
                score += 3 if t in name.lower() else 1
        if score:
            scored.append((score, name, desc[:90],
                           bool(c.get("readonly")), c.get("scope") or c.get("gate") or ""))
    scored.sort(key=lambda x: -x[0])
    return [{"cap": n, "score": s, "desc": d, "readonly": ro, "gate": g}
            for s, n, d, ro, g in scored[:limit]]


def route_pages(text: str, limit: int = 6, hops: int = 1) -> dict:
    if not MANIFEST.is_file():
        return {"ok": False, "error": "还没建索引：python3 tools/page_lazy.py build"}
    _pl = _load(Path(__file__).resolve().parent / "page_lazy.py", "_pl")
    man = _pl.load_manifest(need_names=True)      # 瘦身 manifest：shard_of / name2 现算
    tk = tokens(text)
    read = MANIFEST.stat().st_size

    # 播种：名字/路径命中
    seeds = []
    for p in man["pages"]:
        pl = p.lower()
        if any(t in pl for t in tk):
            seeds.append(p)
    for name, pids in man["name2"].items():
        if any(t in name for t in tk):
            seeds += pids
    seeds = list(dict.fromkeys(seeds))[:10]

    # 只读命中分片 + 1 跳邻居（按需激活）
    seen, out, frontier = set(), [], list(seeds)
    for depth in range(hops + 1):
        nxt = []
        for pid in frontier:
            if pid in seen or pid not in man["shard_of"]:
                continue
            f = SHARDS / man["shard_of"][pid]
            if not f.is_file():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            read += f.stat().st_size
            seen.add(pid)
            dl = " ".join(d.get("defs", [])).lower()
            defhit = sum(1 for t in tk if t in dl)
            out.append({"page": pid, "hops": depth, "def_hits": defhit,
                        "degree": len(d.get("neighbors", []))})
            nxt += d.get("neighbors", [])
        frontier = nxt
        if not frontier:
            break

    out.sort(key=lambda r: (-r["def_hits"], r["hops"], -r["degree"]))
    return {"ok": True, "pages": out[:limit], "loaded": len(seen),
            "total": man["count"], "bytes_read": read}


def suggest(cap: str) -> str:
    if not cap:
        return ""
    return "py -3.14 tools/codex-scripts/five-dim.py cap %s '{}'" % cap



# ── 原生意图层：一句话 → apple-* 桥 + 命令 ────────────────────
# 只做**路由**；真正的门在 omni_plug 的 native 插座里（读通写拦）。
NATIVE_INTENT = [
    (("步数", "走路", "运动量", "走了", "多少步", "计步"), "apple-healthkit", "steps"),
    (("心率", "心跳"), "apple-healthkit", "heart-rate"),
    (("睡眠", "睡了"), "apple-healthkit", "sleep"),
    (("卡路里", "消耗"), "apple-healthkit", "active-energy"),
    (("体重",), "apple-healthkit", "weight"),
    (("天气", "气温", "下雨", "湿度"), "apple-weather", ""),
    (("定位", "在哪", "位置", "坐标"), "apple-location", ""),
    (("日历", "日程", "安排", "会议"), "apple-calendar", "list"),
    (("空闲", "忙不忙"), "apple-calendar", "freebusy"),
    (("提醒", "待办", "todo"), "apple-reminders", "list"),
    (("照片", "相册", "图片库"), "apple-photos", "stats"),
    (("闹钟列表", "有哪些闹钟", "定时"), "apple-alarm", "list"),
    (("通知", "推送"), "apple-notification", "pending"),
    (("剪贴板", "复制", "clipboard"), "apple-clipboard", ""),
    (("正在播放", "音乐", "播放中"), "apple-media", ""),
    (("语音", "嗓子", "朗读", "发音"), "apple-speak", "voices"),
    (("转录", "语音转文字", "识别说话"), "apple-speech", "status"),
    (("识别文字", "ocr", "读图", "截图文字"), "apple-vision", "ocr"),
    (("分词", "词性", "实体", "情感", "语种"), "apple-nlp", "analyze"),
    (("设备", "电量", "内存", "机器信息"), "apple-device", "info"),
    (("蓝牙",), "apple-bluetooth", "status"),
    (("家居", "智能家电"), "apple-homekit", "list"),
    (("地图", "导航", "路线"), "apple-maps", "search"),
    (("播放器", "播放列表"), "apple-player", "list"),
    # 写类意图：路由只"提议"，能不能动手由 native 插座的 device_control 决定
    (("新建提醒", "加个提醒", "帮我记"), "apple-reminders", "create"),
    (("设个闹钟", "定闹钟", "设闹钟", "新建闹钟"), "apple-alarm", "set"),
    (("放首歌", "播放歌曲", "来一首", "放点音乐", "播放音乐"), "apple-player", "play"),

]


def route_native(text: str, limit: int = 3) -> list:
    """把一句话落到 apple-* 桥。命中的只做候选，不执行。"""
    t = str(text or "").lower()
    out = []
    for kws, tool, cmd in NATIVE_INTENT:
        score = sum(1 for k in kws if k.lower() in t)
        if score:
            out.append({"tool": tool, "cmd": cmd, "score": score,
                        "how": "omni_plug op=native tool=%s cmd=%s" % (tool, cmd or "-")})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def route(text: str) -> dict:
    caps = route_caps(text, 5)
    pages = route_pages(text, 6, 1)
    top = caps[0]["cap"] if caps else ""
    nat = route_native(text)
    return {
        "ok": pages.get("ok", False),
        "问": text,
        "能力位": caps,
        "代码页": pages.get("pages", []),
        "按需激活": {"读了字节": pages.get("bytes_read", 0),
                     "加载分片": pages.get("loaded", 0),
                     "总页数": pages.get("total", 0)},
        "原生": nat,
        "建议命令": (nat[0]["how"] if nat and (not caps or nat[0]["score"] >= 1) else suggest(top)),
        "口径": "索引直达，不扫盘；能力位名必须能在 341 位目录里查到才算命中",
    }


def main() -> int:
    a = [x for x in sys.argv[1:] if x != "--json"]
    if not a:
        print(__doc__); return 2
    r = route(" ".join(a))
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1)); return 0
    print("问: %s" % r["问"])
    print("\n能力位（打分，来自 341 位目录）:")
    for c in r["能力位"]:
        flag = "只读" if c["readonly"] else ("需授权:" + (c["gate"] or "?") if c["gate"] else "会改状态")
        print("  [%2d] %-22s %-14s %s" % (c["score"], c["cap"], flag, c["desc"][:56]))
    if not r["能力位"]:
        print("  （无命中）")
    print("\n代码页（分片索引，%d/%d 片 · 读 %d 字节）:"
          % (r["按需激活"]["加载分片"], r["按需激活"]["总页数"], r["按需激活"]["读了字节"]))
    for p in r["代码页"]:
        print("  [%d跳/定义命中%d/度%d] %s" % (p["hops"], p["def_hits"], p["degree"], p["page"]))
    print("\n建议命令: %s" % (r["建议命令"] or "（无）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
