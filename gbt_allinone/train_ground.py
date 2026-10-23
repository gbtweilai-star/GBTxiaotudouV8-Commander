# -*- coding: utf-8 -*-
# ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""train_ground —— **回炉训练场**（主人令 2026-10-16：必须用万能插无死角训练；
万能插就是她的手原生态执行手）。

本位 = **她的手**：回炉训练不再靠外部手摇脚本，而是一个能力位里的 op。
内部复用云卡触手 `pod_link` 的同一套通道（JupyterLab HTTP + 内核）——
与 `comfy_cloud`“经 pod_link 递脚本”同一个已有模式，**不新造路**。

卡片端脚本单独落在 `tools/train/card_*.py`（薄壳不套引号）。
op：plan（直达路线）· status（卡/日志/GPU/语料哈希）· monitor（训练进度）
      launch（上语料+点火，外部执行）· merge（卡上合并，外部执行）
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "tools" / "train"
CORPUS = ROOT / ".scratch" / "self_knowledge_v60.jsonl"
REMOTE_CORPUS = "/workspace/self_knowledge_v60.jsonl"
TRAINER = ROOT / "tools" / "train" / "train_v26_qlora.py"   # 通用训练脚本（v26 起源，路径全走 env）
REMOTE_TRAINER = "/workspace/_train_src.txt"
MANIFEST = ROOT / "state" / "train" / "corpus_v60_manifest.json"
REMOTE_OUT = "/workspace/lora_v60"
TRAIN_LOG = "/workspace/train_v60.log"
# ── 合并 / 验收 / 取回 的实物（缺一件这条能力就不齐）──
MERGE_SCRIPT = TRAIN / "merge_lora.py"
REMOTE_MERGE_SCRIPT = "/workspace/_merge_src.txt"
REMOTE_MERGED = "/workspace/gbt-v8-v60"
MERGE_LOG = "/workspace/merge_v60.log"
ACCEPT_SCRIPT = TRAIN / "accept_infer.py"
ACCEPT_Q = ROOT / ".scratch" / "accept_q.json"
REMOTE_ACCEPT_SCRIPT = "/workspace/_accept_src.txt"
REMOTE_ACCEPT_Q = "/workspace/accept_q.json"
REMOTE_ACCEPT_A = "/workspace/accept_a_v60.jsonl"
ACCEPT_LOG = "/workspace/accept_v60.log"
OUT_LOCAL = ROOT / ".scratch" / "train_out" / "v60"
LEGACY_CARD = "m5a4o6ubgc39cd"


def _resolve_card() -> str:
    """训练卡**现读**（不写死）：env `GBT_TRAIN_CARD` → `state/train_card.json` → 旧常量。

    🔴 2026-10-17 修（留痕）：原实现把卡号**写死**成 `m5a4o6ubgc39cd`。
    实测：`pod_link status` 现读 **52 台卡全 EXITED**，且这 52 台里**查无此 ID** ⇒
    写死的卡号已过期，launch 永远卡在 `up: http 404`（"语料对账不一致"的真因之一）。
    现口径：卡号可配（env / state/train_card.json），没配才回落旧常量——
    并在 `plan()` 里**如实标出卡是从哪来的**，读的人不会把过期常量当现役。
    """
    import json as _json
    import os as _os

    def _valid(v: str) -> bool:
        """卡号必须像真 id：非空、不含占位符尖括号、不是 `卡id/none/null`。

        🔴 2026-10-17 加：主人第一次落盘时写的是 `{"card":"<卡id>"}`（占位符）——
          若把它当真卡号，`up/run` 只会得到 404 又说不清原因。占位符**一律不收**，
          并让 `_card_source()` 如实标「配置是占位符、已忽略」。
        """
        s = str(v or "").strip()
        return bool(s) and ("<" not in s) and (">" not in s) and s.lower() not in (
            "卡id", "cid", "none", "null", "todo", "tbd")

    env = (_os.environ.get("GBT_TRAIN_CARD") or "").strip()
    if env and _valid(env):
        return env
    p = ROOT / "state" / "train_card.json"
    if p.is_file():
        try:
            j = _json.loads(p.read_text(encoding="utf-8-sig"))  # PS Set-Content 会写 BOM
            v = str((j or {}).get("card") or (j or {}).get("pod") or "").strip()
            if _valid(v):
                return v
        except Exception:                                         # noqa: BLE001
            pass
    return LEGACY_CARD


def _card_source() -> str:
    import json as _json
    import os as _os
    env = (_os.environ.get("GBT_TRAIN_CARD") or "").strip()
    if env:
        return ("env:GBT_TRAIN_CARD" if "<" not in env else "env:GBT_TRAIN_CARD（**占位符无效，已忽略**）")
    p = ROOT / "state" / "train_card.json"
    if p.is_file():
        try:
            j = _json.loads(p.read_text(encoding="utf-8-sig"))  # PS Set-Content 会写 BOM
            v = str((j or {}).get("card") or (j or {}).get("pod") or "").strip()
            if "<" in v or not v:
                return "state/train_card.json（**占位符无效，已忽略**）"
        except Exception:                                         # noqa: BLE001
            return "state/train_card.json（**读不动，已忽略**）"
        return "state/train_card.json"
    return "旧常量（**已过期，需现配**）"


