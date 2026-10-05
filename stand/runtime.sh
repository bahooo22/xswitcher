#!/bin/bash
# === stand/runtime.sh ===
# Генерирует runtime-конфигурацию GUI стенда.
# Вызывается из docker-compose.gui.yml перед сборкой образа.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# Переменные окружения стенда (подставляются в runtime-gui.yml)
export HOST_PATH="${HOST_PATH:-E:/eXample/Documents/Source/Github/Fork/xswitcher}"
export NOVNC_PORT="${NOVNC_PORT:-6081}"
export NOVNC_HOSTNAME="${NOVNC_HOSTNAME:-host.docker.internal}"
export XVFB_DISPLAY="${XVFB_DISPLAY:-99}"
export XVFB_WIDTH="${XVFB_WIDTH:-1280}"
export XVFB_HEIGHT="${XVFB_HEIGHT:-720}"

# --- Вывод конфигурации для отладки (не в файл) --- #
echo "=== Стенд GUI xswitcher ===" >&2
echo "" >&2
echo "Гостевая папка: $HOST_PATH" >&2
echo "noVNC порт хоста: $NOVNC_PORT" >&2
echo "ноутн-хост: ${NOVNC_HOSTNAME}" >&2
echo "Xvfb дисплей: :$XVFB_DISPLAY (${XVFB_WIDTH}x${XVFB_HEIGHT})" >&2
echo "" >&2

# --- Генерация runtime.yml --- #
cat > "$HERE/runtime-gui.yml" <<EOF
# === stand/runtime-gui.yml (генерировано) ===
# Авто-генерируется из runtime.sh. Не редактируйте вручную!

guest-path: "${HOST_PATH}"
novnc-port: ${NOVNC_PORT}
novnc-hostname: "${NOVNC_HOSTNAME}"
xvfb-display: ${XVFB_DISPLAY}
xvfb-width: ${XVFB_WIDTH}
xvfb-height: ${XVFB_HEIGHT}
EOF

echo "runtime-gui.yml создан." >&2
echo "" >&2
echo "Для запуска стенда выполните:" >&2
echo '  cd stand && docker compose -f docker-compose.gui.yml up --build --detach' >&2
echo "" >&2
echo "Затем откройте в браузере: ${NOVNC_HOSTNAME}:${NOVNC_PORT}/noVNC/" >&2
