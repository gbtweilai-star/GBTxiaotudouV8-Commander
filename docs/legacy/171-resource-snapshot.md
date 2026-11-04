# 171 · 本机资源快照 resource_snapshot（P2-10）

> 主人 P2：「本机资源快照」。
> 只煎**读数口径**：CPU/内存/磁盘/uptime/主机/平台；不搬第三方监控栈。
> Windows 用 ctypes + shutil；**零第三方依赖**（psutil 可选），不写盘/不起进程/不出网。

## 一、四件

| 件 | 落点 |
|---|---|
| 模块/契约 | [`gbt_allinone/tools/resource_snapshot.py`](../../gbt_allinone/tools/resource_snapshot.py) · `verify()` **16 项** |
| 统一门 | 注册能力位 **`resource_snapshot`**（`run_task`，zero-scope 只读） |
| API | `GET /api/resources`：真采样快照（只读） |
| APP 接线 | console 右栏「本机资源」：CPU/内存/磁盘条 + host/uptime/进程/平台，10s 刷新 |
| 验收 | [`tests/test_resource_snapshot.py`](../../tests/test_resource_snapshot.py) |

## 二、读数口径

- **CPU**：`GetSystemTimes` 两帧差（sleep 0.15s），`busy = kernel+user-idle`，百分比；
- **内存**：`GlobalMemoryStatusEx` → total/used/percent；
- **磁盘**：`shutil.disk_usage(仓库根)` → total/used/percent；
- **uptime**：`GetTickCount64` 秒；
- **进程数**：`psutil` 可选；没有就 `null`，**不硬装**、不猜；
- 归一化：百分比 0..100、负值拒、非数字拒；`host/platform` 截断。

## 三、真机读数（2026-11-03 APP）

`GET /api/resources` → `ok=true · host=DESKTOP-H9L6OL9 · Windows 11 · cpu 36.8% · mem 80.6%（12944/16057MB）· disk 52.6%（134.22/255.13GB）· uptime 43937s · process_count=290`（APP pyembed 有 psutil；仓库 py312 没有则 null）。右栏 UI 同步显示 CPU/内存/磁盘条与 `uptime 12.2h · 进程 292 · Windows 11`。

![本机资源快照（APP 真机右栏）](../assets/app-resource.png)

## 四、边界（说死）

1. 只是**快照采样**，不是持续监控/告警；UI 10s 轮询；
2. CPU 采样有 0.15s 阻塞（读取调用），不在热路径高频调用；
3. 进程数依赖可选 psutil；没有就如实 null；
4. 不读其他进程明细/凭据，不做温度/GPU（要另接 WMI/厂商库，未引）；
5. 只读零作用域，不写盘不出网。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_resource_snapshot.py
# GET http://127.0.0.1:8766/api/resources
# console 右栏「本机资源」
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
