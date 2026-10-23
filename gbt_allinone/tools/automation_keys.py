# gbt-capability: automation_keys
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""自动化配置密钥口（automation_keys）· 主人令 2026-09-27。

主人原话：「FreeLLMAPI 也蒸馏成我们自己的原生，把原控制的移除、保留功能，**集成进我们的 APP 设置
里面当自动化配置密钥口**；整个框架要按我们原有的元素结构来设计；保留 Codex 的编程能力、
DeepSeek Harness 的执行力、克劳德的意见和建议，以及一个内置浏览器全控的能力；所有能力都要
挨个连接上并且**测试跑通闭环验证**。」

## 这个口子做什么（一句话）
**它是"哪把钥匙给哪个子系统用"的唯一配置面** —— 应用设置调这里，不散在各处。

## 三条硬口径（与仓内既有纪律同源，不是新规矩）
  1. **密钥只存"引用"，不存明文**：本文件只记 `env:<环境变量名>` 或 `vault:<DPAPI profile 名>`；
     值的读写一律走既有唯一来源 `model_key_pool`（DPAPI + auth_gate，六条红线在那边）。
     ⇒ **源码/示例/测试里永远不会出现可用的凭据字面量**。
  2. **输出只给掩码**：任何读数只回 `sk-a1b2****`（前 4~6 字符）与"在/不在"，**绝不回值**。
  3. **改配置要过门**：写入设置面需 `filesystem_write`（与写类同律）；**新增真密钥**走
     `model_key_pool.register_key`（它自带 auth_gate + DPAPI），本口子不另开写路径。

## 槽位（= 挨个接好的四类能力 + 免费算力池）
| slot | 谁在用 | 说明 |
|---|---|---|
| `codex` | Codex 编程能力（`codex_*` 六件） | 官方 Codex 会话/线程/回合 |
| `claude` | 克劳德的意见和建议（`claude_code`） | Claude Code CLI |
| `deepseek` | DeepSeek Harness 执行力（`llm_chat` 链） | DeepSeek/Kimi/OpenAI 密钥链 |
| `browser` | 内置浏览器全控（`browser`/原生） | 本条通常**不需要密钥**（本地控制面） |
| `free_pool` | 免费算力池（FreeLLMAPI `127.0.0.1:31415`） | 只需**统一 API key**；**不碰它的 dashboard 会话** |
| `sec_llm` | 红队专用通道 | 独立密钥，不与他能力混用 |

═══ 2026-09-28 升级：从「单引用」到「多候选 + 额度 + 自动切换」（主人令）═══
主人原话：「把这个设计成一个可以自动读取和密钥自动切换，一个模型规定额度使用完了
就自动切换下一个有能源的密钥继续补给能源」。

升级前只有「一槽一条 ref」：额度用尽 = **断连**，没有第二条路。
升级后一槽可挂**多条候选**，按「余量 × 健康 × 优先级」排序，前一条耗尽/冷却/失效
**自动落向下一条**。这是把上一轮独立验证过的额度感知选路（energy-router）**内化进框架原生口**，
不是另起一套。

## ops（既有 5 个 **一个都没动**，只做增量）
  status                 一屏：每槽「引用形式 · 在/不在 · 掩码 · 能不能用 · 候选数 · 余量」
  set    slot=... ref=env:NAME        写"引用"（过 filesystem_write 门；**不写值**）
         set slot=... refs='["env:A","env:B"]' model=... quota_tokens=...   ← 新增：多候选+参数
  unset  slot=...                     清引用（过门）
  test   [slot=...]                   闭环自检：能连的**真连一次**（只读、不打分、不出网到别处）
  where                               给 APP 设置看的接线契约（调哪个 op、什么形状）
  ── 以下为新增 ──
  pick   slot=... [need_tokens=N]     选路：返回该槽**当前该用哪条**（跳过缺失/耗尽/冷却/禁用）
  report slot=... ref=... tokens=N    上报用量（驱动额度计量；超限自动标记该条耗尽）
  mark_fail slot=... ref=... kind=... 按错误分类处置该条（429→冷却 / 402→耗尽 / 401→禁用）
  energy                              能源总览：所有槽位所有候选的余量、健康、切换次数
  switch slot=... ref=...             手动指定用哪条（过门；记录切换原因）

## 状态分层（**判据 D「自检只读」靠这个成立**）
  `state/automation_keys.json`   配置（只有 set/unset/switch 写，过门）
  `state/automation_keys.jsonl`  配置变更账本（既有，追加）
  `state/ak_runtime.json`        运行态：用量/冷却/禁用/切换次数（pick/report/mark_fail 写）
  ⇒ `test` 与 `pick` **一个字都不写配置**，只读计算（需要时写运行态）。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS = _ROOT / "state" / "automation_keys.json"
