# OPS：华为 iBMC 风格 Redfish 模拟目标（Japan CMDB E2E）

**本目录是一次性运维包，不是产品功能。** 合成协议模拟器，不是华为固件、真机抓包或兼容认证。不要合入生产启动脚本、Supervisor 或 `batch_init`。对应 PR 标 **DO NOT MERGE**。

问题：本机 `python3 mock_server.py` 默认只监听 `127.0.0.1`，`bklite-prod` 上的 Stargazer 连不上。本包把同一套 `mock_server.py` / `inventory.py` 放进容器，监听 `0.0.0.0:443`，并加入外部网络 `bklite-prod`。

采集器 `PhyscialServerRedfishInfo` **只接受 IP**，不能填容器主机名。

---

## 0. 一次性粘贴清单

```text
插件入口：【BETA】物理服务器 Redfish
插件 ID：physcial_server_redfish
模型：physcial_server
驱动：protocol
协议参数：collection_protocol=redfish

BMC IP：docker inspect 得到的 bklite-prod 地址（禁止填 huawei-redfish-target）
端口：443
用户：mock-reader
密码：mock-redfish-pw
verify_tls：关闭（自签证书；界面会提示中间人风险，联调必须关）

成功标记（默认 x86 / healthy）：
  inst_name      = 上面填的 BMC IP
  ip_addr        = 同上
  brand          = Huawei
  model          = 2288H V5 (synthetic)
  serial_number  = MOCK-X86-SERVER-001
  asset_code     = 空（模拟清单没有 AssetTag，首版不建 nic/disk/memory）
```

---

## 1. 前置

| 项 | 要求 |
|---|---|
| 产品栈 | 现场已有 compose 已起来（`/opt/bk-lite/deploy/docker-compose` 或 `docker-compose-ha`） |
| 网络 | `docker network ls` 能看到 **已存在** 的 `bklite-prod` |
| 采集节点 | Stargazer / node 已加入 `bklite-prod` |
| 本仓库 | 能读到本目录并 `docker compose build` |

`bklite-prod` 不存在时不要手动新建同名网络凑数，先确认产品栈在这台 Docker 主机上。

```bash
docker network ls | grep bklite-prod
docker network inspect bklite-prod --format '{{range .Containers}}{{.Name}} {{end}}'
# 输出里应有 stargazer / node 一类采集容器
```

---

## 2. 拉起 Redfish 目标

在**本仓库**执行，与产品栈并行，不要另起一套 BK-Lite：

```bash
cd agents/stargazer/tests/collect_fixtures/huawei_redfish_target
docker compose up -d --build
docker compose ps
```

若 `docker.m.daocloud.io/library/python:3.12-slim-bookworm` 拉不到，把 `Dockerfile` 的 `FROM` 改成 `python:3.12-slim-bookworm` 再 `up -d --build`。

容器内监听 `0.0.0.0:443`（HTTPS）。宿主机映射 `18443:443` 只给本机冒烟，**Stargazer 不要走宿主机 IP + 18443**。

### 取 BMC IP（任务必须填这个）

```bash
docker inspect -f '{{.NetworkSettings.Networks.bklite-prod.IPAddress}}' huawei-redfish-target
```

记下该地址，下文记为 `<BMC_IP>`。容器重建后 IP 可能变，要重查并改任务。

### 从采集节点冒烟（在 Stargazer 容器内执行）

```bash
BMC_IP=$(docker inspect -f '{{.NetworkSettings.Networks.bklite-prod.IPAddress}}' huawei-redfish-target)
# 下面这条请 docker exec 进 stargazer / node 再跑；-k 仅用于自签联调
curl -sk -u mock-reader:mock-redfish-pw "https://${BMC_IP}:443/redfish/v1/"
curl -sk -u mock-reader:mock-redfish-pw "https://${BMC_IP}:443/redfish/v1/Systems/1"
```

服务根可匿名；`Systems/1` 需要 Basic。应看到 `2288H V5 (synthetic)` 和 `MOCK-X86-SERVER-001`。响应头有 `X-Mock-Data: synthetic-not-hardware-verified`。

本机（不经过 Stargazer）可：

