from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import atexit
import argparse
import ctypes
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from ctypes import wintypes

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import app as nicegui_app, run, ui  # type: ignore

AUDION_CANONICAL_TOOLTIP_DELAY_MS = 1500
AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS = 100
AUDION_CANONICAL_TOOLTIP_TRANSITION_MS = 100


def install_audion_canonical_tooltip_defaults() -> None:
    try:
        from nicegui.elements.tooltip import Tooltip as NiceGuiTooltip  # type: ignore
    except Exception:
        return
    if getattr(NiceGuiTooltip, "_audion_canonical_tooltip_defaults", False):
        return
    original_init = NiceGuiTooltip.__init__

    def audion_tooltip_init(self: Any, text: str = "") -> None:
        original_init(self, text)
        self.props["delay"] = AUDION_CANONICAL_TOOLTIP_DELAY_MS
        self.props["hide-delay"] = AUDION_CANONICAL_TOOLTIP_HIDE_DELAY_MS
        self.props["transition-duration"] = AUDION_CANONICAL_TOOLTIP_TRANSITION_MS
        self.classes("audion-tooltip")

    NiceGuiTooltip.__init__ = audion_tooltip_init  # type: ignore[method-assign]
    NiceGuiTooltip._audion_canonical_tooltip_defaults = True  # type: ignore[attr-defined]


install_audion_canonical_tooltip_defaults()


AUDION_CANONICAL_UI_CSS = """
<style id="audion-canonical-tooltip-icon-style">
  html body .q-tooltip,
  html body .audion-tooltip {
    background: rgb(23, 33, 43) !important;
    background-color: rgb(23, 33, 43) !important;
    color: #f4f8fb !important;
    border: 1px solid rgba(88, 166, 255, 0.24) !important;
    border-radius: 8px !important;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.34) !important;
  }
  html body .q-icon.material-icons,
  html body .q-icon.material-symbols-outlined,
  html body .q-icon.material-symbols-rounded,
  html body i.material-icons,
  html body i.material-symbols-outlined,
  html body i.material-symbols-rounded,
  html body .q-btn .q-icon,
  html body .q-btn .material-icons,
  html body .q-btn .material-symbols-outlined,
  html body .q-btn .material-symbols-rounded,
  html body .q-field .q-field__append .q-icon,
  html body .q-field .q-field__prepend .q-icon,
  html body .q-item .q-icon,
  html body .q-menu .q-icon,
  html body .audion-label-icon,
  html body .audion-path-option-pin,
  html body .audion-select-option-pin {
    font-size: 14px !important;
    width: 14px !important;
    min-width: 14px !important;
    height: 14px !important;
    line-height: 14px !important;
  }
  html body .material-icons,
  html body .q-icon.material-icons {
    font-family: "Material Icons" !important;
  }
  html body .material-symbols-outlined,
  html body .q-icon.material-symbols-outlined {
    font-family: "Material Symbols Outlined" !important;
  }
  html body .material-symbols-rounded,
  html body .q-icon.material-symbols-rounded {
    font-family: "Material Symbols Rounded" !important;
  }
</style>
"""


def add_audion_canonical_ui_styles() -> None:
    ui.add_head_html(AUDION_CANONICAL_UI_CSS)



def audion_tooltip_path_text(path_value: Any) -> str:
    raw = str(path_value or "").strip()
    if not raw:
        return ""
    try:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        return str(path)
    except Exception:
        return raw


def audion_folder_button_tooltip(folder_id: str, path_value: Any) -> str:
    key = str(folder_id or "folder").strip().lower()
    path_text = audion_tooltip_path_text(path_value)
    if getattr(settings, "language", "ru") == "ru":
        descriptions = {
            "logs": "папку логов запусков и вывода терминала",
            "report": "папку отчётов и результатов операций",
            "reports": "папку отчётов и результатов операций",
            "config": "папку конфигурации проекта: manifest, GUI-настройки и кэши",
            "state": "папку рабочего состояния GUI",
            "project": "корневую папку проекта",
            "root": "корневую папку проекта",
            "data": "папку данных проекта",
            "pipeline": "папку pipeline-артефактов и промежуточных результатов",
            "github": "папку GitHub-артефактов проекта",
            "install": "папку install/runtime-артефактов проекта",
        }
        description = descriptions.get(key, f"папку {folder_id}")
        return f"Открыть {description}: {path_text}" if path_text else f"Открыть {description}."
    descriptions = {
        "logs": "the logs folder with run and terminal output",
        "report": "the reports/results folder",
        "reports": "the reports/results folder",
        "config": "the project config folder with manifest, GUI settings, and caches",
        "state": "the GUI state folder",
        "project": "the project root folder",
        "root": "the project root folder",
        "data": "the project data folder",
        "pipeline": "the pipeline artifacts and intermediate results folder",
        "github": "the project GitHub artifacts folder",
        "install": "the project install/runtime artifacts folder",
    }
    description = descriptions.get(key, f"the {folder_id} folder")
    return f"Open {description}: {path_text}" if path_text else f"Open {description}."


def audion_terminal_action_tooltip(action: str) -> str:
    key = str(action or "").strip().lower()
    if getattr(settings, "language", "ru") == "ru":
        tips = {
            "clear_terminal_window": "Очистить только видимое окно терминала. Файлы логов, отчёты и результаты операций не удаляются.",
            "expand": "Открыть терминал в большом окне, чтобы читать длинный вывод без тесной панели.",
            "expand_log": "Открыть терминал в большом окне, чтобы читать длинный вывод без тесной панели.",
            "pin_command": "Закрепить текущую команду в истории терминала для быстрого повторного запуска.",
            "unpin_command": "Открепить текущую команду от верхней части истории терминала.",
            "clear_history": "Очистить историю команд терминала. Закреплённые команды и файлы логов не удаляются.",
            "terminal_shell": "Выбрать оболочку, в которой будут запускаться команды терминала.",
            "terminal_history": "Выбрать ранее сохранённую или закреплённую команду терминала.",
            "terminal_command": "Команда, которая будет выполнена из выбранной рабочей папки.",
            "terminal_cwd": "Рабочая папка терминала. Команда будет запущена именно отсюда.",
            "pick_folder": "Выбрать рабочую папку терминала через системный диалог.",
            "terminal_run": "Запустить введённую команду в выбранной оболочке и рабочей папке.",
            "latest_report": "Открыть последний созданный отчёт, если он уже есть.",
            "command_preview": "Показать команду, которая будет запущена с текущими параметрами, без выполнения операции.",
            "report_view": "Открыть встроенный список отчётов без перехода в проводник.",
            "close": "Закрыть большое окно терминала и вернуться к основной панели.",
        }
    else:
        tips = {
            "clear_terminal_window": "Clear only the visible terminal window. Log files, reports, and operation results are not deleted.",
            "expand": "Open the terminal in a large window for reading long output comfortably.",
            "expand_log": "Open the terminal in a large window for reading long output comfortably.",
            "pin_command": "Pin the current terminal command for quick reuse.",
            "unpin_command": "Remove the current command from the pinned command list.",
            "clear_history": "Clear terminal command history. Pinned commands and log files are not deleted.",
            "terminal_shell": "Choose the shell used to run terminal commands.",
            "terminal_history": "Pick a saved or pinned terminal command.",
            "terminal_command": "Command to run from the selected working folder.",
            "terminal_cwd": "Terminal working folder. Commands are started from here.",
            "pick_folder": "Choose the terminal working folder with the system dialog.",
            "terminal_run": "Run the entered command in the selected shell and working folder.",
            "latest_report": "Open the latest generated report, if one exists.",
            "command_preview": "Show the command that would run with the current settings, without executing it.",
            "report_view": "Open the built-in reports list without switching to the file explorer.",
            "close": "Close the large terminal window and return to the main panel.",
        }
    return tips.get(key, key.replace("_", " ").strip())


from system_core.ansi_terminal import (
    ansi_to_html,
    strip_ansi,
    terminal_html as _render_terminal_html,
    terminal_lines_html as _terminal_lines_html,
)
from system_core.subprocess_text import decode_subprocess_output, decoded_process_lines, is_python_command
from system_core.ui_nicegui.workbench import (
    WORKBENCH_FEEDBACK_CSS,
    WORKBENCH_LAYOUT_CSS,
    WORKBENCH_OVERRIDE_CSS,
    WorkbenchAdapter,
    WorkbenchConfig,
    WorkbenchHandlers,
    WorkbenchRenderer,
    WorkbenchRole,
    canonical_role,
)


def terminal_lines_html(lines, leading_newline: bool = False) -> str:
    return _terminal_lines_html(lines, leading_newline=False).replace("\n", "")


def render_terminal_html(lines) -> str:
    return _render_terminal_html(lines).replace("\n", "")


def tolerate_missing_process_pool() -> None:
    """Keep NiceGUI alive when multiprocessing is blocked by the environment."""
    try:
        import nicegui.run as nicegui_run  # type: ignore
    except Exception:
        return

    original_setup = getattr(nicegui_run, "setup", None)
    if not callable(original_setup):
        return

    def safe_setup() -> None:
        try:
            original_setup()
        except (OSError, PermissionError) as exc:
            logging.warning("NiceGUI process pool disabled: %s", exc)
            nicegui_run.process_pool = None

    nicegui_run.setup = safe_setup


tolerate_missing_process_pool()


MAIN_PY = ROOT / "system_core" / "main.py"
DOCTOR_PY = ROOT / "system_core" / "doctor.py"
GUI_SETTINGS_PATH = ROOT / "config" / "gui_settings.yaml"
UI_COLORS_PATH = ROOT / "config" / "ui_colors.yaml"
TOOL_MANIFEST_PATH = ROOT / "config" / "tool_manifest.yaml"
PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")
TERMINAL_HISTORY_LIMIT = 2000
PATH_HISTORY_LIMIT = 100

FOLDERS = {
    "input": ROOT / "input",
    "output": ROOT / "output",
    "config": ROOT / "config",
    "logs": ROOT / "logs",
    "report": ROOT / "report",
    "release": ROOT / "release",
}