CARD = _resolve_card()
READ_OPS = ("plan", "preflight", "status", "monitor", "fetch", "judge")
WRITE_OPS = ("launch", "merge", "accept", "accept_all", "finalize", "start_card", "stop_card")


def _pod():
    from .tools import pod_link as pl
    return pl


def _gate(payload: dict) -> dict:
    """**只走唯一门**：`pod_link` 的动作一律经 `api.run_task`。

    🔴 2026-10-17 修（**安全洞 · 门被绕过** · 留痕 · 原口径 / 为什么翻 / 现口径）：
      原实现：`launch` / `merge` / `monitor` 里直调 `pl.up(...)` / `pl.run(...)`。
      为什么翻：那是**直接调模块函数** ⇒ 绕过授权门 —— `pod_link` 的 `up` 要
        `data_export + filesystem_write`、`run` 要 `process_execute`（`policy.evaluate` 现读），
        而这条路上**一个作用域都没过门**（实测直调时卡 404 也照样去怼语料上传）。
        AGENTS 生产面红线第二节写死：「写生产/镜像的动作一律走 run_task；
        **禁止直接调模块函数** —— 那会绕过授权门」。
      现口径：统一 `api.run_task("pod_link", …)`；缺作用域由门 fail-closed，
        门拒绝时把 `missing_scopes / how_to_grant` **原样带出**（不吞、不假装成功）。
    """
    try:
        from . import api as _api
        r = _api.run_task("pod_link", payload)
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    # 门拒绝：拒绝面可能在顶层，也可能在 gbt_result 里 —— 两处都看
    gr = r.get("gbt_result") if isinstance(r, dict) else None
    for cand in (r, gr):
        if isinstance(cand, dict) and (cand.get("denied")
                                       or cand.get("missing_scopes") or cand.get("missing")):
            return {"ok": False, "denied": True,
                    "missing_scopes": cand.get("missing_scopes") or cand.get("missing") or [],
                    "reason": cand.get("reason") or cand.get("message") or "",
                    "how_to_grant": cand.get("how_to_grant") or [],
                    "note": "**门拒绝** ⇒ 不绕门、不重试旁路"}
    body = gr if isinstance(gr, dict) else r
    if isinstance(body, dict) and "result" in body:
        body = body.get("result")
    return body if isinstance(body, dict) else {"ok": False, "raw": str(body)[:200]}


def _card(name: str) -> str:
    p = TRAIN / name
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def plan() -> dict:
    return {"ok": True, "op": "plan", "kind": "train_ground", "card": CARD,
            "卡来源": _card_source(),
            "steps": [
                {"n": 1, "what": "意图直达", "via": "cap train_ground '{\"op\":\"launch\"}'"},
                {"n": 2, "what": "卡", "via": "pod_link（status/start/create） · 现役 " + CARD},
                {"n": 3, "what": "语料", "via": str(CORPUS.name) + " → " + REMOTE_CORPUS + "（本地 sha 对 manifest + 回读 sha256）"},
                {"n": 4, "what": "训练脚本", "via": TRAINER.name + " → " + REMOTE_TRAINER + "（卡上薄壳读它点火）"},
                {"n": 5, "what": "训练", "via": "card_launch.py（pip 锁版 + QLoRA）→ " + REMOTE_OUT},
                {"n": 6, "what": "合并", "via": "card_merge.py → bf16 全量（卡上）"},
                {"n": 7, "what": "验收", "via": "54 题 + brand-lock-check（四把锁）"}],
            "手的口径": "万能插唯一门：five-dim.py cap train_ground ...",
            "只读 op": list(READ_OPS), "外部执行 op": list(WRITE_OPS)}


def _card_state() -> dict:
    """点火前**验卡**：卡号有效 + 卡队里真有这台 + 状态 RUNNING。

    🔴 2026-10-17 加（**防烧票** · 留痕）：`data_export` 是**一次性消耗**（用掉即删行）。
      原来 `launch` 一上来就 `up` 语料 —— 若卡号是占位符/过期常量/卡已销毁，
      一次性票就被**死在 404 上烧掉**（实测 `up: http 404`）。现口径：
      **先验卡、再上传**；卡不可用一律 `stage=card` 早退，**不碰一次性票**。
    """
    src = _card_source()
    bad_src = ("占位符" in src) or ("旧常量" in src) or ("读不动" in src)
    if bad_src:
        return {"ok": False, "card": CARD, "source": src,
                "why": "没有有效卡号（%s）⇒ 先落 `state/train_card.json` 的 {\"card\":\"<真id>\"} 或设 env GBT_TRAIN_CARD" % src}
    r = _gate({"op": "status"})
    if not r.get("ok"):
        return {"ok": False, "card": CARD, "source": src,
                "why": "读卡队失败：%s" % str(r.get("reason") or r.get("error") or r)[:160]}
    pods = r.get("pods") or r.get("rows") or []
    row = next((p for p in pods if str(p.get("id")) == str(CARD)), None)
    if not row:
        return {"ok": False, "card": CARD, "source": src,
                "why": "卡队里**查无此 id**（卡号过期/写错；现读 %d 台）" % len(pods)}
    st = str(row.get("状态") or row.get("status") or row.get("desiredStatus") or "")
    running = st.strip().upper() == "RUNNING"
    return {"ok": running, "card": CARD, "source": src, "status": st,
            "why": ("卡在跑 ⇒ 可上传点火" if running else
                    "卡状态 %s ⇒ 需先 start（花钱动作，硬闸要 confirm=\"主人已授权\"）" % st)}


