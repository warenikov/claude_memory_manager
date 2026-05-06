#!/usr/bin/env bash
# Запуск Claude Memory Manager на любом свободном порту с автооткрытием в браузере.

set -e
cd "$(dirname "$0")"

# 1. Найти свободный порт (через Python — он есть везде)
HOST_PORT=$(python3 -c '
import socket
s = socket.socket()
s.bind(("", 0))
print(s.getsockname()[1])
s.close()
')
export HOST_PORT

URL="http://localhost:${HOST_PORT}"
echo "→ Free port: ${HOST_PORT}"

# 2. Перезапустить контейнер
docker compose down 2>/dev/null || true
docker compose up -d --build

# 3. Дождаться готовности сервиса
echo -n "→ Waiting for service"
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null "${URL}/api/config" 2>/dev/null; then
    echo " — ready."
    break
  fi
  echo -n "."
  sleep 1
done

# 4. Открыть в браузере (Mac / Linux / Windows-Git-Bash)
case "$(uname -s)" in
  Darwin)            open "${URL}" ;;
  Linux)             xdg-open "${URL}" >/dev/null 2>&1 || true ;;
  MINGW*|CYGWIN*|MSYS*) start "${URL}" ;;
esac

echo "✓ Running at: ${URL}"
