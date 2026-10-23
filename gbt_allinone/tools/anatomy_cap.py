# gbt-capability: anatomy_figures
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Anatomy 等轴详解图能力位 —— 把「一个概念」做成**一台真机器**的等轴图 + 可交互页 + A4 印张。

## 这件外部件的来历（主人 2026-10-19 指名抓取：「这两个能力不就可以完美补齐缺失了吗」）
上游真身：`wheresryan22/anatomy`（MIT · 15.9k★ · 2026-10-18 仍在推）——
`_upstream/anatomy/` 就是**逐字节克隆**，本文件一个字都没改它。
它补的是本仓原来**空着的那一格**：科普/原理讲解的**图解与讲解页**（本仓只有成片/剪辑工具，
没有「把原理画成一台能懂的真机器」这条路）。

## 它到底产出什么（现读实物，不是宣传话）
  · **等轴 SVG 图**：零件级（40~150 件）实体、四色明暗、画家排序、卡框（Fig n / 标题 / 提示 / 活读数）
  · **可交互 HTML**：悬停/键盘/自动巡览、WebGL 着色（火/尾焰/水/焦散/灯光）在**同一等轴相机**里
  · **会转的 3D 图**（beta）：`kit/turn*.mjs` 把部件按真 3D 投影逐帧重绘 + 轨道审计
  · **A4/Letter PDF 三种版式**：poster / drawing（带零件表与规格）/ detailed（分步大图）
  · **几何自证**：`node build.mjs --audit` 逐项证明「互不穿插/终端都落在实处/无折/深度序对」
  · **线端自证**：`scripts/lines.mjs` 证明每条纹理线都结束在描边/圆点/轮廓上（`line ends: 0`）

## 依赖面（已现读，触点只有三个）
  · `node`（本机 v24.15.0，要求 ≥20.10）· `Chrome`（本机标准位在）· 无 npm 依赖、无 package.json、无 postinstall
  · **零付费接口、零出网**：整条链在本机跑完（出网只在上游自己的 `scripts/publish.mjs --submit`，
    那条是"向社区画廊提 PR"，本能力位**不接**，也不许接）

## 门（处理器层挂闸，不碰 policy.py）
  · 读面免门：`status` / `examples` / `docs` / `where`
  · 写面挂 `filesystem_write`：`build`（写页面与 PDF）、`verify`（Chrome 截图/环线标注 PNG）
    —— 这两条会真落盘，且 `build` 会**跑外部 node 脚本**，所以按机制层给自己要票。

## 怎么"生成新图"（这是它真正的用法，写在这里免得下次又猜）
  ① 模型读 `docs` 列出的 `SKILL.md` + `references/craft.md`（工艺/零件词表/画家排序）；
  ② 在 `_upstream/anatomy/examples/<新名>/build.mjs` 里写几何（import `kit/iso-kit.mjs`）；
  ③ `cap anatomy_figures '{"op":"build","name":"<新名>"}'` → 出 `outputs/anatomy/<新名>/`；
  ④ `cap anatomy_figures '{"op":"verify","name":"<新名>","what":"lines"}'` → 必须 `line ends: 0`。
  **"推理用我们的、规则用它的"**：几何与工艺规则来自它，概念与模型由本仓自己的大脑给。

ops：`status` / `examples` / `docs` / `build` / `verify` / `where`
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
SRC = WS / "_upstream" / "anatomy"
OUT = WS / "outputs" / "anatomy"
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
OPS = ("status", "examples", "docs", "build", "verify", "where")
_MAX_OUT = 6000


def _node() -> str:
    return shutil.which("node") or ""


def _chrome() -> str:
    for p in CHROME_CANDIDATES:
        if p.is_file():
            return str(p)
    return ""


def _run(argv: list, cwd: Path, timeout: int) -> dict:
    """跑一条本机命令，**原话透传**（P19：拒绝/失败路径不许只剩一个 ok=False）。"""
    try:
        p = subprocess.run([str(a) for a in argv], cwd=str(cwd), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"ok": p.returncode == 0, "exit": p.returncode,
                "out": (p.stdout or "")[-_MAX_OUT:], "err": (p.stderr or "")[-_MAX_OUT:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": None, "fail_closed": True,
                "error": "超时（>%ss）：%s" % (timeout, " ".join(str(a) for a in argv))}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "exit": None, "fail_closed": True,
                "error": "%s: %s" % (type(exc).__name__, str(exc)[:200])}


def _gate(what: str) -> dict | None:
    """写面要票（机制层自我保护）。可信会话（主人）免票，其余一律要一次性授权。"""
    from .. import auth_gate
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    got = auth_gate.check_and_consume("filesystem_write", detail=str(what)[:60])
    if got.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": "filesystem_write",
            "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
            "note": "build/verify 会落盘并跑外部 node 脚本 —— 写面必须人工授权"}