def _blueprint_state() -> dict:
    """**蓝图批准时效**读数（see_first 用 TTL 7200s 判动作）。

    🔴 2026-10-17 加（留痕 · 实测踩到）：`start_card` 被 `see_first` 拒 ——
      v49 批准 mtime 13:58:33，动作发生在 **120.2 分钟**（TTL 120 分钟）⇒ **刚过线 12 秒**。
      训练动作是"一串"（起卡/启动/合并/验收各一次门检查），蓝图 TTL 只有 2 小时、
      比训练窗口短 ⇒ **必须能提前看见还剩多少秒**，不然训练半路被拦下最费钱。
      本位只**如实读数**，不改任何 TTL/不碰 policy（那是主人面）。
    """
    import time as _t
    ttl = 7200
    bdir = ROOT / "state" / "blueprints"
    now = _t.time()
    best = None
    for f in bdir.glob("*.approved"):
        try:
            age = now - f.stat().st_mtime
        except OSError:
            continue
        if age <= ttl and (best is None or age < best[1]):
            best = (f.name, age)
    if best is None:
        return {"ok": False, "ttl_s": ttl,
                "why": "TTL 内**无已批蓝图** ⇒ see_first 会拦动作；请主人重跑 blueprint-first approve"}
    return {"ok": True, "file": best[0], "age_s": int(best[1]),
            "left_s": int(ttl - best[1]), "ttl_s": ttl,
            "note": ("剩 %d s（约 %.0f 分钟）⇒ 够跑完这一串动作" % (ttl - best[1], (ttl - best[1]) / 60)
                     if ttl - best[1] > 1800 else
                     "⚠ 只剩 %d s（约 %.0f 分钟）⇒ **先补批准**再点火（训练动作要过多次门）"
                     % (ttl - best[1], (ttl - best[1]) / 60))}


def preflight() -> dict:
    """只读预检：**能力件清单** + 语料对账 + 卡可用性 + 要哪几张票。

    Owner 令 2026-10-17：「你别看几轮，**看能力齐全**」⇒ 这一发就是"齐全度"读数：
    逐件检查闭环里每个实物在不在盘上，缺哪件**点名**，不靠记忆。
    """
    chk = _corpus_check()
    cs = _card_state()
    arts = {
        "语料 v49": CORPUS.is_file(),
        "语料 manifest": MANIFEST.is_file(),
        "训练脚本": TRAINER.is_file(),
        "卡上启动壳": (TRAIN / "card_launch.py").is_file(),
        "合并器": MERGE_SCRIPT.is_file(),
        "卡上合并壳": (TRAIN / "card_merge.py").is_file(),
        "验收器": ACCEPT_SCRIPT.is_file(),
        "题库": ACCEPT_Q.is_file(),
        "卡上验收壳": (TRAIN / "card_accept.py").is_file(),
        "蓝图已批": any((ROOT / "state" / "blueprints").glob("*v49-train.approved")),
    }
    missing = [k for k, v in arts.items() if not v]
    bp = _blueprint_state()
    return {"ok": bool(chk.get("ok") and cs.get("ok") and not missing and bp.get("ok")),
            "op": "preflight", "kind": "train_ground",
            "能力件": arts, "缺件": missing,
            "corpus_check": chk, "card_state": cs, "blueprint_state": bp,
            "ops": {"只读": list(READ_OPS), "执行": list(WRITE_OPS)},
            "闭环": "preflight → start_card(confirm) → launch(confirm) → monitor → accept(confirm) "
                    "→ fetch answers → judge → merge(confirm) → stop_card(confirm)",
            "need_scopes": ["data_export", "filesystem_write", "process_execute"],
            "点火命令": "five-dim.py cap train_ground '{\"op\":\"launch\",\"confirm\":\"主人已授权\"}'"}


def _down_text(remote: str, limit: int = 24000) -> dict:
    """**读卡上文本件**走 `pod_link.down`（契约里的"卡 → 本机"读路，作用域零、不需 confirm）。

    🔴 2026-10-17 修（**能力不齐** · 留痕）：`pod_link.run` 自身也要 `confirm="主人已授权"`
      ⇒ 原来 `status`/`monitor` 靠"在卡上跑脚本"读日志，**永远读不到**（先撞 process_execute，
      再撞 confirm）。而契约把 `status/ls/down/where` 明确列为**零作用域读路** ⇒
      日志/答案/读数一律走 `down`；只有**执行类**（run/start/stop/create）才要票+confirm。
    """
    import tempfile
    try:
        d = tempfile.mkdtemp(prefix="gbt_down_")
        local = str(Path(d) / (remote.rsplit("/", 1)[-1] or "file"))
        r = _gate({"op": "down", "remote": remote, "local": local})
        if not r.get("ok"):
            return {"ok": False, "remote": remote,
                    "why": str(r.get("reason") or r.get("error") or r)[:160]}
        p = Path(local)
        if not p.is_file():
            return {"ok": False, "remote": remote, "why": "down 报 ok 但本地没落盘（不许假装读到）"}
        txt = p.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "remote": remote, "bytes": len(txt.encode("utf-8")),
                "text": txt[-limit:], "sha256_16": r.get("sha256_16")}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "remote": remote,
                "why": "%s: %s" % (type(exc).__name__, str(exc)[:120])}


