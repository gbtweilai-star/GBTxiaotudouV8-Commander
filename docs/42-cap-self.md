# 42 · 能力自知 `cap_self` —— 她为什么会"连自己都不知道"

> 主人 2026-10-31：「还有所有原生能力她有时候连自己都不知道，这让我更纳闷」

---

## 一、病根：她的"自知"来自三份会漂移的副本

| 源 | 性质 | 漂移方式 |
|---|---|---|
| `caps_registry.BENIGN_CAPS` | **真源**（现读） | 加能力位时只改这里 |
| `data/capabilities.json` | **快照**（导出时点拷贝） | 忘了重导就落后（实测落后过 body_* 七位、commander、pulse_core） |
| `docs/`、README 手写数字 | 最不可靠 | 同一仓里出现过 295 / 341 / 348 / 350 四种说法 |

三份不一致时，**她嘴里说的和手里有的就不是一回事**。更麻烦的是：
这种不一致**没有任何东西会变红**，所以能一直存在 —— 这就是"有时候连自己都不知道"。

## 二、解药：一条自知能力位，三源对账

新增 **`cap_self`**（`gbt_allinone/tentacle/cap_self.py`），全只读、零作用域：

| op | 回答什么 | 关键口径 |
|---|---|---|
| `has <name>` | 有没有这一位 | **三种"没有"必须分开说**：没登记 / 登记了没分派 / 要票 |
| `list [domain]` | 按域枚举 | 读**真源**，不读快照 |
| `ask <意图>` | "我有哪些能做这个" | 走本机召回，不调模型、离线可用 |
| `brief` | 压成能进 2048 ctx 的自述 | 32 域分布 + 要票数，**条数现算不写死** |
| `verify` | **三源对账** | 快照 vs 真源、分派 vs 注册、desc 完整性、policy 可求值；任一漂移即红 + 给差集与修法 |

五处齐：注册表 `cap_self` · `api.py` 分派 · 门（零作用域）· 审计（走唯一门）· 测试
`tests/test_cap_self.py`（含**负对照**：喂一份假快照，`verify` 必须红）。

## 三、当前读数（2026-11-01 实测）

```json
{"ok": true,
 "counts": {"registry": 353, "snapshot": 353, "dispatched": 353},
 "checks": [
   {"name": "快照 ≤ 真源", "ok": true, "extra": []},
   {"name": "快照 ⊇ 真源", "ok": true, "missing": []},
   {"name": "每一位都有门上的分派", "ok": true, "missing": []},
   {"name": "每一位都有 desc", "ok": true, "missing": []},
   {"name": "每一位都能过 policy.evaluate", "ok": true, "bad": []}],
 "failed": []}
```

`has` 的三种回答（实测）：

```
cap_self has pulse_core        → has=true  · dispatched=true · 零作用域
cap_self has does_not_exist    → has=false · why="注册表里没有这一位" · did_you_mean=[]
```

`brief`（她自己的自述，可整段塞进上下文）：

> 我是 GBT小土豆V8，原生能力位 353 个，分布：automation2 · brain2 · collab2 · comms1 · creation54 ·
> data12 · desktop2 · device9 · devour5 · engine10 · finance4 · framework1 · image_video1 · infra2 ·
> integration7 · life1 · llm41 · longrun4 · mind20 · pipeline18 · project2 · recon17 · security29 ·
> social2 · system52 · tentacle20 · tools9 · video15 · vision5 · voice4。其中要过门（人工授权）的 41 个，
> 其余零作用域。要查具体一位：cap_self has <名字>；要按意图找：cap_self ask <一句话>。

## 四、和上一条（`pulse_core`）的关系

- `pulse_core` 管**怎么做**（脉冲/量化/按需/直达四条机制）；
- `cap_self` 管**知道什么**（我有哪些位、哪条漂了）；
- 两者都遵守同一条纪律：**只写进 docs 的，按未实现对待**。

`ask` 与 `pulse_core route` 的分工：`ask` 只做召回（候选 + 是否要票），
`pulse_core route` 才做判决（本机权重在候选里挑）。召回/判决分开，谁出错一眼能定位。

## 五、复现

```powershell
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g,json;print(json.dumps(g.run_task('cap_self',{'op':'verify'}),ensure_ascii=False)[:600])"
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g,json;print(json.dumps(g.run_task('cap_self',{'op':'brief'}),ensure_ascii=False))"
python tests/test_cap_self.py
```

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
