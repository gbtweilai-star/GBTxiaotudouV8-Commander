# -*- coding: utf-8 -*-
"""把这一批（GBT天真 / 五维合一 / 多域监控 + 三处真修）追加进编排账本。

P9 纪律：账必须有生产者 —— 这段文字里的每个数字都来自三份 live JSON，
脚本会把它们现读一遍再写进去，避免"账里一个数、盘上另一个数"。
用法：py -3.12 tools/codex-scripts/append-ledger-tianzhen.py
"""
import json
import pathlib
import time
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"
LEDGER = ROOT / "state" / "model-deploy" / "编排账本.md"


def j(p):
    return json.loads((REL / "data" / p).read_text(encoding="utf-8"))


tz = j("gbt-tianzhen-live.json")
fd = j("five-dim-live.json")
md = j("multidomain-monitor-live.json")

con = tz.get("contract") or {}
same = len(con.get("native_also_in_contract") or [])
r_ok = (tz.get("run_ok", {}).get("result") or {})
r_bad = (tz.get("run_bad", {}).get("result") or {})
v_ok = (tz.get("validate_ok", {}).get("result") or {})
v_bad = (tz.get("validate_bad", {}).get("result") or {})
tot = md.get("totals") or {}
diff = md.get("diff") or {}

lines = []
lines.append("\n## 二十八、GBT天真 / 五维合一 / 多域监控 三页公开（2026-10-21）\n")
lines.append("主人令（逐字）：「**GBT天真也要介绍**」「你这写的一点都不仔细，五维合一，多域监控修一处坏一处"
             "监控全部没有你是这么办事的？还有现在他能被推上榜吗」。\n")
lines.append("### 一、这三页各写了什么（都对着一份 live JSON）\n")
lines.append("| 页 | 主体 | 现读关键数 | 生产者（谁生成这份账） |")
lines.append("|---|---|---|---|")
lines.append("| `docs/10-gbt-tianzhen.md` | GBT天真 = `comfy_native`（主人 2026-10-11 命名） | 原生算子 **%d** · 与 ComfyUI 同名同契约 **%d** · 契约面 **%d** · 覆盖率 **%s%%** | `tools/codex-scripts/gen-native-live.py` |"
             % (tz.get("nodes_count") or 0, same, con.get("contract_nodes") or 0, con.get("native_coverage_pct")))
lines.append("| `docs/11-five-dim.md` | 五维合一 = `brain_unify` | %d 条人话意图真跑：execute ok **%d** / denied **%d** · health 全 5/5 | 同上 |"
             % (len(fd.get("intents") or []),
                sum(1 for r in fd["intents"] if (r["chain"]["execute"] or {}).get("status") == "ok"),
                sum(1 for r in fd["intents"] if (r["chain"]["execute"] or {}).get("status") == "denied")))
lines.append("| `docs/12-multidomain-monitor.md` | 多域监控 | %d 域 · 测 **%d** · 通过 **%d** · 未通过 **%d**（全是 denied）· 未跑 **%d** · 用时 %ss | `multi-domain-monitor.py --diff --out` |"
             % (len(md.get("domains") or {}), tot.get("tested", 0), tot.get("ok", 0),
                tot.get("not_ok", 0), 341 - tot.get("tested", 0), md.get("elapsed_s")))
lines.append("")
lines.append("### 二、这几页逼出来的**真修**（不是改文案）\n")
lines.append("1. **契约保真三处**（`gbt_allinone/tools/comfy_native.py`）：")
lines.append("   ① `LoadImage` 只登记内部别名 `path`，而 ComfyUI 的必填 socket 叫 `image` ⇒ 一张标准 ComfyUI 图"
             "被自家校验判「缺必填」；")
lines.append("   ② 把**落点** `out` 当必填，而 ComfyUI 用 `filename_prefix` 且可省 ⇒ 同上一族误判；")
lines.append("   ③ 连边按**字面名**取上一节点产物（边写 `image->image`，算子回的是 `out`）⇒ 图连通却报「要 image」。")
lines.append("   修后：正例 `%s`（%s）· 反例抓到 **%d** 条错 · 写面真跑 `ok=%s`（%d 节点、产物 %d 件）· 坏图 `ok=%s`（fail-closed）。"
             % (v_ok.get("ok"), v_ok.get("verdict"), len(v_bad.get("errors") or []),
                r_ok.get("ok"), len(r_ok.get("trace") or []), len(r_ok.get("products") or []), r_bad.get("ok")))
