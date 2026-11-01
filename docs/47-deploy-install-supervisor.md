# 47 · 落地：一键安装 + 引擎守护（2026-11-01）

> 主人问「项目落地了？」—— 本文只记**这次真做掉的两步**：把"装得上、崩了会自己起来"落到脚本里，
> 以及过程中踩到的三个部署坑（都修了，都写下来）。

---

## 一、"落地"分三层（先把话说明白）

| 层 | 含义 | 现状 |
|---|---|---|
| **代码层** | 能力位在注册表里、有分派、有门、有测试，丢了会红 | ✅ 完成（354 位三源一致，8 份契约测试） |
| **运行层** | 装得上、起得来、崩了会自己回来 | ✅ **本次完成**（安装脚本 + 守护） |
| **数据层** | 全量判决跑完、有置信区间 | 🟡 进行中（136/481） |

## 二、一键安装：`tools/commander-install.ps1`

六步，**幂等**（重复跑不会重复装）：

```
1/6 Python      找 python（没有就用 embeddable 的 pyembed\python.exe）
2/6 权重        在就跳过；缺就下 part1..N 并合并
3/6 sha256      与 WEIGHTS.md 公布值逐字比对，不匹配直接拒绝使用
4/6 ACTIVE.json 写唯一指针（active_artifact / sha256 / size_gb）
5/6 起引擎      活着就复用，没起就 commander.start()
6/6 自检        pulse_core verify + cap_self verify
```

实测输出（本机，权重已在）：

```
== 2/6 权重 ==   已存在 …gbt-v8-v82-q5_0.gguf (4.88 GB)，跳过下载
== 3/6 sha256 == sha256 OK（与 WEIGHTS.md 公布值逐字相同）
== 4/6 ACTIVE == 已写 state\weights\ACTIVE.json
== 5/6 引擎 ==   引擎已在跑，复用
== 6/6 自检 ==   pulse_core: PASS [] · cap_self: PASS {'registry':354,'snapshot':354,'dispatched':354}
落地完成。
```

开关：`-Force`（重下权重）、`-WithSupervisor`（连守护一起起）、`-Autostart`（注册登录自启）。
**不加 `-Autostart` 不碰系统设置**。

## 三、引擎守护：`tools/commander-supervisor.ps1`

每 15s 打 `/health`，**连续 2 次不通**就重启 llama-server；重启后仍不通就把 engine.log 尾部打出来。

实测（手动 kill 掉引擎）：

```
01:20:49  health 不通（第 1 次）
01:20:49  已拉起 llama-server pid=16788
01:20:56  拉起成功
→ /health = 200
```

**为什么需要它**：llama-server 是独立进程，崩了主干会**静默降级**到云端/词表 ——
主人只看到"她变笨了"，看不到"引擎没了"。守护把这件事变成可见（日志 + 重启）。

## 四、三个部署坑（都修了，值得记）

### ① PowerShell：`else` 不能另起一行

```powershell
if (Test-Engine) { ... }
else { ... }        # ← 解析错误 Unexpected token '}'
```
PS 要求 `} else {` 同行。第一版守护脚本就这么挂的（parse error，守护根本没跑起来）。

### ② `Start-Process -ArgumentList` 传数组**不会给路径加引号**

本机用户名里带空格（`Lenovo E14 Gen 5`），于是 `-m C:\...\Lenovo E14 Gen 5\...gguf`
被拆成多个参数，llama-server 报：

```
error: invalid argument: E14
```

