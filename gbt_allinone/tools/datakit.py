# -*- coding: utf-8 -*-
"""`datakit` · 本地数据工具（**只读**：结果从返回里给，不落盘）

════════════════════════════════════════════════════════════════════════
为什么这批工具**不写盘**（这是设计决定，不是没做完）
════════════════════════════════════════════════════════════════════════
主人发来一整套外部工具目录（HTML→Markdown / HTML→Excel / Excel→JSON / JSON 美化 / CSV 合并…），
说「给她加上这些能力」。我把它分三批：A 本地零成本 · B 出网付费（要授权）· C 缺依赖。

A 批要做成**能力位**，就绕不开仓里那条红线：
  · `policy.py` 是**安全文件**，**AI 无权改**；
  · 一个"会写盘"的新能力位，若 policy 里**没有对应分支** ⇒ 它就是**绕过门**（写盘不受任何闸管）。
⇒ 所以 A 批一律做成**纯只读**：输入是文本/字节，输出**从返回里给**（调用方想存就自己存）。
  作用域天然为空，**不需要改 policy**，也不制造任何"看不见的写口"。

将来若要"落盘版"，那必须由**主人**在 `policy.py` 里加分支（他自己改、或明确授权），
不是我在工具里偷偷加个 `path=` 参数了事。

用法（同一能力位，op 分派）：
    run(op="html2md",    html="<h1>hi</h1>")      -> {"ok": True, "text": "# hi"}
    run(op="html2xlsx",  html="<table>…</table>") -> {"ok": True, "sheets": {...}}   # 只回结构，不落文件
    run(op="xlsx2json",  data=<bytes>, name="a.xlsx") -> {"ok": True, "json": [...]}
    run(op="jsonfmt",    text='{"b":1,"a":2}')    -> {"ok": True, "text": "{\n  \"a\": 2,\n  \"b\": 1\n}"}
    run(op="csvmerge",   texts=["a,b\\n1,2", "a,b\\n3,4"]) -> {"ok": True, "text": "a,b\\n1,2\\n3,4"}
    run(op="tools")                                -> 列出这一族有哪些 op、各要什么入参
"""
from __future__ import annotations

import csv
import io
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OPS = ("html2md", "html2xlsx", "xlsx2json", "jsonfmt", "csvmerge", "tools")


def _need(**kw):
    """必填入参检查 —— 缺了就**如实说缺什么**，不猜、不用空值糊过去。"""
    miss = [k for k, v in kw.items() if v in (None, "", [], {})]
    if miss:
        return {"ok": False, "error": "必填为空：%s" % "、".join(miss), "need": miss}
    return None


def html2md(html: str = "") -> dict:
    bad = _need(html=html)
    if bad:
        return bad
    try:
        from markdownify import markdownify
    except ImportError as e:                                  # noqa: BLE001
        return {"ok": False, "error": "缺依赖 markdownify：%s" % e}
    md = markdownify(html, heading_style="ATX").strip()
    return {"ok": True, "text": md, "chars": len(md), "readonly": True}


def html2xlsx(html: str = "") -> dict:
    """HTML 表格 → **表结构**（不落 xlsx 文件；落盘要主人给 policy 分支）。"""
    bad = _need(html=html)
    if bad:
        return bad
    try:
        import pandas as pd
    except ImportError as e:                                  # noqa: BLE001
        return {"ok": False, "error": "缺依赖 pandas：%s" % e}
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError:
        return {"ok": False, "error": "这段 HTML 里没有可解析的 <table>"}
    except ImportError as e:                                  # read_html 要 lxml/html5lib
        return {"ok": False, "error": "read_html 缺解析器（lxml/html5lib/bs4）：%s" % e}
    sheets = {"sheet%d" % (i + 1): {"columns": [str(c) for c in t.columns],
                                    "rows": t.astype(str).values.tolist()}
              for i, t in enumerate(tables)}
    return {"ok": True, "tables": len(tables), "sheets": sheets, "readonly": True,
            "note": "只回表结构；**不落盘**（落盘版要主人在 policy.py 里加分支）"}