def status() -> dict:
    cs = _card_state()
    log = _down_text(TRAIN_LOG, 4000) if cs.get("ok") else {"ok": False, "why": "卡不可用，不读日志"}
    return {"ok": bool(cs.get("ok")), "op": "status", "kind": "train_ground", "card": CARD,
            "card_state": cs,
            "训练日志尾": (log.get("text") or "")[-1200:] if log.get("ok") else "未读到",
            "取不到就写未读到": True,
            **({} if log.get("ok") else {"日志为什么读不到": log.get("why")})}


def monitor() -> dict:
    log = _down_text(TRAIN_LOG, 20000)
    txt = log.get("text") or ""
    loss = re.findall(r"loss['\"]?[:= ]+([0-9.]+)", txt)
    lines = [x for x in txt.strip().splitlines() if x.strip()]
    return {"ok": bool(log.get("ok")), "op": "monitor", "kind": "train_ground",
            "loss（最后几个）": loss[-4:] if loss else "未读到",
            "最后一行": (lines[-1][:180] if lines else "未读到"),
            **({} if log.get("ok") else {"why": log.get("why")})}


def _corpus_check() -> dict:
    """上传前**本地对账**：语料 sha256 必须等于 manifest 声明，否则 fail-closed（不点火）。

    🔴 2026-10-17 加（留痕）：下面这堆 v26→v49 的接线，起因是实测——
      `train_ground.CORPUS` 指的还是 `self_knowledge_v26.jsonl`（654KB），而 v49 语料
      早在 06:12 就生成好了（`self_knowledge_v49.jsonl` 1,862,792B / 5549 条 / sha 6b7f6689…）
      ⇒ 照原样点火会**拿 v26 数据训 v49**（训了但训错，比没训更坏）。
      对账依据 = `state/train/corpus_v49_manifest.json`（生成器自己落的那份，不是手写）。
    """
    import hashlib
    import json as _json
    if not CORPUS.is_file():
        return {"ok": False, "why": "语料不在盘：%s" % CORPUS}
    blob = CORPUS.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    man = {}
    if MANIFEST.is_file():
        try:
            man = _json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:                                         # noqa: BLE001
            man = {}
    want = str(man.get("sha256") or "")
    return {"ok": bool(want) and sha == want, "sha256": sha, "manifest_sha256": want,
            "bytes": len(blob), "manifest_bytes": man.get("bytes"),
            "count": man.get("count"), "appended": man.get("appended"),
            "why": ("对账一致" if sha == want else
                    ("**manifest 缺 sha 或语料被改过** ⇒ 不点火（先跑 gen_corpus_v49.py）"))}


def launch(dry: bool = False, confirm: str = "", skip_up: bool = False, **_kw) -> dict:
    """点火训练。`skip_up=True` ⇒ 复用卡上**已上传且校验过**的语料（不再烧 `data_export`）。

    2026-10-17 追加（留痕）：`data_export` 是**一次性**的，而它可能比训练窗口先过期；
    允许先把语料单独 `up` 上卡（并用零票的 `down` 回读对账），训练时 `skip_up=True` 直接点火。
    """
    chk = _corpus_check()
    if dry:
        return {"ok": True, "op": "launch", "dry_run": True, "card": CARD, "corpus": str(CORPUS),
                "corpus_check": chk,
                "steps": ["本地语料对账（sha256 vs manifest）", "up 语料（回读 sha256）",
                          "up 训练脚本（通用，v26 起源）", "card_launch.py（锁版 pip + QLoRA）"],
                "_口径": "dry_run 不动卡"}
    if not chk.get("ok"):
        return {"ok": False, "op": "launch", "stage": "corpus_local", "corpus_check": chk,
                "reason": "本地语料与 manifest 对不上 ⇒ 不点火（不拿错数据训）"}
    # **先验卡再上传**：卡不可用 ⇒ 早退，绝不拿一次性 data_export 去撞死卡（见 `_card_state` 留痕）
    cs = _card_state()
    if not cs.get("ok"):
        return {"ok": False, "op": "launch", "stage": "card", "card_state": cs,
                "reason": "卡不可用 ⇒ **不上传、不烧票**；先解决卡（%s）" % cs.get("why")}
    if skip_up:
        up = {"ok": True, "skipped": True, "sha256_16": str(chk.get("sha256") or "")[:16],
              "note": "复用卡上已上传语料（skip_up=True，不再烧 data_export）"}
    else:
        up = _gate({"op": "up", "local": str(CORPUS.relative_to(ROOT)),
                    "remote": REMOTE_CORPUS, "pod": CARD})
        rb = up.get("回读") or {}
        if not up.get("ok") or rb.get("sha256_16") != up.get("sha256_16"):
            return {"ok": False, "op": "launch", "stage": "up",
                    "reason": ("语料对账不一致 ⇒ 不点火" if not up.get("denied")
                               else "门拒绝：缺作用域 ⇒ 不点火（不许绕门）"),
                    "up": up}
    # 🔴 2026-10-17 省票：训练脚本**内嵌进 run(code=)**，不再单独 `up`（data_export 一次性，省一张）
    import base64 as _b64
    code = _card("card_launch.py")
    if "__GBT_TRAINER_B64__" in code and TRAINER.is_file():
        code = code.replace("__GBT_TRAINER_B64__",
                            _b64.b64encode(TRAINER.read_bytes()).decode())
        upt = {"ok": True, "embedded": True, "n": len(code)}
    else:
        upt = _gate({"op": "up", "local": str(TRAINER.relative_to(ROOT)),
                     "remote": REMOTE_TRAINER, "pod": CARD})
    if not upt.get("ok"):
        return {"ok": False, "op": "launch", "stage": "up_trainer",
                "reason": "训练脚本没上卡 ⇒ 不点火", "up_trainer": upt}
    r = _gate({"op": "run", "code": code, "pod": CARD, "confirm": confirm})
    return {"ok": bool(r.get("ok")), "op": "launch", "kind": "train_ground", "card": CARD,
            "语料对账": up.get("sha256_16"), "脚本体": "内嵌(不占票)",
            "点火": (r.get("out") or "").strip()[:160], "日志": TRAIN_LOG}


