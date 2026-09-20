# -*- coding: utf-8 -*-
"""校验 IPMI 监控 mock 目录与 Hardware Server IPMI 插件契约一致。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STARGAZER_ROOT = HERE.parents[1]
if str(STARGAZER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARGAZER_ROOT))

from devtools.ipmi_monitor_mock.catalog import (  # noqa: E402
    DISPLAY_METRICS,
    analog_sensors,
    discrete_sensors,
    expected_payload,
    expected_raw_series,
)
from devtools.ipmi_monitor_mock.render import render_emu, render_lan_conf, write_generated  # noqa: E402
from devtools.ipmi_monitor_mock.sdr import compact_sensor_record, full_sensor_record  # noqa: E402

PLUGIN_METRICS = (
    STARGAZER_ROOT.parents[1]
    / "server"
    / "apps"
    / "monitor"
    / "support-files"
    / "plugins"
    / "Telegraf"
    / "ipmi"
    / "hardware_server"
    / "metrics.json"
)


def assert_catalog_matches_plugin(metrics: dict | None = None) -> None:
    payload = metrics or json.loads(PLUGIN_METRICS.read_text(encoding="utf-8"))
    names = [item["name"] for item in payload["metrics"]]
    assert names == list(DISPLAY_METRICS)
    by_name = {item["name"]: item for item in payload["metrics"]}
    assert 'name=~"host_power"' in by_name["ipmi_chassis_power_state"]["query"]
    assert 'name="chassis_power_status"' in by_name["ipmi_chassis_power_state"]["query"]
    assert 'unit="watts"' in by_name["ipmi_power_watts"]["query"]
    assert 'unit="volts"' in by_name["ipmi_voltage_volts"]["query"]
    assert 'unit="rpm"' in by_name["ipmi_fan_speed_rpm"]["query"]
    assert 'unit="degrees_c"' in by_name["ipmi_temperature_celsius"]["query"]
    covered = {item["display_metric"] for item in expected_raw_series()}
    assert covered == set(DISPLAY_METRICS)
    units = {item["unit"] for item in analog_sensors()}
    assert units == {"degrees_c", "rpm", "volts", "watts"}
    assert any(item["name"] == "host_power" for item in discrete_sensors())
    assert any(item["name"] == "inlet_temp" for item in analog_sensors())


def assert_sdr_records() -> None:
    for sensor in analog_sensors():
        record = full_sensor_record(sensor)
        assert record[3] == 0x01
        assert record[7] == sensor["number"]
        assert record[21] == sensor["unit_code"]
        assert record[47] & 0x3F == len(sensor["name"])
        assert record[48:].decode("ascii") == sensor["name"]
        assert sensor["value"] > 0
    for sensor in discrete_sensors():
        record = compact_sensor_record(sensor)
        assert record[3] == 0x02
        assert record[26] & 0x3F == len(sensor["name"])
        assert record[27:].decode("ascii") == sensor["name"]


def assert_generated_files() -> None:
    lan = render_lan_conf()
    assert "addr 0.0.0.0 623" in lan
    assert "guid a123456789abcdefa123456789abcdef" in lan
    emu = render_emu()
    assert "mc_setbmc 0x20" in emu
    assert "sensor_add 0x20 0 0 35 0x6f event-only" in emu
    for sensor in analog_sensors() + discrete_sensors():
        assert f"main_sdr_add 0x20 " in emu
        assert sensor["name"]
        assert f"sensor_add 0x20 0 {sensor['number']}" in emu
    write_generated(HERE)
    assert (HERE / "ipmi.emu").read_text(encoding="utf-8") == emu


def main() -> int:
    assert_catalog_matches_plugin()
    assert_sdr_records()
    assert_generated_files()
    print("ipmi monitor mock catalog: ok")
    print(json.dumps(expected_payload()["raw_series"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
