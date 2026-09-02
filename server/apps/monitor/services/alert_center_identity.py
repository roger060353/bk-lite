"""监控告警推送告警中心时的 CMDB 身份映射。

与 `resolve_cmdb_model_id` 分离：后者把未知对象默认成 host，告警身份不能误标。
"""

from __future__ import annotations

from apps.cmdb.services.instance_identity import optional_inst_uuid
from apps.monitor.services.module_ingest import CMDB_MODEL_TO_MONITOR_OBJECT

# 监控对象名 → CMDB model_id。未命中返回空串，禁止回落 host。
_MONITOR_OBJECT_NAME_TO_CMDB_MODEL = {
    **{object_name: model_id for model_id, object_name in CMDB_MODEL_TO_MONITOR_OBJECT.items()},
    "host": "host",
    "switch": "switch",
    "router": "router",
    "firewall": "firewall",
    "loadbalance": "loadbalance",
    "LoadBalance": "loadbalance",
    "physcial_server": "physcial_server",
    "mysql": "mysql",
    "postgresql": "postgresql",
    "PostgreSQL": "postgresql",
    "mssql": "mssql",
    "influxdb": "influxdb",
    "Redis": "redis",
    "redis": "redis",
    "Nginx": "nginx",
    "nginx": "nginx",
}
_MONITOR_OBJECT_NAME_TO_CMDB_MODEL_CI = {name.lower(): model_id for name, model_id in _MONITOR_OBJECT_NAME_TO_CMDB_MODEL.items()}


def resolve_alert_cmdb_model(monitor_object_name: str | None) -> str:
    """把监控对象名映射为 CMDB model_id；未知对象保持空，避免误标 host。"""
    if not monitor_object_name:
        return ""
    name = str(monitor_object_name).strip()
    if not name:
        return ""
    return _MONITOR_OBJECT_NAME_TO_CMDB_MODEL.get(name) or _MONITOR_OBJECT_NAME_TO_CMDB_MODEL_CI.get(name.lower(), "")


def normalize_monitor_inst_uuid(cmdb_id: object) -> str:
    """仅接受规范 UUIDv4；旧数字图 ID 不得充当跨模块 inst_uuid。"""
    return optional_inst_uuid(cmdb_id) or ""