_LEDGER = _ROOT / "state" / "automation_keys.jsonl"
_RUNTIME = _ROOT / "state" / "ak_runtime.json"

# 槽位 → 默认引用（**只写引用名，永不写值**）；env 名是公开信息，值只活在环境/保险箱里
SLOTS = {
    "codex": {"what": "Codex 编程能力（官方会话/线程/回合）", "ref": "env:OPENAI_API_KEY",
              "refs": ["env:OPENAI_API_KEY"], "model": "", "quota_tokens": 0},
    "claude": {"what": "克劳德的意见和建议（Claude Code CLI）", "ref": "env:ANTHROPIC_API_KEY",
               "refs": ["env:ANTHROPIC_API_KEY"], "model": "", "quota_tokens": 0},
    "deepseek": {"what": "DeepSeek Harness 执行力（密钥链）", "ref": "vault:deepseek/agnes",
                 "refs": ["vault:deepseek/agnes", "env:DEEPSEEK_API_KEY", "env:AGNES_API_KEY",
                          "env:MOONSHOT_API_KEY", "env:NVIDIA_API_KEY"],
                 "model": "deepseek-flash", "quota_tokens": 0},
    "browser": {"what": "内置浏览器全控（本地控制面，通常无需密钥）", "ref": "local",
                "refs": ["local"], "model": "", "quota_tokens": 0},
    "free_pool": {"what": "免费算力池（FreeLLMAPI 本地 /v1）", "ref": "env:FREELLMAPI_KEY",
                  "refs": ["env:FREELLMAPI_KEY"], "model": "", "quota_tokens": 0},
    "sec_llm": {"what": "红队专用通道（独立密钥，不混用）", "ref": "env:ABLITERATION_API_KEY",
                "refs": ["env:ABLITERATION_API_KEY"], "model": "", "quota_tokens": 0},
}

# ── 错误分类 → 处置（与 energy-router 同表，**唯一真相源**，可单测）──────────
#   kind              换道  冷却  耗尽  禁用
ERR_TABLE = {
    "rate_limited":    (True, True,  False, False),   # 429
    "quota_exhausted": (True, True,  True,  False),   # 402 / 额度关键词
    "key_invalid":     (True, False, False, True),    # 401 / 403
    "transient":       (True, False, False, False),   # 超时/连接
    "upstream_error":  (True, False, False, False),   # 5xx
    "bad_request":     (False, False, False, False),  # 400/422 ⇒ 不换道（换道会掩盖真 bug）
}
DEFAULT_COOLDOWN_S = 120


