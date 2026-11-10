# -*- coding: utf-8 -*-
"""native-vision-policy-check — 固化判据：原生视觉实时链路是不是默认主流。

主人令 2026-11-07：万能插直接看帧/视频回传大模型看；原生能力脑眼手同步实时执行。

判据（缺一条就是回归）：
  ① state/vision-policy.json 可解析，default_lane=native_realtime；
  ② 五段链齐全：continuous_capture / native_observe / model_sees_frames_directly /
     action_via_omni_plug / frame_diff_verify；
  ③ 400ms 新鲜度、帧直接给模型、禁止截图串行默认；
  ④ AGENTS.md 写死这条口径并引用策略文件；
  ⑤ vision_loop / body_realtime 仍在能力注册表，vision_loop.STALE_MS 仍为 400；
  ⑥ capability_router 的单帧看屏回执带 lane=single_frame_fallback（不再冒充实时）；
  ⑦ 对话层接线状态必须显式声明（pending/done），不允许悄悄当成已打通。

用法：.\\pyembed\\python.exe tools\\codex-scripts\\native-vision-policy-check.py [--json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "state" / "vision-policy.json"
AGENTS = ROOT / "AGENTS.md"
DOC = ROOT / "docs" / "原生视觉实时链路.md"
BLUEPRINT = ROOT / "PROJECT_BLUEPRINT.md"
REGISTRY = ROOT / "gbt_allinone" / "caps_registry.py"
LOOP = ROOT / "gbt_allinone" / "vision_loop.py"
ROUTER = ROOT / "gbt_allinone" / "capability_router.py"
CONSOLE = ROOT / "tools" / "console-server.py"
OMNI = ROOT / "gbt_allinone" / "omni_plug.py"

CHAIN = ("continuous_capture", "native_observe", "model_sees_frames_directly",
         "action_via_omni_plug", "frame_diff_verify")
BLUEPRINT_MARK = "2026-11-07 · 原生视觉实时链路定为默认主流"


def check() -> list[dict]:
    rows: list[dict] = []

    def ck(name: str, ok: bool, detail: object = "") -> None:
        rows.append({"name": name, "ok": bool(ok), "detail": str(detail)[:240]})

    pol: dict = {}
    try:
        pol = json.loads(POLICY.read_text(encoding="utf-8"))
        ck("policy:parses", isinstance(pol, dict), str(POLICY))
    except Exception as exc:                                     # noqa: BLE001
        ck("policy:parses", False, "%s: %s" % (type(exc).__name__, exc))

    ck("policy:default_lane", pol.get("default_lane") == "native_realtime",
       pol.get("default_lane"))
    chain = list(pol.get("chain") or [])
    ck("policy:chain", all(x in chain for x in CHAIN), chain)
    rules = pol.get("rules") or {}
    ck("policy:freshness_ms", rules.get("freshness_ms") == 400, rules.get("freshness_ms"))
    ck("policy:frames_direct", rules.get("frames_go_to_model_directly") is True,
       rules.get("frames_go_to_model_directly"))
    ck("policy:forbid_screenshot_first",
       "screenshot_then_text_then_blind_action" in (pol.get("forbidden_defaults") or []),
       pol.get("forbidden_defaults"))
    _cs = CONSOLE.read_text(encoding="utf-8") if CONSOLE.is_file() else ""
    _om = OMNI.read_text(encoding="utf-8") if OMNI.is_file() else ""
    wiring = pol.get("wiring") or {}
    # ⑧ 「done」不能只是嘴上说：声明成 done 就必须在 console-server 里找到帧直送模型的硬证据
    _chat_state = wiring.get("chat_layer")
    _chat_ok = _chat_state in ("pending", "done")
    _chat_detail = str(_chat_state)
    if _chat_state == "done":
        _miss = [x for x in ("_image_data_url", "image_url", "image_path=_screen_path",
                                 "_mark_frame_degraded", "why_degraded") if x not in _cs]
        _chat_ok = _chat_ok and not _miss
        _chat_detail = "done · 帧直送模型 + 降级标记" if not _miss else "done 但代码缺 %s" % (_miss,)
    ck("policy:chat_wiring_declared", _chat_ok, _chat_detail)

    try:
        agents = AGENTS.read_text(encoding="utf-8")
        ck("agents:section", "原生视觉实时链路" in agents)
        ck("agents:policy_ref", "state/vision-policy.json" in agents)
    except Exception as exc:                                     # noqa: BLE001
        ck("agents:read", False, exc)

    reg = REGISTRY.read_text(encoding="utf-8") if REGISTRY.is_file() else ""
    ck("registry:vision_loop", '"vision_loop"' in reg)
    ck("registry:body_realtime", '"body_realtime"' in reg)

    loop = LOOP.read_text(encoding="utf-8") if LOOP.is_file() else ""
    ck("vision_loop:stale_400", "STALE_MS = 400" in loop)

    router = ROUTER.read_text(encoding="utf-8") if ROUTER.is_file() else ""
    ck("router:screen_fallback_marked", "single_frame_fallback" in router)

    bp = BLUEPRINT.read_text(encoding="utf-8") if BLUEPRINT.is_file() else ""
    ck("blueprint:policy_entry", BLUEPRINT_MARK in bp)

    ck("omni:frame_path", "_persist_frame(" in _om and "FRAME_DIR" in _om,
       "取帧落一份有界缓存并回传 path")
    ck("chat:pulse_skipped_after_frame", "not _screen_meta" in _cs,
       "已取到帧就不再让 pulse / method lane 重复决策")
    ck("doc:exists", DOC.is_file(), str(DOC))
    return rows


def main(argv: list[str] | None = None) -> int:
    rows = check()
    bad = [r for r in rows if not r["ok"]]
    args = list(argv if argv is not None else sys.argv[1:])
    if "--json" in args:
        print(json.dumps({"ok": not bad, "rows": rows}, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print("%s  %-34s %s" % ("PASS" if r["ok"] else "FAIL", r["name"], r["detail"]))
        print("\n%s  %d/%d" % ("PASS" if not bad else "FAIL",
                                len(rows) - len(bad), len(rows)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
