# Huawei VRP Telnet mock（网络配置文件采集）

**TEST-ONLY / 日本节点联调**，不进默认生产采集路径，不改任务树默认值。

PR #18 的 `network_config_file` 已支持 `transport_protocol=telnet`，但仓库原先没有可跑的网络设备 Telnet 替身。真机 `192.168.16.242` 从日本节点不可达时，Scrapli 建连超时会被归成 `ScrapliAuthenticationFailed`，最终日志常见 `credentials_exhausted`——这不是账号错了，是 TCP/23 根本没通。

本目录提供最小华为 VRP Telnet mock：登录提示 `Username:` / `Password:`，用户视图 `<mock-vrp>`（小写，匹配 Scrapli `huawei_vrp` 提示符），应答本插件会发的翻页命令和只读 show/display。

## 1. 启动

### 日本节点推荐：Docker，并接入产品栈网络

在**本仓库**执行（可与已有 `/opt/bk-lite/deploy/docker-compose` 并行，不要另起一套产品栈）：

```bash
cd agents/stargazer/devtools/huawei_vrp_telnet_mock
docker compose up -d --build
docker compose ps

# 查产品栈网络名（常见 *default / *bk-lite*）
docker network ls
docker network connect <bklite_network> huawei-vrp-telnet-mock
```

若 `python:3.12-slim` 拉不到，把 `Dockerfile` 的 `FROM` 改成 `docker.m.daocloud.io/library/python:3.12-slim` 再 `up -d --build`。

等价 `docker run`：

```bash
cd agents/stargazer/devtools/huawei_vrp_telnet_mock
docker build -t huawei-vrp-telnet-mock:qa .
docker run -d --name huawei-vrp-telnet-mock --hostname huawei-vrp-telnet-mock \
  -p 2323:23 huawei-vrp-telnet-mock:qa
docker network connect <bklite_network> huawei-vrp-telnet-mock
```

### 本机 / 节点上已有 Stargazer venv

```bash
cd agents/stargazer
uv run python -m devtools.huawei_vrp_telnet_mock --host 0.0.0.0 --port 2323
```

默认账号：`admin` / `Admin@network`，提示符 `<mock-vrp>`。容器内听 **TCP/23**，宿主机映射 **2323**。

冒烟（本机，不依赖 Docker）：

```bash
cd agents/stargazer
uv run python -m devtools.huawei_vrp_telnet_mock.smoke
uv run pytest -q -o addopts='' tests/test_huawei_vrp_telnet_mock_smoke.py
```

手工探活（同一 docker 网络内端口是 23）：

```bash
# 宿主机映射
printf 'admin\nAdmin@network\ndisplay version\nexit\n' | nc -q 2 127.0.0.1 2323
# 产品栈网络内
printf 'admin\nAdmin@network\ndisplay version\nexit\n' | nc -q 2 huawei-vrp-telnet-mock 23
```

## 2. 日本节点：CMDB 任务怎么填

对象仍是 **专业采集 → 网络设备配置文件**（`model_id=network_config_file`）。不要选 SNMP 的「网络设备」。

### 2.1 采集实例（不是凭据）

| 界面 / Django 字段 | 示例 | 说明 |
|---|---|---|
| 实例 `ip_addr` / `host` | `huawei-vrp-telnet-mock` | 已 `docker network connect` 时用容器名；否则用日本节点宿主机 IP |
| 厂商 `brand` | `Huawei` 或 `华为` | 服务端归一成 `device_type=huawei` → Scrapli `huawei_vrp` |
| 模型 | `switch` / `router` / `firewall` / `loadbalance` | 任务只接受这些网络模型 |

`device_type` **不要手填凭据**；由实例 `brand` 解析。

### 2.2 任务参数

| 界面 | Django `params` / 下发字段 | 示例 |
|---|---|---|
| 配置名称 | `config_name` | `running-config` |
| 采集命令（每行一条） | `commands` | `display current-configuration` 换行 `display version` |
| 接入点 | `access_point` | 选日本节点 Stargazer |