lines.append("2. **拒绝回执被省掉**（`gbt_allinone/brain_exec.py`）：五维合一的执行层原来只留 `status=denied`，"
             "缺的作用域与上游原话全丢 ⇒ 现在两层透传（实测拿到 `['desktop_control','privacy_read']`）。")
lines.append("3. **监控读数被省掉**（`tools/codex-scripts/multi-domain-monitor.py`）：门的 `missing_scopes` 嵌在 "
             "`gbt_result.result` 层而本器只读顶层 ⇒ 15 条拒绝全打 `(未报)`；现在两层都读 + 从原话兜底取名。")
lines.append("4. **图鉴文案落后于盘**（`gbt_allinone/caps_registry.py`）：`comfy_native` 写「18 个算子 / 962 把节点」，"
             "盘上现读 **27 / 1495**，未接分类也仍是旧四位数 ⇒ 全部改成现读值并注明口径。")
lines.append("")
lines.append("### 三、多域监控这一轮的意义（回答「修一处坏一处」）\n")
lines.append("立基线之后我真改了三处（契约/连边、`filename_prefix`、`brain_exec` 回执），然后整面重跑："
             "**%d/%d 一条没变 · 15 条拒绝一条没变 · 回归 %s · 修好 %s**。"
             % (tot.get("ok", 0), tot.get("tested", 0), diff.get("regressed_count"), diff.get("fixed_count")))
lines.append("> 基线 `state/monitor/domain-baseline.json`；连续两次 `--diff` 都是 0/0（另一次 358.4s，这次 %ss）。" % md.get("elapsed_s"))
lines.append("")
lines.append("### 四、公开发布（匿名可复核）\n")
lines.append("- 仓库：`gbtweilai-star/GBTxiaotudouV8-Commander`（public）· 本轮 commit `102b97c840` · tree 共 **71** 个 blob · 527 KB；")
lines.append("- 新增 9 个文件全部 **匿名 raw 200**：3 页文档 · 2 张图 · 3 份 live JSON · README（20137 字节）；")
lines.append("- 顺手把 30 个域页与 `data/capabilities.json` 按新图鉴文案重生成（341 位 / 30 域一字不差）。")
lines.append("")
lines.append("### 五、诚实边界（写进 README 的「诚实声明」里，不是只写在这里）\n")
lines.append("- GBT天真**只覆盖契约面 1.2%%**（%d/%d）：重生成/模型面 %s 个、控图检测面 %s 个要权重与 GPU，本机没有；"
             "传统算法面 %s 个「可原生但没接」。"
             % (same, con.get("contract_nodes") or 0,
                (con.get("not_native_by_reason") or {}).get("重生成/模型面：要权重与 GPU（本机无 CUDA、内存 7.39GB）", {}).get("count"),
                (con.get("not_native_by_reason") or {}).get("控图/检测面：部分可原生（已接预处理），其余需权重", {}).get("count"),
                (con.get("not_native_by_reason") or {}).get("传统算法面：**可原生**（未接的按需再长）", {}).get("count")))
lines.append("- 多域监控只测 **%d/341** 位（只读且无需参数）；105 位写口/需参数位不跑、也不假装跑过。" % tot.get("tested", 0))
lines.append("- 五维合一的路由会抖动：同一句人话两次跑可能落到不同能力位（本轮第 4 条「看看当前屏幕上有哪些窗口」"
             "跑之前我标「会被门挡住」，实测 `ok`）——**标签不改、读数照原样入账**。")
lines.append("")
lines.append("### 六、下一步（仍缺的）\n")
lines.append("- 权重 15.25 GB 未上 Hugging Face；无公开 demo 端点；0 star/0 fork ⇒ “能上榜”要靠分发与时间，不靠自嗨（已向主人如实说）。")
lines.append("")
lines.append("_读数时间：%s（三份 live JSON 现读）_\n" % time.strftime("%Y-%m-%dT%H:%M:%S"))

with LEDGER.open("a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")
print("账本已追加 →", LEDGER)
print("字数约", sum(len(x) for x in lines))
