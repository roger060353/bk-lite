# 监控 BMC mock（IPMI + Redfish）

OPS-ONLY。加入外部网络 `bklite-prod`，不要另起产品栈。

```bash
docker compose -f docker-compose.monitor-bmc-mocks.yml up -d --build
```

| 服务 | 网络内地址 | 凭据 |
|---|---|---|
| `ipmi-monitor-mock` | UDP/623 `lanplus` | `admin` / `IpmiMon1` |
| `redfish-monitor-mock` | HTTPS/443（自签） | `redfish` / `RedfishMon1`，校验证书关 |

完整操作手册与指标清单：

- [ipmi_monitor_mock/README.md](ipmi_monitor_mock/README.md)
- [redfish_monitor_mock/README.md](redfish_monitor_mock/README.md)
