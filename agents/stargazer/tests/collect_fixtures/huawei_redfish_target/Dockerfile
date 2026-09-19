FROM docker.m.daocloud.io/library/python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 构建时走 host 网络（见 compose build.network），避免 Docker bridge 访问 Debian 源超时。
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/redfish-mock
COPY mock_server.py inventory.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 443
CMD ["./entrypoint.sh"]
