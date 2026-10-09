# План кроссплатформенной миграции xswitcher

## Context

xswitcher — Go-реализация аналога Punto Switcher, уже работающая на Linux (evdev + X11/XKB + uinput) и частично на macOS (есть синтез клавиш через CGEvent, но нет захвата ввода и переключения раскладки). Цель: сделать полноценный кроссплатформенный open-source проект с поддержкой Linux, macOS и Windows, а также закрыть пробелы в текущей реализации (Wayland, packaging, CI).

Язык остаётся Go. CGo допустим для Linux/macOS. Windows-бэкенд — чистый Go через `golang.org/x/sys/windows` (без CGo).

---

## Архитектурные решения

1. **Абстракция:** Go-интерфейсы в `internal/platform/`, реализации через build tags (`linux`, `darwin`, `windows`). Runtime-dispatch не применяется — API платформ фундаментально различны.
2. **Windows без CGo:** Все Win32 API (`SetWindowsHookEx`, `SendInput`, `GetForegroundWindow`, `ActivateKeyboardLayout`) доступны через `golang.org/x/sys/windows`. Это упрощает CI и устраняет зависимость от C-компилятора на Windows.
3. **Модель демона на Windows:** Tray-приложение по умолчанию (не требует админа для хуков), опциональный `--service` флаг. На Linux — systemd + root (evdev/uinput). На macOS — LaunchAgent + Accessibility permission.
4. **IPC:** Unix domain sockets на Linux/macOS, Named Pipes (`\\.\pipe\xswitcher`) на Windows. Протокол (line-delimited JSON) идентичен, меняется только транспорт.

---

## Фазы реализации

### Фаза 0: Извлечение интерфейсов (Фундамент)
**Риск:** НИЗКИЙ | **Цель:** Определить абстракции без изменения поведения.

Создать `internal/platform/platform.go` с интерфейсами:
- `InputBackend` — захват клавиатурных событий (`Start`, `Stop`, `DeviceNames`)
- `SynthesisBackend` — синтез нажатий (`Init`, `Press`, `Release`, `Sync`, `Close`)
- `LayoutBackend` — переключение раскладки (`CurrentGroup`, `SetGroup`, `ManagedGroups`)
- `WindowBackend` — определение активного окна (`ActiveWindowClass`, `ActiveWindowID`)
- `ProcessBackend` — выполнение команд
- `AudioBackend` — воспроизведение звуков
- `Logger` — логирование

Создать `internal/platform/keyevent.go` с типом `KeyEvent{Code, Value, Timestamp, Device}`.

Создать stub-файлы с build tags:
- `backend_linux.go` — обёртки вокруг существующего evdev/uinput/X11 кода
- `backend_darwin.go` — заглушки `ErrNotImplemented`
- `backend_windows.go` — заглушки `ErrNotImplemented`

**Критические файлы:**
- Новый: `internal/platform/platform.go`, `internal/platform/keyevent.go`
- Новый: `internal/platform/backend_{linux,darwin,windows}.go`

**Проверка:** `go build ./...` на Linux проходит без изменений в поведении.

---

### Фаза 1: Декомпозиция монолита
**Риск:** СРЕДНИЙ | **Цель:** Вынести платформо-специфичную логику из `src/xswitcher.go` (2078 строк) в бэкенды.

Каждый шаг — отдельный коммит с полным Linux-тестированием:

1. **Window Detection** → `internal/platform/window_x11.go` (строки 557-608 xswitcher.go)
2. **Layout Switching** → `internal/platform/layout_xkb.go` (строки 745-838)
3. **Key Synthesis** → обернуть `keybd_event` за `SynthesisBackend` (строки 841-860)
4. **Input Capture** → `internal/platform/input_evdev.go` (строки 1582-1650, 2037-2073)
5. **Process Execution** → разделить `exec/exec.go` на `process_posix.go` / `process_windows.go`
6. **Logging** → `logger_syslog.go` (POSIX) / `logger_eventlog.go` (Windows)
7. **Audio** → `audio_linux.go` / `audio_windows.go`

**Критические файлы:**
- `src/xswitcher.go` — основной объект рефакторинга
- `exec/exec.go` — POSIX-only процессный менеджмент
- `internal/sounds/player.go` — Linux-only аудио
- `src/keybd_event/` — уже имеет per-platform файлы, нужна обёртка

**Проверка:** После каждого шага `go test ./...` + ручное тестирование на Linux.

---

### Фаза 2: Windows-бэкенд
**Риск:** ВЫСОКИЙ | **Цель:** Реализовать все Windows-бэкенды.

