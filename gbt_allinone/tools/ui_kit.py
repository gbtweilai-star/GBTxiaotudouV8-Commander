# gbt-capability: ui_kit
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""ui_kit —— **UI 组件库的口**（吞天吞来的素材 → 可检索 · 可取件 · 读数如实）。

## 来历（主人令：`uiverse-io/galaxy` 让触手吞噬为己用）

`uiverse-io/galaxy` ★13478 · **MIT** · 纯 HTML/CSS · **3802 个组件**（11 个类目），
落位在 `_upstream/galaxy`（七步法第 1 步）。**体检**（真跑）：`<script>` **0** 件 ·
事件处理器 **0** · `eval` **0** · 真外链（排除 SVG 命名空间）**185** 件（多是出处链接）。

## 🔴 为什么"克隆 + 建索引"还不够（实测）

它的文件名是**随机动物名**（`0x-Sarthak_hungry-penguin-30.html`），本身**零语义**；
所以 `asset_index find("neumorphic button")` ⇒ **0 命中**。
⇒ 搬进来只等于"堆在盘上"。**要为己用，必须从内容里提语义。**

## 本件做什么（蒸馏，不是搬运）

`build`：扫 `_upstream/galaxy/**/*.html`，逐件抽 **类目/可见文案/效果标签/主色/外链数/字节**，
落 `store/ui_kit/index.jsonl`（**只追加**）。
`find`：人话 → 命中候选（带路径与读数），**命中 0 就如实报 0**（不硬塞）。
`take`：取一件到 `outputs/ui-kit/`，**同时如实报它带几条外链**（用之前你自己判断）。

## 三条硬规矩

1. **零出网、零执行**：只读文件与文本，**绝不**执行组件里的任何东西（`<script>` 本来也是 0）。
2. **不改别人的仓**：`_upstream/galaxy/**` 一个字节不动。
3. **不编语义**：效果标签只认**代码里真出现的**特征串；认不出就如实留空。
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "_upstream" / "galaxy"
_OPS = ("status", "build", "find", "take", "where")

_EFFECTS = (
    ("渐变", ("linear-gradient", "radial-gradient", "conic-gradient")),
    ("阴影", ("box-shadow", "drop-shadow")),
    ("霓虹发光", ("glow", "neon", "text-shadow")),
    ("模糊玻璃", ("backdrop-filter", "blur(")),
    ("动画", ("@keyframes", "animation:", "transition:")),
    ("变换", ("transform:", "rotate(", "translate")),
    ("圆角", ("border-radius",)),
    ("Tailwind", ("class=\"", "flex ", "px-", "rounded-")),
    ("SVG", ("<svg",)),
    ("渐变文字", ("background-clip",)),
)
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
# 🔴 2026-10-13：**中文人话 ↔ 英文类目名之间的桥**（实测教训：问「渐变卡片」，
#    头三件全是 `Buttons` —— 因为类目名是 English `Cards`，中文「卡片」永远匹配不上它）。
#    这张表就是那座桥；类目名保持不变，只在**检索时**多认几个中文叫法。
_CAT_CN = {
    "Buttons": "按钮 按键 钮",
    "Cards": "卡片 卡 面板块",
    "loaders": "加载 加载动画 转圈 进度 等待",
    "Toggle-switches": "开关 切换 拨动",
    "Inputs": "输入框 输入",
    "Forms": "表单 填表",
    "Checkboxes": "复选框 多选 勾选",
    "Patterns": "图案 花纹 背景图案",
    "Radio-buttons": "单选 单选按钮",
    "Tooltips": "提示 悬浮提示 气泡",
    "Notifications": "通知 提醒 消息条",
}
_TAG = re.compile(r"<[^>]+>")
_URL = re.compile(r"https?://[^\"' >\s]+")
_NS_OK = ("w3.org/2000/svg", "w3.org/1999/xlink", "w3.org/1998/Math")


def _store_dir() -> Path:
    d = os.environ.get("GBT_STORE_DIR")
    return Path(d) if d else (_ROOT / "gbt_allinone" / "store")


def _index_path() -> Path:
    p = _store_dir() / "ui_kit"
    p.mkdir(parents=True, exist_ok=True)
    return p / "index.jsonl"


