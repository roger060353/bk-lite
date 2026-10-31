#!/bin/sh
# TEST-ONLY OpenIPMI ipmi_sim. 不记录口令。
set -eu

CONF_TEMPLATE="${IPMI_LAN_TEMPLATE:-/etc/ipmi/lan.conf.template}"
EMU_FILE="${IPMI_EMU:-/etc/ipmi/ipmi.emu}"
STATE_DIR="${IPMI_STATE_DIR:-/var/lib/ipmi_sim}"
LISTEN_CONF="${STATE_DIR}/lan.conf"

USERNAME="${IPMI_USERNAME:-admin}"
PASSWORD="${IPMI_PASSWORD:-IpmiMon1}"

mkdir -p "$STATE_DIR"
# 口令只允许字母数字，避免 sed 分隔符与 IPMI 插件转义问题。
case "$USERNAME$PASSWORD" in
  *[!A-Za-z0-9]*)
    echo "IPMI_USERNAME/IPMI_PASSWORD must be alphanumeric for this mock" >&2
    exit 1
    ;;
esac

sed "s|IPMI_USERNAME|${USERNAME}|g; s|IPMI_PASSWORD|${PASSWORD}|g" "$CONF_TEMPLATE" > "$LISTEN_CONF"

cd "$STATE_DIR"
exec ipmi_sim -n -c "$LISTEN_CONF" -f "$EMU_FILE" -s "$STATE_DIR"
