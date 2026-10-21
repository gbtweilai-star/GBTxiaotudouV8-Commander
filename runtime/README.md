# 运行时源码（可审阅版）

这里放的是**真源码**，不是示意代码。你可以在 GitHub 上逐行读完"门、授权、审计、注册表、万能插"这五件事是怎么写的。

先跑一次机械自检（零依赖、只读 AST、**不导入引擎、不执行任何能力**）：

```bash
python runtime/static_check.py
```

现读输出（2026-10-21）：

```
PASS  门：run_task 有 2 处定义（原定义 + 包装器） · 行 [2562, 3067]
PASS  门：包装器先快照原定义再包装 · 快照行 3064
PASS  门：包装器调用 _run_task_base · 不是自我递归
PASS  门：契约层三件套齐全 · 信封归一 / 结果校验 / 产出即绑
PASS  作用域门：HUMAN_GATES 覆盖 14 个作用域 · 含 G1/G2/G3 关键项
PASS  作用域门：机制层自保 · filesystem_write 在 MECHANISM_GATES 里
PASS  票据：一次性票集合 · data_export、deploy_force、deploy_publish、owner_control、remote_device
PASS  注册表：条数 341 · machine-readable
PASS  注册表：341 个名字都能在 caps_registry.py 里找到 · 不是手抄的目录

9 过 / 0 不过
```

## 源码地图（哪份文件兑现哪条公开声明）

| 文件 | 现读大小 | 它兑现哪条声明 | 从哪读起 |
|---|---|---|---|
| `gbt_allinone/api.py` | 177 KB | **一切调用只走 `run_task` 这一个门**；信封归一、结果校验、产出即绑 | `def run_task`（文件里有**两处**，先看下面那段说明） |
| `gbt_allinone/security/policy.py` | 67 KB | **写盘 / 花钱 / 出网必须人工授权**；`HUMAN_GATES` 是那张正表 | 搜 `HUMAN_GATES` 与 `MECHANISM_GATES` |
| `gbt_allinone/auth_gate.py` | 23 KB | **票只有主人能发**；时段票 vs 一次性票 | 搜 `ONE_SHOT` |
| `gbt_allinone/caps_registry.py` | 239 KB | **341 位能力**的注册表本体（不是手抄清单） | 搜任一能力位名 |
| `gbt_allinone/omni_plug.py` | 47 KB | **万能插**：六类插座 + 反向调用 | 搜 `socket` / `_ai_call` |
| `gbt_allinone/preflight.py` | 44 KB | 调用前的**预检层**（已知缺口：抛异常时 fail-open，见 `docs/14` §六） | 搜 `def preflight` |
| `gbt_allinone/store.py` | 13 KB | **审计账本**（`audit()`）；只追加 | 搜 `def audit` |
| `gbt_allinone/room_space.py` | 54 KB | 隔离房间：plan → simulate → parity → rehearse → release | 搜 `ENTRY_NAMES` |
| `gbt_allinone/qiankun.py` | 24 KB | 一键部署（必须显式声明落点，否则拒） | 搜 `one_key_deploy` |
| `gbt_allinone/mirror_space.py` | 17 KB | 镜像多维度：shape → rehearse → release | 搜 `def ascend` |
| `gbt_allinone/deployment_rehearsal.py` | 61 KB | 部署排练与晋升 | 搜 `def release` |
| `gbt_allinone/signature.py` | 5 KB | 署名 / 钢印自检 | 搜 `def audit` |

## 为什么 `api.py` 里 `run_task` 出现两次？（这条最容易被误读成 bug）

```python
def run_task(kind, payload=None, stamp=True, safe=False, probe=False):   # 2562：契约层原定义
    ...
    return _verify_result(kind, payload, _normalize_envelope(kind, raw), probe=probe)

_run_task_base = run_task                                                # 3064：先快照原定义

def run_task(kind, payload=None, stamp=True, safe=False, probe=False):   # 3067：遥测包装器
    _r = _run_task_base(kind, payload, stamp=stamp, safe=safe, probe=probe)
    ...  # 只加 skill_watch.observe 遥测，然后 return _r
    return _r
```

- **3064 的 `_run_task_base = run_task` 是刻意的**：先把契约层原定义存起来，3071 的包装器再调它。
  所以这不是"后者静默覆盖前者"，也不是自我递归 —— `static_check.py` 的前三条就是钉这个的。
- 但必须承认：这个写法**看起来像 bug**。我第一次读也当场怀疑"是不是漏了个去重"。
  写在这里，是因为**读者不该需要猜**。真要改，改成装饰器（`@with_telemetry`）会更清楚 —— 这是待办，不是已完成。

## 这个仓库**没有**放什么（说清楚，别让读者以为这就是全部）

| 没放 | 为什么 | 影响 |
|---|---|---|
| **7.6B 权重** | 权重几十 GB，不走 Git | 想跑模型看 `docs/05-deployment.md`（vLLM serve） |
| **完整引擎（约 650 个 py，227 万行，含 3,134 个 vendored `.pylibs`）** | 依赖本机 `store/`、密钥、设备与大量第三方件；放进开源仓既跑不起来也读不完 | 这里放的是**门与核心 13 件**：能证明"单门/授权/审计/注册表/万能插"五条声明的全部关键代码 |
| `store/`、`state/`、密钥 | 含运行账本、本机路径与凭据（DPAPI 保险箱，永不入库） | 引擎无法直接 `python -m gbt_allinone` 跑起来 |

**结论**：这份源码的用途是**审阅与对照**（"你说的门到底怎么写的"），不是 `pip install` 就能跑的发行包。
要真跑，需要 `store/`、密钥、以及本机依赖 —— 这些按设计不进开源仓。
