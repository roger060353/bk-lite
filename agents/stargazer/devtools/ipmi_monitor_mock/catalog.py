# -*- coding: utf-8 -*-
"""IPMI 监控 mock 的传感器目录。

对齐监控插件 Hardware Server IPMI：Telegraf `inputs.ipmi_sensor`
只采 `sdr` + `chassis_power_status`。展示指标按 unit 过滤原始
`ipmi_sensor_value` / `ipmi_sensor_status`。

本目录同时驱动 OpenIPMI `ipmi_sim` SDR 与测试专家核对清单。
"""
from __future__ import annotations

from typing import Any

# Telegraf ipmi_sensor 把 ipmitool 单位串映射为这些 tag。
# 监控 metrics.json 的 query 按这些 unit 过滤。
TELEGRAF_UNIT = {
    "celsius": "degrees_c",
    "rpm": "rpm",
    "volts": "volts",
    "watts": "watts",
}

# IPMI 2.0 Table 43-15 Sensor Unit Type Codes
IPMI_UNIT_CODE = {
    "degrees_c": 0x01,
    "volts": 0x04,
    "watts": 0x06,
    "rpm": 0x12,
}

# IPMI sensor type codes (Table 42-3)
SENSOR_TYPE = {
    "temperature": 0x01,
    "voltage": 0x02,
    "fan": 0x04,
    "other_units": 0x0B,
    "acpi_power": 0x22,
}

# Entity IDs (Table 43-13)
ENTITY = {
    "processor": 0x03,
    "system_board": 0x07,
    "power_supply": 0x0A,
    "fan": 0x1D,
}

DISPLAY_METRICS = (
    "ipmi_chassis_power_state",
    "ipmi_power_watts",
    "ipmi_voltage_volts",
    "ipmi_fan_speed_rpm",
    "ipmi_temperature_celsius",
)

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "IpmiMon1"
DEFAULT_PROTOCOL = "lanplus"
DEFAULT_PORT = 623
DEFAULT_PRIVILEGE = "admin"


def _threshold(m: int, b: int, k1: int, k2: int, raw: int) -> float:
    return round((m * raw + b * (10**k1)) * (10.0**k2), 6)


def analog(
    *,
    number: int,
    name: str,
    kind: str,
    unit: str,
    raw: int,
    m: int = 1,
    b: int = 0,
    k1: int = 0,
    k2: int = 0,
    entity: str = "system_board",
    entity_instance: int = 1,
    upper_critical_raw: int | None = None,
) -> dict[str, Any]:
    telegraf_unit = TELEGRAF_UNIT[unit] if unit in TELEGRAF_UNIT else unit
    value = _threshold(m, b, k1, k2, raw)
    item = {
        "kind": "analog",
        "number": number,
        "name": name,
        "sensor_type": SENSOR_TYPE[kind],
        "event_type": 0x01,
        "unit": telegraf_unit,
        "unit_code": IPMI_UNIT_CODE[telegraf_unit],
        "entity_id": ENTITY[entity],
        "entity_instance": entity_instance,
        "raw": raw,
        "m": m,
        "b": b,
        "k1": k1,
        "k2": k2,
        "value": value,
        "ipmitool_unit": {
            "degrees_c": "degrees C",
            "rpm": "RPM",
            "volts": "Volts",
            "watts": "Watts",
        }[telegraf_unit],
        "display_metric": {
            "degrees_c": "ipmi_temperature_celsius",
            "rpm": "ipmi_fan_speed_rpm",
            "volts": "ipmi_voltage_volts",
            "watts": "ipmi_power_watts",
        }[telegraf_unit],
    }
    if upper_critical_raw is not None:
        item["upper_critical_raw"] = upper_critical_raw
        item["upper_critical"] = _threshold(m, b, k1, k2, upper_critical_raw)
    return item


def discrete(
    *,
    number: int,
    name: str,
    kind: str,
    bit: int = 0,
    entity: str = "system_board",
    entity_instance: int = 1,
) -> dict[str, Any]:
    return {
        "kind": "discrete",
        "number": number,
        "name": name,
        "sensor_type": SENSOR_TYPE[kind],
        "event_type": 0x6F,
        "entity_id": ENTITY[entity],
        "entity_instance": entity_instance,
        "bit": bit,
        "ipmi_sensor_status": 1,
        "display_metric": "ipmi_chassis_power_state",
    }


