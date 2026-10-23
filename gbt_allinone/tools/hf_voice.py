# gbt-capability: hf_voice
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Hugging Face 歌声/语音（**3 臂轮询，避免单点卡壳**）—— 主人令 2026-09-28。

## 主人原话与本地事实
- 主人：「主题曲"真唱"…**把插件连接好部署语音不就好了**」+「**安装 3 个这个插件轮询使用避免卡壳**」
  （配图：Hugging Face 推理 API —— 快速访问数千个高性能模型）。
- 本机事实（`gbt_allinone/docs/语音中枢v2.0-实测与部署.md`，2026-09-18 一手实测）：
  **本机零算力**（无 CUDA、内存紧）⇒ 2B/8B 级歌声合成模型**本地跑不动**。
  ⇒ 所以"真唱"只能走云；这一位就是那条云的走廊。

## 为什么是"3 臂轮询"，不是"一把 key 硬扛"
单把 key 会被限流/超时卡死（"卡壳"）。所以**同一个服务挂 3 个账号槽**，按**轮询 + 冷却 + 换道**
用：某臂 429/5xx/超时就把它**冷却**掉，下一次自动投给下一臂 —— 与 `key_gateway` 的
"链序/冷却/禁用/耗尽/换道"**同一套纪律**（不另立一套轮询逻辑）。

## 出网硬钉（本仓红线，写死在代码里）
1. **只许 https**；2. **主机白名单**：只认 Hugging Face 的三个官方域
   （`api-inference.huggingface.co` / `router.huggingface.co` / `huggingface.co`）；
3. **显式拒绝**环回/私有/保留地址（`localhost` `127.*` `10.*` `172.16-31.*` `192.168.*` `169.254.*`
   `::1` `fc00::/7` `0.0.0.0`）—— 白名单已经不可能命中它们，这里**再钉一道**（防将来改白名单时手滑）；
4. **拒重定向**（跟随重定向等于把"发到哪"交给对方）；5. **只回掩码**、密钥永不回显。

## 门
`sing`（真出网发数据 + 落 wav）= 过 **`external_llm`** 门（"把当前任务数据发送到外部服务"）；
若 `out=` 指向**仓外**路径，另过 `filesystem_write`。**缺票如实拒**，不找旁路。

op=status / arms / models / sing / rotate / verify / where
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_LEDGER = _STATE / "hf_voice.jsonl"
_OUT = _STATE / "hf_voice_out"          # 仓内落盘位（与 state/ 同类，默认不过门）
_ALLOWED_HOSTS = {"api-inference.huggingface.co", "router.huggingface.co", "huggingface.co"}
_PRIVATE_RX = re.compile(
    r"^(localhost|0\.0\.0\.0|127\.|10\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|\[?::1\]?|fc|fd)")
COOLDOWN_S, MAX_FAILS = 300, 3        # 一臂连续失败 3 次 ⇒ 冷却 5 分钟（换道）
ARMS = [
    {"id": "hf-1", "refs": ["env:HF_TOKEN_1", "env:HUGGINGFACE_API_KEY", "env:HF_TOKEN"]},
    {"id": "hf-2", "refs": ["env:HF_TOKEN_2"]},
    {"id": "hf-3", "refs": ["env:HF_TOKEN_3"]},
]
# 候选模型（**诚实标注**：本机没有 HF token ⇒ 全部**未验**，谁也别当"已支持"）
MODELS = [
    {"id": "facebook/mms-tts-zho", "kind": "念白·中文", "verified": False,
     "why": "MMS 系 TTS，中文可用；**未验**（缺 token）"},
    {"id": "suno/bark", "kind": "念白/哼唱（多语）", "verified": False,
     "why": "能出拟声与哼唱腔调，**不是完整歌声合成**；**未验**"},
    {"id": "espnet/kan-bayashi_ljspeech_vits", "kind": "念白·英文", "verified": False,
     "why": "经典 VITS 英文；**未验**"},
    {"id": "facebook/musicgen-small", "kind": "**纯音乐**（不是人声）", "verified": False,
     "why": "生成器乐，可用于主题曲伴奏；**未验**"},
]


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _rows() -> list:
    out = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    return out


