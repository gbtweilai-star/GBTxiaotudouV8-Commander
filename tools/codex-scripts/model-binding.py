# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 自家模型「全家文件」双向绑定 + 漂移告警（主人令 2026-10-14）。

## 为什么有它
主人令：**「把大模型的所有文件使用触手双向绑定，必须加速她」**。
2026-10-14 现读踩到的坑就是「文件与在跑的那份不一致」：
  · 仓里的 `chat_template.jinja` 工具示范写成双花括号 ⇒ 模型照抄 ⇒ 解析器吞掉工具调用；
  · 而**在跑的那份**在 RunPod 卷上 + 被 `CUSTOM_CHAT_TEMPLATE` 覆盖 ⇒ 两边不是同一份，肉眼看不出来。
⇒ 本件把「模型全家」逐件登记 + 逐件对账，**任何一处漂移当场变红**。

## 双向绑定（与 `触手双向绑定架构` 同口径）
  · **A 向（框架 → 文件/部署）**：把模型全家（权重组 / tokenizer / chat template / LoRA / 训练语料 /
    生成与部署脚本 / RunPod 模板 env / 代理车道 / Codex 侧目录与 provider）逐件登记：落点 + sha256 前 16 + 用途。
  · **B 向（文件/部署 → 框架）**：把**在跑的那份**读回来（RunPod 模板 env、代理车道表、Codex catalog），
    与仓内文件**逐字节对账**，读数回写 `state/model-binding.json`，有漂移非零退出。

## 判据（逐条可机检）
  B1 chat_template 漂移：仓内 merged/chat_template.jinja  ↔  RunPod `CUSTOM_CHAT_TEMPLATE` 逐字节一致
  B2 模板坏示范     ：模板里不得残留双花括号的工具示范（那个 bug 的指纹）
  B3 模型名一致     ：RunPod `OPENAI_SERVED_MODEL_NAME_OVERRIDE` == 代理车道表里的自家 id
  B4 解析器口径     ：`TOOL_CALL_PARSER` 必须是 hermes（Qwen2.5 口径；qwen3_coder 是 27B 口径，用错会吞输出）
  B5 上下文对齐     ：RunPod `MAX_MODEL_LEN` == Codex catalog 里该模型的 context_window
  B6 车道在役       ：代理 `/v1/models` 里能看到自家 id
  B7 工件清单       ：权重组/LoRA/语料/脚本/模板 逐件在册且有哈希（缺件如实红，不编）

用法：
    py -3.14 tools/codex-scripts/model-binding.py            # 登记 + 对账 + 回写读数
    py -3.14 tools/codex-scripts/model-binding.py --list     # 只列在册文件

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "model-binding.json"
HOST, PORT = "127.0.0.1", int(os.environ.get("GBT_CLIPROXY_PORT", "8317"))
MODEL = os.environ.get("GBT_ACCEPT_MODEL", "gbt-potato-v8")
ENDPOINT_ID = os.environ.get("GBT_POTATO_ENDPOINT_ID", "qnnqf9w8xcefj8")
CODEX_CATALOG = Path.home() / ".codex" / "models.json"
ROW: list = []

# A 向：模型全家（现读路径；缺件如实红）
PARTS = [
    ("权重组", "outputs/gbt_v8_merged"),
    ("LoRA 适配器", ".scratch/gbt_v8_lora"),
    ("训练语料", ".scratch/self_knowledge_v24.jsonl"),
    ("语料生成器", ".scratch/_gen_v24.py"),
    ("合并/部署脚本", ".scratch/_pod_deploy_v24_clean.py"),
    ("本地代理配置", "deploy/cliproxy/config.gbt.example.yaml"),
]


