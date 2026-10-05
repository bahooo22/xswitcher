# xswitcher GUI Implementation Plan

## Context

xswitcher — консольный демон (Go+cgo), работающий от root с прямым доступом к evdev/X11. У него нет графического интерфейса. Пользователь хочет GUI для удобства настройки, просмотра статуса и About-информации. GUI будет разрабатываться в отдельной ветке `feature/gui` (уже создана от `5d7c504`).

Ключевое архитектурное ограничение: **демон и GUI — два отдельных бинарника**, общающихся через IPC. Демон работает от root, GUI — от обычного пользователя сессии. Смешивание в одном процессе невозможно из-за security boundary и зависимостей GUI-тулкита.

## Архитектурные решения (подтверждены)

| Решение | Выбор | Обоснование |
|---------|-------|-------------|
| GUI toolkit | **Fyne v2** | Self-contained rendering, нет внешних GTK/Qt deps, формовые виджеты для конфига, system tray, file dialogs |
| IPC | **Unix domain socket** | Синхронный request/response, обратная связь об ошибках reload, проще D-Bus |
| Сокет | `/run/xswitcher/xswitcher.sock` | Стандарт для системных демонов; права `0660`, группа `input` |
| Конфиг write | **go-toml Tree read-modify-write** | Сохраняет комментарии и порядок ключей; fallback — regex-replacement |
| About metadata | **ldflags injection** | Версия/коммит/maintainer подставляются при сборке, не хардкодятся |
| Reload strategy | **Respawn (fork+exec)** | Глобальные переменные демона не thread-safe; Respawn уже доказан безопасным |

## Структура пакетов

```
xswitcher/
├── cmd/
│   ├── daemon/main.go          # Тонкая обёртка, импортирует src/ + internal/ipc/server
│   └── gui/main.go             # Fyne app entry point
├── internal/
│   ├── config/
│   │   ├── types.go            # TScanDevices, TKeyboard, TAction, ... (извлечено из src/xswitcher.go)
│   │   ├── parse.go            # TOML → struct (извлечено из config())
│   │   └── write.go            # Tree-based TOML writer с сохранением комментариев
│   ├── ipc/
│   │   ├── protocol.go         # Request/Response JSON structs
│   │   ├── server.go           # Unix socket listener (для daemon)
│   │   └── client.go           # Dial + request helper (для GUI)
│   └── about/
│       └── info.go             # Version, Commit, Maintainer, URLs (ldflags)
├── src/                        # Существующий daemon core (минимальные правки)
│   └── xswitcher.go            # Убрать type defs + config() body → import internal/config
└── go.mod                      # Добавить fyne.io/fyne/v2
```

## IPC Protocol (line-delimited JSON)

```
GUI → daemon:  {"cmd":"ping"}
daemon → GUI:  {"ok":true}

GUI → daemon:  {"cmd":"status"}
daemon → GUI:  {"ok":true,"pid":12345,"uptime":"3h12m","config":"/etc/xswitcher/xswitcher.conf","devices":["event3","event7"]}

GUI → daemon:  {"cmd":"reload"}
daemon → GUI:  {"ok":true,"pid":12346}  OR  {"ok":false,"error":"parse error at line 42"}
```

Socket permissions: создаётся от root с mode `0660`, group `input`. GUI подключается как пользователь из группы `input`.

## MVP Milestone (Phase 1)

### Файлы для создания (11 новых файлов)

| # | Файл | Назначение |
|---|------|-----------|
| 1 | `internal/config/types.go` | Извлечь конфиг-структуры из `src/xswitcher.go:87-168` |
| 2 | `internal/config/parse.go` | Извлечь pure-parse логику из `config()` lines 333-584 |
| 3 | `internal/config/write.go` | Tree-based TOML writer с comment preservation |
| 4 | `internal/ipc/protocol.go` | Request/Response JSON structs |
| 5 | `internal/ipc/server.go` | Unix socket listener goroutine для daemon |
| 6 | `internal/ipc/client.go` | Dial + request helper для GUI |
| 7 | `internal/about/info.go` | Ldflags-injected metadata vars |
| 8 | `cmd/daemon/main.go` | Thin daemon entry, старт IPC server после config() |
| 9 | `cmd/gui/main.go` | Fyne app: главное окно + меню + About dialog |
| 10 | `cmd/gui/editor.go` | Form widgets, bound to config structs |
| 11 | `cmd/gui/about.go` | About dialog widget (maintainer, version, links) |

### Модификации существующих файлов

| Файл | Изменение |
|------|-----------|
| `src/xswitcher.go` | Удалить type definitions (→ `internal/config/types.go`); удалить тело `config()` (→ `internal/config/parse.go`); добавить import `internal/config`; добавить goroutine `ipc.StartServer(sockPath)` после строки 2101 |
| `go.mod` | Добавить `fyne.io/fyne/v2` |

### Порядок реализации

