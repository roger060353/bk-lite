# OPS ONLY / throwaway — 日本 CMDB network SNMP 采集 mock
FROM python:3.12-slim

RUN pip install --no-cache-dir "snmpsim-lextudio==1.1.1"

WORKDIR /opt/snmpsim
COPY data/profiles /opt/snmpsim/profiles

# 默认挂成 public.snmprec（community=public）。单容器切厂商时改挂 combined。
ENV SNMPSIM_DATA_DIR=/opt/snmpsim/data
ENV SNMPSIM_CACHE_DIR=/tmp/snmpsim-cache

RUN mkdir -p /opt/snmpsim/data /tmp/snmpsim-cache

EXPOSE 161/udp

CMD ["sh", "-c", "snmpsim-command-responder --data-dir=\"${SNMPSIM_DATA_DIR}\" --cache-dir=\"${SNMPSIM_CACHE_DIR}\" --agent-udpv4-endpoint=0.0.0.0:161"]