TRANSLATIONS = {
    "ru": {
        "subtitle": "GUI-shell поверх существующего CLI",
        "cancel": "Отменить",
        "workspace": "Рабочие папки",
        "operations": "Операции",
        "document_operations": "Операции с документами",
        "pdf_operations": "Операции с PDF",
        "conversion_group": "КОНВЕРТАЦИЯ В PDF",
        "convert_mode": "Конвертировать...",
        "convert_setup": "Конвертация документов",
        "crop_pdf_group": "ОБРЕЗАТЬ PDF",
        "crop_pdf_mode": "Обрезать PDF...",
        "crop_pdf_setup": "Обрезка PDF",
        "crop_pptx_setup": "Обрезка PPTX",
        "crop_pdf_manual_setup": "ОБРАБОТКА PDF",
        "repeat_crop": "Повторить для уже обрезанных",
        "pdf_crop_action": "Что сделать с PDF",
        "add_pdf_group": "ИЗМЕНИТЬ PDF",
        "add_pdf_mode": "Изменить PDF...",
        "add_pdf_setup": "Изменение PDF",
        "page_numbers_setup": "НУМЕРАЦИЯ СТРАНИЦ PDF",
        "scale_pdf_setup": "Уменьшить PDF",
        "split_vertical": "Разрезать по вертикали 50/50",
        "split_horizontal": "Разрезать по горизонтали 50/50",
        "skip_cover": "Разрезать все кроме обложки",
        "skip_cover_hint": "Для 50/50: первая и последняя страницы останутся целыми.",
        "crop_margins": "Обрезать поля",
        "aspect_crop": "Кадрирование",
        "aspect_none": "Не обрезать",
        "aspect_16_9": "Обрезать 16:9",
        "aspect_a_series": "Обрезать под A4/A3",
        "post_crop": "Обрезка презентаций после конвертации",
        "post_scale": "Уменьшить содержимое презентаций после конвертации",
        "scale_none": "Не уменьшать",
        "scale_percent": "Уменьшить до процента",
        "scale_percent_field": "Процент",
        "scale_pdf_content": "Уменьшить содержимое PDF",
        "left_mm": "Слева, мм",
        "right_mm": "Справа, мм",
        "top_mm": "Сверху, мм",
        "bottom_mm": "Снизу, мм",
        "page_numbers": "Колонтитул нумерации страниц",
        "start_page": "С какой страницы",
        "start_number": "С какого номера",
        "offset_mm": "От края, мм",
        "position": "Расположение",
        "run": "Запустить",
        "convert_file": "Конвертировать файл",
        "file_path": "Путь к Office-файлу",
        "source_folder": "Источник",
        "destination_folder": "Папка-приёмник",
        "target_folder": "Назначение",
        "add_folders": "Добавить папки...",
        "add": "Добавить...",
        "cache_ready": "Кэш источников: {count}",
        "cache_empty": "Кэш источников пуст",
        "status": "Статус",
        "log": "Журнал операции",
        "idle": "Ожидание",
        "running": "Выполняется",
        "done": "Готово",
        "error": "Ошибка",
        "another_running": "Другая операция уже выполняется.",
        "file_required": "Укажите путь к Office-файлу.",
        "source_required": "Укажите папку-источник.",
        "destination_required": "Укажите папку-приёмник.",
        "folder_only": "В этом поле нужна папка, не файл.",
        "operation_done": "Операция завершена.",
        "operation_failed": "Операция завершилась с кодом {code}.",
        "language": "Язык",
        "theme": "Тема",
        "dark": "Темная",
        "light": "Светлая",
        "language_saved": "Язык сохранен. Перезагружаю интерфейс.",
        "theme_saved": "Тема сохранена. Перезагружаю интерфейс.",
        "open": "Открыть",
        "add_file_short": "Добавить файл...",
        "file_list": "File List",
        "file_list_button": "Список",
        "file_list_empty": "INPUT has no files.",
        "file_list_missing": "INPUT was not found: {path}",
        "file_list_ready": "File list generated: {count}.",
        "terminal_file": "File",
        "clear_io": "Очистить I/O",
        "clear_io_short": "Сбросить",
        "delete_io_short": "Удалить",
        "source_selected": "Источник выбран.",
        "target_selected": "Назначение выбрано.",
        "path_required": "Выберите путь.",
        "path_pinned": "Путь закреплен.",
        "path_unpinned": "Закрепление снято.",
        "confirm_title": "Подтвердите действие",
        "confirm_cleanup_io": "Удалить содержимое input и output? Папки останутся на месте.",
        "choose_options": "Параметры запуска",
        "no_options_selected": "Выберите хотя бы один пункт.",
        "back": "Назад",
        "picker_cancelled": "Выбор отменен.",
        "expand_log": "Развернуть",
        "clear_terminal_window": "Очистить окно терминала",
        "report": "Report",
        "close": "Закрыть",
        "lang_switch": "EN",
    },
    "en": {
        "subtitle": "GUI shell over the existing CLI",
        "cancel": "Cancel",
        "workspace": "Workspace folders",
        "operations": "Operations",
        "document_operations": "Document operations",
        "pdf_operations": "PDF operations",
        "conversion_group": "CONVERSION",
        "convert_mode": "Convert...",
        "convert_setup": "Document conversion",
        "crop_pdf_group": "CROP PDF",
        "crop_pdf_mode": "Crop PDF...",
        "crop_pdf_setup": "PDF crop",
        "crop_pptx_setup": "PowerPoint PDF crop",
        "crop_pdf_manual_setup": "PDF tools",
        "repeat_crop": "Repeat for already cropped files",
        "pdf_crop_action": "PDF action",
        "add_pdf_group": "EDIT PDF",
        "add_pdf_mode": "Edit PDF...",
        "add_pdf_setup": "PDF editing",
        "page_numbers_setup": "Page numbering",
        "scale_pdf_setup": "Scale PDF",
        "split_vertical": "Split vertically 50/50",
        "split_horizontal": "Split horizontally 50/50",
        "skip_cover": "Split all except cover",
        "skip_cover_hint": "For 50/50 split: first and last pages stay unchanged.",
        "crop_margins": "Crop margins",
        "aspect_crop": "Crop aspect",
        "aspect_none": "Do not crop",
        "aspect_16_9": "Crop to 16:9",
        "aspect_a_series": "Crop to A4/A3",
        "post_crop": "Crop presentations after conversion",
        "post_scale": "Scale presentation contents after conversion",
        "scale_none": "Do not scale",
        "scale_percent": "Scale to percent",
        "scale_percent_field": "Percent",
        "scale_pdf_content": "Scale PDF content",
        "left_mm": "Left, mm",
        "right_mm": "Right, mm",
        "top_mm": "Top, mm",
        "bottom_mm": "Bottom, mm",
        "page_numbers": "Page number footer/header",
        "start_page": "Start page",
        "start_number": "Start number",
        "offset_mm": "Edge offset, mm",
        "position": "Position",
        "run": "Run",
        "convert_file": "Convert file",
        "file_path": "Office file path",
        "source_folder": "Source",
        "destination_folder": "Destination folder",
        "target_folder": "Target",
        "add_folders": "Add folders...",
        "add": "Add...",
        "cache_ready": "Source cache: {count}",
        "cache_empty": "Source cache is empty",
        "status": "Status",
        "log": "Operation log",
        "idle": "Idle",
        "running": "Running",
        "done": "Done",
        "error": "Error",
        "another_running": "Another operation is already running.",
        "file_required": "Office file path is required.",
        "source_required": "Source folder is required.",
        "destination_required": "Destination folder is required.",
        "folder_only": "This field accepts a folder, not a file.",
        "operation_done": "Operation finished.",
        "operation_failed": "Operation finished with exit code {code}.",
        "language": "Language",
        "theme": "Theme",
        "dark": "Dark",
        "light": "Light",
        "language_saved": "Language saved. Reloading UI.",
        "theme_saved": "Theme saved. Reloading UI.",
        "open": "Open",
        "add_file_short": "Add file...",
        "file_list": "File List",
        "file_list_button": "List",
        "file_list_empty": "INPUT has no files.",
        "file_list_missing": "INPUT was not found: {path}",
        "file_list_ready": "File list generated: {count}.",
        "terminal_file": "File",
        "clear_io": "Clear I/O",
        "clear_io_short": "Reset",
        "delete_io_short": "Delete",
        "source_selected": "Source selected.",
        "target_selected": "Target selected.",
        "path_required": "Choose a path.",
        "path_pinned": "Path pinned.",
        "path_unpinned": "Path unpinned.",
        "confirm_title": "Confirm action",
        "confirm_cleanup_io": "Delete contents of input and output? The folders stay in place.",
        "choose_options": "Run options",
        "no_options_selected": "Select at least one item.",
        "back": "Back",
        "picker_cancelled": "Selection cancelled.",
        "expand_log": "Expand",
        "clear_terminal_window": "Clear terminal window",
        "report": "Report",
        "close": "Close",
        "lang_switch": "RU",
    },
}


def expand_arg(value: Any) -> str:
    text = str(value)
    return (
        text.replace("{MAIN_PY}", str(MAIN_PY))
        .replace("{DOCTOR_PY}", str(DOCTOR_PY))
        .replace("{ROOT}", str(ROOT))
    )


def normalize_option_choice(item: dict[str, Any]) -> dict[str, Any]:
    label = str(item.get("label", item.get("id", ""))).strip()
    return {
        "id": str(item.get("id", "")).strip(),
        "label_en": label,
        "label_ru": str(item.get("label_ru", label)).strip(),
        "value": str(item.get("value", "")).strip(),
        "default": bool(item.get("default", False)),
    }