修法：**自己加引号拼成一个字符串**再传：
```powershell
$argList = @("-m", "`"$w`"", "--host", ...) -join " "
Start-Process -FilePath $server -ArgumentList $argList ...
```

### ③ `.ps1` 在 Windows PowerShell 5.1 里按 ANSI 读 —— 中文全乱、还会报语法错

安装脚本第一次跑直接刷出一堆 `Unexpected token ')'`，因为中文被读成了 `宸插瓨鍦?`。
修法：**`.ps1` 用带 BOM 的 UTF-8**（`New-Object System.Text.UTF8Encoding($true)`）。

> 注意和 .py 相反：`.py` **不要** BOM（会让 `ast.parse` 崩，见 docs/45），`.ps1` 在 5.1 里**要** BOM。

## 五、还没做的（如实列）

1. **登录自启没注册**：需要显式 `-Autostart`（会写计划任务 `GBT-Commander-Supervisor`）。
2. **她的实机/容器/A19 没碰**：这套只在当前这台机器上跑通。
3. **全量判决还在跑**：136/481（94.9%），约 3 小时。

## 六、复现

```powershell
# 装 + 起 + 自检（幂等）
powershell -ExecutionPolicy Bypass -File tools\commander-install.ps1

# 守护（或加 -WithSupervisor 一起起）
powershell -ExecutionPolicy Bypass -File tools\commander-supervisor.ps1

# 撤销自启（如果你注册过）
schtasks /Delete /TN GBT-Commander-Supervisor /F
```

---

## 七、登录自启：**试过，没做成 —— 如实记**（2026-11-01）

按主人「可以」的批准执行了 `-Autostart`，结果：

```
未能注册（原因：拒绝访问）
自启没做成 —— 不写假成功。
```

三种办法都试了，都被环境挡住：

| 办法 | 结果 |
|---|---|
| `Register-ScheduledTask`（ScheduledTasks 模块） | `New-ScheduledTaskAction : 拒绝访问`（CIM 被沙箱拒） |
| `schtasks /Create`（命令行） | 先是带空格路径被拆成 `Invalid argument/option - 'E14'` |
| `schtasks /Create /XML`（绕开命令行引号） | 临时目录在沙箱虚拟路径里，schtasks 够不到（`cannot find the path`） |

### 顺带修掉一个**假报**

第一版脚本把 `schtasks` 的输出 `Out-Null` 掉了、失败也照样打印"已注册" —— 这正是本仓最忌的假报。
现在改成：注册后**必须 `Get-ScheduledTask` 查回来**才算成功；查不到/注册失败一律如实说"没做成"，
并给三条手动路径：

```
A) 手动起守护（现在就能用）
   powershell -NoProfile -ExecutionPolicy Bypass -File "<repo>\tools\commander-supervisor.ps1"
B) 不用管理员的自启：把上面这条做成快捷方式丢进 shell:startup
C) 管理员终端再跑一次 tools\commander-install.ps1 -Autostart
```

**结论**：自启这一项**没有落地**，属于环境权限限制，不是代码问题；安装与守护本身已落地。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属


---

## 八、换台机器重装：三个收编进来的工具（2026-11-01）

以前这三个脚本躺在我工作区的临时区，换台机器就得现场重写。现在它们在仓里：

| 工具 | 干什么 | 用法 |
|---|---|---|
| 	ools/dl-weights.js | 按分片名下载权重（带重试/进度/断点跳过） | 
ode tools/dl-weights.js state/weights gbt-v8-v82-q5_0.gguf.part{1..4} |
| 	ools/merge-weights.py | 按序合并分片成 GGUF，并校验魔数/大小 | python tools/merge-weights.py state/weights state/weights/x.gguf part1 part2 … |
| 	ools/probe-all.py + probe-one.py | 逐能力过唯一门探针（默认跳过副作用/网络/重扫描类，PROBE_LIMIT=N 可限量） | PROBE_LIMIT=20 python tools/probe-all.py |

三条口径：

1. **不依赖工作区根的临时件**：探针的能力清单改读仓内 data/capabilities.json；
2. **解释器可指**：GBT_PYTHON 环境变量优先，否则用工作区的 pyembed/python.exe；
3. **无参调用给用法**（dl-weights.js 无参时打印示例并 rc=2），不甩 Node 栈。

实测：PROBE_LIMIT=3 python tools/probe-all.py → probe: 3 skip: 0，{"ok": 3}。
