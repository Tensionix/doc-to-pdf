# Audion Doc to PDF

Portable Windows-инструмент для пакетной конвертации Word, Excel и PowerPoint в PDF через родной экспорт Microsoft Office, а также для типовой обработки готовых PDF.

## Возможности

- рекурсивная конвертация папки с зеркалированием структуры;
- конвертация одного Office-файла;
- пост-кадрирование презентаций под `16:9` или A-серию;
- масштабирование содержимого презентаций;
- разрезание, кадрирование, обрезка полей, нумерация и масштабирование готовых PDF;
- metadata в `report\latest\metadata` и архивах запусков;
- единые GUI и CLI-маршруты Source/Target.

- Word: `.doc`, `.docx`, `.docm`, `.rtf`, `.txt`, `.odt`
- Excel: `.xls`, `.xlsx`, `.xlsm`, `.xlsb`, `.csv`, `.ods`
- PowerPoint: `.ppt`, `.pptx`, `.pptm`, `.odp`

## GUI

Запустите `launcher_gui.cmd`. Канонический Workbench I/O сверху слева задаёт прямые маршруты:

- `Source` — папка либо один Office/PDF-файл;
- `Target` — папка результата;
- исходные данные не копируются в staging и не помещаются в кэш;
- `input` и `output` остаются безопасными начальными значениями и CLI-значениями по умолчанию.

История путей локальна и не хранится в Git. Закрепления, блокировки, выбор файла/папки, просмотр списка, сброс и защищённое удаление реализованы одинаково с другими Audion Workbench-проектами.

Подробности: `docs\GUI_RU.md`.

## CLI

Конвертировать стандартный `input` в `output`:

```bat
python system_core\main.py batch --recursive --extensions docx,pptx,xlsx
```

Конвертировать произвольные папки:

```bat
python system_core\main.py batch --recursive --input-dir "D:\DOCS" --output-dir "E:\PDF" --extensions docx,pptx,xlsx
```

Конвертировать один файл:

```bat
python system_core\main.py file --input "D:\DOCS\report.docx" --output-dir "E:\PDF"
```

Обработать один PDF или папку PDF по явному маршруту:

```bat
python system_core\main.py pdf-crop-aspect --mode "16:9" --input-dir "D:\PDF\source.pdf" --output-dir "E:\PDF"
python system_core\main.py pdf-scale-content --percent 98 --input-dir "D:\PDF" --output-dir "E:\PDF"
```

Без `--input-dir/--output-dir` сохраняется прежнее поведение `input -> output`.

## Рабочие данные

- `input`, `output` — маршруты по умолчанию;
- `report` — metadata и архивы запусков;
- `logs` — журналы CLI и GUI;
- `config` — manifest, темы и настройки.

`cleanup_project.cmd` удаляет только generated/runtime-содержимое, заявленное самим скриптом. Перед распространением проект проверяется через `install\Check-CmdEncoding.cmd` и smoke/doctor-команды.

## Требования

- Windows;
- установленный Microsoft Office desktop;
- portable runtime проекта либо совместимый Python;
- `pypdf`, `nicegui`, `pyyaml`, `rich`, `pywebview`.

Главные файлы: `launcher_gui.cmd`, `system_core\main.py`, `system_core\office_export.ps1`, `system_core\ui_nicegui\app.py`, `system_core\ui_nicegui\workbench.py`, `config\tool_manifest.yaml`.
