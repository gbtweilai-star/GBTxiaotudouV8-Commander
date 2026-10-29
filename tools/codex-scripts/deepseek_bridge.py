# -*- coding: utf-8 -*-
"""DeepSeek 免费决策桥 · GBT小土豆V8 全能力接入（2026-10-04 主人令）。

## 图景（主人从 chat.deepseek.com 带回的接入方法论）

「能借你装的眼睛看，不能自己长出眼睛看」—— LLM 当**决策模块**需要三件事：
  ① 程序把外部信号**喂进来**（眼睛）：本工具 `manifest` 把 GBT 全部能力位
     一项一项导成 DeepSeek 认得的工具清单，主人粘进 chat.deepseek.com 一次即可；
  ② 模型在对话里输出**结构化指令**：```gbt 指令块（格式见 manifest 头）；
  ③ 程序把指令**接出去执行**（手脚）：本桥解析指令块 → `run_task` **唯一门**执行
     → 结果打成 ```gbt-result 块回喂，闭环成型。

免费机制 = **原生网页对话**（主人已登录 chat.deepseek.com），不走付费 API、
不碰网页会话令牌、不逆向网页私有接口。对话窗（壳 dsh-chat）已直载该网页。

## 红线（一条都不许松）

  · 执行一律 `run_task(kind, args, safe=True)` —— 授权/作用域/审计全在门里，桥**不旁路**；
  · kind **不在册**（拼错/编造）⇒ 解析层拒绝并如实回执；**在册但涉险**的（keylogger /
    screen_sniff / credential_steal / data_hijack / device_takeover 等 policy 硬拒名）
    由**授权门**硬拒，桥把门的回执**原样**回喂 —— 桥不另立黑名单（两处真相必漂移）；
  · 缺作用域/缺票 ⇒ 把门的回执**原样**回喂；票只能主人在终端发放，桥不发、不猜、不缓存；
  · 桥**不读不存任何凭据**；桥自己**不发任何网络请求**（联网需求走在册能力，由门审）；
  · 每轮最多 `MAX_BLOCKS_PER_ROUND` 块；`state/deepseek_bridge/PAUSE` 文件 = 急停闸；
  · 全程留痕：每轮追加 `rounds.jsonl`（超 2000 行裁到 1500，防无界增长）。

## 用法

    py -3.14 tools/codex-scripts/deepseek_bridge.py manifest            # 生成工具清单（粘贴用）
    py -3.14 tools/codex-scripts/deepseek_bridge.py manifest --json     # 附带机器可读版
    py -3.14 tools/codex-scripts/deepseek_bridge.py exec --file 回复.md --execute
    py -3.14 tools/codex-scripts/deepseek_bridge.py exec --clipboard    # 缺 --execute = 只解析不执行
    py -3.14 tools/codex-scripts/deepseek_bridge.py watch --execute     # 剪贴板闭环（Ctrl+C 停）
    py -3.14 tools/codex-scripts/deepseek_bridge.py status

## 为什么不做成能力位

桥是**执行层外面的接插件**，不是第 218 个能力：它自己没有 op 面板需要的语义，
它的每一分执行力都借自 run_task。做成能力位反而多出一条"桥调桥"的环。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 测试可以换一块自留地（P10 教训：判据不许把真盘当输出目录）
STATE = Path(os.environ.get("GBT_DS_BRIDGE_STATE") or (ROOT / "state" / "deepseek_bridge"))
MANIFEST_MD = STATE / "tool_manifest.md"
MANIFEST_JSON = STATE / "tool_manifest.json"
FEEDBACK_MD = STATE / "last_feedback.md"
ROUNDS = STATE / "rounds.jsonl"
PAUSE = STATE / "PAUSE"
WATCH_STATE = STATE / "watch_state.json"

MAX_BLOCKS_PER_ROUND = 8
_RESULT_BUDGET = 1800          # 单条结果回喂的最大字符数（超了截断，标记如实）
_ROUNDS_KEEP = 1500            # rounds.jsonl 裁剪后保留行数
_ROUNDS_MAX = 2000

# ```gbt 指令块解析器（2026-10-04 教训：正则 DOTALL 跨栏匹配会**吞掉单行块的收栏**，
# 把两个块并成一个坏捕获 ⇒ 改行级状态机，每个栏位逐行判定，行为可读可测）。
#
# 认三条形：
#   ```gbt              → 多行块，到独行 ``` 收栏
#   ```gbt json         → 同上（语言后缀容忍）
#   ```gbt {...}```     → 单行内联块
# ```gbt-result（回喂块）开栏即被排除：gbt 后紧跟字母/数字/- 都不算开栏
# —— 回喂块**绝不**被当成指令再吃进去（闭环自吞环）。


def _mk_entry(seq: int, raw: str) -> dict:
    entry = {"seq": seq, "raw": raw.strip()[:4000], "obj": None, "error": ""}
    try:
        obj = json.loads(entry["raw"])
        if not isinstance(obj, dict):
            entry["error"] = "指令块必须是 JSON 对象，收到 %s" % type(obj).__name__
        else:
            entry["obj"] = obj
    except Exception as exc:                                    # noqa: BLE001
        entry["error"] = "JSON 解析失败：%s" % str(exc)[:160]
    return entry


def _fence_at(line: str) -> int:
    """本行里 ```gbt 开栏的位置（gbt 后紧跟字母/数字/- 的不算开栏，如 ```gbt-result）。
    没有返回 -1。同一行多处开栏按第一个合法的算（指令块不往一行里塞两个）。"""
    idx = line.find("```gbt")
    while idx != -1:
        after = line[idx + 6:idx + 7]
        if not after or not re.match(r"[\w-]", after):
            return idx
        idx = line.find("```gbt", idx + 1)
    return -1


def extract_blocks(text: str) -> list:
    found = []
    lines = str(text or "").splitlines()
    i, n = 0, len(lines)
    while i < n:
        idx = _fence_at(lines[i])
        if idx < 0:
            i += 1
            continue
        rest = lines[i][idx + 6:].strip()
        if rest and not rest.startswith("{"):
            # 语言后缀（```gbt json …）—— 剥掉再判
            parts = rest.split(None, 1)
            rest = parts[1].strip() if len(parts) > 1 else ""
        if rest.startswith("{"):
            # 单行内联：取首个 { 到最后一个 }（后面的散文/收栏符都不属于 JSON）
            a, b = rest.find("{"), rest.rfind("}")
            raw = rest[a:b + 1] if (a >= 0 and b > a) else rest
            found.append(_mk_entry(len(found) + 1, raw))
            i += 1
            continue
        i += 1
        buf, closed = [], False
        while i < n:
            if lines[i].strip() == "```":
                closed = True
                break
            buf.append(lines[i])
            i += 1
        entry = _mk_entry(len(found) + 1, "\n".join(buf))
        if not closed and not entry["error"]:
            entry["error"] = "指令块缺收栏 ```（不完整的块）"
        found.append(entry)
        i += 1
    return found


def _caps():
    from gbt_allinone.caps_registry import all_caps
    return all_caps()


def _write_loop_cfg() -> str:
    """给桌面壳的**自主回路**写配置（主人令 2026-10-04：「她能直接操控触手实现自主运行」）。

    回路要自动跑就得知道桥在哪 —— 但**壳不许猜路径**：由桥把自己写进 app userData 下的
    `gbt-deepseek-loop.json`，壳只读配置（读不到 = 待配置，不假装在跑）。
    只写路径与解释器形状，**不写任何凭据**。
    """
    if sys.platform != "win32":
        return ""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return ""
    target = Path(appdata) / "GBT小土豆V8" / "gbt-deepseek-loop.json"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(
            {"bridge": str(Path(__file__).resolve()), "python": "py", "pythonArgs": ["-3.14"]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        return str(target)
    except OSError:
        return ""


def run_task_safe(kind: str, args: dict) -> dict:
    """唯一执行口。测试从这里替换（monkeypatch 本函数名）。"""
    from gbt_allinone.api import run_task
    return run_task(kind, args or {}, safe=True)


# ── ① 能力清单（眼睛：把"我有什么手"一项一项递给决策模块）─────────────────

def build_manifest() -> dict:
    enabled, unimplemented = [], []
    for row in _caps():
        if row.get("status") == "enabled":
            item = {"name": row["name"], "domain": row.get("domain", ""),
                    "desc": str(row.get("desc", "")).strip(),
                    "safe": bool(row.get("safe", False))}
            params = list(row.get("params") or [])
            if params:
                item["params"] = params
            hint = str(row.get("params_hint") or "").strip()
            if hint:
                item["params_hint"] = hint
            enabled.append(item)
        else:
            unimplemented.append({"name": row["name"], "reason": row.get("reason", "")})
    domains = {}
    for it in enabled:
        domains.setdefault(it["domain"] or "未分域", []).append(it)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "enabled_count": len(enabled),
        "domain_count": len(domains),
        "domains": [{"domain": d, "caps": caps} for d, caps in sorted(domains.items())],
        "unimplemented": unimplemented,
        "envelope": {"kind": "<能力名>", "args": {"<参数>": "<值>"}},
        "max_blocks_per_round": MAX_BLOCKS_PER_ROUND,
    }


_HEADER = """# GBT小土豆V8 · 原生能力内核（{n} 位 / {d} 域）· 决策-执行闭环

