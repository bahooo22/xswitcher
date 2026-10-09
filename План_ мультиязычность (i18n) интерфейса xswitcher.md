# План: мультиязычность (i18n) интерфейса xswitcher

## Context (зачем)
GUI (`cmd/gui`) и сообщения демона сейчас целиком на английском и **захардкожены в местах создания виджетов** (~125 пользовательских строк, ни одной централизованной таблицы). Механизма локализации нет вообще, настройки UI-языка тоже нет (коды `en`/`ru` в конфиге — это языки **раскладки ввода** `[AutoDetect]`, не локаль). Цель — добавить полноценную мультиязычность: переключатель языка прямо в GUI без перезапуска, покрытие всего текста (`cmd/gui` + `cmd/daemon`/`src`), и расширяемость до произвольного числа языков «добавил файл — появился язык».

Фork готовится к PR в upstream, поэтому churn зависимостей и размер diff критичны, а правки истории/дерева делит владелец дерева.

### Принятые решения (зафиксированы владельцем)
1. **Механизм:** обновить Fyne до последней версии и использовать официальный пакет `fyne.io/fyne/v2/lang` (его нет в текущем 2.4.5 — появился в 2.5.0).
2. **Выбор языка:** переключатель в самом GUI, смена на лету (UI перестраивается, т.к. строки пекутся при construction).
3. **Хранение:** новый сегмент `[GUI] Language` в `xswitcher.conf`.
4. **Охват:** GUI полностью + сообщения демона, но **машинно-читаемые маркеры логов остаются английскими**; вывод стенда пиновится на en.
5. **Языки:** стартовый набор en (база) + ru, архитектура открыта N-язычности (каталоги JSON, не код).

## Ground-truth (проверено в контейнере xswitcher-live, не предполагено)
- Go в контейнере 1.24.4; сеть к `proxy.golang.org` есть; GL/X dev-пакеты установлены; go-gl вендерит glfw C-исходники (pkg-config glfw3 не нужен). `.gomodcache` bind-смонтирован и прогрет v2.5.2/2.6.3/2.7.4/2.8.1 + go-locale + go-i18n v2.5.1.
- `lang` API: `Localize/LocalizeKey/LocalizePlural/LocalizePluralKey` (+алиасы `L/N/X/XN`), `AddTranslations/AddTranslationsForLocale/AddTranslationsFS`; `locale.go` экспортирует **только `SystemLocale`** — публичного `SetLocale` нет ни в 2.5.2, ни в 2.8.1.
- **Обход ограничения переключателя:** внутренний локализатор Fyne при каждом вызове перечитывает env `LC_ALL→LC_MESSAGES→LANG→LANGUAGE` (go-locale `locale_unix.go`, без кэша) → можно перестроить локализатор Fyne на выбранный язык, временно выставив env и перерегистрировав каталог. Строки нашего приложения ведёт свой резолвер.
- Русские встроенные каталоги Fyne есть начиная с **v2.6.3**; в **v2.5.2 их нет**. В v2.8.1 — 15 языков.
- Формат go-i18n v2.5.1: ключ по имени файла (`ru.json`/`base.ru.json`), fallback-цепочка active→bundle-default(`en`)→`DefaultMessage` в коде, плюралы через `x/text/plural` (ru one/few/many бесплатно).
- **Все** используемые GUI символы Fyne (`widget.NewFormItem/NewCard/NewMultiLineEntry/NewSelect/NewLabelWithStyle/NewHyperlink`, `container.*`, `dialog.ShowFileSave`, `TextWrapWord/Off`, `test.NewApp/Tap`) присутствуют в целевых версиях — проверено grep'ом.
- Парсер конфига **отвергает неизвестные секции** (`internal/config/parse.go` unknown section) → добавление `[GUI]` требует правок в `types.go`/`parse.go`/`write.go`/`embeddedConfig`/`xswitcher.conf` и тесты.
- Ассерт-строки в en, которые сломает локализация: `cmd/gui/autodetect_editor_test.go` (~15 подстрок), `internal/config/parse_test.go` (~20 `wanted`), `write_test.go:30,239`, `src/actioncycles_test.go:36`; скрипты `stand/run.sh` (`grep "Config error"`, `RetypeWord error`…) и `stand/smoke.sh:387` (`kept as is`).

