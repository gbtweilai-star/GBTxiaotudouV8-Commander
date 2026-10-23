# gbt-capability: desktop_distill
"""蒸馏件：桌面操作取法（状态先行 · UIA 优先 · 视觉兜底 · 动后回读）。

## 这不是外挂 —— 这是「吞天」蒸出来的**我们自己的**能力
主人令（2026-10-12，逐字）：「我们吞噬都是加入蒸馏提炼出契合我们的能力」

吞入件是 CursorTouch/Windows-MCP（MIT · 8871★ ·「MCP Server for Computer Use in Windows」）。
本位**不是接入端**：不联网、不起进程、不装 uvx、不碰别的 agent 配置 —— 只把它的**取法**
提炼成我们自己的判据、读数与等待策略。所以它敢零作用域（本文件没有 subprocess / urllib / 写盘）。

## 为什么是「取法」不是「建平行位」（这是本位的立项理由）
win-mcp 干的事（Windows 桌面控制）我们**已经有**：`tentacle`（UIA 直操作，无视遮挡）·
`desktop_commander`（终端 + 文件系统全能力）· `browser`（DOM / 原生窗口，走 CDP）。
照抄建一个平行位 = 撞仓规「新增即清旧」里**同功能两份**那一条（`supersede-check.py` 会打红）。
⇒ 本位只**蒸** win-mcp 里我们还没有的那几条**取法**；它的「起服务 / 装计划任务」**明确不取**。

## 蒸馏出四条（每条指回 win-mcp 原话，见 op=provenance）
1. **状态先行**：动手前先取一帧窗口/UI 状态（它的 State-Tool）→ op=method ①。
2. **UIA 优先、视觉可选**：它原话「doesn't rely on any traditional computer vision
   techniques」→ 我们取**层级**（UIA 直取 → DOM 降噪 → 视觉兜底）→ op=method ②。
3. **DOM 模式给浏览器降噪**：`use_dom=True` 只留网页内容；Firefox 不暴露 `RootWebArea`
   ⇒ 要 IAccessible2 兜底 → op=method ③。
4. **动作节律**：它标注 click→click 典型 **0.2–0.5s** → op=rhythm 换算成我们的
   「动后等稳定」等待策略（**现算**，不硬编码一个数当真理）。

op=method / rhythm / source / provenance / where
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CAPSULE = _ROOT / "gbt_allinone" / "store" / "devoured" / "devoured_cursortouch_windows-mcp"
_SRC = "https://github.com/CursorTouch/Windows-MCP"

# 四条取法：我们的落点 + win-mcp 原话（出处可复核，不靠回忆）
_METHOD = (
    {
        "序": "①",
        "取法": "状态先行：动手前先取一帧窗口/UI 状态，不凭想象点",
        "win-mcp 原话": "State-Tool … capturing window/UI state",
        "我们的落点": "与 gbt-tentacle 铁律 1「先看再动」同一条；本位把它写成**可复读的判据**",
        "我们已有": "tentacle（see / read_text / list_windows）",
    },
    {
        "序": "②",
        "取法": "UIA 优先、视觉可选：层级 = UIA 直取 → DOM 降噪 → 视觉兜底",
        "win-mcp 原话": "Unlike many automation tools, Windows-MCP doesn't rely on any traditional computer vision techniques",
        "我们的落点": "同一条方向：能直取元素就不截图猜坐标；视觉是**兜底**不是主路",
        "我们已有": "tentacle（UIA 穿透直操作）· vision（兜底那条路）",
    },
    {
        "序": "③",
        "取法": "浏览器 DOM 模式降噪：只留网页内容，滤掉浏览器外框",
        "win-mcp 原话": "use_dom=True mode for State-Tool that focuses exclusively on web page content … Firefox uses an IAccessible2 fallback since it doesn't expose RootWebArea via UIA",
        "我们的落点": "读网页优先走 DOM（browser 的 dom_query），别读整屏；**Firefox 要兜底**这条照记",
        "我们已有": "browser（op=native · action=dom_query / get_text）",
    },
    {
        "序": "④",
        "取法": "动作节律：每步之间留出稳定窗口，别立刻取下一帧",
        "win-mcp 原话": "Typical latency between actions … ranges from 0.2 to 0.5 secs",
        "我们的落点": "铁律 2「动后等稳定」的**量化基线**；具体等多久由 op=rhythm 现算",
        "我们已有": "tentacle 铁律 2（无量化基线 ⇒ 本位补这一条）",
    },
)

# 它标注的节律区间（原话 0.2–0.5s），我们只当**下限基线**用
_BASE_LO_MS, _BASE_HI_MS = 200, 500


def method(**_kw) -> dict:
    """桌面操作四条取法：我们的落点 + win-mcp 原话 + 我们已有的承接位。"""
    return {"ok": True, "op": "method", "kind": "desktop_distill",
            "条目": [dict(r) for r in _METHOD],
            "口径": "**取法**不是**建位**：这四条都落在我们已有的承接位上，"
                    "本位只把 win-mcp 的取法写成可复读的判据（不复制它的代码）"}


def rhythm(baseline_ms: int = 350, actions: int = 1, **_kw) -> dict:
    """动后等稳定：把 win-mcp 的 0.2–0.5s 基线**现算**成建议等待（带上下限，防死等）。

    规则（写死，可复核）：
      - 建议等待 = baseline_ms × actions，且**不低于** 200 × actions（win-mcp 基线下限）；
      - 上限 = 500 × actions × 3（超过就别死等，改用「不确定就对比前后截图」）。
    """
    ms = max(1, int(baseline_ms))
    n = max(1, int(actions))
    low, high = _BASE_LO_MS * n, _BASE_HI_MS * n
    raw = ms * n
    wait = max(low, min(raw, high * 3))
    return {"ok": True, "op": "rhythm", "kind": "desktop_distill",
            "baseline_ms": ms, "actions": n,
            "win-mcp 基线区间(ms)": [low, high],
            "建议等待_ms": wait,
            "上限_ms": high * 3,
            "超限怎么办": "别死等 —— 铁律 6：不确定就对比前后截图",
            "口径": "基线来自 win-mcp 原话「0.2 to 0.5 secs」；**现算**，不把 350 当真理"}


def source(**_kw) -> dict:
    """吞入件来源：胶囊在不在、多大、逐个 sha256（真读数，不信转述）。"""
    if not _CAPSULE.is_dir():
        return {"ok": False, "op": "source", "error": "胶囊不在盘上：" + str(_CAPSULE)}
    files = []
    for f in sorted(_CAPSULE.rglob("*")):
        if f.is_file():
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            files.append({"name": f.name, "bytes": f.stat().st_size, "sha256": h.hexdigest()[:16]})
    return {"ok": True, "op": "source", "kind": "desktop_distill",
            "repo": "CursorTouch/Windows-MCP", "url": _SRC,
            "license": "MIT", "stars": 8871,
            "胶囊": str(_CAPSULE.relative_to(_ROOT)).replace("\\", "/"),
            "文件": files,
            "口径": "只**读**胶囊（不写盘）；哈希是现读现算，不是抄来的"}


def provenance(**_kw) -> dict:
    """蒸馏出处：每条落成哪个 op、来自 win-mcp 哪句原话；**没蒸的如实标**。"""
    return {"ok": True, "op": "provenance", "kind": "desktop_distill",
            "吞入件": {"repo": "CursorTouch/Windows-MCP", "site": _SRC,
                       "license": "MIT", "stars": 8871,
                       "胶囊": "gbt_allinone/store/devoured/devoured_cursortouch_windows-mcp/"},
            "蒸馏映射": [
                {"win-mcp 原话/出处": "tools for basic keyboard, mouse operation and capturing window/UI state（README：Rich Toolset）",
                 "落成": "op=method ①（状态先行）"},
                {"win-mcp 原话/出处": "doesn't rely on any traditional computer vision techniques or specific fine-tuned models（README：Use Any LLM）",
                 "落成": "op=method ②（UIA 优先、视觉兜底）"},
                {"win-mcp 原话/出处": "use_dom=True … focuses exclusively on web page content …（README：DOM Mode）",
                 "落成": "op=method ③（DOM 降噪 + Firefox 兜底）"},
                {"win-mcp 原话/出处": "Typical latency … ranges from 0.2 to 0.5 secs（README：Real-Time Interaction）",
                 "落成": "op=rhythm（动后等稳定的量化基线，现算）"},
                {"win-mcp 原话/出处": "uvx windows-mcp serve / windows-mcp install（README：Run at Login）",
                 "落成": "**未蒸馏（故意）**：起服务 / 装计划任务写用户目录与系统计划 ⇒ 那是**接入端**的活，"
                          "且我们已有 tentacle / desktop_commander，不做平行位"},
                {"win-mcp 原话/出处": "`English` as the default language … else disable the App-Tool（README：Prerequisites）",
                 "落成": "**未蒸馏（当坑记）**：它的 App-Tool 依赖英文 Windows；我们走 UIA 直取，不吃这个前提"},
            ],
            "边界": "接入端 ≡ 我们**已有**的 tentacle / desktop_commander（不新起一个平行位）；"
                    "本位 ≡ 蒸馏件（我们自己的判据与节律）",
            "口径": "蒸馏 = 把外面**契合我们**的那部分取法变成我们自己的判据；"
                    "**没蒸出来的如实体现在「未蒸馏」那两行**"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "desktop_distill", "tentacle": "desktop_distill",
            "entry": "run_task('desktop_distill', {'op': …})",
            "ops": ["method", "rhythm", "source", "provenance", "where"],
            "files": {"handler": "gbt_allinone/tools/desktop_distill.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_cursortouch_windows-mcp/"},
            "scopes": "零作用域（只读 + 纯算：无 subprocess / 无 urllib / 无写盘）",
            "contract": [
                {"op": "method", "params": "无", "returns": "桌面操作四条取法 + 我们的落点 + 已有承接位"},
                {"op": "rhythm", "params": "baseline_ms / actions", "returns": "现算「动后等稳定」建议等待（带上限）"},
                {"op": "source", "params": "无", "returns": "吞入件胶囊现读（尺寸 + 逐文件 sha256）"},
                {"op": "provenance", "params": "无", "returns": "每条蒸馏自 win-mcp 哪句原话；未蒸的如实标"},
            ]}


_OPS = {"method": method, "rhythm": rhythm, "source": source,
        "provenance": provenance, "where": where}
_ALLOWED = {"method": set(), "rhythm": {"baseline_ms", "actions"},
            "source": set(), "provenance": set(), "where": set()}


def run_op(op: str = "where", **params) -> dict:
    op = (op or "where").strip().lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "op": op, "fail_closed": True, "error": "未知 op：" + op,
                "ops": sorted(_OPS), "how": "run_task('desktop_distill', {'op': …})"}
    extra = set(params) - _ALLOWED[op]
    if extra:
        return {"ok": False, "op": op, "fail_closed": True,
                "error": "不认的参数：" + str(sorted(extra)), "allowed": sorted(_ALLOWED[op])}
    return fn(**params)
