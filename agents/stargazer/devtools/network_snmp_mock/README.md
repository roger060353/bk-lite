# 日本 CMDB `network` SNMP mock（OPS ONLY）

**丢弃分支 / Draft PR，禁止合入 product master。**

给日本 `bklite-prod` 上的 Stargazer 提供两台只读 SNMP 假设备，用来验收 CMDB 采集对象 **`network`**（插件 `snmp_facts`，UDP/161）。

| 容器 | 厂商 | `sysObjectID`（`systemoid.json` 精确命中） | 期望 brand / model / device_type | 容器端口 | 宿主机映射 |
|---|---|---|---|---|---|
| `network-snmp-huawei` | Huawei | `1.3.6.1.4.1.2011.2.23.145` | Huawei / `S5700-24TP-SI-AC` / `switch` | 161/udp | **1161/udp** |
| `network-snmp-cisco` | Cisco | `1.3.6.1.4.1.9.1.1208` | Cisco / `cat29xxStack` / `switch` | 161/udp | **1162/udp** |

两台默认 community 都是 **`public`**（SNMPv2c）。切厂商用 **不同容器 IP**，不要改 community。

单容器双档案（可选）：`docker compose --profile combined up -d --build`，community 改成 **`huawei`** 或 **`cisco`**，宿主机 **1163/udp**。

本 mock **没有** LLDP/CDP/ARP/FDB，不要开拓扑。

---

## 0. 日本机前置

在跑 BK-Lite 的那台 Docker 主机上：

```bash
docker network inspect bklite-prod >/dev/null
# 若失败：BK-Lite 未起来或主机不对。不要手动新建同名网来凑数。
```

把本目录拷到该主机（或 checkout 本 OPS 分支）：

```text
agents/stargazer/devtools/network_snmp_mock/
```

---

## 1. 启动

```bash
cd agents/stargazer/devtools/network_snmp_mock
docker compose up -d --build
docker compose ps
```

本地没有 `bklite-prod` 时（不要用在日本）：

```bash
BKLITE_NETWORK_EXTERNAL=false BKLITE_NETWORK_NAME=network-snmp-mock-local \
  docker compose up -d --build
```

记下容器 IP（CMDB 任务填 IP，不能填 DNS 名）：

```bash
docker inspect -f '{{.Name}} {{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}' \
  network-snmp-huawei network-snmp-cisco
```

下文用 `<HUAWEI_IP>` / `<CISCO_IP>` 表示这两台在 `bklite-prod` 上的地址。

---

## 2. 凭据（复制即用）

| 字段 | 值 |
|---|---|
| SNMP version | **`v2`**（页面默认；`v2c` 亦可） |
| community | **`public`** |
| `snmp_port`（Stargazer 同网采集） | **`161`** |
| `snmp_port`（从 Docker 宿主机探测） | Huawei **`1161`** / Cisco **`1162`** |
| username / v3 | 不要填 |

---

## 3. 接入点上先探测（必须成功再填任务）

在 **Stargazer / 接入点容器** 里（已加入 `bklite-prod`）：

```bash
# 通路
nc -vzu <HUAWEI_IP> 161
nc -vzu <CISCO_IP> 161

# 系统标量（采集探针会 GET 这 5 个）
snmpget -v2c -c public -On <HUAWEI_IP> \
  1.3.6.1.2.1.1.1.0 1.3.6.1.2.1.1.2.0 1.3.6.1.2.1.1.4.0 \
  1.3.6.1.2.1.1.5.0 1.3.6.1.2.1.1.6.0

snmpget -v2c -c public -On <CISCO_IP> \
  1.3.6.1.2.1.1.1.0 1.3.6.1.2.1.1.2.0 1.3.6.1.2.1.1.4.0 \
  1.3.6.1.2.1.1.5.0 1.3.6.1.2.1.1.6.0

# 接口表（采集会 GETBULK 这些列）
snmpwalk -v2c -c public -On <HUAWEI_IP> 1.3.6.1.2.1.2.2.1.2
snmpwalk -v2c -c public -On <CISCO_IP> 1.3.6.1.2.1.2.2.1.2
snmpwalk -v2c -c public -On <HUAWEI_IP> 1.3.6.1.2.1.31.1.1.1.18
```

期望：

- Huawei `sysObjectID.0` = `1.3.6.1.4.1.2011.2.23.145`，`sysName.0` = `jp-mock-huawei-s5700`
- Cisco `sysObjectID.0` = `1.3.6.1.4.1.9.1.1208`，`sysName.0` = `jp-mock-cisco-c2960`
- 每台至少 4 条 `ifDescr`