def _example_dir(name: str) -> tuple[Path | None, str]:
    name = str(name or "").strip() or "dial-indicator"
    if not NAME_RE.match(name):
        return None, "例子名不合法（只许小写字母/数字/短横线）：%r" % name
    d = SRC / "examples" / name
    if not (d / "build.mjs").is_file():
        have = [p.name for p in (SRC / "examples").glob("*/build.mjs")]
        return None, "没有这个例子（现读 examples 里有 build.mjs 的：%s）" % ", ".join(sorted(have))
    return d, ""


def _pages(d: Path) -> list:
    """这个例子已经构建出来的页面（build.mjs 就写在自己旁边）。"""
    return sorted([p for p in d.glob("*.html")], key=lambda p: (not p.name.endswith("-light.html"), p.name))


# ── 读面 ─────────────────────────────────────────────────────────────────────
def status(**_kw) -> dict:
    node, chrome = _node(), _chrome()
    out = {"ok": bool(SRC.is_dir()), "op": "status", "kind": "anatomy_figures",
           "上游": "wheresryan22/anatomy", "许可": "MIT", "落点": str(SRC.relative_to(WS)).replace("\\", "/"),
           "node": node, "chrome": chrome,
           "产物目录": str(OUT.relative_to(WS)).replace("\\", "/"),
           "ops": list(OPS)}
    if not SRC.is_dir():
        out.update({"installed": False,
                    "error": "未落位：%s（克隆：git clone --depth 1 https://github.com/wheresryan22/anatomy.git _upstream/anatomy）"
                             % SRC})
        return out
    out["installed"] = True
    out["kit"] = sorted(p.name for p in (SRC / "kit").glob("*.mjs"))
    out["examples"] = sorted(p.name for p in (SRC / "examples").iterdir() if (p / "build.mjs").is_file())
    out["references"] = sorted(p.name for p in (SRC / "references").glob("*.md"))
    out["node_ok"] = bool(node) and _node_major(node) >= 20
    out["chrome_ok"] = bool(chrome)
    out["npm_deps"] = "无 package.json、无 postinstall、零出网（publish.mjs 提 PR 那条本能力位不接）"
    out["口径"] = "读面免门；build/verify 过 filesystem_write 门"
    if not out["node_ok"]:
        out["error"] = "node 不在或 <20.10（现读 %s）" % (node or "未找到")
    return out


def _node_major(node: str) -> int:
    got = _run([node, "--version"], WS, 20)
    m = re.match(r"v?(\d+)", (got.get("out") or "").strip())
    return int(m.group(1)) if m else 0


def examples(**_kw) -> dict:
    if not SRC.is_dir():
        return {"ok": False, "op": "examples", "error": "未落位：%s" % SRC}
    rows = []
    for d in sorted((SRC / "examples").iterdir()):
        b = d / "build.mjs"
        if not b.is_file():
            continue
        pages = _pages(d)
        text = b.read_text(encoding="utf-8", errors="replace")
        rows.append({"name": d.name, "build_mjs": b.stat().st_size,
                     "built": [{"file": p.name, "bytes": p.stat().st_size} for p in pages] or "未构建",
                     "sheet": (d / "sheet.mjs").is_file(),
                     # 两种写法都算：`--audit` 开关式 / `auditOrExit` 无条件式（raptor 就是后者）
                     "audit_ready": ("auditOrExit" in text) or ("--audit" in text)})
    return {"ok": True, "op": "examples", "count": len(rows), "rows": rows,
            "怎么跑": "cap anatomy_figures '{\"op\":\"build\",\"name\":\"<name>\"}'"}


def docs(**_kw) -> dict:
    if not SRC.is_dir():
        return {"ok": False, "op": "docs", "error": "未落位：%s" % SRC}
    rows = []
    for p in [SRC / "SKILL.md"] + sorted((SRC / "references").glob("*.md")):
        if p.is_file():
            rows.append({"file": str(p.relative_to(SRC)).replace("\\", "/"),
                         "bytes": p.stat().st_size,
                         "lines": len(p.read_text(encoding="utf-8", errors="replace").splitlines())})
    return {"ok": True, "op": "docs", "count": len(rows), "rows": rows,
            "读法": "先读 SKILL.md（工作流十条）再读 references/craft.md（工艺与零件词表）；要 3D 读 references/3d.md"}


