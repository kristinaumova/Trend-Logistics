#!/bin/sh
# В режиме network_mode: service:backend API доступен на 127.0.0.1:8000
BACKEND_URL="${WAIT_BACKEND_URL:-http://127.0.0.1:8000/healthz}"
echo "Waiting for API at ${BACKEND_URL} ..."
i=0
while [ "$i" -lt 120 ]; do
  if curl -sf "$BACKEND_URL" > /dev/null 2>&1; then
    echo "API is reachable."
    exec nginx -g "daemon off;"
  fi
  i=$((i + 1))
  sleep 1
done
echo "WARNING: API not reachable after 120s — starting nginx anyway."
exec nginx -g "daemon off;"
