# tools/_retired —— 已收编的重复件（2026-10-29）

> **权威件只有一个：`tools/a19_sentinel.py`**（docs/22 指定，写 `state/a19_ready.json` + `/tmp/a19_ready.json`）

## 为什么收编

全量清点时发现 A19 探活件有 **6 套**，其中两套写同一个文件、互相覆盖：

| 文件 | 落点 | 处置 |
|---|---|---|
| `a19_sentinel.py` | `/tmp/a19_ready.json` | ✅ **保留，唯一权威** |
| `a19_wait.py` | `state/a19_caught.json` | 收编 |
| `a19_catch.py` | `state/a19_caught.json` | 收编（与上一条**同路径冲突**） |
| `a19_watch.py` | 无落盘，打一枪就退 | 收编 |
| `a19_watch.sh` | `state/a19_last_state` | 收编 |
| `a19_hunter.py` | `state/a19_caught.json` | 收编（2026-10-29 我自己造的，造之前没先查已有件 —— 记在这里当教训） |

## 收编时抓到的真 bug（已修）

`docs/17` 与 `docs/36` 都把 **`state/a19_ready.json`** 当验收凭据，但 sentinel 只写
`/tmp/a19_ready.json` ⇒ **容器真起来那一刻，文档承诺的那份凭据不会更新**。
已改成双写（`/tmp` 给 `a19_switch` 读 prefill 预算，`state` 给人读）。

## 没并进来的能力（诚实记）

`a19_hunter.py` 有两个 sentinel 没有的能力：① 覆盖网卡地址（App Store 描述原文
「Expose … on your local network」⇒ 服务可能只绑网卡）② 全 65535 口扫 OpenAI 端点。
**这两条目前没有并入 sentinel** —— 留着这个缺口在这里，不假装已经并了。