1. **Extract config types** (`internal/config/types.go`) — механическое перенесение struct definitions
2. **Extract parse logic** (`internal/config/parse.go`) — вынести switch/case из `config()`, сохранить сигнатуру
3. **Refactor src/xswitcher.go** — заменить inline types + config() на imports; убедиться что `go build ./src/` проходит
4. **IPC protocol** (`internal/ipc/protocol.go`) — определить Request/Response structs
5. **IPC server** (`internal/ipc/server.go`) — listener goroutine, dispatch по cmd
6. **IPC client** (`internal/ipc/client.go`) — dial + send/receive helper
7. **Daemon entry** (`cmd/daemon/main.go`) — thin wrapper, start IPC after config
8. **Config writer** (`internal/config/write.go`) — Tree-based read-modify-write
9. **About module** (`internal/about/info.go`) — ldflags vars
10. **GUI main** (`cmd/gui/main.go`) — Fyne app skeleton, connect to socket
11. **Config editor** (`cmd/gui/editor.go`) — form widgets for each config section
12. **About dialog** (`cmd/gui/about.go`) — maintainer info, GitHub links
13. **Integration test** — verify reload round-trip through socket

Пункт 7 («Daemon entry» как thin wrapper) не состоялся: демон сохранил собственный
`main()` в `src/xswitcher.go`, а IPC слушатель запускается из `listenIPC()` внутри
него. Заглушка `cmd/daemon/main.go` удалена, её три локализованных строки были
единственными носителями ключей `daemon.ipc_start_failed`, `daemon.ipc_listening`
и `daemon.ipc_shutting_down`; реальный демон использует `_syslog`-варианты из
`src/handover.go`.

## Config Sections для Editor UI

| Section | Widget Type | Notes |
|---------|------------|-------|
| `[ScanDevices]` | Form: TextEntry × 3, NumberEntry × 1 | Test, Search, Bypass, Respawn |
| `[Keyboard]` | Form: NumberEntry, Checkbox | Delay, WipeBySelection |
| `[Templates]` | Key-Value list editor | Map[string]string |
| `[ActionKeys]` | Multi-line TextEntry × 4 | Layouts, Add, Drop, StateKeys, Test |
| `[[WindowClasses]]` | List + detail form | Regex, MouseClickDrops, Actions |
| `[Actions]` | Form: NumberEntry, TextEntry × 6 | SeqLength, WordChars, WordHead, NewWord[], etc. |
| `[Action.*]` | Dynamic tabs per action | Action chain, Exec, Timeout, SendBuffer, etc. |
| `[Wayland]` | Form: Checkbox, NumberEntry, TextEntry × 4 | BypassX, Delay, Layout0-3 |

MVP: реализовать `[ScanDevices]`, `[Keyboard]`, `[Wayland]` как structured forms; `[Action.*]` и `[[WindowClasses]]` — как raw TOML text area с syntax highlighting. Structured editors для сложных секций — Phase 2.

## About Dialog Content

```
xswitcher GUI
Version: {ldflags}
Commit: {ldflags}
Maintainer: BaHooo (bahooo22)
Fork: https://github.com/bahooo22/xswitcher
Upstream: https://github.com/ds-voix/xswitcher
License: AGPL-3.0
```

Build command:
```bash
go build -ldflags "-X xswitcher/internal/about.Version=$(git describe --tags) \
  -X xswitcher/internal/about.Commit=$(git rev-parse --short HEAD)" \
  -o bin/xswitcher-gui ./cmd/gui/
```

## Verification Strategy

### Headless (без дисплея)
1. **IPC unit tests** (`internal/ipc/*_test.go`): temp socket, ping/status/reload, assert JSON responses
2. **Config round-trip tests** (`internal/config/write_test.go`): parse real `xswitcher.conf` → modify → marshal → re-parse → assert modification + comments preserved
3. **Integration script** (`stand/gui-smoke.sh`): build both binaries, start daemon, send reload via client, verify status response shows new PID

### Manual (с дисплеем)
1. Edit value in GUI → Apply → daemon log shows re-parse
2. Introduce syntax error → Apply → error displayed inline, config file unchanged
3. Kill daemon → GUI shows connection error gracefully
4. Start daemon → GUI auto-connects
5. About dialog shows correct version/commit/maintainer

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `go-toml` v1.9.5 Tree.Marshal loses comments | Test early against real `xswitcher.conf`; fallback to regex replacement or upgrade to go-toml/v2 |
| Socket permissions: GUI user can't connect | Create with group `input`, mode `0660`; document `usermod -aG input $USER` |
| Daemon globals not thread-safe for hot-reload | MVP uses full Respawn (fork+exec); hot-reload deferred |
| Fyne binary size (~15-20MB) | Acceptable; document in README; consider `upx` for releases |
| Config schema drift daemon↔GUI | Both import `internal/config/types.go`; CI check parses embeddedConfig.Toml with current types |
| Wayland array fields hard to edit in form | MVP: raw TOML text area; structured editor in Phase 2 |

## Post-MVP (Phase 2+)

- Structured editors for `[Action.*]` and `[[WindowClasses]]`
- Live status panel (connected devices, current layout, word buffer)
- System tray integration (minimize to tray, quick layout switch)
- Config validation preview (dry-run parse before save)
- Hot-reload without full respawn (mutex-protected state swap)
- D-Bus interface for desktop integration
- i18n (RU/EN)

## Branch & PR Strategy

- Ветка: `feature/gui` (уже создана от `5d7c504`)
- Base для PR: `fix/code-audit-and-issues` (или `main` после merge аудита)
- Коммиты: атомарные по фазам (extract config → IPC → GUI skeleton → editor → about)
- CI: headless IPC + config round-trip tests обязательны для merge