华为风格命令优先。表单占位是 Cisco 的 `show running-config` / `show version`，mock **两者都认**。不要填 `configure` / `save` / `telnet` 等高危前缀。

**特权密码留空。** Huawei VRP 用户视图已是 Scrapli `privilege_exec`；填了 `enable_password` 只会再跑一次 `acquire_priv`，本 mock 不需要。

### 2.3 凭据池（界面 → 落库 JSON → Stargazer）

界面「连接协议」选 **Telnet** 后，端口若仍是 22 会自动改成 **23**。

| 界面文案 | 表单 / 落库字段 | 日本 mock 示例 |
|---|---|---|
| 连接协议 | `transport_protocol` | `telnet`（别名 `asynctelnet` 也可） |
| 用户 | `username` | `admin` |
| 密码 | `password` | `Admin@network` |
| 端口 | `port` | 同一 docker 网络：`23`；走宿主机映射：`2323` |
| 特权密码 | `enable_password` | 空，不要填 |

落库 `CollectModels.credential` 示例：

```json
[
  {
    "username": "admin",
    "password": "Admin@network",
    "transport_protocol": "telnet",
    "port": 23
  }
]
```

下发给 Stargazer 的最终字段（NodeParams，密码走 env 占位）：

| 下发字段 | 值 |
|---|---|
| `transport_protocol` | `telnet` |
| `port` | `23`（或你填的自定义端口） |
| `username` | `admin` |
| `password` | 环境变量展开后的明文 |
| `device_type` | `huawei` |
| `need_enable` | `false`（未填特权密码） |

不要填 `protocol=telnet` 以外的 `protocol` 去改传输：`protocol_version=2` 是配置回包协议，不是 Telnet。

### 2.4 选端口的两种接法

| 采集节点怎么访问 mock | 实例 `ip_addr` | 凭据 `port` |
|---|---|---|
| 已 `docker network connect`，Stargazer 在同一网络 | `huawei-vrp-telnet-mock` | `23` |
| Stargazer 在宿主机，或不方便加网络 | 日本节点 IP 或 `127.0.0.1` | `2323` |

IP 预检走 **任务端口**（Telnet 默认 23）。mock 没起来或网络没接上时，预检就会 `tcp_connect_timeout` / `tcp_connection_refused`，到不了采集成功。

## 3. 成功长什么样（不是 `credentials_exhausted`）

Stargazer 日志应出现（INFO 汇总，不含口令）：

```text
event=collection_run_started ... model_id=network_config_file ...
event=collection_run_summary ... 采集成功=1 采集失败=0 不可达=0 ... 失败类型=
event=collection_run_terminal ... status=success
```

不应出现：

- `error_code=credentials_exhausted`
- `authentication_failed` / `ScrapliAuthenticationFailed`
- `cmdb_collect_error` 含 `Error:` / `Unrecognized command`
- `tcp_connect_timeout` / `target_unreachable`

CMDB：回调 `receive_config_file_result`，该实例出现配置文件版本，正文含 `sysname mock-vrp` 与 `Mock VRP`。

### 失败对照

| 现象 | 常见原因 |
|---|---|
| `credentials_exhausted` 且目标仍是 `192.168.16.242` | 真机不可达；Scrapli 建连超时异常名带 Authentication，会被归成认证耗尽 |
| `tcp_connection_refused` / `tcp_connect_timeout` | mock 没起来，或实例 IP/端口与 docker 网络不一致 |
| `ScrapliAuthenticationFailed` / `username/login prompt seen more than once` | 用户或密码不是 `admin` / `Admin@network` |
| `不支持的异步网络驱动` | 实例 `brand` 不是华为（需 `Huawei` / `华为`） |
| 命令失败且含 `Error:` | 命令被当未知命令；改用 `display` / `show` 只读命令 |

## 4. 停掉 mock（产品栈保持不动）

```bash
cd agents/stargazer/devtools/huawei_vrp_telnet_mock
docker compose down
```