def normalize_option_group(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title", item.get("id", ""))).strip()
    description = str(item.get("description", "")).strip()
    choices = item.get("choices", [])
    args_prefix = item.get("args_prefix", [])
    if not isinstance(choices, list):
        choices = []
    if not isinstance(args_prefix, list):
        args_prefix = []
    return {
        "id": str(item.get("id", "")).strip(),
        "type": str(item.get("type", "checkboxes")).strip(),
        "title_en": title,
        "title_ru": str(item.get("title_ru", title)).strip(),
        "description_en": description,
        "description_ru": str(item.get("description_ru", description)).strip(),
        "min_selected": int(item.get("min_selected", 0) or 0),
        "args_prefix": [expand_arg(arg) for arg in args_prefix],
        "separator": str(item.get("separator", ",")),
        "choices": [
            choice
            for choice in (normalize_option_choice(choice) for choice in choices if isinstance(choice, dict))
            if choice["id"] and choice["value"]
        ],
    }


def normalize_operation(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title", item.get("title_en", item.get("id", "")))).strip()
    description = str(item.get("description", item.get("description_en", ""))).strip()
    args = item.get("args", [])
    language_args = item.get("language_args", {})
    option_groups = item.get("option_groups", [])
    if not isinstance(args, list):
        args = []
    if not isinstance(language_args, dict):
        language_args = {}
    if not isinstance(option_groups, list):
        option_groups = []
    return {
        "id": str(item.get("id", "")).strip(),
        "title_en": title,
        "title_ru": str(item.get("title_ru", title)).strip(),
        "description_en": description,
        "description_ru": str(item.get("description_ru", description)).strip(),
        "args": [expand_arg(arg) for arg in args],
        "language_args": {
            str(lang): [expand_arg(arg) for arg in values]
            for lang, values in language_args.items()
            if isinstance(values, list)
        },
        "option_groups": [
            group
            for group in (normalize_option_group(group) for group in option_groups if isinstance(group, dict))
            if group["id"] and group["choices"]
        ],
        "needs_file": bool(item.get("needs_file", False)),
    }


def load_tool_manifest() -> tuple[dict[str, Any], list[str], list[str]]:
    if not TOOL_MANIFEST_PATH.exists():
        raise RuntimeError(f"Tool manifest was not found: {TOOL_MANIFEST_PATH}")
    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyYAML is required to read tool_manifest.yaml.") from exc

    raw = yaml.safe_load(TOOL_MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError(f"Tool manifest must contain a mapping: {TOOL_MANIFEST_PATH}")

    operations: dict[str, dict[str, Any]] = {}
    main_ids: list[str] = []
    file_ids: list[str] = []

    for section_name, id_bucket in (("operations", main_ids), ("file_operations", file_ids)):
        items = raw.get(section_name, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            operation = normalize_operation(item)
            if not operation["id"]:
                continue
            operations[operation["id"]] = operation
            id_bucket.append(operation["id"])

    return operations, main_ids, file_ids


OPERATIONS, MAIN_OPERATION_IDS, FILE_OPERATION_IDS = load_tool_manifest()

PICKER_BOOTSTRAP = r"""
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AudionDpiAwareness {
  [DllImport("user32.dll")]
  public static extern bool SetProcessDpiAwarenessContext(IntPtr dpiContext);
  [DllImport("shcore.dll")]
  public static extern int SetProcessDpiAwareness(int value);
}
"@
  try { [AudionDpiAwareness]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null }
  catch { [AudionDpiAwareness]::SetProcessDpiAwareness(2) | Out-Null }
} catch {}
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
"""

state: dict[str, Any] = {
    "running": False,
    "cancel": False,
    "progress": 0.0,
    "status": "",
    "lines": [],
    "log_version": 0,
    "terminal_sequence": 0,
    "terminal_reset_id": 0,
    "terminal_scroll_top_seq": 0,
    "exit_code": None,
    "source_path": "",
    "destination_path": "",
    "workspace_feedback": {},
    "active_module": "root",
    "command_screen": "main",
    "crop_pdf_screen": "main",
    "add_pdf_screen": "main",
}

DEFAULT_THEME_ID = "code_dark"
THEME_ALIASES = {"dark": "code_dark", "light": "code_light"}

DEFAULT_THEME_TOKENS: dict[str, str] = {
    "color-background-primary": "#141413",
    "color-background-secondary": "#1f1e1a",
    "color-background-tertiary": "#0f0f0e",
    "color-text-primary": "#faf9f5",
    "color-text-secondary": "#e8e6dc",
    "color-text-tertiary": "#b0aea5",
    "color-border-tertiary": "rgba(250, 249, 245, 0.15)",
    "color-border-secondary": "rgba(250, 249, 245, 0.3)",
    "color-border-primary": "rgba(250, 249, 245, 0.4)",
    "color-accent-primary": "#d97757",
    "font-sans": "Inter, Segoe UI, Arial, sans-serif",
    "font-mono": "Cascadia Mono, Consolas, monospace",
    "border-radius-md": "8px",
    "border-radius-lg": "12px",
}

DEFAULT_THEME_DATA: dict[str, Any] = {
    "label": "Code Dark",
    "label_ru": "Code Темная",
    "mode": "dark",
    "tokens": dict(DEFAULT_THEME_TOKENS),
}

settings: dict[str, Any] = {
    "language": "ru",
    "theme": DEFAULT_THEME_ID,
    "emoji": False,
    "source_path": "",
    "destination_path": "",
}


def display_path(path_value: Any) -> str:
    text = str(path_value or "").strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(ROOT)
    except (OSError, ValueError):
        return str(path)
    return str(relative) or "."


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip()}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_ui_colors(path: Path) -> dict[str, Any]:
    data = _load_yaml(path)
    themes: dict[str, dict[str, Any]] = {}
    themes_raw = data.get("themes", {})
    if not isinstance(themes_raw, dict):
        themes_raw = {}
    for theme_id, theme_data in themes_raw.items():
        if not isinstance(theme_data, dict):
            continue
        normalized_id = str(theme_id).strip().lower()
        if not normalized_id:
            continue
        themes[normalized_id] = {
            "label": str(theme_data.get("label") or normalized_id).strip(),
            "label_ru": str(theme_data.get("label_ru") or theme_data.get("label") or normalized_id).strip(),
            "mode": "dark" if str(theme_data.get("mode", "dark")).lower() == "dark" else "light",
            "tokens": _string_map(theme_data.get("tokens", {})),
        }
    if DEFAULT_THEME_ID not in themes:
        themes[DEFAULT_THEME_ID] = dict(DEFAULT_THEME_DATA)
    return {
        "ramps": data.get("ramps", {}) if isinstance(data.get("ramps", {}), dict) else {},
        "tokens": _string_map(data.get("tokens", {})),
        "themes": themes,
    }


ui_colors = load_ui_colors(UI_COLORS_PATH)


def normalize_theme_id(theme_id: Any) -> str:
    text = str(theme_id or DEFAULT_THEME_ID).strip().lower()
    cleaned = "".join(char for char in text if char.isalnum() or char in {"_", "-"})
    return THEME_ALIASES.get(cleaned, cleaned or DEFAULT_THEME_ID)


def active_theme() -> str:
    theme_id = normalize_theme_id(settings.get("theme", DEFAULT_THEME_ID))
    themes = ui_colors["themes"]
    if theme_id in themes:
        return theme_id
    return DEFAULT_THEME_ID if DEFAULT_THEME_ID in themes else next(iter(themes))


def active_theme_data() -> dict[str, Any]:
    return dict(ui_colors["themes"][active_theme()])


def active_theme_mode() -> str:
    return str(active_theme_data().get("mode", "dark"))


def theme_label(theme_id: str) -> str:
    theme_data = ui_colors["themes"].get(theme_id, {})
    label_key = "label_ru" if settings.get("language") == "ru" else "label"
    return str(theme_data.get(label_key) or theme_data.get("label") or theme_id)


def theme_options() -> dict[str, str]:
    return {theme_id: theme_label(theme_id) for theme_id in ui_colors["themes"]}


def theme_variables() -> dict[str, str]:
    variables: dict[str, str] = {}
    for ramp_name, stops in ui_colors["ramps"].items():
        if not isinstance(stops, dict):
            continue
        for stop, color in stops.items():
            variables[f"color-{ramp_name}-{stop}"] = str(color).strip()
    variables.update(DEFAULT_THEME_TOKENS)
    variables.update(ui_colors["tokens"])
    variables.update(_string_map(active_theme_data().get("tokens", {})))
    return variables


def set_theme(theme_id: Any) -> None:
    selected = normalize_theme_id(theme_id)
    if selected not in ui_colors["themes"]:
        return
    settings["theme"] = selected
    save_settings()
    safe_notify(tr("theme_saved"), type="positive")
    reload_ui()


def theme_change_handler(event: Any) -> None:
    set_theme(getattr(event, "value", None))


def load_settings() -> None:
    data = _load_yaml(GUI_SETTINGS_PATH)
    ui_data = data.get("gui", data) if isinstance(data, dict) else {}
    if not isinstance(ui_data, dict):
        ui_data = {}
    language = str(ui_data.get("language", settings["language"])).strip().lower()
    theme = normalize_theme_id(ui_data.get("theme", settings["theme"]))
    if language in {"ru", "en"}:
        settings["language"] = language
    settings["theme"] = theme if theme in ui_colors["themes"] else DEFAULT_THEME_ID
    settings["emoji"] = bool(ui_data.get("emoji", settings["emoji"]))
    settings["source_path"] = ""
    settings["destination_path"] = ""
    if not state.get("_workspace_initialized"):
        state["source_path"] = ""
        state["destination_path"] = ""
        state["_workspace_initialized"] = True


def save_settings() -> None:
    GUI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "gui:\n"
        "  # Change to \"en\" for public GitHub builds.\n"
        f"  language: {json.dumps(str(settings['language']), ensure_ascii=False)}\n"
        f"  theme: {json.dumps(str(active_theme()), ensure_ascii=False)}\n"
        f"  emoji: {str(bool(settings['emoji'])).lower()}\n"
        "  allow_runtime_switching: true\n"
        "  advanced_open: false\n"
        f"  source_path: {json.dumps("", ensure_ascii=False)}\n"
        f"  destination_path: {json.dumps("", ensure_ascii=False)}\n"
    )
    GUI_SETTINGS_PATH.write_text(text, encoding="utf-8", newline="\n")


def reload_ui() -> None:
    ui.run_javascript(
        """
        (() => {
          try {
            if ('scrollRestoration' in window.history) {
              window.history.scrollRestoration = 'manual';
            }
            window.sessionStorage.setItem('audion_force_scroll_top', '1');
            window.scrollTo(0, 0);
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
          } catch (error) {}
          window.location.reload();
        })();
        """
    )


def tr(key: str, **kwargs: Any) -> str:
    text = TRANSLATIONS.get(settings["language"], TRANSLATIONS["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text


def safe_notify(message: str, kind: str = "info", **notify_kwargs: Any) -> None:
    notify_type = str(notify_kwargs.pop("type", kind))
    options = {"message": str(message), "type": notify_type, **notify_kwargs}
    delivered = False
    for client in list(nicegui_app.clients()):
        if getattr(client, "_deleted", False) or not client.has_socket_connection:
            continue
        try:
            client.outbox.enqueue_message("notify", options, client.id)
            delivered = True
        except Exception as exc:
            logging.warning("NiceGUI notification delivery failed for client %s: %s", getattr(client, "id", "?"), exc)
    if delivered:
        return

    try:
        ui.notify(message, type=notify_type, **notify_kwargs)
    except RuntimeError as exc:
        message_text = str(exc)
        if "slot belongs to has been deleted" not in message_text and "current slot cannot be determined" not in message_text:
            raise
        logging.warning("NiceGUI notification skipped because no live client slot was available: %s", message)


def notify_operation_result(exit_code: int) -> None:
    safe_notify(
        tr("operation_done") if exit_code == 0 else tr("operation_failed", code=exit_code),
        type="positive" if exit_code == 0 else "negative",
    )


def page_number_position_options() -> dict[str, str]:
    if settings["language"] == "ru":
        return {
            "bottom-right": "снизу справа",
            "bottom-center": "снизу по центру",
            "bottom-left": "снизу слева",
            "top-right": "сверху справа",
            "top-center": "сверху по центру",
            "top-left": "сверху слева",
        }
    return {
        "bottom-right": "bottom right",
        "bottom-center": "bottom center",
        "bottom-left": "bottom left",
        "top-right": "top right",
        "top-center": "top center",
        "top-left": "top left",
    }


def em(key: str) -> str:
    if not bool(settings.get("emoji", False)):
        return ""
    return {
        "workspace": "📁 ",
        "operations": "⚙ ",
        "conversion": "🔁 ",
        "crop_pdf": "✂️ ",
        "add_pdf": "🛠️ ",
        "status": "● ",
        "log": "🖥 ",
    }.get(key, "")


def op_text(operation_id: str, field: str) -> str:
    operation = OPERATIONS[operation_id]
    return str(operation.get(f"{field}_{settings['language']}") or operation.get(f"{field}_en") or operation_id)


def localized_text(item: dict[str, Any], field: str) -> str:
    return str(item.get(f"{field}_{settings['language']}") or item.get(f"{field}_en") or item.get(field) or "")


def ensure_dirs() -> None:
    for folder in [*FOLDERS.values(), ROOT / "config"]:
        folder.mkdir(parents=True, exist_ok=True)


def add_log(message: str) -> None:
    if message == "":
        return
    line = message.rstrip("\r\n")
    state["lines"].append(line)
    state["lines"] = state["lines"][-TERMINAL_HISTORY_LIMIT:]
    state["terminal_sequence"] = int(state.get("terminal_sequence") or 0) + 1
    state["log_version"] = int(state["log_version"]) + 1
    plain_line = strip_ansi(line)
    match = PROGRESS_RE.search(plain_line)
    if match and plain_line.startswith(("[OK]", "[FAIL]")):
        index = int(match.group(1))
        total = max(1, int(match.group(2)))
        state["progress"] = max(float(state["progress"]), min(0.98, index / total))


def terminal_html() -> str:
    return render_terminal_html(str(line) for line in state["lines"])


def reset_terminal_state() -> None:
    state["lines"] = []
    state["terminal_sequence"] = 0
    state["log_version"] = int(state["log_version"]) + 1


def clear_terminal_log() -> None:
    reset_terminal_state()


def unbuffer_python_command(command: list[str]) -> list[str]:
    if not command:
        return command
    if not is_python_command(command):
        return command
    if len(command) > 1 and command[1] == "-u":
        return command
    return [command[0], "-u", *command[1:]]


def gui_cli_python() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        console_python = executable.with_name("python.exe")
        if console_python.exists():
            return str(console_python)
    return str(executable)


def progress_text() -> str:
    return f"{round(max(0.0, min(1.0, float(state['progress']))) * 100):.0f}%"


def status_dot_classes() -> str:
    base = "audion-status-dot text-lg leading-none"
    if bool(state["running"]):
        return f"{base} text-sky-400 animate-pulse"
    if state.get("exit_code") is None:
        return f"{base} text-gray-500"
    if int(state.get("exit_code") or 0) == 0:
        return f"{base} text-green-400"
    return f"{base} text-red-400"


def hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def hidden_subprocess_flags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def hidden_subprocess_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    startupinfo = hidden_startupinfo()
    if startupinfo is not None:
        kwargs["startupinfo"] = startupinfo
    creationflags = hidden_subprocess_flags()
    if creationflags:
        kwargs["creationflags"] = creationflags
    return kwargs


def resolve_dialog_powershell() -> list[str]:
    candidates = [
        [str(ROOT / "system_core" / "powershell" / "pwsh.exe"), "-NoLogo", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-Command"],
        ["pwsh.exe", "-NoLogo", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-Command"],
        ["powershell.exe", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command"],
    ]
    for candidate in candidates:
        exe = candidate[0]
        if Path(exe).exists() or shutil.which(exe):
            return candidate
    raise RuntimeError("PowerShell was not found for Windows picker.")


_PICKER_RUN_LOCK = threading.Lock()
_PICKER_JOB_LOCK = threading.Lock()
_PICKER_SHUTDOWN = threading.Event()
_PICKER_JOB_HANDLE: int | None = None


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def close_picker_job() -> None:
    global _PICKER_JOB_HANDLE
    _PICKER_SHUTDOWN.set()
    with _PICKER_JOB_LOCK:
        handle = _PICKER_JOB_HANDLE
        _PICKER_JOB_HANDLE = None
    if os.name == "nt" and handle:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(wintypes.HANDLE(handle))


def _picker_job_handle() -> int | None:
    global _PICKER_JOB_HANDLE
    if os.name != "nt" or _PICKER_SHUTDOWN.is_set():
        return None
    with _PICKER_JOB_LOCK:
        if _PICKER_SHUTDOWN.is_set():
            return None
        if _PICKER_JOB_HANDLE:
            return _PICKER_JOB_HANDLE
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            logging.warning("Could not create the Windows picker job: %s", ctypes.get_last_error())
            return None
        info = _JobObjectExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = 0x00002000
        configured = kernel32.SetInformationJobObject(
            wintypes.HANDLE(job),
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not configured:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(wintypes.HANDLE(job))
            logging.warning("Could not configure the Windows picker job: %s", error)
            return None
        _PICKER_JOB_HANDLE = int(job)
        return _PICKER_JOB_HANDLE


def _assign_picker_to_job(process: subprocess.Popen[str]) -> None:
    handle = _picker_job_handle()
    if os.name != "nt" or not handle:
        if _PICKER_SHUTDOWN.is_set() and process.poll() is None:
            process.kill()
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    assigned = kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(handle),
        wintypes.HANDLE(int(process._handle)),  # type: ignore[attr-defined]
    )
    if not assigned:
        logging.warning("Could not attach picker PID %s to its Windows job: %s", process.pid, ctypes.get_last_error())


def run_picker_script(script: str, error_message: str) -> list[Path]:
    if not _PICKER_RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("A Windows picker is already open.")
    process: subprocess.Popen[str] | None = None
    try:
        if _PICKER_SHUTDOWN.is_set():
            raise RuntimeError("Windows picker supervisor is shutting down.")
        _picker_job_handle()
        process = subprocess.Popen(
            [*resolve_dialog_powershell(), script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
        _assign_picker_to_job(process)
        if _PICKER_SHUTDOWN.is_set():
            if process.poll() is None:
                process.kill()
            raise RuntimeError("Windows picker supervisor is shutting down.")
        try:
            stdout, stderr = process.communicate(timeout=3600)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise RuntimeError("Windows picker timed out.") from exc
        if process.returncode != 0:
            raise RuntimeError(stderr.strip() or error_message)
        return parse_picker_paths(stdout)
    finally:
        if process is not None and process.poll() is None:
            process.kill()
        _PICKER_RUN_LOCK.release()


atexit.register(close_picker_job)
nicegui_app.on_shutdown(close_picker_job)


def pick_single_file() -> list[Path]:
    script = PICKER_BOOTSTRAP + r"""
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'Select one source file'
$dialog.Multiselect = $false
$dialog.Filter = 'Office and PDF files|*.doc;*.docx;*.docm;*.rtf;*.txt;*.odt;*.xls;*.xlsx;*.xlsm;*.xlsb;*.csv;*.ods;*.ppt;*.pptx;*.pptm;*.odp;*.pdf|All files|*.*'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  @($dialog.FileName) | ConvertTo-Json -Compress
}
"""
    return run_picker_script(script, "File picker failed.")


def pick_folder(title: str = "Select folder") -> list[Path]:
    safe_title = title.replace("'", "''")
    script = PICKER_BOOTSTRAP + """
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '__AUDION_FOLDER_DIALOG_TITLE__'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  @($dialog.SelectedPath) | ConvertTo-Json -Compress
}
""".replace("__AUDION_FOLDER_DIALOG_TITLE__", safe_title)
    return run_picker_script(script, "Folder picker failed.")


def parse_picker_paths(text: str) -> list[Path]:
    import json

    payload = text.strip()
    if not payload:
        return []
    data = json.loads(payload)
    if isinstance(data, str):
        data = [data]
    return [Path(str(item)).resolve() for item in data if str(item).strip()]


def input_file_list_lines(source: Path) -> list[str]:
    if not source.exists():
        return [tr("file_list_missing", path=source)]
    if source.is_file():
        return ["No.  Size  List", f"001  {source.stat().st_size}  {source.name}"]
    if not source.is_dir():
        return [f"Unsupported source path: {source}"]

    names = sorted(
        (path.name for path in source.rglob("*") if path.is_file()),
        key=lambda item: item.casefold(),
    )
    if not names:
        return [tr("file_list_empty")]

    number_width = max(3, len(str(len(names))))
    lines = [
        f"{'No.':>{number_width}}  List",
        f"{'-' * number_width}  ----",
    ]
    lines.extend(f"{index:0{number_width}d}. {name}" for index, name in enumerate(names, start=1))
    return lines


async def show_input_file_list() -> None:
    if state["running"]:
        safe_notify(tr("another_running"), type="warning")
        return

    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {tr('file_list')}",
            "lines": [],
            "terminal_sequence": 0,
            "terminal_reset_id": int(state.get("terminal_reset_id", 0)) + 1,
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )
    try:
        lines = await run.io_bound(input_file_list_lines, current_source_path())
        for line in lines:
            add_log(line)
        count = max(0, len(lines) - 2)
        state["terminal_scroll_top_seq"] = int(state.get("terminal_sequence", 0))
        state["exit_code"] = 0
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {tr('file_list')} [{count}]"
        safe_notify(tr("file_list_ready", count=count), type="positive")
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), type="negative")
    finally:
        state["running"] = False


def build_option_args(operation: dict[str, Any], option_values: dict[str, list[str]] | None) -> list[str]:
    if not option_values:
        return []

    args: list[str] = []
    for group in operation.get("option_groups", []):
        if group.get("type") != "checkboxes":
            continue
        selected_ids = set(option_values.get(str(group["id"]), []))
        selected_values = [
            str(choice["value"])
            for choice in group.get("choices", [])
            if str(choice["id"]) in selected_ids
        ]
        min_selected = int(group.get("min_selected", 0) or 0)
        if len(selected_values) < min_selected:
            raise ValueError(tr("no_options_selected"))
        if not selected_values:
            continue
        args.extend(group.get("args_prefix", []))
        separator = str(group.get("separator", ","))
        if separator:
            args.append(separator.join(selected_values))
        else:
            args.extend(selected_values)
    return args


def build_command(operation_id: str, file_path: str, option_values: dict[str, list[str]] | None = None) -> list[str]:
    operation = OPERATIONS[operation_id]
    cmd = [gui_cli_python(), "-u", *operation["args"]]
    cmd.extend(build_option_args(operation, option_values))
    language_args = operation.get("language_args", {})
    if isinstance(language_args, dict):
        cmd.extend(language_args.get(settings["language"], []))
    if operation.get("needs_file"):
        cleaned = file_path.strip().strip('"')
        if not cleaned:
            raise ValueError(tr("file_required"))
        cmd.append(cleaned)
    if operation_id in {"crop_pptx", "crop_pptx_force"}:
        cmd.extend(["--output-dir", str(current_target_path().resolve(strict=False))])
    return cmd


def validate_folder_field(raw_path: str, required_message: str) -> Path:
    cleaned = raw_path.strip().strip('"')
    if not cleaned:
        raise ValueError(required_message)
    path = Path(cleaned).expanduser().resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(f"{tr('folder_only')}: {path}")
    return path


def build_convert_command(
    source_dir: str,
    destination_dir: str,
    option_values: dict[str, list[str]] | None = None,
    post_crop: str = "none",
    post_scale_percent: float = 100.0,
) -> list[str]:
    source_text = source_dir.strip().strip('"')
    if not source_text:
        raise ValueError(tr("source_required"))
    source = Path(source_text).expanduser().resolve()
    destination = validate_folder_field(destination_dir, tr("destination_required"))
    if not source.exists():
        raise ValueError(f"{tr('source_required')}: {source}")

    operation = OPERATIONS["batch_recursive"]
    if source.is_file():
        # Preserve the same format-selection validation as the batch screen, while
        # routing one explicitly selected Office document through the CLI file mode.
        build_option_args(operation, option_values)
        cmd = [
            gui_cli_python(),
            "-u",
            str(MAIN_PY),
            "file",
            "--input",
            str(source),
            "--input-root",
            str(source.parent),
            "--output-dir",
            str(destination),
        ]
        if post_crop != "none":
            cmd.extend(["--post-crop", post_crop])
        if post_scale_percent < 100.0:
            cmd.extend(["--post-scale-percent", str(post_scale_percent)])
        return cmd
    if not source.is_dir():
        raise ValueError(f"{tr('folder_only')}: {source}")

    cmd = [
        gui_cli_python(),
        "-u",
        str(MAIN_PY),
        "batch",
        "--recursive",
        "--input-dir",
        str(source),
        "--output-dir",
        str(destination),
    ]
    cmd.extend(build_option_args(operation, option_values))
    if post_crop != "none":
        cmd.extend(["--post-crop", post_crop])
    if post_scale_percent < 100.0:
        cmd.extend(["--post-scale-percent", str(post_scale_percent)])
    return cmd


def pdf_workspace_cli_args() -> list[str]:
    return [
        "--input-dir",
        str(current_source_path().resolve(strict=False)),
        "--output-dir",
        str(current_target_path().resolve(strict=False)),
    ]


def run_process_command(cmd: list[str]) -> int:
    cmd = unbuffer_python_command(cmd)
    rendered = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    add_log("RUN: " + rendered)

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("NO_COLOR", None)
    if env.get("CLICOLOR") == "0":
        env.pop("CLICOLOR", None)
    env["CLICOLOR"] = "1"
    env["CLICOLOR_FORCE"] = "1"
    env["FORCE_COLOR"] = "1"
    env["AUDION_GUI_TERMINAL"] = "1"

    if not is_python_command(cmd):
        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            **hidden_subprocess_kwargs(),
        )
        assert process.stdout is not None
        for raw_line in process.stdout:
            if state["cancel"]:
                process.terminate()
                add_log("Cancellation requested.")
                break
            for line in decoded_process_lines(raw_line):
                add_log(line)
        return process.wait()

    process = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        **hidden_subprocess_kwargs(),
    )

    assert process.stdout is not None
    for line in process.stdout:
        if state["cancel"]:
            process.terminate()
            add_log("Cancellation requested.")
            break
        for decoded_line in decoded_process_lines(line):
            add_log(decoded_line)

    return process.wait()


def run_cli_operation(
    operation_id: str,
    file_path: str,
    option_values: dict[str, list[str]] | None = None,
) -> int:
    cmd = build_command(operation_id, file_path, option_values)
    return run_process_command(cmd)


def run_convert_operation(
    source_dir: str,
    destination_dir: str,
    option_values: dict[str, list[str]] | None = None,
    post_crop: str = "none",
    post_scale_percent: float = 100.0,
) -> int:
    cmd = build_convert_command(source_dir, destination_dir, option_values, post_crop, post_scale_percent)
    return run_process_command(cmd)


async def start_operation(
    operation_id: str,
    file_path: str = "",
    option_values: dict[str, list[str]] | None = None,
) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), type="warning")
        return

    operation_title = op_text(operation_id, "title")
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {operation_title}",
            "lines": [],
            "terminal_sequence": 0,
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )

    started = time.perf_counter()
    try:
        exit_code = await run.io_bound(run_cli_operation, operation_id, file_path, option_values)
        elapsed = time.perf_counter() - started
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {op_text(operation_id, 'title')} [{exit_code}] {elapsed:.1f}s"
        notify_operation_result(exit_code)
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), type="negative")
    finally:
        state["running"] = False