# 传感器编号 0 留给 ipmi_sim 看门狗。
SENSORS: tuple[dict[str, Any], ...] = (
    analog(
        number=1,
        name="inlet_temp",
        kind="temperature",
        unit="celsius",
        raw=22,
        entity="system_board",
        entity_instance=1,
        upper_critical_raw=47,
    ),
    analog(
        number=2,
        name="cpu1_temp",
        kind="temperature",
        unit="celsius",
        raw=45,
        entity="processor",
        entity_instance=1,
        upper_critical_raw=98,
    ),
    analog(
        number=3,
        name="exhaust_temp",
        kind="temperature",
        unit="celsius",
        raw=33,
        entity="system_board",
        entity_instance=2,
        upper_critical_raw=80,
    ),
    analog(
        number=4,
        name="fan1",
        kind="fan",
        unit="rpm",
        raw=42,
        m=1,
        k2=2,
        entity="fan",
        entity_instance=1,
    ),
    analog(
        number=5,
        name="fan2",
        kind="fan",
        unit="rpm",
        raw=39,
        m=1,
        k2=2,
        entity="fan",
        entity_instance=2,
    ),
    analog(
        number=6,
        name="pwr_consumption",
        kind="other_units",
        unit="watts",
        raw=28,
        m=1,
        k2=1,
        entity="system_board",
        entity_instance=3,
    ),
    analog(
        number=7,
        name="voltage_12v",
        kind="voltage",
        unit="volts",
        raw=121,
        m=1,
        k2=-1,
        entity="system_board",
        entity_instance=4,
    ),
    analog(
        number=8,
        name="voltage_3_3v",
        kind="voltage",
        unit="volts",
        raw=33,
        m=1,
        k2=-1,
        entity="system_board",
        entity_instance=5,
    ),
    discrete(
        number=9,
        name="host_power",
        kind="acpi_power",
        bit=0,
        entity="system_board",
        entity_instance=6,
    ),
)

CHASSIS_POWER_STATUS = {
    "name": "chassis_power_status",
    "command": "chassis power status",
    "ipmi_sensor_value": 1,
    "display_metric": "ipmi_chassis_power_state",
    "note": "Telegraf sensors=['chassis_power_status']：开机=1，关机=0。展示指标用 2-value 映射到 1/正常、2/异常。",
}


def analog_sensors() -> list[dict[str, Any]]:
    return [item for item in SENSORS if item["kind"] == "analog"]


def discrete_sensors() -> list[dict[str, Any]]:
    return [item for item in SENSORS if item["kind"] == "discrete"]


def expected_raw_series() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in analog_sensors():
        rows.append(
            {
                "metric": "ipmi_sensor_value",
                "name": item["name"],
                "unit": item["unit"],
                "value": item["value"],
                "status": "ok",
                "display_metric": item["display_metric"],
            }
        )
    for item in discrete_sensors():
        rows.append(
            {
                "metric": "ipmi_sensor_status",
                "name": item["name"],
                "value": item["ipmi_sensor_status"],
                "status": "ok",
                "display_metric": item["display_metric"],
            }
        )
    rows.append(
        {
            "metric": "ipmi_sensor_value",
            "name": CHASSIS_POWER_STATUS["name"],
            "value": CHASSIS_POWER_STATUS["ipmi_sensor_value"],
            "display_metric": CHASSIS_POWER_STATUS["display_metric"],
        }
    )
    return rows


def expected_payload() -> dict[str, Any]:
    return {
        "plugin": "Hardware Server IPMI",
        "collect_type": "ipmi",
        "instance_type": "hardware_server",
        "transport": {
            "protocol": DEFAULT_PROTOCOL,
            "port": DEFAULT_PORT,
            "proto": "udp",
            "privilege": DEFAULT_PRIVILEGE,
        },
        "credentials": {
            "username": DEFAULT_USERNAME,
            "password": DEFAULT_PASSWORD,
        },
        "telegraf_sensors": ["sdr", "chassis_power_status"],
        "display_metrics": list(DISPLAY_METRICS),
        "raw_series": expected_raw_series(),
        "sensors": list(SENSORS),
        "chassis_power_status": CHASSIS_POWER_STATUS,
    }
