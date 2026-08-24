# GUI: Audion Doc to PDF

The GUI is a control shell over the same CLI. The canonical Workbench I/O and operations are on the left; status, progress, and the streaming log remain on the right.

## Workbench I/O

Workbench does not copy documents or build a staging cache. `Source` points directly to a folder or one Office/PDF file; `Target` points to the result folder. Project `input` and `output` are the initial defaults.

Each row supports path pinning, edit locking, content deletion, and a system picker. Pinned history entries stay first. `Reset` restores `input/output` without dropping pins. Deleting an external Source requires separate confirmation; filesystem roots and the project root are protected.

The action bar contains `Add file`, `Add folder`, `Open`, `List`, `Reset`, and `Delete all`. File and folder selection changes the route only; source data is never moved.

## Conversion

The conversion screen consumes the current Source and Target:

- a Source folder is scanned recursively and mirrored under Target;
- one Office file is converted directly into Target;
- checkboxes filter extensions during batch scans;
- PowerPoint exports can be post-cropped to `16:9`/A-series and content-scaled.

Word, Excel, and PowerPoint conversion uses installed Microsoft Office desktop applications.

## PDF operations

Every PDF operation uses the current Source and Target. Source can be one PDF or a folder containing PDFs.

- vertical or horizontal 50/50 page splitting;
- optional cover-page preservation;
- `16:9` or A-series aspect crop;
- margin crop in millimeters;
- page numbering;
- centered content scaling without page-size changes;
- metadata-based cropping of PowerPoint-exported PDFs.

## Log and lifecycle

The GUI shows the actual CLI command and its output. The status indicator is grey while idle, blue while running, green on success, and red on failure. `Logs`, `CONFIG`, and `Report` open their folders; the log can be expanded.

Only one picker can run at a time, and it is bound to the app lifecycle. Closing pywebview stops the server and child processes without leaving a console window.

## Theme and window

Language and theme controls are in the header. Settings are stored in `config\gui_settings.yaml`; palettes are in `config\ui_colors.yaml`. The desktop window remains fixed at `1280x800`; browser mode is explicit via `window.py --browser`.

`Doctor` checks runtime, `pypdf`, PowerShell, and Office COM. `Info` reports formats and settings.
## Canonical Workbench labels

Workbench uses the same Audion Image Tools public vocabulary in every project. Its buttons always keep the same order and labels: **Source**, **Add file...**, **Target**, **Reset**, **Delete**, **List**.

`Reset` returns to project `input/output` and does not delete files; `Delete` clears the current `Source` and `Target` only after confirmation. The exact Russian labels are **Источник**, **Добавить файл...**, **Назначение**, **Сбросить**, **Удалить**, **Список**. The Workbench variants `Destination`, `Clear`, `Цель`, and `Очистить` are not used.

## Result Check

Open every generated PDF before deleting temporary source copies. Check page count, page size, orientation, fonts, images, tables, hyperlinks, headers, footers, and bookmarks when the selected converter supports them. A zero process exit does not guarantee that an external Office renderer preserved layout.

For combined or reordered PDFs, compare the final page sequence with the source list. Keep the log when a document was skipped, repaired, password-protected, or rendered through a fallback engine.
