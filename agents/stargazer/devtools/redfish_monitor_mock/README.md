# Hardware Server Redfish 监控 Mock（OPS-ONLY）

**只服务监控中心 Hardware Server Redfish 插件，不是 CMDB 物理机 Redfish 资产采集。**
采集链是：

`Telegraf inputs.prometheus` → `${STARGAZER_URL}/api/monitor/redfish/metrics` → stargazer `RedfishCollector` → 本容器 HTTPS。

采集器按 `@odata.id` 抓 **Systems / Managers / Chassis.Thermal / Chassis.Power / Storage+Drives / Chassis.NetworkAdapters**。
**不会爬 `/Sensors`、日志、DIMM、EthernetInterfaces**（`FORBIDDEN_URI_PARTS`）。
本 mock 仍按 DMTF 提供 `/Chassis/.../Sensors`，方便对照规范；监控刮取不会走它。温度/风扇以 **Thermal** 为准。

## 地址 / 端口 / 凭据

| 项 | 值 |
|---|---|
| 容器名 / DNS | `redfish-monitor-mock` |
| 协议 | HTTPS（采集器写死 `https://`） |
| 端口（docker 网络内） | **443** |
| 宿主机映射 | `8443 → 443`（只给宿主机 curl；策略里不要填 8443，除非 Telegraf/stargazer 跑在宿主机） |
| 用户名 | `redfish` |
| 密码 | `RedfishMon1` |
| 校验证书 | **关闭**（自签证书） |

查 IP：

```bash
docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}} {{$net.IPAddress}}{{"\n"}}{{end}}' redfish-monitor-mock
```

和 IPMI mock 一起起：见 `../docker-compose.monitor-bmc-mocks.yml`。外部网络 **`bklite-prod`**。

## 监控策略怎么配（UI）

1. **监控中心 → 集成 → 集成**（`/monitor/integration/list`）。
2. 对象 **硬件服务器 / Hardware Server** → **采集**。
3. 插件选 **Hardware Server Redfish**（`collect_type=redfish`）。不要去 CMDB 自动发现建 Redfish 任务。
4. **节点**：选能访问 `bklite-prod` 的节点；该节点上的 Telegraf 会打 stargazer，**stargazer 再打本 mock**。stargazer 容器也必须在同一网络。
5. 表格：**IP** 填 `redfish-monitor-mock` 的 `bklite-prod` 地址；实例名例如 `redfish-monitor-mock`。
6. 采集表单：
   - **端口** `443`
   - **用户名** `redfish`
   - **密码** `RedfishMon1`
   - **校验证书** 关掉
   - **间隔** `60`
7. 下发后等 1–2 个周期，到指标页 / 硬件服务器仪表盘核对。

## BMC 自检（先于监控策略）

同一网络内：

```bash
curl -k -u redfish:RedfishMon1 https://<REDFISH_MOCK_IP>/redfish/v1/
curl -k -u redfish:RedfishMon1 https://<REDFISH_MOCK_IP>/redfish/v1/Systems
curl -k -u redfish:RedfishMon1 https://<REDFISH_MOCK_IP>/redfish/v1/Chassis/Chassis.Embedded.1/Thermal
curl -k -u redfish:RedfishMon1 https://<REDFISH_MOCK_IP>/redfish/v1/Chassis/Chassis.Embedded.1/Power
```

宿主机：

```bash
curl -k -u redfish:RedfishMon1 https://127.0.0.1:8443/redfish/v1/Systems/System.Embedded.1
```

登录会话（采集器也会 POST，失败则回落 Basic）：

```bash
curl -k -D - -X POST https://<REDFISH_MOCK_IP>/redfish/v1/SessionService/Sessions \
  -H 'Content-Type: application/json' \
  -d '{"UserName":"redfish","Password":"RedfishMon1"}'
```

`/redfish/v1/Chassis/Chassis.Embedded.1/Sensors` 用 curl 能打开；**监控采集器请求该路径会被拒绝**。不要把它当成采集失败。

## 测试专家指标核对清单

下列名称必须全部出现。值为本 mock 健康夹具（两路 PSU 都在供电，功耗未超限）。

| 指标 | 期望值 | 维度 | 组 |
|---|---|---|---|
| `redfish_system_health` | 1 | — | Health |
| `redfish_system_power_state` | 1 | — | Health |
| `redfish_manager_health` | 1 | — | Health |
| `redfish_processor_health_rollup` | 1 | — | Health |
| `redfish_memory_health_rollup` | 1 | — | Health |
| `redfish_firmware_info` | 1 | `bios_version=2.18.1` `bmc_firmware=7.00.00` | Inventory |
| `redfish_temperature_celsius` | 45 / 22 / 33 | `name=CPU1 Temp` / `System Board Inlet Temp` / `System Board Exhaust Temp` | Environment |
| `redfish_temperature_upper_critical_celsius` | 98 / 47 / 80 | 同上 `name` | Environment |
| `redfish_inlet_temperature_celsius` | 22 | — | Environment |
| `redfish_inlet_temperature_upper_critical_celsius` | 47 | — | Environment |
| `redfish_fan_speed` | 4200 / 3900 | `name=Fan1\|Fan2` `unit=RPM` | Environment |
| `redfish_fan_health` | 1 / 1 | `name=Fan1\|Fan2` | Environment |
| `redfish_power_consumed_watts` | 280 | `name=System Power Control` | Power |
| `redfish_power_limit_watts` | 750 | `name=System Power Control` | Power |
| `redfish_power_over_limit` | 0 | — | Power |
| `redfish_psu_health` | 1 / 1 | `name=PS1 Status\|PS2 Status` | Power |
| `redfish_psu_input_watts` | 160 / 145 | 同上 | Power |
| `redfish_psu_output_watts` | 148 / 132 | 同上 | Power |
| `redfish_psu_capacity_watts` | 750 / 750 | 同上 | Power |
| `redfish_psu_input_voltage` | 220 / 220 | 同上 | Power |
| `redfish_psu_delivering` | 1 / 1 | 同上（>20W 才算在供电） | Power |
| `redfish_psu_redundant` | 1 | — | Power |
| `redfish_voltage_volts` | 12.1 / 3.31 | `name=System Board 12V\|System Board 3.3V` | Power |
| `redfish_storage_health` | 1 | `id=RAID.Integrated.1-1` | Storage |
| `redfish_storage_controller_health` | 1 | `id=RAID.Integrated.1-1` `storage_id=RAID.Integrated.1-1` | Storage |
| `redfish_drive_health` | 1 / 2 | HDD=`Physical Disk 0:1:0`；SSD=`SSD 0`（Warning=2） | Storage |
| `redfish_drive_present_count` | 2 | —（空托架 Empty Bay 不计） | Storage |
| `redfish_drive_life_percent` | 86 | 仅 `SSD 0` | Storage |
| `redfish_nic_health` | 1 | `id=NIC.Integrated.1` | Network |
| `redfish_nic_port_health` | 1 | `adapter_id=NIC.Integrated.1` `id=1` | Network |
| `redfish_nic_port_link_up` | 1 | 同上 | Network |
| `redfish_nic_port_speed_mbps` | 25000 | 同上 | Network |

**32 个插件指标名必须齐。** 没有 `redfish_sel_*`。空托架 `Empty Bay` 不应出现。

## 本地不启 Docker 时

```bash
cd agents/stargazer
uv run python -m devtools.redfish_monitor_mock --host 127.0.0.1 --port 8443
uv run python -m devtools.redfish_monitor_mock.smoke
uv run pytest -q -o addopts='' tests/test_redfish_monitor_mock_smoke.py
```