def xlsx2json(data=None, data_b64: str = "", name: str = "book.xlsx") -> dict:
    """xlsx → JSON。**两条入参路都留**（按入参自动分）：

    · `data_b64`：**base64 文本** —— 走**万能插的门**时只能用它，因为门上的 payload 是 JSON，
      **传不了原始字节**（第 55 轮实测：直接传 bytes 会撞 `TypeError: a bytes-like object is required`）。
    · `data`：**原始字节** —— 进程内直接调用时用它，省一次 base64 编解码。
    """
    if data_b64:
        import base64
        try:
            data = base64.b64decode(str(data_b64), validate=True)
        except Exception as e:                                # noqa: BLE001
            return {"ok": False, "error": "data_b64 不是合法 base64：%s" % str(e)[:100]}
    bad = _need(data=data)
    if bad:
        bad["hint"] = "门内请用 data_b64（base64 文本）；进程内可直接传 data（字节）"
        return bad
    try:
        import pandas as pd
    except ImportError as e:                                  # noqa: BLE001
        return {"ok": False, "error": "缺依赖 pandas：%s" % e}
    try:
        book = pd.read_excel(io.BytesIO(data), sheet_name=None)
    except Exception as e:                                    # noqa: BLE001
        return {"ok": False, "error": "读不动这个 xlsx：%s: %s" % (type(e).__name__, str(e)[:120])}
    out = {sheet: df.astype(str).to_dict(orient="records") for sheet, df in book.items()}
    return {"ok": True, "file": name, "sheets": list(out), "json": out, "readonly": True}


def jsonfmt(text: str = "", sort_keys: bool = True) -> dict:
    bad = _need(text=text)
    if bad:
        return bad
    try:
        obj = json.loads(text)
    except Exception as e:                                    # noqa: BLE001
        return {"ok": False, "error": "不是合法 JSON：%s" % str(e)[:120]}
    pretty = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=bool(sort_keys))
    return {"ok": True, "text": pretty,
            "kind": type(obj).__name__,
            "keys": sorted(obj)[:12] if isinstance(obj, dict) else None,
            "readonly": True}


def csvmerge(texts=None, dedupe_header: bool = True) -> dict:
    """多段 CSV 文本**合并成一段文本**（同一表头只留一次；不落盘）。"""
    bad = _need(texts=texts)
    if bad:
        return bad
    if not isinstance(texts, (list, tuple)):
        return {"ok": False, "error": "texts 要是数组（每项一段 CSV 文本）"}
    header, rows = None, []
    for i, t in enumerate(texts, 1):
        rd = list(csv.reader(io.StringIO(str(t))))
        rd = [r for r in rd if any((c or "").strip() for c in r)]
        if not rd:
            continue
        if header is None:
            header = rd[0]
            rows.extend(rd[1:])
        else:
            body = rd[1:] if (dedupe_header and rd[0] == header) else rd
            rows.extend(body)
    if header is None:
        return {"ok": False, "error": "没有可合并的内容（每段都是空的）"}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return {"ok": True, "text": buf.getvalue(), "rows": len(rows),
            "cols": len(header), "parts": len(texts), "readonly": True}


def run(op: str = "tools", **kw) -> dict:
    """唯一入口：op 分派。**所有 op 都只读**（结果从返回里给，不落盘）。"""
    if op == "tools":
        return {"ok": True, "ops": list(OPS), "readonly": True,
                "note": "本族**全部只读**：不落盘、不出网、不改任何文件",
                "params": {"html2md": ["html"], "html2xlsx": ["html"],
                           "xlsx2json": ["data_b64(base64 文本·门内用) 或 data(字节·进程内用)", "name"],
                           "jsonfmt": ["text", "sort_keys"],
                           "csvmerge": ["texts(数组)"]}}
    if op == "html2md":
        return html2md(kw.get("html", ""))
    if op == "html2xlsx":
        return html2xlsx(kw.get("html", ""))
    if op == "xlsx2json":
        return xlsx2json(kw.get("data"), kw.get("data_b64", ""), kw.get("name", "book.xlsx"))
    if op == "jsonfmt":
        return jsonfmt(kw.get("text", ""), kw.get("sort_keys", True))
    if op == "csvmerge":
        return csvmerge(kw.get("texts"), kw.get("dedupe_header", True))
    return {"ok": False, "error": "不认的 op %r（认这些：%s）" % (op, "、".join(OPS))}


if __name__ == "__main__":
    # 自测：每条 op 都拿真样例跑一遍（这就是"能跑"的证据，不是"我写了"）
    print(json.dumps(run("tools"), ensure_ascii=False, indent=1))
    print(json.dumps(run("html2md", html="<h1>标题</h1><p>正文 <b>粗</b></p>"), ensure_ascii=False)[:200])
    print(json.dumps(run("jsonfmt", text='{"b":1,"a":[2,3]}'), ensure_ascii=False)[:200])
    print(json.dumps(run("csvmerge", texts=["a,b\n1,2\n", "a,b\n3,4\n"]), ensure_ascii=False)[:200])
    print(json.dumps(run("html2xlsx", html="<table><tr><th>x</th></tr><tr><td>1</td></tr></table>"),
                     ensure_ascii=False)[:240])