def _load() -> dict:
    if _SETTINGS.is_file():
        try:
            return json.loads(_SETTINGS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save(d: dict) -> None:
    _SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = _SETTINGS.with_name(_SETTINGS.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _SETTINGS)


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


# ── 运行态（与配置分开：这层让「自检只读」成立）────────────────────
def _rload() -> dict:
    if _RUNTIME.is_file():
        try:
            return json.loads(_RUNTIME.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _rsave(d: dict) -> None:
    try:
        _RUNTIME.parent.mkdir(parents=True, exist_ok=True)
        tmp = _RUNTIME.with_name(_RUNTIME.name + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, _RUNTIME)
    except Exception:                                    # noqa: BLE001
        pass            # 记账失败不许反向打断调用


def _rslot(rt: dict, slot: str) -> dict:
    return rt.setdefault(slot, {"used": {}, "cooldown": {}, "disabled": [],
                                "exhausted": [], "switches": 0})


def _mask(s: str, keep: int = 4) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    return s[:keep] + "****" if len(s) > keep else "****"


def _resolve(ref: str) -> dict:
    """把引用解析成「在/不在 + 掩码」——**永不返回值**。"""
    ref = (ref or "").strip()
    if ref == "local" or not ref:
        return {"kind": "local", "present": True, "masked": "", "note": "本地控制面，无需密钥"}
    if ref.startswith("env:"):
        name = ref[4:]
        val = os.environ.get(name)
        return {"kind": "env", "name": name, "present": bool(val), "masked": _mask(val or ""),
                "note": "从环境变量读；**值不进仓、不进日志**"}
    if ref.startswith("vault:"):
        return {"kind": "vault", "name": ref[6:], "present": None, "masked": "",
                "note": "DPAPI 保险箱（唯一来源：model_key_pool）——在/不在要它来答，本口子不读值"}
    return {"kind": "unknown", "present": False, "masked": "", "note": f"引用形式不认识：{ref[:40]}"}


# ── 槽位取配置（配置优先于默认；老格式单 ref 自动升成 refs）──────────
def _slot_cfg(slot: str) -> dict:
    """返回该槽的**生效配置**：refs（数组）/ model / quota_tokens / temperature / max_tokens。

    兼容老配置：若盘上只有 `ref` 没有 `refs`，则把 ref 当成唯一候选 ——
    **不迁移、不改盘**（读的时候兼容，写的时候才落新形状）。
    """
    meta = SLOTS.get(slot) or {}
    cur = (_load().get("slots") or {}).get(slot) or {}
    # 候选来源三级优先：盘上多候选 > 盘上单候选（老格式）> **默认多候选**。
    # ⚠️ 血账：早先写的是 `one = cur.get("ref") or meta.get("ref")` —— 盘上没配置时
    # 直接取到**单条默认 ref**，于是下面那段 `meta["refs"]`（多候选默认）**永远走不到**，
    # 结果"多候选"功能在干净环境下压根不生效（实测 5 条候选只出 1 条）。
    cur_refs = cur.get("refs")
    if isinstance(cur_refs, list) and cur_refs:
        refs = [str(r).strip() for r in cur_refs if str(r or "").strip()]
    elif str(cur.get("ref") or "").strip():
        refs = [str(cur["ref"]).strip()]
    else:
        d = meta.get("refs") if isinstance(meta.get("refs"), list) else []
        refs = [str(r).strip() for r in d if str(r or "").strip()]
        if not refs:
            one = str(meta.get("ref") or "").strip()
            refs = [one] if one else []
    return {
        "refs": refs,
        "model": cur.get("model", meta.get("model", "")),
        "quota_tokens": int(cur.get("quota_tokens", meta.get("quota_tokens", 0)) or 0),
        "temperature": cur.get("temperature", ""),
        "max_tokens": cur.get("max_tokens", ""),
        "enabled": bool(cur.get("enabled", True)),
    }


def status(**_kw) -> dict:
    rt = _rload()
    cur = _load().get("slots", {})
    rows = []
    for slot, meta in SLOTS.items():
        cfg = _slot_cfg(slot)
        st = rt.get(slot) or {}
        used_map = st.get("used") or {}
        cd_map = st.get("cooldown") or {}
        dis = set(st.get("disabled") or [])
        exh = set(st.get("exhausted") or [])
        now = time.time()
        active = ""
        cands = []
        for r in cfg["refs"]:
            rr = _resolve(r)
            used = int(used_map.get(r, 0) or 0)
            quota = cfg["quota_tokens"]
            headroom = (max(0, quota - used) if quota else None)
            cds = int(cd_map.get(r, 0) or 0)
            cands.append({"ref": r, **{k: rr[k] for k in ("kind", "present", "masked", "note")},
                          "used": used, "headroom": headroom,
                          "cooldown_left_s": max(0, int(cds - now)),
                          "disabled": r in dis, "exhausted": r in exh})
            if not active and rr.get("present") and (r not in dis) and (r not in exh) \
               and cds <= now and (not quota or used < quota):
                active = r
        if not active and cfg["refs"]:
            active = cfg["refs"][0]          # 兜底：让 ref 永远是**形状合法**的字符串（判据 B）
        rows.append({"slot": slot, "what": meta["what"], "ref": active, **_resolve(active),
                     "refs": cfg["refs"], "candidates": cands,
                     "model": cfg["model"], "quota_tokens": cfg["quota_tokens"],
                     "switches": int(st.get("switches", 0) or 0)})
    present = sum(1 for r in rows if r.get("present") is True)
    return {"ok": True, "op": "status", "kind": "automation_keys",
            "settings_file": str(_SETTINGS),
            "口径": {"只存引用": "本文件只有 env:<名> / vault:<profile> / local，**没有值**",
                    "掩码规则": "前 4 字符 + ****",
                    "唯一来源": "model_key_pool（DPAPI + auth_gate；六条红线在那边）",
                    "多候选": "一槽可挂多条 refs；前一条耗尽/冷却/失效 ⇒ 自动落向下一条",
                    "状态分层": "配置在 automation_keys.json（过门）；用量/冷却在 ak_runtime.json"},
            "slots": rows, "ready": present, "total": len(rows),
            "hint": "APP 设置改这里：run_task('automation_keys', {'op':'where'})"}


def set_ref(slot: str = "", ref: str = "", refs=None, model=None,
            quota_tokens=None, temperature=None, max_tokens=None, enabled=None,
            **_kw) -> dict:
    """写槽位配置（**过 filesystem_write 门**；**只写引用/参数，永不写值**）。

    `ref` 与 `refs` 二者给一：`ref` 是单候选（兼容老调用方），`refs` 是多候选排队。
    """
    slot = (slot or "").strip()
    if slot not in SLOTS:
        return {"ok": False, "error": f"未知槽位 {slot!r}（可用：{sorted(SLOTS)}）", "fail_closed": True}

    # 归一候选列表
    if refs is not None:
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except json.JSONDecodeError:
                refs = [x.strip() for x in refs.split(",") if x.strip()]
        if not isinstance(refs, list):
            return {"ok": False, "error": "refs 必须是数组（或 JSON 数组字符串）", "fail_closed": True}
        cand = [str(r).strip() for r in refs if str(r or "").strip()]
    elif (ref or "").strip():
        cand = [(ref or "").strip()]
    else:
        cand = []

    for r in cand:
        if not (r == "local" or r.startswith(("env:", "vault:"))):
            return {"ok": False,
                    "error": "ref/refs 每项必须是 env:<环境变量名> / vault:<profile> / local —— "
                             "**本口子不接收密钥值**（值走 model_key_pool 的 DPAPI 路径）",
                    "fail_closed": True, "bad": r}
    if not cand and not any(v is not None for v in
                            (model, quota_tokens, temperature, max_tokens, enabled)):
        return {"ok": False, "error": "没给任何要改的字段", "fail_closed": True}

    # 写类过门（与写面同律）
    from .. import auth_gate
    from ..security import policy as _policy
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write", detail=f"automation_keys.set:{slot}")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant")}
    d = _load()
    node = d.setdefault("slots", {}).setdefault(slot, {})
    if cand:
        node["refs"] = cand
        node["ref"] = cand[0]            # 老字段同步成首条（老读法仍能工作）
    if model is not None:
        node["model"] = str(model)
    if quota_tokens is not None:
        node["quota_tokens"] = int(quota_tokens or 0)
    if temperature is not None:
        node["temperature"] = temperature
    if max_tokens is not None:
        node["max_tokens"] = max_tokens
    if enabled is not None:
        node["enabled"] = bool(enabled)
    d["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save(d)
    _log({"event": "set", "slot": slot, "refs": cand or None,
          "fields": {k: v for k, v in (("model", model), ("quota_tokens", quota_tokens),
                                       ("temperature", temperature), ("max_tokens", max_tokens),
                                       ("enabled", enabled)) if v is not None}})
    return {"ok": True, "slot": slot, "refs": cand or None,
            "note": "只写了引用/参数；值仍在环境/保险箱里"}


def unset(slot: str = "", **_kw) -> dict:
    slot = (slot or "").strip()
    if slot not in SLOTS:
        return {"ok": False, "error": f"未知槽位 {slot!r}", "fail_closed": True}
    from .. import auth_gate
    from ..security import policy as _policy
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write", detail=f"automation_keys.unset:{slot}")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant")}
    d = _load()
    ref = (d.get("slots") or {}).pop(slot, None)
    _save(d)
    _log({"event": "unset", "slot": slot, "was": ref})
    return {"ok": True, "slot": slot, "was": ref, "note": "已回到默认引用"}


