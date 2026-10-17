#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal H3C Comware CLI for Scrapli platform ``hp_comware``.

Used as the SSH login shell. Prompt matches scrapli-community privilege_exec
``<hostname>`` / configuration ``[hostname]``. Hostname stays ``MOCK-H3C``.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

HOSTNAME = os.environ.get("H3C_MOCK_HOSTNAME", "MOCK-H3C")
USER_PROMPT = f"<{HOSTNAME}>"
SYS_PROMPT = f"[{HOSTNAME}]"
UNRECOGNIZED = "% Unrecognized command found at '^' position."
INCOMPLETE = "% Incomplete command found at '^' position."
BANNER = (
    "******************************************************************************\n"
    "* Copyright (c) 2004-2024 New H3C Technologies Co., Ltd. All rights reserved.*\n"
    "* Without the owner's prior written consent,                                 *\n"
    "* no decompiling or reverse-engineering shall be allowed.                    *\n"
    "******************************************************************************\n"
    "\n"
)


def resolve_fixture_dir() -> Path:
    env = os.environ.get("H3C_MOCK_FIXTURE_DIR")
    if env:
        return Path(env)
    sibling = Path(__file__).resolve().parent / "fixtures"
    if sibling.is_dir():
        return sibling
    packaged = Path("/opt/h3c_comware_mock/fixtures")
    if packaged.is_dir():
        return packaged
    return sibling


FIXTURE_DIR = resolve_fixture_dir()

PAGING_COMMANDS = {
    "screen-length disable",
    "screen-length 0",
    "screen-length 0 temporary",
}
VERSION_PREFIXES = (
    "display version",
    "display ver",
    "dis version",
    "dis ver",
    "show version",
    "show ver",
)
CONFIG_PREFIXES = (
    "display current-configuration",
    "display current-config",
    "display current",
    "dis current-configuration",
    "dis current-config",
    "dis current",
    "dis cu",
    "show running-config",
    "show running",
    "show run",
    "show current-configuration",
    "show current-config",
)
SYSTEM_VIEW_COMMANDS = {"system-view", "sys"}
QUIT_COMMANDS = {"quit", "exit", "logout", "return"}


@dataclass
class CommandResult:
    output: str = ""
    exit_cli: bool = False
    change_view: str | None = None


def normalize_command(raw: str) -> str:
    return " ".join(str(raw or "").strip().split()).lower()


def load_fixture(name: str) -> str:
    path = FIXTURE_DIR / name
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")


def _starts_with_any(command: str, prefixes: tuple[str, ...]) -> bool:
    return any(command == prefix or command.startswith(prefix + " ") for prefix in prefixes)


def dispatch(raw_command: str, view: str) -> CommandResult:
    command = normalize_command(raw_command)
    if not command:
        return CommandResult()
    if command in PAGING_COMMANDS:
        return CommandResult()
    if command in {"display", "dis", "show"}:
        return CommandResult(output=INCOMPLETE)
    if _starts_with_any(command, VERSION_PREFIXES):
        return CommandResult(output=load_fixture("version.txt"))
    if _starts_with_any(command, CONFIG_PREFIXES):
        return CommandResult(output=load_fixture("current-configuration.txt"))
    if command in SYSTEM_VIEW_COMMANDS:
        if view == "system":
            return CommandResult()
        return CommandResult(change_view="system")
    if command in QUIT_COMMANDS:
        if view == "system":
            return CommandResult(change_view="user")
        return CommandResult(exit_cli=True)
    return CommandResult(output=UNRECOGNIZED)


def prompt_for(view: str) -> str:
    return SYS_PROMPT if view == "system" else USER_PROMPT


def emit(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def emit_block(text: str) -> None:
    if not text:
        return
    emit(text.replace("\r\n", "\n") + "\n")


def read_line() -> str | None:
    line = sys.stdin.readline()
    if line == "":
        return None
    return line.rstrip("\r\n")


def session_loop(view: str = "user") -> int:
    emit(BANNER)
    emit(prompt_for(view))
    while True:
        raw = read_line()
        if raw is None:
            emit("\n")
            return 0
        result = dispatch(raw, view)
        emit("\n")
        emit_block(result.output)
        if result.exit_cli:
            return 0
        if result.change_view:
            view = result.change_view
        emit(prompt_for(view))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["-c"] and len(args) >= 2:
        result = dispatch(args[1], "user")
        emit_block(result.output)
        return 0 if result.output != UNRECOGNIZED else 1
    try:
        return session_loop()
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
