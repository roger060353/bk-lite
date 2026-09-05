# OceanStor DeviceManager mock

仅用于本地 / CI 联调 CMDB·Stargazer 的 `oceanstor_https` 采集，**不是生产路径**。
用标准库 `http.server` 模拟 DeviceManager 会话与配置查询，夹具字段对齐产品锁定的 `MACADDR` / `WWPN`。

## 覆盖端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/deviceManager/rest/xxxxx/sessions` | 登录，返回 `iBaseToken` + `deviceid` |
| `DELETE` | `/deviceManager/rest/{deviceid}/sessions` | 登出 |
| `GET` | `/deviceManager/rest/{deviceid}/system` | 型号 / 微码（`PRODUCTMODESTRING` / `PRODUCTVERSION`） |
| `GET` | `/deviceManager/rest/{deviceid}/storagepool` | 存储池，支持 `range=[start-end]` |
| `GET` | `/deviceManager/rest/{deviceid}/disk` | 磁盘 |
| `GET` | `/deviceManager/rest/{deviceid}/lun` | 卷 |
| `GET` | `/deviceManager/rest/{deviceid}/eth_port` | 以太口：一条有 `MACADDR`，一条为空（采集后应跳过） |
| `GET` | `/deviceManager/rest/{deviceid}/fc_port` | FC 口：一条有 `WWPN`，一条为 `--`（采集后应跳过） |

后续 GET 必须带登录下发的 `iBaseToken` 头。

## 启动

在 `agents/stargazer` 目录：

```bash
# HTTP，默认 127.0.0.1:18088（避开真机 8088）
uv run python -m devtools.oceanstor_mock.server

# 自签 HTTPS（采集任务把 verify_tls 设为 false）
uv run python -m devtools.oceanstor_mock.server --tls --port 8088
```

默认账号：`admin` / `Admin@storage`，`deviceid=2102355TJUN0S1100017`。

## 把采集任务指过来

CMDB 存储采集对象协议是 `oceanstor_https`（默认 8088）。对 mock：

| 凭据字段 | HTTP mock | HTTPS mock |
|---|---|---|
| host / 实例 IP | `127.0.0.1` | `127.0.0.1` |
| port | `18088` | `8088` |
| scheme | `http` | `https` |
| username | `admin` | `admin` |
| password | `Admin@storage` | `Admin@storage` |
| verify_tls | `false` | `false`（自签证书） |

Stargazer 插件直接调：

```python
OceanStorManager({
    "host": "127.0.0.1",
    "port": 18088,
    "scheme": "http",
    "username": "admin",
    "password": "Admin@storage",
    "verify_tls": False,
})
```

curl 登录示例：

```bash
curl -sS -X POST 'http://127.0.0.1:18088/deviceManager/rest/xxxxx/sessions' \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@storage","scope":"0"}'
```

## 冒烟

```bash
cd agents/stargazer
uv run python -m devtools.oceanstor_mock.smoke
uv run pytest -q -o addopts='' tests/test_oceanstor_mock_smoke.py
```

CMDB 映射（空 MAC/WWPN 跳过 + `storage contains` 口）用同一套夹具：

```bash
cd server
DB_ENGINE=sqlite DB_NAME=:memory: SECRET_KEY=cursor-cloud-dev ENABLE_CELERY=true \
  uv run pytest apps/cmdb/tests/test_oceanstor_mock_mapping.py --no-cov
```

采集侧原始回包会带上无 MAC / 无 WWPN 的口；CMDB `format_metrics` 按身份跳过它们，只给有 `MACADDR` / `WWPN` 的口写 `storage_contains_storage_eth_port` / `storage_contains_storage_fc_port`。