从 **Docker 宿主机** 探测（映射端口；Net-SNMP ≥ 5.9 用 `HOST:PORT`，老版本才认 `-p`）：

```bash
snmpget -v2c -c public -On 127.0.0.1:1161 1.3.6.1.2.1.1.2.0 1.3.6.1.2.1.1.5.0
snmpget -v2c -c public -On 127.0.0.1:1162 1.3.6.1.2.1.1.2.0 1.3.6.1.2.1.1.5.0
snmpwalk -v2c -c public -On 127.0.0.1:1161 1.3.6.1.2.1.2.2.1.2
snmpwalk -v2c -c public -On 127.0.0.1:1162 1.3.6.1.2.1.2.2.1.2
```

不要让同网 Stargazer 去打宿主机 `1161/1162`（绕开 Docker DNS / 可能无法 hairpin）。

---

## 4. CMDB 任务怎么填

入口：**CMDB → 管理 → 自动发现 → 采集 → 专业采集 → 网络设备 → 新增任务**。

建议 **两个任务**（一台 mock 一个），不要用大网段扫。

| 表单项 | Huawei 任务 | Cisco 任务 |
|---|---|---|
| 采集对象 / `model_id` | **网络设备 `network`** | 同左 |
| 接入点 | 日本 Stargazer（`bklite-prod`） | 同左 |
| 采集方式 | **按 IP** | 同左 |
| IP 范围 | `<HUAWEI_IP>` ~ `<HUAWEI_IP>`（单 IP） | `<CISCO_IP>` ~ `<CISCO_IP>` |
| `version` | `v2` | `v2` |
| `community` | `public` | `public` |
| `snmp_port` | **`161`** | **`161`** |
| 拓扑 `has_network_topo` | **关** | **关** |
| 周期 | 手动或 30 分钟均可 | 同左 |

保存后执行。设备通道插件是 `snmp_facts`，不要改成别的。

---

## 5. CMDB 成功标志（对完再喊成功）

任务详情：

- 执行成功，摘要 **新增** ≥ 1 台设备 + 若干接口
- 不要出现 `cmdb_collect_error` / SNMP timeout / community 失败

资产检索（类型是 **`switch`**，不是模型 id `network`）：

| 检查项 | Huawei | Cisco |
|---|---|---|
| 实例名 `inst_name` | `{HUAWEI_IP}-switch` | `{CISCO_IP}-switch` |
| `ip_addr` | `<HUAWEI_IP>` | `<CISCO_IP>` |
| `soid` | `1.3.6.1.4.1.2011.2.23.145` | `1.3.6.1.4.1.9.1.1208` |
| `brand` | **Huawei** | **Cisco** |
| `model` | **S5700-24TP-SI-AC** | **cat29xxStack** |
| `sysname` | `jp-mock-huawei-s5700` | `jp-mock-cisco-c2960` |
| `sysdescr` | 含 `HUAWEI S5700-24TP-SI-AC` | 含 `C2960X` |
| `port` | `161` | `161` |

子对象 **`interface`**：

- 每台 4 条，名称优先 `ifAlias`（Huawei：`uplink-to-core` / `server-vlan` / `mgmt`；Cisco：`edge-uplink` / `server-conn` / `trunk-uplink` / `mgmt`）
- 关联 `interface belong switch`
- 管理状态 / 操作状态能看到 UP / Down（Huawei `NULL0` 为 Down）

品牌若是 **`未知`**：`batch_init` / `init_oid` 没灌 `systemoid.json`，或采集到的 SOID 被改写。先 `snmpget` 对一下 SOID。

---

## 6. 常见失败

| 现象 | 处理 |
|---|---|
| 任务超时 / no response | 接入点不在 `bklite-prod`，或填了宿主机 `1161` 而不是容器 `161` |
| `bklite-prod` 不存在 | BK-Lite 没起；不要手建同名网 |
| community 失败 | 默认两台都是 `public`；combined 才是 `huawei`/`cisco` |
| 品牌 `未知` | OID 目录未同步，或 SOID 不是上表那两条 |
| 拓扑通道失败 | 本 mock 无邻居表，把 `has_network_topo` 关掉 |

停掉：

```bash
cd agents/stargazer/devtools/network_snmp_mock
docker compose down
```

---

## 7. 开发机 walk 数据自检（不依赖 Docker）

```bash
cd agents/stargazer
uv run python -m devtools.network_snmp_mock.smoke
```

对已启动的 mock：

```bash
uv run python -m devtools.network_snmp_mock.smoke \
  --live 127.0.0.1 1161 public --profile huawei
uv run python -m devtools.network_snmp_mock.smoke \
  --live 127.0.0.1 1162 public --profile cisco
```