async def start_convert_operation(
    source_dir: str,
    destination_dir: str,
    option_values: dict[str, list[str]] | None = None,
    post_crop: str = "none",
    post_scale_percent: float = 100.0,
) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), type="warning")
        return

    operation_title = tr("convert_mode")
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {operation_title}",
            "lines": [],
            "terminal_sequence": 0,
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )

    started = time.perf_counter()
    try:
        exit_code = await run.io_bound(
            run_convert_operation,
            source_dir,
            destination_dir,
            option_values,
            post_crop,
            post_scale_percent,
        )
        elapsed = time.perf_counter() - started
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {operation_title} [{exit_code}] {elapsed:.1f}s"
        notify_operation_result(exit_code)
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), type="negative")
    finally:
        state["running"] = False


async def start_raw_cli_operation(title: str, cmd: list[str]) -> None:
    if state["running"]:
        safe_notify(tr("another_running"), type="warning")
        return
    state.update(
        {
            "running": True,
            "cancel": False,
            "progress": 0.02,
            "status": f"{tr('running')}: {title}",
            "lines": [],
            "terminal_sequence": 0,
            "log_version": int(state["log_version"]) + 1,
            "exit_code": None,
        }
    )
    started = time.perf_counter()
    try:
        exit_code = await run.io_bound(run_process_command, cmd)
        elapsed = time.perf_counter() - started
        state["exit_code"] = exit_code
        state["progress"] = 1.0
        state["status"] = f"{tr('done')}: {title} [{exit_code}] {elapsed:.1f}s"
        notify_operation_result(exit_code)
    except Exception as exc:
        state["exit_code"] = 1
        state["progress"] = max(float(state["progress"]), 0.98)
        state["status"] = f"{tr('error')}: {exc}"
        add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
        safe_notify(str(exc), type="negative")
    finally:
        state["running"] = False


def current_source_path() -> Path:
    return Path(str(state.get("source_path") or FOLDERS["input"])).expanduser()


def current_target_path() -> Path:
    return Path(str(state.get("destination_path") or FOLDERS["output"])).expanduser()


def default_workspace_path(role: str) -> Path:
    return FOLDERS["output"] if canonical_role(role) == "target" else FOLDERS["input"]


def save_workspace_path(kind: str, value: Any) -> None:
    raw_text = str(value or "").strip()
    text = str(Path(raw_text).expanduser()) if raw_text else str(default_workspace_path(kind))
    if canonical_role(kind) == "target":
        state["destination_path"] = text
    else:
        state["source_path"] = text
    settings["source_path"] = ""
    settings["destination_path"] = ""
    save_settings()


def open_workspace_folder(role: str) -> None:
    folder = current_target_path() if role == "target" else current_source_path()
    if role != "target" and not folder.exists():
        raise FileNotFoundError(str(folder))
    if folder.is_file():
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", f"/select,{folder}"])
        else:
            open_folder(folder.parent)
        return
    if role == "target":
        folder.mkdir(parents=True, exist_ok=True)
    open_folder(folder)


def mark_workspace_feedback(role: str, action: str) -> None:
    state["workspace_feedback"] = {"role": canonical_role(role), "action": str(action or "path")}


def _save_workbench_path(role: WorkbenchRole, value: Any) -> None:
    save_workspace_path("target" if role == "target" else "source", value)


def _workspace_feedback() -> dict[str, str]:
    value = state.get("workspace_feedback")
    return dict(value) if isinstance(value, dict) else {}


def _clear_workspace_feedback() -> None:
    state["workspace_feedback"] = {}


def absolute_project_path(path_value: Any) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


def normalized_absolute_path(path_value: Any) -> Path:
    return absolute_project_path(path_value).resolve(strict=False)


def paths_equal(left: Any, right: Any) -> bool:
    return os.path.normcase(str(normalized_absolute_path(left))) == os.path.normcase(str(normalized_absolute_path(right)))


