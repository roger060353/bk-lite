# -*- coding: utf-8 -*-
"""存储以太口 / FC 口采集身份：MAC 与 nic 同一约定，WWPN 归一化为冒号分隔小写。"""
import ipaddress
import re

from apps.cmdb.collection.nic_inventory import normalize_nic_mac

_HEX_WWPN_RE = re.compile(r"^[0-9a-f]{16}$|^[0-9a-f]{32}$")
_EMPTY_WWPN = frozenset({"0" * 16, "0" * 32})
_EMPTY_TOKENS = frozenset({"", "n/a", "na", "none", "null", "unknown", "-", "--"})
_ETH_MAC_KEYS = ("MACADDRESS", "MACADDR", "mac")
_FC_WWPN_KEYS = ("WWN", "WWPN", "wwpn")
_ETH_IP_KEYS = ("IPV4ADDR", "LOGICIP", "ip_addr")
_FC_SPEED_KEYS = ("RUNSPEED", "MAXSPEED", "SPEED")


def normalize_storage_mac(raw) -> str:
    """与 nic 相同：小写冒号分隔 aa:bb:cc:dd:ee:ff；非法或空值返回空串。"""
    return normalize_nic_mac(raw)


def normalize_wwpn(raw) -> str:
    """把 WWPN 规范成小写冒号分隔；接受 8 字节或 16 字节十六进制，非法或空值返回空串。"""
    if raw is None:
        return ""
    token = str(raw).strip().lower()
    if token.startswith("0x"):
        token = token[2:]
    if token in _EMPTY_TOKENS:
        return ""
    hex_only = re.sub(r"[^0-9a-f]", "", token)
    if hex_only in _EMPTY_WWPN or not _HEX_WWPN_RE.fullmatch(hex_only):
        return ""
    return ":".join(hex_only[index : index + 2] for index in range(0, len(hex_only), 2))


def _first_present(data, keys):
    if not isinstance(data, dict):
        return ""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def raw_eth_mac(data) -> str:
    return _first_present(data, _ETH_MAC_KEYS)


def raw_fc_wwpn(data) -> str:
    return _first_present(data, _FC_WWPN_KEYS)


def optional_ipv4(raw) -> str:
    """只回填合法 IPv4；空值、占位符和非法地址返回空串。"""
    if raw is None:
        return ""
    token = str(raw).strip()
    if token.lower() in _EMPTY_TOKENS or token == "0.0.0.0":
        return ""
    try:
        address = ipaddress.IPv4Address(token)
    except (ipaddress.AddressValueError, ValueError):
        return ""
    if address.is_unspecified:
        return ""
    return token


def optional_speed(data) -> str:
    raw = _first_present(data, _FC_SPEED_KEYS)
    if raw is None:
        return ""
    token = str(raw).strip()
    if token.lower() in _EMPTY_TOKENS:
        return ""
    return token


def eth_port_identity(data) -> str:
    return normalize_storage_mac(raw_eth_mac(data))


def fc_port_identity(data) -> str:
    return normalize_wwpn(raw_fc_wwpn(data))
