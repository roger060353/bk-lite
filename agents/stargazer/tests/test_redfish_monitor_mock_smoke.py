# -*- coding: utf-8 -*-
"""对 Redfish 监控 mock 跑采集器，锁住插件全量指标与禁止 /Sensors。"""
import json
import sys
from pathlib import Path

import pytest

STARGAZER_ROOT = Path(__file__).resolve().parents[1]
if str(STARGAZER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARGAZER_ROOT))

from devtools.redfish_monitor_mock.inventory import EXPECTED_METRICS, build_inventory  # noqa: E402
from devtools.redfish_monitor_mock.server import DEFAULT_PASSWORD, DEFAULT_USERNAME, RedfishMonitorMockServer  # noqa: E402
from devtools.redfish_monitor_mock.smoke import (  # noqa: E402
    PLUGIN_METRICS,
    assert_collect_text,
    assert_plugin_metric_set,
    collect_against,
)
from tasks.collectors.redfish_collector import FORBIDDEN_URI_PARTS, RedfishCollector, RedfishMonitorError  # noqa: E402


def test_redfish_plugin_metric_names_match_mock_checklist():
    metrics = json.loads(PLUGIN_METRICS.read_text(encoding="utf-8"))
    names = assert_plugin_metric_set(metrics)
    assert "redfish_sel_" not in "".join(names)
    assert metrics["plugin"] == "Hardware Server Redfish"


def test_inventory_exposes_monitor_paths_and_optional_sensors():
    resources = build_inventory()
    assert "/redfish/v1/Systems" in resources
    assert "/redfish/v1/Chassis/Chassis.Embedded.1/Thermal" in resources
    assert "/redfish/v1/Chassis/Chassis.Embedded.1/Power" in resources
    assert "/redfish/v1/Chassis/Chassis.Embedded.1/Sensors" in resources
    chassis = resources["/redfish/v1/Chassis/Chassis.Embedded.1"]
    assert chassis["Thermal"]["@odata.id"].endswith("/Thermal")
    assert chassis["Power"]["@odata.id"].endswith("/Power")
    assert chassis["Sensors"]["@odata.id"].endswith("/Sensors")
    system = resources["/redfish/v1/Systems/System.Embedded.1"]
    assert "Processors" not in system
    assert "Memory" not in system
    assert "EthernetInterfaces" not in system
    assert "/sensors" in FORBIDDEN_URI_PARTS


@pytest.mark.asyncio
async def test_redfish_collector_scrapes_all_monitor_metrics_from_https_mock():
    with RedfishMonitorMockServer(
        host="127.0.0.1",
        port=0,
        username=DEFAULT_USERNAME,
        password=DEFAULT_PASSWORD,
        tls=True,
    ) as server:
        text = await collect_against(server)
        assert_collect_text(text)
        assert str(server.port) not in DEFAULT_PASSWORD


@pytest.mark.asyncio
async def test_redfish_mock_rejects_bad_password():
    with RedfishMonitorMockServer(host="127.0.0.1", port=0, tls=True) as server:
        collector = RedfishCollector(
            {
                "host": "127.0.0.1",
                "port": server.port,
                "username": server.username,
                "password": "wrong-password",
                "verify_tls": False,
            }
        )
        with pytest.raises(RedfishMonitorError, match="authentication failed"):
            await collector.collect()


def test_redfish_collector_still_blocks_sensors_uri():
    collector = RedfishCollector({"host": "127.0.0.1", "username": "redfish", "password": "RedfishMon1"})
    with pytest.raises(RedfishMonitorError, match="not allowed"):
        collector._resource_url("/redfish/v1/Chassis/Chassis.Embedded.1/Sensors")
