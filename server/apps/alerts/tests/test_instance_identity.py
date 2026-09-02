"""告警中心 inst_uuid / model / original_labels 契约测试。"""

from types import SimpleNamespace

import pytest

from apps.alerts.common.instance_identity import (
    LABEL_INST_UUID,
    LABEL_MODEL,
    LABEL_ORIGINAL_LABELS,
    extract_instance_identity,
    merge_stable_identity_labels,
    sanitize_original_labels,
)
from apps.alerts.serializers.alert import AlertModelSerializer
from apps.alerts.serializers.event import EventModelSerializer

INST_UUID = "63e4a531-b6bb-43cc-9eae-8eb8a09f795e"


@pytest.mark.unit
def test_sanitize_original_labels_drops_secrets_and_nested_values():
    cleaned = sanitize_original_labels(
        {
            "host": "db-1",
            "port": 3306,
            "password": "super-secret",
            "auth_token": "abc",
            "nested": {"k": "v"},
            "flags": ["a"],
            "": "x",
        }
    )
    assert cleaned == {"host": "db-1", "port": "3306"}


@pytest.mark.unit
def test_extract_prefers_labels_then_resource_uuid():
    obj = SimpleNamespace(
        labels={LABEL_INST_UUID: INST_UUID.upper(), LABEL_MODEL: "mysql"},
        resource_id="monitor-inst-1",
        resource_type="host",
        tags={"env": "prod"},
        raw_data={},
    )
    identity = extract_instance_identity(obj)
    assert identity[LABEL_INST_UUID] == INST_UUID
    assert identity[LABEL_MODEL] == "mysql"
    assert identity[LABEL_ORIGINAL_LABELS] == {"env": "prod"}


@pytest.mark.unit
def test_extract_ignores_numeric_resource_id_as_inst_uuid():
    obj = SimpleNamespace(
        labels={},
        resource_id="1704",
        resource_type="host",
        tags={},
        raw_data={},
    )
    identity = extract_instance_identity(obj)
    assert identity[LABEL_INST_UUID] == ""
    assert identity[LABEL_MODEL] == "host"


@pytest.mark.unit
def test_merge_keeps_identity_when_operational_labels_differ():
    first = SimpleNamespace(
        labels={
            "status": "active",
            LABEL_INST_UUID: INST_UUID,
            LABEL_MODEL: "mysql",
            LABEL_ORIGINAL_LABELS: {"ip": "10.0.0.1"},
        },
        resource_id=INST_UUID,
        resource_type="mysql",
        tags={"ip": "10.0.0.1"},
        raw_data={},
    )
    second = SimpleNamespace(
        labels={
            "status": "recovered",
            "operator": "admin",
            LABEL_INST_UUID: INST_UUID,
            LABEL_MODEL: "mysql",
            LABEL_ORIGINAL_LABELS: {"ip": "10.0.0.1"},
        },
        resource_id=INST_UUID,
        resource_type="mysql",
        tags={"ip": "10.0.0.1"},
        raw_data={},
    )
    merged = merge_stable_identity_labels([first, second], {})
    assert merged[LABEL_INST_UUID] == INST_UUID
    assert merged[LABEL_MODEL] == "mysql"
    assert merged[LABEL_ORIGINAL_LABELS] == {"ip": "10.0.0.1"}


@pytest.mark.unit
def test_alert_serializer_exposes_identity_fields():
    alert = SimpleNamespace(
        resource_id=INST_UUID,
        resource_type="postgresql",
        labels={LABEL_ORIGINAL_LABELS: {"port": "5432"}},
        tags={},
        raw_data={},
    )
    serializer = AlertModelSerializer.__new__(AlertModelSerializer)
    assert serializer.get_inst_uuid(alert) == INST_UUID
    assert serializer.get_model(alert) == "postgresql"
    assert serializer.get_original_labels(alert) == {"port": "5432"}


@pytest.mark.unit
def test_event_serializer_exposes_identity_fields():
    event = SimpleNamespace(
        resource_id="not-a-uuid",
        resource_type="",
        labels={},
        tags={"job": "mysql"},
        raw_data={LABEL_INST_UUID: INST_UUID, LABEL_MODEL: "mysql"},
    )
    serializer = EventModelSerializer.__new__(EventModelSerializer)
    assert serializer.get_inst_uuid(event) == INST_UUID
    assert serializer.get_model(event) == "mysql"
    assert serializer.get_original_labels(event) == {"job": "mysql"}