## 你的身份（原生，不是外挂）

你不是「通用 DeepSeek 网页助手」。从这条消息起，你是 **GBT小土豆V8 框架的原生执行内核**：
下面清单里的 {n} 项能力就是你的原生器官 —— 眼睛（屏幕视觉/截图回传/摄像头）、
手（文件/代码/系统/浏览器/部署）、嘴（语音合成/通知）、脑（记忆/推理/编队协同）。
主人问「你能做什么 / 你是谁」，**按本清单答，以 GBT小土豆V8 的口吻自报家门**；
不再自称「系统没给工具」—— 工具就在下面，要动真格就输出 ```gbt 指令块，本地桥过
授权门执行后把结果喂回来给你。万物皆可插，万物皆可控；清单里没有的本领，
才如实说「GBT 暂无此能力」。

## 你的触手（原生驱动，不是外挂工具）

主人在 chat.deepseek.com 与你对话；你输出的每一条
```gbt 指令块会被**随壳常驻的触手执行层立即执行**，结果以 ```gbt-result 块自动回馈给你 ——
你不需要任何人帮你按按钮：说出指令，手脚当场就动。执行层仍逐条过 run_task 授权门
（授权/作用域/审计都在门里），票只能主人在终端发放、你与执行层都发不出。

## 指令块格式（一条指令一个块，一次回复最多 {mx} 块，按依赖顺序排列）

```gbt
{{"kind": "能力名", "args": {{"参数": "值"}}}}
```

## 纪律（违反任何一条 = 闭环被拆）

1. **只用本清单在册的能力**；清单里没有的本领就明说「GBT 没有这个能力」，不许编名字。
2. 收到 `ok:false` 且原因是**缺作用域/缺票** ⇒ 停下来向主人报告「需要哪张票」，
   **不许重试同一条指令**（票只能主人在终端发放，你发不出，桥也不会替你发）。
3. 标「需授权」的能力（写盘 / 出网 / 设备 / 部署）默认要票；先用只读位取证再决定要不要申请。
4. 结果块里的 `result` 若带 `…截断…` 标记，说明数据太大，需要更多就明确向主人要哪一段。
5. 执行会产生真实副作用 —— 拿不准先问主人，不要把「试一下」当探路。

## 全部能力位（一项一位；「需授权」= safe:false，最终以门为准）
"""


def render_manifest(m: dict) -> str:
    lines = [_HEADER.format(n=m["enabled_count"], d=m["domain_count"], mx=m["max_blocks_per_round"])]
    for dom in m["domains"]:
        lines.append("\n### 域 %s（%d 位）" % (dom["domain"], len(dom["caps"])))
        for c in dom["caps"]:
            ticket = "只读倾向" if c.get("safe") else "**需授权**"
            line = "\n- **%s**（%s）— %s" % (c["name"], ticket, c["desc"] or "（无描述）")
            if c.get("params"):
                line += "；入参: %s" % ", ".join(c["params"])
            if c.get("params_hint"):
                line += "（%s）" % c["params_hint"]
            lines.append(line)
    if m["unimplemented"]:
        lines.append("\n## 登记未实现（只有名字、没有实现 —— **不许调用**，调了只会得到拒绝回执）\n")
        for u in m["unimplemented"]:
            lines.append("- %s — %s" % (u["name"], u["reason"]))
    lines.append("\n---\n\n> 清单由 `py -3.14 tools/codex-scripts/deepseek_bridge.py manifest` 于 %s 生成；"
                 "能力位增减后**重新生成再粘贴**。\n" % m["generated_at"])
    return "".join(lines)


def cmd_manifest(args: argparse.Namespace) -> int:
    m = build_manifest()
    STATE.mkdir(parents=True, exist_ok=True)
    md = render_manifest(m)
    MANIFEST_MD.write_text(md, encoding="utf-8")
    print("工具清单已生成：%s（%d 位 / %d 域，%d 字符）"
          % (MANIFEST_MD, m["enabled_count"], m["domain_count"], len(md)))
    print("用法：把整份文件内容粘贴进 chat.deepseek.com 对话（粘一次即可，能力位增减后重新生成再粘）。")
    loop_cfg = _write_loop_cfg()
    if loop_cfg:
        print("桌面壳自主回路配置已就位：%s" % loop_cfg)
    if args.json:
        MANIFEST_JSON.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        print("机器可读版：%s" % MANIFEST_JSON)
    return 0


# ── ② 指令解析（extract_blocks 在文件头部常量区旁，行级状态机）────────────

def _compact(obj, budget: int = _RESULT_BUDGET) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception as exc:                                    # noqa: BLE001
        s = "<结果不可序列化: %s>" % str(exc)[:120]
    if len(s) <= budget:
        return s
    head, tail = budget - 320, 240
    return "%s\n…截断（原 %d 字符，需要更多请明确要哪一段）…\n%s" % (s[:head], len(s), s[-tail:])


# ── ③ 执行 + 回喂（手脚：过门执行，结果喂回去）───────────────────────────

def execute_round(text: str, source: str, execute: bool) -> dict:
    """解析 → 校验 → 执行 → 回喂。一段 DeepSeek 回复 = 一轮。"""
    if PAUSE.exists():
        return {"ok": False, "why": "急停闸生效：%s 存在，删除该文件后恢复" % PAUSE,
                "found": 0, "results": [], "summary": "PAUSED"}
    blocks = extract_blocks(text)
    enabled = {c["name"] for c in _caps() if c.get("status") == "enabled"}
    results, kinds = [], []
    ok = failed = rejected = 0
    for b in blocks[:MAX_BLOCKS_PER_ROUND]:
        row = {"seq": b["seq"], "kind": "", "executed": False}
        if b["error"]:
            row.update(ok=False, error=b["error"], note="解析层拒绝（未进执行层）")
            rejected += 1
            results.append(row)
            continue
        obj = b["obj"]
        kind = str(obj.get("kind") or "").strip()
        args = obj.get("args") if isinstance(obj.get("args"), dict) else {}
        row["kind"] = kind
        if kind not in enabled:
            row.update(ok=False,
                       error="kind 不在 GBT 在册能力里（拼错或编造——连授权门都到不了，已拦在解析层）",
                       note="拒绝；可用能力见工具清单")
            rejected += 1
            results.append(row)
            continue
        kinds.append(kind)
        if not execute:
            row.update(ok=None, executed=False, note="dry-run：只解析未执行（加 --execute 才会真跑）")
            results.append(row)
            continue
        row["executed"] = True
        t0 = time.time()
        try:
            env = run_task_safe(kind, args)
        except Exception as exc:                                # noqa: BLE001
            env = {"ok": False, "kind": kind, "error": "桥执行层异常：%s" % str(exc)[:200]}
        dt = time.time() - t0
        row["ok"] = bool(env.get("ok"))
        row["error"] = env.get("error") or ""
        row["result"] = _compact(env.get("result", env))
        row["ms"] = round(dt * 1000)
        if row["ok"]:
            ok += 1
        else:
            failed += 1
        results.append(row)
    skipped = max(0, len(blocks) - MAX_BLOCKS_PER_ROUND)
    summary = ("%d 块：%d ok · %d 失败 · %d 解析层拒绝 · %d 超额跳过"
               % (len(blocks), ok, failed, rejected, skipped))
    if not blocks:
        summary = "没找到 ```gbt 指令块 —— DeepSeek 这段回复里没有指令"
    rnd = {"ts": datetime.now().isoformat(timespec="seconds"), "source": source,
           "mode": "execute" if execute else "dry", "found": len(blocks),
           "executed": len([r for r in results if r.get("executed")]),
           "ok": ok, "failed": failed, "rejected": rejected, "skipped": skipped,
           "kinds": kinds, "summary": summary}
    _log_round(rnd)
    rnd["results"] = results
    return rnd