# ── 写面 ─────────────────────────────────────────────────────────────────────
def build(name: str = "dial-indicator", light: bool = False, audit: bool = False,
          timeout: int = 600, **_kw) -> dict:
    d, why = _example_dir(name)
    if not d:
        return {"ok": False, "op": "build", "error": why, "fail_closed": True}
    denied = _gate("anatomy:build:%s" % d.name)
    if denied:
        return {"op": "build", "name": d.name, **denied}
    node = _node()
    if not node:
        return {"ok": False, "op": "build", "error": "node 不在 PATH（要求 ≥20.10）"}
    argv = [node, "build.mjs"] + (["--light"] if light else []) + (["--audit"] if audit else [])
    got = _run(argv, d, int(timeout))
    pages = _pages(d)
    copied = []
    if pages:
        dst = OUT / d.name
        dst.mkdir(parents=True, exist_ok=True)
        for p in pages:
            shutil.copy2(p, dst / p.name)
            copied.append({"file": str((dst / p.name).relative_to(WS)).replace("\\", "/"),
                           "bytes": (dst / p.name).stat().st_size})
    return {"ok": bool(got.get("ok")) and bool(pages), "op": "build", "name": d.name,
            "argv": argv, "exit": got.get("exit"),
            "out": got.get("out"), "err": got.get("err"), "error": got.get("error"),
            "pages": [{"file": p.name, "bytes": p.stat().st_size} for p in pages],
            "产物": copied,
            "audit": ("已跑 --audit（回执里须见 audit passed）" if audit else "未跑（要几何自证加 \"audit\":true）")}


def verify(name: str = "dial-indicator", what: str = "lines", timeout: int = 600, **_kw) -> dict:
    """验证：`lines`（线端自证 line ends: 0）· `capture`（无头 Chrome 截图 + 控制台干净）· `audit`（几何自证）。"""
    what = str(what or "lines").strip().lower()
    if what not in ("lines", "capture", "audit"):
        return {"ok": False, "op": "verify", "error": "未知 what=%r" % what,
                "available": ["lines", "capture", "audit"], "fail_closed": True}
    if what == "audit":
        return {**build(name, audit=True, timeout=timeout, _verify=True), "op": "verify"}
    d, why = _example_dir(name)
    if not d:
        return {"ok": False, "op": "verify", "error": why, "fail_closed": True}
    pages = _pages(d)
    if not pages:
        return {"ok": False, "op": "verify", "name": d.name,
                "error": "这个例子还没构建（先 op=build）：%s" % d}
    page = pages[0]
    denied = _gate("anatomy:verify:%s:%s" % (d.name, what))
    if denied:
        return {"op": "verify", "name": d.name, "what": what, **denied}
    node = _node()
    if not node:
        return {"ok": False, "op": "verify", "error": "node 不在 PATH"}
    if not _chrome():
        return {"ok": False, "op": "verify", "error": "没找到 Chrome（lines/capture 都要真浏览器）"}
    if what == "lines":
        shot = OUT / d.name / "shots" / "lines.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        argv = [node, "scripts/lines.mjs", str(page.relative_to(SRC)), "--out", str(shot)]
    else:
        argv = [node, "scripts/capture.mjs", str(page.relative_to(SRC))]
    got = _run(argv, SRC, int(timeout))
    text = (got.get("out") or "") + (got.get("err") or "")
    verdict = {"lines": "line ends: 0", "capture": "console: clean"}[what]
    return {"ok": bool(got.get("ok")) and verdict in text, "op": "verify", "name": d.name,
            "what": what, "page": page.name, "argv": argv, "exit": got.get("exit"),
            "判据": verdict, "命中": verdict in text,
            "out": got.get("out"), "err": got.get("err"), "error": got.get("error")}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "anatomy_figures",
            "entry": "py -3.14 tools/codex-scripts/five-dim.py cap anatomy_figures '{\"op\":\"status\"}'",
            "上游": "https://github.com/wheresryan22/anatomy（MIT）",
            "本机落点": "_upstream/anatomy/",
            "产物": "outputs/anatomy/<example>/",
            "ops": list(OPS),
            "what": "把技术概念做成一台真机器的等轴详解图/可交互页/A4 印张（零付费、零出网）",
            "不接": "scripts/publish.mjs 的 --submit（向社区画廊提 PR = 出网发布，主人未授权）"}


def run_op(op: str = "status", **kw) -> dict:
    table = {"status": status, "examples": examples, "docs": docs,
             "build": build, "verify": verify, "where": where}
    fn = table.get(str(op or "status").strip().lower())
    if fn is None:
        return {"ok": False, "op": op, "status": "unknown_op", "available": sorted(table),
                "fail_closed": True, "_口径": "未知 op 一律拒，不猜"}
    return fn(**kw)


if __name__ == "__main__":                                    # 直跑自检（不落盘）
    print(run_op(sys.argv[1] if len(sys.argv) > 1 else "status"))
