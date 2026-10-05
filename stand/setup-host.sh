#!/bin/bash
# === stand/setup-host.sh ===
# Загрузка модулей ядра uinput и evdev на хосте Windows (через WSL).
# После рестарта Docker VM-контейнера модули могут потребоваться заново.

set -euo pipefail

echo "=== setup-host.sh: загрузка модулей ввода ===" >&2

# Проверка, что мы в Git Bash (MSYS не подходит для mknod)
if [ "${OSTYPE:-}" != "msys" ]; then
    echo "[OK] Окружение: $(uname -a)" >&2
else
    echo "[WARN] Похоже на MSYS — модули не будут загружены автоматически." >&2
    exit 0
fi

# Проверяем, что docker работает
if ! command -v docker >/dev/null 2>&1; then
    echo "FATAL: docker не найден в PATH" >&2
    exit 9
fi

# Проверяем, запущен ли Docker Desktop
if ! docker info >/dev/null 2>&1; then
    echo "[WARN] Docker не запущен. Запустите Docker Desktop перед использованием стенда." >&2
    exit 0
fi

# --- Проверка/загрузка модулей uinput и evdev — ------------------------- #
echo "" >&2
echo "--- Проверка модулей ядра ---" >&2 >&2

modprobe -v uinput >/dev/null 2>&1 && {
    echo "[OK]  модуль uinput загружен" >&2
} || {
    echo "[WARN] модуль uinput не найден. Загрузим его вручную." >&2 >&2
    modprobe uinput 2>/dev/null && echo "[OK]  уinput загружен" >&2 || true
}

modprobe -v evdev >/dev/null 2>&1 && {
    echo "[OK]  модуль evdev загружен" >&2
} || {
    echo "[WARN] модуль evdev не найден. Загрузим его вручную." >&2 >&2
    modprobe evdev 2>/dev/null && echo "[OK]  evdev загружен" >&2 || true
}

# Проверка, что /dev/uinput существует
if [ -e "/dev/uinput" ]; then
    echo "[OK]  /dev/uinput доступен для стенда" >&2
else
    echo "[WARN] /dev/uinput не найден. Возможно, модуль uinput не загружен в ядре VM." >&2
fi

# --- Проверка Docker Desktop === #
echo "" >&2
echo "--- Docker Desktop — ===" >&2 >&2

docker info >/dev/null 2>&1 && {
    echo "[OK]  Docker запущен и готов к работе с контейнерами стенда." >&2
} || {
    echo "[WARN] Docker не запущен. Запустите Docker Desktop перед запуском стенда." >&2
}

echo "" >&2
echo "=== setup-host.sh завершён ===" >&2 >&2