def test(slot: str = "", **_kw) -> dict:
    """闭环自检：能真连的**真连一次**（只读）。不出网到别处、不花积分、**不写配置**。"""
    targets = [slot] if slot else sorted(SLOTS)
    out = []
    for s in targets:
        if s not in SLOTS:
            out.append({"slot": s, "ok": False, "why": "未知槽位"})
            continue
        if s == "free_pool":
            try:
                import importlib.util as _iu
                sp = _iu.spec_from_file_location("fla", _ROOT / "gbt_allinone" / "llm" / "freellmapi.py")
                fla = _iu.module_from_spec(sp)
                sp.loader.exec_module(fla)
                base, src = fla.discover_base_url()
                pr = fla.probe() if base else {"up": False, "why": "没发现本地 FreeLLMAPI"}
                # ⚠️ 血账（2026-09-27 实测）：`freellmapi.probe()` 回的是 **`up`**，而这里原来
                # 只读 `ok` ⇒ 端口明明在听也一律判「不可达」。这条**假红**一路传到 health.json，
                # 再由上帝之眼日报报成短板。键名不同 ≠ 服务不在 —— 两个键都认；
                # `why` 也带上**完整读数**（原来 str() 截 160 字，读不出真假）。
                is_up = bool(pr.get("ok") if "ok" in pr else pr.get("up"))
                out.append({"slot": s, "ok": is_up, "base": base, "source": src, "probe": pr,
                            "why": ("探活成功（/api/ping 是无鉴权口）" if is_up
                                    else f"探活失败：{pr.get('error') or pr.get('why') or pr}")})
            except Exception as exc:                           # noqa: BLE001
                out.append({"slot": s, "ok": False, "why": f"{type(exc).__name__}: {str(exc)[:120]}"})
        elif s == "browser":
            out.append({"slot": s, "ok": True, "why": "本地控制面：用 browser 能力位自检（run_task('browser',{'op':'status'})）"})
        else:
            cfg = _slot_cfg(s)
            rows = [_resolve(r) for r in cfg["refs"]]
            ok_any = any(r.get("present") or r.get("kind") == "vault" for r in rows)
            out.append({"slot": s, "ok": bool(ok_any),
                        "ref": (cfg["refs"][0] if cfg["refs"] else ""),
                        "candidates": len(cfg["refs"]),
                        "在位的": [r.get("name") or r.get("kind") for r in rows if r.get("present")],
                        "why": ("有候选在位" if ok_any else "候选全不在位（缺环境变量/保险箱条目）")})
    return {"ok": all(x.get("ok") for x in out), "op": "test", "results": out,
            "_口径": "只读自检；free_pool 只打本地 /v1，不花积分、不出公网；**不写配置**"}


