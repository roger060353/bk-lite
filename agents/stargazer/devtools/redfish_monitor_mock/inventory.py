# -*- coding: utf-8 -*-
"""DMTF 风格 Redfish 监控夹具。

只覆盖 Hardware Server Redfish 采集器实际抓取的资源：
Systems / Managers / Chassis + Thermal + Power、Storage/Drives、
Chassis NetworkAdapters/Ports。

/Chassis/1/Sensors 按 DSP0266 给出只读集合，但 stargazer 采集器
FORBIDDEN_URI_PARTS 含 `/sensors`，监控刮取不会跟随。
不提供 Processors / Memory / EthernetInterfaces / LogServices
（采集器同样禁止，那些是 CMDB 资产路径）。
"""
from __future__ import annotations

from typing import Any

SYSTEM_ID = "System.Embedded.1"
CHASSIS_ID = "Chassis.Embedded.1"
MANAGER_ID = "iDRAC.Embedded.1"
STORAGE_ID = "RAID.Integrated.1-1"
ADAPTER_ID = "NIC.Integrated.1"
BIOS_VERSION = "2.18.1"
BMC_FIRMWARE = "7.00.00"

EXPECTED_METRICS = (
    "redfish_system_health",
    "redfish_system_power_state",
    "redfish_manager_health",
    "redfish_processor_health_rollup",
    "redfish_memory_health_rollup",
    "redfish_temperature_celsius",
    "redfish_inlet_temperature_celsius",
    "redfish_inlet_temperature_upper_critical_celsius",
    "redfish_fan_speed",
    "redfish_power_consumed_watts",
    "redfish_psu_health",
    "redfish_psu_input_watts",
    "redfish_psu_output_watts",
    "redfish_psu_capacity_watts",
    "redfish_psu_delivering",
    "redfish_psu_redundant",
    "redfish_power_limit_watts",
    "redfish_power_over_limit",
    "redfish_firmware_info",
    "redfish_temperature_upper_critical_celsius",
    "redfish_fan_health",
    "redfish_psu_input_voltage",
    "redfish_voltage_volts",
    "redfish_storage_health",
    "redfish_drive_health",
    "redfish_drive_present_count",
    "redfish_drive_life_percent",
    "redfish_storage_controller_health",
    "redfish_nic_health",
    "redfish_nic_port_health",
    "redfish_nic_port_link_up",
    "redfish_nic_port_speed_mbps",
)

EXPECTED_VALUES = {
    "redfish_system_health": 1,
    "redfish_system_power_state": 1,
    "redfish_manager_health": 1,
    "redfish_processor_health_rollup": 1,
    "redfish_memory_health_rollup": 1,
    "redfish_inlet_temperature_celsius": 22,
    "redfish_inlet_temperature_upper_critical_celsius": 47,
    "redfish_power_consumed_watts": 280,
    "redfish_power_limit_watts": 750,
    "redfish_power_over_limit": 0,
    "redfish_psu_redundant": 1,
    "redfish_drive_present_count": 2,
    "redfish_firmware_info": 1,
}


def _link(path: str) -> dict[str, str]:
    return {"@odata.id": path}


def _status(health: str = "OK", state: str = "Enabled", rollup: str | None = None) -> dict[str, str]:
    payload = {"Health": health, "State": state}
    if rollup:
        payload["HealthRollup"] = rollup
    return payload


def _collection(path: str, name: str, members: list[str], odata_type: str) -> dict[str, Any]:
    return {
        "@odata.id": path,
        "@odata.type": odata_type,
        "Name": name,
        "james.b@example.com": len(members),
        "Members": [_link(item) for item in members],
    }