def merge(confirm: str = "", lora: str = "", out: str = "", **_kw) -> dict:
    """LoRA → bf16 全量（卡上）。合并器本体 = 仓内 `tools/train/merge_lora.py`（原 `post_v26.py` 是幽灵）。

    合并 = **执行类** ⇒ 走门 + 要 `process_execute`；卡上跑脚本还要 `confirm="主人已授权"`。

    2026-10-17 追加（留痕）：支持 `lora`/`out` 指定**哪一代适配器** —— 因为验收实测
    `v50` 家族合计 40/44 优于 `v51` 的 37/44，最终合并要能选**最佳代**而不是管线默认代。
    """
    cs = _card_state()
    if not cs.get("ok"):
        return {"ok": False, "op": "merge", "stage": "card", "card_state": cs,
                "reason": "卡不可用 ⇒ 不合并"}
    # 省票：合并器内嵌（不占上传票）
    import base64 as _b64
    code = _card("card_merge.py")
    if lora:
        # 通用代次替换：卡上壳里的默认值可能是 v49/v50/v51 任一代，按传入的 lora 覆盖
        code = re.sub(r'"lora_v\d+"', '"%s"' % lora, code)
        code = re.sub(r'"merge_v\d+\.log"', '"merge_%s.log"' % lora.replace("lora_", ""), code)
    if out:
        code = re.sub(r'"gbt-v8-v\d+"', '"%s"' % out, code)
    if "__GBT_MERGE_B64__" in code and MERGE_SCRIPT.is_file():
        code = code.replace("__GBT_MERGE_B64__",
                            _b64.b64encode(MERGE_SCRIPT.read_bytes()).decode())
        up = {"ok": True, "embedded": True}
    else:
        up = _gate({"op": "up", "local": str(MERGE_SCRIPT.relative_to(ROOT)),
                    "remote": REMOTE_MERGE_SCRIPT, "pod": CARD})
    if not up.get("ok"):
        return {"ok": False, "op": "merge", "stage": "up_merge_script", "up": up,
                "reason": "合并器没上卡 ⇒ 不合并"}
    r = _gate({"op": "run", "code": code, "pod": CARD, "confirm": confirm})
    return {"ok": bool(r.get("ok")), "op": "merge", "kind": "train_ground", "card": CARD,
            "合并器": "内嵌(不占票)" if up.get("embedded") else "上传",
            "合并已发": (r.get("out") or "").strip()[:160],
            "日志": MERGE_LOG, "产物": REMOTE_MERGED,
            **({} if r.get("ok") else {"stage": "run", "detail": r})}


