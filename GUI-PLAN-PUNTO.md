# xswitcher GUI: Punto Switcher Parity Plan

## Context

Пользователь предоставил 16 скриншотов Punto Switcher (Windows layout switcher) и просит спланировать реализацию аналогичного функционала в xswitcher. Текущий GUI MVP (`cmd/gui/`) имеет только базовые формы Config/About с **непривязанными** виджетами — нет read/write round-trip, нет system tray, нет расширенных функций. Daemon поддерживает SEQ/ON/OFF правила, WindowClasses, TypeClipboard, но не имеет автоопределения языка, автозамены, звуков, дневника.

Цель: поэтапная реализация паритета с Punto Switcher через 5 фаз, начиная с привязки существующих форм и заканчивая новыми daemon-фичами.

## Phase 0: Fix Editor Binding (GUI-only, prerequisite)

**Проблема:** Формы editor.go созданы, но никогда не загружают конфиг и не пишут обратно. Apply вызывает только `client.Reload()`.

### Files to modify

- `internal/ipc/protocol.go` — добавить `get_config`, `set_config`, `validate` команды
- `internal/ipc/server.go` — обработчики новых команд (read file → return TOML; write + validate → reload)
- `internal/ipc/client.go` — методы `GetConfig()`, `SetConfig(mods)`, `Validate()`
- `cmd/gui/editor.go` — при открытии таба вызывать `GetConfig()`, заполнять виджеты; Apply → `WriteTOML()` локально + `SetConfig()` + `Validate()` + `Reload()`

### Verification

- Запустить daemon + GUI, изменить значение в форме → Apply → проверить, что конфиг на диске обновился и daemon перезагрузился
- Внести синтаксическую ошибку → Apply → ошибка показана inline, файл не изменён

## Phase 1: System Tray + Live Status (GUI-only)

### New files

- `cmd/gui/tray.go` — systray icon, context menu (Show/Hide, Reload, Exit)
- `cmd/gui/status.go` — live status panel: connected devices, current layout, active window class, word buffer

### Modified files

- `cmd/gui/main.go` — init systray, add Status tab, auto-connect on start
- `internal/ipc/protocol.go` — расширить Status response: Layout int, WordBuffer string, ActiveWindow string

### Verification

- Свернуть окно → tray icon visible → click → window restored
- Status panel показывает актуальные данные при переключении раскладки

## Phase 2: Structured Editors for Complex Sections (GUI-only)

### New files

- `cmd/gui/actions_editor.go` — list+detail editor for `[Action.*]` sections
- `cmd/gui/windowclasses_editor.go` — table editor for `[[WindowClasses]]`
- `cmd/gui/templates_editor.go` — key-value editor for `[Templates]`
- `cmd/gui/actionkeys_editor.go` — multi-select lists for Add/Drop/Test/StateKeys

### Modified files

- `cmd/gui/editor.go` — заменить raw TOML area на structured editors
- `internal/config/write.go` — поддержка записи массивов таблиц (`[[WindowClasses]]`)

### Verification

- Добавить новый Action через GUI → сохранить → проверить TOML структуру
- Изменить WindowClass regex → применить → daemon маршрутизирует правильно

## Phase 3: New Daemon Features — Auto-Replace + Hotkeys (daemon + GUI)

### New config structs (`internal/config/types.go`)

```go
type TAutoReplace struct {
    Trigger  string // abbreviation trigger, e.g. "btw"
    Replace  string // replacement text
    Exact    bool   // match whole word only
}

type THotkey struct {
    Keys   []string // e.g. ["CTRL", "SHIFT", "F1"]
    Action string   // action name or built-in ("switch_layout", "retype")
}
```

### New config sections

- `[AutoReplace]` — array of TAutoReplace entries
- `[Hotkeys]` — array of THotkey entries

### Daemon changes (`src/xswitcher.go`)

- Parse new sections in `config()` via `internal/config/parse.go`
- Auto-replace: after WORD buffer update, check against replace map; if match → wipe + type replacement
- Hotkeys: global key state tracker independent of ActionKeys SEQ matching