def remove_path_tree(path: Path) -> int:
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(path))
    if path.is_symlink() or is_junction:
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()
        return 1
    if path.is_file():
        path.unlink()
        return 1
    if path.is_dir():
        shutil.rmtree(path)
        return 1
    return 0


def clear_directory_contents(folder: Path) -> int:
    removed = 0
    if not folder.exists():
        return removed
    for child in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
        # .gitkeep is not spared: input and output must be genuinely empty after
        # a clear, so nobody has to wonder what the leftover file is or whether it
        # is safe to delete. The folders come from install/init_folders.cmd.
        removed += remove_path_tree(child)
    return removed


def validate_workspace_delete_target(path_value: Any) -> Path:
    target = normalized_absolute_path(path_value)
    if target.parent == target:
        raise RuntimeError(f"Refusing to delete a filesystem root: {target}")
    if paths_equal(target, ROOT):
        raise RuntimeError(f"Refusing to delete the project root: {target}")
    return target


def delete_workspace_path_contents(path_value: Any) -> dict[str, Any]:
    target = validate_workspace_delete_target(path_value)
    if not target.exists() and not target.is_symlink():
        return {"path": str(target), "kind": "missing", "removed": 0}
    is_junction = bool(getattr(os.path, "isjunction", lambda _path: False)(target))
    if target.is_file() or target.is_symlink() or is_junction:
        return {"path": str(target), "kind": "file", "removed": remove_path_tree(target)}
    if not target.is_dir():
        raise RuntimeError(f"Unsupported workspace path: {target}")
    return {"path": str(target), "kind": "folder", "removed": clear_directory_contents(target)}


def delete_workspace_io_contents(source: Path, target: Path) -> dict[str, Any]:
    source_result = delete_workspace_path_contents(source)
    if paths_equal(source, target):
        target_result = {"path": str(normalized_absolute_path(target)), "kind": "same", "removed": 0}
    else:
        target_result = delete_workspace_path_contents(target)
    return {"source": source_result, "target": target_result}


WORKBENCH_CONFIG = WorkbenchConfig(
    root=ROOT,
    input_path=FOLDERS["input"],
    output_path=FOLDERS["output"],
    history_path=FOLDERS["config"] / "path_history.json",
    history_limit=PATH_HISTORY_LIMIT,
)
WORKBENCH_ADAPTER = WorkbenchAdapter(
    config=WORKBENCH_CONFIG,
    current_path_callback=lambda role: current_target_path() if role == "target" else current_source_path(),
    save_path_callback=_save_workbench_path,
    language_callback=lambda: str(settings["language"]),
    translate_callback=tr,
    log_callback=add_log,
    notify_callback=safe_notify,
    reload_callback=lambda _delay=0: reload_ui(),
    busy_callback=lambda: bool(state.get("running")),
    feedback_callback=_workspace_feedback,
    set_feedback_callback=mark_workspace_feedback,
    clear_feedback_callback=_clear_workspace_feedback,
)
WORKBENCH_ADAPTER.validate()
WORKBENCH_ADAPTER.ensure_initial_history()
if not WORKBENCH_ADAPTER.history_entries("source"):
    WORKBENCH_ADAPTER.remember_path("source", str(FOLDERS["input"]))
if not WORKBENCH_ADAPTER.history_entries("target"):
    WORKBENCH_ADAPTER.remember_path("target", str(FOLDERS["output"]))


def canonical_workspace_pin_click_handler(role: str, pinned: bool):
    async def handler() -> None:
        path_value = str(current_target_path() if role == "target" else current_source_path())
        if not path_value:
            safe_notify(tr("path_required"), type="warning")
            return
        try:
            await run.io_bound(WORKBENCH_ADAPTER.set_path_pinned, role, path_value, pinned)
            mark_workspace_feedback(role, "pin" if pinned else "unpin")
            add_log(f"{'Pinned' if pinned else 'Unpinned'} {role} path: {path_value}")
            reload_ui()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), type="negative")

    return handler


def canonical_workspace_delete_path_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), type="warning")
            return
        path = current_target_path() if role == "target" else current_source_path()
        path_value = str(path)
        if not path_value:
            safe_notify(tr("path_required"), type="warning")
            return
        external_source = role != "target" and not paths_equal(path, FOLDERS["input"])
        if external_source:
            is_file = path.is_file()
            with ui.dialog() as dialog, ui.card().classes("rounded-lg"):
                title = "Удалить исходный файл?" if is_file else "Очистить внешний ИСТОЧНИК?"
                if settings["language"] != "ru":
                    title = "Delete the source file?" if is_file else "Clear the external SOURCE?"
                ui.label(title).classes("text-base font-semibold")
                warning = (
                    "Будет удалён исходный файл. Другой копии может не существовать."
                    if is_file
                    else "Будут безвозвратно удалены все файлы и вложенные папки."
                )
                if settings["language"] != "ru":
                    warning = (
                        "The source file will be deleted. Another copy may not exist."
                        if is_file
                        else "All files and nested folders will be permanently deleted."
                    )
                ui.label(warning).classes("text-sm text-gray-300")
                ui.label(str(normalized_absolute_path(path))).classes("max-w-3xl break-all font-mono text-xs text-gray-400")
                with ui.row().classes("gap-2"):
                    ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                    ui.button(tr("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
            if not await dialog:
                return
        try:
            result = await run.io_bound(delete_workspace_path_contents, path)
            if result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, role, path_value)
                save_workspace_path("target" if role == "target" else "source", "")
            mark_workspace_feedback(role, "delete")
            add_log(
                f"Cleared {'TARGET' if role == 'target' else 'SOURCE'}: {result.get('path')} "
                f"[kind={result.get('kind')}, removed={result.get('removed', 0)}]"
            )
            reload_ui()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), type="negative")

    return handler


def canonical_workspace_path_select_handler(role: str):
    async def handler(event: Any) -> None:
        path_value = str(getattr(event, "value", "") or "").strip()
        if not path_value:
            return
        save_workspace_path("target" if role == "target" else "source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role, path_value)
        mark_workspace_feedback(role, "path")
        add_log(f"{'TARGET' if role == 'target' else 'SOURCE'} -> {path_value}")
        reload_ui()

    return handler


def canonical_workspace_pick_click_handler(role: str):
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), type="warning")
            return
        try:
            selected = await run.io_bound(pick_folder, tr("target_folder") if role == "target" else tr("source_folder"))
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), type="negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path("target" if role == "target" else "source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, role, path_value)
        mark_workspace_feedback(role, "path")
        add_log(f"{'TARGET' if role == 'target' else 'SOURCE'} -> {path_value}")
        reload_ui()

    return handler


def canonical_workspace_open_click_handler(role: str):
    async def handler() -> None:
        try:
            await run.io_bound(open_workspace_folder, role)
            current = current_target_path() if role == "target" else current_source_path()
            add_log(f"Opened {'target' if role == 'target' else 'source'} folder: {current}")
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), type="negative")

    return handler


def canonical_workspace_single_file_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), type="warning")
            return
        try:
            selected = await run.io_bound(pick_single_file)
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), type="negative")
            return
        if not selected:
            add_log(tr("picker_cancelled"))
            return
        path_value = str(selected[0])
        save_workspace_path("source", path_value)
        await run.io_bound(WORKBENCH_ADAPTER.remember_path, "source", path_value)
        mark_workspace_feedback("source", "path")
        add_log(f"SOURCE FILE -> {path_value}")
        reload_ui()

    return handler


def canonical_reset_workspace_paths_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), type="warning")
            return
        result = await run.io_bound(WORKBENCH_ADAPTER.clear_path_history_cache_keep_pins)
        save_workspace_path("source", "")
        save_workspace_path("target", "")
        add_log(f"Workspace route reset: SOURCE -> {FOLDERS['input']}")
        add_log(f"Workspace route reset: TARGET -> {FOLDERS['output']}")
        add_log(
            "Workspace path cache cleared: "
            f"sources={result.get('removed_sources', 0)}, targets={result.get('removed_targets', 0)}, "
            f"pins kept={result.get('kept_pins', 0)}"
        )
        safe_notify(tr("operation_done"), type="positive")
        reload_ui()

    return handler


def canonical_workspace_delete_both_click_handler():
    async def handler() -> None:
        if state["running"]:
            safe_notify(tr("another_running"), type="warning")
            return
        source = current_source_path()
        target = current_target_path()
        source_external = not paths_equal(source, FOLDERS["input"])
        with ui.dialog() as dialog, ui.card().classes("rounded-lg"):
            ui.label("Удалить содержимое I/O?" if settings["language"] == "ru" else "Delete I/O contents?").classes("text-base font-semibold")
            warning = (
                "Будут удалены файлы ИСТОЧНИКА и НАЗНАЧЕНИЯ. Внешний ИСТОЧНИК может быть единственным экземпляром."
                if source_external
                else "Будут удалены файлы ИСТОЧНИКА и НАЗНАЧЕНИЯ."
            )
            if settings["language"] != "ru":
                warning = (
                    "SOURCE and TARGET files will be deleted. The external SOURCE may be the only copy."
                    if source_external
                    else "SOURCE and TARGET files will be deleted."
                )
            ui.label(warning).classes("text-sm text-gray-300")
            ui.label(f"SOURCE: {normalized_absolute_path(source)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            ui.label(f"TARGET: {normalized_absolute_path(target)}").classes("max-w-3xl break-all font-mono text-xs text-gray-400")
            with ui.row().classes("gap-2"):
                ui.button(tr("cancel"), on_click=dialog.close).props("dense flat")
                ui.button(tr("delete_io_short"), on_click=lambda: dialog.submit(True)).props("dense color=negative")
        if not await dialog:
            return
        state["running"] = True
        try:
            result = await run.io_bound(delete_workspace_io_contents, source, target)
            source_result = result.get("source", {})
            target_result = result.get("target", {})
            if source_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "source", str(source))
                save_workspace_path("source", "")
            if target_result.get("kind") == "file":
                await run.io_bound(WORKBENCH_ADAPTER.delete_path_history, "target", str(target))
                save_workspace_path("target", "")
            add_log(f"Cleared SOURCE: {source_result.get('path')} [kind={source_result.get('kind')}, removed={source_result.get('removed', 0)}]")
            add_log(f"Cleared TARGET: {target_result.get('path')} [kind={target_result.get('kind')}, removed={target_result.get('removed', 0)}]")
            mark_workspace_feedback("source", "delete")
            reload_ui()
        except Exception as exc:
            add_log(f"ERROR: {exc.__class__.__name__}: {exc}")
            safe_notify(str(exc), type="negative")
        finally:
            state["running"] = False

    return handler


WORKBENCH_RENDERER = WorkbenchRenderer(
    adapter=WORKBENCH_ADAPTER,
    handlers=WorkbenchHandlers(
        delete_path=canonical_workspace_delete_path_click_handler,
        pin_path=canonical_workspace_pin_click_handler,
        select_path=canonical_workspace_path_select_handler,
        pick_path=canonical_workspace_pick_click_handler,
        open_path=canonical_workspace_open_click_handler,
        add_file=canonical_workspace_single_file_click_handler,
        reset_paths=canonical_reset_workspace_paths_click_handler,
        delete_io=canonical_workspace_delete_both_click_handler,
        list_files=show_input_file_list,
    ),
    display_path_callback=display_path,
)


async def choose_operation_options(operation_id: str, file_path: str = "") -> None:
    operation = OPERATIONS[operation_id]
    groups = operation.get("option_groups", [])
    if not groups:
        await start_operation(operation_id, file_path)
        return

    group_controls: dict[str, dict[str, Any]] = {}

    with ui.dialog() as dialog, ui.card().classes("w-[520px] max-w-[92vw] rounded-lg p-4").style("background: var(--audion-panel-bg);"):
        ui.label(f"{tr('choose_options')}: {op_text(operation_id, 'title')}").classes("text-base font-semibold")
        for group in groups:
            group_id = str(group["id"])
            group_controls[group_id] = {}
            with ui.column().classes("w-full gap-1 border-t border-gray-800 pt-3"):
                ui.label(localized_text(group, "title")).classes("text-sm font-semibold")
                description = localized_text(group, "description")
                if description:
                    ui.label(description).classes("text-xs text-gray-400")
                with ui.row().classes("w-full flex-wrap gap-4 pt-1"):
                    for choice in group.get("choices", []):
                        checkbox = ui.checkbox(
                            localized_text(choice, "label"),
                            value=bool(choice.get("default", False)),
                        ).props("dense")
                        group_controls[group_id][str(choice["id"])] = checkbox

        def submit_options() -> None:
            selected: dict[str, list[str]] = {}
            for group in groups:
                group_id = str(group["id"])
                ids = [
                    choice_id
                    for choice_id, checkbox in group_controls.get(group_id, {}).items()
                    if bool(checkbox.value)
                ]
                if len(ids) < int(group.get("min_selected", 0) or 0):
                    safe_notify(tr("no_options_selected"), type="warning")
                    return
                selected[group_id] = ids
            dialog.submit(selected)

        with ui.row().classes("w-full justify-end gap-2 pt-3"):
            ui.button(tr("back"), on_click=dialog.close).props("dense flat")
            ui.button(tr("run"), on_click=submit_options).props("dense flat no-wrap").classes("audion-action audion-nav-run-button rounded-lg")

    selected_options = await dialog
    if selected_options is None:
        return
    await start_operation(operation_id, file_path, selected_options)