def build_inventory() -> dict[str, dict[str, Any]]:
    system_path = f"/redfish/v1/Systems/{SYSTEM_ID}"
    chassis_path = f"/redfish/v1/Chassis/{CHASSIS_ID}"
    manager_path = f"/redfish/v1/Managers/{MANAGER_ID}"
    storage_path = f"{system_path}/Storage/{STORAGE_ID}"
    thermal_path = f"{chassis_path}/Thermal"
    power_path = f"{chassis_path}/Power"
    sensors_path = f"{chassis_path}/Sensors"
    adapters_path = f"{chassis_path}/NetworkAdapters"
    adapter_path = f"{adapters_path}/{ADAPTER_ID}"
    ports_path = f"{adapter_path}/Ports"
    port_path = f"{ports_path}/1"
    session_service = "/redfish/v1/SessionService"
    sessions = f"{session_service}/Sessions"

    root = {
        "@odata.id": "/redfish/v1/",
        "@odata.type": "#ServiceRoot.v1_15_0.ServiceRoot",
        "Id": "RootService",
        "Name": "Root Service",
        "RedfishVersion": "1.15.1",
        "UUID": "92384634-2938-2342-8820-489239905423",
        "Systems": _link("/redfish/v1/Systems"),
        "Chassis": _link("/redfish/v1/Chassis"),
        "Managers": _link("/redfish/v1/Managers"),
        "SessionService": _link(session_service),
        "Links": {"Sessions": _link(sessions)},
    }
    systems = _collection(
        "/redfish/v1/Systems",
        "Computer System Collection",
        [system_path],
        "#ComputerSystemCollection.ComputerSystemCollection",
    )
    chassis = _collection(
        "/redfish/v1/Chassis",
        "Chassis Collection",
        [chassis_path],
        "#ChassisCollection.ChassisCollection",
    )
    managers = _collection(
        "/redfish/v1/Managers",
        "Manager Collection",
        [manager_path],
        "#ManagerCollection.ManagerCollection",
    )
    system = {
        "@odata.id": system_path,
        "@odata.type": "#ComputerSystem.v1_22_0.ComputerSystem",
        "Id": SYSTEM_ID,
        "Name": "System",
        "SystemType": "Physical",
        "BiosVersion": BIOS_VERSION,
        "PowerState": "On",
        "Status": _status("OK", "Enabled"),
        "ProcessorSummary": {"Count": 2, "Model": "Intel Xeon", "Status": _status("OK")},
        "MemorySummary": {"TotalSystemMemoryGiB": 256, "Status": _status("OK")},
        "Storage": _link(f"{system_path}/Storage"),
        "Links": {"Chassis": [_link(chassis_path)], "ManagedBy": [_link(manager_path)]},
    }
    manager = {
        "@odata.id": manager_path,
        "@odata.type": "#Manager.v1_18_0.Manager",
        "Id": MANAGER_ID,
        "Name": "Manager",
        "ManagerType": "BMC",
        "FirmwareVersion": BMC_FIRMWARE,
        "Status": _status("OK", "Enabled"),
        "Links": {"ManagerForServers": [_link(system_path)], "ManagerForChassis": [_link(chassis_path)]},
    }
    chassis_item = {
        "@odata.id": chassis_path,
        "@odata.type": "#Chassis.v1_25_0.Chassis",
        "Id": CHASSIS_ID,
        "Name": "Computer System Chassis",
        "ChassisType": "RackMount",
        "Status": _status("OK", "Enabled"),
        "Thermal": _link(thermal_path),
        "Power": _link(power_path),
        "Sensors": _link(sensors_path),
        "NetworkAdapters": _link(adapters_path),
        "Links": {"ComputerSystems": [_link(system_path)], "ManagedBy": [_link(manager_path)]},
    }
    thermal = {
        "@odata.id": thermal_path,
        "@odata.type": "#Thermal.v1_7_1.Thermal",
        "Id": "Thermal",
        "Name": "Thermal",
        "Temperatures": [
            {
                "@odata.id": f"{thermal_path}#/Temperatures/0",
                "MemberId": "0",
                "Name": "CPU1 Temp",
                "PhysicalContext": "CPU",
                "ReadingCelsius": 45,
                "UpperThresholdCritical": 98,
                "Status": _status("OK"),
            },
            {
                "@odata.id": f"{thermal_path}#/Temperatures/1",
                "MemberId": "1",
                "Name": "System Board Inlet Temp",
                "PhysicalContext": "Intake",
                "ReadingCelsius": 22,
                "UpperThresholdCritical": 47,
                "Status": _status("OK"),
            },
            {
                "@odata.id": f"{thermal_path}#/Temperatures/2",
                "MemberId": "2",
                "Name": "System Board Exhaust Temp",
                "PhysicalContext": "Exhaust",
                "ReadingCelsius": 33,
                "UpperThresholdCritical": 80,
                "Status": _status("OK"),
            },
        ],
        "Fans": [
            {
                "@odata.id": f"{thermal_path}#/Fans/0",
                "MemberId": "0",
                "Name": "Fan1",
                "Reading": 4200,
                "ReadingUnits": "RPM",
                "Status": _status("OK"),
            },
            {
                "@odata.id": f"{thermal_path}#/Fans/1",
                "MemberId": "1",
                "Name": "Fan2",
                "Reading": 3900,
                "ReadingUnits": "RPM",
                "Status": _status("OK"),
            },
        ],
    }
    power = {
        "@odata.id": power_path,
        "@odata.type": "#Power.v1_7_1.Power",
        "Id": "Power",
        "Name": "Power",
        "PowerControl": [
            {
                "@odata.id": f"{power_path}#/PowerControl/0",
                "MemberId": "0",
                "Name": "System Power Control",
                "PowerConsumedWatts": 280,
                "PowerLimit": {"LimitInWatts": 750},
            }
        ],
        "PowerSupplies": [
            {
                "@odata.id": f"{power_path}#/PowerSupplies/0",
                "MemberId": "0",
                "Name": "PS1 Status",
                "PowerCapacityWatts": 750,
                "PowerInputWatts": 160,
                "PowerOutputWatts": 148,
                "LineInputVoltage": 220,
                "Status": _status("OK"),
            },
            {
                "@odata.id": f"{power_path}#/PowerSupplies/1",
                "MemberId": "1",
                "Name": "PS2 Status",
                "PowerCapacityWatts": 750,
                "PowerInputWatts": 145,
                "PowerOutputWatts": 132,
                "LineInputVoltage": 220,
                "Status": _status("OK"),
            },
        ],
        "Voltages": [
            {
                "@odata.id": f"{power_path}#/Voltages/0",
                "MemberId": "0",
                "Name": "System Board 12V",
                "ReadingVolts": 12.1,
                "Status": _status("OK"),
            },
            {
                "@odata.id": f"{power_path}#/Voltages/1",
                "MemberId": "1",
                "Name": "System Board 3.3V",
                "ReadingVolts": 3.31,
                "Status": _status("OK"),
            },
        ],
    }
    sensors = _collection(
        sensors_path,
        "Sensors",
        [f"{sensors_path}/Inlet", f"{sensors_path}/CPU1"],
        "#SensorCollection.SensorCollection",
    )
    inlet_sensor = {
        "@odata.id": f"{sensors_path}/Inlet",
        "@odata.type": "#Sensor.v1_7_0.Sensor",
        "Id": "Inlet",
        "Name": "System Board Inlet Temp",
        "Reading": 22,
        "ReadingUnits": "Cel",
        "PhysicalContext": "Intake",
        "Thresholds": {"UpperCritical": {"Reading": 47}},
        "Status": _status("OK"),
    }
    cpu_sensor = {
        "@odata.id": f"{sensors_path}/CPU1",
        "@odata.type": "#Sensor.v1_7_0.Sensor",
        "Id": "CPU1",
        "Name": "CPU1 Temp",
        "Reading": 45,
        "ReadingUnits": "Cel",
        "PhysicalContext": "CPU",
        "Thresholds": {"UpperCritical": {"Reading": 98}},
        "Status": _status("OK"),
    }
    storage_collection = _collection(
        f"{system_path}/Storage",
        "Storage Collection",
        [storage_path],
        "#StorageCollection.StorageCollection",
    )
    drive0 = f"{storage_path}/Drives/Disk.Bay.0"
    drive1 = f"{storage_path}/Drives/Disk.Bay.1"
    drive_absent = f"{storage_path}/Drives/Disk.Bay.4"
    storage = {
        "@odata.id": storage_path,
        "@odata.type": "#Storage.v1_15_0.Storage",
        "Id": STORAGE_ID,
        "Name": "RAID Controller",
        "Status": _status("OK", "Enabled", rollup="OK"),
        "StorageControllers": [
            {
                "@odata.id": f"{storage_path}#/StorageControllers/0",
                "MemberId": "RAID.Integrated.1-1",
                "Name": "PERC H755",
                "Status": _status("OK"),
            }
        ],
        "Drives": [_link(drive0), _link(drive1), _link(drive_absent)],
    }
    drives = {
        drive0: {
            "@odata.id": drive0,
            "@odata.type": "#Drive.v1_17_0.Drive",
            "Id": "Disk.Bay.0",
            "Name": "Physical Disk 0:1:0",
            "MediaType": "HDD",
            "Protocol": "SAS",
            "Status": _status("OK", "Enabled"),
        },
        drive1: {
            "@odata.id": drive1,
            "@odata.type": "#Drive.v1_17_0.Drive",
            "Id": "Disk.Bay.1",
            "Name": "SSD 0",
            "MediaType": "SSD",
            "Protocol": "SATA",
            "PredictedMediaLifeLeftPercent": 86,
            "Status": _status("Warning", "Enabled"),
        },
        drive_absent: {
            "@odata.id": drive_absent,
            "@odata.type": "#Drive.v1_17_0.Drive",
            "Id": "Disk.Bay.4",
            "Name": "Empty Bay",
            "Status": {"State": "Absent"},
        },
    }
    adapters = _collection(
        adapters_path,
        "Network Adapter Collection",
        [adapter_path],
        "#NetworkAdapterCollection.NetworkAdapterCollection",
    )
    adapter = {
        "@odata.id": adapter_path,
        "@odata.type": "#NetworkAdapter.v1_9_0.NetworkAdapter",
        "Id": ADAPTER_ID,
        "Name": "Integrated NIC 1",
        "Status": _status("OK"),
        "Ports": _link(ports_path),
    }
    ports = _collection(
        ports_path,
        "Network Ports",
        [port_path],
        "#PortCollection.PortCollection",
    )
    port = {
        "@odata.id": port_path,
        "@odata.type": "#Port.v1_10_0.Port",
        "Id": "1",
        "Name": "NIC Port 1",
        "LinkStatus": "LinkUp",
        "CurrentLinkSpeedMbps": 25000,
        "Status": _status("OK"),
    }
    session_service_resource = {
        "@odata.id": session_service,
        "@odata.type": "#SessionService.v1_1_8.SessionService",
        "Id": "SessionService",
        "Name": "Session Service",
        "ServiceEnabled": True,
        "SessionTimeout": 30,
        "Sessions": _link(sessions),
        "Status": _status("OK"),
    }
    session_collection = _collection(
        sessions,
        "Session Collection",
        [],
        "#SessionCollection.SessionCollection",
    )

    resources = {
        "/redfish/v1": root,
        "/redfish/v1/": {**root, "@odata.id": "/redfish/v1/"},
        "/redfish/v1/Systems": systems,
        system_path: system,
        "/redfish/v1/Chassis": chassis,
        chassis_path: chassis_item,
        "/redfish/v1/Managers": managers,
        manager_path: manager,
        thermal_path: thermal,
        power_path: power,
        sensors_path: sensors,
        f"{sensors_path}/Inlet": inlet_sensor,
        f"{sensors_path}/CPU1": cpu_sensor,
        f"{system_path}/Storage": storage_collection,
        storage_path: storage,
        adapters_path: adapters,
        adapter_path: adapter,
        ports_path: ports,
        port_path: port,
        session_service: session_service_resource,
        sessions: session_collection,
    }
    resources.update(drives)
    return resources