## Риски (ключевые)
| Риск | Тяжесть | Митигация |
|---|---|---|
| Перевод протечёт в записываемый TOML → сломанная раскладка/клавиатура | **Критический** | Разделение display/ключ (Фаза 2), golden-тест набора ключей (Фаза 6), проверка байт-идентичности конфига (Фаза 7) |
| Бамп Fyne до последней (glfw v3.4, go-dir 1.22.0, systray v1.12.3, новые deps: bild/oksvg/fsnotify/…) ломает сборку/трей/X | Высокий | Фаза 0: spike с rollback-тегом, замеры сборки+stand на чистой версии; отдельный PR bump |
| 61-check stand и smoke.sh краснеют на переведённых строках демона | Высокий | Машинные маркеры навсегда en; в `run.sh`/`smoke.sh` `export LC_ALL=C XSWITCHER_LANG=en` |
| Перестройка UI рвёт IPC-соединение/выбранный таб/несохранённые правки | Высокий | `client`+goroutine живут вне дерева виджетов; replay состояния; confirm-диалог при несохранённых правках |
| Трей-меню не идемпотентно при повторном `SetSystemTrayMenu` | Средний | Замерить на Linux-драйвере; иначе менять текст `fyne.MenuItem`, не пересоздавать меню |

---

## Фазы (каждая независимо собирается и зелёная в контейнере)

### Фаза 0 — Предусловия и spike по Fyne (behavior-pure)
1. Rollback-тег: `git tag backup/pre-i18n-fyne-<date>`.
2. Определить **фактически последнюю** версию (`go list -m -versions fyne.io/fyne/v2`), зафиксировать точный пин (на обзоре — v2.8.1). Проверить: встроенный `ru`-каталог Fyne присутствует; glfw v3.4 собирается в контейнере; `pkg-config`/X/GL без регрессий.
3. `go get fyne.io/fyne/v2@<pin> && go mod tidy` в контейнере → **записать размер diff `go.mod`/`go.sum`** (это цифра для владельца до приёма churn).
4. Сборка по слоям (fail-fast): `go build ./internal/... ./cmd/daemon` → `go build ./src` (без Fyne) → `go build ./cmd/gui` (cgo/GL) → `go vet ./...` → `go test ./...`.
5. Прогнать GUI под Xvfb (`DISPLAY=:99`, паттерн `stand/smoke.sh:179-209`) + скриншот; проверить, что `tray.go` НЕ показывает fallback «System tray is not available» (type-assertion деградирует молча).
6. Полный стенд: `bash stand/live.sh run` (61) и `smoke.sh`.
   **Если последняя версия ломает трей/GL** — шаг назад на v2.6.3 (min с ru) как запасной пин; задокументировать решение.
- Коммиты: `0.1` только bump (go.mod/go.sum) — **отдельный upstream PR**; `0.2` механические фиксы.
- Exit: build+vet+test+stand зелёные на новой Fyne, поведение GUI не изменилось.

