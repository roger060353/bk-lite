# CMDB Redfish 硬件 P0

Status: implemented

在既有 `physcial_server` Redfish 采集上扩展库存，不新增采集任务类型。凭据、HTTPS、唯一 `ComputerSystem` 和实例名规则保持不变。

## 范围

- 新子模型 `storage_controller`、`psu`，分类 `hardware_components`，`physcial_server contains` 1:n。
- 整机补 `power_state`、`health`。磁盘补 `health`、`disk_life_percent`。网卡补 `nic_speed_mbps`，并在没有操作系统网口名时写入 `nic_iface`。
- `Power` 或 `StorageControllers` 缺失、404 或读取失败时跳过对应子项，任务仍成功。
- 不写瞬时功耗，不把风扇、单颗 CPU、能耗、温度、电压、转速写入 CMDB。

## 字段

健康快照统一用字段 `health`，来源 `Status.Health`。不使用 `HealthRollup`。

`storage_controller`：`sc_id`（必填，`MemberId`，否则 `Id`；两者都没有则跳过）、`sc_name`、`sc_vendor`、`sc_model`、`sc_sn`、`sc_firmware`、`health`、`self_device`。

`psu`：`psu_name`（必填，`Name`，否则 `MemberId` 或 `Id`）、`psu_vendor`、`psu_model`、`psu_sn`、`psu_capacity_watts`（`PowerCapacityWatts`）、`health`、`self_device`。不写 `PowerInputWatts` 等瞬时功耗。

`physcial_server`：`power_state` ← `PowerState`，`health` ← `Status.Health`。

`disk`：`health`；`disk_life_percent` ← `PredictedMediaLifeLeftPercent`。

`nic`：`nic_speed_mbps`（优先 `CurrentLinkSpeedMbps`，否则 `SpeedMbps`，否则 `CurrentSpeedGbps`×1000）。标准 Redfish 没有操作系统网口名；若功能上出现 `HostInterface` 或 `InterfaceName` 则写入 `nic_iface`，否则用功能名、适配器名、功能 Id 或适配器 Id。

`Status.State=Absent` 的控制器、电源、磁盘不入库，与既有磁盘规则一致。

实例名：`{sc_id}-{BMC IP}`、`{psu_name}-{BMC IP}`。寿命、速率、额定功率在采集器侧四舍五入成整数后再进入指标；协议插件用既有 `transform_int` 解析该整数。