def _mask(s: str, keep: int = 4) -> str:
    s = s or ""
    return (s[:keep] + "****") if len(s) > keep else ("****" if s else "")


def _resolve(ref: str) -> dict:
    """引用 → 是否在位（**只回掩码/在位，不回值**；vault: 走保险箱，env: 走环境变量）。"""
    if ref.startswith("env:"):
        name = ref[4:]
        v = os.environ.get(name, "")
        return {"kind": "env", "name": name, "present": bool(v), "masked": _mask(v)}
    if ref.startswith("vault:"):
        try:
            import importlib.util as _iu
            sp = _iu.spec_from_file_location("kpg", _ROOT / "gbt_allinone" / "llm" / "key_gateway.py")
            kg = _iu.module_from_spec(sp)
            sp.loader.exec_module(kg)
            got = kg.take(ref.split(":", 1)[1]) if hasattr(kg, "take") else {"ok": False}
            return {"kind": "vault", "name": ref, "present": bool(got.get("ok")),
                    "masked": "<保险箱（不入明文）>"}
        except Exception as exc:                               # noqa: BLE001
            return {"kind": "vault", "name": ref, "present": False,
                    "why": f"{type(exc).__name__}: {str(exc)[:60]}"}
    return {"kind": "?", "name": ref, "present": False, "why": "引用形状不认（env:/vault:）"}


def _arm_state() -> list:
    """每臂在位与健康（含冷却）。"""
    cool = {}
    for r in _rows():
        if r.get("event") == "cool":
            cool[r["arm"]] = r.get("until", 0)
    fails = {}
    for r in _rows():
        if r.get("event") == "fail":
            fails[r["arm"]] = fails.get(r["arm"], 0) + 1
        elif r.get("event") == "ok":
            fails[r["arm"]] = 0
    now = time.time()
    out = []
    for a in ARMS:
        hits = [_resolve(r) for r in a["refs"]]
        present = next((h for h in hits if h["present"]), None)
        until = float(cool.get(a["id"], 0) or 0)
        out.append({"id": a["id"], "present": bool(present),
                    "source": (present or {}).get("name", ""),
                    "masked": (present or {}).get("masked", ""),
                    "cooling_for_s": max(0, int(until - now)),
                    "fails": fails.get(a["id"], 0),
                    "refs_tried": [h.get("name") for h in hits]})
    return out


def status(**_kw) -> dict:
    arms = _arm_state()
    ready = [a for a in arms if a["present"] and a["cooling_for_s"] == 0]
    return {"ok": True, "op": "status", "provider": "huggingface",
            "arms": arms, "arms_present": sum(1 for a in arms if a["present"]),
            "arms_ready": len(ready), "rotate": "round-robin + 冷却换道（与 key_gateway 同一纪律）",
            "models_verified": sum(1 for m in MODELS if m["verified"]),
            "available": bool(ready),
            "install_hint": ("三把 token 只走引用：HF_TOKEN_1 / HF_TOKEN_2 / HF_TOKEN_3"
                             "（或 HUGGINGFACE_API_KEY / HF_TOKEN 作为第 1 臂的回退）——"
                             "**只配环境变量或保险箱，别写进任何文件**"),
            "_口径": "在位=真读环境变量/保险箱；**只回掩码**；可用性 fail-closed（读不到就是不可用）"}


def arms(**_kw) -> dict:
    return {"ok": True, "op": "arms", "rows": _arm_state(),
            "policy": {"轮询": "按 hf-1 → hf-2 → hf-3 顺序取第一个 ready",
                       "冷却": f"单臂连续失败 {MAX_FAILS} 次 ⇒ 冷却 {COOLDOWN_S}s",
                       "换道": "被冷却的臂自动跳过 ⇒ 下次投下一臂（这就是'避免卡壳'）"}}