def open_folder(folder_id: str | Path) -> None:
    folder = FOLDERS[folder_id] if isinstance(folder_id, str) and folder_id in FOLDERS else Path(folder_id)
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(folder))  # type: ignore[attr-defined]
        return
    webbrowser.open(folder.as_uri())


def operation_button(operation_id: str, file_input: Any | None = None) -> None:
    with ui.element("div").classes("audion-operation-row"):
        ui.button(
            op_text(operation_id, "title"),
            on_click=lambda op=operation_id: choose_operation_options(op, str(file_input.value if file_input else "")),
        ).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        ui.label(op_text(operation_id, "description")).classes("audion-operation-description")


def set_active_module(module_id: str) -> None:
    state["active_module"] = module_id
    if module_id == "root":
        state["command_screen"] = "main"
        state["crop_pdf_screen"] = "main"
        state["add_pdf_screen"] = "main"
    elif module_id == "conversion":
        state["command_screen"] = "convert_custom"
    elif module_id == "crop_pdf":
        state["crop_pdf_screen"] = "main"
    elif module_id == "crop_pptx":
        state["crop_pdf_screen"] = "pptx"
    elif module_id == "crop_manual":
        state["crop_pdf_screen"] = "manual"
    elif module_id == "add_pdf":
        state["add_pdf_screen"] = "main"
    elif module_id == "page_numbers":
        state["add_pdf_screen"] = "page_numbers"
    elif module_id == "scale_pdf":
        state["add_pdf_screen"] = "scale"
    operations_area.refresh()


def set_command_screen(screen: str) -> None:
    state["command_screen"] = screen
    operations_area.refresh()


def set_crop_pdf_screen(screen: str) -> None:
    state["crop_pdf_screen"] = screen
    state["active_module"] = "root" if screen == "main" else "crop_pdf"
    operations_area.refresh()


def set_add_pdf_screen(screen: str) -> None:
    state["add_pdf_screen"] = screen
    state["active_module"] = "root" if screen == "main" else "add_pdf"
    operations_area.refresh()


def command_row(label: str, description: str, on_click: Any) -> None:
    with ui.element("div").classes("audion-operation-row"):
        ui.button(label, on_click=on_click).props("dense flat no-wrap").classes("audion-action audion-operation-button rounded-lg")
        ui.label(description).classes("audion-operation-description")


def module_description(module_id: str) -> str:
    ru = settings["language"] == "ru"
    descriptions = {
        "conversion": (
            "Конвертировать Office-файлы из текущего Source в Target с фильтром форматов и постобработкой.",
            "Convert Office files from the current Source to Target with format filters and post-processing.",
        ),
        "crop_pdf": (
            "Выберите обрезку презентационных PDF в Target либо обработку PDF по маршруту Source → Target.",
            "Choose PowerPoint PDF crop in Target or process PDFs through the Source → Target route.",
        ),
        "crop_pptx": (
            "Обрезать PDF из PowerPoint в текущем Target до точных 16:9; результат обновляется там же.",
            "Crop PowerPoint-exported PDFs in the current Target to exact 16:9 in place.",
        ),
        "crop_manual": (
            "Разрезать PDF 50/50, кадрировать под 16:9/A4/A3 или обрезать поля. Маршрут: Source → Target.",
            "Split PDFs 50/50, crop to 16:9/A4/A3, or crop margins. Route: Source → Target.",
        ),
        "add_pdf": (
            "Выберите нумерацию страниц или уменьшение содержимого PDF по маршруту Source → Target.",
            "Choose page numbering or PDF content scaling through the Source → Target route.",
        ),
        "page_numbers": (
            "Добавить колонтитул с номерами страниц в PDF из Source и сохранить результат в Target.",
            "Add page numbers to PDFs from Source and save results under Target.",
        ),
        "scale_pdf": (
            "Уменьшить содержимое PDF без изменения размера страницы. Маршрут: Source → Target.",
            "Scale PDF contents without changing page size. Route: Source → Target.",
        ),
    }
    pair = descriptions[module_id]
    return pair[0] if ru else pair[1]


def child_header(title: str, on_back: Any, run_handler: Any | None = None) -> None:
    with ui.row().classes("w-full items-center gap-2 pb-1"):
        ui.button(tr("back"), on_click=on_back).props("dense flat no-wrap").classes("audion-action w-28 rounded-lg")
        ui.label(title).classes("min-w-0 flex-1 truncate text-base font-semibold text-center")
        if run_handler is None:
            ui.element("div").classes("audion-nav-run-spacer")
        else:
            ui.button(tr("run"), on_click=run_handler).props("dense flat no-wrap").classes("audion-action audion-nav-run-button rounded-lg")


def adjusted_number_control_value(
    current: Any,
    default: Any,
    minimum: Any,
    maximum: Any,
    step_raw: Any,
    direction: int,
) -> int | float:
    try:
        step = float(step_raw)
    except (TypeError, ValueError):
        step = 1.0
    try:
        value = float(current if current not in {None, ""} else default if default not in {None, ""} else 0)
    except (TypeError, ValueError):
        value = 0.0

    value += step * (1 if direction > 0 else -1)
    for bound, clamp in ((minimum, max), (maximum, min)):
        if bound is None or bound == "":
            continue
        try:
            value = clamp(value, float(bound))
        except (TypeError, ValueError):
            continue
    return int(round(value)) if float(step).is_integer() else round(value, 6)


def spin_number_control(control: Any, default: Any, minimum: Any, maximum: Any, step: Any, direction: int) -> None:
    value = adjusted_number_control_value(getattr(control, "value", None), default, minimum, maximum, step, direction)
    control.set_value(value)


def audion_number(*args: Any, classes: str = "w-36", **kwargs: Any) -> Any:
    default = kwargs.get("value")
    minimum = kwargs.get("min")
    maximum = kwargs.get("max")
    step = kwargs.get("step", 1)
    control = ui.number(*args, **kwargs).props("dense outlined").classes(f"audion-number {classes}")
    with control.add_slot("append"):
        with ui.element("div").classes("audion-number-spinner"):
            ui.button(
                icon="keyboard_arrow_up",
                on_click=lambda item=control: spin_number_control(item, default, minimum, maximum, step, 1),
            ).props("dense flat round tabindex=-1").classes("audion-number-spin-button")
            ui.button(
                icon="keyboard_arrow_down",
                on_click=lambda item=control: spin_number_control(item, default, minimum, maximum, step, -1),
            ).props("dense flat round tabindex=-1").classes("audion-number-spin-button")
    return control


def collect_selected_options(groups: list[dict[str, Any]], group_controls: dict[str, dict[str, Any]]) -> dict[str, list[str]] | None:
    selected: dict[str, list[str]] = {}
    for group in groups:
        group_id = str(group["id"])
        ids = [
            choice_id
            for choice_id, checkbox in group_controls.get(group_id, {}).items()
            if bool(checkbox.value)
        ]
        if len(ids) < int(group.get("min_selected", 0) or 0):
            safe_notify(tr("no_options_selected"), type="warning")
            return None
        selected[group_id] = ids
    return selected


