# -*- coding: utf-8 -*-
"""Stdio smoke for the Comware CLI mock. No SSH / Docker required."""
from __future__ import annotations

from pathlib import Path

from comware_cli import FIXTURE_DIR, INCOMPLETE, UNRECOGNIZED, USER_PROMPT, dispatch, normalize_command

HERE = Path(__file__).resolve().parent


def _assert_contains(output: str, needle: str, command: str) -> None:
    if needle not in output:
        raise AssertionError(f"{command!r} output missing {needle!r}: {output[:200]!r}")


def main() -> int:
    assert normalize_command("  Display   VERSION \t") == "display version"

    empty = dispatch("", "user")
    assert empty.output == "" and empty.exit_cli is False

    paging = dispatch("screen-length disable", "user")
    assert paging.output == ""

    version = dispatch("display version", "user")
    _assert_contains(version.output, "H3C Comware", "display version")
    _assert_contains(version.output, "Version 7.1.070", "display version")

    show_ver = dispatch("show version", "user")
    _assert_contains(show_ver.output, "H3C Comware", "show version")

    config = dispatch("display current-configuration", "user")
    _assert_contains(config.output, "sysname MOCK-H3C", "display current-configuration")
    _assert_contains(config.output, "ssh server enable", "display current-configuration")

    show_run = dispatch("show running-config", "user")
    _assert_contains(show_run.output, "sysname MOCK-H3C", "show running-config")

    incomplete = dispatch("display", "user")
    assert incomplete.output == INCOMPLETE

    unknown = dispatch("reboot", "user")
    assert unknown.output == UNRECOGNIZED

    to_sys = dispatch("system-view", "user")
    assert to_sys.change_view == "system"
    back = dispatch("quit", "system")
    assert back.change_view == "user"
    logout = dispatch("quit", "user")
    assert logout.exit_cli is True

    assert USER_PROMPT == "<MOCK-H3C>"
    assert FIXTURE_DIR == HERE / "fixtures"
    print("h3c_comware_mock smoke: OK")
    print(f"fixtures={FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
