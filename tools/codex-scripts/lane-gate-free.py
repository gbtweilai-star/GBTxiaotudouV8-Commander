# -*- coding: utf-8 -*-
"""现役车道闸（**本地道**）—— 这条闸的第三次改写。

## 三代沿革（每次都只因为一件事：判据要量在役的东西）

1. **一代**：判 RunPod 自有权重道（G1–G10）。主人令 2026-10-24「这个要花钱我们不需要直接清理了」
   ⇒ 车道清掉，闸永远红，红的原因已经不是"坏了"而是"不做了"。
2. **二代**：改判免费道（Cloudflare Workers AI / agnes）。主人令 2026-10-24
   「**不用云端驱动，按需激活使用本地算力**」⇒ 桥的车道链默认只剩 `selfhost`，
   云端两条从链里摘掉 ⇒ 再去量它们又变成"量不在役的东西"。
3. **三代（本版）**：判**本地道**，而且**不要求任何进程在跑** —— 按需激活的设计就是
   「APP 没开时不该有进程」，拿"桥必须在跑"当闸，等于逼着系统常驻，与设计直接相反。

## 判据（三条静态 + 一条条件制，全部机检）

N1 权重件在役：GGUF 在盘 · 头 4 字节 `GGUF` · 体积 ≥ 1GB
N2 壳的契约：`holo_pet_w3/shell/main.cjs` 四处接线都在（现拉服务 / 强制 selfhost / 权重件名 / 解释器变量）
N3 **不用云端不变量**：把桥按壳的方式导入（`GBT_ENABLE_SELFHOST_LANE=1`、**不设** `GBT_ALLOW_CLOUD`）
   ⇒ `LANE_CHAIN` 必须**恰好** `['selfhost']`、`FALLBACK_ORDER` 必须**为空**。
   🔴 这条是主人令「不用云端」的**机械闸**：谁把云端车道加回来，这里当场红，不靠人记。
N4 真出话（**条件制**）：桥在 8791 且权重服务在 8792 ⇒ 真发一句、判 `weights_ours=True`；
   两个都没起 ⇒ 判 `不适用（按需激活＝APP 没开）`，**这是设计，不是失败**；
   桥起了但权重服务没起 ⇒ 红（半开状态才是坏）。

退出码：全绿 0 / 有红 1；`--json` 给机读。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import socket
import sys
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
GGUF = ROOT / "state" / "weights" / "gbt-v8-v82-q5_0.gguf"
SHELL = ROOT / "holo_pet_w3" / "shell" / "main.cjs"
SERVER = ROOT / "tools" / "model-bridge" / "server.py"
BRIDGE = "http://127.0.0.1:8791"
PROMPT = "只回两个字：在线"


def _port_up(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.8)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def n1_weight() -> dict:
    if not GGUF.is_file():
        return {"id": "N1", "name": "权重件在役", "ok": False, "reading": "缺：%s" % GGUF.name}
    size = GGUF.stat().st_size
    try:
        magic = GGUF.open("rb").read(4)
    except OSError as e:
        return {"id": "N1", "name": "权重件在役", "ok": False,
                "reading": "读不到：%s" % type(e).__name__}
    ok = magic == b"GGUF" and size >= 1 << 30
    return {"id": "N1", "name": "权重件在役", "ok": ok,
            "reading": "%s · %.2f GB · magic=%r" % (GGUF.name, size / 1024 ** 3,
                                                    magic.decode("ascii", "replace"))}


def n2_shell_contract() -> dict:
    if not SHELL.is_file():
        return {"id": "N2", "name": "壳的契约", "ok": False, "reading": "缺 main.cjs"}
    txt = SHELL.read_text(encoding="utf-8", errors="replace")
 # 2026-10-25 口径翻正（留痕 · 原口径 / 为什么翻 / 现口径）：
    #   原口径：四处接线全在**壳**里（现拉服务 / 强制 selfhost / 权重件名 / 解释器变量）。
    #   为什么翻：`ensureLocalLLM()` 被退役 —— 它**半年没人调用**、且 spawn 时不带
    #     `--idle-exit`（接上就会常驻 4.88GB，违背「不激活不占内存」）。现在**权重只由桥按需拉起**
    #     ⇒ 该懂「权重件名 / 解释器」的是**桥**，不是壳。旧口径继续咬壳 = 咬一个已经不存在的职责。
    #   现口径：按职责分账 —— 壳管「起桥 + 强制 selfhost + 把 selfhost 指到本机」，
    #     桥管「权重件名 + 解释器 + 按需拉起」。两侧缺任一项仍红（牙没掉）。
    shell_need = [("ensureModelBridge", "壳·现拉桥"),
                  ('GBT_ENABLE_SELFHOST_LANE: "1"', "壳·强制 selfhost"),
                  ("GBT_OURS_BASE_URL", "壳·把 selfhost 指到本机")]
    if not SERVER.is_file():
        return {"id": "N2", "name": "壳的契约", "ok": False, "reading": "缺 server.py"}
    srv_txt = SERVER.read_text(encoding="utf-8", errors="replace")
    srv_need = [("_OURS_WEIGHTS", "桥·权重件名"),
                ("GBT_LLM_PY", "桥·解释器变量"),
                ("--idle-exit", "桥·闲置自退（按需激活的一半）")]
    missing = ["%s（%s）" % (d, "缺失") for needle, d in shell_need if needle not in txt]
    missing += ["%s（%s）" % (d, "缺失") for needle, d in srv_need if needle not in srv_txt]
    return {"id": "N2", "name": "壳的契约", "ok": not missing,
            "reading": "壳三项 + 桥三项 接线齐" if not missing else "缺：%s" % "、".join(missing)}


def n3_local_only() -> dict:
    """主人令「不用云端」的机械闸：把桥按壳的方式导入，看车道链。"""
    if not SERVER.is_file():
        return {"id": "N3", "name": "不用云端不变量", "ok": False, "reading": "缺 server.py"}
    old = {k: os.environ.get(k) for k in ("GBT_ENABLE_SELFHOST_LANE", "GBT_ALLOW_CLOUD",
                                          "GBT_ENABLE_GPU")}
    try:
        os.environ["GBT_ENABLE_SELFHOST_LANE"] = "1"   # 壳起桥时就是这么设的
        os.environ.pop("GBT_ALLOW_CLOUD", None)        # 默认不放开云端
        os.environ.pop("GBT_ENABLE_GPU", None)
        spec = importlib.util.spec_from_file_location("_gbt_srv_lane", SERVER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        chain = list(getattr(mod, "LANE_CHAIN", []))
        fb = list(getattr(mod, "FALLBACK_ORDER", []))
    except Exception as e:                                    # noqa: BLE001
        return {"id": "N3", "name": "不用云端不变量", "ok": False,
                "reading": "导入失败：%s: %s" % (type(e).__name__, str(e)[:70])}
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    ok = chain == ["selfhost"] and fb == []
    return {"id": "N3", "name": "不用云端不变量", "ok": ok,
            "reading": "LANE_CHAIN=%s · FALLBACK_ORDER=%s" % (chain, fb)}


def n4_live() -> dict:
    """条件制：APP 没开就「不适用」，半开才红。"""
    bridge = _port_up(8791)
    ours = _port_up(8792)
    if not bridge and not ours:
        return {"id": "N4", "name": "真出话", "ok": True, "na": True,
                "reading": "不适用（按需激活＝APP 没开：8791/8792 都没起，这是设计）"}
    if bridge and not ours:
 # 2026-10-25 口径翻正（留痕 · 原口径 / 为什么翻 / 现口径）：
        #   原口径：桥在、权重不在 ⇒ 一律判「半开＝坏」。
        #   为什么翻：本轮给桥加了 POST /v1/unload（主人令「没激活的静默不占内存」），
        #     「卸载后闲置」成了**正常的休息态**，端口读数与「半开」一模一样 ⇒
        #     旧口径会把正确状态当坏（闸自己变成假红源）。
        #   现口径：问桥要 selfhost.state —— unloaded（卸载过）⇒ 判「按需闲置（对）」；
        #     其它（idle 且从没成功过 / 探测失败）⇒ 仍判半开红。
        try:
            with urllib.request.urlopen(BRIDGE + "/health", timeout=10) as r:
                h = json.loads(r.read().decode("utf-8", "replace"))
            sh = h.get("selfhost") or {}
            if sh.get("state") == "unloaded" and sh.get("last_unload"):
                lu = sh["last_unload"]
                return {"id": "N4", "name": "真出话", "ok": True,
                        "reading": "按需闲置（桥在 · 权重已卸载 %s · 上次 killed=%s）—— 这是设计"
                                   % (lu.get("at"), lu.get("killed_pids"))}
            return {"id": "N4", "name": "真出话", "ok": False,
                    "reading": "桥起了但权重服务没起，且桥未宣告卸载（state=%r）⇒ 半开，这才是坏"
                               % (sh.get("state"),)}
        except Exception as e:
            return {"id": "N4", "name": "真出话", "ok": False,
                    "reading": "桥起了但权重服务没起，且问不到桥的状态（%s）⇒ 按半开处理"
                               % (type(e).__name__,)}
    try:
        body = json.dumps({"messages": [{"role": "user", "content": PROMPT}],
                           "max_tokens": 16, "temperature": 0}).encode()
        req = urllib.request.Request(BRIDGE + "/v1/chat/completions", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read().decode("utf-8", "replace")
            dt = round(time.perf_counter() - t0, 2)
    except Exception as e:                                    # noqa: BLE001
        return {"id": "N4", "name": "真出话", "ok": False,
                "reading": "%s: %s" % (type(e).__name__, str(e)[:80])}
    d = json.loads(raw)
    gbt = d.get("gbt") or {}
    text = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ok = gbt.get("weights_ours") is True and bool(str(text).strip())
    return {"id": "N4", "name": "真出话", "ok": ok,
            "reading": "%.2fs · lane=%s · weights_ours=%s · text=%r"
                       % (dt, gbt.get("lane"), gbt.get("weights_ours"), str(text)[:24])}


def run() -> dict:
    checks = [n1_weight(), n2_shell_contract(), n3_local_only(), n4_live()]
    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "口径": ("现役车道 = 本地 selfhost（按需激活）。云端两道（RunPod 自有权重 / cfai·agnes）"
                     "已按主人令退役；N3 是会咬人的机械不变量，谁加回云端这里当场红。")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = run()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for c in r["checks"]:
            mark = "✅" if c["ok"] else "🔴"
            if c["ok"] and c.get("na"):
                mark = "✅"
            print("%s %-18s %s" % (mark, c["name"], c["reading"]))
        print("结论：%s" % ("本地道在役 · 全绿" if r["ok"] else "有红"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