def _guard(url: str) -> tuple:
    """出网硬钉：只 https + 主机白名单 + 显式拒私有/环回/保留 + 拒重定向（在 opener 里）。"""
    from urllib.parse import urlparse
    u = urlparse(url or "")
    if u.scheme != "https":
        return False, f"只许 https（收到 {u.scheme or '空'}）"
    host = (u.hostname or "").lower()
    if _PRIVATE_RX.match(host):
        return False, f"**拒私有/环回/保留地址**：{host}"
    if host not in _ALLOWED_HOSTS:
        return False, f"主机 {host!r} 不在白名单（只认 {sorted(_ALLOWED_HOSTS)}）"
    return True, ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):
        return None


def _pick(exclude: set) -> dict | None:
    """轮询：按顺序取第一个 ready 且未被本次排除的臂。"""
    for a in _arm_state():
        if a["id"] in exclude or not a["present"] or a["cooling_for_s"] > 0:
            continue
        return a
    return None


def _call_arm(arm: dict, model: str, text: str, timeout: float) -> dict:
    url = "https://api-inference.huggingface.co/models/" + model
    ok, why = _guard(url)
    if not ok:
        return {"ok": False, "guard": why, "fail_closed": True}
    ref = next((r for r in ARMS if r["id"] == arm["id"]), {}).get("refs", [])
    val = ""
    for r in ref:
        if r.startswith("env:"):
            val = os.environ.get(r[4:], "")
            if val:
                break
    if not val:
        return {"ok": False, "why": "这一臂没有可用值（引用不在位）"}
    body = json.dumps({"inputs": text, "options": {"wait_for_model": True}}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                headers={"Authorization": "Bearer " + val,
                                         "Content-Type": "application/json",
                                         "User-Agent": "gbt-v8/hf_voice"})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            data = r.read()
            return {"ok": True, "bytes": len(data), "ctype": r.headers.get("content-type", ""),
                    "data": data}
    except urllib.error.HTTPError as e:
        return {"ok": False, "code": e.code, "why": f"HTTP {e.code}",
                "cooldown": e.code in (401, 403, 429) or e.code >= 500}
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "why": f"{type(exc).__name__}: {str(exc)[:100]}", "cooldown": True}


def sing(text: str = "", model: str = "facebook/mms-tts-zho", out: str = "",
         timeout: float = 60.0, **_kw) -> dict:
    """文 → 声（**真出网 + 落 wav**）：过 `external_llm` 门 → 3 臂轮询 → 落盘。"""
    if not text.strip():
        return {"ok": False, "op": "sing", "fail_closed": True, "error": "要给 text（要唱的/要念的文本）"}
    if not any(m["id"] == model for m in MODELS):
        return {"ok": False, "op": "sing", "fail_closed": True,
                "error": f"模型不在候选表：{model}（候选：{[m['id'] for m in MODELS]}）",
                "why": "不在册的模型名不许盲发（免得打到一个陌生端点）"}
    ready = [a for a in _arm_state() if a["present"] and a["cooling_for_s"] == 0]
    if not ready:
        return {"ok": False, "op": "sing", "available": False, "fail_closed": True,
                "error": "**三臂都没有可用值**（HF_TOKEN_1/2/3 都不在位）",
                "how": "把三把 token 配成环境变量或保险箱条目（引用式：env:/vault:）；"
                       "**谁有权给：主人**（我不代持、不写进文件）",
                "arms": _arm_state()}
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                            # noqa: F401
        from gbt_allinone import auth_gate                   # type: ignore
        from gbt_allinone.security import policy as _policy  # type: ignore
    if not _policy.is_trusted():
        gate = auth_gate.check_and_consume("external_llm", detail=f"hf_voice sing {model}")
        if not gate.get("ok"):
            return {"ok": False, "op": "sing", "denied": True, "fail_closed": True,
                    "error": gate.get("error"), "how_to_grant": gate.get("how_to_grant"),
                    "why": "把文本发到外部服务 = `external_llm` 门；缺票如实拒"}
    tried, exclude = [], set()
    for _ in range(len(ARMS)):
        arm = _pick(exclude)
        if not arm:
            break
        tried.append(arm["id"])
        r = _call_arm(arm, model, text, timeout)
        if r.get("ok"):
            data = r.pop("data")
            dest = Path(out) if out else (_OUT / ("%s-%s.wav" % (time.strftime("%Y%m%d-%H%M%S"),
                                                                model.split("/")[-1])))
            if not dest.is_absolute():
                dest = _ROOT / dest
            gated = str(_ROOT) not in str(dest)               # 写仓外 ⇒ 另过写盘门
            if gated and not _policy.is_trusted():
                g2 = auth_gate.check_and_consume("filesystem_write", detail=f"hf_voice out {dest}")
                if not g2.get("ok"):
                    return {"ok": False, "op": "sing", "denied": True, "gate": "filesystem_write",
                            "error": g2.get("error"), "how_to_grant": g2.get("how_to_grant")}
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)                            # **二进制逐字节落盘**
            _log({"event": "ok", "arm": arm["id"], "model": model, "bytes": r["bytes"],
                  "out": str(dest.relative_to(_ROOT)).replace("\\", "/")})
            return {"ok": True, "op": "sing", "arm": arm["id"], "model": model,
                    "bytes": r["bytes"], "out": str(dest.relative_to(_ROOT)).replace("\\", "/"),
                    "tried": tried, "verified": False,
                    "note": "**未验**：本机没有 HF token 时这条从没真跑过；这次是**真发出去了**才算"
                            "（请听一遍 wav 再当成品——听感是人的判据，不是判据器的）"}
        _log({"event": "fail", "arm": arm["id"], "why": r.get("why"), "code": r.get("code")})
        if r.get("cooldown"):
            _log({"event": "cool", "arm": arm["id"], "until": time.time() + COOLDOWN_S,
                  "why": r.get("why")})
            exclude.add(arm["id"])
        else:
            exclude.add(arm["id"])
    _log({"event": "exhausted", "tried": tried, "model": model})
    return {"ok": False, "op": "sing", "exhausted": True, "tried": tried,
            "why": "三臂全部失败 ⇒ 如实报（不重试刷额度）",
            "how": "看 state/hf_voice.jsonl 的 fail 行拿原因（401=token 无效 / 429=限流 / 5xx=对方抖动）"}