def render_option_groups(groups: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    group_controls: dict[str, dict[str, Any]] = {}
    for group in groups:
        group_id = str(group["id"])
        group_controls[group_id] = {}
        ui.label(localized_text(group, "title")).classes("text-sm font-semibold")
        description = localized_text(group, "description")
        if description:
            ui.label(description).classes("text-xs text-gray-400")
        with ui.element("div").classes("audion-checkbox-grid w-full pt-1"):
            for choice in group.get("choices", []):
                checkbox = ui.checkbox(
                    localized_text(choice, "label"),
                    value=bool(choice.get("default", False)),
                ).props("dense").classes("audion-checkbox-item")
                group_controls[group_id][str(choice["id"])] = checkbox
    return group_controls


def render_input_conversion_screen() -> None:
    operation_id = "batch_recursive"
    operation = OPERATIONS[operation_id]
    groups = operation.get("option_groups", [])
    with ui.column().classes("w-full gap-2"):
        async def submit() -> None:
            selected = collect_selected_options(groups, group_controls)
            if selected is None:
                return
            percent = float(scale_percent.value or 98) if str(post_scale.value or "none") == "percent" else 100.0
            await start_convert_operation(
                str(current_source_path()),
                str(current_target_path()),
                selected,
                str(post_crop.value or "none"),
                percent,
            )

        child_header(op_text(operation_id, "title"), lambda: set_command_screen("main"), submit)
        ui.label(op_text(operation_id, "description")).classes("text-sm text-gray-300")
        group_controls = render_option_groups(groups)
        ui.label(tr("post_crop")).classes("text-sm font-semibold")
        post_crop = ui.radio(
            {"none": tr("aspect_none"), "16:9": "16:9", "a-series": "A4/A3"},
            value="none",
        ).props("inline dense")
        ui.label(tr("post_scale")).classes("text-sm font-semibold")
        post_scale = ui.radio(
            {"none": tr("scale_none"), "percent": tr("scale_percent")},
            value="none",
        ).props("inline dense")
        scale_percent = audion_number(tr("scale_percent_field"), value=98, min=1, max=100, step=0.5, classes="w-36")


def render_custom_conversion_screen() -> None:
    operation = OPERATIONS["batch_recursive"]
    groups = operation.get("option_groups", [])
    with ui.column().classes("w-full gap-3"):
        async def submit() -> None:
            selected = collect_selected_options(groups, group_controls)
            if selected is None:
                return
            percent = float(scale_percent.value or 98) if str(post_scale.value or "none") == "percent" else 100.0
            await start_convert_operation(
                str(current_source_path()),
                str(current_target_path()),
                selected,
                str(post_crop.value or "none"),
                percent,
            )

        child_header(tr("convert_setup"), lambda: set_active_module("root"), submit)

        with ui.column().classes("audion-panel w-full gap-2 p-3"):
            group_controls = render_option_groups(groups)

        with ui.column().classes("audion-panel w-full gap-3 p-3"):
            with ui.element("div").classes("audion-post-grid w-full"):
                with ui.column().classes("audion-post-cell gap-2"):
                    ui.label(tr("post_crop")).classes("audion-post-title text-sm font-semibold text-center")
                    with ui.row().classes("audion-radio-row w-full"):
                        post_crop = ui.radio(
                            {"none": tr("aspect_none"), "16:9": "16:9", "a-series": "A4/A3"},
                            value="none",
                        ).props("inline dense").classes("audion-radio audion-radio-three")
                with ui.column().classes("audion-post-cell gap-2"):
                    ui.label(tr("post_scale")).classes("audion-post-title text-sm font-semibold text-center")
                    with ui.row().classes("audion-radio-row w-full"):
                        post_scale = ui.radio(
                            {"none": tr("scale_none"), "percent": tr("scale_percent")},
                            value="none",
                        ).props("inline dense").classes("audion-radio audion-radio-two")
                    with ui.row().classes("w-full justify-center"):
                        scale_percent = audion_number(tr("scale_percent_field"), value=98, min=1, max=100, step=0.5, classes="w-36")


@ui.refreshable
def command_area() -> None:
    screen = str(state.get("command_screen") or "main")
    if screen in {"main", "convert_custom"}:
        render_custom_conversion_screen()
        return
    if screen == "convert_input":
        render_input_conversion_screen()
        return


@ui.refreshable
def crop_pdf_area() -> None:
    screen = str(state.get("crop_pdf_screen") or "main")
    if screen == "pptx":
        with ui.column().classes("w-full gap-2"):
            async def submit_pptx_crop() -> None:
                operation_id = "crop_pptx_force" if bool(repeat_crop.value) else "crop_pptx"
                await start_operation(operation_id)

            child_header(tr("crop_pptx_setup"), lambda: set_active_module("root"), submit_pptx_crop)
            ui.label(op_text("crop_pptx", "description")).classes("text-sm text-gray-300")
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                repeat_crop = ui.checkbox(tr("repeat_crop"), value=False).props("dense").classes("audion-checkbox-item")
        return

    if screen == "manual":
        with ui.column().classes("w-full gap-3"):
            async def submit_manual_crop() -> None:
                mode = str(margins_mode.value or action_mode.value or "split_vertical")
                if mode == "split_vertical":
                    command = [gui_cli_python(), "-u", str(MAIN_PY), "pdf-split", "--orientation", "vertical"]
                    if bool(skip_cover.value):
                        command.append("--skip-cover")
                    command.extend(pdf_workspace_cli_args())
                    await start_raw_cli_operation(
                        tr("split_vertical"),
                        command,
                    )
                    return
                if mode == "split_horizontal":
                    command = [gui_cli_python(), "-u", str(MAIN_PY), "pdf-split", "--orientation", "horizontal"]
                    if bool(skip_cover.value):
                        command.append("--skip-cover")
                    command.extend(pdf_workspace_cli_args())
                    await start_raw_cli_operation(
                        tr("split_horizontal"),
                        command,
                    )
                    return
                if mode == "aspect_16_9":
                    await start_raw_cli_operation(
                        tr("aspect_crop"),
                        [gui_cli_python(), "-u", str(MAIN_PY), "pdf-crop-aspect", "--mode", "16:9", *pdf_workspace_cli_args()],
                    )
                    return
                if mode == "aspect_a_series":
                    await start_raw_cli_operation(
                        tr("aspect_crop"),
                        [gui_cli_python(), "-u", str(MAIN_PY), "pdf-crop-aspect", "--mode", "a-series", *pdf_workspace_cli_args()],
                    )
                    return
                await start_raw_cli_operation(
                    tr("crop_margins"),
                    [
                        gui_cli_python(),
                        "-u",
                        str(MAIN_PY),
                        "pdf-crop-margins",
                        "--left-mm",
                        str(left.value or 0),
                        "--right-mm",
                        str(right.value or 0),
                        "--top-mm",
                        str(top.value or 0),
                        "--bottom-mm",
                        str(bottom.value or 0),
                        *pdf_workspace_cli_args(),
                    ],
                )

            child_header(tr("crop_pdf_manual_setup"), lambda: set_active_module("root"), submit_manual_crop)
            with ui.column().classes("audion-panel w-full gap-3 p-3"):
                ui.label(tr("pdf_crop_action")).classes("text-sm font-semibold text-center")
                action_options = {
                    "split_vertical": tr("split_vertical"),
                    "split_horizontal": tr("split_horizontal"),
                    "aspect_16_9": tr("aspect_16_9"),
                    "aspect_a_series": tr("aspect_a_series"),
                }
                with ui.row().classes("audion-radio-row audion-radio-row-left w-full"):
                    action_mode = ui.radio(action_options, value="split_vertical").props("inline dense").classes("audion-radio")
                with ui.row().classes("w-full justify-start pt-1"):
                    skip_cover = ui.checkbox(tr("skip_cover"), value=False).props("dense").classes("audion-checkbox-item")
                ui.label(tr("skip_cover_hint")).classes("text-xs text-gray-400")
            with ui.column().classes("audion-panel w-full gap-3 p-3"):
                with ui.row().classes("w-full items-center gap-3"):
                    margins_mode = ui.radio({"margins": tr("crop_margins")}, value=None).props("inline dense").classes("audion-radio")
                with ui.row().classes("w-full flex-wrap gap-3"):
                    left = audion_number(tr("left_mm"), value=0, min=0, step=1, classes="w-32")
                    right = audion_number(tr("right_mm"), value=0, min=0, step=1, classes="w-32")
                    top = audion_number(tr("top_mm"), value=0, min=0, step=1, classes="w-32")
                    bottom = audion_number(tr("bottom_mm"), value=0, min=0, step=1, classes="w-32")

            syncing_manual_pdf_mode = {"active": False}

            def clear_margin_mode(event: Any) -> None:
                if syncing_manual_pdf_mode["active"] or not getattr(event, "value", None):
                    return
                syncing_manual_pdf_mode["active"] = True
                margins_mode.set_value(None)
                syncing_manual_pdf_mode["active"] = False

            def clear_action_mode(event: Any) -> None:
                if syncing_manual_pdf_mode["active"] or getattr(event, "value", None) != "margins":
                    return
                syncing_manual_pdf_mode["active"] = True
                action_mode.set_value(None)
                syncing_manual_pdf_mode["active"] = False

            action_mode.on_value_change(clear_margin_mode)
            margins_mode.on_value_change(clear_action_mode)
        return

    with ui.column().classes("w-full gap-2"):
        child_header(tr("crop_pdf_setup"), lambda: set_active_module("root"))
        command_row(
            tr("crop_pptx_setup"),
            op_text("crop_pptx", "description"),
            lambda: set_crop_pdf_screen("pptx"),
        )
        command_row(
            tr("crop_pdf_manual_setup"),
            "Разрезать PDF 50/50, кадрировать под 16:9/A4/A3 или обрезать поля. Маршрут: Source → Target."
            if settings["language"] == "ru"
            else "Split PDFs 50/50, crop to 16:9/A4/A3, or crop margins. Route: Source → Target.",
            lambda: set_crop_pdf_screen("manual"),
        )


@ui.refreshable
def add_pdf_area() -> None:
    screen = str(state.get("add_pdf_screen") or "main")
    if screen == "page_numbers":
        with ui.column().classes("w-full gap-2"):
            async def submit_page_numbers() -> None:
                await start_raw_cli_operation(
                    tr("page_numbers"),
                    [
                        gui_cli_python(),
                        "-u",
                        str(MAIN_PY),
                        "pdf-page-numbers",
                        "--start-page",
                        str(int(start_page.value or 1)),
                        "--start-number",
                        str(int(start_number.value or 1)),
                        "--offset-mm",
                        str(offset.value or 0),
                        "--position",
                        str(position.value or "bottom-right"),
                        *pdf_workspace_cli_args(),
                    ],
                )

            child_header(tr("page_numbers_setup"), lambda: set_active_module("root"), submit_page_numbers)
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                ui.label(tr("page_numbers")).classes("text-sm font-semibold")
                with ui.row().classes("w-full flex-wrap gap-2"):
                    start_page = audion_number(tr("start_page"), value=1, min=1, step=1, classes="w-40")
                    start_number = audion_number(tr("start_number"), value=1, min=0, step=1, classes="w-40")
                    offset = audion_number(tr("offset_mm"), value=10, min=0, step=1, classes="w-40")
                    position = ui.select(
                        page_number_position_options(),
                        value="bottom-right",
                        label=tr("position"),
                    ).props("dense outlined popup-content-class=audion-select-popup").classes("audion-select w-52")
        return

    if screen == "scale":
        with ui.column().classes("w-full gap-2"):
            async def submit_scale_pdf_content() -> None:
                await start_raw_cli_operation(
                    tr("scale_pdf_content"),
                    [
                        gui_cli_python(),
                        "-u",
                        str(MAIN_PY),
                        "pdf-scale-content",
                        "--percent",
                        str(pdf_scale_percent.value or 98),
                        *pdf_workspace_cli_args(),
                    ],
                )

            child_header(tr("scale_pdf_setup"), lambda: set_active_module("root"), submit_scale_pdf_content)
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                ui.label(tr("scale_pdf_content")).classes("text-sm font-semibold")
                with ui.row().classes("w-full flex-wrap justify-center gap-2"):
                    pdf_scale_percent = audion_number(tr("scale_percent_field"), value=98, min=1, max=100, step=0.5, classes="w-36")
        return

    with ui.column().classes("w-full gap-2"):
        child_header(tr("add_pdf_setup"), lambda: set_active_module("root"))
        command_row(
            tr("page_numbers_setup"),
            "Добавить колонтитул с номерами страниц в PDF из Source и сохранить результат в Target."
            if settings["language"] == "ru"
            else "Add page numbers to PDFs from Source and save results under Target.",
            lambda: set_add_pdf_screen("page_numbers"),
        )
        command_row(
            tr("scale_pdf_setup"),
            "Уменьшить содержимое PDF без изменения размера страницы. Маршрут: Source → Target."
            if settings["language"] == "ru"
            else "Scale PDF contents without changing page size. Route: Source → Target.",
            lambda: set_add_pdf_screen("scale"),
        )


@ui.refreshable
def operations_area() -> None:
    active_module = str(state.get("active_module") or "root")
    crop_ids = [operation_id for operation_id in MAIN_OPERATION_IDS if operation_id.startswith("crop_")]
    utility_ids = [
        operation_id
        for operation_id in MAIN_OPERATION_IDS
        if operation_id != "batch_recursive" and operation_id not in crop_ids
    ]

    if active_module == "conversion":
        with ui.column().classes("w-full gap-3"):
            command_area()
        return

    if active_module in {"crop_pdf", "crop_pptx", "crop_manual"}:
        with ui.column().classes("w-full gap-3"):
            crop_pdf_area()
        return

    if active_module in {"add_pdf", "page_numbers", "scale_pdf"}:
        with ui.column().classes("w-full gap-3"):
            add_pdf_area()
        return

    with ui.column().classes("w-full gap-3"):
        with ui.column().classes("audion-panel w-full gap-1 p-3"):
            ui.label(tr("document_operations")).classes("text-sm font-semibold text-gray-300")
            command_row(tr("conversion_group"), module_description("conversion"), lambda: set_active_module("conversion"))

        with ui.column().classes("audion-panel w-full gap-1 p-3"):
            ui.label(tr("pdf_operations")).classes("text-sm font-semibold text-gray-300")
            command_row(tr("crop_pptx_setup"), module_description("crop_pptx"), lambda: set_active_module("crop_pptx"))
            command_row(tr("crop_pdf_manual_setup"), module_description("crop_manual"), lambda: set_active_module("crop_manual"))
            command_row(tr("page_numbers_setup"), module_description("page_numbers"), lambda: set_active_module("page_numbers"))
            command_row(tr("scale_pdf_setup"), module_description("scale_pdf"), lambda: set_active_module("scale_pdf"))

        for operation_id in utility_ids:
            operation_button(operation_id)


def folder_button(folder_id: str) -> None:
    folder = FOLDERS[folder_id]
    with ui.row().classes("w-full items-center gap-3"):
        ui.button(folder_id, on_click=lambda item=folder_id: open_folder(item)).props("dense flat no-wrap").classes("audion-action w-20 rounded-lg")
        ui.label(str(folder)).classes("min-w-0 flex-1 truncate font-mono text-xs text-gray-300")


def toggle_language() -> None:
    settings["language"] = "en" if settings["language"] == "ru" else "ru"
    save_settings()
    reload_ui()


_application_css_cache: dict[str, str] = {}


def application_css(name: str) -> str:
    """A stylesheet that lives next to this module rather than inside it."""
    if name not in _application_css_cache:
        path = Path(__file__).resolve().with_name(name)
        _application_css_cache[name] = path.read_text(encoding="utf-8")
    return _application_css_cache[name]


def build_ui() -> None:
    add_audion_canonical_ui_styles()
    ensure_dirs()
    load_settings()
    if not state["status"]:
        state["status"] = tr("idle")
    if active_theme_mode() == "dark":
        ui.dark_mode().enable()
    else:
        ui.dark_mode().disable()

    variables_css = "\n".join(
        f"  --{key}: {value};"
        for key, value in sorted(theme_variables().items())
    )
    ui.add_head_html(
        (
            "<style>\n"
            ":root {\n"
            f"{variables_css}\n"
            "  --audion-bg: var(--color-background-tertiary);\n"
            "  --audion-header-bg: var(--color-background-primary);\n"
            "  --audion-header-text: var(--color-text-primary);\n"
            "  --audion-panel-bg: var(--color-background-secondary);\n"
            "  --audion-terminal-bg: var(--color-background-tertiary);\n"
            "  --audion-terminal-background: var(--audion-terminal-bg);\n"
            "  --audion-block-background: var(--audion-header-bg);\n"
            "  --audion-text: var(--color-text-primary);\n"
            "  --audion-secondary-text: var(--color-text-secondary);\n"
            "  --audion-muted-text: var(--color-text-tertiary);\n"
            "  --audion-button-text: var(--color-accent-primary);\n"
            "  --audion-button-hover-bg: var(--color-background-primary);\n"
            "  --audion-button-hover-background: var(--audion-button-hover-bg);\n"
            "  --audion-panel-border: color-mix(in srgb, var(--color-border-tertiary) 62%, transparent 38%);\n"
            "  --audion-divider: color-mix(in srgb, var(--color-border-tertiary) 48%, transparent 52%);\n"
            "  --audion-button-hover-border: var(--audion-input-border-hover);\n"
            "  --audion-border: var(--audion-panel-border);\n"
            "  --audion-strong-border: var(--audion-input-border-hover);\n"
            "  --audion-input-border: color-mix(in srgb, var(--color-border-secondary) 54%, transparent 46%);\n"
            "  --audion-input-border-hover: color-mix(in srgb, var(--color-border-secondary) 72%, transparent 28%);\n"
            "  --audion-input-border-focus: color-mix(in srgb, var(--color-accent-primary) 78%, var(--color-border-secondary) 22%);\n"
            "  --audion-control-chip: color-mix(in srgb, var(--color-background-primary) 92%, var(--color-text-primary) 8%);\n"
            "  --audion-control-chip-hover: color-mix(in srgb, var(--color-background-primary) 88%, var(--color-text-primary) 12%);\n"
            "  --audion-control-chip-active: color-mix(in srgb, var(--color-background-primary) 84%, var(--color-accent-primary) 16%);\n"
            "  --audion-control-ring: color-mix(in srgb, var(--color-border-secondary) 46%, transparent 54%);\n"
            "  --audion-control-ring-active: color-mix(in srgb, var(--color-accent-primary) 64%, var(--color-border-secondary) 36%);\n"
            "  --audion-terminal-border: var(--audion-panel-border);\n"
            "  --audion-gui-font: var(--font-sans);\n"
            "  --audion-terminal-font: var(--font-mono);\n"
            "  --audion-button-size: 13px;\n"
            "  --audion-terminal-size: 12px;\n"
            "  --audion-terminal-line-height: 1.35;\n"
            "}\n"
            "</style>\n"
        )
    )

    ui.add_head_html(
        "<style>\n"
        + application_css("theme.css")
        + "\n</style>\n"
    )
    ui.add_head_html(f"<style>{WORKBENCH_LAYOUT_CSS}\n{WORKBENCH_OVERRIDE_CSS}</style>")
    ui.add_head_html(WORKBENCH_FEEDBACK_CSS)

    with ui.header().classes("audion-header h-[42px] items-center justify-between px-4"):
        ui.label("Audion Doc to PDF").classes("audion-header-title text-lg font-bold")
        with ui.row().classes("audion-header-controls items-center gap-2"):
            ui.icon("palette").classes("text-lg")
            ui.select(
                options=theme_options(),
                value=active_theme(),
                on_change=theme_change_handler,
            ).props("dense outlined options-dense").classes("audion-theme-select")
            ui.button(tr("lang_switch"), on_click=toggle_language).props("dense flat").classes("audion-button rounded-lg")
            cancel_button = ui.button(tr("cancel"), on_click=lambda: state.update({"cancel": True})).props("dense flat color=negative")
            cancel_button.visible = False

    with ui.element("div").classes("audion-shell"):
        with ui.column().classes("audion-pane audion-scroll gap-3"):
            with ui.column().classes("audion-panel audion-workspace-panel w-full gap-2 p-2"):
                WORKBENCH_RENDERER.render_address_rows()
                WORKBENCH_RENDERER.render_action_bar()

            ui.label(f"{em('operations')}{tr('operations')}").classes("text-lg font-bold")
            operations_area()

        with ui.element("div").classes("audion-pane audion-right gap-2 pt-3"):
            with ui.column().classes("audion-panel w-full gap-2 p-3"):
                with ui.row().classes("w-full items-center gap-3"):
                    ui.label(f"{em('status')}{tr('status')}").classes("text-base font-semibold")
                    status_label = ui.label(str(state["status"])).classes("min-w-0 flex-1 text-sm text-gray-300")
                with ui.row().classes("w-full items-center gap-3"):
                    progress = ui.linear_progress(value=0.0, show_value=False).classes("min-w-0 flex-1")
                    progress_label = ui.label(progress_text()).classes("w-12 text-right text-sm text-gray-300")

            with ui.column().classes("audion-terminal-panel w-full gap-2 p-3"):
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(f"{em('log')}{tr('log')}").classes("text-base font-semibold")
                    ui.space()
                    ui.button("Logs", on_click=lambda: open_folder("logs")).props("dense flat").classes("audion-button rounded-lg").tooltip(audion_folder_button_tooltip("logs", FOLDERS.get("logs", "logs") if "FOLDERS" in globals() else "logs"))
                    ui.button("CONFIG", on_click=lambda: open_folder("config")).props("dense flat").classes("audion-button rounded-lg").tooltip(audion_folder_button_tooltip("config", FOLDERS.get("config", "config") if "FOLDERS" in globals() else "config"))
                    ui.button(tr("report"), on_click=lambda: open_folder("report")).props("dense flat").classes("audion-button rounded-lg").tooltip(audion_folder_button_tooltip("report", FOLDERS.get("report", "report") if "FOLDERS" in globals() else "report"))
                    clear_log_button = ui.button(icon="delete_sweep", on_click=clear_terminal_log).props("dense flat round").classes("audion-button audion-log-icon-button")
                    clear_log_button.tooltip(audion_terminal_action_tooltip("clear_terminal_window"))
                    expand_log_button = ui.button(icon="open_in_full", on_click=lambda: log_dialog.open()).props("dense flat round").classes("audion-button audion-log-icon-button")
                    expand_log_button.tooltip(audion_terminal_action_tooltip("expand_log"))
                log_view = ui.html("", sanitize=False, tag="pre").classes("audion-terminal audion-terminal-html w-full min-h-[66vh]")
                with ui.row().classes("audion-terminal-footer w-full items-center gap-2 px-1 pt-1"):
                    status_dot = ui.label("●").classes(status_dot_classes())
                    terminal_status_label = ui.label(str(state["status"])).classes("min-w-0 flex-1 truncate text-xs")

    with ui.dialog() as log_dialog:
        with ui.card().classes("h-[92vh] w-[92vw] rounded-lg p-3").style("background: var(--audion-terminal-bg);"):
            with ui.row().classes("w-full items-center gap-2"):
                ui.label(f"{em('log')}{tr('log')}").classes("text-base font-semibold")
                ui.space()
                clear_expanded_log_button = ui.button(icon="delete_sweep", on_click=clear_terminal_log).props("dense flat round").classes("audion-button audion-log-icon-button")
                clear_expanded_log_button.tooltip(audion_terminal_action_tooltip("clear_terminal_window"))
                ui.button(tr("close"), on_click=log_dialog.close).props("dense flat").classes("audion-button rounded-lg").tooltip(audion_terminal_action_tooltip("close"))
            expanded_log_view = ui.html("", sanitize=False, tag="pre").classes("audion-terminal audion-terminal-html audion-terminal-expanded w-full")

    last_log_version = {"value": -1}
    rendered_terminal_sequence = {"value": 0}
    rendered_terminal_reset = {"value": -1}
    refresh_timer: Any | None = None

    def clear_terminal_dom() -> None:
        ui.run_javascript(
            """
            requestAnimationFrame(() => {
              document.querySelectorAll('.audion-terminal-html').forEach((el) => {
                el.replaceChildren();
              });
            });
            """
        )

    def append_terminal_dom(html_fragment: str, *, scroll_top: bool = False) -> None:
        fragment = json.dumps(html_fragment, ensure_ascii=False)
        scroll_top_payload = "true" if scroll_top else "false"
        ui.run_javascript(
            f"""
            requestAnimationFrame(() => {{
              const fragment = {fragment};
              const scrollTop = {scroll_top_payload};
              const maxLines = {TERMINAL_HISTORY_LIMIT};
              document.querySelectorAll('.audion-terminal-html').forEach((el) => {{
                const wasAtBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 8;
                el.insertAdjacentHTML('beforeend', fragment);
                let lines = el.querySelectorAll('.audion-terminal-line');
                while (lines.length > maxLines) {{
                  lines[0].remove();
                  lines = el.querySelectorAll('.audion-terminal-line');
                }}
                if (scrollTop) {{
                  el.scrollTop = 0;
                }} else if (wasAtBottom) {{
                  el.scrollTop = el.scrollHeight;
                }}
              }});
            }});
            """
        )

    def refresh() -> None:
        nonlocal refresh_timer
        try:
            status_label.text = str(state["status"])
            status_dot.classes(replace=status_dot_classes())
            terminal_status_label.text = str(state["status"])
            progress.value = float(state["progress"])
            progress_label.text = progress_text()
            log_version = int(state["log_version"])
            if log_version != last_log_version["value"]:
                last_log_version["value"] = log_version
                terminal_sequence = int(state.get("terminal_sequence") or 0)
                terminal_reset_id = int(state.get("terminal_reset_id", 0))
                lines = list(state["lines"])
                first_sequence = terminal_sequence - len(lines)
                if terminal_reset_id != rendered_terminal_reset["value"] or terminal_sequence < rendered_terminal_sequence["value"]:
                    clear_terminal_dom()
                    rendered_terminal_reset["value"] = terminal_reset_id
                    rendered_terminal_sequence["value"] = 0
                if rendered_terminal_sequence["value"] < first_sequence:
                    clear_terminal_dom()
                    scroll_top = int(state.get("terminal_scroll_top_seq", 0)) and int(state.get("terminal_scroll_top_seq", 0)) <= terminal_sequence
                    if scroll_top:
                        state["terminal_scroll_top_seq"] = 0
                    append_terminal_dom(terminal_html(), scroll_top=bool(scroll_top))
                    rendered_terminal_sequence["value"] = terminal_sequence
                else:
                    start_index = max(0, rendered_terminal_sequence["value"] - first_sequence)
                    new_lines = lines[start_index:]
                    if new_lines:
                        scroll_top = int(state.get("terminal_scroll_top_seq", 0)) and int(state.get("terminal_scroll_top_seq", 0)) <= terminal_sequence
                        if scroll_top:
                            state["terminal_scroll_top_seq"] = 0
                        append_terminal_dom(terminal_lines_html(new_lines), scroll_top=bool(scroll_top))
                    rendered_terminal_sequence["value"] = terminal_sequence
            cancel_button.visible = bool(state["running"])
        except RuntimeError as exc:
            message = str(exc)
            if "slot belongs to has been deleted" not in message and "current slot cannot be determined" not in message:
                raise
            logging.warning("NiceGUI refresh timer stopped because the client slot was deleted.")
            if refresh_timer is not None:
                refresh_timer.deactivate()

    refresh_timer = ui.timer(0.5, refresh)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audion Doc to PDF NiceGUI shell.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


def port_is_open(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in str(host or "") else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def assert_gui_host_allowed(host: str) -> None:
    normalized = str(host or "").strip().lower().strip("[]")
    try:
        is_loopback = normalized == "localhost" or ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        is_loopback = normalized == "localhost"
    if is_loopback or str(os.environ.get("AUDION_ALLOW_REMOTE_GUI", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return
    raise SystemExit(
        "Refusing non-loopback host for a GUI with process execution. "
        "Use 127.0.0.1/localhost/::1, or set AUDION_ALLOW_REMOTE_GUI=1 explicitly."
    )


def build_ui_once() -> dict[str, int]:
    """Build the whole page once, headlessly, and report what came of it.

    `--smoke` used to print a line and return, so an app could ship a `build_ui`
    that raised on its first statement and still pass — twice in this fleet it did.
    Here the page is actually built: no browser and no HTTP request, so whatever
    the app defers until a client attaches is skipped, but every widget is
    constructed and the stylesheet has to arrive.
    """
    import asyncio
    import logging
    import re

    from nicegui import core
    from nicegui.client import Client
    from nicegui.page import page as page_definition

    async def build() -> tuple[int, str]:
        core.loop = asyncio.get_running_loop()
        # Work deferred to a connected browser fails here and says nothing about
        # the build. An exception raised by build_ui itself still propagates.
        core.loop.set_exception_handler(lambda _loop, _context: None)
        logging.getLogger("nicegui").setLevel(logging.CRITICAL)
        client = Client(page_definition("/__smoke__"))
        with client:
            build_ui()
        report = len(client.elements), client.shared_head_html + client.head_html
        # The page starts work that waits for a browser to attach. Nothing will
        # attach, so stop it deliberately instead of letting the loop close on it.
        pending = asyncio.all_tasks(core.loop) - {asyncio.current_task()}
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return report

    element_count, head = asyncio.run(build())
    if element_count < 2:
        raise RuntimeError("build_ui produced no widgets")
    # Token prefixes differ between apps, so look for any custom property rather
    # than for one project's naming.
    if not re.search(r"--[\w-]+\s*:", head):
        raise RuntimeError("the stylesheet never reached the page")
    return {"elements": element_count, "stylesheet_bytes": len(head)}


def main() -> int:
    args = parse_args()
    ensure_dirs()
    assert_gui_host_allowed(args.host)
    if args.smoke:
        try:
            report = build_ui_once()
        except Exception as error:  # noqa: BLE001
            print(f"FAIL nicegui shell: {ROOT}: {error}")
            return 1
        print(
            f"OK nicegui shell: {ROOT}"
            f" | widgets={report['elements']}"
            f" | stylesheet={report['stylesheet_bytes']} bytes"
        )
        return 0

    if port_is_open(args.host, args.port):
        url = f"http://{args.host}:{args.port}/"
        print(f"Audion Doc to PDF GUI already appears to be running: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    ui.run(
        root=build_ui,
        title="Audion Doc to PDF",
        host=args.host,
        port=args.port,
        reload=False,
        native=False,
        show=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
