"""按比例最小化后，能不能塞进"云插件"？ —— 用**真实文件体积**对着**真实上限**算。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它回答什么问题
主人说「把他们按照比例最小化模块部署到云插件然后进行拼接合成」。这句话里
「按比例最小化」（= 量化）是**真技术**，但**能小到多少有下界**：
下界由**参数量**决定，不由压缩技巧决定。这个工具就是把这件事**算出来**，
而不是靠感觉说"能/不能"。

## 口径（写死在这里，别的文件引用它）
- 体积取**真源**：HuggingFace API 的 `?blobs=true`（每条 sibling 的字节数）。取不到 ⇒ 写**未读到**，不拿 0 顶。
- 上限取**官方文档**（`developers.cloudflare.com/workers/platform/limits/`，现读日期写进输出）：
  · **Memory per isolate = 128 MB**（含 JS 堆与 Wasm 分配）
  · **Worker size (uncompressed) = 64 MiB**（**没有**压缩后上限；只算未压缩包体）
  · CPU time：Free 10 ms / Paid 5 min（默认 30 s）
  · 单个 Static Asset = 25 MiB
- **判定只用算术**：`文件字节 > 上限字节` ⇒ 装不下，并给出**超了 X 倍**。
- 🔴 **1 bit/参数 的假想档也一起算**：这是**任何量化都不可能越过**的地板 ——
  地板都装不下，就不必再讨论"再压一点"。

用法：
  python tools/codex-scripts/min-quant-fit.py show [--json]
  python tools/codex-scripts/min-quant-fit.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UA = "gbt-min-quant-fit/1.0 (+local)"
MIB = 1024 * 1024
GIB = 1024 * MIB

# ── 上限（真源：Cloudflare Workers Limits 官方文档，2026-09-05 版；现读 2026-09-25）──
LIMITS_DOC = "https://developers.cloudflare.com/workers/platform/limits/"
LIMITS_READ_AT = "2026-09-25"
ENVELOPES = (
    {"name": "Worker 单 isolate 内存", "bytes": 128 * MIB, "kind": "worker",
     "source": "官方 limits：Memory per isolate = 128 MB"},
    {"name": "Worker 体积（未压缩）", "bytes": 64 * MIB, "kind": "worker",
     "source": "官方 limits：Worker size (uncompressed) = 64 MiB（无压缩上限）"},
    {"name": "单个 Static Asset", "bytes": 25 * MIB, "kind": "worker",
     "source": "官方 limits：Individual Static Asset file size = 25 MiB"},
    {"name": "请求体上限（Free/Pro）", "bytes": 100 * MIB, "kind": "worker",
     "source": "官方 limits：Free/Pro 100 MB"},
)

# 候选真件（**逐条现读 HF**；有的带"无审查/abliterated"标签，名字照录不改）
REPOS = (
    {"repo": "unsloth/Qwen-Image-2.1-GGUF", "what": "图像模型（原版）· 含最小档 Q2_K"},
    {"repo": "abenzerps/Qwen-Image-2.1-Uncensored-GGUF", "what": "图像模型（无审查）· 含 文本编码器 与 VAE"},
    {"repo": "pottokao/Qwen-Image-2.1-Text-Encoder-Heretic-GGUF", "what": "文本编码器（abliterated/heretic）"},
    {"repo": "unsloth/Qwen3.8-27B-GGUF", "what": "文本大脑（27B）· 量 27 档"},
)


def http_json(url: str, timeout: float = 25.0) -> dict:
    """只读拉一次 HF API。取不到 ⇒ 如实报未读到。"""
    req = urllib.request.Request(url, headers={"user-agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "body": json.loads(r.read().decode("utf-8", "replace"))}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "err": "HTTP %s" % e.code}
    except Exception as e:
        return {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}


def repo_files(repo: str) -> dict:
    """**一次现读**：返回 {文件名: 字节数}。取不到 ⇒ reading=未读到（不是 0 条）。"""
    r = http_json("https://huggingface.co/api/models/%s?blobs=true" % repo)
    if not r.get("ok"):
        return {"repo": repo, "reading": "未读到", "why": r.get("err"), "files": {}}
    body = r["body"] or {}
    files = {}
    for sib in body.get("siblings") or []:
        n = sib.get("rfilename")
        sz = sib.get("size")
        if isinstance(n, str) and isinstance(sz, int):
            files[n] = sz
    gguf = body.get("gguf") or {}
    return {
        "repo": repo,
        "reading": "已读到" if files else "未读到",
        "files": files,
        "params": gguf.get("total") if isinstance(gguf.get("total"), int) else None,
        "architecture": gguf.get("architecture"),
    }


# 这些后缀对，但**不是模型权重**：imatrix 是标定用的统计表（几十 MB），
#    拿它当"最小量化档"会得出"装得下"的**假绿**（本轮当场踩到：27B 仓库里
#    `imatrix_unsloth.gguf` 10 MB 被选成最小档 ⇒ 报"装得下"）。判据必须排除它们。
NOT_WEIGHTS = ("imatrix", "calibration", "calib", "params", "config", "tokenizer")


def is_weight(fname: str) -> bool:
    """只算**真权重件**：.gguf / .safetensors，且不是标定/配置这类同名附属件。"""
    low = fname.lower()
    base = low.rsplit("/", 1)[-1]
    if not (low.endswith(".gguf") or low.endswith(".safetensors")):
        return False
    return not any(tok in base for tok in NOT_WEIGHTS)


def judge(size_bytes: int | None, env: dict) -> dict:
    """**纯函数**：一个文件对一个上限 ⇒ 装得下/装不下 + 超几倍。"""
    if size_bytes is None:
        return {"过": False, "读数": "未读到（文件体积取不到）"}
    if size_bytes <= env["bytes"]:
        return {"过": True, "倍数": round(env["bytes"] / max(size_bytes, 1), 2),
                "读数": "装得下（上限是它的 %.1f 倍）" % (env["bytes"] / max(size_bytes, 1))}
    return {"过": False, "倍数": round(size_bytes / env["bytes"], 1),
            "读数": "装不下：超 %.1f 倍" % (size_bytes / env["bytes"])}


def one_bit_floor(params: int | None) -> dict:
    """🔴 **任何量化都越不过的地板**：1 bit/参数。地板都装不下 ⇒ 不必再谈"再压一点"。"""
    if not params:
        return {"params": None, "reading": "未读到（拿不到参数量）"}
    floor = params / 8.0                      # 1 bit / 参数
    env = ENVELOPES[0]
    return {
        "params": params,
        "1bit_bytes": int(floor),
        "1bit_gib": round(floor / GIB, 2),
        "isolate_limit_mib": 128,
        "verdict": judge(int(floor), env),
        "口径": "1 bit/参数 是量化的**理论地板**；连它都超 128 MB ⇒ 任何真实量化档都不可能装进 Worker。",
    }


def survey(as_json: bool) -> int:
    rows = []
    for spec in REPOS:
        got = repo_files(spec["repo"])
        weights = {k: v for k, v in (got.get("files") or {}).items() if is_weight(k)}
        if not weights:
            rows.append({**spec, "reading": got.get("reading"), "why": got.get("why"), "smallest": None, "floor": one_bit_floor(got.get("params"))})
            continue
        name, size = min(weights.items(), key=lambda kv: kv[1])
        rows.append({
            **spec,
            "reading": "已读到",
            "files_weight": len(weights),
            "smallest": {"file": name, "bytes": size, "gib": round(size / GIB, 2)},
            "smallest_vs_isolate": judge(size, ENVELOPES[0]),
            "smallest_vs_bundle": judge(size, ENVELOPES[1]),
            "floor": one_bit_floor(got.get("params")),
            "architecture": got.get("architecture"),
        })
    out = {
        "上限口径": {"来源": LIMITS_DOC, "现读日期": LIMITS_READ_AT,
                 "档位": [{"name": e["name"], "mib": e["bytes"] // MIB, "source": e["source"]} for e in ENVELOPES]},
        "逐件": rows,
        "结论口径": "只看算术：**文件字节 vs 上限字节**。装不下就写超几倍，不许含糊。",
    }
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    print("按比例最小化 ⇒ 能不能塞进云插件？（真体积 × 真上限）")
    print("  上限来源：%s（现读 %s）" % (LIMITS_DOC, LIMITS_READ_AT))
    for e in ENVELOPES[:2]:
        print("    · %s = %d MiB" % (e["name"], e["bytes"] // MIB))
    print("")
    for r in rows:
        print("── %s（%s）" % (r["repo"], r["what"]))
        if not r.get("smallest"):
            print("   未读到（%s）" % r.get("why"))
        else:
            s = r["smallest"]
            print("   最小权重档：%s = %.2f GiB" % (s["file"], s["gib"]))
            print("   对 isolate 内存：%s" % r["smallest_vs_isolate"]["读数"])
            print("   对 64 MiB 包体：%s" % r["smallest_vs_bundle"]["读数"])
        f = r.get("floor") or {}
        if f.get("params"):
            print("   🔴 1 bit/参数地板：%d 参数 ⇒ %.2f GiB  ⇒ 对 isolate：%s"
                  % (f["params"], f["1bit_gib"], f["verdict"]["读数"]))
    print("")
    print("  口径：%s" % out["结论口径"])
    return 0


def selftest() -> int:
    ok = 0
    total = 0
    fails = []

    def ck(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
        else:
            fails.append("%s :: %s" % (name, detail))

    # 上限表：必须有、且 isolate 就是 128 MiB（官方文档现读）
    ck("正控·上限表非空", len(ENVELOPES) >= 4, str(len(ENVELOPES)))
    ck("正控·isolate 内存 = 128 MiB（官方口径）", ENVELOPES[0]["bytes"] == 128 * MIB, str(ENVELOPES[0]["bytes"]))
    ck("正控·包体 = 64 MiB 未压缩", ENVELOPES[1]["bytes"] == 64 * MIB, str(ENVELOPES[1]["bytes"]))

    # judge：纯函数三态
    ck("正控·1 MiB 对 128 MiB ⇒ 装得下", judge(1 * MIB, ENVELOPES[0])["过"] is True, str(judge(1 * MIB, ENVELOPES[0])))
    r_over = judge(4 * GIB, ENVELOPES[0])
    ck("负控·4 GiB 对 128 MiB ⇒ 装不下且给出倍数", r_over["过"] is False and r_over["倍数"] >= 30, str(r_over))
    ck("负控·体积取不到 ⇒ 未读到（不许当 0 通过）", judge(None, ENVELOPES[0])["过"] is False and "未读到" in judge(None, ENVELOPES[0])["读数"], str(judge(None, ENVELOPES[0])))

    # 1 bit 地板：7.1e9 参数 ⇒ 0.83 GiB ⇒ 对 128 MB 仍超
    floor = one_bit_floor(7115124736)
    ck("正控·1bit 地板算得出字节", floor["1bit_bytes"] > 0 and floor["verdict"]["过"] is False, str(floor["1bit_gib"]))
    ck("负控·地板超 128 MB ⇒ 必须点名超几倍", "装不下" in floor["verdict"]["读数"], floor["verdict"]["读数"])
    ck("负控·参数量取不到 ⇒ 未读到", one_bit_floor(None)["reading"].startswith("未读到"), one_bit_floor(None)["reading"])

    # 只算权重件：工作流 json / 预览图不算
    ck("正控·.gguf/.safetensors 算权重", is_weight("a/b.gguf") and is_weight("x.safetensors"), "is_weight")
    ck("负控·工作流 json 与 png 不算权重", not is_weight("Qwen_Image_2.1_T2I.json") and not is_weight("assets/a.png"), "is_weight")
    ck("负控·imatrix 标定件不算权重（假绿来源）", not is_weight("imatrix_unsloth.gguf") and not is_weight("UD-imatrix.gguf"), "is_weight")

    # 真源取不到 ⇒ 未读到（打一个肯定不存在的仓库）
    bad = repo_files("__definitely_not_a_real_repo__/__nope__")
    ck("负控·仓库取不到 ⇒ 未读到且 files 空（不许编）", bad["reading"] == "未读到" and bad["files"] == {}, str(bad.get("why"))[:60])

    print("min-quant-fit selftest：%d/%d" % (ok, total))
    for f in fails:
        print("  ✗ " + f)
    return 0 if ok == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="按比例最小化后能否塞进云插件（真体积 × 真上限）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("--json", action="store_true")
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "show":
        return survey(as_json=a.json)
    if a.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