### Фаза 1 — Каталог + резолвер уровня приложения
Новый пакет **без импорта Fyne** (чтобы демон `src`/`internal` не тянул `fyne.io` в корневой бинарник):
- `internal/l10n/l10n.go`:
  - `Init() error` — go:embed `locales/*.json`, парсинг в `*i18n.Bundle` (default `en`), мьютекс.
  - `Available() []Descriptor` (`Code, Name, English`); `Name` из `language.name` каталога (не из Go-мапы — иначе «добавил файл» перестаёт работать).
  - `Current() string`, `Set(code string) error` ("" = по ОС), `Default() string` (`XSWITCHER_LANG` > `[GUI] Language` из конфига > локаль ОС > en).
  - `X(key, fallback string, data ...any) string`, `XN(key, fallback, count, data...) string` — сигнатуры как `lang.X/XN`.
  - `Errf(key, formatFallback string, data ...any) error`, `MustInitFromEnv()` — для демона.
  - `SetForTest(code) func()` — возврат-замыкание, тесты не текут.
- `internal/l10n/locales/{en,ru}.json` — go-i18n JSON (flat + вложенные плюралы). `en.json` достаточно `{language.name}` (fallback на литерал в коде).
- `cmd/gui/fyne_locale.go`:
  - `registerFyneCatalogs() error` — `lang.AddTranslationsFS(localesFS,"locales")` один раз (встроенные строки Fyne).
  - `applyFyneLocale(code) error` — env-lever (V3): временно выставить `LC_ALL/LANGUAGE` → `lang.AddTranslationsForLocale(probe, loc)` → **восстановить env** (иначе `LC_ALL` протечёт в `paplay`/`aplay` из `internal/sounds/player.go`).
- Проверка (линьчин, именно измерить): мини-программой напечатать `lang.X("cancel","Cancel")` до/после `applyFyneLocale("ru")`; зафиксировать `Cancel→Отмена` или задокументировать деградацию.
- Тесты: `Available()` видит оба; `X(unknown)`→английский литерал; ru-плюралы 1/2/5/11/21; drop-in (`testdata/de.json` → переключается без правки кода).
- Коммиты: `1.1` пакет+каталоги · `1.2` `fyne_locale.go`+замер.

### Фаза 2 — Разделить идентичность и display/ключ (behavior-pure, без переводов)
- `cmd/gui/main.go:50-63`: убрать `switch item.Text`; ввести `tabKey`+`tabsRegistry` (`map[*container.TabItem]tabKey`, `keyOf(item)`); `OnSelected` — по `keyOf`. (У `TabItem` нет user-data поля → identity по указателю.)
- `editor.go:137-149`: аналогично 11 под-табов (`subTabKey` константы = имена TOML-секций), чтобы перестройка восстанавливала выбранный под-таб.
- Разделение display vs config-ключ (переводим вывод, литерал ключа в конфиг пишем как раньше):
  - `windowclasses_editor.go:17-19,59,107` — `wcNoneLabel/wcMainLabel` оставить как **значения**, добавить `wcNoneDisplay()/wcMainDisplay()`; `wcLabelFor/wcValueFor` сравнивать по значению, не по локализованной строке.
  - `actionkeys_editor.go:20` — `akListKeys` (ключи) + `akListLabel(key)` (вывод).
  - `sounds_editor.go:62-78` — ключи `cfg.SoundEvents` не трогать, subtitle через `soundEventLabel(ev)`; placeholder-путь оставить литералом.
  - `hotkeys_editor.go:39-41,82-86` — `e.actionNames`/`cfg.HotkeyModifiers` — spelling демона, не переводить; переводить только подписи `Keys/Action` и прозу (плейсхолдер через шаблон с `{{.Modifiers}}`).
  - Кард-тайтлы = имена секций (`editor.go:101-103,137-148`, `actions_editor.go:114` «Action.»+name, `diary_editor.go:75`, `autodetect_editor.go:82`) → `configSection(name)` (ключ) + `sectionTitle(name)` (вывод). `renderRawSections` (`editor.go:368-387`) — **вывод файла, не трогать**.
  - Form-лейблы=ключи TOML (`MinChars/Confidence/Languages/Path/MaxSizeMB/RotateCount/Exec/Timeout/SendBuffer/Directory/Environment/UID/GID/Test/Search/Bypass/Respawn/Delay/Layouts`) → один хелпер `configKeyLabel(key)`.
