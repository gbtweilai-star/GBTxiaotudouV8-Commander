#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page_probe —— 页面自报读数的读取端（2026-10-30）

问题：页面好不好，以前只能"打开看一眼"。这在手机上既慢又不可复核。

做法：页面带 `?_probe=1` 打开时，自己把关键读数 POST 到桥的 `/_probe`，
      桥追加 `state/page_probes.jsonl`。本器读那个账，按页聚合出：
        · 最后一次自报是什么时候（新鲜度）
        · ok / 否
        · 关键读数（tok/s、三角形、像素亮度…）

用法：
    python3 tools/page_probe.py status          # 人读
    python3 tools/page_probe.py status --json   # 机读
    python3 tools/page_probe.py status --max-age 3600   # 只认 1 小时内的
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "page_probes.jsonl"
BASELINE = ROOT / "state" / "page_probe_baseline.json"

# 只盯**会说话**的键：布尔类严格一致；tps 掉 30% 以上算退化；tris 变少算退化。
BOOL_KEYS = ("cap_reached", "cap_ok", "func_ok")
STR_KEYS = ("top1", "cap_domain", "cap_name", "func_name")


def load_baseline() -> dict:
    if not BASELINE.is_file():
        return {}
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}


def save_baseline(data: dict) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def make_baseline() -> dict:
    """把当前每页最后一次读数存成基线（只存可比的键）。"""
    cur = aggregate()
    out = {}
    for it in cur["pages"]:
        rd = it.get("readings") or {}
        keep = {}
        for k in BOOL_KEYS + STR_KEYS:
            if k in rd and rd[k] is not None:
                keep[k] = rd[k]
        for k in ("tps", "tris"):
            if rd.get(k) is not None:
                keep[k] = rd[k]
        if keep:
            out[it["page"]] = keep
    return out


def diff_baseline(rd: dict, base: dict) -> list:
    """→ [『键: 旧 → 新』...]。空列表 = 无退化。"""
    bad = []
    for k in BOOL_KEYS:
        if k in base and base[k] is True and rd.get(k) is not True:
            bad.append("%s: True → %s" % (k, rd.get(k)))
    for k in STR_KEYS:
        if k in base and rd.get(k) is not None and rd.get(k) != base[k]:
            bad.append("%s: %r → %r" % (k, base[k], rd.get(k)))
    if base.get("tps") and rd.get("tps") is not None:
        if rd["tps"] < base["tps"] * 0.7:
            bad.append("tps: %s → %s（掉 30%%+）" % (base["tps"], rd["tps"]))
    if base.get("tris") and rd.get("tris") is not None:
        if rd["tris"] < base["tris"]:
            bad.append("tris: %s → %s" % (base["tris"], rd["tris"]))
    return bad


def load() -> list:
    if not LEDGER.is_file():
        return []
    out = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:                                        # noqa: BLE001
            pass
    return out


# ── 判决规则（2026-10-30）─────────────────────────────────────────────
# 为什么要有：账上只有数字时，人还得自己判断"这个数算好还是坏"。
# 每条规则都必须能指回一个具体读数，不猜。
TPS_MIN = {"gpu": 30.0, "js": 8.0}


