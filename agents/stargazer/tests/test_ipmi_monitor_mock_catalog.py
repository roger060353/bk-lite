# -*- coding: utf-8 -*-
"""锁住 IPMI 监控 mock 与 Hardware Server IPMI 插件的指标/单位契约。"""
import json
import sys
from pathlib import Path

STARGAZER_ROOT = Path(__file__).resolve().parents[1]
if str(STARGAZER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARGAZER_ROOT))

from devtools.ipmi_monitor_mock.catalog import DISPLAY_METRICS, expected_payload  # noqa: E402
from devtools.ipmi_monitor_mock.smoke import (  # noqa: E402
    PLUGIN_METRICS,
    assert_catalog_matches_plugin,
    assert_generated_files,
    assert_sdr_records,
)


def test_ipmi_plugin_display_metrics_match_mock_catalog():
    metrics = json.loads(PLUGIN_METRICS.read_text(encoding="utf-8"))
    assert_catalog_matches_plugin(metrics)
    assert metrics["plugin"] == "Hardware Server IPMI"
    assert list(DISPLAY_METRICS) == [item["name"] for item in metrics["metrics"]]


def test_ipmi_sdr_records_carry_monitor_units_and_host_power():
    assert_sdr_records()
    payload = expected_payload()
    by_metric = {}
    for row in payload["raw_series"]:
        by_metric.setdefault(row["display_metric"], []).append(row)
    assert {row["unit"] for row in by_metric["ipmi_temperature_celsius"]} == {"degrees_c"}
    assert {row["unit"] for row in by_metric["ipmi_fan_speed_rpm"]} == {"rpm"}
    assert {row["unit"] for row in by_metric["ipmi_voltage_volts"]} == {"volts"}
    assert {row["unit"] for row in by_metric["ipmi_power_watts"]} == {"watts"}
    names = {row["name"] for row in by_metric["ipmi_chassis_power_state"]}
    assert names == {"host_power", "chassis_power_status"}
    assert payload["transport"] == {"protocol": "lanplus", "port": 623, "proto": "udp", "privilege": "admin"}


def test_ipmi_sim_files_render_official_shape():
    assert_generated_files()
    emu = (STARGAZER_ROOT / "devtools" / "ipmi_monitor_mock" / "ipmi.emu").read_text(encoding="utf-8")
    assert "main_sdr_add 0x20" in emu
    assert "host_power" in emu
    assert "inlet_temp" in emu
    assert "pwr_consumption" in emu
