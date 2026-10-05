#!/usr/bin/env bash
set -euo pipefail

# === stand/run-gui.sh ===
# Запуск GUI-демона xswitcher внутри контейнера стенда.
#
# Архитектура:
#   — Образ (Dockerfile.gui) компилирует daemon и GUI в stage "builder".
#   — Этап "app" просто запускает бинарники из builder вместе с noVNC-сервером.
#
# Горячая клавиша переключения раскладки задаётся через:
#     XSWITCHER_HOTKEY="ctrl+alt+s"
#
# Доступ к GUI через браузер: http://host.docker.internal:${NOVNC_PORT}/noVNC/

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

# Переменные окружения стенда (из docker-compose)
export LC_ALL="${LC_ALL:-C}"
export XSWITCHER_LANG="${XSWITCHER_LANG:-en}"
export DUMPLOG="${DUMPLOG:-0}"
export NOVNC_PORT="${NOVNC_PORT:-6081}"

# Горячая клавиша — из env или дефолт
HOTKEY="${XSWITCHER_HOTKEY:-ctrl+alt+s}"

say() { printf '%-46s %s\n' "$1" "${2:-}"; }
die() { say "[FAIL]" "$1"; exit 9; }

LOG=/tmp/xswitcher-gui.log
TSV=/w/keybd.tsv

# --- 1. Подготовка конфига стенда ---------------------------------------- #
echo "--- 1. Конфигурация GUI стенда ---" >&2

CONF=/w/stand.conf
cat >"$CONF" <<EOF
[Daemon]
Respawn = -1
Exec = /w/bin/xswitcher-daemon

[ScanDevices]
Test = "/dev/input/event0"

# Горячая клавиша переключения раскладки.
# Формат: [modifier]+[key], например "ctrl+alt+s" или "win_l space".
Keys.Hotkey   = ${HOTKEY}

# RetypeWord trigger (Pause key)
Keys.Pause    = 4679,1

[Action.RetypeWord]
Actions = [Action.Wipe, Action.Switch, Action.Restore]

[Action.Wipe]
Exec    = /bin/echo "BACKSPACE" >"$TSV"

[Action.Switch]
Layouts = [0]

[Action.Restore]
Exec    = /bin/echo "RETYPE" >"$TSV"
EOF

say "[OK] конфиг: $CONF (hotkey=$HOTKEY)" >&2

# --- 2. Xvfb (виртуальный экран) ---------------------------------------- #
echo "--- 2. X server ---" >&2
Xvfb :99 -screen 0 1280x720x16 >/tmp/xvfb.log 2>&1 &
XVFB_PID=$!
for i in $(seq 30); do
    [ -e /tmp/.X11-unix/X99 ] && break
    sleep 0.5
done
[ -e /tmp/.X11-unix/X99 ] || die "Xvfb не запустился (см. /tmp/xvfb.log)"
say "[OK] X server ready (:99)"

# --- 3. Запуск GUI-демона ----------------------------------------------- #
echo "--- 3. GUI xswitcher ---" >&2

cd /w
export GOFLAGS=-buildvcs=false

go build -o /tmp/xswitcher-gui ./cmd/gui/ >/tmp/build.log 2>&1 || \
    die "сборка GUI провалилась (см. /tmp/build.log)"

say "[OK] бинар: $(which xswitcher-gui)" >&2

# Запускаем демон с флагом -gui, читаем конфиг стенда.
/tmp/xswitcher-gui -c "$CONF" >"$LOG" 2>&1 &
GUI_PID=$!

say "xswitcher GUI запущен (PID=$GUI_PID)" >&2

sleep 3

if ! kill -0 $GUI_PID 2>/dev/null; then
    say "[FAIL] демон умер при запуске"
    tail -40 "$LOG" >&2
    exit 9
fi

say "Демон жив: $(kill -0 $GUI_PID 2>/dev/null && echo yes || echo no)" >&2

# --- 4. Проверка, что hotkey был принят -------------------------------- #
echo "--- 4. Проверка hotkey ---" >&2
sleep 1
grep -q "Hotkey.*$HOTKEY" "$LOG" 2>/dev/null && \
    say "[OK] hotkey $HOTKEY зафиксирован в логах" || \
    say "[WARN] hotkey не найден в логах (проверьте конфиг)" >&2

# --- 5. noVNC уже запущен через websockify ------------------------------ #
echo "--- 5. noVNC ---" >&2
say "noVNC: http://host.docker.internal:${NOVNC_PORT}/noVNC/" >&2

# --- 6. Готовность к тестам --------------------------------------------- #
echo "" >&2
echo "=== Стенд GUI готов ===" >&2
echo "" >&2
echo "Что можно проверить:" >&2
echo "  • Откройте http://host.docker.internal:${NOVNC_PORT}/noVNC/" >&2
echo "  • В окне GUI перейдите на About и наберите текст." >&2
echo "  • Нажмите горячую клавишу ($HOTKEY) — раскладка переключится." >&2
echo "" >&2

# --- 7. Очистка при завершении контейнера ------------------------------- #
trap 'say "Останавливаю демон..."; kill $GUI_PID 2>/dev/null; \
       say "Останавливаю Xvfb..."; kill $XVFB_PID 2>/dev/null; true' EXIT

wait $XVFB_PID 2>/dev/null || true

echo "=== Стенд остановлен ===" >&2
exit 0