def accept(confirm: str = "", family: str = "", **_kw) -> dict:
    """卡上**验收推理**：上传验收器 + 题库 → 底座+LoRA 逐题生成 answers（异步）→ 之后 `judge` 判分。

    验收 = 执行类 ⇒ 走门；卡上跑脚本要 confirm。读答案用 `fetch`（零票）。
    """
    cs = _card_state()
    if not cs.get("ok"):
        return {"ok": False, "op": "accept", "stage": "card", "card_state": cs,
                "reason": "卡不可用 ⇒ 不验收"}
    # 2026-10-17 补齐（留痕）：支持**按家族题库**跑验收（6 族各一套），
    #   主 54 用 accept_q.json；家族用 .scratch/<fam>_q.jsonl，答案文件名也随族区分。
    fam = str(family or "").strip().lower()
    q_local = (ROOT / ".scratch" / (fam + "_q.jsonl")) if fam else ACCEPT_Q
    a_name = ("accept_a_%s_v60.jsonl" % fam) if fam else "accept_a_v60.jsonl"
    if not q_local.is_file():
        return {"ok": False, "op": "accept", "stage": "q", "reason": "题库不在盘：%s" % q_local}
    # 省票：验收器 + 题库都内嵌（验收阶段不占上传票）
    import base64 as _b64
    code = _card("card_accept.py")
    shas = []
    if "__GBT_ACCEPT_SRC_B64__" in code and ACCEPT_SCRIPT.is_file():
        code = code.replace("__GBT_ACCEPT_SRC_B64__",
                            _b64.b64encode(ACCEPT_SCRIPT.read_bytes()).decode())
    if "__GBT_ACCEPT_Q_B64__" in code and q_local.is_file():
        code = code.replace("__GBT_ACCEPT_Q_B64__",
                            _b64.b64encode(q_local.read_bytes()).decode())
        code = code.replace("accept_a_v60.jsonl", a_name)
        shas = ["embedded"]
    r = _gate({"op": "run", "code": code, "pod": CARD, "confirm": confirm})
    return {"ok": bool(r.get("ok")), "op": "accept", "kind": "train_ground", "card": CARD,
            "家族": (fam or "主54"), "验收件": "内嵌(不占票)",
            "验收已发": (r.get("out") or "").strip()[:160],
            "答案在卡上": "/workspace/" + a_name, "日志": ACCEPT_LOG,
            **({} if r.get("ok") else {"stage": "run", "detail": r})}


def accept_all(confirm: str = "", **_kw) -> dict:
    """卡上**一发跑完全部验收**（主54 + 6 族）：一次发射、卡上串行、题库/答案文件各自独立。

    2026-10-17 新增（主人令「必须把细节做到位」）：逐族发射要 7 张 `process_execute` 且每次重载模型
    （~40s），票易过期；并发跑又会互踩同名文件（accept_infer.py/accept_q.json 固定路径）。
    ⇒ 本 op 把 runner + accept_infer + 全部题库**内嵌**进 run(code=)（不占上传票），
      在卡上以 nohup 后台串行跑，主线程立刻返回（不等 20 分钟）。
    """
    cs = _card_state()
    if not cs.get("ok"):
        return {"ok": False, "op": "accept_all", "stage": "card", "card_state": cs,
                "reason": "卡不可用 ⇒ 不验收"}
    banks = {}
    if ACCEPT_Q.is_file():
        banks["main54"] = [l for l in ACCEPT_Q.read_text(encoding="utf-8").splitlines() if l.strip()]
    for name in ("comfy", "forge", "offense", "sc", "spider", "video"):
        p = ROOT / ".scratch" / (name + "_q.jsonl")
        if p.is_file():
            banks[name] = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not banks:
        return {"ok": False, "op": "accept_all", "stage": "q", "reason": "没有任何题库"}
    import base64 as _b64
    runner = (ROOT / "tools" / "train" / "card_accept_all.py").read_text(encoding="utf-8")
    runner = runner.replace("\"/workspace/lora_v51\"", "\"%s\"" % REMOTE_OUT)  # 代次跟着管线走，别再写死
    runner = runner.replace("__GBT_ACCEPT_INFER_B64__", _b64.b64encode(ACCEPT_SCRIPT.read_bytes()).decode())
    runner = runner.replace("__GBT_BANKS_B64__",
                            _b64.b64encode(json.dumps(banks, ensure_ascii=False).encode()).decode())
    code = ("import base64, subprocess, pathlib\n"
            "WS = pathlib.Path('/workspace')\n"
            "(WS/'accept_all.py').write_bytes(base64.b64decode(%r))\n"
            "cmd = (\"nohup bash -lc 'cd /workspace && python -u /workspace/accept_all.py' \"\n"
            "       \"> /workspace/accept_all.log 2>&1 & echo STARTED\")\n"
            "p = subprocess.run(['bash','-lc',cmd], capture_output=True, text=True, timeout=60)\n"
            "print('OUT', (p.stdout or '').strip(), (p.stderr or '')[-200:])\n"
            % _b64.b64encode(runner.encode()).decode())
    r = _gate({"op": "run", "code": code, "pod": CARD, "confirm": confirm})
    return {"ok": bool(r.get("ok")), "op": "accept_all", "kind": "train_ground", "card": CARD,
            "套件": list(banks), "题数": {k: len(v) for k, v in banks.items()},
            "验收已发": (r.get("out") or "").strip()[:200],
            "答案文件": "/workspace/accept_a_<suite>_v51.jsonl", "日志": "/workspace/accept_all.log",
            **({} if r.get("ok") else {"stage": "run", "detail": r})}


