#!/usr/bin/env python3
"""
Автотест GUI xswitcher: физическое переключение раскладки через xdotool.

Цель: проверить, что нажатие горячей клавиши (Win+Space / Super+Space) меняет
раскладку и текст в поле ввода отображается в соответствующей раскладке.

Сценарий проверки:
  1. Демон запущен с русской раскладкой (RU).
  2. В текстовом поле написан "привет".
  3. Нажимаем горячую клавишу — раскладка переключается на английскую (US).
  4. Текст визуально отображается как "ghbdtn" (то, что видит пользователь).
  5. Нажимаем горячую клавишу снова — раскладка возвращается на русскую.
  6. Текст снова отображается как "привет".

Установка (одноразово):
    pip install pytest xdotool  # xdotool должен быть в PATH

Запуск:
    pytest test_xswitcher_with_physical_input.py -v

Примечание:
  — Точные координаты окна можно уточнить, запустив noVNC на порту 6081 и
    измерив позицию поля ввода через xdotool getmouselocation.
  — Скрипт работает в среде с X-сервером (locah или Docker + Xvfb).

Dependencies:
  pip install pytest xdotool
"""

import os
import subprocess
import sys
import time
from typing import Final, Optional


# === Настройки окружения ===================================================== #
NOVNC_URL: Final[str] = "http://host.docker.internal:6081"
NOVNC_PORT: Final[int] = 6081

# Координаты внутри GUI окна xswitcher (нужно уточнить для вашего стенда):
#   x=237, y=437 — область около кнопки переключения / поля ввода
#   Эти значения измерены на скриншоте gui-screenshot.png от 05.10.2026.
X_INPUT_FIELD: Final[int] = 237
Y_INPUT_FIELD: Final[int] = 437

# Окно "привет" в русской раскладке → на английской будет "ghbdtn":
EXPECTED_RUSSIAN_TEXT: Final[str] = "привет"
EXPECTED_ENGLISH_TEXT: Final[str] = "ghbdtn"

# Таймауты (секунды):
HOTKEY_DELAY: Final[float] = 0.5   # ждать обработки события IME после нажатия Win+Space
FIELD_CLICK_WAIT: Final[float] = 1.0  # время между кликом и вводом текста


def run_xdotool(cmd: str) -> subprocess.CompletedProcess[str]:
    """Выполнить xdotool и вернуть CompletedProcess."""
    result = subprocess.run(
        ["xdotool", cmd],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError(f"xdotool {cmd!r} failed:\n{result.stderr}")
    return result


def get_cursor_position() -> tuple[int, int]:
    """Получить текущие координаты курсора."""
    result = run_xdotool("getmouselocation --shell")
    lines = result.stdout.strip().split("\n")
    coords: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        coords[key.strip()] = value.strip()

    x_str, y_str = coords.get("x", "0"), coords.get("y", "0")
    return (int(x_str), int(y_str))


def get_active_window_title() -> str:
    """Получить заголовок активного окна."""
    window_id_result = run_xdotool("getactivewindow")
    window_id = window_id_result.stdout.strip().strip('"') or "unknown"

    title_result = run_xdotool(f"windowgetname {window_id}")
    title = title_result.stdout.strip().strip('"') or "(без названия)"
    return title


def find_xswitcher_window_title() -> str:
    """Попробовать определить название окна xswitcher (если известно)."""
    # Если у вас окно имеет стандартный заголовок, можно распознать его.
    # Для примера — ищем окно с ключевыми словами GUI или xswitcher.
    title_result = run_xdotool("getactivewindow")
    window_id = title_result.stdout.strip().strip('"') or "unknown"

    name_result = run_xdotool(f"windowgetname {window_id}")
    title = name_result.stdout.strip().strip('"')
    return title


def click_on_input_field() -> subprocess.CompletedProcess[str]:
    """Кликнуть по полю ввода (координаты X_INPUT_FIELD, Y_INPUT_FIELD)."""
    result = run_xdotool(f"mousemove --sync {X_INPUT_FIELD} {Y_INPUT_FIELD}")
    time.sleep(0.1)  # дать системе обработать движение

    click_result = run_xdotool("click")
    return click_result


def press_hotkey() -> subprocess.CompletedProcess[str]:
    """Нажать горячую клавишу переключения раскладки (Win+Space)."""
    # На Windows/Linux: Super(Windows)+Space переключает раскладку.
    result = run_xdotool("key --delay 10 win_l space")
    return result


def type_text(text: str) -> subprocess.CompletedProcess[str]:
    """Ввести текст в активное окно."""
    # xdotool type отправляет клавиатурульные события, которые видит GUI.
    result = run_xdotool(f"type --delay 10 '{text}'")
    return result


def is_application_running() -> bool:
    """Проверить, запущен ли демон (через /proc или через ответ на IPC)."""
    # Если у вас есть PID — можно проверить напрямую.
    # Здесь просто проверяем наличие процесса xswitcher в системе.
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=3
        )
        return "xswitcher" in result.stdout
    except Exception as e:
        raise RuntimeError(f"Не удалось проверить запущенность демонов: {e}")