def _log_round(rnd: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    row = {k: rnd[k] for k in ("ts", "source", "mode", "found", "executed",
                               "ok", "failed", "rejected", "skipped", "kinds", "summary")}
    with ROUNDS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    try:
        lines = ROUNDS.read_text(encoding="utf-8").splitlines()
        if len(lines) > _ROUNDS_MAX:
            ROUNDS.write_text("".join(l + "\n" for l in lines[-_ROUNDS_KEEP:]), encoding="utf-8")
    except OSError:
        pass


def render_feedback(rnd: dict) -> str:
    """把一轮结果打成粘回 DeepSeek 的反馈块。"""
    payload = {"round_ts": rnd.get("ts"), "mode": rnd.get("mode"),
               "summary": rnd.get("summary"),
               "results": [{k: r[k] for k in r if k != "note"} | ({"note": r["note"]} if r.get("note") else {})
                           for r in rnd.get("results", [])]}
    if rnd.get("why"):
        payload["halted"] = rnd["why"]
    return "请依据以下执行结果继续（```gbt-result 由 GBT 桥回喂）：\n\n```gbt-result\n%s\n```\n" % _compact(payload)


def cmd_feed(args: argparse.Namespace) -> int:
    """一键投喂（主人令 2026-10-04：能力要化成她的原生能力）。

    新对话里 DeepSeek 说「系统没给工具」是**真话** —— 清单没进上下文，她就是裸助手。
    feed 把【身份 + 闭环纪律 + 全部能力清单】整段放上剪贴板：主人在对话窗里
    Ctrl+V → 发送，她的全部能力即刻原生化（该对话内长期有效；新开对话再 feed 一次）。
    """
    m = build_manifest()
    md = render_manifest(m)
    STATE.mkdir(parents=True, exist_ok=True)
    MANIFEST_MD.write_text(md, encoding="utf-8")
    ok = clip_write(md)
    print("身份+纪律+全部能力清单已上剪贴板（%d 位 / %d 域，%d 字符）：%s"
          % (m["enabled_count"], m["domain_count"], len(md),
             "OK" if ok else "🔴 写剪贴板失败 —— 手动用文件 " + str(MANIFEST_MD)))
    loop_cfg = _write_loop_cfg()
    if loop_cfg:
        print("桌面壳自主回路配置已就位：%s（壳重启后自动开跑）" % loop_cfg)
    print("下一步：切到「GBT小土豆V8 · 对话（DeepSeek）」窗 → 输入框 Ctrl+V → 回车发送。")
    print("发送后她即以 GBT 原生执行内核应答；设好自主回路后，她的指令块会被**自动**执行并回喂。")
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
        source = "file:" + str(args.file)
    elif args.clipboard:
        text = clip_read()
        source = "clipboard"
        if not text.strip():
            print("剪贴板是空的 —— 先在 DeepSeek 网页复制它的回复，再跑本命令。")
            return 2
    else:
        text = sys.stdin.read()
        source = "stdin"
    rnd = execute_round(text, source, execute=bool(args.execute))
    STATE.mkdir(parents=True, exist_ok=True)
    FEEDBACK_MD.write_text(render_feedback(rnd), encoding="utf-8")
    print(rnd.get("summary") or rnd.get("why", ""))
    print("反馈块（粘回 DeepSeek）：%s" % FEEDBACK_MD)
    if rnd.get("why"):
        print("⚠ %s" % rnd["why"])
    return 0


# ── ④ 剪贴板闭环（watch：复制 DeepSeek 回复 → 桥执行 → 剪贴板里是反馈块）────

def clip_read() -> str:
    """读剪贴板文本（CF_UNICODETEXT）。三层递进 + 整口兜底（2026-10-04 两轮实测教训）。

    实测一：裸 `wstring_at(p)` 在句柄竞态（写入方正在改）下 access violation —— 炸循环。
    实测二：Chromium 系写入方的句柄 `GlobalSize` 会返回 **0**（实测本机现读）——
            按「量为 0 即空」就永远读不到 PowerShell 明明读得到的内容。
    修法：① OpenClipboard 3 次快速重试抗争用；② GlobalSize>0 走定界读（金标准）；
          ③ GlobalSize==0 走「试整读 → 1M/64K/4K 分级定界」阶梯，读到的都截到首个 NUL；
          ④ 任何一层异常 = 本轮跳过返回空串，**绝不许把 watch 循环带崩**。
    """
    if sys.platform != "win32":
        return ""
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
 # 64 位纪律（2026-10-04 第三轮实测抓出）：不声明 restype/argtypes 时，
    #    GlobalLock 返回的 **64 位指针被 ctypes 默认 c_int 截成 32 位** —— 拿去解引用
    #    轻则读空、重则 AV（最初那次「access violation」的真根因就是它，不是剪贴板本身）。
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool
    user32.CloseClipboard.restype = ctypes.c_bool
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    CF_UNICODETEXT = 13
    for _attempt in range(3):
        opened = False
        try:
            if not user32.OpenClipboard(0):
                time.sleep(0.15)
                continue
            opened = True
            h = user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return ""
            p = kernel32.GlobalLock(h)
            if not p:
                return ""
            try:
                size = int(kernel32.GlobalSize(h) or 0)   # 字节数（UTF-16 每符 2 字节）
                if size > 0:
                    text = ctypes.wstring_at(p, min(size // 2, 4 * 1024 * 1024))
                    return text.split("\x00")[0]
                # GlobalSize 谎报 0（Chromium 系）：试整读，再分级定界，谁成用谁
                for cap in (None, 1 * 1024 * 1024, 64 * 1024, 4 * 1024):
                    try:
                        text = (ctypes.wstring_at(p) if cap is None
                                else ctypes.wstring_at(p, cap))
                        return text.split("\x00")[0]
                    except Exception:                       # noqa: BLE001
                        continue
                return ""
            finally:
                kernel32.GlobalUnlock(h)
        except Exception:                                   # noqa: BLE001
            continue                                        # 句柄竞态等：下一轮重试
        finally:
            if opened:
                try:
                    user32.CloseClipboard()
                except Exception:                           # noqa: BLE001
                    pass
    return ""


def clip_write(text: str) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    try:
        user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
        # 64 位纪律同 clip_read（见那里的注释）——GlobalAlloc/GlobalLock 全要真指针
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.EmptyClipboard.restype = ctypes.c_bool
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
        buf = ctypes.create_unicode_buffer(text)
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, ctypes.sizeof(buf))
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        if not p:
            kernel32.GlobalFree(h)
            return False
        try:
            ctypes.memmove(p, buf, ctypes.sizeof(buf))
        finally:
            kernel32.GlobalUnlock(h)
        if not user32.OpenClipboard(0):
            kernel32.GlobalFree(h)
            return False
        try:
            user32.EmptyClipboard()
            user32.SetClipboardData(CF_UNICODETEXT, h)   # 成功后 h 归系统，不再 free
        finally:
            user32.CloseClipboard()
        return True
    except Exception:                                       # noqa: BLE001
        return False


def cmd_watch(args: argparse.Namespace) -> int:
    interval = max(0.8, float(args.interval))
    last_hash = ""
    if WATCH_STATE.exists():
        try:
            last_hash = json.loads(WATCH_STATE.read_text(encoding="utf-8")).get("last_hash", "")
        except Exception:                                       # noqa: BLE001
            last_hash = ""
    mode = "执行" if args.execute else "只解析（dry）"
    print("watch 启动（%s，%.1fs 一轮）：在 DeepSeek 网页复制它的回复 ⇒ 桥自动执行 ⇒ "
          "反馈块自动上剪贴板，粘回对话即可。Ctrl+C 停。" % (mode, interval))
    print("急停：新建文件 %s 即停。" % PAUSE)
    try:
        while True:
            if PAUSE.exists():
                print("…急停闸生效，暂停监听（删除 %s 恢复）" % PAUSE)
                time.sleep(interval)
                continue
            cur = clip_read()
            if not cur or not extract_blocks(cur):
                time.sleep(interval)
                continue
            h = hashlib.sha256(cur.encode("utf-8", "replace")).hexdigest()
            if h == last_hash:
                time.sleep(interval)
                continue
            last_hash = h
            WATCH_STATE.write_text(json.dumps({"last_hash": h}, ensure_ascii=False), encoding="utf-8")
            rnd = execute_round(cur, "watch", execute=bool(args.execute))
            if rnd.get("why"):
                print("⚠ %s" % rnd["why"])
                time.sleep(interval)
                continue
            feedback = render_feedback(rnd)
            STATE.mkdir(parents=True, exist_ok=True)
            FEEDBACK_MD.write_text(feedback, encoding="utf-8")
            if args.execute:
                clip_write(feedback)
            print("[%s] %s → 反馈已%s（%s）"
                  % (rnd["ts"], rnd["summary"],
                     "上剪贴板" if args.execute else "落盘（dry 未执行）", FEEDBACK_MD))
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nwatch 已停（急停文件法随时可用：%s）" % PAUSE)
        return 0


def cmd_status(_args: argparse.Namespace) -> int:
    from gbt_allinone.caps_registry import all_caps
    enabled = [c for c in all_caps() if c.get("status") == "enabled"]
    print("在册能力位：%d（清单导出口 deepseek_bridge.py manifest）" % len(enabled))
    print("对话窗：壳 dsh-chat → https://chat.deepseek.com/（免费原生网页，决策模块在此）")
    print("急停闸：%s" % ("**生效中**（删除该文件恢复）" if PAUSE.exists() else "未触发"))
    print("清单：", MANIFEST_MD, "（生成于 %s）"
          % (time.strftime("%Y-%m-%d %H:%M", time.localtime(MANIFEST_MD.stat().st_mtime))
             if MANIFEST_MD.exists() else "从未生成 —— 先跑 manifest"))
    if ROUNDS.exists():
        tail = ROUNDS.read_text(encoding="utf-8").splitlines()[-3:]
        print("最近轮次：")
        for l in tail:
            try:
                r = json.loads(l)
                print("  %s [%s|%s] %s" % (r.get("ts"), r.get("mode"), r.get("source"), r.get("summary")))
            except Exception:                                   # noqa: BLE001
                print("  <坏行>", l[:80])
    else:
        print("最近轮次：还没有（rounds.jsonl 不存在）")
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="DeepSeek 免费决策桥（GBT 能力接入）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("manifest", help="导出全部能力位 → DeepSeek 工具清单")
    m.add_argument("--json", action="store_true", help="同时落机器可读版 tool_manifest.json")
    m.set_defaults(fn=cmd_manifest)
    f = sub.add_parser("feed", help="一键投喂：身份+纪律+全部清单 → 剪贴板（对话窗 Ctrl+V 发送即原生化）")
    f.set_defaults(fn=cmd_feed)
    e = sub.add_parser("exec", help="执行一段 DeepSeek 回复里的指令块")
    src = e.add_mutually_exclusive_group()
    src.add_argument("--file", help="从文件读回复")
    src.add_argument("--clipboard", action="store_true", help="从剪贴板读回复")
    e.add_argument("--execute", action="store_true", help="真执行（缺省只解析不执行）")
    e.set_defaults(fn=cmd_exec)
    w = sub.add_parser("watch", help="剪贴板闭环监听")
    w.add_argument("--execute", action="store_true", help="真执行（缺省只解析）")
    w.add_argument("--interval", type=float, default=1.5, help="轮询秒数（下限 0.8）")
    w.set_defaults(fn=cmd_watch)
    s = sub.add_parser("status", help="闭环现状")
    s.set_defaults(fn=cmd_status)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
