# Hardware Server IPMI 监控 mock：OpenIPMI ipmi_sim（官方 lanserv）。
# 只提供 Telegraf ipmi_sensor 需要的 SDR + chassis power，不是 CMDB 资产采集。
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openipmi ipmitool ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY lan.conf.template ipmi.emu docker-entrypoint.sh /etc/ipmi/
RUN chmod +x /etc/ipmi/docker-entrypoint.sh \
    && mkdir -p /var/lib/ipmi_sim

ENV IPMI_USERNAME=admin \
    IPMI_PASSWORD=IpmiMon1 \
    IPMI_LAN_TEMPLATE=/etc/ipmi/lan.conf.template \
    IPMI_EMU=/etc/ipmi/ipmi.emu \
    IPMI_STATE_DIR=/var/lib/ipmi_sim

EXPOSE 623/udp
HEALTHCHECK --interval=30s --timeout=8s --start-period=15s --retries=3 \
    CMD ipmitool -I lanplus -H 127.0.0.1 -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" chassis power status | grep -qi on

ENTRYPOINT ["/etc/ipmi/docker-entrypoint.sh"]
