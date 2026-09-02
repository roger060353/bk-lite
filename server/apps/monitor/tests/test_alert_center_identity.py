"""监控 → 告警中心身份映射测试。"""

from types import SimpleNamespace

import pytest

from apps.monitor.services.alert_center_identity import normalize_monitor_inst_uuid, resolve_alert_cmdb_model
from apps.monitor.services.alert_lifecycle_notify import AlertLifecycleNotifier

INST_UUID = "63e4a531-b6bb-43cc-9eae-8eb8a09f795e"


@pytest.mark.unit
def test_resolve_alert_cmdb_model_covers_middleware_and_does_not_default_host():
    assert resolve_alert_cmdb_model("Mysql") == "mysql"
    assert resolve_alert_cmdb_model("Postgres") == "postgresql"
    assert resolve_alert_cmdb_model("Redis") == "redis"
    assert resolve_alert_cmdb_model("Nginx") == "nginx"
    assert resolve_alert_cmdb_model("MSSQL") == "mssql"
    assert resolve_alert_cmdb_model("InfluxDB") == "influxdb"
    assert resolve_alert_cmdb_model("Host") == "host"
    assert resolve_alert_cmdb_model("unknown-obj") == ""
    assert resolve_alert_cmdb_model("") == ""


@pytest.mark.unit
def test_normalize_monitor_inst_uuid_rejects_legacy_numeric_cmdb_id():
    assert normalize_monitor_inst_uuid(INST_UUID.upper()) == INST_UUID
    assert normalize_monitor_inst_uuid("1704") == ""
    assert normalize_monitor_inst_uuid(None) == ""


@pytest.mark.unit
def test_payload_uses_cmdb_uuid_and_independent_title():
    notifier = AlertLifecycleNotifier(policy=SimpleNamespace(name="磁盘策略", organizations=[]))
    alert = SimpleNamespace(
        id="alert-1",
        policy_id=7,
        content="CPU 超阈值",
        level="warning",
        monitor_instance_id="inst-1",
        monitor_instance_name="db-1",
        value=1,
        status="active",
        start_event_time=None,
        end_event_time=None,
        dimensions={"instance": "10.0.0.8:3306", "password": "nope"},
        metric_instance_id="m-1",
    )
    payload = notifier._build_alert_center_payload(
        alert,
        "created",
        "",
        "",
        instance_org_map={},
        instance_identity_map={"inst-1": {"inst_uuid": INST_UUID, "model": "mysql"}},
    )
    assert payload["title"] == "磁盘策略"
    assert payload["description"] == "CPU 超阈值"
    assert payload["resource_id"] == "inst-1"
    assert payload["resource_type"] == "mysql"
    assert payload["inst_uuid"] == INST_UUID
    assert payload["model"] == "mysql"
    assert payload["original_labels"] == {"instance": "10.0.0.8:3306"}
    assert payload["labels"]["inst_uuid"] == INST_UUID
    assert payload["labels"]["original_labels"] == {"instance": "10.0.0.8:3306"}
    assert "password" not in payload["original_labels"]
