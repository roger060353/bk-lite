# -*- coding: utf-8 -*-
"""SSH / Scrapli probe for the H3C Comware mock.

Matches ``network_config_file``: platform ``hp_comware``, transport ``asyncssh``.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import sys
import uuid
from pathlib import Path

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin@h3c"
INSTANCE_UUID = "123e4567-e89b-42d3-a456-426614174000"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe H3C Comware mock via Scrapli hp_comware")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2223)
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--via",
        choices=("scrapli", "plugin"),
        default="scrapli",
        help="scrapli=AsyncScrapli directly; plugin=NetworkConfigFileInfo",
    )
    return parser


def _assert_identifiable(text: str) -> None:
    for needle in ("H3C Comware", "sysname MOCK-H3C", "MOCK-H3C"):
        if needle not in text:
            raise SystemExit(f"probe failed: missing {needle!r} in output")


async def _probe_scrapli(host: str, port: int, username: str, password: str) -> str:
    from scrapli import AsyncScrapli

    conn = AsyncScrapli(
        platform="hp_comware",
        host=host,
        port=port,
        auth_username=username,
        auth_password=password,
        auth_strict_key=False,
        transport="asyncssh",
        timeout_socket=30.0,
        timeout_transport=30.0,
        timeout_ops=60.0,
    )
    await conn.open()
    try:
        current = await conn.send_command("display current-configuration")
        version = await conn.send_command("display version")
        show_run = await conn.send_command("show running-config")
        show_ver = await conn.send_command("show version")
    finally:
        try:
            await conn.close()
        except Exception:
            pass

    chunks = []
    for name, response in (
        ("display current-configuration", current),
        ("display version", version),
        ("show running-config", show_run),
        ("show version", show_ver),
    ):
        if getattr(response, "failed", False):
            raise SystemExit(f"probe failed: {name} marked failed: {response.result!r}")
        chunks.append(f"===== command: {name} =====\n{response.result}")
    return "\n\n".join(chunks)


async def _probe_plugin(host: str, port: int, username: str, password: str) -> str:
    stargazer_root = Path(__file__).resolve().parents[2]
    if str(stargazer_root) not in sys.path:
        sys.path.insert(0, str(stargazer_root))
    from plugins.inputs.network_config_file.network_config_file_info import NetworkConfigFileInfo

    collector = NetworkConfigFileInfo(
        {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "device_type": "hp_comware",
            "commands": "display current-configuration\ndisplay version",
            "config_name": "running-config",
            "collect_task_id": "h3c-mock-probe",
            "target_model_id": "switch",
            "protocol_version": "2",
            "target_instance_uuid": str(uuid.UUID(INSTANCE_UUID)),
        }
    )
    result = await collector.list_all_resources()
    if not result.get("success"):
        raise SystemExit(f"plugin probe failed: {result}")
    payload = result["result"]
    return base64.b64decode(payload["content_base64"]).decode("utf-8")


async def _run(args: argparse.Namespace) -> int:
    if args.via == "plugin":
        text = await _probe_plugin(args.host, args.port, args.username, args.password)
    else:
        text = await _probe_scrapli(args.host, args.port, args.username, args.password)
    _assert_identifiable(text)
    print(text)
    print("h3c_comware_mock scrapli probe: OK")
    return 0


def main() -> int:
    args = _build_parser().parse_args()
    try:
        return asyncio.run(_run(args))
    except ModuleNotFoundError as err:
        print(
            "missing dependency: install scrapli[asyncssh] scrapli-community " f"(or run from agents/stargazer venv). {err}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
