# -*- coding: utf-8 -*-
"""Hardware Server Redfish 监控 mock（TEST-ONLY）。

HTTPS + Basic / Session。路径对齐 stargazer `RedfishCollector`，
不是 CMDB `physcial_server` 资产采集。
"""
from __future__ import annotations

import argparse
import base64
import hmac
import json
import os
import secrets
import ssl
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .inventory import build_inventory

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8443
DEFAULT_USERNAME = "redfish"
DEFAULT_PASSWORD = "RedfishMon1"
SESSIONS = "/redfish/v1/SessionService/Sessions"
MAX_BODY = 4096


def normalize_path(path: str) -> str:
    if path in {"/redfish/v1", "/redfish/v1/"}:
        return path
    return path.rstrip("/") or "/"


class RedfishMonitorMockServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        tls: bool = True,
        certfile: str | None = None,
        keyfile: str | None = None,
    ):
        if not username or not password:
            raise ValueError("mock credentials must be provided")
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.tls = tls
        self.certfile = certfile
        self.keyfile = keyfile
        self.resources = build_inventory()
        self.sessions: dict[str, tuple[str, float]] = {}
        self.session_lock = threading.Lock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._tls_tmpdir = None

    @property
    def scheme(self) -> str:
        return "https" if self.tls else "http"

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def valid_credentials(self, username, password) -> bool:
        if not isinstance(username, str) or not isinstance(password, str):
            return False
        return hmac.compare_digest(username.encode(), self.username.encode()) and hmac.compare_digest(
            password.encode(), self.password.encode()
        )

    def expire_sessions(self) -> None:
        now = time.monotonic()
        self.sessions = {token: value for token, value in self.sessions.items() if value[1] > now}

    def start(self) -> RedfishMonitorMockServer:
        handler = make_handler(self)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self._httpd.timeout = 1
        if self.tls:
            certfile, keyfile = self._tls_files()
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(certfile=certfile, keyfile=keyfile)
            self._httpd.socket = context.wrap_socket(self._httpd.socket, server_side=True)
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="redfish-monitor-mock", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._tls_tmpdir is not None:
            self._tls_tmpdir.cleanup()
            self._tls_tmpdir = None

    def __enter__(self) -> RedfishMonitorMockServer:
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    def _tls_files(self) -> tuple[str, str]:
        if self.certfile and self.keyfile:
            return self.certfile, self.keyfile
        self._tls_tmpdir = tempfile.TemporaryDirectory(prefix="redfish-monitor-mock-")
        certfile = os.path.join(self._tls_tmpdir.name, "cert.pem")
        keyfile = os.path.join(self._tls_tmpdir.name, "key.pem")
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                keyfile,
                "-out",
                certfile,
                "-days",
                "1",
                "-nodes",
                "-subj",
                "/CN=redfish-monitor-mock",
            ],
            check=True,
            capture_output=True,
        )
        return certfile, keyfile


def make_handler(state: RedfishMonitorMockServer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "BKLiteRedfishMonitorMock/1.0"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):
            return

        def reply(self, status, payload=None, headers=None):
            body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b""
            self.send_response(status)
            if payload is not None:
                self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("OData-Version", "4.0")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def error(self, status, code):
            self.reply(status, {"error": {"code": f"Base.1.0.{code}", "message": "Redfish monitor mock"}})

        def authenticated(self) -> bool:
            with state.session_lock:
                state.expire_sessions()
                if self.headers.get("X-Auth-Token", "") in state.sessions:
                    return True
            authorization = self.headers.get("Authorization", "")
            if not authorization.startswith("Basic "):
                return False
            try:
                user, password = base64.b64decode(authorization[6:], validate=True).decode().split(":", 1)
            except (ValueError, UnicodeError):
                return False
            return state.valid_credentials(user, password)

        def do_GET(self):
            url = urlsplit(self.path)
            path = normalize_path(url.path)
            if path not in {"/redfish/v1", "/redfish/v1/"} and not self.authenticated():
                self.error(401, "NoValidSession")
                return
            payload = state.resources.get(path)
            if payload is None:
                self.error(404, "ResourceMissingAtURI")
                return
            self.reply(200, payload)

        def do_POST(self):
            path = normalize_path(urlsplit(self.path).path)
            if path != SESSIONS:
                self.error(405, "ActionNotSupported")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    self.error(413, "RequestEntityTooLarge")
                    return
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("object required")
            except (ValueError, UnicodeError):
                self.error(400, "MalformedJSON")
                return
            if not state.valid_credentials(payload.get("UserName"), payload.get("Password")):
                self.error(401, "NoValidSession")
                return
            with state.session_lock:
                state.expire_sessions()
                token, session_id = secrets.token_urlsafe(24), secrets.token_hex(8)
                state.sessions[token] = (session_id, time.monotonic() + 300)
            location = f"{SESSIONS}/{session_id}"
            self.reply(
                201,
                {
                    "@odata.id": location,
                    "@odata.type": "#Session.v1_7_1.Session",
                    "Id": session_id,
                    "Name": "User Session",
                    "UserName": state.username,
                },
                {"X-Auth-Token": token, "Location": location},
            )

        def do_DELETE(self):
            path = normalize_path(urlsplit(self.path).path)
            if not path.startswith(SESSIONS + "/"):
                self.error(405, "ActionNotSupported")
                return
            if not self.authenticated():
                self.error(401, "NoValidSession")
                return
            token = self.headers.get("X-Auth-Token", "")
            with state.session_lock:
                session = state.sessions.get(token)
                if not session or path != f"{SESSIONS}/{session[0]}":
                    self.error(403, "InsufficientPrivilege")
                    return
                del state.sessions[token]
            self.reply(204)

        def do_PATCH(self):
            self.error(405, "ActionNotSupported")

        do_PUT = do_PATCH

    return Handler


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Hardware Server Redfish 监控 mock（仅测试）")
    parser.add_argument("--host", default=os.getenv("REDFISH_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("REDFISH_PORT", DEFAULT_PORT)))
    parser.add_argument("--username", default=os.getenv("REDFISH_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password", default=os.getenv("REDFISH_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--http", action="store_true", help="仅本机冒烟；采集器固定走 HTTPS")
    parser.add_argument("--certfile")
    parser.add_argument("--keyfile")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    tls = not args.http
    server = RedfishMonitorMockServer(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password,
        tls=tls,
        certfile=args.certfile,
        keyfile=args.keyfile,
    )
    server.start()
    print(f"Redfish monitor mock listening on {server.base_url}/redfish/v1/", flush=True)
    print(f"username={server.username} verify_tls=false", flush=True)
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