- Guard-тест `cmd/gui/identity_test.go`: после `modsFromWidgets()` на перестроенной панели набор ключей байт-идентичен golden-списку.
- Коммит `2.1`. Exit: `go test ./...` + `smoke.sh` показывают байт-идентичные `[Section] key = value`.

### Фаза 3 — Механическая выноска строк GUI в каталог
~125 display-строк по файлам. Соглашения: `l10n.X(key,"English literal", data...)` (никогда `L()`/gettext — иначе правка английского тихо ломает все переводы); ключи с неймспейсом файла (`gui.tab.config`, `editor.btn.load`, `status.field.uptime`, `daemon.err.config`); числа (`%.3f`) форматировать в Go, переводчик спецификаторов не видит; плюралы через `XN`.
- Реструктурировать генерируемую прозу `autodetect_editor.go:193-257`: `classifyPreview(in) previewVerdict` (чистое решение, зеркалит порядок гейтов `src/autodetect.go`) + `renderPreview(in,v)` (8 шаблонных строк через `l10n.X`) + `previewReport` = тонкая обёртка. Тесты Фазы 6 проверяют `Kind`, а не английский текст. (Это же готовит базу под будущую adversarial-сверку preview vs daemon.)
- Охват: кард-тайтлы/подзаголовки, `NewFormItem`-подписи, лейблы/кнопки/чекбоксы/гиперссылки, `SetPlaceHolder`-прозу (кроме путей/regex), сообщения статуса/ошибок, `about.go:19-25` (метки «Version:/Commit:/» да, значения из `internal/about` — нет), `wcNoneDisplay`, `%d entries` → `XN`.
- Вне охвата (машинный текст): `renderRawSections`, имена секций/ключей TOML, spelling `SoundEvents/HotkeyModifiers/AutoDetectLanguages`, формат `[AutoDetect] Languages`, date-layout `"2006-01-02"`, IPC `Cmd/Event`.
- Коммиты: по одному на файл (`3.1..3.14`), затем `3.15` restructure previewReport. Каждый behavior-pure: при локали `en` и `en.json`==литералы вывод байт-идентичен (enforce golden-тест l10n + leak-scan Фазы 7).

### Фаза 4 — Переключатель, `[GUI]`-секция, перестройка UI
- `[GUI] Language` в конфиге (**решение владельца вместо prefs-файла**):
  - `internal/config/types.go`: `TGUI struct { Language string }` (`""`=auto; известные значения — по каталогам l10n).
  - `internal/config/parse.go`: разрешить секцию `[GUI]` в gate unknown-section; валидация значения (пусто/«auto»/либо код из доступных — но реестр языков в l10n, поэтому宽松: принимать любой непустой код, нераскрытый fallback на en).
  - `internal/config/write.go` + `embeddedConfig/config.go` + `xswitcher.conf` (закомментированный дефолт) + `parse_test.go`/`write_test.go`.
  - Сохранение выбора: переключатель пишет `[GUI] Language` через существующий путь `set_config`→`WriteTOMLChecked` (не отдельный файл-прайорити). GUI читает `Language` из загруженного по IPC конфига.
- `cmd/gui/prefs.go` — только чтение/резолв порядка (`XSWITCHER_LANG` > `[GUI].Language` > локаль ОС > en); сам персист — через конфиг.
- `cmd/gui/appshell.go` (перенос wiring из `main.go`, который сжимается до `app.New()+shell.run()`):
  - `type guiShell struct { app,win,client *ipc.Client,router,tabs,subTabs,statusBar,localeSelect *widget.Select,registry,state shellState,building bool }`
  - `buildConfigTab/buildStatusTab/buildAboutTab` идемпотентны, читают `l10n.Current()`.
  - `setLocale(code)`: `l10n.Set` → `applyFyneLocale` → записать `[GUI] Language` (Apply-путь) → `rebuild()`.
  - `rebuild()`: полный teardown+пересборка табов/контента/трея с восстановлением выбранного таба/под-таба из `state`.