```bash
curl -sk -u mock-reader:mock-redfish-pw https://127.0.0.1:18443/redfish/v1/Systems/1
```

---

## 3. CMDB 任务填写（`physcial_server_redfish`）

1. 采集对象选 **【BETA】物理服务器 Redfish**（树节点 id = `physcial_server_redfish`，`model_id` = `physcial_server`，`driver` = `protocol`）。不要选「物理服务器 SSH」或「物理服务器 IPMI」。
2. 系统会写 `params.collection_protocol=redfish`。不要改成 `ipmi`。
3. 实例 / BMC：

| 字段 | 值 |
|---|---|
| `ip_addr` / BMC IP | `<BMC_IP>`（上一步 inspect，必须是 IPv4） |
| 接入点 | 能访问 `bklite-prod` 的 Stargazer / node |

4. 凭据（inline 或凭据池 `redfish_bmc` / `host/redfish`，字段相同）：

| 字段 | 值 |
|---|---|
| `username` | `mock-reader` |
| `password` | `mock-redfish-pw` |
| `port` | `443` |
| `verify_tls` | **false**（必须显式关闭） |

5. 执行采集一次。

常见失败：

| 现象 | 原因 |
|---|---|
| `Redfish target must be an IP address` | 填了容器名 `huawei-redfish-target` |
| `tls_validation_failed` | `verify_tls` 仍为 true |
| 连接超时 / 无响应 | mock 没加入 `bklite-prod`，或任务填了 `127.0.0.1` / 宿主机 IP |
| 401 | 用户或密码不是 `mock-reader` / `mock-redfish-pw` |
| 仍采集到旧序列号 | 任务还指向旧 BMC IP（容器重建后 IP 变了） |

---

## 4. 成功标记

默认 compose：`--profile x86 --scenario healthy`。首版 Redfish 只写整机身份，不创建 nic / disk / memory / gpu。

| CMDB 字段 | 期望 |
|---|---|
| `inst_name` | 等于任务里的 `<BMC_IP>`（身份只取采集目标 IP，不用序列号） |
| `ip_addr` | `<BMC_IP>` |
| `brand` | `Huawei` |
| `model` | `2288H V5 (synthetic)` |
| `serial_number` | `MOCK-X86-SERVER-001` |
| `asset_code` | 不出现（模拟清单无 `AssetTag`） |

协议层还可核对：`GET /redfish/v1/` 的 `RedfishVersion=1.6.0`，`ComputerSystem` 一条且 `Id=1`。

若改成 `--profile arm`：`model=TaiShan 200 (synthetic)`，`serial_number=MOCK-ARM-SERVER-001`。Japan E2E 用默认 x86 即可。

---

## 5. 停掉目标（产品栈保持不动）

```bash
cd agents/stargazer/tests/collect_fixtures/huawei_redfish_target
docker compose down
```

---

## 6. 附录：物理服务器 SSH 替身（同一现场）

Redfish 只管带外身份。若还要 SSH JOB 采 nic，用另一套 fixture，不要和本容器混端口。

| 项 | 值 |
|---|---|
| 目录 | `agents/stargazer/tests/collect_fixtures/physcial_server_ssh_target/` |
| 说明 | 同目录 `README.md` |
| compose | `physcial_server_ssh_target/docker-compose.yaml` |
| 容器 | `physcial-server-ssh-target` |
| 用户 / 密码 | `root` / `testpw` |
| 宿主机映射 | `12226:22` |
| 接到 `bklite-prod` 后 | 主机填容器名或该容器 IP，端口 **22** |
| 采集节点在宿主机 | 主机 `127.0.0.1`（或宿主机 IP），端口 **12226** |
| CMDB 入口 | 物理服务器 SSH（`physcial_server`，`driver=job`），不要选 IPMI / Redfish |

把 SSH 目标接到产品网络（SSH compose 默认没写 `bklite-prod`）：

```bash
docker network connect bklite-prod physcial-server-ssh-target
```

冒烟：

```bash
sshpass -p testpw ssh -o StrictHostKeyChecking=no -p 12226 root@127.0.0.1 'echo ok'
```

---

## 数据范围与本机环回（开发用）

本目录仍是合成模拟器。公开资料核对于 2026-09-07：

