# -*- coding: utf-8 -*-
"""生成 OpenIPMI ipmi_sim 的 lan.conf / ipmi.emu。"""
from __future__ import annotations

from pathlib import Path

from .catalog import DEFAULT_PASSWORD, DEFAULT_USERNAME, SENSORS
from .sdr import hex_bytes, records_for

HERE = Path(__file__).resolve().parent
LAN_CONF_NAME = "lan.conf"
EMU_NAME = "ipmi.emu"
USERNAME_TOKEN = "FAKESECRET_e4f5g6h7i8j9k0l1m2n3"
PASSWORD_TOKEN = "IPMI_PASSWORD"


def render_lan_conf(username: str = DEFAULT_USERNAME, password: str = DEFAULT_PASSWORD) -> str:
    # 官方 OpenIPMI lanserv/lan.conf：startlan + guid（IPMI 2.0 / lanplus）+ user。
    # 去掉 qemu/serial/lan_config_program，只留监控刮取需要的 RMCP 面。
    return f"""# OpenIPMI ipmi_sim — Hardware Server IPMI monitor mock
# 基于 cminyard/openipmi lanserv/lan.conf，去掉 VM/SOL，监听 UDP/623。
name "ipmisim1"

set_working_mc 0x20
  startlan 1
    addr 0.0.0.0 623
    priv_limit admin
    allowed_auths_callback none md2 md5 straight
    allowed_auths_user none md2 md5 straight
    allowed_auths_operator none md2 md5 straight
    allowed_auths_admin none md2 md5 straight
    guid a123456789abcdefa123456789abcdef
  endlan

  user 1 true  "" "{password}" user 10 none md2 md5 straight
  user 2 true  "{username}" "{password}" admin 10 none md2 md5 straight
"""


def render_lan_conf_template() -> str:
    return render_lan_conf(USERNAME_TOKEN, PASSWORD_TOKEN)


def render_emu() -> str:
    lines = [
        "# OpenIPMI ipmi_sim emulator — Hardware Server IPMI monitor mock",
        "# 结构对齐官方 lanserv/ipmisim1.emu：mc_setbmc / mc_add / sensor 0=watchdog / mc_enable。",
        "# 额外补监控插件需要的温度/风扇/功耗/电压 + host_power SDR。",
        "",
        "mc_setbmc 0x20",
        "mc_add 0x20 0 no-device-sdrs 0x23 9 8 0x9f 0x1291 0xf02 persist_sdr",
        "sel_enable 0x20 1000 0x0a",
        "",
        "# Watchdog sensor. This must be sensor zero.",
        "sensor_add 0x20 0 0 35 0x6f event-only",
        "sensor_set_event_support 0x20 0 0 enable scanning per-state \\",
        "	000000000001111 000000000000000 \\",
        "	000000000001111 000000000000000",
        "",
    ]
    for sensor, record in records_for(SENSORS):
        number = sensor["number"]
        if sensor["kind"] == "analog":
            lines.append(f"# {sensor['name']} {sensor['value']} {sensor['ipmitool_unit']}")
            lines.append(f"sensor_add 0x20 0 {number} {sensor['sensor_type']} 0x01")
            lines.append(f"sensor_set_value 0x20 0 {number} {sensor['raw']} 0")
            if sensor.get("upper_critical_raw") is not None:
                upper = int(sensor["upper_critical_raw"])
                lines.append(
                    f"sensor_set_threshold 0x20 0 {number} settable 111000 0x{upper:02x} 0x{upper:02x} 0x{upper:02x} 00 00 00"
                )
            lines.append("sensor_set_event_support 0x20 0 {0} enable scanning per-state \\".format(number))
            lines.append("	000111111000000 000111111000000 \\")
            lines.append("	000111111000000 000111111000000")
        else:
            lines.append(f"# {sensor['name']} discrete (ipmi_sensor_status ok=1)")
            lines.append(f"sensor_add 0x20 0 {number} {sensor['sensor_type']} 0x6f")
            lines.append(f"sensor_set_bit_clr_rest 0x20 0 {number} {sensor['bit']} 1")
            lines.append("sensor_set_event_support 0x20 0 {0} enable scanning per-state \\".format(number))
            lines.append("	000000000000011 000000000000011 \\")
            lines.append("	000000000000011 000000000000011")
        lines.append(f"main_sdr_add 0x20 {hex_bytes(record)}")
        lines.append("")
    lines.append("mc_enable 0x20")
    lines.append("")
    return "\n".join(lines)


def write_generated(directory: Path | None = None) -> tuple[Path, Path, Path]:
    root = directory or HERE
    lan_path = root / LAN_CONF_NAME
    template_path = root / "lan.conf.template"
    emu_path = root / EMU_NAME
    lan_path.write_text(render_lan_conf(), encoding="utf-8")
    template_path.write_text(render_lan_conf_template(), encoding="utf-8")
    emu_path.write_text(render_emu(), encoding="utf-8")
    return lan_path, template_path, emu_path


def main() -> int:
    write_generated()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
