# -*- coding: utf-8 -*-
"""TEST-ONLY H3C / HP Comware SSH mock. Not a production collection path."""

from .comware_cli import HOSTNAME, SYS_PROMPT, USER_PROMPT, dispatch, normalize_command

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "Admin@h3c"
DEFAULT_SSH_PORT = 22
DEFAULT_HOST_PORT = 2223
CMDB_BRAND = "H3C"
SCRAPLI_PLATFORM = "hp_comware"
DEVICE_TYPE = "hp_comware"

__all__ = [
    "CMDB_BRAND",
    "DEFAULT_HOST_PORT",
    "DEFAULT_PASSWORD",
    "DEFAULT_SSH_PORT",
    "DEFAULT_USERNAME",
    "DEVICE_TYPE",
    "HOSTNAME",
    "SCRAPLI_PLATFORM",
    "SYS_PROMPT",
    "USER_PROMPT",
    "dispatch",
    "normalize_command",
]
