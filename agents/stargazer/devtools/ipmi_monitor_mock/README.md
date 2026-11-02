# Hardware Server IPMI 监控 Mock（OPS-ONLY）

**只服务监控中心 Hardware Server IPMI 插件，不是 CMDB 物理机资产采集。**
Telegraf `inputs.ipmi_sensor` 直连本容器 UDP/623，采集 `sdr` + `chassis_power_status`。
BMC 面是 OpenIPMI 官方 `ipmi_sim`（`lanserv/lan.conf` + `ipmisim1.emu` 结构），不是自研 RMCP 栈。

不要把本 compose 当成一套并行 BK-Lite。现场产品栈仍用已有 `bklite-prod` 网络。

## 地址 / 端口 / 凭据

| 项 | 值 |
|---|---|
| 容器名 / DNS | `ipmi-monitor-mock` |
| 协议 | IPMI 2.0 RMCP+（UI 填 `lanplus`，默认值） |
| 端口 | **UDP 623**（插件 UI 无端口字段，必须是 623） |
| 用户名 | `admin` |
| 密码 | `IpmiMon1` |
| 权限 | `admin` |
| 宿主机映射 | `623/udp` |

查容器在 `bklite-prod` 上的 IP（监控策略里的「IP」填这个，不要填容器名，除非现场 Telegraf 能解析）：

```bash
docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}} {{$net.IPAddress}}{{"\n"}}{{end}}' ipmi-monitor-mock
```

和 Redfish mock 一起起：

```bash
# 仅当现场还没有该网络时
docker network create bklite-prod

cd agents/stargazer/devtools
docker compose -f docker-compose.monitor-bmc-mocks.yml up -d --build
docker stats --no-stream ipmi-monitor-mock redfish-monitor-mock
```

两个容器 `mem_limit` 合计 448MiB。`docker stats` 的 RSS 应明显低于 1GiB。

## 监控策略怎么配（UI）

1. 打开 **监控中心 → 集成 → 集成**（`/monitor/integration/list`）。
2. 对象选 **硬件服务器 / Hardware Server**，进入 **采集**。
3. 插件选 **Hardware Server IPMI**（`collect_type=ipmi`，Collector=Telegraf）。不要选 SNMP，也不要去 CMDB 自动发现里建 IPMI 任务。
4. **节点**：选能访问 `bklite-prod` 的采集节点（节点上的 Telegraf 必须打得到 mock 的 UDP/623）。
5. 表格字段：
   - **IP**：上一步查到的 `ipmi-monitor-mock` 地址
   - **实例名称**：任意，例如 `ipmi-monitor-mock`
   - **组**：可选
6. 保存后编辑采集配置（或创建时的表单）：
   - **用户名** `admin`
   - **密码** `IpmiMon1`
   - **协议** `lanplus`
   - **间隔** `60`
7. 下发后等 1–2 个周期，到 **指标** 页或硬件服务器仪表盘核对。

本插件 UI **没有端口框**。Telegraf 模板是 `user:pass@lanplus(ip)`，ipmitool 默认 UDP/623。

## 容器内自检（先于监控策略）

```bash
docker exec ipmi-monitor-mock ipmitool -I lanplus -H 127.0.0.1 -U admin -P IpmiMon1 chassis power status
docker exec ipmi-monitor-mock ipmitool -I lanplus -H 127.0.0.1 -U admin -P IpmiMon1 sdr elist
```

期望：`Chassis Power is on`，并且 SDR 里能看到下表名称与单位。

从已加入 `bklite-prod` 的另一容器测：

```bash
ipmitool -I lanplus -H <IPMI_MOCK_IP> -U admin -P IpmiMon1 sdr elist
```

若 `lanplus` 在极老的 OpenIPMI 上失败，再试 `-I lan`，并在 UI 把协议改成 `lan`。默认按 `lanplus` 交付。

## 测试专家指标核对清单

监控展示名是 PromQL 包装。原始序列是 Telegraf `ipmi_sensor_*`。
**两边都要有。** 缺原始 unit 则展示图为空。

### A. 展示指标（`metrics.json` / 指标页）

| 展示指标 | 期望 | 原始过滤 |
|---|---|---|
| `ipmi_chassis_power_state` | `1`（正常） | 优先 `ipmi_sensor_status{name=~"host_power"}`；否则 `2 - ipmi_sensor_value{name="chassis_power_status"}` |
| `ipmi_power_watts` | `280` | `ipmi_sensor_value{unit="watts"}` |
| `ipmi_voltage_volts` | `12.1`、`3.3` | `ipmi_sensor_value{unit="volts"}` |
| `ipmi_fan_speed_rpm` | `4200`、`3900` | `ipmi_sensor_value{unit="rpm"}` |
| `ipmi_temperature_celsius` | `22`、`45`、`33` | `ipmi_sensor_value{unit="degrees_c"}` |

### B. Telegraf 原始序列（必须先有这些）

| 原始指标 | `name` | `unit` | 期望值 |
|---|---|---|---|
| `ipmi_sensor_value` | `inlet_temp` | `degrees_c` | 22 |
| `ipmi_sensor_value` | `cpu1_temp` | `degrees_c` | 45 |
| `ipmi_sensor_value` | `exhaust_temp` | `degrees_c` | 33 |
| `ipmi_sensor_value` | `fan1` | `rpm` | 4200 |
| `ipmi_sensor_value` | `fan2` | `rpm` | 3900 |
| `ipmi_sensor_value` | `pwr_consumption` | `watts` | 280 |
| `ipmi_sensor_value` | `voltage_12v` | `volts` | 12.1 |
| `ipmi_sensor_value` | `voltage_3_3v` | `volts` | 3.3 |
| `ipmi_sensor_status` | `host_power` | — | 1（ok） |
| `ipmi_sensor_value` | `chassis_power_status` | — | 1（on） |

Telegraf 可能把名称转成小写/下划线。`host_power` 用正则匹配，其它 `name` 以 SDR 字符串为准。
**判断采集成功：先搜 `unit="degrees_c"` / `rpm` / `volts` / `watts`，不要只搜展示名。**

### C. 本 mock 不提供

- DCMI power reading
- SEL / 日志
- CMDB 资产字段（厂商、序列号、CPU/内存清单）
- 非 623 端口

## 本地不启 Docker 时

```bash
cd agents/stargazer
uv run python -m devtools.ipmi_monitor_mock          # 重生成 lan.conf / ipmi.emu
uv run python -m devtools.ipmi_monitor_mock.smoke
uv run pytest -q -o addopts='' tests/test_ipmi_monitor_mock_catalog.py
```
