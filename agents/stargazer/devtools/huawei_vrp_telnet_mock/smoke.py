"""对 mock 跑一遍 NetworkConfigFileInfo（Scrapli asynctelnet + huawei_vrp）。"""
from __future__ import annotations

import argparse
import asyncio
import base64
import sys
from pathlib import Path

STARGAZER_ROOT = Path(__file__).resolve().parents[2]
if str(STARGAZER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARGAZER_ROOT))

from devtools.huawei_vrp_telnet_mock.server import DEFAULT_PASSWORD, DEFAULT_USERNAME, HuaweiVRPTelnetMockServer  # noqa: E402

INSTANCE_UUID = "123e4567-e89b-42d3-a456-426614174000"
DEFAULT_COMMANDS = "display current-configuration\ndisplay version"


def plugin_params(server: HuaweiVRPTelnetMockServer, commands: str = DEFAULT_COMMANDS) -> dict:
    return {
        "host": server.connect_host,
        "port": server.port,
        "username": server.username,
        "password": server.password,
        "transport_protocol": "telnet",
        "device_type": "huawei",
        "commands": commands,
        "config_name": "running-config",
        "collect_task_id": "42",
        "target_model_id": "switch",
        "protocol_version": "2",
        "target_instance_uuid": INSTANCE_UUID,
        "instance_name": "mock-vrp",
    }


async def collect_against(server: HuaweiVRPTelnetMockServer, commands: str = DEFAULT_COMMANDS) -> dict:
    from plugins.inputs.network_config_file.network_config_file_info import NetworkConfigFileInfo

    return await NetworkConfigFileInfo(plugin_params(server, commands)).list_all_resources()


def assert_collect_payload(result: dict) -> None:
    assert result["success"] is True, result
    payload = result["result"]
    assert payload["status"] == "success"
    assert payload["protocol_version"] == "2"
    assert payload["instance_uuid"] == INSTANCE_UUID
    assert payload["file_name"] == "running-config"
    decoded = base64.b64decode(payload["content_base64"]).decode()
    assert "===== command: display current-configuration =====" in decoded
    assert "sysname mock-vrp" in decoded
    assert "===== command: display version =====" in decoded
    assert "Mock VRP" in decoded
    assert "Error:" not in decoded
    assert "credentials_exhausted" not in decoded


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="对 Huawei VRP Telnet mock 跑采集冒烟")
    parser.parse_args(argv)
    with HuaweiVRPTelnetMockServer(host="127.0.0.1", port=0, username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD) as server:
        result = asyncio.run(collect_against(server))
        assert_collect_payload(result)
    print("huawei vrp telnet mock smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
