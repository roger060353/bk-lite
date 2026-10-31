# -*- coding: utf-8 -*-
"""IPMI 2.0 Type 01 / Type 02 SDR 字节生成（DSP0266 对端是 Redfish；此处对齐 IPMI 2.0 表 43-1/43-2）。"""
from __future__ import annotations

from typing import Iterable


def s4(value: int) -> int:
    if not -8 <= value <= 7:
        raise ValueError(f"signed 4-bit out of range: {value}")
    return value & 0x0F


def s10_bytes(value: int) -> tuple[int, int]:
    if not -512 <= value <= 511:
        raise ValueError(f"signed 10-bit out of range: {value}")
    raw = value & 0x3FF
    return raw & 0xFF, (raw >> 8) & 0x03


def _id_bytes(name: str) -> bytes:
    encoded = name.encode("ascii")
    if not encoded or len(encoded) > 16:
        raise ValueError(f"SDR id string must be 1-16 ASCII bytes: {name!r}")
    return encoded


def full_sensor_record(sensor: dict) -> bytes:
    """Type 01 Full Sensor Record，给阈值型模拟量。"""
    name = _id_bytes(sensor["name"])
    rec = bytearray(48 + len(name))
    record_id = int(sensor["number"])
    rec[0] = record_id & 0xFF
    rec[1] = (record_id >> 8) & 0xFF
    rec[2] = 0x51
    rec[3] = 0x01
    rec[4] = len(rec) - 5
    rec[5] = 0x20
    rec[6] = 0x00
    rec[7] = int(sensor["number"])
    rec[8] = int(sensor["entity_id"])
    rec[9] = int(sensor["entity_instance"])
    rec[10] = 0x7F
    rec[11] = 0x68
    rec[12] = int(sensor["sensor_type"])
    rec[13] = int(sensor["event_type"])
    rec[14] = 0x80
    rec[15] = 0x0E
    rec[16] = 0x80
    rec[17] = 0x0E
    rec[18] = 0x3F
    rec[19] = 0x3F
    rec[20] = 0x00
    rec[21] = int(sensor["unit_code"])
    rec[22] = 0x00
    rec[23] = 0x00
    m_lsb, m_msb = s10_bytes(int(sensor["m"]))
    b_lsb, b_msb = s10_bytes(int(sensor["b"]))
    rec[24] = m_lsb
    rec[25] = m_msb << 6
    rec[26] = b_lsb
    rec[27] = b_msb << 6
    rec[28] = 0x00
    rec[29] = (s4(int(sensor["k2"])) << 4) | s4(int(sensor["k1"]))
    rec[30] = 0x00
    rec[31] = int(sensor["raw"]) & 0xFF
    rec[32] = 0x00
    rec[33] = 0x00
    rec[34] = 0xFF
    rec[35] = 0x00
    upper = int(sensor.get("upper_critical_raw") or 0) & 0xFF
    rec[36] = upper
    rec[37] = upper
    rec[38] = upper
    rec[39] = 0x00
    rec[40] = 0x00
    rec[41] = 0x00
    rec[42] = 0x00
    rec[43] = 0x00
    rec[44] = 0x00
    rec[45] = 0x00
    rec[46] = 0x00
    rec[47] = 0xC0 | len(name)
    rec[48:] = name
    return bytes(rec)


def compact_sensor_record(sensor: dict) -> bytes:
    """Type 02 Compact Sensor Record，给 host_power 离散量。"""
    name = _id_bytes(sensor["name"])
    rec = bytearray(27 + len(name))
    record_id = int(sensor["number"])
    rec[0] = record_id & 0xFF
    rec[1] = (record_id >> 8) & 0xFF
    rec[2] = 0x51
    rec[3] = 0x02
    rec[4] = len(rec) - 5
    rec[5] = 0x20
    rec[6] = 0x00
    rec[7] = int(sensor["number"])
    rec[8] = int(sensor["entity_id"])
    rec[9] = int(sensor["entity_instance"])
    rec[10] = 0x63
    rec[11] = 0x40
    rec[12] = int(sensor["sensor_type"])
    rec[13] = int(sensor["event_type"])
    rec[14] = 0x01
    rec[15] = 0x00
    rec[16] = 0x01
    rec[17] = 0x00
    rec[18] = 0x01
    rec[19] = 0x00
    rec[20] = 0x00
    rec[21] = 0x00
    rec[22] = 0x00
    rec[23] = 0x00
    rec[24] = 0x00
    rec[25] = 0x00
    rec[26] = 0xC0 | len(name)
    rec[27:] = name
    return bytes(rec)


def hex_bytes(record: bytes) -> str:
    return " ".join(f"0x{item:02x}" for item in record)


def records_for(sensors: Iterable[dict]) -> list[tuple[dict, bytes]]:
    out = []
    for sensor in sensors:
        if sensor["kind"] == "analog":
            out.append((sensor, full_sensor_record(sensor)))
        elif sensor["kind"] == "discrete":
            out.append((sensor, compact_sensor_record(sensor)))
        else:
            raise ValueError(f"unknown sensor kind: {sensor['kind']}")
    return out
