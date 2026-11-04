"""op 调用的**参数过滤** —— 只把目标函数真正接受的参数传进去。

## 病根（2026-11-04 全开实测抓出，9 个 real_bug 里 5 个同源）

`run_task(kind, {"text": "..."})` 是面板/冒烟/大脑都爱用的通用形状，但很多 op 函数
**一个参数都不收**：

```python
def sources() -> dict:      # tools/case_mine.py:228
def beliefs(min_conf=0.0):  # tools/belief_forge.py:143
```

而分派链是 `api.run_task → 模块.run_op(op, **payload) → return fn(**params)`，
一把透传 ⇒

```plain
TypeError: sources() got an unexpected keyword argument 'text'
```

**看着像"这个能力坏了"，其实是"喂了它不认识的东西"。** 实测全开 426 位时，
这一种写法在 58 个 tools 模块里是同一个坑，一次拖垮 5 个位
（creation_camp / db_probe / belief_forge / case_mine / long_run_supervisor）。

## 为什么不用 try/except 吞掉

吞异常会把「**真的缺参数**」也变成静默成功 —— 那比报错更坏（假绿）。
所以这里是**调用前**按签名过滤：不认识的参数不传，认识的照传，缺必填照样由函数自己报缺。

## 为什么不改 api.py 一层了事

`api.py` 那一层还不知道最终落到哪个函数（`run_op` 内部再分派）。
硬在 api 层做，就得靠捕获异常重试 —— 万一第一次已经部分执行，重试会重复副作用。
按签名过滤是**调用前**的确定性判断，没有重试，也没有副作用。
"""
from __future__ import annotations

import inspect


def pick(fn, params: dict) -> dict:
    """返回 fn **真正能接受**的参数字典。

    - fn 有 `**kwargs` ⇒ 原样全传（它自己愿意接）。
    - 否则只留 `POSITIONAL_OR_KEYWORD` / `KEYWORD_ONLY` 里出现过的名字。
    - 签名读不出来（C 扩展、functools 包装等）⇒ 原样全传，不擅自丢参数。
    """
    src = dict(params or {})
    if not src:
        return {}
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return src
    params_meta = sig.parameters.values()
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params_meta):
        return src
    allowed = {p.name for p in params_meta
               if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                             inspect.Parameter.KEYWORD_ONLY)}
    return {k: v for k, v in src.items() if k in allowed}


def call(fn, params: dict):
    """按签名过滤后调用。被丢掉的参数**不静默**：如需查看请用 call_verbose。"""
    return fn(**pick(fn, params))


def call_verbose(fn, params: dict):
    """同 `call`，但额外返回被丢掉的参数名（排障用）。"""
    src = dict(params or {})
    kept = pick(fn, src)
    dropped = [k for k in src if k not in kept]
    return fn(**kept), dropped


def where() -> dict:
    """自述：这个工具怎么用、当前版口径。"""
    return {"ok": True, "module": "gbt_allinone.tools._opcall",
            "ops": ["pick", "call", "call_verbose", "where"],
            "rule": "按 inspect.signature 过滤；有 **kwargs 则全传；签名读不出则全传",
            "why": "run_task 的通用 payload（如 {'text': ...}）不该把不收参数的 op 打成 TypeError"}