- **Сохранение IPC при перестройке (жёсткое требование):** `client`+subscribe-goroutine (`main.go:40-48`) живут на `guiShell`, перестройка их не пересоздаёт и не ре-сабскрибит; после rebuild — replay `state` (последний `GetConfig`-`map` и `ipc.Response`), а не повторный запрос (дисконнектнутый демон не обнуляет UI). `building=true` на время конструкии, чтобы `OnSelected` не сработал в разгар сборки.
- **Несохранённые правки:** перед rebuild сравнить `modsFromWidgets()` со снапшотом; при расхождении — локализованный `dialog.ShowConfirm` («Смена языка перестраивает интерфейс; неприменённые правки пропадут. Продолжить?»).
- Трей: замерить идемпотентность `SetSystemTrayMenu/Icon` на appindicator; иначе менять тексты `fyne.MenuItem`.
- Виджет: `widget.NewSelect(codes,onChange)` в топбаре (`main.go:82`), native-name + (English) из каталогов.
- Коммиты: `4.1` appshell+`buildXxx` (без переключателя, behavior-pure, самый большой diff) · `4.2` `[GUI]`-секция в config · `4.3` переключатель+rebuild+confirm · `4.4` трей.

### Фаза 5 — Сообщения демона (`src`, `internal`)
- Охват: `internal/config/parse.go` все `fmt.Errorf` (главная user-visible победа — всплывают в GUI как `Set failed:`), `src/xswitcher.go` (~49 мест: ошибки конфига/парсинга/regex/IPC reload, паники device/keyboard/inotify), `src/notify.go`, `cmd/daemon/main.go`, `internal/ipc/server.go`, `internal/diary/writer.go`.
- Локаль демона: `XSWITCHER_LANG` > `[GUI] Language` из прочитанного конфига > env локали > en; опционально флаг `-lang` (уже есть `spf13/pflag`); для systemd — `Environment=XSWITCHER_LANG=ru`. Документировать.
- **Не переводить машинно-читаемые маркеры** (`SYSLOG.Warning("2".."11")`, `Language: -1 >> 0`, `keybd interface`, `= class`/`* class`, `[Actions]`-дампы) — они нужны grep'ам стенда; оставить en безусловно (согл. решению владельца).
- Опционально (мелко): `ipc.Request.Lang` (`internal/ipc/protocol.go`) → `server.go` зовёт `l10n.Set`; обратно совместимо; пометить process-global last-writer-wins.
- Коммиты: `5.1` config-ошибки · `5.2` src-паники/ошибки · `5.3` src-информационные · `5.4` notify+daemon · `5.5` ipc server (+Lang).

### Фаза 6 — Тесты, ru-каталог, drop-in, документация
- **Locale-pin** вместо ассертов на переведённый текст: `TestMain` c `l10n.SetForTest("en")` в пакетах `cmd/gui`, `internal/config`, `src`; ассерты на токены конфига (`RetypeWord`, `group 0`, `"en"`) сохраняем (они не переводятся).
- `autodetect_editor_test.go`: мигрировать подстроки на `classifyPreview(...).Kind`+числа; оставить один golden-тест рендера en.
- Стенд: `export LC_ALL=C XSWITCHER_LANG=en` в шапке `stand/run.sh` и `smoke.sh`.
- `internal/l10n/locales/ru.json` — по записи на ключ Фаз 3/5 + комплитнесс-тест `inventory` (regex по `l10n.X("key","literal")` во всех файлах; каждый ключ обязан быть в `ru.json`) — он же guard от дрейфа для будущих языков.
- Новые тесты: `plural_ru_test.go` (1/2/5/11/21), `dropin_test.go` (`xx.json` → резолвится без правки Go), `locale_rebuild_test.go` (test.NewApp → `setLocale("ru")` → (a) тайтлы изменились, (b) `keyOf` те же ключи, (c) набор `modsFromWidgets` байт-идентичен en-прогону).
- `README.md`: секция «Adding a language» (положить `locales/<code>.json`, определить `language.name`, опционально плюралы).
- Коммиты: `6.1` пины тестов (можно раньше Фазы 3 ради bisectable-green) · `6.2` ru · `6.3` inventory+dropin · `6.4` стенд-пины · `6.5` docs.