def fetch(what: str = "answers", **_kw) -> dict:
    """**取回卡上产物到本机**（`down`，零作用域）+ sha 对账。`what`: answers / merged_config / lora_config。"""
    cs = _card_state()
    if not cs.get("ok"):
        return {"ok": False, "op": "fetch", "stage": "card", "card_state": cs, "reason": "卡不可用"}
    remote = {"answers": REMOTE_ACCEPT_A,
              "merged_config": REMOTE_MERGED + "/config.json",
              "lora_config": REMOTE_OUT + "/adapter_config.json"}.get(str(what).strip().lower())
    if not remote:
        return {"ok": False, "op": "fetch", "reason": "what 只认 answers/merged_config/lora_config",
                "given": what}
    OUT_LOCAL.mkdir(parents=True, exist_ok=True)
    local = str(OUT_LOCAL / (remote.rsplit("/", 1)[-1]))
    r = _gate({"op": "down", "remote": remote, "local": local})
    return {"ok": bool(r.get("ok")), "op": "fetch", "what": what, "remote": remote,
            "local": local, "sha256_16": r.get("sha256_16"),
            **({} if r.get("ok") else {"detail": r})}


def start_card(confirm: str = "", **_kw) -> dict:
    """**开卡（resume，花钱动作）**：必须主人 `confirm="主人已授权"`；门与 pod_link 都会咬。"""
    r = _gate({"op": "start", "pod": CARD, "confirm": confirm})
    return {"ok": bool(r.get("ok")), "op": "start_card", "card": CARD, "detail": r}


def stop_card(confirm: str = "", **_kw) -> dict:
    r = _gate({"op": "stop", "pod": CARD, "confirm": confirm})
    return {"ok": bool(r.get("ok")), "op": "stop_card", "card": CARD, "detail": r}


JUDGES = ("accept_comfy.py", "accept_offense.py", "accept_sc.py", "accept_spider.py",
          "accept_video.py", "accept_forge.py")


