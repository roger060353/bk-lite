"""对真实 Telnet mock 跑 NetworkConfigFileInfo，校验 Scrapli asynctelnet + huawei_vrp。"""
import socket
import sys
from pathlib import Path

import pytest

STARGAZER_ROOT = Path(__file__).resolve().parents[1]
if str(STARGAZER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARGAZER_ROOT))

from devtools.huawei_vrp_telnet_mock.server import DEFAULT_PASSWORD, DEFAULT_USERNAME, HuaweiVRPTelnetMockServer  # noqa: E402
from devtools.huawei_vrp_telnet_mock.smoke import assert_collect_payload, collect_against  # noqa: E402


def _read_until(conn: socket.socket, needle: bytes, timeout: float = 3.0) -> bytes:
    conn.settimeout(timeout)
    buf = b""
    while needle not in buf:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf


def test_mock_login_and_display_over_raw_socket():
    with HuaweiVRPTelnetMockServer(host="127.0.0.1", port=0) as server:
        conn = socket.create_connection((server.connect_host, server.port), timeout=3)
        try:
            banner = _read_until(conn, b"Username:")
            assert b"Login authentication" in banner
            conn.sendall(b"admin\n")
            assert b"Password:" in _read_until(conn, b"Password:")
            conn.sendall(b"Admin@network\n")
            prompt = _read_until(conn, b"<mock-vrp>")
            assert b"<mock-vrp>" in prompt
            conn.sendall(b"display version\n")
            output = _read_until(conn, b"<mock-vrp>")
            assert b"Mock VRP" in output
            assert b"Error:" not in output
        finally:
            conn.close()


@pytest.mark.asyncio
async def test_network_config_file_collects_from_telnet_mock():
    with HuaweiVRPTelnetMockServer(host="127.0.0.1", port=0, username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD) as server:
        result = await collect_against(server)
        assert_collect_payload(result)
        assert result["result"]["model_id"] == "switch"


@pytest.mark.asyncio
async def test_network_config_file_accepts_show_aliases_on_telnet_mock():
    with HuaweiVRPTelnetMockServer(host="127.0.0.1", port=0) as server:
        result = await collect_against(server, commands="show running-config\nshow version")
        assert result["success"] is True, result
        from base64 import b64decode

        decoded = b64decode(result["result"]["content_base64"]).decode()
        assert "sysname mock-vrp" in decoded
        assert "Mock VRP" in decoded


def test_telnet_mock_rejects_bad_password_over_raw_socket():
    with HuaweiVRPTelnetMockServer(host="127.0.0.1", port=0) as server:
        conn = socket.create_connection((server.connect_host, server.port), timeout=3)
        try:
            assert b"Username:" in _read_until(conn, b"Username:")
            conn.sendall(b"admin\n")
            assert b"Password:" in _read_until(conn, b"Password:")
            conn.sendall(b"wrong-password\n")
            reply = _read_until(conn, b"Username:")
            assert b"Authentication failed" in reply
            assert b"<mock-vrp>" not in reply
        finally:
            conn.close()