- [华为官方 Huawei-iBMC-Cmdlets](https://github.com/Huawei/Huawei-iBMC-Cmdlets)
- [华为鲲鹏服务器 iBMC Redfish 接口说明](https://support.huawei.com/enterprise/zh/doc/EDOC1100372764/18bfdbec)
- [DMTF Redfish 协议规范](https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.23.0.html)
- [DMTF 资源说明](https://redfish.dmtf.org/schemas/DSP2046_2020.4.html)

`inventory.py` 字段带 `MOCK` / `synthetic`。不编造 Huawei OEM。`--scenario multi-system` / `paginated` 只测鲁棒性。

| 参数 | 模拟内容 |
| --- | --- |
| `--profile x86` | 2288H V5 风格标签，2 个合成 x86 CPU |
| `--profile arm` | TaiShan 200 风格标签，2 个合成 ARM CPU |
| 两组共有 | 256 GiB 内存（8×32 GiB）、2 块 960 GB SSD、1 个 RAID1 逻辑卷、2 个 10G 主机网口、独立管理口 |
| `--scenario healthy` | 完整清单，默认 / Japan E2E |
| `--scenario partial` | Storage 集合返回 404 |
| `--scenario unauthorized` | 服务根可访问；保护资源和登录返回 401 |
| `--scenario unavailable` | Systems 集合返回 503 + Retry-After |
| `--scenario multi-system` | 两个 System（采集器会拒绝：必须恰好一个 ComputerSystem） |
| `--scenario paginated` | 内存集合分页 |

本机 CLI **默认仍只监听 `127.0.0.1`**。容器通过 `--bind 0.0.0.0` 对外。

```bash
cd agents/stargazer/tests/collect_fixtures/huawei_redfish_target
export REDFISH_MOCK_USERNAME=mock-reader
read -s REDFISH_MOCK_PASSWORD
export REDFISH_MOCK_PASSWORD
REDFISH_MOCK_TLS_DIR=$(mktemp -d /tmp/redfish-mock-tls.XXXXXX)
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$REDFISH_MOCK_TLS_DIR/key.pem" \
  -out "$REDFISH_MOCK_TLS_DIR/cert.pem" -config tls.cnf
python3 mock_server.py --profile x86 --scenario healthy \
  --cert "$REDFISH_MOCK_TLS_DIR/cert.pem" --key "$REDFISH_MOCK_TLS_DIR/key.pem"
```

默认：`https://127.0.0.1:18443/redfish/v1/`。其它容器不能用这个环回地址。

```bash
python3 mock_server.py --http --port 18080 --profile arm --scenario paginated
```

## 接口行为

- `GET /redfish/v1/`：公开服务根。
- 清单 GET：HTTP Basic 或 `X-Auth-Token`。
- `POST /redfish/v1/SessionService/Sessions`：201 + `X-Auth-Token`；会话内存 60 秒，最多 16 个。
- PATCH / PUT / 硬件 DELETE / 电源 POST：405。
- `X-Mock-Data: synthetic-not-hardware-verified`。不记密码、token、请求体。
- 并发最多 8；socket 超时 3 秒；登录体最多 4 KiB。

## 新鲜验证

```bash
agents/stargazer/.venv/bin/python -m unittest discover \
  -s agents/stargazer/tests/collect_fixtures/huawei_redfish_target -p 'test_*.py' -v
```

测试起真实环回 HTTP/HTTPS 并在结束后关闭。覆盖两组清单稳定读取、CPU 架构、401/404/503、Basic/Token、以及 `--bind 0.0.0.0` 仍可从环回访问。这不是 CMDB 入库或生产 collector 验收。

## 当前插件实现范围

1. 入口：`physcial_server_redfish`，驱动 `protocol`。
2. `collection_protocol=redfish` 进入 Redfish 采集器。
3. `physcial_server.inst_name` 取采集目标 IP。
4. 第一阶段只读唯一 `ComputerSystem` 的 `SerialNumber` / `Model` / `Manufacturer` / `AssetTag`。
5. 只允许 HTTPS、Basic Auth、目标 IP、同源 `/redfish/v1`；证书校验默认开，任务可关。