def judge(readings: dict, ok_flag: bool) -> tuple:
    """→ (verdict, reason)。verdict ∈ ok / red / warn"""
    rd = readings or {}
    # ②b 穿透证据：能调能力位，且分三态（门没通 / 门通了该位报错 / 全 OK）
    if "cap_reached" in rd or "cap_ok" in rd:
        dom = rd.get("cap_domain")
        cap = rd.get("cap_name") or "?"
        ms = rd.get("cap_ms")
        if rd.get("cap_reached") is False and not rd.get("cap_ok"):
            return "red", "页面调不到能力位（%s）" % (rd.get("cap_err") or "no-json")
        if not rd.get("cap_ok"):
            return "warn", "门通了，但 %s 自身报错（域=%s）· %s" % (
                cap, dom, (rd.get("cap_err") or "")[:50])
        if rd.get("func_ok") is False:
            return "warn", "功能没发生：%s · %s" % (rd.get("func_name"),
                                                   (rd.get("func_evidence") or "")[:50])
        parts = ["穿透 ok", "域=%s" % dom, cap, "%sms" % ms, "python %s" % rd.get("cap_python")]
        if rd.get("func_name"):
            parts.append("功能 %s ✓（%s）" % (rd.get("func_name"), (rd.get("func_evidence") or "")[:30]))
        if rd.get("tps") is not None:
            parts.append("%s tok/s" % rd.get("tps"))
        if rd.get("top1") is not None:
            parts.append("top-1 %r" % rd.get("top1"))
        return "ok", " · ".join(parts)


    if not ok_flag:
        return "red", "页面自己报了 ok=false"
    # ① 3D 页：看三角形与帧
    if "tris" in rd:
        tris = rd.get("tris") or 0
        frames = rd.get("frames") or 0
        if tris <= 100:
            return "red", "模型没进画面（tris=%s ≤ 100）" % tris
        if frames == 0:
            return "red", "帧驱动没启动（frames=0，tris=%s 说明几何在提交）" % tris
        if frames < 10:
            return "warn", "帧数偏低（frames=%s）—— 疑似后台标签节流" % frames
        return "ok", "tris=%s · frames=%s · 非黑 %s%%" % (tris, frames, rd.get("nonblack"))
    # ② 推理页：看 top-1 与速度
    if "top1" in rd or "tps" in rd:
        top1 = str(rd.get("top1") or "")
        backend = str(rd.get("backend") or "")
        tps = float(rd.get("tps") or 0)
        if "endoftext" in top1 or "<|" in top1:
            return "red", "top-1 是特殊 token（%r）—— 分布崩了" % top1
        if (rd.get("rows_bad") or 0) > 0:
            return "red", "自检有 %s 项红" % rd.get("rows_bad")
        floor = TPS_MIN.get(backend)
        if floor and tps < floor:
            return "red", "速度 %s < %s（%s 后端门槛）" % (tps, floor, backend)
        return "ok", "%s · %s tok/s · top-1 %r" % (backend, tps, top1)
    # ③ 其它页：只认 ok
    return "ok", "ok"