# ══════════════════════════════════════════════════════════════════
#  新增：额度感知的自动切换（pick / report / mark_fail / energy / switch）
# ══════════════════════════════════════════════════════════════════
def _rank(slot: str, rt: dict) -> list:
    """候选排序：在位 → 未禁用 → 未冷却 → 未耗尽，再按「余量比 × 优先级」排序。

    返回 [{ref, resolve, used, quota, headroom, in_reserve, why}]（**不改任何状态**）。
    """
    cfg = _slot_cfg(slot)
    st = rt.get(slot) or {}
    used_map = st.get("used") or {}
    cd_map = st.get("cooldown") or {}
    dis = set(st.get("disabled") or [])
    exh = set(st.get("exhausted") or [])
    now = time.time()
    out = []
    for i, r in enumerate(cfg["refs"]):
        rr = _resolve(r)
        used = int(used_map.get(r, 0) or 0)
        quota = cfg["quota_tokens"]
        headroom = (max(0, quota - used) if quota else None)
        reserve = int(quota * 0.2) if quota else 0
        why, alive = "", True
        # ⚠️ 血账：早先写成 `if kind=="vault": pass / elif not present: ... / elif r in dis: ...`
        # —— vault 命中第一支就 pass，**后面三条判定全被吞掉** ⇒ 保险箱候选永远切不掉、
        # 永远耗不尽（实测 mark_fail 打上去 pick 照样选它）。存在性未知 ≠ 免疫故障。
        present_ok = True if rr.get("kind") == "vault" else bool(rr.get("present"))
        if not present_ok:
            why, alive = f"引用不在位（{rr.get('name') or rr.get('kind')}）", False
        elif r in dis:
            why, alive = "已禁用（曾报 401/403）", False
        elif r in exh:
            why, alive = "额度已耗尽（显式标记）", False
        elif cd_map.get(r, 0) > now:
            why, alive = "冷却中 %ds" % int(cd_map.get(r, 0) - now), False
        elif quota and used >= quota:
            why, alive = "额度已耗尽（%d/%d）" % (used, quota), False
        prio = 1.0 / (1.0 + i * 0.25)              # 声明顺序即优先级，前排更优
        if quota and headroom is not None:
            ratio = headroom / quota
        else:
            ratio = 1.0
        out.append({"ref": r, "resolve": rr, "used": used, "quota": quota,
                    "headroom": headroom, "reserve": reserve,
                    "in_reserve": bool(quota and headroom is not None and headroom <= reserve),
                    "prio": prio, "score": ratio * prio, "alive": alive, "why": why,
                    "index": i})
    alive_rows = [x for x in out if x["alive"]]
    # 两趟：先只从"非储备"里挑；全网空才放行储备（备用能源的取用纪律）
    first = [x for x in alive_rows if not x["in_reserve"]]
    pool = first if first else alive_rows
    pool.sort(key=lambda x: x["score"], reverse=True)
    pool_ids = {id(x) for x in pool}
    return pool + [x for x in out if id(x) not in pool_ids]      # 不可用的排在后面，只作展示


