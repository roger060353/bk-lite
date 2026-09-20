"""硬件服务器实例指标卡契约：身份查找、包装查询、单位转换、响应整形。"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.serializers.json import DjangoJSONEncoder

from apps.monitor.models import Metric, MetricGroup, MonitorInstance, MonitorObject, MonitorPlugin
from apps.monitor.services.authorized_metric_query import AuthorizedMetricQueryError, AuthorizedMetricQueryService
from apps.monitor.services.metrics import Metrics
from apps.monitor.utils.dimension import candidate_instance_ids
from apps.monitor.views.metrics_instance import MetricsInstanceViewSet

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "support-files" / "plugins" / "Telegraf"
CLEAN_IPMI_ID = "172.18.0.14"
CLEAN_REDFISH_ID = "172.18.0.12"
TUPLE_IPMI_ID = "('172.18.0.14',)"
TUPLE_REDFISH_ID = "('172.18.0.12',)"


def _plugin_metrics(collect_type: str) -> list[dict]:
    payload = json.loads(
        (PLUGIN_ROOT / collect_type / "hardware_server" / "metrics.json").read_text(encoding="utf-8")
    )
    return payload["metrics"]


def _metric_by_name(collect_type: str, name: str) -> dict:
    return next(item for item in _plugin_metrics(collect_type) if item["name"] == name)


def _build_object_and_metric(metric_spec: dict, *, instance_id: str):
    monitor_object = MonitorObject.objects.create(
        name="Hardware Server",
        level="base",
        instance_id_keys=["instance_id"],
    )
    plugin = MonitorPlugin.objects.create(name=f"Hardware Server {metric_spec['name']}")
    group = MetricGroup.objects.create(
        monitor_object=monitor_object,
        monitor_plugin=plugin,
        name=metric_spec.get("metric_group") or "Power",
    )
    metric = Metric.objects.create(
        monitor_object=monitor_object,
        monitor_plugin=plugin,
        metric_group=group,
        name=metric_spec["name"],
        query=metric_spec["query"],
        instance_id_keys=metric_spec.get("instance_id_keys") or ["instance_id"],
        dimensions=metric_spec.get("dimensions") or [],
        unit=metric_spec.get("unit") or "",
        data_type=metric_spec.get("data_type") or "Number",
    )
    instance = MonitorInstance.objects.create(
        id=instance_id,
        name=instance_id,
        monitor_object=monitor_object,
    )
    return monitor_object, metric, instance


def _service(mocker, allowed_instance):
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.get_permission_rules",
        return_value={"data": "permission"},
    )
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.permission_filter",
        side_effect=lambda model, permission, **kwargs: model.objects.filter(id=allowed_instance.id),
    )
    return AuthorizedMetricQueryService(
        user=SimpleNamespace(username="viewer", domain="domain.com", is_superuser=False),
        current_team="1",
        include_children=False,
    )


def _two_voltage_series():
    return {
        "status": "success",
        "data": {
            "result": [
                {
                    "metric": {"instance_id": CLEAN_IPMI_ID, "name": "voltage_12v"},
                    "values": [[1_000, "12.1"], [1_060, "12.1"]],
                },
                {
                    "metric": {"instance_id": CLEAN_IPMI_ID, "name": "voltage_3_3v"},
                    "values": [[1_000, "3.3"], [1_060, "3.3"]],
                },
            ]
        },
    }


@pytest.mark.unit
def test_card_catalog_fields_do_not_use_display_fields_or_drop_non_enum():
    voltage = _metric_by_name("ipmi", "ipmi_voltage_volts")
    power = _metric_by_name("ipmi", "ipmi_power_watts")
    health = _metric_by_name("redfish", "redfish_system_health")
    consumed = _metric_by_name("redfish", "redfish_power_consumed_watts")
    manager = _metric_by_name("redfish", "redfish_manager_health")

    assert voltage["query"].count("__$labels__") == 2
    assert 'unit="volts"' in voltage["query"]
    assert 'name=~"voltage_.*"' in voltage["query"]
    assert voltage["data_type"] == "Number"
    assert voltage["unit"] == "volts"
    assert voltage["dimensions"] == [{"name": "name", "description": "name"}]
    assert "display_fields" not in voltage

    assert power["data_type"] == "Number"
    assert power["unit"] == "watts"
    assert power["dimensions"] == [{"name": "name", "description": "name"}]
    assert power["query"].count("__$labels__") == 2

    assert health["data_type"] == "Enum"
    assert health["dimensions"] == []
    assert health["query"] == (
        "redfish_system_health_gauge{instance_type='hardware_server', collect_type='redfish', __$labels__}"
    )
    assert manager["data_type"] == "Enum"
    assert manager["dimensions"] == []
    assert manager["query"] == (
        "redfish_manager_health_gauge{instance_type='hardware_server', collect_type='redfish', __$labels__}"
    )
    assert consumed["data_type"] == "Number"
    assert consumed["unit"] == "watts"
    assert consumed["dimensions"] == [{"name": "name", "description": "Power control name"}]
    assert consumed["query"] == (
        "redfish_power_consumed_watts_gauge{instance_type='hardware_server', collect_type='redfish', __$labels__}"
    )


@pytest.mark.django_db
def test_clean_pk_card_query_accepts_ui_clean_instance_id(mocker):
    spec = _metric_by_name("ipmi", "ipmi_voltage_volts")
    monitor_object, metric, instance = _build_object_and_metric(spec, instance_id=CLEAN_IPMI_ID)
    service = _service(mocker, instance)
    vm_query = mocker.patch(
        "apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range",
        return_value=_two_voltage_series(),
    )

    result = service.query_range(
        {
            "monitor_object_id": monitor_object.id,
            "metric_id": metric.id,
            "instance_ids": [CLEAN_IPMI_ID],
            "start": 1000,
            "end": 61000,
            "step": "60s",
            "card_budget": True,
        }
    )

    query = vm_query.call_args.args[0]
    assert TUPLE_IPMI_ID not in query
    assert 'instance_id=~"172\\\\.18\\\\.0\\\\.14"' in query
    assert query.startswith("avg(")
    assert "by (instance_id, name)" in query
    assert result["data"]["result"][0]["metric"]["name"] == "voltage_12v"
    assert result["data"]["result"][1]["metric"]["name"] == "voltage_3_3v"


@pytest.mark.django_db
def test_tuple_pk_card_query_still_accepts_ui_clean_instance_id(mocker):
    spec = _metric_by_name("redfish", "redfish_system_health")
    monitor_object, metric, instance = _build_object_and_metric(spec, instance_id=TUPLE_REDFISH_ID)
    service = _service(mocker, instance)
    vm_query = mocker.patch(
        "apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range",
        return_value={"status": "success", "data": {"result": []}},
    )

    service.query_range(
        {
            "monitor_object_id": monitor_object.id,
            "metric_id": metric.id,
            "instance_ids": [CLEAN_REDFISH_ID],
            "start": 1000,
            "end": 61000,
            "step": "60s",
            "card_budget": True,
        }
    )

    query = vm_query.call_args.args[0]
    assert TUPLE_REDFISH_ID not in query
    assert 'instance_id=~"172\\\\.18\\\\.0\\\\.12"' in query
    assert query == (
        'avg(redfish_system_health_gauge{instance_type=\'hardware_server\', '
        'collect_type=\'redfish\', instance_id=~"172\\\\.18\\\\.0\\\\.12"}) by (instance_id)'
    )


@pytest.mark.django_db
def test_dual_row_card_query_uses_logical_instance_id_not_tuple_label(mocker):
    spec = _metric_by_name("redfish", "redfish_power_consumed_watts")
    monitor_object, metric, clean = _build_object_and_metric(spec, instance_id=CLEAN_REDFISH_ID)
    tuple_row = MonitorInstance.objects.create(
        id=TUPLE_REDFISH_ID,
        name="tuple-row",
        monitor_object=monitor_object,
    )
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.get_permission_rules",
        return_value={"data": "permission"},
    )
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.permission_filter",
        side_effect=lambda model, permission, **kwargs: model.objects.filter(
            id__in=[clean.id, tuple_row.id]
        ),
    )
    service = AuthorizedMetricQueryService(
        user=SimpleNamespace(username="viewer", domain="domain.com", is_superuser=False),
        current_team="1",
        include_children=False,
    )
    vm_query = mocker.patch(
        "apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range",
        return_value={"status": "success", "data": {"result": []}},
    )

    for raw_id in (CLEAN_REDFISH_ID, TUPLE_REDFISH_ID):
        vm_query.reset_mock()
        service.query_range(
            {
                "monitor_object_id": monitor_object.id,
                "metric_id": metric.id,
                "instance_ids": [raw_id],
                "start": 1000,
                "end": 61000,
                "step": "60s",
                "card_budget": True,
            }
        )
        query = vm_query.call_args.args[0]
        assert TUPLE_REDFISH_ID not in query
        assert 'instance_id=~"172\\\\.18\\\\.0\\\\.12"' in query
        assert "by (instance_id, name)" in query


@pytest.mark.django_db
def test_clean_pk_missing_row_still_forbidden(mocker):
    spec = _metric_by_name("ipmi", "ipmi_power_watts")
    monitor_object, metric, instance = _build_object_and_metric(spec, instance_id=CLEAN_IPMI_ID)
    service = _service(mocker, instance)
    vm_query = mocker.patch("apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range")

    with pytest.raises(AuthorizedMetricQueryError) as exc_info:
        service.query_range(
            {
                "monitor_object_id": monitor_object.id,
                "metric_id": metric.id,
                "instance_ids": ["172.18.0.99"],
                "start": 1000,
                "end": 61000,
                "step": "60s",
            }
        )

    assert exc_info.value.code == "monitor_instance_forbidden"
    vm_query.assert_not_called()


@pytest.mark.unit
def test_card_unit_conversion_keeps_multi_series_voltage_values():
    converted = MetricsInstanceViewSet._apply_unit_conversion(
        _two_voltage_series(),
        "volts",
    )
    series = converted["data"]["result"]
    assert len(series) == 2
    assert [point[1] for point in series[0]["values"]] == ["12.1", "12.1"]
    assert [point[1] for point in series[1]["values"]] == ["3.3", "3.3"]
    assert converted["data"]["source_unit"] == "volts"


@pytest.mark.unit
def test_enum_source_unit_does_not_drop_health_values():
    raw = {
        "status": "success",
        "data": {
            "result": [
                {
                    "metric": {"instance_id": CLEAN_REDFISH_ID},
                    "values": [[1_000, "1"], [1_060, "1"]],
                }
            ]
        },
    }
    unit = _metric_by_name("redfish", "redfish_system_health")["unit"]
    converted = MetricsInstanceViewSet._apply_unit_conversion(raw, unit)
    assert float(converted["data"]["result"][0]["values"][0][1]) == 1.0


@pytest.mark.unit
def test_candidate_ids_cover_clean_and_tuple_dual_row():
    assert candidate_instance_ids(CLEAN_REDFISH_ID) == [TUPLE_REDFISH_ID, CLEAN_REDFISH_ID]
    assert candidate_instance_ids(TUPLE_REDFISH_ID) == [TUPLE_REDFISH_ID, CLEAN_REDFISH_ID]


# 前端契约（metric-views + renderChart + LineChart）：
# 1. axios 拦截器拆 WebUtils 后得到 VictoriaMetrics 体 {status, data:{result, series_budget, unit}}
# 2. chartData = response.data.result
# 3. renderChart 只读 item.values，跳过 !Number.isFinite(parseFloat(value))
# 4. LineChart 空态判定是 !!viewData.length，不按 series 数或 dimensions 过滤
RANGE_START_MS = 1_700_000_000_000
RANGE_END_MS = 1_700_000_120_000
RANGE_START_S = RANGE_START_MS / 1000
RANGE_MID_S = RANGE_START_S + 60


def _health_vm_payload():
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"instance_id": CLEAN_REDFISH_ID},
                    "values": [[RANGE_START_S, "1"], [RANGE_MID_S, "1"]],
                }
            ],
        },
    }


def _voltage_vm_payload(*, instance_id: str, values: tuple[str, str]):
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"instance_id": instance_id, "name": "12V"},
                    "values": [[RANGE_START_S, values[0]], [RANGE_MID_S, values[0]]],
                },
                {
                    "metric": {"instance_id": instance_id, "name": "3.3V"},
                    "values": [[RANGE_START_S, values[1]], [RANGE_MID_S, values[1]]],
                },
            ],
        },
    }


def _frontend_chart_points(vm_body: dict) -> list[tuple[dict, float, float]]:
    """对齐 web handleResponse → data.result → renderChart 的有限值过滤。"""
    series = ((vm_body.get("data") or {}).get("result")) or []
    points = []
    for item in series:
        for pair in item.get("values") or []:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            timestamp, value = pair[0], pair[1]
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric != numeric:
                continue
            points.append((item.get("metric") or {}, float(timestamp), numeric))
    return points


def _shape_card_range(mocker, vm_payload: dict, source_unit: str) -> dict:
    mocker.patch(
        "apps.monitor.services.metrics.VictoriaMetricsAPI.query_range",
        return_value=copy.deepcopy(vm_payload),
    )
    raw = Metrics.get_metrics_range(
        "avg(dummy) by (instance_id, name)",
        RANGE_START_MS,
        RANGE_END_MS,
        "60s",
        card_budget=True,
    )
    converted = MetricsInstanceViewSet._apply_unit_conversion(raw, source_unit)
    json.dumps(converted, cls=DjangoJSONEncoder)
    return converted


@pytest.mark.unit
def test_card_range_response_keeps_health_and_multi_series_voltage(mocker):
    health_unit = _metric_by_name("redfish", "redfish_system_health")["unit"]
    health = _shape_card_range(mocker, _health_vm_payload(), health_unit)
    health_points = _frontend_chart_points(health)
    health_budget = health["data"]["series_budget"]

    redfish_voltage = _shape_card_range(
        mocker,
        _voltage_vm_payload(instance_id=CLEAN_REDFISH_ID, values=("12.1", "3.31")),
        "volts",
    )
    ipmi_voltage = _shape_card_range(
        mocker,
        _voltage_vm_payload(instance_id=CLEAN_IPMI_ID, values=("12.1", "3.3")),
        "volts",
    )

    assert health["status"] == "success"
    assert len(health["data"]["result"]) == 1
    assert {round(point[2], 3) for point in health_points} == {1.0}
    assert health_budget["truncated"] is False
    assert health_budget["limit"] == Metrics.CARD_QUERY_MAX_SERIES

    for payload, expected in (
        (redfish_voltage, {12.1, 3.31}),
        (ipmi_voltage, {12.1, 3.3}),
    ):
        series = payload["data"]["result"]
        points = _frontend_chart_points(payload)
        names = {item["metric"]["name"] for item in series}
        assert payload["status"] == "success"
        assert len(series) == 2
        assert names == {"12V", "3.3V"}
        assert {round(point[2], 3) for point in points} == expected
        assert payload["data"]["series_budget"]["truncated"] is False
        assert payload["data"]["series_budget"]["limit"] == Metrics.CARD_QUERY_MAX_SERIES
        assert all("values" in item and "value" not in item for item in series)