def aggregate(max_age: float | None = None, compare: bool = True) -> dict:
    rows = load()
    now = time.time()
    per = {}
    for r in rows:
        page = r.get("page") or "?"
        try:
            t = time.mktime(time.strptime(r.get("at", ""), "%Y-%m-%dT%H:%M:%S"))
        except Exception:                                        # noqa: BLE001
            continue
        if max_age is not None and now - t > max_age:
            continue
        cur = per.get(page)
        if cur is None or t > cur["_ts"]:
            per[page] = {"page": page, "at": r.get("at"), "ok": bool(r.get("ok")),
                         "readings": r.get("readings") or {}, "_ts": t,
                         "age_s": int(now - t)}
    base_all = load_baseline() if compare else {}
    items = sorted(per.values(), key=lambda x: x["_ts"], reverse=True)
    for it in items:
        it.pop("_ts", None)
        v, why = judge(it.get("readings"), it.get("ok"))
        base = base_all.get(it.get("page")) or {}
        deg = diff_baseline(it.get("readings") or {}, base) if base else []
        it["regressions"] = deg
        if deg and v == "ok":
            v, why = "warn", "相对基线退化：" + " · ".join(deg[:3])
        elif deg:
            why = why + " ｜退化：" + " · ".join(deg[:2])
        it["verdict"], it["why"] = v, why
    ok_n = sum(1 for x in items if x["verdict"] == "ok")
    warn_n = sum(1 for x in items if x["verdict"] == "warn")
    red_n = sum(1 for x in items if x["verdict"] == "red")
    return {"pages": items, "total": len(items), "ok": ok_n, "warn": warn_n,
            "fail": red_n, "ledger": str(LEDGER)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("op", nargs="?", default="status", choices=["status", "selftest", "baseline"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-age", type=float, default=None,
                    help="只认这么多秒内的自报（默认不限）")
    a = ap.parse_args(argv)

    if a.op == "baseline":
        b = make_baseline()
        save_baseline(b)
        print("  已存基线：%d 页 → %s" % (len(b), BASELINE))
        for k, v in list(b.items())[:8]:
            print("   %-34s %s" % (k[-34:], json.dumps(v, ensure_ascii=False)[:80]))
        return 0

    if a.op == "selftest":
        # 铁证：证明判决规则真的会亮红灯（不是只会在绿的时候显示绿）
        cases = [
            ("3D 缺人物", {"tris": 12, "frames": 5}, True, "red"),
            ("3D 帧没起", {"tris": 20545, "frames": 0}, True, "red"),
            ("3D 节流",   {"tris": 20545, "frames": 2}, True, "warn"),
            ("3D 正常",   {"tris": 20545, "frames": 40, "nonblack": 13}, True, "ok"),
            ("推理崩",    {"backend": "gpu", "tps": 40, "top1": "<|endoftext|>"}, True, "red"),
            ("推理慢",    {"backend": "gpu", "tps": 10, "top1": " Paris"}, True, "red"),
            ("推理正常",  {"backend": "gpu", "tps": 38, "top1": " Paris"}, True, "ok"),
            ("页面自报失败", {"tris": 20545, "frames": 40}, False, "red"),
            ("穿透成功",   {"cap_reached": True, "cap_ok": True, "cap_domain": "llm",
                            "cap_name": "codex_status", "cap_ms": 27, "cap_python": "3.12.14"}, True, "ok"),
            ("门没通",     {"cap_reached": False, "cap_ok": False, "cap_err": "TypeError"}, True, "red"),
            ("门通位不可用", {"cap_reached": True, "cap_ok": False, "cap_domain": "llm",
                            "cap_name": "codex_status", "cap_err": "缺 codex 可执行文件"}, True, "warn"),
            ("功能发生",   {"cap_reached": True, "cap_ok": True, "cap_domain": "voice",
                          "cap_name": "voice_orchestra", "cap_python": "3.12.14",
                          "func_name": "voice_asset", "func_ok": True,
                          "func_evidence": "voice-greet.mp3 57312 B"}, True, "ok"),
            ("功能没发生", {"cap_reached": True, "cap_ok": True, "cap_domain": "system",
                          "cap_name": "health", "cap_python": "3.12.14",
                          "func_name": "panel_state", "func_ok": False,
                          "func_evidence": "Load failed"}, True, "warn"),
            # 基线退化（diff_baseline 的判据本身也要被证明）
            ("基线-布尔退化", "__DIFF__", {"base": {"cap_ok": True}, "cur": {"cap_ok": False},
                                          "expect": "cap_ok: True → False"}),
            ("基线-top1变",   "__DIFF__", {"base": {"top1": " Paris"}, "cur": {"top1": " London"},
                                          "expect": "top1"}),
            ("基线-速度掉",   "__DIFF__", {"base": {"tps": 38}, "cur": {"tps": 20},
                                          "expect": "掉 30%+"}),
            ("基线-无退化",   "__DIFF__", {"base": {"tps": 38}, "cur": {"tps": 37},
                                          "expect": None}),
        ]
        bad = 0
        for case in cases:
            name, rd = case[0], case[1]
            okf = case[2] if len(case) > 2 else None
            want = case[3] if len(case) > 3 else None
            if rd == "__DIFF__":
                _b, _c, _e = okf["base"], okf["cur"], okf["expect"]
                deg = diff_baseline(_c, _b)
                want_deg = _e if False else _e
                if want_deg:
                    good = any(want_deg in d for d in deg)
                    print("   %s %-14s → %s（期望含 %r）· %s"
                          % ("✅" if good else "🔴", name, deg, want_deg, ""))
                    if not good:
                        bad += 1
                else:
                    good = not deg
                    print("   %s %-14s → %s（期望无退化）" % ("✅" if good else "🔴", name, deg))
                    if not good:
                        bad += 1
                continue
            v, why = judge(rd, okf)
            good = (v == want)
            if not good:
                bad += 1
            print("   %s %-14s → %-5s（期望 %-5s）· %s"
                  % ("✅" if good else "🔴", name, v, want, why))
        print("  自测 %d/%d 通过" % (len(cases) - bad, len(cases)))
        if a.json:
            print(json.dumps({"ok": bad == 0, "cases": len(cases), "bad": bad}))
        return 0 if bad == 0 else 1

    res = aggregate(a.max_age)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if res["total"] else 2

    print("  页面自报账 · %d 页（ok %d / 警告 %d / 红 %d）"
          % (res["total"], res["ok"], res["warn"], res["fail"]))
    if not res["pages"]:
        print("  还没有任何页面自报过。让页面带 ?_probe=1 打开一次。")
        return 2
    for it in res["pages"]:
        mark = {"ok": "✅", "warn": "⚠️", "red": "🔴"}[it["verdict"]]
        print("   %s %-30s %5ds 前 · %s" % (mark, it["page"][-30:], it["age_s"], it["why"]))
    return 0 if res["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