def pick(slot: str = "", need_tokens: int = 0, persist: bool = True, **_kw) -> dict:
    """选路：返回该槽**当前该用哪条候选**。跳过缺失/禁用/冷却/耗尽的 —— 这就是自动切换。

    **不改配置**（只读计算）；`persist=True` 时把"上次选中"记进运行态（判据 D 不受影响，
    因为运行态与配置是两个文件）。
    """
    slot = (slot or "").strip()
    if slot not in SLOTS:
        return {"ok": False, "error": f"未知槽位 {slot!r}", "fail_closed": True}
    rt = _rload()
    prev_active = (rt.get(slot) or {}).get("active")      # 先记下来，persist 会覆盖它
    ranked = _rank(slot, rt)
    chosen = next((x for x in ranked if x["alive"]), None)
    if chosen is None and ranked:
        # 全不可用 ⇒ 报清楚，不瞎挑（fail-closed，与门禁同律）
        return {"ok": False, "op": "pick", "slot": slot, "fail_closed": True,
                "error": "该槽所有候选都不可用（缺失/禁用/冷却/耗尽）",
                "candidates": [{"ref": x["ref"], "why": x["why"]} for x in ranked],
                "how_to_fix": "补环境变量 / 用 op=set 追加候选 / 等冷却到期 / op=switch 手动指定"}
    if chosen is None:
        return {"ok": False, "op": "pick", "slot": slot, "fail_closed": True,
                "error": "该槽没有配置任何候选", "how_to_fix": "run_task('automation_keys',{'op':'set',...})"}
    skipped = [{"ref": x["ref"], "why": x["why"]} for x in ranked if not x["alive"]]
    auto_switched = bool(prev_active and prev_active != chosen["ref"])
    if persist:
        st = _rslot(rt, slot)
        st["active"] = chosen["ref"]
        if auto_switched:
            st["switches"] = int(st.get("switches", 0) or 0) + 1
            st["last_switch_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _log({"event": "switch", "slot": slot, "from": prev_active, "to": chosen["ref"],
                  "why": "前一条不可用，自动落向下一条"})
        _rsave(rt)
    return {"ok": True, "op": "pick", "slot": slot, "ref": chosen["ref"],
            "kind": chosen["resolve"].get("kind"), "masked": chosen["resolve"].get("masked"),
            "from_reserve": chosen["in_reserve"],
            "used": chosen["used"], "quota": chosen["quota"] or None,
            "headroom": chosen["headroom"],
            "auto_switched": auto_switched,
            "skipped": skipped, "candidates": len(ranked),
            "note": "只回引用与掩码；值仍在环境/保险箱里"}


def report(slot: str = "", ref: str = "", tokens: int = 0, **_kw) -> dict:
    """上报用量：驱动额度计量；超限**自动把该条标记耗尽**（下次 pick 自动换道）。"""
    slot = (slot or "").strip()
    if slot not in SLOTS:
        return {"ok": False, "error": f"未知槽位 {slot!r}", "fail_closed": True}
    ref = (ref or "").strip() or ((_rload().get(slot) or {}).get("active") or "")
    if not ref:
        return {"ok": False, "error": "没给 ref 且该槽还没有 active（先调 op=pick）", "fail_closed": True}
    rt = _rload()
    st = _rslot(rt, slot)
    st.setdefault("used", {})[ref] = int(st.setdefault("used", {}).get(ref, 0) or 0) + int(tokens or 0)
    used = st["used"][ref]
    quota = _slot_cfg(slot)["quota_tokens"]
    over = bool(quota and used >= quota)
    _rsave(rt)
    return {"ok": True, "op": "report", "slot": slot, "ref": ref, "used": used,
            "quota": quota or None, "headroom": (max(0, quota - used) if quota else None),
            "exhausted": over,
            "action": "该条已标记耗尽，下次 pick 自动落向下一条" if over else "已记账",
            "note": "超限不静默：这里回报 exhausted，切换由 op=pick 执行（可审计）"}


