# H3C / HP Comware SSH mock（OPS ONLY）

**不要合入产品 master。** Japan CMDB `network_config_file` E2E 用的最小 Comware CLI 桩，跑在 docker 网 `bklite-prod`。本目录可整包拷走后 `docker compose build`。

## 给采集任务填的值

| 字段 | 值 | 说明 |
|---|---|---|
| CMDB **brand** | `H3C` | 也会认 `HP Comware` / `Hewlett-Packard`。解析成 `device_type=hp_comware` |
| Scrapli **platform** | `hp_comware` | `network_config_file` 对 H3C 的映射 |
| 采集命令 | `display current-configuration` 与 `display version`（可各占一行） | 也接受 `show running-config` / `show version` |
| username | `admin` | SSH |
| password | `Admin@h3c` | SSH；**无 enable / 特权密码** |
| 容器内端口 | `22` | 同网 `bklite-prod` 上的 Stargazer / 采集器填这个 |
| 宿主机映射 | `2223 -> 22` | 从宿主机 `ssh` / probe 用 `2223` |
| 分页关闭 | `screen-length disable` | 插件 + scrapli `on_open` 会发；mock 空成功回包 |

`brand=H3C` → `resolve_device_type` → `hp_comware` → `SCRAPLI_PLATFORM_BY_DEVICE_TYPE["hp_comware"] == "hp_comware"`。

## 凭据（务必看清）

```
username: admin
password: Admin@h3c
```

不要把这组密码写进生产 CMDB 以外的密钥库。这是 E2E 桩账号。

## 构建与运行（Japan docker 网）

在本目录：

```bash
# 网已存在则跳过；本地没有时先建同名外部网
docker network inspect bklite-prod >/dev/null 2>&1 || docker network create bklite-prod

docker compose build
docker compose up -d
# 若只有 docker engine、没有 compose 插件：
# docker build -t h3c-comware-mock:ops .
# docker run -d --name h3c-comware-mock --hostname mock-h3c --network bklite-prod -p 2223:22 h3c-comware-mock:ops

# 容器在 bklite-prod 上的 IP（采集任务填这个 IP，端口 22）
docker inspect -f '{{range $name, $net := .NetworkSettings.Networks}}{{$name}} {{$net.IPAddress}}{{"\n"}}{{end}}' h3c-comware-mock
```

镜像名：`h3c-comware-mock:ops`。容器名：`h3c-comware-mock`。

只构建、不走 compose：

```bash
docker build -t h3c-comware-mock:ops .
docker run -d --name h3c-comware-mock --hostname mock-h3c \
  --network bklite-prod -p 2223:22 h3c-comware-mock:ops
```

已有容器、需要事后挂网：

```bash
docker network connect bklite-prod h3c-comware-mock
```

停掉：

```bash
docker compose down
```

## 探测

宿主机（映射口）：

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -p 2223 admin@127.0.0.1
# password: Admin@h3c
# 提示符: <MOCK-H3C>
# display current-configuration
# display version
# quit
```

同 docker 网内（采集器 / 另一容器）：

```bash
ssh -o StrictHostKeyChecking=no -p 22 admin@<bklite-prod-IP>
```

Scrapli（与插件相同：`platform=hp_comware` + `asyncssh`）：

```bash
# 在已装 scrapli[asyncssh] + scrapli-community 的环境，例如 agents/stargazer venv
python3 probe.py --host 127.0.0.1 --port 2223
python3 probe.py --host <bklite-prod-IP> --port 22 --via scrapli

# 若在仓库里且能 import stargazer 插件：
python3 probe.py --host 127.0.0.1 --port 2223 --via plugin
```

无 Docker 时先自测 CLI 分发：

```bash
python3 smoke.py
```

## CMDB 任务怎么配

1. 专业采集 / 网络配置文件，对象模型 `switch`（`router` 也可）。
2. 实例 **brand** 填 **`H3C`**（不要填 `hp_comware`；那是内部 device_type）。
3. IP = 容器在 `bklite-prod` 的地址；端口 **22**（采集器也在该网时不要填 2223）。
4. 凭据：`admin` / `Admin@h3c`，传输 SSH，不要填 enable 密码。
5. 命令：

```
display current-configuration
display version
```

成功回包应含 `sysname MOCK-H3C` 与 `H3C Comware`。

## CLI 覆盖

| 输入 | 行为 |
|---|---|
| 提示符 | 用户视图 `<MOCK-H3C>`；`system-view` 后 `[MOCK-H3C]` |
| `screen-length disable`（及 `screen-length 0`） | 成功、无正文 |
| `display current-configuration` / `dis cu` / `show running-config` | 跑 fixtures 配置 |
| `display version` / `dis ver` / `show version` | 跑 fixtures 版本 |
| `quit` / `exit` / `logout` | 用户视图断开；系统视图退回用户视图 |
| 未知命令 | `% Unrecognized command found at '^' position.`（Scrapli 会标 failed） |

## 运维如何拿到这份目录（不合主分支）

1. throwaway 分支（本 PR）：`agents/stargazer/devtools/h3c_comware_mock/`
2. 只拷本目录到 Japan 主机后 `docker compose build`
3. **不要**把该服务写进产品默认 compose / 发布清单

## 映射依据（仓库）

- `server/apps/cmdb/services/network_config_file_policy.py`：`h3c` → `hp_comware`
- `agents/stargazer/plugins/inputs/network_config_file/constants.py`：`hp_comware` → Scrapli `hp_comware`，分页 `screen-length disable`
