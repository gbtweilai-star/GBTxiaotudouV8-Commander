# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 方向语义判别层（Owner 2026-09-19）。

为什么单独立这一层：触手意图覆盖率的留出集里，剩下 5 条全是**方向歧义** ——
  「把粘贴板里的东西念出来」该走 read，「存进剪贴板」该走 write；
  「把这段录成帧流」该走 record，「播一下帧流」该走 replay。
这四个词（读/拷、录/放）**字形相近、语义相反**，靠补词永远补不完，
因为问题不在词表，在**语法**：谁说、把什么、往哪去。

所以这里把"词形问题"升级成"方向问题"：
  ① 提动词（读类 / 写类 / 录类 / 放类）
  ② 提介词与走向（从…出来=读入；把…拷到…=写出；存进/写进=写出）
  ③ 规则判定方向；**判不出就返回 None**，不硬猜（判不出时上层不做任何偏置）。

输出是**数据不是指令**：上层（bridge.route_method）拿它做偏置，最终仍要过门禁与审计。
"""
from __future__ import annotations

READ_VERBS = ("读", "念", "看", "取", "查", "瞅", "瞄", "提取", "念出", "读出")
WRITE_VERBS = ("拷", "复制", "存", "写", "塞", "粘贴", "灌", "抄")
RECORD_VERBS = ("录", "拍", "录制", "录屏", "存成")
REPLAY_VERBS = ("回放", "重放", "播", "播放", "放一下", "放出来")

# 走向标记
TO_TARGET = ("到", "进", "入", "进去", "过去", "至")   # 把 X 弄到 Y ⇒ 写出
FROM_SOURCE = ("从", "出来", "念出", "读出", "取出来")  # 从 X 拿出来 ⇒ 读入


def analyze(text: str) -> dict:
    """判方向。返回 {direction, read, write, record, replay, to, from, why}。

    direction ∈ read | write | record | replay | None（None = 判不出，上层不偏置）。
    """
    t = str(text or "")
    if not t:
        return {"direction": None, "why": "空输入"}
    # ⚠️ 名词里的字不算动词：`拷贝板 / 粘贴板 / 剪贴板` 里的"拷/粘贴"是名词的一部分，
    # 早先「看看拷贝板有什么」被判成写方向（read 看 vs write 拷 打平 → 判不出），
    # 留出集实测踩到。先把这些名词挖掉再提动词 —— 这是语法层的活，不是词表的活。
    t_probe = t
    for noun in ("拷贝板", "粘贴板", "剪贴板"):
        t_probe = t_probe.replace(noun, " ")
    read = [w for w in READ_VERBS if w in t_probe]
    write = [w for w in WRITE_VERBS if w in t_probe]
    rec = [w for w in RECORD_VERBS if w in t]
    rep = [w for w in REPLAY_VERBS if w in t]
    to = [w for w in TO_TARGET if w in t]
    frm = [w for w in FROM_SOURCE if w in t]

    # 规则 1：录/放 两族独立判定，谁强是谁
    if len(rep) > len(rec):
        return {"direction": "replay", "record": rec, "replay": rep, "why": "放类动词更强"}
    if len(rec) > len(rep):
        return {"direction": "record", "record": rec, "replay": rep, "why": "录类动词更强"}

    # 规则 2：读/写 两族。走向标记可以逆转动词字面
    #   「把这段塞进粘贴板」→ write 动词 + 到/进 ⇒ write
    #   「从粘贴板念出来」  → read 动词 + 出来   ⇒ read
    score_read = len(read) + (2 if (frm and not to) else 0)
    score_write = len(write) + (2 if (to and not frm) else 0)
    if score_read > score_write:
        return {"direction": "read", "read": read, "write": write, "to": to, "from": frm,
                "why": "读类占优"}
    if score_write > score_read:
        return {"direction": "write", "read": read, "write": write, "to": to, "from": frm,
                "why": "写类占优"}
    if rec or rep or read or write:
        return {"direction": None, "record": rec, "replay": rep,
                "read": read, "write": write, "to": to, "from": frm,
                "why": "两族打平且无走向标记 ⇒ 不猜"}
    return {"direction": None, "why": "句中没有方向动词"}


def bias(direction: str) -> dict:
    """方向 → 该族方法名（用于给候选加偏置）。不猜方向时返回空表。"""
    table = {
        "read":   ("clipboard_read", "read_text", "read_console", "read_text_fast", "read_region_text"),
        "write":  ("clipboard_copy", "copy", "cut", "type", "paste", "type_to_field",
                   "type_to_window", "clipboard_write"),
        "record": ("vision_stream_record",),
        "replay": ("vision_stream_replay",),
    }
    return table.get(str(direction or ""), ())
