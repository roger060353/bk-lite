# Hardware Server Redfish 监控 mock：DMTF 风格 HTTPS BMC。
# 只实现监控采集器读取的 Systems/Chassis Thermal+Power/Storage/NIC，不是 CMDB 资产树。
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY inventory.py server.py __init__.py __main__.py /app/redfish_monitor_mock/

ENV PYTHONPATH=/app \
    REDFISH_HOST=0.0.0.0 \
    REDFISH_PORT=443 \
    REDFISH_USERNAME=redfish \
    REDFISH_PASSWORD=RedfishMon1

EXPOSE 443
HEALTHCHECK --interval=30s --timeout=8s --start-period=10s --retries=3 \
    CMD python3 -c "import ssl,urllib.request; urllib.request.urlopen('https://127.0.0.1/redfish/v1/', context=ssl._create_unverified_context(), timeout=5)"

CMD ["python3", "-m", "redfish_monitor_mock", "--host", "0.0.0.0", "--port", "443"]