def _extract(path: Path) -> dict:
    """从**内容**里提语义（只读文本、零执行、零出网）。"""
    try:
        t = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    low = t.lower()
    body = _TAG.sub(" ", t)
    body = re.sub(r"\s+", " ", body).strip()
    eff = [name for name, keys in _EFFECTS if any(k in low for k in keys)]
    hexes = [h.lower() for h in _HEX.findall(t)]
    top = sorted({h: hexes.count(h) for h in hexes}.items(), key=lambda kv: -kv[1])[:3]
    urls = [u for u in _URL.findall(t) if not any(ns in u for ns in _NS_OK)]
    rel = path.relative_to(_SRC).as_posix()
    return {"path": path.relative_to(_ROOT).as_posix(), "rel": rel,
            "cat": rel.split("/")[0], "cat_cn": _CAT_CN.get(rel.split("/")[0], ""),
            "file": path.name,
            "text": body[:80], "effects": eff,
            "colors": [c for c, _n in top], "urls": len(urls),
            "bytes": path.stat().st_size}


def build(force: bool = False, **_kw) -> dict:
    """扫 `_upstream/galaxy` 建语义索引（**只追加**；`force=False` 时已有就不重扫）。"""
    if not _SRC.is_dir():
        return {"ok": False, "status": "needs_dependency", "missing": [str(_SRC)],
                "note": "素材不在盘 ⇒ 先按七步法第 1 步落位（git clone --depth 1）"}
    idx = _index_path()
    if idx.is_file() and not force:
        rows = sum(1 for _ in idx.open(encoding="utf-8") if _.strip())
        return {"ok": True, "reused": True, "rows": rows, "index": str(idx),
                "note": "索引已在；要重扫给 force=true"}
    rows, bad = [], 0
    for p in sorted(_SRC.rglob("*.html")):
        r = _extract(p)
        if r:
            rows.append(r)
        else:
            bad += 1
    if not rows:
        return {"ok": False, "error": "一件都抽不出来 ⇒ 不写空库（fail-closed）"}
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "ui_kit_index",
           "src": "_upstream/galaxy", "count": len(rows), "read_failed": bad, "items": rows}
    with idx.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    cats: dict = {}
    for r in rows:
        cats[r["cat"]] = cats.get(r["cat"], 0) + 1
    return {"ok": True, "indexed": len(rows), "read_failed": bad, "cats": cats,
            "with_urls": sum(1 for r in rows if r["urls"]), "index": str(idx)}


def _load() -> list:
    idx = _index_path()
    if not idx.is_file():
        return []
    last = None
    for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                last = json.loads(line)
            except Exception:                                # noqa: BLE001
                continue
    return (last or {}).get("items") or []


def find(q: str = "", limit: int = 8, cat: str = "", effect: str = "", **_kw) -> dict:
    """人话 → 候选组件。**命中 0 就如实报 0**（不硬塞）。"""
    items = _load()
    if not items:
        return {"ok": False, "status": "needs_build", "error": "索引不在 ⇒ 先 op=build"}
    # 🔴 2026-10-13 实测教训：首版打分把「类目命中」与「效果标签命中」**混在一起** ⇒
    #    `Tailwind`/`动画` 这类标签覆盖了九成组件，于是 `neon button` 命中 3322 件、
    #    `渐变卡片` 头三件还是 `Buttons` —— **谁都有分词，就等于谁都不突出**。
    #    修法两条：① **按字段加权**（类目 2.0 · 文案 1.5 · 文件名 1.0 · 效果 1.0）
    #    ② **idf 反比加权**（这个 token 在全部件里越常见越不值钱）—— 滥标签自动失势。
    from ..semantic_route import grams
    qg = grams(str(q)) if str(q).strip() else set()
    # 🔴 **df/idf 与打分必须用同一份字段**（2026-10-13 实测事故：df 统计时漏了"中文桥"字段
    #    ⇒ 桥命中的词拿不到 idf ⇒ 权重 0 ⇒ 桥形同不存在，`q=卡片 cat=Cards` 直接 0 命中）。
    #    ⇒ 字段只在这里拼一次，两处共用。
    def _fvals(r: dict) -> dict:
        return {"cat": "%s %s" % (r["cat"], _CAT_CN.get(r["cat"], "")),
                "text": r.get("text") or "", "file": r.get("file") or "",
                "effects": " ".join(r.get("effects") or [])}
    df: dict = {}
    if qg:
        for r in items:                      # 每件只数一次（文档频次）
            seen = set()
            for fld in _fvals(r).values():
                seen |= (qg & grams(fld))
            for t in seen:
                df[t] = df.get(t, 0) + 1
    import math
    n = max(1, len(items))
    idf = {t: math.log(1.0 + n / (1.0 + c)) for t, c in df.items()}
    out = []
    for r in items:
        if cat and r["cat"].lower() != str(cat).lower():
            continue
        if effect and str(effect) not in " ".join(r["effects"]):
            continue
        # 类目字段 = 英文名 + 中文桥（`Cards` ↔ 卡片/卡）——两条都算，权重最高。
        # 桥表**在代码里现取**（不依赖索引行里存没存 `cat_cn`）⇒ 改桥表立刻生效，不用重建索引。
        _w = {"cat": 2.0, "text": 1.5, "file": 1.0, "effects": 1.0}
        vals = _fvals(r)
        fields = tuple((k, vals[k], _w[k]) for k in ("cat", "text", "file", "effects"))
        s, why = 0.0, []
        for name, val, w in fields:
            hit = qg & grams(val)
            if hit:
                s += w * sum(idf.get(t, 0.0) for t in hit)
                why.append("%s命中%d" % (name, len(hit)))
        if qg and s <= 0:
            continue
        out.append({**{k: r.get(k) for k in ("path", "cat", "file", "text", "effects", "colors", "urls")},
                    "score": round(s, 3), "why": why})
    out.sort(key=lambda r: -r["score"])
    return {"ok": True, "q": q, "hits": len(out), "items": out[:int(limit)],
            "indexed": len(items),
            "_口径": "打分 = Σ(字段权重 × idf)：类目 2.0 · 文案 1.5 · 文件名 1.0 · 效果 1.0；"
                     "idf 让「Tailwind/动画」这类滥标签自动失势；**命中 0 就是 0**（不硬塞候选）"}