def rotate(arm: str = "", action: str = "", **_kw) -> dict:
    """手动换道：`action=disable|enable`（禁用/恢复某臂）。"""
    if arm not in [a["id"] for a in ARMS] or action not in ("disable", "enable"):
        return {"ok": False, "op": "rotate", "fail_closed": True,
                "error": f"要给 arm ∈ {[a['id'] for a in ARMS]} 与 action ∈ disable/enable"}
    until = (time.time() + 10 ** 9) if action == "disable" else 0
    _log({"event": "cool" if action == "disable" else "ok", "arm": arm, "until": until,
          "by": "manual"})
    return {"ok": True, "op": "rotate", "arm": arm, "action": action,
            "note": "手动改的是**冷却位**（不改密钥）；恢复用 enable"}


def models(**_kw) -> dict:
    return {"ok": True, "op": "models", "count": len(MODELS), "rows": MODELS,
            "caveat": "**全部未验**（本机无 HF token）；`musicgen` 是**器乐**不是人声；"
                      "真'唱'（歌声合成）在 HF 上要靠 singing 专用模型，本表还没纳入验证过的项"}


def verify(**_kw) -> dict:
    problems = []
    src = Path(__file__).read_text(encoding="utf-8")
    # ① 出网钉必须真在
    for needle, why in (("_ALLOWED_HOSTS", "主机白名单"), ("_PRIVATE_RX", "私有/环回拒绝"),
                        ("_NoRedirect", "拒重定向"), ("scheme != \"https\"", "只许 https")):
        if needle not in src:
            problems.append(f"出网硬钉缺件：{why}")
    # ② 只回掩码：源码里不许出现把值打出来的写法
    if re.search(r"print\(.*(token|val)\b", src):
        problems.append("源码里出现直接打印 token/值 ⇒ 只许掩码")
    # ③ 三臂在册
    if len(ARMS) != 3:
        problems.append(f"臂数 {len(ARMS)} ≠ 3（主人令：装 3 个轮询）")
    # ④ 私有地址必须真被拒（真跑一次守卫，不是看代码）
    #    ⚠️ 期望值要分两类：**该拒的必须拒**，**白名单内的必须放** ——
    #       第一版我把白名单那条也当成"漏放"，把**正确行为**判成了红（自己给自己造假红）。
    ok1, _ = _guard("http://127.0.0.1/x")                      # 非 https ⇒ 拒
    ok2, _ = _guard("https://localhost/x")                     # 环回 ⇒ 拒
    ok3, _ = _guard("https://10.0.0.5/x")                      # 私有 ⇒ 拒
    ok4, _ = _guard("https://api-inference.huggingface.co/models/x")   # 白名单 ⇒ **放**
    ok5, _ = _guard("https://evil.example.com/x")              # 野主机 ⇒ 拒
    if any((ok1, ok2, ok3, ok5)) or not ok4:
        problems.append(f"守卫口径不对：http环回={ok1} localhost={ok2} 内网={ok3} "
                        f"白名单={ok4}（应为 True）野主机={ok5}")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"arms": len(ARMS), "arms_present": sum(1 for a in _arm_state() if a["present"]),
                       "models": len(MODELS), "models_verified": sum(1 for m in MODELS if m["verified"])},
            "_口径": "硬钉齐 · 只回掩码 · 3 臂 · **守卫真跑**（私有/环回/野主机必须全拒）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "hf_voice", "tentacle": "hf_voice",
            "entry": "run_task('hf_voice', {...})",
            "ops": ["status", "arms", "models", "sing", "rotate", "verify", "where"],
            "why": "本机零算力跑不动歌声合成（语音中枢 v2.0 实测）⇒ 真唱走云；这一位是那条走廊",
            "arms": [a["id"] for a in ARMS],
            "gates": {"sing": "external_llm（+ out= 指仓外时另过 filesystem_write）"},
            "egress_pins": {"scheme": "https only", "hosts": sorted(_ALLOWED_HOSTS),
                            "reject": "私有/环回/保留 + 重定向"},
            "files": {"台账": str(_LEDGER.relative_to(_ROOT)),
                      "落盘位": str(_OUT.relative_to(_ROOT))}}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("status", status), ("arms", arms), ("models", models), ("sing", sing),
                     ("rotate", rotate), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（status/arms/models/sing/rotate/verify/where）"}