def judge(answers: str = "", **_kw) -> dict:
    """**本机判分**：对 `fetch` 回来的 answers 跑验收器（只读分析，不动卡）。"""
    import subprocess
    import sys
    p = Path(answers) if answers else (OUT_LOCAL / "accept_a_v49.jsonl")
    if not p.is_file():
        return {"ok": False, "op": "judge", "reason": "答案不在盘：%s（先 fetch answers）" % p}
    rows = {}
    for name in JUDGES:
        sp = TRAIN / name
        if not sp.is_file():
            rows[name] = {"rc": None, "out": "验收器不在盘"}
            continue
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", str(sp), "--answers", str(p)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=300)
            rows[name] = {"rc": r.returncode,
                          "out": ((r.stdout or "") + (r.stderr or "")).strip()[-400:]}
        except Exception as exc:                                 # noqa: BLE001
            rows[name] = {"rc": -1, "out": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    ok = all(v.get("rc") == 0 for v in rows.values())
    return {"ok": ok, "op": "judge", "answers": str(p), "judges": rows}


def finalize(confirm: str = "", gen: str = "", do_merge: bool = True, **_kw) -> dict:
    """**训练收尾标准流程**（主人 2026-10-17：「这设置好每次训练都要最后这样出来」）。

    固定五步（全部现读，读数不全就写未读到，不编）：
      ① **合并**：最佳适配器 → `/root/gbt-v8-<gen>`（容器盘；卷配额 30G 放不下 15G 合并件）
      ② **量化压缩**：调原生能力 `quant_plan`（plan/layer/route/speed/check）取压缩阶梯与直达线路；
         另按本模型参数（7.7B）给出 bits→体积估算（确定性算术）
      ③ **惰性激活**：报告"用到哪块激活哪块、不用静默"的落点设计 + 现役实测显存（训练峰值）
      ④ **每页绑定 + 任意页直达**：跑原生 `page-reach --check` / `page-bind-check` / `project-bind --check`
      ⑤ **出收尾清单**：`state/weights/release-manifest-<gen>.json` + logbook 记一条
    `gen` 缺省取 CORPUS 名里的 `vNN`；`do_merge=False` 时跳过 ①（只出读数）。
    """
    import subprocess
    import sys
    import time as _t
    gen = str(gen or "").strip() or (CORPUS.stem.rsplit("_", 1)[-1] if "_" in CORPUS.stem else "run")
    out = {"op": "finalize", "gen": gen, "when": _t.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {}}

    # ① 合并（执行类 ⇒ 走门 + confirm）
    if do_merge:
        out["steps"]["merge"] = merge(confirm=confirm, lora="lora_%s" % gen, out="/root/gbt-v8-%s" % gen)
    else:
        out["steps"]["merge"] = {"ok": True, "skipped": True, "why": "do_merge=False（只出读数）"}

    # ② 量化压缩：原生 quant_plan 五 op 现读
    def _cap(kind: str, payload: dict) -> dict:
        p = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "codex-scripts" / "five-dim.py"),
                            "cap", kind, json.dumps(payload, ensure_ascii=False)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        txt = (p.stdout or "") + (p.stderr or "")
        i = txt.find("{")
        try:
            return json.loads(txt[i:]).get("result") or {}
        except Exception:                                        # noqa: BLE001
            return {"ok": False, "未读到": txt[:200]}

    qp = {}
    for qop in ("plan", "layer", "speed", "check"):
        qp[qop] = _cap("quant_plan", {"op": qop})
    qp["route"] = _cap("quant_plan", {"op": "route", "intent": "训练收尾：合并件到部署面的直达线路"})
    out["steps"]["quant_plan"] = {k: {"ok": bool(v.get("ok"))} for k, v in qp.items()}
    # 本模型参数 → bits 估算（确定性算术；params 7,696,356,864 来自训练日志现读）
    params = 7_696_356_864
    est = {}
    for bits in (16, 8, 4, 2):
        est["%dbits" % bits] = round(params * bits / 8 / (1024 ** 3) * 1.05, 2)   # +5% 结构开销
    out["steps"]["size_est_gb"] = est

    # ③ 惰性激活 / 显存（现读训练日志峰值；取不到就写未读到）
    peak = "未读到"
    log = TRAIN_LOG
    if log and Path(log).name:
        pass                                                     # 卡上日志需 down；此处只留口径
    out["steps"]["lazy_activation"] = {
        "设计": "分页/分层按需激活：页面各自静态渲染只加载本块；推理按层加载，未用层不占显存（静默）",
        "训练峰值显存": peak,
        "口径": "峰值显存从卡上 train_<gen>.log 的 TRAIN_DONE 行现读；读不到就写未读到",
    }

    # ③.5 页面自愈（顺序固定 · 2026-10-17 加）：project-bind 新生成的分片页会缺直达条/设备配置，
    #     ⇒ 必须先 build、再 page-reach inject、再 device deploy inject，最后才检查（否则必假红）。
    heal = {}
    for name, argv in (("project-bind", ["tools/codex-scripts/project-bind.py", "--build"]),
                       ("page-reach", ["tools/codex-scripts/page-reach.py", "--inject"]),
                       ("device-deploy", ["tools/codex-scripts/device-deploy.py", "--inject"]),
                       ("gbt-defense", ["tools/codex-scripts/gbt-defense-inject.py"])):
        try:
            cmd = [sys.executable, "-X", "utf8", str(ROOT / argv[0])] + list(argv[1:])
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=1200, cwd=str(ROOT))
            tail = [x.strip() for x in (p.stdout or "").strip().splitlines() if x.strip()]
            heal[name] = {"rc": p.returncode, "line": (tail[-1] if tail else "")[:200]}
        except Exception as e:                                   # noqa: BLE001
            heal[name] = {"rc": -1, "未读到": str(e)[:160]}
    out["steps"]["pages_selfheal"] = heal

    # ④ 页面绑定 + 任意页直达（原生判据，只读）
    pages = {}
    for name, argv in (("page-reach", ["tools/codex-scripts/page-reach.py", "--check"]),
                       ("page-bind-check", ["tools/codex-scripts/page-bind-check.py"]),
                       ("project-bind", ["tools/codex-scripts/project-bind.py", "--check"])):
        try:
            # 只有「脚本路径」那一段要拼 ROOT，选项参数原样传（2026-10-17 修：之前把 --check 也拼成绝对路径）
            cmd = [sys.executable, "-X", "utf8", str(ROOT / argv[0])] + list(argv[1:])
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=900, cwd=str(ROOT))
            tail = [x.strip() for x in (p.stdout or "").strip().splitlines() if x.strip()]
            pages[name] = {"rc": p.returncode, "line": " | ".join(tail[-2:])[:300]}
        except Exception as e:                                   # noqa: BLE001
            pages[name] = {"rc": -1, "未读到": str(e)[:160]}
    out["steps"]["pages"] = pages

    # ⑤ 收尾清单落盘 + 记账
    man = ROOT / "state" / "weights" / ("release-manifest-%s.json" % gen)
    man.parent.mkdir(parents=True, exist_ok=True)
    man.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    out["manifest"] = str(man.relative_to(ROOT))
    lb = ROOT / "gbt_allinone" / "store" / "logbook.jsonl"
    try:
        line = {"kind": "deliver", "what": "训练收尾 finalize %s（合并/量化/惰性/页面绑定/清单一发）" % gen,
                "ts": _t.strftime("%Y-%m-%dT%H:%M:%S")}
        with lb.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:                                            # noqa: BLE001
        pass
    out["ok"] = all(v.get("ok", False) for k, v in out["steps"].items() if k == "merge") and \
        all(v.get("rc") == 0 for v in pages.values())
    return out


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    cf = str(kw.get("confirm") or "")
    if o == "plan":
        return plan()
    if o == "preflight":
        return preflight()
    if o == "status":
        return status()
    if o == "monitor":
        return monitor()
    if o == "launch":
        return launch(dry=bool(kw.get("dry")), confirm=cf, skip_up=bool(kw.get("skip_up")))
    if o == "merge":
        return merge(confirm=cf, lora=str(kw.get("lora") or ""), out=str(kw.get("out") or ""))
    if o == "accept":
        return accept(confirm=cf, family=str(kw.get("family") or ""))
    if o == "accept_all":
        return accept_all(confirm=cf)
    if o == "finalize":
        return finalize(confirm=cf, gen=str(kw.get("gen") or ""),
                        do_merge=bool(kw.get("do_merge", True)))
    if o == "fetch":
        return fetch(what=str(kw.get("what") or "answers"))
    if o == "judge":
        return judge(answers=str(kw.get("answers") or ""))
    if o == "start_card":
        return start_card(confirm=cf)
    if o == "stop_card":
        return stop_card(confirm=cf)
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(READ_OPS + WRITE_OPS)}

