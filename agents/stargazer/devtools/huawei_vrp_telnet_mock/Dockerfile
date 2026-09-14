# TEST-ONLY：华为 VRP Telnet 替身。拉不到官方镜像时把 FROM 改成
# docker.m.daocloud.io/library/python:3.12-slim
FROM python:3.12-slim

WORKDIR /app
COPY server.py /app/server.py
ENV PYTHONUNBUFFERED=1
ENV HUAWEI_VRP_TELNET_HOST=0.0.0.0
ENV HUAWEI_VRP_TELNET_PORT=23
EXPOSE 23
CMD ["python", "/app/server.py", "--host", "0.0.0.0", "--port", "23"]