if __name__ == "__main__":
    # ── 给主人的命令行入口（免引号地狱）────────────────────────────────────
    # 血账（2026-09-28）：我先给主人两条命令，结果 ① 没写清要 cd 到仓库根（他站在 C:\Users\ADMIN
    #   ⇒ ModuleNotFoundError）② 把 `run_task(...)` 这种 Python 代码当成能直接粘进 PowerShell 的命令
    #   （PowerShell 当场解析报错）。⇒ 现在给**真命令**：本文件 + 仓库根的 `hf-voice.cmd` 包一层，
    #   主人只要 `.\hf-voice.cmd status`（在仓内）或双击，中文文本也不再需要转义。
    import argparse
    ap = argparse.ArgumentParser(description="Hugging Face 歌声/语音（3 臂轮询）—— 给主人的命令行")
    ap.add_argument("cmd", nargs="?", default="status",
                    choices=["status", "arms", "models", "sing", "rotate", "verify", "where"])
    ap.add_argument("--text", default="", help="要念/要唱的文本（sing 用）")
    ap.add_argument("--model", default="facebook/mms-tts-zho", help="候选模型（见 models）")
    ap.add_argument("--out", default="", help="落盘路径（默认 state/hf_voice_out/）")
    ap.add_argument("--arm", default="", help="rotate 用：hf-1 / hf-2 / hf-3")
    ap.add_argument("--action", default="", help="rotate 用：disable / enable")
    a = ap.parse_args()
    # 控制台显示：强制 UTF-8 输出（否则中文在 GBK 控制台里是乱码 —— 实测踩过）
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass
    if a.cmd == "sing":
        res = sing(text=a.text, model=a.model, out=a.out)
    elif a.cmd == "rotate":
        res = rotate(arm=a.arm, action=a.action)
    else:
        res = run_op(a.cmd)
    print(json.dumps(res, ensure_ascii=False, indent=1))       # noqa: T201
    raise SystemExit(0 if res.get("ok") else 1)
