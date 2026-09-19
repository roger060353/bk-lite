#!/bin/bash
# 容器内生成短期自签证书并在 0.0.0.0 上启动合成 Redfish。
# 不记录密码、token 或请求体。
set -euo pipefail

BIND="${REDFISH_MOCK_BIND:-0.0.0.0}"
PORT="${REDFISH_MOCK_PORT:-443}"
PROFILE="${REDFISH_MOCK_PROFILE:-x86}"
SCENARIO="${REDFISH_MOCK_SCENARIO:-healthy}"
TLS_DIR="${REDFISH_MOCK_TLS_DIR:-/tmp/redfish-mock-tls}"

if [ -z "${REDFISH_MOCK_USERNAME:-}" ] || [ -z "${REDFISH_MOCK_PASSWORD:-}" ]; then
  echo "set REDFISH_MOCK_USERNAME and REDFISH_MOCK_PASSWORD" >&2
  exit 1
fi

mkdir -p "$TLS_DIR"
CNF="$TLS_DIR/tls.cnf"
{
  echo "[req]"
  echo "prompt = no"
  echo "distinguished_name = subject"
  echo "x509_extensions = extensions"
  echo
  echo "[subject]"
  echo "CN = huawei-redfish-target"
  echo
  echo "[extensions]"
  echo "subjectAltName = @alt_names"
  echo "basicConstraints = critical,CA:TRUE"
  echo "keyUsage = critical,digitalSignature,keyEncipherment,keyCertSign"
  echo
  echo "[alt_names]"
  echo "DNS.1 = localhost"
  echo "DNS.2 = huawei-redfish-target"
  echo "IP.1 = 127.0.0.1"
} > "$CNF"

idx=2
for addr in $(hostname -I 2>/dev/null || true); do
  case "$addr" in
    127.*|::1) continue ;;
  esac
  echo "IP.${idx} = ${addr}" >> "$CNF"
  idx=$((idx + 1))
done

openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
  -keyout "$TLS_DIR/key.pem" \
  -out "$TLS_DIR/cert.pem" \
  -config "$CNF" >/dev/null 2>&1

exec python3 mock_server.py \
  --bind "$BIND" \
  --port "$PORT" \
  --profile "$PROFILE" \
  --scenario "$SCENARIO" \
  --cert "$TLS_DIR/cert.pem" \
  --key "$TLS_DIR/key.pem"