1. **Input** (`input_windows.go`): `SetWindowsHookEx(WH_KEYBOARD_LL)` через `golang.org/x/sys/windows`. Callback переводит `KBDLLHOOKSTRUCT` → `KeyEvent`. Обработка в отдельной горутине (hook timeout >300ms = silent uninstall). Watchdog для переустановки хука.
2. **Synthesis** (`synthesis_windows.go`): Переписать `keybd_windows.go` с `keybd_event` на `SendInput`. Batch-отправка `INPUT[]`. Поддержка extended keys через `KEYEVENTF_EXTENDEDKEY`.
3. **Layout** (`layout_windows.go`): `GetKeyboardLayout(0)` → LANGID, `ActivateKeyboardLayout(hkl, KLF_SETFORPROCESS)`. Перечисление через `GetKeyboardLayoutList`.
4. **Window** (`window_windows.go`): `GetForegroundWindow()` + `GetClassNameW()`.
5. **IPC Transport** (`internal/ipc/transport_windows.go`): Named pipe `\\.\pipe\xswitcher` через `CreateNamedPipe`. Тот же протокол, другой транспорт. Альтернатива: TCP `127.0.0.1:PORT`.
6. **Process** (`process_windows.go`): Job Objects вместо `Setpgid`. `cmd.exe /c` вместо `/bin/bash -c`.
7. **Config Path**: `%APPDATA%\xswitcher\xswitcher.conf` через `os.UserConfigDir()`.

**Критические файлы:**
- `src/keybd_event/keybd_windows.go` — переписать на SendInput
- `internal/ipc/server.go` — добавить транспортную абстракцию
- Новые: `internal/platform/*_windows.go`

**Проверка:** `GOOS=windows go build`. Ручное тестирование на Windows: захват, переключение, retype, GUI через named pipes.

---

### Фаза 3: Дополнение macOS
**Риск:** СРЕДНИЙ | **Цель:** Реализовать отсутствующие macOS-бэкенды.

1. **Input** (`input_darwin.go`): CGEvent tap через `CGEventTapCreate(kCGSessionEventTap, kCGHeadInsertEventTap, ...)`. Фильтрация `kCGEventKeyDown/Up/FlagsChanged`. Проверка `AXIsProcessTrusted()` при старте.
2. **Layout** (`layout_darwin.go`): `TISCopyCurrentKeyboardInputSource()` + `TISSelectInputSource()`. Перечисление через `TISCreateInputSourceList`.
3. **Window** (`window_darwin.go`): `NSWorkspace.shared.frontmostApplication` или `CGWindowListCopyWindowInfo`. Bundle identifier как класс окна.

**Проверка:** Сборка на macOS. Тест accessibility permission flow. Переключение между input sources.

---

### Фаза 4: Улучшение Wayland
**Риск:** СРЕДНИЙ-ВЫСОКИЙ | **Цель:** Полноценная поддержка Wayland.

1. Детекция сессии через `XDG_SESSION_TYPE` / `WAYLAND_DISPLAY`.
2. wlroots-композиторы (Sway, Hyprland): `wlr-foreign-toplevel-management` протокол → `window_wayland_wlr.go`.
3. GNOME/KDE Wayland: D-Bus fallback (`org.gnome.Shell.Eval`, KWin scripting).
4. Переключение раскладки: `zwp_input_method_v2` или compositor-specific D-Bus. Fallback на текущий key-sequence метод.

**Проверка:** Тест на Sway, GNOME Wayland, KDE Plasma Wayland. Матрица поддержки по композиторам в docs.

---

### Фаза 5: Packaging и CI
**Риск:** НИЗКИЙ | **Цель:** Автоматизированные сборки и нативные инсталляторы.

**CI Matrix** (`.github/workflows/build.yml`):
- Linux: Ubuntu 22.04 + CGo → `.deb` (dpkg-deb) + `.rpm` (rpmbuild) + systemd unit
- macOS: macOS 14 + CGo → sign + notarize → `.dmg` + LaunchAgent plist
- Windows: Windows Server 2022, pure Go → `.exe` installer (Inno Setup)

---

## Стратегия тестирования

- **Unit:** `internal/platform/*_test.go` с mock/stub реализациями. Build-tagged, запускаются только на целевой ОС.
- **Integration:** `test/integration/` — e2e тесты: старт демона, IPC, синтетические события, проверка ответов. В CI на каждой платформе.
- **Cross-check:** `GOOS=<other> go vet ./...` для проверки совместимости интерфейсов без полной компиляции.

---

## Риски и митигация

| Риск | Серьёзность | Митигация |
|------|-------------|-----------|
| Поломка Linux при декомпозиции | ВЫСОКАЯ | Один подсистема = один PR. Старый код как fallback behind build tag до верификации. |
| Silent uninstall LL hook на Windows | ВЫСОКАЯ | Бенчмарк latency callback. Offload в buffered channel. Watchdog reinstall. |
| macOS Accessibility permission UX | СРЕДНЯЯ | Ранняя проверка, ясный диалог со ссылкой на System Preferences. Кэш trust state. |
| Фрагментация Wayland | СРЕДНЯЯ | Tiered: wlroots protocol → D-Bus → key-sequence bypass. Документация per-compositor. |
| CGo cross-compilation в CI | СРЕДНЯЯ | Windows = pure Go. Linux/macOS = native runners. Никакого cross-CGo. |

---

## Порядок выполнения

Фаза 0 → 1 → 2 → 3 → 4 → 5 (строго последовательно, каждая фаза зависит от предыдущей).

Внутри фазы 1: шаги 1.1–1.7 выполняются последовательно, каждый — отдельный коммит с полным Linux-тестированием.

macOS (фаза 3) после Windows (фаза 2), потому что Windows-бэкенд проще (pure Go, нет CGo) и даёт быстрее видимый результат. macOS требует CGo + accessibility permissions, что сложнее для отладки.