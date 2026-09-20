# -*- coding: utf-8 -*-
"""对 mock 跑 RedfishCollector，断言监控插件全量指标都能刮到。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

STARGAZER_ROOT = Path(__file__).resolve().parents[2]
if str(STARGAZER_ROOT) not in sys.path:
    sys.path.insert(0, str(STARGAZER_ROOT))

from devtools.redfish_monitor_mock.inventory import (  # noqa: E402
    EXPECTED_METRICS,
    EXPECTED_VALUES,
    expected_metric_checklist,
)
from devtools.redfish_monitor_mock.server import DEFAULT_PASSWORD, DEFAULT_USERNAME, RedfishMonitorMockServer  # noqa: E402

PLUGIN_METRICS = (
    STARGAZER_ROOT.parents[1]
    / "server"
    / "apps"
    / "monitor"
    / "support-files"
    / "plugins"
    / "Telegraf"
    / "redfish"
    / "hardware_server"
    / "metrics.json"
)


def assert_plugin_metric_set(metrics: dict | None = None) -> list[str]:
    payload = metrics or json.loads(PLUGIN_METRICS.read_text(encoding="utf-8"))
    names = [item["name"] for item in payload["metrics"]]
    assert names == list(EXPECTED_METRICS)
    return names


def _named(text: str, metric: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(f"{metric}{{")]


async def collect_against(server: RedfishMonitorMockServer) -> str:
    from tasks.collectors.redfish_collector import RedfishCollector

    collector = RedfishCollector(
        {
            "host": "127.0.0.1" if server.host in {"0.0.0.0", "::"} else server.host,
            "port": server.port,
            "username": server.username,
            "password": server.password,
            "verify_tls": False,
        }
    )
    return await collector.collect()


def assert_collect_text(text: str) -> None:
    assert text.endswith("\n")
    for name in EXPECTED_METRICS:
        assert f"{name}{{" in text, name
    for name, value in EXPECTED_VALUES.items():
        lines = _named(text, name)
        assert lines, name
        assert any(f" {value} " in line or line.endswith(f" {value}") for line in lines), (name, value, lines)
    assert 'name="System Board Inlet Temp"' in text
    assert 'name="PS1 Status"' in text
    assert 'name="SSD 0"' in text
    assert "Empty Bay" not in text
    assert "/sensors" not in text.lower()
    checklist = expected_metric_checklist()
    assert {item["name"] for item in checklist} == set(EXPECTED_METRICS)


def main() -> int:
    assert_plugin_metric_set()
    with RedfishMonitorMockServer(host="127.0.0.1", port=0, username=DEFAULT_USERNAME, password=DEFAULT_PASSWORD, tls=True) as server:
        text = asyncio.run(collect_against(server))
        assert_collect_text(text)
    print("redfish monitor mock smoke: ok")
    print(f"metrics={len(EXPECTED_METRICS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