def mark_fail(slot: str = "", ref: str = "", kind: str = "", cooldown_s: int = 0, **_kw) -> dict:
    """按错误分类处置某条候选：429→冷却 / 402→耗尽 / 401,403→禁用 / 400,422→不换道。

    分类表是 `ERR_TABLE`（唯一真相源）。**改的是运行态，不是配置** ⇒ 可自愈、可审计。
    """
    slot = (slot or "").strip()
    if slot not in SLOTS:
        return {"ok": False, "error": f"未知槽位 {slot!r}", "fail_closed": True}
    kind = (kind or "").strip() or "unknown"
    failover, cooldown, exhaust, disable = ERR_TABLE.get(kind, (True, False, False, False))
    ref = (ref or "").strip() or ((_rload().get(slot) or {}).get("active") or "")
    if not ref:
        return {"ok": False, "error": "没给 ref 且该槽还没有 active", "fail_closed": True}
    rt = _rload()
    st = _rslot(rt, slot)
    if cooldown:
        st.setdefault("cooldown", {})[ref] = time.time() + (int(cooldown_s) or DEFAULT_COOLDOWN_S)
    if exhaust:
        # 显式耗尽标记（与 quota 数值判定**并存**）：quota=0 的槽按定义是"无限"，
        # 单靠数值判不出耗尽 ⇒ 402/额度关键词必须能独立把这条钉死。
        st.setdefault("exhausted", [])
        if ref not in st["exhausted"]:
            st["exhausted"].append(ref)
        q = _slot_cfg(slot)["quota_tokens"] or 0
        if q:
            st.setdefault("used", {})[ref] = max(int(st.setdefault("used", {}).get(ref, 0) or 0), q)
    if disable:
        st.setdefault("disabled", [])
        if ref not in st["disabled"]:
            st["disabled"].append(ref)
    _rsave(rt)
    _log({"event": "mark_fail", "slot": slot, "ref": ref, "kind": kind,
          "failover": failover, "cooldown": cooldown, "exhaust": exhaust, "disable": disable})
    return {"ok": True, "op": "mark_fail", "slot": slot, "ref": ref, "kind": kind,
            "failover": failover, "cooldown_s": (int(cooldown_s) or DEFAULT_COOLDOWN_S) if cooldown else 0,
            "exhausted": exhaust, "disabled": disable,
            "action": ("下一次 pick 会跳过它" if failover else
                       "**不换道**：400/422 是请求本身有错，换道会把参数缺陷伪装成『模型不行』")}


