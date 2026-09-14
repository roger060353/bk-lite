"""华为 VRP Telnet 最小 mock。

TEST-ONLY / 日本节点与本地联调，不进默认生产采集路径，不改任务树默认值。
语义对齐 `network_config_file_info` + Scrapli `huawei_vrp` / `asynctelnet`：
Username/Password 登录、用户视图 `<hostname>`、回显命令、应答
`screen-length 0 temporary` / `screen-width` / display|show 只读命令。
"""
from __future__ import annotations

import argparse
import os
import socket
import threading
import time

IAC = 255
DONT, DO, WONT, WILL = 254, 253, 252, 251

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 2323
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin@network"
DEFAULT_HOSTNAME = "mock-vrp"

DISPLAY_VERSION = """Huawei Versatile Routing Platform Software
VRP (R) software, Version 8.180 (Mock VRP)
Copyright (C) 2012-2026 MOCK
HUAWEI MOCK-S5700 Routing Switch uptime is 0 day, 0 hour, 8 minutes
"""

DISPLAY_CURRENT = """#
sysname mock-vrp
#
vlan batch 1
#
interface GigabitEthernet0/0/1
 description MOCK-UPLINK
 ip address 10.0.16.2 255.255.255.0
#
return
"""

KNOWN_COMMANDS = {
    "screen-length 0 temporary": "",
    "screen-width 256": "Info: The current screen width is 256.",
    "display version": DISPLAY_VERSION,
    "show version": DISPLAY_VERSION,
    "display current-configuration": DISPLAY_CURRENT,
    "display saved-configuration": DISPLAY_CURRENT,
    "show running-config": DISPLAY_CURRENT,
}


def connect_host_for(bind_host: str) -> str:
    return "127.0.0.1" if bind_host in {"0.0.0.0", "::", ""} else bind_host


def command_output(command: str) -> tuple[str, bool]:
    """返回 (输出正文, 是否应关闭会话)。"""
    normalized = " ".join(command.strip().split())
    lowered = normalized.lower()
    if not lowered or lowered in {"y", "n", "yes", "no"}:
        return "", False
    if lowered in {"exit", "quit", "logout"}:
        return "", True
    if lowered in KNOWN_COMMANDS:
        return KNOWN_COMMANDS[lowered], False
    if lowered.startswith("display ") or lowered.startswith("show "):
        return f"# mock output for {normalized}\n", False
    return "Error: Unrecognized command found at '^' position.", False


class _Session:
    USER = "user"
    PASS = "pass"
    EXEC = "exec"

    def __init__(self, conn: socket.socket, username: str, password: str, hostname: str):
        self.conn = conn
        self.username = username
        self.password = password
        self.hostname = hostname
        self.state = self.USER
        self.line = bytearray()
        self.iac = bytearray()
        self.seen_username = ""

    @property
    def prompt(self) -> str:
        return f"<{self.hostname}>"

    def write(self, data: str | bytes) -> None:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        self.conn.sendall(payload)

    def start(self) -> None:
        self.write("Login authentication\r\n\r\nUsername:")

    def feed(self, chunk: bytes) -> bool:
        """处理入站字节。返回 False 表示应关闭连接。"""
        for byte in chunk:
            if self.iac or byte == IAC:
                if not self._feed_iac(byte):
                    continue
                continue
            if self.state == self.PASS:
                if byte in (10, 13):
                    if byte == 13 and not self.line:
                        continue
                    if not self._finish_password():
                        return True
                    self.line.clear()
                    if byte == 13:
                        continue
                else:
                    self.line.append(byte)
                continue
            if byte == 13:
                continue
            if byte == 10:
                if self.state != self.PASS:
                    self.write(b"\r\n")
                if not self._finish_line():
                    return False
                self.line.clear()
                continue
            self.line.append(byte)
            if self.state != self.PASS:
                self.write(bytes([byte]))
        return True

    def _feed_iac(self, byte: int) -> bool:
        self.iac.append(byte)
        if len(self.iac) < 3:
            return False
        cmd = self.iac[1]
        option = bytes([self.iac[2]])
        self.iac.clear()
        if cmd == DO:
            self.write(bytes([IAC, WONT]) + option)
        elif cmd == WILL:
            self.write(bytes([IAC, DONT]) + option)
        return True

    def _finish_line(self) -> bool:
        text = self.line.decode("utf-8", errors="replace")
        if self.state == self.USER:
            self.seen_username = text
            self.state = self.PASS
            self.write("Password:")
            return True
        output, should_close = command_output(text)
        if should_close:
            return False
        if output:
            body = output.replace("\n", "\r\n")
            if not body.endswith("\r\n"):
                body += "\r\n"
            self.write(body)
        self.write(self.prompt)
        return True

    def _finish_password(self) -> bool:
        offered = self.line.decode("utf-8", errors="replace")
        if self.seen_username == self.username and offered == self.password:
            self.state = self.EXEC
            self.write("\r\n" + self.prompt)
            return True
        self.state = self.USER
        self.seen_username = ""
        self.write("\r\nAuthentication failed\r\n\r\nUsername:")
        return True


def _handle_connection(conn: socket.socket, username: str, password: str, hostname: str) -> None:
    conn.settimeout(120)
    session = _Session(conn, username, password, hostname)
    try:
        session.start()
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            if not session.feed(chunk):
                break
    except (TimeoutError, ConnectionError, OSError):
        pass
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()


class HuaweiVRPTelnetMockServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        hostname: str = DEFAULT_HOSTNAME,
    ):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.hostname = hostname
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def connect_host(self) -> str:
        return connect_host_for(self.host)

    def start(self) -> HuaweiVRPTelnetMockServer:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(16)
        sock.settimeout(0.5)
        self._sock = sock
        self.port = int(sock.getsockname()[1])
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="huawei-vrp-telnet-mock", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> HuaweiVRPTelnetMockServer:
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    return
                continue
            worker = threading.Thread(
                target=_handle_connection,
                args=(conn, self.username, self.password, self.hostname),
                daemon=True,
            )
            worker.start()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Huawei VRP Telnet mock（仅测试）")
    parser.add_argument("--host", default=os.environ.get("HUAWEI_VRP_TELNET_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HUAWEI_VRP_TELNET_PORT", DEFAULT_PORT)))
    parser.add_argument("--username", default=os.environ.get("HUAWEI_VRP_TELNET_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password", default=os.environ.get("HUAWEI_VRP_TELNET_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--hostname", default=os.environ.get("HUAWEI_VRP_TELNET_HOSTNAME", DEFAULT_HOSTNAME))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    server = HuaweiVRPTelnetMockServer(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        hostname=args.hostname,
    )
    server.start()
    print(f"Huawei VRP Telnet mock listening on {server.host}:{server.port}")
    print(f"connect_host={server.connect_host} username={server.username} password={server.password}")
    print(f"prompt=<{server.hostname}> platform=huawei_vrp")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
