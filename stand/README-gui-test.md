# GUI стенд для тестов xswitcher с физическим вводом

Этот стенд предназначен для проверки переключения раскладки через **физический ввод** клавиш (через `xdotool`) на графическом интерфейсе.

## Что проверяет этот стенд

- ✓ Демон запущен и реагирует на события клавиатуры.
- ✓ Горячая клавиша (`Win+Space` / `Super+Space`) переключает раскладку.
- ✓ Текст, введённый в неправильной раскладке («ghbdtn»), отображается корректно после переключения.
- ✓ Курсор не «улетает» при нажатии горячей клавиши.
- ✓ Активное окно не меняется.

## Архитектура стенда

```
┌─────────────────────────────────────────┐
│   Windows 11 (24H2) — хост              │
│   ├─ Docker Desktop запущен             │
│   └─ noVNC:6081 → Xvfb :99             │
└─────────────────────────────────────────┘
           ↓ WebSocket
┌─────────────────────────────────────────┐
│  xswitcher-stand (Docker контейнер)      │
│   ├─ Alpine + Python3                   │
│   ├─ Xvfb :99                          │
│   ├─ /w/bin/xswitcher-gui             │
│   └─ noVNC (порт 6081 ←→ 5900)        │
└─────────────────────────────────────────┘

Тестовый сценарий:
  1. Открываем http://host.docker.internal:6081/noVNC/
  2. Видим GUI xswitcher (About tab).
  3. Запускаем тест из stand/tests/physical_input_test.py:
       pytest stand/tests/physical_input_test.py -v
```

## Установка на хосте (Windows)

1. Убедитесь, что Docker Desktop запущен и модули `uinput` + `evdev` загружены:
   ```bash
   stand/setup-host.sh
   ```
2. Поднимите стенд:
   ```bash
   cd stand && docker compose -f docker-compose.gui.yml up --build --detach
   ```

## Запуск тестов

```bash
# После того как стенд запущен, откройте в браузере noVNC и убедитесь, что GUI работает.
# Затем из Windows запускайте pytest:

pip install pytest xdotool

pytest stand/tests/physical_input_test.py -v
```

## Как отладить вручную через noVNC

1. Откройте `http://host.docker.internal:6081/noVNC/` в браузере.
2. В окне GUI нажмите **About** (вкладка «О программе»).
3. Наберите текст в поле ввода.
4. Нажмите горячую клавишу (`Win+Space`) — раскладка переключится, текст изменится.

## Точные координаты поля ввода

Для автоматического клика `xdotool` нужно знать точную позицию поля ввода внутри окна xswitcher:

```bash
# В noVNC откройте About и введите тестовый текст, затем:
xdotool getmouselocation --shell
```

Я использовал координаты `x=237`, `y=437` (измерено на скриншоте `gui-screenshot.png`). Если окно смещается — скорректируйте значения в `stand/tests/physical_input_test.py`.

## Развёртывание стенда (команда)

```bash
cd E:\eXample\Documents\Source\Github\Fork\xswitcher\stand
docker compose -f docker-compose.gui.yml up --build --detach
```

После запуска откройте `http://host.docker.internal:6081/noVNC/`.

## Связанные файлы

| Файл | Описание |
|------|----------|
| `stand/tests/physical_input_test.py` | Автотесты физического ввода через xdotool |
| `stand/run-gui-docker.sh` | Запуск стенда GUI из Docker Desktop |
| `stand/docker-compose.gui.yml` | Конфигурация стенда (noVNC + xswitcher) |
| `stand/Dockerfile.gui` | Docker-образ стенда с noVNC и GUI демоном |
| `stand/run-gui.sh` | Скрипт запуска внутри контейнера |

## Примечания

- Тесты требуют, чтобы демон был запущен **до** запуска тестов — проверьте через noVNC.
- Если стенд падает при сборке — убедитесь, что пакеты `go`, `libxkbcommon-dev` доступны в образе builder.
- Для отладки установите `DUMPLOG=1` перед запуском стенда.
