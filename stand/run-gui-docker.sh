#!/usr/bin/env bash
set -euo pipefail

# === stand/run-gui-docker.sh ===
# Поднимает стенд GUI xswitcher в Docker-контейнере с noVNC.
# Для тестирования физического ввода через xdotool (Windows + noVNC:6081).
#
# Требования на хосте (Windows):
#   - Docker Desktop запущен
#   - Модули uinput и evdev загружены в ядре VM Windows
#     (запускается автоматически stand/setup-host.sh)
#   - Порт 6081 свободен
#
# Результат:
#   noVNC доступен по http://host.docker.internal:6081
#
# Использование:
#   bash stand/run-gui-docker.sh

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

DOCKER="${DOCKER:-/f/Docker/resources/bin/docker}"
WS="$(cygpath -w "$REPO")"

# --- 1. Поднимаем контейнер с GUI стендом ------------------------------- #
echo "=== Старт: поднимаю GUI стенд xswitcher ===" >&2

"${DOCKER}" run --rm --privileged \
    -e DUMPLOG="${DUMPLOG:-}" \
    -p 6081:5900 \
    -p 3001:3001/udp \
    -v "$WS:/w" \
    -v "$WS/.gomodcache:/root/go/pkg/mod" \
    xswitcher-stand bash /w/stand/run-gui.sh

# --- 2. Если стенд завершил с ошибкой — показываем лог ------------------- #
echo "=== Стенд завершился. Показываю последние строки лога ===" >&2
cat "$REPO/.docker/gui.log" 2>/dev/null | tail -30 || true

# --- 3. Подсказка, как проверить через noVNC ---------------------------- #
echo "" >&2
echo "GUI стенд запущен. Откройте в браузере:" >&2
echo "  http://host.docker.internal:6081" >&2
echo "" >&2
echo "В окне вы увидите GUI xswitcher (About tab)." >&2
echo "Теперь можно запускать тесты из test_xswitcher_with_physical_input.py." >&2
echo "" >&2

exit 0