def _user_env(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if v or os.name != "nt":
        return v
    try:
        import winreg                                          # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return (winreg.QueryValueEx(k, name)[0] or "").strip()
    except Exception:                                          # noqa: BLE001
        return ""


def _sha(p: Path) -> str:
    if p.is_file():
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    if p.is_dir():
        h = hashlib.sha256()
        for f in sorted(p.rglob("*")):
            if f.is_file():
                h.update(str(f.relative_to(p)).encode("utf-8"))
 # 实测坑（2026-10-14）：4GB 的 safetensors 用 read_bytes() 会 MemoryError
                #    ⇒ 必须**流式**只取头 1MB（指纹用途够用，且不再把整份权重读进内存）。
                with f.open("rb") as fh:
                    h.update(fh.read(1 << 20))
        return h.hexdigest()[:16]
    return ""


def _lane_ids() -> list:
    key = _user_env("GBT_CLIPROXY_KEY") or ""
    if not key:
        try:
            key = (Path(os.environ.get("APPDATA", "")) / "gbt-cliproxy" / "client-key.txt").read_text(encoding="utf-8").strip()
        except OSError:
            return []
    req = urllib.request.Request("http://%s:%d/v1/models" % (HOST, PORT),
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:      # noqa: S310
            return [m.get("id") for m in (json.loads(r.read().decode("utf-8", "replace")).get("data") or [])]
    except Exception:                                          # noqa: BLE001
        return []


def _remote_env() -> dict:
    key = _user_env("GBT_POTATO_API_KEY")
    if not key:
        return {}
 # 实测坑（2026-10-14）：不带 UA 的 python-urllib 请求会被边缘拒（异常被 except 吞掉 ⇒ 读数全 None）。
    req = urllib.request.Request("https://rest.runpod.io/v1/templates/e4iwgiqa7t",
                                 headers={"Authorization": "Bearer " + key,
                                          "User-Agent": "gbt-model-binding/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:     # noqa: S310
            return json.loads(r.read().decode("utf-8", "replace")).get("env") or {}
    except Exception:                                          # noqa: BLE001
        return {}


def _catalog() -> dict:
    try:
        for m in json.loads(CODEX_CATALOG.read_text(encoding="utf-8"))["models"]:
            if m.get("slug") == MODEL:
                return m
    except Exception:                                          # noqa: BLE001
        pass
    return {}


def j(cid: str, name: str, ok: bool, detail: str) -> None:
    ROW.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})
    print("%s %-3s %-16s %s" % ("PASS" if ok else "FAIL", cid, name, detail))


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="模型全家文件双向绑定 + 漂移告警")
    ap.add_argument("--list", action="store_true", help="只列在册文件")
    a = ap.parse_args(argv)

    print("=== 模型全家绑定 · model=%s · 入口=%s ===" % (MODEL, HOST + ":" + str(PORT)))
    print("\n-- A 向：框架 → 文件（登记）--")
    inventory = []
    for label, rel in PARTS:
        p = ROOT / rel
        exists = p.exists()
        h = _sha(p) if exists else ""
        n = (len(list(p.rglob("*"))) if p.is_dir() else 1) if exists else 0
        inventory.append({"part": label, "path": rel, "exists": exists, "sha16": h, "files": n})
        print("   %-14s %-42s %s  %s" % (label, rel, "在" if exists else "缺", h or "-"))
        if a.list:
            continue
    if not a.list:
        env = _remote_env()
        catalog = _catalog()
        lanes = _lane_ids()
        local_tpl = ROOT / "outputs" / "gbt_v8_merged" / "chat_template.jinja"
        lt = local_tpl.read_text(encoding="utf-8") if local_tpl.is_file() else ""
        rt = str(env.get("CUSTOM_CHAT_TEMPLATE") or "")
        print("\n-- B 向：在跑的那份 → 框架（对账）--")
        j("B1", "模板无漂移", bool(lt) and bool(rt) and lt.strip() == rt.strip(),
          "仓内 %d 字符 · 在跑 %d 字符 · 一致=%s" % (len(lt), len(rt), lt.strip() == rt.strip()))
        j("B2", "无坏示范", '{{"name"' not in lt and '{{"name"' not in rt,
          "双花括号示范残留：仓内=%s 在跑=%s" % ('{{"name"' in lt, '{{"name"' in rt))
        j("B3", "模型名一致", str(env.get("OPENAI_SERVED_MODEL_NAME_OVERRIDE") or "") == MODEL and MODEL in lanes,
          "模板=%s · 车道=%s（%s）" % (env.get("OPENAI_SERVED_MODEL_NAME_OVERRIDE"), lanes, MODEL in lanes))
        j("B4", "解析器口径", str(env.get("TOOL_CALL_PARSER") or "") == "hermes",
          "TOOL_CALL_PARSER=%s（Qwen2.5 口径应为 hermes）" % env.get("TOOL_CALL_PARSER"))
 # 2026-10-14 改口径（真读数咬出来的）：**不是"必须相等"**。
        #   实测病案：catalog 与服务端都设 32768 ⇒ Codex 按 32768 估、真实 token 略多 ⇒
        #   涨到 32769 被 vLLM 顶回 400（账本里那批 FAILED 就是它）。
        #   ⇒ 正确口径：**服务端上限 ≥ catalog 上限，且至少留 2k 头寸**（Codex 提前压缩）。
        _srv = int(env.get("MAX_MODEL_LEN") or 0)
        _cat = int(catalog.get("context_window") or 0)
        j("B5", "上下文留头寸", _srv >= _cat + 2048,
          "服务端 MAX_MODEL_LEN=%s ≥ catalog %s + 2048 头寸 ⇒ %s（实测过 32769 顶爆）"
          % (_srv, _cat, _srv >= _cat + 2048))
        j("B6", "车道在役", MODEL in lanes, "车道表=%s" % lanes)
        j("B7", "工件齐备", all(p["exists"] for p in inventory),
          "缺件=%s" % ([p["part"] for p in inventory if not p["exists"]] or "无"))
        bad = [r for r in ROW if not r["ok"]]
        doc = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "model": MODEL,
               "direction_a": inventory, "direction_b": ROW,
               "remote_env_keys": sorted(env.keys())}
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n判据 PASS %d · FAIL %d · 读数落 %s" % (len(ROW) - len(bad), len(bad), STATE))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