### GUI changes

- `cmd/gui/autoreplace_editor.go` — table with add/remove/edit
- `cmd/gui/hotkeys_editor.go` — key recorder widget + action selector

### IPC changes

- `reload` must re-parse new sections
- `status` returns active hotkey count

### Risks

- Auto-replace conflicts with existing SEQ rules → priority: exact match > SEQ > partial
- Hotkey detection from evdev requires tracking modifier state globally → reuse CTRL map

## Phase 4: Sound Events + Diary (daemon + GUI)

### Sound system

- **Architecture:** Daemon sends sound event notifications via IPC → GUI plays sounds (avoids PulseAudio/PipeWire from root)
- New IPC command: `sound_event` (daemon → GUI push notification)
- Config: `[Sounds]` section mapping event names to file paths
- Events: `layout_switch`, `retype`, `auto_replace`, `error`

### Diary system

- Config: `[Diary]` section: Enabled bool, Path string, MaxSizeMB int, RotateCount int
- Daemon writes typed text (not raw keys) to diary file after each WORD completion
- Privacy: diary disabled by default; explicit opt-in required
- GUI: diary viewer tab with search, date filter, export

### New files

- `cmd/gui/sounds_editor.go` — event-to-file mapping editor + test play button
- `cmd/gui/diary_viewer.go` — text viewer with filters
- `internal/diary/writer.go` — log rotation, size limits
- `internal/sounds/player.go` — GUI-side sound playback (platform-native)

### Risks

- Diary is a keylogger feature → MUST be opt-in, documented, with clear privacy warning
- Sound from GUI process may have latency → acceptable for non-critical feedback
- Log rotation must not lose data during daemon respawn

## Phase 5: Auto-Language Detection (daemon + GUI, most complex)

### Architecture

xswitcher currently uses reactive SEQ matching. Auto-detection requires predictive analysis:

- After N characters of WORD buffer, run language heuristic (character frequency / n-gram model)
- If detected language ≠ current layout AND confidence > threshold → auto-switch + retype
- New config: `[AutoDetect]` section: Enabled, MinChars int, Confidence float, Languages []string

### Implementation approach

- Lightweight n-gram tables embedded at build time (no external deps)
- Per-language character frequency tables for RU/EN/DE/etc.
- Integration point: after `checkAppend()` in serve loop, before SEQ matching
- Fallback: if auto-detect wrong, user's manual switch overrides and trains the model

### GUI

- `cmd/gui/autodetect_editor.go` — enable/disable, threshold slider, language selection, training data import
- Live preview: show detected language for current WORD buffer

### Risks

- False positives will frustrate users → high confidence threshold by default, easy disable
- Performance: n-gram check on every keystroke must be <1ms → precomputed tables, no allocations
- Training data privacy → all processing local, no network

## Branch Strategy

- Continue on `feature/gui` for Phases 0-2 (GUI-only work)
- Create `feature/punto-daemon` from `feature/gui` tip for Phases 3-5 (daemon changes)
- Each phase = separate PR stacked on previous

## Critical Files Reference

- `cmd/gui/editor.go` — unbound forms (Phase 0)
- `internal/ipc/protocol.go` — IPC commands
- `internal/config/types.go` — config structs
- `internal/config/write.go` — TOML writer
- `src/xswitcher.go` — daemon core
- `GUI-PLAN.md` — existing MVP plan

## Verification Strategy (per phase)

| Phase | Headless Test | Manual Test |
|-------|--------------|-------------|
| 0 | IPC get/set/validate unit tests | Edit form → Apply → verify file + daemon reload |
| 1 | Systray init test | Tray icon menu works, status updates live |
| 2 | Config round-trip with complex sections | Add Action/WindowClass via GUI → verify TOML |
| 3 | Auto-replace unit tests, hotkey state tests | Type abbreviation → replaced; press hotkey → action fires |
| 4 | Diary rotation tests, sound playback mock | Enable diary → type → view log; trigger sound → hear it |
| 5 | N-gram accuracy benchmarks | Type mixed-language text → auto-switch triggers correctly |