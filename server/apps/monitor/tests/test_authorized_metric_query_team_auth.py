"""query_by_metric_range 组织鉴权：cookie current_team + org join + instance_id。

浏览器 403「无权访问所选监控实例」的条件，不是 Current-Team 请求头。
get_current_team 只读 cookie / API Key 注入属性。
"""
from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.core.exceptions.base_app_exception import BaseAppException, ForbiddenException
from apps.monitor.models import Metric, MetricGroup, MonitorInstance, MonitorInstanceOrganization, MonitorObject, MonitorPlugin
from apps.monitor.services.authorized_metric_query import (
    AuthorizedMetricQueryError,
    AuthorizedMetricQueryService,
    _expand_permission_instance_aliases,
)
from apps.monitor.views.metrics_instance import MetricsInstanceViewSet
from apps.core.utils.team_utils import get_current_team

pytestmark = pytest.mark.django_db

CLEAN_ID = "172.18.0.12"
TUPLE_ID = "('172.18.0.12',)"


def _build_clean_instance_with_org(*, organization=1):
    monitor_object = MonitorObject.objects.create(
        name="Hardware Server",
        level="base",
        instance_id_keys=["instance_id"],
    )
    plugin = MonitorPlugin.objects.create(name="Hardware Server Redfish")
    group = MetricGroup.objects.create(
        monitor_object=monitor_object,
        monitor_plugin=plugin,
        name="Health",
    )
    metric = Metric.objects.create(
        monitor_object=monitor_object,
        monitor_plugin=plugin,
        metric_group=group,
        name="redfish_system_health",
        query="redfish_system_health_gauge{__$labels__}",
        instance_id_keys=["instance_id"],
        dimensions=[],
        unit="",
        data_type="Enum",
    )
    instance = MonitorInstance.objects.create(
        id=CLEAN_ID,
        name=CLEAN_ID,
        monitor_object=monitor_object,
    )
    MonitorInstanceOrganization.objects.create(monitor_instance=instance, organization=organization)
    return monitor_object, metric, instance


def _viewer():
    return SimpleNamespace(username="viewer", domain="domain.com", is_superuser=False)


def _service(mocker, *, permission, current_team="1"):
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.get_permission_rules",
        return_value=permission,
    )
    return AuthorizedMetricQueryService(
        user=_viewer(),
        current_team=current_team,
        include_children=False,
    )


def _range_payload(monitor_object, metric, instance_id=CLEAN_ID):
    return {
        "monitor_object_id": monitor_object.id,
        "metric_id": metric.id,
        "instance_ids": [instance_id],
        "start": 1000,
        "end": 61000,
        "step": "60s",
        "card_budget": True,
    }


@pytest.mark.unit
def test_get_current_team_ignores_current_team_header():
    request = SimpleNamespace(COOKIES={}, META={"HTTP_CURRENT_TEAM": "1"})
    assert get_current_team(request) is None
    request.COOKIES["current_team"] = "1"
    assert get_current_team(request) == "1"


@pytest.mark.unit
def test_expand_permission_instance_aliases_covers_tuple_and_clean():
    expanded = _expand_permission_instance_aliases(
        {"team": [], "instance": [{"id": TUPLE_ID, "permission": ["View"]}]}
    )
    ids = {item["id"] for item in expanded["instance"]}
    assert ids == {TUPLE_ID, CLEAN_ID}


def test_team_1_org_join_allows_clean_instance_after_tuple_cleanup(mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    service = _service(mocker, permission={"team": [1], "instance": []}, current_team="1")
    vm_query = mocker.patch(
        "apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range",
        return_value={"status": "success", "data": {"result": [{"metric": {"instance_id": CLEAN_ID}, "values": [[1, "1"]]}]}},
    )

    result = service.query_range(_range_payload(monitor_object, metric, CLEAN_ID))

    assert result["data"]["result"][0]["values"][0][1] == "1"
    assert TUPLE_ID not in vm_query.call_args.args[0]
    assert 'instance_id=~"172\\\\.18\\\\.0\\\\.12"' in vm_query.call_args.args[0]


def test_team_2_still_forbidden_when_org_is_1(mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    service = _service(mocker, permission={"team": [2], "instance": []}, current_team="2")
    vm_query = mocker.patch("apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range")

    with pytest.raises(AuthorizedMetricQueryError) as exc_info:
        service.query_range(_range_payload(monitor_object, metric, CLEAN_ID))

    assert exc_info.value.code == "monitor_instance_forbidden"
    vm_query.assert_not_called()


def test_tuple_instance_acl_still_allows_clean_pk_after_cleanup(mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    service = _service(
        mocker,
        permission={"team": [], "instance": [{"id": TUPLE_ID, "permission": ["View"]}]},
        current_team="1",
    )
    vm_query = mocker.patch(
        "apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range",
        return_value={"status": "success", "data": {"result": []}},
    )

    service.query_range(_range_payload(monitor_object, metric, CLEAN_ID))

    vm_query.assert_called_once()


def test_empty_permission_rules_forbidden_even_when_org_row_exists(mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    service = _service(mocker, permission={}, current_team="1")
    vm_query = mocker.patch("apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range")

    with pytest.raises(AuthorizedMetricQueryError) as exc_info:
        service.query_range(_range_payload(monitor_object, metric, CLEAN_ID))

    assert exc_info.value.code == "monitor_instance_forbidden"
    vm_query.assert_not_called()


def test_view_missing_cookie_is_current_team_required_not_instance_403(authenticated_user, mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    vm_query = mocker.patch("apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range")
    view = MetricsInstanceViewSet.as_view({"post": "query_by_metric_range"})
    request = APIRequestFactory().post(
        "/monitor/api/metrics_instance/query_by_metric_range/",
        _range_payload(monitor_object, metric),
        format="json",
        HTTP_CURRENT_TEAM="1",
    )
    force_authenticate(request, user=authenticated_user)

    with pytest.raises(BaseAppException, match="current_team is required"):
        view(request)

    vm_query.assert_not_called()


def test_view_cookie_team_1_and_org_1_hits(authenticated_user, mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.get_permission_rules",
        return_value={"team": [1], "instance": []},
    )
    vm_query = mocker.patch(
        "apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range",
        return_value={"status": "success", "data": {"result": [{"metric": {}, "values": [[1, "1"]]}]}},
    )
    view = MetricsInstanceViewSet.as_view({"post": "query_by_metric_range"})
    request = APIRequestFactory().post(
        "/monitor/api/metrics_instance/query_by_metric_range/",
        _range_payload(monitor_object, metric),
        format="json",
    )
    request.COOKIES["current_team"] = "1"
    force_authenticate(request, user=authenticated_user)

    response = view(request)

    assert response.status_code == 200
    vm_query.assert_called_once()


def test_view_cookie_team_2_is_instance_403(authenticated_user, mocker):
    monitor_object, metric, _ = _build_clean_instance_with_org(organization=1)
    mocker.patch(
        "apps.monitor.services.authorized_metric_query.get_permission_rules",
        return_value={"team": [2], "instance": []},
    )
    vm_query = mocker.patch("apps.monitor.services.authorized_metric_query.Metrics.get_metrics_range")
    view = MetricsInstanceViewSet.as_view({"post": "query_by_metric_range"})
    request = APIRequestFactory().post(
        "/monitor/api/metrics_instance/query_by_metric_range/",
        _range_payload(monitor_object, metric),
        format="json",
    )
    request.COOKIES["current_team"] = "2"
    force_authenticate(request, user=authenticated_user)

    with pytest.raises(ForbiddenException, match="无权访问所选监控实例"):
        view(request)

    vm_query.assert_not_called()