def get_input_field_text_via_api() -> Optional[str]:
    """
    Попытаться прочитать текст из поля ввода через GUI API.

    В xswitcher (Fyne) текст хранится в поле input field, которое можно
    получить через Fyne's internal API. Но для автотеста проще использовать
    подход «через обратную связь» — мы знаем, что после переключения раскладки
    текст должен измениться на "ghbdtn".

    Альтернатива: если у вас есть IPC-интерфейс (например, через grpc),
    можно читать оттуда. Пока возвращаем None.
    """
    return None  # TODO: реализовать чтение через Fyne API или IPC


def wait_for_text_change(target: str, timeout: float = 2.0) -> bool:
    """Ждать, пока текст в поле ввода изменится на target."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        # Для автотеста мы не знаем точный способ чтения текста из GUI —
        # поэтому используем эвристику: ждём завершения обработки события IME.
        # В реальном тесте можно подключить слушатель изменений поля ввода
        # через Fyne API или IPC-интерфейс.
        time.sleep(0.1)
    return False


# === Тесты =================================================================== #

class TestGuiXdotoolPhysicalInput:
    """Тесты физического переключения раскладки через xdotool."""

    @pytest.fixture(autouse=True)
    def setup(self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch):
        """Подготовить окружение перед каждым тестом."""
        # Убедиться, что xdotool доступен.
        result = subprocess.run(["which", "xdotool"], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                "xdotool не найден в PATH. "
                "Установите через: sudo apt-get install xdotool"
            )

        # Убедиться, что демон запущен (если нужен).
        # Если стенд запускается отдельно — этот шаг можно пропустить.
        if not is_application_running():
            raise RuntimeError(
                "Демон xswitcher не запущен. Запустите через "
                '"stand/run.sh" или аналогичный стенд.'
            )

    def test_physical_input_ru_en_switch(self, capsys: pytest.CaptureFixture[str]) -> None:
        """
        Проверить переключение раскладки RU → EN и корректное отображение текста.

        Сценарий:
          1. Приложение запущено с русской раскладкой.
          2. В поле ввода есть текст "привет".
          3. Нажимаем Win+Space — раскладка переключается на английскую.
          4. Текст визуально отображается как "ghbdtn" (английская раскладка).

        Ожидаемый результат: после нажатия горячей клавиши текст в поле ввода
        должен измениться с "привет" на "ghbdtn".
        """
        print("\n=== Тест: RU → EN переключение ===")

        # Шаг 1: кликаем по полю ввода (подготавливаем фокус)
        print(f"Кликаю по полю ввода в точке ({X_INPUT_FIELD}, {Y_INPUT_FIELD})...")
        click_on_input_field()
        time.sleep(FIELD_CLICK_WAIT)

        # Шаг 2: нажимаем горячую клавишу переключения раскладки.
        # В идеале — кликаем сначала на кнопку переключения (если она есть),
        # но для проверки IME достаточно отправить событие клавиши.
        print("Нажимаю Win+Space (переключение раскладки)...")
        result = press_hotkey()
        if result.returncode != 0:
            raise RuntimeError(f"xdotool key вернул код {result.returncode}: {result.stderr}")

        # Шаг 3: ждём обработки события IME.
        print("Жду, пока IME обработает переключение раскладки...")
        time.sleep(HOTKEY_DELAY)

        # Шаг 4: проверяем содержимое поля ввода.
        current_text = get_input_field_text_via_api()
        if current_text is None:
            raise NotImplementedError(
                "get_input_field_text_via_api пока не реализован — "
                "используем эвристику: если раскладка переключилась, текст изменился."
            )

        # Эвистическая проверка: мы знаем, что на английской раскладке
        # русское слово "привет" отображается как "ghbdtn".
        # В реальности — нужно читать поле ввода из GUI.
        print(f"Текущий текст в поле: {current_text!r}")

        assert current_text == EXPECTED_ENGLISH_TEXT, (
            f"Ожидается '{EXPECTED_ENGLISH_TEXT}', но получил(а) {current_text!r}"
        )
        print("✓ Текст успешно отобразился как 'ghbdtn'")

    def test_physical_input_en_ru_switch(self, capsys: pytest.CaptureFixture[str]) -> None:
        """
        Обратное переключение: EN → RU.

        Сценарий:
          1. Поле содержит "ghbdtn" (английская раскладка).
          2. Нажимаем Win+Space — раскладка становится русской.
          3. Текст визуально меняется на "привет".
        """
        print("\n=== Тест: EN → RU переключение ===")

        click_on_input_field()
        time.sleep(FIELD_CLICK_WAIT)

        print("Нажимаю Win+Space...")
        result = press_hotkey()
        if result.returncode != 0:
            raise RuntimeError(f"xdotool key вернул код {result.returncode}: {result.stderr}")

        time.sleep(HOTKEY_DELAY)

        current_text = get_input_field_text_via_api()
        print(f"Текущий текст в поле: {current_text!r}")

        assert current_text == EXPECTED_RUSSIAN_TEXT, (
            f"Ожидается '{EXPECTED_RUSSIAN_TEXT}', но получил(а) {current_text!r}"
        )
        print("✓ Текст успешно отобразился как 'привет'")

    def test_cursor_stable_after_hotkey(self) -> None:
        """Проверить, что курсор не улетел после нажатия горячей клавиши."""
        x_before, y_before = get_cursor_position()
        print(f"Позиция до переключения раскладки: ({x_before}, {y_before})")

        click_on_input_field()
        press_hotkey()
        time.sleep(HOTKEY_DELAY)

        x_after, y_after = get_cursor_position()
        print(f"Позиция после переключения раскладки: ({x_after}, {y_after})")

        assert abs(x_after - x_before) <= 10 and abs(y_after - y_before) <= 10, (
            f"Курсор сместился слишком сильно: "
            f"({x_before}, {y_before}) → ({x_after}, {y_after})"
        )

    def test_active_window_stable(self) -> None:
        """Проверить, что активное окно не меняется при переключении раскладки."""
        title_ru = get_active_window_title()
        print(f"Активное окно до переключения: {title_ru!r}")

        press_hotkey()
        time.sleep(HOTKEY_DELAY)

        title_en = get_active_window_title()
        print(f"Активное окно после переключения: {title_en!r}")

        assert title_ru == title_en, (
            f"Заголовок активного окна изменился:\nRU: {title_ru}\nEN: {title_en}"
        )

    def test_multiple_switches(self) -> None:
        """Проверить несколько переключений подряд."""
        print("\n=== Тест: многократные переключения ===")

        # Начинаем с русской раскладки (как по умолчанию на стенде).
        text = EXPECTED_RUSSIAN_TEXT

        for i in range(5):
            click_on_input_field()
            press_hotkey()
            time.sleep(HOTKEY_DELAY)

            current_text = get_input_field_text_via_api()
            if current_text is None:
                raise NotImplementedError("get_input_field_text_via_api не реализован")

            # Чередование раскладок: RU → EN → RU → EN ...
            expected = EXPECTED_ENGLISH_TEXT if i % 2 == 0 else EXPECTED_RUSSIAN_TEXT
            assert current_text == expected, (
                f"Шаг {i}: ожидалось '{expected}', получил(а) {current_text!r}"
            )
            print(f"  Шаг {i}: текст = {current_text!r}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--capture=system"])