def take(path: str = "", out: str = "", **_kw) -> dict:
    """取一件到 `outputs/ui-kit/`（**同时如实报它带几条外链**）。**不改源仓**。"""
    if not path:
        return {"ok": False, "fail_closed": True, "error": "要 path（用 op=find 拿）"}
    src = (_ROOT / path).resolve()
    try:
        src.relative_to((_ROOT / "_upstream" / "galaxy").resolve())
    except ValueError:
        return {"ok": False, "fail_closed": True, "error": "只许取 _upstream/galaxy 里的件"}
    if not src.is_file():
        return {"ok": False, "status": "not_found", "error": "件不在盘：%s" % path}
    dst = Path(out) if out else (_ROOT / "outputs" / "ui-kit" / src.name)
    # 🔴 2026-10-13 修：`out` 给**相对路径**时，`dst.relative_to(_ROOT)` 会抛 ValueError
    #    （相对路径不是 _ROOT 的子路径）⇒ **只要调用方传了 out 就崩**。
    #    上一轮我把它误读成"grep 没匹配到输出"（其实是它炸了）—— 同类教训：**没看到 ≠ 没问题**。
    if not dst.is_absolute():
        dst = _ROOT / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    r = _extract(src)
    try:
        rel = str(dst.relative_to(_ROOT))
    except ValueError:
        rel = str(dst)
    return {"ok": True, "from": path, "out": rel,
            "bytes": dst.stat().st_size, "urls": r.get("urls", 0),
            "effects": r.get("effects"), "text": r.get("text"),
            "_口径": "取件只拷贝；**外链数如实报**（用它之前自己判断要不要去链）"}


def status(**_kw) -> dict:
    items = _load()
    cats: dict = {}
    for r in items:
        cats[r["cat"]] = cats.get(r["cat"], 0) + 1
    return {"ok": True, "op": "status", "kind": "ui_kit", "src": str(_SRC),
            "src_present": _SRC.is_dir(), "indexed": len(items), "cats": cats,
            "with_urls": sum(1 for r in items if r.get("urls")), "ops": list(_OPS),
            "_口径": "素材来自 uiverse-io/galaxy（MIT · ★13478）；本件**只读不执行**、零出网"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "ui_kit",
            "entry": "run_task('ui_kit', {...})", "ops": list(_OPS),
            "what": "把吞来的 UI 组件**蒸馏成可检索的语义索引**，再取件给下游（渲染/调优）用",
            "为什么不是搬进来就算完": "实测：文件名是随机动物名（hungry-penguin-30.html），"
                                      "asset_index 关键词检索 0 命中 ⇒ 必须从**内容**提语义",
            "hard_rules": ["零出网 · 零执行（不跑组件里的任何东西）",
                           "不改 `_upstream/galaxy/**` 一个字节",
                           "效果标签只认代码里真出现的特征串，认不出留空",
                           "取件如实报外链数"],
            "上游": "uiverse-io/galaxy（MIT · 纯 HTML/CSS · 3802 件 · 11 类目）",
            "下游": "shot-page.py / render_page.py（真渲一张）· vision_print.polish（清晰度/补光）"}


def run(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("build", build), ("find", find),
                   ("take", take), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="UI 组件库的口（吞来的素材 → 可检索可取件）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
