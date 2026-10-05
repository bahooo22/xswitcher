# Стенд GUI xswitcher (noVNC + физический ввод)

Этот стенд позволяет тестировать переключение раскладки через **физическое нажатие клавиш** (через `xdotool`) в графическом интерфейсе xswitcher, запущенном внутри Docker-контейнера и доступном через noVNC.

## Что делает стенд

| Компонент | Роль |
|-----------|------|
| **Xvfb :99** | Виртуальный X-сервер внутри контейнера |
| **xswitcher-gui** | Демон с графическим интерфейсом (Fyne) |
| **noVNC** | Веб-доступ к GUI через WebSocket |
| **pytest + xdotool** | Автотесты физического ввода клавиш |

## Требования на хосте (Windows 11)

```bash
# 1. Установите Docker Desktop (если ещё нет) и запустите его
# 2. Загрузите модули ядра для виртуализации ввода:
bash stand/setup-host.sh
```

## Запуск стенда

```bash
cd E:\eXample\Documents\Source\Github\Fork\xswitcher\stand

# Генерируем runtime-конфигурацию (опционально, можно пропустить):
bash runtime.sh

# Поднимаем стенд:
docker compose -f docker-compose.gui.yml up --build --detach
```

После запуска откройте в браузере:

> http://host.docker.internal:6081/noVNC/

## Проверка через noVNC

1. Откройте `http://host.docker.internal:6081/noVNC/` в браузере.
2. В окне GUI xswitcher перейдите на вкладку **About**.
3. В поле ввода наберите тестовый текст, например «hello».
4. Нажмите горячую клавишу переключения раскладки (по умолчанию — `Win+Space`).
5. Текст должен измениться с «hello» на «gheoll» (или аналогичный набор символов в зависимости от текущей раскладки).

## Запуск автотестов

```bash
pip install pytest xdotool

pytest test_xswitcher_with_physical_input.py -v
```

Тесты проверяют:

- ✓ Переключение раскладки RU → EN (текст «привет» → «ghbdtn»)
- ✓ Обратное переключение EN → RU («ghbdtn» → «привет»)
- ✓ Курсор не смещается после нажатия горячей клавиши
- ✓ Активное окно остаётся прежним

## Отладка через noVNC

Если автотесты упали, откройте noVNC и вручную проверьте:

```bash
# Измерьте координаты поля ввода (измените в тесте, если нужно):
xdotool getmouselocation --shell
```

## Архитектура стенда

```
┌───────────────────────────────────────────┐
│  Windows 11 (24H2) — хост                 │
│  ├─ Docker Desktop                        │
│  └─ Модули: uinput, evdev                │
└───────────────────────────────────────────┘
                  ↓ WebSocket
┌───────────────────────────────────────────┐
│  xswitcher-stand (Docker контейнер)        │
│  ├─ Alpine Linux + Python3               │
│  ├─ Xvfb :99                             │
│  ├─ /w/bin/xswitcher-gui                │
│  ├─ noVNC (порт 6081 ←→ 5900)          │
│  └─ Гостевая папка (только чтение)      │
└───────────────────────────────────────────┘
```

## Файлы стенда

| Файл | Описание |
|------|----------|
| `stand/run-gui.sh` | Скрипт запуска стенда внутри контейнера |
| `stand/Dockerfile.gui` | Docker-образ с noVNC и GUI демоном |
| `stand/docker-compose.gui.yml` | Конфигурация compose (noVNC + xswitcher) |
| `stand/runtime.sh` | Генерация runtime.yml из переменных окружения |
| `stand/runtime-gui.yml` | Конфигурационный файл стенда |
| `test_xswitcher_with_physical_input.py` | Автотесты физического ввода |

## Удаление стенда

```bash
cd stand && docker compose -f docker-compose.gui.yml down --remove-orphans
```