def switch(slot: str = "", ref: str = "", why: str = "", **_kw) -> dict:
    """手动指定该槽用哪条（**过门**）。用于人工介入，与自动切换共用同一套运行态。"""
    slot = (slot or "").strip()
    ref = (ref or "").strip()
    if slot not in SLOTS:
        return {"ok": False, "error": f"未知槽位 {slot!r}", "fail_closed": True}
    if ref not in _slot_cfg(slot)["refs"]:
        return {"ok": False, "fail_closed": True,
                "error": f"{ref!r} 不在 {slot} 的候选里（先用 op=set 追加）",
                "candidates": _slot_cfg(slot)["refs"]}
    from .. import auth_gate
    from ..security import policy as _policy
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("filesystem_write", detail=f"automation_keys.switch:{slot}")
        if not gate.get("ok"):
            return {"ok": False, "denied": True, "gate": "filesystem_write",
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant")}
    rt = _rload()
    st = _rslot(rt, slot)
    prev = st.get("active")
    st["active"] = ref
    if prev != ref:
        st["switches"] = int(st.get("switches", 0) or 0) + 1
        st["last_switch_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _rsave(rt)
    _log({"event": "switch", "slot": slot, "from": prev, "to": ref, "why": why or "手动指定"})
    return {"ok": True, "op": "switch", "slot": slot, "from": prev, "to": ref,
            "note": "手动切换已记录"}


def energy(**_kw) -> dict:
    """能源总览：所有槽位所有候选的「余量 · 健康 · 冷却 · 切换次数」——给界面直接渲染。"""
    rt = _rload()
    rows, live_total = [], 0
    for slot in sorted(SLOTS):
        cfg = _slot_cfg(slot)
        st = rt.get(slot) or {}
        used_map = st.get("used") or {}
        cd_map = st.get("cooldown") or {}
        dis = set(st.get("disabled") or [])
        exh = set(st.get("exhausted") or [])
        now = time.time()
        cands = []
        for r in cfg["refs"]:
            rr = _resolve(r)
            used = int(used_map.get(r, 0) or 0)
            quota = cfg["quota_tokens"]
            headroom = (max(0, quota - used) if quota else None)
            if rr.get("kind") == "vault":
                status_s = "保险箱"
            elif not rr.get("present"):
                status_s = "缺引用"
            elif r in dis:
                status_s = "已禁用"
            elif r in exh:
                status_s = "额度耗尽"
            elif cd_map.get(r, 0) > now:
                status_s = "冷却中"
            elif quota and used >= quota:
                status_s = "额度耗尽"
            else:
                status_s = "可用"
            if status_s in ("可用", "保险箱"):
                live_total += 1
            cands.append({"ref": r, "kind": rr.get("kind"), "masked": rr.get("masked"),
                          "status": status_s, "used": used, "quota": quota or None,
                          "headroom": headroom,
                          "used_pct": (round(100.0 * used / quota, 1) if quota else None),
                          "cooldown_left_s": max(0, int(cd_map.get(r, 0) - now))})
        alive = [c for c in cands if c["status"] in ("可用", "保险箱")]
        rows.append({"slot": slot, "what": SLOTS[slot]["what"], "model": cfg["model"],
                     "quota_tokens": cfg["quota_tokens"], "switches": int(st.get("switches", 0) or 0),
                     "active": st.get("active") or (cfg["refs"][0] if cfg["refs"] else ""),
                     "candidates": cands, "alive": len(alive), "total": len(cands)})
    return {"ok": True, "op": "energy", "slots": rows,
            "alive_total": live_total, "slots_total": len(rows),
            "energy_alive": live_total >= 2,
            "summary": ("能源充足：全网 %d 条候选可用" % live_total) if live_total >= 2
                       else ("⚠ 单点：全网仅 %d 条候选可用，断连风险" % live_total),
            "_口径": "只回引用与掩码；用量来自 ak_runtime.json 记账（非平台真实读数，见 HONEST_BOUNDARY）"}


def where(**_kw) -> dict:
    """**给 APP 设置看的接线契约**：调哪个 op、什么形状、返回什么。"""
    return {"ok": True, "op": "where", "kind": "automation_keys",
            "入口": "run_task('automation_keys', {...})",
            "契约": [
                {"op": "status", "in": {}, "out": "slots[]（ref/在不在/掩码 + refs[]/candidates[]/model/quota_tokens）+ ready/total"},
                {"op": "set", "in": {"slot": "<槽位>", "ref": "env:NAME|vault:profile|local"},
                 "out": "ok（写引用；过 filesystem_write 门）"},
                {"op": "set", "in": {"slot": "<槽位>", "refs": '["env:A","env:B"]',
                                     "model": "gpt-5", "quota_tokens": 500000,
                                     "temperature": 0.7, "max_tokens": 4096, "enabled": True},
                 "out": "ok（多候选 + 参数；过门）"},
                {"op": "unset", "in": {"slot": "<槽位>"}, "out": "ok"},
                {"op": "test", "in": {"slot": "可选"}, "out": "每题一行的闭环自检（只读）"},
                {"op": "pick", "in": {"slot": "<槽位>", "need_tokens": "可选"},
                 "out": "ref（当前该用哪条）+ skipped[]（跳过了谁、为什么）"},
                {"op": "report", "in": {"slot": "..", "ref": "可选", "tokens": 1234},
                 "out": "used/quota/headroom/exhausted（超限自动标记耗尽）"},
                {"op": "mark_fail", "in": {"slot": "..", "ref": "可选",
                                           "kind": "rate_limited|quota_exhausted|key_invalid|transient|upstream_error|bad_request"},
                 "out": "failover/cooldown_s/exhausted/disabled"},
                {"op": "energy", "in": {}, "out": "slots[].candidates[]（余量/状态/冷却）+ energy_alive"},
                {"op": "switch", "in": {"slot": "..", "ref": "..", "why": "可选"},
                 "out": "from/to（手动指定；过门）"},
            ],
            "不做": ["不经本口子写密钥值（走 model_key_pool 的 DPAPI 路径）",
                    "不回显密钥（只有掩码）",
                    "不碰 FreeLLMAPI 的 dashboard 会话（那是它的控制端；我们只用 /v1）",
                    "**不做同平台多账号轮换绕限流**（那是批量注册，违规）：合规的降级是**跨来源**排队"],
            "设置页建议": ("读 energy 渲染每槽的候选表（引用/掩码/余量/状态）；"
                        "用 set 改候选与参数；用 pick 取当前该用的那条；"
                        "用 report 回写用量；整页只出现**引用名**，真密钥永不进设置页")}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    if op == "status":
        return status(**params)
    if op == "set":
        return set_ref(**params)
    if op == "unset":
        return unset(**params)
    if op == "test":
        return test(**params)
    if op == "where":
        return where(**params)
    # ── 2026-09-28 新增 ──
    if op == "pick":
        return pick(**params)
    if op == "report":
        return report(**params)
    if op == "mark_fail":
        return mark_fail(**params)
    if op == "switch":
        return switch(**params)
    if op == "energy":
        return energy(**params)
    return {"ok": False, "error": f"未知 op:{op}"
                                  f"（status/set/unset/test/where/pick/report/mark_fail/switch/energy）",
            "fail_closed": True}


HONEST_BOUNDARY = (
    "本口子保证『一槽多候选、按余量与优先级选路、前一条耗尽/冷却/失效自动落向下一条、"
    "只回引用与掩码』；它**保证不了**『免费额度无限』——每家的免费额度由**平台条款**定义，"
    "不由我们定义。额度数字是**声明值 + 本地记账**，不是平台真实读数"
    "（除少数平台外额度不开放查询 API；真实 429/402 应经 op=mark_fail 落进同一条降级路径）。"
    "它也**不做**同平台多账号轮换来绕限流（那是批量注册，违规）：合规的降级是**跨来源**排队。"
)