def expected_metric_checklist() -> list[dict[str, Any]]:
    return [
        {"name": "redfish_system_health", "value": 1, "labels": {}, "group": "Health"},
        {"name": "redfish_system_power_state", "value": 1, "labels": {}, "group": "Health"},
        {"name": "redfish_manager_health", "value": 1, "labels": {}, "group": "Health"},
        {"name": "redfish_processor_health_rollup", "value": 1, "labels": {}, "group": "Health"},
        {"name": "redfish_memory_health_rollup", "value": 1, "labels": {}, "group": "Health"},
        {"name": "redfish_firmware_info", "value": 1, "labels": {"bios_version": BIOS_VERSION, "bmc_firmware": BMC_FIRMWARE}, "group": "Inventory"},
        {"name": "redfish_temperature_celsius", "value": 45, "labels": {"name": "CPU1 Temp"}, "group": "Environment"},
        {"name": "redfish_temperature_celsius", "value": 22, "labels": {"name": "System Board Inlet Temp"}, "group": "Environment"},
        {"name": "redfish_temperature_celsius", "value": 33, "labels": {"name": "System Board Exhaust Temp"}, "group": "Environment"},
        {"name": "redfish_temperature_upper_critical_celsius", "value": 98, "labels": {"name": "CPU1 Temp"}, "group": "Environment"},
        {"name": "redfish_temperature_upper_critical_celsius", "value": 47, "labels": {"name": "System Board Inlet Temp"}, "group": "Environment"},
        {"name": "redfish_temperature_upper_critical_celsius", "value": 80, "labels": {"name": "System Board Exhaust Temp"}, "group": "Environment"},
        {"name": "redfish_inlet_temperature_celsius", "value": 22, "labels": {}, "group": "Environment"},
        {"name": "redfish_inlet_temperature_upper_critical_celsius", "value": 47, "labels": {}, "group": "Environment"},
        {"name": "redfish_fan_speed", "value": 4200, "labels": {"name": "Fan1", "unit": "RPM"}, "group": "Environment"},
        {"name": "redfish_fan_speed", "value": 3900, "labels": {"name": "Fan2", "unit": "RPM"}, "group": "Environment"},
        {"name": "redfish_fan_health", "value": 1, "labels": {"name": "Fan1"}, "group": "Environment"},
        {"name": "redfish_fan_health", "value": 1, "labels": {"name": "Fan2"}, "group": "Environment"},
        {"name": "redfish_power_consumed_watts", "value": 280, "labels": {"name": "System Power Control"}, "group": "Power"},
        {"name": "redfish_power_limit_watts", "value": 750, "labels": {"name": "System Power Control"}, "group": "Power"},
        {"name": "redfish_power_over_limit", "value": 0, "labels": {}, "group": "Power"},
        {"name": "redfish_psu_health", "value": 1, "labels": {"name": "PS1 Status"}, "group": "Power"},
        {"name": "redfish_psu_health", "value": 1, "labels": {"name": "PS2 Status"}, "group": "Power"},
        {"name": "redfish_psu_input_watts", "value": 160, "labels": {"name": "PS1 Status"}, "group": "Power"},
        {"name": "redfish_psu_input_watts", "value": 145, "labels": {"name": "PS2 Status"}, "group": "Power"},
        {"name": "redfish_psu_output_watts", "value": 148, "labels": {"name": "PS1 Status"}, "group": "Power"},
        {"name": "redfish_psu_output_watts", "value": 132, "labels": {"name": "PS2 Status"}, "group": "Power"},
        {"name": "redfish_psu_capacity_watts", "value": 750, "labels": {"name": "PS1 Status"}, "group": "Power"},
        {"name": "redfish_psu_capacity_watts", "value": 750, "labels": {"name": "PS2 Status"}, "group": "Power"},
        {"name": "redfish_psu_input_voltage", "value": 220, "labels": {"name": "PS1 Status"}, "group": "Power"},
        {"name": "redfish_psu_input_voltage", "value": 220, "labels": {"name": "PS2 Status"}, "group": "Power"},
        {"name": "redfish_psu_delivering", "value": 1, "labels": {"name": "PS1 Status"}, "group": "Power"},
        {"name": "redfish_psu_delivering", "value": 1, "labels": {"name": "PS2 Status"}, "group": "Power"},
        {"name": "redfish_psu_redundant", "value": 1, "labels": {}, "group": "Power"},
        {"name": "redfish_voltage_volts", "value": 12.1, "labels": {"name": "System Board 12V"}, "group": "Power"},
        {"name": "redfish_voltage_volts", "value": 3.31, "labels": {"name": "System Board 3.3V"}, "group": "Power"},
        {"name": "redfish_storage_health", "value": 1, "labels": {"id": STORAGE_ID}, "group": "Storage"},
        {"name": "redfish_storage_controller_health", "value": 1, "labels": {"id": "RAID.Integrated.1-1", "storage_id": STORAGE_ID}, "group": "Storage"},
        {"name": "redfish_drive_health", "value": 1, "labels": {"name": "Physical Disk 0:1:0", "media_type": "HDD", "protocol": "SAS"}, "group": "Storage"},
        {"name": "redfish_drive_health", "value": 2, "labels": {"name": "SSD 0", "media_type": "SSD", "protocol": "SATA"}, "group": "Storage"},
        {"name": "redfish_drive_present_count", "value": 2, "labels": {}, "group": "Storage"},
        {"name": "redfish_drive_life_percent", "value": 86, "labels": {"name": "SSD 0", "media_type": "SSD", "protocol": "SATA"}, "group": "Storage"},
        {"name": "redfish_nic_health", "value": 1, "labels": {"id": ADAPTER_ID}, "group": "Network"},
        {"name": "redfish_nic_port_health", "value": 1, "labels": {"adapter_id": ADAPTER_ID, "id": "1"}, "group": "Network"},
        {"name": "redfish_nic_port_link_up", "value": 1, "labels": {"adapter_id": ADAPTER_ID, "id": "1"}, "group": "Network"},
        {"name": "redfish_nic_port_speed_mbps", "value": 25000, "labels": {"adapter_id": ADAPTER_ID, "id": "1"}, "group": "Network"},
    ]