### Фаза 7 — Verification (в контейнере)
1. `docker exec xswitcher-live bash -c 'cd /w && GOFLAGS=-buildvcs=false go build ./... && go vet ./... && go test ./...'`
2. Guard «нет Fyne в root-бинарнике»: `go list -deps ./src/ | grep -c fyne.io` == 0 (и для `./cmd/daemon`).
3. `bash stand/live.sh run` (61) + `smoke.sh` — с en-пином.
4. GUI-smoke (сейчас отсутствует): добавить шаг в `smoke.sh` — собрать `bin/xswitcher-gui`, Xvfb `:99`, скриншот дважды (`LC_ALL=en_US.UTF-8` и `ru_RU.UTF-8`); проверка отрендеренного текста через `test.NewApp`-юниты + глазами по скрину (Fyne не даёт дешёвого извлечения текста из живого X-окна).
5. Приёмка переключателя: смена на Русский → все видимые строки меняются без рестарта, выбранный таб восстановлен, статус Connected переживает перестройку, `[GUI] Language` записан в конфиг, а **остальной конфиг на диске байт-идентичен** (guard display/ключ).
6. Leak-scan untranslated: grep мест construction на «сырой» английский + `glm/scripts/scan_leaks.py` по изменённым файлам (CJK/glue/secret).
7. `git diff --stat backup/pre-i18n-fyne-<date>..HEAD` — размер diff по фазам; bump-PR (`go.mod`/`go.sum`) меряется отдельно от i18n-PR.
8. Goroutine-leak: `runtime.NumGoroutine()` стабилен после 5 переключений языка (subscribe-loop и `sounds.Player` `cmd.Wait()` не накапливают).

## Коммит-карта
`backup/pre-i18n-fyne-<date>` → `0.1` fyne bump (go.mod/go.sum, отдельный PR) → `0.2` фиксы → `1.1/1.2` l10n+fyne_locale → `2.1` identity/key → `3.1…3.15` выноска строк → `4.1…4.4` appshell/[GUI]/переключатель/трей → `5.1…5.5` демон → `6.1…6.5` тесты/ru/docs → `7` gui-smoke.

## Открытые вопросы (уточнить при старте реализации)
1. Если последняя Fyne ломает трей/GL в контейнере — падать на v2.6.3 (min с ru) или тащить фиксы?
2. ДВА upstream PR (bump, затем i18n) — подтвердить (настоятельно рекомендовано).
3. `[GUI] Language` принимает произвольный код (宽松, fallback en) или жёсткий whitelist по каталогам l10n?
4. Порядок: `6.1` (пины тестов) до `3.x` ради bisectable-green — ок?
5. Передача несохранённых правок при смене языка: confirm+reload (рекоменд.) vs полный перенос значений?

## Ограничение исполнения
Я сейчас read-only (plan mode) и по правилам владельца **не могу** менять/коммитить в его дереве (занятый слот, незакрытые правки, запрет git-мутаций). Реализацию запускает владелец дерева (или я по явному разрешению, когда слот свободен и дерево чисто), начиная с rollback-тега Фазы 0. Порядок с pending-задачами (adversarial-перечтение `previewReport`/`autoDetectWord` и reword `f3b8984`/`a09b065`) согласовать отдельно — i18n-Фаза 3.15 сама переделает `previewReport`, что пересекается с перечтением.