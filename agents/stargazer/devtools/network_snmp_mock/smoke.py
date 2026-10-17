# -*- coding: utf-8 -*-
"""校验 network SNMP mock 的 walk 数据，并可选对存活 snmpsim 跑与 SnmpFacts 同形的 GET/GETBULK。"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent / "data" / "profiles"

SYSTEM_OIDS = (
    "1.3.6.1.2.1.1.1.0",
    "1.3.6.1.2.1.1.2.0",
    "1.3.6.1.2.1.1.4.0",
    "1.3.6.1.2.1.1.5.0",
    "1.3.6.1.2.1.1.6.0",
)
INTERFACE_COLUMNS = (
    "1.3.6.1.2.1.2.2.1.1",
    "1.3.6.1.2.1.2.2.1.2",
    "1.3.6.1.2.1.2.2.1.4",
    "1.3.6.1.2.1.2.2.1.5",
    "1.3.6.1.2.1.2.2.1.6",
    "1.3.6.1.2.1.2.2.1.7",
    "1.3.6.1.2.1.2.2.1.8",
    "1.3.6.1.2.1.31.1.1.1.18",
)

PROFILES = {
    "huawei": {
        "file": "huawei.snmprec",
        "sysobjectid": "1.3.6.1.4.1.2011.2.23.145",
        "sysname": "jp-mock-huawei-s5700",
        "brand": "Huawei",
        "model": "S5700-24TP-SI-AC",
        "if_count": 4,
    },
    "cisco": {
        "file": "cisco.snmprec",
        "sysobjectid": "1.3.6.1.4.1.9.1.1208",
        "sysname": "jp-mock-cisco-c2960",
        "brand": "Cisco",
        "model": "cat29xxStack",
        "if_count": 4,
    },
}


def parse_snmprec(path: Path) -> dict[str, tuple[str, str]]:
    records = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        oid, tag, value = line.split("|", 2)
        records[oid] = (tag, value)
    return records


def assert_walk_files() -> dict[str, dict[str, tuple[str, str]]]:
    loaded = {}
    for name, spec in PROFILES.items():
        path = PROFILE_DIR / spec["file"]
        if not path.is_file():
            raise AssertionError("missing walk file: {}".format(path))
        records = parse_snmprec(path)
        for oid in SYSTEM_OIDS:
            if oid not in records:
                raise AssertionError("{} missing system OID {}".format(name, oid))
        soid_tag, soid_value = records["1.3.6.1.2.1.1.2.0"]
        if soid_tag != "6" or soid_value != spec["sysobjectid"]:
            raise AssertionError("{} sysObjectID want {}|6, got {}|{}".format(name, spec["sysobjectid"], soid_tag, soid_value))
        sysname = records["1.3.6.1.2.1.1.5.0"][1]
        if sysname != spec["sysname"]:
            raise AssertionError("{} sysName want {}, got {}".format(name, spec["sysname"], sysname))
        indexes = []
        for oid in records:
            if oid.startswith("1.3.6.1.2.1.2.2.1.1."):
                indexes.append(oid.rsplit(".", 1)[-1])
        if len(indexes) != spec["if_count"]:
            raise AssertionError("{} ifIndex count want {}, got {}".format(name, spec["if_count"], len(indexes)))
        for column in INTERFACE_COLUMNS:
            missing = [index for index in indexes if "{}.{}".format(column, index) not in records]
            if missing:
                raise AssertionError("{} column {} missing indexes {}".format(name, column, missing))
        loaded[name] = records
    return loaded


def _oid_text(obj) -> str:
    pretty = getattr(obj, "prettyPrint", None)
    return (pretty() if callable(pretty) else str(obj)).lstrip(".")


def _is_prefix(root: str, oid: str) -> bool:
    return oid == root or oid.startswith(root + ".")


async def collect_live(host: str, port: int, community: str) -> dict:
    """与 SnmpFacts 相同的 5 标量 GET + 8 列 GETBULK，不依赖 Sanic。"""
    from pysnmp.hlapi.asyncio import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        bulkCmd,
        getCmd,
    )

    engine = SnmpEngine()
    auth = CommunityData(community)
    target = UdpTransportTarget((host, port), timeout=5, retries=1)
    context = ContextData()
    error, status, _index, var_binds = await getCmd(
        engine,
        auth,
        target,
        context,
        *[ObjectType(ObjectIdentity(oid)) for oid in SYSTEM_OIDS],
        lookupMib=False,
    )
    if error or status:
        raise RuntimeError("SNMP system GET failed: {}".format(error or status))
    system = {_oid_text(name): _oid_text(value) for name, value in var_binds}

    current = [ObjectType(ObjectIdentity(oid)) for oid in INTERFACE_COLUMNS]
    ended = [False] * len(INTERFACE_COLUMNS)
    interfaces = []
    while not all(ended):
        error, status, _index, table = await bulkCmd(engine, auth, target, context, 0, 25, *current, lookupMib=False)
        if error or status:
            raise RuntimeError("SNMP interface GETBULK failed: {}".format(error or status))
        progressed = False
        for row in table or []:
            interface = {}
            nxt = []
            for col, (name, value) in enumerate(row):
                oid = _oid_text(name)
                val = _oid_text(value)
                if ended[col] or val == "No more variables left in this MIB View" or not _is_prefix(INTERFACE_COLUMNS[col], oid):
                    ended[col] = True
                    nxt.append(current[col])
                    continue
                interface[INTERFACE_COLUMNS[col]] = val
                nxt.append(ObjectType(ObjectIdentity(oid)))
            current = nxt
            if interface:
                interfaces.append(interface)
                progressed = True
            if all(ended):
                break
        if not progressed:
            break
    return {"system": system, "interfaces": interfaces}


def assert_collect_payload(result: dict, profile: str) -> None:
    spec = PROFILES[profile]
    system = result["system"]
    soid = system["1.3.6.1.2.1.1.2.0"]
    sysname = system["1.3.6.1.2.1.1.5.0"]
    assert soid == spec["sysobjectid"], (soid, spec["sysobjectid"])
    assert sysname == spec["sysname"], (sysname, spec["sysname"])
    interfaces = result["interfaces"]
    assert len(interfaces) == spec["if_count"], interfaces
    assert all(item.get("1.3.6.1.2.1.2.2.1.1") for item in interfaces), interfaces
    assert all(item.get("1.3.6.1.2.1.2.2.1.2") for item in interfaces), interfaces


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="network SNMP mock smoke")
    parser.add_argument("--live", nargs=3, metavar=("HOST", "PORT", "COMMUNITY"), help="对存活 snmpsim 跑与 SnmpFacts 同形的 GET/GETBULK")
    parser.add_argument("--profile", choices=sorted(PROFILES), help="--live 时断言的厂商档案")
    args = parser.parse_args(argv)

    assert_walk_files()
    print("walk-data ok: huawei + cisco")

    if args.live:
        host, port_text, community = args.live
        profile = args.profile
        if not profile:
            raise SystemExit("--live 需要同时指定 --profile huawei|cisco")
        result = asyncio.run(collect_live(host, int(port_text), community))
        assert_collect_payload(result, profile)
        system = result["system"]
        print(
            "snmp_facts-shape ok: profile={} sysname={} soid={} interfaces={}".format(
                profile,
                system["1.3.6.1.2.1.1.5.0"],
                system["1.3.6.1.2.1.1.2.0"],
                len(result["interfaces"]),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
